#!/usr/bin/env python3
"""Fail-closed static architecture checks for the canonical P8C sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "config/p8c_active_sources.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def module_header(text: str, module: str) -> str:
    match = re.search(rf"\bmodule\s+{re.escape(module)}\b(?P<header>.*?)\)\s*;", text, re.S)
    return match.group("header") if match else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checks: dict[str, dict[str, Any]] = {}

    def record(name: str, passed: bool, detail: Any = None) -> None:
        checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}

    active_paths = [ROOT / value for value in manifest["production_sources"]]
    compatibility_paths = [ROOT / value for value in manifest["compatibility_sources"]]
    record("active_source_manifest_complete", all(path.is_file() for path in active_paths + compatibility_paths))
    production_text = "\n".join(path.read_text(encoding="utf-8") for path in active_paths if path.is_file())
    endpoint_text = (ROOT / "rtl/ir_tfdu_safety_endpoint.sv").read_text(encoding="utf-8")
    integration_text = (ROOT / "rtl/ir_p8c_safety_integration.sv").read_text(encoding="utf-8")
    header = module_header(endpoint_text, "ir_tfdu_safety_endpoint")
    integration_header = module_header(integration_text, "ir_p8c_safety_integration")
    record("single_global_permit_endpoint_port", len(re.findall(r"\bglobal_permit_i\b", header)) == 1)
    record("single_global_permit_integration_port", len(re.findall(r"\bglobal_permit_i\b", integration_header)) == 1)

    identifiers = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", production_text.lower()))
    forbidden = {
        "permit_a", "permit_b", "permit_heartbeat", "global_permit_heartbeat",
        "bank_global_permit", "global_permit_bank", "per_bank_global_permit",
    }
    present_forbidden = sorted(forbidden & identifiers)
    record("no_dual_heartbeat_or_bank_permit_identifier", not present_forbidden, present_forbidden)

    register_map = yaml.safe_load((ROOT / "config/register_map/ir_axi_regs.yaml").read_text(encoding="utf-8"))
    registers = {item["name"]: item for item in register_map["registers"]}
    permit_status = registers.get("P8C_PERMIT_STATUS", {})
    permit_fields = {field["name"]: field.get("access") for field in permit_status.get("fields", [])}
    required_ro = {"GLOBAL_PERMIT_RAW", "GLOBAL_PERMIT_SYNC", "GLOBAL_PERMIT_EFFECTIVE"}
    record("permit_status_fields_read_only", permit_status.get("access") == "RO" and
           all(permit_fields.get(name) == "RO" for name in required_ro), permit_fields)
    required_registers = {
        "P8C_CONTROL", "P8C_PERMIT_STATUS", "P8C_PERMIT_RISE_COUNT",
        "P8C_PERMIT_FALL_COUNT", "P8C_PERMIT_DROP_DURING_FRAME_COUNT",
        "P8C_PERMIT_REARM_COUNT", "P8C_LAST_REASONS", "P8C_BANK_FAULT_MASK",
        "P8C_LANE_TX_PERMIT_MASK", "P8C_EFFECTIVE_TX_ENABLE_MASK",
        "P8C_PHYSICAL_MODULE_SELECTED_MASK", "P8C_ARM_STATUS",
        "P8C_SNAPSHOT_INDEX", "P8C_SNAPSHOT_ROLLING_HIGH",
        "P8C_SNAPSHOT_ROLLING_MAX", "P8C_SNAPSHOT_DUTY_HEADROOM",
        "P8C_SNAPSHOT_TARGET_THROTTLE_COUNT", "P8C_SNAPSHOT_LONGEST_HIGH",
        "P8C_SNAPSHOT_FLAGS", "P8C_SNAPSHOT_COOLDOWN_REMAINING",
        "P8C_REGISTER_MAP_VERSION", "P8C_REGISTER_MAP_HASH_LOW",
    }
    control_fields = {field["name"] for field in registers.get("P8C_CONTROL", {}).get("fields", [])}
    required_controls = {
        "ENDPOINT_ARM_REQUEST", "ENDPOINT_DISARM_REQUEST", "FULL_SHUTDOWN_REQUEST",
        "SAFETY_FAULT_CLEAR_REQUEST", "SNAPSHOT_REQUEST", "TELEMETRY_CLEAR_REQUEST",
    }
    snapshot_fields = {field["name"] for field in registers.get("P8C_SNAPSHOT_FLAGS", {}).get("fields", [])}
    required_snapshot_flags = {
        "DUTY_TARGET_THROTTLE", "DUTY_HARD_FAULT", "STUCK_HIGH_FAULT",
        "DUTY_HISTORY_VALID", "COOLDOWN_ACTIVE",
    }
    record("register_contract_complete",
           required_registers.issubset(registers) and required_controls.issubset(control_fields)
           and required_snapshot_flags.issubset(snapshot_fields),
           {"missing_registers": sorted(required_registers - set(registers)),
            "missing_controls": sorted(required_controls - control_fields),
            "missing_snapshot_flags": sorted(required_snapshot_flags - snapshot_fields)})
    record("software_permit_override_absent", "global_permit_override" not in
           ((ROOT / "software/ps_driver/ir_driver.c").read_text(encoding="utf-8").lower() +
            (ROOT / "software/ps_driver/ir_driver.h").read_text(encoding="utf-8").lower()))

    bypass_tokens = {"safety_bypass", "test_bypass", "permit_bypass", "disable_safety"}
    record("production_safety_bypass_absent", not (bypass_tokens & identifiers),
           sorted(bypass_tokens & identifiers))
    record("fixed_bucket_excluded", all("bucket" not in Path(value).name.lower()
           for value in manifest["production_sources"]) and "fixed_bucket" not in identifiers)
    record("physical_module_accounting_instantiated", "ir_tfdu_physical_module_safety" in endpoint_text and
           "PHYSICAL_MODULE_COUNT" in endpoint_text and "g_physical_safety" in endpoint_text)
    final_assign = re.search(r"assign\s+physical_txd_out_o\s*=\s*\n?\s*txd_pre_final\s*&\s*\{PHYSICAL_MODULE_COUNT\{global_permit_raw_safe\}\}\s*;", endpoint_text)
    record("raw_permit_is_final_txd_kill", final_assign is not None and
           "assign physical_txd_out_o" not in endpoint_text[final_assign.end():] if final_assign else False)
    sd_assign = re.search(r"assign\s+physical_sd_o\s*=\s*(.*?);", endpoint_text, re.S)
    record("sd_control_separate_from_permit", bool(sd_assign) and "permit" not in sd_assign.group(1).lower())
    rx_assign = re.search(r"assign\s+rx_active_o\s*=\s*(.*?);", endpoint_text, re.S)
    record("receive_only_path_independent_of_permit", bool(rx_assign) and
           "permit" not in rx_assign.group(1).lower() and "rxd" in rx_assign.group(1).lower())
    record("canonical_constants_consumed", "generated/tfdu_safety_config.svh" in production_text and
           (ROOT / "config/generated/tfdu_safety_constants.json").is_file())
    record("test_fault_injection_absent_from_production", not ({"fault_inject", "test_force", "test_only"} & identifiers))

    active_profile = json.loads((ROOT / "board_profiles/ACTIVE_PROFILE.json").read_text(encoding="utf-8"))
    safety_config = yaml.safe_load((ROOT / "config/tfdu_safety.yaml").read_text(encoding="utf-8"))
    generated_constants = json.loads(
        (ROOT / "config/generated/tfdu_safety_constants.json").read_text(encoding="utf-8"))
    full_scale_tb = (ROOT / "sim/tb/tb_p8c_full_scale.sv").read_text(encoding="utf-8")
    full_scale_literals = [
        f".CLOCK_HZ({int(safety_config['canonical_clock_hz']):_})",
        f".STARTUP_US({int(safety_config['receiver_startup_us'])})",
        f".WINDOW_US({int(safety_config['rolling_duty_window_us'])})",
        f".MAX_CONTINUOUS_HIGH_US({int(safety_config['max_continuous_txd_high_us'])})",
    ]
    record("canonical_full_scale_vector_bound_to_config",
           generated_constants.get("source_sha256") == sha256(ROOT / "config/tfdu_safety.yaml")
           and all(value in full_scale_tb for value in full_scale_literals),
           full_scale_literals)
    z7020_profiles = {name: value for name, value in safety_config["physical_profiles"].items() if "Z7020" in name}
    record("ax7010_xdc_not_reused_for_z7020", active_profile.get("hardware_target", "").startswith("Zynq-7010") and
           all("xdc" not in value for value in z7020_profiles.values()))
    record("project_constraints_unchanged", sha256(ROOT / "PROJECT_CONSTRAINTS.txt") ==
           manifest["project_constraints_sha256"])
    record("active_z7010_xdc_unchanged", sha256(ROOT / "constraints/active/PORT1.generated.xdc") ==
           manifest["active_z7010_xdc_sha256"])
    active_xdc_text = (ROOT / "constraints/active/PORT1.generated.xdc").read_text(
        encoding="utf-8", errors="replace").lower()
    followup = safety_config.get("hardware_followup", {})
    record("z7010_permit_pin_not_silently_assigned",
           "global_permit" not in active_xdc_text
           and followup.get("z7010_global_permit_pin_freeze") == "PENDING_P9_PIN_FREEZE"
           and followup.get("global_permit_board_pulldown_contract") == "DEFINED",
           {"pin_freeze": followup.get("z7010_global_permit_pin_freeze"),
            "board_pulldown_contract": followup.get("global_permit_board_pulldown_contract")})

    p8b_results = {}
    for value, expected in manifest["p8b_consumed_sources"].items():
        actual = sha256(ROOT / value)
        p8b_results[value] = {"expected": expected, "actual": actual, "match": expected == actual}
    record("p8b_sources_not_forked", all(item["match"] for item in p8b_results.values()), p8b_results)

    p8b_checkpoint_evidence = {
        "evidence/generated/p8b_checkpoint_acceptance_core.json":
            "33ef5c0eaea36ae79ca7753374966af4caed6af022adc512955b6619c5ec6870",
        "evidence/generated/p8b_checkpoint_offline_gate_summary.json":
            "669fb52ee5c5506bca06a77e39fc9700c42fb600f165eb1a1ee4ab413ab78470",
    }
    p8b_checkpoint_results = {
        value: (ROOT / value).is_file() and sha256(ROOT / value) == expected
        for value, expected in p8b_checkpoint_evidence.items()
    }
    state = json.loads((ROOT / "config/project_state.json").read_text(encoding="utf-8"))
    p8b_state = state.get("p8b_acceptance", {})
    record("p8b_checkpoint_evidence_immutable",
           all(p8b_checkpoint_results.values())
           and p8b_state.get("evidence_path") == "evidence/generated/p8b_checkpoint_acceptance_core.json"
           and p8b_state.get("full_regression_path") == "evidence/generated/p8b_checkpoint_offline_gate_summary.json",
           p8b_checkpoint_results)

    no_hw = subprocess.run([sys.executable, "scripts/check_no_hardware_calls.py"], cwd=ROOT,
                           text=True, capture_output=True)
    record("no_hardware_scan", no_hw.returncode == 0 and os.environ.get("NO_HARDWARE") == "1",
           {"environment": os.environ.get("NO_HARDWARE"), "stdout": no_hw.stdout.strip()})
    record("exact_math_guards_present", all(token in production_text for token in
           ("WINDOW_PRODUCT % 1_000_000", "STARTUP_PRODUCT % 1_000_000", "MAX_HIGH_PRODUCT % 1_000_000")))

    failed = sorted(name for name, result in checks.items() if result["status"] != "PASS")
    summary = {
        "status": "PASS" if not failed else "FAIL",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "HARDWARE_SCOPE_PROMOTED": False,
        "checks": checks,
        "failures": failed,
    }
    if args.json:
        print(json.dumps(summary, sort_keys=True))
    else:
        for name, result in checks.items():
            print(f"P8C_STATIC_{name.upper()}={result['status']}")
        print(f"P8C_STATIC_ARCHITECTURE={summary['status']}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
