#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json

from p5_lib import FAIL, GENERATED, PASS, ROOT, load_json, write_markdown


def _mask_int(value) -> int | None:
    try:
        return int(value, 0) if isinstance(value, str) else int(value)
    except Exception:
        return None


def _pinmap_lanes() -> set[int]:
    path = ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv"
    lanes: set[int] = set()
    if not path.exists():
        return lanes
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                lanes.add(int(row.get("lane", "")))
            except ValueError:
                pass
    return lanes


def check() -> dict:
    failures = []
    profiles = sorted((ROOT / "profiles" / "p5").glob("*.json"))
    for profile in profiles:
        data = load_json(profile)
        if data.get("available_lanes") != 2:
            failures.append(f"{profile}: available_lanes is not 2")
        for key in ["lane_mask", "rx_lane_mask", "ack_lane_mask", "max_lane_mask"]:
            value = _mask_int(data.get(key, "0x0"))
            if value is None:
                failures.append(f"{profile}: {key} is not parseable")
            elif value > 0x3:
                failures.append(f"{profile}: {key}={data.get(key)} exceeds 0x3")
    lanes = _pinmap_lanes()
    if lanes != {0, 1}:
        failures.append(f"active pinmap lanes are {sorted(lanes)}, expected [0, 1]")

    result = PASS if not failures else FAIL
    lines = [
        f"TWO_LANE_SCOPE_GATE: {result}",
        "AVAILABLE_LANES: 2",
        "MAX_LANE_MASK: 0x3",
        "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Checks",
        "",
        f"- active pinmap lanes: `{sorted(lanes)}`",
        "- allowed lane masks: 0x1, 0x2, 0x3",
        "- forbidden lane masks: 0x4..0xff",
        "- P5 profiles must not describe 4-lane or 8-lane acceptance.",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(
        GENERATED / "p5_2lane_scope_summary.md",
        "P5 Two-Lane Scope Summary",
        result,
        "P5 profiles and active pinmap are constrained to lanes 0 and 1" if result == PASS else "2-lane scope gate failed",
        lines,
    )
    return {
        "TWO_LANE_SCOPE_GATE": result,
        "AVAILABLE_LANES": 2,
        "EIGHT_LANE_ACCEPTANCE": "DEFERRED_ONLY_2_LANES_AVAILABLE",
        "failures": failures,
        "summary": "evidence/generated/p5_2lane_scope_summary.md",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check P5 stays inside the current two-lane hardware scope.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = check()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"TWO_LANE_SCOPE_GATE: {payload['TWO_LANE_SCOPE_GATE']}")
        print("AVAILABLE_LANES: 2")
        print("EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE")
    return 0 if payload["TWO_LANE_SCOPE_GATE"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
