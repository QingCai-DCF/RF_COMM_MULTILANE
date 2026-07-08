#!/usr/bin/env python3
import argparse
import json

from p3_pre_hw_lib import add_hw_args, authorization_status


def main():
    parser = argparse.ArgumentParser(description="Check RF_COMM_MULTILANE future hardware authorization without touching hardware.")
    add_hw_args(parser)
    args = parser.parse_args()
    payload = authorization_status(args)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload["result"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
