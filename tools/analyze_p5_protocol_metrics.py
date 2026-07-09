#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from p5_lib import GENERATED, P5_DIR, PASS, PASS_WITH_NOTES, SKIP, load_json, write_csv, write_json, write_markdown


NUMERIC_FIELDS = [
    "frames_sent",
    "frames_rx_good",
    "ack_seen",
    "crc_bad",
    "payload_mismatch",
    "retry_count",
    "retry_exhausted",
    "tx_fail",
    "txd_high_total_cycles",
    "txd_high_consecutive_max_cycles",
    "duty_violation_count",
]

COUNTER_KEYS = {
    "SENT_FRAMES",
    "A_SENT_FRAMES",
    "A_SENT_FRAMES_PER_LANE",
    "RX_GOOD",
    "B_RX_GOOD",
    "TOTAL_RX_GOOD",
    "LANE0_RX_GOOD",
    "LANE1_RX_GOOD",
    "A_ACK_SEEN",
    "B_ACK_SENT",
    "LANE0_ACK_SENT",
    "LANE1_ACK_SENT",
    "CRC_BAD",
    "PAYLOAD_MISMATCH",
    "TX_RETRY_EXHAUSTED",
    "TX_FAIL",
    "TXD_HIGH_TOTAL_CYCLES",
    "TXD_HIGH_CONSECUTIVE_MAX_CYCLES",
    "DUTY_WINDOW_VIOLATION",
}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _sum_fields(data: dict[str, Any], *names: str) -> int:
    return sum(_as_int(data.get(name)) for name in names)


def _counter_from_json(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": path.as_posix(),
        "frames_sent": _as_int(data.get("SENT_FRAMES") or data.get("A_SENT_FRAMES") or data.get("A_SENT_FRAMES_PER_LANE")),
        "frames_rx_good": _as_int(data.get("RX_GOOD") or data.get("TOTAL_RX_GOOD") or _sum_fields(data, "LANE0_RX_GOOD", "LANE1_RX_GOOD")),
        "ack_seen": _as_int(data.get("A_ACK_SEEN") or data.get("ACK_SEEN") or _sum_fields(data, "LANE0_ACK_SENT", "LANE1_ACK_SENT")),
        "crc_bad": _as_int(data.get("CRC_BAD")),
        "payload_mismatch": _as_int(data.get("PAYLOAD_MISMATCH")),
        "retry_count": _as_int(data.get("RETRY_COUNT")),
        "retry_exhausted": _as_int(data.get("TX_RETRY_EXHAUSTED")),
        "tx_fail": _as_int(data.get("TX_FAIL")),
        "txd_high_total_cycles": _as_int(data.get("TXD_HIGH_TOTAL_CYCLES")),
        "txd_high_consecutive_max_cycles": _as_int(data.get("TXD_HIGH_CONSECUTIVE_MAX_CYCLES")),
        "duty_violation_count": _as_int(data.get("DUTY_WINDOW_VIOLATION")),
        "latency_min_cycles": data.get("LATENCY_MIN_CYCLES", "SKIP_COUNTER_NOT_AVAILABLE"),
        "latency_avg_cycles": data.get("LATENCY_AVG_CYCLES", "SKIP_COUNTER_NOT_AVAILABLE"),
        "latency_max_cycles": data.get("LATENCY_MAX_CYCLES", "SKIP_COUNTER_NOT_AVAILABLE"),
        "throughput": data.get("THROUGHPUT", "SKIP_COUNTER_NOT_AVAILABLE"),
    }


def analyze() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted(P5_DIR.rglob("*.json")):
        if path.name != "readback.json":
            continue
        if path.name == "p5_pending_hw.json":
            continue
        if path.relative_to(P5_DIR).parts[:1] == ("authorization",):
            continue
        data = load_json(path)
        if isinstance(data, dict):
            executed = data.get("hardware_actions_executed") is True or data.get("HARDWARE_ACTIONS_EXECUTED") is True
            no_hw = data.get("NO_HARDWARE_ACTIONS_EXECUTED") is True
            if not executed or no_hw:
                continue
            if not any(key in data for key in COUNTER_KEYS):
                continue
            rows.append(_counter_from_json(path, data))

    totals = {field: sum(_as_int(row.get(field)) for row in rows) for field in NUMERIC_FIELDS}
    if rows:
        result = PASS_WITH_NOTES if any(row.get("latency_min_cycles") == "SKIP_COUNTER_NOT_AVAILABLE" for row in rows) else PASS
        reason = "P5 protocol metrics extracted from P5 hardware evidence"
    else:
        result = SKIP
        reason = "SKIP_COUNTER_NOT_AVAILABLE: no fresh P5 hardware metric files exist yet"

    csv_fields = [
        "source",
        *NUMERIC_FIELDS,
        "latency_min_cycles",
        "latency_avg_cycles",
        "latency_max_cycles",
        "throughput",
    ]
    write_csv(GENERATED / "p5_protocol_metrics.csv", csv_fields, rows)
    payload = {
        "P5_PROTOCOL_METRICS": result,
        "reason": reason,
        "totals": totals,
        "row_count": len(rows),
        "csv": "evidence/generated/p5_protocol_metrics.csv",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(GENERATED / "p5_protocol_metrics_summary.json", payload)
    lines = [
        f"P5_PROTOCOL_METRICS: {result}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        f"METRIC_SOURCE_COUNT: {len(rows)}",
        f"LATENCY_COUNTER_STATUS: {'SKIP_COUNTER_NOT_AVAILABLE' if not rows else 'SEE_JSON'}",
        f"THROUGHPUT_COUNTER_STATUS: {'SKIP_COUNTER_NOT_AVAILABLE' if not rows else 'SEE_JSON'}",
        "",
        "## Totals",
        "",
        *(f"- {field}: {value}" for field, value in totals.items()),
        "",
        "## Boundary",
        "",
        "- This script only summarizes fresh P5 evidence under `evidence/hardware/p5/`.",
        "- P4 evidence is not promoted to P5 protocol metric PASS.",
    ]
    write_markdown(GENERATED / "p5_protocol_metrics_summary.md", "P5 Protocol Metrics Summary", result, reason, lines)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze P5 protocol metrics from fresh P5 evidence.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = analyze()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P5_PROTOCOL_METRICS: {payload['P5_PROTOCOL_METRICS']}")
        print(payload["reason"])
    return 0 if payload["P5_PROTOCOL_METRICS"] in {PASS, PASS_WITH_NOTES, SKIP} else 1


if __name__ == "__main__":
    raise SystemExit(main())
