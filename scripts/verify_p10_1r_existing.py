#!/usr/bin/env python3
"""Read-only verification of immutable P10.1R PASS and closed checkpoints."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PASS_TAG = "p10.1r-2lane-speed-stability-pass"
PASS_OBJECT = "c78066152e2d5ac0c673e21896fb90b9a78f7489"
PASS_TARGET = "9321ca2f1797eb12bfb02848c3ee27145e1e8eb4"
CLOSED_TAG = "p10.1r-2lane-speed-stability-closed"
CLOSED_OBJECT = "c0998935ddd19f44177540ea260a917c9ac54bad"
CLOSED_TARGET = "e90a2203c4d6b71f93e0ee1c5bf93bb263c8a1b8"
SOURCE_COMMIT = "39df17155ce82e38366fbdac00c79584f0fe1afa"
FINAL_PATH = "evidence/generated/p10_1r_final_summary.json"
FREEZE_PATH = "evidence/generated/p10_1r_artifact_freeze.json"
CLOSEOUT_PATH = "evidence/generated/p10_1r_closeout_summary.json"
AUTH_PATH = "config/p10_1r_current_run_hardware_authorization.json"


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8").strip()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load_tag_json(tag: str, path: str) -> tuple[dict[str, Any], bytes]:
    raw = git_bytes("show", f"{tag}:{path}")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"tagged JSON root is not a mapping: {path}")
    return value, raw


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    errors: list[str] = []
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be 1", errors)
    require(os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower()
            in {"false", "0", "no"},
            "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false", errors)
    for tag, expected_object, expected_target in (
        (PASS_TAG, PASS_OBJECT, PASS_TARGET),
        (CLOSED_TAG, CLOSED_OBJECT, CLOSED_TARGET),
    ):
        try:
            require(git_text("cat-file", "-t", tag) == "tag",
                    f"{tag} is not annotated", errors)
            require(git_text("rev-parse", tag) == expected_object,
                    f"{tag} object changed", errors)
            require(git_text("rev-list", "-n", "1", tag) == expected_target,
                    f"{tag} target changed", errors)
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"tag verification failed for {tag}: {exc}")

    checked_files = 0
    checked_bytes = 0
    try:
        final, _ = load_tag_json(PASS_TAG, FINAL_PATH)
        require(final.get("status") == "PASS", "tagged P10.1R final is not PASS", errors)
        require(final.get("source_commit") == SOURCE_COMMIT,
                "tagged P10.1R source commit mismatch", errors)
        require(final.get("current_run_hardware_authorization") is False,
                "tagged P10.1R authorization is open", errors)
        require(final.get("shutdown_fixed") == "PASS" and
                final.get("shutdown_rotating") == "PASS",
                "tagged P10.1R dual shutdown is not PASS", errors)
        require(final.get("network_used") is False and
                final.get("no_hardware_movement") is True,
                "tagged P10.1R boundary mismatch", errors)
        gates = final.get("mandatory_exit_gates", {})
        require(bool(gates) and all(value == "PASS" for value in gates.values()),
                "tagged P10.1R mandatory gate is not PASS", errors)
        for item in final.get("generated_evidence", []):
            path = item.get("path", "")
            raw = git_bytes("show", f"{PASS_TAG}:{path}")
            require(len(raw) == item.get("bytes"), f"tagged byte mismatch: {path}", errors)
            require(sha_bytes(raw) == item.get("sha256"),
                    f"tagged SHA256 mismatch: {path}", errors)
            current = ROOT / path
            require(current.is_file() and current.read_bytes() == raw,
                    f"current immutable P10.1R evidence differs: {path}", errors)
            checked_files += 1
            checked_bytes += len(raw)

        freeze, freeze_raw = load_tag_json(PASS_TAG, FREEZE_PATH)
        freeze_meta = final.get("artifact_freeze", {})
        require(len(freeze_raw) == freeze_meta.get("bytes") and
                sha_bytes(freeze_raw) == freeze_meta.get("sha256"),
                "tagged artifact freeze hash/size mismatch", errors)
        require(freeze.get("status") == "PASS" and
                freeze.get("acceptance_eligible") is True and
                freeze.get("source_commit") == SOURCE_COMMIT,
                "tagged artifact freeze is not source-bound PASS", errors)
        for item in freeze.get("artifacts", []):
            path = ROOT / item.get("path", "")
            require(path.is_file(), f"P10.1R artifact missing: {path}", errors)
            if path.is_file():
                require(path.stat().st_size == item.get("bytes") and
                        hashlib.sha256(path.read_bytes()).hexdigest() == item.get("sha256"),
                        f"P10.1R artifact hash/size mismatch: {path}", errors)
                checked_files += 1
                checked_bytes += path.stat().st_size

        closeout, _ = load_tag_json(CLOSED_TAG, CLOSEOUT_PATH)
        authorization, _ = load_tag_json(CLOSED_TAG, AUTH_PATH)
        require(closeout.get("status") == "PASS", "P10.1R closeout is not PASS", errors)
        require(closeout.get("accepted_baseline", {}).get("old_f1") ==
                "QUARANTINED_NOT_ACCEPTED",
                "P10.1R old F1 quarantine was not preserved", errors)
        require(authorization.get("current_run_hardware_authorization") is False and
                authorization.get("consumed") is True,
                "P10.1R authorization was not consumed", errors)
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as exc:
        errors.append(f"tagged evidence verification failed: {exc}")

    payload = {
        "schema_version": 1, "test_id": "P10_1R-VERIFY-EXISTING",
        "status": "PASS" if not errors else "FAIL",
        "pass_tag": PASS_TAG, "pass_tag_object": PASS_OBJECT,
        "pass_tag_target": PASS_TARGET, "closed_tag": CLOSED_TAG,
        "closed_tag_object": CLOSED_OBJECT, "closed_tag_target": CLOSED_TARGET,
        "source_commit": SOURCE_COMMIT, "verified_file_count": checked_files,
        "verified_bytes": checked_bytes, "hardware_actions_executed": False,
        "current_run_hardware_authorization": False, "errors": errors,
    }
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"P10_1R_VERIFY_EXISTING={payload['status']}")
        print(f"P10_1R_PASS_TAG_TARGET={PASS_TARGET}")
        print(f"P10_1R_CLOSED_TAG_TARGET={CLOSED_TARGET}")
        print(f"VERIFIED_FILE_COUNT={checked_files}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
        print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
