#!/usr/bin/env python3
"""Finalize the completed P10.3/P10.3F hardware campaign without hardware I/O.

This closeout consumes only the immutable evidence already committed by the
hardware runner.  It verifies the run manifest, artifact bindings, safety and
performance gates, consumes no new authorization, and then updates canonical
state/requirements plus generated status and traceability documents.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from p8a_common import render_project_status, validate_requirements, validate_state


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
STATE = ROOT / "config/project_state.json"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATUS = ROOT / "PROJECT_STATUS.md"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
AUTHORIZATION = ROOT / "config/p10_3f_full_current_run_hardware_authorization.json"
GOAL = ROOT / "goals/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md"

BRANCH = "p10.3/ax7020-stationary-4lane-hardware"
PASS_TAG = "p10.3-ax7020-stationary-4lane-pass"
P10_3_STAGE = "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE"
RUN_ID = "p10_3f_full_20260805T065127Z_e356dd92_1ff0885f_82ef5093"
RUN_ROOT = ROOT / "evidence/hardware/p10_3f_full" / RUN_ID
ORCHESTRATOR = RUN_ROOT / "final/orchestrator_result.json"
MANIFEST = RUN_ROOT / "final/run_evidence_sha256_manifest.json"
FINAL_SUMMARY = GENERATED / "p10_3_final_summary.json"
CONSISTENCY = GENERATED / "p10_3_evidence_consistency.json"
SHUTDOWN = GENERATED / "p10_3_shutdown.json"
CLOSEOUT = GENERATED / "p10_3_hardware_closeout.json"

GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
ARTIFACT_SOURCE_COMMIT = "7fc3a7cb03f9ee19793403f9f1deaef139b11d7d"
HOST_SOURCE_COMMIT = "e356dd9216da528af0a21d39a0eced9b4e96ee1e"
EVIDENCE_COMMIT = "e64c04843d5d996f8d66d650fafaf3a43a2dd7dc"

EXPECTED_STAGES = {
    "preflight", "module_intake", "staircase_1k", "staircase_4k",
    "staircase_16k", "staircase_64k", "staircase_256k", "fault_capture",
    "raw_8x8", "per_lane_phy", "two_lane_regression", "four_lane_raw",
    "mask_matrix", "degrade", "arq_sack", "dma", "streaming_64m",
    "stream_dma_reset_fault", "stream_dma_reset_recovery_64m",
    "stream_service_reset_fault", "stream_service_reset_recovery_64m",
    "performance", "formal_30min",
}

EXPECTED_ARTIFACTS = {
    ("fixed", "shutdown_bitstream"): "df394f8a5d4eb68613749df78af43dab7705e87b3cbf091db8f69dd33cce251c",
    ("fixed", "functional_bitstream"): "1ff0885f89674557144e6c41bf40ef05bb56c8ef85f1b8bd16ef0fc8e8c3b724",
    ("fixed", "xsa"): "86945089f69cbb2b25dd6d71f08a7f6b6b699f9e7619dba70686f1e612379460",
    ("fixed", "bsp"): "330ebffd7de59df6fa6e6c20e39187885b521a73fba7d85697ed13e81a388600",
    ("fixed", "elf"): "7ea3542ac346eb567371cd7635ebcb597f10df7b51b756e76ab57e9e03077b40",
    ("rotating", "shutdown_bitstream"): "1fc058e1b83f5ef9d0a4a37090515301559c9e81f218b4de218577542d8fefa0",
    ("rotating", "functional_bitstream"): "82ef5093e7f1de7676ad2fff26dae55a60a869c39e16f327b9db826f87cf0830",
    ("rotating", "xsa"): "328015e208f43db1faeb7a9272619a970c4ca895b73a6b817ead253f98af434d",
    ("rotating", "bsp"): "83e74bd963c23a639fd5dfb28d554e83264b79272ab1c4da4883a98216d586e0",
    ("rotating", "elf"): "c21f8c9c0d88783b1163d3c20c17ac49ff7b2463511abf9ddf3889f3152d1f7d",
}

REQUIREMENT_EVIDENCE = {
    "P10_3-WIRE-001": "p10_3_wiring.json",
    "P10_3-INV-001": "p10_3_module_inventory.json",
    "P10_3-INV-002": "p10_3_module_inventory.json",
    "P10_3-HW-001": "p10_3_authorization.json",
    "P10_3-HW-002": "p10_3_artifact_freeze.json",
    "P10_3-LED-001": "p10_3_safe_boot.json",
    "P10_3-LED-002": "p10_3_safe_boot.json",
    "P10_3-SAFE-001": "p10_3_safe_boot.json",
    "P10_3-SAFE-002": "p10_3_shutdown.json",
    "P10_3-MOD-001": "p10_3_module_intake.json",
    "P10_3-MOD-002": "p10_3_module_intake.json",
    "P10_3-MOD-003": "p10_3_module_intake.json",
    "P10_3-MOD-004": "p10_3_module_intake.json",
    "P10_3-XTALK-001": "p10_3_raw_8x8.json",
    "P10_3-PHY-001": "p10_3_per_lane_phy.json",
    "P10_3-PHY-002": "p10_3_per_lane_phy.json",
    "P10_3-PHY-003": "p10_3_per_lane_phy.json",
    "P10_3-PHY-004": "p10_3_per_lane_phy.json",
    "P10_3-PHY-005": "p10_3_four_lane_raw.json",
    "P10_3-MASK-001": "p10_3_mask_matrix.json",
    "P10_3-DEG-001": "p10_3_degraded_modes.json",
    "P10_3-ARQ-001": "p10_3_arq_scheduler.json",
    "P10_3-STREAM-001": "p10_3_streaming_64m.json",
    "P10_3-STREAM-002": "p10_3_streaming_64m.json",
    "P10_3-PERF-001": "p10_3_performance.json",
    "P10_3-PERF-002": "p10_3_performance.json",
    "P10_3-SOAK-001": "p10_3_formal_30min.json",
    "P10_3-EVID-001": "p10_3_evidence_consistency.json",
    "P10_3F-HW-001": "p10_3f_hardware/final/summary.json",
    "P10_3F-HW-002": "p10_3f_hardware/final/summary.json",
    "P10_3F-HW-003": "p10_3f_hardware/final/summary.json",
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
        raise ValueError(f"{rel(path)} must contain an object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=check, text=True,
        capture_output=True, errors="replace",
    )


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def verify_manifest(errors: list[str]) -> int:
    manifest = load_json(MANIFEST)
    require(manifest.get("schema_version") == 1, "manifest schema mismatch", errors)
    require(manifest.get("status") == "INDEX_GENERATED", "manifest status mismatch", errors)
    require(manifest.get("acceptance_status") == "PASS", "manifest acceptance is not PASS", errors)
    require(manifest.get("run_id") == RUN_ID, "manifest run ID mismatch", errors)
    entries = manifest.get("files")
    if not isinstance(entries, list):
        errors.append("manifest files is not a list")
        return 0
    seen: set[str] = set()
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            errors.append(f"manifest[{index}] is malformed")
            continue
        name = item.get("path")
        if not isinstance(name, str) or not name or "\\" in name or name in seen:
            errors.append(f"manifest[{index}] path is invalid or duplicate")
            continue
        path = (RUN_ROOT / name).resolve()
        try:
            path.relative_to(RUN_ROOT.resolve())
        except ValueError:
            errors.append(f"manifest path escapes run root: {name}")
            continue
        if not path.is_file():
            errors.append(f"manifest file missing: {name}")
            continue
        seen.add(name)
        require(path.stat().st_size == item.get("bytes"), f"manifest size mismatch: {name}", errors)
        require(sha256(path) == item.get("sha256"), f"manifest SHA256 mismatch: {name}", errors)
    expected = {
        path.relative_to(RUN_ROOT).as_posix()
        for path in RUN_ROOT.rglob("*")
        if path.is_file() and path != MANIFEST
    }
    require(seen == expected, "manifest does not cover the exact run file set", errors)
    return len(entries)


def verify_campaign(errors: list[str]) -> tuple[dict[str, Any], int]:
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be exactly 1", errors)
    require(
        os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() == "false",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false", errors,
    )
    require(git("branch", "--show-current").stdout.strip() == BRANCH, "wrong closeout branch", errors)
    dirty = {
        line[3:].replace("\\", "/")
        for line in git("status", "--porcelain").stdout.splitlines()
        if len(line) >= 4
    }
    resumable = {
        "PROJECT_STATUS.md", "config/project_requirements.yaml",
        "config/project_state.json", "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
        "scripts/p8a_common.py", "scripts/finalize_p10_3_hardware.py",
        "scripts/run_p10_3f_full_hardware.py",
        "scripts/verify_p10_existing.py",
        "tests/test_p8a_consistency.py",
        "evidence/generated/p10_3_hardware_closeout.json",
        "evidence/generated/p10_3_hardware_closeout.md",
        "evidence/generated/p8a_consistency_summary.json",
    }
    require(not dirty or dirty <= resumable, "worktree has non-closeout changes", errors)
    require(sha256(GOAL) == GOAL_SHA256, "Goal SHA256 mismatch", errors)
    require(
        git("merge-base", "--is-ancestor", EVIDENCE_COMMIT, "HEAD", check=False).returncode == 0,
        "evidence commit is not an ancestor", errors,
    )
    require(
        git("merge-base", "--is-ancestor", ARTIFACT_SOURCE_COMMIT, "HEAD", check=False).returncode == 0,
        "artifact source commit is not an ancestor", errors,
    )

    summary = load_json(FINAL_SUMMARY)
    consistency = load_json(CONSISTENCY)
    shutdown = load_json(SHUTDOWN)
    auth = load_json(AUTHORIZATION)
    orchestrator = load_json(ORCHESTRATOR)
    for label, value in (("summary", summary), ("orchestrator", orchestrator)):
        require(value.get("status") == "PASS", f"{label} is not PASS", errors)
        require(value.get("run_id") == RUN_ID, f"{label} run ID mismatch", errors)
        require(value.get("goal_sha256") == GOAL_SHA256, f"{label} Goal mismatch", errors)
        require(value.get("artifact_source_commit") == ARTIFACT_SOURCE_COMMIT, f"{label} artifact source mismatch", errors)
        require(value.get("host_source_commit") == HOST_SOURCE_COMMIT, f"{label} host source mismatch", errors)
        require(value.get("SHUTDOWN_FIXED") == "PASS", f"{label} fixed shutdown failed", errors)
        require(value.get("SHUTDOWN_ROTATING") == "PASS", f"{label} rotating shutdown failed", errors)
        require(value.get("current_run_hardware_authorization") is False, f"{label} authorization remains active", errors)
        require(value.get("errors") == [], f"{label} errors are non-empty", errors)
    require(consistency.get("status") == "PASS", "consistency is not PASS", errors)
    require(consistency.get("verified_complete_file_set") is True, "complete file-set proof missing", errors)
    require(consistency.get("errors") == [], "consistency errors are non-empty", errors)
    require(shutdown.get("status") == "PASS", "shutdown summary is not PASS", errors)
    require(shutdown.get("SHUTDOWN_FIXED") == "PASS", "fixed shutdown marker missing", errors)
    require(shutdown.get("SHUTDOWN_ROTATING") == "PASS", "rotating shutdown marker missing", errors)
    require(auth.get("consumed") is True, "authorization is not consumed", errors)
    require(auth.get("current_run_hardware_authorization") is False, "authorization is still current", errors)
    require(auth.get("status") == "CONSUMED_AFTER_P10_3F_FULL_PASS", "authorization lifecycle mismatch", errors)
    require(auth.get("run_id") == RUN_ID, "authorization run mismatch", errors)

    require(summary.get("hardware_actions_executed") is True, "hardware action marker missing", errors)
    for key in ("ethernet_used", "movement", "rotation", "realignment", "rewiring"):
        require(summary.get(key) is False, f"scope boundary {key} is not false", errors)
    require(summary.get("maximum_lane_mask") == 15, "maximum lane mask is not 0xF", errors)
    require(summary.get("old_hardware_pass_inherited") is False, "old PASS was inherited", errors)

    stages = summary.get("stages")
    stage_map = {
        str(item.get("stage")): item.get("status")
        for item in stages if isinstance(item, dict)
    } if isinstance(stages, list) else {}
    require(set(stage_map) == EXPECTED_STAGES, "required stage set mismatch", errors)
    require(all(value == "PASS" for value in stage_map.values()), "not every stage is PASS", errors)

    artifacts = {
        (str(item.get("role")), str(item.get("kind"))): item
        for item in summary.get("artifacts", []) if isinstance(item, dict)
    }
    require(set(artifacts) == set(EXPECTED_ARTIFACTS), "artifact ledger set mismatch", errors)
    for key, expected_digest in EXPECTED_ARTIFACTS.items():
        item = artifacts.get(key, {})
        require(item.get("sha256") == expected_digest, f"{key}: artifact digest mismatch", errors)
        path = (ROOT / str(item.get("path", ""))).resolve()
        try:
            path.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f"{key}: artifact path escapes repository")
            continue
        require(path.is_file(), f"{key}: artifact file missing", errors)
        if path.is_file():
            require(sha256(path) == expected_digest, f"{key}: artifact file SHA mismatch", errors)

    metrics = summary.get("metrics", {})
    goodput = metrics.get("application_goodput_bps", {})
    formal = metrics.get("formal", {})
    require(float(goodput.get("F_TO_R", 0)) >= 8_000_000, "F-to-R goodput below 8 Mbit/s", errors)
    require(float(goodput.get("R_TO_F", 0)) >= 8_000_000, "R-to-F goodput below 8 Mbit/s", errors)
    require(float(formal.get("runtime_seconds", 0)) >= 1800, "formal runtime below 1800 seconds", errors)
    require(int(formal.get("committed_bytes_f_to_r", 0)) >= 300 * 1024 * 1024, "formal F-to-R bytes below 300 MiB", errors)
    require(int(formal.get("committed_bytes_r_to_f", 0)) >= 300 * 1024 * 1024, "formal R-to-F bytes below 300 MiB", errors)
    for key in ("duty_violation", "continuous_high_violation", "sha_mismatch", "partial_commit", "duplicate_commit", "stale_commit", "retry_exhausted", "descriptor_leak", "double_completion"):
        require(metrics.get("counters", {}).get(key) == 0, f"safety/integrity counter {key} is nonzero", errors)
    require(all(value == 0 for value in metrics.get("module_hard_fault", {}).values()), "module hard fault is nonzero", errors)
    require(all(value <= 16 for value in metrics.get("maximum_continuous_high_cycles", {}).values()), "TX high limit exceeded", errors)
    require(all(value <= 11520 for value in metrics.get("maximum_duty_cycles", {}).values()), "duty target exceeded", errors)

    formal_stage = load_json(RUN_ROOT / "stages/formal_30min/stage_summary.json")
    require(formal_stage.get("status") == "PASS", "formal raw stage is not PASS", errors)
    require(formal_stage.get("errors") == [], "formal raw stage errors are non-empty", errors)
    windows = formal_stage.get("semantics", {}).get("formal_windows", [])
    require(len(windows) == 2, "formal direction windows missing", errors)
    if len(windows) == 2:
        require({item.get("direction") for item in windows} == {0, 1}, "formal directions mismatch", errors)
        require(all(item.get("application_goodput_bps", 0) >= 8_000_000 for item in windows), "formal window goodput below target", errors)
        require(all(item.get("committed_bytes", 0) >= 300 * 1024 * 1024 for item in windows), "formal window bytes below target", errors)

    return summary, verify_manifest(errors)


def update_state(summary: dict[str, Any]) -> dict[str, Any]:
    state = load_json(STATE)
    consistency = load_json(CONSISTENCY)
    metrics = summary["metrics"]
    state.setdefault("stage_status", {})[P10_3_STAGE] = "PASS"
    state["p10_3_status"] = "PASS"
    state["stationary_4lane_hardware"] = "PASS"
    state["four_lane_raw_16mbps"] = "PASS"
    state["four_lane_application_8mbps"] = "PASS"
    state["current_program_stage"] = "USER_DECISION_AFTER_P10_3"
    state["current_run_hardware_authorization"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_hardware_authorization_id"] = "P10_3F-FULL-CURRENT-RUN-IMMUTABLE"
    state["last_hardware_evidence_checkpoint"] = EVIDENCE_COMMIT
    state["last_hardware_run_id"] = RUN_ID
    state["last_hardware_stage"] = "P10_3"
    state["last_shutdown_fixed"] = "PASS"
    state["last_shutdown_rotating"] = "PASS"
    state["last_verified_commit"] = EVIDENCE_COMMIT
    state["p10_3_current_run_authorization"] = {
        "path": rel(AUTHORIZATION), "sha256": sha256(AUTHORIZATION),
        "status": "CONSUMED_AFTER_P10_3F_FULL_PASS", "consumed": True,
        "current_run_hardware_authorization": False, "run_id": RUN_ID,
    }
    state["p10_3_acceptance"] = {
        "status": "PASS",
        "scope": "STATIONARY_AX7020_FOUR_LANE_NO_ETHERNET_WITH_FIRST_FAULT_FORENSICS",
        "run_id": RUN_ID,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": ARTIFACT_SOURCE_COMMIT,
        "host_source_commit": HOST_SOURCE_COMMIT,
        "evidence_checkpoint_commit": EVIDENCE_COMMIT,
        "evidence_checkpoint_tag": PASS_TAG,
        "evidence_path": rel(ORCHESTRATOR),
        "evidence_sha256": sha256(ORCHESTRATOR),
        "evidence_manifest_path": rel(MANIFEST),
        "evidence_manifest_sha256": sha256(MANIFEST),
        "actual_wiring_sha256": consistency["actual_wiring_sha256"],
        "module_inventory_sha256": consistency["module_inventory_sha256"],
        "fixed_board_id": "AX7020-F/JTAG:210249855178",
        "rotating_board_id": "AX7020-R/JTAG:210512180081",
        "module_binding": summary["module_binding"],
        "hardware_actions_executed": True,
        "network_used": False,
        "hardware_movement": False,
        "rotation_executed": False,
        "realignment_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0xF",
        "two_hour_qualification_executed": False,
        "application_goodput_f_to_r_bps": metrics["application_goodput_bps"]["F_TO_R"],
        "application_goodput_r_to_f_bps": metrics["application_goodput_bps"]["R_TO_F"],
        "formal_runtime_seconds": metrics["formal"]["runtime_seconds"],
        "formal_committed_bytes_f_to_r": metrics["formal"]["committed_bytes_f_to_r"],
        "formal_committed_bytes_r_to_f": metrics["formal"]["committed_bytes_r_to_f"],
        "shutdown_fixed": "PASS", "shutdown_rotating": "PASS",
        "external_four_lane_power_acceptance": "PENDING_EXTERNAL_MEASUREMENT",
        "external_tfdu_duty": "PENDING_EXTERNAL_MEASUREMENT",
        "manual_instrumentation": "OMITTED_BY_USER",
        "not_promoted_to": ["P11", "8X32", "600_RPM", "ETHERNET", "SPI", "PHYSICAL_GLOBAL_PERMIT", "PRODUCT_FINAL"],
    }
    state["state_revision"] = "P10-3-STATIONARY-4LANE-HARDWARE-PASS-1"
    write_json(STATE, state)
    STATUS.write_text(render_project_status(state), encoding="utf-8", newline="\n")
    return state


def update_requirements() -> dict[str, Any]:
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    by_id = {
        item.get("requirement_id"): item
        for item in document.get("requirements", []) if isinstance(item, dict)
    }
    common = [
        {"path": rel(ORCHESTRATOR), "sha256": sha256(ORCHESTRATOR)},
        {"path": rel(MANIFEST), "sha256": sha256(MANIFEST)},
    ]
    missing = sorted(set(REQUIREMENT_EVIDENCE) - set(by_id))
    if missing:
        raise ValueError("missing requirements: " + ", ".join(missing))
    for requirement_id, evidence_name in REQUIREMENT_EVIDENCE.items():
        item = by_id[requirement_id]
        evidence = GENERATED / evidence_name
        value = load_json(evidence)
        if value.get("status") not in {"PASS", "CONSUMED_AFTER_P10_3F_FULL_PASS"}:
            raise ValueError(f"{requirement_id}: evidence is not PASS/consumed-PASS")
        item["status"] = "PASS"
        item["evidence_path"] = rel(evidence)
        item["artifact_hash"] = sha256(evidence)
        item["artifact_hashes"] = [
            {"path": rel(evidence), "sha256": sha256(evidence)},
            *[binding.copy() for binding in common],
        ]
        item["hardware_followup"] = (
            "P10.3 PASS is stationary four-lane AX7020 scope only; P11, 8x32, "
            "600 rpm, Ethernet/SPI, physical GLOBAL_PERMIT, external electrical/duty "
            "measurement and product-final acceptance remain pending."
        )

    state_hash = sha256(STATE)
    status_hash = sha256(STATUS)
    for item in document.get("requirements", []):
        if not isinstance(item, dict):
            continue
        for binding in item.get("artifact_hashes", []):
            if binding.get("path") == "config/project_state.json":
                binding["sha256"] = state_hash
            elif binding.get("path") == "PROJECT_STATUS.md":
                binding["sha256"] = status_hash
        if item.get("evidence_path") == "config/project_state.json":
            item["artifact_hash"] = state_hash
        elif item.get("evidence_path") == "PROJECT_STATUS.md":
            item["artifact_hash"] = status_hash
    REQUIREMENTS.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8", newline="\n",
    )
    subprocess.run(
        [sys.executable, "scripts/generate_requirement_traceability.py", "--write"],
        cwd=ROOT, check=True,
        env={**os.environ, "NO_HARDWARE": "1", "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    return document


def write_closeout(summary: dict[str, Any], manifest_count: int, state: dict[str, Any]) -> None:
    metrics = summary["metrics"]
    payload = {
        "schema_version": 1,
        "test_id": "P10_3-HARDWARE-CLOSEOUT",
        "status": "PASS",
        "scope": P10_3_STAGE,
        "branch": BRANCH,
        "run_id": RUN_ID,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": ARTIFACT_SOURCE_COMMIT,
        "host_source_commit": HOST_SOURCE_COMMIT,
        "evidence_commit": EVIDENCE_COMMIT,
        "planned_pass_tag": PASS_TAG,
        "hardware_actions_executed_in_campaign": True,
        "hardware_actions_executed_during_closeout": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "movement_rotation_realignment_or_rewiring": False,
        "maximum_lane_mask": 15,
        "two_hour_test_executed": False,
        "stage_count": len(EXPECTED_STAGES),
        "stage_pass_count": len(EXPECTED_STAGES),
        "direct_observation_count": metrics["direct_observation_count"],
        "application_goodput_bps": metrics["application_goodput_bps"],
        "formal": metrics["formal"],
        "maximum_duty_cycles": metrics["maximum_duty_cycles"],
        "maximum_continuous_high_cycles": metrics["maximum_continuous_high_cycles"],
        "module_hard_fault": metrics["module_hard_fault"],
        "diagnostic_injection_counters": {
            "crc_bad": metrics["counters"]["crc_bad"],
            "deadlock": metrics["counters"]["deadlock"],
            "transport_timeout": metrics["counters"]["transport_timeout"],
            "classification": "EXPECTED_CONTROLLED_INJECTION_STAGES_NOT_FORMAL_ERRORS",
        },
        "acceptance_integrity_and_safety_counters": {
            key: metrics["counters"][key] for key in (
                "sha_mismatch", "partial_commit", "duplicate_commit", "stale_commit",
                "retry_exhausted", "descriptor_leak", "double_completion",
                "duty_violation", "continuous_high_violation",
            )
        },
        "shutdown_fixed": "PASS", "shutdown_rotating": "PASS",
        "external_four_lane_power_acceptance": "PENDING_EXTERNAL_MEASUREMENT",
        "external_tfdu_duty": "PENDING_EXTERNAL_MEASUREMENT",
        "manual_instrumentation": "OMITTED_BY_USER",
        "manifest_file_count": manifest_count,
        "records": [
            record(ORCHESTRATOR), record(MANIFEST), record(FINAL_SUMMARY),
            record(CONSISTENCY), record(SHUTDOWN), record(AUTHORIZATION),
            record(STATE), record(STATUS), record(REQUIREMENTS), record(TRACEABILITY),
        ],
        "canonical_state": {
            "p10_3_status": state["p10_3_status"],
            "current_program_stage": state["current_program_stage"],
            "p11_status": state["p11_status"],
        },
        "scope_non_promotions": ["P11", "8X32", "600_RPM", "PRODUCT_FINAL"],
        "next_recommended_stage": "USER_DECISION_AFTER_P10_3",
        "errors": [],
    }
    write_json(CLOSEOUT, payload)
    md = [
        "# P10.3 stationary four-lane hardware closeout",
        "",
        "- Status: `PASS`",
        f"- Run ID: `{RUN_ID}`",
        f"- Evidence commit: `{EVIDENCE_COMMIT}`",
        f"- Planned PASS tag: `{PASS_TAG}`",
        f"- Stages: `{len(EXPECTED_STAGES)}/{len(EXPECTED_STAGES)} PASS`",
        f"- Direct observations: `{metrics['direct_observation_count']}`",
        f"- F→R / R→F application goodput: `{metrics['application_goodput_bps']['F_TO_R']}` / `{metrics['application_goodput_bps']['R_TO_F']}` bit/s",
        f"- Formal runtime: `{metrics['formal']['runtime_seconds']}` s",
        f"- Formal committed bytes F→R / R→F: `{metrics['formal']['committed_bytes_f_to_r']}` / `{metrics['formal']['committed_bytes_r_to_f']}`",
        "- Fixed / rotating shutdown: `PASS` / `PASS`",
        "- Current-run hardware authorization: `false` (consumed)",
        "- Network / movement / rotation / realignment / rewiring: `false`",
        "",
        "Campaign-wide CRC-bad, deadlock and transport-timeout counters came only from controlled fault-injection stages; the formal stage itself passed its zero-error checks. No such diagnostic counter is reclassified as an unexpected acceptance failure.",
        "",
        "External power/duty instrumentation was omitted by user instruction, so external electrical/duty acceptance remains pending. This PASS does not promote P11, 8×32, 600 rpm, or product-final acceptance.",
    ]
    CLOSEOUT.with_suffix(".md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    errors: list[str] = []
    summary, manifest_count = verify_campaign(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print("P10_3_HARDWARE_CLOSEOUT=FAIL")
        return 1

    state = update_state(summary)
    requirements = update_requirements()
    state_errors = validate_state(state, ROOT)
    requirement_errors = validate_requirements(requirements, ROOT)
    if state_errors or requirement_errors:
        for error in [*state_errors, *requirement_errors]:
            print(f"ERROR: {error}")
        print("P10_3_HARDWARE_CLOSEOUT=FAIL")
        return 1
    write_closeout(summary, manifest_count, state)
    print("P10_3_HARDWARE_CLOSEOUT=PASS")
    print(f"P10_3_RUN_ID={RUN_ID}")
    print(f"P10_3_EVIDENCE_COMMIT={EVIDENCE_COMMIT}")
    print(f"P10_3_MANIFEST_FILES={manifest_count}")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    print("SHUTDOWN_FIXED=PASS")
    print("SHUTDOWN_ROTATING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
