#!/usr/bin/env python3
"""Freeze one machine-readable P10 FastTrack current-run authorization."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import p10_hardware_runtime as runtime


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "config/p10_fasttrack_current_run_authorization.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--formal", action="store_true")
    group.add_argument("--stage")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=ROOT,
            text=True).strip() != runtime.EXPECTED_BRANCH:
        raise SystemExit("P10 authorization refused: wrong branch")
    if subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT,
            text=True).strip():
        raise SystemExit("P10 authorization refused: worktree must be clean")
    stages = list(runtime.ALL_FORMAL_STAGES) if args.formal else [args.stage]
    if not all(isinstance(stage, str) and runtime.STAGE_RE.fullmatch(stage)
               for stage in stages):
        raise SystemExit("P10 authorization refused: invalid stage")
    source = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    payload = runtime.create_authorization_payload(args.run_id, stages, source)
    output = args.output.resolve()
    if not runtime.inside(output, ROOT):
        raise SystemExit("P10 authorization output must remain inside worktree")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    print(json.dumps({"status": "AUTHORIZED", "run_id": args.run_id,
                      "stages": stages, "source_commit": source,
                      "output": runtime.rel(output),
                      "sha256": runtime.sha256(output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
