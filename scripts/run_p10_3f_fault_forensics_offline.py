#!/usr/bin/env python3
"""Aggregate the P10.3F first-fault forensic offline evidence.

This command is deliberately incapable of connecting to hardware.  The full
XSIM suite and all three role-bound build summaries must already exist and
must bind the current clean source commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_3_fault_forensics_offline_raw"
SUMMARY_JSON = GENERATED / "p10_3_fault_forensics_offline.json"
SUMMARY_MD = GENERATED / "p10_3_fault_forensics_offline.md"
EXPECTED_BRANCH = "codex/p10.3-fault-forensics"
SUMMARY_PATHS = {
    "xsim": GENERATED / "p10_3_fault_forensics_xsim/summary.json",
    "functional": GENERATED / "p10_3_fault_forensics_functional_build_summary.json",
    "shutdown": GENERATED / "p10_3_fault_forensics_shutdown_build_summary.json",
    "ps_runtime": GENERATED / "p10_3_fault_forensics_ps_runtime_build_summary.json",
}
SOURCE_PATHS = (
    "config/register_map/ir_axi_regs.yaml",
    "config/safety/p10_3_fault_forensics.yaml",
    "config/performance/p10_3f_staircase.yaml",
    "config/project_requirements.yaml",
    "docs/design/P10_3_FIRST_FAULT_FORENSICS.md",
    "rtl/p10_fault_forensics.sv",
    "rtl/p9_optical_transport_core.sv",
    "rtl/p9_axi_dma_peripheral.sv",
    "scripts/archive_p10_fault_forensics.py",
    "scripts/hw/p10_3f_fault_forensics.tcl",
    "scripts/hw/p10_dual_xsdb_stage.tcl",
    "scripts/run_p10_3f_staircase_hardware.py",
    "scripts/run_p10_3f_fault_forensics_offline.py",
    "scripts/freeze_p10_3f_artifacts.py",
    "scripts/finalize_p10_3f_offline.py",
    "scripts/build_p10_ax7020_functional.py",
    "scripts/build_p10_ax7020_shutdown.py",
    "scripts/build_p10_ps_runtime.py",
    "scripts/run_p10_2_xsim.py",
    "scripts/vivado/build_p10_ax7020_functional.tcl",
    "sim/tb/tb_p10_2_4lane_suite.sv",
    "sim/tb/tb_p10_fault_forensics.sv",
    "sim/tb/tb_p10_forensic_safety_integration.sv",
    "tests/test_p10_3f_fault_forensics.py",
)
CHECKS = {
    "register_map_verify": [sys.executable, "scripts/generate_register_headers.py", "--verify"],
    "host_unit_tests": [sys.executable, "-m", "unittest", "-v", "tests.test_p10_3f_fault_forensics"],
    "requirement_traceability": [sys.executable, "scripts/generate_requirement_traceability.py", "--check"],
    "canonical_consistency": [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
    "no_hardware_static_scan": [sys.executable, "scripts/check_no_hardware_calls.py"],
    "python_compile": [
        sys.executable, "-m", "py_compile",
        "scripts/archive_p10_fault_forensics.py",
        "scripts/run_p10_3f_staircase_hardware.py",
        "scripts/run_p10_3f_fault_forensics_offline.py",
        "scripts/freeze_p10_3f_artifacts.py",
        "scripts/finalize_p10_3f_offline.py",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {rel(path)}")
    return value


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def run_check(name: str, command: list[str]) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "NO_HARDWARE": "1",
           "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"}
    try:
        result = subprocess.run(
            command, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=600, check=False,
        )
        output = result.stdout
        returncode = result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output = f"EXCEPTION={exc!r}\n"
        returncode = -1
    log = RAW / f"{name}.log"
    log.write_text(output, encoding="utf-8", errors="replace", newline="\n")
    return {
        "status": "PASS" if returncode == 0 else "FAIL",
        "command": command,
        "returncode": returncode,
        "log": metadata(log),
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
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if branch != EXPECTED_BRANCH:
        errors.append(f"branch mismatch: {branch}")
    missing = [item for item in SOURCE_PATHS if not (ROOT / item).is_file()]
    errors.extend(f"missing source input: {item}" for item in missing)
    source_dirty = bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--", *SOURCE_PATHS],
        cwd=ROOT, text=True,
    ))
    if source_dirty:
        errors.append("P10.3F source inputs were dirty")

    checks = {name: run_check(name, command) for name, command in CHECKS.items()}
    errors.extend(f"offline check failed: {name}" for name, result in checks.items()
                  if result["status"] != "PASS")

    summaries: dict[str, dict[str, Any]] = {}
    for name, path in SUMMARY_PATHS.items():
        try:
            summaries[name] = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name} summary unavailable: {exc}")
            continue
        summary = summaries[name]
        if summary.get("status") != "PASS":
            errors.append(f"{name} summary is not PASS")
        if summary.get("source_commit") != head:
            errors.append(f"{name} summary source commit mismatch")
        if summary.get("source_worktree_dirty") is not False:
            errors.append(f"{name} summary source inputs were dirty")
        if summary.get("hardware_actions_executed") is not False:
            errors.append(f"{name} summary reports hardware actions")

    xsim_ids = {
        item.get("test_id") for item in summaries.get("xsim", {}).get("results", [])
        if isinstance(item, dict) and item.get("status") == "PASS"
    }
    required_xsim = {
        "tb_p10_fault_forensics", "tb_p10_3_single_lane_ack_progress",
        "tb_p10_3_atomic_lane_migration",
        "tb_p10_forensic_safety_integration",
        "tb_4lane_dual_endpoint", "tb_p10_2_lane_count_elaboration",
    }
    if not required_xsim.issubset(xsim_ids):
        errors.append(f"required XSIM PASS set incomplete: {sorted(required_xsim - xsim_ids)}")

    config = (ROOT / "config/safety/p10_3_fault_forensics.yaml").read_text(
        encoding="utf-8"
    )
    staircase = (ROOT / "config/performance/p10_3f_staircase.yaml").read_text(
        encoding="utf-8"
    )
    if "manual_instrumentation_in_this_followup: OMITTED_BY_USER" not in config or \
            "oscilloscope: OMITTED_BY_USER" not in staircase:
        errors.append("manual-instrumentation exclusion is not explicit")

    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema_version": 1,
        "test_id": "P10_3F-FIRST-FAULT-FORENSICS-OFFLINE",
        "status": status,
        "scope": "P10_3_FIRST_FAULT_FORENSICS_OFFLINE_FOLLOWUP",
        "branch": branch,
        "source_commit": head,
        "source_worktree_dirty": source_dirty,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "manual_instrumentation": "OMITTED_BY_USER",
        "electrical_or_optical_measurement_claimed": False,
        "old_hardware_pass_inherited": False,
        "source_inputs": [metadata(ROOT / item) for item in SOURCE_PATHS if (ROOT / item).is_file()],
        "checks": checks,
        "build_evidence": {
            name: metadata(path) for name, path in SUMMARY_PATHS.items() if path.is_file()
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "errors": errors,
    }
    SUMMARY_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [
        "# P10.3F first-fault forensic offline evidence", "",
        f"- Status: `{status}`",
        f"- Source commit: `{head}`",
        "- Hardware actions executed: `false`",
        "- Manual instrumentation: `OMITTED_BY_USER`",
        "- Electrical/optical measurement claimed: `false`", "",
        "## Checks", "", "| Check | Status |", "|---|---|",
    ]
    lines.extend(f"| `{name}` | `{result['status']}` |" for name, result in checks.items())
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {error}" for error in errors])
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_3F_OFFLINE={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
