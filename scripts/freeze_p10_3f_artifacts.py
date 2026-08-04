#!/usr/bin/env python3
"""Validate and freeze the immutable P10.3F offline artifact bundle."""

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


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_3_fault_forensics_freeze_raw"
FREEZE = GENERATED / "p10_3_fault_forensics_artifact_freeze.json"
FREEZE_MD = GENERATED / "p10_3_fault_forensics_artifact_freeze.md"
EXPECTED_BRANCH = "codex/p10.3-fault-forensics"
GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
SUMMARY_PATHS = {
    "functional": GENERATED / "p10_3_fault_forensics_functional_build_summary.json",
    "shutdown": GENERATED / "p10_3_fault_forensics_shutdown_build_summary.json",
    "ps_runtime": GENERATED / "p10_3_fault_forensics_ps_runtime_build_summary.json",
    "xsim": GENERATED / "p10_3_fault_forensics_xsim/summary.json",
    "offline": GENERATED / "p10_3_fault_forensics_offline.json",
}
GATE_COMMANDS = {
    "state_requirements_consistency": [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
    "requirement_traceability": [sys.executable, "scripts/generate_requirement_traceability.py", "--check"],
    "register_map_verify": [sys.executable, "scripts/generate_register_headers.py", "--verify"],
    "no_hardware_static_scan": [sys.executable, "scripts/check_no_hardware_calls.py"],
    "p8c_safety_regression": [sys.executable, "scripts/verify_p8c_existing.py"],
    "p10_2_scoped_regression": [sys.executable, "scripts/verify_p10_2_existing.py"],
}
EXPECTED_BUILD_IDS = {"fixed": "0x50334646", "rotating": "0x50334652"}


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
        raise ValueError(f"JSON root is not an object: {rel(path)}")
    return value


def run_gate(name: str, command: list[str]) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "NO_HARDWARE": "1",
           "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"}
    try:
        result = subprocess.run(
            command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=600, check=False,
        )
        output, returncode = result.stdout, result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output, returncode = f"EXCEPTION={exc!r}\n", -1
    log = RAW / f"{name}.log"
    log.write_text(output, encoding="utf-8", errors="replace", newline="\n")
    return {
        "status": "PASS" if returncode == 0 else "FAIL",
        "command": command, "returncode": returncode, "log": metadata(log),
    }


def role_by_name(summary: dict[str, Any], role: str) -> dict[str, Any]:
    matches = [item for item in summary.get("roles", [])
               if isinstance(item, dict) and item.get("role") == role]
    if len(matches) != 1:
        raise ValueError(f"exactly one {role} role record required")
    return matches[0]


def artifact_record(role: str, kind: str, item: dict[str, Any],
                    source_commit: str) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    expected_parent = (
        ROOT / "artifacts/p10_3_fault_forensics" / source_commit / item["sha256"]
    ).resolve()
    if path.parent != expected_parent:
        raise ValueError(f"{role}/{kind} is not source-commit/SHA content addressed")
    if not path.is_file() or path.stat().st_size != item.get("bytes") or \
            sha256(path) != item.get("sha256"):
        raise ValueError(f"{role}/{kind} artifact hash/size mismatch")
    if item.get("read_only") is not True:
        raise ValueError(f"{role}/{kind} is not declared read-only")
    return {"role": role, "kind": kind, **metadata(path), "read_only": True}


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
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if branch != EXPECTED_BRANCH:
        errors.append(f"branch mismatch: {branch}")

    summaries: dict[str, dict[str, Any]] = {}
    for name, path in SUMMARY_PATHS.items():
        try:
            summaries[name] = load(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name} summary unavailable: {exc}")
    commits = {str(item.get("source_commit", "")) for item in summaries.values()}
    source_commit = next(iter(commits), "") if len(commits) == 1 else ""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        errors.append(f"summaries do not bind one source commit: {sorted(commits)}")
    elif source_commit != head:
        errors.append(f"HEAD {head} differs from source commit {source_commit}")
    for name, summary in summaries.items():
        if summary.get("status") != "PASS":
            errors.append(f"{name} summary is not PASS")
        if summary.get("source_worktree_dirty") is not False:
            errors.append(f"{name} summary source inputs were dirty")
        if summary.get("hardware_actions_executed") is not False:
            errors.append(f"{name} summary executed hardware actions")

    artifacts: list[dict[str, Any]] = []
    if not errors:
        try:
            for role in ("fixed", "rotating"):
                functional = role_by_name(summaries["functional"], role)
                shutdown = role_by_name(summaries["shutdown"], role)
                runtime = role_by_name(summaries["ps_runtime"], role)
                markers = functional.get("markers", {})
                expected_markers = {
                    "P10_PL_BUILD_ID": EXPECTED_BUILD_IDS[role],
                    "P10_FIRST_FAULT_FORENSICS": "true",
                    "P10_FORENSIC_SNAPSHOT_WORDS": "64",
                    "P10_FORENSIC_EVENT_DEPTH": "256",
                    "P10_FORENSIC_EVENT_WORDS": "8",
                    "P10_FORENSIC_RESET_POLICY": "NO_FUNCTIONAL_RESET",
                    "P10_FORENSIC_BRAM_INFERRED": "true",
                }
                for key, expected in expected_markers.items():
                    if markers.get(key) != expected:
                        raise ValueError(f"{role} marker {key} mismatch")
                artifacts.extend([
                    artifact_record(role, "shutdown_bitstream", shutdown["artifact"], source_commit),
                    artifact_record(role, "functional_bitstream", functional["artifacts"]["bitstream"], source_commit),
                    artifact_record(role, "xsa", functional["artifacts"]["xsa"], source_commit),
                    artifact_record(role, "bsp", runtime["artifacts"]["bsp"], source_commit),
                    artifact_record(role, "elf", runtime["artifacts"]["elf"], source_commit),
                ])
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"artifact extraction failed: {exc}")

    gates = {name: run_gate(name, command) for name, command in GATE_COMMANDS.items()}
    errors.extend(f"offline gate failed: {name}" for name, result in gates.items()
                  if result["status"] != "PASS")
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema_version": 1,
        "test_id": "P10_3F-IMMUTABLE-ARTIFACT-FREEZE",
        "status": status,
        "scope": "P10_3_FIRST_FAULT_FORENSICS_OFFLINE_FOLLOWUP",
        "branch": branch,
        "source_commit": source_commit,
        "goal_sha256": GOAL_SHA256,
        "acceptance_eligible": status == "PASS",
        "eligibility_scope": "NEW_ARTIFACT_CURRENT_RUN_AUTHORIZATION_ONLY",
        "source_tree_clean": all(item.get("source_worktree_dirty") is False
                                 for item in summaries.values()),
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "manual_instrumentation": "OMITTED_BY_USER",
        "old_hardware_pass_inherited": False,
        "allowed_hardware_stages": ["staircase", "formal"],
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "expected_build_ids": EXPECTED_BUILD_IDS,
        "shutdown_policy": {
            "shutdown_before": True,
            "archive_before_independent_shutdown": True,
            "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
            "verify_both_shutdown_markers": True,
            "clear_frozen_capture_before_shutdown_program": False,
        },
        "offline_gates": gates,
        "artifacts": artifacts,
        "build_evidence": {
            name: metadata(path) for name, path in SUMMARY_PATHS.items() if path.is_file()
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "errors": errors,
    }
    FREEZE.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [
        "# P10.3F immutable artifact freeze", "", f"- Status: `{status}`",
        f"- Source commit: `{source_commit or 'NONE'}`",
        "- Hardware actions executed: `false`",
        "- Old hardware PASS inherited: `false`",
        "- Manual instrumentation: `OMITTED_BY_USER`", "", "## Artifacts", "",
    ]
    lines.extend(
        f"- `{item['role']}:{item['kind']}` — `{item['sha256']}` — `{item['path']}`"
        for item in artifacts
    )
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {error}" for error in errors])
    FREEZE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_3F_ARTIFACT_FREEZE={status}")
    print(f"P10_3F_SOURCE_COMMIT={source_commit or 'NONE'}")
    print(f"P10_3F_ARTIFACT_COUNT={len(artifacts)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
