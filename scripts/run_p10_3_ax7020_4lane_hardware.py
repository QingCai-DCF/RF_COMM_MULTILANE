#!/usr/bin/env python3
"""Fail-closed P10.3 request validator and command-only dry-run.

P10.2 deliberately implements no hardware execution backend. A later P10.3
checkpoint must add that backend under a new authorization and artifact set.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIRING = ROOT / "docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md"
FIXED_BOARD = "AX7020-F/JTAG:210249855178"
ROTATING_BOARD = "AX7020-R/JTAG:210512180081"
ALLOWED_STAGES = tuple(f"P10_3-{index:02d}" for index in range(21))
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(request: dict[str, object]) -> list[str]:
    errors: list[str] = []
    if request.get("authorization_current") is not True:
        errors.append("CURRENT_RUN_AUTHORIZATION_REQUIRED")
    if request.get("scope") != "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE":
        errors.append("AUTHORIZATION_SCOPE_MISMATCH")
    if request.get("wiring_sha256") != sha256(WIRING):
        errors.append("WIRING_HASH_MISSING_OR_MISMATCH")
    if request.get("fixed_board") != FIXED_BOARD or request.get("rotating_board") != ROTATING_BOARD:
        errors.append("BOARD_ID_MISMATCH")
    modules = request.get("accepted_modules")
    required = [f"{side}{lane}" for side in "FR" for lane in range(4)]
    if not isinstance(modules, list) or sorted(modules) != sorted(required):
        errors.append("EIGHT_ACCEPTED_MODULES_REQUIRED")
    if request.get("old_f1_selected") is not False:
        errors.append("OLD_F1_SELECTION_FORBIDDEN")
    lane_mask = request.get("lane_mask")
    if not isinstance(lane_mask, int) or lane_mask < 1 or lane_mask > 0xF:
        errors.append("LANE_MASK_OUT_OF_RANGE")
    stage = request.get("stage")
    if stage not in ALLOWED_STAGES:
        errors.append("STAGE_NOT_ALLOWED")
    duration = request.get("maximum_runtime_seconds")
    if not isinstance(duration, int) or duration < 1 or duration > 1800:
        errors.append("RUNTIME_OUT_OF_RANGE_OR_2H_REQUEST")
    for flag, code in (("ethernet", "ETHERNET_FORBIDDEN"),
                       ("movement", "MOVEMENT_FORBIDDEN"),
                       ("rotation", "ROTATION_FORBIDDEN"),
                       ("rewiring", "REWIRING_FORBIDDEN"),
                       ("two_hour", "TWO_HOUR_FORBIDDEN")):
        if request.get(flag) is not False:
            errors.append(code)
    artifacts = request.get("artifacts")
    required_artifacts = ("fixed_shutdown_bit", "rotating_shutdown_bit",
                          "fixed_functional_bit", "rotating_functional_bit",
                          "fixed_elf", "rotating_elf")
    if not isinstance(artifacts, dict) or any(
            not isinstance(artifacts.get(name), str) or
            not SHA_RE.fullmatch(str(artifacts.get(name)))
            for name in required_artifacts):
        errors.append("IMMUTABLE_ARTIFACT_HASH_SET_REQUIRED")
    shutdown = request.get("shutdown_policy")
    if not isinstance(shutdown, dict) or not all(
            shutdown.get(key) is True for key in
            ("before", "on_error", "on_timeout", "on_ctrl_c", "on_normal_exit", "verify_both")):
        errors.append("COMPLETE_SHUTDOWN_POLICY_REQUIRED")
    return errors


def base_self_test_request() -> dict[str, object]:
    return {
        "authorization_current": True,
        "scope": "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE",
        "wiring_sha256": sha256(WIRING),
        "fixed_board": FIXED_BOARD, "rotating_board": ROTATING_BOARD,
        "accepted_modules": [f"{side}{lane}" for side in "FR" for lane in range(4)],
        "old_f1_selected": False, "lane_mask": 0xF, "stage": "P10_3-00",
        "maximum_runtime_seconds": 1800,
        "ethernet": False, "movement": False, "rotation": False,
        "rewiring": False, "two_hour": False,
        "artifacts": {name: "a" * 64 for name in
                      ("fixed_shutdown_bit", "rotating_shutdown_bit",
                       "fixed_functional_bit", "rotating_functional_bit",
                       "fixed_elf", "rotating_elf")},
        "shutdown_policy": {key: True for key in
                            ("before", "on_error", "on_timeout", "on_ctrl_c",
                             "on_normal_exit", "verify_both")},
    }


def self_test() -> int:
    base = base_self_test_request()
    tests = []
    mutations = (
        ("no_authorization", "authorization_current", False, "CURRENT_RUN_AUTHORIZATION_REQUIRED"),
        ("old_f1", "old_f1_selected", True, "OLD_F1_SELECTION_FORBIDDEN"),
        ("lane_mask_gt_f", "lane_mask", 0x10, "LANE_MASK_OUT_OF_RANGE"),
        ("ethernet", "ethernet", True, "ETHERNET_FORBIDDEN"),
        ("movement", "movement", True, "MOVEMENT_FORBIDDEN"),
        ("two_hour", "two_hour", True, "TWO_HOUR_FORBIDDEN"),
    )
    for name, key, value, expected in mutations:
        request = copy.deepcopy(base)
        request[key] = value
        errors = validate(request)
        tests.append({"name": name, "expected": expected, "errors": errors,
                      "status": "PASS" if expected in errors else "FAIL"})
    tests.append({"name": "valid_command_only_dry_run", "errors": validate(base),
                  "status": "PASS" if not validate(base) else "FAIL"})
    status = "PASS" if all(test["status"] == "PASS" for test in tests) else "FAIL"
    print(json.dumps({
        "schema_version": 1, "status": status, "tests": tests,
        "hardware_actions_executed": False, "hw_server_connected": False,
        "jtag_connected": False, "no_2h_stage_present": True,
    }, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.request is None:
        print("P10_3_RUNNER_REFUSED=REQUEST_AND_CURRENT_AUTHORIZATION_REQUIRED")
        return 3
    request = json.loads(args.request.read_text(encoding="utf-8"))
    errors = validate(request)
    if errors:
        print(json.dumps({"status": "REFUSED", "errors": errors,
                          "hardware_actions_executed": False}, indent=2))
        return 3
    if args.execute_hardware:
        print("P10_3_RUNNER_REFUSED=P10_2_HAS_NO_HARDWARE_EXECUTION_BACKEND")
        return 3
    print(json.dumps({
        "status": "PASS_DRY_RUN_COMMANDS_ONLY",
        "ordered_actions": ["verify identities and hashes", "shutdown-before both",
                            "run bounded requested stage", "shutdown-after both",
                            "verify shutdown markers"],
        "hardware_actions_executed": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
