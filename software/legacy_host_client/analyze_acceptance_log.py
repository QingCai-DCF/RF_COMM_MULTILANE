#!/usr/bin/env python3
"""Analyze RF_COMM host-client CSV logs and enforce evidence thresholds."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


KEY_VALUE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=('[^']*'|[^ ]+)")
RX_LEN_RE = re.compile(r"\blen=(\d+)\b")


@dataclass
class LogAnalysis:
    path: Path
    first_time: float | None = None
    last_time: float | None = None
    row_count: int = 0
    ack_frames: int = 0
    error_frames: int = 0
    status_frames: int = 0
    rx_data_frames: int = 0
    rx_data_bytes_from_rows: int = 0
    markers: set[str] = field(default_factory=set)
    summary: dict[str, str] = field(default_factory=dict)
    sent_summary: dict[str, str] = field(default_factory=dict)
    acceptance_fail_reasons: list[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        if self.first_time is None or self.last_time is None:
            return 0.0
        return max(0.0, self.last_time - self.first_time)

    def summary_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.summary.get(key, str(default)), 0)
        except ValueError:
            return default

    def summary_float(self, key: str, default: float = 0.0) -> float:
        try:
            return float(self.summary.get(key, str(default)))
        except ValueError:
            return default

    def effective_error_count(self) -> int:
        return max(self.error_frames, self.summary_int("errors"))

    def effective_rx_data_frames(self) -> int:
        return max(self.rx_data_frames, self.summary_int("rx_data"))

    def effective_status_frames(self) -> int:
        return max(self.status_frames, self.summary_int("status"))


def parse_key_values(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in KEY_VALUE_RE.finditer(text):
        value = match.group(2)
        if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            value = value[1:-1]
        fields[match.group(1)] = value
    return fields


def analyze_csv(path: Path) -> LogAnalysis:
    analysis = LogAnalysis(path=path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"time_s", "type", "seq", "payload_len", "detail"}
        if set(reader.fieldnames or []) != required:
            raise ValueError(f"unexpected CSV header: {reader.fieldnames!r}")

        for row in reader:
            analysis.row_count += 1
            row_type = row["type"]
            analysis.markers.add(row_type)
            try:
                time_s = float(row["time_s"])
            except ValueError:
                time_s = None
            if time_s is not None:
                analysis.first_time = time_s if analysis.first_time is None else min(analysis.first_time, time_s)
                analysis.last_time = time_s if analysis.last_time is None else max(analysis.last_time, time_s)

            detail = row["detail"]
            if row_type == "ACK":
                analysis.ack_frames += 1
            elif row_type == "ERROR":
                analysis.error_frames += 1
            elif row_type == "STATUS_RSP":
                analysis.status_frames += 1
            elif row_type == "RX_DATA":
                analysis.rx_data_frames += 1
                length_match = RX_LEN_RE.search(detail)
                if length_match:
                    analysis.rx_data_bytes_from_rows += int(length_match.group(1))
            elif row_type == "SUMMARY":
                analysis.summary = parse_key_values(detail)
            elif row_type == "SENT_SUMMARY":
                analysis.sent_summary = parse_key_values(detail)
            elif row_type == "ACCEPTANCE_FAIL_REASON":
                analysis.acceptance_fail_reasons.append(detail)
    return analysis


def evaluate_log(analysis: LogAnalysis, *,
                 require_pass: bool,
                 min_duration: float,
                 max_errors: int,
                 min_status_frames: int,
                 min_rx_frames: int,
                 min_tx_mbps: float | None,
                 min_rx_mbps: float | None) -> list[str]:
    failures: list[str] = []
    if analysis.row_count == 0:
        failures.append("log has no data rows")
    if require_pass and "ACCEPTANCE_PASS" not in analysis.markers:
        failures.append("ACCEPTANCE_PASS marker missing")
    if "ACCEPTANCE_FAIL" in analysis.markers:
        reasons = ";".join(analysis.acceptance_fail_reasons) or "unknown"
        failures.append(f"ACCEPTANCE_FAIL marker present: {reasons}")
    if not analysis.summary:
        failures.append("SUMMARY marker missing")
    if analysis.duration < min_duration:
        failures.append(f"duration_s={analysis.duration:.3f}<min_duration_s={min_duration:.3f}")
    if analysis.effective_error_count() > max_errors:
        failures.append(f"errors={analysis.effective_error_count()}>max_errors={max_errors}")
    if analysis.summary_int("payload_mismatch") > 0:
        failures.append(f"payload_mismatch={analysis.summary_int('payload_mismatch')}>0")
    if analysis.effective_status_frames() < min_status_frames:
        failures.append(
            f"status_frames={analysis.effective_status_frames()}<min_status_frames={min_status_frames}"
        )
    if analysis.effective_rx_data_frames() < min_rx_frames:
        failures.append(f"rx_data_frames={analysis.effective_rx_data_frames()}<min_rx_frames={min_rx_frames}")
    if min_tx_mbps is not None and analysis.summary_float("tx_mbps") < min_tx_mbps:
        failures.append(f"tx_mbps={analysis.summary_float('tx_mbps'):.6f}<min_tx_mbps={min_tx_mbps:.6f}")
    if min_rx_mbps is not None and analysis.summary_float("rx_mbps") < min_rx_mbps:
        failures.append(f"rx_mbps={analysis.summary_float('rx_mbps'):.6f}<min_rx_mbps={min_rx_mbps:.6f}")
    return failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_log", type=Path)
    parser.add_argument("--require-pass", action="store_true")
    parser.add_argument("--min-duration", type=float, default=0.0)
    parser.add_argument("--max-errors", type=int, default=0)
    parser.add_argument("--min-status-frames", type=int, default=0)
    parser.add_argument("--min-rx-frames", type=int, default=0)
    parser.add_argument("--min-tx-mbps", type=float)
    parser.add_argument("--min-rx-mbps", type=float)
    args = parser.parse_args(argv)

    analysis = analyze_csv(args.csv_log)
    failures = evaluate_log(
        analysis,
        require_pass=args.require_pass,
        min_duration=args.min_duration,
        max_errors=args.max_errors,
        min_status_frames=args.min_status_frames,
        min_rx_frames=args.min_rx_frames,
        min_tx_mbps=args.min_tx_mbps,
        min_rx_mbps=args.min_rx_mbps,
    )

    print(
        "log_summary "
        f"path={analysis.path} rows={analysis.row_count} duration_s={analysis.duration:.3f} "
        f"ack={analysis.ack_frames} errors={analysis.effective_error_count()} "
        f"status={analysis.effective_status_frames()} rx_data={analysis.effective_rx_data_frames()} "
        f"rx_data_bytes_rows={analysis.rx_data_bytes_from_rows} "
        f"payload_mismatch={analysis.summary_int('payload_mismatch')} "
        f"app_tx_packets={analysis.summary_int('app_tx_packets')} "
        f"app_tx_bytes={analysis.summary_int('app_tx_bytes')} "
        f"app_tx_fragments={analysis.summary_int('app_tx_fragments')} "
        f"tx_mbps={analysis.summary_float('tx_mbps'):.6f} "
        f"rx_mbps={analysis.summary_float('rx_mbps'):.6f}"
    )

    if failures:
        for failure in failures:
            print(f"log_acceptance_fail {failure}")
        print("log_acceptance FAIL")
        return 1
    print("log_acceptance PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
