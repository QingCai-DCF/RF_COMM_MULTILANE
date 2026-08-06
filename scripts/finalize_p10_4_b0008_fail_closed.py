#!/usr/bin/env python3
"""Close P10.4 offline after the reproducible current F2-to-R2 blocker.

This program is deliberately offline-only.  It validates the immutable B0008
qualification and the three later fail-closed runs, verifies their complete
SHA256 manifests and consumed authorizations, then publishes the terminal
audit/state/requirement records.  It never opens a hardware tool or starts TX.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_p10_4_hardware as campaign  # noqa: E402
from p8a_common import (  # noqa: E402
    REQUIREMENTS_PATH,
    STATE_PATH,
    STATUS_PATH,
    TRACEABILITY_PATH,
    load_json,
    render_project_status,
    validate_requirements,
    validate_state,
)


SCOPE = "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT"
BRANCH = "p10.4/autonomous-4lane-hardening"
GOAL = ROOT / "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md"
GOAL_SHA256 = "0098acc827d22ad8f72876f5551e70d8051452e0c81eb2bfe8986e142f47254f"
SOURCE_COMMIT = "6ff17d33a0ea111fbd796899c49decbfa339e2c1"
EVIDENCE_CHECKPOINT = "6c0f074f233d94c5f42f494263eae40ec350d5be"
FINAL_TAG = "p10.4-autonomous-4lane-hardening-investigated-b0008-f2-r2"

QUALIFICATION_RUN = "p10_4_l2b0008raw_20260806T072322Z_6ff17d33_94506af9_2b2b37d4"
FULL_RUN = "p10_4_20260806T074331Z_6ff17d33_94506af9_2b2b37d4"
RECOVERY_RUN = "p10_4_20260806T091241Z_6ff17d33_94506af9_2b2b37d4"
MATRIX_RUN = "p10_4_20260806T092551Z_6ff17d33_94506af9_2b2b37d4"

GENERATED = ROOT / "evidence/generated"
QUALIFICATION_SUMMARY = GENERATED / "p10_4_lane2_b0008_raw_connectivity_retest.json"
QUALIFICATION_ROOT = ROOT / "evidence/hardware/p10_4_raw_connectivity" / QUALIFICATION_RUN
FULL_ROOT = ROOT / "evidence/hardware/p10_4" / FULL_RUN
RECOVERY_ROOT = ROOT / "evidence/hardware/p10_4" / RECOVERY_RUN
MATRIX_ROOT = ROOT / "evidence/hardware/p10_4" / MATRIX_RUN

FULL_RESULT = FULL_ROOT / "final/orchestrator_result.json"
RECOVERY_RESULT = RECOVERY_ROOT / "final/lane_recovery_diagnostic_result.json"
MATRIX_RESULT = MATRIX_ROOT / "final/echo_crosstalk_8x8_diagnostic_result.json"
FULL_LANE_FIXED = FULL_ROOT / "forensics/lane_recovery/fixed.p10ff.json"
FULL_LANE_ROTATING = FULL_ROOT / "forensics/lane_recovery/rotating.p10ff.json"
RECOVERY_FIXED = RECOVERY_ROOT / "forensics/lane_recovery/fixed.p10ff.json"
RECOVERY_ROTATING = RECOVERY_ROOT / "forensics/lane_recovery/rotating.p10ff.json"

FULL_AUTH = ROOT / "config/p10_4_b0008_current_run_hardware_authorization.json"
RECOVERY_AUTH = ROOT / "config/p10_4_lane_recovery_diagnostic_current_run_authorization.json"
MATRIX_AUTH = ROOT / "config/p10_4_echo_crosstalk_8x8_diagnostic_current_run_authorization.json"

BLOCKER = GENERATED / "p10_4_f2_to_r2_directional_blocker.json"
AUDIT = GENERATED / "p10_4_completion_audit.json"
CLOSURE = GENERATED / "p10_4_terminal_offline_closure.json"
FINAL_SUMMARY = GENERATED / "p10_4_final_summary.json"
SHUTDOWN = GENERATED / "p10_4_shutdown.json"
XTALK = GENERATED / "p10_4_echo_crosstalk.json"
CONSISTENCY = GENERATED / "p10_4_evidence_consistency.json"
FINAL_MANIFEST = GENERATED / "p10_4_b0008_fail_closed_manifest.json"

BOARD_BINDING = {
    "fixed": "AX7020-F/JTAG:210249855178",
    "rotating": "AX7020-R/JTAG:210512180081",
}
MODULE_BINDING = {
    "F0": "A0019", "F1": "B0012", "F2": "B0008", "F3": "B0020",
    "R0": "A0010", "R1": "A0017", "R2": "B0023", "R3": "B0025",
}
EXPECTED_ARTIFACTS = {
    ("fixed", "functional_bitstream"): "94506af98a1fa90f6ad9dea3f29ffc6addb3b3e6bb9090bbfe4423c25d8efe3b",
    ("rotating", "functional_bitstream"): "2b2b37d47240680851fb52848943e6d7845dbbc3267d348f3ec4d33b0446e06e",
    ("fixed", "elf"): "dce91dd7172851da0ea0c6794c8eabf61f4214fddffdcb38002e1ae1404d61fb",
    ("rotating", "elf"): "a15b4b4472070632e1c4273392ddc500bd4e389e7bc2035301a1c3e2d55984e1",
    ("fixed", "shutdown_bitstream"): "7073abf6820d7a89829bc162db772274a5d62b855f1177de2f9e5c35de0de762",
    ("rotating", "shutdown_bitstream"): "d938cb6494d23127c364dac80a000f088de71bb527ed19e9511179a484461c36",
}

FULL_EXPECTED_STAGES = [
    ("P10_4-PREFLIGHT", "PASS"),
    ("P10_4-COUNTER_LOCAL_SOURCE", "PASS"),
    ("P10_4-COUNTER_SEMANTICS", "PASS"),
    ("P10_4-BASELINE_SMOKE", "PASS"),
    ("P10_4-TUNING", "PASS"),
    ("P10_4-HALF_DUPLEX", "PASS"),
    ("P10_4-STREAMING_64M", "PASS"),
    ("P10_4-STREAMING_128M", "PASS"),
    ("P10_4-LANE_RECOVERY", "FAIL"),
]

REQUIREMENT_DISPOSITIONS = {
    "P10_4-CLOSE-001": ("PASS", "evidence/generated/p10_4_p10_3_closeout.json"),
    "P10_4-METRIC-001": ("PASS", "evidence/generated/p10_4_counter_semantics.json"),
    "P10_4-MODEL-001": ("PASS", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-PERF-001": ("PASS", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-PERF-002": ("PASS", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-PERF-003": ("FAIL", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-STREAM-001": ("PASS", "evidence/generated/p10_4_streaming_64m.json"),
    "P10_4-STREAM-002": ("PASS", "evidence/generated/p10_4_streaming_64m.json"),
    "P10_4-DEG-001": ("FAIL", "evidence/generated/p10_4_degraded_modes.json"),
    "P10_4-DIR-001": ("PENDING", "evidence/generated/p10_4_direction_switch.json"),
    "P10_4-RESET-001": ("PENDING", "evidence/generated/p10_4_reset_recovery.json"),
    "P10_4-XTALK-001": ("FAIL", "evidence/generated/p10_4_echo_crosstalk.json"),
    "P10_4-XTALK-002": ("PENDING", "evidence/generated/p10_4_crc_bad_remediation.json"),
    "P10_4-FD-001": ("PENDING", "evidence/generated/p10_4_two_plus_two.json"),
    "P10_4-SOAK-001": ("PENDING", "evidence/generated/p10_4_mixed_30min.json"),
    "P10_4-SAFE-001": ("PASS", "evidence/generated/p10_4_shutdown.json"),
}


class CloseoutError(RuntimeError):
    """Raised when immutable closeout inputs do not match their contract."""


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CloseoutError(message)


def record(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing evidence file: {rel(path)}")
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def write_markdown(path: Path, title: str, lines: Iterable[str]) -> None:
    content = [f"# {title}", "", *lines]
    path.with_suffix(".md").write_text(
        "\n".join(content).rstrip() + "\n", encoding="utf-8", newline="\n"
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def verify_run_manifest(run_root: Path) -> dict[str, Any]:
    path = run_root / "final/run_evidence_sha256_manifest.json"
    manifest = load_json(path)
    errors = campaign.verify_evidence_manifest(run_root, manifest)
    require(not errors, f"{rel(run_root)} manifest verification failed: {errors}")
    return {
        **record(path),
        "status": "PASS",
        "file_count": len(manifest.get("files", [])),
    }


def all_shutdown_pass(summary: dict[str, Any]) -> bool:
    shutdowns = summary.get("shutdowns", [])
    return bool(shutdowns) and all(
        isinstance(item, dict)
        and item.get("status") == "PASS"
        and item.get("SHUTDOWN_FIXED") == "PASS"
        and item.get("SHUTDOWN_ROTATING") == "PASS"
        for item in shutdowns
    )


def raw_qualification_vectors(summary: dict[str, Any]) -> list[dict[str, Any]]:
    vectors: list[dict[str, Any]] = []
    for direction in summary.get("directions", []):
        for label, case in direction.get("case_results", {}).items():
            if not label.endswith(("raw_64", "raw_1024")):
                continue
            vectors.append({
                "label": label,
                "direction": direction.get("direction"),
                "status": case.get("status"),
                "requested_raw_pulses": case.get("requested_raw_pulses"),
                "sender_module": case.get("sender_module"),
                "receiver_module": case.get("receiver_module"),
                "sender_physical_tx_count": case.get("sender_physical_tx_count"),
                "receiver_raw_rx_count": case.get("receiver_raw_rx_count"),
                "tx_high_max_cycles": case.get("tx_high_max_cycles"),
                "rolling_duty_high_max_cycles": case.get("rolling_duty_high_max_cycles"),
                "evidence_class": direction.get("evidence_class"),
            })
    return sorted(vectors, key=lambda item: str(item["label"]))


def module_snapshot(document: dict[str, Any], index: int) -> dict[str, Any]:
    modules = document.get("snapshot", {}).get("modules", [])
    matches = [item for item in modules if item.get("module_index") == index]
    require(len(matches) == 1, f"module snapshot {index} missing or duplicated")
    return matches[0]


def verify_authorization(path: Path, run_id: str, status_fragment: str) -> dict[str, Any]:
    value = load_json(path)
    require(value.get("run_id") == run_id, f"{rel(path)} run ID mismatch")
    require(value.get("source_commit") == SOURCE_COMMIT, f"{rel(path)} source mismatch")
    require(value.get("goal_sha256") == GOAL_SHA256, f"{rel(path)} Goal mismatch")
    require(value.get("consumed") is True, f"{rel(path)} is not consumed")
    require(value.get("current_run_hardware_authorization") is False,
            f"{rel(path)} remains current")
    require(status_fragment in str(value.get("status")), f"{rel(path)} lifecycle mismatch")
    return {**record(path), "status": value["status"], "consumed": True,
            "current_run_hardware_authorization": False, "run_id": run_id}


def verify_artifacts(full: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = full.get("artifacts", [])
    by_key = {
        (str(item.get("role")), str(item.get("kind"))): item
        for item in artifacts if isinstance(item, dict)
    }
    for key, digest in EXPECTED_ARTIFACTS.items():
        require(key in by_key, f"artifact missing: {key}")
        item = by_key[key]
        require(item.get("sha256") == digest, f"artifact hash mismatch: {key}")
        path = ROOT / str(item.get("path"))
        require(path.is_file() and sha256(path) == digest,
                f"artifact bytes mismatch: {key}")
    return artifacts


def collect_and_verify() -> dict[str, Any]:
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be exactly 1")
    require(
        os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() == "false",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false",
    )
    require(git("branch", "--show-current").stdout.strip() == BRANCH, "wrong branch")
    require(GOAL.is_file() and sha256(GOAL) == GOAL_SHA256, "Goal SHA256 mismatch")
    require(
        git("merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD", check=False).returncode == 0,
        "artifact source commit is not an ancestor",
    )
    require(
        git("merge-base", "--is-ancestor", EVIDENCE_CHECKPOINT, "HEAD", check=False).returncode == 0,
        "latest hardware evidence checkpoint is not an ancestor",
    )

    qualification = load_json(QUALIFICATION_SUMMARY)
    require(qualification.get("status") == "PASS", "B0008 raw qualification is not PASS")
    require(qualification.get("run_id") == QUALIFICATION_RUN, "qualification run mismatch")
    require(qualification.get("module_binding") == {"F2": "B0008", "R2": "B0023"},
            "qualification module binding mismatch")
    require(qualification.get("SHUTDOWN_FIXED") == "PASS", "qualification fixed shutdown failed")
    require(qualification.get("SHUTDOWN_ROTATING") == "PASS", "qualification rotating shutdown failed")
    qualification_vectors = raw_qualification_vectors(qualification)
    require(len(qualification_vectors) == 4, "qualification raw vector set is incomplete")
    for vector in qualification_vectors:
        require(vector["status"] == "PASS", f"qualification vector failed: {vector['label']}")
        require(vector["evidence_class"] == "RAW_PHYSICAL_ONLY",
                f"qualification evidence class mismatch: {vector['label']}")
        require(vector["sender_physical_tx_count"] == vector["requested_raw_pulses"],
                f"qualification TX count mismatch: {vector['label']}")
        require(vector["receiver_raw_rx_count"] == vector["requested_raw_pulses"],
                f"qualification RX count mismatch: {vector['label']}")

    full = load_json(FULL_RESULT)
    recovery = load_json(RECOVERY_RESULT)
    matrix = load_json(MATRIX_RESULT)
    for label, value, run_id, expected_status in (
        ("full", full, FULL_RUN, "PARTIAL"),
        ("recovery", recovery, RECOVERY_RUN, "FAIL_CLOSED"),
        ("matrix", matrix, MATRIX_RUN, "FAIL_CLOSED"),
    ):
        require(value.get("status") == expected_status, f"{label} status mismatch")
        require(value.get("run_id") == run_id, f"{label} run mismatch")
        require(value.get("artifact_source_commit") == SOURCE_COMMIT,
                f"{label} artifact source mismatch")
        require(value.get("goal_sha256") == GOAL_SHA256, f"{label} Goal mismatch")
        require(value.get("SHUTDOWN_FIXED") == "PASS", f"{label} fixed shutdown failed")
        require(value.get("SHUTDOWN_ROTATING") == "PASS", f"{label} rotating shutdown failed")
        require(value.get("current_run_hardware_authorization") is False,
                f"{label} authorization remains current")
        require(all_shutdown_pass(value), f"{label} contains an unconfirmed shutdown")

    actual_stages = [(item.get("test_id"), item.get("status")) for item in full["stages"]]
    require(actual_stages == FULL_EXPECTED_STAGES, "full campaign stage order/status mismatch")
    require(full.get("board_binding") == BOARD_BINDING, "board binding mismatch")
    require(full.get("module_binding") == MODULE_BINDING, "module binding mismatch")
    artifacts = verify_artifacts(full)

    full_fixed = load_json(FULL_LANE_FIXED)
    full_rotating = load_json(FULL_LANE_ROTATING)
    full_f2 = module_snapshot(full_fixed, 2)
    full_r2 = module_snapshot(full_rotating, 2)
    require(full_f2.get("physical_tx_count") == 75_564_719,
            "full-campaign F2 TX snapshot mismatch")
    require(full_r2.get("raw_rx_count") == 30_943_083,
            "full-campaign R2 RX snapshot mismatch")

    recovery_fixed = load_json(RECOVERY_FIXED)
    recovery_rotating = load_json(RECOVERY_ROTATING)
    recovery_f2 = module_snapshot(recovery_fixed, 2)
    recovery_r2 = module_snapshot(recovery_rotating, 2)
    require(recovery_f2.get("physical_tx_count") == 60_796_539,
            "isolated-recovery F2 TX snapshot mismatch")
    require(recovery_r2.get("raw_rx_count") == 7_915,
            "isolated-recovery R2 RX snapshot mismatch")

    details = matrix.get("stage", {}).get("details", [])
    f2_raw64 = [item for item in details if item.get("label") == "matrix_F2_raw64"]
    require(len(f2_raw64) == 1, "matrix F2 raw64 vector missing or duplicated")
    f2_raw64 = f2_raw64[0]
    fixed_modules = f2_raw64["fixed_p10_2"]["modules"]
    rotating_modules = f2_raw64["rotating_p10_2"]["modules"]
    require(fixed_modules[2].get("physical_tx") == 64, "matrix F2 TX count mismatch")
    require(rotating_modules[6].get("raw_rx") == 0, "matrix R2 RX count mismatch")
    require(f2_raw64["fixed"].get("command_status") == 0,
            "matrix fixed raw command status mismatch")
    require(f2_raw64["rotating"].get("command_status") == 14,
            "matrix rotating raw command did not report receive failure")
    require(fixed_modules[2].get("tx_high_max") == 8, "matrix F2 TX-high maximum mismatch")
    require(fixed_modules[2].get("duty_high_max") == 504, "matrix F2 duty maximum mismatch")
    require(all(item.get("hard_fault") == 0 for item in fixed_modules + rotating_modules),
            "matrix hard-fault counter is nonzero")
    semantics = matrix["stage"]["semantics"]
    require(semantics.get("raw_vectors") == 9, "matrix completed raw-vector count mismatch")
    require(semantics.get("same_module_accepted_data_or_control") == 0,
            "matrix same-module accepted data/control is nonzero")
    require(semantics.get("cross_lane_accepted_data_or_control") == 0,
            "matrix cross-lane accepted data/control is nonzero")
    completed_frame_windows = [
        item for item in semantics.get("frame_windows", []) if item.get("commands", 0) > 0
    ]
    require([item.get("label") for item in completed_frame_windows] == [
        "matrix_F0_frame30s", "matrix_R0_frame30s",
        "matrix_F1_frame30s", "matrix_R1_frame30s",
    ], "matrix completed frame-window prefix mismatch")

    manifests = {
        "qualification": verify_run_manifest(QUALIFICATION_ROOT),
        "full_campaign": verify_run_manifest(FULL_ROOT),
        "isolated_lane_recovery": verify_run_manifest(RECOVERY_ROOT),
        "isolated_echo_crosstalk": verify_run_manifest(MATRIX_ROOT),
    }
    authorizations = {
        "full_campaign": verify_authorization(FULL_AUTH, FULL_RUN, "CONSUMED_AFTER_P10_4_PARTIAL"),
        "isolated_lane_recovery": verify_authorization(
            RECOVERY_AUTH, RECOVERY_RUN, "LANE_RECOVERY_DIAGNOSTIC_FAIL_CLOSED"
        ),
        "isolated_echo_crosstalk": verify_authorization(
            MATRIX_AUTH, MATRIX_RUN, "ECHO_CROSSTALK_8X8_DIAGNOSTIC_FAIL_CLOSED"
        ),
    }

    counters = full.get("counters", {})
    for name in (
        "continuous_high_violation", "crc_bad", "cross_lane_accepted_data",
        "deadlock", "descriptor_leak", "double_completion", "duplicate_commit",
        "duty_violation", "partial_commit", "retry_exhausted",
        "same_module_accepted_data", "sha_mismatch", "stale_commit",
    ):
        require(counters.get(name) == 0, f"campaign counter is nonzero: {name}")

    return {
        "qualification": qualification,
        "qualification_vectors": qualification_vectors,
        "full": full,
        "recovery": recovery,
        "matrix": matrix,
        "full_fixed": full_fixed,
        "full_rotating": full_rotating,
        "recovery_fixed": recovery_fixed,
        "recovery_rotating": recovery_rotating,
        "full_f2": full_f2,
        "full_r2": full_r2,
        "recovery_f2": recovery_f2,
        "recovery_r2": recovery_r2,
        "matrix_f2_raw64": f2_raw64,
        "matrix_completed_windows": completed_frame_windows,
        "artifacts": artifacts,
        "manifests": manifests,
        "authorizations": authorizations,
    }


def source_record(path: Path) -> dict[str, Any]:
    return record(path)


def requirement_audit_rows() -> list[dict[str, Any]]:
    reason = {
        "P10_4-CLOSE-001": "P10.3 immutable closeout rechecked",
        "P10_4-METRIC-001": "direct counter semantics and local-source injection passed",
        "P10_4-MODEL-001": "both 300-second windows reconciled to the frozen airtime model",
        "P10_4-PERF-001": "F-to-R 300-second goodput was 8,388,608 bit/s",
        "P10_4-PERF-002": "R-to-F 300-second goodput was 8,416,570.026666667 bit/s",
        "P10_4-PERF-003": "both directions were below the nonblocking 9 Mbit/s target",
        "P10_4-STREAM-001": "ten exact 64 MiB F-to-R objects passed",
        "P10_4-STREAM-002": "ten exact 64 MiB R-to-F objects passed",
        "P10_4-DEG-001": "lane recovery failed repeatedly on current F2-to-R2 path",
        "P10_4-DIR-001": "not executed after fail-closed trigger",
        "P10_4-RESET-001": "not executed after fail-closed trigger",
        "P10_4-XTALK-001": "8x8 matrix stopped at F2 raw64: 64 TX / 0 remote RX",
        "P10_4-XTALK-002": "required current-hardware masks/formal coverage not completed",
        "P10_4-FD-001": "2+2 experiment not executed after fail-closed trigger",
        "P10_4-SOAK-001": "1800-second mixed formal not executed after fail-closed trigger",
        "P10_4-SAFE-001": "all four current-B0008 runs ended with verified dual shutdown",
    }
    return [
        {"requirement_id": req_id, "status": status, "reason": reason[req_id],
         "evidence_path": evidence}
        for req_id, (status, evidence) in REQUIREMENT_DISPOSITIONS.items()
    ]


def build_payloads(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    full = data["full"]
    matrix = data["matrix"]
    f2_raw64 = data["matrix_f2_raw64"]
    fixed_modules = f2_raw64["fixed_p10_2"]["modules"]
    rotating_modules = f2_raw64["rotating_p10_2"]["modules"]
    full_f2 = data["full_f2"]
    full_r2 = data["full_r2"]
    recovery_f2 = data["recovery_f2"]
    recovery_r2 = data["recovery_r2"]

    artifact_hashes = {
        f"{item['role']}_{item['kind']}": item["sha256"]
        for item in data["artifacts"]
        if (item.get("role"), item.get("kind")) in EXPECTED_ARTIFACTS
    }
    direct_timeline = [
        {
            "sequence": 1,
            "classification": "SHORT_RAW_QUALIFICATION_PASS",
            "run_id": QUALIFICATION_RUN,
            "module_binding": {"F2": "B0008", "R2": "B0023"},
            "evidence_class": "RAW_PHYSICAL_ONLY",
            "vectors": data["qualification_vectors"],
            "interpretation": (
                "A short current-artifact check passed both physical directions at 64 and "
                "1024 requested pulses. It was not a DATA or sustained-path acceptance."
            ),
        },
        {
            "sequence": 2,
            "classification": "FULL_CAMPAIGN_LANE2_CLEAN64_FAILURE",
            "run_id": FULL_RUN,
            "stage": "lane_recovery/lane2_clean64",
            "sender": "F2/B0008",
            "receiver": "R2/B0023",
            "sender_physical_tx": full_f2["physical_tx_count"],
            "receiver_raw_rx": full_r2["raw_rx_count"],
            "receiver_to_sender_ratio": full_r2["raw_rx_count"] / full_f2["physical_tx_count"],
            "tx_retries": data["full_fixed"]["snapshot"]["tx_retry_count"],
            "tx_timeouts": data["full_fixed"]["snapshot"]["tx_timeout_count"],
            "tx_migrations": data["full_fixed"]["snapshot"]["tx_migration_count"],
            "retry_exhausted": data["full_fixed"]["snapshot"]["tx_retry_exhausted_count"],
            "fault_cause": data["full_fixed"]["snapshot"]["fault_cause"],
            "safety_fault": False,
            "result": "FAIL_REMOTE_RAW_LOSS",
        },
        {
            "sequence": 3,
            "classification": "ISOLATED_LANE_RECOVERY_FAILURE",
            "run_id": RECOVERY_RUN,
            "stage": "lane_recovery/lane0_unavailable",
            "explicitly_unavailable_lane": 0,
            "unexpected_failed_path": "F2_TO_R2",
            "sender": "F2/B0008",
            "receiver": "R2/B0023",
            "sender_physical_tx": recovery_f2["physical_tx_count"],
            "receiver_raw_rx": recovery_r2["raw_rx_count"],
            "receiver_to_sender_ratio": recovery_r2["raw_rx_count"] / recovery_f2["physical_tx_count"],
            "tx_retries": data["recovery_fixed"]["snapshot"]["tx_retry_count"],
            "tx_timeouts": data["recovery_fixed"]["snapshot"]["tx_timeout_count"],
            "tx_migrations": data["recovery_fixed"]["snapshot"]["tx_migration_count"],
            "retry_exhausted": data["recovery_fixed"]["snapshot"]["tx_retry_exhausted_count"],
            "fault_cause": data["recovery_fixed"]["snapshot"]["fault_cause"],
            "safety_fault": False,
            "result": "FAIL_REMOTE_RAW_LOSS_NOT_STALE_UNAVAILABLE_MASK",
        },
        {
            "sequence": 4,
            "classification": "ISOLATED_MATRIX_RAW64_FAILURE",
            "run_id": MATRIX_RUN,
            "stage": "echo_crosstalk_8x8/matrix_F2_raw64",
            "sender": "F2/B0008",
            "receiver": "R2/B0023",
            "requested_raw_pulses": 64,
            "sender_physical_tx": fixed_modules[2]["physical_tx"],
            "receiver_raw_rx": rotating_modules[6]["raw_rx"],
            "fixed_command_status": f2_raw64["fixed"]["command_status"],
            "rotating_command_status": f2_raw64["rotating"]["command_status"],
            "continuous_high_max_cycles": fixed_modules[2]["tx_high_max"],
            "rolling_duty_max_cycles": fixed_modules[2]["duty_high_max"],
            "rolling_duty_window_cycles": 64_000,
            "hard_fault_count": 0,
            "result": "FAIL_64_TX_0_REMOTE_RAW_RX",
        },
    ]

    blocker = {
        "schema_version": 2,
        "test_id": "P10_4-F2-R2-DIRECTIONAL-BLOCKER-B0008",
        "scope": SCOPE,
        "status": "FAIL_CLOSED_PHYSICAL_DIRECTIONAL_BLOCKER",
        "classification": "CURRENT_DIRECT_RAW_PHYSICAL_DIRECTIONAL_PATH_FAILURE",
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "latest_hardware_evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "latest_run_id": MATRIX_RUN,
        "board_binding": BOARD_BINDING,
        "module_binding": MODULE_BINDING,
        "artifact_sha256": artifact_hashes,
        "timeline": direct_timeline,
        "reproduction_count_after_short_qualification": 3,
        "terminal_matrix_measurement": {
            "direction": "F2_TO_R2",
            "requested_raw_pulses": 64,
            "sender_physical_tx": 64,
            "receiver_raw_rx": 0,
            "evidence_class": "RAW_PHYSICAL_ONLY",
        },
        "safety_observation": {
            "continuous_high_max_cycles": 8,
            "rolling_duty_max_cycles": 504,
            "rolling_duty_window_cycles": 64_000,
            "rolling_duty_fraction": 504 / 64_000,
            "hard_fault_count": 0,
            "safety_limit_breach_observed_by_pl": False,
            "external_electrical_or_optical_waveform_measured": False,
            "boundary": (
                "PL counters show no configured high-time, duty or hard-fault breach. "
                "No external electrical/optical measurement was permitted, so this is not "
                "external proof of the analog waveform or component health."
            ),
        },
        "root_cause_boundary": (
            "The current evidence localizes an intermittent/reproducible F2-to-R2 physical "
            "directional path loss. Without the forbidden physical intervention or external "
            "instrumentation it cannot distinguish F2 emitter/module, optical path/alignment, "
            "R2 receiver/module, local power/connection, or another analog path cause."
        ),
        "not_claimed": [
            "DATA_PATH_PASS", "COMPONENT_SPECIFIC_ROOT_CAUSE", "EXTERNAL_ELECTRICAL_PASS",
            "P11_PASS", "PRODUCT_FINAL_PASS",
        ],
        "terminal_action": {
            "new_tx_stopped": True,
            "arm_revoked_by_fail_closed_exit": True,
            "current_run_hardware_authorization": False,
            "shutdown_fixed": "PASS",
            "shutdown_rotating": "PASS",
            "further_hardware_runs_allowed_by_this_closeout": False,
        },
        "raw_evidence": {
            "qualification": source_record(QUALIFICATION_SUMMARY),
            "full_campaign": source_record(FULL_RESULT),
            "isolated_lane_recovery": source_record(RECOVERY_RESULT),
            "isolated_matrix": source_record(MATRIX_RESULT),
            "manifests": data["manifests"],
        },
        "disposition": "TERMINAL_FAIL_CLOSED_NO_FURTHER_HARDWARE_ACTION",
    }

    executed_stage_rows = [
        {
            "test_id": item["test_id"],
            "status": item["status"],
            "evidence_path": rel(FULL_ROOT / "stages" / {
                "P10_4-PREFLIGHT": "preflight",
                "P10_4-COUNTER_LOCAL_SOURCE": "counter_local_source",
                "P10_4-COUNTER_SEMANTICS": "counter_semantics",
                "P10_4-BASELINE_SMOKE": "baseline_smoke",
                "P10_4-TUNING": "tuning",
                "P10_4-HALF_DUPLEX": "half_duplex",
                "P10_4-STREAMING_64M": "streaming_64m",
                "P10_4-STREAMING_128M": "streaming_128m",
                "P10_4-LANE_RECOVERY": "lane_recovery",
            }[item["test_id"]] / "stage_summary.json"),
        }
        for item in full["stages"]
    ]
    audit = {
        "schema_version": 2,
        "test_id": "P10_4-COMPLETION-AUDIT-B0008",
        "scope": SCOPE,
        "status": "FAIL_CLOSED",
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "hardware_evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "terminal_run_id": MATRIX_RUN,
        "board_binding": BOARD_BINDING,
        "module_binding": MODULE_BINDING,
        "goal_result_fields": {
            "P10_4_CORE_ROBUSTNESS": "FAIL",
            "P10_4_HALF_DUPLEX_8MBPS_RETENTION": "PASS",
            "P10_4_MARGIN_TARGET_9MBPS": "FAIL_NONBLOCKING",
            "P10_4_STRETCH_9P6MBPS": "FAIL_NONBLOCKING",
            "P10_4_2PLUS2_EXPERIMENT": "PARTIAL_NOT_EXECUTED_AFTER_FAIL_CLOSED",
            "P10_4_EXTERNAL_ELECTRICAL": "PENDING_NOT_IN_SCOPE",
        },
        "executed_full_campaign_stages": executed_stage_rows,
        "direct_achievements": {
            "p10_3_baseline_recheck": "PASS",
            "selected_config": full["selected_config"],
            "half_duplex_300s": {
                "F_TO_R_application_goodput_bps": full["application_goodput_bps"]["F_TO_R"],
                "R_TO_F_application_goodput_bps": full["application_goodput_bps"]["R_TO_F"],
                "F_TO_R_committed_bytes": 314_572_800,
                "R_TO_F_committed_bytes": 315_621_376,
                "eight_mbps_retention": "PASS_BOTH_DIRECTIONS",
                "nine_mbps_margin": "FAIL_NONBLOCKING_BOTH_DIRECTIONS",
            },
            "streaming_64m": "PASS_10_OF_10_EACH_DIRECTION",
            "streaming_128m": "PASS_3_OF_3_EACH_DIRECTION_NONBLOCKING",
            "counter_semantics": "PASS",
            "baseline_smoke": "PASS",
        },
        "terminal_blocker": {
            "path": rel(BLOCKER),
            "classification": blocker["classification"],
            "reproduction_count_after_short_qualification": 3,
            "terminal_measurement": blocker["terminal_matrix_measurement"],
        },
        "not_executed_after_fail_closed": [
            "remaining lane recovery vectors", "remaining 8x8 matrix vectors",
            "direction switch loop", "reset recovery", "2+2 experiment",
            "1800-second mixed formal",
        ],
        "requirement_disposition": requirement_audit_rows(),
        "requirement_counts": {"PASS": 8, "FAIL": 3, "PENDING": 5, "TOTAL": 16},
        "safety_and_shutdown": {
            "integrity_and_safety_counters": full["counters"],
            "shutdown_fixed": "PASS", "shutdown_rotating": "PASS",
            "current_run_hardware_authorization": False,
        },
        "scope_controls": {
            "network_used": False, "hardware_moved": False,
            "rotation_or_realignment_executed": False, "wiring_changed": False,
            "module_replaced_during_campaign_runs": False,
            "external_instrumentation_used": False, "p11_started": False,
        },
        "preserved_scoped_status": {"P10_3": "PASS", "P10_4": "FAIL", "P11": "NOT_STARTED"},
    }

    shutdown_runs = []
    for label, value in (
        ("qualification", data["qualification"]),
        ("full_campaign", data["full"]),
        ("isolated_lane_recovery", data["recovery"]),
        ("isolated_echo_crosstalk", data["matrix"]),
    ):
        shutdown_runs.append({
            "label": label,
            "run_id": value["run_id"],
            "shutdown_fixed": value["SHUTDOWN_FIXED"],
            "shutdown_rotating": value["SHUTDOWN_ROTATING"],
            "shutdown_record_count": len(value.get("shutdowns", [])),
            "all_recorded_shutdowns_verified": all_shutdown_pass(value),
        })
    shutdown = {
        "schema_version": 2,
        "test_id": "P10_4-SAFE-001",
        "scope": SCOPE,
        "status": "PASS",
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "latest_run_id": MATRIX_RUN,
        "runs": shutdown_runs,
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "latest_shutdown_marker_contract": {
            "SHUTDOWN_EXIT": 0,
            "TFDU_SHUTDOWN_PROGRAMMED": True,
            "endpoint_armed": 0,
            "active_tx_mask": 0,
            "sd_request_active": 1,
            "txd_output_intent": 0,
        },
        "current_run_hardware_authorization": False,
        "new_tx_permitted_by_this_record": False,
        "errors": [],
    }

    completed_raw = []
    for item in matrix["stage"]["details"]:
        label = str(item.get("label", ""))
        if label.endswith(("raw64", "raw1024")) and not label.startswith("matrix_F2_"):
            completed_raw.append(label)
    xtalk = {
        "schema_version": 2,
        "test_id": "P10_4-XTALK-001",
        "scope": SCOPE,
        "status": "FAIL",
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "run_id": MATRIX_RUN,
        "evidence_class": "CURRENT_ARTIFACT_DIGITAL_RAW_AND_FRAME_ONLY",
        "completed_before_fail_closed": {
            "raw_vectors": completed_raw,
            "frame_windows": data["matrix_completed_windows"],
            "same_module_accepted_data_or_control": 0,
            "cross_lane_accepted_data_or_control": 0,
        },
        "failure": {
            "label": "matrix_F2_raw64", "direction": "F2_TO_R2",
            "requested_raw_pulses": 64, "sender_physical_tx": 64,
            "receiver_raw_rx": 0, "result": "FAIL_REMOTE_RAW_COUNT_MISMATCH",
        },
        "not_executed_after_fail_closed": [
            "matrix_F2_raw1024", "matrix_R2_raw64", "matrix_R2_raw1024",
            "matrix_F3_raw64", "matrix_F3_raw1024",
            "matrix_R3_raw64", "matrix_R3_raw1024",
            "F2/R2/F3/R3 30-second frame windows",
        ],
        "external_crosstalk_or_optical_acceptance_claimed": False,
        "SHUTDOWN_FIXED": "PASS", "SHUTDOWN_ROTATING": "PASS",
        "current_run_hardware_authorization": False,
        "raw_result": source_record(MATRIX_RESULT),
        "raw_manifest": data["manifests"]["isolated_echo_crosstalk"],
    }

    offline_gate = GENERATED / "offline_gate_summary.json"
    gate_record: dict[str, Any] = {"status": "NOT_PRESENT"}
    if offline_gate.is_file():
        gate = load_json(offline_gate)
        gate_record = {**record(offline_gate), "status": gate.get("status")}
    closure = {
        "schema_version": 2,
        "test_id": "P10_4-TERMINAL-OFFLINE-CLOSURE-B0008",
        "scope": SCOPE,
        "status": "FAIL_WITH_PRESERVED_EVIDENCE",
        "hardware_campaign_status": "FAIL_CLOSED_PHYSICAL_DIRECTIONAL_BLOCKER",
        "artifact_source_commit": SOURCE_COMMIT,
        "hardware_evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "latest_hardware_run_id": MATRIX_RUN,
        "latest_hardware_run_manifest": data["manifests"]["isolated_echo_crosstalk"],
        "generic_offline_gate": gate_record,
        "disposition": {
            "new_tx_stopped": True,
            "new_hardware_run_started_during_closeout": False,
            "current_run_hardware_authorization": False,
            "shutdown_fixed": "PASS", "shutdown_rotating": "PASS",
            "terminal_reason": "THREE_CURRENT_B0008_F2_TO_R2_FAILURES_AFTER_SHORT_RAW_QUALIFICATION",
            "next_recommended_stage": "P10_4_REMEDIATION",
        },
        "preserved_scoped_status": {"P10_3": "PASS", "P10_4": "FAIL", "P11": "NOT_STARTED"},
    }

    final = {
        "schema_version": 2,
        "test_id": "P10_4-FINAL-B0008-FAIL-CLOSED",
        "scope": SCOPE,
        "status": "FAIL",
        "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT": "FAIL",
        "P10_3_EVIDENCE_COMMIT": "e64c04843d5d996f8d66d650fafaf3a43a2dd7dc",
        "P10_3_PASS_TAG": "p10.3-ax7020-stationary-4lane-pass",
        "P10_3_CLOSED_TAG": "p10.3-ax7020-stationary-4lane-closed",
        "P10_4_SOURCE_COMMIT": SOURCE_COMMIT,
        "P10_4_EVIDENCE_CHECKPOINT": EVIDENCE_CHECKPOINT,
        "P10_4_TAG": FINAL_TAG,
        "BRANCH": BRANCH,
        "WORKTREE": str(ROOT),
        "AUTOMATION_ONLY": True,
        "USER_HOLD_POINTS": 0,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "HARDWARE_ACTIONS_EXECUTED": True,
        "NETWORK_USED": False,
        "HARDWARE_MOVED": False,
        "WIRING_CHANGED": False,
        "EXTERNAL_INSTRUMENTATION_USED": False,
        "P10_3_BASELINE_RECHECK": "PASS",
        "BEST_BUFFER_COUNT": 2,
        "BEST_RING_DEPTH": 32,
        "BEST_DESCRIPTOR_BATCH": 16,
        "BEST_OUTSTANDING": 32,
        "BEST_SACK_WINDOW": 32,
        "BEST_BURST_FRAMES": 32,
        "BEST_ACK_THRESHOLD": 32,
        "F_TO_R_APPLICATION_GOODPUT_BPS": full["application_goodput_bps"]["F_TO_R"],
        "R_TO_F_APPLICATION_GOODPUT_BPS": full["application_goodput_bps"]["R_TO_F"],
        "F_TO_R_8MBPS_RETENTION": "PASS",
        "R_TO_F_8MBPS_RETENTION": "PASS",
        "F_TO_R_9MBPS_MARGIN": "FAIL_NONBLOCKING",
        "R_TO_F_9MBPS_MARGIN": "FAIL_NONBLOCKING",
        "F_TO_R_9P6MBPS_STRETCH": "FAIL_NONBLOCKING",
        "R_TO_F_9P6MBPS_STRETCH": "FAIL_NONBLOCKING",
        "STREAMING_64M_F_TO_R": "PASS_10_OF_10",
        "STREAMING_64M_R_TO_F": "PASS_10_OF_10",
        "STREAMING_128M": "PASS_NONBLOCKING_3_OF_3_EACH_DIRECTION",
        "LANE_DEGRADATION_RECOVERY": "FAIL",
        "DIRECTION_SWITCH_LOOP": "FAIL_NOT_EXECUTED_AFTER_FAIL_CLOSED",
        "RESET_RECOVERY": "FAIL_NOT_EXECUTED_AFTER_FAIL_CLOSED",
        "ECHO_CROSSTALK_8X8_DIGITAL": "FAIL",
        "SAME_MODULE_ACCEPTED_DATA": 0,
        "CROSS_LANE_ACCEPTED_DATA": 0,
        "TWO_PLUS_TWO_EXPERIMENT": "PARTIAL",
        "TWO_PLUS_TWO_F_TO_R_BPS": None,
        "TWO_PLUS_TWO_R_TO_F_BPS": None,
        "MIXED_30MIN": "FAIL_NOT_EXECUTED_AFTER_FAIL_CLOSED",
        "RUNTIME_SECONDS": 300,
        "RUNTIME_SECONDS_SEMANTICS": "LONGEST_COMPLETED_ACCEPTANCE_WINDOW_NOT_MIXED_FORMAL",
        "CRC_BAD": full["counters"]["crc_bad"],
        "SHA_MISMATCH": full["counters"]["sha_mismatch"],
        "PARTIAL_COMMIT": full["counters"]["partial_commit"],
        "DUPLICATE_COMMIT": full["counters"]["duplicate_commit"],
        "STALE_COMMIT": full["counters"]["stale_commit"],
        "RETRY_EXHAUSTED": full["counters"]["retry_exhausted"],
        "DESCRIPTOR_LEAK": full["counters"]["descriptor_leak"],
        "DOUBLE_COMPLETION": full["counters"]["double_completion"],
        "DEADLOCK": full["counters"]["deadlock"],
        "DUTY_VIOLATION": full["counters"]["duty_violation"],
        "CONTINUOUS_HIGH_VIOLATION": full["counters"]["continuous_high_violation"],
        "SHUTDOWN_FIXED": "PASS", "SHUTDOWN_ROTATING": "PASS",
        "EXTERNAL_POWER_ACCEPTANCE": "PENDING_NOT_IN_SCOPE",
        "EXTERNAL_TFDU_DUTY": "PENDING_NOT_IN_SCOPE",
        "P11_STATUS": "NOT_STARTED",
        "PASS": [
            "P10.3 baseline recheck", "direct counter semantics", "baseline smoke",
            "bounded performance tuning", "300-second half-duplex >=8 Mbit/s both directions",
            "64 MiB streaming 10/10 each direction", "128 MiB streaming 3/3 each direction",
            "all current-run manifests", "dual shutdown on every exit",
        ],
        "FAIL": [
            "lane degradation/recovery", "8x8 digital matrix at F2-to-R2 raw64",
            "P10.4 core robustness", "direction/reset/2+2/mixed stages not reached after fail-closed",
        ],
        "NONBLOCKING_RESULTS": [
            "9 Mbit/s margin failed both directions", "9.6 Mbit/s stretch failed both directions",
            "128 MiB streaming passed", "2+2 not executed after mandatory failure",
        ],
        "GENERATED_EVIDENCE": [
            rel(BLOCKER), rel(AUDIT), rel(CLOSURE), rel(FINAL_SUMMARY),
            rel(SHUTDOWN), rel(XTALK), rel(CONSISTENCY), rel(FINAL_MANIFEST),
        ],
        "NEXT_RECOMMENDED_STAGE": "P10_4_REMEDIATION",
        "terminal_blocker": blocker["terminal_matrix_measurement"],
        "board_binding": BOARD_BINDING,
        "module_binding": MODULE_BINDING,
        "artifacts": data["artifacts"],
        "raw_runs": [QUALIFICATION_RUN, FULL_RUN, RECOVERY_RUN, MATRIX_RUN],
        "old_p10_3_pass_preserved": True,
        "p11_or_product_scope_promoted": False,
    }

    return {
        "blocker": blocker,
        "audit": audit,
        "closure": closure,
        "final": final,
        "shutdown": shutdown,
        "xtalk": xtalk,
    }


def render_final_text(payload: dict[str, Any]) -> list[str]:
    ordered = [
        "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT",
        "P10_3_EVIDENCE_COMMIT", "P10_3_PASS_TAG", "P10_3_CLOSED_TAG",
        "P10_4_SOURCE_COMMIT", "P10_4_EVIDENCE_CHECKPOINT", "P10_4_TAG",
        "BRANCH", "WORKTREE", "AUTOMATION_ONLY", "USER_HOLD_POINTS",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "HARDWARE_ACTIONS_EXECUTED",
        "NETWORK_USED", "HARDWARE_MOVED", "WIRING_CHANGED",
        "EXTERNAL_INSTRUMENTATION_USED", "P10_3_BASELINE_RECHECK",
        "BEST_BUFFER_COUNT", "BEST_RING_DEPTH", "BEST_DESCRIPTOR_BATCH",
        "BEST_OUTSTANDING", "BEST_SACK_WINDOW", "BEST_BURST_FRAMES",
        "BEST_ACK_THRESHOLD", "F_TO_R_APPLICATION_GOODPUT_BPS",
        "R_TO_F_APPLICATION_GOODPUT_BPS", "F_TO_R_8MBPS_RETENTION",
        "R_TO_F_8MBPS_RETENTION", "F_TO_R_9MBPS_MARGIN",
        "R_TO_F_9MBPS_MARGIN", "F_TO_R_9P6MBPS_STRETCH",
        "R_TO_F_9P6MBPS_STRETCH", "STREAMING_64M_F_TO_R",
        "STREAMING_64M_R_TO_F", "STREAMING_128M", "LANE_DEGRADATION_RECOVERY",
        "DIRECTION_SWITCH_LOOP", "RESET_RECOVERY", "ECHO_CROSSTALK_8X8_DIGITAL",
        "SAME_MODULE_ACCEPTED_DATA", "CROSS_LANE_ACCEPTED_DATA",
        "TWO_PLUS_TWO_EXPERIMENT", "TWO_PLUS_TWO_F_TO_R_BPS",
        "TWO_PLUS_TWO_R_TO_F_BPS", "MIXED_30MIN", "RUNTIME_SECONDS",
        "CRC_BAD", "SHA_MISMATCH", "PARTIAL_COMMIT", "DUPLICATE_COMMIT",
        "STALE_COMMIT", "RETRY_EXHAUSTED", "DESCRIPTOR_LEAK", "DOUBLE_COMPLETION",
        "DEADLOCK", "DUTY_VIOLATION", "CONTINUOUS_HIGH_VIOLATION",
        "SHUTDOWN_FIXED", "SHUTDOWN_ROTATING", "EXTERNAL_POWER_ACCEPTANCE",
        "EXTERNAL_TFDU_DUTY", "P11_STATUS", "NEXT_RECOMMENDED_STAGE",
    ]
    lines = ["- Status: `FAIL`", "", "```text"]
    for key in ordered:
        value = payload.get(key)
        if isinstance(value, bool):
            value = str(value).lower()
        elif value is None:
            value = "NOT_EXECUTED"
        lines.extend([f"{key}:", str(value), ""])
    lines.append("```")
    lines += [
        "",
        "The terminal classification is directional RAW physical-path failure only. "
        "It is not a component-specific root cause and not a DATA-path PASS.",
    ]
    return lines


def publish_payloads(payloads: dict[str, dict[str, Any]]) -> None:
    mapping = {
        "blocker": (BLOCKER, "P10.4 B0008 F2-to-R2 terminal blocker"),
        "audit": (AUDIT, "P10.4 completion audit"),
        "closure": (CLOSURE, "P10.4 terminal offline closure"),
        "final": (FINAL_SUMMARY, "P10.4 final result"),
        "shutdown": (SHUTDOWN, "P10.4 aggregate shutdown evidence"),
        "xtalk": (XTALK, "P10.4 digital echo/crosstalk result"),
    }
    for name, (path, title) in mapping.items():
        payload = payloads[name]
        write_json(path, payload)
        if name == "final":
            lines = render_final_text(payload)
        elif name == "blocker":
            lines = [
                f"- Status: `{payload['status']}`",
                f"- Classification: `{payload['classification']}`",
                f"- Current module pair: `F2={MODULE_BINDING['F2']}` / `R2={MODULE_BINDING['R2']}`",
                f"- Terminal direct vector: `64 physical TX / 0 remote raw RX`",
                f"- Reproductions after short qualification: `{payload['reproduction_count_after_short_qualification']}`",
                "- Both endpoints ended in verified shutdown: `PASS / PASS`",
                "",
                payload["root_cause_boundary"],
            ]
        elif name == "audit":
            lines = [
                f"- Status: `{payload['status']}`",
                "- P10.3 scoped PASS preserved: `true`",
                "- P10.4 result: `FAIL`",
                "- Requirements: `8 PASS / 3 FAIL / 5 PENDING`",
                "- Half-duplex >=8 Mbit/s: `PASS` in both 300-second directions",
                "- 64 MiB / 128 MiB streaming: `PASS / PASS_NONBLOCKING`",
                "- Lane recovery / 8x8 matrix: `FAIL / FAIL`",
                "- Direction switch, reset recovery, 2+2 and mixed formal: not executed after fail-closed.",
            ]
        elif name == "xtalk":
            lines = [
                "- Status: `FAIL`",
                "- F0/R0/F1/R1 raw64, raw1024 and 30-second frame windows completed.",
                "- F2-to-R2 raw64: `64 TX / 0 remote RX`.",
                "- Same-module and cross-lane accepted data/control: `0 / 0`.",
                "- Remaining vectors were not executed after fail-closed.",
            ]
        else:
            lines = [f"- Status: `{payload['status']}`"]
            if "SHUTDOWN_FIXED" in payload:
                lines += [
                    f"- Fixed shutdown: `{payload['SHUTDOWN_FIXED']}`",
                    f"- Rotating shutdown: `{payload['SHUTDOWN_ROTATING']}`",
                ]
        write_markdown(path, title, lines)


def build_final_manifest(data: dict[str, Any]) -> dict[str, Any]:
    sources = [
        QUALIFICATION_SUMMARY, FULL_RESULT, RECOVERY_RESULT, MATRIX_RESULT,
        FULL_AUTH, RECOVERY_AUTH, MATRIX_AUTH,
        FULL_LANE_FIXED, FULL_LANE_ROTATING, RECOVERY_FIXED, RECOVERY_ROTATING,
        FULL_ROOT / "final/run_evidence_sha256_manifest.json",
        RECOVERY_ROOT / "final/run_evidence_sha256_manifest.json",
        MATRIX_ROOT / "final/run_evidence_sha256_manifest.json",
        QUALIFICATION_ROOT / "final/run_evidence_sha256_manifest.json",
    ]
    outputs = [BLOCKER, AUDIT, CLOSURE, FINAL_SUMMARY, SHUTDOWN, XTALK]
    payload = {
        "schema_version": 1,
        "test_id": "P10_4-B0008-FAIL-CLOSED-MANIFEST",
        "scope": SCOPE,
        "status": "PASS",
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "hardware_evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "source_records": [record(path) for path in sources],
        "output_records": [record(path) for path in outputs],
        "source_run_manifests_verified": data["manifests"],
        "current_run_hardware_authorization": False,
        "hardware_actions_executed_during_finalization": False,
        "errors": [],
    }
    write_json(FINAL_MANIFEST, payload)
    return payload


def publish_consistency(data: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    consistency = {
        "schema_version": 2,
        "test_id": "P10_4-EVIDENCE-CONSISTENCY-B0008",
        "scope": SCOPE,
        "status": "PASS",
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "hardware_evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "run_manifests": data["manifests"],
        "authorization_lifecycle": data["authorizations"],
        "terminal_manifest": record(FINAL_MANIFEST),
        "terminal_manifest_record_count": (
            len(manifest["source_records"]) + len(manifest["output_records"])
        ),
        "module_binding": MODULE_BINDING,
        "board_binding": BOARD_BINDING,
        "status_reconciliation": {
            "P10_3": "PASS_PRESERVED",
            "P10_4_hardware": "FAIL",
            "P10_4_evidence_consistency": "PASS",
            "P11": "NOT_STARTED",
        },
        "current_run_hardware_authorization": False,
        "hardware_actions_executed_during_finalization": False,
        "errors": [],
    }
    write_json(CONSISTENCY, consistency)
    write_markdown(CONSISTENCY, "P10.4 evidence consistency", [
        "- Status: `PASS`",
        "- Four immutable run manifests: `PASS`",
        "- Three terminal campaign authorizations: consumed and non-current.",
        "- Hardware result: `FAIL`; evidence consistency: `PASS`.",
        "- P10.3 scoped PASS is preserved and P11 remains not started.",
    ])
    return consistency


def update_state_and_status(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    state = load_json(STATE_PATH)
    state.setdefault("stage_status", {})[SCOPE] = "FAIL"
    state["p10_4_status"] = "FAIL"
    state["current_program_stage"] = SCOPE
    state["current_run_hardware_authorization"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_hardware_authorization_id"] = "P10_4-ECHO-CROSSTALK-8X8-DIAGNOSTIC-B0008"
    state["last_hardware_evidence_checkpoint"] = EVIDENCE_CHECKPOINT
    state["last_hardware_run_id"] = MATRIX_RUN
    state["last_hardware_stage"] = "P10_4"
    state["last_shutdown_fixed"] = "PASS"
    state["last_shutdown_rotating"] = "PASS"
    state["p10_4_current_run_authorization"] = {
        **record(MATRIX_AUTH),
        "status": load_json(MATRIX_AUTH)["status"],
        "consumed": True,
        "current_run_hardware_authorization": False,
        "run_id": MATRIX_RUN,
    }
    state["p10_4_acceptance"] = {
        "status": "FAIL",
        "scope": SCOPE,
        "campaign_disposition": "TERMINAL_FAIL_CLOSED_CURRENT_B0008_F2_TO_R2_PATH",
        "goal_sha256": GOAL_SHA256,
        "source_commit": SOURCE_COMMIT,
        "hardware_evidence_checkpoint": EVIDENCE_CHECKPOINT,
        "run_id": MATRIX_RUN,
        "current_run_hardware_authorization": False,
        "authorization_consumed": True,
        "board_binding": BOARD_BINDING,
        "module_binding": MODULE_BINDING,
        "artifact_sha256": payloads["blocker"]["artifact_sha256"],
        "qualification_run_id": QUALIFICATION_RUN,
        "full_campaign_run_id": FULL_RUN,
        "isolated_lane_recovery_run_id": RECOVERY_RUN,
        "isolated_matrix_run_id": MATRIX_RUN,
        "blocker_path": rel(BLOCKER), "blocker_sha256": sha256(BLOCKER),
        "completion_audit_path": rel(AUDIT), "completion_audit_sha256": sha256(AUDIT),
        "offline_closure_path": rel(CLOSURE), "offline_closure_sha256": sha256(CLOSURE),
        "final_summary_path": rel(FINAL_SUMMARY), "final_summary_sha256": sha256(FINAL_SUMMARY),
        "evidence_consistency_path": rel(CONSISTENCY),
        "evidence_consistency_sha256": sha256(CONSISTENCY),
        "terminal_manifest_path": rel(FINAL_MANIFEST),
        "terminal_manifest_sha256": sha256(FINAL_MANIFEST),
        "terminal_f2_sender_physical_tx": 64,
        "terminal_r2_receiver_raw_rx": 0,
        "reproduction_count_after_short_qualification": 3,
        "half_duplex_f_to_r_goodput_bps": 8_388_608.0,
        "half_duplex_r_to_f_goodput_bps": 8_416_570.026666667,
        "streaming_64m": "PASS_10_OF_10_EACH_DIRECTION",
        "streaming_128m": "PASS_3_OF_3_EACH_DIRECTION_NONBLOCKING",
        "unexecuted_after_fail_closed": [
            "direction_switch", "reset_recovery", "two_plus_two", "mixed_30min",
        ],
        "hardware_actions_executed": True,
        "network_used": False, "hardware_moved": False, "wiring_changed": False,
        "external_instrumentation_used": False, "maximum_lane_mask": "0xF",
        "maximum_single_formal_run_seconds": 1800,
        "shutdown_fixed": "PASS", "shutdown_rotating": "PASS",
        "p10_3_scoped_pass_preserved": True, "p11_started": False,
    }
    state["state_revision"] = "P10-4-FAIL-CLOSED-B0008-F2-R2-REPRODUCED-3X"
    write_json(STATE_PATH, state)
    errors = validate_state(state, ROOT)
    require(not errors, f"updated state validation failed: {errors}")
    STATUS_PATH.write_text(
        render_project_status(state), encoding="utf-8", newline="\n"
    )
    return state


def update_requirements() -> dict[str, Any]:
    document = yaml.safe_load(REQUIREMENTS_PATH.read_text(encoding="utf-8"))
    requirements = document.get("requirements", [])
    by_id = {
        item.get("requirement_id"): item
        for item in requirements if isinstance(item, dict)
    }
    require(set(REQUIREMENT_DISPOSITIONS).issubset(by_id), "P10.4 requirements are incomplete")
    full_common = [record(FULL_RESULT), record(FULL_ROOT / "final/run_evidence_sha256_manifest.json")]
    diagnostic_common = {
        "P10_4-DEG-001": [record(RECOVERY_RESULT), record(RECOVERY_ROOT / "final/run_evidence_sha256_manifest.json")],
        "P10_4-XTALK-001": [record(MATRIX_RESULT), record(MATRIX_ROOT / "final/run_evidence_sha256_manifest.json")],
        "P10_4-SAFE-001": [record(FINAL_MANIFEST)],
    }
    for req_id, (status, evidence_rel) in REQUIREMENT_DISPOSITIONS.items():
        item = by_id[req_id]
        item["status"] = status
        item["waiver"] = None
        if status == "PENDING":
            item["artifact_hashes"] = []
            item.pop("artifact_hash", None)
            item["hardware_followup"] = (
                "Not executed after the mandatory current F2-to-R2 fail-closed trigger; "
                "requires a new immutable remediation bundle and new current-run evidence."
            )
            continue
        evidence = ROOT / evidence_rel
        require(evidence.is_file(), f"requirement evidence missing: {evidence_rel}")
        item["evidence_path"] = evidence_rel
        item["artifact_hash"] = sha256(evidence)
        records = [record(evidence)]
        if req_id not in {"P10_4-CLOSE-001"}:
            records += [entry.copy() for entry in diagnostic_common.get(req_id, full_common)]
        item["artifact_hashes"] = records
        item["hardware_followup"] = (
            "P10.4 is terminal FAIL_CLOSED on the current B0008 F2-to-R2 path. "
            "This scoped result does not promote P11, 8x32, 600 rpm, Ethernet/SPI, "
            "external electrical/duty acceptance, or product-final acceptance."
        )

    state_hash = sha256(STATE_PATH)
    status_hash = sha256(STATUS_PATH)
    for item in requirements:
        if not isinstance(item, dict):
            continue
        for binding in item.get("artifact_hashes", []):
            if binding.get("path") == "config/project_state.json":
                binding["sha256"] = state_hash
                binding["bytes"] = STATE_PATH.stat().st_size
            elif binding.get("path") == "PROJECT_STATUS.md":
                binding["sha256"] = status_hash
                binding["bytes"] = STATUS_PATH.stat().st_size
        if item.get("evidence_path") == "config/project_state.json":
            item["artifact_hash"] = state_hash
        elif item.get("evidence_path") == "PROJECT_STATUS.md":
            item["artifact_hash"] = status_hash

    REQUIREMENTS_PATH.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8", newline="\n",
    )
    errors = validate_requirements(document, ROOT)
    require(not errors, f"updated requirement validation failed: {errors}")
    result = subprocess.run(
        [sys.executable, "scripts/generate_requirement_traceability.py", "--write"],
        cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    require(result.returncode == 0, f"traceability generation failed: {result.stdout}{result.stderr}")
    require(TRACEABILITY_PATH.is_file(), "traceability output is missing")
    return document


def main() -> int:
    try:
        data = collect_and_verify()
        payloads = build_payloads(data)
        publish_payloads(payloads)
        manifest = build_final_manifest(data)
        publish_consistency(data, manifest)
        update_state_and_status(payloads)
        update_requirements()
    except (CloseoutError, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        print("P10_4_B0008_FAIL_CLOSED_FINALIZATION=FAIL")
        return 1

    print("P10_4_B0008_FAIL_CLOSED_FINALIZATION=PASS")
    print("P10_4_RESULT=FAIL")
    print(f"P10_4_TERMINAL_RUN_ID={MATRIX_RUN}")
    print("P10_4_TERMINAL_F2_TX=64")
    print("P10_4_TERMINAL_R2_RAW_RX=0")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    print("SHUTDOWN_FIXED=PASS")
    print("SHUTDOWN_ROTATING=PASS")
    print("HARDWARE_ACTIONS_EXECUTED_DURING_FINALIZATION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
