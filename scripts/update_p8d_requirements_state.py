#!/usr/bin/env python3
"""Advance P8D machine state and close portable data-plane requirements."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from p8a_common import render_project_status, render_traceability


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "config/project_state.json"
REQ_PATH = ROOT / "config/project_requirements.yaml"
STATUS_PATH = ROOT / "PROJECT_STATUS.md"
TRACE_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"

SCOPE = "PORTABLE_FUNCTION_PASS / OFFLINE_RTL_SOFTWARE_MODEL"
FOLLOWUP = (
    "Real AXI DMA/DDR/cache coherency, target implementation timing/CDC, Z7020 hardware, "
    "rotation, external throughput, and final-product acceptance remain pending P8E/P9 or later."
)


SPECS: dict[str, dict[str, Any]] = {
    "L2-ARQ-001": {"text": "Each endpoint direction uses bounded selective-repeat TX/RX windows.",
                    "test": "P8D-SELECTIVE-REPEAT-RTL", "evidence": "p8d_selective_repeat_rtl_summary",
                    "artifacts": ["rtl/ir_selective_repeat_tx.sv", "rtl/ir_selective_repeat_rx.sv"]},
    "L2-ARQ-002": {"text": "The shared global outstanding window supports at least 32 frames.",
                    "test": "P8D-CANONICAL-CONFIG", "evidence": "p8d_data_plane_config_summary",
                    "artifacts": ["config/p8d_data_plane.yaml", "rtl/ir_data_plane_top.sv"]},
    "L2-SEQ-001": {"text": "Sequence width is at least 16 bits and modular wrap is bit-exact.",
                    "test": "P8D-SELECTIVE-REPEAT-RTL", "evidence": "p8d_selective_repeat_rtl_summary",
                    "artifacts": ["rtl/ir_seq_math_pkg.sv", "sim/tb/tb_ir_seq_math.sv"]},
    "L2-SACK-001": {"text": "The negotiated SACK window supports at least 32 bits.",
                     "test": "P8D-SACK-ACK-AGGREGATION", "evidence": "p8d_sack_ack_aggregation_summary",
                     "artifacts": ["rtl/ir_sack_codec.sv", "config/p8d_data_plane.yaml"]},
    "L2-SACK-002": {"text": "ACK aggregation has a bounded frame threshold and maximum delay.",
                     "test": "P8D-SACK-ACK-AGGREGATION", "evidence": "p8d_sack_ack_aggregation_summary",
                     "artifacts": ["rtl/ir_ack_aggregator.sv", "sim/tb/tb_ir_sack_ack_aggregation.sv"]},
    "L2-DUP-001": {"text": "A duplicate logical frame never commits or completes twice.",
                    "test": "P8D-PYTHON-REFERENCE-CAMPAIGN", "evidence": "p8d_selective_repeat_reference_summary",
                    "artifacts": ["tools/p8d_data_plane_reference.py", "rtl/ir_selective_repeat_rx.sv"]},
    "L2-STALE-001": {"text": "Stale session/path data and ACK records are rejected.",
                      "test": "P8D-SELECTIVE-REPEAT-RTL", "evidence": "p8d_selective_repeat_rtl_summary",
                      "artifacts": ["rtl/ir_selective_repeat_tx.sv", "rtl/ir_selective_repeat_rx.sv"]},
    "L2-MIG-001": {"text": "Only unacknowledged frames may migrate across eligible lanes or paths.",
                    "test": "P8D-SCHEDULER-MIGRATION", "evidence": "p8d_scheduler_migration_summary",
                    "artifacts": ["rtl/ir_retry_migration.sv", "sim/tb/tb_ir_scheduler_migration.sv"]},
    "L2-RETRY-001": {"text": "Retry count, timeout/backoff, and exhaustion are bounded.",
                      "test": "P8D-SELECTIVE-REPEAT-RTL", "evidence": "p8d_selective_repeat_rtl_summary",
                      "artifacts": ["rtl/ir_selective_repeat_tx.sv", "config/p8d_data_plane.yaml"]},
    "SCHED-001": {"text": "Scheduling is health-aware and weighted across eligible lanes.",
                  "test": "P8D-SCHEDULER-MIGRATION", "evidence": "p8d_scheduler_migration_summary",
                  "artifacts": ["rtl/ir_health_weighted_scheduler.sv", "tools/p8d_data_plane_reference.py"]},
    "SCHED-002": {"text": "A faulted lane does not block work on healthy eligible lanes.",
                  "test": "P8D-SCHEDULER-MIGRATION", "evidence": "p8d_scheduler_migration_summary",
                  "artifacts": ["rtl/ir_health_weighted_scheduler.sv", "sim/tb/tb_ir_scheduler_migration.sv"]},
    "SCHED-003": {"text": "Scheduler fairness and starvation are explicitly bounded.",
                  "test": "P8D-SCHEDULER-MIGRATION", "evidence": "p8d_scheduler_migration_summary",
                  "artifacts": ["rtl/ir_health_weighted_scheduler.sv", "config/p8d_data_plane.yaml"]},
    "AXIS-001": {"text": "Aggregate AXI-Stream transfers have no loss or duplication under arbitrary backpressure.",
                 "test": "P8D-AXIS-BACKPRESSURE", "evidence": "p8d_axis_backpressure_summary",
                 "artifacts": ["rtl/ir_axis_tx_frontend.sv", "rtl/ir_axis_rx_backend.sv"]},
    "DMA-001": {"text": "Independent bounded TX and RX scatter-gather descriptor rings are modeled.",
                "test": "P8D-DMA-DESCRIPTOR-RING", "evidence": "p8d_dma_descriptor_ring_summary",
                "artifacts": ["rtl/ir_dma_descriptor_model.sv", "software/ps_driver/p8d_driver.h"]},
    "DMA-002": {"text": "Descriptor ownership permits exactly one completion and one reclaim.",
                "test": "P8D-DMA-DESCRIPTOR-RING", "evidence": "p8d_dma_descriptor_ring_summary",
                "artifacts": ["rtl/ir_dma_descriptor_model.sv", "sim/tb/tb_ir_dma_descriptor_ring.sv"]},
    "DMA-003": {"text": "Reset and abort deterministically reclaim ring and payload ownership.",
                "test": "P8D-DMA-DESCRIPTOR-RING", "evidence": "p8d_dma_descriptor_ring_summary",
                "artifacts": ["rtl/ir_dma_descriptor_model.sv", "tools/p8d_data_plane_reference.py"]},
    "DMA-004": {"text": "Descriptor generation rejects stale completions after wrap or reset.",
                "test": "P8D-DMA-DESCRIPTOR-RING", "evidence": "p8d_dma_descriptor_ring_summary",
                "artifacts": ["rtl/ir_dma_descriptor_model.sv", "software/ps_driver/p8d_driver.c"]},
    "RFAP-001": {"text": "RFAP v1/P7 vectors and legacy fallback remain compatible.",
                 "test": "P8D-RFAP-V1-VNEXT-COMPATIBILITY", "evidence": "p8d_rfap_compatibility_summary",
                 "artifacts": ["tools/p8d_rfap_reference.py", "tests/vectors/p7_app_protocol_vectors.json"]},
    "RFAP-002": {"text": "RFAP vNext streaming validates large objects with bounded memory and atomic publish.",
                 "test": "P8D-RFAP-V1-VNEXT-COMPATIBILITY", "evidence": "p8d_rfap_compatibility_summary",
                 "artifacts": ["tools/p8d_rfap_reference.py", "docs/design/P8D_RFAP_VNEXT_COMPATIBILITY.md"]},
    "PERF-MODEL-001": {"text": "The airtime model includes duty, framing, ACK, retry, handover, and descriptor overhead.",
                       "test": "P8D-AIRTIME-BUDGET-MODEL", "evidence": "p8d_airtime_budget_summary",
                       "artifacts": ["scripts/model_p8d_airtime.py", "config/p8d_data_plane.yaml"]},
    "PERF-MODEL-002": {"text": "The 16 Mbit/s architecture target is explicitly evaluated without increasing duty.",
                       "test": "P8D-AIRTIME-BUDGET-MODEL", "evidence": "p8d_airtime_budget_summary",
                       "artifacts": ["scripts/model_p8d_airtime.py", "evidence/generated/p8d_airtime_budget_summary.json"]},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_records(paths: list[str]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for value in paths:
        path = ROOT / value
        if not path.is_file():
            raise FileNotFoundError(value)
        records.append({"path": value, "sha256": sha256(path)})
    return records


def current_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def write_state(state: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
    STATUS_PATH.write_text(render_project_status(state), encoding="utf-8", newline="\n")


def refresh_pass_hashes(document: dict[str, Any]) -> None:
    for item in document["requirements"]:
        if item.get("status") != "PASS":
            continue
        for record in item.get("artifact_hashes", []):
            path = ROOT / record["path"]
            if path.is_file():
                record["sha256"] = sha256(path)
        if item.get("requirement_id") in SPECS and item.get("artifact_hashes"):
            item["artifact_hash"] = item["artifact_hashes"][0]["sha256"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-progress", action="store_true")
    parser.add_argument("--source-commit")
    args = parser.parse_args()
    source_commit = args.source_commit or current_commit()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("source commit must be a full Git hash")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    document["document_version"] = "5.0"
    by_id = {item["requirement_id"]: item for item in document["requirements"]}

    if args.in_progress:
        state["state_revision"] = "P8D-0"
        state["p8d_status"] = "IN_PROGRESS"
        state["stage_status"]["P8D_SELECTIVE_REPEAT_DMA"] = "IN_PROGRESS"
        state["current_program_stage"] = "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE"
        state["current_run_hardware_authorization"] = False
        state["p8d_no_hardware_actions_executed"] = True
        state["p8e_status"] = "PENDING"
        for req_id, spec in SPECS.items():
            item = by_id.get(req_id)
            if item is None:
                item = {"requirement_id": req_id}
                document["requirements"].append(item)
                by_id[req_id] = item
            item.update({
                "requirement_text": spec["text"], "profile": "P8D_MULTI_PROFILE_OFFLINE",
                "verification_method": "Python reference, XSIM RTL, offline C, OOC synthesis, and evidence consistency gates.",
                "verification_stage": "P8D", "verification_scope": SCOPE,
                "test_id": None, "evidence_path": None, "status": "PENDING", "waiver": None,
                "artifact_hashes": [], "hardware_followup": FOLLOWUP,
            })
            item.pop("artifact_hash", None)
        write_state(state)
        refresh_pass_hashes(document)
    else:
        core_path = ROOT / "evidence/generated/p8d_acceptance_core.json"
        core = json.loads(core_path.read_text(encoding="utf-8"))
        if core.get("status") != "PASS" or core.get("source_commit") != source_commit:
            raise RuntimeError("P8D acceptance core is not PASS and bound to the requested source commit")
        if core.get("NO_HARDWARE_ACTIONS_EXECUTED") is not True:
            raise RuntimeError("P8D acceptance core lacks no-hardware declaration")
        state["state_revision"] = "P8D-1"
        state["p8d_status"] = "PASS"
        state["stage_status"]["P8D_SELECTIVE_REPEAT_DMA"] = "PASS"
        state["current_program_stage"] = "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING"
        state["current_run_hardware_authorization"] = False
        state["p8d_no_hardware_actions_executed"] = True
        state["p8e_status"] = "PENDING"
        state["p8d_acceptance"] = {
            "status": "PASS", "profile": "P8D_MULTI_PROFILE_OFFLINE",
            "scope": SCOPE, "test_id": "P8D-ACCEPTANCE-CORE",
            "source_commit": source_commit,
            "evidence_path": "evidence/generated/p8d_acceptance_core.json",
            "evidence_sha256": sha256(core_path),
            "data_plane_config_path": "config/p8d_data_plane.yaml",
            "data_plane_config_sha256": sha256(ROOT / "config/p8d_data_plane.yaml"),
            "architecture_16mbps_feasibility": core["exit_gates"]["8LANE_16MBPS_ARCHITECTURE_FEASIBILITY"],
            "stretch_19p2mbps_feasibility": core["exit_gates"]["19P2MBPS_STRETCH_FEASIBILITY"],
            "hardware_actions_executed": False, "hardware_scope_promoted": False,
            "scope_exclusions": ["REAL_AXI_DMA", "DDR_HARDWARE", "Z7020_HARDWARE",
                                 "ROTATION_HARDWARE", "THROUGHPUT_HARDWARE", "FINAL_PRODUCT_HARDWARE"],
        }
        state["completed_gates"] = [item for item in state.get("completed_gates", [])
                                    if item.get("gate_id") != "P8D"]
        state["completed_gates"].append({"gate_id": "P8D", "status": "PASS"})
        state["pending_gates"] = [item for item in state.get("pending_gates", [])
                                  if item.get("gate_id") != "P8D"]
        state["last_verified_commit"] = source_commit
        write_state(state)
        for req_id, spec in SPECS.items():
            evidence_path = f"evidence/generated/{spec['evidence']}.json"
            artifacts = [*spec["artifacts"], evidence_path]
            records = hash_records(artifacts)
            item = by_id.get(req_id)
            if item is None:
                item = {"requirement_id": req_id}
                document["requirements"].append(item)
                by_id[req_id] = item
            item.update({
                "requirement_text": spec["text"], "profile": "P8D_MULTI_PROFILE_OFFLINE",
                "verification_method": "Direct Python reference, XSIM RTL, offline C, OOC synthesis, and evidence consistency gates.",
                "verification_stage": "P8D", "verification_scope": SCOPE,
                "test_id": spec["test"], "evidence_path": evidence_path,
                "status": "PASS", "waiver": None, "artifact_hash": records[0]["sha256"],
                "artifact_hashes": records, "hardware_followup": FOLLOWUP,
            })
        refresh_pass_hashes(document)

    REQ_PATH.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
                        encoding="utf-8", newline="\n")
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")
    print(f"P8D_MACHINE_STATE={'IN_PROGRESS' if args.in_progress else 'PASS'}")
    print(f"P8D_REQUIREMENTS_UPDATED={len(SPECS)}")
    print(f"P8D_SOURCE_COMMIT={source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
