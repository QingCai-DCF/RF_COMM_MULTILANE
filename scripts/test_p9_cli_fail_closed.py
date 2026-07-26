#!/usr/bin/env python3
"""Prove P9 phase-2/CLI negative cases fail before any hardware server call."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import p9_hardware_runtime as hw  # noqa: E402


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase2", type=Path, required=True)
    args = parser.parse_args(argv)
    phase2_path = args.phase2.resolve()
    baseline = json.loads(phase2_path.read_text(encoding="utf-8"))
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    out = ROOT / "evidence/generated/p9_cli_fail_closed" / run
    out.mkdir(parents=True, exist_ok=False)

    cases: dict[str, dict[str, Any] | None] = {
        "missing_authorization": None,
        "wrong_candidate_hash": copy.deepcopy(baseline),
        "wrong_profile": copy.deepcopy(baseline),
        "missing_shutdown": copy.deepcopy(baseline),
        "wrong_active_xdc": copy.deepcopy(baseline),
        "lane_mask_0x4": copy.deepcopy(baseline),
        "movement_allowed": copy.deepcopy(baseline),
        "rotation_allowed": copy.deepcopy(baseline),
        "network_allowed": copy.deepcopy(baseline),
        "ethernet_required": copy.deepcopy(baseline),
    }
    cases["wrong_candidate_hash"]["candidate_bitstream"]["sha256"] = "0" * 64
    cases["wrong_profile"]["profile"] = "Z7020_8LANE_TARGET"
    cases["missing_shutdown"].pop("shutdown_bitstream", None)
    cases["wrong_active_xdc"]["active_xdc_sha256"] = "0" * 64
    cases["lane_mask_0x4"]["lane_masks"] = [1, 2, 3, 4]
    cases["lane_mask_0x4"]["maximum_lane_mask"] = 4
    cases["movement_allowed"]["movement_allowed"] = True
    cases["rotation_allowed"]["rotation_allowed"] = True
    cases["network_allowed"]["network_allowed"] = True
    cases["ethernet_required"]["ethernet_required"] = True

    results: dict[str, Any] = {}
    failures: list[str] = []
    for name, mutated in cases.items():
        path = out / f"{name}.json"
        if mutated is not None:
            write_json(path, mutated)
        _record, _paths, errors = hw.validate_phase2(path)
        rejected = bool(errors)
        results[name] = {"rejected": rejected, "errors": errors,
                         "authorization": str(path)}
        if not rejected:
            failures.append(f"{name} was not rejected")

    # Exercise the actual CLI rejection branch with a separate invalid run ID
    # and a trap in place of start_hw_server.  The trap must remain untouched.
    cli_record = copy.deepcopy(baseline)
    cli_record["run_id"] = str(baseline["run_id"]) + "_negative_lane4"
    cli_path = out / "cli_lane4_phase2.json"
    write_json(cli_path, cli_record)
    hardware_entry_calls = 0
    original = hw.start_hw_server

    def forbidden_hardware_entry(_raw_logs: Path):
        nonlocal hardware_entry_calls
        hardware_entry_calls += 1
        raise AssertionError("start_hw_server was reached by an invalid P9 CLI")

    hw.start_hw_server = forbidden_hardware_entry
    try:
        cli_rc = hw.main([
            "--execute-hardware", "--formal", "--authorize-from", str(cli_path),
            "--run-id", cli_record["run_id"],
            "--bitstream", str(ROOT / baseline["candidate_bitstream"]["path"]),
            "--shutdown-bitstream", str(ROOT / baseline["shutdown_bitstream"]["path"]),
            "--elf", str(ROOT / baseline["ps_elf"]["path"]),
            "--max-runtime", "1800", "--lane-mask", "0x4", "--stage", "P9-04",
        ])
    finally:
        hw.start_hw_server = original
    if cli_rc == 0: failures.append("CLI lane-mask 0x4 returned success")
    if hardware_entry_calls != 0: failures.append("invalid CLI reached start_hw_server")

    summary = {
        "schema_version": 1, "status": "PASS" if not failures else "FAIL",
        "test_id": "P9-03-CLI-FAIL-CLOSED-NEGATIVE",
        "phase2": str(phase2_path), "negative_cases": results,
        "cli_lane4_returncode": cli_rc,
        "hardware_server_start_calls": hardware_entry_calls,
        "failures": failures,
    }
    write_json(ROOT / "evidence/generated/p9_cli_fail_closed_summary.json", summary)
    write_json(out / "summary.json", summary)
    print(f"P9_CLI_FAIL_CLOSED={summary['status']}")
    print(f"P9_CLI_HW_SERVER_START_CALLS={hardware_entry_calls}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
