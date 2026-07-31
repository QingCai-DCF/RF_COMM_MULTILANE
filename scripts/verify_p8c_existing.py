#!/usr/bin/env python3
"""Read-only verification of the annotated immutable P8C safety checkpoint."""

from __future__ import annotations

import argparse
import json
import subprocess

from p10_1_common import ROOT


TAG = "p8c-pass"
EXPECTED_OBJECT = "6b3aebe4552836639f1a72f29311c62c29985129"
EXPECTED_TARGET = "c44b0d45133bf75c9c71f53dde77f3dc186ad131"
REQUIRED_GATES = {
    "EXACT_1000US_SLIDING_DUTY",
    "STRICT_LT20_PERCENT_HARD_LIMIT",
    "LE18_PERCENT_DESIGN_TARGET",
    "MAX_CONTINUOUS_TXD_HIGH_LE_1US",
    "STUCK_HIGH_FAULT_LATCH_AND_KILL",
    "SINGLE_GLOBAL_PERMIT_PER_ENDPOINT",
    "PERMIT_LOW_ALL_TX_OFF_PROPERTY",
    "PERMIT_ASYNC_DROP_FINAL_RTL_KILL",
    "PERMIT_REASSERT_REQUIRES_EXPLICIT_REARM",
    "PARTIAL_FRAME_NOT_RESUMED",
    "TFDU_STARTUP_500US_REGRESSION",
}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    object_type = git("cat-file", "-t", TAG)
    tag_object = git("rev-parse", TAG)
    target = git("rev-list", "-n", "1", TAG)
    if object_type != "tag":
        errors.append("P8C checkpoint is not an annotated tag")
    if tag_object != EXPECTED_OBJECT:
        errors.append("P8C annotated tag object changed")
    if target != EXPECTED_TARGET:
        errors.append("P8C tag target changed")
    data = json.loads(
        git("show", f"{TAG}:evidence/generated/p8c_final_summary.json")
    )
    if data.get("status") != "PASS":
        errors.append("frozen P8C summary is not PASS")
    if data.get("NO_HARDWARE_ACTIONS_EXECUTED") is not True:
        errors.append("frozen P8C summary lacks the no-hardware boundary")
    if data.get("CURRENT_RUN_HARDWARE_AUTHORIZATION") is not False:
        errors.append("frozen P8C summary has an open authorization")
    gates = data.get("exit_gates", {})
    for gate in REQUIRED_GATES:
        if gates.get(gate) != "PASS":
            errors.append(f"frozen P8C safety gate is not PASS: {gate}")
    payload = {
        "test_id": "P8C-VERIFY-EXISTING",
        "status": "PASS" if not errors else "FAIL",
        "tag": TAG,
        "tag_object": tag_object,
        "tag_target": target,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "verified_safety_gates": sorted(REQUIRED_GATES),
        "errors": errors,
    }
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"P8C_VERIFY_EXISTING={payload['status']}")
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
