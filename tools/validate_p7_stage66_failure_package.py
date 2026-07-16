#!/usr/bin/env python3
"""Validate the immutable r57 Stage66 campaign failure package offline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any


EXPECTED_RUN_ID = "p7_20260716_stationary_app_r57_diag_stage66_c02"
EXPECTED_SOURCE_COMMIT = "f4913949df34d66a5b6a5de3ad9f14ac2cfbac4d"
EXPECTED_ORDINALS = [1, 2, 3, 4, 66]
EXPECTED_OLD_CMD = "75320a519959cc6d089ea3eba33c38caccb7f138a025ea439bc9686cdb79ded4"
EXPECTED_NEW_CMD = "65ec268add3973b6dca64222985da47caeaee44a340b0ec1466782914fd743d9"
EXPECTED_NEW_CONHOST = "32e45de7f02912f3907083690043df4abdc4705eea28300719788eaa4a339d0b"
EXPECTED_PROFILE_ID = "vivado_2023_1_windows_26200_8875_system_helpers"
EXPECTED_IDENTITY_MANIFEST_SHA256 = (
    "67645bc53ae6c484204604ae3741bbce2d24fb7dbff6a5e63e8ea1a68972ed94"
)
EXPECTED_IDENTITY_PROBE_SHA256 = (
    "46ae65f7eea40c1cdda5595a69b36acc6d1add7e231b6319674304100385ea25"
)
EXPECTED_STAGE_SUMMARY = Path(
    "stage_prefix/001_p7_safe_idle/p7_jtag_axi_stage_summary.json"
)
EXPECTED_RECOVERY_FILES = {
    "hardware_authorization.json",
    "hash_manifest.csv",
    "hash_manifest.json",
    "program_tfdu_shutdown_safe.stderr.log",
    "program_tfdu_shutdown_safe.stdout.log",
    "program_tfdu_shutdown_safe.summary.txt",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_object(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is invalid: {type(exc).__name__}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} is not a JSON object")
        return {}
    return value


def marker_map(path: Path, errors: list[str], label: str) -> dict[str, str]:
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label} is unreadable: {type(exc).__name__}: {exc}")
        return {}
    result: dict[str, str] = {}
    for raw in text.splitlines():
        if "=" not in raw:
            continue
        key, value = raw.strip().split("=", 1)
        if key in result:
            errors.append(f"{label} contains duplicate marker {key}")
        else:
            result[key] = value
    return result


def validate_package(package_dir: Path) -> dict[str, Any]:
    root = package_dir.resolve(strict=False)
    errors: list[str] = []
    if not root.is_dir() or root.is_symlink():
        errors.append(f"package root is missing/not regular: {root}")
        return {
            "schema": "rf-comm-p7-stage66-failure-package-validation-v1",
            "P7_STAGE66_FAILURE_PACKAGE_VALIDATION": "FAIL",
            "hardware_actions_executed": False,
            "errors": errors,
        }

    manifest_path = root / "package_manifest.json"
    manifest = load_object(manifest_path, errors, "package manifest")
    if manifest.get("schema") != "rf-comm-p7-r57-stage66-campaign-failure-package-v1":
        errors.append("package manifest schema mismatch")
    if manifest.get("run_id") != EXPECTED_RUN_ID:
        errors.append("package run ID mismatch")
    if manifest.get("source_commit") != EXPECTED_SOURCE_COMMIT:
        errors.append("package source commit mismatch")
    for key, expected in {
        "result": "FAIL_RECOVERED",
        "failed_full_stage_ordinal": 1,
        "stage66_launched": False,
        "complete_1800_second_stage66_pass": False,
        "hardware_mutation_attempted": False,
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "recovery_changes_failed_stage_result": False,
    }.items():
        if manifest.get(key) != expected:
            errors.append(f"package manifest fact mismatch: {key}")

    records = manifest.get("files")
    if not isinstance(records, list):
        records = []
        errors.append("package file records are missing")
    if manifest.get("file_count") != len(records):
        errors.append("package file count mismatch")
    declared: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            errors.append("package file record is malformed")
            continue
        raw = record["path"]
        pure = PurePosixPath(raw)
        if (
            pure.is_absolute()
            or "\\" in raw
            or any(part in {"", ".", ".."} for part in pure.parts)
            or raw in declared
        ):
            errors.append(f"package file path is unsafe/duplicated: {raw}")
            continue
        path = (root / Path(*pure.parts)).resolve(strict=False)
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"package file escapes root: {raw}")
            continue
        if not path.is_file() or path.is_symlink():
            errors.append(f"package file is missing/not regular: {raw}")
            continue
        if record.get("bytes") != path.stat().st_size:
            errors.append(f"package file byte count mismatch: {raw}")
        if record.get("sha256") != sha256_file(path):
            errors.append(f"package file SHA256 mismatch: {raw}")
        declared[raw] = record
    observed = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    }
    if observed != set(declared):
        errors.append(
            "package file set mismatch: "
            f"missing={sorted(set(declared) - observed)} "
            f"unknown={sorted(observed - set(declared))}"
        )

    provenance_record = manifest.get("helper_provenance")
    provenance: dict[str, Any] = {}
    if not isinstance(provenance_record, dict):
        errors.append("helper provenance record is missing")
    else:
        provenance_path = (root / str(provenance_record.get("path", ""))).resolve(
            strict=False
        )
        if provenance_path.parent != root.parent or provenance_path.is_symlink():
            errors.append("helper provenance path is outside the exact package sibling boundary")
        elif not provenance_path.is_file():
            errors.append("helper provenance file is missing")
        else:
            if provenance_record.get("sha256") != sha256_file(provenance_path):
                errors.append("helper provenance SHA256 mismatch")
            provenance = load_object(provenance_path, errors, "helper provenance")

    outer_path = root / "sequence_execution_ledger.json"
    outer = load_object(outer_path, errors, "sequence execution ledger")
    outer_sha = sha256_file(outer_path) if outer_path.is_file() else ""
    if outer.get("schema") != "rf-comm-p7-sequence-execution-ledger-v1":
        errors.append("outer ledger schema mismatch")
    for key, expected in {
        "status": "FAIL",
        "hardware_actions_executed": True,
        "network_used": False,
        "motion_used": False,
        "plan_mode": "DIAGNOSTIC_STAGE66_CAMPAIGN",
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "full_stage_ordinals": EXPECTED_ORDINALS,
        "source_commit": EXPECTED_SOURCE_COMMIT,
        "attempt_count": 1,
        "completed_stage_count": 0,
        "next_stage_index": 0,
        "failed_stage_index": 0,
    }.items():
        if outer.get(key) != expected:
            errors.append(f"outer ledger fact mismatch: {key}")
    attempts = outer.get("attempts")
    attempt = attempts[0] if isinstance(attempts, list) and len(attempts) == 1 else {}
    if not isinstance(attempt, dict):
        attempt = {}
    for key, expected in {
        "attempt": 1,
        "stage_index": 0,
        "full_stage_ordinal": 1,
        "stage_id": "p7_safe_idle",
        "state": "TERMINAL",
        "result": "FAIL",
    }.items():
        if attempt.get(key) != expected:
            errors.append(f"outer failed-attempt fact mismatch: {key}")

    stage_path = root / EXPECTED_STAGE_SUMMARY
    stage = load_object(stage_path, errors, "stage-1 summary")
    stage_sha = sha256_file(stage_path) if stage_path.is_file() else ""
    summary_record = attempt.get("summary_file")
    if not isinstance(summary_record, dict) or summary_record.get("sha256") != stage_sha:
        errors.append("outer failed-attempt summary hash mismatch")
    for key, expected in {
        "P7_JTAG_AXI_SAFE_STAGE": "FAIL_PREFLIGHT",
        "stage_name": "p7_safe_idle",
        "requested_execute_hardware": True,
        "hardware_actions_executed": True,
        "programmed_fpga": False,
        "programmed_candidate": False,
        "programmed_shutdown_before": False,
        "programmed_shutdown_after": False,
        "started_ps_elf": False,
        "drove_tfdu_txd": False,
        "enabled_tfdu_receiver": False,
        "ethernet_used": False,
        "motion_used": False,
        "diagnostic_only": True,
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }.items():
        if stage.get(key) != expected:
            errors.append(f"stage-1 fact mismatch: {key}")
    preflight = stage.get("preflight_process")
    if not isinstance(preflight, dict):
        preflight = {}
        errors.append("stage-1 preflight process is missing")
    launch_error = str(preflight.get("launch_error", ""))
    if not (
        preflight.get("returncode") == 127
        and preflight.get("containment_kind") == "NO_CHILD_LAUNCHED"
        and preflight.get("process_tree_reaped") is True
        and "before P7_GO" in launch_error
        and EXPECTED_OLD_CMD in launch_error
        and EXPECTED_NEW_CMD in launch_error
    ):
        errors.append("stage-1 first-failure boundary is not exact")
    if not (
        preflight.get("expected_tool_daemon_prelaunch_hashes_verified") is False
        and preflight.get("expected_tool_daemon_prelaunch_sha256_by_role") == {}
        and preflight.get("expected_tool_daemon_prelaunch_hash_error") == ""
    ):
        errors.append("stage-1 no-child containment helper record mismatch")

    campaign_path = root / "campaign/campaign_ledger_after_recovery_record.json"
    campaign_ledger = load_object(campaign_path, errors, "campaign ledger")
    hardware_attempts = campaign_ledger.get("hardware_attempts")
    campaign_attempt = (
        hardware_attempts[-1]
        if isinstance(hardware_attempts, list) and hardware_attempts
        else {}
    )
    if not isinstance(campaign_attempt, dict):
        campaign_attempt = {}
    if not (
        campaign_ledger.get("status") == "READY"
        and campaign_ledger.get("actual_hardware_attempt_count") == 2
        and campaign_attempt.get("hardware_attempt_number") == 2
        and campaign_attempt.get("run_id") == EXPECTED_RUN_ID
        and campaign_attempt.get("source_commit") == EXPECTED_SOURCE_COMMIT
        and campaign_attempt.get("status") == "FAIL_RECOVERED"
        and campaign_attempt.get("failed_full_stage_ordinal") == 1
        and campaign_attempt.get("stationary_launched") is False
        and campaign_attempt.get("complete_1800_second_stage66_pass") is False
        and campaign_attempt.get("execution_ledger_sha256") == outer_sha
    ):
        errors.append("campaign terminal attempt is not exact FAIL_RECOVERED")
    recovery_record = campaign_attempt.get("independent_shutdown_recovery")
    if not isinstance(recovery_record, dict):
        recovery_record = {}
        errors.append("campaign recovery record is missing")
    if not (
        recovery_record.get("status") == "PASS"
        and recovery_record.get("shutdown_exit") == 0
        and recovery_record.get("recovery_changes_failed_stage_result") is False
    ):
        errors.append("campaign recovery record does not prove separate PASS")
    recovery_files = recovery_record.get("files")
    recorded_recovery = {
        item.get("name"): item
        for item in (recovery_files if isinstance(recovery_files, list) else [])
        if isinstance(item, dict)
    }
    if set(recorded_recovery) != EXPECTED_RECOVERY_FILES:
        errors.append("campaign recovery file set mismatch")
    for name in EXPECTED_RECOVERY_FILES:
        path = root / "recovery" / name
        record = recorded_recovery.get(name, {})
        if not path.is_file() or record.get("bytes") != path.stat().st_size or record.get(
            "sha256"
        ) != sha256_file(path):
            errors.append(f"campaign recovery file binding mismatch: {name}")

    recovery_markers = marker_map(
        root / "recovery/program_tfdu_shutdown_safe.summary.txt",
        errors,
        "recovery summary",
    )
    for key, expected in {
        "HARDWARE_AUTHORIZATION_EXIT": "0",
        "ALLOW_HARDWARE": "1",
        "NO_HARDWARE_ACTIONS_EXECUTED": "0",
        "TFDU_SHUTDOWN_PROGRAMMED_SEEN": "1",
        "SHUTDOWN_EXIT": "0",
        "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS": "PASS",
    }.items():
        if recovery_markers.get(key) != expected:
            errors.append(f"recovery marker mismatch: {key}")
    try:
        stdout = (root / "recovery/program_tfdu_shutdown_safe.stdout.log").read_text(
            encoding="utf-8", errors="replace"
        )
    except OSError as exc:
        stdout = ""
        errors.append(f"recovery stdout is unreadable: {type(exc).__name__}: {exc}")
    shutdown_markers = [
        line.strip()
        for line in stdout.splitlines()
        if line.strip().startswith("TFDU_SHUTDOWN_PROGRAMMED ")
    ]
    if len(shutdown_markers) != 1 or not shutdown_markers[0].endswith(
        "/shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    ):
        errors.append("recovery stdout does not contain one canonical shutdown marker")

    approved_fix = provenance.get("approved_fix")
    provenance_records = provenance.get("records")
    record_hashes = {
        item.get("role"): item.get("sha256")
        for item in (
            provenance_records if isinstance(provenance_records, list) else []
        )
        if isinstance(item, dict)
    }
    signature_statuses = {
        item.get("role"): item.get("signature_status")
        for item in (
            provenance_records if isinstance(provenance_records, list) else []
        )
        if isinstance(item, dict)
    }
    if not isinstance(approved_fix, dict) or not (
        approved_fix.get("current_profile_id") == EXPECTED_PROFILE_ID
        and approved_fix.get("per_role_mixing_allowed") is False
        and approved_fix.get("unknown_profile_fails_closed") is True
        and approved_fix.get("profile_sha256_by_role") == record_hashes
        and record_hashes.get("cmd") == EXPECTED_NEW_CMD
        and record_hashes.get("conhost") == EXPECTED_NEW_CONHOST
        and set(signature_statuses.values()) == {"Valid"}
    ):
        errors.append("helper provenance/current complete profile mismatch")
    confirmed = provenance.get("confirmed_failure_boundary")
    if not isinstance(confirmed, dict) or confirmed.get("wrapper_launch_error") != launch_error:
        errors.append("helper provenance does not bind the raw first failure")

    repair = load_object(
        root / "repair_focused_validation.json", errors, "repair focused validation"
    )
    focused = repair.get("final_affected_focused_tests")
    source_identity = repair.get("source_bound_identity")
    boundary = repair.get("prelaunch_boundary")
    raw_log = focused.get("raw_log") if isinstance(focused, dict) else None
    if not (
        repair.get("schema")
        == "rf-comm-p7-r57-helper-prelaunch-repair-focused-validation-v2"
        and repair.get("result") == "PASS"
        and repair.get("hardware_actions_executed") is False
        and repair.get("coverage_claimed") is False
        and repair.get("HARDWARE_ACCEPTANCE") == "PENDING_HW"
        and isinstance(focused, dict)
        and focused.get("completed_invocation_count") == 1
        and focused.get("tests_run") == 119
        and focused.get("failures") == 0
        and focused.get("errors") == 0
        and isinstance(raw_log, dict)
        and raw_log.get("path") == "repair_focused_tests.log"
        and raw_log.get("sha256")
        == declared.get("repair_focused_tests.log", {}).get("sha256")
        and raw_log.get("bytes")
        == declared.get("repair_focused_tests.log", {}).get("bytes")
    ):
        errors.append("r57 final affected-focused validation record mismatch")
    if not (
        isinstance(source_identity, dict)
        and source_identity.get("runtime_profile_id") == EXPECTED_PROFILE_ID
        and source_identity.get("legacy_profile_runtime_eligible") is False
        and source_identity.get("per_role_profile_mixing_allowed") is False
        and source_identity.get("unknown_hash_allowed") is False
        and source_identity.get("live_validation") == "PASS"
        and source_identity.get("manifest", {}).get("sha256")
        == EXPECTED_IDENTITY_MANIFEST_SHA256
        and source_identity.get("probe", {}).get("sha256")
        == EXPECTED_IDENTITY_PROBE_SHA256
    ):
        errors.append("r57 source-bound helper identity repair record mismatch")
    required_boundary = {
        "placeholder_rehearsal_requires_no_authorization": True,
        "validate_only_precedes_execution_ledger": True,
        "validate_only_precedes_campaign_lock": True,
        "validate_only_precedes_campaign_attempt": True,
        "runtime_wrapper_revalidates_inside_hardware_lock": True,
        "shared_validator_used": True,
        "exact_outer_argv_generated_by_python": True,
        "shell_path_expression_allowed": False,
        "campaign_attempt_consumed_by_validation": False,
    }
    if boundary != required_boundary:
        errors.append("r57 validate-only prelaunch boundary record mismatch")

    return {
        "schema": "rf-comm-p7-stage66-failure-package-validation-v1",
        "P7_STAGE66_FAILURE_PACKAGE_VALIDATION": "PASS" if not errors else "FAIL",
        "run_id": manifest.get("run_id"),
        "result": manifest.get("result"),
        "file_count": len(declared),
        "hardware_actions_executed": False,
        "network_used": False,
        "motion_used": False,
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline validation for the immutable r57 Stage66 failure package."
    )
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_package(args.package)
    if args.json_summary:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            "P7_STAGE66_FAILURE_PACKAGE_VALIDATION: "
            + result["P7_STAGE66_FAILURE_PACKAGE_VALIDATION"]
        )
    return 0 if not result["errors"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
