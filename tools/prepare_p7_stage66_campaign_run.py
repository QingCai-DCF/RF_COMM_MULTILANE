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
import shutil
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
BUILD_MATERIALIZATION_NAMES = ("p6_ps_candidate", "p7_ps_vitis_workspace")
COLLISION_ROOTS_RELATIVE = (
    Path(".hardware_authorization"),
    Path("build/p7_authorized_sequence"),
    Path("evidence/hardware/p7/authorized_sequence"),
    Path("evidence/generated"),
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_link_or_junction(path: Path) -> bool:
    is_junction = getattr(os.path, "isjunction", lambda _path: False)
    return path.is_symlink() or bool(is_junction(path))


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


def canonical_tree_record(root: Path) -> dict[str, Any]:
    """Hash a regular-file tree using the canonical P7 materialization format."""

    root = root.resolve(strict=False)
    errors: list[str] = []
    records: list[tuple[str, int, str]] = []
    if not os.path.lexists(root):
        errors.append(f"tree is absent: {root}")
    elif _is_link_or_junction(root) or not root.is_dir():
        errors.append(f"tree root is not a regular directory: {root}")
    else:
        try:
            for directory, directory_names, file_names in os.walk(
                root, topdown=True, followlinks=False
            ):
                directory_names.sort()
                file_names.sort()
                directory_path = Path(directory)
                for name in directory_names:
                    candidate = directory_path / name
                    if _is_link_or_junction(candidate):
                        errors.append(f"tree contains a directory link/junction: {candidate}")
                for name in file_names:
                    candidate = directory_path / name
                    relative = candidate.relative_to(root).as_posix()
                    if _is_link_or_junction(candidate) or not candidate.is_file():
                        errors.append(f"tree contains a non-regular file: {candidate}")
                        continue
                    size = candidate.stat().st_size
                    records.append((relative, size, sha256_file(candidate)))
        except OSError as exc:
            errors.append(f"tree enumeration/hash failed: {exc}")
    # Match the established Windows PowerShell `Sort-Object path` evidence:
    # path ordering is case-insensitive while the serialized path keeps case.
    records.sort(key=lambda item: item[0].casefold())
    canonical = "".join(
        f"{relative}\t{size}\t{digest}\n" for relative, size, digest in records
    ).encode("utf-8")
    return {
        "path": str(root),
        "canonicalization": "relative POSIX path TAB byte_count TAB lowercase-sha256 LF; Windows case-insensitive path sort",
        "file_count": len(records),
        "byte_count": sum(item[1] for item in records),
        "tree_sha256": hashlib.sha256(canonical).hexdigest() if not errors else "",
        "errors": errors,
    }


def _git_worktree_identity(root: Path) -> dict[str, Any]:
    root = root.resolve(strict=False)
    result: dict[str, Any] = {
        "path": str(root),
        "head": "",
        "tracked_clean": False,
        "errors": [],
    }
    for label, argv in (
        ("head", ["git", "-C", str(root), "rev-parse", "HEAD"]),
        (
            "status",
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
        ),
    ):
        try:
            completed = subprocess.run(
                argv,
                text=True,
                encoding="utf-8",
                errors="strict",
                capture_output=True,
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            result["errors"].append(f"git {label} failed: {exc}")
            continue
        if completed.returncode != 0:
            result["errors"].append(
                f"git {label} returned {completed.returncode}: {completed.stderr.strip()}"
            )
            continue
        if label == "head":
            result["head"] = completed.stdout.strip().lower()
            if COMMIT_RE.fullmatch(result["head"]) is None:
                result["errors"].append("git HEAD is not an exact 40-hex commit")
        else:
            result["tracked_clean"] = completed.stdout == ""
            result["tracked_status"] = completed.stdout.splitlines()
            if not result["tracked_clean"]:
                result["errors"].append("worktree has tracked changes")
    result["status"] = "PASS" if not result["errors"] else "FAIL"
    return result


def inspect_build_materialization(
    *,
    source_root: Path,
    source_commit: str,
    expected_tree_sha256_by_name: Mapping[str, str],
) -> dict[str, Any]:
    """Validate every predictable build-tree input without copying anything."""

    source_root_input = source_root
    source_root = source_root.resolve(strict=False)
    destination_root = (ROOT / "build").resolve(strict=False)
    report: dict[str, Any] = {
        "status": "FAIL",
        "source_root": str(source_root),
        "destination_root": str(destination_root),
        "source_commit_expected": source_commit.lower(),
        "trees": {},
        "destination_paths_absent": False,
        "copy_started": False,
        "errors": [],
    }
    if COMMIT_RE.fullmatch(source_commit.lower()) is None:
        report["errors"].append(
            {"error_code": "BUILD_SOURCE_COMMIT_MALFORMED", "detail": source_commit}
        )
    if not source_root_input.is_absolute():
        report["errors"].append(
            {
                "error_code": "BUILD_SOURCE_ROOT_NOT_ABSOLUTE",
                "detail": str(source_root_input),
            }
        )
    source_identity = _git_worktree_identity(source_root)
    destination_identity = _git_worktree_identity(ROOT)
    report["source_worktree"] = source_identity
    report["destination_worktree"] = destination_identity
    for label, identity in (
        ("SOURCE", source_identity),
        ("DESTINATION", destination_identity),
    ):
        for detail in identity.get("errors", []):
            report["errors"].append(
                {"error_code": f"BUILD_{label}_WORKTREE_INVALID", "detail": detail}
            )
    if source_identity.get("head") != source_commit.lower():
        report["errors"].append(
            {
                "error_code": "BUILD_SOURCE_COMMIT_MISMATCH",
                "detail": str(source_identity.get("head")),
            }
        )
    destinations_absent = True
    for name in BUILD_MATERIALIZATION_NAMES:
        expected = str(expected_tree_sha256_by_name.get(name, "")).lower()
        source = source_root / "build" / name
        destination = destination_root / name
        source_record = canonical_tree_record(source)
        tree = {
            "source": source_record,
            "destination": str(destination),
            "destination_lexists": os.path.lexists(destination),
            "expected_tree_sha256": expected,
        }
        report["trees"][name] = tree
        if SHA256_RE.fullmatch(expected) is None:
            report["errors"].append(
                {"error_code": "BUILD_TREE_SHA256_MALFORMED", "detail": name}
            )
        for detail in source_record["errors"]:
            report["errors"].append(
                {"error_code": "BUILD_SOURCE_TREE_INVALID", "detail": f"{name}: {detail}"}
            )
        if source_record["tree_sha256"] != expected:
            report["errors"].append(
                {
                    "error_code": "BUILD_SOURCE_TREE_SHA256_MISMATCH",
                    "detail": f"{name}: {source_record['tree_sha256']}",
                }
            )
        if tree["destination_lexists"]:
            destinations_absent = False
            report["errors"].append(
                {"error_code": "BUILD_DESTINATION_COLLISION", "detail": str(destination)}
            )
    report["destination_paths_absent"] = destinations_absent
    if not report["errors"]:
        report["status"] = "PASS"
    return report


def _registered_worktree_roots() -> tuple[list[Path], list[str]]:
    try:
        completed = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="strict",
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], [f"git worktree list failed: {exc}"]
    if completed.returncode != 0:
        return [], [
            f"git worktree list returned {completed.returncode}: {completed.stderr.strip()}"
        ]
    roots = [
        Path(line.removeprefix("worktree ")).resolve(strict=False)
        for line in completed.stdout.splitlines()
        if line.startswith("worktree ")
    ]
    return roots, []


def _collision_workspace_roots() -> tuple[list[Path], list[str]]:
    registered, errors = _registered_worktree_roots()
    roots = {root.resolve(strict=False) for root in registered}
    pools: set[Path] = set()
    for root in registered:
        if (
            root.name.casefold() == "rf_comm_multilane"
            and root.parent.parent.name.casefold() in {"codexworktrees", "worktrees"}
        ):
            pools.add(root.parent.parent.resolve(strict=False))
    for pool in sorted(pools, key=lambda path: str(path).casefold()):
        try:
            for child in pool.iterdir():
                candidate = child / "RF_COMM_MULTILANE"
                if candidate.is_dir() and not _is_link_or_junction(candidate):
                    roots.add(candidate.resolve(strict=False))
        except OSError as exc:
            errors.append(f"worktree pool scan failed at {pool}: {exc}")
    return sorted(roots, key=lambda path: str(path).casefold()), errors


def run_id_filename_collision_report(run_id: str) -> dict[str, Any]:
    roots, errors = _collision_workspace_roots()
    collisions: set[str] = set()
    for root in roots:
        for relative in COLLISION_ROOTS_RELATIVE:
            collision_root = root / relative
            if not collision_root.is_dir() or _is_link_or_junction(collision_root):
                continue
            try:
                for directory, directory_names, file_names in os.walk(
                    collision_root, topdown=True, followlinks=False
                ):
                    for name in (*directory_names, *file_names):
                        if run_id.casefold() in name.casefold():
                            collisions.add(str((Path(directory) / name).resolve(strict=False)))
            except OSError as exc:
                errors.append(f"collision scan failed below {collision_root}: {exc}")
    return {
        "status": "PASS" if not errors and not collisions else "FAIL",
        "run_id": run_id,
        "workspace_root_count": len(roots),
        "collision_roots_relative": [path.as_posix() for path in COLLISION_ROOTS_RELATIVE],
        "collisions": sorted(collisions),
        "errors": errors,
    }


def _campaign_candidate_validation(run_id: str, attempt_number: int) -> dict[str, Any]:
    policy_sha = sha256_file(campaign.POLICY_PATH)
    policy, policy_errors = campaign.validate_policy(campaign.POLICY_PATH, policy_sha)
    if policy is None:
        return {
            "status": "FAIL",
            "policy_sha256": policy_sha,
            "errors": policy_errors,
        }
    ledger_path = campaign.campaign_ledger_path(policy)
    ledger, ledger_errors = campaign.validate_ledger(policy, ledger_path, allow_absent=False)
    next_errors = (
        campaign.validate_next_attempt(
            policy,
            ledger,
            run_id=run_id,
            hardware_attempt_number=attempt_number,
        )
        if isinstance(ledger, dict)
        else ["campaign ledger is unavailable"]
    )
    errors = [*policy_errors, *ledger_errors, *next_errors]
    return {
        "status": "PASS" if not errors else "FAIL",
        "policy_sha256": policy_sha,
        "ledger_path": str(ledger_path),
        "ledger_sha256": campaign.current_ledger_sha256(ledger_path),
        "actual_hardware_attempt_count": (
            ledger.get("actual_hardware_attempt_count") if isinstance(ledger, dict) else None
        ),
        "campaign_status": ledger.get("status") if isinstance(ledger, dict) else None,
        "run_id": run_id,
        "requested_hardware_attempt_number": attempt_number,
        "errors": errors,
    }


def materialize_build_trees(
    *,
    source_root: Path,
    source_commit: str,
    expected_tree_sha256_by_name: Mapping[str, str],
    run_id: str,
    attempt_number: int,
) -> dict[str, Any]:
    """Copy both immutable build trees only after one shared fail-closed preflight."""

    report = _base_report("MATERIALIZE_BUILD_TREES")
    report["phase"] = "BUILD_TREE_MATERIALIZATION_PREFLIGHT"
    report["run_id"] = run_id
    report["requested_hardware_attempt_number"] = attempt_number
    environment = _environment_validation(require_authorized=False)
    report["environment_validation"] = environment
    for item in environment["errors"]:
        _append_error(report, item["error_code"], item["detail"])
    before = _campaign_snapshot()
    report["campaign_before"] = before
    if before.get("status") != "PASS" or before.get("campaign_lock_exists"):
        _append_error(report, "CAMPAIGN_SNAPSHOT_INVALID", json.dumps(before, sort_keys=True))
    candidate = _campaign_candidate_validation(run_id, attempt_number)
    report["campaign_candidate_validation"] = candidate
    for detail in candidate.get("errors", []):
        _append_error(report, "CAMPAIGN_CANDIDATE_INVALID", str(detail))
    collisions = run_id_filename_collision_report(run_id)
    report["run_id_filename_collision_validation"] = collisions
    for detail in collisions.get("errors", []):
        _append_error(report, "RUN_ID_COLLISION_SCAN_FAILED", detail)
    for detail in collisions.get("collisions", []):
        _append_error(report, "RUN_ID_FILENAME_COLLISION", detail)
    inspection = inspect_build_materialization(
        source_root=source_root,
        source_commit=source_commit,
        expected_tree_sha256_by_name=expected_tree_sha256_by_name,
    )
    report["build_materialization_preflight"] = inspection
    for item in inspection["errors"]:
        _append_error(report, item["error_code"], item["detail"])

    materializations: dict[str, Any] = {}
    report["materializations"] = materializations
    if not report["errors"]:
        report["phase"] = "BUILD_TREE_MATERIALIZATION"
        inspection["copy_started"] = True
        for name in BUILD_MATERIALIZATION_NAMES:
            source = source_root.resolve(strict=False) / "build" / name
            destination = (ROOT / "build" / name).resolve(strict=False)
            destination.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(
                    prefix=f".{name}.materializing.", dir=destination.parent
                )
            ).resolve(strict=False)
            item: dict[str, Any] = {
                "source": str(source),
                "destination": str(destination),
                "staging": str(staging),
                "copy_started": True,
                "materialized": False,
            }
            materializations[name] = item
            try:
                shutil.copytree(
                    source,
                    staging,
                    dirs_exist_ok=True,
                    symlinks=False,
                    copy_function=shutil.copy2,
                )
                staged_record = canonical_tree_record(staging)
                item["staging_tree"] = staged_record
                expected = expected_tree_sha256_by_name[name].lower()
                if staged_record["errors"] or staged_record["tree_sha256"] != expected:
                    _append_error(
                        report,
                        "BUILD_STAGING_TREE_MISMATCH",
                        f"{name}: {staged_record}",
                    )
                    break
                if os.path.lexists(destination):
                    _append_error(
                        report,
                        "BUILD_DESTINATION_RACE_COLLISION",
                        str(destination),
                    )
                    break
                os.rename(staging, destination)
                destination_record = canonical_tree_record(destination)
                item["destination_tree"] = destination_record
                if (
                    destination_record["errors"]
                    or destination_record["tree_sha256"] != expected
                ):
                    _append_error(
                        report,
                        "BUILD_DESTINATION_TREE_MISMATCH",
                        f"{name}: {destination_record}",
                    )
                    break
                item["materialized"] = True
            except OSError as exc:
                _append_error(report, "BUILD_MATERIALIZATION_IO_ERROR", f"{name}: {exc}")
                break

    after = _campaign_snapshot()
    report["campaign_after"] = after
    if after != before:
        _append_error(report, "BUILD_MATERIALIZATION_MUTATED_CAMPAIGN", "campaign changed")
    report["campaign_lock_created"] = bool(
        after.get("campaign_lock_exists") and not before.get("campaign_lock_exists")
    )
    report["campaign_attempt_created"] = False
    report["build_materialization_completed"] = bool(materializations) and all(
        item.get("materialized") is True for item in materializations.values()
    ) and len(materializations) == len(BUILD_MATERIALIZATION_NAMES)
    if not report["errors"] and report["build_materialization_completed"]:
        report["P7_STAGE66_PREPARATION_DRIVER"] = "PASS"
        report["error_code"] = "NONE"
        report["phase"] = "BUILD_TREE_MATERIALIZATION_COMPLETE"
    return report


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


def placeholder_rehearsal(
    vivado_path: Path,
    *,
    build_source_root: Path,
    build_source_commit: str,
    expected_build_tree_sha256_by_name: Mapping[str, str],
) -> dict[str, Any]:
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

    build_preflight = inspect_build_materialization(
        source_root=build_source_root,
        source_commit=build_source_commit,
        expected_tree_sha256_by_name=expected_build_tree_sha256_by_name,
    )
    report["build_materialization_rehearsal"] = build_preflight
    for item in build_preflight["errors"]:
        _append_error(report, item["error_code"], item["detail"])

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
        "r58_repository_build_materialization_preflight_pass": (
            build_preflight.get("status") == "PASS"
            and build_preflight.get("copy_started") is False
            and build_preflight.get("destination_paths_absent") is True
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
            "materialize-builds",
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
    parser.add_argument("--build-materialization-source-root", default="")
    parser.add_argument("--build-materialization-source-commit", default="")
    parser.add_argument("--p6-build-tree-sha256", default="")
    parser.add_argument("--p7-build-tree-sha256", default="")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--stage66-campaign-attempt-number", type=int, default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--confirm-stage66-campaign-launch", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output).resolve(strict=False)
    build_inputs = (
        args.build_materialization_source_root,
        args.build_materialization_source_commit,
        args.p6_build_tree_sha256,
        args.p7_build_tree_sha256,
    )
    run_identity_present = bool(args.run_id) or args.stage66_campaign_attempt_number is not None
    expected_build_hashes = {
        "p6_ps_candidate": args.p6_build_tree_sha256,
        "p7_ps_vitis_workspace": args.p7_build_tree_sha256,
    }
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
        if any(
            (
                args.vivado_path,
                args.sequence_plan,
                args.sequence_plan_sha256,
                args.execution_ledger,
                *build_inputs,
                run_identity_present,
            )
        ):
            raise SystemExit("ledger materialization forbids Vivado/build/real run inputs")
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
        if not all(build_inputs):
            raise SystemExit("placeholder rehearsal requires every exact build materialization input")
        if run_identity_present:
            raise SystemExit("placeholder rehearsal forbids allocation of a real run identity")
        report = placeholder_rehearsal(
            Path(args.vivado_path),
            build_source_root=Path(args.build_materialization_source_root),
            build_source_commit=args.build_materialization_source_commit,
            expected_build_tree_sha256_by_name=expected_build_hashes,
        )
        atomic_write_json(output, report)
        launch_argv = None
    elif args.mode == "materialize-builds":
        if args.execute_hardware or args.confirm_stage66_campaign_launch:
            raise SystemExit("build materialization forbids hardware launch controls")
        if any((args.vivado_path, args.sequence_plan, args.sequence_plan_sha256, args.execution_ledger)):
            raise SystemExit("build materialization forbids Vivado/real plan inputs")
        if args.campaign_ledger_source or args.campaign_ledger_source_sha256:
            raise SystemExit("build materialization forbids ledger materialization inputs")
        if args.expected_campaign_attempt_count is not None:
            raise SystemExit("build materialization forbids ledger attempt-count input")
        if not all(build_inputs) or not args.run_id or args.stage66_campaign_attempt_number is None:
            raise SystemExit("build materialization requires exact build inputs and real run identity")
        report = materialize_build_trees(
            source_root=Path(args.build_materialization_source_root),
            source_commit=args.build_materialization_source_commit,
            expected_tree_sha256_by_name=expected_build_hashes,
            run_id=args.run_id,
            attempt_number=args.stage66_campaign_attempt_number,
        )
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
        if any(build_inputs) or run_identity_present:
            raise SystemExit("real validation derives run identity from the plan and forbids build inputs")
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
