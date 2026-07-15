#!/usr/bin/env python3
"""Atomically retire one Stage66 campaign run ID before hardware launch."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any

import p7_stage66_campaign as campaign
from p7_hardware_safety import AUTH_ENV, ROOT, SHA256_RE, resolve_path, sha256_file


def git_head() -> tuple[str | None, str | None]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        return None, completed.stderr.strip() or "git rev-parse HEAD failed"
    return completed.stdout.strip().lower(), None


def validate_retirement_evidence(
    path: Path,
    expected_sha256: str,
    *,
    run_id: str,
    source_commit: str,
    requested_hardware_attempt_number: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    generated_root = (ROOT / "evidence" / "generated").resolve(strict=False)
    evidence = path.resolve(strict=False)
    try:
        evidence.relative_to(generated_root)
    except ValueError:
        errors.append("pre-hardware retirement evidence is outside evidence/generated")
    if not evidence.is_file() or evidence.is_symlink():
        return None, errors + ["pre-hardware retirement evidence is missing/not regular"]
    if not SHA256_RE.fullmatch(expected_sha256 or ""):
        errors.append("pre-hardware retirement evidence SHA256 is malformed")
    elif sha256_file(evidence) != expected_sha256.lower():
        errors.append("pre-hardware retirement evidence SHA256 mismatch")
    try:
        payload = json.loads(evidence.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, errors + [f"pre-hardware retirement evidence JSON is invalid: {exc}"]
    if not isinstance(payload, dict):
        return None, errors + ["pre-hardware retirement evidence root is not an object"]
    expected = {
        "status": "RETIRED_PRE_HARDWARE_DRY_VALIDATION_FAIL",
        "run_id": run_id,
        "run_id_retired": True,
        "resume_restart_copy_reuse_permitted": False,
        "source_commit": source_commit,
        "requested_campaign_hardware_attempt_number": requested_hardware_attempt_number,
        "actual_hardware_attempt_count_after": requested_hardware_attempt_number - 1,
        "diagnostic_hardware_attempt_consumed": False,
    }
    for key, value in expected.items():
        if payload.get(key) != value:
            errors.append(f"pre-hardware retirement evidence field mismatch: {key}")
    generator = payload.get("generator")
    boundary = payload.get("failure_boundary")
    if not isinstance(generator, dict) or generator.get("hardware_actions_executed") is not False:
        errors.append("pre-hardware retirement evidence does not prove zero hardware actions")
    if not isinstance(boundary, dict) or not (
        boundary.get("hardware_execution_entered") is False
        and boundary.get("stage_wrapper_process_started") is False
        and boundary.get("candidate_bitstream_programmed") is False
        and boundary.get("stationary_started") is False
    ):
        errors.append("pre-hardware retirement evidence boundary is incomplete")
    return payload, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and optionally record one fail-closed Stage66 campaign "
            "run-ID retirement without consuming hardware quota."
        )
    )
    parser.add_argument("--policy", required=True)
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--campaign-ledger", required=True)
    parser.add_argument("--campaign-ledger-sha256-before", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--requested-hardware-attempt-number", type=int, required=True)
    parser.add_argument("--retired-source-commit", required=True)
    parser.add_argument("--recorder-source-commit", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--evidence-sha256", required=True)
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result: dict[str, Any] = {
        "schema": "rf-comm-p7-stage66-campaign-prehardware-retirement-record-v1",
        "P7_STAGE66_CAMPAIGN_PREHARDWARE_RETIREMENT": "BLOCKED",
        "hardware_actions_executed": False,
        "diagnostic_hardware_attempt_consumed": False,
        "run_id": args.run_id,
        "requested_hardware_attempt_number": args.requested_hardware_attempt_number,
        "record_requested": bool(args.record),
        "errors": [],
    }
    errors: list[str] = result["errors"]
    if os.environ.get(AUTH_ENV):
        errors.append(f"{AUTH_ENV} must be unset for a pre-hardware retirement record")
    policy, policy_errors = campaign.validate_policy(
        resolve_path(args.policy), args.policy_sha256.lower()
    )
    errors.extend(policy_errors)
    ledger_path = resolve_path(args.campaign_ledger)
    before_sha = campaign.current_ledger_sha256(ledger_path)
    if args.campaign_ledger_sha256_before != before_sha:
        errors.append(
            "campaign ledger snapshot changed before retirement: "
            f"expected={args.campaign_ledger_sha256_before} actual={before_sha}"
        )
    ledger: dict[str, Any] | None = None
    if policy is not None:
        ledger, ledger_errors = campaign.validate_ledger(
            policy, ledger_path, allow_absent=True
        )
        errors.extend(ledger_errors)
    head, git_error = git_head()
    if git_error:
        errors.append(f"unable to establish recorder source commit: {git_error}")
    elif head != args.recorder_source_commit.lower():
        errors.append(
            "recorder source commit mismatch: "
            f"requested={args.recorder_source_commit.lower()} observed={head}"
        )
    if not campaign.COMMIT_RE.fullmatch(args.retired_source_commit.lower()):
        errors.append("retired source commit is malformed")
    evidence_path = resolve_path(args.evidence)
    _evidence, evidence_errors = validate_retirement_evidence(
        evidence_path,
        args.evidence_sha256.lower(),
        run_id=args.run_id,
        source_commit=args.retired_source_commit.lower(),
        requested_hardware_attempt_number=args.requested_hardware_attempt_number,
    )
    errors.extend(evidence_errors)
    lock_path = ledger_path.with_name("campaign_execution.lock")
    if lock_path.exists():
        errors.append("campaign execution lock exists and is never auto-recovered")
    candidate = (
        ledger
        if ledger is not None
        else campaign.new_ledger(policy, args.policy_sha256.lower())
        if policy is not None
        else None
    )
    if not errors and candidate is not None:
        try:
            campaign.retire_pre_hardware_run_id(
                candidate,
                run_id=args.run_id,
                requested_hardware_attempt_number=args.requested_hardware_attempt_number,
                source_commit=args.retired_source_commit.lower(),
                reason=args.reason,
                evidence_path=str(evidence_path.relative_to(ROOT)).replace("\\", "/"),
                evidence_sha256=args.evidence_sha256.lower(),
            )
        except RuntimeError as exc:
            errors.append(str(exc))
    if not errors and args.record and candidate is not None and policy is not None:
        lock = campaign.CampaignLock.acquire(
            ledger_path,
            {
                "operation": "RETIRE_PRE_HARDWARE_RUN_ID",
                "run_id": args.run_id,
                "requested_hardware_attempt_number": args.requested_hardware_attempt_number,
                "recorder_source_commit": args.recorder_source_commit.lower(),
            },
        )
        try:
            if campaign.current_ledger_sha256(ledger_path) != before_sha:
                raise RuntimeError("campaign ledger changed after retirement lock acquisition")
            campaign.atomic_write_json(ledger_path, candidate)
            _written, written_errors = campaign.validate_ledger(
                policy, ledger_path, allow_absent=False
            )
            if written_errors:
                raise RuntimeError(
                    "recorded campaign ledger failed validation: " + "; ".join(written_errors)
                )
            result["campaign_ledger_sha256_after"] = sha256_file(ledger_path)
            result["P7_STAGE66_CAMPAIGN_PREHARDWARE_RETIREMENT"] = "PASS_RECORDED"
        finally:
            lock.release()
    elif not errors:
        result["P7_STAGE66_CAMPAIGN_PREHARDWARE_RETIREMENT"] = "DRY_VALIDATED"
    result["campaign_ledger"] = {
        "path": str(ledger_path),
        "sha256_before": before_sha,
        "actual_hardware_attempt_count": (
            candidate.get("actual_hardware_attempt_count") if candidate is not None else None
        ),
        "retired_pre_hardware_run_id_count": (
            len(candidate.get("retired_pre_hardware_run_ids", []))
            if candidate is not None
            else None
        ),
    }
    if args.json_summary:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "P7_STAGE66_CAMPAIGN_PREHARDWARE_RETIREMENT: "
            + result["P7_STAGE66_CAMPAIGN_PREHARDWARE_RETIREMENT"]
        )
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
