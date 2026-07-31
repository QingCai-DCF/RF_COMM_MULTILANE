#!/usr/bin/env python3
"""Offline P10.1 host-control plan encoder; never touches hardware by default."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from p10_1_common import ROOT


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("fixed", "rotating"), required=True)
    parser.add_argument("--direction", choices=("F_TO_R", "R_TO_F"), required=True)
    parser.add_argument("--lane-mask", type=lambda value: int(value, 0), default=3)
    parser.add_argument("--total-bytes", type=int, default=64 * 1024 * 1024)
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.lane_mask == 0 or args.lane_mask & ~0x3:
        raise SystemExit("lane mask must be within 0x1..0x3")
    if args.execute_hardware:
        if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
            raise SystemExit("hardware execution refused: current-run authorization is absent")
        raise SystemExit("hardware execution is not implemented in this offline stage")
    plan = {
        "schema_version": 1,
        "mode": "DRY_RUN_ONLY",
        "role": args.role,
        "direction": args.direction,
        "lane_mask": args.lane_mask,
        "total_bytes": args.total_bytes,
        "commands": [
            "PERF_CAPS", "PERF_CONFIG", "PERF_START",
            "PERF_STATUS_LOW_FREQUENCY", "PERF_STOP", "PERF_SNAPSHOT",
        ],
        "host_commands_per_segment": 0,
        "network_used": False,
        "hardware_actions_executed": False,
    }
    text = json.dumps(plan, indent=2, sort_keys=True) + "\n"
    if args.output:
        path = args.output if args.output.is_absolute() else ROOT / args.output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
