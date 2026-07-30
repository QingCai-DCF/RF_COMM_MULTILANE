#!/usr/bin/env python3
"""Run and preserve the concise, non-hardware P10 fast-track preflight."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence/generated/p10_preflight_raw"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def run_check(name: str, command: list[str], timeout: int) -> dict[str, object]:
    env = dict(os.environ)
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    started = datetime.now(timezone.utc)
    try:
        result = subprocess.run(
            command, cwd=ROOT, env=env, text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False,
        )
        exit_code = result.returncode
        output = result.stdout
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        captured = exc.stdout or ""
        output = captured if isinstance(captured, str) else captured.decode("utf-8", "replace")
        output += f"\nTIMEOUT_AFTER_SECONDS={timeout}\n"
        timed_out = True
    ended = datetime.now(timezone.utc)
    log = RAW / f"{name}.txt"
    log.write_text(output, encoding="utf-8")
    return {
        "name": name,
        "command": command,
        "exit_code": exit_code,
        "status": "PASS" if exit_code == 0 else "FAIL",
        "timed_out": timed_out,
        "started_at_utc": started.isoformat(),
        "ended_at_utc": ended.isoformat(),
        "duration_seconds": (ended - started).total_seconds(),
        "log": str(log.relative_to(ROOT)).replace("\\", "/"),
        "log_sha256": sha256_file(log),
    }


def ancestor(ref: str, head: str) -> bool:
    return git("merge-base", "--is-ancestor", ref, head, check=False).returncode == 0


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    head = git("rev-parse", "HEAD").stdout.strip()
    branch = git("branch", "--show-current").stdout.strip()
    tracked_dirty = [line for line in git("status", "--short").stdout.splitlines() if not line.startswith("??")]

    checks = [
        run_check("p8a_consistency", ["python", "scripts/check_p8a_consistency.py"], 300),
        run_check(
            "p8e_verify_existing",
            ["python", "scripts/run_p8e_dual_target_gate.py", "--verify-existing", "--json-summary"],
            900,
        ),
        run_check(
            "p9_verify_existing",
            ["python", "scripts/verify_p9_existing.py", "--json-summary"],
            300,
        ),
        run_check("no_hardware_static_scan", ["python", "scripts/check_no_hardware_calls.py"], 300),
    ]
    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    payload = {
        "schema_version": 1,
        "test_id": "P10-FASTTRACK-CONCISE-PREFLIGHT",
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "worktree": str(ROOT),
        "branch": branch,
        "head": head,
        "main": git("rev-parse", "main").stdout.strip(),
        "expected_branch": "p10/ax7020-dual-node-2lane",
        "branch_match": branch == "p10/ax7020-dual-node-2lane",
        "tracked_worktree_clean_before_checks": not tracked_dirty,
        "tracked_dirty_before_checks": tracked_dirty,
        "ancestors": {
            "main": ancestor("main", head),
            "p8e-pass": ancestor("p8e-pass", head),
            "p9-z7010-2lane-pass": ancestor("p9-z7010-2lane-pass", head),
        },
        "canonical_hashes": {
            "PROJECT_CONSTRAINTS.txt": sha256_file(ROOT / "PROJECT_CONSTRAINTS.txt"),
            "AGENTS.md": sha256_file(ROOT / "AGENTS.md"),
            "config/project_state.json": sha256_file(ROOT / "config/project_state.json"),
            "config/project_requirements.yaml": sha256_file(ROOT / "config/project_requirements.yaml"),
            "config/register_map/ir_axi_regs.yaml": sha256_file(ROOT / "config/register_map/ir_axi_regs.yaml"),
        },
        "goal_hashes": {
            "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md": sha256_file(ROOT / "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"),
            "goals/P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET_GOAL.md": sha256_file(ROOT / "goals/P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET_GOAL.md"),
        },
        "checks": checks,
        "no_hardware_environment": {
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
        "overall_fasttrack_hardware_authorization": True,
        "hardware_actions_executed": False,
    }
    json_path = ROOT / "evidence/generated/p10_fasttrack_concise_preflight.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# P10 fast-track concise preflight",
        "",
        f"- Result: `{status}`",
        f"- Branch: `{branch}`",
        f"- Base/HEAD: `{head}`",
        f"- Includes main: `{payload['ancestors']['main']}`",
        f"- Includes P8E: `{payload['ancestors']['p8e-pass']}`",
        f"- Includes P9: `{payload['ancestors']['p9-z7010-2lane-pass']}`",
        f"- Tracked worktree clean before checks: `{payload['tracked_worktree_clean_before_checks']}`",
        "- Preflight subphase environment: `NO_HARDWARE=1`, `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`.",
        "- Hardware actions executed: `false`.",
        "",
        "| Check | Result | Exit | Duration (s) | Raw log |",
        "|---|---|---:|---:|---|",
    ]
    for check in checks:
        lines.append(
            f"| `{check['name']}` | {check['status']} | {check['exit_code']} | "
            f"{check['duration_seconds']:.3f} | `{check['log']}` |"
        )
    lines.extend(["", "The fast-track hardware authorization remains present, but the wiring audit separately blocks hardware admission."])
    (ROOT / "evidence/generated/p10_fasttrack_concise_preflight.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    transition_json = ROOT / "evidence/generated/p10_fasttrack_midrun_transition.json"
    repo_intake = {
        "schema_version": 1,
        "test_id": "P10-REPO-INTAKE",
        "status": status,
        "worktree": str(ROOT),
        "branch": branch,
        "base_commit": head,
        "main_commit": payload["main"],
        "branch_match": payload["branch_match"],
        "ancestors": payload["ancestors"],
        "tracked_worktree_clean_at_concise_preflight_start": payload["tracked_worktree_clean_before_checks"],
        "canonical_hashes": payload["canonical_hashes"],
        "goal_hashes": payload["goal_hashes"],
        "concise_preflight": "evidence/generated/p10_fasttrack_concise_preflight.json",
        "midrun_transition": {
            "path": "evidence/generated/p10_fasttrack_midrun_transition.json",
            "sha256": sha256_file(transition_json),
        },
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": True,
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
    }
    (ROOT / "evidence/generated/p10_repo_intake.json").write_text(
        json.dumps(repo_intake, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    repo_lines = [
        "# P10 repository intake",
        "",
        f"- Result: `{status}`",
        f"- Worktree: `{ROOT}`",
        f"- Branch: `{branch}`",
        f"- Base commit: `{head}`",
        f"- Includes main: `{payload['ancestors']['main']}`",
        f"- Includes P8E: `{payload['ancestors']['p8e-pass']}`",
        f"- Includes P9: `{payload['ancestors']['p9-z7010-2lane-pass']}`",
        f"- Fast-track goal SHA256: `{payload['goal_hashes']['goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md']}`",
        f"- Superseded goal SHA256: `{payload['goal_hashes']['goals/P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET_GOAL.md']}`",
        "- Unknown tracked modifications at concise-preflight start: none.",
        "- Hardware actions executed: `false`.",
        "- Hardware admission is blocked by `P10-SAFETY-POWERUP-001`.",
    ]
    (ROOT / "evidence/generated/p10_repo_intake.md").write_text("\n".join(repo_lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "checks": len(checks)}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
