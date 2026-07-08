from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

CLK_HZ = 64_000_000.0
CNT_CHIP_MAX = 7
CHIP_CYCLES = CNT_CHIP_MAX + 1
CHIPS_PER_SYMBOL = 4
BITS_PER_SYMBOL = 2
SYMBOL_TIME_US = (CHIPS_PER_SYMBOL * CHIP_CYCLES * 1_000_000.0) / CLK_HZ

CNT_PREAMBLE = 16
PREAMBLE_GAP_SYMS = 1
PHY_CRC_SYMBOLS = 16
EOF_SILENCE_SYMS = 3
FRAME_FIXED_SYMBOLS = CNT_PREAMBLE + PREAMBLE_GAP_SYMS + PHY_CRC_SYMBOLS + EOF_SILENCE_SYMS

DATA_HDR_BYTES = 14
ACK_HDR_BYTES = 12
MAX_PROTOCOL_FRAGMENT_BYTES = 255
HALF_DUPLEX_LANES = 8
FDX_LANES_PER_DIRECTION = 4


@dataclass
class OptionRow:
    fragment_bytes: int
    packet_bytes: int
    fragments_per_packet: int
    ack_bitmap_bytes: int
    data_airtime_us: float
    ack_airtime_us: float
    per_lane_no_ack_mbps: float
    half_8lane_no_ack_mbps: float
    fdx_4lane_no_ack_mbps: float
    per_lane_packet_ack_mbps: float
    half_8lane_packet_ack_mbps: float
    fdx_4lane_packet_ack_mbps: float
    meets_16_8_packet_ack: bool
    meets_32_16_packet_ack: bool


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def frame_airtime_us(frame_bytes: int) -> float:
    symbols = FRAME_FIXED_SYMBOLS + frame_bytes * 4
    return symbols * SYMBOL_TIME_US


def make_row(fragment_bytes: int, packet_bytes: int) -> OptionRow:
    if fragment_bytes < 1 or fragment_bytes > MAX_PROTOCOL_FRAGMENT_BYTES:
        raise ValueError(f"fragment_bytes must be 1..{MAX_PROTOCOL_FRAGMENT_BYTES}: {fragment_bytes}")
    fragments = ceil(packet_bytes / fragment_bytes)
    ack_bitmap = ceil(fragments / 8)
    data_airtime = frame_airtime_us(DATA_HDR_BYTES + fragment_bytes)
    ack_airtime = frame_airtime_us(ACK_HDR_BYTES + ack_bitmap)
    per_lane_no_ack = (fragment_bytes * 8.0) / data_airtime
    packet_time = fragments * data_airtime + ack_airtime
    per_lane_packet_ack = (packet_bytes * 8.0) / packet_time
    half_packet = per_lane_packet_ack * HALF_DUPLEX_LANES
    fdx_packet = per_lane_packet_ack * FDX_LANES_PER_DIRECTION
    return OptionRow(
        fragment_bytes=fragment_bytes,
        packet_bytes=packet_bytes,
        fragments_per_packet=fragments,
        ack_bitmap_bytes=ack_bitmap,
        data_airtime_us=data_airtime,
        ack_airtime_us=ack_airtime,
        per_lane_no_ack_mbps=per_lane_no_ack,
        half_8lane_no_ack_mbps=per_lane_no_ack * HALF_DUPLEX_LANES,
        fdx_4lane_no_ack_mbps=per_lane_no_ack * FDX_LANES_PER_DIRECTION,
        per_lane_packet_ack_mbps=per_lane_packet_ack,
        half_8lane_packet_ack_mbps=half_packet,
        fdx_4lane_packet_ack_mbps=fdx_packet,
        meets_16_8_packet_ack=(half_packet >= 16.0 and fdx_packet >= 8.0),
        meets_32_16_packet_ack=(half_packet >= 32.0 and fdx_packet >= 16.0),
    )


def fmt(value: float) -> str:
    return f"{value:.6f}"


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now().strftime("%Y%m%d")
    csv_path = REPORTS / f"effective_payload_rate_options_{date_tag}.csv"
    md_path = REPORTS / f"effective_payload_rate_options_{date_tag}.md"
    constraint = find_constraint()
    constraint_hash = sha256(constraint) if constraint else "MISSING"

    fragments = [16, 32, 64, 128, 247, 255]
    packet_sizes = [256, 1024, 4096, 16384]
    rows = [make_row(fragment, packet) for fragment in fragments for packet in packet_sizes if packet >= fragment]
    best_ack = max(rows, key=lambda row: row.half_8lane_packet_ack_mbps)
    best_no_ack_255 = make_row(255, 16384)
    rows_16_8 = [row for row in rows if row.meets_16_8_packet_ack]
    rows_32_16 = [row for row in rows if row.meets_32_16_packet_ack]

    fieldnames = [
        "fragment_bytes",
        "packet_bytes",
        "fragments_per_packet",
        "ack_bitmap_bytes",
        "data_airtime_us",
        "ack_airtime_us",
        "per_lane_no_ack_mbps",
        "half_8lane_no_ack_mbps",
        "fdx_4lane_no_ack_mbps",
        "per_lane_packet_ack_mbps",
        "half_8lane_packet_ack_mbps",
        "fdx_4lane_packet_ack_mbps",
        "meets_16_8_packet_ack",
        "meets_32_16_packet_ack",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "fragment_bytes": row.fragment_bytes,
                    "packet_bytes": row.packet_bytes,
                    "fragments_per_packet": row.fragments_per_packet,
                    "ack_bitmap_bytes": row.ack_bitmap_bytes,
                    "data_airtime_us": fmt(row.data_airtime_us),
                    "ack_airtime_us": fmt(row.ack_airtime_us),
                    "per_lane_no_ack_mbps": fmt(row.per_lane_no_ack_mbps),
                    "half_8lane_no_ack_mbps": fmt(row.half_8lane_no_ack_mbps),
                    "fdx_4lane_no_ack_mbps": fmt(row.fdx_4lane_no_ack_mbps),
                    "per_lane_packet_ack_mbps": fmt(row.per_lane_packet_ack_mbps),
                    "half_8lane_packet_ack_mbps": fmt(row.half_8lane_packet_ack_mbps),
                    "fdx_4lane_packet_ack_mbps": fmt(row.fdx_4lane_packet_ack_mbps),
                    "meets_16_8_packet_ack": int(row.meets_16_8_packet_ack),
                    "meets_32_16_packet_ack": int(row.meets_32_16_packet_ack),
                }
            )

    md_lines = [
        "# Effective Payload Rate Options",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "This is a deterministic budget model, not hardware evidence. It uses the current 64 MHz 4PPM PHY timing and the current DATA/ACK header sizes.",
        "",
        f"- Constraint SHA256: `{constraint_hash}`",
        f"- DATA header bytes: `{DATA_HDR_BYTES}`",
        f"- ACK header bytes: `{ACK_HDR_BYTES}`",
        f"- Max protocol fragment field: `{MAX_PROTOCOL_FRAGMENT_BYTES}` bytes",
        f"- Symbol time: `{SYMBOL_TIME_US:.3f} us`",
        f"- Fixed symbols per frame: `{FRAME_FIXED_SYMBOLS}`",
        f"- CSV: `{csv_path.relative_to(ROOT)}`",
        "",
        "## Key Findings",
        "",
        f"- Best packet-ACK option in this sweep: fragment `{best_ack.fragment_bytes}` bytes, packet `{best_ack.packet_bytes}` bytes, half-duplex 8-lane payload `{best_ack.half_8lane_packet_ack_mbps:.6f} Mbit/s`, full-duplex 4+4 payload `{best_ack.fdx_4lane_packet_ack_mbps:.6f} Mbit/s`.",
        f"- Even near the current protocol fragment maximum, the raw-approaching no-ACK upper bound remains below 32/16 Mbit/s payload: half `{best_no_ack_255.half_8lane_no_ack_mbps:.6f}`, fdx `{best_no_ack_255.fdx_4lane_no_ack_mbps:.6f}`.",
        f"- Packet-ACK options meeting the earlier 16/8 Mbit/s effective-payload threshold: `{len(rows_16_8)}` of `{len(rows)}`.",
        f"- Packet-ACK options meeting 32/16 Mbit/s effective-payload threshold: `{len(rows_32_16)}` of `{len(rows)}`.",
        "",
        "Interpretation: 32/16 Mbit/s is currently defensible as raw PHY capacity only. If it is required as effective payload or PC-to-PC throughput, the protocol needs a larger physical rate, more lanes, reduced overhead, or a different frame/ACK strategy.",
        "",
        "## Selected Rows",
        "",
        "| Fragment | Packet | Frags | Half 8-lane packet-ACK Mbit/s | FDX 4+4 packet-ACK Mbit/s | Meets 16/8 | Meets 32/16 |",
        "| ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        if row.fragment_bytes in {16, 32, 64, 128, 255} and row.packet_bytes in {256, 4096, 16384}:
            md_lines.append(
                f"| {row.fragment_bytes} | {row.packet_bytes} | {row.fragments_per_packet} | "
                f"{row.half_8lane_packet_ack_mbps:.6f} | {row.fdx_4lane_packet_ack_mbps:.6f} | "
                f"{'yes' if row.meets_16_8_packet_ack else 'no'} | {'yes' if row.meets_32_16_packet_ack else 'no'} |"
            )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"WROTE_CSV={csv_path}")
    print(f"WROTE_MARKDOWN={md_path}")
    print(
        "EFFECTIVE_PAYLOAD_RATE_OPTIONS "
        f"best_half8_packet_ack={best_ack.half_8lane_packet_ack_mbps:.6f} "
        f"best_fdx4_packet_ack={best_ack.fdx_4lane_packet_ack_mbps:.6f} "
        f"meets_16_8_count={len(rows_16_8)} "
        f"meets_32_16_count={len(rows_32_16)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
