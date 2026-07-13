#!/usr/bin/env python3
"""Run each required complete P7 regression suite exactly once.

The output is an ignored, content-bound checkpoint input.  It lets the later
clean-source P7 checkpoint consume the complete-suite result without invoking
the same tests a second time.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from p7_regression_evidence import (
    BUILD_ROOT,
    REGRESSION_SCHEMA as SCHEMA,
    required_suite_commands,
    sha256_file,
)


ROOT = Path(__file__).resolve().parents[1]
SUITES = tuple(required_suite_commands().items())


def git(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *command], cwd=ROOT, text=True, capture_output=True, check=False)


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    if path.exists() or partial.exists():
        raise ValueError(f"refusing to overwrite regression evidence: {path}")
    try:
        with partial.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    finally:
        if partial.exists():
            partial.unlink()


def run_suite(name: str, command: list[str], output_dir: Path) -> dict[str, Any]:
    process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    stdout_path = output_dir / f"{name}.stdout.log"
    stderr_path = output_dir / f"{name}.stderr.log"
    atomic_write(stdout_path, process.stdout.encode("utf-8"))
    atomic_write(stderr_path, process.stderr.encode("utf-8"))
    match = re.search(r"Ran (\d+) tests? in ", process.stderr)
    count = int(match.group(1)) if match else None
    passed = process.returncode == 0 and count is not None and re.search(r"^OK$", process.stderr, re.MULTILINE) is not None
    return {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "invocation_count": 1,
        "discovered_test_count": count,
        "returncode": process.returncode,
        "status": "PASS" if passed else "FAIL",
        "stdout": {"path": str(stdout_path.resolve()), "sha256": sha256_file(stdout_path), "bytes": stdout_path.stat().st_size},
        "stderr": {"path": str(stderr_path.resolve()), "sha256": sha256_file(stderr_path), "bytes": stderr_path.stat().st_size},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    output = Path(args.output).resolve(strict=False)
    if not output.is_relative_to(BUILD_ROOT) or output == BUILD_ROOT or output.suffix.lower() != ".json":
        raise SystemExit("regression summary must be a new .json file under the ignored build root")
    status = git(["status", "--short"])
    head = git(["rev-parse", "HEAD"])
    if status.returncode != 0 or head.returncode != 0 or status.stdout.strip():
        result = {
            "schema": SCHEMA,
            "status": "BLOCKED_DIRTY_SOURCE",
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "dirty_files": status.stdout.splitlines(),
        }
        if args.json_summary:
            print(json.dumps(result, ensure_ascii=False))
        return 2
    if output.exists() or output.with_name(output.name + ".partial").exists():
        raise SystemExit(f"refusing existing regression summary: {output}")
    output_dir = output.parent / (output.stem + "_logs")
    if output_dir.exists():
        raise SystemExit(f"refusing existing regression log directory: {output_dir}")
    output_dir.mkdir(parents=True)
    suites = [run_suite(name, command, output_dir) for name, command in SUITES]
    status_after = git(["status", "--short"])
    head_after = git(["rev-parse", "HEAD"])
    source_commit = head.stdout.strip().lower()
    source_commit_after = head_after.stdout.strip().lower()
    dirty_after = bool(status_after.stdout.strip()) or status_after.returncode != 0
    commit_unchanged = (
        head_after.returncode == 0 and source_commit_after == source_commit
    )
    passed = (
        all(item["status"] == "PASS" for item in suites)
        and not dirty_after
        and commit_unchanged
    )
    result = {
        "schema": SCHEMA,
        "status": "PASS" if passed else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
        "source_commit": source_commit,
        "source_commit_after_suites": source_commit_after,
        "source_commit_unchanged": commit_unchanged,
        "dirty_worktree_before_suites": False,
        "dirty_worktree_after_suites": dirty_after,
        "dirty_files_after_suites": status_after.stdout.splitlines(),
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "FULL_SUITE_INVOCATION_COUNT": 2,
        "suite_invocation_count_by_name": {item["name"]: item["invocation_count"] for item in suites},
        "total_discovered_test_count": sum(int(item["discovered_test_count"] or 0) for item in suites),
        "suites": suites,
    }
    atomic_write(output, (json.dumps(result, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    if args.json_summary:
        print(json.dumps({**result, "summary_path": str(output), "summary_sha256": sha256_file(output)}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
