#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from p4_hw_evidence import P4_DIR, write_markdown, write_text


def main() -> int:
    parser = argparse.ArgumentParser(description="P4 shutdown entrypoint. Defaults to dry-run and does not touch hardware.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    if args.execute_hardware:
        payload = {
            "P4_SHUTDOWN": "BLOCKED_NOT_AUTHORIZED",
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "reason": "shutdown programming requires the main P4 authorization wrapper",
        }
        code = 2
    else:
        payload = {
            "P4_SHUTDOWN": "SKIP_NO_HARDWARE_ACTIONS",
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "reason": "dry-run made no hardware changes; shutdown image not required",
        }
        code = 0
    write_text(
        P4_DIR / "shutdown" / "p4_shutdown_log.txt",
        "\n".join(f"{key}: {value}" for key, value in payload.items()),
    )
    write_markdown(
        P4_DIR / "shutdown" / "p4_shutdown_summary.md",
        "P4 Shutdown Summary",
        payload["P4_SHUTDOWN"],
        payload["reason"],
        [
            f"P4_SHUTDOWN: {payload['P4_SHUTDOWN']}",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
        ],
    )
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
