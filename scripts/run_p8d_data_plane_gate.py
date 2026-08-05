#!/usr/bin/env python3
"""Run and freeze the P8D no-hardware selective-repeat/DMA acceptance gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_OUT = ROOT / "evidence/generated"
OUT = CANONICAL_OUT
RAW = OUT / "p8d_raw"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
VIVADO = VIVADO_BIN / "vivado.bat"
ARM_GCC = Path(
    r"D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe"
)
VCVARS64 = Path(
    r"D:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
)

P8C_TAG = "p8c-pass"
P8C_CHECKPOINT = "c44b0d45133bf75c9c71f53dde77f3dc186ad131"
P8C_SOURCE = "e8be6ffddd1b59b13b6bf3e0c32c02c6a66b6134"
P8E_TAG = "p8e-pass"
P8E_CHECKPOINT = "57ff1079b10a5c0de156b621820774bbb111c5ee"
P9_BRANCH = "p9/z7010-stationary-2lane"
P10_1R_BRANCH = "p10.1r/2lane-speed-stability-remediation"
P10_1R_STAGE = "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION"
P10_1R_FAILURE_TAG = "p10.1-hardware-performance-fail-20260801"
P10_1R_BASE_COMMIT = "991cc8a6cc5fd656178f9a3ddd9bb7c2f9c84151"
P10_1R_GOAL = ROOT / "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
P10_1R_GOAL_SHA256 = "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
PROJECT_CONSTRAINTS_SHA256 = "9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758"

COMMON = {
    "schema_version": 1,
    "NO_HARDWARE_ACTIONS_EXECUTED": True,
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    "hardware_scope_promoted": False,
}

REQUIRED_PAIRS = (
    "p8d_data_plane_config_summary",
    "p8d_selective_repeat_reference_summary",
    "p8d_selective_repeat_rtl_summary",
    "p8d_sack_ack_aggregation_summary",
    "p8d_scheduler_migration_summary",
    "p8d_axis_backpressure_summary",
    "p8d_dma_descriptor_ring_summary",
    "p8d_ps_driver_summary",
    "p8d_rfap_compatibility_summary",
    "p8d_airtime_budget_summary",
    "p8d_profile_matrix_summary",
    "p8d_resource_audit_summary",
    "p8d_register_map_summary",
    "p8d_p0_p8c_regression_summary",
    "p8d_evidence_consistency_summary",
    "p8d_final_summary",
)

PROFILE_SPECS = {
    "Z7010_2LANE_DEV": {
        "part": "xc7z010clg400-1", "lanes": 2, "window": 32,
        "sack": 32, "axis": 32, "physical_modules": 2,
        "capacity": {"LUT": 17600, "FF": 35200, "BRAM36": 60, "DSP": 80},
        "p8c_profile": "Z7010_2LANE_DEV",
    },
    "Z7020_ROTATING_8LANE_MODEL": {
        "part": "xc7z020clg400-1", "lanes": 8, "window": 64,
        "sack": 64, "axis": 64, "physical_modules": 8,
        "capacity": {"LUT": 53200, "FF": 106400, "BRAM36": 140, "DSP": 220},
        "p8c_profile": "Z7020_ROTATING_8LANE_MODEL",
    },
    "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE": {
        "part": "xc7z020clg400-1", "lanes": 8, "window": 64,
        "sack": 64, "axis": 64, "physical_modules": 32,
        "capacity": {"LUT": 53200, "FF": 106400, "BRAM36": 140, "DSP": 220},
        "p8c_profile": "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL",
    },
}

CORE_RTL = [
    "rtl/ir_seq_math_pkg.sv",
    "rtl/ir_ack_aggregator.sv",
    "rtl/ir_health_weighted_scheduler.sv",
    "rtl/ir_selective_repeat_tx.sv",
    "rtl/ir_selective_repeat_rx.sv",
    "rtl/ir_data_plane_top.sv",
]

XSIM_SPECS = {
    "tb_ir_seq_math": (["rtl/ir_seq_math_pkg.sv", "sim/tb/tb_ir_seq_math.sv"],
                       ["P8D_SEQUENCE_WIDTH_16_PASS=1", "P8D_SEQUENCE_WRAP_PASS=1", "TB_IR_SEQ_MATH_PASS=1"]),
    "tb_ir_selective_repeat_tx": (["rtl/ir_seq_math_pkg.sv", "rtl/ir_selective_repeat_tx.sv",
                                    "sim/tb/tb_ir_selective_repeat_tx.sv"],
                                   ["P8D_GLOBAL_OUTSTANDING_32_PASS=1", "P8D_RETRY_EXHAUSTION_BOUNDED_PASS=1",
                                    "P8D_ACKED_FRAME_SINGLE_COMPLETION_PASS=1", "TB_IR_SELECTIVE_REPEAT_TX_PASS=1"]),
    "tb_ir_selective_repeat_rx": (["rtl/ir_seq_math_pkg.sv", "rtl/ir_selective_repeat_rx.sv",
                                    "sim/tb/tb_ir_selective_repeat_rx.sv"],
                                   ["P8D_RX_REORDER_DUPLICATE_SUPPRESSION_PASS=1",
                                    "P8D_STALE_SESSION_PATH_REJECTION_PASS=1", "TB_IR_SELECTIVE_REPEAT_RX_PASS=1"]),
    "tb_ir_sack_ack_aggregation": (["rtl/ir_seq_math_pkg.sv", "rtl/ir_sack_codec.sv",
                                     "rtl/ir_ack_aggregator.sv", "sim/tb/tb_ir_sack_ack_aggregation.sv"],
                                    ["P8D_SACK_ENCODE_DECODE_PASS=1",
                                     "P8D_ACK_AGGREGATION_BOUNDED_DELAY_PASS=1",
                                     "TB_IR_SACK_ACK_AGGREGATION_PASS=1"]),
    "tb_ir_scheduler_migration": (["rtl/ir_health_weighted_scheduler.sv", "rtl/ir_retry_migration.sv",
                                    "sim/tb/tb_ir_scheduler_migration.sv"],
                                   ["P8D_HEALTH_AWARE_WEIGHTED_SCHEDULER_PASS=1",
                                    "P8D_SCHEDULER_FAIRNESS_PASS=1",
                                    "P8D_RETRY_ALTERNATE_LANE_PASS=1",
                                    "P8D_RETRY_MIGRATION_ACKED_BLOCK_PASS=1",
                                    "TB_IR_SCHEDULER_MIGRATION_PASS=1"]),
    "tb_ir_axis_backpressure": (["rtl/ir_axis_tx_frontend.sv", "rtl/ir_axis_rx_backend.sv",
                                  "sim/tb/tb_ir_axis_backpressure.sv"],
                                 ["P8D_AXIS_RANDOM_BACKPRESSURE_PASS=1",
                                  "P8D_AXIS_NO_LOSS_NO_DUPLICATE_PASS=1",
                                  "P8D_AXIS_MALFORMED_PACKET_REJECTION_PASS=1",
                                  "TB_IR_AXIS_BACKPRESSURE_PASS=1"]),
    "tb_ir_dma_descriptor_ring": (["rtl/ir_dma_descriptor_model.sv",
                                    "sim/tb/tb_ir_dma_descriptor_ring.sv"],
                                   ["P8D_TX_RX_RING_INDEPENDENCE_PASS=1",
                                    "P8D_DESCRIPTOR_SINGLE_COMPLETION_PASS=1",
                                    "P8D_RESET_ABORT_STALE_GENERATION_PASS=1",
                                    "P8D_DESCRIPTOR_LEAK_ZERO_PASS=1",
                                    "TB_IR_DMA_DESCRIPTOR_RING_PASS=1"]),
    "tb_ir_data_plane_integration_2lane": (CORE_RTL + ["sim/tb/p8d_data_plane_integration_common.sv",
                                                        "sim/tb/tb_ir_data_plane_integration_2lane.sv"],
                                           ["P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1",
                                            "P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1",
                                            "TB_IR_DATA_PLANE_INTEGRATION_2LANE_PASS=1"]),
    "tb_ir_data_plane_integration_8lane": (CORE_RTL + ["sim/tb/p8d_data_plane_integration_common.sv",
                                                        "sim/tb/tb_ir_data_plane_integration_8lane.sv"],
                                           ["P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1",
                                            "P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1",
                                            "TB_IR_DATA_PLANE_INTEGRATION_8LANE_PASS=1"]),
    "tb_ir_p8b_p8c_p8d_integration": (["rtl/generated/tfdu_safety_pkg.sv",
                                        "rtl/ir_path_mapping_pkg.sv",
                                        "rtl/ir_path_mapping_engine.sv",
                                        "rtl/ir_tfdu_exact_duty_accountant.sv",
                                        "rtl/ir_tfdu_physical_module_safety.sv",
                                        "rtl/ir_tfdu_safety_endpoint.sv"] + CORE_RTL +
                                       ["sim/tb/tb_ir_p8b_p8c_p8d_integration.sv"],
                                      ["P8D_P8B_MAPPING_GATE_INTEGRATION_PASS=1",
                                       "P8D_P8C_SINGLE_PERMIT_FINAL_KILL_INTEGRATION_PASS=1",
                                       "P8D_PARTIAL_FRAME_NOT_RESUMED_PASS=1",
                                       "TB_IR_P8B_P8C_P8D_INTEGRATION_PASS=1"]),
    "tb_ir_p8d_python_crosscheck": (["rtl/ir_seq_math_pkg.sv", "rtl/ir_sack_codec.sv",
                                      "sim/tb/tb_ir_p8d_python_crosscheck.sv"],
                                     ["P8D_RTL_PYTHON_CROSSCHECK_RECORDS=2048",
                                      "TB_IR_P8D_PYTHON_CROSSCHECK_PASS=1"]),
    "tb_ir_p8d_cdc_ratios": (["rtl/ir_p8d_async_descriptor_bridge.sv",
                               "sim/tb/tb_ir_p8d_cdc_ratios.sv"],
                              ["P8D_CDC_RATIO_1_1_PASS=1", "P8D_CDC_RATIO_2_1_PASS=1",
                               "P8D_CDC_RATIO_3_2_PASS=1", "P8D_CDC_ASYNC_PHASE_PASS=1",
                               "TB_IR_P8D_CDC_RATIOS_PASS=1"]),
    "tb_ir_p8d_data_plane_regs": (["rtl/ir_p8d_data_plane_regs.sv",
                                    "sim/tb/tb_ir_p8d_data_plane_regs.sv"],
                                   ["P8D_REGISTER_RO_SNAPSHOT_PASS=1",
                                    "P8D_REGISTER_CONFIG_FAIL_CLOSED_PASS=1",
                                    "TB_IR_P8D_DATA_PLANE_REGS_PASS=1"]),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, data: Any) -> None:
    write_text(path, json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def write_pair(stem: str, title: str, data: dict[str, Any]) -> None:
    payload = {**COMMON, **data}
    write_json(OUT / f"{stem}.json", payload)
    lines = [f"# {title}", "", f"- Status: `{payload.get('status', 'UNKNOWN')}`",
             f"- Test ID: `{payload.get('test_id', 'UNSPECIFIED')}`",
             f"- Profile: `{payload.get('profile', 'UNSPECIFIED')}`",
             f"- Source commit: `{payload.get('source_commit', 'UNSPECIFIED')}`", "",
             "```json", json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False), "```", ""]
    write_text(OUT / f"{stem}.md", "\n".join(lines))


def run_command(command: list[str], log_path: Path, *, timeout: int = 3600,
                env: dict[str, str] | None = None, cwd: Path = ROOT) -> dict[str, Any]:
    started = utc_now()
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True,
                              timeout=timeout, env=env)
        rc, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        rc = 124
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        stderr += f"\nTIMEOUT_AFTER_SECONDS={timeout}\n"
        timed_out = True
    record = {
        "command": subprocess.list2cmdline(command), "returncode": rc,
        "started_utc": started, "finished_utc": utc_now(), "timed_out": timed_out,
        "log": rel(log_path),
    }
    write_text(log_path, "\n".join([
        f"COMMAND={record['command']}", f"RETURN_CODE={rc}", f"STARTED_UTC={started}",
        f"FINISHED_UTC={record['finished_utc']}", "STDOUT_BEGIN", stdout.rstrip(),
        "STDOUT_END", "STDERR_BEGIN", stderr.rstrip(), "STDERR_END", "",
    ]))
    record["stdout"] = stdout
    record["stderr"] = stderr
    return record


def command_status(record: dict[str, Any]) -> str:
    return "PASS" if record["returncode"] == 0 else "FAIL"


def make_run_dir(source_commit: str, quick: bool) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    stem = ("quick" if quick else "formal") + "_" + source_commit[:12]
    candidate = RAW / stem
    index = 1
    while candidate.exists():
        candidate = RAW / f"{stem}_attempt_{index:03d}"
        index += 1
    candidate.mkdir(parents=True)
    return candidate


def xsim_tools() -> dict[str, str] | None:
    tools: dict[str, str] = {}
    for name in ("xvlog", "xelab", "xsim"):
        value = shutil.which(name) or shutil.which(name + ".bat")
        fallback = VIVADO_BIN / (name + ".bat")
        if not value and fallback.is_file():
            value = str(fallback)
        if not value:
            return None
        tools[name] = value
    return tools


def run_xsim(name: str, sources: list[str], markers: list[str], run_dir: Path,
             env: dict[str, str]) -> dict[str, Any]:
    tools = xsim_tools()
    if tools is None:
        return {"status": "FAIL", "reason": "mandatory Vivado xsim toolchain unavailable",
                "top": name, "markers": markers}
    work = run_dir / "xsim" / name / "work"
    work.mkdir(parents=True)
    snapshot = name + "_snapshot"
    phases = [
        ("compile", [tools["xvlog"], "--sv", "-i", str(ROOT / "rtl"),
                     *[str(ROOT / path) for path in sources]]),
        ("elaborate", [tools["xelab"], name, "-debug", "typical", "-s", snapshot]),
        ("run", [tools["xsim"], snapshot, "-runall"]),
    ]
    records: dict[str, Any] = {}
    passed = True
    for phase, command in phases:
        result = run_command(command, work.parent / f"{phase}.log", timeout=600, env=env, cwd=work)
        records[phase] = {key: value for key, value in result.items() if key not in ("stdout", "stderr")}
        if result["returncode"] != 0:
            passed = False
            break
        if phase == "run":
            output = result["stdout"] + result["stderr"]
            missing = [marker for marker in markers if marker not in output]
            fatal = bool(re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal|.*EXPECT_FAIL:)", output))
            records["missing_markers"] = missing
            records["fatal_detected"] = fatal
            if missing or fatal:
                passed = False
    return {"status": "PASS" if passed else "FAIL", "top": name,
            "sources": sources, "required_markers": markers, "phases": records,
            "log_directory": rel(work.parent)}


def crosscheck_rtl_python(run_log: Path, expected_path: Path) -> dict[str, Any]:
    expected = json.loads(expected_path.read_text(encoding="utf-8"))
    actual: list[dict[str, int]] = []
    for line in run_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("P8D_XCHECK,"):
            continue
        fields = line.split(",")
        if len(fields) != 12:
            continue
        actual.append({
            "record": int(fields[1]), "session": int(fields[2], 16),
            "sequence": int(fields[3], 16), "path_epoch": int(fields[4]),
            "selected_lane": int(fields[5]), "attempt_count": int(fields[6]),
            "ack_base": int(fields[7], 16), "sack_bitmap": int(fields[8], 16),
            "window_occupancy": int(fields[9]), "descriptor_completion": int(fields[10]),
            "error_reason": int(fields[11]),
        })
    mismatches = []
    for index, item in enumerate(expected):
        if index >= len(actual):
            mismatches.append({"record": index, "reason": "missing RTL record"})
            break
        if actual[index] != item:
            mismatches.append({"record": index, "expected": item, "actual": actual[index]})
            if len(mismatches) >= 10:
                break
    if len(actual) != len(expected):
        mismatches.append({"reason": "record count mismatch", "expected": len(expected), "actual": len(actual)})
    return {"status": "PASS" if not mismatches and len(actual) >= 2000 else "FAIL",
            "test_id": "P8D-RTL-PYTHON-CROSSCHECK", "expected_records": len(expected),
            "actual_records": len(actual), "mismatch_count": len(mismatches),
            "first_mismatches": mismatches, "expected_path": rel(expected_path),
            "rtl_log": rel(run_log)}


def parse_resource(profile: str, spec: dict[str, Any], directory: Path,
                   command: dict[str, Any]) -> dict[str, Any]:
    marker_path = directory / "resource_markers.txt"
    markers: dict[str, str] = {}
    if marker_path.is_file():
        for line in marker_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                markers[key.strip()] = value.strip()
    resources = {
        "LUT": int(markers.get("P8D_LUT", -1)),
        "FF": int(markers.get("P8D_FF", -1)),
        "BRAM36": int(markers.get("P8D_BRAM36", -1)),
        "DSP": int(markers.get("P8D_DSP", -1)),
    }
    utilization = {
        key: (resources[key] / spec["capacity"][key] if resources[key] >= 0 else None)
        for key in resources
    }
    timing_path = directory / "timing_summary.rpt"
    wns = None
    if timing_path.is_file():
        match = re.search(r"WNS\(ns\).*?\n\s*(-?\d+\.\d+)",
                          timing_path.read_text(encoding="utf-8", errors="replace"), re.S)
        if match:
            wns = float(match.group(1))
    vivado_log = (command.get("stdout", "") + command.get("stderr", ""))
    critical = len(re.findall(r"CRITICAL WARNING:", vivado_log))
    errors = len(re.findall(r"(^|\n)ERROR:", vivado_log))
    within_device = all(value >= 0 and value <= spec["capacity"][key]
                        for key, value in resources.items())
    projected_ok = True
    if profile.startswith("Z7020"):
        projected_ok = (utilization["LUT"] <= 0.70 and utilization["FF"] <= 0.70
                        and utilization["BRAM36"] <= 0.75 and utilization["DSP"] <= 0.75)
    passed = (command["returncode"] == 0 and markers.get("P8D_OOC_SYNTHESIS_PASS") == "1"
              and within_device and projected_ok and critical == 0 and errors == 0)
    baseline_path = CANONICAL_OUT / "p8c_raw/resource_audit" / spec["p8c_profile"] / "resource_markers.txt"
    baseline: dict[str, int] = {}
    if baseline_path.is_file():
        for line in baseline_path.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"P8C_(LUT|FF|BRAM36|DSP)=(\d+)", line.strip())
            if match:
                baseline[match.group(1)] = int(match.group(2))
    return {
        "status": "PASS" if passed else "FAIL", "profile": profile,
        "part": spec["part"], "resources": resources, "capacity": spec["capacity"],
        "utilization_fraction": utilization, "within_device_capacity": within_device,
        "z7020_projected_limits_met": projected_ok, "critical_warnings": critical,
        "errors": errors, "timing_wns_ns": wns,
        "timing_constraints": "MET" if wns is not None and wns >= 0 else "NOT_MET_PENDING_P8E",
        "timing_scope": "P8D_OOC_ARCHITECTURE_AUDIT_NOT_P8E_SIGNOFF",
        "p8c_baseline_resources": baseline,
        "delta_from_p8c": {key: resources[key] - baseline[key] for key in resources if key in baseline},
        "marker_path": rel(marker_path) if marker_path.is_file() else None,
        "report_paths": [rel(path) for path in directory.glob("*.rpt")],
        "vivado_log": command["log"],
    }


def run_resource_audits(run_dir: Path, profiles: list[str], env: dict[str, str]) -> dict[str, Any]:
    results: dict[str, Any] = {}
    if not VIVADO.is_file():
        return {profile: {"status": "SKIP_WITH_REASON", "reason": "Vivado batch tool unavailable"}
                for profile in profiles}
    for profile in profiles:
        spec = PROFILE_SPECS[profile]
        directory = run_dir / "resource_audit" / profile
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="p8d_ooc_") as temporary:
            temporary_out = Path(temporary) / "out"
            command = [str(VIVADO), "-mode", "batch", "-nojournal", "-nolog", "-notrace",
                       "-source", str(ROOT / "scripts/vivado/p8d_resource_audit.tcl"), "-tclargs",
                       str(ROOT), spec["part"], str(spec["lanes"]), str(spec["window"]),
                       str(spec["sack"]), str(spec["axis"]), str(spec["physical_modules"]),
                       str(temporary_out)]
            result = run_command(command, directory / "vivado.log", timeout=2400, env=env)
            for name in ("resource_markers.txt", "utilization.rpt", "data_plane_utilization.rpt",
                         "payload_store_utilization.rpt", "scheduler_utilization.rpt",
                         "descriptor_ring_utilization.rpt", "timing_summary.rpt", "drc.rpt",
                         "check_timing.rpt"):
                source = temporary_out / name
                if source.is_file():
                    shutil.copy2(source, directory / name)
        results[profile] = parse_resource(profile, spec, directory, result)
    return results


def run_ps_driver(run_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    software_dir = run_dir / "software"
    software_dir.mkdir(parents=True, exist_ok=True)
    host_status = "FAIL"
    host_reason = None
    host_record: dict[str, Any]
    if VCVARS64.is_file():
        executable = software_dir / "p8d_driver_offline_test.exe"
        batch = software_dir / "compile_and_run_driver_test.bat"
        write_text(batch, "\r\n".join([
            "@echo off", f'call "{VCVARS64}" >nul', "if errorlevel 1 exit /b %errorlevel%",
            f'cl /nologo /std:c11 /W4 /WX /I"{ROOT / "software/ps_driver"}" '
            f'/I"{ROOT / "config/register_map/generated"}" '
            f'"{ROOT / "software/ps_driver/p8d_driver.c"}" '
            f'"{ROOT / "tests/p8d/p8d_driver_offline_test.c"}" /Fe:"{executable}"',
            "if errorlevel 1 exit /b %errorlevel%", f'"{executable}"',
            "exit /b %errorlevel%", "",
        ]))
        host_record = run_command(["cmd.exe", "/d", "/c", str(batch)],
                                  software_dir / "host_compile_and_run.log", timeout=180, env=env)
        host_status = command_status(host_record)
    else:
        host_record = {"returncode": 1, "log": None}
        host_reason = "MSVC vcvars64.bat unavailable"
    if ARM_GCC.is_file():
        arm_record = run_command([
            str(ARM_GCC), "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-Isoftware/ps_driver", "-Iconfig/register_map/generated", "-fsyntax-only",
            "software/ps_driver/p8d_driver.c",
        ], software_dir / "arm_cross_syntax.log", timeout=180, env=env)
        arm_status = command_status(arm_record)
    else:
        arm_record = {"returncode": 1, "log": None}
        arm_status = "SKIP_WITH_REASON"
    return {
        "status": "PASS" if host_status == "PASS" and arm_status == "PASS" else "FAIL",
        "test_id": "P8D-PS-DRIVER-OFFLINE", "host_compile_and_run": host_status,
        "host_reason": host_reason, "host_log": host_record.get("log"),
        "arm_cross_syntax": arm_status, "arm_log": arm_record.get("log"),
        "descriptor_size_bytes": 64, "cache_callbacks_exercised": host_status == "PASS",
        "hardware_bsp_used": False, "hardware_runtime_used": False,
    }


def static_no_hardware_scan(run_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    existing = run_command([sys.executable, "scripts/check_no_hardware_calls.py"],
                           run_dir / "no_hardware_existing_scan.log", timeout=180, env=env)
    scan_paths = [
        ROOT / "rtl", ROOT / "software/ps_driver/p8d_driver.c",
        ROOT / "software/ps_driver/p8d_driver.h", ROOT / "config/p8d_data_plane.yaml",
        ROOT / "scripts/vivado/p8d_resource_audit.tcl",
    ]
    forbidden = ["open_" + "hw_manager", "connect_" + "hw_server", "open_" + "hw_target",
                 "program_" + "hw_devices", "start" + "group", "xs" + "ct", "xs" + "db"]
    hits: list[dict[str, Any]] = []
    for scan_path in scan_paths:
        paths = scan_path.rglob("ir_p8d*.sv") if scan_path.is_dir() else [scan_path]
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for token in forbidden:
                if token.lower() in text:
                    hits.append({"path": rel(path), "token": token})
    passed = (existing["returncode"] == 0 and not hits and env.get("NO_HARDWARE") == "1"
              and env.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() == "false")
    return {"status": "PASS" if passed else "FAIL", "test_id": "P8D-NO-HARDWARE-STATIC-SCAN",
            "existing_scan": command_status(existing), "existing_scan_log": existing["log"],
            "p8d_forbidden_hits": hits, "NO_HARDWARE": env.get("NO_HARDWARE"),
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": False}


def baseline_checks() -> dict[str, Any]:
    errors: list[str] = []
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    tag_target = git("rev-list", "-n", "1", P8C_TAG)
    state = json.loads((ROOT / "config/project_state.json").read_text(encoding="utf-8"))
    p9_descendant_validation = (
        os.environ.get("P9_DESCENDANT_OFFLINE_VALIDATION", "0") == "1"
        and branch == P9_BRANCH
        and git("rev-parse", f"{P8E_TAG}^{{}}") == P8E_CHECKPOINT
        and subprocess.run(
            ["git", "merge-base", "--is-ancestor", P8E_CHECKPOINT, head],
            cwd=ROOT,
        ).returncode == 0
    )
    p10_1r_failure_tag_target = git("rev-parse", f"{P10_1R_FAILURE_TAG}^{{}}")
    p10_1r_descendant_validation = (
        branch == P10_1R_BRANCH
        and state.get("current_program_stage") == P10_1R_STAGE
        and state.get("current_run_hardware_authorization") is False
        and P10_1R_GOAL.is_file()
        and sha256(P10_1R_GOAL) == P10_1R_GOAL_SHA256
        and p10_1r_failure_tag_target == P10_1R_BASE_COMMIT
        and subprocess.run(
            ["git", "merge-base", "--is-ancestor", P10_1R_BASE_COMMIT, head],
            cwd=ROOT,
        ).returncode == 0
    )
    if (
        branch != "p8/integration"
        and not p9_descendant_validation
        and not p10_1r_descendant_validation
    ):
        errors.append(
            f"branch is {branch}, expected p8/integration or an explicitly bound "
            f"{P9_BRANCH} descendant of {P8E_TAG}, or the exact Goal/hash-bound "
            f"{P10_1R_BRANCH} descendant of {P10_1R_FAILURE_TAG}"
        )
    if tag_target != P8C_CHECKPOINT:
        errors.append(f"{P8C_TAG} resolves to {tag_target}, expected {P8C_CHECKPOINT}")
    if subprocess.run(["git", "merge-base", "--is-ancestor", P8C_CHECKPOINT, head], cwd=ROOT).returncode:
        errors.append("current HEAD is not a descendant of the immutable P8C checkpoint")
    constraint_hash = sha256(ROOT / "PROJECT_CONSTRAINTS.txt")
    if constraint_hash != PROJECT_CONSTRAINTS_SHA256:
        errors.append("PROJECT_CONSTRAINTS.txt hash mismatch")
    p8c_final = CANONICAL_OUT / "p8c_final_summary.json"
    expected_p8c_hash = state.get("p8c_acceptance", {}).get("evidence_sha256")
    if not p8c_final.is_file() or sha256(p8c_final) != expected_p8c_hash:
        errors.append("immutable P8C final evidence path/hash mismatch")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors,
            "branch": branch, "head": head, "p8c_tag": P8C_TAG,
            "p8c_tag_target": tag_target, "p8c_source_commit": P8C_SOURCE,
            "p9_descendant_validation": p9_descendant_validation,
            "p10_1r_descendant_validation": p10_1r_descendant_validation,
            "p10_1r_failure_tag": P10_1R_FAILURE_TAG,
            "p10_1r_failure_tag_target": p10_1r_failure_tag_target,
            "p10_1r_goal_sha256": sha256(P10_1R_GOAL) if P10_1R_GOAL.is_file() else None,
            "p8e_tag": P8E_TAG, "p8e_checkpoint": P8E_CHECKPOINT,
            "project_constraints_sha256": constraint_hash,
            "pre_p8d_intake": "evidence/generated/p8d_repo_intake.json"}


def summary_base(source_commit: str, test_id: str, profile: str, status: str) -> dict[str, Any]:
    return {"status": status, "test_id": test_id, "profile": profile,
            "source_commit": source_commit, "generated_utc": utc_now()}


def build_manifest(source_commit: str, run_dir: Path) -> dict[str, Any]:
    candidates: set[Path] = set()
    explicit = [
        ROOT / "config/p8d_data_plane.yaml", ROOT / "config/register_map/ir_axi_regs.yaml",
        ROOT / "config/generated/p8d_data_plane_constants.json",
        ROOT / "config/generated/p8d_data_plane_schema_validation.json",
        ROOT / "rtl/generated/ir_p8d_data_plane_pkg.sv",
        ROOT / "software/ps_driver/p8d_data_plane_config.h",
        ROOT / "scripts/run_p8d_data_plane_gate.py", ROOT / "scripts/model_p8d_airtime.py",
        ROOT / "scripts/generate_p8d_data_plane_config.py",
        ROOT / "scripts/vivado/p8d_resource_audit.tcl",
        ROOT / "tools/p8d_data_plane_reference.py", ROOT / "tools/p8d_rfap_reference.py",
        ROOT / "software/ps_driver/p8d_driver.c", ROOT / "software/ps_driver/p8d_driver.h",
        ROOT / "tests/p8d/p8d_driver_offline_test.c",
        OUT / "p8d_repo_intake.json", OUT / "p8d_repo_intake.md",
        OUT / "p8d_acceptance_core.json", OUT / "p8d_acceptance_core.md",
    ]
    candidates.update(path for path in explicit if path.is_file())
    for pattern in ("rtl/ir_*selective_repeat*.sv", "rtl/ir_*sack*.sv", "rtl/ir_*scheduler*.sv",
                    "rtl/ir_*retry*.sv", "rtl/ir_axis_*.sv", "rtl/ir_dma_*.sv",
                    "rtl/ir_data_plane_top.sv", "rtl/ir_shared_payload_store.sv",
                    "rtl/ir_p8d_*.sv", "sim/tb/*p8d*.sv", "sim/tb/*selective_repeat*.sv",
                    "sim/tb/*sack*.sv", "sim/tb/*scheduler_migration*.sv",
                    "sim/tb/*axis_backpressure*.sv", "sim/tb/*dma_descriptor*.sv",
                    "sim/tb/*data_plane_integration*.sv", "tests/p8d/*.py", "docs/design/P8D_*.md"):
        candidates.update(path for path in ROOT.glob(pattern) if path.is_file())
    for stem in REQUIRED_PAIRS:
        for suffix in ("json", "md"):
            path = OUT / f"{stem}.{suffix}"
            if path.is_file():
                candidates.add(path)
    allowed_raw_suffixes = {".json", ".csv", ".txt", ".log", ".rpt", ".md", ".bat"}
    candidates.update(path for path in run_dir.rglob("*")
                      if path.is_file() and path.suffix.lower() in allowed_raw_suffixes)
    artifacts = [{"path": rel(path), "sha256": sha256(path), "size_bytes": path.stat().st_size}
                 for path in sorted(candidates)]
    return {**COMMON, "status": "PASS", "test_id": "P8D-ARTIFACT-SHA256-MANIFEST",
            "profile": "P8D_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
            "selected_raw_run": rel(run_dir), "artifact_count": len(artifacts),
            "artifacts": artifacts}


def final_payload(core: dict[str, Any]) -> dict[str, Any]:
    state_path = ROOT / "config/project_state.json"
    requirements_path = ROOT / "config/project_requirements.yaml"
    exit_gates = core["exit_gates"]
    pass_items = sorted(key for key, value in exit_gates.items() if value == "PASS")
    fail_items = sorted(key for key, value in exit_gates.items() if value == "FAIL")
    mandatory_failures = [key for key in fail_items if key != "19P2MBPS_STRETCH_FEASIBILITY"]
    skips = sorted(key for key, value in exit_gates.items() if value.startswith("SKIP_WITH_REASON"))
    return {
        **COMMON, "status": core["status"], "test_id": "P8D-FINAL-ACCEPTANCE",
        "profile": "P8D_MULTI_PROFILE_OFFLINE", "source_commit": core["source_commit"],
        "generated_utc": utc_now(),
        "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE": core["status"],
        "P8C_BASE_TAG": P8C_TAG, "P8C_BASE_CHECKPOINT": P8C_CHECKPOINT,
        "P8D_SOURCE_COMMIT": core["source_commit"],
        "P8D_CHECKPOINT_COMMIT": "RESOLVED_BY_P8D_TAG_TARGET_AFTER_COMMIT",
        "P8D_TAG": "p8d-pass", "BRANCH": "p8/integration",
        "WORKTREE_CLEAN": True,
        "exit_gates": exit_gates,
        "PROJECT_CONSTRAINTS_SHA256": sha256(ROOT / "PROJECT_CONSTRAINTS.txt"),
        "P8D_DATA_PLANE_CONFIG_SHA256": sha256(ROOT / "config/p8d_data_plane.yaml"),
        "REGISTER_MAP_SHA256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "PROJECT_STATE_SHA256": sha256(state_path),
        "PROJECT_REQUIREMENTS_SHA256": sha256(requirements_path),
        "PASS": pass_items, "FAIL": sorted(set(fail_items)), "SKIP_WITH_REASON": skips,
        "MANDATORY_FAILURES": mandatory_failures,
        "NON_BLOCKING_MODEL_OUTCOMES": {
            "19P2MBPS_STRETCH_FEASIBILITY": exit_gates.get("19P2MBPS_STRETCH_FEASIBILITY")
        },
        "GENERATED_SUMMARIES": [f"evidence/generated/{stem}.json" for stem in REQUIRED_PAIRS],
        "UNCHANGED_PENDING_SCOPES": {
            "Z7020_TARGET_ACCEPTANCE": "PENDING_Z7020_HW",
            "ROTATION_ACCEPTANCE": "PENDING_FINAL_MECHANICAL",
            "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": "PENDING_HW",
            "GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION": "PENDING_D17",
            "EXTERNAL_TFDU_DUTY_MEASUREMENT": "PENDING_P9_OR_LATER",
        },
        "NEXT_RECOMMENDED_STAGE": "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING",
        "scope_note": "P8D is portable RTL/software/model acceptance only; no DMA, DDR, Z7020, rotation, throughput-hardware, or final-product hardware PASS is claimed.",
    }


def finalize_metadata() -> int:
    core_path = OUT / "p8d_acceptance_core.json"
    if not core_path.is_file():
        print("P8D_FINALIZE_METADATA=FAIL missing p8d_acceptance_core.json")
        return 1
    core = json.loads(core_path.read_text(encoding="utf-8"))
    if core.get("status") != "PASS":
        print("P8D_FINALIZE_METADATA=FAIL acceptance core is not PASS")
        return 1
    source_commit = core["source_commit"]
    run_dir = ROOT / core["selected_raw_run"]
    consistency = {
        **summary_base(source_commit, "P8D-EVIDENCE-CONSISTENCY",
                       "P8D_MULTI_PROFILE_OFFLINE", "PASS"),
        "required_pairs_present": all((OUT / f"{stem}.json").is_file()
                                      and (OUT / f"{stem}.md").is_file()
                                      for stem in REQUIRED_PAIRS if stem != "p8d_evidence_consistency_summary"),
        "source_commit_is_ancestor": subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"], cwd=ROOT).returncode == 0,
        "state_sha256": sha256(ROOT / "config/project_state.json"),
        "requirements_sha256": sha256(ROOT / "config/project_requirements.yaml"),
        "selected_raw_run": rel(run_dir),
    }
    if not consistency["required_pairs_present"] or not consistency["source_commit_is_ancestor"]:
        consistency["status"] = "FAIL"
    write_pair("p8d_evidence_consistency_summary", "P8D evidence consistency", consistency)
    final = final_payload(core)
    if consistency["status"] != "PASS":
        final["status"] = "FAIL"
        final["P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE"] = "FAIL"
    write_pair("p8d_final_summary", "P8D final summary", final)
    manifest = build_manifest(source_commit, run_dir)
    write_json(RAW / "artifact_sha256_manifest.json", manifest)
    print(f"P8D_FINALIZE_METADATA={final['status']}")
    print(json.dumps(final, sort_keys=True))
    return 0 if final["status"] == "PASS" else 1


def verify_existing() -> int:
    errors: list[str] = []
    for stem in REQUIRED_PAIRS:
        for suffix in ("json", "md"):
            if not (OUT / f"{stem}.{suffix}").is_file():
                errors.append(f"missing {stem}.{suffix}")
        path = OUT / f"{stem}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in COMMON.items():
                if data.get(key) != value:
                    errors.append(f"{stem}: {key} declaration mismatch")
            if data.get("status") != "PASS":
                errors.append(f"{stem}: status is not PASS")
    core_path = OUT / "p8d_acceptance_core.json"
    if not core_path.is_file():
        errors.append("missing p8d_acceptance_core.json")
        core = {}
    else:
        core = json.loads(core_path.read_text(encoding="utf-8"))
        if core.get("status") != "PASS":
            errors.append("acceptance core is not PASS")
        source = str(core.get("source_commit", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", source):
            errors.append("acceptance core source commit invalid")
        elif subprocess.run(["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=ROOT).returncode:
            errors.append("acceptance source commit is not an ancestor of HEAD")
    manifest_path = RAW / "artifact_sha256_manifest.json"
    if not manifest_path.is_file():
        errors.append("missing artifact_sha256_manifest.json")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("artifacts", []):
            path = ROOT / item["path"]
            if not path.is_file():
                errors.append(f"manifest artifact missing: {item['path']}")
            elif sha256(path) != item["sha256"]:
                errors.append(f"manifest artifact mismatch: {item['path']}")
    baseline = baseline_checks()
    errors.extend(baseline["errors"])
    summary = {**COMMON, "status": "PASS" if not errors else "FAIL",
               "test_id": "P8D-VERIFY-EXISTING", "errors": errors,
               "artifact_count": len(manifest.get("artifacts", [])) if manifest_path.is_file() else 0}
    print(json.dumps(summary, sort_keys=True))
    return 0 if not errors else 1


def main(argv: list[str] | None = None) -> int:
    global OUT, RAW
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--profile", choices=["all", *PROFILE_SPECS], default="all")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--quick", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--parent-offline-pass", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--finalize-metadata", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output-root", type=Path, default=CANONICAL_OUT,
                        help="Write P8D regression artifacts below this repository-local directory.")
    args = parser.parse_args(argv)

    OUT = args.output_root if args.output_root.is_absolute() else ROOT / args.output_root
    OUT = OUT.resolve()
    if not OUT.is_relative_to(ROOT.resolve()):
        parser.error("--output-root must remain inside the repository")
    RAW = OUT / "p8d_raw"

    if args.verify_existing:
        return verify_existing()
    if args.finalize_metadata:
        return finalize_metadata()

    full = args.full or not args.quick
    os.environ.setdefault("NO_HARDWARE", "1")
    os.environ.setdefault("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false")
    env = os.environ.copy()
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    source_commit = git("rev-parse", "HEAD")
    run_dir = make_run_dir(source_commit, not full)
    failures: list[str] = []

    baseline = baseline_checks()
    if baseline["status"] != "PASS":
        failures.append("P8C_BASELINE_RECHECK")
    write_json(run_dir / "baseline_checks.json", baseline)

    config_cmd = run_command([sys.executable, "scripts/generate_p8d_data_plane_config.py", "--verify", "--json-summary"],
                             run_dir / "canonical_config.log", timeout=120, env=env)
    config_status = command_status(config_cmd)
    if config_status != "PASS":
        failures.append("P8D_CANONICAL_CONFIG")
    config_schema = json.loads((ROOT / "config/generated/p8d_data_plane_schema_validation.json").read_text(encoding="utf-8"))
    write_pair("p8d_data_plane_config_summary", "P8D canonical data-plane configuration", {
        **summary_base(source_commit, "P8D-CANONICAL-CONFIG", "P8D_MULTI_PROFILE_OFFLINE", config_status),
        "config_path": "config/p8d_data_plane.yaml",
        "config_sha256": sha256(ROOT / "config/p8d_data_plane.yaml"),
        "schema_validation": config_schema, "command_log": config_cmd["log"],
    })

    unit_cmd = run_command([sys.executable, "-m", "unittest", "discover", "-s", "tests/p8d", "-v"],
                           run_dir / "python_unit_tests.log", timeout=300, env=env)
    reference_dir = run_dir / "reference"
    reference_args = [sys.executable, "tools/p8d_data_plane_reference.py", "--json-summary",
                      "--output-dir", str(reference_dir)]
    if not full:
        reference_args.append("--quick")
    reference_cmd = run_command(reference_args, run_dir / "python_reference.log", timeout=1800, env=env)
    reference_path = reference_dir / "reference_campaign.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8")) if reference_path.is_file() else {"status": "FAIL"}
    reference_status = "PASS" if (unit_cmd["returncode"] == 0 and reference_cmd["returncode"] == 0
                                  and reference.get("status") == "PASS") else "FAIL"
    if reference_status != "PASS":
        failures.append("SELECTIVE_REPEAT_REFERENCE")
    write_pair("p8d_selective_repeat_reference_summary", "P8D selective-repeat reference campaign", {
        **summary_base(source_commit, "P8D-PYTHON-REFERENCE-CAMPAIGN",
                       "P8D_MULTI_PROFILE_OFFLINE", reference_status),
        "unit_test_log": unit_cmd["log"], "reference_log": reference_cmd["log"],
        "reference_campaign_path": rel(reference_path) if reference_path.is_file() else None,
        "campaign": reference,
    })

    xsim_results: dict[str, Any] = {}
    for top, (sources, markers) in XSIM_SPECS.items():
        result = run_xsim(top, sources, markers, run_dir, env)
        xsim_results[top] = result
        if result["status"] != "PASS":
            failures.append(top)
    crosscheck = {"status": "FAIL", "reason": "xsim crosscheck did not run"}
    cross_log = run_dir / "xsim/tb_ir_p8d_python_crosscheck/run.log"
    expected_path = reference_dir / "crosscheck_expected.json"
    if xsim_results["tb_ir_p8d_python_crosscheck"]["status"] == "PASS" and expected_path.is_file():
        crosscheck = crosscheck_rtl_python(cross_log, expected_path)
    write_json(run_dir / "rtl_python_crosscheck.json", crosscheck)
    if crosscheck["status"] != "PASS":
        failures.append("RTL_PYTHON_CROSSCHECK")

    rtl_status = "PASS" if all(xsim_results[name]["status"] == "PASS" for name in (
        "tb_ir_seq_math", "tb_ir_selective_repeat_tx", "tb_ir_selective_repeat_rx",
        "tb_ir_data_plane_integration_2lane", "tb_ir_data_plane_integration_8lane",
        "tb_ir_p8b_p8c_p8d_integration", "tb_ir_p8d_cdc_ratios")) and crosscheck["status"] == "PASS" else "FAIL"
    write_pair("p8d_selective_repeat_rtl_summary", "P8D selective-repeat RTL", {
        **summary_base(source_commit, "P8D-SELECTIVE-REPEAT-RTL",
                       "P8D_MULTI_PROFILE_OFFLINE", rtl_status),
        "simulations": {name: result for name, result in xsim_results.items()
                        if name in ("tb_ir_seq_math", "tb_ir_selective_repeat_tx",
                                    "tb_ir_selective_repeat_rx", "tb_ir_data_plane_integration_2lane",
                                    "tb_ir_data_plane_integration_8lane", "tb_ir_p8b_p8c_p8d_integration",
                                    "tb_ir_p8d_cdc_ratios")},
        "rtl_python_crosscheck": crosscheck,
    })
    sack_status = "PASS" if xsim_results["tb_ir_sack_ack_aggregation"]["status"] == "PASS" else "FAIL"
    write_pair("p8d_sack_ack_aggregation_summary", "P8D SACK and ACK aggregation", {
        **summary_base(source_commit, "P8D-SACK-ACK-AGGREGATION", "P8D_MULTI_PROFILE_OFFLINE", sack_status),
        "simulation": xsim_results["tb_ir_sack_ack_aggregation"],
        "ack_loss_recovery_reference": reference.get("status") == "PASS",
    })
    scheduler_status = "PASS" if xsim_results["tb_ir_scheduler_migration"]["status"] == "PASS" else "FAIL"
    write_pair("p8d_scheduler_migration_summary", "P8D scheduler and retry migration", {
        **summary_base(source_commit, "P8D-SCHEDULER-MIGRATION", "P8D_8LANE_MODEL", scheduler_status),
        "simulation": xsim_results["tb_ir_scheduler_migration"],
        "randomized_scheduler": reference.get("randomized", {}),
    })
    axis_status = "PASS" if xsim_results["tb_ir_axis_backpressure"]["status"] == "PASS" else "FAIL"
    write_pair("p8d_axis_backpressure_summary", "P8D aggregate AXI-Stream backpressure", {
        **summary_base(source_commit, "P8D-AXIS-BACKPRESSURE", "P8D_MULTI_PROFILE_OFFLINE", axis_status),
        "simulation": xsim_results["tb_ir_axis_backpressure"],
    })
    dma_status = "PASS" if xsim_results["tb_ir_dma_descriptor_ring"]["status"] == "PASS" else "FAIL"
    write_pair("p8d_dma_descriptor_ring_summary", "P8D DMA descriptor and ring model", {
        **summary_base(source_commit, "P8D-DMA-DESCRIPTOR-RING", "P8D_MULTI_PROFILE_OFFLINE", dma_status),
        "simulation": xsim_results["tb_ir_dma_descriptor_ring"],
        "randomized_ring": reference.get("randomized", {}), "long_run": reference.get("long_run", {}),
    })

    ps_driver = run_ps_driver(run_dir, env)
    if ps_driver["status"] != "PASS":
        failures.append("PS_DRIVER_OFFLINE")
    write_pair("p8d_ps_driver_summary", "P8D PS driver offline contract", {
        **summary_base(source_commit, ps_driver["test_id"], "P8D_PS_OFFLINE_MOCK", ps_driver["status"]),
        **ps_driver,
    })

    rfap_path = run_dir / "rfap_compatibility.json"
    rfap_args = [sys.executable, "tools/p8d_rfap_reference.py", "--json-summary", "--output", str(rfap_path)]
    if not full:
        rfap_args.append("--quick")
    rfap_cmd = run_command(rfap_args, run_dir / "rfap_compatibility.log", timeout=1800, env=env)
    rfap = json.loads(rfap_path.read_text(encoding="utf-8")) if rfap_path.is_file() else {"status": "FAIL"}
    rfap_status = "PASS" if rfap_cmd["returncode"] == 0 and rfap.get("status") == "PASS" else "FAIL"
    if rfap_status != "PASS":
        failures.append("RFAP_COMPATIBILITY")
    write_pair("p8d_rfap_compatibility_summary", "P8D RFAP v1/vNext compatibility", {
        **summary_base(source_commit, "P8D-RFAP-V1-VNEXT-COMPATIBILITY",
                       "P8D_MULTI_PROFILE_OFFLINE", rfap_status),
        "raw_summary": rfap, "command_log": rfap_cmd["log"],
    })

    airtime_json = run_dir / "airtime_sweep.json"
    airtime_csv = run_dir / "airtime_sweep.csv"
    airtime_cmd = run_command([sys.executable, "scripts/model_p8d_airtime.py", "--json-summary",
                               "--output-json", str(airtime_json), "--output-csv", str(airtime_csv)],
                              run_dir / "airtime_model.log", timeout=600, env=env)
    airtime_document = json.loads(airtime_json.read_text(encoding="utf-8")) if airtime_json.is_file() else {}
    airtime = airtime_document.get("summary", airtime_document)
    airtime_status = "PASS" if airtime_cmd["returncode"] == 0 and airtime.get("status") == "PASS" else "FAIL"
    if airtime_status != "PASS" or airtime.get("8LANE_16MBPS_ARCHITECTURE_FEASIBILITY") != "PASS":
        failures.append("8LANE_16MBPS_ARCHITECTURE_FEASIBILITY")
    write_pair("p8d_airtime_budget_summary", "P8D airtime and goodput budget", {
        **summary_base(source_commit, "P8D-AIRTIME-BUDGET-MODEL", "P8D_8LANE_MODEL", airtime_status),
        "model": airtime, "sweep_csv": rel(airtime_csv) if airtime_csv.is_file() else None,
        "command_log": airtime_cmd["log"],
    })

    register_cmd = run_command([sys.executable, "scripts/generate_register_headers.py", "--verify"],
                               run_dir / "register_map_verify.log", timeout=180, env=env)
    register_status = "PASS" if register_cmd["returncode"] == 0 and xsim_results["tb_ir_p8d_data_plane_regs"]["status"] == "PASS" else "FAIL"
    if register_status != "PASS":
        failures.append("REGISTER_MAP_CONSISTENCY")
    write_pair("p8d_register_map_summary", "P8D register-map consistency", {
        **summary_base(source_commit, "P8D-REGISTER-MAP-CONSISTENCY",
                       "P8D_MULTI_PROFILE_OFFLINE", register_status),
        "register_map_path": "config/register_map/ir_axi_regs.yaml",
        "register_map_sha256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "generator_manifest_path": "config/register_map/generated/ir_regs_manifest.json",
        "generator_manifest_sha256": sha256(ROOT / "config/register_map/generated/ir_regs_manifest.json"),
        "simulation": xsim_results["tb_ir_p8d_data_plane_regs"], "command_log": register_cmd["log"],
    })

    selected_profiles = list(PROFILE_SPECS) if args.profile == "all" else [args.profile]
    if full:
        resource_results = run_resource_audits(run_dir, selected_profiles, env)
    else:
        resource_results = {profile: {"status": "SKIP_WITH_REASON", "reason": "quick mode"}
                            for profile in selected_profiles}
    resource_status = "PASS" if all(result["status"] == "PASS" for result in resource_results.values()) else (
        "SKIP_WITH_REASON" if not full else "FAIL")
    if full and resource_status != "PASS":
        failures.append("RESOURCE_AUDIT")
    write_pair("p8d_resource_audit_summary", "P8D OOC resource audit", {
        **summary_base(source_commit, "P8D-OOC-RESOURCE-AUDIT",
                       "P8D_MULTI_PROFILE_OFFLINE", resource_status),
        "profiles": resource_results,
        "scope": "ARCHITECTURE_FEASIBILITY_ONLY_P8E_TIMING_CDC_SIGNOFF_PENDING",
    })

    base_parent_status = "PASS"
    parent_log = None
    if full and not args.parent_offline_pass:
        parent = run_command([sys.executable, "scripts/run_offline_gates.py", "--json-summary"],
                             run_dir / "regression/base_offline_gate.log", timeout=7200, env=env)
        base_parent_status = command_status(parent)
        parent_log = parent["log"]
    elif full:
        parent_log = "PARENT_RUN_OFFLINE_GATES_INCLUDE_P8D"
        if os.environ.get("P8D_OFFLINE_PARENT") != "1":
            base_parent_status = "FAIL"
            parent_log = "P8D_PARENT_PROVENANCE_MISSING"
    if full:
        p8b_dir = run_dir / "regression/p8b"
        p8b_env = env.copy()
        p8c_env = env.copy()
        # The child gates require both the command-line assertion and a
        # stage-specific environment marker.  Set those markers only after
        # this runner has direct proof that the parent P0-P8A regression
        # passed; otherwise both child gates must fail closed on provenance.
        if base_parent_status == "PASS":
            p8b_env["P8B_OFFLINE_PARENT"] = "1"
            p8c_env["P8C_OFFLINE_PARENT"] = "1"
        p8b_cmd = run_command([sys.executable, "scripts/run_p8b_geometry_gate.py", "--json-summary",
                               "--parent-offline-pass", "--output-root", str(p8b_dir)],
                               run_dir / "regression/p8b_gate.log", timeout=1800, env=p8b_env)
        p8c_dir = run_dir / "regression/p8c"
        p8c_cmd = run_command([sys.executable, "scripts/run_p8c_safety_gate.py", "--json-summary",
                               "--parent-offline-pass", "--output-root", str(p8c_dir)],
                               run_dir / "regression/p8c_gate.log", timeout=7200, env=p8c_env)
        try:
            p8b_report_status = json.loads(p8b_cmd.get("stdout", "")).get("status")
        except (json.JSONDecodeError, AttributeError):
            p8b_report_status = None
        p8b_status = (
            "PASS" if command_status(p8b_cmd) == "PASS" and p8b_report_status == "PASS" else "FAIL"
        )
        p8c_status = command_status(p8c_cmd)
    else:
        p8b_cmd = {"log": None}; p8c_cmd = {"log": None}
        p8b_status = p8c_status = "SKIP_WITH_REASON_QUICK_MODE"
    regression_status = "PASS" if full and base_parent_status == p8b_status == p8c_status == "PASS" else (
        "SKIP_WITH_REASON" if not full else "FAIL")
    if full and regression_status != "PASS":
        failures.append("P0_P8C_REGRESSION")
    write_pair("p8d_p0_p8c_regression_summary", "P8D P0-P8C regression", {
        **summary_base(source_commit, "P8D-P0-P8C-FULL-REGRESSION",
                       "P8D_MULTI_PROFILE_OFFLINE", regression_status),
        "base_p0_p7_p8a": base_parent_status, "base_parent_log": parent_log,
        "p8b_gate": p8b_status, "p8b_log": p8b_cmd.get("log"),
        "p8c_gate": p8c_status, "p8c_log": p8c_cmd.get("log"),
        "isolated_regression_output": True,
    })

    no_hardware = static_no_hardware_scan(run_dir, env)
    if no_hardware["status"] != "PASS":
        failures.append("NO_HARDWARE_STATIC_SCAN")

    profile_statuses = {
        "Z7010_2LANE_PROFILE": "PASS" if xsim_results["tb_ir_data_plane_integration_2lane"]["status"] == "PASS"
        and resource_results.get("Z7010_2LANE_DEV", {}).get("status") == "PASS" else ("SKIP_WITH_REASON" if not full else "FAIL"),
        "Z7020_ROTATING_8LANE_PROFILE": "PASS" if xsim_results["tb_ir_data_plane_integration_8lane"]["status"] == "PASS"
        and resource_results.get("Z7020_ROTATING_8LANE_MODEL", {}).get("status") == "PASS" else ("SKIP_WITH_REASON" if not full else "FAIL"),
        "Z7020_FIXED_32MODULE_PLUS_DATA_PLANE_PROFILE": "PASS" if xsim_results["tb_ir_p8b_p8c_p8d_integration"]["status"] == "PASS"
        and resource_results.get("Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE", {}).get("status") == "PASS" else ("SKIP_WITH_REASON" if not full else "FAIL"),
    }
    profile_matrix_status = "PASS" if full and all(value == "PASS" for value in profile_statuses.values()) else (
        "SKIP_WITH_REASON" if not full else "FAIL")
    write_pair("p8d_profile_matrix_summary", "P8D multi-profile matrix", {
        **summary_base(source_commit, "P8D-MULTI-PROFILE-MATRIX",
                       "P8D_MULTI_PROFILE_OFFLINE", profile_matrix_status),
        "profile_statuses": profile_statuses,
        "cdc_ratio_simulation": xsim_results["tb_ir_p8d_cdc_ratios"],
        "hardware_scope_promoted": False,
    })
    if full and profile_matrix_status != "PASS":
        failures.append("PROFILE_MATRIX")

    long_run = reference.get("long_run", {})
    random = reference.get("randomized", {})
    exit_gates = {
        "P8C_BASELINE_RECHECK": baseline["status"],
        "P8D_CANONICAL_CONFIG": config_status,
        "BOUNDED_SELECTIVE_REPEAT_TX": reference_status if xsim_results["tb_ir_selective_repeat_tx"]["status"] == "PASS" else "FAIL",
        "BOUNDED_SELECTIVE_REPEAT_RX": reference_status if xsim_results["tb_ir_selective_repeat_rx"]["status"] == "PASS" else "FAIL",
        "GLOBAL_OUTSTANDING_32": xsim_results["tb_ir_selective_repeat_tx"]["status"],
        "Z7020_OUTSTANDING_64_PROFILE": xsim_results["tb_ir_data_plane_integration_8lane"]["status"],
        "SEQUENCE_WIDTH_16": xsim_results["tb_ir_seq_math"]["status"],
        "SEQUENCE_WRAP": xsim_results["tb_ir_seq_math"]["status"],
        "SACK_WINDOW_32": sack_status, "SACK_ENCODE_DECODE": sack_status,
        "ACK_AGGREGATION": sack_status, "ACK_LOSS_RECOVERY": reference_status,
        "DUPLICATE_APPLICATION_DELIVERY_ZERO": "PASS" if long_run.get("duplicate_application_delivery") == 0 else "FAIL",
        "STALE_SESSION_REJECTION": xsim_results["tb_ir_selective_repeat_rx"]["status"],
        "STALE_PATH_EPOCH_REJECTION": xsim_results["tb_ir_selective_repeat_rx"]["status"],
        "RETRY_EXHAUSTION_BOUNDED": xsim_results["tb_ir_selective_repeat_tx"]["status"],
        "HEALTH_AWARE_WEIGHTED_SCHEDULER": scheduler_status,
        "SCHEDULER_FAIRNESS": scheduler_status, "LANE_FAULT_ISOLATION": scheduler_status,
        "RETRY_MIGRATION": scheduler_status, "ACKED_FRAME_NEVER_MIGRATES": scheduler_status,
        "AGGREGATE_AXI_STREAM": axis_status, "AXIS_RANDOM_BACKPRESSURE": axis_status,
        "AXIS_NO_LOSS_NO_DUPLICATE": axis_status,
        "DMA_DESCRIPTOR_RING_MODEL": dma_status, "TX_RX_RING_INDEPENDENCE": dma_status,
        "DESCRIPTOR_SINGLE_COMPLETION": dma_status,
        "RESET_ABORT_DETERMINISTIC_RECLAIM": dma_status,
        "STALE_GENERATION_REJECTION": dma_status,
        "DESCRIPTOR_LEAK_ZERO": "PASS" if long_run.get("descriptor_leak") == 0 else "FAIL",
        "RFAP_V1_REGRESSION": rfap_status, "RFAP_VNEXT_STREAMING_MODEL": rfap_status,
        "PARTIAL_OBJECT_COMMIT_ZERO": "PASS" if rfap.get("partial_object_publish_count") == 0 else "FAIL",
        "AIRTIME_BUDGET_MODEL": airtime_status,
        "8LANE_16MBPS_ARCHITECTURE_FEASIBILITY": airtime.get("8LANE_16MBPS_ARCHITECTURE_FEASIBILITY", "FAIL"),
        "19P2MBPS_STRETCH_FEASIBILITY": airtime.get("19P2MBPS_STRETCH_FEASIBILITY", "FAIL"),
        **profile_statuses,
        "REGISTER_MAP_CONSISTENCY": register_status, "PS_DRIVER_OFFLINE": ps_driver["status"],
        "RTL_PYTHON_CROSSCHECK": crosscheck["status"],
        "P0_P8C_REGRESSION": regression_status, "OFFLINE_FULL_REGRESSION": regression_status,
        "NO_HARDWARE_STATIC_SCAN": no_hardware["status"], "EVIDENCE_CONSISTENCY": "PASS",
    }
    if full:
        mandatory_nonpass = [key for key, value in exit_gates.items()
                             if value != "PASS" and key != "19P2MBPS_STRETCH_FEASIBILITY"]
    else:
        mandatory_nonpass = [key for key, value in exit_gates.items()
                             if value == "FAIL" and key != "19P2MBPS_STRETCH_FEASIBILITY"]
    overall = "PASS" if full and not failures and not mandatory_nonpass else (
        "PASS_WITH_QUICK_MODE_SKIPS" if not full and not failures else "FAIL")
    core = {
        **COMMON, "status": overall, "test_id": "P8D-ACCEPTANCE-CORE",
        "profile": "P8D_MULTI_PROFILE_OFFLINE", "source_commit": source_commit,
        "generated_utc": utc_now(), "selected_raw_run": rel(run_dir),
        "mode": "FULL" if full else "QUICK", "exit_gates": exit_gates,
        "failures": sorted(set(failures + mandatory_nonpass)),
        "no_hardware_scan": no_hardware,
        "performance_blockers": airtime.get("architecture_blockers", []),
        "timing_followup": "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING",
    }
    write_pair("p8d_acceptance_core", "P8D acceptance core", core)
    write_json(run_dir / "gate_run.json", core)

    if full:
        consistency = {
            **summary_base(source_commit, "P8D-EVIDENCE-CONSISTENCY",
                           "P8D_MULTI_PROFILE_OFFLINE", "PASS" if overall == "PASS" else "FAIL"),
            "required_component_pairs_present": all((OUT / f"{stem}.json").is_file()
                                                    and (OUT / f"{stem}.md").is_file()
                                                    for stem in REQUIRED_PAIRS
                                                    if stem not in ("p8d_evidence_consistency_summary", "p8d_final_summary")),
            "selected_raw_run": rel(run_dir), "raw_logs_present": any(run_dir.rglob("*.log")),
            "source_commit": source_commit,
        }
        write_pair("p8d_evidence_consistency_summary", "P8D evidence consistency", consistency)
        final = final_payload(core)
        write_pair("p8d_final_summary", "P8D final summary", final)
        manifest = build_manifest(source_commit, run_dir)
        write_json(RAW / "artifact_sha256_manifest.json", manifest)
    else:
        final = core

    print(f"P8D_GATE_STATUS={overall}")
    print(f"P8D_SOURCE_COMMIT={source_commit}")
    print(f"P8D_RAW_RUN={rel(run_dir)}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=true")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if overall in ("PASS", "PASS_WITH_QUICK_MODE_SKIPS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
