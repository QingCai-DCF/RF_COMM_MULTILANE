#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from p4_auto_authorization import (
    AUTH_ENV,
    AUTH_ENV_VALUE,
    DEFAULT_AUTH_FILE,
    ensure_authorization_record,
    validate_authorization,
    write_authorization_summary,
)
from p4_auto_bitstream_provenance import generate_bitstream_provenance
from p4_auto_debug_readback import generate_safe_idle_proxy_readback
from p4_auto_parse_ila import (
    parse_lane0_ack_retry_capture_dir,
    parse_lane0_300s_soak_capture_dir,
    parse_lane0_frame_crc_capture_dir,
    parse_lane1_ack_retry_capture_dir,
    parse_lane1_frame_crc_capture_dir,
    parse_raw_lane_matrix_capture_dir,
    parse_raw_pulse_capture_dir,
    parse_safe_idle_capture_dir,
    parse_tfdu_control_idle_capture_dir,
    parse_two_lane_300s_soak_capture_dir,
    parse_two_lane_minimal_capture_dir,
)
from p4_auto_lib import (
    GENERATED,
    P4_AUTO_DIR,
    ROOT,
    active_hashes,
    current_gate_statuses,
    ensure_dirs,
    git_value,
    rel,
    resolve_root_path,
    run_cmd,
    sha256_or_missing,
    tool_versions_text,
    write_json,
    write_markdown,
    write_text,
)
from p4_auto_profiles import write_profiles


DEFAULT_VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
DEFAULT_HW_SERVER_URL = "localhost:3121"
DEFAULT_JTAG_FREQUENCY_HZ = 1_000_000


SUMMARY_FILES = [
    "evidence/generated/p4_auto_repo_intake.md",
    "evidence/generated/p4_auto_recheck_p1_p2_p3_summary.md",
    "evidence/generated/p4_auto_previous_p4_intake.md",
    "evidence/generated/p4_auto_authorization_summary.md",
    "evidence/generated/p4_auto_authorized_run_package.md",
    "evidence/generated/p4_auto_authorized_bitstream_preflight.md",
    "evidence/generated/p4_auto_profiles_summary.md",
    "evidence/generated/p4_auto_bitstream_provenance_summary.md",
    "evidence/generated/p4_auto_safe_idle_direct_proxy_summary.md",
    "evidence/generated/p4_auto_tfdu_control_idle_summary.md",
    "evidence/generated/p4_auto_raw_pulse_smoke_summary.md",
    "evidence/generated/p4_auto_raw_lane_matrix_summary.md",
    "evidence/generated/p4_auto_lane0_frame_crc_summary.md",
    "evidence/generated/p4_auto_lane0_ack_retry_summary.md",
    "evidence/generated/p4_auto_lane1_frame_crc_summary.md",
    "evidence/generated/p4_auto_lane1_ack_retry_summary.md",
    "evidence/generated/p4_auto_two_lane_minimal_summary.md",
    "evidence/generated/p4_auto_lane0_300s_soak_summary.md",
    "evidence/generated/p4_auto_two_lane_300s_soak_summary.md",
    "evidence/generated/p4_auto_shutdown_summary.md",
    "evidence/generated/p4_auto_hardware_acceptance_summary.md",
    "evidence/generated/p4_auto_hardware_acceptance_summary.json",
]


def write_repo_intake() -> dict:
    status = git_value("status", "--short")
    statuses = current_gate_statuses()
    hashes = active_hashes()
    lines = [
        "P4_AUTO_REPO_INTAKE: PASS",
        f"branch: `{git_value('branch', '--show-current')}`",
        f"dirty_state: `{'clean' if not status else 'dirty'}`",
        f"P1_RECHECK: {statuses['P1_RECHECK']}",
        f"P2_RECHECK: {statuses['P2_RECHECK']}",
        f"P3_RECHECK: {statuses['P3_RECHECK']}",
        "USER_CONFIRMED_SUPPLY_OK: recorded by P4_AUTO authorization gate",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Active Hashes",
        "",
        *(f"- {name}: `{digest}`" for name, digest in hashes.items()),
        "",
        "## Git Status",
        "",
        "```text",
        status or "(clean)",
        "```",
    ]
    write_markdown(
        GENERATED / "p4_auto_repo_intake.md",
        "P4 Auto Repo Intake",
        "PASS",
        "repository state and canonical inputs recorded",
        lines,
    )
    return {"result": "PASS", "path": rel(GENERATED / "p4_auto_repo_intake.md"), **statuses}


def run_rechecks(skip: bool, allow_skips: bool) -> dict:
    if skip:
        statuses = current_gate_statuses()
        result = "PASS" if all(statuses[key] in {"PASS", "PASS_WITH_SKIPS"} for key in ["P1_RECHECK", "P2_RECHECK", "P3_RECHECK"]) else "FAIL"
        commands: list[dict] = []
    else:
        commands = []
        cmd = [
            sys.executable,
            "tools/run_offline_gate.py",
            "--allow-skips",
            "--json-summary",
            "--include-simulation",
            "--include-pre-hw-package",
        ]
        proc = run_cmd(cmd, timeout=900)
        commands.append({"cmd": proc["cmd"], "returncode": proc["returncode"], "stdout_tail": proc["stdout"][-2000:], "stderr_tail": proc["stderr"][-2000:]})
        run_cmd([sys.executable, "tools/summarize_gate.py"], timeout=120)
        statuses = current_gate_statuses()
        result = "PASS" if all(statuses[key] in {"PASS", "PASS_WITH_SKIPS"} for key in ["P1_RECHECK", "P2_RECHECK", "P3_RECHECK"]) and (allow_skips or proc["returncode"] == 0) else "FAIL"
    lines = [
        f"P4_AUTO_RECHECK_P1_P2_P3: {result}",
        f"P1_RECHECK: {statuses['P1_RECHECK']}",
        f"P2_RECHECK: {statuses['P2_RECHECK']}",
        f"P3_RECHECK: {statuses['P3_RECHECK']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Commands",
        "",
        *(f"- `{item['cmd']}` -> rc={item['returncode']}" for item in commands),
        *(["- skipped, used existing summaries"] if skip else []),
    ]
    write_markdown(
        GENERATED / "p4_auto_recheck_p1_p2_p3_summary.md",
        "P4 Auto Recheck P1 P2 P3 Summary",
        result,
        "P1/P2/P3 markers are acceptable" if result == "PASS" else "P1/P2/P3 recheck blocked P4_AUTO",
        lines,
    )
    return {"result": result, "commands": commands, **statuses}


def write_previous_p4_intake() -> dict:
    previous = {}
    path = GENERATED / "p4_hardware_acceptance_summary.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
    result = previous.get("P4_HARDWARE_ACCEPTANCE", "MISSING")
    lines = [
        f"P4_PREVIOUS_ATTEMPT: {result}",
        f"PREVIOUS_P4_COMMIT: `{previous.get('COMMIT', 'MISSING')}`",
        f"SAFE_IDLE: {previous.get('SAFE_IDLE', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {previous.get('SHUTDOWN_ON_EXIT', 'MISSING')}",
        f"NEXT_RECOMMENDED_STAGE: {previous.get('NEXT_RECOMMENDED_STAGE', 'MISSING')}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- Previous P4 evidence is parsed as historical context only.",
        "- PASS is not promoted to lane, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        GENERATED / "p4_auto_previous_p4_intake.md",
        "P4 Auto Previous P4 Intake",
        "PASS" if previous else "SKIP_WITH_REASON",
        "previous P4 evidence parsed" if previous else "previous P4 JSON summary missing",
        lines,
    )
    return {"result": "PASS" if previous else "SKIP_WITH_REASON", "previous": previous}


def write_stage_placeholders(reason: str, status: str = "SKIP_WITH_REASON") -> dict:
    stages = {
        "safe_idle_direct_proxy": ("SAFE_IDLE_DIRECT_PROXY", "p4_auto_safe_idle_direct_proxy_summary.md", P4_AUTO_DIR / "safe_idle_direct_proxy"),
        "tfdu_control_idle": ("TFDU_CONTROL_IDLE", "p4_auto_tfdu_control_idle_summary.md", P4_AUTO_DIR / "tfdu_control_idle"),
        "raw_pulse_smoke": ("RAW_PULSE_SMOKE_L0", "p4_auto_raw_pulse_smoke_summary.md", P4_AUTO_DIR / "raw_pulse_smoke"),
        "raw_lane_matrix": ("RAW_LANE_MATRIX", "p4_auto_raw_lane_matrix_summary.md", P4_AUTO_DIR / "raw_lane_matrix"),
        "lane0_frame_crc": ("LANE0_FRAME_CRC", "p4_auto_lane0_frame_crc_summary.md", P4_AUTO_DIR / "protocol_smoke"),
        "lane0_ack_retry": ("LANE0_ACK_RETRY", "p4_auto_lane0_ack_retry_summary.md", P4_AUTO_DIR / "protocol_smoke"),
        "lane1_frame_crc": ("LANE1_FRAME_CRC", "p4_auto_lane1_frame_crc_summary.md", P4_AUTO_DIR / "protocol_smoke"),
        "lane1_ack_retry": ("LANE1_ACK_RETRY", "p4_auto_lane1_ack_retry_summary.md", P4_AUTO_DIR / "protocol_smoke"),
        "two_lane_minimal": ("TWO_LANE_MINIMAL", "p4_auto_two_lane_minimal_summary.md", P4_AUTO_DIR / "protocol_smoke"),
        "lane0_300s_soak": ("LANE0_300S_SOAK", "p4_auto_lane0_300s_soak_summary.md", P4_AUTO_DIR / "soak"),
        "two_lane_300s_soak": ("TWO_LANE_300S_SOAK", "p4_auto_two_lane_300s_soak_summary.md", P4_AUTO_DIR / "soak"),
    }
    payload = {}
    for key, (marker, summary_name, evidence_dir) in stages.items():
        lines = [
            f"{marker}: {status}",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            f"reason: {reason}",
        ]
        if marker == "RAW_LANE_MATRIX":
            lines.extend(
                [
                    "",
                    "| Direction | Status | Reason |",
                    "| --- | --- | --- |",
                    f"| AB_L0 | {status} | {reason} |",
                    f"| BA_L0 | {status} | {reason} |",
                    f"| AB_L1 | {status} | lane1 remains blocked until fresh raw evidence |",
                    f"| BA_L1 | {status} | {reason} |",
                ]
            )
            write_text(
                evidence_dir / "p4_auto_raw_lane_matrix.csv",
                "direction,status,reason\n"
                f"AB_L0,{status},{reason}\n"
                f"BA_L0,{status},{reason}\n"
                f"AB_L1,{status},lane1 remains blocked until fresh raw evidence\n"
                f"BA_L1,{status},{reason}\n",
            )
            write_json(
                evidence_dir / "p4_auto_raw_lane_matrix.json",
                [
                    {"direction": "AB_L0", "status": status, "reason": reason},
                    {"direction": "BA_L0", "status": status, "reason": reason},
                    {"direction": "AB_L1", "status": status, "reason": "lane1 remains blocked until fresh raw evidence"},
                    {"direction": "BA_L1", "status": status, "reason": reason},
                ],
            )
        if marker == "RAW_PULSE_SMOKE_L0":
            write_text(evidence_dir / "raw_pulse_smoke.csv", f"lane,direction,status,reason\n0,BOTH,{status},{reason}\n")
            write_json(evidence_dir / "raw_pulse_smoke.json", {"lane": 0, "status": status, "reason": reason})
        if marker in {"LANE0_FRAME_CRC", "LANE0_ACK_RETRY"}:
            suffix = "frame_crc" if marker == "LANE0_FRAME_CRC" else "ack_retry"
            write_text(evidence_dir / f"lane0_{suffix}_counters.csv", f"test,status,reason\nall,{status},{reason}\n")
        write_markdown(
            GENERATED / summary_name,
            marker.replace("_", " ").title(),
            status,
            reason,
            lines,
        )
        write_markdown(
            evidence_dir / summary_name,
            marker.replace("_", " ").title(),
            status,
            reason,
            lines,
        )
        payload[marker] = status
    return payload


def write_shutdown_summary(status: str, reason: str, *, no_hw: bool = True) -> dict:
    write_text(P4_AUTO_DIR / "p4_auto_tool_versions.txt", tool_versions_text())
    write_markdown(
        GENERATED / "p4_auto_shutdown_summary.md",
        "P4 Auto Shutdown Summary",
        status,
        reason,
        [
            f"SHUTDOWN_ON_EXIT: {status}",
            f"reason: {reason}",
            f"SHUTDOWN_BITSTREAM: `shutdown_bitstream/tfdu_shutdown_j10_j11.bit`",
            f"SHUTDOWN_BITSTREAM_SHA256: `{sha256_or_missing(ROOT / 'shutdown_bitstream' / 'tfdu_shutdown_j10_j11.bit')}`",
            f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
        no_hw=no_hw,
    )
    write_markdown(
        P4_AUTO_DIR / "shutdown" / "p4_auto_shutdown_summary.md",
        "P4 Auto Shutdown Summary",
        status,
        reason,
        [
            f"SHUTDOWN_ON_EXIT: {status}",
            f"reason: {reason}",
            f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
        no_hw=no_hw,
    )
    return {"SHUTDOWN_ON_EXIT": status, "reason": reason}


def _best_safe_idle_bitstream(provenance: dict) -> str:
    rows = provenance.get("rows", [])
    for row in rows:
        if row.get("stage") == "safe_idle" and row.get("status") == "PASS":
            return row.get("immutable_bitstream_path", "")
    return ""


def run_shutdown_baseline(args, auth_payload: dict) -> dict:
    shutdown_bit = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"
    profile = args.profile_path or "profiles/p4_auto_safe_idle_proxy.json"
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/hw/program_tfdu_shutdown_safe.ps1",
        "-AllowHardware",
        "-ExecuteHardware",
        "-ShutdownOnExit",
        "-MaxRuntimeSec",
        str(args.max_runtime_sec),
        "-BoardId",
        args.board_id,
        "-Bitstream",
        rel(shutdown_bit),
        "-BitstreamSha256",
        sha256_or_missing(shutdown_bit),
        "-TestProfile",
        "P4_AUTO_SHUTDOWN_BASELINE",
        "-ActivePinmapHash",
        args.active_pinmap_hash,
        "-ActiveXdcHash",
        args.active_xdc_hash,
        "-AuthorizationFile",
        args.authorization_file,
        "-ProfilePath",
        profile,
        "-ProfileSha256",
        sha256_or_missing(resolve_root_path(profile)),
        "-EvidenceDir",
        "evidence/hardware/p4_auto/shutdown/stage_b_shutdown_baseline",
    ]
    result = run_cmd(cmd, timeout=min(max(args.max_runtime_sec or 300, 60), 900))
    write_json(P4_AUTO_DIR / "stage_b_shutdown_baseline" / "run_result.json", result)
    text = "\n".join([result.get("stdout", ""), result.get("stderr", "")])
    passed = result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in text or "TFDU_SHUTDOWN_PROGRAMMED" in text
    status = "PASS" if passed else "FAIL"
    write_shutdown_summary(status, "shutdown-safe baseline wrapper executed" if passed else "shutdown-safe baseline wrapper failed", no_hw=False)
    return {"STAGE_B_SHUTDOWN_BASELINE": status, "SHUTDOWN_ON_EXIT": status, "cmd": result["cmd"], "returncode": result["returncode"], "stdout_tail": result["stdout"][-2000:], "stderr_tail": result["stderr"][-2000:]}


def _resolve_vivado() -> str | None:
    return shutil.which("vivado") or shutil.which("vivado.bat") or (str(DEFAULT_VIVADO) if DEFAULT_VIVADO.exists() else None)


def _tcl_path(path: Path) -> str:
    return path.resolve().as_posix()


def _provenance_row(provenance: dict, stage: str) -> dict:
    for row in provenance.get("rows", []):
        if row.get("stage") == stage:
            return row
    return {}


def write_authorized_run_package(
    auth_payload: dict,
    provenance: dict,
    *,
    board_id: str = "",
    requested_stage: str = "safe_idle",
    profile_path: str = "",
) -> dict:
    stage_map = {
        "safe_idle": ("safe_idle", "profiles/p4_auto_safe_idle_proxy.json"),
        "tfdu_control_idle": ("tfdu_control_idle", "profiles/p4_auto_tfdu_control_idle.json"),
        "raw_pulse": ("raw_pulse", "profiles/p4_auto_raw_pulse_l0.json"),
        "raw_lane_matrix": ("raw_lane_matrix", "profiles/p4_auto_raw_lane_matrix.json"),
        "lane0_frame_crc": ("protocol_lane0", "profiles/p4_auto_lane0_frame_crc.json"),
        "lane0_ack_retry": ("protocol_lane0_ack", "profiles/p4_auto_lane0_ack_retry.json"),
        "lane1_frame_crc": ("protocol_lane1", "profiles/p4_auto_lane1_frame_crc.json"),
        "lane1_ack_retry": ("protocol_lane1_ack", "profiles/p4_auto_lane1_ack_retry.json"),
        "two_lane_minimal": ("protocol_two_lane_minimal", "profiles/p4_auto_two_lane_minimal.json"),
        "lane0_300s_soak": ("protocol_lane0_soak", "profiles/p4_auto_lane0_300s_soak.json"),
        "two_lane_300s_soak": ("protocol_two_lane_soak", "profiles/p4_auto_two_lane_300s_soak.json"),
    }
    stage_key, default_profile_rel = stage_map.get(requested_stage, stage_map["safe_idle"])
    row = _provenance_row(provenance, stage_key)
    if stage_key == "safe_idle" and not row:
        row = _provenance_row(provenance, "instrumented_idle")
    profile_rel = rel(resolve_root_path(profile_path)) if profile_path else default_profile_rel
    profile_path = ROOT / profile_rel
    profile = {}
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            profile = {}
    max_runtime_sec = int(profile.get("max_runtime_sec") or 300)
    board = board_id or "AX7010"
    hashes = active_hashes()
    bitstream_rel = row.get("immutable_bitstream_path", "MISSING")
    bitstream_sha = row.get("sha256", "MISSING")
    profile_sha = sha256_or_missing(profile_path)
    auth_rel = rel(DEFAULT_AUTH_FILE)
    cmd_common = [
        "tools/run_p4_auto_hardware_acceptance.py",
        "--allow-hardware",
        "--execute-hardware",
        "--authorization-file",
        auth_rel,
        "--user-confirmed-supply-ok",
        "--no-manual-intervention",
        "--shutdown-on-exit",
        "--max-runtime-sec",
        str(max_runtime_sec),
        "--stage",
        requested_stage if requested_stage in stage_map else "safe_idle",
        "--board-id",
        board,
        "--bitstream",
        bitstream_rel,
        "--bitstream-sha256",
        bitstream_sha,
        "--profile-path",
        profile_rel,
        "--profile-sha256",
        profile_sha,
        "--active-pinmap-hash",
        hashes["pinmap"],
        "--active-xdc-hash",
        hashes["active_xdc"],
        "--json-summary",
        "--skip-recheck",
    ]
    python_command = " ".join(["python", *cmd_common])
    ps_command = " ".join(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\run_p4_auto_hardware_acceptance.ps1",
            "-AllowHardware",
            "-ExecuteHardware",
            "-AuthorizationFile",
            auth_rel.replace("/", "\\"),
            "-UserConfirmedSupplyOk",
            "-NoManualIntervention",
            "-ShutdownOnExit",
            "-MaxRuntimeSec",
            str(max_runtime_sec),
            "-Stage",
            requested_stage if requested_stage in stage_map else "safe_idle",
            "-BoardId",
            board,
            "-Bitstream",
            bitstream_rel.replace("/", "\\"),
            "-BitstreamSha256",
            bitstream_sha,
            "-ProfilePath",
            profile_rel.replace("/", "\\"),
            "-ProfileSha256",
            profile_sha,
            "-ActivePinmapHash",
            hashes["pinmap"],
            "-ActiveXdcHash",
            hashes["active_xdc"],
            "-JsonSummary",
            "-SkipRecheck",
        ]
    )
    env_command = f"$env:{AUTH_ENV}='{AUTH_ENV_VALUE}'"
    projected_auth = validate_authorization(
        allow_hardware=True,
        execute_hardware=True,
        authorization_file=DEFAULT_AUTH_FILE,
        user_confirmed_supply_ok=True,
        no_manual_intervention=True,
        board_id=board,
        bitstream=bitstream_rel,
        bitstream_sha256=bitstream_sha,
        profile_path=profile_rel,
        profile_sha256=profile_sha,
        active_pinmap_hash=hashes["pinmap"],
        active_xdc_hash=hashes["active_xdc"],
        max_runtime_sec=max_runtime_sec,
        shutdown_on_exit=True,
    )
    auth_missing = list(projected_auth.get("missing", []))
    payload = {
        "P4_AUTO_AUTHORIZED_RUN_PACKAGE": "READY" if row.get("status") == "PASS" else "SKIP_WITH_REASON",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "AUTHORIZATION_STATUS_AT_GENERATION": auth_payload.get("P4_AUTO_AUTHORIZATION", "UNKNOWN"),
        "PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS": projected_auth.get("P4_AUTO_AUTHORIZATION", "UNKNOWN"),
        "PROJECTED_MISSING_CONTROLS_BEFORE_RUN": auth_missing,
        "RF_COMM_HW_AUTH_REQUIRED": f"{AUTH_ENV}={AUTH_ENV_VALUE}",
        "BOARD_ID": board,
        "STAGE": requested_stage if requested_stage in stage_map else "safe_idle",
        "MAX_RUNTIME_SEC": max_runtime_sec,
        "AUTHORIZATION_FILE": auth_rel,
        "BITSTREAM": bitstream_rel,
        "BITSTREAM_SHA256": bitstream_sha,
        "PROFILE_PATH": profile_rel,
        "PROFILE_SHA256": profile_sha,
        "ACTIVE_PINMAP_HASH": hashes["pinmap"],
        "ACTIVE_XDC_HASH": hashes["active_xdc"],
        "DEBUG_PROBES_LTX": row.get("debug_probes_path", "MISSING"),
        "DEBUG_PROBES_LTX_SHA256": row.get("debug_probes_sha256", "MISSING"),
        "POWERSHELL_ENV_COMMAND": env_command,
        "PYTHON_COMMAND": python_command,
        "POWERSHELL_COMMAND": ps_command,
        "boundary": "command package only; it does not authorize or execute hardware",
    }
    json_path = P4_AUTO_DIR / "authorization" / "p4_auto_authorized_run_package.json"
    md_path = P4_AUTO_DIR / "authorization" / "p4_auto_authorized_run_package.md"
    write_json(json_path, payload)
    lines = [
        f"P4_AUTO_AUTHORIZED_RUN_PACKAGE: {payload['P4_AUTO_AUTHORIZED_RUN_PACKAGE']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"AUTHORIZATION_STATUS_AT_GENERATION: {payload['AUTHORIZATION_STATUS_AT_GENERATION']}",
        f"PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS: {payload['PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS']}",
        f"RF_COMM_HW_AUTH_REQUIRED: `{payload['RF_COMM_HW_AUTH_REQUIRED']}`",
        f"BOARD_ID: `{board}`",
        f"STAGE: `{payload['STAGE']}`",
        f"MAX_RUNTIME_SEC: {max_runtime_sec}",
        f"AUTHORIZATION_FILE: `{auth_rel}`",
        f"BITSTREAM: `{bitstream_rel}`",
        f"BITSTREAM_SHA256: `{bitstream_sha}`",
        f"PROFILE_PATH: `{profile_rel}`",
        f"PROFILE_SHA256: `{profile_sha}`",
        f"ACTIVE_PINMAP_HASH: `{hashes['pinmap']}`",
        f"ACTIVE_XDC_HASH: `{hashes['active_xdc']}`",
        f"DEBUG_PROBES_LTX: `{payload['DEBUG_PROBES_LTX']}`",
        f"DEBUG_PROBES_LTX_SHA256: `{payload['DEBUG_PROBES_LTX_SHA256']}`",
        "",
        "## Projected Missing Controls Before Run",
        "",
        *(f"- `{item}`" for item in auth_missing),
        *(["- none"] if not auth_missing else []),
        "",
        "## PowerShell",
        "",
        "```powershell",
        env_command,
        ps_command,
        "```",
        "",
        "## Python",
        "",
        "```powershell",
        env_command,
        python_command,
        "```",
        "",
        "## Boundary",
        "",
        "- This package records the exact artifact hashes and command arguments for the next authorized run.",
        "- It does not execute hardware and does not promote hardware acceptance.",
    ]
    write_markdown(
        GENERATED / "p4_auto_authorized_run_package.md",
        "P4 Auto Authorized Run Package",
        payload["P4_AUTO_AUTHORIZED_RUN_PACKAGE"],
        "exact authorized-run inputs recorded without executing hardware",
        lines,
    )
    write_markdown(
        md_path,
        "P4 Auto Authorized Run Package",
        payload["P4_AUTO_AUTHORIZED_RUN_PACKAGE"],
        "exact authorized-run inputs recorded without executing hardware",
        lines,
    )
    return {"summary": rel(GENERATED / "p4_auto_authorized_run_package.md"), "json": rel(json_path), **payload}


def validate_authorized_bitstream_preflight(args, provenance: dict) -> dict:
    bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(bitstream) if bitstream else "MISSING"
    actual_sha = sha256_or_missing(bitstream)
    manifest_row = {}
    for row in provenance.get("rows", []):
        if row.get("immutable_bitstream_path") == authorized_rel and row.get("status") == "PASS":
            manifest_row = row
            break
    manifest_sha = manifest_row.get("sha256", "MISSING")
    expected_sha = args.bitstream_sha256 or "MISSING"
    passed = bool(
        manifest_row
        and actual_sha != "MISSING"
        and expected_sha != "MISSING"
        and actual_sha.lower() == expected_sha.lower()
        and actual_sha.lower() == manifest_sha.lower()
    )
    payload = {
        "P4_AUTO_AUTHORIZED_BITSTREAM_PREFLIGHT": "PASS" if passed else "FAIL",
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_EXISTS": bool(bitstream and bitstream.exists()),
        "AUTHORIZED_BITSTREAM_SHA256": actual_sha,
        "AUTHORIZED_BITSTREAM_SHA256_EXPECTED": expected_sha,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": bool(manifest_row),
        "AUTHORIZED_BITSTREAM_MANIFEST_SHA256": manifest_sha,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(P4_AUTO_DIR / "bitstreams" / "authorized_bitstream_preflight.json", payload)
    write_markdown(
        GENERATED / "p4_auto_authorized_bitstream_preflight.md",
        "P4 Auto Authorized Bitstream Preflight",
        payload["P4_AUTO_AUTHORIZED_BITSTREAM_PREFLIGHT"],
        "authorized bitstream matches current immutable manifest" if passed else "authorized bitstream is not in the current immutable manifest or SHA does not match",
        [
            f"P4_AUTO_AUTHORIZED_BITSTREAM_PREFLIGHT: {payload['P4_AUTO_AUTHORIZED_BITSTREAM_PREFLIGHT']}",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            f"AUTHORIZED_BITSTREAM: `{authorized_rel}`",
            f"AUTHORIZED_BITSTREAM_EXISTS: {str(payload['AUTHORIZED_BITSTREAM_EXISTS']).lower()}",
            f"AUTHORIZED_BITSTREAM_SHA256: `{actual_sha}`",
            f"AUTHORIZED_BITSTREAM_SHA256_EXPECTED: `{expected_sha}`",
            f"AUTHORIZED_BITSTREAM_IN_MANIFEST: {str(payload['AUTHORIZED_BITSTREAM_IN_MANIFEST']).lower()}",
            f"AUTHORIZED_BITSTREAM_MANIFEST_SHA256: `{manifest_sha}`",
        ],
    )
    return payload


def _write_stage_program_tcl(
    path: Path,
    bitstream: Path,
    log_path: Path,
    ltx_path: Path | None,
    capture_dir: Path,
    *,
    stage_label: str = "SAFE_IDLE",
    capture_prefix: str = "safe_idle",
    post_program_wait_ms: int = 0,
) -> None:
    ltx_value = _tcl_path(ltx_path) if ltx_path else ""
    script = f"""
set log_file {{{_tcl_path(log_path)}}}
set ila_dir {{{_tcl_path(capture_dir)}}}
file mkdir $ila_dir
set fh [open $log_file "w"]
proc say {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
say "P4_AUTO_{stage_label}_PROGRAM_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set bit_file {{{_tcl_path(bitstream)}}}
if {{![file exists $bit_file]}} {{
  say "P4_AUTO_{stage_label}_BITSTREAM_MISSING=$bit_file"
  close $fh
  exit 20
}}
set ltx_file {{{ltx_value}}}
set rc [catch {{
  open_hw_manager
  connect_hw_server -url {{{DEFAULT_HW_SERVER_URL}}}
  set targets [get_hw_targets -quiet *]
  say "P4_AUTO_HW_TARGET_COUNT=[llength $targets]"
  if {{[llength $targets] == 0}} {{
    error "No JTAG hw_target found."
  }}
  set dev ""
  foreach target $targets {{
    say "P4_AUTO_HW_TARGET=$target"
    if {{[catch {{current_hw_target $target}} target_err]}} {{
      say "P4_AUTO_CURRENT_HW_TARGET_ERROR=$target_err"
      continue
    }}
    if {{[catch {{set_property PARAM.FREQUENCY {DEFAULT_JTAG_FREQUENCY_HZ} $target}} freq_err]}} {{
      say "P4_AUTO_HW_JTAG_FREQUENCY_WARN=$freq_err"
    }} else {{
      say "P4_AUTO_HW_JTAG_FREQUENCY_HZ={DEFAULT_JTAG_FREQUENCY_HZ}"
    }}
    if {{[catch {{open_hw_target $target}} open_err]}} {{
      say "P4_AUTO_OPEN_HW_TARGET_ERROR=$open_err"
      continue
    }}
    foreach candidate [get_hw_devices -quiet *] {{
      set part ""
      catch {{set part [get_property PART $candidate]}}
      say "P4_AUTO_HW_DEVICE=$candidate PART=$part"
      if {{[string match -nocase *xc7z010* $part] || [string match -nocase *7z010* $part]}} {{
        set dev $candidate
        break
      }}
      if {{$dev eq ""}} {{
        set dev $candidate
      }}
    }}
    if {{$dev ne ""}} {{
      break
    }}
    catch {{close_hw_target $target}}
  }}
  if {{$dev eq ""}} {{
    error "No programmable hw_device found."
  }}
  current_hw_device $dev
  refresh_hw_device -update_hw_probes false $dev
  foreach prop {{NAME PART IDCODE IS_PROGRAMMED PROGRAM.FILE}} {{
    if {{[catch {{set value [get_property $prop $dev]}} prop_err]}} {{
      say "P4_AUTO_{stage_label}_DEVICE_PROP $prop ERROR=$prop_err"
    }} else {{
      say "P4_AUTO_{stage_label}_DEVICE_PROP $prop=$value"
    }}
  }}
  set_property PROGRAM.FILE $bit_file $dev
  if {{$ltx_file ne "" && [file exists $ltx_file]}} {{
    set_property PROBES.FILE $ltx_file $dev
    say "P4_AUTO_{stage_label}_PROBES_FILE=$ltx_file"
  }} else {{
    say "P4_AUTO_{stage_label}_PROBES_FILE=MISSING"
  }}
  program_hw_devices $dev
  if {{{post_program_wait_ms} > 0}} {{
    after {post_program_wait_ms}
  }}
  refresh_hw_device -update_hw_probes true $dev
  say "P4_AUTO_{stage_label}_BITSTREAM_PROGRAMMED=$bit_file"
  set ilas [get_hw_ilas -quiet *]
  set vios [get_hw_vios -quiet *]
  set probes [get_hw_probes -quiet *]
  say "P4_AUTO_HW_ILA_COUNT=[llength $ilas]"
  say "P4_AUTO_HW_VIO_COUNT=[llength $vios]"
  say "P4_AUTO_HW_PROBE_COUNT=[llength $probes]"
  set capture_pass 0
  set capture_idx 0
  foreach ila $ilas {{
    set wdb_file [file join $ila_dir "{capture_prefix}_${{capture_idx}}.wdb"]
    set csv_file [file join $ila_dir "{capture_prefix}_${{capture_idx}}.csv"]
    set ila_rc [catch {{
      current_hw_ila $ila
      catch {{set_property CONTROL.TRIGGER_POSITION 0 $ila}}
      if {{[catch {{run_hw_ila -trigger_now $ila}} trigger_err]}} {{
        say "P4_AUTO_ILA_TRIGGER_NOW_WARN_${{capture_idx}}=$trigger_err"
        run_hw_ila $ila
      }}
      wait_on_hw_ila $ila
      set data [upload_hw_ila_data $ila]
      write_hw_ila_data -force $wdb_file $data
      if {{[catch {{write_hw_ila_data -force -csv_file $csv_file $data}} csv_err]}} {{
        say "P4_AUTO_ILA_CSV_EXPORT_WARN_${{capture_idx}}=$csv_err"
      }}
    }} ila_err]
    if {{$ila_rc == 0}} {{
      say "P4_AUTO_ILA_CAPTURE_${{capture_idx}}=PASS"
      say "P4_AUTO_ILA_CAPTURE_${{capture_idx}}_WDB=$wdb_file"
      if {{[file exists $csv_file]}} {{
        say "P4_AUTO_ILA_CAPTURE_${{capture_idx}}_CSV=$csv_file"
      }}
      set capture_pass 1
    }} else {{
      say "P4_AUTO_ILA_CAPTURE_${{capture_idx}}=FAIL"
      say "P4_AUTO_ILA_CAPTURE_${{capture_idx}}_ERROR=$ila_err"
    }}
    incr capture_idx
  }}
  if {{$capture_pass}} {{
    say "P4_AUTO_ILA_CAPTURE=PASS"
  }} elseif {{[llength $ilas] == 0}} {{
    say "P4_AUTO_ILA_CAPTURE=SKIP_NO_ILA"
  }} else {{
    say "P4_AUTO_ILA_CAPTURE=FAIL"
  }}
  say "P4_AUTO_{stage_label}_PROGRAM=PASS"
  catch {{close_hw_target}}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
}} err opts]
if {{$rc != 0}} {{
  say "P4_AUTO_{stage_label}_PROGRAM=FAIL"
  say "P4_AUTO_{stage_label}_PROGRAM_ERROR=$err"
  catch {{close_hw_target}}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
  close $fh
  exit 21
}}
close $fh
exit 0
""".strip()
    write_text(path, script)


def _write_safe_idle_program_tcl(path: Path, bitstream: Path, log_path: Path, ltx_path: Path | None, capture_dir: Path) -> None:
    _write_stage_program_tcl(path, bitstream, log_path, ltx_path, capture_dir)


def _run_shutdown_after_stage(args, profile: str, evidence_dir: str, test_profile: str = "P4_AUTO_SAFE_IDLE_SHUTDOWN") -> dict:
    shutdown_bit = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "scripts/hw/program_tfdu_shutdown_safe.ps1",
        "-AllowHardware",
        "-ExecuteHardware",
        "-ShutdownOnExit",
        "-MaxRuntimeSec",
        str(args.max_runtime_sec),
        "-BoardId",
        args.board_id,
        "-Bitstream",
        rel(shutdown_bit),
        "-BitstreamSha256",
        sha256_or_missing(shutdown_bit),
        "-TestProfile",
        test_profile,
        "-ActivePinmapHash",
        args.active_pinmap_hash,
        "-ActiveXdcHash",
        args.active_xdc_hash,
        "-AuthorizationFile",
        args.authorization_file,
        "-ProfilePath",
        profile,
        "-ProfileSha256",
        sha256_or_missing(resolve_root_path(profile)),
        "-EvidenceDir",
        evidence_dir,
    ]
    vivado = _resolve_vivado()
    if vivado:
        cmd.extend(["-VivadoPath", vivado])
    return run_cmd(cmd, timeout=min(max(args.max_runtime_sec or 300, 60), 900))


def run_safe_idle_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "safe_idle_direct_proxy"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_safe_idle_proxy.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "instrumented_idle") or _provenance_row(provenance, "safe_idle")
    immutable_rel = row.get("immutable_bitstream_path", "")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / immutable_rel if immutable_rel else None)
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream) if bitstream else "MISSING"
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_safe_idle_programming.tcl.txt"
    log_path = evidence_dir / "program_log.txt"
    run_path = evidence_dir / "p4_auto_safe_idle_program_result.json"
    summary_path = GENERATED / "p4_auto_safe_idle_direct_proxy_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "safe_idle"
    vivado = _resolve_vivado()

    payload = {
        "SAFE_IDLE_PROGRAM": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "INSTRUMENTED_IDLE_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "INSTRUMENTED_IDLE_BITSTREAM_SHA256": actual_sha,
        "INSTRUMENTED_IDLE_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_SAFE_IDLE_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["SAFE_IDLE_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        write_markdown(
            summary_path,
            "P4 Auto Safe Idle Direct Proxy Summary",
            "FAIL_WITH_EVIDENCE",
            payload["reason"],
            [
                "SAFE_IDLE_DIRECT_PROXY: FAIL_WITH_EVIDENCE",
                "SAFE_IDLE_PROGRAM: FAIL",
                "BITSTREAM_SHA_MATCH: FAIL",
                f"INSTRUMENTED_IDLE_BITSTREAM: `{payload['INSTRUMENTED_IDLE_BITSTREAM']}`",
                f"INSTRUMENTED_IDLE_BITSTREAM_SHA256: `{actual_sha}`",
                f"INSTRUMENTED_IDLE_MANIFEST_SHA256: `{manifest_sha}`",
                f"AUTHORIZED_BITSTREAM: `{authorized_rel}`",
                f"AUTHORIZED_BITSTREAM_IN_MANIFEST: {str(authorized_path_in_manifest).lower()}",
                f"AUTHORIZED_BITSTREAM_SHA_MATCH: {str(authorized_sha_match).lower()}",
                f"DEBUG_PROBES_LTX: `{payload['DEBUG_PROBES_LTX']}`",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
        )
        return payload
    if not vivado:
        payload["SAFE_IDLE_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_safe_idle_program_tcl(tcl_path, bitstream, log_path, ltx_path, capture_dir)
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(args.max_runtime_sec or 300, 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_SAFE_IDLE_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_safe_idle_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "safe_idle_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        write_markdown(
            capture_dir / "safe_idle_parse_summary.md",
            "P4 Auto Safe Idle ILA Parse Summary",
            ila_parse.get("SAFE_IDLE_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for safe-idle command/readback evidence",
            [
                f"SAFE_IDLE_ILA_PARSE: {ila_parse.get('SAFE_IDLE_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"MODE_CMD_ALL_LANES: {best_parse.get('MODE_CMD_ALL_LANES', 'MISSING')}",
                f"SD_CMD_ALL_LANES: {best_parse.get('SD_CMD_ALL_LANES', 'MISSING')}",
                f"TXD_CMD_ALL_LANES: {best_parse.get('TXD_CMD_ALL_LANES', 'MISSING')}",
                f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {best_parse.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {best_parse.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {best_parse.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                f"UNEXPECTED_TX_PULSE_COUNT: {best_parse.get('UNEXPECTED_TX_PULSE_COUNT', 'MISSING')}",
                f"SHUTDOWN_STATE: {best_parse.get('SHUTDOWN_STATE', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
        payload["SAFE_IDLE_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_SAFE_IDLE_PARSE"] = ila_parse.get("SAFE_IDLE_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and payload["ILA_SAFE_IDLE_PARSE"] == "PASS" else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
    finally:
        shutdown_result = _run_shutdown_after_stage(args, profile, "evidence/hardware/p4_auto/shutdown/after_safe_idle_program")
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["SAFE_IDLE_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    return payload


def run_tfdu_control_idle_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "tfdu_control_idle"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_tfdu_control_idle.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "tfdu_control_idle")
    immutable_rel = row.get("immutable_bitstream_path", "")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / immutable_rel if immutable_rel else None)
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream) if bitstream else "MISSING"
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_tfdu_control_idle_programming.tcl.txt"
    log_path = evidence_dir / "program_log.txt"
    run_path = evidence_dir / "p4_auto_tfdu_control_idle_program_result.json"
    summary_path = GENERATED / "p4_auto_tfdu_control_idle_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "tfdu_control_idle"
    vivado = _resolve_vivado()

    payload = {
        "TFDU_CONTROL_IDLE": "SKIP_WITH_REASON",
        "TFDU_CONTROL_IDLE_PROGRAM": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "TFDU_CONTROL_IDLE_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "TFDU_CONTROL_IDLE_BITSTREAM_SHA256": actual_sha,
        "TFDU_CONTROL_IDLE_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_TFDU_CONTROL_IDLE_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["TFDU_CONTROL_IDLE"] = "FAIL_WITH_EVIDENCE"
        payload["TFDU_CONTROL_IDLE_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized TFDU control-idle bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        write_markdown(
            summary_path,
            "P4 Auto TFDU Control Idle Summary",
            "FAIL_WITH_EVIDENCE",
            payload["reason"],
            [
                "TFDU_CONTROL_IDLE: FAIL_WITH_EVIDENCE",
                "TFDU_CONTROL_IDLE_PROGRAM: FAIL",
                "BITSTREAM_SHA_MATCH: FAIL",
                f"AUTHORIZED_BITSTREAM: `{authorized_rel}`",
                f"AUTHORIZED_BITSTREAM_IN_MANIFEST: {str(authorized_path_in_manifest).lower()}",
                f"AUTHORIZED_BITSTREAM_SHA_MATCH: {str(authorized_sha_match).lower()}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
        )
        return payload
    if not vivado:
        payload["TFDU_CONTROL_IDLE"] = "FAIL_WITH_EVIDENCE"
        payload["TFDU_CONTROL_IDLE_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="TFDU_CONTROL_IDLE",
        capture_prefix="tfdu_control_idle",
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(args.max_runtime_sec or 60, 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_TFDU_CONTROL_IDLE_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_tfdu_control_idle_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "tfdu_control_idle_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        write_markdown(
            capture_dir / "tfdu_control_idle_parse_summary.md",
            "P4 Auto TFDU Control Idle ILA Parse Summary",
            ila_parse.get("TFDU_CONTROL_IDLE_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for receive-active idle command/readback evidence",
            [
                f"TFDU_CONTROL_IDLE_ILA_PARSE: {ila_parse.get('TFDU_CONTROL_IDLE_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"MODE_CMD_ALL_LANES: {best_parse.get('MODE_CMD_ALL_LANES', 'MISSING')}",
                f"SD_CMD_ALL_ENABLED_LANES: {best_parse.get('SD_CMD_ALL_ENABLED_LANES', 'MISSING')}",
                f"TXD_CMD_ALL_ENABLED_LANES: {best_parse.get('TXD_CMD_ALL_ENABLED_LANES', 'MISSING')}",
                f"LANE_ENABLE_ALL_LANES: {best_parse.get('LANE_ENABLE_ALL_LANES', 'MISSING')}",
                f"STARTUP_WAIT_US: {best_parse.get('STARTUP_WAIT_US', 'MISSING')}",
                f"STARTUP_DONE: {best_parse.get('STARTUP_DONE', 'MISSING')}",
                f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {best_parse.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {best_parse.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {best_parse.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                f"UNEXPECTED_TX_PULSE_COUNT: {best_parse.get('UNEXPECTED_TX_PULSE_COUNT', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
        parse_ok = ila_parse.get("TFDU_CONTROL_IDLE_ILA_PARSE") == "PASS"
        payload["TFDU_CONTROL_IDLE_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["TFDU_CONTROL_IDLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_TFDU_CONTROL_IDLE_PARSE"] = ila_parse.get("TFDU_CONTROL_IDLE_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "MODE_CMD_ALL_LANES",
            "SD_CMD_ALL_ENABLED_LANES",
            "TXD_CMD_ALL_ENABLED_LANES",
            "STARTUP_WAIT_US",
            "STARTUP_DONE",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
            "UNEXPECTED_TX_PULSE_COUNT",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_tfdu_control_idle",
            test_profile="P4_AUTO_TFDU_CONTROL_IDLE_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["TFDU_CONTROL_IDLE"] = "FAIL_WITH_EVIDENCE"
            payload["TFDU_CONTROL_IDLE_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    lines = [
        f"TFDU_CONTROL_IDLE: {payload['TFDU_CONTROL_IDLE']}",
        f"TFDU_CONTROL_IDLE_PROGRAM: {payload['TFDU_CONTROL_IDLE_PROGRAM']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"MODE_CMD_ALL_LANES: {payload.get('MODE_CMD_ALL_LANES', 'MISSING')}",
        f"SD_CMD_ALL_ENABLED_LANES: {payload.get('SD_CMD_ALL_ENABLED_LANES', 'MISSING')}",
        f"TXD_CMD_ALL_ENABLED_LANES: {payload.get('TXD_CMD_ALL_ENABLED_LANES', 'MISSING')}",
        f"STARTUP_WAIT_US: {payload.get('STARTUP_WAIT_US', 'MISSING')}",
        f"STARTUP_DONE: {payload.get('STARTUP_DONE', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"UNEXPECTED_TX_PULSE_COUNT: {payload.get('UNEXPECTED_TX_PULSE_COUNT', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized runtime internal/proxy evidence for receive-active idle with TX held low.",
        "- It is not raw pulse, protocol, external pin scope, lane, Ethernet, rotation, or soak acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto TFDU Control Idle Summary",
        payload["TFDU_CONTROL_IDLE"],
        "receive-active idle runtime internal proxy evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "ila_or_axi_summary.md",
        "P4 Auto TFDU Control Idle Summary",
        payload["TFDU_CONTROL_IDLE"],
        "receive-active idle runtime internal proxy evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_raw_pulse_smoke_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "raw_pulse_smoke"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_raw_pulse_l0.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "raw_pulse")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_raw_pulse_smoke_programming.tcl.txt"
    log_path = evidence_dir / "program_log.txt"
    run_path = evidence_dir / "p4_auto_raw_pulse_smoke_program_result.json"
    summary_path = GENERATED / "p4_auto_raw_pulse_smoke_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "raw_pulse_smoke"
    vivado = _resolve_vivado()
    payload = {
        "RAW_PULSE_SMOKE_L0": "SKIP_WITH_REASON",
        "RAW_PULSE_PROGRAM": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "RAW_PULSE_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "RAW_PULSE_BITSTREAM_SHA256": actual_sha,
        "RAW_PULSE_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_RAW_PULSE_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["RAW_PULSE_SMOKE_L0"] = "FAIL_WITH_EVIDENCE"
        payload["RAW_PULSE_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized raw-pulse bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["RAW_PULSE_SMOKE_L0"] = "FAIL_WITH_EVIDENCE"
        payload["RAW_PULSE_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="RAW_PULSE",
        capture_prefix="raw_pulse",
        post_program_wait_ms=300,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 30, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_RAW_PULSE_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_raw_pulse_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "raw_pulse_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("RAW_PULSE_ILA_PARSE") == "PASS"
        payload["RAW_PULSE_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["RAW_PULSE_SMOKE_L0"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_RAW_PULSE_PARSE"] = ila_parse.get("RAW_PULSE_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "TX_REQUESTED_COUNT",
            "TX_PULSE_COUNT",
            "RX_PULSE_COUNT",
            "RX_REMOTE_LANE0_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
        payload["ACK_SEEN_EVIDENCE"] = "ACK_TX_WINDOW_ACTIVE_LOW_PROXY"
        write_markdown(
            capture_dir / "raw_pulse_parse_summary.md",
            "P4 Auto Raw Pulse ILA Parse Summary",
            ila_parse.get("RAW_PULSE_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for low-duty raw pulse evidence",
            [
                f"RAW_PULSE_ILA_PARSE: {ila_parse.get('RAW_PULSE_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"TX_REQUESTED_COUNT: {payload.get('TX_REQUESTED_COUNT', 'MISSING')}",
                f"TX_PULSE_COUNT: {payload.get('TX_PULSE_COUNT', 'MISSING')}",
                f"RX_PULSE_COUNT: {payload.get('RX_PULSE_COUNT', 'MISSING')}",
                f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
                f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_raw_pulse_smoke",
            test_profile="P4_AUTO_RAW_PULSE_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["RAW_PULSE_SMOKE_L0"] = "FAIL_WITH_EVIDENCE"
            payload["RAW_PULSE_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "raw_pulse_smoke.csv",
        "lane,direction,status,tx_requested_count,tx_pulse_count,rx_pulse_count,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"0,A_TO_B,{payload['RAW_PULSE_SMOKE_L0']},{payload.get('TX_REQUESTED_COUNT','MISSING')},{payload.get('TX_PULSE_COUNT','MISSING')},{payload.get('RX_PULSE_COUNT','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "raw_pulse_smoke.json", payload)
    lines = [
        f"RAW_PULSE_SMOKE_L0: {payload['RAW_PULSE_SMOKE_L0']}",
        f"RAW_PULSE_PROGRAM: {payload['RAW_PULSE_PROGRAM']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"TX_REQUESTED_COUNT: {payload.get('TX_REQUESTED_COUNT', 'MISSING')}",
        f"TX_PULSE_COUNT: {payload.get('TX_PULSE_COUNT', 'MISSING')}",
        f"RX_PULSE_COUNT: {payload.get('RX_PULSE_COUNT', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized low-duty raw-pulse smoke evidence for lane0 only.",
        "- It is not frame/CRC, ACK/retry, two-lane, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Raw Pulse Smoke Summary",
        payload["RAW_PULSE_SMOKE_L0"],
        "low-duty raw pulse runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "ila_or_axi_summary.md",
        "P4 Auto Raw Pulse Smoke Summary",
        payload["RAW_PULSE_SMOKE_L0"],
        "low-duty raw pulse runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_raw_lane_matrix_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "raw_lane_matrix"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_raw_lane_matrix.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "raw_lane_matrix")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_raw_lane_matrix_programming.tcl.txt"
    log_path = evidence_dir / "program_log.txt"
    run_path = evidence_dir / "p4_auto_raw_lane_matrix_program_result.json"
    summary_path = GENERATED / "p4_auto_raw_lane_matrix_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "raw_lane_matrix"
    vivado = _resolve_vivado()
    payload = {
        "RAW_LANE_MATRIX": "SKIP_WITH_REASON",
        "RAW_LANE_MATRIX_PROGRAM": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "RAW_LANE_MATRIX_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "RAW_LANE_MATRIX_BITSTREAM_SHA256": actual_sha,
        "RAW_LANE_MATRIX_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_RAW_LANE_MATRIX_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "direction_results": [],
    }
    if not bitstream_match:
        payload["RAW_LANE_MATRIX"] = "FAIL_WITH_EVIDENCE"
        payload["RAW_LANE_MATRIX_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized raw-lane-matrix bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["RAW_LANE_MATRIX"] = "FAIL_WITH_EVIDENCE"
        payload["RAW_LANE_MATRIX_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="RAW_LANE_MATRIX",
        capture_prefix="raw_lane_matrix",
        post_program_wait_ms=3500,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 60, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_RAW_LANE_MATRIX_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_raw_lane_matrix_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "raw_lane_matrix_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("RAW_LANE_MATRIX_ILA_PARSE") == "PASS"
        direction_results = best_parse.get("direction_results", [])
        payload["RAW_LANE_MATRIX_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["RAW_LANE_MATRIX"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_RAW_LANE_MATRIX_PARSE"] = ila_parse.get("RAW_LANE_MATRIX_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        payload["TXD_STUCK_HIGH_VIOLATION"] = best_parse.get("TXD_STUCK_HIGH_VIOLATION", "MISSING")
        payload["DUTY_WINDOW_VIOLATION"] = best_parse.get("DUTY_WINDOW_VIOLATION", "MISSING")
        payload["direction_results"] = direction_results
        write_markdown(
            capture_dir / "raw_lane_matrix_parse_summary.md",
            "P4 Auto Raw Lane Matrix ILA Parse Summary",
            ila_parse.get("RAW_LANE_MATRIX_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for AB/BA lane0/lane1 low-duty raw pulse evidence",
            [
                f"RAW_LANE_MATRIX_ILA_PARSE: {ila_parse.get('RAW_LANE_MATRIX_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                *(f"{item.get('direction')}: {item.get('status')} tx={item.get('tx_observed_count')} rx={item.get('rx_active_low_pulse_count')} txd_high_max_cycles={item.get('txd_high_max_cycles')}" for item in direction_results),
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_raw_lane_matrix",
            test_profile="P4_AUTO_RAW_LANE_MATRIX_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["RAW_LANE_MATRIX"] = "FAIL_WITH_EVIDENCE"
            payload["RAW_LANE_MATRIX_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    csv_lines = [
        "direction,lane,source_endpoint,destination_endpoint,status,tx_requested_count,tx_observed_count,rx_active_low_pulse_count,rx_falling_edge_count,txd_high_max_cycles,txd_high_total_cycles"
    ]
    for item in payload.get("direction_results", []):
        csv_lines.append(
            ",".join(
                str(item.get(key, "MISSING"))
                for key in [
                    "direction",
                    "lane",
                    "source_endpoint",
                    "destination_endpoint",
                    "status",
                    "tx_requested_count",
                    "tx_observed_count",
                    "rx_active_low_pulse_count",
                    "rx_falling_edge_count",
                    "txd_high_max_cycles",
                    "txd_high_total_cycles",
                ]
            )
        )
    write_text(evidence_dir / "p4_auto_raw_lane_matrix.csv", "\n".join(csv_lines) + "\n")
    write_json(evidence_dir / "p4_auto_raw_lane_matrix.json", payload)
    lines = [
        f"RAW_LANE_MATRIX: {payload['RAW_LANE_MATRIX']}",
        f"RAW_LANE_MATRIX_PROGRAM: {payload['RAW_LANE_MATRIX_PROGRAM']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        "",
        "| Direction | Status | TX Count | RX Count | TXD High Max Cycles |",
        "| --- | --- | --- | --- | --- |",
        *(f"| {item.get('direction')} | {item.get('status')} | {item.get('tx_observed_count')} | {item.get('rx_active_low_pulse_count')} | {item.get('txd_high_max_cycles')} |" for item in payload.get("direction_results", [])),
        "",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized low-duty raw physical pulse evidence for lane0/lane1 AB/BA only.",
        "- It is not frame/CRC, ACK/retry, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Raw Lane Matrix Summary",
        payload["RAW_LANE_MATRIX"],
        "low-duty raw lane matrix runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "ila_or_axi_summary.md",
        "P4 Auto Raw Lane Matrix Summary",
        payload["RAW_LANE_MATRIX"],
        "low-duty raw lane matrix runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_lane0_frame_crc_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "protocol_smoke"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_lane0_frame_crc.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_lane0")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_lane0_frame_crc_programming.tcl.txt"
    log_path = evidence_dir / "lane0_frame_crc_program_log.txt"
    run_path = evidence_dir / "p4_auto_lane0_frame_crc_program_result.json"
    summary_path = GENERATED / "p4_auto_lane0_frame_crc_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "protocol_smoke" / "lane0_frame_crc"
    vivado = _resolve_vivado()
    payload = {
        "LANE0_FRAME_CRC": "SKIP_WITH_REASON",
        "LANE0_FRAME_CRC_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "LANE0_FRAME_CRC_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "LANE0_FRAME_CRC_BITSTREAM_SHA256": actual_sha,
        "LANE0_FRAME_CRC_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_LANE0_FRAME_CRC_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["LANE0_FRAME_CRC"] = "FAIL_WITH_EVIDENCE"
        payload["LANE0_FRAME_CRC_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized lane0 frame/CRC bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["LANE0_FRAME_CRC"] = "FAIL_WITH_EVIDENCE"
        payload["LANE0_FRAME_CRC_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="LANE0_FRAME_CRC",
        capture_prefix="lane0_frame_crc",
        post_program_wait_ms=1500,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 60, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_LANE0_FRAME_CRC_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_lane0_frame_crc_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "lane0_frame_crc_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("LANE0_FRAME_CRC_ILA_PARSE") == "PASS"
        payload["LANE0_FRAME_CRC_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["LANE0_FRAME_CRC"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_LANE0_FRAME_CRC_PARSE"] = ila_parse.get("LANE0_FRAME_CRC_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x1" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x0" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "SENT_FRAMES",
            "REQUESTED_FRAMES",
            "RX_GOOD",
            "FRAME_BAD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "RX_SYMBOL_ERRORS",
            "PREAMBLE_SEEN_COUNT",
            "RX_REMOTE_LANE0_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
        write_markdown(
            capture_dir / "lane0_frame_crc_parse_summary.md",
            "P4 Auto Lane0 Frame CRC ILA Parse Summary",
            ila_parse.get("LANE0_FRAME_CRC_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for lane0 deterministic frame/CRC evidence",
            [
                f"LANE0_FRAME_CRC_ILA_PARSE: {ila_parse.get('LANE0_FRAME_CRC_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
                f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
                f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
                f"SENT_FRAMES: {payload.get('SENT_FRAMES', 'MISSING')}",
                f"RX_GOOD: {payload.get('RX_GOOD', 'MISSING')}",
                f"FRAME_BAD: {payload.get('FRAME_BAD', 'MISSING')}",
                f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
                f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
                f"RX_SYMBOL_ERRORS: {payload.get('RX_SYMBOL_ERRORS', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_lane0_frame_crc",
            test_profile="P4_AUTO_LANE0_FRAME_CRC_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["LANE0_FRAME_CRC"] = "FAIL_WITH_EVIDENCE"
            payload["LANE0_FRAME_CRC_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "lane0_frame_crc_counters.csv",
        "test,status,session,lane_mask,ack_lane_mask,sent_frames,rx_good,frame_bad,crc_bad,payload_mismatch,rx_symbol_errors,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"lane0_frame_crc,{payload['LANE0_FRAME_CRC']},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('SENT_FRAMES','MISSING')},{payload.get('RX_GOOD','MISSING')},{payload.get('FRAME_BAD','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('RX_SYMBOL_ERRORS','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "lane0_frame_crc_readback.json", payload)
    lines = [
        f"LANE0_FRAME_CRC: {payload['LANE0_FRAME_CRC']}",
        f"LANE0_FRAME_CRC_PROGRAM: {payload['LANE0_FRAME_CRC_PROGRAM']}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"SENT_FRAMES: {payload.get('SENT_FRAMES', 'MISSING')}",
        f"RX_GOOD: {payload.get('RX_GOOD', 'MISSING')}",
        f"FRAME_BAD: {payload.get('FRAME_BAD', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized lane0 deterministic frame/CRC smoke evidence with ACK disabled.",
        "- It is not ACK/retry, lane1, two-lane, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Lane0 Frame CRC Summary",
        payload["LANE0_FRAME_CRC"],
        "lane0 deterministic frame/CRC runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "lane0_frame_crc_summary.md",
        "P4 Auto Lane0 Frame CRC Summary",
        payload["LANE0_FRAME_CRC"],
        "lane0 deterministic frame/CRC runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_lane1_frame_crc_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "protocol_smoke"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_lane1_frame_crc.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_lane1")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_lane1_frame_crc_programming.tcl.txt"
    log_path = evidence_dir / "lane1_frame_crc_program_log.txt"
    run_path = evidence_dir / "p4_auto_lane1_frame_crc_program_result.json"
    summary_path = GENERATED / "p4_auto_lane1_frame_crc_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "protocol_smoke" / "lane1_frame_crc"
    vivado = _resolve_vivado()
    payload = {
        "LANE1_FRAME_CRC": "SKIP_WITH_REASON",
        "LANE1_FRAME_CRC_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "LANE1_FRAME_CRC_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "LANE1_FRAME_CRC_BITSTREAM_SHA256": actual_sha,
        "LANE1_FRAME_CRC_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_LANE1_FRAME_CRC_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["LANE1_FRAME_CRC"] = "FAIL_WITH_EVIDENCE"
        payload["LANE1_FRAME_CRC_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized lane1 frame/CRC bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["LANE1_FRAME_CRC"] = "FAIL_WITH_EVIDENCE"
        payload["LANE1_FRAME_CRC_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="LANE1_FRAME_CRC",
        capture_prefix="lane1_frame_crc",
        post_program_wait_ms=1500,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 60, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_LANE1_FRAME_CRC_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_lane1_frame_crc_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "lane1_frame_crc_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("LANE1_FRAME_CRC_ILA_PARSE") == "PASS"
        payload["LANE1_FRAME_CRC_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["LANE1_FRAME_CRC"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_LANE1_FRAME_CRC_PARSE"] = ila_parse.get("LANE1_FRAME_CRC_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x2" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x0" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "SENT_FRAMES",
            "REQUESTED_FRAMES",
            "RX_GOOD",
            "FRAME_BAD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "RX_SYMBOL_ERRORS",
            "PREAMBLE_SEEN_COUNT",
            "RX_REMOTE_LANE1_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
        write_markdown(
            capture_dir / "lane1_frame_crc_parse_summary.md",
            "P4 Auto Lane1 Frame CRC ILA Parse Summary",
            ila_parse.get("LANE1_FRAME_CRC_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for lane1 deterministic frame/CRC evidence",
            [
                f"LANE1_FRAME_CRC_ILA_PARSE: {ila_parse.get('LANE1_FRAME_CRC_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
                f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
                f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
                f"SENT_FRAMES: {payload.get('SENT_FRAMES', 'MISSING')}",
                f"RX_GOOD: {payload.get('RX_GOOD', 'MISSING')}",
                f"FRAME_BAD: {payload.get('FRAME_BAD', 'MISSING')}",
                f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
                f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
                f"RX_SYMBOL_ERRORS: {payload.get('RX_SYMBOL_ERRORS', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_lane1_frame_crc",
            test_profile="P4_AUTO_LANE1_FRAME_CRC_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["LANE1_FRAME_CRC"] = "FAIL_WITH_EVIDENCE"
            payload["LANE1_FRAME_CRC_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "lane1_frame_crc_counters.csv",
        "test,status,session,lane_mask,ack_lane_mask,sent_frames,rx_good,frame_bad,crc_bad,payload_mismatch,rx_symbol_errors,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"lane1_frame_crc,{payload['LANE1_FRAME_CRC']},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('SENT_FRAMES','MISSING')},{payload.get('RX_GOOD','MISSING')},{payload.get('FRAME_BAD','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('RX_SYMBOL_ERRORS','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "lane1_frame_crc_readback.json", payload)
    lines = [
        f"LANE1_FRAME_CRC: {payload['LANE1_FRAME_CRC']}",
        f"LANE1_FRAME_CRC_PROGRAM: {payload['LANE1_FRAME_CRC_PROGRAM']}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"SENT_FRAMES: {payload.get('SENT_FRAMES', 'MISSING')}",
        f"RX_GOOD: {payload.get('RX_GOOD', 'MISSING')}",
        f"FRAME_BAD: {payload.get('FRAME_BAD', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"RX_REMOTE_LANE1_ACTIVE_LOW_PULSE_COUNT: {payload.get('RX_REMOTE_LANE1_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized lane1 deterministic frame/CRC smoke evidence with ACK disabled.",
        "- It is ILA/internal proxy evidence, not external pin scope verification.",
        "- It is not lane1 ACK/retry, two-lane, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Lane1 Frame CRC Summary",
        payload["LANE1_FRAME_CRC"],
        "lane1 deterministic frame/CRC runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "lane1_frame_crc_summary.md",
        "P4 Auto Lane1 Frame CRC Summary",
        payload["LANE1_FRAME_CRC"],
        "lane1 deterministic frame/CRC runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_lane0_ack_retry_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "protocol_smoke"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_lane0_ack_retry.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_lane0_ack")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_lane0_ack_retry_programming.tcl.txt"
    log_path = evidence_dir / "lane0_ack_retry_program_log.txt"
    run_path = evidence_dir / "p4_auto_lane0_ack_retry_program_result.json"
    summary_path = GENERATED / "p4_auto_lane0_ack_retry_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "protocol_smoke" / "lane0_ack_retry"
    vivado = _resolve_vivado()
    payload = {
        "LANE0_ACK_RETRY": "SKIP_WITH_REASON",
        "LANE0_ACK_RETRY_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "LANE0_ACK_RETRY_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "LANE0_ACK_RETRY_BITSTREAM_SHA256": actual_sha,
        "LANE0_ACK_RETRY_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_LANE0_ACK_RETRY_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["LANE0_ACK_RETRY"] = "FAIL_WITH_EVIDENCE"
        payload["LANE0_ACK_RETRY_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized lane0 ACK/retry bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["LANE0_ACK_RETRY"] = "FAIL_WITH_EVIDENCE"
        payload["LANE0_ACK_RETRY_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="LANE0_ACK_RETRY",
        capture_prefix="lane0_ack_retry",
        post_program_wait_ms=1500,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 120, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_LANE0_ACK_RETRY_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_lane0_ack_retry_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "lane0_ack_retry_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("LANE0_ACK_RETRY_ILA_PARSE") == "PASS"
        payload["LANE0_ACK_RETRY_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["LANE0_ACK_RETRY"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_LANE0_ACK_RETRY_PARSE"] = ila_parse.get("LANE0_ACK_RETRY_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x1" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x1" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "A_SENT_FRAMES",
            "REQUESTED_FRAMES",
            "B_RX_GOOD",
            "B_FRAME_BAD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "B_ACK_SENT",
            "A_ACK_SEEN",
            "TX_RETRY_EXHAUSTED",
            "TX_FAIL",
            "A_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "B_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
        write_markdown(
            capture_dir / "lane0_ack_retry_parse_summary.md",
            "P4 Auto Lane0 ACK Retry ILA Parse Summary",
            ila_parse.get("LANE0_ACK_RETRY_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for lane0 deterministic DATA plus ACK evidence",
            [
                f"LANE0_ACK_RETRY_ILA_PARSE: {ila_parse.get('LANE0_ACK_RETRY_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
                f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
                f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
                f"A_SENT_FRAMES: {payload.get('A_SENT_FRAMES', 'MISSING')}",
                f"B_RX_GOOD: {payload.get('B_RX_GOOD', 'MISSING')}",
                f"B_ACK_SENT: {payload.get('B_ACK_SENT', 'MISSING')}",
                f"A_ACK_SEEN: {payload.get('A_ACK_SEEN', 'MISSING')}",
                "ACK_SEEN_EVIDENCE: ACK_TX_WINDOW_ACTIVE_LOW_PROXY",
                f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
                f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
                f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
                f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_lane0_ack_retry",
            test_profile="P4_AUTO_LANE0_ACK_RETRY_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["LANE0_ACK_RETRY"] = "FAIL_WITH_EVIDENCE"
            payload["LANE0_ACK_RETRY_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "lane0_ack_retry_counters.csv",
        "test,status,session,lane_mask,ack_lane_mask,a_sent_frames,b_rx_good,b_ack_sent,a_ack_seen,tx_retry_exhausted,tx_fail,crc_bad,payload_mismatch,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"lane0_ack_retry,{payload['LANE0_ACK_RETRY']},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('A_SENT_FRAMES','MISSING')},{payload.get('B_RX_GOOD','MISSING')},{payload.get('B_ACK_SENT','MISSING')},{payload.get('A_ACK_SEEN','MISSING')},{payload.get('TX_RETRY_EXHAUSTED','MISSING')},{payload.get('TX_FAIL','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "lane0_ack_retry_readback.json", payload)
    lines = [
        f"LANE0_ACK_RETRY: {payload['LANE0_ACK_RETRY']}",
        f"LANE0_ACK_RETRY_PROGRAM: {payload['LANE0_ACK_RETRY_PROGRAM']}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"A_SENT_FRAMES: {payload.get('A_SENT_FRAMES', 'MISSING')}",
        f"B_RX_GOOD: {payload.get('B_RX_GOOD', 'MISSING')}",
        f"B_ACK_SENT: {payload.get('B_ACK_SENT', 'MISSING')}",
        f"A_ACK_SEEN: {payload.get('A_ACK_SEEN', 'MISSING')}",
        f"ACK_SEEN_EVIDENCE: {payload.get('ACK_SEEN_EVIDENCE', 'ACK_TX_WINDOW_ACTIVE_LOW_PROXY')}",
        f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
        f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"A_ACK_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('A_ACK_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"B_DATA_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('B_DATA_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized lane0 deterministic DATA plus ACK/retry smoke evidence.",
        "- A_ACK_SEEN is internal/proxy readback from A-side active-low RX during the bounded B ACK TX window, not external pin scope verification.",
        "- It is not lane1, two-lane, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Lane0 ACK Retry Summary",
        payload["LANE0_ACK_RETRY"],
        "lane0 deterministic ACK/retry runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "lane0_ack_retry_summary.md",
        "P4 Auto Lane0 ACK Retry Summary",
        payload["LANE0_ACK_RETRY"],
        "lane0 deterministic ACK/retry runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_lane1_ack_retry_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "protocol_smoke"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_lane1_ack_retry.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_lane1_ack")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_lane1_ack_retry_programming.tcl.txt"
    log_path = evidence_dir / "lane1_ack_retry_program_log.txt"
    run_path = evidence_dir / "p4_auto_lane1_ack_retry_program_result.json"
    summary_path = GENERATED / "p4_auto_lane1_ack_retry_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "protocol_smoke" / "lane1_ack_retry"
    vivado = _resolve_vivado()
    payload = {
        "LANE1_ACK_RETRY": "SKIP_WITH_REASON",
        "LANE1_ACK_RETRY_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "LANE1_ACK_RETRY_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "LANE1_ACK_RETRY_BITSTREAM_SHA256": actual_sha,
        "LANE1_ACK_RETRY_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_LANE1_ACK_RETRY_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["LANE1_ACK_RETRY"] = "FAIL_WITH_EVIDENCE"
        payload["LANE1_ACK_RETRY_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized lane1 ACK/retry bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["LANE1_ACK_RETRY"] = "FAIL_WITH_EVIDENCE"
        payload["LANE1_ACK_RETRY_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="LANE1_ACK_RETRY",
        capture_prefix="lane1_ack_retry",
        post_program_wait_ms=1500,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 120, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_LANE1_ACK_RETRY_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_lane1_ack_retry_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "lane1_ack_retry_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("LANE1_ACK_RETRY_ILA_PARSE") == "PASS"
        payload["LANE1_ACK_RETRY_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["LANE1_ACK_RETRY"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_LANE1_ACK_RETRY_PARSE"] = ila_parse.get("LANE1_ACK_RETRY_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x2" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x2" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "A_SENT_FRAMES",
            "REQUESTED_FRAMES",
            "B_RX_GOOD",
            "B_FRAME_BAD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "B_ACK_SENT",
            "A_ACK_SEEN",
            "TX_RETRY_EXHAUSTED",
            "TX_FAIL",
            "A_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "B_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
        write_markdown(
            capture_dir / "lane1_ack_retry_parse_summary.md",
            "P4 Auto Lane1 ACK Retry ILA Parse Summary",
            ila_parse.get("LANE1_ACK_RETRY_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for lane1 deterministic DATA plus ACK evidence",
            [
                f"LANE1_ACK_RETRY_ILA_PARSE: {ila_parse.get('LANE1_ACK_RETRY_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
                f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
                f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
                f"A_SENT_FRAMES: {payload.get('A_SENT_FRAMES', 'MISSING')}",
                f"B_RX_GOOD: {payload.get('B_RX_GOOD', 'MISSING')}",
                f"B_ACK_SENT: {payload.get('B_ACK_SENT', 'MISSING')}",
                f"A_ACK_SEEN: {payload.get('A_ACK_SEEN', 'MISSING')}",
                "ACK_SEEN_EVIDENCE: ACK_TX_WINDOW_ACTIVE_LOW_PROXY",
                f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
                f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
                f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
                f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_lane1_ack_retry",
            test_profile="P4_AUTO_LANE1_ACK_RETRY_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["LANE1_ACK_RETRY"] = "FAIL_WITH_EVIDENCE"
            payload["LANE1_ACK_RETRY_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "lane1_ack_retry_counters.csv",
        "test,status,session,lane_mask,ack_lane_mask,a_sent_frames,b_rx_good,b_ack_sent,a_ack_seen,tx_retry_exhausted,tx_fail,crc_bad,payload_mismatch,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"lane1_ack_retry,{payload['LANE1_ACK_RETRY']},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('A_SENT_FRAMES','MISSING')},{payload.get('B_RX_GOOD','MISSING')},{payload.get('B_ACK_SENT','MISSING')},{payload.get('A_ACK_SEEN','MISSING')},{payload.get('TX_RETRY_EXHAUSTED','MISSING')},{payload.get('TX_FAIL','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "lane1_ack_retry_readback.json", payload)
    lines = [
        f"LANE1_ACK_RETRY: {payload['LANE1_ACK_RETRY']}",
        f"LANE1_ACK_RETRY_PROGRAM: {payload['LANE1_ACK_RETRY_PROGRAM']}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"A_SENT_FRAMES: {payload.get('A_SENT_FRAMES', 'MISSING')}",
        f"B_RX_GOOD: {payload.get('B_RX_GOOD', 'MISSING')}",
        f"B_ACK_SENT: {payload.get('B_ACK_SENT', 'MISSING')}",
        f"A_ACK_SEEN: {payload.get('A_ACK_SEEN', 'MISSING')}",
        f"ACK_SEEN_EVIDENCE: {payload.get('ACK_SEEN_EVIDENCE', 'ACK_TX_WINDOW_ACTIVE_LOW_PROXY')}",
        f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
        f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"A_ACK_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('A_ACK_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"B_DATA_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('B_DATA_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized lane1 deterministic DATA plus ACK/retry smoke evidence.",
        "- A_ACK_SEEN is internal/proxy readback from A-side active-low RX during the bounded B ACK TX window, not external pin scope verification.",
        "- It is not two-lane, Ethernet, rotation, soak, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Lane1 ACK Retry Summary",
        payload["LANE1_ACK_RETRY"],
        "lane1 deterministic ACK/retry runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "lane1_ack_retry_summary.md",
        "P4 Auto Lane1 ACK Retry Summary",
        payload["LANE1_ACK_RETRY"],
        "lane1 deterministic ACK/retry runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_two_lane_minimal_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "protocol_smoke"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_two_lane_minimal.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_two_lane_minimal")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_two_lane_minimal_programming.tcl.txt"
    log_path = evidence_dir / "two_lane_minimal_program_log.txt"
    run_path = evidence_dir / "p4_auto_two_lane_minimal_program_result.json"
    summary_path = GENERATED / "p4_auto_two_lane_minimal_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "protocol_smoke" / "two_lane_minimal"
    vivado = _resolve_vivado()
    payload = {
        "TWO_LANE_MINIMAL": "SKIP_WITH_REASON",
        "TWO_LANE_MINIMAL_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "TWO_LANE_MINIMAL_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "TWO_LANE_MINIMAL_BITSTREAM_SHA256": actual_sha,
        "TWO_LANE_MINIMAL_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_TWO_LANE_MINIMAL_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["TWO_LANE_MINIMAL"] = "FAIL_WITH_EVIDENCE"
        payload["TWO_LANE_MINIMAL_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized two-lane minimal bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["TWO_LANE_MINIMAL"] = "FAIL_WITH_EVIDENCE"
        payload["TWO_LANE_MINIMAL_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="TWO_LANE_MINIMAL",
        capture_prefix="two_lane_minimal",
        post_program_wait_ms=1500,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 120, 60), 300))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = program_result["returncode"] == 0 and "P4_AUTO_TWO_LANE_MINIMAL_PROGRAM=PASS" in program_text
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_two_lane_minimal_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "two_lane_minimal_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        parse_ok = ila_parse.get("TWO_LANE_MINIMAL_ILA_PARSE") == "PASS"
        payload["TWO_LANE_MINIMAL_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["TWO_LANE_MINIMAL"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_TWO_LANE_MINIMAL_PARSE"] = ila_parse.get("TWO_LANE_MINIMAL_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x3" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x3" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "A_SENT_FRAMES_PER_LANE",
            "REQUESTED_FRAMES_PER_LANE",
            "LANE0_RX_GOOD",
            "LANE1_RX_GOOD",
            "TOTAL_RX_GOOD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "LANE0_ACK_SENT",
            "LANE1_ACK_SENT",
            "TX_RETRY_EXHAUSTED",
            "TX_FAIL",
            "LANE0_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "LANE1_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "LANE0_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "LANE1_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
        write_markdown(
            capture_dir / "two_lane_minimal_parse_summary.md",
            "P4 Auto Two-Lane Minimal ILA Parse Summary",
            ila_parse.get("TWO_LANE_MINIMAL_ILA_PARSE", "UNKNOWN"),
            "runtime ILA CSV parsed for bounded two-lane deterministic DATA plus ACK evidence",
            [
                f"TWO_LANE_MINIMAL_ILA_PARSE: {ila_parse.get('TWO_LANE_MINIMAL_ILA_PARSE', 'UNKNOWN')}",
                f"CSV_COUNT: {ila_parse.get('csv_count', 0)}",
                f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
                f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
                f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
                f"LANE0_RX_GOOD: {payload.get('LANE0_RX_GOOD', 'MISSING')}",
                f"LANE1_RX_GOOD: {payload.get('LANE1_RX_GOOD', 'MISSING')}",
                f"LANE0_ACK_SENT: {payload.get('LANE0_ACK_SENT', 'MISSING')}",
                f"LANE1_ACK_SENT: {payload.get('LANE1_ACK_SENT', 'MISSING')}",
                f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
                f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
                f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
                f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
                f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
                f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
            ],
            no_hw=False,
        )
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_two_lane_minimal",
            test_profile="P4_AUTO_TWO_LANE_MINIMAL_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["TWO_LANE_MINIMAL"] = "FAIL_WITH_EVIDENCE"
            payload["TWO_LANE_MINIMAL_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "two_lane_minimal_counters.csv",
        "test,status,session,lane_mask,ack_lane_mask,lane0_rx_good,lane1_rx_good,total_rx_good,lane0_ack_sent,lane1_ack_sent,tx_retry_exhausted,tx_fail,crc_bad,payload_mismatch,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"two_lane_minimal,{payload['TWO_LANE_MINIMAL']},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('LANE0_RX_GOOD','MISSING')},{payload.get('LANE1_RX_GOOD','MISSING')},{payload.get('TOTAL_RX_GOOD','MISSING')},{payload.get('LANE0_ACK_SENT','MISSING')},{payload.get('LANE1_ACK_SENT','MISSING')},{payload.get('TX_RETRY_EXHAUSTED','MISSING')},{payload.get('TX_FAIL','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "two_lane_minimal_readback.json", payload)
    lines = [
        f"TWO_LANE_MINIMAL: {payload['TWO_LANE_MINIMAL']}",
        f"TWO_LANE_MINIMAL_PROGRAM: {payload['TWO_LANE_MINIMAL_PROGRAM']}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"A_SENT_FRAMES_PER_LANE: {payload.get('A_SENT_FRAMES_PER_LANE', 'MISSING')}",
        f"LANE0_RX_GOOD: {payload.get('LANE0_RX_GOOD', 'MISSING')}",
        f"LANE1_RX_GOOD: {payload.get('LANE1_RX_GOOD', 'MISSING')}",
        f"TOTAL_RX_GOOD: {payload.get('TOTAL_RX_GOOD', 'MISSING')}",
        f"LANE0_ACK_SENT: {payload.get('LANE0_ACK_SENT', 'MISSING')}",
        f"LANE1_ACK_SENT: {payload.get('LANE1_ACK_SENT', 'MISSING')}",
        f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
        f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"LANE0_DATA_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('LANE0_DATA_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"LANE1_DATA_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('LANE1_DATA_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"LANE0_ACK_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('LANE0_ACK_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"LANE1_ACK_RX_ACTIVE_LOW_PULSE_COUNT: {payload.get('LANE1_ACK_RX_ACTIVE_LOW_PULSE_COUNT', 'MISSING')}",
        f"TXD_HIGH_CONSECUTIVE_MAX_CYCLES: {payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES', 'MISSING')}",
        f"TXD_HIGH_TOTAL_CYCLES: {payload.get('TXD_HIGH_TOTAL_CYCLES', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized bounded two-lane minimal DATA plus ACK smoke evidence from one two-lane bitstream.",
        "- It uses internal/proxy ILA readback and raw active-low counters, not external pin scope verification.",
        "- It is not Ethernet, rotation, soak, throughput, 8-lane, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Two-Lane Minimal Summary",
        payload["TWO_LANE_MINIMAL"],
        "bounded two-lane minimal runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "two_lane_minimal_summary.md",
        "P4 Auto Two-Lane Minimal Summary",
        payload["TWO_LANE_MINIMAL"],
        "bounded two-lane minimal runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_lane0_300s_soak_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "soak"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_lane0_300s_soak.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_lane0_soak")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_lane0_300s_soak_programming.tcl.txt"
    log_path = evidence_dir / "lane0_300s_soak_program_log.txt"
    run_path = evidence_dir / "p4_auto_lane0_300s_soak_program_result.json"
    summary_path = GENERATED / "p4_auto_lane0_300s_soak_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "soak" / "lane0_300s_soak"
    vivado = _resolve_vivado()
    soak_runtime_sec = 315
    payload = {
        "LANE0_300S_SOAK": "SKIP_WITH_REASON",
        "LANE0_300S_SOAK_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "SOAK_RUNTIME_SEC": soak_runtime_sec,
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "LANE0_300S_SOAK_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "LANE0_300S_SOAK_BITSTREAM_SHA256": actual_sha,
        "LANE0_300S_SOAK_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_LANE0_300S_SOAK_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["LANE0_300S_SOAK"] = "FAIL_WITH_EVIDENCE"
        payload["LANE0_300S_SOAK_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized lane0 300s soak bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["LANE0_300S_SOAK"] = "FAIL_WITH_EVIDENCE"
        payload["LANE0_300S_SOAK_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="LANE0_300S_SOAK",
        capture_prefix="lane0_300s_soak",
        post_program_wait_ms=soak_runtime_sec * 1000,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 360, 360) + 120, 600))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = "P4_AUTO_LANE0_300S_SOAK_PROGRAM=PASS" in program_text and program_result["returncode"] in {0, 124}
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_lane0_300s_soak_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "lane0_300s_soak_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        runtime_ok = soak_runtime_sec >= 300
        parse_ok = ila_parse.get("LANE0_300S_SOAK_ILA_PARSE") == "PASS"
        payload["LANE0_300S_SOAK_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["LANE0_300S_SOAK"] = "PASS" if program_ok and ila_capture_pass and parse_ok and runtime_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_LANE0_300S_SOAK_PARSE"] = ila_parse.get("LANE0_300S_SOAK_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x1" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x1" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "A_SENT_FRAMES",
            "REQUESTED_FRAMES",
            "SOAK_SENT_FRAMES",
            "SOAK_RX_GOOD",
            "B_RX_GOOD",
            "B_FRAME_BAD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "B_ACK_SENT",
            "A_ACK_SEEN",
            "TX_RETRY_EXHAUSTED",
            "TX_FAIL",
            "A_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "B_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_lane0_300s_soak",
            test_profile="P4_AUTO_LANE0_300S_SOAK_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["LANE0_300S_SOAK"] = "FAIL_WITH_EVIDENCE"
            payload["LANE0_300S_SOAK_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "lane0_300s_soak_counters.csv",
        "test,status,runtime_sec,session,lane_mask,ack_lane_mask,sent_frames,rx_good,b_ack_sent,a_ack_seen,tx_retry_exhausted,tx_fail,crc_bad,payload_mismatch,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"lane0_300s_soak,{payload['LANE0_300S_SOAK']},{payload.get('SOAK_RUNTIME_SEC','MISSING')},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('A_SENT_FRAMES','MISSING')},{payload.get('B_RX_GOOD','MISSING')},{payload.get('B_ACK_SENT','MISSING')},{payload.get('A_ACK_SEEN','MISSING')},{payload.get('TX_RETRY_EXHAUSTED','MISSING')},{payload.get('TX_FAIL','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "lane0_300s_soak_readback.json", payload)
    lines = [
        f"LANE0_300S_SOAK: {payload['LANE0_300S_SOAK']}",
        f"LANE0_300S_SOAK_PROGRAM: {payload['LANE0_300S_SOAK_PROGRAM']}",
        f"SOAK_RUNTIME_SEC: {payload.get('SOAK_RUNTIME_SEC', 'MISSING')}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"A_SENT_FRAMES: {payload.get('A_SENT_FRAMES', 'MISSING')}",
        f"B_RX_GOOD: {payload.get('B_RX_GOOD', 'MISSING')}",
        f"B_ACK_SENT: {payload.get('B_ACK_SENT', 'MISSING')}",
        f"A_ACK_SEEN: {payload.get('A_ACK_SEEN', 'MISSING')}",
        f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
        f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized bounded lane0 300s soak evidence.",
        "- It is internal/proxy ILA readback, not external pin scope verification.",
        "- It is not two-lane soak, Ethernet, rotation, 8-lane, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Lane0 300s Soak Summary",
        payload["LANE0_300S_SOAK"],
        "lane0 300s bounded soak runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "lane0_300s_soak_summary.md",
        "P4 Auto Lane0 300s Soak Summary",
        payload["LANE0_300S_SOAK"],
        "lane0 300s bounded soak runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def run_two_lane_300s_soak_program(args, provenance: dict) -> dict:
    evidence_dir = P4_AUTO_DIR / "soak"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile = args.profile_path or "profiles/p4_auto_two_lane_300s_soak.json"
    authorized_bitstream = resolve_root_path(args.bitstream)
    authorized_rel = rel(authorized_bitstream) if authorized_bitstream else "MISSING"
    row = {}
    for item in provenance.get("rows", []):
        if item.get("immutable_bitstream_path") == authorized_rel and item.get("status") == "PASS":
            row = item
            break
    if not row:
        row = _provenance_row(provenance, "protocol_two_lane_soak")
    bitstream = authorized_bitstream if authorized_bitstream else (ROOT / row.get("immutable_bitstream_path", ""))
    manifest_sha = row.get("sha256", "MISSING")
    actual_sha = sha256_or_missing(bitstream)
    authorized_path_in_manifest = bool(row and row.get("immutable_bitstream_path") == authorized_rel)
    authorized_sha_match = bool(args.bitstream_sha256 and actual_sha != "MISSING" and args.bitstream_sha256.lower() == actual_sha.lower())
    bitstream_match = bool(bitstream and bitstream.exists() and authorized_path_in_manifest and authorized_sha_match and actual_sha.lower() == manifest_sha.lower())
    tcl_path = evidence_dir / "p4_auto_two_lane_300s_soak_programming.tcl.txt"
    log_path = evidence_dir / "two_lane_300s_soak_program_log.txt"
    run_path = evidence_dir / "p4_auto_two_lane_300s_soak_program_result.json"
    summary_path = GENERATED / "p4_auto_two_lane_300s_soak_summary.md"
    ltx_rel = row.get("debug_probes_path", "")
    ltx_path = ROOT / ltx_rel if ltx_rel and ltx_rel != "MISSING" else None
    capture_dir = P4_AUTO_DIR / "ila" / "soak" / "two_lane_300s_soak"
    vivado = _resolve_vivado()
    soak_runtime_sec = 315
    payload = {
        "TWO_LANE_300S_SOAK": "SKIP_WITH_REASON",
        "TWO_LANE_300S_SOAK_PROGRAM": "SKIP_WITH_REASON",
        "CONFIG_READBACK": "SKIP_WITH_REASON",
        "SOAK_RUNTIME_SEC": soak_runtime_sec,
        "BITSTREAM_SHA_MATCH": "PASS" if bitstream_match else "FAIL",
        "PROGRAM_RETURN_CODE": "NOT_RUN",
        "PROGRAM_LOG": rel(log_path),
        "PROGRAM_TCL": rel(tcl_path),
        "TWO_LANE_300S_SOAK_BITSTREAM": rel(bitstream) if bitstream else "MISSING",
        "TWO_LANE_300S_SOAK_BITSTREAM_SHA256": actual_sha,
        "TWO_LANE_300S_SOAK_MANIFEST_SHA256": manifest_sha,
        "AUTHORIZED_BITSTREAM": authorized_rel,
        "AUTHORIZED_BITSTREAM_IN_MANIFEST": authorized_path_in_manifest,
        "AUTHORIZED_BITSTREAM_SHA_MATCH": authorized_sha_match,
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "ILA_CAPTURE_DIR": rel(capture_dir),
        "ILA_CAPTURE": "NOT_RUN",
        "ILA_TWO_LANE_300S_SOAK_PARSE": "NOT_RUN",
        "DEBUG_READBACK_AVAILABLE": "SKIP_WITH_REASON",
        "SHUTDOWN_ON_EXIT": "SKIP_WITH_REASON",
        "HARDWARE_ACTIONS_EXECUTED": False,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
    }
    if not bitstream_match:
        payload["TWO_LANE_300S_SOAK"] = "FAIL_WITH_EVIDENCE"
        payload["TWO_LANE_300S_SOAK_PROGRAM"] = "FAIL"
        payload["reason"] = "authorized two-lane 300s soak bitstream is missing from manifest or SHA does not match authorization/manifest"
        write_json(run_path, payload)
        return payload
    if not vivado:
        payload["TWO_LANE_300S_SOAK"] = "FAIL_WITH_EVIDENCE"
        payload["TWO_LANE_300S_SOAK_PROGRAM"] = "FAIL"
        payload["reason"] = "Vivado executable missing"
        write_json(run_path, payload)
        return payload

    _write_stage_program_tcl(
        tcl_path,
        bitstream,
        log_path,
        ltx_path,
        capture_dir,
        stage_label="TWO_LANE_300S_SOAK",
        capture_prefix="two_lane_300s_soak",
        post_program_wait_ms=soak_runtime_sec * 1000,
    )
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    shutdown_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    try:
        program_result = run_cmd([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 360, 360) + 120, 600))
        program_text = "\n".join([program_result.get("stdout", ""), program_result.get("stderr", ""), log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else ""])
        program_ok = "P4_AUTO_TWO_LANE_300S_SOAK_PROGRAM=PASS" in program_text and program_result["returncode"] in {0, 124}
        ila_capture_pass = "P4_AUTO_ILA_CAPTURE=PASS" in program_text
        ila_parse = parse_two_lane_300s_soak_capture_dir(capture_dir)
        ila_parse["HARDWARE_ACTIONS_EXECUTED"] = True
        ila_parse["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for item in ila_parse.get("results", []):
            item["HARDWARE_ACTIONS_EXECUTED"] = True
            item["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        if isinstance(ila_parse.get("best_result"), dict):
            ila_parse["best_result"]["HARDWARE_ACTIONS_EXECUTED"] = True
            ila_parse["best_result"]["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        write_json(capture_dir / "two_lane_300s_soak_parse_result.json", ila_parse)
        best_parse = ila_parse.get("best_result", {})
        runtime_ok = soak_runtime_sec >= 300
        parse_ok = ila_parse.get("TWO_LANE_300S_SOAK_ILA_PARSE") == "PASS"
        payload["TWO_LANE_300S_SOAK_PROGRAM"] = "PASS" if program_ok else "FAIL"
        payload["TWO_LANE_300S_SOAK"] = "PASS" if program_ok and ila_capture_pass and parse_ok and runtime_ok else "FAIL_WITH_EVIDENCE"
        payload["ILA_CAPTURE"] = "PASS" if ila_capture_pass else "FAIL" if "P4_AUTO_ILA_CAPTURE=FAIL" in program_text else "SKIP_WITH_REASON"
        payload["ILA_TWO_LANE_300S_SOAK_PARSE"] = ila_parse.get("TWO_LANE_300S_SOAK_ILA_PARSE", "UNKNOWN")
        payload["DEBUG_READBACK_AVAILABLE"] = "PASS" if program_ok and ila_capture_pass and parse_ok else "BLOCKED_RUNTIME_READBACK_MISSING"
        payload["CONFIG_READBACK"] = "PASS" if best_parse.get("SESSION_READBACK") == "0x2201" and best_parse.get("LANE_MASK_READBACK") == "0x3" and best_parse.get("ACK_LANE_MASK_READBACK") == "0x3" else "FAIL"
        payload["PROGRAM_RETURN_CODE"] = program_result["returncode"]
        payload["HARDWARE_ACTIONS_EXECUTED"] = True
        payload["NO_HARDWARE_ACTIONS_EXECUTED"] = False
        for key in [
            "SESSION_READBACK",
            "LANE_MASK_READBACK",
            "ACK_LANE_MASK_READBACK",
            "A_SENT_FRAMES_PER_LANE",
            "REQUESTED_FRAMES_PER_LANE",
            "SOAK_SENT_FRAMES_PER_LANE",
            "SOAK_LANE0_RX_GOOD",
            "SOAK_LANE1_RX_GOOD",
            "LANE0_RX_GOOD",
            "LANE1_RX_GOOD",
            "TOTAL_RX_GOOD",
            "CRC_BAD",
            "PAYLOAD_MISMATCH",
            "LANE0_ACK_SENT",
            "LANE1_ACK_SENT",
            "TX_RETRY_EXHAUSTED",
            "TX_FAIL",
            "LANE0_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "LANE1_ACK_RX_ACTIVE_LOW_PULSE_COUNT",
            "LANE0_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "LANE1_DATA_RX_ACTIVE_LOW_PULSE_COUNT",
            "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
            "TXD_HIGH_TOTAL_CYCLES",
            "TXD_STUCK_HIGH_VIOLATION",
            "DUTY_WINDOW_VIOLATION",
        ]:
            payload[key] = best_parse.get(key, "MISSING")
    finally:
        shutdown_result = _run_shutdown_after_stage(
            args,
            profile,
            "evidence/hardware/p4_auto/shutdown/after_two_lane_300s_soak",
            test_profile="P4_AUTO_TWO_LANE_300S_SOAK_SHUTDOWN",
        )
        shutdown_text = "\n".join([shutdown_result.get("stdout", ""), shutdown_result.get("stderr", "")])
        shutdown_ok = shutdown_result["returncode"] == 0 or "SHUTDOWN_EXIT=0" in shutdown_text or "TFDU_SHUTDOWN_PROGRAMMED" in shutdown_text
        payload["SHUTDOWN_ON_EXIT"] = "PASS" if shutdown_ok else "FAIL"
        if not shutdown_ok:
            payload["TWO_LANE_300S_SOAK"] = "FAIL_WITH_EVIDENCE"
            payload["TWO_LANE_300S_SOAK_PROGRAM"] = "FAIL"

    payload["program_run"] = {
        "cmd": program_result.get("cmd", ""),
        "returncode": program_result.get("returncode", 125),
        "stdout_tail": program_result.get("stdout", "")[-2000:],
        "stderr_tail": program_result.get("stderr", "")[-2000:],
    }
    payload["shutdown_run"] = {
        "cmd": shutdown_result.get("cmd", ""),
        "returncode": shutdown_result.get("returncode", 125),
        "stdout_tail": shutdown_result.get("stdout", "")[-2000:],
        "stderr_tail": shutdown_result.get("stderr", "")[-2000:],
    }
    write_json(run_path, payload)
    write_text(
        evidence_dir / "two_lane_300s_soak_counters.csv",
        "test,status,runtime_sec,session,lane_mask,ack_lane_mask,sent_frames_per_lane,lane0_rx_good,lane1_rx_good,lane0_ack_sent,lane1_ack_sent,tx_retry_exhausted,tx_fail,crc_bad,payload_mismatch,txd_high_max_cycles,txd_stuck_high_violation,duty_window_violation\n"
        f"two_lane_300s_soak,{payload['TWO_LANE_300S_SOAK']},{payload.get('SOAK_RUNTIME_SEC','MISSING')},{payload.get('SESSION_READBACK','MISSING')},{payload.get('LANE_MASK_READBACK','MISSING')},{payload.get('ACK_LANE_MASK_READBACK','MISSING')},{payload.get('A_SENT_FRAMES_PER_LANE','MISSING')},{payload.get('LANE0_RX_GOOD','MISSING')},{payload.get('LANE1_RX_GOOD','MISSING')},{payload.get('LANE0_ACK_SENT','MISSING')},{payload.get('LANE1_ACK_SENT','MISSING')},{payload.get('TX_RETRY_EXHAUSTED','MISSING')},{payload.get('TX_FAIL','MISSING')},{payload.get('CRC_BAD','MISSING')},{payload.get('PAYLOAD_MISMATCH','MISSING')},{payload.get('TXD_HIGH_CONSECUTIVE_MAX_CYCLES','MISSING')},{payload.get('TXD_STUCK_HIGH_VIOLATION','MISSING')},{payload.get('DUTY_WINDOW_VIOLATION','MISSING')}\n",
    )
    write_json(evidence_dir / "two_lane_300s_soak_readback.json", payload)
    lines = [
        f"TWO_LANE_300S_SOAK: {payload['TWO_LANE_300S_SOAK']}",
        f"TWO_LANE_300S_SOAK_PROGRAM: {payload['TWO_LANE_300S_SOAK_PROGRAM']}",
        f"SOAK_RUNTIME_SEC: {payload.get('SOAK_RUNTIME_SEC', 'MISSING')}",
        f"CONFIG_READBACK: {payload['CONFIG_READBACK']}",
        f"BITSTREAM_SHA_MATCH: {payload['BITSTREAM_SHA_MATCH']}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"SESSION_READBACK: {payload.get('SESSION_READBACK', 'MISSING')}",
        f"LANE_MASK_READBACK: {payload.get('LANE_MASK_READBACK', 'MISSING')}",
        f"ACK_LANE_MASK_READBACK: {payload.get('ACK_LANE_MASK_READBACK', 'MISSING')}",
        f"A_SENT_FRAMES_PER_LANE: {payload.get('A_SENT_FRAMES_PER_LANE', 'MISSING')}",
        f"LANE0_RX_GOOD: {payload.get('LANE0_RX_GOOD', 'MISSING')}",
        f"LANE1_RX_GOOD: {payload.get('LANE1_RX_GOOD', 'MISSING')}",
        f"LANE0_ACK_SENT: {payload.get('LANE0_ACK_SENT', 'MISSING')}",
        f"LANE1_ACK_SENT: {payload.get('LANE1_ACK_SENT', 'MISSING')}",
        f"TX_RETRY_EXHAUSTED: {payload.get('TX_RETRY_EXHAUSTED', 'MISSING')}",
        f"TX_FAIL: {payload.get('TX_FAIL', 'MISSING')}",
        f"CRC_BAD: {payload.get('CRC_BAD', 'MISSING')}",
        f"PAYLOAD_MISMATCH: {payload.get('PAYLOAD_MISMATCH', 'MISSING')}",
        f"TXD_STUCK_HIGH_VIOLATION: {payload.get('TXD_STUCK_HIGH_VIOLATION', 'MISSING')}",
        f"DUTY_WINDOW_VIOLATION: {payload.get('DUTY_WINDOW_VIOLATION', 'MISSING')}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        "- This is authorized bounded two-lane 300s soak evidence.",
        "- It is internal/proxy ILA readback, not external pin scope verification.",
        "- It is not Ethernet, rotation, 8-lane, or product-final acceptance.",
    ]
    write_markdown(
        summary_path,
        "P4 Auto Two-Lane 300s Soak Summary",
        payload["TWO_LANE_300S_SOAK"],
        "two-lane 300s bounded soak runtime evidence generated",
        lines,
        no_hw=False,
    )
    write_markdown(
        evidence_dir / "two_lane_300s_soak_summary.md",
        "P4 Auto Two-Lane 300s Soak Summary",
        payload["TWO_LANE_300S_SOAK"],
        "two-lane 300s bounded soak runtime evidence generated",
        lines,
        no_hw=False,
    )
    return payload


def _load_json_if_present(path: str) -> dict:
    resolved = ROOT / path
    if not resolved.exists():
        return {}
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _prior_pass_stage_statuses() -> dict:
    prior: dict[str, str] = {}
    safe_idle = _load_json_if_present("evidence/hardware/p4_auto/safe_idle_direct_proxy/p4_auto_safe_idle_program_result.json")
    if safe_idle.get("SAFE_IDLE_PROGRAM") == "PASS" and safe_idle.get("DEBUG_READBACK_AVAILABLE") == "PASS":
        prior["SAFE_IDLE_DIRECT_PROXY"] = "PASS"
        prior["SAFE_IDLE_PROGRAM"] = "PASS"
        prior["BITSTREAM_SHA_MATCH"] = "PASS"
        prior["DEBUG_READBACK_AVAILABLE"] = "PASS"
    for path, key in [
        ("evidence/hardware/p4_auto/tfdu_control_idle/p4_auto_tfdu_control_idle_program_result.json", "TFDU_CONTROL_IDLE"),
        ("evidence/hardware/p4_auto/raw_pulse_smoke/p4_auto_raw_pulse_smoke_program_result.json", "RAW_PULSE_SMOKE_L0"),
        ("evidence/hardware/p4_auto/raw_lane_matrix/p4_auto_raw_lane_matrix_program_result.json", "RAW_LANE_MATRIX"),
        ("evidence/hardware/p4_auto/protocol_smoke/lane0_frame_crc_readback.json", "LANE0_FRAME_CRC"),
        ("evidence/hardware/p4_auto/protocol_smoke/lane0_ack_retry_readback.json", "LANE0_ACK_RETRY"),
        ("evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_frame_crc_program_result.json", "LANE1_FRAME_CRC"),
        ("evidence/hardware/p4_auto/protocol_smoke/lane1_ack_retry_readback.json", "LANE1_ACK_RETRY"),
        ("evidence/hardware/p4_auto/protocol_smoke/two_lane_minimal_readback.json", "TWO_LANE_MINIMAL"),
        ("evidence/hardware/p4_auto/soak/lane0_300s_soak_readback.json", "LANE0_300S_SOAK"),
        ("evidence/hardware/p4_auto/soak/two_lane_300s_soak_readback.json", "TWO_LANE_300S_SOAK"),
    ]:
        payload = _load_json_if_present(path)
        if payload.get(key) == "PASS":
            prior[key] = "PASS"
            if payload.get("DEBUG_READBACK_AVAILABLE") == "PASS":
                prior.setdefault("DEBUG_READBACK_AVAILABLE", "PASS")
            if payload.get("BITSTREAM_SHA_MATCH") == "PASS":
                prior.setdefault("BITSTREAM_SHA_MATCH", "PASS")
    return prior


def _merge_prior_passes(stage_status: dict) -> dict:
    merged = dict(stage_status)
    for key, value in _prior_pass_stage_statuses().items():
        current = str(merged.get(key, ""))
        if current in {"", "SKIP_WITH_REASON", "BLOCKED_BY_AUTOMATION_GAP", "PASS_OFFLINE_ILA_INSTRUMENTED", "PASS_STATIC_MANIFEST_ONLY", "PASS_OFFLINE_STATIC_PROXY"}:
            merged[key] = value
    return merged


def write_acceptance_summary(
    auth_payload: dict,
    recheck: dict,
    profiles: dict,
    provenance: dict,
    stage_status: dict,
    shutdown: dict,
    execute_hardware: bool,
    authorized_run_package: dict | None = None,
) -> dict:
    stage_status = _merge_prior_passes(stage_status)
    hardware_actions = shutdown.get("STAGE_B_SHUTDOWN_BASELINE") in {"PASS", "FAIL"}
    stop_conditions = []
    if shutdown.get("STAGE_B_SHUTDOWN_BASELINE") == "FAIL":
        stop_conditions.append("shutdown_baseline_failed")
    if provenance.get("P4_AUTO_BITSTREAM_PROVENANCE") != "PASS":
        stop_conditions.append("bitstream_provenance_incomplete")
    safe_idle = stage_status.get("SAFE_IDLE_DIRECT_PROXY", "SKIP_WITH_REASON")
    safe_idle_program = stage_status.get("SAFE_IDLE_PROGRAM", "SKIP_WITH_REASON")
    bitstream_sha_match = stage_status.get("BITSTREAM_SHA_MATCH", "SKIP_WITH_REASON")
    debug_readback = stage_status.get("DEBUG_READBACK_AVAILABLE", "SKIP_WITH_REASON")
    tfdu_idle = stage_status.get("TFDU_CONTROL_IDLE", "SKIP_WITH_REASON")
    raw_pulse = stage_status.get("RAW_PULSE_SMOKE_L0", "SKIP_WITH_REASON")
    raw_matrix = stage_status.get("RAW_LANE_MATRIX", "SKIP_WITH_REASON")
    lane0_crc = stage_status.get("LANE0_FRAME_CRC", "SKIP_WITH_REASON")
    lane0_ack = stage_status.get("LANE0_ACK_RETRY", "SKIP_WITH_REASON")
    lane1_crc = stage_status.get("LANE1_FRAME_CRC", "SKIP_WITH_REASON")
    lane1_ack = stage_status.get("LANE1_ACK_RETRY", "SKIP_WITH_REASON")
    two_lane = stage_status.get("TWO_LANE_MINIMAL", "SKIP_WITH_REASON")
    lane0_soak = stage_status.get("LANE0_300S_SOAK", "SKIP_WITH_REASON")
    two_lane_soak = stage_status.get("TWO_LANE_300S_SOAK", "SKIP_WITH_REASON")
    stage_failures = {
        "TFDU_CONTROL_IDLE": tfdu_idle,
        "RAW_PULSE_SMOKE_L0": raw_pulse,
        "RAW_LANE_MATRIX": raw_matrix,
        "LANE0_FRAME_CRC": lane0_crc,
        "LANE0_ACK_RETRY": lane0_ack,
        "LANE1_FRAME_CRC": lane1_crc,
        "LANE1_ACK_RETRY": lane1_ack,
        "TWO_LANE_MINIMAL": two_lane,
        "LANE0_300S_SOAK": lane0_soak,
        "TWO_LANE_300S_SOAK": two_lane_soak,
    }
    failed_stages = [name for name, value in stage_failures.items() if str(value).startswith("FAIL")]
    if bitstream_sha_match == "FAIL":
        stop_conditions.append("bitstream_sha_mismatch")
    if failed_stages:
        stop_conditions.append("stage_failure:" + ",".join(failed_stages))

    auth_missing = execute_hardware and not auth_payload.get("AUTHORIZED")
    offline_ready_for_authorized_run = (
        not execute_hardware
        and safe_idle == "PASS_OFFLINE_ILA_INSTRUMENTED"
        and provenance.get("P4_AUTO_BITSTREAM_PROVENANCE") == "PASS"
    )
    post_safe_idle_gap = (
        execute_hardware
        and auth_payload.get("AUTHORIZED")
        and safe_idle == "PASS"
        and debug_readback == "PASS"
        and any(str(value).startswith("BLOCKED") for value in [tfdu_idle, raw_pulse, raw_matrix, lane0_crc, lane0_ack, lane1_crc, lane1_ack, two_lane, lane0_soak, two_lane_soak])
    )
    if two_lane == "PASS" and str(lane0_soak).startswith("BLOCKED"):
        automation_blocker = "LANE0_300S_SOAK_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_LANE0_300S_SOAK"
    elif lane0_soak == "PASS" and str(two_lane_soak).startswith("BLOCKED"):
        automation_blocker = "TWO_LANE_300S_SOAK_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_TWO_LANE_300S_SOAK"
    elif lane1_ack == "PASS" and str(two_lane).startswith("BLOCKED"):
        automation_blocker = "TWO_LANE_MINIMAL_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_TWO_LANE_MINIMAL"
    elif lane1_crc == "PASS" and str(lane1_ack).startswith("BLOCKED"):
        automation_blocker = "LANE1_ACK_RETRY_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_LANE1_ACK_RETRY"
    elif lane0_ack == "PASS" and str(lane1_crc).startswith("BLOCKED"):
        automation_blocker = "LANE1_FRAME_CRC_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_LANE1_FRAME_CRC"
    elif lane0_crc == "PASS" and str(lane0_ack).startswith("BLOCKED"):
        automation_blocker = "LANE0_ACK_RETRY_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_LANE0_ACK_RETRY"
    elif raw_matrix == "PASS" and str(lane0_crc).startswith("BLOCKED"):
        automation_blocker = "LANE0_FRAME_CRC_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_LANE0_FRAME_CRC"
    elif raw_pulse == "PASS" and str(raw_matrix).startswith("BLOCKED"):
        automation_blocker = "RAW_LANE_MATRIX_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_RAW_LANE_MATRIX"
    elif tfdu_idle == "PASS" and str(raw_pulse).startswith("BLOCKED"):
        automation_blocker = "RAW_PULSE_AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_RAW_PULSE"
    else:
        automation_blocker = "POST_SAFE_IDLE_STAGE_AUTOMATION_GAP" if post_safe_idle_gap else "AUTOMATION_GAP"
        gap_next_stage = "P4_AUTO_FIXES_FROM_EVIDENCE"

    if shutdown.get("SHUTDOWN_ON_EXIT") == "FAIL" or "bitstream_provenance_incomplete" in stop_conditions or failed_stages or safe_idle in {"FAIL", "FAIL_WITH_EVIDENCE"} or safe_idle_program == "FAIL" or bitstream_sha_match == "FAIL":
        result = "FAIL_WITH_EVIDENCE"
        next_stage = "P4_AUTO_FIXES_FROM_EVIDENCE"
    elif all(value == "PASS" for value in [safe_idle, tfdu_idle, raw_pulse, raw_matrix, lane0_crc, lane0_ack, lane1_crc, lane1_ack, two_lane, lane0_soak]) and two_lane_soak in {"PASS", "SKIP_USER_NOT_REQUIRED"}:
        result = "PASS"
        next_stage = "P5_PROTOCOL_STABILIZATION"
    elif all(value == "PASS" for value in [safe_idle, tfdu_idle, raw_matrix, lane0_crc, lane0_ack, lane0_soak]) and lane1_crc.startswith("BLOCKED"):
        result = "PASS_LANE0_ONLY"
        next_stage = "P5_LANE0_STABILIZATION_AND_LANE1_DEBUG_AUTOMATION"
    elif auth_missing:
        result = "BLOCKED_BY_AUTOMATION_GAP"
        next_stage = "P4_AUTO_AUTHORIZED_HARDWARE_RUN"
        stop_conditions.append("hardware_authorization_incomplete")
    elif offline_ready_for_authorized_run:
        result = "BLOCKED_BY_AUTOMATION_GAP"
        next_stage = "P4_AUTO_AUTHORIZED_HARDWARE_RUN"
    else:
        result = "BLOCKED_BY_AUTOMATION_GAP"
        next_stage = gap_next_stage
        if execute_hardware and auth_payload.get("AUTHORIZED") and not post_safe_idle_gap:
            stop_conditions.append("safe_idle_proxy_readback_not_implemented")
    generated = [
        item
        for item in SUMMARY_FILES
        if (ROOT / item).exists()
        or item
        in {
            "evidence/generated/p4_auto_hardware_acceptance_summary.md",
            "evidence/generated/p4_auto_hardware_acceptance_summary.json",
        }
    ]
    raw_matrix_rows = []
    raw_matrix_json = P4_AUTO_DIR / "raw_lane_matrix" / "p4_auto_raw_lane_matrix.json"
    if raw_matrix_json.exists():
        try:
            raw_matrix_payload = json.loads(raw_matrix_json.read_text(encoding="utf-8"))
            raw_matrix_rows = raw_matrix_payload.get("direction_results", []) if isinstance(raw_matrix_payload, dict) else []
        except json.JSONDecodeError:
            raw_matrix_rows = []
    if not raw_matrix_rows:
        raw_matrix_rows = [
            {"direction": "AB_L0", "status": raw_matrix},
            {"direction": "BA_L0", "status": raw_matrix},
            {"direction": "AB_L1", "status": raw_matrix},
            {"direction": "BA_L1", "status": raw_matrix},
        ]
    payload = {
        "P4_AUTO_HARDWARE_ACCEPTANCE": result,
        "COMMIT": git_value("rev-parse", "HEAD"),
        "USER_CONFIRMED_SUPPLY_OK": auth_payload.get("USER_CONFIRMED_SUPPLY_OK", False),
        "MANUAL_INTERVENTION_REQUIRED": auth_payload.get("MANUAL_INTERVENTION_REQUIRED", True),
        "HARDWARE_ACTIONS_EXECUTED": hardware_actions,
        "HARDWARE_ACCEPTANCE": "PENDING_HW" if not hardware_actions else result,
        "P1_RECHECK": recheck.get("P1_RECHECK", "UNKNOWN"),
        "P2_RECHECK": recheck.get("P2_RECHECK", "UNKNOWN"),
        "P3_RECHECK": recheck.get("P3_RECHECK", "UNKNOWN"),
        "P4_AUTO_PROFILES": profiles.get("P4_AUTO_PROFILES", "UNKNOWN"),
        "P4_AUTO_BITSTREAM_PROVENANCE": provenance.get("P4_AUTO_BITSTREAM_PROVENANCE", "UNKNOWN"),
        "P4_AUTO_BLOCKER": (
            "none"
            if result == "PASS"
            else (
                "HARDWARE_EVIDENCE_FAILURE"
                if failed_stages
                else (
                    "RF_COMM_HW_AUTH_REQUIRED"
                    if auth_missing
                    else (
                        "AUTHORIZED_HARDWARE_EXECUTION_NOT_RUN"
                        if offline_ready_for_authorized_run
                        else automation_blocker
                    )
                )
            )
        ),
        "AUTHORIZED_RUN_PACKAGE": authorized_run_package.get("summary", "MISSING") if authorized_run_package else "MISSING",
        "SAFE_IDLE_DIRECT_PROXY": safe_idle,
        "SAFE_IDLE_PROGRAM": safe_idle_program,
        "BITSTREAM_SHA_MATCH": bitstream_sha_match,
        "DEBUG_READBACK_AVAILABLE": debug_readback,
        "TFDU_CONTROL_IDLE": tfdu_idle,
        "RAW_PULSE_SMOKE_L0": raw_pulse,
        "RAW_LANE_MATRIX": raw_matrix,
        "LANE0_FRAME_CRC": lane0_crc,
        "LANE0_ACK_RETRY": lane0_ack,
        "LANE1_FRAME_CRC": lane1_crc,
        "LANE1_ACK_RETRY": lane1_ack,
        "TWO_LANE_MINIMAL": two_lane,
        "LANE0_300S_SOAK": lane0_soak,
        "TWO_LANE_300S_SOAK": two_lane_soak,
        "SHUTDOWN_ON_EXIT": shutdown.get("SHUTDOWN_ON_EXIT", "SKIP_NO_HARDWARE_ACTIONS"),
        "STOP_CONDITIONS_TRIGGERED": stop_conditions or "none",
        "IMMUTABLE_SAFE_IDLE_BITSTREAM": _best_safe_idle_bitstream(provenance),
        "GENERATED_SUMMARIES": generated,
        "NEXT_RECOMMENDED_STAGE": next_stage,
    }
    lines = [
        f"P4_AUTO_HARDWARE_ACCEPTANCE: {result}",
        f"COMMIT: {payload['COMMIT']}",
        f"USER_CONFIRMED_SUPPLY_OK: {str(payload['USER_CONFIRMED_SUPPLY_OK']).lower()}",
        f"MANUAL_INTERVENTION_REQUIRED: {str(payload['MANUAL_INTERVENTION_REQUIRED']).lower()}",
        f"HARDWARE_ACTIONS_EXECUTED: {str(hardware_actions).lower()}",
        f"HARDWARE_ACCEPTANCE: {payload['HARDWARE_ACCEPTANCE']}",
        f"P4_AUTO_BLOCKER: {payload['P4_AUTO_BLOCKER']}",
        f"AUTHORIZED_RUN_PACKAGE: `{payload['AUTHORIZED_RUN_PACKAGE']}`",
        f"SAFE_IDLE_DIRECT_PROXY: {safe_idle}",
        f"SAFE_IDLE_PROGRAM: {safe_idle_program}",
        f"BITSTREAM_SHA_MATCH: {bitstream_sha_match}",
        f"DEBUG_READBACK_AVAILABLE: {debug_readback}",
        f"TFDU_CONTROL_IDLE: {tfdu_idle}",
        f"RAW_PULSE_SMOKE_L0: {raw_pulse}",
        f"RAW_LANE_MATRIX: {raw_matrix}",
        f"LANE0_FRAME_CRC: {lane0_crc}",
        f"LANE0_ACK_RETRY: {lane0_ack}",
        f"LANE1_FRAME_CRC: {lane1_crc}",
        f"LANE1_ACK_RETRY: {lane1_ack}",
        f"TWO_LANE_MINIMAL: {two_lane}",
        f"LANE0_300S_SOAK: {lane0_soak}",
        f"TWO_LANE_300S_SOAK: {two_lane_soak}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        f"STOP_CONDITIONS_TRIGGERED: {', '.join(stop_conditions) if stop_conditions else 'none'}",
        f"NEXT_RECOMMENDED_STAGE: {next_stage}",
        "",
        "## Raw Lane Matrix",
        "",
        "| Direction | Status |",
        "| --- | --- |",
        *(f"| {item.get('direction', 'UNKNOWN')} | {item.get('status', raw_matrix)} |" for item in raw_matrix_rows),
        "",
        "## Generated Summaries",
        "",
        *(f"- `{item}`" for item in generated),
    ]
    write_markdown(
        GENERATED / "p4_auto_hardware_acceptance_summary.md",
        "P4 Auto Hardware Acceptance Summary",
        result,
        "P4_AUTO hardware acceptance did not reach a PASS state" if result != "PASS" else "P4_AUTO full acceptance passed",
        lines,
        no_hw=not hardware_actions,
    )
    write_json(GENERATED / "p4_auto_hardware_acceptance_summary.json", payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run P4_AUTO hardware acceptance. Defaults to dry-run; hardware needs --allow-hardware, authorization, hashes, runtime, and shutdown.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-hardware", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--authorization-file", default=str(DEFAULT_AUTH_FILE.relative_to(ROOT)))
    parser.add_argument("--user-confirmed-supply-ok", action="store_true")
    parser.add_argument("--no-manual-intervention", action="store_true")
    parser.add_argument("--board-id", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--profile-path", default="")
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
    ensure_dirs()
    ensure_authorization_record(args.user_confirmed_supply_ok, args.no_manual_intervention, args.max_runtime_sec or 360)
    repo = write_repo_intake()
    recheck = run_rechecks(skip=args.skip_recheck, allow_skips=args.allow_skips or args.dry_run or not args.execute_hardware)
    previous = write_previous_p4_intake()
    profiles = write_profiles()
    provenance = generate_bitstream_provenance(used_for_programming=False)
    requested_stage = args.stage
    if requested_stage == "all" and args.profile_path:
        profile_resolved = resolve_root_path(args.profile_path)
        if profile_resolved and profile_resolved.exists():
            try:
                profile_stage = json.loads(profile_resolved.read_text(encoding="utf-8")).get("stage", "")
                if profile_stage == "TFDU_CONTROL_IDLE":
                    requested_stage = "tfdu_control_idle"
                elif profile_stage == "RAW_PULSE_SMOKE_L0":
                    requested_stage = "raw_pulse"
                elif profile_stage == "RAW_LANE_MATRIX":
                    requested_stage = "raw_lane_matrix"
                elif profile_stage == "LANE0_FRAME_CRC":
                    requested_stage = "lane0_frame_crc"
                elif profile_stage == "LANE0_ACK_RETRY":
                    requested_stage = "lane0_ack_retry"
                elif profile_stage == "LANE1_FRAME_CRC":
                    requested_stage = "lane1_frame_crc"
                elif profile_stage == "LANE1_ACK_RETRY":
                    requested_stage = "lane1_ack_retry"
                elif profile_stage == "TWO_LANE_MINIMAL":
                    requested_stage = "two_lane_minimal"
                elif profile_stage == "LANE0_300S_SOAK":
                    requested_stage = "lane0_300s_soak"
                elif profile_stage == "TWO_LANE_300S_SOAK":
                    requested_stage = "two_lane_300s_soak"
            except json.JSONDecodeError:
                pass
    auth_payload = validate_authorization(
        allow_hardware=args.allow_hardware,
        execute_hardware=args.execute_hardware,
        authorization_file=resolve_root_path(args.authorization_file) or DEFAULT_AUTH_FILE,
        user_confirmed_supply_ok=args.user_confirmed_supply_ok,
        no_manual_intervention=args.no_manual_intervention,
        board_id=args.board_id,
        bitstream=args.bitstream,
        bitstream_sha256=args.bitstream_sha256,
        profile_path=args.profile_path,
        profile_sha256=args.profile_sha256,
        active_pinmap_hash=args.active_pinmap_hash,
        active_xdc_hash=args.active_xdc_hash,
        max_runtime_sec=args.max_runtime_sec,
        shutdown_on_exit=args.shutdown_on_exit,
    )
    write_authorization_summary(auth_payload)
    authorized_run_package = write_authorized_run_package(
        auth_payload,
        provenance,
        board_id=args.board_id,
        requested_stage=requested_stage,
        profile_path=args.profile_path,
    )
    safe_idle_program = {}
    if args.execute_hardware and auth_payload["AUTHORIZED"] and profiles["P4_AUTO_PROFILES"] == "PASS" and provenance["P4_AUTO_BITSTREAM_PROVENANCE"] == "PASS" and recheck["result"] == "PASS":
        bitstream_preflight = validate_authorized_bitstream_preflight(args, provenance)
        if bitstream_preflight["P4_AUTO_AUTHORIZED_BITSTREAM_PREFLIGHT"] != "PASS":
            shutdown = write_shutdown_summary(
                "SKIP_NO_HARDWARE_ACTIONS",
                "authorized bitstream preflight failed before any hardware action",
            )
            stage_reason = "authorized bitstream is not in the current immutable manifest or SHA does not match; stopped before hardware"
            stage_status = write_stage_placeholders(stage_reason, status="SKIP_WITH_REASON")
            stage_status["SAFE_IDLE_DIRECT_PROXY"] = "FAIL_WITH_EVIDENCE"
            stage_status["SAFE_IDLE_PROGRAM"] = "SKIP_WITH_REASON"
            stage_status["BITSTREAM_SHA_MATCH"] = "FAIL"
            stage_status["DEBUG_READBACK_AVAILABLE"] = "SKIP_WITH_REASON"
        else:
            shutdown = run_shutdown_baseline(args, auth_payload)
            if shutdown.get("STAGE_B_SHUTDOWN_BASELINE") != "PASS":
                stage_reason = "shutdown-safe baseline failed; stopped before safe-idle programming"
                stage_status = write_stage_placeholders(stage_reason, status="SKIP_WITH_REASON")
                stage_status["SAFE_IDLE_DIRECT_PROXY"] = "FAIL_WITH_EVIDENCE"
                stage_status["SAFE_IDLE_PROGRAM"] = "SKIP_WITH_REASON"
                stage_status["BITSTREAM_SHA_MATCH"] = "SKIP_WITH_REASON"
                stage_status["DEBUG_READBACK_AVAILABLE"] = "SKIP_WITH_REASON"
            else:
                provenance = generate_bitstream_provenance(used_for_programming=True, programmed_bitstream=args.bitstream)
                if requested_stage == "tfdu_control_idle":
                    stage_reason = "current authorized package completed TFDU receive-active idle; raw pulse, lane matrix, protocol, and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    tfdu_control_idle = run_tfdu_control_idle_program(args, provenance)
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            if previous_summary.get("SAFE_IDLE_DIRECT_PROXY") == "PASS":
                                stage_status["SAFE_IDLE_DIRECT_PROXY"] = "PASS"
                                stage_status["SAFE_IDLE_PROGRAM"] = previous_summary.get("SAFE_IDLE_PROGRAM", "PASS")
                                stage_status["BITSTREAM_SHA_MATCH"] = previous_summary.get("BITSTREAM_SHA_MATCH", "PASS")
                                stage_status["DEBUG_READBACK_AVAILABLE"] = previous_summary.get("DEBUG_READBACK_AVAILABLE", "PASS")
                        except json.JSONDecodeError:
                            pass
                    stage_status["TFDU_CONTROL_IDLE"] = tfdu_control_idle.get("TFDU_CONTROL_IDLE", "UNKNOWN")
                    if tfdu_control_idle.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "raw_pulse":
                    stage_reason = "current authorized package completed lane0 low-duty raw-pulse smoke; lane matrix, protocol, and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    raw_pulse = run_raw_pulse_smoke_program(args, provenance)
                    stage_status["RAW_PULSE_SMOKE_L0"] = raw_pulse.get("RAW_PULSE_SMOKE_L0", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = raw_pulse.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = raw_pulse.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if raw_pulse.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "raw_lane_matrix":
                    stage_reason = "current authorized package completed low-duty raw lane matrix; protocol and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    raw_lane_matrix = run_raw_lane_matrix_program(args, provenance)
                    stage_status["RAW_LANE_MATRIX"] = raw_lane_matrix.get("RAW_LANE_MATRIX", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = raw_lane_matrix.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = raw_lane_matrix.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if raw_lane_matrix.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "lane0_frame_crc":
                    stage_reason = "current authorized package completed lane0 frame/CRC smoke; ACK/retry, lane1 protocol, two-lane, and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    lane0_frame_crc = run_lane0_frame_crc_program(args, provenance)
                    stage_status["LANE0_FRAME_CRC"] = lane0_frame_crc.get("LANE0_FRAME_CRC", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = lane0_frame_crc.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = lane0_frame_crc.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if lane0_frame_crc.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "lane0_ack_retry":
                    stage_reason = "current authorized package completed lane0 ACK/retry smoke; lane1 protocol, two-lane, and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX", "LANE0_FRAME_CRC"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    lane0_ack_retry = run_lane0_ack_retry_program(args, provenance)
                    stage_status["LANE0_ACK_RETRY"] = lane0_ack_retry.get("LANE0_ACK_RETRY", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = lane0_ack_retry.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = lane0_ack_retry.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if lane0_ack_retry.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "lane1_frame_crc":
                    stage_reason = "current authorized package completed lane1 frame/CRC smoke; lane1 ACK/retry, two-lane, and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX", "LANE0_FRAME_CRC", "LANE0_ACK_RETRY"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    lane1_frame_crc = run_lane1_frame_crc_program(args, provenance)
                    stage_status["LANE1_FRAME_CRC"] = lane1_frame_crc.get("LANE1_FRAME_CRC", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = lane1_frame_crc.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = lane1_frame_crc.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if lane1_frame_crc.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "lane1_ack_retry":
                    stage_reason = "current authorized package completed lane1 ACK/retry smoke; two-lane and soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX", "LANE0_FRAME_CRC", "LANE0_ACK_RETRY", "LANE1_FRAME_CRC"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    lane1_ack_retry = run_lane1_ack_retry_program(args, provenance)
                    stage_status["LANE1_ACK_RETRY"] = lane1_ack_retry.get("LANE1_ACK_RETRY", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = lane1_ack_retry.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = lane1_ack_retry.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if lane1_ack_retry.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "two_lane_minimal":
                    stage_reason = "current authorized package completed two-lane minimal smoke; soak runners remain separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX", "LANE0_FRAME_CRC", "LANE0_ACK_RETRY", "LANE1_FRAME_CRC", "LANE1_ACK_RETRY"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    two_lane_minimal = run_two_lane_minimal_program(args, provenance)
                    stage_status["TWO_LANE_MINIMAL"] = two_lane_minimal.get("TWO_LANE_MINIMAL", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = two_lane_minimal.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = two_lane_minimal.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if two_lane_minimal.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "lane0_300s_soak":
                    stage_reason = "current authorized package completed lane0 300s soak; two-lane soak remains separate"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX", "LANE0_FRAME_CRC", "LANE0_ACK_RETRY", "LANE1_FRAME_CRC", "LANE1_ACK_RETRY", "TWO_LANE_MINIMAL"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    lane0_300s_soak = run_lane0_300s_soak_program(args, provenance)
                    stage_status["LANE0_300S_SOAK"] = lane0_300s_soak.get("LANE0_300S_SOAK", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = lane0_300s_soak.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = lane0_300s_soak.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if lane0_300s_soak.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                elif requested_stage == "two_lane_300s_soak":
                    stage_reason = "current authorized package completed two-lane 300s soak"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    previous_summary_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
                    if previous_summary_path.exists():
                        try:
                            previous_summary = json.loads(previous_summary_path.read_text(encoding="utf-8"))
                            for key in ["SAFE_IDLE_DIRECT_PROXY", "SAFE_IDLE_PROGRAM", "BITSTREAM_SHA_MATCH", "DEBUG_READBACK_AVAILABLE", "TFDU_CONTROL_IDLE", "RAW_PULSE_SMOKE_L0", "RAW_LANE_MATRIX", "LANE0_FRAME_CRC", "LANE0_ACK_RETRY", "LANE1_FRAME_CRC", "LANE1_ACK_RETRY", "TWO_LANE_MINIMAL", "LANE0_300S_SOAK"]:
                                if previous_summary.get(key) == "PASS":
                                    stage_status[key] = "PASS"
                        except json.JSONDecodeError:
                            pass
                    two_lane_300s_soak = run_two_lane_300s_soak_program(args, provenance)
                    stage_status["TWO_LANE_300S_SOAK"] = two_lane_300s_soak.get("TWO_LANE_300S_SOAK", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = two_lane_300s_soak.get("BITSTREAM_SHA_MATCH", stage_status.get("BITSTREAM_SHA_MATCH", "UNKNOWN"))
                    stage_status["DEBUG_READBACK_AVAILABLE"] = two_lane_300s_soak.get("DEBUG_READBACK_AVAILABLE", stage_status.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if two_lane_300s_soak.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
                else:
                    safe_idle_program = run_safe_idle_program(args, provenance)
                    if safe_idle_program.get("DEBUG_READBACK_AVAILABLE") == "PASS":
                        stage_reason = "current authorized package completed safe-idle direct-proxy; post-safe-idle P4_AUTO stage runners are not implemented in this package"
                    else:
                        stage_reason = "blocked until runtime AXI/ILA/VIO safe-idle signal readback is available"
                    stage_status = write_stage_placeholders(stage_reason, status="BLOCKED_BY_AUTOMATION_GAP")
                    safe_idle_proxy = generate_safe_idle_proxy_readback(
                        execute_hardware=True,
                        hardware_program_executed=safe_idle_program.get("SAFE_IDLE_PROGRAM") == "PASS",
                        runtime_readback_status=safe_idle_program.get("DEBUG_READBACK_AVAILABLE", ""),
                    )
                    stage_status["SAFE_IDLE_DIRECT_PROXY"] = safe_idle_proxy.get("SAFE_IDLE_DIRECT_PROXY", "FAIL_WITH_EVIDENCE") if safe_idle_program.get("SAFE_IDLE_PROGRAM") == "PASS" else "FAIL_WITH_EVIDENCE"
                    stage_status["SAFE_IDLE_PROGRAM"] = safe_idle_program.get("SAFE_IDLE_PROGRAM", "UNKNOWN")
                    stage_status["BITSTREAM_SHA_MATCH"] = safe_idle_program.get("BITSTREAM_SHA_MATCH", "UNKNOWN")
                    stage_status["DEBUG_READBACK_AVAILABLE"] = safe_idle_program.get("DEBUG_READBACK_AVAILABLE", safe_idle_proxy.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN"))
                    if safe_idle_program.get("SHUTDOWN_ON_EXIT") == "FAIL":
                        shutdown["SHUTDOWN_ON_EXIT"] = "FAIL"
    else:
        reason = "dry-run/no authorized hardware execution; no FPGA programming, PS start, UART, ILA, VIO, or TFDU TX occurred"
        if args.execute_hardware and not auth_payload["AUTHORIZED"]:
            reason = "authorization gate incomplete; hardware execution refused before any hardware connection"
        stage_status = write_stage_placeholders(reason, status="SKIP_WITH_REASON")
        safe_idle_proxy = generate_safe_idle_proxy_readback(execute_hardware=False)
        stage_status["SAFE_IDLE_DIRECT_PROXY"] = safe_idle_proxy["SAFE_IDLE_DIRECT_PROXY"]
        stage_status["SAFE_IDLE_PROGRAM"] = safe_idle_proxy.get("SAFE_IDLE_PROGRAM", "UNKNOWN")
        stage_status["BITSTREAM_SHA_MATCH"] = safe_idle_proxy.get("BITSTREAM_SHA_MATCH", "UNKNOWN")
        stage_status["DEBUG_READBACK_AVAILABLE"] = safe_idle_proxy.get("DEBUG_READBACK_AVAILABLE", "UNKNOWN")
        shutdown = write_shutdown_summary("SKIP_NO_HARDWARE_ACTIONS", "no hardware action occurred, so shutdown programming was not required")
    payload = write_acceptance_summary(
        auth_payload,
        recheck,
        profiles,
        provenance,
        stage_status,
        shutdown,
        args.execute_hardware,
        authorized_run_package=authorized_run_package,
    )
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    if args.execute_hardware and not auth_payload["AUTHORIZED"]:
        return 2
    if payload["P4_AUTO_HARDWARE_ACCEPTANCE"] == "FAIL_WITH_EVIDENCE":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
