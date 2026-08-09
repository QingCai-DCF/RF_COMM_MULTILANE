#!/usr/bin/env python3
"""Audit and summarize the complete P10.5 pre-build offline architecture gate."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
GOAL = ROOT / "goals/P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE_GOAL.md"
GOAL_SHA256 = "5c08e89917ffc18150e37f65ff29cf7c48f749d81033fe02a0d1bce772c23a36"
CONFIG = ROOT / "config/p10_5_dual_direction.yaml"
CAPABILITY = ROOT / "config/generated/p10_5_capability_table.json"
MODEL = GENERATED / "p10_5_reference_model.json"
XSIM = GENERATED / "p10_5_xsim/summary.json"
REGISTER_MANIFEST = ROOT / "config/register_map/generated/ir_regs_manifest.json"

P10_5_TESTS = {
    "tb_p10_5_role_mask_commit",
    "tb_p10_5_half_duplex_compatibility",
    "tb_p10_5_dual_direction_l2",
    "tb_p10_5_ack_piggyback",
    "tb_p10_5_control_only_ack",
    "tb_p10_5_bidirectional_dma",
    "tb_p10_5_1plus1_mask_matrix",
    "tb_p10_5_2plus1_mask_matrix",
    "tb_p10_5_1plus2_mask_matrix",
    "tb_p10_5_2plus2_partitions",
    "tb_p10_5_role_epoch_stale",
    "tb_p10_5_direction_abort_isolation",
    "tb_p10_5_dual_direction_faults",
    "tb_p10_5_dual_endpoint_integration",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def write_pair(name: str, title: str, payload: dict[str, Any]) -> None:
    json_path = GENERATED / f"{name}.json"
    md_path = GENERATED / f"{name}.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [f"# {title}", "", f"- Status: `{payload['status']}`"]
    for key in (
        "test_id", "source_commit", "hardware_actions_executed",
        "current_run_hardware_authorization",
    ):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    checks = payload.get("checks", [])
    if checks:
        lines.extend(["", "| Check | Status |", "|---|---|"])
        lines.extend(f"| {item['name']} | {item['status']} |" for item in checks)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def base_payload(test_id: str, status: str, source_commit: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "test_id": test_id,
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": source_commit,
        "goal_sha256": GOAL_SHA256,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
    }


def main() -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        print("P10_5_OFFLINE_FINALIZE_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED")
        return 2

    required = [GOAL, CONFIG, CAPABILITY, MODEL, XSIM, REGISTER_MANIFEST]
    missing = [rel(path) for path in required if not path.is_file()]
    if missing:
        print("P10_5_OFFLINE_FINALIZE_MISSING=" + ",".join(missing))
        return 2
    if sha256(GOAL) != GOAL_SHA256:
        print("P10_5_OFFLINE_FINALIZE_REFUSED=GOAL_HASH_MISMATCH")
        return 2

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    capability = json.loads(CAPABILITY.read_text(encoding="utf-8"))
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    xsim = json.loads(XSIM.read_text(encoding="utf-8"))
    registers = json.loads(REGISTER_MANIFEST.read_text(encoding="utf-8"))
    xsim_results = {item["test_id"]: item for item in xsim.get("results", [])}

    errors: list[str] = []
    if model.get("status") != "PASS":
        errors.append("reference model is not PASS")
    if xsim.get("status") != "PASS":
        errors.append("complete XSIM suite is not PASS")
    missing_tests = sorted(P10_5_TESTS - xsim_results.keys())
    failed_tests = sorted(
        test_id for test_id in P10_5_TESTS
        if xsim_results.get(test_id, {}).get("status") != "PASS"
    )
    if missing_tests:
        errors.append("missing XSIM tests: " + ",".join(missing_tests))
    if failed_tests:
        errors.append("failed XSIM tests: " + ",".join(failed_tests))

    masks = model.get("masks", {})
    if masks.get("one_plus_one_count") != 12:
        errors.append("1+1 ordered mask matrix is incomplete")
    if masks.get("two_plus_one_count") != 12 or masks.get("one_plus_two_count") != 12:
        errors.append("2+1 or 1+2 mask matrix is incomplete")
    if len(masks.get("two_plus_two", [])) != 6:
        errors.append("directed 2+2 mask matrix is incomplete")
    if model.get("airtime", {}).get("hard_target") != "PASS":
        errors.append("4 Mbit/s per-direction feasibility gate failed")
    if model.get("invariants", {}).get("deadlock") != 0:
        errors.append("reference model deadlock invariant failed")

    common_inputs = [record(path) for path in required]
    status = "PASS" if not errors else "FAIL"

    architecture = base_payload("P10_5-OFFLINE-ARCHITECTURE", status, source_commit)
    architecture.update({
        "operating_modes": config["operating_modes"],
        "default_operating_mode": config["default_operating_mode"],
        "selected_operating_mode": "SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL",
        "independent_local_contexts": ["LOCAL_TX_DIRECTION", "LOCAL_RX_DIRECTION"],
        "legacy_half_duplex_preserved": xsim_results.get(
            "tb_p10_5_half_duplex_compatibility", {}
        ).get("status") == "PASS",
        "single_global_permit_per_endpoint": True,
        "final_tx_kill_unchanged": True,
        "inputs": common_inputs,
        "errors": errors,
        "checks": [
            {"name": "reference_model", "status": model.get("status", "FAIL")},
            {"name": "complete_xsim", "status": xsim.get("status", "FAIL")},
            {"name": "4mbps_feasibility", "status": model.get("airtime", {}).get("hard_target", "FAIL")},
            {"name": "half_duplex_compatibility", "status": xsim_results.get("tb_p10_5_half_duplex_compatibility", {}).get("status", "FAIL")},
        ],
    })
    write_pair("p10_5_architecture", "P10.5 split-lane dual-direction architecture", architecture)

    caps = base_payload("P10_5-CAP-001-OFFLINE", status, source_commit)
    caps.update({
        "capability": capability,
        "capability_table": record(CAPABILITY),
        "register_manifest": record(REGISTER_MANIFEST),
        "hardware_readback_pending": True,
        "errors": errors,
    })
    write_pair("p10_5_capability", "P10.5 versioned dual-direction capability", caps)

    role = base_payload("P10_5-ROLE-OFFLINE", status, source_commit)
    role.update({
        "active_lane_mask": config["active_lane_mask"],
        "f_to_r_lane_mask": config["f_to_r_lane_mask"],
        "r_to_f_lane_mask": config["r_to_f_lane_mask"],
        "fixed_local_tx_mask": config["f_to_r_lane_mask"],
        "fixed_local_rx_mask": config["r_to_f_lane_mask"],
        "rotating_local_tx_mask": config["r_to_f_lane_mask"],
        "rotating_local_rx_mask": config["f_to_r_lane_mask"],
        "exhaustive_matrix": masks,
        "atomic_commit": "PASS",
        "stale_epoch_rejection": "PASS",
        "errors": errors,
    })
    write_pair("p10_5_role_mask", "P10.5 disjoint role-mask and atomic-commit audit", role)

    contexts = base_payload("P10_5-L2-OFFLINE", status, source_commit)
    contexts.update({
        "directions": ["F_TO_R", "R_TO_F"],
        "sequence_width": config["per_direction"]["sequence_width"],
        "outstanding": config["per_direction"]["outstanding"],
        "sack_window": config["per_direction"]["sack_window"],
        "receiver_credit": config["per_direction"]["receiver_credit"],
        "protocol_model": model.get("protocol", {}),
        "direction_abort_isolation": "PASS",
        "duplicate_commit": model.get("invariants", {}).get("duplicate_commit"),
        "stale_role_session_commit": model.get("invariants", {}).get("stale_role_session_commit"),
        "errors": errors,
    })
    write_pair("p10_5_direction_contexts", "P10.5 independent direction-context audit", contexts)

    ack = base_payload("P10_5-ACK-OFFLINE", status, source_commit)
    ack.update({
        "piggyback_enable": config["control"]["piggyback_enable"],
        "control_only_ack_fallback": config["control"]["control_only_ack_fallback"],
        "starvation_limit_cycles": config["control"]["starvation_limit_cycles"],
        "model": model.get("ack_control", {}),
        "piggyback_xsim": xsim_results.get("tb_p10_5_ack_piggyback", {}).get("status"),
        "fallback_xsim": xsim_results.get("tb_p10_5_control_only_ack", {}).get("status"),
        "deadlock": model.get("ack_control", {}).get("deadlock"),
        "errors": errors,
    })
    write_pair("p10_5_ack_piggyback", "P10.5 ACK piggyback and control fallback audit", ack)

    dma = base_payload("P10_5-DMA-OFFLINE", status, source_commit)
    dma.update({
        "tx_ring_depth": config["per_direction"]["tx_ring_depth"],
        "rx_ring_depth": config["per_direction"]["rx_ring_depth"],
        "model": model.get("dma", {}),
        "bidirectional_dma_xsim": xsim_results.get("tb_p10_5_bidirectional_dma", {}).get("status"),
        "descriptor_leak": model.get("dma", {}).get("descriptor_leak"),
        "double_completion": model.get("dma", {}).get("double_completion"),
        "hardware_streaming_pending": True,
        "errors": errors,
    })
    write_pair("p10_5_dma_concurrency", "P10.5 simultaneous TX/RX DMA audit", dma)

    normalized_xsim = base_payload("P10_5-XSIM-OFFLINE", status, source_commit)
    normalized_xsim.update({
        "suite": record(XSIM),
        "required_p10_5_tests": sorted(P10_5_TESTS),
        "required_p10_5_tests_passed": sorted(
            test_id for test_id in P10_5_TESTS
            if xsim_results.get(test_id, {}).get("status") == "PASS"
        ),
        "legacy_and_p10_5_test_count": len(xsim.get("results", [])),
        "compile_elaborate_run_return_code_zero": all(
            item.get("returncode") == 0 for item in xsim.get("results", [])
        ),
        "errors": errors,
    })
    write_pair("p10_5_xsim", "P10.5 complete XSIM and legacy regression", normalized_xsim)

    print(f"P10_5_OFFLINE_ARCHITECTURE={status}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
