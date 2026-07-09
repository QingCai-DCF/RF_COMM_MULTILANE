#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from p4_hw_authorization import DEFAULT_AUTH_FILE, ensure_authorization_template, validate_authorization, write_authorization_artifacts
from p4_hw_evidence import (
    GENERATED,
    P4_DIR,
    PENDING_HW_LINE,
    ROOT,
    active_hashes,
    candidate_bitstream_metadata,
    current_gate_statuses,
    ensure_p4_dirs,
    git_value,
    rel,
    run_cmd,
    tool_versions_text,
    write_json,
    write_markdown,
    write_recheck_summary,
    write_repo_intake,
    write_text,
)
from p4_hw_profiles import safe_idle_audit
from p4_hw_execution import run_authorized_safe_idle_sequence


P4_STAGE_NAMES = [
    "safe-idle",
    "tfdu-control-idle",
    "raw-pulse-smoke",
    "raw-lane-matrix",
    "lane0-frame-crc",
    "lane0-ack-retry",
    "lane1-frame-crc",
    "lane1-ack-retry",
    "two-lane-minimal",
    "lane0-300s-soak",
    "two-lane-300s-soak",
]


def _resolve_root_path(value: str | None) -> Path:
    if not value:
        return DEFAULT_AUTH_FILE
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def run_p4_rechecks(skip: bool = False, allow_skips: bool = True) -> dict:
    write_repo_intake()
    if skip:
        existing = GENERATED / "p4_recheck_p1_p2_p3_summary.md"
        if existing.exists():
            statuses = current_gate_statuses()
            prereq_pass = all(statuses.get(key) in {"PASS", "PASS_WITH_SKIPS"} for key in ["P1_RECHECK", "P2_RECHECK", "P3_RECHECK"])
            return {"result": "PASS" if prereq_pass else "FAIL", "path": rel(existing), **statuses}
        return write_recheck_summary([])
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
        [sys.executable, "tools/run_pre_hw_acceptance_package_gate.py", "--json-summary", "--allow-skips"],
        [sys.executable, "tools/summarize_gate.py"],
    ]
    results = []
    for cmd in commands:
        result = run_cmd(cmd, timeout=900)
        results.append(
            {
                "cmd": result["cmd"],
                "returncode": result["returncode"],
                "stdout_tail": result["stdout"][-3000:],
                "stderr_tail": result["stderr"][-3000:],
            }
        )
        if result["returncode"] != 0 and not allow_skips:
            break
    write_repo_intake()
    return write_recheck_summary(results)


def write_p4_dry_run_placeholders(auth_payload: dict, profile_payload: dict) -> dict:
    hashes = active_hashes()
    bitstream = candidate_bitstream_metadata()
    env_lines = [
        "P4_ENVIRONMENT_CAPTURE: SKIP_NOT_AUTHORIZED",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "Hardware environment capture is intentionally not run until authorization passes.",
        "",
        "## Static Hashes",
        "",
        *(f"- {name}: `{value}`" for name, value in hashes.items()),
    ]
    write_markdown(
        P4_DIR / "p4_environment_capture.md",
        "P4 Environment Capture",
        "SKIP_NOT_AUTHORIZED",
        "JTAG and tool target capture require explicit hardware authorization",
        env_lines,
    )
    write_text(P4_DIR / "p4_tool_versions.txt", tool_versions_text())
    write_text(
        P4_DIR / "p4_jtag_targets.txt",
        "\n".join(
            [
                "P4_JTAG_TARGETS: SKIP_NOT_AUTHORIZED",
                "NO_HARDWARE_ACTIONS_EXECUTED: true",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ]
        ),
    )
    manifest_lines = [
        "P4_BITSTREAM_CANDIDATE: DRY_RUN_ONLY",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"bitstream_candidate_path: `{bitstream['bitstream_candidate_path']}`",
        f"bitstream_candidate_sha256: `{bitstream['bitstream_candidate_sha256']}`",
        f"bitstream_candidate_status: `{bitstream['bitstream_candidate_status']}`",
        "",
        "## Active Inputs",
        "",
        *(f"- {name}: `{value}`" for name, value in hashes.items()),
    ]
    write_markdown(
        P4_DIR / "p4_bitstream_candidate_manifest.md",
        "P4 Bitstream Candidate Manifest",
        "DRY_RUN_ONLY",
        "candidate metadata recorded without programming hardware",
        manifest_lines,
    )
    write_text(
        P4_DIR / "p4_safe_idle_programming_log.txt",
        "\n".join(
            [
                "P4_SAFE_IDLE_PROGRAMMING: SKIP_NOT_AUTHORIZED",
                "NO_HARDWARE_ACTIONS_EXECUTED: true",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
                "No bitstream was programmed.",
            ]
        ),
    )
    write_markdown(
        P4_DIR / "p4_safe_idle_readback_summary.md",
        "P4 Safe Idle Readback Summary",
        "SKIP_NOT_AUTHORIZED",
        "safe-idle hardware programming/readback requires authorization",
        [
            "SAFE_IDLE_READBACK: SKIP_NOT_AUTHORIZED",
            "READBACK_LIMITED: true",
            "reason: no hardware authorization",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
    )
    write_markdown(
        P4_DIR / "p4_tfdu_control_idle_summary.md",
        "P4 TFDU Control Idle Summary",
        "SKIP_NOT_AUTHORIZED",
        "TFDU SD/Mode/Txd control is not touched without authorization",
        [
            "TFDU_CONTROL_IDLE: SKIP_NOT_AUTHORIZED",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
    )
    write_markdown(
        P4_DIR / "raw_pulse_smoke" / "p4_raw_pulse_smoke_summary.md",
        "P4 Raw Pulse Smoke Summary",
        "SKIP_NOT_AUTHORIZED",
        "raw pulse smoke would drive TFDU Txd and is blocked",
        [
            "RAW_PULSE_SMOKE: SKIP_NOT_AUTHORIZED",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
    )
    write_text(
        P4_DIR / "raw_pulse_smoke" / "p4_raw_pulse_smoke.csv",
        "lane,direction,burst_pulses,status,reason\n"
        "0,A_TO_B,10,SKIP_NOT_AUTHORIZED,no valid P4 authorization\n"
        "0,B_TO_A,10,SKIP_NOT_AUTHORIZED,no valid P4 authorization\n"
        "1,A_TO_B,10,SKIP_NOT_AUTHORIZED,no valid P4 authorization\n"
        "1,B_TO_A,10,SKIP_NOT_AUTHORIZED,no valid P4 authorization\n",
    )
    matrix_rows = [
        ("AB_L0", "SKIP_NOT_AUTHORIZED", "no valid P4 authorization"),
        ("BA_L0", "SKIP_NOT_AUTHORIZED", "no valid P4 authorization"),
        ("AB_L1", "SKIP_NOT_AUTHORIZED", "lane1 remains blocked until fresh raw evidence; no valid P4 authorization"),
        ("BA_L1", "SKIP_NOT_AUTHORIZED", "lane1 remains blocked until fresh raw evidence; no valid P4 authorization"),
    ]
    write_text(
        P4_DIR / "raw_lane_matrix" / "p4_raw_lane_matrix.csv",
        "direction,status,reason\n" + "\n".join(f"{a},{b},{c}" for a, b, c in matrix_rows),
    )
    write_markdown(
        P4_DIR / "raw_lane_matrix" / "p4_raw_lane_matrix.md",
        "P4 Raw Lane Matrix",
        "SKIP_NOT_AUTHORIZED",
        "raw lane matrix is blocked until authorized P4 execution",
        [
            "RAW_LANE_MATRIX: SKIP_NOT_AUTHORIZED",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            "",
            "| Direction | Status | Reason |",
            "| --- | --- | --- |",
            *(f"| {direction} | {status} | {reason} |" for direction, status, reason in matrix_rows),
        ],
    )
    protocol_files = {
        "p4_lane0_frame_crc_summary.md": ("LANE0_FRAME_CRC", "requires lane0 raw matrix PASS"),
        "p4_lane0_ack_retry_summary.md": ("LANE0_ACK_RETRY", "requires lane0 frame/CRC PASS"),
        "p4_lane1_frame_crc_summary.md": ("LANE1_FRAME_CRC", "requires lane1 raw AB/BA PASS"),
        "p4_lane1_ack_retry_summary.md": ("LANE1_ACK_RETRY", "requires lane1 frame/CRC PASS"),
        "p4_two_lane_minimal_summary.md": ("TWO_LANE_MINIMAL", "requires both lane0 and lane1 protocol PASS"),
    }
    for filename, (marker, reason) in protocol_files.items():
        write_markdown(
            P4_DIR / "protocol_smoke" / filename,
            marker.replace("_", " ").title(),
            "SKIP_NOT_AUTHORIZED",
            reason,
            [
                f"{marker}: SKIP_NOT_AUTHORIZED",
                "NO_HARDWARE_ACTIONS_EXECUTED: true",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
        )
    for filename in ["p4_lane0_frame_crc_counters.csv", "p4_lane0_ack_retry_counters.csv"]:
        write_text(P4_DIR / "protocol_smoke" / filename, "test,status,reason\nall,SKIP_NOT_AUTHORIZED,no valid P4 authorization\n")
    for filename, marker in [
        ("p4_lane0_300s_soak_summary.md", "LANE0_300S_SOAK"),
        ("p4_two_lane_300s_soak_summary.md", "TWO_LANE_300S_SOAK"),
    ]:
        write_markdown(
            P4_DIR / "soak" / filename,
            marker.replace("_", " ").title(),
            "SKIP_NOT_AUTHORIZED",
            "soak is blocked until prerequisite hardware stages pass",
            [
                f"{marker}: SKIP_NOT_AUTHORIZED",
                "NO_HARDWARE_ACTIONS_EXECUTED: true",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
        )
    write_text(
        P4_DIR / "shutdown" / "p4_shutdown_log.txt",
        "P4_SHUTDOWN: SKIP_NO_HARDWARE_ACTIONS\nNO_HARDWARE_ACTIONS_EXECUTED: true\nHARDWARE_ACCEPTANCE: PENDING_HW\n",
    )
    write_markdown(
        P4_DIR / "shutdown" / "p4_shutdown_summary.md",
        "P4 Shutdown Summary",
        "SKIP_NO_HARDWARE_ACTIONS",
        "no hardware action occurred, so shutdown programming was not required",
        [
            "SHUTDOWN_ON_EXIT: SKIP_NO_HARDWARE_ACTIONS",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
    )
    return {
        "environment_capture": rel(P4_DIR / "p4_environment_capture.md"),
        "authorization_record": rel(P4_DIR / "p4_authorization_record.md"),
        "profile_audit": profile_payload.get("summary"),
        "bitstream_manifest": rel(P4_DIR / "p4_bitstream_candidate_manifest.md"),
    }


def write_p4_summary(
    auth_payload: dict,
    recheck_payload: dict,
    profile_payload: dict,
    placeholders: dict,
    execute_hardware: bool,
    stage_payload: dict | None = None,
) -> dict:
    stage_payload = stage_payload or {}
    statuses = current_gate_statuses()
    prereq_pass = all(statuses.get(key) in {"PASS", "PASS_WITH_SKIPS"} for key in ["P1_RECHECK", "P2_RECHECK", "P3_RECHECK"])
    hardware_actions = bool(stage_payload.get("HARDWARE_ACTIONS_EXECUTED", False))
    no_hardware_actions = not hardware_actions
    stop_conditions = stage_payload.get("STOP_CONDITIONS_TRIGGERED", []) or []
    environment_capture = stage_payload.get("ENVIRONMENT_CAPTURE", "SKIP_NOT_AUTHORIZED" if not auth_payload["AUTHORIZED"] else "SKIP_WITH_REASON")
    safe_idle = stage_payload.get("SAFE_IDLE", "SKIP_NOT_AUTHORIZED" if not auth_payload["AUTHORIZED"] else "SKIP_WITH_REASON")
    shutdown_on_exit = stage_payload.get("SHUTDOWN_ON_EXIT", "SKIP_NO_HARDWARE_ACTIONS" if no_hardware_actions else "FAIL")
    if not auth_payload["AUTHORIZED"]:
        p4_status = "BLOCKED_NOT_AUTHORIZED"
        next_stage = "P4_HARDWARE_ACCEPTANCE_ONLY_AFTER_USER_AUTHORIZATION"
    elif not prereq_pass or profile_payload.get("P4_SAFE_IDLE_PROFILE_AUDIT") != "PASS":
        p4_status = "FAIL_WITH_EVIDENCE"
        next_stage = "P4A_SAFE_STATE_FIX"
    elif hardware_actions:
        p4_status = "FAIL_WITH_EVIDENCE"
        next_stage = "P4_SAFE_IDLE_READBACK_OR_ENVIRONMENT_FIX" if stop_conditions or safe_idle != "PASS_WITH_LIMITED_READBACK" else "P4_SAFE_IDLE_DIRECT_READBACK_INSTRUMENTATION"
    else:
        p4_status = "FAIL_WITH_EVIDENCE"
        next_stage = "P4_HARDWARE_RUNNER_IMPLEMENTATION_REVIEW"
    hardware_acceptance_status = p4_status if hardware_actions else "PENDING_HW"
    generated = [
        "evidence/generated/p4_repo_intake.md",
        "evidence/generated/p4_recheck_p1_p2_p3_summary.md",
        "evidence/generated/p4_authorization_gate_summary.md",
        "evidence/generated/p4_safe_idle_profile_audit.md",
        "evidence/generated/p4_hardware_acceptance_summary.md",
        "evidence/generated/p4_hardware_acceptance_gate_summary.md",
        "evidence/generated/p4_no_hardware_or_authorized_hardware_scan.md",
        "evidence/hardware/p4/p4_authorized_run_results.json",
    ]
    pass_items = []
    if recheck_payload.get("result") == "PASS":
        pass_items.append("P4.0 repo intake + P1/P2/P3 recheck")
    if profile_payload.get("P4_SAFE_IDLE_PROFILE_AUDIT") == "PASS":
        pass_items.append("P4.3 safe-idle profile audit")
    if environment_capture == "PASS":
        pass_items.append("P4.2 hardware environment capture")
    if safe_idle == "PASS_WITH_LIMITED_READBACK":
        pass_items.append("P4.4 safe-idle bitstream programming")
    if shutdown_on_exit == "PASS":
        pass_items.append("shutdown-on-exit")
    fail_items = []
    if p4_status == "FAIL_WITH_EVIDENCE":
        if stop_conditions:
            fail_items.extend(f"stop condition: {item}" for item in stop_conditions)
        else:
            fail_items.append("P4 hardware acceptance did not reach all required stages")
    if not auth_payload["AUTHORIZED"]:
        skip_items = [
            "P4.1 authorization validation: BLOCKED_NOT_AUTHORIZED",
            "P4.2 hardware environment capture: SKIP_NOT_AUTHORIZED",
            "P4.4 safe-idle programming/readback: SKIP_NOT_AUTHORIZED",
            "P4.5 TFDU control idle: SKIP_NOT_AUTHORIZED",
            "P4.6 raw pulse smoke: SKIP_NOT_AUTHORIZED",
            "P4.7 raw lane matrix: SKIP_NOT_AUTHORIZED",
            "P4.8-P4.12 protocol/soak stages: SKIP_NOT_AUTHORIZED",
        ]
    else:
        skip_reason = "blocked by earlier P4 stage result"
        if safe_idle == "PASS_WITH_LIMITED_READBACK":
            skip_reason = "blocked until direct safe-idle TFDU pin readback or ILA/proxy evidence is available"
        skip_items = [
            f"P4.2 hardware environment capture: {environment_capture}",
            f"P4.4 safe-idle programming/readback: {safe_idle}",
            f"P4.5 TFDU control idle: SKIP_WITH_REASON: {skip_reason}",
            f"P4.6 raw pulse smoke: SKIP_WITH_REASON: {skip_reason}",
            f"P4.7 raw lane matrix: SKIP_WITH_REASON: {skip_reason}",
            f"P4.8-P4.12 protocol/soak stages: SKIP_WITH_REASON: {skip_reason}",
        ]
    lines = [
        f"P4_HARDWARE_ACCEPTANCE: {p4_status}",
        f"COMMIT: {git_value('rev-parse', 'HEAD')}",
        f"AUTHORIZED: {str(auth_payload['AUTHORIZED']).lower()}",
        f"AUTHORIZATION_FILE: {auth_payload['AUTHORIZATION_FILE']}",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hardware_actions).lower()}",
        f"HARDWARE_ACTIONS_EXECUTED: {str(hardware_actions).lower()}",
        f"HARDWARE_ACCEPTANCE: {hardware_acceptance_status}",
        f"P1_RECHECK: {statuses.get('P1_RECHECK', 'UNKNOWN')}",
        f"P2_RECHECK: {statuses.get('P2_RECHECK', 'UNKNOWN')}",
        f"P3_RECHECK: {statuses.get('P3_RECHECK', 'UNKNOWN')}",
        f"SAFE_IDLE_PROFILE_AUDIT: {profile_payload.get('P4_SAFE_IDLE_PROFILE_AUDIT', 'UNKNOWN')}",
        f"P4_ENVIRONMENT_CAPTURE: {environment_capture}",
        f"SAFE_IDLE: {safe_idle}",
        "TFDU_CONTROL_IDLE: SKIP_WITH_REASON",
        "RAW_PULSE_SMOKE: SKIP_WITH_REASON",
        "RAW_LANE_MATRIX: SKIP_WITH_REASON",
        "LANE0_FRAME_CRC: SKIP_WITH_REASON",
        "LANE0_ACK_RETRY: SKIP_WITH_REASON",
        "LANE1_FRAME_CRC: SKIP_WITH_REASON",
        "LANE1_ACK_RETRY: SKIP_WITH_REASON",
        "TWO_LANE_MINIMAL: SKIP_WITH_REASON",
        "LANE0_300S_SOAK: SKIP_WITH_REASON",
        "TWO_LANE_300S_SOAK: SKIP_WITH_REASON",
        f"SHUTDOWN_ON_EXIT: {shutdown_on_exit}",
        f"STOP_CONDITIONS_TRIGGERED: {', '.join(stop_conditions) if stop_conditions else 'none'}",
        f"NEXT_RECOMMENDED_STAGE: {next_stage}",
        "",
        "## Generated Summaries",
        "",
        *(f"- `{item}`" for item in generated if (ROOT / item).exists()),
        *(f"- `{path}`" for path in placeholders.values() if path),
        "",
        "## PASS",
        "",
        *(f"- {item}" for item in pass_items),
        *(["- none"] if not pass_items else []),
        "",
        "## FAIL",
        "",
        *(f"- {item}" for item in fail_items),
        *(["- none"] if not fail_items else []),
        "",
        "## SKIP_WITH_REASON",
        "",
        *(f"- {item}" for item in skip_items),
    ]
    write_markdown(
        GENERATED / "p4_hardware_acceptance_summary.md",
        "P4 Hardware Acceptance Summary",
        p4_status,
        "P4 is correctly blocked until explicit hardware authorization" if p4_status == "BLOCKED_NOT_AUTHORIZED" else "P4 did not reach hardware acceptance",
        lines,
        no_hw=no_hardware_actions,
    )
    write_markdown(
        GENERATED / "p4_hardware_acceptance_gate_summary.md",
        "P4 Hardware Acceptance Gate Summary",
        p4_status,
        "no hardware authorization; hardware acceptance remains pending" if not auth_payload["AUTHORIZED"] else "hardware execution did not complete",
        lines,
        no_hw=no_hardware_actions,
    )
    write_markdown(
        GENERATED / "p4_no_hardware_or_authorized_hardware_scan.md",
        "P4 No Hardware Or Authorized Hardware Scan",
        "PASS",
        "P4 entrypoint either produced dry-run evidence or used only the authorized safe wrapper",
        [
            "P4_NO_HARDWARE_OR_AUTHORIZED_HARDWARE_SCAN: PASS",
            f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hardware_actions).lower()}",
            f"HARDWARE_ACTIONS_EXECUTED: {str(hardware_actions).lower()}",
            f"HARDWARE_ACCEPTANCE: {hardware_acceptance_status}",
            "",
            f"- authorization status: {auth_payload['P4_AUTHORIZATION']}",
            f"- environment capture: {environment_capture}",
            f"- safe-idle programming/readback: {safe_idle}",
            f"- shutdown-on-exit: {shutdown_on_exit}",
            "- no PS ELF start",
            "- no UART command",
            "- no ILA capture",
            "- no intentional TFDU TX pulse",
        ],
        no_hw=no_hardware_actions,
    )
    payload = {
        "P4_HARDWARE_ACCEPTANCE": p4_status,
        "COMMIT": git_value("rev-parse", "HEAD"),
        "AUTHORIZED": auth_payload["AUTHORIZED"],
        "AUTHORIZATION_FILE": auth_payload["AUTHORIZATION_FILE"],
        "NO_HARDWARE_ACTIONS_EXECUTED": no_hardware_actions,
        "HARDWARE_ACTIONS_EXECUTED": hardware_actions,
        "HARDWARE_ACCEPTANCE": hardware_acceptance_status,
        "P1_RECHECK": statuses.get("P1_RECHECK", "UNKNOWN"),
        "P2_RECHECK": statuses.get("P2_RECHECK", "UNKNOWN"),
        "P3_RECHECK": statuses.get("P3_RECHECK", "UNKNOWN"),
        "SAFE_IDLE_PROFILE_AUDIT": profile_payload.get("P4_SAFE_IDLE_PROFILE_AUDIT", "UNKNOWN"),
        "P4_ENVIRONMENT_CAPTURE": environment_capture,
        "SAFE_IDLE": safe_idle,
        "TFDU_CONTROL_IDLE": "SKIP_WITH_REASON",
        "RAW_PULSE_SMOKE": "SKIP_WITH_REASON",
        "RAW_LANE_MATRIX": "SKIP_WITH_REASON",
        "LANE0_FRAME_CRC": "SKIP_WITH_REASON",
        "LANE0_ACK_RETRY": "SKIP_WITH_REASON",
        "LANE1_FRAME_CRC": "SKIP_WITH_REASON",
        "LANE1_ACK_RETRY": "SKIP_WITH_REASON",
        "TWO_LANE_MINIMAL": "SKIP_WITH_REASON",
        "LANE0_300S_SOAK": "SKIP_WITH_REASON",
        "TWO_LANE_300S_SOAK": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": shutdown_on_exit,
        "STOP_CONDITIONS_TRIGGERED": stop_conditions or "none",
        "GENERATED_SUMMARIES": [item for item in generated if (ROOT / item).exists()],
        "PASS": pass_items,
        "FAIL": fail_items,
        "SKIP_WITH_REASON": skip_items,
        "NEXT_RECOMMENDED_STAGE": next_stage,
    }
    write_json(GENERATED / "p4_hardware_acceptance_summary.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run P4 hardware acceptance gates. Defaults to dry-run and never touches hardware without authorization.")
    parser.add_argument("--dry-run", action="store_true", help="Run dry-run P4 gates. This is the default unless --execute-hardware is used.")
    parser.add_argument("--execute-hardware", action="store_true", help="Request hardware execution after all authorization gates pass.")
    parser.add_argument("--require-user-hw-authorization", action="store_true")
    parser.add_argument("--authorization-file", default=str(DEFAULT_AUTH_FILE.relative_to(ROOT)))
    parser.add_argument("--profile", default="")
    parser.add_argument("--board-id", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--profile-sha256", default="")
    parser.add_argument("--active-pinmap-hash", default="")
    parser.add_argument("--active-xdc-hash", default="")
    parser.add_argument("--max-runtime-sec", type=int)
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--stage", default="all")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--skip-recheck", action="store_true", help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_p4_dirs()
    ensure_authorization_template()
    dry_run = args.dry_run or not args.execute_hardware
    profile_for_auth = args.profile
    if dry_run and not profile_for_auth:
        profile_for_auth = "profiles/p4_lane0_safe_smoke.json"
    recheck_payload = run_p4_rechecks(skip=args.skip_recheck, allow_skips=args.allow_skips or dry_run)
    profile_payload = safe_idle_audit()
    auth_payload = validate_authorization(
        execute_hardware=args.execute_hardware,
        require_user_hw_authorization=args.require_user_hw_authorization,
        authorization_file=_resolve_root_path(args.authorization_file),
        profile=profile_for_auth,
        max_runtime_sec=args.max_runtime_sec,
        shutdown_on_exit=args.shutdown_on_exit,
        board_id=args.board_id,
        bitstream=args.bitstream,
        bitstream_sha256=args.bitstream_sha256,
        profile_sha256=args.profile_sha256,
        active_pinmap_hash=args.active_pinmap_hash,
        active_xdc_hash=args.active_xdc_hash,
    )
    write_authorization_artifacts(auth_payload)
    stage_payload = {}
    prereq_statuses = current_gate_statuses()
    prereq_pass = all(prereq_statuses.get(key) in {"PASS", "PASS_WITH_SKIPS"} for key in ["P1_RECHECK", "P2_RECHECK", "P3_RECHECK"])
    if args.execute_hardware and auth_payload["AUTHORIZED"] and prereq_pass and profile_payload.get("P4_SAFE_IDLE_PROFILE_AUDIT") == "PASS":
        placeholders = {
            "environment_capture": rel(P4_DIR / "p4_environment_capture.md"),
            "authorization_record": rel(P4_DIR / "p4_authorization_record.md"),
            "profile_audit": profile_payload.get("summary"),
            "bitstream_manifest": rel(P4_DIR / "p4_bitstream_candidate_manifest.md"),
        }
        stage_payload = run_authorized_safe_idle_sequence(args, auth_payload)
    else:
        placeholders = write_p4_dry_run_placeholders(auth_payload, profile_payload)
    payload = write_p4_summary(auth_payload, recheck_payload, profile_payload, placeholders, args.execute_hardware, stage_payload)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    if args.execute_hardware and not auth_payload["AUTHORIZED"]:
        return 2
    if payload["P4_HARDWARE_ACCEPTANCE"] == "FAIL_WITH_EVIDENCE":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
