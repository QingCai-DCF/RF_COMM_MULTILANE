from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from math import ceil
from pathlib import Path

from model_effective_payload_rate_options import (
    ACK_HDR_BYTES,
    DATA_HDR_BYTES,
    FDX_LANES_PER_DIRECTION,
    FRAME_FIXED_SYMBOLS,
    HALF_DUPLEX_LANES,
    MAX_PROTOCOL_FRAGMENT_BYTES,
    make_row,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

TARGET_HALF_MBPS = 32.0
TARGET_FDX_PER_DIR_MBPS = 16.0
RAW_PER_LANE_MBPS = 4.0
FRAME_SYMBOLS_PER_BYTE = 4.0


@dataclass
class BoundaryMetrics:
    raw_per_lane_mbps: float
    raw_half_8lane_mbps: float
    raw_fdx_4lane_per_dir_mbps: float
    data_header_bytes: int
    ack_header_bytes: int
    frame_fixed_symbols: int
    frame_fixed_byte_equivalent: float
    max_fragment_bytes: int
    max_fragment_no_ack_efficiency: float
    max_fragment_no_ack_per_lane_mbps: float
    max_fragment_no_ack_half_8lane_mbps: float
    max_fragment_no_ack_fdx_4lane_mbps: float
    max_fragment_no_ack_required_lanes_half_32: int
    max_fragment_no_ack_required_lanes_per_dir_fdx_16: int
    max_fragment_no_ack_required_raw_per_lane_mbps: float
    best_packet_ack_fragment_bytes: int
    best_packet_ack_packet_bytes: int
    best_packet_ack_efficiency: float
    best_packet_ack_per_lane_mbps: float
    best_packet_ack_half_8lane_mbps: float
    best_packet_ack_fdx_4lane_mbps: float
    best_packet_ack_required_lanes_half_32: int
    best_packet_ack_required_lanes_per_dir_fdx_16: int
    best_packet_ack_required_raw_per_lane_mbps: float
    effective_32_16_possible_with_current_raw: bool
    rate_claim_must_be_raw_phy: bool


def required_lanes(target_mbps: float, per_lane_payload_mbps: float) -> int:
    return ceil(target_mbps / per_lane_payload_mbps)


def required_raw_per_lane(target_mbps: float, lanes: int, efficiency: float) -> float:
    return target_mbps / (lanes * efficiency)


def build_metrics() -> BoundaryMetrics:
    raw_half = RAW_PER_LANE_MBPS * HALF_DUPLEX_LANES
    raw_fdx = RAW_PER_LANE_MBPS * FDX_LANES_PER_DIRECTION

    max_no_ack = make_row(MAX_PROTOCOL_FRAGMENT_BYTES, 16_384)
    options = [
        make_row(fragment, packet)
        for fragment in (16, 32, 64, 128, 247, 255)
        for packet in (256, 1024, 4096, 16_384)
        if packet >= fragment
    ]
    best_ack = max(options, key=lambda row: row.half_8lane_packet_ack_mbps)

    fixed_byte_equiv = FRAME_FIXED_SYMBOLS / FRAME_SYMBOLS_PER_BYTE
    max_no_ack_eff = max_no_ack.per_lane_no_ack_mbps / RAW_PER_LANE_MBPS
    best_ack_eff = best_ack.per_lane_packet_ack_mbps / RAW_PER_LANE_MBPS

    return BoundaryMetrics(
        raw_per_lane_mbps=RAW_PER_LANE_MBPS,
        raw_half_8lane_mbps=raw_half,
        raw_fdx_4lane_per_dir_mbps=raw_fdx,
        data_header_bytes=DATA_HDR_BYTES,
        ack_header_bytes=ACK_HDR_BYTES,
        frame_fixed_symbols=FRAME_FIXED_SYMBOLS,
        frame_fixed_byte_equivalent=fixed_byte_equiv,
        max_fragment_bytes=MAX_PROTOCOL_FRAGMENT_BYTES,
        max_fragment_no_ack_efficiency=max_no_ack_eff,
        max_fragment_no_ack_per_lane_mbps=max_no_ack.per_lane_no_ack_mbps,
        max_fragment_no_ack_half_8lane_mbps=max_no_ack.half_8lane_no_ack_mbps,
        max_fragment_no_ack_fdx_4lane_mbps=max_no_ack.fdx_4lane_no_ack_mbps,
        max_fragment_no_ack_required_lanes_half_32=required_lanes(
            TARGET_HALF_MBPS, max_no_ack.per_lane_no_ack_mbps
        ),
        max_fragment_no_ack_required_lanes_per_dir_fdx_16=required_lanes(
            TARGET_FDX_PER_DIR_MBPS, max_no_ack.per_lane_no_ack_mbps
        ),
        max_fragment_no_ack_required_raw_per_lane_mbps=required_raw_per_lane(
            TARGET_HALF_MBPS, HALF_DUPLEX_LANES, max_no_ack_eff
        ),
        best_packet_ack_fragment_bytes=best_ack.fragment_bytes,
        best_packet_ack_packet_bytes=best_ack.packet_bytes,
        best_packet_ack_efficiency=best_ack_eff,
        best_packet_ack_per_lane_mbps=best_ack.per_lane_packet_ack_mbps,
        best_packet_ack_half_8lane_mbps=best_ack.half_8lane_packet_ack_mbps,
        best_packet_ack_fdx_4lane_mbps=best_ack.fdx_4lane_packet_ack_mbps,
        best_packet_ack_required_lanes_half_32=required_lanes(
            TARGET_HALF_MBPS, best_ack.per_lane_packet_ack_mbps
        ),
        best_packet_ack_required_lanes_per_dir_fdx_16=required_lanes(
            TARGET_FDX_PER_DIR_MBPS, best_ack.per_lane_packet_ack_mbps
        ),
        best_packet_ack_required_raw_per_lane_mbps=required_raw_per_lane(
            TARGET_HALF_MBPS, HALF_DUPLEX_LANES, best_ack_eff
        ),
        effective_32_16_possible_with_current_raw=False,
        rate_claim_must_be_raw_phy=True,
    )


def validate(metrics: BoundaryMetrics) -> list[str]:
    failures: list[str] = []
    if abs(metrics.raw_half_8lane_mbps - TARGET_HALF_MBPS) > 1e-9:
        failures.append("raw half-duplex capacity no longer matches 32 Mbit/s")
    if abs(metrics.raw_fdx_4lane_per_dir_mbps - TARGET_FDX_PER_DIR_MBPS) > 1e-9:
        failures.append("raw full-duplex per-direction capacity no longer matches 16 Mbit/s")
    if metrics.frame_fixed_symbols <= 0 or metrics.data_header_bytes <= 0:
        failures.append("positive protocol overhead proof precondition is not met")
    if metrics.max_fragment_no_ack_half_8lane_mbps >= TARGET_HALF_MBPS:
        failures.append("current max-fragment no-ACK half-duplex payload reaches raw target unexpectedly")
    if metrics.max_fragment_no_ack_fdx_4lane_mbps >= TARGET_FDX_PER_DIR_MBPS:
        failures.append("current max-fragment no-ACK full-duplex payload reaches raw target unexpectedly")
    if metrics.best_packet_ack_half_8lane_mbps >= TARGET_HALF_MBPS:
        failures.append("current packet-ACK half-duplex payload reaches raw target unexpectedly")
    if metrics.best_packet_ack_fdx_4lane_mbps >= TARGET_FDX_PER_DIR_MBPS:
        failures.append("current packet-ACK full-duplex payload reaches raw target unexpectedly")
    if metrics.max_fragment_no_ack_required_lanes_half_32 <= HALF_DUPLEX_LANES:
        failures.append("required half-duplex lanes should exceed available lanes for payload 32")
    if metrics.max_fragment_no_ack_required_lanes_per_dir_fdx_16 <= FDX_LANES_PER_DIRECTION:
        failures.append("required full-duplex lanes per direction should exceed available lanes for payload 16")
    return failures


def write_reports(metrics: BoundaryMetrics, json_output: Path | None) -> tuple[Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d")
    md_path = REPORTS / f"rate_boundary_proof_{date_tag}.md"
    json_path = json_output if json_output is not None else REPORTS / f"rate_boundary_proof_{date_tag}.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "verdict": "RATE_BOUNDARY_PROOF_PASS",
        "metrics": asdict(metrics),
        "interpretation": (
            "The current 8-lane 4 Mbit/s-per-lane PHY can meet 32/16 Mbit/s only as raw PHY capacity. "
            "Any reliable payload measurement with positive frame/protocol overhead is strictly below raw capacity."
        ),
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    md_lines = [
        "# RF_COMM Rate Boundary Proof",
        "",
        f"Generated: {payload['generated']}",
        "",
        "This is a deterministic arithmetic proof. It does not program hardware and does not drive TFDU boards.",
        "",
        "## Verdict",
        "",
        "`RATE_BOUNDARY_PROOF_PASS`",
        "",
        "The current 8-lane PHY can meet 32 Mbit/s half-duplex and 16 Mbit/s per direction full-duplex only as raw PHY capacity. If those same numbers are required as effective payload or PC-to-PC throughput, the current 8 x 4 Mbit/s raw physical budget is insufficient because any positive frame/protocol overhead makes payload throughput strictly lower than raw throughput.",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Raw per lane | {metrics.raw_per_lane_mbps:.6f} Mbit/s |",
        f"| Raw half-duplex, 8 lanes | {metrics.raw_half_8lane_mbps:.6f} Mbit/s |",
        f"| Raw full-duplex, 4 lanes per direction | {metrics.raw_fdx_4lane_per_dir_mbps:.6f} Mbit/s |",
        f"| DATA header | {metrics.data_header_bytes} bytes |",
        f"| ACK header | {metrics.ack_header_bytes} bytes |",
        f"| Fixed PHY symbols per frame | {metrics.frame_fixed_symbols} symbols |",
        f"| Fixed PHY byte equivalent | {metrics.frame_fixed_byte_equivalent:.3f} bytes |",
        f"| Max current fragment | {metrics.max_fragment_bytes} bytes |",
        f"| Max-fragment no-ACK efficiency | {metrics.max_fragment_no_ack_efficiency:.6f} |",
        f"| Max-fragment no-ACK half-duplex payload | {metrics.max_fragment_no_ack_half_8lane_mbps:.6f} Mbit/s |",
        f"| Max-fragment no-ACK full-duplex payload per direction | {metrics.max_fragment_no_ack_fdx_4lane_mbps:.6f} Mbit/s |",
        f"| Lanes needed for 32 Mbit/s payload, max-fragment no-ACK | {metrics.max_fragment_no_ack_required_lanes_half_32} |",
        f"| Lanes per direction needed for 16 Mbit/s payload, max-fragment no-ACK | {metrics.max_fragment_no_ack_required_lanes_per_dir_fdx_16} |",
        f"| Raw per lane needed for 32/16 payload, max-fragment no-ACK | {metrics.max_fragment_no_ack_required_raw_per_lane_mbps:.6f} Mbit/s |",
        f"| Best packet-ACK fragment | {metrics.best_packet_ack_fragment_bytes} bytes |",
        f"| Best packet-ACK packet | {metrics.best_packet_ack_packet_bytes} bytes |",
        f"| Best packet-ACK efficiency | {metrics.best_packet_ack_efficiency:.6f} |",
        f"| Best packet-ACK half-duplex payload | {metrics.best_packet_ack_half_8lane_mbps:.6f} Mbit/s |",
        f"| Best packet-ACK full-duplex payload per direction | {metrics.best_packet_ack_fdx_4lane_mbps:.6f} Mbit/s |",
        f"| Lanes needed for 32 Mbit/s payload, packet-ACK | {metrics.best_packet_ack_required_lanes_half_32} |",
        f"| Lanes per direction needed for 16 Mbit/s payload, packet-ACK | {metrics.best_packet_ack_required_lanes_per_dir_fdx_16} |",
        f"| Raw per lane needed for 32/16 payload, packet-ACK | {metrics.best_packet_ack_required_raw_per_lane_mbps:.6f} Mbit/s |",
        "",
        "## Acceptance Consequence",
        "",
        "For the current target and current PHY, the 32/16 Mbit/s acceptance claim must be classified as `raw_phy_only`. Effective payload and PC-to-PC throughput should continue to be reported separately. If effective payload 32/16 Mbit/s becomes mandatory, the project needs a hard constraint change plus more raw PHY capacity, more lanes, or lower-overhead/higher-rate signaling.",
    ]
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return md_path, json_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)

    metrics = build_metrics()
    failures = validate(metrics)
    md_path, json_path = write_reports(metrics, args.json_output)
    if failures:
        print("RATE_BOUNDARY_PROOF_FAIL " + ";".join(failures))
        return 1
    print(
        "RATE_BOUNDARY_PROOF_PASS "
        f"raw_half_8lane_mbps={metrics.raw_half_8lane_mbps:.6f} "
        f"raw_fdx_4lane_per_dir_mbps={metrics.raw_fdx_4lane_per_dir_mbps:.6f} "
        f"max_fragment_no_ack_half_payload_mbps={metrics.max_fragment_no_ack_half_8lane_mbps:.6f} "
        f"max_fragment_no_ack_fdx_payload_mbps={metrics.max_fragment_no_ack_fdx_4lane_mbps:.6f} "
        f"best_packet_ack_half_payload_mbps={metrics.best_packet_ack_half_8lane_mbps:.6f} "
        f"best_packet_ack_fdx_payload_mbps={metrics.best_packet_ack_fdx_4lane_mbps:.6f} "
        f"required_lanes_half_payload32={metrics.max_fragment_no_ack_required_lanes_half_32} "
        f"required_lanes_per_dir_fdx_payload16={metrics.max_fragment_no_ack_required_lanes_per_dir_fdx_16} "
        f"required_raw_per_lane_packet_ack_mbps={metrics.best_packet_ack_required_raw_per_lane_mbps:.6f} "
        f"effective_32_16_possible_with_current_raw=0 rate_claim_must_be_raw_phy=1 "
        f"markdown={md_path.relative_to(ROOT)} json={json_path.relative_to(ROOT) if json_path.is_relative_to(ROOT) else json_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
