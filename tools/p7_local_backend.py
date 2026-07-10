#!/usr/bin/env python3
"""Offline P7 local-stub object transport CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p7_app_transport import ApplicationTransport, LanePolicy, LocalStubBackend


def main() -> int:
    parser = argparse.ArgumentParser(description="Run RFAP object transport through the offline local stub")
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--session-epoch", default="0x50370001")
    parser.add_argument("--object-id", default="1")
    parser.add_argument("--lane-policy", choices=[item.name for item in LanePolicy], default="STRIPE_ROUND_ROBIN")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    transport = ApplicationTransport(LocalStubBackend())
    result = transport.send_file(
        Path(args.input_file), Path(args.output_file),
        session_epoch=int(args.session_epoch, 0), object_id=int(args.object_id, 0),
        lane_policy=LanePolicy[args.lane_policy],
    )
    summary = {
        "P7_LOCAL_BACKEND": "PASS" if result.passed else "FAIL",
        "reason": result.error,
        "input_sha256": result.input_sha256,
        "output_sha256": result.output_sha256,
        "input_crc32": f"0x{result.input_crc32:08x}",
        "output_crc32": f"0x{result.output_crc32:08x}",
        "metrics": transport.metrics.snapshot(),
        "hardware_actions_executed": False,
        "network_used": False,
    }
    if args.json_summary:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        for key, value in summary.items():
            print(f"{key}: {value}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
