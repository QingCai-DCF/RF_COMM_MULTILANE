from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from model_effective_payload_rate_options import (
    FDX_LANES_PER_DIRECTION,
    HALF_DUPLEX_LANES,
    MAX_PROTOCOL_FRAGMENT_BYTES,
    SYMBOL_TIME_US,
    make_row,
)


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
DATE_TAG = "20260626"

TARGET_MAX_LANES = 8
TARGET_HALF_MBIT = 32.0
TARGET_FDX_PER_DIR_MBIT = 16.0
TARGET_SINGLE_LANE_RAW_MBIT = 4.0
CURRENT_PHYSICAL_RUNTIME_CAP_SECONDS = 600


@dataclass
class CheckItem:
    item_id: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def has_pattern(pattern: str, text: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is not None


def build_checks() -> tuple[list[CheckItem], dict[str, float | int | str]]:
    constraint = find_hard_constraint()
    constraint_text = read_text(constraint)
    raw_per_lane_mbps = 2.0 / SYMBOL_TIME_US
    raw_half_mbps = raw_per_lane_mbps * HALF_DUPLEX_LANES
    raw_fdx_per_dir_mbps = raw_per_lane_mbps * FDX_LANES_PER_DIRECTION

    fragment_options = [16, 32, 64, 128, 247, MAX_PROTOCOL_FRAGMENT_BYTES]
    packet_options = [256, 1024, 4096, 16384]
    rows = [make_row(fragment, packet) for fragment in fragment_options for packet in packet_options if packet >= fragment]
    best_packet_ack = max(rows, key=lambda row: row.half_8lane_packet_ack_mbps)
    best_no_ack = make_row(MAX_PROTOCOL_FRAGMENT_BYTES, 16384)

    constraint_names_target = all(
        [
            has_pattern(r"最多\s*8\s*路", constraint_text),
            has_pattern(r"半双工.*32\s*Mbit/s", constraint_text),
            has_pattern(r"全双工.*16\s*Mbit/s", constraint_text),
            has_pattern(r"单\s*lane.*4\s*Mbps", constraint_text),
        ]
    )
    root_sha_ok = constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256
    raw_matches_target = (
        abs(raw_per_lane_mbps - TARGET_SINGLE_LANE_RAW_MBIT) < 1e-9
        and abs(raw_half_mbps - TARGET_HALF_MBIT) < 1e-9
        and abs(raw_fdx_per_dir_mbps - TARGET_FDX_PER_DIR_MBIT) < 1e-9
    )
    effective_32_16_reachable = (
        best_no_ack.half_8lane_no_ack_mbps >= TARGET_HALF_MBIT
        and best_no_ack.fdx_4lane_no_ack_mbps >= TARGET_FDX_PER_DIR_MBIT
    )
    effective_16_8_reachable = (
        best_packet_ack.half_8lane_packet_ack_mbps >= 16.0
        and best_packet_ack.fdx_4lane_packet_ack_mbps >= 8.0
    )
    two_hour_in_constraint = has_pattern(r"2\s*小时", constraint_text)
    tcp_dhcp_in_constraint = has_pattern(r"TCP", constraint_text) and has_pattern(r"DHCP", constraint_text)
    rotating_in_constraint = has_pattern(r"20\s*cm", constraint_text) and has_pattern(r"600\s*rpm", constraint_text)

    checks = [
        CheckItem(
            "ROOT-CONSTRAINT-SHA",
            "PASS" if root_sha_ok else "FAIL",
            rel(constraint),
            f"sha256={sha256(constraint)}",
        ),
        CheckItem(
            "CONSTRAINT-RATE-WORDING",
            "PASS" if constraint_names_target else "MISSING",
            rel(constraint),
            "Constraint states max 8 lanes, 4 Mbps raw per lane, 32 Mbit/s half-duplex, and 16 Mbit/s per direction full-duplex."
            if constraint_names_target
            else "Could not find the expected rate/lane wording in the hard constraint.",
        ),
        CheckItem(
            "RAW-PHY-CAPACITY",
            "PASS_RAW_TARGET" if raw_matches_target else "FAIL",
            "tools/model_effective_payload_rate_options.py",
            f"raw_per_lane={raw_per_lane_mbps:.6f}, half8={raw_half_mbps:.6f}, fdx4={raw_fdx_per_dir_mbps:.6f} Mbit/s.",
        ),
        CheckItem(
            "FDX-LANE-PARTITION",
            "PASS_RAW_TARGET" if HALF_DUPLEX_LANES == TARGET_MAX_LANES and FDX_LANES_PER_DIRECTION * 2 == TARGET_MAX_LANES else "FAIL",
            "tools/model_effective_payload_rate_options.py",
            f"Full-duplex target is modeled as {FDX_LANES_PER_DIRECTION}+{FDX_LANES_PER_DIRECTION} lanes from {TARGET_MAX_LANES} total lanes.",
        ),
        CheckItem(
            "EFFECTIVE-32-16-REACHABILITY",
            "BOUNDARY_RAW_ONLY" if not effective_32_16_reachable else "PASS_MODEL",
            "reports/effective_payload_rate_options_20260626.md",
            (
                "Current PHY cannot reach exactly 32/16 Mbit/s as effective payload because payload throughput is strictly below raw capacity; "
                f"best current no-ACK upper bound is half={best_no_ack.half_8lane_no_ack_mbps:.6f}, fdx={best_no_ack.fdx_4lane_no_ack_mbps:.6f} Mbit/s."
            )
            if not effective_32_16_reachable
            else "Current model can reach 32/16 Mbit/s effective payload.",
        ),
        CheckItem(
            "EFFECTIVE-16-8-REACHABILITY",
            "PASS_MODEL" if effective_16_8_reachable else "MISSING",
            "reports/effective_payload_rate_options_20260626.md",
            f"Best packet-ACK option is half={best_packet_ack.half_8lane_packet_ack_mbps:.6f}, fdx={best_packet_ack.fdx_4lane_packet_ack_mbps:.6f} Mbit/s.",
        ),
        CheckItem(
            "RUNTIME-RULE",
            "PASS_OPERATIONAL_RULE" if CURRENT_PHYSICAL_RUNTIME_CAP_SECONDS == 600 else "FAIL",
            "conversation runtime rule",
            "Physical TFDU continuous operation is capped at 600 s; continuous targets over 10 minutes are counted as 10 minutes unless the hard constraint is explicitly changed.",
        ),
        CheckItem(
            "TWO-HOUR-ROTATION-TARGET",
            "PRESENT_CONSTRAINT_MODEL_ONLY" if two_hour_in_constraint else "MISSING",
            rel(constraint),
            "Hard constraint still contains 2-hour rotating stability target; current physical runtime cap means physical tests must be segmented/capped.",
        ),
        CheckItem(
            "TCP-DHCP-TARGET",
            "PRESENT_CONSTRAINT" if tcp_dhcp_in_constraint else "MISSING",
            rel(constraint),
            "Hard constraint includes PS-to-PC TCP and DHCP requirements.",
        ),
        CheckItem(
            "ROTATING-SHAFT-TARGET",
            "PRESENT_CONSTRAINT" if rotating_in_constraint else "MISSING",
            rel(constraint),
            "Hard constraint includes 20 cm / 600 rpm rotating shaft requirement.",
        ),
    ]

    metrics: dict[str, float | int | str] = {
        "raw_per_lane_mbps": raw_per_lane_mbps,
        "raw_half_8lane_mbps": raw_half_mbps,
        "raw_fdx_4lane_per_dir_mbps": raw_fdx_per_dir_mbps,
        "best_packet_ack_half_8lane_mbps": best_packet_ack.half_8lane_packet_ack_mbps,
        "best_packet_ack_fdx_4lane_mbps": best_packet_ack.fdx_4lane_packet_ack_mbps,
        "best_no_ack_half_8lane_mbps": best_no_ack.half_8lane_no_ack_mbps,
        "best_no_ack_fdx_4lane_mbps": best_no_ack.fdx_4lane_no_ack_mbps,
        "runtime_cap_seconds": CURRENT_PHYSICAL_RUNTIME_CAP_SECONDS,
        "constraint_sha256": sha256(constraint),
    }
    return checks, metrics


def overall_status(checks: list[CheckItem]) -> str:
    if any(item.status == "FAIL" for item in checks):
        return "FAIL"
    if any(item.status == "MISSING" for item in checks):
        return "INCOMPLETE"
    if any(item.status == "BOUNDARY_RAW_ONLY" for item in checks):
        return "BOUNDARY_RAW_ONLY"
    return "PASS"


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    checks, metrics = build_checks()
    status = overall_status(checks)
    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / f"target_consistency_check_{DATE_TAG}.md"
    json_path = REPORTS / f"target_consistency_check_{DATE_TAG}.json"

    md_rows = [[item.item_id, item.status, item.evidence, item.note] for item in checks]
    metric_rows = [[key, f"{value:.6f}" if isinstance(value, float) else str(value)] for key, value in metrics.items()]
    md = [
        "# RF_COMM Target Consistency Check",
        "",
        f"Generated: {generated}",
        "",
        f"Overall: `{status}`",
        "",
        "This check verifies target wording, lane count, raw PHY capacity, and effective-payload feasibility under the current 64 MHz 4PPM model. It does not program hardware.",
        "",
        "## Metrics",
        "",
        md_table(["metric", "value"], metric_rows),
        "",
        "## Checks",
        "",
        md_table(["id", "status", "evidence", "note"], md_rows),
        "",
        "## Interpretation",
        "",
        "The current design is internally consistent if the final 32/16 Mbit/s target is treated as raw PHY capacity. Under the current PHY and frame overhead, the same numbers are not reachable as effective payload or PC-to-PC throughput.",
        "",
        f"RF_COMM_TARGET_CONSISTENCY_CHECK overall={status}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": status,
        "metrics": metrics,
        "checks": [asdict(item) for item in checks],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"RF_COMM_TARGET_CONSISTENCY_CHECK overall={status}")
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
