#!/usr/bin/env python3
"""Read-only verification of the immutable P10.2 offline-readiness checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TAG = "p10.2-4lane-offline-ready"
TAG_OBJECT = "bf7c966fcda3e17665c7eae4c0179aec99f020ff"
TAG_TARGET = "08771d6bf9e852c9d34bcff61add1598e120b70a"
SOURCE_COMMIT = "dd44b0a4163ce74a491bae49bb6079b82dd94b7d"
GOAL_SHA256 = "f09ddcd1556b6def7eab250cae92b1cc69f7316a4c3338b5b04d23b10f22a8f5"
FINAL_PATH = "evidence/generated/p10_2_final_summary.json"
GATE_PATH = "evidence/generated/p10_2_gate_summary.json"
CONSISTENCY_PATH = "evidence/generated/p10_2_evidence_consistency.json"


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def git_text(*args: str) -> str:
    return git_bytes(*args).decode("utf-8").strip()


def load_tag_json(path: str) -> tuple[dict[str, Any], bytes]:
    raw = git_bytes("show", f"{TAG}:{path}")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"tagged JSON root is not a mapping: {path}")
    return value, raw


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_artifacts(final: dict[str, Any], errors: list[str]) -> tuple[int, int]:
    checked = 0
    checked_bytes = 0
    artifacts = final.get("artifacts", {})
    if set(artifacts) != {"fixed", "rotating"}:
        errors.append("tagged P10.2 role artifact set mismatch")
        return checked, checked_bytes
    for role, kinds in artifacts.items():
        if set(kinds) != {"bitstream", "xsa", "bsp", "elf"}:
            errors.append(f"tagged P10.2 {role} artifact kind set mismatch")
            continue
        for kind, item in kinds.items():
            try:
                path = ROOT / item["path"]
                expected_size = int(item["bytes"])
                expected_sha = item["sha256"]
                require(item.get("read_only") is True,
                        f"P10.2 artifact not declared read-only: {role}/{kind}", errors)
                require(path.is_file(), f"P10.2 artifact missing: {path}", errors)
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                require(len(raw) == expected_size,
                        f"P10.2 artifact byte mismatch: {path}", errors)
                require(hashlib.sha256(raw).hexdigest() == expected_sha,
                        f"P10.2 artifact SHA256 mismatch: {path}", errors)
                checked += 1
                checked_bytes += len(raw)
            except (KeyError, TypeError, ValueError, OSError) as exc:
                errors.append(f"malformed P10.2 artifact {role}/{kind}: {exc}")
    return checked, checked_bytes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    errors: list[str] = []
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be 1", errors)
    require(os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower()
            in {"false", "0", "no"},
            "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false", errors)
    checked = 0
    checked_bytes = 0
    try:
        require(git_text("cat-file", "-t", TAG) == "tag", f"{TAG} is not annotated", errors)
        require(git_text("rev-parse", TAG) == TAG_OBJECT, f"{TAG} object changed", errors)
        require(git_text("rev-list", "-n", "1", TAG) == TAG_TARGET,
                f"{TAG} target changed", errors)
        require(subprocess.run(
            ["git", "merge-base", "--is-ancestor", TAG_TARGET, "HEAD"], cwd=ROOT,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0, "P10.2 checkpoint is not an ancestor of HEAD", errors)
        final, _ = load_tag_json(FINAL_PATH)
        gate, _ = load_tag_json(GATE_PATH)
        consistency, _ = load_tag_json(CONSISTENCY_PATH)
        require(final.get("status") == "PASS", "tagged P10.2 final is not PASS", errors)
        require(final.get("source_commit") == SOURCE_COMMIT,
                "tagged P10.2 source commit mismatch", errors)
        require(final.get("goal_sha256") == GOAL_SHA256,
                "tagged P10.2 Goal SHA256 mismatch", errors)
        require(final.get("hardware_actions_executed") is False and
                final.get("current_run_hardware_authorization") is False,
                "tagged P10.2 no-hardware boundary mismatch", errors)
        require(final.get("network_used") is False and final.get("two_hour_qualification_executed") is False,
                "tagged P10.2 scope boundary mismatch", errors)
        require(gate.get("status") == "PASS" and gate.get("hardware_actions_executed") is False,
                "tagged P10.2 full offline gate is not PASS", errors)
        require(consistency.get("status") == "PASS",
                "tagged P10.2 evidence consistency is not PASS", errors)
        artifact_count, artifact_bytes = validate_artifacts(final, errors)
        checked += artifact_count
        checked_bytes += artifact_bytes
        for path in (FINAL_PATH, GATE_PATH, CONSISTENCY_PATH):
            _, raw = load_tag_json(path)
            current = ROOT / path
            require(current.is_file() and current.read_bytes() == raw,
                    f"current immutable P10.2 evidence differs: {path}", errors)
            checked += 1
            checked_bytes += len(raw)
    except (OSError, ValueError, KeyError, json.JSONDecodeError,
            subprocess.SubprocessError) as exc:
        errors.append(f"tagged P10.2 verification failed: {exc}")
    payload = {
        "schema_version": 1,
        "test_id": "P10_2-VERIFY-EXISTING",
        "status": "PASS" if not errors else "FAIL",
        "tag": TAG,
        "tag_object": TAG_OBJECT,
        "tag_target": TAG_TARGET,
        "source_commit": SOURCE_COMMIT,
        "goal_sha256": GOAL_SHA256,
        "verified_file_count": checked,
        "verified_bytes": checked_bytes,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "errors": errors,
    }
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"P10_2_VERIFY_EXISTING={payload['status']}")
        print(f"P10_2_TAG_TARGET={TAG_TARGET}")
        print(f"VERIFIED_FILE_COUNT={checked}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
        print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
