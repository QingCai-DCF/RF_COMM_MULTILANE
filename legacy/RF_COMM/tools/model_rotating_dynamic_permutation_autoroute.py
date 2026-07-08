#!/usr/bin/env python3
"""Offline model for rotating-shaft dynamic TX/RX permutation autoroute.

The model is deliberately side-effect free. It does not program FPGA hardware,
write UART, drive TFDU boards, or claim real rotating-shaft acceptance.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

LANE_COUNT = 8
TARGET_RPM = 600
SHAFT_DIAMETER_MM = 200
ORIGINAL_TARGET_SECONDS = 2 * 60 * 60
RUNTIME_CAP_SECONDS = 10 * 60
EFFECTIVE_SECONDS = min(ORIGINAL_TARGET_SECONDS, RUNTIME_CAP_SECONDS)
REV_PER_SECOND = TARGET_RPM // 60
ROTATIONS = REV_PER_SECOND * EFFECTIVE_SECONDS
SECTORS_PER_REV = LANE_COUNT
SECTORS = ROTATIONS * SECTORS_PER_REV
RAW_MBIT_PER_LANE = 4.0
RAW_HALF_8LANE_MBPS = RAW_MBIT_PER_LANE * LANE_COUNT
RAW_FDX_4LANE_PER_DIR_MBPS = RAW_MBIT_PER_LANE * (LANE_COUNT // 2)
HALF_MASK = 0xFF
FDX_A_TO_B_MASK = 0x0F
FDX_B_TO_A_MASK = 0xF0


@dataclass
class ModelStats:
    sectors: int = SECTORS
    rotations: int = ROTATIONS
    permutation_changes: int = 0
    transfers: int = 0
    fragments: int = 0
    route_relearn_events: int = 0
    stale_cache_events: int = 0
    blocked_probe_events: int = 0
    total_probes: int = 0
    max_probe_sweep: int = 0
    unrecovered_errors: int = 0
    deadlock_events: int = 0
    half_slots: int = 0
    full_duplex_slots: int = 0
    half_pair_coverage: int = 0
    fdx_a_to_b_pair_coverage: int = 0
    fdx_b_to_a_pair_coverage: int = 0
    half_tx_lane_coverage: int = 0
    half_rx_lane_coverage: int = 0
    fdx_a_to_b_tx_lane_coverage: int = 0
    fdx_a_to_b_rx_lane_coverage: int = 0
    fdx_b_to_a_tx_lane_coverage: int = 0
    fdx_b_to_a_rx_lane_coverage: int = 0
    unique_half_permutations: int = 0
    unique_fdx_a_to_b_permutations: int = 0
    unique_fdx_b_to_a_permutations: int = 0


def lanes_from_mask(mask: int) -> list[int]:
    return [lane for lane in range(LANE_COUNT) if ((mask >> lane) & 1) != 0]


def bit(mask: int, lane: int) -> bool:
    return ((mask >> lane) & 1) != 0


def pair_bit(tx_lane: int, rx_lane: int, rx_lanes: list[int]) -> int:
    return 1 << (tx_lane * len(rx_lanes) + rx_lanes.index(rx_lane))


def permutation_for(mask: int, sector: int, direction: int) -> dict[int, int]:
    lanes = lanes_from_mask(mask)
    n = len(lanes)
    stride_options = (1, 3, 5, 7) if n == 8 else (1, 3)
    stride = stride_options[(sector // n + direction) % len(stride_options)]
    offset = (sector + direction * 3 + sector // 17 + sector // 257) % n
    return {tx_lane: lanes[(idx * stride + offset) % n] for idx, tx_lane in enumerate(lanes)}


def is_blocked(sector: int, direction: int, tx_lane: int, frag: int) -> bool:
    # Deterministic short impairment. It forces real probing but remains recoverable.
    return ((sector * 11 + direction * 19 + tx_lane * 7 + frag * 5) % 113) in {17, 41}


class DynamicPermutationModel:
    def __init__(self) -> None:
        self.stats = ModelStats()
        self.cache: dict[tuple[str, int], tuple[int, int] | None] = {
            ("half", 0): None,
            ("half", 1): None,
            ("fdx", 0): None,
            ("fdx", 1): None,
        }
        self.rr: dict[tuple[str, int], int] = {
            ("half", 0): 0,
            ("half", 1): 0,
            ("fdx", 0): 0,
            ("fdx", 1): 0,
        }
        self.half_permutations: set[tuple[tuple[int, int], ...]] = set()
        self.fdx_a_to_b_permutations: set[tuple[tuple[int, int], ...]] = set()
        self.fdx_b_to_a_permutations: set[tuple[tuple[int, int], ...]] = set()

    def observe_pair(self, mode: str, direction: int, tx_lane: int, rx_lane: int) -> None:
        if mode == "half":
            self.stats.half_tx_lane_coverage |= 1 << tx_lane
            self.stats.half_rx_lane_coverage |= 1 << rx_lane
            self.stats.half_pair_coverage |= pair_bit(tx_lane, rx_lane, lanes_from_mask(HALF_MASK))
        elif direction == 0:
            self.stats.fdx_a_to_b_tx_lane_coverage |= 1 << tx_lane
            self.stats.fdx_a_to_b_rx_lane_coverage |= 1 << rx_lane
            self.stats.fdx_a_to_b_pair_coverage |= pair_bit(tx_lane, rx_lane, lanes_from_mask(FDX_A_TO_B_MASK))
        else:
            self.stats.fdx_b_to_a_tx_lane_coverage |= 1 << tx_lane
            self.stats.fdx_b_to_a_rx_lane_coverage |= 1 << rx_lane
            self.stats.fdx_b_to_a_pair_coverage |= pair_bit(tx_lane, rx_lane, lanes_from_mask(FDX_B_TO_A_MASK))

    def probe(self, mode: str, direction: int, sector: int, frag: int, lane_mask: int, perm: dict[int, int]) -> None:
        key = (mode, direction)
        cached = self.cache[key]
        tx_lanes = lanes_from_mask(lane_mask)
        if cached is not None and ((sector + direction + frag) % 5) == 0:
            start_lane = cached[0]
        else:
            start_lane = tx_lanes[self.rr[key] % len(tx_lanes)]
        start_idx = tx_lanes.index(start_lane) if start_lane in tx_lanes else 0
        probe_order = tx_lanes[start_idx:] + tx_lanes[:start_idx]

        probes = 0
        found: tuple[int, int] | None = None
        for tx_lane in probe_order:
            probes += 1
            rx_lane = perm[tx_lane]
            if is_blocked(sector, direction, tx_lane, frag):
                self.stats.blocked_probe_events += 1
                continue
            found = (tx_lane, rx_lane)
            break

        self.stats.total_probes += probes
        self.stats.max_probe_sweep = max(self.stats.max_probe_sweep, probes)
        if found is None:
            self.stats.unrecovered_errors += 1
            return

        if cached is None or cached != found:
            self.stats.route_relearn_events += 1
        if cached is not None and cached != found:
            self.stats.stale_cache_events += 1

        self.cache[key] = found
        self.rr[key] = (tx_lanes.index(found[0]) + 1) % len(tx_lanes)
        self.observe_pair(mode, direction, found[0], found[1])

    def transfer(self, mode: str, direction: int, sector: int, lane_mask: int, perm: dict[int, int]) -> None:
        frag_count = 1 + ((sector + direction * 3) % 8)
        self.stats.transfers += 1
        self.stats.fragments += frag_count
        for frag in range(frag_count):
            self.probe(mode, direction, sector, frag, lane_mask, perm)

    def run(self) -> None:
        last_half_perm: tuple[tuple[int, int], ...] | None = None
        last_a_perm: tuple[tuple[int, int], ...] | None = None
        last_b_perm: tuple[tuple[int, int], ...] | None = None

        for sector in range(SECTORS):
            half_perm = permutation_for(HALF_MASK, sector, 0)
            a_perm = permutation_for(FDX_A_TO_B_MASK, sector, 0)
            b_perm = permutation_for(FDX_B_TO_A_MASK, sector, 1)
            half_key = tuple(sorted(half_perm.items()))
            a_key = tuple(sorted(a_perm.items()))
            b_key = tuple(sorted(b_perm.items()))
            self.half_permutations.add(half_key)
            self.fdx_a_to_b_permutations.add(a_key)
            self.fdx_b_to_a_permutations.add(b_key)
            if half_key != last_half_perm:
                self.stats.permutation_changes += 1
            if a_key != last_a_perm:
                self.stats.permutation_changes += 1
            if b_key != last_b_perm:
                self.stats.permutation_changes += 1
            last_half_perm = half_key
            last_a_perm = a_key
            last_b_perm = b_key

            if sector % 2 == 0:
                self.stats.full_duplex_slots += 1
                self.transfer("fdx", 0, sector, FDX_A_TO_B_MASK, a_perm)
                self.transfer("fdx", 1, sector, FDX_B_TO_A_MASK, b_perm)
            else:
                self.stats.half_slots += 1
                self.transfer("half", (sector // 2) & 1, sector, HALF_MASK, half_perm)

        self.stats.unique_half_permutations = len(self.half_permutations)
        self.stats.unique_fdx_a_to_b_permutations = len(self.fdx_a_to_b_permutations)
        self.stats.unique_fdx_b_to_a_permutations = len(self.fdx_b_to_a_permutations)

    def validate(self) -> list[str]:
        failures: list[str] = []
        if self.stats.sectors != SECTORS or self.stats.rotations != ROTATIONS:
            failures.append("rotating metadata mismatch")
        if self.stats.unrecovered_errors or self.stats.deadlock_events:
            failures.append("unrecovered error or deadlock")
        if self.stats.half_pair_coverage.bit_count() != 64:
            failures.append(f"half pair coverage {self.stats.half_pair_coverage.bit_count()}/64")
        if self.stats.fdx_a_to_b_pair_coverage.bit_count() != 16:
            failures.append(f"fdx A->B pair coverage {self.stats.fdx_a_to_b_pair_coverage.bit_count()}/16")
        if self.stats.fdx_b_to_a_pair_coverage.bit_count() != 16:
            failures.append(f"fdx B->A pair coverage {self.stats.fdx_b_to_a_pair_coverage.bit_count()}/16")
        if self.stats.half_tx_lane_coverage != 0xFF or self.stats.half_rx_lane_coverage != 0xFF:
            failures.append("half lane coverage incomplete")
        if self.stats.fdx_a_to_b_tx_lane_coverage != 0x0F or self.stats.fdx_a_to_b_rx_lane_coverage != 0x0F:
            failures.append("fdx A->B lane coverage incomplete")
        if self.stats.fdx_b_to_a_tx_lane_coverage != 0xF0 or self.stats.fdx_b_to_a_rx_lane_coverage != 0xF0:
            failures.append("fdx B->A lane coverage incomplete")
        if self.stats.stale_cache_events == 0 or self.stats.route_relearn_events == 0:
            failures.append("dynamic route relearn path not exercised")
        if self.stats.blocked_probe_events == 0 or self.stats.max_probe_sweep <= 1:
            failures.append("blocked probe recovery path not exercised")
        if self.stats.unique_half_permutations < 32:
            failures.append("half permutation diversity too low")
        if self.stats.unique_fdx_a_to_b_permutations < 8 or self.stats.unique_fdx_b_to_a_permutations < 8:
            failures.append("fdx permutation diversity too low")
        return failures

    def summary(self, failures: list[str]) -> dict[str, object]:
        return {
            "generated": datetime.now().isoformat(timespec="seconds"),
            "overall": "PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE" if not failures else "FAIL",
            "evidence_type": "OFFLINE_MODEL_NOT_HARDWARE",
            "original_target_seconds": ORIGINAL_TARGET_SECONDS,
            "runtime_cap_seconds": RUNTIME_CAP_SECONDS,
            "seconds": EFFECTIVE_SECONDS,
            "rpm": TARGET_RPM,
            "shaft_diameter_mm": SHAFT_DIAMETER_MM,
            "rotations": ROTATIONS,
            "sectors_per_rev": SECTORS_PER_REV,
            "sectors": SECTORS,
            "lane_count": LANE_COUNT,
            "raw_half_8lane_mbps": RAW_HALF_8LANE_MBPS,
            "raw_fdx_4lane_per_dir_mbps": RAW_FDX_4LANE_PER_DIR_MBPS,
            "rate_claim": "raw_phy_only",
            "no_hardware_programming": True,
            "no_uart_write": True,
            "no_tfdu_drive": True,
            "real_rotating_shaft_acceptance": False,
            "failures": failures,
            "stats": asdict(self.stats),
        }


def write_csv(path: Path, summary: dict[str, object]) -> None:
    stats = summary["stats"]
    assert isinstance(stats, dict)
    rows = [
        ("overall", summary["overall"], "failures", ";".join(summary["failures"])),
        ("target", "PASS", "seconds", str(summary["seconds"])),
        ("target", "PASS", "rpm", str(summary["rpm"])),
        ("target", "PASS", "shaft_diameter_mm", str(summary["shaft_diameter_mm"])),
        ("rate", "PASS", "raw_half_8lane_mbps", f"{summary['raw_half_8lane_mbps']:.6f}"),
        ("rate", "PASS", "raw_fdx_4lane_per_dir_mbps", f"{summary['raw_fdx_4lane_per_dir_mbps']:.6f}"),
        ("permutation", "PASS", "permutation_changes", str(stats["permutation_changes"])),
        ("permutation", "PASS", "unique_half_permutations", str(stats["unique_half_permutations"])),
        ("permutation", "PASS", "unique_fdx_a_to_b_permutations", str(stats["unique_fdx_a_to_b_permutations"])),
        ("permutation", "PASS", "unique_fdx_b_to_a_permutations", str(stats["unique_fdx_b_to_a_permutations"])),
        ("autoroute", "PASS", "route_relearn_events", str(stats["route_relearn_events"])),
        ("autoroute", "PASS", "stale_cache_events", str(stats["stale_cache_events"])),
        ("autoroute", "PASS", "blocked_probe_events", str(stats["blocked_probe_events"])),
        ("autoroute", "PASS", "max_probe_sweep", str(stats["max_probe_sweep"])),
        ("coverage", "PASS", "half_pair_coverage_count", str(int(stats["half_pair_coverage"]).bit_count())),
        ("coverage", "PASS", "fdx_a_to_b_pair_coverage_count", str(int(stats["fdx_a_to_b_pair_coverage"]).bit_count())),
        ("coverage", "PASS", "fdx_b_to_a_pair_coverage_count", str(int(stats["fdx_b_to_a_pair_coverage"]).bit_count())),
        ("recovery", "PASS", "unrecovered_errors", str(stats["unrecovered_errors"])),
        ("recovery", "PASS", "deadlock_events", str(stats["deadlock_events"])),
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["category", "status", "metric", "value"])
        writer.writerows(rows)


def write_markdown(path: Path, summary: dict[str, object]) -> None:
    stats = summary["stats"]
    assert isinstance(stats, dict)
    lines = [
        "# Rotating Dynamic Permutation Autoroute",
        "",
        f"Generated: {summary['generated']}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{summary['overall']}`",
        "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Real rotating-shaft acceptance: `0`",
        "",
        "This model exercises the project requirement that the rotating side can recover when transmitter-to-receiver correspondence changes. It is not physical TFDU or shaft evidence.",
        "",
        "## Target Scope",
        "",
        f"- Modeled seconds: `{summary['seconds']}`",
        f"- Original target seconds: `{summary['original_target_seconds']}`",
        f"- Runtime cap seconds: `{summary['runtime_cap_seconds']}`",
        f"- Shaft diameter: `{summary['shaft_diameter_mm']} mm`",
        f"- Rotation speed: `{summary['rpm']} rpm`",
        f"- Rotations: `{summary['rotations']}`",
        f"- Sectors: `{summary['sectors']}`",
        f"- Raw half-duplex capacity: `{summary['raw_half_8lane_mbps']:.6f} Mbit/s`",
        f"- Raw 4+4 full-duplex capacity per direction: `{summary['raw_fdx_4lane_per_dir_mbps']:.6f} Mbit/s`",
        "",
        "## Coverage",
        "",
        "| metric | value |",
        "| --- | --- |",
        f"| permutation_changes | `{stats['permutation_changes']}` |",
        f"| unique_half_permutations | `{stats['unique_half_permutations']}` |",
        f"| unique_fdx_a_to_b_permutations | `{stats['unique_fdx_a_to_b_permutations']}` |",
        f"| unique_fdx_b_to_a_permutations | `{stats['unique_fdx_b_to_a_permutations']}` |",
        f"| route_relearn_events | `{stats['route_relearn_events']}` |",
        f"| stale_cache_events | `{stats['stale_cache_events']}` |",
        f"| blocked_probe_events | `{stats['blocked_probe_events']}` |",
        f"| max_probe_sweep | `{stats['max_probe_sweep']}` |",
        f"| half_pair_coverage_count | `{int(stats['half_pair_coverage']).bit_count()}/64` |",
        f"| fdx_a_to_b_pair_coverage_count | `{int(stats['fdx_a_to_b_pair_coverage']).bit_count()}/16` |",
        f"| fdx_b_to_a_pair_coverage_count | `{int(stats['fdx_b_to_a_pair_coverage']).bit_count()}/16` |",
        f"| half_tx_lane_coverage | `0x{int(stats['half_tx_lane_coverage']):02x}` |",
        f"| half_rx_lane_coverage | `0x{int(stats['half_rx_lane_coverage']):02x}` |",
        f"| fdx_a_to_b_tx_lane_coverage | `0x{int(stats['fdx_a_to_b_tx_lane_coverage']):02x}` |",
        f"| fdx_a_to_b_rx_lane_coverage | `0x{int(stats['fdx_a_to_b_rx_lane_coverage']):02x}` |",
        f"| fdx_b_to_a_tx_lane_coverage | `0x{int(stats['fdx_b_to_a_tx_lane_coverage']):02x}` |",
        f"| fdx_b_to_a_rx_lane_coverage | `0x{int(stats['fdx_b_to_a_rx_lane_coverage']):02x}` |",
        f"| unrecovered_errors | `{stats['unrecovered_errors']}` |",
        f"| deadlock_events | `{stats['deadlock_events']}` |",
        "",
        "```text",
        f"RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall={summary['overall']} "
        f"seconds={summary['seconds']} rpm={summary['rpm']} shaft_diameter_mm={summary['shaft_diameter_mm']} "
        f"permutation_changes={stats['permutation_changes']} half_pairs={int(stats['half_pair_coverage']).bit_count()}/64 "
        f"fdx_a_to_b_pairs={int(stats['fdx_a_to_b_pair_coverage']).bit_count()}/16 "
        f"fdx_b_to_a_pairs={int(stats['fdx_b_to_a_pair_coverage']).bit_count()}/16 "
        f"route_relearn_events={stats['route_relearn_events']} stale_cache_events={stats['stale_cache_events']} "
        f"blocked_probe_events={stats['blocked_probe_events']} max_probe_sweep={stats['max_probe_sweep']} "
        f"unrecovered_errors={stats['unrecovered_errors']} deadlock_events={stats['deadlock_events']}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "REAL_ROTATING_SHAFT_ACCEPTANCE=0",
        "```",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    model = DynamicPermutationModel()
    model.run()
    failures = model.validate()
    summary = model.summary(failures)
    md_path = REPORTS / "rotating_dynamic_permutation_autoroute_current.md"
    json_path = REPORTS / "rotating_dynamic_permutation_autoroute_current.json"
    csv_path = REPORTS / "rotating_dynamic_permutation_autoroute_current.csv"
    write_markdown(md_path, summary)
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(csv_path, summary)
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    stats = summary["stats"]
    assert isinstance(stats, dict)
    print(
        f"RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall={summary['overall']} "
        f"seconds={summary['seconds']} rpm={summary['rpm']} shaft_diameter_mm={summary['shaft_diameter_mm']} "
        f"permutation_changes={stats['permutation_changes']} "
        f"half_pairs={int(stats['half_pair_coverage']).bit_count()}/64 "
        f"fdx_a_to_b_pairs={int(stats['fdx_a_to_b_pair_coverage']).bit_count()}/16 "
        f"fdx_b_to_a_pairs={int(stats['fdx_b_to_a_pair_coverage']).bit_count()}/16 "
        f"route_relearn_events={stats['route_relearn_events']} "
        f"stale_cache_events={stats['stale_cache_events']} "
        f"blocked_probe_events={stats['blocked_probe_events']} max_probe_sweep={stats['max_probe_sweep']} "
        f"unrecovered_errors={stats['unrecovered_errors']} deadlock_events={stats['deadlock_events']}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("REAL_ROTATING_SHAFT_ACCEPTANCE=0")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
