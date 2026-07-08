from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
OPEN_IDS = ("N03", "N04", "S05", "A01", "A02")


@dataclass
class EnvelopeRow:
    item: str
    category: str
    status: str
    expected: str
    actual: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def add(rows: list[EnvelopeRow], item: str, category: str, ok: bool, expected: str, actual: str, evidence: Path, note: str, pass_status: str = "PASS") -> None:
    rows.append(
        EnvelopeRow(
            item=item,
            category=category,
            status=pass_status if ok else "FAIL",
            expected=expected,
            actual=actual,
            evidence=rel(evidence),
            note=note,
        )
    )


def metric_value(rows: Iterable[dict[str, str]], metric: str) -> str:
    for row in rows:
        if row.get("metric") == metric:
            return row.get("value", "")
    return ""


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def mask(value: Any) -> str:
    try:
        return f"0x{int(value):02x}"
    except (TypeError, ValueError):
        return str(value)


def blocking_matrix_ids(matrix_rows: list[dict[str, str]]) -> tuple[str, ...]:
    blocking = {"DEFERRED_NO_ETHERNET", "MISSING_HARDWARE", "PARTIAL_G1_ONLY"}
    return tuple(row.get("item_id", "") for row in matrix_rows if row.get("status") in blocking)


def md_table(rows: list[EnvelopeRow]) -> str:
    lines = [
        "| item | category | status | expected | actual | evidence | note |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        cells = [
            row.item,
            row.category,
            row.status,
            row.expected,
            row.actual,
            row.evidence,
            row.note,
        ]
        lines.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in cells) + " |")
    return "\n".join(lines)


def build_rows() -> tuple[list[EnvelopeRow], dict[str, str]]:
    constraint = find_hard_constraint()
    twin_md = REPORTS / "full_system_capped_digital_twin_current.md"
    twin_json = REPORTS / "full_system_capped_digital_twin_current.json"
    twin_csv = REPORTS / "full_system_capped_digital_twin_current.csv"
    matrix_csv = REPORTS / "target_acceptance_matrix_current.csv"
    readiness_md = REPORTS / "remaining_acceptance_readiness_current.md"
    readiness_csv = REPORTS / "remaining_acceptance_readiness_current.csv"
    no_eth_boundary = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    rotating_offline = REPORTS / "rotating_autoroute_offline_evidence_current.md"
    rotating_dynamic = REPORTS / "rotating_dynamic_permutation_autoroute_current.md"
    rotating_dynamic_json = REPORTS / "rotating_dynamic_permutation_autoroute_current.json"
    rotating_dynamic_csv = REPORTS / "rotating_dynamic_permutation_autoroute_current.csv"

    twin = read_json(twin_json)
    stats = twin.get("stats") if isinstance(twin.get("stats"), dict) else {}
    endpoint_a = twin.get("endpoint_a") if isinstance(twin.get("endpoint_a"), dict) else {}
    endpoint_b = twin.get("endpoint_b") if isinstance(twin.get("endpoint_b"), dict) else {}
    twin_text = read_text(twin_md)
    twin_rows = read_csv(twin_csv)
    matrix_rows = read_csv(matrix_csv)
    readiness_text = read_text(readiness_md)
    readiness_rows = read_csv(readiness_csv)
    no_eth_text = read_text(no_eth_boundary)
    rotating_text = read_text(rotating_offline)
    rotating_dynamic_text = read_text(rotating_dynamic)
    rotating_dynamic_payload = read_json(rotating_dynamic_json)
    rotating_dynamic_stats = (
        rotating_dynamic_payload.get("stats")
        if isinstance(rotating_dynamic_payload.get("stats"), dict)
        else {}
    )
    rotating_dynamic_rows = read_csv(rotating_dynamic_csv)

    rows: list[EnvelopeRow] = []

    add(
        rows,
        "hard_constraint_unchanged",
        "constraint",
        constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256,
        EXPECTED_CONSTRAINT_SHA256,
        sha256(constraint),
        constraint or ROOT,
        "Envelope check remains tied to the hard project target.",
    )
    add(
        rows,
        "digital_twin_source_pass",
        "source",
        "- Overall: `PASS`" in twin_text and metric_value(twin_rows, "failures") == "",
        "full-system digital twin PASS with no failures",
        f"md_pass={int('- Overall: `PASS`' in twin_text)} failures={metric_value(twin_rows, 'failures')}",
        twin_md,
        "Uses the current deterministic full-system capped digital twin evidence.",
    )
    add(
        rows,
        "no_hardware_side_effects",
        "safety",
        all(marker in twin_text for marker in ["No hardware programming: `1`", "No UART write: `1`", "No TFDU drive: `1`"]),
        "no FPGA programming, UART write, or TFDU drive",
        "present" if "No hardware programming: `1`" in twin_text else "missing",
        twin_md,
        "This check is report-only and does not touch hardware.",
    )
    add(
        rows,
        "runtime_cap_applied",
        "stability",
        as_int(twin.get("original_target_seconds")) == 7200
        and as_int(twin.get("runtime_cap_seconds")) == 600
        and as_int(twin.get("seconds")) == 600,
        "original=7200 cap=600 effective=600",
        f"original={twin.get('original_target_seconds')} cap={twin.get('runtime_cap_seconds')} effective={twin.get('seconds')}",
        twin_json,
        "The model follows the current rule that continuous tests longer than 10 minutes are counted as 10 minutes.",
    )
    add(
        rows,
        "rotating_geometry_and_duration",
        "rotation",
        as_int(twin.get("rpm")) == 600
        and as_int(twin.get("shaft_diameter_mm")) == 200
        and as_int(twin.get("rotations")) == 6000
        and as_int(twin.get("sectors")) == 48000,
        "200 mm / 600 rpm / 600 s / 6000 rotations / 48000 sectors",
        f"{twin.get('shaft_diameter_mm')}mm {twin.get('rpm')}rpm rotations={twin.get('rotations')} sectors={twin.get('sectors')}",
        twin_json,
        "Covers the rotating-shaft target metadata under the active 600 s cap.",
    )
    add(
        rows,
        "raw_rate_target_envelope",
        "rate",
        as_int(twin.get("lane_count")) == 8
        and abs(as_float(twin.get("raw_half_8lane_mbps")) - 32.0) < 1e-9
        and abs(as_float(twin.get("raw_fdx_4lane_per_dir_mbps")) - 16.0) < 1e-9
        and twin.get("rate_claim") == "raw_phy_only",
        "8 lanes, raw half=32 Mbit/s, raw 4+4 full-duplex=16 Mbit/s per direction, raw-only claim",
        f"lanes={twin.get('lane_count')} raw_half={twin.get('raw_half_8lane_mbps')} raw_fdx={twin.get('raw_fdx_4lane_per_dir_mbps')} claim={twin.get('rate_claim')}",
        twin_json,
        "Prevents the raw 32/16 Mbit/s target from being overclaimed as effective payload throughput.",
    )
    add(
        rows,
        "half_duplex_8lane_coverage",
        "lane_coverage",
        as_int(stats.get("half_duplex_slots")) > 0
        and stats.get("half_tx_lane_coverage") == 0xFF
        and stats.get("half_rx_lane_coverage") == 0xFF
        and stats.get("tx_lane_coverage") == 0xFF
        and stats.get("rx_lane_coverage") == 0xFF,
        "half-duplex slots > 0 and TX/RX lane coverage 0xff",
        f"slots={stats.get('half_duplex_slots')} half_tx={mask(stats.get('half_tx_lane_coverage'))} half_rx={mask(stats.get('half_rx_lane_coverage'))} tx={mask(stats.get('tx_lane_coverage'))} rx={mask(stats.get('rx_lane_coverage'))}",
        twin_json,
        "Checks the 8-lane half-duplex lane envelope in the digital twin.",
    )
    add(
        rows,
        "full_duplex_4plus4_partition",
        "lane_coverage",
        as_int(stats.get("full_duplex_slots")) > 0
        and stats.get("fdx_a_to_b_tx_lane_coverage") == 0x0F
        and stats.get("fdx_b_to_a_tx_lane_coverage") == 0xF0
        and stats.get("fdx_a_to_b_rx_lane_coverage") == 0x0F
        and stats.get("fdx_b_to_a_rx_lane_coverage") == 0xF0,
        "full-duplex slots > 0, A->B TX/RX 0x0f, B->A TX/RX 0xf0",
        f"slots={stats.get('full_duplex_slots')} a2b_tx={mask(stats.get('fdx_a_to_b_tx_lane_coverage'))} b2a_tx={mask(stats.get('fdx_b_to_a_tx_lane_coverage'))} a2b_rx={mask(stats.get('fdx_a_to_b_rx_lane_coverage'))} b2a_rx={mask(stats.get('fdx_b_to_a_rx_lane_coverage'))}",
        twin_json,
        "Checks the final independent 4+4 full-duplex lane partition envelope.",
    )
    add(
        rows,
        "rotating_autoroute_search",
        "autoroute",
        stats.get("route_map_coverage") == 0xFF
        and stats.get("source_lane_coverage") == 0xFF
        and as_int(stats.get("failed_route_events")) > 0
        and as_int(stats.get("route_probe_events")) > 0
        and as_int(stats.get("max_search_attempts")) > 1
        and as_int(stats.get("max_route_probe_observed")) > 0
        and as_int(stats.get("unrecovered_errors")) == 0
        and as_int(stats.get("deadlock_events")) == 0,
        "all route/source lanes covered, route probing and recovery search exercised, no unrecovered error/deadlock",
        f"route={mask(stats.get('route_map_coverage'))} source={mask(stats.get('source_lane_coverage'))} failed_route={stats.get('failed_route_events')} route_probe={stats.get('route_probe_events')} max_probe={stats.get('max_route_probe_observed')} max_search={stats.get('max_search_attempts')} unrecovered={stats.get('unrecovered_errors')} deadlock={stats.get('deadlock_events')}",
        twin_json,
        "Exercises automatic route finding while TX/RX correspondence changes.",
    )
    add(
        rows,
        "rotating_dynamic_permutation_autoroute",
        "autoroute",
        "RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall=PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE"
        in rotating_dynamic_text
        and as_int(rotating_dynamic_payload.get("seconds")) == 600
        and as_int(rotating_dynamic_payload.get("rpm")) == 600
        and as_int(rotating_dynamic_payload.get("shaft_diameter_mm")) == 200
        and metric_value(rotating_dynamic_rows, "half_pair_coverage_count") == "64"
        and metric_value(rotating_dynamic_rows, "fdx_a_to_b_pair_coverage_count") == "16"
        and metric_value(rotating_dynamic_rows, "fdx_b_to_a_pair_coverage_count") == "16"
        and as_int(rotating_dynamic_stats.get("stale_cache_events")) > 0
        and as_int(rotating_dynamic_stats.get("route_relearn_events")) > 0
        and as_int(rotating_dynamic_stats.get("blocked_probe_events")) > 0
        and as_int(rotating_dynamic_stats.get("max_probe_sweep")) > 1
        and as_int(rotating_dynamic_stats.get("unrecovered_errors")) == 0
        and as_int(rotating_dynamic_stats.get("deadlock_events")) == 0,
        "dynamic TX/RX permutation model covers half 64/64 pairs, FDX 16/16 pairs per direction, stale-cache relearn, blocked probes, unrecovered=0",
        f"half_pairs={metric_value(rotating_dynamic_rows, 'half_pair_coverage_count')}/64 "
        f"a2b_pairs={metric_value(rotating_dynamic_rows, 'fdx_a_to_b_pair_coverage_count')}/16 "
        f"b2a_pairs={metric_value(rotating_dynamic_rows, 'fdx_b_to_a_pair_coverage_count')}/16 "
        f"stale={rotating_dynamic_stats.get('stale_cache_events')} "
        f"relearn={rotating_dynamic_stats.get('route_relearn_events')} "
        f"blocked={rotating_dynamic_stats.get('blocked_probe_events')} "
        f"unrecovered={rotating_dynamic_stats.get('unrecovered_errors')}",
        rotating_dynamic,
        "Adds a dedicated offline model for the user requirement that transmitter/receiver correspondence changes during rotation and must be rediscovered automatically.",
    )
    add(
        rows,
        "link_fault_recovery_paths",
        "robustness",
        as_int(stats.get("short_blockage_events")) > 0
        and as_int(stats.get("crc_error_events")) > 0
        and as_int(stats.get("fragment_ack_loss_events")) > 0
        and as_int(stats.get("final_ack_loss_events")) > 0
        and as_int(stats.get("unrecovered_errors")) == 0,
        "short blockage, CRC, fragment ACK loss, final ACK loss exercised; unrecovered=0",
        f"blockage={stats.get('short_blockage_events')} crc={stats.get('crc_error_events')} frag_ack={stats.get('fragment_ack_loss_events')} final_ack={stats.get('final_ack_loss_events')} unrecovered={stats.get('unrecovered_errors')}",
        twin_json,
        "Covers the offline recovery envelope for optical impairment and protocol retry paths.",
    )
    add(
        rows,
        "network_recovery_paths",
        "network",
        as_int(endpoint_a.get("tcp_reconnect_events")) > 0
        and as_int(endpoint_b.get("tcp_reconnect_events")) > 0
        and as_int(endpoint_a.get("dhcp_static_fallback_events")) > 0
        and as_int(endpoint_b.get("dhcp_static_fallback_events")) > 0
        and as_int(endpoint_a.get("queued_rx_max")) > 0
        and as_int(endpoint_b.get("queued_rx_max")) > 0
        and as_int(stats.get("queued_rx_delivered")) > 0,
        "both endpoints exercise TCP reconnect, DHCP/static fallback, and queued RX delivery",
        f"a_tcp={endpoint_a.get('tcp_reconnect_events')} b_tcp={endpoint_b.get('tcp_reconnect_events')} a_dhcp={endpoint_a.get('dhcp_static_fallback_events')} b_dhcp={endpoint_b.get('dhcp_static_fallback_events')} queued={stats.get('queued_rx_delivered')}",
        twin_json,
        "Keeps PS/PC TCP/DHCP behavior testable offline while the board has no Ethernet cable.",
    )
    add(
        rows,
        "bidirectional_packet_flow",
        "traffic",
        as_int(stats.get("transfers")) > 0
        and as_int(stats.get("fragments")) > 0
        and as_int(stats.get("payload_bytes")) > 0
        and as_int(endpoint_a.get("tx_packets")) > 0
        and as_int(endpoint_b.get("tx_packets")) > 0
        and as_int(endpoint_a.get("rx_packets")) > 0
        and as_int(endpoint_b.get("rx_packets")) > 0,
        "both endpoints TX/RX and payload/fragments are nonzero",
        f"transfers={stats.get('transfers')} fragments={stats.get('fragments')} payload={stats.get('payload_bytes')} a_tx={endpoint_a.get('tx_packets')} b_tx={endpoint_b.get('tx_packets')} a_rx={endpoint_a.get('rx_packets')} b_rx={endpoint_b.get('rx_packets')}",
        twin_json,
        "Confirms the offline twin is not only a static lane arithmetic check.",
    )
    open_ids = blocking_matrix_ids(matrix_rows)
    readiness_blockers = {row.get("item_id", ""): row.get("status", "") for row in readiness_rows}
    add(
        rows,
        "real_acceptance_boundary",
        "boundary",
        open_ids == OPEN_IDS
        and all(readiness_blockers.get(item_id) == "BLOCKED_EXTERNAL_PRECONDITIONS" for item_id in OPEN_IDS)
        and "REAL_ACCEPTANCE_EXECUTED=0" in readiness_text
        and "REAL_ROTATING_SHAFT_ACCEPTANCE=0" in rotating_text,
        "N03/N04/S05/A01/A02 remain blocked; real acceptance executed=0",
        f"open_ids={','.join(open_ids)} readiness={';'.join(f'{k}:{v}' for k, v in sorted(readiness_blockers.items()))}",
        matrix_csv,
        "The offline envelope improves model evidence without converting any real hardware item to PASS.",
        pass_status="PASS_BOUNDARY_NOT_HARDWARE",
    )
    add(
        rows,
        "current_no_ethernet_boundary",
        "boundary",
        "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1" in readiness_text
        and "NO_REAL_BOARD_TCP_DHCP=1" in no_eth_text
        and "NO_REAL_ETHERNET_LINK_REQUIRED=1" in no_eth_text,
        "current no-Ethernet cable condition is explicit and no real board TCP/DHCP is claimed",
        "present" if "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1" in readiness_text else "missing",
        readiness_md,
        "Real TCP/DHCP and two-AX7010 network acceptance remain unavailable until Ethernet exists.",
        pass_status="PASS_BOUNDARY_NO_ETHERNET",
    )

    meta = {
        "constraint": rel(constraint),
        "constraint_sha256": sha256(constraint),
        "full_system_twin_md": rel(twin_md),
        "full_system_twin_json": rel(twin_json),
        "full_system_twin_csv": rel(twin_csv),
        "target_matrix_csv": rel(matrix_csv),
        "remaining_acceptance_readiness_md": rel(readiness_md),
        "remaining_acceptance_readiness_csv": rel(readiness_csv),
        "no_ethernet_network_boundary": rel(no_eth_boundary),
        "rotating_autoroute_offline": rel(rotating_offline),
        "rotating_dynamic_permutation_autoroute_md": rel(rotating_dynamic),
        "rotating_dynamic_permutation_autoroute_json": rel(rotating_dynamic_json),
        "rotating_dynamic_permutation_autoroute_csv": rel(rotating_dynamic_csv),
    }
    return rows, meta


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows, meta = build_rows()
    failures = [row for row in rows if row.status == "FAIL"]
    overall = "PASS_OFFLINE_TARGET_ENVELOPE_NOT_HARDWARE" if not failures else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "full_system_offline_target_envelope_current.md"
    json_path = REPORTS / "full_system_offline_target_envelope_current.json"
    csv_path = REPORTS / "full_system_offline_target_envelope_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# Full-System Offline Target Envelope",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Checks: `{len(rows)}`",
        f"- Failures: `{len(failures)}`",
        "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Real board TCP/DHCP acceptance: `0`",
        "- Real two-AX7010 traffic acceptance: `0`",
        "- Real rotating shaft acceptance: `0`",
        "- Real 8-lane TFDU hardware acceptance: `0`",
        "",
        "This report checks the current full-system digital twin against the project target envelope. It is deliberately not real hardware acceptance.",
        "",
        "## Checks",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall={overall} checks={len(rows)} failures={len(failures)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "REAL_BOARD_TCP_DHCP_ACCEPTANCE=0",
        "REAL_TWO_AX7010_TRAFFIC_ACCEPTANCE=0",
        "REAL_ROTATING_SHAFT_ACCEPTANCE=0",
        "REAL_8LANE_TFDU_ACCEPTANCE=0",
        "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1",
        "RAW_RATE_CLAIM_ONLY=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "checks": len(rows),
        "failures": len(failures),
        "meta": meta,
        "items": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_FULL_SYSTEM_OFFLINE_TARGET_ENVELOPE overall={overall} checks={len(rows)} failures={len(failures)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("REAL_BOARD_TCP_DHCP_ACCEPTANCE=0")
    print("REAL_TWO_AX7010_TRAFFIC_ACCEPTANCE=0")
    print("REAL_ROTATING_SHAFT_ACCEPTANCE=0")
    print("REAL_8LANE_TFDU_ACCEPTANCE=0")
    print("CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1")
    print("RAW_RATE_CLAIM_ONLY=1")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
