from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from math import ceil
from pathlib import Path

from model_effective_payload_rate_options import (
    DATA_HDR_BYTES,
    FDX_LANES_PER_DIRECTION,
    FRAME_FIXED_SYMBOLS,
    HALF_DUPLEX_LANES,
    MAX_PROTOCOL_FRAGMENT_BYTES,
    make_row,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

RAW_PER_LANE_MBPS = 4.0
TARGET_HALF_MBPS = 32.0
TARGET_FDX_PER_DIR_MBPS = 16.0
FRAME_SYMBOLS_PER_BYTE = 4.0


@dataclass
class GapMetrics:
    raw_per_lane_mbps: float
    half_lanes: int
    fdx_lanes_per_direction: int
    raw_half_mbps: float
    raw_fdx_per_dir_mbps: float
    required_efficiency_for_half_payload_target: float
    required_efficiency_for_fdx_payload_target: float
    current_packet_ack_efficiency: float
    current_no_ack_efficiency: float
    current_packet_ack_half_mbps: float
    current_packet_ack_fdx_per_dir_mbps: float
    current_no_ack_half_mbps: float
    current_no_ack_fdx_per_dir_mbps: float
    packet_ack_gap_half_mbps: float
    packet_ack_gap_fdx_per_dir_mbps: float
    no_ack_gap_half_mbps: float
    no_ack_gap_fdx_per_dir_mbps: float
    packet_ack_required_raw_per_lane_mbps: float
    no_ack_required_raw_per_lane_mbps: float
    packet_ack_required_half_lanes: int
    packet_ack_required_fdx_lanes_per_direction: int
    no_ack_required_half_lanes: int
    no_ack_required_fdx_lanes_per_direction: int
    max_fragment_bytes: int
    fixed_overhead_byte_equivalent: float
    data_header_bytes: int
    minimum_fragment_bytes_for_95pct_no_ack_efficiency: int
    minimum_fragment_bytes_for_98pct_no_ack_efficiency: int
    effective_32_16_with_current_raw_possible: bool
    zero_overhead_required_for_payload_equals_raw: bool


def required_raw_per_lane(target_mbps: float, lanes: int, efficiency: float) -> float:
    return target_mbps / (lanes * efficiency)


def required_lanes(target_mbps: float, raw_per_lane_mbps: float, efficiency: float) -> int:
    return ceil(target_mbps / (raw_per_lane_mbps * efficiency))


def min_fragment_for_efficiency(target_efficiency: float, overhead_bytes: float) -> int:
    return ceil((target_efficiency * overhead_bytes) / (1.0 - target_efficiency))


def build_metrics() -> GapMetrics:
    packet_ack = make_row(MAX_PROTOCOL_FRAGMENT_BYTES, 16_384)
    no_ack = make_row(MAX_PROTOCOL_FRAGMENT_BYTES, 16_384)
    packet_eff = packet_ack.per_lane_packet_ack_mbps / RAW_PER_LANE_MBPS
    no_ack_eff = no_ack.per_lane_no_ack_mbps / RAW_PER_LANE_MBPS
    fixed_overhead = DATA_HDR_BYTES + (FRAME_FIXED_SYMBOLS / FRAME_SYMBOLS_PER_BYTE)

    return GapMetrics(
        raw_per_lane_mbps=RAW_PER_LANE_MBPS,
        half_lanes=HALF_DUPLEX_LANES,
        fdx_lanes_per_direction=FDX_LANES_PER_DIRECTION,
        raw_half_mbps=RAW_PER_LANE_MBPS * HALF_DUPLEX_LANES,
        raw_fdx_per_dir_mbps=RAW_PER_LANE_MBPS * FDX_LANES_PER_DIRECTION,
        required_efficiency_for_half_payload_target=TARGET_HALF_MBPS / (RAW_PER_LANE_MBPS * HALF_DUPLEX_LANES),
        required_efficiency_for_fdx_payload_target=TARGET_FDX_PER_DIR_MBPS / (RAW_PER_LANE_MBPS * FDX_LANES_PER_DIRECTION),
        current_packet_ack_efficiency=packet_eff,
        current_no_ack_efficiency=no_ack_eff,
        current_packet_ack_half_mbps=packet_ack.half_8lane_packet_ack_mbps,
        current_packet_ack_fdx_per_dir_mbps=packet_ack.fdx_4lane_packet_ack_mbps,
        current_no_ack_half_mbps=no_ack.half_8lane_no_ack_mbps,
        current_no_ack_fdx_per_dir_mbps=no_ack.fdx_4lane_no_ack_mbps,
        packet_ack_gap_half_mbps=TARGET_HALF_MBPS - packet_ack.half_8lane_packet_ack_mbps,
        packet_ack_gap_fdx_per_dir_mbps=TARGET_FDX_PER_DIR_MBPS - packet_ack.fdx_4lane_packet_ack_mbps,
        no_ack_gap_half_mbps=TARGET_HALF_MBPS - no_ack.half_8lane_no_ack_mbps,
        no_ack_gap_fdx_per_dir_mbps=TARGET_FDX_PER_DIR_MBPS - no_ack.fdx_4lane_no_ack_mbps,
        packet_ack_required_raw_per_lane_mbps=required_raw_per_lane(TARGET_HALF_MBPS, HALF_DUPLEX_LANES, packet_eff),
        no_ack_required_raw_per_lane_mbps=required_raw_per_lane(TARGET_HALF_MBPS, HALF_DUPLEX_LANES, no_ack_eff),
        packet_ack_required_half_lanes=required_lanes(TARGET_HALF_MBPS, RAW_PER_LANE_MBPS, packet_eff),
        packet_ack_required_fdx_lanes_per_direction=required_lanes(TARGET_FDX_PER_DIR_MBPS, RAW_PER_LANE_MBPS, packet_eff),
        no_ack_required_half_lanes=required_lanes(TARGET_HALF_MBPS, RAW_PER_LANE_MBPS, no_ack_eff),
        no_ack_required_fdx_lanes_per_direction=required_lanes(TARGET_FDX_PER_DIR_MBPS, RAW_PER_LANE_MBPS, no_ack_eff),
        max_fragment_bytes=MAX_PROTOCOL_FRAGMENT_BYTES,
        fixed_overhead_byte_equivalent=fixed_overhead,
        data_header_bytes=DATA_HDR_BYTES,
        minimum_fragment_bytes_for_95pct_no_ack_efficiency=min_fragment_for_efficiency(0.95, fixed_overhead),
        minimum_fragment_bytes_for_98pct_no_ack_efficiency=min_fragment_for_efficiency(0.98, fixed_overhead),
        effective_32_16_with_current_raw_possible=False,
        zero_overhead_required_for_payload_equals_raw=True,
    )


def validate(metrics: GapMetrics) -> list[str]:
    failures: list[str] = []
    if metrics.required_efficiency_for_half_payload_target != 1.0:
        failures.append("half-duplex payload target no longer equals raw capacity")
    if metrics.required_efficiency_for_fdx_payload_target != 1.0:
        failures.append("full-duplex payload target no longer equals raw capacity")
    if metrics.current_packet_ack_efficiency >= 1.0 or metrics.current_no_ack_efficiency >= 1.0:
        failures.append("positive-overhead efficiency should remain below 1")
    if metrics.current_packet_ack_half_mbps >= TARGET_HALF_MBPS:
        failures.append("packet-ACK payload unexpectedly reaches 32 Mbit/s")
    if metrics.current_packet_ack_fdx_per_dir_mbps >= TARGET_FDX_PER_DIR_MBPS:
        failures.append("packet-ACK payload unexpectedly reaches 16 Mbit/s per direction")
    if metrics.packet_ack_required_half_lanes <= HALF_DUPLEX_LANES:
        failures.append("packet-ACK half-duplex lane requirement should exceed 8")
    if metrics.packet_ack_required_fdx_lanes_per_direction <= FDX_LANES_PER_DIRECTION:
        failures.append("packet-ACK full-duplex lane requirement should exceed 4 per direction")
    return failures


def write_outputs(metrics: GapMetrics, failures: list[str]) -> tuple[Path, Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "payload_gap_closure_current.md"
    json_path = REPORTS / "payload_gap_closure_current.json"
    csv_path = REPORTS / "payload_gap_closure_current.csv"
    generated = datetime.now().isoformat(timespec="seconds")
    overall = "PASS_RAW_ONLY_GAP_CLASSIFIED" if not failures else "FAIL"

    payload = {
        "generated": generated,
        "overall": overall,
        "failures": failures,
        "metrics": asdict(metrics),
        "interpretation": "With the current 8 x 4 Mbit/s raw PHY, 32/16 Mbit/s can be accepted only as raw capacity. Effective payload 32/16 would require zero overhead, more raw rate, or more lanes.",
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = [
        ("current_raw_half_mbps", metrics.raw_half_mbps, "PASS_RAW"),
        ("current_raw_fdx_per_dir_mbps", metrics.raw_fdx_per_dir_mbps, "PASS_RAW"),
        ("required_payload_efficiency", metrics.required_efficiency_for_half_payload_target, "IMPOSSIBLE_WITH_POSITIVE_OVERHEAD"),
        ("current_packet_ack_efficiency", metrics.current_packet_ack_efficiency, "BELOW_1"),
        ("current_packet_ack_half_mbps", metrics.current_packet_ack_half_mbps, "BELOW_32"),
        ("current_packet_ack_fdx_per_dir_mbps", metrics.current_packet_ack_fdx_per_dir_mbps, "BELOW_16"),
        ("packet_ack_gap_half_mbps", metrics.packet_ack_gap_half_mbps, "GAP"),
        ("packet_ack_gap_fdx_per_dir_mbps", metrics.packet_ack_gap_fdx_per_dir_mbps, "GAP"),
        ("packet_ack_required_raw_per_lane_mbps", metrics.packet_ack_required_raw_per_lane_mbps, "CLOSURE_OPTION"),
        ("packet_ack_required_half_lanes", metrics.packet_ack_required_half_lanes, "CLOSURE_OPTION"),
        ("packet_ack_required_fdx_lanes_per_direction", metrics.packet_ack_required_fdx_lanes_per_direction, "CLOSURE_OPTION"),
        ("no_ack_required_raw_per_lane_mbps", metrics.no_ack_required_raw_per_lane_mbps, "LOWER_BOUND_OPTION"),
        ("minimum_fragment_bytes_for_95pct_no_ack_efficiency", metrics.minimum_fragment_bytes_for_95pct_no_ack_efficiency, "PROTOCOL_FIELD_CHANGE"),
        ("minimum_fragment_bytes_for_98pct_no_ack_efficiency", metrics.minimum_fragment_bytes_for_98pct_no_ack_efficiency, "PROTOCOL_FIELD_CHANGE"),
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value", "classification"])
        for row in rows:
            writer.writerow(row)

    md_lines = [
        "# Payload Gap Closure Model",
        "",
        f"Generated: {generated}",
        "",
        "This is a deterministic offline model. It does not program hardware, write UART, send real TX data, or drive TFDU boards.",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- Evidence type: `OFFLINE_RATE_MODEL_NOT_HARDWARE`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "## Current Boundary",
        "",
        "| item | value |",
        "| --- | ---: |",
        f"| Raw half-duplex capacity | {metrics.raw_half_mbps:.6f} Mbit/s |",
        f"| Raw full-duplex capacity per direction | {metrics.raw_fdx_per_dir_mbps:.6f} Mbit/s |",
        f"| Efficiency required for payload to equal 32/16 | {metrics.required_efficiency_for_half_payload_target:.6f} |",
        f"| Current packet-ACK efficiency | {metrics.current_packet_ack_efficiency:.6f} |",
        f"| Current max-fragment no-ACK efficiency | {metrics.current_no_ack_efficiency:.6f} |",
        f"| Current packet-ACK half-duplex payload | {metrics.current_packet_ack_half_mbps:.6f} Mbit/s |",
        f"| Current packet-ACK full-duplex payload per direction | {metrics.current_packet_ack_fdx_per_dir_mbps:.6f} Mbit/s |",
        f"| Packet-ACK gap to 32 Mbit/s half-duplex payload | {metrics.packet_ack_gap_half_mbps:.6f} Mbit/s |",
        f"| Packet-ACK gap to 16 Mbit/s full-duplex payload | {metrics.packet_ack_gap_fdx_per_dir_mbps:.6f} Mbit/s |",
        "",
        "## Closure Options If 32/16 Becomes Effective Payload",
        "",
        "| option | required change | result |",
        "| --- | --- | --- |",
        "| Keep current 8 lanes / 4 Mbit/s | Treat 32/16 as raw PHY capacity only | Passes current target interpretation; payload reported separately |",
        f"| Increase raw lane rate | At least `{metrics.packet_ack_required_raw_per_lane_mbps:.6f}` Mbit/s per lane for current packet-ACK format | Would close 32/16 payload gap with 8 half-duplex lanes or 4+4 FDX lanes |",
        f"| Add lanes | `{metrics.packet_ack_required_half_lanes}` half-duplex lanes, or `{metrics.packet_ack_required_fdx_lanes_per_direction}` lanes per direction for full-duplex packet-ACK | Exceeds current 8-lane final topology in full-duplex |",
        f"| Remove ACK cost lower bound | At least `{metrics.no_ack_required_raw_per_lane_mbps:.6f}` Mbit/s per lane even with max-fragment no-ACK upper bound | Still requires more than current 4 Mbit/s raw per lane |",
        f"| Expand fragment field | At least `{metrics.minimum_fragment_bytes_for_95pct_no_ack_efficiency}` bytes for 95% no-ACK efficiency, `{metrics.minimum_fragment_bytes_for_98pct_no_ack_efficiency}` bytes for 98% | Helps approach raw capacity but cannot equal raw with positive overhead |",
        "| Lower effective-payload target | Accept current packet-ACK payload about 28.97/14.48 Mbit/s | Would require explicit target change before claiming completion |",
        "",
        "## Acceptance Consequence",
        "",
        "The current hardware-rate target can be closed as raw PHY capacity, which is already backed by simulation/model and offline bitstream evidence. It cannot be honestly closed as 32/16 Mbit/s effective payload without a target change or additional physical-rate budget.",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return md_path, json_path, csv_path


def main() -> int:
    metrics = build_metrics()
    failures = validate(metrics)
    md_path, json_path, csv_path = write_outputs(metrics, failures)
    overall = "PASS_RAW_ONLY_GAP_CLASSIFIED" if not failures else "FAIL"
    print(
        "RF_COMM_PAYLOAD_GAP_CLOSURE "
        f"overall={overall} "
        f"packet_ack_half_mbps={metrics.current_packet_ack_half_mbps:.6f} "
        f"packet_ack_fdx_mbps={metrics.current_packet_ack_fdx_per_dir_mbps:.6f} "
        f"packet_ack_gap_half_mbps={metrics.packet_ack_gap_half_mbps:.6f} "
        f"packet_ack_gap_fdx_mbps={metrics.packet_ack_gap_fdx_per_dir_mbps:.6f} "
        f"required_raw_per_lane_packet_ack_mbps={metrics.packet_ack_required_raw_per_lane_mbps:.6f} "
        f"required_half_lanes_packet_ack={metrics.packet_ack_required_half_lanes} "
        f"required_fdx_lanes_per_dir_packet_ack={metrics.packet_ack_required_fdx_lanes_per_direction} "
        f"no_hardware_action=1 markdown={md_path.relative_to(ROOT)} json={json_path.relative_to(ROOT)} csv={csv_path.relative_to(ROOT)}"
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
