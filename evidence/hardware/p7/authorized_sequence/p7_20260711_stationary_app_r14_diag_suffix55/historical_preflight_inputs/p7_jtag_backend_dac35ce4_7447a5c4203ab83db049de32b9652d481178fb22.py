#!/usr/bin/env python3
"""Offline generator and strict parser for the P7 direct JTAG/AXI backend.

The module intentionally has no hardware-execution path.  It creates a single
continuous P6 transaction file for an external shutdown-bounded wrapper, or it
parses the wrapper's raw result.  It never sets RF_COMM_HW_AUTH, starts Vivado,
connects to hw_server, programs a device, or opens a network connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config" / "register_map" / "generated"))

import ir_regs as regs  # noqa: E402
from p7_app_protocol import (  # noqa: E402
    AppFragment,
    AppHeader,
    ProtocolError,
    Reassembler,
    atomic_commit,
    crc32,
    segment_object,
)
from p7_app_transport import LanePolicy  # noqa: E402


SCHEMA = "rfap-p7-jtag-axi-dry-run-v1"
TRANSACTION_MAGIC = "P7_JTAG_AXI_TRANSACTIONS_V1"
DEFAULT_BASE_ADDRESS = 0x43C00000
DEFAULT_P6_SESSION = 0x2201
DEFAULT_TIMEOUT_CYCLES = 0x0061A800
DEFAULT_COMMIT_POLLS = 2000
DEFAULT_TRANSFER_POLLS = 10000
DEFAULT_POLL_PERIOD_US = 1000
DEFAULT_TXD_HIGH_LIMIT_CYCLES = 8
P6_MAX_PAYLOAD_BYTES = 247
RFAP_HEADER_BYTES = 32
RFAP_MAX_CHUNK_BYTES = 215
MAX_OBJECT_BYTES = 8 * 1024 * 1024
MAX_TRANSACTION_OPERATIONS = 1_100_000
MAX_TRANSACTION_BYTES = 128 * 1024 * 1024
MAX_TRANSACTION_LINE_BYTES = 512
MAX_RAW_LOG_BYTES = 128 * 1024 * 1024
P6_MAX_RETRY_PER_FRAGMENT = 3
REFERENCE_JTAG_FREQUENCY_HZ = 1_000_000
ESTIMATED_AXI_OPERATION_US_AT_1MHZ = 1_250
ESTIMATED_STAGE_FIXED_OVERHEAD_SECONDS = 30.0
MAX_AUTHORIZED_RUNTIME_SECONDS = 1800
# The JTAG safe wrapper launches exactly four Vivado children: read-only
# preflight, shutdown-before, candidate, and shutdown-after.  For each child,
# the initial empty check and any approved-helper natural-exit grace share one
# fixed 30 second deadline.  The deadline is per contained Vivado Job, not per
# PID, and never resets while the approved topology shrinks.  Forced cleanup
# is a FAIL-only safety action; at most two such cleanup waits can occur along
# one wrapper path (a failed before/candidate child plus shutdown-after), and
# that reserve is carried inside the independent other-overhead guard.
CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS = 0
NON_VIVADO_EMPTY_PROOF_ALLOWANCE_SECONDS = 1
EXPECTED_TOOL_DAEMON_GRACE_SECONDS = 30
CONTAINMENT_TOPOLOGY_REVALIDATION_INTERVAL_SECONDS = 0.10
CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS = 10
CONTAINMENT_FAILURE_BOUND_SECONDS = (
    EXPECTED_TOOL_DAEMON_GRACE_SECONDS + CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS
)
JTAG_WRAPPER_VIVADO_PROCESS_COUNT = 4
JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS = (
    JTAG_WRAPPER_VIVADO_PROCESS_COUNT
    * EXPECTED_TOOL_DAEMON_GRACE_SECONDS
)
JTAG_WRAPPER_MAX_FORCED_CLEANUP_EVENTS = 2
JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS = (
    JTAG_WRAPPER_MAX_FORCED_CLEANUP_EVENTS * CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS
)
JTAG_WRAPPER_BOOKKEEPING_GUARD_SECONDS = 45
JTAG_WRAPPER_OTHER_GUARD_SECONDS = (
    JTAG_WRAPPER_BOOKKEEPING_GUARD_SECONDS
    + JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS
)
JTAG_OUTER_WRAPPER_GRACE_SECONDS = 120

# Source-bound hashes for the only four executables that may remain in a
# Vivado Job after the batch parent exits.  A path match alone cannot grant a
# natural-exit window.
EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE = {
    "cs_server": "9bf0e15ffe162a96679c14b8117cf8ebe8a47b8032bee4ab8cb0317c112df536",
    "rdi_xsdb": "3193d8c4e7115e82e5b4ea6c2eb1aa8a7566bd5a9f9c78e9d901b9eab9d4ebfc",
    "cmd": "75320a519959cc6d089ea3eba33c38caccb7f138a025ea439bc9686cdb79ded4",
    "conhost": "a93cbb36b9c02364be6a72817174c46f94b66715549f279c6592ed659d237911",
}
if JTAG_WRAPPER_OTHER_GUARD_SECONDS < JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS:
    raise RuntimeError("P7 JTAG other guard does not reserve every bounded forced cleanup")
BASELINE_OPERATION_COUNT = 19
PER_FRAGMENT_FIXED_OPERATION_COUNT = 34
FINAL_OPERATION_COUNT = 3

P6_CTRL_CLEAR_STICKY = 1 << 1
P6_CTRL_COMMIT = 1 << 2
P6_CTRL_START = 1 << 3
P6_CTRL_STOP = 1 << 4
P6_CTRL_SHUTDOWN = 1 << 5

P6_STATUS_READY = 1 << 1
P6_STATUS_COMMITTED = 1 << 2
P6_STATUS_DONE = 1 << 4
P6_STATUS_FAIL = 1 << 5
P6_STATUS_CONFIG_REJECTED = 1 << 6
P6_STATUS_TIMEOUT = 1 << 7
P6_STATUS_FAILURE_MASK = P6_STATUS_FAIL | P6_STATUS_CONFIG_REJECTED | P6_STATUS_TIMEOUT

P6_MAILBOX_OK = 0x50364F4B
P6_SHUTDOWN_REASON_TFDU = 0x54464455

COUNTER_OFFSETS: dict[str, int] = {
    "TX_COUNT": regs.IR_REG_P6_TX_COUNT,
    "RX_GOOD_COUNT_L0": regs.IR_REG_P6_RX_GOOD_COUNT_L0,
    "RX_GOOD_COUNT_L1": regs.IR_REG_P6_RX_GOOD_COUNT_L1,
    "CRC_BAD": regs.IR_REG_P6_CRC_BAD,
    "PAYLOAD_MISMATCH": regs.IR_REG_P6_PAYLOAD_MISMATCH,
    "RETRY_COUNT": regs.IR_REG_P6_RETRY_COUNT,
    "RETRY_EXHAUSTED": regs.IR_REG_P6_RETRY_EXHAUSTED,
    "TX_FAIL": regs.IR_REG_P6_TX_FAIL,
    "DUTY_VIOLATION": regs.IR_REG_P6_DUTY_VIOLATION,
    "RAW_TX_PULSES": regs.IR_REG_COUNTER_TX_PULSE,
    "RAW_RX_PULSES": regs.IR_REG_COUNTER_RX_RAW_PULSE,
    "FRAME_GOOD": regs.IR_REG_COUNTER_FRAME_GOOD,
    "FRAME_BAD": regs.IR_REG_COUNTER_FRAME_BAD,
    "ACK_SENT": regs.IR_REG_COUNTER_ACK_SENT,
    "ACK_SEEN": regs.IR_REG_COUNTER_ACK_SEEN,
}

ZERO_DELTA_COUNTERS = {
    "CRC_BAD",
    "PAYLOAD_MISMATCH",
    "RETRY_EXHAUSTED",
    "TX_FAIL",
    "DUTY_VIOLATION",
    "FRAME_BAD",
}


def transaction_shape(object_length: int) -> dict[str, int]:
    """Return the exact generated DSL operation geometry without materializing data."""
    if not isinstance(object_length, int) or isinstance(object_length, bool):
        raise ValueError("object length must be an integer")
    if not 0 <= object_length <= MAX_OBJECT_BYTES:
        raise ValueError(f"object length must be in 0..{MAX_OBJECT_BYTES}")
    if object_length == 0:
        fragment_count = 1
        encoded_word_count = (RFAP_HEADER_BYTES + 3) // 4
    else:
        fragment_count = (object_length + RFAP_MAX_CHUNK_BYTES - 1) // RFAP_MAX_CHUNK_BYTES
        full_fragments, remainder = divmod(object_length, RFAP_MAX_CHUNK_BYTES)
        if remainder == 0:
            encoded_word_count = full_fragments * (
                (RFAP_HEADER_BYTES + RFAP_MAX_CHUNK_BYTES + 3) // 4
            )
        else:
            encoded_word_count = full_fragments * (
                (RFAP_HEADER_BYTES + RFAP_MAX_CHUNK_BYTES + 3) // 4
            ) + (RFAP_HEADER_BYTES + remainder + 3) // 4
    operation_count = (
        BASELINE_OPERATION_COUNT
        + fragment_count * PER_FRAGMENT_FIXED_OPERATION_COUNT
        + 3 * encoded_word_count
        + FINAL_OPERATION_COUNT
    )
    return {
        "object_length": object_length,
        "fragment_count": fragment_count,
        "encoded_word_count": encoded_word_count,
        "operation_count": operation_count,
    }


def runtime_feasibility(
    operation_count: int,
    *,
    jtag_frequency_hz: int = REFERENCE_JTAG_FREQUENCY_HZ,
    authorized_runtime_sec: int = MAX_AUTHORIZED_RUNTIME_SECONDS,
    preflight_timeout_sec: int | None = None,
    shutdown_timeout_sec: int | None = None,
    configured_stage_timeout_sec: int | None = None,
) -> dict[str, Any]:
    """Conservative planning estimate; hard process/Tcl deadlines remain authoritative."""
    if not 1 <= operation_count <= MAX_TRANSACTION_OPERATIONS:
        raise ValueError(f"operation count must be in 1..{MAX_TRANSACTION_OPERATIONS}")
    if not 100_000 <= jtag_frequency_hz <= 5_000_000:
        raise ValueError("JTAG frequency must be in 100000..5000000 Hz")
    if not 1 <= authorized_runtime_sec <= MAX_AUTHORIZED_RUNTIME_SECONDS:
        raise ValueError(f"authorized runtime must be in 1..{MAX_AUTHORIZED_RUNTIME_SECONDS}")
    frequency_scale = max(1.0, REFERENCE_JTAG_FREQUENCY_HZ / jtag_frequency_hz)
    estimated_seconds = ESTIMATED_STAGE_FIXED_OVERHEAD_SECONDS + (
        operation_count * ESTIMATED_AXI_OPERATION_US_AT_1MHZ * frequency_scale / 1_000_000.0
    )
    minimum_runtime = math.ceil(estimated_seconds)
    result: dict[str, Any] = {
        "jtag_frequency_hz": jtag_frequency_hz,
        "reference_jtag_frequency_hz": REFERENCE_JTAG_FREQUENCY_HZ,
        "estimated_axi_operation_us_at_1mhz": ESTIMATED_AXI_OPERATION_US_AT_1MHZ,
        "estimated_stage_fixed_overhead_seconds": ESTIMATED_STAGE_FIXED_OVERHEAD_SECONDS,
        "estimate_model": "one_axi_read_per_poll_operation_global_deadline_authoritative",
        "estimated_stage_runtime_seconds": round(estimated_seconds, 6),
        "minimum_stage_runtime_sec": minimum_runtime,
        "authorized_runtime_sec": authorized_runtime_sec,
        "feasible_within_authorized_runtime": minimum_runtime <= authorized_runtime_sec,
        "containment_initial_empty_wait_seconds": CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS,
        "expected_tool_daemon_grace_seconds": EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
        "containment_total_exit_window_seconds": EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
        "containment_topology_revalidation_interval_seconds": (
            CONTAINMENT_TOPOLOGY_REVALIDATION_INTERVAL_SECONDS
        ),
        "containment_forced_cleanup_wait_seconds": CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS,
        "containment_failure_bound_seconds": CONTAINMENT_FAILURE_BOUND_SECONDS,
        "jtag_wrapper_vivado_process_count": JTAG_WRAPPER_VIVADO_PROCESS_COUNT,
        "jtag_wrapper_containment_allowance_seconds": JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS,
        "jtag_wrapper_max_forced_cleanup_events": JTAG_WRAPPER_MAX_FORCED_CLEANUP_EVENTS,
        "jtag_wrapper_forced_cleanup_reserve_seconds": (
            JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS
        ),
        "jtag_wrapper_other_guard_seconds": JTAG_WRAPPER_OTHER_GUARD_SECONDS,
        "jtag_wrapper_bookkeeping_guard_seconds": JTAG_WRAPPER_BOOKKEEPING_GUARD_SECONDS,
        "jtag_wrapper_other_guard_after_forced_cleanup_seconds": (
            JTAG_WRAPPER_OTHER_GUARD_SECONDS
            - JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS
        ),
    }
    wrapper_values = (
        preflight_timeout_sec,
        shutdown_timeout_sec,
        configured_stage_timeout_sec,
    )
    if any(value is not None for value in wrapper_values):
        if any(value is None for value in wrapper_values):
            raise ValueError(
                "preflight, shutdown, and configured stage timeouts must be provided together"
            )
        assert preflight_timeout_sec is not None
        assert shutdown_timeout_sec is not None
        assert configured_stage_timeout_sec is not None
        if preflight_timeout_sec < 1 or shutdown_timeout_sec < 1 or configured_stage_timeout_sec < 1:
            raise ValueError("wrapper phase timeouts must be positive")
        minimum_global = (
            preflight_timeout_sec
            + 2 * shutdown_timeout_sec
            + minimum_runtime
            + JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS
            + JTAG_WRAPPER_OTHER_GUARD_SECONDS
        )
        configured_global = (
            preflight_timeout_sec
            + 2 * shutdown_timeout_sec
            + configured_stage_timeout_sec
            + JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS
            + JTAG_WRAPPER_OTHER_GUARD_SECONDS
        )
        global_budget = {
            "minimum_estimated_global_runtime_sec": minimum_global,
            "configured_global_timeout_ceiling_sec": configured_global,
            "authorized_global_runtime_sec": authorized_runtime_sec,
            "containment_initial_empty_wait_seconds": CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS,
            "expected_tool_daemon_grace_seconds": EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
            "containment_total_exit_window_seconds": EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
            "containment_topology_revalidation_interval_seconds": (
                CONTAINMENT_TOPOLOGY_REVALIDATION_INTERVAL_SECONDS
            ),
            "containment_success_bound_seconds_each": EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
            "containment_failure_bound_seconds_each": CONTAINMENT_FAILURE_BOUND_SECONDS,
            "contained_vivado_process_count": JTAG_WRAPPER_VIVADO_PROCESS_COUNT,
            "containment_allowance_seconds": JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS,
            "max_forced_cleanup_events": JTAG_WRAPPER_MAX_FORCED_CLEANUP_EVENTS,
            "forced_cleanup_wait_seconds": CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS,
            "forced_cleanup_reserve_seconds": JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS,
            "other_guard_seconds": JTAG_WRAPPER_OTHER_GUARD_SECONDS,
            "bookkeeping_guard_seconds": JTAG_WRAPPER_BOOKKEEPING_GUARD_SECONDS,
            "other_guard_after_forced_cleanup_seconds": (
                JTAG_WRAPPER_OTHER_GUARD_SECONDS
                - JTAG_WRAPPER_FORCED_CLEANUP_RESERVE_SECONDS
            ),
            "configured_unallocated_margin_seconds": authorized_runtime_sec - configured_global,
            "estimated_unallocated_margin_seconds": authorized_runtime_sec - minimum_global,
            "minimum_stage_fits_configured_timeout": minimum_runtime
            <= configured_stage_timeout_sec,
            "feasible": minimum_runtime <= configured_stage_timeout_sec
            and minimum_global <= authorized_runtime_sec
            and configured_global <= authorized_runtime_sec,
        }
        result["global_runtime_budget"] = global_budget
        result["feasible_within_authorized_runtime"] = bool(global_budget["feasible"])
    return result


class BackendValidationError(RuntimeError):
    """A generated bundle or raw result violated the strict backend contract."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> None:
    raise BackendValidationError(code, message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _word(data: bytes, word_index: int) -> int:
    value = 0
    for byte_lane in range(4):
        offset = word_index * 4 + byte_lane
        if offset < len(data):
            value |= data[offset] << (8 * byte_lane)
    return value


def _bytes_from_words(words: Iterable[int], length: int) -> bytes:
    output = bytearray(length)
    for word_index, word in enumerate(words):
        for byte_lane in range(4):
            offset = word_index * 4 + byte_lane
            if offset < length:
                output[offset] = (word >> (8 * byte_lane)) & 0xFF
    return bytes(output)


def _header_dict(fragment: AppFragment) -> dict[str, int]:
    return asdict(fragment.header)


def parse_lane_policy(value: str | LanePolicy) -> LanePolicy:
    if isinstance(value, LanePolicy):
        return value
    normalized = value.strip().upper().replace("-", "_")
    aliases = {
        "LANE0": LanePolicy.LANE0_ONLY,
        "LANE0_ONLY": LanePolicy.LANE0_ONLY,
        "LANE1": LanePolicy.LANE1_ONLY,
        "LANE1_ONLY": LanePolicy.LANE1_ONLY,
        "STRIPE": LanePolicy.STRIPE_ROUND_ROBIN,
        "STRIPE_ROUND_ROBIN": LanePolicy.STRIPE_ROUND_ROBIN,
        "REPLICATE": LanePolicy.REPLICATE_0X3,
        "REPLICATE_0X3": LanePolicy.REPLICATE_0X3,
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise ValueError(f"unsupported lane policy: {value}") from error


def lane_for_fragment(policy: LanePolicy, fragment_index: int) -> int:
    if policy == LanePolicy.LANE0_ONLY:
        return 0x1
    if policy == LanePolicy.LANE1_ONLY:
        return 0x2
    if policy == LanePolicy.STRIPE_ROUND_ROBIN:
        return 0x1 if fragment_index % 2 == 0 else 0x2
    if policy == LanePolicy.REPLICATE_0X3:
        return 0x3
    raise ValueError(f"unsupported lane policy: {policy}")


def _address(base_address: int, offset: int) -> str:
    return f"0x{base_address + offset:08x}"


def _read_counter_lines(lines: Any, prefix: str, base_address: int) -> None:
    for name, offset in COUNTER_OFFSETS.items():
        lines.append(f"R32 {_address(base_address, offset)} {prefix}_{name}")
    lines.append(
        f"R32 {_address(base_address, regs.IR_REG_P6_TXD_HIGH_CONSECUTIVE_MAX)} "
        f"{prefix}_TXD_HIGH_MAX"
    )
    lines.append(f"R32 {_address(base_address, regs.IR_REG_P6_ERROR_CODE)} {prefix}_ERROR_CODE")
    lines.append(f"R32 {_address(base_address, regs.IR_REG_P6_STICKY_ERROR)} {prefix}_STICKY_ERROR")


class _AtomicLineSink:
    """List-like UTF-8 line sink that fsyncs then atomically replaces its target."""

    def __init__(self, path: Path, *, max_bytes: int = MAX_TRANSACTION_BYTES) -> None:
        self.path = path
        self.max_bytes = max_bytes
        self._temp_name = ""
        self._handle: Any = None
        self._digest = hashlib.sha256()
        self._bytes_written = 0
        self._operation_count = 0

    def __enter__(self) -> "_AtomicLineSink":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, self._temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".partial", dir=self.path.parent
        )
        self._handle = os.fdopen(descriptor, "wb")
        return self

    def append(self, line: str) -> None:
        encoded = (line + "\n").encode("utf-8")
        if len(encoded) > MAX_TRANSACTION_LINE_BYTES:
            raise ValueError(f"generated line exceeds {MAX_TRANSACTION_LINE_BYTES} bytes")
        if self._bytes_written + len(encoded) > self.max_bytes:
            raise ValueError(f"generated file exceeds {self.max_bytes} bytes")
        self._handle.write(encoded)
        self._digest.update(encoded)
        self._bytes_written += len(encoded)
        if line.startswith(("W32 ", "R32 ", "POLL32 ", "ASSERT32 ")):
            self._operation_count += 1
            if self._operation_count > MAX_TRANSACTION_OPERATIONS:
                raise ValueError(
                    f"generated operation count exceeds {MAX_TRANSACTION_OPERATIONS}"
                )

    def extend(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.append(line)

    @property
    def sha256(self) -> str:
        return self._digest.hexdigest()

    @property
    def bytes_written(self) -> int:
        return self._bytes_written

    @property
    def operation_count(self) -> int:
        return self._operation_count

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        try:
            if self._handle is not None:
                if exc_type is None:
                    self._handle.flush()
                    os.fsync(self._handle.fileno())
                self._handle.close()
                self._handle = None
            if exc_type is None:
                os.replace(self._temp_name, self.path)
            elif self._temp_name:
                try:
                    os.unlink(self._temp_name)
                except FileNotFoundError:
                    pass
        except BaseException:
            if self._handle is not None:
                self._handle.close()
                self._handle = None
            if self._temp_name:
                try:
                    os.unlink(self._temp_name)
                except FileNotFoundError:
                    pass
            raise
        return False


def build_transaction_lines(
    fragments: list[AppFragment],
    *,
    policy: LanePolicy,
    base_address: int,
    p6_session: int,
    timeout_cycles: int,
    commit_polls: int,
    transfer_polls: int,
    poll_period_us: int = DEFAULT_POLL_PERIOD_US,
    line_sink: _AtomicLineSink | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    if base_address != DEFAULT_BASE_ADDRESS:
        raise ValueError(f"base address must be exactly 0x{DEFAULT_BASE_ADDRESS:08x}")
    if p6_session < 0 or p6_session > 0xFFFF:
        raise ValueError("P6 session must fit uint16")
    if timeout_cycles <= 0 or timeout_cycles > 0xFFFFFFFF:
        raise ValueError("timeout cycles must be in 1..0xffffffff")
    if not 1 <= commit_polls <= 10_000 or not 1 <= transfer_polls <= 10_000:
        raise ValueError("poll bounds must be in 1..10000")
    if poll_period_us < 0 or poll_period_us % 1000 != 0 or poll_period_us > 100_000:
        raise ValueError("poll period must be a multiple of 1000 us in 0..100000")
    poll_delay_ms = poll_period_us // 1000

    tx_window = regs.IR_REG_P6_PAYLOAD_WINDOW_BASE
    rx_window = regs.IR_REG_P6_RX_WINDOW_BASE
    lines: Any = [] if line_sink is None else line_sink
    lines.extend([
        "# P7 RFAP direct JTAG/AXI transaction file.",
        "# DRY-RUN ARTIFACT: execute only through an external authorized shutdown-bounded wrapper.",
        "# The wrapper owns programming, authorization, maximum runtime, and TFDU shutdown-on-exit.",
        TRANSACTION_MAGIC,
        "META BACKEND p7_jtag_backend",
        f"META LANE_POLICY {policy.name}",
        f"W32 {_address(base_address, regs.IR_REG_P6_CTRL)} 0x{P6_CTRL_CLEAR_STICKY:08x}",
    ])
    _read_counter_lines(lines, "P7_BASE", base_address)
    plans: list[dict[str, Any]] = []
    for fragment in fragments:
        encoded = fragment.encode()
        index = fragment.header.fragment_index
        lane_mask = lane_for_fragment(policy, index)
        prefix = f"P7F{index:05d}"
        word_count = (len(encoded) + 3) // 4
        lines.extend(
            [
                f"# P7_FRAGMENT index={index} lane_mask=0x{lane_mask:x} bytes={len(encoded)}",
                f"W32 {_address(base_address, regs.IR_REG_P6_CTRL)} 0x{P6_CTRL_CLEAR_STICKY:08x}",
            ]
        )
        for word_index in range(word_count):
            lines.append(
                f"W32 {_address(base_address, tx_window + 4 * word_index)} "
                f"0x{_word(encoded, word_index):08x}"
            )
        for word_index in range(word_count):
            lines.append(
                f"R32 {_address(base_address, tx_window + 4 * word_index)} "
                f"{prefix}_TXW{word_index:03d}"
            )
        lines.extend(
            [
                f"W32 {_address(base_address, regs.IR_REG_P6_SESSION)} 0x{p6_session:08x}",
                f"W32 {_address(base_address, regs.IR_REG_P6_LANE_MASK)} 0x{lane_mask:08x}",
                f"W32 {_address(base_address, regs.IR_REG_P6_ACK_LANE_MASK)} 0x{lane_mask:08x}",
                f"W32 {_address(base_address, regs.IR_REG_P6_PAYLOAD_LEN)} 0x{len(encoded):08x}",
                f"W32 {_address(base_address, regs.IR_REG_P6_TIMEOUT_CYCLES)} 0x{timeout_cycles:08x}",
                f"W32 {_address(base_address, regs.IR_REG_P6_CTRL)} 0x{P6_CTRL_COMMIT:08x}",
                f"POLL32 {_address(base_address, regs.IR_REG_P6_STATUS)} 0x00000004 "
                f"0x00000004 {commit_polls} {poll_delay_ms} {prefix}_COMMIT",
                f"R32 {_address(base_address, regs.IR_REG_P6_PAYLOAD_CRC32)} {prefix}_TX_CRC32",
                f"W32 {_address(base_address, regs.IR_REG_P6_CTRL)} 0x{P6_CTRL_START:08x}",
                f"POLL32 {_address(base_address, regs.IR_REG_P6_STATUS)} 0x00000010 "
                f"0x00000010 {transfer_polls} {poll_delay_ms} {prefix}_DONE",
                f"R32 {_address(base_address, regs.IR_REG_P6_STATUS)} {prefix}_STATUS",
                f"R32 {_address(base_address, regs.IR_REG_P6_MAILBOX_STATUS)} {prefix}_MAILBOX",
                f"R32 {_address(base_address, regs.IR_REG_P6_RX_PAYLOAD_LEN)} {prefix}_RX_LEN",
                f"R32 {_address(base_address, regs.IR_REG_P6_RX_PAYLOAD_CRC32)} {prefix}_RX_CRC32",
                f"R32 {_address(base_address, regs.IR_REG_P6_RX_DIGEST)} {prefix}_RX_DIGEST",
            ]
        )
        _read_counter_lines(lines, prefix, base_address)
        for word_index in range(word_count):
            lines.append(
                f"R32 {_address(base_address, rx_window + 4 * word_index)} "
                f"{prefix}_RXW{word_index:03d}"
            )
        plans.append(
            {
                "fragment_index": index,
                "lane_mask": lane_mask,
                "encoded_length": len(encoded),
                "word_count": word_count,
                "p6_payload_crc32": crc32(encoded),
                "p6_payload_sha256": _sha256(encoded),
                "header": _header_dict(fragment),
            }
        )
    lines.extend(
        [
            f"W32 {_address(base_address, regs.IR_REG_P6_CTRL)} "
            f"0x{P6_CTRL_STOP | P6_CTRL_SHUTDOWN:08x}",
            f"R32 {_address(base_address, regs.IR_REG_P6_SHUTDOWN_REASON)} P7_FINAL_SHUTDOWN_REASON",
            f"W32 {_address(base_address, regs.IR_REG_P6_CTRL)} "
            f"0x{P6_CTRL_STOP | P6_CTRL_SHUTDOWN:08x}",
            "END",
        ]
    )
    return (lines if isinstance(lines, list) else []), plans


def _relative_to(path: Path, parent: Path) -> str:
    return Path(os.path.relpath(path.resolve(), parent.resolve())).as_posix()


def generate_bundle(
    data: bytes,
    *,
    transaction_path: Path,
    manifest_path: Path,
    session_epoch: int,
    object_id: int,
    lane_policy: str | LanePolicy,
    base_address: int = DEFAULT_BASE_ADDRESS,
    p6_session: int = DEFAULT_P6_SESSION,
    timeout_cycles: int = DEFAULT_TIMEOUT_CYCLES,
    commit_polls: int = DEFAULT_COMMIT_POLLS,
    transfer_polls: int = DEFAULT_TRANSFER_POLLS,
    poll_period_us: int = DEFAULT_POLL_PERIOD_US,
    txd_high_limit_cycles: int = DEFAULT_TXD_HIGH_LIMIT_CYCLES,
    jtag_frequency_hz: int = REFERENCE_JTAG_FREQUENCY_HZ,
    authorized_runtime_sec: int = MAX_AUTHORIZED_RUNTIME_SECONDS,
) -> dict[str, Any]:
    """Generate a dry-run manifest and one continuous transaction file."""
    if poll_period_us < 0 or poll_period_us % 1000 != 0 or poll_period_us > 100_000:
        raise ValueError("poll period must be a multiple of 1000 us in 0..100000")
    if txd_high_limit_cycles <= 0:
        raise ValueError("TXD high limit cycles must be positive")
    policy = parse_lane_policy(lane_policy)
    shape = transaction_shape(len(data))
    if shape["operation_count"] > MAX_TRANSACTION_OPERATIONS:
        raise ValueError(
            f"object requires {shape['operation_count']} operations; limit is "
            f"{MAX_TRANSACTION_OPERATIONS}"
        )
    feasibility = runtime_feasibility(
        shape["operation_count"],
        jtag_frequency_hz=jtag_frequency_hz,
        authorized_runtime_sec=authorized_runtime_sec,
    )
    poll_delay_ms = poll_period_us // 1000
    poll_bounds = {
        "poll_operation_count": 2 * shape["fragment_count"],
        "poll_iteration_ceiling": shape["fragment_count"] * (
            commit_polls + transfer_polls
        ),
        "poll_delay_ms": poll_delay_ms,
        "poll_worst_case_delay_seconds": round(
            shape["fragment_count"]
            * ((commit_polls - 1) + (transfer_polls - 1))
            * poll_delay_ms
            / 1000.0,
            6,
        ),
        "hard_stop": "per_poll_bounds_plus_host_and_tcl_global_deadlines",
    }
    fragments = segment_object(data, session_epoch=session_epoch, object_id=object_id)
    with _AtomicLineSink(transaction_path) as transaction_sink:
        _, plans = build_transaction_lines(
            fragments,
            policy=policy,
            base_address=base_address,
            p6_session=p6_session,
            timeout_cycles=timeout_cycles,
            commit_polls=commit_polls,
            transfer_polls=transfer_polls,
            poll_period_us=poll_period_us,
            line_sink=transaction_sink,
        )
    transaction_sha256 = transaction_sink.sha256
    transaction_file_bytes = transaction_sink.bytes_written
    transaction_operation_count = transaction_sink.operation_count
    if transaction_operation_count != shape["operation_count"]:
        raise RuntimeError(
            f"generated operation count {transaction_operation_count} differs from formula "
            f"{shape['operation_count']}"
        )
    manifest = {
        "schema": SCHEMA,
        "kind": "P7_JTAG_AXI_DRY_RUN_MANIFEST",
        "NO_HARDWARE": 1,
        "dry_run_only": True,
        "direct_hardware_execution_supported": False,
        "external_safe_wrapper_required": True,
        "single_program_continuous_transactions": True,
        "authorization_environment_modified": False,
        "vivado_invoked": False,
        "network_used": False,
        "hardware_actions_executed_by_module": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "base_address": base_address,
        "p6_session": p6_session,
        "timeout_cycles": timeout_cycles,
        "commit_poll_limit": commit_polls,
        "transfer_poll_limit": transfer_polls,
        "poll_period_us": poll_period_us,
        "txd_high_limit_cycles": txd_high_limit_cycles,
        "lane_policy": policy.name,
        "allowed_lane_masks": [1, 2, 3],
        "lane1_reliability_boundary": "PENDING_FRESH_RAW_CRC_ACK_SESSION_MASK_GATES",
        "input_length": len(data),
        "input_crc32": crc32(data),
        "input_sha256": _sha256(data),
        "session_epoch": session_epoch,
        "object_id": object_id,
        "fragment_count": len(fragments),
        "transaction_shape": shape,
        "transaction_operation_count": transaction_operation_count,
        "transaction_file_bytes": transaction_file_bytes,
        "transaction_limits": {
            "max_operations": MAX_TRANSACTION_OPERATIONS,
            "max_file_bytes": MAX_TRANSACTION_BYTES,
            "max_line_bytes": MAX_TRANSACTION_LINE_BYTES,
        },
        "runtime_feasibility": feasibility,
        "transaction_poll_bounds": poll_bounds,
        "fragments": plans,
        "transaction_file": _relative_to(transaction_path, manifest_path.parent),
        "transaction_sha256": transaction_sha256,
        "external_wrapper_contract": {
            "authorization_required": True,
            "artifact_hash_inputs_required": True,
            "maximum_runtime_required": True,
            "program_once_before_transaction_file": True,
            "startup_wait_us_min": 500,
            "shutdown_on_every_exit_required": True,
            "required_shutdown_evidence": ["SHUTDOWN_EXIT=0", "TFDU_SHUTDOWN_PROGRAMMED"],
            "no_ethernet": True,
            "no_motion": True,
        },
    }
    atomic_commit(
        manifest_path,
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )
    return manifest


def _parse_value(key: str, value: str) -> int | str:
    text = value.strip()
    if text.lower().startswith("0x"):
        try:
            return int(text, 16)
        except ValueError:
            return text
    if re.fullmatch(r"[0-9A-Fa-f]{8}", text):
        return int(text, 16)
    if key.endswith("_POLLS") or key == "P6_JTAG_AXI_TRANSACTION_COUNT":
        try:
            return int(text, 10)
        except ValueError:
            return text
    if re.fullmatch(r"[0-9]+", text):
        return int(text, 10)
    return text


def parse_unique_raw_log(path: Path) -> dict[str, int | str]:
    if not path.is_file():
        _fail("RAW_LOG_MISSING", str(path))
    size = path.stat().st_size
    if not 1 <= size <= MAX_RAW_LOG_BYTES:
        _fail("RAW_LOG_SIZE", f"raw log bytes {size} outside 1..{MAX_RAW_LOG_BYTES}")
    values: dict[str, int | str] = {}
    line_number = 0
    with path.open("rb") as handle:
        while True:
            raw_line = handle.readline(MAX_TRANSACTION_LINE_BYTES + 1)
            if not raw_line:
                break
            line_number += 1
            if len(raw_line) > MAX_TRANSACTION_LINE_BYTES:
                _fail("RAW_LOG_LINE_SIZE", f"raw log line {line_number} is too long")
            try:
                line = raw_line.decode("ascii", errors="strict").strip()
            except UnicodeDecodeError as error:
                _fail("RAW_LOG_ASCII", f"line {line_number}: {error}")
            if "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            key = key.strip()
            if not key:
                _fail("EMPTY_KEY", f"raw log line {line_number} has an empty key")
            if len(key) > 96 or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
                _fail("RAW_LOG_KEY", f"raw log line {line_number} has invalid key {key!r}")
            if key in values:
                _fail("DUPLICATE_KEY", f"raw log key {key} appears more than once")
            values[key] = _parse_value(key, raw_value)
            if len(values) > MAX_TRANSACTION_OPERATIONS * 2 + 128:
                _fail("RAW_LOG_ENTRY_LIMIT", "raw log entry limit exceeded")
    return values


def _require_int(values: dict[str, int | str], key: str) -> int:
    if key not in values:
        _fail("MISSING_KEY", f"raw log is missing {key}")
    value = values[key]
    if not isinstance(value, int):
        _fail("NON_NUMERIC_VALUE", f"raw log {key} is not numeric: {value!r}")
    if value < 0 or value > 0xFFFFFFFF:
        _fail("FIELD_RANGE", f"raw log {key} is outside uint32")
    return value


def _require_marker(values: dict[str, int | str], key: str, expected: str) -> None:
    if values.get(key) != expected:
        _fail("MISSING_PASS_MARKER", f"{key} must be {expected!r}, got {values.get(key)!r}")


def _delta32(current: int, previous: int) -> int:
    return (current - previous) & 0xFFFFFFFF


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        _fail("MANIFEST_READ", str(error))
    if not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA:
        _fail("MANIFEST_SCHEMA", f"expected schema {SCHEMA}")
    if manifest.get("dry_run_only") is not True:
        _fail("MANIFEST_SAFETY", "manifest must remain dry_run_only=true")
    if manifest.get("NO_HARDWARE") != 1 or manifest.get("external_safe_wrapper_required") is not True:
        _fail("MANIFEST_SAFETY", "manifest must require offline/external-wrapper execution")
    if manifest.get("direct_hardware_execution_supported") is not False:
        _fail("MANIFEST_SAFETY", "direct execution must remain disabled")
    if manifest.get("hardware_actions_executed_by_module") is not False:
        _fail("MANIFEST_SAFETY", "generator cannot claim hardware actions")
    if (
        manifest.get("authorization_environment_modified") is not False
        or manifest.get("vivado_invoked") is not False
        or manifest.get("network_used") is not False
    ):
        _fail("MANIFEST_SAFETY", "manifest violates the offline generator boundary")
    fragments = manifest.get("fragments")
    if (
        not isinstance(fragments, list)
        or not fragments
        or len(fragments) != manifest.get("fragment_count")
    ):
        _fail("MANIFEST_FRAGMENT_COUNT", "fragment list/count mismatch")
    scalar_ranges = {
        "input_length": (0, 8 * 1024 * 1024),
        "input_crc32": (0, 0xFFFFFFFF),
        "session_epoch": (0, 0xFFFFFFFF),
        "object_id": (0, 0xFFFFFFFF),
        "base_address": (0, 0xFFFFFFFF),
        "p6_session": (0, 0xFFFF),
        "timeout_cycles": (1, 0xFFFFFFFF),
        "commit_poll_limit": (1, 10_000),
        "transfer_poll_limit": (1, 10_000),
        "poll_period_us": (0, 100_000),
        "txd_high_limit_cycles": (1, 0x7FFFFFFF),
        "transaction_operation_count": (1, MAX_TRANSACTION_OPERATIONS),
        "transaction_file_bytes": (1, MAX_TRANSACTION_BYTES),
    }
    for key, (minimum, maximum) in scalar_ranges.items():
        value = manifest.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            _fail("MANIFEST_FIELD", f"{key} must be an integer in {minimum}..{maximum}")
    if not isinstance(manifest.get("input_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", manifest["input_sha256"]
    ):
        _fail("MANIFEST_FIELD", "input_sha256 must be lowercase SHA256 hex")
    if manifest["base_address"] != DEFAULT_BASE_ADDRESS:
        _fail("MANIFEST_FIELD", "base_address must be the canonical P6 AXI base")
    if manifest["poll_period_us"] % 1000 != 0:
        _fail("MANIFEST_FIELD", "poll_period_us must be a multiple of 1000")
    expected_limits = {
        "max_operations": MAX_TRANSACTION_OPERATIONS,
        "max_file_bytes": MAX_TRANSACTION_BYTES,
        "max_line_bytes": MAX_TRANSACTION_LINE_BYTES,
    }
    if manifest.get("transaction_limits") != expected_limits:
        _fail("MANIFEST_LIMITS", "transaction limits differ from the bounded implementation")
    shape = transaction_shape(manifest["input_length"])
    poll_delay_ms = manifest["poll_period_us"] // 1000
    expected_poll_bounds = {
        "poll_operation_count": 2 * shape["fragment_count"],
        "poll_iteration_ceiling": shape["fragment_count"]
        * (manifest["commit_poll_limit"] + manifest["transfer_poll_limit"]),
        "poll_delay_ms": poll_delay_ms,
        "poll_worst_case_delay_seconds": round(
            shape["fragment_count"]
            * (
                (manifest["commit_poll_limit"] - 1)
                + (manifest["transfer_poll_limit"] - 1)
            )
            * poll_delay_ms
            / 1000.0,
            6,
        ),
        "hard_stop": "per_poll_bounds_plus_host_and_tcl_global_deadlines",
    }
    if manifest.get("transaction_poll_bounds") != expected_poll_bounds:
        _fail("MANIFEST_POLL_BOUNDS", "transaction poll bounds differ from exact formula")
    if manifest.get("transaction_shape") != shape:
        _fail("MANIFEST_OPERATION_COUNT", "transaction shape differs from exact formula")
    if manifest["transaction_operation_count"] != shape["operation_count"]:
        _fail("MANIFEST_OPERATION_COUNT", "transaction operation count differs from formula")
    feasibility = manifest.get("runtime_feasibility")
    if not isinstance(feasibility, dict):
        _fail("MANIFEST_RUNTIME", "runtime feasibility record is missing")
    try:
        recalculated_feasibility = runtime_feasibility(
            shape["operation_count"],
            jtag_frequency_hz=int(feasibility["jtag_frequency_hz"]),
            authorized_runtime_sec=int(feasibility["authorized_runtime_sec"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        _fail("MANIFEST_RUNTIME", str(error))
    if feasibility != recalculated_feasibility:
        _fail("MANIFEST_RUNTIME", "runtime feasibility record differs from formula")
    indexes = [item.get("fragment_index") for item in fragments if isinstance(item, dict)]
    if indexes != list(range(len(fragments))):
        _fail("MANIFEST_FRAGMENT_ORDER", "fragments must be unique and strictly ordered")
    try:
        policy = parse_lane_policy(str(manifest["lane_policy"]))
    except (KeyError, ValueError) as error:
        _fail("MANIFEST_LANE_POLICY", str(error))
    for index, fragment in enumerate(fragments):
        if not isinstance(fragment, dict):
            _fail("MANIFEST_FRAGMENT", f"fragment {index} is not a mapping")
        if fragment.get("lane_mask") != lane_for_fragment(policy, index):
            _fail("MANIFEST_LANE_POLICY", f"fragment {index} lane mask violates policy")
        length = fragment.get("encoded_length")
        if not isinstance(length, int) or not 1 <= length <= P6_MAX_PAYLOAD_BYTES:
            _fail("MANIFEST_PAYLOAD_LENGTH", f"fragment {index} P6 length is invalid")
        if fragment.get("word_count") != (length + 3) // 4:
            _fail("MANIFEST_WORD_COUNT", f"fragment {index} word count is invalid")
        payload_crc = fragment.get("p6_payload_crc32")
        payload_sha = fragment.get("p6_payload_sha256")
        if not isinstance(payload_crc, int) or isinstance(payload_crc, bool) or not 0 <= payload_crc <= 0xFFFFFFFF:
            _fail("MANIFEST_FRAGMENT", f"fragment {index} payload CRC32 is invalid")
        if not isinstance(payload_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", payload_sha):
            _fail("MANIFEST_FRAGMENT", f"fragment {index} payload SHA256 is invalid")
        header_fields = fragment.get("header")
        if not isinstance(header_fields, dict):
            _fail("MANIFEST_FRAGMENT", f"fragment {index} header is missing")
        try:
            header = AppHeader(**header_fields)
            header.validate()
        except (ProtocolError, TypeError) as error:
            _fail("MANIFEST_RFAP_HEADER", f"fragment {index}: {error}")
        if (
            header.fragment_index != index
            or header.fragment_count != len(fragments)
            or header.total_length != manifest["input_length"]
            or header.object_crc32 != manifest["input_crc32"]
            or header.session_epoch != manifest["session_epoch"]
            or header.object_id != manifest["object_id"]
            or length != 32 + header.chunk_length
        ):
            _fail("MANIFEST_RFAP_HEADER", f"fragment {index} header/object metadata mismatch")
    transaction = (manifest_path.parent / str(manifest.get("transaction_file", ""))).resolve()
    if not transaction.is_file():
        _fail("TRANSACTION_FILE_MISSING", str(transaction))
    if transaction.stat().st_size != manifest["transaction_file_bytes"]:
        _fail("TRANSACTION_SIZE", "transaction file byte count differs from manifest")
    if _sha256_file(transaction) != manifest.get("transaction_sha256"):
        _fail("TRANSACTION_HASH", "transaction file SHA256 differs from manifest")
    return manifest


def validate_manifest_bundle(
    manifest_path: Path,
    *,
    expected_transaction_path: Path | None = None,
    expected_transaction_sha256: str | None = None,
    expected_jtag_frequency_hz: int | None = None,
    expected_authorized_runtime_sec: int | None = None,
) -> dict[str, Any]:
    """Public pre-hardware validator for a generated manifest/DSL bundle."""

    manifest_path = manifest_path.resolve()
    manifest = _load_manifest(manifest_path)
    transaction = (manifest_path.parent / str(manifest["transaction_file"])).resolve()
    if expected_transaction_path is not None and transaction != expected_transaction_path.resolve():
        _fail("TRANSACTION_PATH", "manifest transaction path differs from the authorized path")
    if (
        expected_transaction_sha256 is not None
        and str(manifest.get("transaction_sha256", "")).lower()
        != expected_transaction_sha256.lower()
    ):
        _fail("TRANSACTION_HASH", "manifest transaction SHA256 differs from authorization")
    feasibility = manifest["runtime_feasibility"]
    if (
        expected_jtag_frequency_hz is not None
        and int(feasibility["jtag_frequency_hz"]) != expected_jtag_frequency_hz
    ):
        _fail("MANIFEST_RUNTIME", "manifest JTAG frequency differs from execution control")
    if (
        expected_authorized_runtime_sec is not None
        and int(feasibility["authorized_runtime_sec"])
        != expected_authorized_runtime_sec
    ):
        _fail("MANIFEST_RUNTIME", "manifest authorized runtime differs from execution control")
    return manifest


def _expected_fragment_raw_keys(manifest: dict[str, Any]) -> set[str]:
    expected: set[str] = set()
    for plan in manifest["fragments"]:
        prefix = f"P7F{int(plan['fragment_index']):05d}"
        expected.update(
            {
                f"{prefix}_COMMIT",
                f"{prefix}_COMMIT_POLLS",
                f"{prefix}_DONE",
                f"{prefix}_DONE_POLLS",
                f"{prefix}_STATUS",
                f"{prefix}_MAILBOX",
                f"{prefix}_RX_LEN",
                f"{prefix}_RX_CRC32",
                f"{prefix}_RX_DIGEST",
                f"{prefix}_TX_CRC32",
                f"{prefix}_TXD_HIGH_MAX",
                f"{prefix}_ERROR_CODE",
                f"{prefix}_STICKY_ERROR",
            }
        )
        expected.update(f"{prefix}_{name}" for name in COUNTER_OFFSETS)
        expected.update(
            f"{prefix}_{direction}W{word:03d}"
            for direction in ("TX", "RX")
            for word in range(int(plan["word_count"]))
        )
    return expected


def parse_raw_result(
    *,
    manifest_path: Path,
    raw_log_path: Path,
    output_path: Path,
    summary_path: Path | None = None,
) -> dict[str, Any]:
    """Strictly validate a raw executor log, then atomically publish the object."""
    manifest = _load_manifest(manifest_path)
    values = parse_unique_raw_log(raw_log_path)
    expected_fragment_keys = _expected_fragment_raw_keys(manifest)
    unexpected_fragment_keys = sorted(
        key for key in values if key.startswith("P7F") and key not in expected_fragment_keys
    )
    if unexpected_fragment_keys:
        _fail(
            "UNEXPECTED_FRAGMENT_RECORD",
            f"raw log contains unexpected fragment keys: {unexpected_fragment_keys[:4]}",
        )
    _require_marker(values, "P7_JTAG_AXI_TRANSACTIONS", "PASS")
    if _require_int(values, "P7_TRANSACTION_COUNT") != manifest["transaction_operation_count"]:
        _fail("TRANSACTION_COUNT", "raw transaction count differs from manifest")
    if _require_int(values, "P7_FINAL_SHUTDOWN_REASON") != P6_SHUTDOWN_REASON_TFDU:
        _fail("TRANSACTION_SHUTDOWN", "P6 shutdown control did not latch the TFDU reason")

    previous = {name: _require_int(values, f"P7_BASE_{name}") for name in COUNTER_OFFSETS}
    baseline_high = _require_int(values, "P7_BASE_TXD_HIGH_MAX")
    high_limit = int(manifest["txd_high_limit_cycles"])
    if baseline_high > high_limit:
        _fail("TXD_HIGH_LIMIT", f"baseline TXD high max {baseline_high} exceeds {high_limit}")
    if _require_int(values, "P7_BASE_ERROR_CODE") != 0:
        _fail("BASELINE_ERROR", "P6 ERROR_CODE was nonzero after clear-sticky")
    if _require_int(values, "P7_BASE_STICKY_ERROR") != 0:
        _fail("BASELINE_ERROR", "P6 STICKY_ERROR was nonzero after clear-sticky")

    reassembler = Reassembler(expected_session_epoch=int(manifest["session_epoch"]))
    fragment_records: list[dict[str, Any]] = []
    for plan in manifest["fragments"]:
        index = int(plan["fragment_index"])
        prefix = f"P7F{index:05d}"
        encoded_length = int(plan["encoded_length"])
        word_count = int(plan["word_count"])
        commit_value = _require_int(values, f"{prefix}_COMMIT")
        done_value = _require_int(values, f"{prefix}_DONE")
        commit_poll_count = _require_int(values, f"{prefix}_COMMIT_POLLS")
        done_poll_count = _require_int(values, f"{prefix}_DONE_POLLS")
        if commit_value & P6_STATUS_COMMITTED == 0:
            _fail("COMMIT_STATUS", f"fragment {index} did not commit")
        if done_value & P6_STATUS_DONE == 0:
            _fail("DONE_STATUS", f"fragment {index} did not complete")
        if not 1 <= commit_poll_count <= int(manifest["commit_poll_limit"]):
            _fail("COMMIT_POLL_COUNT", f"fragment {index} commit poll count is invalid")
        if not 1 <= done_poll_count <= int(manifest["transfer_poll_limit"]):
            _fail("DONE_POLL_COUNT", f"fragment {index} transfer poll count is invalid")

        status = _require_int(values, f"{prefix}_STATUS")
        if status & P6_STATUS_DONE == 0 or status & P6_STATUS_FAILURE_MASK:
            _fail("P6_STATUS", f"fragment {index} failed with status 0x{status:08x}")
        if _require_int(values, f"{prefix}_MAILBOX") != P6_MAILBOX_OK:
            _fail("P6_MAILBOX", f"fragment {index} mailbox is not P6 OK")
        expected_crc = int(plan["p6_payload_crc32"])
        if _require_int(values, f"{prefix}_TX_CRC32") != expected_crc:
            _fail("TX_CRC32", f"fragment {index} committed CRC differs from manifest")
        if _require_int(values, f"{prefix}_RX_LEN") != encoded_length:
            _fail("RX_LENGTH", f"fragment {index} RX length differs from manifest")
        if _require_int(values, f"{prefix}_RX_CRC32") != expected_crc:
            _fail("RX_CRC32", f"fragment {index} RX CRC differs from manifest")
        if _require_int(values, f"{prefix}_RX_DIGEST") != expected_crc:
            _fail("RX_DIGEST", f"fragment {index} RX digest differs from manifest")

        tx_words = [_require_int(values, f"{prefix}_TXW{word:03d}") for word in range(word_count)]
        rx_words = [_require_int(values, f"{prefix}_RXW{word:03d}") for word in range(word_count)]
        tx_payload = _bytes_from_words(tx_words, encoded_length)
        rx_payload = _bytes_from_words(rx_words, encoded_length)
        if crc32(tx_payload) != expected_crc or _sha256(tx_payload) != plan["p6_payload_sha256"]:
            _fail("TX_READBACK", f"fragment {index} TX window readback differs from manifest")
        if rx_payload != tx_payload:
            _fail("RX_BYTES", f"fragment {index} RX bytes differ from committed TX bytes")
        if crc32(rx_payload) != expected_crc or _sha256(rx_payload) != plan["p6_payload_sha256"]:
            _fail("RX_INTEGRITY", f"fragment {index} RX bytes fail CRC32/SHA256")
        try:
            decoded = AppFragment.decode(rx_payload)
        except ProtocolError as error:
            _fail("RFAP_DECODE", f"fragment {index}: {error.code}: {error}")
        if _header_dict(decoded) != plan["header"]:
            _fail("RFAP_HEADER", f"fragment {index} header differs from manifest")
        if decoded.header.fragment_index != index:
            _fail("FRAGMENT_INDEX", f"fragment slot {index} contains index {decoded.header.fragment_index}")
        try:
            state = reassembler.add(rx_payload)
        except ProtocolError as error:
            _fail(error.code, f"fragment {index}: {error}")
        if state not in {"ACCEPTED", "COMPLETE"}:
            _fail("DUPLICATE_FRAGMENT", f"fragment {index} produced state {state}")

        current = {name: _require_int(values, f"{prefix}_{name}") for name in COUNTER_OFFSETS}
        deltas = {name: _delta32(current[name], previous[name]) for name in COUNTER_OFFSETS}
        # The real P6 RTL routes P6_CTRL_CLEAR_STICKY into each tfdu_lane_phy
        # ``clear_sticky`` input, and the engine's clear pulse also resets
        # RETRY_COUNT.  These three values therefore restart at zero before
        # every fragment and are per-fragment observations, not cumulative
        # counters.  Keep the cumulative-delta contract for the other
        # counters and record the clear-scoped observations directly.
        for name in ("RAW_TX_PULSES", "RAW_RX_PULSES", "RETRY_COUNT"):
            deltas[name] = current[name]
        expected_l0 = 1 if int(plan["lane_mask"]) & 0x1 else 0
        expected_l1 = 1 if int(plan["lane_mask"]) & 0x2 else 0
        retry_delta = deltas["RETRY_COUNT"]
        if not 0 <= retry_delta <= P6_MAX_RETRY_PER_FRAGMENT:
            _fail(
                "RETRY_DELTA",
                f"fragment {index} RETRY_COUNT delta={retry_delta} outside 0..{P6_MAX_RETRY_PER_FRAGMENT}",
            )
        exact_deltas = {
            "TX_COUNT": 1,
            "RX_GOOD_COUNT_L0": expected_l0,
            "RX_GOOD_COUNT_L1": expected_l1,
            # Every retry re-transmits one valid frame.  The receiver counts
            # and ACKs each valid duplicate, while the sender records one
            # eventual ACK_SEEN and one completed TX_COUNT.
            "FRAME_GOOD": 1 + retry_delta,
            "ACK_SENT": 1 + retry_delta,
            "ACK_SEEN": 1,
        }
        for name, expected in exact_deltas.items():
            if deltas[name] != expected:
                _fail(
                    "COUNTER_DELTA",
                    f"fragment {index} {name} delta={deltas[name]} expected={expected}",
                )
        for name in ZERO_DELTA_COUNTERS:
            if deltas[name] != 0:
                _fail("ERROR_COUNTER", f"fragment {index} {name} increased by {deltas[name]}")
        for name in ("RAW_TX_PULSES", "RAW_RX_PULSES"):
            if current[name] == 0:
                _fail("RAW_PULSE_COUNTER", f"fragment {index} {name} is zero after the clear-scoped transfer")
        if _require_int(values, f"{prefix}_ERROR_CODE") != 0:
            _fail("P6_ERROR_CODE", f"fragment {index} ERROR_CODE is nonzero")
        if _require_int(values, f"{prefix}_STICKY_ERROR") != 0:
            _fail("P6_STICKY_ERROR", f"fragment {index} STICKY_ERROR is nonzero")
        txd_high = _require_int(values, f"{prefix}_TXD_HIGH_MAX")
        if txd_high == 0 or txd_high > high_limit:
            _fail(
                "TXD_HIGH_LIMIT",
                f"fragment {index} TXD high max {txd_high} outside 1..{high_limit}",
            )
        latency_upper_bound_us = (
            commit_poll_count + done_poll_count
        ) * int(manifest["poll_period_us"])
        fragment_records.append(
            {
                "fragment_index": index,
                "lane_mask": int(plan["lane_mask"]),
                "latency_us": latency_upper_bound_us,
                "latency_semantics": "upper_bound",
                "latency_upper_bound_us": latency_upper_bound_us,
                "latency_source": "bounded_poll_count_x_manifest_poll_period",
                "commit_polls": commit_poll_count,
                "transfer_polls": done_poll_count,
                "counters": current,
                "counter_deltas": deltas,
                "retry_count_delta": retry_delta,
                "raw_pulse_counter_semantics": "clear_scoped_per_fragment_observation",
                "txd_high_max_cycles": txd_high,
                "rx_length": encoded_length,
                "rx_crc32": expected_crc,
                "rx_sha256": _sha256(rx_payload),
                "rx_bytes_hex": rx_payload.hex(),
            }
        )
        previous = current

    if reassembler.duplicates != 0:
        _fail("DUPLICATE_FRAGMENT", f"reassembler saw {reassembler.duplicates} duplicates")
    if reassembler.missing_count != 0 or not reassembler.complete:
        _fail("MISSING_FRAGMENT", f"reassembly has {reassembler.missing_count} missing fragments")
    try:
        output = reassembler.data()
    except ProtocolError as error:
        _fail(error.code, str(error))
    output_crc = crc32(output)
    output_sha = _sha256(output)
    if len(output) != int(manifest["input_length"]):
        _fail("OBJECT_LENGTH", "reassembled length differs from input manifest")
    if output_crc != int(manifest["input_crc32"]):
        _fail("OBJECT_CRC32", "reassembled object CRC32 differs from input manifest")
    if output_sha != manifest["input_sha256"]:
        _fail("OBJECT_SHA256", "reassembled object SHA256 differs from input manifest")

    atomic_commit(output_path, output)
    latency_bounds = [int(record["latency_upper_bound_us"]) for record in fragment_records]

    def nearest_rank(percentile: float) -> int:
        ordered = sorted(latency_bounds)
        return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]

    aggregate_latency_upper_bound_us = sum(latency_bounds)
    poll_bound_goodput_lower_bound_bps = (
        (len(output) * 8_000_000) // aggregate_latency_upper_bound_us
        if aggregate_latency_upper_bound_us > 0
        else 0
    )
    summary = {
        "P7_JTAG_BACKEND_PARSE": "PASS",
        "manifest": str(manifest_path),
        "raw_log": str(raw_log_path),
        "output_file": str(output_path),
        "object_length": len(output),
        "object_crc32": output_crc,
        "object_sha256": output_sha,
        "lane_policy": manifest["lane_policy"],
        "fragment_count": len(fragment_records),
        "transaction_operation_count": manifest["transaction_operation_count"],
        "transaction_file_bytes": manifest["transaction_file_bytes"],
        "runtime_feasibility": manifest["runtime_feasibility"],
        "fragments": fragment_records,
        "fragment_latency_upper_bound_us": {
            "sample_count": len(latency_bounds),
            "min": min(latency_bounds),
            "mean": round(sum(latency_bounds) / len(latency_bounds), 6),
            "p50": nearest_rank(0.50),
            "p95": nearest_rank(0.95),
            "p99": nearest_rank(0.99),
            "max": max(latency_bounds),
            "percentile_method": "nearest_rank",
            "semantics": "upper_bound",
            "source": "bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period",
        },
        "object_transport_latency_upper_bound_us": aggregate_latency_upper_bound_us,
        "object_transport_latency_semantics": "sum_of_sequential_fragment_poll_upper_bounds",
        "poll_bound_application_goodput_lower_bound_bps": poll_bound_goodput_lower_bound_bps,
        "poll_bound_goodput_semantics": "lower_bound_from_object_bytes_over_transport_latency_upper_bound",
        "missing_fragments": 0,
        "duplicate_fragments": 0,
        "error_counter_increments": 0,
        "hardware_actions_executed_by_module": False,
        "NO_HARDWARE": 1,
        "raw_log_execution_provenance": "EXTERNAL_OR_MEMORY_MOCK_NOT_PROMOTED",
        "network_used": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    if summary_path is not None:
        atomic_commit(
            summary_path,
            (json.dumps(summary, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
    return summary


class MemoryMockExecutor:
    """Pure-memory executor for generated W/R/POLL transactions."""

    def __init__(
        self,
        *,
        base_address: int = DEFAULT_BASE_ADDRESS,
        expected_p6_session: int = DEFAULT_P6_SESSION,
    ) -> None:
        self.base_address = base_address
        self.expected_p6_session = expected_p6_session
        self.registers: dict[int, int] = {
            regs.IR_REG_P6_STATUS: P6_STATUS_READY,
            regs.IR_REG_P6_ERROR_CODE: 0,
            regs.IR_REG_P6_STICKY_ERROR: 0,
        }
        self.tx_words = [0] * 64
        self.rx_words = [0] * 64
        self.committed = False

    def _offset(self, address: int) -> int:
        offset = address - self.base_address
        if offset < 0 or offset > 0xFFFF:
            _fail("MOCK_ADDRESS", f"address 0x{address:08x} is outside the mock window")
        return offset

    def _payload(self) -> bytes:
        length = self.registers.get(regs.IR_REG_P6_PAYLOAD_LEN, 0) & 0xFFFF
        return _bytes_from_words(self.tx_words, length)

    def _reject(self, code: int) -> None:
        self.registers[regs.IR_REG_P6_ERROR_CODE] = code
        self.registers[regs.IR_REG_P6_STICKY_ERROR] = 1
        self.registers[regs.IR_REG_P6_STATUS] = (
            P6_STATUS_READY | P6_STATUS_DONE | P6_STATUS_FAIL | P6_STATUS_CONFIG_REJECTED
        )
        self.committed = False

    def _validate(self, require_commit: bool) -> int:
        if require_commit and not self.committed:
            return 6
        if self.registers.get(regs.IR_REG_P6_SESSION, 0) != self.expected_p6_session:
            return 1
        lane = self.registers.get(regs.IR_REG_P6_LANE_MASK, 0)
        if lane not in (1, 2, 3):
            return 2
        if self.registers.get(regs.IR_REG_P6_ACK_LANE_MASK, 0) != lane:
            return 3
        length = self.registers.get(regs.IR_REG_P6_PAYLOAD_LEN, 0) & 0xFFFF
        if not 1 <= length <= P6_MAX_PAYLOAD_BYTES:
            return 4
        if self.registers.get(regs.IR_REG_P6_TIMEOUT_CYCLES, 0) == 0:
            return 5
        return 0

    def _control(self, value: int) -> None:
        if value & P6_CTRL_CLEAR_STICKY:
            self.registers[regs.IR_REG_P6_ERROR_CODE] = 0
            self.registers[regs.IR_REG_P6_STICKY_ERROR] = 0
            self.registers[regs.IR_REG_COUNTER_TX_PULSE] = 0
            self.registers[regs.IR_REG_COUNTER_RX_RAW_PULSE] = 0
            self.registers[regs.IR_REG_P6_STATUS] = P6_STATUS_READY | (
                P6_STATUS_COMMITTED if self.committed else 0
            )
        if value & P6_CTRL_COMMIT:
            error = self._validate(require_commit=False)
            if error:
                self._reject(error)
                return
            payload = self._payload()
            self.registers[regs.IR_REG_P6_PAYLOAD_CRC32] = crc32(payload)
            self.registers[regs.IR_REG_P6_STATUS] = P6_STATUS_READY | P6_STATUS_COMMITTED
            self.committed = True
        if value & P6_CTRL_START:
            error = self._validate(require_commit=True)
            if error:
                self._reject(error)
                return
            payload = self._payload()
            for index in range(64):
                self.rx_words[index] = self.tx_words[index]
            digest = crc32(payload)
            self.registers[regs.IR_REG_P6_RX_PAYLOAD_LEN] = len(payload)
            self.registers[regs.IR_REG_P6_RX_PAYLOAD_CRC32] = digest
            self.registers[regs.IR_REG_P6_RX_DIGEST] = digest
            self.registers[regs.IR_REG_P6_MAILBOX_STATUS] = P6_MAILBOX_OK
            self.registers[regs.IR_REG_P6_TX_COUNT] = self.registers.get(regs.IR_REG_P6_TX_COUNT, 0) + 1
            lane = self.registers[regs.IR_REG_P6_LANE_MASK]
            if lane & 0x1:
                self.registers[regs.IR_REG_P6_RX_GOOD_COUNT_L0] = (
                    self.registers.get(regs.IR_REG_P6_RX_GOOD_COUNT_L0, 0) + 1
                )
            if lane & 0x2:
                self.registers[regs.IR_REG_P6_RX_GOOD_COUNT_L1] = (
                    self.registers.get(regs.IR_REG_P6_RX_GOOD_COUNT_L1, 0) + 1
                )
            pulses = max(1, len(payload) * 4)
            self.registers[regs.IR_REG_COUNTER_TX_PULSE] = (
                self.registers.get(regs.IR_REG_COUNTER_TX_PULSE, 0) + pulses
            )
            self.registers[regs.IR_REG_COUNTER_RX_RAW_PULSE] = (
                self.registers.get(regs.IR_REG_COUNTER_RX_RAW_PULSE, 0) + pulses
            )
            for offset in (
                regs.IR_REG_COUNTER_FRAME_GOOD,
                regs.IR_REG_COUNTER_ACK_SENT,
                regs.IR_REG_COUNTER_ACK_SEEN,
            ):
                self.registers[offset] = self.registers.get(offset, 0) + 1
            self.registers[regs.IR_REG_P6_TXD_HIGH_CONSECUTIVE_MAX] = max(
                8, self.registers.get(regs.IR_REG_P6_TXD_HIGH_CONSECUTIVE_MAX, 0)
            )
            self.registers[regs.IR_REG_P6_STATUS] = (
                P6_STATUS_READY | P6_STATUS_COMMITTED | P6_STATUS_DONE
            )
        if value & P6_CTRL_SHUTDOWN:
            self.registers[regs.IR_REG_P6_SHUTDOWN_REASON] = P6_SHUTDOWN_REASON_TFDU

    def write32(self, address: int, value: int) -> None:
        offset = self._offset(address)
        value &= 0xFFFFFFFF
        tx_base = regs.IR_REG_P6_PAYLOAD_WINDOW_BASE
        if tx_base <= offset < tx_base + 256 and (offset - tx_base) % 4 == 0:
            self.tx_words[(offset - tx_base) // 4] = value
            return
        self.registers[offset] = value
        if offset == regs.IR_REG_P6_CTRL:
            self._control(value)

    def read32(self, address: int) -> int:
        offset = self._offset(address)
        tx_base = regs.IR_REG_P6_PAYLOAD_WINDOW_BASE
        rx_base = regs.IR_REG_P6_RX_WINDOW_BASE
        if tx_base <= offset < tx_base + 256 and (offset - tx_base) % 4 == 0:
            return self.tx_words[(offset - tx_base) // 4]
        if rx_base <= offset < rx_base + 256 and (offset - rx_base) % 4 == 0:
            return self.rx_words[(offset - rx_base) // 4]
        return self.registers.get(offset, 0) & 0xFFFFFFFF

    def execute(self, transaction_path: Path, raw_log_path: Path) -> dict[str, Any]:
        if not transaction_path.is_file() or not 1 <= transaction_path.stat().st_size <= MAX_TRANSACTION_BYTES:
            _fail("MOCK_TRANSACTION_SIZE", "transaction file is missing, empty, or oversized")
        operations = 0
        first_meaningful = True
        ended = False
        last_operation: tuple[str, int, int] | None = None
        used_keys: set[str] = set()
        line_number = 0
        with _AtomicLineSink(raw_log_path, max_bytes=MAX_RAW_LOG_BYTES) as output:
            output.append("P7_MEMORY_MOCK_EXECUTOR=1")
            with transaction_path.open("rb") as handle:
                while True:
                    raw_line = handle.readline(MAX_TRANSACTION_LINE_BYTES + 1)
                    if not raw_line:
                        break
                    line_number += 1
                    if len(raw_line) > MAX_TRANSACTION_LINE_BYTES:
                        _fail("MOCK_LINE_SIZE", f"line {line_number} is too long")
                    try:
                        line = raw_line.decode("ascii", errors="strict").strip()
                    except UnicodeDecodeError as error:
                        _fail("MOCK_ASCII", f"line {line_number}: {error}")
                    if not line or line.startswith("#"):
                        continue
                    if first_meaningful:
                        if line != TRANSACTION_MAGIC:
                            _fail("MOCK_MAGIC", f"line {line_number}: transaction magic missing")
                        first_meaningful = False
                        continue
                    if ended:
                        _fail("MOCK_AFTER_END", f"line {line_number}: content after END")
                    fields = line.split()
                    operation = fields[0]
                    if operation == "END":
                        if len(fields) != 1:
                            _fail("MOCK_SYNTAX", f"line {line_number}: END arguments")
                        ended = True
                        continue
                    if operation == "META":
                        if len(fields) != 3:
                            _fail("MOCK_SYNTAX", f"line {line_number}: META syntax")
                        continue
                    operations += 1
                    if operations > MAX_TRANSACTION_OPERATIONS:
                        _fail("MOCK_OPERATION_LIMIT", str(MAX_TRANSACTION_OPERATIONS))
                    try:
                        if operation == "W32" and len(fields) == 3:
                            address = int(fields[1], 0)
                            data = int(fields[2], 0)
                            self.write32(address, data)
                            last_operation = (operation, address, data)
                        elif operation == "R32" and len(fields) == 3:
                            key = fields[2]
                            if key in used_keys:
                                _fail("MOCK_DUPLICATE_KEY", key)
                            used_keys.add(key)
                            output.append(f"{key}={self.read32(int(fields[1], 0)):08X}")
                            last_operation = (operation, int(fields[1], 0), 0)
                        elif operation == "POLL32" and len(fields) == 7:
                            address = int(fields[1], 0)
                            mask = int(fields[2], 0)
                            expected = int(fields[3], 0)
                            max_polls = int(fields[4], 10)
                            delay_ms = int(fields[5], 10)
                            key = fields[6]
                            if not 1 <= max_polls <= 10_000 or not 0 <= delay_ms <= 100:
                                _fail("MOCK_POLL_BOUND", f"line {line_number}")
                            if key in used_keys:
                                _fail("MOCK_DUPLICATE_KEY", key)
                            used_keys.add(key)
                            polls_key = f"{key}_POLLS"
                            if polls_key in used_keys:
                                _fail("MOCK_DUPLICATE_KEY", polls_key)
                            used_keys.add(polls_key)
                            value = self.read32(address)
                            if value & mask != expected:
                                output.append(f"{key}={value:08X}")
                                output.append(f"{key}_TIMEOUT=1")
                                _fail("MOCK_POLL_TIMEOUT", f"line {line_number}: {key}")
                            output.append(f"{key}={value:08X}")
                            output.append(f"{key}_POLLS=1")
                            last_operation = (operation, address, 0)
                        elif operation == "ASSERT32" and len(fields) == 5:
                            address = int(fields[1], 0)
                            mask = int(fields[2], 0)
                            expected = int(fields[3], 0)
                            key = fields[4]
                            if key in used_keys:
                                _fail("MOCK_DUPLICATE_KEY", key)
                            used_keys.add(key)
                            value = self.read32(address)
                            output.append(f"{key}={value:08X}")
                            if value & mask != expected:
                                _fail("MOCK_ASSERT", f"line {line_number}: {key}")
                            last_operation = (operation, address, 0)
                        else:
                            _fail("MOCK_OPERATION", f"line {line_number}: {line}")
                    except ValueError as error:
                        _fail("MOCK_SYNTAX", f"line {line_number}: {error}")
            if first_meaningful or not ended:
                _fail("MOCK_END", "transaction magic or END missing")
            if last_operation != (
                "W32",
                self.base_address + regs.IR_REG_P6_CTRL,
                P6_CTRL_STOP | P6_CTRL_SHUTDOWN,
            ):
                _fail("MOCK_FINAL_SHUTDOWN", "final operation is not P6 stop/shutdown")
            output.append("P7_JTAG_AXI_TRANSACTIONS=PASS")
            output.append(f"P7_TRANSACTION_COUNT={operations}")
        return {
            "P7_MEMORY_MOCK_EXECUTOR": "PASS",
            "operations": operations,
            "hardware_actions_executed": False,
            "network_used": False,
        }


def _self_test_data(size: int, salt: int) -> bytes:
    pattern = bytes(((index * 73 + salt * 29) ^ (index >> 1)) & 0xFF for index in range(256))
    return (pattern * ((size + 255) // 256))[:size]


def run_memory_mock_self_test() -> dict[str, Any]:
    sizes = (0, 215, 216, 4096)
    policies = tuple(LanePolicy)
    cases = 0
    fragments = 0
    with tempfile.TemporaryDirectory(prefix="p7_jtag_backend_") as temp_text:
        temp = Path(temp_text)
        for policy_index, policy in enumerate(policies):
            for size in sizes:
                case = f"{policy.name.lower()}_{size}"
                data = _self_test_data(size, policy_index + 1)
                transaction = temp / f"{case}.transactions.txt"
                manifest = temp / f"{case}.manifest.json"
                raw = temp / f"{case}.raw.log"
                output = temp / f"{case}.output.bin"
                generated = generate_bundle(
                    data,
                    transaction_path=transaction,
                    manifest_path=manifest,
                    session_epoch=0x50370000 + policy_index,
                    object_id=size + 1,
                    lane_policy=policy,
                )
                MemoryMockExecutor().execute(transaction, raw)
                parsed = parse_raw_result(
                    manifest_path=manifest,
                    raw_log_path=raw,
                    output_path=output,
                )
                if output.read_bytes() != data or parsed["object_sha256"] != _sha256(data):
                    _fail("SELF_TEST_ROUNDTRIP", case)
                actual_lanes = [item["lane_mask"] for item in generated["fragments"]]
                expected_lanes = [lane_for_fragment(policy, index) for index in range(len(actual_lanes))]
                if actual_lanes != expected_lanes:
                    _fail("SELF_TEST_LANE_POLICY", case)
                cases += 1
                fragments += len(generated["fragments"])

        negative_data = _self_test_data(216, 99)
        transaction = temp / "negative.transactions.txt"
        manifest = temp / "negative.manifest.json"
        raw = temp / "negative.raw.log"
        output = temp / "negative.output.bin"
        generate_bundle(
            negative_data,
            transaction_path=transaction,
            manifest_path=manifest,
            session_epoch=0x5037FFFF,
            object_id=0x1234,
            lane_policy=LanePolicy.STRIPE_ROUND_ROBIN,
        )
        MemoryMockExecutor().execute(transaction, raw)
        original_lines = raw.read_text(encoding="utf-8").splitlines()
        mutations = {
            "missing": [line for line in original_lines if not line.startswith("P7F00001_RXW000=")],
            "duplicate": original_lines
            + [next(line for line in original_lines if line.startswith("P7F00000_RXW000="))],
            "unexpected_fragment": original_lines + ["P7F99999_RXW000=00000000"],
            "corrupt_rx": [
                "P7F00000_RXW000=00000000" if line.startswith("P7F00000_RXW000=") else line
                for line in original_lines
            ],
            "safety_error": [
                "P7F00000_DUTY_VIOLATION=00000001"
                if line.startswith("P7F00000_DUTY_VIOLATION=")
                else line
                for line in original_lines
            ],
        }
        negative_codes: dict[str, str] = {}
        for name, lines in mutations.items():
            mutated = temp / f"{name}.raw.log"
            atomic_commit(mutated, ("\n".join(lines) + "\n").encode("utf-8"))
            atomic_commit(output, b"existing-output-must-survive")
            try:
                parse_raw_result(
                    manifest_path=manifest,
                    raw_log_path=mutated,
                    output_path=output,
                )
            except BackendValidationError as error:
                negative_codes[name] = error.code
            else:
                _fail("SELF_TEST_NEGATIVE_ACCEPTED", name)
            if output.read_bytes() != b"existing-output-must-survive":
                _fail("SELF_TEST_ATOMICITY", name)
            if list(temp.glob(f".{output.name}.*.partial")):
                _fail("SELF_TEST_PARTIAL_FILE", name)
    return {
        "P7_JTAG_BACKEND_MEMORY_MOCK_SELF_TEST": "PASS",
        "roundtrip_cases": cases,
        "roundtrip_fragments": fragments,
        "sizes": list(sizes),
        "lane_policies": [policy.name for policy in policies],
        "negative_cases": negative_codes,
        "atomic_replace": "PASS",
        "hardware_actions_executed": False,
        "network_used": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser("generate", help="generate dry-run manifest/transactions")
    generate_parser.add_argument("--input-file", required=True)
    generate_parser.add_argument("--transaction-file", required=True)
    generate_parser.add_argument("--manifest", required=True)
    generate_parser.add_argument("--session-epoch", default="0x50370001")
    generate_parser.add_argument("--object-id", default="1")
    generate_parser.add_argument(
        "--lane-policy",
        default="STRIPE_ROUND_ROBIN",
        choices=[policy.name for policy in LanePolicy],
    )
    generate_parser.add_argument("--base-address", default=f"0x{DEFAULT_BASE_ADDRESS:x}")
    generate_parser.add_argument("--p6-session", default=f"0x{DEFAULT_P6_SESSION:x}")
    generate_parser.add_argument("--timeout-cycles", default=f"0x{DEFAULT_TIMEOUT_CYCLES:x}")
    generate_parser.add_argument("--commit-polls", type=int, default=DEFAULT_COMMIT_POLLS)
    generate_parser.add_argument("--transfer-polls", type=int, default=DEFAULT_TRANSFER_POLLS)
    generate_parser.add_argument("--poll-period-us", type=int, default=DEFAULT_POLL_PERIOD_US)
    generate_parser.add_argument(
        "--jtag-frequency-hz", type=int, default=REFERENCE_JTAG_FREQUENCY_HZ
    )
    generate_parser.add_argument(
        "--authorized-runtime-sec", type=int, default=MAX_AUTHORIZED_RUNTIME_SECONDS
    )

    parse_parser = subparsers.add_parser("parse", help="strictly parse externally produced raw log")
    parse_parser.add_argument("--manifest", required=True)
    parse_parser.add_argument("--raw-log", required=True)
    parse_parser.add_argument("--output-file", required=True)
    parse_parser.add_argument("--summary-file")

    mock_parser = subparsers.add_parser("mock-execute", help="offline Memory/mock execution only")
    mock_parser.add_argument("--manifest", required=True)
    mock_parser.add_argument("--raw-log", required=True)

    subparsers.add_parser("self-test", help="run offline Memory/mock conformance tests")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            input_path = Path(args.input_file).resolve()
            result = generate_bundle(
                input_path.read_bytes(),
                transaction_path=Path(args.transaction_file).resolve(),
                manifest_path=Path(args.manifest).resolve(),
                session_epoch=int(args.session_epoch, 0),
                object_id=int(args.object_id, 0),
                lane_policy=args.lane_policy,
                base_address=int(args.base_address, 0),
                p6_session=int(args.p6_session, 0),
                timeout_cycles=int(args.timeout_cycles, 0),
                commit_polls=args.commit_polls,
                transfer_polls=args.transfer_polls,
                poll_period_us=args.poll_period_us,
                jtag_frequency_hz=args.jtag_frequency_hz,
                authorized_runtime_sec=args.authorized_runtime_sec,
            )
            output: dict[str, Any] = {
                "P7_JTAG_BACKEND_GENERATE": "DRY_RUN_PASS",
                "manifest": str(Path(args.manifest).resolve()),
                "transaction_file": str(Path(args.transaction_file).resolve()),
                "input_length": result["input_length"],
                "input_sha256": result["input_sha256"],
                "fragment_count": result["fragment_count"],
                "transaction_operation_count": result["transaction_operation_count"],
                "transaction_file_bytes": result["transaction_file_bytes"],
                "runtime_feasibility": result["runtime_feasibility"],
                "lane_policy": result["lane_policy"],
                "hardware_actions_executed": False,
                "network_used": False,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
        elif args.command == "parse":
            output = parse_raw_result(
                manifest_path=Path(args.manifest).resolve(),
                raw_log_path=Path(args.raw_log).resolve(),
                output_path=Path(args.output_file).resolve(),
                summary_path=Path(args.summary_file).resolve() if args.summary_file else None,
            )
        elif args.command == "mock-execute":
            manifest_path = Path(args.manifest).resolve()
            manifest = _load_manifest(manifest_path)
            transaction = (manifest_path.parent / manifest["transaction_file"]).resolve()
            output = MemoryMockExecutor(
                base_address=int(manifest["base_address"]),
                expected_p6_session=int(manifest["p6_session"]),
            ).execute(transaction, Path(args.raw_log).resolve())
        else:
            output = run_memory_mock_self_test()
    except (BackendValidationError, OSError, ProtocolError, ValueError) as error:
        code = error.code if isinstance(error, BackendValidationError) else type(error).__name__
        failure = {
            "P7_JTAG_BACKEND": "FAIL",
            "error_code": code,
            "reason": str(error),
            "hardware_actions_executed": False,
            "network_used": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }
        print(json.dumps(failure, sort_keys=True), file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
