#!/usr/bin/env python3
"""Compute the bounded P10.2 four-module IRED power requirement offline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def model() -> dict[str, object]:
    per_module_peak_a = 0.6
    duty = 0.18
    rows = []
    for simultaneous in (1, 2, 4):
        peak = simultaneous * per_module_peak_a
        rows.append({
            "simultaneous_tx_modules": simultaneous,
            "ired_peak_current_a": peak,
            "ired_long_term_average_at_18pct_a": peak * duty,
            "minimum_effective_capacitance_for_0p1v_1us_f":
                peak * 1e-6 / 0.1,
        })
    return {
        "schema_version": 1,
        "test_id": "P10_2-FOUR-TX-POWER-REQUIREMENT-MODEL",
        "status": "PASS",
        "scope": "OFFLINE_REQUIREMENT_PACKAGE_ONLY",
        "per_module_engineering_peak_a": per_module_peak_a,
        "four_tx_peak_ired_current_a": 2.4,
        "rows": rows,
        "existing_supply_acceptance": "PENDING_MEASUREMENT_NOT_GUESSED",
        "hardware_acceptance": "PENDING_P10_3",
        "no_hardware": True,
        "hardware_actions_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", type=Path)
    args = parser.parse_args()
    result = model()
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.json_summary:
        path = args.json_summary if args.json_summary.is_absolute() else ROOT / args.json_summary
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
