#!/usr/bin/env python3
"""Materialize the Goal-authorized exact P10.5 current hardware run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_5_hardware as campaign


ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "evidence/generated/p10_5_artifact_freeze.json"
AUTH = ROOT / "config/p10_5_current_run_hardware_authorization.json"
GENERATED = ROOT / "evidence/generated/p10_5_authorization"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path),
            "bytes": path.stat().st_size}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def resolve_output(path: Path) -> Path:
    candidate = (path if path.is_absolute() else ROOT / path).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"P10_5_AUTHORIZATION_REFUSED=outside repository: {path}") from exc
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
        raise SystemExit(f"P10_5_AUTHORIZATION_REFUSED={exc}")
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("artifact freeze is not acceptance eligible")
    try:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{rel(FREEZE)}"], cwd=ROOT)
        if committed != FREEZE.read_bytes():
            errors.append("artifact freeze is not the exact committed HEAD version")
    except subprocess.CalledProcessError:
        errors.append("artifact freeze is not committed")
    source = str(freeze.get("source_commit", ""))
    if subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"],
                      cwd=ROOT, check=False).returncode != 0:
        errors.append("artifact source is not an ancestor of HEAD")
    artifacts = {campaign.artifact_key(x): x for x in freeze.get("artifacts", [])}
    fixed = artifacts.get("fixed:functional_bitstream", {}).get("sha256", "")
    rotating = artifacts.get("rotating:functional_bitstream", {}).get("sha256", "")
    now = datetime.now(timezone.utc)
    run_id = (f"p10_5_{now.strftime('%Y%m%dT%H%M%SZ')}_{source[:8]}_"
              f"{fixed[:8]}_{rotating[:8]}")
    if campaign.RUN_RE.fullmatch(run_id) is None:
        errors.append("content-bound run-id generation failed")
    policy = campaign.load_policy(campaign.RUNTIME_REST_POLICY)
    payload = {
        "schema_version": 1,
        "authorization_id": "P10_5-CURRENT-RUN-IMMUTABLE",
        "status": "READY_FOR_EXACT_CURRENT_RUN" if not errors else "FAIL",
        "scope": campaign.SCOPE, "run_id": run_id,
        "authorized": not errors, "consumed": False,
        "current_run_hardware_authorization": not errors,
        "no_hardware": False if not errors else True,
        "authorization_source": [
            "goals/P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE_GOAL.md",
            "direct user submission of the P10.5 Goal dated 2026-08-09",
            "direct user statement dated 2026-08-27: 我已将B0025换位换为新的B0011，请你继续目标",
        ],
        "authorization_source_semantics": (
            "Submitting the Goal explicitly authorizes its complete bounded P10.5 "
            "hardware campaign without further confirmation after immutable offline freeze."
        ),
        "pre_run_user_module_replacement": {
            "logical_module": "R3", "position": "AX7020-R/J11-B",
            "removed_small_board_id": "B0025",
            "installed_small_board_id": "B0011",
            "identity_basis": "USER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            "replacement_power_state": "NOT_STATED_BY_USER; NOT_CLAIMED",
            "codex_physical_action": False,
            "historical_b0025_evidence_preserved": True,
        },
        "goal_sha256": campaign.GOAL_SHA256,
        "artifact_freeze": rel(FREEZE), "artifact_freeze_sha256": sha256(FREEZE),
        "source_commit": source,
        "authorization_parent_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "fixed_jtag_serial": campaign.EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": campaign.EXPECTED_ROTATING_SERIAL,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{campaign.EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{campaign.EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": campaign.MODULE_BINDING,
        "maximum_lane_mask": 15, "maximum_single_formal_run_seconds": 1800,
        "maximum_continuous_module_runtime_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "ethernet_allowed": False, "spi_allowed": False,
        "external_instrumentation_allowed": False,
        "movement_rotation_realignment_rewiring_or_module_replacement_allowed": False,
        "p11_allowed": False, "two_hour_test_allowed": False,
        "shutdown_policy": campaign.SHUTDOWN_POLICY,
        "runtime_rest_policy": {
            "path": rel(campaign.RUNTIME_REST_POLICY),
            "sha256": sha256(campaign.RUNTIME_REST_POLICY),
            "policy_id": policy["policy_id"],
            "maximum_continuous_runtime_seconds": 1800,
            "minimum_cooldown_ratio": 0.5,
            "conservative_modules": list(campaign.ALL_MODULES),
        },
        "register_map": {
            "version": f"0x{campaign.REGISTER_MAP_VERSION:08X}",
            "hash_low": f"0x{campaign.REGISTER_MAP_HASH_LOW:08X}",
        },
        "primary_partition": {"active": 15, "f_to_r": 3, "r_to_f": 12},
        "allowed_stages": list(campaign.STAGES),
        "stage_runtime_limits_seconds": {
            stage: campaign.stage_runtime_limit(stage) for stage in campaign.STAGES},
        "allowed_plan_sha256": campaign.plan_hashes(),
        "offline_inputs": freeze.get("offline_inputs", {}),
        "artifacts": freeze.get("artifacts", []),
        "hardware_configuration_inputs": {
            "actual_wiring": metadata(campaign.AS_WIRED),
            "module_inventory": metadata(campaign.MODULE_INVENTORY),
            "dual_direction_config": metadata(campaign.CONFIG),
            "runtime_rest_policy": metadata(campaign.RUNTIME_REST_POLICY),
        },
        "host_runtime_inputs": {
            name: metadata(path)
            for name, path in campaign.host_runtime_input_paths().items()
        },
        "hardware_actions_executed": False,
        "created_at_utc": now.isoformat(), "errors": errors,
    }
    write_json(auth_path, payload)
    evidence = {
        "schema_version": 1, "test_id": "P10_5-AUTHORIZATION",
        "status": payload["status"], "run_id": run_id,
        "authorization": rel(auth_path), "authorization_sha256": sha256(auth_path),
        "artifact_source_commit": source,
        "current_run_hardware_authorization": payload["current_run_hardware_authorization"],
        "hardware_actions_executed": False, "errors": errors,
    }
    write_json(evidence_base.with_suffix(".json"), evidence)
    evidence_base.with_suffix(".md").write_text(
        "# P10.5 current-run authorization\n\n"
        f"- Status: `{payload['status']}`\n- Run ID: `{run_id}`\n"
        "- Hardware actions executed: `false`\n",
        encoding="utf-8", newline="\n")
    print(f"P10_5_AUTHORIZATION={payload['status']}")
    print(f"P10_5_RUN_ID={run_id}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
