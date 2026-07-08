#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from p1_lib import GENERATED, run_all


def main():
    parser = argparse.ArgumentParser(description="Run RF_COMM_MULTILANE P1 offline hardening gates.")
    parser.add_argument("--strict", action="store_true", help="Treat skips as failures unless --allow-skips is set.")
    parser.add_argument("--allow-skips", action="store_true", help="Allow SKIP_WITH_REASON in the final status.")
    parser.add_argument("--output-dir", default=str(GENERATED), help="Summary output directory.")
    parser.add_argument("--json-summary", action="store_true", help="Print a compact JSON summary.")
    parser.add_argument("--no-bootstrap-run", action="store_true", help="Do not invoke scripts/run_offline_gates.py.")
    args = parser.parse_args()

    status, results = run_all(
        output_dir=Path(args.output_dir),
        strict=args.strict,
        allow_skips=args.allow_skips,
        run_bootstrap=not args.no_bootstrap_run,
    )
    failed = [r["name"] for r in results if r["result"] == "FAIL"]
    skipped = [r for r in results if r["result"] == "SKIP_WITH_REASON"]
    if args.json_summary:
        print(
            json.dumps(
                {
                    "P1_OFFLINE_HARDENING": status,
                    "NO_HARDWARE_ACTIONS_EXECUTED": True,
                    "HARDWARE_ACCEPTANCE": "PENDING_HW",
                    "failed": failed,
                    "skipped": skipped,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"P1_OFFLINE_HARDENING: {status}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        print("HARDWARE_ACCEPTANCE: PENDING_HW")
        print(f"FAILED_GATES: {', '.join(failed) if failed else 'none'}")
        print(f"SKIPPED_GATES: {', '.join(r['name'] for r in skipped) if skipped else 'none'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
