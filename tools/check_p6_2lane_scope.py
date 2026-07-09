#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from run_p6_local_transport_no_ethernet import check_2lane_scope


def main() -> int:
    parser = argparse.ArgumentParser(description="Check P6 two-lane scope boundary.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    payload = check_2lane_scope()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P6_2LANE_SCOPE: {payload['P6_2LANE_SCOPE']}")
        print("EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE")
    return 0 if payload["P6_2LANE_SCOPE"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
