#!/usr/bin/env python3
from p1_lib import active_profile_check, constraint_checks


if __name__ == "__main__":
    results = [constraint_checks(), active_profile_check()]
    failed = [r for r in results if r["result"] == "FAIL"]
    for result in results:
        print(f"{result['name']}: {result['result']} - {result['reason']}")
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    raise SystemExit(1 if failed else 0)
