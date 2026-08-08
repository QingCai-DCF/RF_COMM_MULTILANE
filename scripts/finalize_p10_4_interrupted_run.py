#!/usr/bin/env python3
"""Freeze a fail-closed, resumable P10.4 parent-run checkpoint.

This tool is offline.  It never connects to hardware.  It verifies every
completed stage directly from raw stage, shutdown, forensic, and runtime/rest
records, records the interrupted stage conservatively through the independently
verified emergency shutdown, consumes the interrupted authorization, and
freezes a SHA256 manifest for the parent run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_4_hardware as campaign


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT_RUN_ID = (
    "p10_4_20260808T102748Z_6ff17d33_94506af9_2b2b37d4"
)
INTERRUPTED_STAGE = "pl_reset_rotating_2"
COMPLETED_PREFIX = campaign.STAGES[: campaign.STAGES.index(INTERRUPTED_STAGE)]
EMERGENCY_LABEL = "interrupted_pl_reset_rotating_2_emergency"
PARENT_CHECKPOINT = ROOT / "evidence/generated/p10_4_interrupted_parent_checkpoint.json"
PARENT_CHECKPOINT_MD = ROOT / "evidence/generated/p10_4_interrupted_parent_checkpoint.md"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def metadata(path: Path) -> dict[str, Any]:
    return {
        "path": campaign.rel(path),
        "sha256": campaign.sha256(path),
        "bytes": path.stat().st_size,
    }


def parse_shutdown(path: Path) -> tuple[dict[str, str], list[str]]:
    errors: list[str] = []
    if not path.is_file():
        return {}, [f"shutdown result missing: {campaign.rel(path)}"]
    markers = campaign.parse_markers(path)
    required = {
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "TFDU_SHUTDOWN_PROGRAMMED": "1",
        "SHUTDOWN_EXIT": "0",
        "P10_DUAL_SHUTDOWN_RESULT": "PASS",
    }
    for name, expected in required.items():
        if markers.get(name) != expected:
            errors.append(
                f"{campaign.rel(path)} marker {name}={markers.get(name)!r}, "
                f"expected {expected!r}"
            )
    return markers, errors


def expected_plan_hash(stage: str, selected: dict[str, Any]) -> str:
    config = campaign.baseline_config() if campaign.STAGES.index(stage) <= \
        campaign.STAGES.index("tuning") else selected
    text = campaign.build_plans(config)[stage]
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def verify_parent_run(run_root: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    ledger_path = run_root / "runtime_rest/runtime_rest_ledger.json"
    try:
        ledger = load_json(ledger_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, [f"runtime ledger unreadable: {exc}"]
    entries = ledger.get("stages", [])
    if ledger.get("status") != "PENDING":
        errors.append("interrupted parent runtime ledger must be PENDING")
    if ledger.get("active_stage") != INTERRUPTED_STAGE:
        errors.append("runtime ledger active stage differs from interrupted stage")
    if not isinstance(entries, list) or len(entries) != len(COMPLETED_PREFIX):
        errors.append("runtime ledger completed-stage count mismatch")
        entries = []
    if [item.get("stage") for item in entries if isinstance(item, dict)] != \
            list(COMPLETED_PREFIX):
        errors.append("runtime ledger completed-stage order mismatch")
    for item in entries:
        if not isinstance(item, dict) or item.get("status") != "PASS" or \
                item.get("runtime_limit_status") != "PASS" or \
                item.get("cooldown_status") != "PASS" or \
                item.get("shutdown_verified") is not True:
            errors.append(f"runtime/rest entry is not PASS: {item.get('stage')}")
        if float(item.get("measured_runtime_seconds", 999999)) > 1800:
            errors.append(f"runtime entry exceeds 1800 seconds: {item.get('stage')}")
        if float(item.get("actual_cooldown_seconds", -1)) + 1e-6 < \
                float(item.get("required_cooldown_seconds", 999999)):
            errors.append(f"cooldown entry is short: {item.get('stage')}")

    tuning_summary_path = run_root / "stages/tuning/stage_summary.json"
    try:
        tuning = load_json(tuning_summary_path)
        selected = dict(tuning["semantics"]["selected"])
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"selected configuration unreadable: {exc}")
        selected = {}
    if selected not in campaign.candidate_configs():
        errors.append("selected configuration is not an allowed P10.4 candidate")

    records: list[dict[str, Any]] = []
    for index, stage in enumerate(COMPLETED_PREFIX):
        stage_dir = run_root / "stages" / stage
        summary_path = stage_dir / "stage_summary.json"
        plan_path = stage_dir / "immutable.plan"
        forensic_path = run_root / "forensics" / stage / "summary.json"
        before_path = run_root / "shutdown" / f"{stage}_before" / "attempt_1.result.txt"
        after_path = run_root / "shutdown" / f"{stage}_after" / "attempt_1.result.txt"
        try:
            summary = load_json(summary_path)
            if summary.get("stage") != stage or summary.get("status") != "PASS":
                errors.append(f"completed stage summary is not PASS: {stage}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"completed stage summary unreadable {stage}: {exc}")
            summary = {}
        try:
            forensic_summary = load_json(forensic_path)
            if forensic_summary.get("status") != "PASS":
                errors.append(f"forensic archive is not PASS: {stage}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"forensic archive unreadable {stage}: {exc}")
        if not plan_path.is_file() or campaign.sha256(plan_path) != \
                expected_plan_hash(stage, selected):
            errors.append(f"immutable plan hash mismatch: {stage}")
        _, before_errors = parse_shutdown(before_path)
        _, after_errors = parse_shutdown(after_path)
        errors.extend(before_errors)
        errors.extend(after_errors)
        runtime = entries[index] if index < len(entries) else {}
        records.append({
            "stage": stage,
            "status": summary.get("status"),
            "summary": metadata(summary_path) if summary_path.is_file() else None,
            "plan": metadata(plan_path) if plan_path.is_file() else None,
            "forensic_summary": metadata(forensic_path) if forensic_path.is_file() else None,
            "shutdown_before": metadata(before_path) if before_path.is_file() else None,
            "shutdown_after": metadata(after_path) if after_path.is_file() else None,
            "runtime_rest": runtime,
        })

    interrupted_plan = run_root / "stages" / INTERRUPTED_STAGE / "immutable.plan"
    interrupted_summary = run_root / "stages" / INTERRUPTED_STAGE / "stage_summary.json"
    before_result = (
        run_root / "shutdown" / f"{INTERRUPTED_STAGE}_before" /
        "attempt_1.result.txt"
    )
    emergency_result = (
        run_root / "shutdown" / EMERGENCY_LABEL / "attempt_1.result.txt"
    )
    _, before_errors = parse_shutdown(before_result)
    emergency_markers, emergency_errors = parse_shutdown(emergency_result)
    errors.extend(before_errors)
    errors.extend(emergency_errors)
    if interrupted_summary.exists():
        errors.append("interrupted stage unexpectedly has a completed stage summary")
    if not interrupted_plan.is_file() or campaign.sha256(interrupted_plan) != \
            expected_plan_hash(INTERRUPTED_STAGE, selected):
        errors.append("interrupted-stage immutable plan hash mismatch")

    start_utc = before_result.stat().st_mtime
    shutdown_utc = emergency_result.stat().st_mtime
    elapsed = max(0.0, shutdown_utc - start_utc)
    required_cooldown = math.ceil(elapsed * 0.5 * 1000.0) / 1000.0
    now = datetime.now(timezone.utc).timestamp()
    actual_cooldown = max(0.0, now - shutdown_utc)
    interruption_status = (
        "PASS" if elapsed <= 1800 and actual_cooldown + 1e-6 >= required_cooldown
        and not before_errors and not emergency_errors else "FAIL"
    )
    if interruption_status != "PASS":
        errors.append("interrupted-stage runtime/shutdown/cooldown closeout failed")
    stage_stdout = run_root / "stages" / INTERRUPTED_STAGE / "xsdb.stdout.log"
    stdout_text = stage_stdout.read_text(encoding="utf-8", errors="replace") \
        if stage_stdout.is_file() else ""
    interruption = {
        "stage": INTERRUPTED_STAGE,
        "status": interruption_status,
        "stage_result": "ABSENT_INTERRUPTED_REEXECUTION_REQUIRED",
        "conservative_modules": list(campaign.ALL_MODULES),
        "runtime_start_basis": "shutdown-before result file mtime (earlier than plan materialization)",
        "start_utc": datetime.fromtimestamp(start_utc, timezone.utc).isoformat(),
        "shutdown_verified_utc": datetime.fromtimestamp(
            shutdown_utc, timezone.utc
        ).isoformat(),
        "measured_runtime_seconds": round(elapsed, 6),
        "runtime_limit_seconds": 1800,
        "runtime_limit_status": "PASS" if elapsed <= 1800 else "FAIL",
        "required_cooldown_seconds": required_cooldown,
        "cooldown_completed_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "actual_cooldown_seconds": round(actual_cooldown, 6),
        "cooldown_status": (
            "PASS" if actual_cooldown + 1e-6 >= required_cooldown else "FAIL"
        ),
        "shutdown_before": metadata(before_result),
        "emergency_shutdown": metadata(emergency_result),
        "emergency_shutdown_markers": emergency_markers,
        "immutable_plan": metadata(interrupted_plan),
        "partial_stdout": metadata(stage_stdout) if stage_stdout.is_file() else None,
        "service_ready_reached": "P10_SERVICE_READY_" in stdout_text,
        "paired_launch_reached": "P10_PAIRED_LAUNCH=" in stdout_text,
        "no_tx_claim_from_marker_absence": False,
        "reexecution_required": True,
    }
    return {
        "ledger": ledger,
        "selected_config": selected,
        "completed_stage_records": records,
        "interruption": interruption,
    }, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-run-id", default=DEFAULT_PARENT_RUN_ID)
    args = parser.parse_args(argv)
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        print("P10_4_INTERRUPTION_CHECKPOINT=FAIL_ENVIRONMENT", file=sys.stderr)
        return 2
    run_root = campaign.HW_ROOT / args.parent_run_id
    auth_path = campaign.AUTH
    errors: list[str] = []
    try:
        authorization = load_json(auth_path)
        immutable_authorization = load_json(
            run_root / "authorization/immutable_authorization.json"
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"P10_4_INTERRUPTION_CHECKPOINT=FAIL:{exc}", file=sys.stderr)
        return 2
    if authorization != immutable_authorization:
        errors.append("current authorization differs from run-start immutable copy")
    if authorization.get("run_id") != args.parent_run_id or \
            authorization.get("consumed") is not False or \
            authorization.get("current_run_hardware_authorization") is not True:
        errors.append("parent authorization is not the active unconsumed run authorization")
    verified, verify_errors = verify_parent_run(run_root)
    errors.extend(verify_errors)
    if errors:
        print(json.dumps({"status": "FAIL", "errors": errors}, indent=2))
        return 1

    interruption = verified["interruption"]
    interrupted_result = {
        "schema_version": 1,
        "test_id": "P10_4-INTERRUPTED-RUN-CLOSEOUT",
        "status": "INTERRUPTED_FAIL_CLOSED_RESUMABLE",
        "scope": campaign.SCOPE,
        "run_id": args.parent_run_id,
        "goal_sha256": campaign.GOAL_SHA256,
        "completed_stage_count": len(COMPLETED_PREFIX),
        "completed_stages": list(COMPLETED_PREFIX),
        "interrupted_stage": INTERRUPTED_STAGE,
        "interruption": interruption,
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "current_run_hardware_authorization": False,
        "resume_permitted_only_with_new_immutable_authorization": True,
        "p10_4_acceptance_promoted": False,
        "errors": [],
        "generated_at_utc": campaign.utc_now(),
    }
    final_dir = run_root / "final"
    write_json(final_dir / "interrupted_orchestrator_result.json", interrupted_result)
    write_json(final_dir / "interruption_recovery.json", interruption)
    write_text(
        final_dir / "interruption_recovery.md",
        "# P10.4 interrupted-stage recovery\n\n"
        f"- Parent run: `{args.parent_run_id}`\n"
        f"- Completed stages: `{len(COMPLETED_PREFIX)}`\n"
        f"- Interrupted stage: `{INTERRUPTED_STAGE}`\n"
        f"- Conservative runtime: `{interruption['measured_runtime_seconds']}` s\n"
        f"- Required cooldown: `{interruption['required_cooldown_seconds']}` s\n"
        f"- Actual cooldown: `{interruption['actual_cooldown_seconds']}` s\n"
        "- Emergency shutdown fixed/rotating: `PASS` / `PASS`\n"
        "- Interrupted stage result: `ABSENT_INTERRUPTED_REEXECUTION_REQUIRED`\n",
    )
    manifest = campaign.evidence_manifest(run_root)
    manifest_errors = campaign.verify_evidence_manifest(run_root, manifest)
    if manifest_errors:
        print(json.dumps({"status": "FAIL", "errors": manifest_errors}, indent=2))
        return 1

    consumed = dict(authorization)
    consumed.update({
        "status": "CONSUMED_AFTER_P10_4_INTERRUPTED_FAIL_CLOSED_RESUMABLE",
        "current_run_hardware_authorization": False,
        "consumed": True,
        "consumed_at_utc": campaign.utc_now(),
        "result": campaign.rel(final_dir / "interrupted_orchestrator_result.json"),
        "evidence_manifest": campaign.rel(
            final_dir / "run_evidence_sha256_manifest.json"
        ),
    })
    write_json(auth_path, consumed)
    authorization_summary = {
        "schema_version": 1,
        "test_id": "P10_4-AUTHORIZATION",
        "status": consumed["status"],
        "run_id": args.parent_run_id,
        "authorization": campaign.rel(auth_path),
        "current_run_hardware_authorization": False,
        "consumed": True,
        "result": consumed["result"],
        "errors": [],
    }
    write_json(ROOT / "evidence/generated/p10_4_authorization.json", authorization_summary)
    write_text(
        ROOT / "evidence/generated/p10_4_authorization.md",
        "# P10.4 current-run authorization\n\n"
        f"- Status: `{consumed['status']}`\n"
        f"- Run ID: `{args.parent_run_id}`\n"
        "- Current-run hardware authorization: `false`\n"
        "- Hardware actions executed: `true`\n",
    )
    checkpoint = {
        "schema_version": 1,
        "test_id": "P10_4-INTERRUPTED-PARENT-CHECKPOINT",
        "status": "PASS",
        "parent_run_outcome": "INTERRUPTED_FAIL_CLOSED_RESUMABLE",
        "parent_run_id": args.parent_run_id,
        "goal_sha256": campaign.GOAL_SHA256,
        "source_commit": authorization["source_commit"],
        "artifacts": authorization["artifacts"],
        "board_binding": authorization["board_binding"],
        "module_binding": campaign.MODULE_BINDING,
        "selected_config": verified["selected_config"],
        "completed_stage_count": len(COMPLETED_PREFIX),
        "completed_stages": list(COMPLETED_PREFIX),
        "completed_stage_records": verified["completed_stage_records"],
        "interrupted_stage": INTERRUPTED_STAGE,
        "remaining_stages": list(campaign.STAGES[len(COMPLETED_PREFIX):]),
        "interruption": interruption,
        "parent_runtime_ledger_raw": metadata(
            run_root / "runtime_rest/runtime_rest_ledger.json"
        ),
        "parent_run_manifest": metadata(
            final_dir / "run_evidence_sha256_manifest.json"
        ),
        "parent_manifest_file_count": manifest["file_count"],
        "parent_manifest_verified": True,
        "immutable_parent_authorization": metadata(
            run_root / "authorization/immutable_authorization.json"
        ),
        "consumed_parent_authorization": metadata(auth_path),
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "cooldown_status": interruption["cooldown_status"],
        "resume_requires_new_current_run_authorization": True,
        "network_used": False,
        "hardware_moved": False,
        "wiring_changed": False,
        "module_replaced_during_run": False,
        "external_instrumentation_used": False,
        "p10_4_acceptance_promoted": False,
        "errors": [],
        "generated_at_utc": campaign.utc_now(),
    }
    write_json(PARENT_CHECKPOINT, checkpoint)
    write_text(
        PARENT_CHECKPOINT_MD,
        "# P10.4 interrupted parent checkpoint\n\n"
        f"- Status: `PASS`\n- Parent run: `{args.parent_run_id}`\n"
        f"- Completed stages: `{len(COMPLETED_PREFIX)}/{len(campaign.STAGES)}`\n"
        f"- Interrupted stage: `{INTERRUPTED_STAGE}`\n"
        "- Emergency dual shutdown: `PASS`\n"
        f"- Cooldown: `{interruption['cooldown_status']}`\n"
        "- Resume: requires a new immutable current-run authorization\n",
    )
    print("P10_4_INTERRUPTION_CHECKPOINT=PASS")
    print(f"P10_4_PARENT_RUN_ID={args.parent_run_id}")
    print(f"COMPLETED_STAGES={len(COMPLETED_PREFIX)}")
    print("SHUTDOWN_FIXED=PASS")
    print("SHUTDOWN_ROTATING=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
