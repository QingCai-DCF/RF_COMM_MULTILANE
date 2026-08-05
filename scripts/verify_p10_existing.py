#!/usr/bin/env python3
"""Read-only verification of the frozen P10 PASS and offline closeout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from p8a_common import (
    REQUIREMENTS_PATH,
    ROOT,
    STATE_PATH,
    STATUS_PATH,
    TRACEABILITY_PATH,
    render_project_status,
    render_traceability,
    sha256_artifact,
    validate_requirements,
    validate_state,
)


RUN_ID = "p10_formal_20260730T181535Z_03"
RUN_ROOT = ROOT / "evidence/hardware/p10" / RUN_ID
PASS_TAG = "p10-ax7020-dual-node-2lane-pass"
PASS_TAG_OBJECT = "0b8f4fd41b98978ae3c036d0f057990b947e3cdb"
PASS_TAG_TARGET = "35f5fefdcf5ac2833ed5708cef7a5de3005a2aa0"
CLOSED_TAG = "p10-ax7020-dual-node-2lane-closed"
CLOSED_TAG_OBJECT = "de64a1e8fd21931015b01f0f48c91bf0ba3b5040"
CLOSED_TAG_TARGET = "b212f81bd0a8114e309fb821025fa17f0484b255"
FINAL_PATH = RUN_ROOT / "final/orchestrator_result.json"
MANIFEST_PATH = RUN_ROOT / "final/run_evidence_sha256_manifest.json"
CLOSEOUT_PATH = ROOT / "evidence/generated/p10_closeout_summary.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def verify_manifest(errors: list[str]) -> tuple[int, int]:
    if not MANIFEST_PATH.is_file():
        errors.append("P10 evidence manifest is missing")
        return 0, 0
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    require(manifest.get("status") == "PASS", "P10 evidence manifest is not PASS", errors)
    require(manifest.get("run_id") == RUN_ID, "P10 evidence manifest run ID mismatch", errors)
    entries = manifest.get("files", [])
    if not isinstance(entries, list):
        errors.append("P10 evidence manifest files is not a list")
        return 0, 0
    checked = 0
    checked_bytes = 0
    for entry in entries:
        path = RUN_ROOT / str(entry.get("path", ""))
        if not path.is_file():
            errors.append(f"manifest file missing: {entry.get('path')}")
            continue
        expected_size = int(entry.get("bytes", -1))
        if path.stat().st_size != expected_size:
            errors.append(f"manifest byte count mismatch: {entry.get('path')}")
            continue
        if sha256(path) != entry.get("sha256"):
            errors.append(f"manifest SHA256 mismatch: {entry.get('path')}")
            continue
        checked += 1
        checked_bytes += expected_size
    return checked, checked_bytes


def exact_generated_checks(errors: list[str]) -> None:
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    requirements = yaml.safe_load(REQUIREMENTS_PATH.read_text(encoding="utf-8"))
    errors.extend(validate_state(state, ROOT))
    errors.extend(validate_requirements(requirements, ROOT))
    if STATUS_PATH.read_bytes() != render_project_status(state).encode("utf-8"):
        errors.append("PROJECT_STATUS.md is stale")
    if TRACEABILITY_PATH.read_bytes() != render_traceability(requirements).encode("utf-8"):
        errors.append("requirement traceability matrix is stale")


def verify_superseded_closeout(state: dict[str, Any], errors: list[str]) -> None:
    require(
        git("cat-file", "-t", CLOSED_TAG) == "tag",
        "P10 closed tag type changed",
        errors,
    )
    require(
        git("rev-parse", CLOSED_TAG) == CLOSED_TAG_OBJECT,
        "P10 closed tag object changed",
        errors,
    )
    require(
        git("rev-list", "-n", "1", CLOSED_TAG) == CLOSED_TAG_TARGET,
        "P10 closed tag target changed",
        errors,
    )
    require(CLOSEOUT_PATH.is_file(), "P10 closeout summary is missing", errors)
    if not CLOSEOUT_PATH.is_file():
        return
    closeout = json.loads(CLOSEOUT_PATH.read_text(encoding="utf-8"))
    require(closeout.get("status") == "PASS", "P10 closeout status is not PASS", errors)
    require(
        closeout.get("authorization", {}).get(
            "current_run_hardware_authorization"
        )
        is False,
        "P10 closeout authorization is not false",
        errors,
    )
    require(
        state.get("last_hardware_authorization_consumed") is True,
        "P10 authorization is not recorded as consumed",
        errors,
    )
    require(
        state.get("p10_acceptance", {}).get("status") == "PASS",
        "P10 scoped acceptance is not preserved",
        errors,
    )
    state_closeout = state.get("p10_post_acceptance_closeout", {})
    require(
        state_closeout.get("status") == "PASS",
        "P10 post-acceptance closeout state is not PASS",
        errors,
    )
    require(
        state_closeout.get("evidence_path")
        == CLOSEOUT_PATH.relative_to(ROOT).as_posix(),
        "P10 closeout state path mismatch",
        errors,
    )
    require(
        state_closeout.get("evidence_sha256")
        == sha256_artifact(CLOSEOUT_PATH, ROOT),
        "P10 closeout state SHA256 mismatch",
        errors,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    errors: list[str] = []

    no_hardware = os.environ.get("NO_HARDWARE") == "1"
    authorization_false = os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() in {"0", "false", "no"}
    require(no_hardware, "NO_HARDWARE must be 1", errors)
    require(
        authorization_false,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false",
        errors,
    )

    try:
        require(git("cat-file", "-t", PASS_TAG) == "tag", "P10 PASS tag type changed", errors)
        require(git("rev-parse", PASS_TAG) == PASS_TAG_OBJECT, "P10 PASS tag object changed", errors)
        require(
            git("rev-list", "-n", "1", PASS_TAG) == PASS_TAG_TARGET,
            "P10 PASS tag target changed",
            errors,
        )
        tag_diff = subprocess.run(
            [
                "git",
                "diff",
                "--quiet",
                PASS_TAG,
                "--",
                str(RUN_ROOT.relative_to(ROOT)).replace("\\", "/"),
                "evidence/generated/p10_fasttrack_final_summary.json",
                "evidence/generated/p10_fasttrack_final_summary.md",
            ],
            cwd=ROOT,
            check=False,
        )
        require(
            tag_diff.returncode == 0,
            "frozen P10 run/final summary differs from the PASS tag",
            errors,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        errors.append(f"P10 Git topology verification failed: {exc}")

    checked_files, checked_bytes = verify_manifest(errors)
    if FINAL_PATH.is_file():
        final = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
        require(final.get("status") == "PASS", "P10 final status is not PASS", errors)
        require(final.get("run_id") == RUN_ID, "P10 final run ID mismatch", errors)
        require(final.get("SHUTDOWN_FIXED") == "PASS", "fixed shutdown is not PASS", errors)
        require(final.get("SHUTDOWN_ROTATING") == "PASS", "rotating shutdown is not PASS", errors)
        require(final.get("network_used") is False, "P10 final evidence used network", errors)
        require(final.get("hardware_movement") is False, "P10 final evidence used motion", errors)
    else:
        errors.append("P10 final orchestrator evidence is missing")

    env = dict(os.environ)
    env["NO_HARDWARE"] = "1"
    env["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
    current_state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    p10_1_supersedes_closeout_generator = (
        current_state.get("p10_1_offline_status") == "PASS"
        and current_state.get("current_program_stage")
        in {
            "P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE",
            "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE",
            "P10_1_PERFORMANCE_REMEDIATION",
            "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION",
            "USER_DECISION_AFTER_2LANE_SPEED_STABILITY_PASS",
            "P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS",
            "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE",
            "USER_DECISION_AFTER_P10_3",
            "P11_PREREQUISITE_ACQUISITION",
        }
    )
    if p10_1_supersedes_closeout_generator:
        verify_superseded_closeout(current_state, errors)
        closeout_check_status = "PASS_CURRENT_CANONICAL_SUPERSESSION"
    else:
        closeout_check = run(
            [sys.executable, "scripts/generate_p10_closeout.py", "--check"], env
        )
        require(
            closeout_check.returncode == 0
            and "P10_CLOSEOUT_GENERATION=PASS" in closeout_check.stdout,
            "P10 closeout generator check failed",
            errors,
        )
        closeout_check_status = (
            "PASS" if closeout_check.returncode == 0 else "FAIL"
        )
    no_hardware_scan = run(
        [sys.executable, "scripts/check_no_hardware_calls.py"], env
    )
    require(
        no_hardware_scan.returncode == 0
        and "NO_HARDWARE_ACTIONS_EXECUTED=1" in no_hardware_scan.stdout,
        "no-hardware static scan failed",
        errors,
    )
    try:
        exact_generated_checks(errors)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        errors.append(f"canonical generated-file validation failed: {exc}")

    summary: dict[str, Any] = {
        "status": "PASS" if not errors else "FAIL",
        "test_id": "P10-VERIFY-EXISTING",
        "mode": "READ_ONLY_TAGGED_EVIDENCE_AND_OFFLINE_CLOSEOUT",
        "tag": PASS_TAG,
        "tag_object": PASS_TAG_OBJECT,
        "tag_target": PASS_TAG_TARGET,
        "run_id": RUN_ID,
        "verified_manifest_file_count": checked_files,
        "verified_manifest_bytes": checked_bytes,
        "closeout_generator_check": closeout_check_status,
        "no_hardware_static_scan": (
            "PASS" if no_hardware_scan.returncode == 0 else "FAIL"
        ),
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "errors": errors,
    }
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P10_VERIFY_EXISTING={summary['status']}")
        print(f"P10_TAG_TARGET={summary['tag_target']}")
        print(f"VERIFIED_MANIFEST_FILE_COUNT={checked_files}")
        print(f"VERIFIED_MANIFEST_BYTES={checked_bytes}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
        print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
        for error in errors:
            print(f"ERROR: {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
