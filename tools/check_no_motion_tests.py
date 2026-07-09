#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p5_lib import FAIL, GENERATED, PASS, ROOT, load_json, write_markdown


FORBIDDEN_PASS_PHRASES = [
    "ROTATION_ACCEPTANCE: PASS",
    "RPM_ACCEPTANCE: PASS",
    "600_RPM: PASS",
    "MOTION_ACCEPTANCE: PASS",
    "ALIGNMENT_SWEEP: PASS",
]


def _scan_text(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [phrase for phrase in FORBIDDEN_PASS_PHRASES if phrase in text]


def check() -> dict:
    profiles = sorted((ROOT / "profiles" / "p5").glob("*.json"))
    failures = []
    for profile in profiles:
        data = load_json(profile)
        if data.get("hardware_movement_allowed") is not False:
            failures.append(f"{profile}: hardware_movement_allowed is not false")
        if data.get("rotation_enabled") is not False:
            failures.append(f"{profile}: rotation_enabled is not false")
    for relpath in [
        "PROJECT_STATUS.md",
        "docs/PROJECT_STATUS.md",
        "README.md",
        "evidence/generated/p5_2lane_protocol_stabilization_summary.md",
    ]:
        hits = _scan_text(ROOT / relpath)
        failures.extend(f"{relpath}: forbidden motion PASS phrase `{hit}`" for hit in hits)

    result = PASS if not failures else FAIL
    lines = [
        f"NO_MOTION_GATE: {result}",
        "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
        "HARDWARE_MOVEMENT_ALLOWED: false",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Checks",
        "",
        "- Rotation, rpm, sweep, alignment, misalignment, and manual dropout tests are deferred.",
        "- Stationary soak must not be described as rotation acceptance.",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(
        GENERATED / "p5_no_motion_tests_summary.md",
        "P5 No Motion Tests Summary",
        result,
        "Motion and rotation acceptance are deferred because hardware movement is unavailable" if result == PASS else "Motion gate found forbidden pass claims",
        lines,
    )
    return {
        "NO_MOTION_GATE": result,
        "ROTATION_ACCEPTANCE": "DEFERRED_NO_HARDWARE_MOVEMENT",
        "failures": failures,
        "summary": "evidence/generated/p5_no_motion_tests_summary.md",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check P5 does not claim or run rotation/motion acceptance.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = check()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"NO_MOTION_GATE: {payload['NO_MOTION_GATE']}")
        print("ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    return 0 if payload["NO_MOTION_GATE"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
