#!/usr/bin/env python3
import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(name, cmd, status=None):
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"name": name, "cmd": " ".join(cmd), "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "status": status}

def run_sv_gates(outdir):
    sim_dir = outdir / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    files = [
        "rtl/tfdu_lane_phy.sv",
        "sim/models/tfdu6102_behavior_model.sv",
        "sim/tb/tb_tfdu_lane_phy_smoke.sv",
    ]
    if shutil.which("iverilog") and shutil.which("vvp"):
        exe = sim_dir / "tb_tfdu_lane_phy_smoke.vvp"
        compile_result = run("lane_phy_sim_compile", ["iverilog", "-g2012", "-o", str(exe), *files])
        if compile_result["returncode"] != 0:
            return [compile_result]
        sim_result = run("lane_phy_sim", ["vvp", str(exe)])
        if "TB_TFDU_LANE_PHY_SMOKE_PASS=1" not in sim_result["stdout"]:
            sim_result["returncode"] = sim_result["returncode"] or 1
            sim_result["stderr"] += "\nMissing TB_TFDU_LANE_PHY_SMOKE_PASS=1 marker.\n"
        return [compile_result, sim_result]
    if shutil.which("verilator"):
        return [
            run(
                "lane_phy_sv_lint",
                ["verilator", "--lint-only", "--timing", "-Wall", *files],
            )
        ]
    return [
        {
            "name": "lane_phy_sim",
            "cmd": "iverilog|verilator",
            "returncode": 0,
            "stdout": "SIM_TOOL_MISSING=1\nLANE_PHY_SIM_STATUS=PENDING_TOOL\n",
            "stderr": "",
            "status": "PENDING_TOOL",
        }
    ]

def main():
    results = []
    py = sys.executable
    results.append(run("project_integrity", [py, "scripts/check_project_integrity.py"]))
    results.append(run("xdc_conflicts", [py, "scripts/check_xdc_conflicts.py"]))
    results.append(run("tfdu_safety_static", [py, "scripts/check_tfdu_safety_static.py"]))
    results.append(run("register_map_generation", [py, "scripts/generate_register_headers.py"]))
    results.append(run("no_hardware_calls", [py, "scripts/check_no_hardware_calls.py"]))
    results.append(run("host_client_unit_tests", [py, "software/host_client/test_protocol_contract.py"]))
    outdir = ROOT / "evidence/generated"
    outdir.mkdir(parents=True, exist_ok=True)
    results.extend(run_sv_gates(outdir))
    hard_fail = [r for r in results if r["returncode"] != 0]
    pending = [r for r in results if r.get("status") == "PENDING_TOOL"]
    status = "FAIL" if hard_fail else ("PASS_WITH_PENDING_TOOL" if pending else "PASS")
    summary = {"status": status, "no_hardware": True, "results": results}
    (outdir / "offline_gate_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [f"# Offline Gate Summary", "", f"BOOTSTRAP_STATUS: {status}", "NO_HARDWARE_ACTIONS_EXECUTED: true", ""]
    for r in results:
        mark = r.get("status") or ("PASS" if r["returncode"] == 0 else "FAIL")
        lines += [f"## {r['name']}: {mark}", "", "```text", r["stdout"].strip(), r["stderr"].strip(), "```", ""]
    (outdir / "offline_gate_summary.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"OFFLINE_GATES_RAN=1 status={status}")
    print(f"GENERATED_SUMMARY={outdir / 'offline_gate_summary.md'}")
    return 1 if hard_fail else 0

if __name__ == "__main__":
    raise SystemExit(main())
