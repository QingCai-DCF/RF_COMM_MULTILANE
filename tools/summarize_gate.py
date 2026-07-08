#!/usr/bin/env python3
import json
from pathlib import Path

from p1_lib import GENERATED


def main():
    path = GENERATED / "offline_gate_summary.json"
    if not path.exists():
        print("RESULT: FAIL")
        print("REASON: offline_gate_summary.json missing")
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"RESULT: {data.get('status', 'UNKNOWN')}")
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    print("HARDWARE_ACCEPTANCE: PENDING_HW")
    for result in data.get("results", []):
        print(f"{result['name']}: {result['result']}")
    return 0 if data.get("status") in {"PASS", "PASS_WITH_SKIPS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
