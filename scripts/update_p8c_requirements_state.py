#!/usr/bin/env python3
"""Close P8C portable-function requirements and machine state from final evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import yaml

from p8a_common import render_project_status, render_traceability

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "config/project_state.json"
REQ_PATH = ROOT / "config/project_requirements.yaml"
STATUS_PATH = ROOT / "PROJECT_STATUS.md"
TRACE_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
P8B_CHECKPOINT_EVIDENCE = {
    "evidence_path": (
        "evidence/generated/p8b_checkpoint_acceptance_core.json",
        "33ef5c0eaea36ae79ca7753374966af4caed6af022adc512955b6619c5ec6870",
    ),
    "full_regression_path": (
        "evidence/generated/p8b_checkpoint_offline_gate_summary.json",
        "669fb52ee5c5506bca06a77e39fc9700c42fb600f165eb1a1ee4ab413ab78470",
    ),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hashes(paths: list[str]) -> list[dict[str, str]]:
    records = []
    for value in paths:
        path = ROOT / value
        if not path.is_file():
            raise FileNotFoundError(value)
        records.append({"path": value, "sha256": sha256(path)})
    return records


SPECS = {
    "SYS-PERMIT-001": (
        "Each independent endpoint has exactly one local active-high GLOBAL_PERMIT input.",
        "P8C-SINGLE-GLOBAL-PERMIT", "evidence/generated/p8c_single_global_permit_architecture_summary.json",
        ["rtl/ir_tfdu_safety_endpoint.sv", "config/tfdu_safety.yaml", "evidence/generated/p8c_single_global_permit_architecture_summary.json"],
        "Physical signal count, fail-low bias, fanout, and final buffer implementation remain PENDING_D17."),
    "SYS-PERMIT-002": (
        "GLOBAL_PERMIT low forces every local physical Txd output low through the final RTL kill.",
        "P8C-PERMIT-FAULT-INJECTION", "evidence/generated/p8c_permit_fault_injection_summary.json",
        ["rtl/ir_tfdu_safety_endpoint.sv", "sim/tb/tb_p8c_endpoint_safety.sv", "evidence/generated/p8c_permit_fault_injection_summary.json"],
        "External electrical kill path and deassertion latency remain PENDING_D17."),
    "SYS-PERMIT-003": (
        "Canonical RTL has no dual, heartbeat, per-bank, or per-lane external global permit channel.",
        "P8C-STATIC-SINGLE-PERMIT", "evidence/generated/p8c_single_global_permit_architecture_summary.json",
        ["config/p8c_active_sources.json", "scripts/check_p8c_safety_static.py", "evidence/generated/p8c_single_global_permit_architecture_summary.json"],
        "Schematic and netlist uniqueness remain PENDING_D17."),
    "SYS-PERMIT-004": (
        "Permit reassertion requires explicit re-arm and cannot resume a partial frame.",
        "P8C-PERMIT-FAULT-INJECTION", "evidence/generated/p8c_permit_fault_injection_summary.json",
        ["rtl/ir_tfdu_safety_endpoint.sv", "sim/tb/tb_p8c_endpoint_safety.sv", "evidence/generated/p8c_permit_fault_injection_summary.json"],
        "Final-hardware interruption and external observer tests remain PENDING_D17/P9."),
    "SYS-PERMIT-005": (
        "Raw permit deassert reaches the final RTL Txd kill without PS or normal frame completion.",
        "P8C-RAW-PERMIT-FINAL-KILL", "evidence/generated/p8c_permit_fault_injection_summary.json",
        ["rtl/ir_tfdu_safety_endpoint.sv", "sim/tb/tb_p8c_endpoint_safety.sv", "evidence/generated/p8c_permit_fault_injection_summary.json"],
        "Pin-to-final-driver electrical latency remains PENDING_D17."),
    "SYS-PERMIT-006": (
        "Permit low allows controlled receive-only acquisition while every physical TX remains disabled.",
        "P8C-RECEIVE-ONLY-ACQUISITION", "evidence/generated/p8c_receive_only_acquisition_summary.json",
        ["rtl/ir_tfdu_safety_endpoint.sv", "sim/tb/tb_p8c_endpoint_safety.sv", "evidence/generated/p8c_receive_only_acquisition_summary.json"],
        "Receive-only operation on final endpoint hardware remains PENDING_P9_OR_LATER."),
    "PHY-SAFE-001": (
        "TFDU6102 Txd/Rxd/SD polarity and static high-speed Mode semantics are correct in portable RTL.",
        "P8C-TFDU-POLARITY-MODE", "evidence/generated/p8c_continuous_high_guard_summary.json",
        ["rtl/ir_tfdu_physical_module_safety.sv", "rtl/ir_tfdu_safety_endpoint.sv", "evidence/generated/p8c_continuous_high_guard_summary.json"],
        "Final pin electrical polarity and optical behavior remain PENDING_P9/P12."),
    "PHY-SAFE-002": (
        "Normal RX/TX is blocked for at least 500 us after shutdown exit.",
        "P8C-FULL-SCALE-STARTUP", "evidence/generated/p8c_exact_sliding_duty_rtl_summary.json",
        ["rtl/ir_tfdu_physical_module_safety.sv", "sim/tb/tb_p8c_full_scale.sv", "evidence/generated/p8c_exact_sliding_duty_rtl_summary.json"],
        "External shutdown-exit timing measurement remains PENDING_P9."),
    "PHY-SAFE-003": (
        "Portable RTL limits continuous physical Txd high to at most 1 us and latches MAX+1 fault.",
        "P8C-RTL-CONTINUOUS-HIGH", "evidence/generated/p8c_continuous_high_guard_summary.json",
        ["rtl/ir_tfdu_physical_module_safety.sv", "sim/tb/tb_p8c_physical_safety.sv", "evidence/generated/p8c_continuous_high_guard_summary.json"],
        "External pulse-width measurement remains PENDING_P9_OR_LATER."),
    "PHY-SAFE-004": (
        "Each physical module satisfies exact arbitrary-alignment 1000 us strict <20% duty with <=18% target admission.",
        "P8C-RTL-EXACT-DUTY", "evidence/generated/p8c_exact_sliding_duty_rtl_summary.json",
        ["rtl/ir_tfdu_exact_duty_accountant.sv", "sim/tb/tb_p8c_full_scale.sv", "evidence/generated/p8c_exact_sliding_duty_rtl_summary.json"],
        "External per-module rolling-duty measurement remains PENDING_P9_OR_LATER."),
    "PHY-SAFE-005": (
        "Duty-history invalidation requires at least 1000 us all-TX-low cooldown before reuse.",
        "P8C-HISTORY-COOLDOWN", "evidence/generated/p8c_exact_sliding_duty_rtl_summary.json",
        ["rtl/ir_tfdu_exact_duty_accountant.sv", "sim/tb/tb_p8c_exact_duty.sv", "evidence/generated/p8c_exact_sliding_duty_rtl_summary.json"],
        "Final hardware reset/clear sequencing remains PENDING_D17/P9."),
    "PHY-SAFE-006": (
        "Rolling-duty state is bound to physical-module identity and survives lane, path, and permit transitions.",
        "P8C-PHYSICAL-MODULE-ACCOUNTING", "evidence/generated/p8c_physical_module_accounting_summary.json",
        ["rtl/ir_p8c_mapping_safety_adapter.sv", "sim/tb/tb_p8c_profile_matrix.sv", "evidence/generated/p8c_physical_module_accounting_summary.json"],
        "Final 32-module bank wiring and identity audit remain PENDING_D17/P12."),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    source_commit = args.source_commit or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be a full Git hash")
    final_path = ROOT / "evidence/generated/p8c_final_summary.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    if final.get("status") != "PASS" or final.get("P8C_SOURCE_COMMIT") != source_commit:
        raise RuntimeError("P8C final evidence is not a PASS bound to the requested source commit")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state["state_revision"] = "P8C-1"
    state["p8c_no_hardware_actions_executed"] = True
    state["current_program_stage"] = "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE"
    state["stage_status"]["P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT"] = "PASS"
    architecture = state["architecture_status"]
    architecture.update({
        "implementation_status": "RTL_PORTABLE_FUNCTION_PASS_PHYSICAL_PENDING_D17",
        "single_global_permit_rtl_architecture": "PASS",
        "global_permit_physical_implementation": "PENDING_D17",
        "z7010_global_permit_pin_freeze": "PENDING_P9_PIN_FREEZE",
        "exact_rolling_duty_rtl_property": "PASS",
        "tfdu_duty_hardware_measurement": "PENDING_P9_OR_LATER",
    })
    state["p8c_acceptance"] = {
        "status": "PASS", "profile": "P8C_MULTI_PROFILE_OFFLINE",
        "scope": "PORTABLE_FUNCTION_PASS / OFFLINE_RTL",
        "test_id": "P8C-FINAL-ACCEPTANCE", "source_commit": source_commit,
        "evidence_path": "evidence/generated/p8c_final_summary.json",
        "evidence_sha256": sha256(final_path),
        "safety_config_path": "config/tfdu_safety.yaml",
        "safety_config_sha256": sha256(ROOT / "config/tfdu_safety.yaml"),
        "single_global_permit_rtl_architecture": "PASS",
        "global_permit_physical_implementation": "PENDING_D17",
        "z7010_global_permit_pin_freeze": "PENDING_P9_PIN_FREEZE",
        "exact_rolling_duty_rtl_property": "PASS",
        "tfdu_duty_hardware_measurement": "PENDING_P9_OR_LATER",
        "hardware_actions_executed": False, "hardware_scope_promoted": False,
        "scope_exclusions": ["Z7020_HARDWARE", "ROTATION_HARDWARE", "SECTOR_BANK_HARDWARE",
                             "DUTY_EXTERNAL_MEASUREMENT", "FINAL_PRODUCT_HARDWARE"],
    }
    state["completed_gates"] = [item for item in state.get("completed_gates", []) if item.get("gate_id") != "P8C"]
    state["completed_gates"].append({"gate_id": "P8C", "status": "PASS"})
    state["pending_gates"] = [item for item in state["pending_gates"] if item.get("gate_id") != "P8C"]
    state["last_verified_commit"] = source_commit
    p8b = state.get("p8b_acceptance", {})
    for path_key, (path_value, expected_hash) in P8B_CHECKPOINT_EVIDENCE.items():
        path = ROOT / path_value
        if not path.is_file() or sha256(path) != expected_hash:
            raise RuntimeError(f"P8B immutable checkpoint evidence mismatch: {path_value}")
        hash_key = "evidence_sha256" if path_key == "evidence_path" else "full_regression_sha256"
        p8b[path_key] = path_value
        p8b[hash_key] = expected_hash
    geometry_path = ROOT / p8b["geometry_config_path"]
    p8b["geometry_config_sha256"] = sha256(geometry_path)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    STATUS_PATH.write_text(render_project_status(state), encoding="utf-8", newline="\n")

    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    document["document_version"] = "4.0"
    requirements = document["requirements"]
    by_id = {item["requirement_id"]: item for item in requirements}
    for req_id, (text, test_id, evidence_path, artifacts, followup) in SPECS.items():
        item = by_id.get(req_id)
        if item is None:
            item = {"requirement_id": req_id}
            requirements.append(item)
            by_id[req_id] = item
        records = hashes(artifacts)
        item.update({
            "requirement_text": text, "profile": "P8C_MULTI_PROFILE_OFFLINE",
            "verification_method": "Current Python/XSIM/static/OOC evidence with physical hardware follow-up retained.",
            "verification_stage": "P8C", "verification_scope": "PORTABLE_FUNCTION_PASS / OFFLINE_RTL",
            "test_id": test_id, "evidence_path": evidence_path, "status": "PASS", "waiver": None,
            "artifact_hash": records[0]["sha256"], "artifact_hashes": records,
            "hardware_followup": followup,
        })

    # Refresh all pre-existing PASS bindings after the state/status and current
    # regression evidence changed. Failed/historical evidence is never removed.
    for item in requirements:
        if item.get("status") != "PASS":
            continue
        for record in item.get("artifact_hashes", []):
            path = ROOT / record["path"]
            if path.is_file():
                record["sha256"] = sha256(path)
        if item.get("requirement_id") in SPECS and item.get("artifact_hashes"):
            item["artifact_hash"] = item["artifact_hashes"][0]["sha256"]
    REQ_PATH.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
                        encoding="utf-8", newline="\n")
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")
    print(f"P8C_REQUIREMENTS_UPDATED={len(SPECS)}")
    print("P8C_MACHINE_STATE_UPDATED=1")
    print(f"P8C_SOURCE_COMMIT={source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
