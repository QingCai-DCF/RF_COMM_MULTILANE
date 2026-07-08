#!/usr/bin/env python3
"""Deterministic full-system capped-soak model for RF_COMM.

This model combines the current system targets that can be checked without
hardware: two AX7010-style endpoints, PC/PS control, 8-lane rotating autoroute,
short optical impairments, TCP reconnects, DHCP fallback, and the active
10-minute continuous-test cap. It is not physical hardware evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


LANE_COUNT = 8
TARGET_RPM = 600
REV_PER_SECOND = TARGET_RPM // 60
SHAFT_DIAMETER_MM = 200
ORIGINAL_TARGET_SECONDS = 2 * 60 * 60
RUNTIME_CAP_SECONDS = 10 * 60
EFFECTIVE_SECONDS = min(ORIGINAL_TARGET_SECONDS, RUNTIME_CAP_SECONDS)
ROTATIONS = REV_PER_SECOND * EFFECTIVE_SECONDS
SECTORS_PER_REV = LANE_COUNT
SECTORS = ROTATIONS * SECTORS_PER_REV
MAX_PACKET_BYTES = 2040
FRAGMENT_BYTES = 255
MAX_FRAGS = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) // FRAGMENT_BYTES
MAX_RETRY = LANE_COUNT * MAX_FRAGS
RAW_MBIT_PER_LANE = 4.0
RAW_HALF_8LANE_MBPS = RAW_MBIT_PER_LANE * LANE_COUNT
RAW_FDX_4LANE_PER_DIR_MBPS = RAW_MBIT_PER_LANE * (LANE_COUNT // 2)
FDX_A_TO_B_MASK = 0x0F
FDX_B_TO_A_MASK = 0xF0


@dataclass
class EndpointState:
    name: str
    tcp_connected: bool = True
    dhcp_ok: bool = True
    reconnect_countdown: int = 0
    queued_rx: int = 0
    queued_rx_max: int = 0
    tx_packets: int = 0
    rx_packets: int = 0
    status_queries: int = 0
    config_updates: int = 0
    tcp_disconnect_events: int = 0
    tcp_reconnect_events: int = 0
    dhcp_renew_events: int = 0
    dhcp_static_fallback_events: int = 0


@dataclass
class ModelStats:
    sectors: int = 0
    rotations: int = 0
    transfers: int = 0
    fragments: int = 0
    payload_bytes: int = 0
    failed_route_events: int = 0
    total_failed_attempts: int = 0
    max_search_attempts: int = 0
    max_retry_observed: int = 0
    short_blockage_events: int = 0
    crc_error_events: int = 0
    fragment_ack_loss_events: int = 0
    final_ack_loss_events: int = 0
    queued_rx_delivered: int = 0
    deadlock_events: int = 0
    unrecovered_errors: int = 0
    half_duplex_slots: int = 0
    full_duplex_slots: int = 0
    tx_lane_coverage: int = 0
    rx_lane_coverage: int = 0
    route_map_coverage: int = 0
    source_lane_coverage: int = 0
    half_tx_lane_coverage: int = 0
    half_rx_lane_coverage: int = 0
    fdx_a_to_b_tx_lane_coverage: int = 0
    fdx_a_to_b_rx_lane_coverage: int = 0
    fdx_b_to_a_tx_lane_coverage: int = 0
    fdx_b_to_a_rx_lane_coverage: int = 0
    route_probe_events: int = 0
    max_route_probe_observed: int = 0


def bit(mask: int, lane: int) -> bool:
    return ((mask >> lane) & 1) != 0


def popcount(mask: int) -> int:
    return int(mask).bit_count()


def rotating_route_map(sector: int, direction: int) -> int:
    return (sector + direction * 3 + sector // 19 + sector // 997) % LANE_COUNT


def rotating_source_lane(sector: int, direction: int, frag: int) -> int:
    rev_idx = sector // SECTORS_PER_REV
    sector_in_rev = sector % SECTORS_PER_REV
    jitter = sector // 257 + rev_idx // 31 + frag * 3 + direction * 5
    return (sector_in_rev + rev_idx + jitter) % LANE_COUNT


def reachable_source_lane(base_lane: int, route: int, tx_mask: int, rx_mask: int) -> int | None:
    lanes = [
        lane for lane in range(LANE_COUNT)
        if bit(tx_mask, lane) and bit(rx_mask, (lane + route) % LANE_COUNT)
    ]
    if not lanes:
        return None
    return lanes[base_lane % len(lanes)]


def optical_blockage_attempts(sector: int, direction: int, frag: int) -> int:
    if ((sector + direction * 37 + frag * 11) % 97) == 13:
        return 1 + ((sector // 997 + direction + frag) % 3)
    return 0


def packet_payload_len(sector: int, direction: int) -> int:
    payload_options = (256, 512, 1024, 1536, 2040)
    return payload_options[(sector + direction * 2 + sector // 113) % len(payload_options)]


class FullSystemModel:
    def __init__(self) -> None:
        self.stats = ModelStats(sectors=SECTORS, rotations=ROTATIONS)
        self.a = EndpointState("ax7010_a")
        self.b = EndpointState("ax7010_b")
        self.tx_rr = [0, LANE_COUNT // 2]

    def update_network(self, sector: int) -> None:
        for idx, endpoint in enumerate((self.a, self.b)):
            if sector % 2000 == 0:
                endpoint.dhcp_renew_events += 1
            if sector != 0 and ((sector + idx * 311) % 4096) == 0:
                endpoint.dhcp_ok = False
                endpoint.dhcp_static_fallback_events += 1
            if not endpoint.dhcp_ok and ((sector + idx) % 17) == 0:
                endpoint.dhcp_ok = True

            if sector != 0 and ((sector + idx * 503) % 3071) == 0 and endpoint.tcp_connected:
                endpoint.tcp_connected = False
                endpoint.reconnect_countdown = 3 + idx
                endpoint.tcp_disconnect_events += 1
            if not endpoint.tcp_connected:
                endpoint.reconnect_countdown -= 1
                if endpoint.reconnect_countdown <= 0:
                    endpoint.tcp_connected = True
                    endpoint.tcp_reconnect_events += 1
                    self.stats.queued_rx_delivered += endpoint.queued_rx
                    endpoint.rx_packets += endpoint.queued_rx
                    endpoint.queued_rx = 0

            if sector % 125 == 0:
                endpoint.status_queries += 1
            if sector % 2048 == 0:
                endpoint.config_updates += 1

    def deliver_to_pc(self, endpoint: EndpointState) -> None:
        if endpoint.tcp_connected:
            endpoint.rx_packets += 1
        else:
            endpoint.queued_rx += 1
            endpoint.queued_rx_max = max(endpoint.queued_rx_max, endpoint.queued_rx)

    def search_fragment(self, sector: int, direction: int, frag: int, tx_mask: int, rx_mask: int, fdx: bool) -> None:
        base_route = rotating_route_map(sector, direction)
        base_good_lane = rotating_source_lane(sector, direction, frag)
        route = base_route
        route_probe = 0
        reachable_lane = None
        for candidate_probe in range(LANE_COUNT):
            candidate_route = (base_route + candidate_probe) % LANE_COUNT
            candidate_lane = reachable_source_lane(base_good_lane, candidate_route, tx_mask, rx_mask)
            if candidate_lane is not None:
                route = candidate_route
                route_probe = candidate_probe
                reachable_lane = candidate_lane
                break
        if reachable_lane is None:
            self.stats.unrecovered_errors += 1
            return
        good_lane = reachable_lane
        rx_lane = (good_lane + route) % LANE_COUNT
        self.stats.route_map_coverage |= 1 << route
        self.stats.source_lane_coverage |= 1 << good_lane
        if route_probe:
            self.stats.route_probe_events += 1
            self.stats.max_route_probe_observed = max(self.stats.max_route_probe_observed, route_probe)

        attempts = 0
        blocked = optical_blockage_attempts(sector, direction, frag)
        if blocked:
            self.stats.short_blockage_events += 1
        for i in range(blocked):
            lane = (self.tx_rr[direction] + i) % LANE_COUNT
            if bit(tx_mask, lane):
                self.stats.tx_lane_coverage |= 1 << lane
                self.stats.total_failed_attempts += 1
                attempts += 1

        found = False
        for i in range(MAX_RETRY + 1):
            lane = (self.tx_rr[direction] + blocked + i) % LANE_COUNT
            if not bit(tx_mask, lane):
                continue
            attempts += 1
            self.stats.tx_lane_coverage |= 1 << lane
            mapped_rx = (lane + route) % LANE_COUNT
            if lane == good_lane and bit(rx_mask, mapped_rx):
                rx_lane = mapped_rx
                found = True
                break
            self.stats.total_failed_attempts += 1

        if not found or attempts > (MAX_RETRY + 1):
            self.stats.unrecovered_errors += 1
            return
        if attempts > 1:
            self.stats.failed_route_events += 1
        self.stats.max_search_attempts = max(self.stats.max_search_attempts, attempts)
        self.stats.max_retry_observed = max(self.stats.max_retry_observed, attempts - 1)
        self.stats.rx_lane_coverage |= 1 << rx_lane
        if fdx:
            if direction == 0:
                self.stats.fdx_a_to_b_tx_lane_coverage |= 1 << good_lane
                self.stats.fdx_a_to_b_rx_lane_coverage |= 1 << rx_lane
            else:
                self.stats.fdx_b_to_a_tx_lane_coverage |= 1 << good_lane
                self.stats.fdx_b_to_a_rx_lane_coverage |= 1 << rx_lane
        else:
            self.stats.half_tx_lane_coverage |= 1 << good_lane
            self.stats.half_rx_lane_coverage |= 1 << rx_lane
        self.tx_rr[direction] = (good_lane + 1) % LANE_COUNT

    def transfer(self, sector: int, direction: int, fdx: bool) -> None:
        src = self.a if direction == 0 else self.b
        dst = self.b if direction == 0 else self.a
        payload_len = packet_payload_len(sector, direction)
        frag_count = (payload_len + FRAGMENT_BYTES - 1) // FRAGMENT_BYTES
        if fdx:
            tx_mask = FDX_A_TO_B_MASK if direction == 0 else FDX_B_TO_A_MASK
            rx_mask = FDX_A_TO_B_MASK if direction == 0 else FDX_B_TO_A_MASK
        else:
            tx_mask = 0xFF
            rx_mask = 0xFF

        src.tx_packets += 1
        self.stats.transfers += 1
        self.stats.fragments += frag_count
        self.stats.payload_bytes += payload_len
        for frag in range(frag_count):
            self.search_fragment(sector, direction, frag, tx_mask, rx_mask, fdx)
            event_id = sector * MAX_FRAGS * 2 + direction * MAX_FRAGS + frag
            if event_id % 997 == 996:
                self.stats.crc_error_events += 1
            if event_id % 4099 == 4098:
                self.stats.fragment_ack_loss_events += 1
        if ((sector * 2 + direction) % 6151) == 6150:
            self.stats.final_ack_loss_events += 1
        self.deliver_to_pc(dst)

    def run(self) -> None:
        for sector in range(SECTORS):
            self.update_network(sector)
            fdx = (sector % 2) == 0
            if fdx:
                self.stats.full_duplex_slots += 1
                self.transfer(sector, 0, fdx=True)
                self.transfer(sector, 1, fdx=True)
            else:
                self.stats.half_duplex_slots += 1
                self.transfer(sector, (sector // 2) & 1, fdx=False)
        for endpoint in (self.a, self.b):
            if endpoint.queued_rx:
                self.stats.queued_rx_delivered += endpoint.queued_rx
                endpoint.rx_packets += endpoint.queued_rx
                endpoint.queued_rx = 0

    def validate(self) -> list[str]:
        failures: list[str] = []
        if self.stats.sectors != 48000 or self.stats.rotations != 6000:
            failures.append("rotating metadata mismatch")
        if self.stats.unrecovered_errors != 0 or self.stats.deadlock_events != 0:
            failures.append("unrecovered error or deadlock")
        for name, mask in (
            ("tx_lane_coverage", self.stats.tx_lane_coverage),
            ("rx_lane_coverage", self.stats.rx_lane_coverage),
            ("route_map_coverage", self.stats.route_map_coverage),
            ("source_lane_coverage", self.stats.source_lane_coverage),
        ):
            if mask != 0xFF:
                failures.append(f"{name}=0x{mask:02x}")
        if self.stats.failed_route_events == 0 or self.stats.short_blockage_events == 0:
            failures.append("autoroute recovery paths not exercised")
        if self.stats.route_probe_events == 0 or self.stats.max_route_probe_observed == 0:
            failures.append("4+4 route probing path not exercised")
        if self.stats.crc_error_events == 0:
            failures.append("crc recovery path not exercised")
        if self.stats.fragment_ack_loss_events == 0 or self.stats.final_ack_loss_events == 0:
            failures.append("ack recovery paths not exercised")
        if self.a.tcp_reconnect_events == 0 or self.b.tcp_reconnect_events == 0:
            failures.append("tcp reconnect path not exercised on both endpoints")
        if self.a.dhcp_static_fallback_events == 0 or self.b.dhcp_static_fallback_events == 0:
            failures.append("dhcp fallback path not exercised on both endpoints")
        if self.a.queued_rx_max == 0 or self.b.queued_rx_max == 0:
            failures.append("queued rx after reconnect not exercised on both endpoints")
        if self.stats.full_duplex_slots == 0 or self.stats.half_duplex_slots == 0:
            failures.append("both half-duplex and full-duplex slots must be covered")
        if popcount(self.stats.tx_lane_coverage) != LANE_COUNT or popcount(self.stats.rx_lane_coverage) != LANE_COUNT:
            failures.append("lane coverage popcount mismatch")
        if self.stats.half_tx_lane_coverage != 0xFF or self.stats.half_rx_lane_coverage != 0xFF:
            failures.append(
                f"half-duplex lane coverage incomplete tx=0x{self.stats.half_tx_lane_coverage:02x} "
                f"rx=0x{self.stats.half_rx_lane_coverage:02x}"
            )
        if self.stats.fdx_a_to_b_tx_lane_coverage != 0x0F:
            failures.append(f"fdx A->B TX coverage=0x{self.stats.fdx_a_to_b_tx_lane_coverage:02x}")
        if self.stats.fdx_b_to_a_tx_lane_coverage != 0xF0:
            failures.append(f"fdx B->A TX coverage=0x{self.stats.fdx_b_to_a_tx_lane_coverage:02x}")
        if self.stats.fdx_a_to_b_rx_lane_coverage != FDX_A_TO_B_MASK or self.stats.fdx_b_to_a_rx_lane_coverage != FDX_B_TO_A_MASK:
            failures.append(
                f"fdx 4+4 RX partition coverage incomplete a_to_b=0x{self.stats.fdx_a_to_b_rx_lane_coverage:02x} "
                f"b_to_a=0x{self.stats.fdx_b_to_a_rx_lane_coverage:02x}"
            )
        return failures

    def summary(self) -> dict[str, object]:
        return {
            "original_target_seconds": ORIGINAL_TARGET_SECONDS,
            "runtime_cap_seconds": RUNTIME_CAP_SECONDS,
            "seconds": EFFECTIVE_SECONDS,
            "rpm": TARGET_RPM,
            "rev_per_s": REV_PER_SECOND,
            "shaft_diameter_mm": SHAFT_DIAMETER_MM,
            "rotations": ROTATIONS,
            "sectors_per_rev": SECTORS_PER_REV,
            "sectors": SECTORS,
            "lane_count": LANE_COUNT,
            "raw_half_8lane_mbps": RAW_HALF_8LANE_MBPS,
            "raw_fdx_4lane_per_dir_mbps": RAW_FDX_4LANE_PER_DIR_MBPS,
            "rate_claim": "raw_phy_only",
            "stats": asdict(self.stats),
            "endpoint_a": asdict(self.a),
            "endpoint_b": asdict(self.b),
        }


def write_csv(path: Path, summary: dict[str, object], failures: list[str]) -> None:
    stats = summary["stats"]
    assert isinstance(stats, dict)
    endpoint_a = summary["endpoint_a"]
    endpoint_b = summary["endpoint_b"]
    assert isinstance(endpoint_a, dict)
    assert isinstance(endpoint_b, dict)
    rows = [
        ("overall", "PASS" if not failures else "FAIL", "failures", ";".join(failures)),
        ("target", "PASS", "original_target_seconds", str(summary["original_target_seconds"])),
        ("target", "PASS", "runtime_cap_seconds", str(summary["runtime_cap_seconds"])),
        ("rotation", "PASS", "rpm", str(summary["rpm"])),
        ("rotation", "PASS", "shaft_diameter_mm", str(summary["shaft_diameter_mm"])),
        ("rotation", "PASS", "rotations", str(summary["rotations"])),
        ("rotation", "PASS", "sectors", str(summary["sectors"])),
        ("rate", "PASS", "raw_half_8lane_mbps", f"{float(summary['raw_half_8lane_mbps']):.6f}"),
        ("rate", "PASS", "raw_fdx_4lane_per_dir_mbps", f"{float(summary['raw_fdx_4lane_per_dir_mbps']):.6f}"),
        ("coverage", "PASS" if stats["tx_lane_coverage"] == 0xFF else "FAIL", "tx_lane_coverage", f"0x{int(stats['tx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["rx_lane_coverage"] == 0xFF else "FAIL", "rx_lane_coverage", f"0x{int(stats['rx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["half_tx_lane_coverage"] == 0xFF else "FAIL", "half_tx_lane_coverage", f"0x{int(stats['half_tx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["half_rx_lane_coverage"] == 0xFF else "FAIL", "half_rx_lane_coverage", f"0x{int(stats['half_rx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["fdx_a_to_b_tx_lane_coverage"] == FDX_A_TO_B_MASK else "FAIL", "fdx_a_to_b_tx_lane_coverage", f"0x{int(stats['fdx_a_to_b_tx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["fdx_b_to_a_tx_lane_coverage"] == FDX_B_TO_A_MASK else "FAIL", "fdx_b_to_a_tx_lane_coverage", f"0x{int(stats['fdx_b_to_a_tx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["fdx_a_to_b_rx_lane_coverage"] == FDX_A_TO_B_MASK else "FAIL", "fdx_a_to_b_rx_lane_coverage", f"0x{int(stats['fdx_a_to_b_rx_lane_coverage']):02x}"),
        ("coverage", "PASS" if stats["fdx_b_to_a_rx_lane_coverage"] == FDX_B_TO_A_MASK else "FAIL", "fdx_b_to_a_rx_lane_coverage", f"0x{int(stats['fdx_b_to_a_rx_lane_coverage']):02x}"),
        ("recovery", "PASS" if stats["unrecovered_errors"] == 0 else "FAIL", "unrecovered_errors", str(stats["unrecovered_errors"])),
        ("recovery", "PASS" if stats["deadlock_events"] == 0 else "FAIL", "deadlock_events", str(stats["deadlock_events"])),
        ("autoroute", "PASS" if stats["route_probe_events"] > 0 else "FAIL", "route_probe_events", str(stats["route_probe_events"])),
        ("autoroute", "PASS" if stats["max_route_probe_observed"] > 0 else "FAIL", "max_route_probe_observed", str(stats["max_route_probe_observed"])),
        ("network", "PASS" if endpoint_a["tcp_reconnect_events"] and endpoint_b["tcp_reconnect_events"] else "FAIL", "tcp_reconnect_events", str(endpoint_a["tcp_reconnect_events"] + endpoint_b["tcp_reconnect_events"])),
        ("network", "PASS" if endpoint_a["dhcp_static_fallback_events"] and endpoint_b["dhcp_static_fallback_events"] else "FAIL", "dhcp_static_fallback_events", str(endpoint_a["dhcp_static_fallback_events"] + endpoint_b["dhcp_static_fallback_events"])),
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("category,status,metric,value\n")
        for category, status, metric, value in rows:
            handle.write(f"{category},{status},{metric},{value}\n")


def write_markdown(path: Path, summary: dict[str, object], failures: list[str]) -> None:
    stats = summary["stats"]
    assert isinstance(stats, dict)
    endpoint_a = summary["endpoint_a"]
    endpoint_b = summary["endpoint_b"]
    assert isinstance(endpoint_a, dict)
    assert isinstance(endpoint_b, dict)
    overall = "PASS" if not failures else "FAIL"
    lines = [
        "# Full-System Capped Digital Twin",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "## Target Scope",
        "",
        f"- Original target seconds: `{summary['original_target_seconds']}`",
        f"- Runtime cap seconds: `{summary['runtime_cap_seconds']}`",
        f"- Effective modeled seconds: `{summary['seconds']}`",
        f"- Shaft diameter: `{summary['shaft_diameter_mm']} mm`",
        f"- Rotation speed: `{summary['rpm']} rpm`",
        f"- Rotations: `{summary['rotations']}`",
        f"- Sectors: `{summary['sectors']}`",
        f"- Lane count: `{summary['lane_count']}`",
        f"- Raw half-duplex capacity: `{float(summary['raw_half_8lane_mbps']):.6f} Mbit/s`",
        f"- Raw 4+4 full-duplex capacity per direction: `{float(summary['raw_fdx_4lane_per_dir_mbps']):.6f} Mbit/s`",
        f"- Rate claim: `{summary['rate_claim']}`",
        "",
        "## Coverage",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| transfers | `{stats['transfers']}` |",
        f"| fragments | `{stats['fragments']}` |",
        f"| payload_bytes | `{stats['payload_bytes']}` |",
        f"| half_duplex_slots | `{stats['half_duplex_slots']}` |",
        f"| full_duplex_slots | `{stats['full_duplex_slots']}` |",
        f"| tx_lane_coverage | `0x{int(stats['tx_lane_coverage']):02x}` |",
        f"| rx_lane_coverage | `0x{int(stats['rx_lane_coverage']):02x}` |",
        f"| route_map_coverage | `0x{int(stats['route_map_coverage']):02x}` |",
        f"| source_lane_coverage | `0x{int(stats['source_lane_coverage']):02x}` |",
        f"| half_tx_lane_coverage | `0x{int(stats['half_tx_lane_coverage']):02x}` |",
        f"| half_rx_lane_coverage | `0x{int(stats['half_rx_lane_coverage']):02x}` |",
        f"| fdx_a_to_b_tx_lane_coverage | `0x{int(stats['fdx_a_to_b_tx_lane_coverage']):02x}` |",
        f"| fdx_b_to_a_tx_lane_coverage | `0x{int(stats['fdx_b_to_a_tx_lane_coverage']):02x}` |",
        f"| fdx_a_to_b_rx_lane_coverage | `0x{int(stats['fdx_a_to_b_rx_lane_coverage']):02x}` |",
        f"| fdx_b_to_a_rx_lane_coverage | `0x{int(stats['fdx_b_to_a_rx_lane_coverage']):02x}` |",
        f"| failed_route_events | `{stats['failed_route_events']}` |",
        f"| short_blockage_events | `{stats['short_blockage_events']}` |",
        f"| crc_error_events | `{stats['crc_error_events']}` |",
        f"| fragment_ack_loss_events | `{stats['fragment_ack_loss_events']}` |",
        f"| final_ack_loss_events | `{stats['final_ack_loss_events']}` |",
        f"| route_probe_events | `{stats['route_probe_events']}` |",
        f"| max_route_probe_observed | `{stats['max_route_probe_observed']}` |",
        f"| queued_rx_delivered | `{stats['queued_rx_delivered']}` |",
        f"| unrecovered_errors | `{stats['unrecovered_errors']}` |",
        f"| deadlock_events | `{stats['deadlock_events']}` |",
        "",
        "## Network Model",
        "",
        "| endpoint | tcp_reconnect_events | dhcp_static_fallback_events | queued_rx_max |",
        "| --- | ---: | ---: | ---: |",
        f"| A | {endpoint_a['tcp_reconnect_events']} | {endpoint_a['dhcp_static_fallback_events']} | {endpoint_a['queued_rx_max']} |",
        f"| B | {endpoint_b['tcp_reconnect_events']} | {endpoint_b['dhcp_static_fallback_events']} | {endpoint_b['queued_rx_max']} |",
        "",
    ]
    if failures:
        lines += ["## Failures", "", *[f"- `{failure}`" for failure in failures], ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--csv-output", type=Path)
    args = parser.parse_args(argv)

    model = FullSystemModel()
    model.run()
    failures = model.validate()
    summary = model.summary()
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown_output is not None:
        write_markdown(args.markdown_output, summary, failures)
    if args.csv_output is not None:
        write_csv(args.csv_output, summary, failures)

    if failures:
        print("FULL_SYSTEM_CAPPED_DIGITAL_TWIN_FAIL " + ";".join(failures))
        return 1

    stats = model.stats
    print(
        "FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS "
        f"original_target_seconds={ORIGINAL_TARGET_SECONDS} runtime_cap_seconds={RUNTIME_CAP_SECONDS} "
        f"seconds={EFFECTIVE_SECONDS} rpm={TARGET_RPM} rev_per_s={REV_PER_SECOND} "
        f"shaft_diameter_mm={SHAFT_DIAMETER_MM} rotations={ROTATIONS} sectors={SECTORS} "
        f"lane_count={LANE_COUNT} transfers={stats.transfers} fragments={stats.fragments} "
        f"payload_bytes={stats.payload_bytes} half_duplex_slots={stats.half_duplex_slots} "
        f"full_duplex_slots={stats.full_duplex_slots} failed_route_events={stats.failed_route_events} "
        f"route_probe_events={stats.route_probe_events} max_route_probe_observed={stats.max_route_probe_observed} "
        f"short_blockage_events={stats.short_blockage_events} crc_error_events={stats.crc_error_events} "
        f"fragment_ack_loss_events={stats.fragment_ack_loss_events} final_ack_loss_events={stats.final_ack_loss_events} "
        f"tcp_reconnect_events={model.a.tcp_reconnect_events + model.b.tcp_reconnect_events} "
        f"dhcp_static_fallback_events={model.a.dhcp_static_fallback_events + model.b.dhcp_static_fallback_events} "
        f"queued_rx_delivered={stats.queued_rx_delivered} max_search_attempts={stats.max_search_attempts} "
        f"max_retry_observed={stats.max_retry_observed} tx_lane_coverage=0x{stats.tx_lane_coverage:02x} "
        f"rx_lane_coverage=0x{stats.rx_lane_coverage:02x} route_map_coverage=0x{stats.route_map_coverage:02x} "
        f"source_lane_coverage=0x{stats.source_lane_coverage:02x} unrecovered_errors={stats.unrecovered_errors} "
        f"half_tx_lane_coverage=0x{stats.half_tx_lane_coverage:02x} "
        f"half_rx_lane_coverage=0x{stats.half_rx_lane_coverage:02x} "
        f"fdx_a_to_b_tx_lane_coverage=0x{stats.fdx_a_to_b_tx_lane_coverage:02x} "
        f"fdx_b_to_a_tx_lane_coverage=0x{stats.fdx_b_to_a_tx_lane_coverage:02x} "
        f"fdx_a_to_b_rx_lane_coverage=0x{stats.fdx_a_to_b_rx_lane_coverage:02x} "
        f"fdx_b_to_a_rx_lane_coverage=0x{stats.fdx_b_to_a_rx_lane_coverage:02x} "
        f"deadlock_events={stats.deadlock_events} raw_half_8lane_mbps={RAW_HALF_8LANE_MBPS:.6f} "
        f"raw_fdx_4lane_per_dir_mbps={RAW_FDX_4LANE_PER_DIR_MBPS:.6f} rate_claim=raw_phy_only"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
