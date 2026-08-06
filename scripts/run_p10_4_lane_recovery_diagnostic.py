#!/usr/bin/env python3
"""Run one immutable P10.4 lane-degradation/recovery diagnostic safely.

This is deliberately separate from the full P10.4 orchestrator.  It reuses the
exact authorized lane-recovery plan and frozen artifacts, produces a unique
run root, consumes its own current-run authorization, and never promotes the
result to a full-campaign PASS.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import run_p10_4_hardware as campaign


ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "config/p10_4_lane_recovery_diagnostic_current_run_authorization.json"
GENERATED = ROOT / "evidence/generated/p10_4_lane_recovery_diagnostic"
STAGE = "lane_recovery"
SELECTED_CONFIG_NAME = "buffers2_batch16"


def selected_config() -> dict[str, Any]:
    matches = [
        item for item in campaign.candidate_configs()
        if item.get("name") == SELECTED_CONFIG_NAME
    ]
    if len(matches) != 1:
        raise ValueError("frozen diagnostic runtime configuration is missing")
    return dict(matches[0])


def validate_diagnostic_authorization(
    path: Path, run_id: str
) -> tuple[dict[str, Any], dict[str, Path], list[str], str]:
    authorization, artifacts, errors = campaign.validate_authorization(path, run_id)
    selected = selected_config()
    plan = campaign.build_plans(selected)[STAGE]
    expected = authorization.get("allowed_plan_sha256", {}).get(
        SELECTED_CONFIG_NAME, {}
    ).get(STAGE)
    actual = hashlib.sha256(plan.encode("ascii")).hexdigest()
    if expected != actual:
        errors.append("lane-recovery diagnostic plan is not exactly authorized")
    if STAGE not in authorization.get("allowed_stages", []):
        errors.append("lane-recovery diagnostic stage is not authorized")
    return authorization, artifacts, errors, plan


def publish_terminal_evidence(run_root: Path, summary: dict[str, Any]) -> list[str]:
    result = run_root / "final/lane_recovery_diagnostic_result.json"
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    summary["evidence_manifest"] = campaign.rel(manifest_path)
    summary["evidence_manifest_verified"] = True
    campaign.write_json(result, summary)
    manifest = campaign.evidence_manifest(run_root)
    errors = campaign.verify_evidence_manifest(run_root, manifest)
    if errors:
        summary["evidence_manifest_verified"] = False
        summary["status"] = "FAIL_CLOSED"
        summary["errors"].extend(errors)
        campaign.write_json(result, summary)
        # The failure annotation changed the result bytes; freeze and verify
        # those exact bytes before returning fail-closed.
        manifest = campaign.evidence_manifest(run_root)
        followup_errors = campaign.verify_evidence_manifest(run_root, manifest)
        for item in followup_errors:
            if item not in errors:
                errors.append(item)
    campaign.write_pair(
        GENERATED, summary, "P10.4 lane-recovery diagnostic"
    )
    return errors


def consume_authorization(
    path: Path, authorization: dict[str, Any], run_root: Path,
    status: str, errors: list[str]
) -> None:
    consumed = dict(authorization)
    consumed.update({
        "status": f"CONSUMED_AFTER_P10_4_LANE_RECOVERY_DIAGNOSTIC_{status}",
        "current_run_hardware_authorization": False,
        "consumed": True,
        "consumed_at_utc": campaign.utc_now(),
        "result": campaign.rel(
            run_root / "final/lane_recovery_diagnostic_result.json"
        ),
        "diagnostic_stage": STAGE,
        "diagnostic_errors": errors,
    })
    campaign.write_json(path, consumed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    auth_path = args.authorization.resolve()
    authorization, artifacts, errors, plan = validate_diagnostic_authorization(
        auth_path, args.run_id
    )
    if args.validate_only:
        print(json.dumps({
            "status": "PASS" if not errors else "FAIL",
            "stage": STAGE,
            "selected_config": SELECTED_CONFIG_NAME,
            "errors": errors,
        }, indent=2))
        return 0 if not errors else 3
    if not args.execute_hardware:
        errors.append("--execute-hardware is required")
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "true":
        errors.append(
            "NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required"
        )
    run_root = campaign.HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run-id evidence directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2), file=sys.stderr)
        return 3

    env = {
        **os.environ,
        "NO_HARDWARE": "0",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
        "RF_COMM_P10_HW_AUTH": "P10_4_IMMUTABLE_AUTHORIZED",
    }
    ps7 = campaign.initialize_run(run_root, auth_path, artifacts)
    server_proc = None
    stage_result: dict[str, Any] | None = None
    shutdowns: list[dict[str, Any]] = []
    forensics: list[dict[str, Any]] = []
    run_errors: list[str] = []
    hardware_actions = False
    archived = True
    try:
        server_proc, server = campaign.start_hw_server(run_root / "raw_logs")
        hardware_actions = True
        campaign.write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server start failed"))

        initial = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, "initial", env
        )
        shutdowns.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")

        before = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, f"{STAGE}_before", env
        )
        shutdowns.append(before)
        if before.get("status") != "PASS":
            raise RuntimeError("lane-recovery shutdown-before unconfirmed")

        archived = False
        process, stage_dir = campaign.invoke_stage(
            STAGE, plan, run_root, auth_path, artifacts, ps7, env
        )
        process_failed = bool(
            process.get("returncode") != 0 or process.get("timed_out")
        )
        archive = campaign.capture_and_archive(
            STAGE, run_root, auth_path, env, force_abort=process_failed
        )
        forensics.append(archive)
        archived = archive.get("status") == "PASS"
        if not archived:
            raise RuntimeError("lane-recovery forensic archive failed")

        after = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, f"{STAGE}_after", env
        )
        shutdowns.append(after)
        stage_result = campaign.evaluate_stage(STAGE, stage_dir, process, archive, plan)
        stage_result["shutdown_before_status"] = before.get("status")
        stage_result["shutdown_after_status"] = after.get("status")
        if after.get("status") != "PASS":
            raise RuntimeError("lane-recovery shutdown-after unconfirmed")
        if stage_result.get("status") != "PASS":
            raise RuntimeError("lane-recovery diagnostic failed closed")

        terminal = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, "final", env
        )
        shutdowns.append(terminal)
        if terminal.get("status") != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        run_errors.append("Ctrl+C")
    except Exception as exc:
        run_errors.append(str(exc))
    finally:
        if not archived:
            try:
                retry = campaign.capture_and_archive(
                    f"{STAGE}_finally_before_shutdown", run_root,
                    auth_path, env, force_abort=True
                )
                forensics.append(retry)
                if retry.get("status") != "PASS":
                    run_errors.append("finally forensic archive failed")
            except BaseException as exc:  # preserve shutdown on every exit
                run_errors.append(f"finally forensic exception: {exc}")
        hardware_actions = True
        emergency = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, "finally", env
        )
        shutdowns.append(emergency)
        if emergency.get("status") != "PASS":
            run_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                campaign.terminate_tree(server_proc)
            except Exception as exc:
                run_errors.append(f"hw_server termination failed: {exc}")

    all_shutdown = bool(shutdowns) and all(
        item.get("status") == "PASS"
        and item.get("SHUTDOWN_FIXED") == "PASS"
        and item.get("SHUTDOWN_ROTATING") == "PASS"
        for item in shutdowns
    )
    status = "PASS" if (
        stage_result is not None
        and stage_result.get("status") == "PASS"
        and all_shutdown
        and not run_errors
    ) else "FAIL_CLOSED"
    summary = {
        "schema_version": 1,
        "test_id": "P10_4-LANE-RECOVERY-DIAGNOSTIC",
        "status": status,
        "scope": campaign.SCOPE,
        "run_id": args.run_id,
        "goal_sha256": campaign.GOAL_SHA256,
        "diagnostic_only": True,
        "full_campaign_pass_claimed": False,
        "artifact_source_commit": authorization["source_commit"],
        "artifacts": authorization["artifacts"],
        "selected_config": selected_config(),
        "stage": stage_result,
        "forensics": forensics,
        "shutdowns": shutdowns,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown else "FAIL",
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "hardware_moved": False,
        "wiring_changed": False,
        "module_replaced": False,
        "external_instrumentation_used": False,
        "maximum_lane_mask": 15,
        "errors": run_errors,
        "generated_at_utc": campaign.utc_now(),
    }
    manifest_errors = publish_terminal_evidence(run_root, summary)
    if manifest_errors:
        status = "FAIL_CLOSED"
    consume_authorization(auth_path, authorization, run_root, status, summary["errors"])
    print(f"P10_4_LANE_RECOVERY_DIAGNOSTIC={status}")
    print(f"P10_4_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
