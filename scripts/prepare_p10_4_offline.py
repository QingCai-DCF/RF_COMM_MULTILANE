#!/usr/bin/env python3
"""Generate P10.4 repository intake and immutable P10.3 closeout checks."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_4_repo_intake_raw"
GOAL = ROOT / "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md"
GOAL_SHA = "0098acc827d22ad8f72876f5551e70d8051452e0c81eb2bfe8986e142f47254f"
BRANCH = "p10.4/autonomous-4lane-hardening"
BASE_TAG = "p10.3-ax7020-stationary-4lane-closed"
PASS_TAG = "p10.3-ax7020-stationary-4lane-pass"
P10_3_EVIDENCE = "e64c04843d5d996f8d66d650fafaf3a43a2dd7dc"
P10_3_CLOSEOUT = "11a05992279717511527573012449b37787b9d6a"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run(name: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                            timeout=900, env={**os.environ, "NO_HARDWARE": "1",
                            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"})
    RAW.mkdir(parents=True, exist_ok=True)
    log = RAW / f"{name}.log"
    log.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"RETURN_CODE={result.returncode}\nSTDOUT_BEGIN\n{result.stdout}\nSTDOUT_END\n" +
        f"STDERR_BEGIN\n{result.stderr}\nSTDERR_END\n",
        encoding="utf-8", newline="\n",
    )
    return {"name": name, "status": "PASS" if result.returncode == 0 else "FAIL",
            "returncode": result.returncode,
            "log": log.relative_to(ROOT).as_posix(), "log_sha256": sha(log)}


def write_pair(name: str, title: str, payload: dict[str, Any]) -> None:
    base = GENERATED / name
    base.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [f"# {title}", "", f"- Status: `{payload['status']}`"]
    for key in ("branch", "head", "base_tag", "p10_3_evidence_commit",
                "p10_3_closeout_commit", "hardware_actions_executed"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    if payload.get("checks"):
        lines.extend(["", "| Check | Status |", "|---|---|"])
        lines.extend(f"| {item['name']} | {item['status']} |" for item in payload["checks"])
    base.with_suffix(".md").write_text("\n".join(lines) + "\n",
                                       encoding="utf-8", newline="\n")


def main() -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        print("P10_4_INTAKE_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED")
        return 2
    errors: list[str] = []
    if not GOAL.is_file() or sha(GOAL) != GOAL_SHA:
        errors.append("Goal hash mismatch")
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    if branch != BRANCH:
        errors.append(f"branch mismatch: {branch}")
    base_commit = git("rev-list", "-n", "1", BASE_TAG)
    pass_commit = git("rev-list", "-n", "1", PASS_TAG)
    if base_commit != P10_3_CLOSEOUT:
        errors.append("closed tag target mismatch")
    if pass_commit != "e647f066bbba8b36660e5f0bc43c79adc872c4c0":
        errors.append("pass tag target mismatch")
    for commit in (P10_3_EVIDENCE, P10_3_CLOSEOUT):
        if subprocess.run(["git", "merge-base", "--is-ancestor", commit, head],
                          cwd=ROOT).returncode != 0:
            errors.append(f"required P10.3 commit is not ancestor: {commit}")
    checks = [
        run("p10_3_verify_existing", ["python", "scripts/verify_p10_3_existing.py"]),
        run("p10_2_verify_existing", ["python", "scripts/verify_p10_2_existing.py"]),
        run("p10_1r_verify_existing", ["python", "scripts/verify_p10_1r_existing.py"]),
        run("p8c_safety_verify_existing", ["python", "scripts/verify_p8c_existing.py"]),
        run("state_requirements_consistency", ["python", "scripts/check_p8a_consistency.py", "--check"]),
    ]
    errors.extend(item["name"] for item in checks if item["status"] != "PASS")
    inputs = {
        name: {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}
        for name, path in {
            "PROJECT_CONSTRAINTS": ROOT / "PROJECT_CONSTRAINTS.txt",
            "AGENTS": ROOT / "AGENTS.md",
            "project_state": ROOT / "config/project_state.json",
            "requirements": ROOT / "config/project_requirements.yaml",
            "register_map": ROOT / "config/register_map/ir_axi_regs.yaml",
            "fixed_profile": ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
            "rotating_profile": ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
            "wiring": ROOT / "config/hardware/p10_3_actual_wiring.yaml",
            "module_inventory": ROOT / "config/hardware/tfdu_module_inventory.yaml",
            "goal": GOAL,
        }.items()
    }
    tools = {
        "python": platform.python_version(),
        "git": subprocess.check_output(["git", "--version"], text=True).strip(),
        "vivado": str(Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")),
        "xsdb": str(Path(r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat")),
    }
    payload = {
        "schema_version": 1, "test_id": "P10_4-REPO-INTAKE",
        "status": "PASS" if not errors else "FAIL", "branch": branch,
        "head": head, "base_tag": BASE_TAG, "base_commit": base_commit,
        "p10_3_evidence_commit": P10_3_EVIDENCE,
        "p10_3_closeout_commit": P10_3_CLOSEOUT,
        "git_status": git("status", "--short").splitlines(),
        "inputs": inputs, "tool_versions": tools, "checks": checks,
        "hardware_authorization": "GOAL_SUBMISSION_STANDING_AUTHORIZATION_NOT_YET_MATERIALIZED_AS_CURRENT_RUN",
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False, "errors": errors,
        "start_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_pair("p10_4_repo_intake", "P10.4 repository intake", payload)
    closeout = {
        "schema_version": 1, "test_id": "P10_4-CLOSE-001",
        "status": "PASS" if not any("tag" in item or "ancestor" in item for item in errors) else "FAIL",
        "branch": branch, "head": head, "base_tag": BASE_TAG,
        "pass_tag": PASS_TAG, "p10_3_evidence_commit": P10_3_EVIDENCE,
        "p10_3_closeout_commit": P10_3_CLOSEOUT,
        "pass_tag_target": pass_commit, "closed_tag_target": base_commit,
        "p10_3_raw_evidence_rewritten": False,
        "p10_3_scoped_pass_preserved": True,
        "hardware_actions_executed": False,
    }
    write_pair("p10_4_p10_3_closeout", "P10.4 P10.3 immutable closeout recheck", closeout)
    print(f"P10_4_REPO_INTAKE={payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
