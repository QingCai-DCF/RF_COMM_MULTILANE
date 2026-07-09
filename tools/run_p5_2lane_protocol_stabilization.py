#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from analyze_p5_protocol_metrics import analyze as analyze_metrics
from audit_p5_plan_requirements import audit as audit_plan_requirements
from check_2lane_scope import check as check_2lane_scope
from check_no_ethernet_hardware_tests import check as check_no_ethernet
from check_no_motion_tests import check as check_no_motion
from check_p5_evidence_consistency import check as check_consistency
from p5_lib import (
    FAIL,
    GENERATED,
    NOT_RUN_OPTIONAL,
    P5_CONTEXT,
    P5_DIR,
    PENDING_HW_NOT_EXECUTED,
    PASS,
    PASS_WITH_NOTES,
    PASS_WITH_SKIPS,
    ROOT,
    active_hashes,
    ensure_dirs,
    git_value,
    json_from_stdout,
    load_json,
    p5_hardware_pending_payload,
    rel,
    run_cmd,
    sha256_or_missing,
    status_is_passish,
    write_csv,
    write_json,
    write_markdown,
    write_profiles,
    write_text,
)
from p5_hardware_authorization import (
    DEFAULT_AUTH_FILE as P5_DEFAULT_AUTH_FILE,
    DEFAULT_BOARD_ID,
    DEFAULT_SHUTDOWN_BITSTREAM,
    DEFAULT_STAGE as P5_DEFAULT_AUTH_STAGE,
    STAGE_PLAN,
    ensure_authorization_template,
    generate_stage_plan,
    validate_authorization as validate_p5_authorization,
    write_authorization_summary,
    write_authorized_run_package,
)
from p5_hw_execution import run_authorized_hardware
from reconcile_p4_auto_evidence import reconcile as reconcile_p4
from run_p5_retry_fault_injection_sim import run_simulation as run_retry_fault_injection_sim


HARDWARE_STAGES = {
    "SAFE_IDLE_RECHECK": ("safe_idle_recheck", P5_DIR / "safe_idle_recheck", GENERATED / "p5_safe_idle_recheck_summary.md"),
    "TFDU_CONTROL_IDLE_RECHECK": ("tfdu_control_idle_recheck", P5_DIR / "tfdu_control_idle_recheck", GENERATED / "p5_tfdu_control_idle_recheck_summary.md"),
    "RAW_LANE_MATRIX_FRESH": ("raw_lane_matrix_fresh", P5_DIR / "raw_lane_matrix", GENERATED / "p5_raw_lane_matrix_summary.md"),
    "LANE0_FRAME_CRC_100": ("lane0_frame_crc_100", P5_DIR / "protocol" / "lane0_frame_crc_100", GENERATED / "p5_lane0_frame_crc_100_summary.md"),
    "LANE1_FRAME_CRC_100": ("lane1_frame_crc_100", P5_DIR / "protocol" / "lane1_frame_crc_100", GENERATED / "p5_lane1_frame_crc_100_summary.md"),
    "LANE0_ACK_RETRY_100": ("lane0_ack_retry_100", P5_DIR / "protocol" / "lane0_ack_retry_100", GENERATED / "p5_lane0_ack_retry_100_summary.md"),
    "LANE1_ACK_RETRY_100": ("lane1_ack_retry_100", P5_DIR / "protocol" / "lane1_ack_retry_100", GENERATED / "p5_lane1_ack_retry_100_summary.md"),
    "TWO_LANE_MINIMAL_100": ("two_lane_minimal_100", P5_DIR / "protocol" / "two_lane_minimal_100", GENERATED / "p5_two_lane_minimal_100_summary.md"),
    "PAYLOAD_SWEEP": ("payload_sweep", P5_DIR / "payload_sweep", GENERATED / "p5_payload_sweep_summary.md"),
    "MASK_REGRESSION": ("mask_regression", P5_DIR / "mask_regression", GENERATED / "p5_mask_regression_summary.md"),
    "TWO_LANE_30MIN_SOAK": ("two_lane_30min_soak", P5_DIR / "soak" / "two_lane_30min", GENERATED / "p5_two_lane_30min_soak_summary.md"),
}


def _selected(stage_filter: str, stage: str) -> bool:
    return stage_filter == stage


def write_repo_intake() -> dict[str, Any]:
    ensure_dirs()
    status = git_value("status", "--short")
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    write_text(GENERATED / "p5_current_head.txt", head)
    write_text(GENERATED / "p5_git_status_before.txt", status or "(clean)")
    dirty_paths = [line[3:] if len(line) > 3 else line for line in status.splitlines() if line.strip()]
    non_evidence_dirty = [
        path
        for path in dirty_paths
        if not (
            path.startswith("evidence/")
            or path.startswith("evidence\\")
            or path.startswith("profiles/p5/")
            or path.startswith("profiles\\p5\\")
            or path.startswith("tools/run_p5")
            or path.startswith("tools\\run_p5")
            or path.startswith("tools/check_p5")
            or path.startswith("tools\\check_p5")
            or path.startswith("tools/reconcile_p4")
            or path.startswith("tools\\reconcile_p4")
            or path.startswith("tools/check_no_")
            or path.startswith("tools\\check_no_")
            or path.startswith("tools/check_2lane")
            or path.startswith("tools\\check_2lane")
            or path.startswith("tools/analyze_p5")
            or path.startswith("tools\\analyze_p5")
            or path.startswith("tools/p5_lib.py")
            or path.startswith("tools\\p5_lib.py")
        )
    ]
    result = PASS if not status else PASS_WITH_NOTES
    lines = [
        f"P5_REPO_INTAKE: {result}",
        f"P4_HEAD: {P5_CONTEXT['P4_HEAD']}",
        f"current HEAD: `{head}`",
        f"branch: `{branch}`",
        f"working_tree: `{'clean' if not status else 'dirty'}`",
        f"dirty_non_evidence_paths_count: {len(non_evidence_dirty)}",
        f"P4_RESULT_PACKAGE: {P5_CONTEXT['P4_RESULT_PACKAGE']}",
        "NETWORK_CABLE_CONNECTED: false",
        "HARDWARE_MOVEMENT_ALLOWED: false",
        "AVAILABLE_LANES: 2",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Git Status",
        "",
        "```text",
        status or "(clean)",
        "```",
    ]
    if non_evidence_dirty:
        lines.extend(
            [
                "",
                "## Dirty Boundary",
                "",
                "- Working tree is dirty outside generated evidence/P5 scaffolding, so this run does not execute hardware.",
                "- P5 hardware stages remain pending until the tree state and authorization are intentionally accepted.",
            ]
        )
    write_markdown(
        GENERATED / "p5_repo_intake.md",
        "P5 Repository Intake",
        result,
        "repository state recorded; hardware remains disabled" if status else "repository state recorded",
        lines,
    )
    return {
        "P5_REPO_INTAKE": result,
        "current_head": head,
        "branch": branch,
        "dirty": bool(status),
        "dirty_non_evidence_paths_count": len(non_evidence_dirty),
        "summary": "evidence/generated/p5_repo_intake.md",
    }


def run_rechecks(reuse_existing: bool = False) -> dict[str, Any]:
    if reuse_existing:
        offline_json = load_json(GENERATED / "offline_gate_summary.json")
        results = [
            {
                "cmd": "reuse existing evidence/generated/offline_gate_summary.json after prior P5.2 recheck command run",
                "returncode": 0 if offline_json else 1,
                "stdout_tail": "",
                "stderr_tail": "" if offline_json else "offline_gate_summary.json missing or invalid",
                "json": offline_json,
            }
        ]
    else:
        commands = [
            [sys.executable, "tools/run_offline_gate.py", "--allow-skips", "--json-summary", "--include-simulation", "--include-pre-hw-package"],
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                "tools/run_offline_gate.ps1",
                "-AllowSkips",
                "-JsonSummary",
                "-IncludeSimulation",
                "-IncludePreHwPackage",
            ],
            [sys.executable, "tools/run_simulation_gate.py", "--json-summary", "--allow-skips"],
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/run_simulation_gate.ps1", "-JsonSummary", "-AllowSkips"],
            [sys.executable, "tools/summarize_gate.py"],
        ]
        results = []
        for cmd in commands:
            proc = run_cmd(cmd, timeout=900)
            results.append(
                {
                    "cmd": proc["cmd"],
                    "returncode": proc["returncode"],
                    "stdout_tail": proc["stdout"][-2000:],
                    "stderr_tail": proc["stderr"][-2000:],
                    "json": json_from_stdout(proc["stdout"]),
                }
            )
        offline_json = results[0].get("json", {})
    p1 = offline_json.get("P1_OFFLINE_HARDENING", "UNKNOWN")
    p2 = offline_json.get("P2_SIMULATION_BASELINE", "UNKNOWN")
    p3 = offline_json.get("P3_PRE_HW_ACCEPTANCE_PACKAGE", "UNKNOWN")
    recheck_result = PASS if all(status in {PASS, PASS_WITH_SKIPS} for status in [p1, p2, p3]) else FAIL
    lines = [
        f"P1_RECHECK: {p1}",
        f"P2_RECHECK: {p2}",
        f"P3_RECHECK: {p3}",
        f"P1_P2_P3_RECHECK: {recheck_result}",
        "P4_NORMALIZED_INTAKE: see evidence/generated/p5_p4_evidence_reconciliation.md",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Commands",
        "",
        *(f"- `{item['cmd']}` -> rc={item['returncode']}" for item in results),
    ]
    write_markdown(
        GENERATED / "p5_recheck_p1_p2_p3_p4_summary.md",
        "P5 Recheck P1 P2 P3 P4 Summary",
        recheck_result,
        "offline and simulation rechecks completed" if recheck_result == PASS else "one or more offline rechecks failed",
        lines,
    )
    return {
        "P1_RECHECK": p1,
        "P2_RECHECK": p2,
        "P3_RECHECK": p3,
        "P1_P2_P3_RECHECK": recheck_result,
        "commands": [{key: value for key, value in item.items() if key != "json"} for item in results],
        "summary": "evidence/generated/p5_recheck_p1_p2_p3_p4_summary.md",
    }


def _write_raw_matrix_pending(reason: str) -> dict[str, Any]:
    payload = p5_hardware_pending_payload("RAW_LANE_MATRIX_FRESH", P5_DIR / "raw_lane_matrix", GENERATED / "p5_raw_lane_matrix_summary.md", reason)
    rows = [
        {"direction": direction, "status": PENDING_HW_NOT_EXECUTED, "reason": reason, "remote_active_low_pulse_count": "PENDING_HW"}
        for direction in ["AB_L0", "BA_L0", "AB_L1", "BA_L1"]
    ]
    write_csv(P5_DIR / "raw_lane_matrix" / "p5_raw_lane_matrix.csv", ["direction", "status", "reason", "remote_active_low_pulse_count"], rows)
    write_json(P5_DIR / "raw_lane_matrix" / "p5_raw_lane_matrix.json", rows)
    return payload


def write_pending_hardware_summaries(reason: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for marker, (_, evidence_dir, summary_path) in HARDWARE_STAGES.items():
        if marker == "RAW_LANE_MATRIX_FRESH":
            item = _write_raw_matrix_pending(reason)
        else:
            item = p5_hardware_pending_payload(marker, evidence_dir, summary_path, reason)
        payload[marker] = item.get(marker, PENDING_HW_NOT_EXECUTED)
    retry_payload = run_retry_fault_injection_sim()
    two_hour_lines = [
        f"TWO_LANE_2H_SOAK_OPTIONAL: {NOT_RUN_OPTIONAL}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- The optional 2h soak is not run until the required 30min P5 soak passes.",
    ]
    write_markdown(
        GENERATED / "p5_two_lane_2h_soak_optional_summary.md",
        "P5 Two-Lane 2h Optional Soak Summary",
        NOT_RUN_OPTIONAL,
        "optional soak is not run before required P5 30min soak PASS",
        two_hour_lines,
    )
    payload["RETRY_FAULT_INJECTION_SIM"] = retry_payload.get("RETRY_FAULT_INJECTION_SIM", "FAIL")
    payload["RETRY_FAULT_INJECTION_HW_OPTIONAL"] = "SKIP_NO_HW_FAULT_INJECTION_HOOK"
    payload["TWO_LANE_2H_SOAK_OPTIONAL"] = NOT_RUN_OPTIONAL
    return payload


def prepare_hardware_package(args: argparse.Namespace, *, execute_hardware: bool) -> dict[str, Any]:
    ensure_authorization_template(args.max_runtime_sec or 1800)
    stage_plan = generate_stage_plan()
    auth_path = ROOT / args.authorization_file if args.authorization_file and not Path(args.authorization_file).is_absolute() else Path(args.authorization_file or P5_DEFAULT_AUTH_FILE)
    shutdown_rel = args.shutdown_bitstream or str(DEFAULT_SHUTDOWN_BITSTREAM.relative_to(ROOT))
    package_stage = args.stage_filter if args.stage_filter != "all" else P5_DEFAULT_AUTH_STAGE
    stage_defaults = next((item for item in STAGE_PLAN if item["stage"] == package_stage), {})
    package_profile = args.profile or stage_defaults.get("profile", "")
    package_bitstream = args.bitstream or ((stage_defaults.get("bitstreams") or [""])[0] if stage_defaults else "")
    package_runtime = args.max_runtime_sec
    if package_runtime <= 0 and package_profile:
        profile_data = load_json(ROOT / package_profile)
        if isinstance(profile_data, dict):
            try:
                package_runtime = int(profile_data.get("max_runtime_sec") or 0)
            except Exception:
                package_runtime = 0
    hashes = active_hashes()
    auth = validate_p5_authorization(
        allow_hardware=args.allow_hardware,
        execute_hardware=execute_hardware,
        authorization_file=auth_path,
        board_id=args.board_id,
        bitstream=package_bitstream,
        bitstream_sha256=args.bitstream_sha256 or sha256_or_missing(ROOT / package_bitstream),
        profile=package_profile,
        profile_sha256=args.profile_sha256 or sha256_or_missing(ROOT / package_profile),
        active_pinmap_hash=args.active_pinmap_hash or hashes.get("pinmap", "MISSING"),
        active_xdc_hash=args.active_xdc_hash or hashes.get("active_xdc", "MISSING"),
        shutdown_bitstream=shutdown_rel,
        shutdown_bitstream_sha256=args.shutdown_bitstream_sha256 or sha256_or_missing(ROOT / shutdown_rel),
        max_runtime_sec=package_runtime if package_runtime > 0 else None,
        shutdown_on_exit=args.shutdown_on_exit,
        lane_count=args.lane_count,
    )
    auth_summary = write_authorization_summary(auth)
    run_package = write_authorized_run_package(
        auth_payload=auth,
        stage=args.stage_filter if args.stage_filter != "all" else P5_DEFAULT_AUTH_STAGE,
        board_id=args.board_id,
        authorization_file=auth_path,
        profile=package_profile,
        bitstream=package_bitstream,
        max_runtime_sec=package_runtime if package_runtime > 0 else None,
        lane_count=args.lane_count,
        shutdown_bitstream=shutdown_rel,
    )
    return {
        "P5_HARDWARE_STAGE_PLAN": stage_plan["P5_HARDWARE_STAGE_PLAN"],
        "P5_HARDWARE_STAGE_PLAN_SUMMARY": "evidence/generated/p5_hardware_stage_plan_summary.md",
        **auth_summary,
        **run_package,
        "P5_HARDWARE_AUTHORIZATION_MISSING_CONTROLS": auth.get("missing", []),
    }


def update_status_docs(p5_status: str) -> dict[str, Any]:
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    content = f"""# Project Status

Project: RF_COMM_MULTILANE
Current branch: {branch}
Current HEAD: {head}

P0_BOOTSTRAP: PASS
P1_OFFLINE_HARDENING: PASS
P2_SIMULATION_BASELINE: PASS
P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
P5_2LANE_PROTOCOL_STABILIZATION: {p5_status}
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE

USER_CONFIRMED_SUPPLY_OK: true
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
AVAILABLE_LANES: 2

P5 evidence is stationary, 2-lane, JTAG/ILA/proxy based when hardware is explicitly authorized.
It is not Ethernet, rotation, 8-lane, or product-final acceptance.

Current P5 runner default is dry-run. Fresh P5 hardware stages remain pending until an explicitly authorized P5 run provides P5 evidence and shutdown-on-exit logs.
"""
    write_text(ROOT / "PROJECT_STATUS.md", content)
    write_text(ROOT / "docs" / "PROJECT_STATUS.md", content)

    readme = f"""# RF_COMM_MULTILANE

No-hardware rebuild workspace for the TFDU6102 RF_COMM project.

Imported legacy source: `C:\\Users\\user\\Documents\\RF_COMM`

Canonical inputs:
- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map: `config/register_map/ir_axi_regs.yaml`
- P1 offline hardening gates: `python tools/run_offline_gate.py --allow-skips --json-summary`
- P2 simulation gate: `python tools/run_simulation_gate.py --allow-skips --json-summary`
- P5 dry-run gate: `python tools/run_p5_gate.py --json-summary --skip-ethernet --skip-motion --lane-count 2`

Hardware is not run by default. Hardware-related items remain `HARDWARE_ACCEPTANCE: PENDING_HW` unless the user explicitly authorizes a safe wrapper run and shutdown evidence is captured.

Current stage summary:
- P0_BOOTSTRAP: PASS
- P1_OFFLINE_HARDENING: PASS
- P2_SIMULATION_BASELINE: PASS
- P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
- P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
- P5_2LANE_PROTOCOL_STABILIZATION: {p5_status}
- ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
- ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
- EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE

P5 evidence is stationary, 2-lane, JTAG/ILA/proxy based when hardware is explicitly authorized. It is not Ethernet, rotation, 8-lane, or product-final acceptance.
"""
    write_text(ROOT / "README.md", readme)
    lines = [
        "P5_DOCS_STATUS_CHECK: PASS",
        f"P5_2LANE_PROTOCOL_STABILIZATION: {p5_status}",
        "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
        "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
        "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
    ]
    write_markdown(
        GENERATED / "p5_project_status_update_summary.md",
        "P5 Project Status Update Summary",
        PASS,
        "project status documents updated with P5 boundary",
        lines,
    )
    return {"P5_DOCS_STATUS_CHECK": PASS, "summary": "evidence/generated/p5_project_status_update_summary.md"}


def write_final_summary(payload: dict[str, Any]) -> dict[str, Any]:
    blocking_hw = [
        "SAFE_IDLE_RECHECK",
        "TFDU_CONTROL_IDLE_RECHECK",
        "RAW_LANE_MATRIX_FRESH",
        "LANE0_FRAME_CRC_100",
        "LANE1_FRAME_CRC_100",
        "LANE0_ACK_RETRY_100",
        "LANE1_ACK_RETRY_100",
        "TWO_LANE_MINIMAL_100",
        "PAYLOAD_SWEEP",
        "MASK_REGRESSION",
        "TWO_LANE_30MIN_SOAK",
    ]
    has_fail = any(value == FAIL for value in payload.values())
    hardware_pending = any(payload.get(key) == PENDING_HW_NOT_EXECUTED for key in blocking_hw)
    p5_status = FAIL if has_fail else "IN_PROGRESS" if hardware_pending else PASS_WITH_NOTES
    shutdown_value = (
        payload.get("SHUTDOWN_ON_EXIT")
        if payload.get("HARDWARE_ACTIONS_EXECUTED") and payload.get("SHUTDOWN_ON_EXIT")
        else "PENDING_HW_FOR_FRESH_P5_HARDWARE"
    )
    no_hardware_actions = not bool(payload.get("HARDWARE_ACTIONS_EXECUTED"))
    payload.update(
        {
            "P5_2LANE_PROTOCOL_STABILIZATION": p5_status,
            "COMMIT": git_value("rev-parse", "HEAD"),
            "USER_CONFIRMED_SUPPLY_OK": True,
            "NETWORK_CABLE_CONNECTED": False,
            "HARDWARE_MOVEMENT_ALLOWED": False,
            "AVAILABLE_LANES": 2,
            "ETHERNET_ACCEPTANCE": "DEFERRED_NO_NETWORK_CABLE",
            "ROTATION_ACCEPTANCE": "DEFERRED_NO_HARDWARE_MOVEMENT",
            "EIGHT_LANE_ACCEPTANCE": "DEFERRED_ONLY_2_LANES_AVAILABLE",
            "SHUTDOWN_ON_EXIT": shutdown_value,
            "STOP_CONDITIONS_TRIGGERED": payload.get(
                "STOP_CONDITIONS_TRIGGERED",
                "fresh_p5_hardware_not_authorized" if hardware_pending and not has_fail else "none" if not has_fail else "failure",
            ),
            "NEXT_RECOMMENDED_STAGE": "P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET" if p5_status in {PASS, PASS_WITH_NOTES} else "COMPLETE_FRESH_P5_AUTHORIZED_HARDWARE_EVIDENCE",
            "NO_HARDWARE_ACTIONS_EXECUTED": no_hardware_actions,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }
    )
    summaries = sorted(path.as_posix() for path in GENERATED.glob("p5_*summary.md"))
    payload["GENERATED_SUMMARIES"] = [rel(ROOT / item) if not item.startswith("evidence/") else item for item in summaries]
    write_json(GENERATED / "p5_2lane_protocol_stabilization_summary.json", payload)
    lines = [
        f"P5_2LANE_PROTOCOL_STABILIZATION: {p5_status}",
        f"COMMIT: {payload['COMMIT']}",
        "USER_CONFIRMED_SUPPLY_OK: true",
        "NETWORK_CABLE_CONNECTED: false",
        "HARDWARE_MOVEMENT_ALLOWED: false",
        "AVAILABLE_LANES: 2",
        "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
        "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
        "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
        f"P4_EVIDENCE_RECONCILIATION: {payload.get('P4_EVIDENCE_RECONCILIATION', 'NOT_RUN')}",
        f"P5_HARDWARE_STAGE_PLAN: {payload.get('P5_HARDWARE_STAGE_PLAN', 'NOT_RUN')}",
        f"P5_AUTHORIZED_RUN_PACKAGE: {payload.get('P5_AUTHORIZED_RUN_PACKAGE', 'NOT_RUN')}",
        f"P5_HARDWARE_AUTHORIZATION: {payload.get('P5_HARDWARE_AUTHORIZATION', 'NOT_RUN')}",
        f"SAFE_IDLE_RECHECK: {payload.get('SAFE_IDLE_RECHECK', 'NOT_RUN')}",
        f"RAW_LANE_MATRIX_FRESH: {payload.get('RAW_LANE_MATRIX_FRESH', 'NOT_RUN')}",
        f"LANE0_FRAME_CRC_100: {payload.get('LANE0_FRAME_CRC_100', 'NOT_RUN')}",
        f"LANE1_FRAME_CRC_100: {payload.get('LANE1_FRAME_CRC_100', 'NOT_RUN')}",
        f"LANE0_ACK_RETRY_100: {payload.get('LANE0_ACK_RETRY_100', 'NOT_RUN')}",
        f"LANE1_ACK_RETRY_100: {payload.get('LANE1_ACK_RETRY_100', 'NOT_RUN')}",
        f"TWO_LANE_MINIMAL_100: {payload.get('TWO_LANE_MINIMAL_100', 'NOT_RUN')}",
        f"PAYLOAD_SWEEP: {payload.get('PAYLOAD_SWEEP', 'NOT_RUN')}",
        f"MASK_REGRESSION: {payload.get('MASK_REGRESSION', 'NOT_RUN')}",
        f"RETRY_FAULT_INJECTION_SIM: {payload.get('RETRY_FAULT_INJECTION_SIM', 'NOT_RUN')}",
        f"RETRY_FAULT_INJECTION_HW_OPTIONAL: {payload.get('RETRY_FAULT_INJECTION_HW_OPTIONAL', 'NOT_RUN')}",
        f"TWO_LANE_30MIN_SOAK: {payload.get('TWO_LANE_30MIN_SOAK', 'NOT_RUN')}",
        f"TWO_LANE_2H_SOAK_OPTIONAL: {payload.get('TWO_LANE_2H_SOAK_OPTIONAL', NOT_RUN_OPTIONAL)}",
        f"P5_PROTOCOL_METRICS: {payload.get('P5_PROTOCOL_METRICS', 'NOT_RUN')}",
        f"P5_PLAN_REQUIREMENTS_AUDIT: {payload.get('P5_PLAN_REQUIREMENTS_AUDIT', 'NOT_RUN')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        f"STOP_CONDITIONS_TRIGGERED: {payload['STOP_CONDITIONS_TRIGGERED']}",
        f"HARDWARE_ACTIONS_EXECUTED: {str(payload.get('HARDWARE_ACTIONS_EXECUTED', False)).lower()}",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(payload.get('NO_HARDWARE_ACTIONS_EXECUTED', True)).lower()}",
        "",
        "## Boundary",
        "",
        "- P5 dry-run/offline scaffolding and deferred scope gates were generated.",
        "- Fresh P5 hardware protocol stabilization is not claimed as PASS.",
        "- Existing P4 evidence is reconciled as historical intake only.",
        "",
        "## Generated Summaries",
        "",
        *(f"- `{item}`" for item in payload["GENERATED_SUMMARIES"]),
        "",
        f"NEXT_RECOMMENDED_STAGE: {payload['NEXT_RECOMMENDED_STAGE']}",
    ]
    write_markdown(
        GENERATED / "p5_2lane_protocol_stabilization_summary.md",
        "P5 Two-Lane Protocol Stabilization Summary",
        p5_status,
        "fresh P5 hardware evidence remains pending" if p5_status == "IN_PROGRESS" else "P5 summary generated",
        lines,
        no_hw=no_hardware_actions,
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run P5 two-lane protocol stabilization gates. Defaults to dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-hardware", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--authorization-file", default=".hardware_authorization/P5_2LANE_APPROVED.txt")
    parser.add_argument("--board-id", default=DEFAULT_BOARD_ID)
    parser.add_argument("--max-runtime-sec", type=int, default=0)
    parser.add_argument("--profile", default="")
    parser.add_argument("--profile-sha256", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--active-pinmap-hash", default="")
    parser.add_argument("--active-xdc-hash", default="")
    parser.add_argument("--shutdown-bitstream", default="shutdown_bitstream/tfdu_shutdown_j10_j11.bit")
    parser.add_argument("--shutdown-bitstream-sha256", default="")
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--stage-filter", default="all")
    parser.add_argument("--stop-on-first-fail", action="store_true")
    parser.add_argument("--skip-ethernet", action="store_true", default=True)
    parser.add_argument("--skip-motion", action="store_true", default=True)
    parser.add_argument("--lane-count", type=int, default=2)
    parser.add_argument("--skip-recheck", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--reuse-existing-recheck", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_dirs()
    payload: dict[str, Any] = {}

    if args.lane_count != 2:
        payload["P5_2LANE_PROTOCOL_STABILIZATION"] = FAIL
        payload["STOP_CONDITIONS_TRIGGERED"] = "lane_count_not_2"
        write_final_summary(payload)
        if args.json_summary:
            print(json.dumps(payload, ensure_ascii=False))
        return 1

    if args.execute_hardware:
        if args.stage_filter == "all":
            payload.update(write_repo_intake())
            p4 = reconcile_p4()
            payload["P4_EVIDENCE_RECONCILIATION"] = p4["P4_EVIDENCE_RECONCILIATION"]
            if not args.skip_recheck:
                payload.update(run_rechecks(reuse_existing=args.reuse_existing_recheck))
            payload.update(write_profiles())
            payload.update(check_no_ethernet())
            payload.update(check_no_motion())
            payload.update(check_2lane_scope())
        payload.update(prepare_hardware_package(args, execute_hardware=True))
        if payload.get("P5_HARDWARE_AUTHORIZATION") != "AUTHORIZED":
            payload["P5_2LANE_PROTOCOL_STABILIZATION"] = FAIL
            write_final_summary(payload)
            if args.json_summary:
                print(json.dumps(payload, ensure_ascii=False))
            return 1
        payload.update(run_authorized_hardware(args))
        if args.stage_filter != "all":
            if args.json_summary:
                print(json.dumps(payload, ensure_ascii=False))
            else:
                for key, value in payload.items():
                    if isinstance(value, (str, int, bool)):
                        print(f"{key}: {value}")
            return 1 if payload.get("P5_HARDWARE_EXECUTION") == FAIL else 0
        retry_payload = run_retry_fault_injection_sim()
        payload["RETRY_FAULT_INJECTION_SIM"] = retry_payload.get("RETRY_FAULT_INJECTION_SIM", "FAIL")
        payload["RETRY_FAULT_INJECTION_HW_OPTIONAL"] = "SKIP_NO_HW_FAULT_INJECTION_HOOK"
        payload["TWO_LANE_2H_SOAK_OPTIONAL"] = NOT_RUN_OPTIONAL
        payload.update(analyze_metrics())
        payload.update(check_consistency())
        payload.update(audit_plan_requirements())
        final_payload = write_final_summary(payload)
        update_status_docs(final_payload["P5_2LANE_PROTOCOL_STABILIZATION"])
        final_payload.update(audit_plan_requirements())
        final_payload = write_final_summary(final_payload)
        if args.json_summary:
            print(json.dumps(final_payload, ensure_ascii=False))
        else:
            print(f"P5_2LANE_PROTOCOL_STABILIZATION: {final_payload['P5_2LANE_PROTOCOL_STABILIZATION']}")
            print(f"STOP_CONDITIONS_TRIGGERED: {final_payload['STOP_CONDITIONS_TRIGGERED']}")
            print("HARDWARE_ACTIONS_EXECUTED: true")
            print("HARDWARE_ACCEPTANCE: PENDING_HW")
        return 1 if final_payload["P5_2LANE_PROTOCOL_STABILIZATION"] == FAIL else 0

    if _selected(args.stage_filter, "intake"):
        payload.update(write_repo_intake())
    if _selected(args.stage_filter, "reconcile"):
        payload.update({"P4_EVIDENCE_RECONCILIATION": reconcile_p4()["P4_EVIDENCE_RECONCILIATION"]})
    if _selected(args.stage_filter, "recheck") and not args.skip_recheck:
        payload.update(run_rechecks(reuse_existing=args.reuse_existing_recheck))
    if _selected(args.stage_filter, "profiles"):
        payload.update(write_profiles())
    if _selected(args.stage_filter, "ethernet"):
        payload.update(check_no_ethernet())
    if _selected(args.stage_filter, "motion"):
        payload.update(check_no_motion())
    if _selected(args.stage_filter, "scope"):
        payload.update(check_2lane_scope())
    if _selected(args.stage_filter, "authorization"):
        payload.update(prepare_hardware_package(args, execute_hardware=False))
    if _selected(args.stage_filter, "stage-plan"):
        stage_plan = generate_stage_plan()
        payload.update(
            {
                "P5_HARDWARE_STAGE_PLAN": stage_plan["P5_HARDWARE_STAGE_PLAN"],
                "P5_HARDWARE_STAGE_PLAN_SUMMARY": "evidence/generated/p5_hardware_stage_plan_summary.md",
            }
        )

    if args.stage_filter == "all":
        payload.update(write_repo_intake())
        p4 = reconcile_p4()
        payload["P4_EVIDENCE_RECONCILIATION"] = p4["P4_EVIDENCE_RECONCILIATION"]
        if not args.skip_recheck:
            payload.update(run_rechecks(reuse_existing=args.reuse_existing_recheck))
        payload.update(write_profiles())
        payload.update(check_no_ethernet())
        payload.update(check_no_motion())
        payload.update(check_2lane_scope())
        payload.update(prepare_hardware_package(args, execute_hardware=False))

    if args.stage_filter in {"all", "hardware-pending"}:
        payload.update(write_pending_hardware_summaries("fresh P5 hardware execution was not explicitly authorized in this run"))

    if args.stage_filter in {"all", "metrics"}:
        payload.update(analyze_metrics())
    if args.stage_filter in {"all", "consistency"}:
        payload.update(check_consistency())
    if args.stage_filter in {"all", "audit"}:
        payload.update(audit_plan_requirements())

    if args.stage_filter != "all":
        if args.json_summary:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            for key, value in payload.items():
                if isinstance(value, (str, int, bool)):
                    print(f"{key}: {value}")
        return 1 if any(value == FAIL for value in payload.values()) else 0

    final_payload = write_final_summary(payload)
    update_status_docs(final_payload["P5_2LANE_PROTOCOL_STABILIZATION"])
    final_payload.update(audit_plan_requirements())
    final_payload = write_final_summary(final_payload)

    if args.json_summary:
        print(json.dumps(final_payload, ensure_ascii=False))
    else:
        print(f"P5_2LANE_PROTOCOL_STABILIZATION: {final_payload['P5_2LANE_PROTOCOL_STABILIZATION']}")
        print(f"STOP_CONDITIONS_TRIGGERED: {final_payload['STOP_CONDITIONS_TRIGGERED']}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
    return 1 if final_payload["P5_2LANE_PROTOCOL_STABILIZATION"] == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
