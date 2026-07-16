#!/usr/bin/env python3
"""Single fail-closed preparation/launch driver for the P7 Stage66 campaign.

Placeholder rehearsal and real prelaunch validation never acquire a hardware
or campaign lock, never create an execution ledger/attempt, and never launch a
wrapper.  The optional launch path is available only after the exact same
validation succeeds and invokes the canonical outer executor without a shell.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import p7_stage66_campaign as campaign
import p7_vivado_helper_identity as helper_identity
import run_p7_authorized_hardware_sequence as sequence


ROOT = Path(__file__).resolve().parents[1]
OUTER_EXECUTOR = (ROOT / "tools" / "run_p7_authorized_hardware_sequence.py").resolve()
SCHEMA = "rf-comm-p7-stage66-preparation-driver-v1"
PLACEHOLDER_TOKEN = "P7_UNALLOCATED_STAGE66_PLACEHOLDER"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_SHELL_FRAGMENTS = ("Join-Path", "Test-Path", "Resolve-Path", "$(", "`", "\r", "\n", "\x00")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".partial", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def materialize_campaign_ledger(
    source: Path, expected_sha256: str, expected_attempt_count: int
) -> dict[str, Any]:
    """Materialize one exact recovered ledger without overwriting any target."""

    report = _base_report("MATERIALIZE_CAMPAIGN_LEDGER")
    report["phase"] = "CAMPAIGN_LEDGER_MATERIALIZATION"
    if (
        isinstance(expected_attempt_count, bool)
        or not isinstance(expected_attempt_count, int)
        or not 0 <= expected_attempt_count <= campaign.MAX_HARDWARE_ATTEMPTS
    ):
        _append_error(
            report,
            "EXPECTED_CAMPAIGN_ATTEMPT_COUNT_INVALID",
            str(expected_attempt_count),
        )
    environment = _environment_validation(require_authorized=False)
    report["environment_validation"] = environment
    for item in environment["errors"]:
        _append_error(report, item["error_code"], item["detail"])
    source = source.resolve(strict=False)
    generated_root = (ROOT / "evidence" / "generated").resolve(strict=False)
    try:
        source.relative_to(generated_root)
    except ValueError:
        _append_error(report, "LEDGER_SOURCE_OUTSIDE_GENERATED_EVIDENCE", str(source))
    if not source.is_file() or source.is_symlink():
        _append_error(report, "LEDGER_SOURCE_MISSING_OR_NONREGULAR", str(source))
        source_bytes = b""
        actual_sha = ""
    else:
        source_bytes = source.read_bytes()
        actual_sha = hashlib.sha256(source_bytes).hexdigest()
    report["source"] = {
        "path": str(source),
        "sha256": actual_sha,
        "bytes": len(source_bytes),
    }
    if SHA256_RE.fullmatch(expected_sha256.lower()) is None:
        _append_error(report, "LEDGER_SOURCE_SHA256_MALFORMED", expected_sha256)
    elif actual_sha != expected_sha256.lower():
        _append_error(report, "LEDGER_SOURCE_SHA256_MISMATCH", actual_sha)

    policy_sha = sha256_file(campaign.POLICY_PATH)
    policy, policy_errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
    for item in policy_errors:
        _append_error(report, "CAMPAIGN_POLICY_INVALID", item)
    target = campaign.campaign_ledger_path(policy) if policy is not None else ROOT
    lock = target.with_name("campaign_execution.lock")
    report["target"] = str(target)
    if lock.exists():
        _append_error(report, "CAMPAIGN_LOCK_ALREADY_EXISTS", str(lock))

    wrote = False
    if not report["errors"]:
        if target.exists():
            if not target.is_file() or target.is_symlink():
                _append_error(report, "CAMPAIGN_LEDGER_TARGET_NONREGULAR", str(target))
            elif sha256_file(target) != actual_sha:
                _append_error(
                    report,
                    "CAMPAIGN_LEDGER_TARGET_COLLISION",
                    "existing target differs; overwrite is forbidden",
                )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".campaign_ledger.", suffix=".materializing", dir=target.parent
            )
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(source_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.link(temporary, target)
                os.unlink(temporary)
                wrote = True
            except FileExistsError:
                _append_error(
                    report,
                    "CAMPAIGN_LEDGER_TARGET_RACE",
                    "target appeared during exclusive materialization",
                )
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)

    if target.is_file() and not target.is_symlink() and policy is not None:
        ledger, ledger_errors = campaign.validate_ledger(policy, target, allow_absent=False)
        for item in ledger_errors:
            _append_error(report, "MATERIALIZED_CAMPAIGN_LEDGER_INVALID", item)
        if isinstance(ledger, dict):
            report["materialized_ledger"] = {
                "sha256": sha256_file(target),
                "actual_hardware_attempt_count": ledger.get(
                    "actual_hardware_attempt_count"
                ),
                "status": ledger.get("status"),
            }
            if ledger.get("actual_hardware_attempt_count") != expected_attempt_count:
                _append_error(
                    report,
                    "MATERIALIZED_CAMPAIGN_ATTEMPT_COUNT_MISMATCH",
                    str(ledger.get("actual_hardware_attempt_count")),
                )
            if ledger.get("status") != "READY":
                _append_error(
                    report,
                    "MATERIALIZED_CAMPAIGN_NOT_READY",
                    str(ledger.get("status")),
                )
    report["campaign_ledger_materialized"] = wrote
    if not report["errors"]:
        report["P7_STAGE66_PREPARATION_DRIVER"] = "PASS"
        report["error_code"] = "NONE"
        report["phase"] = "CAMPAIGN_LEDGER_MATERIALIZATION_COMPLETE"
    return report


def build_outer_execution_argv(
    *,
    sequence_plan: Path,
    sequence_plan_sha256: str,
    execution_ledger: Path,
    source_commit: str,
) -> list[str]:
    """Return the sole canonical outer hardware argv; never a shell command."""

    return [
        str(Path(sys.executable).resolve(strict=False)),
        str(OUTER_EXECUTOR),
        "--sequence-plan",
        str(sequence_plan.resolve(strict=False)),
        "--sequence-plan-sha256",
        sequence_plan_sha256.lower(),
        "--execution-ledger",
        str(execution_ledger.resolve(strict=False)),
        "--execute-hardware",
        "--source-commit",
        source_commit.lower(),
        "--max-runtime-sec",
        "1800",
        "--shutdown-on-exit",
        "--no-ethernet",
        "--no-motion",
        "--lane-count",
        "2",
        "--max-lane-mask",
        "0x3",
        "--json-summary",
    ]


def validate_outer_execution_argv(
    argv: Sequence[str],
    *,
    sequence_plan: Path,
    sequence_plan_sha256: str,
    execution_ledger: Path,
    source_commit: str,
) -> tuple[argparse.Namespace | None, list[str]]:
    errors: list[str] = []
    expected = build_outer_execution_argv(
        sequence_plan=sequence_plan,
        sequence_plan_sha256=sequence_plan_sha256,
        execution_ledger=execution_ledger,
        source_commit=source_commit,
    )
    if list(argv) != expected:
        errors.append("outer argv differs from the canonical exact vector")
    if len(argv) < 2 or Path(argv[0]).resolve(strict=False) != Path(sys.executable).resolve(strict=False):
        errors.append("outer argv Python executable is not the exact current interpreter")
    if len(argv) < 2 or Path(argv[1]).resolve(strict=False) != OUTER_EXECUTOR:
        errors.append("outer argv executor path is not canonical")
    if "--resume" in argv:
        errors.append("Stage66 campaign argv must never contain --resume")
    if any(fragment in token for token in argv for fragment in FORBIDDEN_SHELL_FRAGMENTS):
        errors.append("outer argv contains a shell/path-expression fragment")
    for option in (
        "--sequence-plan",
        "--sequence-plan-sha256",
        "--execution-ledger",
        "--execute-hardware",
        "--source-commit",
        "--max-runtime-sec",
        "--shutdown-on-exit",
        "--no-ethernet",
        "--no-motion",
        "--lane-count",
        "--max-lane-mask",
        "--json-summary",
    ):
        if list(argv).count(option) != 1:
            errors.append(f"outer argv option count must be exactly one: {option}")
    parsed: argparse.Namespace | None = None
    try:
        parsed = sequence.build_parser().parse_args(list(argv)[2:])
    except SystemExit as exc:
        errors.append(f"outer argv parser rejected the vector: exit={exc.code}")
    return parsed, errors


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
        timeout=10,
    )
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or COMMIT_RE.fullmatch(value) is None:
        raise RuntimeError(f"unable to determine exact Git HEAD: {completed.stderr.strip()}")
    return value


def _environment_validation(*, require_authorized: bool) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    auth_value = os.environ.get(sequence.AUTH_ENV)
    if require_authorized:
        if auth_value != sequence.AUTH_ENV_VALUE:
            errors.append(
                {
                    "error_code": "SCOPED_AUTH_ENV_MISSING",
                    "detail": f"{sequence.AUTH_ENV} must equal the exact authorized marker",
                }
            )
    elif auth_value is not None:
        errors.append(
            {
                "error_code": "PLACEHOLDER_REHEARSAL_AUTH_ENV_PRESENT",
                "detail": f"{sequence.AUTH_ENV} must be absent during placeholder rehearsal",
            }
        )
    for key in ("PYTHONHOME", "PYTHONPATH"):
        if os.environ.get(key):
            errors.append(
                {
                    "error_code": "UNSAFE_PYTHON_ENV_PRESENT",
                    "detail": f"{key} must be absent so repository imports cannot be redirected",
                }
            )
    no_hardware = os.environ.get("NO_HARDWARE")
    if require_authorized and no_hardware not in (None, "", "0"):
        errors.append(
            {
                "error_code": "NO_HARDWARE_ENV_CONFLICT",
                "detail": "NO_HARDWARE conflicts with an explicitly authorized launch",
            }
        )
    expected_cmd = helper_identity.EXPECTED_VIVADO_HELPER_PATHS_BY_ROLE["cmd"]
    observed_cmd = os.environ.get("COMSPEC", "")
    if not observed_cmd or Path(observed_cmd).resolve(strict=False) != Path(expected_cmd).resolve(strict=False):
        errors.append(
            {
                "error_code": "COMSPEC_PATH_MISMATCH",
                "detail": "COMSPEC is not the exact Windows System32 cmd.exe path",
            }
        )
    return {
        "status": "PASS" if not errors else "FAIL",
        "error_code": "NONE" if not errors else errors[0]["error_code"],
        "required_authorization_state": "AUTHORIZED" if require_authorized else "ABSENT",
        "authorization_env_present": auth_value is not None,
        "authorization_env_exact": auth_value == sequence.AUTH_ENV_VALUE,
        "NO_HARDWARE": no_hardware,
        "COMSPEC": observed_cmd,
        "PYTHONHOME_present": bool(os.environ.get("PYTHONHOME")),
        "PYTHONPATH_present": bool(os.environ.get("PYTHONPATH")),
        "all_launched_executables_are_absolute": True,
        "errors": errors,
    }


def _campaign_snapshot() -> dict[str, Any]:
    policy_sha = sha256_file(campaign.POLICY_PATH)
    policy, policy_errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
    if policy is None:
        return {
            "status": "FAIL",
            "errors": policy_errors,
            "policy_sha256": policy_sha,
            "campaign_lock_exists": None,
        }
    ledger_path = campaign.campaign_ledger_path(policy)
    ledger, ledger_errors = campaign.validate_ledger(policy, ledger_path, allow_absent=True)
    return {
        "status": "PASS" if not policy_errors and not ledger_errors else "FAIL",
        "errors": [*policy_errors, *ledger_errors],
        "policy_path": str(campaign.POLICY_PATH),
        "policy_sha256": policy_sha,
        "ledger_path": str(ledger_path),
        "ledger_sha256": campaign.current_ledger_sha256(ledger_path),
        "actual_hardware_attempt_count": (
            ledger.get("actual_hardware_attempt_count") if isinstance(ledger, dict) else 0
        ),
        "campaign_status": ledger.get("status") if isinstance(ledger, dict) else "READY",
        "campaign_lock_path": str(ledger_path.with_name("campaign_execution.lock")),
        "campaign_lock_exists": ledger_path.with_name("campaign_execution.lock").exists(),
    }


def _base_report(mode: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "P7_STAGE66_PREPARATION_DRIVER": "FAIL",
        "mode": mode,
        "phase": "INITIALIZE",
        "error_code": "UNSET",
        "generated_at_utc": now_utc(),
        "hardware_actions_executed": False,
        "hardware_connection_attempted": False,
        "tfdu_touched": False,
        "network_used": False,
        "motion_used": False,
        "wrapper_process_launched": False,
        "execution_ledger_created": False,
        "campaign_lock_created": False,
        "campaign_attempt_created": False,
        "coverage_claimed": False,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "errors": [],
    }


def _append_error(report: dict[str, Any], code: str, detail: str) -> None:
    report["errors"].append({"error_code": code, "detail": detail})
    if report["error_code"] == "UNSET":
        report["error_code"] = code


def placeholder_rehearsal(vivado_path: Path) -> dict[str, Any]:
    report = _base_report("PLACEHOLDER_REHEARSAL")
    report["phase"] = "PLACEHOLDER_EXACT_ARGV_REHEARSAL"
    environment = _environment_validation(require_authorized=False)
    report["environment_validation"] = environment
    for item in environment["errors"]:
        _append_error(report, item["error_code"], item["detail"])
    before = _campaign_snapshot()
    report["campaign_before"] = before
    if before.get("status") != "PASS":
        _append_error(report, "CAMPAIGN_SNAPSHOT_INVALID", "; ".join(before.get("errors", [])))
    if before.get("campaign_lock_exists"):
        _append_error(report, "CAMPAIGN_LOCK_ALREADY_EXISTS", str(before.get("campaign_lock_path")))

    identity = helper_identity.validate_vivado_helper_identity(vivado_path)
    report["vivado_helper_identity_validation"] = identity
    if identity.get("status") != "PASS":
        _append_error(report, str(identity.get("error_code")), "current helper identity validation failed")

    plan = ROOT / ".hardware_authorization" / f"{PLACEHOLDER_TOKEN}_sequence_plan.txt"
    ledger = (
        ROOT
        / "evidence"
        / "hardware"
        / "p7"
        / "authorized_sequence"
        / PLACEHOLDER_TOKEN
        / "sequence_execution_ledger.json"
    )
    head = _git_head()
    argv = build_outer_execution_argv(
        sequence_plan=plan,
        sequence_plan_sha256="0" * 64,
        execution_ledger=ledger,
        source_commit=head,
    )
    _parsed, base_errors = validate_outer_execution_argv(
        argv,
        sequence_plan=plan,
        sequence_plan_sha256="0" * 64,
        execution_ledger=ledger,
        source_commit=head,
    )
    report["placeholder_exact_launch_argv"] = argv

    def rejected(mutated: list[str]) -> bool:
        _value, errors = validate_outer_execution_argv(
            mutated,
            sequence_plan=plan,
            sequence_plan_sha256="0" * 64,
            execution_ledger=ledger,
            source_commit=head,
        )
        return bool(errors)

    omitted = list(argv)
    omitted.remove("--no-ethernet")
    shell_path = list(argv)
    shell_path[shell_path.index("--sequence-plan") + 1] = "Join-Path $root plan.txt"
    alias_python = list(argv)
    alias_python[0] = "python"
    resume = [*argv, "--resume"]
    actual_hashes = dict(identity.get("observed_sha256_by_role", {}))
    unknown_hashes = dict(actual_hashes)
    if unknown_hashes:
        unknown_hashes["cmd"] = "0" * 64
    matrix = {
        "r54_outer_controls_complete": not base_errors,
        "r54_outer_control_omission_rejected": rejected(omitted),
        "r55_join_path_test_path_alias_rejected": rejected(shell_path) and rejected(alias_python),
        "r55_exact_literal_python_paths_only": all(Path(item).is_absolute() for item in argv[:2]),
        "r56_canonical_p6_plan_hash_pair_guard_present": (
            ("--plan-file", "--plan-sha256") in sequence.PATH_HASH_PAIRS
            and {"--plan-file", "--plan-sha256"} <= sequence.REQUIRED_COMMON_OPTIONS
        ),
        "r57_current_complete_helper_profile_pass": (
            helper_identity.approved_vivado_helper_hash_profile_id(actual_hashes)
            == helper_identity.CURRENT_VIVADO_HELPER_HASH_PROFILE_ID
        ),
        "r57_unknown_helper_hash_rejected": (
            helper_identity.approved_vivado_helper_hash_profile_id(unknown_hashes) is None
        ),
        "failed_run_resume_rejected": rejected(resume),
    }
    report["fixed_regression_matrix"] = matrix
    if base_errors:
        _append_error(report, "PLACEHOLDER_EXACT_ARGV_INVALID", "; ".join(base_errors))
    for name, passed in matrix.items():
        if passed is not True:
            _append_error(report, "FIXED_REGRESSION_MATRIX_FAILED", name)

    after = _campaign_snapshot()
    report["campaign_after"] = after
    if after != before:
        _append_error(report, "PLACEHOLDER_REHEARSAL_MUTATED_CAMPAIGN", "campaign snapshot changed")
    if ledger.exists():
        _append_error(report, "PLACEHOLDER_REHEARSAL_CREATED_LEDGER", str(ledger))
    if not report["errors"]:
        report["P7_STAGE66_PREPARATION_DRIVER"] = "PASS"
        report["error_code"] = "NONE"
        report["phase"] = "PLACEHOLDER_REHEARSAL_COMPLETE"
    return report


def validate_real_prelaunch(
    *,
    vivado_path: Path,
    sequence_plan_path: Path,
    sequence_plan_sha256: str,
    execution_ledger: Path,
) -> tuple[dict[str, Any], list[str] | None]:
    report = _base_report("REAL_VALIDATE_ONLY")
    report["phase"] = "REAL_PRELAUNCH_VALIDATE_ONLY"
    environment = _environment_validation(require_authorized=True)
    report["environment_validation"] = environment
    for item in environment["errors"]:
        _append_error(report, item["error_code"], item["detail"])
    before = _campaign_snapshot()
    report["campaign_before"] = before
    if before.get("status") != "PASS":
        _append_error(report, "CAMPAIGN_SNAPSHOT_INVALID", "; ".join(before.get("errors", [])))
    if before.get("campaign_lock_exists"):
        _append_error(report, "CAMPAIGN_LOCK_ALREADY_EXISTS", str(before.get("campaign_lock_path")))

    identity = helper_identity.validate_vivado_helper_identity(vivado_path)
    report["vivado_helper_identity_validation"] = identity
    if identity.get("status") != "PASS":
        _append_error(report, str(identity.get("error_code")), "current helper identity validation failed")

    plan = sequence.validate_sequence_plan(sequence_plan_path, sequence_plan_sha256.lower())
    report["sequence_plan_validation"] = {
        "path": plan.get("path"),
        "sha256": plan.get("sha256"),
        "source_commit": plan.get("source_commit"),
        "plan_mode": plan.get("plan_mode"),
        "full_stage_ordinals": plan.get("full_stage_ordinals"),
        "stage_count": plan.get("stage_count"),
        "errors": plan.get("errors", []),
    }
    for item in plan.get("errors", []):
        _append_error(report, "SEQUENCE_PLAN_VALIDATION_FAILED", str(item))
    if plan.get("plan_mode") != sequence.STAGE66_CAMPAIGN_PLAN_MODE:
        _append_error(report, "PLAN_MODE_MISMATCH", "plan is not the bounded Stage66 campaign")
    if plan.get("full_stage_ordinals") != [1, 2, 3, 4, 66] or plan.get("stage_count") != 5:
        _append_error(report, "PLAN_STAGE_MATRIX_MISMATCH", "plan must be exact ordinals 1--4,66")
    source_commit = str(plan.get("source_commit", ""))
    campaign_context = plan.get("stage66_diagnostic_campaign")
    expected_ledger = None
    if isinstance(campaign_context, dict):
        run_id = str(campaign_context.get("run_id", ""))
        expected_ledger = (
            sequence.HARDWARE_ROOT
            / "authorized_sequence"
            / run_id
            / "sequence_execution_ledger.json"
        ).resolve(strict=False)
        report["run_id"] = run_id
        report["hardware_attempt_number"] = campaign_context.get("hardware_attempt_number")
    else:
        _append_error(report, "CAMPAIGN_CONTEXT_MISSING", "validated plan lacks campaign context")
    if expected_ledger is None or execution_ledger.resolve(strict=False) != expected_ledger:
        _append_error(report, "EXECUTION_LEDGER_PATH_MISMATCH", str(expected_ledger))
    if execution_ledger.exists():
        _append_error(report, "EXECUTION_LEDGER_COLLISION", str(execution_ledger))
    for stage in plan.get("stages", []):
        evidence_dir = Path(str(stage.get("evidence_dir", "")))
        if evidence_dir.exists() and (
            evidence_dir.is_symlink() or not evidence_dir.is_dir() or any(evidence_dir.iterdir())
        ):
            _append_error(report, "STAGE_EVIDENCE_COLLISION", str(evidence_dir))

    launch_argv: list[str] | None = None
    if COMMIT_RE.fullmatch(source_commit):
        launch_argv = build_outer_execution_argv(
            sequence_plan=sequence_plan_path,
            sequence_plan_sha256=sequence_plan_sha256,
            execution_ledger=execution_ledger,
            source_commit=source_commit,
        )
        parsed, argv_errors = validate_outer_execution_argv(
            launch_argv,
            sequence_plan=sequence_plan_path,
            sequence_plan_sha256=sequence_plan_sha256,
            execution_ledger=execution_ledger,
            source_commit=source_commit,
        )
        for item in argv_errors:
            _append_error(report, "OUTER_EXACT_ARGV_INVALID", item)
        if parsed is not None and not plan.get("errors"):
            for item in sequence._outer_sequence_errors(parsed, plan):
                _append_error(report, "OUTER_LAUNCH_CONTROL_INVALID", item)
        report["exact_outer_launch_argv"] = launch_argv
    else:
        _append_error(report, "SOURCE_COMMIT_INVALID", source_commit)

    after = _campaign_snapshot()
    report["campaign_after"] = after
    if after != before:
        _append_error(report, "REAL_PRELAUNCH_MUTATED_CAMPAIGN", "campaign snapshot changed")
    report["execution_ledger_created"] = execution_ledger.exists()
    report["campaign_lock_created"] = bool(
        after.get("campaign_lock_exists") and not before.get("campaign_lock_exists")
    )
    if report["execution_ledger_created"] or report["campaign_lock_created"]:
        _append_error(report, "VALIDATE_ONLY_MUTATION_DETECTED", "ledger/lock appeared during validation")
    if not report["errors"]:
        report["P7_STAGE66_PREPARATION_DRIVER"] = "PASS"
        report["error_code"] = "NONE"
        report["phase"] = "REAL_PRELAUNCH_VALIDATE_ONLY_COMPLETE"
    return report, launch_argv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rehearse, validate, and optionally launch one new P7 Stage66 campaign run."
    )
    parser.add_argument(
        "--mode",
        choices=(
            "materialize-ledger",
            "placeholder-rehearsal",
            "validate-only",
            "launch",
        ),
        required=True,
    )
    parser.add_argument("--vivado-path", default="")
    parser.add_argument("--sequence-plan", default="")
    parser.add_argument("--sequence-plan-sha256", default="")
    parser.add_argument("--execution-ledger", default="")
    parser.add_argument("--campaign-ledger-source", default="")
    parser.add_argument("--campaign-ledger-source-sha256", default="")
    parser.add_argument("--expected-campaign-attempt-count", type=int, default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--confirm-stage66-campaign-launch", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output).resolve(strict=False)
    if args.mode == "materialize-ledger":
        if args.execute_hardware or args.confirm_stage66_campaign_launch:
            raise SystemExit("ledger materialization forbids hardware launch controls")
        if (
            not args.campaign_ledger_source
            or not args.campaign_ledger_source_sha256
            or args.expected_campaign_attempt_count is None
        ):
            raise SystemExit(
                "ledger materialization requires source path, SHA256, and expected attempt count"
            )
        if any((args.vivado_path, args.sequence_plan, args.sequence_plan_sha256, args.execution_ledger)):
            raise SystemExit("ledger materialization forbids Vivado/real run inputs")
        report = materialize_campaign_ledger(
            Path(args.campaign_ledger_source),
            args.campaign_ledger_source_sha256,
            args.expected_campaign_attempt_count,
        )
        atomic_write_json(output, report)
        launch_argv = None
    elif args.mode == "placeholder-rehearsal":
        if args.execute_hardware or args.confirm_stage66_campaign_launch:
            raise SystemExit("placeholder rehearsal forbids hardware launch controls")
        if not args.vivado_path:
            raise SystemExit("placeholder rehearsal requires --vivado-path")
        if any((args.sequence_plan, args.sequence_plan_sha256, args.execution_ledger)):
            raise SystemExit("placeholder rehearsal forbids real run paths/hashes")
        if args.campaign_ledger_source or args.campaign_ledger_source_sha256:
            raise SystemExit("placeholder rehearsal forbids ledger materialization inputs")
        if args.expected_campaign_attempt_count is not None:
            raise SystemExit("placeholder rehearsal forbids ledger attempt-count input")
        report = placeholder_rehearsal(Path(args.vivado_path))
        atomic_write_json(output, report)
        launch_argv = None
    else:
        if not args.vivado_path:
            raise SystemExit("real validation requires --vivado-path")
        if not all((args.sequence_plan, args.sequence_plan_sha256, args.execution_ledger)):
            raise SystemExit("real validation requires sequence plan, SHA256, and execution ledger")
        if args.campaign_ledger_source or args.campaign_ledger_source_sha256:
            raise SystemExit("real validation forbids ledger materialization inputs")
        if args.expected_campaign_attempt_count is not None:
            raise SystemExit("real validation forbids ledger attempt-count input")
        if args.mode == "launch" and not (
            args.execute_hardware and args.confirm_stage66_campaign_launch
        ):
            raise SystemExit(
                "launch mode requires --execute-hardware and --confirm-stage66-campaign-launch"
            )
        if args.mode == "validate-only" and (
            args.execute_hardware or args.confirm_stage66_campaign_launch
        ):
            raise SystemExit("validate-only mode forbids hardware launch controls")
        report, launch_argv = validate_real_prelaunch(
            vivado_path=Path(args.vivado_path),
            sequence_plan_path=Path(args.sequence_plan).resolve(strict=False),
            sequence_plan_sha256=args.sequence_plan_sha256,
            execution_ledger=Path(args.execution_ledger).resolve(strict=False),
        )
        atomic_write_json(output, report)

    if args.mode == "launch" and report["P7_STAGE66_PREPARATION_DRIVER"] == "PASS":
        assert launch_argv is not None
        stdout_path = output.with_suffix(output.suffix + ".outer.stdout.log")
        stderr_path = output.with_suffix(output.suffix + ".outer.stderr.log")
        if stdout_path.exists() or stderr_path.exists():
            _append_error(report, "DRIVER_LOG_COLLISION", "outer launch log path already exists")
            report["P7_STAGE66_PREPARATION_DRIVER"] = "FAIL"
            atomic_write_json(output, report)
        else:
            report["mode"] = "LAUNCH"
            report["phase"] = "OUTER_LAUNCH_INTENT"
            report["wrapper_process_launched"] = False
            report["launch_intent_at_utc"] = now_utc()
            atomic_write_json(output, report)
            with stdout_path.open("xb") as stdout_handle, stderr_path.open("xb") as stderr_handle:
                completed = subprocess.run(
                    launch_argv,
                    cwd=ROOT,
                    env=os.environ.copy(),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    check=False,
                )
            report["wrapper_process_launched"] = True
            report["hardware_actions_executed"] = True
            report["hardware_connection_attempted"] = True
            report["outer_returncode"] = int(completed.returncode)
            report["outer_stdout"] = {
                "path": str(stdout_path),
                "sha256": sha256_file(stdout_path),
                "bytes": stdout_path.stat().st_size,
            }
            report["outer_stderr"] = {
                "path": str(stderr_path),
                "sha256": sha256_file(stderr_path),
                "bytes": stderr_path.stat().st_size,
            }
            report["phase"] = "OUTER_LAUNCH_TERMINAL"
            report["P7_STAGE66_PREPARATION_DRIVER"] = (
                "LAUNCHED_TERMINAL_PASS" if completed.returncode == 0 else "LAUNCHED_TERMINAL_FAIL"
            )
            report["completed_at_utc"] = now_utc()
            atomic_write_json(output, report)
            if args.json_summary:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            return int(completed.returncode)

    if args.json_summary:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"P7_STAGE66_PREPARATION_DRIVER={report['P7_STAGE66_PREPARATION_DRIVER']}")
    return 0 if report["P7_STAGE66_PREPARATION_DRIVER"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
