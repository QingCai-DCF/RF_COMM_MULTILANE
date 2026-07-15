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
import ctypes
import csv
import functools
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
CANONICAL_FULL_PART = "xc7z010clg400-1"
CANONICAL_LIVE_PART = "xc7z010"
CANONICAL_LIVE_DEVICE = "xc7z010_1"
CANONICAL_LIVE_IDCODE_HEX = "13722093"
CANONICAL_LIVE_IDCODE_BINARY = "00010011011100100010000010010011"
HISTORICAL_PREFLIGHT_PART_IDENTITY_REJECTED = "PART_IDENTITY_REJECTED"
HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED = (
    "IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED"
)
HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED = (
    "IDENTITY_PASS_HELPER_REAP_SHUTDOWN_TCL_CHAR_MAP_REJECTED"
)
HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED = (
    "IDENTITY_PASS_SHUTDOWN_BARRIERS_CANDIDATE_PROGRAMMED_WRITE_ALLOWLIST_REJECTED"
)
HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED = (
    "STAGE_AND_SHUTDOWN_PASS_BACKEND_RAW_PULSE_SEMANTICS_REJECTED"
)
HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED = (
    "STAGE_PASS_SHUTDOWN_PROGRAMMED_HELPER_EXIT_RACE_FORCED_CLEANUP"
)
HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED = (
    "STAGE_PASS_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING"
)
HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED = (
    "STAGE_AND_SHUTDOWN_PASS_BACKEND_RETRY_SEMANTICS_REJECTED"
)
HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE = (
    "STAGE_ABORTED_FOR_INSUFFICIENT_OUTER_INTERACTIVE_DEADLINE"
)
HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT = (
    "DIAGNOSTIC_SUFFIX_1M_JTAG_SINGLE_WORD_TRANSACTIONS_TIMED_OUT"
)
HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT = (
    "DIAGNOSTIC_SUFFIX_1M_JTAG_QUEUED_TRANSACTIONS_TIMED_OUT"
)
HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED = (
    "DIAGNOSTIC_SUFFIX_AXI4_QUEUED_CONTROL_COMMIT_ORDER_REJECTED"
)
HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED = (
    "DIAGNOSTIC_SUFFIX_AXI4_BURST_WORD_ORDER_REJECTED"
)
HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_SHUTDOWN_TCL_ARG_COUNT_REJECTED"
)
HISTORICAL_STAGE_PS_RESET_TARGET_UNIQUENESS_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_RESET_TARGET_UNIQUENESS_REJECTED"
)
HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_CHILD_TARGET_IDENTITY_REJECTED"
)
HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_JTAG_DEVICE_CARDINALITY_REJECTED"
)
HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_BOUNDARY_30_LANE0_REJECTED"
)
HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_FAILURE_CAPTURE_DOW_REJECTED"
)
HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_OUTPUT_CRC_SHA_DIVERGENCE_REJECTED"
)
HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_BOUNDARY_30_OBJECT_INTEGRITY_REJECTED"
)
HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_POST_WIPE_OUTPUT_CAPTURE_REJECTED"
)
HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_FAILURE_SNAPSHOT_MARKER_REJECTED"
)
HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_FAILURE_SNAPSHOT_MAILBOX_PUBLISHED_MARKER_REJECTED"
)
HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED"
)
HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED = (
    "DIAGNOSTIC_SUFFIX_PS_FUNCTIONAL_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED"
)
HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED = (
    "DIAGNOSTIC_SUFFIX_AXI4LITE_REJECTED_MULTIWORD_BURST"
)
HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED = (
    "DIAGNOSTIC_SUFFIX_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED"
)
EXPECTED_VIVADO_HELPER_ROLES = ("cs_server", "rdi_xsdb", "cmd", "conhost")
EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE = {
    "cs_server": "9bf0e15ffe162a96679c14b8117cf8ebe8a47b8032bee4ab8cb0317c112df536",
    "rdi_xsdb": "3193d8c4e7115e82e5b4ea6c2eb1aa8a7566bd5a9f9c78e9d901b9eab9d4ebfc",
    "cmd": "75320a519959cc6d089ea3eba33c38caccb7f138a025ea439bc9686cdb79ded4",
    "conhost": "a93cbb36b9c02364be6a72817174c46f94b66715549f279c6592ed659d237911",
}
APPROVED_VIVADO_HELPER_INITIAL_CLASSIFICATIONS = frozenset(
    {
        "SINGLE_EXACT_CS_SERVER",
        "DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
        "EXACT_R2_VIVADO_EXIT_HELPER_FOREST",
    }
)
VIVADO_HELPER_GRACE_SECONDS = 30.0
VIVADO_HELPER_MAX_TOPOLOGY_SAMPLE_GAP_SECONDS = 0.25
P7_TRACE_MAGIC = 0x52543750
HARDWARE_EXECUTION_LOCK_RELATIVE = Path(".hardware_authorization") / "P7_HARDWARE_EXECUTION.lock"
CHECKPOINT_RELATION_BOUND = "BOUND_TO_ACTIVE_OFFLINE_CHECKPOINT"
CHECKPOINT_RELATION_OLD_DIAGNOSTIC = "PRECHECKPOINT_OLD_COMMIT_READ_ONLY_DIAGNOSTIC"
CHECKPOINT_RELATION_OLD_FAILED_STAGE = "PRECHECKPOINT_OLD_COMMIT_FAILED_STAGE_DIAGNOSTIC"
CHECKPOINT_RELATIONS_HISTORICAL = frozenset(
    {CHECKPOINT_RELATION_OLD_DIAGNOSTIC, CHECKPOINT_RELATION_OLD_FAILED_STAGE}
)
CORE_READINESS_CHECKS = (
    "host_command_cache_disabled_or_isolated",
    "deadline_frozen_in_private_context",
    "active_transfer_obeys_absolute_deadline",
    "stop_abort_shutdown_observed_during_active_object",
    "shutdown_readback_verified",
    "failure_cleanup_shutdown_first",
    "failure_wipe_uses_private_validated_range",
    "integrity_crc_sha_immutable_chunk_snapshot",
    "critical_payload_copies_are_volatile_byte_verified",
    "first_error_diagnostic_is_atomic_and_first_only",
    "stage62_first_error_prepare_is_first_only",
    "first_error_capture_precedes_validation_and_is_input_bound",
    "stage62_diagnostic_fixed_ocm_section",
    "stage62_copy_four_snapshot_classification",
    "stage62_diagnostic_crc_publish_order",
    "stage62_only_microtest_bypasses_pl_and_is_disassembly_bound",
    "pre_repair_encode_raw_compared_to_fixed_input_reference",
    "p6_tx_mmio_readback_and_rx_boundaries_observed",
    "local_payload_buffers_are_64_byte_aligned",
    "end_to_end_output_compare_is_independent",
    "nonzero_output_canary_is_manifest_bound",
    "integrity_failure_snapshot_precedes_output_wipe",
    "integrity_failure_snapshot_mailbox_diagnostic",
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
    "native_payload_alignment_matrix_test",
    "native_stage62_diagnostic_matrix_test",
    "native_stage62_microtest_layout_test",
    "p7_python_and_codec_tests",
    "real_vitis_build_source_bound",
)
CORE_READINESS_SOURCES = (
    "software/ps_driver/p7_app_service.h",
    "software/ps_driver/p7_stage62_diagnostic.h",
    "software/ps_driver/p7_stage62_diagnostic.c",
    "software/ps_driver/p7_stage62_microtest.h",
    "software/ps_driver/p7_stage62_microtest.c",
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
    "software/ps_driver/ir_regs.h",
    "tools/p7_app_protocol.py",
    "tools/run_p7_ps_core_offline.py",
    "tools/p7_regression_evidence.py",
    "tools/run_p7_regression_suites.py",
    "scripts/build_p7_ps_runtime.py",
    "scripts/build_p7_ps_runtime.tcl",
    "tests/p7/test_p7_application.py",
    "tests/p7/ir_driver_payload_alignment_test.c",
    "tests/p7/p7_stage62_diagnostic_test.c",
    "tests/p7/p7_stage62_microtest_layout_test.c",
    "tests/test_p7_stage62_microtest.py",
    "tests/test_p7_regression_dedup.py",
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
    "software/ps_driver/p7_stage62_microtest.h",
    "software/ps_driver/p7_stage62_microtest.c",
    "scripts/hw/p7_ps_application_execute.tcl",
    "scripts/hw/run_p7_ps_application_stage_safe.py",
    "scripts/hw/run_p7_jtag_axi_stage_safe.py",
    "tools/p7_contained_launcher.py",
    "tools/p7_ps_mailbox_backend.py",
    "tools/run_p7_gate.py",
    "tools/run_p7_ps_core_offline.py",
    "tools/summarize_p7_hardware.py",
)
HISTORICAL_GIT_CRITICAL_SOURCES = (
    "scripts/hw/p7_hw_preflight.tcl",
    "scripts/hw/p7_jtag_axi_transactions.tcl",
    "scripts/hw/run_p7_jtag_axi_stage_safe.py",
    "tools/p7_contained_launcher.py",
    "tools/p7_hardware_safety.py",
    "tools/p7_jtag_backend.py",
    "tools/generate_p7_authorized_sequence_plan.py",
    "tools/run_p7_authorized_hardware_sequence.py",
    "tools/run_p7_gate.py",
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


@functools.lru_cache(maxsize=16)
def _registered_worktree_roots(repo_root_text: str) -> tuple[Path, ...]:
    """Return only worktree roots registered by this repository.

    Historical hardware records intentionally preserve the absolute checkout
    paths used at execution time.  A linked worktree must be able to validate
    those immutable records without treating an arbitrary absolute path as
    equivalent to its own checkout.  Git's registered worktree list is the
    fail-closed authority for that narrow relocation.
    """

    current = Path(repo_root_text).resolve(strict=False)
    try:
        completed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=current,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return (current,)
    if completed.returncode != 0:
        return (current,)
    roots: dict[str, Path] = {}
    for line in completed.stdout.splitlines():
        if not line.startswith("worktree "):
            continue
        value = line[len("worktree ") :].strip()
        if not value:
            continue
        candidate = Path(value).resolve(strict=False)
        roots[os.path.normcase(str(candidate))] = candidate
    current_key = os.path.normcase(str(current))
    if current_key not in roots:
        return (current,)
    return tuple(sorted(roots.values(), key=lambda item: len(str(item)), reverse=True))


@functools.lru_cache(maxsize=4096)
def _same_regular_file_contents(left_text: str, right_text: str) -> bool:
    left = Path(left_text)
    right = Path(right_text)
    try:
        if (
            left.is_symlink()
            or right.is_symlink()
            or not left.is_file()
            or not right.is_file()
            or left.stat().st_size != right.stat().st_size
        ):
            return False
        return sha256_file(left) == sha256_file(right)
    except OSError:
        return False


def _remap_registered_worktree_reference(raw: Path, repo_root: Path) -> Path:
    """Map an absolute reference only across equivalent registered worktrees."""

    recorded = raw.resolve(strict=False)
    current = repo_root.resolve(strict=False)
    try:
        recorded.relative_to(current)
        return recorded
    except ValueError:
        pass
    roots = _registered_worktree_roots(str(current))
    if not any(os.path.normcase(str(item)) == os.path.normcase(str(current)) for item in roots):
        return recorded
    for source_root in roots:
        if os.path.normcase(str(source_root)) == os.path.normcase(str(current)):
            continue
        try:
            relative = recorded.relative_to(source_root)
        except ValueError:
            continue
        remapped = (current / relative).resolve(strict=False)
        try:
            remapped.relative_to(current)
        except ValueError:
            return recorded
        if recorded.is_symlink() or remapped.is_symlink():
            return recorded
        recorded_exists = recorded.exists()
        remapped_exists = remapped.exists()
        if recorded_exists != remapped_exists:
            return recorded
        if recorded_exists:
            if recorded.is_file() != remapped.is_file() or recorded.is_dir() != remapped.is_dir():
                return recorded
            if recorded.is_file() and not _same_regular_file_contents(
                str(recorded), str(remapped)
            ):
                return recorded
            if not recorded.is_file() and not recorded.is_dir():
                return recorded
        return remapped
    return recorded


def _same_registered_worktree_location(
    left: Path | None, right: Path | None, repo_root: Path
) -> bool:
    """Compare provenance locations without requiring ignored originals.

    Content is deliberately not inferred here.  Callers use this only after
    frozen-file hashes have been validated; this helper proves that both path
    claims name the same repository-relative location in Git-registered
    worktrees.
    """

    if left is None or right is None:
        return False
    left_resolved = left.resolve(strict=False)
    right_resolved = right.resolve(strict=False)
    if left_resolved == right_resolved:
        return True
    current = repo_root.resolve(strict=False)
    roots = _registered_worktree_roots(str(current))
    if not any(os.path.normcase(str(item)) == os.path.normcase(str(current)) for item in roots):
        return False

    def relative_location(path: Path) -> Path | None:
        for root in roots:
            try:
                return path.relative_to(root)
            except ValueError:
                continue
        return None

    left_relative = relative_location(left_resolved)
    right_relative = relative_location(right_resolved)
    return (
        left_relative is not None
        and right_relative is not None
        and os.path.normcase(str(left_relative))
        == os.path.normcase(str(right_relative))
    )


def _argv_matches_with_registered_worktree_paths(
    observed: Any,
    expected: Sequence[str],
    repo_root: Path,
    *,
    path_indices: set[int],
) -> bool:
    if (
        not isinstance(observed, list)
        or len(observed) != len(expected)
        or not all(isinstance(item, str) for item in observed)
    ):
        return False
    for index, expected_value in enumerate(expected):
        observed_value = observed[index]
        if index in path_indices:
            if (
                not observed_value
                or not expected_value
                or not _same_registered_worktree_location(
                    Path(observed_value), Path(expected_value), repo_root
                )
            ):
                return False
        elif observed_value != expected_value:
            return False
    return True


@functools.lru_cache(maxsize=4096)
def _git_filtered_blob_id(repo_root_text: str, relative_text: str, path_text: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "hash-object", f"--path={relative_text}", path_text],
            cwd=Path(repo_root_text),
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip().lower()
    return value if completed.returncode == 0 and re.fullmatch(r"[0-9a-f]{40}", value) else None


def _sha256_matches_registered_materialization(
    path: Path, expected_sha256: str, repo_root: Path
) -> bool:
    """Accept CRLF/LF checkout materialization only with one identical Git blob."""

    canonical = path.resolve(strict=False)
    current = repo_root.resolve(strict=False)
    if canonical.is_symlink() or not canonical.is_file():
        return False
    if sha256_file(canonical) == expected_sha256:
        return True
    try:
        relative = canonical.relative_to(current)
    except ValueError:
        return False
    relative_text = relative.as_posix()
    current_blob = _git_filtered_blob_id(str(current), relative_text, str(canonical))
    if current_blob is None:
        return False
    for worktree in _registered_worktree_roots(str(current)):
        if os.path.normcase(str(worktree)) == os.path.normcase(str(current)):
            continue
        alternate = (worktree / relative).resolve(strict=False)
        if (
            alternate.is_symlink()
            or not alternate.is_file()
            or sha256_file(alternate) != expected_sha256
        ):
            continue
        alternate_blob = _git_filtered_blob_id(
            str(current), relative_text, str(alternate)
        )
        if alternate_blob == current_blob:
            return True
    return False


def resolve_reference(value: Any, *, document: Path, repo_root: Path) -> Path | None:
    if not isinstance(value, (str, os.PathLike)) or not str(value).strip():
        return None
    raw = Path(str(value))
    if raw.is_absolute():
        return _remap_registered_worktree_reference(raw, repo_root)
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


def _normalized_windows_process_path(value: Any) -> str:
    return str(Path(str(value)).resolve(strict=False)).replace("/", "\\").casefold()


def _audited_windows_system_directory() -> Path | None:
    if os.name == "nt":
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer))
        except (AttributeError, OSError):
            return None
        return Path(buffer.value).resolve(strict=False) if 0 < int(length) < len(buffer) else None
    return (Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32").resolve(strict=False)


def _derived_vivado_helper_paths(argv: Any) -> dict[str, str] | None:
    if (
        not isinstance(argv, list)
        or not argv
        or not all(isinstance(item, str) and bool(item) for item in argv)
    ):
        return None
    executable = Path(argv[0]).resolve(strict=False)
    if executable.name.casefold() != "vivado.bat":
        return None
    helper_dir = executable.parent / "unwrapped" / "win64.o"
    system_directory = _audited_windows_system_directory()
    if system_directory is None:
        return None
    return {
        "cs_server": _normalized_windows_process_path(helper_dir / "cs_server.exe"),
        "rdi_xsdb": _normalized_windows_process_path(helper_dir / "rdi_xsdb.exe"),
        "cmd": _normalized_windows_process_path(system_directory / "cmd.exe"),
        "conhost": _normalized_windows_process_path(system_directory / "conhost.exe"),
    }


def _normalize_v2_helper_processes(
    processes: Any,
    helper_paths: Mapping[str, str],
    *,
    allow_empty: bool,
) -> dict[int, tuple[int, str, str, int]] | None:
    if not isinstance(processes, list) or (not processes and not allow_empty):
        return None
    path_to_role = {path: role for role, path in helper_paths.items()}
    if len(path_to_role) != len(EXPECTED_VIVADO_HELPER_ROLES):
        return None
    normalized: dict[int, tuple[int, str, str, int]] = {}
    parent_activity: dict[int, bool] = {}
    ordered_ids: list[int] = []
    for item in processes:
        if not isinstance(item, dict) or set(item) != {
            "pid",
            "parent_pid",
            "parent_active_globally",
            "image_path",
            "creation_time_100ns",
        }:
            return None
        process_id = item.get("pid")
        parent_id = item.get("parent_pid")
        parent_active_globally = item.get("parent_active_globally")
        image_path = item.get("image_path")
        creation_time = item.get("creation_time_100ns")
        if (
            type(process_id) is not int
            or type(parent_id) is not int
            or type(parent_active_globally) is not bool
            or type(image_path) is not str
            or type(creation_time) is not int
            or process_id <= 0
            or parent_id <= 0
            or creation_time <= 0
            or process_id == parent_id
            or process_id in normalized
        ):
            return None
        path = _normalized_windows_process_path(image_path)
        role = path_to_role.get(path)
        if role is None:
            return None
        ordered_ids.append(process_id)
        normalized[process_id] = (parent_id, path, role, creation_time)
        parent_activity[process_id] = parent_active_globally
    if ordered_ids != sorted(ordered_ids) or any(
        parent_activity[process_id] is not (parent_id in normalized)
        for process_id, (parent_id, _path, _role, _creation_time) in normalized.items()
    ):
        return None
    return normalized


def _classify_v2_initial_helper_topology(
    normalized: Mapping[int, tuple[int, str, str, int]],
) -> str:
    counts = {role: 0 for role in EXPECTED_VIVADO_HELPER_ROLES}
    for _parent_id, _path, role, _creation_time in normalized.values():
        counts[role] += 1
    edges = sorted(
        (normalized[parent_id][2], role)
        for _process_id, (parent_id, _path, role, _creation_time) in normalized.items()
        if parent_id in normalized
    )
    if counts == {"cs_server": 1, "rdi_xsdb": 0, "cmd": 0, "conhost": 0}:
        return "SINGLE_EXACT_CS_SERVER" if not edges else "UNAPPROVED"
    if counts == {"cs_server": 2, "rdi_xsdb": 0, "cmd": 0, "conhost": 0}:
        return (
            "DIRECT_PARENT_CHILD_EXACT_CS_SERVER"
            if edges == [("cs_server", "cs_server")]
            else "UNAPPROVED"
        )
    if counts != {"cs_server": 2, "rdi_xsdb": 1, "cmd": 1, "conhost": 2}:
        return "UNAPPROVED"
    roots = [
        (process_id, parent_id, role)
        for process_id, (parent_id, _path, role, _creation_time) in normalized.items()
        if parent_id not in normalized
    ]
    expected_edges = sorted(
        [("cs_server", "cs_server"), ("cmd", "conhost"), ("cmd", "rdi_xsdb")]
    )
    return (
        "EXACT_R2_VIVADO_EXIT_HELPER_FOREST"
        if edges == expected_edges
        and sorted(role for _process_id, _parent_id, role in roots)
        == sorted(["cs_server", "cmd", "conhost"])
        and len({parent_id for _process_id, parent_id, _role in roots}) == 3
        else "UNAPPROVED"
    )


def _v2_process_containment_errors(record: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    containment_kind = record.get("containment_kind")
    windows_job = containment_kind == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE"
    posix_group = containment_kind == "POSIX_PROCESS_GROUP"
    append_error(errors, windows_job or posix_group, f"{label} containment_kind is missing/unsupported")
    append_error(errors, record.get("containment_cleanup_attempted") is False, f"{label} attempted forced containment cleanup")
    append_error(errors, record.get("containment_cleanup_terminated") is False, f"{label} required forced containment termination")
    for key in (
        "expected_tool_daemon_grace_used",
        "expected_tool_daemon_topology_monotonic",
        "expected_tool_daemon_hashes_verified",
        "expected_tool_daemon_prelaunch_hashes_verified",
        "expected_tool_daemon_postexit_hashes_verified",
        "expected_tool_daemon_topology_terminal_empty",
        "process_exit_race_rechecked",
        "process_identity_query_retried",
    ):
        append_error(errors, type(record.get(key)) is bool, f"{label} {key} is not boolean")
    for key in ("process_identity_query_retry_count", "process_exit_race_recheck_count"):
        append_error(errors, type(record.get(key)) is int and int(record.get(key)) >= 0, f"{label} {key} is missing/malformed")
    for key, message in (
        ("containment_query_error", "containment identity query error"),
        ("expected_tool_daemon_topology_error", "helper topology error"),
        ("expected_tool_daemon_hash_error", "helper aggregate hash error"),
        ("expected_tool_daemon_prelaunch_hash_error", "helper prelaunch hash error"),
        ("expected_tool_daemon_postexit_hash_error", "helper postexit hash error"),
    ):
        append_error(errors, record.get(key) == "", f"{label} has a {message}")

    retry_count = record.get("process_identity_query_retry_count")
    recheck_count = record.get("process_exit_race_recheck_count")
    transient_errors = record.get("process_identity_query_transient_errors", [])
    append_error(
        errors,
        isinstance(transient_errors, list)
        and len(transient_errors) <= 1
        and all(isinstance(item, str) and bool(item) for item in transient_errors),
        f"{label} identity-query transient-error provenance is malformed",
    )
    append_error(errors, type(retry_count) is int and 0 <= retry_count <= 1, f"{label} identity-query retry count exceeds the global bound")
    append_error(errors, type(recheck_count) is int and 0 <= recheck_count <= 2, f"{label} exit-race recheck count exceeds the global bound")
    append_error(errors, record.get("process_identity_query_retried") is (retry_count == 1), f"{label} identity-query retry boolean/count mismatch")
    append_error(errors, record.get("process_exit_race_rechecked") is (isinstance(recheck_count, int) and recheck_count > 0), f"{label} exit-race recheck boolean/count mismatch")
    if isinstance(transient_errors, list) and transient_errors:
        append_error(errors, retry_count == 1 and isinstance(recheck_count, int) and recheck_count >= 1, f"{label} transient identity error is not bound to the single retry/final empty proof")

    if posix_group:
        append_error(errors, record.get("expected_tool_daemon_paths") == [], f"{label} POSIX record contains Windows helper paths")
        append_error(errors, record.get("expected_tool_daemon_grace_used") is False, f"{label} POSIX record claims Windows helper grace")
        append_error(errors, type(record.get("expected_tool_daemon_grace_seconds")) in {int, float} and not isinstance(record.get("expected_tool_daemon_grace_seconds"), bool) and float(record.get("expected_tool_daemon_grace_seconds")) == 0.0, f"{label} POSIX record contains a Windows helper grace duration")
        append_error(errors, type(record.get("expected_tool_daemon_grace_elapsed_seconds")) in {int, float} and not isinstance(record.get("expected_tool_daemon_grace_elapsed_seconds"), bool) and float(record.get("expected_tool_daemon_grace_elapsed_seconds")) == 0.0, f"{label} POSIX record contains Windows helper grace elapsed time")
        append_error(errors, record.get("expected_tool_daemon_classification") == "NONE", f"{label} POSIX record contains a Windows helper classification")
        append_error(errors, record.get("descendant_paths_seen") == [] and record.get("descendant_processes_seen") == [], f"{label} POSIX record contains Windows helper descendants")
        append_error(errors, record.get("expected_tool_daemon_topology_snapshots") == [], f"{label} POSIX record contains Windows topology snapshots")
        append_error(errors, record.get("expected_tool_daemon_topology_sample_elapsed_seconds") == [], f"{label} POSIX record contains Windows topology samples")
        append_error(errors, record.get("expected_tool_daemon_topology_revalidation_count") == 0 and not isinstance(record.get("expected_tool_daemon_topology_revalidation_count"), bool), f"{label} POSIX record contains Windows topology revalidation")
        append_error(errors, record.get("expected_tool_daemon_topology_monotonic") is False, f"{label} POSIX record claims monotonic Windows topology")
        append_error(errors, type(record.get("expected_tool_daemon_topology_max_sample_gap_seconds")) in {int, float} and not isinstance(record.get("expected_tool_daemon_topology_max_sample_gap_seconds"), bool) and float(record.get("expected_tool_daemon_topology_max_sample_gap_seconds")) == 0.0, f"{label} POSIX record contains a Windows topology sample gap")
        append_error(errors, record.get("expected_tool_daemon_topology_terminal_empty") is False, f"{label} POSIX record claims Windows terminal EMPTY topology")
        for key in (
            "expected_tool_daemon_hashes_verified",
            "expected_tool_daemon_prelaunch_hashes_verified",
            "expected_tool_daemon_postexit_hashes_verified",
        ):
            append_error(errors, record.get(key) is False, f"{label} POSIX record claims Windows helper hash verification")
        for key in (
            "expected_tool_daemon_sha256_by_role",
            "expected_tool_daemon_prelaunch_sha256_by_role",
            "expected_tool_daemon_postexit_sha256_by_role",
        ):
            append_error(errors, record.get(key) == {}, f"{label} POSIX record contains Windows helper hashes")
        append_error(errors, retry_count == 0 and record.get("process_identity_query_retried") is False, f"{label} POSIX record contains a Windows identity retry")
        append_error(errors, recheck_count == 0 and record.get("process_exit_race_rechecked") is False, f"{label} POSIX record contains a Windows exit-race recheck")
        return errors

    helper_paths = _derived_vivado_helper_paths(record.get("argv"))
    recorded_paths = record.get("expected_tool_daemon_paths")
    if helper_paths is None:
        append_error(errors, recorded_paths == [], f"{label} non-Vivado process records helper paths")
    else:
        expected_path_list = [helper_paths[role] for role in EXPECTED_VIVADO_HELPER_ROLES]
        recorded_normalized = (
            [_normalized_windows_process_path(path) for path in recorded_paths]
            if isinstance(recorded_paths, list) and all(isinstance(path, str) for path in recorded_paths)
            else []
        )
        append_error(errors, recorded_normalized == expected_path_list, f"{label} helper paths are not exactly derived from argv[0]")
        for prefix in ("expected_tool_daemon_prelaunch", "expected_tool_daemon_postexit"):
            phase = "prelaunch" if prefix.endswith("prelaunch") else "postexit"
            append_error(errors, record.get(f"{prefix}_hashes_verified") is True, f"{label} helper {phase} hashes were not verified")
            append_error(errors, record.get(f"{prefix}_sha256_by_role") == EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE, f"{label} helper {phase} hash map mismatch")
        append_error(errors, record.get("expected_tool_daemon_hashes_verified") is True, f"{label} aggregate helper hashes were not verified")
        append_error(errors, record.get("expected_tool_daemon_sha256_by_role") == EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE, f"{label} aggregate helper hash map mismatch")
    if helper_paths is None:
        for key in (
            "expected_tool_daemon_hashes_verified",
            "expected_tool_daemon_prelaunch_hashes_verified",
            "expected_tool_daemon_postexit_hashes_verified",
        ):
            append_error(errors, record.get(key) is False, f"{label} non-Vivado process claims helper hash verification")
        for key in (
            "expected_tool_daemon_sha256_by_role",
            "expected_tool_daemon_prelaunch_sha256_by_role",
            "expected_tool_daemon_postexit_sha256_by_role",
        ):
            append_error(errors, record.get(key) == {}, f"{label} non-Vivado process records helper hashes")

    samples_raw = record.get("expected_tool_daemon_topology_sample_elapsed_seconds")
    samples = (
        [float(value) for value in samples_raw]
        if isinstance(samples_raw, list)
        and samples_raw
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in samples_raw)
        else []
    )
    append_error(errors, bool(samples), f"{label} Windows containment topology samples are missing/malformed")
    append_error(errors, samples == sorted(samples) and all(0 <= value <= VIVADO_HELPER_GRACE_SECONDS for value in samples), f"{label} topology sample timeline is invalid")
    append_error(errors, bool(samples) and samples[0] <= VIVADO_HELPER_MAX_TOPOLOGY_SAMPLE_GAP_SECONDS, f"{label} initial topology sample exceeds 250 ms")
    gaps = [max(0.0, current - previous) for previous, current in zip(samples, samples[1:])]
    recomputed_gap = round(max(gaps, default=0.0), 6)
    max_gap = record.get("expected_tool_daemon_topology_max_sample_gap_seconds")
    append_error(errors, isinstance(max_gap, (int, float)) and not isinstance(max_gap, bool) and round(float(max_gap), 6) == recomputed_gap, f"{label} topology max-sample-gap record mismatch")
    append_error(errors, recomputed_gap <= VIVADO_HELPER_MAX_TOPOLOGY_SAMPLE_GAP_SECONDS, f"{label} topology sampling gap exceeds 250 ms")
    snapshots = record.get("expected_tool_daemon_topology_snapshots")
    append_error(errors, isinstance(snapshots, list) and bool(snapshots) and all(isinstance(item, dict) for item in snapshots), f"{label} topology snapshots are missing/malformed")
    snapshots = snapshots if isinstance(snapshots, list) else []
    append_error(
        errors,
        bool(snapshots)
        and all(set(item) == {"classification", "elapsed_seconds", "processes"} for item in snapshots if isinstance(item, dict)),
        f"{label} topology snapshot fields are not exact",
    )
    snapshot_times = [item.get("elapsed_seconds") for item in snapshots if isinstance(item, dict)]
    snapshot_times_valid = (
        len(snapshot_times) == len(snapshots)
        and bool(snapshot_times)
        and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in snapshot_times)
    )
    snapshot_time_values = [float(value) for value in snapshot_times] if snapshot_times_valid else []
    append_error(errors, snapshot_times_valid, f"{label} topology snapshot times are malformed")
    append_error(errors, bool(snapshot_time_values) and snapshot_time_values == sorted(snapshot_time_values), f"{label} topology snapshot chronology is invalid")
    append_error(errors, bool(snapshot_time_values) and bool(samples) and all(value in samples for value in snapshot_time_values), f"{label} topology snapshots are not bound to sample times")
    append_error(errors, bool(snapshot_time_values) and bool(samples) and snapshot_time_values[-1] == samples[-1], f"{label} terminal EMPTY snapshot is not the final topology sample")
    append_error(errors, bool(snapshots) and snapshots[-1].get("classification") == "EMPTY" and snapshots[-1].get("processes") == [], f"{label} topology does not terminate in EMPTY")
    append_error(errors, record.get("expected_tool_daemon_topology_terminal_empty") is True, f"{label} does not prove terminal EMPTY topology")

    grace_used = record.get("expected_tool_daemon_grace_used") is True
    grace_seconds = record.get("expected_tool_daemon_grace_seconds")
    grace_elapsed = record.get("expected_tool_daemon_grace_elapsed_seconds")
    revalidation_count = record.get("expected_tool_daemon_topology_revalidation_count")
    append_error(errors, type(revalidation_count) is int and revalidation_count >= 0, f"{label} topology revalidation count is malformed")
    if grace_used:
        append_error(errors, helper_paths is not None, f"{label} grants helper grace to a non-Vivado process")
        append_error(errors, grace_seconds == VIVADO_HELPER_GRACE_SECONDS, f"{label} helper grace is not the fixed 30-second window")
        append_error(errors, isinstance(grace_elapsed, (int, float)) and not isinstance(grace_elapsed, bool) and samples and samples[-1] <= float(grace_elapsed) <= VIVADO_HELPER_GRACE_SECONDS, f"{label} helper grace elapsed time is invalid")
        append_error(errors, record.get("expected_tool_daemon_topology_monotonic") is True, f"{label} helper topology is not monotonic")
        transient_errors = record.get("process_identity_query_transient_errors", [])
        transient_count = len(transient_errors) if isinstance(transient_errors, list) else 0
        append_error(errors, type(revalidation_count) is int and revalidation_count >= 1 and len(samples) == revalidation_count + 2 + transient_count, f"{label} topology sample/revalidation count mismatch")
        append_error(errors, len(samples) >= 2 and bool(snapshot_time_values) and snapshot_time_values[0] == samples[1], f"{label} initial helper snapshot is not bound to the post-identity sample")
        initial_processes = snapshots[0].get("processes") if snapshots else None
        initial = _normalize_v2_helper_processes(initial_processes, helper_paths or {}, allow_empty=False)
        initial_classification = _classify_v2_initial_helper_topology(initial or {})
        append_error(errors, initial_classification in APPROVED_VIVADO_HELPER_INITIAL_CLASSIFICATIONS, f"{label} initial helper topology is not independently approved")
        append_error(errors, record.get("expected_tool_daemon_classification") == initial_classification and snapshots and snapshots[0].get("classification") == initial_classification, f"{label} initial helper classification mismatch")
        append_error(errors, record.get("descendant_processes_seen") == initial_processes, f"{label} initial descendant identities do not bind the first snapshot")
        append_error(errors, record.get("descendant_paths_seen") == [item.get("image_path") for item in initial_processes] if isinstance(initial_processes, list) else False, f"{label} initial descendant paths do not bind identities")
        previous_ids = set(initial or {})
        for index, snapshot in enumerate(snapshots[1:-1], 1):
            current = _normalize_v2_helper_processes(snapshot.get("processes"), helper_paths or {}, allow_empty=False)
            current_ids = set(current or {})
            valid_subset = (
                initial is not None
                and current is not None
                and bool(current_ids)
                and current_ids < previous_ids
                and current_ids <= set(initial)
                and all(current[pid] == initial[pid] for pid in current_ids)
            )
            append_error(errors, valid_subset, f"{label} topology snapshot {index} is not an immutable strict shrink")
            append_error(errors, snapshot.get("classification") == f"STRICT_SHRINK_SUBSET_OF_{initial_classification}", f"{label} topology snapshot {index} classification mismatch")
            previous_ids = current_ids if current is not None else set()
    else:
        append_error(
            errors,
            type(grace_seconds) in {int, float}
            and not isinstance(grace_seconds, bool)
            and float(grace_seconds) == 0.0
            and type(grace_elapsed) in {int, float}
            and not isinstance(grace_elapsed, bool)
            and float(grace_elapsed) == 0.0,
            f"{label} records grace duration without helper grace",
        )
        append_error(errors, record.get("expected_tool_daemon_classification") == "NONE", f"{label} records a helper classification without grace")
        append_error(errors, record.get("descendant_paths_seen") == [] and record.get("descendant_processes_seen") == [], f"{label} records descendants without helper grace")
        append_error(errors, record.get("expected_tool_daemon_topology_monotonic") is False, f"{label} records monotonic helper topology without grace")
        append_error(errors, revalidation_count == 0, f"{label} records topology revalidation without grace")
        append_error(errors, len(snapshots) == 1, f"{label} no-grace topology must contain only terminal EMPTY")
        append_error(errors, len(samples) in {1, 2}, f"{label} no-grace topology sample count is invalid")
    return errors


def process_record_errors(record: Any, label: str, *, document: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{label} process record missing"]
    append_error(errors, record.get("returncode") == 0, f"{label} returncode is not exactly 0")
    for key in ("timed_out", "abort_seen", "interrupted"):
        append_error(errors, record.get(key, False) is False, f"{label} reports {key}=true")
    append_error(
        errors,
        record.get("process_tree_terminated", False) is False,
        f"{label} reports process_tree_terminated=true",
    )
    append_error(errors, record.get("process_tree_reaped") is True, f"{label} does not prove process_tree_reaped=true")
    append_error(errors, record.get("containment_assigned") is True, f"{label} does not prove containment assignment")
    append_error(errors, record.get("containment_closed") is True, f"{label} does not prove containment closure")
    append_error(errors, record.get("descendant_count_after") == 0, f"{label} does not prove zero descendants after reap")
    errors.extend(_v2_process_containment_errors(record, label))
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


def normalize_p7_idcode(value: Any) -> str:
    clean = str(value or "").strip().replace("_", "")
    if re.fullmatch(r"[01]{32}", clean):
        return f"{int(clean, 2):08X}"
    match = re.fullmatch(r"(?:0[xX])?([0-9A-Fa-f]{8})", clean)
    return match.group(1).upper() if match else ""


def raw_marker_path(candidate: Candidate) -> Path:
    return candidate.path.parent / (
        "p7_jtag_axi_raw_result.txt" if candidate.kind == "jtag" else "p7_ps_application_raw_result.log"
    )


def raw_markers(candidate: Candidate) -> tuple[dict[str, str], list[str]]:
    return parse_marker_text(marker_text(raw_marker_path(candidate)))


def _authorized_shutdown_path(candidate: Candidate, *, repo_root: Path) -> Path | None:
    """Return the shutdown image bound by the candidate's immutable safety record."""

    if candidate.kind == "ps":
        frozen = candidate.data.get("frozen_shutdown")
        frozen_path = resolve_reference(
            frozen.get("path") if isinstance(frozen, dict) else None,
            document=candidate.path,
            repo_root=repo_root,
        )
        if frozen_path is not None:
            return frozen_path
    safety = candidate.data.get("safety_validation")
    artifacts = safety.get("artifacts") if isinstance(safety, dict) else None
    shutdown = artifacts.get("shutdown_bitstream") if isinstance(artifacts, dict) else None
    return resolve_reference(
        shutdown.get("path") if isinstance(shutdown, dict) else None,
        document=candidate.path,
        repo_root=repo_root,
    )


def shutdown_errors(
    candidate: Candidate,
    which: str,
    *,
    require: bool = True,
    evidence: RepositoryEvidence | None = None,
) -> list[str]:
    errors: list[str] = []
    block = candidate.data.get(f"shutdown_{which}")
    if not isinstance(block, dict):
        return [f"shutdown-{which} record missing"] if require else []
    repo_root = evidence.repo_root if evidence is not None else candidate.path.parent
    errors.extend(
        process_record_errors(
            block,
            f"shutdown-{which}",
            document=candidate.path,
            repo_root=repo_root,
        )
    )
    append_error(errors, block.get("passed") is True, f"shutdown-{which} passed is not true")
    append_error(errors, block.get("attempted") is True, f"shutdown-{which} was not attempted")
    append_error(
        errors,
        block.get("programming_attempted") is True,
        f"shutdown-{which} does not prove programming_attempted=true",
    )
    result_path = resolve_reference(
        block.get("result_file"), document=candidate.path, repo_root=repo_root
    )
    if result_path is None:
        result_path = candidate.path.parent / f"shutdown_{which}_result.txt"
        if candidate.kind == "jtag":
            result_path = candidate.path.parent / f"p7_shutdown_{which}_result.txt"
    result_markers, result_duplicates = parse_marker_text(marker_text(result_path))
    append_error(errors, result_path.is_file(), f"shutdown-{which} fresh result file missing")
    append_error(errors, not result_duplicates, f"shutdown-{which} fresh result contains duplicate markers: {sorted(set(result_duplicates))}")
    append_error(
        errors,
        result_markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1",
        f"shutdown-{which} fresh result lacks exact P7_TCL_PROGRAMMING_ATTEMPTED=1",
    )
    tfdu_value = result_markers.get("TFDU_SHUTDOWN_PROGRAMMED", "")
    append_error(
        errors,
        bool(tfdu_value),
        f"shutdown-{which} fresh result lacks TFDU_SHUTDOWN_PROGRAMMED",
    )
    authorized_shutdown = _authorized_shutdown_path(candidate, repo_root=repo_root)
    programmed_shutdown = resolve_reference(
        tfdu_value, document=result_path, repo_root=repo_root
    )
    append_error(
        errors,
        authorized_shutdown is not None
        and programmed_shutdown is not None
        and programmed_shutdown == authorized_shutdown,
        f"shutdown-{which} fresh result path does not match the authorized shutdown bit",
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


def common_runner_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    *,
    accepted_historical_source: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
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
        if accepted_historical_source is None:
            actual_head = current_repository_head(evidence)
            append_error(errors, actual_head is not None, "unable to read current repository HEAD")
            append_error(errors, actual_head == source_requested, "hardware source commit does not match current repository HEAD")
        else:
            historical_source = str(accepted_historical_source).lower()
            append_error(errors, bool(COMMIT_RE.fullmatch(historical_source)), "accepted historical source commit is missing/malformed")
            append_error(errors, source_requested == historical_source, "hardware source commit does not match accepted historical source")
            actual_head = current_repository_head(evidence)
            append_error(errors, actual_head is not None, "unable to read current repository HEAD for historical source validation")
            if actual_head is not None:
                errors.extend(
                    _git_source_ancestry_errors(
                        evidence,
                        old_commit=historical_source,
                        active_commit=actual_head,
                    )
                )
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
    append_error(
        errors,
        str(auth_fields.get("EXPECTED_PART", "")).casefold() == CANONICAL_FULL_PART.casefold(),
        "authorization EXPECTED_PART is not the one canonical full part",
    )
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
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_PART", "")).casefold() == provenance["expected_part"].casefold(), "canonical part compatibility marker mismatch")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_CANONICAL_PART", "")).casefold() == CANONICAL_FULL_PART.casefold(), "canonical full part marker mismatch")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_LIVE_PART", "")).casefold() == CANONICAL_LIVE_PART.casefold(), "exact live part mismatch")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_LIVE_DEVICE", "")).casefold() == CANONICAL_LIVE_DEVICE.casefold(), "exact live device mismatch")
    append_error(errors, str(target.get("P7_HW_PREFLIGHT_DEVICE", "")).casefold() == CANONICAL_LIVE_DEVICE.casefold(), "live device compatibility marker mismatch")
    append_error(errors, normalize_p7_idcode(target.get("P7_HW_PREFLIGHT_LIVE_IDCODE")) == CANONICAL_LIVE_IDCODE_HEX, "exact live IDCODE mismatch")
    append_error(errors, normalize_p7_idcode(target.get("P7_HW_PREFLIGHT_IDCODE")) == CANONICAL_LIVE_IDCODE_HEX, "live IDCODE compatibility marker mismatch")
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
        "P7_HW_PREFLIGHT_DEVICE",
        "P7_HW_PREFLIGHT_IDCODE",
        "P7_HW_PREFLIGHT_CANONICAL_PART",
        "P7_HW_PREFLIGHT_LIVE_PART",
        "P7_HW_PREFLIGHT_LIVE_DEVICE",
        "P7_HW_PREFLIGHT_LIVE_IDCODE",
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
                if label == "frozen_shutdown":
                    selected_shutdown = provenance_artifacts.get("shutdown_bitstream")
                    selected_sha = (
                        str(selected_shutdown.get("actual_sha256", "")).lower()
                        if isinstance(selected_shutdown, dict)
                        else ""
                    )
                    append_error(
                        errors,
                        str(record.get("actual_sha256", "")).lower() == selected_sha,
                        "PS frozen shutdown SHA256 does not bind the authorized shutdown image",
                    )
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
    append_error(errors, observed_raw_markers.get("P7_HW_CANONICAL_PART", "").casefold() == CANONICAL_FULL_PART.casefold(), "raw stage canonical full part mismatch")
    append_error(errors, observed_raw_markers.get("P7_HW_LIVE_PART", "").casefold() == CANONICAL_LIVE_PART.casefold(), "raw stage live part mismatch")
    append_error(errors, observed_raw_markers.get("P7_HW_LIVE_DEVICE", "").casefold() == CANONICAL_LIVE_DEVICE.casefold(), "raw stage live device mismatch")
    append_error(errors, normalize_p7_idcode(observed_raw_markers.get("P7_HW_LIVE_IDCODE")) == CANONICAL_LIVE_IDCODE_HEX, "raw stage live IDCODE mismatch")
    if candidate.kind == "ps":
        append_error(errors, observed_raw_markers.get("P7_XSDB_LIVE_DEVICE", "").casefold() == CANONICAL_LIVE_PART.casefold(), "raw PS XSDB live device mismatch")
        append_error(errors, normalize_p7_idcode(observed_raw_markers.get("P7_XSDB_LIVE_IDCODE")) == CANONICAL_LIVE_IDCODE_HEX, "raw PS XSDB live IDCODE mismatch")
        append_error(errors, normalize_p7_idcode(observed_raw_markers.get("P7_XSDB_PREFLIGHT_IDCODE")) == CANONICAL_LIVE_IDCODE_HEX, "raw PS preflight IDCODE mismatch")

    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))
    for which in ("before", "after"):
        block = data.get(f"shutdown_{which}")
        provenance[f"shutdown_{which}"] = {
            "returncode": block.get("returncode") if isinstance(block, dict) else None,
            "passed": block.get("passed") if isinstance(block, dict) else None,
            "attempted": block.get("attempted") if isinstance(block, dict) else None,
            "programming_attempted": block.get("programming_attempted") if isinstance(block, dict) else None,
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


def validate_safe_idle(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    *,
    accepted_historical_source: str | None = None,
) -> StageResult:
    errors, provenance = common_runner_errors(
        candidate,
        evidence,
        accepted_historical_source=accepted_historical_source,
    )
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
        checks={
            "non_transmitting_semantic_mode": not errors,
            "shutdown_before_after": not shutdown_errors(candidate, "before", evidence=evidence)
            and not shutdown_errors(candidate, "after", evidence=evidence),
        },
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
    data = candidate.data
    observed, _duplicates = raw_markers(candidate)
    _event_path, events, _event_errors = load_authorized_events(candidate)
    mutation_events = {"shutdown_before_started", "candidate_started", "shutdown_after_started"}
    return (
        _candidate_programmed(candidate)
        or any(
            data.get(key) is True
            for key in (
                "programmed_fpga",
                "programmed_shutdown_before",
                "programmed_shutdown_after",
                "drove_tfdu_txd",
                "enabled_tfdu_receiver",
            )
        )
        or isinstance(data.get("shutdown_before"), dict)
        or isinstance(data.get("shutdown_after"), dict)
        or observed.get("P7_CANDIDATE_PROGRAMMED") == "1"
        or observed.get("P7_PS_CANDIDATE_PROGRAMMED") == "1"
        or observed.get("P7_PS_ELF_DOWNLOADED") == "1"
        or any(str(item.get("event", "")) in mutation_events for item in events)
    )


def _candidate_source_commit(candidate: Candidate) -> str:
    safety = candidate.data.get("safety_validation")
    return str(safety.get("source_commit_requested", "")).lower() if isinstance(safety, dict) else ""


def _historical_preflight_variant(candidate: Candidate) -> str:
    preflight_path = candidate.path.parent / (
        "p7_hw_preflight_result.txt" if candidate.kind == "ps" else "p7_preflight_result.txt"
    )
    markers, duplicates = parse_marker_text(marker_text(preflight_path))
    if duplicates:
        return "UNKNOWN"
    if markers == {
        "P7_HW_PREFLIGHT_AUTHORIZED": "0",
        "P7_HW_PREFLIGHT_READ_ONLY": "1",
        "P7_HW_PREFLIGHT_RESULT": "FAIL",
        "P7_HW_PREFLIGHT_ERROR": "P7 expected exactly one authorized part match; found 0",
    }:
        return HISTORICAL_PREFLIGHT_PART_IDENTITY_REJECTED
    if markers == {
        "P7_HW_PREFLIGHT_AUTHORIZED": "1",
        "P7_HW_PREFLIGHT_READ_ONLY": "1",
        "P7_HW_PREFLIGHT_BOARD_ID": "210512180081",
        "P7_HW_PREFLIGHT_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_PREFLIGHT_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PREFLIGHT_PART": CANONICAL_FULL_PART,
        "P7_HW_PREFLIGHT_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_PREFLIGHT_CANONICAL_PART": CANONICAL_FULL_PART,
        "P7_HW_PREFLIGHT_LIVE_PART": CANONICAL_LIVE_PART,
        "P7_HW_PREFLIGHT_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PREFLIGHT_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_PREFLIGHT_RESULT": "PASS",
    }:
        preflight_key = "preflight" if candidate.kind == "ps" else "preflight_process"
        preflight = candidate.data.get(preflight_key)
        shutdown_after = candidate.data.get("shutdown_after")
        stage_process = candidate.data.get("stage_process")
        if candidate.kind == "ps":
            shutdown_before = candidate.data.get("shutdown_before")
            expected_failures = [
                "shutdown process returned nonzero exit code: 41",
                "TFDU_SHUTDOWN_PROGRAMMED marker missing from fresh result file",
                "P7_SHUTDOWN_RESULT=PASS marker missing from fresh result file",
                "P7_TCL_PROGRAMMING_ATTEMPTED=1 marker missing from fresh result file",
            ]
            if (
                candidate.marker == "FAIL_SHUTDOWN_AFTER"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and isinstance(shutdown_after, dict)
                and all(
                    shutdown.get("returncode") == 41
                    and shutdown.get("passed") is False
                    and shutdown.get("programming_attempted") is None
                    and shutdown.get("process_tree_reaped") is True
                    and shutdown.get("process_tree_terminated") is False
                    and shutdown.get("failures") == expected_failures
                    for shutdown in (shutdown_before, shutdown_after)
                )
                and candidate.data.get("internal_error")
                == "RuntimeError: shutdown-before requires rc=0 plus TFDU_SHUTDOWN_PROGRAMMED"
                and candidate.data.get("ps_process") is None
                and candidate.data.get("programmed_candidate") is False
                and candidate.data.get("started_ps_elf") is False
                and "P7_JTAG_STAGE_ERROR=P7 JTAG Tcl requires exactly 17 arguments"
                in marker_text(candidate.path.parent / "shutdown_before.stdout.log")
                and "P7_JTAG_STAGE_ERROR=P7 JTAG Tcl requires exactly 17 arguments"
                in marker_text(candidate.path.parent / "shutdown_after.stdout.log")
            ):
                return HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED
            ps_process = candidate.data.get("ps_process")
            ps_failures = candidate.data.get("ps_failures")
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and shutdown_before.get("programming_attempted") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and shutdown_after.get("programming_attempted") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and isinstance(ps_failures, list)
                and ps_failures == ps_process.get("failures")
                and candidate.data.get("programmed_candidate") is False
                and candidate.data.get("started_ps_elf") is False
                and marker_text(candidate.path.parent / "p7_ps_application_raw_result.log").splitlines()
                == [
                    "P7_PS_MODE=functional",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 XSDB reset target is not unique on the exact authorized device",
                ]
            ):
                return HISTORICAL_STAGE_PS_RESET_TARGET_UNIQUENESS_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and shutdown_before.get("programming_attempted") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and shutdown_after.get("programming_attempted") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and isinstance(ps_failures, list)
                and ps_failures == ps_process.get("failures")
                and candidate.data.get("programmed_candidate") is False
                and candidate.data.get("started_ps_elf") is False
                and marker_text(candidate.path.parent / "p7_ps_application_raw_result.log").splitlines()
                == [
                    "P7_PS_MODE=functional",
                    "P7_XSDB_DAP_DISTINCT_TARGET_COUNT=0",
                    "P7_XSDB_APU_DISTINCT_TARGET_COUNT=0",
                    "P7_XSDB_FPGA_DISTINCT_TARGET_COUNT=1",
                    "P7_XSDB_CPU0_DISTINCT_TARGET_COUNT=0",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 XSDB reset target is not unique on the exact authorized device",
                ]
            ):
                return HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and shutdown_before.get("programming_attempted") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and shutdown_after.get("programming_attempted") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and isinstance(ps_failures, list)
                and ps_failures == ps_process.get("failures")
                and candidate.data.get("programmed_candidate") is False
                and candidate.data.get("started_ps_elf") is False
                and marker_text(candidate.path.parent / "p7_ps_application_raw_result.log").splitlines()
                == [
                    "P7_PS_MODE=functional",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 XSDB live chain must contain only the one exact device/IDCODE match",
                ]
            ):
                return HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and marker_text(candidate.path.parent / "p7_ps_application_raw_result.log").splitlines()[-2:]
                == [
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 functional boundary case failed: index=8 length=30",
                ]
            ):
                return HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED
            raw_lines = marker_text(candidate.path.parent / "p7_ps_application_raw_result.log").splitlines()
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and len(raw_lines) >= 2
                and raw_lines[-2] == "P7_PS_STAGE_RESULT=FAIL"
                and raw_lines[-1].startswith(
                    'P7_PS_STAGE_ERROR=couldn\'t open "C:/Users/user/Documents/RF_COMM_MULTILANE/'
                )
                and raw_lines[-1].endswith(
                    '/bundle/boundary_8_descriptor_failure.bin": no such file or directory'
                )
            ):
                return HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-7:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=6",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 functional boundary case failed: index=6 length=1 status=4 error=13",
                ]
                and (
                    candidate.path.parent
                    / "bundle"
                    / "boundary_6_descriptor_failure.bin"
                ).is_file()
            ):
                return HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-7:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=8",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=30",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 functional boundary case failed: index=8 length=30 status=4 error=13",
                ]
                and (
                    candidate.path.parent
                    / "bundle"
                    / "boundary_8_descriptor_failure.bin"
                ).is_file()
            ):
                return HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-9:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=8",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=30",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 functional boundary case failed: index=8 length=30 status=4 error=13",
                ]
                and (
                    candidate.path.parent / "bundle" / "boundary_8_descriptor_failure.bin"
                ).is_file()
                and (
                    candidate.path.parent / "bundle" / "boundary_8_output_failure.bin"
                ).is_file()
                and (
                    candidate.path.parent / "bundle" / "boundary_8_trace_failure.bin"
                ).is_file()
            ):
                return HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-9:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=11",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=30",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 integrity failure snapshot publication marker missing",
                ]
                and (candidate.path.parent / "bundle" / "boundary_11_descriptor_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_11_output_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_11_trace_failure.bin").is_file()
                and not (candidate.path.parent / "bundle" / "boundary_11_integrity_snapshot_failure.bin").exists()
            ):
                return HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-12:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=214",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_ADDRESS=0x0b100040",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_BYTES=320",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_STATUS=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 integrity failure snapshot publication marker missing",
                ]
                and (candidate.path.parent / "bundle" / "boundary_13_descriptor_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_13_output_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_13_trace_failure.bin").is_file()
                and not (candidate.path.parent / "bundle" / "boundary_13_integrity_snapshot_failure.bin").exists()
                and not (candidate.path.parent / "bundle" / "boundary_13_integrity_snapshot_wipe_verify.bin").exists()
            ):
                return HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-15:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=10",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=30",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=13",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_ADDRESS=0x00021000",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_BYTES=320",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_STATUS=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_MAGIC_READBACK=0x53463750",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_WIPED=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 functional boundary case failed: index=10 length=30 status=4 error=13",
                ]
                and (candidate.path.parent / "bundle" / "boundary_10_descriptor_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_10_output_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_10_trace_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_10_integrity_snapshot_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_10_integrity_snapshot_wipe_verify.bin").is_file()
            ):
                return HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED
            if (
                candidate.marker == "FAIL_STAGE"
                and candidate.data.get("stage_name") == "p7_ps_functional"
                and candidate.data.get("mode") == "functional"
                and isinstance(preflight, dict)
                and preflight.get("returncode") == 0
                and preflight.get("passed") is True
                and isinstance(shutdown_before, dict)
                and shutdown_before.get("returncode") == 0
                and shutdown_before.get("passed") is True
                and isinstance(shutdown_after, dict)
                and shutdown_after.get("returncode") == 0
                and shutdown_after.get("passed") is True
                and isinstance(ps_process, dict)
                and ps_process.get("returncode") == 0
                and ps_process.get("passed") is False
                and candidate.data.get("programmed_candidate") is True
                and candidate.data.get("started_ps_elf") is True
                and raw_lines[-9:]
                == [
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX=8",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH=30",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=4",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=23",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1",
                    "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1",
                    "P7_PS_STAGE_RESULT=FAIL",
                    "P7_PS_STAGE_ERROR=P7 functional boundary case failed: index=8 length=30 status=4 error=23",
                ]
                and (candidate.path.parent / "bundle" / "boundary_8_descriptor_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_8_output_failure.bin").is_file()
                and (candidate.path.parent / "bundle" / "boundary_8_trace_failure.bin").is_file()
                and not (candidate.path.parent / "bundle" / "boundary_8_integrity_snapshot_failure.bin").exists()
                and not (candidate.path.parent / "bundle" / "boundary_8_integrity_snapshot_wipe_verify.bin").exists()
            ):
                return HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED
        shutdown_result_path = candidate.path.parent / "p7_shutdown_after_result.txt"
        shutdown_markers, shutdown_duplicates = parse_marker_text(
            marker_text(shutdown_result_path)
        )
        if (
            candidate.marker == "FAIL_SHUTDOWN_AFTER"
            and candidate.data.get("stage_name") == "p7_p6_frame_regression_m2"
            and isinstance(preflight, dict)
            and preflight.get("returncode") == 0
            and isinstance(stage_process, dict)
            and stage_process.get("returncode") == 0
            and stage_process.get("passed") is True
            and isinstance(shutdown_after, dict)
            and shutdown_after.get("returncode") == 124
            and shutdown_after.get("timed_out") is True
            and shutdown_after.get("passed") is False
            and shutdown_after.get("process_tree_reaped") is True
            and shutdown_after.get("process_tree_terminated") is True
            and shutdown_after.get("containment_cleanup_attempted") is True
            and shutdown_after.get("containment_cleanup_terminated") is True
            and shutdown_after.get("expected_tool_daemon_classification") == "NONE"
            and shutdown_after.get("expected_tool_daemon_grace_used") is False
            and not shutdown_duplicates
            and shutdown_markers == {
                "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
                "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
                "P7_HW_PART": CANONICAL_FULL_PART,
                "P7_HW_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
                "P7_HW_CANONICAL_PART": CANONICAL_FULL_PART,
                "P7_HW_LIVE_PART": CANONICAL_LIVE_PART,
                "P7_HW_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
                "P7_HW_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
            }
        ):
            return HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED
        if (
            candidate.marker == "FAIL_SHUTDOWN_AFTER"
            and candidate.data.get("stage_name") == "p7_fragment_boundary_216_rep3"
            and isinstance(preflight, dict)
            and preflight.get("returncode") == 0
            and isinstance(stage_process, dict)
            and stage_process.get("returncode") == 0
            and stage_process.get("passed") is True
            and isinstance(shutdown_after, dict)
            and shutdown_after.get("returncode") == 125
            and shutdown_after.get("passed") is False
            and shutdown_after.get("process_tree_reaped") is False
            and shutdown_after.get("process_tree_terminated") is True
            and shutdown_after.get("containment_cleanup_attempted") is True
            and shutdown_after.get("containment_cleanup_terminated") is True
            and shutdown_after.get("expected_tool_daemon_topology_terminal_empty") is False
            and "parent PID lookup missed active contained processes" in str(
                shutdown_after.get("containment_query_error", "")
            )
            and not shutdown_duplicates
            and shutdown_markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
            and resolve_reference(
                shutdown_markers.get("TFDU_SHUTDOWN_PROGRAMMED"),
                document=shutdown_result_path,
                repo_root=candidate.path.parents[6],
            )
            == (
                candidate.path.parents[6]
                / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
            ).resolve(strict=False)
            and shutdown_markers.get("P7_SHUTDOWN_RESULT") == "PASS"
        ):
            return HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED
        if (
            candidate.marker == "FAIL_SHUTDOWN_AFTER"
            and isinstance(preflight, dict)
            and preflight.get("returncode") == 0
        ):
            return HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED
        if (
            candidate.marker == "FAIL_STAGE"
            and isinstance(preflight, dict)
            and preflight.get("returncode") == 0
        ):
            raw, raw_duplicates = raw_markers(candidate)
            stage_process = candidate.data.get("stage_process")
            transaction = candidate.data.get("transaction_validation")
            expected_axi4lite_failures = [
                "stage process returned nonzero exit code: 41",
                "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=FAIL",
                "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
                "stage marker mismatch: P7_TRANSACTION_COUNT expected=4269 observed=MISSING",
                "stage PASS marker missing from stdout",
            ]
            stage_stderr_text = marker_text(
                candidate.path.parent / "p7_jtag_axi_stage.stderr.log"
            ).strip()
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_p6_frame_regression_m1"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 0
                and stage_process.get("passed") is True
                and stage_process.get("timed_out") is False
                and stage_process.get("process_tree_terminated") is False
                and stage_process.get("process_tree_reaped") is True
                and candidate.data.get("stage_failures") == []
                and isinstance(transaction, dict)
                and transaction.get("operation_count") == 4269
                and transaction.get("minimum_run_hw_axi_call_count") == 246
                and transaction.get("multi_transaction_batch_count") == 122
                and transaction.get("batched_single_word_transaction_count") == 4145
                and transaction.get("max_batch_transactions") == 62
                and transaction.get("standalone_run_hw_axi_call_count") == 124
                and transaction.get("axi4_incr_burst_count") == 60
                and transaction.get("axi4_incr_burst_word_count") == 3567
                and transaction.get("max_axi4_incr_burst_words") == 62
                and transaction.get("queued_single_run_hw_axi_call_count") == 83
                and transaction.get("queued_single_multi_transaction_batch_count") == 62
                and transaction.get("queued_single_transaction_count") == 599
                and transaction.get("max_queued_single_transactions") == 16
                and transaction.get("ordered_control_write_run_hw_axi_call_count") == 63
                and transaction.get("queued_control_write_transaction_count") == 0
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS"
                and raw.get("P7_TRANSACTION_COUNT") == "4269"
                and raw.get("P7_JTAG_STAGE_RESULT") == "PASS"
                and raw.get("P7F00000_TX_CRC32") == "A155F91B"
                and raw.get("P7F00000_RX_CRC32") == "A155F91B"
                and raw.get("P7F00000_RX_DIGEST") == "A155F91B"
                and raw.get("P7F00000_TXW000") == "50414652"
                and raw.get("P7F00000_RXW000") == "00414652"
                and raw.get("P7F00000_CRC_BAD") == "00000000"
                and candidate.data.get("backend_parse_failure")
                == "BackendValidationError: TX_CRC32: fragment 0 committed CRC differs from manifest"
            ):
                return HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_p6_frame_regression_m1"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 0
                and stage_process.get("passed") is True
                and stage_process.get("timed_out") is False
                and stage_process.get("process_tree_terminated") is False
                and stage_process.get("process_tree_reaped") is True
                and candidate.data.get("stage_failures") == []
                and isinstance(transaction, dict)
                and transaction.get("operation_count") == 4269
                and transaction.get("minimum_run_hw_axi_call_count") == 226
                and transaction.get("multi_transaction_batch_count") == 122
                and transaction.get("batched_single_word_transaction_count") == 4165
                and transaction.get("max_batch_transactions") == 62
                and transaction.get("standalone_run_hw_axi_call_count") == 104
                and transaction.get("axi4_incr_burst_count") == 60
                and transaction.get("axi4_incr_burst_word_count") == 3567
                and transaction.get("max_axi4_incr_burst_words") == 62
                and transaction.get("queued_single_run_hw_axi_call_count") == 126
                and transaction.get("queued_single_multi_transaction_batch_count") == 62
                and transaction.get("queued_single_transaction_count") == 662
                and transaction.get("max_queued_single_transactions") == 16
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS"
                and raw.get("P7_TRANSACTION_COUNT") == "4269"
                and raw.get("P7_JTAG_STAGE_RESULT") == "PASS"
                and raw.get("P7F00000_TX_CRC32") == "A155F91B"
                and raw.get("P7F00000_RX_CRC32") == "A155F91B"
                and raw.get("P7F00000_RX_DIGEST") == "A155F91B"
                and raw.get("P7F00000_TXW000") == "50414652"
                and raw.get("P7F00000_RXW000") == "00414652"
                and raw.get("P7F00000_CRC_BAD") == "00000000"
                and candidate.data.get("backend_parse_failure")
                == "BackendValidationError: TX_CRC32: fragment 0 committed CRC differs from manifest"
            ):
                return HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_p6_frame_regression_m1"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 41
                and stage_process.get("timed_out") is False
                and stage_process.get("process_tree_reaped") is True
                and candidate.data.get("stage_failures") == expected_axi4lite_failures
                and isinstance(transaction, dict)
                and transaction.get("operation_count") == 4269
                and transaction.get("minimum_single_word_axi4lite_transaction_count") == 4269
                and transaction.get("minimum_run_hw_axi_call_count") == 933
                and transaction.get("multi_transaction_batch_count") == 231
                and transaction.get("batched_single_word_transaction_count") == 3567
                and transaction.get("max_batch_transactions") == 16
                and transaction.get("standalone_run_hw_axi_call_count") == 702
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
                and raw.get("P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED") == "1"
                and raw.get("P7_JTAG_STAGE_RESULT") == "FAIL"
                and raw.get("P7_JTAG_STAGE_ERROR")
                == "ERROR: [Common 17-39] 'run_hw_axi' failed due to earlier errors."
                and stage_stderr_text
                == "ERROR: [Xicom 50-38] xicom:  Queueing Transaction Failed. As total write transactions count 16 is greater than maximum allowed value 1 of targetted JTAG_AXI IP."
                and not any(key.startswith("P7F") for key in raw)
            ):
                return HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_p6_frame_regression_m1"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 41
                and stage_process.get("timed_out") is False
                and stage_process.get("process_tree_reaped") is True
                and candidate.data.get("stage_failures") == expected_axi4lite_failures
                and isinstance(transaction, dict)
                and transaction.get("operation_count") == 4269
                and transaction.get("coalesced_hw_axi_transaction_count") == 762
                and transaction.get("burst_group_count") == 60
                and transaction.get("max_burst_words") == 62
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
                and raw.get("P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED") == "1"
                and raw.get("P7_JTAG_STAGE_RESULT") == "FAIL"
                and raw.get("P7_JTAG_STAGE_ERROR")
                == "ERROR: [Labtoolstcl 44-619] Protocol 'AXI4-Lite' does not support bursts. Only value '1' is valid for option 'LEN'"
                and not any(key.startswith("P7F") for key in raw)
            ):
                return HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
            if (
                not raw_duplicates
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
                and raw.get("P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED") == "1"
                and raw.get("P7_JTAG_STAGE_RESULT") == "FAIL"
                and raw.get("P7_JTAG_STAGE_ERROR")
                == "write offset is outside the P6 candidate allowlist: 0x100"
            ):
                return HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED
            if (
                not raw_duplicates
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
                and raw.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS"
                and raw.get("P7_TRANSACTION_COUNT") == "4269"
                and raw.get("P7_JTAG_STAGE_RESULT") == "PASS"
                and candidate.data.get("backend_parse_failure")
                == "BackendValidationError: RAW_PULSE_COUNTER: fragment 1 RAW_TX_PULSES did not increase"
            ):
                return HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_large_jtag_64k_rr_prbs15"
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
                and raw.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS"
                and raw.get("P7_TRANSACTION_COUNT") == "67092"
                and raw.get("P7_JTAG_STAGE_RESULT") == "PASS"
                and candidate.data.get("backend_parse_failure")
                == "BackendValidationError: COUNTER_DELTA: fragment 200 FRAME_GOOD delta=2 expected=1"
            ):
                return HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_p6_frame_regression_m2"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 130
                and stage_process.get("abort_seen") is True
                and stage_process.get("process_tree_terminated") is True
                and stage_process.get("process_tree_reaped") is True
                and set(raw)
                == {
                    "P7_HW_TARGET",
                    "P7_HW_DEVICE",
                    "P7_HW_PART",
                    "P7_HW_IDCODE",
                    "P7_HW_CANONICAL_PART",
                    "P7_HW_LIVE_PART",
                    "P7_HW_LIVE_DEVICE",
                    "P7_HW_LIVE_IDCODE",
                }
            ):
                return HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE
            expected_timeout_failures = [
                "stage process returned nonzero exit code: 124",
                "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=MISSING",
                "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
                "stage marker mismatch: P7_TRANSACTION_COUNT expected=1073038 observed=MISSING",
                "stage PASS marker missing from stdout",
            ]
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_large_jtag_1m_l0_random"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 124
                and stage_process.get("timed_out") is True
                and stage_process.get("process_tree_terminated") is True
                and stage_process.get("process_tree_reaped") is True
                and candidate.data.get("stage_failures") == expected_timeout_failures
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and isinstance(candidate.data.get("transaction_validation"), dict)
                and candidate.data["transaction_validation"].get("minimum_run_hw_axi_call_count") == 224401
                and candidate.data["transaction_validation"].get("multi_transaction_batch_count") == 58527
                and candidate.data["transaction_validation"].get("batched_single_word_transaction_count") == 907164
                and candidate.data["transaction_validation"].get("max_batch_transactions") == 16
                and candidate.data["transaction_validation"].get("standalone_run_hw_axi_call_count") == 165874
                and raw.get("P7F01666_FRAME_BAD") == "00000000"
                and not any(key.startswith("P7F01667_") for key in raw)
            ):
                return HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
            if (
                not raw_duplicates
                and candidate.data.get("stage_name") == "p7_large_jtag_1m_l0_random"
                and isinstance(stage_process, dict)
                and stage_process.get("returncode") == 124
                and stage_process.get("timed_out") is True
                and stage_process.get("process_tree_terminated") is True
                and stage_process.get("process_tree_reaped") is True
                and candidate.data.get("stage_failures") == expected_timeout_failures
                and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
                and raw.get("P7F00944_RXW017") == "F72C793C"
                and not any(key.startswith("P7F00945_") for key in raw)
            ):
                return HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT
        if candidate.marker == "FAIL_PREFLIGHT":
            return HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED
    return "UNKNOWN"


def _historical_identity_pass_containment_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    preflight: Mapping[str, Any],
    preflight_markers: Mapping[str, str],
) -> list[str]:
    """Validate the frozen r2 helper-topology rejection without reusing PASS rules."""

    errors: list[str] = []
    append_error(errors, preflight.get("returncode") == 125, "historical r2 inner preflight returncode is not exactly 125")
    append_error(errors, preflight.get("process_tree_terminated") is True, "historical r2 inner preflight did not record forced containment cleanup")
    append_error(errors, preflight.get("process_tree_reaped") is False, "historical r2 inner preflight unexpectedly claims a natural reap")
    append_error(errors, preflight.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", "historical r2 inner preflight containment is not a Windows Job")
    append_error(errors, preflight.get("containment_cleanup_terminated") is True, "historical r2 inner preflight does not bind forced cleanup")
    append_error(errors, preflight.get("expected_tool_daemon_grace_used") is False, "historical r2 inner preflight unexpectedly claims daemon grace")
    append_error(errors, preflight.get("expected_tool_daemon_grace_seconds") == 0.0, "historical r2 inner preflight daemon-grace duration is not zero")
    append_error(errors, preflight.get("expected_tool_daemon_classification") == "UNAPPROVED", "historical r2 helper topology was not rejected as UNAPPROVED")
    append_error(errors, preflight.get("process_exit_race_rechecked") is False, "historical r2 inner preflight unexpectedly claims an exit-race recheck")
    append_error(errors, preflight.get("process_identity_query_retried") is False, "historical r2 inner preflight unexpectedly claims an identity-query retry")
    append_error(errors, preflight.get("containment_query_error") == "", "historical r2 inner preflight containment query error is nonempty")

    argv = preflight.get("argv")
    safety = candidate.data.get("safety_validation")
    authorization = safety.get("authorization") if isinstance(safety, dict) else None
    auth_fields = safety.get("authorization_fields") if isinstance(safety, dict) else None
    result_path = candidate.path.parent / "p7_preflight_result.txt"
    argv_exact = (
        isinstance(argv, list)
        and len(argv) == 13
        and all(isinstance(item, str) for item in argv)
        and str(argv[0]).replace("/", "\\").casefold().endswith("\\vivado\\2023.1\\bin\\vivado.bat")
        and argv[1:4] == ["-mode", "batch", "-source"]
        and _same_registered_worktree_location(
            Path(argv[4]),
            evidence.repo_root / "scripts/hw/p7_hw_preflight.tcl",
            evidence.repo_root,
        )
        and argv[5] == "-tclargs"
        and _same_registered_worktree_location(
            Path(argv[6]), evidence.repo_root, evidence.repo_root
        )
        and isinstance(authorization, dict)
        and _same_registered_worktree_location(
            Path(argv[7]),
            Path(str(authorization.get("path", ""))),
            evidence.repo_root,
        )
        and argv[8:12]
        == [
            "210512180081",
            CANONICAL_FULL_PART,
            "localhost:3121/xilinx_tcf/Digilent/210512180081",
            "localhost:3121",
        ]
        and _same_registered_worktree_location(
            Path(argv[12]), result_path, evidence.repo_root
        )
    )
    append_error(errors, argv_exact, "historical r2 inner preflight argv does not bind exact identity inputs")
    append_error(
        errors,
        isinstance(auth_fields, dict)
        and str(auth_fields.get("BOARD_ID", "")) == "210512180081"
        and str(auth_fields.get("EXPECTED_PART", "")).casefold() == CANONICAL_FULL_PART.casefold()
        and str(auth_fields.get("EXPECTED_TARGET", "")).casefold()
        == "localhost:3121/xilinx_tcf/Digilent/210512180081".casefold(),
        "historical r2 authorization does not bind the exact target identity",
    )

    expected_cs = ""
    expected_rdi = ""
    if argv_exact:
        vivado = Path(str(argv[0])).resolve(strict=False)
        expected_cs = str((vivado.parent / "unwrapped/win64.o/cs_server.exe").resolve(strict=False)).replace("/", "\\").casefold()
        expected_rdi = str((vivado.parent / "unwrapped/win64.o/rdi_xsdb.exe").resolve(strict=False)).replace("/", "\\").casefold()
    expected_paths = preflight.get("expected_tool_daemon_paths")
    append_error(
        errors,
        bool(expected_cs)
        and isinstance(expected_paths, list)
        and len(expected_paths) == 1
        and str(Path(str(expected_paths[0])).resolve(strict=False)).replace("/", "\\").casefold() == expected_cs,
        "historical r2 expected cs_server path mismatch",
    )

    processes = preflight.get("descendant_processes_seen")
    normalized: list[tuple[int, int, str]] = []
    if isinstance(processes, list) and len(processes) == 6 and all(isinstance(item, dict) for item in processes):
        try:
            if any(
                not isinstance(item.get("pid"), int)
                or isinstance(item.get("pid"), bool)
                or not isinstance(item.get("parent_pid"), int)
                or isinstance(item.get("parent_pid"), bool)
                for item in processes
            ):
                raise TypeError("PID fields must be non-boolean integers")
            normalized = [
                (
                    int(item["pid"]),
                    int(item["parent_pid"]),
                    str(Path(str(item["image_path"])).resolve(strict=False)).replace("/", "\\").casefold(),
                )
                for item in processes
            ]
        except (KeyError, TypeError, ValueError):
            normalized = []
    ids = [pid for pid, _parent_pid, _path in normalized]
    append_error(
        errors,
        len(normalized) == 6
        and len(set(ids)) == 6
        and all(pid > 0 and parent_pid >= 0 and pid != parent_pid for pid, parent_pid, _path in normalized),
        "historical r2 helper process identities are malformed/duplicated",
    )
    observed_paths = preflight.get("descendant_paths_seen")
    append_error(
        errors,
        isinstance(observed_paths, list)
        and len(observed_paths) == len(normalized) == 6
        and all(
            str(Path(str(observed_paths[index])).resolve(strict=False)).replace("/", "\\").casefold()
            == normalized[index][2]
            for index in range(len(normalized))
        ),
        "historical r2 helper path list does not bind process identities",
    )

    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    expected_conhost = str((system_root / "System32/conhost.exe").resolve(strict=False)).replace("/", "\\").casefold()
    expected_cmd = str((system_root / "System32/cmd.exe").resolve(strict=False)).replace("/", "\\").casefold()
    by_path: dict[str, list[tuple[int, int]]] = {}
    for pid, parent_pid, path in normalized:
        by_path.setdefault(path, []).append((pid, parent_pid))
    append_error(
        errors,
        bool(expected_cs)
        and bool(expected_rdi)
        and sorted(len(by_path.get(path, [])) for path in (expected_cs, expected_conhost, expected_cmd, expected_rdi))
        == [1, 1, 2, 2]
        and len(by_path) == 4,
        "historical r2 observed helper image multiset mismatch",
    )
    cs_records = by_path.get(expected_cs, [])
    cmd_records = by_path.get(expected_cmd, [])
    conhost_records = by_path.get(expected_conhost, [])
    rdi_records = by_path.get(expected_rdi, [])
    active_ids = set(ids)
    cs_direct_edges = sum(parent == other_pid for pid, parent in cs_records for other_pid, _other_parent in cs_records if pid != other_pid)
    cmd_pid = cmd_records[0][0] if len(cmd_records) == 1 else -1
    append_error(errors, len(cs_records) == 2 and cs_direct_edges == 1, "historical r2 cs_server pair is not a direct parent-child topology")
    append_error(
        errors,
        len(cmd_records) == 1
        and len(rdi_records) == 1
        and rdi_records[0][1] == cmd_pid
        and sum(parent_pid == cmd_pid for _pid, parent_pid in conhost_records) == 1,
        "historical r2 cmd/rdi_xsdb/conhost helper topology mismatch",
    )
    cs_roots = [(pid, parent_pid) for pid, parent_pid in cs_records if parent_pid not in {item[0] for item in cs_records}]
    root_conhosts = [(pid, parent_pid) for pid, parent_pid in conhost_records if parent_pid != cmd_pid]
    root_parent_ids = (
        [cs_roots[0][1], cmd_records[0][1], root_conhosts[0][1]]
        if len(cs_roots) == len(cmd_records) == len(root_conhosts) == 1
        else []
    )
    append_error(
        errors,
        len(cs_roots) == 1
        and cs_roots[0][1] not in active_ids
        and len(cmd_records) == 1
        and cmd_records[0][1] not in active_ids
        and len(root_conhosts) == 1
        and root_conhosts[0][1] not in active_ids,
        "historical r2 helper forest roots do not have inactive parents",
    )
    append_error(
        errors,
        len(root_parent_ids) == 3
        and all(parent_id > 0 for parent_id in root_parent_ids)
        and len(set(root_parent_ids)) == 3,
        "historical r2 helper forest root parent PIDs are not positive/distinct",
    )

    target = candidate.data.get("target_identity")
    append_error(errors, isinstance(target, dict) and target == dict(preflight_markers), "historical r2 raw/summary exact identity records differ")
    append_error(
        errors,
        candidate.data.get("preflight_failures") == ["preflight process returned nonzero exit code: 125"],
        "historical r2 preflight failure list does not bind inner rc125",
    )
    append_error(
        errors,
        resolve_reference(candidate.data.get("preflight_result_file"), document=candidate.path, repo_root=evidence.repo_root)
        == result_path.resolve(strict=False),
        "historical r2 preflight result path mismatch",
    )
    append_error(
        errors,
        candidate.data.get("reason") == "read-only target preflight did not return rc=0 with exact identity markers",
        "historical r2 wrapper reason is not the exact identity-pass/containment-fail boundary",
    )
    runtime = candidate.data.get("global_runtime")
    append_error(
        errors,
        isinstance(runtime, dict)
        and runtime.get("authorized_max_seconds") == 300
        and runtime.get("within_authorized_limit") is True
        and isinstance(runtime.get("elapsed_seconds"), (int, float))
        and 0 <= float(runtime.get("elapsed_seconds")) <= 300,
        "historical r2 runtime record is invalid",
    )
    return errors


def _historical_failed_shutdown_process_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    which: str,
) -> list[str]:
    """Validate one r3 rc41 Tcl failure without treating it as shutdown PASS."""

    errors: list[str] = []
    block = candidate.data.get(f"shutdown_{which}")
    label = f"historical r3 shutdown-{which}"
    if not isinstance(block, dict):
        return [f"{label} process record missing"]
    append_error(errors, block.get("name") == f"shutdown_{which}", f"{label} process name mismatch")
    append_error(errors, block.get("returncode") == 41, f"{label} returncode is not exactly 41")
    append_error(errors, block.get("passed") is False, f"{label} incorrectly reports PASS")
    append_error(
        errors,
        block.get("failures")
        == [
            "shutdown process returned nonzero exit code: 41",
            "P7_SHUTDOWN_RESULT=PASS marker missing from fresh result file",
        ],
        f"{label} failure list mismatch",
    )
    if which == "after":
        append_error(errors, block.get("attempted") is True, f"{label} does not record attempted=true")
    else:
        append_error(errors, "attempted" not in block, f"{label} unexpectedly contains a post-hoc attempted field")
    append_error(errors, "programming_attempted" not in block, f"{label} unexpectedly contains a post-fix programming-attempt field")
    for key in ("timed_out", "abort_seen", "interrupted", "process_tree_terminated"):
        append_error(errors, block.get(key) is False, f"{label} reports {key}=true or missing")
    append_error(errors, block.get("process_tree_reaped") is True, f"{label} child tree was not naturally reaped")
    append_error(errors, block.get("containment_assigned") is True, f"{label} containment was not assigned")
    append_error(errors, block.get("containment_closed") is True, f"{label} containment was not closed")
    append_error(errors, block.get("descendant_count_after") == 0, f"{label} retained descendants")
    errors.extend(_v2_process_containment_errors(block, label))
    append_error(errors, block.get("launch_error") == "", f"{label} launch error is nonempty")

    result_path = candidate.path.parent / f"p7_shutdown_{which}_result.txt"
    stdout_path = candidate.path.parent / f"p7_shutdown_{which}.stdout.log"
    stderr_path = candidate.path.parent / f"p7_shutdown_{which}.stderr.log"
    append_error(
        errors,
        resolve_reference(block.get("result_file"), document=candidate.path, repo_root=evidence.repo_root)
        == result_path.resolve(strict=False),
        f"{label} result path mismatch",
    )
    append_error(
        errors,
        resolve_reference(block.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root)
        == stdout_path.resolve(strict=False),
        f"{label} stdout path mismatch",
    )
    append_error(
        errors,
        resolve_reference(block.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root)
        == stderr_path.resolve(strict=False),
        f"{label} stderr path mismatch",
    )
    append_error(errors, stderr_path.is_file() and stderr_path.stat().st_size == 0, f"{label} stderr is missing/nonempty")
    expected_result_markers = {
        "P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED": "0",
        "P7_JTAG_STAGE_RESULT": "FAIL",
        "P7_JTAG_STAGE_ERROR": "char map list unbalanced",
    }
    result_markers, result_duplicates = parse_marker_text(marker_text(result_path))
    stdout_markers, stdout_duplicates = parse_marker_text(marker_text(stdout_path))
    append_error(errors, not result_duplicates and result_markers == expected_result_markers, f"{label} fresh result does not bind the exact Tcl char-map failure")
    append_error(
        errors,
        not stdout_duplicates
        and stdout_markers
        == {
            "P7_JTAG_STAGE_RESULT": "FAIL",
            "P7_JTAG_STAGE_ERROR": "char map list unbalanced",
        },
        f"{label} stdout does not bind the exact Tcl char-map failure",
    )
    append_error(
        errors,
        "TFDU_SHUTDOWN_PROGRAMMED" not in result_markers
        and "SHUTDOWN_EXIT" not in result_markers
        and "P7_SHUTDOWN_RESULT" not in result_markers,
        f"{label} falsely contains a successful shutdown marker",
    )

    safety = candidate.data.get("safety_validation")
    authorization = safety.get("authorization") if isinstance(safety, dict) else None
    auth_path = resolve_reference(
        authorization.get("path") if isinstance(authorization, dict) else None,
        document=candidate.path,
        repo_root=evidence.repo_root,
    )
    preflight = candidate.data.get("preflight_process")
    preflight_argv = preflight.get("argv") if isinstance(preflight, dict) else None
    vivado = str(preflight_argv[0]) if isinstance(preflight_argv, list) and preflight_argv else ""
    shutdown_bit = (evidence.repo_root / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit").resolve(strict=False)
    expected_argv = [
        vivado,
        "-mode",
        "batch",
        "-source",
        str((evidence.repo_root / "scripts/hw/p7_jtag_axi_transactions.tcl").resolve(strict=False)),
        "-tclargs",
        str(evidence.repo_root.resolve(strict=False)),
        "SHUTDOWN",
        str(auth_path) if auth_path is not None else "",
        "210512180081",
        CANONICAL_FULL_PART,
        "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "localhost:3121",
        "1000000",
        str(shutdown_bit),
        "-",
        "-",
        str(result_path.resolve(strict=False)),
        "0x43c00000",
        "1100000",
        "134217728",
        "90",
        str(shutdown_bit),
    ]
    append_error(
        errors,
        bool(vivado)
        and Path(vivado).name.casefold() == "vivado.bat"
        and _argv_matches_with_registered_worktree_paths(
            block.get("argv"),
            expected_argv,
            evidence.repo_root,
            path_indices={4, 6, 8, 14, 17, 22},
        ),
        f"{label} argv mismatch",
    )
    return errors


def _old_commit_shutdown_tcl_failure_errors(candidate: Candidate, evidence: RepositoryEvidence) -> list[str]:
    """Prove the r3 boundary: preflight passed, both shutdown attempts failed, no candidate started."""

    data = candidate.data
    errors: list[str] = []
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "safe_idle", "historical r3 failure is not the JTAG safe-idle stage")
    append_error(errors, candidate.executed, "historical r3 failure omits hardware_actions_executed=true")
    append_error(errors, candidate.marker == "FAIL_SHUTDOWN_AFTER", "historical r3 wrapper result is not exactly FAIL_SHUTDOWN_AFTER")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", "historical r3 promoted or omitted hardware acceptance")
    append_error(errors, _candidate_mutation_attempted(candidate), "historical r3 does not preserve its shutdown attempts")
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "programmed_shutdown_after",
        "started_ps_elf",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
        "uart_access",
        "ethernet_used",
        "motion_used",
    ):
        append_error(errors, data.get(key) is False, f"historical r3 does not explicitly prove {key}=false")
    append_error(errors, not isinstance(data.get("stage_process"), dict), "historical r3 contains a candidate child process")
    append_error(errors, not raw_marker_path(candidate).exists(), "historical r3 contains a candidate raw-result log")

    transaction = data.get("transaction_validation")
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("metadata") == {"EVIDENCE_KIND": "safe_idle"},
        "historical r3 transaction validation is not the exact safe-idle boundary",
    )
    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append("historical r3 preflight process record missing")
        preflight = {}
    else:
        errors.extend(process_record_errors(preflight, "historical r3 preflight", document=candidate.path, repo_root=evidence.repo_root))
    append_error(errors, preflight.get("expected_tool_daemon_grace_used") is True, "historical r3 preflight did not use the fixed helper grace")
    append_error(errors, preflight.get("expected_tool_daemon_grace_seconds") == VIVADO_HELPER_GRACE_SECONDS, "historical r3 preflight helper grace is not exactly 30 seconds")
    append_error(errors, preflight.get("expected_tool_daemon_classification") == "EXACT_R2_VIVADO_EXIT_HELPER_FOREST", "historical r3 preflight initial helper forest mismatch")
    append_error(errors, isinstance(preflight.get("descendant_processes_seen"), list) and len(preflight.get("descendant_processes_seen", [])) == 6, "historical r3 preflight does not bind the exact six-process helper forest")
    snapshots = preflight.get("expected_tool_daemon_topology_snapshots")
    append_error(
        errors,
        isinstance(snapshots, list)
        and len(snapshots) >= 2
        and snapshots[0].get("classification") == "EXACT_R2_VIVADO_EXIT_HELPER_FOREST"
        and snapshots[-1] == {
            "classification": "EMPTY",
            "elapsed_seconds": snapshots[-1].get("elapsed_seconds"),
            "processes": [],
        },
        "historical r3 preflight helper forest does not naturally shrink to EMPTY",
    )
    initial_processes = snapshots[0].get("processes") if isinstance(snapshots, list) and snapshots and isinstance(snapshots[0], dict) else None
    if isinstance(initial_processes, list):
        active_ids = {item.get("pid") for item in initial_processes if isinstance(item, dict)}
        roots = [
            item
            for item in initial_processes
            if isinstance(item, dict) and item.get("parent_pid") not in active_ids
        ]
        append_error(
            errors,
            len(roots) == 3
            and all(item.get("parent_active_globally") is False for item in roots)
            and len({item.get("parent_pid") for item in roots}) == 3,
            "historical r3 preflight helper roots do not bind distinct globally-inactive parents",
        )

    preflight_path = candidate.path.parent / "p7_preflight_result.txt"
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED, "historical r3 preflight identity markers/failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers), "historical r3 raw/summary exact identity records differ")
    append_error(errors, data.get("preflight_failures") == [], "historical r3 preflight failure list is nonempty")
    append_error(
        errors,
        resolve_reference(data.get("preflight_result_file"), document=candidate.path, repo_root=evidence.repo_root)
        == preflight_path.resolve(strict=False),
        "historical r3 preflight result path mismatch",
    )
    safety = data.get("safety_validation")
    authorization = safety.get("authorization") if isinstance(safety, dict) else None
    auth_path = resolve_reference(
        authorization.get("path") if isinstance(authorization, dict) else None,
        document=candidate.path,
        repo_root=evidence.repo_root,
    )
    expected_preflight_argv = [
        preflight.get("argv", [""])[0] if isinstance(preflight.get("argv"), list) and preflight.get("argv") else "",
        "-mode",
        "batch",
        "-source",
        str((evidence.repo_root / "scripts/hw/p7_hw_preflight.tcl").resolve(strict=False)),
        "-tclargs",
        str(evidence.repo_root.resolve(strict=False)),
        str(auth_path) if auth_path is not None else "",
        "210512180081",
        CANONICAL_FULL_PART,
        "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "localhost:3121",
        str(preflight_path.resolve(strict=False)),
    ]
    append_error(
        errors,
        Path(str(expected_preflight_argv[0])).name.casefold() == "vivado.bat"
        and _argv_matches_with_registered_worktree_paths(
            preflight.get("argv"),
            expected_preflight_argv,
            evidence.repo_root,
            path_indices={4, 6, 7, 12},
        ),
        "historical r3 preflight argv does not bind exact identity inputs",
    )
    preflight_stdout = candidate.path.parent / "p7_preflight.stdout.log"
    preflight_stderr = candidate.path.parent / "p7_preflight.stderr.log"
    append_error(errors, resolve_reference(preflight.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == preflight_stdout.resolve(strict=False), "historical r3 preflight stdout path mismatch")
    append_error(errors, resolve_reference(preflight.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == preflight_stderr.resolve(strict=False), "historical r3 preflight stderr path mismatch")
    preflight_stdout_text = marker_text(preflight_stdout)
    append_error(errors, preflight_stdout_text.count("INFO: [Labtools 27-2285] Connecting to hw_server url TCP:localhost:3121") == 1, "historical r3 preflight localhost connection line missing/duplicated")
    append_error(errors, preflight_stdout_text.count("INFO: [Labtoolstcl 44-466] Opening hw_target localhost:3121/xilinx_tcf/Digilent/210512180081") == 1, "historical r3 preflight exact target-open line missing/duplicated")
    append_error(errors, preflight_stderr.is_file() and preflight_stderr.stat().st_size == 0, "historical r3 preflight stderr is missing/nonempty")

    errors.extend(_historical_failed_shutdown_process_errors(candidate, evidence, "before"))
    errors.extend(_historical_failed_shutdown_process_errors(candidate, evidence, "after"))
    append_error(errors, data.get("child_reaped_before_shutdown_after") is False, "historical r3 no-candidate reap fact changed")
    append_error(
        errors,
        data.get("internal_error")
        == "RuntimeError: shutdown-before requires normal rc=0 and TFDU_SHUTDOWN_PROGRAMMED marker",
        "historical r3 internal error mismatch",
    )
    append_error(
        errors,
        data.get("stage_failures") == ["candidate child process tree was not reaped before shutdown-after"],
        "historical r3 stage failure list mismatch",
    )
    append_error(errors, data.get("backend_parse_failure") == "", "historical r3 backend-parse failure is nonempty")
    append_error(errors, data.get("reason") == "stage is incomplete because shutdown-after lacked rc=0 plus marker", "historical r3 reason mismatch")

    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    names = [str(item.get("event", "")) for item in events]
    append_error(
        errors,
        names
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "stage_exception",
            "shutdown_after_started",
            "shutdown_after_finished",
            "authorized_execution_end",
        ],
        "historical r3 event sequence mismatch",
    )
    if len(events) == 7:
        append_error(errors, events[1].get("returncode") == 0 and events[1].get("passed") is True, "historical r3 preflight event is not PASS")
        append_error(errors, events[2].get("returncode") == 41 and events[2].get("passed") is False, "historical r3 shutdown-before event mismatch")
        append_error(errors, events[3].get("error") == data.get("internal_error"), "historical r3 exception event mismatch")
        append_error(errors, events[4].get("candidate_child_reaped") is False and events[4].get("candidate_returncode") is None, "historical r3 shutdown-after start falsely claims a candidate child")
        append_error(errors, events[5].get("returncode") == 41 and events[5].get("passed") is False, "historical r3 shutdown-after event mismatch")
        append_error(errors, events[6].get("status") == "FAIL_SHUTDOWN_AFTER", "historical r3 end event status mismatch")
        event_times = [parse_time(item.get("timestamp_utc"), float("nan")) for item in events]
        append_error(errors, all(value == value for value in event_times) and event_times == sorted(event_times), "historical r3 event chronology is invalid")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"historical r3 lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(
        errors,
        isinstance(runtime, dict)
        and runtime.get("authorized_max_seconds") == 600
        and runtime.get("within_authorized_limit") is True
        and isinstance(runtime.get("elapsed_seconds"), (int, float))
        and 0 <= float(runtime.get("elapsed_seconds")) <= 600,
        "historical r3 runtime record is invalid",
    )
    return errors


def _old_commit_write_allowlist_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate the narrow r4 FAIL_STAGE boundary without granting coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r4"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "safe_idle", f"{label} failure is not the JTAG safe-idle stage")
    append_error(errors, candidate.executed, f"{label} failure omits hardware_actions_executed=true")
    append_error(errors, candidate.marker == "FAIL_STAGE", f"{label} wrapper result is not exactly FAIL_STAGE")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("semantic_mode") == "safe-idle", f"{label} semantic mode is not safe-idle")
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "programmed_shutdown_after",
    ):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in (
        "started_ps_elf",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
        "uart_access",
        "ethernet_used",
        "motion_used",
    ):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, _candidate_mutation_attempted(candidate), f"{label} omits its hardware mutation footprint")
    append_error(errors, _candidate_programmed(candidate), f"{label} omits candidate programming")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate child was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("metadata") == {"EVIDENCE_KIND": "safe_idle"}
        and transaction.get("operation_count") == 13
        and transaction.get("write_operations") == [{"offset": "0x100", "value": "0x00000030"}],
        f"{label} transaction validation is not the exact safe-idle boundary",
    )

    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
        preflight = {}
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_path = candidate.path.parent / "p7_preflight_result.txt"
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers), f"{label} raw/summary target identity differs")
    append_error(errors, data.get("preflight_failures") == [], f"{label} preflight failure list is nonempty")

    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    append_error(errors, stage.get("name") == "jtag_axi_stage", f"{label} candidate process name mismatch")
    append_error(errors, stage.get("returncode") == 41, f"{label} candidate returncode is not exactly 41")
    append_error(errors, stage.get("passed") is False, f"{label} candidate incorrectly reports PASS")
    for key in ("timed_out", "abort_seen", "interrupted", "process_tree_terminated"):
        append_error(errors, stage.get(key) is False, f"{label} candidate reports {key}=true or missing")
    append_error(errors, stage.get("process_tree_reaped") is True, f"{label} candidate process tree was not reaped")
    append_error(errors, stage.get("containment_assigned") is True and stage.get("containment_closed") is True, f"{label} candidate containment assignment/closure mismatch")
    append_error(errors, stage.get("descendant_count_after") == 0, f"{label} candidate retained descendants")
    errors.extend(_v2_process_containment_errors(stage, f"{label} candidate"))
    append_error(errors, stage.get("launch_error") == "", f"{label} candidate launch error is nonempty")
    expected_stage_failures = [
        "stage process returned nonzero exit code: 41",
        "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=FAIL",
        "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
        "stage marker mismatch: P7_TRANSACTION_COUNT expected=13 observed=MISSING",
        "stage PASS marker missing from stdout",
    ]
    append_error(errors, stage.get("failures") == expected_stage_failures, f"{label} candidate failure list mismatch")
    append_error(errors, data.get("stage_failures") == expected_stage_failures, f"{label} wrapper stage failure list mismatch")
    append_error(errors, data.get("backend_parse_failure") == "", f"{label} backend-parse failure is nonempty")
    append_error(errors, data.get("internal_error") == "", f"{label} internal error is nonempty")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} reason mismatch")

    raw_path = raw_marker_path(candidate)
    raw, raw_duplicates = raw_markers(candidate)
    expected_raw = {
        "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PART": CANONICAL_FULL_PART,
        "P7_HW_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_CANONICAL_PART": CANONICAL_FULL_PART,
        "P7_HW_LIVE_PART": CANONICAL_LIVE_PART,
        "P7_HW_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_HW_AXI": "hw_axi_1",
        "P7_TXN_META_EVIDENCE_KIND": "safe_idle",
        "SAFE_STATUS": "00000000",
        "SAFE_TX_COUNT": "00000000",
        "SAFE_RX_GOOD_L0": "00000000",
        "SAFE_RX_GOOD_L1": "00000000",
        "SAFE_CRC_BAD": "00000000",
        "SAFE_PAYLOAD_MISMATCH": "00000000",
        "SAFE_RETRY_EXHAUSTED": "00000000",
        "SAFE_TX_FAIL": "00000000",
        "SAFE_TXD_HIGH_MAX": "00000000",
        "SAFE_DUTY_VIOLATION": "00000000",
        "SAFE_ERROR_CODE": "00000000",
        "SAFE_STICKY_ERROR": "00000000",
        "P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED": "1",
        "P7_TCL_PROGRAMMING_ATTEMPTED": "1",
        "P7_JTAG_STAGE_RESULT": "FAIL",
        "P7_JTAG_STAGE_ERROR": "write offset is outside the P6 candidate allowlist: 0x100",
    }
    append_error(errors, raw_path.is_file() and not raw_duplicates and raw == expected_raw, f"{label} raw result does not bind the exact allowlist failure and zero safe-idle reads")
    append_error(errors, resolve_reference(stage.get("result_file"), document=candidate.path, repo_root=evidence.repo_root) == raw_path.resolve(strict=False), f"{label} candidate result path mismatch")
    stage_stdout = candidate.path.parent / "p7_jtag_axi_stage.stdout.log"
    stage_stderr = candidate.path.parent / "p7_jtag_axi_stage.stderr.log"
    append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == stage_stdout.resolve(strict=False), f"{label} candidate stdout path mismatch")
    append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == stage_stderr.resolve(strict=False), f"{label} candidate stderr path mismatch")
    append_error(errors, stage_stderr.is_file() and stage_stderr.stat().st_size == 0, f"{label} candidate stderr is missing/nonempty")
    stage_stdout_text = marker_text(stage_stdout)
    append_error(errors, len(re.findall(r"^P7_TCL_EMERGENCY_TFDU_SHUTDOWN_PROGRAMMED=.+$", stage_stdout_text, re.MULTILINE)) == 1, f"{label} emergency shutdown stdout marker missing/duplicated")
    append_error(errors, len(re.findall(r"^P7_JTAG_STAGE_ERROR=write offset is outside the P6 candidate allowlist: 0x100$", stage_stdout_text, re.MULTILINE)) == 1, f"{label} allowlist error stdout marker missing/duplicated")

    event_errors = authorized_event_errors(candidate, evidence)
    errors.extend(event_errors)
    _event_path, events, _load_errors = load_authorized_events(candidate)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 9:
        append_error(errors, events[1].get("returncode") == 0 and events[1].get("passed") is True, f"{label} preflight event mismatch")
        append_error(errors, events[2].get("returncode") == 0 and events[2].get("passed") is True, f"{label} shutdown-before event mismatch")
        append_error(errors, events[4].get("candidate_returncode") == 41 and events[4].get("process_tree_reaped") is True, f"{label} candidate-reap event mismatch")
        append_error(errors, events[5].get("returncode") == 41 and events[5].get("passed") is False, f"{label} failed-stage event mismatch")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_STAGE", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(
        errors,
        isinstance(runtime, dict)
        and runtime.get("authorized_max_seconds") == 600
        and runtime.get("within_authorized_limit") is True
        and isinstance(runtime.get("elapsed_seconds"), (int, float))
        and 0 <= float(runtime.get("elapsed_seconds")) <= 600,
        f"{label} runtime record is invalid",
    )
    return errors


def _old_commit_axi4lite_burst_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r11's AXI4-Lite burst rejection without granting coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r11"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "p6_frame_regression", f"{label} failure is not the JTAG P6 frame-regression stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_p6_frame_regression_m1" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "programmed_shutdown_after",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
    ):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 4269
        and transaction.get("coalesced_hw_axi_transaction_count") == 762
        and transaction.get("burst_group_count") == 60
        and transaction.get("burst_word_count") == 3567
        and transaction.get("max_burst_words") == 62
        and transaction.get("single_word_hw_axi_transaction_count") == 702
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE0_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 4096
        and backend_manifest.get("lane_policy") == "LANE0_ONLY"
        and backend_manifest.get("transaction_operation_count") == 4269,
        f"{label} transaction record does not bind the rejected multiword-burst plan",
    )

    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
        preflight = {}
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_path = candidate.path.parent / "p7_preflight_result.txt"
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    expected_stage_failures = [
        "stage process returned nonzero exit code: 41",
        "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=FAIL",
        "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
        "stage marker mismatch: P7_TRANSACTION_COUNT expected=4269 observed=MISSING",
        "stage PASS marker missing from stdout",
    ]
    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 41 and stage.get("passed") is False, f"{label} candidate return/result mismatch")
    append_error(errors, stage.get("failures") == expected_stage_failures and data.get("stage_failures") == expected_stage_failures, f"{label} candidate failure list mismatch")
    for key in ("timed_out", "abort_seen", "interrupted", "process_tree_terminated"):
        append_error(errors, stage.get(key) is False, f"{label} candidate reports {key}=true or missing")
    append_error(errors, stage.get("process_tree_reaped") is True and stage.get("containment_assigned") is True and stage.get("containment_closed") is True and stage.get("descendant_count_after") == 0, f"{label} candidate containment/reap mismatch")
    errors.extend(_v2_process_containment_errors(stage, f"{label} candidate"))
    append_error(errors, stage.get("launch_error") == "", f"{label} candidate launch error is nonempty")
    append_error(errors, data.get("backend_parse_failure") == "" and not isinstance(data.get("backend_parse"), dict), f"{label} incorrectly claims a backend parse")
    append_error(errors, data.get("internal_error") == "", f"{label} internal error is nonempty")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} reason mismatch")

    raw, raw_duplicates = raw_markers(candidate)
    expected_raw_subset = {
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_HW_AXI": "hw_axi_1",
        "P7_TXN_META_BACKEND": "p7_jtag_backend",
        "P7_TXN_META_LANE_POLICY": "LANE0_ONLY",
        "P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED": "1",
        "P7_TCL_PROGRAMMING_ATTEMPTED": "1",
        "P7_JTAG_STAGE_RESULT": "FAIL",
        "P7_JTAG_STAGE_ERROR": "ERROR: [Labtoolstcl 44-619] Protocol 'AXI4-Lite' does not support bursts. Only value '1' is valid for option 'LEN'",
    }
    append_error(errors, not raw_duplicates and all(raw.get(key) == value for key, value in expected_raw_subset.items()), f"{label} raw result does not bind the exact AXI4-Lite rejection")
    append_error(errors, all(raw.get(key) == "00000000" for key in raw if key.startswith("P7_BASE_")), f"{label} baseline counters are not all zero")
    append_error(errors, not any(key.startswith("P7F") for key in raw), f"{label} raw result unexpectedly contains fragment traffic")
    raw_path = raw_marker_path(candidate)
    append_error(errors, resolve_reference(stage.get("result_file"), document=candidate.path, repo_root=evidence.repo_root) == raw_path.resolve(strict=False), f"{label} candidate result path mismatch")
    stage_stdout = candidate.path.parent / "p7_jtag_axi_stage.stdout.log"
    stage_stderr = candidate.path.parent / "p7_jtag_axi_stage.stderr.log"
    append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == stage_stdout.resolve(strict=False), f"{label} candidate stdout path mismatch")
    append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == stage_stderr.resolve(strict=False), f"{label} candidate stderr path mismatch")
    append_error(errors, stage_stderr.is_file() and stage_stderr.stat().st_size == 0, f"{label} candidate stderr is missing/nonempty")
    stdout_text = marker_text(stage_stdout)
    append_error(errors, stdout_text.count("Protocol 'AXI4-Lite' does not support bursts") == 1, f"{label} stdout AXI4-Lite rejection is missing/duplicated")

    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 9:
        append_error(errors, events[4].get("candidate_returncode") == 41 and events[4].get("process_tree_reaped") is True, f"{label} candidate-reap event mismatch")
        append_error(errors, events[5].get("returncode") == 41 and events[5].get("passed") is False, f"{label} failed-stage event mismatch")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_STAGE", f"{label} end event mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 960 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 0 <= float(runtime.get("elapsed_seconds")) <= 960, f"{label} runtime record is invalid")
    return errors


def _old_commit_jtag_axi_queue_depth_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r12's queue-depth-one rejection without granting coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r12"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "p6_frame_regression", f"{label} failure is not the JTAG P6 frame-regression stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_p6_frame_regression_m1" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "programmed_shutdown_after",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
    ):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 4269
        and transaction.get("minimum_single_word_axi4lite_transaction_count") == 4269
        and transaction.get("minimum_run_hw_axi_call_count") == 933
        and transaction.get("multi_transaction_batch_count") == 231
        and transaction.get("batched_single_word_transaction_count") == 3567
        and transaction.get("max_batch_transactions") == 16
        and transaction.get("standalone_run_hw_axi_call_count") == 702
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE0_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 4096
        and backend_manifest.get("lane_policy") == "LANE0_ONLY"
        and backend_manifest.get("transaction_operation_count") == 4269,
        f"{label} transaction record does not bind the rejected 16-transaction queue plan",
    )

    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
        preflight = {}
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_path = candidate.path.parent / "p7_preflight_result.txt"
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    expected_stage_failures = [
        "stage process returned nonzero exit code: 41",
        "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=FAIL",
        "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
        "stage marker mismatch: P7_TRANSACTION_COUNT expected=4269 observed=MISSING",
        "stage PASS marker missing from stdout",
    ]
    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 41 and stage.get("passed") is False, f"{label} candidate return/result mismatch")
    append_error(errors, stage.get("failures") == expected_stage_failures and data.get("stage_failures") == expected_stage_failures, f"{label} candidate failure list mismatch")
    for key in ("timed_out", "abort_seen", "interrupted", "process_tree_terminated"):
        append_error(errors, stage.get(key) is False, f"{label} candidate reports {key}=true or missing")
    append_error(errors, stage.get("process_tree_reaped") is True and stage.get("containment_assigned") is True and stage.get("containment_closed") is True and stage.get("descendant_count_after") == 0, f"{label} candidate containment/reap mismatch")
    errors.extend(_v2_process_containment_errors(stage, f"{label} candidate"))
    append_error(errors, stage.get("launch_error") == "", f"{label} candidate launch error is nonempty")
    append_error(errors, data.get("backend_parse_failure") == "" and not isinstance(data.get("backend_parse"), dict), f"{label} incorrectly claims a backend parse")
    append_error(errors, data.get("internal_error") == "", f"{label} internal error is nonempty")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} reason mismatch")

    raw, raw_duplicates = raw_markers(candidate)
    expected_raw_subset = {
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_HW_AXI": "hw_axi_1",
        "P7_TXN_META_BACKEND": "p7_jtag_backend",
        "P7_TXN_META_LANE_POLICY": "LANE0_ONLY",
        "P7_TCL_EMERGENCY_SHUTDOWN_PROGRAMMED": "1",
        "P7_TCL_PROGRAMMING_ATTEMPTED": "1",
        "P7_JTAG_STAGE_RESULT": "FAIL",
        "P7_JTAG_STAGE_ERROR": "ERROR: [Common 17-39] 'run_hw_axi' failed due to earlier errors.",
    }
    append_error(errors, not raw_duplicates and all(raw.get(key) == value for key, value in expected_raw_subset.items()), f"{label} raw result does not bind the generic run_hw_axi rejection")
    append_error(errors, all(raw.get(key) == "00000000" for key in raw if key.startswith("P7_BASE_")), f"{label} baseline counters are not all zero")
    append_error(errors, not any(key.startswith("P7F") for key in raw), f"{label} raw result unexpectedly contains fragment traffic")
    raw_path = raw_marker_path(candidate)
    append_error(errors, resolve_reference(stage.get("result_file"), document=candidate.path, repo_root=evidence.repo_root) == raw_path.resolve(strict=False), f"{label} candidate result path mismatch")
    stage_stdout = candidate.path.parent / "p7_jtag_axi_stage.stdout.log"
    stage_stderr = candidate.path.parent / "p7_jtag_axi_stage.stderr.log"
    append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == stage_stdout.resolve(strict=False), f"{label} candidate stdout path mismatch")
    append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == stage_stderr.resolve(strict=False), f"{label} candidate stderr path mismatch")
    expected_stderr = "ERROR: [Xicom 50-38] xicom:  Queueing Transaction Failed. As total write transactions count 16 is greater than maximum allowed value 1 of targetted JTAG_AXI IP."
    append_error(errors, marker_text(stage_stderr).strip() == expected_stderr, f"{label} candidate stderr does not bind the exact queue-depth-one rejection")
    append_error(errors, marker_text(stage_stdout).count("'run_hw_axi' failed due to earlier errors") == 1, f"{label} stdout generic run_hw_axi rejection is missing/duplicated")

    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 9:
        append_error(errors, events[4].get("candidate_returncode") == 41 and events[4].get("process_tree_reaped") is True, f"{label} candidate-reap event mismatch")
        append_error(errors, events[5].get("returncode") == 41 and events[5].get("passed") is False, f"{label} failed-stage event mismatch")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_STAGE", f"{label} end event mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 960 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 0 <= float(runtime.get("elapsed_seconds")) <= 960, f"{label} runtime record is invalid")
    return errors


def _old_commit_backend_raw_pulse_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r5's post-shutdown backend rejection without granting coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r5"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "p6_frame_regression", f"{label} failure is not the JTAG P6 frame-regression stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_p6_frame_regression_m1" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_candidate", "programmed_shutdown_before", "programmed_shutdown_after", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 4269
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE0_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 4096
        and backend_manifest.get("lane_policy") == "LANE0_ONLY"
        and backend_manifest.get("transaction_operation_count") == 4269,
        f"{label} transaction/backend manifest boundary mismatch",
    )

    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_path = candidate.path.parent / "p7_preflight_result.txt"
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    else:
        expected_stdout = (candidate.path.parent / "p7_jtag_axi_stage.stdout.log").resolve(strict=False)
        expected_stderr = (candidate.path.parent / "p7_jtag_axi_stage.stderr.log").resolve(strict=False)
        append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stdout and expected_stdout.is_file(), f"{label} candidate stdout binding mismatch")
        append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stderr and expected_stderr.is_file(), f"{label} candidate stderr binding mismatch")
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("passed") is True and stage.get("failures") == [], f"{label} candidate process is not an exact inner PASS")
    append_error(errors, data.get("stage_failures") == [] and data.get("internal_error") == "", f"{label} wrapper stage/internal failure fields mismatch")
    expected_backend_failure = "BackendValidationError: RAW_PULSE_COUNTER: fragment 1 RAW_TX_PULSES did not increase"
    append_error(
        errors,
        data.get("backend_parse_failure") == expected_backend_failure
        and data.get("backend_parse")
        == {"passed": False, "failure": expected_backend_failure, "attempted_after_shutdown": True},
        f"{label} backend rejection mismatch",
    )
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} wrapper reason mismatch")
    append_error(errors, not (candidate.path.parent / "p7_jtag_backend_parse_summary.json").exists(), f"{label} unexpectedly contains a backend PASS summary")

    raw, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates, f"{label} raw result contains duplicate markers")
    expected_raw_subset = {
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_TCL_PROGRAMMING_ATTEMPTED": "1",
        "P7_JTAG_AXI_TRANSACTIONS": "PASS",
        "P7_TRANSACTION_COUNT": "4269",
        "P7_JTAG_STAGE_RESULT": "PASS",
        "P7F00000_RAW_TX_PULSES": "00000460",
        "P7F00001_RAW_TX_PULSES": "00000460",
        "P7F00000_RAW_RX_PULSES": "000008C0",
        "P7F00001_RAW_RX_PULSES": "000008C1",
        "P7F00000_TX_COUNT": "00000001",
        "P7F00001_TX_COUNT": "00000002",
        "P7F00000_FRAME_GOOD": "00000001",
        "P7F00001_FRAME_GOOD": "00000002",
    }
    append_error(errors, all(raw.get(key) == value for key, value in expected_raw_subset.items()), f"{label} raw result does not bind the exact clear-scoped/cumulative counter contrast")
    append_error(errors, len([key for key in raw if re.fullmatch(r"P7F\d{5}_RAW_TX_PULSES", key)]) == 20, f"{label} raw result does not contain 20 fragment TX pulse observations")

    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "backend_parse_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 10:
        append_error(errors, events[5].get("returncode") == 0 and events[5].get("passed") is True, f"{label} inner stage event is not PASS")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event is not PASS")
        append_error(errors, events[8].get("passed") is False and events[8].get("failure") == expected_backend_failure, f"{label} backend event mismatch")
        append_error(errors, events[9].get("status") == "FAIL_STAGE", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(
        errors,
        isinstance(runtime, dict)
        and runtime.get("authorized_max_seconds") == 900
        and runtime.get("within_authorized_limit") is True
        and isinstance(runtime.get("elapsed_seconds"), (int, float))
        and 0 <= float(runtime.get("elapsed_seconds")) <= 900,
        f"{label} runtime record is invalid",
    )
    return errors


def _old_commit_backend_retry_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r8's post-shutdown retry-semantics rejection without coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r8"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "large_object_jtag", f"{label} failure is not the large-object JTAG stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_large_jtag_64k_rr_prbs15" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_candidate", "programmed_shutdown_before", "programmed_shutdown_after", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 67092
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "STRIPE_ROUND_ROBIN"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 65536
        and backend_manifest.get("input_sha256") == "ca45ccdf9f0c2be72656e6414cd71ae407b860df22830092d92fb0dbf1a0f1eb"
        and backend_manifest.get("lane_policy") == "STRIPE_ROUND_ROBIN"
        and backend_manifest.get("transaction_operation_count") == 67092,
        f"{label} transaction/backend manifest boundary mismatch",
    )
    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(candidate.path.parent / "p7_preflight_result.txt"))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))
    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    else:
        expected_stdout = (candidate.path.parent / "p7_jtag_axi_stage.stdout.log").resolve(strict=False)
        expected_stderr = (candidate.path.parent / "p7_jtag_axi_stage.stderr.log").resolve(strict=False)
        append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stdout and expected_stdout.is_file(), f"{label} candidate stdout binding mismatch")
        append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stderr and expected_stderr.is_file(), f"{label} candidate stderr binding mismatch")
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 0 and stage.get("passed") is True and stage.get("failures") == [], f"{label} candidate process is not exact inner PASS")
    expected_failure = "BackendValidationError: COUNTER_DELTA: fragment 200 FRAME_GOOD delta=2 expected=1"
    append_error(errors, data.get("stage_failures") == [] and data.get("internal_error") == "", f"{label} wrapper stage/internal failure fields mismatch")
    append_error(errors, data.get("backend_parse_failure") == expected_failure and data.get("backend_parse") == {"passed": False, "failure": expected_failure, "attempted_after_shutdown": True}, f"{label} backend rejection mismatch")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} wrapper reason mismatch")
    append_error(errors, not (candidate.path.parent / "p7_jtag_backend_parse_summary.json").exists(), f"{label} unexpectedly contains a backend PASS summary")

    raw, raw_duplicates = raw_markers(candidate)
    expected_raw = {
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_TCL_PROGRAMMING_ATTEMPTED": "1",
        "P7_JTAG_AXI_TRANSACTIONS": "PASS",
        "P7_TRANSACTION_COUNT": "67092",
        "P7_JTAG_STAGE_RESULT": "PASS",
        "P7F00199_RETRY_COUNT": "00000000",
        "P7F00200_RETRY_COUNT": "00000001",
        "P7F00201_RETRY_COUNT": "00000000",
        "P7F00199_FRAME_GOOD": "000000C8",
        "P7F00200_FRAME_GOOD": "000000CA",
        "P7F00201_FRAME_GOOD": "000000CB",
        "P7F00199_ACK_SENT": "000000C8",
        "P7F00200_ACK_SENT": "000000CA",
        "P7F00201_ACK_SENT": "000000CB",
        "P7F00199_ACK_SEEN": "000000C8",
        "P7F00200_ACK_SEEN": "000000C9",
        "P7F00201_ACK_SEEN": "000000CA",
    }
    append_error(errors, not raw_duplicates and all(raw.get(key) == value for key, value in expected_raw.items()), f"{label} raw retry evidence mismatch")
    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(errors, [item.get("event") for item in events] == ["authorized_execution_begin", "preflight_finished", "shutdown_before_finished", "candidate_started", "candidate_child_reaped", "stage_finished", "shutdown_after_started", "shutdown_after_finished", "backend_parse_finished", "authorized_execution_end"], f"{label} event sequence mismatch")
    if len(events) == 10:
        append_error(errors, events[5].get("returncode") == 0 and events[5].get("passed") is True, f"{label} inner stage event is not PASS")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("passed") is False and events[8].get("failure") == expected_failure, f"{label} backend-parse event mismatch")
        append_error(errors, events[9].get("status") == "FAIL_STAGE", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 960 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 0 <= float(runtime.get("elapsed_seconds")) <= 960, f"{label} runtime record is invalid")
    return errors


def _axi4_burst_word_order_reversal_proofs(
    candidate: Candidate,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reconstruct r15's natural and physical payload ordering from raw words."""

    errors: list[str] = []
    label = "historical r15"
    raw, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates, f"{label} raw result contains duplicate markers")
    frozen_transaction_files = list(
        (candidate.path.parent.parent / "historical_preflight_inputs").glob(
            "p7_stage_001_transactions_*.txt"
        )
    )
    authorized_words: dict[str, int] = {}
    latest_payload_words: dict[int, int] = {}
    if len(frozen_transaction_files) == 1:
        for line in frozen_transaction_files[0].read_text(
            encoding="utf-8", errors="strict"
        ).splitlines():
            fields = line.split()
            if len(fields) >= 3 and fields[0] == "W32":
                try:
                    address = int(fields[1], 0)
                    value = int(fields[2], 0)
                except ValueError:
                    continue
                if 0x43C0_0200 <= address <= 0x43C0_02FC:
                    latest_payload_words[address] = value
            elif (
                len(fields) == 3
                and fields[0] == "R32"
                and re.fullmatch(r"P7F\d{5}_TXW\d{3}", fields[2])
            ):
                try:
                    address = int(fields[1], 0)
                except ValueError:
                    continue
                if address in latest_payload_words:
                    authorized_words[fields[2]] = latest_payload_words[address]
    else:
        errors.append(f"{label} frozen stage transaction file missing/duplicated")
    reversal_proofs: list[dict[str, Any]] = []
    expected_authorized_keys: set[str] = set()
    for fragment_index in range(20):
        prefix = f"P7F{fragment_index:05d}_"
        expected_length = 43 if fragment_index == 19 else 247
        try:
            observed_length = int(raw[f"{prefix}RX_LEN"], 16)
        except (KeyError, ValueError):
            observed_length = -1
        word_count = (expected_length + 3) // 4
        expected_keys = [f"{prefix}TXW{index:03d}" for index in range(word_count)]
        try:
            words = [int(raw[key], 16).to_bytes(4, "little") for key in expected_keys]
            observed_crc = int(raw[f"{prefix}TX_CRC32"], 16)
        except (KeyError, ValueError, OverflowError):
            words = []
            observed_crc = -1
        natural = b"".join(words)[:expected_length]
        physical = b"".join(reversed(words))[:expected_length]
        expected_authorized_keys.update(expected_keys)
        authorized_words_match = len(words) == word_count and all(
            authorized_words.get(key) == int(raw.get(key, ""), 16)
            for key in expected_keys
        )
        natural_crc = zlib.crc32(natural) & 0xFFFF_FFFF
        physical_crc = zlib.crc32(physical) & 0xFFFF_FFFF
        proof = {
            "fragment_index": fragment_index,
            "length": observed_length,
            "word_count": len(words),
            "natural_crc32": f"{natural_crc:08X}",
            "reversed_word_crc32": f"{physical_crc:08X}",
            "observed_tx_crc32": f"{observed_crc:08X}" if observed_crc >= 0 else None,
            "authorized_transaction_words_match": authorized_words_match,
        }
        reversal_proofs.append(proof)
        append_error(
            errors,
            observed_length == expected_length
            and len(words) == word_count
            and authorized_words_match
            and natural_crc != observed_crc
            and physical_crc == observed_crc,
            f"{label} fragment {fragment_index} does not prove exact reversed AXI4 burst word order",
        )
    append_error(
        errors,
        len(reversal_proofs) == 20
        and len(expected_authorized_keys) == 1189
        and set(authorized_words) == expected_authorized_keys,
        f"{label} frozen authorized payload-word matrix mismatch",
    )
    return reversal_proofs, errors


def _old_commit_ps_shutdown_arg_count_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r16's exact pre-candidate PS shutdown argv rejection."""

    errors: list[str] = []
    label = "historical r16"
    data = candidate.data
    append_error(errors, candidate.kind == "ps" and candidate.stage == "ps_runtime", f"{label} failure is not the PS functional stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_SHUTDOWN_AFTER", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_ps_functional" and data.get("mode") == "functional", f"{label} stage identity/mode mismatch")
    append_error(errors, data.get("hardware_actions_executed") is True, f"{label} omits the hardware execution attempt")
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "programmed_shutdown_after",
        "started_ps_elf",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
        "uart_access",
        "ethernet_used",
        "motion_used",
    ):
        append_error(errors, data.get(key) is False, f"{label} does not preserve {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is False, f"{label} candidate-child absence fact mismatch")
    append_error(errors, data.get("ps_process") is None, f"{label} unexpectedly contains a PS candidate process")
    append_error(
        errors,
        data.get("internal_error")
        == "RuntimeError: shutdown-before requires rc=0 plus TFDU_SHUTDOWN_PROGRAMMED",
        f"{label} internal failure mismatch",
    )
    append_error(
        errors,
        isinstance(data.get("postprocess"), dict)
        and data["postprocess"].get("passed") is False
        and data["postprocess"].get("failures")
        == ["PS process did not pass exact rc/marker policy"],
        f"{label} postprocess failure mismatch",
    )
    safety = data.get("safety_validation")
    append_error(
        errors,
        isinstance(safety, dict)
        and safety.get("P7_HARDWARE_SAFETY") == "PASS"
        and safety.get("ready_for_hardware_preflight") is True
        and safety.get("authorization_environment_present") is True
        and safety.get("errors") == []
        and str(safety.get("source_commit_requested", "")).lower()
        == "594f91c14a9a28b0be98463bd9faac33ff92d75d",
        f"{label} safety/source boundary mismatch",
    )
    preflight = data.get("preflight")
    if isinstance(preflight, dict):
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    else:
        errors.append(f"{label} preflight process record missing")
    preflight_markers, preflight_duplicates = parse_marker_text(
        marker_text(candidate.path.parent / "p7_hw_preflight_result.txt")
    )
    append_error(
        errors,
        not preflight_duplicates
        and isinstance(preflight, dict)
        and preflight.get("returncode") == 0
        and preflight.get("passed") is True
        and data.get("target_identity") == dict(preflight_markers),
        f"{label} read-only preflight identity mismatch",
    )
    expected_shutdown_failures = [
        "shutdown process returned nonzero exit code: 41",
        "TFDU_SHUTDOWN_PROGRAMMED marker missing from fresh result file",
        "P7_SHUTDOWN_RESULT=PASS marker missing from fresh result file",
        "P7_TCL_PROGRAMMING_ATTEMPTED=1 marker missing from fresh result file",
    ]
    for which in ("before", "after"):
        shutdown = data.get(f"shutdown_{which}")
        if not isinstance(shutdown, dict):
            errors.append(f"{label} shutdown-{which} process record missing")
            continue
        errors.extend(_v2_process_containment_errors(shutdown, f"{label} shutdown-{which}"))
        append_error(
            errors,
            shutdown.get("name") == f"shutdown_{which}"
            and shutdown.get("returncode") == 41
            and shutdown.get("passed") is False
            and shutdown.get("programming_attempted") is None
            and shutdown.get("process_tree_reaped") is True
            and shutdown.get("process_tree_terminated") is False
            and shutdown.get("failures") == expected_shutdown_failures,
            f"{label} shutdown-{which} exact rejection mismatch",
        )
        command = shutdown.get("argv")
        tclargs: list[Any] = []
        if isinstance(command, list) and command.count("-tclargs") == 1:
            tclargs = command[command.index("-tclargs") + 1 :]
        append_error(
            errors,
            len(tclargs) == 16
            and tclargs[1] == "SHUTDOWN"
            and tclargs[13] == "1"
            and tclargs[14] == "900"
            and str(tclargs[15]).endswith(
                "p7_frozen_shutdown_bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit"
            ),
            f"{label} shutdown-{which} does not prove the exact missing max-transaction-bytes argument",
        )
        stdout_path = candidate.path.parent / f"shutdown_{which}.stdout.log"
        stderr_path = candidate.path.parent / f"shutdown_{which}.stderr.log"
        append_error(errors, stdout_path.is_file() and stderr_path.is_file() and stderr_path.stat().st_size == 0, f"{label} shutdown-{which} log set mismatch")
        append_error(
            errors,
            "P7_JTAG_STAGE_ERROR=P7 JTAG Tcl requires exactly 17 arguments"
            in marker_text(stdout_path),
            f"{label} shutdown-{which} exact Tcl error missing",
        )
        append_error(errors, not (candidate.path.parent / f"shutdown_{which}_result.txt").exists(), f"{label} shutdown-{which} unexpectedly produced a promoted result file")
    events_path = candidate.path.parent / "p7_ps_application_events.json"
    try:
        events_payload = json.loads(events_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} event log invalid: {exc}")
    else:
        event_names = [item.get("event") for item in events_payload.get("events", []) if isinstance(item, dict)]
        append_error(
            errors,
            event_names
            == [
                "authorized_execution_begin",
                "preflight_finished",
                "shutdown_before_finished",
                "stage_exception",
                "shutdown_after_started",
                "shutdown_after_finished",
                "authorized_execution_end",
            ],
            f"{label} event sequence mismatch",
        )
    raw_manifest_errors, _raw_manifest_record = validate_raw_evidence_manifest(candidate, evidence)
    errors.extend(raw_manifest_errors)
    append_error(
        errors,
        isinstance(data.get("bundle_post_shutdown_verification"), dict)
        and data["bundle_post_shutdown_verification"].get("passed") is True
        and data["bundle_post_shutdown_verification"].get("immutable_pre_post_equal") is True,
        f"{label} immutable bundle post-shutdown verification mismatch",
    )
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    append_error(
        errors,
        _historical_preflight_variant(candidate)
        == HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED,
        f"{label} failure class mismatch",
    )
    return errors


def _old_commit_ps_reset_target_uniqueness_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r18's exact pre-reset/pre-candidate XSDB target rejection."""

    errors: list[str] = []
    variant = _historical_preflight_variant(candidate)
    r21 = variant == HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED
    r22 = variant == HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED
    r23 = variant == HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED
    r24 = variant == HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED
    r25 = variant == HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED
    label = "historical r25" if r25 else "historical r24" if r24 else "historical r23" if r23 else "historical r22" if r22 else "historical r21" if r21 else "historical r18"
    data = candidate.data
    expected_ps_failures = [
        "PS stage marker mismatch: P7_PS_STAGE_RESULT expected=PASS observed=FAIL",
        "PS stage marker mismatch: P7_PS_CANDIDATE_PROGRAMMED expected=1 observed=MISSING",
        "PS stage marker mismatch: P7_PS_ELF_DOWNLOADED expected=1 observed=MISSING",
        "PS stage marker mismatch: P7_HW_TARGET expected=localhost:3121/xilinx_tcf/Digilent/210512180081 observed=MISSING",
        "PS stage marker mismatch: P7_HW_PART expected=xc7z010clg400-1 observed=MISSING",
        "PS stage marker mismatch: P7_XSDB_LIVE_DEVICE_MATCH expected=1 observed=MISSING",
        "PS stage marker mismatch: P7_XSDB_TARGET_SELECTION expected=EXACT_CABLE_DEVICE_IDCODE_AND_UNIQUE_NODE_IDS observed=MISSING",
        "PS stage live board/cable serial marker mismatch",
        "PS stage Vivado preflight identity marker mismatch: P7_HW_CANONICAL_PART expected=xc7z010clg400-1 observed=MISSING",
        "PS stage Vivado preflight identity marker mismatch: P7_HW_LIVE_PART expected=xc7z010 observed=MISSING",
        "PS stage Vivado preflight identity marker mismatch: P7_HW_LIVE_DEVICE expected=xc7z010_1 observed=MISSING",
        "PS stage Vivado preflight identity marker mismatch: P7_HW_LIVE_IDCODE expected=00010011011100100010000010010011 observed=MISSING",
        "PS stage XSDB live IDCODE is not the exact authorized IDCODE",
        "PS stage fresh preflight IDCODE is not the exact authorized IDCODE",
        "PS stage XSDB live device is not the exact canonical live device root",
        "PS stage Vivado live device marker is not the exact authorized live device",
        "P7_PS_STAGE_RESULT=PASS missing from stdout",
    ]
    append_error(errors, candidate.kind == "ps" and candidate.stage == "ps_runtime", f"{label} failure is not PS functional")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_ps_functional" and data.get("mode") == "functional", f"{label} stage identity/mode mismatch")
    append_error(errors, data.get("hardware_actions_executed") is True, f"{label} omits the hardware attempt")
    append_error(
        errors,
        data.get("programmed_fpga") is True
        and data.get("programmed_candidate") is False
        and data.get("programmed_shutdown_before") is True
        and data.get("programmed_shutdown_after") is True
        and data.get("started_ps_elf") is False,
        f"{label} programming/ELF facts mismatch",
    )
    append_error(
        errors,
        data.get("drove_tfdu_txd") is True
        and data.get("enabled_tfdu_receiver") is True
        and data.get("uart_access") is False
        and data.get("ethernet_used") is False
        and data.get("motion_used") is False,
        f"{label} conservative TFDU/no-network/no-motion facts mismatch",
    )
    append_error(errors, data.get("internal_error") == "", f"{label} unexpected internal error")
    append_error(errors, data.get("ps_failures") == expected_ps_failures, f"{label} exact PS failure list mismatch")
    append_error(
        errors,
        isinstance(data.get("postprocess"), dict)
        and data["postprocess"].get("passed") is False
        and data["postprocess"].get("cases") == []
        and data["postprocess"].get("mailbox") == {}
        and data["postprocess"].get("failures") == ["PS process did not pass exact rc/marker policy"],
        f"{label} postprocess failure mismatch",
    )
    safety = data.get("safety_validation")
    append_error(
        errors,
        isinstance(safety, dict)
        and safety.get("P7_HARDWARE_SAFETY") == "PASS"
        and safety.get("ready_for_hardware_preflight") is True
        and safety.get("authorization_environment_present") is True
        and safety.get("errors") == []
        and str(safety.get("source_commit_requested", "")).lower()
        == (
            "0da648c128e4cdf363754f06a20560bc42b76aae"
            if r22
            else "b149620f92a2abda4add8529166dd7d5f5359506"
            if r21
            else "b1765f8d8671e0c650122029bc72146f43274558"
        ),
        f"{label} safety/source boundary mismatch",
    )
    preflight = data.get("preflight")
    if isinstance(preflight, dict):
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    else:
        errors.append(f"{label} preflight process record missing")
    preflight_markers, preflight_duplicates = parse_marker_text(
        marker_text(candidate.path.parent / "p7_hw_preflight_result.txt")
    )
    append_error(
        errors,
        not preflight_duplicates
        and isinstance(preflight, dict)
        and preflight.get("returncode") == 0
        and preflight.get("passed") is True
        and data.get("target_identity") == dict(preflight_markers),
        f"{label} read-only preflight identity mismatch",
    )
    for which in ("before", "after"):
        shutdown = data.get(f"shutdown_{which}")
        if not isinstance(shutdown, dict):
            errors.append(f"{label} shutdown-{which} record missing")
            continue
        errors.extend(_v2_process_containment_errors(shutdown, f"{label} shutdown-{which}"))
        append_error(
            errors,
            shutdown.get("returncode") == 0
            and shutdown.get("passed") is True
            and shutdown.get("programming_attempted") is True
            and shutdown.get("process_tree_reaped") is True
            and shutdown.get("process_tree_terminated") is False
            and shutdown.get("failures") == [],
            f"{label} shutdown-{which} exact PASS mismatch",
        )
        result_path = candidate.path.parent / f"shutdown_{which}_result.txt"
        result_markers, result_duplicates = parse_marker_text(marker_text(result_path))
        expected_shutdown_bit = ""
        if isinstance(shutdown.get("argv"), list) and shutdown["argv"]:
            expected_shutdown_bit = str(shutdown["argv"][-1]).replace("\\", "/")
        append_error(
            errors,
            not result_duplicates
            and result_markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
            and result_markers.get("P7_SHUTDOWN_RESULT") == "PASS"
            and expected_shutdown_bit.endswith(
                "/p7_frozen_shutdown_bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit"
            )
            and result_markers.get("TFDU_SHUTDOWN_PROGRAMMED", "").replace("\\", "/")
            == expected_shutdown_bit,
            f"{label} shutdown-{which} result markers mismatch",
        )
    ps_process = data.get("ps_process")
    if isinstance(ps_process, dict):
        errors.extend(_v2_process_containment_errors(ps_process, f"{label} PS process"))
    else:
        errors.append(f"{label} PS process record missing")
        ps_process = {}
    append_error(
        errors,
        ps_process.get("name") == "ps_application_stage"
        and ps_process.get("returncode") == 0
        and ps_process.get("passed") is False
        and ps_process.get("process_tree_reaped") is True
        and ps_process.get("process_tree_terminated") is False
        and ps_process.get("failures") == expected_ps_failures,
        f"{label} PS process exact rejection mismatch",
    )
    raw_lines = marker_text(candidate.path.parent / "p7_ps_application_raw_result.log").splitlines()
    raw_error = (
        "P7 XSDB live chain must contain only the one exact device/IDCODE match"
        if r22
        else "P7 XSDB reset target is not unique on the exact authorized device"
    )
    expected_raw_lines = [
        "P7_PS_MODE=functional",
        *(
            [
                "P7_XSDB_DAP_DISTINCT_TARGET_COUNT=0",
                "P7_XSDB_APU_DISTINCT_TARGET_COUNT=0",
                "P7_XSDB_FPGA_DISTINCT_TARGET_COUNT=1",
                "P7_XSDB_CPU0_DISTINCT_TARGET_COUNT=0",
            ]
            if r21
            else []
        ),
        "P7_PS_STAGE_RESULT=FAIL",
        f"P7_PS_STAGE_ERROR={raw_error}",
    ]
    append_error(
        errors,
        raw_lines == expected_raw_lines,
        f"{label} raw XSDB failure mismatch",
    )
    for name in ("ps_application_stage.stdout.log", "ps_application_stage.stderr.log"):
        append_error(
            errors,
            f"P7_PS_STAGE_ERROR={raw_error}"
            in marker_text(candidate.path.parent / name),
            f"{label} exact XSDB error missing from {name}",
        )
    raw_manifest_errors, _raw_manifest_record = validate_raw_evidence_manifest(candidate, evidence)
    errors.extend(raw_manifest_errors)
    append_error(
        errors,
        isinstance(data.get("bundle_post_shutdown_verification"), dict)
        and data["bundle_post_shutdown_verification"].get("passed") is True
        and data["bundle_post_shutdown_verification"].get("immutable_pre_post_equal") is True,
        f"{label} immutable bundle post-shutdown verification mismatch",
    )
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    append_error(
        errors,
        variant
        in {
            HISTORICAL_STAGE_PS_RESET_TARGET_UNIQUENESS_REJECTED,
            HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED,
            HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED,
        },
        f"{label} failure class mismatch",
    )
    return errors


def _old_commit_ps_functional_boundary_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r23-r31 exact post-program functional boundary rejections."""

    errors: list[str] = []
    variant = _historical_preflight_variant(candidate)
    r24 = variant == HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED
    r25 = variant == HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED
    r26 = variant == HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED
    r27 = variant == HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED
    r28 = variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED
    r29 = variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED
    r30 = variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED
    r31 = variant == HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED
    label = "historical r31" if r31 else "historical r30" if r30 else "historical r29" if r29 else "historical r28" if r28 else "historical r27" if r27 else "historical r26" if r26 else "historical r25" if r25 else "historical r24" if r24 else "historical r23"
    data = candidate.data
    expected_failures = [
        "PS stage marker mismatch: P7_PS_STAGE_RESULT expected=PASS observed=FAIL",
        "P7_PS_STAGE_RESULT=PASS missing from stdout",
    ]
    append_error(errors, candidate.kind == "ps" and candidate.stage == "ps_runtime", f"{label} kind/stage mismatch")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} result boundary mismatch")
    append_error(errors, data.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", f"{label} hardware acceptance promoted")
    append_error(
        errors,
        data.get("stage_name") == "p7_ps_functional"
        and data.get("mode") == "functional"
        and data.get("programmed_candidate") is True
        and data.get("started_ps_elf") is True
        and data.get("ethernet_used") is False
        and data.get("motion_used") is False,
        f"{label} execution/scope facts mismatch",
    )
    safety = data.get("safety_validation")
    append_error(
        errors,
        isinstance(safety, dict)
        and safety.get("P7_HARDWARE_SAFETY") == "PASS"
        and safety.get("errors") == []
        and str(safety.get("source_commit_requested", "")).lower()
        == (
            "0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4"
            if r31
            else "7ce64d36a4a9c98c14c639d21cae3740119c5f68"
            if r30
            else "cd26d97b036366b901d9c20f0273da38f6042953"
            if r29
            else "e4c369f380119d527b3238b09fc5fe3d628760d7"
            if r28
            else "164cedde1e7d91a7eeb3787ec160525e3352da9f"
            if r27
            else "e4d6937ad559065a650054998807599f859f34bf"
            if r26
            else "6cb92a2cdd7c056d67f79b83e7de4b9fd139104d"
            if r25
            else "9a01b3da79f8a0e3561a56f799355915c132f3b1"
            if r24
            else "f9a3d34641c2aabd08d88e84070e2a1e98ccef79"
        ),
        f"{label} safety/source mismatch",
    )
    for name in ("preflight", "shutdown_before", "shutdown_after"):
        process = data.get(name)
        if not isinstance(process, dict):
            errors.append(f"{label} {name} record missing")
            continue
        errors.extend(_v2_process_containment_errors(process, f"{label} {name}"))
        append_error(
            errors,
            process.get("returncode") == 0
            and process.get("passed") is True
            and process.get("process_tree_reaped") is True
            and process.get("process_tree_terminated") is False
            and process.get("failures") == [],
            f"{label} {name} exact PASS mismatch",
        )
    ps_process = data.get("ps_process")
    append_error(
        errors,
        isinstance(ps_process, dict)
        and ps_process.get("name") == "ps_application_stage"
        and ps_process.get("returncode") == 0
        and ps_process.get("passed") is False
        and ps_process.get("process_tree_reaped") is True
        and ps_process.get("process_tree_terminated") is False
        and ps_process.get("failures") == expected_failures
        and data.get("ps_failures") == expected_failures,
        f"{label} PS process rejection mismatch",
    )
    raw_path = candidate.path.parent / "p7_ps_application_raw_result.log"
    raw_markers, duplicates = parse_marker_text(marker_text(raw_path))
    expected_markers = {
        "P7_PS_MODE": "functional",
        "P7_XSDB_DAP_DISTINCT_TARGET_COUNT": "0",
        "P7_XSDB_APU_DISTINCT_TARGET_COUNT": "1",
        "P7_XSDB_FPGA_DISTINCT_TARGET_COUNT": "1",
        "P7_XSDB_CPU0_DISTINCT_TARGET_COUNT": "1",
        "P7_XSDB_CABLE_ROOT_COUNT": "1",
        "P7_XSDB_JTAG_DEVICE_COUNT": "2",
        "P7_PS_RESET_TARGET": "APU",
        "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_PART": "xc7z010clg400-1",
        "P7_HW_CANONICAL_PART": "xc7z010clg400-1",
        "P7_HW_LIVE_PART": "xc7z010",
        "P7_HW_LIVE_DEVICE": "xc7z010_1",
        "P7_HW_LIVE_IDCODE": "00010011011100100010000010010011",
        "P7_HW_BOARD_ID": "210512180081",
        "P7_XSDB_LIVE_DEVICE": "xc7z010",
        "P7_XSDB_LIVE_DEVICE_MATCH": "1",
        "P7_XSDB_LIVE_BOARD_ID": "210512180081",
        "P7_XSDB_LIVE_IDCODE": "0x13722093",
        "P7_XSDB_PREFLIGHT_IDCODE": "00010011011100100010000010010011",
        "P7_XSDB_TARGET_SELECTION": "EXACT_CABLE_DEVICE_IDCODE_AND_UNIQUE_NODE_IDS",
        "P7_PS_CANDIDATE_PROGRAMMED": "1",
        "P7_HOST_TO_PS_INPUT_BYTES": "4456448",
        "P7_HOST_TO_PS_INPUT_DURATION_MS": "102392" if r31 else "74793" if r30 else "76363" if r29 else "76397" if r28 else "74211" if r27 else "79224" if r26 else "77849" if r25 else "74283" if r24 else "72445",
        "P7_HOST_TO_PS_INPUT_BYTES_PER_SEC": "43523" if r31 else "59583" if r30 else "58358" if r29 else "58332" if r28 else "60051" if r27 else "56251" if r26 else "57244" if r25 else "59992" if r24 else "61514",
        "P7_HOST_TO_PS_INPUT_BPS": "348187" if r31 else "476670" if r30 else "466869" if r29 else "466662" if r28 else "480408" if r27 else "450009" if r26 else "457958" if r25 else "479942" if r24 else "492119",
        "P7_PS_ELF_DOWNLOADED": "1",
        "P7_PS_SERVICE_READY_POLLS": "3",
        "P7_PS_SERVICE_HEARTBEAT_AND_START_TICKS": "1",
        **(
            {
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_INDEX": "10" if r30 else "13" if r29 else "11" if r28 else "8" if r26 or r27 or r31 else "6",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_LENGTH": "214" if r29 else "30" if r26 or r27 or r28 or r30 or r31 else "1",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS": "4",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE": "23" if r31 else "13",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED": "1",
            }
            if r25 or r26 or r27 or r28 or r29 or r30 or r31
            else {}
        ),
        **(
            {
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED": "1",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED": "1",
            }
            if r27 or r28 or r29 or r30 or r31
            else {}
        ),
        **(
            {
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_ADDRESS": "0x00021000" if r30 else "0x0b100040",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_BYTES": "320",
                "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_STATUS": "1",
                **(
                    {
                        "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_MAGIC_READBACK": "0x53463750",
                        "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED": "1",
                        "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_WIPED": "1",
                    }
                    if r30
                    else {}
                ),
            }
            if r29 or r30
            else {}
        ),
        "P7_PS_STAGE_RESULT": "FAIL",
        "P7_PS_STAGE_ERROR": (
            "P7 functional boundary case failed: index=8 length=30 status=4 error=23"
            if r31
            else "P7 functional boundary case failed: index=10 length=30 status=4 error=13"
            if r30
            else "P7 integrity failure snapshot publication marker missing"
            if r29 or r28
            else "P7 functional boundary case failed: index=8 length=30 status=4 error=13"
            if r26 or r27
            else "P7 functional boundary case failed: index=6 length=1 status=4 error=13"
            if r25
            else 'couldn\'t open "C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/hardware/p7/authorized_sequence/'
            'p7_20260712_stationary_app_r24_diag_suffix62/062_p7_ps_functional/bundle/'
            'boundary_8_descriptor_failure.bin": no such file or directory'
            if r24
            else "P7 functional boundary case failed: index=8 length=30"
        ),
    }
    append_error(errors, not duplicates and raw_markers == expected_markers, f"{label} raw marker set mismatch")
    failure_index = 10 if r30 else 13 if r29 else 11 if r28 else 8 if r26 or r27 or r31 else 6
    failure_descriptor = candidate.path.parent / "bundle" / f"boundary_{failure_index}_descriptor_failure.bin"
    if r25 or r26 or r27 or r28 or r29 or r30 or r31:
        try:
            descriptor = decode_p7_descriptor(failure_descriptor.read_bytes())
        except (OSError, ValueError, struct.error) as exc:
            errors.append(f"{label} failure descriptor invalid: {exc}")
            descriptor = {}
        boundary_input = candidate.path.parent / "bundle" / f"boundary_{failure_index}_input.bin"
        try:
            input_bytes = boundary_input.read_bytes()
        except OSError as exc:
            errors.append(f"{label} boundary input invalid: {exc}")
            input_bytes = b""
        expected_sha = hashlib.sha256(input_bytes).hexdigest()
        append_error(
            errors,
            input_bytes == (bytes(range(214)) if r29 else bytes(range(30)) if r26 or r27 or r28 or r30 or r31 else b"\x00")
            and descriptor.get("magic") == 0x53443750
            and descriptor.get("version") == 1
            and descriptor.get("command") == 1
            and descriptor.get("status") == 4
            and descriptor.get("session_epoch") == 0x50370001
            and descriptor.get("object_id") == (11 if r30 else 14 if r29 else 12 if r28 else 9 if r26 or r27 or r31 else 7)
            and descriptor.get("object_length") == (214 if r29 else 30 if r26 or r27 or r28 or r30 or r31 else 1)
            and descriptor.get("expected_crc32") == (zlib.crc32(input_bytes) & 0xFFFFFFFF) == (0xF05C083E if r29 else 0xC5665F58 if r26 or r27 or r28 or r30 or r31 else 0xD202EF8D)
            and descriptor.get("lane_policy") == (2 if r29 else 4 if r28 else 1 if r26 or r27 or r31 else 3)
            and descriptor.get("max_retries") == 3
            and descriptor.get("error_code") == (23 if r31 else 13)
            and descriptor.get("bytes_completed") == 0
            and descriptor.get("fragments_total") == 1
            and descriptor.get("fragments_completed") == (0 if r31 else 1)
            and descriptor.get("output_crc32") == (
                0 if r31 else 0xE56AEFE1 if r29 else 0x0B14A45E if r28 else 0x1FDA9DB9 if r27 or r30 else 0x0A703D75 if r26 else (zlib.crc32(b"\x02") & 0xFFFFFFFF)
            )
            and descriptor.get("fragment_attempts") == 1
            and descriptor.get("fallback_count") == 0
            and descriptor.get("expected_sha256") == expected_sha
            and descriptor.get("input_sha256") == expected_sha
            and descriptor.get("output_sha256") == (
                "0" * 64
                if r31
                else "85cc3c9bdc8b6699e216e48c446c9f4f7d861a8bcfef504fcaeb02b3e99ad750"
                if r30
                else "fa740d204a804cb81d21e7d56bff7091dbc387d59c9e50e2d400a4275f85bcf0"
                if r29
                else "152b23e36032b5b79a2f47434511a939aa869078ef97c37d757772102af7972c"
                if r28
                else "85cc3c9bdc8b6699e216e48c446c9f4f7d861a8bcfef504fcaeb02b3e99ad750"
                if r27
                else "7b1241c20725167eb4bf923caa908244ee622a994ec2e3fcc8cadea7584f1d46"
                if r26
                else expected_sha
            )
            and descriptor.get("p6_retry_count") == 0
            and descriptor.get("p6_retry_exhausted") == 0
            and descriptor.get("p6_tx_fail") == 0
            and descriptor.get("p6_crc_bad") == 0
            and descriptor.get("p6_payload_mismatch") == 0
            and descriptor.get("max_txd_high_cycles") == 8
            and descriptor.get("duty_violation_count") == 0
            and descriptor.get("lane0_fragments") == (0 if r29 or r31 else 1)
            and descriptor.get("lane1_fragments") == (1 if r28 or r29 else 0)
            and descriptor.get("replicated_fragments") == (1 if r28 else 0)
            and int(descriptor.get("start_ticks", 0)) > 0
            and int(descriptor.get("end_ticks", 0)) >= int(descriptor.get("start_ticks", 0))
            and (
                not (r30 or r31)
                or (
                    descriptor.get("start_ticks") == (3150968661 if r31 else 1621848612)
                    and descriptor.get("end_ticks") == (3151562286 if r31 else 1622475754)
                )
            )
            and descriptor.get("restart_count") == 0
            and descriptor.get("completion_sequence") == (11 if r30 else 14 if r29 else 12 if r28 else 9 if r26 or r27 or r31 else 7)
            and sha256_file(failure_descriptor)
            == (
                "60dd6a044ef42e7bd13273aad8d4c423cb74568a56d9006e20aba7d1c63efe33"
                if r31
                else "31bbae84a4619feab7312fe0a7afa683bded879788239c19f25c24f61fade980"
                if r30
                else "8df414a31c8beabb0706ee7c4afa61f87c51d83c4f58340cfc13cc556a989f37"
                if r29
                else "042c8059fca445532853554af7b4b67acba1a56fb5a32a96c6df557c25fff58e"
                if r28
                else "d6ff7937295d60a6c337a60989c80da61c58767b07082e5df965895ba8f0483a"
                if r27
                else "e367cde75315414d98e2db62c6ef175f6ee156f9566ea7f73192148662647847"
                if r26
                else "06be977397d309af45d492dea1208171153b9fa7324b4f52faccca01d21d1acb"
            )
            and not (candidate.path.parent / "bundle" / f"boundary_{failure_index}_output_result.bin").exists()
            and not (candidate.path.parent / "bundle" / f"boundary_{failure_index}_trace_result.bin").exists()
            and (
                (candidate.path.parent / "bundle" / f"boundary_{failure_index}_output_failure.bin").is_file()
                if r27 or r28 or r29 or r30 or r31
                else not (candidate.path.parent / "bundle" / f"boundary_{failure_index}_output_failure.bin").exists()
            )
            and (
                (candidate.path.parent / "bundle" / f"boundary_{failure_index}_trace_failure.bin").is_file()
                if r27 or r28 or r29 or r30 or r31
                else not (candidate.path.parent / "bundle" / f"boundary_{failure_index}_trace_failure.bin").exists()
            ),
            f"{label} exact CRC/SHA divergence descriptor boundary mismatch",
        )
        if r27 or r28 or r29 or r30 or r31:
            failure_output = candidate.path.parent / "bundle" / f"boundary_{failure_index}_output_failure.bin"
            failure_trace = candidate.path.parent / "bundle" / f"boundary_{failure_index}_trace_failure.bin"
            try:
                output_bytes = failure_output.read_bytes()
                trace_words = struct.unpack("<16I", failure_trace.read_bytes())
            except (OSError, struct.error) as exc:
                errors.append(f"{label} post-terminal output/trace capture invalid: {exc}")
                output_bytes = b""
                trace_words = (0,) * 16
            append_error(
                errors,
                output_bytes == (bytes(100) + b"\x02" + bytes(113) if r29 else bytes(30))
                and sha256_file(failure_output) == ("c087c4c3d79aa6dabe40b1a5f5d8cc1b7d96be35a2b4795b692171fdf58a3c1b" if r29 else "0679246d6c4216de0daa08e5523fb2674db2b6599c3b72ff946b488a15290b62")
                and sha256_file(failure_trace) == ("71b5234332dc3355db44b7e36b459d3805bdf3b85968306c59ed9b7e35adb969" if r31 else "7e22964c05ee1c45a9d14f04444a52ece17c61296547c1ae716d373efc2ead0d" if r30 else "c8fcb94f910b24a4e0da0f5a59eb128343936a8f66ef874e547e5f69a6765883" if r29 else "775a705154de00d454df4390dc4d8cabaa66f00eb17a75333d840eee7b53c608" if r28 else "dd4721823cdd22ae8537c86582eca9ea268e3e9faf4abd824a22fae2bbd71bda")
                and trace_words[0] == P7_TRACE_MAGIC
                and trace_words[1] == 0x50370001
                and trace_words[2] == (11 if r30 else 14 if r29 else 12 if r28 else 9)
                and (trace_words[3] & 0xFFFF) == 0
                and (trace_words[3] >> 16) == 1
                and trace_words[4:8] == ((1, 1, 0, 23) if r31 else (1, 1, 1, 0) if r30 else (2, 1, 1, 0) if r29 else (3, 1, 1, 0) if r28 else (1, 1, 0, 0))
                and trace_words[8] == (0xBBD10203 if r31 else 0x60AC6840 if r30 else 0x642DF8E6 if r29 else 0x6BEE2989 if r28 else 0x5F982668)
                and trace_words[9] == 0
                and trace_words[10] == (0xBBD8B4D9 if r31 else 0x60B3FE1D if r30 else 0x643ED1ED if r29 else 0x6BF5C030 if r28 else 0x5F9FBC65)
                and trace_words[11:] == ((0, 0, 0, 0, 23) if r31 else (0, 0, 0, 0, 0)),
                f"{label} exact post-terminal wipe/fragment trace capture mismatch",
            )
            if r30:
                snapshot_path = candidate.path.parent / "bundle" / "boundary_10_integrity_snapshot_failure.bin"
                wipe_path = candidate.path.parent / "bundle" / "boundary_10_integrity_snapshot_wipe_verify.bin"
                try:
                    snapshot_bytes = snapshot_path.read_bytes()
                    snapshot_words = struct.unpack("<16I", snapshot_bytes[:64])
                    wiped_bytes = wipe_path.read_bytes()
                except (OSError, struct.error) as exc:
                    errors.append(f"{label} integrity snapshot capture invalid: {exc}")
                    snapshot_bytes = b""
                    snapshot_words = (0,) * 16
                    wiped_bytes = b""
                corrupted_payload = bytes.fromhex(
                    "000002030000060700000a0b00000e0f"
                    "000012130000161700001a1b0000"
                )
                output_digest_words = struct.unpack(
                    ">8I",
                    bytes.fromhex(
                        "85cc3c9bdc8b6699e216e48c446c9f4f"
                        "7d861a8bcfef504fcaeb02b3e99ad750"
                    ),
                )
                append_error(
                    errors,
                    len(snapshot_bytes) == 320
                    and snapshot_words[:8]
                    == (
                        0x53463750,
                        1,
                        0x50370001,
                        11,
                        30,
                        30,
                        0x1FDA9DB9,
                        13,
                    )
                    and snapshot_words[8:] == output_digest_words
                    and snapshot_bytes[64:94] == corrupted_payload
                    and snapshot_bytes[94:] == bytes(226)
                    and sha256_file(snapshot_path)
                    == "e99af3fe526f68a64c6bbc42207db7d440008e3a38b2685d2a812ee3e02fd95d"
                    and wiped_bytes == bytes(320)
                    and sha256_file(wipe_path)
                    == "7b6436b0c98f62380866d9432c2af0ee08ce16a171bda6951aecd95ee1307d61",
                    f"{label} exact OCM failure snapshot/wipe evidence mismatch",
                )
            elif r28 or r29 or r31:
                snapshot_index = 13 if r29 else 11
                append_error(
                    errors,
                    not (candidate.path.parent / "bundle" / f"boundary_{8 if r31 else snapshot_index}_integrity_snapshot_failure.bin").exists()
                    and not (candidate.path.parent / "bundle" / f"boundary_{8 if r31 else snapshot_index}_integrity_snapshot_wipe_verify.bin").exists(),
                    f"{label} unexpectedly contains a captured failure snapshot",
                )
    else:
        append_error(
            errors,
            not (candidate.path.parent / "bundle" / "boundary_8_descriptor_failure.bin").exists(),
            f"{label} unexpectedly contains the later diagnostic failure descriptor",
        )
    raw_manifest_errors, _record = validate_raw_evidence_manifest(candidate, evidence)
    errors.extend(raw_manifest_errors)
    append_error(
        errors,
        isinstance(data.get("bundle_post_shutdown_verification"), dict)
        and data["bundle_post_shutdown_verification"].get("passed") is True
        and data["bundle_post_shutdown_verification"].get("immutable_pre_post_equal") is True,
        f"{label} immutable bundle verification mismatch",
    )
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    append_error(
        errors,
        variant
        in {
            HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED,
            HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED,
            HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED,
            HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED,
            HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED,
        },
        f"{label} failure class mismatch",
    )
    return errors


def _old_commit_axi4_burst_word_order_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r15's exact AXI4 burst word-order rejection with zero coverage."""

    errors: list[str] = []
    label = "historical r15"
    data = candidate.data
    transaction = data.get("transaction_validation")
    expected_metrics = {
        "operation_count": 4269,
        "minimum_run_hw_axi_call_count": 246,
        "multi_transaction_batch_count": 122,
        "batched_single_word_transaction_count": 4145,
        "max_batch_transactions": 62,
        "standalone_run_hw_axi_call_count": 124,
        "axi4_incr_burst_count": 60,
        "axi4_incr_burst_word_count": 3567,
        "max_axi4_incr_burst_words": 62,
        "queued_single_run_hw_axi_call_count": 83,
        "queued_single_multi_transaction_batch_count": 62,
        "queued_single_transaction_count": 599,
        "max_queued_single_transactions": 16,
        "ordered_control_write_run_hw_axi_call_count": 63,
        "queued_control_write_transaction_count": 0,
    }
    append_error(
        errors,
        isinstance(transaction, dict)
        and all(transaction.get(key) == value for key, value in expected_metrics.items()),
        f"{label} ordered-control/AXI4 transaction metrics mismatch",
    )
    append_error(
        errors,
        _historical_preflight_variant(candidate) == HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
        f"{label} failure class mismatch",
    )
    append_error(
        errors,
        data.get("reason")
        == "strict backend parser rejected candidate evidence; candidate and shutdown success cannot promote the stage",
        f"{label} wrapper reason mismatch",
    )

    # r14 and r15 share every process, shutdown, raw marker, backend, event,
    # runtime, and lock invariant.  Normalize only the fields explicitly
    # checked above so the common validator cannot silently accept an r15
    # metric/reason mutation.
    normalized_data = json.loads(json.dumps(data))
    normalized_transaction = normalized_data.get("transaction_validation", {})
    normalized_transaction.update(
        {
            "minimum_run_hw_axi_call_count": 226,
            "multi_transaction_batch_count": 122,
            "batched_single_word_transaction_count": 4165,
            "max_batch_transactions": 62,
            "standalone_run_hw_axi_call_count": 104,
            "axi4_incr_burst_count": 60,
            "axi4_incr_burst_word_count": 3567,
            "max_axi4_incr_burst_words": 62,
            "queued_single_run_hw_axi_call_count": 126,
            "queued_single_multi_transaction_batch_count": 62,
            "queued_single_transaction_count": 662,
            "max_queued_single_transactions": 16,
        }
    )
    normalized_data["reason"] = "stage return code/markers failed; nonzero return codes can never be promoted"
    normalized = Candidate(
        candidate.path,
        normalized_data,
        candidate.kind,
        candidate.stage,
        candidate.timestamp,
    )
    errors.extend(
        item.replace("historical r14", label)
        for item in _old_commit_axi4_queued_control_order_failure_errors(normalized, evidence)
    )

    _reversal_proofs, reversal_errors = _axi4_burst_word_order_reversal_proofs(candidate)
    errors.extend(reversal_errors)
    return errors


def _old_commit_axi4_queued_control_order_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r14's post-shutdown COMMIT-order rejection with zero coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r14"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "p6_frame_regression", f"{label} failure is not the JTAG P6 frame-regression stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_p6_frame_regression_m1" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_candidate", "programmed_shutdown_before", "programmed_shutdown_after", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 4269
        and transaction.get("minimum_run_hw_axi_call_count") == 226
        and transaction.get("multi_transaction_batch_count") == 122
        and transaction.get("batched_single_word_transaction_count") == 4165
        and transaction.get("max_batch_transactions") == 62
        and transaction.get("standalone_run_hw_axi_call_count") == 104
        and transaction.get("axi4_incr_burst_count") == 60
        and transaction.get("axi4_incr_burst_word_count") == 3567
        and transaction.get("max_axi4_incr_burst_words") == 62
        and transaction.get("queued_single_run_hw_axi_call_count") == 126
        and transaction.get("queued_single_multi_transaction_batch_count") == 62
        and transaction.get("queued_single_transaction_count") == 662
        and transaction.get("max_queued_single_transactions") == 16
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE0_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 4096
        and backend_manifest.get("input_sha256") == "d63320acd81e8ea9e08c7932552f04ca8bd45a673c40003ff4f7b6143d91081d"
        and backend_manifest.get("lane_policy") == "LANE0_ONLY"
        and backend_manifest.get("transaction_operation_count") == 4269,
        f"{label} transaction/backend manifest boundary mismatch",
    )

    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_markers, preflight_duplicates = parse_marker_text(
        marker_text(candidate.path.parent / "p7_preflight_result.txt")
    )
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    else:
        expected_stdout = (candidate.path.parent / "p7_jtag_axi_stage.stdout.log").resolve(strict=False)
        expected_stderr = (candidate.path.parent / "p7_jtag_axi_stage.stderr.log").resolve(strict=False)
        append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stdout and expected_stdout.is_file(), f"{label} candidate stdout binding mismatch")
        append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stderr and expected_stderr.is_file(), f"{label} candidate stderr binding mismatch")
    append_error(
        errors,
        stage.get("name") == "jtag_axi_stage"
        and stage.get("returncode") == 0
        and stage.get("passed") is True
        and stage.get("failures") == []
        and stage.get("timed_out") is False
        and stage.get("process_tree_terminated") is False
        and stage.get("process_tree_reaped") is True,
        f"{label} candidate process is not an exact inner PASS",
    )
    append_error(errors, data.get("stage_failures") == [] and data.get("internal_error") == "", f"{label} wrapper stage/internal failure fields mismatch")
    expected_backend_failure = "BackendValidationError: TX_CRC32: fragment 0 committed CRC differs from manifest"
    append_error(
        errors,
        data.get("backend_parse_failure") == expected_backend_failure
        and data.get("backend_parse")
        == {"passed": False, "failure": expected_backend_failure, "attempted_after_shutdown": True},
        f"{label} backend rejection mismatch",
    )
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} historical wrapper reason mismatch")
    append_error(errors, not (candidate.path.parent / "p7_jtag_backend_parse_summary.json").exists(), f"{label} unexpectedly contains a backend PASS summary")

    raw, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates, f"{label} raw result contains duplicate markers")
    expected_raw_subset = {
        "P7_CANDIDATE_PROGRAMMED": "1",
        "P7_TCL_PROGRAMMING_ATTEMPTED": "1",
        "P7_JTAG_AXI_TRANSACTIONS": "PASS",
        "P7_TRANSACTION_COUNT": "4269",
        "P7_JTAG_STAGE_RESULT": "PASS",
        "P7F00000_TX_CRC32": "A155F91B",
        "P7F00000_RX_CRC32": "A155F91B",
        "P7F00000_RX_DIGEST": "A155F91B",
        "P7F00000_TXW000": "50414652",
        "P7F00000_RXW000": "00414652",
        "P7F00000_CRC_BAD": "00000000",
        "P7F00000_STATUS": "00000017",
        "P7F00000_FRAME_GOOD": "00000001",
        "P7F00000_TX_COUNT": "00000001",
    }
    append_error(errors, all(raw.get(key) == value for key, value in expected_raw_subset.items()), f"{label} raw result does not bind the exact first-fragment stale-header CRC contrast")

    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "backend_parse_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 10:
        append_error(errors, events[4].get("candidate_returncode") == 0 and events[4].get("process_tree_reaped") is True, f"{label} candidate-reap event mismatch")
        append_error(errors, events[5].get("returncode") == 0 and events[5].get("passed") is True, f"{label} inner stage event is not PASS")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event is not PASS")
        append_error(errors, events[8].get("passed") is False and events[8].get("failure") == expected_backend_failure, f"{label} backend event mismatch")
        append_error(errors, events[9].get("status") == "FAIL_STAGE", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(
        errors,
        isinstance(runtime, dict)
        and runtime.get("authorized_max_seconds") == 960
        and runtime.get("within_authorized_limit") is True
        and isinstance(runtime.get("elapsed_seconds"), (int, float))
        and 0 <= float(runtime.get("elapsed_seconds")) <= 960,
        f"{label} runtime record is invalid",
    )
    return errors


def _old_commit_outer_deadline_abort_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r9's deliberate fail-closed abort without granting coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r9"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "p6_frame_regression", f"{label} failure is not a JTAG P6 frame-regression stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_p6_frame_regression_m2" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_shutdown_before", "programmed_shutdown_after", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    append_error(errors, data.get("programmed_candidate") is False, f"{label} incorrectly claims candidate programming completed")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 4269
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE1_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 4096
        and backend_manifest.get("input_sha256") == "a7abce3a5f3164feb667e984f8e38f6e6fc3a7f87e54cc0b2008aa15962a1e7d"
        and backend_manifest.get("lane_policy") == "LANE1_ONLY"
        and backend_manifest.get("transaction_operation_count") == 4269,
        f"{label} transaction/backend manifest boundary mismatch",
    )
    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_markers, preflight_duplicates = parse_marker_text(
        marker_text(candidate.path.parent / "p7_preflight_result.txt")
    )
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    expected_stage_failures = [
        "stage process returned nonzero exit code: 130",
        "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=MISSING",
        "stage marker mismatch: P7_CANDIDATE_PROGRAMMED expected=1 observed=MISSING",
        "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
        "stage marker mismatch: P7_TRANSACTION_COUNT expected=4269 observed=MISSING",
        "stage PASS marker missing from stdout",
    ]
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 130 and stage.get("passed") is False, f"{label} candidate return/result mismatch")
    append_error(errors, stage.get("abort_seen") is True and stage.get("timed_out") is False and stage.get("interrupted") is False, f"{label} candidate abort boundary mismatch")
    append_error(errors, stage.get("process_tree_terminated") is True and stage.get("process_tree_reaped") is True, f"{label} candidate was not safely terminated/reaped")
    append_error(errors, stage.get("containment_assigned") is True and stage.get("containment_closed") is True and stage.get("descendant_count_after") == 0, f"{label} candidate containment mismatch")
    append_error(errors, stage.get("containment_cleanup_attempted") is True and stage.get("containment_cleanup_terminated") is True, f"{label} candidate forced-cleanup provenance mismatch")
    append_error(errors, stage.get("expected_tool_daemon_classification") == "NONE" and stage.get("expected_tool_daemon_grace_used") is False, f"{label} candidate helper topology mismatch")
    append_error(errors, stage.get("launch_error") == "" and stage.get("failures") == expected_stage_failures, f"{label} candidate failure provenance mismatch")
    append_error(errors, data.get("stage_failures") == expected_stage_failures and data.get("backend_parse_failure") == "" and data.get("backend_parse") is None and data.get("internal_error") == "", f"{label} wrapper failure fields mismatch")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} wrapper reason mismatch")
    append_error(errors, not (candidate.path.parent / "p7_jtag_backend_parse_summary.json").exists(), f"{label} unexpectedly contains a backend PASS summary")

    raw_path = raw_marker_path(candidate)
    raw, raw_duplicates = raw_markers(candidate)
    expected_raw = {
        "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PART": CANONICAL_FULL_PART,
        "P7_HW_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_CANONICAL_PART": CANONICAL_FULL_PART,
        "P7_HW_LIVE_PART": CANONICAL_LIVE_PART,
        "P7_HW_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
    }
    append_error(errors, raw_path.is_file() and not raw_duplicates and raw == expected_raw, f"{label} raw result is not the exact pre-program abort boundary")
    append_error(errors, resolve_reference(stage.get("result_file"), document=candidate.path, repo_root=evidence.repo_root) == raw_path.resolve(strict=False), f"{label} candidate result path mismatch")

    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 9:
        append_error(errors, events[4].get("candidate_returncode") == 130 and events[4].get("process_tree_reaped") is True, f"{label} candidate-reap event mismatch")
        append_error(errors, events[5].get("returncode") == 130 and events[5].get("passed") is False, f"{label} stage event mismatch")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_STAGE", f"{label} end event mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 960 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 0 <= float(runtime.get("elapsed_seconds")) <= 960, f"{label} runtime record is invalid")
    return errors


def _old_commit_1m_jtag_timeout_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r10's bounded 1 MiB diagnostic timeout with zero coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r10"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "large_object_jtag", f"{label} failure is not a large-object JTAG stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_large_jtag_1m_l0_random" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_candidate", "programmed_shutdown_before", "programmed_shutdown_after", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 1_073_038
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE0_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 1_048_576
        and backend_manifest.get("input_sha256") == "de7e28fb7ae8b57b4280dc13d61316442d564631d71caa52b28284929b0a8549"
        and backend_manifest.get("lane_policy") == "LANE0_ONLY"
        and backend_manifest.get("transaction_operation_count") == 1_073_038,
        f"{label} transaction/backend manifest boundary mismatch",
    )
    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_markers, preflight_duplicates = parse_marker_text(
        marker_text(candidate.path.parent / "p7_preflight_result.txt")
    )
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    expected_stage_failures = [
        "stage process returned nonzero exit code: 124",
        "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=MISSING",
        "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
        "stage marker mismatch: P7_TRANSACTION_COUNT expected=1073038 observed=MISSING",
        "stage PASS marker missing from stdout",
    ]
    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    else:
        expected_stdout = (candidate.path.parent / "p7_jtag_axi_stage.stdout.log").resolve(strict=False)
        expected_stderr = (candidate.path.parent / "p7_jtag_axi_stage.stderr.log").resolve(strict=False)
        append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stdout and expected_stdout.is_file(), f"{label} candidate stdout binding mismatch")
        append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stderr and expected_stderr.is_file(), f"{label} candidate stderr binding mismatch")
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 124 and stage.get("passed") is False, f"{label} candidate return/result mismatch")
    append_error(errors, stage.get("timed_out") is True and stage.get("abort_seen") is False and stage.get("interrupted") is False, f"{label} candidate timeout boundary mismatch")
    append_error(errors, stage.get("process_tree_terminated") is True and stage.get("process_tree_reaped") is True, f"{label} candidate was not safely terminated/reaped")
    append_error(errors, stage.get("containment_cleanup_attempted") is True and stage.get("containment_cleanup_terminated") is True, f"{label} candidate forced-cleanup provenance mismatch")
    append_error(errors, stage.get("expected_tool_daemon_classification") == "NONE" and stage.get("expected_tool_daemon_grace_used") is False, f"{label} candidate helper topology mismatch")
    append_error(errors, stage.get("failures") == expected_stage_failures and stage.get("launch_error") == "", f"{label} candidate failure provenance mismatch")
    append_error(errors, data.get("stage_failures") == expected_stage_failures and data.get("backend_parse_failure") == "" and data.get("backend_parse") is None and data.get("internal_error") == "", f"{label} wrapper failure fields mismatch")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} wrapper reason mismatch")
    append_error(errors, not (candidate.path.parent / "p7_jtag_backend_parse_summary.json").exists(), f"{label} unexpectedly contains a backend PASS summary")

    raw, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates, f"{label} raw result contains duplicate markers")
    expected_identity = {
        "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PART": CANONICAL_FULL_PART,
        "P7_HW_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_CANONICAL_PART": CANONICAL_FULL_PART,
        "P7_HW_LIVE_PART": CANONICAL_LIVE_PART,
        "P7_HW_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_CANDIDATE_PROGRAMMED": "1",
    }
    append_error(errors, all(raw.get(key) == value for key, value in expected_identity.items()), f"{label} raw identity/programming boundary mismatch")
    append_error(errors, raw.get("P7F00000_DONE") == "00000017" and raw.get("P7F00944_RXW017") == "F72C793C", f"{label} raw partial-progress boundary mismatch")
    append_error(errors, not any(key.startswith("P7F00945_") for key in raw), f"{label} raw log advanced beyond the frozen timeout boundary")
    for forbidden in ("P7_JTAG_AXI_TRANSACTIONS", "P7_TRANSACTION_COUNT", "P7_JTAG_STAGE_RESULT"):
        append_error(errors, forbidden not in raw, f"{label} raw timeout incorrectly contains terminal marker {forbidden}")
    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(errors, [item.get("event") for item in events] == ["authorized_execution_begin", "preflight_finished", "shutdown_before_finished", "candidate_started", "candidate_child_reaped", "stage_finished", "shutdown_after_started", "shutdown_after_finished", "authorized_execution_end"], f"{label} event sequence mismatch")
    if len(events) == 9:
        append_error(errors, events[5].get("returncode") == 124 and events[5].get("passed") is False, f"{label} timeout event mismatch")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_STAGE", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 1800 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 1400 <= float(runtime.get("elapsed_seconds")) <= 1800, f"{label} runtime record is invalid")
    return errors


def _old_commit_1m_jtag_queued_timeout_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r13's bounded queued 1 MiB diagnostic timeout with zero coverage."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r13"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "large_object_jtag", f"{label} failure is not a large-object JTAG stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_STAGE", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_large_jtag_1m_l0_random" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_candidate", "programmed_shutdown_before", "programmed_shutdown_after", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 1_073_038
        and transaction.get("minimum_single_word_axi4lite_transaction_count") == 1_073_038
        and transaction.get("minimum_run_hw_axi_call_count") == 224_401
        and transaction.get("multi_transaction_batch_count") == 58_527
        and transaction.get("batched_single_word_transaction_count") == 907_164
        and transaction.get("max_batch_transactions") == 16
        and transaction.get("standalone_run_hw_axi_call_count") == 165_874
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE0_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 1_048_576
        and backend_manifest.get("input_sha256") == "de7e28fb7ae8b57b4280dc13d61316442d564631d71caa52b28284929b0a8549"
        and backend_manifest.get("lane_policy") == "LANE0_ONLY"
        and backend_manifest.get("transaction_operation_count") == 1_073_038,
        f"{label} queued transaction/backend manifest boundary mismatch",
    )
    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_markers, preflight_duplicates = parse_marker_text(
        marker_text(candidate.path.parent / "p7_preflight_result.txt")
    )
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))
    errors.extend(shutdown_errors(candidate, "after", evidence=evidence))

    expected_stage_failures = [
        "stage process returned nonzero exit code: 124",
        "stage marker mismatch: P7_JTAG_STAGE_RESULT expected=PASS observed=MISSING",
        "stage marker mismatch: P7_JTAG_AXI_TRANSACTIONS expected=PASS observed=MISSING",
        "stage marker mismatch: P7_TRANSACTION_COUNT expected=1073038 observed=MISSING",
        "stage PASS marker missing from stdout",
    ]
    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    else:
        expected_stdout = (candidate.path.parent / "p7_jtag_axi_stage.stdout.log").resolve(strict=False)
        expected_stderr = (candidate.path.parent / "p7_jtag_axi_stage.stderr.log").resolve(strict=False)
        append_error(errors, resolve_reference(stage.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stdout and expected_stdout.is_file(), f"{label} candidate stdout binding mismatch")
        append_error(errors, resolve_reference(stage.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root) == expected_stderr and expected_stderr.is_file(), f"{label} candidate stderr binding mismatch")
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 124 and stage.get("passed") is False, f"{label} candidate return/result mismatch")
    append_error(errors, stage.get("timed_out") is True and stage.get("abort_seen") is False and stage.get("interrupted") is False, f"{label} candidate timeout boundary mismatch")
    append_error(errors, stage.get("process_tree_terminated") is True and stage.get("process_tree_reaped") is True, f"{label} candidate was not safely terminated/reaped")
    append_error(errors, stage.get("containment_cleanup_attempted") is True and stage.get("containment_cleanup_terminated") is True, f"{label} candidate forced-cleanup provenance mismatch")
    append_error(errors, stage.get("expected_tool_daemon_classification") == "NONE" and stage.get("expected_tool_daemon_grace_used") is False, f"{label} candidate helper topology mismatch")
    append_error(errors, stage.get("failures") == expected_stage_failures and stage.get("launch_error") == "", f"{label} candidate failure provenance mismatch")
    append_error(errors, data.get("stage_failures") == expected_stage_failures and data.get("backend_parse_failure") == "" and data.get("backend_parse") is None and data.get("internal_error") == "", f"{label} wrapper failure fields mismatch")
    append_error(errors, data.get("reason") == "stage return code/markers failed; nonzero return codes can never be promoted", f"{label} wrapper reason mismatch")
    append_error(errors, not (candidate.path.parent / "p7_jtag_backend_parse_summary.json").exists(), f"{label} unexpectedly contains a backend PASS summary")

    raw, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates, f"{label} raw result contains duplicate markers")
    expected_identity = {
        "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PART": CANONICAL_FULL_PART,
        "P7_HW_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_CANONICAL_PART": CANONICAL_FULL_PART,
        "P7_HW_LIVE_PART": CANONICAL_LIVE_PART,
        "P7_HW_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_CANDIDATE_PROGRAMMED": "1",
    }
    append_error(errors, all(raw.get(key) == value for key, value in expected_identity.items()), f"{label} raw identity/programming boundary mismatch")
    append_error(errors, raw.get("P7F00000_DONE") == "00000017" and raw.get("P7F01666_FRAME_BAD") == "00000000", f"{label} raw queued partial-progress boundary mismatch")
    append_error(errors, not any(key.startswith("P7F01667_") for key in raw), f"{label} raw log advanced beyond the frozen timeout boundary")
    try:
        raw_text = (candidate.path.parent / "p7_jtag_axi_raw_result.txt").read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label} raw result unreadable: {exc}")
        raw_text = ""
    append_error(errors, raw_text.endswith("P7F01666_ACK_SEN") and not raw_text.endswith("\n"), f"{label} raw torn terminal write boundary mismatch")
    for forbidden in ("P7_JTAG_AXI_TRANSACTIONS", "P7_TRANSACTION_COUNT", "P7_JTAG_STAGE_RESULT"):
        append_error(errors, forbidden not in raw, f"{label} raw timeout incorrectly contains terminal marker {forbidden}")
    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(errors, [item.get("event") for item in events] == ["authorized_execution_begin", "preflight_finished", "shutdown_before_finished", "candidate_started", "candidate_child_reaped", "stage_finished", "shutdown_after_started", "shutdown_after_finished", "authorized_execution_end"], f"{label} event sequence mismatch")
    if len(events) == 9:
        append_error(errors, events[5].get("returncode") == 124 and events[5].get("passed") is False, f"{label} timeout event mismatch")
        append_error(errors, events[7].get("returncode") == 0 and events[7].get("passed") is True, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_STAGE", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 1800 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 1500 <= float(runtime.get("elapsed_seconds")) <= 1800, f"{label} runtime record is invalid")
    return errors


def _old_commit_shutdown_helper_exit_race_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r6's programmed shutdown followed by a fail-closed helper-exit race."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r6"
    append_error(
        errors,
        candidate.kind == "jtag" and candidate.stage == "fragment_boundary_jtag",
        f"{label} failure is not the JTAG fragment-boundary stage",
    )
    append_error(
        errors,
        candidate.executed and candidate.marker == "FAIL_SHUTDOWN_AFTER",
        f"{label} execution/result boundary mismatch",
    )
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(
        errors,
        data.get("stage_name") == "p7_fragment_boundary_216_rep3"
        and data.get("semantic_mode") == "rfap",
        f"{label} stage identity/semantic mode mismatch",
    )
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
    ):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    append_error(errors, data.get("programmed_shutdown_after") is False, f"{label} incorrectly promotes shutdown-after")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 303
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "REPLICATE_0X3"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 216
        and backend_manifest.get("lane_policy") == "REPLICATE_0X3"
        and backend_manifest.get("transaction_operation_count") == 303,
        f"{label} transaction/backend manifest boundary mismatch",
    )

    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_path = candidate.path.parent / "p7_preflight_result.txt"
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(
        errors,
        not preflight_duplicates
        and _historical_preflight_variant(candidate)
        == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
        f"{label} failure class mismatch",
    )
    append_error(
        errors,
        data.get("target_identity") == dict(preflight_markers)
        and data.get("preflight_failures") == [],
        f"{label} preflight identity/failure boundary mismatch",
    )
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))

    stage_process = data.get("stage_process")
    if not isinstance(stage_process, dict):
        errors.append(f"{label} candidate process record missing")
        stage_process = {}
    else:
        errors.extend(process_record_errors(stage_process, f"{label} candidate", document=candidate.path, repo_root=evidence.repo_root))
    append_error(
        errors,
        stage_process.get("name") == "jtag_axi_stage"
        and stage_process.get("returncode") == 0
        and stage_process.get("passed") is True
        and stage_process.get("failures") == [],
        f"{label} candidate process is not an exact inner PASS",
    )
    append_error(errors, data.get("stage_failures") == [] and data.get("internal_error") == "", f"{label} wrapper stage/internal failure fields mismatch")

    shutdown_after = data.get("shutdown_after")
    if not isinstance(shutdown_after, dict):
        errors.append(f"{label} shutdown-after record missing")
        shutdown_after = {}
    append_error(
        errors,
        shutdown_after.get("name") == "shutdown_after"
        and shutdown_after.get("returncode") == 125
        and shutdown_after.get("passed") is False
        and shutdown_after.get("failures") == ["shutdown process returned nonzero exit code: 125"]
        and shutdown_after.get("timed_out") is False
        and shutdown_after.get("abort_seen") is False
        and shutdown_after.get("interrupted") is False
        and shutdown_after.get("process_tree_reaped") is False
        and shutdown_after.get("process_tree_terminated") is True
        and shutdown_after.get("containment_cleanup_attempted") is True
        and shutdown_after.get("containment_cleanup_terminated") is True
        and shutdown_after.get("containment_assigned") is True
        and shutdown_after.get("containment_closed") is True
        and shutdown_after.get("descendant_count_after") == 0,
        f"{label} shutdown-after fail-closed containment facts mismatch",
    )
    append_error(
        errors,
        shutdown_after.get("expected_tool_daemon_classification")
        == "EXACT_R2_VIVADO_EXIT_HELPER_FOREST"
        and shutdown_after.get("expected_tool_daemon_grace_used") is True
        and shutdown_after.get("expected_tool_daemon_grace_seconds") == 30.0
        and shutdown_after.get("expected_tool_daemon_topology_monotonic") is True
        and shutdown_after.get("expected_tool_daemon_topology_terminal_empty") is False
        and shutdown_after.get("process_identity_query_retry_count") == 1
        and shutdown_after.get("process_exit_race_recheck_count") == 1
        and shutdown_after.get("process_identity_query_retried") is True
        and shutdown_after.get("process_exit_race_rechecked") is True
        and shutdown_after.get("expected_tool_daemon_hashes_verified") is True
        and shutdown_after.get("expected_tool_daemon_prelaunch_hashes_verified") is True
        and shutdown_after.get("expected_tool_daemon_postexit_hashes_verified") is True
        and isinstance(shutdown_after.get("expected_tool_daemon_grace_elapsed_seconds"), (int, float))
        and 0 < shutdown_after.get("expected_tool_daemon_grace_elapsed_seconds") < 30
        and isinstance(shutdown_after.get("expected_tool_daemon_topology_revalidation_count"), int)
        and not isinstance(shutdown_after.get("expected_tool_daemon_topology_revalidation_count"), bool)
        and 0 < shutdown_after.get("expected_tool_daemon_topology_revalidation_count")
        and isinstance(shutdown_after.get("expected_tool_daemon_topology_max_sample_gap_seconds"), (int, float))
        and 0 <= shutdown_after.get("expected_tool_daemon_topology_max_sample_gap_seconds") <= 0.25
        and "parent PID lookup missed active contained processes" in str(shutdown_after.get("containment_query_error", ""))
        and shutdown_after.get("expected_tool_daemon_topology_error") == "",
        f"{label} shutdown-after helper-exit race provenance mismatch",
    )
    shutdown_result = candidate.path.parent / "p7_shutdown_after_result.txt"
    shutdown_markers, shutdown_duplicates = parse_marker_text(marker_text(shutdown_result))
    canonical_shutdown = (
        evidence.repo_root / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    ).resolve(strict=False)
    append_error(
        errors,
        not shutdown_duplicates
        and shutdown_markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
        and resolve_reference(
            shutdown_markers.get("TFDU_SHUTDOWN_PROGRAMMED"),
            document=shutdown_result,
            repo_root=evidence.repo_root,
        )
        == canonical_shutdown
        and shutdown_markers.get("P7_SHUTDOWN_RESULT") == "PASS",
        f"{label} shutdown-after result does not prove the programmed shutdown image",
    )
    append_error(
        errors,
        data.get("reason") == "stage is incomplete because shutdown-after lacked rc=0 plus marker"
        and data.get("backend_parse") is None
        and data.get("backend_parse_failure") == "",
        f"{label} fail-closed reason/backend boundary mismatch",
    )

    raw, raw_duplicates = raw_markers(candidate)
    append_error(
        errors,
        not raw_duplicates
        and raw.get("P7_CANDIDATE_PROGRAMMED") == "1"
        and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1"
        and raw.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS"
        and raw.get("P7_TRANSACTION_COUNT") == "303"
        and raw.get("P7_JTAG_STAGE_RESULT") == "PASS",
        f"{label} raw candidate PASS markers mismatch",
    )
    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(
        errors,
        [item.get("event") for item in events]
        == [
            "authorized_execution_begin",
            "preflight_finished",
            "shutdown_before_finished",
            "candidate_started",
            "candidate_child_reaped",
            "stage_finished",
            "shutdown_after_started",
            "shutdown_after_finished",
            "authorized_execution_end",
        ],
        f"{label} event sequence mismatch",
    )
    if len(events) == 9:
        append_error(errors, events[5].get("returncode") == 0 and events[5].get("passed") is True, f"{label} inner stage event is not PASS")
        append_error(errors, events[7].get("returncode") == 125 and events[7].get("passed") is False, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_SHUTDOWN_AFTER", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(
        errors,
        isinstance(runtime, dict)
        and runtime.get("authorized_max_seconds") == 900
        and runtime.get("within_authorized_limit") is True
        and isinstance(runtime.get("elapsed_seconds"), (int, float))
        and 0 <= float(runtime.get("elapsed_seconds")) <= 900,
        f"{label} runtime record is invalid",
    )
    return errors


def _old_commit_shutdown_timeout_failure_errors(
    candidate: Candidate,
    evidence: RepositoryEvidence,
) -> list[str]:
    """Validate r7's timed-out shutdown-before-programming failure exactly."""

    data = candidate.data
    errors: list[str] = []
    label = "historical r7"
    append_error(errors, candidate.kind == "jtag" and candidate.stage == "p6_frame_regression", f"{label} failure is not the JTAG P6 frame-regression stage")
    append_error(errors, candidate.executed and candidate.marker == "FAIL_SHUTDOWN_AFTER", f"{label} execution/result boundary mismatch")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", f"{label} promoted or omitted hardware acceptance")
    append_error(errors, data.get("stage_name") == "p7_p6_frame_regression_m2" and data.get("semantic_mode") == "rfap", f"{label} stage identity/semantic mode mismatch")
    for key in ("programmed_fpga", "programmed_candidate", "programmed_shutdown_before", "drove_tfdu_txd", "enabled_tfdu_receiver"):
        append_error(errors, data.get(key) is True, f"{label} does not preserve {key}=true")
    append_error(errors, data.get("programmed_shutdown_after") is False, f"{label} incorrectly promotes shutdown-after")
    for key in ("started_ps_elf", "uart_access", "ethernet_used", "motion_used"):
        append_error(errors, data.get(key) is False, f"{label} does not explicitly prove {key}=false")
    append_error(errors, data.get("child_reaped_before_shutdown_after") is True, f"{label} candidate was not reaped before shutdown-after")

    transaction = data.get("transaction_validation")
    backend_manifest = transaction.get("backend_manifest") if isinstance(transaction, dict) else None
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("operation_count") == 4269
        and transaction.get("metadata") == {"BACKEND": "p7_jtag_backend", "LANE_POLICY": "LANE1_ONLY"}
        and isinstance(backend_manifest, dict)
        and backend_manifest.get("schema") == JTAG_MANIFEST_SCHEMA
        and backend_manifest.get("input_length") == 4096
        and backend_manifest.get("lane_policy") == "LANE1_ONLY"
        and backend_manifest.get("transaction_operation_count") == 4269,
        f"{label} transaction/backend manifest boundary mismatch",
    )
    preflight = data.get("preflight_process")
    if not isinstance(preflight, dict):
        errors.append(f"{label} preflight process record missing")
    else:
        errors.extend(process_record_errors(preflight, f"{label} preflight", document=candidate.path, repo_root=evidence.repo_root))
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(candidate.path.parent / "p7_preflight_result.txt"))
    append_error(errors, not preflight_duplicates and _historical_preflight_variant(candidate) == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED, f"{label} failure class mismatch")
    append_error(errors, data.get("target_identity") == dict(preflight_markers) and data.get("preflight_failures") == [], f"{label} preflight identity/failure boundary mismatch")
    errors.extend(shutdown_errors(candidate, "before", evidence=evidence))

    stage = data.get("stage_process")
    if not isinstance(stage, dict):
        errors.append(f"{label} candidate process record missing")
        stage = {}
    else:
        errors.extend(process_record_errors(stage, f"{label} candidate", document=candidate.path, repo_root=evidence.repo_root))
    append_error(errors, stage.get("name") == "jtag_axi_stage" and stage.get("returncode") == 0 and stage.get("passed") is True and stage.get("failures") == [], f"{label} candidate process is not an exact inner PASS")
    append_error(errors, data.get("stage_failures") == [] and data.get("internal_error") == "", f"{label} wrapper stage/internal failure fields mismatch")

    shutdown_after = data.get("shutdown_after")
    if not isinstance(shutdown_after, dict):
        errors.append(f"{label} shutdown-after record missing")
        shutdown_after = {}
    expected_failures = [
        "shutdown process returned nonzero exit code: 124",
        "TFDU_SHUTDOWN_PROGRAMMED marker missing from fresh result file",
        "P7_SHUTDOWN_RESULT=PASS marker missing from fresh result file",
        "P7_TCL_PROGRAMMING_ATTEMPTED=1 marker missing from fresh result file",
    ]
    append_error(
        errors,
        shutdown_after.get("name") == "shutdown_after"
        and shutdown_after.get("returncode") == 124
        and isinstance(shutdown_after.get("elapsed_seconds"), (int, float))
        and shutdown_after.get("elapsed_seconds") >= 30
        and shutdown_after.get("timed_out") is True
        and shutdown_after.get("passed") is False
        and shutdown_after.get("programming_attempted") is None
        and shutdown_after.get("failures") == expected_failures
        and shutdown_after.get("abort_seen") is False
        and shutdown_after.get("interrupted") is False
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("process_tree_terminated") is True
        and shutdown_after.get("containment_cleanup_attempted") is True
        and shutdown_after.get("containment_cleanup_terminated") is True
        and shutdown_after.get("containment_assigned") is True
        and shutdown_after.get("containment_closed") is True
        and shutdown_after.get("descendant_count_after") == 0
        and shutdown_after.get("expected_tool_daemon_classification") == "NONE"
        and shutdown_after.get("expected_tool_daemon_grace_used") is False,
        f"{label} shutdown-after timeout/containment facts mismatch",
    )
    shutdown_markers, shutdown_duplicates = parse_marker_text(marker_text(candidate.path.parent / "p7_shutdown_after_result.txt"))
    expected_identity = {
        "P7_HW_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
        "P7_HW_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_PART": CANONICAL_FULL_PART,
        "P7_HW_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
        "P7_HW_CANONICAL_PART": CANONICAL_FULL_PART,
        "P7_HW_LIVE_PART": CANONICAL_LIVE_PART,
        "P7_HW_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
        "P7_HW_LIVE_IDCODE": CANONICAL_LIVE_IDCODE_BINARY,
    }
    append_error(errors, not shutdown_duplicates and shutdown_markers == expected_identity, f"{label} shutdown-after partial identity record mismatch")
    append_error(errors, data.get("reason") == "stage is incomplete because shutdown-after lacked rc=0 plus marker" and data.get("backend_parse") is None and data.get("backend_parse_failure") == "", f"{label} fail-closed reason/backend boundary mismatch")

    raw, raw_duplicates = raw_markers(candidate)
    append_error(errors, not raw_duplicates and raw.get("P7_CANDIDATE_PROGRAMMED") == "1" and raw.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1" and raw.get("P7_JTAG_AXI_TRANSACTIONS") == "PASS" and raw.get("P7_TRANSACTION_COUNT") == "4269" and raw.get("P7_JTAG_STAGE_RESULT") == "PASS", f"{label} raw candidate PASS markers mismatch")
    errors.extend(authorized_event_errors(candidate, evidence))
    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    append_error(errors, [item.get("event") for item in events] == ["authorized_execution_begin", "preflight_finished", "shutdown_before_finished", "candidate_started", "candidate_child_reaped", "stage_finished", "shutdown_after_started", "shutdown_after_finished", "authorized_execution_end"], f"{label} event sequence mismatch")
    if len(events) == 9:
        append_error(errors, events[5].get("returncode") == 0 and events[5].get("passed") is True, f"{label} inner stage event is not PASS")
        append_error(errors, events[7].get("returncode") == 124 and events[7].get("passed") is False, f"{label} shutdown-after event mismatch")
        append_error(errors, events[8].get("status") == "FAIL_SHUTDOWN_AFTER", f"{label} end event status mismatch")
    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"{label} lock: {item}" for item in lock_errors)
    runtime = data.get("global_runtime")
    append_error(errors, isinstance(runtime, dict) and runtime.get("authorized_max_seconds") == 900 and runtime.get("within_authorized_limit") is True and isinstance(runtime.get("elapsed_seconds"), (int, float)) and 0 <= float(runtime.get("elapsed_seconds")) <= 900, f"{label} runtime record is invalid")
    return errors


def _old_commit_read_only_preflight_errors(candidate: Candidate, evidence: RepositoryEvidence) -> list[str]:
    """Prove that a superseded-commit record is diagnostic only.

    This intentionally recognizes one narrow historical shape: an authorized
    wrapper reached the read-only target preflight, that preflight failed, and
    no shutdown image, candidate bitstream/ELF, TFDU output, or receiver-enable
    action was even attempted.  Such a record remains immutable chronology but
    contributes no stage coverage and cannot inherit a later source checkpoint.
    """

    data = candidate.data
    errors: list[str] = []
    append_error(errors, candidate.executed, "old-commit diagnostic did not record hardware_actions_executed=true")
    append_error(errors, candidate.marker == "FAIL_PREFLIGHT", "old-commit diagnostic result is not exactly FAIL_PREFLIGHT")
    append_error(errors, data.get("hardware_acceptance") == "PENDING_HW", "old-commit diagnostic promoted or omitted hardware acceptance")
    append_error(errors, candidate.stage == "safe_idle", "old-commit diagnostic is not the safe-idle preflight stage")
    append_error(errors, not _candidate_mutation_attempted(candidate), "old-commit diagnostic contains a hardware mutation attempt")
    for key in (
        "programmed_fpga",
        "programmed_candidate",
        "programmed_shutdown_before",
        "programmed_shutdown_after",
        "started_ps_elf",
        "drove_tfdu_txd",
        "enabled_tfdu_receiver",
    ):
        append_error(errors, data.get(key) is False, f"old-commit diagnostic does not explicitly prove {key}=false")
    append_error(errors, not isinstance(data.get("shutdown_before"), dict), "old-commit diagnostic contains shutdown-before process evidence")
    append_error(errors, not isinstance(data.get("shutdown_after"), dict), "old-commit diagnostic contains shutdown-after process evidence")
    candidate_key = "ps_process" if candidate.kind == "ps" else "stage_process"
    append_error(errors, not isinstance(data.get(candidate_key), dict), "old-commit diagnostic contains a candidate child process")
    transaction = data.get("transaction_validation")
    append_error(
        errors,
        isinstance(transaction, dict)
        and transaction.get("valid") is True
        and transaction.get("metadata") == {"EVIDENCE_KIND": "safe_idle"},
        "old-commit diagnostic transaction validation is not the exact safe-idle boundary",
    )

    preflight_key = "preflight" if candidate.kind == "ps" else "preflight_process"
    preflight = data.get(preflight_key)
    historical_variant = _historical_preflight_variant(candidate)
    append_error(
        errors,
        historical_variant
        in {
            HISTORICAL_PREFLIGHT_PART_IDENTITY_REJECTED,
            HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED,
        },
        "old-commit diagnostic preflight failure shape is not recognized",
    )
    if not isinstance(preflight, dict):
        errors.append("old-commit diagnostic preflight process record missing")
    else:
        append_error(errors, preflight.get("returncode") == 125, "old-commit diagnostic preflight returncode is not exactly 125")
        append_error(errors, preflight.get("passed") is not True, "old-commit diagnostic preflight incorrectly reports PASS")
        for key in ("timed_out", "abort_seen", "interrupted"):
            append_error(errors, preflight.get(key) is False, f"old-commit diagnostic preflight reports {key}=true or missing")
        append_error(errors, preflight.get("process_tree_reaped") is False, "old-commit diagnostic preflight unexpectedly claims process_tree_reaped=true")
        if historical_variant == HISTORICAL_PREFLIGHT_PART_IDENTITY_REJECTED:
            append_error(errors, preflight.get("process_tree_terminated") is False, "old-commit part-identity diagnostic reports process_tree_terminated=true or missing")
        append_error(
            errors,
            preflight.get("containment_kind") in {"WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", "POSIX_PROCESS_GROUP"},
            "old-commit diagnostic preflight containment kind is missing/unsupported",
        )
        append_error(errors, preflight.get("containment_assigned") is True, "old-commit diagnostic preflight lacks containment assignment")
        append_error(errors, preflight.get("containment_closed") is True, "old-commit diagnostic preflight lacks containment closure")
        append_error(errors, preflight.get("descendant_count_after") == 0, "old-commit diagnostic preflight does not prove zero remaining descendants")
        append_error(errors, not preflight.get("launch_error"), "old-commit diagnostic preflight has a launch error")
        append_error(errors, isinstance(preflight.get("argv"), list) and bool(preflight.get("argv")), "old-commit diagnostic preflight exact argv missing")

    preflight_path = candidate.path.parent / ("p7_hw_preflight_result.txt" if candidate.kind == "ps" else "p7_preflight_result.txt")
    preflight_markers, preflight_duplicates = parse_marker_text(marker_text(preflight_path))
    append_error(errors, preflight_path.is_file(), "old-commit diagnostic preflight result file missing")
    append_error(errors, not preflight_duplicates, "old-commit diagnostic preflight result contains duplicate markers")
    append_error(errors, preflight_markers.get("P7_HW_PREFLIGHT_READ_ONLY") == "1", "old-commit diagnostic preflight is not read-only")
    if historical_variant == HISTORICAL_PREFLIGHT_PART_IDENTITY_REJECTED:
        append_error(errors, data.get("target_identity") == dict(preflight_markers), "old-commit part-identity raw/summary records differ")
    elif historical_variant == HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED and isinstance(preflight, dict):
        errors.extend(
            _historical_identity_pass_containment_errors(
                candidate,
                evidence,
                preflight,
                preflight_markers,
            )
        )
    if isinstance(preflight, dict):
        preflight_stdout = resolve_reference(preflight.get("stdout_path"), document=candidate.path, repo_root=evidence.repo_root)
        preflight_stderr = resolve_reference(preflight.get("stderr_path"), document=candidate.path, repo_root=evidence.repo_root)
        append_error(errors, preflight_stdout == (candidate.path.parent / "p7_preflight.stdout.log").resolve(strict=False), "old-commit diagnostic preflight stdout path mismatch")
        append_error(errors, preflight_stderr == (candidate.path.parent / "p7_preflight.stderr.log").resolve(strict=False), "old-commit diagnostic preflight stderr path mismatch")
        stdout_text = marker_text(preflight_stdout)
        append_error(errors, stdout_text.count("INFO: [Labtools 27-2285] Connecting to hw_server url TCP:localhost:3121") == 1, "old-commit diagnostic preflight localhost connection line missing/duplicated")
        append_error(errors, stdout_text.count("INFO: [Labtoolstcl 44-466] Opening hw_target localhost:3121/xilinx_tcf/Digilent/210512180081") == 1, "old-commit diagnostic preflight exact target-open line missing/duplicated")
        append_error(errors, preflight_stderr is not None and preflight_stderr.is_file() and preflight_stderr.stat().st_size == 0, "old-commit diagnostic preflight stderr missing/nonempty")

    observed, observed_duplicates = raw_markers(candidate)
    append_error(errors, not observed_duplicates, "old-commit diagnostic candidate log contains duplicate markers")
    append_error(errors, not observed, "old-commit diagnostic unexpectedly contains a candidate raw-result log")

    _event_path, events, event_errors = load_authorized_events(candidate)
    errors.extend(event_errors)
    names = [str(item.get("event", "")) for item in events]
    append_error(
        errors,
        names == ["authorized_execution_begin", "preflight_finished", "authorized_execution_end"],
        "old-commit diagnostic event sequence is not exactly begin/preflight-finished/end",
    )
    if len(events) == 3:
        append_error(errors, events[1].get("returncode") == (preflight.get("returncode") if isinstance(preflight, dict) else None), "old-commit diagnostic event returncode mismatch")
        append_error(errors, events[1].get("passed") is False, "old-commit diagnostic preflight-finished event is not FAIL")
        append_error(errors, events[2].get("status") == candidate.marker, "old-commit diagnostic end event does not bind wrapper result")
        times = [parse_time(item.get("timestamp_utc"), float("nan")) for item in events]
        append_error(errors, all(value == value for value in times) and times == sorted(times), "old-commit diagnostic event UTC chronology is invalid")

    lock_errors, _lock_record = hardware_execution_lock_errors(candidate, evidence)
    errors.extend(f"old-commit diagnostic lock: {item}" for item in lock_errors)

    safety = data.get("safety_validation")
    if not isinstance(safety, dict):
        errors.append("old-commit diagnostic safety_validation object missing")
        return errors
    source_requested = str(safety.get("source_commit_requested", "")).lower()
    source_current = str(safety.get("source_commit_current", "")).lower()
    append_error(errors, COMMIT_RE.fullmatch(source_requested) is not None, "old-commit diagnostic source commit missing/malformed")
    append_error(errors, source_requested == source_current, "old-commit diagnostic requested/current source commits differ")
    append_error(errors, safety.get("P7_HARDWARE_SAFETY") == "PASS", "old-commit diagnostic hardware safety gate is not PASS")
    append_error(errors, safety.get("ready_for_hardware_preflight") is True, "old-commit diagnostic was not authorized for preflight")
    append_error(errors, safety.get("errors") == [], "old-commit diagnostic hardware safety errors are nonempty")
    append_error(errors, safety.get("no_ethernet") is True and data.get("ethernet_used") is False, "old-commit diagnostic does not prove no Ethernet")
    append_error(errors, safety.get("no_motion") is True and data.get("motion_used") is False, "old-commit diagnostic does not prove no motion")
    append_error(errors, safety.get("lane_count") == 2 and str(safety.get("max_lane_mask", "")).casefold() == "0x3", "old-commit diagnostic lane scope is not exactly two lanes/mask 0x3")
    auth_fields = safety.get("authorization_fields")
    if not isinstance(auth_fields, dict):
        errors.append("old-commit diagnostic authorization fields missing")
    else:
        append_error(errors, str(auth_fields.get("SOURCE_COMMIT", "")).lower() == source_requested, "old-commit diagnostic authorization source mismatch")
        append_error(errors, str(auth_fields.get("SHUTDOWN_ON_EXIT", "")).casefold() == "required", "old-commit diagnostic authorization omits shutdown-on-exit")
        append_error(errors, str(auth_fields.get("NO_ETHERNET", "")).casefold() == "true", "old-commit diagnostic authorization permits Ethernet")
        append_error(errors, str(auth_fields.get("NO_MOTION", "")).casefold() == "true", "old-commit diagnostic authorization permits motion")
        append_error(errors, str(auth_fields.get("LANE_COUNT", "")) == "2", "old-commit diagnostic authorization lane count mismatch")
        append_error(errors, str(auth_fields.get("MAX_LANE_MASK", "")).casefold() == "0x3", "old-commit diagnostic authorization lane mask mismatch")
    authorization_record = safety.get("authorization")
    if not isinstance(authorization_record, dict):
        errors.append("old-commit diagnostic authorization hash record missing")
    else:
        expected_sha = str(authorization_record.get("expected_sha256", "")).lower()
        actual_sha = str(authorization_record.get("actual_sha256", "")).lower()
        append_error(errors, SHA256_RE.fullmatch(expected_sha) is not None, "old-commit diagnostic authorization expected SHA256 malformed")
        append_error(errors, expected_sha == actual_sha, "old-commit diagnostic authorization expected/actual SHA256 mismatch")
        append_error(errors, bool(str(authorization_record.get("path", ""))), "old-commit diagnostic authorization recorded path missing")
    return errors


def _verify_historical_hash_file(record: Any, *, label: str, document: Path, repo_root: Path) -> list[str]:
    errors, normalized = verify_hash_record(
        label,
        record,
        document=document,
        repo_root=repo_root,
        expected_required=False,
    )
    if normalized is not None:
        path = Path(normalized["path"])
        if path.is_file() and isinstance(record, dict) and "bytes" in record:
            append_error(errors, path.stat().st_size == record.get("bytes"), f"{label} byte count mismatch")
    return errors


def _historical_r2_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    append_error(errors, process.get("name") == "sequence_p7_safe_idle", "historical r2 outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, "historical r2 outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False, "historical r2 outer process required forced cleanup")
    append_error(errors, process.get("process_tree_reaped") is True, "historical r2 outer process did not reap the inner wrapper tree")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", "historical r2 outer process containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True, "historical r2 outer process containment assignment/closure mismatch")
    append_error(errors, process.get("descendant_count_after") == 0, "historical r2 outer process retained descendants")
    append_error(errors, process.get("containment_cleanup_terminated") is False, "historical r2 outer process claims containment cleanup")
    append_error(errors, process.get("expected_tool_daemon_grace_used") is False, "historical r2 outer process claims daemon grace")
    append_error(errors, process.get("expected_tool_daemon_grace_seconds") == 0.0, "historical r2 outer process daemon-grace duration is not zero")
    append_error(errors, process.get("expected_tool_daemon_paths") == [], "historical r2 outer process records expected daemon paths")
    append_error(errors, process.get("descendant_paths_seen") == [], "historical r2 outer process records descendant paths")
    append_error(errors, process.get("descendant_processes_seen") == [], "historical r2 outer process records descendant identities")
    append_error(errors, process.get("expected_tool_daemon_classification") == "NONE", "historical r2 outer process daemon classification is not NONE")
    append_error(errors, process.get("process_exit_race_rechecked") is False, "historical r2 outer process claims an exit-race recheck")
    append_error(errors, process.get("process_identity_query_retried") is False, "historical r2 outer process claims an identity retry")
    append_error(errors, process.get("containment_query_error") == "", "historical r2 outer process containment query error is nonempty")
    append_error(errors, process.get("launch_error") == "", "historical r2 outer process launch error is nonempty")
    append_error(
        errors,
        isinstance(process.get("elapsed_seconds"), (int, float))
        and 0 <= float(process.get("elapsed_seconds")) <= 300,
        "historical r2 outer elapsed time is invalid",
    )
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / "001_p7_safe_idle.stdout.log"
    stderr = wrapper_logs / "001_p7_safe_idle.stderr.log"
    append_error(
        errors,
        resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root)
        == stdout.resolve(strict=False),
        "historical r2 outer stdout path mismatch",
    )
    append_error(
        errors,
        resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root)
        == stderr.resolve(strict=False),
        "historical r2 outer stderr path mismatch",
    )
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, "historical r2 outer stderr is missing/nonempty")
    expected_failures = [
        "outer wrapper process containment/return-code policy failed",
        "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_PREFLIGHT",
        "wrapper summary does not prove programmed_shutdown_after=true",
        "wrapper shutdown-after record is missing",
        "wrapper candidate process record is missing: stage_process",
        "JTAG wrapper strict backend parse is missing or not bound to this run",
    ]
    append_error(errors, attempt.get("failures") == expected_failures, "historical r2 outer failure list mismatch")
    append_error(errors, attempt.get("shutdown_after") == {"present": False}, "historical r2 outer attempt shutdown-after boundary mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(
        errors,
        isinstance(orchestrator_elapsed, (int, float))
        and isinstance(process_elapsed, (int, float))
        and float(orchestrator_elapsed) >= float(process_elapsed) >= 0,
        "historical r2 orchestrator elapsed time does not cover the outer child",
    )
    launch_intent = parse_time(attempt.get("launch_intent_at_utc"), float("nan"))
    started = parse_time(attempt.get("started_at_utc"), float("nan"))
    append_error(
        errors,
        launch_intent == launch_intent and started == started and launch_intent <= started,
        "historical r2 launch-intent chronology is invalid",
    )
    return errors


def _historical_r3_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    append_error(errors, process.get("name") == "sequence_p7_safe_idle", "historical r3 outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, "historical r3 outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False, "historical r3 outer process required forced cleanup")
    append_error(errors, process.get("process_tree_reaped") is True, "historical r3 outer process did not naturally reap the wrapper tree")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", "historical r3 outer process containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True, "historical r3 outer process containment assignment/closure mismatch")
    append_error(errors, process.get("descendant_count_after") == 0, "historical r3 outer process retained descendants")
    errors.extend(_v2_process_containment_errors(process, "historical r3 outer process"))
    append_error(errors, process.get("launch_error") == "", "historical r3 outer process launch error is nonempty")
    append_error(
        errors,
        isinstance(process.get("elapsed_seconds"), (int, float))
        and 0 <= float(process.get("elapsed_seconds")) <= 600,
        "historical r3 outer elapsed time is invalid",
    )
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / "001_p7_safe_idle.stdout.log"
    stderr = wrapper_logs / "001_p7_safe_idle.stderr.log"
    append_error(
        errors,
        resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root)
        == stdout.resolve(strict=False),
        "historical r3 outer stdout path mismatch",
    )
    append_error(
        errors,
        resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root)
        == stderr.resolve(strict=False),
        "historical r3 outer stderr path mismatch",
    )
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, "historical r3 outer stderr is missing/nonempty")
    append_error(
        errors,
        attempt.get("failures")
        == [
            "outer wrapper process containment/return-code policy failed",
            "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_SHUTDOWN_AFTER",
            "wrapper summary does not prove programmed_shutdown_after=true",
            "wrapper shutdown-after did not return rc=0 and PASS",
            "shutdown-after fresh result lacks TFDU_SHUTDOWN_PROGRAMMED or SHUTDOWN_EXIT=0",
            "shutdown-after fresh result lacks P7_SHUTDOWN_RESULT=PASS",
            "wrapper candidate process record is missing: stage_process",
            "JTAG wrapper strict backend parse is missing or not bound to this run",
        ],
        "historical r3 outer failure list mismatch",
    )
    shutdown_after = attempt.get("shutdown_after")
    if not isinstance(shutdown_after, dict):
        errors.append("historical r3 outer shutdown-after record missing")
    else:
        append_error(
            errors,
            shutdown_after.get("present") is True
            and shutdown_after.get("returncode") == 41
            and shutdown_after.get("passed") is False
            and shutdown_after.get("process_tree_reaped") is True
            and shutdown_after.get("process_tree_terminated") is False
            and shutdown_after.get("containment_cleanup_attempted") is False
            and shutdown_after.get("containment_cleanup_terminated") is False
            and shutdown_after.get("shutdown_marker") is False
            and shutdown_after.get("p7_shutdown_result") is None,
            "historical r3 outer shutdown-after facts mismatch",
        )
        errors.extend(
            _verify_historical_hash_file(
                shutdown_after.get("result_file"),
                label="historical r3 outer shutdown-after result",
                document=outer_path,
                repo_root=evidence.repo_root,
            )
        )
        result_path = resolve_reference(
            shutdown_after.get("result_file", {}).get("path")
            if isinstance(shutdown_after.get("result_file"), dict)
            else None,
            document=outer_path,
            repo_root=evidence.repo_root,
        )
        append_error(
            errors,
            result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False),
            "historical r3 outer shutdown-after result path mismatch",
        )
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(
        errors,
        isinstance(orchestrator_elapsed, (int, float))
        and isinstance(process_elapsed, (int, float))
        and float(orchestrator_elapsed) >= float(process_elapsed) >= 0,
        "historical r3 orchestrator elapsed time does not cover the outer child",
    )
    launch_intent = parse_time(attempt.get("launch_intent_at_utc"), float("nan"))
    started = parse_time(attempt.get("started_at_utc"), float("nan"))
    append_error(
        errors,
        launch_intent == launch_intent and started == started and launch_intent <= started,
        "historical r3 launch-intent chronology is invalid",
    )
    return errors


def _historical_r4_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    label = "historical r4"
    append_error(errors, process.get("name") == "sequence_p7_safe_idle", f"{label} outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, f"{label} outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False, f"{label} outer process required forced cleanup")
    append_error(errors, process.get("process_tree_reaped") is True, f"{label} outer process did not naturally reap the wrapper tree")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", f"{label} outer process containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True, f"{label} outer containment assignment/closure mismatch")
    append_error(errors, process.get("descendant_count_after") == 0, f"{label} outer process retained descendants")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "", f"{label} outer launch error is nonempty")
    append_error(
        errors,
        isinstance(process.get("elapsed_seconds"), (int, float))
        and 0 <= float(process.get("elapsed_seconds")) <= 600,
        f"{label} outer elapsed time is invalid",
    )
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / "001_p7_safe_idle.stdout.log"
    stderr = wrapper_logs / "001_p7_safe_idle.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr is missing/nonempty")
    append_error(
        errors,
        attempt.get("failures")
        == [
            "outer wrapper process containment/return-code policy failed",
            "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_STAGE",
            "wrapper candidate process did not return rc=0 and PASS",
            "JTAG wrapper strict backend parse is missing or not bound to this run",
        ],
        f"{label} outer failure list mismatch",
    )
    shutdown_after = attempt.get("shutdown_after")
    if not isinstance(shutdown_after, dict):
        errors.append(f"{label} outer shutdown-after record missing")
    else:
        append_error(
            errors,
            shutdown_after.get("present") is True
            and shutdown_after.get("returncode") == 0
            and shutdown_after.get("passed") is True
            and shutdown_after.get("attempted") is True
            and shutdown_after.get("programming_attempted") is True
            and shutdown_after.get("process_tree_reaped") is True
            and shutdown_after.get("process_tree_terminated") is False
            and shutdown_after.get("containment_cleanup_attempted") is False
            and shutdown_after.get("containment_cleanup_terminated") is False
            and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
            and shutdown_after.get("p7_tcl_programming_attempted") == "1"
            and shutdown_after.get("p7_shutdown_result") == "PASS",
            f"{label} outer shutdown-after facts mismatch",
        )
        errors.extend(
            _verify_historical_hash_file(
                shutdown_after.get("result_file"),
                label=f"{label} outer shutdown-after result",
                document=outer_path,
                repo_root=evidence.repo_root,
            )
        )
        result_path = resolve_reference(
            shutdown_after.get("result_file", {}).get("path")
            if isinstance(shutdown_after.get("result_file"), dict)
            else None,
            document=outer_path,
            repo_root=evidence.repo_root,
        )
        append_error(errors, result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False), f"{label} outer shutdown-after result path mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(
        errors,
        isinstance(orchestrator_elapsed, (int, float))
        and isinstance(process_elapsed, (int, float))
        and float(orchestrator_elapsed) >= float(process_elapsed) >= 0,
        f"{label} orchestrator elapsed time does not cover the outer child",
    )
    launch_intent = parse_time(attempt.get("launch_intent_at_utc"), float("nan"))
    started = parse_time(attempt.get("started_at_utc"), float("nan"))
    append_error(errors, launch_intent == launch_intent and started == started and launch_intent <= started, f"{label} launch-intent chronology is invalid")
    return errors


def _historical_r5_safe_idle_prefix_errors(
    attempt: Mapping[str, Any],
    *,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
    source: str,
) -> list[str]:
    """Validate r5's one historical PASS prefix without granting new-source coverage."""

    errors: list[str] = []
    label = "historical r5 safe-idle prefix"
    append_error(errors, attempt.get("attempt") == 1 and attempt.get("stage_index") == 0, f"{label} attempt identity mismatch")
    append_error(errors, attempt.get("stage_id") == "p7_safe_idle" and attempt.get("group") == "safe_idle" and attempt.get("case") == {}, f"{label} stage boundary mismatch")
    append_error(errors, attempt.get("risk_index") == 10 and attempt.get("state") == "TERMINAL" and attempt.get("result") == "PASS" and attempt.get("failures") == [], f"{label} terminal PASS facts mismatch")
    append_error(errors, isinstance(attempt.get("command"), list) and bool(attempt.get("command")), f"{label} command missing")
    summary_record = attempt.get("summary_file")
    errors.extend(_verify_historical_hash_file(summary_record, label=f"{label} summary", document=outer_path, repo_root=evidence.repo_root))
    summary_path = resolve_reference(summary_record.get("path") if isinstance(summary_record, dict) else None, document=outer_path, repo_root=evidence.repo_root)
    expected_summary = epoch_root / "001_p7_safe_idle/p7_jtag_axi_stage_summary.json"
    append_error(errors, summary_path == expected_summary.resolve(strict=False), f"{label} summary path mismatch")
    try:
        data = json.loads(expected_summary.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return errors + [f"{label} summary invalid: {exc}"]
    prefix = Candidate(
        expected_summary,
        data,
        "jtag",
        classify_jtag_stage(data),
        parse_time(data.get("generated_at_utc"), expected_summary.stat().st_mtime),
    )
    append_error(errors, _candidate_source_commit(prefix) == source, f"{label} source mismatch")
    append_error(errors, prefix.marker == "PASS" and prefix.executed, f"{label} wrapper is not executed PASS")
    provenance_count = len(evidence.provenance_rows)
    try:
        safe_idle = validate_safe_idle(
            prefix,
            evidence,
            accepted_historical_source=source,
        )
    finally:
        del evidence.provenance_rows[provenance_count:]
    errors.extend(f"{label}: {item}" for item in safe_idle.errors)
    append_error(errors, safe_idle.status == "PASS", f"{label} semantic validator is not PASS")

    process = attempt.get("process")
    if not isinstance(process, dict):
        errors.append(f"{label} outer process missing")
        process = {}
    append_error(errors, process.get("name") == "sequence_p7_safe_idle" and process.get("returncode") == 0, f"{label} outer process result mismatch")
    append_error(errors, process.get("process_tree_reaped") is True and process.get("process_tree_terminated") is False, f"{label} outer process reap mismatch")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment mismatch")
    append_error(errors, process.get("argv") == attempt.get("command"), f"{label} outer argv mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    for key in ("stdout_file", "stderr_file"):
        errors.extend(_verify_historical_hash_file(process.get(key), label=f"{label} outer {key}", document=outer_path, repo_root=evidence.repo_root))
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 0
        and shutdown_after.get("passed") is True
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is True
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
        and shutdown_after.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after facts mismatch",
    )
    return errors


def _historical_r6_pass_prefix_errors(
    attempts: Sequence[Mapping[str, Any]],
    *,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
    source: str,
    expected_count: int = 27,
    epoch_label: str = "historical r6",
    full_stage_ordinals: Sequence[int] | None = None,
) -> list[str]:
    """Validate a contiguous PASS prefix while granting zero active coverage."""

    errors: list[str] = []
    if len(attempts) != expected_count:
        return [f"{epoch_label} PASS prefix must contain exactly {expected_count} attempts"]
    ordinals = list(full_stage_ordinals) if full_stage_ordinals is not None else list(range(1, expected_count + 1))
    if len(ordinals) != expected_count or any(
        not isinstance(value, int) or isinstance(value, bool) or value < 1 for value in ordinals
    ):
        return [f"{epoch_label} PASS prefix full-stage ordinal matrix is malformed"]
    errors.extend(
        _historical_r5_safe_idle_prefix_errors(
            attempts[0],
            epoch_root=epoch_root,
            outer_path=outer_path,
            evidence=evidence,
            source=source,
        )
    )
    for index, attempt in enumerate(attempts[1:], start=1):
        stage_id = str(attempt.get("stage_id", ""))
        label = f"{epoch_label} PASS prefix stage {index + 1} ({stage_id})"
        append_error(errors, attempt.get("attempt") == index + 1 and attempt.get("stage_index") == index, f"{label} attempt identity mismatch")
        if full_stage_ordinals is not None:
            append_error(errors, attempt.get("full_stage_ordinal") == ordinals[index], f"{label} full-stage ordinal mismatch")
        append_error(errors, attempt.get("state") == "TERMINAL" and attempt.get("result") == "PASS" and attempt.get("failures") == [], f"{label} terminal PASS facts mismatch")
        append_error(errors, isinstance(attempt.get("command"), list) and bool(attempt.get("command")), f"{label} command missing")
        summary_record = attempt.get("summary_file")
        errors.extend(_verify_historical_hash_file(summary_record, label=f"{label} summary", document=outer_path, repo_root=evidence.repo_root))
        summary_path = resolve_reference(summary_record.get("path") if isinstance(summary_record, dict) else None, document=outer_path, repo_root=evidence.repo_root)
        expected_summary = epoch_root / f"{ordinals[index]:03d}_{stage_id}" / "p7_jtag_axi_stage_summary.json"
        append_error(errors, summary_path == expected_summary.resolve(strict=False), f"{label} summary path mismatch")
        try:
            data = json.loads(expected_summary.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{label} summary invalid: {exc}")
            continue
        prefix = Candidate(
            expected_summary,
            data,
            "jtag",
            classify_jtag_stage(data),
            parse_time(data.get("generated_at_utc"), expected_summary.stat().st_mtime),
        )
        append_error(errors, _candidate_source_commit(prefix) == source, f"{label} source mismatch")
        append_error(errors, prefix.marker == "PASS" and prefix.executed, f"{label} wrapper is not executed PASS")
        common, _provenance = common_runner_errors(
            prefix,
            evidence,
            accepted_historical_source=source,
        )
        errors.extend(f"{label}: {item}" for item in common)
        wrapper_parse = data.get("backend_parse")
        parse_path = resolve_reference(
            wrapper_parse.get("summary_file") if isinstance(wrapper_parse, dict) else None,
            document=expected_summary,
            repo_root=evidence.repo_root,
        )
        parsed: dict[str, Any] = {}
        append_error(errors, isinstance(wrapper_parse, dict) and wrapper_parse.get("passed") is True, f"{label} wrapper backend binding is not PASS")
        append_error(errors, parse_path is not None and parse_path.is_file(), f"{label} strict backend parse summary is missing")
        if isinstance(wrapper_parse, dict) and parse_path is not None and parse_path.is_file():
            append_error(errors, sha256_file(parse_path) == str(wrapper_parse.get("summary_sha256", "")).lower(), f"{label} strict backend parse summary hash mismatch")
            try:
                value = json.loads(parse_path.read_text(encoding="utf-8", errors="strict"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"{label} strict backend parse summary invalid: {exc}")
            else:
                parsed = value if isinstance(value, dict) else {}
        raw_expected = (expected_summary.parent / "p7_jtag_axi_raw_result.txt").resolve(strict=False)
        append_error(errors, resolve_reference(parsed.get("raw_log"), document=parse_path or expected_summary, repo_root=evidence.repo_root) == raw_expected, f"{label} strict backend parse raw-log binding mismatch")
        append_error(
            errors,
            parsed.get(BACKEND_PARSE_MARKER) == "PASS"
            and parsed.get("failures") in (None, [])
            and parsed.get("failure") in (None, ""),
            f"{label} strict backend parse is not clean PASS",
        )
        process = attempt.get("process")
        if not isinstance(process, dict):
            errors.append(f"{label} outer process missing")
            process = {}
        append_error(errors, process.get("name") == f"sequence_{stage_id}" and process.get("returncode") == 0, f"{label} outer process result mismatch")
        append_error(errors, process.get("process_tree_reaped") is True and process.get("process_tree_terminated") is False, f"{label} outer process reap mismatch")
        append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment mismatch")
        append_error(errors, process.get("argv") == attempt.get("command"), f"{label} outer argv mismatch")
        errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
        for key in ("stdout_file", "stderr_file"):
            errors.extend(_verify_historical_hash_file(process.get(key), label=f"{label} outer {key}", document=outer_path, repo_root=evidence.repo_root))
        shutdown_after = attempt.get("shutdown_after")
        append_error(
            errors,
            isinstance(shutdown_after, dict)
            and shutdown_after.get("present") is True
            and shutdown_after.get("returncode") == 0
            and shutdown_after.get("passed") is True
            and shutdown_after.get("attempted") is True
            and shutdown_after.get("programming_attempted") is True
            and shutdown_after.get("process_tree_reaped") is True
            and shutdown_after.get("process_tree_terminated") is False
            and shutdown_after.get("containment_cleanup_attempted") is False
            and shutdown_after.get("containment_cleanup_terminated") is False
            and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
            and shutdown_after.get("p7_tcl_programming_attempted") == "1"
            and shutdown_after.get("p7_shutdown_result") == "PASS",
            f"{label} outer shutdown-after facts mismatch",
        )
        if isinstance(shutdown_after, dict):
            errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
    return errors


def _historical_r10_pass_prefix_errors(
    attempts: Sequence[Mapping[str, Any]],
    *,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
    source: str,
) -> list[str]:
    errors = _historical_r6_pass_prefix_errors(
        attempts,
        epoch_root=epoch_root,
        outer_path=outer_path,
        evidence=evidence,
        source=source,
        expected_count=7,
        epoch_label="historical r10",
        full_stage_ordinals=(1, 2, 3, 4, 55, 56, 57),
    )
    if attempts:
        append_error(errors, attempts[0].get("full_stage_ordinal") == 1, "historical r10 safe-idle full-stage ordinal mismatch")
    return errors


def _historical_r5_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    label = "historical r5"
    append_error(errors, process.get("name") == "sequence_p7_p6_frame_regression_m1", f"{label} outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, f"{label} outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False and process.get("process_tree_reaped") is True, f"{label} outer process reap/termination mismatch")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", f"{label} outer containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment assignment/closure mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "", f"{label} outer launch error is nonempty")
    append_error(errors, isinstance(process.get("elapsed_seconds"), (int, float)) and 0 <= float(process.get("elapsed_seconds")) <= 900, f"{label} outer elapsed time is invalid")
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / "002_p7_p6_frame_regression_m1.stdout.log"
    stderr = wrapper_logs / "002_p7_p6_frame_regression_m1.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr missing/nonempty")
    append_error(
        errors,
        attempt.get("failures")
        == [
            "outer wrapper process containment/return-code policy failed",
            "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_STAGE",
            "JTAG wrapper strict backend parse is missing or not bound to this run",
        ],
        f"{label} outer failure list mismatch",
    )
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 0
        and shutdown_after.get("passed") is True
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is True
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("process_tree_terminated") is False
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
        and shutdown_after.get("p7_tcl_programming_attempted") == "1"
        and shutdown_after.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after facts mismatch",
    )
    if isinstance(shutdown_after, dict):
        errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(errors, isinstance(orchestrator_elapsed, (int, float)) and isinstance(process_elapsed, (int, float)) and float(orchestrator_elapsed) >= float(process_elapsed) >= 0, f"{label} orchestrator elapsed time mismatch")
    return errors


def _historical_r6_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    label = "historical r6"
    stage_id = "p7_fragment_boundary_216_rep3"
    append_error(errors, process.get("name") == f"sequence_{stage_id}", f"{label} outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, f"{label} outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False and process.get("process_tree_reaped") is True, f"{label} outer process reap/termination mismatch")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", f"{label} outer containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment assignment/closure mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "", f"{label} outer launch error is nonempty")
    append_error(errors, isinstance(process.get("elapsed_seconds"), (int, float)) and 0 <= float(process.get("elapsed_seconds")) <= 900, f"{label} outer elapsed time is invalid")
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / f"028_{stage_id}.stdout.log"
    stderr = wrapper_logs / f"028_{stage_id}.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr missing/nonempty")
    append_error(
        errors,
        attempt.get("failures")
        == [
            "outer wrapper process containment/return-code policy failed",
            "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_SHUTDOWN_AFTER",
            "wrapper summary does not prove programmed_shutdown_after=true",
            "wrapper shutdown-after did not return rc=0 and PASS",
            "wrapper shutdown-after process tree was not reaped",
            "wrapper shutdown-after used or omits forced-cleanup evidence",
            "wrapper shutdown-after reports forced containment termination",
            "wrapper shutdown-after reports process-tree termination",
            "JTAG wrapper strict backend parse is missing or not bound to this run",
        ],
        f"{label} outer failure list mismatch",
    )
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 125
        and shutdown_after.get("passed") is False
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is True
        and shutdown_after.get("process_tree_reaped") is False
        and shutdown_after.get("process_tree_terminated") is True
        and shutdown_after.get("containment_cleanup_attempted") is True
        and shutdown_after.get("containment_cleanup_terminated") is True
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
        and shutdown_after.get("p7_tcl_programming_attempted") == "1"
        and shutdown_after.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after facts mismatch",
    )
    if isinstance(shutdown_after, dict):
        errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
        result_path = resolve_reference(shutdown_after.get("result_file", {}).get("path") if isinstance(shutdown_after.get("result_file"), dict) else None, document=outer_path, repo_root=evidence.repo_root)
        append_error(errors, result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False), f"{label} outer shutdown-after result path mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(errors, isinstance(orchestrator_elapsed, (int, float)) and isinstance(process_elapsed, (int, float)) and float(orchestrator_elapsed) >= float(process_elapsed) >= 0, f"{label} orchestrator elapsed time mismatch")
    return errors


def _historical_r11_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
    epoch_label: str = "historical r11",
) -> list[str]:
    errors: list[str] = []
    label = epoch_label
    stage_id = "p7_p6_frame_regression_m1"
    append_error(errors, process.get("name") == f"sequence_{stage_id}", f"{label} outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, f"{label} outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False and process.get("process_tree_reaped") is True, f"{label} outer process reap/termination mismatch")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", f"{label} outer containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment assignment/closure mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "", f"{label} outer launch error is nonempty")
    append_error(errors, isinstance(process.get("elapsed_seconds"), (int, float)) and 0 <= float(process.get("elapsed_seconds")) <= 1080, f"{label} outer elapsed time is invalid")
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / f"002_{stage_id}.stdout.log"
    stderr = wrapper_logs / f"002_{stage_id}.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr missing/nonempty")
    append_error(
        errors,
        attempt.get("failures")
        == (
            [
                "outer wrapper process containment/return-code policy failed",
                "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_STAGE",
                "JTAG wrapper strict backend parse is missing or not bound to this run",
            ]
            if epoch_label in {"historical r14", "historical r15"}
            else [
                "outer wrapper process containment/return-code policy failed",
                "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_STAGE",
                "wrapper candidate process did not return rc=0 and PASS",
                "JTAG wrapper strict backend parse is missing or not bound to this run",
            ]
        ),
        f"{label} outer failure list mismatch",
    )
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 0
        and shutdown_after.get("passed") is True
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is True
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("process_tree_terminated") is False
        and shutdown_after.get("containment_cleanup_attempted") is False
        and shutdown_after.get("containment_cleanup_terminated") is False
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
        and shutdown_after.get("p7_tcl_programming_attempted") == "1"
        and shutdown_after.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after facts mismatch",
    )
    if isinstance(shutdown_after, dict):
        errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
        result_path = resolve_reference(shutdown_after.get("result_file", {}).get("path") if isinstance(shutdown_after.get("result_file"), dict) else None, document=outer_path, repo_root=evidence.repo_root)
        append_error(errors, result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False), f"{label} outer shutdown-after result path mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(errors, isinstance(orchestrator_elapsed, (int, float)) and isinstance(process_elapsed, (int, float)) and float(orchestrator_elapsed) >= float(process_elapsed) >= 0, f"{label} orchestrator elapsed time mismatch")
    return errors


def _historical_r7_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    label = "historical r7"
    stage_id = "p7_p6_frame_regression_m2"
    append_error(errors, process.get("name") == f"sequence_{stage_id}", f"{label} outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, f"{label} outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False and process.get("process_tree_reaped") is True, f"{label} outer process reap/termination mismatch")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", f"{label} outer containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment assignment/closure mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "", f"{label} outer launch error is nonempty")
    append_error(errors, isinstance(process.get("elapsed_seconds"), (int, float)) and 0 <= float(process.get("elapsed_seconds")) <= 900, f"{label} outer elapsed time is invalid")
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / f"003_{stage_id}.stdout.log"
    stderr = wrapper_logs / f"003_{stage_id}.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr missing/nonempty")
    append_error(
        errors,
        attempt.get("failures")
        == [
            "outer wrapper process containment/return-code policy failed",
            "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_SHUTDOWN_AFTER",
            "wrapper summary does not prove programmed_shutdown_after=true",
            "wrapper shutdown-after did not return rc=0 and PASS",
            "wrapper shutdown-after does not prove programming_attempted=true",
            "wrapper shutdown-after used or omits forced-cleanup evidence",
            "wrapper shutdown-after reports forced containment termination",
            "wrapper shutdown-after reports process-tree termination",
            "shutdown-after fresh result lacks exact TFDU_SHUTDOWN_PROGRAMMED marker",
            "shutdown-after fresh result lacks P7_TCL_PROGRAMMING_ATTEMPTED=1",
            "shutdown-after fresh result lacks P7_SHUTDOWN_RESULT=PASS",
            "JTAG wrapper strict backend parse is missing or not bound to this run",
        ],
        f"{label} outer failure list mismatch",
    )
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 124
        and shutdown_after.get("passed") is False
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is None
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("process_tree_terminated") is True
        and shutdown_after.get("containment_cleanup_attempted") is True
        and shutdown_after.get("containment_cleanup_terminated") is True
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is False
        and shutdown_after.get("p7_tcl_programming_attempted") is None
        and shutdown_after.get("p7_shutdown_result") is None,
        f"{label} outer shutdown-after facts mismatch",
    )
    if isinstance(shutdown_after, dict):
        errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
        result_path = resolve_reference(shutdown_after.get("result_file", {}).get("path") if isinstance(shutdown_after.get("result_file"), dict) else None, document=outer_path, repo_root=evidence.repo_root)
        append_error(errors, result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False), f"{label} outer shutdown-after result path mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(errors, isinstance(orchestrator_elapsed, (int, float)) and isinstance(process_elapsed, (int, float)) and float(orchestrator_elapsed) >= float(process_elapsed) >= 0, f"{label} orchestrator elapsed time mismatch")
    return errors


def _historical_r8_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    label = "historical r8"
    stage_id = "p7_large_jtag_64k_rr_prbs15"
    append_error(errors, process.get("name") == f"sequence_{stage_id}", f"{label} outer process name mismatch")
    append_error(errors, process.get("returncode") == 1, f"{label} outer process returncode is not exactly 1")
    append_error(errors, process.get("process_tree_terminated") is False and process.get("process_tree_reaped") is True, f"{label} outer process reap/termination mismatch")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", f"{label} outer containment is not a Windows Job")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "", f"{label} outer launch error is nonempty")
    append_error(errors, isinstance(process.get("elapsed_seconds"), (int, float)) and 0 <= float(process.get("elapsed_seconds")) <= 960, f"{label} outer elapsed time is invalid")
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / f"055_{stage_id}.stdout.log"
    stderr = wrapper_logs / f"055_{stage_id}.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr missing/nonempty")
    append_error(errors, attempt.get("failures") == ["outer wrapper process containment/return-code policy failed", "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_STAGE", "JTAG wrapper strict backend parse is missing or not bound to this run"], f"{label} outer failure list mismatch")
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 0
        and shutdown_after.get("passed") is True
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is True
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("process_tree_terminated") is False
        and shutdown_after.get("containment_cleanup_attempted") is False
        and shutdown_after.get("containment_cleanup_terminated") is False
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
        and shutdown_after.get("p7_tcl_programming_attempted") == "1"
        and shutdown_after.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after facts mismatch",
    )
    if isinstance(shutdown_after, dict):
        errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
        result_path = resolve_reference(shutdown_after.get("result_file", {}).get("path") if isinstance(shutdown_after.get("result_file"), dict) else None, document=outer_path, repo_root=evidence.repo_root)
        append_error(errors, result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False), f"{label} outer shutdown-after result path mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(errors, isinstance(orchestrator_elapsed, (int, float)) and isinstance(process_elapsed, (int, float)) and float(orchestrator_elapsed) >= float(process_elapsed) >= 0, f"{label} orchestrator elapsed mismatch")
    return errors


def _historical_r9_outer_containment_errors(
    attempt: Mapping[str, Any],
    process: Mapping[str, Any],
    *,
    candidate: Candidate,
    epoch_root: Path,
    outer_path: Path,
    evidence: RepositoryEvidence,
) -> list[str]:
    errors: list[str] = []
    label = "historical r9"
    stage_id = "p7_p6_frame_regression_m2"
    append_error(errors, process.get("name") == f"sequence_{stage_id}" and process.get("returncode") == 1, f"{label} outer process identity/returncode mismatch")
    append_error(errors, process.get("process_tree_terminated") is False and process.get("process_tree_reaped") is True, f"{label} outer process reap/termination mismatch")
    append_error(errors, process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE" and process.get("containment_assigned") is True and process.get("containment_closed") is True and process.get("descendant_count_after") == 0, f"{label} outer containment mismatch")
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    append_error(errors, process.get("launch_error") == "" and process.get("abort_seen") is False and process.get("timed_out") is False, f"{label} outer process incorrectly owns the child abort")
    append_error(errors, isinstance(process.get("elapsed_seconds"), (int, float)) and 0 <= float(process.get("elapsed_seconds")) <= 960, f"{label} outer elapsed time is invalid")
    wrapper_logs = epoch_root / ".sequence_execution_ledger_wrapper_logs"
    stdout = wrapper_logs / f"003_{stage_id}.stdout.log"
    stderr = wrapper_logs / f"003_{stage_id}.stderr.log"
    append_error(errors, resolve_reference(process.get("stdout_path"), document=outer_path, repo_root=evidence.repo_root) == stdout.resolve(strict=False), f"{label} outer stdout path mismatch")
    append_error(errors, resolve_reference(process.get("stderr_path"), document=outer_path, repo_root=evidence.repo_root) == stderr.resolve(strict=False), f"{label} outer stderr path mismatch")
    append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, f"{label} outer stderr missing/nonempty")
    expected_failures = [
        "outer wrapper process containment/return-code policy failed",
        "wrapper result is not PASS: P7_JTAG_AXI_SAFE_STAGE=FAIL_STAGE",
        "wrapper candidate process did not return rc=0 and PASS",
        "wrapper candidate used or omits forced-cleanup evidence",
        "wrapper candidate reports forced containment termination",
        "wrapper candidate reports process-tree termination",
        "JTAG wrapper strict backend parse is missing or not bound to this run",
    ]
    append_error(errors, attempt.get("failures") == expected_failures, f"{label} outer failure list mismatch")
    shutdown_after = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(shutdown_after, dict)
        and shutdown_after.get("present") is True
        and shutdown_after.get("returncode") == 0
        and shutdown_after.get("passed") is True
        and shutdown_after.get("attempted") is True
        and shutdown_after.get("programming_attempted") is True
        and shutdown_after.get("process_tree_reaped") is True
        and shutdown_after.get("process_tree_terminated") is False
        and shutdown_after.get("containment_cleanup_attempted") is False
        and shutdown_after.get("containment_cleanup_terminated") is False
        and shutdown_after.get("tfdu_shutdown_programmed_exact") is True
        and shutdown_after.get("p7_tcl_programming_attempted") == "1"
        and shutdown_after.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after facts mismatch",
    )
    if isinstance(shutdown_after, dict):
        errors.extend(_verify_historical_hash_file(shutdown_after.get("result_file"), label=f"{label} outer shutdown-after result", document=outer_path, repo_root=evidence.repo_root))
        result_path = resolve_reference(shutdown_after.get("result_file", {}).get("path") if isinstance(shutdown_after.get("result_file"), dict) else None, document=outer_path, repo_root=evidence.repo_root)
        append_error(errors, result_path == (candidate.path.parent / "p7_shutdown_after_result.txt").resolve(strict=False), f"{label} outer shutdown-after result path mismatch")
    orchestrator_elapsed = attempt.get("orchestrator_elapsed_seconds")
    process_elapsed = process.get("elapsed_seconds")
    append_error(errors, isinstance(orchestrator_elapsed, (int, float)) and isinstance(process_elapsed, (int, float)) and float(orchestrator_elapsed) >= float(process_elapsed) >= 0, f"{label} orchestrator elapsed mismatch")

    deadline_record_path = epoch_root / "outer_deadline_abort_record.json"
    refusal_record_path = epoch_root / "recovery_launcher_refusal_record.json"
    try:
        deadline_record = json.loads(deadline_record_path.read_text(encoding="utf-8", errors="strict"))
        refusal_record = json.loads(refusal_record_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} abort/refusal record invalid: {exc}")
    else:
        append_error(
            errors,
            deadline_record
            == {
                "schema": "rf-comm-p7-outer-deadline-abort-record-v1",
                "run_id": epoch_root.name,
                "result": "ABORT_REQUESTED",
                "outer_interactive_command_timeout_seconds": 7200,
                "historical_r8_first_55_stage_elapsed_minutes": 182.68,
                "reason": "configured outer interactive command deadline cannot contain the complete 66-stage sequence; abort requested before external termination so the active safe wrapper can execute shutdown-on-exit",
                "abort_file": ".hardware_authorization/ABORT_NOW.txt",
                "abort_file_content": {"P7_ABORT_REQUESTED": "1", "REASON": "outer_interactive_process_deadline_insufficient_for_full_sequence"},
                "failed_stage_index_zero_based": 2,
                "failed_stage": stage_id,
                "failed_stage_candidate_returncode": 130,
                "failed_stage_shutdown_after_result": "PASS",
                "coverage_claimed": False,
                "stationary_started": False,
            },
            f"{label} outer-deadline abort record mismatch",
        )
        append_error(
            errors,
            refusal_record.get("schema") == "rf-comm-p7-recovery-launcher-refusal-v1"
            and refusal_record.get("run_id") == epoch_root.name
            and refusal_record.get("attempt") == 1
            and refusal_record.get("result") == "NO_HARDWARE_ACTIONS"
            and refusal_record.get("returncode") == 1
            and refusal_record.get("script_loaded") is False
            and refusal_record.get("authorization_checked") is False
            and refusal_record.get("vivado_started") is False
            and refusal_record.get("hardware_actions_executed") is False
            and refusal_record.get("shutdown_claimed") is False,
            f"{label} launcher-refusal no-action record mismatch",
        )
    return errors


def _historical_ps_shutdown_arg_count_epoch_record(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    *,
    outer: Mapping[str, Any],
    outer_path: Path,
    epoch_root: Path,
    source: str,
) -> tuple[dict[str, Any], list[str]]:
    """Bind r16's 11-stage PASS prefix and pre-candidate PS shutdown failure."""

    errors: list[str] = []
    label = "historical r16"
    expected_ordinals = [1, 2, 3, 4, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]
    append_error(errors, outer.get("schema") == "rf-comm-p7-sequence-execution-ledger-v1", f"{label} outer schema mismatch")
    append_error(errors, outer.get("status") == "FAIL" and outer.get("hardware_actions_executed") is True, f"{label} outer result boundary mismatch")
    append_error(errors, outer.get("network_used") is False and outer.get("motion_used") is False, f"{label} outer no-network/no-motion boundary mismatch")
    append_error(errors, str(outer.get("source_commit", "")).lower() == source, f"{label} outer source mismatch")
    append_error(
        errors,
        outer.get("plan_mode") == "DIAGNOSTIC_SUFFIX_55"
        and outer.get("coverage_claimed") is False
        and outer.get("HARDWARE_ACCEPTANCE") == "PENDING_HW"
        and outer.get("full_stage_ordinals") == expected_ordinals,
        f"{label} diagnostic zero-coverage boundary mismatch",
    )
    append_error(
        errors,
        outer.get("attempt_count") == 12
        and outer.get("completed_stage_count") == 11
        and outer.get("failed_stage_index") == 11
        and outer.get("next_stage_index") == 11,
        f"{label} failed-stage boundary mismatch",
    )
    attempts = outer.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != 12 or not all(isinstance(item, dict) for item in attempts):
        errors.append(f"{label} outer attempts are malformed")
        attempts = []
    if attempts:
        errors.extend(
            _historical_r6_pass_prefix_errors(
                attempts[:11],
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
                source=source,
                expected_count=11,
                epoch_label=label,
                full_stage_ordinals=expected_ordinals[:11],
            )
        )
        attempt = attempts[11]
    else:
        attempt = {}
    append_error(
        errors,
        attempt.get("attempt") == 12
        and attempt.get("stage_index") == 11
        and attempt.get("full_stage_ordinal") == 62
        and attempt.get("stage_id") == "p7_ps_functional"
        and attempt.get("group") == "ps_functional"
        and attempt.get("risk_index") == 40
        and attempt.get("case") == {}
        and attempt.get("state") == "TERMINAL"
        and attempt.get("result") == "FAIL",
        f"{label} failed attempt identity mismatch",
    )
    expected_failures = [
        "outer wrapper process containment/return-code policy failed",
        "wrapper result is not PASS: P7_PS_APPLICATION_SAFE_STAGE=FAIL_SHUTDOWN_AFTER",
        "wrapper summary does not prove programmed_shutdown_before=true",
        "wrapper summary does not prove programmed_shutdown_after=true",
        "wrapper shutdown-before did not return rc=0 and PASS",
        "wrapper shutdown-before does not prove programming_attempted=true",
        "shutdown-before fresh result file is missing",
        "shutdown-before fresh result lacks exact TFDU_SHUTDOWN_PROGRAMMED marker",
        "shutdown-before fresh result lacks P7_TCL_PROGRAMMING_ATTEMPTED=1",
        "shutdown-before fresh result lacks P7_SHUTDOWN_RESULT=PASS",
        "wrapper shutdown-after did not return rc=0 and PASS",
        "wrapper shutdown-after does not prove programming_attempted=true",
        "shutdown-after fresh result file is missing",
        "shutdown-after fresh result lacks exact TFDU_SHUTDOWN_PROGRAMMED marker",
        "shutdown-after fresh result lacks P7_TCL_PROGRAMMING_ATTEMPTED=1",
        "shutdown-after fresh result lacks P7_SHUTDOWN_RESULT=PASS",
        "wrapper candidate process record is missing: ps_process",
        "PS wrapper postprocess is missing or not PASS",
    ]
    append_error(errors, attempt.get("failures") == expected_failures, f"{label} outer failure list mismatch")
    summary_record = attempt.get("summary_file")
    errors.extend(_verify_historical_hash_file(summary_record, label=f"{label} failed summary", document=outer_path, repo_root=evidence.repo_root))
    append_error(
        errors,
        resolve_reference(summary_record.get("path") if isinstance(summary_record, dict) else None, document=outer_path, repo_root=evidence.repo_root)
        == candidate.path.resolve(strict=False),
        f"{label} outer summary binding mismatch",
    )
    process = attempt.get("process")
    if not isinstance(process, dict):
        errors.append(f"{label} outer process missing")
        process = {}
    append_error(
        errors,
        process.get("name") == "sequence_p7_ps_functional"
        and process.get("returncode") == 1
        and process.get("process_tree_reaped") is True
        and process.get("process_tree_terminated") is False
        and process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE"
        and process.get("containment_assigned") is True
        and process.get("containment_closed") is True
        and process.get("descendant_count_after") == 0
        and process.get("argv") == attempt.get("command"),
        f"{label} outer process/containment mismatch",
    )
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    for key in ("stdout_file", "stderr_file"):
        errors.extend(_verify_historical_hash_file(process.get(key), label=f"{label} outer {key}", document=outer_path, repo_root=evidence.repo_root))
    outer_shutdown = attempt.get("shutdown_after")
    outer_shutdown_result = (
        outer_shutdown.get("result_file")
        if isinstance(outer_shutdown, dict)
        and isinstance(outer_shutdown.get("result_file"), dict)
        else {}
    )
    append_error(
        errors,
        isinstance(outer_shutdown, dict)
        and outer_shutdown.get("present") is True
        and outer_shutdown.get("returncode") == 41
        and outer_shutdown.get("passed") is False
        and outer_shutdown.get("attempted") is True
        and outer_shutdown.get("programming_attempted") is None
        and outer_shutdown.get("process_tree_reaped") is True
        and outer_shutdown.get("process_tree_terminated") is False
        and outer_shutdown_result.get("missing") is True
        and _same_registered_worktree_location(
            resolve_reference(
                outer_shutdown_result.get("path"),
                document=outer_path,
                repo_root=evidence.repo_root,
            ),
            candidate.path.parent / "shutdown_after_result.txt",
            evidence.repo_root,
        ),
        f"{label} outer shutdown-after facts mismatch",
    )

    expected_stage_files = {
        "p7_hw_preflight_result.txt",
        "p7_ps_application_events.json",
        "p7_ps_application_stage_summary.json",
        "p7_raw_evidence_sha256_manifest.json",
        "preflight.stderr.log",
        "preflight.stdout.log",
        "shutdown_after.stderr.log",
        "shutdown_after.stdout.log",
        "shutdown_before.stderr.log",
        "shutdown_before.stdout.log",
    }
    append_error(
        errors,
        {path.name for path in candidate.path.parent.iterdir() if path.is_file()} == expected_stage_files
        and (candidate.path.parent / "bundle").is_dir(),
        f"{label} failed-stage file set mismatch",
    )
    diagnostic_files = {
        name: _hash_record(candidate.path.parent / name) for name in sorted(expected_stage_files)
    }

    frozen_dir = epoch_root / "historical_preflight_inputs"
    frozen_manifest_path = frozen_dir / "manifest.json"
    try:
        frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} frozen manifest invalid: {exc}")
        frozen_manifest = {}
    expected_roles = {
        "offline_checkpoint",
        "sequence_plan",
        "stage_authorization",
        "generation_manifest",
        "recovery_p4_authorization",
        "stage_execution_plan",
        "stage_bundle_manifest",
        "historical_stage_tcl",
        "historical_stage_wrapper_python",
        "historical_process_support_python",
        "historical_ps_execute_tcl",
        "historical_ps_mailbox_backend",
    }
    append_error(
        errors,
        isinstance(frozen_manifest, dict)
        and frozen_manifest.get("schema") == "rf-comm-p7-historical-failed-stage-inputs-v1"
        and frozen_manifest.get("run_id") == epoch_root.name
        and str(frozen_manifest.get("source_commit", "")).lower() == source
        and frozen_manifest.get("stage_index") == 11
        and frozen_manifest.get("full_stage_ordinal") == 62
        and frozen_manifest.get("stage_id") == "p7_ps_functional"
        and frozen_manifest.get("result") == "FAIL_SHUTDOWN_AFTER"
        and frozen_manifest.get("mutation_attempted") is False
        and frozen_manifest.get("candidate_mutation_attempted") is False
        and frozen_manifest.get("coverage_claimed") is False,
        f"{label} frozen manifest boundary mismatch",
    )
    frozen_records: dict[str, dict[str, Any]] = {}
    frozen_files = frozen_manifest.get("files") if isinstance(frozen_manifest, dict) else None
    if not isinstance(frozen_files, list) or len(frozen_files) != len(expected_roles):
        errors.append(f"{label} frozen manifest role count mismatch")
    else:
        for item in frozen_files:
            if not isinstance(item, dict):
                errors.append(f"{label} frozen manifest contains a malformed file record")
                continue
            role = str(item.get("role", ""))
            path = resolve_reference(item.get("frozen_path"), document=frozen_manifest_path, repo_root=evidence.repo_root)
            digest = str(item.get("sha256", "")).lower()
            append_error(errors, role in expected_roles and role not in frozen_records, f"{label} frozen role invalid/duplicate: {role}")
            append_error(errors, path is not None and path.is_file() and not path.is_symlink(), f"{label} frozen file missing/symbolic: {role}")
            if path is not None and path.is_file():
                append_error(errors, path.stat().st_size == item.get("bytes"), f"{label} frozen file size mismatch: {role}")
                append_error(errors, SHA256_RE.fullmatch(digest) is not None and sha256_file(path) == digest, f"{label} frozen file SHA mismatch: {role}")
                frozen_records[role] = {**item, "resolved_path": str(path)}
    append_error(errors, set(frozen_records) == expected_roles, f"{label} frozen roles incomplete")
    historical_source_control_flow: dict[str, Any] = {}
    if set(frozen_records) == expected_roles:
        source_paths = {
            "historical_stage_tcl": "scripts/hw/p7_jtag_axi_transactions.tcl",
            "historical_stage_wrapper_python": "scripts/hw/run_p7_ps_application_stage_safe.py",
            "historical_process_support_python": "scripts/hw/run_p7_jtag_axi_stage_safe.py",
            "historical_ps_execute_tcl": "scripts/hw/p7_ps_application_execute.tcl",
            "historical_ps_mailbox_backend": "tools/p7_ps_mailbox_backend.py",
        }
        texts: dict[str, str] = {}
        for role, relative in source_paths.items():
            frozen_path = Path(frozen_records[role]["resolved_path"])
            frozen_bytes = frozen_path.read_bytes()
            computed_blob = hashlib.sha1(f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes).hexdigest()
            append_error(errors, computed_blob == str(frozen_records[role].get("git_blob_sha1", "")).lower(), f"{label} frozen Git blob mismatch: {role}")
            try:
                committed = subprocess.run(["git", "show", f"{source}:{relative}"], cwd=evidence.repo_root, capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(f"{label} unable to read source {relative}: {exc}")
            else:
                append_error(errors, committed.returncode == 0 and committed.stdout == frozen_bytes, f"{label} frozen source differs from commit: {role}")
            try:
                texts[role] = frozen_bytes.decode("utf-8", errors="strict")
            except UnicodeError as exc:
                errors.append(f"{label} frozen source is not UTF-8 ({role}): {exc}")
                texts[role] = ""
        old_tcl = texts.get("historical_stage_tcl", "")
        old_wrapper = texts.get("historical_stage_wrapper_python", "")
        function_start = old_wrapper.find("def build_shutdown_command(")
        function_end = old_wrapper.find("\ndef build_ps_command(", function_start)
        old_function = old_wrapper[function_start:function_end] if 0 <= function_start < function_end else ""
        arg_mismatch = (
            "if {[llength $argv] != 17}" in old_tcl
            and old_function.count('        "1",') == 1
            and "process_support.MAX_TRANSACTION_BYTES" not in old_function
        )
        append_error(errors, arg_mismatch, f"{label} frozen source does not prove the 17-vs-16 shutdown argv mismatch")
        historical_source_control_flow = {
            "jtag_tcl_requires_argument_count": 17,
            "ps_wrapper_shutdown_argument_count": 16,
            "ps_wrapper_max_transaction_bytes_argument_present": False,
            "historical_shutdown_argv_mismatch_proven": arg_mismatch,
            "sources": {
                role: _hash_record(Path(record["resolved_path"]))
                for role, record in frozen_records.items()
                if role.startswith("historical_")
            },
        }

    recovery_dirs = sorted(epoch_root.glob("recovery_shutdown_after_failed_stage062_*"))
    declared_recoveries = frozen_manifest.get("recovery_directories") if isinstance(frozen_manifest, dict) else None
    append_error(
        errors,
        len(recovery_dirs) == 1
        and isinstance(declared_recoveries, list)
        and declared_recoveries == [recovery_dirs[0].name],
        f"{label} recovery directory binding mismatch",
    )
    recovery_record: dict[str, Any] | None = None
    recovery_end = float("nan")
    if len(recovery_dirs) == 1:
        recovery_dir = recovery_dirs[0]
        expected_recovery_files = {
            "program_tfdu_shutdown_safe.summary.txt",
            "hardware_authorization.json",
            "hash_manifest.json",
            "hash_manifest.csv",
            "program_tfdu_shutdown_safe.stdout.log",
            "program_tfdu_shutdown_safe.stderr.log",
        }
        append_error(errors, {path.name for path in recovery_dir.iterdir() if path.is_file()} == expected_recovery_files, f"{label} recovery file set mismatch")
        summary = recovery_dir / "program_tfdu_shutdown_safe.summary.txt"
        recovery_text = marker_text(summary)
        recovery_markers, recovery_duplicates = parse_marker_text(recovery_text)
        recovery_begin_text = next(
            (
                line.removeprefix("PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN ").strip()
                for line in recovery_text.splitlines()
                if line.startswith("PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN ")
            ),
            "",
        )
        recovery_end_text = next(
            (
                line.removeprefix("PROGRAM_TFDU_SHUTDOWN_SAFE_END ").strip()
                for line in recovery_text.splitlines()
                if line.startswith("PROGRAM_TFDU_SHUTDOWN_SAFE_END ")
            ),
            "",
        )
        append_error(
            errors,
            not recovery_duplicates
            and recovery_markers.get("SHUTDOWN_RAW_EXIT") == "125"
            and recovery_markers.get("TFDU_SHUTDOWN_PROGRAMMED_SEEN") == "1"
            and recovery_markers.get("SHUTDOWN_EXIT") == "0"
            and recovery_markers.get("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS") == "PASS",
            f"{label} independent recovery markers mismatch",
        )
        try:
            authorization = json.loads((recovery_dir / "hardware_authorization.json").read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{label} recovery authorization invalid: {exc}")
            authorization = {}
        append_error(errors, isinstance(authorization, dict) and authorization.get("AUTHORIZED") is True and authorization.get("P4_AUTHORIZATION") == "AUTHORIZED" and authorization.get("missing") == [], f"{label} recovery authorization mismatch")
        start = parse_time(recovery_begin_text, float("nan"))
        recovery_end = parse_time(recovery_end_text, float("nan"))
        recovery_record = {
            "directory": str(recovery_dir),
            "observed_raw_exit": 125,
            "shutdown_exit": 0,
            "tfdu_shutdown_programmed_seen": True,
            "started_at_utc": recovery_begin_text,
            "ended_at_utc": recovery_end_text,
            "files": [_hash_record(recovery_dir / name) for name in sorted(expected_recovery_files)],
        }
        outer_end = parse_time(attempt.get("ended_at_utc"), float("nan"))
        append_error(errors, outer_end == outer_end and start == start and recovery_end == recovery_end and outer_end <= start <= recovery_end, f"{label} recovery chronology mismatch")

    started_at = attempts[0].get("started_at_utc") if attempts else attempt.get("started_at_utc")
    record = {
        "schema": "rf-comm-p7-historical-failed-stage-epoch-v1",
        "epoch_root": str(epoch_root),
        "source_commit": source,
        "failure_class": HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED,
        "result": "FAIL",
        "coverage_keys": [],
        "mutation_attempted_by_wrapper": False,
        "mutation_attempted_by_candidate": False,
        "candidate_process_present": False,
        "outer_sequence_ledger": _hash_record(outer_path),
        "outer_process_containment": {
            "process_tree_reaped": process.get("process_tree_reaped"),
            "containment_kind": process.get("containment_kind"),
            "containment_assigned": process.get("containment_assigned"),
            "containment_closed": process.get("containment_closed"),
            "descendant_count_after": process.get("descendant_count_after"),
        },
        "inner_preflight_process_tree_reaped": candidate.data.get("preflight", {}).get(
            "process_tree_reaped"
        ),
        "read_only_target_identity": candidate.data.get("target_identity"),
        "historical_source_control_flow": historical_source_control_flow,
        "ps_shutdown_argument_count_rejection_failure": {
            "shutdown_before_returncode": candidate.data.get("shutdown_before", {}).get("returncode"),
            "shutdown_after_returncode": candidate.data.get("shutdown_after", {}).get("returncode"),
            "candidate_process_present": False,
            "candidate_programmed": False,
            "started_ps_elf": False,
            "exact_tcl_error": "P7 JTAG Tcl requires exactly 17 arguments",
        },
        "verified_historical_pass_prefix": [
            {
                "stage_index": index,
                "full_stage_ordinal": prefix_attempt.get("full_stage_ordinal"),
                "stage_id": prefix_attempt.get("stage_id"),
                "result": "PASS_ON_SUPERSEDED_SOURCE_NO_ACTIVE_CHECKPOINT_COVERAGE",
                "coverage_keys": [],
                "summary_file": prefix_attempt.get("summary_file"),
            }
            for index, prefix_attempt in enumerate(attempts[:11])
        ],
        "diagnostic_preflight_files": diagnostic_files,
        "frozen_preflight_inputs": {
            "manifest": _hash_record(frozen_manifest_path) if frozen_manifest_path.is_file() else None,
            "files": [
                {key: value for key, value in frozen_records[role].items() if key != "resolved_path"}
                for role in sorted(frozen_records)
            ],
        },
        "authorization_missing_no_action_recoveries": [],
        "effective_shutdown_recovery": recovery_record,
        "started_at_utc": started_at,
        "ended_at_utc": recovery_record.get("ended_at_utc") if isinstance(recovery_record, dict) else None,
        "ended_at_epoch_seconds": recovery_end,
    }
    return record, errors


def _historical_ps_reset_target_uniqueness_epoch_record(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    *,
    outer: Mapping[str, Any],
    outer_path: Path,
    epoch_root: Path,
    source: str,
) -> tuple[dict[str, Any], list[str]]:
    """Bind r18's adaptive prefix and exact pre-reset XSDB rejection."""

    errors: list[str] = []
    variant = _historical_preflight_variant(candidate)
    r21 = variant == HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED
    r22 = variant == HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED
    r23 = variant == HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED
    r24 = variant == HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED
    r25 = variant == HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED
    r26 = variant == HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED
    r27 = variant == HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED
    r28 = variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED
    r29 = variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED
    r30 = variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED
    r31 = variant == HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED
    label = "historical r31" if r31 else "historical r30" if r30 else "historical r29" if r29 else "historical r28" if r28 else "historical r27" if r27 else "historical r26" if r26 else "historical r25" if r25 else "historical r24" if r24 else "historical r23" if r23 else "historical r22" if r22 else "historical r21" if r21 else "historical r18"
    expected_ordinals = [1, 2, 3, 4, *range(55, 66)] if r26 or r28 or r29 or r30 or r31 else [1, 2, 3, 4, 62, 63, 64, 65]
    prefix_count = 11 if r26 or r28 or r29 or r30 or r31 else 4
    failed_index = prefix_count
    append_error(errors, outer.get("schema") == "rf-comm-p7-sequence-execution-ledger-v1", f"{label} outer schema mismatch")
    append_error(errors, outer.get("status") == "FAIL" and outer.get("hardware_actions_executed") is True, f"{label} outer result boundary mismatch")
    append_error(errors, outer.get("network_used") is False and outer.get("motion_used") is False, f"{label} outer no-network/no-motion mismatch")
    append_error(errors, str(outer.get("source_commit", "")).lower() == source, f"{label} outer source mismatch")
    append_error(
        errors,
        outer.get("plan_mode") == ("DIAGNOSTIC_SUFFIX_55" if r26 or r28 or r29 or r30 or r31 else "DIAGNOSTIC_ADAPTIVE_SUFFIX")
        and outer.get("coverage_claimed") is False
        and outer.get("HARDWARE_ACCEPTANCE") == "PENDING_HW"
        and outer.get("full_stage_ordinals") == expected_ordinals,
        f"{label} adaptive zero-coverage boundary mismatch",
    )
    append_error(
        errors,
        outer.get("attempt_count") == prefix_count + 1
        and outer.get("completed_stage_count") == prefix_count
        and outer.get("failed_stage_index") == failed_index
        and outer.get("next_stage_index") == failed_index,
        f"{label} failed-stage boundary mismatch",
    )
    attempts = outer.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != prefix_count + 1 or not all(isinstance(item, dict) for item in attempts):
        errors.append(f"{label} outer attempts malformed")
        attempts = []
    if attempts:
        errors.extend(
            _historical_r6_pass_prefix_errors(
                attempts[:prefix_count],
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
                source=source,
                expected_count=prefix_count,
                epoch_label=label,
                full_stage_ordinals=expected_ordinals[:prefix_count],
            )
        )
        attempt = attempts[prefix_count]
    else:
        attempt = {}
    append_error(
        errors,
        attempt.get("attempt") == prefix_count + 1
        and attempt.get("stage_index") == failed_index
        and attempt.get("full_stage_ordinal") == 62
        and attempt.get("stage_id") == "p7_ps_functional"
        and attempt.get("group") == "ps_functional"
        and attempt.get("risk_index") == 40
        and attempt.get("case") == {}
        and attempt.get("state") == "TERMINAL"
        and attempt.get("result") == "FAIL",
        f"{label} failed attempt identity mismatch",
    )
    append_error(
        errors,
        attempt.get("failures")
        == [
            "outer wrapper process containment/return-code policy failed",
            "wrapper result is not PASS: P7_PS_APPLICATION_SAFE_STAGE=FAIL_STAGE",
            "wrapper candidate process did not return rc=0 and PASS",
            "PS wrapper postprocess is missing or not PASS",
        ],
        f"{label} outer failure list mismatch",
    )
    summary_record = attempt.get("summary_file")
    errors.extend(_verify_historical_hash_file(summary_record, label=f"{label} failed summary", document=outer_path, repo_root=evidence.repo_root))
    append_error(
        errors,
        resolve_reference(summary_record.get("path") if isinstance(summary_record, dict) else None, document=outer_path, repo_root=evidence.repo_root)
        == candidate.path.resolve(strict=False),
        f"{label} outer summary binding mismatch",
    )
    process = attempt.get("process")
    if not isinstance(process, dict):
        errors.append(f"{label} outer process missing")
        process = {}
    append_error(
        errors,
        process.get("name") == "sequence_p7_ps_functional"
        and process.get("returncode") == 1
        and process.get("process_tree_reaped") is True
        and process.get("process_tree_terminated") is False
        and process.get("containment_kind") == "WINDOWS_JOB_OBJECT_KILL_ON_CLOSE"
        and process.get("containment_assigned") is True
        and process.get("containment_closed") is True
        and process.get("descendant_count_after") == 0
        and process.get("argv") == attempt.get("command"),
        f"{label} outer process/containment mismatch",
    )
    errors.extend(_v2_process_containment_errors(process, f"{label} outer process"))
    for key in ("stdout_file", "stderr_file"):
        errors.extend(_verify_historical_hash_file(process.get(key), label=f"{label} outer {key}", document=outer_path, repo_root=evidence.repo_root))
    outer_shutdown = attempt.get("shutdown_after")
    append_error(
        errors,
        isinstance(outer_shutdown, dict)
        and outer_shutdown.get("present") is True
        and outer_shutdown.get("returncode") == 0
        and outer_shutdown.get("passed") is True
        and outer_shutdown.get("attempted") is True
        and outer_shutdown.get("programming_attempted") is True
        and outer_shutdown.get("process_tree_reaped") is True
        and outer_shutdown.get("process_tree_terminated") is False
        and outer_shutdown.get("tfdu_shutdown_programmed_exact") is True
        and outer_shutdown.get("p7_tcl_programming_attempted") == "1"
        and outer_shutdown.get("p7_shutdown_result") == "PASS",
        f"{label} outer shutdown-after mismatch",
    )
    if isinstance(outer_shutdown, dict):
        errors.extend(_verify_historical_hash_file(outer_shutdown.get("result_file"), label=f"{label} outer shutdown result", document=outer_path, repo_root=evidence.repo_root))

    expected_stage_files = {
        "p7_hw_preflight_result.txt",
        "p7_ps_application_events.json",
        "p7_ps_application_raw_result.log",
        "p7_ps_application_stage_summary.json",
        "p7_raw_evidence_sha256_manifest.json",
        "preflight.stderr.log",
        "preflight.stdout.log",
        "ps_application_stage.stderr.log",
        "ps_application_stage.stdout.log",
        "shutdown_after.stderr.log",
        "shutdown_after.stdout.log",
        "shutdown_after_result.txt",
        "shutdown_before.stderr.log",
        "shutdown_before.stdout.log",
        "shutdown_before_result.txt",
    }
    append_error(
        errors,
        {path.name for path in candidate.path.parent.iterdir() if path.is_file()} == expected_stage_files
        and (candidate.path.parent / "bundle").is_dir(),
        f"{label} failed-stage file set mismatch",
    )

    frozen_dir = epoch_root / "historical_preflight_inputs"
    frozen_manifest_path = frozen_dir / "manifest.json"
    try:
        frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} frozen manifest invalid: {exc}")
        frozen_manifest = {}
    expected_roles = {
        "offline_checkpoint", "sequence_plan", "stage_authorization", "generation_manifest",
        "recovery_p4_authorization", "stage_execution_plan", "stage_bundle_manifest",
        "historical_stage_tcl", "historical_stage_wrapper_python",
        "historical_process_support_python", "historical_ps_execute_tcl",
        "historical_ps_mailbox_backend",
    }
    append_error(
        errors,
        frozen_manifest.get("schema") == "rf-comm-p7-historical-failed-stage-inputs-v1"
        and frozen_manifest.get("run_id") == epoch_root.name
        and str(frozen_manifest.get("source_commit", "")).lower() == source
        and frozen_manifest.get("stage_index") == failed_index
        and frozen_manifest.get("full_stage_ordinal") == 62
        and frozen_manifest.get("stage_id") == "p7_ps_functional"
        and frozen_manifest.get("result") == "FAIL_STAGE"
        and frozen_manifest.get("mutation_attempted") is True
        and frozen_manifest.get("candidate_mutation_attempted") is True
        and frozen_manifest.get("coverage_claimed") is False,
        f"{label} frozen manifest boundary mismatch",
    )
    frozen_records: dict[str, dict[str, Any]] = {}
    files = frozen_manifest.get("files") if isinstance(frozen_manifest, dict) else None
    if not isinstance(files, list) or len(files) != len(expected_roles):
        errors.append(f"{label} frozen manifest role count mismatch")
    else:
        for item in files:
            if not isinstance(item, dict):
                errors.append(f"{label} frozen manifest malformed record")
                continue
            role = str(item.get("role", ""))
            path = resolve_reference(item.get("frozen_path"), document=frozen_manifest_path, repo_root=evidence.repo_root)
            digest = str(item.get("sha256", "")).lower()
            append_error(errors, role in expected_roles and role not in frozen_records, f"{label} frozen role invalid/duplicate: {role}")
            append_error(errors, path is not None and path.is_file() and not path.is_symlink(), f"{label} frozen file missing/symbolic: {role}")
            if path is not None and path.is_file():
                append_error(errors, path.stat().st_size == item.get("bytes") and sha256_file(path) == digest, f"{label} frozen file size/hash mismatch: {role}")
                frozen_records[role] = {**item, "resolved_path": str(path)}
    append_error(errors, set(frozen_records) == expected_roles, f"{label} frozen roles incomplete")
    historical_source_control_flow: dict[str, Any] = {}
    if set(frozen_records) == expected_roles:
        source_paths = {
            "historical_stage_tcl": "scripts/hw/p7_jtag_axi_transactions.tcl",
            "historical_stage_wrapper_python": "scripts/hw/run_p7_ps_application_stage_safe.py",
            "historical_process_support_python": "scripts/hw/run_p7_jtag_axi_stage_safe.py",
            "historical_ps_execute_tcl": "scripts/hw/p7_ps_application_execute.tcl",
            "historical_ps_mailbox_backend": "tools/p7_ps_mailbox_backend.py",
        }
        texts: dict[str, str] = {}
        for role, relative in source_paths.items():
            frozen_path = Path(frozen_records[role]["resolved_path"])
            frozen_bytes = frozen_path.read_bytes()
            blob = hashlib.sha1(f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes).hexdigest()
            append_error(errors, blob == str(frozen_records[role].get("git_blob_sha1", "")).lower(), f"{label} frozen Git blob mismatch: {role}")
            try:
                committed = subprocess.run(["git", "show", f"{source}:{relative}"], cwd=evidence.repo_root, capture_output=True, timeout=30, check=False)
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(f"{label} unable to read source {relative}: {exc}")
            else:
                append_error(errors, committed.returncode == 0 and committed.stdout == frozen_bytes, f"{label} frozen source differs from commit: {role}")
            texts[role] = frozen_bytes.decode("utf-8", errors="replace")
        old_ps_tcl = texts.get("historical_ps_execute_tcl", "")
        old_row_predicate = (
            "if {[llength $dap_matches] == 1}" in old_ps_tcl
            and "[llength $dap_matches] == 0 && [llength $apu_matches] == 1" in old_ps_tcl
            and "proc p7_unique_targets_by_id" not in old_ps_tcl
        )
        child_identity_predicate = (
            "proc p7_unique_targets_by_id" in old_ps_tcl
            and "proc p7_classify_debug_targets" not in old_ps_tcl
            and "![dict exists $props jtag_device_id]" in old_ps_tcl
            and "![dict exists $props jtag_cable_serial]" in old_ps_tcl
        )
        device_cardinality_predicate = (
            "proc p7_classify_debug_targets" in old_ps_tcl
            and "[llength $all_device_nodes] != 1 || [llength $device_matches] != 1" in old_ps_tcl
            and "P7 XSDB live chain must contain only the one exact device/IDCODE match" in old_ps_tcl
        )
        functional_boundary_predicate = (
            "proc p7_classify_debug_targets" in old_ps_tcl
            and "[llength $all_device_nodes] != 1 || [llength $device_matches] != 1" not in old_ps_tcl
            and "P7 functional boundary case failed: index=$boundary_index length=$boundary_length($boundary_index)" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED" not in old_ps_tcl
        )
        failure_capture_predicate = (
            "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1" in old_ps_tcl
            and "dow -data $failure_descriptor $descriptor_address" in old_ps_tcl
            and "p7_atomic_dump $failure_descriptor $descriptor_address 256" not in old_ps_tcl
        )
        output_integrity_capture_predicate = (
            "P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1" in old_ps_tcl
            and "dow -data $failure_descriptor $descriptor_address" not in old_ps_tcl
            and "p7_atomic_dump $failure_descriptor $descriptor_address 256" in old_ps_tcl
        )
        boundary_30_capture_predicate = (
            output_integrity_capture_predicate
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED" not in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED" not in old_ps_tcl
            and "boundary_${boundary_index}_output_failure.bin" not in old_ps_tcl
            and "boundary_${boundary_index}_trace_failure.bin" not in old_ps_tcl
        )
        post_wipe_capture_predicate = (
            output_integrity_capture_predicate
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1" in old_ps_tcl
            and "boundary_${boundary_index}_output_failure.bin" in old_ps_tcl
            and "boundary_${boundary_index}_trace_failure.bin" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED" not in old_ps_tcl
        )
        failure_snapshot_marker_predicate = (
            output_integrity_capture_predicate
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED=1" in old_ps_tcl
            and "[p7_read32 $failure_snapshot_address] != 0x53463750" in old_ps_tcl
            and "P7 integrity failure snapshot publication marker missing" in old_ps_tcl
        )
        failure_snapshot_mailbox_marker_predicate = (
            output_integrity_capture_predicate
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED=1" in old_ps_tcl
            and "[p7_read32 $firmware_snapshot_address] != 0x53463750" in old_ps_tcl
            and "P7 integrity failure snapshot publication marker missing" in old_ps_tcl
            and "set firmware_snapshot_address [p7_read32 0x0002009C]" in old_ps_tcl
            and "set firmware_snapshot_bytes [p7_read32 0x000200A0]" in old_ps_tcl
            and "set firmware_snapshot_status [p7_read32 0x000200A4]" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_STATUS=$firmware_snapshot_status" in old_ps_tcl
            and "$firmware_snapshot_status != 1" in old_ps_tcl
            and "$firmware_snapshot_bytes != 320" in old_ps_tcl
        )
        failure_snapshot_captured_predicate = (
            failure_snapshot_mailbox_marker_predicate
            and "set failure_snapshot_address 0x00021000" in old_ps_tcl
            and "set firmware_snapshot_magic_readback [p7_read32 0x000200A8]" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_MAGIC_READBACK=[format 0x%08x $firmware_snapshot_magic_readback]" in old_ps_tcl
            and "$firmware_snapshot_magic_readback != 0x53463750" in old_ps_tcl
            and "p7_atomic_dump $failure_snapshot $firmware_snapshot_address 320" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED=1" in old_ps_tcl
            and "p7_zero_words_and_verify $firmware_snapshot_address 320" in old_ps_tcl
            and "p7_atomic_dump $failure_snapshot_wipe $firmware_snapshot_address 320" in old_ps_tcl
            and "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_WIPED=1" in old_ps_tcl
        )
        append_error(
            errors,
            failure_snapshot_captured_predicate
            if r30 or r31
            else failure_snapshot_mailbox_marker_predicate
            if r29
            else failure_snapshot_marker_predicate
            if r28
            else post_wipe_capture_predicate
            if r27
            else boundary_30_capture_predicate
            if r26
            else output_integrity_capture_predicate
            if r25
            else failure_capture_predicate
            if r24
            else functional_boundary_predicate
            if r23
            else device_cardinality_predicate
            if r22
            else child_identity_predicate
            if r21
            else old_row_predicate,
            f"{label} frozen source does not prove its exact target-selection predicate",
        )
        historical_source_control_flow = {
            "target_uniqueness_basis": (
                "FUNCTIONAL_BOUNDARY_30_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED_AFTER_FAIL_CLOSED_WIPE"
                if r31
                else "FUNCTIONAL_STRIPE_BOUNDARY_30_OCM_FAILURE_SNAPSHOT_CAPTURED_AND_WIPED"
                if r30
                else "FUNCTIONAL_LANE1_BOUNDARY_214_MAILBOX_PUBLISHED_FAILURE_SNAPSHOT_MARKER_MISSING"
                if r29
                else "FUNCTIONAL_REPLICATE_BOUNDARY_30_FAILURE_SNAPSHOT_MARKER_MISSING"
                if r28
                else "FUNCTIONAL_BOUNDARY_30_POST_WIPE_OUTPUT_AND_FRAGMENT_TRACE_CAPTURED"
                if r27
                else "FUNCTIONAL_BOUNDARY_30_DESCRIPTOR_CAPTURED_WITHOUT_OUTPUT_OR_TRACE_BYTES"
                if r26
                else "FUNCTIONAL_FAILURE_DESCRIPTOR_ATOMIC_CAPTURED_OUTPUT_CRC_SHA_DIVERGENCE"
                if r25
                else "FUNCTIONAL_FAILURE_DESCRIPTOR_CAPTURE_USED_DOW_IN_WRONG_DIRECTION"
                if r24
                else "SINGLE_CABLE_EXACT_DEVICE_MATCH_AND_DISTINCT_CHILD_TARGET_IDS"
                if r23
                else "SINGLE_CABLE_AND_SINGLE_ANY_IDCODE_ROW_BEFORE_CHILD_CLASSIFICATION"
                if r22
                else "DISTINCT_TARGET_ID_WITH_CHILD_ROWS_REQUIRING_DIRECT_JTAG_IDENTITY"
                if r21
                else "PROPERTY_ROW_COUNT"
            ),
            "numeric_target_id_dedup_present": r21 or r22 or r23 or r24 or r25 or r26 or r27 or r28 or r29 or r30 or r31,
            "historical_target_rejection_proven": (
                failure_snapshot_captured_predicate
                if r30 or r31
                else failure_snapshot_mailbox_marker_predicate
                if r29
                else failure_snapshot_marker_predicate
                if r28
                else post_wipe_capture_predicate
                if r27
                else boundary_30_capture_predicate
                if r26
                else output_integrity_capture_predicate
                if r25
                else failure_capture_predicate
                if r24
                else functional_boundary_predicate
                if r23
                else device_cardinality_predicate
                if r22
                else child_identity_predicate
                if r21
                else old_row_predicate
            ),
            "sources": {
                role: _hash_record(Path(record["resolved_path"]))
                for role, record in frozen_records.items()
                if role.startswith("historical_")
            },
        }

    recovery_dirs = sorted(epoch_root.glob("recovery_shutdown_after_failed_stage062_*"))
    declared = frozen_manifest.get("recovery_directories") if isinstance(frozen_manifest, dict) else None
    expected_recovery_count = 2 if r21 else 1
    append_error(
        errors,
        len(recovery_dirs) == expected_recovery_count
        and declared == [path.name for path in recovery_dirs],
        f"{label} recovery directory binding mismatch",
    )
    recovery_record: dict[str, Any] | None = None
    no_action_recoveries: list[dict[str, Any]] = []
    recovery_end = float("nan")
    previous_end = parse_time(attempt.get("ended_at_utc"), float("nan"))
    for recovery_dir in recovery_dirs:
        expected_recovery_files = {
            "program_tfdu_shutdown_safe.summary.txt", "hardware_authorization.json",
            "hash_manifest.json", "hash_manifest.csv", "program_tfdu_shutdown_safe.stdout.log",
            "program_tfdu_shutdown_safe.stderr.log",
        }
        observed_files = {path.name for path in recovery_dir.iterdir() if path.is_file()}
        summary_path = recovery_dir / "program_tfdu_shutdown_safe.summary.txt"
        text = marker_text(summary_path)
        markers, duplicates = parse_marker_text(text)
        begin_text = next((line.split(" ", 1)[1].strip() for line in text.splitlines() if line.startswith("PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN ")), "")
        end_text = next((line.split(" ", 1)[1].strip() for line in text.splitlines() if line.startswith("PROGRAM_TFDU_SHUTDOWN_SAFE_END ")), "")
        try:
            authorization = json.loads((recovery_dir / "hardware_authorization.json").read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"{label} recovery authorization invalid: {exc}")
            authorization = {}
        recovery_start = parse_time(begin_text, float("nan"))
        current_end = parse_time(end_text, float("nan"))
        append_error(
            errors,
            previous_end == previous_end
            and recovery_start == recovery_start
            and current_end == current_end
            and previous_end <= recovery_start <= current_end,
            f"{label} recovery chronology mismatch",
        )
        previous_end = current_end
        if markers.get("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS") == "AUTHORIZATION_MISSING":
            expected_no_action_files = expected_recovery_files - {
                "program_tfdu_shutdown_safe.stdout.log",
                "program_tfdu_shutdown_safe.stderr.log",
            }
            append_error(errors, observed_files == expected_no_action_files, f"{label} no-action recovery file set mismatch")
            append_error(
                errors,
                not duplicates
                and markers.get("HARDWARE_AUTHORIZATION_EXIT") == "2"
                and markers.get("AUTHORIZATION_MISSING") == "1"
                and markers.get("NO_HARDWARE_ACTIONS_EXECUTED") == "1"
                and authorization.get("AUTHORIZED") is False
                and "RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"
                in authorization.get("missing", []),
                f"{label} no-action recovery boundary mismatch",
            )
            no_action_recoveries.append(
                {
                    "directory": str(recovery_dir),
                    "hardware_actions_executed": False,
                    "started_at_utc": begin_text,
                    "ended_at_utc": end_text,
                    "files": [_hash_record(recovery_dir / name) for name in sorted(expected_no_action_files)],
                }
            )
            continue
        append_error(errors, observed_files == expected_recovery_files, f"{label} effective recovery file set mismatch")
        append_error(
            errors,
            not duplicates
            and markers.get("SHUTDOWN_RAW_EXIT") == "125"
            and markers.get("TFDU_SHUTDOWN_PROGRAMMED_SEEN") == "1"
            and markers.get("SHUTDOWN_EXIT") == "0"
            and markers.get("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS") == "PASS",
            f"{label} independent recovery markers mismatch",
        )
        append_error(errors, recovery_record is None, f"{label} has more than one effective recovery")
        append_error(errors, authorization.get("AUTHORIZED") is True and authorization.get("P4_AUTHORIZATION") == "AUTHORIZED" and authorization.get("missing") == [], f"{label} recovery authorization mismatch")
        recovery_end = current_end
        recovery_record = {
            "directory": str(recovery_dir),
            "observed_raw_exit": 125,
            "shutdown_exit": 0,
            "tfdu_shutdown_programmed_seen": True,
            "started_at_utc": begin_text,
            "ended_at_utc": end_text,
            "files": [_hash_record(recovery_dir / name) for name in sorted(expected_recovery_files)],
        }
    append_error(errors, recovery_record is not None, f"{label} effective recovery missing")
    append_error(errors, len(no_action_recoveries) == (1 if r21 else 0), f"{label} no-action recovery count mismatch")

    record = {
        "schema": "rf-comm-p7-historical-failed-stage-epoch-v1",
        "epoch_root": str(epoch_root),
        "source_commit": source,
        "failure_class": variant,
        "result": "FAIL",
        "coverage_keys": [],
        "mutation_attempted_by_wrapper": True,
        "mutation_attempted_by_candidate": True,
        "candidate_programmed": candidate.data.get("programmed_candidate"),
        "started_ps_elf": candidate.data.get("started_ps_elf"),
        "outer_sequence_ledger": _hash_record(outer_path),
        "outer_process_containment": {
            "process_tree_reaped": process.get("process_tree_reaped"),
            "containment_kind": process.get("containment_kind"),
            "containment_assigned": process.get("containment_assigned"),
            "containment_closed": process.get("containment_closed"),
            "descendant_count_after": process.get("descendant_count_after"),
        },
        "inner_preflight_process_tree_reaped": candidate.data.get("preflight", {}).get(
            "process_tree_reaped"
        ),
        "read_only_target_identity": candidate.data.get("target_identity"),
        "historical_source_control_flow": historical_source_control_flow,
        "ps_reset_target_uniqueness_rejection": {
            "candidate_process_returncode": candidate.data.get("ps_process", {}).get("returncode"),
            "candidate_process_marker_passed": candidate.data.get("ps_process", {}).get("passed"),
            "candidate_programmed": candidate.data.get("programmed_candidate"),
            "started_ps_elf": candidate.data.get("started_ps_elf"),
            "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
            "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
            "raw_error": (
                "P7 functional boundary case failed at index=8 length=30 status=4 error=23; the descriptor proves expected/input SHA256=f2192584b67da35dfc26f743e5f53bb0376046f899dc6dabd5e7b541ae86c32f, fragments_completed=0, output CRC32=0, and zero output SHA256; the fragment trace records lane0 mask 0x1, attempt=1, result=0, error=23 and p6_error_code=23; post-terminal DDR output is all zero after fail-closed wipe. This proves the verified final output-copy boundary rejected a mismatch, but does not identify which pre-wipe byte first differed or prove rx_payload alignment as the root cause"
                if r31
                else "P7 functional boundary case failed at index=10 length=30 status=4 error=13; descriptor expected/input SHA256=f2192584b67da35dfc26f743e5f53bb0376046f899dc6dabd5e7b541ae86c32f but output CRC32=0x1fda9db9 and SHA256=85cc3c9bdc8b6699e216e48c446c9f4f7d861a8bcfef504fcaeb02b3e99ad750; fragment trace records lane0 mask 0x1, attempt=1, result=1 and zero error fields; the OCM snapshot at 0x00021000 captured every 32-bit payload word with its low 16 bits zeroed, matched the descriptor digest, and was independently captured then wiped to 320 zero bytes; post-terminal DDR output is all zero after fail-closed wipe"
                if r30
                else "P7 integrity failure snapshot publication marker missing at boundary index=13 length=214 status=4 error=13; firmware mailbox reported address=0x0b100040 bytes=320 status=PUBLISHED; descriptor output CRC32=0xe56aefe1 and SHA256=fa740d204a804cb81d21e7d56bff7091dbc387d59c9e50e2d400a4275f85bcf0; fragment trace records lane1 mask 0x2, attempt=1, result=1 and zero error fields; post-terminal output contains only byte 0x02 at offset 100 and no integrity snapshot file was captured"
                if r29
                else "P7 integrity failure snapshot publication marker missing at boundary index=11 length=30 status=4 error=13; descriptor output CRC32=0x0b14a45e and SHA256=152b23e36032b5b79a2f47434511a939aa869078ef97c37d757772102af7972c; fragment trace records replicate lane mask 0x3, attempt=1, result=1 and zero error fields; post-terminal output is all zero and no integrity snapshot file was captured"
                if r28
                else "P7 functional boundary case failed: index=8 length=30 status=4 error=13; descriptor output CRC32=0x1fda9db9 and SHA256=85cc3c9bdc8b6699e216e48c446c9f4f7d861a8bcfef504fcaeb02b3e99ad750; fragment trace records lane0, attempt=1, result=0 and zero error fields, while the post-terminal output capture is all zero because frozen firmware wipes completed output bytes before publishing FAILED"
                if r27
                else "P7 functional boundary case failed: index=8 length=30 status=4 error=13; descriptor expected/input SHA256=f2192584b67da35dfc26f743e5f53bb0376046f899dc6dabd5e7b541ae86c32f, output CRC32=0x0a703d75, output SHA256=7b1241c20725167eb4bf923caa908244ee622a994ec2e3fcc8cadea7584f1d46; output bytes were not captured"
                if r26
                else "P7 functional boundary case failed: index=6 length=1 status=4 error=13; descriptor output CRC corresponds to byte 0x02 while output SHA256 equals the expected byte 0x00 digest"
                if r25
                else "failure descriptor capture used XSDB dow and failed before status/error markers"
                if r24
                else "P7 functional boundary case failed: index=8 length=30"
                if r23
                else "P7 XSDB live chain must contain only the one exact device/IDCODE match"
                if r22
                else "P7 XSDB reset target is not unique on the exact authorized device"
            ),
        },
        "verified_historical_pass_prefix": [
            {
                "stage_index": index,
                "full_stage_ordinal": prefix_attempt.get("full_stage_ordinal"),
                "stage_id": prefix_attempt.get("stage_id"),
                "result": "PASS_ON_SUPERSEDED_SOURCE_NO_ACTIVE_CHECKPOINT_COVERAGE",
                "coverage_keys": [],
                "summary_file": prefix_attempt.get("summary_file"),
            }
            for index, prefix_attempt in enumerate(attempts[:prefix_count])
        ],
        "frozen_inputs_manifest": _hash_record(frozen_manifest_path),
        "failed_stage_files": {
            name: _hash_record(candidate.path.parent / name) for name in sorted(expected_stage_files)
        },
        "authorization_missing_no_action_recoveries": no_action_recoveries,
        "effective_shutdown_recovery": recovery_record,
        "started_at_utc": attempts[0].get("started_at_utc") if attempts else attempt.get("started_at_utc"),
        "ended_at_utc": recovery_record.get("ended_at_utc") if isinstance(recovery_record, dict) else None,
        "ended_at_epoch_seconds": recovery_end,
    }
    return record, errors


def _historical_epoch_record(candidate: Candidate, evidence: RepositoryEvidence) -> tuple[dict[str, Any], list[str]]:
    """Bind the superseded executor attempt and manifest-declared recoveries.

    The inner preflight's historical ``process_tree_reaped=false`` is preserved
    verbatim.  It is not promoted to PASS: the enclosing sequence process must
    independently prove complete containment/reap.  Zero or more authorization-
    missing recoveries remain explicit no-action records, followed by exactly
    one final recovery that proves an actually programmed shutdown image.
    """

    errors: list[str] = []
    epoch_root = candidate.path.parent.parent.resolve(strict=False)
    outer_path = epoch_root / "sequence_execution_ledger.json"
    try:
        outer = json.loads(outer_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"historical outer sequence ledger invalid: {exc}"]
    if not isinstance(outer, dict):
        return {}, ["historical outer sequence ledger is not an object"]
    source = _candidate_source_commit(candidate)
    historical_variant = _historical_preflight_variant(candidate)
    if historical_variant == HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED:
        return _historical_ps_shutdown_arg_count_epoch_record(
            candidate,
            evidence,
            outer=outer,
            outer_path=outer_path,
            epoch_root=epoch_root,
            source=source,
        )
    if historical_variant in {
        HISTORICAL_STAGE_PS_RESET_TARGET_UNIQUENESS_REJECTED,
        HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED,
        HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED,
        HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED,
        HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED,
        HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED,
        HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED,
        HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED,
        HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED,
        HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED,
        HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED,
        HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED,
    }:
        return _historical_ps_reset_target_uniqueness_epoch_record(
            candidate,
            evidence,
            outer=outer,
            outer_path=outer_path,
            epoch_root=epoch_root,
            source=source,
        )
    one_m_timeout_variants = {
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
    }
    failed_stage_variants = {
        HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED,
        HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED,
        HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
        HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
        HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
        HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
        HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }
    failed_stage_variant = historical_variant in failed_stage_variants
    failed_stage_index = (
        7
        if historical_variant in one_m_timeout_variants
        else 54
        if historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED
        else 27
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED
        else 2
        if historical_variant
        in {
            HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
            HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
        }
        else 1
        if historical_variant
        in {
            HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
            HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
            HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
            HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
            HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
        }
        else 0
    )
    full_failed_stage_ordinal = (
        58
        if historical_variant in one_m_timeout_variants
        else failed_stage_index + 1
    )
    recovery_failed_stage_label = (
        f"{full_failed_stage_ordinal:03d}"
        if historical_variant
        in {
            HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
            HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
            HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
            HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
            HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
            HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
        }
        else str(full_failed_stage_ordinal)
    )
    append_error(errors, outer.get("schema") == "rf-comm-p7-sequence-execution-ledger-v1", "historical outer sequence ledger schema mismatch")
    append_error(errors, outer.get("status") == "FAIL", "historical outer sequence ledger is not FAIL")
    append_error(errors, outer.get("hardware_actions_executed") is True, "historical outer sequence ledger omits hardware_actions_executed=true")
    append_error(errors, outer.get("network_used") is False and outer.get("motion_used") is False, "historical outer sequence ledger violates no-network/no-motion")
    append_error(errors, str(outer.get("source_commit", "")).lower() == source, "historical outer sequence ledger source commit mismatch")
    if historical_variant in {
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        diagnostic_label = (
            "historical r10"
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT
            else "historical r13"
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
            else "historical r11"
            if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
            else "historical r12"
            if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
            else "historical r14"
            if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
            else "historical r15"
        )
        append_error(errors, outer.get("plan_mode") == "DIAGNOSTIC_SUFFIX_55", f"{diagnostic_label} outer plan mode mismatch")
        append_error(errors, outer.get("coverage_claimed") is False and outer.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", f"{diagnostic_label} outer ledger claims acceptance coverage")
        append_error(errors, outer.get("full_stage_ordinals") == [1, 2, 3, 4, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65], f"{diagnostic_label} outer full-stage ordinal matrix mismatch")
    append_error(errors, outer.get("attempt_count") == failed_stage_index + 1 and outer.get("completed_stage_count") == failed_stage_index, "historical outer sequence ledger attempt/completion count mismatch")
    append_error(errors, outer.get("next_stage_index") == failed_stage_index and outer.get("failed_stage_index") == failed_stage_index, "historical outer sequence ledger failed-stage boundary mismatch")
    attempts = outer.get("attempts")
    if not isinstance(attempts, list) or len(attempts) != failed_stage_index + 1 or not all(isinstance(item, dict) for item in attempts):
        errors.append("historical outer sequence ledger attempt list does not match the failed-stage boundary")
        attempt: dict[str, Any] = {}
    else:
        if historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED:
            errors.extend(
                _historical_r5_safe_idle_prefix_errors(
                    attempts[0],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                )
            )
        elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED:
            errors.extend(
                _historical_r6_pass_prefix_errors(
                    attempts[:failed_stage_index],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                )
            )
        elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED:
            errors.extend(
                _historical_r6_pass_prefix_errors(
                    attempts[:failed_stage_index],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                    expected_count=2,
                    epoch_label="historical r7",
                )
            )
        elif historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED:
            errors.extend(
                _historical_r6_pass_prefix_errors(
                    attempts[:failed_stage_index],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                    expected_count=54,
                    epoch_label="historical r8",
                )
            )
        elif historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE:
            errors.extend(
                _historical_r6_pass_prefix_errors(
                    attempts[:failed_stage_index],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                    expected_count=2,
                    epoch_label="historical r9",
                )
            )
        elif historical_variant in one_m_timeout_variants:
            errors.extend(
                _historical_r10_pass_prefix_errors(
                    attempts[:failed_stage_index],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                )
            )
        elif historical_variant in {
            HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
            HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
            HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
            HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
        }:
            errors.extend(
                _historical_r5_safe_idle_prefix_errors(
                    attempts[0],
                    epoch_root=epoch_root,
                    outer_path=outer_path,
                    evidence=evidence,
                    source=source,
                )
            )
        attempt = attempts[failed_stage_index]
    append_error(errors, attempt.get("attempt") == failed_stage_index + 1 and attempt.get("stage_index") == failed_stage_index, "historical outer attempt identity mismatch")
    if historical_variant in {
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        diagnostic_label = (
            "historical r10"
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT
            else "historical r13"
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
            else "historical r11"
            if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
            else "historical r12"
            if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
            else "historical r14"
            if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
            else "historical r15"
        )
        append_error(errors, attempt.get("full_stage_ordinal") == full_failed_stage_ordinal, f"{diagnostic_label} failed attempt full-stage ordinal mismatch")
    append_error(errors, attempt.get("stage_id") == candidate.data.get("stage_name"), "historical outer attempt stage mismatch")
    expected_group = (
        "large_object_jtag"
        if historical_variant in {HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED, *one_m_timeout_variants}
        else "fragment_boundary"
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED
        else "p6_frame_regression"
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED
        else "p6_frame_regression"
        if historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE
        else "p6_frame_regression"
        if failed_stage_index == 1
        else "safe_idle"
    )
    expected_case = (
        {"lane_policy": "LANE0_ONLY", "object_size": 1048576, "pattern": "deterministic_random"}
        if historical_variant in one_m_timeout_variants
        else {"lane_policy": "STRIPE_ROUND_ROBIN", "object_size": 65536, "pattern": "prbs15"}
        if historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED
        else {"lane_policy": "REPLICATE_0X3", "object_size": 216}
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED
        else {"lane_mask": 2, "minimum_fragments": 10}
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED
        else {"lane_mask": 2, "minimum_fragments": 10}
        if historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE
        else {"lane_mask": 1, "minimum_fragments": 10}
        if failed_stage_index == 1
        else {}
    )
    append_error(errors, attempt.get("group") == expected_group and attempt.get("case") == expected_case, "historical outer attempt group/case mismatch")
    append_error(errors, attempt.get("state") == "TERMINAL" and attempt.get("result") == "FAIL", "historical outer attempt is not terminal FAIL")
    expected_risk = (
        32
        if historical_variant in one_m_timeout_variants
        else 31
        if historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED
        else 25
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED
        else 20
        if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED
        else 20
        if historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE
        else 20
        if failed_stage_index == 1
        else 10
    )
    append_error(errors, attempt.get("risk_index") == expected_risk, "historical outer plan risk mismatch")
    append_error(errors, isinstance(attempt.get("command"), list) and bool(attempt.get("command")), "historical outer attempt exact command missing")
    append_error(errors, isinstance(attempt.get("failures"), list) and bool(attempt.get("failures")), "historical outer attempt failure list missing")
    if failed_stage_variant:
        append_error(errors, isinstance(attempt.get("shutdown_after"), dict) and attempt.get("shutdown_after", {}).get("present") is True, "historical failed-stage outer attempt omits shutdown-after evidence")
    else:
        append_error(errors, isinstance(attempt.get("shutdown_after"), dict) and attempt.get("shutdown_after", {}).get("present") is False, "historical outer attempt incorrectly claims shutdown-after")
    summary_record = attempt.get("summary_file")
    errors.extend(
        _verify_historical_hash_file(
            summary_record,
            label="historical outer attempt summary",
            document=outer_path,
            repo_root=evidence.repo_root,
        )
    )
    summary_path = resolve_reference(summary_record.get("path") if isinstance(summary_record, dict) else None, document=outer_path, repo_root=evidence.repo_root)
    append_error(errors, summary_path == candidate.path.resolve(strict=False), "historical outer attempt does not bind the diagnostic summary")

    process = attempt.get("process")
    if not isinstance(process, dict):
        errors.append("historical outer sequence process record missing")
        process = {}
    append_error(errors, isinstance(process.get("returncode"), int) and process.get("returncode") != 0, "historical outer sequence process did not fail")
    append_error(errors, process.get("process_tree_reaped") is True, "historical outer sequence process was not reaped")
    append_error(errors, process.get("containment_kind") in {"WINDOWS_JOB_OBJECT_KILL_ON_CLOSE", "POSIX_PROCESS_GROUP"}, "historical outer sequence containment kind missing/unsupported")
    append_error(errors, process.get("containment_assigned") is True and process.get("containment_closed") is True, "historical outer sequence containment was not assigned/closed")
    append_error(errors, process.get("descendant_count_after") == 0, "historical outer sequence has remaining descendants")
    append_error(errors, not process.get("launch_error"), "historical outer sequence process has a launch error")
    for key in ("timed_out", "abort_seen", "interrupted", "process_tree_terminated"):
        append_error(errors, process.get(key) is False, f"historical outer sequence process reports {key}=true or missing")
    append_error(errors, process.get("argv") == attempt.get("command"), "historical outer sequence process argv does not bind command")
    for key in ("stdout_file", "stderr_file"):
        errors.extend(
            _verify_historical_hash_file(
                process.get(key),
                label=f"historical outer sequence {key}",
                document=outer_path,
                repo_root=evidence.repo_root,
            )
        )
    if historical_variant == HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED:
        errors.extend(
            _historical_r2_outer_containment_errors(
                attempt,
                process,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED:
        errors.extend(
            _historical_r3_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED:
        errors.extend(
            _historical_r4_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED:
        errors.extend(
            _historical_r5_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED:
        errors.extend(
            _historical_r6_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED:
        errors.extend(
            _historical_r7_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED:
        errors.extend(
            _historical_r8_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE:
        errors.extend(
            _historical_r9_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
            )
        )
    elif historical_variant in {
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        errors.extend(
            _historical_r11_outer_containment_errors(
                attempt,
                process,
                candidate=candidate,
                epoch_root=epoch_root,
                outer_path=outer_path,
                evidence=evidence,
                epoch_label=(
                    "historical r11"
                    if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
                    else "historical r12"
                    if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
                    else "historical r14"
                    if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
                    else "historical r15"
                ),
            )
        )

    wrapper_start, wrapper_end = authorized_execution_boundaries(candidate)
    outer_start = parse_time(attempt.get("started_at_utc"), float("nan"))
    outer_end = parse_time(attempt.get("ended_at_utc"), float("nan"))
    inner_start = parse_time(wrapper_start, float("nan"))
    inner_end = parse_time(wrapper_end, float("nan"))
    append_error(
        errors,
        all(value == value for value in (outer_start, inner_start, inner_end, outer_end))
        and outer_start <= inner_start <= inner_end <= outer_end,
        "historical outer/inner wrapper chronology mismatch",
    )
    if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED:
        diagnostic_file_names = (
            candidate.path.name,
            "p7_preflight.stdout.log",
            "p7_preflight.stderr.log",
            "p7_preflight_result.txt",
            "p7_shutdown_before.stdout.log",
            "p7_shutdown_before.stderr.log",
            "p7_shutdown_before_result.txt",
            "p7_shutdown_after.stdout.log",
            "p7_shutdown_after.stderr.log",
            "p7_shutdown_after_result.txt",
            "p7_jtag_axi_stage_events.jsonl",
        )
    elif historical_variant in {
        HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED,
        HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
        HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
        HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
        HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
        HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        diagnostic_file_names = (
            candidate.path.name,
            "p7_preflight.stdout.log",
            "p7_preflight.stderr.log",
            "p7_preflight_result.txt",
            "p7_shutdown_before.stdout.log",
            "p7_shutdown_before.stderr.log",
            "p7_shutdown_before_result.txt",
            "p7_jtag_axi_stage.stdout.log",
            "p7_jtag_axi_stage.stderr.log",
            "p7_jtag_axi_raw_result.txt",
            "p7_shutdown_after.stdout.log",
            "p7_shutdown_after.stderr.log",
            "p7_shutdown_after_result.txt",
            "p7_jtag_axi_stage_events.jsonl",
        )
    else:
        diagnostic_file_names = (
            candidate.path.name,
            "p7_preflight.stdout.log",
            "p7_preflight.stderr.log",
            "p7_preflight_result.txt",
            "p7_jtag_axi_stage_events.jsonl",
        )
    diagnostic_files: dict[str, dict[str, Any]] = {}
    for name in diagnostic_file_names:
        path = candidate.path.parent / name
        append_error(errors, path.is_file() and not path.is_symlink(), f"historical diagnostic file missing/symbolic: {name}")
        if path.is_file():
            diagnostic_files[name] = _hash_record(path)
    append_error(
        errors,
        {path.name for path in candidate.path.parent.iterdir() if path.is_file()}
        == set(diagnostic_file_names),
        "historical diagnostic stage file set mismatch",
    )

    frozen_dir = epoch_root / "historical_preflight_inputs"
    frozen_manifest_path = frozen_dir / "manifest.json"
    try:
        frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"historical preflight input manifest invalid: {exc}")
        frozen_manifest = {}
    expected_manifest_schema = (
        "rf-comm-p7-historical-failed-stage-inputs-v1"
        if failed_stage_variant
        else "rf-comm-p7-historical-preflight-inputs-v1"
    )
    append_error(errors, isinstance(frozen_manifest, dict) and frozen_manifest.get("schema") == expected_manifest_schema, "historical input manifest schema mismatch")
    append_error(errors, frozen_manifest.get("run_id") == epoch_root.name, "historical preflight input manifest run_id does not match epoch root")
    append_error(errors, str(frozen_manifest.get("source_commit", "")).lower() == source, "historical preflight input manifest source mismatch")
    append_error(errors, frozen_manifest.get("stage_index") == failed_stage_index and frozen_manifest.get("stage_id") == candidate.data.get("stage_name"), "historical preflight input manifest stage mismatch")
    if historical_variant in {
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        diagnostic_label = (
            "historical r10"
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT
            else "historical r13"
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
            else "historical r11"
            if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
            else "historical r12"
            if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
            else "historical r14"
            if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
            else "historical r15"
        )
        append_error(errors, frozen_manifest.get("full_stage_ordinal") == full_failed_stage_ordinal, f"{diagnostic_label} input manifest full-stage ordinal mismatch")
    append_error(
        errors,
        frozen_manifest.get("result") == (candidate.marker if failed_stage_variant else "FAIL_PREFLIGHT"),
        "historical preflight input manifest result mismatch",
    )
    append_error(
        errors,
        frozen_manifest.get("mutation_attempted") is failed_stage_variant,
        "historical preflight input manifest mutation-attempt fact mismatch",
    )
    if failed_stage_variant:
        append_error(
            errors,
            frozen_manifest.get("candidate_mutation_attempted")
            is (
                historical_variant
                in {
                    HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED,
                    HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
                    HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
                    HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
                    HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
                    HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
                    HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
                    HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
                    HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                    HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                    HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                    HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
                }
            ),
            "historical failed-stage input manifest candidate-mutation fact mismatch",
        )
    append_error(errors, frozen_manifest.get("coverage_claimed") is False, "historical preflight input manifest claims coverage")
    declared_recovery_dirs = frozen_manifest.get("recovery_directories")
    append_error(
        errors,
        isinstance(declared_recovery_dirs, list)
        and bool(declared_recovery_dirs)
        and len(declared_recovery_dirs) == len(set(str(item) for item in declared_recovery_dirs))
        and all(
            isinstance(item, str)
            and item.startswith(
                f"recovery_shutdown_after_failed_stage{recovery_failed_stage_label}_"
                if failed_stage_variant
                else "recovery_shutdown_after_failed_preflight_"
            )
            and Path(item).name == item
            and item not in {".", ".."}
            for item in declared_recovery_dirs
        ),
        "historical preflight input manifest recovery_directories is missing/unsafe/duplicated",
    )
    expected_roles = {
        "offline_checkpoint",
        "sequence_plan",
        "stage_authorization",
        "stage_transactions",
        "generation_manifest",
        "recovery_p4_authorization",
    }
    if failed_stage_variant:
        expected_roles.add("historical_stage_tcl")
    if historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED:
        expected_roles.update({"historical_backend_python", "historical_lane_phy_rtl"})
    elif historical_variant in {
        HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
        HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
        HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
        HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        expected_roles.update(
            {
                "historical_stage_wrapper_python",
                "historical_backend_python",
                "historical_lane_phy_rtl",
            }
        )
    frozen_files = frozen_manifest.get("files") if isinstance(frozen_manifest, dict) else None
    frozen_records: dict[str, dict[str, Any]] = {}
    if not isinstance(frozen_files, list) or len(frozen_files) != len(expected_roles):
        errors.append(f"historical preflight input manifest must contain exactly {len(expected_roles)} files")
    else:
        for index, item in enumerate(frozen_files):
            if not isinstance(item, dict):
                errors.append(f"historical preflight input manifest file {index} is malformed")
                continue
            role = str(item.get("role", ""))
            append_error(errors, role in expected_roles and role not in frozen_records, f"historical preflight input role invalid/duplicate: {role}")
            original_raw = Path(str(item.get("original_path", "")))
            original_resolved = (
                _remap_registered_worktree_reference(
                    original_raw, evidence.repo_root
                )
                if original_raw.is_absolute()
                else (evidence.repo_root / original_raw).resolve(strict=False)
            )
            append_error(errors, bool(str(item.get("original_path", ""))) and (original_raw.is_absolute() or ".." not in original_raw.parts), f"historical preflight input original path missing/unsafe: {role}")
            frozen_path = resolve_reference(item.get("frozen_path"), document=frozen_manifest_path, repo_root=evidence.repo_root)
            expected_sha = str(item.get("sha256", "")).lower()
            append_error(errors, frozen_path is not None and frozen_path.is_file() and not frozen_path.is_symlink(), f"historical frozen preflight input missing/symbolic: {role}")
            if frozen_path is not None:
                try:
                    frozen_path.resolve(strict=False).relative_to(frozen_dir.resolve(strict=False))
                except ValueError:
                    errors.append(f"historical frozen preflight input escapes its epoch: {role}")
            append_error(errors, SHA256_RE.fullmatch(expected_sha) is not None, f"historical frozen preflight input SHA256 malformed: {role}")
            if frozen_path is not None and frozen_path.is_file():
                append_error(errors, frozen_path.stat().st_size == item.get("bytes"), f"historical frozen preflight input byte count mismatch: {role}")
                if SHA256_RE.fullmatch(expected_sha):
                    append_error(errors, sha256_file(frozen_path) == expected_sha, f"historical frozen preflight input SHA256 mismatch: {role}")
                frozen_records[role] = {
                    "role": role,
                    "original_path": str(item.get("original_path", "")),
                    "original_resolved_path": str(original_resolved),
                    "frozen_file": _hash_record(frozen_path),
                    **(
                        {"git_blob_sha1": str(item.get("git_blob_sha1", "")).lower()}
                        if role.startswith("historical_")
                        else {}
                    ),
                }
    append_error(errors, set(frozen_records) == expected_roles, "historical frozen preflight input roles are incomplete")

    historical_source_control_flow: dict[str, Any] = {}
    if set(frozen_records) == expected_roles:
        role_paths = {role: Path(record["frozen_file"]["path"]) for role, record in frozen_records.items()}
        outer_offline = outer.get("offline_checkpoint") if isinstance(outer.get("offline_checkpoint"), dict) else {}
        outer_plan = outer.get("sequence_plan") if isinstance(outer.get("sequence_plan"), dict) else {}
        safety = candidate.data.get("safety_validation")
        authorization = safety.get("authorization") if isinstance(safety, dict) and isinstance(safety.get("authorization"), dict) else {}
        transaction = candidate.data.get("transaction_validation") if isinstance(candidate.data.get("transaction_validation"), dict) else {}
        expected_original_paths = {
            "offline_checkpoint": resolve_reference(outer_offline.get("path"), document=outer_path, repo_root=evidence.repo_root),
            "sequence_plan": resolve_reference(outer_plan.get("path"), document=outer_path, repo_root=evidence.repo_root),
            "stage_authorization": resolve_reference(authorization.get("path"), document=candidate.path, repo_root=evidence.repo_root),
            "stage_transactions": resolve_reference(transaction.get("path"), document=candidate.path, repo_root=evidence.repo_root),
            **(
                {
                    "historical_stage_tcl": (
                        evidence.repo_root / "scripts/hw/p7_jtag_axi_transactions.tcl"
                    ).resolve(strict=False)
                }
                if failed_stage_variant
                else {}
            ),
            **(
                {
                    **(
                        {
                            "historical_stage_wrapper_python": (
                                evidence.repo_root / "scripts/hw/run_p7_jtag_axi_stage_safe.py"
                            ).resolve(strict=False)
                        }
                        if historical_variant
                        in {
                            HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
                            HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
                            HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
                            HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
                            HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
                            HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
                            HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                            HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                            HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                            HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
                        }
                        else {}
                    ),
                    "historical_backend_python": (
                        evidence.repo_root / "tools/p7_jtag_backend.py"
                    ).resolve(strict=False),
                    "historical_lane_phy_rtl": (
                        evidence.repo_root / "rtl/tfdu_lane_phy.sv"
                    ).resolve(strict=False),
                }
                if historical_variant
                in {
                    HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
                    HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
                    HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
                    HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
                    HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
                    HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
                    HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
                    HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                    HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                    HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                    HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
                }
                else {}
            ),
        }
        for role, expected_original in expected_original_paths.items():
            append_error(
                errors,
                _same_registered_worktree_location(
                    Path(frozen_records[role]["original_resolved_path"]),
                    expected_original,
                    evidence.repo_root,
                ),
                f"historical frozen input original_path does not bind recorded {role} path",
            )
        generation_original = Path(frozen_records["generation_manifest"]["original_resolved_path"])
        generation_root = (evidence.repo_root / "build/p7_authorized_sequence").resolve(strict=False)
        try:
            generation_relative = generation_original.relative_to(generation_root)
        except ValueError:
            generation_relative = None
        append_error(
            errors,
            generation_relative is not None
            and len(generation_relative.parts) == 2
            and generation_relative.parts[0].startswith(epoch_root.name)
            and generation_relative.parts[1] == "p7_authorized_sequence_generation_manifest.json",
            "historical frozen generation manifest original_path does not bind a run-scoped generator bundle",
        )
        append_error(errors, str(outer_offline.get("sha256", "")).lower() == frozen_records["offline_checkpoint"]["frozen_file"]["sha256"], "historical frozen offline checkpoint does not bind outer ledger")
        append_error(errors, str(outer_plan.get("sha256", "")).lower() == frozen_records["sequence_plan"]["frozen_file"]["sha256"], "historical frozen sequence plan does not bind outer ledger")
        append_error(errors, str(authorization.get("actual_sha256", "")).lower() == frozen_records["stage_authorization"]["frozen_file"]["sha256"], "historical frozen stage authorization does not bind wrapper summary")
        append_error(errors, isinstance(transaction, dict) and str(transaction.get("actual_sha256", "")).lower() == frozen_records["stage_transactions"]["frozen_file"]["sha256"], "historical frozen transactions do not bind wrapper summary")
        if failed_stage_variant:
            historical_tcl = role_paths["historical_stage_tcl"]
            historical_tcl_bytes = historical_tcl.read_bytes()
            recorded_blob_sha1 = str(frozen_records["historical_stage_tcl"].get("git_blob_sha1", "")).lower()
            computed_blob_sha1 = hashlib.sha1(
                f"blob {len(historical_tcl_bytes)}\0".encode("ascii") + historical_tcl_bytes
            ).hexdigest()
            append_error(errors, re.fullmatch(r"[0-9a-f]{40}", recorded_blob_sha1) is not None, "historical failed-stage frozen Tcl manifest Git blob identity is malformed")
            append_error(errors, computed_blob_sha1 == recorded_blob_sha1, "historical failed-stage frozen Tcl bytes do not hash to the manifest Git blob")
            try:
                committed_tcl = subprocess.run(
                    ["git", "show", f"{source}:scripts/hw/p7_jtag_axi_transactions.tcl"],
                    cwd=evidence.repo_root,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                errors.append(f"unable to read historical failed-stage Tcl Git blob: {exc}")
            else:
                append_error(errors, committed_tcl.returncode == 0, "historical failed-stage Tcl is absent from its source commit")
                append_error(errors, committed_tcl.stdout == historical_tcl_bytes, "historical failed-stage frozen Tcl differs from its source-commit blob")
            try:
                historical_tcl_text = historical_tcl_bytes.decode("utf-8", errors="strict")
            except UnicodeError as exc:
                errors.append(f"historical failed-stage frozen Tcl is not strict UTF-8: {exc}")
            else:
                common_control_flow = {
                    "path": str(historical_tcl),
                    "git_blob_sha1": computed_blob_sha1,
                    "sha256": hashlib.sha256(historical_tcl_bytes).hexdigest(),
                    "size_bytes": len(historical_tcl_bytes),
                }
                if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED:
                    bad_map = r"string map {\ /}"
                    authorization_bad_map = r"set auth_slash [string map {\ /} $authorization_file]"
                    bad_map_offset = historical_tcl_text.find(authorization_bad_map)
                    open_offset = historical_tcl_text.find("open_hw_manager")
                    program_offset = historical_tcl_text.find("program_hw_devices")
                    append_error(errors, historical_tcl_text.count(bad_map) == 3, "historical r3 frozen Tcl bad path-map occurrence count mismatch")
                    append_error(errors, historical_tcl_text.count(authorization_bad_map) == 1, "historical r3 frozen Tcl authorization bad-map site missing/duplicated")
                    append_error(errors, 0 <= bad_map_offset < open_offset < program_offset, "historical r3 frozen Tcl does not prove the unconditional bad map precedes hardware open/program")
                    append_error(errors, "P7_TCL_PROGRAMMING_ATTEMPTED" not in historical_tcl_text, "historical r3 frozen Tcl unexpectedly contains post-fix programming markers")
                    historical_source_control_flow = {
                        **common_control_flow,
                        "bad_path_map_occurrence_count": historical_tcl_text.count(bad_map),
                        "authorization_bad_map_byte_offset": bad_map_offset,
                        "open_hw_manager_byte_offset": open_offset,
                        "first_program_hw_devices_byte_offset": program_offset,
                        "unconditional_bad_map_precedes_hardware_open_and_program": 0 <= bad_map_offset < open_offset < program_offset,
                    }
                elif historical_variant == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED:
                    broken_allowlist = "set fixed [list 0x100 0x108 0x10C 0x110 0x114 0x118 0x11C 0x15C 0x16C 0x170 0x174]"
                    validate_call = "p7_validate_write $offset $data"
                    write_call = "p7_axi_write $hw_axi $address $data txn_index"
                    validate_offset = historical_tcl_text.find(validate_call)
                    write_offset = historical_tcl_text.find(write_call)
                    append_error(errors, historical_tcl_text.count(broken_allowlist) == 1, "historical r4 frozen Tcl broken write allowlist missing/duplicated")
                    append_error(errors, historical_tcl_text.count(validate_call) == 1 and historical_tcl_text.count(write_call) == 1, "historical r4 frozen Tcl validate/write call sites missing/duplicated")
                    append_error(errors, 0 <= validate_offset < write_offset, "historical r4 frozen Tcl does not prove allowlist validation precedes AXI write")
                    append_error(errors, r"string map {\ /}" not in historical_tcl_text, "historical r4 frozen Tcl regressed to the r3 bad path map")
                    append_error(errors, "P7_TCL_PROGRAMMING_ATTEMPTED" in historical_tcl_text, "historical r4 frozen Tcl omits programming-attempt provenance")
                    historical_source_control_flow = {
                        **common_control_flow,
                        "broken_write_allowlist_occurrence_count": historical_tcl_text.count(broken_allowlist),
                        "validate_write_call_byte_offset": validate_offset,
                        "axi_write_call_byte_offset": write_offset,
                        "allowlist_validation_precedes_axi_write": 0 <= validate_offset < write_offset,
                    }
            if historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED:
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(
                        f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes
                    ).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"historical r5 frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(
                            ["git", "show", f"{source}:{relative}"],
                            cwd=evidence.repo_root,
                            capture_output=True,
                            timeout=30,
                            check=False,
                        )
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read historical r5 source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"historical r5 frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"historical r5 frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {
                        "path": str(frozen_source),
                        "git_blob_sha1": computed_blob,
                        "sha256": hashlib.sha256(frozen_bytes).hexdigest(),
                        "size_bytes": len(frozen_bytes),
                        "text": source_text,
                    }
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                rtl_text = source_records.get("historical_lane_phy_rtl", {}).pop("text", "")
                old_check = 'if deltas[name] == 0:'
                old_failure = 'f"fragment {index} {name} did not increase"'
                rtl_tx_clear = "tx_pulse_count <= 32'd0;"
                rtl_rx_clear = "rx_raw_count <= 32'd0;"
                append_error(errors, backend_text.count(old_check) == 1 and backend_text.count(old_failure) == 1, "historical r5 backend does not bind the exact cumulative-delta rejection")
                append_error(errors, "clear_scoped_per_fragment_observation" not in backend_text, "historical r5 backend unexpectedly contains the post-fix clear-scoped semantics")
                clear_block_match = re.search(r"if \(clear_sticky\) begin(?P<body>.*?)end", rtl_text, re.DOTALL)
                clear_body = clear_block_match.group("body") if clear_block_match else ""
                append_error(errors, rtl_tx_clear in clear_body and rtl_rx_clear in clear_body, "historical r5 lane PHY does not prove raw pulse counters reset on clear_sticky")
                historical_source_control_flow = {
                    **historical_source_control_flow,
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                    "backend_requires_cumulative_raw_pulse_delta": old_check in backend_text,
                    "rtl_clear_sticky_resets_raw_pulse_counters": rtl_tx_clear in clear_body and rtl_rx_clear in clear_body,
                    "historical_contract_mismatch_proven": (
                        old_check in backend_text
                        and rtl_tx_clear in clear_body
                        and rtl_rx_clear in clear_body
                    ),
                }
            elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED:
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(
                        f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes
                    ).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"historical r6 frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(
                            ["git", "show", f"{source}:{relative}"],
                            cwd=evidence.repo_root,
                            capture_output=True,
                            timeout=30,
                            check=False,
                        )
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read historical r6 source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"historical r6 frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"historical r6 frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {
                        "path": str(frozen_source),
                        "git_blob_sha1": computed_blob,
                        "sha256": hashlib.sha256(frozen_bytes).hexdigest(),
                        "size_bytes": len(frozen_bytes),
                        "text": source_text,
                    }
                wrapper_text = source_records.get("historical_stage_wrapper_python", {}).pop("text", "")
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                rtl_text = source_records.get("historical_lane_phy_rtl", {}).pop("text", "")
                old_break = "if not next_identities:\n                                break"
                append_error(errors, wrapper_text.count(old_break) == 1, "historical r6 wrapper does not bind the exact identity-query exit-race break")
                append_error(errors, "process_identity_query_transient_errors" not in wrapper_text, "historical r6 wrapper unexpectedly contains the post-fix terminal-empty provenance")
                append_error(errors, "terminal identity-race empty proof" not in wrapper_text, "historical r6 wrapper unexpectedly contains the post-fix terminal-empty proof")
                append_error(errors, "clear_scoped_per_fragment_observation" in backend_text, "historical r6 backend omits the r5 clear-scoped raw-pulse fix")
                clear_block_match = re.search(r"if \(clear_sticky\) begin(?P<body>.*?)end", rtl_text, re.DOTALL)
                clear_body = clear_block_match.group("body") if clear_block_match else ""
                append_error(errors, "tx_pulse_count <= 32'd0;" in clear_body and "rx_raw_count <= 32'd0;" in clear_body, "historical r6 lane PHY clear-sticky contract mismatch")
                historical_source_control_flow = {
                    **historical_source_control_flow,
                    "stage_wrapper": source_records.get("historical_stage_wrapper_python", {}),
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                    "wrapper_breaks_after_exhausted_identity_retry_without_final_empty_proof": old_break in wrapper_text,
                    "post_fix_terminal_empty_proof_absent": "process_identity_query_transient_errors" not in wrapper_text,
                    "r5_clear_scoped_backend_fix_present": "clear_scoped_per_fragment_observation" in backend_text,
                    "historical_exit_race_contract_mismatch_proven": (
                        old_break in wrapper_text
                        and "process_identity_query_transient_errors" not in wrapper_text
                    ),
                }
            elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED:
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(
                        f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes
                    ).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"historical r7 frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(
                            ["git", "show", f"{source}:{relative}"],
                            cwd=evidence.repo_root,
                            capture_output=True,
                            timeout=30,
                            check=False,
                        )
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read historical r7 source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"historical r7 frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"historical r7 frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {
                        "path": str(frozen_source),
                        "git_blob_sha1": computed_blob,
                        "sha256": hashlib.sha256(frozen_bytes).hexdigest(),
                        "size_bytes": len(frozen_bytes),
                        "text": source_text,
                    }
                wrapper_text = source_records.get("historical_stage_wrapper_python", {}).pop("text", "")
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                rtl_text = source_records.get("historical_lane_phy_rtl", {}).pop("text", "")
                clear_block_match = re.search(r"if \(clear_sticky\) begin(?P<body>.*?)end", rtl_text, re.DOTALL)
                clear_body = clear_block_match.group("body") if clear_block_match else ""
                append_error(errors, "process_identity_query_transient_errors" in wrapper_text and "terminal identity-race empty proof" in wrapper_text, "historical r7 wrapper omits the r6 terminal-empty fix")
                append_error(errors, "clear_scoped_per_fragment_observation" in backend_text, "historical r7 backend omits the r5 clear-scoped raw-pulse fix")
                append_error(errors, "tx_pulse_count <= 32'd0;" in clear_body and "rx_raw_count <= 32'd0;" in clear_body, "historical r7 lane PHY clear-sticky contract mismatch")
                historical_source_control_flow = {
                    **historical_source_control_flow,
                    "stage_wrapper": source_records.get("historical_stage_wrapper_python", {}),
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                    "r6_terminal_empty_fix_present": (
                        "process_identity_query_transient_errors" in wrapper_text
                        and "terminal identity-race empty proof" in wrapper_text
                    ),
                    "r5_clear_scoped_backend_fix_present": "clear_scoped_per_fragment_observation" in backend_text,
                }
            elif historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED:
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"historical r8 frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(["git", "show", f"{source}:{relative}"], cwd=evidence.repo_root, capture_output=True, timeout=30, check=False)
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read historical r8 source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"historical r8 frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"historical r8 frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {"path": str(frozen_source), "git_blob_sha1": computed_blob, "sha256": hashlib.sha256(frozen_bytes).hexdigest(), "size_bytes": len(frozen_bytes), "text": source_text}
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                old_clear_scope = 'for name in ("RAW_TX_PULSES", "RAW_RX_PULSES"):'
                old_frame_exact = '"FRAME_GOOD": 1,'
                old_ack_exact = '"ACK_SENT": 1,'
                append_error(errors, backend_text.count(old_clear_scope) == 2 and backend_text.count(old_frame_exact) == 1 and backend_text.count(old_ack_exact) == 1, "historical r8 backend does not bind the exact retry-semantics mismatch")
                append_error(errors, "P6_MAX_RETRY_PER_FRAGMENT" not in backend_text, "historical r8 backend unexpectedly contains the retry-semantics fix")
                try:
                    engine = subprocess.run(["git", "show", f"{source}:rtl/p6_dynamic_transport_engine.sv"], cwd=evidence.repo_root, text=True, capture_output=True, timeout=30, check=False)
                except (OSError, subprocess.SubprocessError) as exc:
                    errors.append(f"unable to read historical r8 transport engine: {exc}")
                    engine_text = ""
                else:
                    append_error(errors, engine.returncode == 0, "historical r8 transport engine is absent from source commit")
                    engine_text = engine.stdout if engine.returncode == 0 else ""
                clear_bodies = re.findall(r"if \(clear_pulse\) begin(?P<body>.*?)end", engine_text, re.DOTALL)
                retry_clear_scoped = any("retry_count <= 32'd0;" in body for body in clear_bodies)
                append_error(errors, retry_clear_scoped, "historical r8 RTL does not prove RETRY_COUNT is clear-scoped")
                historical_source_control_flow = {
                    **historical_source_control_flow,
                    "stage_wrapper": source_records.get("historical_stage_wrapper_python", {}),
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                    "backend_treats_retry_count_as_cumulative": old_clear_scope in backend_text,
                    "backend_requires_frame_and_ack_sent_delta_one": old_frame_exact in backend_text and old_ack_exact in backend_text,
                    "rtl_clear_pulse_resets_retry_count": retry_clear_scoped,
                    "historical_retry_contract_mismatch_proven": old_clear_scope in backend_text and old_frame_exact in backend_text and old_ack_exact in backend_text and retry_clear_scoped,
                }
            elif historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE:
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"historical r9 frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(["git", "show", f"{source}:{relative}"], cwd=evidence.repo_root, capture_output=True, timeout=30, check=False)
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read historical r9 source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"historical r9 frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"historical r9 frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {"path": str(frozen_source), "git_blob_sha1": computed_blob, "sha256": hashlib.sha256(frozen_bytes).hexdigest(), "size_bytes": len(frozen_bytes), "text": source_text}
                wrapper_text = source_records.get("historical_stage_wrapper_python", {}).pop("text", "")
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                rtl_text = source_records.get("historical_lane_phy_rtl", {}).pop("text", "")
                append_error(errors, "process_identity_query_transient_errors" in wrapper_text and "terminal identity-race empty proof" in wrapper_text, "historical r9 wrapper omits terminal-empty helper proof")
                append_error(errors, "P6_MAX_RETRY_PER_FRAGMENT = 3" in backend_text and "retry_count_delta" in backend_text, "historical r9 backend omits bounded retry semantics")
                clear_block_match = re.search(r"if \(clear_sticky\) begin(?P<body>.*?)end", rtl_text, re.DOTALL)
                clear_body = clear_block_match.group("body") if clear_block_match else ""
                append_error(errors, "tx_pulse_count <= 32'd0;" in clear_body and "rx_raw_count <= 32'd0;" in clear_body, "historical r9 lane PHY clear-sticky contract mismatch")
                historical_source_control_flow = {
                    **historical_source_control_flow,
                    "stage_wrapper": source_records.get("historical_stage_wrapper_python", {}),
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                    "terminal_empty_fix_present": "process_identity_query_transient_errors" in wrapper_text and "terminal identity-race empty proof" in wrapper_text,
                    "bounded_retry_semantics_present": "P6_MAX_RETRY_PER_FRAGMENT = 3" in backend_text and "retry_count_delta" in backend_text,
                    "raw_pulse_clear_scope_present": "tx_pulse_count <= 32'd0;" in clear_body and "rx_raw_count <= 32'd0;" in clear_body,
                }
            elif historical_variant in {
                HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
            }:
                source_label = (
                    "historical r14"
                    if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
                    else "historical r15"
                )
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"{source_label} frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(["git", "show", f"{source}:{relative}"], cwd=evidence.repo_root, capture_output=True, timeout=30, check=False)
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read {source_label} source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"{source_label} frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"{source_label} frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {"path": str(frozen_source), "git_blob_sha1": computed_blob, "sha256": hashlib.sha256(frozen_bytes).hexdigest(), "size_bytes": len(frozen_bytes), "text": source_text}
                wrapper_text = source_records.get("historical_stage_wrapper_python", {}).pop("text", "")
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                rtl_text = source_records.get("historical_lane_phy_rtl", {}).pop("text", "")
                append_error(errors, "P6_MAX_RETRY_PER_FRAGMENT = 3" in backend_text and "retry_count_delta" in backend_text, f"{source_label} backend omits bounded retry semantics")
                clear_block_match = re.search(r"if \(clear_sticky\) begin(?P<body>.*?)end", rtl_text, re.DOTALL)
                clear_body = clear_block_match.group("body") if clear_block_match else ""
                append_error(errors, "tx_pulse_count <= 32'd0;" in clear_body and "rx_raw_count <= 32'd0;" in clear_body, f"{source_label} lane PHY clear-sticky contract mismatch")
                queue_run_count = historical_tcl_text.count("run_hw_axi -queue")
                queued_control_guard_absent = "if {$offset == 0x100} {" not in historical_tcl_text
                append_error(errors, historical_tcl_text.count("-burst INCR") == 2 and queue_run_count == 2, f"{source_label} Tcl does not bind AXI4 bursts plus queued singles")
                append_error(errors, "axi4_incr_burst_count" in wrapper_text and "queued_single_run_hw_axi_call_count" in wrapper_text, f"{source_label} wrapper omits AXI4/queued metrics")
                if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED:
                    append_error(errors, queued_control_guard_absent, f"{source_label} Tcl unexpectedly contains the ordered P6_CTRL fix")
                    append_error(errors, "ordered_control_write_run_hw_axi_call_count" not in wrapper_text, f"{source_label} wrapper unexpectedly contains ordered-control metrics")
                else:
                    append_error(errors, not queued_control_guard_absent, f"{source_label} Tcl omits the ordered P6_CTRL fix")
                    append_error(errors, "ordered_control_write_run_hw_axi_call_count" in wrapper_text and "queued_control_write_transaction_count" in wrapper_text, f"{source_label} wrapper omits ordered-control metrics")
                    append_error(errors, "lreverse $encoded" not in historical_tcl_text, f"{source_label} Tcl unexpectedly contains the burst write word-order fix")
                    append_error(errors, "$count - 1 - $index" not in historical_tcl_text, f"{source_label} Tcl unexpectedly contains the burst read word-order fix")
                try:
                    old_build_tcl = subprocess.run(["git", "show", f"{source}:scripts/build_p6_jtag_candidate.tcl"], cwd=evidence.repo_root, text=True, capture_output=True, timeout=30, check=False)
                    old_top_rtl = subprocess.run(["git", "show", f"{source}:rtl/p6_jtag_top.sv"], cwd=evidence.repo_root, text=True, capture_output=True, timeout=30, check=False)
                except (OSError, subprocess.SubprocessError) as exc:
                    errors.append(f"unable to read {source_label} AXI4/converter source: {exc}")
                    old_build_text = ""
                    old_top_text = ""
                else:
                    append_error(errors, old_build_tcl.returncode == 0 and old_top_rtl.returncode == 0, f"{source_label} AXI4/converter source is absent from source commit")
                    old_build_text = old_build_tcl.stdout if old_build_tcl.returncode == 0 else ""
                    old_top_text = old_top_rtl.stdout if old_top_rtl.returncode == 0 else ""
                full_axi4_converter = (
                    "CONFIG.PROTOCOL {0}" in old_build_text
                    and "CONFIG.RD_TXN_QUEUE_LENGTH {16}" in old_build_text
                    and "CONFIG.WR_TXN_QUEUE_LENGTH {16}" in old_build_text
                    and "create_ip -name axi_protocol_converter" in old_build_text
                    and "CONFIG.SI_PROTOCOL {AXI4}" in old_build_text
                    and "CONFIG.MI_PROTOCOL {AXI4LITE}" in old_build_text
                    and "j_axi_awlen" in old_top_text
                    and "j_axi_arlen" in old_top_text
                    and "p6_axi_protocol_converter" in old_top_text
                )
                append_error(errors, full_axi4_converter, f"{source_label} source does not bind full AXI4 through the AXI4-Lite converter")
                historical_source_control_flow = {
                    **historical_source_control_flow,
                    "stage_wrapper": source_records.get("historical_stage_wrapper_python", {}),
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                    "tcl_axi4_incr_burst_option_count": historical_tcl_text.count("-burst INCR"),
                    "tcl_queued_single_word_run_count": queue_run_count,
                    "tcl_ordered_control_guard_absent": queued_control_guard_absent,
                    "wrapper_axi4_and_queue_metrics_present": "axi4_incr_burst_count" in wrapper_text and "queued_single_run_hw_axi_call_count" in wrapper_text,
                    "source_commit_full_axi4_converter_present": full_axi4_converter,
                    **(
                        {
                            "historical_queued_control_order_mismatch_proven": full_axi4_converter
                            and queue_run_count == 2
                            and queued_control_guard_absent,
                        }
                        if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
                        else {
                            "tcl_ordered_control_guard_present": not queued_control_guard_absent,
                            "tcl_burst_write_word_order_fix_absent": "lreverse $encoded" not in historical_tcl_text,
                            "tcl_burst_read_word_order_fix_absent": "$count - 1 - $index" not in historical_tcl_text,
                            "historical_burst_word_order_mismatch_proven": full_axi4_converter
                            and queue_run_count == 2
                            and not queued_control_guard_absent
                            and "lreverse $encoded" not in historical_tcl_text
                            and "$count - 1 - $index" not in historical_tcl_text,
                        }
                    ),
                }
            elif historical_variant in {
                HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
            }:
                source_label = (
                    "historical r11"
                    if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
                    else "historical r12"
                    if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
                    else "historical r13"
                )
                source_records: dict[str, dict[str, Any]] = {}
                for role, relative in (
                    ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                    ("historical_backend_python", "tools/p7_jtag_backend.py"),
                    ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
                ):
                    frozen_source = role_paths[role]
                    frozen_bytes = frozen_source.read_bytes()
                    computed_blob = hashlib.sha1(f"blob {len(frozen_bytes)}\0".encode("ascii") + frozen_bytes).hexdigest()
                    recorded_blob = str(frozen_records[role].get("git_blob_sha1", "")).lower()
                    append_error(errors, computed_blob == recorded_blob, f"{source_label} frozen source Git blob mismatch: {role}")
                    try:
                        committed_source = subprocess.run(["git", "show", f"{source}:{relative}"], cwd=evidence.repo_root, capture_output=True, timeout=30, check=False)
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read {source_label} source {relative}: {exc}")
                    else:
                        append_error(errors, committed_source.returncode == 0 and committed_source.stdout == frozen_bytes, f"{source_label} frozen source differs from source commit: {role}")
                    try:
                        source_text = frozen_bytes.decode("utf-8", errors="strict")
                    except UnicodeError as exc:
                        errors.append(f"{source_label} frozen source is not strict UTF-8 ({role}): {exc}")
                        source_text = ""
                    source_records[role] = {"path": str(frozen_source), "git_blob_sha1": computed_blob, "sha256": hashlib.sha256(frozen_bytes).hexdigest(), "size_bytes": len(frozen_bytes), "text": source_text}
                wrapper_text = source_records.get("historical_stage_wrapper_python", {}).pop("text", "")
                backend_text = source_records.get("historical_backend_python", {}).pop("text", "")
                rtl_text = source_records.get("historical_lane_phy_rtl", {}).pop("text", "")
                append_error(errors, "P6_MAX_RETRY_PER_FRAGMENT = 3" in backend_text and "retry_count_delta" in backend_text, f"{source_label} backend omits bounded retry semantics")
                clear_block_match = re.search(r"if \(clear_sticky\) begin(?P<body>.*?)end", rtl_text, re.DOTALL)
                clear_body = clear_block_match.group("body") if clear_block_match else ""
                append_error(errors, "tx_pulse_count <= 32'd0;" in clear_body and "rx_raw_count <= 32'd0;" in clear_body, f"{source_label} lane PHY clear-sticky contract mismatch")
                common_source_control = {
                    **historical_source_control_flow,
                    "stage_wrapper": source_records.get("historical_stage_wrapper_python", {}),
                    "backend": source_records.get("historical_backend_python", {}),
                    "lane_phy_rtl": source_records.get("historical_lane_phy_rtl", {}),
                }
                if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED:
                    old_burst_write = "proc p7_axi_write_burst"
                    old_burst_read = "proc p7_axi_read_burst"
                    old_burst_option_count = historical_tcl_text.count("-burst INCR")
                    append_error(errors, historical_tcl_text.count(old_burst_write) == 1 and historical_tcl_text.count(old_burst_read) == 1 and old_burst_option_count == 2, "historical r11 Tcl does not bind the rejected two-burst implementation")
                    append_error(errors, "p7_axi_write_batch" not in historical_tcl_text and "AXI4-Lite write batch" not in historical_tcl_text, "historical r11 Tcl unexpectedly contains the post-fix AXI4-Lite batch implementation")
                    append_error(errors, "coalesced_hw_axi_transaction_count" in wrapper_text and "burst_group_count" in wrapper_text, "historical r11 wrapper does not bind the misleading burst dry metrics")
                    append_error(errors, "minimum_single_word_axi4lite_transaction_count" not in wrapper_text, "historical r11 wrapper unexpectedly contains the post-fix AXI4-Lite metrics")
                    historical_source_control_flow = {
                        **common_source_control,
                        "tcl_multiword_incr_burst_count": old_burst_option_count,
                        "tcl_post_fix_axi4lite_batch_absent": "p7_axi_write_batch" not in historical_tcl_text,
                        "wrapper_old_burst_metrics_present": "coalesced_hw_axi_transaction_count" in wrapper_text,
                        "wrapper_post_fix_axi4lite_metrics_absent": "minimum_single_word_axi4lite_transaction_count" not in wrapper_text,
                        "historical_axi4lite_contract_mismatch_proven": old_burst_option_count == 2 and "p7_axi_write_batch" not in historical_tcl_text,
                    }
                else:
                    queue_run_count = historical_tcl_text.count("run_hw_axi -queue")
                    append_error(errors, historical_tcl_text.count("proc p7_axi_write_batch") == 1 and historical_tcl_text.count("proc p7_axi_read_batch") == 1 and queue_run_count == 2, f"{source_label} Tcl does not bind the two queued single-word batch paths")
                    append_error(errors, "-burst INCR" not in historical_tcl_text and historical_tcl_text.count("-len 1 -force") >= 4, f"{source_label} Tcl does not prove LEN=1 without AXI bursts")
                    append_error(errors, "minimum_single_word_axi4lite_transaction_count" in wrapper_text and "max_batch_transactions" in wrapper_text, f"{source_label} wrapper omits the queued-single dry metrics")
                    append_error(errors, "coalesced_hw_axi_transaction_count" not in wrapper_text and "burst_group_count" not in wrapper_text, f"{source_label} wrapper retains rejected burst metrics")
                    try:
                        old_ip_props = subprocess.run(
                            ["git", "show", f"{source}:evidence/generated/vivado/p6_ip_inspect/jtag_axi_properties.txt"],
                            cwd=evidence.repo_root,
                            text=True,
                            capture_output=True,
                            timeout=30,
                            check=False,
                        )
                        old_build_tcl = subprocess.run(
                            ["git", "show", f"{source}:scripts/build_p6_jtag_candidate.tcl"],
                            cwd=evidence.repo_root,
                            text=True,
                            capture_output=True,
                            timeout=30,
                            check=False,
                        )
                    except (OSError, subprocess.SubprocessError) as exc:
                        errors.append(f"unable to read {source_label} JTAG_AXI build configuration: {exc}")
                        old_ip_text = ""
                        old_build_text = ""
                    else:
                        append_error(errors, old_ip_props.returncode == 0 and old_build_tcl.returncode == 0, f"{source_label} JTAG_AXI build configuration is absent from the source commit")
                        old_ip_text = old_ip_props.stdout if old_ip_props.returncode == 0 else ""
                        old_build_text = old_build_tcl.stdout if old_build_tcl.returncode == 0 else ""
                    queue_depth_one = "CONFIG.RD_TXN_QUEUE_LENGTH=1" in old_ip_text and "CONFIG.WR_TXN_QUEUE_LENGTH=1" in old_ip_text
                    queue_depth_not_overridden = "CONFIG.RD_TXN_QUEUE_LENGTH" not in old_build_text and "CONFIG.WR_TXN_QUEUE_LENGTH" not in old_build_text
                    queue_depth_sixteen = "CONFIG.RD_TXN_QUEUE_LENGTH=16" in old_ip_text and "CONFIG.WR_TXN_QUEUE_LENGTH=16" in old_ip_text
                    queue_depth_overridden_sixteen = "CONFIG.RD_TXN_QUEUE_LENGTH {16}" in old_build_text and "CONFIG.WR_TXN_QUEUE_LENGTH {16}" in old_build_text
                    if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED:
                        append_error(errors, queue_depth_one, "historical r12 source does not prove JTAG_AXI read/write queue depth one")
                        append_error(errors, queue_depth_not_overridden, "historical r12 build Tcl unexpectedly overrides the queue-depth-one default")
                    else:
                        append_error(errors, queue_depth_sixteen, "historical r13 source does not prove JTAG_AXI read/write queue depth sixteen")
                        append_error(errors, queue_depth_overridden_sixteen, "historical r13 build Tcl does not bind queue depth sixteen")
                    historical_source_control_flow = {
                        **common_source_control,
                        "tcl_queued_single_word_run_count": queue_run_count,
                        "tcl_len_one_without_burst": "-burst INCR" not in historical_tcl_text,
                        "wrapper_queued_single_metrics_present": "minimum_single_word_axi4lite_transaction_count" in wrapper_text,
                        "source_commit_ip_read_queue_length": 16 if queue_depth_sixteen else 1 if queue_depth_one else None,
                        "source_commit_ip_write_queue_length": 16 if queue_depth_sixteen else 1 if queue_depth_one else None,
                        "source_commit_build_queue_override_absent": queue_depth_not_overridden,
                        "source_commit_build_queue_override_sixteen": queue_depth_overridden_sixteen,
                        "historical_queue_contract_mismatch_proven": historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED and queue_run_count == 2 and queue_depth_one and queue_depth_not_overridden,
                        "historical_queue_timeout_configuration_proven": historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT and queue_run_count == 2 and queue_depth_sixteen and queue_depth_overridden_sixteen,
                    }
        try:
            old_offline = json.loads(role_paths["offline_checkpoint"].read_text(encoding="utf-8", errors="strict"))
            old_plan = json.loads(role_paths["sequence_plan"].read_text(encoding="utf-8", errors="strict"))
            generation = json.loads(role_paths["generation_manifest"].read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"historical frozen JSON input invalid: {exc}")
        else:
            append_error(errors, isinstance(old_offline, dict) and old_offline.get("P7_OFFLINE_GATE") == "PASS", "historical frozen offline checkpoint is not PASS")
            append_error(errors, str(old_offline.get("source_commit", "")).lower() == source, "historical frozen offline checkpoint source mismatch")
            append_error(errors, old_offline.get("hardware_actions_executed") is False and old_offline.get("NO_HARDWARE_ACTIONS_EXECUTED") is True, "historical frozen offline checkpoint violates no-hardware boundary")
            old_hashes = old_offline.get("checkpoint_input_hashes")
            append_error(errors, isinstance(old_hashes, dict), "historical frozen offline checkpoint input hashes missing")
            if isinstance(old_hashes, dict):
                append_error(errors, old_offline.get("checkpoint_input_count") == len(old_hashes), "historical frozen offline checkpoint input count mismatch")
                append_error(errors, set(HISTORICAL_GIT_CRITICAL_SOURCES) <= set(old_hashes), "historical frozen offline checkpoint omits critical Git-bound sources")
            tree_digest = str(old_offline.get("source_tree_listing_sha256", "")).lower()
            append_error(errors, SHA256_RE.fullmatch(tree_digest) is not None, "historical frozen offline checkpoint tree digest malformed")
            if not (evidence.repo_root / ".git").exists():
                errors.append("Git metadata unavailable; cannot validate historical checkpoint tree/blobs")
            elif COMMIT_RE.fullmatch(source):
                try:
                    tree = subprocess.run(
                        ["git", "ls-tree", "-r", "--full-tree", source],
                        cwd=evidence.repo_root,
                        text=True,
                        capture_output=True,
                        timeout=30,
                        check=False,
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    errors.append(f"unable to recompute historical source tree listing: {exc}")
                else:
                    append_error(errors, tree.returncode == 0, "unable to read historical source tree listing")
                    if tree.returncode == 0 and SHA256_RE.fullmatch(tree_digest):
                        append_error(errors, hashlib.sha256(tree.stdout.encode("utf-8")).hexdigest() == tree_digest, "historical frozen offline checkpoint tree digest mismatch")
                if isinstance(old_hashes, dict):
                    for relative in HISTORICAL_GIT_CRITICAL_SOURCES:
                        expected_blob_sha = str(old_hashes.get(relative, "")).lower()
                        append_error(errors, SHA256_RE.fullmatch(expected_blob_sha) is not None, f"historical old checkpoint Git blob hash malformed: {relative}")
                        try:
                            blob = subprocess.run(
                                ["git", "show", f"{source}:{relative}"],
                                cwd=evidence.repo_root,
                                capture_output=True,
                                timeout=30,
                                check=False,
                            )
                        except (OSError, subprocess.SubprocessError) as exc:
                            errors.append(f"unable to read historical Git blob {relative}: {exc}")
                            continue
                        append_error(errors, blob.returncode == 0, f"historical critical source absent from old commit: {relative}")
                        if blob.returncode == 0 and SHA256_RE.fullmatch(expected_blob_sha):
                            append_error(errors, hashlib.sha256(blob.stdout).hexdigest() == expected_blob_sha, f"historical old checkpoint Git blob hash mismatch: {relative}")
                preflight_tcl_sha = str(candidate.data.get("safety_validation", {}).get("preflight_tcl_sha256", "")).lower()
                append_error(errors, SHA256_RE.fullmatch(preflight_tcl_sha) is not None, "historical preflight Tcl SHA256 missing/malformed")
                append_error(errors, isinstance(old_hashes, dict) and preflight_tcl_sha == str(old_hashes.get("scripts/hw/p7_hw_preflight.tcl", "")).lower(), "historical preflight Tcl hash does not bind old checkpoint/Git blob")
            append_error(errors, isinstance(old_plan, dict) and old_plan.get("schema") == "rf-comm-p7-hardware-sequence-plan-v1", "historical frozen sequence plan schema mismatch")
            append_error(errors, str(old_plan.get("source_commit", "")).lower() == source, "historical frozen sequence plan source mismatch")
            diagnostic_variant = historical_variant in {
                HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
                HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
                HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
            }
            expected_plan_count = 15 if diagnostic_variant else 66
            append_error(errors, isinstance(old_plan.get("stages"), list) and len(old_plan.get("stages", [])) == expected_plan_count, "historical frozen sequence plan stage count mismatch")
            if diagnostic_variant:
                diagnostic_label = (
                    "historical r10"
                    if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT
                    else "historical r13"
                    if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
                    else "historical r11"
                    if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
                    else "historical r12"
                    if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
                    else "historical r14"
                    if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
                    else "historical r15"
                )
                append_error(errors, old_plan.get("plan_mode") == "DIAGNOSTIC_SUFFIX_55" and old_plan.get("coverage_claimed") is False and old_plan.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", f"{diagnostic_label} frozen sequence plan diagnostic boundary mismatch")
                append_error(errors, old_plan.get("full_stage_ordinals") == [1, 2, 3, 4, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65], f"{diagnostic_label} frozen sequence plan ordinal matrix mismatch")
                append_error(errors, not any(isinstance(item, dict) and item.get("group") == "ps_stationary" for item in old_plan.get("stages", [])), f"{diagnostic_label} frozen sequence plan contains stationary")
            old_stages = old_plan.get("stages") if isinstance(old_plan.get("stages"), list) else []
            first_stage = old_stages[0] if old_stages and isinstance(old_stages[0], dict) else {}
            append_error(
                errors,
                first_stage.get("id") == "p7_safe_idle"
                and first_stage.get("group") == "safe_idle"
                and first_stage.get("risk_index") == 10
                and first_stage.get("case") == {},
                "historical frozen sequence plan first stage is not the exact safe-idle risk-10 case",
            )
            if failed_stage_index == 1:
                append_error(errors, first_stage.get("command") == attempts[0].get("command"), "historical r5 frozen sequence plan safe-idle command does not bind PASS prefix")
                prefix_summary = resolve_reference(first_stage.get("summary_path"), document=role_paths["sequence_plan"], repo_root=evidence.repo_root)
                append_error(errors, prefix_summary == (epoch_root / "001_p7_safe_idle/p7_jtag_axi_stage_summary.json").resolve(strict=False), "historical r5 frozen sequence plan safe-idle summary path mismatch")
            planned_stage = old_stages[failed_stage_index] if len(old_stages) > failed_stage_index and isinstance(old_stages[failed_stage_index], dict) else {}
            append_error(errors, planned_stage.get("id") == candidate.data.get("stage_name") and planned_stage.get("group") == expected_group and planned_stage.get("risk_index") == expected_risk, "historical frozen sequence plan failed-stage identity mismatch")
            append_error(errors, planned_stage.get("command") == attempt.get("command"), "historical frozen sequence plan command does not bind outer attempt")
            append_error(
                errors,
                resolve_reference(planned_stage.get("summary_path"), document=role_paths["sequence_plan"], repo_root=evidence.repo_root)
                == candidate.path.resolve(strict=False),
                "historical frozen sequence plan summary path does not bind diagnostic summary",
            )
            first_command = planned_stage.get("command") if isinstance(planned_stage.get("command"), list) else []

            def argv_value(flag: str) -> str | None:
                indices = [index for index, item in enumerate(first_command) if item == flag]
                if len(indices) != 1 or indices[0] + 1 >= len(first_command):
                    return None
                return str(first_command[indices[0] + 1])

            append_error(errors, argv_value("--source-commit") == source, "historical frozen sequence plan command source mismatch")
            append_error(errors, argv_value("--authorization-sha256") == frozen_records["stage_authorization"]["frozen_file"]["sha256"], "historical frozen sequence plan command authorization SHA mismatch")
            append_error(errors, argv_value("--transaction-sha256") == frozen_records["stage_transactions"]["frozen_file"]["sha256"], "historical frozen sequence plan command transaction SHA mismatch")
            if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED:
                append_error(errors, argv_value("--shutdown-timeout-sec") == "30", "historical r7 failed stage does not bind the undersized 30-second shutdown timeout")
                append_error(errors, argv_value("--max-runtime-sec") == "900", "historical r7 failed stage max runtime mismatch")
            if historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED:
                append_error(errors, argv_value("--shutdown-timeout-sec") == "60", "historical r8 failed stage shutdown timeout mismatch")
                append_error(errors, argv_value("--max-runtime-sec") == "960", "historical r8 failed stage max runtime mismatch")
            if historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE:
                append_error(errors, argv_value("--shutdown-timeout-sec") == "60", "historical r9 failed stage shutdown timeout mismatch")
                append_error(errors, argv_value("--max-runtime-sec") == "960", "historical r9 failed stage max runtime mismatch")
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT:
                append_error(errors, argv_value("--shutdown-timeout-sec") == "60", "historical r10 failed stage shutdown timeout mismatch")
                append_error(errors, argv_value("--stage-timeout-sec") == "1400", "historical r10 failed stage candidate timeout mismatch")
                append_error(errors, argv_value("--max-runtime-sec") == "1800", "historical r10 failed stage max runtime mismatch")
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT:
                append_error(errors, argv_value("--shutdown-timeout-sec") == "60", "historical r13 failed stage shutdown timeout mismatch")
                append_error(errors, argv_value("--stage-timeout-sec") == "1400", "historical r13 failed stage candidate timeout mismatch")
                append_error(errors, argv_value("--max-runtime-sec") == "1800", "historical r13 failed stage max runtime mismatch")
            if historical_variant in {
                HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
            }:
                queue_label = (
                    "historical r11"
                    if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
                    else "historical r12"
                    if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
                    else "historical r14"
                    if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
                    else "historical r15"
                )
                append_error(errors, argv_value("--shutdown-timeout-sec") == "60", f"{queue_label} failed stage shutdown timeout mismatch")
                append_error(errors, argv_value("--stage-timeout-sec") == "550", f"{queue_label} failed stage candidate timeout mismatch")
                append_error(errors, argv_value("--max-runtime-sec") == "960", f"{queue_label} failed stage max runtime mismatch")
            append_error(
                errors,
                _same_registered_worktree_location(
                    resolve_reference(argv_value("--authorization-file"), document=role_paths["sequence_plan"], repo_root=evidence.repo_root),
                    Path(frozen_records["stage_authorization"]["original_resolved_path"]),
                    evidence.repo_root,
                ),
                "historical frozen sequence plan command authorization path mismatch",
            )
            append_error(
                errors,
                _same_registered_worktree_location(
                    resolve_reference(argv_value("--transaction-file"), document=role_paths["sequence_plan"], repo_root=evidence.repo_root),
                    Path(frozen_records["stage_transactions"]["original_resolved_path"]),
                    evidence.repo_root,
                ),
                "historical frozen sequence plan command transaction path mismatch",
            )
            append_error(
                errors,
                resolve_reference(argv_value("--evidence-dir"), document=role_paths["sequence_plan"], repo_root=evidence.repo_root)
                == candidate.path.parent.resolve(strict=False),
                "historical frozen sequence plan command evidence directory mismatch",
            )
            append_error(errors, isinstance(generation, dict) and generation.get("schema") == "rf-comm-p7-authorized-sequence-generator-v1", "historical frozen generation manifest schema mismatch")
            append_error(errors, str(generation.get("source_commit", "")).lower() == source, "historical frozen generation manifest source mismatch")
            generation_offline = generation.get("offline_checkpoint") if isinstance(generation.get("offline_checkpoint"), dict) else {}
            append_error(errors, str(generation_offline.get("sha256", "")).lower() == frozen_records["offline_checkpoint"]["frozen_file"]["sha256"], "historical frozen generation manifest offline checkpoint mismatch")
            generation_plan = generation.get("sequence_plan") if isinstance(generation.get("sequence_plan"), dict) else {}
            append_error(errors, str(generation_plan.get("sha256", "")).lower() == frozen_records["sequence_plan"]["frozen_file"]["sha256"], "historical frozen generation manifest sequence-plan SHA mismatch")
            append_error(errors, generation_plan.get("stage_count") == (15 if diagnostic_variant else 66), "historical frozen generation manifest sequence-plan stage count mismatch")
            if diagnostic_variant:
                diagnostic_label = (
                    "historical r10" if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT
                    else "historical r13" if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
                    else "historical r11" if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
                    else "historical r12" if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
                    else "historical r14" if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
                    else "historical r15"
                )
                append_error(errors, generation.get("plan_mode") == "DIAGNOSTIC_SUFFIX_55" and generation.get("coverage_claimed") is False and generation.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", f"{diagnostic_label} frozen generation manifest diagnostic boundary mismatch")
                append_error(errors, generation.get("full_stage_ordinals") == [1, 2, 3, 4, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65], f"{diagnostic_label} frozen generation manifest ordinal matrix mismatch")
            generation_authorizations = generation.get("authorization_records")
            stage_authorizations = [
                item
                for item in generation_authorizations
                if isinstance(item, dict) and item.get("stage") == candidate.data.get("stage_name")
            ] if isinstance(generation_authorizations, list) else []
            append_error(errors, len(stage_authorizations) == 1, "historical frozen generation manifest failed-stage authorization record missing/duplicated")
            if len(stage_authorizations) == 1:
                append_error(errors, str(stage_authorizations[0].get("sha256", "")).lower() == frozen_records["stage_authorization"]["frozen_file"]["sha256"], "historical frozen generation manifest failed-stage authorization SHA mismatch")
                append_error(
                    errors,
                    _same_registered_worktree_location(
                        resolve_reference(stage_authorizations[0].get("path"), document=role_paths["generation_manifest"], repo_root=evidence.repo_root),
                        Path(frozen_records["stage_authorization"]["original_resolved_path"]),
                        evidence.repo_root,
                    ),
                    "historical frozen generation manifest failed-stage authorization path mismatch",
                )
        try:
            auth_fields, auth_markers, auth_duplicates = parse_authorization(role_paths["stage_authorization"])
        except (OSError, UnicodeError) as exc:
            errors.append(f"historical frozen stage authorization invalid: {exc}")
        else:
            append_error(errors, not auth_duplicates and "P7_STATIONARY_APP_LAYER_APPROVED" in auth_markers, "historical frozen stage authorization marker/uniqueness failure")
            append_error(errors, str(auth_fields.get("SOURCE_COMMIT", "")).lower() == source, "historical frozen stage authorization source mismatch")
            for key, expected in {
                "AUTHORIZED_STAGE": "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET",
                "USER_HARDWARE_AUTHORIZATION_FOR_P7": "GRANTED",
                "BOARD_ID": "210512180081",
                "EXPECTED_PART": "xc7z010clg400-1",
                "EXPECTED_TARGET": "localhost:3121/xilinx_tcf/Digilent/210512180081",
                "P7_JTAG_STAGE_NAME": candidate.data.get("stage_name"),
                "P7_JTAG_SEMANTIC_MODE": candidate.data.get("semantic_mode"),
            }.items():
                append_error(errors, str(auth_fields.get(key, "")).casefold() == expected.casefold(), f"historical frozen stage authorization {key} mismatch")
            safety_fields = candidate.data.get("safety_validation", {}).get("authorization_fields", {})
            append_error(errors, isinstance(safety_fields, dict) and auth_fields == {str(key): str(value) for key, value in safety_fields.items()}, "historical frozen stage authorization fields do not bind wrapper summary")
            plan_record = candidate.data.get("safety_validation", {}).get("artifacts", {}).get("plan", {})
            append_error(errors, isinstance(plan_record, dict) and str(auth_fields.get("P7_PLAN_SHA256", "")).lower() == str(plan_record.get("actual_sha256", "")).lower(), "historical frozen stage authorization plan SHA256 mismatch")
            append_error(
                errors,
                resolve_reference(auth_fields.get("P7_PLAN_PATH"), document=role_paths["stage_authorization"], repo_root=evidence.repo_root)
                == resolve_reference(plan_record.get("path") if isinstance(plan_record, dict) else None, document=candidate.path, repo_root=evidence.repo_root),
                "historical frozen stage authorization plan path mismatch",
            )
            transaction = candidate.data.get("transaction_validation")
            append_error(errors, isinstance(transaction, dict) and str(auth_fields.get("P7_JTAG_TRANSACTION_SHA256", "")).lower() == str(transaction.get("actual_sha256", "")).lower(), "historical frozen stage authorization transaction SHA256 mismatch")
            append_error(errors, isinstance(transaction, dict) and str(auth_fields.get("P7_JTAG_TRANSACTION_PATH", "")) == str(transaction.get("path", "")), "historical frozen stage authorization transaction path mismatch")
        transaction_text = marker_text(role_paths["stage_transactions"])
        transaction_lines = [line.strip() for line in transaction_text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
        append_error(errors, bool(transaction_lines) and transaction_lines[0] == "P7_JTAG_AXI_TRANSACTIONS_V1", "historical frozen transaction DSL header mismatch")
        try:
            recovery_p4_fields, recovery_p4_markers, recovery_p4_duplicates = parse_authorization(
                role_paths["recovery_p4_authorization"]
            )
        except (OSError, UnicodeError) as exc:
            errors.append(f"historical frozen P4 recovery authorization invalid: {exc}")
            recovery_p4_fields = {}
            recovery_p4_markers = []
            recovery_p4_duplicates = []
        append_error(errors, not recovery_p4_duplicates, "historical frozen P4 recovery authorization contains duplicate fields")
        append_error(
            errors,
            set(recovery_p4_markers)
            == {
                "I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.",
                "I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.",
            },
            "historical frozen P4 recovery authorization marker set mismatch",
        )
        try:
            recovery_runtime = int(recovery_p4_fields.get("MAX_RUNTIME_SEC", "0"))
        except (TypeError, ValueError):
            recovery_runtime = 0
        append_error(errors, 1 <= recovery_runtime <= 300, "historical frozen P4 recovery authorization runtime invalid")
        append_error(errors, bool(str(recovery_p4_fields.get("AUTHORIZED_BY", "")).strip()), "historical frozen P4 recovery authorization owner missing")
        append_error(errors, re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(recovery_p4_fields.get("DATE", ""))) is not None, "historical frozen P4 recovery authorization date malformed")
    else:
        recovery_p4_fields = {}

    recovery_pattern = (
        f"recovery_shutdown_after_failed_stage{recovery_failed_stage_label}_*"
        if failed_stage_variant
        else "recovery_shutdown_after_failed_preflight_*"
    )
    recovery_dirs = sorted(path for path in epoch_root.glob(recovery_pattern) if path.is_dir())
    append_error(errors, bool(recovery_dirs), "historical epoch has no shutdown recovery evidence")
    append_error(
        errors,
        isinstance(declared_recovery_dirs, list)
        and [path.name for path in recovery_dirs] == [str(item) for item in declared_recovery_dirs],
        "historical recovery directory set/order does not match its manifest declaration",
    )
    no_action_records: list[dict[str, Any]] = []
    effective_records: list[dict[str, Any]] = []
    recovery_times: list[tuple[float, float]] = []
    for recovery_dir in recovery_dirs:
        summary = recovery_dir / "program_tfdu_shutdown_safe.summary.txt"
        summary_text = marker_text(summary)
        recovery_markers, duplicates = parse_marker_text(summary_text)
        append_error(errors, summary.is_file(), f"historical recovery summary missing: {recovery_dir.name}")
        append_error(errors, not duplicates, f"historical recovery summary contains duplicate markers: {recovery_dir.name}")
        begin_match = re.search(r"^PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN\s+(.+)$", summary_text, re.MULTILINE)
        end_match = re.search(r"^PROGRAM_TFDU_SHUTDOWN_SAFE_END\s+(.+)$", summary_text, re.MULTILINE)
        begin = parse_time(begin_match.group(1).strip() if begin_match else None, float("nan"))
        end = parse_time(end_match.group(1).strip() if end_match else None, float("nan"))
        append_error(errors, begin == begin and end == end and begin <= end, f"historical recovery UTC interval invalid: {recovery_dir.name}")
        recovery_times.append((begin, end))
        file_records = {
            path.name: _hash_record(path)
            for path in sorted(recovery_dir.iterdir())
            if path.is_file()
        }
        for required in ("program_tfdu_shutdown_safe.summary.txt", "hardware_authorization.json", "hash_manifest.json", "hash_manifest.csv"):
            append_error(errors, required in file_records, f"historical recovery required file missing: {recovery_dir.name}/{required}")
        manifest_path = recovery_dir / "hash_manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"historical recovery hash manifest invalid ({recovery_dir.name}): {exc}")
            manifest = {}
        manifest_files = manifest.get("files") if isinstance(manifest, dict) else None
        if not isinstance(manifest_files, list) or not manifest_files:
            errors.append(f"historical recovery hash manifest files missing: {recovery_dir.name}")
        else:
            for item in manifest_files:
                if not isinstance(item, dict):
                    errors.append(f"historical recovery hash manifest record malformed: {recovery_dir.name}")
                    continue
                path = resolve_reference(item.get("path"), document=manifest_path, repo_root=evidence.repo_root)
                expected = str(item.get("sha256", "")).lower()
                append_error(errors, item.get("exists") is True and path is not None and path.is_file(), f"historical recovery manifest target missing: {item.get('path')}")
                append_error(errors, SHA256_RE.fullmatch(expected) is not None, f"historical recovery manifest SHA256 malformed: {item.get('path')}")
                if path is not None and path.is_file() and SHA256_RE.fullmatch(expected):
                    append_error(errors, sha256_file(path) == expected, f"historical recovery manifest target changed: {item.get('path')}")
        authorization_path = recovery_dir / "hardware_authorization.json"
        try:
            recovery_authorization = json.loads(authorization_path.read_text(encoding="utf-8", errors="strict"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"historical recovery authorization invalid ({recovery_dir.name}): {exc}")
            recovery_authorization = {}
        if not isinstance(recovery_authorization, dict):
            errors.append(f"historical recovery authorization is not an object: {recovery_dir.name}")
            recovery_authorization = {}
        recovery_status = recovery_markers.get("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS")
        r4_incomplete_no_action = (
            historical_variant == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED
            and recovery_status == "AUTHORIZATION_MISSING"
            and recovery_authorization.get("missing")
            == [
                "--max-runtime-sec",
                "--shutdown-on-exit",
                "--board-id",
                "--bitstream",
                "--bitstream-sha256",
                "--active-pinmap-hash",
                "--active-xdc-hash",
                "RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW",
            ]
        )
        r7_profile_mismatch_no_action = (
            historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED
            and recovery_status == "AUTHORIZATION_MISSING"
            and recovery_authorization.get("missing")
            == [
                "--profile-sha256 mismatch: expected dc89e18e3c4f4d8a14cba63d8c6c5970aa632e8f6837a3e0e6e86345ea2f80e1, got dc89e84036847bcb865937bb3df3d1b3df7b027ec97ec31f433fe4d53aa89fe3"
            ]
        )
        canonical_profile = (evidence.repo_root / "config/profiles/G1_LANE0_BASELINE.json").resolve(strict=False)
        canonical_shutdown_tcl = (evidence.repo_root / "scripts/legacy_safe_tools/program_tfdu_shutdown.tcl").resolve(strict=False)
        canonical_shutdown_bit = (evidence.repo_root / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit").resolve(strict=False)
        canonical_pinmap = (evidence.repo_root / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv").resolve(strict=False)
        canonical_xdc = (evidence.repo_root / "constraints/active/PORT1.generated.xdc").resolve(strict=False)
        for label, path, summary_path_key, summary_sha_key in (
            ("profile", canonical_profile, "PROFILE_PATH", "PROFILE_SHA256"),
            ("shutdown Tcl", canonical_shutdown_tcl, "SHUTDOWN_TCL", "SHUTDOWN_TCL_SHA256"),
            ("shutdown bitstream", canonical_shutdown_bit, "SHUTDOWN_BITSTREAM", "SHUTDOWN_BITSTREAM_SHA256"),
        ):
            append_error(errors, path.is_file(), f"historical recovery canonical {label} missing")
            summary_bound = resolve_reference(recovery_markers.get(summary_path_key), document=summary, repo_root=evidence.repo_root)
            append_error(errors, summary_bound == path, f"historical recovery summary {label} path mismatch")
            expected_sha = str(recovery_markers.get(summary_sha_key, "")).lower()
            append_error(errors, SHA256_RE.fullmatch(expected_sha) is not None, f"historical recovery summary {label} SHA256 malformed")
            if path.is_file() and SHA256_RE.fullmatch(expected_sha):
                append_error(errors, sha256_file(path) == expected_sha, f"historical recovery summary {label} SHA256 mismatch")
        append_error(errors, resolve_reference(recovery_markers.get("HASH_MANIFEST_JSON"), document=summary, repo_root=evidence.repo_root) == manifest_path.resolve(strict=False), "historical recovery summary JSON-manifest path mismatch")
        append_error(errors, resolve_reference(recovery_markers.get("HASH_MANIFEST_CSV"), document=summary, repo_root=evidence.repo_root) == (recovery_dir / "hash_manifest.csv").resolve(strict=False), "historical recovery summary CSV-manifest path mismatch")
        append_error(errors, resolve_reference(recovery_markers.get("HARDWARE_AUTHORIZATION_LOG"), document=summary, repo_root=evidence.repo_root) == authorization_path.resolve(strict=False), "historical recovery summary authorization path mismatch")
        append_error(
            errors,
            str(recovery_authorization.get("BOARD_ID", ""))
            == ("MISSING" if r4_incomplete_no_action else "210512180081"),
            "historical recovery authorization board mismatch",
        )
        append_error(errors, recovery_authorization.get("ABORT_FILE_PRESENT") is False, "historical recovery authorization reports abort file")
        recovery_p4_sha = (
            frozen_records.get("recovery_p4_authorization", {})
            .get("frozen_file", {})
            .get("sha256", "")
        )
        append_error(errors, str(recovery_authorization.get("AUTHORIZATION_FILE_SHA256", "")).lower() == recovery_p4_sha, "historical recovery authorization does not bind frozen P4 authorization")
        append_error(errors, recovery_authorization.get("AUTHORIZATION_FILE_EXISTS") is True, "historical recovery authorization file-exists fact is not true")
        append_error(errors, recovery_authorization.get("AUTHORIZATION_FIELDS") == recovery_p4_fields, "historical recovery authorization fields do not match frozen P4 authorization")
        recovery_authorization_file_raw = Path(
            str(recovery_authorization.get("AUTHORIZATION_FILE", ""))
        )
        recovery_authorization_file = (
            _remap_registered_worktree_reference(
                recovery_authorization_file_raw, evidence.repo_root
            )
            if recovery_authorization_file_raw.is_absolute()
            else (evidence.repo_root / recovery_authorization_file_raw).resolve(
                strict=False
            )
        )
        append_error(
            errors,
            _same_registered_worktree_location(
                recovery_authorization_file,
                Path(frozen_records.get("recovery_p4_authorization", {}).get("original_resolved_path", "")),
                evidence.repo_root,
            ),
            "historical recovery authorization original path does not bind frozen P4 authorization",
        )
        append_error(errors, resolve_reference(recovery_authorization.get("PROFILE"), document=authorization_path, repo_root=evidence.repo_root) == canonical_profile, "historical recovery authorization profile path mismatch")
        if r4_incomplete_no_action:
            append_error(errors, recovery_authorization.get("BITSTREAM") == "MISSING", "historical r4 no-action recovery bitstream field mismatch")
        else:
            append_error(errors, resolve_reference(recovery_authorization.get("BITSTREAM"), document=authorization_path, repo_root=evidence.repo_root) == canonical_shutdown_bit, "historical recovery authorization bitstream path mismatch")
        authorization_hash_bindings = (
            ("PROFILE_SHA256", canonical_profile),
            ("BITSTREAM_SHA256", canonical_shutdown_bit),
            ("ACTIVE_PINMAP_HASH", canonical_pinmap),
            ("ACTIVE_XDC_HASH", canonical_xdc),
        )
        for key, path in authorization_hash_bindings:
            expected = str(recovery_authorization.get(key, "")).lower()
            expected_copy = str(recovery_authorization.get(f"{key}_EXPECTED", "")).lower()
            if r4_incomplete_no_action:
                if key == "BITSTREAM_SHA256":
                    append_error(errors, expected == "missing" and expected_copy == "missing", "historical r4 no-action recovery bitstream SHA fields mismatch")
                else:
                    append_error(errors, path.is_file() and SHA256_RE.fullmatch(expected) is not None, f"historical r4 no-action recovery {key} actual hash missing/malformed")
                    append_error(errors, expected_copy in {"missing", "not_provided"}, f"historical r4 no-action recovery {key} expected field mismatch")
                    if path.is_file() and SHA256_RE.fullmatch(expected):
                        append_error(
                            errors,
                            _sha256_matches_registered_materialization(
                                path, expected, evidence.repo_root
                            ),
                            f"historical r4 no-action recovery {key} actual hash does not bind canonical file",
                        )
            else:
                append_error(errors, path.is_file() and SHA256_RE.fullmatch(expected) is not None, f"historical recovery authorization {key} missing/malformed")
                if r7_profile_mismatch_no_action and key == "PROFILE_SHA256":
                    append_error(errors, expected_copy == "dc89e84036847bcb865937bb3df3d1b3df7b027ec97ec31f433fe4d53aa89fe3", "historical r7 no-action recovery mistyped expected profile SHA mismatch")
                else:
                    append_error(errors, expected == expected_copy, f"historical recovery authorization {key} expected/actual mismatch")
                if path.is_file() and SHA256_RE.fullmatch(expected):
                    append_error(
                        errors,
                        _sha256_matches_registered_materialization(
                            path, expected, evidence.repo_root
                        ),
                        f"historical recovery authorization {key} does not bind canonical file",
                    )
        record = {
            "directory": str(recovery_dir),
            "started_at_utc": begin_match.group(1).strip() if begin_match else None,
            "ended_at_utc": end_match.group(1).strip() if end_match else None,
            "files": file_records,
        }
        if recovery_status == "AUTHORIZATION_MISSING":
            append_error(errors, set(file_records) == {"program_tfdu_shutdown_safe.summary.txt", "hardware_authorization.json", "hash_manifest.json", "hash_manifest.csv"}, "historical no-action recovery file set mismatch")
            append_error(errors, recovery_markers.get("AUTHORIZATION_MISSING") == "1", "historical no-action recovery lacks AUTHORIZATION_MISSING=1")
            append_error(errors, recovery_markers.get("NO_HARDWARE_ACTIONS_EXECUTED") == "1", "historical authorization-missing recovery did not remain no-action")
            append_error(errors, recovery_markers.get("HARDWARE_AUTHORIZATION_EXIT") not in {None, "0"}, "historical authorization-missing recovery has a successful authorization exit")
            append_error(errors, "TFDU_SHUTDOWN_PROGRAMMED_SEEN" not in recovery_markers and "SHUTDOWN_EXIT" not in recovery_markers, "historical no-action recovery falsely claims shutdown programming")
            append_error(errors, recovery_authorization.get("AUTHORIZED") is False, "historical no-action recovery authorization is not false")
            append_error(errors, recovery_authorization.get("P4_AUTHORIZATION") == "BLOCKED_NOT_AUTHORIZED", "historical no-action recovery authorization status mismatch")
            append_error(errors, recovery_authorization.get("RF_COMM_HW_AUTH_PRESENT") is r7_profile_mismatch_no_action, "historical no-action recovery RF hardware authorization fact mismatch")
            expected_missing = (
                [
                    "--max-runtime-sec",
                    "--shutdown-on-exit",
                    "--board-id",
                    "--bitstream",
                    "--bitstream-sha256",
                    "--active-pinmap-hash",
                    "--active-xdc-hash",
                    "RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW",
                ]
                if r4_incomplete_no_action
                else [
                    "--profile-sha256 mismatch: expected dc89e18e3c4f4d8a14cba63d8c6c5970aa632e8f6837a3e0e6e86345ea2f80e1, got dc89e84036847bcb865937bb3df3d1b3df7b027ec97ec31f433fe4d53aa89fe3"
                ]
                if r7_profile_mismatch_no_action
                else ["RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"]
            )
            append_error(errors, recovery_authorization.get("missing") == expected_missing, "historical no-action recovery missing-requirements list mismatch")
            record["classification"] = "AUTHORIZATION_MISSING_NO_ACTION"
            record["hardware_actions_executed"] = False
            no_action_records.append(record)
        elif recovery_status == "PASS":
            append_error(errors, set(file_records) == {"program_tfdu_shutdown_safe.summary.txt", "hardware_authorization.json", "hash_manifest.json", "hash_manifest.csv", "program_tfdu_shutdown_safe.stdout.log", "program_tfdu_shutdown_safe.stderr.log"}, "historical effective recovery file set mismatch")
            append_error(errors, recovery_markers.get("HARDWARE_AUTHORIZATION_EXIT") == "0" and recovery_markers.get("ALLOW_HARDWARE") == "1", "historical effective recovery authorization did not pass")
            append_error(errors, recovery_markers.get("NO_HARDWARE_ACTIONS_EXECUTED") == "0", "historical effective recovery incorrectly claims no hardware action")
            append_error(errors, recovery_markers.get("TFDU_SHUTDOWN_PROGRAMMED_SEEN") == "1", "historical effective recovery lacks TFDU shutdown marker")
            append_error(errors, recovery_markers.get("SHUTDOWN_EXIT") == "0", "historical effective recovery lacks SHUTDOWN_EXIT=0")
            append_error(errors, recovery_markers.get("SHUTDOWN_RAW_EXIT") in {"0", "125"}, "historical effective recovery raw exit is neither direct success nor the supported normalized wrapper exit")
            append_error(errors, recovery_authorization.get("AUTHORIZED") is True, "historical effective recovery authorization is not true")
            append_error(errors, recovery_authorization.get("P4_AUTHORIZATION") == "AUTHORIZED", "historical effective recovery authorization status mismatch")
            append_error(errors, recovery_authorization.get("RF_COMM_HW_AUTH_PRESENT") is True, "historical effective recovery lacks RF hardware authorization")
            append_error(errors, recovery_authorization.get("missing") == [], "historical effective recovery authorization missing-list is nonempty")
            stdout = recovery_dir / "program_tfdu_shutdown_safe.stdout.log"
            append_error(errors, resolve_reference(recovery_markers.get("SHUTDOWN_STDOUT_LOG"), document=summary, repo_root=evidence.repo_root) == stdout.resolve(strict=False), "historical effective recovery summary stdout path mismatch")
            append_error(errors, resolve_reference(recovery_markers.get("SHUTDOWN_STDERR_LOG"), document=summary, repo_root=evidence.repo_root) == (recovery_dir / "program_tfdu_shutdown_safe.stderr.log").resolve(strict=False), "historical effective recovery summary stderr path mismatch")
            stdout_text = marker_text(stdout)
            shutdown_marker_paths = [
                resolve_reference(
                    line[len("TFDU_SHUTDOWN_PROGRAMMED ") :],
                    document=stdout,
                    repo_root=evidence.repo_root,
                )
                for line in stdout_text.splitlines()
                if line.startswith("TFDU_SHUTDOWN_PROGRAMMED ")
            ]
            append_error(errors, stdout_text.count("HW_TARGET localhost:3121/xilinx_tcf/Digilent/210512180081") == 1, "historical effective recovery stdout target identity missing/duplicated")
            append_error(errors, stdout_text.count("HW_JTAG_FREQUENCY_HZ 1000000") == 1, "historical effective recovery stdout JTAG frequency missing/duplicated")
            append_error(errors, stdout_text.count("HW_DEVICE xc7z010_1") == 1, "historical effective recovery stdout device identity missing/duplicated")
            append_error(
                errors,
                shutdown_marker_paths
                == [canonical_shutdown_bit.resolve(strict=False)],
                "historical effective recovery stdout canonical shutdown marker missing/duplicated",
            )
            stderr = recovery_dir / "program_tfdu_shutdown_safe.stderr.log"
            append_error(errors, stderr.is_file() and stderr.stat().st_size == 0, "historical effective recovery stderr is missing/nonempty")
            record["classification"] = "EFFECTIVE_TFDU_SHUTDOWN"
            record["hardware_actions_executed"] = True
            record["tfdu_shutdown_programmed_seen"] = True
            record["shutdown_exit"] = 0
            raw_exit_text = str(recovery_markers.get("SHUTDOWN_RAW_EXIT", ""))
            record["observed_raw_exit"] = int(raw_exit_text) if re.fullmatch(r"\d+", raw_exit_text) else None
            effective_records.append(record)
        else:
            errors.append(f"historical recovery status is neither no-action nor PASS: {recovery_dir.name}")
    append_error(errors, len(no_action_records) + len(effective_records) == len(recovery_dirs), "historical epoch contains an unclassified recovery")
    append_error(errors, len(effective_records) == 1, "historical epoch must contain exactly one effective shutdown recovery")
    if historical_variant == HISTORICAL_PREFLIGHT_IDENTITY_PASS_HELPER_CONTAINMENT_REJECTED:
        append_error(
            errors,
            len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1,
            "historical r2 must contain exactly one effective recovery and no no-action recovery",
        )
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0,
            "historical r2 recovery does not prove normalized raw rc125 with SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED:
        append_error(
            errors,
            len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1,
            "historical r3 must contain exactly one effective recovery and no no-action recovery",
        )
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r3 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED:
        append_error(
            errors,
            len(recovery_dirs) == 2
            and len(no_action_records) == 1
            and len(effective_records) == 1,
            "historical r4 must contain one authorization-missing no-action recovery followed by one effective recovery",
        )
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r4 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED:
        append_error(
            errors,
            len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1,
            "historical r5 must contain exactly one effective recovery and no no-action recovery",
        )
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r5 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED:
        append_error(
            errors,
            len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1,
            "historical r6 must contain exactly one effective recovery and no no-action recovery",
        )
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r6 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED:
        append_error(
            errors,
            len(recovery_dirs) == 2
            and len(no_action_records) == 1
            and len(effective_records) == 1,
            "historical r7 must contain one authorization-missing no-action recovery followed by one effective recovery",
        )
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r7 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED:
        append_error(errors, len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1, "historical r8 must contain exactly one effective recovery and no no-action recovery")
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r8 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE:
        append_error(errors, len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1, "historical r9 must contain exactly one effective recovery and no recovery-directory no-action record")
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            "historical r9 recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant in {
        HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
        HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
    }:
        recovery_label = "historical r10" if historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT else "historical r13"
        append_error(errors, len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1, f"{recovery_label} must contain exactly one effective recovery and no recovery-directory no-action record")
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            f"{recovery_label} recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    elif historical_variant in {
        HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
        HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
        HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
        HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
    }:
        recovery_label = (
            "historical r11"
            if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
            else "historical r12"
            if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
            else "historical r14"
            if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
            else "historical r15"
        )
        append_error(errors, len(recovery_dirs) == 1 and not no_action_records and len(effective_records) == 1, f"{recovery_label} must contain exactly one effective recovery and no recovery-directory no-action record")
        append_error(
            errors,
            len(effective_records) == 1
            and effective_records[0].get("observed_raw_exit") == 125
            and effective_records[0].get("shutdown_exit") == 0
            and effective_records[0].get("tfdu_shutdown_programmed_seen") is True,
            f"{recovery_label} recovery does not prove one TFDU marker with normalized raw rc125 and SHUTDOWN_EXIT=0",
        )
    ordered_recoveries = sorted(recovery_times)
    append_error(
        errors,
        bool(ordered_recoveries)
        and outer_end == outer_end
        and outer_end <= ordered_recoveries[0][0]
        and all(previous_end <= next_start for (_previous_start, previous_end), (next_start, _next_end) in zip(ordered_recoveries, ordered_recoveries[1:])),
        "historical outer attempt/recovery chronology is invalid",
    )
    if len(effective_records) == 1:
        effective_end = parse_time(effective_records[0].get("ended_at_utc"), float("nan"))
        append_error(errors, ordered_recoveries and effective_end == ordered_recoveries[-1][1], "historical effective shutdown is not the final recovery action")
    epoch_end = ordered_recoveries[-1][1] if ordered_recoveries else outer_end
    r15_reversal_proofs: list[dict[str, Any]] = []
    if historical_variant == HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED:
        r15_reversal_proofs, reversal_errors = _axi4_burst_word_order_reversal_proofs(candidate)
        errors.extend(reversal_errors)
    inner_preflight = candidate.data.get("preflight" if candidate.kind == "ps" else "preflight_process")
    record = {
        "schema": (
            "rf-comm-p7-historical-failed-stage-epoch-v1"
            if failed_stage_variant
            else "rf-comm-p7-historical-read-only-preflight-epoch-v1"
        ),
        "epoch_root": str(epoch_root),
        "source_commit": source,
        "failure_class": historical_variant,
        **({"preflight_failure_class": historical_variant} if not failed_stage_variant else {}),
        "result": "FAIL",
        "coverage_keys": [],
        "mutation_attempted_by_wrapper": _candidate_mutation_attempted(candidate),
        "mutation_attempted_by_candidate": _candidate_programmed(candidate),
        "candidate_process_present": isinstance(
            candidate.data.get("ps_process" if candidate.kind == "ps" else "stage_process"),
            dict,
        ),
        "outer_sequence_ledger": _hash_record(outer_path),
        "outer_process_containment": {
            "process_tree_reaped": process.get("process_tree_reaped"),
            "containment_kind": process.get("containment_kind"),
            "containment_assigned": process.get("containment_assigned"),
            "containment_closed": process.get("containment_closed"),
            "descendant_count_after": process.get("descendant_count_after"),
        },
        "inner_preflight_process_tree_reaped": inner_preflight.get("process_tree_reaped") if isinstance(inner_preflight, dict) else None,
        "read_only_target_identity": candidate.data.get("target_identity"),
        "inner_preflight_containment": {
            "returncode": inner_preflight.get("returncode"),
            "process_tree_terminated": inner_preflight.get("process_tree_terminated"),
            "process_tree_reaped": inner_preflight.get("process_tree_reaped"),
            "containment_kind": inner_preflight.get("containment_kind"),
            "containment_assigned": inner_preflight.get("containment_assigned"),
            "containment_closed": inner_preflight.get("containment_closed"),
            "descendant_count_after": inner_preflight.get("descendant_count_after"),
            "containment_cleanup_terminated": inner_preflight.get("containment_cleanup_terminated"),
            "expected_tool_daemon_paths": inner_preflight.get("expected_tool_daemon_paths"),
            "expected_tool_daemon_classification": inner_preflight.get("expected_tool_daemon_classification"),
            "descendant_paths_seen": inner_preflight.get("descendant_paths_seen"),
            "descendant_processes_seen": inner_preflight.get("descendant_processes_seen"),
            "containment_query_error": inner_preflight.get("containment_query_error"),
        } if isinstance(inner_preflight, dict) else None,
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "failed_shutdown_attempts": {
                    which: {
                        "returncode": candidate.data.get(f"shutdown_{which}", {}).get("returncode"),
                        "passed": candidate.data.get(f"shutdown_{which}", {}).get("passed"),
                        "process_tree_reaped": candidate.data.get(f"shutdown_{which}", {}).get("process_tree_reaped"),
                        "programmed_shutdown": candidate.data.get(f"programmed_shutdown_{which}"),
                        "result_file": _hash_record(
                            candidate.path.parent / f"p7_shutdown_{which}_result.txt"
                        ),
                    }
                    for which in ("before", "after")
                },
            }
            if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED
            else (
                {
                    "historical_source_control_flow": historical_source_control_flow,
                    "failed_candidate_stage": {
                        "returncode": candidate.data.get("stage_process", {}).get("returncode"),
                        "passed": candidate.data.get("stage_process", {}).get("passed"),
                        "process_tree_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                        "candidate_programmed": candidate.data.get("programmed_candidate"),
                        "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    },
                    "successful_shutdown_barriers": {
                        which: {
                            "returncode": candidate.data.get(f"shutdown_{which}", {}).get("returncode"),
                            "passed": candidate.data.get(f"shutdown_{which}", {}).get("passed"),
                            "process_tree_reaped": candidate.data.get(f"shutdown_{which}", {}).get("process_tree_reaped"),
                            "programmed_shutdown": candidate.data.get(f"programmed_shutdown_{which}"),
                            "result_file": _hash_record(candidate.path.parent / f"p7_shutdown_{which}_result.txt"),
                        }
                        for which in ("before", "after")
                    },
                }
                if historical_variant == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED
                else (
                    {
                        "historical_source_control_flow": historical_source_control_flow,
                        "backend_rejected_candidate_stage": {
                            "returncode": candidate.data.get("stage_process", {}).get("returncode"),
                            "passed": candidate.data.get("stage_process", {}).get("passed"),
                            "process_tree_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                            "candidate_programmed": candidate.data.get("programmed_candidate"),
                            "raw_result_file": _hash_record(raw_marker_path(candidate)),
                            "backend_parse_failure": candidate.data.get("backend_parse_failure"),
                        },
                        "successful_shutdown_barriers": {
                            which: {
                                "returncode": candidate.data.get(f"shutdown_{which}", {}).get("returncode"),
                                "passed": candidate.data.get(f"shutdown_{which}", {}).get("passed"),
                                "process_tree_reaped": candidate.data.get(f"shutdown_{which}", {}).get("process_tree_reaped"),
                                "programmed_shutdown": candidate.data.get(f"programmed_shutdown_{which}"),
                                "result_file": _hash_record(candidate.path.parent / f"p7_shutdown_{which}_result.txt"),
                            }
                            for which in ("before", "after")
                        },
                    }
                    if historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED
                    else {}
                )
            )
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "axi4lite_burst_rejection_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "stage_error": raw_markers(candidate)[0].get("P7_JTAG_STAGE_ERROR"),
                    "fragment_markers_present": any(key.startswith("P7F") for key in raw_markers(candidate)[0]),
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "jtag_axi_queue_depth_one_rejection_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "stderr_file": _hash_record(candidate.path.parent / "p7_jtag_axi_stage.stderr.log"),
                    "raw_stage_error": raw_markers(candidate)[0].get("P7_JTAG_STAGE_ERROR"),
                    "exact_stderr_error": marker_text(candidate.path.parent / "p7_jtag_axi_stage.stderr.log").strip(),
                    "fragment_markers_present": any(key.startswith("P7F") for key in raw_markers(candidate)[0]),
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "queued_jtag_timeout_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_timed_out": candidate.data.get("stage_process", {}).get("timed_out"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "minimum_run_hw_axi_call_count": candidate.data.get("transaction_validation", {}).get("minimum_run_hw_axi_call_count"),
                    "multi_transaction_batch_count": candidate.data.get("transaction_validation", {}).get("multi_transaction_batch_count"),
                    "max_batch_transactions": candidate.data.get("transaction_validation", {}).get("max_batch_transactions"),
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "axi4_queued_control_order_rejection_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_passed": candidate.data.get("stage_process", {}).get("passed"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "backend_parse_failure": candidate.data.get("backend_parse_failure"),
                    "minimum_run_hw_axi_call_count": candidate.data.get("transaction_validation", {}).get("minimum_run_hw_axi_call_count"),
                    "axi4_incr_burst_count": candidate.data.get("transaction_validation", {}).get("axi4_incr_burst_count"),
                    "queued_single_transaction_count": candidate.data.get("transaction_validation", {}).get("queued_single_transaction_count"),
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "axi4_burst_word_order_rejection_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_passed": candidate.data.get("stage_process", {}).get("passed"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "backend_parse_failure": candidate.data.get("backend_parse_failure"),
                    "minimum_run_hw_axi_call_count": candidate.data.get("transaction_validation", {}).get("minimum_run_hw_axi_call_count"),
                    "axi4_incr_burst_count": candidate.data.get("transaction_validation", {}).get("axi4_incr_burst_count"),
                    "ordered_control_write_run_hw_axi_call_count": candidate.data.get("transaction_validation", {}).get("ordered_control_write_run_hw_axi_call_count"),
                    "reversed_word_crc_fragment_proof_count": len(r15_reversal_proofs),
                    "reversed_word_crc_fragment_proofs": r15_reversal_proofs,
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "shutdown_helper_exit_race_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_passed": candidate.data.get("stage_process", {}).get("passed"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "shutdown_after_returncode": candidate.data.get("shutdown_after", {}).get("returncode"),
                    "shutdown_after_result_marker": parse_marker_text(
                        marker_text(candidate.path.parent / "p7_shutdown_after_result.txt")
                    )[0].get("P7_SHUTDOWN_RESULT"),
                    "shutdown_after_process_tree_reaped": candidate.data.get("shutdown_after", {}).get("process_tree_reaped"),
                    "shutdown_after_forced_cleanup": candidate.data.get("shutdown_after", {}).get("containment_cleanup_terminated"),
                    "shutdown_after_query_error": candidate.data.get("shutdown_after", {}).get("containment_query_error"),
                    "shutdown_after_result_file": _hash_record(candidate.path.parent / "p7_shutdown_after_result.txt"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "backend_retry_semantics_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_passed": candidate.data.get("stage_process", {}).get("passed"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "backend_parse_failure": candidate.data.get("backend_parse_failure"),
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "outer_deadline_abort_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_abort_seen": candidate.data.get("stage_process", {}).get("abort_seen"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_forced_cleanup": candidate.data.get("stage_process", {}).get("containment_cleanup_terminated"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "shutdown_before_passed": candidate.data.get("shutdown_before", {}).get("passed"),
                    "shutdown_after_passed": candidate.data.get("shutdown_after", {}).get("passed"),
                    "deadline_abort_record": _hash_record(epoch_root / "outer_deadline_abort_record.json"),
                    "launcher_refusal_record": _hash_record(epoch_root / "recovery_launcher_refusal_record.json"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE
            else {}
        ),
        **(
            {
                "historical_source_control_flow": historical_source_control_flow,
                "shutdown_timeout_before_programming_failure": {
                    "candidate_returncode": candidate.data.get("stage_process", {}).get("returncode"),
                    "candidate_passed": candidate.data.get("stage_process", {}).get("passed"),
                    "candidate_reaped": candidate.data.get("stage_process", {}).get("process_tree_reaped"),
                    "candidate_programmed": candidate.data.get("programmed_candidate"),
                    "raw_result_file": _hash_record(raw_marker_path(candidate)),
                    "shutdown_after_returncode": candidate.data.get("shutdown_after", {}).get("returncode"),
                    "shutdown_after_timed_out": candidate.data.get("shutdown_after", {}).get("timed_out"),
                    "shutdown_after_programming_attempted": candidate.data.get("shutdown_after", {}).get("programming_attempted"),
                    "shutdown_after_process_tree_reaped": candidate.data.get("shutdown_after", {}).get("process_tree_reaped"),
                    "shutdown_after_forced_cleanup": candidate.data.get("shutdown_after", {}).get("containment_cleanup_terminated"),
                    "shutdown_after_result_file": _hash_record(candidate.path.parent / "p7_shutdown_after_result.txt"),
                },
            }
            if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED
            else {}
        ),
        "verified_historical_pass_prefix": (
            [
                {
                    "stage_index": index,
                    "stage_id": prefix_attempt.get("stage_id"),
                    "result": "PASS_ON_SUPERSEDED_SOURCE_NO_ACTIVE_CHECKPOINT_COVERAGE",
                    "coverage_keys": [],
                    "summary_file": prefix_attempt.get("summary_file"),
                }
                for index, prefix_attempt in enumerate(attempts[:failed_stage_index])
                if isinstance(prefix_attempt, dict)
            ]
            if historical_variant
            in {
                HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
                HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
                HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
                HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
                HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
                HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
                HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
                HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
                HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
                HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
                HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
            }
            else []
        ),
        "diagnostic_preflight_files": diagnostic_files,
        "frozen_preflight_inputs": {
            "manifest": _hash_record(frozen_manifest_path) if frozen_manifest_path.is_file() else None,
            "files": [frozen_records[role] for role in sorted(frozen_records)],
        },
        "authorization_missing_no_action_recoveries": no_action_records,
        "effective_shutdown_recovery": effective_records[0] if len(effective_records) == 1 else None,
        "started_at_utc": (
            attempts[0].get("started_at_utc")
            if isinstance(attempts, list) and attempts and isinstance(attempts[0], dict)
            else attempt.get("started_at_utc")
        ),
        "ended_at_utc": effective_records[0].get("ended_at_utc") if len(effective_records) == 1 else None,
        "ended_at_epoch_seconds": epoch_end,
    }
    return record, errors


def _git_source_ancestry_errors(
    evidence: RepositoryEvidence,
    *,
    old_commit: str,
    active_commit: str,
) -> list[str]:
    errors: list[str] = []
    if not (evidence.repo_root / ".git").exists():
        return ["Git metadata unavailable; cannot prove historical source ancestry"]
    for label, commit in (("historical", old_commit), ("active", active_commit)):
        try:
            result = subprocess.run(
                ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
                cwd=evidence.repo_root,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"unable to validate {label} source commit object: {exc}")
        else:
            append_error(errors, result.returncode == 0, f"{label} source commit object is missing")
    if errors:
        return errors
    try:
        ancestry = subprocess.run(
            ["git", "merge-base", "--is-ancestor", old_commit, active_commit],
            cwd=evidence.repo_root,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"unable to validate historical source ancestry: {exc}")
    else:
        append_error(errors, ancestry.returncode == 0, "historical source commit is not an ancestor of the active checkpoint")
    return errors


def _historical_epoch_order_errors(
    epochs: Sequence[Mapping[str, Any]],
    evidence: RepositoryEvidence,
) -> list[str]:
    """Require complete epoch intervals and monotonic source/checkpoint history."""

    errors: list[str] = []
    for index, epoch in enumerate(epochs):
        start = parse_time(epoch.get("started_at_utc"), float("nan"))
        end = parse_time(epoch.get("ended_at_utc"), float("nan"))
        append_error(
            errors,
            start == start and end == end and start <= end,
            f"historical epoch {index} interval is missing/malformed",
        )
    for index, (previous, following) in enumerate(zip(epochs, epochs[1:])):
        previous_end = parse_time(previous.get("ended_at_utc"), float("nan"))
        following_start = parse_time(following.get("started_at_utc"), float("nan"))
        append_error(
            errors,
            previous_end == previous_end
            and following_start == following_start
            and previous_end <= following_start,
            f"historical epoch order {index}->{index + 1} overlaps or regresses",
        )
        previous_source = str(previous.get("source_commit", "")).lower()
        following_source = str(following.get("source_commit", "")).lower()
        if previous_source == following_source:
            continue
        if COMMIT_RE.fullmatch(previous_source) and COMMIT_RE.fullmatch(following_source):
            errors.extend(
                f"historical source order {index}->{index + 1}: {item}"
                for item in _git_source_ancestry_errors(
                    evidence,
                    old_commit=previous_source,
                    active_commit=following_source,
                )
            )
        else:
            errors.append(f"historical source order {index}->{index + 1} has malformed commit identity")
    return errors


def _candidate_checkpoint_relation(
    candidate: Candidate,
    evidence: RepositoryEvidence,
    *,
    offline_commit: str,
    offline_time: float,
) -> tuple[str, list[str], dict[str, Any] | None]:
    source = _candidate_source_commit(candidate)
    wrapper_start, wrapper_end = authorized_execution_boundaries(candidate)
    start = parse_time(wrapper_start, float("nan"))
    end = parse_time(wrapper_end, float("nan"))
    errors: list[str] = []
    if source == offline_commit:
        append_error(errors, start == start and offline_time == offline_time and start >= offline_time, "checkpoint-bound run started before the active offline checkpoint")
        return CHECKPOINT_RELATION_BOUND, errors, None
    historical_variant = _historical_preflight_variant(candidate)
    if historical_variant == HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED:
        errors.extend(_old_commit_shutdown_tcl_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED:
        errors.extend(_old_commit_write_allowlist_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED:
        errors.extend(_old_commit_backend_raw_pulse_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED:
        errors.extend(_old_commit_shutdown_helper_exit_race_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED:
        errors.extend(_old_commit_shutdown_timeout_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED:
        errors.extend(_old_commit_backend_retry_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE:
        errors.extend(_old_commit_outer_deadline_abort_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT:
        errors.extend(_old_commit_1m_jtag_timeout_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT:
        errors.extend(_old_commit_1m_jtag_queued_timeout_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED:
        errors.extend(_old_commit_axi4lite_burst_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED:
        errors.extend(_old_commit_jtag_axi_queue_depth_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED:
        errors.extend(_old_commit_axi4_queued_control_order_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED:
        errors.extend(_old_commit_axi4_burst_word_order_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED:
        errors.extend(_old_commit_ps_shutdown_arg_count_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_RESET_TARGET_UNIQUENESS_REJECTED:
        errors.extend(_old_commit_ps_reset_target_uniqueness_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED:
        errors.extend(_old_commit_ps_reset_target_uniqueness_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED:
        errors.extend(_old_commit_ps_reset_target_uniqueness_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    elif historical_variant == HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED:
        errors.extend(_old_commit_ps_functional_boundary_failure_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_FAILED_STAGE
    else:
        errors.extend(_old_commit_read_only_preflight_errors(candidate, evidence))
        relation = CHECKPOINT_RELATION_OLD_DIAGNOSTIC
    historical_epoch, historical_errors = _historical_epoch_record(candidate, evidence)
    errors.extend(historical_errors)
    append_error(errors, COMMIT_RE.fullmatch(source) is not None and source != offline_commit, "superseded diagnostic source commit is missing or matches the active checkpoint")
    if COMMIT_RE.fullmatch(source) and COMMIT_RE.fullmatch(offline_commit) and source != offline_commit:
        errors.extend(
            _git_source_ancestry_errors(
                evidence,
                old_commit=source,
                active_commit=offline_commit,
            )
        )
    epoch_end = historical_epoch.get("ended_at_epoch_seconds") if isinstance(historical_epoch, dict) else None
    append_error(
        errors,
        end == end
        and offline_time == offline_time
        and isinstance(epoch_end, (int, float))
        and end <= float(epoch_end) <= offline_time,
        "superseded diagnostic/recovery epoch did not finish before the active offline checkpoint",
    )
    if isinstance(historical_epoch, dict):
        historical_epoch.pop("ended_at_epoch_seconds", None)
    return relation, errors, historical_epoch


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
    candidate_raw = candidate.path.parent / (
        "p7_ps_application_raw_result.log" if candidate.kind == "ps" else "p7_jtag_axi_raw_result.txt"
    )
    if not _candidate_mutation_attempted(candidate) or (
        not _candidate_programmed(candidate) and not candidate_raw.is_file()
    ):
        return candidate.path.parent / ("p7_hw_preflight_result.txt" if candidate.kind == "ps" else "p7_preflight_result.txt")
    return candidate_raw


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
    tfdu_value = result_markers.get("TFDU_SHUTDOWN_PROGRAMMED", "")
    shutdown_exit = result_markers.get("SHUTDOWN_EXIT")
    authorized_shutdown = _authorized_shutdown_path(candidate, repo_root=evidence.repo_root)
    programmed_shutdown = resolve_reference(
        tfdu_value, document=result_path, repo_root=evidence.repo_root
    )
    return {
        "present": True,
        "returncode": block.get("returncode"),
        "passed": block.get("passed"),
        "attempted": block.get("attempted"),
        "programming_attempted": block.get("programming_attempted"),
        "result_file": _hash_record(result_path) if result_path.is_file() else {"path": str(result_path), "missing": True},
        "stdout_file": _hash_record(stdout_path) if stdout_path is not None and stdout_path.is_file() else {"path": str(stdout_path or "MISSING"), "missing": True},
        "tfdu_shutdown_marker": bool(tfdu_value),
        "tfdu_shutdown_path": tfdu_value,
        "tfdu_shutdown_path_matches_authorized": bool(
            authorized_shutdown is not None
            and programmed_shutdown is not None
            and programmed_shutdown == authorized_shutdown
        ),
        "programming_attempted_marker": result_markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1",
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


def _collapse_historical_epoch_candidates(
    candidates: Sequence[Candidate],
    offline_commit: str,
) -> list[Candidate]:
    """Represent a superseded multi-attempt epoch by its terminal failed stage.

    The terminal epoch validator independently binds every preceding PASS
    attempt.  Those old-source prefix stages must not appear as standalone
    active-checkpoint coverage records.
    """

    terminal_by_epoch: dict[Path, Candidate] = {}
    for item in candidates:
        if _candidate_source_commit(item) == offline_commit.lower():
            continue
        if _historical_preflight_variant(item) in {
            HISTORICAL_STAGE_SHUTDOWN_TCL_CHAR_MAP_REJECTED,
            HISTORICAL_STAGE_WRITE_ALLOWLIST_REJECTED,
            HISTORICAL_STAGE_BACKEND_RAW_PULSE_SEMANTICS_REJECTED,
            HISTORICAL_STAGE_SHUTDOWN_HELPER_EXIT_RACE_REJECTED,
            HISTORICAL_STAGE_SHUTDOWN_TIMEOUT_BEFORE_PROGRAMMING_REJECTED,
            HISTORICAL_STAGE_BACKEND_RETRY_SEMANTICS_REJECTED,
            HISTORICAL_STAGE_OPERATOR_ABORTED_FOR_OUTER_DEADLINE,
            HISTORICAL_STAGE_1M_JTAG_SINGLE_WORD_TIMEOUT,
            HISTORICAL_STAGE_1M_JTAG_QUEUED_TIMEOUT,
            HISTORICAL_STAGE_AXI4LITE_BURST_REJECTED,
            HISTORICAL_STAGE_JTAG_AXI_QUEUE_DEPTH_ONE_REJECTED,
            HISTORICAL_STAGE_AXI4_QUEUED_CONTROL_ORDER_REJECTED,
            HISTORICAL_STAGE_AXI4_BURST_WORD_ORDER_REJECTED,
            HISTORICAL_STAGE_PS_SHUTDOWN_ARG_COUNT_REJECTED,
            HISTORICAL_STAGE_PS_RESET_TARGET_UNIQUENESS_REJECTED,
            HISTORICAL_STAGE_PS_CHILD_TARGET_IDENTITY_REJECTED,
            HISTORICAL_STAGE_PS_JTAG_DEVICE_CARDINALITY_REJECTED,
            HISTORICAL_STAGE_PS_FUNCTIONAL_BOUNDARY_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_CAPTURE_REJECTED,
            HISTORICAL_STAGE_PS_OUTPUT_INTEGRITY_DIVERGENCE_REJECTED,
            HISTORICAL_STAGE_PS_BOUNDARY_30_INTEGRITY_REJECTED,
            HISTORICAL_STAGE_PS_POST_WIPE_CAPTURED_INTEGRITY_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MARKER_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_MAILBOX_MARKER_REJECTED,
            HISTORICAL_STAGE_PS_FAILURE_SNAPSHOT_CAPTURED_INTEGRITY_REJECTED,
            HISTORICAL_STAGE_PS_OUTPUT_BYTE_COPY_VERIFICATION_REJECTED,
        }:
            terminal_by_epoch[item.path.parent.parent.resolve(strict=False)] = item
    return [
        item
        for item in candidates
        if (
            item.path.parent.parent.resolve(strict=False) not in terminal_by_epoch
            or terminal_by_epoch[item.path.parent.parent.resolve(strict=False)].path == item.path
        )
    ]


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
    offline_time = parse_time(offline_payload.get("generated_at_utc"), float("nan"))
    if offline_time != offline_time:
        raise ValueError("offline checkpoint generated_at_utc is missing/malformed")

    def start_key(candidate: Candidate) -> tuple[float, str]:
        wrapper_start, _wrapper_end = authorized_execution_boundaries(candidate)
        process = _candidate_process(candidate)
        return (parse_time(wrapper_start, parse_time(process.get("started_at_utc"), candidate.timestamp)), str(candidate.path))

    orphan_errors = orphan_hardware_footprint_errors(evidence)
    if orphan_errors:
        raise ValueError("; ".join(orphan_errors))
    hardware_candidates = [
        item for item in evidence.candidates if candidate_has_hardware_footprint(item)
    ]
    executed = sorted(
        _collapse_historical_epoch_candidates(
            hardware_candidates, offline_checkpoint_commit
        ),
        key=start_key,
    )
    runs: list[dict[str, Any]] = []
    read_only_diagnostic_count = 0
    failed_stage_diagnostic_count = 0
    historical_epochs: list[dict[str, Any]] = []
    for sequence, candidate in enumerate(executed, 1):
        process = _candidate_process(candidate)
        raw_path = _candidate_raw_path(candidate)
        event_path = _candidate_event_path(candidate)
        mutation_attempted = _candidate_mutation_attempted(candidate)
        basic_pass = _candidate_basic_pass(candidate, evidence)
        source = _candidate_source_commit(candidate)
        checkpoint_relation, relation_errors, historical_epoch = _candidate_checkpoint_relation(
            candidate,
            evidence,
            offline_commit=offline_checkpoint_commit.lower(),
            offline_time=offline_time,
        )
        if relation_errors:
            raise ValueError(
                f"run {rel(candidate.path, evidence.repo_root)} has invalid checkpoint relationship: "
                + "; ".join(relation_errors)
            )
        diagnostic_only = checkpoint_relation in CHECKPOINT_RELATIONS_HISTORICAL
        read_only_diagnostic_count += int(checkpoint_relation == CHECKPOINT_RELATION_OLD_DIAGNOSTIC)
        failed_stage_diagnostic_count += int(checkpoint_relation == CHECKPOINT_RELATION_OLD_FAILED_STAGE)
        attempted = [] if diagnostic_only else (_candidate_attempted_coverage(candidate, evidence) if mutation_attempted else [])
        if diagnostic_only and isinstance(historical_epoch, dict):
            historical_epochs.append(historical_epoch)
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
                "checkpoint_relation": checkpoint_relation,
                "diagnostic_only": diagnostic_only,
                "mutation_attempted": mutation_attempted,
                "eligible_for_checkpoint_coverage": checkpoint_relation == CHECKPOINT_RELATION_BOUND and mutation_attempted,
                "historical_epoch": historical_epoch,
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
                "shutdown_required": mutation_attempted,
                "shutdown_before": _ledger_shutdown(candidate, "before", evidence),
                "shutdown_after": _ledger_shutdown(candidate, "after", evidence),
            }
        )
    historical_order_errors = _historical_epoch_order_errors(historical_epochs, evidence)
    if historical_order_errors:
        raise ValueError("; ".join(historical_order_errors))
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
        "precheckpoint_read_only_diagnostic_count": read_only_diagnostic_count,
        "precheckpoint_failed_stage_diagnostic_count": failed_stage_diagnostic_count,
        "precheckpoint_historical_failure_count": (
            read_only_diagnostic_count + failed_stage_diagnostic_count
        ),
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
    if COMMIT_RE.fullmatch(offline_commit):
        executed = _collapse_historical_epoch_candidates(executed, offline_commit)
    offline_time = parse_time(offline.get("generated_at_utc"), float("nan"))
    append_error(errors, offline_time == offline_time, "run sequence offline checkpoint generated_at_utc malformed")
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
    append_error(
        errors,
        payload.get("precheckpoint_read_only_diagnostic_count")
        == sum(
            1
            for item in runs
            if isinstance(item, dict) and item.get("checkpoint_relation") == CHECKPOINT_RELATION_OLD_DIAGNOSTIC
        ),
        "run sequence historical diagnostic count mismatch",
    )
    append_error(
        errors,
        payload.get("precheckpoint_failed_stage_diagnostic_count")
        == sum(
            1
            for item in runs
            if isinstance(item, dict) and item.get("checkpoint_relation") == CHECKPOINT_RELATION_OLD_FAILED_STAGE
        ),
        "run sequence historical failed-stage diagnostic count mismatch",
    )
    append_error(
        errors,
        payload.get("precheckpoint_historical_failure_count")
        == sum(
            1
            for item in runs
            if isinstance(item, dict) and item.get("checkpoint_relation") in CHECKPOINT_RELATIONS_HISTORICAL
        ),
        "run sequence total historical failure count mismatch",
    )
    candidates_by_path = {item.path.resolve(strict=False): item for item in executed}
    seen_summaries: set[Path] = set()
    ordered_starts: list[float] = []
    ordered_intervals: list[tuple[float, float]] = []
    historical_epochs: list[dict[str, Any]] = []
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
        expected_pass = _candidate_basic_pass(candidate, evidence)
        expected_relation, relation_errors, historical_epoch = _candidate_checkpoint_relation(
            candidate,
            evidence,
            offline_commit=offline_commit,
            offline_time=offline_time,
        )
        errors.extend(f"run sequence entry {index}: {item}" for item in relation_errors)
        diagnostic_only = expected_relation in CHECKPOINT_RELATIONS_HISTORICAL
        failed_stage_diagnostic = expected_relation == CHECKPOINT_RELATION_OLD_FAILED_STAGE
        expected_attempted = [] if diagnostic_only else (_candidate_attempted_coverage(candidate, evidence) if mutation_attempted else [])
        recorded_historical_epoch = run.get("historical_epoch") if isinstance(run.get("historical_epoch"), dict) else {}
        if diagnostic_only and isinstance(historical_epoch, dict):
            historical_epochs.append(historical_epoch)
        append_error(errors, run.get("stage") == candidate.stage and run.get("kind") == candidate.kind, f"run sequence entry {index} stage/kind mismatch")
        append_error(errors, run.get("risk_index") == _candidate_risk(candidate, evidence), f"run sequence entry {index} risk index mismatch")
        append_error(errors, run.get("attempted_coverage_keys") == expected_attempted, f"run sequence entry {index} attempted coverage mismatch")
        append_error(errors, run.get("coverage_keys") == (expected_attempted if expected_pass else []), f"run sequence entry {index} PASS coverage mismatch")
        append_error(errors, run.get("result") == ("PASS" if expected_pass else "FAIL"), f"run sequence entry {index} result mismatch")
        append_error(errors, run.get("runner_result") == candidate.marker, f"run sequence entry {index} runner result mismatch")
        append_error(errors, run.get("checkpoint_relation") == expected_relation, f"run sequence entry {index} checkpoint relation mismatch")
        append_error(errors, run.get("diagnostic_only") is diagnostic_only, f"run sequence entry {index} diagnostic-only classification mismatch")
        append_error(errors, run.get("mutation_attempted") is mutation_attempted, f"run sequence entry {index} mutation-attempted classification mismatch")
        append_error(
            errors,
            run.get("eligible_for_checkpoint_coverage") is (expected_relation == CHECKPOINT_RELATION_BOUND and mutation_attempted),
            f"run sequence entry {index} checkpoint coverage eligibility mismatch",
        )
        append_error(errors, run.get("historical_epoch") == historical_epoch, f"run sequence entry {index} historical epoch binding mismatch")
        if diagnostic_only:
            append_error(errors, run.get("result") == "FAIL", f"run sequence entry {index} historical diagnostic is not FAIL")
            append_error(errors, run.get("attempted_coverage_keys") == [] and run.get("coverage_keys") == [], f"run sequence entry {index} historical diagnostic claims coverage")
            if failed_stage_diagnostic:
                append_error(errors, run.get("mutation_attempted") is True and run.get("shutdown_required") is True, f"run sequence entry {index} historical failed-stage omits shutdown attempts/obligation")
            else:
                append_error(errors, run.get("risk_index") == 5, f"run sequence entry {index} historical diagnostic risk is not 5")
                append_error(errors, run.get("mutation_attempted") is False and run.get("shutdown_required") is False, f"run sequence entry {index} historical diagnostic claims mutation/shutdown requirement")
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
                if diagnostic_only:
                    # Historical variants preserve their exact failed child
                    # topology in the hash-bound epoch validator.  Recovery is
                    # audited separately and must never rewrite that fact.
                    if label == "preflight":
                        append_error(
                            errors,
                            recorded_historical_epoch.get("inner_preflight_process_tree_reaped")
                            is block.get("process_tree_reaped"),
                            f"run sequence entry {index} historical inner-preflight reap fact mismatch",
                        )
                    continue
                append_error(errors, block.get("process_tree_reaped") is True, f"run sequence entry {index} {label} child tree was not reaped")
        candidate_key = "ps_process" if candidate.kind == "ps" else "stage_process"
        if isinstance(candidate.data.get(candidate_key), dict):
            errors.extend(f"run sequence entry {index}: {item}" for item in authorized_event_errors(candidate, evidence))
        source = str(candidate.data.get("safety_validation", {}).get("source_commit_requested", "")).lower()
        append_error(errors, run.get("source_commit") == source, f"run sequence entry {index} source commit mismatch")
        if diagnostic_only:
            append_error(errors, source != offline_commit, f"run sequence entry {index} historical source was relabeled as active checkpoint")
        else:
            append_error(errors, source == offline_commit, f"run sequence entry {index} source/offline commit mismatch")
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
            require_clean = (
                not failed_stage_diagnostic
                and (which == "after" or _candidate_programmed(candidate) or expected_pass)
            )
            if require_clean:
                append_error(errors, isinstance(shutdown, dict) and shutdown.get("returncode") == 0 and shutdown.get("passed") is True, f"run sequence entry {index} shutdown-{which} rc/PASS invalid")
            else:
                append_error(errors, isinstance(shutdown, dict) and shutdown.get("present") is True, f"run sequence entry {index} shutdown-before attempt record missing")
            if isinstance(shutdown, dict):
                append_error(errors, shutdown.get("result_marker_duplicates") == [], f"run sequence entry {index} shutdown-{which} result has duplicate markers")
                if require_clean:
                    append_error(errors, shutdown.get("attempted") is True, f"run sequence entry {index} shutdown-{which} attempted flag missing")
                    append_error(errors, shutdown.get("programming_attempted") is True, f"run sequence entry {index} shutdown-{which} programming-attempt flag missing")
                    append_error(errors, shutdown.get("programming_attempted_marker") is True, f"run sequence entry {index} shutdown-{which} fresh programming-attempt marker missing")
                    append_error(errors, shutdown.get("tfdu_shutdown_marker") is True, f"run sequence entry {index} shutdown-{which} fresh TFDU marker missing")
                    append_error(errors, shutdown.get("tfdu_shutdown_path_matches_authorized") is True, f"run sequence entry {index} shutdown-{which} TFDU path is not the authorized shutdown bit")
                    append_error(errors, shutdown.get("p7_shutdown_result_pass") is True, f"run sequence entry {index} P7 shutdown-{which} result missing")
                for field in ("result_file", "stdout_file"):
                    if shutdown.get(field, {}).get("missing") is True and not require_clean:
                        continue
                    file_errors, _record = verify_hash_record(
                        f"run sequence entry {index} shutdown-{which} {field}", shutdown.get(field), document=ledger_path, repo_root=evidence.repo_root, expected_required=False
                    )
                    errors.extend(file_errors)

        if diagnostic_only:
            continue
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
    errors.extend(_historical_epoch_order_errors(historical_epochs, evidence))
    append_error(errors, ordered_starts == sorted(ordered_starts), "run sequence UTC start order is not chronological")
    append_error(
        errors,
        all(previous_end <= next_start for (_previous_start, previous_end), (next_start, _next_end) in zip(ordered_intervals, ordered_intervals[1:])),
        "run sequence contains overlapping hardware stages",
    )
    stationary_pass_indices = [
        index
        for index, run in enumerate(runs)
        if isinstance(run, dict)
        and run.get("checkpoint_relation") == CHECKPOINT_RELATION_BOUND
        and "ps_stationary_qualified" in run.get("coverage_keys", [])
    ]
    append_error(errors, len(stationary_pass_indices) <= 1, "run sequence contains more than one qualified stationary PASS")
    stationary_launch_indices = [
        index
        for index, run in enumerate(runs)
        if isinstance(run, dict)
        and run.get("checkpoint_relation") == CHECKPOINT_RELATION_BOUND
        and run.get("stage") == "stationary"
    ]
    append_error(errors, len(stationary_launch_indices) <= 1, "run sequence contains more than one final stationary launch intent")
    if stationary_launch_indices:
        append_error(errors, stationary_launch_indices[0] == len(runs) - 1, "stationary launch intent is not the final executed hardware stage")
    if stationary_pass_indices:
        append_error(errors, stationary_pass_indices[0] == len(runs) - 1, "qualified stationary PASS is not the final executed hardware stage")
    bound_starts = [
        parse_time(run.get("started_at_utc"), float("nan"))
        for run in runs
        if isinstance(run, dict) and run.get("checkpoint_relation") == CHECKPOINT_RELATION_BOUND
    ]
    historical_ends = [
        parse_time(
            run.get("historical_epoch", {}).get("ended_at_utc")
            if isinstance(run.get("historical_epoch"), dict)
            else None,
            float("nan"),
        )
        for run in runs
        if isinstance(run, dict) and run.get("checkpoint_relation") in CHECKPOINT_RELATIONS_HISTORICAL
    ]
    append_error(errors, all(value == value and value >= offline_time for value in bound_starts), "one or more active-checkpoint runs started before checkpoint freeze")
    append_error(errors, all(value == value and value <= offline_time for value in historical_ends), "one or more historical diagnostic epochs ended after checkpoint freeze")
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


def audit_all_shutdowns(
    evidence: RepositoryEvidence,
    candidates: Sequence[Candidate] | None = None,
) -> StageResult:
    errors: list[str] = []
    audited = 0
    evidence_paths: list[str] = []
    for candidate in evidence.candidates if candidates is None else candidates:
        mutated = _candidate_mutation_attempted(candidate)
        if not mutated:
            continue
        audited += 1
        evidence_paths.append(rel(candidate.path, evidence.repo_root))
        if not candidate.executed:
            errors.append(f"{rel(candidate.path, evidence.repo_root)}: hardware footprint contradicts hardware_actions_executed=true")
        for item in shutdown_errors(candidate, "after", evidence=evidence):
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
    ledger_path = evidence.hardware_root / "p7_run_sequence_ledger.json"
    try:
        ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        ledger_payload = {}
    ledger_offline = ledger_payload.get("offline_checkpoint") if isinstance(ledger_payload, dict) else None
    active_commit = (
        str(ledger_offline.get("source_commit", "")).lower()
        if isinstance(ledger_offline, dict)
        else ""
    )
    checkpoint_scoped = COMMIT_RE.fullmatch(active_commit) is not None
    active_candidates = [
        candidate
        for candidate in evidence.candidates
        if not checkpoint_scoped or _candidate_source_commit(candidate) == active_commit
    ]
    by_stage: dict[str, list[Candidate]] = {}
    for candidate in active_candidates:
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

    results["shutdown"] = audit_all_shutdowns(evidence, active_candidates)
    consistency_errors = list(evidence.parse_errors)
    partial_files = [row["path"] for row in evidence.inventory if str(row.get("path", "")).casefold().endswith((".write_partial", ".partial", ".tmp"))]
    if partial_files:
        consistency_errors.append(f"uncommitted/partial hardware evidence files remain: {partial_files}")
    consistency_errors.extend(verify_loose_hash_manifests(evidence))
    active_provenance_rows = [
        row for row in evidence.provenance_rows
        if not checkpoint_scoped or str(row.get("source_commit", "")).lower() == active_commit
    ]
    consistency_errors.extend(provenance_consistency_errors(active_provenance_rows))
    consistency_errors.extend(stationary_uniqueness_errors)
    for stage_name, stage_result in results.items():
        if stage_name != "consistency" and stage_result.status == "FAIL":
            consistency_errors.append(f"mandatory stage evidence is internally inconsistent: {stage_name}")
    ledger_status, ledger_errors, ledger_metrics = validate_sequence_ledger(evidence)
    consistency_errors.extend(ledger_errors)
    unclassified_executed = [item for item in active_candidates if item.executed and item.stage.startswith("unclassified")]
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
        sorted({row.get("summary", "") for row in active_provenance_rows if row.get("summary")})
        + ([rel(evidence.hardware_root / "p7_run_sequence_ledger.json", evidence.repo_root)] if (evidence.hardware_root / "p7_run_sequence_ledger.json").is_file() else []),
        metrics={
            "inventory_files": len(evidence.inventory),
            "selected_provenance_rows": len(active_provenance_rows),
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
    ledger_path = evidence.hardware_root / "p7_run_sequence_ledger.json"
    try:
        ledger_payload = json.loads(ledger_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        ledger_payload = {}
    ledger_offline = ledger_payload.get("offline_checkpoint") if isinstance(ledger_payload, dict) else None
    active_commit = str(ledger_offline.get("source_commit", "")).lower() if isinstance(ledger_offline, dict) else ""
    checkpoint_scoped = COMMIT_RE.fullmatch(active_commit) is not None
    provenance = [
        row for row in evidence.provenance_rows
        if not checkpoint_scoped or str(row.get("source_commit", "")).lower() == active_commit
    ]
    source_commits = sorted({str(row.get("source_commit")) for row in provenance if row.get("source_commit")})
    source_commit = active_commit if checkpoint_scoped else source_commits[0] if len(source_commits) == 1 else "INCONSISTENT_OR_MISSING"
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
        "BITSTREAM_SHA256": bit_hashes[0] if len(bit_hashes) == 1 else "PENDING_HW" if not bit_hashes and final.status == "PENDING_HW" else "INCONSISTENT_OR_MISSING",
        "PS_ELF_SHA256": elf_hashes[0] if len(elf_hashes) == 1 else "PENDING_HW" if not elf_hashes and final.status == "PENDING_HW" else "INCONSISTENT_OR_MISSING",
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
