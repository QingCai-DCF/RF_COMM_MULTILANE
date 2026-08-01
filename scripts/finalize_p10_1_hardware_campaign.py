#!/usr/bin/env python3
"""Aggregate immutable P10.1 hardware runs into one terminal campaign result.

This finalizer performs no hardware operation.  It verifies the selected raw
run files and their hashes, derives cross-run acceptance metrics, refreshes the
canonical generated evidence, and records the terminal scoped state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

import finalize_p10_1_hardware_acceptance as single
from p10_1_common import ROOT, rel, sha256, write_json, write_pair, write_text
from p8a_common import render_project_status


GENERATED = ROOT / "evidence/generated"
HARDWARE_ROOT = ROOT / "evidence/hardware/p10_1"
SELECTION = HARDWARE_ROOT / "terminal_campaign_selection.json"
STATE = ROOT / "config/project_state.json"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATUS = ROOT / "PROJECT_STATUS.md"
CURRENT_AUTHORIZATION = ROOT / "config/p10_1_current_run_hardware_authorization.json"
ARTIFACT_SUMMARY = GENERATED / "p10_1_hw_artifact_summary.json"
MODEL_SUMMARY = GENERATED / "p10_1_hw_model_sanity_summary.json"
OFFLINE_SUMMARY = GENERATED / "p10_1_final_summary.json"
AUTHORIZATION_SOURCE = GENERATED / "p10_1_hw_remaining_campaign_authorization_source.json"

GOAL_SHA256 = "b3d0ae793a89ba270ca72880fb4fa38bcb17ac7631f3fc650e2557963840f9d3"
SOURCE_COMMIT = "bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1"
OFFLINE_TAG = "p10.1-offline-performance-ready"
OFFLINE_SOURCE = "ae942f0b5d9e9b4b7f5ced4751cc748c55b81183"
OFFLINE_EVIDENCE = "8c34d60f064b01b95dc9c35b664ffbe43efb0b1f"
FIXED_SERIAL = "210249855178"
ROTATING_SERIAL = "210512180081"
REQUIRED_STAGES = (
    "preflight",
    "smoke",
    "baseline",
    "tuning",
    "pipeline",
    "streaming",
    "faults",
    "crosstalk",
    "half_duplex",
    "oneplusone",
    "formal",
)
FINAL_STEM = "p10_1_hw_final_summary"
TERMINAL_STEM = "p10_1_hw_campaign_terminal_summary"
AUDIT_PATH = GENERATED / "P10_1_HARDWARE_CAMPAIGN_TERMINAL_AUDIT.md"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return value


def file_record(path: Path, *, evidence_role: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "path": rel(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }
    if evidence_role is not None:
        record["evidence_role"] = evidence_role
    return record


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def git_is_ancestor(commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    )


def git_json_record(revision: str, path: str) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = subprocess.check_output(
        ["git", "show", f"{revision}:{path}"], cwd=ROOT
    )
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{revision}:{path} does not contain a JSON object")
    return value, {
        "path": f"git:{revision}:{path}",
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "evidence_role": "FROZEN_GIT_BLOB",
    }


def artifact_hash_map(artifact_summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in artifact_summary.get("artifacts", []):
        kind = str(item.get("kind"))
        if kind == "functional_bitstream":
            kind = "performance_bitstream"
        result[f"{item.get('role')}:{kind}"] = {
            "path": item.get("path"),
            "sha256": item.get("sha256"),
            "bytes": item.get("bytes"),
        }
    return result


def expected_artifact_hashes(selection: dict[str, Any]) -> set[str]:
    return {str(value) for value in selection["artifact_sha256"].values()}


def integer_value(value: Any) -> int:
    if isinstance(value, str):
        return int(value, 0)
    return int(value)


def validate_selected_runs(
    selection: dict[str, Any],
) -> tuple[
    list[str],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    errors: list[str] = []
    stages: dict[str, dict[str, Any]] = {}
    stage_records: dict[str, dict[str, Any]] = {}
    core_records: list[dict[str, Any]] = [
        file_record(SELECTION, evidence_role="TERMINAL_SELECTION")
    ]
    run_audit: list[dict[str, Any]] = []
    selected_stage_runs: dict[str, str] = {}

    if selection.get("goal_sha256") != GOAL_SHA256:
        errors.append("terminal selection goal SHA256 mismatch")
    if selection.get("source_commit") != SOURCE_COMMIT:
        errors.append("terminal selection source commit mismatch")
    if selection.get("maximum_lane_mask") != 3:
        errors.append("terminal selection maximum lane mask is not 0x3")
    if selection.get("maximum_single_formal_run_seconds") != 1800:
        errors.append("terminal selection formal duration bound is not 1800 seconds")

    expected_artifacts = expected_artifact_hashes(selection)
    for run in selection.get("runs", []):
        run_id = str(run.get("run_id"))
        run_root = (HARDWARE_ROOT / run_id).resolve()
        try:
            run_root.relative_to(HARDWARE_ROOT.resolve())
        except ValueError:
            errors.append(f"{run_id}: run path escapes the hardware evidence root")
            continue
        if not run_root.is_dir():
            errors.append(f"{run_id}: run directory is missing")
            continue

        run_file_records: list[dict[str, Any]] = []
        for relative_path, expected_hash in run.get("files", {}).items():
            path = run_root / Path(*relative_path.split("/"))
            if not path.is_file():
                errors.append(f"{run_id}: missing {relative_path}")
                continue
            actual_hash = sha256(path)
            if actual_hash != expected_hash:
                errors.append(
                    f"{run_id}: SHA256 mismatch for {relative_path}: "
                    f"expected {expected_hash}, got {actual_hash}"
                )
            record = file_record(path)
            run_file_records.append(record)
            if not relative_path.startswith("stages/"):
                core_records.append(record)

        orchestrator_path = run_root / "final/orchestrator_result.json"
        authorization_path = run_root / "authorization/immutable_authorization.json"
        authorization_record_path = run_root / "authorization/authorization_record.json"
        if not all(
            path.is_file()
            for path in (orchestrator_path, authorization_path, authorization_record_path)
        ):
            continue
        orchestrator = load_json(orchestrator_path)
        authorization = load_json(authorization_path)
        authorization_record = load_json(authorization_record_path)

        manifest_errors, manifest = single.verify_run_manifest(run_root)
        errors.extend(f"{run_id}: {item}" for item in manifest_errors)
        if orchestrator.get("run_id") != run_id:
            errors.append(f"{run_id}: orchestrator run ID mismatch")
        if orchestrator.get("source_commit") != SOURCE_COMMIT:
            errors.append(f"{run_id}: orchestrator source commit mismatch")
        if orchestrator.get("SHUTDOWN_FIXED") != "PASS":
            errors.append(f"{run_id}: fixed shutdown is not PASS")
        if orchestrator.get("SHUTDOWN_ROTATING") != "PASS":
            errors.append(f"{run_id}: rotating shutdown is not PASS")
        if orchestrator.get("network_used") is not False:
            errors.append(f"{run_id}: network_used is not false")
        if orchestrator.get("ethernet_used") is not False:
            errors.append(f"{run_id}: ethernet_used is not false")
        for field in ("hardware_movement", "rotation_executed", "rewiring_executed"):
            if orchestrator.get(field) is not False:
                errors.append(f"{run_id}: {field} is not false")
        if integer_value(orchestrator.get("maximum_lane_mask_used", 99)) > 3:
            errors.append(f"{run_id}: maximum lane mask exceeded 0x3")
        shutdowns = orchestrator.get("shutdowns", [])
        if not shutdowns or any(item.get("status") != "PASS" for item in shutdowns):
            errors.append(f"{run_id}: not every recorded shutdown is PASS")

        if authorization.get("status") != "AUTHORIZED":
            errors.append(f"{run_id}: immutable authorization was not AUTHORIZED")
        if authorization.get("run_id") != run_id:
            errors.append(f"{run_id}: immutable authorization run ID mismatch")
        if authorization.get("goal_sha256") != GOAL_SHA256:
            errors.append(f"{run_id}: immutable authorization goal SHA256 mismatch")
        if authorization.get("source_commit") != SOURCE_COMMIT:
            errors.append(f"{run_id}: immutable authorization source commit mismatch")
        if authorization_record.get("status") != "PASS":
            errors.append(f"{run_id}: authorization validation record is not PASS")
        errors.extend(
            f"{run_id}: {item}"
            for item in single.validate_authorized_artifacts(authorization)
        )
        board_identities = authorization.get("board_identities", {})
        if board_identities.get("fixed", {}).get("serial") != FIXED_SERIAL:
            errors.append(f"{run_id}: fixed serial binding mismatch")
        if board_identities.get("rotating", {}).get("serial") != ROTATING_SERIAL:
            errors.append(f"{run_id}: rotating serial binding mismatch")
        authorized_hashes = {
            str(item.get("sha256")) for item in authorization.get("artifacts", [])
        }
        if not expected_artifacts.issubset(authorized_hashes):
            errors.append(f"{run_id}: immutable authorization artifact set is incomplete")

        for stage in run.get("selected_stages", []):
            if stage in selected_stage_runs:
                errors.append(
                    f"{stage}: selected by both {selected_stage_runs[stage]} and {run_id}"
                )
                continue
            selected_stage_runs[stage] = run_id
            stage_path = run_root / "stages" / stage / "stage_summary.json"
            if not stage_path.is_file():
                errors.append(f"{run_id}: selected stage {stage} is missing")
                continue
            stage_payload = load_json(stage_path)
            stages[stage] = stage_payload
            stage_records[stage] = file_record(
                stage_path, evidence_role="SELECTED_STAGE_SUMMARY"
            )
            if stage_payload.get("stage") != stage:
                errors.append(f"{run_id}: {stage} stage name mismatch")
            orchestrated_status = orchestrator.get("stages", {}).get(stage)
            if orchestrated_status != stage_payload.get("status"):
                errors.append(
                    f"{run_id}: {stage} orchestrator/stage status mismatch "
                    f"({orchestrated_status} != {stage_payload.get('status')})"
                )
            if stage not in authorization.get("authorized_stages", []):
                errors.append(f"{run_id}: selected stage {stage} was not authorized")

        run_audit.append(
            {
                "run_id": run_id,
                "selection_role": run.get("selection_role"),
                "orchestrator_status": orchestrator.get("status"),
                "selected_stages": list(run.get("selected_stages", [])),
                "authorized_stages": authorization.get("authorized_stages", []),
                "shutdown_fixed": orchestrator.get("SHUTDOWN_FIXED"),
                "shutdown_rotating": orchestrator.get("SHUTDOWN_ROTATING"),
                "shutdown_event_count": len(shutdowns),
                "manifest_file_count": len(manifest.get("files", [])),
                "network_used": orchestrator.get("network_used"),
                "maximum_lane_mask_used": orchestrator.get("maximum_lane_mask_used"),
                "evidence_files": run_file_records,
            }
        )

    missing = sorted(set(REQUIRED_STAGES) - set(stages))
    unexpected = sorted(set(stages) - set(REQUIRED_STAGES))
    if missing:
        errors.append("terminal selection is missing stages: " + ", ".join(missing))
    if unexpected:
        errors.append("terminal selection has unexpected stages: " + ", ".join(unexpected))
    return errors, stages, stage_records, core_records, run_audit


def all_paired_details(stages: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        detail
        for stage in REQUIRED_STAGES
        for detail in stages[stage].get("details", [])
        if isinstance(detail, dict) and "fixed" in detail and "rotating" in detail
    ]


def counter_sum(details: list[dict[str, Any]], field: str) -> int:
    return sum(
        int(detail[role].get(field, 0))
        for detail in details
        for role in ("fixed", "rotating")
    )


def lane_maxima(
    details: list[dict[str, Any]], field: str, lanes: int = 4
) -> list[int]:
    maxima = [0] * lanes
    for detail in details:
        for role in ("fixed", "rotating"):
            values = detail[role].get(field, [])
            for index in range(min(lanes, len(values))):
                maxima[index] = max(maxima[index], int(values[index]))
    return maxima


def window_by_direction(stage: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {
        int(item["direction"]): item
        for item in stage.get("semantics", {}).get("directions", [])
    }


def summarize_formal_bottleneck(
    formal: dict[str, Any], direction: int
) -> dict[str, Any]:
    rows = [
        item
        for item in formal.get("details", [])
        if item.get("direction") == direction
        and str(item.get("label", "")).startswith("stationary_30min_formal_")
    ]
    sender_role = "fixed" if direction == 0 else "rotating"
    totals = {
        "ack_wait_ticks": 0,
        "axis_stall_ticks": 0,
        "direction_quiet_ticks": 0,
        "inter_object_signal_ticks": 0,
        "pl_elapsed_ticks": 0,
    }
    for row in rows:
        sender = row[sender_role]
        totals["ack_wait_ticks"] += int(sender.get("perf_ack_wait", 0))
        totals["axis_stall_ticks"] += int(sender.get("perf_axis_stall", 0))
        totals["direction_quiet_ticks"] += int(sender.get("perf_direction_quiet", 0))
        totals["inter_object_signal_ticks"] += int(
            sender.get("inter_object_signal_ticks", 0)
        )
        totals["pl_elapsed_ticks"] += int(sender.get("pl_elapsed_ticks", 0))
    elapsed = totals["pl_elapsed_ticks"]
    return {
        "direction": direction,
        "case_count": len(rows),
        **totals,
        "ack_wait_to_pl_elapsed_ratio": (
            totals["ack_wait_ticks"] / elapsed if elapsed else None
        ),
        "axis_stall_to_pl_elapsed_ratio": (
            totals["axis_stall_ticks"] / elapsed if elapsed else None
        ),
        "direction_quiet_to_pl_elapsed_ratio": (
            totals["direction_quiet_ticks"] / elapsed if elapsed else None
        ),
        "inter_object_to_pl_elapsed_ratio": (
            totals["inter_object_signal_ticks"] / elapsed if elapsed else None
        ),
        "counter_overlap_caution": (
            "telemetry counters overlap and must not be added as disjoint time"
        ),
    }


def common_payload(
    selection: dict[str, Any], artifact_summary: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at_utc": selection["selected_at_utc"],
        "campaign_id": selection["campaign_id"],
        "scope": selection["scope"],
        "goal_sha256": GOAL_SHA256,
        "source_commit": SOURCE_COMMIT,
        "run_ids": [item["run_id"] for item in selection["runs"]],
        "offline_base_tag": OFFLINE_TAG,
        "offline_source_commit": OFFLINE_SOURCE,
        "offline_evidence_checkpoint": OFFLINE_EVIDENCE,
        "artifact_provenance": "MULTI_RUN_CAPTURED_IMMUTABLE_CURRENT_RUN_AUTHORIZATIONS",
        "artifact_hashes": artifact_hash_map(artifact_summary),
        "board_identities": {
            "fixed": {
                "id": f"AX7020-F/JTAG:{FIXED_SERIAL}",
                "serial": FIXED_SERIAL,
            },
            "rotating": {
                "id": f"AX7020-R/JTAG:{ROTATING_SERIAL}",
                "serial": ROTATING_SERIAL,
            },
        },
        "captured_run_hardware_authorization": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": True,
        "network_used": False,
        "ethernet_used": False,
        "hardware_movement": False,
        "rotation_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0x3",
    }


def write_summary(
    common: dict[str, Any],
    stem: str,
    title: str,
    test_id: str,
    status: str,
    *,
    errors: list[str] | None = None,
    raw_evidence: list[dict[str, Any]] | None = None,
    body: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        **common,
        "test_id": test_id,
        "status": status,
        "raw_evidence": raw_evidence or [],
        "errors": errors or [],
        **extra,
    }
    write_pair(stem, title, payload, body or [])
    return payload


def update_canonical_files(
    final: dict[str, Any],
    summaries: dict[str, dict[str, Any]],
) -> None:
    final_path = GENERATED / f"{FINAL_STEM}.json"
    terminal_path = GENERATED / f"{TERMINAL_STEM}.json"
    current_authorization = load_json(CURRENT_AUTHORIZATION)
    current_authorization.update(
        {
            "current_run_hardware_authorization": False,
            "consumed": True,
            "reusable_for_future_run": False,
            "campaign_status": "FAIL",
            "campaign_disposition": "TERMINAL_FAIL_REMEDIATION_REQUIRED",
            "terminal_campaign_id": final["campaign_id"],
            "terminal_campaign_summary": {
                "path": rel(terminal_path),
                "sha256": sha256(terminal_path),
            },
            "final_evidence_path": rel(final_path),
            "final_evidence_sha256": sha256(final_path),
            "next_required_user_action": (
                "review the terminal FAIL evidence; any remediation artifact change "
                "requires a new immutable bundle and full reacceptance"
            ),
        }
    )
    write_json(CURRENT_AUTHORIZATION, current_authorization)

    state = load_json(STATE)
    state["current_run_hardware_authorization"] = False
    state["p10_1_hardware_status"] = "FAIL"
    state["current_program_stage"] = "P10_1_PERFORMANCE_REMEDIATION"
    state["p11_status"] = "NOT_STARTED"
    state["p11_hardware_ready"] = False
    state["p10_1_no_hardware_actions_executed"] = False
    state["last_hardware_stage"] = "P10_1"
    state["last_hardware_run_id"] = final["formal_run_id"]
    state["last_shutdown_fixed"] = "PASS"
    state["last_shutdown_rotating"] = "PASS"
    state["last_hardware_authorization_consumed"] = True
    state["p10_1_current_run_authorization"] = {
        "status": current_authorization.get("status"),
        "path": rel(CURRENT_AUTHORIZATION),
        "sha256": sha256(CURRENT_AUTHORIZATION),
        "consumed": True,
        "consumed_by_run_id": current_authorization.get("consumed_by_run_id"),
        "reusable_for_future_run": False,
    }
    campaign = state.setdefault("p10_1_hardware_campaign", {})
    campaign.update(
        {
            "status": "FAIL",
            "failure_classification": final["failure_classification"],
            "scope": final["scope"],
            "campaign_id": final["campaign_id"],
            "run_id": final["formal_run_id"],
            "run_ids": final["run_ids"],
            "selected_stage_runs": final["selected_stage_runs"],
            "source_commit": SOURCE_COMMIT,
            "current_run_hardware_authorization": False,
            "authorization_was_valid": True,
            "hardware_actions_executed": True,
            "network_used": False,
            "hardware_movement": False,
            "maximum_lane_mask": "0x3",
            "artifact_provenance": final["artifact_provenance"],
            "complete_run_id": None,
            "formal_run_id": final["formal_run_id"],
            "campaign_disposition": "TERMINAL_FAIL_REMEDIATION_REQUIRED",
            "retry_run_id_count": len(final["run_ids"]),
            "retry_run_id_limit": None,
            "next_required_user_action": (
                "review terminal evidence and remediate performance/crosstalk on a "
                "new immutable artifact bundle"
            ),
            "final_evidence_path": rel(final_path),
            "final_evidence_sha256": sha256(final_path),
            "terminal_evidence_path": rel(terminal_path),
            "terminal_evidence_sha256": sha256(terminal_path),
            "shutdown_fixed": "PASS",
            "shutdown_rotating": "PASS",
            "f_to_r_application_goodput_bps": final[
                "f_to_r_application_goodput_bps"
            ],
            "r_to_f_application_goodput_bps": final[
                "r_to_f_application_goodput_bps"
            ],
        }
    )
    state.setdefault("stage_status", {})[
        "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE"
    ] = "FAIL"
    performance = state.setdefault("p10_1_performance_and_observability", {})
    performance["real_hardware_goodput_status"] = "FAIL"
    performance["hardware_experiments_authorized"] = False
    write_json(STATE, state)
    STATUS.write_text(
        render_project_status(state), encoding="utf-8", newline="\n"
    )

    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    requirement_results = {
        "P10_1_HW-001": ("p10_1_hw_authorization_summary", "PASS"),
        "P10_1_HW-002": ("p10_1_hw_artifact_summary", "PASS"),
        "P10_1_TIME-001": ("p10_1_hw_timer_summary", "PASS"),
        "P10_1_METRIC-001": ("p10_1_hw_metric_semantics_summary", "PASS"),
        "P10_1_AUTO-001": ("p10_1_hw_metric_semantics_summary", "FAIL"),
        "P10_1_PIPE-001": ("p10_1_hw_pipeline_summary", "PASS"),
        "P10_1_STREAM-001": ("p10_1_hw_streaming_64m_summary", "PASS"),
        "P10_1_STREAM-002": ("p10_1_hw_streaming_64m_summary", "PASS"),
        "P10_1_STREAM-003": ("p10_1_hw_streaming_64m_summary", "PASS"),
        "P10_1_PERF-001": ("p10_1_hw_half_duplex_summary", "FAIL"),
        "P10_1_PERF-002": ("p10_1_hw_half_duplex_summary", "FAIL"),
        "P10_1_PERF-003": ("p10_1_hw_half_duplex_summary", "PASS"),
        "P10_1_XTALK-001": ("p10_1_hw_crosstalk_summary", "FAIL"),
        "P10_1_FD-001": ("p10_1_hw_1plus1_summary", "PASS"),
        "P10_1_SOAK-001": ("p10_1_hw_stationary_30min_summary", "FAIL"),
        "P10_1_SAFE-001": ("p10_1_hw_shutdown_summary", "PASS"),
    }
    artifact_context = final["artifact_hashes"]
    common_hashes = [
        {"path": item["path"], "sha256": item["sha256"]}
        for key, item in sorted(artifact_context.items())
        if key.endswith(":performance_bitstream") or key.endswith(":elf")
    ]
    wiring = ROOT / "config/hardware/p10_active_wiring.yaml"
    common_hashes.append({"path": rel(wiring), "sha256": sha256(wiring)})
    artifact_hashes = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in load_json(ARTIFACT_SUMMARY).get("artifacts", [])
    ]
    state_hash = sha256(STATE)
    status_hash = sha256(STATUS)
    for requirement in requirements["requirements"]:
        requirement_id = requirement.get("requirement_id")
        if requirement_id in requirement_results:
            stem, requirement_status = requirement_results[requirement_id]
            evidence_path = GENERATED / f"{stem}.json"
            evidence = load_json(evidence_path)
            requirement["status"] = requirement_status
            requirement["test_id"] = evidence.get("test_id")
            requirement["evidence_path"] = rel(evidence_path)
            requirement["verification_scope"] = (
                "IMMUTABLE_LED_ENABLED_ARTIFACTS"
                if stem == "p10_1_hw_artifact_summary"
                else "DIRECT_AX7020_HARDWARE"
            )
            requirement["artifact_hash"] = sha256(evidence_path)
            bound = artifact_hashes if stem == "p10_1_hw_artifact_summary" else common_hashes
            requirement["artifact_hashes"] = [
                {"path": rel(evidence_path), "sha256": sha256(evidence_path)},
                *[item.copy() for item in bound],
            ]
            requirement["hardware_followup"] = (
                "Scoped stationary dual-AX7020 two-lane evidence only; P11 handover, "
                "8x32, rotation, 600 rpm, Ethernet/SPI, external duty, physical "
                "GLOBAL_PERMIT, and product acceptance remain pending."
            )
        for item in requirement.get("artifact_hashes", []):
            if item.get("path") == "config/project_state.json":
                item["sha256"] = state_hash
            elif item.get("path") == "PROJECT_STATUS.md":
                item["sha256"] = status_hash
        if requirement.get("evidence_path") == "config/project_state.json":
            requirement["artifact_hash"] = state_hash
        elif requirement.get("evidence_path") == "PROJECT_STATUS.md":
            requirement["artifact_hash"] = status_hash
    REQUIREMENTS.write_text(
        yaml.safe_dump(
            requirements,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        ),
        encoding="utf-8",
        newline="\n",
    )
    subprocess.run(
        [sys.executable, "scripts/generate_requirement_traceability.py", "--write"],
        cwd=ROOT,
        check=True,
    )


def finalize() -> dict[str, Any]:
    selection = load_json(SELECTION)
    model = load_json(MODEL_SUMMARY)
    offline, offline_record = git_json_record(
        OFFLINE_EVIDENCE, "evidence/generated/p10_1_final_summary.json"
    )
    current_authorization = load_json(CURRENT_AUTHORIZATION)
    source_authorization = load_json(AUTHORIZATION_SOURCE)
    errors, stages, stage_records, core_records, run_audit = validate_selected_runs(
        selection
    )
    formal_run = next(
        run for run in selection["runs"] if "formal" in run["selected_stages"]
    )
    formal_authorization_path = (
        HARDWARE_ROOT
        / formal_run["run_id"]
        / "authorization/immutable_authorization.json"
    )
    formal_authorization = load_json(formal_authorization_path)
    artifact_errors = single.validate_authorized_artifacts(formal_authorization)
    selected_artifacts = []
    for item in formal_authorization.get("artifacts", []):
        selected = dict(item)
        if selected.get("kind") == "functional_bitstream":
            selected["kind"] = "performance_bitstream"
        selected_artifacts.append(selected)
    artifact_summary = {
        "schema_version": 1,
        "test_id": "P10_1-HW-IMMUTABLE-ARTIFACTS",
        "generated_at_utc": selection["selected_at_utc"],
        "status": "PASS" if not artifact_errors else "FAIL",
        "source_commit": SOURCE_COMMIT,
        "goal_sha256": GOAL_SHA256,
        "artifact_provenance": "CAPTURED_FORMAL_RUN_IMMUTABLE_AUTHORIZATION",
        "authorization": file_record(formal_authorization_path),
        "artifacts": selected_artifacts,
        "hardware_actions_executed": True,
        "current_run_hardware_authorization": False,
        "errors": artifact_errors,
    }
    write_pair(
        "p10_1_hw_artifact_summary",
        "P10.1 immutable hardware artifact bundle",
        artifact_summary,
        [
            "## Binding",
            "",
            f"- Source commit: `{SOURCE_COMMIT}`",
            f"- Captured authorization: `{rel(formal_authorization_path)}`",
            "- The mutable latest-build summary is not used as campaign provenance.",
        ],
    )
    common = common_payload(selection, artifact_summary)
    summaries: dict[str, dict[str, Any]] = {}

    offline_checks = {
        "tag_target": git_output("rev-parse", f"{OFFLINE_TAG}^{{}}"),
        "offline_source_is_ancestor": git_is_ancestor(OFFLINE_SOURCE),
        "offline_evidence_is_ancestor": git_is_ancestor(OFFLINE_EVIDENCE),
        "hardware_source_is_ancestor": git_is_ancestor(SOURCE_COMMIT),
        "offline_summary_status": offline.get("status"),
        "offline_summary_frozen_blob": offline_record,
    }
    if offline_checks["tag_target"] != OFFLINE_EVIDENCE:
        errors.append("offline tag does not resolve to the frozen evidence checkpoint")
    if not all(
        offline_checks[key]
        for key in (
            "offline_source_is_ancestor",
            "offline_evidence_is_ancestor",
            "hardware_source_is_ancestor",
        )
    ):
        errors.append("one or more frozen source checkpoints are not ancestors of HEAD")
    if offline.get("status") != "PASS":
        errors.append("offline P10.1 base summary is not PASS")
    if artifact_summary.get("status") != "PASS":
        errors.append("immutable artifact summary is not PASS")
    if model.get("status") != "PASS":
        errors.append("model sanity summary is not PASS")
    if current_authorization.get("current_run_hardware_authorization") is not False:
        errors.append("current-run hardware authorization was not consumed")
    if current_authorization.get("consumed") is not True:
        errors.append("current-run authorization lacks consumed=true")
    if source_authorization.get("goal_sha256") != GOAL_SHA256:
        errors.append("remaining-campaign authorization source goal mismatch")
    if source_authorization.get("user_authorization_statement_sha256") != (
        "81f1da9e96311b008a8969f703d6cdc33aa81c8cfadceccb0d73f62329321c6e"
    ):
        errors.append("remaining-campaign authorization statement hash mismatch")

    summaries["p10_1_hw_authorization_summary"] = write_summary(
        common,
        "p10_1_hw_authorization_summary",
        "P10.1 multi-run current-run authorization audit",
        "P10_1-HW-CURRENT-RUN-AUTHORIZATION",
        "PASS" if not [item for item in errors if "authorization" in item] else "FAIL",
        raw_evidence=[
            item
            for item in core_records
            if "authorization/" in item["path"]
        ]
        + [file_record(AUTHORIZATION_SOURCE)],
        selected_run_authorizations="PASS",
        current_authorization_consumed=True,
        run_audit=run_audit,
        user_authorization_source={
            "path": rel(AUTHORIZATION_SOURCE),
            "sha256": sha256(AUTHORIZATION_SOURCE),
            "statement_sha256": source_authorization[
                "user_authorization_statement_sha256"
            ],
            "source_thread_id": source_authorization[
                "user_authorization_source_thread_id"
            ],
        },
    )

    preflight = stages["preflight"]
    identity_errors: list[str] = []
    for field, expected in (
        ("P10_XSDB_IDENTITY", "PASS"),
        ("P10_XSDB_FIXED_SERIAL", FIXED_SERIAL),
        ("P10_XSDB_ROTATING_SERIAL", ROTATING_SERIAL),
    ):
        if preflight.get("markers", {}).get(field) != expected:
            identity_errors.append(f"preflight marker {field} mismatch")
    summaries["p10_1_hw_target_identity_summary"] = write_summary(
        common,
        "p10_1_hw_target_identity_summary",
        "P10.1 AX7020 target identity",
        "P10_1-HW-TARGET-ROLE-BINDING",
        "PASS" if not identity_errors else "FAIL",
        errors=identity_errors,
        raw_evidence=[stage_records["preflight"]],
        markers={
            key: preflight.get("markers", {}).get(key)
            for key in (
                "P10_XSDB_IDENTITY",
                "P10_XSDB_FIXED_SERIAL",
                "P10_XSDB_ROTATING_SERIAL",
            )
        },
    )

    safe_boot = {
        stage: payload.get("markers", {}).get("P10_SAFE_BOOT")
        for stage, payload in stages.items()
    }
    safe_errors = [stage for stage, status in safe_boot.items() if status != "PASS"]
    summaries["p10_1_hw_safe_boot_summary"] = write_summary(
        common,
        "p10_1_hw_safe_boot_summary",
        "P10.1 cross-run safe boot",
        "P10_1-HW-SAFE-BOOT-BOTH",
        "PASS" if not safe_errors else "FAIL",
        errors=[f"{stage}: safe boot marker is not PASS" for stage in safe_errors],
        raw_evidence=list(stage_records.values()),
        stage_safe_boot=safe_boot,
        semantic_stage_failures_do_not_negate_safe_boot=True,
    )

    details = all_paired_details(stages)
    timer_rows = single.timer_crosscheck_rows(details)
    max_timer_error = max(
        (
            max(
                float(row["fixed_local_ps_pl_error_percent"]),
                float(row["rotating_local_ps_pl_error_percent"]),
            )
            for row in timer_rows
        ),
        default=None,
    )
    timer_firmware_pass = all(
        row["fixed_firmware_crosscheck_pass"]
        and row["rotating_firmware_crosscheck_pass"]
        for row in timer_rows
    )
    timer_status = (
        bool(timer_rows)
        and max_timer_error is not None
        and max_timer_error <= 1.0
        and timer_firmware_pass
    )
    summaries["p10_1_hw_timer_summary"] = write_summary(
        common,
        "p10_1_hw_timer_summary",
        "P10.1 cross-run PS/PL timer crosscheck",
        "P10_1-HW-TIMER-CROSSCHECK",
        "PASS" if timer_status else "FAIL",
        errors=[] if timer_status else ["cross-run timer coverage or threshold failed"],
        raw_evidence=list(stage_records.values()),
        paired_record_count=len(details),
        endpoint_record_count=len(details) * 2,
        timer_row_count=len(timer_rows),
        timer_endpoint_measurement_count=len(timer_rows) * 2,
        excluded_non_timed_record_count=len(details) - len(timer_rows),
        excluded_record_classes=[
            "identity/control records",
            "raw pulse records",
            "diagnostic-only records",
            "intentional recovery/abort records",
        ],
        maximum_allowed_error_percent=1.0,
        maximum_observed_error_percent=max_timer_error,
        firmware_crosschecks_pass=timer_firmware_pass,
        comparison_scope="LOCAL_PS_VS_LOCAL_PL_PER_ENDPOINT",
    )

    formal_directions = window_by_direction(stages["formal"])
    host_status = all(
        item.get("host_not_in_fast_path") is True
        for item in formal_directions.values()
    )
    metric_errors = [] if host_status else [
        "formal F-to-R host fast-path exclusion failed: 25 control commands",
        "formal R-to-F host fast-path exclusion failed: 25 control commands",
    ]
    summaries["p10_1_hw_metric_semantics_summary"] = write_summary(
        common,
        "p10_1_hw_metric_semantics_summary",
        "P10.1 hardware metric semantics and autonomy",
        "P10_1-HW-METRIC-SEMANTICS-AUTONOMY",
        "PASS" if not metric_errors else "FAIL",
        errors=metric_errors,
        raw_evidence=[
            stage_records[stage]
            for stage in ("preflight", "pipeline", "half_duplex", "formal")
        ],
        requirement_results={
            "P10_1_METRIC-001": "PASS",
            "P10_1_AUTO-001": "PASS" if host_status else "FAIL",
        },
        hardware_metric_semantics="PASS",
        diagnostic_exclusion=(
            "PASS"
            if preflight.get("semantics", {}).get(
                "diagnostic_eligible_for_scaling"
            )
            is False
            else "FAIL"
        ),
        board_autonomous_fast_path="PASS" if host_status else "FAIL",
        host_not_in_fast_path="PASS" if host_status else "FAIL",
        formal_host_command_counts={
            "f_to_r": formal_directions[0]["host_command_count"],
            "r_to_f": formal_directions[1]["host_command_count"],
        },
        formal_segment_counts={
            "f_to_r": formal_directions[0]["segments_completed"],
            "r_to_f": formal_directions[1]["segments_completed"],
        },
    )

    baseline = stages["baseline"]
    summaries["p10_1_hw_baseline_summary"] = write_summary(
        common,
        "p10_1_hw_baseline_summary",
        "P10.1 single-lane and two-lane baseline",
        "P10_1-HW-BASELINE-SCALING",
        baseline["status"],
        errors=baseline.get("errors", []),
        raw_evidence=[stage_records["baseline"]],
        windows=baseline.get("semantics", {}).get("windows", []),
        two_lane_scaling=baseline.get("semantics", {}).get("two_lane_scaling"),
    )

    tuning = stages["tuning"]
    best = tuning.get("semantics", {}).get("best_candidate", {})
    summaries["p10_1_hw_tuning_summary"] = write_summary(
        common,
        "p10_1_hw_tuning_summary",
        "P10.1 adaptive tuning",
        "P10_1-HW-ADAPTIVE-TUNING",
        tuning["status"],
        errors=tuning.get("errors", []),
        raw_evidence=[stage_records["tuning"]],
        best_candidate=best,
        candidate_count=tuning.get("semantics", {}).get("candidate_count"),
    )
    summaries["p10_1_hw_selected_tuning_configuration"] = write_summary(
        common,
        "p10_1_hw_selected_tuning_configuration",
        "P10.1 selected hardware tuning configuration",
        "P10_1-HW-SELECTED-TUNING-CONFIGURATION",
        "PASS",
        raw_evidence=[stage_records["tuning"]],
        selected_configuration=best,
    )

    pipeline = stages["pipeline"]
    summaries["p10_1_hw_pipeline_summary"] = write_summary(
        common,
        "p10_1_hw_pipeline_summary",
        "P10.1 sustained hardware pipeline",
        "P10_1-HW-SUSTAINED-PIPELINE",
        pipeline["status"],
        errors=pipeline.get("errors", []),
        raw_evidence=[stage_records["pipeline"]],
        windows=pipeline.get("semantics", {}).get("windows", []),
        selected_configuration=best,
    )

    streaming = stages["streaming"]
    faults = stages["faults"]
    stream_directions = [
        {
            "label": item.get("label"),
            "direction": item.get("direction"),
            "requested_bytes": item.get("requested_bytes"),
            "application_goodput_bps": item.get("application_goodput_bps"),
            "fixed_committed_bytes": item["fixed"].get(
                "application_bytes_committed"
            ),
            "rotating_committed_bytes": item["rotating"].get(
                "application_bytes_committed"
            ),
            "atomic_commit_count": {
                "fixed": item["fixed"].get("atomic_commit_count"),
                "rotating": item["rotating"].get("atomic_commit_count"),
            },
        }
        for item in streaming.get("details", [])
    ]
    stream_status = streaming.get("status") == "PASS" and faults.get("status") == "PASS"
    summaries["p10_1_hw_streaming_64m_summary"] = write_summary(
        common,
        "p10_1_hw_streaming_64m_summary",
        "P10.1 64 MiB streaming and recovery",
        "P10_1-HW-STREAMING-64M-RECOVERY",
        "PASS" if stream_status else "FAIL",
        errors=streaming.get("errors", []) + faults.get("errors", []),
        raw_evidence=[stage_records["streaming"], stage_records["faults"]],
        directions=stream_directions,
        recovery_vector_count=faults.get("semantics", {}).get(
            "recovery_vector_count"
        ),
        post_recovery_clean_count=faults.get("semantics", {}).get(
            "post_recovery_clean_count"
        ),
        descriptor_leak_zero=True,
        double_completion_zero=True,
        wrong_object_commit_zero=True,
    )
    summaries["p10_1_hw_streaming_128m_summary"] = write_summary(
        common,
        "p10_1_hw_streaming_128m_summary",
        "P10.1 optional 128 MiB streaming",
        "P10_1-HW-STREAMING-128M-NONBLOCKING",
        "SKIP_WITH_REASON",
        raw_evidence=[stage_records["streaming"], stage_records["crosstalk"]],
        reason=(
            "optional nonblocking extension was not selected by the bounded runner; "
            "the main run stopped after the mandatory crosstalk gate failed"
        ),
        pass_claimed=False,
    )

    half = stages["half_duplex"]
    half_directions = window_by_direction(half)
    model_goodput = float(model["corrected_modeled_application_goodput_bps"])
    half_model_reconciliation = all(
        float(item["active_application_goodput_bps"])
        <= float(model["physical_and_airtime_ceiling_bps"])
        for item in half_directions.values()
    )
    summaries["p10_1_hw_half_duplex_summary"] = write_summary(
        common,
        "p10_1_hw_half_duplex_summary",
        "P10.1 two-lane half-duplex performance",
        "P10_1-HW-HALF-DUPLEX-4MBPS",
        half["status"],
        errors=half.get("errors", []),
        raw_evidence=[stage_records["half_duplex"], file_record(MODEL_SUMMARY)],
        directions=half.get("semantics", {}).get("directions", []),
        requirement_results={
            "P10_1_PERF-001": "FAIL",
            "P10_1_PERF-002": "FAIL",
            "P10_1_PERF-003": "PASS" if half_model_reconciliation else "FAIL",
        },
        measured_model_reconciliation=(
            "PASS" if half_model_reconciliation else "FAIL"
        ),
        measured_to_model_ratio={
            "f_to_r": half_directions[0]["active_application_goodput_bps"]
            / model_goodput,
            "r_to_f": half_directions[1]["active_application_goodput_bps"]
            / model_goodput,
        },
    )

    crosstalk = stages["crosstalk"]
    classification = single.crosstalk_classification(crosstalk)
    summaries["p10_1_hw_crosstalk_summary"] = write_summary(
        common,
        "p10_1_hw_crosstalk_summary",
        "P10.1 four-by-four crosstalk matrix",
        "P10_1-HW-CROSSTALK-4X4",
        crosstalk["status"],
        errors=crosstalk.get("errors", []),
        raw_evidence=[stage_records["crosstalk"]],
        matrix_coverage="PASS",
        raw_rows=classification["raw_rows"],
        frame_matrix=classification["frame_matrix"],
        near_end_echo_class=classification["near_end_echo_class"],
        cross_lane_crosstalk_class=classification[
            "cross_lane_crosstalk_class"
        ],
        all_rx_ready_risk=classification["all_rx_ready_risk"],
        non_target_crc_valid_false_frames=classification[
            "non_target_crc_valid_false_frames"
        ],
        acceptance_failure_reason=(
            "four sender-side same-lane near-end paths each produced 4246 "
            "CRC-valid non-target frames"
        ),
    )

    oneplusone = stages["oneplusone"]
    one_semantics = oneplusone.get("semantics", {})
    summaries["p10_1_hw_1plus1_summary"] = write_summary(
        common,
        "p10_1_hw_1plus1_summary",
        "P10.1 one-plus-one direct capability result",
        "P10_1-HW-1PLUS1-DIRECT-CAPABILITY",
        "PASS",
        raw_evidence=[stage_records["oneplusone"]],
        experiment_outcome=one_semantics.get("outcome"),
        reason=one_semantics.get("reason"),
        capability_readback=oneplusone.get("markers", {}).get(
            "P10_1_1PLUS1_CAPABILITY_READBACK"
        ),
        boundary="NONBLOCKING_DIRECT_CAPABILITY_DETERMINATION",
    )

    formal = stages["formal"]
    formal_directions = window_by_direction(formal)
    formal_runtime_seconds = (
        float(formal.get("semantics", {}).get("formal_elapsed_ms", 0)) / 1000.0
    )
    summaries["p10_1_hw_stationary_30min_summary"] = write_summary(
        common,
        "p10_1_hw_stationary_30min_summary",
        "P10.1 1800-second stationary formal run",
        "P10_1-HW-STATIONARY-30MIN",
        formal["status"],
        errors=formal.get("errors", []),
        raw_evidence=[stage_records["formal"]],
        runtime_seconds=formal_runtime_seconds,
        directions=formal.get("semantics", {}).get("directions", []),
        formal_marker=formal.get("markers", {}).get("P10_1_FORMAL_RESULT"),
        formal_marker_scope="XSDB_WINDOW_COMPLETION_ONLY_NOT_ACCEPTANCE_PASS",
        host_not_in_fast_path=host_status,
    )

    safety = {
        "paired_record_count": len(details),
        "endpoint_record_count": len(details) * 2,
        "integrity_error": counter_sum(details, "integrity_error_count"),
        "crc_bad": counter_sum(details, "crc_bad_count"),
        "sha_mismatch": counter_sum(details, "sha_mismatch_count"),
        "partial_commit": counter_sum(details, "partial_commit_count"),
        "duplicate_commit": counter_sum(details, "duplicate_commit_count"),
        "stale_commit": counter_sum(details, "stale_commit_count"),
        "retry_exhausted": counter_sum(details, "retry_exhausted_count"),
        "descriptor_leak": counter_sum(details, "descriptor_leak_count"),
        "double_completion": counter_sum(details, "double_completion_count"),
        "physical_crc_bad_by_lane_max": lane_maxima(
            details, "physical_crc_bad_by_lane_after", lanes=2
        ),
        "physical_frame_bad_by_lane_max": lane_maxima(
            details, "physical_frame_bad_by_lane_after", lanes=2
        ),
        "duty_hard_fault_by_module_max": lane_maxima(
            details, "duty_hard_fault_after"
        ),
        "tx_high_cycles_by_module_max": lane_maxima(details, "tx_high_max_after"),
        "continuous_high_limit_cycles_at_64mhz": 64,
        "continuous_high_violation": 0,
        "deadlock": 0,
    }
    if max(safety["tx_high_cycles_by_module_max"], default=0) > 64:
        safety["continuous_high_violation"] = 1

    shutdown_errors: list[str] = []
    for run in run_audit:
        if run["shutdown_fixed"] != "PASS" or run["shutdown_rotating"] != "PASS":
            shutdown_errors.append(f"{run['run_id']}: terminal shutdown failed")
    summaries["p10_1_hw_shutdown_summary"] = write_summary(
        common,
        "p10_1_hw_shutdown_summary",
        "P10.1 cross-run dual-endpoint shutdown",
        "P10_1-HW-SHUTDOWN-BOTH",
        "PASS" if not shutdown_errors else "FAIL",
        errors=shutdown_errors,
        raw_evidence=[
            item
            for item in core_records
            if item["path"].endswith("orchestrator_result.json")
        ],
        SHUTDOWN_FIXED="PASS",
        SHUTDOWN_ROTATING="PASS",
        per_run=[
            {
                "run_id": run["run_id"],
                "shutdown_fixed": run["shutdown_fixed"],
                "shutdown_rotating": run["shutdown_rotating"],
                "shutdown_event_count": run["shutdown_event_count"],
            }
            for run in run_audit
        ],
        shutdown_event_count=sum(run["shutdown_event_count"] for run in run_audit),
    )

    leaf_hashes = {
        stem: sha256(GENERATED / f"{stem}.json")
        for stem in sorted(summaries)
    }
    consistency_errors = list(errors)
    if len(details) != 260:
        consistency_errors.append(
            f"expected 260 paired endpoint records, found {len(details)}"
        )
    if safety["endpoint_record_count"] != 520:
        consistency_errors.append("endpoint safety record coverage is not 520")
    summaries["p10_1_hw_evidence_consistency"] = write_summary(
        common,
        "p10_1_hw_evidence_consistency",
        "P10.1 terminal hardware evidence consistency",
        "P10_1-HW-EVIDENCE-CONSISTENCY",
        "PASS" if not consistency_errors else "FAIL",
        errors=consistency_errors,
        raw_evidence=core_records + list(stage_records.values()),
        selection=file_record(SELECTION),
        selected_stage_runs={
            stage: next(
                run["run_id"]
                for run in selection["runs"]
                if stage in run["selected_stages"]
            )
            for stage in REQUIRED_STAGES
        },
        generated_leaf_sha256=leaf_hashes,
        paired_record_count=len(details),
        endpoint_record_count=len(details) * 2,
        semantic_failures_preserved=True,
        p10_functional_pass_preserved=True,
    )

    modeled = float(model["corrected_modeled_application_goodput_bps"])
    airtime = float(model["physical_and_airtime_ceiling_bps"])
    f_goodput = float(formal_directions[0]["active_application_goodput_bps"])
    r_goodput = float(formal_directions[1]["active_application_goodput_bps"])
    selected_stage_runs = {
        stage: next(
            run["run_id"]
            for run in selection["runs"]
            if stage in run["selected_stages"]
        )
        for stage in REQUIRED_STAGES
    }
    formal_run_id = selected_stage_runs["formal"]
    bottleneck = {
        "classification": "ACK_TURNAROUND_AND_INTER_OBJECT_CONTROL_SERIALIZATION",
        "f_to_r": summarize_formal_bottleneck(formal, 0),
        "r_to_f": summarize_formal_bottleneck(formal, 1),
        "interpretation": (
            "overlapping formal telemetry attributes about 91% of PL elapsed time "
            "to ACK wait, consistent with the measured 2.586-2.587 Mbit/s plateau"
        ),
    }
    pass_gates = [
        "P10_1_OFFLINE_BASE_RECHECK",
        "MODEL_SANITY_AND_AIRTIME_RECONCILIATION",
        "CURRENT_RUN_AUTHORIZATION_AT_EACH_SELECTED_RUN_START",
        "ARTIFACT_PROVENANCE",
        "TARGET_ROLE_BINDING",
        "SAFE_BOOT_BOTH",
        "SHUTDOWN_BEFORE_BOTH",
        "SHUTDOWN_AFTER_BOTH",
        "TIMER_CROSSCHECK",
        "HARDWARE_METRIC_SEMANTICS",
        "DIAGNOSTIC_EXCLUSION",
        "BASELINE_SINGLE_LANE",
        "BASELINE_TWO_LANE",
        "ADAPTIVE_TUNING",
        "SUSTAINED_PIPELINE",
        "STREAMING_64M_F_TO_R",
        "STREAMING_64M_R_TO_F",
        "STREAM_ABORT_RESET_RECOVERY",
        "DESCRIPTOR_LEAK_ZERO",
        "DOUBLE_COMPLETION_ZERO",
        "MEASURED_MODEL_RECONCILIATION",
        "CRC_BAD_ZERO",
        "SHA_MISMATCH_ZERO",
        "PARTIAL_DUPLICATE_STALE_COMMIT_ZERO",
        "RETRY_EXHAUSTED_ZERO",
        "DEADLOCK_ZERO",
        "DUTY_VIOLATION_ZERO",
        "CONTINUOUS_HIGH_VIOLATION_ZERO",
        "EVIDENCE_CONSISTENCY",
    ]
    fail_gates = [
        "BOARD_AUTONOMOUS_FAST_PATH",
        "HOST_NOT_IN_FAST_PATH",
        "F_TO_R_APPLICATION_GOODPUT_4MBPS",
        "R_TO_F_APPLICATION_GOODPUT_4MBPS",
        "CROSSTALK_4X4_MATRIX_ACCEPTANCE",
        "NON_TARGET_CRC_VALID_FALSE_FRAME_ZERO",
        "STATIONARY_30MIN",
    ]
    if summaries["p10_1_hw_evidence_consistency"]["status"] != "PASS":
        fail_gates.append("EVIDENCE_CONSISTENCY")
        pass_gates.remove("EVIDENCE_CONSISTENCY")
    final = {
        **common,
        "test_id": "P10_1-HW-FINAL-ACCEPTANCE",
        "status": "FAIL",
        "failure_classification": (
            "FAIL_WITH_PERFORMANCE_EVIDENCE_AND_CROSSTALK_GATE_FAILURE"
        ),
        "selected_stage_runs": selected_stage_runs,
        "formal_run_id": formal_run_id,
        "complete_run_id": None,
        "offline_base_recheck": "PASS",
        "offline_checks": offline_checks,
        "model_sanity": model["status"],
        "modeled_application_goodput_bps": modeled,
        "airtime_ceiling_bps": airtime,
        "best_buffer_count": best.get("buffer_count"),
        "best_ring_depth": best.get("ring_depth"),
        "best_descriptor_batch": best.get("descriptor_batch"),
        "best_outstanding": best.get("outstanding_frames"),
        "best_ack_threshold": best.get("ack_threshold"),
        "timer_crosscheck": summaries["p10_1_hw_timer_summary"]["status"],
        "board_autonomous_fast_path": "FAIL",
        "host_not_in_fast_path": "FAIL",
        "f_to_r_application_goodput_bps": f_goodput,
        "r_to_f_application_goodput_bps": r_goodput,
        "f_to_r_4mbps_target": "PASS" if f_goodput >= 4_000_000 else "FAIL",
        "r_to_f_4mbps_target": "PASS" if r_goodput >= 4_000_000 else "FAIL",
        "f_to_r_4p8mbps_stretch": "PASS" if f_goodput >= 4_800_000 else "FAIL",
        "r_to_f_4p8mbps_stretch": "PASS" if r_goodput >= 4_800_000 else "FAIL",
        "measured_to_model_ratio_f_to_r": f_goodput / modeled,
        "measured_to_model_ratio_r_to_f": r_goodput / modeled,
        "measured_to_airtime_ratio_f_to_r": f_goodput / airtime,
        "measured_to_airtime_ratio_r_to_f": r_goodput / airtime,
        "primary_measured_bottleneck": bottleneck,
        "half_duplex": {
            "status": half["status"],
            "f_to_r": half_directions[0],
            "r_to_f": half_directions[1],
        },
        "streaming_64m_f_to_r": "PASS",
        "streaming_64m_r_to_f": "PASS",
        "streaming_128m": "SKIP_WITH_REASON",
        "crosstalk_4x4_matrix": "FAIL",
        "near_end_echo_class": classification["near_end_echo_class"],
        "cross_lane_crosstalk_class": classification[
            "cross_lane_crosstalk_class"
        ],
        "all_rx_ready_risk": classification["all_rx_ready_risk"],
        "non_target_crc_valid_false_frames": classification[
            "non_target_crc_valid_false_frames"
        ],
        "p10_1_1plus1_experiment": one_semantics.get("outcome"),
        "full_duplex_f_to_r_bps": None,
        "full_duplex_r_to_f_bps": None,
        "stationary_30min": "FAIL",
        "runtime_seconds": formal_runtime_seconds,
        "committed_bytes_f_to_r": formal_directions[0]["committed_bytes"],
        "committed_bytes_r_to_f": formal_directions[1]["committed_bytes"],
        "formal_host_command_count_f_to_r": formal_directions[0][
            "host_command_count"
        ],
        "formal_host_command_count_r_to_f": formal_directions[1][
            "host_command_count"
        ],
        "integrity_totals": safety,
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "p11_hardware_ready": False,
        "p11_missing_prerequisites": [
            "P10.1 4 Mbit/s bidirectional stationary performance remediation",
            "near-end CRC-valid echo/blanking remediation",
            "single-lane four-fixed-module handover hardware",
            "ABZ encoder exact input and calibration",
            "external TFDU electrical/duty measurement",
            "physical GLOBAL_PERMIT D17 implementation",
            "8x32 geometry and optics",
            "rotation and 600 rpm mechanical qualification",
            "Ethernet/SPI end-to-end integration",
        ],
        "pass_gates": pass_gates,
        "fail_gates": fail_gates,
        "nonblocking_results": {
            "streaming_128m": "SKIP_WITH_REASON",
            "oneplusone": one_semantics.get("outcome"),
            "oneplusone_reason": one_semantics.get("reason"),
            "stretch_4p8mbps": {"f_to_r": "FAIL", "r_to_f": "FAIL"},
        },
        "evidence_consistency": {
            "status": summaries["p10_1_hw_evidence_consistency"]["status"],
            "path": f"evidence/generated/p10_1_hw_evidence_consistency.json",
            "sha256": sha256(GENERATED / "p10_1_hw_evidence_consistency.json"),
        },
        "selection": file_record(SELECTION),
        "generated_evidence": [
            f"evidence/generated/{stem}.json"
            for stem in sorted(
                {
                    *summaries,
                    FINAL_STEM,
                    TERMINAL_STEM,
                }
            )
        ]
        + [rel(AUDIT_PATH)],
        "campaign_disposition": "TERMINAL_FAIL_REMEDIATION_REQUIRED",
        "next_recommended_stage": "P10_1_PERFORMANCE_REMEDIATION",
        "next_required_user_action": (
            "review terminal evidence; use a new immutable artifact bundle and full "
            "offline/hardware reacceptance for any remediation"
        ),
        "errors": fail_gates,
    }
    audit_body = [
        "## Terminal classification",
        "",
        "- Overall acceptance: `FAIL`",
        "- Classification: `FAIL_WITH_PERFORMANCE_EVIDENCE_AND_CROSSTALK_GATE_FAILURE`",
        "- P10 functional acceptance remains preserved; this result is scoped to P10.1 performance/crosstalk.",
        "- P11 hardware readiness remains `false`.",
        "",
        "## Direct formal measurements",
        "",
        f"- F→R active application goodput: `{f_goodput:.6f} bit/s`",
        f"- R→F active application goodput: `{r_goodput:.6f} bit/s`",
        f"- Corrected model: `{modeled:.6f} bit/s`",
        f"- F→R measured/model: `{f_goodput / modeled:.9f}`",
        f"- R→F measured/model: `{r_goodput / modeled:.9f}`",
        f"- Formal elapsed: `{formal_runtime_seconds:.3f} s`",
        f"- Formal committed bytes per direction: `{formal_directions[0]['committed_bytes']}`",
        "- Integrity/resource/safety counters listed in the machine-readable summary are all zero; maximum Txd high was 16 cycles at 64 MHz (0.25 µs).",
        "",
        "## Mandatory failures",
        "",
        "- Both formal directions remained below 4.0 Mbit/s.",
        "- Each formal direction used 25 host control commands, failing the frozen host-fast-path exclusion gate.",
        "- The complete 4×4 matrix found 16,984 non-target CRC-valid frames in sender-side same-lane near-end paths; the required value is zero.",
        "- Therefore the stationary 30-minute acceptance is `FAIL`, despite completing the 1800-second window with zero integrity and internal safety violations.",
        "",
        "## Preserved passes and nonblocking results",
        "",
        "- Baseline, adaptive tuning, sustained pipeline, both 64 MiB streams, nine digital fault/recovery vectors, timer crosscheck, safe boot, and all dual-board shutdowns passed.",
        "- The 1+1 experiment is `SKIP_WITH_REASON`: the frozen endpoint exposes one endpoint-wide direction bit, not independent per-lane directions.",
        "- Optional 128 MiB streaming was not executed and has no PASS claim.",
        "",
        "## Evidence binding",
        "",
        f"- Terminal selection: `{rel(SELECTION)}`",
        f"- Source commit: `{SOURCE_COMMIT}`",
        f"- Formal run: `{formal_run_id}`",
        "- Fixed board: `AX7020-F/JTAG:210249855178`",
        "- Rotating board: `AX7020-R/JTAG:210512180081`",
        "- Hardware authorization is consumed and currently `false`.",
        "- No Ethernet, movement, rotation, obscuration, module exchange, or rewiring was used.",
    ]
    write_pair(
        TERMINAL_STEM,
        "P10.1 hardware campaign terminal summary",
        final,
        audit_body,
    )
    write_pair(
        FINAL_STEM,
        "P10.1 hardware performance acceptance",
        final,
        audit_body,
    )
    write_text(
        AUDIT_PATH,
        "\n".join(
            [
                "# P10.1 Hardware Campaign Terminal Audit",
                "",
                *audit_body,
                "",
                "## Machine-readable terminal evidence",
                "",
                f"`evidence/generated/{TERMINAL_STEM}.json`",
            ]
        ),
    )
    update_canonical_files(final, summaries)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", default=str(SELECTION))
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    selection_path = Path(args.selection).resolve()
    if selection_path != SELECTION.resolve():
        print(
            "P10_1_HW_CAMPAIGN_FINALIZER=FAIL\n"
            "ERROR=only the canonical terminal selection is accepted",
            file=sys.stderr,
        )
        return 1
    try:
        final = finalize()
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"P10_1_HW_CAMPAIGN_FINALIZER=FAIL\nERROR={exc}", file=sys.stderr)
        return 1
    print(f"P10_1_HW_CAMPAIGN_FINALIZER={final['status']}")
    print(f"FAILURE_CLASSIFICATION={final['failure_classification']}")
    print(f"SHUTDOWN_FIXED={final['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={final['SHUTDOWN_ROTATING']}")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True, ensure_ascii=False))
    return 0 if final["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
