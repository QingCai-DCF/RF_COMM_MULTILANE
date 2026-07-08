#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
SIM_EVIDENCE = ROOT / "evidence/simulation"
SIM_LOGS = SIM_EVIDENCE / "logs"
PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP_WITH_REASON"
PASS_WITH_SKIPS = "PASS_WITH_SKIPS"
NO_HW = "NO_HARDWARE_ACTIONS_EXECUTED: true"
PENDING_HW = "HARDWARE_ACCEPTANCE: PENDING_HW"
BASELINE_COMMIT = "e48b1fe550c82835679d4c950ba23e0053801ad7"

sys.path.insert(0, str(ROOT / "tools" / "sim"))
from detect_simulator import detect_simulators, write_detection_summary  # noqa: E402


HDL_TESTS = [
    {
        "name": "tb_tfdu_lane_phy_reset_shutdown",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_lane_phy_reset_shutdown.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_lane_phy_startup_gate",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_lane_phy_startup_gate.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_lane_phy_txd_default_low",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_lane_phy_txd_default_low.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_lane_phy_txd_stuck_high_guard",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_lane_phy_txd_stuck_high_guard.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_lane_phy_rx_active_low",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_lane_phy_rx_active_low.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_lane_phy_pulse_width",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_lane_phy_pulse_width.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu6102_behavior_model_smoke",
        "group": "TFDU6102_BEHAVIOR_MODEL",
        "sources": ["sim/tb/tb_tfdu6102_behavior_model_smoke.sv", "sim/models/tfdu6102_behavior_model.sv"],
    },
    {
        "name": "tb_tfdu6102_pair_link_smoke",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": [
            "sim/tb/tb_tfdu6102_pair_link_smoke.sv",
            "rtl/tfdu/tfdu_lane_phy.sv",
            "sim/models/tfdu6102_behavior_model.sv",
        ],
    },
    {
        "name": "tb_tfdu_multilane_generate_smoke",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_multilane_generate_smoke.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_negative_no_startup_tx",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_negative_no_startup_tx.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_tfdu_negative_mode_low_fir_drop",
        "group": "TFDU6102_BEHAVIOR_MODEL",
        "sources": ["sim/tb/tb_tfdu_negative_mode_low_fir_drop.sv", "sim/models/tfdu6102_behavior_model.sv"],
    },
    {
        "name": "tb_tfdu_negative_stuck_high",
        "group": "TFDU_LANE_PHY_TESTS",
        "sources": ["sim/tb/tb_tfdu_negative_stuck_high.sv", "rtl/tfdu/tfdu_lane_phy.sv"],
    },
    {
        "name": "tb_ir_4ppm_pulse_smoke",
        "group": "4PPM_PULSE_SMOKE",
        "sources": [
            "sim/tb/tb_ir_4ppm_pulse_smoke.sv",
            "rtl/ir_4ppm_codec.sv",
            "rtl/tfdu/tfdu_lane_phy.sv",
            "sim/models/tfdu6102_behavior_model.sv",
        ],
    },
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def run_cmd(cmd, timeout=120, log_path=None):
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
    payload = {
        "cmd": " ".join(str(item) for item in cmd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    if log_path:
        write_text(
            log_path,
            "\n".join(
                [
                    f"$ {payload['cmd']}",
                    f"returncode={proc.returncode}",
                    "",
                    "## stdout",
                    proc.stdout,
                    "",
                    "## stderr",
                    proc.stderr,
                ]
            ),
        )
    return payload


def git_value(*args):
    try:
        proc = run_cmd(["git", *args], timeout=20)
    except Exception as exc:
        return f"ERROR: {exc}"
    if proc["returncode"] != 0:
        return (proc["stderr"] or proc["stdout"]).strip()
    return proc["stdout"].strip()


def status_from_results(results):
    if any(item["result"] == FAIL for item in results):
        return FAIL
    if any(item["result"] == SKIP for item in results):
        return PASS_WITH_SKIPS
    return PASS


def write_summary(path: Path, title: str, result: str, reason: str, command: str, lines=None):
    body = [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"current_commit: {git_value('rev-parse', 'HEAD')}",
        f"command: {command}",
        f"RESULT: {result}",
        f"REASON: {reason}",
        NO_HW,
        PENDING_HW,
        "",
    ]
    if lines:
        body.extend(lines)
        body.append("")
    write_text(path, "\n".join(body))


def write_repo_intake():
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    status = git_value("status", "--short")
    ancestor = run_cmd(["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"], timeout=20)
    result = PASS if ancestor["returncode"] == 0 else FAIL
    lines = [
        f"- HEAD: `{head}`",
        f"- branch: `{branch}`",
        f"- dirty_status: {'clean' if not status else 'dirty'}",
        f"- baseline_commit: `{BASELINE_COMMIT}`",
        f"- baseline_is_ancestor_or_head: {str(ancestor['returncode'] == 0).lower()}",
        "",
        "```text",
        status or "(clean)",
        "```",
    ]
    write_summary(
        GENERATED / "p2_repo_intake.md",
        "P2 Repo Intake",
        result,
        "baseline commit is reachable from HEAD" if result == PASS else "baseline commit is not reachable from HEAD",
        "git status; git rev-parse HEAD; git branch --show-current",
        lines,
    )
    return {"name": "P2_REPO_INTAKE", "result": result, "reason": "repo intake recorded", "summary": "evidence/generated/p2_repo_intake.md"}


def review_p1_evidence():
    required = [
        "offline_gate_summary.md",
        "p1_offline_hardening_summary.md",
        "tfdu6102_offline_contract_summary.md",
        "constraint_uniqueness_summary.md",
        "rtl_offline_lint_summary.md",
        "ps_driver_sequence_summary.md",
        "host_offline_stub_summary.md",
    ]
    missing = [name for name in required if not (GENERATED / name).exists()]
    no_hw_missing = []
    for name in required:
        path = GENERATED / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "NO_HARDWARE_ACTIONS_EXECUTED" not in text:
            no_hw_missing.append(name)
    result = PASS if not missing and not no_hw_missing else FAIL
    lines = [
        "## P1 Evidence Files",
        "",
        *(f"- `{name}`: {'present' if (GENERATED / name).exists() else 'missing'}" for name in required),
        "",
        f"- missing_no_hardware_marker: {', '.join(no_hw_missing) if no_hw_missing else 'none'}",
    ]
    write_summary(
        GENERATED / "p1_evidence_review_for_p2.md",
        "P1 Evidence Review For P2",
        result,
        "P1 evidence files are present and retain no-hardware markers" if result == PASS else "P1 evidence review failed",
        "python tools/run_simulation_gate.py",
        lines,
    )
    return {"name": "P1_EVIDENCE_REVIEW", "result": result, "reason": "P1 evidence reviewed", "summary": "evidence/generated/p1_evidence_review_for_p2.md"}


def run_reference_tests():
    SIM_LOGS.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "sim/scripts/run_reference_tests.py", "--json"]
    proc = run_cmd(cmd, timeout=60, log_path=SIM_LOGS / "tfdu6102_reference_model.log")
    try:
        payload = json.loads(proc["stdout"])
    except json.JSONDecodeError:
        payload = {"status": FAIL, "tests": [], "parse_error": proc["stdout"]}
    result = PASS if proc["returncode"] == 0 and payload.get("status") == PASS else FAIL
    tests = payload.get("tests", [])
    lines = [
        f"- returncode: {proc['returncode']}",
        f"- tests: {len(tests)}",
        "",
        "| Test | Result | Reason |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {item.get('name')} | {item.get('result')} | {item.get('reason', '')} |" for item in tests)
    write_summary(
        GENERATED / "tfdu6102_reference_model_summary.md",
        "TFDU6102 Reference Model Summary",
        result,
        "Python reference model tests passed" if result == PASS else "Python reference model tests failed",
        "python sim/scripts/run_reference_tests.py --json",
        lines,
    )
    return {"name": "PYTHON_REFERENCE_MODEL", "result": result, "reason": "reference tests completed", "summary": "evidence/generated/tfdu6102_reference_model_summary.md"}


def run_icarus_test(test, selected):
    build_dir = SIM_EVIDENCE / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    out = build_dir / f"{test['name']}.vvp"
    compile_log = SIM_LOGS / f"{test['name']}.compile.log"
    run_log = SIM_LOGS / f"{test['name']}.run.log"
    compile_cmd = ["iverilog", "-g2012", "-s", test["name"], "-o", str(out), *test["sources"]]
    compile_proc = run_cmd(compile_cmd, timeout=120, log_path=compile_log)
    if compile_proc["returncode"] != 0:
        return {
            "name": test["name"],
            "group": test["group"],
            "result": FAIL,
            "reason": "iverilog compile failed",
            "compile_log": rel(compile_log),
        }
    run_proc = run_cmd(["vvp", str(out)], timeout=120, log_path=run_log)
    return {
        "name": test["name"],
        "group": test["group"],
        "result": PASS if run_proc["returncode"] == 0 else FAIL,
        "reason": "HDL test passed" if run_proc["returncode"] == 0 else "HDL test run failed",
        "compile_log": rel(compile_log),
        "run_log": rel(run_log),
        "simulator": selected["name"],
    }


def run_xsim_test(test, selected):
    work = SIM_EVIDENCE / "xsim_work" / test["name"]
    work.mkdir(parents=True, exist_ok=True)
    compile_log = SIM_LOGS / f"{test['name']}.xvlog.log"
    elab_log = SIM_LOGS / f"{test['name']}.xelab.log"
    run_log = SIM_LOGS / f"{test['name']}.xsim.log"
    xvlog_exe = selected["paths"]["xvlog"]
    xelab_exe = selected["paths"]["xelab"]
    xsim_exe = selected["paths"]["xsim"]
    xvlog = run_cmd([xvlog_exe, "-sv", *test["sources"]], timeout=120, log_path=compile_log)
    if xvlog["returncode"] != 0:
        return {"name": test["name"], "group": test["group"], "result": FAIL, "reason": "xvlog compile failed", "compile_log": rel(compile_log)}
    xelab = run_cmd([xelab_exe, test["name"], "-snapshot", test["name"]], timeout=120, log_path=elab_log)
    if xelab["returncode"] != 0:
        return {"name": test["name"], "group": test["group"], "result": FAIL, "reason": "xelab failed", "elab_log": rel(elab_log)}
    xsim = run_cmd([xsim_exe, test["name"], "-runall"], timeout=120, log_path=run_log)
    return {
        "name": test["name"],
        "group": test["group"],
        "result": PASS if xsim["returncode"] == 0 else FAIL,
        "reason": "HDL test passed" if xsim["returncode"] == 0 else "xsim run failed",
        "run_log": rel(run_log),
        "simulator": selected["name"],
    }


def run_hdl_tests(detection):
    selected = detection.get("selected")
    if not selected:
        reason = "No executable HDL simulator found; HDL testbenches are skipped with reason and Python reference tests remain required."
        return [
            {"name": test["name"], "group": test["group"], "result": SKIP, "reason": reason}
            for test in HDL_TESTS
        ]
    if selected["kind"] == "icarus":
        return [run_icarus_test(test, selected) for test in HDL_TESTS]
    if selected["kind"] == "xsim":
        return [run_xsim_test(test, selected) for test in HDL_TESTS]
    reason = f"{selected['name']} detected, but this gate only executes event testbenches with iverilog/vvp or xsim."
    return [{"name": test["name"], "group": test["group"], "result": SKIP, "reason": reason} for test in HDL_TESTS]


def aggregate_group(results, group):
    group_results = [item for item in results if item.get("group") == group]
    if not group_results:
        return {"result": SKIP, "reason": "no tests in group"}
    result = status_from_results(group_results)
    if result == PASS:
        reason = "all group tests passed"
    elif result == PASS_WITH_SKIPS:
        reason = "one or more group tests skipped with reason"
    else:
        reason = "one or more group tests failed"
    return {"result": result, "reason": reason}


def write_hdl_group_summaries(hdl_results):
    behavior = aggregate_group(hdl_results, "TFDU6102_BEHAVIOR_MODEL")
    lane = aggregate_group(hdl_results, "TFDU_LANE_PHY_TESTS")
    ppm = aggregate_group(hdl_results, "4PPM_PULSE_SMOKE")
    for path, title, group, agg in [
        (GENERATED / "tfdu6102_behavior_model_summary.md", "TFDU6102 Behavior Model HDL Summary", "TFDU6102_BEHAVIOR_MODEL", behavior),
        (GENERATED / "tfdu_lane_phy_sim_summary.md", "TFDU Lane PHY Simulation Summary", "TFDU_LANE_PHY_TESTS", lane),
        (GENERATED / "ir_4ppm_pulse_smoke_summary.md", "IR 4PPM Pulse Smoke Summary", "4PPM_PULSE_SMOKE", ppm),
    ]:
        rows = [item for item in hdl_results if item.get("group") == group]
        lines = ["| Test | Result | Reason |", "| --- | --- | --- |"]
        lines.extend(f"| {item['name']} | {item['result']} | {item['reason']} |" for item in rows)
        write_summary(path, title, agg["result"], agg["reason"], "python tools/run_simulation_gate.py", lines)
    return {"behavior": behavior, "lane": lane, "ppm": ppm}


def run_no_hardware_scan():
    proc = run_cmd([sys.executable, "tools/check_no_hardware_actions.py"], timeout=120, log_path=SIM_LOGS / "no_hardware_static_scan.log")
    result = PASS if proc["returncode"] == 0 else FAIL
    return {"name": "NO_HARDWARE_SCAN", "result": result, "reason": "no-hardware static scan completed", "summary": "evidence/generated/no_hardware_action_static_scan.md"}


def write_test_matrix(results):
    lines = [
        "# P2 Simulation Test Matrix",
        "",
        NO_HW,
        PENDING_HW,
        "",
        "| Name | Group | Result | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for item in results:
        lines.append(f"| {item['name']} | {item.get('group', '')} | {item['result']} | {item.get('reason', '')} |")
    write_text(SIM_EVIDENCE / "test_matrix.md", "\n".join(lines))


def write_project_status(p2_status, p1_status):
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    status = git_value("status", "--short")
    content = f"""# Project Status

Project: RF_COMM_MULTILANE
Current branch: {branch}
Current HEAD: {head}

P0_BOOTSTRAP: PASS
P1_OFFLINE_HARDENING: {p1_status if p1_status != 'NOT_RUN_STANDALONE' else 'PASS'}
P2_SIMULATION_BASELINE: {p2_status}
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

git dirty status: {"clean" if not status else "dirty"}

## Allowed P2 Claims

- simulation baseline exists
- TFDU6102 offline model checks pass when the gate reports PASS for that item
- TFDU lane PHY simulation checks pass when HDL tests run and pass
- offline gates continue to block hardware actions

## Non-Claims

- P2 does not prove TFDU6102 physical hardware.
- P2 does not prove lane0, lane1, multi-lane, Ethernet, rotation, soak, or product readiness.
- Offline or simulation results must not promote HARDWARE_ACCEPTANCE beyond PENDING_HW.
"""
    write_text(ROOT / "PROJECT_STATUS.md", content)
    write_text(ROOT / "docs/PROJECT_STATUS.md", content)


def write_sim_results(payload):
    write_text(SIM_EVIDENCE / "sim_results.json", json.dumps(payload, indent=2, ensure_ascii=False))


def write_p2_summary(status, p1_status, detection, reference, hdl_groups, no_hw, all_results, commands):
    pass_items = [item["name"] for item in all_results if item["result"] == PASS]
    fail_items = [f"{item['name']}: {item.get('reason', '')}" for item in all_results if item["result"] == FAIL]
    skip_items = [f"{item['name']}: {item.get('reason', '')}" for item in all_results if item["result"] == SKIP]
    lines = [
        f"P2_SIMULATION_BASELINE: {status}",
        f"P1_RECHECK: {p1_status}",
        f"SIMULATOR_DETECTION: {'PASS' if detection.get('selected') else 'SKIP_WITH_REASON'}",
        f"PYTHON_REFERENCE_MODEL: {reference['result']}",
        f"HDL_SIMULATION: {status_from_results([item for item in all_results if item.get('group')])}",
        f"TFDU6102_BEHAVIOR_MODEL: {hdl_groups['behavior']['result']}",
        f"TFDU_LANE_PHY_TESTS: {hdl_groups['lane']['result']}",
        f"4PPM_PULSE_SMOKE: {hdl_groups['ppm']['result']}",
        f"NO_HARDWARE_SCAN: {no_hw['result']}",
        "",
        "## Generated Summaries",
        "",
        "- evidence/generated/p2_repo_intake.md",
        "- evidence/generated/simulator_detection_summary.md",
        "- evidence/generated/tfdu6102_reference_model_summary.md",
        "- evidence/generated/tfdu6102_behavior_model_summary.md",
        "- evidence/generated/tfdu_lane_phy_sim_summary.md",
        "- evidence/generated/ir_4ppm_pulse_smoke_summary.md",
        "- evidence/generated/simulation_gate_summary.md",
        "- evidence/generated/p2_simulation_baseline_summary.md",
        "- evidence/simulation/sim_results.json",
        "- evidence/simulation/test_matrix.md",
        "",
        "## PASS",
        "",
        *(f"- {item}" for item in pass_items),
        "",
        "## FAIL",
        "",
        *(f"- {item}" for item in fail_items or ["none"]),
        "",
        "## SKIP_WITH_REASON",
        "",
        *(f"- {item}" for item in skip_items or ["none"]),
        "",
        "## Verification run",
        "",
        *(f"- `{cmd}`" for cmd in commands),
        "",
        f"NEXT_RECOMMENDED_STAGE: {'P3_PRE_HW_ACCEPTANCE_PACKAGE' if status in {PASS, PASS_WITH_SKIPS} else 'P2_FIXUPS'}",
    ]
    write_summary(
        GENERATED / "p2_simulation_baseline_summary.md",
        "P2 Simulation Baseline Summary",
        status,
        "P2 simulation baseline completed" if status in {PASS, PASS_WITH_SKIPS} else "P2 simulation baseline failed",
        "python tools/run_simulation_gate.py",
        lines,
    )


def main():
    global GENERATED
    parser = argparse.ArgumentParser(description="Run RF_COMM_MULTILANE P2 offline simulation gate.")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--output-dir", default=str(GENERATED))
    parser.add_argument("--p1-recheck-status", default="NOT_RUN_STANDALONE")
    args = parser.parse_args()

    GENERATED = Path(args.output_dir)
    if not GENERATED.is_absolute():
        GENERATED = ROOT / GENERATED
    GENERATED.mkdir(parents=True, exist_ok=True)
    SIM_EVIDENCE.mkdir(parents=True, exist_ok=True)
    SIM_LOGS.mkdir(parents=True, exist_ok=True)

    commands = [
        "python tools/sim/detect_simulator.py",
        "python sim/scripts/run_reference_tests.py --json",
        "python tools/check_no_hardware_actions.py",
    ]

    repo_intake = write_repo_intake()
    p1_review = review_p1_evidence()
    detection = detect_simulators()
    write_detection_summary(detection, GENERATED / "simulator_detection_summary.md")
    reference = run_reference_tests()
    hdl_results = run_hdl_tests(detection)
    hdl_groups = write_hdl_group_summaries(hdl_results)
    no_hw = run_no_hardware_scan()

    all_results = [repo_intake, p1_review, reference, no_hw, *hdl_results]
    status = status_from_results(all_results)
    if status == PASS_WITH_SKIPS and not args.allow_skips:
        exit_status = FAIL
    else:
        exit_status = status

    write_test_matrix(all_results)
    sim_payload = {
        "generated_at_utc": now_iso(),
        "P2_SIMULATION_BASELINE": status,
        "exit_status": exit_status,
        "P1_RECHECK": args.p1_recheck_status,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "detection": detection,
        "results": all_results,
        "commands": commands,
    }
    write_sim_results(sim_payload)
    write_project_status(status, args.p1_recheck_status)
    write_p2_summary(status, args.p1_recheck_status, detection, reference, hdl_groups, no_hw, all_results, commands)
    write_summary(
        GENERATED / "simulation_gate_summary.md",
        "Simulation Gate Summary",
        status,
        "simulation gate completed" if status in {PASS, PASS_WITH_SKIPS} else "simulation gate failed",
        "python tools/run_simulation_gate.py",
        [
            f"P2_SIMULATION_BASELINE: {status}",
            f"P1_RECHECK: {args.p1_recheck_status}",
            f"NO_HARDWARE_SCAN: {no_hw['result']}",
            f"PYTHON_REFERENCE_MODEL: {reference['result']}",
            f"HDL_RESULTS: {status_from_results(hdl_results)}",
            "",
            "See `evidence/simulation/sim_results.json` and `evidence/simulation/test_matrix.md`.",
        ],
    )

    if args.json_summary:
        print(
            json.dumps(
                {
                    "P2_SIMULATION_BASELINE": status,
                    "NO_HARDWARE_ACTIONS_EXECUTED": True,
                    "HARDWARE_ACCEPTANCE": "PENDING_HW",
                    "failed": [item for item in all_results if item["result"] == FAIL],
                    "skipped": [item for item in all_results if item["result"] == SKIP],
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"P2_SIMULATION_BASELINE: {status}")
        print(NO_HW)
        print(PENDING_HW)
    return 1 if exit_status == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
