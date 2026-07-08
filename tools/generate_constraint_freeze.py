#!/usr/bin/env python3
from p3_pre_hw_lib import generate_constraint_freeze


if __name__ == "__main__":
    result = generate_constraint_freeze()
    print(f"RESULT: {result['result']}")
    print(f"REASON: {result['reason']}")
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    print("HARDWARE_ACCEPTANCE: PENDING_HW")
    raise SystemExit(0 if result["result"] == "PASS" else 1)
