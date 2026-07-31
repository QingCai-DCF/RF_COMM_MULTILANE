#!/usr/bin/env python3
"""Fail-closed P10.1 hardware-performance preflight; defaults to dry-run."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from pathlib import Path
from typing import Any

from p10_1_common import (
    RAW,
    ROOT,
    evidence_base,
    rel,
    sha256,
    write_json,
    write_pair,
)


FIXED_ID = "AX7020-F/JTAG:210249855178"
ROTATING_ID = "AX7020-R/JTAG:210512180081"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RAW_CASES = RAW / "p10_1_hardware_dry_run_cases.json"


def resolve_repo_file(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return path


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("current_run_hardware_authorization") is not True:
        errors.append("current-run hardware authorization is absent")
    identities = manifest.get("board_identities", {})
    if not isinstance(identities, dict):
        errors.append("board identities are missing")
    else:
        if identities.get("fixed") != FIXED_ID:
            errors.append("fixed board identity mismatch")
        if identities.get("rotating") != ROTATING_ID:
            errors.append("rotating board identity mismatch")
    lane_mask = manifest.get("lane_mask")
    if not isinstance(lane_mask, int) or lane_mask < 1 or lane_mask > 0x3:
        errors.append("lane mask must be within 0x1..0x3")
    if manifest.get("ethernet_requested") is not False:
        errors.append("Ethernet is forbidden in P10.1")
    if manifest.get("movement_requested") is not False:
        errors.append("movement is forbidden in P10.1")
    runtime = manifest.get("max_runtime_seconds")
    if not isinstance(runtime, int) or runtime <= 0 or runtime > 7200:
        errors.append("bounded max_runtime_seconds is required")
    shutdown = manifest.get("shutdown", {})
    if not isinstance(shutdown, dict) or any(
        shutdown.get(key) is not True
        for key in ("before", "on_error", "on_timeout", "on_interrupt", "after")
    ):
        errors.append("complete shutdown-before/on-exit/after policy is required")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) < 4:
        errors.append("fixed/rotating bitstream and ELF artifacts are required")
    else:
        roles_and_types: set[tuple[str, str]] = set()
        for index, record in enumerate(artifacts):
            label = f"artifacts[{index}]"
            if not isinstance(record, dict):
                errors.append(f"{label} must be an object")
                continue
            roles_and_types.add(
                (str(record.get("role")), str(record.get("artifact_type")))
            )
            path = resolve_repo_file(record.get("path"))
            digest = str(record.get("sha256", "")).lower()
            if path is None or not path.is_file():
                errors.append(f"{label} runtime artifact is missing")
            elif not SHA256_RE.fullmatch(digest) or sha256(path) != digest:
                errors.append(f"{label} artifact hash mismatch")
        expected = {
            ("fixed", "bitstream"),
            ("fixed", "ps_elf"),
            ("rotating", "bitstream"),
            ("rotating", "ps_elf"),
        }
        if not expected.issubset(roles_and_types):
            errors.append("role-bound fixed/rotating bitstream and ELF set is incomplete")
    return errors


def artifact(path: Path, role: str, artifact_type: str) -> dict[str, Any]:
    return {
        "role": role,
        "artifact_type": artifact_type,
        "path": rel(path),
        "sha256": sha256(path),
    }


def reference_manifest() -> dict[str, Any]:
    fixed_elf = ROOT / "evidence/generated/p10_1_software/p10_1_fixed_performance.elf"
    rotating_elf = (
        ROOT / "evidence/generated/p10_1_software/p10_1_rotating_performance.elf"
    )
    # A dry-run exercises hash and presence checks without presenting any
    # file as a programmable candidate. Actual bitstreams are substituted by
    # the build wrapper once the source checkpoint exists.
    fixed_bit = ROOT / "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc"
    rotating_bit = (
        ROOT
        / "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc"
    )
    return {
        "schema_version": 1,
        "current_run_hardware_authorization": True,
        "board_identities": {"fixed": FIXED_ID, "rotating": ROTATING_ID},
        "lane_mask": 0x3,
        "ethernet_requested": False,
        "movement_requested": False,
        "max_runtime_seconds": 3600,
        "shutdown": {
            "before": True,
            "on_error": True,
            "on_timeout": True,
            "on_interrupt": True,
            "after": True,
        },
        "artifacts": [
            artifact(fixed_bit, "fixed", "bitstream"),
            artifact(fixed_elf, "fixed", "ps_elf"),
            artifact(rotating_bit, "rotating", "bitstream"),
            artifact(rotating_elf, "rotating", "ps_elf"),
        ],
        "dry_run_placeholders": {
            "bitstream_records_are_nonprogrammable_xdc_hash_fixtures": True
        },
    }


def run_self_tests() -> list[dict[str, Any]]:
    base = reference_manifest()
    cases: list[tuple[str, dict[str, Any], str | None]] = [
        ("valid_dry_run", base, None),
    ]
    no_auth = copy.deepcopy(base)
    no_auth["current_run_hardware_authorization"] = False
    cases.append(("no_authorization", no_auth, "authorization"))
    wrong_id = copy.deepcopy(base)
    wrong_id["board_identities"]["fixed"] = "AX7020-F/JTAG:WRONG"
    cases.append(("wrong_board_id", wrong_id, "identity"))
    wrong_hash = copy.deepcopy(base)
    wrong_hash["artifacts"][0]["sha256"] = "0" * 64
    cases.append(("wrong_artifact_hash", wrong_hash, "hash"))
    missing_shutdown = copy.deepcopy(base)
    missing_shutdown["shutdown"]["after"] = False
    cases.append(("missing_shutdown", missing_shutdown, "shutdown"))
    bad_lane = copy.deepcopy(base)
    bad_lane["lane_mask"] = 0x4
    cases.append(("lane_mask_above_0x3", bad_lane, "lane mask"))
    ethernet = copy.deepcopy(base)
    ethernet["ethernet_requested"] = True
    cases.append(("ethernet_requested", ethernet, "Ethernet"))
    movement = copy.deepcopy(base)
    movement["movement_requested"] = True
    cases.append(("movement_requested", movement, "movement"))
    missing_runtime = copy.deepcopy(base)
    missing_runtime["artifacts"][1]["path"] = "missing/p10_1_fixed.elf"
    cases.append(("runtime_missing", missing_runtime, "missing"))
    results: list[dict[str, Any]] = []
    for case_id, manifest, expected_fragment in cases:
        errors = validate_manifest(manifest)
        passed = not errors if expected_fragment is None else any(
            expected_fragment.lower() in error.lower() for error in errors
        )
        results.append(
            {
                "case_id": case_id,
                "expected": "ACCEPT_DRY_RUN" if expected_fragment is None else "REJECT",
                "status": "PASS" if passed else "FAIL",
                "validation_errors": errors,
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1 for this offline checkpoint")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("current process authorization must remain false")
    if args.execute_hardware:
        errors.append("hardware execution is unavailable in the P10.1 offline checkpoint")
    cases = run_self_tests()
    if any(case["status"] != "PASS" for case in cases):
        errors.append("one or more fail-closed dry-run vectors failed")
    manifest_result: dict[str, Any] | None = None
    if args.manifest is not None:
        try:
            data = json.loads(args.manifest.read_text(encoding="utf-8"))
            manifest_errors = validate_manifest(data)
            manifest_result = {
                "path": str(args.manifest),
                "status": "PASS" if not manifest_errors else "FAIL",
                "errors": manifest_errors,
            }
            errors.extend(manifest_errors)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"manifest read failed: {exc}")
    write_json(
        RAW_CASES,
        {
            "schema_version": 1,
            "hardware_actions_executed": False,
            "cases": cases,
        },
    )
    payload = evidence_base(
        "P10_1-HARDWARE-RUNNER-DRY-RUN",
        status="PASS" if not errors else "FAIL",
        default_mode="DRY_RUN",
        hardware_actions_executed=False,
        no_authorization_fail_closed=True,
        hardware_server_started=False,
        jtag_accessed=False,
        programmable_artifact_used=False,
        rejection_case_count=len(cases) - 1,
        rejection_cases=cases,
        manifest_result=manifest_result,
        raw_cases={"path": rel(RAW_CASES), "sha256": sha256(RAW_CASES)},
        future_sequence=[
            "identity",
            "shutdown",
            "safe_boot",
            "short_raw_smoke",
            "short_object_smoke",
            "timer_calibration",
            "F_TO_R_sustained",
            "R_TO_F_sustained",
            "64_MiB",
            "30_minute_performance",
            "shutdown",
        ],
        errors=errors,
    )
    write_pair(
        "p10_1_hardware_dry_run",
        "P10.1 fail-closed hardware runner dry-run",
        payload,
    )
    print(f"P10_1_HARDWARE_RUNNER_DRY_RUN={payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
