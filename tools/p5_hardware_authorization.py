#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from p5_lib import (
    FAIL,
    GENERATED,
    NOT_RUN_OPTIONAL,
    P5_DIR,
    P5_STAGE,
    PASS,
    PASS_WITH_NOTES,
    PENDING_HW_NOT_EXECUTED,
    ROOT,
    SKIP,
    active_hashes,
    ensure_dirs,
    load_json,
    rel,
    sha256_or_missing,
    write_json,
    write_markdown,
    write_text,
)


AUTH_ENV = "RF_COMM_HW_AUTH"
AUTH_ENV_VALUE = "I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"
DEFAULT_AUTH_FILE = ROOT / ".hardware_authorization" / "P5_2LANE_APPROVED.txt"
DEFAULT_ABORT_FILE = ROOT / ".hardware_authorization" / "ABORT_NOW.txt"
DEFAULT_BOARD_ID = "AX7010"
DEFAULT_STAGE = "two_lane_30min_soak"
DEFAULT_SHUTDOWN_BITSTREAM = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"

REQUIRED_AUTH_PHRASES = [
    "I AUTHORIZE RF_COMM_MULTILANE P5 2-LANE PROTOCOL STABILIZATION ON CONNECTED HARDWARE.",
    "I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.",
    "AUTHORIZED_STAGE=P5_2LANE_PROTOCOL_STABILIZATION",
    "USER_CONFIRMED_SUPPLY_OK=true",
    "NETWORK_CABLE_CONNECTED=false",
    "HARDWARE_MOVEMENT_ALLOWED=false",
    "AVAILABLE_LANES=2",
    "MAX_LANE_MASK=0x3",
    "SHUTDOWN_ON_EXIT=required",
]


STAGE_PLAN: list[dict[str, Any]] = [
    {
        "plan_item": "P5.8",
        "stage": "safe_idle_recheck",
        "marker": "SAFE_IDLE_RECHECK",
        "profile": "profiles/p5/p5_safe_idle_recheck.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_safe_idle.bit"],
        "summary": "evidence/generated/p5_safe_idle_recheck_summary.md",
        "evidence_dir": "evidence/hardware/p5/safe_idle_recheck",
        "required_pass_markers": [
            "SAFE_IDLE_RECHECK: PASS",
            "TXD_STUCK_HIGH_VIOLATION: 0",
            "DUTY_WINDOW_VIOLATION: 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.8",
        "stage": "tfdu_control_idle_recheck",
        "marker": "TFDU_CONTROL_IDLE_RECHECK",
        "profile": "profiles/p5/p5_tfdu_control_idle_recheck.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit"],
        "summary": "evidence/generated/p5_tfdu_control_idle_recheck_summary.md",
        "evidence_dir": "evidence/hardware/p5/tfdu_control_idle_recheck",
        "required_pass_markers": [
            "TFDU_CONTROL_IDLE_RECHECK: PASS",
            "MODE_PROXY_READBACK: high_speed",
            "TXD_STUCK_HIGH_VIOLATION: 0",
            "DUTY_WINDOW_VIOLATION: 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.9",
        "stage": "raw_lane_matrix_fresh",
        "marker": "RAW_LANE_MATRIX_FRESH",
        "profile": "profiles/p5/p5_raw_lane_matrix_fresh.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit"],
        "summary": "evidence/generated/p5_raw_lane_matrix_summary.md",
        "evidence_dir": "evidence/hardware/p5/raw_lane_matrix",
        "required_pass_markers": [
            "AB_L0: PASS",
            "BA_L0: PASS",
            "AB_L1: PASS",
            "BA_L1: PASS",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.10",
        "stage": "lane0_frame_crc_100",
        "marker": "LANE0_FRAME_CRC_100",
        "profile": "profiles/p5/p5_lane0_frame_crc_100.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_lane0.bit"],
        "summary": "evidence/generated/p5_lane0_frame_crc_100_summary.md",
        "evidence_dir": "evidence/hardware/p5/protocol/lane0_frame_crc_100",
        "required_pass_markers": [
            "SENT_FRAMES >= 100",
            "RX_GOOD == SENT_FRAMES",
            "CRC_BAD == 0",
            "PAYLOAD_MISMATCH == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.10",
        "stage": "lane1_frame_crc_100",
        "marker": "LANE1_FRAME_CRC_100",
        "profile": "profiles/p5/p5_lane1_frame_crc_100.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_lane1.bit"],
        "summary": "evidence/generated/p5_lane1_frame_crc_100_summary.md",
        "evidence_dir": "evidence/hardware/p5/protocol/lane1_frame_crc_100",
        "required_pass_markers": [
            "SENT_FRAMES >= 100",
            "RX_GOOD == SENT_FRAMES",
            "CRC_BAD == 0",
            "PAYLOAD_MISMATCH == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.11",
        "stage": "lane0_ack_retry_100",
        "marker": "LANE0_ACK_RETRY_100",
        "profile": "profiles/p5/p5_lane0_ack_retry_100.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit"],
        "summary": "evidence/generated/p5_lane0_ack_retry_100_summary.md",
        "evidence_dir": "evidence/hardware/p5/protocol/lane0_ack_retry_100",
        "required_pass_markers": [
            "A_SENT_FRAMES >= 100",
            "B_RX_GOOD == A_SENT_FRAMES",
            "A_ACK_SEEN == A_SENT_FRAMES",
            "TX_RETRY_EXHAUSTED == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.11",
        "stage": "lane1_ack_retry_100",
        "marker": "LANE1_ACK_RETRY_100",
        "profile": "profiles/p5/p5_lane1_ack_retry_100.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit"],
        "summary": "evidence/generated/p5_lane1_ack_retry_100_summary.md",
        "evidence_dir": "evidence/hardware/p5/protocol/lane1_ack_retry_100",
        "required_pass_markers": [
            "A_SENT_FRAMES >= 100",
            "B_RX_GOOD == A_SENT_FRAMES",
            "A_ACK_SEEN == A_SENT_FRAMES",
            "TX_RETRY_EXHAUSTED == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.12",
        "stage": "two_lane_minimal_100",
        "marker": "TWO_LANE_MINIMAL_100",
        "profile": "profiles/p5/p5_two_lane_minimal_100.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit"],
        "summary": "evidence/generated/p5_two_lane_minimal_100_summary.md",
        "evidence_dir": "evidence/hardware/p5/protocol/two_lane_minimal_100",
        "required_pass_markers": [
            "LANE0_RX_GOOD >= 100",
            "LANE1_RX_GOOD >= 100",
            "TX_RETRY_EXHAUSTED == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.13",
        "stage": "payload_sweep",
        "marker": "PAYLOAD_SWEEP",
        "profile": "profiles/p5/p5_two_lane_payload_sweep.json",
        "bitstreams": [
            "evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit",
            "evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit",
            "evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit",
        ],
        "summary": "evidence/generated/p5_payload_sweep_summary.md",
        "evidence_dir": "evidence/hardware/p5/payload_sweep",
        "required_pass_markers": [
            "PAYLOAD_SWEEP: PASS or PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED",
            "CRC_BAD == 0",
            "PAYLOAD_MISMATCH == 0",
            "TX_RETRY_EXHAUSTED == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.14",
        "stage": "mask_regression",
        "marker": "MASK_REGRESSION",
        "profile": "profiles/p5/p5_two_lane_mask_regression.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit"],
        "summary": "evidence/generated/p5_mask_regression_summary.md",
        "evidence_dir": "evidence/hardware/p5/mask_regression",
        "required_pass_markers": [
            "positive cases PASS",
            "negative cases REJECTED_AS_EXPECTED or FAIL_SAFE_AS_EXPECTED",
            "no infinite retry",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.15",
        "stage": "retry_fault_injection_hw_optional",
        "marker": "RETRY_FAULT_INJECTION_HW_OPTIONAL",
        "profile": "profiles/p5/p5_retry_fault_injection_hw_optional.json",
        "bitstreams": [],
        "summary": "evidence/generated/p5_retry_fault_injection_summary.md",
        "evidence_dir": "evidence/hardware/p5/retry_fault_injection_optional",
        "required_pass_markers": [
            "RETRY_FAULT_INJECTION_HW_OPTIONAL: PASS or SKIP_NO_HW_FAULT_INJECTION_HOOK",
            "SHUTDOWN_ON_EXIT: PASS when hardware hook is used",
        ],
        "optional_skip": "SKIP_NO_HW_FAULT_INJECTION_HOOK",
        "stop_on_fail": False,
    },
    {
        "plan_item": "P5.16",
        "stage": "two_lane_30min_soak",
        "marker": "TWO_LANE_30MIN_SOAK",
        "profile": "profiles/p5/p5_two_lane_30min_soak.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit"],
        "summary": "evidence/generated/p5_two_lane_30min_soak_summary.md",
        "evidence_dir": "evidence/hardware/p5/soak/two_lane_30min",
        "required_pass_markers": [
            "TWO_LANE_30MIN_SOAK: PASS",
            "runtime_sec >= 1800 or documented bounded runtime",
            "TX_RETRY_EXHAUSTED == 0",
            "CRC_BAD == 0",
            "PAYLOAD_MISMATCH == 0",
            "SHUTDOWN_ON_EXIT: PASS",
        ],
        "stop_on_fail": True,
    },
    {
        "plan_item": "P5.16 optional",
        "stage": "two_lane_2h_soak_optional",
        "marker": "TWO_LANE_2H_SOAK_OPTIONAL",
        "profile": "profiles/p5/p5_two_lane_2h_soak_optional.json",
        "bitstreams": ["evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit"],
        "summary": "evidence/generated/p5_two_lane_2h_soak_optional_summary.md",
        "evidence_dir": "evidence/hardware/p5/soak/two_lane_2h_optional",
        "required_pass_markers": [
            "TWO_LANE_2H_SOAK_OPTIONAL: PASS or NOT_RUN_OPTIONAL",
            "run only after TWO_LANE_30MIN_SOAK: PASS",
        ],
        "optional_skip": NOT_RUN_OPTIONAL,
        "stop_on_fail": False,
    },
]


def resolve_root_path(value: str | Path | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def ensure_authorization_template(max_runtime_sec: int = 1800) -> Path:
    template = ROOT / ".hardware_authorization" / "P5_2LANE_APPROVED.txt.template"
    body = f"""I AUTHORIZE RF_COMM_MULTILANE P5 2-LANE PROTOCOL STABILIZATION ON CONNECTED HARDWARE.
I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.
AUTHORIZED_STAGE=P5_2LANE_PROTOCOL_STABILIZATION
USER_CONFIRMED_SUPPLY_OK=true
NETWORK_CABLE_CONNECTED=false
HARDWARE_MOVEMENT_ALLOWED=false
AVAILABLE_LANES=2
MAX_LANE_MASK=0x3
ALLOWED_AUTOMATION=Vivado batch, JTAG, XSDB, AXI/JTAG-to-AXI, PS driver, ILA, VIO, debug registers, log parsing
FORBIDDEN=Ethernet acceptance, rotation/motion, lane_mask_above_0x3, unbounded TX, missing shutdown, stale bitstream
MAX_RUNTIME_SEC={max_runtime_sec}
SHUTDOWN_ON_EXIT=required
AUTHORIZED_BY=<user>
DATE=<YYYY-MM-DD>
"""
    write_text(template, body)
    return template


def parse_authorization_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "exists": path.exists(),
        "valid": False,
        "missing": [],
        "fields": {},
        "sha256": sha256_or_missing(path),
    }
    if not path.exists():
        result["missing"].append(rel(path))
        return result
    text = path.read_text(encoding="utf-8", errors="ignore")
    for phrase in REQUIRED_AUTH_PHRASES:
        if phrase not in text:
            result["missing"].append(phrase)
    field_patterns = {
        "MAX_RUNTIME_SEC": r"(?m)^MAX_RUNTIME_SEC=(\d+)\s*$",
        "AUTHORIZED_BY": r"(?m)^AUTHORIZED_BY=(.+?)\s*$",
        "DATE": r"(?m)^DATE=(\d{4}-\d{2}-\d{2})\s*$",
    }
    for key, pattern in field_patterns.items():
        match = re.search(pattern, text)
        if match:
            result["fields"][key] = match.group(1).strip()
        else:
            result["missing"].append(key)
    if "DATE" in result["fields"]:
        try:
            datetime.strptime(result["fields"]["DATE"], "%Y-%m-%d")
        except ValueError:
            result["missing"].append("DATE must be YYYY-MM-DD")
    if "MAX_RUNTIME_SEC" in result["fields"] and int(result["fields"]["MAX_RUNTIME_SEC"]) <= 0:
        result["missing"].append("MAX_RUNTIME_SEC must be positive")
    result["valid"] = not result["missing"]
    return result


def _add_hash_check(missing: list[str], flag: str, provided: str, actual: str, *, required: bool = True) -> None:
    if not required and not provided:
        return
    if not provided:
        missing.append(flag)
    elif actual == "MISSING":
        missing.append(f"{flag} actual file missing")
    elif provided.lower() != actual.lower():
        missing.append(f"{flag} mismatch: expected {actual}, got {provided}")


def validate_authorization(
    *,
    allow_hardware: bool,
    execute_hardware: bool,
    authorization_file: Path,
    board_id: str,
    bitstream: str,
    bitstream_sha256: str,
    profile: str,
    profile_sha256: str,
    active_pinmap_hash: str,
    active_xdc_hash: str,
    shutdown_bitstream: str,
    shutdown_bitstream_sha256: str,
    max_runtime_sec: int | None,
    shutdown_on_exit: bool,
    lane_count: int = 2,
    abort_file: Path = DEFAULT_ABORT_FILE,
    require_env: bool = True,
) -> dict[str, Any]:
    parsed = parse_authorization_file(authorization_file)
    missing: list[str] = []
    profile_path = resolve_root_path(profile)
    bitstream_path = resolve_root_path(bitstream)
    shutdown_path = resolve_root_path(shutdown_bitstream) or DEFAULT_SHUTDOWN_BITSTREAM
    hashes = active_hashes()
    actual_profile_sha = sha256_or_missing(profile_path) if profile_path else "MISSING"
    actual_bitstream_sha = sha256_or_missing(bitstream_path) if bitstream_path else "MISSING"
    actual_shutdown_sha = sha256_or_missing(shutdown_path)

    if execute_hardware and not allow_hardware:
        missing.append("--allow-hardware")
    if not execute_hardware:
        missing.append("--execute-hardware")
    if lane_count != 2:
        missing.append("--lane-count 2")
    if not max_runtime_sec or max_runtime_sec <= 0:
        missing.append("--max-runtime-sec")
    if not shutdown_on_exit:
        missing.append("--shutdown-on-exit")
    if execute_hardware:
        if not board_id:
            missing.append("--board-id")
        if not bitstream:
            missing.append("--bitstream")
        elif not bitstream_path or not bitstream_path.exists():
            missing.append(f"--bitstream missing: {bitstream}")
        if not profile:
            missing.append("--profile")
        elif not profile_path or not profile_path.exists():
            missing.append(f"--profile missing: {profile}")
        _add_hash_check(missing, "--bitstream-sha256", bitstream_sha256, actual_bitstream_sha)
        _add_hash_check(missing, "--profile-sha256", profile_sha256, actual_profile_sha)
        _add_hash_check(missing, "--active-pinmap-hash", active_pinmap_hash, hashes.get("pinmap", "MISSING"))
        _add_hash_check(missing, "--active-xdc-hash", active_xdc_hash, hashes.get("active_xdc", "MISSING"))
        _add_hash_check(missing, "--shutdown-bitstream-sha256", shutdown_bitstream_sha256, actual_shutdown_sha)
        if not shutdown_path.exists():
            missing.append(f"--shutdown-bitstream missing: {rel(shutdown_path)}")
        if require_env and os.environ.get(AUTH_ENV) != AUTH_ENV_VALUE:
            missing.append(f"{AUTH_ENV}={AUTH_ENV_VALUE}")
        if abort_file.exists():
            missing.append(f"operator abort file present: {rel(abort_file)}")
    missing.extend(parsed["missing"])
    auth_runtime = parsed["fields"].get("MAX_RUNTIME_SEC")
    if auth_runtime and max_runtime_sec and int(auth_runtime) < int(max_runtime_sec):
        missing.append("MAX_RUNTIME_SEC in authorization file is lower than requested runtime")

    authorized = execute_hardware and allow_hardware and not missing
    return {
        "P5_HARDWARE_AUTHORIZATION": "AUTHORIZED" if authorized else "BLOCKED_NOT_AUTHORIZED",
        "AUTHORIZED": authorized,
        "AUTHORIZATION_FILE": rel(authorization_file),
        "AUTHORIZATION_FILE_EXISTS": parsed["exists"],
        "AUTHORIZATION_FILE_SHA256": parsed["sha256"],
        "RF_COMM_HW_AUTH_PRESENT": os.environ.get(AUTH_ENV) == AUTH_ENV_VALUE,
        "BOARD_ID": board_id or "MISSING",
        "LANE_COUNT": lane_count,
        "BITSTREAM": rel(bitstream_path) if bitstream_path else "MISSING",
        "BITSTREAM_SHA256": actual_bitstream_sha,
        "BITSTREAM_SHA256_EXPECTED": bitstream_sha256 or "MISSING",
        "PROFILE": rel(profile_path) if profile_path else "MISSING",
        "PROFILE_SHA256": actual_profile_sha,
        "PROFILE_SHA256_EXPECTED": profile_sha256 or "MISSING",
        "ACTIVE_PINMAP_HASH": hashes.get("pinmap", "MISSING"),
        "ACTIVE_PINMAP_HASH_EXPECTED": active_pinmap_hash or "MISSING",
        "ACTIVE_XDC_HASH": hashes.get("active_xdc", "MISSING"),
        "ACTIVE_XDC_HASH_EXPECTED": active_xdc_hash or "MISSING",
        "SHUTDOWN_BITSTREAM": rel(shutdown_path),
        "SHUTDOWN_BITSTREAM_SHA256": actual_shutdown_sha,
        "SHUTDOWN_BITSTREAM_SHA256_EXPECTED": shutdown_bitstream_sha256 or "MISSING",
        "MAX_RUNTIME_SEC": max_runtime_sec or "MISSING",
        "SHUTDOWN_ON_EXIT": shutdown_on_exit,
        "ABORT_FILE": rel(abort_file),
        "ABORT_FILE_PRESENT": abort_file.exists(),
        "missing": missing,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def write_authorization_summary(payload: dict[str, Any]) -> dict[str, Any]:
    status = PASS if payload.get("AUTHORIZED") else "BLOCKED_NOT_AUTHORIZED"
    reason = "P5 hardware authorization is complete" if payload.get("AUTHORIZED") else "P5 hardware authorization is incomplete or not requested"
    lines = [
        f"P5_HARDWARE_AUTHORIZATION: {payload['P5_HARDWARE_AUTHORIZATION']}",
        f"AUTHORIZED: {str(payload['AUTHORIZED']).lower()}",
        f"AUTHORIZATION_FILE: `{payload['AUTHORIZATION_FILE']}`",
        f"AUTHORIZATION_FILE_EXISTS: {str(payload['AUTHORIZATION_FILE_EXISTS']).lower()}",
        f"AUTHORIZATION_FILE_SHA256: `{payload['AUTHORIZATION_FILE_SHA256']}`",
        f"RF_COMM_HW_AUTH_PRESENT: {str(payload['RF_COMM_HW_AUTH_PRESENT']).lower()}",
        f"BOARD_ID: `{payload['BOARD_ID']}`",
        f"LANE_COUNT: {payload['LANE_COUNT']}",
        f"BITSTREAM: `{payload['BITSTREAM']}`",
        f"BITSTREAM_SHA256: `{payload['BITSTREAM_SHA256']}`",
        f"BITSTREAM_SHA256_EXPECTED: `{payload['BITSTREAM_SHA256_EXPECTED']}`",
        f"PROFILE: `{payload['PROFILE']}`",
        f"PROFILE_SHA256: `{payload['PROFILE_SHA256']}`",
        f"PROFILE_SHA256_EXPECTED: `{payload['PROFILE_SHA256_EXPECTED']}`",
        f"ACTIVE_PINMAP_HASH: `{payload['ACTIVE_PINMAP_HASH']}`",
        f"ACTIVE_PINMAP_HASH_EXPECTED: `{payload['ACTIVE_PINMAP_HASH_EXPECTED']}`",
        f"ACTIVE_XDC_HASH: `{payload['ACTIVE_XDC_HASH']}`",
        f"ACTIVE_XDC_HASH_EXPECTED: `{payload['ACTIVE_XDC_HASH_EXPECTED']}`",
        f"SHUTDOWN_BITSTREAM: `{payload['SHUTDOWN_BITSTREAM']}`",
        f"SHUTDOWN_BITSTREAM_SHA256: `{payload['SHUTDOWN_BITSTREAM_SHA256']}`",
        f"SHUTDOWN_BITSTREAM_SHA256_EXPECTED: `{payload['SHUTDOWN_BITSTREAM_SHA256_EXPECTED']}`",
        f"MAX_RUNTIME_SEC: `{payload['MAX_RUNTIME_SEC']}`",
        f"SHUTDOWN_ON_EXIT: {str(payload['SHUTDOWN_ON_EXIT']).lower()}",
        f"ABORT_FILE_PRESENT: {str(payload['ABORT_FILE_PRESENT']).lower()}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Missing Controls",
        "",
        *(f"- `{item}`" for item in payload["missing"]),
        *(["- none"] if not payload["missing"] else []),
    ]
    auth_dir = P5_DIR / "authorization"
    write_markdown(
        auth_dir / "p5_hardware_authorization_record.md",
        "P5 Hardware Authorization Record",
        status,
        reason,
        lines,
    )
    write_markdown(
        GENERATED / "p5_hardware_authorization_summary.md",
        "P5 Hardware Authorization Summary",
        status,
        reason,
        lines,
    )
    return {
        "P5_HARDWARE_AUTHORIZATION": payload["P5_HARDWARE_AUTHORIZATION"],
        "P5_HARDWARE_AUTHORIZATION_SUMMARY": rel(GENERATED / "p5_hardware_authorization_summary.md"),
        "AUTHORIZED": payload["AUTHORIZED"],
    }


def _profile_runtime(profile_rel: str, fallback: int) -> int:
    data = load_json(ROOT / profile_rel)
    if isinstance(data, dict):
        try:
            return int(data.get("max_runtime_sec") or fallback)
        except Exception:
            return fallback
    return fallback


def _artifact_row(stage: dict[str, Any], order: int) -> dict[str, Any]:
    profile_rel = stage["profile"]
    profile_path = ROOT / profile_rel
    bitstreams = []
    missing = []
    for bitstream_rel in stage.get("bitstreams", []):
        bitstream_path = ROOT / bitstream_rel
        bitstream_sha = sha256_or_missing(bitstream_path)
        if bitstream_sha == "MISSING":
            missing.append(bitstream_rel)
        bitstreams.append({"path": bitstream_rel, "sha256": bitstream_sha})
    profile_sha = sha256_or_missing(profile_path)
    if profile_sha == "MISSING":
        missing.append(profile_rel)
    if stage.get("optional_skip") == NOT_RUN_OPTIONAL:
        status = NOT_RUN_OPTIONAL
    elif not bitstreams and stage.get("optional_skip"):
        status = stage["optional_skip"]
    else:
        status = "READY_FOR_AUTHORIZATION" if not missing else "MISSING_ARTIFACT"
    return {
        "order": order,
        "plan_item": stage["plan_item"],
        "stage": stage["stage"],
        "marker": stage["marker"],
        "status": status,
        "profile": profile_rel,
        "profile_sha256": profile_sha,
        "bitstreams": bitstreams,
        "max_runtime_sec": _profile_runtime(profile_rel, 300),
        "summary": stage["summary"],
        "evidence_dir": stage["evidence_dir"],
        "required_pass_markers": stage["required_pass_markers"],
        "stop_on_fail": bool(stage.get("stop_on_fail")),
        "missing_artifacts": missing,
    }


def generate_stage_plan() -> dict[str, Any]:
    ensure_dirs()
    rows = [_artifact_row(stage, index + 1) for index, stage in enumerate(STAGE_PLAN)]
    required_missing = [
        row
        for row in rows
        if row["status"] == "MISSING_ARTIFACT" and row["marker"] not in {"RETRY_FAULT_INJECTION_HW_OPTIONAL", "TWO_LANE_2H_SOAK_OPTIONAL"}
    ]
    optional_notes = [row for row in rows if row["status"] in {"SKIP_NO_HW_FAULT_INJECTION_HOOK", NOT_RUN_OPTIONAL}]
    result = SKIP if required_missing else PASS_WITH_NOTES if optional_notes else PASS
    hashes = active_hashes()
    payload = {
        "P5_HARDWARE_STAGE_PLAN": result,
        "rows": rows,
        "required_missing_count": len(required_missing),
        "optional_note_count": len(optional_notes),
        "active_hashes": hashes,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(GENERATED / "p5_hardware_stage_plan_summary.json", payload)
    lines = [
        f"P5_HARDWARE_STAGE_PLAN: {result}",
        f"REQUIRED_MISSING_ARTIFACTS: {len(required_missing)}",
        f"OPTIONAL_NOTES: {len(optional_notes)}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Active Input Hashes",
        "",
        *(f"- {name}: `{value}`" for name, value in hashes.items()),
        "",
        "## Stage Plan",
        "",
        "| Order | Stage | Status | Profile | Bitstream SHA(s) | Stop on Fail |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        sha_text = "<br>".join(f"`{item['sha256']}`" for item in row["bitstreams"]) if row["bitstreams"] else row["status"]
        lines.append(
            f"| {row['order']} | {row['stage']} | {row['status']} | `{row['profile']}` | {sha_text} | {str(row['stop_on_fail']).lower()} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is a dry-run hardware stage plan only.",
            "- P5 hardware stages remain PENDING_HW until an authorized safe wrapper run writes fresh evidence and shutdown logs.",
            "- Ethernet, motion/rotation, lane masks above 0x3, and 8-lane acceptance remain out of scope.",
        ]
    )
    write_markdown(
        GENERATED / "p5_hardware_stage_plan_summary.md",
        "P5 Hardware Stage Plan Summary",
        result,
        "P5 hardware stage plan generated without executing hardware",
        lines,
    )
    return payload


def _stage_by_name(stage_name: str) -> dict[str, Any]:
    for stage in STAGE_PLAN:
        if stage["stage"] == stage_name:
            return stage
    for stage in STAGE_PLAN:
        if stage["stage"] == DEFAULT_STAGE:
            return stage
    raise KeyError(DEFAULT_STAGE)


def write_authorized_run_package(
    *,
    auth_payload: dict[str, Any] | None = None,
    stage: str = DEFAULT_STAGE,
    board_id: str = DEFAULT_BOARD_ID,
    authorization_file: Path = DEFAULT_AUTH_FILE,
    profile: str = "",
    bitstream: str = "",
    max_runtime_sec: int | None = None,
    lane_count: int = 2,
    shutdown_bitstream: str = str(DEFAULT_SHUTDOWN_BITSTREAM.relative_to(ROOT)),
) -> dict[str, Any]:
    ensure_dirs()
    ensure_authorization_template(max_runtime_sec or 1800)
    stage_def = _stage_by_name(stage)
    profile_rel = profile or stage_def["profile"]
    bitstream_rel = bitstream or (stage_def.get("bitstreams") or [""])[0]
    runtime = max_runtime_sec or _profile_runtime(profile_rel, 1800)
    hashes = active_hashes()
    profile_sha = sha256_or_missing(ROOT / profile_rel)
    bitstream_sha = sha256_or_missing(ROOT / bitstream_rel) if bitstream_rel else "MISSING"
    shutdown_rel = rel(resolve_root_path(shutdown_bitstream) or DEFAULT_SHUTDOWN_BITSTREAM)
    shutdown_sha = sha256_or_missing(ROOT / shutdown_rel)

    projected_auth = validate_authorization(
        allow_hardware=True,
        execute_hardware=True,
        authorization_file=authorization_file,
        board_id=board_id,
        bitstream=bitstream_rel,
        bitstream_sha256=bitstream_sha,
        profile=profile_rel,
        profile_sha256=profile_sha,
        active_pinmap_hash=hashes.get("pinmap", "MISSING"),
        active_xdc_hash=hashes.get("active_xdc", "MISSING"),
        shutdown_bitstream=shutdown_rel,
        shutdown_bitstream_sha256=shutdown_sha,
        max_runtime_sec=runtime,
        shutdown_on_exit=True,
        lane_count=lane_count,
    )
    artifact_missing = bitstream_sha == "MISSING" or profile_sha == "MISSING" or shutdown_sha == "MISSING"
    package_status = SKIP if artifact_missing else "READY_FOR_AUTHORIZATION"
    if projected_auth.get("AUTHORIZED"):
        package_status = "READY_AUTHORIZED"

    auth_rel = rel(authorization_file)
    python_args = [
        "tools/run_p5_gate.py",
        "--allow-hardware",
        "--execute-hardware",
        "--authorization-file",
        auth_rel,
        "--board-id",
        board_id,
        "--shutdown-on-exit",
        "--max-runtime-sec",
        str(runtime),
        "--stage-filter",
        stage_def["stage"],
        "--lane-count",
        str(lane_count),
        "--profile",
        profile_rel,
        "--profile-sha256",
        profile_sha,
        "--bitstream",
        bitstream_rel,
        "--bitstream-sha256",
        bitstream_sha,
        "--active-pinmap-hash",
        hashes.get("pinmap", "MISSING"),
        "--active-xdc-hash",
        hashes.get("active_xdc", "MISSING"),
        "--shutdown-bitstream",
        shutdown_rel,
        "--shutdown-bitstream-sha256",
        shutdown_sha,
        "--skip-ethernet",
        "--skip-motion",
        "--stop-on-first-fail",
        "--json-summary",
    ]
    python_command = " ".join(["python", *python_args])
    ps_command = " ".join(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            "tools\\run_p5_gate.ps1",
            "-AllowHardware",
            "-ExecuteHardware",
            "-AuthorizationFile",
            auth_rel.replace("/", "\\"),
            "-BoardId",
            board_id,
            "-ShutdownOnExit",
            "-MaxRuntimeSec",
            str(runtime),
            "-StageFilter",
            stage_def["stage"],
            "-LaneCount",
            str(lane_count),
            "-Profile",
            profile_rel.replace("/", "\\"),
            "-ProfileSha256",
            profile_sha,
            "-Bitstream",
            bitstream_rel.replace("/", "\\"),
            "-BitstreamSha256",
            bitstream_sha,
            "-ActivePinmapHash",
            hashes.get("pinmap", "MISSING"),
            "-ActiveXdcHash",
            hashes.get("active_xdc", "MISSING"),
            "-ShutdownBitstream",
            shutdown_rel.replace("/", "\\"),
            "-ShutdownBitstreamSha256",
            shutdown_sha,
            "-SkipEthernet",
            "-SkipMotion",
            "-StopOnFirstFail",
            "-JsonSummary",
        ]
    )
    payload = {
        "P5_AUTHORIZED_RUN_PACKAGE": package_status,
        "AUTHORIZATION_STATUS_AT_GENERATION": (auth_payload or {}).get("P5_HARDWARE_AUTHORIZATION", "NOT_EVALUATED"),
        "PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS": projected_auth["P5_HARDWARE_AUTHORIZATION"],
        "PROJECTED_MISSING_CONTROLS_BEFORE_RUN": projected_auth["missing"],
        "RF_COMM_HW_AUTH_REQUIRED": f"{AUTH_ENV}={AUTH_ENV_VALUE}",
        "BOARD_ID": board_id,
        "STAGE": stage_def["stage"],
        "MARKER": stage_def["marker"],
        "MAX_RUNTIME_SEC": runtime,
        "LANE_COUNT": lane_count,
        "AUTHORIZATION_FILE": auth_rel,
        "BITSTREAM": bitstream_rel,
        "BITSTREAM_SHA256": bitstream_sha,
        "PROFILE": profile_rel,
        "PROFILE_SHA256": profile_sha,
        "ACTIVE_PINMAP_HASH": hashes.get("pinmap", "MISSING"),
        "ACTIVE_XDC_HASH": hashes.get("active_xdc", "MISSING"),
        "SHUTDOWN_BITSTREAM": shutdown_rel,
        "SHUTDOWN_BITSTREAM_SHA256": shutdown_sha,
        "POWERSHELL_ENV_COMMAND": f"$env:{AUTH_ENV}='{AUTH_ENV_VALUE}'",
        "PYTHON_COMMAND": python_command,
        "POWERSHELL_COMMAND": ps_command,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    json_path = P5_DIR / "authorization" / "p5_authorized_run_package.json"
    write_json(json_path, payload)
    lines = [
        f"P5_AUTHORIZED_RUN_PACKAGE: {payload['P5_AUTHORIZED_RUN_PACKAGE']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"AUTHORIZATION_STATUS_AT_GENERATION: {payload['AUTHORIZATION_STATUS_AT_GENERATION']}",
        f"PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS: {payload['PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS']}",
        f"RF_COMM_HW_AUTH_REQUIRED: `{payload['RF_COMM_HW_AUTH_REQUIRED']}`",
        f"BOARD_ID: `{payload['BOARD_ID']}`",
        f"STAGE: `{payload['STAGE']}`",
        f"MARKER: `{payload['MARKER']}`",
        f"MAX_RUNTIME_SEC: {payload['MAX_RUNTIME_SEC']}",
        f"LANE_COUNT: {payload['LANE_COUNT']}",
        f"AUTHORIZATION_FILE: `{payload['AUTHORIZATION_FILE']}`",
        f"BITSTREAM: `{payload['BITSTREAM']}`",
        f"BITSTREAM_SHA256: `{payload['BITSTREAM_SHA256']}`",
        f"PROFILE: `{payload['PROFILE']}`",
        f"PROFILE_SHA256: `{payload['PROFILE_SHA256']}`",
        f"ACTIVE_PINMAP_HASH: `{payload['ACTIVE_PINMAP_HASH']}`",
        f"ACTIVE_XDC_HASH: `{payload['ACTIVE_XDC_HASH']}`",
        f"SHUTDOWN_BITSTREAM: `{payload['SHUTDOWN_BITSTREAM']}`",
        f"SHUTDOWN_BITSTREAM_SHA256: `{payload['SHUTDOWN_BITSTREAM_SHA256']}`",
        "",
        "## Projected Missing Controls Before Run",
        "",
        *(f"- `{item}`" for item in payload["PROJECTED_MISSING_CONTROLS_BEFORE_RUN"]),
        *(["- none"] if not payload["PROJECTED_MISSING_CONTROLS_BEFORE_RUN"] else []),
        "",
        "## PowerShell",
        "",
        "```powershell",
        payload["POWERSHELL_ENV_COMMAND"],
        payload["POWERSHELL_COMMAND"],
        "```",
        "",
        "## Python",
        "",
        "```powershell",
        payload["POWERSHELL_ENV_COMMAND"],
        payload["PYTHON_COMMAND"],
        "```",
        "",
        "## Boundary",
        "",
        "- This package records the exact artifact hashes and command arguments for a future authorized P5 run.",
        "- It does not execute hardware and does not promote P5 hardware acceptance.",
        "- The current P5 runner still refuses to claim PASS unless fresh P5 hardware evidence and shutdown logs exist.",
    ]
    write_markdown(
        GENERATED / "p5_authorized_run_package_summary.md",
        "P5 Authorized Run Package Summary",
        package_status,
        "P5 authorized-run inputs recorded without executing hardware",
        lines,
    )
    write_markdown(
        P5_DIR / "authorization" / "p5_authorized_run_package.md",
        "P5 Authorized Run Package Summary",
        package_status,
        "P5 authorized-run inputs recorded without executing hardware",
        lines,
    )
    return {
        "P5_AUTHORIZED_RUN_PACKAGE": package_status,
        "P5_AUTHORIZED_RUN_PACKAGE_SUMMARY": rel(GENERATED / "p5_authorized_run_package_summary.md"),
        "P5_AUTHORIZED_RUN_PACKAGE_JSON": rel(json_path),
        "PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS": projected_auth["P5_HARDWARE_AUTHORIZATION"],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and validate P5 hardware authorization without touching hardware.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-hardware", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--authorization-file", default=str(DEFAULT_AUTH_FILE.relative_to(ROOT)))
    parser.add_argument("--board-id", default=DEFAULT_BOARD_ID)
    parser.add_argument("--stage", default=DEFAULT_STAGE)
    parser.add_argument("--profile", default="")
    parser.add_argument("--profile-sha256", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--active-pinmap-hash", default="")
    parser.add_argument("--active-xdc-hash", default="")
    parser.add_argument("--shutdown-bitstream", default=str(DEFAULT_SHUTDOWN_BITSTREAM.relative_to(ROOT)))
    parser.add_argument("--shutdown-bitstream-sha256", default="")
    parser.add_argument("--max-runtime-sec", type=int)
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--lane-count", type=int, default=2)
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_dirs()
    template = ensure_authorization_template(args.max_runtime_sec or 1800)
    stage_plan = generate_stage_plan()
    stage_def = _stage_by_name(args.stage)
    bitstream = args.bitstream or ((stage_def.get("bitstreams") or [""])[0])
    profile = args.profile or stage_def["profile"]
    runtime = args.max_runtime_sec or _profile_runtime(profile, 1800)
    profile_sha = args.profile_sha256 or sha256_or_missing(ROOT / profile)
    bitstream_sha = args.bitstream_sha256 or sha256_or_missing(ROOT / bitstream) if bitstream else args.bitstream_sha256
    hashes = active_hashes()
    shutdown_sha = args.shutdown_bitstream_sha256 or sha256_or_missing(resolve_root_path(args.shutdown_bitstream) or DEFAULT_SHUTDOWN_BITSTREAM)
    auth_path = resolve_root_path(args.authorization_file) or DEFAULT_AUTH_FILE
    auth_payload = validate_authorization(
        allow_hardware=args.allow_hardware,
        execute_hardware=args.execute_hardware,
        authorization_file=auth_path,
        board_id=args.board_id,
        bitstream=bitstream,
        bitstream_sha256=bitstream_sha,
        profile=profile,
        profile_sha256=profile_sha,
        active_pinmap_hash=args.active_pinmap_hash or hashes.get("pinmap", "MISSING"),
        active_xdc_hash=args.active_xdc_hash or hashes.get("active_xdc", "MISSING"),
        shutdown_bitstream=args.shutdown_bitstream,
        shutdown_bitstream_sha256=shutdown_sha,
        max_runtime_sec=runtime,
        shutdown_on_exit=args.shutdown_on_exit,
        lane_count=args.lane_count,
    )
    auth_summary = write_authorization_summary(auth_payload)
    package = write_authorized_run_package(
        auth_payload=auth_payload,
        stage=args.stage,
        board_id=args.board_id,
        authorization_file=auth_path,
        profile=profile,
        bitstream=bitstream,
        max_runtime_sec=runtime,
        lane_count=args.lane_count,
        shutdown_bitstream=args.shutdown_bitstream,
    )
    payload = {
        **auth_payload,
        **auth_summary,
        "AUTHORIZATION_TEMPLATE": rel(template),
        "P5_HARDWARE_STAGE_PLAN": stage_plan["P5_HARDWARE_STAGE_PLAN"],
        **package,
    }
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P5_HARDWARE_AUTHORIZATION: {payload['P5_HARDWARE_AUTHORIZATION']}")
        print(f"P5_AUTHORIZED_RUN_PACKAGE: {payload['P5_AUTHORIZED_RUN_PACKAGE']}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
    return 2 if args.execute_hardware and not auth_payload["AUTHORIZED"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
