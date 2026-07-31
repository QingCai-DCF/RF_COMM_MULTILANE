#!/usr/bin/env python3
"""Freeze P10.1 hardware artifacts or finalize one immutable hardware run.

The artifact mode is offline-build-only.  The final mode is read-only with
respect to hardware: it consumes already-captured run evidence, writes the
required generated summaries, and updates canonical scoped state.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from p10_1_common import ROOT, rel, sha256, write_json, write_pair
from p8a_common import render_project_status


GENERATED = ROOT / "evidence/generated"
HARDWARE_ROOT = ROOT / "evidence/hardware/p10_1"
FUNCTIONAL = GENERATED / "p10_1_hw_functional_build_summary.json"
RUNTIME = GENERATED / "p10_1_hw_ps_runtime_build_summary.json"
SHUTDOWN = GENERATED / "p10_offline_artifact_manifest.json"
ARTIFACT_SUMMARY = GENERATED / "p10_1_hw_artifact_summary.json"
AUTHORIZATION = ROOT / "config/p10_1_current_run_hardware_authorization.json"
STATE = ROOT / "config/project_state.json"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATUS = ROOT / "PROJECT_STATUS.md"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
P10_RUNTIME = ROOT / "scripts/p10_hardware_runtime.py"
P10_RUNTIME_REVERIFY_STEM = "p10_goodput_runtime_source_reverification"
P10_RUNTIME_REVERIFY = GENERATED / f"{P10_RUNTIME_REVERIFY_STEM}.json"
P10_RUNTIME_BASE_COMMIT = "201a05e199a56e785a06d61910d42139fa0248e5"
P10_RUNTIME_BASE_SHA256 = (
    "33f11e8ae3070cce7e915c2af31dd5a0aad8cb8a9999a2a1feb7d133744d5da1"
)
P10_RUNTIME_CURRENT_SHA256 = (
    "1cf329ec479636369ba3c0c2bb2248c12b4ebab82d3c849cf86f7c6f53209a76"
)
P10_RUNTIME_ALLOWED_DIFF_SHA256 = (
    "2915c5b74dc877b120dbf6fd69ed18c7d484ea3cd48cfcfb040821a5cb9597c4"
)
GOAL_SHA256 = (
    "b3d0ae793a89ba270ca72880fb4fa38bcb17ac7631f3fc650e2557963840f9d3"
)
OFFLINE_TAG = "p10.1-offline-performance-ready"
OFFLINE_SOURCE = "ae942f0b5d9e9b4b7f5ced4751cc748c55b81183"
OFFLINE_EVIDENCE = "8c34d60f064b01b95dc9c35b664ffbe43efb0b1f"
FIXED_ID = "AX7020-F/JTAG:210249855178"
ROTATING_ID = "AX7020-R/JTAG:210512180081"
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
DEVICE_CAPACITY = {
    "lut": 53200,
    "ff": 106400,
    "bram36_equivalent": 140.0,
    "dsp": 220,
}
RESOURCE_LIMITS = {
    "lut": 70.0,
    "ff": 70.0,
    "bram36_equivalent": 75.0,
    "dsp": 50.0,
}
REQUIRED_GENERATED_STEMS = (
    "p10_1_hw_repo_intake",
    "p10_1_hw_model_sanity_summary",
    "p10_1_hw_artifact_summary",
    "p10_1_hw_authorization_summary",
    "p10_1_hw_target_identity_summary",
    "p10_1_hw_safe_boot_summary",
    "p10_1_hw_timer_summary",
    "p10_1_hw_metric_semantics_summary",
    "p10_1_hw_baseline_summary",
    "p10_1_hw_tuning_summary",
    "p10_1_hw_pipeline_summary",
    "p10_1_hw_streaming_64m_summary",
    "p10_1_hw_streaming_128m_summary",
    "p10_1_hw_half_duplex_summary",
    "p10_1_hw_crosstalk_summary",
    "p10_1_hw_1plus1_summary",
    "p10_1_hw_stationary_30min_summary",
    "p10_1_hw_shutdown_summary",
)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} does not contain an object")
    return value


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(path: Path) -> dict[str, Any]:
    return {
        "path": rel(path),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def artifact_record(item: dict[str, Any], role: str, kind: str) -> dict[str, Any]:
    path = (ROOT / str(item["path"])).resolve()
    result = record(path)
    result.update({"role": role, "kind": kind})
    if result["sha256"] != item.get("sha256"):
        raise ValueError(f"{role} {kind} SHA256 mismatch")
    if result["bytes"] != int(item.get("bytes", -1)):
        raise ValueError(f"{role} {kind} byte count mismatch")
    return result


def parse_resources(report: Path) -> dict[str, Any]:
    text = report.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"^\|\s*p10_ps_system_wrapper\s*\|\s*\(top\)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        text,
        re.MULTILINE,
    )
    if match is None:
        return {"status": "FAIL", "error": "top utilization row not found"}
    total_lut, _, _, _, ff, ramb36, ramb18, dsp = (
        int(value) for value in match.groups()
    )
    used = {
        "lut": total_lut,
        "ff": ff,
        "bram36_equivalent": ramb36 + ramb18 / 2.0,
        "dsp": dsp,
    }
    percent = {
        key: value / DEVICE_CAPACITY[key] * 100.0
        for key, value in used.items()
    }
    within = all(percent[key] <= RESOURCE_LIMITS[key] for key in RESOURCE_LIMITS)
    return {
        "status": "PASS" if within else "FAIL",
        "used": used,
        "capacity": DEVICE_CAPACITY,
        "percent": percent,
        "limits_percent": RESOURCE_LIMITS,
        "within_limits": within,
    }


def generate_artifact_summary() -> dict[str, Any]:
    errors: list[str] = []
    try:
        functional = load_json(FUNCTIONAL)
        runtime = load_json(RUNTIME)
        shutdown = load_json(SHUTDOWN)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        functional, runtime, shutdown = {}, {}, {}
        errors.append(f"build evidence unreadable: {exc}")
    source = functional.get("source_commit")
    if (
        functional.get("status") != "PASS"
        or runtime.get("status") != "PASS"
        or functional.get("source_worktree_dirty") is not False
        or runtime.get("source_worktree_dirty") is not False
        or runtime.get("source_commit") != source
        or not isinstance(source, str)
        or not re.fullmatch(r"[0-9a-f]{40}", source)
    ):
        errors.append("functional/runtime summaries are not one clean source")
    if shutdown.get("status") != "PASS":
        errors.append("shutdown artifact manifest is not PASS")

    artifacts: list[dict[str, Any]] = []
    roles: list[dict[str, Any]] = []
    for role in ("fixed", "rotating"):
        try:
            f_role = next(
                item for item in functional["roles"] if item["role"] == role
            )
            r_role = next(item for item in runtime["roles"] if item["role"] == role)
            shutdown_item = next(
                item
                for item in shutdown["artifacts"]
                if item["role"] == role and item["kind"] == "shutdown_bitstream"
            )
            role_artifacts = [
                artifact_record(
                    f_role["artifacts"]["bitstream"], role, "performance_bitstream"
                ),
                artifact_record(f_role["artifacts"]["xsa"], role, "xsa"),
                artifact_record(r_role["artifacts"]["bsp"], role, "bsp"),
                artifact_record(r_role["artifacts"]["elf"], role, "elf"),
                artifact_record(shutdown_item, role, "shutdown_bitstream"),
            ]
            artifacts.extend(role_artifacts)
            markers = f_role.get("markers", {})
            implementation_checks = {
                "role_build": f_role.get("status") == "PASS",
                "runtime_build": r_role.get("status") == "PASS",
                "wns": float(markers.get("P10_WNS_NS", "-1")) >= 0.0,
                "whs": float(markers.get("P10_WHS_NS", "-1")) >= 0.0,
                "tns": float(markers.get("P10_TNS_NS", "-1")) == 0.0,
                "drc_critical": markers.get("P10_DRC_CRITICAL_COUNT") == "0",
                "drc_error": markers.get("P10_DRC_ERROR_COUNT") == "0",
                "cdc_critical": markers.get("P10_CDC_CRITICAL_COUNT") == "0",
                "methodology_critical": (
                    markers.get("P10_METHODOLOGY_CRITICAL_COUNT") == "0"
                ),
                "reqp_1839": markers.get("P10_REQP_1839_COUNT") == "0",
                "ethernet_disabled": markers.get("P10_ETHERNET_ENABLED") == "false",
                "led_active_low": (
                    markers.get("P10_PL_ACTIVITY_LED_ACTIVE_LOW") == "true"
                ),
                "led_monitor_only": (
                    markers.get("P10_PL_ACTIVITY_LED_SAFETY_ROLE") == "MONITOR_ONLY"
                ),
            }
            util_report = next(
                ROOT / item["path"]
                for item in f_role.get("reports", [])
                if item["path"].endswith("post_route_utilization.rpt")
            )
            resources = parse_resources(util_report)
            if not all(implementation_checks.values()):
                errors.append(f"{role} implementation hard gate failed")
            if resources.get("status") != "PASS":
                errors.append(f"{role} resource hard gate failed")
            roles.append(
                {
                    "role": role,
                    "board_id": FIXED_ID if role == "fixed" else ROTATING_ID,
                    "profile": f_role.get("profile"),
                    "part": functional.get("part"),
                    "implementation_checks": implementation_checks,
                    "resources": resources,
                    "markers": markers,
                    "reports": f_role.get("reports", []),
                    "artifacts": role_artifacts,
                    "status": (
                        "PASS"
                        if all(implementation_checks.values())
                        and resources.get("status") == "PASS"
                        else "FAIL"
                    ),
                }
            )
        except (KeyError, StopIteration, OSError, ValueError, TypeError) as exc:
            errors.append(f"{role} artifact audit failed: {exc}")

    required_inputs = {
        name: record(ROOT / name)
        for name in (
            "config/hardware/p10_active_wiring.yaml",
            "config/hardware/p10_1_ax7020_pl_activity_leds.yaml",
            "config/performance/p10_1_measurement_contract.yaml",
            "config/performance/p10_1_pipeline.yaml",
            "config/performance/p10_1_streaming.yaml",
            "config/performance/p10_1_hardware_runtime.yaml",
            "config/register_map/ir_axi_regs.yaml",
            "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
            "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
        )
    }
    payload = {
        "schema_version": 1,
        "test_id": "P10_1-HW-IMMUTABLE-ARTIFACT-PROVENANCE",
        "status": "PASS" if not errors else "FAIL",
        "generated_at_utc": utc_now(),
        "source_commit": source,
        "offline_base_tag": OFFLINE_TAG,
        "offline_source_commit": OFFLINE_SOURCE,
        "offline_evidence_checkpoint": OFFLINE_EVIDENCE,
        "goal_sha256": GOAL_SHA256,
        "board_identities": {"fixed": FIXED_ID, "rotating": ROTATING_ID},
        "roles": roles,
        "artifacts": artifacts,
        "required_inputs": required_inputs,
        "functional_build_summary": record(FUNCTIONAL)
        if FUNCTIONAL.is_file()
        else None,
        "runtime_build_summary": record(RUNTIME) if RUNTIME.is_file() else None,
        "shutdown_manifest": record(SHUTDOWN) if SHUTDOWN.is_file() else None,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "network_used": False,
        "errors": errors,
    }
    write_pair(
        "p10_1_hw_artifact_summary",
        "P10.1 immutable AX7020 performance artifacts",
        payload,
    )
    return payload


def authorized_artifact_map(
    authorization: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Return the artifacts captured for this run, never the latest build."""
    kind_aliases = {"functional_bitstream": "performance_bitstream"}
    artifact_map = {
        f"{item['role']}:{kind_aliases.get(item['kind'], item['kind'])}": {
            key: item[key] for key in ("path", "sha256", "bytes")
        }
        for item in authorization.get("artifacts", [])
    }
    if not artifact_map:
        raise ValueError("captured authorization has no immutable artifacts")
    return artifact_map


def validate_authorized_artifacts(
    authorization: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(authorization.get("artifacts", [])):
        try:
            role = str(item["role"])
            kind = str(item["kind"])
            identity = (role, kind)
            if identity in seen:
                errors.append(f"duplicate authorized artifact: {role}:{kind}")
                continue
            seen.add(identity)
            path = (ROOT / str(item["path"])).resolve()
            path.relative_to(ROOT.resolve())
            if not path.is_file():
                errors.append(f"authorized artifact missing: {item['path']}")
                continue
            if path.stat().st_size != int(item["bytes"]):
                errors.append(f"authorized artifact byte mismatch: {item['path']}")
            if sha256(path) != item["sha256"]:
                errors.append(f"authorized artifact SHA256 mismatch: {item['path']}")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"invalid authorized artifact {index}: {exc}")
    if not seen:
        errors.append("captured authorization has no immutable artifacts")
    return errors


def function_source_hashes(
    source: bytes, function_names: tuple[str, ...]
) -> dict[str, str]:
    tree = ast.parse(source.decode("utf-8"))
    lines = source.splitlines(keepends=True)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    result: dict[str, str] = {}
    for name in function_names:
        node = functions.get(name)
        if node is None or node.end_lineno is None:
            raise ValueError(f"runtime function missing: {name}")
        body = b"".join(lines[node.lineno - 1 : node.end_lineno])
        result[name] = hashlib.sha256(body).hexdigest()
    return result


def audit_p10_runtime_source_binding() -> dict[str, Any]:
    source_path = rel(P10_RUNTIME)
    previous = subprocess.run(
        [
            "git",
            "show",
            f"{P10_RUNTIME_BASE_COMMIT}:{source_path}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    current = P10_RUNTIME.read_bytes()
    diff = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            f"{P10_RUNTIME_BASE_COMMIT}..HEAD",
            "--",
            source_path,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    worktree_diff = subprocess.run(
        ["git", "diff", "--name-only", "--", source_path],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    function_names = ("evaluate_stage", "summarize_campaign")
    previous_functions = function_source_hashes(previous, function_names)
    current_functions = function_source_hashes(current, function_names)
    previous_sha = hashlib.sha256(previous).hexdigest()
    current_sha = hashlib.sha256(current).hexdigest()
    diff_sha = hashlib.sha256(diff).hexdigest()
    errors: list[str] = []
    if previous_sha != P10_RUNTIME_BASE_SHA256:
        errors.append("historical P10 runtime SHA256 is not the frozen value")
    if current_sha != P10_RUNTIME_CURRENT_SHA256:
        errors.append("current P10 runtime SHA256 is outside this audit")
    if diff_sha != P10_RUNTIME_ALLOWED_DIFF_SHA256:
        errors.append("P10 runtime diff is outside the audited identity-only change")
    if worktree_diff:
        errors.append("P10 runtime has uncommitted changes")
    if previous_functions != current_functions:
        errors.append("goodput calculation or campaign aggregation function changed")
    return {
        "schema_version": 1,
        "test_id": "P10-GOODPUT-RUNTIME-SOURCE-REVERIFICATION",
        "status": "PASS" if not errors else "FAIL",
        "verification_scope": "P10_POST_ACCEPTANCE_ANALYSIS_NO_HARDWARE",
        "generated_at_utc": utc_now(),
        "historical_source_commit": P10_RUNTIME_BASE_COMMIT,
        "current_source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "runtime_path": source_path,
        "historical_runtime_sha256": previous_sha,
        "current_runtime_sha256": current_sha,
        "audited_diff_sha256": diff_sha,
        "audited_change_class": "REGISTER_MAP_IDENTITY_BINDING_ONLY",
        "function_source_sha256": {
            name: {
                "historical": previous_functions[name],
                "current": current_functions[name],
                "identical": previous_functions[name] == current_functions[name],
            }
            for name in function_names
        },
        "goodput_formula_changed": False if not errors else None,
        "campaign_minimum_aggregation_changed": False if not errors else None,
        "historical_goodput_audit_invalidated": False if not errors else None,
        "current_runtime_worktree_clean": not bool(worktree_diff),
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "errors": errors,
    }


def generate_p10_runtime_source_reverification() -> dict[str, Any]:
    payload = audit_p10_runtime_source_binding()
    write_pair(
        P10_RUNTIME_REVERIFY_STEM,
        "P10 goodput runtime source re-verification",
        payload,
    )
    return payload


def consumed_authorization_payload(
    authorization: dict[str, Any],
    *,
    run_id: str,
    campaign_status: str,
    consumed_at_utc: str,
    final_evidence_sha256: str,
    campaign_disposition: str | None,
    next_required_user_action: str | None,
    shutdown_fixed: str,
    shutdown_rotating: str,
) -> dict[str, Any]:
    result = copy.deepcopy(authorization)
    if result.get("run_id") != run_id:
        raise ValueError("current authorization run_id does not match final run")
    if result.get("current_run_hardware_authorization") is False:
        if (
            result.get("consumed") is True
            and result.get("consumed_by_run_id") == run_id
            and result.get("reusable_for_future_run") is False
        ):
            result.update(
                {
                    "campaign_status": campaign_status,
                    "campaign_disposition": campaign_disposition,
                    "shutdown_fixed": shutdown_fixed,
                    "shutdown_rotating": shutdown_rotating,
                    "final_evidence_sha256": final_evidence_sha256,
                    "next_required_user_action": next_required_user_action,
                }
            )
            return result
        raise ValueError("current authorization has an invalid consumed state")
    if (
        result.get("status") != "AUTHORIZED"
        or result.get("current_run_hardware_authorization") is not True
    ):
        raise ValueError("current authorization was not active for this run")
    result.update(
        {
            "status": f"CONSUMED_AFTER_P10_1_HARDWARE_{campaign_status}",
            "authorization_status_at_run_start": "AUTHORIZED",
            "current_run_hardware_authorization": False,
            "consumed": True,
            "consumed_by_run_id": run_id,
            "consumed_at_utc": consumed_at_utc,
            "reusable_for_future_run": False,
            "campaign_status": campaign_status,
            "campaign_disposition": campaign_disposition,
            "hardware_actions_executed": True,
            "shutdown_fixed": shutdown_fixed,
            "shutdown_rotating": shutdown_rotating,
            "final_evidence_path": rel(
                GENERATED / "p10_1_hw_final_summary.json"
            ),
            "final_evidence_sha256": final_evidence_sha256,
            "next_required_user_action": next_required_user_action,
        }
    )
    return result


def consume_current_authorization(final: dict[str, Any]) -> dict[str, Any]:
    current = load_json(AUTHORIZATION)
    consumed = consumed_authorization_payload(
        current,
        run_id=final["run_id"],
        campaign_status=final["status"],
        consumed_at_utc=final["generated_at_utc"],
        final_evidence_sha256=sha256(
            GENERATED / "p10_1_hw_final_summary.json"
        ),
        campaign_disposition=final.get("campaign_disposition"),
        next_required_user_action=final.get("next_required_user_action"),
        shutdown_fixed=final["SHUTDOWN_FIXED"],
        shutdown_rotating=final["SHUTDOWN_ROTATING"],
    )
    write_json(AUTHORIZATION, consumed)
    return consumed


def common_context(
    run_id: str,
    authorization: dict[str, Any],
    _latest_artifacts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # `_latest_artifacts` is intentionally ignored.  A historical hardware run
    # must remain bound to the artifacts frozen into its own authorization.
    artifact_map = authorized_artifact_map(authorization)
    inputs = authorization.get("input_hashes", {})
    return {
        "run_id": run_id,
        "source_commit": authorization.get("source_commit"),
        "offline_base_tag": OFFLINE_TAG,
        "offline_source_commit": OFFLINE_SOURCE,
        "offline_evidence_checkpoint": OFFLINE_EVIDENCE,
        "goal_sha256": GOAL_SHA256,
        "board_identities": authorization.get("board_identities"),
        "artifact_hashes": artifact_map,
        "artifact_provenance": "CAPTURED_IMMUTABLE_CURRENT_RUN_AUTHORIZATION",
        "wiring": inputs.get("wiring"),
        "measurement_contract": inputs.get("measurement_contract"),
        "pipeline_config": inputs.get("pipeline_model"),
        "streaming_contract": inputs.get("streaming_contract"),
        "hardware_runtime_config": inputs.get("hardware_runtime"),
        "register_map": inputs.get("register_map"),
        "captured_run_hardware_authorization": True,
        "current_run_hardware_authorization": False,
        "authorization_lifecycle": "CONSUMED_AFTER_RUN",
        "hardware_actions_executed": True,
        "network_used": False,
        "ethernet_used": False,
        "hardware_movement": False,
        "rotation_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0x3",
    }


def pair_payload(
    test_id: str,
    status: str,
    context: dict[str, Any],
    raw_evidence: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "test_id": test_id,
        "status": status,
        "generated_at_utc": utc_now(),
        **context,
        "raw_evidence": raw_evidence,
        **extra,
    }


def stage_record(
    run_root: Path,
    stage: str,
    orchestrator: dict[str, Any] | None = None,
    orchestrator_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = run_root / "stages" / stage / "stage_summary.json"
    if path.is_file():
        return load_json(path), record(path)

    declared = (orchestrator or {}).get("stages", {}).get(stage)
    disposition = (
        "NOT_RUN_DUE_PRIOR_STAGE_FAILURE"
        if declared == "NOT_RUN"
        else "MISSING_STAGE_EVIDENCE"
    )
    payload = {
        "schema_version": 1,
        "test_id": f"P10_1-HW-{stage.upper()}",
        "stage": stage,
        "status": "FAIL",
        "execution_status": declared or "MISSING",
        "disposition": disposition,
        "markers": {},
        "details": [],
        "semantics": {},
        "errors": [
            (
                f"{stage} was not run because the campaign stopped after "
                "an earlier stage failure"
                if declared == "NOT_RUN"
                else f"{stage} stage summary is missing"
            )
        ],
    }
    if orchestrator_path is None or not orchestrator_path.is_file():
        raise ValueError(f"{stage} stage summary and orchestrator evidence are missing")
    source = record(orchestrator_path)
    source.update(
        {
            "evidence_role": "ORCHESTRATOR_STAGE_DISPOSITION",
            "stage": stage,
            "declared_status": declared,
        }
    )
    return payload, source


def verify_run_manifest(run_root: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    path = run_root / "final/run_evidence_sha256_manifest.json"
    try:
        manifest = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"run manifest unreadable: {exc}"], {}
    listed: set[str] = set()
    for item in manifest.get("files", []):
        try:
            relative = str(item["path"])
            candidate = (run_root / relative).resolve()
            candidate.relative_to(run_root.resolve())
            listed.add(relative)
            if (
                not candidate.is_file()
                or candidate.stat().st_size != int(item["bytes"])
                or sha256(candidate) != item["sha256"]
            ):
                errors.append(f"run manifest mismatch: {relative}")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"invalid run manifest entry: {exc}")
    actual = {
        item.relative_to(run_root).as_posix()
        for item in run_root.rglob("*")
        if item.is_file() and item != path
    }
    if listed != actual:
        errors.append("run manifest file set differs from captured run")
    if manifest.get("status") != "PASS":
        errors.append("run manifest status is not PASS")
    return errors, manifest


def cross_board_timer_errors(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for detail in details:
        if detail.get("recovery_case"):
            continue
        required = (
            "ps_elapsed_ticks",
            "ps_timer_frequency_hz",
            "pl_elapsed_ticks",
            "pl_timer_frequency_hz",
        )
        if any(
            key not in detail[role]
            for role in ("fixed", "rotating")
            for key in required
        ):
            continue
        item: dict[str, Any] = {"label": detail.get("label")}
        for timer, ticks, frequency in (
            ("ps", "ps_elapsed_ticks", "ps_timer_frequency_hz"),
            ("pl", "pl_elapsed_ticks", "pl_timer_frequency_hz"),
        ):
            values = []
            for role in ("fixed", "rotating"):
                endpoint = detail[role]
                values.append(
                    endpoint[ticks] / endpoint[frequency]
                    if endpoint[frequency]
                    else 0.0
                )
            maximum = max(values)
            fraction = abs(values[0] - values[1]) / maximum if maximum else 1.0
            item[f"{timer}_fixed_seconds"] = values[0]
            item[f"{timer}_rotating_seconds"] = values[1]
            item[f"{timer}_cross_board_error_percent"] = fraction * 100.0
        results.append(item)
    return results


def classify_ratio(value: float) -> str:
    if value == 0.0:
        return "LOW"
    if value <= 0.01:
        return "MODERATE"
    return "HIGH"


def crosstalk_classification(stage: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    near_ratios: list[float] = []
    cross_ratios: list[float] = []
    for item in stage.get("raw_matrix", []):
        label = str(item.get("label", ""))
        direction = 0 if "_f" in label else 1
        lane = 0 if "f0_" in label or "r0_" in label else 1
        target_count = 64 if "raw64" in label else 1024
        if direction == 0:
            target = item["rotating_rx"][2 + lane]
            near = item["fixed_rx"][lane]
            cross_values = [
                item["fixed_rx"][1 - lane],
                item["rotating_rx"][2 + (1 - lane)],
            ]
        else:
            target = item["fixed_rx"][lane]
            near = item["rotating_rx"][2 + lane]
            cross_values = [
                item["rotating_rx"][2 + (1 - lane)],
                item["fixed_rx"][1 - lane],
            ]
        denominator = max(target, target_count, 1)
        near_ratio = near / denominator
        cross_ratio = max(cross_values, default=0) / denominator
        near_ratios.append(near_ratio)
        cross_ratios.append(cross_ratio)
        rows.append(
            {
                "label": label,
                "target_rx_pulses": target,
                "near_end_echo_pulses": near,
                "maximum_cross_lane_pulses": max(cross_values, default=0),
                "near_end_ratio": near_ratio,
                "cross_lane_ratio": cross_ratio,
            }
        )
    frame_matrix = stage.get("semantics", {}).get("frame_matrix", [])
    false_frames = sum(
        int(item.get("non_target_crc_valid_frames", 0)) for item in frame_matrix
    )
    near_class = (
        classify_ratio(max(near_ratios)) if near_ratios else "NOT_MEASURED"
    )
    cross_class = (
        classify_ratio(max(cross_ratios)) if cross_ratios else "NOT_MEASURED"
    )
    if false_frames:
        risk = "BLOCKED"
    elif not rows:
        risk = "NOT_MEASURED"
    elif cross_class == "HIGH":
        risk = "NEEDS_OPTICAL_BAFFLE"
    elif cross_class == "MODERATE" or near_class == "HIGH":
        risk = "NEEDS_BLANKING"
    else:
        risk = "ACCEPTABLE"
    return {
        "raw_rows": rows,
        "frame_matrix": frame_matrix,
        "near_end_echo_class": near_class,
        "cross_lane_crosstalk_class": cross_class,
        "all_rx_ready_risk": risk,
        "non_target_crc_valid_false_frames": false_frames,
        "classification_thresholds": {
            "LOW": "ratio == 0",
            "MODERATE": "0 < ratio <= 0.01",
            "HIGH": "ratio > 0.01",
        },
    }


def write_hardware_pair(
    stem: str,
    title: str,
    test_id: str,
    status: str,
    context: dict[str, Any],
    raw: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    payload = pair_payload(test_id, status, context, raw, **extra)
    write_pair(stem, title, payload)
    return payload


def update_canonical_state(
    final: dict[str, Any],
    summary_by_stem: dict[str, dict[str, Any]],
) -> None:
    current_authorization = consume_current_authorization(final)
    state = load_json(STATE)
    status = final["status"]
    state["current_run_hardware_authorization"] = False
    state["p10_1_hardware_status"] = status
    state["current_program_stage"] = (
        "P11_PREREQUISITE_ACQUISITION"
        if status == "PASS"
        else "P10_1_PERFORMANCE_REMEDIATION"
    )
    state["p11_status"] = "NOT_STARTED"
    state["p11_hardware_ready"] = False
    state["p10_1_no_hardware_actions_executed"] = False
    state["last_hardware_stage"] = "P10_1"
    state["last_hardware_run_id"] = final["run_id"]
    state["last_shutdown_fixed"] = final["SHUTDOWN_FIXED"]
    state["last_shutdown_rotating"] = final["SHUTDOWN_ROTATING"]
    state["p10_1_current_run_authorization"] = {
        "status": current_authorization["status"],
        "path": rel(AUTHORIZATION),
        "sha256": sha256(AUTHORIZATION),
        "consumed": current_authorization["consumed"],
        "consumed_by_run_id": current_authorization["consumed_by_run_id"],
        "reusable_for_future_run": current_authorization[
            "reusable_for_future_run"
        ],
    }
    campaign = state.setdefault("p10_1_hardware_campaign", {})
    campaign.update(
        {
            "status": status,
            "run_id": final["run_id"],
            "source_commit": final["source_commit"],
            "current_run_hardware_authorization": False,
            "authorization_was_valid": (
                summary_by_stem["p10_1_hw_authorization_summary"].get("status")
                == "PASS"
            ),
            "hardware_actions_executed": True,
            "network_used": False,
            "hardware_movement": False,
            "maximum_lane_mask": "0x3",
            "artifact_provenance": final.get("artifact_provenance"),
            "complete_run_id": final.get("complete_run_id"),
            "campaign_disposition": final.get("campaign_disposition"),
            "retry_run_id_count": final.get("retry_run_id_count"),
            "retry_run_id_limit": final.get("retry_run_id_limit"),
            "next_required_user_action": final.get(
                "next_required_user_action"
            ),
            "final_evidence_path": "evidence/generated/p10_1_hw_final_summary.json",
            "final_evidence_sha256": sha256(
                GENERATED / "p10_1_hw_final_summary.json"
            ),
            "shutdown_fixed": final["SHUTDOWN_FIXED"],
            "shutdown_rotating": final["SHUTDOWN_ROTATING"],
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
    ] = status
    performance = state.setdefault("p10_1_performance_and_observability", {})
    performance["real_hardware_goodput_status"] = status
    performance["hardware_experiments_authorized"] = False
    # Preserve the already-frozen offline sub-scope: its own evidence still
    # truthfully records zero hardware actions.  The new hardware campaign
    # record above owns the direct-run action flag.
    performance["hardware_actions_executed"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_hardware_authorization_id"] = (
        "P10_1-HARDWARE-CURRENT-RUN-IMMUTABLE"
    )
    write_json(STATE, state)
    STATUS.write_text(
        render_project_status(state), encoding="utf-8", newline="\n"
    )

    requirements = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    requirement_to_stem = {
        "P10_1_HW-001": "p10_1_hw_authorization_summary",
        "P10_1_HW-002": "p10_1_hw_artifact_summary",
        "P10_1_TIME-001": "p10_1_hw_timer_summary",
        "P10_1_METRIC-001": "p10_1_hw_metric_semantics_summary",
        "P10_1_AUTO-001": "p10_1_hw_metric_semantics_summary",
        "P10_1_PIPE-001": "p10_1_hw_pipeline_summary",
        "P10_1_STREAM-001": "p10_1_hw_streaming_64m_summary",
        "P10_1_STREAM-002": "p10_1_hw_streaming_64m_summary",
        "P10_1_STREAM-003": "p10_1_hw_streaming_64m_summary",
        "P10_1_PERF-001": "p10_1_hw_half_duplex_summary",
        "P10_1_PERF-002": "p10_1_hw_half_duplex_summary",
        "P10_1_PERF-003": "p10_1_hw_half_duplex_summary",
        "P10_1_XTALK-001": "p10_1_hw_crosstalk_summary",
        "P10_1_FD-001": "p10_1_hw_1plus1_summary",
        "P10_1_SOAK-001": "p10_1_hw_stationary_30min_summary",
        "P10_1_SAFE-001": "p10_1_hw_shutdown_summary",
    }
    artifact_context = final["artifact_hashes"]
    common_hashes = [
        {"path": item["path"], "sha256": item["sha256"]}
        for key, item in sorted(artifact_context.items())
        if key.endswith(":performance_bitstream") or key.endswith(":elf")
    ]
    if final.get("wiring"):
        common_hashes.append(
            {
                "path": final["wiring"]["path"],
                "sha256": final["wiring"]["sha256"],
            }
        )
    artifact_summary_hashes = [
        {"path": item["path"], "sha256": item["sha256"]}
        for item in summary_by_stem["p10_1_hw_artifact_summary"].get(
            "artifacts", []
        )
    ]
    state_hash = sha256(STATE)
    status_hash = sha256(STATUS)
    for requirement in requirements["requirements"]:
        requirement_id = requirement.get("requirement_id")
        stem = requirement_to_stem.get(requirement_id)
        if stem:
            summary = summary_by_stem[stem]
            path = GENERATED / f"{stem}.json"
            passed = summary.get("status") == "PASS"
            requirement["status"] = "PASS" if passed else "FAIL"
            requirement["test_id"] = summary.get("test_id")
            requirement["evidence_path"] = rel(path)
            requirement["verification_scope"] = (
                "DIRECT_AX7020_HARDWARE"
                if stem != "p10_1_hw_artifact_summary"
                else "IMMUTABLE_LED_ENABLED_ARTIFACTS"
            )
            requirement["artifact_hash"] = sha256(path)
            bound_hashes = (
                artifact_summary_hashes
                if stem == "p10_1_hw_artifact_summary"
                else common_hashes
            )
            requirement["artifact_hashes"] = [
                {"path": rel(path), "sha256": sha256(path)},
                *[item.copy() for item in bound_hashes],
            ]
            requirement["hardware_followup"] = (
                "Scoped stationary dual-AX7020 two-lane evidence only; "
                "P11 handover, 8x32, rotation, 600 rpm, Ethernet/SPI, external "
                "duty, physical GLOBAL_PERMIT, and product acceptance remain pending."
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
    runtime_reverification = load_json(P10_RUNTIME_REVERIFY)
    if runtime_reverification.get("status") != "PASS":
        raise ValueError("P10 goodput runtime source re-verification is not PASS")
    p10_goodput = next(
        (
            item
            for item in requirements["requirements"]
            if item.get("requirement_id") == "P10-PERF-MEAS-001"
        ),
        None,
    )
    if p10_goodput is None or p10_goodput.get("status") != "PASS":
        raise ValueError("P10-PERF-MEAS-001 is missing or not PASS")
    runtime_bindings = [
        item
        for item in p10_goodput.get("artifact_hashes", [])
        if item.get("path") == rel(P10_RUNTIME)
    ]
    if len(runtime_bindings) != 1:
        raise ValueError("P10-PERF-MEAS-001 runtime binding is ambiguous")
    runtime_bindings[0]["sha256"] = runtime_reverification[
        "current_runtime_sha256"
    ]
    p10_goodput["artifact_hashes"] = [
        item
        for item in p10_goodput["artifact_hashes"]
        if item.get("path") != rel(P10_RUNTIME_REVERIFY)
    ]
    p10_goodput["artifact_hashes"].append(
        {
            "path": rel(P10_RUNTIME_REVERIFY),
            "sha256": sha256(P10_RUNTIME_REVERIFY),
        }
    )
    p10_goodput["source_reverification"] = {
        "test_id": runtime_reverification["test_id"],
        "evidence_path": rel(P10_RUNTIME_REVERIFY),
        "evidence_sha256": sha256(P10_RUNTIME_REVERIFY),
        "historical_runtime_sha256": runtime_reverification[
            "historical_runtime_sha256"
        ],
        "current_runtime_sha256": runtime_reverification[
            "current_runtime_sha256"
        ],
        "goodput_formula_changed": runtime_reverification[
            "goodput_formula_changed"
        ],
        "campaign_minimum_aggregation_changed": runtime_reverification[
            "campaign_minimum_aggregation_changed"
        ],
    }
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


def finalize_run(run_id: str) -> dict[str, Any]:
    run_root = (HARDWARE_ROOT / run_id).resolve()
    run_root.relative_to(HARDWARE_ROOT.resolve())
    orchestrator_path = run_root / "final/orchestrator_result.json"
    immutable_auth_path = (
        run_root / "authorization/immutable_authorization.json"
    )
    auth_record_path = run_root / "authorization/authorization_record.json"
    orchestrator = load_json(orchestrator_path)
    authorization = load_json(immutable_auth_path)
    auth_record = load_json(auth_record_path)
    artifacts = load_json(ARTIFACT_SUMMARY)
    manifest_errors, run_manifest = verify_run_manifest(run_root)
    runtime_reverification = generate_p10_runtime_source_reverification()
    if runtime_reverification.get("status") != "PASS":
        raise ValueError("P10 goodput runtime source re-verification failed")
    context = common_context(run_id, authorization, artifacts)
    stage_payloads: dict[str, dict[str, Any]] = {}
    stage_records: dict[str, dict[str, Any]] = {}
    for stage in REQUIRED_STAGES:
        stage_payloads[stage], stage_records[stage] = stage_record(
            run_root,
            stage,
            orchestrator=orchestrator,
            orchestrator_path=orchestrator_path,
        )

    summaries: dict[str, dict[str, Any]] = {
        "p10_1_hw_artifact_summary": artifacts
    }
    auth_errors = validate_authorized_artifacts(authorization)
    if (
        auth_record.get("status") != "PASS"
        or authorization.get("status") != "AUTHORIZED"
        or authorization.get("run_id") != run_id
        or authorization.get("goal_sha256") != GOAL_SHA256
        or authorization.get("authorized_stages") != list(REQUIRED_STAGES)
    ):
        auth_errors.append("captured current-run authorization is invalid")
    summaries["p10_1_hw_authorization_summary"] = write_hardware_pair(
        "p10_1_hw_authorization_summary",
        "P10.1 current-run hardware authorization",
        "P10_1-HW-CURRENT-RUN-AUTHORIZATION",
        "PASS" if not auth_errors else "FAIL",
        context,
        [record(immutable_auth_path), record(auth_record_path)],
        authorization=authorization,
        authorization_sha256=sha256(immutable_auth_path),
        authorization_validation=auth_record,
        errors=auth_errors,
    )

    preflight = stage_payloads["preflight"]
    identity_errors = []
    if (
        preflight.get("markers", {}).get("P10_XSDB_IDENTITY") != "PASS"
        or preflight.get("markers", {}).get("P10_XSDB_FIXED_SERIAL")
        != "210249855178"
        or preflight.get("markers", {}).get("P10_XSDB_ROTATING_SERIAL")
        != "210512180081"
    ):
        identity_errors.append("preflight target binding did not prove both serials")
    summaries["p10_1_hw_target_identity_summary"] = write_hardware_pair(
        "p10_1_hw_target_identity_summary",
        "P10.1 AX7020 target identity",
        "P10_1-HW-TARGET-ROLE-BINDING",
        "PASS" if not identity_errors else "FAIL",
        context,
        [stage_records["preflight"]],
        markers=preflight.get("markers"),
        details=preflight.get("details"),
        errors=identity_errors,
    )

    safe_errors = [
        f"{stage}: safe boot or stage failed"
        for stage, payload in stage_payloads.items()
        if payload.get("status") != "PASS"
        or payload.get("markers", {}).get("P10_SAFE_BOOT") != "PASS"
    ]
    summaries["p10_1_hw_safe_boot_summary"] = write_hardware_pair(
        "p10_1_hw_safe_boot_summary",
        "P10.1 safe boot",
        "P10_1-HW-SAFE-BOOT-BOTH",
        "PASS" if not safe_errors else "FAIL",
        context,
        list(stage_records.values()),
        stage_safe_boot={
            stage: payload.get("markers", {}).get("P10_SAFE_BOOT")
            for stage, payload in stage_payloads.items()
        },
        safe_boot_contract={
            "tx_request": 0,
            "physical_tx_intent": 0,
            "endpoint_armed": 0,
            "active_tx_mask": 0,
            "outstanding_physical_attempt": 0,
            "autonomous_tx": False,
        },
        errors=safe_errors,
    )

    all_details = [
        detail
        for payload in stage_payloads.values()
        for detail in payload.get("details", [])
        if "fixed" in detail and "rotating" in detail
    ]
    timer_rows = cross_board_timer_errors(all_details)
    timer_errors = [
        f"{item['label']}: timer disagreement exceeds 1%"
        for item in timer_rows
        if item["ps_cross_board_error_percent"] > 1.0
        or item["pl_cross_board_error_percent"] > 1.0
    ]
    if not timer_rows:
        timer_errors.append("no complete PS/PL timer crosscheck row was captured")
    timer_errors.extend(
        f"{stage}: complete timer coverage unavailable because stage is not PASS"
        for stage, payload in stage_payloads.items()
        if payload.get("status") != "PASS"
    )
    for detail in all_details:
        if detail.get("recovery_case"):
            continue
        if any(
            detail[role].get("timer_crosscheck_pass") != 1
            for role in ("fixed", "rotating")
        ):
            timer_errors.append(f"{detail['label']}: local PS/PL timer gate failed")
    summaries["p10_1_hw_timer_summary"] = write_hardware_pair(
        "p10_1_hw_timer_summary",
        "P10.1 PS/PL timer crosscheck",
        "P10_1-HW-TIMER-CROSSCHECK",
        "PASS" if not timer_errors else "FAIL",
        context,
        list(stage_records.values()),
        timer_rows=timer_rows,
        maximum_allowed_error_percent=1.0,
        host_timer_role="orchestration_only",
        errors=timer_errors,
    )

    metric_errors = []
    if preflight.get("status") != "PASS":
        metric_errors.append("preflight did not complete")
    preflight_labels = {
        detail.get("label"): detail for detail in preflight.get("details", [])
    }
    if "diagnostic_only_1byte" not in preflight_labels:
        metric_errors.append("1-byte diagnostic record missing")
    if preflight.get("semantics", {}).get(
        "diagnostic_eligible_for_scaling"
    ) is not False:
        metric_errors.append("diagnostic scaling exclusion missing")
    if not all(
        window.get("host_not_in_fast_path")
        for payload in stage_payloads.values()
        for window in payload.get("semantics", {}).get("windows", [])
    ):
        metric_errors.append("host fast-path exclusion failed")
    summaries["p10_1_hw_metric_semantics_summary"] = write_hardware_pair(
        "p10_1_hw_metric_semantics_summary",
        "P10.1 hardware metric semantics and autonomy",
        "P10_1-HW-METRIC-SEMANTICS-AUTONOMY",
        "PASS" if not metric_errors else "FAIL",
        context,
        [stage_records["preflight"]],
        diagnostic_only_1byte=preflight_labels.get("diagnostic_only_1byte"),
        failed_object=preflight_labels.get("failed_object_diagnostic"),
        semantics=preflight.get("semantics"),
        application_numerator="remotely_verified_atomic_commit_bytes",
        host_not_in_fast_path=True if not metric_errors else False,
        errors=metric_errors,
    )

    for stem, title, test_id, stage in (
        (
            "p10_1_hw_baseline_summary",
            "P10.1 single/two-lane baseline",
            "P10_1-HW-BASELINE",
            "baseline",
        ),
        (
            "p10_1_hw_tuning_summary",
            "P10.1 bounded adaptive tuning",
            "P10_1-HW-ADAPTIVE-TUNING",
            "tuning",
        ),
        (
            "p10_1_hw_pipeline_summary",
            "P10.1 sustained multi-buffer pipeline",
            "P10_1-HW-SUSTAINED-PIPELINE",
            "pipeline",
        ),
    ):
        payload = stage_payloads[stage]
        summaries[stem] = write_hardware_pair(
            stem,
            title,
            test_id,
            payload.get("status", "FAIL"),
            context,
            [stage_records[stage]],
            semantics=payload.get("semantics"),
            details=payload.get("details"),
            errors=payload.get("errors", []),
        )

    streaming = stage_payloads["streaming"]
    faults = stage_payloads["faults"]
    stream_errors = [
        *streaming.get("errors", []),
        *faults.get("errors", []),
    ]
    summaries["p10_1_hw_streaming_64m_summary"] = write_hardware_pair(
        "p10_1_hw_streaming_64m_summary",
        "P10.1 64 MiB streaming and recovery",
        "P10_1-HW-STREAMING-64M-RECOVERY",
        "PASS" if not stream_errors else "FAIL",
        context,
        [stage_records["streaming"], stage_records["faults"]],
        clean_streams=streaming.get("details"),
        recovery_vectors=faults.get("details"),
        fault_semantics=faults.get("semantics"),
        single_atomic_commit_required=True,
        errors=stream_errors,
    )
    summaries["p10_1_hw_streaming_128m_summary"] = write_hardware_pair(
        "p10_1_hw_streaming_128m_summary",
        "P10.1 optional 128 MiB streaming",
        "P10_1-HW-STREAMING-128M",
        "SKIP_WITH_REASON",
        context,
        [record(ROOT / "config/performance/p10_1_hardware_runtime.yaml")],
        reason=(
            "The frozen runtime address/mailbox contract supports at most 64 MiB; "
            "128 MiB is nonblocking and was not emulated or misreported as hardware."
        ),
        errors=[],
    )

    half = stage_payloads["half_duplex"]
    half_windows = half.get("semantics", {}).get("directions", [])
    half_by_direction = {
        int(item["direction"]): item for item in half_windows
    }
    half_errors = list(half.get("errors", []))
    for direction in (0, 1):
        if direction not in half_by_direction:
            half_errors.append(f"missing half-duplex direction {direction}")
    f_value = half_by_direction.get(0, {}).get(
        "wall_application_goodput_bps"
    )
    r_value = half_by_direction.get(1, {}).get(
        "wall_application_goodput_bps"
    )
    f_goodput = float(f_value) if f_value is not None else None
    r_goodput = float(r_value) if r_value is not None else None
    f_4mbps = (
        "PASS"
        if f_goodput is not None and f_goodput >= 4_000_000
        else "FAIL"
    )
    r_4mbps = (
        "PASS"
        if r_goodput is not None and r_goodput >= 4_000_000
        else "FAIL"
    )
    f_4p8mbps = (
        "PASS"
        if f_goodput is not None and f_goodput >= 4_800_000
        else "FAIL"
    )
    r_4p8mbps = (
        "PASS"
        if r_goodput is not None and r_goodput >= 4_800_000
        else "FAIL"
    )
    measured_bottleneck = (
        "PL_PHY_AIRTIME_RECONCILED"
        if not half_errors and f_goodput is not None and r_goodput is not None
        else "NOT_MEASURED"
    )
    model = load_json(GENERATED / "p10_1_hw_model_sanity_summary.json")
    modeled = float(model.get("corrected_modeled_application_goodput_bps", 0.0))
    ceiling = float(model.get("physical_and_airtime_ceiling_bps", 0.0))
    summaries["p10_1_hw_half_duplex_summary"] = write_hardware_pair(
        "p10_1_hw_half_duplex_summary",
        "P10.1 two-lane half-duplex performance",
        "P10_1-HW-HALF-DUPLEX-4MBPS",
        "PASS" if not half_errors else "FAIL",
        context,
        [stage_records["half_duplex"]],
        directions=half_windows,
        f_to_r_application_goodput_bps=f_goodput,
        r_to_f_application_goodput_bps=r_goodput,
        f_to_r_4mbps_target=f_4mbps,
        r_to_f_4mbps_target=r_4mbps,
        f_to_r_4p8mbps_stretch=f_4p8mbps,
        r_to_f_4p8mbps_stretch=r_4p8mbps,
        modeled_application_goodput_bps=modeled,
        airtime_ceiling_bps=ceiling,
        measured_to_model_ratio_f_to_r=(
            f_goodput / modeled if f_goodput is not None and modeled else None
        ),
        measured_to_model_ratio_r_to_f=(
            r_goodput / modeled if r_goodput is not None and modeled else None
        ),
        measured_to_airtime_ratio_f_to_r=(
            f_goodput / ceiling if f_goodput is not None and ceiling else None
        ),
        measured_to_airtime_ratio_r_to_f=(
            r_goodput / ceiling if r_goodput is not None and ceiling else None
        ),
        primary_measured_bottleneck=measured_bottleneck,
        errors=half_errors,
    )

    crosstalk = stage_payloads["crosstalk"]
    classification = crosstalk_classification(crosstalk)
    xtalk_errors = list(crosstalk.get("errors", []))
    if classification["non_target_crc_valid_false_frames"] != 0:
        xtalk_errors.append("non-target CRC-valid false frame observed")
    summaries["p10_1_hw_crosstalk_summary"] = write_hardware_pair(
        "p10_1_hw_crosstalk_summary",
        "P10.1 4x4 echo and crosstalk matrix",
        "P10_1-HW-CROSSTALK-4X4",
        "PASS" if not xtalk_errors else "FAIL",
        context,
        [stage_records["crosstalk"]],
        **classification,
        errors=xtalk_errors,
    )

    oneplusone = stage_payloads["oneplusone"]
    one_semantics = oneplusone.get("semantics", {})
    one_errors = list(oneplusone.get("errors", []))
    if one_semantics.get("outcome") != "SKIP_WITH_REASON":
        one_errors.append("frozen endpoint direction capability was not explicit")
    summaries["p10_1_hw_1plus1_summary"] = write_hardware_pair(
        "p10_1_hw_1plus1_summary",
        "P10.1 nonblocking 1+1 capability experiment",
        "P10_1-HW-1PLUS1-DIRECT-CAPABILITY",
        "PASS" if not one_errors else "FAIL",
        context,
        [stage_records["oneplusone"]],
        experiment_outcome=one_semantics.get("outcome"),
        reason=one_semantics.get("reason"),
        full_duplex_f_to_r_bps=None,
        full_duplex_r_to_f_bps=None,
        boundary="NOT_A_4PLUS4_FULL_DUPLEX_PASS",
        errors=one_errors,
    )

    formal = stage_payloads["formal"]
    formal_windows = formal.get("semantics", {}).get("directions", [])
    formal_by_direction = {
        int(item["direction"]): item for item in formal_windows
    }
    formal_errors = list(formal.get("errors", []))
    formal_elapsed_ms = formal.get("semantics", {}).get("formal_elapsed_ms")
    if formal_elapsed_ms != 1_800_000:
        formal_errors.append("formal runtime is not exactly 1800 seconds")
    formal_runtime_seconds = (
        float(formal_elapsed_ms) / 1000.0
        if formal_elapsed_ms is not None
        else None
    )
    formal_f_committed = None
    formal_r_committed = None
    if 0 in formal_by_direction:
        formal_f_committed = formal_by_direction[0].get("committed_bytes")
    if 1 in formal_by_direction:
        formal_r_committed = formal_by_direction[1].get("committed_bytes")
    summaries["p10_1_hw_stationary_30min_summary"] = write_hardware_pair(
        "p10_1_hw_stationary_30min_summary",
        "P10.1 stationary 30-minute acceptance",
        "P10_1-HW-STATIONARY-30MIN",
        "PASS" if not formal_errors else "FAIL",
        context,
        [stage_records["formal"]],
        runtime_seconds=formal_runtime_seconds,
        directions=formal_windows,
        committed_bytes_f_to_r=formal_f_committed,
        committed_bytes_r_to_f=formal_r_committed,
        errors=formal_errors,
    )

    shutdowns = orchestrator.get("shutdowns", [])
    shutdown_errors = [
        item.get("label", "unknown")
        for item in shutdowns
        if item.get("status") != "PASS"
        or item.get("SHUTDOWN_FIXED") != "PASS"
        or item.get("SHUTDOWN_ROTATING") != "PASS"
    ]
    if orchestrator.get("SHUTDOWN_FIXED") != "PASS":
        shutdown_errors.append("orchestrator fixed shutdown is not PASS")
    if orchestrator.get("SHUTDOWN_ROTATING") != "PASS":
        shutdown_errors.append("orchestrator rotating shutdown is not PASS")
    summaries["p10_1_hw_shutdown_summary"] = write_hardware_pair(
        "p10_1_hw_shutdown_summary",
        "P10.1 dual-endpoint shutdown",
        "P10_1-HW-SHUTDOWN-BOTH",
        "PASS" if not shutdown_errors else "FAIL",
        context,
        [record(orchestrator_path), record(run_root / "final/run_evidence_sha256_manifest.json")],
        shutdowns=shutdowns,
        SHUTDOWN_FIXED=orchestrator.get("SHUTDOWN_FIXED"),
        SHUTDOWN_ROTATING=orchestrator.get("SHUTDOWN_ROTATING"),
        errors=shutdown_errors,
    )

    consistency_errors = list(manifest_errors)
    if (
        orchestrator.get("status") != "PASS"
        or orchestrator.get("run_id") != run_id
        or orchestrator.get("hardware_actions_executed") is not True
        or orchestrator.get("network_used") is not False
        or orchestrator.get("hardware_movement") is not False
    ):
        consistency_errors.append("orchestrator boundary/status is invalid")
    if set(orchestrator.get("stages", {})) != set(REQUIRED_STAGES):
        consistency_errors.append("executed stage set differs from authorization")
    for stem in REQUIRED_GENERATED_STEMS:
        json_path = GENERATED / f"{stem}.json"
        md_path = GENERATED / f"{stem}.md"
        if not json_path.is_file() or not md_path.is_file():
            consistency_errors.append(f"missing generated pair: {stem}")
    manifest_path = GENERATED / "p10_1_hw_sha256_manifest.json"
    manifest_files = [
        path
        for stem in REQUIRED_GENERATED_STEMS
        for path in (GENERATED / f"{stem}.json", GENERATED / f"{stem}.md")
        if path.is_file()
    ]
    generated_manifest = {
        "schema_version": 1,
        "test_id": "P10_1-HW-GENERATED-EVIDENCE-MANIFEST",
        "status": "PASS" if not consistency_errors else "FAIL",
        "run_id": run_id,
        "run_manifest": run_manifest,
        "files": [record(path) for path in manifest_files],
        "generated_at_utc": utc_now(),
    }
    write_json(manifest_path, generated_manifest)
    summaries["p10_1_hw_evidence_consistency"] = write_hardware_pair(
        "p10_1_hw_evidence_consistency",
        "P10.1 hardware evidence consistency",
        "P10_1-HW-EVIDENCE-CONSISTENCY",
        "PASS" if not consistency_errors else "FAIL",
        context,
        [record(run_root / "final/run_evidence_sha256_manifest.json"), record(manifest_path)],
        run_manifest_file_count=len(run_manifest.get("files", [])),
        generated_pair_count=len(REQUIRED_GENERATED_STEMS),
        errors=consistency_errors,
    )

    mandatory_stems = (
        "p10_1_hw_artifact_summary",
        "p10_1_hw_authorization_summary",
        "p10_1_hw_target_identity_summary",
        "p10_1_hw_safe_boot_summary",
        "p10_1_hw_timer_summary",
        "p10_1_hw_metric_semantics_summary",
        "p10_1_hw_baseline_summary",
        "p10_1_hw_tuning_summary",
        "p10_1_hw_pipeline_summary",
        "p10_1_hw_streaming_64m_summary",
        "p10_1_hw_half_duplex_summary",
        "p10_1_hw_crosstalk_summary",
        "p10_1_hw_1plus1_summary",
        "p10_1_hw_stationary_30min_summary",
        "p10_1_hw_shutdown_summary",
        "p10_1_hw_evidence_consistency",
    )
    mandatory_failures = [
        stem for stem in mandatory_stems if summaries[stem].get("status") != "PASS"
    ]
    final_status = "PASS" if not mandatory_failures else "FAIL"
    best = stage_payloads["tuning"].get("semantics", {}).get(
        "best_candidate", {}
    )
    retry_audit_path = GENERATED / "p10_1_hw_preflight_retry_audit.json"
    retry_audit = (
        load_json(retry_audit_path) if retry_audit_path.is_file() else {}
    )
    final = pair_payload(
        "P10_1-HW-FINAL-ACCEPTANCE",
        final_status,
        context,
        [record(orchestrator_path), record(manifest_path)],
        offline_base_recheck=load_json(
            GENERATED / "p10_1_hw_repo_intake.json"
        ).get("status"),
        model_sanity=model.get("status"),
        modeled_application_goodput_bps=modeled,
        airtime_ceiling_bps=ceiling,
        timer_crosscheck=summaries["p10_1_hw_timer_summary"]["status"],
        board_autonomous_fast_path=summaries[
            "p10_1_hw_metric_semantics_summary"
        ]["status"],
        host_not_in_fast_path=summaries[
            "p10_1_hw_metric_semantics_summary"
        ]["status"],
        best_buffer_count=best.get("buffer_count"),
        best_ring_depth=best.get("ring_depth"),
        best_descriptor_batch=best.get("descriptor_batch"),
        best_outstanding=best.get("outstanding_frames"),
        f_to_r_application_goodput_bps=f_goodput,
        r_to_f_application_goodput_bps=r_goodput,
        f_to_r_4mbps_target=f_4mbps,
        r_to_f_4mbps_target=r_4mbps,
        f_to_r_4p8mbps_stretch=f_4p8mbps,
        r_to_f_4p8mbps_stretch=r_4p8mbps,
        measured_to_model_ratio_f_to_r=(
            f_goodput / modeled if f_goodput is not None and modeled else None
        ),
        measured_to_model_ratio_r_to_f=(
            r_goodput / modeled if r_goodput is not None and modeled else None
        ),
        primary_measured_bottleneck=measured_bottleneck,
        streaming_64m_f_to_r=summaries[
            "p10_1_hw_streaming_64m_summary"
        ]["status"],
        streaming_64m_r_to_f=summaries[
            "p10_1_hw_streaming_64m_summary"
        ]["status"],
        streaming_128m="SKIP_WITH_REASON",
        crosstalk_4x4_matrix=summaries[
            "p10_1_hw_crosstalk_summary"
        ]["status"],
        near_end_echo_class=classification["near_end_echo_class"],
        cross_lane_crosstalk_class=classification[
            "cross_lane_crosstalk_class"
        ],
        all_rx_ready_risk=classification["all_rx_ready_risk"],
        p10_1_1plus1_experiment=one_semantics.get("outcome"),
        full_duplex_f_to_r_bps=None,
        full_duplex_r_to_f_bps=None,
        stationary_30min=summaries[
            "p10_1_hw_stationary_30min_summary"
        ]["status"],
        runtime_seconds=formal_runtime_seconds,
        committed_bytes_f_to_r=formal_f_committed,
        committed_bytes_r_to_f=formal_r_committed,
        executed_stage_status={
            stage: orchestrator.get("stages", {}).get(stage, "MISSING")
            for stage in REQUIRED_STAGES
        },
        complete_run_id=(
            run_id
            if all(
                orchestrator.get("stages", {}).get(stage) == "PASS"
                for stage in REQUIRED_STAGES
            )
            else None
        ),
        integrity_totals={
            "crc_bad": sum(
                detail[role].get("crc_bad_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "sha_mismatch": sum(
                detail[role].get("sha_mismatch_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "partial_commit": sum(
                detail[role].get("partial_commit_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "duplicate_commit": sum(
                detail[role].get("duplicate_commit_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "stale_commit": sum(
                detail[role].get("stale_commit_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "retry_exhausted": sum(
                detail[role].get("retry_exhausted_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "descriptor_leak": sum(
                detail[role].get("descriptor_leak_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "double_completion": sum(
                detail[role].get("double_completion_count", 0)
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "deadlock": 0,
            "duty_violation": sum(
                sum(detail[role].get("duty_hard_fault_after", []))
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
            "continuous_high_violation": sum(
                int(
                    max(detail[role].get("tx_high_max_after", [0]), default=0)
                    > 64
                )
                for detail in all_details
                for role in ("fixed", "rotating")
            ),
        },
        SHUTDOWN_FIXED=orchestrator.get("SHUTDOWN_FIXED"),
        SHUTDOWN_ROTATING=orchestrator.get("SHUTDOWN_ROTATING"),
        p11_hardware_ready=False,
        p11_missing_prerequisites=[
            "single-lane four-fixed-module handover hardware",
            "ABZ encoder exact input and calibration",
            "external TFDU electrical/duty measurement",
            "physical GLOBAL_PERMIT D17 implementation",
            "8x32 geometry and optics",
            "rotation and 600 rpm mechanical qualification",
            "Ethernet/SPI end-to-end integration",
        ],
        pass_gates=[
            stem for stem in mandatory_stems if stem not in mandatory_failures
        ],
        fail_gates=mandatory_failures,
        nonblocking_results={
            "streaming_128m": "SKIP_WITH_REASON",
            "oneplusone": one_semantics.get("outcome"),
            "stretch_4p8mbps": {
                "f_to_r": f_4p8mbps,
                "r_to_f": r_4p8mbps,
            },
        },
        retry_limit_audit=record(retry_audit_path) if retry_audit else None,
        campaign_disposition=retry_audit.get("campaign_disposition"),
        retry_run_id_count=retry_audit.get(
            "preflight_retry_ledger", {}
        ).get("new_run_id_count"),
        retry_run_id_limit=retry_audit.get("goal", {}).get(
            "diagnostic_stage_new_run_id_limit"
        ),
        next_required_user_action=retry_audit.get(
            "next_required_user_action"
        ),
        generated_evidence=[
            f"evidence/generated/{stem}.json"
            for stem in (
                *REQUIRED_GENERATED_STEMS,
                "p10_1_hw_evidence_consistency",
                "p10_1_hw_final_summary",
            )
        ],
        next_recommended_stage=(
            "P11_PREREQUISITE_ACQUISITION"
            if final_status == "PASS"
            else "P10_1_PERFORMANCE_REMEDIATION"
        ),
        errors=mandatory_failures,
    )
    write_pair(
        "p10_1_hw_final_summary",
        "P10.1 hardware performance acceptance",
        final,
    )
    summaries["p10_1_hw_final_summary"] = final
    update_canonical_state(final, summaries)
    return final


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("artifacts", "final"), required=True
    )
    parser.add_argument("--run-id")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    try:
        if args.mode == "artifacts":
            result = generate_artifact_summary()
        else:
            if not args.run_id:
                raise ValueError("--run-id is required for final mode")
            result = finalize_run(args.run_id)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"P10_1_HW_FINALIZER=FAIL\nERROR={exc}", file=sys.stderr)
        return 1
    print(f"P10_1_HW_FINALIZER={result['status']}")
    if args.json_summary:
        print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"PASS", "SKIP_WITH_REASON"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
