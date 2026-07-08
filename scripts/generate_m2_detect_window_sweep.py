#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "evidence" / "generated"


def pulse_detected(detect_start: int, detect_end: int, pulse_start: int, pulse_width: int) -> bool:
    pulse_end = pulse_start + pulse_width - 1
    return not (pulse_end < detect_start or pulse_start > detect_end)


def evaluate_case(case: dict) -> dict:
    required = case["required_pulses"]
    missed = [
        pulse
        for pulse in required
        if not pulse_detected(case["detect_start"], case["detect_end"], pulse["offset"], pulse["width"])
    ]
    passes_required = not missed
    expected_pass = case["expected_required_pass"]
    return {
        **case,
        "missed_required_pulses": missed,
        "passes_required": passes_required,
        "verdict": "PASS" if passes_required == expected_pass else "FAIL",
    }


def pulse_range(start: int, end: int, width: int = 1) -> list[dict]:
    return [{"offset": offset, "width": width} for offset in range(start, end + 1)]


def main() -> int:
    cases = [
        {
            "name": "G1_A_DETECT_0_5",
            "cnt_chip_max": 7,
            "detect_start": 0,
            "detect_end": 5,
            "required_pulses": pulse_range(0, 5),
            "expected_required_pass": True,
            "reason": "G1 lane0 A profile window from imported freeze evidence.",
        },
        {
            "name": "G1_B_DETECT_0_7",
            "cnt_chip_max": 7,
            "detect_start": 0,
            "detect_end": 7,
            "required_pulses": pulse_range(0, 7),
            "expected_required_pass": True,
            "reason": "G1 lane0 B profile window covers the complete 8-cycle chip.",
        },
        {
            "name": "TFDU_MODEL_DETECT_14_30",
            "cnt_chip_max": 31,
            "detect_start": 14,
            "detect_end": 30,
            "required_pulses": pulse_range(14, 30),
            "expected_required_pass": True,
            "reason": "M2 TFDU behavior-model integration bench uses the delayed optical RX window.",
        },
        {
            "name": "NEGATIVE_NARROW_WINDOW_3_4",
            "cnt_chip_max": 7,
            "detect_start": 3,
            "detect_end": 4,
            "required_pulses": pulse_range(0, 5),
            "expected_required_pass": False,
            "reason": "Reference negative case proves the sweep detects missed offsets.",
        },
    ]

    results = [evaluate_case(case) for case in cases]
    positive_cases_pass = all(
        item["passes_required"] for item in results if item["expected_required_pass"]
    )
    negative_cases_detected = all(
        not item["passes_required"] for item in results if not item["expected_required_pass"]
    )
    overall_pass = positive_cases_pass and negative_cases_detected and all(
        item["verdict"] == "PASS" for item in results
    )

    OUTDIR.mkdir(parents=True, exist_ok=True)
    json_out = {
        "marker": "M2_DETECT_WINDOW_SWEEP_REPORT",
        "status": "PASS" if overall_pass else "FAIL",
        "model": "A pulse is detected when rx_pulse_active overlaps DETECT_START_CYCLES..DETECT_END_CYCLES.",
        "results": results,
    }
    (OUTDIR / "m2_detect_window_sweep.json").write_text(
        json.dumps(json_out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# M2 Detect Window Sweep",
        "",
        "M2_DETECT_WINDOW_SWEEP_REPORT=1",
        f"M2_DETECT_WINDOW_SWEEP_POSITIVE_CASES_PASS={1 if positive_cases_pass else 0}",
        f"M2_DETECT_WINDOW_SWEEP_NEGATIVE_CASES_DETECTED={1 if negative_cases_detected else 0}",
        f"M2_DETECT_WINDOW_SWEEP={'PASS' if overall_pass else 'FAIL'}",
        "",
        "| Case | CNT_CHIP_MAX | Window | Required offsets | Missed required | Expected | Verdict |",
        "|---|---:|---|---|---|---|---|",
    ]
    for item in results:
        required_offsets = ",".join(str(pulse["offset"]) for pulse in item["required_pulses"])
        missed_offsets = ",".join(str(pulse["offset"]) for pulse in item["missed_required_pulses"]) or "none"
        expected = "pass" if item["expected_required_pass"] else "miss"
        lines.append(
            f"| {item['name']} | {item['cnt_chip_max']} | "
            f"{item['detect_start']}..{item['detect_end']} | {required_offsets} | "
            f"{missed_offsets} | {expected} | {item['verdict']} |"
        )
    lines += [
        "",
        "This is an offline reference sweep for the abstract pulse-stream decoder. It does not claim hardware timing acceptance or replace SystemVerilog simulation.",
        "",
    ]
    (OUTDIR / "m2_detect_window_sweep.md").write_text("\n".join(lines), encoding="utf-8")

    print("M2_DETECT_WINDOW_SWEEP_REPORT=1")
    print(f"M2_DETECT_WINDOW_SWEEP_POSITIVE_CASES_PASS={1 if positive_cases_pass else 0}")
    print(f"M2_DETECT_WINDOW_SWEEP_NEGATIVE_CASES_DETECTED={1 if negative_cases_detected else 0}")
    print(f"M2_DETECT_WINDOW_SWEEP={'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
