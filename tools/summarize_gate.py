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
    p4_auto_path = GENERATED / "p4_auto_hardware_acceptance_summary.json"
    p4_auto = {}
    if p4_auto_path.exists():
        try:
            p4_auto = json.loads(p4_auto_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            p4_auto = {}
    print(f"RESULT: {data.get('status', 'UNKNOWN')}")
    if "P1_OFFLINE_HARDENING" in data:
        print(f"P1_OFFLINE_HARDENING: {data.get('P1_OFFLINE_HARDENING')}")
    if "P2_SIMULATION_BASELINE" in data:
        print(f"P2_SIMULATION_BASELINE: {data.get('P2_SIMULATION_BASELINE')}")
    if "P3_PRE_HW_ACCEPTANCE_PACKAGE" in data:
        print(f"P3_PRE_HW_ACCEPTANCE_PACKAGE: {data.get('P3_PRE_HW_ACCEPTANCE_PACKAGE')}")
    p4_status = p4_auto.get("P4_AUTO_HARDWARE_ACCEPTANCE", data.get("P4_AUTO_HARDWARE_ACCEPTANCE"))
    if p4_status:
        print(f"P4_AUTO_HARDWARE_ACCEPTANCE: {p4_status}")
    hardware_actions = bool(p4_auto.get("HARDWARE_ACTIONS_EXECUTED"))
    print(f"NO_HARDWARE_ACTIONS_EXECUTED: {str(not hardware_actions).lower()}")
    print(f"HARDWARE_ACCEPTANCE: {p4_auto.get('HARDWARE_ACCEPTANCE', 'PENDING_HW')}")
    for result in data.get("results", []):
        print(f"{result['name']}: {result['result']}")
    return 0 if data.get("status") in {"PASS", "PASS_WITH_SKIPS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
