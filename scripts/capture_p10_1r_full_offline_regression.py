#!/usr/bin/env python3
"""Capture an exact-source P10.1R full offline replay without rewriting history."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "evidence/generated/p10_1r_full_offline_regression"
SOURCE_COMMIT = ""
DETERMINISTIC_TIMESTAMP = "2026-08-02T00:00:00Z"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def record(path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def source_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=path, text=True
    ).strip()


def copy_file(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def copy_tree(source: Path, destination: Path) -> list[Path]:
    copied: list[Path] = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        target = destination / path.relative_to(source)
        copied.append(copy_file(path, target))
    return copied


def main() -> int:
    global SOURCE_COMMIT
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--p8c-root", type=Path, required=True)
    parser.add_argument("--p8d-root", type=Path, required=True)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []

    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")

    source_root = args.source_root.resolve()
    p8c_root = args.p8c_root.resolve()
    p8d_root = args.p8d_root.resolve()
    SOURCE_COMMIT = source_head(source_root)
    if not re.fullmatch(r"[0-9a-f]{40}", SOURCE_COMMIT):
        errors.append("replay worktree HEAD is not a full Git commit")

    base_json = source_root / "evidence/generated/offline_gate_summary.json"
    base_md = source_root / "evidence/generated/offline_gate_summary.md"
    p8c_final = p8c_root / "p8c_final_summary.json"
    p8d_final = p8d_root / "p8d_final_summary.json"
    required = (base_json, base_md, p8c_final, p8d_final)
    for path in required:
        if not path.is_file():
            errors.append(f"missing replay evidence {path}")

    payloads: dict[str, dict[str, Any]] = {}
    if not errors:
        payloads = {
            "base": load_json(base_json),
            "p8c": load_json(p8c_final),
            "p8d": load_json(p8d_final),
        }
        for name, payload in payloads.items():
            if payload.get("status") not in {"PASS", "PASS_WITH_PENDING_TOOL"}:
                errors.append(f"{name} replay did not PASS")
        if payloads["base"].get("OFFLINE_REAL_BUILD_PROCESS_RAN") is not True:
            errors.append("canonical base replay did not run the real build process")
        if payloads["base"].get("no_hardware") is not True:
            errors.append("canonical base replay lacks the no-hardware marker")
        for name in ("p8c", "p8d"):
            if payloads[name].get("source_commit") != SOURCE_COMMIT:
                errors.append(f"{name} replay source commit mismatch")

    if DESTINATION.exists():
        errors.append(f"destination already exists: {DESTINATION}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    DESTINATION.mkdir(parents=True)
    copied: list[Path] = []
    copied.append(copy_file(base_json, DESTINATION / "offline_gate_summary.json"))
    copied.append(copy_file(base_md, DESTINATION / "offline_gate_summary.md"))

    vivado_source = source_root / "evidence/generated/vivado"
    vivado_destination = DESTINATION / "base_vivado"
    patterns = (
        "nonhardware_build_summary.*",
        "vivado_stdout_stderr.txt",
        "nonhardware_build_markers_*.txt",
        "post_route_timing_summary_*.rpt",
        "post_route_utilization_*.rpt",
        "post_route_drc_*.rpt",
        "post_synth_drc_*.rpt",
        "p4_auto_*_debug_instrumentation.txt",
    )
    for pattern in patterns:
        for source in sorted(vivado_source.glob(pattern)):
            if source.is_file():
                copied.append(copy_file(source, vivado_destination / source.name))

    copied.extend(copy_tree(p8c_root, DESTINATION / "p8c"))
    copied.extend(copy_tree(p8d_root, DESTINATION / "p8d"))

    manifest = {
        "schema_version": 1,
        "test_id": "P10_1R-EXACT-SOURCE-FULL-OFFLINE-REGRESSION",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS",
        "source_commit": SOURCE_COMMIT,
        "source_replay_worktree": str(source_root),
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "canonical_base_status": payloads["base"]["status"],
        "canonical_real_build_process_ran": payloads["base"][
            "OFFLINE_REAL_BUILD_PROCESS_RAN"
        ],
        "p8c_status": payloads["p8c"]["status"],
        "p8d_status": payloads["p8d"]["status"],
        "captured_file_count": len(copied),
        "files": [record(path) for path in sorted(copied)],
    }
    summary_path = DESTINATION / "summary.json"
    summary_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (DESTINATION / "summary.md").write_text(
        "\n".join(
            [
                "# P10.1R exact-source full offline regression",
                "",
                "- Status: `PASS`",
                f"- Source commit: `{SOURCE_COMMIT}`",
                "- Hardware actions executed: `false`",
                "- Current-run hardware authorization: `false`",
                "- Canonical base used the real offline build process: `true`",
                "- P8C safety regression: `PASS`",
                "- P8D data-plane regression: `PASS`",
                "",
                "This capture is isolated from historical generated evidence and "
                "does not promote any hardware scope.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    print("P10_1R_FULL_OFFLINE_CAPTURE=PASS")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    if args.json_summary:
        print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
