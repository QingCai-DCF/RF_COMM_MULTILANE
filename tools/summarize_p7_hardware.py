#!/usr/bin/env python3
"""Fail-closed P7 hardware evidence consistency gate and summary generator.

This program is deliberately read-only with respect to hardware.  It never starts
Vivado/XSDB, never opens a target, and never writes outside ``--output-dir``.  A
PASS is derived only by joining the fresh safe-wrapper records with their raw
logs, immutable artifact hashes, and (for direct JTAG) the strict backend parser
record.  Markdown conclusions, dry-runs, simulations, and offline manifests are
not hardware evidence by themselves.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import struct
import subprocess
import sys
import tempfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
MARKER_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,127}$")
PS_MARKER = "P7_PS_APPLICATION_SAFE_STAGE"
JTAG_MARKER = "P7_JTAG_AXI_SAFE_STAGE"
BACKEND_PARSE_MARKER = "P7_JTAG_BACKEND_PARSE"
JTAG_MANIFEST_SCHEMA = "rfap-p7-jtag-axi-dry-run-v1"
PS_COUNTS_PER_SECOND = 333_333_343
P7_TRACE_MAGIC = 0x52543750
HARDWARE_EXECUTION_LOCK_RELATIVE = Path(".hardware_authorization") / "P7_HARDWARE_EXECUTION.lock"
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
    "strict_ring_host_publication_supported",
    "stationary_identity_ledger_bound",
    "native_shutdown_readback_test",
    "p7_python_and_codec_tests",
    "real_vitis_build_source_bound",
)
CORE_READINESS_SOURCES = (
    "software/ps_driver/p7_app_service.h",
    "software/ps_driver/p7_app_service.c",
    "software/ps_driver/p7_runtime_main.c",
    "software/ps_driver/ir_driver.h",
    "software/ps_driver/ir_driver.c",
    "tools/p7_ps_mailbox_backend.py",
    "scripts/hw/run_p7_ps_application_stage_safe.py",
    "scripts/hw/p7_ps_application_execute.tcl",
)
AUTH_ARTIFACT_KEYS = {
    "plan": ("P7_PLAN_PATH", "P7_PLAN_SHA256"),
    "bitstream": ("BITSTREAM_PATH", "BITSTREAM_SHA256"),
    "xsa": ("XSA_PATH", "XSA_SHA256"),
    "elf": ("ELF_PATH", "ELF_SHA256"),
    "profile": ("PROFILE_PATH", "PROFILE_SHA256"),
    "active_xdc": ("ACTIVE_XDC_PATH", "ACTIVE_XDC_SHA256"),
    "pinmap": ("PINMAP_PATH", "PINMAP_SHA256"),
    "register_map": ("REGISTER_MAP_PATH", "REGISTER_MAP_SHA256"),
    "shutdown_bitstream": ("SHUTDOWN_BITSTREAM_PATH", "SHUTDOWN_BITSTREAM_SHA256"),
    "ltx": ("LTX_PATH", "LTX_SHA256"),
}
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
OFFLINE_CRITICAL_SOURCES = (
    "software/ps_driver/p7_app_service.h",
    "software/ps_driver/p7_app_service.c",
    "software/ps_driver/p7_runtime_main.c",
    "scripts/hw/p7_ps_application_execute.tcl",
    "scripts/hw/run_p7_ps_application_stage_safe.py",
    "scripts/hw/run_p7_jtag_axi_stage_safe.py",
    "tools/p7_contained_launcher.py",
    "tools/p7_ps_mailbox_backend.py",
    "tools/run_p7_gate.py",
    "tools/run_p7_ps_core_offline.py",
    "tools/summarize_p7_hardware.py",
)

REQUIRED_ARTIFACTS = (
    "plan",
    "bitstream",
    "xsa",
    "elf",
    "profile",
    "active_xdc",
    "pinmap",
    "register_map",
    "shutdown_bitstream",
)

REQUIRED_BOUNDARY_LENGTHS = (0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024)
REQUIRED_BOUNDARY_POLICIES = (1, 2, 3, 4)
POLICY_NAME_BY_ID = {
    1: "LANE0_ONLY",
    2: "LANE1_ONLY",
    3: "STRIPE_ROUND_ROBIN",
    4: "REPLICATE_0X3",
}
REQUIRED_BOUNDARY_JTAG = {
    (length, POLICY_NAME_BY_ID[policy])
    for length in REQUIRED_BOUNDARY_LENGTHS
    for policy in REQUIRED_BOUNDARY_POLICIES
}
REQUIRED_LARGE_JTAG = {
    (4_096, "STRIPE_ROUND_ROBIN", "deterministic_random"),
    (1_048_576, "LANE0_ONLY", "deterministic_random"),
    (1_048_576, "LANE1_ONLY", "deterministic_random"),
    (1_048_576, "STRIPE_ROUND_ROBIN", "deterministic_random"),
    (1_048_576, "REPLICATE_0X3", "deterministic_random"),
    (65_536, "STRIPE_ROUND_ROBIN", "counter"),
    (65_536, "STRIPE_ROUND_ROBIN", "prbs15"),
    (65_536, "STRIPE_ROUND_ROBIN", "deterministic_random"),
    (65_536, "STRIPE_ROUND_ROBIN", "binary_all_byte_values_repeated"),
}

STATIONARY_SLOT_CONTRACT = {
    0: ("stationary_deterministic_random_1048576_slot_0", "deterministic_random", 1_048_576, 1, 0, 0),
    1: ("stationary_counter_65536_slot_1", "counter", 65_536, 3, 1, 2),
    2: ("stationary_prbs15_65536_slot_2", "prbs15", 65_536, 3, 2, 2),
    3: ("stationary_binary_all_byte_values_repeated_65536_slot_3", "binary_all_byte_values_repeated", 65_536, 2, 0, 0),
    4: ("stationary_deterministic_random_1048576_slot_4", "deterministic_random", 1_048_576, 4, 0, 0),
    5: ("stationary_counter_4096_slot_5", "counter", 4_096, 3, 0, 0),
    6: ("stationary_prbs15_65536_slot_6", "prbs15", 65_536, 1, 0, 0),
    7: ("stationary_binary_all_byte_values_repeated_65536_slot_7", "binary_all_byte_values_repeated", 65_536, 2, 0, 0),
}

FINAL_REQUIRED_STAGES = (
    "safe_idle",
    "p6_frame_regression",
    "fragment_boundary",
    "large_object_jtag",
    "ps_runtime",
    "lane_fallback",
    "abort_restart",
    "queue_backpressure",
    "calibration",
    "stationary",
    "application_metrics",
    "shutdown",
    "consistency",
)

ALIASES: dict[str, tuple[str, ...]] = {
    "safe_idle": ("p7_safe_idle_recheck_summary",),
    "p6_frame_regression": ("p7_p6_frame_regression_summary",),
    "fragment_boundary": (
        "p7_fragment_boundary_hw_summary",
        "p7_fragment_boundary_matrix_summary",
    ),
    "large_object_jtag": (
        "p7_large_object_jtag_summary",
        "p7_large_object_summary",
    ),
    "ps_runtime": (
        "p7_ps_runtime_hw_summary",
        "p7_ps_app_runtime_summary",
    ),
    "lane_fallback": (
        "p7_lane_fallback_hw_summary",
        "p7_lane_scheduler_fallback_summary",
        "p7_lane_fault_fallback_summary",
    ),
    "abort_restart": (
        "p7_abort_restart_hw_summary",
        "p7_abort_restart_atomicity_summary",
        "p7_abort_restart_summary",
    ),
    "queue_backpressure": (
        "p7_queue_backpressure_hw_summary",
        "p7_queue_backpressure_summary",
    ),
    "calibration": (
        "p7_30min_calibration_summary",
        "p7_calibration_5min_embedded_summary",
    ),
    "stationary": (
        "p7_stationary_30min_summary",
        "p7_stationary_app_30min_soak_summary",
        "p7_application_30min_stationary_summary",
    ),
    "application_metrics": (
        "p7_application_metrics_summary",
        "p7_performance_summary",
    ),
    "shutdown": ("p7_shutdown_evidence_summary", "p7_shutdown_summary"),
    "consistency": (
        "p7_result_consistency_summary",
        "p7_evidence_consistency_summary",
    ),
    "final": (
        "p7_final_summary",
        "p7_final_acceptance_summary",
        "p7_stationary_local_application_layer_summary",
    ),
}


@dataclass
class Candidate:
    path: Path
    data: dict[str, Any]
    kind: str
    stage: str
    timestamp: float

    @property
    def executed(self) -> bool:
        return self.data.get("hardware_actions_executed") is True

    @property
    def marker(self) -> str:
        key = PS_MARKER if self.kind == "ps" else JTAG_MARKER
        return str(self.data.get(key, "MISSING"))


@dataclass
class StageResult:
    name: str
    status: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "stage": self.name,
            "result": self.status,
            "reason": self.reason,
            "evidence": self.evidence,
            "checks": self.checks,
            "metrics": self.metrics,
            "errors": self.errors,
            "notes": self.notes,
            "hardware_acceptance": "PASS" if self.status == "PASS" else "PENDING_HW" if self.status in {"PENDING_HW", "SKIP_WITH_REASON"} else "FAIL",
            "network_used": False,
            "motion_used": False,
            "available_lanes": 2,
            "max_lane_mask": "0x3",
            "product_final_acceptance": "PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT",
        }


@dataclass
class RepositoryEvidence:
    repo_root: Path
    hardware_root: Path
    output_dir: Path
    json_documents: dict[Path, dict[str, Any]] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    backend_parses: list[tuple[Path, dict[str, Any]]] = field(default_factory=list)
    jtag_manifests: list[tuple[Path, dict[str, Any]]] = field(default_factory=list)
    skip_records: list[tuple[Path, dict[str, Any]]] = field(default_factory=list)
    inventory: list[dict[str, Any]] = field(default_factory=list)
    provenance_rows: list[dict[str, Any]] = field(default_factory=list)
    git_head_checked: bool = False
    git_head: str | None = None


RISK_ORDER = {
    "safe_idle": 10,
    "p6_frame_regression": 20,
    "fragment_boundary_jtag": 25,
    "large_object_jtag": 30,
    "ps_runtime": 40,
    "lane_fallback": 50,
    "abort_restart": 60,
    "queue_backpressure": 70,
    "stationary": 80,
}

SEQUENCE_REQUIRED_GROUPS: tuple[tuple[int, set[str]], ...] = (
    (10, {"safe_idle"}),
    (20, {"p6_lane0", "p6_lane1", "p6_mask3"}),
    (25, {f"boundary:{length}:{policy}" for length, policy in REQUIRED_BOUNDARY_JTAG}),
    (30, {f"jtag:{length}:{policy}:{pattern}" for length, policy, pattern in REQUIRED_LARGE_JTAG if length == 4_096}),
    (31, {f"jtag:{length}:{policy}:{pattern}" for length, policy, pattern in REQUIRED_LARGE_JTAG if length == 65_536}),
    (32, {f"jtag:{length}:{policy}:{pattern}" for length, policy, pattern in REQUIRED_LARGE_JTAG if length == 1_048_576}),
    (40, {"ps_functional"}),
    (50, {"ps_fault_fallback"}),
    (60, {"ps_abort_restart"}),
    (70, {"ps_queue"}),
    (80, {"ps_stationary_qualified"}),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(root.resolve(strict=False))).replace("\\", "/")
    except ValueError:
        return str(path.resolve(strict=False)).replace("\\", "/")


def resolve_reference(value: Any, *, document: Path, repo_root: Path) -> Path | None:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        return None
    raw = Path(str(value))
    if raw.is_absolute():
        return raw.resolve(strict=False)
    options = ((document.parent / raw), (repo_root / raw))
    for option in options:
        if option.exists():
            return option.resolve(strict=False)
    return options[0].resolve(strict=False)


def parse_time(value: Any, fallback: float) -> float:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return fallback


def current_repository_head(evidence: RepositoryEvidence) -> str | None:
    if evidence.git_head_checked:
        return evidence.git_head
    evidence.git_head_checked = True
    if not (evidence.repo_root / ".git").exists():
        return None
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=evidence.repo_root,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip().lower()
    if completed.returncode == 0 and COMMIT_RE.fullmatch(value):
        evidence.git_head = value
    return evidence.git_head


def classify_jtag_stage(data: Mapping[str, Any]) -> str:
    stage_name = str(data.get("stage_name", "")).casefold().replace("-", "_")
    metadata = data.get("transaction_validation", {}).get("metadata", {})
    evidence_kind = str(metadata.get("EVIDENCE_KIND", "")).casefold().replace("-", "_") if isinstance(metadata, dict) else ""
    text = f"{stage_name} {evidence_kind}"
    if "safe" in text and "idle" in text:
        return "safe_idle"
    if "p6" in text and "frame" in text and ("regression" in text or "recheck" in text):
        return "p6_frame_regression"
    if "fragment" in text and "boundary" in text:
        return "fragment_boundary_jtag"
    if "large" in text and ("object" in text or "jtag" in text):
        return "large_object_jtag"
    return "unclassified_jtag"


def classify_ps_stage(data: Mapping[str, Any]) -> str:
    return {
        "functional": "ps_runtime",
        "fault-fallback": "lane_fallback",
        "queue": "queue_backpressure",
        "abort-restart": "abort_restart",
        "stationary": "stationary",
    }.get(str(data.get("mode", "")), "unclassified_ps")


def discover(evidence: RepositoryEvidence) -> None:
    if not evidence.hardware_root.is_dir():
        return
    for path in sorted(p for p in evidence.hardware_root.rglob("*") if p.is_file()):
        try:
            inventory_record = {
                "path": rel(path, evidence.repo_root),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            evidence.inventory.append(inventory_record)
        except OSError as exc:
            evidence.parse_errors.append(f"unable to inventory {path}: {exc}")
            continue
        if path.suffix.casefold() != ".json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            evidence.parse_errors.append(f"invalid JSON evidence {rel(path, evidence.repo_root)}: {exc}")
            continue
        if not isinstance(data, dict):
            evidence.parse_errors.append(f"JSON evidence is not an object: {rel(path, evidence.repo_root)}")
            continue
        evidence.json_documents[path] = data
        timestamp = parse_time(data.get("generated_at_utc"), path.stat().st_mtime)
        if PS_MARKER in data:
            evidence.candidates.append(Candidate(path, data, "ps", classify_ps_stage(data), timestamp))
        elif JTAG_MARKER in data:
            evidence.candidates.append(Candidate(path, data, "jtag", classify_jtag_stage(data), timestamp))
        elif data.get(BACKEND_PARSE_MARKER) is not None:
            evidence.backend_parses.append((path, data))
        elif data.get("schema") == JTAG_MANIFEST_SCHEMA:
            evidence.jtag_manifests.append((path, data))
        elif str(data.get("result", data.get("status", ""))).upper() == "SKIP_WITH_REASON":
            evidence.skip_records.append((path, data))


def append_error(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def process_record_errors(record: Any, label: str, *, document: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{label} process record missing"]
    append_error(errors, record.get("returncode") == 0, f"{label} returncode is not exactly 0")
    for key in ("timed_out", "abort_seen", "interrupted"):
        append_error(errors, record.get(key, False) is False, f"{label} reports {key}=true")
    append_error(errors, record.get("process_tree_reaped") is True, f"{label} does not prove process_tree_reaped=true")
    append_error(
        errors,
        record.get("containment_kind") in {"WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", "POSIX_PROCESS_GROUP"},
        f"{label} containment_kind is missing/unsupported",
    )
    append_error(errors, record.get("containment_assigned") is True, f"{label} does not prove containment assignment")
    append_error(errors, record.get("containment_closed") is True, f"{label} does not prove containment closure")
    append_error(errors, record.get("descendant_count_after") == 0, f"{label} does not prove zero descendants after reap")
    append_error(errors, not record.get("launch_error"), f"{label} has a launch error")
    for stream in ("stdout_path", "stderr_path"):
        if stream in record:
            path = resolve_reference(record.get(stream), document=document, repo_root=repo_root)
            append_error(errors, path is not None and path.is_file(), f"{label} {stream} missing")
    return errors


def marker_text(path: Path | None) -> str:
    if path is None or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_marker_text(text: str) -> tuple[dict[str, str], list[str]]:
    """Parse canonical KEY=VALUE records and preserve duplicate-key evidence."""
    result: dict[str, str] = {}
    duplicates: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if MARKER_KEY_RE.fullmatch(key) is None:
            continue
        if key in result:
            duplicates.append(key)
            continue
        result[key] = value
    return result, duplicates


def raw_marker_path(candidate: Candidate) -> Path:
    return candidate.path.parent / (
        "p7_jtag_axi_raw_result.txt" if candidate.kind == "jtag" else "p7_ps_application_raw_result.log"
    )


def raw_markers(candidate: Candidate) -> tuple[dict[str, str], list[str]]:
    return parse_marker_text(marker_text(raw_marker_path(candidate)))


def shutdown_errors(
    candidate: Candidate,
    which: str,
    *,
    require: bool = True,
) -> list[str]:
    errors: list[str] = []
    block = candidate.data.get(f"shutdown_{which}")
    if not isinstance(block, dict):
        return [f"shutdown-{which} record missing"] if require else []
    errors.extend(process_record_errors(block, f"shutdown-{which}", document=candidate.path, repo_root=candidate.path.parents[5] if len(candidate.path.parents) > 5 else candidate.path.parent))
    append_error(errors, block.get("passed") is True, f"shutdown-{which} passed is not true")
    if which == "after":
        append_error(errors, block.get("attempted", True) is True, "shutdown-after was not attempted")
    result_path = resolve_reference(block.get("result_file"), document=candidate.path, repo_root=candidate.path.parent)
    if result_path is None:
        result_path = candidate.path.parent / f"shutdown_{which}_result.txt"
        if candidate.kind == "jtag":
            result_path = candidate.path.parent / f"p7_shutdown_{which}_result.txt"
    stdout_path = resolve_reference(block.get("stdout_path"), document=candidate.path, repo_root=candidate.path.parent)
    result_markers, result_duplicates = parse_marker_text(marker_text(result_path))
    stdout_markers, stdout_duplicates = parse_marker_text(marker_text(stdout_path))
    append_error(errors, result_path.is_file(), f"shutdown-{which} fresh result file missing")
    append_error(errors, not result_duplicates, f"shutdown-{which} fresh result contains duplicate markers: {sorted(set(result_duplicates))}")
    append_error(errors, not stdout_duplicates, f"shutdown-{which} stdout contains duplicate markers: {sorted(set(stdout_duplicates))}")
    tfdu_value = result_markers.get("TFDU_SHUTDOWN_PROGRAMMED", stdout_markers.get("TFDU_SHUTDOWN_PROGRAMMED", ""))
    shutdown_exit = result_markers.get("SHUTDOWN_EXIT", stdout_markers.get("SHUTDOWN_EXIT"))
    append_error(
        errors,
        bool(tfdu_value) or shutdown_exit == "0",
        f"shutdown-{which} lacks TFDU_SHUTDOWN_PROGRAMMED or SHUTDOWN_EXIT=0",
    )
    append_error(errors, result_markers.get("P7_SHUTDOWN_RESULT") == "PASS", f"shutdown-{which} fresh result lacks exact P7_SHUTDOWN_RESULT=PASS")
    return errors


def verify_hash_record(
    label: str,
    record: Any,
    *,
    document: Path,
    repo_root: Path,
    expected_required: bool = True,
) -> tuple[list[str], dict[str, Any] | None]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{label} hash record missing"], None
    path = resolve_reference(record.get("path"), document=document, repo_root=repo_root)
    expected = str(record.get("expected_sha256", record.get("sha256", ""))).lower()
    recorded_actual = str(record.get("actual_sha256", expected)).lower()
    append_error(errors, path is not None and path.is_file(), f"{label} file missing: {record.get('path', 'MISSING')}")
    append_error(errors, bool(SHA256_RE.fullmatch(expected)), f"{label} expected SHA256 missing/malformed")
    if expected_required:
        append_error(errors, bool(SHA256_RE.fullmatch(recorded_actual)), f"{label} actual SHA256 missing/malformed")
    actual = "MISSING"
    if path is not None and path.is_file():
        actual = sha256_file(path)
        if SHA256_RE.fullmatch(expected):
            append_error(errors, actual == expected, f"{label} SHA256 mismatch")
        if SHA256_RE.fullmatch(recorded_actual):
            append_error(errors, actual == recorded_actual, f"{label} recorded actual SHA256 mismatch")
    normalized = None if path is None else {
        "label": label,
        "path": str(path),
        "expected_sha256": expected,
        "actual_sha256": actual,
    }
    return errors, normalized


def verify_embedded_file_records(value: Any, *, document: Path, repo_root: Path, prefix: str = "manifest") -> list[str]:
    """Re-hash every canonical ``{path,size_bytes,sha256}`` record in a manifest."""
    errors: list[str] = []
    if isinstance(value, dict):
        if "path" in value and "sha256" in value:
            record_errors, _record = verify_hash_record(
                prefix, value, document=document, repo_root=repo_root, expected_required=False
            )
            errors.extend(record_errors)
            path = resolve_reference(value.get("path"), document=document, repo_root=repo_root)
            if path is not None and path.is_file() and "size_bytes" in value:
                append_error(errors, path.stat().st_size == value.get("size_bytes"), f"{prefix} size record mismatch")
        for key, child in value.items():
            errors.extend(
                verify_embedded_file_records(
                    child, document=document, repo_root=repo_root, prefix=f"{prefix}.{key}"
                )
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(
                verify_embedded_file_records(
                    child, document=document, repo_root=repo_root, prefix=f"{prefix}[{index}]"
                )
            )
    return errors


def validate_raw_evidence_manifest(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[list[str], dict[str, Any] | None]:
    errors, record = verify_hash_record(
        "PS raw evidence SHA256 manifest",
        candidate.data.get("raw_evidence_sha256_manifest"),
        document=candidate.path,
        repo_root=evidence.repo_root,
        expected_required=False,
    )
    if record is None:
        return errors, None
    manifest_path = Path(record["path"])
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return errors + [f"PS raw evidence SHA256 manifest invalid: {exc}"], record
    append_error(errors, payload.get("schema") == "rf-comm-p7-raw-evidence-sha256-v1", "PS raw evidence manifest schema mismatch")
    records = payload.get("records")
    append_error(errors, isinstance(records, list), "PS raw evidence manifest records list missing")
    if not isinstance(records, list):
        return errors, record
    append_error(errors, payload.get("record_count") == len(records), "PS raw evidence manifest record_count mismatch")
    append_error(errors, payload.get("partial_file_count") == 0, "PS raw evidence manifest contains partial files")
    append_error(errors, payload.get("partial_files") == [], "PS raw evidence manifest partial_files is nonempty")
    observed: set[str] = set()
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            errors.append(f"PS raw evidence manifest record {index} is malformed")
            continue
        relative = str(item.get("path", ""))
        relative_path = Path(relative)
        append_error(errors, bool(relative) and not relative_path.is_absolute() and ".." not in relative_path.parts, f"PS raw evidence manifest record {index} path is unsafe")
        append_error(errors, relative not in observed, f"PS raw evidence manifest record duplicated: {relative}")
        observed.add(relative)
        target = (candidate.path.parent / relative_path).resolve(strict=False)
        try:
            target.relative_to(candidate.path.parent.resolve(strict=False))
        except ValueError:
            errors.append(f"PS raw evidence manifest record escapes run directory: {relative}")
            continue
        append_error(errors, target.is_file() and not target.is_symlink(), f"PS raw evidence file missing/symbolic: {relative}")
        append_error(errors, item.get("committed") is True, f"PS raw evidence file is not committed: {relative}")
        expected_sha = str(item.get("sha256", "")).lower()
        append_error(errors, SHA256_RE.fullmatch(expected_sha) is not None, f"PS raw evidence SHA256 malformed: {relative}")
        if target.is_file():
            append_error(errors, target.stat().st_size == item.get("size_bytes"), f"PS raw evidence size mismatch: {relative}")
            if SHA256_RE.fullmatch(expected_sha):
                append_error(errors, sha256_file(target) == expected_sha, f"PS raw evidence SHA256 mismatch: {relative}")
    expected_files = {
        path.relative_to(candidate.path.parent).as_posix()
        for path in candidate.path.parent.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.resolve(strict=False) not in {candidate.path.resolve(strict=False), manifest_path.resolve(strict=False)}
    }
    append_error(errors, observed == expected_files, f"PS raw evidence manifest completeness mismatch: missing={sorted(expected_files - observed)} extra={sorted(observed - expected_files)}")
    return errors, record


def profile_errors(path: Path | None) -> list[str]:
    if path is None or not path.is_file():
        return ["profile artifact is missing"]
    try:
        profile = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"profile JSON invalid: {exc}"]
    errors: list[str] = []
    append_error(errors, profile.get("network_required") is False, "profile network_required is not false")
    append_error(errors, profile.get("motion_required") is False, "profile motion_required is not false")
    append_error(errors, profile.get("lane_count") == 2, "profile lane_count is not 2")
    try:
        mask = int(str(profile.get("max_lane_mask", "")), 0)
    except ValueError:
        mask = -1
    append_error(errors, 1 <= mask <= 3, "profile max lane mask exceeds 0x3 or is invalid")
    allowed = profile.get("allowed_lane_masks")
    if isinstance(allowed, list):
        try:
            parsed = {int(str(item), 0) for item in allowed}
        except (TypeError, ValueError):
            parsed = set()
        append_error(errors, parsed == {1, 2, 3}, "profile allowed lane masks are not exactly 0x1/0x2/0x3")
    else:
        errors.append("profile allowed_lane_masks list missing")
    return errors


def hardware_execution_lock_errors(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[list[str], dict[str, Any] | None]:
    """Validate the immutable record proving exclusive ownership of the board.

    The lock file itself is deliberately absent after a clean wrapper exit.  The
    safe-wrapper summary therefore carries the acquisition record while its own
    SHA256 (and the chronology ledger) makes that record immutable.
    """

    errors: list[str] = []
    record = candidate.data.get("hardware_execution_lock")
    if not isinstance(record, dict):
        return ["hardware_execution_lock record missing"], None
    canonical = (evidence.repo_root / HARDWARE_EXECUTION_LOCK_RELATIVE).resolve(strict=False)
    recorded_path = resolve_reference(record.get("path"), document=candidate.path, repo_root=evidence.repo_root)
    append_error(errors, recorded_path == canonical, "hardware execution lock path is not canonical")
    append_error(errors, record.get("acquired") is True, "hardware execution lock was not recorded as acquired")
    append_error(errors, record.get("stale_lock_auto_recovery") is False, "hardware execution lock permits/claims stale-lock auto-recovery")
    token_sha = str(record.get("token_sha256", "")).lower()
    append_error(errors, SHA256_RE.fullmatch(token_sha) is not None, "hardware execution lock token SHA256 is missing/malformed")
    owner = record.get("owner")
    if not isinstance(owner, dict):
        errors.append("hardware execution lock owner record missing")
        return errors, dict(record)
    expected_wrapper = "run_p7_ps_application_stage_safe.py" if candidate.kind == "ps" else "run_p7_jtag_axi_stage_safe.py"
    append_error(errors, owner.get("wrapper") == expected_wrapper, "hardware execution lock owner wrapper mismatch")
    append_error(errors, owner.get("stage_name") == candidate.data.get("stage_name"), "hardware execution lock owner stage mismatch")
    if candidate.kind == "ps":
        append_error(errors, owner.get("mode") == candidate.data.get("mode"), "hardware execution lock owner mode mismatch")
    owner_dir = resolve_reference(owner.get("evidence_dir"), document=candidate.path, repo_root=evidence.repo_root)
    append_error(errors, owner_dir == candidate.path.parent.resolve(strict=False), "hardware execution lock owner evidence directory mismatch")
    acquired_at = parse_time(owner.get("acquired_at_utc"), float("nan"))
    append_error(errors, acquired_at == acquired_at, "hardware execution lock acquisition UTC timestamp is missing/malformed")
    return errors, dict(record)


def core_readiness_errors(path: Path, evidence: RepositoryEvidence) -> list[str]:
    """Independently validate the source-bound PS-core hardware attestation."""

    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"PS core readiness JSON invalid: {exc}"]
    if not isinstance(payload, dict):
        return ["PS core readiness payload is not an object"]
    append_error(errors, payload.get("schema") == "rf-comm-p7-ps-core-hardware-readiness-v1", "PS core readiness schema mismatch")
    append_error(errors, payload.get("P7_PS_CORE_HARDWARE_READINESS") == "PASS", "PS core readiness attestation is not PASS")
    append_error(errors, payload.get("hardware_actions_executed") is False, "PS core readiness attestation claims hardware actions")
    append_error(errors, payload.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", "PS core readiness attestation improperly promotes hardware acceptance")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        errors.append("PS core readiness checks object missing")
        checks = {}
    for name in CORE_READINESS_CHECKS:
        append_error(errors, checks.get(name) is True, f"PS core readiness check is not true: {name}")
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        errors.append("PS core readiness source hashes missing")
        sources = {}
    root = evidence.repo_root.resolve(strict=False)
    for relative in CORE_READINESS_SOURCES:
        expected = str(sources.get(relative, "")).lower()
        source = (root / relative).resolve(strict=False)
        try:
            source.relative_to(root)
        except ValueError:
            errors.append(f"PS core readiness source escapes repository: {relative}")
            continue
        append_error(errors, source.is_file(), f"PS core readiness source missing: {relative}")
        append_error(errors, SHA256_RE.fullmatch(expected) is not None, f"PS core readiness source SHA256 malformed: {relative}")
        if source.is_file() and SHA256_RE.fullmatch(expected):
            append_error(errors, sha256_file(source) == expected, f"PS core readiness source hash mismatch: {relative}")
    service_path = root / "software/ps_driver/p7_app_service.c"
    if service_path.is_file():
        service_text = service_path.read_text(encoding="utf-8", errors="replace")
        running_index = service_text.find("descriptor->status = P7_DESCRIPTOR_RUNNING;")
        start_index = service_text.find("object_start = p7_get_ticks();", running_index + 1)
        input_integrity_index = service_text.find("p7_integrity_checked(", start_index + 1)
        output_integrity_index = service_text.find("p7_integrity_checked(", input_integrity_index + 1)
        end_index = service_text.find("object_end = p7_get_ticks();", output_integrity_index + 1)
        append_error(
            errors,
            0 <= running_index < start_index < input_integrity_index < output_integrity_index < end_index,
            "PS object latency source boundary is not RUNNING/start -> input integrity -> output integrity/end",
        )
    native = payload.get("native_shutdown_test")
    append_error(errors, isinstance(native, dict) and native.get("returncode") == 0, "PS core native shutdown test did not pass")
    unit_tests = payload.get("unit_tests")
    append_error(errors, isinstance(unit_tests, dict) and unit_tests.get("returncode") == 0, "PS core Python/codec tests did not pass")
    return errors


def parse_authorization(path: Path) -> tuple[dict[str, str], list[str], list[str]]:
    fields: dict[str, str] = {}
    markers: list[str] = []
    duplicates: list[str] = []
    for raw_line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            markers.append(line)
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in fields:
            duplicates.append(key)
        fields[key] = value.strip()
    return fields, markers, duplicates


def candidate_output_hash_records(candidate: Candidate) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if candidate.kind == "jtag":
        backend = candidate.data.get("backend_parse")
        if isinstance(backend, dict) and backend.get("output_file") and backend.get("output_sha256"):
            records.append(
                {
                    "name": "jtag_reassembled_output",
                    "path": backend.get("output_file"),
                    "sha256": str(backend.get("output_sha256", "")).lower(),
                    "size_bytes": backend.get("object_length"),
                }
            )
        return records
    post = candidate.data.get("postprocess")
    if not isinstance(post, dict):
        return records
    for group in ("cases", "boundary_cases"):
        for index, case in enumerate(post.get(group, [])):
            if not isinstance(case, dict):
                continue
            descriptor = case.get("descriptor") if isinstance(case.get("descriptor"), dict) else {}
            sha = str(case.get("output_sha256", descriptor.get("output_sha256", ""))).lower()
            if SHA256_RE.fullmatch(sha):
                records.append(
                    {
                        "name": str(case.get("name", f"{group}_{index}")),
                        "sha256": sha,
                        "size_bytes": int(case.get("output_bytes", descriptor.get("object_length", -1))),
                    }
                )
    trace = post.get("stationary_trace_validation")
    if isinstance(trace, dict):
        for record in trace.get("records", []):
            if not isinstance(record, dict) or not isinstance(record.get("output_file"), dict):
                continue
            output = record["output_file"]
            records.append(
                {
                    "name": f"stationary_terminal_{record.get('sequence')}",
                    "path": output.get("path"),
                    "sha256": str(output.get("sha256", output.get("actual_sha256", ""))).lower(),
                    "size_bytes": output.get("size_bytes"),
                }
            )
    return records


def load_authorized_events(candidate: Candidate) -> tuple[Path, list[dict[str, Any]], list[str]]:
    event_path = candidate.path.parent / (
        "p7_ps_application_events.json" if candidate.kind == "ps" else "p7_jtag_axi_stage_events.jsonl"
    )
    errors: list[str] = []
    append_error(errors, event_path.is_file(), "authorized hardware event log missing")
    events: list[dict[str, Any]] = []
    if event_path.is_file():
        try:
            if candidate.kind == "ps":
                payload = json.loads(event_path.read_text(encoding="utf-8", errors="strict"))
                events = [dict(item) for item in payload.get("events", []) if isinstance(item, dict)] if isinstance(payload, dict) else []
            else:
                for line in event_path.read_text(encoding="utf-8", errors="strict").splitlines():
                    if line.strip():
                        value = json.loads(line)
                        if isinstance(value, dict):
                            events.append(dict(value))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"authorized hardware event log invalid: {exc}")
    return event_path, events, errors


def authorized_event_errors(candidate: Candidate, evidence: RepositoryEvidence) -> list[str]:
    _event_path, events, errors = load_authorized_events(candidate)
    names = [str(item.get("event", "")) for item in events]
    required_events = (
        "authorized_execution_begin",
        "candidate_started",
        "candidate_child_reaped",
        "shutdown_after_started",
        "authorized_execution_end",
    )
    for required in required_events:
        append_error(errors, names.count(required) == 1, f"authorized event sequence must contain exactly one {required}")
    if all(required in names for required in required_events):
        begin_index = names.index("authorized_execution_begin")
        candidate_start_index = names.index("candidate_started")
        reaped_index = names.index("candidate_child_reaped")
        shutdown_index = names.index("shutdown_after_started")
        end_index = names.index("authorized_execution_end")
        append_error(errors, begin_index < candidate_start_index < reaped_index < shutdown_index < end_index, "authorized event order is not begin < candidate-started < candidate-reaped < shutdown-after-started < end")
        append_error(errors, events[reaped_index].get("process_tree_reaped") is True, "candidate-child-reaped event does not assert process_tree_reaped=true")
        append_error(errors, events[shutdown_index].get("candidate_child_reaped") is True, "shutdown-after-started event does not assert candidate_child_reaped=true")
        process = _candidate_process(candidate)
        candidate_returncode = process.get("returncode") if isinstance(process, dict) else None
        append_error(errors, events[reaped_index].get("candidate_returncode") == candidate_returncode, "candidate-child-reaped event returncode does not bind the candidate process")
        append_error(errors, events[shutdown_index].get("candidate_returncode") == candidate_returncode, "shutdown-after-started event returncode does not bind the candidate process")
        append_error(errors, events[end_index].get("status") == candidate.marker, "authorized-execution-end status does not bind the wrapper result")
    event_times: list[float] = []
    for index, item in enumerate(events):
        timestamp = parse_time(item.get("timestamp_utc"), float("nan"))
        append_error(errors, timestamp == timestamp, f"authorized event {index} UTC timestamp missing/malformed")
        if timestamp == timestamp:
            event_times.append(timestamp)
    append_error(errors, event_times == sorted(event_times), "authorized event timestamps are not nondecreasing")
    if all(required in names for required in required_events):
        event_time_by_name = {
            name: parse_time(events[names.index(name)].get("timestamp_utc"), float("nan"))
            for name in required_events
        }
        process_blocks = (
            (candidate.data.get("preflight" if candidate.kind == "ps" else "preflight_process"), "preflight"),
            (candidate.data.get("shutdown_before"), "shutdown-before"),
            (_candidate_process(candidate), "candidate"),
            (candidate.data.get("shutdown_after"), "shutdown-after"),
        )
        intervals: dict[str, tuple[float, float]] = {}
        for block, label in process_blocks:
            if not isinstance(block, dict):
                errors.append(f"{label} process interval missing from authorized chronology")
                continue
            start = parse_time(block.get("started_at_utc"), float("nan"))
            end = parse_time(block.get("ended_at_utc"), float("nan"))
            append_error(errors, start == start and end == end and start <= end, f"{label} process interval malformed")
            intervals[label] = (start, end)
        if len(intervals) == 4:
            begin = event_time_by_name["authorized_execution_begin"]
            candidate_started = event_time_by_name["candidate_started"]
            reaped = event_time_by_name["candidate_child_reaped"]
            shutdown_started = event_time_by_name["shutdown_after_started"]
            end = event_time_by_name["authorized_execution_end"]
            append_error(
                errors,
                begin <= intervals["preflight"][0] <= intervals["preflight"][1]
                <= intervals["shutdown-before"][0] <= intervals["shutdown-before"][1]
                <= candidate_started <= intervals["candidate"][0] <= intervals["candidate"][1]
                <= reaped <= shutdown_started <= intervals["shutdown-after"][0]
                <= intervals["shutdown-after"][1] <= end,
                "authorized event/process chronology does not enclose preflight, shutdown barriers, candidate, reap, and final shutdown in order",
            )
    append_error(errors, candidate.data.get("child_reaped_before_shutdown_after") is True, "wrapper summary does not assert child_reaped_before_shutdown_after=true")
    return errors


def authorized_execution_boundaries(candidate: Candidate) -> tuple[str | None, str | None]:
    _path, events, _errors = load_authorized_events(candidate)
    begin = [item.get("timestamp_utc") for item in events if item.get("event") == "authorized_execution_begin"]
    end = [item.get("timestamp_utc") for item in events if item.get("event") == "authorized_execution_end"]
    if len(begin) != 1 or len(end) != 1:
        return None, None
    return str(begin[0]), str(end[0])


def common_runner_errors(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[list[str], dict[str, Any]]:
    data = candidate.data
    errors: list[str] = []
    provenance: dict[str, Any] = {"summary": rel(candidate.path, evidence.repo_root), "kind": candidate.kind, "stage": candidate.stage}
    provenance.update(
        {
            "generated_at_utc": data.get("generated_at_utc"),
            "hardware_actions_executed": candidate.executed,
            "programmed_fpga": data.get("programmed_candidate"),
            "drove_tfdu_txd": data.get("drove_tfdu_txd"),
            "enabled_tfdu_receiver": data.get("enabled_tfdu_receiver"),
            "uart_access": data.get("uart_access"),
            "network_used": data.get("ethernet_used"),
            "motion_used": data.get("motion_used"),
        }
    )
    append_error(errors, candidate.marker == "PASS", f"runner status is {candidate.marker}, not PASS")
    append_error(errors, candidate.executed, "runner PASS has hardware_actions_executed != true")
    append_error(errors, data.get("ethernet_used") is False, "runner does not prove ethernet_used=false")
    append_error(errors, data.get("motion_used") is False, "runner does not prove motion_used=false")
    append_error(errors, data.get("uart_access") is False, "runner does not prove uart_access=false")
    if candidate.kind == "jtag" and data.get("semantic_mode") == "safe-idle":
        append_error(errors, data.get("drove_tfdu_txd") is False, "safe-idle runner does not prove drove_tfdu_txd=false")
        append_error(errors, data.get("enabled_tfdu_receiver") is False, "safe-idle runner does not prove enabled_tfdu_receiver=false")
    else:
        append_error(errors, data.get("drove_tfdu_txd") is True, "transmitting runner does not prove drove_tfdu_txd=true")
        append_error(errors, data.get("enabled_tfdu_receiver") is True, "transmitting runner does not prove enabled_tfdu_receiver=true")
    append_error(errors, data.get("programmed_shutdown_before") is True, "runner did not prove shutdown-before")
    append_error(errors, data.get("programmed_shutdown_after") is True, "runner did not prove shutdown-after")
    lock_errors, lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(lock_errors)
    if lock_record is not None:
        provenance["hardware_execution_lock"] = lock_record

    safety = data.get("safety_validation")
    if not isinstance(safety, dict):
        errors.append("safety_validation object missing")
        return errors, provenance
    append_error(errors, safety.get("P7_HARDWARE_SAFETY") == "PASS", "hardware safety gate is not PASS")
    append_error(errors, safety.get("ready_for_hardware_preflight") is True, "hardware preflight readiness is not true")
    append_error(errors, safety.get("errors") == [], "hardware safety errors are nonempty")
    append_error(errors, safety.get("authorization_environment_present") is True, "external hardware authorization was not present")
    append_error(errors, safety.get("no_ethernet") is True, "safety record no_ethernet is not true")
    append_error(errors, safety.get("no_motion") is True, "safety record no_motion is not true")
    append_error(errors, safety.get("shutdown_on_exit") is True, "safety record shutdown_on_exit is not true")
    append_error(errors, safety.get("lane_count") == 2, "safety lane_count is not 2")
    append_error(errors, str(safety.get("max_lane_mask", "")).casefold() == "0x3", "safety max_lane_mask is not 0x3")
    try:
        runtime = int(safety.get("max_runtime_sec", 0))
    except (TypeError, ValueError):
        runtime = 0
    append_error(errors, 1 <= runtime <= 1800, "authorized runtime is outside 1..1800 seconds")
    append_error(errors, safety.get("abort_file_present") is False, "abort file was present")

    source_requested = str(safety.get("source_commit_requested", "")).lower()
    source_current = str(safety.get("source_commit_current", "")).lower()
    append_error(errors, bool(COMMIT_RE.fullmatch(source_requested)), "source commit is missing/malformed")
    append_error(errors, source_requested == source_current, "requested and current source commits differ")
    if (evidence.repo_root / ".git").exists():
        actual_head = current_repository_head(evidence)
        append_error(errors, actual_head is not None, "unable to read current repository HEAD")
        append_error(errors, actual_head == source_requested, "hardware source commit does not match current repository HEAD")
    provenance["source_commit"] = source_requested

    auth_fields = safety.get("authorization_fields")
    if not isinstance(auth_fields, dict):
        errors.append("authorization fields missing")
        auth_fields = {}
    exact_auth = {
        "AUTHORIZED_STAGE": "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET",
        "USER_HARDWARE_AUTHORIZATION_FOR_P7": "GRANTED",
        "BOARD_ID": str(auth_fields.get("BOARD_ID", "")),
        "EXPECTED_PART": str(auth_fields.get("EXPECTED_PART", "")),
        "EXPECTED_TARGET": str(auth_fields.get("EXPECTED_TARGET", "")),
        "SOURCE_COMMIT": source_requested,
        "SHUTDOWN_ON_EXIT": "required",
        "NO_ETHERNET": "true",
        "NO_MOTION": "true",
        "LANE_COUNT": "2",
        "MAX_LANE_MASK": "0x3",
    }
    for key, expected in exact_auth.items():
        append_error(errors, str(auth_fields.get(key, "")).casefold() == expected.casefold(), f"authorization field {key} mismatch")
    append_error(errors, bool(str(auth_fields.get("BOARD_ID", "")).strip()), "authorization BOARD_ID is empty")
    append_error(errors, bool(str(auth_fields.get("EXPECTED_PART", "")).strip()), "authorization EXPECTED_PART is empty")
    append_error(errors, bool(str(auth_fields.get("EXPECTED_TARGET", "")).strip()), "authorization EXPECTED_TARGET is empty")
    for forbidden in ("ETHERNET", "DHCP", "TCP", "ROTATION", "MOTION"):
        value = auth_fields.get(f"ALLOW_{forbidden}")
        if value is not None:
            append_error(errors, str(value).casefold() in {"false", "0", "no"}, f"authorization unexpectedly enables {forbidden}")
    try:
        auth_runtime = int(auth_fields.get("MAX_RUNTIME_SEC", 0))
    except (TypeError, ValueError):
        auth_runtime = 0
    append_error(errors, runtime <= auth_runtime <= 1800, "authorization MAX_RUNTIME_SEC is invalid")
    # Re-hash every authorization extension path independently.  This covers
    # PS7 init, P6/P7 build summaries, input seed, active profile, promotion
    # record, core readiness, frozen shutdown, and direct-JTAG bundle/DSL.
    authorization_extensions: dict[str, Any] = {}
    for path_key, path_value in auth_fields.items():
        if not path_key.endswith("_PATH"):
            continue
        sha_key = path_key[:-5] + "_SHA256"
        expected_sha = str(auth_fields.get(sha_key, "")).lower()
        bound_path = resolve_reference(path_value, document=candidate.path, repo_root=evidence.repo_root)
        append_error(errors, bound_path is not None and bound_path.is_file(), f"authorization extension path missing: {path_key}")
        append_error(errors, SHA256_RE.fullmatch(expected_sha) is not None, f"authorization extension SHA256 missing/malformed: {sha_key}")
        if bound_path is not None and bound_path.is_file() and SHA256_RE.fullmatch(expected_sha):
            append_error(errors, sha256_file(bound_path) == expected_sha, f"authorization extension hash mismatch: {path_key}")
            authorization_extensions[path_key] = {
                "path": str(bound_path),
                "size_bytes": bound_path.stat().st_size,
                "sha256": sha256_file(bound_path),
                "authorization_sha256_key": sha_key,
            }
    if candidate.kind == "ps":
        append_error(errors, str(auth_fields.get("P7_PS_MODE", "")) == str(data.get("mode", "")), "authorization P7_PS_MODE mismatch")
        append_error(errors, str(auth_fields.get("P7_PS_CORE_READINESS", "")) == "PASS", "authorization does not bind P7_PS_CORE_READINESS=PASS")
    else:
        append_error(errors, str(auth_fields.get("P7_JTAG_STAGE_NAME", "")) == str(data.get("stage_name", "")), "authorization P7_JTAG_STAGE_NAME mismatch")
    provenance.update(
        {
            "board_id": str(auth_fields.get("BOARD_ID", "")),
            "expected_part": str(auth_fields.get("EXPECTED_PART", "")),
            "expected_target": str(auth_fields.get("EXPECTED_TARGET", "")),
        }
    )

    auth_errors, auth_record = verify_hash_record(
        "authorization",
        safety.get("authorization"),
        document=candidate.path,
        repo_root=evidence.repo_root,
    )
    errors.extend(auth_errors)
    if auth_record:
        provenance["authorization"] = auth_record
        try:
            parsed_fields, auth_markers, duplicates = parse_authorization(Path(auth_record["path"]))
        except (OSError, UnicodeError) as exc:
            errors.append(f"authorization file cannot be parsed independently: {exc}")
        else:
            append_error(errors, not duplicates, f"authorization file contains duplicate keys: {sorted(set(duplicates))}")
            append_error(errors, "P7_STATIONARY_APP_LAYER_APPROVED" in auth_markers, "authorization approval marker missing")
            normalized_summary_fields = {str(key): str(value) for key, value in auth_fields.items()}
            append_error(errors, parsed_fields == normalized_summary_fields, "runner authorization_fields do not exactly match the immutable authorization file")
    provenance["authorization_extensions"] = authorization_extensions

    artifacts = safety.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifact hash records missing")
        artifacts = {}
    provenance_artifacts: dict[str, Any] = {}
    for name in REQUIRED_ARTIFACTS:
        artifact_errors, record = verify_hash_record(
            f"artifact:{name}", artifacts.get(name), document=candidate.path, repo_root=evidence.repo_root
        )
        errors.extend(artifact_errors)
        if record:
            provenance_artifacts[name] = record
            auth_path_key, auth_sha_key = AUTH_ARTIFACT_KEYS[name]
            auth_path = resolve_reference(auth_fields.get(auth_path_key), document=candidate.path, repo_root=evidence.repo_root)
            append_error(errors, auth_path == Path(record["path"]).resolve(strict=False), f"authorization artifact path does not bind selected {name}")
            append_error(errors, str(auth_fields.get(auth_sha_key, "")).lower() == str(record["actual_sha256"]).lower(), f"authorization artifact SHA256 does not bind selected {name}")
            if name == "profile":
                errors.extend(profile_errors(Path(record["path"])))
    if candidate.kind == "jtag":
        artifact_errors, record = verify_hash_record(
            "artifact:ltx", artifacts.get("ltx"), document=candidate.path, repo_root=evidence.repo_root
        )
        errors.extend(artifact_errors)
        if record:
            provenance_artifacts["ltx"] = record
            auth_path_key, auth_sha_key = AUTH_ARTIFACT_KEYS["ltx"]
            auth_path = resolve_reference(auth_fields.get(auth_path_key), document=candidate.path, repo_root=evidence.repo_root)
            append_error(errors, auth_path == Path(record["path"]).resolve(strict=False), "authorization artifact path does not bind selected ltx")
            append_error(errors, str(auth_fields.get(auth_sha_key, "")).lower() == str(record["actual_sha256"]).lower(), "authorization artifact SHA256 does not bind selected ltx")
    provenance["artifacts"] = provenance_artifacts

    target = data.get("target_identity")
    if not isinstance(target, dict):
        errors.append("fresh target identity record missing")
        target = {}
    append_error(errors, target.get("P7_HW_PREFLIGHT_RESULT") == "PASS", "fresh target preflight result is not PASS")
    append_error(errors, target.get("P7_HW_PREFLIGHT_READ_ONLY") == "1", "preflight was not read-only")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_BOARD_ID", "")) == provenance["board_id"], "live board ID mismatch")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_PART", "")).casefold() == provenance["expected_part"].casefold(), "live part mismatch")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_TARGET", "")).casefold() == provenance["expected_target"].casefold(), "live target mismatch")
    preflight_result_path = candidate.path.parent / ("p7_hw_preflight_result.txt" if candidate.kind == "ps" else "p7_preflight_result.txt")
    append_error(errors, preflight_result_path.is_file(), "canonical read-only preflight result is missing")
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_result_path))
    append_error(errors, not preflight_duplicates, f"preflight result contains duplicate markers: {sorted(set(preflight_duplicates))}")
    for key in (
        "P7_HW_PREFLIGHT_RESULT",
        "P7_HW_PREFLIGHT_READ_ONLY",
        "P7_HW_PREFLIGHT_BOARD_ID",
        "P7_HW_PREFLIGHT_PART",
        "P7_HW_PREFLIGHT_TARGET",
    ):
        append_error(errors, preflight_markers.get(key) == str(target.get(key, "")), f"preflight raw/summary identity mismatch: {key}")

    if candidate.kind == "ps":
        preflight = data.get("preflight")
        stage_process = data.get("ps_process")
        raw_path = candidate.path.parent / "p7_ps_application_raw_result.log"
        append_error(errors, data.get("programmed_candidate") is True, "PS candidate was not programmed")
        append_error(errors, data.get("started_ps_elf") is True, "real PS ELF was not downloaded/started")
        readiness = data.get("core_hardware_readiness")
        append_error(errors, isinstance(readiness, dict) and readiness.get("status") == "PASS", "PS core hardware readiness is not PASS")
        if isinstance(readiness, dict):
            ready_errors, ready_record = verify_hash_record(
                "PS core readiness", readiness, document=candidate.path, repo_root=evidence.repo_root
            )
            errors.extend(ready_errors)
            if ready_record:
                provenance["core_readiness"] = ready_record
                errors.extend(core_readiness_errors(Path(ready_record["path"]), evidence))
        for label in ("bundle_manifest", "execution_plan", "frozen_shutdown"):
            record_errors, record = verify_hash_record(
                f"PS {label}", data.get(label), document=candidate.path, repo_root=evidence.repo_root,
                expected_required=False,
            )
            errors.extend(record_errors)
            if record:
                provenance[label] = record
        raw_manifest_errors, raw_manifest_record = validate_raw_evidence_manifest(candidate, evidence)
        errors.extend(raw_manifest_errors)
        if raw_manifest_record:
            provenance["raw_evidence_sha256_manifest"] = raw_manifest_record
        bundle_path = resolve_reference(
            data.get("bundle_manifest", {}).get("path") if isinstance(data.get("bundle_manifest"), dict) else None,
            document=candidate.path,
            repo_root=evidence.repo_root,
        )
        if bundle_path is not None and bundle_path.is_file():
            try:
                bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8", errors="strict"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"PS bundle manifest JSON invalid: {exc}")
            else:
                append_error(errors, bundle_payload.get("schema") == "rf-comm-p7-ps-hardware-bundle-v1", "PS bundle manifest schema mismatch")
                append_error(errors, bundle_payload.get("hardware_actions_executed") is False, "PS offline bundle incorrectly claims hardware actions")
                append_error(errors, bundle_payload.get("atomic_files") is True, "PS bundle does not require atomic files")
                errors.extend(verify_embedded_file_records(bundle_payload, document=bundle_path, repo_root=evidence.repo_root, prefix="PS bundle"))
        events_path = candidate.path.parent / "p7_ps_application_events.json"
        append_error(errors, events_path.is_file(), "PS authorized event log missing")
        if events_path.is_file():
            try:
                events_payload = json.loads(events_path.read_text(encoding="utf-8", errors="strict"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"PS authorized event log invalid: {exc}")
            else:
                event_names = [item.get("event") for item in events_payload.get("events", []) if isinstance(item, dict)] if isinstance(events_payload, dict) else []
                append_error(errors, "authorized_execution_begin" in event_names and "authorized_execution_end" in event_names, "PS authorized event log is incomplete")
    else:
        preflight = data.get("preflight_process")
        stage_process = data.get("stage_process")
        raw_path = candidate.path.parent / "p7_jtag_axi_raw_result.txt"
        append_error(errors, data.get("programmed_candidate") is True, "JTAG candidate was not programmed")
    errors.extend(authorized_event_errors(candidate, evidence))
    errors.extend(process_record_errors(preflight, "preflight", document=candidate.path, repo_root=evidence.repo_root))
    errors.extend(process_record_errors(stage_process, "hardware stage", document=candidate.path, repo_root=evidence.repo_root))
    if isinstance(stage_process, dict):
        append_error(errors, stage_process.get("passed") is True, "hardware stage process passed is not true")
        recorded_result = resolve_reference(stage_process.get("result_file"), document=candidate.path, repo_root=evidence.repo_root)
        if recorded_result is not None:
            append_error(errors, recorded_result == raw_path.resolve(strict=False), "raw result path is not the canonical run-local file")
    append_error(errors, raw_path.is_file(), "canonical raw hardware result log is missing")
    observed_raw_markers, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates, f"canonical raw hardware result contains duplicate markers: {sorted(set(raw_duplicates))}")
    summarized_markers = data.get("stage_result_markers")
    if summarized_markers is not None:
        append_error(errors, isinstance(summarized_markers, dict), "stage_result_markers is malformed")
        if isinstance(summarized_markers, dict):
            normalized_summary_markers = {str(key): str(value) for key, value in summarized_markers.items()}
            append_error(errors, normalized_summary_markers == observed_raw_markers, "stage_result_markers do not exactly match the canonical raw result")
    if candidate.kind == "ps":
        append_error(errors, observed_raw_markers.get("P7_PS_STAGE_RESULT") == "PASS", "raw PS PASS marker missing")
        append_error(errors, observed_raw_markers.get("P7_PS_MODE") == str(data.get("mode")), "raw PS mode marker mismatch")
        append_error(errors, observed_raw_markers.get("P7_PS_ELF_DOWNLOADED") == "1", "raw PS ELF marker missing")
    else:
        append_error(errors, observed_raw_markers.get("P7_JTAG_STAGE_RESULT") == "PASS", "raw JTAG PASS marker missing")
        append_error(errors, observed_raw_markers.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS", "raw JTAG transaction PASS marker missing")

    errors.extend(shutdown_errors(candidate, "before"))
    errors.extend(shutdown_errors(candidate, "after"))
    for which in ("before", "after"):
        block = data.get(f"shutdown_{which}")
        provenance[f"shutdown_{which}"] = {
            "returncode": block.get("returncode") if isinstance(block, dict) else None,
            "passed": block.get("passed") if isinstance(block, dict) else None,
            "result_file": block.get("result_file") if isinstance(block, dict) else None,
        }
    provenance["SHUTDOWN_EXIT"] = 0 if all(
        isinstance(data.get(f"shutdown_{which}"), dict)
        and data[f"shutdown_{which}"].get("returncode") == 0
        and data[f"shutdown_{which}"].get("passed") is True
        for which in ("before", "after")
    ) else None
    provenance["output_file_hashes"] = candidate_output_hash_records(candidate)
    return errors, provenance


def choose_latest(candidates: Sequence[Candidate]) -> Candidate | None:
    executed = [item for item in candidates if item.executed]
    pool = executed or list(candidates)
    return max(pool, key=lambda item: (item.timestamp, str(item.path))) if pool else None


def skip_for_stage(evidence: RepositoryEvidence, stage: str) -> StageResult | None:
    matches = [(path, data) for path, data in evidence.skip_records if str(data.get("stage", "")) == stage]
    if not matches:
        return None
    path, data = max(matches, key=lambda item: item[0].stat().st_mtime)
    reason = str(data.get("reason", "")).strip()
    if not reason:
        return StageResult(stage, "FAIL", "malformed SKIP_WITH_REASON record", [rel(path, evidence.repo_root)], errors=["skip reason is empty"])
    if data.get("hardware_actions_executed") is not False:
        return StageResult(stage, "FAIL", "malformed SKIP_WITH_REASON record", [rel(path, evidence.repo_root)], errors=["skip record claims hardware actions"])
    return StageResult(stage, "SKIP_WITH_REASON", reason, [rel(path, evidence.repo_root)])


def missing_stage(evidence: RepositoryEvidence, stage: str, reason: str) -> StageResult:
    skip = skip_for_stage(evidence, stage)
    return skip or StageResult(stage, "PENDING_HW", reason)


def markers(candidate: Candidate) -> dict[str, str]:
    result, _duplicates = raw_markers(candidate)
    return result


def integer_marker(sources: Sequence[Mapping[str, Any]], names: Sequence[str]) -> int | None:
    for source in sources:
        for name in names:
            value = source.get(name)
            if value is None:
                continue
            try:
                return int(str(value), 0)
            except ValueError:
                continue
    return None


def validate_safe_idle(candidate: Candidate, evidence: RepositoryEvidence) -> StageResult:
    errors, provenance = common_runner_errors(candidate, evidence)
    observed = markers(candidate)
    append_error(errors, candidate.kind == "jtag", "safe-idle evidence is not a direct JTAG safe-wrapper run")
    append_error(errors, candidate.data.get("semantic_mode") == "safe-idle", "safe-idle wrapper semantic_mode is not exact safe-idle")
    append_error(errors, candidate.data.get("drove_tfdu_txd") is False, "safe-idle wrapper does not prove drove_tfdu_txd=false")
    append_error(errors, candidate.data.get("enabled_tfdu_receiver") is False, "safe-idle wrapper does not prove enabled_tfdu_receiver=false")
    append_error(errors, candidate.data.get("uart_access") is False, "safe-idle wrapper does not prove uart_access=false")
    transaction = candidate.data.get("transaction_validation")
    if not isinstance(transaction, dict):
        errors.append("safe-idle transaction validation record missing")
        transaction = {}
    metadata = transaction.get("metadata")
    append_error(errors, isinstance(metadata, dict) and str(metadata.get("EVIDENCE_KIND", "")).casefold() == "safe_idle", "safe-idle transaction EVIDENCE_KIND mismatch")
    for key in ("start_operation_count", "commit_operation_count", "payload_write_count"):
        append_error(errors, int(transaction.get(key, -1)) == 0, f"safe-idle transaction {key} is not zero")
    append_error(errors, transaction.get("write_operations") == [{"offset": "0x100", "value": "0x00000030"}], "safe-idle transaction writes more than final STOP|SHUTDOWN")
    result_keys = set(str(key) for key in transaction.get("result_keys", []))
    append_error(errors, SAFE_IDLE_REQUIRED_KEYS <= result_keys, "safe-idle transaction does not read/assert every required status/counter")
    backend = candidate.data.get("backend_parse")
    parse_path: Path | None = None
    if not isinstance(backend, dict):
        errors.append("safe-idle strict parser binding missing")
        backend = {}
    else:
        append_error(errors, backend.get("passed") is True, "safe-idle strict parser binding is not PASS")
        append_error(errors, backend.get("semantic_mode") == "safe-idle", "safe-idle parser semantic mode mismatch")
        append_error(errors, backend.get("raw_log_bound_to_this_hardware_process") is True, "safe-idle parser is not bound to this raw hardware log")
        parse_path = resolve_reference(backend.get("summary_file"), document=candidate.path, repo_root=evidence.repo_root)
        append_error(errors, parse_path is not None and parse_path.is_file(), "safe-idle parser summary missing")
        if parse_path is not None and parse_path.is_file():
            append_error(errors, sha256_file(parse_path) == str(backend.get("summary_sha256", "")).lower(), "safe-idle parser summary SHA256 mismatch")
    parsed: dict[str, Any] = {}
    if parse_path is not None and parse_path.is_file():
        try:
            value = json.loads(parse_path.read_text(encoding="utf-8", errors="strict"))
            parsed = value if isinstance(value, dict) else {}
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"safe-idle parser summary invalid: {exc}")
    append_error(errors, parsed.get("P7_SAFE_IDLE_PARSE") == "PASS" and parsed.get("failures") == [], "safe-idle strict parser is not clean PASS")
    append_error(errors, parsed.get("semantic_mode") == "safe-idle", "safe-idle strict parser semantic mode mismatch")
    append_error(errors, parsed.get("drove_tfdu_txd") is False and parsed.get("enabled_tfdu_receiver") is False, "safe-idle parser does not prove non-transmission/receiver shutdown")
    required_values = parsed.get("required_values")
    append_error(errors, isinstance(required_values, dict) and set(required_values) == SAFE_IDLE_REQUIRED_KEYS, "safe-idle parser required-value set mismatch")
    if isinstance(required_values, dict):
        for key in SAFE_IDLE_REQUIRED_KEYS:
            raw_value = observed.get(key)
            try:
                parsed_value = int(str(required_values.get(key, "")), 0)
                observed_value = int(str(raw_value), 0)
            except ValueError:
                parsed_value = observed_value = -1
            append_error(errors, parsed_value == observed_value, f"safe-idle parser/raw marker mismatch: {key}")
            if key == "SAFE_STATUS":
                append_error(errors, parsed_value >= 0 and parsed_value & 0xE8 == 0, "safe-idle status has BUSY/FAIL/CONFIG_ERROR/TIMEOUT bits")
            else:
                append_error(errors, parsed_value == 0, f"safe-idle counter/error is nonzero: {key}")
    evidence.provenance_rows.append(provenance)
    return StageResult(
        "safe_idle",
        "PASS" if not errors else "FAIL",
        "fresh safe-idle readback and both shutdown barriers passed" if not errors else "safe-idle evidence failed closed",
        [rel(candidate.path, evidence.repo_root)],
        checks={"non_transmitting_semantic_mode": not errors, "shutdown_before_after": not shutdown_errors(candidate, "before") and not shutdown_errors(candidate, "after")},
        errors=errors,
    )


def validate_p6_regression(candidate: Candidate, evidence: RepositoryEvidence) -> StageResult:
    errors, provenance = common_runner_errors(candidate, evidence)
    observed = markers(candidate)
    metadata = candidate.data.get("transaction_validation", {}).get("metadata", {})
    sources = [observed, metadata if isinstance(metadata, dict) else {}]
    append_error(errors, str(observed.get("P7_P6_FRAME_REGRESSION", "")).upper() == "PASS", "P6 frame regression semantic PASS marker missing")
    counts = {}
    for label, aliases in {
        "lane0": ("P7_P6_LANE0_FRAMES", "LANE0_FRAMES"),
        "lane1": ("P7_P6_LANE1_FRAMES", "LANE1_FRAMES"),
        "mask3": ("P7_P6_MASK3_FRAMES", "MASK3_FRAMES"),
    }.items():
        counts[label] = integer_marker(sources, aliases)
        append_error(errors, counts[label] is not None and counts[label] >= 10, f"P6 {label} frame count is below 10/missing")
    for key in ("CRC_BAD", "PAYLOAD_MISMATCH", "RETRY_EXHAUSTED", "TX_FAIL", "DUTY_VIOLATION"):
        value = integer_marker(sources, (f"P7_P6_{key}", key))
        append_error(errors, value == 0, f"P6 regression {key} is missing/nonzero")
    max_high = integer_marker(sources, ("P7_P6_MAX_TXD_HIGH_CYCLES", "MAX_TXD_HIGH_CYCLES"))
    append_error(errors, max_high is not None and 0 < max_high <= 8, "P6 regression max TXD-high cycles is outside 1..8")
    evidence.provenance_rows.append(provenance)
    return StageResult(
        "p6_frame_regression",
        "PASS" if not errors else "FAIL",
        "lane masks 0x1/0x2/0x3 each passed at least ten P6 frames" if not errors else "P6 frame regression evidence failed closed",
        [rel(candidate.path, evidence.repo_root)],
        metrics={"frame_counts": counts, "max_txd_high_cycles": max_high},
        errors=errors,
    )


def validate_p6_regression_candidates(candidates: Sequence[Candidate], evidence: RepositoryEvidence) -> StageResult:
    """Accept either a dedicated semantic run or three strict backend-bound P6 masks."""
    latest_by_key: dict[str, Candidate] = {}
    for candidate in candidates:
        for key in _candidate_attempted_coverage(candidate, evidence):
            previous = latest_by_key.get(key)
            if previous is None or candidate.timestamp > previous.timestamp:
                latest_by_key[key] = candidate
    coverage_to_policy = {
        "p6_lane0": "LANE0_ONLY",
        "p6_lane1": "LANE1_ONLY",
        "p6_mask3": "REPLICATE_0X3",
    }
    selected_candidates = {item.path: item for item in latest_by_key.values()}
    if len(selected_candidates) == 1 and set(latest_by_key) == set(coverage_to_policy):
        only = next(iter(selected_candidates.values()))
        if not isinstance(only.data.get("backend_parse"), dict):
            result = validate_p6_regression(only, evidence)
            result.notes.append(f"preserved superseded P6 regression attempts: {max(0, len(candidates) - 1)}")
            return result
    errors: list[str] = []
    sources: list[str] = []
    counts: dict[str, int] = {}
    for coverage, policy in coverage_to_policy.items():
        candidate = latest_by_key.get(coverage)
        if candidate is None:
            errors.append(f"P6 regression backend run missing for {policy}")
            continue
        common, provenance = common_runner_errors(candidate, evidence)
        linked, parse_path, link_errors = linked_backend_parse(candidate, evidence)
        errors.extend(f"{policy}: {item}" for item in common + link_errors)
        evidence.provenance_rows.append(provenance)
        sources.append(rel(candidate.path, evidence.repo_root))
        if parse_path is not None:
            sources.append(rel(parse_path, evidence.repo_root))
        parsed = linked.get("parse", {}) if isinstance(linked, dict) else {}
        count = int(parsed.get("fragment_count", -1))
        counts[policy] = count
        append_error(errors, count >= 10, f"P6 regression {policy} has fewer than ten parsed frames")
        fragments = parsed.get("fragments", [])
        append_error(errors, isinstance(fragments, list) and len(fragments) == count, f"P6 regression {policy} fragment ledger count mismatch")
        if isinstance(fragments, list):
            for index, fragment in enumerate(fragments):
                if not isinstance(fragment, dict):
                    errors.append(f"P6 regression {policy} fragment {index} is malformed")
                    continue
                append_error(errors, 0 < int(fragment.get("txd_high_max_cycles", 0)) <= 8, f"P6 regression {policy} fragment {index} TXD-high limit invalid")
    return StageResult(
        "p6_frame_regression",
        "PASS" if not errors else "FAIL",
        "strict raw-log-bound backend parses prove at least ten P6 frames on masks 0x1/0x2/0x3" if not errors else "P6 frame regression evidence failed closed",
        sorted(set(sources)),
        metrics={"frame_counts": counts},
        errors=errors,
        notes=[f"preserved superseded P6 regression attempts: {max(0, len(candidates) - len(selected_candidates))}"],
    )


def expected_lane_distribution(
    policy: int,
    fragment_count: int,
    unavailable_lane_mask: int,
    unavailable_after_fragment: int,
) -> tuple[int, int, int] | None:
    lane0 = lane1 = replicated = 0
    for fragment_index in range(fragment_count):
        unavailable = unavailable_lane_mask if fragment_index >= unavailable_after_fragment else 0
        preferred = 1 if policy == 1 else 2 if policy == 2 else (1 if fragment_index % 2 == 0 else 2) if policy == 3 else 3 if policy == 4 else 0
        lane = preferred & ~unavailable & 0x3
        if lane == 0 and preferred == 1 and not unavailable & 2:
            lane = 2
        elif lane == 0 and preferred == 2 and not unavailable & 1:
            lane = 1
        if lane == 0:
            return None
        lane0 += int(bool(lane & 1))
        lane1 += int(bool(lane & 2))
        replicated += int(lane == 3)
    return lane0, lane1, replicated


def case_output_errors(
    candidate: Candidate,
    case: Mapping[str, Any],
    prefix: str = "",
    *,
    expected_status: int = 3,
    expected_error: int = 0,
    require_zero_transport: bool = False,
) -> list[str]:
    errors: list[str] = []
    descriptor = case.get("descriptor")
    if not isinstance(descriptor, dict):
        return [f"{prefix} descriptor record missing"]
    append_error(errors, case.get("passed") is True, f"{prefix} case is not PASS")
    append_error(errors, case.get("failures") == [], f"{prefix} case failures are nonempty")
    required_fields = (
        "status", "error_code", "object_length", "bytes_completed", "fragments_total",
        "fragments_completed", "fragment_attempts", "fallback_count", "expected_crc32",
        "output_crc32", "expected_sha256", "input_sha256", "output_sha256",
        "p6_retry_count", "p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad",
        "p6_payload_mismatch", "max_txd_high_cycles", "duty_violation_count",
        "lane_policy", "unavailable_lane_mask", "unavailable_after_fragment",
        "lane0_fragments", "lane1_fragments", "replicated_fragments",
        "start_ticks", "end_ticks", "completion_sequence",
    )
    for key in required_fields:
        append_error(errors, key in descriptor, f"{prefix} descriptor field missing: {key}")

    def value(key: str, default: int = -1) -> int:
        try:
            return int(descriptor.get(key, default))
        except (TypeError, ValueError):
            errors.append(f"{prefix} descriptor field is not an integer: {key}")
            return default

    object_length = value("object_length")
    try:
        output_bytes = int(case.get("output_bytes", -1))
    except (TypeError, ValueError):
        output_bytes = -1
    append_error(errors, output_bytes == object_length, f"{prefix} output/input length mismatch")
    append_error(errors, value("status") == expected_status, f"{prefix} terminal status mismatch")
    append_error(errors, value("error_code") == expected_error, f"{prefix} terminal error code mismatch")
    expected_sha = str(descriptor.get("expected_sha256", "")).lower()
    input_sha = str(descriptor.get("input_sha256", "")).lower()
    descriptor_output_sha = str(descriptor.get("output_sha256", "")).lower()
    output_sha = str(case.get("output_sha256", "")).lower()
    append_error(errors, bool(SHA256_RE.fullmatch(expected_sha)), f"{prefix} expected SHA256 missing")
    append_error(errors, input_sha == expected_sha, f"{prefix} input SHA256 does not match expected identity")
    append_error(errors, SHA256_RE.fullmatch(output_sha) is not None, f"{prefix} host output SHA256 missing/malformed")
    expected_crc = descriptor.get("expected_crc32")
    fragments_total = value("fragments_total")
    append_error(errors, fragments_total == max(1, (max(object_length, 0) + 214) // 215), f"{prefix} fragment geometry mismatch")
    if expected_status == 3:
        append_error(errors, value("bytes_completed") == object_length, f"{prefix} completed-byte count mismatch")
        append_error(errors, value("fragments_completed") == fragments_total, f"{prefix} completed-fragment count mismatch")
        append_error(errors, value("fragment_attempts") == fragments_total, f"{prefix} fragment attempt count is not exactly one submission per fragment")
        append_error(errors, descriptor_output_sha == expected_sha == output_sha, f"{prefix} input/output SHA256 mismatch")
        append_error(errors, isinstance(expected_crc, int) and value("output_crc32") == expected_crc, f"{prefix} input/output CRC32 mismatch")
        append_error(errors, value("completion_sequence") > 0, f"{prefix} completion sequence missing")
        append_error(errors, 0 <= value("start_ticks") < value("end_ticks"), f"{prefix} object processing interval invalid")
        expected_lanes = expected_lane_distribution(
            value("lane_policy"), fragments_total, value("unavailable_lane_mask", 0), value("unavailable_after_fragment", 0)
        )
        observed_lanes = (value("lane0_fragments"), value("lane1_fragments"), value("replicated_fragments"))
        append_error(errors, expected_lanes is not None and observed_lanes == expected_lanes, f"{prefix} lane distribution mismatch")
    else:
        append_error(errors, value("bytes_completed") == 0, f"{prefix} negative case retained partial bytes")
        append_error(errors, descriptor_output_sha == output_sha, f"{prefix} negative-case descriptor/host output SHA256 mismatch")
        if require_zero_transport:
            append_error(errors, value("fragments_completed") == 0 and value("fragment_attempts") == 0, f"{prefix} rejected/strict-negative case attempted transport")
    append_error(errors, value("p6_retry_count", -1) >= 0, f"{prefix} P6 retry count missing/negative")
    for key, label in (
        ("p6_retry_exhausted", "P6 retry exhausted"),
        ("p6_tx_fail", "P6 TX fail"),
        ("p6_crc_bad", "P6 CRC bad"),
        ("p6_payload_mismatch", "P6 payload mismatch"),
        ("duty_violation_count", "duty violation"),
    ):
        append_error(errors, value(key) == 0, f"{prefix} {label}")
    append_error(errors, 0 <= value("max_txd_high_cycles") <= 8, f"{prefix} TXD-high limit exceeded/missing")
    return errors


def require_ps_postprocess(candidate: Candidate) -> tuple[list[str], dict[str, Any]]:
    post = candidate.data.get("postprocess")
    if not isinstance(post, dict):
        return ["PS postprocess record missing"], {}
    errors: list[str] = []
    append_error(errors, post.get("passed") is True, "PS postprocess is not PASS")
    append_error(errors, post.get("failures") == [], "PS postprocess failures are nonempty")
    mailbox = post.get("mailbox")
    if not isinstance(mailbox, dict):
        errors.append("PS final mailbox record missing")
    else:
        append_error(errors, int(mailbox.get("shutdown_result", -1)) == 0, "PS mailbox shutdown_result is nonzero/missing")
        append_error(errors, int(mailbox.get("service_state", -1)) == 4, "PS mailbox service state is not SHUTDOWN")
    return errors, post


def validate_ps_functional(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[StageResult, StageResult]:
    errors, provenance = common_runner_errors(candidate, evidence)
    post_errors, post = require_ps_postprocess(candidate)
    errors.extend(post_errors)
    cases = post.get("cases", []) if isinstance(post, dict) else []
    boundary = post.get("boundary_cases", []) if isinstance(post, dict) else []
    runtime_errors = list(errors)
    required_large = {
        "1m_lane0": (1_048_576, 1),
        "1m_lane1": (1_048_576, 2),
        "1m_stripe": (1_048_576, 3),
        "1m_replicate": (1_048_576, 4),
        "64k_counter_stripe": (65_536, 3),
        "64k_prbs15_stripe": (65_536, 3),
        "64k_random_stripe": (65_536, 3),
        "64k_all_bytes_stripe": (65_536, 3),
    }
    valid_cases = [case for case in cases if isinstance(case, dict)] if isinstance(cases, list) else []
    observed_names = [str(case.get("name", "")) for case in valid_cases]
    append_error(runtime_errors, len(valid_cases) == len(cases) == 8, "PS functional matrix must contain exactly eight case objects")
    append_error(runtime_errors, set(observed_names) == set(required_large) and len(set(observed_names)) == 8, "PS functional large-object/pattern matrix is incomplete/duplicated")
    slots = [case.get("slot") for case in valid_cases]
    append_error(runtime_errors, sorted(slots) == list(range(8)), "PS functional case slots are not exactly 0..7")
    for case in cases:
        if isinstance(case, dict):
            expected_geometry = required_large.get(str(case.get("name", "")))
            descriptor = case.get("descriptor", {})
            if expected_geometry is not None and isinstance(descriptor, dict):
                append_error(runtime_errors, (int(descriptor.get("object_length", -1)), int(descriptor.get("lane_policy", -1))) == expected_geometry, f"functional:{case.get('name', '?')}: name/geometry mismatch")
            runtime_errors.extend(case_output_errors(candidate, case, f"functional:{case.get('name', '?')}:"))
    checkpoint = post.get("functional_checkpoint") if isinstance(post, dict) else None
    if not isinstance(checkpoint, dict):
        runtime_errors.append("PS functional 4 KiB stripe checkpoint record missing")
    else:
        checkpoint_descriptor = checkpoint.get("descriptor", {})
        append_error(runtime_errors, int(checkpoint_descriptor.get("object_length", -1)) == 4_096, "PS functional checkpoint is not 4 KiB")
        append_error(runtime_errors, int(checkpoint_descriptor.get("lane_policy", -1)) == 3, "PS functional 4 KiB checkpoint is not stripe")
        runtime_errors.extend(case_output_errors(candidate, checkpoint, "functional:4k-checkpoint:"))
    boundary_errors = list(errors)
    boundary_pairs: set[tuple[int, int]] = set()
    for case in boundary:
        if not isinstance(case, dict):
            boundary_errors.append("boundary case is not an object")
            continue
        descriptor = case.get("descriptor", {})
        try:
            length = int(case.get("length", descriptor.get("object_length", -1)))
            policy = int(descriptor.get("lane_policy", -1))
        except (TypeError, ValueError):
            length, policy = -1, -1
        boundary_pairs.add((length, policy))
        boundary_errors.extend(case_output_errors(candidate, case, f"boundary:{length}:{policy}:"))
    expected_pairs = {(length, policy) for length in REQUIRED_BOUNDARY_LENGTHS for policy in REQUIRED_BOUNDARY_POLICIES}
    append_error(boundary_errors, isinstance(boundary, list) and len(boundary) == len(expected_pairs), "hardware boundary matrix case count is not exactly 48")
    append_error(boundary_errors, boundary_pairs == expected_pairs, "hardware boundary matrix does not exactly cover every required length x lane policy")
    evidence.provenance_rows.append(provenance)
    source = [rel(candidate.path, evidence.repo_root)]
    runtime = StageResult(
        "ps_runtime",
        "PASS" if not runtime_errors else "FAIL",
        "real PS ELF completed the full large-object policy/pattern matrix" if not runtime_errors else "real PS runtime evidence failed closed",
        source,
        metrics={"functional_cases": len(cases), "functional_4k_checkpoint": isinstance(checkpoint, dict) and checkpoint.get("passed") is True},
        errors=runtime_errors,
    )
    fragment = StageResult(
        "fragment_boundary",
        "PASS" if not boundary_errors else "FAIL",
        "all required boundary lengths passed on lane0/lane1/stripe/replicate" if not boundary_errors else "fragment boundary evidence failed closed",
        source,
        metrics={"observed_length_policy_pairs": len(boundary_pairs), "required_pairs": len(expected_pairs)},
        errors=boundary_errors,
    )
    return runtime, fragment


def validate_ps_mode(candidate: Candidate, evidence: RepositoryEvidence, stage: str) -> StageResult:
    errors, provenance = common_runner_errors(candidate, evidence)
    post_errors, post = require_ps_postprocess(candidate)
    errors.extend(post_errors)
    cases = post.get("cases", []) if isinstance(post, dict) else []
    append_error(errors, isinstance(cases, list) and all(isinstance(case, dict) for case in cases), f"{stage} case list contains malformed records")
    names = {str(item.get("name", "")) for item in cases if isinstance(item, dict)}
    mailbox = post.get("mailbox", {}) if isinstance(post, dict) else {}
    if stage == "lane_fallback":
        required = {
            "stripe_lane0_to_lane1",
            "stripe_lane1_to_lane0",
            "replicate_lane0_unavailable",
            "replicate_lane1_unavailable",
            "strict_lane0_unavailable",
            "strict_lane1_unavailable",
            "stripe_both_unavailable",
        }
        fallback_geometry = {
            "stripe_lane0_to_lane1": (3, 1, 2),
            "stripe_lane1_to_lane0": (3, 2, 2),
            "replicate_lane0_unavailable": (4, 1, 0),
            "replicate_lane1_unavailable": (4, 2, 0),
            "strict_lane0_unavailable": (1, 1, 0),
            "strict_lane1_unavailable": (2, 2, 0),
            "stripe_both_unavailable": (3, 3, 0),
        }
        append_error(errors, len(cases) == len(required) and names == required, "lane fallback positive/strict-negative matrix incomplete/duplicated")
        observed_markers = markers(candidate)
        append_error(errors, observed_markers.get("P7_FAULT_MODEL") == "SOFTWARE_INJECTED_SCHEDULER_FAULT", "fallback evidence is not labeled software-injected")
        for item in cases:
            if not isinstance(item, dict):
                continue
            descriptor = item.get("descriptor", {})
            name = str(item.get("name", ""))
            expected_geometry = fallback_geometry.get(name)
            append_error(
                errors,
                expected_geometry is not None
                and int(descriptor.get("object_length", -1)) == 65_536
                and (
                    int(descriptor.get("lane_policy", -1)),
                    int(descriptor.get("unavailable_lane_mask", -1)),
                    int(descriptor.get("unavailable_after_fragment", -1)),
                ) == expected_geometry,
                f"{name} fault/fallback geometry mismatch",
            )
            positive = name.startswith(("stripe_lane", "replicate_lane"))
            errors.extend(
                case_output_errors(
                    candidate,
                    item,
                    f"{stage}:{name}:",
                    expected_status=3 if positive else 4,
                    expected_error=0 if positive else 8,
                    require_zero_transport=not positive,
                )
            )
            if positive:
                append_error(errors, int(descriptor.get("fallback_count", 0)) >= 1, f"{name} did not count fallback")
            if name.startswith("strict_") or name == "stripe_both_unavailable":
                append_error(errors, int(descriptor.get("bytes_completed", 0)) == 0, f"{name} committed partial bytes")
                append_error(errors, int(descriptor.get("fragment_attempts", 0)) == 0, f"{name} attempted transport/TX")
    elif stage == "abort_restart":
        contracts = {
            "abort_mid_object": (5, 15, False),
            "restart_new_epoch": (3, 0, False),
            "duplicate_replay_rejected": (6, 19, True),
        }
        append_error(errors, len(cases) == 3 and names == set(contracts), "abort/restart matrix incomplete/duplicated")
        for item in cases:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", ""))
            contract = contracts.get(name)
            if contract is not None:
                errors.extend(case_output_errors(candidate, item, f"{stage}:{name}:", expected_status=contract[0], expected_error=contract[1], require_zero_transport=contract[2]))
        by_name = {str(item.get("name", "")): item.get("descriptor", {}) for item in cases if isinstance(item, dict)}
        abort_descriptor = by_name.get("abort_mid_object", {})
        restart_descriptor = by_name.get("restart_new_epoch", {})
        replay_descriptor = by_name.get("duplicate_replay_rejected", {})
        append_error(
            errors,
            [int(by_name.get(name, {}).get("completion_sequence", -1)) for name in ("abort_mid_object", "restart_new_epoch", "duplicate_replay_rejected")] == [1, 1, 2],
            "abort/restart completion ordering is not exactly [1,1,2]",
        )
        append_error(errors, int(restart_descriptor.get("session_epoch", -1)) > int(abort_descriptor.get("session_epoch", -1)), "abort/restart did not advance session epoch")
        append_error(
            errors,
            (int(replay_descriptor.get("session_epoch", -1)), int(replay_descriptor.get("object_id", -1)))
            == (int(restart_descriptor.get("session_epoch", -2)), int(restart_descriptor.get("object_id", -2))),
            "duplicate replay does not bind the restarted object identity",
        )
        observed_markers = markers(candidate)
        for marker in ("P7_ABORT_RESTART_NEW_EPOCH", "P7_ABORT_RESTART_REPLAY_REJECTED", "P7_ABORT_INTERPHASE_SHUTDOWN_PROGRAMMED", "P7_ABORT_RESTART_CANDIDATE_REPROGRAMMED"):
            append_error(errors, observed_markers.get(marker) == "1", f"abort/restart raw marker missing: {marker}=1")
    elif stage == "queue_backpressure":
        valid_cases = [item for item in cases if isinstance(item, dict)]
        expected_names = {f"queue_{index}" for index in range(8)}
        append_error(errors, len(valid_cases) == len(cases) == 8, "queue max-depth cases are not exactly eight objects")
        append_error(errors, {str(item.get("name", "")) for item in valid_cases} == expected_names, "queue names are incomplete/duplicated")
        append_error(errors, sorted(int(item.get("slot", -1)) for item in valid_cases) == list(range(8)), "queue slots are not exactly 0..7")
        identities = [(int(item.get("descriptor", {}).get("session_epoch", -1)), int(item.get("descriptor", {}).get("object_id", -1))) for item in valid_cases]
        append_error(errors, len(set(identities)) == 8, "queue descriptor identities are not unique")
        completion_sequences = [int(item.get("descriptor", {}).get("completion_sequence", -1)) for item in sorted(valid_cases, key=lambda value: int(value.get("slot", -1)))]
        append_error(errors, completion_sequences == list(range(1, 9)), "queue completion sequence does not prove FIFO order 1..8")
        for item in valid_cases:
            slot = int(item.get("slot", -1))
            descriptor = item.get("descriptor", {})
            append_error(errors, int(descriptor.get("object_id", -1)) == slot + 1, f"queue slot {slot} object identity mismatch")
            errors.extend(case_output_errors(candidate, item, f"{stage}:queue_{slot}:"))
        append_error(errors, int(mailbox.get("queue_high_watermark", -1)) == 8, "queue high-water mark is not 8")
        append_error(errors, int(mailbox.get("backpressure_events", 0)) >= 1, "queue backpressure was not observed")
        append_error(errors, int(mailbox.get("abort_count", 0)) >= 1, "ABORT while queued was not observed")
        observed_markers = markers(candidate)
        for marker in (
            "P7_QUEUE_DEPTH1_COMPLETE", "P7_QUEUE_FULL_BEFORE_RUN", "P7_QUEUE_STOP_WHILE_QUEUED",
            "P7_QUEUE_OVERFLOW_REJECTED_BEFORE_DDR_WRITE", "P7_QUEUE_PRODUCER_FASTER_THAN_CONSUMER",
            "P7_QUEUE_MAX_FIFO_COMPLETE", "P7_QUEUE_ABORT_WHILE_QUEUED",
            "P7_QUEUE_INTERPHASE_SHUTDOWN_1_PROGRAMMED", "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_1",
            "P7_QUEUE_INTERPHASE_SHUTDOWN_2_PROGRAMMED", "P7_QUEUE_INTERPHASE_CANDIDATE_REPROGRAM_2",
        ):
            append_error(errors, observed_markers.get(marker) == "1", f"queue raw marker missing: {marker}=1")
        for marker, expected in {
            "P7_QUEUE_INTERPHASE_SHUTDOWN_COUNT": "2",
            "P7_QUEUE_OVERFLOW_ADMISSION": "FULL",
            "P7_QUEUE_OVERFLOW_OCCUPANCY": "8",
            "P7_QUEUE_OVERFLOW_CAPACITY": "8",
            "P7_QUEUE_OVERFLOW_DDR_WRITE": "0",
            "P7_QUEUE_OVERFLOW_DDR_WRITE_COUNT": "0",
            "P7_QUEUE_OVERFLOW_CANDIDATE_OBJECT_ID": "9",
        }.items():
            append_error(errors, observed_markers.get(marker) == expected, f"queue raw marker mismatch: {marker}")
    evidence.provenance_rows.append(provenance)
    reason = {
        "lane_fallback": "software-injected scheduler fallback and strict-negative cases passed",
        "abort_restart": "abort, shutdown, new-epoch restart, atomicity, and replay rejection passed",
        "queue_backpressure": "depth-1/depth-8/FIFO/overflow/STOP/ABORT queue cases passed",
    }[stage]
    return StageResult(stage, "PASS" if not errors else "FAIL", reason if not errors else f"{stage} evidence failed closed", [rel(candidate.path, evidence.repo_root)], metrics={"case_count": len(cases)}, errors=errors, notes=["lane fault evidence is software scheduler injection, not a physical optical fault"] if stage == "lane_fallback" else [])


def pattern_from_manifest(manifest: Mapping[str, Any], stage_name: str) -> str:
    explicit = str(manifest.get("payload_pattern", manifest.get("pattern", ""))).casefold()
    aliases = {
        "random": "deterministic_random",
        "deterministic_random": "deterministic_random",
        "counter": "counter",
        "prbs15": "prbs15",
        "all_bytes": "binary_all_byte_values_repeated",
        "binary_all_byte_values_repeated": "binary_all_byte_values_repeated",
    }
    if explicit in aliases:
        return aliases[explicit]
    name = stage_name.casefold()
    for needle in ("binary_all_byte_values_repeated", "all_bytes", "deterministic_random", "random", "prbs15", "counter"):
        if needle in name:
            return aliases[needle]
    return "unknown"


def intended_jtag_tuple(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[int, str, str] | None:
    backend = candidate.data.get("backend_parse")
    transaction = candidate.data.get("transaction_validation")
    backend_details = transaction.get("backend_manifest", {}) if isinstance(transaction, dict) else {}
    length_value: Any = backend.get("object_length") if isinstance(backend, dict) else None
    policy_value: Any = backend.get("lane_policy") if isinstance(backend, dict) else None
    if length_value is None and isinstance(backend_details, dict):
        length_value = backend_details.get("input_length")
    if not policy_value and isinstance(backend_details, dict):
        policy_value = backend_details.get("lane_policy")
    manifest: dict[str, Any] = {}
    if isinstance(backend, dict):
        parse_path = resolve_reference(backend.get("summary_file"), document=candidate.path, repo_root=evidence.repo_root)
        if parse_path is not None and parse_path.is_file():
            try:
                parsed = json.loads(parse_path.read_text(encoding="utf-8", errors="strict"))
                if length_value is None:
                    length_value = parsed.get("object_length")
                if not policy_value:
                    policy_value = parsed.get("lane_policy")
                manifest_path = resolve_reference(parsed.get("manifest"), document=parse_path, repo_root=evidence.repo_root)
                if manifest_path is not None and manifest_path.is_file():
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                pass
    stage_name = str(candidate.data.get("stage_name", ""))
    if length_value is None:
        for length in (1_048_576, 65_536, 4_096):
            if str(length) in stage_name or (length == 1_048_576 and "1m" in stage_name.casefold()) or (length == 65_536 and "64k" in stage_name.casefold()) or (length == 4_096 and "4k" in stage_name.casefold()):
                length_value = length
                break
    if not policy_value:
        folded = stage_name.casefold()
        if "lane0" in folded:
            policy_value = "LANE0_ONLY"
        elif "lane1" in folded:
            policy_value = "LANE1_ONLY"
        elif "replicate" in folded:
            policy_value = "REPLICATE_0X3"
        elif "stripe" in folded:
            policy_value = "STRIPE_ROUND_ROBIN"
    try:
        length = int(length_value)
    except (TypeError, ValueError):
        return None
    policy = str(policy_value or "")
    pattern = pattern_from_manifest(manifest, stage_name)
    return (length, policy, pattern) if policy and pattern != "unknown" else None


def intended_boundary_pair(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[int, str] | None:
    backend = candidate.data.get("backend_parse")
    transaction = candidate.data.get("transaction_validation")
    details = transaction.get("backend_manifest", {}) if isinstance(transaction, dict) else {}
    length_value: Any = backend.get("object_length") if isinstance(backend, dict) else None
    policy_value: Any = backend.get("lane_policy") if isinstance(backend, dict) else None
    if length_value is None and isinstance(details, dict):
        length_value = details.get("input_length")
    if not policy_value and isinstance(details, dict):
        policy_value = details.get("lane_policy")
    stage_name = str(candidate.data.get("stage_name", "")).casefold()
    if length_value is None:
        match = re.search(r"(?:^|[_-])(?:len(?:gth)?[_-]?)?([0-9]+)(?:[_-]|$)", stage_name)
        if match:
            length_value = int(match.group(1))
    if not policy_value:
        if "lane0" in stage_name:
            policy_value = "LANE0_ONLY"
        elif "lane1" in stage_name:
            policy_value = "LANE1_ONLY"
        elif "replicate" in stage_name:
            policy_value = "REPLICATE_0X3"
        elif "stripe" in stage_name:
            policy_value = "STRIPE_ROUND_ROBIN"
    try:
        length = int(length_value)
    except (TypeError, ValueError):
        return None
    policy = str(policy_value or "")
    return (length, policy) if policy else None


def validate_boundary_jtag(candidates: Sequence[Candidate], evidence: RepositoryEvidence) -> StageResult:
    if not candidates:
        return missing_stage(evidence, "fragment_boundary", "direct-JTAG 12-length x 4-policy boundary matrix is missing")
    grouped: dict[tuple[int, str], list[Candidate]] = {}
    unknown: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        pair = intended_boundary_pair(candidate, evidence)
        if pair is None:
            unknown.setdefault(str(candidate.data.get("stage_name", candidate.path)), []).append(candidate)
        else:
            grouped.setdefault(pair, []).append(candidate)
    selected = {pair: choose_latest(items) for pair, items in grouped.items()}
    errors: list[str] = []
    sources: list[str] = []
    superseded = sum(max(0, len(items) - 1) for items in grouped.values())
    for pair in REQUIRED_BOUNDARY_JTAG:
        candidate = selected.get(pair)
        if candidate is None:
            errors.append(f"direct-JTAG boundary case missing: {pair}")
            continue
        common, provenance = common_runner_errors(candidate, evidence)
        linked, parse_path, link_errors = linked_backend_parse(candidate, evidence)
        local = common + link_errors
        parsed = linked.get("parse", {}) if isinstance(linked, dict) else {}
        observed = (int(parsed.get("object_length", -1)), str(parsed.get("lane_policy", "")))
        append_error(local, observed == pair, f"boundary intended/parsed pair mismatch: intended={pair} parsed={observed}")
        if local:
            errors.extend(f"{rel(candidate.path, evidence.repo_root)}: {item}" for item in local)
        sources.append(rel(candidate.path, evidence.repo_root))
        if parse_path is not None:
            sources.append(rel(parse_path, evidence.repo_root))
        evidence.provenance_rows.append(provenance)
    for name, items in unknown.items():
        latest = choose_latest(items)
        errors.append(f"unable to classify latest intended boundary pair: {name} summary={rel(latest.path, evidence.repo_root) if latest else 'MISSING'}")
        superseded += max(0, len(items) - 1)
    return StageResult(
        "fragment_boundary",
        "PASS" if not errors else "FAIL",
        "direct-JTAG strict parser passed all 12 boundary lengths on lane0/lane1/stripe/replicate" if not errors else "direct-JTAG fragment boundary matrix failed closed",
        sorted(set(sources)),
        metrics={"required_pairs": len(REQUIRED_BOUNDARY_JTAG), "observed_required_pairs": len(REQUIRED_BOUNDARY_JTAG & set(selected))},
        errors=errors,
        notes=[f"preserved superseded direct-JTAG boundary attempts: {superseded}"],
    )


def linked_backend_parse(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[dict[str, Any] | None, Path | None, list[str]]:
    errors: list[str] = []
    raw_expected = (candidate.path.parent / "p7_jtag_axi_raw_result.txt").resolve(strict=False)
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path, data in evidence.backend_parses:
        raw = resolve_reference(data.get("raw_log"), document=path, repo_root=evidence.repo_root)
        if raw == raw_expected:
            matches.append((path, data))
    if len(matches) != 1:
        return None, None, [f"expected exactly one strict backend parse bound to safe-wrapper raw log; observed={len(matches)}"]
    path, parsed = matches[0]
    append_error(errors, parsed.get(BACKEND_PARSE_MARKER) == "PASS", "strict JTAG backend parser is not PASS")
    manifest_path = resolve_reference(parsed.get("manifest"), document=path, repo_root=evidence.repo_root)
    output_path = resolve_reference(parsed.get("output_file"), document=path, repo_root=evidence.repo_root)
    append_error(errors, manifest_path is not None and manifest_path.is_file(), "JTAG bundle manifest missing")
    append_error(errors, output_path is not None and output_path.is_file(), "JTAG reassembled output missing")
    manifest: dict[str, Any] = {}
    if manifest_path is not None and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"JTAG bundle manifest invalid: {exc}")
    append_error(errors, manifest.get("schema") == JTAG_MANIFEST_SCHEMA, "JTAG bundle manifest schema mismatch")
    append_error(errors, manifest.get("network_used") is False, "JTAG generator manifest network_used is not false")
    append_error(errors, set(manifest.get("allowed_lane_masks", [])) == {1, 2, 3}, "JTAG manifest lane masks are not exactly 1/2/3")
    tx_path = None
    if manifest_path is not None:
        tx_path = resolve_reference(manifest.get("transaction_file"), document=manifest_path, repo_root=evidence.repo_root)
    tx_expected = str(manifest.get("transaction_sha256", "")).lower()
    append_error(errors, tx_path is not None and tx_path.is_file(), "JTAG transaction file missing")
    if tx_path is not None and tx_path.is_file():
        append_error(errors, SHA256_RE.fullmatch(tx_expected) is not None and sha256_file(tx_path) == tx_expected, "JTAG transaction manifest hash mismatch")
        transaction = candidate.data.get("transaction_validation", {})
        append_error(errors, str(transaction.get("actual_sha256", "")).lower() == tx_expected, "safe wrapper transaction hash differs from bundle manifest")
    if output_path is not None and output_path.is_file():
        output = output_path.read_bytes()
        append_error(errors, len(output) == int(parsed.get("object_length", -1)), "JTAG output length mismatch")
        append_error(errors, hashlib.sha256(output).hexdigest() == str(parsed.get("object_sha256", "")).lower(), "JTAG output SHA256 mismatch")
        append_error(errors, (zlib.crc32(output) & 0xFFFFFFFF) == int(parsed.get("object_crc32", -1)), "JTAG output CRC32 mismatch")
    append_error(errors, int(parsed.get("missing_fragments", -1)) == 0, "JTAG parse reports missing fragments")
    append_error(errors, int(parsed.get("duplicate_fragments", -1)) == 0, "JTAG parse reports duplicate fragments")
    append_error(errors, int(parsed.get("error_counter_increments", -1)) == 0, "JTAG parse reports error counter increments")
    if manifest:
        append_error(errors, int(manifest.get("input_length", -1)) == int(parsed.get("object_length", -2)), "JTAG manifest/parser object length mismatch")
        append_error(errors, int(manifest.get("input_crc32", -1)) == int(parsed.get("object_crc32", -2)), "JTAG manifest/parser object CRC32 mismatch")
        append_error(errors, str(manifest.get("input_sha256", "")).lower() == str(parsed.get("object_sha256", "")).lower(), "JTAG manifest/parser object SHA256 mismatch")
    wrapper_parse = candidate.data.get("backend_parse")
    if not isinstance(wrapper_parse, dict):
        errors.append("safe wrapper backend_parse binding record missing")
    else:
        append_error(errors, wrapper_parse.get("passed") is True, "safe wrapper backend_parse is not PASS")
        append_error(errors, wrapper_parse.get("raw_log_bound_to_this_hardware_process") is True, "safe wrapper did not bind parser to this hardware process")
        summary_record = resolve_reference(wrapper_parse.get("summary_file"), document=candidate.path, repo_root=evidence.repo_root)
        append_error(errors, summary_record == path.resolve(strict=False), "safe wrapper backend parser summary path mismatch")
        if summary_record is not None and summary_record.is_file():
            append_error(errors, sha256_file(summary_record) == str(wrapper_parse.get("summary_sha256", "")).lower(), "safe wrapper backend parser summary SHA256 mismatch")
        append_error(errors, output_path is not None and output_path == resolve_reference(wrapper_parse.get("output_file"), document=candidate.path, repo_root=evidence.repo_root), "safe wrapper backend output path mismatch")
        if output_path is not None and output_path.is_file():
            append_error(errors, sha256_file(output_path) == str(wrapper_parse.get("output_sha256", "")).lower(), "safe wrapper backend output SHA256 mismatch")
    return {"parse": parsed, "manifest": manifest}, path, errors


def validate_large_jtag_metrics(candidate: Candidate, parsed: Mapping[str, Any]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    wrapper = candidate.data.get("backend_parse")
    if not isinstance(wrapper, dict):
        return ["large-JTAG wrapper backend_parse metrics record missing"], {}
    object_length = int(parsed.get("object_length", -1))
    fragment_count = int(parsed.get("fragment_count", -1))
    fragments = parsed.get("fragments")
    append_error(errors, object_length > 0, "large-JTAG object length is not positive")
    append_error(errors, isinstance(fragments, list) and len(fragments) == fragment_count > 0, "large-JTAG fragment latency ledger count mismatch")
    latency_bounds = [int(item.get("latency_upper_bound_us", 0)) for item in fragments if isinstance(item, dict)] if isinstance(fragments, list) else []
    append_error(errors, len(latency_bounds) == fragment_count and all(value > 0 for value in latency_bounds), "large-JTAG fragment latency upper bounds are missing/nonpositive")
    latency_summary = parsed.get("fragment_latency_upper_bound_us")
    if not isinstance(latency_summary, dict):
        errors.append("large-JTAG fragment latency summary missing")
        latency_summary = {}
    if latency_bounds:
        ordered = sorted(latency_bounds)

        def nearest_rank(numerator: int, denominator: int) -> int:
            rank = max(0, ((numerator * len(ordered) + denominator - 1) // denominator) - 1)
            return ordered[min(rank, len(ordered) - 1)]

        expected_summary = {
            "sample_count": len(ordered),
            "min": ordered[0],
            "mean": round(sum(ordered) / len(ordered), 6),
            "p50": nearest_rank(50, 100),
            "p95": nearest_rank(95, 100),
            "p99": nearest_rank(99, 100),
            "max": ordered[-1],
            "percentile_method": "nearest_rank",
            "semantics": "upper_bound",
            "source": "bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period",
        }
        append_error(errors, latency_summary == expected_summary, "large-JTAG fragment latency summary does not recompute from fragment bounds")
    object_upper = int(parsed.get("object_transport_latency_upper_bound_us", -1))
    append_error(errors, object_upper == sum(latency_bounds) > 0, "large-JTAG object transport upper bound is not the sum of fragment bounds")
    append_error(errors, parsed.get("object_transport_latency_semantics") == "sum_of_sequential_fragment_poll_upper_bounds", "large-JTAG object latency semantics missing/mismatch")
    expected_poll_goodput = (object_length * 8_000_000) // object_upper if object_upper > 0 else 0
    append_error(errors, int(parsed.get("poll_bound_application_goodput_lower_bound_bps", -1)) == expected_poll_goodput > 0, "large-JTAG poll-bound goodput formula mismatch")
    append_error(errors, parsed.get("poll_bound_goodput_semantics") == "lower_bound_from_object_bytes_over_transport_latency_upper_bound", "large-JTAG poll-bound goodput semantics missing/mismatch")
    for key in (
        "object_length",
        "fragment_count",
        "fragment_latency_upper_bound_us",
        "object_transport_latency_upper_bound_us",
        "object_transport_latency_semantics",
        "poll_bound_application_goodput_lower_bound_bps",
        "poll_bound_goodput_semantics",
    ):
        append_error(errors, wrapper.get(key) == parsed.get(key), f"large-JTAG wrapper/parser metric mismatch: {key}")
    host_elapsed = float(wrapper.get("host_end_to_end_elapsed_seconds", 0))
    append_error(errors, host_elapsed > 0, "large-JTAG host end-to-end elapsed time is not positive")
    expected_host_goodput = round(object_length * 8.0 / host_elapsed, 6) if host_elapsed > 0 else 0.0
    append_error(errors, float(wrapper.get("host_end_to_end_goodput_bps", -1)) == expected_host_goodput, "large-JTAG host end-to-end goodput formula mismatch")
    append_error(errors, wrapper.get("host_end_to_end_time_source") == "host_monotonic_child_process_elapsed", "large-JTAG host timing source missing/mismatch")
    host_semantics = str(wrapper.get("host_end_to_end_semantics", ""))
    append_error(errors, "host overhead" in host_semantics and "not optical-only" in host_semantics, "large-JTAG host metric semantics do not exclude optical-only interpretation")
    row = {
        "object_length": object_length,
        "lane_policy": parsed.get("lane_policy"),
        "fragment_count": fragment_count,
        "fragment_latency_upper_bound_us": latency_summary,
        "object_transport_latency_upper_bound_us": object_upper,
        "poll_bound_application_goodput_lower_bound_bps": expected_poll_goodput,
        "host_end_to_end_elapsed_seconds": host_elapsed,
        "host_end_to_end_goodput_bps": expected_host_goodput,
        "host_end_to_end_time_source": wrapper.get("host_end_to_end_time_source"),
        "host_end_to_end_semantics": host_semantics,
    }
    return errors, row


def validate_large_jtag(candidates: Sequence[Candidate], evidence: RepositoryEvidence) -> StageResult:
    if not candidates:
        return missing_stage(evidence, "large_object_jtag", "no fresh direct JTAG/AXI large-object safe-wrapper evidence")
    grouped: dict[tuple[int, str, str], list[Candidate]] = {}
    unclassified: dict[str, list[Candidate]] = {}
    for candidate in candidates:
        key = intended_jtag_tuple(candidate, evidence)
        if key is None:
            unclassified.setdefault(str(candidate.data.get("stage_name", candidate.path)), []).append(candidate)
        else:
            grouped.setdefault(key, []).append(candidate)
    selected = {key: choose_latest(items) for key, items in grouped.items()}
    records: dict[tuple[int, str, str], tuple[Candidate, Path, dict[str, Any]]] = {}
    errors: list[str] = []
    sources: list[str] = []
    case_metrics: list[dict[str, Any]] = []
    superseded = sum(max(0, len(items) - 1) for items in grouped.values())
    for key, candidate in selected.items():
        if candidate is None:
            continue
        common, provenance = common_runner_errors(candidate, evidence)
        linked, parse_path, link_errors = linked_backend_parse(candidate, evidence)
        local = common + link_errors
        if linked is None or parse_path is None:
            errors.extend(f"{rel(candidate.path, evidence.repo_root)}: {item}" for item in local)
            continue
        parsed = linked["parse"]
        manifest = linked["manifest"]
        observed_key = (
            int(parsed.get("object_length", -1)),
            str(parsed.get("lane_policy", "")),
            pattern_from_manifest(manifest, str(candidate.data.get("stage_name", ""))),
        )
        append_error(local, observed_key == key, f"intended/parsed JTAG tuple mismatch: intended={key} parsed={observed_key}")
        metric_errors, metric_row = validate_large_jtag_metrics(candidate, parsed)
        local.extend(metric_errors)
        if metric_row:
            case_metrics.append({"pattern": key[2], **metric_row})
        records[key] = (candidate, parse_path, linked)
        if local:
            errors.extend(f"{rel(candidate.path, evidence.repo_root)}: {item}" for item in local)
        evidence.provenance_rows.append(provenance)
    for name, items in unclassified.items():
        latest = choose_latest(items)
        errors.append(f"unable to classify latest intended large-JTAG tuple: {name} summary={rel(latest.path, evidence.repo_root) if latest else 'MISSING'}")
        superseded += max(0, len(items) - 1)
    missing = sorted(REQUIRED_LARGE_JTAG - set(records), key=str)
    if missing:
        errors.append(f"direct JTAG large-object matrix missing tuples: {missing}")
    for key, (candidate, parse_path, _linked) in records.items():
        if key in REQUIRED_LARGE_JTAG:
            sources.extend((rel(candidate.path, evidence.repo_root), rel(parse_path, evidence.repo_root)))
    return StageResult(
        "large_object_jtag",
        "PASS" if not errors else "FAIL",
        "strict safe-wrapper + raw-log-bound backend parser passed the required 1 MiB/64 KiB matrix" if not errors else "direct JTAG large-object evidence failed closed",
        sorted(set(sources)),
        metrics={
            "required_cases": len(REQUIRED_LARGE_JTAG),
            "observed_required_cases": len(REQUIRED_LARGE_JTAG & set(records)),
            "cases": sorted(case_metrics, key=lambda row: (int(row["object_length"]), str(row["lane_policy"]), str(row["pattern"]))),
        },
        errors=errors,
        notes=[
            "JTAG/AXI is auxiliary evidence and cannot promote PS_PL_PHY_PL_PS_APPLICATION_PASS",
            f"preserved superseded direct-JTAG attempts: {superseded}",
        ],
    )


def stationary_results(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[StageResult, StageResult, StageResult]:
    errors, provenance = common_runner_errors(candidate, evidence)
    post_errors, post = require_ps_postprocess(candidate)
    errors.extend(post_errors)
    mailbox = post.get("mailbox", {}) if isinstance(post, dict) else {}
    objects = post.get("stationary_objects", []) if isinstance(post, dict) else []
    samples = post.get("stationary_samples", []) if isinstance(post, dict) else []
    append_error(errors, candidate.data.get("service_runtime_limit_sec") == 1800, "stationary configured runtime is not exactly 1800 seconds")
    append_error(errors, int(mailbox.get("max_runtime_seconds", -1)) == 1800, "stationary firmware runtime is not exactly 1800 seconds")
    append_error(errors, int(mailbox.get("calibration_window_seconds", -1)) == 300, "stationary calibration window is not exactly 300 seconds")
    append_error(errors, int(mailbox.get("sample_interval_seconds", -1)) == 30, "stationary mailbox sample interval is not exactly 30 seconds")
    append_error(errors, int(mailbox.get("runtime_flags", 0)) & 0x2 == 0x2, "stationary mailbox deadline-reached flag is missing")
    append_error(errors, candidate.data.get("scheduling_cutoff_sec") == 1740, "stationary scheduling cutoff is not the authorized 1740 seconds")
    try:
        wall = float(mailbox.get("observed_wall_seconds", -1))
    except (TypeError, ValueError):
        wall = -1.0
    append_error(errors, 1800.0 <= wall <= 1801.5, "stationary host wall duration is outside 1800.0..1801.5 seconds")
    append_error(errors, isinstance(objects, list) and len(objects) >= 8, "stationary per-object ledger is missing/too short")
    runtime_start_ticks = int(mailbox.get("runtime_start_ticks", -1))
    append_error(errors, runtime_start_ticks > 0, "stationary mailbox runtime_start_ticks is missing/invalid")
    final_cases = {
        int(item.get("slot", -1)): item
        for item in post.get("cases", [])
        if isinstance(item, dict) and isinstance(item.get("descriptor"), dict)
    }
    append_error(errors, set(final_cases) == set(STATIONARY_SLOT_CONTRACT), "stationary final case slots are not exactly 0..7")
    for slot, contract in STATIONARY_SLOT_CONTRACT.items():
        final_case = final_cases.get(slot)
        if not isinstance(final_case, dict):
            continue
        descriptor = final_case.get("descriptor", {})
        append_error(errors, str(final_case.get("name", "")) == contract[0], f"stationary slot {slot} deterministic name/pattern mismatch")
        observed_geometry = (
            int(descriptor.get("object_length", -1)),
            int(descriptor.get("lane_policy", -1)),
            int(descriptor.get("unavailable_lane_mask", -1)),
            int(descriptor.get("unavailable_after_fragment", -1)),
        )
        append_error(errors, observed_geometry == contract[2:], f"stationary slot {slot} size/policy/fallback contract mismatch")

    bundle_record = candidate.data.get("bundle_manifest")
    bundle_path = resolve_reference(
        bundle_record.get("path") if isinstance(bundle_record, dict) else None,
        document=candidate.path,
        repo_root=evidence.repo_root,
    )
    bundle_cases: dict[int, dict[str, Any]] = {}
    if bundle_path is None or not bundle_path.is_file():
        errors.append("stationary immutable bundle manifest missing")
    else:
        try:
            bundle_payload = json.loads(bundle_path.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"stationary immutable bundle manifest invalid: {exc}")
        else:
            manifest_cases = bundle_payload.get("cases") if isinstance(bundle_payload, dict) else None
            append_error(errors, isinstance(manifest_cases, list) and len(manifest_cases) == 8, "stationary bundle case manifest count is not exactly eight")
            if isinstance(manifest_cases, list):
                bundle_cases = {int(item.get("slot", -1)): item for item in manifest_cases if isinstance(item, dict)}
                append_error(errors, set(bundle_cases) == set(STATIONARY_SLOT_CONTRACT), "stationary bundle case slots are not exactly 0..7")
                for slot, contract in STATIONARY_SLOT_CONTRACT.items():
                    record = bundle_cases.get(slot, {})
                    append_error(errors, str(record.get("name", "")) == contract[0], f"stationary bundle slot {slot} name mismatch")
                    append_error(errors, str(record.get("pattern", "")) == contract[1], f"stationary bundle slot {slot} pattern mismatch")
                    manifest_geometry = (
                        int(record.get("object_length", -1)),
                        int(record.get("lane_policy", -1)),
                        int(record.get("unavailable_lane_mask", -1)),
                        int(record.get("unavailable_after_fragment", -1)),
                    )
                    append_error(errors, manifest_geometry == contract[2:], f"stationary bundle slot {slot} geometry mismatch")
                    expected_sha = str(final_cases.get(slot, {}).get("descriptor", {}).get("expected_sha256", "")).lower()
                    input_record = record.get("input")
                    append_error(errors, isinstance(input_record, dict) and str(input_record.get("sha256", "")).lower() == expected_sha, f"stationary bundle slot {slot} input hash does not bind final descriptor")
    for slot, final_case in final_cases.items():
        errors.extend(case_output_errors(candidate, final_case, f"stationary-final-slot-{slot}:"))
    seen_identity: set[tuple[int, int]] = set()
    object_sequences: list[int] = []
    object_end_ticks: list[int] = []
    observed_sizes: set[int] = set()
    observed_policies: set[int] = set()
    for index, item in enumerate(objects if isinstance(objects, list) else []):
        if not isinstance(item, dict):
            errors.append(f"stationary object {index} is not a record")
            continue
        identity = (int(item.get("session_epoch", -1)), int(item.get("object_id", -1)))
        object_sequences.append(int(item.get("sequence", -1)))
        append_error(errors, identity not in seen_identity, f"stationary object identity reused: {identity}")
        seen_identity.add(identity)
        append_error(errors, int(item.get("status", -1)) == 3 and int(item.get("error_code", -1)) == 0, f"stationary object {index} did not complete cleanly")
        start_ticks = int(item.get("start_ticks", -1))
        end_ticks = int(item.get("end_ticks", -1))
        object_end_ticks.append(end_ticks)
        append_error(errors, runtime_start_ticks <= start_ticks < end_ticks, f"stationary object {index} PS timing is invalid or precedes runtime start")
        append_error(errors, end_ticks - runtime_start_ticks <= 1800 * PS_COUNTS_PER_SECOND, f"stationary object {index} completed after the canonical 1800-second deadline")
        size = int(item.get("bytes_completed", -1))
        append_error(errors, size in {4_096, 65_536, 1_048_576}, f"stationary object {index} size is not 4 KiB/64 KiB/1 MiB")
        observed_sizes.add(size)
        append_error(errors, int(item.get("fragments_completed", -1)) == int(item.get("fragments_total", -2)), f"stationary object {index} fragment ledger incomplete")
        append_error(errors, SHA256_RE.fullmatch(str(item.get("output_sha256", "")).lower()) is not None, f"stationary object {index} output SHA256 missing")
        for key in ("p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad", "p6_payload_mismatch", "duty_violations"):
            append_error(errors, int(item.get(key, -1)) == 0, f"stationary object {index} {key} is missing/nonzero")
        append_error(errors, 0 < int(item.get("max_txd_high_cycles", 0)) <= 8, f"stationary object {index} TXD-high limit invalid")
        slot = int(item.get("slot", -1))
        final_case = final_cases.get(slot, {})
        descriptor = final_case.get("descriptor", {}) if isinstance(final_case, dict) else {}
        append_error(errors, str(item.get("output_sha256", "")).lower() == str(descriptor.get("expected_sha256", "")).lower(), f"stationary object {index} output SHA256 differs from slot input identity")
        policy = int(descriptor.get("lane_policy", -1))
        unavailable = int(descriptor.get("unavailable_lane_mask", 0))
        observed_policies.add(policy)
        fragments = int(item.get("fragments_total", -1))
        lane0 = int(item.get("lane0_fragments", -1))
        lane1 = int(item.get("lane1_fragments", -1))
        replicated = int(item.get("replicated_fragments", -1))
        if policy == 1:
            append_error(errors, (lane0, lane1, replicated) == (fragments, 0, 0), f"stationary object {index} lane0-only counters mismatch")
        elif policy == 2:
            append_error(errors, (lane0, lane1, replicated) == (0, fragments, 0), f"stationary object {index} lane1-only counters mismatch")
        elif policy == 4:
            append_error(errors, (lane0, lane1, replicated) == (fragments, fragments, fragments), f"stationary object {index} replicate counters mismatch")
        elif policy == 3 and unavailable == 0:
            append_error(errors, lane0 > 0 and lane1 > 0 and lane0 + lane1 == fragments and abs(lane0 - lane1) <= 1 and replicated == 0, f"stationary object {index} stripe counters mismatch")
        elif policy == 3 and unavailable == 1:
            append_error(errors, int(item.get("fallback_count", 0)) >= 1 and (lane0, lane1, replicated) == (1, fragments - 1, 0), f"stationary object {index} lane0 fallback counters mismatch")
        elif policy == 3 and unavailable == 2:
            append_error(errors, int(item.get("fallback_count", 0)) >= 1 and (lane0, lane1, replicated) == (fragments - 1, 1, 0), f"stationary object {index} lane1 fallback counters mismatch")
        else:
            errors.append(f"stationary object {index} has invalid/unbound lane policy {policy}")
    append_error(errors, {4_096, 65_536, 1_048_576} <= observed_sizes, "stationary ledger does not cover 4 KiB, 64 KiB, and 1 MiB")
    append_error(errors, {1, 2, 3, 4} <= observed_policies, "stationary ledger does not cover lane0, lane1, stripe, and replicate policies")
    append_error(errors, object_sequences == list(range(1, len(objects) + 1)), "stationary object completion sequence is not contiguous")
    append_error(errors, all(left < right for left, right in zip(object_end_ticks, object_end_ticks[1:])), "stationary terminal end_ticks are not strictly increasing with completion sequence")
    mailbox_aggregates = {
        "objects_requested": len(objects),
        "objects_completed": len(objects),
        "objects_failed": 0,
        "bytes_completed": sum(int(item.get("bytes_completed", 0)) for item in objects if isinstance(item, dict)),
        "fragments_completed": sum(int(item.get("fragments_completed", 0)) for item in objects if isinstance(item, dict)),
        "lane0_fragments": sum(int(item.get("lane0_fragments", 0)) for item in objects if isinstance(item, dict)),
        "lane1_fragments": sum(int(item.get("lane1_fragments", 0)) for item in objects if isinstance(item, dict)),
        "fallback_count": sum(int(item.get("fallback_count", 0)) for item in objects if isinstance(item, dict)),
        "p6_retry_count": sum(int(item.get("p6_retry_count", 0)) for item in objects if isinstance(item, dict)),
        "p6_retry_exhausted": 0,
        "p6_tx_fail": 0,
        "p6_crc_bad": 0,
        "p6_payload_mismatch": 0,
        "max_txd_high_cycles": max((int(item.get("max_txd_high_cycles", 0)) for item in objects if isinstance(item, dict)), default=0),
        "duty_violation_count": 0,
    }
    for key, expected in mailbox_aggregates.items():
        append_error(errors, int(mailbox.get(key, -1)) == expected, f"stationary mailbox does not exactly reconcile to terminal ledger: {key}")
    calibration_samples = [item for item in samples if isinstance(item, dict) and item.get("window") == "CALIBRATION"]
    acceptance_samples = [item for item in samples if isinstance(item, dict) and item.get("window") == "ACCEPTANCE"]
    append_error(errors, len(calibration_samples) == 10, "stationary calibration sample count is not exactly 10")
    append_error(errors, len(acceptance_samples) == 50, "stationary acceptance sample count is not exactly 50")
    append_error(errors, len(samples) == 60, "stationary 30-second sample series is not exactly 60 samples")
    elapsed = [float(item.get("elapsed_sec", -1)) for item in samples if isinstance(item, dict)]
    append_error(errors, bool(elapsed) and all(b > a for a, b in zip(elapsed, elapsed[1:])), "stationary sample elapsed times are not strictly increasing")
    append_error(errors, bool(elapsed) and 1800.0 <= elapsed[-1] <= 1801.5, "stationary final PS-timer sample is outside 1800.0..1801.5 seconds")
    previous_sample_ticks = 0
    previous_sample_bytes = 0
    previous_queue_observation_not_before_ticks = 0
    for index, item in enumerate(samples if isinstance(samples, list) else []):
        if not isinstance(item, dict):
            continue
        append_error(errors, int(item.get("failed", -1)) == 0, f"stationary sample {index} reports failed objects")
        for key in ("p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad", "p6_payload_mismatch", "duty_violations"):
            append_error(errors, int(item.get(key, -1)) == 0, f"stationary sample {index} {key} is missing/nonzero")
        append_error(errors, 0 <= int(item.get("queue_occupancy", -1)) <= 8, f"stationary sample {index} queue occupancy invalid")
        append_error(errors, 0 <= int(item.get("queue_high", -1)) <= 8, f"stationary sample {index} queue high-water invalid")
        append_error(errors, int(item.get("max_txd_high", 0)) <= 8, f"stationary sample {index} TXD-high limit exceeded")
        append_error(errors, int(item.get("sequence", index + 1)) == index + 1, f"stationary sample {index} sequence is not contiguous")
        sample_ticks = int(item.get("elapsed_ticks", -1))
        append_error(errors, sample_ticks > previous_sample_ticks, f"stationary sample {index} exact PS elapsed_ticks is missing/non-monotonic")
        append_error(errors, sample_ticks == (index + 1) * 30 * PS_COUNTS_PER_SECOND, f"stationary sample {index} is not the canonical {(index + 1) * 30}-second boundary")
        queue_not_before_ticks = int(item.get("queue_observation_not_before_ticks", -1))
        append_error(errors, queue_not_before_ticks >= sample_ticks, f"stationary sample {index} queue-observation lower bound precedes its canonical PS threshold")
        append_error(errors, previous_queue_observation_not_before_ticks <= queue_not_before_ticks <= int(mailbox.get("runtime_elapsed_ticks", -1)), f"stationary sample {index} queue-observation lower bound is non-monotonic or beyond terminal runtime")
        previous_queue_observation_not_before_ticks = queue_not_before_ticks
        if sample_ticks > 0:
            append_error(
                errors,
                abs(float(item.get("elapsed_sec", -1)) - (sample_ticks / PS_COUNTS_PER_SECOND)) <= 0.001,
                f"stationary sample {index} elapsed seconds do not represent exact PS elapsed_ticks",
            )
        expected_window = "CALIBRATION" if index < 10 else "ACCEPTANCE"
        append_error(errors, item.get("window") == expected_window, f"stationary sample {index} window classification mismatch")
        terminal_count = int(item.get("objects", -1))
        append_error(errors, 0 <= terminal_count <= len(objects), f"stationary sample {index} object count exceeds ledger")
        if sample_ticks > 0:
            prefix = [
                row
                for row in objects
                if isinstance(row, dict) and int(row.get("end_ticks", -1)) - runtime_start_ticks <= sample_ticks
            ]
            append_error(errors, terminal_count == len(prefix), f"stationary sample {index} object count is not causally bound to terminal end_ticks")
            snapshot = {
                "bytes": sum(int(row.get("bytes_completed", 0)) for row in prefix),
                "fragments": sum(int(row.get("fragments_completed", 0)) for row in prefix),
                "lane0": sum(int(row.get("lane0_fragments", 0)) for row in prefix),
                "lane1": sum(int(row.get("lane1_fragments", 0)) for row in prefix),
                "replicated": sum(int(row.get("replicated_fragments", 0)) for row in prefix),
                "fallbacks": sum(int(row.get("fallback_count", 0)) for row in prefix),
                "p6_retries": sum(int(row.get("p6_retry_count", 0)) for row in prefix),
                "p6_retry_exhausted": sum(int(row.get("p6_retry_exhausted", 0)) for row in prefix),
                "p6_tx_fail": sum(int(row.get("p6_tx_fail", 0)) for row in prefix),
                "p6_crc_bad": sum(int(row.get("p6_crc_bad", 0)) for row in prefix),
                "p6_payload_mismatch": sum(int(row.get("p6_payload_mismatch", 0)) for row in prefix),
                "duty_violations": sum(int(row.get("duty_violations", 0)) for row in prefix),
                "max_txd_high": max((int(row.get("max_txd_high_cycles", 0)) for row in prefix), default=0),
                "last_object": int(prefix[-1].get("object_id", 0)) if prefix else 0,
            }
            for key, expected in snapshot.items():
                append_error(errors, int(item.get(key, -1)) == expected, f"stationary sample {index} does not reconcile to ledger: {key}")
            expected_current_bps = (snapshot["bytes"] * 8 * PS_COUNTS_PER_SECOND) // sample_ticks
            sample_delta_ticks = sample_ticks - previous_sample_ticks
            expected_rolling_bps = ((snapshot["bytes"] - previous_sample_bytes) * 8 * PS_COUNTS_PER_SECOND) // sample_delta_ticks
            append_error(errors, int(item.get("current_bps", -1)) == expected_current_bps, f"stationary sample {index} cumulative goodput formula mismatch")
            append_error(errors, int(item.get("rolling_bps", -1)) == expected_rolling_bps, f"stationary sample {index} rolling goodput is not bound to the causal 30-second object window")
            interval_rows = [
                row
                for row in prefix
                if int(row.get("end_ticks", -1)) - runtime_start_ticks > previous_sample_ticks
            ]
            interval_latencies = sorted(int(row.get("end_ticks", 0)) - int(row.get("start_ticks", 0)) for row in interval_rows)
            if interval_latencies:
                def nearest_rank(numerator: int, denominator: int) -> int:
                    rank = max(0, ((numerator * len(interval_latencies) + denominator - 1) // denominator) - 1)
                    return interval_latencies[min(rank, len(interval_latencies) - 1)]

                expected_latency = {
                    "latency_count": len(interval_latencies),
                    "latency_min_ticks": interval_latencies[0],
                    "latency_mean_ticks": sum(interval_latencies) // len(interval_latencies),
                    "latency_p50_ticks": nearest_rank(50, 100),
                    "latency_p95_ticks": nearest_rank(95, 100),
                    "latency_p99_ticks": nearest_rank(99, 100),
                    "latency_max_ticks": interval_latencies[-1],
                }
            else:
                expected_latency = {
                    "latency_count": 0,
                    "latency_min_ticks": 0,
                    "latency_mean_ticks": 0,
                    "latency_p50_ticks": 0,
                    "latency_p95_ticks": 0,
                    "latency_p99_ticks": 0,
                    "latency_max_ticks": 0,
                }
            for key, expected in expected_latency.items():
                append_error(errors, int(item.get(key, -1)) == expected, f"stationary sample {index} causal interval latency mismatch: {key}")
            previous_sample_bytes = snapshot["bytes"]
            previous_sample_ticks = sample_ticks
        latency = [
            int(item.get("latency_min_ticks", 0)),
            int(item.get("latency_mean_ticks", 0)),
            int(item.get("latency_p50_ticks", 0)),
            int(item.get("latency_p95_ticks", 0)),
            int(item.get("latency_p99_ticks", 0)),
            int(item.get("latency_max_ticks", 0)),
        ]
        if int(item.get("latency_count", 0)) == 0:
            append_error(errors, not any(latency), f"stationary sample {index} empty latency set has nonzero statistics")
        else:
            append_error(errors, 0 < latency[0] <= latency[2] <= latency[3] <= latency[4] <= latency[5] and latency[0] <= latency[1] <= latency[5], f"stationary sample {index} latency ordering is invalid")
    cal_median = statistics.median([int(item.get("rolling_bps", 0)) for item in calibration_samples]) if calibration_samples else 0
    acc_median = statistics.median([int(item.get("rolling_bps", 0)) for item in acceptance_samples]) if acceptance_samples else 0
    append_error(errors, cal_median > 0 and acc_median > 0, "stationary rolling-goodput medians are not positive")
    append_error(errors, cal_median > 0 and acc_median >= 0.8 * cal_median, "acceptance goodput median is below 80% of calibration")
    calibration_baseline: dict[str, Any] = {}
    calibration_latency: dict[str, Any] = {
        "definition": (
            "full PS object-processing interval from a valid descriptor entering RUNNING through output "
            "CRC32/SHA256 completion, excluding host descriptor publication and JTAG terminal observation"
        ),
        "time_source": "PS global timer",
        "percentile_scope": "each 30-second calibration interval; interval percentiles are not merged into a synthetic global percentile",
    }
    if calibration_samples:
        baseline = calibration_samples[-1]
        baseline_fragments = int(baseline.get("fragments", 0))
        baseline_lane0 = int(baseline.get("lane0", 0))
        baseline_lane1 = int(baseline.get("lane1", 0))
        baseline_replicated = int(baseline.get("replicated", 0))
        physical_transmissions = baseline_lane0 + baseline_lane1
        append_error(errors, int(baseline.get("sequence", -1)) == 10, "calibration baseline is not bound to sample 10")
        append_error(errors, 299.0 <= float(baseline.get("elapsed_sec", -1)) <= 301.5, "calibration baseline sample is not at the 300-second boundary")
        append_error(errors, int(baseline.get("bytes", 0)) > 0 and baseline_fragments > 0, "calibration baseline has no completed payload")
        append_error(errors, baseline_lane0 > 0 and baseline_lane1 > 0 and baseline_replicated > 0, "calibration baseline does not establish both-lane and replication utilization")
        append_error(errors, int(baseline.get("fallbacks", 0)) > 0, "calibration baseline does not include controlled fallback")
        calibration_baseline = {
            "sample_sequence": int(baseline.get("sequence", -1)),
            "elapsed_sec": float(baseline.get("elapsed_sec", -1)),
            "objects_completed": int(baseline.get("objects", 0)),
            "bytes_completed": int(baseline.get("bytes", 0)),
            "logical_fragments_completed": baseline_fragments,
            "lane0_fragment_transmissions": baseline_lane0,
            "lane1_fragment_transmissions": baseline_lane1,
            "replicated_logical_fragments": baseline_replicated,
            "physical_fragment_transmissions": physical_transmissions,
            "lane0_physical_transmission_fraction": (baseline_lane0 / physical_transmissions) if physical_transmissions else 0.0,
            "lane1_physical_transmission_fraction": (baseline_lane1 / physical_transmissions) if physical_transmissions else 0.0,
            "replicated_logical_fragment_fraction": (baseline_replicated / baseline_fragments) if baseline_fragments else 0.0,
            "controlled_fallback_events": int(baseline.get("fallbacks", 0)),
            "queue_high_watermark": int(baseline.get("queue_high", 0)),
            "backpressure_events": int(baseline.get("backpressure", 0)),
            "time_source": "PS global timer sample 10 at the embedded 300-second boundary",
        }
        nonempty_latency = [item for item in calibration_samples if int(item.get("latency_count", 0)) > 0]
        append_error(errors, len(nonempty_latency) == 10, "calibration latency distribution is not populated in all ten intervals")
        latency_observations = sum(int(item.get("latency_count", 0)) for item in nonempty_latency)
        weighted_mean_numerator = sum(
            int(item.get("latency_mean_ticks", 0)) * int(item.get("latency_count", 0))
            for item in nonempty_latency
        )
        calibration_latency.update(
            {
                "interval_count": len(calibration_samples),
                "nonempty_interval_count": len(nonempty_latency),
                "observation_count": latency_observations,
                "minimum_ticks": min((int(item.get("latency_min_ticks", 0)) for item in nonempty_latency), default=0),
                "weighted_interval_mean_ticks": (weighted_mean_numerator / latency_observations) if latency_observations else 0.0,
                "interval_p50_ticks": [int(item.get("latency_p50_ticks", 0)) for item in nonempty_latency],
                "interval_p95_ticks": [int(item.get("latency_p95_ticks", 0)) for item in nonempty_latency],
                "interval_p99_ticks": [int(item.get("latency_p99_ticks", 0)) for item in nonempty_latency],
                "maximum_ticks": max((int(item.get("latency_max_ticks", 0)) for item in nonempty_latency), default=0),
            }
        )
    append_error(errors, any(int(item.get("fallbacks", 0)) > 0 for item in samples if isinstance(item, dict)), "stationary samples do not prove controlled fallback")
    raw_markers = markers(candidate)
    append_error(errors, raw_markers.get("P7_STATIONARY_PRIMARY_TIME_SOURCE") == "PS_RUNTIME_ELAPSED_TICKS", "stationary primary PS time-source marker missing")
    append_error(errors, raw_markers.get("P7_STATIONARY_HOST_TIME_ROLE") == "INDEPENDENT_WATCHDOG_AND_INPUT_PRELOAD", "stationary host time-role marker missing")
    append_error(errors, raw_markers.get("P7_STATIONARY_SAMPLE_SEMANTICS") == "FIXED_PS_THRESHOLDS_FROM_IMMUTABLE_TERMINAL_END_TICKS", "stationary canonical sample semantics marker missing")
    append_error(errors, integer_marker((raw_markers,), ("P7_STATIONARY_RUNTIME_START_TICKS",)) == runtime_start_ticks, "stationary runtime-start marker/mailbox mismatch")
    append_error(errors, raw_markers.get("P7_CALIBRATION_WINDOW_COMPLETE") == "1", "stationary calibration completion marker missing")
    append_error(errors, raw_markers.get("P7_ACCEPTANCE_WINDOW_COMPLETE") == "1", "stationary acceptance completion marker missing")
    append_error(errors, raw_markers.get("P7_REQUEUE_AFTER_CUTOFF") == "0", "stationary requeue-after-cutoff marker is missing/nonzero")
    append_error(errors, raw_markers.get("P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION") == "0", "stationary cutoff-violation marker is missing/nonzero")
    append_error(errors, integer_marker((raw_markers,), ("P7_STATIONARY_REQUEUE_CUTOFF_TICKS",)) == 1740 * PS_COUNTS_PER_SECOND, "stationary cutoff tick marker mismatch")
    try:
        drain_elapsed = float(raw_markers.get("P7_STATIONARY_DRAIN_COMPLETE_ELAPSED", "nan"))
        drain_ticks = int(raw_markers.get("P7_STATIONARY_DRAIN_COMPLETE_TICKS", -1))
    except ValueError:
        drain_elapsed, drain_ticks = float("nan"), -1
    append_error(errors, 1740.0 <= drain_elapsed <= 1790.0, "stationary drain completion is outside 1740..1790 seconds")
    append_error(errors, drain_ticks >= 1740 * PS_COUNTS_PER_SECOND and drain_ticks <= 1790 * PS_COUNTS_PER_SECOND, "stationary drain completion ticks are outside cutoff..1790")
    append_error(errors, abs(drain_elapsed - drain_ticks / PS_COUNTS_PER_SECOND) <= 0.001, "stationary drain elapsed/ticks mismatch")
    try:
        raw_wall = float(raw_markers.get("P7_STATIONARY_WALL_SECONDS", "nan"))
    except ValueError:
        raw_wall = float("nan")
    append_error(errors, abs(raw_wall - wall) <= 0.001, "stationary host wall marker/mailbox mismatch")
    append_error(errors, raw_markers.get("P7_STATIONARY_HOST_WATCHDOG_CORROBORATION") == "PASS", "stationary independent host watchdog marker missing")
    append_error(errors, integer_marker((raw_markers,), ("P7_STATIONARY_TERMINAL_DESCRIPTORS",)) == len(objects), "stationary terminal descriptor marker count mismatch")
    append_error(errors, integer_marker((raw_markers,), ("P7_STATIONARY_PS_ELAPSED_TICKS",)) == int(mailbox.get("runtime_elapsed_ticks", -2)), "stationary PS elapsed marker/mailbox mismatch")
    terminal_refresh = raw_markers.get("P7_TERMINAL_UNACKNOWLEDGED_REFRESH")
    request_value = int(mailbox.get("runtime_elapsed_request", -1))
    ack_value = int(mailbox.get("runtime_elapsed_ack", -2))
    marker_request = integer_marker((raw_markers,), ("P7_TERMINAL_UNACKNOWLEDGED_REQUEST",))
    marker_ack = integer_marker((raw_markers,), ("P7_TERMINAL_UNACKNOWLEDGED_ACK",))
    append_error(errors, terminal_refresh in {"0", "1"}, "terminal runtime-refresh fallback marker is not strict 0/1")
    append_error(errors, marker_request == request_value and marker_ack == ack_value, "terminal runtime-refresh marker tuple differs from final mailbox tuple")
    if terminal_refresh == "1":
        append_error(errors, request_value != ack_value, "terminal runtime-refresh fallback claims an unacknowledged request but final request/ACK are equal")
    elif terminal_refresh == "0":
        append_error(errors, request_value == ack_value, "terminal runtime-refresh fallback is zero but final request/ACK differ")
    append_error(errors, mailbox.get("terminal_unacknowledged_refresh") is (terminal_refresh == "1"), "terminal runtime-refresh postprocess flag mismatch")
    append_error(errors, raw_markers.get("P7_SAMPLE_00060_SAFE_TERMINAL_STATE") == "1", "stationary safe terminal sample marker missing")
    append_error(errors, raw_markers.get("P7_SAMPLE_SEQUENCE_WRITER") == "HOST_POST_TERMINAL", "stationary sample writer provenance marker missing")
    append_error(errors, bool(samples) and int(samples[-1].get("queue_observation_not_before_ticks", -1)) == int(mailbox.get("runtime_elapsed_ticks", -2)), "stationary terminal queue-observation lower bound does not bind the final mailbox runtime")
    append_error(errors, bool(samples) and int(samples[-1].get("objects", -1)) == len(objects), "stationary canonical final sample does not contain every terminal object")
    evidence.provenance_rows.append(provenance)
    source = [rel(candidate.path, evidence.repo_root)]
    stationary = StageResult(
        "stationary",
        "PASS" if not errors else "FAIL",
        "the unique real-PS stationary run completed the exact 1800-second 300+1500 contract" if not errors else "stationary evidence failed closed",
        source,
        metrics={"observed_wall_seconds": wall, "objects": len(objects), "samples": len(samples), "calibration_samples": len(calibration_samples), "acceptance_samples": len(acceptance_samples), "calibration_median_bps": cal_median, "acceptance_median_bps": acc_median},
        errors=list(errors),
        notes=["sample object latency covers PS object processing from descriptor RUNNING through output integrity completion, but excludes host publication and JTAG observation"],
    )
    calibration_errors = [item for item in errors if "calibration" in item.casefold() or "goodput" in item.casefold()]
    calibration = StageResult(
        "calibration",
        "PASS" if not calibration_errors and not errors else "FAIL",
        "the first 300 seconds of the same unique run supplied exactly ten clean calibration samples" if not errors else "embedded calibration evidence failed closed",
        source,
        metrics={
            "window_seconds": 300,
            "samples": len(calibration_samples),
            "median_bps": cal_median,
            "acceptance_median_bps": acc_median,
            "acceptance_to_calibration_ratio": (acc_median / cal_median) if cal_median else 0.0,
            "additional_calibration_runtime_sec": 0,
            "baseline_cumulative_at_300_seconds": calibration_baseline,
            "transport_interval_latency": calibration_latency,
        },
        errors=list(errors),
        notes=["latency percentiles remain per-30-second interval; the summarizer does not manufacture a global percentile from interval summaries"],
    )
    metrics = derive_metrics(candidate, post, errors)
    return stationary, calibration, metrics


def stationary_observed_wall(candidate: Candidate) -> float:
    post = candidate.data.get("postprocess")
    if isinstance(post, dict) and isinstance(post.get("mailbox"), dict):
        try:
            return float(post["mailbox"].get("observed_wall_seconds", -1))
        except (TypeError, ValueError):
            pass
    observed_markers = markers(candidate)
    match = re.search(r"(?:^|\n)P7_STATIONARY_WALL_SECONDS=([0-9]+(?:[.][0-9]+)?)(?:\n|$)", raw)
    return float(match.group(1)) if match else -1.0


def stationary_is_qualified(candidate: Candidate) -> bool:
    post = candidate.data.get("postprocess")
    wall = stationary_observed_wall(candidate)
    return (
        candidate.executed
        and candidate.marker == "PASS"
        and isinstance(post, dict)
        and post.get("passed") is True
        and 1800.0 <= wall <= 1801.5
        and candidate.data.get("service_runtime_limit_sec") == 1800
    )


def _hash_record(path: Path) -> dict[str, Any]:
    return {"path": str(path.resolve(strict=False)), "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}


def _candidate_process(candidate: Candidate) -> dict[str, Any]:
    key = "ps_process" if candidate.kind == "ps" else "stage_process"
    value = candidate.data.get(key)
    if isinstance(value, dict):
        return value
    preflight_key = "preflight" if candidate.kind == "ps" else "preflight_process"
    preflight = candidate.data.get(preflight_key)
    return preflight if isinstance(preflight, dict) else {}


def _candidate_programmed(candidate: Candidate) -> bool:
    return candidate.data.get("programmed_candidate") is True or candidate.data.get("started_ps_elf") is True


def _candidate_mutation_attempted(candidate: Candidate) -> bool:
    return (
        _candidate_programmed(candidate)
        or candidate.data.get("programmed_shutdown_before") is True
        or isinstance(candidate.data.get("shutdown_before"), dict)
    )


def candidate_has_hardware_footprint(candidate: Candidate) -> bool:
    observed, _duplicates = raw_markers(candidate)
    _event_path, events, _event_errors = load_authorized_events(candidate)
    return (
        candidate.executed
        or _candidate_mutation_attempted(candidate)
        or observed.get("P7_CANDIDATE_PROGRAMMED") == "1"
        or observed.get("P7_PS_CANDIDATE_PROGRAMMED") == "1"
        or observed.get("P7_PS_ELF_DOWNLOADED") == "1"
        or any(item.get("event") == "authorized_execution_begin" for item in events)
    )


def orphan_hardware_footprint_errors(evidence: RepositoryEvidence) -> list[str]:
    errors: list[str] = []
    candidate_dirs = {candidate.path.parent.resolve(strict=False) for candidate in evidence.candidates}
    footprint_names = {
        "p7_ps_application_events.json",
        "p7_jtag_axi_stage_events.jsonl",
        "p7_ps_application_raw_result.log",
        "p7_jtag_axi_raw_result.txt",
        "shutdown_before_result.txt",
        "shutdown_after_result.txt",
        "p7_shutdown_before_result.txt",
        "p7_shutdown_after_result.txt",
    }
    if evidence.hardware_root.is_dir():
        for path in evidence.hardware_root.rglob("*"):
            if path.is_file() and path.name in footprint_names and path.parent.resolve(strict=False) not in candidate_dirs:
                errors.append(f"hardware footprint has no parseable final safe-wrapper summary: {rel(path, evidence.repo_root)}")
    for candidate in evidence.candidates:
        if candidate_has_hardware_footprint(candidate) and not candidate.executed:
            errors.append(f"hardware footprint contradicts hardware_actions_executed=true: {rel(candidate.path, evidence.repo_root)}")
    return errors


def _candidate_risk(candidate: Candidate, evidence: RepositoryEvidence) -> int:
    if not _candidate_mutation_attempted(candidate):
        return 5  # Strictly read-only target preflight; no stage coverage.
    if candidate.stage == "large_object_jtag":
        intended = intended_jtag_tuple(candidate, evidence)
        if intended is not None:
            return {4_096: 30, 65_536: 31, 1_048_576: 32}.get(intended[0], 39)
    return RISK_ORDER.get(candidate.stage, 999)


def _candidate_raw_path(candidate: Candidate) -> Path:
    if not _candidate_mutation_attempted(candidate):
        return candidate.path.parent / ("p7_hw_preflight_result.txt" if candidate.kind == "ps" else "p7_preflight_result.txt")
    return candidate.path.parent / ("p7_ps_application_raw_result.log" if candidate.kind == "ps" else "p7_jtag_axi_raw_result.txt")


def _candidate_event_path(candidate: Candidate) -> Path:
    return candidate.path.parent / ("p7_ps_application_events.json" if candidate.kind == "ps" else "p7_jtag_axi_stage_events.jsonl")


def _candidate_attempted_coverage(candidate: Candidate, evidence: RepositoryEvidence) -> list[str]:
    if candidate.stage == "safe_idle":
        return ["safe_idle"]
    if candidate.stage == "p6_frame_regression":
        stage_name = str(candidate.data.get("stage_name", "")).casefold()
        if markers(candidate).get("P7_P6_FRAME_REGRESSION") == "PASS" or not any(
            token in stage_name for token in ("lane0", "lane1", "mask3", "replicate")
        ):
            return ["p6_lane0", "p6_lane1", "p6_mask3"]
        backend = candidate.data.get("backend_parse")
        transaction = candidate.data.get("transaction_validation")
        details = transaction.get("backend_manifest", {}) if isinstance(transaction, dict) else {}
        policy = str(backend.get("lane_policy", "")) if isinstance(backend, dict) else ""
        if not policy and isinstance(details, dict):
            policy = str(details.get("lane_policy", ""))
        if not policy:
            policy = "LANE0_ONLY" if "lane0" in stage_name else "LANE1_ONLY" if "lane1" in stage_name else "REPLICATE_0X3" if "mask3" in stage_name or "replicate" in stage_name else ""
        return {
            "LANE0_ONLY": ["p6_lane0"],
            "LANE1_ONLY": ["p6_lane1"],
            "REPLICATE_0X3": ["p6_mask3"],
        }.get(policy, [])
    if candidate.stage == "large_object_jtag":
        intended = intended_jtag_tuple(candidate, evidence)
        return [] if intended is None else [f"jtag:{intended[0]}:{intended[1]}:{intended[2]}"]
    if candidate.stage == "fragment_boundary_jtag":
        intended = intended_boundary_pair(candidate, evidence)
        return [] if intended is None else [f"boundary:{intended[0]}:{intended[1]}"]
    return {
        "ps_runtime": ["ps_functional"],
        "lane_fallback": ["ps_fault_fallback"],
        "queue_backpressure": ["ps_queue"],
        "abort_restart": ["ps_abort_restart"],
        "stationary": ["ps_stationary_qualified"],
    }.get(candidate.stage, [])


def _candidate_basic_pass(candidate: Candidate, evidence: RepositoryEvidence) -> bool:
    if not candidate.executed or candidate.marker != "PASS":
        return False
    common_errors, _provenance = common_runner_errors(candidate, evidence)
    if common_errors:
        return False
    process = _candidate_process(candidate)
    if process.get("returncode") != 0 or process.get("passed") is not True:
        return False
    after = candidate.data.get("shutdown_after")
    if not isinstance(after, dict) or after.get("returncode") != 0 or after.get("passed") is not True:
        return False
    if candidate.kind == "ps":
        post = candidate.data.get("postprocess")
        if not isinstance(post, dict) or post.get("passed") is not True:
            return False
        if candidate.stage == "stationary" and not stationary_is_qualified(candidate):
            return False
        provenance_count = len(evidence.provenance_rows)
        try:
            if candidate.stage == "ps_runtime":
                runtime, boundary = validate_ps_functional(candidate, evidence)
                return runtime.status == boundary.status == "PASS"
            if candidate.stage in {"lane_fallback", "abort_restart", "queue_backpressure"}:
                return validate_ps_mode(candidate, evidence, candidate.stage).status == "PASS"
            if candidate.stage == "stationary":
                stationary, calibration, metrics = stationary_results(candidate, evidence)
                return stationary.status == calibration.status == metrics.status == "PASS"
        finally:
            del evidence.provenance_rows[provenance_count:]
    if candidate.kind == "jtag" and candidate.stage in {"p6_frame_regression", "fragment_boundary_jtag", "large_object_jtag"}:
        semantic_p6 = markers(candidate).get("P7_P6_FRAME_REGRESSION") == "PASS"
        backend = candidate.data.get("backend_parse")
        if not semantic_p6 and (not isinstance(backend, dict) or backend.get("passed") is not True or backend.get("raw_log_bound_to_this_hardware_process") is not True):
            return False
        if not semantic_p6:
            linked, _parse_path, link_errors = linked_backend_parse(candidate, evidence)
            if link_errors:
                return False
            parsed = linked.get("parse", {}) if isinstance(linked, dict) else {}
            if candidate.stage == "p6_frame_regression":
                fragments = parsed.get("fragments", [])
                if int(parsed.get("fragment_count", -1)) < 10 or not isinstance(fragments, list) or len(fragments) != int(parsed.get("fragment_count", -1)):
                    return False
            elif candidate.stage == "fragment_boundary_jtag":
                intended = intended_boundary_pair(candidate, evidence)
                if intended is None or (int(parsed.get("object_length", -1)), str(parsed.get("lane_policy", ""))) != intended:
                    return False
            elif candidate.stage == "large_object_jtag":
                intended = intended_jtag_tuple(candidate, evidence)
                manifest = linked.get("manifest", {}) if isinstance(linked, dict) else {}
                observed = (
                    int(parsed.get("object_length", -1)),
                    str(parsed.get("lane_policy", "")),
                    pattern_from_manifest(manifest, str(candidate.data.get("stage_name", ""))),
                )
                metric_errors, _row = validate_large_jtag_metrics(candidate, parsed)
                if intended is None or observed != intended or metric_errors:
                    return False
        else:
            provenance_count = len(evidence.provenance_rows)
            try:
                if validate_p6_regression(candidate, evidence).status != "PASS":
                    return False
            finally:
                del evidence.provenance_rows[provenance_count:]
    if candidate.stage == "safe_idle":
        provenance_count = len(evidence.provenance_rows)
        try:
            return validate_safe_idle(candidate, evidence).status == "PASS"
        finally:
            del evidence.provenance_rows[provenance_count:]
    return True


def _ledger_shutdown(candidate: Candidate, which: str, evidence: RepositoryEvidence) -> dict[str, Any]:
    block = candidate.data.get(f"shutdown_{which}")
    if not isinstance(block, dict):
        return {"present": False}
    result_path = resolve_reference(block.get("result_file"), document=candidate.path, repo_root=evidence.repo_root)
    if result_path is None:
        result_path = candidate.path.parent / (f"shutdown_{which}_result.txt" if candidate.kind == "ps" else f"p7_shutdown_{which}_result.txt")
    stdout_path = resolve_reference(block.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root)
    result_markers, result_duplicates = parse_marker_text(marker_text(result_path))
    stdout_markers, stdout_duplicates = parse_marker_text(marker_text(stdout_path))
    tfdu_value = result_markers.get("TFDU_SHUTDOWN_PROGRAMMED", stdout_markers.get("TFDU_SHUTDOWN_PROGRAMMED", ""))
    shutdown_exit = result_markers.get("SHUTDOWN_EXIT", stdout_markers.get("SHUTDOWN_EXIT"))
    return {
        "present": True,
        "returncode": block.get("returncode"),
        "passed": block.get("passed"),
        "attempted": block.get("attempted", True),
        "result_file": _hash_record(result_path) if result_path.is_file() else {"path": str(result_path), "missing": True},
        "stdout_file": _hash_record(stdout_path) if stdout_path is not None and stdout_path.is_file() else {"path": str(stdout_path or "MISSING"), "missing": True},
        "tfdu_shutdown_marker": bool(tfdu_value),
        "shutdown_exit_zero_marker": shutdown_exit == "0",
        "p7_shutdown_result_pass": result_markers.get("P7_SHUTDOWN_RESULT") == "PASS",
        "result_marker_duplicates": sorted(set(result_duplicates)),
        "stdout_marker_duplicates": sorted(set(stdout_duplicates)),
    }


def offline_checkpoint_errors(
    payload: Mapping[str, Any],
    *,
    checkpoint_path: Path,
    repo_root: Path,
    expected_commit: str,
) -> list[str]:
    errors: list[str] = []
    append_error(errors, payload.get("P7_OFFLINE_GATE") == "PASS", "offline checkpoint is not P7_OFFLINE_GATE=PASS")
    append_error(errors, payload.get("hardware_actions_executed") is False and payload.get("NO_HARDWARE_ACTIONS_EXECUTED") is True, "offline checkpoint violates the no-hardware boundary")
    append_error(errors, payload.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", "offline checkpoint promoted hardware acceptance")
    checks = payload.get("checks")
    append_error(errors, isinstance(checks, dict), "offline checkpoint checks object missing")
    if isinstance(checks, dict):
        append_error(errors, checks.get("P7_CLEAN_SOURCE_CHECKPOINT") is True, "offline checkpoint clean-source check is not PASS")
        append_error(errors, checks.get("P7_CHECKPOINT_INPUT_HASHES") is True, "offline checkpoint input-hash check is not PASS")
    source_commit = str(payload.get("source_commit", "")).lower()
    append_error(errors, COMMIT_RE.fullmatch(source_commit) is not None, "offline checkpoint source_commit is missing/malformed")
    append_error(errors, source_commit == expected_commit.lower(), "offline checkpoint source_commit does not match the frozen ledger commit")
    append_error(errors, payload.get("dirty_worktree") is False, "offline checkpoint does not prove dirty_worktree=false")
    tree_digest = str(payload.get("source_tree_listing_sha256", "")).lower()
    append_error(errors, SHA256_RE.fullmatch(tree_digest) is not None, "offline checkpoint source-tree listing SHA256 missing/malformed")
    if (repo_root / ".git").exists() and SHA256_RE.fullmatch(tree_digest):
        try:
            tree = subprocess.run(
                ["git", "ls-tree", "-r", "--full-tree", source_commit],
                cwd=repo_root,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"unable to recompute offline source-tree listing: {exc}")
        else:
            append_error(errors, tree.returncode == 0, "unable to recompute offline source-tree listing")
            if tree.returncode == 0:
                actual_tree_digest = hashlib.sha256(tree.stdout.encode("utf-8")).hexdigest()
                append_error(errors, actual_tree_digest == tree_digest, "offline checkpoint source-tree listing SHA256 mismatch")
    source_hashes = payload.get("checkpoint_input_hashes")
    if not isinstance(source_hashes, dict):
        return errors + ["offline checkpoint checkpoint_input_hashes object missing"]
    append_error(errors, payload.get("checkpoint_input_count") == len(source_hashes), "offline checkpoint input-hash count mismatch")
    append_error(errors, bool(source_hashes), "offline checkpoint input-hash map is empty")
    append_error(errors, set(OFFLINE_CRITICAL_SOURCES) <= set(source_hashes), "offline checkpoint omits one or more critical P7 source hashes")
    root = repo_root.resolve(strict=False)
    for name, expected_value in source_hashes.items():
        expected = str(expected_value).lower()
        path = (root / str(name)).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"offline checkpoint source path escapes repository: {name}")
            continue
        append_error(errors, path.is_file(), f"offline checkpoint source file missing: {name}")
        append_error(errors, SHA256_RE.fullmatch(expected) is not None, f"offline checkpoint source hash malformed: {name}")
        if path.is_file() and SHA256_RE.fullmatch(expected):
            append_error(errors, sha256_file(path) == expected, f"offline checkpoint source changed after freeze: {name}")
    return errors


def generate_sequence_ledger(
    evidence: RepositoryEvidence,
    *,
    ledger_path: Path,
    offline_checkpoint_summary: Path,
    offline_checkpoint_sha256: str,
    offline_checkpoint_commit: str,
) -> dict[str, Any]:
    if not offline_checkpoint_summary.is_file():
        raise ValueError(f"offline checkpoint summary missing: {offline_checkpoint_summary}")
    actual_offline_sha = sha256_file(offline_checkpoint_summary)
    if not SHA256_RE.fullmatch(offline_checkpoint_sha256.lower()) or actual_offline_sha != offline_checkpoint_sha256.lower():
        raise ValueError("offline checkpoint summary SHA256 mismatch")
    if not COMMIT_RE.fullmatch(offline_checkpoint_commit.lower()):
        raise ValueError("offline checkpoint commit must be exactly 40 hex characters")
    if (evidence.repo_root / ".git").exists():
        actual_head = current_repository_head(evidence)
        if actual_head is None or actual_head != offline_checkpoint_commit.lower():
            raise ValueError("offline checkpoint commit does not match current repository HEAD")
    offline_payload = json.loads(offline_checkpoint_summary.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(offline_payload, dict):
        raise ValueError("offline checkpoint summary is not a JSON object")
    checkpoint_errors = offline_checkpoint_errors(
        offline_payload,
        checkpoint_path=offline_checkpoint_summary,
        repo_root=evidence.repo_root,
        expected_commit=offline_checkpoint_commit,
    )
    if checkpoint_errors:
        raise ValueError("; ".join(checkpoint_errors))

    def start_key(candidate: Candidate) -> tuple[float, str]:
        wrapper_start, _wrapper_end = authorized_execution_boundaries(candidate)
        process = _candidate_process(candidate)
        return (parse_time(wrapper_start, parse_time(process.get("started_at_utc"), candidate.timestamp)), str(candidate.path))

    orphan_errors = orphan_hardware_footprint_errors(evidence)
    if orphan_errors:
        raise ValueError("; ".join(orphan_errors))
    executed = sorted((item for item in evidence.candidates if candidate_has_hardware_footprint(item)), key=start_key)
    runs: list[dict[str, Any]] = []
    for sequence, candidate in enumerate(executed, 1):
        process = _candidate_process(candidate)
        raw_path = _candidate_raw_path(candidate)
        event_path = _candidate_event_path(candidate)
        attempted = _candidate_attempted_coverage(candidate, evidence) if _candidate_mutation_attempted(candidate) else []
        basic_pass = _candidate_basic_pass(candidate, evidence)
        source = candidate.data.get("safety_validation", {}).get("source_commit_requested", "")
        wrapper_start, wrapper_end = authorized_execution_boundaries(candidate)
        runs.append(
            {
                "sequence": sequence,
                "risk_index": _candidate_risk(candidate, evidence),
                "stage": candidate.stage,
                "kind": candidate.kind,
                "mode": candidate.data.get("mode"),
                "stage_name": candidate.data.get("stage_name"),
                "attempted_coverage_keys": attempted,
                "coverage_keys": attempted if basic_pass else [],
                "result": "PASS" if basic_pass else "FAIL",
                "runner_result": candidate.marker,
                "source_commit": str(source).lower(),
                "started_at_utc": wrapper_start,
                "ended_at_utc": wrapper_end,
                "candidate_child_started_at_utc": process.get("started_at_utc"),
                "candidate_child_ended_at_utc": process.get("ended_at_utc"),
                "elapsed_seconds": process.get("elapsed_seconds"),
                "time_source": "authorized_wrapper_event_utc_boundaries_plus_candidate_child_host_monotonic_elapsed",
                "argv": process.get("argv", []),
                "argv_available": isinstance(process.get("argv"), list) and bool(process.get("argv")),
                "returncode": process.get("returncode"),
                "summary_file": _hash_record(candidate.path),
                "raw_log": _hash_record(raw_path) if raw_path.is_file() else {"path": str(raw_path), "missing": True},
                "event_log": _hash_record(event_path) if event_path.is_file() else {"path": str(event_path), "missing": True},
                "hardware_execution_lock": candidate.data.get("hardware_execution_lock"),
                "shutdown_required": _candidate_mutation_attempted(candidate),
                "shutdown_before": _ledger_shutdown(candidate, "before", evidence),
                "shutdown_after": _ledger_shutdown(candidate, "after", evidence),
            }
        )
    payload = {
        "schema": "rf-comm-p7-run-sequence-ledger-v1",
        "generated_at_utc": utc_now(),
        "hardware_actions_executed_by_generator": False,
        "risk_order": [
            "offline_checkpoint",
            "safe_idle",
            "p6_frame_regression",
            "fragment_boundary_jtag",
            "large_object_jtag_4k",
            "large_object_jtag_64k",
            "large_object_jtag_1mib",
            "ps_functional",
            "fault_fallback",
            "abort_restart",
            "queue_backpressure",
            "stationary_qualified_last",
        ],
        "offline_checkpoint": {
            "result": "PASS",
            "source_commit": offline_checkpoint_commit.lower(),
            "generated_at_utc": offline_payload.get("generated_at_utc"),
            "summary_file": _hash_record(offline_checkpoint_summary),
        },
        "run_count": len(runs),
        "runs": runs,
    }
    atomic_write_json(ledger_path, payload)
    return payload


def validate_sequence_ledger(evidence: RepositoryEvidence) -> tuple[str, list[str], dict[str, Any]]:
    ledger_path = evidence.hardware_root / "p7_run_sequence_ledger.json"
    executed = [item for item in evidence.candidates if candidate_has_hardware_footprint(item)]
    footprint_errors = orphan_hardware_footprint_errors(evidence)
    if not ledger_path.is_file():
        if executed or footprint_errors:
            return "FAIL", footprint_errors + ["p7_run_sequence_ledger.json is missing after hardware execution"], {"run_count": len(executed)}
        return "PENDING_HW", [], {"run_count": 0}
    errors: list[str] = []
    errors.extend(footprint_errors)
    try:
        payload = json.loads(ledger_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return "FAIL", [f"run sequence ledger invalid: {exc}"], {}
    append_error(errors, isinstance(payload, dict) and payload.get("schema") == "rf-comm-p7-run-sequence-ledger-v1", "run sequence ledger schema mismatch")
    append_error(errors, payload.get("hardware_actions_executed_by_generator") is False, "run sequence ledger generator claims hardware actions")
    offline = payload.get("offline_checkpoint")
    if not isinstance(offline, dict):
        errors.append("run sequence offline checkpoint missing")
        offline = {}
    append_error(errors, offline.get("result") == "PASS", "run sequence offline checkpoint is not PASS")
    offline_record_errors, offline_record = verify_hash_record(
        "run sequence offline checkpoint", offline.get("summary_file"), document=ledger_path, repo_root=evidence.repo_root, expected_required=False
    )
    errors.extend(offline_record_errors)
    offline_payload: dict[str, Any] = {}
    if offline_record:
        try:
            offline_payload = json.loads(Path(offline_record["path"]).read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"run sequence offline checkpoint JSON invalid: {exc}")
    offline_commit = str(offline.get("source_commit", "")).lower()
    append_error(errors, COMMIT_RE.fullmatch(offline_commit) is not None, "run sequence offline checkpoint commit malformed")
    if offline_record and COMMIT_RE.fullmatch(offline_commit):
        errors.extend(
            offline_checkpoint_errors(
                offline_payload,
                checkpoint_path=Path(offline_record["path"]),
                repo_root=evidence.repo_root,
                expected_commit=offline_commit,
            )
        )

    runs = payload.get("runs")
    if not isinstance(runs, list):
        return "FAIL", errors + ["run sequence runs list missing"], {}
    append_error(errors, payload.get("run_count") == len(runs), "run sequence run_count mismatch")
    append_error(errors, [item.get("sequence") for item in runs if isinstance(item, dict)] == list(range(1, len(runs) + 1)), "run sequence numbers are not contiguous")
    candidates_by_path = {item.path.resolve(strict=False): item for item in executed}
    seen_summaries: set[Path] = set()
    ordered_starts: list[float] = []
    ordered_intervals: list[tuple[float, float]] = []
    passed_keys: set[str] = set()
    all_required_keys = set().union(*(keys for _risk, keys in SEQUENCE_REQUIRED_GROUPS))
    for index, run in enumerate(runs):
        if not isinstance(run, dict):
            errors.append(f"run sequence entry {index} is malformed")
            continue
        summary_errors, summary_record = verify_hash_record(
            f"run sequence entry {index} summary", run.get("summary_file"), document=ledger_path, repo_root=evidence.repo_root, expected_required=False
        )
        errors.extend(summary_errors)
        candidate = candidates_by_path.get(Path(summary_record["path"]).resolve(strict=False)) if summary_record else None
        if candidate is None:
            errors.append(f"run sequence entry {index} does not bind an executed wrapper summary")
            continue
        append_error(errors, candidate.path not in seen_summaries, f"run sequence entry {index} duplicates a summary")
        seen_summaries.add(candidate.path)
        process = _candidate_process(candidate)
        wrapper_start, wrapper_end = authorized_execution_boundaries(candidate)
        mutation_attempted = _candidate_mutation_attempted(candidate)
        expected_attempted = _candidate_attempted_coverage(candidate, evidence) if mutation_attempted else []
        expected_pass = _candidate_basic_pass(candidate, evidence)
        append_error(errors, run.get("stage") == candidate.stage and run.get("kind") == candidate.kind, f"run sequence entry {index} stage/kind mismatch")
        append_error(errors, run.get("risk_index") == _candidate_risk(candidate, evidence), f"run sequence entry {index} risk index mismatch")
        append_error(errors, run.get("attempted_coverage_keys") == expected_attempted, f"run sequence entry {index} attempted coverage mismatch")
        append_error(errors, run.get("coverage_keys") == (expected_attempted if expected_pass else []), f"run sequence entry {index} PASS coverage mismatch")
        append_error(errors, run.get("result") == ("PASS" if expected_pass else "FAIL"), f"run sequence entry {index} result mismatch")
        append_error(errors, run.get("returncode") == process.get("returncode"), f"run sequence entry {index} returncode mismatch")
        append_error(errors, run.get("argv_available") is True and isinstance(run.get("argv"), list) and run.get("argv") == process.get("argv") and bool(run.get("argv")), f"run sequence entry {index} exact argv missing/mismatch")
        append_error(errors, run.get("started_at_utc") == wrapper_start and run.get("ended_at_utc") == wrapper_end, f"run sequence entry {index} wrapper UTC boundaries missing/mismatch")
        append_error(errors, run.get("candidate_child_started_at_utc") == process.get("started_at_utc") and run.get("candidate_child_ended_at_utc") == process.get("ended_at_utc"), f"run sequence entry {index} candidate child UTC boundaries missing/mismatch")
        start = parse_time(run.get("started_at_utc"), float("nan"))
        end = parse_time(run.get("ended_at_utc"), float("nan"))
        append_error(errors, start == start and end == end and end >= start, f"run sequence entry {index} UTC boundaries invalid")
        if start == start:
            ordered_starts.append(start)
        if start == start and end == end:
            ordered_intervals.append((start, end))
        append_error(errors, run.get("elapsed_seconds") == process.get("elapsed_seconds") and isinstance(run.get("elapsed_seconds"), (int, float)) and float(run.get("elapsed_seconds")) >= 0, f"run sequence entry {index} monotonic elapsed time missing/mismatch")
        lock_errors, lock_record = hardware_execution_lock_errors(candidate, evidence)
        errors.extend(f"run sequence entry {index}: {item}" for item in lock_errors)
        append_error(errors, run.get("hardware_execution_lock") == lock_record, f"run sequence entry {index} hardware execution lock record mismatch")
        lock_owner = lock_record.get("owner", {}) if isinstance(lock_record, dict) else {}
        lock_acquired = parse_time(lock_owner.get("acquired_at_utc") if isinstance(lock_owner, dict) else None, float("nan"))
        append_error(errors, lock_acquired == lock_acquired and start == start and lock_acquired <= start, f"run sequence entry {index} lock was not acquired before authorized execution")
        child_keys = (
            ("preflight", "preflight") if candidate.kind == "ps" else ("preflight_process", "preflight"),
            ("ps_process", "candidate") if candidate.kind == "ps" else ("stage_process", "candidate"),
            ("shutdown_before", "shutdown-before"),
            ("shutdown_after", "shutdown-after"),
        )
        for block_key, label in child_keys:
            block = candidate.data.get(block_key)
            if isinstance(block, dict):
                append_error(errors, block.get("process_tree_reaped") is True, f"run sequence entry {index} {label} child tree was not reaped")
        candidate_key = "ps_process" if candidate.kind == "ps" else "stage_process"
        if isinstance(candidate.data.get(candidate_key), dict):
            errors.extend(f"run sequence entry {index}: {item}" for item in authorized_event_errors(candidate, evidence))
        source = str(candidate.data.get("safety_validation", {}).get("source_commit_requested", "")).lower()
        append_error(errors, run.get("source_commit") == source == offline_commit, f"run sequence entry {index} source/offline commit mismatch")
        raw_errors, _raw_record = verify_hash_record(
            f"run sequence entry {index} raw log", run.get("raw_log"), document=ledger_path, repo_root=evidence.repo_root, expected_required=False
        )
        errors.extend(raw_errors)
        event_errors, _event_record = verify_hash_record(
            f"run sequence entry {index} event log", run.get("event_log"), document=ledger_path, repo_root=evidence.repo_root, expected_required=False
        )
        errors.extend(event_errors)
        append_error(errors, run.get("shutdown_required") is mutation_attempted, f"run sequence entry {index} shutdown-required classification mismatch")
        for which in ("before", "after"):
            shutdown = run.get(f"shutdown_{which}")
            if not mutation_attempted:
                append_error(errors, isinstance(shutdown, dict) and shutdown.get("present") is False, f"run sequence entry {index} read-only preflight unexpectedly records shutdown-{which}")
                continue
            require_clean = which == "after" or _candidate_programmed(candidate) or expected_pass
            if require_clean:
                append_error(errors, isinstance(shutdown, dict) and shutdown.get("returncode") == 0 and shutdown.get("passed") is True, f"run sequence entry {index} shutdown-{which} rc/PASS invalid")
            else:
                append_error(errors, isinstance(shutdown, dict) and shutdown.get("present") is True, f"run sequence entry {index} shutdown-before attempt record missing")
            if isinstance(shutdown, dict):
                append_error(errors, shutdown.get("result_marker_duplicates") == [], f"run sequence entry {index} shutdown-{which} result has duplicate markers")
                append_error(errors, shutdown.get("stdout_marker_duplicates") == [], f"run sequence entry {index} shutdown-{which} stdout has duplicate markers")
                if require_clean:
                    append_error(errors, shutdown.get("tfdu_shutdown_marker") is True or shutdown.get("shutdown_exit_zero_marker") is True, f"run sequence entry {index} shutdown-{which} marker missing")
                    append_error(errors, shutdown.get("p7_shutdown_result_pass") is True, f"run sequence entry {index} P7 shutdown-{which} result missing")
                for field in ("result_file", "stdout_file"):
                    if shutdown.get(field, {}).get("missing") is True and not require_clean:
                        continue
                    file_errors, _record = verify_hash_record(
                        f"run sequence entry {index} shutdown-{which} {field}", shutdown.get(field), document=ledger_path, repo_root=evidence.repo_root, expected_required=False
                    )
                    errors.extend(file_errors)

        next_incomplete_risk = next((risk for risk, keys in SEQUENCE_REQUIRED_GROUPS if not keys <= passed_keys), None)
        risk = int(run.get("risk_index", 999))
        if next_incomplete_risk is not None and risk > next_incomplete_risk:
            errors.append(f"run sequence entry {index} advanced to risk {risk} before risk {next_incomplete_risk} passed")
        attempted_keys = set(str(item) for item in run.get("attempted_coverage_keys", []))
        coverage_keys = set(str(item) for item in run.get("coverage_keys", []))
        if run.get("result") == "PASS":
            passed_keys.update(coverage_keys)
        else:
            passed_keys.difference_update(attempted_keys)

    append_error(errors, seen_summaries == set(candidates_by_path), "run sequence ledger does not list every executed hardware summary exactly once")
    append_error(errors, ordered_starts == sorted(ordered_starts), "run sequence UTC start order is not chronological")
    append_error(
        errors,
        all(previous_end <= next_start for (_previous_start, previous_end), (next_start, _next_end) in zip(ordered_intervals, ordered_intervals[1:])),
        "run sequence contains overlapping hardware stages",
    )
    stationary_pass_indices = [
        index
        for index, run in enumerate(runs)
        if isinstance(run, dict) and "ps_stationary_qualified" in run.get("coverage_keys", [])
    ]
    append_error(errors, len(stationary_pass_indices) <= 1, "run sequence contains more than one qualified stationary PASS")
    stationary_launch_indices = [
        index
        for index, run in enumerate(runs)
        if isinstance(run, dict) and run.get("stage") == "stationary"
    ]
    append_error(errors, len(stationary_launch_indices) <= 1, "run sequence contains more than one final stationary launch intent")
    if stationary_pass_indices:
        append_error(errors, stationary_pass_indices[0] == len(runs) - 1, "qualified stationary PASS is not the final executed hardware stage")
    offline_time = parse_time(offline.get("generated_at_utc"), float("nan"))
    if ordered_starts:
        append_error(errors, offline_time == offline_time and offline_time <= ordered_starts[0], "offline checkpoint was not frozen before first hardware stage")
    # Missing coverage is not itself a ledger corruption; the corresponding
    # stage remains PENDING/FAIL elsewhere.  But the ledger must never invent a
    # key outside the declared risk model.
    append_error(errors, passed_keys <= all_required_keys, "run sequence contains undeclared PASS coverage keys")
    metrics = {
        "run_count": len(runs),
        "listed_executed_summaries": len(seen_summaries),
        "passed_coverage_keys": sorted(passed_keys),
        "ledger_sha256": sha256_file(ledger_path),
    }
    return ("PASS" if not errors else "FAIL"), errors, metrics


def decode_p7_descriptor(raw: bytes) -> dict[str, Any]:
    if len(raw) != 256:
        raise ValueError("descriptor must contain exactly 256 bytes")
    words = struct.unpack("<64I", raw)

    def digest_words(start: int) -> str:
        return b"".join(int(word).to_bytes(4, "big") for word in words[start : start + 8]).hex()

    return {
        "magic": words[0], "version": words[1], "command": words[2], "status": words[3],
        "session_epoch": words[4], "object_id": words[5], "object_length": words[8],
        "expected_crc32": words[9], "lane_policy": words[10], "max_retries": words[11],
        "unavailable_lane_mask": words[12], "unavailable_after_fragment": words[13],
        "abort_after_fragment": words[14], "trace_capacity": words[16], "error_code": words[17],
        "bytes_completed": words[18], "fragments_total": words[19], "fragments_completed": words[20],
        "output_crc32": words[21], "fragment_attempts": words[22], "fallback_count": words[23],
        "expected_sha256": digest_words(24), "input_sha256": digest_words(32), "output_sha256": digest_words(40),
        "p6_retry_count": words[48], "p6_retry_exhausted": words[49], "p6_tx_fail": words[50],
        "p6_crc_bad": words[51], "p6_payload_mismatch": words[52], "max_txd_high_cycles": words[53],
        "duty_violation_count": words[54], "lane0_fragments": words[55], "lane1_fragments": words[56],
        "replicated_fragments": words[57], "start_ticks": words[58] | (words[59] << 32),
        "end_ticks": words[60] | (words[61] << 32), "restart_count": words[62],
        "completion_sequence": words[63],
    }


def validate_stationary_trace_binaries(
    candidate: Candidate,
    post: Mapping[str, Any],
    trace_summary: Mapping[str, Any],
) -> tuple[list[str], list[int]]:
    errors: list[str] = []
    objects = {
        int(item.get("sequence", -1)): item
        for item in post.get("stationary_objects", [])
        if isinstance(item, dict)
    }
    cases = {
        int(item.get("slot", -1)): item.get("descriptor", {})
        for item in post.get("cases", [])
        if isinstance(item, dict) and isinstance(item.get("descriptor"), dict)
    }
    records = trace_summary.get("records")
    if not isinstance(records, list):
        return ["stationary trace binary record list missing"], []
    timing_records: list[dict[str, int]] = []
    fragment_latencies: list[int] = []
    fallback_lane0_to_lane1 = 0
    fallback_lane1_to_lane0 = 0
    for record_index, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"stationary trace binary record {record_index} is malformed")
            continue
        sequence = int(record.get("sequence", -1))
        terminal = objects.get(sequence)
        if not isinstance(terminal, dict):
            errors.append(f"stationary trace binary sequence has no terminal ledger row: {sequence}")
            continue
        descriptor = cases.get(int(terminal.get("slot", -1)))
        if not isinstance(descriptor, dict):
            errors.append(f"stationary trace binary sequence has no slot policy descriptor: {sequence}")
            continue
        append_error(errors, int(record.get("slot", -1)) == int(terminal.get("slot", -2)), f"stationary trace summary slot mismatch: {sequence}")
        for key in ("session_epoch", "object_id"):
            append_error(errors, int(record.get(key, -1)) == int(terminal.get(key, -2)), f"stationary trace summary identity mismatch: {sequence}/{key}")

        descriptor_record = record.get("descriptor_file")
        descriptor_path = resolve_reference(
            descriptor_record.get("path") if isinstance(descriptor_record, dict) else None,
            document=candidate.path,
            repo_root=candidate.path.parent,
        )
        output_record = record.get("output_file")
        output_path = resolve_reference(
            output_record.get("path") if isinstance(output_record, dict) else None,
            document=candidate.path,
            repo_root=candidate.path.parent,
        )
        decoded: dict[str, Any] = {}
        if descriptor_path is None or not descriptor_path.is_file():
            errors.append(f"stationary descriptor binary file missing: {sequence}")
        else:
            try:
                decoded = decode_p7_descriptor(descriptor_path.read_bytes())
            except (OSError, ValueError, struct.error) as exc:
                errors.append(f"stationary descriptor binary invalid: {sequence}: {exc}")
        if decoded:
            descriptor_expected = {
                "magic": 0x53443750,
                "version": 1,
                "command": 1,
                "status": 3,
                "error_code": 0,
                "session_epoch": int(terminal.get("session_epoch", -1)),
                "object_id": int(terminal.get("object_id", -1)),
                "object_length": int(terminal.get("bytes_completed", -1)),
                "expected_crc32": int(descriptor.get("expected_crc32", -1)),
                "lane_policy": int(descriptor.get("lane_policy", -1)),
                "unavailable_lane_mask": int(descriptor.get("unavailable_lane_mask", -1)),
                "unavailable_after_fragment": int(descriptor.get("unavailable_after_fragment", -1)),
                "bytes_completed": int(terminal.get("bytes_completed", -1)),
                "fragments_total": int(terminal.get("fragments_total", -1)),
                "fragments_completed": int(terminal.get("fragments_completed", -1)),
                "fragment_attempts": int(terminal.get("fragment_attempts", -1)),
                "fallback_count": int(terminal.get("fallback_count", -1)),
                "p6_retry_count": int(terminal.get("p6_retry_count", -1)),
                "p6_retry_exhausted": int(terminal.get("p6_retry_exhausted", -1)),
                "p6_tx_fail": int(terminal.get("p6_tx_fail", -1)),
                "p6_crc_bad": int(terminal.get("p6_crc_bad", -1)),
                "p6_payload_mismatch": int(terminal.get("p6_payload_mismatch", -1)),
                "max_txd_high_cycles": int(terminal.get("max_txd_high_cycles", -1)),
                "duty_violation_count": int(terminal.get("duty_violations", -1)),
                "lane0_fragments": int(terminal.get("lane0_fragments", -1)),
                "lane1_fragments": int(terminal.get("lane1_fragments", -1)),
                "replicated_fragments": int(terminal.get("replicated_fragments", -1)),
                "start_ticks": int(terminal.get("start_ticks", -1)),
                "end_ticks": int(terminal.get("end_ticks", -1)),
                "completion_sequence": sequence,
            }
            for key, expected in descriptor_expected.items():
                append_error(errors, decoded.get(key) == expected, f"stationary descriptor/terminal mismatch: {sequence}/{key}")
            expected_sha = str(terminal.get("output_sha256", "")).lower()
            for key in ("expected_sha256", "input_sha256", "output_sha256"):
                append_error(errors, decoded.get(key) == expected_sha, f"stationary descriptor SHA256 mismatch: {sequence}/{key}")
            append_error(errors, decoded.get("output_crc32") == decoded.get("expected_crc32"), f"stationary descriptor CRC32 mismatch: {sequence}")
            append_error(errors, decoded.get("trace_capacity") == int(terminal.get("fragments_total", -1)), f"stationary descriptor trace capacity mismatch: {sequence}")
        if output_path is None or not output_path.is_file():
            errors.append(f"stationary output binary file missing: {sequence}")
        else:
            output = output_path.read_bytes()
            expected_sha = str(terminal.get("output_sha256", "")).lower()
            append_error(errors, len(output) == int(terminal.get("bytes_completed", -1)), f"stationary output byte length mismatch: {sequence}")
            append_error(errors, hashlib.sha256(output).hexdigest() == expected_sha, f"stationary output SHA256 differs from terminal ledger: {sequence}")
            append_error(errors, hashlib.sha256(output).hexdigest() == str(descriptor.get("expected_sha256", "")).lower(), f"stationary output SHA256 differs from slot input identity: {sequence}")
            append_error(errors, (zlib.crc32(output) & 0xFFFFFFFF) == int(descriptor.get("expected_crc32", -1)), f"stationary output CRC32 differs from slot input identity: {sequence}")
        trace_file = record.get("trace_file")
        trace_path = resolve_reference(
            trace_file.get("path") if isinstance(trace_file, dict) else None,
            document=candidate.path,
            repo_root=candidate.path.parent,
        )
        if trace_path is None or not trace_path.is_file():
            errors.append(f"stationary trace binary file missing: {sequence}")
            continue
        raw = trace_path.read_bytes()
        expected_fragments = int(terminal.get("fragments_completed", -1))
        append_error(errors, len(raw) == expected_fragments * 64, f"stationary trace binary size mismatch: {sequence}")
        parsed: list[dict[str, int]] = []
        for offset in range(0, len(raw) - (len(raw) % 64), 64):
            words = struct.unpack_from("<16I", raw, offset)
            if words[0] == 0:
                continue
            parsed.append(
                {
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
            )
        append_error(errors, len(parsed) == expected_fragments, f"stationary trace binary fragment count mismatch: {sequence}")
        policy = int(descriptor.get("lane_policy", -1))
        unavailable = int(descriptor.get("unavailable_lane_mask", 0))
        unavailable_after = int(descriptor.get("unavailable_after_fragment", 0))
        lane0 = lane1 = replicated = attempts = retries = retry_exhausted = tx_fail = redirected = 0
        directions: set[str] = set()
        previous_end = 0
        for expected_index, item in enumerate(parsed):
            append_error(errors, item["magic"] == P7_TRACE_MAGIC, f"stationary trace magic mismatch: {sequence}/{expected_index}")
            append_error(errors, item["session_epoch"] == int(terminal.get("session_epoch", -1)), f"stationary trace session mismatch: {sequence}/{expected_index}")
            append_error(errors, item["object_id"] == int(terminal.get("object_id", -1)), f"stationary trace object mismatch: {sequence}/{expected_index}")
            append_error(errors, item["fragment_index"] == expected_index and item["fragment_count"] == expected_fragments, f"stationary trace geometry/order mismatch: {sequence}/{expected_index}")
            if policy == 1:
                expected_lane = 1
            elif policy == 2:
                expected_lane = 2
            elif policy == 4:
                expected_lane = 3
            else:
                expected_lane = 1 if expected_index % 2 == 0 else 2
                if expected_index >= unavailable_after and expected_lane & unavailable:
                    if expected_lane == 1:
                        expected_lane = 2
                        directions.add("lane0_to_lane1")
                    else:
                        expected_lane = 1
                        directions.add("lane1_to_lane0")
                    redirected += 1
            append_error(errors, item["lane_mask"] == expected_lane, f"stationary trace lane policy mismatch: {sequence}/{expected_index}")
            append_error(errors, item["attempt_count"] == 1 and item["result"] == 1 and item["error_code"] == 0, f"stationary trace attempt/result mismatch: {sequence}/{expected_index}")
            append_error(errors, item["p6_retry_exhausted"] == item["p6_tx_fail"] == item["p6_error_code"] == 0, f"stationary trace P6 failure: {sequence}/{expected_index}")
            append_error(errors, int(terminal.get("start_ticks", 0)) <= item["start_ticks"] < item["end_ticks"] <= int(terminal.get("end_ticks", 0)), f"stationary trace timing escapes object interval: {sequence}/{expected_index}")
            append_error(errors, previous_end == 0 or item["start_ticks"] >= previous_end, f"stationary trace timing overlaps/regresses: {sequence}/{expected_index}")
            previous_end = item["end_ticks"]
            lane0 += int(bool(item["lane_mask"] & 1))
            lane1 += int(bool(item["lane_mask"] & 2))
            replicated += int(item["lane_mask"] == 3)
            attempts += item["attempt_count"]
            retries += item["p6_retry_count"]
            retry_exhausted += item["p6_retry_exhausted"]
            tx_fail += item["p6_tx_fail"]
            latency = item["end_ticks"] - item["start_ticks"]
            fragment_latencies.append(latency)
            timing_records.append(
                {
                    "sequence": sequence,
                    "fragment_index": expected_index,
                    "start_ticks": item["start_ticks"],
                    "end_ticks": item["end_ticks"],
                    "latency_ticks": latency,
                }
            )
        expected_counters = {
            "fragments_completed": len(parsed),
            "fragment_attempts": attempts,
            "lane0_fragments": lane0,
            "lane1_fragments": lane1,
            "replicated_fragments": replicated,
            "fallback_count": len(directions),
            "p6_retry_count": retries,
            "p6_retry_exhausted": retry_exhausted,
            "p6_tx_fail": tx_fail,
        }
        for key, expected in expected_counters.items():
            append_error(errors, int(terminal.get(key, -1)) == expected, f"stationary trace/terminal counter mismatch: {sequence}/{key}")
        append_error(errors, int(record.get("fragment_count", -1)) == len(parsed), f"stationary trace summary fragment count mismatch: {sequence}")
        append_error(errors, int(record.get("fragment_attempts", -1)) == attempts, f"stationary trace summary attempt count mismatch: {sequence}")
        append_error(errors, int(record.get("fallback_count", -1)) == len(directions), f"stationary trace summary fallback event mismatch: {sequence}")
        append_error(errors, int(record.get("redirected_fragments", -1)) == redirected, f"stationary trace summary redirected fragment mismatch: {sequence}")
        fallback_lane0_to_lane1 += int("lane0_to_lane1" in directions)
        fallback_lane1_to_lane0 += int("lane1_to_lane0" in directions)
    append_error(errors, trace_summary.get("fragment_timing_records") == timing_records, "stationary trace timing record ledger does not match raw trace binaries")
    append_error(errors, int(trace_summary.get("fragment_latency_samples", -1)) == len(fragment_latencies), "stationary raw trace latency sample count mismatch")
    append_error(errors, int(trace_summary.get("fallback_lane0_to_lane1", -1)) == fallback_lane0_to_lane1, "stationary raw trace lane0-to-lane1 fallback count mismatch")
    append_error(errors, int(trace_summary.get("fallback_lane1_to_lane0", -1)) == fallback_lane1_to_lane0, "stationary raw trace lane1-to-lane0 fallback count mismatch")
    return errors, fragment_latencies


def derive_metrics(candidate: Candidate, post: Mapping[str, Any], inherited_errors: Sequence[str]) -> StageResult:
    mailbox = post.get("mailbox", {}) if isinstance(post, dict) else {}
    objects = [item for item in post.get("stationary_objects", []) if isinstance(item, dict)] if isinstance(post, dict) else []
    trace = post.get("stationary_trace_validation") if isinstance(post, dict) else None
    metrics_value = post.get("application_metrics") if isinstance(post, dict) else None
    errors = list(inherited_errors)
    if not isinstance(trace, dict):
        errors.append("stationary_trace_validation object missing")
        trace = {}
    if not isinstance(metrics_value, dict):
        errors.append("application_metrics object missing")
        metrics: dict[str, Any] = {}
    else:
        metrics = dict(metrics_value)
    fragment_trace_errors, fragment_latency_ticks = validate_stationary_trace_binaries(candidate, post, trace)
    errors.extend(fragment_trace_errors)
    required_fields = (
        "objects_requested", "objects_completed", "objects_failed",
        "fragments_generated", "fragments_submitted", "fragments_completed",
        "fragments_retried", "fragments_duplicated", "fragments_rejected",
        "fragments_out_of_order", "bytes_requested", "bytes_completed",
        "whole_object_crc_failures", "sha256_mismatches", "lane0_fragments",
        "lane1_fragments", "replicated_fragments", "fallback_lane0_to_lane1",
        "fallback_lane1_to_lane0", "queue_high_watermark", "backpressure_events",
        "host_to_ps_bytes_per_sec", "application_goodput_bps",
        "fragment_latency_min_us", "fragment_latency_mean_us", "fragment_latency_p50_us",
        "fragment_latency_p95_us", "fragment_latency_p99_us", "fragment_latency_max_us",
        "object_latency_min_ms", "object_latency_mean_ms", "object_latency_p95_ms",
        "object_latency_max_ms", "p6_retry_count", "p6_retry_exhausted", "p6_tx_fail",
        "p6_crc_bad", "p6_payload_mismatch", "max_txd_high_cycles",
        "duty_violation_count", "shutdown_result",
    )
    for key in required_fields:
        append_error(errors, key in metrics, f"application metric missing: {key}")
    append_error(errors, metrics.get("validated") is True, "application metrics validated flag is not true")
    append_error(errors, metrics.get("failures") == [], "application metrics failures are nonempty")
    append_error(errors, trace.get("passed") is True and trace.get("failures") == [], "stationary trace validation is not clean PASS")
    expected_objects = len(objects)
    append_error(errors, int(trace.get("terminal_bundles_expected", -1)) == expected_objects, "trace expected terminal bundle count mismatch")
    append_error(errors, int(trace.get("terminal_bundle_markers_observed", -1)) == expected_objects, "trace terminal bundle marker count mismatch")
    append_error(errors, int(trace.get("terminal_bundles_validated", -1)) == expected_objects, "trace validated terminal bundle count mismatch")
    append_error(errors, int(trace.get("artifact_files_expected", -1)) == 3 * expected_objects, "trace expected artifact file count mismatch")
    append_error(errors, int(trace.get("files_observed", -1)) == 3 * expected_objects, "trace observed artifact file count mismatch")
    append_error(errors, int(trace.get("fragment_trace_entries", -1)) == int(metrics.get("fragments_completed", -2)), "trace entries do not reconcile to application metrics")
    append_error(errors, int(trace.get("fragment_latency_samples", -1)) == int(metrics.get("fragment_latency_sample_count", -2)), "trace latency samples do not reconcile to metrics")
    records = trace.get("records")
    append_error(errors, isinstance(records, list) and len(records) == expected_objects, "stationary trace record list count mismatch")
    observed_markers = markers(candidate)
    if isinstance(records, list):
        sequences: list[int] = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                errors.append(f"stationary trace record {index} is malformed")
                continue
            sequence = int(record.get("sequence", -1))
            sequences.append(sequence)
            append_error(errors, record.get("passed") is True and record.get("failures") == [], f"stationary trace record {sequence} is not PASS")
            marker_key = f"P7_STATIONARY_TERMINAL_BUNDLE_{sequence:08d}_CAPTURED"
            append_error(errors, observed_markers.get(marker_key) == "1", f"stationary terminal bundle capture marker missing: {sequence}")
            for field in ("descriptor_file", "output_file", "trace_file"):
                record_errors, _bound = verify_hash_record(
                    f"stationary trace {sequence} {field}", record.get(field), document=candidate.path, repo_root=candidate.path.parent, expected_required=False
                )
                errors.extend(record_errors)
        append_error(errors, sequences == list(range(1, expected_objects + 1)), "stationary trace record sequences are not contiguous")
    zero_required = (
        "objects_failed", "fragments_duplicated", "fragments_rejected",
        "fragments_out_of_order", "whole_object_crc_failures", "sha256_mismatches",
        "p6_retry_exhausted", "p6_tx_fail", "p6_crc_bad", "p6_payload_mismatch",
        "duty_violation_count", "shutdown_result",
    )
    for key in zero_required:
        append_error(errors, int(metrics.get(key, -1)) == 0, f"application metric must be zero: {key}")
    append_error(errors, int(metrics.get("objects_requested", -1)) == int(metrics.get("objects_completed", -2)) == expected_objects, "application object counters do not reconcile")
    append_error(errors, int(metrics.get("fragments_generated", -1)) == int(metrics.get("fragments_completed", -2)), "generated/completed fragment counts differ")
    append_error(errors, int(metrics.get("fragments_submitted", -1)) >= int(metrics.get("fragments_generated", 0)), "submitted fragment count is below generated")
    append_error(errors, int(metrics.get("fragments_retried", -1)) == int(metrics.get("fragments_submitted", 0)) - int(metrics.get("fragments_generated", 0)), "fragment retry metric does not reconcile")
    expected_bytes = sum(int(item.get("bytes_completed", 0)) for item in objects)
    append_error(errors, int(metrics.get("bytes_requested", -1)) == int(metrics.get("bytes_completed", -2)) == expected_bytes, "application byte metrics do not reconcile to ledger")
    exact_aggregates = {
        "objects_requested": len(objects),
        "objects_completed": len(objects),
        "objects_failed": 0,
        "fragments_generated": sum(int(item.get("fragments_total", 0)) for item in objects),
        "fragments_submitted": sum(int(item.get("fragment_attempts", 0)) for item in objects),
        "fragments_completed": sum(int(item.get("fragments_completed", 0)) for item in objects),
        "fragments_retried": sum(int(item.get("fragment_attempts", 0)) - int(item.get("fragments_total", 0)) for item in objects),
        "lane0_fragments": sum(int(item.get("lane0_fragments", 0)) for item in objects),
        "lane1_fragments": sum(int(item.get("lane1_fragments", 0)) for item in objects),
        "replicated_fragments": sum(int(item.get("replicated_fragments", 0)) for item in objects),
        "fallback_lane0_to_lane1": int(trace.get("fallback_lane0_to_lane1", -1)),
        "fallback_lane1_to_lane0": int(trace.get("fallback_lane1_to_lane0", -1)),
        "p6_retry_count": sum(int(item.get("p6_retry_count", 0)) for item in objects),
        "p6_retry_exhausted": sum(int(item.get("p6_retry_exhausted", 0)) for item in objects),
        "p6_tx_fail": sum(int(item.get("p6_tx_fail", 0)) for item in objects),
        "p6_crc_bad": sum(int(item.get("p6_crc_bad", 0)) for item in objects),
        "p6_payload_mismatch": sum(int(item.get("p6_payload_mismatch", 0)) for item in objects),
        "max_txd_high_cycles": max((int(item.get("max_txd_high_cycles", 0)) for item in objects), default=0),
        "duty_violation_count": sum(int(item.get("duty_violations", 0)) for item in objects),
    }
    for key, expected in exact_aggregates.items():
        append_error(errors, int(metrics.get(key, -1)) == expected, f"application metric does not exactly reconcile to terminal/raw aggregate: {key}")
    append_error(errors, exact_aggregates["lane0_fragments"] > 0 and exact_aggregates["lane1_fragments"] > 0 and exact_aggregates["replicated_fragments"] > 0, "application lane/replication metrics are incomplete")
    append_error(errors, exact_aggregates["fallback_lane0_to_lane1"] > 0 and exact_aggregates["fallback_lane1_to_lane0"] > 0, "application metrics do not prove both controlled fallback directions")
    append_error(errors, int(metrics.get("queue_high_watermark", -1)) == 8, "application queue high-water mark is not 8")
    append_error(errors, int(metrics.get("backpressure_events", -1)) >= 0, "application backpressure metric is invalid")
    append_error(errors, int(metrics.get("host_to_ps_bytes_per_sec", 0)) > 0, "host-to-PS bytes/sec is not positive")
    append_error(errors, int(metrics.get("application_goodput_bps", 0)) > 0, "cumulative application goodput is not positive")
    append_error(errors, int(metrics.get("ps_counts_per_second", -1)) == PS_COUNTS_PER_SECOND, "PS global-timer counts-per-second constant mismatch")
    runtime_ticks = int(metrics.get("ps_runtime_elapsed_ticks", 0))
    append_error(errors, runtime_ticks == int(mailbox.get("runtime_elapsed_ticks", -1)), "application metrics runtime ticks differ from mailbox")
    append_error(errors, 1800 * PS_COUNTS_PER_SECOND <= runtime_ticks <= int(1801.5 * PS_COUNTS_PER_SECOND), "PS runtime ticks do not prove the bounded full 1800-second window")
    if runtime_ticks > 0:
        expected_goodput = (int(metrics.get("bytes_completed", 0)) * 8 * PS_COUNTS_PER_SECOND) // runtime_ticks
        append_error(errors, int(metrics.get("application_goodput_bps", -1)) == expected_goodput, "application goodput is not bound to bytes and PS runtime ticks")
    host_markers = markers(candidate)
    host_fields = {
        "host_to_ps_input_bytes": "P7_HOST_TO_PS_INPUT_BYTES",
        "host_to_ps_input_duration_ms": "P7_HOST_TO_PS_INPUT_DURATION_MS",
        "host_to_ps_bytes_per_sec": "P7_HOST_TO_PS_INPUT_BYTES_PER_SEC",
        "host_to_ps_bits_per_sec": "P7_HOST_TO_PS_INPUT_BPS",
    }
    for metric_key, marker_key in host_fields.items():
        marker_value = host_markers.get(marker_key)
        append_error(errors, marker_value is not None and str(marker_value).isdecimal(), f"host preload raw marker missing/malformed: {marker_key}")
        if marker_value is not None and str(marker_value).isdecimal():
            append_error(errors, int(metrics.get(metric_key, -1)) == int(marker_value), f"host preload metric/raw marker mismatch: {metric_key}")
    host_bytes = int(metrics.get("host_to_ps_input_bytes", 0))
    host_ms = int(metrics.get("host_to_ps_input_duration_ms", 0))
    if host_ms > 0:
        append_error(errors, int(metrics.get("host_to_ps_bytes_per_sec", -1)) == (host_bytes * 1000) // host_ms, "host preload bytes/sec formula mismatch")
        append_error(errors, int(metrics.get("host_to_ps_bits_per_sec", -1)) == (host_bytes * 8000) // host_ms, "host preload bits/sec formula mismatch")
    fragment_latency = [float(metrics.get(key, 0)) for key in ("fragment_latency_min_us", "fragment_latency_mean_us", "fragment_latency_p50_us", "fragment_latency_p95_us", "fragment_latency_p99_us", "fragment_latency_max_us")]
    append_error(errors, 0 < fragment_latency[0] <= fragment_latency[2] <= fragment_latency[3] <= fragment_latency[4] <= fragment_latency[5] and fragment_latency[0] <= fragment_latency[1] <= fragment_latency[5], "fragment latency metric ordering is invalid")
    if fragment_latency_ticks:
        ordered_fragment_ticks = sorted(fragment_latency_ticks)

        def fragment_nearest_rank(numerator: int, denominator: int) -> int:
            rank = max(0, ((numerator * len(ordered_fragment_ticks) + denominator - 1) // denominator) - 1)
            return ordered_fragment_ticks[min(rank, len(ordered_fragment_ticks) - 1)]

        def ticks_to_us(value: float) -> float:
            return round(value * 1_000_000.0 / PS_COUNTS_PER_SECOND, 6)

        expected_fragment_latency = (
            ticks_to_us(ordered_fragment_ticks[0]),
            ticks_to_us(statistics.fmean(ordered_fragment_ticks)),
            ticks_to_us(fragment_nearest_rank(50, 100)),
            ticks_to_us(fragment_nearest_rank(95, 100)),
            ticks_to_us(fragment_nearest_rank(99, 100)),
            ticks_to_us(ordered_fragment_ticks[-1]),
        )
        append_error(errors, tuple(fragment_latency) == expected_fragment_latency, "fragment latency metrics do not recompute from raw terminal trace binaries")
    object_latency = [float(metrics.get(key, 0)) for key in ("object_latency_min_ms", "object_latency_mean_ms", "object_latency_p95_ms", "object_latency_max_ms")]
    append_error(errors, 0 < object_latency[0] <= object_latency[2] <= object_latency[3] and object_latency[0] <= object_latency[1] <= object_latency[3], "object latency metric ordering is invalid")
    object_latency_ticks = sorted(int(item.get("end_ticks", 0)) - int(item.get("start_ticks", 0)) for item in objects)
    if object_latency_ticks and all(value > 0 for value in object_latency_ticks):
        def ticks_to_ms(value: float) -> float:
            return round(value * 1000.0 / PS_COUNTS_PER_SECOND, 6)

        p95_rank = max(0, ((95 * len(object_latency_ticks) + 99) // 100) - 1)
        expected_object_latency = (
            ticks_to_ms(object_latency_ticks[0]),
            ticks_to_ms(statistics.fmean(object_latency_ticks)),
            ticks_to_ms(object_latency_ticks[min(p95_rank, len(object_latency_ticks) - 1)]),
            ticks_to_ms(object_latency_ticks[-1]),
        )
        append_error(errors, tuple(object_latency) == expected_object_latency, "object latency metrics do not recompute from terminal descriptor start/end ticks")
    append_error(errors, int(metrics.get("fragment_latency_sample_count", -1)) == int(metrics.get("fragments_completed", -2)), "fragment latency sample count mismatch")
    append_error(errors, int(metrics.get("object_latency_sample_count", -1)) == expected_objects, "object latency sample count mismatch")
    append_error(errors, 0 < int(metrics.get("max_txd_high_cycles", 0)) <= 8, "application max TXD-high metric is outside 1..8")
    time_sources = metrics.get("time_sources")
    append_error(errors, isinstance(time_sources, dict), "application metric time_sources object missing")
    if isinstance(time_sources, dict):
        append_error(errors, "host wall clock" in str(time_sources.get("host_to_ps_bytes_per_sec", "")), "host-to-PS time source is not labeled host wall clock")
        for key in ("application_goodput_bps", "fragment_latency", "object_latency"):
            append_error(errors, "PS global timer" in str(time_sources.get(key, "")), f"metric time source is not PS global timer: {key}")
    append_error(
        errors,
        mailbox.get("metrics_time_sources") == (
            "ps_global_timer_for_scheduler_samples_goodput_fragment_and_object_latency;"
            "host_wall_clock_for_preload_and_independent_duration_watchdog"
        ),
        "mailbox metric time-source boundary mismatch",
    )
    metrics["object_latency_definition"] = (
        "full PS object-processing interval from valid descriptor RUNNING through output CRC32/SHA256 completion; "
        "excludes host descriptor publication and JTAG terminal observation"
    )
    return StageResult(
        "application_metrics",
        "PASS" if not errors else "FAIL",
        "bytes, goodput, latency, queue, retry, safety, and lane metrics are complete and source-labeled" if not errors else "application metrics evidence failed closed",
        [str(candidate.path)],
        metrics=metrics,
        errors=errors,
        notes=["object_latency_* fields cover PS processing only; host publication and JTAG observation timing are excluded and reported separately"],
    )


def audit_all_shutdowns(evidence: RepositoryEvidence) -> StageResult:
    errors: list[str] = []
    audited = 0
    evidence_paths: list[str] = []
    for candidate in evidence.candidates:
        mutated = candidate_has_hardware_footprint(candidate)
        if not mutated:
            continue
        audited += 1
        evidence_paths.append(rel(candidate.path, evidence.repo_root))
        if not candidate.executed:
            errors.append(f"{rel(candidate.path, evidence.repo_root)}: hardware footprint contradicts hardware_actions_executed=true")
        for item in shutdown_errors(candidate, "after"):
            errors.append(f"{rel(candidate.path, evidence.repo_root)}: {item}")
    if audited == 0:
        return missing_stage(evidence, "shutdown", "no hardware-mutating P7 run exists to audit")
    return StageResult(
        "shutdown",
        "PASS" if not errors else "FAIL",
        "every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker" if not errors else "one or more hardware runs lack valid shutdown-after evidence",
        evidence_paths,
        metrics={"audited_hardware_runs": audited},
        errors=errors,
    )


def verify_loose_hash_manifests(evidence: RepositoryEvidence) -> list[str]:
    errors: list[str] = []
    for path in sorted(evidence.hardware_root.rglob("*")) if evidence.hardware_root.is_dir() else []:
        if not path.is_file() or path.suffix.casefold() not in {".sha256", ".sha256sum"} and "sha256" not in path.name.casefold():
            continue
        if path.suffix.casefold() == ".json":
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError) as exc:
            errors.append(f"unable to read SHA256 manifest {rel(path, evidence.repo_root)}: {exc}")
            continue
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            match = re.fullmatch(r"([0-9a-fA-F]{64})\s+[*]?(.+)", stripped)
            if not match:
                errors.append(f"malformed SHA256 manifest line {rel(path, evidence.repo_root)}:{number}")
                continue
            target = resolve_reference(match.group(2).strip(), document=path, repo_root=evidence.repo_root)
            if target is None or not target.is_file():
                errors.append(f"SHA256 manifest target missing: {match.group(2).strip()}")
            elif sha256_file(target) != match.group(1).lower():
                errors.append(f"SHA256 manifest target tampered: {rel(target, evidence.repo_root)}")
    return errors


def provenance_consistency_errors(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    errors: list[str] = []
    for key in ("source_commit", "board_id", "expected_part", "expected_target"):
        values = {str(row.get(key, "")) for row in rows if row.get(key) not in (None, "")}
        if len(values) > 1:
            errors.append(f"selected hardware evidence disagrees on {key}: {sorted(values)}")
    for artifact in ("plan", "active_xdc", "pinmap", "register_map", "shutdown_bitstream"):
        hashes = {
            str(row.get("artifacts", {}).get(artifact, {}).get("actual_sha256", ""))
            for row in rows
            if isinstance(row.get("artifacts"), dict) and artifact in row.get("artifacts", {})
        }
        hashes.discard("")
        if len(hashes) > 1:
            errors.append(f"selected hardware evidence disagrees on canonical artifact {artifact}: {sorted(hashes)}")
    ps_rows = [row for row in rows if row.get("kind") == "ps"]
    for artifact in ("bitstream", "xsa", "elf"):
        hashes = {str(row.get("artifacts", {}).get(artifact, {}).get("actual_sha256", "")) for row in ps_rows}
        hashes.discard("")
        if len(hashes) > 1:
            errors.append(f"PS hardware evidence disagrees on immutable {artifact}: {sorted(hashes)}")
    jtag_rows = [row for row in rows if row.get("kind") == "jtag"]
    for artifact in ("bitstream", "ltx"):
        hashes = {str(row.get("artifacts", {}).get(artifact, {}).get("actual_sha256", "")) for row in jtag_rows}
        hashes.discard("")
        if len(hashes) > 1:
            errors.append(f"JTAG hardware evidence disagrees on immutable {artifact}: {sorted(hashes)}")
    return errors


def build_results(evidence: RepositoryEvidence) -> dict[str, StageResult]:
    results: dict[str, StageResult] = {}
    by_stage: dict[str, list[Candidate]] = {}
    for candidate in evidence.candidates:
        by_stage.setdefault(candidate.stage, []).append(candidate)

    safe = choose_latest(by_stage.get("safe_idle", []))
    results["safe_idle"] = validate_safe_idle(safe, evidence) if safe else missing_stage(evidence, "safe_idle", "safe-idle hardware stage is missing")
    p6_candidates = [item for item in by_stage.get("p6_frame_regression", []) if item.executed]
    results["p6_frame_regression"] = validate_p6_regression_candidates(p6_candidates, evidence) if p6_candidates else missing_stage(evidence, "p6_frame_regression", "P6 one-frame lane-mask regression is missing")

    functional_candidates = [item for item in by_stage.get("ps_runtime", []) if item.data.get("mode") == "functional"]
    functional = choose_latest(functional_candidates)
    if functional:
        runtime, redundant_boundary = validate_ps_functional(functional, evidence)
        if redundant_boundary.status != "PASS":
            runtime.status = "FAIL"
            runtime.errors.extend(f"redundant PS boundary regression: {item}" for item in redundant_boundary.errors)
            runtime.reason = "real PS runtime or its redundant boundary regression failed closed"
        runtime.metrics["redundant_ps_boundary_pairs"] = redundant_boundary.metrics.get("observed_length_policy_pairs", 0)
        results["ps_runtime"] = runtime
    else:
        results["ps_runtime"] = missing_stage(evidence, "ps_runtime", "real PS functional runtime hardware stage is missing")
    results["fragment_boundary"] = validate_boundary_jtag(
        [item for item in by_stage.get("fragment_boundary_jtag", []) if item.executed], evidence
    )

    results["large_object_jtag"] = validate_large_jtag(
        [item for item in by_stage.get("large_object_jtag", []) if item.executed], evidence
    )
    for stage in ("lane_fallback", "abort_restart", "queue_backpressure"):
        candidate = choose_latest(by_stage.get(stage, []))
        results[stage] = validate_ps_mode(candidate, evidence, stage) if candidate else missing_stage(evidence, stage, f"{stage} hardware stage is missing")

    stationary_candidates = [item for item in by_stage.get("stationary", []) if item.executed]
    full_stationary_candidates = [item for item in stationary_candidates if stationary_observed_wall(item) >= 1800.0]
    qualified_stationary_candidates = [item for item in stationary_candidates if stationary_is_qualified(item)]
    stationary_uniqueness_errors: list[str] = []
    if len(stationary_candidates) > 1:
        stationary_uniqueness_errors.append(
            "the final stationary launch intent is one-shot and may not be retried after a short failure or crash; "
            f"observed_launches={len(stationary_candidates)}"
        )
    if len(full_stationary_candidates) > 1:
        stationary_uniqueness_errors.append(
            "only one full-duration real-PS stationary run is allowed; "
            f"observed={len(full_stationary_candidates)}"
        )
    if len(qualified_stationary_candidates) > 1:
        stationary_uniqueness_errors.append(
            "exactly one qualified real-PS stationary PASS is allowed; "
            f"observed={len(qualified_stationary_candidates)}"
        )
    if len(qualified_stationary_candidates) == 1:
        stationary, calibration, metrics = stationary_results(qualified_stationary_candidates[0], evidence)
        if stationary_uniqueness_errors:
            stationary.errors.extend(stationary_uniqueness_errors)
            stationary.status = "FAIL"
            calibration.errors.extend(stationary_uniqueness_errors)
            calibration.status = "FAIL"
            metrics.errors.extend(stationary_uniqueness_errors)
            metrics.status = "FAIL"
        short_failures = [item for item in stationary_candidates if item not in qualified_stationary_candidates]
        if short_failures:
            note = f"preserved {len(short_failures)} failed/aborted non-qualified stationary launch(es); one-shot policy forbids an automatic retry"
            stationary.notes.append(note)
            calibration.notes.append(note)
            metrics.notes.append(note)
        results["stationary"] = stationary
        results["calibration"] = calibration
        results["application_metrics"] = metrics
    elif stationary_candidates:
        latest_attempt = choose_latest(stationary_candidates)
        stationary, calibration, metrics = stationary_results(latest_attempt, evidence)  # type: ignore[arg-type]
        paths = [rel(item.path, evidence.repo_root) for item in stationary_candidates]
        failure = stationary_uniqueness_errors or ["no executed stationary attempt is a qualified full-duration PASS"]
        stationary.status = "FAIL"
        stationary.reason = "no unique qualified stationary PASS exists"
        stationary.evidence = paths
        stationary.errors.extend(failure)
        calibration.status = "FAIL"
        calibration.reason = "no unique qualified stationary run can own calibration"
        calibration.evidence = paths
        calibration.errors.extend(failure)
        metrics.status = "FAIL"
        metrics.reason = "no unique qualified stationary run can own metrics"
        metrics.evidence = paths
        metrics.errors.extend(failure)
        results["stationary"] = stationary
        results["calibration"] = calibration
        results["application_metrics"] = metrics
    else:
        results["stationary"] = missing_stage(evidence, "stationary", "the unique 1800-second real-PS stationary run is missing")
        results["calibration"] = missing_stage(evidence, "calibration", "embedded 300-second calibration window is missing")
        results["application_metrics"] = missing_stage(evidence, "application_metrics", "stationary application metrics are missing")

    results["shutdown"] = audit_all_shutdowns(evidence)
    consistency_errors = list(evidence.parse_errors)
    partial_files = [row["path"] for row in evidence.inventory if str(row.get("path", "")).casefold().endswith((".write_partial", ".partial", ".tmp"))]
    if partial_files:
        consistency_errors.append(f"uncommitted/partial hardware evidence files remain: {partial_files}")
    consistency_errors.extend(verify_loose_hash_manifests(evidence))
    consistency_errors.extend(provenance_consistency_errors(evidence.provenance_rows))
    consistency_errors.extend(stationary_uniqueness_errors)
    for stage_name, stage_result in results.items():
        if stage_name != "consistency" and stage_result.status == "FAIL":
            consistency_errors.append(f"mandatory stage evidence is internally inconsistent: {stage_name}")
    ledger_status, ledger_errors, ledger_metrics = validate_sequence_ledger(evidence)
    consistency_errors.extend(ledger_errors)
    unclassified_executed = [item for item in evidence.candidates if item.executed and item.stage.startswith("unclassified")]
    if unclassified_executed:
        consistency_errors.append(
            "executed hardware summaries are unclassified: "
            + ", ".join(rel(item.path, evidence.repo_root) for item in unclassified_executed)
        )
    mandatory_incomplete = any(
        result.status in {"PENDING_HW", "SKIP_WITH_REASON"}
        for name, result in results.items()
        if name != "consistency"
    )
    consistency_status = "FAIL" if consistency_errors else "PENDING_HW" if mandatory_incomplete else ledger_status
    results["consistency"] = StageResult(
        "consistency",
        consistency_status,
        "all selected summaries, raw records, hashes, targets, commits, risk order, and stationary-run cardinality agree" if consistency_status == "PASS" else "run-sequence ledger is pending" if consistency_status == "PENDING_HW" else "evidence consistency failed closed",
        sorted({row.get("summary", "") for row in evidence.provenance_rows if row.get("summary")})
        + ([rel(evidence.hardware_root / "p7_run_sequence_ledger.json", evidence.repo_root)] if (evidence.hardware_root / "p7_run_sequence_ledger.json").is_file() else []),
        metrics={
            "inventory_files": len(evidence.inventory),
            "selected_provenance_rows": len(evidence.provenance_rows),
            "stationary_attempts": len(stationary_candidates),
            "full_duration_stationary_attempts": len(full_stationary_candidates),
            "qualified_stationary_passes": len(qualified_stationary_candidates),
            **ledger_metrics,
        },
        errors=consistency_errors,
    )
    return results


def final_result(results: Mapping[str, StageResult]) -> StageResult:
    failures = [name for name in FINAL_REQUIRED_STAGES if results[name].status == "FAIL"]
    incomplete = [name for name in FINAL_REQUIRED_STAGES if results[name].status in {"PENDING_HW", "SKIP_WITH_REASON"}]
    if failures:
        status = "FAIL"
        reason = "one or more mandatory real-hardware gates failed"
    elif incomplete:
        status = "PENDING_HW"
        reason = "real-hardware evidence is incomplete; offline/proxy evidence was not promoted"
    else:
        status = "PASS"
        reason = "all mandatory stationary two-lane local application hardware gates passed"
    return StageResult(
        "final",
        status,
        reason,
        sorted({path for name in FINAL_REQUIRED_STAGES for path in results[name].evidence}),
        checks={name: results[name].status for name in FINAL_REQUIRED_STAGES},
        errors=[f"{name}: {item}" for name in failures for item in results[name].errors],
        notes=[
            "Scope is stationary, local, two-lane application transport only.",
            "No Ethernet cable/network acceptance and no hardware motion/rotation acceptance occurred.",
            "Software-injected lane unavailability is not a physical optical fault test.",
            "Product-final acceptance remains pending.",
        ],
    )


def markdown_for_stage(stage: StageResult, generated_at: str, envelope: Mapping[str, Any] | None = None) -> str:
    envelope = envelope or {}
    lines = [
        f"# {stage.name}",
        "",
        f"RESULT: {stage.status}",
        f"REASON: {stage.reason}",
        f"GENERATED_AT_UTC: {generated_at}",
        f"REPO: {envelope.get('repo', 'MISSING')}",
        f"HEAD: {envelope.get('HEAD', 'INCONSISTENT_OR_MISSING')}",
        "HARDWARE_ACTIONS_EXECUTED_BY_SUMMARIZER: false",
        f"HARDWARE_ACTIONS_EXECUTED: {str(bool(envelope.get('hardware_actions_executed'))).lower()}",
        f"PROGRAMMED_FPGA: {envelope.get('programmed_fpga')}",
        f"DROVE_TFDU_TXD: {envelope.get('drove_tfdu_txd')}",
        f"ENABLED_TFDU_RECEIVER: {envelope.get('enabled_tfdu_receiver')}",
        f"SHUTDOWN_EXIT: {envelope.get('SHUTDOWN_EXIT')}",
        "NETWORK_USED: false",
        "MOTION_USED: false",
        "AVAILABLE_LANES: 2",
        "MAX_LANE_MASK: 0x3",
        "PRODUCT_FINAL_ACCEPTANCE: PENDING",
        "PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT",
        "",
        "## Evidence",
        "",
    ]
    lines.extend(f"- `{item}`" for item in stage.evidence) if stage.evidence else lines.append("- None (hardware evidence pending).")
    lines.extend(["", "## Checks", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in stage.checks.items()) if stage.checks else lines.append("- No additional checks recorded.")
    lines.extend(["", "## Metrics", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in stage.metrics.items()) if stage.metrics else lines.append("- No metrics available.")
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- {item}" for item in stage.errors) if stage.errors else lines.append("- None.")
    if stage.notes:
        lines.extend(["", "## Scope notes", ""])
        lines.extend(f"- {item}" for item in stage.notes)
    lines.extend(["", "## Hardware evidence envelope", ""])
    for key in (
        "profile",
        "bitstream",
        "ltx",
        "xsa",
        "elf",
        "authorization",
        "input_file_hashes",
        "output_file_hashes",
        "shutdown_before",
        "shutdown_after",
    ):
        lines.extend(
            [
                f"### {key}",
                "",
                "```json",
                json.dumps(envelope.get(key), indent=2, sort_keys=True, ensure_ascii=False),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "### envelope_status",
            "",
            "```json",
            json.dumps(
                {
                    "repo": envelope.get("repo"),
                    "HEAD": envelope.get("HEAD"),
                    "hardware_actions_executed": envelope.get("hardware_actions_executed"),
                    "programmed_fpga": envelope.get("programmed_fpga"),
                    "drove_tfdu_txd": envelope.get("drove_tfdu_txd"),
                    "enabled_tfdu_receiver": envelope.get("enabled_tfdu_receiver"),
                    "uart_access": envelope.get("uart_access"),
                    "SHUTDOWN_EXIT": envelope.get("SHUTDOWN_EXIT"),
                },
                indent=2,
                sort_keys=True,
            ),
            "```",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def markdown_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    if value is None:
        return "NONE"
    return str(value)


def markdown_final(
    stage: StageResult,
    results: Mapping[str, StageResult],
    final_fields: Mapping[str, Any],
    generated_at: str,
) -> str:
    ordered_fields = (
        "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET",
        "HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION",
        "STATIONARY_2LANE_APPLICATION_ACCEPTANCE",
        "COMMIT",
        "SOURCE_COMMIT",
        "USER_HARDWARE_AUTHORIZATION_FOR_P7",
        "NETWORK_CABLE_CONNECTED",
        "HARDWARE_MOVEMENT_ALLOWED",
        "NO_ETHERNET_USED",
        "NO_HARDWARE_MOVEMENT",
        "AVAILABLE_LANES",
        "AVAILABLE_PHYSICAL_LANES",
        "MAX_LANE_MASK",
        "MAX_LANE_MASK_USED",
        "HARDWARE_ACTIONS_EXECUTED",
        "PS_PL_PHY_PL_PS_APPLICATION_PASS",
        "JTAG_AXI_AUXILIARY_PATH_PASS",
        "JTAG_AXI_PL_PHY_PL_PASS",
        "FRAGMENTATION_REASSEMBLY",
        "FILE_INTEGRITY_SHA256",
        "QUEUE_BACKPRESSURE",
        "SOFTWARE_LANE_FALLBACK",
        "STATIONARY_30MIN",
        "SHUTDOWN_BEFORE",
        "SHUTDOWN_AFTER",
        "BITSTREAM_SHA256",
        "PS_ELF_SHA256",
        "ETHERNET_ACCEPTANCE",
        "ROTATION_ACCEPTANCE",
        "EIGHT_LANE_ACCEPTANCE",
        "PRODUCT_FINAL_ACCEPTANCE",
        "PRODUCT_FINAL_ACCEPTANCE_REASON",
    )
    lines = [
        "# P7 final hardware acceptance summary",
        "",
        f"GENERATED_AT_UTC: {generated_at}",
    ]
    lines.extend(f"{key}: {markdown_scalar(final_fields.get(key))}" for key in ordered_fields)
    lines.extend(["", "## Gate results", "", "| Gate | Result | Reason |", "|---|---|---|"])
    for name in FINAL_REQUIRED_STAGES:
        item = results[name]
        lines.append(f"| {name} | {item.status} | {item.reason.replace('|', '/')} |")
    for heading in ("PASS", "FAIL", "SKIP_WITH_REASON", "PENDING_HW"):
        lines.extend(["", f"## {heading}", ""])
        matching = [str(item) for item in final_fields.get(heading, [])]
        lines.extend(f"- {item}" for item in matching) if matching else lines.append("- None.")
    lines.extend(["", "## GENERATED_SUMMARIES", ""])
    generated = [str(item) for item in final_fields.get("GENERATED_SUMMARIES", [])]
    lines.extend(f"- `{item}`" for item in generated) if generated else lines.append("- None.")
    lines.extend(["", f"NEXT_RECOMMENDED_STAGE: {markdown_scalar(final_fields.get('NEXT_RECOMMENDED_STAGE'))}"])
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This result is limited to a stationary, local, two-lane application path. It does not prove Ethernet, rotation, eight-lane operation, or product-final acceptance. JTAG/AXI is auxiliary; only the real PS ELF/runtime path can set `PS_PL_PHY_PL_PS_APPLICATION_PASS: true`.",
            "",
        ]
    )
    return "\n".join(lines)


def atomic_write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def provenance_for_stage(stage_name: str, rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    candidate_stages = {
        "safe_idle": {"safe_idle"},
        "p6_frame_regression": {"p6_frame_regression"},
        "fragment_boundary": {"fragment_boundary_jtag"},
        "large_object_jtag": {"large_object_jtag"},
        "ps_runtime": {"ps_runtime"},
        "lane_fallback": {"lane_fallback"},
        "abort_restart": {"abort_restart"},
        "queue_backpressure": {"queue_backpressure"},
        "calibration": {"stationary"},
        "stationary": {"stationary"},
        "application_metrics": {"stationary"},
    }.get(stage_name)
    selected = rows if candidate_stages is None else [row for row in rows if str(row.get("stage", "")) in candidate_stages]
    unique: dict[str, dict[str, Any]] = {}
    for row in selected:
        key = str(row.get("summary", json.dumps(row, sort_keys=True, default=str)))
        unique[key] = dict(row)
    return [unique[key] for key in sorted(unique)]


def stage_json_payload(
    stage: StageResult,
    evidence: RepositoryEvidence,
    generated_at: str,
) -> dict[str, Any]:
    rows = provenance_for_stage(stage.name, evidence.provenance_rows)
    commits = sorted({str(row.get("source_commit")) for row in rows if row.get("source_commit")})
    artifacts: dict[str, list[dict[str, Any]]] = {}
    for name in (*REQUIRED_ARTIFACTS, "ltx"):
        records = {
            json.dumps(row.get("artifacts", {}).get(name), sort_keys=True): row.get("artifacts", {}).get(name)
            for row in rows
            if isinstance(row.get("artifacts"), dict) and isinstance(row.get("artifacts", {}).get(name), dict)
        }
        artifacts[name] = [records[key] for key in sorted(records)]
    authorization_records = [row["authorization"] for row in rows if isinstance(row.get("authorization"), dict)]
    input_hash_records: list[dict[str, Any]] = []
    output_hash_records: list[dict[str, Any]] = []
    for row in rows:
        extensions = row.get("authorization_extensions")
        if isinstance(extensions, dict):
            input_hash_records.extend(dict(record) for record in extensions.values() if isinstance(record, dict))
        outputs = row.get("output_file_hashes")
        if isinstance(outputs, list):
            output_hash_records.extend(dict(record) for record in outputs if isinstance(record, dict))
    payload = stage.to_json()
    payload.update(
        {
            "generated_at_utc": generated_at,
            "repo": str(evidence.repo_root),
            "HEAD": commits[0] if len(commits) == 1 else "INCONSISTENT_OR_MISSING",
            "hardware_actions_executed": bool(rows) and any(row.get("hardware_actions_executed") is True for row in rows),
            "programmed_fpga": bool(rows) and all(row.get("programmed_fpga") is True for row in rows),
            "drove_tfdu_txd": None if not rows or any(row.get("drove_tfdu_txd") is None for row in rows) else any(row.get("drove_tfdu_txd") is True for row in rows),
            "enabled_tfdu_receiver": None if not rows or any(row.get("enabled_tfdu_receiver") is None for row in rows) else any(row.get("enabled_tfdu_receiver") is True for row in rows),
            "uart_access": None if not rows or any(row.get("uart_access") is None for row in rows) else any(row.get("uart_access") is True for row in rows),
            "shutdown_before": [row.get("shutdown_before") for row in rows],
            "shutdown_after": [row.get("shutdown_after") for row in rows],
            "SHUTDOWN_EXIT": 0 if rows and all(row.get("SHUTDOWN_EXIT") == 0 for row in rows) else None,
            "profile": artifacts["profile"],
            "bitstream": artifacts["bitstream"],
            "ltx": artifacts["ltx"],
            "xsa": artifacts["xsa"],
            "elf": artifacts["elf"],
            "authorization": authorization_records,
            "input_file_hashes": input_hash_records,
            "output_file_hashes": output_hash_records,
            "artifact_provenance": artifacts,
            "runner_provenance": rows,
        }
    )
    if stage.name == "final":
        payload["HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION"] = stage.status
    return payload


def generated_summary_paths(evidence: RepositoryEvidence) -> list[str]:
    names = {
        f"{alias}.{suffix}"
        for aliases in ALIASES.values()
        for alias in aliases
        for suffix in ("md", "json")
    }
    names.update(
        {
            "p7_hardware_evidence_summary.json",
            "p7_provenance.md",
            "p7_provenance.json",
            "p7_artifact_provenance_summary.md",
            "p7_artifact_provenance_summary.json",
            "p7_hardware_authorization_summary.md",
            "p7_hardware_authorization_summary.json",
        }
    )
    return [rel(evidence.output_dir / name, evidence.repo_root) for name in sorted(names)]


def rollup_status(results: Mapping[str, StageResult], names: Sequence[str]) -> str:
    statuses = [results[name].status for name in names]
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    if all(status == "PASS" for status in statuses):
        return "PASS"
    return "PENDING_HW"


def next_recommended_stage(results: Mapping[str, StageResult], final: StageResult) -> str:
    if final.status == "PASS":
        return "FINAL_EVIDENCE_COMMIT"
    for name in FINAL_REQUIRED_STAGES:
        if results[name].status == "FAIL":
            return f"REMEDIATE_{name.upper()}"
    for name in FINAL_REQUIRED_STAGES:
        if results[name].status in {"PENDING_HW", "SKIP_WITH_REASON"}:
            return f"EXECUTE_OR_COLLECT_{name.upper()}"
    return "REVIEW_EVIDENCE_CONSISTENCY"


def final_status_fields(
    evidence: RepositoryEvidence,
    results: Mapping[str, StageResult],
    final: StageResult,
) -> dict[str, Any]:
    provenance = evidence.provenance_rows
    source_commits = sorted({str(row.get("source_commit")) for row in provenance if row.get("source_commit")})
    source_commit = source_commits[0] if len(source_commits) == 1 else "INCONSISTENT_OR_MISSING"
    ps_rows = [row for row in provenance if row.get("kind") == "ps"]
    bit_hashes = sorted(
        {
            str(row.get("artifacts", {}).get("bitstream", {}).get("actual_sha256"))
            for row in ps_rows
            if row.get("artifacts", {}).get("bitstream")
        }
    )
    elf_hashes = sorted(
        {
            str(row.get("artifacts", {}).get("elf", {}).get("actual_sha256"))
            for row in ps_rows
            if row.get("artifacts", {}).get("elf")
        }
    )
    ps_pass = final.status == "PASS" and all(results[name].status == "PASS" for name in FINAL_REQUIRED_STAGES)
    jtag_pass = (
        all(
            results[name].status == "PASS"
            for name in ("safe_idle", "p6_frame_regression", "fragment_boundary", "large_object_jtag", "shutdown")
        )
        and results["consistency"].status != "FAIL"
    )
    fields: dict[str, Any] = {
        "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET": final.status,
        "HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION": final.status,
        "STATIONARY_2LANE_APPLICATION_ACCEPTANCE": final.status,
        # The summarizer runs before the final evidence commit, so reusing the
        # source commit here would falsely claim that generated evidence is committed.
        "COMMIT": "PENDING_FINAL_EVIDENCE_COMMIT",
        "SOURCE_COMMIT": source_commit,
        "USER_HARDWARE_AUTHORIZATION_FOR_P7": "GRANTED",
        "NETWORK_CABLE_CONNECTED": False,
        "HARDWARE_MOVEMENT_ALLOWED": False,
        "NO_ETHERNET_USED": True,
        "NO_HARDWARE_MOVEMENT": True,
        "AVAILABLE_LANES": 2,
        "AVAILABLE_PHYSICAL_LANES": 2,
        "MAX_LANE_MASK": "0x3",
        "MAX_LANE_MASK_USED": "0x3",
        "HARDWARE_ACTIONS_EXECUTED": any(row.get("hardware_actions_executed") is True for row in provenance),
        "PS_PL_PHY_PL_PS_APPLICATION_PASS": ps_pass,
        "JTAG_AXI_AUXILIARY_PATH_PASS": jtag_pass,
        "JTAG_AXI_PL_PHY_PL_PASS": jtag_pass,
        "FRAGMENTATION_REASSEMBLY": results["fragment_boundary"].status,
        "FILE_INTEGRITY_SHA256": rollup_status(results, ("ps_runtime", "stationary", "application_metrics", "consistency")),
        "QUEUE_BACKPRESSURE": results["queue_backpressure"].status,
        "SOFTWARE_LANE_FALLBACK": results["lane_fallback"].status,
        "STATIONARY_30MIN": results["stationary"].status,
        "SHUTDOWN_BEFORE": results["shutdown"].status,
        "SHUTDOWN_AFTER": results["shutdown"].status,
        "BITSTREAM_SHA256": bit_hashes[0] if len(bit_hashes) == 1 else "INCONSISTENT_OR_MISSING",
        "PS_ELF_SHA256": elf_hashes[0] if len(elf_hashes) == 1 else "INCONSISTENT_OR_MISSING",
        "ETHERNET_ACCEPTANCE": "DEFERRED_NO_NETWORK_CABLE",
        "ROTATION_ACCEPTANCE": "DEFERRED_NO_HARDWARE_MOVEMENT",
        "EIGHT_LANE_ACCEPTANCE": "DEFERRED_ONLY_2_LANES_AVAILABLE",
        "PRODUCT_FINAL_ACCEPTANCE": "PENDING",
        "PRODUCT_FINAL_ACCEPTANCE_REASON": "PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT",
        "PASS": [f"{name}: {results[name].reason}" for name in FINAL_REQUIRED_STAGES if results[name].status == "PASS"],
        "FAIL": [f"{name}: {results[name].reason}" for name in FINAL_REQUIRED_STAGES if results[name].status == "FAIL"],
        "SKIP_WITH_REASON": [f"{name}: {results[name].reason}" for name in FINAL_REQUIRED_STAGES if results[name].status == "SKIP_WITH_REASON"],
        "PENDING_HW": [f"{name}: {results[name].reason}" for name in FINAL_REQUIRED_STAGES if results[name].status == "PENDING_HW"],
        "GENERATED_SUMMARIES": generated_summary_paths(evidence),
        "NEXT_RECOMMENDED_STAGE": next_recommended_stage(results, final),
    }
    return fields


def write_outputs(evidence: RepositoryEvidence, results: Mapping[str, StageResult], final: StageResult) -> dict[str, Any]:
    generated_at = utc_now()
    evidence.output_dir.mkdir(parents=True, exist_ok=True)
    final_fields = final_status_fields(evidence, results, final)
    final_envelope = stage_json_payload(final, evidence, generated_at)
    final_envelope.update(final_fields)
    payload = {
        "schema": "rf-comm-p7-hardware-evidence-consistency-v1",
        "generated_at_utc": generated_at,
        **final_fields,
        "hardware_actions_executed_by_summarizer": False,
        "hardware_root": str(evidence.hardware_root),
        "output_dir": str(evidence.output_dir),
        "stages": {name: stage_json_payload(result, evidence, generated_at) for name, result in results.items()},
        "final": final_envelope,
        "provenance": evidence.provenance_rows,
    }
    atomic_write_json(evidence.output_dir / "p7_hardware_evidence_summary.json", payload)
    for stage_name, aliases in ALIASES.items():
        stage = final if stage_name == "final" else results[stage_name]
        envelope = final_envelope if stage_name == "final" else stage_json_payload(stage, evidence, generated_at)
        markdown = markdown_final(final, results, final_fields, generated_at) if stage_name == "final" else markdown_for_stage(stage, generated_at, envelope)
        for alias in aliases:
            atomic_write_text(evidence.output_dir / f"{alias}.md", markdown)
            atomic_write_json(evidence.output_dir / f"{alias}.json", envelope)

    provenance_payload = {
        "schema": "rf-comm-p7-hardware-provenance-v1",
        "generated_at_utc": generated_at,
        "hardware_actions_executed_by_summarizer": False,
        "records": evidence.provenance_rows,
    }
    atomic_write_json(evidence.output_dir / "p7_provenance.json", provenance_payload)
    provenance_md = ["# P7 hardware provenance", "", f"RESULT: {results['consistency'].status}", "", "| Stage | Kind | Source commit | Target | Summary |", "|---|---|---|---|---|"]
    for row in evidence.provenance_rows:
        provenance_md.append(f"| {row.get('stage', '')} | {row.get('kind', '')} | {row.get('source_commit', '')} | {row.get('expected_target', '')} | `{row.get('summary', '')}` |")
    provenance_md.extend(["", "Hashes and paths are recorded in `p7_provenance.json`; every referenced artifact was re-hashed by this offline summarizer.", ""])
    atomic_write_text(evidence.output_dir / "p7_provenance.md", "\n".join(provenance_md))
    atomic_write_json(evidence.output_dir / "p7_artifact_provenance_summary.json", provenance_payload)
    atomic_write_text(evidence.output_dir / "p7_artifact_provenance_summary.md", "\n".join(provenance_md))

    authorization_rows = [
        {
            "stage": row.get("stage"),
            "kind": row.get("kind"),
            "summary": row.get("summary"),
            "source_commit": row.get("source_commit"),
            "authorization": row.get("authorization"),
            "authorization_extensions": row.get("authorization_extensions", {}),
        }
        for row in evidence.provenance_rows
        if isinstance(row.get("authorization"), dict)
    ]
    authorization_status = results["consistency"].status if authorization_rows else "PENDING_HW"
    authorization_payload = {
        "schema": "rf-comm-p7-hardware-authorization-summary-v1",
        "generated_at_utc": generated_at,
        "result": authorization_status,
        "hardware_actions_executed_by_summarizer": False,
        "records": authorization_rows,
    }
    atomic_write_json(evidence.output_dir / "p7_hardware_authorization_summary.json", authorization_payload)
    authorization_md = [
        "# P7 hardware authorization summary",
        "",
        f"RESULT: {authorization_status}",
        f"GENERATED_AT_UTC: {generated_at}",
        "HARDWARE_ACTIONS_EXECUTED_BY_SUMMARIZER: false",
        "",
        "Each selected runner authorization was parsed independently and its path/SHA256 fields were re-hashed.",
        "",
        f"AUTHORIZATION_RECORDS: {len(authorization_rows)}",
        "",
    ]
    atomic_write_text(evidence.output_dir / "p7_hardware_authorization_summary.md", "\n".join(authorization_md))

    atomic_write_csv(evidence.output_dir / "p7_hardware_file_inventory.csv", evidence.inventory, ("path", "size_bytes", "sha256"))
    atomic_write_json(evidence.output_dir / "p7_hardware_file_inventory.json", {"files": evidence.inventory})

    stationary_candidates = [item for item in evidence.candidates if item.kind == "ps" and item.stage == "stationary" and item.executed]
    qualified_stationary = [item for item in stationary_candidates if stationary_is_qualified(item)]
    object_rows: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    application_metric_row: dict[str, Any] = {}
    if len(qualified_stationary) == 1:
        post = qualified_stationary[0].data.get("postprocess", {})
        if isinstance(post, dict):
            object_rows = [dict(row) for row in post.get("stationary_objects", []) if isinstance(row, dict)]
            sample_rows = [dict(row) for row in post.get("stationary_samples", []) if isinstance(row, dict)]
            raw_metrics = post.get("application_metrics")
            if isinstance(raw_metrics, dict):
                application_metric_row = {
                    key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value
                    for key, value in raw_metrics.items()
                }
    object_fields = sorted({key for row in object_rows for key in row}) or ["sequence"]
    sample_fields = sorted({key for row in sample_rows for key in row}) or ["elapsed_sec"]
    atomic_write_csv(evidence.output_dir / "p7_object_ledger.csv", object_rows, object_fields)
    atomic_write_csv(evidence.output_dir / "p7_stationary_samples.csv", sample_rows, sample_fields)
    metric_rows = (
        [{"record_type": "application_metrics", **application_metric_row}] if application_metric_row else []
    ) + [{"record_type": "object", **row} for row in object_rows] + [{"record_type": "sample", **row} for row in sample_rows]
    metric_fields = ["record_type"] + sorted({key for row in metric_rows for key in row if key != "record_type"})
    atomic_write_csv(evidence.output_dir / "p7_application_metrics_summary.csv", metric_rows, metric_fields or ["record_type"])
    return payload


def summarize(repo_root: Path, hardware_root: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    evidence = RepositoryEvidence(repo_root.resolve(), hardware_root.resolve(), output_dir.resolve())
    discover(evidence)
    results = build_results(evidence)
    final = final_result(results)
    payload = write_outputs(evidence, results, final)
    return payload, 0 if final.status == "PASS" else 1 if final.status == "FAIL" else 2


def build_parser() -> argparse.ArgumentParser:
    default_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Offline-only, fail-closed P7 hardware evidence consistency gate.")
    parser.add_argument("--repo-root", default=str(default_root))
    parser.add_argument("--hardware-root", default="evidence/hardware/p7")
    parser.add_argument("--output-dir", default="evidence/generated")
    parser.add_argument("--generate-sequence-ledger", action="store_true")
    parser.add_argument("--offline-checkpoint-summary", default="")
    parser.add_argument("--offline-checkpoint-sha256", default="")
    parser.add_argument("--offline-checkpoint-commit", default="")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    hardware_root = Path(args.hardware_root)
    if not hardware_root.is_absolute():
        hardware_root = repo_root / hardware_root
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    if args.generate_sequence_ledger:
        if not args.offline_checkpoint_summary or not args.offline_checkpoint_sha256 or not args.offline_checkpoint_commit:
            print("sequence ledger generation requires --offline-checkpoint-summary, --offline-checkpoint-sha256, and --offline-checkpoint-commit", file=sys.stderr)
            return 2
        checkpoint = Path(args.offline_checkpoint_summary)
        if not checkpoint.is_absolute():
            checkpoint = repo_root / checkpoint
        evidence = RepositoryEvidence(repo_root, hardware_root.resolve(), output_dir.resolve())
        discover(evidence)
        try:
            ledger = generate_sequence_ledger(
                evidence,
                ledger_path=hardware_root / "p7_run_sequence_ledger.json",
                offline_checkpoint_summary=checkpoint.resolve(),
                offline_checkpoint_sha256=args.offline_checkpoint_sha256,
                offline_checkpoint_commit=args.offline_checkpoint_commit,
            )
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            print(f"P7_SEQUENCE_LEDGER_GENERATION: FAIL: {exc}", file=sys.stderr)
            return 1
        if args.json_summary:
            print(json.dumps(ledger, indent=2, ensure_ascii=False))
        else:
            print("P7_SEQUENCE_LEDGER_GENERATION: PASS")
            print(f"P7_SEQUENCE_LEDGER: {hardware_root / 'p7_run_sequence_ledger.json'}")
        return 0
    payload, returncode = summarize(repo_root, hardware_root, output_dir)
    if args.json_summary:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: {payload['P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET']}")
        print(f"P7_HARDWARE_EVIDENCE_SUMMARY: {output_dir / 'p7_final_summary.md'}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
