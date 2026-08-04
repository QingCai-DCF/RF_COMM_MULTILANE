#!/usr/bin/env python3
"""Validate all P10.3 offline gates and freeze the exact immutable artifact bundle."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_3_ax7020_4lane_hardware as p103


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_3_raw/offline_gates"
FREEZE = GENERATED / "p10_3_artifact_freeze.json"
SUMMARY_PATHS = {
    "functional": GENERATED / "p10_3_functional_build_summary.json",
    "shutdown": GENERATED / "p10_3_shutdown_build_summary.json",
    "ps_runtime": GENERATED / "p10_3_ps_runtime_build_summary.json",
    "xsim": GENERATED / "p10_3_xsim/summary.json",
}
GATE_COMMANDS = {
    "p10_2_verify_existing": [sys.executable, "scripts/verify_p10_2_existing.py"],
    "p10_1r_verify_existing": [sys.executable, "scripts/verify_p10_1r_existing.py"],
    "p10_verify_existing": [sys.executable, "scripts/verify_p10_frozen_existing.py"],
    "p8c_safety_verify_existing": [sys.executable, "scripts/verify_p8c_existing.py"],
    "state_requirements_consistency": [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
    "no_hardware_static_scan": [sys.executable, "scripts/check_no_hardware_calls.py"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not a mapping: {rel(path)}")
    return value


def run_gate(name: str, command: list[str]) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    result = subprocess.run(
        command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=300, check=False,
    )
    log = RAW / f"{name}.log"
    log.write_text(result.stdout, encoding="utf-8", newline="\n")
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "command": command,
        "returncode": result.returncode,
        "log": rel(log),
        "log_sha256": sha256(log),
        "log_bytes": log.stat().st_size,
    }


def role_by_name(summary: dict[str, Any], role: str) -> dict[str, Any]:
    records = [item for item in summary.get("roles", [])
               if isinstance(item, dict) and item.get("role") == role]
    if len(records) != 1:
        raise ValueError(f"exactly one {role} role record required")
    return records[0]


def artifact_record(role: str, kind: str, item: dict[str, Any],
                    source_commit: str) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    expected_parent = (ROOT / "artifacts/p10_3" / source_commit / item["sha256"]).resolve()
    if path.parent != expected_parent:
        raise ValueError(f"{role}/{kind} path is not source-commit/SHA content addressed")
    if not path.is_file() or path.stat().st_size != item["bytes"] or \
            sha256(path) != item["sha256"]:
        raise ValueError(f"{role}/{kind} artifact hash/size mismatch")
    if item.get("read_only") is not True:
        raise ValueError(f"{role}/{kind} artifact is not declared read-only")
    return {
        "role": role,
        "kind": kind,
        "path": rel(path),
        "sha256": item["sha256"],
        "bytes": item["bytes"],
        "read_only": True,
    }


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() not in {
        "false", "0", "no",
    }:
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    if branch != p103.BRANCH:
        errors.append(f"branch mismatch: {branch}")
    summaries: dict[str, dict[str, Any]] = {}
    for name, path in SUMMARY_PATHS.items():
        try:
            summaries[name] = load(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
    source_commits = {str(item.get("source_commit", ""))
                      for item in summaries.values()}
    source_commit = next(iter(source_commits), "") if len(source_commits) == 1 else ""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        errors.append(f"build summaries do not bind one valid source commit: {sorted(source_commits)}")
    elif source_commit != head:
        errors.append(f"HEAD {head} differs from build source commit {source_commit}")
    for name, summary in summaries.items():
        if summary.get("status") != "PASS":
            errors.append(f"{name} summary is not PASS")
        if summary.get("source_worktree_dirty") is not False:
            errors.append(f"{name} source worktree was dirty")
        if summary.get("hardware_actions_executed") is not False:
            errors.append(f"{name} executed hardware actions")
    artifacts: list[dict[str, Any]] = []
    if not errors:
        try:
            for role in ("fixed", "rotating"):
                functional = role_by_name(summaries["functional"], role)
                shutdown = role_by_name(summaries["shutdown"], role)
                runtime = role_by_name(summaries["ps_runtime"], role)
                artifacts.append(artifact_record(
                    role, "shutdown_bitstream", shutdown["artifact"], source_commit
                ))
                artifacts.append(artifact_record(
                    role, "functional_bitstream", functional["artifacts"]["bitstream"], source_commit
                ))
                artifacts.append(artifact_record(
                    role, "xsa", functional["artifacts"]["xsa"], source_commit
                ))
                artifacts.append(artifact_record(
                    role, "bsp", runtime["artifacts"]["bsp"], source_commit
                ))
                artifacts.append(artifact_record(
                    role, "elf", runtime["artifacts"]["elf"], source_commit
                ))
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"artifact extraction failed: {exc}")
    offline_gates = {name: run_gate(name, command)
                     for name, command in GATE_COMMANDS.items()}
    for name, result in offline_gates.items():
        if result["status"] != "PASS":
            errors.append(f"offline gate failed: {name}")
    for name in ("functional_fixed", "functional_rotating"):
        role = name.split("_", 1)[1]
        record = role_by_name(summaries.get("functional", {}), role)
        offline_gates[name] = {"status": record.get("status", "FAIL")}
    for name in ("shutdown_fixed", "shutdown_rotating"):
        role = name.split("_", 1)[1]
        record = role_by_name(summaries.get("shutdown", {}), role)
        offline_gates[name] = {"status": record.get("status", "FAIL")}
    for name in ("ps_runtime_fixed", "ps_runtime_rotating"):
        role = name.split("_", 2)[2]
        record = role_by_name(summaries.get("ps_runtime", {}), role)
        offline_gates[name] = {"status": record.get("status", "FAIL")}
    offline_gates["p10_3_xsim"] = {
        "status": summaries.get("xsim", {}).get("status", "FAIL")
    }
    for name, result in offline_gates.items():
        if result.get("status") != "PASS" and f"offline gate failed: {name}" not in errors:
            errors.append(f"offline gate failed: {name}")
    build_evidence = {
        name: metadata(path) for name, path in SUMMARY_PATHS.items()
        if path.is_file()
    }
    baseline_names = {
        "p10_2_verify_existing", "p10_1r_verify_existing",
        "p10_verify_existing", "p8c_safety_verify_existing",
    }
    baseline = {
        "status": "PASS" if all(offline_gates.get(name, {}).get("status") == "PASS"
                                  for name in baseline_names) else "FAIL",
        "gates": sorted(baseline_names),
    }
    status = "PASS" if not errors else "FAIL"
    record = {
        "schema_version": 1,
        "test_id": "P10_3-IMMUTABLE-ARTIFACT-FREEZE",
        "status": status,
        "scope": p103.SCOPE,
        "branch": branch,
        "source_commit": source_commit,
        "goal_sha256": p103.GOAL_SHA256,
        "acceptance_eligible": status == "PASS",
        "source_tree_clean": all(item.get("source_worktree_dirty") is False
                                 for item in summaries.values()),
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "network_used": False,
        "allowed_hardware_stages": list(p103.STAGES),
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "expected_build_ids": {"fixed": "0x50333446", "rotating": "0x50333452"},
        "baseline_verification": baseline,
        "offline_gates": offline_gates,
        "artifacts": artifacts,
        "build_evidence": build_evidence,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "errors": errors,
    }
    FREEZE.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    md = GENERATED / "p10_3_artifact_freeze.md"
    lines = ["# P10.3 immutable artifact freeze", "", f"- Status: `{status}`",
             f"- Source commit: `{source_commit or 'NONE'}`",
             "- Hardware actions executed: `false`", "", "## Artifacts", ""]
    lines += [f"- `{item['role']}:{item['kind']}` — `{item['sha256']}` — `{item['path']}`"
              for item in artifacts]
    if errors:
        lines += ["", "## Errors", ""] + [f"- {error}" for error in errors]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_3_ARTIFACT_FREEZE={status}")
    print(f"P10_3_SOURCE_COMMIT={source_commit or 'NONE'}")
    print(f"P10_3_ARTIFACT_COUNT={len(artifacts)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
