#!/usr/bin/env python3
"""Run or verify the complete no-hardware P10.2 four-lane readiness gate (offline-build-only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "evidence/generated/p10_2_raw"
LOGS = RAW / "gate_commands"
SUMMARY_JSON = ROOT / "evidence/generated/p10_2_gate_summary.json"
SUMMARY_MD = ROOT / "evidence/generated/p10_2_gate_summary.md"
GOAL = ROOT / "goals/P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS_GOAL.md"
GOAL_SHA256 = "f09ddcd1556b6def7eab250cae92b1cc69f7316a4c3338b5b04d23b10f22a8f5"
BRANCH = "p10.2/4lane-offline-readiness"
BASE = "e90a2203c4d6b71f93e0ee1c5bf93bb263c8a1b8"
P10_1R_SOURCE = "39df17155ce82e38366fbdac00c79584f0fe1afa"
P10_1R_CHECKPOINT = "9321ca2f1797eb12bfb02848c3ee27145e1e8eb4"
P10_1R_PASS_TAG = "p10.1r-2lane-speed-stability-pass"
P10_1R_CLOSED_TAG = "p10.1r-2lane-speed-stability-closed"
P10_1R_WORKTREE = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def run_step(
    name: str,
    command: list[str],
    timeout: int,
    steps: list[dict[str, Any]],
) -> subprocess.CompletedProcess[str]:
    LOGS.mkdir(parents=True, exist_ok=True)
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
            "NO_2H_QUALIFICATION": "true",
        },
    )
    log = LOGS / f"{name}.log"
    log.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + f"RETURN_CODE={result.returncode}\n"
        + "STDOUT_BEGIN\n" + result.stdout + "\nSTDOUT_END\n"
        + "STDERR_BEGIN\n" + result.stderr + "\nSTDERR_END\n",
        encoding="utf-8", errors="replace", newline="\n",
    )
    steps.append({
        "step": name,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "returncode": result.returncode,
        "command": command,
        "log": rel(log),
        "log_sha256": sha256(log),
        "hardware_actions_executed": False,
    })
    return result


def verify_path_record(record: dict[str, Any], label: str, errors: list[str]) -> None:
    path_text = record.get("path")
    digest = record.get("sha256")
    if not isinstance(path_text, str) or not isinstance(digest, str):
        errors.append(f"{label} lacks path/SHA256")
        return
    path = ROOT / path_text
    if not path.is_file():
        errors.append(f"{label} missing: {path_text}")
    elif sha256(path) != digest:
        errors.append(f"{label} SHA256 mismatch: {path_text}")


def p10_1r_recheck() -> dict[str, Any]:
    errors: list[str] = []
    closeout_path = ROOT / "evidence/generated/p10_1r_closeout_summary.json"
    metadata_path = ROOT / "evidence/generated/p10_1r_git_checkpoint_metadata.json"
    final_path = ROOT / "evidence/generated/p10_1r_final_summary.json"
    consistency_path = ROOT / "evidence/generated/p10_1r_hardware_evidence_consistency.json"
    for path in (closeout_path, metadata_path, final_path, consistency_path):
        if not path.is_file():
            errors.append(f"missing immutable P10.1R evidence {rel(path)}")
    closeout = json.loads(closeout_path.read_text(encoding="utf-8")) if closeout_path.is_file() else {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
    final = json.loads(final_path.read_text(encoding="utf-8")) if final_path.is_file() else {}
    consistency = json.loads(consistency_path.read_text(encoding="utf-8")) if consistency_path.is_file() else {}
    checks: dict[str, bool] = {}
    try:
        checks = {
            "pass_tag_annotated": git("cat-file", "-t", P10_1R_PASS_TAG) == "tag",
            "pass_tag_target": git("rev-list", "-n", "1", P10_1R_PASS_TAG) == P10_1R_CHECKPOINT,
            "closed_tag_annotated": git("cat-file", "-t", P10_1R_CLOSED_TAG) == "tag",
            "closed_tag_target": git("rev-list", "-n", "1", P10_1R_CLOSED_TAG) == BASE,
            "source_ancestor_of_checkpoint": subprocess.run(
                ["git", "merge-base", "--is-ancestor", P10_1R_SOURCE, P10_1R_CHECKPOINT],
                cwd=ROOT, capture_output=True,
            ).returncode == 0,
            "main_at_closeout": git("rev-parse", "main") == BASE,
            "p10_1r_worktree_clean": P10_1R_WORKTREE.is_dir() and
                not git("status", "--porcelain", cwd=P10_1R_WORKTREE),
            "closeout_pass": closeout.get("status") == "PASS",
            "authorization_closed": closeout.get("authorization", {}).get(
                "current_run_hardware_authorization") is False,
            "authorization_consumed": closeout.get("authorization", {}).get(
                "last_hardware_authorization_consumed") is True,
            "shutdown_fixed": closeout.get("shutdown", {}).get("fixed") == "PASS",
            "shutdown_rotating": closeout.get("shutdown", {}).get("rotating") == "PASS",
            "final_pass": final.get("status") == "PASS",
            "consistency_pass": consistency.get("status") == "PASS",
            "old_f1_quarantined": closeout.get("accepted_baseline", {}).get("old_f1") ==
                "QUARANTINED_NOT_ACCEPTED",
        }
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"P10.1R Git topology check failed: {exc}")
    errors.extend(f"P10.1R check failed: {name}" for name, passed in checks.items() if not passed)
    verified = 0
    for name, record in metadata.get("artifacts", {}).items():
        before = len(errors)
        verify_path_record(record, f"P10.1R artifact {name}", errors)
        if len(errors) == before:
            verified += 1
    for name in ("wiring", "module_inventory", "final_summary", "evidence_consistency", "formal_run_manifest"):
        record = metadata.get(name, {})
        before = len(errors)
        if name == "module_inventory" and isinstance(record.get("path"), str):
            baseline_bytes = subprocess.check_output(
                ["git", "show", f"{BASE}:{record['path']}"], cwd=ROOT
            )
            if sha256_bytes(baseline_bytes) != record.get("sha256"):
                errors.append("P10.1R immutable module-inventory blob SHA256 mismatch")
            else:
                baseline_inventory = yaml.safe_load(baseline_bytes.decode("utf-8"))
                current_inventory = yaml.safe_load(
                    (ROOT / record["path"]).read_text(encoding="utf-8")
                )
                if baseline_inventory.get("accepted") != current_inventory.get("accepted") or \
                        baseline_inventory.get("quarantine") != current_inventory.get("quarantine"):
                    errors.append("P10.2 changed accepted/quarantined P10.1R module identity")
                checks["p10_1r_inventory_identity_preserved"] = not any(
                    item.startswith("P10.2 changed accepted/quarantined") for item in errors
                )
                checks["future_inventory_positions_are_additive"] = all(
                    item.get("proposed_position", "").startswith(("J11-A_", "J11-B_"))
                    for item in current_inventory.get("future_intake", [])
                )
                if not checks["future_inventory_positions_are_additive"]:
                    errors.append("future module positions are not explicit additive P10.2 metadata")
        else:
            verify_path_record(record, f"P10.1R metadata {name}", errors)
        if len(errors) == before:
            verified += 1
    return {
        "schema_version": 1,
        "test_id": "P10_2-P10_1R-FROZEN-RECHECK",
        "status": "PASS" if not errors else "FAIL",
        "p10_1r_source_commit": P10_1R_SOURCE,
        "p10_1r_evidence_checkpoint": P10_1R_CHECKPOINT,
        "p10_1r_pass_tag": P10_1R_PASS_TAG,
        "p10_1r_pass_tag_target": git("rev-list", "-n", "1", P10_1R_PASS_TAG),
        "p10_1r_closed_tag": P10_1R_CLOSED_TAG,
        "p10_1r_closed_tag_target": git("rev-list", "-n", "1", P10_1R_CLOSED_TAG),
        "checks": checks,
        "verified_hash_records": verified,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "errors": errors,
    }


def no_hardware_static_scan(source_commit: str) -> dict[str, Any]:
    errors: list[str] = []
    changed = git("diff", "--name-only", f"{BASE}..{source_commit}").splitlines()
    executable = [
        path for path in changed
        if Path(path).suffix.lower() in {".py", ".ps1", ".tcl", ".bat", ".cmd"}
    ]
    forbidden = {
        "vivado_hardware_manager": re.compile(r"\b(open_hw|connect_hw_server|open_hw_target|program_hw_devices|refresh_hw_device)\b", re.I),
        "hw_server_executable": re.compile(r"hw_server\.(bat|exe)", re.I),
        "xsdb_executable": re.compile(r"xsdb\.(bat|exe)", re.I),
        "serial_or_network_io": re.compile(r"serial\.Serial|socket\.socket|requests\.(get|post)|urllib\.request", re.I),
    }
    findings: list[dict[str, Any]] = []
    for relative in executable:
        path = ROOT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in forbidden.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                line_text = text.splitlines()[line - 1]
                if relative == "scripts/run_p10_2_4lane_offline_gate.py" and \
                        "re.compile" in line_text:
                    continue
                findings.append({"file": relative, "line": line, "rule": name,
                                 "match": match.group(0)})
    errors.extend(f"forbidden executable token: {item}" for item in findings)
    return {
        "schema_version": 1,
        "test_id": "P10_2-NO-HARDWARE-STATIC-SCAN",
        "status": "PASS" if not errors else "FAIL",
        "source_commit": source_commit,
        "changed_executable_files": executable,
        "forbidden_findings": findings,
        "allowed_offline_tools": ["Vivado synthesis/implementation batch", "XSIM", "XSCT/Vitis build only"],
        "hw_server_connected": False,
        "jtag_connected": False,
        "fpga_programmed": False,
        "ps_elf_run": False,
        "uart_written": False,
        "tfdu_driven": False,
        "network_used": False,
        "two_hour_qualification_executed": False,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "errors": errors,
    }


def emit_summary(payload: dict[str, Any], destination: str | None) -> None:
    if destination is None:
        return
    encoded = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
    if destination == "-":
        print(encoded)
    else:
        path = (ROOT / destination).resolve()
        path.relative_to(ROOT.resolve())
        path.write_text(encoded + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    mode.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--json-summary", nargs="?", const="-", metavar="PATH")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()
    steps: list[dict[str, Any]] = []
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    if os.environ.get("NO_2H_QUALIFICATION", "true").lower() != "true":
        errors.append("NO_2H_QUALIFICATION must be true")
    if git("branch", "--show-current") != BRANCH:
        errors.append("branch mismatch")
    if not GOAL.is_file() or sha256(GOAL) != GOAL_SHA256:
        errors.append("goal SHA256 mismatch")
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASE, "HEAD"],
                      cwd=ROOT, capture_output=True).returncode != 0:
        errors.append("P10.1R closeout base is not an ancestor of HEAD")
    recheck = p10_1r_recheck()
    if recheck["status"] != "PASS":
        errors.extend(recheck["errors"])

    if args.verify_existing:
        result = subprocess.run(
            [sys.executable, "scripts/finalize_p10_2_offline.py", "--verify-existing", "--json-summary"],
            cwd=ROOT, text=True, capture_output=True,
            env={**os.environ, "NO_HARDWARE": "1",
                 "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
                 "NO_2H_QUALIFICATION": "true"},
        )
        try:
            verified = json.loads(result.stdout)
        except json.JSONDecodeError:
            verified = {"status": "FAIL", "errors": [result.stdout, result.stderr]}
        if result.returncode != 0:
            errors.extend(verified.get("errors", ["verify-existing failed"]))
        payload = {
            "schema_version": 1, "mode": "verify-existing",
            "status": "PASS" if not errors else "FAIL", "p10_1r_recheck": recheck,
            "p10_2_verify": verified, "allow_skips": args.allow_skips,
            "no_cache": args.no_cache, "hardware_actions_executed": False,
            "current_run_hardware_authorization": False, "errors": errors,
        }
        emit_summary(payload, args.json_summary)
        print(f"P10_2_4LANE_OFFLINE_GATE={payload['status']}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
        return 0 if not errors else 1

    RAW.mkdir(parents=True, exist_ok=True)
    write_json(RAW / "p10_1r_recheck.json", recheck)
    source_commit = git("rev-parse", "HEAD")
    scan = no_hardware_static_scan(source_commit)
    write_json(RAW / "no_hardware_static_scan.json", scan)
    if scan["status"] != "PASS":
        errors.extend(scan["errors"])

    commands: list[tuple[str, list[str], int]] = [
        ("board_package", [sys.executable, "scripts/generate_p10_2_board_package.py"], 120),
        ("register_map", [sys.executable, "scripts/generate_register_headers.py", "--verify"], 120),
        ("templates", [sys.executable, "scripts/generate_p10_3_evidence_templates.py"], 120),
        ("model", [sys.executable, "scripts/model_p10_2_4lane.py", "--json-summary",
                   "evidence/generated/p10_2_raw/model.json"], 300),
        ("power_model", [sys.executable, "scripts/model_p10_2_4lane_power.py", "--json-summary",
                         "evidence/generated/p10_2_raw/power_model.json"], 120),
        ("xsim", [sys.executable, "scripts/run_p10_2_xsim.py"], 1800),
        ("host_software", [sys.executable, "scripts/build_p10_2_software.py"], 600),
    ]
    if errors:
        commands = []
    for name, command, timeout in commands:
        result = run_step(name, command, timeout, steps)
        if result.returncode != 0:
            errors.append(f"step failed: {name}")
            break

    if not errors:
        xsim_summary = json.loads((RAW / "xsim/summary.json").read_text(encoding="utf-8"))
        xsim_by_id = {item.get("test_id"): item for item in xsim_summary.get("results", [])}
        regression_errors: list[str] = []
        if xsim_by_id.get("tb_2lane_4lane_regression", {}).get("status") != "PASS":
            regression_errors.append("current two-lane RTL compatibility XSIM failed")
        if xsim_by_id.get("tb_p10_2_lane_count_elaboration", {}).get("status") != "PASS":
            regression_errors.append("2/4/8 common-source elaboration XSIM failed")
        if recheck.get("status") != "PASS":
            regression_errors.append("immutable P10.1R closeout recheck failed")
        regression_payload = {
            "schema_version": 1,
            "test_id": "P10_2-CURRENT-TWO-LANE-AND-FROZEN-P10_1R-REGRESSION",
            "status": "PASS" if not regression_errors else "FAIL",
            "source_commit": source_commit,
            "current_two_lane_xsim": xsim_by_id.get("tb_2lane_4lane_regression"),
            "lane_count_elaboration": xsim_by_id.get("tb_p10_2_lane_count_elaboration"),
            "p10_1r_recheck_sha256": sha256(RAW / "p10_1r_recheck.json"),
            "p10_1r_hardware_pass_preserved_without_artifact_reuse": True,
            "hardware_actions_executed": False,
            "current_run_hardware_authorization": False,
            "errors": regression_errors,
        }
        write_json(RAW / "p10_frozen_regression.json", regression_payload)
        if regression_errors:
            errors.extend(regression_errors)

    if not errors:
        runner = run_step(
            "p10_3_runner_selftest",
            [sys.executable, "scripts/run_p10_3_ax7020_4lane_hardware.py", "--self-test"],
            120, steps,
        )
        try:
            runner_payload = json.loads(runner.stdout)
        except json.JSONDecodeError:
            runner_payload = {"status": "FAIL", "errors": ["runner output is not JSON"],
                              "hardware_actions_executed": False}
        write_json(RAW / "p10_3_runner_selftest.json", runner_payload)
        if runner.returncode != 0 or runner_payload.get("status") != "PASS":
            errors.append("P10.3 runner self-test failed")

    if not errors:
        build_command = [sys.executable, "scripts/build_p10_ax7020_functional.py",
                         "--campaign", "p10_2"]
        if args.quick:
            build_command.append("--reuse-existing")
        build = run_step("functional_build", build_command, 4200, steps)
        if build.returncode != 0:
            errors.append("fixed/rotating four-lane routed build failed")

    if not errors:
        if args.quick:
            runtime_summary = ROOT / "evidence/generated/p10_2_ps_runtime_build_summary.json"
            if not runtime_summary.is_file():
                errors.append("quick mode requires an existing P10.2 runtime build")
            else:
                existing_runtime = json.loads(runtime_summary.read_text(encoding="utf-8"))
                if existing_runtime.get("status") != "PASS" or \
                        existing_runtime.get("source_commit") != source_commit:
                    errors.append("quick-mode runtime build is absent or bound to another source commit")
        else:
            runtime = run_step(
                "runtime_build",
                [sys.executable, "scripts/build_p10_ps_runtime.py", "--campaign", "p10_2"],
                2400, steps,
            )
            if runtime.returncode != 0:
                errors.append("fixed/rotating four-lane BSP/ELF build failed")

    if not errors:
        finalized = run_step(
            "finalize",
            [sys.executable, "scripts/finalize_p10_2_offline.py", "--write", "--json-summary"],
            600, steps,
        )
        try:
            final_payload = json.loads(finalized.stdout)
        except json.JSONDecodeError:
            final_payload = {"status": "FAIL", "errors": ["finalizer output is not JSON"]}
        if finalized.returncode != 0 or final_payload.get("status") != "PASS":
            errors.extend(final_payload.get("errors", ["finalizer failed"]))

    status = "PASS" if not errors else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": "P10_2-4LANE-OFFLINE-GATE",
        "status": status,
        "mode": "full" if args.full else "quick",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "goal_sha256": GOAL_SHA256,
        "branch": BRANCH,
        "allow_skips_requested": args.allow_skips,
        "core_skips_allowed": False,
        "no_cache": args.no_cache,
        "steps": steps,
        "p10_1r_recheck": recheck,
        "no_hardware_static_scan": scan,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "network_used": False,
        "two_hour_qualification_executed": False,
        "errors": errors,
    }
    write_json(SUMMARY_JSON, summary)
    lines = ["# P10.2 four-lane offline gate", "", f"- Status: `{status}`",
             f"- Source commit: `{source_commit}`", "- Hardware actions executed: `false`.", "",
             "| Step | Status | Log |", "|---|---|---|"]
    lines.extend(f"| {item['step']} | {item['status']} | `{item['log']}` |" for item in steps)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    emit_summary(summary, args.json_summary)
    print(f"P10_2_4LANE_OFFLINE_GATE={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
