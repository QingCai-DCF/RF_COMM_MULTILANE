#!/usr/bin/env python3
"""Validate the immutable r72 Stage66 campaign failure package offline."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

from prepare_p7_stage66_campaign_run import canonical_tree_record


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = ROOT / "evidence/generated/p7_r72_stage66_campaign_c06_failure_package"
EXPECTED_RUN_ID = "p7_20260716_stationary_app_r72_diag_stage66_c06"
EXPECTED_SOURCE_COMMIT = "3f7cd27b02e6e8f3747d285f80db438598159256"
EXPECTED_RAW_TREE = "afbfc33217c6713fe996e85232b051d7e6f66e711a74aabf66648cb9f75d4385"
EXPECTED_ORDINALS = [1, 2, 3, 4, 66]


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
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"{label} is unreadable: {type(exc).__name__}: {exc}")
        return {}
    result: dict[str, str] = {}
    for line in lines:
        if "=" not in line:
            continue
        key, value = line.strip().split("=", 1)
        if key in result:
            errors.append(f"{label} contains duplicate marker {key}")
        else:
            result[key] = value
    return result


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate_package(
    package_dir: Path = DEFAULT_PACKAGE,
    *,
    raw_root: Path | None = None,
) -> dict[str, Any]:
    package = package_dir.resolve(strict=False)
    errors: list[str] = []
    failure = load_object(package / "failure_record.json", errors, "failure record")
    observation = load_object(
        package / "postprocess_observation.json", errors, "postprocess observation"
    )

    require(errors, failure.get("status") == "IMMUTABLE_FAIL_RECOVERED", "r72 status changed")
    require(errors, failure.get("run_id") == EXPECTED_RUN_ID, "r72 run ID changed")
    require(
        errors,
        failure.get("source_commit") == EXPECTED_SOURCE_COMMIT,
        "r72 source commit changed",
    )
    require(errors, failure.get("run_id_immutable_fail") is True, "r72 is not immutable FAIL")
    require(
        errors,
        failure.get("resume_restart_copy_reuse_permitted") is False,
        "r72 reuse boundary changed",
    )

    bindings = failure.get("package_bindings")
    if not isinstance(bindings, dict):
        errors.append("package bindings are missing")
        bindings = {}
    for relative, expected in bindings.items():
        path = package / str(relative)
        require(errors, path.is_file() and not path.is_symlink(), f"bound file missing: {relative}")
        if path.is_file():
            require(
                errors,
                sha256_file(path) == expected,
                f"bound file hash mismatch: {relative}",
            )
    observed_sha = sha256_file(package / "postprocess_observation.json")
    boundary = failure.get("confirmed_failure_boundary", {})
    require(
        errors,
        isinstance(boundary, dict)
        and boundary.get("postprocess_observation_sha256") == observed_sha,
        "postprocess observation binding mismatch",
    )

    preserved = failure.get("preserved_raw_evidence", {})
    if raw_root is None:
        raw_root = ROOT / str(preserved.get("path", ""))
    raw_record = canonical_tree_record(raw_root)
    require(errors, not raw_record.get("errors"), "raw tree could not be hashed")
    require(errors, raw_record.get("file_count") == 341, "r72 raw file count changed")
    require(errors, raw_record.get("byte_count") == 69_848_130, "r72 raw byte count changed")
    require(errors, raw_record.get("tree_sha256") == EXPECTED_RAW_TREE, "r72 raw tree changed")
    require(
        errors,
        isinstance(preserved, dict)
        and preserved.get("tree_sha256") == raw_record.get("tree_sha256"),
        "failure record raw-tree binding mismatch",
    )

    ledger_path = raw_root / "sequence_execution_ledger.json"
    ledger = load_object(ledger_path, errors, "sequence execution ledger")
    require(errors, ledger.get("status") == "FAIL", "r72 execution ledger is not FAIL")
    require(errors, ledger.get("full_stage_ordinals") == EXPECTED_ORDINALS, "r72 ordinals changed")
    require(errors, ledger.get("attempt_count") == 5, "r72 attempt count changed")
    require(errors, ledger.get("completed_stage_count") == 4, "r72 completed-stage count changed")
    require(errors, ledger.get("failed_stage_index") == 4, "r72 failed-stage index changed")
    require(errors, ledger.get("coverage_claimed") is False, "r72 claims acceptance coverage")
    require(errors, ledger.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", "r72 acceptance changed")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        attempts = []
        errors.append("r72 attempts are missing")
    require(
        errors,
        [item.get("result") for item in attempts if isinstance(item, dict)]
        == ["PASS", "PASS", "PASS", "PASS", "FAIL"],
        "r72 stage result sequence changed",
    )

    campaign = load_object(
        package / "campaign/campaign_ledger_after_recovery_record.json",
        errors,
        "campaign ledger",
    )
    hardware_attempts = campaign.get("hardware_attempts")
    last = hardware_attempts[-1] if isinstance(hardware_attempts, list) and hardware_attempts else {}
    require(errors, campaign.get("status") == "READY", "campaign is not READY after recovery")
    require(errors, campaign.get("actual_hardware_attempt_count") == 6, "campaign count changed")
    require(
        errors,
        isinstance(last, dict)
        and last.get("run_id") == EXPECTED_RUN_ID
        and last.get("hardware_attempt_number") == 6
        and last.get("status") == "FAIL_RECOVERED"
        and last.get("failed_full_stage_ordinal") == 66
        and last.get("stationary_launched") is True
        and last.get("complete_1800_second_stage66_pass") is False,
        "campaign terminal r72 attempt changed",
    )

    stage_root = raw_root / "066_p7_ps_stationary"
    stage_path = stage_root / "p7_ps_application_stage_summary.json"
    stage = load_object(stage_path, errors, "stage66 summary")
    require(errors, stage.get("P7_PS_APPLICATION_SAFE_STAGE") == "FAIL_STAGE", "stage66 is not FAIL")
    require(errors, stage.get("diagnostic_only") is True, "stage66 is not diagnostic-only")
    require(errors, stage.get("coverage_claimed") is False, "stage66 claims coverage")
    require(errors, stage.get("HARDWARE_ACCEPTANCE") == "PENDING_HW", "stage66 acceptance changed")
    process = stage.get("ps_process", {})
    postprocess = stage.get("postprocess", {})
    require(
        errors,
        isinstance(process, dict)
        and process.get("passed") is True
        and process.get("returncode") == 0
        and process.get("timed_out") is False,
        "r72 raw PS terminal process boundary changed",
    )
    require(
        errors,
        isinstance(postprocess, dict)
        and postprocess.get("passed") is False
        and len(postprocess.get("failures", [])) == 49,
        "r72 authoritative postprocess failure boundary changed",
    )

    observation_records = observation.get(
        "confirmed_slot_artifact_binding_observation", {}
    ).get("records", [])
    records_by_slot = {
        int(item.get("slot", -1)): item
        for item in observation_records
        if isinstance(item, dict)
    }
    cases = postprocess.get("cases", []) if isinstance(postprocess, dict) else []
    require(errors, len(cases) == 8 and len(records_by_slot) == 8, "slot observation count changed")
    bundle = stage_root / "bundle"
    for case in cases:
        if not isinstance(case, dict):
            errors.append("stationary case is malformed")
            continue
        slot = int(case.get("slot", -1))
        descriptor = case.get("descriptor", {})
        sequence = int(descriptor.get("completion_sequence", -1))
        record = records_by_slot.get(slot, {})
        generic_descriptor = bundle / f"descriptor_result_{slot}.bin"
        generic_output = bundle / f"output_result_{slot}.bin"
        generic_trace = bundle / f"trace_result_{slot}.bin"
        sequence_descriptor = bundle / f"stationary_{sequence:08d}_descriptor_result.bin"
        sequence_output = bundle / f"stationary_{sequence:08d}_output_result.bin"
        sequence_trace = bundle / f"stationary_{sequence:08d}_trace_result.bin"
        input_path = bundle / f"input_{slot}.bin"
        paths = [
            generic_descriptor,
            generic_output,
            generic_trace,
            sequence_descriptor,
            sequence_output,
            sequence_trace,
            input_path,
        ]
        if not all(path.is_file() for path in paths):
            errors.append(f"slot {slot} artifact set is incomplete")
            continue
        require(
            errors,
            generic_descriptor.read_bytes() == sequence_descriptor.read_bytes(),
            f"slot {slot} final descriptor alias relation changed",
        )
        require(
            errors,
            generic_output.read_bytes() != sequence_output.read_bytes(),
            f"slot {slot} stale generic output relation changed",
        )
        require(
            errors,
            generic_trace.read_bytes() != sequence_trace.read_bytes()
            and not any(generic_trace.read_bytes()),
            f"slot {slot} zero generic trace relation changed",
        )
        require(
            errors,
            sequence_output.read_bytes() == input_path.read_bytes(),
            f"slot {slot} sequence output/input equality changed",
        )
        for key, path in {
            "generic_descriptor_sha256": generic_descriptor,
            "generic_output_sha256": generic_output,
            "generic_trace_sha256": generic_trace,
            "sequence_output_sha256": sequence_output,
            "sequence_trace_sha256": sequence_trace,
        }.items():
            require(
                errors,
                record.get(key) == sha256_file(path),
                f"slot {slot} observation hash mismatch: {key}",
            )

    mailbox = postprocess.get("mailbox", {}) if isinstance(postprocess, dict) else {}
    metrics = postprocess.get("application_metrics", {}) if isinstance(postprocess, dict) else {}
    objects = postprocess.get("stationary_objects", []) if isinstance(postprocess, dict) else []
    start_ticks = int(mailbox.get("runtime_start_ticks", 0))
    counts_per_second = int(metrics.get("ps_counts_per_second", 0))
    rolling: list[int] = []
    if start_ticks > 0 and counts_per_second > 0 and isinstance(objects, list):
        for sample in range(1, 61):
            threshold = sample * 30 * counts_per_second
            window_start = max(0, threshold - 300 * counts_per_second)
            high = sum(
                int(item.get("bytes_completed", 0))
                for item in objects
                if isinstance(item, dict)
                and int(item.get("end_ticks", 0)) - start_ticks <= threshold
            )
            low = sum(
                int(item.get("bytes_completed", 0))
                for item in objects
                if isinstance(item, dict)
                and int(item.get("end_ticks", 0)) - start_ticks <= window_start
            )
            rolling.append(
                ((high - low) * 8 * counts_per_second) // (threshold - window_start)
            )
    replay = observation.get("counterfactual_metric_replay", {})
    require(errors, len(rolling) == 60, "300-second replay sample count changed")
    if rolling:
        require(
            errors,
            statistics.median(rolling[:10]) == replay.get("calibration_median_bps"),
            "300-second calibration replay changed",
        )
        require(
            errors,
            statistics.median(rolling[10:]) == replay.get("acceptance_median_bps"),
            "300-second acceptance replay changed",
        )
    require(
        errors,
        isinstance(replay, dict)
        and replay.get("classification") == "OFFLINE_DIAGNOSTIC_ONLY_NOT_HARDWARE_PASS"
        and replay.get("acceptance_promotion_permitted") is False,
        "counterfactual replay scope changed",
    )

    blocked_markers = marker_map(
        raw_root
        / "recovery_shutdown_after_failed_stage066_20260716T162804Z"
        / "program_tfdu_shutdown_safe.summary.txt",
        errors,
        "blocked recovery preparation",
    )
    require(
        errors,
        blocked_markers.get("AUTHORIZATION_MISSING") == "1"
        and blocked_markers.get("NO_HARDWARE_ACTIONS_EXECUTED") == "1",
        "blocked recovery preparation hardware boundary changed",
    )
    recovery_markers = marker_map(
        raw_root
        / "recovery_shutdown_after_failed_stage066_20260716T162843Z"
        / "program_tfdu_shutdown_safe.summary.txt",
        errors,
        "independent recovery",
    )
    require(
        errors,
        recovery_markers.get("SHUTDOWN_EXIT") == "0"
        and recovery_markers.get("TFDU_SHUTDOWN_PROGRAMMED_SEEN") == "1"
        and recovery_markers.get("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS") == "PASS",
        "independent recovery PASS markers changed",
    )

    result = {
        "schema": "rf-comm-p7-r72-stage66-failure-package-validation-v1",
        "P7_R72_STAGE66_FAILURE_PACKAGE_VALIDATION": "PASS" if not errors else "FAIL",
        "run_id": EXPECTED_RUN_ID,
        "result": "FAIL_RECOVERED",
        "hardware_actions_executed": False,
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "raw_tree_sha256": raw_record.get("tree_sha256", ""),
        "errors": errors,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE)
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    result = validate_package(args.package_dir, raw_root=args.raw_root)
    if args.json_summary:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"P7_R72_STAGE66_FAILURE_PACKAGE_VALIDATION={result['P7_R72_STAGE66_FAILURE_PACKAGE_VALIDATION']}")
        for error in result["errors"]:
            print(f"ERROR={error}")
    return 0 if not result["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
