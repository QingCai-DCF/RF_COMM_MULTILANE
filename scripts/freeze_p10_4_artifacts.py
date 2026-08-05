#!/usr/bin/env python3
"""Validate and freeze the immutable P10.4 artifact bundle offline."""

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
RAW = GENERATED / "p10_4_artifact_freeze_raw"
FREEZE = GENERATED / "p10_4_artifact_freeze.json"
FREEZE_MD = GENERATED / "p10_4_artifact_freeze.md"
BRANCH = "p10.4/autonomous-4lane-hardening"
GOAL_SHA256 = "0098acc827d22ad8f72876f5551e70d8051452e0c81eb2bfe8986e142f47254f"
SCOPE = "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT"
EXPECTED_BUILD = {"fixed": "0x50343446", "rotating": "0x50343452"}
SUMMARIES = {
    "functional": GENERATED / "p10_4_functional_build_summary.json",
    "shutdown": GENERATED / "p10_4_shutdown_build_summary.json",
    "ps_runtime": GENERATED / "p10_4_ps_runtime_build_summary.json",
    "xsim": GENERATED / "p10_4_xsim/summary.json",
}
OFFLINE_INPUTS = {
    "performance_model": GENERATED / "p10_4_model_reconciliation_offline.json",
    "performance_config": ROOT / "config/performance/p10_4_hardening.yaml",
    "register_map": ROOT / "config/register_map/ir_axi_regs.yaml",
    "goal": ROOT / "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md",
}
TCLSH = Path(r"D:\Xilinx\Vivado\2023.1\tps\win64\git-2.16.2\mingw64\bin\tclsh.exe")
GATES = {
    "runner_unit": [sys.executable, "-m", "unittest", "tests.test_p10_4_hardware"],
    "tcl_complete": [str(TCLSH), "scripts/hw/check_tcl_complete.tcl",
                     "scripts/hw/p10_dual_xsdb_stage.tcl",
                     "scripts/hw/p10_3f_fault_forensics.tcl",
                     "scripts/hw/p10_program_dual_shutdown.tcl"],
    "forensic_tcl_selftest": [str(TCLSH), "scripts/hw/p10_3f_fault_forensics.tcl",
                              "selftest"],
    "register_map": [sys.executable, "scripts/generate_register_headers.py", "--verify"],
    "model": [sys.executable, "scripts/model_p10_4.py", "--check"],
    "p10_3_baseline": [sys.executable, "scripts/verify_p10_3_existing.py"],
    "p10_2_baseline": [sys.executable, "scripts/verify_p10_2_existing.py"],
    "p10_1r_baseline": [sys.executable, "scripts/verify_p10_1r_existing.py"],
    "p10_frozen": [sys.executable, "scripts/verify_p10_frozen_existing.py"],
    "p8c_safety": [sys.executable, "scripts/verify_p8c_existing.py"],
    "state_requirements": [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
    "traceability": [sys.executable, "scripts/generate_requirement_traceability.py", "--check"],
    "no_hardware_static": [sys.executable, "scripts/check_no_hardware_calls.py"],
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
        raise ValueError(f"non-object JSON: {path}")
    return value


def run_gate(name: str, command: list[str]) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            command, cwd=ROOT, env={**os.environ, "NO_HARDWARE": "1",
                                    "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
            text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=1200, check=False,
        )
        output, returncode = result.stdout, result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output, returncode = f"EXCEPTION={exc!r}\n", -1
    log = RAW / f"{name}.log"
    log.write_text(output, encoding="utf-8", newline="\n")
    return {"status": "PASS" if returncode == 0 else "FAIL",
            "command": command, "returncode": returncode, "log": metadata(log)}


def role(summary: dict[str, Any], name: str) -> dict[str, Any]:
    found = [item for item in summary.get("roles", [])
             if isinstance(item, dict) and item.get("role") == name]
    if len(found) != 1:
        raise ValueError(f"exactly one {name} role required")
    return found[0]


def artifact(role_name: str, kind: str, item: dict[str, Any],
             source_commit: str) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    expected = (ROOT / "artifacts/p10_4" / source_commit / item["sha256"]).resolve()
    if path.parent != expected:
        raise ValueError(f"{role_name}:{kind} is not source/SHA content addressed")
    if not path.is_file() or path.stat().st_size != item.get("bytes") or \
            sha256(path) != item.get("sha256") or item.get("read_only") is not True:
        raise ValueError(f"{role_name}:{kind} hash/size/read-only mismatch")
    return {"role": role_name, "kind": kind, **metadata(path), "read_only": True}


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        errors.append("offline environment gates are not set")
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    if branch != BRANCH:
        errors.append(f"branch mismatch: {branch}")
    summaries: dict[str, dict[str, Any]] = {}
    for name, path in SUMMARIES.items():
        try:
            summaries[name] = load(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name} summary unavailable: {exc}")
    commits = {str(item.get("source_commit", "")) for item in summaries.values()}
    source_commit = next(iter(commits), "") if len(commits) == 1 else ""
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or source_commit != head:
        errors.append(f"build summaries/HEAD source mismatch: {sorted(commits)} / {head}")
    for name, summary in summaries.items():
        if summary.get("status") != "PASS":
            errors.append(f"{name} summary is not PASS")
        if summary.get("source_worktree_dirty") is not False:
            errors.append(f"{name} source inputs were dirty")
        if summary.get("hardware_actions_executed") is not False:
            errors.append(f"{name} executed hardware")
    offline_inputs: dict[str, dict[str, Any]] = {}
    for name, path in OFFLINE_INPUTS.items():
        try:
            offline_inputs[name] = metadata(path)
        except OSError as exc:
            errors.append(f"offline input unavailable: {name}: {exc}")
    try:
        model = load(OFFLINE_INPUTS["performance_model"])
        if model.get("status") != "PASS" or model.get("source_commit") != source_commit:
            errors.append("offline performance model source/status mismatch")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"offline performance model unavailable: {exc}")
    artifacts: list[dict[str, Any]] = []
    if not errors:
        try:
            for role_name in ("fixed", "rotating"):
                function = role(summaries["functional"], role_name)
                shutdown = role(summaries["shutdown"], role_name)
                runtime = role(summaries["ps_runtime"], role_name)
                markers = function.get("markers", {})
                required = {
                    "P10_CAMPAIGN": "p10_4",
                    "P10_PL_BUILD_ID": EXPECTED_BUILD[role_name],
                    "P10_FUNCTIONAL_BUILD": "PASS", "P10_WNS_NS": None,
                    "P10_WHS_NS": None, "P10_TNS_NS": "0.0",
                    "P10_CDC_CRITICAL_COUNT": "0", "P10_DRC_CRITICAL_COUNT": "0",
                    "P10_DRC_ERROR_COUNT": "0", "P10_REQP_1839_COUNT": "0",
                    "P10_RESOURCE_LIMITS_PASS": "1",
                    "P10_FIRST_FAULT_FORENSICS": "true",
                    "P10_FORENSIC_BRAM_INFERRED": "true",
                    "P10_FORENSIC_SNAPSHOT_WORDS": "64",
                    "P10_FORENSIC_EVENT_DEPTH": "256",
                    "P10_FORENSIC_EVENT_WORDS": "8",
                    "P10_FORENSIC_RESET_POLICY": "NO_FUNCTIONAL_RESET",
                }
                for key, value in required.items():
                    if key not in markers or (value is not None and markers[key] != value):
                        raise ValueError(f"{role_name} marker {key} mismatch")
                if float(markers["P10_WNS_NS"]) < 0 or float(markers["P10_WHS_NS"]) < 0:
                    raise ValueError(f"{role_name} negative timing")
                artifacts.extend((
                    artifact(role_name, "shutdown_bitstream", shutdown["artifact"], source_commit),
                    artifact(role_name, "functional_bitstream", function["artifacts"]["bitstream"], source_commit),
                    artifact(role_name, "xsa", function["artifacts"]["xsa"], source_commit),
                    artifact(role_name, "bsp", runtime["artifacts"]["bsp"], source_commit),
                    artifact(role_name, "elf", runtime["artifacts"]["elf"], source_commit),
                ))
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"artifact extraction failed: {exc}")
    gates = {name: run_gate(name, command) for name, command in GATES.items()}
    errors.extend(f"offline gate failed: {name}" for name, item in gates.items()
                  if item["status"] != "PASS")
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema_version": 1, "test_id": "P10_4-IMMUTABLE-ARTIFACT-FREEZE",
        "status": status, "scope": SCOPE,
        "branch": branch, "source_commit": source_commit,
        "goal_sha256": GOAL_SHA256, "acceptance_eligible": status == "PASS",
        "source_tree_clean": all(
            item.get("source_worktree_dirty") is False for item in summaries.values()
        ),
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False, "old_hardware_pass_inherited": False,
        "automation_only": True, "user_hold_points": 0,
        "maximum_lane_mask": 15, "maximum_single_formal_run_seconds": 1800,
        "maximum_aggregate_command_bytes": 128 << 20,
        "expected_build_ids": EXPECTED_BUILD,
        "register_map": {"version": "0x0A000004", "hash_low": "0xBCFECB39"},
        "shutdown_policy": {
            "shutdown_before_every_stage": True,
            "archive_before_independent_shutdown": True,
            "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
            "verify_both_shutdown_markers": True,
            "clear_frozen_capture_before_shutdown_program": False,
        },
        "allowed_hardware_stages": __import__("run_p10_4_hardware").STAGES,
        "offline_inputs": offline_inputs,
        "artifacts": artifacts, "offline_gates": gates,
        "build_evidence": {name: metadata(path) for name, path in SUMMARIES.items()
                           if path.is_file()},
        "errors": errors, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    FREEZE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    lines = ["# P10.4 immutable artifact freeze", "", f"- Status: `{status}`",
             f"- Source commit: `{source_commit or 'NONE'}`",
             "- Hardware actions executed: `false`", "", "## Artifacts", ""]
    lines.extend(f"- `{item['role']}:{item['kind']}` `{item['sha256']}` `{item['path']}`"
                 for item in artifacts)
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {item}" for item in errors])
    FREEZE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_4_ARTIFACT_FREEZE={status}")
    print(f"P10_4_SOURCE_COMMIT={source_commit or 'NONE'}")
    print(f"P10_4_ARTIFACT_COUNT={len(artifacts)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
