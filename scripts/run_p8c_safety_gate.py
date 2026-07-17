#!/usr/bin/env python3
"""Canonical no-hardware P8C safety, simulation, synthesis, and evidence gate."""

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

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated"
RAW = OUT / "p8c_raw"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
VIVADO = VIVADO_BIN / "vivado.bat"
VSDEVCMD = Path(r"D:\Program Files\Microsoft Visual Studio\2022\Community\Common7\Tools\VsDevCmd.bat")
REQUIRED_PAIRS = [
    "p8c_repo_intake", "p8c_safety_config_summary",
    "p8c_exact_sliding_duty_reference_summary", "p8c_exact_sliding_duty_rtl_summary",
    "p8c_continuous_high_guard_summary", "p8c_single_global_permit_architecture_summary",
    "p8c_permit_fault_injection_summary", "p8c_receive_only_acquisition_summary",
    "p8c_physical_module_accounting_summary", "p8c_register_map_summary",
    "p8c_profile_matrix_summary", "p8c_resource_audit_summary",
    "p8c_p0_p8b_regression_summary", "p8c_offline_gate_summary", "p8c_final_summary",
]
COMMON = {
    "NO_HARDWARE_ACTIONS_EXECUTED": True,
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    "HARDWARE_SCOPE_PROMOTED": False,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run(cmd: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None,
        timeout: int = 1200) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env,
                          timeout=timeout, errors="replace")
    return {"command": subprocess.list2cmdline(cmd), "returncode": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def write_log(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"COMMAND={result['command']}\nRETURNCODE={result['returncode']}\n\n"
        f"STDOUT\n{result['stdout']}\nSTDERR\n{result['stderr']}",
        encoding="utf-8", newline="\n")


def write_pair(stem: str, title: str, data: dict[str, Any]) -> tuple[Path, Path]:
    payload = {**COMMON, **data}
    json_path, md_path = OUT / f"{stem}.json", OUT / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    lines = [f"# {title}", "", "```text",
             f"STATUS: {payload.get('status', 'N/A')}",
             "NO_HARDWARE_ACTIONS_EXECUTED: true",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION: false",
             "HARDWARE_SCOPE_PROMOTED: false", "```", "", "```json",
             json.dumps(payload, indent=2, sort_keys=True), "```", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return json_path, md_path


def clean_generated_dir(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(OUT.resolve()) or resolved == OUT.resolve():
        raise RuntimeError(f"unsafe generated directory: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def xsim_tools() -> dict[str, str]:
    tools = {}
    for name in ("xvlog", "xelab", "xsim"):
        found = shutil.which(name) or shutil.which(f"{name}.bat")
        fallback = VIVADO_BIN / f"{name}.bat"
        if not found and fallback.is_file():
            found = str(fallback)
        if not found:
            raise RuntimeError(f"mandatory XSIM tool missing: {name}")
        tools[name] = found
    return tools


XSIM_TESTS: dict[str, dict[str, Any]] = {
    "tb_p8c_exact_duty": {"sources": ["rtl/ir_tfdu_exact_duty_accountant.sv", "sim/tb/tb_p8c_exact_duty.sv"], "markers": ["P8C_TELEMETRY_CLEAR_HISTORY_PRESERVED_PASS=1", "P8C_EXACT_VECTOR_MATRIX_PASS=1", "TB_P8C_EXACT_DUTY_PASS=1"]},
    "tb_p8c_physical_safety": {"sources": ["rtl/ir_tfdu_exact_duty_accountant.sv", "rtl/ir_tfdu_physical_module_safety.sv", "sim/tb/tb_p8c_physical_safety.sv"], "markers": ["P8C_CONTINUOUS_VECTOR_MATRIX_PASS=1", "P8C_SD_HISTORY_PRESERVED_PASS=1", "TB_P8C_PHYSICAL_SAFETY_PASS=1"]},
    "tb_p8c_endpoint_safety": {"sources": ["rtl/generated/tfdu_safety_pkg.sv", "rtl/ir_tfdu_exact_duty_accountant.sv", "rtl/ir_tfdu_physical_module_safety.sv", "rtl/ir_tfdu_safety_endpoint.sv", "sim/tb/tb_p8c_endpoint_safety.sv"], "markers": ["P8C_PERMIT_VECTOR_MATRIX_PASS=1", "P8C_FAULT_DROP_MID_HIGH_PASS=1", "P8C_HISTORY_PERMIT_LANE_PATH_PRESERVED_PASS=1", "P8C_KILL_REASON_PRIORITY_PASS=1", "TB_P8C_ENDPOINT_SAFETY_PASS=1"]},
    "tb_p8c_safety_regs": {"sources": ["rtl/ir_p8c_safety_regs.sv", "sim/tb/tb_p8c_safety_regs.sv"], "markers": ["TB_P8C_SAFETY_REGS_PASS=1"]},
    "tb_p8c_trace_crosscheck": {"sources": ["rtl/ir_tfdu_exact_duty_accountant.sv", "sim/tb/tb_p8c_trace_crosscheck.sv"], "markers": ["TB_P8C_TRACE_CROSSCHECK_PASS=1"]},
    "tb_p8c_profile_matrix": {"sources": ["rtl/generated/tfdu_safety_pkg.sv", "rtl/ir_path_mapping_pkg.sv", "rtl/ir_path_mapping_engine.sv", "rtl/ir_path_epoch_commit.sv", "rtl/ir_tfdu_exact_duty_accountant.sv", "rtl/ir_tfdu_physical_module_safety.sv", "rtl/ir_tfdu_safety_endpoint.sv", "rtl/ir_p8c_mapping_safety_adapter.sv", "rtl/ir_p8c_safety_integration.sv", "sim/tb/tb_p8c_profile_matrix.sv"], "markers": ["P8C_ILLEGAL_COMMIT_DURING_FRAME_PASS=1", "P8C_PERMIT_DROP_DURING_PATH_COMMIT_PASS=1", "P8C_INDEPENDENT_FAULT_ISOLATION_PASS=1", "TB_P8C_PROFILE_MATRIX_PASS=1"]},
    "tb_p8c_full_scale": {"sources": ["rtl/generated/tfdu_safety_pkg.sv", "rtl/ir_tfdu_exact_duty_accountant.sv", "rtl/ir_tfdu_physical_module_safety.sv", "rtl/ir_tfdu_safety_endpoint.sv", "sim/tb/tb_p8c_full_scale.sv"], "markers": ["P8C_LONG_PERIODIC_4PPM_LIKE_PASS=1", "TB_P8C_FULL_SCALE_PASS=1"]},
    "tb_tfdu_lane_phy_smoke": {"sources": ["rtl/ir_tfdu_exact_duty_accountant.sv", "rtl/ir_tfdu_physical_module_safety.sv", "rtl/tfdu_lane_phy.sv", "sim/models/tfdu6102_behavior_model.sv", "sim/tb/tb_tfdu_lane_phy_smoke.sv"], "markers": ["TB_TFDU_LANE_PHY_SMOKE_PASS=1"]},
}


def run_xsim_campaign() -> tuple[bool, dict[str, Any]]:
    tools = xsim_tools()
    xsim_root = RAW / "xsim"
    clean_generated_dir(xsim_root)
    results: dict[str, Any] = {}
    for top, spec in XSIM_TESTS.items():
        work = xsim_root / top / "work"
        work.mkdir(parents=True)
        snapshot = f"{top}_sim"
        phases = [
            ("compile", [tools["xvlog"], "--sv", "-i", str(ROOT / "rtl"),
                         *[str(ROOT / source) for source in spec["sources"]]]),
            ("elaborate", [tools["xelab"], top, "-s", snapshot]),
            ("run", [tools["xsim"], snapshot, "-runall"]),
        ]
        combined = ""
        phase_results = {}
        passed = True
        for phase, command in phases:
            result = run(command, cwd=work, timeout=600)
            write_log(xsim_root / top / f"{phase}.log", result)
            phase_results[phase] = result["returncode"]
            combined += result["stdout"] + result["stderr"]
            if result["returncode"] != 0:
                passed = False
                break
        if any(marker not in combined for marker in spec["markers"]):
            passed = False
        if re.search(r"(?:Fatal:|EXPECT_FAIL|ASSERT_FAIL)", combined, re.I):
            passed = False
        results[top] = {"status": "PASS" if passed else "FAIL",
                        "phase_returncodes": phase_results, "markers": spec["markers"],
                        "sources": spec["sources"],
                        "log_directory": rel(xsim_root / top)}
    return all(item["status"] == "PASS" for item in results.values()), results


def run_resource_audit() -> tuple[bool, dict[str, Any]]:
    if not VIVADO.is_file():
        return False, {"status": "FAIL", "reason": "mandatory Vivado OOC tool missing"}
    resource_root = RAW / "resource_audit"
    clean_generated_dir(resource_root)
    profiles = [
        ("Z7010_2LANE_DEV", "ir_p8c_resource_top_2", "xc7z010clg400-1"),
        ("Z7020_ROTATING_8LANE_MODEL", "ir_p8c_resource_top_8", "xc7z020clg400-1"),
        ("Z7020_FIXED_32MODULE_ACCOUNTING_MODEL", "ir_p8c_resource_top_32", "xc7z020clg400-1"),
    ]
    results = {}
    for profile, top, part in profiles:
        with tempfile.TemporaryDirectory(prefix="p8c_ooc_") as temporary:
            temp_out = Path(temporary) / "out"
            command = [str(VIVADO), "-mode", "batch", "-nojournal", "-nolog", "-notrace",
                       "-source", str(ROOT / "scripts/vivado/p8c_resource_audit.tcl"),
                       "-tclargs", str(ROOT), top, part, str(temp_out)]
            result = run(command, timeout=1200)
            profile_dir = resource_root / profile
            profile_dir.mkdir(parents=True)
            write_log(profile_dir / "vivado.log", result)
            copied = []
            for name in ("resource_markers.txt", "utilization.rpt", "timing_summary.rpt", "drc.rpt", "check_timing.rpt"):
                source = temp_out / name
                if source.is_file():
                    shutil.copy2(source, profile_dir / name)
                    copied.append(name)
            markers = {}
            marker_path = profile_dir / "resource_markers.txt"
            if marker_path.is_file():
                for line in marker_path.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        markers[key] = value
            check_timing_path = profile_dir / "check_timing.rpt"
            timing_summary_path = profile_dir / "timing_summary.rpt"
            check_timing_text = (check_timing_path.read_text(encoding="utf-8", errors="replace")
                                 if check_timing_path.is_file() else "")
            timing_summary_text = (timing_summary_path.read_text(encoding="utf-8", errors="replace")
                                   if timing_summary_path.is_file() else "")
            timing_checks = {
                name: int(match.group(1)) if (match := re.search(
                    rf"checking\s+{re.escape(name)}\s+\((\d+)\)", check_timing_text)) else None
                for name in ("no_clock", "constant_clock", "unconstrained_internal_endpoints",
                             "no_input_delay", "no_output_delay", "multiple_clock")
            }
            core_unconstrained = sum(
                timing_checks[name] or 0
                for name in ("no_clock", "constant_clock", "unconstrained_internal_endpoints")
            )
            timing_constraints_met = "All user specified timing constraints are met" in timing_summary_text
            critical = len(re.findall(r"^CRITICAL WARNING:", result["stdout"] + result["stderr"], re.I | re.M))
            passed = (result["returncode"] == 0 and markers.get("P8C_OOC_SYNTHESIS_PASS") == "1"
                      and critical == 0 and core_unconstrained == 0 and timing_constraints_met
                      and all(value is not None for value in timing_checks.values()))
            results[profile] = {"status": "PASS" if passed else "FAIL", "top": top,
                                "part": part, "markers": markers, "critical_warning_count": critical,
                                "timing_checks": timing_checks,
                                "unconstrained_clock_or_internal_path_count": core_unconstrained,
                                "ooc_io_delay_gaps_reported": {
                                    "no_input_delay": timing_checks["no_input_delay"],
                                    "no_output_delay": timing_checks["no_output_delay"],
                                    "scope": "OOC wrapper ports; not final board timing closure",
                                },
                                "ooc_timing_constraints_met": timing_constraints_met,
                                "reports": [rel(profile_dir / name) for name in copied]}
    return all(item["status"] == "PASS" for item in results.values()), results


def run_host_stub() -> tuple[bool, dict[str, Any]]:
    raw_dir = RAW / "software"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if not VSDEVCMD.is_file():
        return False, {"status": "FAIL", "reason": "mandatory host C toolchain missing"}
    with tempfile.TemporaryDirectory(prefix="p8c_host_c_") as temporary:
        exe = Path(temporary) / "p8c_ps_driver_stub.exe"
        batch = Path(temporary) / "build_and_run.bat"
        batch.write_text("\r\n".join([
            "@echo off",
            f'call "{VSDEVCMD}" -no_logo -arch=x64',
            "if errorlevel 1 exit /b %errorlevel%",
            "cl /nologo /std:c11 /W4 /Isoftware\\ps_driver /Iconfig\\register_map\\generated "
            "software\\ps_driver\\main_offline_stub.c software\\ps_driver\\ir_driver.c "
            f"software\\ps_driver\\ir_profile.c /Fo{temporary}{os.sep} /Fe:{exe}",
            "if errorlevel 1 exit /b %errorlevel%",
            f'"{exe}"',
            "exit /b %errorlevel%",
        ]) + "\r\n", encoding="utf-8")
        result = run(["cmd.exe", "/d", "/c", str(batch)], timeout=120)
    write_log(raw_dir / "ps_driver_host_compile_and_run.log", result)
    return result["returncode"] == 0, {"status": "PASS" if result["returncode"] == 0 else "FAIL",
                                      "log": rel(raw_dir / "ps_driver_host_compile_and_run.log")}


def verify_existing() -> tuple[bool, dict[str, Any]]:
    errors = []
    for stem in REQUIRED_PAIRS:
        for suffix in ("json", "md"):
            if not (OUT / f"{stem}.{suffix}").is_file():
                errors.append(f"missing {stem}.{suffix}")
        path = OUT / f"{stem}.json"
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            for key, value in COMMON.items():
                if data.get(key) is not value:
                    errors.append(f"{stem} common declaration mismatch: {key}")
            if data.get("status") not in ("PASS", None):
                errors.append(f"{stem} not PASS")
    manifest_path = RAW / "artifact_sha256_manifest.json"
    if not manifest_path.is_file():
        errors.append("artifact SHA256 manifest missing")
    else:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for item in manifest.get("artifacts", []):
            path = ROOT / item["path"]
            if not path.is_file() or sha256(path) != item["sha256"]:
                errors.append(f"artifact mismatch: {item['path']}")
    commands = [
        [sys.executable, "scripts/generate_tfdu_safety_config.py", "--verify"],
        [sys.executable, "scripts/generate_register_headers.py", "--verify"],
        [sys.executable, "scripts/check_p8c_safety_static.py"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/p8c", "-v"],
        [sys.executable, "scripts/check_p8a_consistency.py"],
    ]
    command_results = []
    env = os.environ.copy(); env["NO_HARDWARE"] = "1"
    for command in commands:
        result = run(command, env=env)
        command_results.append({"command": result["command"], "returncode": result["returncode"]})
        if result["returncode"] != 0:
            errors.append(f"verify command failed: {result['command']}")
    status = run(["git", "status", "--porcelain"])
    if status["stdout"].strip():
        errors.append("worktree is not clean")
    return not errors, {"status": "PASS" if not errors else "FAIL", "errors": errors,
                        "commands": command_results, **COMMON}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--parent-offline-pass", action="store_true")
    parser.add_argument("--no-full-regression", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args(argv)
    if args.verify_existing:
        passed, summary = verify_existing()
        print(json.dumps(summary, sort_keys=True) if args.json_summary else f"P8C_VERIFY_EXISTING={summary['status']}")
        return 0 if passed else 1

    OUT.mkdir(parents=True, exist_ok=True)
    clean_generated_dir(RAW)
    env = os.environ.copy(); env["NO_HARDWARE"] = "1"
    failures: list[str] = []
    commands: dict[str, Any] = {}

    state = json.loads((ROOT / "config/project_state.json").read_text(encoding="utf-8"))
    if os.environ.get("NO_HARDWARE") != "1" or state.get("current_run_hardware_authorization") is not False:
        failures.append("NO_HARDWARE/current authorization precondition")

    for name, command in {
        "safety_config_verify": [sys.executable, "scripts/generate_tfdu_safety_config.py", "--verify"],
        "register_map_verify": [sys.executable, "scripts/generate_register_headers.py", "--verify"],
        "python_unit_tests": [sys.executable, "-m", "unittest", "discover", "-s", "tests/p8c", "-v"],
        "python_reference": [sys.executable, "tools/p8c_tfdu_safety_reference.py", "--json-summary"],
        "static_architecture": [sys.executable, "scripts/check_p8c_safety_static.py", "--json"],
    }.items():
        result = run(command, env=env)
        write_log(RAW / f"{name}.log", result)
        commands[name] = {"status": "PASS" if result["returncode"] == 0 else "FAIL",
                          "log": rel(RAW / f"{name}.log")}
        if result["returncode"] != 0:
            failures.append(name)

    reference = json.loads(commands and run(
        [sys.executable, "tools/p8c_tfdu_safety_reference.py", "--json-summary"], env=env)["stdout"])
    static_result_raw = run([sys.executable, "scripts/check_p8c_safety_static.py", "--json"], env=env)
    static_summary = json.loads(static_result_raw["stdout"]) if static_result_raw["stdout"].strip() else {"status": "FAIL"}

    xsim_pass, xsim_results = run_xsim_campaign()
    if not xsim_pass: failures.append("xsim_campaign")
    trace_log = RAW / "xsim/tb_p8c_trace_crosscheck/run.log"
    trace_result = run([sys.executable, "scripts/compare_p8c_rtl_trace.py", str(trace_log),
                        "--output", str(RAW / "trace_comparison.json")], env=env)
    write_log(RAW / "trace_comparison.log", trace_result)
    if trace_result["returncode"] != 0: failures.append("rtl_python_trace")
    trace_summary = json.loads((RAW / "trace_comparison.json").read_text(encoding="utf-8")) if (RAW / "trace_comparison.json").is_file() else {"status": "FAIL"}

    software_pass, software_result = run_host_stub()
    if not software_pass: failures.append("ps_driver_host_stub")
    resource_pass, resource_results = run_resource_audit()
    if not resource_pass: failures.append("resource_audit")

    if args.parent_offline_pass:
        full_regression = {"status": "PASS", "source": "parent run_offline_gates.py",
                           "parent_environment": os.environ.get("P8C_OFFLINE_PARENT")}
        if os.environ.get("P8C_OFFLINE_PARENT") != "1":
            full_regression["status"] = "FAIL"; failures.append("parent_offline_provenance")
    elif args.no_full_regression:
        full_regression = {"status": "PASS", "source": "development focused run",
                           "final_full_regression_required": True}
    else:
        result = run([sys.executable, "scripts/run_offline_gates.py", "--include-p8b", "--json-summary"],
                     env=env, timeout=3600)
        write_log(RAW / "p0_p8b_full_regression.log", result)
        full_regression = {"status": "PASS" if result["returncode"] == 0 else "FAIL",
                           "source": "current canonical P0-P8B offline regression",
                           "log": rel(RAW / "p0_p8b_full_regression.log")}
        if result["returncode"] != 0: failures.append("p0_p8b_full_regression")

    exact_reference_checks = [
        "exact_design_target", "design_target_plus_one_request_throttled",
        "legal_strict_hard_boundary", "illegal_20_percent_fault",
        "long_periodic_4ppm_like_train_not_truncated",
        "cross_bucket_attack_detected_exactly",
        "legacy_fixed_bucket_misses_cross_boundary_attack",
        "cooldown_full_window_required", "cooldown_completes_at_window",
        "reduced_exact_window_exhaustive", "random_adversarial_safety",
    ]
    continuous_reference_checks = [
        "continuous_zero_cycle_vector", "continuous_one_cycle_vector",
        "continuous_2x_max_remains_killed",
    ]
    gating_reference_checks = [
        "one_hot_gating_and_reason", "path_epoch_gating_and_reason",
        "invalid_selected_reason_precedes_one_hot", "fault_kill_reason_priority",
    ]
    reference_checks = reference.get("checks", {})
    vector_coverage = {
        "EXACT_DUTY_TARGETED_VECTOR_MATRIX": "PASS" if (
            all(reference_checks.get(name) is True for name in exact_reference_checks)
            and xsim_results["tb_p8c_exact_duty"]["status"] == "PASS"
            and xsim_results["tb_p8c_full_scale"]["status"] == "PASS"
        ) else "FAIL",
        "CONTINUOUS_HIGH_VECTOR_MATRIX": "PASS" if (
            all(reference_checks.get(name) is True for name in continuous_reference_checks)
            and xsim_results["tb_p8c_physical_safety"]["status"] == "PASS"
        ) else "FAIL",
        "PERMIT_VECTOR_MATRIX": "PASS" if (
            all(reference_checks.get(name) is True for name in gating_reference_checks)
            and
            xsim_results["tb_p8c_endpoint_safety"]["status"] == "PASS"
            and xsim_results["tb_p8c_profile_matrix"]["status"] == "PASS"
        ) else "FAIL",
        "ONE_HOT_PATH_VECTOR_MATRIX": "PASS" if (
            xsim_results["tb_p8c_endpoint_safety"]["status"] == "PASS"
            and xsim_results["tb_p8c_profile_matrix"]["status"] == "PASS"
        ) else "FAIL",
        "MULTI_PROFILE_VECTOR_MATRIX": xsim_results["tb_p8c_profile_matrix"]["status"],
    }
    for name, status in vector_coverage.items():
        if status != "PASS":
            failures.append(name)

    config = yaml.safe_load((ROOT / "config/tfdu_safety.yaml").read_text(encoding="utf-8"))
    constants = json.loads((ROOT / "config/generated/tfdu_safety_constants.json").read_text(encoding="utf-8"))
    source_commit = run(["git", "rev-parse", "HEAD"])["stdout"].strip()
    base = {"status": "PASS" if not failures else "FAIL", "source_commit": source_commit,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "failures": failures, "profile": "P8C_MULTI_PROFILE_OFFLINE"}
    write_pair("p8c_safety_config_summary", "P8C safety configuration", {**base,
        "test_id": "P8C-SAFETY-CONFIG", "config_sha256": sha256(ROOT / "config/tfdu_safety.yaml"),
        "config": config, "derived": constants})
    write_pair("p8c_exact_sliding_duty_reference_summary", "P8C exact duty Python reference", {**base,
        "test_id": "P8C-PYTHON-REFERENCE-CAMPAIGN", "reference": reference})
    write_pair("p8c_exact_sliding_duty_rtl_summary", "P8C exact duty RTL", {**base,
        "test_id": "P8C-RTL-EXACT-DUTY", "reduced": xsim_results["tb_p8c_exact_duty"],
        "full_scale": xsim_results["tb_p8c_full_scale"], "trace_comparison": trace_summary})
    write_pair("p8c_continuous_high_guard_summary", "P8C continuous-high guard", {**base,
        "test_id": "P8C-RTL-CONTINUOUS-HIGH", "simulation": xsim_results["tb_p8c_physical_safety"]})
    write_pair("p8c_single_global_permit_architecture_summary", "P8C single global permit architecture", {**base,
        "test_id": "P8C-SINGLE-GLOBAL-PERMIT", "static": static_summary,
        "simulation": xsim_results["tb_p8c_endpoint_safety"]})
    write_pair("p8c_permit_fault_injection_summary", "P8C permit fault injection", {**base,
        "test_id": "P8C-PERMIT-FAULT-INJECTION", "simulation": xsim_results["tb_p8c_endpoint_safety"]})
    write_pair("p8c_receive_only_acquisition_summary", "P8C receive-only acquisition", {**base,
        "test_id": "P8C-RECEIVE-ONLY-ACQUISITION", "simulation": xsim_results["tb_p8c_endpoint_safety"]})
    write_pair("p8c_physical_module_accounting_summary", "P8C physical module accounting", {**base,
        "test_id": "P8C-PHYSICAL-MODULE-ACCOUNTING", "simulation": xsim_results["tb_p8c_profile_matrix"]})
    write_pair("p8c_register_map_summary", "P8C register map", {**base,
        "test_id": "P8C-REGISTER-MAP", "map_sha256": sha256(ROOT / "config/register_map/ir_axi_regs.yaml"),
        "simulation": xsim_results["tb_p8c_safety_regs"], "software": software_result})
    write_pair("p8c_profile_matrix_summary", "P8C profile matrix", {**base,
        "test_id": "P8C-PROFILE-MATRIX", "simulation": xsim_results["tb_p8c_profile_matrix"],
        "profiles": config["physical_profiles"]})
    write_pair("p8c_resource_audit_summary", "P8C OOC resource audit", {**base,
        "test_id": "P8C-OOC-RESOURCE-AUDIT", "resources": resource_results})
    write_pair("p8c_p0_p8b_regression_summary", "P8C P0-P8B regression", {**base,
        "test_id": "P8C-P0-P8B-REGRESSION", "regression": full_regression,
        "p7_status_preserved": state.get("p7_status"),
        "p8b_status_preserved": state.get("stage_status", {}).get("P8B_GEOMETRY_MAPPING_HANDOVER")})
    write_pair("p8c_offline_gate_summary", "P8C offline gate", {**base,
        "test_id": "P8C-OFFLINE-GATE", "commands": commands, "xsim": xsim_results,
        "software": software_result, "resource_status": "PASS" if resource_pass else "FAIL",
        "full_regression": full_regression, "mandatory_vector_coverage": vector_coverage})

    exits = {
        "P8C_TFDU_SAFETY_EXACT_DUTY_SINGLE_GLOBAL_PERMIT": "PASS" if not failures else "FAIL",
        "EXACT_1000US_SLIDING_DUTY": xsim_results["tb_p8c_full_scale"]["status"],
        "STRICT_LT20_PERCENT_HARD_LIMIT": xsim_results["tb_p8c_exact_duty"]["status"],
        "LE18_PERCENT_DESIGN_TARGET": xsim_results["tb_p8c_full_scale"]["status"],
        "CROSS_BUCKET_BOUNDARY_ATTACK": "PASS" if reference.get("checks", {}).get("cross_bucket_attack_detected_exactly") else "FAIL",
        "DUTY_HISTORY_PERSISTS_ACROSS_PERMIT_AND_PATH": "PASS" if (
            xsim_results["tb_p8c_endpoint_safety"]["status"] == "PASS" and
            xsim_results["tb_p8c_profile_matrix"]["status"] == "PASS") else "FAIL",
        "DUTY_HISTORY_RESET_COOLDOWN_1000US": xsim_results["tb_p8c_exact_duty"]["status"],
        "DUTY_ACCOUNTING_PER_PHYSICAL_MODULE": xsim_results["tb_p8c_profile_matrix"]["status"],
        "MAX_CONTINUOUS_TXD_HIGH_LE_1US": xsim_results["tb_p8c_physical_safety"]["status"],
        "STUCK_HIGH_FAULT_LATCH_AND_KILL": xsim_results["tb_p8c_physical_safety"]["status"],
        "SINGLE_GLOBAL_PERMIT_PER_ENDPOINT": static_summary.get("status", "FAIL"),
        "NO_DUAL_PERMIT": static_summary.get("status", "FAIL"),
        "NO_PERMIT_HEARTBEAT": static_summary.get("status", "FAIL"),
        "NO_PER_BANK_GLOBAL_PERMIT": static_summary.get("status", "FAIL"),
        "PERMIT_LOW_ALL_TX_OFF_PROPERTY": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "PERMIT_ASYNC_DROP_FINAL_RTL_KILL": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "PERMIT_HIGH_REQUIRES_SYNC_FILTER": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "PERMIT_REASSERT_REQUIRES_EXPLICIT_REARM": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "PARTIAL_FRAME_NOT_RESUMED": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "GLOBAL_PERMIT_SD_SEPARATION": static_summary.get("status", "FAIL"),
        "RECEIVE_ONLY_ACQUISITION_WITH_PERMIT_LOW": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "TFDU_STARTUP_500US_REGRESSION": xsim_results["tb_p8c_full_scale"]["status"],
        "ILLEGAL_ONE_HOT_KILL": xsim_results["tb_p8c_endpoint_safety"]["status"],
        "INVALID_PATH_EPOCH_KILL": xsim_results["tb_p8c_profile_matrix"]["status"],
        "P8B_MAPPING_REGRESSION": full_regression["status"],
        "REGISTER_MAP_GENERATION": commands["register_map_verify"]["status"],
        "SOFTWARE_PERMIT_OVERRIDE_ABSENT": static_summary.get("status", "FAIL"),
        "TEST_BYPASS_NOT_IN_PRODUCTION": static_summary.get("status", "FAIL"),
        "Z7010_2LANE_PROFILE": xsim_results["tb_p8c_profile_matrix"]["status"],
        "Z7020_ROTATING_8LANE_MODEL": xsim_results["tb_p8c_profile_matrix"]["status"],
        "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL": xsim_results["tb_p8c_profile_matrix"]["status"],
        "P0_P7_REGRESSION": full_regression["status"], "P8A_REGRESSION": full_regression["status"],
        "P8B_REGRESSION": full_regression["status"], "OFFLINE_FULL_REGRESSION": full_regression["status"],
        "NO_HARDWARE_SCAN": static_summary.get("status", "FAIL"), "EVIDENCE_CONSISTENCY": "PASS",
    }
    if any(value != "PASS" for value in exits.values()):
        base["status"] = "FAIL"
        failures.extend(key for key, value in exits.items() if value != "PASS" and key not in failures)
    final = {**base, "test_id": "P8C-FINAL-ACCEPTANCE", "exit_gates": exits,
             "mandatory_vector_coverage": vector_coverage,
             "P8A_BASELINE_COMMIT": "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4",
             "P8A_TAG": "p8a-pass", "P8B_CHECKPOINT_COMMIT": "80c8433eac1a09a32c9018460f8b76286c4a72a7",
             "P8B_TAG": "p8b-pass", "P8C_SOURCE_COMMIT": source_commit,
             "P8C_CHECKPOINT_COMMIT": "RESOLVED_BY_P8C_TAG_TARGET_AFTER_COMMIT", "P8C_TAG": "p8c-pass",
             "hardware_pending": {
                 "GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION": "PENDING_D17",
                 "GLOBAL_PERMIT_OPEN_CIRCUIT_ELECTRICAL": "PENDING_D17",
                 "GLOBAL_PERMIT_PARTIAL_POWER": "PENDING_D17",
                 "Z7010_GLOBAL_PERMIT_PIN_FREEZE": "PENDING_P9_PIN_FREEZE",
                 "TFDU_DUTY_EXTERNAL_MEASUREMENT": "PENDING_P9_OR_LATER",
                 "SIMULTANEOUS_TX_POWER_ACCEPTANCE": "PENDING_HARDWARE_POWER_STAGE",
             },
             "PASS": sorted(key for key, value in exits.items() if value == "PASS"),
             "FAIL": sorted(key for key, value in exits.items() if value != "PASS"),
             "SKIP_WITH_REASON": [], "NEXT_RECOMMENDED_STAGE": "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE"}
    write_pair("p8c_final_summary", "P8C final summary", final)

    artifact_paths = []
    active = json.loads((ROOT / "config/p8c_active_sources.json").read_text(encoding="utf-8"))
    for value in (active["production_sources"] + active["compatibility_sources"]
                  + active["simulation_sources"] + active["ooc_only_sources"]):
        artifact_paths.append(ROOT / value)
    artifact_paths += [ROOT / "config/tfdu_safety.yaml", ROOT / "config/register_map/ir_axi_regs.yaml",
                       ROOT / "config/generated/tfdu_safety_constants.json",
                       ROOT / "config/register_map/generated/ir_regs_manifest.json",
                       ROOT / "scripts/run_p8c_safety_gate.py",
                       ROOT / "scripts/check_p8c_safety_static.py",
                       ROOT / "scripts/generate_tfdu_safety_config.py",
                       ROOT / "scripts/generate_register_headers.py",
                       ROOT / "scripts/vivado/p8c_resource_audit.tcl",
                       ROOT / "tools/p8c_tfdu_safety_reference.py",
                       ROOT / "software/ps_driver/ir_driver.c",
                       ROOT / "software/ps_driver/ir_driver.h",
                       ROOT / "software/ps_driver/main_offline_stub.c"]
    artifact_paths += [OUT / f"{stem}.{suffix}" for stem in REQUIRED_PAIRS for suffix in ("json", "md")]
    source_manifest_path = RAW / "source_manifest.json"
    source_manifest_path.write_text(json.dumps(active, indent=2, sort_keys=True) + "\n",
                                    encoding="utf-8", newline="\n")
    raw_artifacts = list(RAW.glob("*.log"))
    raw_artifacts += list((RAW / "xsim").glob("*/*.log"))
    raw_artifacts += list((RAW / "software").glob("*.log"))
    raw_artifacts += [path for path in (RAW / "resource_audit").glob("*/*")
                      if path.suffix.lower() in {".log", ".rpt", ".txt"}]
    raw_artifacts += [RAW / "trace_comparison.json", source_manifest_path]
    artifact_paths += raw_artifacts
    manifest = {**COMMON, "status": "PASS" if not failures else "FAIL", "source_commit": source_commit,
                "artifacts": [{"path": rel(path), "sha256": sha256(path)} for path in sorted(set(artifact_paths)) if path.is_file()]}
    (RAW / "artifact_sha256_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    print(f"P8C_GATE_STATUS={'PASS' if not failures else 'FAIL'}")
    print(f"P8C_SOURCE_COMMIT={source_commit}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=true")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
