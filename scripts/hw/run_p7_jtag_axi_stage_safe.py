#!/usr/bin/env python3
"""Authorization-bound P7 direct JTAG/AXI stage wrapper.

The default path is dry-run only.  The hardware path is deliberately limited
to fixed Vivado Tcl entry points and a non-executable, host-validated
transaction DSL.  It never sets RF_COMM_HW_AUTH itself.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if os.name == "nt":
    from ctypes import wintypes


ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from p7_hardware_safety import (  # noqa: E402
    DEFAULT_ABORT_FILE,
    HardwareExecutionLock,
    ROOT as SAFETY_ROOT,
    SHA256_RE,
    add_common_arguments,
    normalized_path,
    parse_authorization_file,
    resolve_path,
    sha256_file,
    validate_request,
)
from p7_jtag_backend import (  # noqa: E402
    CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS,
    EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
    JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS,
    JTAG_WRAPPER_OTHER_GUARD_SECONDS,
    JTAG_WRAPPER_VIVADO_PROCESS_COUNT,
    MAX_TRANSACTION_BYTES as BACKEND_MAX_TRANSACTION_BYTES,
    MAX_TRANSACTION_LINE_BYTES,
    MAX_TRANSACTION_OPERATIONS,
    TRANSACTION_MAGIC as BACKEND_TRANSACTION_MAGIC,
    SCHEMA as BACKEND_MANIFEST_SCHEMA,
    parse_raw_result,
    runtime_feasibility,
    validate_manifest_bundle,
)
from run_p7_authorized_hardware_sequence import (  # noqa: E402
    CANONICAL_FULL_PART,
    CANONICAL_LIVE_DEVICE,
    CANONICAL_LIVE_IDCODE_BINARY,
    CANONICAL_LIVE_IDCODE_HEX,
    CANONICAL_LIVE_PART,
    build_preflight_command,
    canonical_live_identity_failures,
    evaluate_preflight,
    normalize_p7_idcode,
    parse_markers,
)


if ROOT != SAFETY_ROOT:
    raise RuntimeError("P7 safety module resolved a different repository root")

STAGE_TCL = ROOT / "scripts" / "hw" / "p7_jtag_axi_transactions.tcl"
CONTAINED_LAUNCHER = ROOT / "tools" / "p7_contained_launcher.py"
IMMUTABLE_P6_DIR = ROOT / "evidence" / "hardware" / "p6" / "bitstreams"
CANONICAL_SHUTDOWN_BIT = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"
TRANSACTION_MAGIC = BACKEND_TRANSACTION_MAGIC
AXI_BASE = 0x43C00000
AXI_LAST_OFFSET = 0x03FC
MAX_TRANSACTION_BYTES = BACKEND_MAX_TRANSACTION_BYTES
MAX_OPERATIONS = MAX_TRANSACTION_OPERATIONS
MAX_POLL_COUNT = 10000
MAX_POLL_DELAY_MS = 100
MAX_METADATA_ENTRIES = 64
# Compatibility alias retained for evidence fields/tests.  The budget now
# separates the four-child containment allowance from other Python/hash/Tcl
# teardown instead of silently asking one 45-second bucket to cover both.
GLOBAL_RUNTIME_GUARD_SECONDS = JTAG_WRAPPER_OTHER_GUARD_SECONDS

HEX32_RE = re.compile(r"^0x[0-9a-fA-F]{8}$")
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
META_VALUE_RE = re.compile(r"^[A-Za-z0-9_.:+/@-]{1,128}$")
STAGE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
BATCH_FORBIDDEN_CHARS = '&|<>^%!\r\n\x00"()'
SAFE_IDLE_REQUIRED_KEYS = frozenset(
    {
        "SAFE_STATUS",
        "SAFE_TX_COUNT",
        "SAFE_RX_GOOD_L0",
        "SAFE_RX_GOOD_L1",
        "SAFE_CRC_BAD",
        "SAFE_PAYLOAD_MISMATCH",
        "SAFE_RETRY_EXHAUSTED",
        "SAFE_TX_FAIL",
        "SAFE_TXD_HIGH_MAX",
        "SAFE_DUTY_VIOLATION",
        "SAFE_ERROR_CODE",
        "SAFE_STICKY_ERROR",
    }
)


@dataclass
class ProcessResult:
    name: str
    returncode: int
    stdout_path: str
    stderr_path: str
    elapsed_seconds: float
    argv: list[str] = field(default_factory=list)
    started_at_utc: str = ""
    ended_at_utc: str = ""
    timed_out: bool = False
    abort_seen: bool = False
    interrupted: bool = False
    process_tree_terminated: bool = False
    process_tree_reaped: bool = False
    containment_kind: str = "NONE"
    containment_assigned: bool = False
    containment_closed: bool = False
    descendant_count_after: int = -1
    expected_tool_daemon_grace_used: bool = False
    expected_tool_daemon_grace_seconds: float = 0.0
    expected_tool_daemon_paths: list[str] = field(default_factory=list)
    descendant_paths_seen: list[str] = field(default_factory=list)
    descendant_processes_seen: list[dict[str, Any]] = field(default_factory=list)
    expected_tool_daemon_classification: str = "NONE"
    containment_cleanup_terminated: bool = False
    process_exit_race_rechecked: bool = False
    process_identity_query_retried: bool = False
    containment_query_error: str = ""
    launch_error: str = ""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        # A hard interruption may leave a .partial, but never a corrupt
        # committed JSON document that future evidence discovery would parse.
        raise


def append_event(path: Path, event: str, **fields: Any) -> None:
    payload = {"timestamp_utc": now_utc(), "event": event, **fields}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def safe_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_hex32(text: str, label: str) -> int:
    if not HEX32_RE.fullmatch(text):
        raise ValueError(f"{label} must be exactly 0x plus eight hex digits: {text}")
    return int(text, 16)


def _validate_write(offset: int, data: int, line_number: int) -> list[str]:
    errors: list[str] = []
    fixed_writes = {0x100, 0x108, 0x10C, 0x110, 0x114, 0x118, 0x11C, 0x15C, 0x16C, 0x170, 0x174}
    in_payload_window = 0x200 <= offset <= 0x2FC and offset % 4 == 0
    if offset not in fixed_writes and not in_payload_window:
        errors.append(f"line {line_number}: write offset is not in the P6 JTAG candidate write allowlist: 0x{offset:03x}")
        return errors
    if offset == 0x100 and (data == 0 or data & ~0x3F):
        errors.append(f"line {line_number}: P6_CTRL may use only nonzero bits 0x01..0x20")
    elif offset in (0x10C, 0x110) and data not in (1, 2, 3):
        errors.append(f"line {line_number}: lane mask write must be 0x1, 0x2, or 0x3")
    elif offset == 0x114 and not 1 <= data <= 247:
        errors.append(f"line {line_number}: payload length must be in 1..247")
    elif offset == 0x108 and data > 0xFFFF:
        errors.append(f"line {line_number}: P6 session must fit 16 bits")
    elif offset in (0x16C, 0x174) and data > 63:
        errors.append(f"line {line_number}: payload/RX word index must be in 0..63")
    elif offset == 0x15C and data == 0:
        errors.append(f"line {line_number}: bounded timeout cycles must be nonzero")
    return errors


def validate_transaction_file(
    path_value: str,
    expected_sha256: str,
    *,
    jtag_frequency_hz: int = 1_000_000,
) -> dict[str, Any]:
    """Stream-validate the bounded ASCII DSL without loading the file into memory."""
    report: dict[str, Any] = {
        "format": TRANSACTION_MAGIC,
        "path": path_value or "MISSING",
        "expected_sha256": expected_sha256.lower() if expected_sha256 else "MISSING",
        "actual_sha256": "NOT_COMPUTED",
        "operation_count": 0,
        "poll_operation_count": 0,
        "poll_iteration_ceiling": 0,
        "metadata": {},
        "errors": [],
    }
    errors: list[str] = report["errors"]
    if not path_value:
        errors.append("missing required stage control: --transaction-file")
        return report
    if not expected_sha256:
        errors.append("missing required stage control: --transaction-sha256")
    elif not SHA256_RE.fullmatch(expected_sha256):
        errors.append(f"invalid transaction SHA256 syntax: {expected_sha256}")
    path = resolve_path(path_value)
    report["path"] = str(path)
    if not path.is_file():
        errors.append(f"transaction file missing: {path}")
        return report
    size = path.stat().st_size
    report["size_bytes"] = size
    if size < 1 or size > MAX_TRANSACTION_BYTES:
        errors.append(f"transaction file size must be in 1..{MAX_TRANSACTION_BYTES}: {size}")
        return report
    actual_sha = sha256_file(path)
    report["actual_sha256"] = actual_sha
    if expected_sha256 and SHA256_RE.fullmatch(expected_sha256) and actual_sha != expected_sha256.lower():
        errors.append(f"transaction SHA256 mismatch: expected={expected_sha256.lower()} actual={actual_sha}")
    keys: set[str] = set()
    metadata: dict[str, str] = {}
    operation_count = 0
    poll_operation_count = 0
    poll_iteration_ceiling = 0
    start_operation_count = 0
    commit_operation_count = 0
    payload_write_count = 0
    write_operations: list[tuple[int, int]] = []
    last_operation: tuple[str, int, int] | None = None
    seen_lane = False
    seen_ack = False
    lane_value: int | None = None
    ack_value: int | None = None
    seen_length = False
    seen_commit = False
    ended = False
    saw_magic = False
    line_number = 0
    try:
        with path.open("rb") as handle:
            while True:
                raw = handle.readline(MAX_TRANSACTION_LINE_BYTES + 1)
                if not raw:
                    break
                line_number += 1
                if len(raw) > MAX_TRANSACTION_LINE_BYTES:
                    errors.append(
                        f"line {line_number}: line exceeds {MAX_TRANSACTION_LINE_BYTES} bytes"
                    )
                    break
                try:
                    line = raw.decode("ascii", errors="strict").strip()
                except UnicodeDecodeError as exc:
                    errors.append(f"line {line_number}: only printable ASCII is allowed: {exc}")
                    break
                if not line or line.startswith("#"):
                    continue
                if any(ord(char) < 0x20 or ord(char) > 0x7E for char in line):
                    errors.append(f"line {line_number}: only printable ASCII is allowed")
                    continue
                if not saw_magic:
                    saw_magic = True
                    if line != TRANSACTION_MAGIC:
                        errors.append(f"first non-comment line must be {TRANSACTION_MAGIC}")
                        break
                    continue
                if ended:
                    errors.append(f"line {line_number}: content after END is forbidden")
                    continue
                fields = line.split()
                op = fields[0]
                if op == "END":
                    if len(fields) != 1:
                        errors.append(f"line {line_number}: END takes no arguments")
                    ended = True
                    continue
                if op == "META":
                    if (
                        len(fields) != 3
                        or not KEY_RE.fullmatch(fields[1])
                        or not META_VALUE_RE.fullmatch(fields[2])
                    ):
                        errors.append(
                            f"line {line_number}: META syntax is META KEY SAFE_ASCII_VALUE"
                        )
                    elif fields[1] in metadata:
                        errors.append(f"line {line_number}: duplicate META key: {fields[1]}")
                    elif len(metadata) >= MAX_METADATA_ENTRIES:
                        errors.append(
                            f"line {line_number}: META entry limit exceeded: {MAX_METADATA_ENTRIES}"
                        )
                    else:
                        metadata[fields[1]] = fields[2]
                    continue
                operation_count += 1
                if operation_count > MAX_OPERATIONS:
                    errors.append(f"line {line_number}: operation limit exceeded: {MAX_OPERATIONS}")
                    break
                try:
                    if op == "W32":
                        if len(fields) != 3:
                            raise ValueError("W32 syntax is W32 ADDRESS DATA")
                        address = parse_hex32(fields[1], "address")
                        data = parse_hex32(fields[2], "data")
                        if address % 4 or not AXI_BASE <= address <= AXI_BASE + AXI_LAST_OFFSET:
                            raise ValueError(f"address is outside aligned P6 window: {fields[1]}")
                        offset = address - AXI_BASE
                        errors.extend(_validate_write(offset, data, line_number))
                        write_operations.append((offset, data))
                        if 0x200 <= offset <= 0x2FC:
                            payload_write_count += 1
                        if offset == 0x10C:
                            seen_lane = True
                            lane_value = data
                            seen_commit = False
                        elif offset == 0x110:
                            seen_ack = True
                            ack_value = data
                            seen_commit = False
                        elif offset == 0x114:
                            seen_length = True
                            seen_commit = False
                        elif offset in (0x108, 0x15C) or 0x200 <= offset <= 0x2FC:
                            seen_commit = False
                        elif offset == 0x100:
                            if data & 0x04:
                                commit_operation_count += 1
                                if not (seen_lane and seen_ack and seen_length):
                                    errors.append(
                                        f"line {line_number}: COMMIT requires lane, ACK lane, and payload length first"
                                    )
                                if lane_value != ack_value:
                                    errors.append(
                                        f"line {line_number}: P6 lane mask and ACK lane mask must match"
                                    )
                                seen_commit = True
                            if data & 0x08:
                                start_operation_count += 1
                                if not (seen_lane and seen_ack and seen_length and seen_commit):
                                    errors.append(
                                        f"line {line_number}: START requires a bounded committed configuration"
                                    )
                                seen_commit = False
                        last_operation = (op, address, data)
                    elif op == "R32":
                        if len(fields) != 3:
                            raise ValueError("R32 syntax is R32 ADDRESS KEY")
                        address = parse_hex32(fields[1], "address")
                        if address % 4 or not AXI_BASE <= address <= AXI_BASE + AXI_LAST_OFFSET:
                            raise ValueError(f"address is outside aligned P6 window: {fields[1]}")
                        if not KEY_RE.fullmatch(fields[2]) or fields[2] in keys:
                            raise ValueError(f"result key is invalid or duplicate: {fields[2]}")
                        keys.add(fields[2])
                        last_operation = (op, address, 0)
                    elif op in ("POLL32", "ASSERT32"):
                        expected_len = 7 if op == "POLL32" else 5
                        if len(fields) != expected_len:
                            raise ValueError(
                                "POLL32 syntax is POLL32 ADDRESS MASK EXPECTED MAX_POLLS DELAY_MS KEY"
                                if op == "POLL32"
                                else "ASSERT32 syntax is ASSERT32 ADDRESS MASK EXPECTED KEY"
                            )
                        address = parse_hex32(fields[1], "address")
                        mask = parse_hex32(fields[2], "mask")
                        expected = parse_hex32(fields[3], "expected")
                        key = fields[6] if op == "POLL32" else fields[4]
                        if address % 4 or not AXI_BASE <= address <= AXI_BASE + AXI_LAST_OFFSET:
                            raise ValueError(f"address is outside aligned P6 window: {fields[1]}")
                        if mask == 0 or expected & ~mask:
                            raise ValueError(
                                "mask must be nonzero and expected bits must be a subset of mask"
                            )
                        if not KEY_RE.fullmatch(key) or key in keys:
                            raise ValueError(f"result key is invalid or duplicate: {key}")
                        if op == "POLL32":
                            polls = int(fields[4], 10)
                            delay_ms = int(fields[5], 10)
                            if not 1 <= polls <= MAX_POLL_COUNT:
                                raise ValueError(f"MAX_POLLS must be in 1..{MAX_POLL_COUNT}")
                            if not 0 <= delay_ms <= MAX_POLL_DELAY_MS:
                                raise ValueError(
                                    f"DELAY_MS must be in 0..{MAX_POLL_DELAY_MS}"
                                )
                            poll_operation_count += 1
                            poll_iteration_ceiling += polls
                        keys.add(key)
                        if op == "POLL32":
                            polls_key = f"{key}_POLLS"
                            if not KEY_RE.fullmatch(polls_key) or polls_key in keys:
                                raise ValueError(
                                    f"derived poll result key is invalid or duplicate: {polls_key}"
                                )
                            keys.add(polls_key)
                        last_operation = (op, address, 0)
                    else:
                        raise ValueError(f"unsupported operation: {op}")
                except ValueError as exc:
                    errors.append(f"line {line_number}: {exc}")
    except OSError as exc:
        errors.append(f"unable to stream transaction file: {exc}")

    if not saw_magic:
        errors.append(f"first non-comment line must be {TRANSACTION_MAGIC}")
    if not ended:
        errors.append("END marker is missing")
    required_final = ("W32", AXI_BASE + 0x100, 0x30)
    if last_operation != required_final:
        errors.append("final operation before END must be W32 0x43c00100 0x00000030")
    report["operation_count"] = operation_count
    report["poll_operation_count"] = poll_operation_count
    report["poll_iteration_ceiling"] = poll_iteration_ceiling
    report["start_operation_count"] = start_operation_count
    report["commit_operation_count"] = commit_operation_count
    report["payload_write_count"] = payload_write_count
    report["result_keys"] = sorted(keys)
    report["write_operations"] = [
        {"offset": f"0x{offset:03x}", "value": f"0x{value:08x}"}
        for offset, value in write_operations
    ]
    report["metadata"] = metadata
    if 1 <= operation_count <= MAX_OPERATIONS:
        try:
            report["runtime_feasibility"] = runtime_feasibility(
                operation_count,
                jtag_frequency_hz=jtag_frequency_hz,
                authorized_runtime_sec=1800,
            )
        except ValueError as exc:
            errors.append(str(exc))
    report["valid"] = not errors
    return report


def _immutable_candidate_errors(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    for label, value, expected, suffix in (
        ("bitstream", args.bitstream, args.bitstream_sha256, ".bit"),
        ("LTX", args.ltx, args.ltx_sha256, ".ltx"),
    ):
        if not value or not expected:
            errors.append(f"immutable P6 JTAG candidate requires {label} path and expected SHA256")
            continue
        path = resolve_path(value)
        try:
            path.relative_to(IMMUTABLE_P6_DIR.resolve(strict=False))
        except ValueError:
            errors.append(f"{label} must be under immutable P6 artifact directory: {IMMUTABLE_P6_DIR}")
            continue
        expected_name = f"p6_jtag_dynamic_transport_{expected.lower()}{suffix}"
        if path.name.casefold() != expected_name.casefold():
            errors.append(f"{label} filename must bind its SHA256: expected={expected_name} observed={path.name}")
    if args.shutdown_bitstream and resolve_path(args.shutdown_bitstream) != CANONICAL_SHUTDOWN_BIT.resolve(strict=False):
        errors.append(f"shutdown bitstream must be canonical: {CANONICAL_SHUTDOWN_BIT}")
    return errors


def _profile_errors(args: argparse.Namespace) -> list[str]:
    if not args.profile:
        return ["stage profile is required"]
    path = resolve_path(args.profile)
    if not path.is_file():
        return []
    try:
        profile = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"unable to parse stage profile JSON: {exc}"]
    errors: list[str] = []
    if profile.get("network_required") is not False and profile.get("ethernet_enabled") is not False:
        errors.append("profile must explicitly disable Ethernet/network transport")
    if profile.get("motion_required") is not False and profile.get("rotation_enabled") is not False:
        errors.append("profile must explicitly disable motion/rotation")
    if profile.get("lane_count") != 2:
        errors.append("profile lane_count must be exactly 2")
    try:
        profile_mask = int(str(profile.get("max_lane_mask", "")), 0)
    except ValueError:
        profile_mask = 0
    if not 1 <= profile_mask <= 3:
        errors.append("profile max_lane_mask must be in 0x1..0x3")
    if profile.get("shutdown_on_exit") is not True:
        errors.append("profile shutdown_on_exit must be true")
    try:
        startup_wait_us = int(profile.get("startup_wait_us", 0))
        profile_runtime = int(profile.get("max_runtime_sec", 0))
    except (TypeError, ValueError):
        startup_wait_us = 0
        profile_runtime = 0
        errors.append("profile startup/runtime values must be integers")
    if startup_wait_us < 500:
        errors.append("profile startup_wait_us must be at least 500")
    if args.max_runtime_sec and profile_runtime < args.max_runtime_sec:
        errors.append("profile max_runtime_sec is lower than the requested runtime")
    return errors


def _backend_manifest_errors(
    args: argparse.Namespace, transaction: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    """Bind the generated RFAP manifest to the exact validated DSL before connect."""

    errors: list[str] = []
    details: dict[str, Any] = {
        "path": args.backend_manifest or "MISSING",
        "expected_sha256": (args.backend_manifest_sha256 or "MISSING").lower(),
    }
    if not args.backend_manifest:
        return ["P7 JTAG backend manifest is required"], details
    path = resolve_path(args.backend_manifest)
    details["path"] = str(path)
    if not SHA256_RE.fullmatch(args.backend_manifest_sha256 or ""):
        errors.append("P7 JTAG backend manifest expected SHA256 is missing or invalid")
    if not path.is_file() or path.is_symlink():
        errors.append(f"P7 JTAG backend manifest missing or symbolic: {path}")
        return errors, details
    actual = sha256_file(path)
    details["actual_sha256"] = actual
    if SHA256_RE.fullmatch(args.backend_manifest_sha256 or "") and actual != args.backend_manifest_sha256.lower():
        errors.append("P7 JTAG backend manifest SHA256 mismatch")
    try:
        payload = validate_manifest_bundle(
            path,
            expected_transaction_path=resolve_path(args.transaction_file),
            expected_transaction_sha256=args.transaction_sha256,
            expected_jtag_frequency_hz=args.jtag_frequency_hz,
            expected_authorized_runtime_sec=args.max_runtime_sec,
        )
    except Exception as exc:
        errors.append(f"P7 JTAG backend manifest bundle validation failed: {exc}")
        return errors, details
    if not isinstance(payload, dict) or payload.get("schema") != BACKEND_MANIFEST_SCHEMA:
        errors.append(f"P7 JTAG backend manifest schema must be {BACKEND_MANIFEST_SCHEMA}")
        return errors, details
    details["schema"] = payload.get("schema")
    manifest_transaction = (path.parent / str(payload.get("transaction_file", ""))).resolve(strict=False)
    requested_transaction = resolve_path(args.transaction_file)
    if normalized_path(manifest_transaction) != normalized_path(requested_transaction):
        errors.append("P7 JTAG backend manifest transaction path mismatch")
    if str(payload.get("transaction_sha256", "")).lower() != str(args.transaction_sha256).lower():
        errors.append("P7 JTAG backend manifest transaction SHA256 mismatch")
    try:
        manifest_operations = int(payload.get("transaction_operation_count", -1))
        validated_operations = int(transaction.get("operation_count", -2))
    except (TypeError, ValueError):
        manifest_operations = -1
        validated_operations = -2
    if manifest_operations != validated_operations:
        errors.append("P7 JTAG backend manifest transaction operation count mismatch")
    if payload.get("dry_run_only") is not True or payload.get("external_safe_wrapper_required") is not True:
        errors.append("P7 JTAG backend manifest lost its external safe-wrapper boundary")
    details["input_length"] = payload.get("input_length")
    details["input_sha256"] = payload.get("input_sha256")
    details["lane_policy"] = payload.get("lane_policy")
    details["transaction_operation_count"] = payload.get("transaction_operation_count")
    return errors, details


def _jtag_authorization_extension_errors(args: argparse.Namespace) -> list[str]:
    """Require the user-owned authorization artifact to bind the generated run inputs."""

    path = resolve_path(args.authorization_file) if args.authorization_file else None
    if path is None or not path.is_file():
        return []
    try:
        fields, _, duplicates = parse_authorization_file(path)
    except (OSError, UnicodeError) as exc:
        return [f"unable to parse P7 JTAG authorization extension: {exc}"]
    errors: list[str] = []
    if duplicates:
        errors.append("P7 JTAG authorization extension contains duplicate keys")
    exact = {
        "P7_JTAG_STAGE_NAME": args.stage_name,
        "P7_JTAG_SEMANTIC_MODE": args.semantic_mode,
        "P7_JTAG_TRANSACTION_PATH": str(resolve_path(args.transaction_file)),
        "P7_JTAG_TRANSACTION_SHA256": str(args.transaction_sha256).lower(),
        "P7_JTAG_FREQUENCY_HZ": str(args.jtag_frequency_hz),
        "P7_JTAG_AXI_BASE": str(args.axi_base_address).lower(),
    }
    if args.semantic_mode == "rfap":
        exact.update(
            {
                "P7_JTAG_BACKEND_MANIFEST_PATH": str(resolve_path(args.backend_manifest)),
                "P7_JTAG_BACKEND_MANIFEST_SHA256": str(args.backend_manifest_sha256).lower(),
            }
        )
    for key, expected in exact.items():
        observed = fields.get(key)
        if observed is None:
            errors.append(f"authorization field missing: {key}")
        elif key.endswith("_PATH"):
            if normalized_path(observed) != normalized_path(expected):
                errors.append(f"authorization field mismatch: {key}")
        elif observed.casefold() != expected.casefold():
            errors.append(
                f"authorization field mismatch: {key} expected={expected} observed={observed}"
            )
    return errors


def _safe_idle_transaction_errors(args: argparse.Namespace, transaction: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if args.backend_manifest or args.backend_manifest_sha256:
        errors.append("safe-idle semantic mode forbids an RFAP backend manifest")
    metadata = transaction.get("metadata", {})
    if not isinstance(metadata, dict) or str(metadata.get("EVIDENCE_KIND", "")).casefold() != "safe_idle":
        errors.append("safe-idle transaction must declare META EVIDENCE_KIND safe_idle")
    for key in ("start_operation_count", "commit_operation_count", "payload_write_count"):
        if int(transaction.get(key, -1)) != 0:
            errors.append(f"safe-idle transaction must have {key}=0")
    if transaction.get("write_operations") != [{"offset": "0x100", "value": "0x00000030"}]:
        errors.append("safe-idle transaction may write only final P6 STOP|SHUTDOWN")
    observed_keys = set(str(key) for key in transaction.get("result_keys", []))
    missing = sorted(SAFE_IDLE_REQUIRED_KEYS - observed_keys)
    if missing:
        errors.append(f"safe-idle transaction missing required read/assert keys: {missing}")
    unexpected = sorted(observed_keys - SAFE_IDLE_REQUIRED_KEYS)
    if unexpected:
        errors.append(f"safe-idle transaction has unexpected result keys: {unexpected}")
    return errors


def evaluate_safe_idle_raw(
    result_text: str,
    *,
    expected_operation_count: int,
) -> dict[str, Any]:
    """Strictly validate the fresh Tcl result for a non-transmitting safe-idle stage."""

    markers = parse_markers(result_text)
    failures: list[str] = []
    if markers.get("P7_TXN_META_EVIDENCE_KIND", "").casefold() != "safe_idle":
        failures.append("safe-idle result is missing exact EVIDENCE_KIND binding")
    try:
        observed_count = int(markers.get("P7_TRANSACTION_COUNT", ""), 10)
    except ValueError:
        observed_count = -1
    if observed_count != expected_operation_count:
        failures.append(
            "safe-idle transaction count mismatch: "
            f"expected={expected_operation_count} observed={markers.get('P7_TRANSACTION_COUNT', 'MISSING')}"
        )

    values: dict[str, int] = {}
    for key in sorted(SAFE_IDLE_REQUIRED_KEYS):
        raw_value = markers.get(key)
        if raw_value is None:
            failures.append(f"safe-idle result marker missing: {key}")
            continue
        try:
            value = int(raw_value, 0)
        except ValueError:
            failures.append(f"safe-idle result marker is not an integer: {key}={raw_value}")
            continue
        if not 0 <= value <= 0xFFFFFFFF:
            failures.append(f"safe-idle result marker is outside 32 bits: {key}={raw_value}")
            continue
        values[key] = value

    status = values.get("SAFE_STATUS")
    if status is not None and status & 0xE8:
        failures.append(
            f"safe-idle status has BUSY/FAIL/CONFIG_ERROR/TIMEOUT bits set: 0x{status:08x}"
        )
    for key, value in values.items():
        if key != "SAFE_STATUS" and value != 0:
            failures.append(f"safe-idle counter/error marker is nonzero: {key}=0x{value:08x}")

    return {
        "P7_SAFE_IDLE_PARSE": "PASS" if not failures else "FAIL",
        "semantic_mode": "safe-idle",
        "expected_operation_count": expected_operation_count,
        "observed_operation_count": observed_count,
        "required_values": {key: f"0x{value:08x}" for key, value in sorted(values.items())},
        "forbidden_status_mask": "0x000000e8",
        "drove_tfdu_txd": False,
        "enabled_tfdu_receiver": False,
        "failures": failures,
    }


def transaction_runtime_errors(
    args: argparse.Namespace, transaction: dict[str, Any]
) -> list[str]:
    """Fail closed when estimated or configured global execution cannot fit authorization."""
    errors: list[str] = []
    operation_count = int(transaction.get("operation_count", 0))
    if operation_count < 1 or operation_count > MAX_OPERATIONS:
        return errors
    authorized_runtime = args.max_runtime_sec
    if authorized_runtime is None or not 1 <= authorized_runtime <= 1800:
        return errors
    try:
        feasibility = runtime_feasibility(
            operation_count,
            jtag_frequency_hz=args.jtag_frequency_hz,
            authorized_runtime_sec=authorized_runtime,
            preflight_timeout_sec=args.preflight_timeout_sec,
            shutdown_timeout_sec=args.shutdown_timeout_sec,
            configured_stage_timeout_sec=args.stage_timeout_sec,
        )
    except ValueError as exc:
        errors.append(str(exc))
        return errors
    transaction["runtime_feasibility"] = feasibility
    minimum_stage = int(feasibility["minimum_stage_runtime_sec"])
    global_budget = dict(feasibility["global_runtime_budget"])
    transaction["global_runtime_budget"] = global_budget
    estimated_global = int(global_budget["minimum_estimated_global_runtime_sec"])
    configured_global_ceiling = int(global_budget["configured_global_timeout_ceiling_sec"])
    if minimum_stage > args.stage_timeout_sec:
        errors.append(
            "transaction runtime estimate cannot fit --stage-timeout-sec: "
            f"required={minimum_stage} configured={args.stage_timeout_sec}"
        )
    if estimated_global > authorized_runtime:
        errors.append(
            "transaction runtime estimate plus phase/containment/other reserves exceeds authorization: "
            f"required={estimated_global} authorized={authorized_runtime}"
        )
    if configured_global_ceiling > authorized_runtime:
        errors.append(
            "configured process timeout ceiling exceeds global authorization: "
            f"ceiling={configured_global_ceiling} authorized={authorized_runtime}"
        )
    return errors


def _stage_control_errors(args: argparse.Namespace) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    transaction = validate_transaction_file(
        args.transaction_file,
        args.transaction_sha256,
        jtag_frequency_hz=args.jtag_frequency_hz,
    )
    errors.extend(transaction["errors"])
    if args.semantic_mode == "safe-idle":
        transaction["backend_manifest"] = {"semantic_mode": "safe-idle", "required": False}
        errors.extend(_safe_idle_transaction_errors(args, transaction))
    else:
        manifest_errors, backend_manifest = _backend_manifest_errors(args, transaction)
        transaction["backend_manifest"] = backend_manifest
        errors.extend(manifest_errors)
    errors.extend(transaction_runtime_errors(args, transaction))
    errors.extend(_immutable_candidate_errors(args))
    errors.extend(_profile_errors(args))
    errors.extend(_jtag_authorization_extension_errors(args))
    if not STAGE_NAME_RE.fullmatch(args.stage_name or ""):
        errors.append("stage name must match [a-z0-9][a-z0-9_.-]{0,63}")
    if args.axi_base_address.lower() != "0x43c00000":
        errors.append("P7 direct JTAG/AXI stage base must be exactly 0x43c00000")
    if not 100_000 <= args.jtag_frequency_hz <= 5_000_000:
        errors.append("JTAG frequency must be in 100000..5000000 Hz")
    if not 1 <= args.preflight_timeout_sec <= 300:
        errors.append("preflight timeout must be in 1..300 seconds")
    if not 1 <= args.shutdown_timeout_sec <= 300:
        errors.append("shutdown timeout must be in 1..300 seconds")
    if args.max_runtime_sec is not None and not 1 <= args.stage_timeout_sec <= args.max_runtime_sec:
        errors.append("stage timeout must be positive and no greater than --max-runtime-sec")
    if args.max_runtime_sec is not None and args.preflight_timeout_sec > args.max_runtime_sec:
        errors.append("preflight timeout may not exceed --max-runtime-sec")
    if resolve_path(args.abort_file or str(DEFAULT_ABORT_FILE)) != DEFAULT_ABORT_FILE.resolve(strict=False):
        errors.append(f"abort file must be the canonical path: {DEFAULT_ABORT_FILE}")
    if Path(args.vivado_path).suffix.casefold() in (".bat", ".cmd"):
        for label, value in vars(args).items():
            if isinstance(value, str) and any(char in value for char in BATCH_FORBIDDEN_CHARS):
                errors.append(f"batch-safe execution rejects command metacharacters in --{label.replace('_', '-')}")
    if not STAGE_TCL.is_file():
        errors.append(f"P7 JTAG/AXI Tcl missing: {STAGE_TCL}")
    return errors, transaction


def _verify_hash(path_value: str, expected: str, label: str) -> str | None:
    path = resolve_path(path_value)
    if not path.is_file():
        return f"{label} disappeared before launch: {path}"
    actual = sha256_file(path)
    if actual != expected.lower():
        return f"{label} changed before launch: expected={expected.lower()} actual={actual} path={path}"
    return None


def _reject_batch_metacharacters(command: list[str]) -> None:
    executable_suffix = Path(command[0]).suffix.casefold()
    if executable_suffix not in (".bat", ".cmd"):
        return
    for argument in command:
        if any(char in argument for char in BATCH_FORBIDDEN_CHARS):
            raise ValueError("batch-file invocation argument contains a forbidden command metacharacter")


_CONTAINMENT_RESULTS: dict[subprocess.Popen[Any], bool] = {}
_CONTAINMENT_DETAILS: dict[subprocess.Popen[Any], dict[str, Any]] = {}
_POSIX_PROCESS_GROUPS: dict[subprocess.Popen[Any], int] = {}

# Vivado may launch its own ChipScope server and keep it alive briefly after
# the batch process exits.  Only this exact executable under the invoked
# Vivado installation may receive a short natural-exit grace.  Any other
# descendant, a same-named executable elsewhere, or a grace timeout remains a
# containment failure and is terminated before returning.
PROCESS_EXIT_RACE_RECHECK_SECONDS = 0.25


def _normalized_windows_image_path(value: str | Path) -> str:
    return str(Path(value).resolve(strict=False)).replace("/", "\\").casefold()


def _expected_tool_daemon_paths(command: list[str]) -> list[str]:
    if not command:
        return []
    executable = Path(command[0]).resolve(strict=False)
    if executable.stem.casefold() != "vivado":
        return []
    expected = executable.parent / "unwrapped" / "win64.o" / "cs_server.exe"
    return [str(expected.resolve(strict=False))]


def classify_expected_tool_daemons(
    identities: list[dict[str, Any]], approved_paths: list[str]
) -> str:
    """Accept only the canonical singleton or exact direct parent-child pair."""

    if len(approved_paths) != 1 or not isinstance(approved_paths[0], str):
        return "UNAPPROVED"
    approved = _normalized_windows_image_path(approved_paths[0])
    normalized: list[tuple[int, int, str]] = []
    for item in identities:
        try:
            raw_process_id = item["pid"]
            raw_parent_id = item["parent_pid"]
            image_path = str(item["image_path"])
        except (KeyError, TypeError, ValueError):
            return "UNAPPROVED"
        if (
            not isinstance(raw_process_id, int)
            or isinstance(raw_process_id, bool)
            or not isinstance(raw_parent_id, int)
            or isinstance(raw_parent_id, bool)
        ):
            return "UNAPPROVED"
        process_id = raw_process_id
        parent_id = raw_parent_id
        if process_id <= 0 or parent_id < 0 or process_id == parent_id:
            return "UNAPPROVED"
        normalized.append((process_id, parent_id, _normalized_windows_image_path(image_path)))
    process_ids = [item[0] for item in normalized]
    if len(set(process_ids)) != len(process_ids):
        return "UNAPPROVED"
    if any(item[2] != approved for item in normalized):
        return "UNAPPROVED"
    if len(normalized) == 1:
        return "SINGLE_EXACT_CS_SERVER"
    if len(normalized) != 2:
        return "UNAPPROVED"
    first, second = normalized
    direct_edges = int(first[1] == second[0]) + int(second[1] == first[0])
    return (
        "DIRECT_PARENT_CHILD_EXACT_CS_SERVER"
        if direct_edges == 1
        else "UNAPPROVED"
    )


if os.name == "nt":
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS = 1
    JOB_OBJECT_BASIC_PROCESS_ID_LIST_CLASS = 3
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    TH32CS_SNAPPROCESS = 0x00000002
    JOB_PROCESS_ID_CAPACITY = 256

    class _JobObjectBasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JobObjectExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JobObjectBasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    class _JobObjectBasicAccountingInformation(ctypes.Structure):
        _fields_ = [
            ("TotalUserTime", ctypes.c_longlong),
            ("TotalKernelTime", ctypes.c_longlong),
            ("ThisPeriodTotalUserTime", ctypes.c_longlong),
            ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
            ("TotalPageFaultCount", wintypes.DWORD),
            ("TotalProcesses", wintypes.DWORD),
            ("ActiveProcesses", wintypes.DWORD),
            ("TotalTerminatedProcesses", wintypes.DWORD),
        ]

    class _JobObjectBasicProcessIdList(ctypes.Structure):
        _fields_ = [
            ("NumberOfAssignedProcesses", wintypes.DWORD),
            ("NumberOfProcessIdsInList", wintypes.DWORD),
            ("ProcessIdList", ctypes.c_size_t * JOB_PROCESS_ID_CAPACITY),
        ]

    class _ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _KERNEL32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _KERNEL32.CreateJobObjectW.restype = wintypes.HANDLE
    _KERNEL32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    _KERNEL32.SetInformationJobObject.restype = wintypes.BOOL
    _KERNEL32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _KERNEL32.AssignProcessToJobObject.restype = wintypes.BOOL
    _KERNEL32.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    _KERNEL32.QueryInformationJobObject.restype = wintypes.BOOL
    _KERNEL32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _KERNEL32.TerminateJobObject.restype = wintypes.BOOL
    _KERNEL32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _KERNEL32.OpenProcess.restype = wintypes.HANDLE
    _KERNEL32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _KERNEL32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _KERNEL32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _KERNEL32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _KERNEL32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry32W)]
    _KERNEL32.Process32FirstW.restype = wintypes.BOOL
    _KERNEL32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry32W)]
    _KERNEL32.Process32NextW.restype = wintypes.BOOL
    _KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
    _KERNEL32.CloseHandle.restype = wintypes.BOOL

    class _WindowsJobContainment:
        def __init__(self) -> None:
            handle = _KERNEL32.CreateJobObjectW(None, None)
            if not handle:
                raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
            self.handle = handle
            self.closed = False
            limits = _JobObjectExtendedLimitInformation()
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _KERNEL32.SetInformationJobObject(
                self.handle,
                JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                ctypes.byref(limits),
                ctypes.sizeof(limits),
            ):
                error = ctypes.get_last_error()
                _KERNEL32.CloseHandle(self.handle)
                self.closed = True
                raise OSError(error, "SetInformationJobObject failed")

        def assign(self, process: subprocess.Popen[Any]) -> None:
            if not _KERNEL32.AssignProcessToJobObject(
                self.handle, wintypes.HANDLE(int(process._handle))  # type: ignore[attr-defined]
            ):
                raise OSError(ctypes.get_last_error(), "AssignProcessToJobObject failed")

        def active_processes(self) -> int:
            accounting = _JobObjectBasicAccountingInformation()
            if not _KERNEL32.QueryInformationJobObject(
                self.handle,
                JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION_CLASS,
                ctypes.byref(accounting),
                ctypes.sizeof(accounting),
                None,
            ):
                raise OSError(ctypes.get_last_error(), "QueryInformationJobObject failed")
            return int(accounting.ActiveProcesses)

        def active_process_ids(self) -> list[int]:
            process_ids = _JobObjectBasicProcessIdList()
            if not _KERNEL32.QueryInformationJobObject(
                self.handle,
                JOB_OBJECT_BASIC_PROCESS_ID_LIST_CLASS,
                ctypes.byref(process_ids),
                ctypes.sizeof(process_ids),
                None,
            ):
                raise OSError(ctypes.get_last_error(), "QueryInformationJobObject process list failed")
            assigned = int(process_ids.NumberOfAssignedProcesses)
            count = int(process_ids.NumberOfProcessIdsInList)
            if assigned != count or count > JOB_PROCESS_ID_CAPACITY:
                raise OSError("Job Object process list exceeded the fixed fail-closed capacity")
            return [int(process_ids.ProcessIdList[index]) for index in range(count)]

        @staticmethod
        def process_image_path(process_id: int) -> str:
            handle = _KERNEL32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, wintypes.DWORD(process_id)
            )
            if not handle:
                raise OSError(ctypes.get_last_error(), f"OpenProcess failed for contained PID {process_id}")
            try:
                capacity = wintypes.DWORD(32768)
                buffer = ctypes.create_unicode_buffer(capacity.value)
                if not _KERNEL32.QueryFullProcessImageNameW(
                    handle, 0, buffer, ctypes.byref(capacity)
                ):
                    raise OSError(
                        ctypes.get_last_error(),
                        f"QueryFullProcessImageNameW failed for contained PID {process_id}",
                    )
                return buffer.value
            finally:
                _KERNEL32.CloseHandle(handle)

        def active_process_images(self) -> list[tuple[int, str]]:
            return [(process_id, self.process_image_path(process_id)) for process_id in self.active_process_ids()]

        @staticmethod
        def process_parent_ids(process_ids: list[int]) -> dict[int, int]:
            requested = set(process_ids)
            if len(requested) != len(process_ids):
                raise OSError("Job Object returned duplicate active process IDs")
            snapshot = _KERNEL32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            invalid_handle = ctypes.c_void_p(-1).value
            snapshot_value = (
                snapshot
                if isinstance(snapshot, int)
                else ctypes.cast(snapshot, ctypes.c_void_p).value
            )
            if not snapshot_value or snapshot_value == invalid_handle:
                raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")
            parents: dict[int, int] = {}
            try:
                entry = _ProcessEntry32W()
                entry.dwSize = ctypes.sizeof(entry)
                if not _KERNEL32.Process32FirstW(snapshot, ctypes.byref(entry)):
                    raise OSError(ctypes.get_last_error(), "Process32FirstW failed")
                while True:
                    process_id = int(entry.th32ProcessID)
                    if process_id in requested:
                        parents[process_id] = int(entry.th32ParentProcessID)
                    entry.dwSize = ctypes.sizeof(entry)
                    if not _KERNEL32.Process32NextW(snapshot, ctypes.byref(entry)):
                        error = ctypes.get_last_error()
                        # ERROR_NO_MORE_FILES is the successful enumeration terminator.
                        if error != 18:
                            raise OSError(error, "Process32NextW failed")
                        break
            finally:
                _KERNEL32.CloseHandle(snapshot)
            if set(parents) != requested:
                missing = sorted(requested - set(parents))
                raise OSError(f"parent PID lookup missed active contained processes: {missing}")
            return parents

        def active_process_identities(self) -> list[dict[str, Any]]:
            process_ids = self.active_process_ids()
            parents = self.process_parent_ids(process_ids)
            return [
                {
                    "pid": process_id,
                    "parent_pid": parents[process_id],
                    "image_path": self.process_image_path(process_id),
                }
                for process_id in process_ids
            ]

        def terminate(self) -> bool:
            return bool(_KERNEL32.TerminateJobObject(self.handle, 125))

        def wait_empty(self, timeout_sec: float = 10.0) -> bool:
            deadline = time.monotonic() + timeout_sec
            while time.monotonic() < deadline:
                if self.active_processes() == 0:
                    return True
                time.sleep(0.05)
            return self.active_processes() == 0

        def close(self) -> None:
            if not self.closed:
                _KERNEL32.CloseHandle(self.handle)
                self.closed = True

    _WINDOWS_JOBS: dict[subprocess.Popen[Any], _WindowsJobContainment] = {}


def launch_contained_process(
    command: list[str],
    *,
    stdout: Any,
    stderr: Any,
    popen_args: dict[str, Any],
) -> subprocess.Popen[Any]:
    """Launch only after the Windows handshake helper is inside a Job Object."""

    if os.name != "nt":
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, **popen_args)
        _POSIX_PROCESS_GROUPS[process] = process.pid
        _CONTAINMENT_DETAILS[process] = {
            "containment_kind": "POSIX_PROCESS_GROUP",
            "containment_assigned": True,
            "containment_closed": False,
            "descendant_count_after": -1,
            "expected_tool_daemon_grace_used": False,
            "expected_tool_daemon_grace_seconds": 0.0,
            "expected_tool_daemon_paths": [],
            "descendant_paths_seen": [],
            "descendant_processes_seen": [],
            "expected_tool_daemon_classification": "NONE",
            "containment_cleanup_terminated": False,
            "process_exit_race_rechecked": False,
            "process_identity_query_retried": False,
            "containment_query_error": "",
        }
        return process
    if not CONTAINED_LAUNCHER.is_file():
        raise OSError(f"P7 contained launcher missing: {CONTAINED_LAUNCHER}")
    payload = base64.urlsafe_b64encode(
        json.dumps(command, ensure_ascii=False).encode("utf-8")
    ).decode("ascii").rstrip("=")
    job = _WindowsJobContainment()
    process: subprocess.Popen[Any] | None = None
    try:
        process = subprocess.Popen(
            [sys.executable, str(CONTAINED_LAUNCHER), payload],
            stdin=subprocess.PIPE,
            stdout=stdout,
            stderr=stderr,
            **popen_args,
        )
        job.assign(process)
        _WINDOWS_JOBS[process] = job
        _CONTAINMENT_DETAILS[process] = {
            "containment_kind": "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE",
            "containment_assigned": True,
            "containment_closed": False,
            "descendant_count_after": -1,
            "expected_tool_daemon_grace_used": False,
            "expected_tool_daemon_grace_seconds": 0.0,
            "expected_tool_daemon_paths": _expected_tool_daemon_paths(command),
            "descendant_paths_seen": [],
            "descendant_processes_seen": [],
            "expected_tool_daemon_classification": "NONE",
            "containment_cleanup_terminated": False,
            "process_exit_race_rechecked": False,
            "process_identity_query_retried": False,
            "containment_query_error": "",
        }
        assert process.stdin is not None
        process.stdin.write("P7_GO\n")
        process.stdin.flush()
        process.stdin.close()
        return process
    except BaseException:
        if process is not None and process.poll() is None:
            try:
                process.kill()
                process.wait(timeout=10)
            except (OSError, subprocess.SubprocessError):
                pass
        if process is not None:
            _WINDOWS_JOBS.pop(process, None)
            details = _CONTAINMENT_DETAILS.setdefault(process, {})
            details["containment_closed"] = True
            details["descendant_count_after"] = -1
            _CONTAINMENT_RESULTS[process] = False
        job.close()
        raise


def _posix_group_empty(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    return False


def verify_process_tree_reaped(process: subprocess.Popen[Any]) -> bool:
    """Close containment only after proving no process remains in it."""

    cached = _CONTAINMENT_RESULTS.get(process)
    if cached is not None:
        return cached
    if os.name == "nt":
        job = _WINDOWS_JOBS.pop(process, None)
        if job is None:
            _CONTAINMENT_RESULTS[process] = False
            return False
        details = _CONTAINMENT_DETAILS.setdefault(process, {})
        physically_empty = False
        empty = False
        try:
            empty = job.wait_empty(CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS)
            physically_empty = empty
            if not empty:
                identities: list[dict[str, Any]] | None = None
                first_query_error: OSError | None = None
                try:
                    identities = job.active_process_identities()
                except OSError as exc:
                    first_query_error = exc
                if identities is None or not identities:
                    # A parent can exit between Job PID enumeration, Toolhelp
                    # parent lookup, and image lookup.  First accept a proven
                    # empty Job; otherwise perform exactly one complete fresh
                    # identity query, which may now yield the legal singleton.
                    if job.wait_empty(PROCESS_EXIT_RACE_RECHECK_SECONDS):
                        details["process_exit_race_rechecked"] = True
                        empty = True
                        physically_empty = True
                    else:
                        try:
                            identities = job.active_process_identities()
                            details["process_identity_query_retried"] = True
                        except OSError as retry_exc:
                            details["containment_query_error"] = (
                                f"first={type(first_query_error).__name__}: {first_query_error}; "
                                f"retry={type(retry_exc).__name__}: {retry_exc}"
                            )
                            identities = None
                if not empty and identities:
                    details["descendant_processes_seen"] = identities
                    details["descendant_paths_seen"] = [
                        str(item["image_path"]) for item in identities
                    ]
                    classification = classify_expected_tool_daemons(
                        identities,
                        list(details.get("expected_tool_daemon_paths", [])),
                    )
                    details["expected_tool_daemon_classification"] = classification
                else:
                    classification = "UNAPPROVED"
                if not empty and classification in {
                    "SINGLE_EXACT_CS_SERVER",
                    "DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
                }:
                    # This is not a generic descendant grace.  It applies only
                    # to one exact cs_server or its known direct parent-child
                    # topology under the invoked Vivado root.  PASS still
                    # requires the complete Job to exit naturally.
                    details["expected_tool_daemon_grace_used"] = True
                    details["expected_tool_daemon_grace_seconds"] = (
                        EXPECTED_TOOL_DAEMON_GRACE_SECONDS
                    )
                    empty = job.wait_empty(EXPECTED_TOOL_DAEMON_GRACE_SECONDS)
                    physically_empty = empty
                if not empty:
                    details["containment_cleanup_terminated"] = bool(job.terminate())
                    physically_empty = job.wait_empty(10.0)
                    # Forced cleanup proves the machine was made safe, but it
                    # must not promote a lingering or unrecognized child to PASS.
                    empty = False
        except OSError as exc:
            # Errors outside the one explicitly retried identity snapshot are
            # fail-closed unless the Job itself is now proven empty.
            try:
                empty = job.wait_empty(PROCESS_EXIT_RACE_RECHECK_SECONDS)
            except OSError:
                empty = False
            physically_empty = empty
            if empty:
                details["process_exit_race_rechecked"] = True
            else:
                details["containment_query_error"] = f"{type(exc).__name__}: {exc}"
                try:
                    details["containment_cleanup_terminated"] = bool(job.terminate())
                    physically_empty = job.wait_empty(10.0)
                except OSError:
                    pass
        finally:
            job.close()
        details["containment_closed"] = True
        details["descendant_count_after"] = 0 if physically_empty else -1
        result = bool(empty and process.poll() is not None)
    else:
        pgid = _POSIX_PROCESS_GROUPS.pop(process, None)
        if pgid is None:
            _CONTAINMENT_RESULTS[process] = False
            return False
        empty = _posix_group_empty(pgid)
        physically_empty = empty
        if not empty:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 10.0
            while time.monotonic() < deadline and not _posix_group_empty(pgid):
                time.sleep(0.05)
            physically_empty = _posix_group_empty(pgid)
            empty = False
        details = _CONTAINMENT_DETAILS.setdefault(process, {})
        details["containment_closed"] = physically_empty
        details["descendant_count_after"] = 0 if physically_empty else -1
        result = bool(empty and process.poll() is not None)
    _CONTAINMENT_RESULTS[process] = result
    return result


def containment_record(process: subprocess.Popen[Any] | None) -> dict[str, Any]:
    if process is None:
        return {
            "containment_kind": "NO_CHILD_LAUNCHED",
            "containment_assigned": False,
            "containment_closed": True,
            "descendant_count_after": 0,
            "expected_tool_daemon_grace_used": False,
            "expected_tool_daemon_grace_seconds": 0.0,
            "expected_tool_daemon_paths": [],
            "descendant_paths_seen": [],
            "descendant_processes_seen": [],
            "expected_tool_daemon_classification": "NONE",
            "containment_cleanup_terminated": False,
            "process_exit_race_rechecked": False,
            "process_identity_query_retried": False,
            "containment_query_error": "",
        }
    return {
        "containment_kind": "MISSING",
        "containment_assigned": False,
        "containment_closed": False,
        "descendant_count_after": -1,
        "expected_tool_daemon_grace_used": False,
        "expected_tool_daemon_grace_seconds": 0.0,
        "expected_tool_daemon_paths": [],
        "descendant_paths_seen": [],
        "descendant_processes_seen": [],
        "expected_tool_daemon_classification": "NONE",
        "containment_cleanup_terminated": False,
        "process_exit_race_rechecked": False,
        "process_identity_query_retried": False,
        "containment_query_error": "",
        **_CONTAINMENT_DETAILS.get(process, {}),
    }


def terminate_process_tree(process: subprocess.Popen[Any]) -> bool:
    """Terminate only this process tree and prove the parent was reaped."""

    if os.name == "nt" and process in _WINDOWS_JOBS:
        job = _WINDOWS_JOBS.pop(process)
        empty = False
        try:
            signaled = job.terminate()
            try:
                process.wait(timeout=10)
            except (subprocess.SubprocessError, OSError):
                signaled = False
            empty = job.wait_empty(10.0)
            result = bool(signaled and empty and process.poll() is not None)
        except OSError:
            result = False
        finally:
            job.close()
        details = _CONTAINMENT_DETAILS.setdefault(process, {})
        details["containment_closed"] = True
        details["descendant_count_after"] = 0 if empty else -1
        _CONTAINMENT_RESULTS[process] = result
        return result
    if os.name != "nt" and process in _POSIX_PROCESS_GROUPS:
        pgid = _POSIX_PROCESS_GROUPS.pop(process)
        try:
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except (subprocess.SubprocessError, OSError):
                pass
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not _posix_group_empty(pgid):
            time.sleep(0.05)
        result = process.poll() is not None and _posix_group_empty(pgid)
        details = _CONTAINMENT_DETAILS.setdefault(process, {})
        details["containment_closed"] = result
        details["descendant_count_after"] = 0 if result else -1
        _CONTAINMENT_RESULTS[process] = result
        return result
    if process.poll() is not None:
        return verify_process_tree_reaped(process)
    tree_signal_succeeded = False
    if os.name == "nt":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        try:
            taskkill_result = subprocess.run(
                [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                text=True,
                capture_output=True,
                timeout=20,
                check=False,
            )
            tree_signal_succeeded = taskkill_result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            tree_signal_succeeded = True
        except (OSError, ProcessLookupError):
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            return False
    except OSError:
        return False
    return tree_signal_succeeded and process.poll() is not None


def run_bounded_process(
    *,
    name: str,
    command: list[str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_sec: int,
    abort_file: Path,
    watch_abort: bool,
) -> ProcessResult:
    """Run one fixed argv vector and kill its process tree on timeout/abort."""

    _reject_batch_metacharacters(command)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    started_at_utc = now_utc()
    popen_args: dict[str, Any] = {
        "cwd": ROOT,
        "text": True,
        "shell": False,
    }
    if os.name == "nt":
        popen_args["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_args["start_new_session"] = True
    process: subprocess.Popen[Any] | None = None
    timed_out = False
    abort_seen = False
    interrupted = False
    tree_terminated = False
    process_tree_reaped = False
    raw_returncode: int | None = None
    launch_error = ""
    try:
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            try:
                process = launch_contained_process(
                    command, stdout=stdout_handle, stderr=stderr_handle, popen_args=popen_args
                )
                deadline = started + timeout_sec
                while process.poll() is None:
                    if watch_abort and abort_file.exists():
                        abort_seen = True
                        tree_terminated = terminate_process_tree(process)
                        break
                    if time.monotonic() >= deadline:
                        timed_out = True
                        tree_terminated = terminate_process_tree(process)
                        break
                    time.sleep(0.10)
            except KeyboardInterrupt:
                interrupted = True
            except BaseException as exc:  # reap before reporting any post-launch failure
                launch_error = f"{type(exc).__name__}: {exc}"
            finally:
                if process is not None:
                    if process.poll() is None:
                        tree_terminated = terminate_process_tree(process) or tree_terminated
                    try:
                        raw_returncode = process.wait(timeout=10)
                    except (subprocess.TimeoutExpired, OSError):
                        tree_terminated = terminate_process_tree(process) or tree_terminated
                        try:
                            raw_returncode = process.wait(timeout=10)
                        except (subprocess.TimeoutExpired, OSError):
                            raw_returncode = process.poll()
                    process_tree_reaped = (
                        raw_returncode is not None
                        and process.poll() is not None
                        and verify_process_tree_reaped(process)
                    )
    except BaseException as exc:
        launch_error = launch_error or f"{type(exc).__name__}: {exc}"
    finally:
        if process is not None and process.poll() is None:
            tree_terminated = terminate_process_tree(process) or tree_terminated
            try:
                raw_returncode = process.wait(timeout=10)
            except (subprocess.TimeoutExpired, OSError):
                raw_returncode = process.poll()
            process_tree_reaped = (
                raw_returncode is not None
                and process.poll() is not None
                and verify_process_tree_reaped(process)
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
    containment = containment_record(process)
    tree_terminated = tree_terminated or bool(containment.get("containment_cleanup_terminated", False))
    return ProcessResult(
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
        expected_tool_daemon_grace_used=bool(
            containment.get("expected_tool_daemon_grace_used", False)
        ),
        expected_tool_daemon_grace_seconds=float(
            containment.get("expected_tool_daemon_grace_seconds", 0.0)
        ),
        expected_tool_daemon_paths=list(containment.get("expected_tool_daemon_paths", [])),
        descendant_paths_seen=list(containment.get("descendant_paths_seen", [])),
        descendant_processes_seen=list(
            containment.get("descendant_processes_seen", [])
        ),
        expected_tool_daemon_classification=str(
            containment.get("expected_tool_daemon_classification", "NONE")
        ),
        containment_cleanup_terminated=bool(
            containment.get("containment_cleanup_terminated", False)
        ),
        process_exit_race_rechecked=bool(
            containment.get("process_exit_race_rechecked", False)
        ),
        process_identity_query_retried=bool(
            containment.get("process_identity_query_retried", False)
        ),
        containment_query_error=str(containment.get("containment_query_error", "")),
        launch_error=launch_error,
    )


def deadline_timeout(requested_sec: int, deadline: float, *, reserve_sec: int = 0) -> int:
    """Return a positive timeout that preserves the global shutdown/runtime reserve."""
    available = math.floor(deadline - time.monotonic() - reserve_sec)
    if available < 1:
        raise RuntimeError(
            f"global runtime budget exhausted before launch; reserve={reserve_sec} seconds"
        )
    return min(requested_sec, available)


def containment_allowance(process_count: int) -> int:
    if not 0 <= process_count <= JTAG_WRAPPER_VIVADO_PROCESS_COUNT:
        raise ValueError("contained Vivado process count is outside the fixed 0..4 wrapper contract")
    return process_count * (
        CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS + EXPECTED_TOOL_DAEMON_GRACE_SECONDS
    )


def record_global_runtime(
    manifest: dict[str, Any], *, started: float, max_runtime_sec: int
) -> bool:
    elapsed = round(time.monotonic() - started, 6)
    within = elapsed <= max_runtime_sec
    manifest["global_runtime"] = {
        "elapsed_seconds": elapsed,
        "authorized_max_seconds": max_runtime_sec,
        "within_authorized_limit": within,
    }
    return within


def evaluate_shutdown(returncode: int, stdout: str, result_text: str) -> tuple[bool, list[str]]:
    failures: list[str] = []
    combined = stdout + "\n" + result_text
    if returncode != 0:
        failures.append(f"shutdown process returned nonzero exit code: {returncode}")
    if "TFDU_SHUTDOWN_PROGRAMMED=" not in combined:
        failures.append("TFDU_SHUTDOWN_PROGRAMMED marker missing")
    if parse_markers(result_text).get("P7_SHUTDOWN_RESULT") != "PASS":
        failures.append("P7_SHUTDOWN_RESULT=PASS marker missing from fresh result file")
    return not failures, failures


def evaluate_stage(
    returncode: int,
    stdout: str,
    result_text: str,
    *,
    expected_target: str,
    expected_part: str,
    expected_operation_count: int | None = None,
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    markers = parse_markers(result_text)
    if returncode != 0:
        failures.append(f"stage process returned nonzero exit code: {returncode}")
    expected = {
        "P7_JTAG_STAGE_RESULT": "PASS",
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_JTAG_AXI_TRANSACTIONS": "PASS",
        "P7_HW_TARGET": expected_target,
        "P7_HW_PART": expected_part,
        "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
    }
    for key, value in expected.items():
        if markers.get(key) != value:
            failures.append(f"stage marker mismatch: {key} expected={value} observed={markers.get(key, 'MISSING')}")
    if expected_operation_count is not None and markers.get("P7_TRANSACTION_COUNT") != str(
        expected_operation_count
    ):
        failures.append(
            "stage marker mismatch: P7_TRANSACTION_COUNT "
            f"expected={expected_operation_count} "
            f"observed={markers.get('P7_TRANSACTION_COUNT', 'MISSING')}"
        )
    if parse_markers(stdout).get("P7_JTAG_STAGE_RESULT") != "PASS":
        failures.append("stage PASS marker missing from stdout")
    failures.extend(
        canonical_live_identity_failures(
            markers,
            expected_part=expected_part,
            prefix="P7_HW",
            label="JTAG stage",
        )
    )
    if normalize_p7_idcode(markers.get("P7_HW_IDCODE", "")) != CANONICAL_LIVE_IDCODE_HEX:
        failures.append("JTAG stage compatibility IDCODE marker is missing or not the exact authorized IDCODE")
    return not failures, failures


def build_stage_tcl_command(
    args: argparse.Namespace,
    *,
    mode: str,
    bitstream: Path,
    ltx: Path | None,
    transaction: Path | None,
    result_file: Path,
    runtime_sec: int | None = None,
) -> list[str]:
    return [
        str(Path(args.vivado_path).resolve(strict=False)),
        "-mode",
        "batch",
        "-source",
        str(STAGE_TCL),
        "-tclargs",
        str(ROOT),
        mode,
        str(resolve_path(args.authorization_file)),
        args.board_id,
        args.expected_part,
        args.expected_target,
        args.hw_server_url,
        str(args.jtag_frequency_hz),
        str(bitstream),
        str(ltx) if ltx else "-",
        str(transaction) if transaction else "-",
        str(result_file),
        args.axi_base_address,
        str(MAX_OPERATIONS),
        str(MAX_TRANSACTION_BYTES),
        str(
            runtime_sec
            if runtime_sec is not None
            else min(args.stage_timeout_sec, args.max_runtime_sec or args.stage_timeout_sec)
        ),
        str(CANONICAL_SHUTDOWN_BIT),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="P7 shutdown-bounded direct JTAG/AXI stage; default dry-run only.")
    add_common_arguments(parser)
    parser.add_argument("--stage-name", default="p7_jtag_axi_stage")
    parser.add_argument("--semantic-mode", choices=("rfap", "safe-idle"), default="rfap")
    parser.add_argument("--transaction-file", default="")
    parser.add_argument("--transaction-sha256", default="")
    parser.add_argument("--backend-manifest", default="")
    parser.add_argument("--backend-manifest-sha256", default="")
    parser.add_argument("--axi-base-address", default="0x43c00000")
    parser.add_argument("--jtag-frequency-hz", type=int, default=1_000_000)
    parser.add_argument("--preflight-timeout-sec", type=int, default=180)
    parser.add_argument("--stage-timeout-sec", type=int, default=300)
    parser.add_argument("--shutdown-timeout-sec", type=int, default=240)
    parser.add_argument("--evidence-dir", default="")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def _base_manifest(
    args: argparse.Namespace,
    safety: dict[str, Any],
    stage_errors: list[str],
    transaction: dict[str, Any],
) -> dict[str, Any]:
    return {
        "P7_JTAG_AXI_SAFE_STAGE": "DRY_RUN_ONLY",
        "generated_at_utc": now_utc(),
        "stage_name": args.stage_name,
        "semantic_mode": args.semantic_mode,
        "requested_execute_hardware": bool(args.execute_hardware),
        "hardware_actions_executed": False,
        "programmed_fpga": False,
        "programmed_candidate": False,
        "programmed_shutdown_before": False,
        "programmed_shutdown_after": False,
        "started_ps_elf": False,
        "drove_tfdu_txd": False,
        "enabled_tfdu_receiver": False,
        "uart_access": False,
        "ethernet_used": False,
        "motion_used": False,
        "hardware_acceptance": "PENDING_HW",
        "safety_validation": safety,
        "stage_validation_errors": stage_errors,
        "transaction_validation": transaction,
        "exit_code_policy": "returncode_must_be_exactly_zero_and_required_markers_must_match",
        "transaction_format_boundary": "strict_P7_JTAG_AXI_TRANSACTIONS_V1_no_source_no_eval_no_external_commands",
    }


def _emit(manifest: dict[str, Any], args: argparse.Namespace, evidence_dir: Path | None = None) -> None:
    if evidence_dir is not None:
        write_json(evidence_dir / "p7_jtag_axi_stage_summary.json", manifest)
    if args.json_summary:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print(f"P7_JTAG_AXI_SAFE_STAGE: {manifest['P7_JTAG_AXI_SAFE_STAGE']}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    safety = validate_request(args)
    stage_errors, transaction = _stage_control_errors(args)
    all_errors = list(safety["errors"]) + stage_errors
    manifest = _base_manifest(args, safety, stage_errors, transaction)

    if not args.execute_hardware:
        manifest["reason"] = "default dry-run path; no Vivado process or hardware connection was launched"
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "DRY_RUN_ONLY"
        evidence_dir = resolve_path(args.evidence_dir) if args.evidence_dir else None
        _emit(manifest, args, evidence_dir)
        return 0

    if all_errors:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "BLOCKED"
        manifest["reason"] = "authorization, immutable artifact, profile, or transaction validation failed before hardware"
        manifest["all_validation_errors"] = all_errors
        evidence_dir = resolve_path(args.evidence_dir) if args.evidence_dir else None
        _emit(manifest, args, evidence_dir)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence_dir = (
        resolve_path(args.evidence_dir)
        if args.evidence_dir
        else ROOT / "evidence" / "hardware" / "p7" / "jtag_axi" / args.stage_name / stamp
    )
    if evidence_dir.exists() and (
        evidence_dir.is_symlink() or not evidence_dir.is_dir() or any(evidence_dir.iterdir())
    ):
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "BLOCKED_EVIDENCE_DIR"
        manifest["reason"] = "hardware run evidence directory must be a new unique path or an existing empty directory"
        manifest["evidence_dir"] = str(evidence_dir)
        _emit(manifest, args)
        return 2
    evidence_dir.mkdir(parents=True, exist_ok=True)
    try:
        hardware_lock = HardwareExecutionLock.acquire(
            owner={
                "wrapper": "run_p7_jtag_axi_stage_safe.py",
                "stage_name": args.stage_name,
                "acquired_at_utc": now_utc(),
                "evidence_dir": str(evidence_dir),
            }
        )
    except RuntimeError as exc:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "BLOCKED_HARDWARE_LOCK"
        manifest["reason"] = str(exc)
        manifest["evidence_dir"] = str(evidence_dir)
        _emit(manifest, args, evidence_dir)
        return 2
    manifest["hardware_execution_lock"] = hardware_lock.record()
    execution_started = time.monotonic()
    global_deadline = execution_started + int(args.max_runtime_sec)
    manifest["global_runtime_deadline_source"] = "host_monotonic"
    manifest["global_runtime_guard_seconds"] = GLOBAL_RUNTIME_GUARD_SECONDS
    manifest["global_runtime_budget_components"] = {
        "contained_vivado_process_count": JTAG_WRAPPER_VIVADO_PROCESS_COUNT,
        "initial_empty_wait_seconds_per_process": CONTAINMENT_INITIAL_EMPTY_WAIT_SECONDS,
        "expected_tool_daemon_grace_seconds_per_process": EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
        "containment_allowance_seconds": JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS,
        "other_guard_seconds": JTAG_WRAPPER_OTHER_GUARD_SECONDS,
    }
    event_log = evidence_dir / "p7_jtag_axi_stage_events.jsonl"
    manifest["evidence_dir"] = str(evidence_dir)
    manifest["event_log"] = str(event_log)
    append_event(event_log, "authorized_execution_begin", stage=args.stage_name)

    abort_file = resolve_path(args.abort_file or str(DEFAULT_ABORT_FILE))
    preflight_result_file = evidence_dir / "p7_preflight_result.txt"
    for stale in (preflight_result_file,):
        if stale.exists():
            stale.unlink()
    preflight_command = build_preflight_command(args, preflight_result_file)
    preflight_proc = run_bounded_process(
        name="preflight",
        command=preflight_command,
        stdout_path=evidence_dir / "p7_preflight.stdout.log",
        stderr_path=evidence_dir / "p7_preflight.stderr.log",
        timeout_sec=deadline_timeout(
            args.preflight_timeout_sec,
            global_deadline,
            reserve_sec=(
                2 * args.shutdown_timeout_sec
                + args.stage_timeout_sec
                + containment_allowance(3)
                + JTAG_WRAPPER_OTHER_GUARD_SECONDS
            ),
        ),
        abort_file=abort_file,
        watch_abort=True,
    )
    manifest["hardware_actions_executed"] = True
    manifest["preflight_process"] = asdict(preflight_proc)
    manifest["preflight_result_file"] = str(preflight_result_file)
    preflight_stdout = safe_text(Path(preflight_proc.stdout_path))
    preflight_text = safe_text(preflight_result_file)
    preflight_ok, preflight_failures = evaluate_preflight(
        returncode=preflight_proc.returncode,
        stdout=preflight_stdout,
        result_text=preflight_text,
        expected_board_id=args.board_id,
        expected_part=args.expected_part,
        expected_target=args.expected_target,
    )
    manifest["preflight_failures"] = preflight_failures
    manifest["target_identity"] = parse_markers(preflight_text)
    append_event(event_log, "preflight_finished", returncode=preflight_proc.returncode, passed=preflight_ok)
    if not preflight_ok:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "FAIL_PREFLIGHT"
        manifest["reason"] = "read-only target preflight did not return rc=0 with exact identity markers"
        append_event(event_log, "authorized_execution_end", status=manifest["P7_JTAG_AXI_SAFE_STAGE"])
        record_global_runtime(
            manifest, started=execution_started, max_runtime_sec=int(args.max_runtime_sec)
        )
        _emit(manifest, args, evidence_dir)
        hardware_lock.release()
        return 1

    before_ok = False
    after_ok = False
    stage_ok = False
    stage_failures: list[str] = []
    backend_parse_ok = False
    backend_parse_failure = ""
    internal_error = ""
    candidate_child_reaped = False
    candidate_returncode: int | None = None
    shutdown_bit = resolve_path(args.shutdown_bitstream)
    candidate_bit = resolve_path(args.bitstream)
    candidate_ltx = resolve_path(args.ltx)
    transaction_file = resolve_path(args.transaction_file)
    auth_file = resolve_path(args.authorization_file)

    try:
        for path_value, expected, label in (
            (str(auth_file), args.authorization_sha256, "authorization file"),
            (str(shutdown_bit), args.shutdown_bitstream_sha256, "shutdown bitstream"),
        ):
            error = _verify_hash(path_value, expected, label)
            if error:
                raise RuntimeError(error)
        before_result_file = evidence_dir / "p7_shutdown_before_result.txt"
        if before_result_file.exists():
            before_result_file.unlink()
        before_command = build_stage_tcl_command(
            args,
            mode="SHUTDOWN",
            bitstream=shutdown_bit,
            ltx=None,
            transaction=None,
            result_file=before_result_file,
        )
        before_proc = run_bounded_process(
            name="shutdown_before",
            command=before_command,
            stdout_path=evidence_dir / "p7_shutdown_before.stdout.log",
            stderr_path=evidence_dir / "p7_shutdown_before.stderr.log",
            timeout_sec=deadline_timeout(
                args.shutdown_timeout_sec,
                global_deadline,
                reserve_sec=(
                    args.stage_timeout_sec
                    + args.shutdown_timeout_sec
                    + containment_allowance(2)
                    + JTAG_WRAPPER_OTHER_GUARD_SECONDS
                ),
            ),
            abort_file=abort_file,
            watch_abort=False,
        )
        before_ok, before_failures = evaluate_shutdown(
            before_proc.returncode,
            safe_text(Path(before_proc.stdout_path)),
            safe_text(before_result_file),
        )
        manifest["shutdown_before"] = {
            **asdict(before_proc),
            "result_file": str(before_result_file),
            "passed": before_ok,
            "failures": before_failures,
        }
        manifest["programmed_shutdown_before"] = before_ok
        append_event(event_log, "shutdown_before_finished", returncode=before_proc.returncode, passed=before_ok)
        if not before_ok:
            raise RuntimeError("shutdown-before requires normal rc=0 and TFDU_SHUTDOWN_PROGRAMMED marker")
        if abort_file.exists():
            raise RuntimeError(f"operator abort file appeared before candidate stage: {abort_file}")
        candidate_inputs = [
            (str(auth_file), args.authorization_sha256, "authorization file"),
            (str(candidate_bit), args.bitstream_sha256, "candidate bitstream"),
            (str(candidate_ltx), args.ltx_sha256, "candidate LTX"),
            (str(transaction_file), args.transaction_sha256, "transaction file"),
            (str(shutdown_bit), args.shutdown_bitstream_sha256, "shutdown bitstream"),
        ]
        if args.semantic_mode == "rfap":
            candidate_inputs.append(
                (args.backend_manifest, args.backend_manifest_sha256, "P7 JTAG backend manifest")
            )
        for path_value, expected, label in candidate_inputs:
            error = _verify_hash(path_value, expected, label)
            if error:
                raise RuntimeError(error)
        stage_result_file = evidence_dir / "p7_jtag_axi_raw_result.txt"
        if stage_result_file.exists():
            stage_result_file.unlink()
        stage_timeout = deadline_timeout(
            args.stage_timeout_sec,
            global_deadline,
            reserve_sec=(
                args.shutdown_timeout_sec
                + containment_allowance(1)
                + JTAG_WRAPPER_OTHER_GUARD_SECONDS
            ),
        )
        minimum_stage_runtime = int(
            transaction.get("runtime_feasibility", {}).get("minimum_stage_runtime_sec", 0)
        )
        if stage_timeout < minimum_stage_runtime:
            raise RuntimeError(
                "remaining global runtime cannot fit transaction estimate before candidate launch: "
                f"remaining_stage_timeout={stage_timeout} required={minimum_stage_runtime}"
            )
        stage_command = build_stage_tcl_command(
            args,
            mode="STAGE",
            bitstream=candidate_bit,
            ltx=candidate_ltx,
            transaction=transaction_file,
            result_file=stage_result_file,
            runtime_sec=stage_timeout,
        )
        if (
            args.semantic_mode == "rfap"
            and int(transaction.get("start_operation_count", 0)) > 0
        ):
            manifest["drove_tfdu_txd"] = True
            manifest["enabled_tfdu_receiver"] = True
            manifest["tfdu_activity_semantics"] = (
                "conservative_true_once_transmitting_candidate_command_is_launched"
            )
        append_event(event_log, "candidate_started", semantic_mode=args.semantic_mode)
        stage_proc = run_bounded_process(
            name="jtag_axi_stage",
            command=stage_command,
            stdout_path=evidence_dir / "p7_jtag_axi_stage.stdout.log",
            stderr_path=evidence_dir / "p7_jtag_axi_stage.stderr.log",
            timeout_sec=stage_timeout,
            abort_file=abort_file,
            watch_abort=True,
        )
        candidate_child_reaped = bool(stage_proc.process_tree_reaped)
        candidate_returncode = int(stage_proc.returncode)
        append_event(
            event_log,
            "candidate_child_reaped",
            process_tree_reaped=candidate_child_reaped,
            candidate_returncode=candidate_returncode,
        )
        stage_ok, stage_failures = evaluate_stage(
            stage_proc.returncode,
            safe_text(Path(stage_proc.stdout_path)),
            safe_text(stage_result_file),
            expected_target=args.expected_target,
            expected_part=args.expected_part,
            expected_operation_count=int(transaction["operation_count"]),
        )
        stage_markers = parse_markers(safe_text(stage_result_file))
        manifest["stage_process"] = {**asdict(stage_proc), "passed": stage_ok, "failures": stage_failures}
        manifest["stage_process"]["result_file"] = str(stage_result_file)
        manifest["stage_result_markers"] = stage_markers
        manifest["programmed_candidate"] = stage_markers.get("P7_CANDIDATE_PROGRAMMED") == "1"
        manifest["programmed_fpga"] = bool(
            manifest["programmed_shutdown_before"] or manifest["programmed_candidate"]
        )
        append_event(event_log, "stage_finished", returncode=stage_proc.returncode, passed=stage_ok)
    except Exception as exc:  # finally must still independently program shutdown.
        internal_error = f"{type(exc).__name__}: {exc}"
        append_event(event_log, "stage_exception", error=internal_error)
    finally:
        after_result_file = evidence_dir / "p7_shutdown_after_result.txt"
        if after_result_file.exists():
            after_result_file.unlink()
        reverify_errors = [
            item
            for item in (
                _verify_hash(str(shutdown_bit), args.shutdown_bitstream_sha256, "shutdown bitstream"),
            )
            if item
        ]
        if reverify_errors:
            manifest["shutdown_after"] = {
                "passed": False,
                "failures": reverify_errors,
                "returncode": 126,
                "attempted": False,
                "result_file": str(after_result_file),
            }
            append_event(event_log, "shutdown_after_blocked", failures=reverify_errors)
        else:
            after_command = build_stage_tcl_command(
                args,
                mode="SHUTDOWN",
                bitstream=shutdown_bit,
                ltx=None,
                transaction=None,
                result_file=after_result_file,
            )
            manifest["child_reaped_before_shutdown_after"] = candidate_child_reaped
            append_event(
                event_log,
                "shutdown_after_started",
                candidate_child_reaped=candidate_child_reaped,
                candidate_returncode=candidate_returncode,
            )
            try:
                after_timeout = deadline_timeout(
                    args.shutdown_timeout_sec,
                    global_deadline,
                    reserve_sec=JTAG_WRAPPER_OTHER_GUARD_SECONDS,
                )
            except RuntimeError as exc:
                # Safety takes precedence if an earlier process exceeded its bounded
                # termination allowance.  The run cannot PASS, but shutdown is still
                # attempted with a minimal independently bounded process window.
                after_timeout = 1
                internal_error = internal_error or f"{type(exc).__name__}: {exc}"
                manifest["shutdown_after_runtime_emergency"] = True
            after_proc = run_bounded_process(
                name="shutdown_after",
                command=after_command,
                stdout_path=evidence_dir / "p7_shutdown_after.stdout.log",
                stderr_path=evidence_dir / "p7_shutdown_after.stderr.log",
                timeout_sec=after_timeout,
                abort_file=abort_file,
                watch_abort=False,
            )
            after_ok, after_failures = evaluate_shutdown(
                after_proc.returncode,
                safe_text(Path(after_proc.stdout_path)),
                safe_text(after_result_file),
            )
            manifest["shutdown_after"] = {
                **asdict(after_proc),
                "passed": after_ok,
                "failures": after_failures,
                "attempted": True,
                "result_file": str(after_result_file),
            }
            manifest["programmed_shutdown_after"] = after_ok
            manifest["programmed_fpga"] = bool(manifest["programmed_fpga"] or after_ok)
            append_event(event_log, "shutdown_after_finished", returncode=after_proc.returncode, passed=after_ok)

    # Parse and reconstruct only after shutdown-after.  Tcl rc/markers prove
    # that the bounded operation stream ran; the strict backend parser proves
    # the actual fragment bytes, CRC/SHA, counters, lane masks, and safety
    # observations.  Neither half can independently promote this stage.
    if stage_ok and after_ok:
        try:
            transaction_hash_error = _verify_hash(
                str(transaction_file), args.transaction_sha256,
                "transaction file",
            )
            if transaction_hash_error:
                raise RuntimeError(transaction_hash_error)
            if args.semantic_mode == "safe-idle":
                parse_summary_path = evidence_dir / "p7_safe_idle_parse_summary.json"
                parsed = evaluate_safe_idle_raw(
                    safe_text(Path(manifest["stage_process"]["result_file"])),
                    expected_operation_count=int(transaction["operation_count"]),
                )
                write_json(parse_summary_path, parsed)
                backend_parse_ok = parsed.get("P7_SAFE_IDLE_PARSE") == "PASS"
                if not backend_parse_ok:
                    raise RuntimeError("strict P7 safe-idle parser did not return PASS")
                manifest["backend_parse"] = {
                    "passed": True,
                    "semantic_mode": "safe-idle",
                    "summary_file": str(parse_summary_path),
                    "summary_sha256": sha256_file(parse_summary_path),
                    "required_values": parsed.get("required_values"),
                    "raw_log_bound_to_this_hardware_process": True,
                }
                manifest["drove_tfdu_txd"] = False
                manifest["enabled_tfdu_receiver"] = False
            else:
                manifest_path = resolve_path(args.backend_manifest)
                manifest_hash_error = _verify_hash(
                    str(manifest_path), args.backend_manifest_sha256,
                    "P7 JTAG backend manifest",
                )
                if manifest_hash_error:
                    raise RuntimeError(manifest_hash_error)
                parse_summary_path = evidence_dir / "p7_jtag_backend_parse_summary.json"
                output_path = evidence_dir / "p7_jtag_reassembled_output.bin"
                parsed = parse_raw_result(
                    manifest_path=manifest_path,
                    raw_log_path=Path(manifest["stage_process"]["result_file"]),
                    output_path=output_path,
                    summary_path=parse_summary_path,
                )
                backend_parse_ok = parsed.get("P7_JTAG_BACKEND_PARSE") == "PASS"
                if not backend_parse_ok:
                    raise RuntimeError("strict P7 JTAG backend parser did not return PASS")
                stage_elapsed_seconds = float(manifest["stage_process"].get("elapsed_seconds", 0.0))
                if stage_elapsed_seconds <= 0.0:
                    raise RuntimeError("JTAG hardware process elapsed time is missing")
                object_length = int(parsed.get("object_length", 0))
                manifest["backend_parse"] = {
                    "passed": True,
                    "semantic_mode": "rfap",
                    "summary_file": str(parse_summary_path),
                    "summary_sha256": sha256_file(parse_summary_path),
                    "output_file": str(output_path),
                    "output_sha256": sha256_file(output_path),
                    "object_length": parsed.get("object_length"),
                    "object_crc32": parsed.get("object_crc32"),
                    "object_sha256": parsed.get("object_sha256"),
                    "lane_policy": parsed.get("lane_policy"),
                    "fragment_count": parsed.get("fragment_count"),
                    "missing_fragments": parsed.get("missing_fragments"),
                    "duplicate_fragments": parsed.get("duplicate_fragments"),
                    "error_counter_increments": parsed.get("error_counter_increments"),
                    "fragment_latency_upper_bound_us": parsed.get("fragment_latency_upper_bound_us"),
                    "object_transport_latency_upper_bound_us": parsed.get(
                        "object_transport_latency_upper_bound_us"
                    ),
                    "object_transport_latency_semantics": parsed.get(
                        "object_transport_latency_semantics"
                    ),
                    "poll_bound_application_goodput_lower_bound_bps": parsed.get(
                        "poll_bound_application_goodput_lower_bound_bps"
                    ),
                    "poll_bound_goodput_semantics": parsed.get("poll_bound_goodput_semantics"),
                    "host_end_to_end_elapsed_seconds": stage_elapsed_seconds,
                    "host_end_to_end_goodput_bps": round(
                        object_length * 8.0 / stage_elapsed_seconds, 6
                    ),
                    "host_end_to_end_time_source": "host_monotonic_child_process_elapsed",
                    "host_end_to_end_semantics": (
                        "includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; "
                        "not optical-only fragment latency"
                    ),
                    "raw_log_bound_to_this_hardware_process": True,
                }
                transmitted = int(transaction.get("start_operation_count", 0)) > 0
                manifest["drove_tfdu_txd"] = transmitted
                manifest["enabled_tfdu_receiver"] = transmitted
            append_event(event_log, "backend_parse_finished", passed=True)
        except Exception as exc:
            backend_parse_failure = f"{type(exc).__name__}: {exc}"
            manifest["backend_parse"] = {
                "passed": False,
                "failure": backend_parse_failure,
                "attempted_after_shutdown": True,
            }
            append_event(
                event_log, "backend_parse_finished", passed=False,
                failure=backend_parse_failure,
            )

    manifest["internal_error"] = internal_error
    manifest["stage_failures"] = stage_failures
    manifest["backend_parse_failure"] = backend_parse_failure
    if not candidate_child_reaped:
        stage_ok = False
        stage_failures.append("candidate child process tree was not reaped before shutdown-after")
    global_runtime_ok = record_global_runtime(
        manifest, started=execution_started, max_runtime_sec=int(args.max_runtime_sec)
    )
    if not global_runtime_ok:
        stage_ok = False
        stage_failures.append("global authorized runtime exceeded")
    if before_ok and stage_ok and after_ok and backend_parse_ok and not internal_error:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "PASS"
        manifest["reason"] = (
            "authorized non-transmitting safe-idle checks and both shutdown barriers passed"
            if args.semantic_mode == "safe-idle"
            else "authorized direct JTAG/AXI stage, strict byte/counter parser, and both shutdown barriers passed"
        )
        return_code = 0
    elif not after_ok:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "FAIL_SHUTDOWN_AFTER"
        manifest["reason"] = "stage is incomplete because shutdown-after lacked rc=0 plus marker"
        return_code = 1
    elif not before_ok:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "FAIL_SHUTDOWN_BEFORE"
        manifest["reason"] = "candidate was not allowed because shutdown-before failed"
        return_code = 1
    else:
        manifest["P7_JTAG_AXI_SAFE_STAGE"] = "FAIL_STAGE"
        manifest["reason"] = "stage return code/markers failed; nonzero return codes can never be promoted"
        return_code = 1
    append_event(event_log, "authorized_execution_end", status=manifest["P7_JTAG_AXI_SAFE_STAGE"])
    _emit(manifest, args, evidence_dir)
    hardware_lock.release()
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
