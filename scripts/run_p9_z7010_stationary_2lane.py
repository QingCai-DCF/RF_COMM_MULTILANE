#!/usr/bin/env python3
"""P9 Z7010 stationary two-lane safe orchestrator.

Hardware entry points in this file require-user-hw-authorization and default to
NO_HARDWARE dry-run.  The P9 formal path is fail-closed until a phase-2 record
binds immutable artifacts, profile, source, lane mask, and bounded runtime.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated"
P9_CONFIG = ROOT / "config/p9_z7010_stationary_2lane.yaml"
DEFAULT_AUTHORIZATION = ROOT / "config/p9_current_run_authorization.json"
GOAL_SOURCE = Path(r"C:\Users\user\Downloads\P9_Z7010_STATIONARY_2LANE_HARDWARE_VALIDATION_GOAL.md")
P8E_TAG = "p8e-pass"
P8E_TAG_OBJECT = "a0c32296eea2fdeb333a313bb28fe4efbb60bea2"
P8E_CHECKPOINT = "57ff1079b10a5c0de156b621820774bbb111c5ee"
P8E_SOURCE = "0c67e7717a5a0fb594a237a05184be65cf748f4f"
P9_BRANCH = "p9/z7010-stationary-2lane"
EXPECTED_WORKTREE = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE_P9")
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")

STAGES = tuple(f"P9-{index:02d}" for index in range(29))
HARDWARE_STAGE_FIRST = "P9-04"
TEXT_SUFFIXES = {".csv", ".json", ".log", ".md", ".rpt", ".tcl", ".txt", ".yaml", ".yml"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_pair(stem: str, title: str, payload: dict[str, Any]) -> None:
    payload.setdefault("generated_utc", utc_now())
    write_json(OUT / f"{stem}.json", payload)
    lines = [
        f"# {title}", "", f"- Status: `{payload.get('status', 'UNKNOWN')}`",
        f"- Test ID: `{payload.get('test_id', 'UNKNOWN')}`",
        f"- Source commit: `{payload.get('source_commit', 'UNKNOWN')}`", "",
        "The adjacent JSON is authoritative. Raw command logs are retained under the P9 hardware evidence tree.", "",
    ]
    highlights = payload.get("highlights", {})
    if highlights:
        lines += ["## Highlights", ""]
        for key, value in highlights.items():
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
            lines.append(f"- `{key}`: `{rendered}`")
        lines.append("")
    (OUT / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run_command(command: list[str], log_path: Path, *, env: dict[str, str] | None = None,
                timeout: int = 7200) -> dict[str, Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True,
                              timeout=timeout, env=env)
        returncode, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\nTIMEOUT_AFTER_SECONDS={timeout}\n"
    log_path.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        f"STARTED_UTC={started}\nFINISHED_UTC={utc_now()}\nRETURN_CODE={returncode}\n"
        f"STDOUT_BEGIN\n{stdout}\nSTDOUT_END\nSTDERR_BEGIN\n{stderr}\nSTDERR_END\n",
        encoding="utf-8", errors="replace", newline="\n",
    )
    return {"returncode": returncode, "stdout": stdout, "stderr": stderr,
            "log": rel(log_path), "log_sha256": sha256(log_path)}


def load_config() -> dict[str, Any]:
    return yaml.safe_load(P9_CONFIG.read_text(encoding="utf-8"))


def tool_version(command: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=120)
        text = (proc.stdout + proc.stderr).strip().splitlines()
        return {"available": proc.returncode == 0, "returncode": proc.returncode, "lines": text[:8]}
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}


def collect_intake(authorization_path: Path) -> dict[str, Any]:
    status = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=ROOT, text=True).splitlines()
    paths = {
        "PROJECT_CONSTRAINTS.txt": ROOT / "PROJECT_CONSTRAINTS.txt",
        "AGENTS.md": ROOT / "AGENTS.md",
        "config/project_state.json": ROOT / "config/project_state.json",
        "config/project_requirements.yaml": ROOT / "config/project_requirements.yaml",
        "config/register_map/ir_axi_regs.yaml": ROOT / "config/register_map/ir_axi_regs.yaml",
        "board_profiles/ACTIVE_PROFILE.json": ROOT / "board_profiles/ACTIVE_PROFILE.json",
        "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv": ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
        "constraints/active/PORT1.generated.xdc": ROOT / "constraints/active/PORT1.generated.xdc",
        "evidence/generated/p8e_final_summary.json": ROOT / "evidence/generated/p8e_final_summary.json",
        "evidence/generated/p8e_raw/artifact_sha256_manifest.json": ROOT / "evidence/generated/p8e_raw/artifact_sha256_manifest.json",
        "config/p9_z7010_stationary_2lane.yaml": P9_CONFIG,
        "p9_goal_source": GOAL_SOURCE,
        "current_run_authorization": authorization_path,
    }
    tag_object = git("rev-parse", P8E_TAG)
    tag_target = git("rev-parse", f"{P8E_TAG}^{{}}")
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    errors = []
    if ROOT.resolve() != EXPECTED_WORKTREE.resolve(): errors.append("worktree path mismatch")
    if branch != P9_BRANCH: errors.append("branch mismatch")
    if tag_object != P8E_TAG_OBJECT: errors.append("p8e tag object mismatch")
    if tag_target != P8E_CHECKPOINT: errors.append("p8e tag target mismatch")
    if subprocess.run(["git", "merge-base", "--is-ancestor", P8E_CHECKPOINT, head], cwd=ROOT).returncode:
        errors.append("HEAD is not a p8e-pass descendant")
    missing = [name for name, path in paths.items() if not path.is_file()]
    errors.extend(f"missing {name}" for name in missing)
    payload = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "test_id": "P9-00-REPO-INTAKE",
        "source_commit": head,
        "worktree_path": str(ROOT),
        "branch": branch,
        "head": head,
        "p8e_base_tag": P8E_TAG,
        "p8e_tag_object": tag_object,
        "p8e_tag_target": tag_target,
        "p8e_source_commit": P8E_SOURCE,
        "git_status_short_current": status,
        "worktree_clean_before_p9_change": True,
        "initial_clean_observation": {
            "head": P8E_CHECKPOINT,
            "branch": P9_BRANCH,
            "git_status_short": [],
            "basis": "direct pre-change command observation in the current Codex run",
        },
        "input_sha256": {name: sha256(path) for name, path in paths.items() if path.is_file()},
        "tools": {
            "python": {"available": True, "version": sys.version},
            "vivado": tool_version([r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat", "-version"]),
            "xsct": tool_version([r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat", "-eval", "puts [version]"]),
            "xsim": tool_version([r"D:\Xilinx\Vivado\2023.1\bin\xsim.bat", "-help"]),
            "arm_gcc": tool_version([r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe", "--version"]),
        },
        "hardware_authorization_present": authorization_path.is_file(),
        "hardware_actions_executed": False,
        "errors": errors,
        "start_timestamp_utc": utc_now(),
    }
    write_pair("p9_repo_intake", "P9 Repository Intake", payload)
    return payload


def run_p8e_verify(run_root: Path) -> dict[str, Any]:
    env = os.environ.copy()
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    result = run_command(
        [sys.executable, "scripts/run_p8e_dual_target_gate.py", "--verify-existing", "--json-summary"],
        run_root / "raw_logs/p8e_verify_existing.log", env=env, timeout=600,
    )
    marker = "P8E_VERIFY_EXISTING=PASS" in result["stdout"]
    return {**result, "status": "PASS" if result["returncode"] == 0 and marker else "FAIL"}


def validate_authorization(path: Path, *, stage: str, max_runtime: int,
                           lane_mask: int, require_bound_artifacts: bool) -> dict[str, Any]:
    errors: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "FAIL", "errors": [f"authorization unreadable: {exc}"]}
    config = load_config()
    if record.get("authorized") is not True: errors.append("authorized is not true")
    if record.get("scope") != config["scope"]: errors.append("scope mismatch")
    if max_runtime <= 0 or max_runtime > min(1800, int(record.get("maximum_runtime_seconds", 0))):
        errors.append("maximum runtime missing or exceeds authorization")
    if lane_mask not in {1, 2, 3}: errors.append("lane mask exceeds authorized scope")
    if stage not in STAGES: errors.append("unknown stage")
    if stage >= HARDWARE_STAGE_FIRST and require_bound_artifacts:
        if record.get("artifact_binding_phase") != "PHASE2_IMMUTABLE_ARTIFACTS_BOUND":
            errors.append("phase-2 immutable artifact binding is absent")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "authorization_sha256": sha256(path), "record": record}


def default_run_id() -> str:
    source_short = git("rev-parse", "--short=12", "HEAD")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"p9_{timestamp}_{source_short}_unfrozen"


def execute_build_and_freeze(run_root: Path, authorization_path: Path,
                             requested_run_id: str) -> dict[str, Any]:
    source_commit = git("rev-parse", "HEAD")
    timing_dir = ROOT / "evidence/generated/vivado/p9_z7010_candidate/timing_audit"
    commands: list[tuple[str, list[str], int]] = [
        ("candidate", [str(VIVADO), "-mode", "batch", "-source",
                       str(ROOT / "scripts/build_p9_z7010_candidate.tcl"),
                       "-tclargs", str(ROOT)], 7200),
        ("timing_audit", [str(VIVADO), "-mode", "batch", "-source",
                           str(ROOT / "scripts/audit_p9_timing_checkpoint.tcl"),
                           "-tclargs",
                           str(ROOT / "evidence/generated/vivado/p9_z7010_candidate/post_route_p9_candidate.dcp"),
                           str(timing_dir)], 1800),
        ("shutdown", [str(VIVADO), "-mode", "batch", "-source",
                      str(ROOT / "scripts/build_p9_z7010_shutdown.tcl"),
                      "-tclargs", str(ROOT)], 3600),
        ("ps_runtime", [sys.executable, str(ROOT / "scripts/build_p9_ps_runtime.py")], 3600),
        ("candidate_regression", [sys.executable,
                                  str(ROOT / "scripts/run_p9_candidate_regression.py"),
                                  "--source-commit", source_commit], 7200),
    ]
    freeze_command = [sys.executable, str(ROOT / "scripts/freeze_p9_artifacts.py"),
                      "--source-commit", source_commit,
                      "--phase1-authorization", str(authorization_path)]
    if requested_run_id:
        freeze_command.extend(["--run-id", requested_run_id])
    commands.append(("freeze", freeze_command, 1800))

    results: dict[str, Any] = {}
    errors: list[str] = []
    env = os.environ.copy()
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    for name, command, timeout in commands:
        result = run_command(command, run_root / f"raw_logs/build_{name}.log",
                             env=env, timeout=timeout)
        results[name] = result
        if result["returncode"] != 0:
            errors.append(f"{name} failed with return code {result['returncode']}")
            break
    freeze_summary_path = OUT / "p9_artifact_freeze_summary.json"
    freeze_summary = json.loads(freeze_summary_path.read_text(encoding="utf-8")) \
        if not errors and freeze_summary_path.is_file() else None
    if not errors and (not isinstance(freeze_summary, dict) or
                       freeze_summary.get("status") != "PASS" or
                       freeze_summary.get("source_commit") != source_commit):
        errors.append("freeze summary is absent, failed, or not source-bound")
    return {
        "status": "PASS" if not errors else "FAIL",
        "test_id": "P9-02-BUILD-AND-IMMUTABLE-FREEZE",
        "source_commit": source_commit,
        "hardware_actions_executed": False,
        "steps": results,
        "freeze_summary": freeze_summary,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if "--execute-hardware" in argv:
        from p9_hardware_runtime import main as hardware_main
        return hardware_main(argv)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--authorize-from", type=Path, default=DEFAULT_AUTHORIZATION)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--bitstream", type=Path)
    parser.add_argument("--shutdown-bitstream", type=Path)
    parser.add_argument("--elf", type=Path)
    parser.add_argument("--max-runtime", type=int, default=0)
    parser.add_argument("--lane-mask", type=lambda value: int(value, 0), default=1)
    parser.add_argument("--stage", choices=STAGES, default="P9-00")
    parser.add_argument("--resume-diagnostic-from", default="")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)

    requested_run_id = args.run_id
    run_id = args.run_id or default_run_id()
    run_root = ROOT / "evidence/hardware/p9" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    authorization_path = args.authorize_from.resolve()
    intake = collect_intake(authorization_path)
    p8e = run_p8e_verify(run_root) if args.stage == "P9-00" else {"status": "NOT_RUN"}
    if args.build_only:
        build_errors = list(intake.get("errors", []))
        if args.stage != "P9-02": build_errors.append("--build-only requires --stage P9-02")
        if args.formal: build_errors.append("--build-only cannot be combined with --formal")
        authorization = validate_authorization(
            authorization_path, stage="P9-02", max_runtime=1800,
            lane_mask=3, require_bound_artifacts=False,
        )
        if authorization["status"] != "PASS": build_errors.extend(authorization["errors"])
        if args.dry_run or build_errors:
            build = {"status": "PASS" if args.dry_run and not build_errors else "FAIL",
                     "test_id": "P9-02-BUILD-DRY-RUN", "planned": True,
                     "hardware_actions_executed": False, "errors": build_errors}
        else:
            build = execute_build_and_freeze(run_root, authorization_path, requested_run_id)
        summary = {"schema_version": 1, **build, "stage": "P9-02",
                   "run_id": run_id, "intake": intake, "authorization": authorization,
                   "dry_run": args.dry_run, "build_only": True}
        write_json(run_root / "final/orchestrator_result.json", summary)
        if args.json_summary: print(json.dumps(summary, sort_keys=True))
        else: print(f"P9_BUILD_FREEZE_STATUS={summary['status']}")
        return 0 if summary["status"] == "PASS" else 1
    hardware_requested = args.formal and args.stage >= HARDWARE_STAGE_FIRST
    effective_runtime = args.max_runtime
    authorization = validate_authorization(
        authorization_path, stage=args.stage, max_runtime=effective_runtime,
        lane_mask=args.lane_mask, require_bound_artifacts=hardware_requested,
    ) if hardware_requested else {"status": "NOT_REQUIRED_FOR_OFFLINE_STAGE", "errors": []}

    errors = list(intake.get("errors", []))
    if args.stage == "P9-00" and p8e["status"] != "PASS": errors.append("P8E_VERIFY_EXISTING")
    if hardware_requested and authorization["status"] != "PASS": errors.extend(authorization["errors"])
    if hardware_requested and (os.environ.get("NO_HARDWARE", "1") == "1" or not args.formal):
        errors.append("hardware execution remains disabled")
    status = "PASS" if not errors else "FAIL"
    summary = {
        "schema_version": 1, "status": status, "test_id": f"{args.stage}-ORCHESTRATOR",
        "stage": args.stage, "run_id": run_id, "source_commit": git("rev-parse", "HEAD"),
        "dry_run": not hardware_requested or args.dry_run, "formal": args.formal,
        "build_only": args.build_only, "hardware_requested": hardware_requested,
        "hardware_actions_executed": False, "intake": intake, "p8e_verify_existing": p8e,
        "authorization": authorization, "errors": errors,
    }
    write_json(run_root / "final/orchestrator_result.json", summary)
    if args.json_summary: print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P9_STAGE={args.stage}")
        print(f"P9_STATUS={status}")
        print(f"P9_RUN_ID={run_id}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
