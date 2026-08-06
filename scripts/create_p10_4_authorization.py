#!/usr/bin/env python3
"""Materialize the Goal-authorized exact P10.4 current hardware run."""

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


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evidence/generated/p10_4_artifact_freeze.json"
AUTH = ROOT / "config/p10_4_current_run_hardware_authorization.json"
GENERATED = ROOT / "evidence/generated/p10_4_authorization"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def resolve_output(path: Path) -> Path:
    candidate = path if path.is_absolute() else ROOT / path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"P10_4_AUTHORIZATION_REFUSED=output outside repository: {path}") from exc
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
        errors.append("authorization must be materialized offline")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                               text=True).strip():
        errors.append("worktree must be clean before authorization materialization")
    try:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"P10_4_AUTHORIZATION_REFUSED={exc}")
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("artifact freeze is not acceptance eligible")
    try:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{rel(FREEZE)}"], cwd=ROOT
        )
        if committed != FREEZE.read_bytes():
            errors.append("artifact freeze is not the exact committed HEAD version")
    except subprocess.CalledProcessError:
        errors.append("artifact freeze is not committed")
    source = str(freeze.get("source_commit", ""))
    if subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"],
                      cwd=ROOT, check=False).returncode != 0:
        errors.append("artifact source commit is not an ancestor of HEAD")
    artifacts = {campaign.artifact_key(item): item for item in freeze.get("artifacts", [])}
    try:
        fixed = artifacts["fixed:functional_bitstream"]["sha256"]
        rotating = artifacts["rotating:functional_bitstream"]["sha256"]
    except KeyError:
        errors.append("functional bitstream artifacts missing")
        fixed = rotating = ""
    now = datetime.now(timezone.utc)
    run_id = (
        f"p10_4_{now.strftime('%Y%m%dT%H%M%SZ')}_{source[:8]}_"
        f"{fixed[:8]}_{rotating[:8]}"
    )
    if campaign.RUN_RE.fullmatch(run_id) is None:
        errors.append("content-bound run id generation failed")
    plans = campaign.build_plans(campaign.baseline_config())
    plan_hashes = {
        stage: hashlib.sha256(text.encode("ascii")).hexdigest()
        for stage, text in plans.items()
    }
    payload = {
        "schema_version": 1,
        "authorization_id": "P10_4-CURRENT-RUN-IMMUTABLE",
        "status": "READY_FOR_EXACT_CURRENT_RUN" if not errors else "FAIL",
        "scope": campaign.SCOPE, "run_id": run_id,
        "authorized": not errors, "consumed": False,
        "current_run_hardware_authorization": not errors,
        "no_hardware": False if not errors else True,
        "authorization_source": "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md",
        "authorization_source_semantics": (
            "Submitting the Goal explicitly authorizes all listed P10.4 hardware operations; "
            "there are zero user HOLD points."
        ),
        "goal_sha256": campaign.GOAL_SHA256,
        "artifact_freeze": rel(FREEZE), "artifact_freeze_sha256": sha256(FREEZE),
        "source_commit": source,
        "authorization_parent_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "fixed_jtag_serial": campaign.EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": campaign.EXPECTED_ROTATING_SERIAL,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{campaign.EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{campaign.EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": campaign.MODULE_BINDING,
        "pre_run_module_change": campaign.PRE_RUN_MODULE_CHANGE,
        "hardware_configuration_inputs": campaign.hardware_configuration_inputs(),
        "maximum_lane_mask": 15, "maximum_single_formal_run_seconds": 1800,
        "maximum_aggregate_command_bytes": 128 << 20,
        "ethernet_allowed": False, "external_instrumentation_allowed": False,
        "movement_rotation_realignment_rewiring_or_module_replacement_allowed": False,
        "allowed_stages": list(campaign.STAGES),
        "baseline_plan_sha256": plan_hashes,
        "allowed_selected_configs": campaign.candidate_configs(),
        "allowed_plan_sha256": campaign.allowed_plan_sha256(),
        "bounded_retry_policy": {"hw_server_connect": 3, "program": 2,
                                 "new_run_id_per_diagnostic_stage": 2},
        "register_map": {"version": "0x0A000004", "hash_low": "0xBCFECB39"},
        "shutdown_policy": campaign.SHUTDOWN_POLICY,
        "offline_inputs": freeze.get("offline_inputs", {}),
        "artifacts": freeze.get("artifacts", []),
        "network_used": False, "hardware_moved": False,
        "wiring_changed": False, "module_replaced": False,
        "external_instrumentation_used": False,
        "errors": errors, "created_at_utc": now.isoformat(),
    }
    write_json(auth_path, payload)
    evidence = {
        "schema_version": 1, "test_id": "P10_4-CURRENT-RUN-AUTHORIZATION",
        "status": payload["status"], "run_id": run_id,
        "authorization": rel(auth_path), "authorization_sha256": sha256(auth_path),
        "artifact_freeze": rel(FREEZE), "artifact_freeze_sha256": sha256(FREEZE),
        "current_run_hardware_authorization": payload["current_run_hardware_authorization"],
        "hardware_actions_executed": False, "errors": errors,
    }
    write_json(evidence_base.with_suffix(".json"), evidence)
    evidence_base.with_suffix(".md").write_text(
        "# P10.4 current-run authorization\n\n"
        f"- Status: `{payload['status']}`\n- Run ID: `{run_id}`\n"
        f"- Authorization SHA256: `{evidence['authorization_sha256']}`\n"
        "- Hardware actions executed: `false`\n",
        encoding="utf-8", newline="\n",
    )
    print(f"P10_4_AUTHORIZATION={payload['status']}")
    print(f"P10_4_RUN_ID={run_id}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
