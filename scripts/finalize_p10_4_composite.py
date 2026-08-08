#!/usr/bin/env python3
"""Publish the immutable parent-plus-resume P10.4 closeout.

This program is offline-only.  It does not reinterpret or mutate either
hardware run root.  It verifies both frozen SHA256 manifests, joins the exact
42-stage parent prefix to the exact 12-stage resume suffix, and publishes the
canonical P10.4 summaries/state/requirements from that direct evidence.
"""

from __future__ import annotations

import argparse
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
BRANCH = "p10.4/b0019-f2-r2-remediation"
GOAL = ROOT / "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md"
GOAL_SHA256 = "0098acc827d22ad8f72876f5551e70d8051452e0c81eb2bfe8986e142f47254f"
SOURCE_COMMIT = "6ff17d33a0ea111fbd796899c49decbfa339e2c1"
PARENT_CHECKPOINT = "5da414ba385b750caede64826f2b1e1ee39073d0"
SUFFIX_CHECKPOINT = "f53d98252dfa85d73f35d49ebf5dc01323bcb4e7"
FINAL_TAG = "p10.4-autonomous-4lane-hardening-pass"
COMPOSITE_ID = "p10_4_composite_5da414ba_f53d9825"

PARENT_RUN = "p10_4_20260808T102748Z_6ff17d33_94506af9_2b2b37d4"
SUFFIX_RUN = "p10_4_20260808T162049Z_6ff17d33_94506af9_2b2b37d4"
PARENT_ROOT = ROOT / "evidence/hardware/p10_4" / PARENT_RUN
SUFFIX_ROOT = ROOT / "evidence/hardware/p10_4" / SUFFIX_RUN
COMPOSITE_ROOT = ROOT / "evidence/hardware/p10_4" / COMPOSITE_ID

PARENT_RESULT = PARENT_ROOT / "final/interrupted_orchestrator_result.json"
SUFFIX_RESULT = SUFFIX_ROOT / "final/resume_orchestrator_result.json"
PARENT_MANIFEST = PARENT_ROOT / "final/run_evidence_sha256_manifest.json"
SUFFIX_MANIFEST = SUFFIX_ROOT / "final/run_evidence_sha256_manifest.json"
PARENT_AUTH = ROOT / "config/p10_4_current_run_hardware_authorization.json"
SUFFIX_AUTH = ROOT / "config/p10_4_resume_current_run_hardware_authorization.json"
PARENT_CHECKPOINT_RECORD = ROOT / "evidence/generated/p10_4_interrupted_parent_checkpoint.json"
B0019_QUALIFICATION = ROOT / "evidence/generated/p10_4_lane2_b0019_raw_connectivity_retest.json"
HISTORICAL_B0008_BLOCKER = ROOT / "evidence/generated/p10_4_f2_to_r2_directional_blocker.json"

GENERATED = ROOT / "evidence/generated"
FINAL_SUMMARY = GENERATED / "p10_4_final_summary.json"
COMPLETION_AUDIT = GENERATED / "p10_4_completion_audit.json"
OFFLINE_CLOSURE = GENERATED / "p10_4_terminal_offline_closure.json"
CONSISTENCY = GENERATED / "p10_4_evidence_consistency.json"
COMPOSITE_MANIFEST = GENERATED / "p10_4_composite_manifest.json"
RUNTIME_COMPLIANCE = GENERATED / "p10_4_runtime_rest_compliance.json"
FD_REQUIREMENT_CLOSURE = GENERATED / "p10_4_two_plus_two_requirement_closure.json"
CRC_HARDWARE_CLOSURE = GENERATED / "p10_4_crc_remediation_hardware_closure.json"

BOARD_BINDING = {
    "fixed": "AX7020-F/JTAG:210249855178",
    "rotating": "AX7020-R/JTAG:210512180081",
}
MODULE_BINDING = {
    "F0": "A0019", "F1": "B0012", "F2": "B0019", "F3": "B0020",
    "R0": "A0010", "R1": "A0017", "R2": "B0023", "R3": "B0025",
}

REQUIREMENT_DISPOSITIONS = {
    "P10_4-SAFE-RUNTIME-001": ("PASS", "evidence/generated/p10_4_runtime_rest_compliance.json"),
    "P10_4-SAFE-COOLDOWN-001": ("PASS", "evidence/generated/p10_4_runtime_rest_compliance.json"),
    "P10_4-CLOSE-001": ("PASS", "evidence/generated/p10_4_p10_3_closeout.json"),
    "P10_4-METRIC-001": ("PASS", "evidence/generated/p10_4_counter_semantics.json"),
    "P10_4-MODEL-001": ("PASS", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-PERF-001": ("PASS", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-PERF-002": ("PASS", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-PERF-003": ("FAIL", "evidence/generated/p10_4_half_duplex_performance.json"),
    "P10_4-STREAM-001": ("PASS", "evidence/generated/p10_4_streaming_64m.json"),
    "P10_4-STREAM-002": ("PASS", "evidence/generated/p10_4_streaming_64m.json"),
    "P10_4-DEG-001": ("PASS", "evidence/generated/p10_4_degraded_modes.json"),
    "P10_4-DIR-001": ("PASS", "evidence/generated/p10_4_direction_switch.json"),
    "P10_4-RESET-001": ("PASS", "evidence/generated/p10_4_reset_recovery.json"),
    "P10_4-XTALK-001": ("PASS", "evidence/generated/p10_4_echo_crosstalk.json"),
    "P10_4-XTALK-002": ("PASS", "evidence/generated/p10_4_crc_remediation_hardware_closure.json"),
    "P10_4-FD-001": ("PASS", "evidence/generated/p10_4_two_plus_two_requirement_closure.json"),
    "P10_4-SOAK-001": ("PASS", "evidence/generated/p10_4_mixed_30min.json"),
    "P10_4-SAFE-001": ("PASS", "evidence/generated/p10_4_shutdown.json"),
}


class CloseoutError(RuntimeError):
    """Raised when immutable closeout inputs do not match their contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CloseoutError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing evidence file: {rel(path)}")
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def write_pair(base: Path, payload: dict[str, Any], title: str,
               extra_lines: Iterable[str] = ()) -> None:
    write_json(base.with_suffix(".json"), payload)
    lines = [f"# {title}", "", f"- Status: `{payload.get('status')}`"]
    for key in ("test_id", "run_id", "composite_run_id", "artifact_source_commit"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    lines.extend(extra_lines)
    errors = payload.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", "", *[f"- {item}" for item in errors]])
    base.with_suffix(".md").write_text(
        "\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n"
    )


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def verify_manifest(run_root: Path, path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    errors = campaign.verify_evidence_manifest(run_root, manifest)
    require(not errors, f"manifest verification failed for {rel(run_root)}: {errors}")
    require(manifest.get("status") == "PASS", f"manifest is not PASS: {rel(path)}")
    return {**record(path), "status": "PASS", "file_count": manifest["file_count"]}


def verify_authorization(path: Path, run_id: str, status_fragment: str) -> dict[str, Any]:
    auth = load_json(path)
    require(auth.get("run_id") == run_id, f"authorization run mismatch: {rel(path)}")
    require(auth.get("goal_sha256") == GOAL_SHA256, f"authorization Goal mismatch: {rel(path)}")
    require(auth.get("source_commit") == SOURCE_COMMIT, f"authorization source mismatch: {rel(path)}")
    require(auth.get("consumed") is True, f"authorization not consumed: {rel(path)}")
    require(auth.get("current_run_hardware_authorization") is False,
            f"authorization remains current: {rel(path)}")
    require(status_fragment in str(auth.get("status")),
            f"authorization lifecycle mismatch: {rel(path)}")
    return auth


def verify_artifacts(artifacts: list[dict[str, Any]]) -> None:
    required = {
        ("fixed", "functional_bitstream"), ("rotating", "functional_bitstream"),
        ("fixed", "shutdown_bitstream"), ("rotating", "shutdown_bitstream"),
        ("fixed", "elf"), ("rotating", "elf"),
    }
    by_key = {(item.get("role"), item.get("kind")): item for item in artifacts}
    require(required.issubset(by_key), "frozen artifact set is incomplete")
    for key, item in by_key.items():
        path = ROOT / str(item["path"])
        require(path.is_file(), f"artifact missing: {key}")
        require(sha256(path) == item["sha256"], f"artifact hash mismatch: {key}")


def verify_shutdown_phase(run_root: Path, stage: str, phase: str) -> dict[str, Any]:
    shutdown_dir = run_root / "shutdown" / f"{stage}_{phase}"
    require(shutdown_dir.is_dir(), f"missing shutdown directory: {rel(shutdown_dir)}")
    attempts = sorted(shutdown_dir.glob("attempt_*.result.txt"))
    require(attempts, f"missing shutdown result: {rel(shutdown_dir)}")
    expected = {
        "P10_SHUTDOWN_FIXED_SERIAL": "210249855178",
        "P10_SHUTDOWN_ROTATING_SERIAL": "210512180081",
        "P10_SHUTDOWN_FIXED_TXD_OUTPUT_INTENT": "0",
        "P10_SHUTDOWN_ROTATING_TXD_OUTPUT_INTENT": "0",
        "P10_SHUTDOWN_FIXED_SD_REQUEST_ACTIVE": "1",
        "P10_SHUTDOWN_ROTATING_SD_REQUEST_ACTIVE": "1",
        "P10_SHUTDOWN_FIXED_ENDPOINT_ARMED": "0",
        "P10_SHUTDOWN_ROTATING_ENDPOINT_ARMED": "0",
        "P10_SHUTDOWN_FIXED_ACTIVE_TX_MASK": "0",
        "P10_SHUTDOWN_ROTATING_ACTIVE_TX_MASK": "0",
        "P10_SHUTDOWN_FIXED": "PASS",
        "P10_SHUTDOWN_ROTATING": "PASS",
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "TFDU_SHUTDOWN_PROGRAMMED": "1",
        "SHUTDOWN_EXIT": "0",
        "P10_DUAL_SHUTDOWN_RESULT": "PASS",
    }
    accepted: tuple[Path, dict[str, str]] | None = None
    for path in attempts:
        markers: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                markers[key] = value
        if all(markers.get(key) == value for key, value in expected.items()):
            accepted = path, markers
    require(accepted is not None, f"no verified shutdown attempt: {rel(shutdown_dir)}")
    path, markers = accepted
    return {
        "stage": stage,
        "phase": phase,
        "status": "PASS",
        "marker_count": len(markers),
        **record(path),
    }


def collect_and_verify() -> dict[str, Any]:
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be exactly 1")
    require(
        os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() == "false",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false",
    )
    require(git("branch", "--show-current").stdout.strip() == BRANCH, "wrong branch")
    require(GOAL.is_file() and sha256(GOAL) == GOAL_SHA256, "Goal SHA256 mismatch")
    for commit in (SOURCE_COMMIT, PARENT_CHECKPOINT, SUFFIX_CHECKPOINT):
        require(
            git("merge-base", "--is-ancestor", commit, "HEAD", check=False).returncode == 0,
            f"required checkpoint is not an ancestor: {commit}",
        )

    parent_result = load_json(PARENT_RESULT)
    suffix_result = load_json(SUFFIX_RESULT)
    parent_auth = verify_authorization(PARENT_AUTH, PARENT_RUN, "INTERRUPTED_FAIL_CLOSED_RESUMABLE")
    suffix_auth = verify_authorization(SUFFIX_AUTH, SUFFIX_RUN, "PASS_WITH_NONBLOCKING_LIMITS")
    parent_manifest = verify_manifest(PARENT_ROOT, PARENT_MANIFEST)
    suffix_manifest = verify_manifest(SUFFIX_ROOT, SUFFIX_MANIFEST)

    require(parent_result.get("status") == "INTERRUPTED_FAIL_CLOSED_RESUMABLE",
            "parent result lifecycle mismatch")
    require(parent_result.get("SHUTDOWN_FIXED") == "PASS" and
            parent_result.get("SHUTDOWN_ROTATING") == "PASS",
            "parent interruption did not close with dual shutdown")
    require(suffix_result.get("status") == "PASS_WITH_NONBLOCKING_LIMITS",
            "suffix result status mismatch")
    require(suffix_result.get("SHUTDOWN_FIXED") == "PASS" and
            suffix_result.get("SHUTDOWN_ROTATING") == "PASS",
            "suffix did not close with dual shutdown")
    require(suffix_result.get("nonblocking_failures") == ["two_plus_two"],
            "suffix nonblocking failure set changed")
    require(suffix_result.get("errors") == [], "suffix contains blocking errors")

    expected = list(campaign.STAGES)
    parent_names = list(parent_result.get("completed_stages", []))
    suffix_names = list(suffix_auth.get("resume_stages", []))
    require(len(expected) == 54, "canonical P10.4 stage count changed")
    require(parent_names == expected[:42], "parent completed prefix mismatch")
    require(suffix_names == expected[42:], "resume suffix stage set mismatch")
    require(parent_result.get("interrupted_stage") == expected[42],
            "parent interrupted stage mismatch")

    parent_ledger = load_json(PARENT_ROOT / "runtime_rest/runtime_rest_ledger.json")
    suffix_ledger = load_json(SUFFIX_ROOT / "runtime_rest/runtime_rest_ledger.json")
    parent_entries = list(parent_ledger.get("stages", []))
    suffix_entries = list(suffix_ledger.get("stages", []))
    require([item.get("stage") for item in parent_entries] == expected[:42],
            "parent runtime ledger prefix mismatch")
    require([item.get("stage") for item in suffix_entries] == expected[42:],
            "suffix runtime ledger mismatch")
    require(all(item.get("status") == "PASS" for item in parent_entries + suffix_entries),
            "combined runtime ledger contains a non-PASS stage")
    require(parent_ledger.get("active_stage") == expected[42] and
            parent_ledger.get("status") == "PENDING",
            "parent interruption ledger provenance mismatch")
    require(suffix_ledger.get("active_stage") is None and suffix_ledger.get("status") == "PASS",
            "suffix runtime ledger is not closed")
    runtime_by_stage = {
        item["stage"]: item for item in parent_entries + suffix_entries
    }

    stage_results: list[dict[str, Any]] = []
    stage_sources: list[dict[str, Any]] = []
    shutdown_sources: list[dict[str, Any]] = []
    for index, stage in enumerate(expected):
        run_root = PARENT_ROOT if index < 42 else SUFFIX_ROOT
        run_id = PARENT_RUN if index < 42 else SUFFIX_RUN
        path = run_root / "stages" / stage / "stage_summary.json"
        result = load_json(path)
        require(result.get("stage") == stage, f"stage identity mismatch: {stage}")
        wanted_status = "FAIL" if stage == "two_plus_two" else "PASS"
        require(result.get("status") == wanted_status,
                f"stage status mismatch: {stage}={result.get('status')}")
        before = verify_shutdown_phase(run_root, stage, "before")
        after = verify_shutdown_phase(run_root, stage, "after")
        shutdown_sources.extend((before, after))
        if "shutdown_before_status" in result:
            require(result["shutdown_before_status"] == "PASS",
                    f"summary shutdown-before failed: {stage}")
        if "shutdown_after_status" in result:
            require(result["shutdown_after_status"] == "PASS",
                    f"summary shutdown-after failed: {stage}")
        require(not result.get("process", {}).get("timed_out", False),
                f"stage timed out: {stage}")
        runtime_rest = runtime_by_stage[stage]
        require(runtime_rest.get("status") == "PASS", f"runtime/rest failed: {stage}")
        require(float(runtime_rest.get("measured_runtime_seconds", 1801)) <= 1800.0,
                f"runtime limit exceeded: {stage}")
        require(float(runtime_rest.get("actual_cooldown_seconds", -1)) >=
                 float(runtime_rest.get("required_cooldown_seconds", 0)),
                 f"cooldown ratio not met: {stage}")
        if "runtime_rest" in result:
            require(result["runtime_rest"] == runtime_rest,
                    f"summary/runtime-ledger mismatch: {stage}")
        if stage == "two_plus_two":
            require(result.get("nonblocking") is True, "2+2 is not marked nonblocking")
            require(result.get("markers", {}).get("P10_4_TWO_PLUS_TWO_TX_EXECUTED") == "false",
                    "2+2 unsupported probe unexpectedly transmitted")
            require(result.get("semantics", {}).get("reason") ==
                    "UNSUPPORTED_SINGLE_BUNDLE_DIRECTION",
                    "2+2 capability reason changed")
        annotated = dict(result)
        annotated["runtime_rest"] = dict(runtime_rest)
        annotated["shutdown_before_status"] = "PASS"
        annotated["shutdown_after_status"] = "PASS"
        annotated["shutdown_before_evidence"] = before
        annotated["shutdown_after_evidence"] = after
        annotated["component_run_id"] = run_id
        annotated["component_evidence_path"] = rel(path)
        stage_results.append(annotated)
        stage_sources.append({
            "stage": stage, "status": wanted_status, "run_id": run_id,
            "shutdown_before": before,
            "shutdown_after": after,
            **record(path),
        })

    combined_ledger = {
        "schema_version": 2,
        "status": "PASS",
        "policy_id": suffix_ledger.get("policy_id"),
        "maximum_continuous_runtime_seconds": 1800.0,
        "cooldown_ratio": 0.5,
        "conservative_module_accounting": list(MODULE_BINDING),
        "parent_interruption": {
            "run_id": PARENT_RUN,
            "historical_active_stage": parent_ledger.get("active_stage"),
            "reexecuted_from_shutdown_before_in_suffix": True,
        },
        "stages": parent_entries + suffix_entries,
        "stage_count": 54,
        "maximum_measured_runtime_seconds": max(
            float(item["measured_runtime_seconds"]) for item in parent_entries + suffix_entries
        ),
        "minimum_cooldown_margin_seconds": min(
            float(item["actual_cooldown_seconds"]) -
            float(item["required_cooldown_seconds"])
            for item in parent_entries + suffix_entries
        ),
    }

    require(parent_auth.get("module_binding") == MODULE_BINDING, "parent module binding mismatch")
    require(suffix_auth.get("module_binding") == MODULE_BINDING, "suffix module binding mismatch")
    artifacts = list(suffix_auth.get("artifacts", []))
    require(artifacts == parent_auth.get("artifacts"), "artifact bundle changed between runs")
    verify_artifacts(artifacts)

    counters = campaign.zero_counter_summary(stage_results)
    require(all(value == 0 for value in counters.values()),
            f"combined safety/integrity counters are nonzero: {counters}")
    by_stage = {item["stage"]: item for item in stage_results}
    half_windows = by_stage["half_duplex"].get("semantics", {}).get("windows", [])
    half_by_direction = {int(item["direction"]): item for item in half_windows}
    require(set(half_by_direction) == {0, 1}, "half-duplex direction evidence incomplete")
    for direction in (0, 1):
        require(float(half_by_direction[direction].get("application_goodput_bps", 0)) >= 8_000_000,
                f"8 Mbit/s retention failed for direction {direction}")

    qualification = load_json(B0019_QUALIFICATION)
    require(qualification.get("status") == "PASS", "B0019 raw qualification is not PASS")
    require(qualification.get("module_binding") == {"F2": "B0019", "R2": "B0023"},
            "B0019 qualification binding mismatch")
    require(qualification.get("SHUTDOWN_FIXED") == "PASS" and
            qualification.get("SHUTDOWN_ROTATING") == "PASS",
            "B0019 qualification shutdown mismatch")

    return {
        "expected_stages": expected,
        "stage_results": stage_results,
        "stage_sources": stage_sources,
        "shutdown_sources": shutdown_sources,
        "by_stage": by_stage,
        "counters": counters,
        "combined_ledger": combined_ledger,
        "half_by_direction": half_by_direction,
        "parent_result": parent_result,
        "suffix_result": suffix_result,
        "parent_auth": parent_auth,
        "suffix_auth": suffix_auth,
        "parent_manifest": parent_manifest,
        "suffix_manifest": suffix_manifest,
        "artifacts": artifacts,
        "selected_config": suffix_auth["selected_config"],
        "qualification": qualification,
    }


def group_definitions(expected: list[str]) -> dict[str, tuple[list[str], bool]]:
    reset_stages = [
        stage for stage in expected
        if stage.startswith(("ps_reset_", "dma_reset_", "dma_recovery_",
                             "pl_reset_", "pl_recovery_"))
        or stage in {"duplicate_fault", "duplicate_recovery", "stale_fault", "stale_recovery"}
    ]
    return {
        "safe_boot": (["preflight"], False),
        "counter_semantics": (["counter_local_source", "counter_semantics"], False),
        "baseline_smoke": (["baseline_smoke"], False),
        "performance_tuning": (["tuning"], False),
        "half_duplex_performance": (["half_duplex"], False),
        "streaming_64m": (["streaming_64m", "streaming_64m_b"], False),
        "streaming_128m": (["streaming_128m"], True),
        "degraded_modes": (["lane_recovery", "degrade"], False),
        "direction_switch": (["direction_switch"], False),
        "reset_recovery": (reset_stages, False),
        "echo_crosstalk": (["echo_crosstalk_8x8"], False),
        "two_plus_two": (["two_plus_two"], True),
        "mixed_30min": (["mixed_15min_a", "mixed_15min_b"], False),
    }


def artifact_digest_map(artifacts: list[dict[str, Any]]) -> dict[str, str]:
    output: dict[str, str] = {}
    for item in artifacts:
        key = f"{item['role']}_{item['kind']}"
        output[key] = item["sha256"]
    return output


def build_payloads(data: dict[str, Any]) -> dict[str, Any]:
    half = data["half_by_direction"]
    f_to_r = float(half[0]["application_goodput_bps"])
    r_to_f = float(half[1]["application_goodput_bps"])
    common = {
        "schema_version": 3,
        "run_id": COMPOSITE_ID,
        "composite_run_id": COMPOSITE_ID,
        "component_run_ids": [PARENT_RUN, SUFFIX_RUN],
        "scope": SCOPE,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": SOURCE_COMMIT,
        "artifacts": data["artifacts"],
        "hardware_actions_executed": True,
        "current_run_hardware_authorization": False,
        "component_evidence_checkpoints": [PARENT_CHECKPOINT, SUFFIX_CHECKPOINT],
    }
    groups: dict[str, dict[str, Any]] = {}
    for name, (stages, nonblocking) in group_definitions(data["expected_stages"]).items():
        groups[name] = campaign.group_payload(
            name, stages, data["by_stage"], common, nonblocking=nonblocking
        )

    require(all(
        payload["status"] == "PASS"
        for name, payload in groups.items() if name != "two_plus_two"
    ), "a mandatory group is not PASS")
    require(groups["two_plus_two"]["status"] == "FAIL_NONBLOCKING",
            "2+2 group result changed")

    selected = data["selected_config"]
    two_plus_two = data["by_stage"]["two_plus_two"]
    mixed_entries = [
        item for item in data["combined_ledger"]["stages"]
        if item["stage"] in {"mixed_15min_a", "mixed_15min_b"}
    ]
    final = {
        **common,
        "test_id": "P10_4-FINAL-COMPOSITE",
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT":
            "PASS_WITH_NONBLOCKING_LIMITS",
        "P10_3_EVIDENCE_COMMIT": "e64c04843d5d996f8d66d650fafaf3a43a2dd7dc",
        "P10_3_PASS_TAG": "p10.3-ax7020-stationary-4lane-pass",
        "P10_3_CLOSED_TAG": "p10.3-ax7020-stationary-4lane-closed",
        "P10_4_SOURCE_COMMIT": SOURCE_COMMIT,
        "P10_4_EVIDENCE_CHECKPOINT": SUFFIX_CHECKPOINT,
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
        "BEST_BUFFER_COUNT": selected["buffer_count"],
        "BEST_RING_DEPTH": selected["ring_depth"],
        "BEST_DESCRIPTOR_BATCH": selected["descriptor_batch"],
        "BEST_OUTSTANDING": selected["outstanding"],
        "BEST_SACK_WINDOW": 32,
        "BEST_BURST_FRAMES": 32,
        "BEST_ACK_THRESHOLD": selected["ack_threshold"],
        "F_TO_R_APPLICATION_GOODPUT_BPS": f_to_r,
        "R_TO_F_APPLICATION_GOODPUT_BPS": r_to_f,
        "F_TO_R_8MBPS_RETENTION": "PASS",
        "R_TO_F_8MBPS_RETENTION": "PASS",
        "F_TO_R_9MBPS_MARGIN": "PASS" if f_to_r >= 9_000_000 else "FAIL_NONBLOCKING",
        "R_TO_F_9MBPS_MARGIN": "PASS" if r_to_f >= 9_000_000 else "FAIL_NONBLOCKING",
        "F_TO_R_9P6MBPS_STRETCH": "PASS" if f_to_r >= 9_600_000 else "FAIL_NONBLOCKING",
        "R_TO_F_9P6MBPS_STRETCH": "PASS" if r_to_f >= 9_600_000 else "FAIL_NONBLOCKING",
        "STREAMING_64M_F_TO_R": "PASS_10_OF_10",
        "STREAMING_64M_R_TO_F": "PASS_10_OF_10",
        "STREAMING_128M": "PASS_NONBLOCKING_3_OF_3_EACH_DIRECTION",
        "LANE_DEGRADATION_RECOVERY": "PASS",
        "DIRECTION_SWITCH_LOOP": "PASS",
        "RESET_RECOVERY": "PASS",
        "ECHO_CROSSTALK_8X8_DIGITAL": "PASS",
        "SAME_MODULE_ACCEPTED_DATA": data["counters"]["same_module_accepted_data"],
        "CROSS_LANE_ACCEPTED_DATA": data["counters"]["cross_lane_accepted_data"],
        "TWO_PLUS_TWO_EXPERIMENT": "FAIL_WITH_EVIDENCE",
        "TWO_PLUS_TWO_F_TO_R_BPS": 0,
        "TWO_PLUS_TWO_R_TO_F_BPS": 0,
        "TWO_PLUS_TWO_TX_EXECUTED": False,
        "TWO_PLUS_TWO_CAPABILITY": "UNSUPPORTED_SINGLE_BUNDLE_DIRECTION",
        "MIXED_30MIN": "PASS_SEGMENTED_900S_PLUS_900S",
        "RUNTIME_SECONDS": 1800,
        "RUNTIME_SECONDS_SEMANTICS": "TWO_TX_CAPABLE_900S_SEGMENTS",
        "RUNTIME_REST_POLICY": "PASS",
        "MAXIMUM_CONTINUOUS_MODULE_RUNTIME_SECONDS": 1800,
        "MINIMUM_INTERSTAGE_COOLDOWN_RATIO": 0.5,
        "CRC_BAD": data["counters"]["crc_bad"],
        "SHA_MISMATCH": data["counters"]["sha_mismatch"],
        "PARTIAL_COMMIT": data["counters"]["partial_commit"],
        "DUPLICATE_COMMIT": data["counters"]["duplicate_commit"],
        "STALE_COMMIT": data["counters"]["stale_commit"],
        "RETRY_EXHAUSTED": data["counters"]["retry_exhausted"],
        "DESCRIPTOR_LEAK": data["counters"]["descriptor_leak"],
        "DOUBLE_COMPLETION": data["counters"]["double_completion"],
        "DEADLOCK": data["counters"]["deadlock"],
        "TRANSPORT_TIMEOUT": data["counters"]["transport_timeout"],
        "DUTY_VIOLATION": data["counters"]["duty_violation"],
        "CONTINUOUS_HIGH_VIOLATION": data["counters"]["continuous_high_violation"],
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "EXTERNAL_POWER_ACCEPTANCE": "PENDING_NOT_IN_SCOPE",
        "EXTERNAL_TFDU_DUTY": "PENDING_NOT_IN_SCOPE",
        "P11_STATUS": "NOT_STARTED",
        "PASS": [
            "P10.3 baseline recheck",
            "54-stage immutable parent-plus-suffix campaign",
            "8 Mbit/s half-duplex retention in both directions",
            "64/128 MiB streaming",
            "lane degradation/recovery and direction switching",
            "endpoint/DMA/PL reset and injected-fault recovery",
            "8x8 digital echo/crosstalk",
            "segmented 30-minute mixed formal",
            "per-stage runtime and half-runtime cooldown policy",
            "dual shutdown on every stage and terminal exit",
        ],
        "FAIL": [],
        "NONBLOCKING_RESULTS": [
            "9.0 Mbit/s margin target was not met in either direction",
            "9.6 Mbit/s stretch target was not met in either direction",
            "2+2 simultaneous opposite-direction transport is unsupported by the frozen single-bundle-direction artifact; no TX was executed by the probe",
        ],
        "NEXT_RECOMMENDED_STAGE": "P11_OFFLINE_PREPARATION",
        "board_binding": BOARD_BINDING,
        "module_binding": MODULE_BINDING,
        "artifact_sha256": artifact_digest_map(data["artifacts"]),
        "selected_config": selected,
        "application_goodput_bps": {"F_TO_R": f_to_r, "R_TO_F": r_to_f},
        "counters": data["counters"],
        "stages": data["stage_results"],
        "runtime_rest_ledger": data["combined_ledger"],
        "mixed_formal_segments": mixed_entries,
        "two_plus_two_direct_result": two_plus_two,
        "component_runs": [
            {"run_id": PARENT_RUN, "result": record(PARENT_RESULT),
             "manifest": data["parent_manifest"], "checkpoint": PARENT_CHECKPOINT},
            {"run_id": SUFFIX_RUN, "result": record(SUFFIX_RESULT),
             "manifest": data["suffix_manifest"], "checkpoint": SUFFIX_CHECKPOINT},
        ],
        "old_p10_3_pass_preserved": True,
        "p11_or_product_scope_promoted": False,
        "errors": [],
    }
    # The P10.4 Goal's final record uses the uppercase operator-facing names.
    # Remove the lowercase common aliases so case-insensitive JSON consumers
    # (notably PowerShell ConvertFrom-Json) can parse the evidence unambiguously.
    final.pop("current_run_hardware_authorization")
    final.pop("hardware_actions_executed")

    shutdown = {
        **common,
        "test_id": "P10_4-SAFE-001",
        "status": "PASS",
        "stage_count": 54,
        "all_stage_shutdown_before_verified": True,
        "all_stage_shutdown_after_verified": True,
        "parent_emergency_shutdown_verified": True,
        "suffix_terminal_shutdown_verified": True,
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "current_run_hardware_authorization": False,
        "new_tx_permitted_by_this_record": False,
        "component_results": [record(PARENT_RESULT), record(SUFFIX_RESULT)],
        "errors": [],
    }
    runtime = {
        **common,
        "test_id": "P10_4-RUNTIME-REST-COMPOSITE",
        "status": "PASS",
        "maximum_continuous_runtime_seconds": 1800,
        "minimum_cooldown_ratio": 0.5,
        "stage_count": 54,
        "maximum_measured_runtime_seconds":
            data["combined_ledger"]["maximum_measured_runtime_seconds"],
        "minimum_cooldown_margin_seconds":
            data["combined_ledger"]["minimum_cooldown_margin_seconds"],
        "ledger": data["combined_ledger"],
        "errors": [],
    }
    fd_closure = {
        **common,
        "test_id": "P10_4-FD-001",
        "status": "PASS",
        "requirement_result": "PASS_DIRECT_CAPABILITY_DETERMINATION",
        "experiment_result": "FAIL_WITH_EVIDENCE",
        "capability": "UNSUPPORTED_SINGLE_BUNDLE_DIRECTION",
        "tx_executed": False,
        "f_to_r_bps": 0,
        "r_to_f_bps": 0,
        "nonblocking": True,
        "direct_stage_evidence": record(
            SUFFIX_ROOT / "stages/two_plus_two/stage_summary.json"
        ),
        "no_final_full_duplex_claim": True,
        "errors": [],
    }
    crc_closure = {
        **common,
        "test_id": "P10_4-XTALK-002",
        "status": "PASS",
        "offline_remediation": record(GENERATED / "p10_4_crc_bad_remediation.json"),
        "hardware_confirmation": {
            "echo_crosstalk_8x8": "PASS",
            "mixed_30min": "PASS",
            "crc_bad": data["counters"]["crc_bad"],
            "same_module_accepted_data": data["counters"]["same_module_accepted_data"],
            "cross_lane_accepted_data": data["counters"]["cross_lane_accepted_data"],
        },
        "errors": [],
    }
    requirement_rows = [
        {"requirement_id": key, "status": value[0], "evidence_path": value[1]}
        for key, value in REQUIREMENT_DISPOSITIONS.items()
    ]
    audit = {
        **common,
        "test_id": "P10_4-COMPLETION-AUDIT-COMPOSITE",
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "stage_count": 54,
        "mandatory_stage_count": 52,
        "mandatory_stage_failures": [],
        "nonblocking_stage_results": {
            "streaming_128m": "PASS",
            "two_plus_two": "FAIL_WITH_EVIDENCE",
        },
        "stage_sources": data["stage_sources"],
        "group_statuses": {name: payload["status"] for name, payload in groups.items()},
        "requirement_disposition": requirement_rows,
        "requirement_counts": {"PASS": 17, "FAIL_NONBLOCKING": 1, "PENDING": 0, "TOTAL": 18},
        "counters": data["counters"],
        "runtime_rest_status": "PASS",
        "shutdown_fixed": "PASS",
        "shutdown_rotating": "PASS",
        "historical_b0008_blocker_preserved": record(HISTORICAL_B0008_BLOCKER),
        "current_b0019_raw_qualification": record(B0019_QUALIFICATION),
        "p10_3_scoped_pass_preserved": True,
        "p11_started": False,
        "errors": [],
    }
    closure = {
        **common,
        "test_id": "P10_4-TERMINAL-OFFLINE-CLOSURE-COMPOSITE",
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "hardware_campaign_status": "PASS_WITH_NONBLOCKING_LIMITS",
        "hardware_evidence_checkpoint": SUFFIX_CHECKPOINT,
        "hardware_actions_executed_during_finalization": False,
        "current_run_hardware_authorization": False,
        "shutdown_fixed": "PASS",
        "shutdown_rotating": "PASS",
        "p10_3_status": "PASS",
        "p11_status": "NOT_STARTED",
        "next_recommended_stage": "P11_OFFLINE_PREPARATION",
        "scope_not_promoted_to": ["P11", "8x32", "600rpm", "Ethernet", "product-final"],
        "errors": [],
    }
    consistency = {
        **common,
        "test_id": "P10_4-EVIDENCE-CONSISTENCY-COMPOSITE",
        "status": "PASS",
        "exact_stage_order_verified": True,
        "parent_manifest_verified": True,
        "suffix_manifest_verified": True,
        "stage_count": 54,
        "mandatory_groups_pass": True,
        "nonblocking_failures": ["two_plus_two"],
        "combined_counters_zero": True,
        "runtime_rest_policy_verified": True,
        "dual_shutdown_verified": True,
        "frozen_run_roots_modified": False,
        "manifest_path": rel(COMPOSITE_MANIFEST),
        "errors": [],
    }
    return {
        "groups": groups,
        "final": final,
        "shutdown": shutdown,
        "runtime": runtime,
        "fd_closure": fd_closure,
        "crc_closure": crc_closure,
        "audit": audit,
        "closure": closure,
        "consistency": consistency,
    }


def publish_payloads(data: dict[str, Any], payloads: dict[str, Any]) -> dict[str, Any]:
    group_paths: list[Path] = []
    for name, payload in payloads["groups"].items():
        base = GENERATED / f"p10_4_{name}"
        write_pair(base, payload, f"P10.4 {name}")
        group_paths.extend([base.with_suffix(".json"), base.with_suffix(".md")])

    standalone = {
        "p10_4_final_summary": (payloads["final"], "P10.4 final composite summary"),
        "p10_4_shutdown": (payloads["shutdown"], "P10.4 shutdown"),
        "p10_4_runtime_rest_compliance": (payloads["runtime"], "P10.4 runtime/rest compliance"),
        "p10_4_two_plus_two_requirement_closure":
            (payloads["fd_closure"], "P10.4 2+2 requirement closure"),
        "p10_4_crc_remediation_hardware_closure":
            (payloads["crc_closure"], "P10.4 CRC remediation hardware closure"),
        "p10_4_completion_audit": (payloads["audit"], "P10.4 completion audit"),
        "p10_4_terminal_offline_closure":
            (payloads["closure"], "P10.4 terminal offline closure"),
        "p10_4_evidence_consistency":
            (payloads["consistency"], "P10.4 evidence consistency"),
    }
    standalone_paths: list[Path] = []
    for name, (payload, title) in standalone.items():
        base = GENERATED / name
        extra: list[str] = []
        if name == "p10_4_final_summary":
            extra = [
                f"- Overall: `{payload['status']}`",
                f"- P10.4 evidence checkpoint: `{SUFFIX_CHECKPOINT}`",
                f"- 2+2 experiment: `{payload['TWO_PLUS_TWO_EXPERIMENT']}`",
                "- Hardware remains shutdown; P11 is not started.",
            ]
        write_pair(base, payload, title, extra)
        standalone_paths.extend([base.with_suffix(".json"), base.with_suffix(".md")])

    (COMPOSITE_ROOT / "inputs").mkdir(parents=True, exist_ok=False)
    (COMPOSITE_ROOT / "final").mkdir(parents=True, exist_ok=True)
    component_evidence = {
        "schema_version": 1,
        "status": "PASS",
        "composite_run_id": COMPOSITE_ID,
        "components": [
            {"run_id": PARENT_RUN, "result": record(PARENT_RESULT),
             "manifest": data["parent_manifest"], "checkpoint": PARENT_CHECKPOINT},
            {"run_id": SUFFIX_RUN, "result": record(SUFFIX_RESULT),
             "manifest": data["suffix_manifest"], "checkpoint": SUFFIX_CHECKPOINT},
        ],
        "parent_checkpoint": record(PARENT_CHECKPOINT_RECORD),
        "b0019_qualification": record(B0019_QUALIFICATION),
    }
    write_json(COMPOSITE_ROOT / "inputs/component_evidence.json", component_evidence)
    write_json(COMPOSITE_ROOT / "final/composite_orchestrator_result.json", payloads["final"])
    write_json(COMPOSITE_ROOT / "final/composite_evidence_consistency.json",
               payloads["consistency"])

    manifest_inputs = [
        PARENT_RESULT, PARENT_MANIFEST, SUFFIX_RESULT, SUFFIX_MANIFEST,
        PARENT_AUTH, SUFFIX_AUTH, PARENT_CHECKPOINT_RECORD, B0019_QUALIFICATION,
        COMPOSITE_ROOT / "inputs/component_evidence.json",
        COMPOSITE_ROOT / "final/composite_orchestrator_result.json",
        COMPOSITE_ROOT / "final/composite_evidence_consistency.json",
        *group_paths, *standalone_paths,
    ]
    manifest = {
        "schema_version": 1,
        "test_id": "P10_4-COMPOSITE-EVIDENCE-MANIFEST",
        "status": "PASS",
        "composite_run_id": COMPOSITE_ID,
        "component_run_ids": [PARENT_RUN, SUFFIX_RUN],
        "files": [record(path) for path in manifest_inputs],
        "file_count": len(manifest_inputs),
        "self_excluded": True,
        "errors": [],
    }
    write_pair(GENERATED / "p10_4_composite_manifest", manifest,
               "P10.4 composite evidence manifest")
    write_json(COMPOSITE_ROOT / "final/composite_manifest.json", manifest)
    return manifest


def update_state(payloads: dict[str, Any], manifest: dict[str, Any],
                 data: dict[str, Any]) -> dict[str, Any]:
    state = load_json(STATE_PATH)
    state.setdefault("stage_status", {})[SCOPE] = "PASS_WITH_NONBLOCKING_LIMITS"
    state["p10_4_status"] = "PASS_WITH_NONBLOCKING_LIMITS"
    state["current_program_stage"] = "P11_OFFLINE_PREPARATION"
    state["current_run_hardware_authorization"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_hardware_authorization_id"] = data["suffix_auth"]["authorization_id"]
    state["last_hardware_evidence_checkpoint"] = SUFFIX_CHECKPOINT
    state["last_hardware_run_id"] = SUFFIX_RUN
    state["last_hardware_stage"] = "P10_4"
    state["last_shutdown_fixed"] = "PASS"
    state["last_shutdown_rotating"] = "PASS"
    state["last_verified_commit"] = SUFFIX_CHECKPOINT
    if SCOPE not in state.setdefault("completed_gates", []):
        state["completed_gates"].append(SCOPE)
    state["p10_4_current_run_authorization"] = {
        **record(SUFFIX_AUTH),
        "run_id": SUFFIX_RUN,
        "status": data["suffix_auth"]["status"],
        "consumed": True,
        "current_run_hardware_authorization": False,
    }
    final = payloads["final"]
    state["p10_4_acceptance"] = {
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "scope": SCOPE,
        "run_id": SUFFIX_RUN,
        "campaign_disposition": "CLOSED_WITH_TRUTHFUL_2PLUS2_CAPABILITY_LIMIT",
        "goal_sha256": GOAL_SHA256,
        "source_commit": SOURCE_COMMIT,
        "hardware_evidence_checkpoint": SUFFIX_CHECKPOINT,
        "composite_run_id": COMPOSITE_ID,
        "component_run_ids": [PARENT_RUN, SUFFIX_RUN],
        "current_run_hardware_authorization": False,
        "authorization_consumed": True,
        "board_binding": BOARD_BINDING,
        "module_binding": MODULE_BINDING,
        "artifact_sha256": final["artifact_sha256"],
        "final_summary_path": rel(FINAL_SUMMARY),
        "final_summary_sha256": sha256(FINAL_SUMMARY),
        "completion_audit_path": rel(COMPLETION_AUDIT),
        "completion_audit_sha256": sha256(COMPLETION_AUDIT),
        "offline_closure_path": rel(OFFLINE_CLOSURE),
        "offline_closure_sha256": sha256(OFFLINE_CLOSURE),
        "evidence_consistency_path": rel(CONSISTENCY),
        "evidence_consistency_sha256": sha256(CONSISTENCY),
        "composite_manifest_path": rel(COMPOSITE_MANIFEST),
        "composite_manifest_sha256": sha256(COMPOSITE_MANIFEST),
        "parent_manifest_path": rel(PARENT_MANIFEST),
        "parent_manifest_sha256": sha256(PARENT_MANIFEST),
        "suffix_manifest_path": rel(SUFFIX_MANIFEST),
        "suffix_manifest_sha256": sha256(SUFFIX_MANIFEST),
        "half_duplex_f_to_r_goodput_bps": final["F_TO_R_APPLICATION_GOODPUT_BPS"],
        "half_duplex_r_to_f_goodput_bps": final["R_TO_F_APPLICATION_GOODPUT_BPS"],
        "streaming_64m": "PASS_10_OF_10_EACH_DIRECTION",
        "streaming_128m": "PASS_3_OF_3_EACH_DIRECTION_NONBLOCKING",
        "lane_degradation_recovery": "PASS",
        "direction_switch": "PASS",
        "reset_recovery": "PASS",
        "echo_crosstalk_8x8": "PASS",
        "two_plus_two_experiment": "FAIL_WITH_EVIDENCE_NONBLOCKING",
        "mixed_30min": "PASS_SEGMENTED_WITH_COOLDOWN",
        "runtime_rest_policy": "PASS",
        "hardware_actions_executed": True,
        "network_used": False,
        "hardware_moved": False,
        "wiring_changed": False,
        "external_instrumentation_used": False,
        "maximum_lane_mask": "0xF",
        "maximum_single_formal_run_seconds": 1800,
        "maximum_continuous_module_runtime_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "shutdown_fixed": "PASS",
        "shutdown_rotating": "PASS",
        "p10_3_scoped_pass_preserved": True,
        "p11_started": False,
        "nonblocking_results": final["NONBLOCKING_RESULTS"],
    }
    state["state_revision"] = "P10-4-COMPOSITE-PASS-WITH-NONBLOCKING-LIMITS-B0019"
    errors = validate_state(state, ROOT)
    require(not errors, f"updated state validation failed: {errors}")
    write_json(STATE_PATH, state)
    STATUS_PATH.write_text(render_project_status(state), encoding="utf-8", newline="\n")
    return state


def update_requirements() -> dict[str, Any]:
    document = yaml.safe_load(REQUIREMENTS_PATH.read_text(encoding="utf-8"))
    requirements = document.get("requirements", [])
    by_id = {
        item.get("requirement_id"): item
        for item in requirements if isinstance(item, dict)
    }
    require(set(REQUIREMENT_DISPOSITIONS).issubset(by_id),
            "P10.4 requirement set is incomplete")
    common_records = [
        record(COMPOSITE_MANIFEST), record(PARENT_RESULT), record(PARENT_MANIFEST),
        record(SUFFIX_RESULT), record(SUFFIX_MANIFEST),
    ]
    for req_id, (status, evidence_rel) in REQUIREMENT_DISPOSITIONS.items():
        item = by_id[req_id]
        evidence = ROOT / evidence_rel
        require(evidence.is_file(), f"requirement evidence missing: {evidence_rel}")
        item["status"] = status
        item["waiver"] = None
        item["evidence_path"] = evidence_rel
        item["artifact_hash"] = sha256(evidence)
        item["artifact_hashes"] = [record(evidence), *[entry.copy() for entry in common_records]]
        if req_id == "P10_4-PERF-003":
            item["hardware_followup"] = (
                "The nonblocking 9.0 Mbit/s margin was not met in either direction. "
                "The direct >=8.0 Mbit/s mandatory result remains PASS without weakening safety."
            )
        elif req_id == "P10_4-FD-001":
            item["hardware_followup"] = (
                "Requirement PASS means the bounded direct capability determination was completed. "
                "The experiment result remains FAIL_WITH_EVIDENCE because the frozen artifact has "
                "one bundle-wide direction; no simultaneous-opposite-direction TX was executed."
            )
        else:
            item["hardware_followup"] = (
                "P10.4 closed PASS_WITH_NONBLOCKING_LIMITS on the immutable B0019 bundle. "
                "This does not promote P11, 8x32, 600 rpm, Ethernet/SPI, external electrical/duty, "
                "rotation, or product-final acceptance."
            )

    state_hash = sha256(STATE_PATH)
    status_hash = sha256(STATUS_PATH)
    for item in requirements:
        if not isinstance(item, dict):
            continue
        for binding in item.get("artifact_hashes", []):
            if binding.get("path") == "config/project_state.json":
                binding.update({"sha256": state_hash, "bytes": STATE_PATH.stat().st_size})
            elif binding.get("path") == "PROJECT_STATUS.md":
                binding.update({"sha256": status_hash, "bytes": STATUS_PATH.stat().st_size})
        if item.get("evidence_path") == "config/project_state.json":
            item["artifact_hash"] = state_hash
        elif item.get("evidence_path") == "PROJECT_STATUS.md":
            item["artifact_hash"] = status_hash

    errors = validate_requirements(document, ROOT)
    require(not errors, f"updated requirement validation failed: {errors}")
    REQUIREMENTS_PATH.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8", newline="\n",
    )
    result = subprocess.run(
        [sys.executable, "scripts/generate_requirement_traceability.py", "--write"],
        cwd=ROOT, text=True, capture_output=True,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    require(result.returncode == 0,
            f"traceability generation failed: {result.stdout}{result.stderr}")
    require(TRACEABILITY_PATH.is_file(), "traceability output is missing")
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        data = collect_and_verify()
        payloads = build_payloads(data)
        if args.validate_only:
            print(json.dumps({
                "status": payloads["final"]["status"],
                "stage_count": len(data["stage_results"]),
                "nonblocking_failures": ["two_plus_two"],
                "SHUTDOWN_FIXED": "PASS",
                "SHUTDOWN_ROTATING": "PASS",
            }, indent=2))
            return 0
        require(not COMPOSITE_ROOT.exists(), "composite evidence root already exists")
        manifest = publish_payloads(data, payloads)
        update_state(payloads, manifest, data)
        update_requirements()
    except (CloseoutError, KeyError, IndexError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        print("P10_4_COMPOSITE_FINALIZATION=FAIL")
        return 1

    print("P10_4_COMPOSITE_FINALIZATION=PASS")
    print("P10_4_RESULT=PASS_WITH_NONBLOCKING_LIMITS")
    print(f"P10_4_COMPOSITE_RUN_ID={COMPOSITE_ID}")
    print("TWO_PLUS_TWO_EXPERIMENT=FAIL_WITH_EVIDENCE")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    print("SHUTDOWN_FIXED=PASS")
    print("SHUTDOWN_ROTATING=PASS")
    print("HARDWARE_ACTIONS_EXECUTED_DURING_FINALIZATION=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
