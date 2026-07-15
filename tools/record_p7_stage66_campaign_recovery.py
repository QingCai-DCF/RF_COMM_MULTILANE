#!/usr/bin/env python3
"""Record one independent shutdown recovery into the Stage66 campaign ledger."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import p7_stage66_campaign as campaign
from p7_hardware_safety import ROOT, SHA256_RE, resolve_path, sha256_file


REQUIRED_FILES = {
    "hardware_authorization.json",
    "hash_manifest.csv",
    "hash_manifest.json",
    "program_tfdu_shutdown_safe.stderr.log",
    "program_tfdu_shutdown_safe.stdout.log",
    "program_tfdu_shutdown_safe.summary.txt",
}


def marker_map(text: str) -> tuple[dict[str, str], list[str]]:
    markers: dict[str, str] = {}
    duplicates: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in markers:
            duplicates.append(key)
        else:
            markers[key] = value
    return markers, duplicates


def validate_recovery(
    recovery_dir: Path, *, run_id: str, failure_ended_at_utc: str | None
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    root = (
        ROOT / "evidence" / "hardware" / "p7" / "authorized_sequence" / run_id
    ).resolve(strict=False)
    directory = recovery_dir.resolve(strict=False)
    try:
        directory.relative_to(root)
    except ValueError:
        errors.append(f"recovery directory must be under failed run root {root}")
    if not directory.is_dir() or directory.is_symlink():
        return {}, errors + [f"recovery directory is missing/not regular: {directory}"]
    if not directory.name.startswith("recovery_shutdown_after_failed_stage"):
        errors.append("recovery directory name is not the canonical independent-recovery form")
    observed = {path.name for path in directory.iterdir() if path.is_file()}
    if observed != REQUIRED_FILES:
        errors.append(
            f"independent recovery file set mismatch: missing={sorted(REQUIRED_FILES - observed)} "
            f"unknown={sorted(observed - REQUIRED_FILES)}"
        )
    summary_path = directory / "program_tfdu_shutdown_safe.summary.txt"
    summary_text = (
        summary_path.read_text(encoding="utf-8", errors="strict")
        if summary_path.is_file()
        else ""
    )
    markers, duplicates = marker_map(summary_text)
    if duplicates:
        errors.append(f"independent recovery summary contains duplicate markers: {duplicates}")
    expected_markers = {
        "HARDWARE_AUTHORIZATION_EXIT": "0",
        "ALLOW_HARDWARE": "1",
        "NO_HARDWARE_ACTIONS_EXECUTED": "0",
        "TFDU_SHUTDOWN_PROGRAMMED_SEEN": "1",
        "SHUTDOWN_EXIT": "0",
        "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS": "PASS",
    }
    for key, expected in expected_markers.items():
        if markers.get(key) != expected:
            errors.append(f"independent recovery marker mismatch: {key}")
    stdout_path = directory / "program_tfdu_shutdown_safe.stdout.log"
    stdout = (
        stdout_path.read_text(encoding="utf-8", errors="replace")
        if stdout_path.is_file()
        else ""
    )
    emitted = [
        line
        for line in stdout.splitlines()
        if line.strip().startswith("TFDU_SHUTDOWN_PROGRAMMED=")
    ]
    if len(emitted) != 1:
        errors.append("independent recovery must emit exactly one TFDU_SHUTDOWN_PROGRAMMED marker")
    auth_path = directory / "hardware_authorization.json"
    try:
        authorization = json.loads(auth_path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        authorization = {}
        errors.append(f"independent recovery authorization JSON is invalid: {exc}")
    if not isinstance(authorization, dict) or not (
        authorization.get("AUTHORIZED") is True
        and authorization.get("P4_AUTHORIZATION") == "AUTHORIZED"
        and authorization.get("missing") == []
    ):
        errors.append("independent recovery scoped authorization did not PASS")
    begin_line = next(
        (line for line in summary_text.splitlines() if line.startswith("PROGRAM_TFDU_SHUTDOWN_SAFE_BEGIN ")),
        "",
    )
    end_line = next(
        (line for line in summary_text.splitlines() if line.startswith("PROGRAM_TFDU_SHUTDOWN_SAFE_END ")),
        "",
    )
    begin_text = begin_line.partition(" ")[2]
    end_text = end_line.partition(" ")[2]
    try:
        begin = datetime.fromisoformat(begin_text)
        end = datetime.fromisoformat(end_text)
        if begin.tzinfo is None or end.tzinfo is None or end < begin:
            raise ValueError("invalid recovery interval")
        if failure_ended_at_utc:
            failure_end = datetime.fromisoformat(failure_ended_at_utc)
            if failure_end.tzinfo is None or begin.astimezone(timezone.utc) < failure_end.astimezone(
                timezone.utc
            ):
                errors.append("independent recovery began before the failed run ended")
    except ValueError as exc:
        errors.append(f"independent recovery UTC chronology is invalid: {exc}")
    files = [
        {
            "name": name,
            "path": str(directory / name),
            "sha256": sha256_file(directory / name),
            "bytes": (directory / name).stat().st_size,
        }
        for name in sorted(REQUIRED_FILES)
        if (directory / name).is_file()
    ]
    return {
        "directory": str(directory),
        "started_at": begin_text,
        "ended_at": end_text,
        "files": files,
        "shutdown_exit": 0,
        "status": "PASS",
        "recovery_changes_failed_stage_result": False,
    }, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and atomically record one independent Stage66 campaign shutdown recovery."
    )
    parser.add_argument("--policy", required=True)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--campaign-ledger", required=True)
    parser.add_argument("--campaign-ledger-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--recovery-dir", required=True)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: dict[str, Any] = {
        "schema": "rf-comm-p7-stage66-campaign-recovery-record-v1",
        "P7_STAGE66_CAMPAIGN_RECOVERY_RECORD": "BLOCKED",
        "hardware_actions_executed": False,
        "run_id": args.run_id,
        "record_requested": bool(args.record),
        "errors": [],
    }
    errors: list[str] = result["errors"]
    policy, policy_errors = campaign.validate_policy(
        resolve_path(args.policy), args.policy_sha256.lower()
    )
    errors.extend(policy_errors)
    ledger_path = resolve_path(args.campaign_ledger)
    if not SHA256_RE.fullmatch(args.campaign_ledger_sha256):
        errors.append("campaign ledger SHA256 is malformed")
    elif not ledger_path.is_file() or sha256_file(ledger_path) != args.campaign_ledger_sha256.lower():
        errors.append("campaign ledger SHA256 mismatch")
    ledger: dict[str, Any] | None = None
    if policy is not None:
        ledger, ledger_errors = campaign.validate_ledger(policy, ledger_path, allow_absent=False)
        # RECOVERY_REQUIRED is expected here; all other structural errors remain fatal.
        errors.extend(ledger_errors)
    attempt: dict[str, Any] | None = None
    if ledger is not None:
        attempts = ledger.get("hardware_attempts")
        if not isinstance(attempts, list) or not attempts or not isinstance(attempts[-1], dict):
            errors.append("campaign ledger has no terminal failed attempt to recover")
        else:
            attempt = attempts[-1]
            if attempt.get("run_id") != args.run_id:
                errors.append("recovery run ID does not match the terminal campaign attempt")
            if attempt.get("status") != "FAIL_RECOVERY_REQUIRED":
                errors.append("terminal campaign attempt is not awaiting independent recovery")
    recovery_record, recovery_errors = validate_recovery(
        resolve_path(args.recovery_dir),
        run_id=args.run_id,
        failure_ended_at_utc=str(attempt.get("ended_at_utc")) if attempt else None,
    )
    errors.extend(recovery_errors)
    lock_path = ledger_path.with_name("campaign_execution.lock")
    if lock_path.exists():
        errors.append("campaign execution lock exists and is never auto-recovered")
    if not errors and args.record and ledger is not None and attempt is not None:
        attempt["independent_shutdown_recovery"] = recovery_record
        attempt["status"] = "FAIL_RECOVERED"
        ledger["status"] = (
            "EXHAUSTED"
            if ledger["actual_hardware_attempt_count"] == campaign.MAX_HARDWARE_ATTEMPTS
            else "READY"
        )
        ledger["updated_at_utc"] = campaign.now_utc()
        campaign.atomic_write_json(ledger_path, ledger)
        result["campaign_ledger_sha256_after"] = sha256_file(ledger_path)
        result["P7_STAGE66_CAMPAIGN_RECOVERY_RECORD"] = "PASS_RECORDED"
    elif not errors:
        result["P7_STAGE66_CAMPAIGN_RECOVERY_RECORD"] = "DRY_VALIDATED"
    result["recovery"] = recovery_record
    if args.json_summary:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "P7_STAGE66_CAMPAIGN_RECOVERY_RECORD: "
            + result["P7_STAGE66_CAMPAIGN_RECOVERY_RECORD"]
        )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
