#!/usr/bin/env python3
"""Fail-closed controls for the bounded P7 Stage 66 diagnostic campaign."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from p7_hardware_safety import ROOT, SHA256_RE, resolve_path, sha256_file


POLICY_SCHEMA = "rf-comm-p7-stage66-diagnostic-campaign-policy-v1"
LEDGER_SCHEMA = "rf-comm-p7-stage66-diagnostic-campaign-ledger-v1"
PLAN_MODE = "DIAGNOSTIC_STAGE66_CAMPAIGN"
CAMPAIGN_ID = "p7_stage66_stationary_diagnostic_20260715"
CAMPAIGN_FULL_STAGE_ORDINALS = (1, 2, 3, 4, 66)
MAX_HARDWARE_ATTEMPTS = 10
ABSENT_LEDGER_SHA256 = "ABSENT"
POLICY_PATH = (ROOT / "config" / "p7_stage66_diagnostic_campaign_policy.json").resolve(
    strict=False
)
LEDGER_ROOT = (
    ROOT / "evidence" / "hardware" / "p7" / "stage66_diagnostic_campaign"
).resolve(strict=False)
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
ATTEMPT_KEYS = {
    "hardware_attempt_number",
    "run_id",
    "source_commit",
    "sequence_plan_path",
    "sequence_plan_sha256",
    "execution_ledger_path",
    "prior_campaign_ledger_sha256",
    "launch_intent_at_utc",
    "ended_at_utc",
    "status",
    "failed_full_stage_ordinal",
    "stationary_launched",
    "complete_1800_second_stage66_pass",
    "execution_ledger_sha256",
    "independent_shutdown_recovery",
}
RETIREMENT_KEYS = {
    "run_id",
    "requested_hardware_attempt_number",
    "source_commit",
    "retired_at_utc",
    "status",
    "reason",
    "evidence_path",
    "evidence_sha256",
    "hardware_attempt_consumed",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _aware_datetime(value: Any, label: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        errors.append(f"{label} is missing/malformed")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{label} is not timezone-aware")
        return None
    return parsed.astimezone(timezone.utc)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _exact_keys(
    value: Mapping[str, Any], expected: set[str], label: str, errors: list[str]
) -> None:
    missing = sorted(expected - set(value))
    unknown = sorted(set(value) - expected)
    if missing:
        errors.append(f"{label} missing keys: {missing}")
    if unknown:
        errors.append(f"{label} contains unknown keys: {unknown}")


def validate_policy(
    path: Path, expected_sha256: str
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    policy_path = path.resolve(strict=False)
    if policy_path != POLICY_PATH:
        errors.append(f"Stage66 campaign policy must be canonical: {POLICY_PATH}")
    if not policy_path.is_file() or policy_path.is_symlink():
        return None, errors + [f"Stage66 campaign policy is missing/not regular: {policy_path}"]
    if not SHA256_RE.fullmatch(expected_sha256 or ""):
        errors.append("Stage66 campaign policy SHA256 is malformed")
    elif sha256_file(policy_path) != expected_sha256.lower():
        errors.append("Stage66 campaign policy SHA256 mismatch")
    try:
        policy = _load_json_object(policy_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, errors + [f"Stage66 campaign policy JSON is invalid: {exc}"]
    _exact_keys(
        policy,
        {
            "schema",
            "campaign_id",
            "authorization_status",
            "maximum_actual_hardware_attempts",
            "mandatory_prefix_full_stage_ordinals",
            "standalone_stage_full_ordinal",
            "selected_full_stage_ordinals",
            "stage66_exact_runtime_seconds",
            "diagnostic_marking",
            "stop_after_first_complete_stage66_pass",
            "failed_run_id_reuse_forbidden",
            "formal_full_run_excluded_from_diagnostic_limit",
            "runtime_campaign_ledger",
            "safety",
            "immutable_failed_baseline",
            "final_formal_requirements",
        },
        "Stage66 campaign policy",
        errors,
    )
    if policy.get("schema") != POLICY_SCHEMA:
        errors.append(f"Stage66 campaign policy schema must be {POLICY_SCHEMA}")
    if policy.get("authorization_status") != "AUTHORIZED":
        errors.append("Stage66 campaign policy is not AUTHORIZED")
    campaign_id = policy.get("campaign_id")
    if campaign_id != CAMPAIGN_ID:
        errors.append(f"Stage66 campaign ID must be exactly {CAMPAIGN_ID}")
    if policy.get("maximum_actual_hardware_attempts") != MAX_HARDWARE_ATTEMPTS:
        errors.append("Stage66 campaign maximum must be exactly 10 actual hardware attempts")
    if policy.get("mandatory_prefix_full_stage_ordinals") != [1, 2, 3, 4]:
        errors.append("Stage66 campaign mandatory prefix must be exact ordinals 1--4")
    if policy.get("standalone_stage_full_ordinal") != 66:
        errors.append("Stage66 campaign standalone stage must be full ordinal 66")
    if policy.get("selected_full_stage_ordinals") != list(CAMPAIGN_FULL_STAGE_ORDINALS):
        errors.append("Stage66 campaign selected ordinals must be exactly 1--4,66")
    if policy.get("stage66_exact_runtime_seconds") != 1800:
        errors.append("Stage66 campaign stationary runtime must be exactly 1800 seconds")
    if policy.get("diagnostic_marking") != {
        "P7_EXECUTION_MODE": "DIAGNOSTIC_ONLY",
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }:
        errors.append("Stage66 campaign diagnostic marking is not exact")
    for key in (
        "stop_after_first_complete_stage66_pass",
        "failed_run_id_reuse_forbidden",
        "formal_full_run_excluded_from_diagnostic_limit",
    ):
        if policy.get(key) is not True:
            errors.append(f"Stage66 campaign policy requires {key}=true")
    expected_safety = {
        "no_ethernet": True,
        "no_motion": True,
        "lane_count": 2,
        "max_lane_mask": "0x3",
        "shutdown_before_after_required": True,
        "independent_shutdown_recovery_after_failure_required": True,
        "external_hw_server_must_not_be_modified": True,
        "legacy_rf_comm_must_not_be_modified": True,
    }
    if policy.get("safety") != expected_safety:
        errors.append("Stage66 campaign safety contract is not exact")
    ledger_path = resolve_path(str(policy.get("runtime_campaign_ledger", "")))
    expected_ledger_path = LEDGER_ROOT / CAMPAIGN_ID / "campaign_ledger.json"
    if ledger_path != expected_ledger_path:
        errors.append(
            f"Stage66 runtime campaign ledger must be exactly {expected_ledger_path}"
        )

    baseline = policy.get("immutable_failed_baseline")
    expected_baseline = {
        "run_id": "p7_20260715_stationary_app_r41_formal_full",
        "status": "FAIL",
        "source_commit": "946ccbad66d64d715ad6745449b95f6c261ddf76",
        "execution_ledger": "evidence/generated/p7_r41_formal_failure_package/sequence_execution_ledger.json",
        "execution_ledger_sha256": "a86ec2a8e326a5354e9e79abed71ca938a3aa7a54b6936bc961beaf668ddba64",
        "completed_stage_count": 65,
        "failed_full_stage_ordinal": 66,
        "resume_restart_copy_reuse_forbidden": True,
    }
    if baseline != expected_baseline:
        errors.append("Stage66 campaign immutable r41 baseline binding is not exact")
    if isinstance(baseline, dict):
        baseline_path = resolve_path(str(baseline.get("execution_ledger", "")))
        baseline_sha = str(baseline.get("execution_ledger_sha256", "")).lower()
        if not baseline_path.is_file() or baseline_path.is_symlink():
            errors.append("frozen r41 execution ledger is missing/not regular")
        elif sha256_file(baseline_path) != baseline_sha:
            errors.append("frozen r41 execution ledger SHA256 mismatch")
        else:
            try:
                r41 = _load_json_object(baseline_path)
                attempts = r41.get("attempts")
                last = attempts[-1] if isinstance(attempts, list) and attempts else {}
                if not (
                    r41.get("status") == "FAIL"
                    and r41.get("source_commit") == expected_baseline["source_commit"]
                    and r41.get("completed_stage_count") == 65
                    and r41.get("attempt_count") == 66
                    and isinstance(last, dict)
                    and last.get("full_stage_ordinal") == 66
                    and last.get("result") == "FAIL"
                ):
                    errors.append(
                        "frozen r41 execution ledger no longer proves immutable Stage66 FAIL"
                    )
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
                errors.append(f"frozen r41 execution ledger is invalid: {exc}")

    expected_final = {
        "new_run_id_required": True,
        "full_stage_ordinals": list(range(1, 67)),
        "stage66_launch_limit": 1,
        "required_complete_suites_exactly_once": True,
        "cache_bypassed_canonical_offline_gate_required": True,
        "new_scoped_authorization_and_dry_validation_required": True,
        "only_formal_run_contributes_acceptance_coverage": True,
    }
    if policy.get("final_formal_requirements") != expected_final:
        errors.append("Stage66 campaign final formal-run requirements are not exact")
    return policy, errors


def campaign_ledger_path(policy: Mapping[str, Any]) -> Path:
    return resolve_path(str(policy["runtime_campaign_ledger"]))


def current_ledger_sha256(path: Path) -> str:
    return sha256_file(path) if path.is_file() else ABSENT_LEDGER_SHA256


def validate_ledger(
    policy: Mapping[str, Any], path: Path, *, allow_absent: bool
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    expected_path = campaign_ledger_path(policy)
    ledger_path = path.resolve(strict=False)
    if ledger_path != expected_path:
        errors.append(f"campaign ledger path mismatch: expected={expected_path} observed={ledger_path}")
    if not ledger_path.exists():
        return (None, errors) if allow_absent else (None, errors + ["campaign ledger is missing"])
    if not ledger_path.is_file() or ledger_path.is_symlink():
        return None, errors + ["campaign ledger is not a regular non-symlink file"]
    try:
        ledger = _load_json_object(ledger_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, errors + [f"campaign ledger JSON is invalid: {exc}"]
    _exact_keys(
        ledger,
        {
            "schema",
            "campaign_id",
            "policy_sha256",
            "created_at_utc",
            "updated_at_utc",
            "status",
            "maximum_actual_hardware_attempts",
            "actual_hardware_attempt_count",
            "hardware_attempts",
            "retired_pre_hardware_run_ids",
        },
        "campaign ledger",
        errors,
    )
    if ledger.get("schema") != LEDGER_SCHEMA:
        errors.append(f"campaign ledger schema must be {LEDGER_SCHEMA}")
    if ledger.get("campaign_id") != policy.get("campaign_id"):
        errors.append("campaign ledger campaign ID mismatch")
    if ledger.get("policy_sha256") != sha256_file(POLICY_PATH):
        errors.append("campaign ledger policy SHA256 mismatch")
    if ledger.get("maximum_actual_hardware_attempts") != MAX_HARDWARE_ATTEMPTS:
        errors.append("campaign ledger maximum attempt count mismatch")
    created_at = _aware_datetime(
        ledger.get("created_at_utc"), "campaign ledger created_at_utc", errors
    )
    updated_at = _aware_datetime(
        ledger.get("updated_at_utc"), "campaign ledger updated_at_utc", errors
    )
    if created_at is not None and updated_at is not None and updated_at < created_at:
        errors.append("campaign ledger updated_at_utc precedes created_at_utc")
    attempts = ledger.get("hardware_attempts")
    if not isinstance(attempts, list):
        return ledger, errors + ["campaign ledger hardware_attempts must be a list"]
    if ledger.get("actual_hardware_attempt_count") != len(attempts):
        errors.append("campaign ledger actual hardware attempt count mismatch")
    if len(attempts) > MAX_HARDWARE_ATTEMPTS:
        errors.append("campaign ledger exceeds the ten-attempt hard limit")
    seen_ids: set[str] = set()
    pass_count = 0
    unresolved_count = 0
    previous_end: datetime | None = None
    for index, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, dict):
            errors.append(f"campaign attempt {index} is not an object")
            continue
        _exact_keys(attempt, ATTEMPT_KEYS, f"campaign attempt {index}", errors)
        run_id = attempt.get("run_id")
        if attempt.get("hardware_attempt_number") != index:
            errors.append(f"campaign attempt {index} number is not contiguous")
        if not isinstance(run_id, str) or not RUN_ID_RE.fullmatch(run_id):
            errors.append(f"campaign attempt {index} run ID is malformed")
        elif run_id in seen_ids:
            errors.append(f"campaign attempt run ID is reused: {run_id}")
        else:
            seen_ids.add(run_id)
            if f"diag_stage66_c{index:02d}" not in run_id:
                errors.append(f"campaign attempt {index} run ID/number suffix mismatch")
        if run_id == policy.get("immutable_failed_baseline", {}).get("run_id"):
            errors.append("immutable r41 run ID appears in the diagnostic campaign ledger")
        if not COMMIT_RE.fullmatch(str(attempt.get("source_commit", ""))):
            errors.append(f"campaign attempt {index} source commit is malformed")
        if not isinstance(attempt.get("sequence_plan_path"), str) or not attempt.get(
            "sequence_plan_path"
        ):
            errors.append(f"campaign attempt {index} sequence plan path is missing")
        if not SHA256_RE.fullmatch(str(attempt.get("sequence_plan_sha256", ""))):
            errors.append(f"campaign attempt {index} sequence plan SHA256 is malformed")
        if not isinstance(attempt.get("execution_ledger_path"), str) or not attempt.get(
            "execution_ledger_path"
        ):
            errors.append(f"campaign attempt {index} execution ledger path is missing")
        prior_sha = attempt.get("prior_campaign_ledger_sha256")
        if prior_sha != ABSENT_LEDGER_SHA256 and not SHA256_RE.fullmatch(str(prior_sha)):
            errors.append(f"campaign attempt {index} prior-ledger SHA256 is malformed")
        if index > 1 and not SHA256_RE.fullmatch(str(prior_sha)):
            errors.append(f"campaign attempt {index} does not hash-bind the prior ledger")
        launch_time = _aware_datetime(
            attempt.get("launch_intent_at_utc"),
            f"campaign attempt {index} launch_intent_at_utc",
            errors,
        )
        if previous_end is not None and launch_time is not None and launch_time < previous_end:
            errors.append(f"campaign attempt {index} overlaps the prior attempt")
        status = attempt.get("status")
        if status == "PASS":
            pass_count += 1
            if attempt.get("stationary_launched") is not True or attempt.get(
                "complete_1800_second_stage66_pass"
            ) is not True:
                errors.append(f"campaign attempt {index} PASS lacks complete Stage66 evidence")
            if attempt.get("failed_full_stage_ordinal") is not None:
                errors.append(f"campaign attempt {index} PASS records a failed stage")
            if attempt.get("independent_shutdown_recovery") is not None:
                errors.append(f"campaign attempt {index} PASS contains failure recovery")
        elif status in {"ACTIVE", "FAIL_RECOVERY_REQUIRED"}:
            unresolved_count += 1
        elif status == "FAIL_RECOVERED":
            recovery = attempt.get("independent_shutdown_recovery")
            if not isinstance(recovery, dict) or not (
                recovery.get("status") == "PASS"
                and recovery.get("shutdown_exit") == 0
                and recovery.get("recovery_changes_failed_stage_result") is False
            ):
                errors.append(
                    f"campaign attempt {index} recovered status lacks exact independent shutdown evidence"
                )
        else:
            errors.append(f"campaign attempt {index} status is unsupported: {status}")
        terminal = status != "ACTIVE"
        ended_time = (
            _aware_datetime(
                attempt.get("ended_at_utc"),
                f"campaign attempt {index} ended_at_utc",
                errors,
            )
            if terminal
            else None
        )
        if status == "ACTIVE" and attempt.get("ended_at_utc") is not None:
            errors.append(f"campaign attempt {index} ACTIVE status has an end time")
        if launch_time is not None and ended_time is not None and ended_time < launch_time:
            errors.append(f"campaign attempt {index} ends before launch intent")
        if ended_time is not None:
            previous_end = ended_time
        failed_ordinal = attempt.get("failed_full_stage_ordinal")
        if status in {"FAIL_RECOVERY_REQUIRED", "FAIL_RECOVERED"}:
            if failed_ordinal not in CAMPAIGN_FULL_STAGE_ORDINALS:
                errors.append(f"campaign attempt {index} failed ordinal is outside 1--4,66")
            if attempt.get("complete_1800_second_stage66_pass") is not False:
                errors.append(f"campaign attempt {index} failure claims complete Stage66 PASS")
        elif status == "ACTIVE" and failed_ordinal is not None:
            errors.append(f"campaign attempt {index} ACTIVE status records a failed ordinal")
        if not isinstance(attempt.get("stationary_launched"), bool):
            errors.append(f"campaign attempt {index} stationary_launched is not boolean")
        execution_sha = attempt.get("execution_ledger_sha256")
        if status == "ACTIVE":
            if execution_sha is not None:
                errors.append(f"campaign attempt {index} ACTIVE status has terminal ledger SHA256")
            if attempt.get("independent_shutdown_recovery") is not None:
                errors.append(f"campaign attempt {index} ACTIVE status contains recovery")
        elif not SHA256_RE.fullmatch(str(execution_sha or "")):
            errors.append(f"campaign attempt {index} execution ledger SHA256 is malformed")
        if status == "FAIL_RECOVERY_REQUIRED" and attempt.get(
            "independent_shutdown_recovery"
        ) is not None:
            errors.append(f"campaign attempt {index} pending recovery already contains recovery")
        if status in {"ACTIVE", "FAIL_RECOVERY_REQUIRED"} and index != len(attempts):
            errors.append(f"campaign attempt {index} unresolved status is not terminal")
    if pass_count > 1:
        errors.append("campaign ledger contains more than one PASS")
    if pass_count and unresolved_count:
        errors.append("campaign ledger mixes PASS with an unresolved attempt")
    if pass_count == 1 and attempts[-1].get("status") != "PASS":
        errors.append("campaign PASS is not the terminal attempt")
    if unresolved_count > 1:
        errors.append("campaign ledger contains multiple unresolved attempts")
    retired = ledger.get("retired_pre_hardware_run_ids")
    retired_ids: list[str] = []
    if not isinstance(retired, list):
        errors.append("campaign ledger retired pre-hardware run ID list is malformed")
    else:
        for index, item in enumerate(retired, 1):
            label = f"campaign pre-hardware retirement {index}"
            if not isinstance(item, dict):
                errors.append(f"{label} is not an object")
                continue
            _exact_keys(item, RETIREMENT_KEYS, label, errors)
            run_id = str(item.get("run_id", ""))
            retired_ids.append(run_id)
            requested_number = item.get("requested_hardware_attempt_number")
            if not RUN_ID_RE.fullmatch(run_id):
                errors.append(f"{label} run ID is malformed")
            elif isinstance(requested_number, bool) or not isinstance(requested_number, int):
                errors.append(f"{label} requested hardware attempt number is malformed")
            elif not 1 <= requested_number <= MAX_HARDWARE_ATTEMPTS:
                errors.append(f"{label} requested hardware attempt number is out of range")
            elif f"diag_stage66_c{requested_number:02d}" not in run_id:
                errors.append(f"{label} run ID/attempt suffix mismatch")
            if run_id == policy.get("immutable_failed_baseline", {}).get("run_id"):
                errors.append(f"{label} illegally reuses immutable r41")
            if not COMMIT_RE.fullmatch(str(item.get("source_commit", ""))):
                errors.append(f"{label} source commit is malformed")
            retired_at = _aware_datetime(
                item.get("retired_at_utc"), f"{label} retired_at_utc", errors
            )
            if created_at is not None and retired_at is not None and retired_at < created_at:
                errors.append(f"{label} predates campaign ledger creation")
            if updated_at is not None and retired_at is not None and retired_at > updated_at:
                errors.append(f"{label} is later than campaign ledger updated_at_utc")
            if item.get("status") != "RETIRED_PRE_HARDWARE":
                errors.append(f"{label} status is not RETIRED_PRE_HARDWARE")
            if not isinstance(item.get("reason"), str) or not item.get("reason"):
                errors.append(f"{label} reason is missing")
            evidence_name = item.get("evidence_path")
            if (
                not isinstance(evidence_name, str)
                or not evidence_name
                or Path(evidence_name).is_absolute()
                or ".." in Path(evidence_name).parts
            ):
                errors.append(f"{label} evidence path is not repository-relative")
            else:
                evidence_path = resolve_path(evidence_name)
                generated_root = (ROOT / "evidence" / "generated").resolve(strict=False)
                if (
                    not _inside(evidence_path, generated_root)
                    or not evidence_path.is_file()
                    or evidence_path.is_symlink()
                ):
                    errors.append(f"{label} evidence is missing/outside generated evidence")
                elif not SHA256_RE.fullmatch(str(item.get("evidence_sha256", ""))):
                    errors.append(f"{label} evidence SHA256 is malformed")
                elif sha256_file(evidence_path) != str(item["evidence_sha256"]).lower():
                    errors.append(f"{label} evidence SHA256 mismatch")
            if item.get("hardware_attempt_consumed") is not False:
                errors.append(f"{label} must prove hardware_attempt_consumed=false")
        if len(retired_ids) != len(set(retired_ids)) or set(retired_ids) & seen_ids:
            errors.append("campaign ledger reuses a retired or launched run ID")
    if attempts:
        first_prior = attempts[0].get("prior_campaign_ledger_sha256")
        if retired_ids:
            if not SHA256_RE.fullmatch(str(first_prior)):
                errors.append(
                    "campaign first hardware attempt does not hash-bind the pre-hardware retirement ledger"
                )
        elif first_prior != ABSENT_LEDGER_SHA256:
            errors.append("campaign first attempt does not bind an absent prior ledger")
    expected_status = (
        "PASSED"
        if pass_count
        else "RECOVERY_REQUIRED"
        if unresolved_count
        else "EXHAUSTED"
        if len(attempts) == MAX_HARDWARE_ATTEMPTS
        else "READY"
    )
    if ledger.get("status") != expected_status:
        errors.append(
            f"campaign ledger status mismatch: expected={expected_status} observed={ledger.get('status')}"
        )
    return ledger, errors


def validate_next_attempt(
    policy: Mapping[str, Any],
    ledger: Mapping[str, Any] | None,
    *,
    run_id: str,
    hardware_attempt_number: Any,
) -> list[str]:
    errors: list[str] = []
    if isinstance(hardware_attempt_number, bool) or not isinstance(
        hardware_attempt_number, int
    ):
        errors.append("Stage66 campaign hardware attempt number must be an integer")
        attempt_number = 0
    else:
        attempt_number = hardware_attempt_number
    if not RUN_ID_RE.fullmatch(run_id):
        errors.append("Stage66 campaign run ID is malformed")
    expected_suffix = f"diag_stage66_c{attempt_number:02d}"
    if expected_suffix not in run_id:
        errors.append(f"Stage66 campaign run ID must contain {expected_suffix}")
    if run_id == policy.get("immutable_failed_baseline", {}).get("run_id"):
        errors.append("immutable r41 run ID can never be reused")
    attempts = [] if ledger is None else ledger.get("hardware_attempts", [])
    retired = [] if ledger is None else ledger.get("retired_pre_hardware_run_ids", [])
    if ledger is not None and ledger.get("status") != "READY":
        errors.append(f"campaign is not ready for another attempt: status={ledger.get('status')}")
    if not isinstance(attempts, list):
        attempts = []
        errors.append("campaign attempt history is malformed")
    expected_number = len(attempts) + 1
    if attempt_number != expected_number:
        errors.append(
            f"campaign hardware attempt number must be next contiguous value {expected_number}"
        )
    if expected_number > MAX_HARDWARE_ATTEMPTS:
        errors.append("campaign ten-attempt hardware limit is exhausted")
    used = {
        str(item.get("run_id"))
        for item in attempts
        if isinstance(item, dict) and item.get("run_id")
    }
    used.update(
        str(item.get("run_id"))
        for item in retired
        if isinstance(item, dict) and item.get("run_id")
    )
    if run_id in used:
        errors.append("campaign run ID was already launched or retired")
    return errors


def validate_active_attempt(
    ledger: Mapping[str, Any],
    *,
    run_id: str,
    hardware_attempt_number: int,
    source_commit: str,
    prior_campaign_ledger_sha256: str,
) -> list[str]:
    """Bind a child hardware wrapper to the one locked outer launch intent."""
    errors: list[str] = []
    attempts = ledger.get("hardware_attempts")
    if ledger.get("status") != "RECOVERY_REQUIRED":
        errors.append("campaign ledger is not locked in RECOVERY_REQUIRED during child launch")
    if not isinstance(attempts, list) or not attempts or not isinstance(attempts[-1], dict):
        return errors + ["campaign ledger has no terminal ACTIVE attempt"]
    attempt = attempts[-1]
    expected = {
        "status": "ACTIVE",
        "run_id": run_id,
        "hardware_attempt_number": hardware_attempt_number,
        "source_commit": source_commit,
        "prior_campaign_ledger_sha256": prior_campaign_ledger_sha256,
    }
    for key, value in expected.items():
        if attempt.get(key) != value:
            errors.append(f"campaign terminal ACTIVE attempt mismatch: {key}")
    return errors


def new_ledger(policy: Mapping[str, Any], policy_sha256: str) -> dict[str, Any]:
    stamp = now_utc()
    return {
        "schema": LEDGER_SCHEMA,
        "campaign_id": policy["campaign_id"],
        "policy_sha256": policy_sha256.lower(),
        "created_at_utc": stamp,
        "updated_at_utc": stamp,
        "status": "READY",
        "maximum_actual_hardware_attempts": MAX_HARDWARE_ATTEMPTS,
        "actual_hardware_attempt_count": 0,
        "hardware_attempts": [],
        "retired_pre_hardware_run_ids": [],
    }


def retire_pre_hardware_run_id(
    ledger: dict[str, Any],
    *,
    run_id: str,
    requested_hardware_attempt_number: int,
    source_commit: str,
    reason: str,
    evidence_path: str,
    evidence_sha256: str,
) -> None:
    """Retire a blocked preparation ID without consuming hardware quota."""

    if ledger.get("status") != "READY":
        raise RuntimeError(f"campaign ledger is not READY: {ledger.get('status')}")
    if isinstance(requested_hardware_attempt_number, bool) or not isinstance(
        requested_hardware_attempt_number, int
    ):
        raise RuntimeError("requested hardware attempt number must be an integer")
    expected_number = len(ledger.get("hardware_attempts", [])) + 1
    if requested_hardware_attempt_number != expected_number:
        raise RuntimeError(
            f"pre-hardware retirement must target next attempt number {expected_number}"
        )
    if not RUN_ID_RE.fullmatch(run_id) or (
        f"diag_stage66_c{requested_hardware_attempt_number:02d}" not in run_id
    ):
        raise RuntimeError("pre-hardware retirement run ID/attempt number is malformed")
    used = {
        str(item.get("run_id"))
        for item in ledger.get("hardware_attempts", [])
        if isinstance(item, dict)
    }
    used.update(
        str(item.get("run_id"))
        for item in ledger.get("retired_pre_hardware_run_ids", [])
        if isinstance(item, dict)
    )
    if run_id in used:
        raise RuntimeError("pre-hardware run ID is already launched or retired")
    if not COMMIT_RE.fullmatch(source_commit):
        raise RuntimeError("pre-hardware retirement source commit is malformed")
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("pre-hardware retirement reason is missing")
    relative = Path(evidence_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuntimeError("pre-hardware retirement evidence path is not repository-relative")
    resolved_evidence = resolve_path(evidence_path)
    generated_root = (ROOT / "evidence" / "generated").resolve(strict=False)
    if (
        not _inside(resolved_evidence, generated_root)
        or not resolved_evidence.is_file()
        or resolved_evidence.is_symlink()
    ):
        raise RuntimeError("pre-hardware retirement evidence is missing/outside generated evidence")
    if not SHA256_RE.fullmatch(evidence_sha256) or sha256_file(
        resolved_evidence
    ) != evidence_sha256.lower():
        raise RuntimeError("pre-hardware retirement evidence SHA256 mismatch")
    stamp = now_utc()
    ledger["retired_pre_hardware_run_ids"].append(
        {
            "run_id": run_id,
            "requested_hardware_attempt_number": requested_hardware_attempt_number,
            "source_commit": source_commit,
            "retired_at_utc": stamp,
            "status": "RETIRED_PRE_HARDWARE",
            "reason": reason.strip(),
            "evidence_path": evidence_path.replace("\\", "/"),
            "evidence_sha256": evidence_sha256.lower(),
            "hardware_attempt_consumed": False,
        }
    )
    ledger["updated_at_utc"] = stamp


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    data = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    with partial.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(partial, path)


@dataclass
class CampaignLock:
    path: Path
    payload: bytes
    released: bool = False

    @classmethod
    def acquire(cls, ledger_path: Path, owner: Mapping[str, Any]) -> "CampaignLock":
        lock_path = ledger_path.with_name("campaign_execution.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        token = secrets.token_hex(32)
        record = {
            "schema": "rf-comm-p7-stage66-campaign-lock-v1",
            "token_sha256": hashlib.sha256(token.encode("ascii")).hexdigest(),
            "stale_lock_auto_recovery": False,
            "acquired_at_utc": now_utc(),
            "owner": dict(owner),
        }
        payload = (json.dumps(record, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        try:
            fd = os.open(
                lock_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o600,
            )
        except FileExistsError as exc:
            raise RuntimeError(
                f"Stage66 campaign lock already exists and is never auto-recovered: {lock_path}"
            ) from exc
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        return cls(lock_path, payload)

    def release(self) -> None:
        if self.released:
            return
        if not self.path.is_file() or self.path.read_bytes() != self.payload:
            raise RuntimeError("Stage66 campaign lock identity changed; refusing removal")
        self.path.unlink()
        self.released = True


def begin_attempt(
    ledger: dict[str, Any],
    *,
    run_id: str,
    hardware_attempt_number: int,
    source_commit: str,
    sequence_plan_path: str,
    sequence_plan_sha256: str,
    execution_ledger_path: str,
    prior_campaign_ledger_sha256: str,
) -> None:
    if ledger.get("status") != "READY":
        raise RuntimeError(f"campaign ledger is not READY: {ledger.get('status')}")
    if hardware_attempt_number != len(ledger["hardware_attempts"]) + 1:
        raise RuntimeError("campaign attempt number changed before launch")
    if not RUN_ID_RE.fullmatch(run_id) or f"diag_stage66_c{hardware_attempt_number:02d}" not in run_id:
        raise RuntimeError("campaign run ID/attempt number is malformed")
    if not COMMIT_RE.fullmatch(source_commit):
        raise RuntimeError("campaign source commit is malformed")
    if not SHA256_RE.fullmatch(sequence_plan_sha256):
        raise RuntimeError("campaign sequence plan SHA256 is malformed")
    if prior_campaign_ledger_sha256 != ABSENT_LEDGER_SHA256 and not SHA256_RE.fullmatch(
        prior_campaign_ledger_sha256
    ):
        raise RuntimeError("campaign prior-ledger SHA256 is malformed")
    attempt = {
        "hardware_attempt_number": hardware_attempt_number,
        "run_id": run_id,
        "source_commit": source_commit,
        "sequence_plan_path": sequence_plan_path,
        "sequence_plan_sha256": sequence_plan_sha256,
        "execution_ledger_path": execution_ledger_path,
        "prior_campaign_ledger_sha256": prior_campaign_ledger_sha256,
        "launch_intent_at_utc": now_utc(),
        "ended_at_utc": None,
        "status": "ACTIVE",
        "failed_full_stage_ordinal": None,
        "stationary_launched": False,
        "complete_1800_second_stage66_pass": False,
        "execution_ledger_sha256": None,
        "independent_shutdown_recovery": None,
    }
    ledger["hardware_attempts"].append(attempt)
    ledger["actual_hardware_attempt_count"] = len(ledger["hardware_attempts"])
    # ACTIVE attempts are represented by RECOVERY_REQUIRED at ledger scope so a
    # crash can never look READY for a second run.
    ledger["status"] = "RECOVERY_REQUIRED"
    ledger["updated_at_utc"] = now_utc()


def finish_attempt(
    ledger: dict[str, Any],
    *,
    passed: bool,
    failed_full_stage_ordinal: int | None,
    stationary_launched: bool,
    execution_ledger_sha256: str,
) -> None:
    attempt = ledger["hardware_attempts"][-1]
    if attempt.get("status") != "ACTIVE":
        raise RuntimeError("campaign terminal update does not target one ACTIVE attempt")
    if not SHA256_RE.fullmatch(execution_ledger_sha256):
        raise RuntimeError("campaign terminal execution-ledger SHA256 is malformed")
    if passed and (failed_full_stage_ordinal is not None or not stationary_launched):
        raise RuntimeError("campaign PASS requires one launched Stage66 and no failed ordinal")
    if not passed and failed_full_stage_ordinal not in CAMPAIGN_FULL_STAGE_ORDINALS:
        raise RuntimeError("campaign failure ordinal must be one of exact 1--4,66")
    attempt["ended_at_utc"] = now_utc()
    attempt["failed_full_stage_ordinal"] = failed_full_stage_ordinal
    attempt["stationary_launched"] = bool(stationary_launched)
    attempt["complete_1800_second_stage66_pass"] = bool(passed)
    attempt["execution_ledger_sha256"] = execution_ledger_sha256
    attempt["status"] = "PASS" if passed else "FAIL_RECOVERY_REQUIRED"
    ledger["status"] = "PASSED" if passed else "RECOVERY_REQUIRED"
    ledger["updated_at_utc"] = now_utc()
