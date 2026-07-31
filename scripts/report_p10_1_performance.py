#!/usr/bin/env python3
"""Render a P10.1 metric/finalizer JSON record as a compact Markdown report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    lines = ["# P10.1 performance report", ""]
    directions = data.get("directions", data.get("result", {}).get("directions", {}))
    lines.extend([
        "| Direction | Status | Records | Minimum bit/s | Median bit/s | Maximum bit/s |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for direction, value in sorted(directions.items()):
        lines.append(
            f"| {direction} | {value.get('status')} | {value.get('record_count')} | "
            f"{value.get('minimum_bps')} | {value.get('median_bps')} | {value.get('maximum_bps')} |"
        )
    lines.extend([
        "",
        "Hardware scope: no real-hardware goodput claim is made by this report.",
    ])
    output = "\n".join(lines) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8", newline="\n")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
