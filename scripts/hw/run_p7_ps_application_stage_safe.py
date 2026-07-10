#!/usr/bin/env python3
"""P7 PS application-layer hardware runner with a fail-closed dry-run default.

This wrapper prepares mailbox/descriptor/DDR images offline.  Hardware access
is possible only through fixed Vivado/XSDB Tcl entry points after the complete
P7 authorization and artifact boundary passes.  It never sets
RF_COMM_HW_AUTH and it never accepts an external command or Tcl fragment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import statistics
import struct
import subprocess
import sys
import tempfile
import time
import zlib
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
HW_DIR = ROOT / "scripts" / "hw"
for item in (TOOLS, HW_DIR):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from p7_hardware_safety import (  # noqa: E402
    DEFAULT_ABORT_FILE,
    HardwareExecutionLock,
    SHA256_RE,
    add_common_arguments,
    normalized_path,
    parse_authorization_file,
    resolve_path,
    sha256_file,
    validate_request,
)
from p7_ps_mailbox_backend import (  # noqa: E402
    DescriptorRequest,
    P7_CONTROL_RUN,
    P7_CONTROL_SHUTDOWN,
    P7_CONTROL_STOP,
    P7_DESCRIPTOR_BYTES,
    P7_DESCRIPTOR_COMPLETE,
    P7_DESCRIPTOR_MAGIC,
    P7_DESCRIPTOR_READY,
    P7_DESCRIPTOR_TRANSFER,
    P7_MAILBOX_MAGIC,
    P7_RUNTIME_VERSION,
    P7_MAILBOX_BASE,
    P7_DESCRIPTOR_BASE,
    P7_QUEUE_DEPTH,
    P7_RUNTIME_DEADLINE_REACHED,
    pack_mailbox,
    unpack_descriptor,
    unpack_mailbox,
    validate_completed,
)
from run_p7_authorized_hardware_sequence import (  # noqa: E402
    build_preflight_command,
    evaluate_preflight,
    parse_markers,
)
import run_p7_jtag_axi_stage_safe as process_support  # noqa: E402


PS_EXECUTE_TCL = HW_DIR / "p7_ps_application_execute.tcl"
SHUTDOWN_TCL = HW_DIR / "p7_jtag_axi_transactions.tcl"
P6_IMMUTABLE_DIR = ROOT / "evidence" / "hardware" / "p6" / "bitstreams"
P7_IMMUTABLE_DIR = ROOT / "evidence" / "hardware" / "p7" / "artifacts"
CANONICAL_SHUTDOWN_BIT = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"
P7_BUILD_SUMMARY_DEFAULT = ROOT / "evidence" / "generated" / "vitis" / "p7_ps_runtime" / "p7_ps_runtime_build_summary.json"
P6_BUILD_SUMMARY_DEFAULT = ROOT / "evidence" / "generated" / "vivado" / "p6_ps_candidate" / "p6_ps_candidate_build_summary.json"
CORE_READINESS_DEFAULT = ROOT / "evidence" / "generated" / "p7_ps_core_hardware_readiness.json"
ACTIVE_PROFILE_DEFAULT = ROOT / "board_profiles" / "ACTIVE_PROFILE.json"
LANE1_PROMOTION_DEFAULT = ROOT / "evidence" / "generated" / "p7_lane1_promotion_summary.json"
FROZEN_SHUTDOWN_DIR = ROOT / "evidence" / "hardware" / "p7" / "shutdown"

PLAN_MAGIC = "P7_PS_EXECUTION_PLAN_V1"
MAX_SERVICE_RUNTIME_SEC = 1800
CALIBRATION_SEC = 300
ACCEPTANCE_SEC = 1500
MIN_IDLE_MARGIN_SEC = 5
MAX_IDLE_MARGIN_SEC = 60
P7_COUNTS_PER_SECOND = 333_333_343
XSDB_PROCESS_GRACE_SEC = 120
STATIONARY_ACTIVE_WATCHDOG_TOLERANCE_SEC = 1.5
STATIONARY_SETUP_WATCHDOG_SEC = 300
POST_SAFE_REAP_GRACE_SEC = 120
FRAGMENT_CHUNK_BYTES = 215
MAX_OBJECT_BYTES = 8 * 1024 * 1024
SLOT_STRIDE = 0x02000000
SLOT_INPUT_OFFSET = 0x00000000
SLOT_OUTPUT_OFFSET = 0x00800000
SLOT_TRACE_OFFSET = 0x01000000
SLOT_BASE = 0x00100000

MODE_NAMES = ("functional", "fault-fallback", "queue", "abort-restart", "stationary")
P7_DESCRIPTOR_FAILED = 4
P7_DESCRIPTOR_ABORTED = 5
P7_TRACE_MAGIC = 0x52543750
EXPECTED_PROFILE_STAGE = {
    "functional": "P7_PS_APPLICATION_FUNCTIONAL",
    "fault-fallback": "P7_PS_APPLICATION_FUNCTIONAL",
    "queue": "P7_PS_APPLICATION_FUNCTIONAL",
    "abort-restart": "P7_PS_APPLICATION_FUNCTIONAL",
    "stationary": "P7_STATIONARY_APP_30MIN",
}
CORE_READINESS_CHECKS = (
    "host_command_cache_disabled_or_isolated",
    "deadline_frozen_in_private_context",
    "active_transfer_obeys_absolute_deadline",
    "stop_abort_shutdown_observed_during_active_object",
    "shutdown_readback_verified",
    "failure_cleanup_shutdown_first",
    "failure_wipe_uses_private_validated_range",
    "descriptor_ready_published_last",
    "terminal_descriptor_stable_snapshot",
    "phy_reenabled_and_startup_ready_waited",
    "runtime_terminal_after_exact_deadline",
    "runtime_elapsed_seqlock_and_monotonic_reader",
    "runtime_elapsed_causal_request_release",
    "object_latency_start_precedes_input_integrity",
    "firmware_stationary_admission_cutoff",
    "contained_child_tree_reaped_before_shutdown",
    "strict_ring_host_publication_supported",
    "stationary_identity_ledger_bound",
    "native_shutdown_readback_test",
    "p7_python_and_codec_tests",
    "real_vitis_build_source_bound",
)
KNOWN_UNSAFE_CORE_FINGERPRINT = "6f17835efdcb8ed22b80d7568f7e55413c60058182e4cd22a2be724d2b9dc63e"
CORE_READINESS_SOURCES = (
    "software/ps_driver/p7_app_service.h",
    "software/ps_driver/p7_admission_contract.h",
    "software/ps_driver/p7_app_service.c",
    "software/ps_driver/p7_runtime_main.c",
    "software/ps_driver/ir_driver.h",
    "software/ps_driver/ir_driver.c",
    "tools/p7_ps_mailbox_backend.py",
    "scripts/hw/run_p7_ps_application_stage_safe.py",
    "scripts/hw/p7_ps_application_execute.tcl",
    "scripts/hw/run_p7_jtag_axi_stage_safe.py",
    "tools/p7_contained_launcher.py",
)
STAGE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")


@dataclass
class StageCase:
    slot: int
    name: str
    request: DescriptorRequest
    expected_status: int
    expected_error: int
    trace_capacity: int
    pattern: str = "deterministic"


@dataclass
class StageBundle:
    directory: Path
    plan_path: Path
    plan_sha256: str
    manifest_path: Path
    manifest_sha256: str
    cases: list[StageCase]
    boundary_cases: list[StageCase]
    functional_checkpoint: StageCase | None
    queue_overflow_candidate: StageCase | None
    scheduling_cutoff_sec: int


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def file_record(path: Path) -> dict[str, Any]:
    return {"path": str(path), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def deterministic_data(seed: bytes, size: int, salt: int) -> bytes:
    if size == 0:
        return b""
    source = seed or bytes(range(251))
    return bytes((source[index % len(source)] ^ ((salt * 29 + index * 17) & 0xFF)) for index in range(size))


def patterned_data(pattern: str, seed: bytes, size: int, salt: int) -> bytes:
    if pattern == "counter":
        return bytes((index + salt) & 0xFF for index in range(size))
    if pattern == "binary_all_byte_values_repeated":
        return bytes(range(256)) * (size // 256) + bytes(range(size % 256))
    if pattern == "prbs15":
        state = ((salt << 7) ^ 0x4A6D) & 0x7FFF or 1
        output = bytearray(size)
        for index in range(size):
            value = 0
            for bit in range(8):
                value |= (state & 1) << bit
                feedback = ((state >> 14) ^ (state >> 13)) & 1
                state = ((state << 1) & 0x7FFF) | feedback
            output[index] = value
        return bytes(output)
    if pattern == "deterministic_random":
        seed_material = hashlib.sha256(seed + salt.to_bytes(4, "little", signed=False)).digest()
        return hashlib.shake_256(seed_material).digest(size)
    raise ValueError(f"unsupported payload pattern: {pattern}")


def slot_addresses(slot: int) -> tuple[int, int, int]:
    if not 0 <= slot < P7_QUEUE_DEPTH:
        raise ValueError("descriptor slot is outside 0..7")
    base = SLOT_BASE + slot * SLOT_STRIDE
    return base + SLOT_INPUT_OFFSET, base + SLOT_OUTPUT_OFFSET, base + SLOT_TRACE_OFFSET


def fragment_count(length: int) -> int:
    return 1 if length == 0 else math.ceil(length / FRAGMENT_CHUNK_BYTES)


def _make_case(
    *,
    slot: int,
    name: str,
    data: bytes,
    session_epoch: int,
    object_id: int,
    lane_policy: int,
    unavailable_lane_mask: int = 0,
    unavailable_after_fragment: int = 0,
    abort_after_fragment: int = 0xFFFFFFFF,
    expected_status: int = P7_DESCRIPTOR_COMPLETE,
    expected_error: int = 0,
    pattern: str = "deterministic",
) -> StageCase:
    input_address, output_address, trace_address = slot_addresses(slot)
    capacity = fragment_count(len(data))
    request = DescriptorRequest(
        session_epoch=session_epoch,
        object_id=object_id,
        input_address=input_address,
        output_address=output_address,
        data=data,
        lane_policy=lane_policy,
        max_retries=3,
        unavailable_lane_mask=unavailable_lane_mask,
        unavailable_after_fragment=unavailable_after_fragment,
        abort_after_fragment=abort_after_fragment,
        trace_address=trace_address,
        trace_capacity=capacity,
    )
    request.validate()
    return StageCase(slot, name, request, expected_status, expected_error, capacity, pattern)


def build_cases(mode: str, input_data: bytes, stationary_object_bytes: int) -> list[StageCase]:
    if len(input_data) > MAX_OBJECT_BYTES:
        raise ValueError(f"input file exceeds P7 maximum object size: {len(input_data)}")
    epoch = 0x50370001
    cases: list[StageCase] = []
    if mode == "functional":
        specs = (
            ("1m_lane0", 1024 * 1024, "deterministic_random", 1),
            ("1m_lane1", 1024 * 1024, "deterministic_random", 2),
            ("1m_stripe", 1024 * 1024, "deterministic_random", 3),
            ("1m_replicate", 1024 * 1024, "deterministic_random", 4),
            ("64k_counter_stripe", 64 * 1024, "counter", 3),
            ("64k_prbs15_stripe", 64 * 1024, "prbs15", 3),
            ("64k_random_stripe", 64 * 1024, "deterministic_random", 3),
            ("64k_all_bytes_stripe", 64 * 1024, "binary_all_byte_values_repeated", 3),
        )
        for slot, (name, size, pattern, lane_policy) in enumerate(specs):
            data = patterned_data(pattern, input_data, size, slot + 1)
            cases.append(
                _make_case(
                    slot=slot,
                    name=name,
                    data=data,
                    session_epoch=epoch,
                    object_id=(54 + slot) if slot < 4 else (50 + slot - 4),
                    lane_policy=lane_policy,
                    pattern=pattern,
                )
            )
    elif mode == "fault-fallback":
        data = patterned_data("deterministic_random", input_data, 64 * 1024, 7)
        specs = (
            ("stripe_lane0_to_lane1", 3, 1, 2, P7_DESCRIPTOR_COMPLETE, 0),
            ("stripe_lane1_to_lane0", 3, 2, 2, P7_DESCRIPTOR_COMPLETE, 0),
            ("replicate_lane0_unavailable", 4, 1, 0, P7_DESCRIPTOR_COMPLETE, 0),
            ("replicate_lane1_unavailable", 4, 2, 0, P7_DESCRIPTOR_COMPLETE, 0),
            ("strict_lane0_unavailable", 1, 1, 0, P7_DESCRIPTOR_FAILED, 8),
            ("strict_lane1_unavailable", 2, 2, 0, P7_DESCRIPTOR_FAILED, 8),
            ("stripe_both_unavailable", 3, 3, 0, P7_DESCRIPTOR_FAILED, 8),
        )
        for slot, (name, policy, unavailable, after_fragment, status, error) in enumerate(specs):
            cases.append(
                _make_case(
                    slot=slot,
                    name=name,
                    data=data,
                    session_epoch=epoch,
                    object_id=slot + 1,
                    lane_policy=policy,
                    unavailable_lane_mask=unavailable,
                    unavailable_after_fragment=after_fragment,
                    expected_status=status,
                    expected_error=error,
                )
            )
    elif mode == "queue":
        for slot in range(P7_QUEUE_DEPTH):
            cases.append(
                _make_case(
                    slot=slot,
                    name=f"queue_{slot}",
                    data=deterministic_data(input_data, 512 + 17 * slot, 20 + slot),
                    session_epoch=epoch,
                    object_id=slot + 1,
                    lane_policy=3,
                )
            )
    elif mode == "abort-restart":
        data = patterned_data("deterministic_random", input_data, 1024 * 1024, 41)
        cases.append(
            _make_case(
                slot=0,
                name="abort_mid_object",
                data=data,
                session_epoch=epoch,
                object_id=1,
                lane_policy=3,
                abort_after_fragment=1,
                expected_status=P7_DESCRIPTOR_ABORTED,
                expected_error=15,
            )
        )
        cases.append(
            _make_case(
                slot=1,
                name="restart_new_epoch",
                data=data,
                session_epoch=epoch + 1,
                object_id=2,
                lane_policy=3,
            )
        )
        cases.append(
            _make_case(
                slot=2,
                name="duplicate_replay_rejected",
                data=data,
                session_epoch=epoch + 1,
                object_id=2,
                lane_policy=3,
                expected_status=6,
                expected_error=19,
            )
        )
    elif mode == "stationary":
        if stationary_object_bytes != 64 * 1024:
            raise ValueError("stationary base object size must be exactly 65536 bytes")
        patterns = (
            "deterministic_random",
            "counter",
            "prbs15",
            "binary_all_byte_values_repeated",
            "deterministic_random",
            "counter",
            "prbs15",
            "binary_all_byte_values_repeated",
        )
        lane_policies = (1, 3, 3, 2, 4, 3, 1, 2)
        for slot in range(P7_QUEUE_DEPTH):
            size = 1024 * 1024 if slot in (0, 4) else (4096 if slot == 5 else stationary_object_bytes)
            pattern = patterns[slot]
            cases.append(
                _make_case(
                    slot=slot,
                    name=f"stationary_{pattern}_{size}_slot_{slot}",
                    data=patterned_data(pattern, input_data, size, 80 + slot),
                    session_epoch=epoch,
                    object_id=slot + 1,
                    lane_policy=lane_policies[slot],
                    unavailable_lane_mask=1 if slot == 1 else (2 if slot == 2 else 0),
                    unavailable_after_fragment=2 if slot in (1, 2) else 0,
                    pattern=pattern,
                )
            )
    else:
        raise ValueError(f"unsupported P7 PS mode: {mode}")
    return cases


def build_functional_boundary_cases(input_data: bytes) -> list[StageCase]:
    epoch = 0x50370001
    cases: list[StageCase] = []
    sizes = (0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024)
    policies = ((1, "lane0"), (2, "lane1"), (3, "stripe"), (4, "replicate"))
    logical_index = 0
    for size in sizes:
        for lane_policy, policy_name in policies:
            ring_slot = logical_index % P7_QUEUE_DEPTH
            pattern = "binary_all_byte_values_repeated" if size else "counter"
            case = _make_case(
                slot=ring_slot,
                name=f"functional_boundary_{size}_{policy_name}",
                data=patterned_data(pattern, input_data, size, 160 + logical_index),
                session_epoch=epoch,
                object_id=1 + logical_index,
                lane_policy=lane_policy,
                pattern=pattern,
            )
            cases.append(replace(case, slot=logical_index))
            logical_index += 1
    return cases


def build_functional_checkpoint(input_data: bytes) -> StageCase:
    return _make_case(
        slot=0,
        name="functional_checkpoint_4096_stripe",
        data=patterned_data("deterministic_random", input_data, 4096, 240),
        session_epoch=0x50370001,
        object_id=49,
        lane_policy=3,
        pattern="deterministic_random",
    )


def build_queue_overflow_candidate(input_data: bytes) -> StageCase:
    """Build a valid ninth producer request that is never pre-written to DDR."""

    virtual_slot = P7_QUEUE_DEPTH
    base = SLOT_BASE + virtual_slot * SLOT_STRIDE
    data = deterministic_data(input_data, 777, 99)
    capacity = fragment_count(len(data))
    request = DescriptorRequest(
        session_epoch=0x50370001,
        object_id=9,
        input_address=base + SLOT_INPUT_OFFSET,
        output_address=base + SLOT_OUTPUT_OFFSET,
        data=data,
        lane_policy=3,
        max_retries=3,
        unavailable_lane_mask=0,
        unavailable_after_fragment=0,
        abort_after_fragment=0xFFFFFFFF,
        trace_address=base + SLOT_TRACE_OFFSET,
        trace_capacity=capacity,
    )
    request.validate()
    return StageCase(virtual_slot, "queue_overflow_candidate_9", request, P7_DESCRIPTOR_COMPLETE, 0, capacity)


def build_stage_bundle(
    *,
    bundle_dir: Path,
    mode: str,
    input_path: Path,
    max_runtime_sec: int,
    calibration_sec: int,
    acceptance_sec: int,
    sample_interval_sec: int,
    idle_margin_sec: int,
    stationary_object_bytes: int,
) -> StageBundle:
    input_data = input_path.read_bytes()
    cases = build_cases(mode, input_data, stationary_object_bytes)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    descriptors = bytearray(P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH)
    records: list[dict[str, Any]] = []
    for case in cases:
        input_file = bundle_dir / f"input_{case.slot}.bin"
        output_zero = bundle_dir / f"output_zero_{case.slot}.bin"
        trace_zero = bundle_dir / f"trace_zero_{case.slot}.bin"
        descriptor_free = bundle_dir / f"descriptor_free_{case.slot}.bin"
        packed = case.request.pack()
        descriptors[case.slot * P7_DESCRIPTOR_BYTES : (case.slot + 1) * P7_DESCRIPTOR_BYTES] = packed
        free_image = bytearray(packed)
        struct.pack_into("<I", free_image, 12, 0)
        atomic_write_bytes(input_file, case.request.data)
        atomic_write_bytes(output_zero, b"\x00" * len(case.request.data))
        atomic_write_bytes(trace_zero, b"\x00" * (case.trace_capacity * 64))
        atomic_write_bytes(descriptor_free, bytes(free_image))
        records.append(
            {
                "slot": case.slot,
                "name": case.name,
                "input_address": f"0x{case.request.input_address:08x}",
                "output_address": f"0x{case.request.output_address:08x}",
                "trace_address": f"0x{case.request.trace_address:08x}",
                "object_length": len(case.request.data),
                "trace_capacity": case.trace_capacity,
                "session_epoch": f"0x{case.request.session_epoch:08x}",
                "object_id": case.request.object_id,
                "lane_policy": case.request.lane_policy,
                "unavailable_lane_mask": case.request.unavailable_lane_mask,
                "unavailable_after_fragment": case.request.unavailable_after_fragment,
                "abort_after_fragment": case.request.abort_after_fragment,
                "expected_status": case.expected_status,
                "expected_error": case.expected_error,
                "pattern": case.pattern,
                "input": file_record(input_file),
                "output_zero": file_record(output_zero),
                "trace_zero": file_record(trace_zero),
                "descriptor_free": file_record(descriptor_free),
                "ready_publication": {
                    "address": f"0x{P7_DESCRIPTOR_BASE + case.slot * P7_DESCRIPTOR_BYTES + 12:08x}",
                    "value": P7_DESCRIPTOR_READY,
                    "published_after_body": True,
                },
            }
        )
    boundary_cases = build_functional_boundary_cases(input_data) if mode == "functional" else []
    boundary_records: list[dict[str, Any]] = []
    boundary_descriptor_batch_records: list[dict[str, Any]] = []
    if boundary_cases:
        boundary_batches = [bytearray(P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH) for _ in range(6)]
        for case in boundary_cases:
            batch = case.slot // P7_QUEUE_DEPTH
            ring_slot = case.slot % P7_QUEUE_DEPTH
            prefix = f"boundary_{case.slot}"
            input_file = bundle_dir / f"{prefix}_input.bin"
            output_zero = bundle_dir / f"{prefix}_output_zero.bin"
            trace_zero = bundle_dir / f"{prefix}_trace_zero.bin"
            descriptor_free = bundle_dir / f"{prefix}_descriptor_free.bin"
            packed = case.request.pack()
            boundary_batches[batch][
                ring_slot * P7_DESCRIPTOR_BYTES : (ring_slot + 1) * P7_DESCRIPTOR_BYTES
            ] = packed
            atomic_write_bytes(input_file, case.request.data)
            atomic_write_bytes(output_zero, b"\x00" * len(case.request.data))
            atomic_write_bytes(trace_zero, b"\x00" * (case.trace_capacity * 64))
            atomic_write_bytes(descriptor_free, packed)
            boundary_records.append(
                {
                    "slot": case.slot,
                    "batch": batch,
                    "ring_slot": ring_slot,
                    "name": case.name,
                    "object_length": len(case.request.data),
                    "session_epoch": f"0x{case.request.session_epoch:08x}",
                    "object_id": case.request.object_id,
                    "lane_policy": case.request.lane_policy,
                    "trace_capacity": case.trace_capacity,
                    "input": file_record(input_file),
                    "output_zero": file_record(output_zero),
                    "trace_zero": file_record(trace_zero),
                    "descriptor_free": file_record(descriptor_free),
                    "ready_publication": {
                        "address": f"0x{P7_DESCRIPTOR_BASE + ring_slot * P7_DESCRIPTOR_BYTES + 12:08x}",
                        "value": P7_DESCRIPTOR_READY,
                        "published_after_body": True,
                    },
                }
            )
        for batch, descriptors_batch in enumerate(boundary_batches):
            batch_path = bundle_dir / f"boundary_batch_{batch}_descriptors.bin"
            atomic_write_bytes(batch_path, bytes(descriptors_batch))
            boundary_descriptor_batch_records.append(file_record(batch_path))
    functional_checkpoint = build_functional_checkpoint(input_data) if mode == "functional" else None
    functional_checkpoint_record: dict[str, Any] | None = None
    if functional_checkpoint is not None:
        case = functional_checkpoint
        prefix = "functional_checkpoint_4k"
        input_file = bundle_dir / f"{prefix}_input.bin"
        output_zero = bundle_dir / f"{prefix}_output_zero.bin"
        trace_zero = bundle_dir / f"{prefix}_trace_zero.bin"
        descriptor_free = bundle_dir / f"{prefix}_descriptor_free.bin"
        atomic_write_bytes(input_file, case.request.data)
        atomic_write_bytes(output_zero, b"\x00" * len(case.request.data))
        atomic_write_bytes(trace_zero, b"\x00" * (case.trace_capacity * 64))
        atomic_write_bytes(descriptor_free, case.request.pack())
        functional_checkpoint_record = {
            "name": case.name,
            "session_epoch": f"0x{case.request.session_epoch:08x}",
            "object_id": case.request.object_id,
            "input_address": f"0x{case.request.input_address:08x}",
            "output_address": f"0x{case.request.output_address:08x}",
            "trace_address": f"0x{case.request.trace_address:08x}",
            "object_length": len(case.request.data),
            "trace_capacity": case.trace_capacity,
            "lane_policy": case.request.lane_policy,
            "expected_completion_sequence": 49,
            "input": file_record(input_file),
            "output_zero": file_record(output_zero),
            "trace_zero": file_record(trace_zero),
            "descriptor_free": file_record(descriptor_free),
            "ready_publication": {
                "address": f"0x{P7_DESCRIPTOR_BASE + 12:08x}",
                "value": P7_DESCRIPTOR_READY,
                "published_after_body": True,
            },
        }
    queue_overflow_candidate = build_queue_overflow_candidate(input_data) if mode == "queue" else None
    queue_overflow_record: dict[str, Any] | None = None
    if queue_overflow_candidate is not None:
        case = queue_overflow_candidate
        prefix = "queue_overflow_candidate"
        input_file = bundle_dir / f"{prefix}_input.bin"
        output_zero = bundle_dir / f"{prefix}_output_zero.bin"
        trace_zero = bundle_dir / f"{prefix}_trace_zero.bin"
        descriptor_free = bundle_dir / f"{prefix}_descriptor_free.bin"
        packed = case.request.pack()
        atomic_write_bytes(input_file, case.request.data)
        atomic_write_bytes(output_zero, b"\x00" * len(case.request.data))
        atomic_write_bytes(trace_zero, b"\x00" * (case.trace_capacity * 64))
        atomic_write_bytes(descriptor_free, packed)
        queue_overflow_record = {
            "candidate_index": P7_QUEUE_DEPTH,
            "name": case.name,
            "session_epoch": f"0x{case.request.session_epoch:08x}",
            "object_id": case.request.object_id,
            "input_address": f"0x{case.request.input_address:08x}",
            "output_address": f"0x{case.request.output_address:08x}",
            "trace_address": f"0x{case.request.trace_address:08x}",
            "object_length": len(case.request.data),
            "trace_capacity": case.trace_capacity,
            "lane_policy": case.request.lane_policy,
            "input": file_record(input_file),
            "output_zero": file_record(output_zero),
            "trace_zero": file_record(trace_zero),
            "descriptor_free": file_record(descriptor_free),
            "admission_contract": {
                "expected_result": "FULL",
                "required_occupancy": P7_QUEUE_DEPTH,
                "capacity": P7_QUEUE_DEPTH,
                "expected_ddr_write_count": 0,
                "ring_must_remain_byte_identical": True,
            },
        }
    descriptor_file = bundle_dir / "descriptors.bin"
    mailbox_file = bundle_dir / "mailbox.bin"
    atomic_write_bytes(descriptor_file, bytes(descriptors))
    initial_command = P7_CONTROL_STOP if mode == "queue" else P7_CONTROL_RUN
    scheduling_cutoff = max_runtime_sec - idle_margin_sec
    firmware_cutoff = scheduling_cutoff if mode == "stationary" else 0
    firmware_admission_guard = 1 if mode == "stationary" else 0
    mailbox_image = bytearray(
        pack_mailbox(
            control_command=initial_command,
            max_runtime_seconds=max_runtime_sec,
            calibration_window_seconds=calibration_sec,
            sample_interval_seconds=sample_interval_sec,
            scheduling_cutoff_seconds=firmware_cutoff,
            admission_guard_seconds=firmware_admission_guard,
        )
    )
    # BOOTING=0 is the pre-start sentinel; the service publishes READY/STOPPED
    # only after it validates the mailbox and establishes the runtime deadline.
    struct.pack_into("<I", mailbox_image, 8, 0)
    atomic_write_bytes(mailbox_file, bytes(mailbox_image))
    queue_phase_mailboxes: dict[str, Any] = {}
    if mode == "queue":
        depth1_path = bundle_dir / "mailbox_queue_depth_1.bin"
        depth8_stop_path = bundle_dir / "mailbox_queue_depth_8_stop.bin"
        depth1 = bytearray(
            pack_mailbox(
                control_command=P7_CONTROL_RUN,
                queue_depth=1,
                max_runtime_seconds=max_runtime_sec,
                calibration_window_seconds=0,
                sample_interval_seconds=sample_interval_sec,
            )
        )
        struct.pack_into("<I", depth1, 8, 0)
        atomic_write_bytes(depth1_path, bytes(depth1))
        atomic_write_bytes(depth8_stop_path, bytes(mailbox_image))
        queue_phase_mailboxes = {
            "depth_1_run": file_record(depth1_path),
            "depth_8_stop": file_record(depth8_stop_path),
        }
    plan_lines = [
        PLAN_MAGIC,
        f"MODE {mode}",
        f"MAX_RUNTIME_SECONDS {max_runtime_sec}",
        f"CALIBRATION_SECONDS {calibration_sec}",
        f"ACCEPTANCE_SECONDS {acceptance_sec}",
        f"SAMPLE_INTERVAL_SECONDS {sample_interval_sec}",
        f"IDLE_MARGIN_SECONDS {idle_margin_sec}",
        f"SCHEDULING_CUTOFF_SECONDS {scheduling_cutoff}",
        f"COUNTS_PER_SECOND {P7_COUNTS_PER_SECOND}",
        f"CASE_COUNT {len(cases)}",
        f"BOUNDARY_COUNT {len(boundary_cases)}",
        f"CHECKPOINT_COUNT {1 if functional_checkpoint is not None else 0}",
    ]
    for case in cases:
        plan_lines.append(
            " ".join(
                [
                    "CASE",
                    str(case.slot),
                    f"0x{case.request.input_address:08x}",
                    f"0x{case.request.output_address:08x}",
                    str(len(case.request.data)),
                    f"0x{case.request.trace_address:08x}",
                    str(case.trace_capacity),
                    f"0x{case.request.session_epoch:08x}",
                    str(case.request.object_id),
                    str(case.expected_status),
                    str(case.expected_error),
                    str(case.request.lane_policy),
                    str(case.request.unavailable_lane_mask),
                    str(case.request.unavailable_after_fragment),
                ]
            )
        )
    for case in boundary_cases:
        plan_lines.append(
            " ".join(
                [
                    "BOUNDARY",
                    str(case.slot),
                    f"0x{case.request.input_address:08x}",
                    f"0x{case.request.output_address:08x}",
                    str(len(case.request.data)),
                    f"0x{case.request.trace_address:08x}",
                    str(case.trace_capacity),
                    f"0x{case.request.session_epoch:08x}",
                    str(case.request.object_id),
                    str(case.expected_status),
                    str(case.expected_error),
                    str(case.request.lane_policy),
                    str(case.request.unavailable_lane_mask),
                    str(case.request.unavailable_after_fragment),
                ]
            )
        )
    plan_lines.append("END")
    plan_path = bundle_dir / "execution_plan.txt"
    atomic_write_text(plan_path, "\n".join(plan_lines) + "\n")
    manifest_path = bundle_dir / "bundle_manifest.json"
    manifest = {
        "schema": "rf-comm-p7-ps-hardware-bundle-v1",
        "generated_at_utc": now_utc(),
        "mode": mode,
        "hardware_actions_executed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "input_source": file_record(input_path),
        "mailbox": file_record(mailbox_file),
        "descriptors": file_record(descriptor_file),
        "execution_plan": file_record(plan_path),
        "queue_phase_mailboxes": queue_phase_mailboxes,
        "case_count": len(cases),
        "cases": records,
        "boundary_case_count": len(boundary_cases),
        "boundary_cases": boundary_records,
        "boundary_descriptor_batches": boundary_descriptor_batch_records,
        "functional_checkpoint": functional_checkpoint_record,
        "queue_overflow_candidate": queue_overflow_record,
        "schedule": {
            "max_runtime_sec": max_runtime_sec,
            "calibration_sec": calibration_sec,
            "acceptance_sec": acceptance_sec,
            "idle_margin_sec": idle_margin_sec,
            "scheduling_cutoff_sec": scheduling_cutoff,
            "counts_per_second": P7_COUNTS_PER_SECOND,
            "calibration_plus_acceptance": calibration_sec + acceptance_sec,
        },
        "atomic_files": True,
    }
    atomic_write_json(manifest_path, manifest)
    return StageBundle(
        bundle_dir,
        plan_path,
        sha256_file(plan_path),
        manifest_path,
        sha256_file(manifest_path),
        cases,
        boundary_cases,
        functional_checkpoint,
        queue_overflow_candidate,
        scheduling_cutoff,
    )


def _verify_manifest_record(record: Any, expected_path: Path, expected_size: int, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"bundle manifest record missing: {label}"]
    if normalized_path(record.get("path", "")) != normalized_path(expected_path):
        errors.append(f"bundle manifest path mismatch: {label}")
    if not expected_path.is_file() or expected_path.is_symlink():
        errors.append(f"bundle file missing or symbolic link: {label}")
        return errors
    if record.get("size_bytes") != expected_size or expected_path.stat().st_size != expected_size:
        errors.append(f"bundle size mismatch: {label}")
    recorded_sha = str(record.get("sha256", "")).lower()
    if not SHA256_RE.fullmatch(recorded_sha) or sha256_file(expected_path) != recorded_sha:
        errors.append(f"bundle SHA256 mismatch: {label}")
    return errors


def verify_bundle_integrity(bundle: StageBundle) -> None:
    """Revalidate the immutable execution bundle immediately before XSDB."""

    errors: list[str] = []
    if not bundle.manifest_path.is_file() or bundle.manifest_path.is_symlink():
        raise RuntimeError("bundle manifest disappeared or became a symbolic link")
    if sha256_file(bundle.manifest_path) != bundle.manifest_sha256:
        raise RuntimeError("bundle manifest hash changed after construction")
    try:
        manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"bundle manifest parse failed: {exc}") from exc
    if manifest.get("schema") != "rf-comm-p7-ps-hardware-bundle-v1":
        errors.append("bundle manifest schema mismatch")
    if manifest.get("case_count") != len(bundle.cases):
        errors.append("bundle manifest case count mismatch")
    schedule = manifest.get("schedule")
    if not isinstance(schedule, dict) or schedule.get("counts_per_second") != P7_COUNTS_PER_SECOND:
        errors.append("bundle manifest PS timer frequency is missing or mismatched")
    if sha256_file(bundle.plan_path) != bundle.plan_sha256:
        errors.append("execution plan hash changed after construction")
    errors.extend(_verify_manifest_record(manifest.get("mailbox"), bundle.directory / "mailbox.bin", 256, "mailbox"))
    errors.extend(
        _verify_manifest_record(
            manifest.get("descriptors"), bundle.directory / "descriptors.bin", P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH, "descriptors"
        )
    )
    errors.extend(_verify_manifest_record(manifest.get("execution_plan"), bundle.plan_path, bundle.plan_path.stat().st_size, "plan"))
    if manifest.get("mode") == "queue":
        queue_mailboxes = manifest.get("queue_phase_mailboxes")
        if not isinstance(queue_mailboxes, dict):
            errors.append("queue phase mailbox records missing")
        else:
            errors.extend(
                _verify_manifest_record(
                    queue_mailboxes.get("depth_1_run"), bundle.directory / "mailbox_queue_depth_1.bin", 256, "queue depth-1 mailbox"
                )
            )
            errors.extend(
                _verify_manifest_record(
                    queue_mailboxes.get("depth_8_stop"), bundle.directory / "mailbox_queue_depth_8_stop.bin", 256, "queue depth-8 mailbox"
                )
            )
    records = manifest.get("cases")
    if not isinstance(records, list) or len(records) != len(bundle.cases):
        errors.append("bundle manifest case records mismatch")
        records = []
    for case in bundle.cases:
        record = records[case.slot] if case.slot < len(records) else None
        if not isinstance(record, dict) or record.get("slot") != case.slot:
            errors.append(f"bundle manifest slot mismatch: {case.slot}")
            continue
        expected_publication = {
            "address": f"0x{P7_DESCRIPTOR_BASE + case.slot * P7_DESCRIPTOR_BYTES + 12:08x}",
            "value": P7_DESCRIPTOR_READY,
            "published_after_body": True,
        }
        if record.get("ready_publication") != expected_publication:
            errors.append(f"bundle READY-publication contract mismatch: slot {case.slot}")
        expected = (
            ("input", bundle.directory / f"input_{case.slot}.bin", len(case.request.data)),
            ("output_zero", bundle.directory / f"output_zero_{case.slot}.bin", len(case.request.data)),
            ("trace_zero", bundle.directory / f"trace_zero_{case.slot}.bin", case.trace_capacity * 64),
            ("descriptor_free", bundle.directory / f"descriptor_free_{case.slot}.bin", P7_DESCRIPTOR_BYTES),
        )
        for key, path, size in expected:
            errors.extend(_verify_manifest_record(record.get(key), path, size, f"slot {case.slot} {key}"))
    descriptor_bytes = (bundle.directory / "descriptors.bin").read_bytes()
    for case in bundle.cases:
        body_status = struct.unpack_from("<I", descriptor_bytes, case.slot * P7_DESCRIPTOR_BYTES + 12)[0]
        free_status = struct.unpack_from(
            "<I", (bundle.directory / f"descriptor_free_{case.slot}.bin").read_bytes(), 12
        )[0]
        if body_status != 0 or free_status != 0:
            errors.append(f"descriptor body was pre-published before final READY write: slot {case.slot}")
    boundary_records = manifest.get("boundary_cases")
    if len(bundle.boundary_cases) != int(manifest.get("boundary_case_count", -1)):
        errors.append("functional boundary case count mismatch")
    if bundle.boundary_cases:
        batch_records = manifest.get("boundary_descriptor_batches")
        if not isinstance(batch_records, list) or len(batch_records) != 6:
            errors.append("functional boundary descriptor batch records missing")
            batch_records = []
        boundary_batch_bytes: list[bytes] = []
        for batch in range(6):
            batch_path = bundle.directory / f"boundary_batch_{batch}_descriptors.bin"
            record = batch_records[batch] if batch < len(batch_records) else None
            errors.extend(
                _verify_manifest_record(
                    record,
                    batch_path,
                    P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH,
                    f"functional boundary descriptor batch {batch}",
                )
            )
            boundary_batch_bytes.append(batch_path.read_bytes() if batch_path.is_file() else b"")
        if not isinstance(boundary_records, list) or len(boundary_records) != len(bundle.boundary_cases):
            errors.append("functional boundary manifest records missing")
            boundary_records = []
        for case in bundle.boundary_cases:
            record = boundary_records[case.slot] if case.slot < len(boundary_records) else {}
            batch = case.slot // P7_QUEUE_DEPTH
            ring_slot = case.slot % P7_QUEUE_DEPTH
            prefix = f"boundary_{case.slot}"
            if (
                record.get("slot") != case.slot
                or record.get("batch") != batch
                or record.get("ring_slot") != ring_slot
                or record.get("object_id") != case.request.object_id
                or record.get("lane_policy") != case.request.lane_policy
                or record.get("object_length") != len(case.request.data)
            ):
                errors.append(f"functional boundary manifest identity mismatch: slot {case.slot}")
            expected_publication = {
                "address": f"0x{P7_DESCRIPTOR_BASE + ring_slot * P7_DESCRIPTOR_BYTES + 12:08x}",
                "value": P7_DESCRIPTOR_READY,
                "published_after_body": True,
            }
            if record.get("ready_publication") != expected_publication:
                errors.append(f"functional boundary READY-publication contract mismatch: slot {case.slot}")
            for key, path, size in (
                ("input", bundle.directory / f"{prefix}_input.bin", len(case.request.data)),
                ("output_zero", bundle.directory / f"{prefix}_output_zero.bin", len(case.request.data)),
                ("trace_zero", bundle.directory / f"{prefix}_trace_zero.bin", case.trace_capacity * 64),
                ("descriptor_free", bundle.directory / f"{prefix}_descriptor_free.bin", P7_DESCRIPTOR_BYTES),
            ):
                errors.extend(_verify_manifest_record(record.get(key), path, size, f"boundary slot {case.slot} {key}"))
            if (
                len(boundary_batch_bytes[batch]) != P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH
                or boundary_batch_bytes[batch][
                    ring_slot * P7_DESCRIPTOR_BYTES : (ring_slot + 1) * P7_DESCRIPTOR_BYTES
                ] != case.request.pack()
                or struct.unpack_from("<I", boundary_batch_bytes[batch], ring_slot * P7_DESCRIPTOR_BYTES + 12)[0] != 0
            ):
                errors.append(f"functional boundary descriptor was pre-published: slot {case.slot}")
    checkpoint_record = manifest.get("functional_checkpoint")
    if bundle.functional_checkpoint is None:
        if checkpoint_record is not None:
            errors.append("non-functional bundle unexpectedly contains a 4KiB checkpoint")
    else:
        case = bundle.functional_checkpoint
        if not isinstance(checkpoint_record, dict):
            errors.append("functional 4KiB checkpoint manifest record missing")
        else:
            if (
                checkpoint_record.get("object_id") != 49
                or checkpoint_record.get("object_length") != 4096
                or checkpoint_record.get("lane_policy") != 3
                or checkpoint_record.get("expected_completion_sequence") != 49
                or checkpoint_record.get("ready_publication")
                != {
                    "address": f"0x{P7_DESCRIPTOR_BASE + 12:08x}",
                    "value": P7_DESCRIPTOR_READY,
                    "published_after_body": True,
                }
            ):
                errors.append("functional 4KiB checkpoint identity/publication contract mismatch")
            prefix = "functional_checkpoint_4k"
            for key, path, size in (
                ("input", bundle.directory / f"{prefix}_input.bin", len(case.request.data)),
                ("output_zero", bundle.directory / f"{prefix}_output_zero.bin", len(case.request.data)),
                ("trace_zero", bundle.directory / f"{prefix}_trace_zero.bin", case.trace_capacity * 64),
                ("descriptor_free", bundle.directory / f"{prefix}_descriptor_free.bin", P7_DESCRIPTOR_BYTES),
            ):
                errors.extend(_verify_manifest_record(checkpoint_record.get(key), path, size, f"functional checkpoint {key}"))
            descriptor_path = bundle.directory / f"{prefix}_descriptor_free.bin"
            if (
                not descriptor_path.is_file()
                or descriptor_path.stat().st_size != P7_DESCRIPTOR_BYTES
                or descriptor_path.read_bytes() != case.request.pack()
            ):
                errors.append("functional 4KiB checkpoint descriptor body mismatch")
    overflow_record = manifest.get("queue_overflow_candidate")
    if bundle.queue_overflow_candidate is None:
        if overflow_record is not None:
            errors.append("non-queue bundle unexpectedly contains an overflow candidate")
    else:
        case = bundle.queue_overflow_candidate
        if manifest.get("mode") != "queue" or not isinstance(overflow_record, dict):
            errors.append("queue overflow candidate manifest record missing")
        else:
            expected_contract = {
                "expected_result": "FULL",
                "required_occupancy": P7_QUEUE_DEPTH,
                "capacity": P7_QUEUE_DEPTH,
                "expected_ddr_write_count": 0,
                "ring_must_remain_byte_identical": True,
            }
            if overflow_record.get("admission_contract") != expected_contract:
                errors.append("queue overflow admission contract mismatch")
            if (
                overflow_record.get("candidate_index") != P7_QUEUE_DEPTH
                or overflow_record.get("object_id") != 9
                or case.request.object_id != 9
                or any(item.request.object_id == case.request.object_id for item in bundle.cases)
            ):
                errors.append("queue overflow candidate identity is not distinct object 9")
            prefix = "queue_overflow_candidate"
            for key, path, size in (
                ("input", bundle.directory / f"{prefix}_input.bin", len(case.request.data)),
                ("output_zero", bundle.directory / f"{prefix}_output_zero.bin", len(case.request.data)),
                ("trace_zero", bundle.directory / f"{prefix}_trace_zero.bin", case.trace_capacity * 64),
                ("descriptor_free", bundle.directory / f"{prefix}_descriptor_free.bin", P7_DESCRIPTOR_BYTES),
            ):
                errors.extend(_verify_manifest_record(overflow_record.get(key), path, size, f"queue overflow candidate {key}"))
            descriptor_path = bundle.directory / f"{prefix}_descriptor_free.bin"
            if descriptor_path.is_file() and descriptor_path.stat().st_size == P7_DESCRIPTOR_BYTES:
                descriptor = unpack_descriptor(descriptor_path.read_bytes())
                if descriptor_path.read_bytes() != case.request.pack() or (
                    descriptor["magic"] != P7_DESCRIPTOR_MAGIC
                    or descriptor["version"] != P7_RUNTIME_VERSION
                    or descriptor["command"] != P7_DESCRIPTOR_TRANSFER
                    or descriptor["status"] != 0
                    or descriptor["object_id"] != 9
                    or descriptor["session_epoch"] != case.request.session_epoch
                ):
                    errors.append("queue overflow candidate descriptor body is invalid")
    if errors:
        raise RuntimeError("execution bundle integrity failed: " + "; ".join(errors))


def snapshot_directory_files(directory: Path) -> dict[str, dict[str, Any]]:
    snapshot: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.is_symlink() or ".partial" in path.name:
            continue
        relative = path.relative_to(directory).as_posix()
        snapshot[relative] = {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return snapshot


def write_evidence_sha256_manifest(evidence_dir: Path) -> Path:
    manifest_path = evidence_dir / "p7_raw_evidence_sha256_manifest.json"
    records: list[dict[str, Any]] = []
    partials: list[str] = []
    for path in sorted(evidence_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(evidence_dir).as_posix()
        if path == manifest_path or path.name == "p7_ps_application_stage_summary.json":
            continue
        if path.is_symlink():
            raise RuntimeError(f"evidence manifest refuses symbolic link: {relative}")
        is_partial = ".partial" in path.name or ".write_partial" in path.name
        if is_partial:
            partials.append(relative)
        records.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "committed": not is_partial,
            }
        )
    atomic_write_json(
        manifest_path,
        {
            "schema": "rf-comm-p7-raw-evidence-sha256-v1",
            "generated_at_utc": now_utc(),
            "hardware_acceptance": "PENDING_HW",
            "record_count": len(records),
            "partial_file_count": len(partials),
            "partial_files": partials,
            "records": records,
        },
    )
    return manifest_path


def _profile_errors(args: argparse.Namespace) -> list[str]:
    if not args.profile:
        return ["P7 PS profile is required"]
    path = resolve_path(args.profile)
    if not path.is_file():
        return []
    try:
        profile = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"unable to parse P7 PS profile: {exc}"]
    errors: list[str] = []
    if profile.get("stage") != EXPECTED_PROFILE_STAGE[args.mode]:
        errors.append(f"profile stage must be {EXPECTED_PROFILE_STAGE[args.mode]}")
    if profile.get("network_required") is not False:
        errors.append("profile network_required must be false")
    if profile.get("motion_required") is not False:
        errors.append("profile motion_required must be false")
    if profile.get("lane_count") != 2 or str(profile.get("max_lane_mask", "")).lower() != "0x3":
        errors.append("profile must remain in the two-lane mask<=0x3 boundary")
    masks = profile.get("allowed_lane_masks")
    if not isinstance(masks, list) or {str(item).lower() for item in masks} != {"0x1", "0x2", "0x3"}:
        errors.append("profile allowed_lane_masks must be exactly 0x1,0x2,0x3")
    if profile.get("shutdown_on_exit") is not True:
        errors.append("profile shutdown_on_exit must be true")
    if profile.get("duty_guard_required") is not True:
        errors.append("profile duty_guard_required must be true")
    try:
        if int(profile.get("startup_wait_us", 0)) < 500:
            errors.append("profile startup_wait_us must be at least 500")
        hard_limit_us = int(profile.get("continuous_txd_high_hard_limit_us", 0))
        stuck_trip_us = int(profile.get("stuck_high_trip_us", 0))
        if hard_limit_us != 80:
            errors.append("profile continuous TXD-high hard limit must be exactly the canonical 80 us")
        if stuck_trip_us != 10:
            errors.append("profile stuck-high trip must be exactly the canonical safe 10 us")
        if int(profile.get("max_runtime_sec", 0)) < args.max_runtime_sec:
            errors.append("profile max_runtime_sec is lower than requested")
    except (TypeError, ValueError):
        errors.append("profile runtime/startup fields must be integers")
    if args.mode == "stationary":
        if profile.get("calibration_window_sec") != CALIBRATION_SEC:
            errors.append("stationary profile calibration window must be exactly 300 seconds")
        if profile.get("acceptance_window_sec") != ACCEPTANCE_SEC:
            errors.append("stationary profile acceptance window must be exactly 1500 seconds")
        if profile.get("calibration_is_part_of_final_30min_run") is not True:
            errors.append("stationary calibration must be part of the final 30-minute run")
        if profile.get("sample_interval_sec") != 30:
            errors.append("stationary profile sample interval must be exactly 30 seconds")
    return errors


def _active_profile_errors(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    active_path = resolve_path(args.active_profile)
    promotion_path = resolve_path(args.lane1_promotion_summary)
    if active_path != ACTIVE_PROFILE_DEFAULT.resolve(strict=False):
        errors.append(f"active profile must be canonical: {ACTIVE_PROFILE_DEFAULT}")
    if promotion_path != LANE1_PROMOTION_DEFAULT.resolve(strict=False):
        errors.append(f"lane1 promotion summary must be canonical: {LANE1_PROMOTION_DEFAULT}")
    for label, path, expected in (
        ("active profile", active_path, args.active_profile_sha256),
        ("lane1 promotion summary", promotion_path, args.lane1_promotion_summary_sha256),
    ):
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
        elif not SHA256_RE.fullmatch(expected or ""):
            errors.append(f"{label} expected SHA256 is missing or invalid")
        elif sha256_file(path) != expected.lower():
            errors.append(f"{label} SHA256 mismatch")
    if errors:
        return errors
    try:
        active = json.loads(active_path.read_text(encoding="utf-8", errors="strict"))
        promotion = json.loads(promotion_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"unable to parse active-profile lane1 promotion boundary: {exc}"]
    active_promotion = active.get("lane1_reliability_promotion")
    if active.get("default_no_hardware") is not True:
        errors.append("active profile default_no_hardware must remain true")
    if active.get("lane1_reliable_enabled") is not True or not isinstance(active_promotion, dict):
        errors.append("active profile does not enable a promoted reliable lane1")
        active_promotion = {}
    if active_promotion.get("status") != "PASS":
        errors.append("active profile lane1 promotion status is not PASS")
    promotion_source_commit = str(active_promotion.get("source_commit", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{40}", promotion_source_commit):
        errors.append("active profile lane1 promotion source_commit must be a full 40-hex commit")
    elif not re.fullmatch(r"[0-9a-fA-F]{40}", str(args.source_commit or "")):
        errors.append("authorized source_commit must be a full 40-hex commit")
    else:
        try:
            existence = subprocess.run(
                ["git", "cat-file", "-e", f"{promotion_source_commit}^{{commit}}"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
            )
            ancestry = subprocess.run(
                ["git", "merge-base", "--is-ancestor", promotion_source_commit, str(args.source_commit).lower()],
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=30,
            ) if existence.returncode == 0 else None
        except (OSError, subprocess.TimeoutExpired) as exc:
            errors.append(f"unable to validate lane1 promotion commit ancestry: {type(exc).__name__}")
        else:
            if existence.returncode != 0:
                errors.append("active profile lane1 promotion source_commit is unknown to this repository")
            elif ancestry is None or ancestry.returncode != 0:
                errors.append("active profile lane1 promotion source_commit is not an ancestor of the authorized source commit")
    if normalized_path(active_promotion.get("evidence", "")) != normalized_path(promotion_path):
        errors.append("active profile lane1 promotion evidence path mismatch")
    if active_promotion.get("requires_fresh_p7_regression_before_acceptance") is not True:
        errors.append("active profile must retain the fresh-P7-regression acceptance boundary")
    if promotion.get("P7_LANE1_RELIABILITY_PROMOTION_GATE") != "PASS":
        errors.append("lane1 promotion summary gate is not PASS")
    if str(promotion.get("source_commit", "")).lower() != promotion_source_commit:
        errors.append("lane1 promotion summary source_commit is not bound to the active profile promotion commit")
    if promotion.get("hardware_actions_executed") is not False or promotion.get("source_evidence_contains_hardware_actions") is not True:
        errors.append("lane1 promotion summary hardware-evidence boundary is malformed")
    checks = promotion.get("checks")
    if not isinstance(checks, dict) or not checks or any(value is not True for value in checks.values()):
        errors.append("lane1 promotion summary contains a missing/non-PASS check")
    sources = promotion.get("sources")
    if not isinstance(sources, dict) or not sources:
        errors.append("lane1 promotion summary source evidence is missing")
    else:
        for key, record in sources.items():
            if not isinstance(record, dict):
                errors.append(f"lane1 promotion source record malformed: {key}")
                continue
            source_path = resolve_path(record.get("path", ""))
            expected = str(record.get("sha256", "")).lower()
            if not SHA256_RE.fullmatch(expected) or not source_path.is_file() or sha256_file(source_path) != expected:
                errors.append(f"lane1 promotion source evidence mismatch: {key}")
    return errors


def _immutable_errors(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    definitions = (
        ("P6 PS bitstream", args.bitstream, args.bitstream_sha256, P6_IMMUTABLE_DIR, "p6_ps_dynamic_transport_", ".bit"),
        ("P6 PS XSA", args.xsa, args.xsa_sha256, P6_IMMUTABLE_DIR, "p6_ps_dynamic_transport_", ".xsa"),
        ("P7 ELF", args.elf, args.elf_sha256, P7_IMMUTABLE_DIR, "p7_runtime_", ".elf"),
    )
    for label, value, expected, parent, prefix, suffix in definitions:
        if not value or not expected:
            errors.append(f"{label} requires an explicit path and SHA256")
            continue
        path = resolve_path(value)
        try:
            path.relative_to(parent.resolve(strict=False))
        except ValueError:
            errors.append(f"{label} must be under immutable directory: {parent}")
            continue
        expected_name = f"{prefix}{expected.lower()}{suffix}"
        if path.name.casefold() != expected_name.casefold():
            errors.append(f"{label} filename must bind its SHA256: expected={expected_name} observed={path.name}")
    if args.shutdown_bitstream and resolve_path(args.shutdown_bitstream) != CANONICAL_SHUTDOWN_BIT.resolve(strict=False):
        errors.append(f"shutdown bitstream must be canonical: {CANONICAL_SHUTDOWN_BIT}")
    return errors


def _elf_alloc_image_end(path: Path) -> int:
    """Return the highest end-exclusive address of an ELF32 little-endian SHF_ALLOC section."""

    raw = path.read_bytes()
    if len(raw) < 52 or raw[:4] != b"\x7fELF" or raw[4] != 1 or raw[5] != 1:
        raise ValueError("P7 ELF is not ELF32 little-endian")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", raw, 0)
    section_offset = header[6]
    section_entry_size = header[11]
    section_count = header[12]
    if section_entry_size < 40 or section_count < 1:
        raise ValueError("P7 ELF section table is missing")
    table_end = section_offset + section_entry_size * section_count
    if section_offset < 52 or table_end > len(raw) or table_end < section_offset:
        raise ValueError("P7 ELF section table is out of bounds")
    image_end = 0
    for index in range(section_count):
        offset = section_offset + index * section_entry_size
        section = struct.unpack_from("<IIIIIIIIII", raw, offset)
        flags = section[2]
        address = section[3]
        size = section[5]
        if flags & 0x2:
            end = address + size
            if end < address:
                raise ValueError("P7 ELF allocated section address overflow")
            image_end = max(image_end, end)
    if image_end == 0:
        raise ValueError("P7 ELF contains no allocated sections")
    return image_end


def _summary_errors(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    for label, path_value, expected_sha in (
        ("P6 build summary", args.p6_build_summary, args.p6_build_summary_sha256),
        ("P7 build summary", args.p7_build_summary, args.p7_build_summary_sha256),
    ):
        path = resolve_path(path_value)
        if not path.is_file():
            errors.append(f"{label} missing: {path}")
            continue
        if not SHA256_RE.fullmatch(expected_sha or ""):
            errors.append(f"{label} expected SHA256 is missing or invalid")
        elif sha256_file(path) != expected_sha.lower():
            errors.append(f"{label} SHA256 mismatch")
    p6_path = resolve_path(args.p6_build_summary)
    if p6_path.is_file():
        try:
            summary = json.loads(p6_path.read_text(encoding="utf-8"))
            if (
                summary.get("P6_PS_CANDIDATE_BUILD") != "PASS"
                or summary.get("returncode") != 0
                or summary.get("timing_met") is not True
                or summary.get("drc_clean") is not True
                or summary.get("ethernet_used") is not False
                or summary.get("motion_used") is not False
            ):
                errors.append("P6 build summary semantic build/safety gates are not PASS")
            for key, path_value, expected in (
                ("bit", args.bitstream, args.bitstream_sha256),
                ("xsa", args.xsa, args.xsa_sha256),
            ):
                artifact = summary["artifacts"][key]
                if normalized_path(artifact["immutable"]) != normalized_path(path_value) or artifact["sha256"].lower() != expected.lower():
                    errors.append(f"P6 build summary {key} artifact does not match requested immutable artifact")
            active_input = summary["inputs"]["active_profile"]
            # The immutable P6 PL candidate was built before lane1 was promoted.
            # A current active-profile hash mismatch is allowed only through the
            # separately hash-bound P5/P6 lane1 promotion gate validated above;
            # it does not require or authorize a P6 PL rebuild.
            if normalized_path(active_input["path"]) != normalized_path(ACTIVE_PROFILE_DEFAULT) or not SHA256_RE.fullmatch(
                str(active_input["sha256"])
            ):
                errors.append("P6 build summary historical active-profile binding is malformed")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"unable to validate P6 build summary: {exc}")
    p7_path = resolve_path(args.p7_build_summary)
    if p7_path.is_file():
        try:
            summary = json.loads(p7_path.read_text(encoding="utf-8"))
            try:
                mailbox_base = int(str(summary.get("mailbox_base", "")), 0)
                ocm_image_end = int(str(summary.get("ocm_image_end", "")), 0)
            except ValueError:
                mailbox_base = -1
                ocm_image_end = -1
            if (
                summary.get("P7_PS_RUNTIME_BUILD") != "PASS"
                or summary.get("returncode") != 0
                or summary.get("syntax_only") is not False
                or summary.get("mailbox_overlap") is not False
                or summary.get("linker_ocm_hard_boundary_0x20000") is not True
                or mailbox_base != P7_MAILBOX_BASE
                or not 0 < ocm_image_end < mailbox_base
                or summary.get("queue_depth") != P7_QUEUE_DEPTH
                or summary.get("max_object_bytes") != MAX_OBJECT_BYTES
                or summary.get("counts_per_second") != P7_COUNTS_PER_SECOND
                or summary.get("counts_per_second_definition") != "XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ/2"
                or summary.get("network_used") is not False
                or summary.get("hardware_actions_executed") is not False
                or summary.get("HARDWARE_ACCEPTANCE") != "PENDING_HW"
            ):
                errors.append("P7 build summary semantic runtime/mailbox gates are not PASS")
            if normalized_path(summary.get("xsa", "")) != normalized_path(args.xsa) or str(summary.get("xsa_sha256", "")).lower() != args.xsa_sha256.lower():
                errors.append("P7 build summary XSA does not match the authorized P6 XSA")
            artifact = summary["artifacts"]["elf"]
            if normalized_path(artifact["immutable"]) != normalized_path(args.elf) or artifact["sha256"].lower() != args.elf_sha256.lower():
                errors.append("P7 build summary ELF does not match requested immutable ELF")
            linker_map = summary["artifacts"]["linker_map"]
            linker_path = resolve_path(linker_map["immutable"])
            linker_sha = str(linker_map["sha256"]).lower()
            expected_linker_name = f"p7_runtime_{linker_sha}.map"
            try:
                linker_path.relative_to(P7_IMMUTABLE_DIR.resolve(strict=False))
            except ValueError:
                errors.append("P7 linker map must be under the immutable P7 artifact directory")
            if (
                not SHA256_RE.fullmatch(linker_sha)
                or linker_path.name.casefold() != expected_linker_name.casefold()
                or not linker_path.is_file()
                or sha256_file(linker_path) != linker_sha
            ):
                errors.append("P7 linker-map immutable path/hash binding is invalid")
            else:
                map_text = linker_path.read_text(encoding="utf-8", errors="replace")
                if not re.search(
                    r"(?m)^ps7_ram_0\s+0x0+\s+0x0*20000(?:\s|$)",
                    map_text,
                ):
                    errors.append("P7 linker map does not hard-limit ps7_ram_0 to exactly 0x20000 bytes")
            bsp_parameters = summary["artifacts"]["bsp_xparameters"]
            bsp_parameters_path = resolve_path(bsp_parameters["immutable"])
            bsp_parameters_sha = str(bsp_parameters["sha256"]).lower()
            if (
                not SHA256_RE.fullmatch(bsp_parameters_sha)
                or not bsp_parameters_path.is_file()
                or sha256_file(bsp_parameters_path) != bsp_parameters_sha
                or bsp_parameters_path.name.casefold() != f"p7_bsp_xparameters_{bsp_parameters_sha}.h".casefold()
            ):
                errors.append("P7 BSP timer-constant source is not immutable/hash-bound")
            else:
                bsp_text = bsp_parameters_path.read_text(encoding="utf-8", errors="strict")
                cpu_clock_match = re.search(
                    r"(?m)^#define\s+XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ\s+([0-9]+)\s*$",
                    bsp_text,
                )
                if cpu_clock_match is None or int(cpu_clock_match.group(1)) // 2 != P7_COUNTS_PER_SECOND:
                    errors.append("P7 BSP COUNTS_PER_SECOND does not equal the runner's exact timer constant")
            for inspection_name in ("size", "symbols", "sections"):
                inspection = summary["inspection"][inspection_name]
                inspection_path = resolve_path(inspection["path"])
                if inspection.get("returncode") != 0 or not inspection_path.is_file():
                    errors.append(f"P7 ELF inspection is missing or failed: {inspection_name}")
            elf_path = resolve_path(args.elf)
            if not elf_path.is_file():
                errors.append("authorized P7 ELF is missing for direct OCM-boundary inspection")
            elif _elf_alloc_image_end(elf_path) != ocm_image_end:
                errors.append("P7 ELF allocated image end does not match the build summary OCM boundary")
            for source, expected in summary["sources"].items():
                source_path = resolve_path(source)
                if not source_path.is_file() or sha256_file(source_path) != str(expected).lower():
                    errors.append(f"P7 ELF source provenance mismatch: {source}")
            ps7_path = resolve_path(args.ps7_init)
            expected_ps7_parent = (ROOT / "build" / "p7_ps_vitis_workspace" / "p7_platform" / "hw").resolve(strict=False)
            if ps7_path.parent != expected_ps7_parent or ps7_path.name.casefold() != "ps7_init.tcl":
                errors.append("PS7 init must come from the P7 platform generated from the authorized XSA")
            elif not any(sha256_file(item) == args.xsa_sha256.lower() for item in ps7_path.parent.glob("*.xsa") if item.is_file()):
                errors.append("PS7 init platform directory does not contain the authorized XSA content")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"unable to validate P7 build summary: {exc}")
    return errors


def _authorization_extension_errors(args: argparse.Namespace) -> list[str]:
    auth_path = resolve_path(args.authorization_file) if args.authorization_file else None
    if auth_path is None or not auth_path.is_file():
        return []
    try:
        fields, _, _ = parse_authorization_file(auth_path)
    except (OSError, UnicodeError):
        return []
    errors: list[str] = []
    required = (
        ("PS7_INIT_PATH", args.ps7_init),
        ("PS7_INIT_SHA256", args.ps7_init_sha256),
        ("P6_PS_BUILD_SUMMARY_PATH", args.p6_build_summary),
        ("P6_PS_BUILD_SUMMARY_SHA256", args.p6_build_summary_sha256),
        ("P7_PS_BUILD_SUMMARY_PATH", args.p7_build_summary),
        ("P7_PS_BUILD_SUMMARY_SHA256", args.p7_build_summary_sha256),
        ("P7_INPUT_PATH", args.input_file),
        ("P7_INPUT_SHA256", args.input_sha256),
        ("P7_PS_MODE", args.mode),
        ("P7_PS_CORE_READINESS", "PASS"),
        ("P7_PS_CORE_READINESS_PATH", args.core_readiness_attestation),
        ("P7_PS_CORE_READINESS_SHA256", args.core_readiness_attestation_sha256),
        ("ACTIVE_PROFILE_PATH", args.active_profile),
        ("ACTIVE_PROFILE_SHA256", args.active_profile_sha256),
        ("P7_LANE1_PROMOTION_SUMMARY_PATH", args.lane1_promotion_summary),
        ("P7_LANE1_PROMOTION_SUMMARY_SHA256", args.lane1_promotion_summary_sha256),
        ("P7_FROZEN_SHUTDOWN_PATH", str(frozen_shutdown_path(args))),
        ("P7_FROZEN_SHUTDOWN_SHA256", args.shutdown_bitstream_sha256),
        ("P7_COUNTS_PER_SECOND", str(P7_COUNTS_PER_SECOND)),
    )
    for key, expected in required:
        observed = fields.get(key)
        if observed is None:
            errors.append(f"authorization extension field missing: {key}")
        elif key.endswith("_PATH"):
            if normalized_path(observed) != normalized_path(expected):
                errors.append(f"authorization extension path mismatch: {key}")
        elif observed.casefold() != str(expected).casefold():
            errors.append(f"authorization extension field mismatch: {key}")
    return errors


def validate_core_readiness(args: argparse.Namespace) -> dict[str, Any]:
    path = resolve_path(args.core_readiness_attestation)
    report: dict[str, Any] = {
        "path": str(path),
        "expected_sha256": args.core_readiness_attestation_sha256 or "MISSING",
        "actual_sha256": "MISSING",
        "status": "BLOCKED",
        "errors": [],
    }
    errors: list[str] = report["errors"]
    if not path.is_file():
        errors.append(
            "P7 PS core hardware-readiness attestation is missing; current core must not reach hardware execution"
        )
        return report
    actual = sha256_file(path)
    report["actual_sha256"] = actual
    if not SHA256_RE.fullmatch(args.core_readiness_attestation_sha256 or ""):
        errors.append("core-readiness attestation expected SHA256 is missing or invalid")
    elif actual != args.core_readiness_attestation_sha256.lower():
        errors.append("core-readiness attestation SHA256 mismatch")
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"unable to parse core-readiness attestation: {exc}")
        return report
    report["attestation"] = data
    if data.get("schema") != "rf-comm-p7-ps-core-hardware-readiness-v1":
        errors.append("core-readiness attestation schema mismatch")
    if data.get("P7_PS_CORE_HARDWARE_READINESS") != "PASS":
        errors.append("P7_PS_CORE_HARDWARE_READINESS must be PASS")
    if data.get("hardware_actions_executed") is not False:
        errors.append("core-readiness attestation must be an offline result")
    checks = data.get("checks")
    if not isinstance(checks, dict):
        errors.append("core-readiness attestation checks object missing")
    else:
        for key in CORE_READINESS_CHECKS:
            if checks.get(key) is not True:
                errors.append(f"core-readiness check is not true: {key}")
    sources = data.get("sources")
    if not isinstance(sources, dict):
        errors.append("core-readiness source hashes missing")
    else:
        fingerprint = hashlib.sha256()
        for source in CORE_READINESS_SOURCES:
            expected = sources.get(source)
            source_path = resolve_path(source)
            if not SHA256_RE.fullmatch(str(expected or "")):
                errors.append(f"core-readiness source hash missing: {source}")
            elif not source_path.is_file() or sha256_file(source_path) != str(expected).lower():
                errors.append(f"core-readiness source hash mismatch: {source}")
            fingerprint.update(source.encode("utf-8"))
            fingerprint.update(b"\0")
            fingerprint.update(str(expected or "").lower().encode("ascii", errors="replace"))
            fingerprint.update(b"\n")
        report["source_fingerprint"] = fingerprint.hexdigest()
        if fingerprint.hexdigest() == KNOWN_UNSAFE_CORE_FINGERPRINT:
            errors.append("audited current P7 PS core snapshot has unresolved P0 safety blockers and cannot reach hardware")
    report["status"] = "PASS" if not errors else "BLOCKED"
    return report


def _stage_validation(args: argparse.Namespace, core_readiness: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(_profile_errors(args))
    errors.extend(_active_profile_errors(args))
    errors.extend(_immutable_errors(args))
    errors.extend(_summary_errors(args))
    errors.extend(_authorization_extension_errors(args))
    errors.extend(core_readiness["errors"])
    if not STAGE_NAME_RE.fullmatch(args.stage_name or ""):
        errors.append("stage name contains unsupported characters")
    if args.mode == "stationary":
        if args.max_runtime_sec != MAX_SERVICE_RUNTIME_SEC:
            errors.append("stationary max runtime must be exactly 1800 seconds")
        if args.calibration_sec != CALIBRATION_SEC or args.acceptance_sec != ACCEPTANCE_SEC:
            errors.append("stationary windows must be exactly 300 calibration + 1500 acceptance seconds")
        if args.calibration_sec + args.acceptance_sec != args.max_runtime_sec:
            errors.append("stationary calibration plus acceptance must equal 1800 seconds")
        if args.idle_deadline_margin_sec != MAX_IDLE_MARGIN_SEC:
            errors.append("stationary idle deadline margin must be exactly 60 seconds")
        if args.max_runtime_sec - args.idle_deadline_margin_sec <= args.calibration_sec:
            errors.append("stationary scheduling cutoff must remain after calibration")
        if args.sample_interval_sec != 30:
            errors.append("stationary sample interval must be exactly 30 seconds")
    else:
        if not 1 <= args.max_runtime_sec <= 900:
            errors.append("non-stationary P7 PS runtime must be in 1..900 seconds")
        if args.calibration_sec != 0 or args.acceptance_sec != 0:
            errors.append("non-stationary modes must not claim calibration/acceptance windows")
    if not 1 <= args.sample_interval_sec <= 60:
        errors.append("sample interval must be in 1..60 seconds")
    if not 100_000 <= args.jtag_frequency_hz <= 5_000_000:
        errors.append("JTAG frequency must be in 100000..5000000 Hz")
    if not 1 <= args.preflight_timeout_sec <= 300:
        errors.append("preflight timeout must be in 1..300 seconds")
    if not 1 <= args.shutdown_timeout_sec <= 300:
        errors.append("shutdown timeout must be in 1..300 seconds")
    if args.mode == "stationary" and args.stationary_object_bytes != 64 * 1024:
        errors.append("stationary base object size must be exactly 65536 bytes")
    if resolve_path(args.abort_file or str(DEFAULT_ABORT_FILE)) != DEFAULT_ABORT_FILE.resolve(strict=False):
        errors.append(f"abort file must be canonical: {DEFAULT_ABORT_FILE}")
    for label, value, expected in (
        ("PS7 init", args.ps7_init, args.ps7_init_sha256),
        ("input file", args.input_file, args.input_sha256),
    ):
        path = resolve_path(value) if value else None
        if path is None or not path.is_file():
            errors.append(f"{label} missing: {path or 'MISSING'}")
        elif not SHA256_RE.fullmatch(expected or ""):
            errors.append(f"{label} expected SHA256 is missing or invalid")
        elif sha256_file(path) != expected.lower():
            errors.append(f"{label} SHA256 mismatch")
        elif label == "input file" and path.stat().st_size > MAX_OBJECT_BYTES:
            errors.append(f"input file exceeds P7 maximum object size: {path.stat().st_size}")
    xsdb = Path(args.xsdb_path).resolve(strict=False) if args.xsdb_path else None
    if xsdb is None or not xsdb.is_file():
        errors.append(f"XSDB executable missing: {xsdb or 'MISSING'}")
    if not PS_EXECUTE_TCL.is_file():
        errors.append(f"P7 PS execute Tcl missing: {PS_EXECUTE_TCL}")
    if not SHUTDOWN_TCL.is_file():
        errors.append(f"P7 shutdown Tcl missing: {SHUTDOWN_TCL}")
    return errors


def _verify_hash(path_value: str, expected: str, label: str) -> str | None:
    path = resolve_path(path_value)
    if not path.is_file():
        return f"{label} disappeared: {path}"
    actual = sha256_file(path)
    return None if actual == expected.lower() else f"{label} hash changed: expected={expected.lower()} actual={actual}"


def _atomic_process(
    *,
    name: str,
    command: list[str],
    evidence_dir: Path,
    timeout_sec: int,
    abort_file: Path,
    watch_abort: bool,
    stationary_active_watchdog: bool = False,
) -> process_support.ProcessResult:
    stdout_final = evidence_dir / f"{name}.stdout.log"
    stderr_final = evidence_dir / f"{name}.stderr.log"
    stdout_partial = Path(str(stdout_final) + ".partial")
    stderr_partial = Path(str(stderr_final) + ".partial")
    for path in (stdout_partial, stderr_partial):
        if path.exists():
            path.unlink()
    started_at_utc = now_utc()
    if stationary_active_watchdog:
        result = _run_stationary_watchdog_process(
            name=name,
            command=command,
            stdout_path=stdout_partial,
            stderr_path=stderr_partial,
            abort_file=abort_file,
            watch_abort=watch_abort,
        )
    else:
        result = process_support.run_bounded_process(
            name=name,
            command=command,
            stdout_path=stdout_partial,
            stderr_path=stderr_partial,
            timeout_sec=timeout_sec,
            abort_file=abort_file,
            watch_abort=watch_abort,
        )
    if stdout_partial.exists():
        os.replace(stdout_partial, stdout_final)
    else:
        atomic_write_text(stdout_final, "")
    if stderr_partial.exists():
        os.replace(stderr_partial, stderr_final)
    else:
        atomic_write_text(stderr_final, "")
    result.stdout_path = str(stdout_final)
    result.stderr_path = str(stderr_final)
    result.argv = list(command)
    result.started_at_utc = started_at_utc
    result.ended_at_utc = now_utc()
    return result


def _run_stationary_watchdog_process(
    *,
    name: str,
    command: list[str],
    stdout_path: Path,
    stderr_path: Path,
    abort_file: Path,
    watch_abort: bool,
) -> process_support.ProcessResult:
    """Bound candidate-active time independently from safe post-run evidence reap."""

    process_support._reject_batch_metacharacters(command)
    started = time.monotonic()
    started_at_utc = now_utc()
    active_started: float | None = None
    safe_terminal_seen: float | None = None
    timed_out = False
    abort_seen = False
    interrupted = False
    tree_terminated = False
    process_tree_reaped = False
    watchdog_reason = ""
    launch_error = ""
    raw_returncode: int | None = None
    process: subprocess.Popen[Any] | None = None
    popen_args: dict[str, Any] = {"cwd": ROOT, "text": True, "shell": False}
    if os.name == "nt":
        popen_args["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_args["start_new_session"] = True
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            try:
                process = process_support.launch_contained_process(
                    command, stdout=stdout_handle, stderr=stderr_handle, popen_args=popen_args
                )
                while process.poll() is None:
                    now = time.monotonic()
                    stdout_handle.flush()
                    live_text = (
                        stdout_path.read_text(encoding="utf-8", errors="replace")
                        if stdout_path.is_file()
                        else ""
                    )
                    if active_started is None and "P7_STATIONARY_SERVICE_READY_ACTIVE=1" in live_text:
                        active_started = now
                    if safe_terminal_seen is None and (
                        "P7_STATIONARY_SERVICE_TERMINAL_OBSERVED=1" in live_text
                        or "P7_SAMPLE_00060_SAFE_TERMINAL_STATE=1" in live_text
                    ):
                        safe_terminal_seen = now
                    if watch_abort and abort_file.exists():
                        abort_seen = True
                        watchdog_reason = "operator_abort"
                        break
                    if active_started is None and now - started >= STATIONARY_SETUP_WATCHDOG_SEC:
                        timed_out = True
                        watchdog_reason = "candidate_setup_marker_timeout"
                        break
                    if (
                        active_started is not None
                        and safe_terminal_seen is None
                        and now - active_started
                        >= MAX_SERVICE_RUNTIME_SEC + STATIONARY_ACTIVE_WATCHDOG_TOLERANCE_SEC
                    ):
                        timed_out = True
                        watchdog_reason = "stationary_active_window_exceeded"
                        break
                    if safe_terminal_seen is not None and now - safe_terminal_seen >= POST_SAFE_REAP_GRACE_SEC:
                        timed_out = True
                        watchdog_reason = "post_safe_evidence_reap_timeout"
                        break
                    time.sleep(0.10)
            except KeyboardInterrupt:
                interrupted = True
                watchdog_reason = "keyboard_interrupt"
            except BaseException as exc:
                launch_error = f"{type(exc).__name__}: {exc}"
                watchdog_reason = "wrapper_exception"
            finally:
                if process is not None:
                    if process.poll() is None and (timed_out or abort_seen or interrupted or launch_error):
                        tree_terminated = (
                            process_support.terminate_process_tree(process) or tree_terminated
                        )
                    try:
                        raw_returncode = process.wait(timeout=10)
                    except (subprocess.TimeoutExpired, OSError):
                        tree_terminated = (
                            process_support.terminate_process_tree(process) or tree_terminated
                        )
                        try:
                            raw_returncode = process.wait(timeout=10)
                        except (subprocess.TimeoutExpired, OSError):
                            raw_returncode = process.poll()
                    process_tree_reaped = (
                        raw_returncode is not None
                        and process.poll() is not None
                        and process_support.verify_process_tree_reaped(process)
                    )
    except BaseException as exc:
        launch_error = launch_error or f"{type(exc).__name__}: {exc}"
        watchdog_reason = watchdog_reason or "launch_error"
    finally:
        if process is not None and process.poll() is None:
            tree_terminated = process_support.terminate_process_tree(process) or tree_terminated
            try:
                raw_returncode = process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                raw_returncode = process.poll()
            process_tree_reaped = (
                raw_returncode is not None
                and process.poll() is not None
                and process_support.verify_process_tree_reaped(process)
            )
        elif process is None:
            process_tree_reaped = True

    if launch_error:
        try:
            with stderr_path.open("a", encoding="utf-8") as handle:
                handle.write(f"wrapper process failure: {launch_error}\n")
        except OSError:
            pass
    if interrupted or abort_seen:
        returncode = 130
    elif timed_out:
        returncode = 124
    elif launch_error:
        returncode = 127
    elif not process_tree_reaped or raw_returncode is None:
        returncode = 125
    else:
        returncode = int(raw_returncode)
    containment = process_support.containment_record(process)
    result = process_support.ProcessResult(
        name=name,
        returncode=returncode,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        elapsed_seconds=round(time.monotonic() - started, 6),
        argv=list(command),
        started_at_utc=started_at_utc,
        ended_at_utc=now_utc(),
        timed_out=timed_out,
        abort_seen=abort_seen,
        interrupted=interrupted,
        process_tree_terminated=tree_terminated,
        process_tree_reaped=process_tree_reaped,
        containment_kind=str(containment["containment_kind"]),
        containment_assigned=bool(containment["containment_assigned"]),
        containment_closed=bool(containment["containment_closed"]),
        descendant_count_after=int(containment["descendant_count_after"]),
        launch_error=launch_error,
    )
    result.watchdog_reason = watchdog_reason
    result.active_marker_seen = active_started is not None
    result.safe_terminal_marker_seen = safe_terminal_seen is not None
    return result


def _process_record(result: process_support.ProcessResult) -> dict[str, Any]:
    return {
        **asdict(result),
        "argv": list(getattr(result, "argv", [])),
        "started_at_utc": getattr(result, "started_at_utc", "UNKNOWN"),
        "ended_at_utc": getattr(result, "ended_at_utc", "UNKNOWN"),
        "watchdog_reason": getattr(result, "watchdog_reason", ""),
        "active_marker_seen": getattr(result, "active_marker_seen", False),
        "safe_terminal_marker_seen": getattr(result, "safe_terminal_marker_seen", False),
    }


def _atomic_result_path(final_path: Path) -> Path:
    partial = Path(str(final_path) + ".partial")
    for path in (final_path, partial):
        if path.exists():
            path.unlink()
    return partial


def _promote_result(partial: Path, final: Path) -> None:
    if partial.is_file():
        os.replace(partial, final)


def frozen_shutdown_path(args: argparse.Namespace) -> Path:
    digest = args.shutdown_bitstream_sha256.lower() if SHA256_RE.fullmatch(args.shutdown_bitstream_sha256 or "") else "INVALID"
    return FROZEN_SHUTDOWN_DIR / f"p7_frozen_shutdown_{digest}.bit"


def freeze_shutdown_bit(args: argparse.Namespace) -> tuple[Path, bytes]:
    source = resolve_path(args.shutdown_bitstream)
    expected = args.shutdown_bitstream_sha256.lower()
    payload = source.read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise RuntimeError(f"shutdown bitstream changed before freeze: expected={expected} actual={actual}")
    destination = frozen_shutdown_path(args)
    if destination.exists() and (not destination.is_file() or destination.is_symlink()):
        raise RuntimeError(f"frozen shutdown destination is not a regular file: {destination}")
    if not destination.is_file() or sha256_file(destination) != expected:
        atomic_write_bytes(destination, payload)
    if destination.stat().st_size != len(payload) or sha256_file(destination) != expected:
        raise RuntimeError("content-addressed frozen shutdown copy verification failed")
    return destination, payload


def restore_frozen_shutdown(path: Path, payload: bytes, expected: str) -> None:
    if path.exists() and (not path.is_file() or path.is_symlink()):
        raise RuntimeError(f"frozen shutdown path became unsafe: {path}")
    if not path.is_file() or sha256_file(path) != expected.lower():
        atomic_write_bytes(path, payload)
    if sha256_file(path) != expected.lower():
        raise RuntimeError("unable to restore verified frozen shutdown image")


def build_shutdown_command(args: argparse.Namespace, result_path: Path, shutdown_bit: Path | None = None) -> list[str]:
    shutdown_bit = shutdown_bit or resolve_path(args.shutdown_bitstream)
    return [
        str(Path(args.vivado_path).resolve(strict=False)),
        "-mode",
        "batch",
        "-source",
        str(SHUTDOWN_TCL),
        "-tclargs",
        str(ROOT),
        "SHUTDOWN",
        str(resolve_path(args.authorization_file)),
        args.board_id,
        args.expected_part,
        args.expected_target,
        args.hw_server_url,
        str(args.jtag_frequency_hz),
        str(shutdown_bit),
        "-",
        "-",
        str(result_path),
        "0x43c00000",
        "1",
        str(args.max_runtime_sec),
        str(shutdown_bit),
    ]


def build_ps_command(
    args: argparse.Namespace,
    bundle: StageBundle,
    preflight_result: Path,
    raw_result: Path,
) -> list[str]:
    return [
        str(Path(args.xsdb_path).resolve(strict=False)),
        str(PS_EXECUTE_TCL),
        str(ROOT),
        str(resolve_path(args.authorization_file)),
        str(preflight_result),
        str(resolve_path(args.bitstream)),
        str(resolve_path(args.elf)),
        str(resolve_path(args.ps7_init)),
        str(bundle.directory),
        str(bundle.plan_path),
        str(raw_result),
        args.hw_server_url,
        args.board_id,
        args.expected_part,
        args.expected_target,
        str(args.max_runtime_sec),
        args.mode,
        str(args.idle_deadline_margin_sec),
        str(resolve_path(args.shutdown_bitstream)),
        str(P7_COUNTS_PER_SECOND),
    ]


def evaluate_ps_process(
    returncode: int,
    stdout: str,
    raw_text: str,
    *,
    mode: str,
    target: str,
    part: str,
    board_id: str = "",
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    if returncode != 0:
        failures.append(f"PS stage process returned nonzero exit code: {returncode}")
    markers = parse_markers(raw_text)
    expected = {
        "P7_PS_STAGE_RESULT": "PASS",
        "P7_PS_CANDIDATE_PROGRAMMED": "1",
        "P7_PS_ELF_DOWNLOADED": "1",
        "P7_PS_MODE": mode,
        "P7_HW_TARGET": target,
        "P7_HW_PART": part,
        "P7_XSDB_LIVE_DEVICE_MATCH": "1",
        "P7_XSDB_TARGET_SELECTION": "EXACT_CABLE_DEVICE_IDCODE_AND_UNIQUE_NODE_IDS",
    }
    for key, value in expected.items():
        if markers.get(key) != value:
            failures.append(f"PS stage marker mismatch: {key} expected={value} observed={markers.get(key, 'MISSING')}")
    if board_id and markers.get("P7_XSDB_LIVE_BOARD_ID") != board_id:
        failures.append("PS stage live board/cable serial marker mismatch")
    live_idcode = markers.get("P7_XSDB_LIVE_IDCODE", "")
    preflight_idcode = markers.get("P7_XSDB_PREFLIGHT_IDCODE", "")
    if not re.fullmatch(r"(?:0x)?[0-9A-Fa-f]+", preflight_idcode) or not re.fullmatch(
        r"(?:0x)?[0-9A-Fa-f]+", live_idcode
    ):
        failures.append("PS stage live/preflight IDCODE marker is missing or malformed")
    elif int(live_idcode, 16) != int(preflight_idcode, 16):
        failures.append("PS stage live IDCODE does not equal the fresh preflight IDCODE")
    live_device = markers.get("P7_XSDB_LIVE_DEVICE", "")
    if not live_device or not part.casefold().startswith(live_device.casefold()):
        failures.append("PS stage live device root is inconsistent with the authorized exact part")
    if parse_markers(stdout).get("P7_PS_STAGE_RESULT") != "PASS":
        failures.append("P7_PS_STAGE_RESULT=PASS missing from stdout")
    return not failures, failures


def _parse_trace(path: Path, case: StageCase) -> tuple[list[dict[str, int]], list[str]]:
    failures: list[str] = []
    if not path.is_file():
        return [], [f"trace result missing for slot {case.slot}"]
    raw = path.read_bytes()
    expected_bytes = case.trace_capacity * 64
    if len(raw) != expected_bytes:
        return [], [f"trace size mismatch for slot {case.slot}: expected={expected_bytes} observed={len(raw)}"]
    traces: list[dict[str, int]] = []
    for index in range(case.trace_capacity):
        words = struct.unpack_from("<16I", raw, index * 64)
        if words[0] == 0:
            continue
        trace = {
            "magic": words[0],
            "session_epoch": words[1],
            "object_id": words[2],
            "fragment_index": words[3] & 0xFFFF,
            "fragment_count": words[3] >> 16,
            "lane_mask": words[4],
            "attempt_count": words[5],
            "result": words[6],
            "error_code": words[7],
            "start_ticks": words[8] | (words[9] << 32),
            "end_ticks": words[10] | (words[11] << 32),
            "p6_retry_count": words[12],
            "p6_retry_exhausted": words[13],
            "p6_tx_fail": words[14],
            "p6_error_code": words[15],
        }
        traces.append(trace)
        if trace["magic"] != P7_TRACE_MAGIC:
            failures.append(f"slot {case.slot} trace {index} magic mismatch")
        if trace["session_epoch"] != case.request.session_epoch:
            failures.append(f"slot {case.slot} trace {index} session mismatch")
        if trace["object_id"] != case.request.object_id:
            failures.append(f"slot {case.slot} trace {index} object mismatch")
        if trace["lane_mask"] not in (1, 2, 3):
            failures.append(f"slot {case.slot} trace {index} lane mask exceeds 0x3")
        if trace["fragment_count"] != case.trace_capacity:
            failures.append(f"slot {case.slot} trace {index} fragment count mismatch")
        if trace["fragment_index"] >= case.trace_capacity:
            failures.append(f"slot {case.slot} trace {index} fragment index out of range")
        if trace["attempt_count"] != 1:
            failures.append(f"slot {case.slot} trace {index} must contain exactly one P7 submission")
        if trace["p6_retry_count"] > case.request.max_retries:
            failures.append(f"slot {case.slot} trace {index} exceeds the authorized P6 retry acceptance cap")
        if trace["end_ticks"] <= trace["start_ticks"]:
            failures.append(f"slot {case.slot} trace {index} has invalid timing")
        if trace["p6_retry_exhausted"] or trace["p6_tx_fail"] or trace["p6_error_code"]:
            failures.append(f"slot {case.slot} trace {index} reports a P6 failure")
    if case.expected_status == P7_DESCRIPTOR_COMPLETE:
        if len(traces) != case.trace_capacity:
            failures.append(f"slot {case.slot} completed trace is sparse/all-zero")
        indices = [item["fragment_index"] for item in traces]
        if sorted(indices) != list(range(case.trace_capacity)):
            failures.append(f"slot {case.slot} completed trace fragment ordering/coverage mismatch")
        if any(item["result"] != 1 or item["error_code"] != 0 for item in traces):
            failures.append(f"slot {case.slot} completed trace contains a failed fragment")
        identities = {(item["session_epoch"], item["object_id"]) for item in traces}
        if len(identities) != 1:
            failures.append(f"slot {case.slot} trace mixes object identities")
    return traces, failures


STATIONARY_OBJECT_PATTERN = re.compile(
    r"^P7_STATIONARY_OBJECT_([0-9]{8})=SLOT_([0-7]),GEN_([0-9]+),SESSION_([0-9A-Fa-f]{8}),"
    r"OBJECT_([0-9]+),STATUS_([0-9]+),ERROR_([0-9]+),BYTES_([0-9]+),"
    r"FRAGMENTS_([0-9]+)/([0-9]+),ATTEMPTS_([0-9]+),FALLBACKS_([0-9]+),"
    r"OUTSHA_([0-9A-Fa-f]{64}),P6_RETRY_COUNT_([0-9]+),P6_RETRY_EXHAUSTED_([0-9]+),"
    r"P6_TX_FAIL_([0-9]+),P6_CRC_BAD_([0-9]+),P6_PAYLOAD_MISMATCH_([0-9]+),"
    r"MAX_TXD_HIGH_CYCLES_([0-9]+),DUTY_VIOLATIONS_([0-9]+),LANE0_([0-9]+),"
    r"LANE1_([0-9]+),REPLICATED_([0-9]+),START_TICKS_([0-9]+),END_TICKS_([0-9]+),"
    r"COMPLETION_SEQUENCE_([0-9]+)$"
)


def _parse_stationary_objects(raw_text: str) -> list[dict[str, int | str]]:
    objects: list[dict[str, int | str]] = []
    for line in raw_text.splitlines():
        match = STATIONARY_OBJECT_PATTERN.fullmatch(line.strip())
        if not match:
            continue
        objects.append(
            {
                "sequence": int(match.group(1)),
                "slot": int(match.group(2)),
                "generation": int(match.group(3)),
                "session_epoch": int(match.group(4), 16),
                "object_id": int(match.group(5)),
                "status": int(match.group(6)),
                "error_code": int(match.group(7)),
                "bytes_completed": int(match.group(8)),
                "fragments_completed": int(match.group(9)),
                "fragments_total": int(match.group(10)),
                "fragment_attempts": int(match.group(11)),
                "fallback_count": int(match.group(12)),
                "output_sha256": match.group(13).lower(),
                "p6_retry_count": int(match.group(14)),
                "p6_retry_exhausted": int(match.group(15)),
                "p6_tx_fail": int(match.group(16)),
                "p6_crc_bad": int(match.group(17)),
                "p6_payload_mismatch": int(match.group(18)),
                "max_txd_high_cycles": int(match.group(19)),
                "duty_violations": int(match.group(20)),
                "lane0_fragments": int(match.group(21)),
                "lane1_fragments": int(match.group(22)),
                "replicated_fragments": int(match.group(23)),
                "start_ticks": int(match.group(24)),
                "end_ticks": int(match.group(25)),
                "completion_sequence": int(match.group(26)),
            }
        )
    return objects


def _nearest_rank(values: list[int], percentile: float) -> int:
    """Return a deterministic nearest-rank percentile for a non-empty sample."""
    if not values:
        raise ValueError("nearest-rank percentile requires at least one value")
    if not 0.0 < percentile <= 1.0:
        raise ValueError("percentile must be in (0, 1]")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _expected_stationary_lane(case: StageCase, fragment_index: int) -> tuple[int, str]:
    """Return the scheduler-selected mask and any controlled fallback direction."""
    policy = case.request.lane_policy
    if policy == 1:
        preferred = 1
    elif policy == 2:
        preferred = 2
    elif policy == 3:
        preferred = 1 if fragment_index % 2 == 0 else 2
    elif policy == 4:
        preferred = 3
    else:  # StageCase construction already rejects this; remain fail-closed here.
        return 0, "invalid_policy"
    unavailable = (
        case.request.unavailable_lane_mask
        if fragment_index >= case.request.unavailable_after_fragment
        else 0
    )
    selected = preferred & ~unavailable & 0x3
    direction = ""
    if selected == 0 and preferred == 1 and not (unavailable & 2):
        selected = 2
        direction = "lane0_to_lane1"
    elif selected == 0 and preferred == 2 and not (unavailable & 1):
        selected = 1
        direction = "lane1_to_lane0"
    return selected, direction


def _stationary_trace_evidence(
    bundle: StageBundle,
    stationary_objects: list[dict[str, Any]],
    raw_text: str,
) -> tuple[dict[str, Any], list[int], list[str]]:
    """Validate every terminal object's immutable trace dump, not only final slots."""
    failures: list[str] = []
    fragment_latency_ticks: list[int] = []
    fragment_timing_records: list[dict[str, int]] = []
    records: list[dict[str, Any]] = []
    rejected = 0
    duplicated = 0
    out_of_order = 0
    fallback_lane0_to_lane1 = 0
    fallback_lane1_to_lane0 = 0
    sha256_mismatches = 0
    whole_object_crc_failures = 0

    marker_pattern = re.compile(r"^P7_STATIONARY_TERMINAL_BUNDLE_([0-9]{8})_CAPTURED=1$")
    marker_sequences: list[int] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("P7_STATIONARY_TERMINAL_BUNDLE_"):
            continue
        match = marker_pattern.fullmatch(stripped)
        if match is None:
            failures.append(f"malformed stationary terminal-bundle marker: {stripped}")
        else:
            marker_sequences.append(int(match.group(1)))
    expected_sequences = list(range(1, len(stationary_objects) + 1))
    if marker_sequences != expected_sequences:
        failures.append(
            "stationary terminal-bundle markers must be exactly contiguous and unique: "
            f"expected=1..{len(stationary_objects)} observed={marker_sequences}"
        )

    expected_names = {
        f"stationary_{sequence:08d}_{suffix}_result.bin"
        for sequence in expected_sequences
        for suffix in ("descriptor", "output", "trace")
    }
    observed_paths = list(bundle.directory.glob("stationary_*_result.bin"))
    observed_names = {path.name for path in observed_paths}
    if observed_names != expected_names:
        failures.append(
            "stationary terminal descriptor/output/trace file set does not equal the ledger: "
            f"missing={sorted(expected_names - observed_names)} extra={sorted(observed_names - expected_names)}"
        )

    for item in stationary_objects:
        sequence = int(item["sequence"])
        slot = int(item["slot"])
        local_failures: list[str] = []
        prefix = f"stationary_{sequence:08d}"
        descriptor_path = bundle.directory / f"{prefix}_descriptor_result.bin"
        output_path = bundle.directory / f"{prefix}_output_result.bin"
        trace_path = bundle.directory / f"{prefix}_trace_result.bin"
        if not 0 <= slot < len(bundle.cases):
            local_failures.append(f"terminal ledger slot is outside 0..{len(bundle.cases) - 1}")
            traces: list[dict[str, int]] = []
            case = None
        else:
            base_case = bundle.cases[slot]
            case = replace(
                base_case,
                request=replace(
                    base_case.request,
                    session_epoch=int(item["session_epoch"]),
                    object_id=int(item["object_id"]),
                ),
            )
            if descriptor_path.is_file() and descriptor_path.stat().st_size == P7_DESCRIPTOR_BYTES:
                descriptor_raw = descriptor_path.read_bytes()
                descriptor = unpack_descriptor(descriptor_raw)
                output = output_path.read_bytes() if output_path.is_file() else b""
                validation = validate_completed(
                    case.request,
                    descriptor_raw,
                    output,
                    expected_completion_sequence=sequence,
                )
                local_failures.extend(
                    f"terminal descriptor/output: {failure}" for failure in validation["failures"]
                )
                if int(item["completion_sequence"]) != sequence:
                    local_failures.append(
                        "host ledger sequence differs from the logged firmware completion sequence"
                    )
                terminal_fields = (
                    "status",
                    "error_code",
                    "bytes_completed",
                    "fragments_total",
                    "fragments_completed",
                    "fragment_attempts",
                    "fallback_count",
                    "p6_retry_count",
                    "p6_retry_exhausted",
                    "p6_tx_fail",
                    "p6_crc_bad",
                    "p6_payload_mismatch",
                    "max_txd_high_cycles",
                    "lane0_fragments",
                    "lane1_fragments",
                    "replicated_fragments",
                    "start_ticks",
                    "end_ticks",
                    "completion_sequence",
                )
                for key in terminal_fields:
                    if int(item[key]) != int(descriptor[key]):
                        local_failures.append(
                            f"logged terminal {key} differs from immutable descriptor snapshot"
                        )
                if int(item["duty_violations"]) != int(descriptor["duty_violation_count"]):
                    local_failures.append(
                        "logged terminal duty violations differ from immutable descriptor snapshot"
                    )
                expected_sha = hashlib.sha256(case.request.data).hexdigest()
                if hashlib.sha256(output).hexdigest() != expected_sha:
                    sha256_mismatches += 1
                expected_crc = zlib.crc32(case.request.data) & 0xFFFFFFFF
                if int(descriptor["output_crc32"]) != expected_crc:
                    whole_object_crc_failures += 1
            else:
                local_failures.append("immutable terminal descriptor snapshot is missing or malformed")
            if not output_path.is_file() or output_path.stat().st_size != len(case.request.data):
                local_failures.append("immutable terminal output snapshot is missing or has the wrong size")
            traces, parse_failures = _parse_trace(trace_path, case)
            local_failures.extend(parse_failures)

        lane0 = 0
        lane1 = 0
        replicated = 0
        attempts = 0
        p6_retries = 0
        p6_retry_exhausted = 0
        p6_tx_fail = 0
        redirected_fragments = 0
        fallback_directions: set[str] = set()
        indices = [int(trace["fragment_index"]) for trace in traces]
        duplicated += len(indices) - len(set(indices))
        order_mismatches = sum(index != observed for index, observed in enumerate(indices))
        out_of_order += order_mismatches
        if order_mismatches:
            local_failures.append("trace records are not stored in strict fragment-index order")
        previous_end = 0
        for trace in traces:
            index = int(trace["fragment_index"])
            lane_mask = int(trace["lane_mask"])
            attempts += int(trace["attempt_count"])
            p6_retries += int(trace["p6_retry_count"])
            p6_retry_exhausted += int(trace["p6_retry_exhausted"])
            p6_tx_fail += int(trace["p6_tx_fail"])
            if int(trace["result"]) != 1 or int(trace["error_code"]) != 0:
                rejected += 1
            if lane_mask & 1:
                lane0 += 1
            if lane_mask & 2:
                lane1 += 1
            if lane_mask == 3:
                replicated += 1
            if case is not None:
                expected_mask, direction = _expected_stationary_lane(case, index)
                if lane_mask != expected_mask:
                    local_failures.append(
                        f"fragment {index} lane mask expected={expected_mask} observed={lane_mask}"
                    )
                if direction:
                    redirected_fragments += 1
                    fallback_directions.add(direction)
            start_ticks = int(trace["start_ticks"])
            end_ticks = int(trace["end_ticks"])
            if previous_end and start_ticks < previous_end:
                local_failures.append(f"fragment {index} timing overlaps/regresses the preceding fragment")
            previous_end = max(previous_end, end_ticks)
            if end_ticks > start_ticks:
                fragment_latency_ticks.append(end_ticks - start_ticks)
                fragment_timing_records.append(
                    {
                        "sequence": sequence,
                        "fragment_index": index,
                        "start_ticks": start_ticks,
                        "end_ticks": end_ticks,
                        "latency_ticks": end_ticks - start_ticks,
                    }
                )

        if traces:
            if int(item["start_ticks"]) > min(int(trace["start_ticks"]) for trace in traces):
                local_failures.append("object start tick does not enclose its first fragment")
            if int(item["end_ticks"]) < max(int(trace["end_ticks"]) for trace in traces):
                local_failures.append("object end tick does not enclose its last fragment")
        expected_counters = {
            "fragments_completed": len(traces),
            "fragment_attempts": attempts,
            "lane0_fragments": lane0,
            "lane1_fragments": lane1,
            "replicated_fragments": replicated,
            # Firmware reports one event per newly unavailable preferred lane,
            # while trace utilization can redirect many later fragments.
            "fallback_count": len(fallback_directions),
            "p6_retry_count": p6_retries,
            "p6_retry_exhausted": p6_retry_exhausted,
            "p6_tx_fail": p6_tx_fail,
        }
        for key, expected in expected_counters.items():
            if int(item[key]) != expected:
                local_failures.append(f"trace/terminal {key} expected={expected} observed={item[key]}")
        failures.extend(f"stationary trace sequence {sequence}: {failure}" for failure in local_failures)
        record: dict[str, Any] = {
            "sequence": sequence,
            "slot": slot,
            "session_epoch": int(item["session_epoch"]),
            "object_id": int(item["object_id"]),
            "fragment_count": len(traces),
            "fragment_attempts": attempts,
            "fallback_count": len(fallback_directions),
            "redirected_fragments": redirected_fragments,
            "passed": not local_failures,
            "failures": local_failures,
        }
        if trace_path.is_file():
            record["trace_file"] = file_record(trace_path)
        if descriptor_path.is_file():
            record["descriptor_file"] = file_record(descriptor_path)
        if output_path.is_file():
            record["output_file"] = file_record(output_path)
        records.append(record)
        fallback_lane0_to_lane1 += int("lane0_to_lane1" in fallback_directions)
        fallback_lane1_to_lane0 += int("lane1_to_lane0" in fallback_directions)

    summary = {
        "passed": not failures,
        "failures": failures,
        "terminal_bundles_expected": len(stationary_objects),
        "terminal_bundle_markers_observed": len(marker_sequences),
        "artifact_files_expected": 3 * len(stationary_objects),
        "files_observed": len(observed_paths),
        "terminal_bundles_validated": sum(bool(record["passed"]) for record in records),
        "fragment_trace_entries": sum(int(record["fragment_count"]) for record in records),
        "fragment_latency_samples": len(fragment_latency_ticks),
        "fragment_timing_records": fragment_timing_records,
        "fragments_rejected": rejected,
        "fragments_duplicated": duplicated,
        "fragments_out_of_order": out_of_order,
        "fallback_lane0_to_lane1": fallback_lane0_to_lane1,
        "fallback_lane1_to_lane0": fallback_lane1_to_lane0,
        "sha256_mismatches": sha256_mismatches,
        "whole_object_crc_failures": whole_object_crc_failures,
        "percentile_method": "nearest_rank",
        "records": records,
    }
    return summary, fragment_latency_ticks, failures


def _canonical_stationary_samples(
    stationary_objects: list[dict[str, Any]],
    *,
    runtime_start_ticks: int,
    counts_per_second: int = P7_COUNTS_PER_SECOND,
    sample_interval_seconds: int = 30,
    runtime_seconds: int = MAX_SERVICE_RUNTIME_SEC,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reconstruct fixed PS-time windows from immutable terminal end ticks."""

    failures: list[str] = []
    if runtime_start_ticks <= 0:
        return [], ["stationary runtime start tick is missing"]
    if counts_per_second <= 0 or sample_interval_seconds <= 0 or runtime_seconds <= 0:
        return [], ["stationary canonical sample configuration is invalid"]
    if runtime_seconds % sample_interval_seconds:
        return [], ["stationary runtime is not divisible by its sample interval"]

    ordered = sorted(stationary_objects, key=lambda item: int(item["sequence"]))
    sequences = [int(item["sequence"]) for item in ordered]
    if sequences != list(range(1, len(ordered) + 1)):
        failures.append("stationary canonical ledger sequence is not contiguous")
    prepared: list[tuple[dict[str, Any], int]] = []
    runtime_ticks = runtime_seconds * counts_per_second
    identities: set[tuple[int, int]] = set()
    previous_end_ticks = -1
    for item in ordered:
        identity = (int(item["session_epoch"]), int(item["object_id"]))
        if identity in identities:
            failures.append("stationary canonical ledger contains a duplicate object identity")
        identities.add(identity)
        start_ticks = int(item["start_ticks"])
        end_ticks = int(item["end_ticks"])
        relative_end = end_ticks - runtime_start_ticks
        if start_ticks < runtime_start_ticks:
            failures.append(
                f"stationary object starts before runtime origin: sequence={item['sequence']}"
            )
        if end_ticks <= start_ticks:
            failures.append(
                f"stationary object has non-positive latency: sequence={item['sequence']}"
            )
        if end_ticks <= previous_end_ticks:
            failures.append(
                "stationary completion sequence does not have strictly increasing end ticks: "
                f"sequence={item['sequence']}"
            )
        previous_end_ticks = end_ticks
        if not 0 <= relative_end <= runtime_ticks:
            failures.append(
                f"stationary object terminal tick is outside 0..runtime: sequence={item['sequence']}"
            )
        prepared.append((item, relative_end))

    samples: list[dict[str, Any]] = []
    sample_count = runtime_seconds // sample_interval_seconds
    for sequence in range(1, sample_count + 1):
        threshold_ticks = sequence * sample_interval_seconds * counts_per_second
        previous_threshold = threshold_ticks - sample_interval_seconds * counts_per_second
        included = [item for item, relative_end in prepared if relative_end <= threshold_ticks]
        interval = [
            item
            for item, relative_end in prepared
            if previous_threshold < relative_end <= threshold_ticks
        ]
        bytes_completed = sum(int(item["bytes_completed"]) for item in included)
        previous_bytes = sum(
            int(item["bytes_completed"])
            for item, relative_end in prepared
            if relative_end <= previous_threshold
        )
        interval_ticks = threshold_ticks - previous_threshold
        latencies = [int(item["end_ticks"]) - int(item["start_ticks"]) for item in interval]
        latency_summary = {
            "latency_count": len(latencies),
            "latency_min_ticks": min(latencies, default=0),
            "latency_mean_ticks": sum(latencies) // len(latencies) if latencies else 0,
            "latency_p50_ticks": _nearest_rank(latencies, 0.50) if latencies else 0,
            "latency_p95_ticks": _nearest_rank(latencies, 0.95) if latencies else 0,
            "latency_p99_ticks": _nearest_rank(latencies, 0.99) if latencies else 0,
            "latency_max_ticks": max(latencies, default=0),
        }
        samples.append(
            {
                "sequence": sequence,
                "elapsed_ticks": threshold_ticks,
                "elapsed_sec": float(sequence * sample_interval_seconds),
                "window": "CALIBRATION" if threshold_ticks <= CALIBRATION_SEC * counts_per_second else "ACCEPTANCE",
                "objects": len(included),
                "failed": 0,
                "bytes": bytes_completed,
                "fragments": sum(int(item["fragments_completed"]) for item in included),
                "lane0": sum(int(item["lane0_fragments"]) for item in included),
                "lane1": sum(int(item["lane1_fragments"]) for item in included),
                "replicated": sum(int(item["replicated_fragments"]) for item in included),
                "fallbacks": sum(int(item["fallback_count"]) for item in included),
                "p6_retries": sum(int(item["p6_retry_count"]) for item in included),
                "p6_retry_exhausted": sum(int(item["p6_retry_exhausted"]) for item in included),
                "p6_tx_fail": sum(int(item["p6_tx_fail"]) for item in included),
                "p6_crc_bad": sum(int(item["p6_crc_bad"]) for item in included),
                "p6_payload_mismatch": sum(int(item["p6_payload_mismatch"]) for item in included),
                "max_txd_high": max(
                    (int(item["max_txd_high_cycles"]) for item in included), default=0
                ),
                "duty_violations": sum(int(item["duty_violations"]) for item in included),
                "current_bps": (bytes_completed * 8 * counts_per_second) // threshold_ticks,
                "rolling_bps": (
                    (bytes_completed - previous_bytes) * 8 * counts_per_second
                )
                // interval_ticks,
                "last_object": int(included[-1]["object_id"]) if included else 0,
                **latency_summary,
            }
        )
    return samples, failures


def _stationary_application_metrics(
    bundle: StageBundle,
    stationary_objects: list[dict[str, Any]],
    mailbox: dict[str, Any],
    raw_text: str,
    trace_summary: dict[str, Any],
    fragment_latency_ticks: list[int],
) -> tuple[dict[str, Any], list[str]]:
    """Derive the complete P7 plan section 10 metric set from bound evidence."""
    failures: list[str] = []
    markers = parse_markers(raw_text)
    expected_host_bytes = sum(len(case.request.data) for case in bundle.cases)
    host_bytes_text = markers.get("P7_HOST_TO_PS_INPUT_BYTES", "")
    host_duration_text = markers.get("P7_HOST_TO_PS_INPUT_DURATION_MS", "")
    host_bytes_per_sec_text = markers.get("P7_HOST_TO_PS_INPUT_BYTES_PER_SEC", "")
    host_bps_text = markers.get("P7_HOST_TO_PS_INPUT_BPS", "")
    if not all(
        text.isdecimal()
        for text in (host_bytes_text, host_duration_text, host_bytes_per_sec_text, host_bps_text)
    ):
        failures.append("host-to-PS preload metrics are missing or malformed")
        host_bytes = host_duration_ms = host_bytes_per_sec = host_bps = 0
    else:
        host_bytes = int(host_bytes_text)
        host_duration_ms = int(host_duration_text)
        host_bytes_per_sec = int(host_bytes_per_sec_text)
        host_bps = int(host_bps_text)
        if host_bytes != expected_host_bytes:
            failures.append(
                f"host-to-PS byte count expected={expected_host_bytes} observed={host_bytes}"
            )
        if host_duration_ms < 1:
            failures.append("host-to-PS duration must be at least one millisecond")
        else:
            if host_bytes_per_sec != (host_bytes * 1000) // host_duration_ms:
                failures.append("host-to-PS bytes/sec marker is not bound to bytes and duration")
            if host_bps != (host_bytes * 8000) // host_duration_ms:
                failures.append("host-to-PS bit-rate marker is not bound to bytes and duration")

    objects_expected = len(stationary_objects)
    fragments_generated = sum(bundle.cases[int(item["slot"])].trace_capacity for item in stationary_objects)
    fragments_submitted = sum(int(item["fragment_attempts"]) for item in stationary_objects)
    fragments_completed = sum(int(item["fragments_completed"]) for item in stationary_objects)
    bytes_requested = sum(len(bundle.cases[int(item["slot"])].request.data) for item in stationary_objects)
    bytes_completed = sum(int(item["bytes_completed"]) for item in stationary_objects)
    if fragments_submitted < fragments_generated:
        failures.append("stationary submitted-fragment count is below generated fragments")
    if int(trace_summary.get("fragment_trace_entries", -1)) != fragments_completed:
        failures.append("stationary trace-entry count does not reconcile to completed fragments")
    if len(fragment_latency_ticks) != fragments_completed:
        failures.append("stationary fragment-latency sample count does not reconcile to completed fragments")
    if int(mailbox.get("objects_requested", -1)) != objects_expected:
        failures.append("stationary mailbox requested-object count does not reconcile to terminal ledger")
    if int(mailbox.get("objects_completed", -1)) != objects_expected:
        failures.append("stationary mailbox completed-object count does not reconcile to terminal ledger")
    if int(mailbox.get("objects_failed", -1)) != 0:
        failures.append("stationary mailbox contains failed objects")

    runtime_ticks = int(mailbox.get("runtime_elapsed_ticks", 0))
    if runtime_ticks <= 0:
        failures.append("stationary PS runtime elapsed ticks are missing")
    application_goodput_bps = (
        (bytes_completed * 8 * P7_COUNTS_PER_SECOND) // runtime_ticks if runtime_ticks > 0 else 0
    )
    object_latency_ticks = [
        int(item["end_ticks"]) - int(item["start_ticks"])
        for item in stationary_objects
        if int(item["end_ticks"]) > int(item["start_ticks"])
    ]
    if len(object_latency_ticks) != objects_expected:
        failures.append("stationary object-latency samples do not cover every terminal object")

    def convert(value: float, multiplier: float) -> float:
        return round(value * multiplier / P7_COUNTS_PER_SECOND, 6)

    if fragment_latency_ticks:
        fragment_min = convert(min(fragment_latency_ticks), 1_000_000.0)
        fragment_mean = convert(statistics.fmean(fragment_latency_ticks), 1_000_000.0)
        fragment_p50 = convert(_nearest_rank(fragment_latency_ticks, 0.50), 1_000_000.0)
        fragment_p95 = convert(_nearest_rank(fragment_latency_ticks, 0.95), 1_000_000.0)
        fragment_p99 = convert(_nearest_rank(fragment_latency_ticks, 0.99), 1_000_000.0)
        fragment_max = convert(max(fragment_latency_ticks), 1_000_000.0)
    else:
        fragment_min = fragment_mean = fragment_p50 = fragment_p95 = fragment_p99 = fragment_max = 0.0
    if object_latency_ticks:
        object_min = convert(min(object_latency_ticks), 1000.0)
        object_mean = convert(statistics.fmean(object_latency_ticks), 1000.0)
        object_p95 = convert(_nearest_rank(object_latency_ticks, 0.95), 1000.0)
        object_max = convert(max(object_latency_ticks), 1000.0)
    else:
        object_min = object_mean = object_p95 = object_max = 0.0

    logged_sha256_mismatches = sum(
        str(item["output_sha256"]).lower()
        != hashlib.sha256(bundle.cases[int(item["slot"])].request.data).hexdigest()
        for item in stationary_objects
    )
    sha256_mismatches = max(
        logged_sha256_mismatches,
        int(trace_summary.get("sha256_mismatches", 0)),
    )
    metrics: dict[str, Any] = {
        "objects_requested": int(mailbox.get("objects_requested", 0)),
        "objects_completed": int(mailbox.get("objects_completed", 0)),
        "objects_failed": int(mailbox.get("objects_failed", 0)),
        "fragments_generated": fragments_generated,
        "fragments_submitted": fragments_submitted,
        "fragments_completed": fragments_completed,
        "fragments_retried": max(0, fragments_submitted - fragments_generated),
        "fragments_duplicated": int(trace_summary.get("fragments_duplicated", 0)),
        "fragments_rejected": int(trace_summary.get("fragments_rejected", 0)),
        "fragments_out_of_order": int(trace_summary.get("fragments_out_of_order", 0)),
        "bytes_requested": bytes_requested,
        "bytes_completed": bytes_completed,
        "whole_object_crc_failures": int(trace_summary.get("whole_object_crc_failures", 0)),
        "sha256_mismatches": sha256_mismatches,
        "lane0_fragments": sum(int(item["lane0_fragments"]) for item in stationary_objects),
        "lane1_fragments": sum(int(item["lane1_fragments"]) for item in stationary_objects),
        "replicated_fragments": sum(int(item["replicated_fragments"]) for item in stationary_objects),
        "fallback_lane0_to_lane1": int(trace_summary.get("fallback_lane0_to_lane1", 0)),
        "fallback_lane1_to_lane0": int(trace_summary.get("fallback_lane1_to_lane0", 0)),
        "queue_high_watermark": int(mailbox.get("queue_high_watermark", 0)),
        "backpressure_events": int(mailbox.get("backpressure_events", 0)),
        "host_to_ps_bytes_per_sec": host_bytes_per_sec,
        "application_goodput_bps": application_goodput_bps,
        "fragment_latency_min_us": fragment_min,
        "fragment_latency_mean_us": fragment_mean,
        "fragment_latency_p50_us": fragment_p50,
        "fragment_latency_p95_us": fragment_p95,
        "fragment_latency_p99_us": fragment_p99,
        "fragment_latency_max_us": fragment_max,
        "object_latency_min_ms": object_min,
        "object_latency_mean_ms": object_mean,
        "object_latency_p95_ms": object_p95,
        "object_latency_max_ms": object_max,
        "p6_retry_count": sum(int(item["p6_retry_count"]) for item in stationary_objects),
        "p6_retry_exhausted": sum(int(item["p6_retry_exhausted"]) for item in stationary_objects),
        "p6_tx_fail": sum(int(item["p6_tx_fail"]) for item in stationary_objects),
        "p6_crc_bad": sum(int(item["p6_crc_bad"]) for item in stationary_objects),
        "p6_payload_mismatch": sum(int(item["p6_payload_mismatch"]) for item in stationary_objects),
        "max_txd_high_cycles": max(
            (int(item["max_txd_high_cycles"]) for item in stationary_objects), default=0
        ),
        "duty_violation_count": sum(int(item["duty_violations"]) for item in stationary_objects),
        "shutdown_result": int(mailbox.get("shutdown_result", -1)),
        "fragment_latency_sample_count": len(fragment_latency_ticks),
        "object_latency_sample_count": len(object_latency_ticks),
        "host_to_ps_input_bytes": host_bytes,
        "host_to_ps_input_duration_ms": host_duration_ms,
        "host_to_ps_bits_per_sec": host_bps,
        "ps_counts_per_second": P7_COUNTS_PER_SECOND,
        "ps_runtime_elapsed_ticks": runtime_ticks,
        "latency_percentile_method": "nearest_rank",
        "time_sources": {
            "host_to_ps_bytes_per_sec": (
                "Tcl host wall clock milliseconds around the initial XSDB dow -data preload; "
                "includes JTAG host overhead and is not optical latency"
            ),
            "application_goodput_bps": "PS global timer runtime_elapsed_ticks over completed application bytes",
            "fragment_latency": "PS global timer ticks around each P6 fragment transport operation",
            "object_latency": "PS global timer ticks around complete object processing",
        },
    }
    zero_required = (
        "objects_failed",
        "fragments_duplicated",
        "fragments_rejected",
        "fragments_out_of_order",
        "whole_object_crc_failures",
        "sha256_mismatches",
        "p6_retry_exhausted",
        "p6_tx_fail",
        "p6_crc_bad",
        "p6_payload_mismatch",
        "duty_violation_count",
        "shutdown_result",
    )
    for key in zero_required:
        if int(metrics[key]) != 0:
            failures.append(f"stationary application metric must be zero: {key}={metrics[key]}")
    if int(metrics["max_txd_high_cycles"]) > 8:
        failures.append("stationary application metric exceeds max TXD-high cycles")
    metrics["validated"] = not failures
    metrics["failures"] = failures
    return metrics, failures


def postprocess_bundle(bundle: StageBundle, mode: str, raw_text: str) -> dict[str, Any]:
    failures: list[str] = []
    markers = parse_markers(raw_text)
    case_results: list[dict[str, Any]] = []
    boundary_results: list[dict[str, Any]] = []
    functional_checkpoint_result: dict[str, Any] = {}
    stationary_objects: list[dict[str, Any]] = (
        list(_parse_stationary_objects(raw_text)) if mode == "stationary" else []
    )
    stationary_final_by_slot: dict[int, dict[str, Any]] = {}
    for item in stationary_objects:
        stationary_final_by_slot[int(item["slot"])] = item
    samples: list[dict[str, int | float | str]] = []
    stationary_trace_validation: dict[str, Any] = {}
    application_metrics: dict[str, Any] = {}
    for case in bundle.cases:
        effective_case = case
        expected_completion_sequence: int | None = None
        if mode == "stationary" and case.slot in stationary_final_by_slot:
            final_identity = stationary_final_by_slot[case.slot]
            effective_case = replace(
                case,
                request=replace(
                    case.request,
                    session_epoch=int(final_identity["session_epoch"]),
                    object_id=int(final_identity["object_id"]),
                ),
            )
            expected_completion_sequence = int(final_identity["sequence"])
        elif mode == "functional":
            expected_completion_sequence = (54 + case.slot) if case.slot < 4 else (50 + case.slot - 4)
        descriptor_path = bundle.directory / f"descriptor_result_{case.slot}.bin"
        output_path = bundle.directory / f"output_result_{case.slot}.bin"
        trace_path = bundle.directory / f"trace_result_{case.slot}.bin"
        if not descriptor_path.is_file() or descriptor_path.stat().st_size != P7_DESCRIPTOR_BYTES:
            failures.append(f"descriptor result missing/invalid for slot {case.slot}")
            continue
        descriptor_raw = descriptor_path.read_bytes()
        descriptor = unpack_descriptor(descriptor_raw)
        output = output_path.read_bytes() if output_path.is_file() else b""
        traces, trace_failures = _parse_trace(trace_path, effective_case)
        failures.extend(trace_failures)
        local_failures: list[str] = []
        if mode == "stationary" and case.slot not in stationary_final_by_slot:
            local_failures.append("stationary final descriptor has no terminal-ledger identity")
        if descriptor["status"] != case.expected_status:
            local_failures.append(f"status expected={case.expected_status} observed={descriptor['status']}")
        if descriptor["error_code"] != case.expected_error:
            local_failures.append(f"error expected={case.expected_error} observed={descriptor['error_code']}")
        expected_sha = hashlib.sha256(case.request.data).hexdigest()
        identity_checks = (
            ("magic", P7_DESCRIPTOR_MAGIC),
            ("version", P7_RUNTIME_VERSION),
            ("command", P7_DESCRIPTOR_TRANSFER),
            ("session_epoch", effective_case.request.session_epoch),
            ("input_address", effective_case.request.input_address),
            ("output_address", effective_case.request.output_address),
            ("object_length", len(effective_case.request.data)),
            ("expected_crc32", zlib.crc32(effective_case.request.data) & 0xFFFFFFFF),
            ("lane_policy", effective_case.request.lane_policy),
            ("max_retries", effective_case.request.max_retries),
            ("unavailable_lane_mask", effective_case.request.unavailable_lane_mask),
            ("unavailable_after_fragment", effective_case.request.unavailable_after_fragment),
            ("abort_after_fragment", effective_case.request.abort_after_fragment),
            ("trace_address", effective_case.request.trace_address),
            ("trace_capacity", case.trace_capacity),
        )
        for key, expected in identity_checks:
            if descriptor[key] != expected:
                local_failures.append(f"{key} expected={expected} observed={descriptor[key]}")
        if descriptor["object_id"] != effective_case.request.object_id:
            local_failures.append(f"object_id expected={effective_case.request.object_id} observed={descriptor['object_id']}")
        if descriptor["expected_sha256"] != expected_sha:
            local_failures.append("expected SHA256/request identity mismatch")
        if int(descriptor["completion_sequence"]) < 1:
            local_failures.append("completion sequence was not published")
        if int(descriptor["max_txd_high_cycles"]) > 8:
            local_failures.append("continuous TXD-high safety limit exceeded")
        if int(descriptor["duty_violation_count"]) != 0:
            local_failures.append("duty guard violation reported")
        if case.expected_status == P7_DESCRIPTOR_COMPLETE:
            validation = validate_completed(
                effective_case.request,
                descriptor_raw,
                output,
                expected_completion_sequence=expected_completion_sequence,
            )
            local_failures.extend(validation["failures"])
            if descriptor["fragments_total"] != case.trace_capacity or descriptor["fragments_completed"] != case.trace_capacity:
                local_failures.append("completed fragment counters do not match trace capacity")
            if descriptor["fragment_attempts"] < case.trace_capacity:
                local_failures.append("fragment attempt count is below completed fragments")
            if int(descriptor["end_ticks"]) <= int(descriptor["start_ticks"]):
                local_failures.append("object latency ticks are missing/invalid")
        else:
            if descriptor["bytes_completed"] != 0:
                local_failures.append("failed/aborted descriptor retained partial bytes")
            if len(output) != len(case.request.data):
                local_failures.append("failed/aborted output length mismatch")
            if any(output):
                local_failures.append("failed/aborted output was not atomically wiped")
        failures.extend(f"slot {case.slot}: {item}" for item in local_failures)
        case_results.append(
            {
                "slot": case.slot,
                "name": case.name,
                "passed": not local_failures and not trace_failures,
                "failures": local_failures + trace_failures,
                "descriptor": {key: value for key, value in descriptor.items() if key != "words"},
                "trace_entries": traces,
                "output_sha256": hashlib.sha256(output).hexdigest(),
                "output_bytes": len(output),
                "object_latency_ticks": max(0, int(descriptor["end_ticks"]) - int(descriptor["start_ticks"])),
            }
        )
    mailbox_path = bundle.directory / "mailbox_final.bin"
    mailbox: dict[str, Any] = {}
    if not mailbox_path.is_file() or mailbox_path.stat().st_size != 256:
        failures.append("final mailbox result missing or invalid")
    else:
        mailbox = unpack_mailbox(mailbox_path.read_bytes())
        if mailbox["magic"] != P7_MAILBOX_MAGIC or mailbox["version"] != P7_RUNTIME_VERSION:
            failures.append("PS mailbox magic/version mismatch")
        if mailbox["queue_depth"] != P7_QUEUE_DEPTH:
            failures.append("PS mailbox queue depth is not exactly 8")
        expected_cutoff = bundle.scheduling_cutoff_sec if mode == "stationary" else 0
        expected_admission_guard = 1 if mode == "stationary" else 0
        if (
            int(mailbox.get("scheduling_cutoff_seconds", -1)) != expected_cutoff
            or int(mailbox.get("admission_guard_seconds", -1))
            != expected_admission_guard
        ):
            failures.append("PS firmware admission cutoff/guard mailbox binding mismatch")
        if int(mailbox.get("runtime_elapsed_sequence", 0)) == 0 or int(
            mailbox.get("runtime_elapsed_sequence", 0)
        ) & 1:
            failures.append("PS mailbox runtime elapsed seqlock is missing or left odd")
        request_value = int(mailbox.get("runtime_elapsed_request", -1))
        ack_value = int(mailbox.get("runtime_elapsed_ack", -2))
        request_mismatch = request_value != ack_value
        terminal_unacknowledged = markers.get("P7_TERMINAL_UNACKNOWLEDGED_REFRESH") == "1"
        final_request_marker = markers.get("P7_TERMINAL_FINAL_REQUEST", "")
        final_ack_marker = markers.get("P7_TERMINAL_FINAL_ACK", "")
        if mode == "stationary" and not (
            final_request_marker.isdecimal()
            and final_ack_marker.isdecimal()
            and int(final_request_marker) == request_value
            and int(final_ack_marker) == ack_value
        ):
            failures.append("stationary terminal request/ACK markers do not match final mailbox")
        if request_mismatch:
            captured_request = markers.get(
                "P7_TERMINAL_UNACKNOWLEDGED_CAPTURED_REQUEST", ""
            )
            captured_ack = markers.get("P7_TERMINAL_UNACKNOWLEDGED_CAPTURED_ACK", "")
            if not (
                mode == "stationary"
                and mailbox["service_state"] in (4, 5)
                and terminal_unacknowledged
                and captured_request.isdecimal()
                and captured_ack.isdecimal()
                and final_request_marker.isdecimal()
                and final_ack_marker.isdecimal()
                and int(captured_request) == request_value
                and int(captured_ack) == ack_value
                and int(final_request_marker) == request_value
                and int(final_ack_marker) == ack_value
            ):
                failures.append("PS mailbox runtime elapsed snapshot request was not acknowledged")
        elif terminal_unacknowledged:
            failures.append("terminal-unacknowledged marker contradicts equal final request/ACK")
        mailbox["terminal_unacknowledged_refresh"] = request_mismatch and terminal_unacknowledged
        expected_command = P7_CONTROL_RUN if mode == "stationary" else P7_CONTROL_SHUTDOWN
        if mailbox["control_command"] != expected_command:
            failures.append("PS mailbox final control command mismatch")
        if mailbox["service_state"] != 4 or mailbox["shutdown_result"] != 0:
            failures.append("PS service did not publish clean SHUTDOWN state")
    if mode == "queue" and mailbox:
        if mailbox["queue_high_watermark"] != 8 or mailbox["backpressure_events"] < 1:
            failures.append("queue mode did not observe full 8-entry queue/backpressure")
        if mailbox["abort_count"] < 1 or mailbox["objects_failed"] != P7_QUEUE_DEPTH:
            failures.append("queue ABORT-while-queued did not abort exactly eight queued objects")
        queue_markers = parse_markers(raw_text)
        for marker in (
            "P7_QUEUE_DEPTH1_COMPLETE",
            "P7_QUEUE_FULL_BEFORE_RUN",
            "P7_QUEUE_STOP_WHILE_QUEUED",
            "P7_QUEUE_OVERFLOW_REJECTED_BEFORE_DDR_WRITE",
            "P7_QUEUE_PRODUCER_FASTER_THAN_CONSUMER",
            "P7_QUEUE_MAX_FIFO_COMPLETE",
            "P7_QUEUE_ABORT_WHILE_QUEUED",
            "P7_QUEUE_INTERPHASE_SHUTDOWN_1_PROGRAMMED",
            "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_1",
            "P7_QUEUE_INTERPHASE_SHUTDOWN_2_PROGRAMMED",
            "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_2",
        ):
            if queue_markers.get(marker) != "1":
                failures.append(f"queue mode marker missing: {marker}")
        if queue_markers.get("P7_QUEUE_INTERPHASE_SHUTDOWN_COUNT") != "2":
            failures.append("queue mode interphase shutdown count mismatch")
        for marker, expected in (
            ("P7_QUEUE_OVERFLOW_ADMISSION", "FULL"),
            ("P7_QUEUE_OVERFLOW_OCCUPANCY", str(P7_QUEUE_DEPTH)),
            ("P7_QUEUE_OVERFLOW_CAPACITY", str(P7_QUEUE_DEPTH)),
            ("P7_QUEUE_OVERFLOW_DDR_WRITE", "0"),
            ("P7_QUEUE_OVERFLOW_DDR_WRITE_COUNT", "0"),
            ("P7_QUEUE_OVERFLOW_CANDIDATE_OBJECT_ID", "9"),
        ):
            if queue_markers.get(marker) != expected:
                failures.append(f"queue overflow admission evidence mismatch: {marker}")
        ring_before_path = bundle.directory / "queue_overflow_ring_before.bin"
        ring_after_path = bundle.directory / "queue_overflow_ring_after.bin"
        if (
            not ring_before_path.is_file()
            or not ring_after_path.is_file()
            or ring_before_path.stat().st_size != P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH
            or ring_after_path.stat().st_size != P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH
        ):
            failures.append("queue overflow ring before/after evidence missing")
        elif ring_before_path.read_bytes() != ring_after_path.read_bytes():
            failures.append("queue overflow admission changed the full descriptor ring")
        overflow_candidate = bundle.queue_overflow_candidate
        if (
            overflow_candidate is None
            or overflow_candidate.request.object_id != 9
            or any(case.request.object_id == overflow_candidate.request.object_id for case in bundle.cases)
        ):
            failures.append("queue overflow candidate is not a distinct valid object 9")
        sequences = [int(item.get("descriptor", {}).get("completion_sequence", 0)) for item in case_results]
        if sequences != list(range(1, P7_QUEUE_DEPTH + 1)):
            failures.append("queue mode did not preserve FIFO completion order 1..8")
        if mailbox["stop_count"] < 1:
            failures.append("queue mode did not observe STOP while descriptors were queued")
        depth1_mailbox_path = bundle.directory / "queue_depth1_mailbox.bin"
        depth1_descriptor_path = bundle.directory / "queue_depth1_descriptor_result.bin"
        depth1_output_path = bundle.directory / "queue_depth1_output_result.bin"
        depth1_trace_path = bundle.directory / "queue_depth1_trace_result.bin"
        if not depth1_mailbox_path.is_file() or depth1_mailbox_path.stat().st_size != 256:
            failures.append("queue depth-1 mailbox evidence missing")
        else:
            depth1_mailbox = unpack_mailbox(depth1_mailbox_path.read_bytes())
            if (
                depth1_mailbox["queue_depth"] != 1
                or depth1_mailbox["queue_high_watermark"] != 1
                or depth1_mailbox["objects_completed"] != 1
                or depth1_mailbox["objects_failed"] != 0
                or depth1_mailbox["service_state"] != 4
                or depth1_mailbox["shutdown_result"] != 0
            ):
                failures.append("queue depth-1 phase mailbox contract failed")
        if not depth1_descriptor_path.is_file() or depth1_descriptor_path.stat().st_size != P7_DESCRIPTOR_BYTES:
            failures.append("queue depth-1 descriptor evidence missing")
        else:
            depth1_output = depth1_output_path.read_bytes() if depth1_output_path.is_file() else b""
            depth1_validation = validate_completed(bundle.cases[0].request, depth1_descriptor_path.read_bytes(), depth1_output)
            failures.extend(f"queue depth-1: {item}" for item in depth1_validation["failures"])
            _, depth1_trace_failures = _parse_trace(depth1_trace_path, bundle.cases[0])
            failures.extend(f"queue depth-1: {item}" for item in depth1_trace_failures)
        max_mailbox_path = bundle.directory / "queue_max_mailbox.bin"
        if not max_mailbox_path.is_file() or max_mailbox_path.stat().st_size != 256:
            failures.append("queue max-depth mailbox evidence missing")
        else:
            max_mailbox = unpack_mailbox(max_mailbox_path.read_bytes())
            if (
                max_mailbox["queue_depth"] != P7_QUEUE_DEPTH
                or max_mailbox["queue_high_watermark"] != P7_QUEUE_DEPTH
                or max_mailbox["backpressure_events"] < 1
                or max_mailbox["objects_completed"] != P7_QUEUE_DEPTH
                or max_mailbox["objects_failed"] != 0
                or max_mailbox["service_state"] != 4
                or max_mailbox["shutdown_result"] != 0
            ):
                failures.append("queue max-depth positive phase mailbox contract failed")
        abort_descriptors_path = bundle.directory / "queue_abort_descriptors_final.bin"
        if not abort_descriptors_path.is_file() or abort_descriptors_path.stat().st_size != P7_DESCRIPTOR_BYTES * P7_QUEUE_DEPTH:
            failures.append("queue ABORT-while-queued descriptor evidence missing")
        else:
            abort_raw = abort_descriptors_path.read_bytes()
            for case in bundle.cases:
                descriptor = unpack_descriptor(
                    abort_raw[case.slot * P7_DESCRIPTOR_BYTES : (case.slot + 1) * P7_DESCRIPTOR_BYTES]
                )
                if (
                    descriptor["status"] != P7_DESCRIPTOR_ABORTED
                    or descriptor["error_code"] != 15
                    or descriptor["bytes_completed"] != 0
                    or descriptor["fragment_attempts"] != 0
                    or descriptor["completion_sequence"] != case.slot + 1
                    or descriptor["session_epoch"] != case.request.session_epoch
                    or descriptor["object_id"] != case.request.object_id
                    or descriptor["expected_sha256"] != hashlib.sha256(case.request.data).hexdigest()
                ):
                    failures.append(f"queue ABORT-while-queued descriptor contract failed: slot {case.slot}")
    if mode == "abort-restart" and mailbox:
        abort_markers = parse_markers(raw_text)
        for marker in (
            "P7_ABORT_INTERPHASE_SHUTDOWN_PROGRAMMED",
            "P7_ABORT_RESTART_CANDIDATE_REPROGRAMMED",
            "P7_ABORT_RESTART_NEW_EPOCH",
            "P7_ABORT_RESTART_REPLAY_REJECTED",
        ):
            if abort_markers.get(marker) != "1":
                failures.append(f"abort/restart marker missing: {marker}")
        abort_count_text = abort_markers.get("P7_ABORT_PHASE_ABORT_COUNT", "")
        if not abort_count_text.isdecimal() or int(abort_count_text) < 1 or abort_markers.get(
            "P7_ABORT_PHASE_SHUTDOWN_RESULT"
        ) != "0":
            failures.append("abort phase did not prove bounded abort plus clean shutdown")
        sequences = [int(item.get("descriptor", {}).get("completion_sequence", 0)) for item in case_results]
        if len(case_results) != 3 or sequences != [1, 1, 2]:
            failures.append("abort/restart completion ordering is invalid")
        elif (
            int(case_results[1]["descriptor"]["session_epoch"]) <= int(case_results[0]["descriptor"]["session_epoch"])
            or int(case_results[2]["descriptor"]["session_epoch"]) != int(case_results[1]["descriptor"]["session_epoch"])
            or int(case_results[2]["descriptor"]["object_id"]) != int(case_results[1]["descriptor"]["object_id"])
        ):
            failures.append("abort/restart new-epoch or duplicate replay identity mismatch")
        if mailbox["objects_completed"] != 1 or mailbox["objects_failed"] != 1:
            failures.append("abort/restart final service did not record one retransmit plus one duplicate rejection")
    if mode == "fault-fallback":
        if parse_markers(raw_text).get("P7_FAULT_MODEL") != "SOFTWARE_INJECTED_SCHEDULER_FAULT":
            failures.append("fault/fallback evidence is not labeled as software-injected")
        expected_trace_masks = {
            0: lambda index: 1 if index == 0 else 2,
            1: lambda index: 2 if index == 1 else 1,
            2: lambda index: 2,
            3: lambda index: 1,
        }
        for item in case_results:
            slot = int(item["slot"])
            descriptor = item.get("descriptor", {})
            traces = item.get("trace_entries", [])
            if slot in expected_trace_masks:
                if int(descriptor.get("fallback_count", 0)) < 1:
                    failures.append(f"fault/fallback slot {slot} did not count the controlled fallback")
                for trace in traces:
                    expected_mask = expected_trace_masks[slot](int(trace["fragment_index"]))
                    if int(trace["lane_mask"]) != expected_mask:
                        failures.append(f"fault/fallback slot {slot} trace used an unexpected/unavailable lane")
            elif slot in (4, 5, 6):
                if traces or any(
                    int(descriptor.get(key, 0)) != 0
                    for key in ("fragment_attempts", "fallback_count", "lane0_fragments", "lane1_fragments", "replicated_fragments")
                ):
                    failures.append(f"strict-policy unavailable case performed a transport attempt/TX: slot {slot}")
        fault_markers = parse_markers(raw_text)
        if fault_markers.get("P7_FAULT_STRICT_NEGATIVE_PHASES") != "3":
            failures.append("fault/fallback strict negative phases are incomplete")
        for slot in (4, 5, 6):
            if fault_markers.get(f"P7_FAULT_NEGATIVE_{slot}_INTERPHASE_SHUTDOWN") != "1":
                failures.append(f"fault/fallback interphase shutdown marker missing: slot {slot}")
    if mode == "functional":
        if len(case_results) != P7_QUEUE_DEPTH:
            failures.append("functional large-object matrix must contain exactly eight cases")
        for item in case_results:
            slot = int(item["slot"])
            descriptor = item.get("descriptor", {})
            traces = item.get("trace_entries", [])
            if slot == 0:
                expected_masks = [1] * len(traces)
            elif slot == 1:
                expected_masks = [2] * len(traces)
            elif slot == 3:
                expected_masks = [3] * len(traces)
            else:
                expected_masks = [1 if index % 2 == 0 else 2 for index in range(len(traces))]
            if [int(trace["lane_mask"]) for trace in traces] != expected_masks:
                failures.append(f"functional lane-policy trace mismatch for slot {slot}")
            fragments = int(descriptor.get("fragments_total", 0))
            lane0 = int(descriptor.get("lane0_fragments", 0))
            lane1 = int(descriptor.get("lane1_fragments", 0))
            replicated = int(descriptor.get("replicated_fragments", 0))
            if (
                (slot == 0 and (lane0, lane1, replicated) != (fragments, 0, 0))
                or (slot == 1 and (lane0, lane1, replicated) != (0, fragments, 0))
                or (slot == 3 and (lane0, lane1, replicated) != (fragments, fragments, fragments))
                or (slot not in (0, 1, 3) and (lane0 + lane1 != fragments or abs(lane0 - lane1) > 1 or replicated != 0))
            ):
                failures.append(f"functional lane-policy descriptor counters mismatch for slot {slot}")
        functional_markers = parse_markers(raw_text)
        if functional_markers.get("P7_FUNCTIONAL_LARGE_POLICY_MATRIX_COMPLETE") != "1" or functional_markers.get(
            "P7_FUNCTIONAL_BOUNDARY_MATRIX_COMPLETE"
        ) != "1":
            failures.append("functional large-policy/boundary phase marker missing")
        if (
            functional_markers.get("P7_FUNCTIONAL_CHECKPOINT_4K_COMPLETE") != "1"
            or functional_markers.get("P7_FUNCTIONAL_EXECUTION_ORDER")
            != "BOUNDARY48_THEN_4K_THEN_64K4_THEN_1M4"
        ):
            failures.append("functional risk-increasing execution order/4KiB checkpoint marker missing")
        required_sizes = [0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024]
        if (
            functional_markers.get("P7_FUNCTIONAL_BOUNDARY_BATCHES") != "6"
            or functional_markers.get("P7_FUNCTIONAL_BOUNDARY_CASES") != "48"
            or len(bundle.boundary_cases) != 48
            or [len(case.request.data) for case in bundle.boundary_cases] != [size for size in required_sizes for _ in range(4)]
            or [case.request.lane_policy for case in bundle.boundary_cases] != [policy for _ in required_sizes for policy in (1, 2, 3, 4)]
            or [case.request.object_id for case in bundle.boundary_cases] != list(range(1, 49))
        ):
            failures.append("functional 12-size x 4-policy boundary matrix is not canonical")
        for case in bundle.boundary_cases:
            prefix = f"boundary_{case.slot}"
            descriptor_path = bundle.directory / f"{prefix}_descriptor_result.bin"
            output_path = bundle.directory / f"{prefix}_output_result.bin"
            trace_path = bundle.directory / f"{prefix}_trace_result.bin"
            local: list[str] = []
            if not descriptor_path.is_file() or descriptor_path.stat().st_size != P7_DESCRIPTOR_BYTES:
                local.append("descriptor missing/invalid")
                descriptor: dict[str, Any] = {}
            else:
                descriptor_raw = descriptor_path.read_bytes()
                descriptor = unpack_descriptor(descriptor_raw)
                output = output_path.read_bytes() if output_path.is_file() else b""
                validation = validate_completed(
                    case.request,
                    descriptor_raw,
                    output,
                    expected_completion_sequence=case.slot + 1,
                )
                local.extend(validation["failures"])
            traces, trace_failures = _parse_trace(trace_path, case)
            local.extend(trace_failures)
            if case.request.lane_policy == 1:
                expected_masks = [1] * len(traces)
            elif case.request.lane_policy == 2:
                expected_masks = [2] * len(traces)
            elif case.request.lane_policy == 4:
                expected_masks = [3] * len(traces)
            else:
                expected_masks = [1 if index % 2 == 0 else 2 for index in range(len(traces))]
            if [int(trace["lane_mask"]) for trace in traces] != expected_masks:
                local.append("trace lane-policy sequence mismatch")
            if descriptor:
                fragments = int(descriptor.get("fragments_total", 0))
                counters = (
                    int(descriptor.get("lane0_fragments", 0)),
                    int(descriptor.get("lane1_fragments", 0)),
                    int(descriptor.get("replicated_fragments", 0)),
                )
                expected_counters = {
                    1: (fragments, 0, 0),
                    2: (0, fragments, 0),
                    3: ((fragments + 1) // 2, fragments // 2, 0),
                    4: (fragments, fragments, fragments),
                }[case.request.lane_policy]
                if counters != expected_counters:
                    local.append("descriptor lane-policy counters mismatch")
            failures.extend(f"functional boundary slot {case.slot}: {item}" for item in local)
            boundary_results.append(
                {
                    "slot": case.slot,
                    "length": len(case.request.data),
                    "passed": not local,
                    "failures": local,
                    "descriptor": {key: value for key, value in descriptor.items() if key != "words"},
                    "trace_entries": traces,
                }
            )
        checkpoint = bundle.functional_checkpoint
        checkpoint_local: list[str] = []
        checkpoint_descriptor: dict[str, Any] = {}
        checkpoint_traces: list[dict[str, int]] = []
        if checkpoint is None:
            checkpoint_local.append("checkpoint request missing")
        else:
            checkpoint_prefix = "functional_checkpoint_4k"
            checkpoint_descriptor_path = bundle.directory / f"{checkpoint_prefix}_descriptor_result.bin"
            checkpoint_output_path = bundle.directory / f"{checkpoint_prefix}_output_result.bin"
            checkpoint_trace_path = bundle.directory / f"{checkpoint_prefix}_trace_result.bin"
            if not checkpoint_descriptor_path.is_file() or checkpoint_descriptor_path.stat().st_size != P7_DESCRIPTOR_BYTES:
                checkpoint_local.append("descriptor missing/invalid")
            else:
                checkpoint_raw = checkpoint_descriptor_path.read_bytes()
                checkpoint_descriptor = unpack_descriptor(checkpoint_raw)
                checkpoint_output = checkpoint_output_path.read_bytes() if checkpoint_output_path.is_file() else b""
                checkpoint_validation = validate_completed(
                    checkpoint.request,
                    checkpoint_raw,
                    checkpoint_output,
                    expected_completion_sequence=49,
                )
                checkpoint_local.extend(checkpoint_validation["failures"])
            checkpoint_traces, checkpoint_trace_failures = _parse_trace(checkpoint_trace_path, checkpoint)
            checkpoint_local.extend(checkpoint_trace_failures)
            expected_checkpoint_masks = [1 if index % 2 == 0 else 2 for index in range(len(checkpoint_traces))]
            if [int(trace["lane_mask"]) for trace in checkpoint_traces] != expected_checkpoint_masks:
                checkpoint_local.append("trace is not exact stripe round-robin")
        failures.extend(f"functional 4KiB checkpoint: {item}" for item in checkpoint_local)
        functional_checkpoint_result = {
            "passed": not checkpoint_local,
            "failures": checkpoint_local,
            "descriptor": {key: value for key, value in checkpoint_descriptor.items() if key != "words"},
            "trace_entries": checkpoint_traces,
        }
        observed_main_sequences = {
            int(item["slot"]): int(item.get("descriptor", {}).get("completion_sequence", 0)) for item in case_results
        }
        expected_main_sequences = {**{slot: 54 + slot for slot in range(4)}, **{slot: 50 + slot - 4 for slot in range(4, 8)}}
        if observed_main_sequences != expected_main_sequences:
            failures.append("functional 64KiB/1MiB completion sequence does not follow the risk-increasing order")
        if mailbox and (
            mailbox["objects_completed"] != P7_QUEUE_DEPTH + len(bundle.boundary_cases) + 1
            or mailbox["objects_failed"] != 0
            or mailbox["completion_sequence"] != P7_QUEUE_DEPTH + len(bundle.boundary_cases) + 1
        ):
            failures.append("functional final mailbox does not prove all 57 boundary/checkpoint/large objects")
    if mode == "stationary" and mailbox:
        if mailbox["max_runtime_seconds"] != MAX_SERVICE_RUNTIME_SEC:
            failures.append("stationary mailbox runtime is not exactly 1800 seconds")
        if not (mailbox["runtime_flags"] & P7_RUNTIME_DEADLINE_REACHED):
            failures.append("stationary service did not reach its automatic runtime deadline")
        if mailbox["calibration_window_seconds"] != CALIBRATION_SEC:
            failures.append("stationary mailbox calibration window is not 300 seconds")
        if markers.get("P7_CALIBRATION_WINDOW_COMPLETE") != "1":
            failures.append("stationary calibration completion marker missing")
        if markers.get("P7_ACCEPTANCE_WINDOW_COMPLETE") != "1":
            failures.append("stationary acceptance completion marker missing")
        if markers.get("P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION") != "0":
            failures.append("stationary scheduler requeued work after the idle cutoff")
        try:
            stationary_wall_seconds = float(markers.get("P7_STATIONARY_WALL_SECONDS", "nan"))
        except ValueError:
            stationary_wall_seconds = float("nan")
        if not 1800.0 <= stationary_wall_seconds <= 1801.5:
            failures.append("stationary observed wall duration is outside 1800.0..1801.5 seconds")
        mailbox["observed_wall_seconds"] = stationary_wall_seconds
        required_elapsed_ticks = MAX_SERVICE_RUNTIME_SEC * P7_COUNTS_PER_SECOND
        if int(mailbox["runtime_elapsed_ticks"]) < required_elapsed_ticks:
            failures.append("stationary mailbox runtime elapsed ticks do not prove a full 1800 seconds")
        mailbox["required_runtime_elapsed_ticks"] = required_elapsed_ticks
        try:
            drain_elapsed = float(markers.get("P7_STATIONARY_DRAIN_COMPLETE_ELAPSED", "nan"))
        except ValueError:
            drain_elapsed = float("nan")
        if not bundle.scheduling_cutoff_sec <= drain_elapsed <= 1790.0:
            failures.append("stationary queue drain marker is missing or outside cutoff..1790 seconds")
        mailbox["drain_complete_elapsed_sec"] = drain_elapsed
        if mailbox["objects_completed"] < 1 or mailbox["objects_failed"] != 0:
            failures.append("stationary object counters are not clean")
        terminal_marker = markers.get("P7_STATIONARY_TERMINAL_DESCRIPTORS", "")
        expected_terminal = int(terminal_marker) if terminal_marker.isdecimal() else -1
        if expected_terminal < len(bundle.cases) or len(stationary_objects) != expected_terminal:
            failures.append("stationary per-object terminal evidence count mismatch")
        if [item["sequence"] for item in stationary_objects] != list(range(1, len(stationary_objects) + 1)):
            failures.append("stationary per-object terminal sequence is not contiguous")
        if int(mailbox["objects_completed"]) != len(stationary_objects):
            failures.append("stationary mailbox completed count does not match per-object evidence")
        identities: set[tuple[int, int]] = set()
        per_slot_generations: dict[int, list[int]] = {slot: [] for slot in range(P7_QUEUE_DEPTH)}
        for item in stationary_objects:
            case = bundle.cases[int(item["slot"])]
            per_slot_generations[int(item["slot"])].append(int(item["generation"]))
            identity = (int(item["session_epoch"]), int(item["object_id"]))
            if identity in identities:
                failures.append("stationary object identity was reused")
            identities.add(identity)
            if (
                item["session_epoch"] != case.request.session_epoch
                or item["status"] != P7_DESCRIPTOR_COMPLETE
                or item["error_code"] != 0
                or item["bytes_completed"] != len(case.request.data)
                or item["fragments_completed"] != case.trace_capacity
                or item["fragments_total"] != case.trace_capacity
                or item["output_sha256"] != hashlib.sha256(case.request.data).hexdigest()
                or int(item["fragment_attempts"]) != case.trace_capacity
                or int(item["p6_retry_count"]) > int(item["fragment_attempts"]) * case.request.max_retries
                or int(item["start_ticks"]) >= int(item["end_ticks"])
                or int(item["completion_sequence"]) != int(item["sequence"])
            ):
                failures.append(f"stationary object terminal integrity mismatch: sequence={item['sequence']}")
            if any(
                int(item[key]) != 0
                for key in ("p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad", "p6_payload_mismatch", "duty_violations")
            ) or int(item["max_txd_high_cycles"]) > 8:
                failures.append(f"stationary object safety failure: sequence={item['sequence']}")
            lane0 = int(item["lane0_fragments"])
            lane1 = int(item["lane1_fragments"])
            replicated = int(item["replicated_fragments"])
            if case.request.lane_policy == 1 and (lane0, lane1, replicated) != (case.trace_capacity, 0, 0):
                failures.append(f"stationary lane0-only semantics mismatch: sequence={item['sequence']}")
            elif case.request.lane_policy == 2 and (lane0, lane1, replicated) != (0, case.trace_capacity, 0):
                failures.append(f"stationary lane1-only semantics mismatch: sequence={item['sequence']}")
            elif case.request.lane_policy == 4 and (
                lane0, lane1, replicated
            ) != (case.trace_capacity, case.trace_capacity, case.trace_capacity):
                failures.append(f"stationary replicate/mask0x3 semantics mismatch: sequence={item['sequence']}")
            elif case.request.lane_policy == 3 and case.request.unavailable_lane_mask == 0 and (
                lane0 < 1 or lane1 < 1 or abs(lane0 - lane1) > 1 or replicated != 0 or lane0 + lane1 != case.trace_capacity
            ):
                failures.append(f"stationary stripe distribution mismatch: sequence={item['sequence']}")
            if case.request.lane_policy == 3 and case.request.unavailable_lane_mask == 1 and (
                int(item["fallback_count"]) < 1
                or lane0 != 1
                or lane1 != case.trace_capacity - 1
                or replicated != 0
            ):
                failures.append(f"stationary lane0 controlled fallback mismatch: sequence={item['sequence']}")
            if case.request.lane_policy == 3 and case.request.unavailable_lane_mask == 2 and (
                int(item["fallback_count"]) < 1
                or lane1 != 1
                or lane0 != case.trace_capacity - 1
                or replicated != 0
            ):
                failures.append(f"stationary lane1 controlled fallback mismatch: sequence={item['sequence']}")
        for slot, generations in per_slot_generations.items():
            if generations and generations != list(range(len(generations))):
                failures.append(f"stationary generation sequence mismatch for slot {slot}")
        ledger_bytes = sum(int(item["bytes_completed"]) for item in stationary_objects)
        ledger_fragments = sum(int(item["fragments_completed"]) for item in stationary_objects)
        ledger_lane0 = sum(int(item["lane0_fragments"]) for item in stationary_objects)
        ledger_lane1 = sum(int(item["lane1_fragments"]) for item in stationary_objects)
        ledger_replicated = sum(int(item["replicated_fragments"]) for item in stationary_objects)
        ledger_fallbacks = sum(int(item["fallback_count"]) for item in stationary_objects)
        ledger_retries = sum(int(item["p6_retry_count"]) for item in stationary_objects)
        if (
            int(mailbox["completion_sequence"]) != len(stationary_objects)
            or int(mailbox["objects_completed"]) != len(stationary_objects)
            or int(mailbox["bytes_completed"]) != ledger_bytes
            or int(mailbox["fragments_completed"]) != ledger_fragments
        ):
            failures.append("stationary final mailbox counters do not reconcile to the terminal ledger")
        mailbox["stationary_terminal_evidence_count"] = len(stationary_objects)
        completed_policies = {
            bundle.cases[int(item["slot"])].request.lane_policy for item in stationary_objects
        }
        if completed_policies != {1, 2, 3, 4}:
            failures.append("stationary terminal ledger does not cover lane0/lane1/stripe/replicate policies")
        if markers.get("P7_STATIONARY_FAULT_MODEL") != "SOFTWARE_INJECTED_BIDIRECTIONAL_CONTROLLED_FALLBACK":
            failures.append("stationary controlled-fallback evidence label missing")
        final_results_by_slot = {int(item["slot"]): item for item in case_results}
        for case in bundle.cases:
            item = final_results_by_slot.get(case.slot)
            if item is None:
                continue
            traces = item.get("trace_entries", [])
            for trace in traces:
                index = int(trace["fragment_index"])
                lane_mask = int(trace["lane_mask"])
                if case.request.lane_policy == 1 and lane_mask != 1:
                    failures.append(f"stationary final lane0-only trace mismatch: slot {case.slot}")
                elif case.request.lane_policy == 2 and lane_mask != 2:
                    failures.append(f"stationary final lane1-only trace mismatch: slot {case.slot}")
                elif case.request.lane_policy == 4 and lane_mask != 3:
                    failures.append(f"stationary final replicate trace omitted mask0x3: slot {case.slot}")
                elif case.request.lane_policy == 3 and case.request.unavailable_lane_mask == 0:
                    expected_mask = 1 if index % 2 == 0 else 2
                    if lane_mask != expected_mask:
                        failures.append(f"stationary final stripe trace mismatch: slot {case.slot}")
                elif case.request.lane_policy == 3:
                    expected_mask = 1 if index % 2 == 0 else 2
                    if index >= case.request.unavailable_after_fragment and expected_mask & case.request.unavailable_lane_mask:
                        expected_mask = 2 if expected_mask == 1 else 1
                    if lane_mask != expected_mask:
                        failures.append(f"stationary final controlled-fallback trace mismatch: slot {case.slot}")
            if case.request.unavailable_lane_mask:
                if int(item.get("descriptor", {}).get("fallback_count", 0)) < 1:
                    failures.append(f"stationary final slot {case.slot} omitted fallback count")
                for trace in traces:
                    index = int(trace["fragment_index"])
                    lane_mask = int(trace["lane_mask"])
                    if index >= case.request.unavailable_after_fragment and lane_mask & case.request.unavailable_lane_mask:
                        failures.append(f"stationary final slot {case.slot} transmitted on injected-unavailable lane")
        sample_pattern = re.compile(
            r"^P7_SAMPLE_[0-9]{5}=ELAPSED_([0-9.]+),ELAPSED_TICKS_([0-9]+),"
            r"WINDOW_(CALIBRATION|ACCEPTANCE),OBJECTS_([0-9]+),FAILED_([0-9]+),"
            r"BYTES_HI_([0-9A-Fa-f]{8}),BYTES_LO_([0-9A-Fa-f]{8}),FRAGMENTS_([0-9]+),"
            r"LANE0_([0-9]+),LANE1_([0-9]+),REPLICATED_([0-9]+),FALLBACKS_([0-9]+),"
            r"P6_RETRIES_([0-9]+),P6_RETRY_EXHAUSTED_([0-9]+),P6_TX_FAIL_([0-9]+),"
            r"P6_CRC_BAD_([0-9]+),P6_PAYLOAD_MISMATCH_([0-9]+),MAX_TXD_HIGH_([0-9]+),"
            r"DUTY_VIOLATIONS_([0-9]+),QUEUE_OCCUPANCY_([0-9]+),QUEUE_HIGH_([0-9]+),"
            r"BACKPRESSURE_([0-9]+),QUEUE_OBS_NOT_BEFORE_TICKS_([0-9]+),CURRENT_BPS_([0-9]+),"
            r"ROLLING_BPS_([0-9]+),LATENCY_COUNT_([0-9]+),LATENCY_MIN_TICKS_([0-9]+),"
            r"LATENCY_MEAN_TICKS_([0-9]+),LATENCY_P50_TICKS_([0-9]+),"
            r"LATENCY_P95_TICKS_([0-9]+),LATENCY_P99_TICKS_([0-9]+),"
            r"LATENCY_MAX_TICKS_([0-9]+),LAST_OBJECT_([0-9]+)$"
        )
        samples = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            match = sample_pattern.fullmatch(stripped)
            if not match:
                continue
            samples.append(
                {
                    "sequence": int(stripped[10:15]),
                    "elapsed_sec": float(match.group(1)),
                    "elapsed_ticks": int(match.group(2)),
                    "window": match.group(3),
                    "objects": int(match.group(4)),
                    "failed": int(match.group(5)),
                    "bytes": (int(match.group(6), 16) << 32) | int(match.group(7), 16),
                    "fragments": int(match.group(8)),
                    "lane0": int(match.group(9)),
                    "lane1": int(match.group(10)),
                    "replicated": int(match.group(11)),
                    "fallbacks": int(match.group(12)),
                    "p6_retries": int(match.group(13)),
                    "p6_retry_exhausted": int(match.group(14)),
                    "p6_tx_fail": int(match.group(15)),
                    "p6_crc_bad": int(match.group(16)),
                    "p6_payload_mismatch": int(match.group(17)),
                    "max_txd_high": int(match.group(18)),
                    "duty_violations": int(match.group(19)),
                    "queue_occupancy": int(match.group(20)),
                    "queue_high": int(match.group(21)),
                    "backpressure": int(match.group(22)),
                    "queue_observation_not_before_ticks": int(match.group(23)),
                    "current_bps": int(match.group(24)),
                    "rolling_bps": int(match.group(25)),
                    "latency_count": int(match.group(26)),
                    "latency_min_ticks": int(match.group(27)),
                    "latency_mean_ticks": int(match.group(28)),
                    "latency_p50_ticks": int(match.group(29)),
                    "latency_p95_ticks": int(match.group(30)),
                    "latency_p99_ticks": int(match.group(31)),
                    "latency_max_ticks": int(match.group(32)),
                    "last_object": int(match.group(33)),
                }
            )
        if len(samples) != 60 or [int(item["sequence"]) for item in samples] != list(range(1, 61)):
            failures.append(f"stationary sample sequence must be exactly 1..60: observed={len(samples)}")
        canonical_samples, canonical_sample_failures = _canonical_stationary_samples(
            stationary_objects,
            runtime_start_ticks=int(mailbox.get("runtime_start_ticks", 0)),
            counts_per_second=P7_COUNTS_PER_SECOND,
            sample_interval_seconds=int(mailbox.get("sample_interval_seconds", 0)),
            runtime_seconds=MAX_SERVICE_RUNTIME_SEC,
        )
        failures.extend(canonical_sample_failures)
        monotonic_fields = (
            "objects", "bytes", "fragments", "lane0", "lane1", "replicated", "fallbacks", "p6_retries",
            "p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad", "p6_payload_mismatch", "max_txd_high",
            "duty_violations", "queue_high", "backpressure",
        )
        for index, sample in enumerate(samples):
            if index and float(sample["elapsed_sec"]) <= float(samples[index - 1]["elapsed_sec"]):
                failures.append("stationary sample elapsed times are not strictly increasing")
            if index:
                for key in monotonic_fields:
                    if int(sample[key]) < int(samples[index - 1][key]):
                        failures.append(f"stationary sample counter regressed: {key}")
            if int(sample["failed"]) != 0 or any(
                int(sample[key]) != 0
                for key in ("p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad", "p6_payload_mismatch", "duty_violations")
            ):
                failures.append("stationary sample reported object/P6/safety failure")
            if not 0 <= int(sample["queue_occupancy"]) <= P7_QUEUE_DEPTH or not 0 <= int(sample["queue_high"]) <= P7_QUEUE_DEPTH:
                failures.append("stationary sample queue depth is outside 0..8")
            if int(sample["max_txd_high"]) > 8:
                failures.append("stationary sample exceeded continuous TXD-high limit")
            latency_values = [
                int(sample["latency_min_ticks"]), int(sample["latency_mean_ticks"]), int(sample["latency_p50_ticks"]),
                int(sample["latency_p95_ticks"]), int(sample["latency_p99_ticks"]), int(sample["latency_max_ticks"]),
            ]
            if int(sample["latency_count"]) == 0:
                if any(latency_values):
                    failures.append("stationary empty latency sample contains nonzero values")
            elif not (
                0 < latency_values[0]
                <= latency_values[2]
                <= latency_values[3]
                <= latency_values[4]
                <= latency_values[5]
                and latency_values[0] <= latency_values[1] <= latency_values[5]
            ):
                failures.append("stationary sample latency summary is inconsistent")
            if int(sample["objects"]) > 0 and int(sample["last_object"]) == 0:
                failures.append("stationary sample omitted the last completed object ID")
            if int(sample["queue_observation_not_before_ticks"]) < int(sample["elapsed_ticks"]):
                failures.append("stationary queue observation predates its canonical PS threshold")
            if index < len(canonical_samples):
                expected_sample = canonical_samples[index]
                for key in (
                    "sequence",
                    "elapsed_ticks",
                    "window",
                    "objects",
                    "failed",
                    "bytes",
                    "fragments",
                    "lane0",
                    "lane1",
                    "replicated",
                    "fallbacks",
                    "p6_retries",
                    "p6_retry_exhausted",
                    "p6_tx_fail",
                    "p6_crc_bad",
                    "p6_payload_mismatch",
                    "max_txd_high",
                    "duty_violations",
                    "current_bps",
                    "rolling_bps",
                    "latency_count",
                    "latency_min_ticks",
                    "latency_mean_ticks",
                    "latency_p50_ticks",
                    "latency_p95_ticks",
                    "latency_p99_ticks",
                    "latency_max_ticks",
                    "last_object",
                ):
                    if sample[key] != expected_sample[key]:
                        failures.append(
                            "stationary sample differs from fixed-threshold terminal reconstruction: "
                            f"sequence={sample['sequence']} key={key} expected={expected_sample[key]} observed={sample[key]}"
                        )
                if abs(float(sample["elapsed_sec"]) - float(expected_sample["elapsed_sec"])) > 0.000001:
                    failures.append(
                        "stationary sample elapsed seconds differ from its exact PS tick threshold"
                    )
        calibration_samples = [item for item in samples if item["window"] == "CALIBRATION"]
        acceptance_samples = [item for item in samples if item["window"] == "ACCEPTANCE"]
        if len(calibration_samples) != 10 or len(acceptance_samples) != 50:
            failures.append("stationary samples must contain exactly 10 calibration plus 50 acceptance points")
        if calibration_samples and acceptance_samples:
            calibration_median = float(statistics.median(int(item["rolling_bps"]) for item in calibration_samples))
            acceptance_median = float(statistics.median(int(item["rolling_bps"]) for item in acceptance_samples))
            if calibration_median <= 0 or acceptance_median <= 0:
                failures.append("stationary rolling-goodput medians must both be positive")
            elif acceptance_median < 0.80 * calibration_median:
                failures.append("stationary acceptance rolling-goodput median fell below 80% of calibration median")
            mailbox["calibration_rolling_goodput_median_bps"] = calibration_median
            mailbox["acceptance_rolling_goodput_median_bps"] = acceptance_median
        if samples:
            last_sample = samples[-1]
            if (
                float(last_sample["elapsed_sec"]) != 1800.0
                or int(last_sample["elapsed_ticks"]) != required_elapsed_ticks
                or markers.get("P7_SAMPLE_00060_SAFE_TERMINAL_STATE") != "1"
                or markers.get("P7_SAMPLE_SEQUENCE_WRITER") != "HOST_POST_TERMINAL"
                or int(mailbox["last_sample_sequence"]) != 60
            ):
                failures.append("stationary final sample is not bound to the safe terminal 1800-second state")
            expected_final_sample = {
                "objects": len(stationary_objects),
                "bytes": ledger_bytes,
                "fragments": ledger_fragments,
                "lane0": ledger_lane0,
                "lane1": ledger_lane1,
                "replicated": ledger_replicated,
                "fallbacks": ledger_fallbacks,
                "p6_retries": ledger_retries,
            }
            for key, expected in expected_final_sample.items():
                if int(last_sample[key]) != expected:
                    failures.append(f"stationary final sample does not reconcile to terminal ledger: {key}")
            if max(int(item["queue_high"]) for item in samples) != P7_QUEUE_DEPTH:
                failures.append("stationary samples never recorded the full 8-entry queue high-water mark")
        stationary_trace_validation, fragment_latency_ticks, trace_evidence_failures = (
            _stationary_trace_evidence(bundle, stationary_objects, raw_text)
        )
        failures.extend(trace_evidence_failures)
        application_metrics, application_metric_failures = _stationary_application_metrics(
            bundle,
            stationary_objects,
            mailbox,
            raw_text,
            stationary_trace_validation,
            fragment_latency_ticks,
        )
        failures.extend(application_metric_failures)
        mailbox["metrics_time_sources"] = (
            "ps_global_timer_for_scheduler_samples_goodput_fragment_and_object_latency;"
            "host_wall_clock_for_preload_and_independent_duration_watchdog"
        )
    return {
        "passed": not failures,
        "failures": failures,
        "mailbox": {key: value for key, value in mailbox.items() if key != "words"},
        "cases": case_results,
        "boundary_cases": boundary_results,
        "functional_checkpoint": functional_checkpoint_result,
        "stationary_objects": stationary_objects,
        "stationary_samples": samples,
        "stationary_trace_validation": stationary_trace_validation,
        "application_metrics": application_metrics,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P7 PS application safe runner; default dry-run only.")
    add_common_arguments(parser)
    parser.add_argument("--mode", choices=MODE_NAMES, default="functional")
    parser.add_argument("--stage-name", default="p7_ps_application")
    parser.add_argument("--input-file", default="")
    parser.add_argument("--input-sha256", default="")
    parser.add_argument("--ps7-init", default="")
    parser.add_argument("--ps7-init-sha256", default="")
    parser.add_argument("--p6-build-summary", default=str(P6_BUILD_SUMMARY_DEFAULT.relative_to(ROOT)))
    parser.add_argument("--p6-build-summary-sha256", default="")
    parser.add_argument("--p7-build-summary", default=str(P7_BUILD_SUMMARY_DEFAULT.relative_to(ROOT)))
    parser.add_argument("--p7-build-summary-sha256", default="")
    parser.add_argument("--core-readiness-attestation", default=str(CORE_READINESS_DEFAULT.relative_to(ROOT)))
    parser.add_argument("--core-readiness-attestation-sha256", default="")
    parser.add_argument("--active-profile", default=str(ACTIVE_PROFILE_DEFAULT.relative_to(ROOT)))
    parser.add_argument("--active-profile-sha256", default="")
    parser.add_argument("--lane1-promotion-summary", default=str(LANE1_PROMOTION_DEFAULT.relative_to(ROOT)))
    parser.add_argument("--lane1-promotion-summary-sha256", default="")
    parser.add_argument("--xsdb-path", default="")
    parser.add_argument("--jtag-frequency-hz", type=int, default=1_000_000)
    parser.add_argument("--preflight-timeout-sec", type=int, default=180)
    parser.add_argument("--shutdown-timeout-sec", type=int, default=240)
    parser.add_argument("--calibration-sec", type=int, default=0)
    parser.add_argument("--acceptance-sec", type=int, default=0)
    parser.add_argument("--sample-interval-sec", type=int, default=10)
    parser.add_argument("--idle-deadline-margin-sec", type=int, default=60)
    parser.add_argument("--stationary-object-bytes", type=int, default=64 * 1024)
    parser.add_argument("--evidence-dir", default="")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def _base_summary(
    args: argparse.Namespace,
    safety: dict[str, Any],
    stage_errors: list[str],
    core_readiness: dict[str, Any],
) -> dict[str, Any]:
    return {
        "P7_PS_APPLICATION_SAFE_STAGE": "DRY_RUN_ONLY",
        "generated_at_utc": now_utc(),
        "mode": args.mode,
        "stage_name": args.stage_name,
        "requested_execute_hardware": bool(args.execute_hardware),
        "hardware_actions_executed": False,
        "programmed_fpga": False,
        "programmed_candidate": False,
        "started_ps_elf": False,
        "programmed_shutdown_before": False,
        "programmed_shutdown_after": False,
        "drove_tfdu_txd": False,
        "enabled_tfdu_receiver": False,
        "uart_access": False,
        "network_used": False,
        "ethernet_used": False,
        "motion_used": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "service_runtime_limit_sec": args.max_runtime_sec,
        "safety_validation": safety,
        "stage_validation_errors": stage_errors,
        "core_hardware_readiness": core_readiness,
        "raw_exit_policy": "every_process_must_return_exactly_zero_and_match_fresh_markers",
        "output_atomicity": "temp_fsync_replace_for_host_outputs_and_partial_rename_for_XSDB_dumps",
    }


def _emit(summary: dict[str, Any], args: argparse.Namespace, evidence_dir: Path | None = None) -> None:
    if evidence_dir is not None:
        atomic_write_json(evidence_dir / "p7_ps_application_stage_summary.json", summary)
    if args.json_summary:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    else:
        print(f"P7_PS_APPLICATION_SAFE_STAGE: {summary['P7_PS_APPLICATION_SAFE_STAGE']}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.max_runtime_sec is None:
        args.max_runtime_sec = MAX_SERVICE_RUNTIME_SEC if args.mode == "stationary" else 900
    if args.mode == "stationary":
        if args.calibration_sec == 0:
            args.calibration_sec = CALIBRATION_SEC
        if args.acceptance_sec == 0:
            args.acceptance_sec = ACCEPTANCE_SEC
        if args.sample_interval_sec == 10:
            args.sample_interval_sec = 30
    safety = validate_request(args)
    core_readiness = validate_core_readiness(args)
    stage_errors = _stage_validation(args, core_readiness)
    summary = _base_summary(args, safety, stage_errors, core_readiness)
    all_errors = list(safety["errors"]) + stage_errors
    if not args.execute_hardware:
        summary["reason"] = "default dry-run; no Vivado, XSDB, hw_server, target, FPGA, ELF, or memory access occurred"
        evidence_dir = resolve_path(args.evidence_dir) if args.evidence_dir else None
        _emit(summary, args, evidence_dir)
        return 0
    if all_errors:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "BLOCKED"
        summary["reason"] = "authorization, source, profile, artifact, input, or target controls failed before hardware"
        summary["all_validation_errors"] = all_errors
        evidence_dir = resolve_path(args.evidence_dir) if args.evidence_dir else None
        _emit(summary, args, evidence_dir)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence_dir = (
        resolve_path(args.evidence_dir)
        if args.evidence_dir
        else ROOT / "evidence" / "hardware" / "p7" / "ps_application" / args.mode / stamp
    )
    if evidence_dir.exists() and (
        evidence_dir.is_symlink() or not evidence_dir.is_dir() or any(evidence_dir.iterdir())
    ):
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "BLOCKED_EVIDENCE_DIR"
        summary["reason"] = "hardware run evidence directory must be a new unique path or an existing empty directory"
        summary["evidence_dir"] = str(evidence_dir)
        _emit(summary, args)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)
    events: list[dict[str, Any]] = []

    def event(name: str, **fields: Any) -> None:
        events.append({"timestamp_utc": now_utc(), "event": name, **fields})

    bundle = build_stage_bundle(
        bundle_dir=evidence_dir / "bundle",
        mode=args.mode,
        input_path=resolve_path(args.input_file),
        max_runtime_sec=args.max_runtime_sec,
        calibration_sec=args.calibration_sec,
        acceptance_sec=args.acceptance_sec,
        sample_interval_sec=args.sample_interval_sec,
        idle_margin_sec=args.idle_deadline_margin_sec,
        stationary_object_bytes=args.stationary_object_bytes,
    )
    summary["evidence_dir"] = str(evidence_dir)
    summary["bundle_manifest"] = file_record(bundle.manifest_path)
    summary["execution_plan"] = file_record(bundle.plan_path)
    summary["scheduling_cutoff_sec"] = bundle.scheduling_cutoff_sec
    abort_file = DEFAULT_ABORT_FILE.resolve(strict=False)
    try:
        frozen_shutdown, frozen_shutdown_payload = freeze_shutdown_bit(args)
        verify_bundle_integrity(bundle)
        bundle_pre_run_snapshot = snapshot_directory_files(bundle.directory)
    except Exception as exc:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "BLOCKED_PREPARE"
        summary["reason"] = f"verified bundle/shutdown freeze failed before hardware: {type(exc).__name__}: {exc}"
        _emit(summary, args, evidence_dir)
        return 2
    summary["frozen_shutdown"] = file_record(frozen_shutdown)
    summary["bundle_pre_run_file_count"] = len(bundle_pre_run_snapshot)
    try:
        hardware_lock = HardwareExecutionLock.acquire(
            owner={
                "wrapper": "run_p7_ps_application_stage_safe.py",
                "mode": args.mode,
                "stage_name": args.stage_name,
                "acquired_at_utc": now_utc(),
                "evidence_dir": str(evidence_dir),
            }
        )
    except RuntimeError as exc:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "BLOCKED_HARDWARE_LOCK"
        summary["reason"] = str(exc)
        _emit(summary, args, evidence_dir)
        return 2
    summary["hardware_execution_lock"] = hardware_lock.record()
    event("authorized_execution_begin", mode=args.mode)

    preflight_final = evidence_dir / "p7_hw_preflight_result.txt"
    preflight_partial = _atomic_result_path(preflight_final)
    preflight_proc = _atomic_process(
        name="preflight",
        command=build_preflight_command(args, preflight_partial),
        evidence_dir=evidence_dir,
        timeout_sec=args.preflight_timeout_sec,
        abort_file=abort_file,
        watch_abort=True,
    )
    _promote_result(preflight_partial, preflight_final)
    summary["hardware_actions_executed"] = True
    preflight_text = preflight_final.read_text(encoding="utf-8", errors="replace") if preflight_final.is_file() else ""
    preflight_stdout = Path(preflight_proc.stdout_path).read_text(encoding="utf-8", errors="replace")
    preflight_ok, preflight_failures = evaluate_preflight(
        returncode=preflight_proc.returncode,
        stdout=preflight_stdout,
        result_text=preflight_text,
        expected_board_id=args.board_id,
        expected_part=args.expected_part,
        expected_target=args.expected_target,
    )
    summary["preflight"] = {**_process_record(preflight_proc), "passed": preflight_ok, "failures": preflight_failures}
    summary["target_identity"] = parse_markers(preflight_text)
    preflight_sha256 = sha256_file(preflight_final) if preflight_final.is_file() else "MISSING"
    event("preflight_finished", returncode=preflight_proc.returncode, passed=preflight_ok)
    if not preflight_ok:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "FAIL_PREFLIGHT"
        summary["reason"] = "exact read-only board/part/target preflight failed"
        event("authorized_execution_end", status=summary["P7_PS_APPLICATION_SAFE_STAGE"])
        atomic_write_json(evidence_dir / "p7_ps_application_events.json", {"events": events})
        _emit(summary, args, evidence_dir)
        hardware_lock.release()
        return 1

    before_ok = False
    after_ok = False
    ps_process_ok = False
    ps_failures: list[str] = []
    internal_error = ""
    candidate_child_reaped = False
    candidate_returncode: int | None = None
    raw_final = evidence_dir / "p7_ps_application_raw_result.log"
    try:
        for value, expected, label in (
            (args.authorization_file, args.authorization_sha256, "authorization file"),
            (str(frozen_shutdown), args.shutdown_bitstream_sha256, "frozen shutdown bitstream"),
        ):
            error = _verify_hash(value, expected, label)
            if error:
                raise RuntimeError(error)
        before_final = evidence_dir / "shutdown_before_result.txt"
        before_partial = _atomic_result_path(before_final)
        before_proc = _atomic_process(
            name="shutdown_before",
            command=build_shutdown_command(args, before_partial, frozen_shutdown),
            evidence_dir=evidence_dir,
            timeout_sec=args.shutdown_timeout_sec,
            abort_file=abort_file,
            watch_abort=False,
        )
        _promote_result(before_partial, before_final)
        before_stdout = Path(before_proc.stdout_path).read_text(encoding="utf-8", errors="replace")
        before_text = before_final.read_text(encoding="utf-8", errors="replace") if before_final.is_file() else ""
        before_ok, before_failures = process_support.evaluate_shutdown(before_proc.returncode, before_stdout, before_text)
        summary["shutdown_before"] = {**_process_record(before_proc), "passed": before_ok, "failures": before_failures}
        summary["programmed_shutdown_before"] = before_ok
        summary["programmed_fpga"] = before_ok
        event("shutdown_before_finished", returncode=before_proc.returncode, passed=before_ok)
        if not before_ok:
            raise RuntimeError("shutdown-before requires rc=0 plus TFDU_SHUTDOWN_PROGRAMMED")
        if abort_file.exists():
            raise RuntimeError("operator abort file appeared before PS candidate stage")
        for value, expected, label in (
            (args.authorization_file, args.authorization_sha256, "authorization file"),
            (args.bitstream, args.bitstream_sha256, "P6 PS bitstream"),
            (args.xsa, args.xsa_sha256, "P6 PS XSA"),
            (args.elf, args.elf_sha256, "P7 ELF"),
            (args.profile, args.profile_sha256, "P7 profile"),
            (args.active_profile, args.active_profile_sha256, "active profile"),
            (args.lane1_promotion_summary, args.lane1_promotion_summary_sha256, "lane1 promotion summary"),
            (args.ps7_init, args.ps7_init_sha256, "PS7 init"),
            (args.input_file, args.input_sha256, "input file"),
            (args.p6_build_summary, args.p6_build_summary_sha256, "P6 build summary"),
            (args.p7_build_summary, args.p7_build_summary_sha256, "P7 build summary"),
            (args.core_readiness_attestation, args.core_readiness_attestation_sha256, "core-readiness attestation"),
            (str(frozen_shutdown), args.shutdown_bitstream_sha256, "frozen shutdown bitstream"),
            (str(preflight_final), preflight_sha256, "fresh preflight attestation"),
        ):
            error = _verify_hash(value, expected, label)
            if error:
                raise RuntimeError(error)
        verify_bundle_integrity(bundle)
        raw_partial = _atomic_result_path(raw_final)
        summary["drove_tfdu_txd"] = True
        summary["enabled_tfdu_receiver"] = True
        summary["tfdu_activity_semantics"] = (
            "conservative_true_once_PS_candidate_ELF_command_is_launched"
        )
        event("candidate_started", mode=args.mode)
        ps_proc = _atomic_process(
            name="ps_application_stage",
            command=build_ps_command(args, bundle, preflight_final, raw_partial),
            evidence_dir=evidence_dir,
            timeout_sec=(args.max_runtime_sec if args.mode == "stationary" else args.max_runtime_sec + XSDB_PROCESS_GRACE_SEC),
            abort_file=abort_file,
            watch_abort=True,
            stationary_active_watchdog=args.mode == "stationary",
        )
        candidate_child_reaped = bool(ps_proc.process_tree_reaped)
        candidate_returncode = int(ps_proc.returncode)
        event(
            "candidate_child_reaped",
            process_tree_reaped=candidate_child_reaped,
            candidate_returncode=candidate_returncode,
        )
        _promote_result(raw_partial, raw_final)
        raw_text = raw_final.read_text(encoding="utf-8", errors="replace") if raw_final.is_file() else ""
        ps_stdout = Path(ps_proc.stdout_path).read_text(encoding="utf-8", errors="replace")
        ps_process_ok, ps_failures = evaluate_ps_process(
            ps_proc.returncode,
            ps_stdout,
            raw_text,
            mode=args.mode,
            target=args.expected_target,
            part=args.expected_part,
            board_id=args.board_id,
        )
        summary["ps_process"] = {**_process_record(ps_proc), "passed": ps_process_ok, "failures": ps_failures}
        markers = parse_markers(raw_text)
        summary["programmed_candidate"] = markers.get("P7_PS_CANDIDATE_PROGRAMMED") == "1"
        summary["programmed_fpga"] = bool(
            summary["programmed_fpga"] or summary["programmed_candidate"]
        )
        summary["started_ps_elf"] = markers.get("P7_PS_ELF_DOWNLOADED") == "1"
        event("ps_stage_finished", returncode=ps_proc.returncode, passed=ps_process_ok)
    except Exception as exc:
        internal_error = f"{type(exc).__name__}: {exc}"
        event("stage_exception", error=internal_error)
    finally:
        after_final = evidence_dir / "shutdown_after_result.txt"
        after_partial = _atomic_result_path(after_final)
        summary["child_reaped_before_shutdown_after"] = candidate_child_reaped
        event(
            "shutdown_after_started",
            candidate_child_reaped=candidate_child_reaped,
            candidate_returncode=candidate_returncode,
        )
        try:
            restore_frozen_shutdown(frozen_shutdown, frozen_shutdown_payload, args.shutdown_bitstream_sha256)
            after_proc = _atomic_process(
                name="shutdown_after",
                command=build_shutdown_command(args, after_partial, frozen_shutdown),
                evidence_dir=evidence_dir,
                timeout_sec=args.shutdown_timeout_sec,
                abort_file=abort_file,
                watch_abort=False,
            )
            _promote_result(after_partial, after_final)
            after_stdout = Path(after_proc.stdout_path).read_text(encoding="utf-8", errors="replace")
            after_text = after_final.read_text(encoding="utf-8", errors="replace") if after_final.is_file() else ""
            after_ok, after_failures = process_support.evaluate_shutdown(after_proc.returncode, after_stdout, after_text)
            summary["shutdown_after"] = {
                **_process_record(after_proc),
                "attempted": True,
                "passed": after_ok,
                "failures": after_failures,
            }
            summary["programmed_shutdown_after"] = after_ok
            summary["programmed_fpga"] = bool(summary["programmed_fpga"] or after_ok)
            event("shutdown_after_finished", returncode=after_proc.returncode, passed=after_ok)
        except Exception as shutdown_exc:
            after_ok = False
            summary["shutdown_after"] = {
                "attempted": False,
                "passed": False,
                "returncode": 126,
                "failures": [f"{type(shutdown_exc).__name__}: {shutdown_exc}"],
            }
            event("shutdown_after_failed_to_launch", reason=str(shutdown_exc))

    bundle_integrity_failures: list[str] = []
    try:
        verify_bundle_integrity(bundle)
        bundle_post_snapshot = snapshot_directory_files(bundle.directory)
        immutable_post = {key: bundle_post_snapshot.get(key) for key in bundle_pre_run_snapshot}
        if immutable_post != bundle_pre_run_snapshot:
            bundle_integrity_failures.append("bundle immutable inputs changed between pre-run and post-shutdown verification")
    except Exception as exc:
        bundle_integrity_failures.append(f"post-shutdown bundle verification failed: {type(exc).__name__}: {exc}")
        bundle_post_snapshot = {}
    summary["bundle_post_shutdown_verification"] = {
        "passed": not bundle_integrity_failures,
        "failures": bundle_integrity_failures,
        "immutable_pre_post_equal": not bundle_integrity_failures,
        "pre_run_file_count": len(bundle_pre_run_snapshot),
        "post_shutdown_file_count": len(bundle_post_snapshot),
    }
    raw_text = raw_final.read_text(encoding="utf-8", errors="replace") if raw_final.is_file() else ""
    postprocess = postprocess_bundle(bundle, args.mode, raw_text) if ps_process_ok else {
        "passed": False,
        "failures": ["PS process did not pass exact rc/marker policy"],
        "mailbox": {},
        "cases": [],
    }
    if bundle_integrity_failures:
        postprocess["passed"] = False
        postprocess.setdefault("failures", []).extend(bundle_integrity_failures)
    summary["postprocess"] = postprocess
    summary["internal_error"] = internal_error
    summary["ps_failures"] = ps_failures
    if (
        before_ok
        and ps_process_ok
        and postprocess["passed"]
        and after_ok
        and candidate_child_reaped
        and not internal_error
    ):
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "PASS"
        summary["reason"] = "authorized PS application stage and both shutdown barriers passed"
        returncode = 0
    elif not after_ok:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "FAIL_SHUTDOWN_AFTER"
        summary["reason"] = "hardware stage is incomplete without rc=0 plus shutdown marker"
        returncode = 1
    elif not before_ok:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "FAIL_SHUTDOWN_BEFORE"
        summary["reason"] = "candidate/ELF stage was refused because shutdown-before failed"
        returncode = 1
    else:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "FAIL_STAGE"
        summary["reason"] = "PS process, mailbox/descriptor/trace/output, or exact marker checks failed"
        returncode = 1
    event("authorized_execution_end", status=summary["P7_PS_APPLICATION_SAFE_STAGE"])
    atomic_write_json(evidence_dir / "p7_ps_application_events.json", {"events": events})
    try:
        evidence_manifest = write_evidence_sha256_manifest(evidence_dir)
        summary["raw_evidence_sha256_manifest"] = file_record(evidence_manifest)
        evidence_manifest_data = json.loads(evidence_manifest.read_text(encoding="utf-8"))
        if int(evidence_manifest_data.get("partial_file_count", -1)) != 0:
            summary["P7_PS_APPLICATION_SAFE_STAGE"] = "FAIL_EVIDENCE_MANIFEST"
            summary["reason"] = "post-shutdown evidence contains uncommitted partial files"
            summary["evidence_partial_files"] = evidence_manifest_data.get("partial_files", [])
            returncode = 1
    except Exception as exc:
        summary["P7_PS_APPLICATION_SAFE_STAGE"] = "FAIL_EVIDENCE_MANIFEST"
        summary["reason"] = "post-shutdown raw evidence SHA256 manifest generation failed"
        summary["evidence_manifest_error"] = f"{type(exc).__name__}: {exc}"
        returncode = 1
    _emit(summary, args, evidence_dir)
    hardware_lock.release()
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
