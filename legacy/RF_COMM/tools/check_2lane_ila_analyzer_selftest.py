#!/usr/bin/env python3
"""Self-test the 2-lane ILA CSV analyzer without hardware.

The synthetic cases verify that local/near-end receiver echo is reported but is
not accepted as proof of the required far-end A<->B physical path.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from analyze_2lane_ila_csv import analyze_capture, to_jsonable
from classify_2lane_physical_matrix import classify_one


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CASE_DIR = REPORTS / "ila_analyzer_selftest_current"


HEADER = [
    "Sample in Buffer",
    "Sample in Window",
    "TRIGGER",
    "design_shiboqi_i/ir_array_top_axi_0_ir_tx_out[1:0]",
    "design_shiboqi_i/ir_rx_in_0_1[1:0]",
    "design_shiboqi_i/ir_array_top_axi_0_ir_sd[1:0]",
    "design_shiboqi_i/ir_array_top_axi_0_ir_mode_out[1:0]",
    "design_shiboqi_i/ir_loopback_b0_ir_tx_out[1:0]",
    "design_shiboqi_i/loop_rx_b0_1[1:0]",
    "design_shiboqi_i/ir_loopback_b0_ir_sd[1:0]",
    "design_shiboqi_i/ir_loopback_b0_ir_mode_out[1:0]",
    "design_shiboqi_i/ir_loopback_b0_debug_status[31:0]",
]

RADIX = [
    "Radix - UNSIGNED",
    "UNSIGNED",
    "UNSIGNED",
    "HEX",
    "HEX",
    "HEX",
    "HEX",
    "HEX",
    "HEX",
    "HEX",
    "HEX",
    "HEX",
]


@dataclass(frozen=True)
class CaseResult:
    case: str
    trigger_mode: str
    expected: str
    expected_capture_verdict: str
    actual_capture_verdict: str
    expected_classification: str
    actual_classification: str
    near_rx_pulses: int
    cross_link_verdict: str
    status: str
    evidence: str


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT)).replace("\\", "/")


def pulse_starts() -> list[int]:
    return [10, 22, 34, 46]


def set_tx(values: list[int], lane: int, starts: list[int], width: int = 2) -> None:
    mask = 1 << lane
    for start in starts:
        for idx in range(start, min(start + width, len(values))):
            values[idx] |= mask


def set_rx_active_low(values: list[int], lane: int, starts: list[int], delay: int, width: int = 2) -> None:
    mask = ~(1 << lane)
    for start in starts:
        for idx in range(start + delay, min(start + delay + width, len(values))):
            values[idx] &= mask


def write_case(
    name: str,
    trigger_mode: str,
    *,
    tx_signal: str,
    tx_lane: int,
    far_rx_signal: str | None,
    far_rx_lane: int | None,
    near_echo: bool,
    cross_far_rx_lane: int | None = None,
) -> Path:
    samples = 64
    a_tx = [0] * samples
    a_rx = [3] * samples
    a_sd = [0] * samples
    a_mode = [3] * samples
    b_tx = [0] * samples
    b_rx = [3] * samples
    b_sd = [0] * samples
    b_mode = [3] * samples
    starts = pulse_starts()

    tx_values = a_tx if tx_signal == "a_tx" else b_tx
    set_tx(tx_values, tx_lane, starts)

    if near_echo:
        near_values = a_rx if tx_signal == "a_tx" else b_rx
        set_rx_active_low(near_values, tx_lane, starts, delay=1)

    if far_rx_signal is not None and far_rx_lane is not None:
        far_values = a_rx if far_rx_signal == "a_rx" else b_rx
        set_rx_active_low(far_values, far_rx_lane, starts, delay=3)

    if cross_far_rx_lane is not None:
        far_values = b_rx if tx_signal == "a_tx" else a_rx
        set_rx_active_low(far_values, cross_far_rx_lane, starts, delay=3)

    path = CASE_DIR / f"{name}.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        writer.writerow(RADIX)
        for idx in range(samples):
            writer.writerow(
                [
                    idx,
                    idx,
                    1 if idx == starts[0] else 0,
                    f"{a_tx[idx]:x}",
                    f"{a_rx[idx]:x}",
                    f"{a_sd[idx]:x}",
                    f"{a_mode[idx]:x}",
                    f"{b_tx[idx]:x}",
                    f"{b_rx[idx]:x}",
                    f"{b_sd[idx]:x}",
                    f"{b_mode[idx]:x}",
                    "ec000000",
                ]
            )

    path.with_suffix(".summary.txt").write_text(f"TRIGGER_MODE={trigger_mode}\n", encoding="utf-8")
    return path


def build_cases() -> dict[str, tuple[Path, str, str, str, str]]:
    CASE_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "a_to_b_lane0_far_pass": (
            write_case(
                "a_to_b_lane0_far_pass",
                "a_tx_lane0",
                tx_signal="a_tx",
                tx_lane=0,
                far_rx_signal="b_rx",
                far_rx_lane=0,
                near_echo=True,
            ),
            "A_TO_B_LANE0",
            "PASS_EXPECTED_RAW",
            "PASS_PHYSICAL_RAW_PULSE",
            "",
        ),
        "b_to_a_lane0_near_echo_only": (
            write_case(
                "b_to_a_lane0_near_echo_only",
                "b2a_rx_lane0",
                tx_signal="b_tx",
                tx_lane=0,
                far_rx_signal=None,
                far_rx_lane=None,
                near_echo=True,
            ),
            "B_TO_A_LANE0",
            "FAIL_EXPECTED_RAW",
            "FAIL_PHYSICAL_RX_MISSING",
            "",
        ),
        "a_to_b_lane1_cross_only": (
            write_case(
                "a_to_b_lane1_cross_only",
                "a_tx_lane1",
                tx_signal="a_tx",
                tx_lane=1,
                far_rx_signal=None,
                far_rx_lane=None,
                near_echo=True,
                cross_far_rx_lane=0,
            ),
            "A_TO_B_LANE1",
            "FAIL_EXPECTED_RAW",
            "FAIL_PHYSICAL_RX_MISSING",
            "A_TO_B_CROSS_1_TO_0",
        ),
        "b_to_a_lane1_far_pass": (
            write_case(
                "b_to_a_lane1_far_pass",
                "b2a_rx_lane1",
                tx_signal="b_tx",
                tx_lane=1,
                far_rx_signal="a_rx",
                far_rx_lane=1,
                near_echo=True,
            ),
            "B_TO_A_LANE1",
            "PASS_EXPECTED_RAW",
            "PASS_PHYSICAL_RAW_PULSE",
            "",
        ),
    }


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    rows: list[CaseResult] = []
    analyses = []

    for case, (path, expected, expected_capture, expected_class, cross_name) in cases.items():
        analysis = analyze_capture(path)
        analyses.append(to_jsonable(analysis))
        classified = classify_one(to_jsonable(analysis))
        link = analysis.links[expected]
        cross_verdict = analysis.links[cross_name].verdict if cross_name else ""
        checks = [
            analysis.expected == expected,
            analysis.verdict == expected_capture,
            classified["classification"] == expected_class,
        ]
        if "near_echo" in case or expected_class == "PASS_PHYSICAL_RAW_PULSE":
            checks.append(int(classified.get("near_rx_pulses") or 0) > 0)
        if cross_name:
            checks.append(cross_verdict.startswith("PASS_RAW_PULSE"))
            checks.append(not analysis.links[expected].verdict.startswith("PASS_RAW_PULSE"))

        rows.append(
            CaseResult(
                case=case,
                trigger_mode=analysis.trigger_mode,
                expected=analysis.expected,
                expected_capture_verdict=expected_capture,
                actual_capture_verdict=analysis.verdict,
                expected_classification=expected_class,
                actual_classification=str(classified["classification"]),
                near_rx_pulses=int(classified.get("near_rx_pulses") or 0),
                cross_link_verdict=cross_verdict,
                status="PASS" if all(checks) else "FAIL",
                evidence=rel(path),
            )
        )

    failures = [row for row in rows if row.status != "PASS"]
    overall = "PASS" if not failures else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")

    json_path = REPORTS / "ila_analyzer_selftest_current.json"
    md_path = REPORTS / "ila_analyzer_selftest_current.md"
    csv_path = REPORTS / "ila_analyzer_selftest_current.csv"
    analysis_json = CASE_DIR / "synthetic_analysis.json"
    analysis_json.write_text(json.dumps(analyses, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    payload = {
        "generated": generated,
        "overall": overall,
        "cases": len(rows),
        "failures": len(failures),
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "case_dir": rel(CASE_DIR),
        "synthetic_analysis": rel(analysis_json),
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md_lines = [
        "# 2-Lane ILA Analyzer Self-Test",
        "",
        f"Generated: {generated}",
        "",
        f"- Overall: `{overall}`",
        f"- Cases: `{len(rows)}`",
        f"- Failures: `{len(failures)}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "| case | status | expected | capture | classification | near_rx_pulses | cross_link | evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        md_lines.append(
            f"| {row.case} | {row.status} | {row.expected} | {row.actual_capture_verdict} | "
            f"{row.actual_classification} | {row.near_rx_pulses} | {row.cross_link_verdict} | {row.evidence} |"
        )
    md_lines.extend(
        [
            "",
            "```text",
            f"RF_COMM_2LANE_ILA_ANALYZER_SELFTEST overall={overall} cases={len(rows)} failures={len(failures)}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "```",
        ]
    )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_2LANE_ILA_ANALYZER_SELFTEST overall={overall} cases={len(rows)} failures={len(failures)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
