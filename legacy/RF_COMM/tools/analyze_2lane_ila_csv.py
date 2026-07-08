#!/usr/bin/env python3
"""Analyze RF_COMM 2-lane ILA CSV captures.

The tool is intentionally offline-only: it reads Vivado ILA CSV files and
optional run summaries, then classifies raw lane activity without touching
hardware.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


SIGNAL_TOKENS = {
    "a_tx": "ir_array_top_axi_0_ir_tx_out",
    "a_rx": "ir_rx_in_0_1",
    "a_sd": "ir_array_top_axi_0_ir_sd",
    "a_mode": "ir_array_top_axi_0_ir_mode_out",
    "b_tx": "ir_loopback_b0_ir_tx_out",
    "b_rx": "loop_rx_b0_1",
    "b_sd": "ir_loopback_b0_ir_sd",
    "b_mode": "ir_loopback_b0_ir_mode_out",
    "b_debug": "ir_loopback_b0_debug_status",
}


@dataclass
class SignalMetrics:
    signal: str
    lane: int
    polarity: str
    samples: int
    active_samples: int
    active_fraction: float
    edges: int
    pulse_count: int
    first_active: int | None
    last_active: int | None
    min_width: int | None
    median_width: float | None
    max_width: int | None
    initial_value: int | None
    final_value: int | None
    stuck_active: bool
    has_pulse_activity: bool


@dataclass
class LinkMetrics:
    name: str
    tx_signal: str
    tx_lane: int
    rx_signal: str
    rx_lane: int
    near_rx_signal: str
    near_rx_lane: int
    tx_pulses: int
    rx_pulses: int
    near_rx_pulses: int
    tx_edges: int
    rx_edges: int
    near_rx_edges: int
    first_tx: int | None
    first_rx: int | None
    first_near_rx: int | None
    first_delay_samples: int | None
    first_near_delay_samples: int | None
    paired_delays_samples: list[int]
    near_paired_delays_samples: list[int]
    verdict: str


@dataclass
class CaptureAnalysis:
    csv_path: str
    summary_path: str | None
    trigger_mode: str
    expected: str
    samples: int
    verdict: str
    verdict_reason: str
    signals: dict[str, SignalMetrics]
    links: dict[str, LinkMetrics]
    b_debug_first: str | None
    b_debug_last: str | None
    b_debug_unique_count: int
    b_debug_class_counts: dict[str, int]
    b_debug_top_values: list[str]


def parse_value(raw: str) -> int:
    raw = raw.strip()
    if raw == "":
        return 0
    try:
        return int(raw, 16)
    except ValueError:
        return int(raw, 0)


def decode_b_debug(value: int) -> str:
    top_nibble = (value >> 28) & 0xF
    subcode = (value >> 24) & 0xF
    top_byte = (value >> 24) & 0xFF
    if value == 0:
        return "IDLE_ZERO"
    if top_byte == 0xEC:
        ack_lane1 = (value >> 16) & 0xFF
        ack_lane0 = (value >> 8) & 0xFF
        rx_good = value & 0xFF
        return f"EC_COUNTERS ack_lane1={ack_lane1} ack_lane0={ack_lane0} rx_good={rx_good}"
    if top_nibble != 0xD:
        return f"UNKNOWN_0x{value:08x}"
    if subcode == 0x1:
        return "D1_REASSEMBLY_TIMEOUT"
    if subcode == 0x2:
        return "D2_DATA_PARSE_OR_PROTOCOL_MISMATCH"
    if subcode == 0x3:
        return "D3_REASSEMBLY_CONTEXT_MISMATCH"
    if subcode == 0x4:
        seen_session = (value >> 12) & 0xFFF
        expected_session = value & 0xFFF
        return f"D4_SESSION_MISMATCH seen=0x{seen_session:03x} expected=0x{expected_session:03x}"
    if subcode == 0x5:
        seen_session = (value >> 16) & 0xFF
        seq = (value >> 8) & 0xFF
        frame_len = value & 0xFF
        return f"D5_DATA_CRC_FAIL session_lsb=0x{seen_session:02x} seq=0x{seq:02x} frame_len={frame_len}"
    if subcode == 0x6:
        frag_idx = (value >> 20) & 0xF
        frag_count = (value >> 16) & 0xF
        total_len = (value >> 8) & 0xFF
        payload_len = value & 0xFF
        return f"D6_DATA_SHAPE_FAIL frag={frag_idx}/{frag_count} total_len={total_len} payload_len={payload_len}"
    if subcode == 0x7:
        raw_idx = (value >> 16) & 0xFF
        expected = (value >> 8) & 0xFF
        actual = value & 0xFF
        return f"D7_APP_PAYLOAD_BYTE_MISMATCH idx={raw_idx} expected=0x{expected:02x} actual=0x{actual:02x}"
    if subcode == 0x8:
        raw_idx = (value >> 16) & 0xFF
        expected_len = (value >> 8) & 0xFF
        return f"D8_APP_PACKET_LENGTH_MISMATCH idx={raw_idx} expected_len={expected_len}"
    if subcode == 0x9:
        lane = (value >> 20) & 0xF
        frag_idx = (value >> 16) & 0xF
        frag_count = (value >> 12) & 0xF
        payload_len = (value >> 8) & 0xF
        seq = value & 0xFF
        return f"D9_DATA_FRAGMENT_ACCEPTED lane={lane} frag={frag_idx}/{frag_count} payload_len_lsn={payload_len} seq=0x{seq:02x}"
    return f"D{subcode:X}_UNMAPPED_0x{value:08x}"


def find_column(header: list[str], token: str) -> int | None:
    matches = [idx for idx, name in enumerate(header) if token in name]
    return matches[0] if matches else None


def active_runs(bits: list[int], active_value: int) -> list[tuple[int, int]]:
    runs: list[tuple[int, int]] = []
    start: int | None = None
    for idx, bit in enumerate(bits):
        if bit == active_value and start is None:
            start = idx
        elif bit != active_value and start is not None:
            runs.append((start, idx - 1))
            start = None
    if start is not None:
        runs.append((start, len(bits) - 1))
    return runs


def summarize_bits(signal: str, lane: int, bits: list[int], active_value: int) -> SignalMetrics:
    samples = len(bits)
    runs = active_runs(bits, active_value)
    widths = [end - start + 1 for start, end in runs]
    active_samples = sum(widths)
    edges = sum(1 for a, b in zip(bits, bits[1:]) if a != b)
    active_fraction = (active_samples / samples) if samples else 0.0
    stuck_active = active_fraction >= 0.95
    has_pulse_activity = active_samples > 0 and not stuck_active and (edges > 0 or len(runs) > 1)
    return SignalMetrics(
        signal=signal,
        lane=lane,
        polarity="active_high" if active_value else "active_low",
        samples=samples,
        active_samples=active_samples,
        active_fraction=round(active_fraction, 6),
        edges=edges,
        pulse_count=len(runs),
        first_active=runs[0][0] if runs else None,
        last_active=runs[-1][1] if runs else None,
        min_width=min(widths) if widths else None,
        median_width=statistics.median(widths) if widths else None,
        max_width=max(widths) if widths else None,
        initial_value=bits[0] if bits else None,
        final_value=bits[-1] if bits else None,
        stuck_active=stuck_active,
        has_pulse_activity=has_pulse_activity,
    )


def paired_delays(tx_runs: list[tuple[int, int]], rx_runs: list[tuple[int, int]]) -> list[int]:
    return [rx[0] - tx[0] for tx, rx in zip(tx_runs, rx_runs)]


def classify_link(name: str, tx: SignalMetrics, rx: SignalMetrics, delays: list[int]) -> str:
    if tx.stuck_active:
        return "FAIL_TX_STUCK_ACTIVE"
    if rx.stuck_active:
        return "FAIL_RX_STUCK_ACTIVE"
    if not tx.has_pulse_activity:
        return "NO_TX_ACTIVITY"
    if not rx.has_pulse_activity:
        return "FAIL_NO_RX_ACTIVITY"
    if delays and min(delays) < -5:
        return "PASS_RAW_PULSE_RX_EARLY_WARN"
    return "PASS_RAW_PULSE"


def read_summary_trigger(csv_path: Path) -> tuple[Path | None, str]:
    summary_path = csv_path.with_suffix(".summary.txt")
    if not summary_path.exists():
        return None, ""
    text = summary_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"^TRIGGER_MODE=(\S+)", text, re.MULTILINE)
    return summary_path, match.group(1) if match else ""


def expected_from_name(csv_path: Path, trigger_mode: str) -> str:
    name = csv_path.name.lower()
    trigger = trigger_mode.lower()
    merged = f"{name} {trigger}"
    if "a_tx_lane0" in merged:
        return "A_TO_B_LANE0"
    if "a_tx_lane1" in merged:
        return "A_TO_B_LANE1"
    if "b_tx_lane0" in merged:
        return "B_TO_A_LANE0"
    if "b_tx_lane1" in merged:
        return "B_TO_A_LANE1"
    if "b_tx_nonzero" in merged:
        return "B_TO_A_ANY"
    if "b2a_rx_lane0" in merged:
        return "B_TO_A_LANE0"
    if "b2a_rx_lane1" in merged:
        return "B_TO_A_LANE1"
    if "b2a_rx_nonzero" in merged:
        return "B_TO_A_ANY"
    if "b_rx" in merged:
        return "A_TO_B_ANY"
    return "UNKNOWN"


def load_vectors(csv_path: Path) -> tuple[int, dict[str, list[int]]]:
    with csv_path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            next(reader, None)
        except StopIteration:
            raise ValueError(f"Empty ILA CSV: {csv_path}")

        columns = {name: find_column(header, token) for name, token in SIGNAL_TOKENS.items()}
        vectors: dict[str, list[int]] = {name: [] for name, idx in columns.items() if idx is not None}
        for row in reader:
            for name, idx in columns.items():
                if idx is None or idx >= len(row):
                    continue
                vectors[name].append(parse_value(row[idx]))

    samples = max((len(values) for values in vectors.values()), default=0)
    return samples, vectors


def lane_bits(vectors: dict[str, list[int]], signal: str, lane: int) -> list[int]:
    return [((value >> lane) & 1) for value in vectors.get(signal, [])]


def analyze_capture(csv_path: Path) -> CaptureAnalysis:
    summary_path, trigger_mode = read_summary_trigger(csv_path)
    expected = expected_from_name(csv_path, trigger_mode)
    samples, vectors = load_vectors(csv_path)

    signals: dict[str, SignalMetrics] = {}
    for signal in ("a_tx", "a_rx", "b_tx", "b_rx", "a_sd", "b_sd", "a_mode", "b_mode"):
        if signal not in vectors:
            continue
        active_value = 0 if signal.endswith("_rx") else 1
        for lane in (0, 1):
            key = f"{signal}{lane}"
            signals[key] = summarize_bits(signal, lane, lane_bits(vectors, signal, lane), active_value)

    links: dict[str, LinkMetrics] = {}
    link_defs = {
        "A_TO_B_LANE0": ("a_tx0", "b_rx0", "a_rx0"),
        "A_TO_B_LANE1": ("a_tx1", "b_rx1", "a_rx1"),
        "A_TO_B_CROSS_0_TO_1": ("a_tx0", "b_rx1", "a_rx0"),
        "A_TO_B_CROSS_1_TO_0": ("a_tx1", "b_rx0", "a_rx1"),
        "B_TO_A_LANE0": ("b_tx0", "a_rx0", "b_rx0"),
        "B_TO_A_LANE1": ("b_tx1", "a_rx1", "b_rx1"),
        "B_TO_A_CROSS_0_TO_1": ("b_tx0", "a_rx1", "b_rx0"),
        "B_TO_A_CROSS_1_TO_0": ("b_tx1", "a_rx0", "b_rx1"),
    }
    for name, (tx_key, rx_key, near_rx_key) in link_defs.items():
        if tx_key not in signals or rx_key not in signals or near_rx_key not in signals:
            continue
        tx = signals[tx_key]
        rx = signals[rx_key]
        near_rx = signals[near_rx_key]
        tx_runs = active_runs(lane_bits(vectors, tx.signal, tx.lane), 1)
        rx_runs = active_runs(lane_bits(vectors, rx.signal, rx.lane), 0)
        near_rx_runs = active_runs(lane_bits(vectors, near_rx.signal, near_rx.lane), 0)
        delays = paired_delays(tx_runs, rx_runs)
        near_delays = paired_delays(tx_runs, near_rx_runs)
        first_delay = None
        if tx.first_active is not None and rx.first_active is not None:
            first_delay = rx.first_active - tx.first_active
        first_near_delay = None
        if tx.first_active is not None and near_rx.first_active is not None:
            first_near_delay = near_rx.first_active - tx.first_active
        links[name] = LinkMetrics(
            name=name,
            tx_signal=tx.signal,
            tx_lane=tx.lane,
            rx_signal=rx.signal,
            rx_lane=rx.lane,
            near_rx_signal=near_rx.signal,
            near_rx_lane=near_rx.lane,
            tx_pulses=tx.pulse_count,
            rx_pulses=rx.pulse_count,
            near_rx_pulses=near_rx.pulse_count,
            tx_edges=tx.edges,
            rx_edges=rx.edges,
            near_rx_edges=near_rx.edges,
            first_tx=tx.first_active,
            first_rx=rx.first_active,
            first_near_rx=near_rx.first_active,
            first_delay_samples=first_delay,
            first_near_delay_samples=first_near_delay,
            paired_delays_samples=delays[:16],
            near_paired_delays_samples=near_delays[:16],
            verdict=classify_link(name, tx, rx, delays),
        )

    verdict, reason = classify_capture(expected, links, signals)
    b_debug = vectors.get("b_debug", [])
    unique_debug = len(set(b_debug)) if b_debug else 0
    class_counter = Counter(decode_b_debug(value) for value in b_debug)
    top_value_counter = Counter(f"0x{value:08x}" for value in b_debug)
    return CaptureAnalysis(
        csv_path=str(csv_path),
        summary_path=str(summary_path) if summary_path else None,
        trigger_mode=trigger_mode,
        expected=expected,
        samples=samples,
        verdict=verdict,
        verdict_reason=reason,
        signals=signals,
        links=links,
        b_debug_first=f"0x{b_debug[0]:08x}" if b_debug else None,
        b_debug_last=f"0x{b_debug[-1]:08x}" if b_debug else None,
        b_debug_unique_count=unique_debug,
        b_debug_class_counts=dict(class_counter.most_common(12)),
        b_debug_top_values=[f"{value} count={count}" for value, count in top_value_counter.most_common(12)],
    )


def classify_capture(
    expected: str, links: dict[str, LinkMetrics], signals: dict[str, SignalMetrics]
) -> tuple[str, str]:
    if expected in links:
        main = links[expected]
        if main.verdict.startswith("PASS_RAW_PULSE"):
            cross_names = []
            if expected == "A_TO_B_LANE0":
                cross_names = ["A_TO_B_CROSS_0_TO_1"]
            elif expected == "A_TO_B_LANE1":
                cross_names = ["A_TO_B_CROSS_1_TO_0"]
            elif expected == "B_TO_A_LANE0":
                cross_names = ["B_TO_A_CROSS_0_TO_1"]
            elif expected == "B_TO_A_LANE1":
                cross_names = ["B_TO_A_CROSS_1_TO_0"]
            cross_active = [name for name in cross_names if links.get(name) and links[name].rx_pulses > 0]
            if cross_active:
                return "WARN_CROSS_ACTIVITY", f"{expected} passed but cross RX activity exists: {','.join(cross_active)}"
            return "PASS_EXPECTED_RAW", f"{expected} has TX and corresponding RX pulse activity"
        near_note = ""
        if main.tx_pulses > 0 and main.rx_pulses == 0 and main.near_rx_pulses > 0:
            near_note = (
                f" near_rx_echo={main.near_rx_signal}{main.near_rx_lane}:"
                f"pulses={main.near_rx_pulses}:delay={main.first_near_delay_samples}"
            )
        return "FAIL_EXPECTED_RAW", f"{expected} verdict={main.verdict}{near_note}"

    if expected == "A_TO_B_ANY":
        passed = [
            name
            for name in ("A_TO_B_LANE0", "A_TO_B_LANE1")
            if links.get(name) and links[name].verdict.startswith("PASS_RAW_PULSE")
        ]
        return ("PASS_ANY_A_TO_B", ",".join(passed)) if passed else ("FAIL_NO_A_TO_B_LINK", "no A_TO_B lane has corresponding raw pulse")

    if expected == "B_TO_A_ANY":
        passed = [
            name
            for name in ("B_TO_A_LANE0", "B_TO_A_LANE1")
            if links.get(name) and links[name].verdict.startswith("PASS_RAW_PULSE")
        ]
        return ("PASS_ANY_B_TO_A", ",".join(passed)) if passed else ("FAIL_NO_B_TO_A_LINK", "no B_TO_A lane has corresponding raw pulse")

    active_links = [
        name
        for name, link in links.items()
        if link.verdict.startswith("PASS_RAW_PULSE") and "CROSS" not in name
    ]
    if active_links:
        return "PASS_UNEXPECTED_ACTIVITY", ",".join(active_links)
    active_tx = [name for name, metric in signals.items() if name.endswith(("tx0", "tx1")) and metric.has_pulse_activity]
    if active_tx:
        return "FAIL_TX_WITHOUT_LINKED_RX", ",".join(active_tx)
    return "INCONCLUSIVE_NO_EXPECTATION", "no expected trigger and no main link activity"


def latest_ila_csvs(limit: int | None) -> list[Path]:
    paths = sorted(REPORTS.glob("ila_2lane_prearmed_*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    return paths[:limit] if limit else paths


def expand_inputs(paths: Iterable[str], glob_pattern: str | None, limit: int | None) -> list[Path]:
    out: list[Path] = []
    for item in paths:
        path = Path(item)
        if not path.is_absolute():
            path = ROOT / path
        out.append(path)
    if glob_pattern:
        out.extend(sorted(ROOT.glob(glob_pattern)))
    if not out:
        out = latest_ila_csvs(limit)
    return [path for path in out if path.exists()]


def to_jsonable(analysis: CaptureAnalysis) -> dict:
    data = asdict(analysis)
    return data


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join("" if cell is None else str(cell) for cell in row) + " |")
    return "\n".join(lines)


def render_markdown(analyses: list[CaptureAnalysis]) -> str:
    summary_rows = []
    for analysis in analyses:
        debug_preview = ", ".join(
            f"{key}:{value}" for key, value in list(analysis.b_debug_class_counts.items())[:3]
        )
        summary_rows.append(
            [
                Path(analysis.csv_path).name,
                analysis.trigger_mode or "UNKNOWN",
                analysis.expected,
                analysis.samples,
                analysis.verdict,
                analysis.verdict_reason,
                debug_preview,
            ]
        )

    parts = [
        "# 2-lane ILA Matrix Analysis",
        "",
        "This report is generated offline from Vivado ILA CSV files. It does not program FPGA hardware.",
        "",
        "## Summary",
        "",
        md_table(["csv", "trigger", "expected", "samples", "verdict", "reason", "b_debug_classes"], summary_rows),
    ]

    for analysis in analyses:
        parts.extend(
            [
                "",
                f"## {Path(analysis.csv_path).name}",
                "",
                f"- CSV: `{analysis.csv_path}`",
                f"- Summary: `{analysis.summary_path or ''}`",
                f"- B debug first/last: `{analysis.b_debug_first}` / `{analysis.b_debug_last}`",
                f"- B debug unique values: `{analysis.b_debug_unique_count}`",
                "",
                "### B Debug Classes",
                "",
                md_table(
                    ["decoded_class", "samples"],
                    [[key, value] for key, value in analysis.b_debug_class_counts.items()],
                ),
                "",
                "### B Debug Top Values",
                "",
                "\n".join(f"- `{entry}`" for entry in analysis.b_debug_top_values) or "-",
                "",
                "### Main Links",
                "",
            ]
        )
        link_rows = []
        for name in (
            "A_TO_B_LANE0",
            "A_TO_B_LANE1",
            "A_TO_B_CROSS_0_TO_1",
            "A_TO_B_CROSS_1_TO_0",
            "B_TO_A_LANE0",
            "B_TO_A_LANE1",
            "B_TO_A_CROSS_0_TO_1",
            "B_TO_A_CROSS_1_TO_0",
        ):
            link = analysis.links.get(name)
            if not link:
                continue
            delay_preview = ",".join(str(v) for v in link.paired_delays_samples[:6])
            link_rows.append(
                [
                    name,
                    link.tx_pulses,
                    link.rx_pulses,
                    link.tx_edges,
                    link.rx_edges,
                    link.first_delay_samples,
                    link.near_rx_pulses,
                    link.first_near_delay_samples,
                    delay_preview,
                    link.verdict,
                ]
            )
        parts.append(
            md_table(
                [
                    "link",
                    "tx_pulses",
                    "rx_pulses",
                    "tx_edges",
                    "rx_edges",
                    "first_delay",
                    "near_rx_pulses",
                    "first_near_delay",
                    "paired_delays",
                    "verdict",
                ],
                link_rows,
            )
        )
        parts.extend(["", "### Signal Metrics", ""])
        signal_rows = []
        for key in ("a_tx0", "a_tx1", "b_rx0", "b_rx1", "b_tx0", "b_tx1", "a_rx0", "a_rx1"):
            metric = analysis.signals.get(key)
            if not metric:
                continue
            signal_rows.append(
                [
                    key,
                    metric.polarity,
                    metric.edges,
                    metric.pulse_count,
                    metric.active_samples,
                    metric.active_fraction,
                    metric.first_active,
                    metric.last_active,
                    metric.median_width,
                    metric.stuck_active,
                    metric.has_pulse_activity,
                ]
            )
        parts.append(
            md_table(
                [
                    "signal",
                    "polarity",
                    "edges",
                    "pulses",
                    "active_samples",
                    "active_fraction",
                    "first",
                    "last",
                    "median_width",
                    "stuck",
                    "pulse_activity",
                ],
                signal_rows,
            )
        )
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="*", help="ILA CSV file(s). Defaults to latest reports/ila_2lane_prearmed_*.csv.")
    parser.add_argument("--glob", help="Optional glob relative to repo root, for example 'reports/ila_2lane_prearmed_*.csv'.")
    parser.add_argument("--limit", type=int, default=20, help="Limit default latest-file selection.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    parser.add_argument("--out", type=Path, help="Write output to this file.")
    args = parser.parse_args()

    csv_paths = expand_inputs(args.csv, args.glob, args.limit)
    analyses = [analyze_capture(path) for path in csv_paths]
    output = (
        json.dumps([to_jsonable(analysis) for analysis in analyses], indent=2, ensure_ascii=False)
        if args.json
        else render_markdown(analyses)
    )

    if args.out:
        out_path = args.out if args.out.is_absolute() else ROOT / args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
