#!/usr/bin/env python3
from p1_lib import profiles_check


if __name__ == "__main__":
    result = profiles_check()
    print(f"RESULT: {result['result']}")
    print(f"REASON: {result['reason']}")
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    raise SystemExit(0 if result["result"] == "PASS" else 1)
