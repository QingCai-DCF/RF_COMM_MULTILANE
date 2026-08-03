#!/usr/bin/env python3
"""Close the scoped P10.1R hardware-remediation campaign without touching hardware.

The script consumes only already-recorded immutable run evidence.  It verifies
the source/artifact/board/authorization binding, every run manifest, shutdown
markers, required performance and integrity counters, then updates the
canonical state and requirement traceability documents.  It intentionally
does not launch Vivado, hw_server, XSDB, a PS ELF, UART, or any physical I/O.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
STATE = ROOT / "config/project_state.json"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATUS = ROOT / "PROJECT_STATUS.md"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
CURRENT_AUTHORIZATION = ROOT / "config/p10_1r_current_run_hardware_authorization.json"

BRANCH = "p10.1r/2lane-speed-stability-remediation"
SOURCE_COMMIT = "39df17155ce82e38366fbdac00c79584f0fe1afa"
FAILURE_TAG = "p10.1-hardware-performance-fail-20260801"
FAILURE_TAG_COMMIT = "991cc8a6cc5fd656178f9a3ddd9bb7c2f9c84151"
GOAL_SHA256 = "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
PASS_TAG = "p10.1r-2lane-speed-stability-pass"
FINALIZED_AT_UTC = "2026-08-03T13:10:00Z"

GOAL = ROOT / "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
ARTIFACT_FREEZE = GENERATED / "p10_1r_artifact_freeze.json"
FAILURE_BASELINE = GENERATED / "p10_1r_failure_baseline_summary.json"
OFFLINE_CONSISTENCY = GENERATED / "p10_1r_evidence_consistency.json"
HARDWARE_CONSISTENCY = GENERATED / "p10_1r_hardware_evidence_consistency.json"
FINAL_SUMMARY = GENERATED / "p10_1r_final_summary.json"

STAGES: dict[str, dict[str, str]] = {
    "preflight": {"wrapper": "p10_1r_safe_boot.json"},
    "echo_tail": {"wrapper": "p10_1r_echo_tail.json"},
    "crosstalk": {"wrapper": "p10_1r_crosstalk.json"},
    "phy_sanity": {"wrapper": "p10_1r_phy_sanity.json"},
    "ack_tuning": {"wrapper": "p10_1r_ack_tuning.json"},
    "performance": {"wrapper": "p10_1r_performance.json"},
    "streaming_64m": {"wrapper": "p10_1r_streaming_64m.json"},
    "formal_30min": {"wrapper": "p10_1r_formal_30min.json"},
}

EXPECTED_ARTIFACTS = {
    ("fixed", "functional_bitstream"): "565337987c949bb65b57a088eb1038144714b867d8ebf6d5115e7346b11d44ea",
    ("fixed", "shutdown_bitstream"): "0d0f4fbf2b35518094aec58728461f505c225a5f1aef647d3917259564fc279a",
    ("fixed", "xsa"): "cc671149676f1cdeaea6cb750c0cdd31f1b2456697d93244cc5fb12fa4eca648",
    ("fixed", "bsp"): "ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8",
    ("fixed", "elf"): "0d3963ce7fbcaab95373ebec97f4c62712bd216f041a23547c9006024e219db4",
    ("rotating", "functional_bitstream"): "df0c60f6e3826c358fd2ca562ee4807b28a935c354bda535e98c59313e6471b0",
    ("rotating", "shutdown_bitstream"): "a0abfef77d566a6baaf51242d95cae679e63cb9e34f423595f3faae7bcfbac27",
    ("rotating", "xsa"): "e1890cb603530e70abcf931c3ae69a5ddf4bfde68a66b1a31ccb6231b883c28d",
    ("rotating", "bsp"): "d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5",
    ("rotating", "elf"): "5abf3d3d597b14e182d07665609a8dd8ff05d7c6159fd2deb1f81813723c035e",
}

REQUIREMENT_BINDINGS: dict[str, tuple[str, ...]] = {
    "P10_1R-ECHO-001": ("p10_1r_crosstalk_remediation.json", "p10_1r_xsim/summary.json"),
    "P10_1R-ECHO-002": ("p10_1r_crosstalk_remediation.json",),
    "P10_1R-ECHO-003": ("p10_1r_echo_tail.json",),
    "P10_1R-ECHO-004": ("p10_1r_crosstalk_remediation.json",),
    "P10_1R-ECHO-005": ("p10_1r_echo_tail.json",),
    "P10_1R-ECHO-006": ("p10_1r_crosstalk_remediation.json", "p10_1r_phy_sanity.json"),
    "P10_1R-ACK-001": ("p10_1r_ack_tuning.json", "p10_1r_performance.json"),
    "P10_1R-ACK-002": ("p10_1r_ack_tuning.json", "p10_1r_performance.json"),
    "P10_1R-ACK-003": ("p10_1r_ack_tuning.json", "p10_1r_streaming_64m.json"),
    "P10_1R-ACK-004": ("p10_1r_ack_tuning.json", "p10_1r_formal_30min.json"),
    "P10_1R-HOST-001": ("p10_1r_formal_30min.json",),
    "P10_1R-PERF-001": ("p10_1r_performance.json",),
    "P10_1R-PERF-002": ("p10_1r_performance.json",),
    "P10_1R-STREAM-001": ("p10_1r_streaming_64m.json",),
    "P10_1R-STREAM-002": ("p10_1r_streaming_64m.json",),
    "P10_1R-SOAK-001": ("p10_1r_formal_30min.json",),
}

TEST_IDS = {
    "P10_1R-ECHO-001": "P10_1R-HW-CROSSTALK",
    "P10_1R-ECHO-002": "P10_1R-HW-CROSSTALK",
    "P10_1R-ECHO-003": "P10_1R-HW-ECHO_TAIL",
    "P10_1R-ECHO-004": "P10_1R-HW-CROSSTALK",
    "P10_1R-ECHO-005": "P10_1R-HW-ECHO_TAIL",
    "P10_1R-ECHO-006": "P10_1R-HW-CROSSTALK",
    "P10_1R-ACK-001": "P10_1R-HW-ACK_TUNING",
    "P10_1R-ACK-002": "P10_1R-HW-ACK_TUNING",
    "P10_1R-ACK-003": "P10_1R-HW-ACK_TUNING",
    "P10_1R-ACK-004": "P10_1R-HW-FORMAL_30MIN",
    "P10_1R-HOST-001": "P10_1R-HW-FORMAL_30MIN",
    "P10_1R-PERF-001": "P10_1R-HW-PERFORMANCE",
    "P10_1R-PERF-002": "P10_1R-HW-PERFORMANCE",
    "P10_1R-STREAM-001": "P10_1R-HW-STREAMING_64M",
    "P10_1R-STREAM-002": "P10_1R-HW-STREAMING_64M",
    "P10_1R-SOAK-001": "P10_1R-HW-FORMAL_30MIN",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel(path)} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def expect(condition: bool, message: str, errors: list[str]) -> bool:
    if not condition:
        errors.append(message)
    return condition


def repo_path(value: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{label}: missing path")
        return None
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes repository")
        return None
    if not path.is_file():
        errors.append(f"{label}: missing {value}")
        return None
    return path


def verify_file_record(
    item: Any, base: Path, label: str, errors: list[str]
) -> Path | None:
    if not isinstance(item, dict):
        errors.append(f"{label}: record is not a mapping")
        return None
    value = item.get("path")
    expected = str(item.get("sha256", "")).lower()
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        errors.append(f"{label}: malformed path/SHA256")
        return None
    path = (base / value).resolve()
    try:
        path.relative_to(base.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes evidence root")
        return None
    if not path.is_file():
        errors.append(f"{label}: missing {value}")
        return None
    actual = sha256(path)
    expect(actual == expected, f"{label}: SHA256 mismatch", errors)
    if "bytes" in item:
        expect(path.stat().st_size == item.get("bytes"), f"{label}: byte count mismatch", errors)
    return path


def flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, list):
        result: list[float] = []
        for item in value:
            result.extend(flatten_numbers(item))
        return result
    return []


def values_for_key(value: Any, key: str) -> list[Any]:
    result: list[Any] = []
    if isinstance(value, dict):
        for name, item in value.items():
            if name == key:
                result.append(item)
            result.extend(values_for_key(item, key))
    elif isinstance(value, list):
        for item in value:
            result.extend(values_for_key(item, key))
    return result


def numeric_values(value: Any, keys: Iterable[str]) -> list[float]:
    result: list[float] = []
    for key in keys:
        for item in values_for_key(value, key):
            result.extend(flatten_numbers(item))
    return result


def all_false(value: Any, key: str) -> bool:
    items = values_for_key(value, key)
    return bool(items) and all(item is False for item in items if isinstance(item, bool))


def parse_lane_mask(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise ValueError(f"invalid lane mask {value!r}")


def verify_artifact_freeze(errors: list[str]) -> dict[str, Any]:
    freeze = load_json(ARTIFACT_FREEZE)
    expect(freeze.get("status") == "PASS", "artifact freeze is not PASS", errors)
    expect(freeze.get("source_commit") == SOURCE_COMMIT, "artifact freeze source mismatch", errors)
    expect(freeze.get("branch") == BRANCH, "artifact freeze branch mismatch", errors)
    goal = freeze.get("goal", {})
    expect(isinstance(goal, dict) and goal.get("sha256") == GOAL_SHA256, "artifact freeze Goal mismatch", errors)
    expect(freeze.get("acceptance_eligible") is True, "artifact bundle is not acceptance eligible", errors)
    expect(freeze.get("old_hardware_results_inherited") is False, "old hardware result inheritance is not false", errors)
    expect(
        freeze.get("board_binding")
        == {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating_role": "AX7020-R/JTAG:210512180081",
        },
        "artifact freeze board binding mismatch",
        errors,
    )
    roles = freeze.get("roles", {})
    for (role, kind), expected_sha in EXPECTED_ARTIFACTS.items():
        freeze_kind = "bitstream" if kind == "functional_bitstream" else kind
        item = roles.get(role, {}).get(freeze_kind, {}) if isinstance(roles, dict) else {}
        expect(item.get("sha256") == expected_sha, f"{role}/{kind}: frozen SHA mismatch", errors)
        expect(item.get("built_source_commit") == SOURCE_COMMIT, f"{role}/{kind}: source mismatch", errors)
        path = repo_path(item.get("path"), f"{role}/{kind}", errors)
        if path is not None:
            expect(sha256(path) == expected_sha, f"{role}/{kind}: file SHA mismatch", errors)
            expect(SOURCE_COMMIT in path.parts, f"{role}/{kind}: source absent from path", errors)
            expect(expected_sha in path.parts, f"{role}/{kind}: digest absent from path", errors)
    return freeze


def verify_manifest(run_root: Path, manifest: dict[str, Any], errors: list[str]) -> int:
    expect(manifest.get("status") == "PASS", f"{run_root.name}: manifest is not PASS", errors)
    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append(f"{run_root.name}: manifest files is not a list")
        return 0
    seen: set[str] = set()
    for index, item in enumerate(files):
        path = verify_file_record(item, run_root, f"{run_root.name}: manifest[{index}]", errors)
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            value = item["path"].replace("\\", "/")
            expect(value not in seen, f"{run_root.name}: duplicate manifest path {value}", errors)
            seen.add(value)
        if path is None:
            continue
    actual = {
        item.relative_to(run_root).as_posix()
        for item in run_root.rglob("*")
        if item.is_file()
    }
    expected_unlisted = {
        "final/orchestrator_result.json",
        "final/run_evidence_sha256_manifest.json",
    }
    expect(actual - seen == expected_unlisted, f"{run_root.name}: incomplete manifest coverage", errors)
    expect(not (seen - actual), f"{run_root.name}: manifest references missing files", errors)
    return len(files)


def immutable_artifact_set(value: dict[str, Any]) -> set[tuple[str, str, str]]:
    result: set[tuple[str, str, str]] = set()
    for item in value.get("artifacts", []):
        if isinstance(item, dict):
            result.add((str(item.get("role")), str(item.get("kind")), str(item.get("sha256"))))
    return result


def verify_run(stage: str, spec: dict[str, str], errors: list[str]) -> dict[str, Any]:
    wrapper_path = GENERATED / spec["wrapper"]
    wrapper = load_json(wrapper_path)
    expect(wrapper.get("status") == "PASS", f"{stage}: generated wrapper is not PASS", errors)
    expect(wrapper.get("source_commit") == SOURCE_COMMIT, f"{stage}: wrapper source mismatch", errors)
    expect(wrapper.get("hardware_actions_executed") is True, f"{stage}: hardware action marker missing", errors)
    for key in ("network_used", "hardware_movement", "rewiring_executed"):
        expect(wrapper.get(key) is False, f"{stage}: wrapper {key} is not false", errors)
    expect(wrapper.get("errors") == [], f"{stage}: wrapper errors are non-empty", errors)

    raw_path = repo_path(wrapper.get("raw_summary"), f"{stage}: raw summary", errors)
    if raw_path is None:
        raise ValueError(f"{stage}: raw summary unavailable")
    expect(sha256(raw_path) == wrapper.get("raw_summary_sha256"), f"{stage}: raw summary SHA mismatch", errors)
    raw = load_json(raw_path)
    expect(raw.get("status") == "PASS", f"{stage}: raw summary is not PASS", errors)
    expect(raw.get("errors") == [], f"{stage}: raw errors are non-empty", errors)

    run_id = wrapper.get("run_id")
    expect(isinstance(run_id, str) and run_id == raw_path.parents[1].name, f"{stage}: run ID/path mismatch", errors)
    run_root = raw_path.parents[1]
    auth_path = run_root / "authorization/immutable_authorization.json"
    auth_record_path = run_root / "authorization/authorization_record.json"
    orchestrator_path = run_root / "final/orchestrator_result.json"
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    for path, label in (
        (auth_path, "immutable authorization"),
        (auth_record_path, "authorization record"),
        (orchestrator_path, "orchestrator result"),
        (manifest_path, "manifest"),
    ):
        expect(path.is_file(), f"{stage}: missing {label}", errors)

    authorization = load_json(auth_path)
    auth_record = load_json(auth_record_path)
    orchestrator = load_json(orchestrator_path)
    manifest = load_json(manifest_path)

    expect(authorization.get("status") == "AUTHORIZED", f"{stage}: immutable authorization was not authorized", errors)
    expect(authorization.get("current_run_hardware_authorization") is True, f"{stage}: immutable authorization not true at start", errors)
    expect(authorization.get("consumed") is False, f"{stage}: immutable start record was retroactively consumed", errors)
    expect(authorization.get("run_id") == run_id, f"{stage}: authorization run mismatch", errors)
    expect(authorization.get("source_commit") == SOURCE_COMMIT, f"{stage}: authorization source mismatch", errors)
    expect(authorization.get("goal_sha256") == GOAL_SHA256, f"{stage}: authorization Goal mismatch", errors)
    expect(authorization.get("authorized_stages") == [stage], f"{stage}: authorization stage set mismatch", errors)
    expect(authorization.get("maximum_single_formal_run_seconds") == 1800, f"{stage}: formal bound mismatch", errors)
    expect(authorization.get("maximum_lane_mask") == 3, f"{stage}: lane-mask bound mismatch", errors)
    boards = authorization.get("board_identities", {})
    expect(boards.get("fixed", {}).get("serial") == "210249855178", f"{stage}: fixed serial mismatch", errors)
    expect(boards.get("rotating", {}).get("serial") == "210512180081", f"{stage}: rotating serial mismatch", errors)
    shutdown = authorization.get("shutdown", {})
    for key in ("before", "after", "finally", "normal_exit", "on_error", "on_interrupt", "on_timeout"):
        expect(shutdown.get(key) is True, f"{stage}: shutdown policy {key} is not true", errors)
    expect(immutable_artifact_set(authorization) == {(role, kind, digest) for (role, kind), digest in EXPECTED_ARTIFACTS.items()}, f"{stage}: immutable artifact ledger mismatch", errors)

    expect(auth_record.get("status") == "PASS", f"{stage}: authorization record is not PASS", errors)
    expect(auth_record.get("run_id") == run_id, f"{stage}: authorization record run mismatch", errors)
    expect(auth_record.get("source_commit") == SOURCE_COMMIT, f"{stage}: authorization record source mismatch", errors)
    expect(auth_record.get("goal_sha256") == GOAL_SHA256, f"{stage}: authorization record Goal mismatch", errors)
    expect(auth_record.get("authorized_stages") == [stage], f"{stage}: authorization record stage mismatch", errors)
    expect(auth_record.get("authorization_sha256") == sha256(auth_path), f"{stage}: immutable authorization SHA mismatch", errors)

    expect(orchestrator.get("status") == "PASS", f"{stage}: orchestrator is not PASS", errors)
    expect(orchestrator.get("run_id") == run_id, f"{stage}: orchestrator run mismatch", errors)
    expect(orchestrator.get("source_commit") == SOURCE_COMMIT, f"{stage}: orchestrator source mismatch", errors)
    expect(orchestrator.get("hardware_actions_executed") is True, f"{stage}: orchestrator hardware marker missing", errors)
    expect(orchestrator.get("current_run_hardware_authorization") is True, f"{stage}: in-run authorization marker missing", errors)
    expect(orchestrator.get("stage_status", {}).get(stage) == "PASS", f"{stage}: stage status is not PASS", errors)
    expect(orchestrator.get("errors") == [], f"{stage}: orchestrator errors are non-empty", errors)
    for key in ("network_used", "ethernet_used", "spi_used", "hardware_movement", "rewiring_executed", "rotation_executed"):
        expect(orchestrator.get(key) is False, f"{stage}: orchestrator {key} is not false", errors)
    try:
        expect(parse_lane_mask(orchestrator.get("maximum_lane_mask_used")) <= 3, f"{stage}: lane mask exceeded 0x3", errors)
    except (TypeError, ValueError) as exc:
        errors.append(f"{stage}: {exc}")
    expect(orchestrator.get("SHUTDOWN_FIXED") == "PASS", f"{stage}: fixed shutdown failed", errors)
    expect(orchestrator.get("SHUTDOWN_ROTATING") == "PASS", f"{stage}: rotating shutdown failed", errors)
    shutdowns = orchestrator.get("shutdowns", [])
    expect(isinstance(shutdowns, list) and len(shutdowns) >= 2, f"{stage}: shutdown-before/after records missing", errors)
    if isinstance(shutdowns, list):
        expect(all(item.get("status") == "PASS" for item in shutdowns if isinstance(item, dict)), f"{stage}: a shutdown record is not PASS", errors)
        markers = [
            attempt.get("markers", {})
            for item in shutdowns
            if isinstance(item, dict)
            for attempt in item.get("attempts", [])
            if isinstance(attempt, dict)
        ]
        expect(
            any(
                marker.get("TFDU_SHUTDOWN_PROGRAMMED") == "1"
                and marker.get("SHUTDOWN_EXIT") == "0"
                for marker in markers
            ),
            f"{stage}: verifiable shutdown markers missing",
            errors,
        )

    manifest_count = verify_manifest(run_root, manifest, errors)
    expect(manifest.get("run_id") == run_id, f"{stage}: manifest run mismatch", errors)
    expect(orchestrator.get("evidence_file_count") == manifest_count, f"{stage}: manifest count mismatch", errors)
    expect(orchestrator.get("evidence_manifest") == rel(manifest_path), f"{stage}: orchestrator manifest path mismatch", errors)

    return {
        "stage": stage,
        "wrapper_path": wrapper_path,
        "wrapper": wrapper,
        "raw_path": raw_path,
        "raw": raw,
        "run_id": run_id,
        "run_root": run_root,
        "authorization_path": auth_path,
        "authorization_record_path": auth_record_path,
        "orchestrator_path": orchestrator_path,
        "orchestrator": orchestrator,
        "manifest_path": manifest_path,
        "manifest_count": manifest_count,
    }


def average(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / len(materialized)


def build_metrics(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    echo = results["echo_tail"]["wrapper"]["semantics"]
    cross = results["crosstalk"]["wrapper"]["semantics"]
    ack = results["ack_tuning"]["wrapper"]["semantics"]
    performance = results["performance"]["wrapper"]["semantics"]
    streaming = results["streaming_64m"]["wrapper"]["semantics"]
    formal = results["formal_30min"]["wrapper"]["semantics"]
    perf_windows = performance["windows"]
    formal_windows = formal["formal_windows"]
    perf_by_direction = {int(item["direction"]): item for item in perf_windows}
    formal_by_direction = {int(item["direction"]): item for item in formal_windows}
    all_raw = {stage: item["raw"] for stage, item in results.items()}

    counters = {
        "crc_bad": sum(numeric_values(all_raw, ("crc_bad_count", "physical_crc_bad"))),
        "sha_mismatch": sum(numeric_values(all_raw, ("sha_mismatch_count",))),
        "partial_commit": sum(numeric_values(all_raw, ("partial_commit_count",))),
        "duplicate_commit": sum(numeric_values(all_raw, ("duplicate_commit_count",))),
        "stale_commit": sum(numeric_values(all_raw, ("stale_commit_count",))),
        "retry_exhausted": sum(numeric_values(all_raw, ("retry_exhausted_count", "perf_retry_exhausted_count", "retry_exhausted"))),
        "descriptor_leak": sum(numeric_values(all_raw, ("descriptor_leak_count", "perf_descriptor_leak_count", "descriptor_leak"))),
        "double_completion": sum(numeric_values(all_raw, ("double_completion_count", "perf_double_completion_count"))),
        "transport_timeout": sum(numeric_values(all_raw, ("tx_timeouts",))),
        "duty_violation": sum(numeric_values(all_raw, ("duty_hard_fault_after", "duty_hard_faults"))),
    }
    tx_high = numeric_values(all_raw, ("tx_high_max_after", "tx_high_max_cycles"))
    timed_out = values_for_key(all_raw, "timed_out")
    counters["continuous_high_violation"] = sum(1 for item in tx_high if item > 64)
    counters["maximum_observed_txd_high_cycles"] = max(tx_high, default=0)
    counters["deadlock"] = sum(1 for item in timed_out if item is True)

    return {
        "guard_cycles": {module: 4096 for module in ("F0", "F1", "R0", "R1")},
        "same_module_raw_echo_count": echo["same_module_raw_echo_count"],
        "same_module_blanked_frame_count": echo["same_module_blanked_frame_count"],
        "same_module_accepted_data_count": cross["same_module_accepted_data_count"],
        "non_target_accepted_crc_valid_count": max(numeric_values(all_raw, ("non_target_accepted",)), default=0),
        "cross_lane_accepted_data_count": cross["cross_lane_accepted_data_count"],
        "other_lane_blanked_count": cross["other_lane_blanked_count"],
        "remote_acceptance_reconciled_case_count": cross["remote_acceptance_reconciled_case_count"],
        "local_source_rejection_enabled": cross["local_source_rejection_enabled"],
        "local_source_rejected_frame_count": cross["local_source_rejected_frame_count"],
        "local_source_rejection_directly_exercised": cross["local_source_rejection_observed"],
        "best_burst_frames": ack["best_burst_frames"],
        "best_ack_threshold": ack["best_ack_threshold"],
        "best_ack_max_delay_cycles": ack["best_ack_max_delay_cycles"],
        "objects_in_flight": ack["objects_in_flight"],
        "ack_wait_ratio_before": 0.914,
        "ack_wait_ratio_after": average(item["ack_wait_ratio"] for item in perf_windows),
        "inter_object_ratio_before": 0.445,
        "inter_object_ratio_after": average(item["inter_object_ratio"] for item in perf_windows),
        "host_blocking_commands_fixed_to_rotating": formal_by_direction[0]["host_blocking_commands"],
        "host_blocking_commands_rotating_to_fixed": formal_by_direction[1]["host_blocking_commands"],
        "minimum_segments_per_host_command": min(item["minimum_segments_per_host_command"] for item in formal_windows),
        "host_fast_path_dependency_count": sum(item["host_fast_path_dependency_count"] for item in formal_windows),
        "sustained_application_goodput_bps": {
            "fixed_to_rotating": perf_by_direction[0]["application_goodput_bps"],
            "rotating_to_fixed": perf_by_direction[1]["application_goodput_bps"],
        },
        "formal_application_goodput_bps": {
            "fixed_to_rotating": formal_by_direction[0]["application_goodput_bps"],
            "rotating_to_fixed": formal_by_direction[1]["application_goodput_bps"],
        },
        "streaming_64m": {
            "fixed_to_rotating_count": streaming["f2r_64m_count"],
            "rotating_to_fixed_count": streaming["r2f_64m_count"],
            "recovery_vector_count": streaming["recovery_vector_count"],
            "post_recovery_clean_count": streaming["post_recovery_clean_count"],
        },
        "formal_runtime_seconds": formal["elapsed_ms"] / 1000.0,
        "formal_committed_bytes": {
            "fixed_to_rotating": formal_by_direction[0]["committed_bytes"],
            "rotating_to_fixed": formal_by_direction[1]["committed_bytes"],
        },
        "formal_window_seconds": {
            "fixed_to_rotating": formal_by_direction[0]["duration_seconds"],
            "rotating_to_fixed": formal_by_direction[1]["duration_seconds"],
        },
        "counters": counters,
    }


def build_exit_gates(
    results: dict[str, dict[str, Any]],
    metrics: dict[str, Any],
    failure_baseline: dict[str, Any],
    current_authorization: dict[str, Any],
    errors: list[str],
) -> dict[str, str]:
    raw = {stage: item["raw"] for stage, item in results.items()}
    echo = results["echo_tail"]["wrapper"]["semantics"]
    cross = results["crosstalk"]["wrapper"]["semantics"]
    ack = results["ack_tuning"]["wrapper"]["semantics"]
    perf_windows = results["performance"]["wrapper"]["semantics"]["windows"]
    stream = results["streaming_64m"]["wrapper"]["semantics"]
    formal = results["formal_30min"]["wrapper"]["semantics"]
    offline_xsim = load_json(GENERATED / "p10_1r_xsim/summary.json")
    counters = metrics["counters"]
    gates: dict[str, str] = {}

    def gate(name: str, condition: bool) -> None:
        gates[name] = "PASS" if condition else "FAIL"
        expect(condition, f"mandatory gate failed: {name}", errors)

    gate(
        "FAILURE_BASELINE_FROZEN",
        failure_baseline.get("status") == "PASS"
        and failure_baseline.get("failure_tag") == FAILURE_TAG
        and failure_baseline.get("failure_tag_target") == FAILURE_TAG_COMMIT
        and failure_baseline.get("old_authorization_consumed") is True
        and failure_baseline.get("old_authorization_reusable") is False,
    )
    gate(
        "OLD_AUTHORIZATION_CLOSED",
        current_authorization.get("current_run_hardware_authorization") is False
        and current_authorization.get("consumed") is True
        and current_authorization.get("reusable_for_future_run") is False,
    )
    gate("PER_MODULE_TX_RX_EXCLUSION", cross.get("same_module_accepted_data_count") == 0)
    gate("OTHER_LANE_NOT_BLANKED", cross.get("other_lane_blanked_count") == 0)
    decoder_counts = numeric_values(raw, ("decoder_clear_lane0", "decoder_clear_lane1"))
    gate("DECODER_CLEAR_ON_TX", offline_xsim.get("status") == "PASS" and max(decoder_counts, default=0) > 0)
    gate(
        "POST_TX_GUARD_MEASURED",
        echo.get("configured_guard_cycles") == 4096
        and echo.get("configured_guard_is_safe") is True
        and echo.get("sample_count") == 4000
        and set(echo.get("modules", {})) == {"F0", "F1", "R0", "R1"},
    )
    gate(
        "LOCAL_SOURCE_REJECTION",
        cross.get("local_source_rejection_enabled") is True
        and offline_xsim.get("status") == "PASS"
        and cross.get("same_module_accepted_data_count") == 0,
    )
    gate("SAME_MODULE_RAW_ECHO_OBSERVABLE", metrics["same_module_raw_echo_count"] == 4000)
    gate("SAME_MODULE_ACCEPTED_DATA_ZERO", metrics["same_module_accepted_data_count"] == 0)
    gate("NON_TARGET_ACCEPTED_CRC_VALID_ZERO", metrics["non_target_accepted_crc_valid_count"] == 0)
    gate("CROSS_LANE_ACCEPTED_ZERO", metrics["cross_lane_accepted_data_count"] == 0)
    gate("ACK_BUNDLE_WINDOW", ack.get("best_burst_frames", 0) >= 24 and ack.get("best_ack_threshold", 0) >= 24)
    gate("NO_PER_OBJECT_TURNAROUND", metrics["inter_object_ratio_after"] < 0.01)
    gate("MULTI_OBJECT_PIPELINE", ack.get("objects_in_flight", 0) >= 4)
    gate(
        "HOST_NOT_IN_FAST_PATH",
        metrics["host_blocking_commands_fixed_to_rotating"] <= 4
        and metrics["host_blocking_commands_rotating_to_fixed"] <= 4
        and metrics["minimum_segments_per_host_command"] >= 1000
        and metrics["host_fast_path_dependency_count"] == 0,
    )
    perf_by_direction = {int(item["direction"]): item for item in perf_windows}
    gate("F_TO_R_APPLICATION_GOODPUT_4MBPS", perf_by_direction[0]["application_goodput_bps"] >= 4_000_000)
    gate("R_TO_F_APPLICATION_GOODPUT_4MBPS", perf_by_direction[1]["application_goodput_bps"] >= 4_000_000)
    gate("STREAMING_64M_F_TO_R_5X", stream.get("f2r_64m_count", 0) >= 5)
    gate("STREAMING_64M_R_TO_F_5X", stream.get("r2f_64m_count", 0) >= 5)
    gate("STREAM_ABORT_RESET_RECOVERY", stream.get("recovery_vector_count", 0) >= 3 and stream.get("post_recovery_clean_count", 0) >= 3)
    formal_windows = formal.get("formal_windows", [])
    gate(
        "STATIONARY_30MIN",
        formal.get("elapsed_ms", 0) >= 1_800_000
        and len(formal_windows) == 2
        and all(item.get("duration_seconds", 0) >= 840 for item in formal_windows)
        and all(item.get("application_goodput_bps", 0) >= 4_000_000 for item in formal_windows),
    )
    gate("CRC_BAD_ZERO", counters["crc_bad"] == 0)
    gate("SHA_MISMATCH_ZERO", counters["sha_mismatch"] == 0)
    gate("PARTIAL_DUPLICATE_STALE_ZERO", counters["partial_commit"] == 0 and counters["duplicate_commit"] == 0 and counters["stale_commit"] == 0)
    gate("RETRY_EXHAUSTED_ZERO", counters["retry_exhausted"] == 0)
    gate("DESCRIPTOR_LEAK_ZERO", counters["descriptor_leak"] == 0)
    gate("DOUBLE_COMPLETION_ZERO", counters["double_completion"] == 0)
    gate("DEADLOCK_ZERO", counters["deadlock"] == 0 and counters["transport_timeout"] == 0)
    gate("DUTY_VIOLATION_ZERO", counters["duty_violation"] == 0)
    gate("CONTINUOUS_HIGH_VIOLATION_ZERO", counters["continuous_high_violation"] == 0 and counters["maximum_observed_txd_high_cycles"] <= 64)
    gate(
        "SHUTDOWN_FIXED",
        all(
            item["orchestrator"].get("SHUTDOWN_FIXED") == "PASS"
            for item in results.values()
        ),
    )
    gate(
        "SHUTDOWN_ROTATING",
        all(
            item["orchestrator"].get("SHUTDOWN_ROTATING") == "PASS"
            for item in results.values()
        ),
    )
    gate("EVIDENCE_CONSISTENCY", not errors)
    return gates


def stage_evidence_records(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        record(result["wrapper_path"]),
        record(result["raw_path"]),
        record(result["authorization_path"]),
        record(result["authorization_record_path"]),
        record(result["manifest_path"]),
        record(result["orchestrator_path"]),
    ]


def update_current_authorization(results: dict[str, dict[str, Any]]) -> None:
    authorization = load_json(CURRENT_AUTHORIZATION)
    authorization["status"] = "CONSUMED_AFTER_P10_1R_CAMPAIGN_PASS"
    authorization["campaign_status"] = "PASS"
    authorization["campaign_disposition"] = "ALL_MANDATORY_P10_1R_STAGE_SETS_COMPLETE"
    authorization["current_run_hardware_authorization"] = False
    authorization["consumed"] = True
    authorization["full_campaign_completed"] = True
    authorization["reusable_for_future_run"] = False
    authorization["hardware_actions_executed"] = True
    authorization["shutdown_fixed"] = "PASS"
    authorization["shutdown_rotating"] = "PASS"
    authorization["campaign_stage_runs"] = {
        stage: item["run_id"] for stage, item in results.items()
    }
    authorization["campaign_evidence"] = {
        stage: {
            "orchestrator_result": rel(item["orchestrator_path"]),
            "orchestrator_sha256": sha256(item["orchestrator_path"]),
            "manifest": rel(item["manifest_path"]),
            "manifest_sha256": sha256(item["manifest_path"]),
        }
        for stage, item in results.items()
    }
    authorization["next_required_action"] = "USER_DECISION_AFTER_2LANE_SPEED_STABILITY_PASS"
    write_json(CURRENT_AUTHORIZATION, authorization)


def write_crosstalk_alias(result: dict[str, Any]) -> None:
    source = result["wrapper"]
    payload = {
        "schema_version": 1,
        "test_id": "P10_1R-HW-CROSSTALK-REMEDIATION",
        "generated_at_utc": FINALIZED_AT_UTC,
        "status": "PASS",
        "source_commit": SOURCE_COMMIT,
        "run_id": result["run_id"],
        "hardware_actions_executed": True,
        "finalization_hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "hardware_movement": False,
        "rewiring_executed": False,
        "source_wrapper": record(result["wrapper_path"]),
        "raw_summary": record(result["raw_path"]),
        "run_manifest": record(result["manifest_path"]),
        "orchestrator_result": record(result["orchestrator_path"]),
        "semantics": source.get("semantics", {}),
        "errors": [],
    }
    path = GENERATED / "p10_1r_crosstalk_remediation.json"
    write_json(path, payload)
    write_markdown(
        path.with_suffix(".md"),
        [
            "# P10.1R crosstalk remediation hardware evidence",
            "",
            "- Status: `PASS`",
            f"- Run ID: `{result['run_id']}`",
            f"- Source commit: `{SOURCE_COMMIT}`",
            "- Current-run hardware authorization: `false` (consumed)",
            "- Hardware actions in the recorded run: `true`",
            "- Hardware actions during this finalization: `false`",
            "",
            "The four role-bound cases report zero same-module accepted DATA, zero cross-lane accepted DATA, zero other-lane blanking, and four reconciled intended-remote cases.",
            "",
            "The adjacent JSON and its bound raw run manifest are authoritative.",
        ],
    )


def update_state(
    freeze: dict[str, Any],
    results: dict[str, dict[str, Any]],
    metrics: dict[str, Any],
    gates: dict[str, str],
) -> None:
    state = load_json(STATE)
    state["current_program_stage"] = "USER_DECISION_AFTER_2LANE_SPEED_STABILITY_PASS"
    state["current_run_hardware_authorization"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_hardware_authorization_id"] = "P10_1R-CURRENT-RUN-IMMUTABLE"
    state["last_hardware_run_id"] = results["preflight"]["run_id"]
    state["last_hardware_stage"] = "P10_1R"
    state["last_shutdown_fixed"] = "PASS"
    state["last_shutdown_rotating"] = "PASS"
    state["last_verified_commit"] = SOURCE_COMMIT
    state["p10_1r_status"] = "PASS"
    state["two_lane_speed_stability"] = "PASS_STATIONARY_AX7020_2LANE_HALF_DUPLEX"
    state["p11_status"] = "NOT_STARTED"
    state["p11_hardware_ready"] = False
    state["stage_status"]["P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION"] = "PASS"
    state["state_revision"] = "P10-1R-HARDWARE-PASS-1"
    completed = state.get("completed_gates", [])
    if not any(isinstance(item, dict) and item.get("gate_id") == "P10_1R" for item in completed):
        completed.append({"gate_id": "P10_1R", "status": "PASS"})
    state["completed_gates"] = completed

    remediation = state.get("p10_1r_remediation", {})
    if not isinstance(remediation, dict):
        remediation = {}
    remediation.update(
        {
            "status": "PASS",
            "base_failure_tag": FAILURE_TAG,
            "source_commit": SOURCE_COMMIT,
            "goal_path": rel(GOAL),
            "goal_sha256": GOAL_SHA256,
            "source_artifact_freeze": "PASS",
            "artifact_freeze_path": rel(ARTIFACT_FREEZE),
            "artifact_freeze_sha256": sha256(ARTIFACT_FREEZE),
            "artifacts": freeze["roles"],
            "candidate_guard_cycles": metrics["guard_cycles"],
            "selected_guard_cycles": metrics["guard_cycles"],
            "candidate_guard_hardware_measured": True,
            "current_run_hardware_authorization": False,
            "new_artifact_hardware_validation": "PASS",
            "hardware_actions_executed": True,
            "current_bundle_hardware_actions_executed": True,
            "network_used": False,
            "hardware_movement": False,
            "no_hardware_movement": True,
            "rewiring_executed": False,
            "last_hardware_run_id": results["preflight"]["run_id"],
            "last_shutdown_fixed": "PASS",
            "last_shutdown_rotating": "PASS",
            "campaign_stage_runs": {stage: item["run_id"] for stage, item in results.items()},
            "mandatory_exit_gates": gates,
            "metrics": metrics,
            "p10_functional_status_preserved": "PASS",
            "p11_started": False,
            "checkpoint_tag": PASS_TAG,
            "final_summary_path": rel(FINAL_SUMMARY),
            "hardware_evidence_consistency_path": rel(HARDWARE_CONSISTENCY),
            "scope": "AX7020_DUAL_NODE_STATIONARY_2LANE_HALF_DUPLEX_NO_ETHERNET",
            "scope_exclusions": [
                "ETHERNET",
                "SPI",
                "ONEPLUSONE_FULL_DUPLEX",
                "P11_HANDOVER",
                "8X32",
                "600RPM",
                "PRODUCT_FINAL",
            ],
        }
    )
    blocker = remediation.get("hardware_blocker")
    if isinstance(blocker, dict):
        blocker["status"] = "RESOLVED_BY_EXACT_BUNDLE_HARDWARE_CAMPAIGN"
    state["p10_1r_remediation"] = remediation
    write_json(STATE, state)


def update_requirements(results: dict[str, dict[str, Any]]) -> None:
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("requirements"), list):
        raise ValueError("config/project_requirements.yaml has invalid structure")
    by_id = {
        item.get("requirement_id"): item
        for item in document["requirements"]
        if isinstance(item, dict)
    }
    wrapper_to_result = {
        item["wrapper_path"].name: item for item in results.values()
    }
    crosstalk_alias = GENERATED / "p10_1r_crosstalk_remediation.json"
    for requirement_id, names in REQUIREMENT_BINDINGS.items():
        item = by_id.get(requirement_id)
        if not isinstance(item, dict):
            raise ValueError(f"missing requirement {requirement_id}")
        bindings: list[dict[str, Any]] = []
        for name in names:
            path = GENERATED / name
            bindings.append(record(path))
            source_name = "p10_1r_crosstalk.json" if path == crosstalk_alias else path.name
            result = wrapper_to_result.get(source_name)
            if result is not None:
                bindings.extend([record(result["raw_path"]), record(result["manifest_path"])])
        bindings.append(record(ARTIFACT_FREEZE))
        deduplicated: list[dict[str, Any]] = []
        seen: set[str] = set()
        for binding in bindings:
            if binding["path"] not in seen:
                deduplicated.append(binding)
                seen.add(binding["path"])
        item["status"] = "PASS"
        item["verification_scope"] = "P10_1R_AX7020_STATIONARY_2LANE_HALF_DUPLEX_NO_ETHERNET_HARDWARE_PASS"
        item["verification_stage"] = "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION"
        item["test_id"] = TEST_IDS[requirement_id]
        item["evidence_path"] = deduplicated[0]["path"]
        item["artifact_hash"] = deduplicated[0]["sha256"]
        item["artifact_hashes"] = [
            {"path": binding["path"], "sha256": binding["sha256"]}
            for binding in deduplicated
        ]
        item["hardware_followup"] = (
            "Scoped PASS is limited to the frozen AX7020 stationary two-lane "
            "half-duplex no-Ethernet bundle; it does not promote P11, 1+1 full "
            "duplex, 8x32, 600 rpm, external electrical/optical measurement, "
            "or product-final acceptance."
        )

    mutable_hashes = {rel(STATE): sha256(STATE), rel(STATUS): sha256(STATUS)}
    for item in document["requirements"]:
        if not isinstance(item, dict):
            continue
        hashes = item.get("artifact_hashes", [])
        if not isinstance(hashes, list):
            continue
        for binding in hashes:
            if isinstance(binding, dict) and binding.get("path") in mutable_hashes:
                binding["sha256"] = mutable_hashes[binding["path"]]
        if hashes and isinstance(hashes[0], dict) and hashes[0].get("path") in mutable_hashes:
            item["artifact_hash"] = hashes[0]["sha256"]
    REQUIREMENTS.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
        newline="\n",
    )


def run_check(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        errors="replace",
        env={
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
    )
    return {
        "command": subprocess.list2cmdline(command),
        "return_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def write_consistency(
    freeze: dict[str, Any],
    results: dict[str, dict[str, Any]],
    gates: dict[str, str],
    checks: list[dict[str, Any]],
    errors: list[str],
) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "test_id": "P10_1R-HARDWARE-EVIDENCE-CONSISTENCY",
        "generated_at_utc": FINALIZED_AT_UTC,
        "status": "PASS" if not errors else "FAIL",
        "source_commit": SOURCE_COMMIT,
        "goal_sha256": GOAL_SHA256,
        "hardware_actions_executed": True,
        "finalization_hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "hardware_movement": False,
        "rewiring_executed": False,
        "artifact_freeze": record(ARTIFACT_FREEZE),
        "artifact_roles": freeze["roles"],
        "offline_evidence_consistency_preserved": record(OFFLINE_CONSISTENCY),
        "runs": {
            stage: {
                "run_id": item["run_id"],
                "manifest_file_count": item["manifest_count"],
                "manifest_coverage": "ALL_RUN_FILES_EXCEPT_MANIFEST_AND_FINAL_ORCHESTRATOR",
                "evidence": stage_evidence_records(item),
                "shutdown_fixed": "PASS",
                "shutdown_rotating": "PASS",
            }
            for stage, item in results.items()
        },
        "canonical_files": [record(STATE), record(STATUS), record(REQUIREMENTS), record(TRACEABILITY), record(CURRENT_AUTHORIZATION)],
        "mandatory_exit_gates": gates,
        "checks": checks,
        "errors": errors.copy(),
    }
    write_json(HARDWARE_CONSISTENCY, payload)
    lines = [
        "# P10.1R hardware evidence consistency",
        "",
        f"- Status: `{payload['status']}`",
        f"- Source commit: `{SOURCE_COMMIT}`",
        "- Current-run hardware authorization: `false`",
        "- Hardware actions in the recorded campaign: `true`",
        "- Hardware actions during this finalization: `false`",
        "- Network used: `false`",
        "- Hardware movement / rewiring: `false` / `false`",
        "",
        "## Immutable run coverage",
        "",
        "| Stage | Run ID | Manifest files | Fixed shutdown | Rotating shutdown |",
        "|---|---|---:|---|---|",
    ]
    for stage, item in results.items():
        lines.append(f"| `{stage}` | `{item['run_id']}` | {item['manifest_count']} | PASS | PASS |")
    lines.extend(["", "## Mandatory exit gates", ""])
    lines.extend(f"- `{name}`: `{status}`" for name, status in gates.items())
    lines.extend(
        [
            "",
            "The pre-existing offline consistency evidence remains at `p10_1r_evidence_consistency.json`; it was not overwritten. The adjacent JSON is authoritative for the hardware campaign.",
        ]
    )
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {item}" for item in errors])
    write_markdown(HARDWARE_CONSISTENCY.with_suffix(".md"), lines)
    return payload


def write_final_summary(
    head: str,
    results: dict[str, dict[str, Any]],
    metrics: dict[str, Any],
    gates: dict[str, str],
    errors: list[str],
) -> dict[str, Any]:
    generated = [
        record(GENERATED / STAGES[stage]["wrapper"])
        for stage in STAGES
    ] + [
        record(GENERATED / "p10_1r_crosstalk_remediation.json"),
        record(OFFLINE_CONSISTENCY),
        record(HARDWARE_CONSISTENCY),
        record(GENERATED / "p10_1r_shutdown.json"),
    ]
    payload = {
        "schema_version": 1,
        "test_id": "P10_1R-FINAL-HARDWARE-CHECKPOINT",
        "generated_at_utc": FINALIZED_AT_UTC,
        "status": "PASS" if not errors and all(value == "PASS" for value in gates.values()) else "FAIL",
        "branch": BRANCH,
        "worktree": str(ROOT),
        "head_when_aggregated": head,
        "base_failure_tag": FAILURE_TAG,
        "base_failure_tag_commit": FAILURE_TAG_COMMIT,
        "source_commit": SOURCE_COMMIT,
        "goal_sha256": GOAL_SHA256,
        "checkpoint_tag": PASS_TAG,
        "hardware_actions_executed": True,
        "finalization_hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "no_hardware_movement": True,
        "wiring_changed": False,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating": "AX7020-R/JTAG:210512180081",
        },
        "lane_mapping": {"lane0": "F0-R0", "lane1": "F1-R1"},
        "artifact_freeze": record(ARTIFACT_FREEZE),
        "metrics": metrics,
        "mandatory_exit_gates": gates,
        "stage_runs": {stage: item["run_id"] for stage, item in results.items()},
        "shutdown_fixed": "PASS",
        "shutdown_rotating": "PASS",
        "p10_functional_status_preserved": "PASS",
        "p10_1_failure_baseline_preserved": "FAIL",
        "p11_status": "NOT_STARTED",
        "shutdown_led_physical_confirmation": "PENDING_USER_VISUAL_OR_ELECTRICAL_OBSERVATION",
        "shutdown_led_scope_note": "Both role-bound shutdown bitstreams were programmed with active-low all-off intent and all shutdown markers passed; configuration evidence does not directly measure physical LED pins.",
        "scope_non_promotions": [
            "P11",
            "ONEPLUSONE_FULL_DUPLEX",
            "8X32",
            "600RPM",
            "ETHERNET",
            "SPI",
            "PHYSICAL_GLOBAL_PERMIT",
            "EXTERNAL_TFDU_DUTY",
            "PRODUCT_FINAL",
        ],
        "pass": list(gates),
        "fail": [name for name, value in gates.items() if value != "PASS"],
        "generated_evidence": generated,
        "next_recommended_stage": "USER_DECISION_AFTER_2LANE_SPEED_STABILITY_PASS",
        "errors": errors.copy(),
    }
    write_json(FINAL_SUMMARY, payload)
    goodput = metrics["sustained_application_goodput_bps"]
    counters = metrics["counters"]
    stream = metrics["streaming_64m"]
    committed = metrics["formal_committed_bytes"]
    lines = [
        "# P10.1R AX7020 two-lane speed and stability final summary",
        "",
        f"- Status: `{payload['status']}`",
        f"- Source commit: `{SOURCE_COMMIT}`",
        f"- Planned checkpoint tag: `{PASS_TAG}`",
        "- Current-run hardware authorization: `false`",
        "- Hardware actions in recorded runs: `true`",
        "- Hardware actions during finalization: `false`",
        "- Network / movement / rewiring: `false` / `false` / `false`",
        "",
        "## Acceptance result",
        "",
        f"- F→R sustained application goodput: `{goodput['fixed_to_rotating']} bit/s`",
        f"- R→F sustained application goodput: `{goodput['rotating_to_fixed']} bit/s`",
        f"- Formal runtime: `{metrics['formal_runtime_seconds']} s`",
        f"- Formal committed bytes F→R / R→F: `{committed['fixed_to_rotating']}` / `{committed['rotating_to_fixed']}`",
        f"- 64 MiB objects F→R / R→F: `{stream['fixed_to_rotating_count']}` / `{stream['rotating_to_fixed_count']}`",
        f"- Same-module raw echo / accepted DATA: `{metrics['same_module_raw_echo_count']}` / `{metrics['same_module_accepted_data_count']}`",
        f"- Cross-lane accepted DATA: `{metrics['cross_lane_accepted_data_count']}`",
        f"- Maximum observed Txd high: `{counters['maximum_observed_txd_high_cycles']} cycles`",
        "",
        "## Counter closure",
        "",
        f"- CRC bad / SHA mismatch: `{counters['crc_bad']}` / `{counters['sha_mismatch']}`",
        f"- Partial / duplicate / stale commit: `{counters['partial_commit']}` / `{counters['duplicate_commit']}` / `{counters['stale_commit']}`",
        f"- Retry exhausted / descriptor leak / double completion: `{counters['retry_exhausted']}` / `{counters['descriptor_leak']}` / `{counters['double_completion']}`",
        f"- Deadlock / duty / continuous-high violation: `{counters['deadlock']}` / `{counters['duty_violation']}` / `{counters['continuous_high_violation']}`",
        "",
        "## Mandatory exit gates",
        "",
    ]
    lines.extend(f"- `{name}`: `{value}`" for name, value in gates.items())
    lines.extend(
        [
            "",
            "## Scope retained",
            "",
            "This PASS is limited to the frozen stationary AX7020 two-lane half-duplex no-Ethernet artifact bundle. P11, 1+1 full duplex, 8×32, 600 rpm, physical GLOBAL_PERMIT, external TFDU electrical/duty measurement, and product-final acceptance remain outside scope.",
            "",
            "Physical observation of the four PL LEDs in shutdown remains pending; the shutdown programming and marker evidence proves configuration intent, not the voltage or visible state at the LED pins.",
        ]
    )
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {item}" for item in errors])
    write_markdown(FINAL_SUMMARY.with_suffix(".md"), lines)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []

    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be exactly 1 for evidence finalization")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    branch = git("branch", "--show-current").stdout.strip()
    head = git("rev-parse", "HEAD").stdout.strip()
    expect(branch == BRANCH, f"branch is {branch}, expected {BRANCH}", errors)
    expect(sha256(GOAL) == GOAL_SHA256, "Goal SHA256 mismatch", errors)
    expect(git("merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD", check=False).returncode == 0, "source commit is not an ancestor of HEAD", errors)
    expect(git("rev-parse", f"{FAILURE_TAG}^{{}}", check=False).stdout.strip() == FAILURE_TAG_COMMIT, "failure tag target mismatch", errors)

    freeze = verify_artifact_freeze(errors)
    failure_baseline = load_json(FAILURE_BASELINE)
    current_authorization = load_json(CURRENT_AUTHORIZATION)
    expect(current_authorization.get("source_commit") == SOURCE_COMMIT, "current authorization source mismatch", errors)
    expect(current_authorization.get("goal_sha256") == GOAL_SHA256, "current authorization Goal mismatch", errors)
    expect(immutable_artifact_set(current_authorization) == {(role, kind, digest) for (role, kind), digest in EXPECTED_ARTIFACTS.items()}, "current authorization artifact ledger mismatch", errors)
    expect(current_authorization.get("current_run_hardware_authorization") is False, "current authorization remains active", errors)
    expect(current_authorization.get("consumed") is True, "current authorization is not consumed", errors)

    results: dict[str, dict[str, Any]] = {}
    for stage, spec in STAGES.items():
        try:
            results[stage] = verify_run(stage, spec, errors)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{stage}: evidence verification exception: {exc}")
    if set(results) != set(STAGES):
        errors.append("not every required stage could be loaded")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("P10_1R_HARDWARE_FINALIZATION=FAIL")
        return 1

    metrics = build_metrics(results)
    gates = build_exit_gates(results, metrics, failure_baseline, current_authorization, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("P10_1R_HARDWARE_FINALIZATION=FAIL")
        return 1

    write_crosstalk_alias(results["crosstalk"])
    update_current_authorization(results)
    update_state(freeze, results, metrics, gates)

    status_write = run_check([sys.executable, "scripts/generate_project_status.py", "--write"])
    if status_write["status"] != "PASS":
        errors.append("project status generation failed")
    if not errors:
        update_requirements(results)
        trace_write = run_check([sys.executable, "scripts/generate_requirement_traceability.py", "--write"])
        if trace_write["status"] != "PASS":
            errors.append("requirement traceability generation failed")

    checks = [
        run_check([sys.executable, "scripts/generate_project_status.py", "--check"]),
        run_check([sys.executable, "scripts/generate_requirement_traceability.py", "--check"]),
        run_check([sys.executable, "scripts/check_p8a_consistency.py", "--check"]),
        run_check([sys.executable, "scripts/check_no_hardware_calls.py"]),
        run_check(["git", "diff", "--check"]),
    ]
    for check in checks:
        if check["status"] != "PASS":
            errors.append(f"consistency command failed: {check['command']}")
    if errors:
        gates["EVIDENCE_CONSISTENCY"] = "FAIL"

    write_consistency(freeze, results, gates, checks, errors)
    final = write_final_summary(head, results, metrics, gates, errors)

    print(f"P10_1R_HARDWARE_FINALIZATION={final['status']}")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    print("FINALIZATION_HARDWARE_ACTIONS_EXECUTED=false")
    print(f"FINAL_SUMMARY_SHA256={sha256(FINAL_SUMMARY)}")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if final["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
