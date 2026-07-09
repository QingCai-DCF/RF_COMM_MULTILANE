#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from p4_hw_evidence import P4_DIR, write_markdown, write_text


DIRECTIONS = ["AB_L0", "BA_L0", "AB_L1", "BA_L1"]


def main() -> int:
    parser = argparse.ArgumentParser(description="P4 raw lane matrix entrypoint. Defaults to dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    status = "BLOCKED_NOT_AUTHORIZED" if args.execute_hardware else "SKIP_NOT_AUTHORIZED"
    rows = [{"direction": direction, "status": status, "reason": "no valid P4 authorization"} for direction in DIRECTIONS]
    write_text(
        P4_DIR / "raw_lane_matrix" / "p4_raw_lane_matrix.csv",
        "direction,status,reason\n" + "\n".join(f"{row['direction']},{row['status']},{row['reason']}" for row in rows),
    )
    write_markdown(
        P4_DIR / "raw_lane_matrix" / "p4_raw_lane_matrix.md",
        "P4 Raw Lane Matrix",
        status,
        "raw matrix is not run without authorization",
        [
            f"RAW_LANE_MATRIX: {status}",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            "",
            "| Direction | Status | Reason |",
            "| --- | --- | --- |",
            *(f"| {row['direction']} | {row['status']} | {row['reason']} |" for row in rows),
        ],
    )
    payload = {
        "RAW_LANE_MATRIX": status,
        "directions": rows,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 2 if args.execute_hardware else 0


if __name__ == "__main__":
    raise SystemExit(main())
