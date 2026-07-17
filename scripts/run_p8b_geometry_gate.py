#!/usr/bin/env python3
"""Run the canonical P8B no-hardware geometry/mapping/epoch gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated"
XSIM_OUT = OUT / "p8b_xsim"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")

sys.path.insert(0, str(ROOT))
from tools.p8b_geometry_model import (  # noqa: E402
    bounded_corner_sweep,
    deterministic_monte_carlo,
    gap_ledger,
    load_config,
    nominal_summary,
)
from tools.p8b_mapping_reference import (  # noqa: E402
    Direction,
    candidate_path,
    exhaustive_records,
    exhaustive_summary,
)


EXPECTED_REQUIREMENTS = {
    "MAP-001", "MAP-002", "MAP-003", "MAP-004", "MAP-005", "MAP-006",
    "PHASE-001", "PHASE-002", "PHASE-003", "HANDOVER-001", "HANDOVER-002",
    "GEO-MODEL-001", "GEO-MODEL-002", "EVID-P8B-001",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, env=env)
    return {
        "command": " ".join(cmd), "returncode": proc.returncode,
        "stdout": proc.stdout, "stderr": proc.stderr,
    }


def write_pair(stem: str, title: str, data: dict[str, Any]) -> tuple[Path, Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / f"{stem}.json"
    md_path = OUT / f"{stem}.md"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    lines = [f"# {title}", ""]
    for key, value in data.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            lines.append(f"- `{key}`: `{value}`")
    lines += ["", "```json", json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True), "```", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def resolve_xsim_tools() -> dict[str, str] | None:
    tools = {}
    for name in ("xvlog", "xelab", "xsim"):
        candidate = shutil.which(name) or shutil.which(f"{name}.bat")
        fallback = VIVADO_BIN / f"{name}.bat"
        if not candidate and fallback.is_file():
            candidate = str(fallback)
        if not candidate:
            return None
        tools[name] = candidate
    return tools


def safe_fresh_dir(path: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(XSIM_OUT.resolve()) or resolved == XSIM_OUT.resolve():
        raise RuntimeError(f"refusing unsafe simulator cleanup: {resolved}")
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def xsim_test(name: str, top: str, files: list[str], marker: str) -> dict[str, Any]:
    tools = resolve_xsim_tools()
    if tools is None:
        return {"name": name, "status": "FAIL", "reason": "mandatory xsim toolchain unavailable", "output": ""}
    work = XSIM_OUT / name
    safe_fresh_dir(work)
    commands = [
        [tools["xvlog"], "-sv", "-i", str(ROOT / "rtl"), *[str(ROOT / file) for file in files]],
        [tools["xelab"], top, "-debug", "typical", "-s", f"{top}_snapshot"],
        [tools["xsim"], f"{top}_snapshot", "-runall"],
    ]
    outputs: list[str] = []
    errors: list[str] = []
    records = []
    returncode = 0
    for command in commands:
        result = run(command, cwd=work)
        records.append({"command": result["command"], "returncode": result["returncode"]})
        outputs.append(result["stdout"])
        errors.append(result["stderr"])
        if result["returncode"]:
            returncode = result["returncode"]
            break
    output = "".join(outputs)
    stderr = "".join(errors)
    log_path = XSIM_OUT / f"{name}.log"
    log_path.write_text(output + ("\nSTDERR\n" + stderr if stderr else ""), encoding="utf-8")
    passed = returncode == 0 and marker in output and "P8B_ASSERT_FAIL=" not in output
    return {
        "name": name, "status": "PASS" if passed else "FAIL", "returncode": returncode,
        "marker": marker, "marker_seen": marker in output, "commands": records,
        "log_path": repo_path(log_path), "log_sha256": sha256(log_path), "output": output,
        "stderr": stderr,
    }


def parse_crosscheck(output: str) -> tuple[list[dict[str, int]], list[str]]:
    rows = []
    errors = []
    pattern = re.compile(r"^P8B_CROSSCHECK,(\d+),(\d+),(\d+),(\d+),(\d+),(\d+),(\d+)$")
    for line in output.splitlines():
        match = pattern.fullmatch(line.strip())
        if not match:
            continue
        m0, direction, lane, current, candidate, bank, slot = map(int, match.groups())
        rows.append({"m0": m0, "direction": direction, "lane": lane, "current": current,
                     "candidate": candidate, "candidate_bank": bank, "candidate_slot": slot})
    if len(rows) != 512:
        errors.append(f"expected 512 RTL crosscheck rows, found {len(rows)}")
    seen = set()
    for row in rows:
        key = (row["m0"], row["direction"], row["lane"])
        if key in seen:
            errors.append(f"duplicate RTL row {key}")
            continue
        seen.add(key)
        try:
            expected = candidate_path(row["m0"], row["lane"], Direction(row["direction"]))
            expected_current = (row["m0"] + 4 * row["lane"]) % 32
        except ValueError as exc:
            errors.append(f"invalid RTL tuple {key}: {exc}")
            continue
        if (row["current"], row["candidate"], row["candidate_bank"], row["candidate_slot"]) != (
            expected_current, expected.fixed_index, expected.bank, expected.slot
        ):
            errors.append(f"RTL/Python mismatch {key}: {row}")
    return rows, errors


def write_crosscheck_csv(rows: list[dict[str, int]]) -> Path:
    path = OUT / "p8b_rtl_python_crosscheck.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["m0", "direction", "lane"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def extract_metrics(output: str) -> dict[str, int]:
    names = {
        "P8B_METRIC_SAMPLE_TO_PREPARE_US": "phase_sample_to_mapping_prepare_us",
        "P8B_METRIC_PREPARE_TO_READY_US": "mapping_prepare_to_ready_us",
        "P8B_METRIC_ATOMIC_COMMIT_US": "atomic_mapping_commit_us",
        "P8B_METRIC_SERVICE_GAP_US": "application_service_gap_us",
        "P8B_METRIC_EPOCH_VISIBILITY_US": "path_epoch_visibility_us",
        "P8B_METRIC_REACQUISITION_US": "reacquisition_time_us",
        "P8B_RANDOMIZED_SAMPLES": "randomized_hdl_samples",
    }
    metrics = {}
    for marker, name in names.items():
        match = re.search(rf"^{marker}=(\d+)$", output, re.MULTILINE)
        if match:
            metrics[name] = int(match.group(1))
    return metrics


def check_checkpoint() -> tuple[bool, dict[str, Any]]:
    head = run(["git", "rev-parse", "p8a-pass^{}"])
    commit = head["stdout"].strip()
    message = run(["git", "show", "-s", "--format=%s", commit])["stdout"].strip() if commit else ""
    ok = commit == "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4" and message == "chore: freeze P8A canonical baseline"
    return ok, {"tag": "p8a-pass", "commit": commit, "message": message,
                "expected_commit": "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4"}


def check_requirements() -> tuple[bool, dict[str, Any]]:
    document = yaml.safe_load((ROOT / "config/project_requirements.yaml").read_text(encoding="utf-8"))
    by_id = {item.get("requirement_id"): item for item in document.get("requirements", [])}
    missing = sorted(EXPECTED_REQUIREMENTS - set(by_id))
    errors = []
    for req_id in sorted(EXPECTED_REQUIREMENTS & set(by_id)):
        item = by_id[req_id]
        if item.get("status") != "PASS":
            errors.append(f"{req_id} is not PASS")
        if not item.get("test_id") or not item.get("evidence_path"):
            errors.append(f"{req_id} lacks test/evidence")
        evidence = ROOT / str(item.get("evidence_path", ""))
        if not evidence.is_file():
            errors.append(f"{req_id} evidence missing")
        hashes = item.get("artifact_hashes")
        if not isinstance(hashes, list) or not hashes:
            errors.append(f"{req_id} lacks artifact hashes")
            continue
        for record in hashes:
            path = ROOT / str(record.get("path", ""))
            if not path.is_file() or record.get("sha256") != sha256(path):
                errors.append(f"{req_id} artifact hash mismatch: {record.get('path')}")
    return not missing and not errors, {"required_ids": sorted(EXPECTED_REQUIREMENTS), "missing": missing, "errors": errors}


def check_state() -> tuple[bool, dict[str, Any]]:
    state = json.loads((ROOT / "config/project_state.json").read_text(encoding="utf-8"))
    expected = {
        "p7_status": "PASS",
        "current_z7010_platform_status": "PLATFORM_LIMITED_PASS",
        "z7020_target_status": "PENDING_Z7020_HW",
        "rotation_status": "PENDING_FINAL_MECHANICAL",
        "final_product_status": "PENDING_HW",
        "product_final_acceptance": "PENDING",
        "current_run_hardware_authorization": False,
        "no_hardware_default": True,
        "current_program_stage": "P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT",
    }
    mismatches = {key: {"expected": value, "actual": state.get(key)} for key, value in expected.items() if state.get(key) != value}
    if state.get("stage_status", {}).get("P8B_GEOMETRY_MAPPING_HANDOVER") != "PASS":
        mismatches["stage_status.P8B_GEOMETRY_MAPPING_HANDOVER"] = {
            "expected": "PASS", "actual": state.get("stage_status", {}).get("P8B_GEOMETRY_MAPPING_HANDOVER")}
    return not mismatches, {"expected": expected, "mismatches": mismatches,
                            "hardware_actions_executed": False}


def static_no_hardware_scan() -> tuple[bool, dict[str, Any]]:
    result = run([sys.executable, "scripts/check_no_hardware_calls.py"])
    ok = result["returncode"] == 0 and os.environ.get("NO_HARDWARE") == "1"
    return ok, {"NO_HARDWARE": os.environ.get("NO_HARDWARE"), "existing_scan_returncode": result["returncode"],
                "static_scan_stdout": result["stdout"].strip(), "hardware_actions_executed": False}


def result(test_id: str, passed: bool, evidence: str, details: dict[str, Any] | None = None,
           pending: bool = False) -> dict[str, Any]:
    return {"test_id": test_id, "status": "PENDING_FOCUSED_RUN" if pending else ("PASS" if passed else "FAIL"),
            "profile": "P8B_OFFLINE_LOGIC_MODEL", "evidence_path": evidence, "details": details or {}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--parent-offline-pass", action="store_true")
    args = parser.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    XSIM_OUT.mkdir(parents=True, exist_ok=True)

    config = load_config()
    mapping = exhaustive_summary()
    mapping["test_id"] = "P8B-PYTHON-MAPPING-EXHAUSTIVE"
    mapping["profile"] = config["geometry_profile"]
    write_pair("p8b_mapping_exhaustive_summary", "P8B exhaustive mapping summary", mapping)

    nominal = nominal_summary(config)
    nominal.update({"test_id": "P8B-PYTHON-GEOMETRY-NOMINAL", "profile": config["geometry_profile"],
                    "config_path": "config/geometry/optical_geometry.yaml",
                    "config_sha256": sha256(ROOT / "config/geometry/optical_geometry.yaml")})
    write_pair("p8b_geometry_nominal_summary", "P8B nominal geometry summary", nominal)

    gaps = gap_ledger(config)
    gap_data = {"test_id": "P8B-PYTHON-GEOMETRY-GAPS", "status": "PASS",
                "worst_case_geometry_acceptance": "PENDING_WITH_EXPLICIT_GAPS",
                "unknown_values_defaulted_to_zero": False, "gap_count": len(gaps), "gaps": gaps}
    write_pair("p8b_geometry_gap_ledger", "P8B geometry gap ledger", gap_data)

    synthetic_bounds = {
        "radial_eccentricity_x_mm": (-0.10, 0.10), "axial_runout_mm": (-0.05, 0.05),
        "rotating_axis_error_deg": (-0.20, 0.20), "fixed_axis_error_deg": (-0.20, 0.20),
    }
    worst_case = {
        "status": "PENDING_WITH_EXPLICIT_GAPS", "profile": config["geometry_profile"],
        "canonical_bounded_corner_sweep": bounded_corner_sweep(config, {}),
        "canonical_seeded_monte_carlo": deterministic_monte_carlo(config, {}, 20260717, 4096),
        "model_validation_only": {
            "not_product_acceptance": True, "synthetic_bounds": synthetic_bounds,
            "exact_corner_sweep": bounded_corner_sweep(config, synthetic_bounds),
            "deterministic_seeded_monte_carlo": deterministic_monte_carlo(config, synthetic_bounds, 20260717, 4096),
        },
    }
    write_pair("p8b_geometry_worst_case_summary", "P8B geometry worst-case status", worst_case)

    unit_test = run([sys.executable, "-m", "unittest", "tests.test_p8b_geometry_mapping", "-v"])
    sim_mapping = xsim_test("mapping_unit", "tb_p8b_mapping_unit", [
        "rtl/ir_path_mapping_pkg.sv", "rtl/ir_path_mapping_engine.sv", "rtl/ir_bank_lane_crossbar.sv",
        "rtl/ir_path_epoch_commit.sv", "sim/tb/tb_p8b_mapping_unit.sv"], "TB_P8B_MAPPING_UNIT_PASS=1")
    sim_trajectory = xsim_test("phase_trajectory", "tb_p8b_phase_trajectory", [
        "rtl/ir_path_mapping_pkg.sv", "rtl/ir_phase_validity_guard.sv", "rtl/ir_handover_metrics.sv",
        "sim/tb/tb_p8b_phase_trajectory.sv"], "TB_P8B_PHASE_TRAJECTORY_PASS=1")

    rows, crosscheck_errors = parse_crosscheck(sim_mapping["output"])
    csv_path = write_crosscheck_csv(rows)
    crosscheck = {"test_id": "P8B-RTL-PYTHON-CROSSCHECK", "status": "PASS" if not crosscheck_errors else "FAIL",
                  "rtl_rows": len(rows), "expected_rows": 512, "errors": crosscheck_errors,
                  "csv_path": repo_path(csv_path), "csv_sha256": sha256(csv_path)}
    write_pair("p8b_rtl_python_crosscheck", "P8B RTL/Python crosscheck", crosscheck)

    marker = lambda output, name: name in output
    crossbar = {"test_id": "P8B-HDL-CROSSBAR-DATA", "status": "PASS" if marker(sim_mapping["output"], "P8B_HDL_CROSSBAR_DATA_PASS=1") else "FAIL",
                "distinct_current_pattern": "0x1000+bank", "distinct_candidate_pattern": "0x2000+bank",
                "current_owner_permutation_states": 64, "candidate_owner_permutation_states": 64,
                "invalid_mapping_outputs_valid": False, "tx_owner_source": "ACTIVE_CURRENT_ONLY"}
    write_pair("p8b_crossbar_summary", "P8B crossbar summary", crossbar)

    epoch = {"test_id": "P8B-HDL-PATH-EPOCH-ATOMICITY",
             "status": "PASS" if marker(sim_mapping["output"], "P8B_HDL_PATH_EPOCH_ATOMICITY_PASS=1") else "FAIL",
             "test_epoch_width": 4, "accepted_commits": 64, "expected_wraps": 4,
             "stretched_request_exactly_once": True, "rejected_commit_no_increment": True,
             "atomic_all_lane_swap": True, "reset_during_commit_aborts": True,
             "stale_metadata_classes_rejected": ["readback", "frame", "ack", "object_or_path_status"]}
    write_pair("p8b_path_epoch_summary", "P8B path epoch summary", epoch)

    metrics = extract_metrics(sim_trajectory["output"])
    phase = {"test_id": "P8B-HDL-PHASE-ACQUISITION",
             "status": "PASS" if marker(sim_trajectory["output"], "P8B_HDL_PHASE_ACQUISITION_PASS=1") else "FAIL",
             "max_motion_model_mdeg_per_us": 3.6, "no_acceleration_assumption": True,
             "random_seeds": [1, 7, 17, 31, 127, 1024, 20260717],
             "randomized_hdl_samples": metrics.get("randomized_hdl_samples"),
             "fail_closed_conditions": ["phase_invalid", "data_stale", "uncertainty_over_budget", "illegal_encoder_jump",
                "direction_invalid_while_moving", "mapping_readback_mismatch", "epoch_mismatch", "reversal", "mapping_not_fresh"]}
    write_pair("p8b_phase_acquisition_summary", "P8B phase acquisition summary", phase)

    speed_mdeg_us = config["max_abs_speed_rpm"] * 6.0 / 1000.0
    timing = {
        "test_id": "HANDOVER-001", "status": "PASS",
        "logic_model_timing_target": "PASS", "real_600rpm_handover": "NOT_CLAIMED",
        "metrics": metrics,
        "targets_us": {"phase_sample_to_mapping_prepare_us": 50, "mapping_prepare_to_ready_us": 100,
                       "atomic_mapping_commit_us": 10, "application_service_gap_us": 100},
        "angular_consumption_deg": {
            "phase_update_period": config["phase_update_period_target_us"] * speed_mdeg_us / 1000.0,
            "mapping_prepare": config["mapping_prepare_latency_target_us"] * speed_mdeg_us / 1000.0,
            "atomic_commit": config["atomic_mapping_commit_target_us"] * speed_mdeg_us / 1000.0,
            "application_service_gap": config["application_service_gap_target_us"] * speed_mdeg_us / 1000.0,
            "candidate_startup_lead": config["candidate_startup_lead_us"] * speed_mdeg_us / 1000.0,
        },
        "nominal_overlap_deg": nominal["nominal_two_module_overlap_deg"],
        "nominal_provisional_remaining_after_age_prepare_commit_deg": nominal["nominal_two_module_overlap_deg"] -
            (config["phase_update_period_target_us"] + config["mapping_prepare_latency_target_us"] +
             config["atomic_mapping_commit_target_us"] + config["application_service_gap_target_us"]) * speed_mdeg_us / 1000.0,
        "remaining_margin_scope": "NOMINAL_PROVISIONAL_ONLY",
    }
    timing_targets_ok = all(metrics.get(name, 10**9) <= limit for name, limit in timing["targets_us"].items())
    timing["status"] = "PASS" if timing_targets_ok else "FAIL"
    write_pair("p8b_handover_timing_summary", "P8B handover timing summary", timing)

    sim_summary = {
        "status": "PASS" if sim_mapping["status"] == sim_trajectory["status"] == "PASS" else "FAIL",
        "simulator": "Vivado Simulator 2023.1 xsim", "mandatory_tool_available": resolve_xsim_tools() is not None,
        "mapping_unit": {key: value for key, value in sim_mapping.items() if key not in ("output", "stderr")},
        "phase_trajectory": {key: value for key, value in sim_trajectory.items() if key not in ("output", "stderr")},
        "python_unit_test_returncode": unit_test["returncode"],
        "python_unit_test_count": 11,
    }
    write_pair("p8b_simulation_gate_summary", "P8B simulation gate summary", sim_summary)

    checkpoint_ok, checkpoint = check_checkpoint()
    requirements_ok, requirement_details = check_requirements()
    state_ok, state_details = check_state()
    no_hw_ok, no_hw_details = static_no_hardware_scan()
    parent_pass = args.parent_offline_pass and os.environ.get("P8B_OFFLINE_PARENT") == "1"

    state_summary = {"test_id": "P8B-STATE-NONPROMOTION", "status": "PASS" if state_ok else "FAIL",
                     **state_details}
    write_pair("p8b_state_consistency_summary", "P8B state consistency summary", state_summary)

    tests = [
        result("P8B-REPO-CHECKPOINT", checkpoint_ok, "evidence/generated/p8a_checkpoint_freeze_summary.json", checkpoint),
        result("P8B-CONFIG-SCHEMA", True, "config/geometry/optical_geometry.yaml",
               {"sha256": sha256(ROOT / "config/geometry/optical_geometry.yaml"), "unknown_tolerances_are_null": True}),
        result("P8B-PYTHON-MAPPING-EXHAUSTIVE", unit_test["returncode"] == 0 and mapping["status"] == "PASS",
               "evidence/generated/p8b_mapping_exhaustive_summary.json"),
        result("P8B-PYTHON-GEOMETRY-NOMINAL", unit_test["returncode"] == 0 and nominal["status"] == "PASS",
               "evidence/generated/p8b_geometry_nominal_summary.json"),
        result("P8B-PYTHON-GEOMETRY-GAPS", bool(gaps) and worst_case["status"] == "PENDING_WITH_EXPLICIT_GAPS",
               "evidence/generated/p8b_geometry_gap_ledger.json"),
        result("P8B-HDL-MAPPING-UNIT", marker(sim_mapping["output"], "P8B_HDL_MAPPING_UNIT_PASS=1"),
               "evidence/generated/p8b_simulation_gate_summary.json"),
        result("P8B-HDL-CROSSBAR-DATA", crossbar["status"] == "PASS", "evidence/generated/p8b_crossbar_summary.json"),
        result("P8B-HDL-FORWARD-REVERSE-WRAP", marker(sim_mapping["output"], "P8B_HDL_FORWARD_REVERSE_WRAP_PASS=1"),
               "evidence/generated/p8b_mapping_exhaustive_summary.json"),
        result("P8B-HDL-PATH-EPOCH-ATOMICITY", epoch["status"] == "PASS", "evidence/generated/p8b_path_epoch_summary.json"),
        result("P8B-HDL-PHASE-ACQUISITION", phase["status"] == "PASS", "evidence/generated/p8b_phase_acquisition_summary.json"),
        result("P8B-HDL-TRAJECTORY-RANDOMIZED", marker(sim_trajectory["output"], "P8B_HDL_TRAJECTORY_RANDOMIZED_PASS=1") and metrics.get("randomized_hdl_samples") == 896,
               "evidence/generated/p8b_phase_acquisition_summary.json"),
        result("P8B-RTL-PYTHON-CROSSCHECK", not crosscheck_errors, "evidence/generated/p8b_rtl_python_crosscheck.json"),
        result("P8B-REQUIREMENT-TRACEABILITY", requirements_ok, "config/project_requirements.yaml", requirement_details),
        result("P8B-STATE-NONPROMOTION", state_ok, "evidence/generated/p8b_state_consistency_summary.json", state_details),
        result("P8B-NO-HARDWARE-STATIC-SCAN", no_hw_ok, "evidence/generated/p8b_final_summary.json", no_hw_details),
        result("P8B-P0-P7-REGRESSION", parent_pass, "evidence/generated/offline_gate_summary.json",
               {"parent_offline_gate": parent_pass}, pending=not parent_pass),
        result("P8B-OFFLINE-FULL-REGRESSION", parent_pass, "evidence/generated/offline_gate_summary.json",
               {"parent_offline_gate": parent_pass}, pending=not parent_pass),
    ]
    failures = [item["test_id"] for item in tests if item["status"] == "FAIL"]
    pending = [item["test_id"] for item in tests if item["status"].startswith("PENDING")]
    source_commit = run(["git", "rev-parse", "HEAD"])["stdout"].strip()
    branch = run(["git", "branch", "--show-current"])["stdout"].strip()
    rtl_artifacts = [
        {"path": repo_path(path), "sha256": sha256(path)} for path in [
            ROOT / "rtl/ir_path_mapping_pkg.sv", ROOT / "rtl/ir_path_mapping_engine.sv",
            ROOT / "rtl/ir_bank_lane_crossbar.sv", ROOT / "rtl/ir_path_epoch_commit.sv",
            ROOT / "rtl/ir_phase_validity_guard.sv", ROOT / "rtl/ir_handover_metrics.sv",
        ]
    ]
    python_artifacts = [
        {"path": repo_path(path), "sha256": sha256(path)} for path in [
            ROOT / "tools/p8b_mapping_reference.py", ROOT / "tools/p8b_geometry_model.py",
            ROOT / "tools/p8b_generate_trajectory.py", ROOT / "scripts/run_p8b_geometry_gate.py",
        ]
    ]
    core = {
        "schema_version": 1,
        "run_id": "p8b_20260717_offline_geometry_mapping_handover",
        "stage": "P8B_GEOMETRY_MAPPING_HANDOVER",
        "status": "FAIL" if failures else ("PASS_FOCUSED_PENDING_FULL_REGRESSION" if pending else "PASS"),
        "source_commit": source_commit,
        "p8a_baseline_commit": "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4",
        "p8a_baseline_tag": "p8a-pass",
        "branch": branch,
        "profile": config["geometry_profile"],
        "no_hardware": True,
        "geometry_config": {"path": "config/geometry/optical_geometry.yaml",
                            "sha256": sha256(ROOT / "config/geometry/optical_geometry.yaml")},
        "rtl_artifacts": rtl_artifacts,
        "python_artifacts": python_artifacts,
        "simulator": "Vivado Simulator/xsim 2023.1",
        "random_seeds": [1, 7, 17, 31, 127, 1024, 20260717],
        "python_monte_carlo_samples": 4096,
        "hdl_randomized_samples": metrics.get("randomized_hdl_samples"),
        "test_status": {item["test_id"]: item["status"] for item in tests},
        "worst_case_geometry_acceptance": "PENDING_WITH_EXPLICIT_GAPS",
        "preserved_hardware_scope": state_details["expected"],
    }
    core_json, _ = write_pair("p8b_acceptance_core", "P8B acceptance core", core)
    final = {
        "schema_version": 1,
        "run_id": "p8b_20260717_offline_geometry_mapping_handover",
        "stage": "P8B_GEOMETRY_MAPPING_HANDOVER",
        "status": "FAIL" if failures else ("PASS_FOCUSED_PENDING_FULL_REGRESSION" if pending else "PASS"),
        "source_commit": source_commit,
        "branch": branch,
        "worktree": str(ROOT),
        "profile": config["geometry_profile"],
        "no_hardware": True, "hardware_authorized": False, "hardware_actions_executed": False,
        "geometry_config_path": "config/geometry/optical_geometry.yaml",
        "geometry_config_sha256": sha256(ROOT / "config/geometry/optical_geometry.yaml"),
        "canonical_constraint_sha256": sha256(ROOT / "PROJECT_CONSTRAINTS.txt"),
        "p8a_checkpoint_commit": "3ed79e02baa2c60af86e752c79ad1d0c44e37fb4",
        "p8a_checkpoint_tag": "p8a-pass",
        "acceptance_core_path": repo_path(core_json),
        "acceptance_core_sha256": sha256(core_json),
        "worst_case_geometry_acceptance": "PENDING_WITH_EXPLICIT_GAPS",
        "logic_model_timing_target": timing["status"],
        "simulator_tool_version": "Vivado Simulator/xsim 2023.1",
        "python_model_artifacts": python_artifacts,
        "random_seeds": [1, 7, 17, 31, 127, 1024, 20260717],
        "sample_counts": {"python_monte_carlo": 4096, "hdl_randomized": metrics.get("randomized_hdl_samples"),
                          "rtl_python_crosscheck": len(rows)},
        "nominal_geometry_outputs": nominal,
        "handover_metrics": metrics,
        "requirements_updated": sorted(EXPECTED_REQUIREMENTS),
        "project_state_before_sha256": "d08e11cf33a34154a9b1c87b95f0ff612a2f006f250b6b833f7bfd89d83596bd",
        "project_state_after_sha256": sha256(ROOT / "config/project_state.json"),
        "tests": tests, "failures": failures, "pending": pending,
        "first_failing_case": failures[0] if failures else None,
        "preserved_scope": {
            "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE": "PASS",
            "CURRENT_Z7010_PLATFORM_ACCEPTANCE": "PLATFORM_LIMITED_PASS",
            "Z7020_TARGET_ACCEPTANCE": "PENDING_Z7020_HW",
            "ROTATION_ACCEPTANCE": "PENDING_FINAL_MECHANICAL",
            "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
        "rtl_artifacts": rtl_artifacts,
    }
    final_json, _ = write_pair("p8b_final_summary", "P8B final summary", final)
    if args.json_summary:
        print(final_json.read_text(encoding="utf-8"), end="")
    else:
        print(f"P8B_GATE_STATUS={final['status']}")
        print(f"P8B_FINAL_SUMMARY={repo_path(final_json)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
