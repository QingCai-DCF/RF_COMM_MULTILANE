#!/usr/bin/env python3
"""Read-only verification of frozen P10 PASS/closed evidence without live-state rebinding."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PASS_TAG = "p10-ax7020-dual-node-2lane-pass"
PASS_OBJECT = "0b8f4fd41b98978ae3c036d0f057990b947e3cdb"
PASS_TARGET = "35f5fefdcf5ac2833ed5708cef7a5de3005a2aa0"
CLOSED_TAG = "p10-ax7020-dual-node-2lane-closed"
CLOSED_OBJECT = "de64a1e8fd21931015b01f0f48c91bf0ba3b5040"
CLOSED_TARGET = "b212f81bd0a8114e309fb821025fa17f0484b255"
RUN_ID = "p10_formal_20260730T181535Z_03"
RUN_ROOT = f"evidence/hardware/p10/{RUN_ID}"
FINAL_PATH = f"{RUN_ROOT}/final/orchestrator_result.json"
MANIFEST_PATH = f"{RUN_ROOT}/final/run_evidence_sha256_manifest.json"
CLOSEOUT_PATH = "evidence/generated/p10_closeout_summary.json"
AUTH_PATH = "config/p10_fasttrack_current_run_authorization.json"


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8").strip()


def tagged_json(tag: str, path: str) -> dict[str, Any]:
    value = json.loads(git_bytes("show", f"{tag}:{path}").decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"tagged JSON root is not a mapping: {path}")
    return value


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    errors: list[str] = []
    checked = 0
    checked_bytes = 0
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be 1", errors)
    require(os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower()
            in {"false", "0", "no"},
            "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false", errors)
    for tag, object_id, target in (
        (PASS_TAG, PASS_OBJECT, PASS_TARGET),
        (CLOSED_TAG, CLOSED_OBJECT, CLOSED_TARGET),
    ):
        try:
            require(git_text("cat-file", "-t", tag) == "tag", f"{tag} is not annotated", errors)
            require(git_text("rev-parse", tag) == object_id, f"{tag} object changed", errors)
            require(git_text("rev-list", "-n", "1", tag) == target, f"{tag} target changed", errors)
            require(subprocess.run(
                ["git", "merge-base", "--is-ancestor", target, "HEAD"], cwd=ROOT,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            ).returncode == 0, f"{tag} target is not an ancestor of HEAD", errors)
        except subprocess.SubprocessError as exc:
            errors.append(f"tag verification failed for {tag}: {exc}")
    try:
        final = tagged_json(PASS_TAG, FINAL_PATH)
        manifest = tagged_json(PASS_TAG, MANIFEST_PATH)
        closeout = tagged_json(CLOSED_TAG, CLOSEOUT_PATH)
        authorization = tagged_json(CLOSED_TAG, AUTH_PATH)
        require(final.get("status") == "PASS", "tagged P10 final is not PASS", errors)
        require(final.get("run_id") == RUN_ID, "tagged P10 run ID mismatch", errors)
        require(final.get("SHUTDOWN_FIXED") == "PASS" and
                final.get("SHUTDOWN_ROTATING") == "PASS",
                "tagged P10 dual shutdown is not PASS", errors)
        require(final.get("network_used") is False and final.get("rewiring_executed") is False,
                "tagged P10 scope boundary mismatch", errors)
        require(manifest.get("status") == "PASS" and manifest.get("run_id") == RUN_ID,
                "tagged P10 evidence manifest is not PASS", errors)
        entries = manifest.get("files", [])
        require(isinstance(entries, list) and bool(entries),
                "tagged P10 evidence manifest has no files", errors)
        if isinstance(entries, list):
            for entry in entries:
                path = f"{RUN_ROOT}/{entry.get('path', '')}"
                try:
                    raw = git_bytes("show", f"{PASS_TAG}:{path}")
                except subprocess.SubprocessError:
                    errors.append(f"tagged P10 manifest file missing: {path}")
                    continue
                require(len(raw) == entry.get("bytes"),
                        f"tagged P10 manifest byte mismatch: {path}", errors)
                require(hashlib.sha256(raw).hexdigest() == entry.get("sha256"),
                        f"tagged P10 manifest SHA256 mismatch: {path}", errors)
                checked += 1
                checked_bytes += len(raw)
        require(closeout.get("status") == "PASS", "tagged P10 closeout is not PASS", errors)
        require(authorization.get("current_run_hardware_authorization") is True and
                authorization.get("authorization_id") ==
                "P10-FASTTRACK-CURRENT-RUN-IMMUTABLE",
                "tagged immutable P10 authorization record changed", errors)
        closeout_auth = closeout.get("authorization", {})
        require(closeout_auth.get("current_run_hardware_authorization") is False and
                closeout_auth.get("last_hardware_authorization_consumed") is True,
                "tagged P10 closeout does not consume authorization", errors)
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as exc:
        errors.append(f"tagged P10 evidence verification failed: {exc}")
    payload = {
        "schema_version": 1,
        "test_id": "P10-FROZEN-VERIFY-EXISTING",
        "status": "PASS" if not errors else "FAIL",
        "pass_tag": PASS_TAG,
        "pass_tag_object": PASS_OBJECT,
        "pass_tag_target": PASS_TARGET,
        "closed_tag": CLOSED_TAG,
        "closed_tag_object": CLOSED_OBJECT,
        "closed_tag_target": CLOSED_TARGET,
        "verified_file_count": checked,
        "verified_bytes": checked_bytes,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "errors": errors,
    }
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"P10_FROZEN_VERIFY_EXISTING={payload['status']}")
        print(f"P10_PASS_TAG_TARGET={PASS_TARGET}")
        print(f"P10_CLOSED_TAG_TARGET={CLOSED_TARGET}")
        print(f"VERIFIED_FILE_COUNT={checked}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
        print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
