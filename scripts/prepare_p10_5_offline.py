#!/usr/bin/env python3
"""Generate P10.5 repository intake and verify the immutable P10.4 baseline."""

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
P10_4_ROOT = ROOT.parent / "RF_COMM_MULTILANE_P10_4"
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_5_repo_intake_raw"
GOAL = ROOT / "goals/P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE_GOAL.md"
GOAL_SHA = "5c08e89917ffc18150e37f65ff29cf7c48f749d81033fe02a0d1bce772c23a36"
BRANCH = "p10.5/dual-direction-2plus2"
BASE_TAG = "p10.4-autonomous-4lane-hardening-closed"
BASE_COMMIT = "bcbe5b51469ac499fb0a17a89cb9f5a4bbda6676"
P10_4_FINAL = "7987e6385b65fa2c7ed7d3a008c1ecbdf323ffa8"
P10_4_ARTIFACT_SOURCE = "6ff17d33a0ea111fbd796899c49decbfa339e2c1"
P10_4_EVIDENCE = "f53d98252dfa85d73f35d49ebf5dc01323bcb4e7"
P10_4_AUDIT_SHA = "6c351c7f7fdcac9d1a2cead7548b940d0345c6e1cc7e48d7e3783c7c38e3c904"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run(name: str, command: list[str], timeout: int = 900,
        cwd: Path = ROOT) -> dict[str, Any]:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                            timeout=timeout, env={**os.environ, "NO_HARDWARE": "1",
                            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"})
    RAW.mkdir(parents=True, exist_ok=True)
    log = RAW / f"{name}.log"
    log.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"RETURN_CODE={result.returncode}\nSTDOUT_BEGIN\n{result.stdout}\nSTDOUT_END\n" +
        f"STDERR_BEGIN\n{result.stderr}\nSTDERR_END\n",
        encoding="utf-8", newline="\n")
    return {"name": name, "status": "PASS" if result.returncode == 0 else "FAIL",
            "returncode": result.returncode, "log": log.relative_to(ROOT).as_posix(),
            "log_sha256": sha(log)}


def write_pair(name: str, title: str, payload: dict[str, Any]) -> None:
    path = GENERATED / name
    path.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    lines = [f"# {title}", "", f"- Status: `{payload['status']}`"]
    for key in ("branch", "head", "base_tag", "base_commit",
                "hardware_actions_executed"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    if payload.get("checks"):
        lines += ["", "| Check | Status |", "|---|---|"]
        lines += [f"| {item['name']} | {item['status']} |" for item in payload["checks"]]
    path.with_suffix(".md").write_text("\n".join(lines) + "\n",
                                        encoding="utf-8", newline="\n")


def main() -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_5_INTAKE_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED")
        return 2
    errors: list[str] = []
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    base = git("rev-list", "-n", "1", BASE_TAG)
    if branch != BRANCH:
        errors.append(f"branch mismatch: {branch}")
    if base != BASE_COMMIT:
        errors.append(f"closed tag mismatch: {base}")
    if not GOAL.is_file() or sha(GOAL) != GOAL_SHA:
        errors.append("Goal hash mismatch")
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASE_COMMIT, head],
                      cwd=ROOT).returncode:
        errors.append("P10.4 closed tag is not an ancestor")
    checks = [
        run("p10_4_validate_existing",
            ["python", "scripts/finalize_p10_4_composite.py", "--validate-only"],
            cwd=P10_4_ROOT),
        run("p10_3_verify_existing", ["python", "scripts/verify_p10_3_existing.py"]),
        run("p10_2_verify_existing", ["python", "scripts/verify_p10_2_existing.py"]),
        run("p10_1r_verify_existing", ["python", "scripts/verify_p10_1r_existing.py"]),
        run("p8c_verify_existing", ["python", "scripts/verify_p8c_existing.py"]),
        run("state_requirements_consistency", ["python", "scripts/check_p8a_consistency.py", "--check"]),
    ]
    errors += [item["name"] for item in checks if item["status"] != "PASS"]
    files = {
        "PROJECT_CONSTRAINTS": ROOT / "PROJECT_CONSTRAINTS.txt",
        "AGENTS": ROOT / "AGENTS.md",
        "project_state": ROOT / "config/project_state.json",
        "requirements": ROOT / "config/project_requirements.yaml",
        "register_map": ROOT / "config/register_map/ir_axi_regs.yaml",
        "wiring": ROOT / "config/hardware/p10_3_actual_wiring.yaml",
        "module_inventory": ROOT / "config/hardware/tfdu_module_inventory.yaml",
        "fixed_profile": ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
        "rotating_profile": ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
        "p10_4_closeout": ROOT / "evidence/generated/p10_4_closeout_summary.json",
        "goal": GOAL,
    }
    inputs = {key: {"path": value.relative_to(ROOT).as_posix(), "sha256": sha(value)}
              for key, value in files.items()}
    payload = {
        "schema_version": 1, "test_id": "P10_5-REPO-INTAKE",
        "status": "PASS" if not errors else "FAIL", "branch": branch,
        "head": head, "base_tag": BASE_TAG, "base_commit": base,
        "p10_4_final_commit": P10_4_FINAL,
        "p10_4_artifact_source_commit": P10_4_ARTIFACT_SOURCE,
        "p10_4_evidence_checkpoint": P10_4_EVIDENCE,
        "source_audit_package_sha256": P10_4_AUDIT_SHA,
        "git_status": git("status", "--short").splitlines(),
        "inputs": inputs, "checks": checks,
        "tool_versions": {"python": platform.python_version(),
                          "git": subprocess.check_output(["git", "--version"], text=True).strip(),
                          "vivado": r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat",
                          "xsdb": r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat"},
        "current_authorization": "P10.5 Goal standing authorization; hardware materialization deferred until immutable artifact freeze",
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False, "errors": errors,
        "start_timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_pair("p10_5_repo_intake", "P10.5 repository intake", payload)
    closeout = json.loads((ROOT / "evidence/generated/p10_4_closeout_summary.json").read_text(encoding="utf-8"))
    closeout_recheck = {
        "schema_version": 1, "test_id": "P10_5-CLOSE-001-RECHECK",
        "status": "PASS" if closeout.get("status") == "PASS" and not errors else "FAIL",
        "p10_4_final_commit": P10_4_FINAL, "p10_4_evidence_checkpoint": P10_4_EVIDENCE,
        "two_plus_two_result": closeout["p10_4"]["two_plus_two"]["result"],
        "two_plus_two_capability": closeout["p10_4"]["two_plus_two"]["capability"],
        "two_plus_two_tx_executed": closeout["p10_4"]["two_plus_two"]["tx_executed"],
        "shutdown": closeout["p10_4"]["shutdown"],
        "frozen_evidence_rewritten": False, "hardware_actions_executed": False,
    }
    write_pair("p10_4_closeout", "P10.4 immutable closeout recheck", closeout_recheck)
    print(f"P10_5_REPO_INTAKE={payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
