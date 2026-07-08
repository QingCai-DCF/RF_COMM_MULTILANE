#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

from p1_lib import GENERATED, run_all


PASS = "PASS"
FAIL = "FAIL"
PASS_WITH_SKIPS = "PASS_WITH_SKIPS"
SKIP = "SKIP_WITH_REASON"


def _load_json_stdout(stdout):
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
    return {}


def _write_combined_offline_summary(output_dir, p1_status, p2_payload, final_status, p3_payload=None):
    output_dir = Path(output_dir)
    md_path = output_dir / "offline_gate_summary.md"
    json_path = output_dir / "offline_gate_summary.json"
    p2_status = p2_payload.get("P2_SIMULATION_BASELINE", "NOT_RUN")
    p2_failed = p2_payload.get("failed", [])
    p2_skipped = p2_payload.get("skipped", [])
    append = [
        "",
        "## P2 Simulation Gate",
        "",
        f"P2_SIMULATION_BASELINE: {p2_status}",
        f"COMBINED_OFFLINE_STATUS: {final_status}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "SUMMARY: evidence/generated/simulation_gate_summary.md",
        "RESULTS: evidence/simulation/sim_results.json",
        "",
        "### P2 Failures",
        "",
        *(f"- {item.get('name', item)}: {item.get('reason', '')}" if isinstance(item, dict) else f"- {item}" for item in p2_failed),
        *(["- none"] if not p2_failed else []),
        "",
        "### P2 Skips",
        "",
        *(f"- {item.get('name', item)}: {item.get('reason', '')}" if isinstance(item, dict) else f"- {item}" for item in p2_skipped),
        *(["- none"] if not p2_skipped else []),
        "",
    ]
    if p3_payload:
        append.extend(
            [
                "## P3 Pre-Hardware Acceptance Package",
                "",
                f"P3_PRE_HW_ACCEPTANCE_PACKAGE: {p3_payload.get('P3_PRE_HW_ACCEPTANCE_PACKAGE', 'UNKNOWN')}",
                f"COMBINED_OFFLINE_STATUS: {final_status}",
                "NO_HARDWARE_ACTIONS_EXECUTED: true",
                "HARDWARE_ACCEPTANCE: PENDING_HW",
                "SUMMARY: evidence/generated/p3_pre_hw_acceptance_package_summary.md",
                "",
                "### P3 Failures",
                "",
                *(f"- {item}" for item in p3_payload.get("fail", [])),
                *(["- none"] if not p3_payload.get("fail") else []),
                "",
                "### P3 Skips",
                "",
                *(f"- {item}" for item in p3_payload.get("skip", [])),
                *(["- none"] if not p3_payload.get("skip") else []),
                "",
            ]
        )
    if md_path.exists():
        current = md_path.read_text(encoding="utf-8", errors="ignore")
        current = current.split("\n## P2 Simulation Gate", 1)[0].rstrip()
        md_path.write_text(current + "\n" + "\n".join(append), encoding="utf-8")
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        data = {}
    data["status"] = final_status
    data["P1_OFFLINE_HARDENING"] = p1_status
    data["P2_SIMULATION_BASELINE"] = p2_status
    data["simulation_gate"] = p2_payload
    if p3_payload:
        data["P3_PRE_HW_ACCEPTANCE_PACKAGE"] = p3_payload.get("P3_PRE_HW_ACCEPTANCE_PACKAGE")
        data["pre_hw_acceptance_package_gate"] = p3_payload
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run RF_COMM_MULTILANE P1 offline hardening gates.")
    parser.add_argument("--strict", action="store_true", help="Treat skips as failures unless --allow-skips is set.")
    parser.add_argument("--allow-skips", action="store_true", help="Allow SKIP_WITH_REASON in the final status.")
    parser.add_argument("--output-dir", default=str(GENERATED), help="Summary output directory.")
    parser.add_argument("--json-summary", action="store_true", help="Print a compact JSON summary.")
    parser.add_argument("--no-bootstrap-run", action="store_true", help="Do not invoke scripts/run_offline_gates.py.")
    parser.add_argument("--include-simulation", action="store_true", help="Run the P2 offline simulation gate after P1 gates.")
    parser.add_argument("--simulation-required", action="store_true", help="Fail if the simulation gate does not complete.")
    parser.add_argument("--allow-simulation-skip", action="store_true", help="Allow explicitly recorded HDL simulation skips.")
    parser.add_argument("--include-pre-hw-package", action="store_true", help="Run the P3 pre-hardware acceptance package gate after P1/P2.")
    args = parser.parse_args()

    status, results = run_all(
        output_dir=Path(args.output_dir),
        strict=args.strict,
        allow_skips=args.allow_skips,
        run_bootstrap=not args.no_bootstrap_run,
    )
    failed = [r["name"] for r in results if r["result"] == "FAIL"]
    skipped = [r for r in results if r["result"] == "SKIP_WITH_REASON"]
    simulation_payload = None
    p3_payload = None
    final_status = status

    if args.include_simulation:
        if status not in {PASS, PASS_WITH_SKIPS}:
            simulation_payload = {
                "P2_SIMULATION_BASELINE": FAIL,
                "failed": [{"name": "P1_RECHECK", "reason": f"P1 status is {status}"}],
                "skipped": [],
            }
            final_status = FAIL
        else:
            sim_cmd = [
                sys.executable,
                "tools/run_simulation_gate.py",
                "--output-dir",
                args.output_dir,
                "--p1-recheck-status",
                status,
                "--json-summary",
            ]
            if args.allow_skips or args.allow_simulation_skip:
                sim_cmd.append("--allow-skips")
            proc = subprocess.run(sim_cmd, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, timeout=600)
            simulation_payload = _load_json_stdout(proc.stdout)
            if not simulation_payload:
                simulation_payload = {
                    "P2_SIMULATION_BASELINE": FAIL,
                    "failed": [{"name": "simulation_gate", "reason": "simulation JSON summary missing"}],
                    "skipped": [],
                    "stdout": proc.stdout[-4000:],
                    "stderr": proc.stderr[-4000:],
                }
            sim_status = simulation_payload.get("P2_SIMULATION_BASELINE", FAIL)
            if proc.returncode != 0 or sim_status == FAIL:
                final_status = FAIL
                failed.append("simulation_gate")
            elif sim_status == PASS_WITH_SKIPS:
                if args.simulation_required and not (args.allow_simulation_skip or args.allow_skips):
                    final_status = FAIL
                    failed.append("simulation_gate_skipped_but_required")
                else:
                    final_status = PASS_WITH_SKIPS
            elif status == PASS_WITH_SKIPS:
                final_status = PASS_WITH_SKIPS
            else:
                final_status = PASS
        _write_combined_offline_summary(Path(args.output_dir), status, simulation_payload, final_status)

    if args.include_pre_hw_package:
        if final_status not in {PASS, PASS_WITH_SKIPS}:
            p3_payload = {
                "P3_PRE_HW_ACCEPTANCE_PACKAGE": FAIL,
                "fail": [f"offline prereq status is {final_status}"],
                "skip": [],
            }
            final_status = FAIL
            failed.append("pre_hw_acceptance_package_prereq")
        else:
            p3_cmd = [
                sys.executable,
                "tools/run_pre_hw_acceptance_package_gate.py",
                "--json-summary",
                "--no-hardware",
                "--skip-p1-p2-recheck",
            ]
            if args.allow_skips:
                p3_cmd.append("--allow-skips")
            proc = subprocess.run(p3_cmd, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, timeout=300)
            p3_payload = _load_json_stdout(proc.stdout)
            if not p3_payload:
                p3_payload = {
                    "P3_PRE_HW_ACCEPTANCE_PACKAGE": FAIL,
                    "fail": ["pre_hw_package JSON summary missing"],
                    "skip": [],
                    "stdout": proc.stdout[-4000:],
                    "stderr": proc.stderr[-4000:],
                }
            p3_status = p3_payload.get("P3_PRE_HW_ACCEPTANCE_PACKAGE", FAIL)
            if proc.returncode != 0 or p3_status == FAIL:
                final_status = FAIL
                failed.append("pre_hw_acceptance_package_gate")
            elif final_status == PASS_WITH_SKIPS:
                final_status = PASS_WITH_SKIPS
            else:
                final_status = PASS
        _write_combined_offline_summary(Path(args.output_dir), status, simulation_payload or {}, final_status, p3_payload=p3_payload)

    if args.json_summary:
        payload = {
            "P1_OFFLINE_HARDENING": status,
            "P2_SIMULATION_BASELINE": simulation_payload.get("P2_SIMULATION_BASELINE") if simulation_payload else "NOT_RUN",
            "P3_PRE_HW_ACCEPTANCE_PACKAGE": p3_payload.get("P3_PRE_HW_ACCEPTANCE_PACKAGE") if p3_payload else "NOT_RUN",
            "COMBINED_OFFLINE_STATUS": final_status,
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "failed": failed,
            "skipped": skipped,
        }
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P1_OFFLINE_HARDENING: {status}")
        if simulation_payload:
            print(f"P2_SIMULATION_BASELINE: {simulation_payload.get('P2_SIMULATION_BASELINE')}")
        if p3_payload:
            print(f"P3_PRE_HW_ACCEPTANCE_PACKAGE: {p3_payload.get('P3_PRE_HW_ACCEPTANCE_PACKAGE')}")
        if simulation_payload or p3_payload:
            print(f"COMBINED_OFFLINE_STATUS: {final_status}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
        print(f"FAILED_GATES: {', '.join(failed) if failed else 'none'}")
        print(f"SKIPPED_GATES: {', '.join(r['name'] for r in skipped) if skipped else 'none'}")
    return 1 if failed or final_status == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
