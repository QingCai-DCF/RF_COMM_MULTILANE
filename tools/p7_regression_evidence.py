#!/usr/bin/env python3
"""Fail-closed validation for exactly-once P7 complete-suite evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BUILD_ROOT = (ROOT / "build").resolve(strict=False)
REGRESSION_SCHEMA = "rf-comm-p7-complete-regression-suites-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required_suite_commands(
    python_executable: str = sys.executable,
) -> dict[str, list[str]]:
    return {
        "top_level_discovery": [
            python_executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test*.py",
            "-v",
        ],
        "tests_p7_discovery": [
            python_executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests/p7",
            "-p",
            "test_*.py",
            "-v",
        ],
    }


def validate_regression_summary(
    path: Path,
    expected_sha256: str,
    source_commit: str,
    *,
    root: Path = ROOT,
    python_executable: str = sys.executable,
) -> tuple[bool, dict[str, Any]]:
    """Validate immutable complete-suite evidence without invoking any test."""

    errors: list[str] = []
    supplied_path = path.expanduser()
    resolved_path = supplied_path.resolve(strict=False)
    build_root = (root / "build").resolve(strict=False)
    if (
        supplied_path.is_symlink()
        or not resolved_path.is_relative_to(build_root)
        or resolved_path == build_root
        or not resolved_path.is_file()
    ):
        return False, {
            "path": str(resolved_path),
            "errors": [
                "validated regression summary must be a non-symlink regular file under build"
            ],
        }

    actual_sha256 = sha256_file(resolved_path)
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        errors.append("validated regression summary expected SHA256 is invalid")
    elif actual_sha256 != expected_sha256.lower():
        errors.append("validated regression summary SHA256 mismatch")
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return False, {
            "path": str(resolved_path),
            "sha256": actual_sha256,
            "errors": errors + [f"invalid regression JSON: {exc}"],
        }

    normalized_commit = source_commit.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", normalized_commit):
        errors.append("current source commit is invalid")
    if not isinstance(payload, dict):
        return False, {
            "path": str(resolved_path),
            "sha256": actual_sha256,
            "payload": payload,
            "errors": errors
            + ["validated regression summary root must be a JSON object"],
        }
    if (
        payload.get("schema") != REGRESSION_SCHEMA
        or payload.get("status") != "PASS"
    ):
        errors.append("validated regression summary schema/status is not PASS")
    if str(payload.get("source_commit", "")).lower() != normalized_commit:
        errors.append("validated regression summary source commit mismatch")
    if str(payload.get("source_commit_after_suites", "")).lower() != normalized_commit:
        errors.append("validated regression post-suite source commit mismatch")
    if payload.get("dirty_worktree_before_suites") is not False:
        errors.append("validated regression suites did not start from clean source")
    if payload.get("dirty_worktree_after_suites") is not False:
        errors.append("validated regression suites did not leave source clean")
    if payload.get("source_commit_unchanged") is not True:
        errors.append("validated regression source commit changed during suites")
    if (
        payload.get("NO_HARDWARE_ACTIONS_EXECUTED") is not True
        or payload.get("HARDWARE_ACCEPTANCE") != "PENDING_HW"
    ):
        errors.append("validated regression summary violates no-hardware/PENDING boundary")

    expected_commands = required_suite_commands(python_executable)
    expected_names = tuple(expected_commands)
    invocation_count = payload.get("FULL_SUITE_INVOCATION_COUNT")
    invocation_counts = payload.get("suite_invocation_count_by_name")
    exact_invocation_counts = (
        isinstance(invocation_count, int)
        and not isinstance(invocation_count, bool)
        and invocation_count == len(expected_names)
        and isinstance(invocation_counts, dict)
        and set(invocation_counts) == set(expected_names)
        and all(
            isinstance(invocation_counts.get(name), int)
            and not isinstance(invocation_counts.get(name), bool)
            and invocation_counts[name] == 1
            for name in expected_names
        )
    )
    if not exact_invocation_counts:
        errors.append("required complete suites were not invoked exactly once each")

    suites = payload.get("suites")
    if not isinstance(suites, list):
        errors.append("validated regression suite records are missing")
        suites = []
    names = [item.get("name") for item in suites if isinstance(item, dict)]
    if (
        len(suites) != len(expected_names)
        or len(names) != len(expected_names)
        or len(set(names)) != len(expected_names)
        or set(names) != set(expected_names)
    ):
        errors.append("validated regression suite record set is not exact")
    by_name = {
        str(item.get("name")): item for item in suites if isinstance(item, dict)
    }

    discovered_total = 0
    expected_log_dir = resolved_path.parent / f"{resolved_path.stem}_logs"
    for name in expected_names:
        item = by_name.get(name)
        if not isinstance(item, dict):
            continue
        discovered_count = item.get("discovered_test_count")
        suite_invocation_count = item.get("invocation_count")
        suite_returncode = item.get("returncode")
        exact_pass = (
            isinstance(suite_invocation_count, int)
            and not isinstance(suite_invocation_count, bool)
            and suite_invocation_count == 1
            and isinstance(suite_returncode, int)
            and not isinstance(suite_returncode, bool)
            and suite_returncode == 0
            and item.get("status") == "PASS"
            and isinstance(discovered_count, int)
            and not isinstance(discovered_count, bool)
            and discovered_count >= 1
        )
        if not exact_pass:
            errors.append(f"validated regression suite is not an exact PASS: {name}")
        if item.get("command") != subprocess.list2cmdline(expected_commands[name]):
            errors.append(f"validated regression suite command mismatch: {name}")
        if isinstance(discovered_count, int) and not isinstance(discovered_count, bool):
            discovered_total += discovered_count

        for stream in ("stdout", "stderr"):
            record = item.get(stream)
            if not isinstance(record, dict):
                errors.append(f"validated regression {name} {stream} record missing")
                continue
            supplied_log = Path(str(record.get("path", ""))).expanduser()
            resolved_log = supplied_log.resolve(strict=False)
            expected_log = (expected_log_dir / f"{name}.{stream}.log").resolve(
                strict=False
            )
            if (
                supplied_log.is_symlink()
                or resolved_log != expected_log
                or not resolved_log.is_relative_to(build_root)
                or not resolved_log.is_file()
            ):
                errors.append(f"validated regression {name} {stream} log path is invalid")
                continue
            recorded_bytes = record.get("bytes")
            if (
                not isinstance(recorded_bytes, int)
                or isinstance(recorded_bytes, bool)
                or recorded_bytes != resolved_log.stat().st_size
            ):
                errors.append(f"validated regression {name} {stream} log size mismatch")
            if sha256_file(resolved_log) != str(record.get("sha256", "")).lower():
                errors.append(f"validated regression {name} {stream} log hash mismatch")

        stderr_record = item.get("stderr")
        if isinstance(stderr_record, dict):
            stderr_path = Path(str(stderr_record.get("path", ""))).resolve(strict=False)
            if stderr_path.is_file() and stderr_path == (
                expected_log_dir / f"{name}.stderr.log"
            ).resolve(strict=False):
                stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
                match = re.search(r"Ran (\d+) tests? in ", stderr_text)
                if (
                    match is None
                    or int(match.group(1)) != discovered_count
                    or re.search(r"^OK$", stderr_text, re.MULTILINE) is None
                ):
                    errors.append(f"validated regression {name} test-result markers mismatch")

    if payload.get("total_discovered_test_count") != discovered_total:
        errors.append("validated regression total discovered test count mismatch")
    return not errors, {
        "path": str(resolved_path),
        "sha256": actual_sha256,
        "payload": payload,
        "errors": errors,
    }
