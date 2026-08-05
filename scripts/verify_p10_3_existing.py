#!/usr/bin/env python3
"""Read-only verification of the immutable P10.3 closeout and hardware PASS."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT = ROOT / "evidence/generated/p10_3_closeout_summary.json"
FINAL = ROOT / "evidence/generated/p10_3_final_summary.json"
CONSISTENCY = ROOT / "evidence/generated/p10_3_evidence_consistency.json"
SHUTDOWN = ROOT / "evidence/generated/p10_3_shutdown.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    errors: list[str] = []
    try:
        closeout = json.loads(CLOSEOUT.read_text(encoding="utf-8"))
        final = json.loads(FINAL.read_text(encoding="utf-8"))
        consistency = json.loads(CONSISTENCY.read_text(encoding="utf-8"))
        shutdown = json.loads(SHUTDOWN.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"P10_3_VERIFY_EXISTING=FAIL:{exc}")
        return 1
    if git("cat-file", "-t", "p10.3-ax7020-stationary-4lane-pass") != "tag":
        errors.append("P10.3 pass tag is not annotated")
    if git("cat-file", "-t", "p10.3-ax7020-stationary-4lane-closed") != "tag":
        errors.append("P10.3 closeout tag is not annotated")
    if git("rev-parse", "p10.3-ax7020-stationary-4lane-pass^{}") != \
            "e647f066bbba8b36660e5f0bc43c79adc872c4c0":
        errors.append("P10.3 pass tag target changed")
    if git("rev-parse", "p10.3-ax7020-stationary-4lane-closed^{}") != \
            "11a05992279717511527573012449b37787b9d6a":
        errors.append("P10.3 closeout tag target changed")
    if closeout.get("status") != "PASS" or closeout.get(
        "hardware_campaign_status"
    ) != "PASS":
        errors.append("P10.3 closeout status is not PASS")
    if final.get("status") != "PASS" or final.get("SHUTDOWN_FIXED") != "PASS" or \
            final.get("SHUTDOWN_ROTATING") != "PASS":
        errors.append("P10.3 final status/shutdown is not PASS")
    if consistency.get("status") != "PASS":
        errors.append("P10.3 evidence consistency is not PASS")
    if shutdown.get("status") != "PASS" or shutdown.get("SHUTDOWN_FIXED") != "PASS" or \
            shutdown.get("SHUTDOWN_ROTATING") != "PASS":
        errors.append("P10.3 shutdown summary is not PASS")
    for name, path in (("consistency", CONSISTENCY), ("shutdown", SHUTDOWN)):
        expected = closeout.get("evidence" if name == "consistency" else name, {}).get(
            f"{name}_sha256" if name == "consistency" else "sha256"
        )
        if expected != sha(path):
            errors.append(f"P10.3 {name} hash changed")
    manifest = ROOT / closeout.get("evidence", {}).get("manifest_path", "missing")
    if not manifest.is_file() or sha(manifest) != closeout.get("evidence", {}).get(
        "manifest_sha256"
    ):
        errors.append("P10.3 run evidence manifest changed or is missing")
    print(f"P10_3_VERIFY_EXISTING={'PASS' if not errors else 'FAIL'}")
    for error in errors:
        print(f"ERROR={error}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
