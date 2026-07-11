#!/usr/bin/env python3
"""P7 fail-closed, authorization-bound hardware sequence executor.

Without ``--execute-hardware`` this module only validates immutable inputs and
never launches a wrapper.  Hardware execution is possible only from a hashed
``rf-comm-p7-hardware-sequence-plan-v1`` document whose commands are exact argv
vectors for one of the two P7 safe wrappers.  The plan is deliberately rigid:
safe-idle, three P6 masks, the complete 48-case boundary matrix, the exact
nine-case large-object matrix, then functional/fault/abort/queue and one final
1800-second stationary run.

The old read-only preflight entry point and its public helper functions remain
available when no sequence plan is supplied.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import p7_jtag_backend as jtag_backend

from p7_hardware_safety import (
    AUTH_ENV,
    AUTH_ENV_VALUE,
    AUTH_MARKER,
    DEFAULT_PREFLIGHT_TCL,
    ROOT,
    SHA256_RE,
    add_common_arguments,
    parse_authorization_file,
    resolve_path,
    sha256_file,
    validate_request,
)


SEQUENCE_SCHEMA = "rf-comm-p7-hardware-sequence-plan-v1"
LEDGER_SCHEMA = "rf-comm-p7-sequence-execution-ledger-v1"
HARDWARE_ROOT = (ROOT / "evidence" / "hardware" / "p7").resolve(strict=False)
JTAG_WRAPPER = (ROOT / "scripts" / "hw" / "run_p7_jtag_axi_stage_safe.py").resolve(strict=False)
PS_WRAPPER = (ROOT / "scripts" / "hw" / "run_p7_ps_application_stage_safe.py").resolve(strict=False)
BOUNDARY_SIZES = (0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024)
LANE_POLICIES = (
    "LANE0_ONLY",
    "LANE1_ONLY",
    "STRIPE_ROUND_ROBIN",
    "REPLICATE_0X3",
)
LARGE_PATTERNS = (
    "counter",
    "prbs15",
    "deterministic_random",
    "binary_all_byte_values_repeated",
)
LARGE_CASES = (
    (4_096, "STRIPE_ROUND_ROBIN", "deterministic_random", 30),
    *((65_536, "STRIPE_ROUND_ROBIN", pattern, 31) for pattern in LARGE_PATTERNS),
    *((1_048_576, policy, "deterministic_random", 32) for policy in LANE_POLICIES),
)
# Both child safe wrappers enforce the same 64-character stage-name ceiling.
# The sequence validator must never accept an id that a child later rejects.
STAGE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
PS_STATIONARY_SETUP_WATCHDOG_SECONDS = 300
PS_STATIONARY_ACTIVE_TOLERANCE_SECONDS = 1.5
PS_POST_SAFE_REAP_GRACE_SECONDS = 120
PS_NONSTATIONARY_XSDB_GRACE_SECONDS = 120
PS_OUTER_ORCHESTRATION_GUARD_SECONDS = 120
PS_VIVADO_PROCESS_COUNT = 3
PS_XSDB_PROCESS_COUNT = 1
PS_MAX_FORCED_CLEANUP_EVENTS = 2

# Vivado reports the package/speed-grade-qualified build part and the live
# silicon identity through different properties.  Keep the mapping explicit:
# accepting a prefix such as ``xc7z010*`` would also accept the wrong package,
# speed grade, device name, or JTAG identity.
CANONICAL_FULL_PART = "xc7z010clg400-1"
CANONICAL_LIVE_PART = "xc7z010"
CANONICAL_LIVE_DEVICE = "xc7z010_1"
CANONICAL_LIVE_IDCODE_BINARY = "00010011011100100010000010010011"
CANONICAL_LIVE_IDCODE_HEX = "13722093"


def is_exact_vivado_batch_launcher(value: str | Path) -> bool:
    """Forbid direct vivado.exe so the contained batch/process topology is stable."""

    return Path(value).resolve(strict=False).name.casefold() == "vivado.bat"

COMMON_BOOLEAN_OPTIONS = {
    "--execute-hardware",
    "--shutdown-on-exit",
    "--no-ethernet",
    "--no-motion",
    "--json-summary",
}
COMMON_VALUE_OPTIONS = {
    "--authorization-file",
    "--authorization-sha256",
    "--board-id",
    "--expected-part",
    "--expected-target",
    "--source-commit",
    "--plan-file",
    "--plan-sha256",
    "--bitstream",
    "--bitstream-sha256",
    "--xsa",
    "--xsa-sha256",
    "--elf",
    "--elf-sha256",
    "--profile",
    "--profile-sha256",
    "--active-xdc",
    "--active-xdc-sha256",
    "--pinmap",
    "--pinmap-sha256",
    "--register-map",
    "--register-map-sha256",
    "--shutdown-bitstream",
    "--shutdown-bitstream-sha256",
    "--ltx",
    "--ltx-sha256",
    "--max-runtime-sec",
    "--lane-count",
    "--max-lane-mask",
    "--abort-file",
    "--vivado-path",
    "--hw-server-url",
    "--stage-name",
    "--jtag-frequency-hz",
    "--preflight-timeout-sec",
    "--shutdown-timeout-sec",
    "--evidence-dir",
}
JTAG_VALUE_OPTIONS = {
    "--semantic-mode",
    "--transaction-file",
    "--transaction-sha256",
    "--backend-manifest",
    "--backend-manifest-sha256",
    "--axi-base-address",
    "--stage-timeout-sec",
}
PS_VALUE_OPTIONS = {
    "--mode",
    "--input-file",
    "--input-sha256",
    "--ps7-init",
    "--ps7-init-sha256",
    "--p6-build-summary",
    "--p6-build-summary-sha256",
    "--p7-build-summary",
    "--p7-build-summary-sha256",
    "--core-readiness-attestation",
    "--core-readiness-attestation-sha256",
    "--active-profile",
    "--active-profile-sha256",
    "--lane1-promotion-summary",
    "--lane1-promotion-summary-sha256",
    "--xsdb-path",
    "--calibration-sec",
    "--acceptance-sec",
    "--sample-interval-sec",
    "--idle-deadline-margin-sec",
    "--stationary-object-bytes",
}
PATH_HASH_PAIRS = (
    ("--authorization-file", "--authorization-sha256"),
    ("--plan-file", "--plan-sha256"),
    ("--bitstream", "--bitstream-sha256"),
    ("--xsa", "--xsa-sha256"),
    ("--elf", "--elf-sha256"),
    ("--profile", "--profile-sha256"),
    ("--active-xdc", "--active-xdc-sha256"),
    ("--pinmap", "--pinmap-sha256"),
    ("--register-map", "--register-map-sha256"),
    ("--shutdown-bitstream", "--shutdown-bitstream-sha256"),
    ("--ltx", "--ltx-sha256"),
    ("--transaction-file", "--transaction-sha256"),
    ("--backend-manifest", "--backend-manifest-sha256"),
    ("--input-file", "--input-sha256"),
    ("--ps7-init", "--ps7-init-sha256"),
    ("--p6-build-summary", "--p6-build-summary-sha256"),
    ("--p7-build-summary", "--p7-build-summary-sha256"),
    ("--core-readiness-attestation", "--core-readiness-attestation-sha256"),
    ("--active-profile", "--active-profile-sha256"),
    ("--lane1-promotion-summary", "--lane1-promotion-summary-sha256"),
)
REQUIRED_COMMON_OPTIONS = {
    "--execute-hardware",
    "--authorization-file",
    "--authorization-sha256",
    "--board-id",
    "--expected-part",
    "--expected-target",
    "--source-commit",
    "--plan-file",
    "--plan-sha256",
    "--bitstream",
    "--bitstream-sha256",
    "--xsa",
    "--xsa-sha256",
    "--elf",
    "--elf-sha256",
    "--profile",
    "--profile-sha256",
    "--active-xdc",
    "--active-xdc-sha256",
    "--pinmap",
    "--pinmap-sha256",
    "--register-map",
    "--register-map-sha256",
    "--shutdown-bitstream",
    "--shutdown-bitstream-sha256",
    "--max-runtime-sec",
    "--shutdown-on-exit",
    "--no-ethernet",
    "--no-motion",
    "--lane-count",
    "--max-lane-mask",
    "--abort-file",
    "--vivado-path",
    "--hw-server-url",
    "--stage-name",
    "--preflight-timeout-sec",
    "--shutdown-timeout-sec",
    "--evidence-dir",
    "--json-summary",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _duplicate_rejecting_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8", errors="strict"),
        object_pairs_hook=_duplicate_rejecting_object,
    )
    if not isinstance(value, dict):
        raise ValueError(f"JSON document is not an object: {path}")
    return value


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    if partial.exists():
        raise RuntimeError(f"stale atomic-write partial file exists: {partial}")
    encoded = (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    try:
        with partial.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    finally:
        if partial.exists():
            partial.unlink()


def _path_equal(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.resolve(strict=False))) == os.path.normcase(
        str(right.resolve(strict=False))
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def _file_record(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=False)
    if not resolved.is_file():
        return {"path": str(resolved), "missing": True}
    return {
        "path": str(resolved),
        "sha256": sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _verify_file_record(label: str, value: Any) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} record is missing"]
    raw_path = value.get("path")
    expected = str(value.get("sha256", "")).lower()
    if not isinstance(raw_path, str) or not raw_path:
        return [f"{label} path is missing"]
    path = Path(raw_path).resolve(strict=False)
    errors: list[str] = []
    if not path.is_file():
        errors.append(f"{label} file is missing: {path}")
    if not SHA256_RE.fullmatch(expected):
        errors.append(f"{label} SHA256 is malformed")
    elif path.is_file() and sha256_file(path) != expected:
        errors.append(f"{label} SHA256 changed: {path}")
    if path.is_file() and value.get("bytes") != path.stat().st_size:
        errors.append(f"{label} byte count changed: {path}")
    return errors


def _current_git_head() -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, result.stderr.strip() or "git rev-parse failed"
    head = result.stdout.strip().lower()
    if not COMMIT_RE.fullmatch(head):
        return None, f"git returned malformed HEAD: {head}"
    return head, None


def _git_tree_listing_sha256(commit: str) -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "--full-tree", commit],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if result.returncode != 0:
        return None, result.stderr.strip() or "git ls-tree failed"
    return hashlib.sha256(result.stdout.encode("utf-8")).hexdigest(), None


def expected_stage_contracts() -> list[dict[str, Any]]:
    """Return the one canonical 66-stage P7 hardware sequence."""

    contracts: list[dict[str, Any]] = [
        {"group": "safe_idle", "risk_index": 10, "case": {}},
    ]
    for lane_mask in (1, 2, 3):
        contracts.append(
            {
                "group": "p6_frame_regression",
                "risk_index": 20,
                "case": {"lane_mask": lane_mask, "minimum_fragments": 10},
            }
        )
    for object_size in BOUNDARY_SIZES:
        for lane_policy in LANE_POLICIES:
            contracts.append(
                {
                    "group": "fragment_boundary",
                    "risk_index": 25,
                    "case": {"object_size": object_size, "lane_policy": lane_policy},
                }
            )
    for object_size, lane_policy, pattern, risk in LARGE_CASES:
        contracts.append(
            {
                "group": "large_object_jtag",
                "risk_index": risk,
                "case": {
                    "object_size": object_size,
                    "lane_policy": lane_policy,
                    "pattern": pattern,
                },
            }
        )
    contracts.extend(
        [
            {"group": "ps_functional", "risk_index": 40, "case": {}},
            {"group": "ps_fault", "risk_index": 50, "case": {}},
            {"group": "ps_abort", "risk_index": 60, "case": {}},
            {"group": "ps_queue", "risk_index": 70, "case": {}},
            {"group": "ps_stationary", "risk_index": 80, "case": {}},
        ]
    )
    return contracts


def validate_stage_matrix(stages: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(stages, list):
        return ["sequence plan stages must be a list"]
    expected = expected_stage_contracts()
    if len(stages) != len(expected):
        errors.append(f"sequence must contain exactly {len(expected)} stages, observed {len(stages)}")
    for index, contract in enumerate(expected):
        if index >= len(stages):
            errors.append(f"sequence stage {index + 1} is missing: {contract}")
            continue
        stage = stages[index]
        if not isinstance(stage, dict):
            errors.append(f"sequence stage {index + 1} is not an object")
            continue
        observed = {
            "group": stage.get("group"),
            "risk_index": stage.get("risk_index"),
            "case": stage.get("case"),
        }
        if observed != contract:
            errors.append(
                f"sequence stage {index + 1} contract mismatch: expected={contract} observed={observed}"
            )
    if len(stages) > len(expected):
        errors.append("sequence contains stages after the single final stationary stage")
    groups = [item.get("group") for item in stages if isinstance(item, dict)]
    if groups.count("ps_stationary") != 1:
        errors.append("sequence must contain exactly one stationary stage")
    if groups and groups[-1] != "ps_stationary":
        errors.append("stationary stage must be the final planned hardware stage")
    if "ps_abort" in groups and "ps_queue" in groups:
        if groups.index("ps_abort") >= groups.index("ps_queue"):
            errors.append("abort stage must precede queue stage")
    return errors


def _parse_exact_wrapper_command(
    command: Any,
) -> tuple[Path | None, dict[str, str | bool], list[str]]:
    errors: list[str] = []
    if not isinstance(command, list) or len(command) < 2:
        return None, {}, ["stage command must be a nonempty argv list"]
    if any(not isinstance(item, str) or not item or "\x00" in item or "\n" in item for item in command):
        return None, {}, ["stage command contains an empty, non-string, NUL, or newline argv element"]
    python_path = Path(command[0]).resolve(strict=False)
    current_python = Path(sys.executable).resolve(strict=False)
    if not _path_equal(python_path, current_python):
        errors.append(
            f"stage interpreter must be this exact Python executable: expected={current_python} observed={python_path}"
        )
    wrapper = resolve_path(command[1])
    if not (_path_equal(wrapper, JTAG_WRAPPER) or _path_equal(wrapper, PS_WRAPPER)):
        errors.append(f"command is not an approved P7 safe wrapper: {wrapper}")
        return wrapper, {}, errors
    value_options = set(COMMON_VALUE_OPTIONS)
    if _path_equal(wrapper, JTAG_WRAPPER):
        value_options.update(JTAG_VALUE_OPTIONS)
    else:
        value_options.update(PS_VALUE_OPTIONS)
    allowed = value_options | COMMON_BOOLEAN_OPTIONS
    parsed: dict[str, str | bool] = {}
    index = 2
    while index < len(command):
        token = command[index]
        if token not in allowed:
            errors.append(f"unknown or positional wrapper argument: {token}")
            index += 1
            continue
        if token in parsed:
            errors.append(f"duplicate wrapper option is forbidden: {token}")
        if token in COMMON_BOOLEAN_OPTIONS:
            parsed[token] = True
            index += 1
            continue
        if index + 1 >= len(command):
            errors.append(f"wrapper option lacks a value: {token}")
            index += 1
            continue
        value = command[index + 1]
        if value.startswith("--"):
            errors.append(f"wrapper option lacks a value: {token}")
            index += 1
            continue
        parsed[token] = value
        index += 2
    missing = sorted(REQUIRED_COMMON_OPTIONS - set(parsed))
    if missing:
        errors.append(f"wrapper command omits mandatory exact options: {', '.join(missing)}")
    return wrapper, parsed, errors


def _int_option(
    options: Mapping[str, str | bool], name: str, errors: list[str], *, minimum: int, maximum: int
) -> int | None:
    raw = options.get(name)
    try:
        value = int(str(raw), 0)
    except (TypeError, ValueError):
        errors.append(f"{name} must be an integer")
        return None
    if value < minimum or value > maximum:
        errors.append(f"{name} must be in {minimum}..{maximum}: {value}")
    return value


def minimum_ps_outer_wrapper_timeout(
    *, mode: str, max_runtime: int, preflight: int, shutdown: int
) -> int:
    vivado_per_process = jtag_backend.EXPECTED_TOOL_DAEMON_GRACE_SECONDS
    containment = (
        PS_VIVADO_PROCESS_COUNT * vivado_per_process
        + PS_XSDB_PROCESS_COUNT * jtag_backend.NON_VIVADO_EMPTY_PROOF_ALLOWANCE_SECONDS
    )
    forced_cleanup_reserve = (
        PS_MAX_FORCED_CLEANUP_EVENTS
        * jtag_backend.CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS
    )
    if mode == "stationary":
        candidate = (
            PS_STATIONARY_SETUP_WATCHDOG_SECONDS
            + max_runtime
            + PS_STATIONARY_ACTIVE_TOLERANCE_SECONDS
            + PS_POST_SAFE_REAP_GRACE_SECONDS
        )
    else:
        candidate = max_runtime + PS_NONSTATIONARY_XSDB_GRACE_SECONDS
    return math.ceil(
        preflight
        + 2 * shutdown
        + candidate
        + containment
        + forced_cleanup_reserve
        + PS_OUTER_ORCHESTRATION_GUARD_SECONDS
    )


def _validate_hash_pairs(
    options: Mapping[str, str | bool], errors: list[str]
) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for path_key, hash_key in PATH_HASH_PAIRS:
        raw_path = options.get(path_key)
        raw_hash = options.get(hash_key)
        if raw_path is None and raw_hash is None:
            continue
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"{hash_key} is present without {path_key}")
            continue
        if not isinstance(raw_hash, str) or not SHA256_RE.fullmatch(raw_hash):
            errors.append(f"{path_key} has a missing or malformed {hash_key}")
            continue
        path = resolve_path(raw_path)
        paths[path_key] = path
        if not path.is_file():
            errors.append(f"immutable wrapper input is missing: {path_key}={path}")
            continue
        actual = sha256_file(path)
        if actual != raw_hash.lower():
            errors.append(
                f"immutable wrapper input SHA256 mismatch: {path_key} expected={raw_hash.lower()} actual={actual}"
            )
    return paths


def _validate_authorization_binding(
    *,
    wrapper: Path,
    options: Mapping[str, str | bool],
    paths: Mapping[str, Path],
    source_commit: str,
    errors: list[str],
) -> None:
    auth = paths.get("--authorization-file")
    if auth is None or not auth.is_file():
        return
    authorization_root = (ROOT / ".hardware_authorization").resolve(strict=False)
    if not _inside(auth, authorization_root):
        errors.append(f"authorization file is outside {authorization_root}: {auth}")
        return
    try:
        fields, markers, duplicates = parse_authorization_file(auth)
    except (OSError, UnicodeError) as exc:
        errors.append(f"authorization file cannot be parsed: {exc}")
        return
    if duplicates:
        errors.append(f"authorization contains duplicate keys: {sorted(set(duplicates))}")
    if AUTH_MARKER not in markers:
        errors.append(f"authorization marker missing: {AUTH_MARKER}")
    common_expected = {
        "SOURCE_COMMIT": source_commit,
        "SHUTDOWN_ON_EXIT": "required",
        "NO_ETHERNET": "true",
        "NO_MOTION": "true",
        "LANE_COUNT": "2",
        "MAX_LANE_MASK": "0x3",
    }
    for key, expected in common_expected.items():
        if fields.get(key, "").casefold() != expected.casefold():
            errors.append(f"authorization binding mismatch: {key}")
    try:
        auth_runtime = int(fields.get("MAX_RUNTIME_SEC", ""), 10)
        requested_runtime = int(str(options.get("--max-runtime-sec")), 10)
        if auth_runtime < requested_runtime or auth_runtime > 1800:
            errors.append("authorization MAX_RUNTIME_SEC does not bound the wrapper request")
    except ValueError:
        errors.append("authorization MAX_RUNTIME_SEC is malformed")
    if _path_equal(wrapper, JTAG_WRAPPER):
        exact = {
            "P7_JTAG_STAGE_NAME": str(options.get("--stage-name", "")),
            "P7_JTAG_SEMANTIC_MODE": str(options.get("--semantic-mode", "")),
            "P7_JTAG_TRANSACTION_PATH": str(paths.get("--transaction-file", "")),
            "P7_JTAG_TRANSACTION_SHA256": str(options.get("--transaction-sha256", "")).lower(),
        }
        if options.get("--semantic-mode") == "rfap":
            exact.update(
                {
                    "P7_JTAG_BACKEND_MANIFEST_PATH": str(paths.get("--backend-manifest", "")),
                    "P7_JTAG_BACKEND_MANIFEST_SHA256": str(
                        options.get("--backend-manifest-sha256", "")
                    ).lower(),
                }
            )
    else:
        exact = {
            "P7_PS_MODE": str(options.get("--mode", "")),
            "P7_INPUT_PATH": str(paths.get("--input-file", "")),
            "P7_INPUT_SHA256": str(options.get("--input-sha256", "")).lower(),
        }
    for key, expected in exact.items():
        observed = fields.get(key)
        if observed is None:
            errors.append(f"authorization extension is missing {key}")
        elif key.endswith("_PATH"):
            if os.path.normcase(str(Path(observed).resolve(strict=False))) != os.path.normcase(
                str(Path(expected).resolve(strict=False))
            ):
                errors.append(f"authorization extension path mismatch: {key}")
        elif observed.casefold() != expected.casefold():
            errors.append(f"authorization extension mismatch: {key}")


def _expected_policy_for_mask(mask: int) -> str:
    return {1: "LANE0_ONLY", 2: "LANE1_ONLY", 3: "REPLICATE_0X3"}[mask]


def _validate_backend_manifest(
    stage: Mapping[str, Any], options: Mapping[str, str | bool], paths: Mapping[str, Path]
) -> list[str]:
    errors: list[str] = []
    manifest_path = paths.get("--backend-manifest")
    if manifest_path is None:
        return ["RFAP JTAG stage is missing its hashed backend manifest"]
    try:
        manifest = _load_json_object(manifest_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [f"backend manifest is invalid: {exc}"]
    case = stage["case"]
    group = stage["group"]
    if group == "p6_frame_regression":
        expected_length = None
        expected_policy = _expected_policy_for_mask(int(case["lane_mask"]))
        if int(manifest.get("fragment_count", -1)) < int(case["minimum_fragments"]):
            errors.append("P6 regression backend manifest has fewer than 10 fragments")
    else:
        expected_length = int(case["object_size"])
        expected_policy = str(case["lane_policy"])
    if expected_length is not None and manifest.get("input_length") != expected_length:
        errors.append(
            f"backend manifest object length mismatch: expected={expected_length} observed={manifest.get('input_length')}"
        )
    if manifest.get("lane_policy") != expected_policy:
        errors.append(
            f"backend manifest lane policy mismatch: expected={expected_policy} observed={manifest.get('lane_policy')}"
        )
    fragments = manifest.get("fragments")
    if not isinstance(fragments, list) or not fragments:
        errors.append("backend manifest fragment list is missing or empty")
    else:
        masks = [item.get("lane_mask") for item in fragments if isinstance(item, dict)]
        if len(masks) != len(fragments) or any(not isinstance(mask, int) or not 1 <= mask <= 3 for mask in masks):
            errors.append("backend manifest contains a lane mask outside 0x1..0x3")
        if group == "p6_frame_regression" and any(mask != case["lane_mask"] for mask in masks):
            errors.append("P6 regression backend manifest does not use the requested mask for every fragment")
    if manifest.get("network_used") is not False or manifest.get("hardware_actions_executed_by_module") is not False:
        errors.append("backend manifest violates offline/no-network generation boundary")
    return errors


def _validate_stage_command(
    stage: Mapping[str, Any], source_commit: str
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    wrapper, options, command_errors = _parse_exact_wrapper_command(stage.get("command"))
    errors.extend(command_errors)
    if wrapper is None:
        return None, errors
    if options.get("--source-commit") != source_commit:
        errors.append("wrapper source commit differs from the frozen plan/checkpoint commit")
    if options.get("--stage-name") != stage.get("id"):
        errors.append("wrapper --stage-name must exactly equal the sequence stage id")
    if options.get("--execute-hardware") is not True:
        errors.append("wrapper argv must explicitly request --execute-hardware")
    for flag in ("--shutdown-on-exit", "--no-ethernet", "--no-motion", "--json-summary"):
        if options.get(flag) is not True:
            errors.append(f"wrapper argv is missing {flag}")
    _int_option(options, "--lane-count", errors, minimum=2, maximum=2)
    _int_option(options, "--max-lane-mask", errors, minimum=1, maximum=3)
    max_runtime = _int_option(options, "--max-runtime-sec", errors, minimum=1, maximum=1800)
    _int_option(options, "--preflight-timeout-sec", errors, minimum=1, maximum=300)
    _int_option(options, "--shutdown-timeout-sec", errors, minimum=1, maximum=300)
    if str(options.get("--hw-server-url", "")) == "" or not re.fullmatch(
        r"(?:localhost|127\.0\.0\.1|\[::1\]):[0-9]{1,5}", str(options.get("--hw-server-url", ""))
    ):
        errors.append("wrapper hw_server URL must be an explicit local endpoint")
    for executable_option in ("--vivado-path", "--xsdb-path"):
        if executable_option in options and not Path(str(options[executable_option])).resolve(strict=False).is_file():
            errors.append(f"wrapper executable is missing: {executable_option}")
    if not is_exact_vivado_batch_launcher(str(options.get("--vivado-path", ""))):
        errors.append("wrapper --vivado-path must resolve to exactly vivado.bat; vivado.exe is forbidden")
    paths = _validate_hash_pairs(options, errors)
    _validate_authorization_binding(
        wrapper=wrapper,
        options=options,
        paths=paths,
        source_commit=source_commit,
        errors=errors,
    )
    group = str(stage.get("group"))
    jtag_group = group in {"safe_idle", "p6_frame_regression", "fragment_boundary", "large_object_jtag"}
    if jtag_group != _path_equal(wrapper, JTAG_WRAPPER):
        errors.append(f"stage group {group} uses the wrong safe wrapper")
    expected_mode = {
        "ps_functional": "functional",
        "ps_fault": "fault-fallback",
        "ps_abort": "abort-restart",
        "ps_queue": "queue",
        "ps_stationary": "stationary",
    }.get(group)
    if jtag_group:
        semantic = options.get("--semantic-mode")
        if group == "safe_idle":
            if semantic != "safe-idle":
                errors.append("safe-idle group requires --semantic-mode safe-idle")
            if "--backend-manifest" in options or "--backend-manifest-sha256" in options:
                errors.append("safe-idle command must not include an RFAP backend manifest")
        else:
            if semantic != "rfap":
                errors.append(f"{group} requires --semantic-mode rfap")
            for key in ("--backend-manifest", "--backend-manifest-sha256"):
                if key not in options:
                    errors.append(f"RFAP stage is missing {key}")
            errors.extend(_validate_backend_manifest(stage, options, paths))
        for key in (
            "--transaction-file",
            "--transaction-sha256",
            "--jtag-frequency-hz",
            "--stage-timeout-sec",
        ):
            if key not in options:
                errors.append(f"JTAG stage is missing {key}")
        try:
            configured_global = (
                int(str(options.get("--preflight-timeout-sec", 0)))
                + 2 * int(str(options.get("--shutdown-timeout-sec", 0)))
                + int(str(options.get("--stage-timeout-sec", 0)))
                + jtag_backend.JTAG_WRAPPER_CONTAINMENT_ALLOWANCE_SECONDS
                + jtag_backend.JTAG_WRAPPER_OTHER_GUARD_SECONDS
            )
        except ValueError:
            configured_global = max_runtime + 1 if max_runtime is not None else 1
        if max_runtime is not None and configured_global > max_runtime:
            errors.append(
                "JTAG configured phase timeouts plus explicit containment/other guards "
                f"exceed global runtime: configured={configured_global} authorized={max_runtime}"
            )
    else:
        if options.get("--mode") != expected_mode:
            errors.append(f"{group} requires --mode {expected_mode}")
        for key in (
            "--input-file",
            "--input-sha256",
            "--ps7-init",
            "--ps7-init-sha256",
            "--p6-build-summary",
            "--p6-build-summary-sha256",
            "--p7-build-summary",
            "--p7-build-summary-sha256",
            "--core-readiness-attestation",
            "--core-readiness-attestation-sha256",
            "--active-profile",
            "--active-profile-sha256",
            "--lane1-promotion-summary",
            "--lane1-promotion-summary-sha256",
            "--xsdb-path",
        ):
            if key not in options:
                errors.append(f"PS stage is missing {key}")
        if group == "ps_stationary":
            if max_runtime != 1800:
                errors.append("stationary wrapper runtime must be exactly 1800 seconds")
            exact_stationary = {
                "--calibration-sec": "300",
                "--acceptance-sec": "1500",
                "--sample-interval-sec": "30",
            }
            for key, expected in exact_stationary.items():
                if options.get(key) != expected:
                    errors.append(f"stationary wrapper requires {key} {expected}")
        elif max_runtime is not None and max_runtime > 900:
            errors.append("non-stationary PS stage runtime must not exceed 900 seconds")
    evidence_raw = options.get("--evidence-dir")
    evidence_dir = resolve_path(str(evidence_raw)) if isinstance(evidence_raw, str) else ROOT
    if not _inside(evidence_dir, HARDWARE_ROOT) or _path_equal(evidence_dir, HARDWARE_ROOT):
        errors.append(f"stage evidence directory must be a child of {HARDWARE_ROOT}: {evidence_dir}")
    summary_name = "p7_jtag_axi_stage_summary.json" if jtag_group else "p7_ps_application_stage_summary.json"
    expected_summary = evidence_dir / summary_name
    summary_raw = stage.get("summary_path")
    if not isinstance(summary_raw, str) or not _path_equal(resolve_path(summary_raw), expected_summary):
        errors.append(f"stage summary_path must be exactly {expected_summary}")
    timeout = stage.get("wrapper_timeout_sec")
    if not isinstance(timeout, int) or timeout < 1 or timeout > 3600:
        errors.append("stage wrapper_timeout_sec must be an integer in 1..3600")
    elif max_runtime is not None:
        preflight = int(str(options.get("--preflight-timeout-sec", 0)))
        shutdown = int(str(options.get("--shutdown-timeout-sec", 0)))
        if jtag_group:
            # JTAG max_runtime is the child's global ceiling; phases and the
            # explicit 4-child containment/other guards are already inside it.
            minimum_timeout = (
                max_runtime + jtag_backend.JTAG_OUTER_WRAPPER_GRACE_SECONDS
            )
        else:
            minimum_timeout = minimum_ps_outer_wrapper_timeout(
                mode=str(expected_mode),
                max_runtime=max_runtime,
                preflight=preflight,
                shutdown=shutdown,
            )
        if timeout < minimum_timeout:
            errors.append(
                f"wrapper_timeout_sec is too short for bounded stage plus safety barriers: minimum={minimum_timeout}"
            )
    normalized = {
        **stage,
        "wrapper": str(wrapper),
        "options": dict(options),
        "evidence_dir": str(evidence_dir),
        "summary_path": str(expected_summary),
    }
    return normalized, errors


def _validate_offline_checkpoint(
    checkpoint_path: Path, checkpoint_sha256: str, source_commit: str
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if not checkpoint_path.is_file():
        return None, [f"offline checkpoint is missing: {checkpoint_path}"]
    if checkpoint_path.is_symlink():
        errors.append("offline checkpoint must not be a symlink")
    if not SHA256_RE.fullmatch(checkpoint_sha256):
        errors.append("offline checkpoint SHA256 is malformed")
    elif sha256_file(checkpoint_path) != checkpoint_sha256.lower():
        errors.append("offline checkpoint SHA256 mismatch")
    try:
        payload = _load_json_object(checkpoint_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, errors + [f"offline checkpoint JSON is invalid: {exc}"]
    if payload.get("P7_OFFLINE_GATE") != "PASS":
        errors.append("offline checkpoint does not prove P7_OFFLINE_GATE=PASS")
    if payload.get("hardware_actions_executed") is not False or payload.get("NO_HARDWARE_ACTIONS_EXECUTED") is not True:
        errors.append("offline checkpoint does not prove the no-hardware boundary")
    if payload.get("HARDWARE_ACCEPTANCE") != "PENDING_HW":
        errors.append("offline checkpoint improperly promotes hardware acceptance")
    if str(payload.get("source_commit", "")).lower() != source_commit:
        errors.append("offline checkpoint source commit mismatch")
    if payload.get("dirty_worktree") is not False:
        errors.append("offline checkpoint must prove dirty_worktree=false")
    checks = payload.get("checks")
    if not isinstance(checks, dict) or checks.get("P7_CLEAN_SOURCE_CHECKPOINT") is not True or checks.get("P7_CHECKPOINT_INPUT_HASHES") is not True:
        errors.append("offline checkpoint clean-source/input-hash checks are not both PASS")
    source_hashes = payload.get("checkpoint_input_hashes")
    if not isinstance(source_hashes, dict) or not source_hashes:
        errors.append("offline checkpoint input hash map is missing or empty")
    else:
        if payload.get("checkpoint_input_count") != len(source_hashes):
            errors.append("offline checkpoint input hash count mismatch")
        for raw_name, raw_hash in source_hashes.items():
            if not isinstance(raw_name, str) or not raw_name or Path(raw_name).is_absolute() or ".." in Path(raw_name).parts:
                errors.append(f"offline checkpoint input path is not repository-relative: {raw_name}")
                continue
            expected = str(raw_hash).lower()
            path = (ROOT / raw_name).resolve(strict=False)
            if not _inside(path, ROOT) or not path.is_file():
                errors.append(f"offline checkpoint input is missing or escapes repository: {raw_name}")
            elif not SHA256_RE.fullmatch(expected):
                errors.append(f"offline checkpoint input hash is malformed: {raw_name}")
            elif sha256_file(path) != expected:
                errors.append(f"offline checkpoint input changed after freeze: {raw_name}")
    expected_tree = str(payload.get("source_tree_listing_sha256", "")).lower()
    if not SHA256_RE.fullmatch(expected_tree):
        errors.append("offline checkpoint source-tree listing SHA256 is malformed")
    else:
        actual_tree, tree_error = _git_tree_listing_sha256(source_commit)
        if tree_error:
            errors.append(f"unable to verify offline checkpoint source tree: {tree_error}")
        elif actual_tree != expected_tree:
            errors.append("offline checkpoint source-tree listing SHA256 mismatch")
    return payload, errors


def validate_sequence_plan(path: Path, expected_sha256: str) -> dict[str, Any]:
    errors: list[str] = []
    plan_path = path.resolve(strict=False)
    if not plan_path.is_file():
        return {"errors": [f"sequence plan is missing: {plan_path}"], "stages": []}
    if plan_path.is_symlink():
        errors.append("sequence plan must not be a symlink")
    if not SHA256_RE.fullmatch(expected_sha256):
        errors.append("sequence plan SHA256 is malformed")
    elif sha256_file(plan_path) != expected_sha256.lower():
        errors.append("sequence plan SHA256 mismatch")
    try:
        plan = _load_json_object(plan_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return {"errors": errors + [f"sequence plan JSON is invalid: {exc}"], "stages": []}
    allowed_top = {"schema", "generated_at_utc", "description", "source_commit", "offline_checkpoint", "stages"}
    unknown_top = sorted(set(plan) - allowed_top)
    if unknown_top:
        errors.append(f"sequence plan contains unknown top-level keys: {unknown_top}")
    if plan.get("schema") != SEQUENCE_SCHEMA:
        errors.append(f"sequence plan schema must be {SEQUENCE_SCHEMA}")
    source_commit = str(plan.get("source_commit", "")).lower()
    if not COMMIT_RE.fullmatch(source_commit):
        errors.append("sequence plan source_commit must be exactly 40 lowercase hex characters")
    head, head_error = _current_git_head()
    if head_error:
        errors.append(f"unable to establish current source commit: {head_error}")
    elif head != source_commit:
        errors.append(f"sequence plan source commit differs from current HEAD: plan={source_commit} HEAD={head}")
    checkpoint = plan.get("offline_checkpoint")
    checkpoint_payload: dict[str, Any] | None = None
    checkpoint_path = ROOT
    checkpoint_sha = ""
    if not isinstance(checkpoint, dict) or set(checkpoint) != {"path", "sha256"}:
        errors.append("offline_checkpoint must contain exactly path and sha256")
    else:
        checkpoint_path = resolve_path(str(checkpoint.get("path", "")))
        checkpoint_sha = str(checkpoint.get("sha256", "")).lower()
        checkpoint_payload, checkpoint_errors = _validate_offline_checkpoint(
            checkpoint_path, checkpoint_sha, source_commit
        )
        errors.extend(checkpoint_errors)
    stages = plan.get("stages")
    errors.extend(validate_stage_matrix(stages))
    normalized_stages: list[dict[str, Any]] = []
    ids: set[str] = set()
    evidence_dirs: set[str] = set()
    summary_paths: set[str] = set()
    authorization_paths: set[str] = set()
    if isinstance(stages, list):
        allowed_stage = {
            "id",
            "group",
            "risk_index",
            "case",
            "command",
            "summary_path",
            "wrapper_timeout_sec",
        }
        for index, stage in enumerate(stages):
            if not isinstance(stage, dict):
                continue
            unknown = sorted(set(stage) - allowed_stage)
            if unknown:
                errors.append(f"stage {index + 1} contains unknown keys: {unknown}")
            stage_id = stage.get("id")
            if not isinstance(stage_id, str) or not STAGE_ID_RE.fullmatch(stage_id):
                errors.append(f"stage {index + 1} id is missing or malformed")
            elif stage_id in ids:
                errors.append(f"duplicate stage id: {stage_id}")
            else:
                ids.add(stage_id)
            normalized, stage_errors = _validate_stage_command(stage, source_commit)
            errors.extend(f"stage {index + 1} ({stage_id}): {item}" for item in stage_errors)
            if normalized is None:
                continue
            normalized_stages.append(normalized)
            evidence_key = os.path.normcase(normalized["evidence_dir"])
            summary_key = os.path.normcase(normalized["summary_path"])
            auth_key = os.path.normcase(
                str(resolve_path(str(normalized["options"].get("--authorization-file", ""))))
            )
            if evidence_key in evidence_dirs:
                errors.append(f"stage evidence directory is reused: {normalized['evidence_dir']}")
            evidence_dirs.add(evidence_key)
            if summary_key in summary_paths:
                errors.append(f"stage summary path is reused: {normalized['summary_path']}")
            summary_paths.add(summary_key)
            if auth_key in authorization_paths:
                errors.append("authorization file is reused across distinct stage names")
            authorization_paths.add(auth_key)
    return {
        "schema": SEQUENCE_SCHEMA,
        "path": str(plan_path),
        "sha256": sha256_file(plan_path),
        "source_commit": source_commit,
        "offline_checkpoint": {
            "path": str(checkpoint_path),
            "sha256": checkpoint_sha,
            "payload": checkpoint_payload,
        },
        "stage_count": len(normalized_stages),
        "stages": normalized_stages,
        "errors": errors,
    }


def _resolve_summary_reference(value: Any, summary_path: Path) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate.resolve(strict=False)
    local = (summary_path.parent / candidate).resolve(strict=False)
    return local if local.exists() else resolve_path(value)


def validate_wrapper_summary(
    stage: Mapping[str, Any], summary_path: Path, *, require_pass: bool
) -> tuple[dict[str, Any] | None, list[str], dict[str, Any]]:
    errors: list[str] = []
    shutdown_record: dict[str, Any] = {"present": False}
    if not summary_path.is_file():
        return None, [f"wrapper summary is missing: {summary_path}"], shutdown_record
    try:
        summary = _load_json_object(summary_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, [f"wrapper summary is invalid: {exc}"], shutdown_record
    wrapper = Path(str(stage["wrapper"]))
    is_jtag = _path_equal(wrapper, JTAG_WRAPPER)
    marker_key = "P7_JTAG_AXI_SAFE_STAGE" if is_jtag else "P7_PS_APPLICATION_SAFE_STAGE"
    marker = summary.get(marker_key)
    if require_pass and marker != "PASS":
        errors.append(f"wrapper result is not PASS: {marker_key}={marker}")
    if summary.get("stage_name") != stage.get("id"):
        errors.append("wrapper summary stage_name mismatch")
    if summary.get("hardware_actions_executed") is not True:
        errors.append("wrapper summary does not prove hardware_actions_executed=true")
    for key in ("network_used", "ethernet_used"):
        if key in summary and summary.get(key) is not False:
            errors.append(f"wrapper summary violates no-network boundary: {key}")
    if summary.get("motion_used") is not False:
        errors.append("wrapper summary violates no-motion boundary")
    safety = summary.get("safety_validation")
    if not isinstance(safety, dict) or str(safety.get("source_commit_requested", "")).lower() != str(
        stage["options"].get("--source-commit", "")
    ).lower():
        errors.append("wrapper summary source commit is missing or mismatched")
    if summary.get("programmed_shutdown_after") is not True:
        errors.append("wrapper summary does not prove programmed_shutdown_after=true")
    shutdown = summary.get("shutdown_after")
    if not isinstance(shutdown, dict):
        errors.append("wrapper shutdown-after record is missing")
    else:
        shutdown_record = {
            "present": True,
            "returncode": shutdown.get("returncode"),
            "passed": shutdown.get("passed"),
            "process_tree_reaped": shutdown.get("process_tree_reaped"),
            "process_tree_terminated": shutdown.get("process_tree_terminated"),
            "containment_cleanup_attempted": shutdown.get("containment_cleanup_attempted"),
            "containment_cleanup_terminated": shutdown.get("containment_cleanup_terminated"),
        }
        if shutdown.get("returncode") != 0 or shutdown.get("passed") is not True:
            errors.append("wrapper shutdown-after did not return rc=0 and PASS")
        if shutdown.get("process_tree_reaped") is not True:
            errors.append("wrapper shutdown-after process tree was not reaped")
        if shutdown.get("containment_cleanup_attempted") is not False:
            errors.append("wrapper shutdown-after used or omits forced-cleanup evidence")
        if shutdown.get("containment_cleanup_terminated") is not False:
            errors.append("wrapper shutdown-after reports forced containment termination")
        if shutdown.get("process_tree_terminated") is not False:
            errors.append("wrapper shutdown-after reports process-tree termination")
        result_path = _resolve_summary_reference(shutdown.get("result_file"), summary_path)
        shutdown_record["result_file"] = _file_record(result_path) if result_path else {"missing": True}
        result_text = (
            result_path.read_text(encoding="utf-8", errors="strict")
            if result_path is not None and result_path.is_file()
            else ""
        )
        result_markers = parse_markers(result_text)
        shutdown_marker = bool(result_markers.get("TFDU_SHUTDOWN_PROGRAMMED")) or result_markers.get(
            "SHUTDOWN_EXIT"
        ) == "0"
        shutdown_record["shutdown_marker"] = shutdown_marker
        shutdown_record["p7_shutdown_result"] = result_markers.get("P7_SHUTDOWN_RESULT")
        if not shutdown_marker:
            errors.append("shutdown-after fresh result lacks TFDU_SHUTDOWN_PROGRAMMED or SHUTDOWN_EXIT=0")
        if result_markers.get("P7_SHUTDOWN_RESULT") != "PASS":
            errors.append("shutdown-after fresh result lacks P7_SHUTDOWN_RESULT=PASS")
    process_key = "stage_process" if is_jtag else "ps_process"
    process = summary.get(process_key)
    if not isinstance(process, dict):
        errors.append(f"wrapper candidate process record is missing: {process_key}")
    else:
        if process.get("returncode") != 0 or process.get("passed") is not True:
            errors.append("wrapper candidate process did not return rc=0 and PASS")
        if process.get("process_tree_reaped") is not True:
            errors.append("wrapper candidate process tree was not reaped")
        if process.get("containment_cleanup_attempted") is not False:
            errors.append("wrapper candidate used or omits forced-cleanup evidence")
        if process.get("containment_cleanup_terminated") is not False:
            errors.append("wrapper candidate reports forced containment termination")
        if process.get("process_tree_terminated") is not False:
            errors.append("wrapper candidate reports process-tree termination")
    if is_jtag:
        backend = summary.get("backend_parse")
        if not isinstance(backend, dict) or backend.get("passed") is not True or backend.get(
            "raw_log_bound_to_this_hardware_process"
        ) is not True:
            errors.append("JTAG wrapper strict backend parse is missing or not bound to this run")
    else:
        postprocess = summary.get("postprocess")
        if not isinstance(postprocess, dict) or postprocess.get("passed") is not True:
            errors.append("PS wrapper postprocess is missing or not PASS")
        if stage.get("group") == "ps_stationary":
            if summary.get("mode") != "stationary" or summary.get("service_runtime_limit_sec") != 1800:
                errors.append("stationary wrapper summary is not the exact 1800-second mode")
    return summary, errors, shutdown_record


def _sequence_process_support() -> Any:
    hw_dir = str((ROOT / "scripts" / "hw").resolve(strict=False))
    if hw_dir not in sys.path:
        sys.path.insert(0, hw_dir)
    import run_p7_jtag_axi_stage_safe as support  # noqa: PLC0415

    return support


def _run_stage_process(
    *, stage: Mapping[str, Any], stdout_path: Path, stderr_path: Path
) -> dict[str, Any]:
    support = _sequence_process_support()
    process = support.run_bounded_process(
        name=f"sequence_{stage['id']}",
        command=list(stage["command"]),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_sec=int(stage["wrapper_timeout_sec"]),
        abort_file=resolve_path(str(stage["options"]["--abort-file"])),
        # The safe child wrapper observes the abort file and retains control of
        # its mandatory finally/shutdown path.  The outer containment is only a
        # last-resort wrapper timeout boundary.
        watch_abort=False,
    )
    return asdict(process)


def _new_ledger(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": LEDGER_SCHEMA,
        "created_at_utc": now_utc(),
        "updated_at_utc": now_utc(),
        "status": "READY",
        "hardware_actions_executed": False,
        "network_used": False,
        "motion_used": False,
        "source_commit": plan["source_commit"],
        "sequence_plan": {
            "path": plan["path"],
            "sha256": plan["sha256"],
            "stage_count": plan["stage_count"],
        },
        "offline_checkpoint": {
            "path": plan["offline_checkpoint"]["path"],
            "sha256": plan["offline_checkpoint"]["sha256"],
            "result": "PASS",
            "source_commit": plan["source_commit"],
        },
        "attempt_count": 0,
        "completed_stage_count": 0,
        "next_stage_index": 0,
        "attempts": [],
    }


def _attempt_errors(
    attempt: Any, stage: Mapping[str, Any], *, require_pass: bool
) -> list[str]:
    errors: list[str] = []
    if not isinstance(attempt, dict):
        return ["ledger attempt is not an object"]
    if attempt.get("stage_index") != stage.get("stage_index"):
        errors.append("ledger attempt stage index mismatch")
    if attempt.get("stage_id") != stage.get("id") or attempt.get("group") != stage.get("group"):
        errors.append("ledger attempt stage identity mismatch")
    if attempt.get("command") != stage.get("command"):
        errors.append("ledger attempt exact argv mismatch")
    if attempt.get("state") == "LAUNCH_INTENT" or attempt.get("result") == "IN_PROGRESS":
        return errors + [
            "unresolved launch intent has an orphan/unknown hardware footprint and can never be resumed automatically"
        ]
    if attempt.get("state") != "TERMINAL":
        errors.append("ledger attempt state is not TERMINAL")
    process = attempt.get("process")
    if not isinstance(process, dict):
        errors.append("ledger attempt process record is missing")
    else:
        if require_pass and process.get("returncode") != 0:
            errors.append("resumed PASS attempt has nonzero wrapper return code")
        if process.get("process_tree_reaped") is not True:
            errors.append("ledger attempt does not prove outer wrapper process containment/reap")
        if process.get("containment_closed") is not True or process.get("descendant_count_after") != 0:
            errors.append("ledger attempt outer process containment is not closed and empty")
        if process.get("containment_cleanup_attempted") is not False:
            errors.append("ledger attempt outer process used or omits forced-cleanup evidence")
        if process.get("containment_cleanup_terminated") is not False:
            errors.append("ledger attempt outer process reports forced containment termination")
        if process.get("process_tree_terminated") is not False:
            errors.append("ledger attempt outer process reports process-tree termination")
        errors.extend(_verify_file_record("ledger wrapper stdout", process.get("stdout_file")))
        errors.extend(_verify_file_record("ledger wrapper stderr", process.get("stderr_file")))
    errors.extend(_verify_file_record("ledger wrapper summary", attempt.get("summary_file")))
    if require_pass:
        if attempt.get("result") != "PASS":
            errors.append("only verified PASS attempts can be resumed")
        summary_path = Path(str(attempt.get("summary_file", {}).get("path", ""))).resolve(strict=False)
        _summary, summary_errors, _shutdown = validate_wrapper_summary(
            stage, summary_path, require_pass=True
        )
        errors.extend(summary_errors)
    return errors


def validate_resume_ledger(
    ledger: Any, plan: Mapping[str, Any]
) -> tuple[int, list[str]]:
    errors: list[str] = []
    if not isinstance(ledger, dict) or ledger.get("schema") != LEDGER_SCHEMA:
        return 0, ["execution ledger schema mismatch"]
    expected_plan = ledger.get("sequence_plan")
    if not isinstance(expected_plan, dict) or expected_plan.get("path") != plan["path"] or expected_plan.get(
        "sha256"
    ) != plan["sha256"]:
        errors.append("execution ledger is bound to a different sequence plan")
    offline = ledger.get("offline_checkpoint")
    if not isinstance(offline, dict) or offline.get("path") != plan["offline_checkpoint"]["path"] or offline.get(
        "sha256"
    ) != plan["offline_checkpoint"]["sha256"] or offline.get("result") != "PASS":
        errors.append("execution ledger offline checkpoint binding mismatch")
    if ledger.get("source_commit") != plan["source_commit"]:
        errors.append("execution ledger source commit mismatch")
    attempts = ledger.get("attempts")
    if not isinstance(attempts, list):
        return 0, errors + ["execution ledger attempts list is missing"]
    prefix = 0
    stationary_attempts = 0
    previous_end: datetime | None = None
    for ordinal, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, dict):
            errors.append(f"ledger attempt {ordinal} is malformed")
            continue
        stage_index = attempt.get("stage_index")
        if not isinstance(stage_index, int) or stage_index < 0 or stage_index >= len(plan["stages"]):
            errors.append(f"ledger attempt {ordinal} has an invalid stage index")
            continue
        stage = {**plan["stages"][stage_index], "stage_index": stage_index}
        try:
            started = datetime.fromisoformat(str(attempt.get("started_at_utc")))
            ended = datetime.fromisoformat(str(attempt.get("ended_at_utc")))
            if started.tzinfo is None or ended.tzinfo is None or ended < started:
                raise ValueError("invalid attempt interval")
            if previous_end is not None and started < previous_end:
                errors.append(f"ledger attempt {ordinal} overlaps the prior hardware stage")
            previous_end = ended
        except ValueError:
            errors.append(f"ledger attempt {ordinal} has invalid UTC execution boundaries")
        if stage.get("group") == "ps_stationary":
            stationary_attempts += 1
        if stage_index != prefix:
            errors.append(
                f"ledger attempt {ordinal} is not the next contiguous stage: expected={prefix} observed={stage_index}"
            )
        attempt_errors = _attempt_errors(attempt, stage, require_pass=True)
        errors.extend(f"ledger attempt {ordinal}: {item}" for item in attempt_errors)
        if not attempt_errors and stage_index == prefix:
            prefix += 1
    if stationary_attempts > 1:
        errors.append("execution ledger contains more than one stationary attempt")
    if stationary_attempts == 1 and prefix != len(plan["stages"]):
        errors.append("a stationary attempt exists without a verified final sequence PASS")
    if ledger.get("attempt_count") != len(attempts):
        errors.append("execution ledger attempt_count mismatch")
    if ledger.get("completed_stage_count") != prefix or ledger.get("next_stage_index") != prefix:
        errors.append("execution ledger completed/next counters mismatch")
    return prefix, errors


def _outer_sequence_errors(args: argparse.Namespace, plan: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if os.environ.get(AUTH_ENV) != AUTH_ENV_VALUE:
        errors.append(f"external environment authorization required: {AUTH_ENV}={AUTH_ENV_VALUE}")
    if args.source_commit.lower() != plan["source_commit"]:
        errors.append("outer --source-commit must match the frozen plan/checkpoint commit")
    if args.max_runtime_sec != 1800:
        errors.append(
            "outer --max-runtime-sec must be exactly 1800 as the per-stage/continuous-test ceiling"
        )
    if not args.shutdown_on_exit:
        errors.append("outer --shutdown-on-exit is required")
    if not args.no_ethernet:
        errors.append("outer --no-ethernet is required")
    if not args.no_motion:
        errors.append("outer --no-motion is required")
    if args.lane_count != 2:
        errors.append("outer --lane-count must be exactly 2")
    try:
        mask = int(str(args.max_lane_mask), 0)
    except ValueError:
        mask = 0
    if mask < 1 or mask > 3:
        errors.append("outer --max-lane-mask must be in 0x1..0x3")
    if not args.execution_ledger:
        errors.append("--execution-ledger is required for hardware sequence execution")
    else:
        ledger_path = resolve_path(args.execution_ledger)
        if not _inside(ledger_path, HARDWARE_ROOT) or _path_equal(ledger_path, HARDWARE_ROOT):
            errors.append(f"execution ledger must be a file under {HARDWARE_ROOT}")
        if any(_path_equal(ledger_path, Path(stage["summary_path"])) for stage in plan["stages"]):
            errors.append("execution ledger must not alias a wrapper summary path")
    return errors


def _sequence_manifest(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "P7_AUTHORIZED_HARDWARE_SEQUENCE": "DRY_RUN_ONLY",
        "generated_at_utc": now_utc(),
        "hardware_actions_executed": False,
        "programmed_fpga": False,
        "started_ps_elf": False,
        "jtag_axi_access": False,
        "drove_tfdu_txd": False,
        "enabled_tfdu_receiver": False,
        "uart_access": False,
        "network_used": False,
        "motion_used": False,
        "sequence_plan": {
            "path": plan.get("path"),
            "sha256": plan.get("sha256"),
            "source_commit": plan.get("source_commit"),
            "stage_count": plan.get("stage_count", 0),
        },
        "offline_checkpoint": {
            "path": plan.get("offline_checkpoint", {}).get("path"),
            "sha256": plan.get("offline_checkpoint", {}).get("sha256"),
        },
        "validation_errors": list(plan.get("errors", [])),
    }


def _execute_sequence(args: argparse.Namespace, plan: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    manifest = _sequence_manifest(plan)
    outer_errors = _outer_sequence_errors(args, plan)
    if outer_errors:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
        manifest["reason"] = "outer full-sequence execution controls failed before any wrapper launch"
        manifest["validation_errors"].extend(outer_errors)
        return 2, manifest
    ledger_path = resolve_path(args.execution_ledger)
    if ledger_path.exists():
        if not args.resume:
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
            manifest["reason"] = "execution ledger already exists; explicit --resume is required"
            return 2, manifest
        try:
            ledger = _load_json_object(ledger_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
            manifest["reason"] = f"existing execution ledger is invalid: {exc}"
            return 2, manifest
        next_index, resume_errors = validate_resume_ledger(ledger, plan)
        if resume_errors:
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
            manifest["reason"] = "resume refused because every skipped stage is not a currently verified PASS"
            manifest["validation_errors"].extend(resume_errors)
            return 2, manifest
    else:
        if args.resume:
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
            manifest["reason"] = "--resume was requested but the execution ledger does not exist"
            return 2, manifest
        ledger = _new_ledger(plan)
        next_index = 0
        _atomic_write_json(ledger_path, ledger)
    if next_index == len(plan["stages"]):
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "PASS"
        manifest["reason"] = "all stages were already verified from the immutable resume ledger"
        manifest["execution_ledger"] = _file_record(ledger_path)
        manifest["hardware_actions_executed"] = bool(ledger.get("hardware_actions_executed"))
        return 0, manifest

    log_dir = ledger_path.parent / f".{ledger_path.stem}_wrapper_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    for stage_index in range(next_index, len(plan["stages"])):
        stage = {**plan["stages"][stage_index], "stage_index": stage_index}
        evidence_dir = Path(stage["evidence_dir"])
        if evidence_dir.exists() and (
            evidence_dir.is_symlink() or not evidence_dir.is_dir() or any(evidence_dir.iterdir())
        ):
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
            manifest["reason"] = f"unrecorded stage evidence directory is not new/empty: {evidence_dir}"
            ledger["status"] = "BLOCKED_EVIDENCE_DIR"
            ledger["updated_at_utc"] = now_utc()
            ledger["blocked_stage_index"] = stage_index
            _atomic_write_json(ledger_path, ledger)
            manifest["execution_ledger"] = _file_record(ledger_path)
            return 2, manifest
        if stage["group"] == "ps_stationary" and any(
            item.get("group") == "ps_stationary" for item in ledger.get("attempts", []) if isinstance(item, dict)
        ):
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
            manifest["reason"] = "one-time stationary invariant forbids launching a second stationary attempt"
            return 2, manifest
        stdout_path = log_dir / f"{stage_index + 1:03d}_{stage['id']}.stdout.log"
        stderr_path = log_dir / f"{stage_index + 1:03d}_{stage['id']}.stderr.log"
        # Persist the exact launch intent before the wrapper can possibly be
        # spawned.  An interrupted/orphan intent is never auto-resumable.  This
        # makes a host/orchestrator crash during the final stationary window a
        # permanent one-attempt barrier rather than a path to a second 1800 s
        # launch.
        intent: dict[str, Any] = {
            "attempt": len(ledger["attempts"]) + 1,
            "stage_index": stage_index,
            "stage_id": stage["id"],
            "group": stage["group"],
            "risk_index": stage["risk_index"],
            "case": stage["case"],
            "command": stage["command"],
            "state": "LAUNCH_INTENT",
            "result": "IN_PROGRESS",
            "launch_intent_at_utc": now_utc(),
            "started_at_utc": None,
            "ended_at_utc": None,
            "process": {},
            "summary_file": {"path": stage["summary_path"], "missing": True},
            "shutdown_after": {"present": False},
        }
        ledger["attempts"].append(intent)
        ledger["attempt_count"] = len(ledger["attempts"])
        ledger["status"] = "RUNNING_LAUNCH_INTENT"
        ledger["current_stage_index"] = stage_index
        ledger["current_stage_id"] = stage["id"]
        ledger["hardware_actions_executed"] = True
        ledger["updated_at_utc"] = now_utc()
        _atomic_write_json(ledger_path, ledger)
        started = time.monotonic()
        try:
            process = _run_stage_process(stage=stage, stdout_path=stdout_path, stderr_path=stderr_path)
        except Exception as exc:  # the persisted intent remains auditable
            process = {
                "returncode": 127,
                "process_tree_reaped": False,
                "containment_closed": False,
                "descendant_count_after": -1,
                "started_at_utc": intent["launch_intent_at_utc"],
                "ended_at_utc": now_utc(),
                "launch_error": f"{type(exc).__name__}: {exc}",
            }
        summary_path = Path(stage["summary_path"])
        _summary, summary_errors, shutdown_record = validate_wrapper_summary(
            stage, summary_path, require_pass=True
        )
        process_ok = (
            process.get("returncode") == 0
            and process.get("process_tree_reaped") is True
            and process.get("containment_closed") is True
            and process.get("descendant_count_after") == 0
            and process.get("containment_cleanup_attempted") is False
            and process.get("containment_cleanup_terminated") is False
            and process.get("process_tree_terminated") is False
        )
        passed = process_ok and not summary_errors
        attempt = {
            **intent,
            "state": "TERMINAL",
            "started_at_utc": process.get("started_at_utc"),
            "ended_at_utc": process.get("ended_at_utc"),
            "orchestrator_elapsed_seconds": round(time.monotonic() - started, 6),
            "result": "PASS" if passed else "FAIL",
            "failures": ([] if process_ok else ["outer wrapper process containment/return-code policy failed"])
            + summary_errors,
            "process": {
                **process,
                "stdout_file": _file_record(stdout_path),
                "stderr_file": _file_record(stderr_path),
            },
            "summary_file": _file_record(summary_path),
            "shutdown_after": shutdown_record,
        }
        ledger["attempts"][-1] = attempt
        ledger["hardware_actions_executed"] = True
        ledger["updated_at_utc"] = now_utc()
        ledger.pop("current_stage_index", None)
        ledger.pop("current_stage_id", None)
        if passed:
            ledger["completed_stage_count"] = stage_index + 1
            ledger["next_stage_index"] = stage_index + 1
            ledger["status"] = "RUNNING" if stage_index + 1 < len(plan["stages"]) else "PASS"
        else:
            ledger["status"] = "FAIL"
            ledger["failed_stage_index"] = stage_index
            ledger["next_stage_index"] = stage_index
        _atomic_write_json(ledger_path, ledger)
        if not passed:
            manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "FAIL"
            manifest["reason"] = "sequence stopped at the first wrapper/summary/shutdown failure"
            manifest["failed_stage"] = {
                "index": stage_index,
                "id": stage["id"],
                "failures": attempt["failures"],
            }
            manifest["execution_ledger"] = _file_record(ledger_path)
            manifest["hardware_actions_executed"] = True
            return 1, manifest
    manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "PASS"
    manifest["reason"] = "all 66 stages passed in strict order; the sole 1800-second stationary stage was last"
    manifest["hardware_actions_executed"] = True
    manifest["execution_ledger"] = _file_record(ledger_path)
    return 0, manifest


def _sequence_main(args: argparse.Namespace) -> int:
    if not args.sequence_plan_sha256:
        report = {
            "P7_AUTHORIZED_HARDWARE_SEQUENCE": "BLOCKED",
            "hardware_actions_executed": False,
            "reason": "--sequence-plan-sha256 is mandatory",
        }
        print(json.dumps(report, indent=2, ensure_ascii=False) if args.json_summary else "P7_AUTHORIZED_HARDWARE_SEQUENCE: BLOCKED")
        return 2
    plan = validate_sequence_plan(resolve_path(args.sequence_plan), args.sequence_plan_sha256.lower())
    manifest = _sequence_manifest(plan)
    if plan["errors"]:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
        manifest["reason"] = "strict immutable sequence-plan validation failed"
        returncode = 2
    elif not args.execute_hardware:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "DRY_RUN_VALIDATED"
        manifest["reason"] = "all 66 planned wrapper argv vectors and immutable inputs validated; no process was launched"
        returncode = 0
    else:
        returncode, manifest = _execute_sequence(args, plan)
    print(
        json.dumps(manifest, indent=2, ensure_ascii=False)
        if args.json_summary
        else f"P7_AUTHORIZED_HARDWARE_SEQUENCE: {manifest['P7_AUTHORIZED_HARDWARE_SEQUENCE']}"
    )
    return returncode


def parse_markers(text: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        markers[key.strip()] = value.strip()
    return markers


def normalize_p7_idcode(value: str) -> str:
    """Return one exact eight-digit IDCODE representation or ``""``.

    Vivado's ``get_property IDCODE`` returns a 32-bit binary string on the
    canonical board while XSDB commonly reports the same value as hexadecimal.
    No masks, short values, or variable-width numeric forms are accepted.
    """

    clean = value.strip().replace("_", "")
    if re.fullmatch(r"[01]{32}", clean):
        return f"{int(clean, 2):08X}"
    match = re.fullmatch(r"(?:0[xX])?([0-9A-Fa-f]{8})", clean)
    return match.group(1).upper() if match else ""


def canonical_live_identity_failures(
    markers: Mapping[str, str],
    *,
    expected_part: str,
    prefix: str,
    label: str,
) -> list[str]:
    """Validate the one authorized full-part to live-silicon mapping."""

    failures: list[str] = []
    if expected_part.casefold() != CANONICAL_FULL_PART.casefold():
        failures.append(
            f"{label} canonical part is unsupported: expected={CANONICAL_FULL_PART} "
            f"observed={expected_part or 'MISSING'}"
        )
        return failures
    expected_text = {
        f"{prefix}_CANONICAL_PART": CANONICAL_FULL_PART,
        f"{prefix}_LIVE_PART": CANONICAL_LIVE_PART,
        f"{prefix}_LIVE_DEVICE": CANONICAL_LIVE_DEVICE,
    }
    for key, value in expected_text.items():
        observed = markers.get(key, "")
        if observed.casefold() != value.casefold():
            failures.append(
                f"{label} identity marker mismatch: {key} expected={value} "
                f"observed={observed or 'MISSING'}"
            )
    idcode_key = f"{prefix}_LIVE_IDCODE"
    observed_idcode = markers.get(idcode_key, "")
    normalized = normalize_p7_idcode(observed_idcode)
    if normalized != CANONICAL_LIVE_IDCODE_HEX:
        failures.append(
            f"{label} identity marker mismatch: {idcode_key} "
            f"expected={CANONICAL_LIVE_IDCODE_BINARY} "
            f"observed={observed_idcode or 'MISSING'}"
        )
    return failures


def evaluate_preflight(
    *,
    returncode: int,
    stdout: str,
    result_text: str,
    expected_board_id: str,
    expected_part: str,
    expected_target: str,
) -> tuple[bool, list[str]]:
    """Return PASS only for rc=0 and exact fresh result-file markers."""

    failures: list[str] = []
    if returncode != 0:
        failures.append(f"preflight process returned nonzero exit code: {returncode}")
    result_markers = parse_markers(result_text)
    stdout_markers = parse_markers(stdout)
    expected = {
        "P7_HW_PREFLIGHT_RESULT": "PASS",
        "P7_HW_PREFLIGHT_AUTHORIZED": "1",
        "P7_HW_PREFLIGHT_READ_ONLY": "1",
        "P7_HW_PREFLIGHT_BOARD_ID": expected_board_id,
        # Retained compatibility alias; the unambiguous canonical/live fields
        # below are authoritative and are validated independently.
        "P7_HW_PREFLIGHT_PART": expected_part,
        "P7_HW_PREFLIGHT_TARGET": expected_target,
        "P7_HW_PREFLIGHT_DEVICE": CANONICAL_LIVE_DEVICE,
    }
    for key, value in expected.items():
        if result_markers.get(key) != value:
            failures.append(
                f"preflight result marker mismatch: {key} expected={value} observed={result_markers.get(key, 'MISSING')}"
            )
    if stdout_markers.get("P7_HW_PREFLIGHT_RESULT") != "PASS":
        failures.append("preflight PASS marker missing from process stdout")
    failures.extend(
        canonical_live_identity_failures(
            result_markers,
            expected_part=expected_part,
            prefix="P7_HW_PREFLIGHT",
            label="preflight",
        )
    )
    legacy_idcode = normalize_p7_idcode(result_markers.get("P7_HW_PREFLIGHT_IDCODE", ""))
    if legacy_idcode != CANONICAL_LIVE_IDCODE_HEX:
        failures.append("preflight compatibility IDCODE marker is missing or not the exact authorized IDCODE")
    return not failures, failures


def build_preflight_command(args: argparse.Namespace, result_file: Path) -> list[str]:
    return [
        str(Path(args.vivado_path).resolve(strict=False)),
        "-mode",
        "batch",
        "-source",
        str(DEFAULT_PREFLIGHT_TCL),
        "-tclargs",
        str(ROOT),
        str(resolve_path(args.authorization_file)),
        args.board_id,
        args.expected_part,
        args.expected_target,
        args.hw_server_url,
        str(result_file),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P7 strict authorized sequence executor; default is validation-only dry-run."
    )
    add_common_arguments(parser)
    parser.add_argument("--sequence-plan", default="")
    parser.add_argument("--sequence-plan-sha256", default="")
    parser.add_argument("--execution-ledger", default="")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--evidence-dir", default="")
    parser.add_argument("--preflight-timeout-sec", type=int, default=180)
    parser.add_argument("--json-summary", action="store_true")
    return parser


def _base_manifest(args: argparse.Namespace, safety: dict[str, Any]) -> dict[str, Any]:
    return {
        "P7_AUTHORIZED_HARDWARE_SEQUENCE": "DRY_RUN_ONLY",
        "generated_at_utc": now_utc(),
        "hardware_actions_executed": False,
        "preflight_hardware_connection": False,
        "programmed_fpga": False,
        "started_ps_elf": False,
        "jtag_axi_access": False,
        "drove_tfdu_txd": False,
        "enabled_tfdu_receiver": False,
        "uart_access": False,
        "network_used": False,
        "motion_used": False,
        "shutdown_required_for_this_preflight": False,
        "programming_implemented": False,
        "ps_mailbox_payload_runner_implemented": False,
        "supported_hardware_actions": ["read_only_target_preflight"],
        "safety_validation": safety,
        "requested_execute_hardware": bool(args.execute_hardware),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.sequence_plan:
        return _sequence_main(args)
    if args.sequence_plan_sha256 or args.execution_ledger or args.resume:
        manifest = {
            "P7_AUTHORIZED_HARDWARE_SEQUENCE": "BLOCKED",
            "hardware_actions_executed": False,
            "reason": "sequence options require --sequence-plan",
        }
        print(
            json.dumps(manifest, indent=2, ensure_ascii=False)
            if args.json_summary
            else "P7_AUTHORIZED_HARDWARE_SEQUENCE: BLOCKED"
        )
        return 2
    safety = validate_request(args)
    manifest = _base_manifest(args, safety)

    if not args.execute_hardware:
        manifest["reason"] = "default dry-run path; no external hardware tool was launched"
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "DRY_RUN_ONLY"
        if args.evidence_dir:
            evidence_dir = resolve_path(args.evidence_dir)
            _write_json(evidence_dir / "p7_preflight_stage_manifest.json", manifest)
        print(json.dumps(manifest, indent=2, ensure_ascii=False) if args.json_summary else "P7_AUTHORIZED_HARDWARE_SEQUENCE: DRY_RUN_ONLY")
        return 0

    if safety["errors"]:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
        manifest["reason"] = "mandatory authorization or artifact validation failed before hardware connection"
        if args.evidence_dir:
            evidence_dir = resolve_path(args.evidence_dir)
            _write_json(evidence_dir / "p7_preflight_stage_manifest.json", manifest)
        print(json.dumps(manifest, indent=2, ensure_ascii=False) if args.json_summary else "P7_AUTHORIZED_HARDWARE_SEQUENCE: BLOCKED")
        return 2

    if not is_exact_vivado_batch_launcher(args.vivado_path):
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
        manifest["reason"] = "Vivado launcher must be exactly vivado.bat; direct vivado.exe is forbidden"
        print(json.dumps(manifest, indent=2, ensure_ascii=False) if args.json_summary else "P7_AUTHORIZED_HARDWARE_SEQUENCE: BLOCKED")
        return 2

    if args.preflight_timeout_sec < 1 or args.preflight_timeout_sec > 300:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "BLOCKED"
        manifest["reason"] = "preflight timeout must be in 1..300 seconds"
        print(json.dumps(manifest, indent=2, ensure_ascii=False) if args.json_summary else "P7_AUTHORIZED_HARDWARE_SEQUENCE: BLOCKED")
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_dir = resolve_path(args.evidence_dir) if args.evidence_dir else ROOT / "evidence" / "hardware" / "p7" / "preflight" / stamp
    evidence_dir.mkdir(parents=True, exist_ok=True)
    result_file = evidence_dir / "p7_hw_preflight_result.txt"
    stdout_file = evidence_dir / "p7_hw_preflight.stdout.log"
    stderr_file = evidence_dir / "p7_hw_preflight.stderr.log"
    manifest_file = evidence_dir / "p7_preflight_stage_manifest.json"
    if result_file.exists():
        result_file.unlink()

    command = build_preflight_command(args, result_file)
    manifest["preflight_command"] = command
    manifest["preflight_tcl_sha256"] = sha256_file(DEFAULT_PREFLIGHT_TCL)
    manifest["evidence_dir"] = str(evidence_dir)
    started = now_utc()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=args.preflight_timeout_sec,
            check=False,
        )
        returncode = int(proc.returncode)
        stdout = proc.stdout
        stderr = proc.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        stderr += f"\nP7 preflight timed out after {args.preflight_timeout_sec} seconds\n"
    stdout_file.write_text(stdout, encoding="utf-8")
    stderr_file.write_text(stderr, encoding="utf-8")
    result_text = result_file.read_text(encoding="utf-8", errors="strict") if result_file.is_file() else ""
    passed, failures = evaluate_preflight(
        returncode=returncode,
        stdout=stdout,
        result_text=result_text,
        expected_board_id=args.board_id,
        expected_part=args.expected_part,
        expected_target=args.expected_target,
    )
    manifest.update(
        {
            "preflight_started_at_utc": started,
            "preflight_finished_at_utc": now_utc(),
            "preflight_returncode": returncode,
            "preflight_result_file": str(result_file),
            "preflight_stdout_file": str(stdout_file),
            "preflight_stderr_file": str(stderr_file),
            "preflight_failures": failures,
            "preflight_hardware_connection": True,
            "hardware_actions_executed": True,
        }
    )
    if passed:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "PREFLIGHT_ONLY_PASS"
        manifest["reason"] = "authorized read-only target preflight passed; no programming or TFDU action was implemented"
    else:
        manifest["P7_AUTHORIZED_HARDWARE_SEQUENCE"] = "FAIL"
        manifest["reason"] = "read-only preflight failed; nonzero exit codes can never be promoted by markers"
    _write_json(manifest_file, manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False) if args.json_summary else f"P7_AUTHORIZED_HARDWARE_SEQUENCE: {manifest['P7_AUTHORIZED_HARDWARE_SEQUENCE']}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
