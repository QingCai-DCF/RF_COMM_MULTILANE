#!/usr/bin/env python3
from p3_pre_hw_lib import check_hardware_scripts_default_dry_run


if __name__ == "__main__":
    result = check_hardware_scripts_default_dry_run()
    print(f"RESULT: {result['result']}")
    print(f"REASON: {result['reason']}")
    print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    print("HARDWARE_ACCEPTANCE: PENDING_HW")
    raise SystemExit(0 if result["result"] == "PASS" else 1)
