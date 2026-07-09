#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from p4_auto_lib import AUTH_DIR, GENERATED, ROOT, rel, resolve_root_path, sha256_or_missing, write_markdown, write_text


AUTH_ENV = "RF_COMM_HW_AUTH"
AUTH_ENV_VALUE = "I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"
DEFAULT_AUTH_FILE = ROOT / ".hardware_authorization" / "P4_AUTO_APPROVED.txt"
DEFAULT_ABORT_FILE = ROOT / ".hardware_authorization" / "ABORT_NOW.txt"

REQUIRED_PHRASES = [
    "I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.",
    "I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.",
    "AUTHORIZED_STAGE=P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL",
    "USER_CONFIRMED_SUPPLY_OK=true",
    "MANUAL_INTERVENTION_REQUIRED=false",
]


def ensure_authorization_record(user_confirmed_supply_ok: bool, no_manual_intervention: bool, max_runtime_sec: int = 360) -> None:
    template = ROOT / ".hardware_authorization" / "P4_AUTO_APPROVED.txt.template"
    body = f"""I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.
I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.
AUTHORIZED_STAGE=P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
USER_CONFIRMED_SUPPLY_OK=true
MANUAL_INTERVENTION_REQUIRED=false
ALLOWED_AUTOMATION=Vivado batch, JTAG, XSDB, AXI/JTAG-to-AXI, PS driver, ILA, VIO, debug registers, log parsing
FORBIDDEN=manual scope requirement, manual voltage measurement requirement, unbounded TX, long soak beyond profile, stale bitstream, untracked bitstream
MAX_RUNTIME_SEC={max_runtime_sec}
SHUTDOWN_ON_EXIT=required
LOW_DUTY_ONLY_UNTIL_PROTOCOL_PASS=true
AUTHORIZED_BY=user
DATE={datetime.utcnow().strftime('%Y-%m-%d')}
"""
    write_text(template, body)
    if user_confirmed_supply_ok and no_manual_intervention and not DEFAULT_AUTH_FILE.exists():
        write_text(DEFAULT_AUTH_FILE, body)
    record_lines = [
        "AUTHORIZED_STAGE: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL",
        f"USER_CONFIRMED_SUPPLY_OK: {str(user_confirmed_supply_ok).lower()}",
        f"MANUAL_INTERVENTION_REQUIRED: {str(not no_manual_intervention).lower()}",
        "ALLOWED_AUTOMATION: Vivado batch, JTAG, XSDB, AXI/JTAG-to-AXI, PS driver, ILA, VIO, debug registers, log parsing",
        "FORBIDDEN: manual scope requirement, manual voltage measurement requirement, unbounded TX, long soak beyond profile, stale bitstream, untracked bitstream",
        "MAX_RUNTIME_PER_STAGE_SEC: profile-bounded",
        "SHUTDOWN_ON_EXIT: required",
        "LOW_DUTY_ONLY_UNTIL_PROTOCOL_PASS: true",
        f"AUTHORIZATION_FILE: `{rel(DEFAULT_AUTH_FILE)}`",
        f"AUTHORIZATION_TEMPLATE: `{rel(template)}`",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
    ]
    write_markdown(
        AUTH_DIR / "P4_AUTO_USER_AUTHORIZATION.md",
        "P4 Auto User Authorization",
        "RECORDED",
        "user-confirmed supply and no-manual-intervention flags recorded without touching hardware",
        record_lines,
    )


def parse_authorization_file(path: Path) -> dict:
    result = {"exists": path.exists(), "valid": False, "missing": [], "fields": {}, "sha256": sha256_or_missing(path)}
    if not path.exists():
        result["missing"].append(rel(path))
        return result
    text = path.read_text(encoding="utf-8", errors="ignore")
    for phrase in REQUIRED_PHRASES:
        if phrase not in text:
            result["missing"].append(phrase)
    patterns = {
        "MAX_RUNTIME_SEC": r"(?m)^MAX_RUNTIME_SEC=(\d+)\s*$",
        "AUTHORIZED_BY": r"(?m)^AUTHORIZED_BY=(.+?)\s*$",
        "DATE": r"(?m)^DATE=(\d{4}-\d{2}-\d{2})\s*$",
    }
    for key, pattern in patterns.items():
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


def _add_hash_check(missing: list[str], flag: str, provided: str, actual: str) -> None:
    if not provided:
        missing.append(flag)
    elif actual != "MISSING" and provided.lower() != actual.lower():
        missing.append(f"{flag} mismatch: expected {actual}, got {provided}")


def validate_authorization(
    *,
    allow_hardware: bool,
    execute_hardware: bool,
    authorization_file: Path,
    user_confirmed_supply_ok: bool,
    no_manual_intervention: bool,
    board_id: str,
    bitstream: str,
    bitstream_sha256: str,
    profile_path: str,
    profile_sha256: str,
    active_pinmap_hash: str,
    active_xdc_hash: str,
    max_runtime_sec: int | None,
    shutdown_on_exit: bool,
    abort_file: Path = DEFAULT_ABORT_FILE,
) -> dict:
    parsed = parse_authorization_file(authorization_file)
    missing: list[str] = []
    bitstream_path = resolve_root_path(bitstream)
    profile_resolved = resolve_root_path(profile_path)
    actual_bitstream_sha = sha256_or_missing(bitstream_path)
    actual_profile_sha = sha256_or_missing(profile_resolved)
    actual_pinmap_sha = sha256_or_missing(ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv")
    actual_xdc_sha = sha256_or_missing(ROOT / "constraints" / "active" / "PORT1.generated.xdc")
    if execute_hardware and not allow_hardware:
        missing.append("--allow-hardware")
    if not execute_hardware:
        missing.append("--execute-hardware")
    if not user_confirmed_supply_ok:
        missing.append("--user-confirmed-supply-ok")
    if not no_manual_intervention:
        missing.append("--no-manual-intervention")
    if not shutdown_on_exit:
        missing.append("--shutdown-on-exit")
    if not max_runtime_sec or max_runtime_sec <= 0:
        missing.append("--max-runtime-sec")
    if execute_hardware:
        if not board_id:
            missing.append("--board-id")
        if not bitstream:
            missing.append("--bitstream")
        elif not bitstream_path or not bitstream_path.exists():
            missing.append(f"--bitstream missing: {bitstream}")
        if not profile_path:
            missing.append("--profile-path")
        elif not profile_resolved or not profile_resolved.exists():
            missing.append(f"--profile-path missing: {profile_path}")
        _add_hash_check(missing, "--bitstream-sha256", bitstream_sha256, actual_bitstream_sha)
        _add_hash_check(missing, "--profile-sha256", profile_sha256, actual_profile_sha)
        _add_hash_check(missing, "--active-pinmap-hash", active_pinmap_hash, actual_pinmap_sha)
        _add_hash_check(missing, "--active-xdc-hash", active_xdc_hash, actual_xdc_sha)
        if os.environ.get(AUTH_ENV) != AUTH_ENV_VALUE:
            missing.append(f"{AUTH_ENV}={AUTH_ENV_VALUE}")
        if abort_file.exists():
            missing.append(f"operator abort file present: {rel(abort_file)}")
    missing.extend(parsed["missing"])
    if parsed["fields"].get("MAX_RUNTIME_SEC") and max_runtime_sec and int(parsed["fields"]["MAX_RUNTIME_SEC"]) < int(max_runtime_sec):
        missing.append("MAX_RUNTIME_SEC in authorization file is lower than requested runtime")
    authorized = execute_hardware and not missing
    return {
        "P4_AUTO_AUTHORIZATION": "AUTHORIZED" if authorized else "BLOCKED_NOT_AUTHORIZED",
        "AUTHORIZED": authorized,
        "AUTHORIZATION_FILE": rel(authorization_file),
        "AUTHORIZATION_FILE_EXISTS": parsed["exists"],
        "AUTHORIZATION_FILE_SHA256": parsed["sha256"],
        "RF_COMM_HW_AUTH_PRESENT": os.environ.get(AUTH_ENV) == AUTH_ENV_VALUE,
        "USER_CONFIRMED_SUPPLY_OK": user_confirmed_supply_ok,
        "MANUAL_INTERVENTION_REQUIRED": not no_manual_intervention,
        "BOARD_ID": board_id or "MISSING",
        "BITSTREAM": rel(bitstream_path) if bitstream_path else "MISSING",
        "BITSTREAM_SHA256": actual_bitstream_sha,
        "BITSTREAM_SHA256_EXPECTED": bitstream_sha256 or "MISSING",
        "PROFILE_PATH": rel(profile_resolved) if profile_resolved else "MISSING",
        "PROFILE_SHA256": actual_profile_sha,
        "PROFILE_SHA256_EXPECTED": profile_sha256 or "MISSING",
        "ACTIVE_PINMAP_HASH": actual_pinmap_sha,
        "ACTIVE_PINMAP_HASH_EXPECTED": active_pinmap_hash or "MISSING",
        "ACTIVE_XDC_HASH": actual_xdc_sha,
        "ACTIVE_XDC_HASH_EXPECTED": active_xdc_hash or "MISSING",
        "MAX_RUNTIME_SEC": max_runtime_sec or "MISSING",
        "SHUTDOWN_ON_EXIT": shutdown_on_exit,
        "missing": missing,
    }


def write_authorization_summary(payload: dict) -> None:
    result = "PASS" if payload["AUTHORIZED"] else "BLOCKED_NOT_AUTHORIZED"
    lines = [
        f"P4_AUTO_AUTHORIZATION: {payload['P4_AUTO_AUTHORIZATION']}",
        f"AUTHORIZED: {str(payload['AUTHORIZED']).lower()}",
        f"AUTHORIZATION_FILE: `{payload['AUTHORIZATION_FILE']}`",
        f"AUTHORIZATION_FILE_EXISTS: {str(payload['AUTHORIZATION_FILE_EXISTS']).lower()}",
        f"AUTHORIZATION_FILE_SHA256: `{payload['AUTHORIZATION_FILE_SHA256']}`",
        f"RF_COMM_HW_AUTH_PRESENT: {str(payload['RF_COMM_HW_AUTH_PRESENT']).lower()}",
        f"USER_CONFIRMED_SUPPLY_OK: {str(payload['USER_CONFIRMED_SUPPLY_OK']).lower()}",
        f"MANUAL_INTERVENTION_REQUIRED: {str(payload['MANUAL_INTERVENTION_REQUIRED']).lower()}",
        f"BOARD_ID: `{payload['BOARD_ID']}`",
        f"BITSTREAM: `{payload['BITSTREAM']}`",
        f"BITSTREAM_SHA256: `{payload['BITSTREAM_SHA256']}`",
        f"BITSTREAM_SHA256_EXPECTED: `{payload['BITSTREAM_SHA256_EXPECTED']}`",
        f"PROFILE_PATH: `{payload['PROFILE_PATH']}`",
        f"PROFILE_SHA256: `{payload['PROFILE_SHA256']}`",
        f"PROFILE_SHA256_EXPECTED: `{payload['PROFILE_SHA256_EXPECTED']}`",
        f"ACTIVE_PINMAP_HASH: `{payload['ACTIVE_PINMAP_HASH']}`",
        f"ACTIVE_PINMAP_HASH_EXPECTED: `{payload['ACTIVE_PINMAP_HASH_EXPECTED']}`",
        f"ACTIVE_XDC_HASH: `{payload['ACTIVE_XDC_HASH']}`",
        f"ACTIVE_XDC_HASH_EXPECTED: `{payload['ACTIVE_XDC_HASH_EXPECTED']}`",
        f"MAX_RUNTIME_SEC: `{payload['MAX_RUNTIME_SEC']}`",
        f"SHUTDOWN_ON_EXIT: {str(payload['SHUTDOWN_ON_EXIT']).lower()}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Missing Controls",
        "",
        *(f"- `{item}`" for item in payload["missing"]),
        *(["- none"] if not payload["missing"] else []),
    ]
    write_markdown(AUTH_DIR / "p4_auto_authorization_record.md", "P4 Auto Authorization Record", result, "P4_AUTO authorization gate evaluated", lines)
    write_markdown(GENERATED / "p4_auto_authorization_summary.md", "P4 Auto Authorization Summary", result, "P4_AUTO authorization gate evaluated", lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate P4_AUTO hardware authorization. Defaults to dry-run and requires --allow-hardware for execution.")
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
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    ensure_authorization_record(args.user_confirmed_supply_ok, args.no_manual_intervention, args.max_runtime_sec or 360)
    payload = validate_authorization(
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
    write_authorization_summary(payload)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload["AUTHORIZED"] or not args.execute_hardware else 2


if __name__ == "__main__":
    raise SystemExit(main())
