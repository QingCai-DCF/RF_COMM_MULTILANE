#!/usr/bin/env python3
import argparse
import json

from p3_pre_hw_lib import run_pre_hw_acceptance_package_gate


def main():
    parser = argparse.ArgumentParser(description="Run P3 pre-hardware acceptance package gate. This gate never executes hardware.")
    parser.add_argument("--allow-skips", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--no-hardware", action="store_true", default=True)
    parser.add_argument("--skip-p1-p2-recheck", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.no_hardware:
        raise SystemExit("P3 gate refuses hardware mode.")
    payload = run_pre_hw_acceptance_package_gate(allow_skips=args.allow_skips, skip_p1_p2_recheck=args.skip_p1_p2_recheck)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload.get("P3_PRE_HW_ACCEPTANCE_PACKAGE") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
