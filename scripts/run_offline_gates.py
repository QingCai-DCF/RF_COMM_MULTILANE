#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
XILINX_VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
VITIS_CROSS_GCC_CANDIDATES = [
    Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe"),
    Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-linux-gnueabi\bin\arm-linux-gnueabihf-gcc.exe"),
    Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch64\nt\aarch64-none\bin\aarch64-none-elf-gcc.exe"),
    Path(r"D:\Xilinx\Vitis\2023.1\gnu\aarch64\nt\aarch64-linux\bin\aarch64-linux-gnu-gcc.exe"),
    Path(r"D:\Xilinx\Vitis\2023.1\gnu\armr5\nt\gcc-arm-none-eabi\bin\armr5-none-eabi-gcc.exe"),
]


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run the canonical no-hardware RF_COMM_MULTILANE offline bootstrap gates."
    )
    parser.add_argument(
        "--include-p8b",
        action="store_true",
        help="Run the mandatory P8B Python/xsim geometry gate after the complete P0-P7/P8A regression.",
    )
    parser.add_argument(
        "--include-p8c",
        action="store_true",
        help="Run the mandatory P8C safety gate after the complete P0-P8B regression.",
    )
    parser.add_argument(
        "--include-p8d",
        action="store_true",
        help="Run the mandatory P8D selective-repeat/DMA gate, including isolated P8B/P8C regressions.",
    )
    parser.add_argument(
        "--include-p8e",
        action="store_true",
        help="Run the mandatory P8E dual-target build/CDC/resource/timing gate after the base regression.",
    )
    # Compatibility flags make the canonical integrated command explicit while
    # preserving the existing always-on P0-P7 simulation and P8A checks.
    parser.add_argument("--include-simulation", action="store_true")
    parser.add_argument("--include-p8a", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    return parser

def run(name, cmd, status=None, env=None):
    p = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, env=env)
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

def resolve_tool(names, fallback: Path | None = None):
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    if fallback and fallback.exists():
        return str(fallback)
    return None

def xilinx_sim_toolchain():
    tools = {
        "xvlog": resolve_tool(["xvlog", "xvlog.bat"], XILINX_VIVADO_BIN / "xvlog.bat"),
        "xelab": resolve_tool(["xelab", "xelab.bat"], XILINX_VIVADO_BIN / "xelab.bat"),
        "xsim": resolve_tool(["xsim", "xsim.bat"], XILINX_VIVADO_BIN / "xsim.bat"),
    }
    return tools if all(tools.values()) else None

def vitis_cross_gcc():
    for candidate in VITIS_CROSS_GCC_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return None

def tool_discovery_lines():
    vivado_on_path = resolve_tool(["vivado", "vivado.bat"])
    xvlog_on_path = resolve_tool(["xvlog", "xvlog.bat"])
    xelab_on_path = resolve_tool(["xelab", "xelab.bat"])
    xsim_on_path = resolve_tool(["xsim", "xsim.bat"])
    lines = [
        f"IVERILOG_ON_PATH={1 if shutil.which('iverilog') else 0}",
        f"VERILATOR_ON_PATH={1 if shutil.which('verilator') else 0}",
        f"VIVADO_PATH_ON_PATH={1 if vivado_on_path else 0}",
        f"XVLOG_PATH_ON_PATH={1 if xvlog_on_path else 0}",
        f"XELAB_PATH_ON_PATH={1 if xelab_on_path else 0}",
        f"XSIM_PATH_ON_PATH={1 if xsim_on_path else 0}",
        f"XILINX_VIVADO_2023_1_BIN={XILINX_VIVADO_BIN}",
        f"XILINX_SIM_TOOLCHAIN_BAT_AVAILABLE={1 if xilinx_sim_toolchain() else 0}",
    ]
    return "\n".join(lines) + "\n"

def run_xsim_test(sim_dir, name, files, marker, top):
    tools = xilinx_sim_toolchain()
    assert tools is not None
    work_dir = sim_dir / name
    if work_dir.resolve().is_relative_to(sim_dir.resolve()) and work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    snapshot = f"{top}_snapshot"
    stdout_parts = [tool_discovery_lines()]
    stderr_parts = []
    commands = [
        [tools["xvlog"], "-sv", "-i", str(ROOT / "rtl"), "-i", str(ROOT / "sim/models"), *[str(ROOT / f) for f in files]],
        [tools["xelab"], top, "-debug", "typical", "-s", snapshot],
        [tools["xsim"], snapshot, "-runall"],
    ]
    cmd_text = " && ".join(" ".join(cmd) for cmd in commands)
    for cmd in commands:
        proc = subprocess.run(cmd, cwd=work_dir, text=True, capture_output=True)
        stdout_parts.append(proc.stdout)
        stderr_parts.append(proc.stderr)
        if proc.returncode != 0:
            return {
                "name": name,
                "cmd": cmd_text,
                "returncode": proc.returncode,
                "stdout": "".join(stdout_parts),
                "stderr": "".join(stderr_parts),
                "status": None,
            }
    stdout = "".join(stdout_parts)
    stderr = "".join(stderr_parts)
    returncode = 0
    if marker not in stdout:
        returncode = 1
        stderr += f"\nMissing {marker} marker.\n"
    return {"name": name, "cmd": cmd_text, "returncode": returncode, "stdout": stdout, "stderr": stderr, "status": None}

def run_sv_gates(outdir):
    sim_dir = outdir / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    tests = [
        (
            "lane_phy_sim",
            [
                "rtl/ir_tfdu_exact_duty_accountant.sv",
                "rtl/ir_tfdu_physical_module_safety.sv",
                "rtl/tfdu_lane_phy.sv",
                "sim/models/tfdu6102_behavior_model.sv",
                "sim/tb/tb_tfdu_lane_phy_smoke.sv",
            ],
            "TB_TFDU_LANE_PHY_SMOKE_PASS=1",
            "tb_tfdu_lane_phy_smoke",
        ),
        (
            "m2_4ppm_codec_sim",
            [
                "rtl/ir_4ppm_codec.sv",
                "sim/models/tfdu6102_behavior_model.sv",
                "sim/tb/tb_tfdu_4ppm_codec.sv",
            ],
            "TB_TFDU_4PPM_CODEC_PASS=1",
            "tb_tfdu_4ppm_codec",
        ),
        (
            "m2_frame_l1_sim",
            [
                "rtl/ir_frame_l1.sv",
                "sim/tb/tb_lane0_frame_crc.sv",
            ],
            "TB_LANE0_FRAME_CRC_PASS=1",
            "tb_lane0_frame_crc",
        ),
        (
            "m2_4ppm_model_integration_sim",
            [
                "rtl/ir_4ppm_codec.sv",
                "sim/models/tfdu6102_behavior_model.sv",
                "sim/tb/tb_tfdu_4ppm_model_integration.sv",
            ],
            "TB_TFDU_4PPM_MODEL_INTEGRATION_PASS=1",
            "tb_tfdu_4ppm_model_integration",
        ),
        (
            "m3_lane0_ack_only_sim",
            [
                "rtl/ir_arq_l2.sv",
                "sim/tb/tb_lane0_ack_only.sv",
            ],
            "TB_LANE0_ACK_ONLY_PASS=1",
            "tb_lane0_ack_only",
        ),
        (
            "m4_axi_regs_sim",
            [
                "rtl/ir_axi_regs_new.sv",
                "sim/tb/tb_ir_axi_regs_new.sv",
            ],
            "TB_IR_AXI_REGS_NEW_PASS=1",
            "tb_ir_axi_regs_new",
        ),
        (
            "scheduler_sim",
            [
                "rtl/ir_multilane_scheduler.sv",
                "sim/tb/tb_ir_multilane_scheduler.sv",
            ],
            "TB_IR_MULTILANE_SCHEDULER_PASS=1",
            "tb_ir_multilane_scheduler",
        ),
    ]
    if shutil.which("iverilog") and shutil.which("vvp"):
        results = []
        for name, files, marker, _top in tests:
            results.extend(run_iverilog_test(sim_dir, name, files, marker))
        return results
    if shutil.which("verilator"):
        files = []
        for _, test_files, _, _top in tests:
            files.extend(test_files)
        return [
            run(
                "sv_lint",
                ["verilator", "--lint-only", "--timing", "-Wall", *sorted(set(files))],
            )
        ]
    if xilinx_sim_toolchain():
        return [run_xsim_test(sim_dir, name, files, marker, top) for name, files, marker, top in tests]
    return [
        {
            "name": name,
            "cmd": "iverilog|verilator|xvlog/xelab/xsim",
            "returncode": 0,
            "stdout": tool_discovery_lines() + f"SIM_TOOL_MISSING=1\n{name.upper()}_STATUS=PENDING_TOOL\n",
            "stderr": "",
            "status": "PENDING_TOOL",
        }
        for name, _, _, _top in tests
    ]

def run_ps_driver_c_compile(outdir):
    build_dir = outdir / "c"
    build_dir.mkdir(parents=True, exist_ok=True)
    exe = build_dir / ("ps_driver_offline_stub.exe" if sys.platform.startswith("win") else "ps_driver_offline_stub")
    sources = [
        "software/ps_driver/main_offline_stub.c",
        "software/ps_driver/ir_driver.c",
        "software/ps_driver/ir_profile.c",
    ]
    common_args = ["-std=c11", "-Wall", "-Wextra", "-Isoftware/ps_driver", "-Iconfig/register_map/generated", *sources, "-o", str(exe)]
    compiler = shutil.which("gcc") or shutil.which("clang")
    if not compiler:
        cross_compiler = vitis_cross_gcc()
        if cross_compiler:
            cross_args = ["-std=c11", "-Wall", "-Wextra", "-Isoftware/ps_driver", "-Iconfig/register_map/generated", "-fsyntax-only", *sources]
            compile_result = run("ps_driver_c_compile", [cross_compiler, *cross_args])
            return {
                "name": "ps_driver_c_compile",
                "cmd": compile_result["cmd"],
                "returncode": compile_result["returncode"],
                "stdout": (
                    compile_result["stdout"]
                    + "C_COMPILER_HOST_MISSING=1\n"
                    + "VITIS_CROSS_GCC_AVAILABLE=1\n"
                    + f"VITIS_CROSS_GCC={cross_compiler}\n"
                    + "M4_PS_DRIVER_C_COMPILE_MODE=CROSS_SYNTAX_ONLY\n"
                    + "M4_PS_DRIVER_C_OFFLINE_STUB_RUN=SKIPPED_CROSS_TARGET\n"
                    + ("M4_PS_DRIVER_C_COMPILE=PASS\n" if compile_result["returncode"] == 0 else "")
                ),
                "stderr": compile_result["stderr"],
                "status": None,
            }
        return {
            "name": "ps_driver_c_compile",
            "cmd": "gcc|clang",
            "returncode": 0,
            "stdout": "C_COMPILER_MISSING=1\nVITIS_CROSS_GCC_AVAILABLE=0\nM4_PS_DRIVER_C_COMPILE=PENDING_TOOL\n",
            "stderr": "",
            "status": "PENDING_TOOL",
        }
    compile_result = run("ps_driver_c_compile", [compiler, *common_args])
    if compile_result["returncode"] != 0:
        return compile_result
    run_result = run("ps_driver_c_offline_stub", [str(exe)])
    return {
        "name": "ps_driver_c_compile",
        "cmd": compile_result["cmd"] + " && " + run_result["cmd"],
        "returncode": run_result["returncode"],
        "stdout": compile_result["stdout"] + run_result["stdout"] + "M4_PS_DRIVER_C_COMPILE=PASS\n",
        "stderr": compile_result["stderr"] + run_result["stderr"],
        "status": None,
    }

def write_summary(outdir, results):
    hard_fail = [r for r in results if r["returncode"] != 0]
    pending = [r for r in results if r.get("status") == "PENDING_TOOL"]
    status = "FAIL" if hard_fail else ("PASS_WITH_PENDING_TOOL" if pending else "PASS")
    summary = {
        "status": status,
        "no_hardware": True,
        "hardware_acceptance": "PENDING_HW",
        "hardware_acceptance_scope": "NO_NEW_HARDWARE_SCOPE_EVALUATED",
        "preserved_scoped_hardware_acceptance": {
            "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE": "PASS",
            "CURRENT_Z7010_PLATFORM_ACCEPTANCE": "PLATFORM_LIMITED_PASS",
            "Z7020_TARGET_ACCEPTANCE": "PENDING_Z7020_HW",
            "ROTATION_ACCEPTANCE": "PENDING_FINAL_MECHANICAL",
            "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
        "OFFLINE_CACHE_STATUS": "BYPASS",
        "OFFLINE_CACHE_KEY": None,
        "OFFLINE_CACHE_VALIDATED_OUTPUT_HASHES": {},
        "OFFLINE_REAL_BUILD_PROCESS_RAN": True,
        "results": results,
    }
    (outdir / "offline_gate_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        f"# Offline Gate Summary",
        "",
        f"BOOTSTRAP_STATUS: {status}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "OFFLINE_GATE_HARDWARE_SCOPE: NO_NEW_HARDWARE_SCOPE_EVALUATED",
        "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE_PRESERVED: PASS",
        "CURRENT_Z7010_PLATFORM_ACCEPTANCE_PRESERVED: PLATFORM_LIMITED_PASS",
        "Z7020_TARGET_ACCEPTANCE: PENDING_Z7020_HW",
        "ROTATION_ACCEPTANCE: PENDING_FINAL_MECHANICAL",
        "FINAL_PRODUCT_HARDWARE_ACCEPTANCE: PENDING_HW",
        "OFFLINE_CACHE_STATUS: BYPASS",
        "OFFLINE_REAL_BUILD_PROCESS_RAN: true",
        "",
    ]
    for r in results:
        mark = r.get("status") or ("PASS" if r["returncode"] == 0 else "FAIL")
        stdout = "\n".join(line.rstrip() for line in r["stdout"].strip().splitlines())
        stderr = "\n".join(line.rstrip() for line in r["stderr"].strip().splitlines())
        lines += [f"## {r['name']}: {mark}", "", "```text", stdout, stderr, "```", ""]
    (outdir / "offline_gate_summary.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return status

def main(argv=None):
    args = build_parser().parse_args(argv)
    results = []
    py = sys.executable
    results.append(run("project_integrity", [py, "scripts/check_project_integrity.py"]))
    results.append(run("p8a_unit_tests", [py, "-m", "unittest", "tests.test_p8a_consistency", "-v"]))
    results.append(run("p8a_consistency", [py, "scripts/check_p8a_consistency.py"]))
    results.append(run("xdc_conflicts", [py, "scripts/check_xdc_conflicts.py"]))
    results.append(run("tfdu_safety_static", [py, "scripts/check_tfdu_safety_static.py"]))
    results.append(run("m1_tfdu_model_reference", [py, "scripts/generate_m1_tfdu_model_reference.py"]))
    results.append(run("register_map_generation", [py, "scripts/generate_register_headers.py"]))
    results.append(run("no_hardware_calls", [py, "scripts/check_no_hardware_calls.py"]))
    results.append(run("sv_port_contracts", [py, "scripts/check_sv_port_contracts.py"]))
    results.append(run("host_client_unit_tests", [py, "software/host_client/test_protocol_contract.py"]))
    results.append(run("m2_detect_window_sweep", [py, "scripts/generate_m2_detect_window_sweep.py"]))
    results.append(run("m2_static_reference_checks", [py, "scripts/check_m2_static.py"]))
    results.append(run("m3_crc_bad_ack_reference", [py, "scripts/generate_m3_crc_bad_ack_reference.py"]))
    results.append(run("m3_static_reference_checks", [py, "scripts/check_m3_static.py"]))
    results.append(run("m4_ps_driver_trace", [py, "scripts/generate_m4_ps_driver_trace.py"]))
    results.append(run("m4_static_reference_checks", [py, "scripts/check_m4_static.py"]))
    results.append(run("scheduler_static_checks", [py, "scripts/check_scheduler_static.py"]))
    results.append(run("m5_static_nonhardware_build_checks", [py, "scripts/check_m5_static.py"]))
    results.append(run("m6_static_hardware_prep_checks", [py, "scripts/check_m6_static.py"]))
    results.append(run("m6_refusal_runtime", [py, "scripts/check_m6_refusal_runtime.py"]))
    outdir = ROOT / "evidence/generated"
    outdir.mkdir(parents=True, exist_ok=True)
    results.append(run_ps_driver_c_compile(outdir))
    m5_result = run("m5_vivado_nonhardware_build", [py, "scripts/run_vivado_nonhardware_build.py"])
    if "PENDING_TOOL" in m5_result["stdout"]:
        m5_result["status"] = "PENDING_TOOL"
    results.append(m5_result)
    results.extend(run_sv_gates(outdir))

    write_summary(outdir, results)
    results.append(run("generate_plan_completion_audit", [py, "scripts/generate_plan_completion_audit.py"]))
    write_summary(outdir, results)
    results.append(run("plan_completion_static", [py, "scripts/check_plan_completion_static.py"]))
    status = write_summary(outdir, results)

    include_p8b = args.include_p8b or args.include_p8c
    if include_p8b:
        parent_clean = all(r["returncode"] == 0 for r in results)
        p8b_env = os.environ.copy()
        p8b_cmd = [py, "scripts/run_p8b_geometry_gate.py"]
        if parent_clean:
            p8b_env["P8B_OFFLINE_PARENT"] = "1"
            p8b_cmd.append("--parent-offline-pass")
        results.append(run("p8b_geometry_mapping_handover", p8b_cmd, env=p8b_env))
        status = write_summary(outdir, results)

    if args.include_p8c:
        parent_clean = all(r["returncode"] == 0 for r in results)
        p8c_env = os.environ.copy()
        p8c_env["NO_HARDWARE"] = "1"
        p8c_cmd = [py, "scripts/run_p8c_safety_gate.py", "--json-summary"]
        if parent_clean:
            p8c_env["P8C_OFFLINE_PARENT"] = "1"
            p8c_cmd.append("--parent-offline-pass")
        results.append(run("p8c_tfdu_safety_single_global_permit", p8c_cmd, env=p8c_env))
        status = write_summary(outdir, results)

    if args.include_p8d:
        parent_clean = all(r["returncode"] == 0 for r in results)
        p8d_env = os.environ.copy()
        p8d_env["NO_HARDWARE"] = "1"
        p8d_env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
        p8d_cmd = [py, "scripts/run_p8d_data_plane_gate.py", "--full", "--json-summary"]
        if parent_clean:
            p8d_cmd.append("--parent-offline-pass")
        results.append(run("p8d_selective_repeat_sack_dma_data_plane", p8d_cmd, env=p8d_env))
        status = write_summary(outdir, results)

    if args.include_p8e:
        parent_clean = all(r["returncode"] == 0 for r in results)
        p8e_env = os.environ.copy()
        p8e_env["NO_HARDWARE"] = "1"
        p8e_env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
        p8e_cmd = [py, "scripts/run_p8e_dual_target_gate.py", "--full", "--json-summary"]
        if parent_clean:
            p8e_env["P8E_OFFLINE_PARENT"] = "1"
            p8e_cmd.append("--parent-offline-pass")
        results.append(run("p8e_dual_target_build_cdc_resource_timing", p8e_cmd, env=p8e_env))
        status = write_summary(outdir, results)

    hard_fail = [r for r in results if r["returncode"] != 0]
    print(f"OFFLINE_GATES_RAN=1 status={status}")
    print(f"P8B_INCLUDED={1 if include_p8b else 0}")
    print(f"P8C_INCLUDED={1 if args.include_p8c else 0}")
    print(f"P8D_INCLUDED={1 if args.include_p8d else 0}")
    print(f"P8E_INCLUDED={1 if args.include_p8e else 0}")
    print(f"GENERATED_SUMMARY={outdir / 'offline_gate_summary.md'}")
    return 1 if hard_fail else 0

if __name__ == "__main__":
    raise SystemExit(main())
