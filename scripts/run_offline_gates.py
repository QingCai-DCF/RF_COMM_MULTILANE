#!/usr/bin/env python3
import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def run(name, cmd, status=None):
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return {"name": name, "cmd": " ".join(cmd), "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr, "status": status}

def run_iverilog_test(sim_dir, name, files, marker):
    exe = sim_dir / f"{name}.vvp"
    compile_result = run(f"{name}_compile", ["iverilog", "-g2012", "-o", str(exe), *files])
    if compile_result["returncode"] != 0:
        return [compile_result]
    sim_result = run(name, ["vvp", str(exe)])
    if marker not in sim_result["stdout"]:
        sim_result["returncode"] = sim_result["returncode"] or 1
        sim_result["stderr"] += f"\nMissing {marker} marker.\n"
    return [compile_result, sim_result]

def run_sv_gates(outdir):
    sim_dir = outdir / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    tests = [
        (
            "lane_phy_sim",
            [
                "rtl/tfdu_lane_phy.sv",
                "sim/models/tfdu6102_behavior_model.sv",
                "sim/tb/tb_tfdu_lane_phy_smoke.sv",
            ],
            "TB_TFDU_LANE_PHY_SMOKE_PASS=1",
        ),
        (
            "m2_4ppm_codec_sim",
            [
                "rtl/ir_4ppm_codec.sv",
                "sim/models/tfdu6102_behavior_model.sv",
                "sim/tb/tb_tfdu_4ppm_codec.sv",
            ],
            "TB_TFDU_4PPM_CODEC_PASS=1",
        ),
        (
            "m2_frame_l1_sim",
            [
                "rtl/ir_frame_l1.sv",
                "sim/tb/tb_lane0_frame_crc.sv",
            ],
            "TB_LANE0_FRAME_CRC_PASS=1",
        ),
        (
            "m3_lane0_ack_only_sim",
            [
                "rtl/ir_arq_l2.sv",
                "sim/tb/tb_lane0_ack_only.sv",
            ],
            "TB_LANE0_ACK_ONLY_PASS=1",
        ),
        (
            "m4_axi_regs_sim",
            [
                "rtl/ir_axi_regs_new.sv",
                "sim/tb/tb_ir_axi_regs_new.sv",
            ],
            "TB_IR_AXI_REGS_NEW_PASS=1",
        ),
    ]
    if shutil.which("iverilog") and shutil.which("vvp"):
        results = []
        for name, files, marker in tests:
            results.extend(run_iverilog_test(sim_dir, name, files, marker))
        return results
    if shutil.which("verilator"):
        files = []
        for _, test_files, _ in tests:
            files.extend(test_files)
        return [
            run(
                "sv_lint",
                ["verilator", "--lint-only", "--timing", "-Wall", *sorted(set(files))],
            )
        ]
    return [
        {
            "name": name,
            "cmd": "iverilog|verilator",
            "returncode": 0,
            "stdout": f"SIM_TOOL_MISSING=1\n{name.upper()}_STATUS=PENDING_TOOL\n",
            "stderr": "",
            "status": "PENDING_TOOL",
        }
        for name, _, _ in tests
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
    results.append(run("m2_static_reference_checks", [py, "scripts/check_m2_static.py"]))
    results.append(run("m3_static_reference_checks", [py, "scripts/check_m3_static.py"]))
    results.append(run("m4_static_reference_checks", [py, "scripts/check_m4_static.py"]))
    results.append(run("m5_static_nonhardware_build_checks", [py, "scripts/check_m5_static.py"]))
    results.append(run("m6_static_hardware_prep_checks", [py, "scripts/check_m6_static.py"]))
    m5_result = run("m5_vivado_nonhardware_build", [py, "scripts/run_vivado_nonhardware_build.py"])
    if "PENDING_TOOL" in m5_result["stdout"]:
        m5_result["status"] = "PENDING_TOOL"
    results.append(m5_result)
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
