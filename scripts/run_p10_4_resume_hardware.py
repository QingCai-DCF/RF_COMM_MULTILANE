#!/usr/bin/env python3
"""Resume the exact unfinished suffix of an interrupted P10.4 campaign.

The parent run is immutable and must prove a contiguous PASS prefix, verified
dual emergency shutdown, and the required post-interruption cooldown.  This
runner creates a new evidence root and executes every remaining stage from the
interrupted stage onward.  It never skips a stage based only on directory
presence and never mutates the parent raw evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import run_p10_4_hardware as campaign
from p10_tfdu_runtime_guard import RuntimeRestGuard, load_policy


ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "config/p10_4_resume_current_run_hardware_authorization.json"
PARENT_CHECKPOINT = ROOT / "evidence/generated/p10_4_interrupted_parent_checkpoint.json"
AUTH_BUILDER = ROOT / "scripts/create_p10_4_resume_authorization.py"
PARENT_FINALIZER = ROOT / "scripts/finalize_p10_4_interrupted_run.py"
INTERRUPTED_STAGE = "pl_reset_rotating_2"
PREFIX_STAGES = campaign.STAGES[: campaign.STAGES.index(INTERRUPTED_STAGE)]
RESUME_STAGES = campaign.STAGES[campaign.STAGES.index(INTERRUPTED_STAGE):]
RESUME_SCOPE = campaign.SCOPE + "_RESUME_SUFFIX"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def metadata(path: Path) -> dict[str, Any]:
    return {
        "path": campaign.rel(path),
        "sha256": campaign.sha256(path),
        "bytes": path.stat().st_size,
    }


def resume_host_inputs() -> dict[str, dict[str, Any]]:
    paths = {
        "resume_runner": Path(__file__).resolve(),
        "campaign_library": Path(campaign.__file__).resolve(),
        "authorization_builder": AUTH_BUILDER,
        "parent_finalizer": PARENT_FINALIZER,
        "runtime_rest_guard": ROOT / "scripts/p10_tfdu_runtime_guard.py",
        "parent_checkpoint": PARENT_CHECKPOINT,
    }
    return {name: metadata(path) for name, path in paths.items()}


def verify_metadata(item: Any, label: str) -> tuple[Path | None, list[str]]:
    errors: list[str] = []
    if not isinstance(item, dict):
        return None, [f"{label} metadata is malformed"]
    try:
        path = (ROOT / item["path"]).resolve()
        if not campaign.base.inside(path, ROOT) or not path.is_file():
            errors.append(f"{label} file is missing or outside repository")
        elif path.stat().st_size != item["bytes"] or \
                campaign.sha256(path) != item["sha256"]:
            errors.append(f"{label} hash/size mismatch")
        return path, errors
    except (KeyError, OSError, TypeError, ValueError) as exc:
        return None, [f"{label} metadata error: {exc}"]


def validate_parent_checkpoint(checkpoint: dict[str, Any]) -> tuple[
        list[dict[str, Any]], dict[str, Any], Path | None, list[str]]:
    errors: list[str] = []
    expected = {
        "schema_version": 1,
        "test_id": "P10_4-INTERRUPTED-PARENT-CHECKPOINT",
        "status": "PASS",
        "parent_run_outcome": "INTERRUPTED_FAIL_CLOSED_RESUMABLE",
        "goal_sha256": campaign.GOAL_SHA256,
        "completed_stage_count": len(PREFIX_STAGES),
        "completed_stages": list(PREFIX_STAGES),
        "interrupted_stage": INTERRUPTED_STAGE,
        "remaining_stages": list(RESUME_STAGES),
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "cooldown_status": "PASS",
        "resume_requires_new_current_run_authorization": True,
        "p10_4_acceptance_promoted": False,
    }
    for name, value in expected.items():
        if checkpoint.get(name) != value:
            errors.append(f"parent checkpoint {name} mismatch")
    selected = checkpoint.get("selected_config")
    if not isinstance(selected, dict) or selected not in campaign.candidate_configs():
        errors.append("parent selected configuration is invalid")
        selected = {}
    interruption = checkpoint.get("interruption", {})
    if not isinstance(interruption, dict) or interruption.get("status") != "PASS" or \
            interruption.get("stage") != INTERRUPTED_STAGE or \
            interruption.get("reexecution_required") is not True or \
            interruption.get("runtime_limit_status") != "PASS" or \
            interruption.get("cooldown_status") != "PASS" or \
            float(interruption.get("actual_cooldown_seconds", -1)) + 1e-6 < \
            float(interruption.get("required_cooldown_seconds", 999999)):
        errors.append("parent interruption closeout is not safe to resume")
    emergency = interruption.get("emergency_shutdown_markers", {}) \
        if isinstance(interruption, dict) else {}
    for name, value in {
        "SHUTDOWN_FIXED": "PASS", "SHUTDOWN_ROTATING": "PASS",
        "TFDU_SHUTDOWN_PROGRAMMED": "1", "SHUTDOWN_EXIT": "0",
    }.items():
        if not isinstance(emergency, dict) or emergency.get(name) != value:
            errors.append(f"parent emergency shutdown marker missing: {name}")

    parent_manifest_path, manifest_meta_errors = verify_metadata(
        checkpoint.get("parent_run_manifest"), "parent run manifest"
    )
    errors.extend(manifest_meta_errors)
    parent_run_root: Path | None = None
    if parent_manifest_path is not None:
        try:
            parent_run_root = parent_manifest_path.parents[1]
            manifest = load_json(parent_manifest_path)
            errors.extend(campaign.verify_evidence_manifest(parent_run_root, manifest))
            if manifest.get("file_count") != checkpoint.get("parent_manifest_file_count"):
                errors.append("parent manifest file count mismatch")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"parent run manifest unreadable: {exc}")

    records = checkpoint.get("completed_stage_records")
    if not isinstance(records, list) or len(records) != len(PREFIX_STAGES):
        errors.append("parent completed-stage record count mismatch")
        records = []
    if [record.get("stage") for record in records if isinstance(record, dict)] != \
            list(PREFIX_STAGES):
        errors.append("parent completed-stage record order mismatch")
    prefix_results: list[dict[str, Any]] = []
    for index, stage in enumerate(PREFIX_STAGES):
        record = records[index] if index < len(records) and \
            isinstance(records[index], dict) else {}
        if record.get("status") != "PASS":
            errors.append(f"parent stage is not PASS: {stage}")
        summary_path, item_errors = verify_metadata(record.get("summary"), f"{stage} summary")
        errors.extend(item_errors)
        for key in ("plan", "forensic_summary", "shutdown_before", "shutdown_after"):
            _, item_errors = verify_metadata(record.get(key), f"{stage} {key}")
            errors.extend(item_errors)
        runtime = record.get("runtime_rest", {})
        if not isinstance(runtime, dict) or runtime.get("stage") != stage or \
                runtime.get("status") != "PASS" or \
                runtime.get("shutdown_verified") is not True or \
                runtime.get("runtime_limit_status") != "PASS" or \
                runtime.get("cooldown_status") != "PASS":
            errors.append(f"parent runtime/rest record is not PASS: {stage}")
        if summary_path is not None:
            try:
                summary = load_json(summary_path)
                if summary.get("stage") != stage or summary.get("status") != "PASS":
                    errors.append(f"parent stage summary content mismatch: {stage}")
                summary["runtime_rest"] = runtime
                summary["shutdown_before_status"] = "PASS"
                summary["shutdown_after_status"] = "PASS"
                summary["evidence_run_role"] = "parent_prefix"
                prefix_results.append(summary)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"parent stage summary unreadable {stage}: {exc}")
    return prefix_results, dict(selected), parent_run_root, errors


def validate_authorization(path: Path, run_id: str) -> tuple[
        dict[str, Any], dict[str, Path], list[dict[str, Any]], list[str]]:
    errors = campaign.validate_plans()
    try:
        auth = load_json(path)
        freeze = load_json(campaign.FREEZE)
        checkpoint = load_json(PARENT_CHECKPOINT)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {}, [], [f"resume authorization input unreadable: {exc}"]
    prefix_results, selected, parent_run_root, parent_errors = \
        validate_parent_checkpoint(checkpoint)
    errors.extend(parent_errors)
    expected = {
        "schema_version": 1,
        "authorization_id": "P10_4-RESUME-CURRENT-RUN-IMMUTABLE",
        "status": "READY_FOR_EXACT_RESUME_RUN",
        "scope": RESUME_SCOPE,
        "run_id": run_id,
        "authorized": True,
        "consumed": False,
        "current_run_hardware_authorization": True,
        "no_hardware": False,
        "goal_sha256": campaign.GOAL_SHA256,
        "source_commit": freeze.get("source_commit"),
        "fixed_jtag_serial": campaign.EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": campaign.EXPECTED_ROTATING_SERIAL,
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "maximum_continuous_module_runtime_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "ethernet_allowed": False,
        "external_instrumentation_allowed": False,
        "movement_rotation_realignment_rewiring_or_module_replacement_allowed": False,
        "resume_stages": list(RESUME_STAGES),
        "completed_parent_stages": list(PREFIX_STAGES),
        "interrupted_stage": INTERRUPTED_STAGE,
        "selected_config": selected,
    }
    for name, value in expected.items():
        if auth.get(name) != value:
            errors.append(f"resume authorization {name} mismatch")
    if campaign.RUN_RE.fullmatch(run_id) is None:
        errors.append("resume run id is not content-bound P10.4 syntax")
    if auth.get("parent_checkpoint") != metadata(PARENT_CHECKPOINT):
        errors.append("resume authorization parent checkpoint mismatch")
    if parent_run_root is not None and auth.get("parent_run_id") != parent_run_root.name:
        errors.append("resume authorization parent run id mismatch")
    if auth.get("resume_host_inputs") != resume_host_inputs():
        errors.append("resume authorization host inputs mismatch")
    plans = campaign.build_plans(selected)
    expected_plan_hashes = {
        stage: hashlib.sha256(plans[stage].encode("ascii")).hexdigest()
        for stage in RESUME_STAGES
    }
    if auth.get("resume_plan_sha256") != expected_plan_hashes:
        errors.append("resume authorization plan hash set mismatch")
    if auth.get("stage_runtime_limits_seconds") != {
            stage: campaign.stage_timeout(stage) for stage in RESUME_STAGES}:
        errors.append("resume authorization stage runtime limits mismatch")
    if auth.get("artifacts") != freeze.get("artifacts") or \
            auth.get("offline_inputs") != freeze.get("offline_inputs"):
        errors.append("resume authorization differs from artifact freeze")
    if auth.get("module_binding") != campaign.MODULE_BINDING or \
            auth.get("hardware_configuration_inputs") != \
            campaign.hardware_configuration_inputs():
        errors.append("resume authorization hardware binding mismatch")
    if not campaign.file_matches_head(path) or \
            not campaign.file_matches_head(PARENT_CHECKPOINT) or \
            not campaign.file_matches_head(campaign.FREEZE):
        errors.append("resume authorization/checkpoint/freeze are not exact HEAD inputs")
    for name, item in resume_host_inputs().items():
        candidate = (ROOT / item["path"]).resolve()
        if not campaign.file_matches_head(candidate):
            errors.append(f"resume host input is not committed: {name}")

    artifacts: dict[str, Path] = {}
    items = {
        campaign.artifact_key(item): item for item in freeze.get("artifacts", [])
        if isinstance(item, dict)
    }
    for key, item in items.items():
        try:
            candidate = (ROOT / item["path"]).resolve()
            if not campaign.base.inside(candidate, ROOT) or not candidate.is_file() or \
                    candidate.stat().st_size != item["bytes"] or \
                    campaign.sha256(candidate) != item["sha256"]:
                errors.append(f"resume artifact changed: {key}")
            else:
                artifacts[key] = candidate
        except (KeyError, OSError, TypeError, ValueError):
            errors.append(f"malformed resume artifact: {key}")
    required = {
        f"{role}:{kind}" for role in ("fixed", "rotating")
        for kind in ("shutdown_bitstream", "functional_bitstream", "xsa", "bsp", "elf")
    }
    if set(artifacts) != required:
        errors.append("resume artifact set incomplete")
    return auth, artifacts, prefix_results, errors


def initialize_resume_run(run_root: Path, auth: Path,
                          artifacts: dict[str, Path]) -> dict[str, Path]:
    ps7 = campaign.initialize_run(run_root, auth, artifacts)
    shutil.copy2(PARENT_CHECKPOINT, run_root / "authorization/parent_checkpoint.json")
    checkpoint = load_json(PARENT_CHECKPOINT)
    parent_manifest = (ROOT / checkpoint["parent_run_manifest"]["path"]).resolve()
    shutil.copy2(parent_manifest, run_root / "authorization/parent_run_manifest.json")
    campaign.write_json(run_root / "authorization/resume_contract.json", {
        "schema_version": 1,
        "status": "PASS",
        "parent_run_id": checkpoint["parent_run_id"],
        "completed_parent_stages": list(PREFIX_STAGES),
        "resume_stages": list(RESUME_STAGES),
        "interrupted_stage_reexecuted_first": INTERRUPTED_STAGE,
        "parent_manifest": checkpoint["parent_run_manifest"],
    })
    return ps7


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    auth_path = args.authorization.resolve()
    authorization, artifacts, prefix_results, errors = validate_authorization(
        auth_path, args.run_id
    )
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                               text=True).strip():
        errors.append("resume worktree must be clean")
    if args.validate_only:
        print(json.dumps({"status": "PASS" if not errors else "FAIL",
                          "errors": errors}, indent=2))
        return 0 if not errors else 3
    if not args.execute_hardware:
        errors.append("--execute-hardware is required")
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    run_root = campaign.HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("resume run-id evidence directory already exists")
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
    ps7 = initialize_resume_run(run_root, auth_path, artifacts)
    runtime_guard = RuntimeRestGuard(
        load_policy(campaign.RUNTIME_REST_POLICY),
        run_root / "runtime_rest/runtime_rest_ledger.json",
        campaign.ALL_MODULES,
    )
    server_proc = None
    stage_results: list[dict[str, Any]] = []
    shutdown_results: list[dict[str, Any]] = []
    forensic_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    selected = dict(authorization["selected_config"])
    hardware_actions = False
    active_stage: str | None = None
    runtime_stage_active = False
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
        shutdown_results.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("resume initial dual shutdown unconfirmed")
        plans = campaign.build_plans(selected)
        for stage in RESUME_STAGES:
            runtime_guard.wait_for_cooldown()
            active_stage = stage
            archived = False
            before = campaign.guarded_shutdown(
                run_root, auth_path, artifacts, f"{stage}_before", env
            )
            shutdown_results.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"{stage}: shutdown-before unconfirmed")
            actual_hash = hashlib.sha256(plans[stage].encode("ascii")).hexdigest()
            if authorization["resume_plan_sha256"].get(stage) != actual_hash:
                raise RuntimeError(f"{stage}: immutable resume plan mismatch")
            runtime_guard.begin_stage(stage, campaign.stage_timeout(stage))
            runtime_stage_active = True
            process, stage_dir = campaign.invoke_stage(
                stage, plans[stage], run_root, auth_path, artifacts, ps7, env
            )
            process_failed = bool(
                process.get("returncode") != 0 or process.get("timed_out")
            )
            archive = campaign.capture_and_archive(
                stage, run_root, auth_path, env, force_abort=process_failed
            )
            forensic_results.append(archive)
            archived = archive.get("status") == "PASS"
            if not archived:
                raise RuntimeError(f"{stage}: forensic archive failed")
            after = campaign.guarded_shutdown(
                run_root, auth_path, artifacts, f"{stage}_after", env
            )
            shutdown_results.append(after)
            runtime_record = runtime_guard.finish_stage(
                shutdown_verified=after.get("status") == "PASS"
            )
            runtime_stage_active = False
            runtime_guard.wait_for_cooldown()
            result = campaign.evaluate_stage(
                stage, stage_dir, process, archive, plans[stage]
            )
            result["runtime_rest"] = dict(runtime_record)
            result["shutdown_before_status"] = before.get("status")
            result["shutdown_after_status"] = after.get("status")
            result["evidence_run_role"] = "resume_suffix"
            campaign.write_json(stage_dir / "stage_summary.json", result)
            stage_results.append(result)
            if after.get("status") != "PASS":
                raise RuntimeError(f"{stage}: shutdown-after unconfirmed")
            if result.get("status") != "PASS" and \
                    stage not in campaign.NONBLOCKING_STAGES:
                raise RuntimeError(f"{stage}: mandatory resume stage failed closed")
        final_shutdown = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, "final", env
        )
        shutdown_results.append(final_shutdown)
        if final_shutdown.get("status") != "PASS":
            raise RuntimeError("resume final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if active_stage is not None and not archived:
            try:
                retry = campaign.capture_and_archive(
                    f"{active_stage}_finally_before_shutdown", run_root,
                    auth_path, env, force_abort=True,
                )
                forensic_results.append(retry)
                if retry.get("status") != "PASS":
                    campaign_errors.append("finally forensic archive failed")
            except BaseException as exc:
                campaign_errors.append(f"finally forensic exception: {exc}")
        hardware_actions = True
        emergency = campaign.guarded_shutdown(
            run_root, auth_path, artifacts, "finally", env
        )
        shutdown_results.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if runtime_stage_active:
            try:
                runtime_guard.finish_stage(
                    shutdown_verified=emergency.get("status") == "PASS"
                )
                runtime_stage_active = False
                runtime_guard.wait_for_cooldown()
            except BaseException as exc:
                campaign_errors.append(f"runtime/rest finalization failed: {exc}")
        if server_proc is not None:
            try:
                campaign.terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"hw_server termination failed: {exc}")

    by_stage = {item["stage"]: item for item in stage_results}
    mandatory = [stage for stage in RESUME_STAGES
                 if stage not in campaign.NONBLOCKING_STAGES]
    mandatory_pass = all(by_stage.get(stage, {}).get("status") == "PASS"
                         for stage in mandatory)
    all_shutdown = bool(shutdown_results) and all(
        item.get("status") == "PASS" and item.get("SHUTDOWN_FIXED") == "PASS"
        and item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdown_results
    )
    counters = campaign.zero_counter_summary(stage_results)
    hard_zero = all(value == 0 for value in counters.values())
    runtime_ledger = runtime_guard.public_ledger()
    runtime_policy_pass = (
        runtime_ledger.get("status") == "PASS"
        and len(runtime_ledger.get("stages", [])) == len(stage_results)
    )
    nonblocking_failures = [stage for stage in RESUME_STAGES
                            if stage in campaign.NONBLOCKING_STAGES and
                            by_stage.get(stage, {}).get("status") != "PASS"]
    if mandatory_pass and all_shutdown and hard_zero and runtime_policy_pass \
            and not campaign_errors:
        status = "PASS_WITH_NONBLOCKING_LIMITS" if nonblocking_failures else "PASS"
    else:
        status = "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": "P10_4-RESUME-SUFFIX",
        "status": status,
        "scope": RESUME_SCOPE,
        "run_id": args.run_id,
        "parent_run_id": authorization["parent_run_id"],
        "parent_checkpoint": authorization["parent_checkpoint"],
        "goal_sha256": campaign.GOAL_SHA256,
        "artifact_source_commit": authorization["source_commit"],
        "artifacts": authorization["artifacts"],
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "resume_stages": list(RESUME_STAGES),
        "selected_config": selected,
        "module_binding": campaign.MODULE_BINDING,
        "stages": stage_results,
        "runtime_rest_policy_status": "PASS" if runtime_policy_pass else "FAIL",
        "runtime_rest_ledger": runtime_ledger,
        "counters": counters,
        "forensics": forensic_results,
        "shutdowns": shutdown_results,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown else "FAIL",
        "nonblocking_failures": sorted(nonblocking_failures),
        "network_used": False,
        "hardware_moved": False,
        "wiring_changed": False,
        "module_replaced": False,
        "external_instrumentation_used": False,
        "p11_status": "NOT_STARTED",
        "errors": campaign_errors,
        "generated_at_utc": campaign.utc_now(),
    }
    campaign.write_json(run_root / "final/resume_orchestrator_result.json", summary)
    consistency = {
        "schema_version": 1,
        "test_id": "P10_4-RESUME-EVIDENCE-CONSISTENCY",
        "status": "PASS",
        "run_id": args.run_id,
        "parent_run_id": authorization["parent_run_id"],
        "manifest": campaign.rel(
            run_root / "final/run_evidence_sha256_manifest.json"
        ),
        "errors": [],
    }
    campaign.write_json(run_root / "final/resume_evidence_consistency.json", consistency)
    manifest = campaign.evidence_manifest(run_root)
    manifest_errors = campaign.verify_evidence_manifest(run_root, manifest)
    if manifest_errors:
        summary["status"] = "FAIL"
        summary["errors"].extend(manifest_errors)
        consistency["status"] = "FAIL"
        consistency["errors"] = manifest_errors
        campaign.write_json(run_root / "final/resume_orchestrator_result.json", summary)
        campaign.write_json(
            run_root / "final/resume_evidence_consistency.json", consistency
        )
        # Re-freeze once after the terminal failure records are final.
        manifest = campaign.evidence_manifest(run_root)
        terminal_errors = campaign.verify_evidence_manifest(run_root, manifest)
        if terminal_errors:
            print(json.dumps({"terminal_manifest_errors": terminal_errors}),
                  file=sys.stderr)
    consumed = dict(authorization)
    consumed.update({
        "status": f"CONSUMED_AFTER_P10_4_RESUME_{summary['status']}",
        "current_run_hardware_authorization": False,
        "consumed": True,
        "consumed_at_utc": campaign.utc_now(),
        "result": campaign.rel(run_root / "final/resume_orchestrator_result.json"),
        "evidence_manifest": campaign.rel(
            run_root / "final/run_evidence_sha256_manifest.json"
        ),
    })
    campaign.write_json(auth_path, consumed)
    campaign.write_pair(ROOT / "evidence/generated/p10_4_resume_authorization", {
        "schema_version": 1,
        "test_id": "P10_4-RESUME-AUTHORIZATION",
        "status": consumed["status"],
        "run_id": args.run_id,
        "parent_run_id": authorization["parent_run_id"],
        "authorization": campaign.rel(auth_path),
        "current_run_hardware_authorization": False,
        "consumed": True,
        "result": consumed["result"],
        "errors": [],
    }, "P10.4 resume current-run authorization")
    print(f"P10_4_RESUME_HARDWARE={summary['status']}")
    print(f"P10_4_RESUME_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if summary["status"] in {"PASS", "PASS_WITH_NONBLOCKING_LIMITS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
