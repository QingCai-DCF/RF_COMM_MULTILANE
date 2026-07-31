#!/usr/bin/env python3
"""Execute or verify the complete P10.1 offline engineering checkpoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from p10_1_common import RAW, ROOT, rel, write_json, write_text


LEDGER = RAW / "p10_1_regression_commands.json"
GATE_LOG_ROOT = RAW / "offline_gate"


def execute(
    name: str,
    command: list[str],
    timeout: int,
) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        env={
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
    )
    log = GATE_LOG_ROOT / f"{name}.log"
    write_text(
        log,
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + f"RETURN_CODE={result.returncode}\n"
        + "STDOUT_BEGIN\n" + result.stdout + "STDOUT_END\n"
        + "STDERR_BEGIN\n" + result.stderr + "STDERR_END",
    )
    return {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "return_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "log": rel(log),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    del args.allow_skips, args.no_cache
    GATE_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    commands: list[dict[str, Any]] = []

    def run(name: str, command: list[str], timeout: int = 300) -> bool:
        record = execute(name, command, timeout)
        commands.append(record)
        print(f"{name}={record['status']}")
        return record["status"] == "PASS"

    verify = args.verify_existing
    run(
        "config_generation",
        [sys.executable, "scripts/generate_p10_1_config.py", "--check" if verify else "--write"],
    )
    run("historical_recompute", [sys.executable, "scripts/recompute_p10_performance.py"])
    run(
        "finalizer_unit_tests",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/p10_1",
            "-p",
            "test_*.py",
            "-v",
        ],
    )
    run(
        "pipeline_model",
        [
            sys.executable,
            "scripts/model_p10_1_dual_node_pipeline.py",
            "--quick" if args.quick else "--full",
        ],
        600,
    )
    software = [sys.executable, "scripts/build_p10_1_software.py"]
    if verify:
        software.append("--verify-existing")
    run("software_build", software, 300)
    xsim = [sys.executable, "scripts/run_p10_1_xsim.py"]
    if verify:
        xsim.append("--verify-existing")
    run("xsim", xsim, 600)
    build = [sys.executable, "scripts/build_p10_1_ax7020.py"]
    if verify or args.quick:
        build.append("--reuse-existing")
    run("ax7020_dual_build", build, 3600)
    run(
        "hardware_runner_dry_run",
        [sys.executable, "scripts/run_p10_1_hardware_performance.py"],
    )
    run("p11_readiness", [sys.executable, "scripts/generate_p10_1_readiness.py"])

    # Canonical state is updated only after every substantive offline artifact
    # exists. The updater keeps real hardware performance and P11 pending.
    run(
        "requirements_state_update",
        [sys.executable, "scripts/update_p10_1_requirements_state.py", "--write"],
    )
    run(
        "project_status_generation",
        [sys.executable, "scripts/generate_project_status.py", "--write"],
    )
    run(
        "requirement_traceability_generation",
        [sys.executable, "scripts/generate_requirement_traceability.py", "--write"],
    )
    intake = [sys.executable, "scripts/generate_p10_1_intake.py"]
    if verify:
        intake.append("--verify-existing")
    run("repo_intake", intake, 600)

    run(
        "p10_verify_existing",
        [sys.executable, "scripts/verify_p10_existing.py", "--json-summary"],
        600,
    )
    run(
        "p9_verify_existing",
        [sys.executable, "scripts/verify_p9_existing.py", "--json-summary"],
        600,
    )
    run(
        "p8e_verify_existing",
        [
            sys.executable,
            "scripts/run_p8e_dual_target_gate.py",
            "--verify-existing",
            "--json-summary",
        ],
        600,
    )
    run(
        "p8c_verify_existing",
        [sys.executable, "scripts/verify_p8c_existing.py", "--json-summary"],
    )
    run(
        "p8c_current_unit_regression",
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/p8c",
            "-p",
            "test_*.py",
            "-v",
        ],
        600,
    )
    run(
        "p8c_current_static_regression",
        [sys.executable, "scripts/check_p8c_safety_static.py", "--json"],
        600,
    )
    run(
        "register_map_consistency",
        [sys.executable, "scripts/generate_register_headers.py", "--verify"],
    )
    run(
        "p8a_state_requirements_consistency",
        [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
        600,
    )
    run(
        "no_hardware_static_scan",
        [sys.executable, "scripts/check_no_hardware_calls.py"],
    )
    run("git_diff_check", ["git", "diff", "--check"])

    write_json(
        LEDGER,
        {
            "schema_version": 1,
            "hardware_actions_executed": False,
            "current_run_hardware_authorization": False,
            "commands": commands,
        },
    )
    final_ok = run(
        "final_evidence",
        [sys.executable, "scripts/generate_p10_1_final_evidence.py"],
    )
    failures = [item["name"] for item in commands if item["status"] != "PASS"]
    status = "PASS" if not failures and final_ok else "FAIL"
    summary = {
        "status": status,
        "command_count": len(commands),
        "failures": failures,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "final_summary": "evidence/generated/p10_1_final_summary.json",
    }
    print(f"P10_1_OFFLINE_GATE={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
