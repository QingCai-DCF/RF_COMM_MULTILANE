#!/usr/bin/env python3
"""Compare the deterministic reduced P8C RTL trace with the Python model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.p8c_tfdu_safety_reference import ExactDutyAccountant, SafetyConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_log", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    records = []
    for line in args.trace_log.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("P8C_TRACE,"):
            continue
        values = [int(value) for value in line.split(",")[1:]]
        if len(values) != 9:
            raise ValueError(f"malformed trace line: {line}")
        records.append(values)
    derived = SafetyConfig.load().derive(
        clock_hz=1_000_000, startup_us=1, window_us=100, max_high_us=1
    )
    model = ExactDutyAccountant(derived)
    first_mismatch = None
    for values in records:
        cycle, charge, target_request, invalidate, rolling, valid, remaining, hard, hard_count = values
        expected = model.step(
            charge=bool(charge), target_request=bool(target_request), invalidate=bool(invalidate)
        )
        expected_tuple = (
            int(expected["rolling"]), int(bool(expected["history_valid"])),
            int(expected["cooldown_remaining"]), int(bool(expected["hard_fault"])),
            model.hard_fault_count,
        )
        actual_tuple = (rolling, valid, remaining, hard, hard_count)
        if actual_tuple != expected_tuple:
            first_mismatch = {
                "cycle": cycle,
                "actual": actual_tuple,
                "expected": expected_tuple,
                "raw_record": values,
            }
            break
    summary = {
        "status": "PASS" if records and first_mismatch is None else "FAIL",
        "test_id": "P8C-RTL-PYTHON-CYCLE-TRACE",
        "profile": "P8C_REDUCED_1MHZ_100CYCLE_WINDOW",
        "record_count": len(records),
        "first_mismatch": first_mismatch,
        "random_seed": None,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "HARDWARE_SCOPE_PROMOTED": False,
    }
    encoded = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
