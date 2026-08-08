#!/usr/bin/env python3
"""Create the immutable authorization for a verified P10.4 suffix resume."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_4_hardware as campaign
import run_p10_4_resume_hardware as resume


ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / "config/p10_4_resume_current_run_hardware_authorization.json"
GENERATED = ROOT / "evidence/generated/p10_4_resume_authorization"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def resolve_output(path: Path) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"P10_4_RESUME_AUTH_REFUSED=outside repository: {path}") from exc
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--evidence-base", type=Path, default=GENERATED)
    args = parser.parse_args(argv)
    auth_path = resolve_output(args.authorization)
    evidence_base = resolve_output(args.evidence_base)
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        errors.append("resume authorization must be materialized offline")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                               text=True).strip():
        errors.append("worktree must be clean before resume authorization")
    try:
        freeze = resume.load_json(campaign.FREEZE)
        checkpoint = resume.load_json(resume.PARENT_CHECKPOINT)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"P10_4_RESUME_AUTH_REFUSED={exc}")
    _, selected, parent_run_root, parent_errors = \
        resume.validate_parent_checkpoint(checkpoint)
    errors.extend(parent_errors)
    for path, label in (
        (campaign.FREEZE, "artifact freeze"),
        (resume.PARENT_CHECKPOINT, "parent checkpoint"),
    ):
        if not campaign.file_matches_head(path):
            errors.append(f"{label} is not the exact committed HEAD version")
    for name, item in resume.resume_host_inputs().items():
        if not campaign.file_matches_head((ROOT / item["path"]).resolve()):
            errors.append(f"resume host input is not committed: {name}")
    source = str(freeze.get("source_commit", ""))
    if subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"],
                      cwd=ROOT, check=False).returncode != 0:
        errors.append("artifact source commit is not an ancestor of HEAD")
    artifacts_by_key = {
        campaign.artifact_key(item): item for item in freeze.get("artifacts", [])
        if isinstance(item, dict)
    }
    try:
        fixed = artifacts_by_key["fixed:functional_bitstream"]["sha256"]
        rotating = artifacts_by_key["rotating:functional_bitstream"]["sha256"]
    except KeyError:
        errors.append("functional bitstream artifacts missing")
        fixed = rotating = ""
    now = datetime.now(timezone.utc)
    run_id = (
        f"p10_4_{now.strftime('%Y%m%dT%H%M%SZ')}_{source[:8]}_"
        f"{fixed[:8]}_{rotating[:8]}"
    )
    if campaign.RUN_RE.fullmatch(run_id) is None:
        errors.append("content-bound resume run id generation failed")
    plans = campaign.build_plans(selected)
    plan_hashes = {
        stage: hashlib.sha256(plans[stage].encode("ascii")).hexdigest()
        for stage in resume.RESUME_STAGES
    }
    policy = campaign.load_policy(campaign.RUNTIME_REST_POLICY)
    payload = {
        "schema_version": 1,
        "authorization_id": "P10_4-RESUME-CURRENT-RUN-IMMUTABLE",
        "status": "READY_FOR_EXACT_RESUME_RUN" if not errors else "FAIL",
        "scope": resume.RESUME_SCOPE,
        "run_id": run_id,
        "authorized": not errors,
        "consumed": False,
        "current_run_hardware_authorization": not errors,
        "no_hardware": False if not errors else True,
        "authorization_source": [
            "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md",
            "direct user continuation instruction dated 2026-08-08",
            "campaign-level standing authorization already recorded for P10.4",
        ],
        "authorization_source_semantics": (
            "The user authorized all P10.4 operations and instructed Codex to continue. "
            "This run reexecutes the interrupted stage and every exact remaining stage "
            "after a verified emergency shutdown and half-runtime cooldown."
        ),
        "current_user_statement": "继续",
        "goal_sha256": campaign.GOAL_SHA256,
        "artifact_freeze": campaign.rel(campaign.FREEZE),
        "artifact_freeze_sha256": campaign.sha256(campaign.FREEZE),
        "source_commit": source,
        "authorization_parent_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "parent_run_id": checkpoint.get("parent_run_id"),
        "parent_evidence_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "parent_checkpoint": resume.metadata(resume.PARENT_CHECKPOINT),
        "parent_run_manifest": checkpoint.get("parent_run_manifest"),
        "parent_completed_stage_count": len(resume.PREFIX_STAGES),
        "completed_parent_stages": list(resume.PREFIX_STAGES),
        "interrupted_stage": resume.INTERRUPTED_STAGE,
        "resume_stages": list(resume.RESUME_STAGES),
        "selected_config": selected,
        "resume_plan_sha256": plan_hashes,
        "stage_runtime_limits_seconds": {
            stage: campaign.stage_timeout(stage) for stage in resume.RESUME_STAGES
        },
        "fixed_jtag_serial": campaign.EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": campaign.EXPECTED_ROTATING_SERIAL,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{campaign.EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{campaign.EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": campaign.MODULE_BINDING,
        "pre_run_module_change": campaign.PRE_RUN_MODULE_CHANGE,
        "hardware_configuration_inputs": campaign.hardware_configuration_inputs(),
        "resume_host_inputs": resume.resume_host_inputs(),
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "maximum_continuous_module_runtime_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "maximum_aggregate_command_bytes": 128 << 20,
        "ethernet_allowed": False,
        "external_instrumentation_allowed": False,
        "movement_rotation_realignment_rewiring_or_module_replacement_allowed": False,
        "retry_override": {
            "user_statement": "不设上限",
            "new_run_id_limit": None,
            "formal_run_max_seconds_unchanged": 1800,
        },
        "register_map": {
            "version": f"0x{campaign.REGISTER_MAP_VERSION:08X}",
            "hash_low": f"0x{campaign.REGISTER_MAP_HASH_LOW:08X}",
        },
        "runtime_rest_policy": {
            "path": campaign.rel(campaign.RUNTIME_REST_POLICY),
            "sha256": campaign.sha256(campaign.RUNTIME_REST_POLICY),
            "policy_id": policy["policy_id"],
            "maximum_continuous_runtime_seconds": 1800,
            "minimum_cooldown_ratio": 0.5,
            "conservative_modules": list(campaign.ALL_MODULES),
        },
        "shutdown_policy": campaign.SHUTDOWN_POLICY,
        "offline_inputs": freeze.get("offline_inputs", {}),
        "artifacts": freeze.get("artifacts", []),
        "network_used": False,
        "hardware_moved": False,
        "wiring_changed": False,
        "module_replaced": False,
        "external_instrumentation_used": False,
        "errors": errors,
        "created_at_utc": now.isoformat(),
    }
    if parent_run_root is None or parent_run_root.name != payload["parent_run_id"]:
        payload["errors"].append("parent run root binding mismatch")
        payload["status"] = "FAIL"
        payload["authorized"] = False
        payload["current_run_hardware_authorization"] = False
        payload["no_hardware"] = True
    write_json(auth_path, payload)
    evidence = {
        "schema_version": 1,
        "test_id": "P10_4-RESUME-CURRENT-RUN-AUTHORIZATION",
        "status": payload["status"],
        "run_id": run_id,
        "parent_run_id": payload["parent_run_id"],
        "authorization": campaign.rel(auth_path),
        "authorization_sha256": campaign.sha256(auth_path),
        "parent_checkpoint": payload["parent_checkpoint"],
        "resume_stages": payload["resume_stages"],
        "current_run_hardware_authorization": payload[
            "current_run_hardware_authorization"
        ],
        "hardware_actions_executed": False,
        "errors": payload["errors"],
    }
    write_json(evidence_base.with_suffix(".json"), evidence)
    evidence_base.with_suffix(".md").write_text(
        "# P10.4 resume current-run authorization\n\n"
        f"- Status: `{payload['status']}`\n"
        f"- Run ID: `{run_id}`\n"
        f"- Parent run: `{payload['parent_run_id']}`\n"
        f"- Resume stages: `{len(resume.RESUME_STAGES)}`\n"
        f"- Authorization SHA256: `{evidence['authorization_sha256']}`\n"
        "- Hardware actions executed: `false`\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"P10_4_RESUME_AUTHORIZATION={payload['status']}")
    print(f"P10_4_RESUME_RUN_ID={run_id}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if payload["status"] == "READY_FOR_EXACT_RESUME_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
