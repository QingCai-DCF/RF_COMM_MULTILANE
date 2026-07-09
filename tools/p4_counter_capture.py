#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser(description="P4 counter capture placeholder. Defaults to dry-run.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    payload = {
        "P4_COUNTER_CAPTURE": "SKIP_NOT_AUTHORIZED" if not args.execute_hardware else "BLOCKED_NOT_AUTHORIZED",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "reason": "counter capture requires authorized P4 hardware execution",
    }
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 2 if args.execute_hardware else 0


if __name__ == "__main__":
    raise SystemExit(main())
