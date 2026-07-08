#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "sim/models/tfdu6102_behavior_model.sv"
OUTDIR = ROOT / "evidence" / "generated"


def read_param(text: str, name: str) -> int:
    match = re.search(rf"parameter\s+(?:int|bit)\s+{name}\s*=\s*([^,\n)]+)", text)
    if not match:
        raise ValueError(f"Missing parameter {name}")
    value = match.group(1).strip()
    if value.startswith("1'b"):
        return int(value[-1])
    return int(value.replace("_", ""))


def midpoint(lo: int, hi: int) -> int:
    return lo + ((hi - lo) // 2)


def bounded_loss_period(loss_permille: int) -> int:
    if loss_permille <= 0:
        return 0
    if loss_permille >= 1000:
        return 1
    return max(1, 1000 // loss_permille)


def should_drop_pulse(count: int, loss_permille: int) -> bool:
    period = bounded_loss_period(loss_permille)
    return period != 0 and count % period == 0


def leading_edge_jitter_ns(count: int, jitter_ns: int) -> int:
    if jitter_ns <= 0:
        return 0
    return jitter_ns if count % 2 else 0


def classify_rx_width(high_ns: int, params: dict[str, int]) -> int:
    if high_ns <= 180:
        return midpoint(params["RX_125_MIN_NS"], params["RX_125_MAX_NS"])
    return midpoint(params["RX_250_MIN_NS"], params["RX_250_MAX_NS"])


def main() -> int:
    text = MODEL.read_text(encoding="utf-8", errors="ignore")
    names = [
        "STARTUP_US",
        "JITTER_NS",
        "PULSE_LOSS_PERMILLE",
        "LONG_HIGH_LIMIT_US",
        "NEAR_END_ECHO",
        "RX_125_MIN_NS",
        "RX_125_MAX_NS",
        "RX_250_MIN_NS",
        "RX_250_MAX_NS",
        "ECHO_DELAY_NS",
        "ECHO_WIDTH_NS",
    ]
    params = {name: read_param(text, name) for name in names}

    width_125 = classify_rx_width(125, params)
    width_250 = classify_rx_width(250, params)
    range_125_pass = params["RX_125_MIN_NS"] <= width_125 <= params["RX_125_MAX_NS"]
    range_250_pass = params["RX_250_MIN_NS"] <= width_250 <= params["RX_250_MAX_NS"]
    jitter_pass = [leading_edge_jitter_ns(i, params["JITTER_NS"]) for i in range(1, 5)] == [
        params["JITTER_NS"],
        0,
        params["JITTER_NS"],
        0,
    ]
    loss_pass = [should_drop_pulse(i, 250) for i in range(1, 9)] == [
        False,
        False,
        False,
        True,
        False,
        False,
        False,
        True,
    ]
    near_echo_pass = params["NEAR_END_ECHO"] == 0 and params["ECHO_DELAY_NS"] > 0 and params["ECHO_WIDTH_NS"] > 0
    long_high_pass = params["LONG_HIGH_LIMIT_US"] == 80 and "optical_enabled = 1'b0" in text
    startup_pass = params["STARTUP_US"] == 500 and "#(STARTUP_US * 1000)" in text
    rx_low_active_pass = "Rxd = 1'b0" in text and "Rxd = 1'b1" in text
    overall_pass = all(
        [
            range_125_pass,
            range_250_pass,
            jitter_pass,
            loss_pass,
            near_echo_pass,
            long_high_pass,
            startup_pass,
            rx_low_active_pass,
        ]
    )

    OUTDIR.mkdir(parents=True, exist_ok=True)
    data = {
        "marker": "M1_TFDU_MODEL_REFERENCE_REPORT",
        "status": "PASS" if overall_pass else "FAIL",
        "parameters": params,
        "reference": {
            "rx_width_for_125ns_txd": width_125,
            "rx_width_for_250ns_txd": width_250,
            "jitter_sequence_counts_1_to_4": [leading_edge_jitter_ns(i, params["JITTER_NS"]) for i in range(1, 5)],
            "loss_250_permille_counts_1_to_8": [should_drop_pulse(i, 250) for i in range(1, 9)],
        },
    }
    (OUTDIR / "m1_tfdu_model_reference.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# M1 TFDU Model Reference",
        "",
        "M1_TFDU_MODEL_REFERENCE_REPORT=1",
        f"M1_MODEL_STARTUP_500US_PASS={1 if startup_pass else 0}",
        f"M1_MODEL_RX_LOW_ACTIVE_PASS={1 if rx_low_active_pass else 0}",
        f"M1_MODEL_125NS_RX_RANGE_PASS={1 if range_125_pass else 0}",
        f"M1_MODEL_250NS_RX_RANGE_PASS={1 if range_250_pass else 0}",
        f"M1_MODEL_JITTER_PATTERN_PASS={1 if jitter_pass else 0}",
        f"M1_MODEL_PULSE_LOSS_PATTERN_PASS={1 if loss_pass else 0}",
        f"M1_MODEL_NEAR_END_ECHO_PASS={1 if near_echo_pass else 0}",
        f"M1_MODEL_LONG_HIGH_DISABLE_PASS={1 if long_high_pass else 0}",
        f"M1_TFDU_MODEL_REFERENCE={'PASS' if overall_pass else 'FAIL'}",
        "",
        "| Item | Value |",
        "|---|---:|",
        f"| 125 ns Txd reference Rxd low width | {width_125} ns |",
        f"| 250 ns Txd reference Rxd low width | {width_250} ns |",
        f"| default leading-edge jitter | {params['JITTER_NS']} ns |",
        f"| default long-high cutoff | {params['LONG_HIGH_LIMIT_US']} us |",
        "",
        "This offline reference checks the TFDU behavior-model contract without claiming SystemVerilog simulation or hardware acceptance.",
        "",
    ]
    (OUTDIR / "m1_tfdu_model_reference.md").write_text("\n".join(lines), encoding="utf-8")

    print("M1_TFDU_MODEL_REFERENCE_REPORT=1")
    print(f"M1_MODEL_STARTUP_500US_PASS={1 if startup_pass else 0}")
    print(f"M1_MODEL_RX_LOW_ACTIVE_PASS={1 if rx_low_active_pass else 0}")
    print(f"M1_MODEL_125NS_RX_RANGE_PASS={1 if range_125_pass else 0}")
    print(f"M1_MODEL_250NS_RX_RANGE_PASS={1 if range_250_pass else 0}")
    print(f"M1_MODEL_JITTER_PATTERN_PASS={1 if jitter_pass else 0}")
    print(f"M1_MODEL_PULSE_LOSS_PATTERN_PASS={1 if loss_pass else 0}")
    print(f"M1_MODEL_NEAR_END_ECHO_PASS={1 if near_echo_pass else 0}")
    print(f"M1_MODEL_LONG_HIGH_DISABLE_PASS={1 if long_high_pass else 0}")
    print(f"M1_TFDU_MODEL_REFERENCE={'PASS' if overall_pass else 'FAIL'}")
    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
