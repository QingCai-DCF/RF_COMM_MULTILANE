#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path

from p4_hw_evidence import GENERATED, P4_DIR, ROOT, rel, sha256_or_missing, write_markdown, write_text


AUTH_ENV = "RF_COMM_HW_AUTH"
AUTH_ENV_VALUE = "I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW"
DEFAULT_AUTH_FILE = ROOT / ".hardware_authorization" / "P4_APPROVED.txt"
DEFAULT_ABORT_FILE = ROOT / ".hardware_authorization" / "ABORT_NOW.txt"

REQUIRED_PHRASES = [
    "I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.",
    "I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.",
]


def parse_authorization_file(path: Path) -> dict:
    result = {
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
    for phrase in REQUIRED_PHRASES:
        if phrase not in text:
            result["missing"].append(phrase)
    field_patterns = {
        "MAX_RUNTIME_SEC": r"(?m)^MAX_RUNTIME_SEC=(\d+)\s*$",
        "AUTHORIZED_BY": r"(?m)^AUTHORIZED_BY=(.+?)\s*$",
        "DATE": r"(?m)^DATE=(\d{4}-\d{2}-\d{2})\s*$",
    }
    for key, pattern in field_patterns.items():
        match = re.search(pattern, text)
        if not match:
            result["missing"].append(key)
            continue
        result["fields"][key] = match.group(1).strip()
    if "MAX_RUNTIME_SEC" in result["fields"]:
        runtime = int(result["fields"]["MAX_RUNTIME_SEC"])
        if runtime <= 0:
            result["missing"].append("MAX_RUNTIME_SEC must be positive")
    if "AUTHORIZED_BY" in result["fields"] and not result["fields"]["AUTHORIZED_BY"]:
        result["missing"].append("AUTHORIZED_BY must be non-empty")
    if "DATE" in result["fields"]:
        try:
            datetime.strptime(result["fields"]["DATE"], "%Y-%m-%d")
        except ValueError:
            result["missing"].append("DATE must be YYYY-MM-DD")
    result["valid"] = not result["missing"]
    return result


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def add_missing_hash_check(
    missing: list[str],
    *,
    name: str,
    provided: str,
    actual: str,
) -> None:
    if not provided:
        missing.append(f"--{name}")
        return
    if actual != "MISSING" and provided.lower() != actual.lower():
        missing.append(f"--{name} mismatch: expected {actual}, got {provided}")


def validate_authorization(
    *,
    execute_hardware: bool,
    require_user_hw_authorization: bool,
    authorization_file: Path,
    profile: str,
    max_runtime_sec: int | None,
    shutdown_on_exit: bool,
    board_id: str = "",
    bitstream: str = "",
    bitstream_sha256: str = "",
    profile_sha256: str = "",
    active_pinmap_hash: str = "",
    active_xdc_hash: str = "",
    abort_file: Path = DEFAULT_ABORT_FILE,
    require_env: bool = True,
) -> dict:
    parsed = parse_authorization_file(authorization_file)
    missing: list[str] = []
    if not execute_hardware:
        missing.append("--execute-hardware")
    if not require_user_hw_authorization:
        missing.append("--require-user-hw-authorization")
    profile_path = resolve_project_path(profile) if profile else None
    bitstream_path = resolve_project_path(bitstream) if bitstream else None
    active_pinmap = ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv"
    active_xdc = ROOT / "constraints" / "active" / "PORT1.generated.xdc"
    actual_profile_sha256 = sha256_or_missing(profile_path) if profile_path else "MISSING"
    actual_bitstream_sha256 = sha256_or_missing(bitstream_path) if bitstream_path else "MISSING"
    actual_pinmap_sha256 = sha256_or_missing(active_pinmap)
    actual_xdc_sha256 = sha256_or_missing(active_xdc)
    if not profile:
        missing.append("--profile")
    elif not profile_path or not profile_path.exists():
        missing.append(f"--profile path missing: {profile}")
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
            missing.append(f"--bitstream path missing: {bitstream}")
        add_missing_hash_check(missing, name="bitstream-sha256", provided=bitstream_sha256, actual=actual_bitstream_sha256)
        add_missing_hash_check(missing, name="active-pinmap-hash", provided=active_pinmap_hash, actual=actual_pinmap_sha256)
        add_missing_hash_check(missing, name="active-xdc-hash", provided=active_xdc_hash, actual=actual_xdc_sha256)
        if profile_sha256 and actual_profile_sha256 != "MISSING" and profile_sha256.lower() != actual_profile_sha256.lower():
            missing.append(f"--profile-sha256 mismatch: expected {actual_profile_sha256}, got {profile_sha256}")
        if abort_file.exists():
            missing.append(f"operator abort file present: {rel(abort_file)}")
    if require_env and os.environ.get(AUTH_ENV) != AUTH_ENV_VALUE:
        missing.append(f"{AUTH_ENV}={AUTH_ENV_VALUE}")
    missing.extend(parsed["missing"])
    auth_runtime = parsed["fields"].get("MAX_RUNTIME_SEC")
    if auth_runtime and max_runtime_sec and int(auth_runtime) < int(max_runtime_sec):
        missing.append("MAX_RUNTIME_SEC in authorization file is lower than requested runtime")
    authorized = not missing
    return {
        "AUTHORIZED": authorized,
        "P4_AUTHORIZATION": "AUTHORIZED" if authorized else "BLOCKED_NOT_AUTHORIZED",
        "AUTHORIZATION_FILE": rel(authorization_file),
        "AUTHORIZATION_FILE_EXISTS": parsed["exists"],
        "AUTHORIZATION_FILE_SHA256": parsed["sha256"],
        "AUTHORIZATION_FIELDS": parsed["fields"],
        "RF_COMM_HW_AUTH_PRESENT": os.environ.get(AUTH_ENV) == AUTH_ENV_VALUE,
        "BOARD_ID": board_id or "MISSING",
        "PROFILE": rel(profile_path) if profile_path else "MISSING",
        "PROFILE_SHA256": actual_profile_sha256,
        "PROFILE_SHA256_EXPECTED": profile_sha256 or "NOT_PROVIDED",
        "BITSTREAM": rel(bitstream_path) if bitstream_path else "MISSING",
        "BITSTREAM_SHA256": actual_bitstream_sha256,
        "BITSTREAM_SHA256_EXPECTED": bitstream_sha256 or "MISSING",
        "ACTIVE_PINMAP_HASH": actual_pinmap_sha256,
        "ACTIVE_PINMAP_HASH_EXPECTED": active_pinmap_hash or "MISSING",
        "ACTIVE_XDC_HASH": actual_xdc_sha256,
        "ACTIVE_XDC_HASH_EXPECTED": active_xdc_hash or "MISSING",
        "ABORT_FILE": rel(abort_file),
        "ABORT_FILE_PRESENT": abort_file.exists(),
        "missing": missing,
    }


def write_authorization_artifacts(payload: dict) -> None:
    status = "PASS" if payload["AUTHORIZED"] else "BLOCKED_NOT_AUTHORIZED"
    reason = "P4 hardware authorization is complete" if payload["AUTHORIZED"] else "no valid P4 hardware authorization was provided"
    lines = [
        f"P4_AUTHORIZATION: {payload['P4_AUTHORIZATION']}",
        f"AUTHORIZED: {str(payload['AUTHORIZED']).lower()}",
        f"AUTHORIZATION_FILE: `{payload['AUTHORIZATION_FILE']}`",
        f"AUTHORIZATION_FILE_EXISTS: {str(payload['AUTHORIZATION_FILE_EXISTS']).lower()}",
        f"AUTHORIZATION_FILE_SHA256: `{payload['AUTHORIZATION_FILE_SHA256']}`",
        f"RF_COMM_HW_AUTH_PRESENT: {str(payload['RF_COMM_HW_AUTH_PRESENT']).lower()}",
        f"BOARD_ID: `{payload['BOARD_ID']}`",
        f"PROFILE: `{payload['PROFILE']}`",
        f"PROFILE_SHA256: `{payload['PROFILE_SHA256']}`",
        f"BITSTREAM: `{payload['BITSTREAM']}`",
        f"BITSTREAM_SHA256: `{payload['BITSTREAM_SHA256']}`",
        f"BITSTREAM_SHA256_EXPECTED: `{payload['BITSTREAM_SHA256_EXPECTED']}`",
        f"ACTIVE_PINMAP_HASH: `{payload['ACTIVE_PINMAP_HASH']}`",
        f"ACTIVE_PINMAP_HASH_EXPECTED: `{payload['ACTIVE_PINMAP_HASH_EXPECTED']}`",
        f"ACTIVE_XDC_HASH: `{payload['ACTIVE_XDC_HASH']}`",
        f"ACTIVE_XDC_HASH_EXPECTED: `{payload['ACTIVE_XDC_HASH_EXPECTED']}`",
        f"ABORT_FILE_PRESENT: {str(payload['ABORT_FILE_PRESENT']).lower()}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Missing Controls",
        "",
        *(f"- `{item}`" for item in payload["missing"]),
        *(["- none"] if not payload["missing"] else []),
        "",
        "## Required Authorization File Content",
        "",
        "```text",
        "I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.",
        "I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.",
        "MAX_RUNTIME_SEC=<number>",
        "AUTHORIZED_BY=<user>",
        "DATE=<YYYY-MM-DD>",
        "```",
    ]
    write_markdown(P4_DIR / "p4_authorization_record.md", "P4 Authorization Record", status, reason, lines)
    write_markdown(GENERATED / "p4_authorization_gate_summary.md", "P4 Authorization Gate Summary", status, reason, lines)


def ensure_authorization_template() -> None:
    template = ROOT / ".hardware_authorization" / "P4_APPROVED.txt.template"
    write_text(
        template,
        """I AUTHORIZE RF_COMM_MULTILANE P4 HARDWARE ACCEPTANCE ON CONNECTED HARDWARE.
I UNDERSTAND THIS MAY DRIVE TFDU6102 TXD AFTER SAFE-IDLE CHECKS PASS.
MAX_RUNTIME_SEC=<number>
AUTHORIZED_BY=<user>
DATE=<YYYY-MM-DD>
""",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate P4 hardware authorization without touching hardware.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--require-user-hw-authorization", action="store_true")
    parser.add_argument("--authorization-file", default=str(DEFAULT_AUTH_FILE))
    parser.add_argument("--profile", default="")
    parser.add_argument("--board-id", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--profile-sha256", default="")
    parser.add_argument("--active-pinmap-hash", default="")
    parser.add_argument("--active-xdc-hash", default="")
    parser.add_argument("--abort-file", default=str(DEFAULT_ABORT_FILE.relative_to(ROOT)))
    parser.add_argument("--max-runtime-sec", type=int)
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--no-write-artifacts", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ensure_authorization_template()
    payload = validate_authorization(
        execute_hardware=args.execute_hardware,
        require_user_hw_authorization=args.require_user_hw_authorization,
        authorization_file=Path(args.authorization_file),
        profile=args.profile,
        max_runtime_sec=args.max_runtime_sec,
        shutdown_on_exit=args.shutdown_on_exit,
        board_id=args.board_id,
        bitstream=args.bitstream,
        bitstream_sha256=args.bitstream_sha256,
        profile_sha256=args.profile_sha256,
        active_pinmap_hash=args.active_pinmap_hash,
        active_xdc_hash=args.active_xdc_hash,
        abort_file=resolve_project_path(args.abort_file),
    )
    if not args.no_write_artifacts:
        write_authorization_artifacts(payload)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    if args.execute_hardware and not payload["AUTHORIZED"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
