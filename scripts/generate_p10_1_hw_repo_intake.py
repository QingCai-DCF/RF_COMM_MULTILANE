#!/usr/bin/env python3
"""Generate the fail-closed P10.1 hardware-stage repository intake.

offline-build-only: tool discovery is limited to local version commands and
never connects to an XSCT/XSDB target or hardware server.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from p10_1_common import ROOT, rel, sha256, write_json, write_text


GOAL = Path(
    r"C:\Users\user\Downloads"
    r"\P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE_GOAL.md"
)
GOAL_SHA256 = (
    "b3d0ae793a89ba270ca72880fb4fa38bcb17ac7631f3fc650e2557963840f9d3"
)
BRANCH = "p10.1/hardware-performance-acceptance"
OFFLINE_TAG = "p10.1-offline-performance-ready"
OFFLINE_SOURCE = "ae942f0b5d9e9b4b7f5ced4751cc748c55b81183"
OFFLINE_EVIDENCE = "8c34d60f064b01b95dc9c35b664ffbe43efb0b1f"
OUTPUT_JSON = ROOT / "evidence/generated/p10_1_hw_repo_intake.json"
OUTPUT_MD = ROOT / "evidence/generated/p10_1_hw_repo_intake.md"
RAW_LOG = ROOT / "evidence/generated/p10_1_hw_repo_intake_commands.log"
VIVADO_VERSION_TCL = ROOT / "scripts/vivado/report_tool_version.tcl"

INPUTS = [
    "PROJECT_CONSTRAINTS.txt",
    "AGENTS.md",
    "config/project_state.json",
    "config/project_requirements.yaml",
    "config/register_map/ir_axi_regs.yaml",
    "config/performance/p10_1_measurement_contract.yaml",
    "config/performance/p10_1_pipeline.yaml",
    "config/performance/p10_1_streaming.yaml",
    "config/performance/p10_1_hardware_runtime.yaml",
    "config/hardware/p10_active_wiring.yaml",
    "config/hardware/p10_1_ax7020_pl_activity_leds.yaml",
    "board_profiles/ax7020_fixed_2lane/profile.yaml",
    "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
    "board_profiles/ax7020_rotating_2lane/profile.yaml",
    "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
]


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True
    ).strip()


def is_ancestor(ancestor: str, descendant: str = "HEAD") -> bool:
    return (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", ancestor, descendant],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        == 0
    )


def tag_record(name: str) -> dict[str, str]:
    return {
        "name": name,
        "object_type": git("cat-file", "-t", name),
        "object": git("rev-parse", name),
        "target": git("rev-list", "-n", "1", name),
    }


def run(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    try:
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
        return {
            "name": name,
            "command": subprocess.list2cmdline(command),
            "return_code": result.returncode,
            "status": "PASS" if result.returncode == 0 else "FAIL",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "name": name,
            "command": subprocess.list2cmdline(command),
            "return_code": None,
            "status": "FAIL",
            "stdout": "",
            "stderr": str(exc),
        }


def verify_offline_checkpoint() -> dict[str, Any]:
    errors: list[str] = []
    try:
        raw = subprocess.check_output(
            [
                "git",
                "show",
                f"{OFFLINE_EVIDENCE}:evidence/generated/p10_1_final_summary.json",
            ],
            cwd=ROOT,
        )
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("status") != "PASS":
            errors.append("frozen P10.1 final summary is not PASS")
    except (subprocess.CalledProcessError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raw = b""
        payload = {}
        errors.append(f"frozen P10.1 summary unreadable: {exc}")
    return {
        "name": "p10_1_offline_verify_existing",
        "status": "PASS" if not errors else "FAIL",
        "checkpoint": OFFLINE_EVIDENCE,
        "path": "evidence/generated/p10_1_final_summary.json",
        "git_blob_sha256": (
            __import__("hashlib").sha256(raw).hexdigest() if raw else None
        ),
        "test_id": payload.get("test_id"),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-baselines", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    goal_hash = sha256(GOAL) if GOAL.is_file() else None
    if goal_hash != GOAL_SHA256:
        errors.append("hardware Goal is missing or has the wrong SHA256")
    branch = git("branch", "--show-current")
    if branch != BRANCH:
        errors.append(f"wrong branch: {branch}")
    offline = tag_record(OFFLINE_TAG)
    if offline["object_type"] != "tag" or offline["target"] != OFFLINE_EVIDENCE:
        errors.append("offline tag is not the expected annotated tag/target")
    if not is_ancestor(OFFLINE_SOURCE, OFFLINE_EVIDENCE):
        errors.append("offline source commit is not an ancestor of its evidence checkpoint")
    for tag in (
        "p10-ax7020-dual-node-2lane-pass",
        "p10-ax7020-dual-node-2lane-closed",
    ):
        if tag_record(tag)["object_type"] != "tag":
            errors.append(f"{tag} is not annotated")
    if not is_ancestor(OFFLINE_EVIDENCE):
        errors.append("offline evidence checkpoint is not an ancestor of HEAD")

    baseline = [verify_offline_checkpoint()]
    commands = [
        (
            "p10_verify_existing",
            [sys.executable, "scripts/verify_p10_existing.py", "--json-summary"],
            900,
        ),
        (
            "p9_verify_existing",
            [sys.executable, "scripts/verify_p9_existing.py", "--json-summary"],
            900,
        ),
        (
            "p8e_verify_existing",
            [
                sys.executable,
                "scripts/run_p8e_dual_target_gate.py",
                "--verify-existing",
                "--json-summary",
            ],
            900,
        ),
        (
            "p8c_safety_verify_existing",
            [sys.executable, "scripts/verify_p8c_existing.py", "--json-summary"],
            600,
        ),
        (
            "state_requirements_consistency",
            [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
            600,
        ),
        (
            "no_hardware_static_scan",
            [sys.executable, "scripts/check_no_hardware_calls.py"],
            300,
        ),
    ]
    if not args.skip_baselines:
        baseline.extend(run(*item) for item in commands)
    for item in baseline:
        if item["status"] != "PASS":
            errors.append(f"baseline failed: {item['name']}")

    log_lines: list[str] = []
    for item in baseline:
        log_lines.extend(
            [
                f"NAME={item['name']}",
                f"STATUS={item['status']}",
                f"COMMAND={item.get('command', 'git show checkpoint evidence')}",
                "STDOUT_BEGIN",
                item.get("stdout", ""),
                "STDOUT_END",
                "STDERR_BEGIN",
                item.get("stderr", ""),
                "STDERR_END",
            ]
        )
    write_text(RAW_LOG, "\n".join(log_lines))

    input_records = []
    for name in INPUTS:
        path = ROOT / name
        if not path.is_file():
            errors.append(f"missing canonical input: {name}")
            continue
        input_records.append(
            {"path": name, "sha256": sha256(path), "bytes": path.stat().st_size}
        )

    tool_commands = {
        "python": [sys.executable, "--version"],
        "vivado": [
            r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
            "-mode",
            "batch",
            "-nolog",
            "-nojournal",
            "-notrace",
            "-source",
            str(VIVADO_VERSION_TCL),
        ],
        "xsct": [r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat", "-version"],
    }
    tools: dict[str, Any] = {}
    for name, command in tool_commands.items():
        record = run(name, command, 60)
        tools[name] = {
            "path": command[0],
            "status": record["status"],
            "version": (record["stdout"] + record["stderr"]).splitlines()[:8],
        }
        if record["status"] != "PASS":
            errors.append(f"tool unavailable: {name}")

    status_lines = git("status", "--short").splitlines()
    payload = {
        "schema_version": 1,
        "test_id": "P10_1-HW-REPOSITORY-INTAKE",
        "status": "PASS" if not errors else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "worktree": str(ROOT),
        "branch": branch,
        "head": git("rev-parse", "HEAD"),
        "git_status": status_lines,
        "offline_base_tag": offline,
        "offline_source_commit": OFFLINE_SOURCE,
        "offline_evidence_checkpoint": OFFLINE_EVIDENCE,
        "offline_evidence_is_ancestor": is_ancestor(OFFLINE_EVIDENCE),
        "p10_tags": {
            "pass": tag_record("p10-ax7020-dual-node-2lane-pass"),
            "closed": tag_record("p10-ax7020-dual-node-2lane-closed"),
        },
        "goal": {"path": str(GOAL), "sha256": goal_hash},
        "canonical_inputs": input_records,
        "tools": tools,
        "environment": {
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "network_used": False,
        "baseline_rechecks": [
            {
                key: value
                for key, value in item.items()
                if key not in {"stdout", "stderr"}
            }
            for item in baseline
        ],
        "baseline_log": {
            "path": rel(RAW_LOG),
            "sha256": sha256(RAW_LOG),
        },
        "errors": errors,
    }
    write_json(OUTPUT_JSON, payload)
    write_text(
        OUTPUT_MD,
        "\n".join(
            [
                "# P10.1 hardware-stage repository intake",
                "",
                f"- Status: `{payload['status']}`",
                f"- Branch: `{branch}`",
                f"- HEAD at intake: `{payload['head']}`",
                f"- Offline tag target: `{offline['target']}`",
                f"- Goal SHA256: `{goal_hash}`",
                "- NO_HARDWARE: `1`",
                "- CURRENT_RUN_HARDWARE_AUTHORIZATION: `false`",
                "- Hardware actions executed: `false`",
                "",
                "The P10.1 offline checkpoint, P10, P9, P8E, P8C safety, "
                "state/requirements consistency, and no-hardware scan are "
                "rechecked without contacting hardware.",
                "",
                f"Machine-readable evidence: `{rel(OUTPUT_JSON)}`",
            ]
        ),
    )
    print(f"P10_1_HW_REPO_INTAKE={payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
