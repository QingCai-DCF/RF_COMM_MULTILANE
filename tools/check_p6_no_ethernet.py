#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from run_p6_local_transport_no_ethernet import check_no_ethernet


def main() -> int:
    parser = argparse.ArgumentParser(description="Check P6 no-Ethernet boundary.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    payload = check_no_ethernet()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P6_NO_ETHERNET: {payload['P6_NO_ETHERNET']}")
        print("ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE")
    return 0 if payload["P6_NO_ETHERNET"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
