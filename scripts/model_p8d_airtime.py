#!/usr/bin/env python3
"""P8D duty/ACK/handover/retry/DMA airtime and goodput model."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/p8d_data_plane.yaml"
HANDOVER = ROOT / "evidence/generated/p8b_handover_timing_summary.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    handover = json.loads(HANDOVER.read_text(encoding="utf-8"))
    return config, handover


def handover_metric(config: dict[str, Any], evidence: dict[str, Any]) -> float:
    nominal = float(config["handover_service_gap_source"]["nominal_us"])
    candidates = [
        evidence.get("application_service_gap_us"),
        evidence.get("metrics", {}).get("application_service_gap_us")
        if isinstance(evidence.get("metrics"), dict) else None,
        evidence.get("handover_metrics", {}).get("application_service_gap_us")
        if isinstance(evidence.get("handover_metrics"), dict) else None,
    ]
    for value in candidates:
        if value is not None:
            return float(value)
    # The canonical source explicitly records the imported nominal value; the
    # raw evidence path/hash remains bound even if its schema is stage-specific.
    return nominal


def model_point(config: dict[str, Any], *, lane_count: int, duty_target: float,
                sack_batch: int, outstanding: int, per: float,
                service_gap_us: float, descriptor_gap_us: float) -> dict[str, Any]:
    p = config["airtime_model_parameters"]
    raw_lane = float(p["phy_raw_bps_per_lane"])
    payload = int(config["max_l1_payload_bytes"])
    useful = int(config["rfap_v1_useful_chunk_bytes"])
    frame_bytes = payload + int(p["frame_overhead_bytes"])
    frame_airtime_us = frame_bytes * 8.0 / raw_lane * 1e6
    ack_bytes = int(p["ack_frame_payload_bytes"]) + int(p["frame_overhead_bytes"])
    ack_airtime_us = ack_bytes * 8.0 / raw_lane * 1e6
    nominal_high = float(p["nominal_txd_high_fraction"])
    active_ratio = min(1.0, duty_target / nominal_high)
    frame_payload_ceiling = lane_count * payload * 8.0 / (frame_airtime_us * 1e-6)
    rfap_useful_ceiling = lane_count * useful * 8.0 / (frame_airtime_us * 1e-6)
    duty_limited = rfap_useful_ceiling * active_ratio

    # One aggregate ACK covers sack_batch data frames. Direction guards are
    # charged at both turnarounds. The aggregate stream stripes those frames
    # across the available lanes.
    data_batch_airtime_us = max(1.0, sack_batch / lane_count) * frame_airtime_us
    ack_fraction = (ack_airtime_us + 2.0 * float(p["direction_guard_us"])) / (
        data_batch_airtime_us + ack_airtime_us + 2.0 * float(p["direction_guard_us"]))
    pitch_us = float(config["handover_service_gap_source"]["fixed_module_pitch_time_at_600rpm_us"])
    handover_fraction = min(0.99, service_gap_us / pitch_us)
    descriptor_fraction = descriptor_gap_us / (frame_airtime_us + descriptor_gap_us)
    retry_fraction = min(0.99, max(0.0, per))
    placeholder_fraction = float(p["ps_network_spi_placeholder_overhead_fraction"])
    required_occupancy = max(sack_batch, lane_count * math.ceil(
        (ack_airtime_us + 2.0 * float(p["direction_guard_us"]) + frame_airtime_us) /
        frame_airtime_us))
    window_factor = min(1.0, outstanding / required_occupancy)
    efficiency = ((1.0 - ack_fraction) * (1.0 - handover_fraction) *
                  (1.0 - retry_fraction) * (1.0 - descriptor_fraction) *
                  (1.0 - placeholder_fraction) * window_factor)
    application = duty_limited * efficiency
    serialized_latency_us = (required_occupancy / lane_count) * frame_airtime_us
    latency_p50 = serialized_latency_us + ack_airtime_us + service_gap_us * 0.5
    return {
        "lane_count": lane_count, "duty_target": duty_target,
        "sack_batch": sack_batch, "outstanding": outstanding, "per": per,
        "handover_service_gap_us": service_gap_us,
        "descriptor_gap_us": descriptor_gap_us,
        "phy_raw_capacity_bps": lane_count * raw_lane,
        "frame_airtime_us": frame_airtime_us,
        "frame_payload_ceiling_bps": frame_payload_ceiling,
        "rfap_useful_ceiling_bps": rfap_useful_ceiling,
        "duty_limited_capacity_bps": duty_limited,
        "ack_sack_overhead_fraction": ack_fraction,
        "handover_overhead_fraction": handover_fraction,
        "retry_overhead_fraction": retry_fraction,
        "descriptor_gap_overhead_fraction": descriptor_fraction,
        "placeholder_overhead_fraction": placeholder_fraction,
        "window_factor": window_factor,
        "modeled_application_goodput_bps": application,
        "required_window_occupancy": required_occupancy,
        "latency_p50_estimate_us": latency_p50,
        "latency_p99_estimate_us": latency_p50 + float(p["latency_jitter_us"]) * 2.326,
    }


def run_model() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    config, handover = load_inputs()
    service_gap = handover_metric(config, handover)
    p = config["airtime_model_parameters"]
    baseline = model_point(
        config, lane_count=8, duty_target=float(config["duty_design_target"]),
        sack_batch=int(p["direction_window_frames"]), outstanding=64,
        per=float(p["nominal_per"]), service_gap_us=service_gap,
        descriptor_gap_us=float(p["dma_descriptor_gap_us"]))
    sweep: list[dict[str, Any]] = []
    for lane_count in (1, 2, 4, 8):
        for duty in (0.18, 0.199):
            for sack_batch in (1, 4, 8, 16, 32):
                for outstanding in (8, 16, 32, 64):
                    for per in (0.0, 0.01, 0.03, 0.10):
                        for gap in (0.0, service_gap, 100.0):
                            for descriptor_gap in (0.0, 0.5, 2.0):
                                sweep.append(model_point(
                                    config, lane_count=lane_count, duty_target=duty,
                                    sack_batch=sack_batch, outstanding=outstanding,
                                    per=per, service_gap_us=gap,
                                    descriptor_gap_us=descriptor_gap))
    hard_target = 16_000_000.0
    stretch_target = 19_200_000.0
    maximum_overhead = max(0.0, 1.0 - hard_target / baseline["duty_limited_capacity_bps"])
    architecture = "PASS" if baseline["modeled_application_goodput_bps"] >= hard_target else "FAIL_WITH_EXPLICIT_BLOCKER"
    # At the normal 18% design target, the useful physical ceiling itself is
    # below 19.2 Mbit/s, before ACK/handover/retry/DMA overhead.
    stretch = "PASS" if baseline["modeled_application_goodput_bps"] >= stretch_target else "FAIL"
    blockers = []
    if architecture != "PASS":
        blockers.append("Modeled 8-lane goodput at the 18% design target is below 16 Mbit/s; optimize framing/ACK batching/service gap without relaxing safety or integrity.")
    if stretch != "PASS":
        blockers.append("The 18% duty-limited RFAP useful ceiling is below 19.2 Mbit/s; the stretch target is not feasible with the frozen v1 frame/chunk geometry.")
    summary = {
        "schema_version": 1, "status": "PASS" if architecture == "PASS" else "FAIL",
        "test_id": "P8D-AIRTIME-BUDGET-MODEL", "profile": "P8D_8LANE_MODEL",
        "config_path": "config/p8d_data_plane.yaml", "config_sha256": sha256(CONFIG),
        "p8b_handover_evidence_path": "evidence/generated/p8b_handover_timing_summary.json",
        "p8b_handover_evidence_sha256": sha256(HANDOVER),
        "baseline": baseline, "sensitivity_rows": len(sweep),
        "required_maximum_total_overhead_fraction_for_16mbps": maximum_overhead,
        "8LANE_16MBPS_ARCHITECTURE_FEASIBILITY": architecture,
        "19P2MBPS_STRETCH_FEASIBILITY": stretch,
        "architecture_blockers": blockers,
        "performance_scope": "OFFLINE_ARCHITECTURE_MODEL_ONLY",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    return summary, sweep


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-csv", type=Path)
    args = parser.parse_args(argv)
    summary, sweep = run_model()
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps({"summary": summary, "sweep": sweep},
                                               indent=2, sort_keys=True) + "\n",
                                    encoding="utf-8", newline="\n")
    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(sweep[0]))
            writer.writeheader()
            writer.writerows(sweep)
    print(json.dumps(summary, sort_keys=True) if args.json_summary else
          f"P8D_AIRTIME_BUDGET={summary['status']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
