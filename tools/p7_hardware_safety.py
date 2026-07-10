#!/usr/bin/env python3
"""Fail-closed P7 hardware authorization and artifact validation.

This module never connects to hardware.  It is shared by the P7 preflight
orchestrator and its offline tests.  Supplying ``--execute-hardware`` here only
requests a complete validation of the execution controls; no external hardware
tool is launched by this file.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUTH_ENV = "RF_COMM_HW_AUTH"
AUTH_ENV_VALUE = "P7_STATIONARY_APP_LAYER_APPROVED"
AUTH_MARKER = "P7_STATIONARY_APP_LAYER_APPROVED"
AUTHORIZED_STAGE = "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET"
MAX_P7_RUNTIME_SEC = 1800
DEFAULT_ABORT_FILE = ROOT / ".hardware_authorization" / "ABORT_NOW.txt"
DEFAULT_PREFLIGHT_TCL = ROOT / "scripts" / "hw" / "p7_hw_preflight.tcl"
HARDWARE_EXECUTION_LOCK = ROOT / ".hardware_authorization" / "P7_HARDWARE_EXECUTION.lock"


@dataclass(frozen=True)
class ArtifactDefinition:
    name: str
    path_attr: str
    sha_attr: str
    auth_path_key: str
    auth_sha_key: str
    required: bool = True


ARTIFACT_DEFINITIONS = (
    ArtifactDefinition("plan", "plan_file", "plan_sha256", "P7_PLAN_PATH", "P7_PLAN_SHA256"),
    ArtifactDefinition("bitstream", "bitstream", "bitstream_sha256", "BITSTREAM_PATH", "BITSTREAM_SHA256"),
    ArtifactDefinition("xsa", "xsa", "xsa_sha256", "XSA_PATH", "XSA_SHA256"),
    ArtifactDefinition("elf", "elf", "elf_sha256", "ELF_PATH", "ELF_SHA256"),
    ArtifactDefinition("profile", "profile", "profile_sha256", "PROFILE_PATH", "PROFILE_SHA256"),
    ArtifactDefinition("active_xdc", "active_xdc", "active_xdc_sha256", "ACTIVE_XDC_PATH", "ACTIVE_XDC_SHA256"),
    ArtifactDefinition("pinmap", "pinmap", "pinmap_sha256", "PINMAP_PATH", "PINMAP_SHA256"),
    ArtifactDefinition("register_map", "register_map", "register_map_sha256", "REGISTER_MAP_PATH", "REGISTER_MAP_SHA256"),
    ArtifactDefinition(
        "shutdown_bitstream",
        "shutdown_bitstream",
        "shutdown_bitstream_sha256",
        "SHUTDOWN_BITSTREAM_PATH",
        "SHUTDOWN_BITSTREAM_SHA256",
    ),
    ArtifactDefinition("ltx", "ltx", "ltx_sha256", "LTX_PATH", "LTX_SHA256", required=False),
)


SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-fA-F]{40}$")
LOCAL_HW_SERVER_RE = re.compile(r"^(?:tcp:)?(?:localhost|127[.]0[.]0[.]1):[0-9]{1,5}$", re.IGNORECASE)


class HardwareExecutionLock:
    """Exclusive cross-wrapper board lock with fail-closed stale-lock policy."""

    def __init__(self, path: Path, token: str, owner: dict[str, Any]):
        self.path = path
        self.token = token
        self.owner = owner
        self.acquired = True
        atexit.register(self.release)

    @classmethod
    def acquire(cls, *, owner: dict[str, Any], path: Path = HARDWARE_EXECUTION_LOCK) -> "HardwareExecutionLock":
        path = path.resolve(strict=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        token = secrets.token_hex(32)
        payload = {
            "schema": "rf-comm-p7-hardware-execution-lock-v1",
            "token": token,
            "pid": os.getpid(),
            **owner,
        }
        encoded = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            try:
                existing = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                existing = "UNREADABLE"
            raise RuntimeError(
                f"P7 hardware execution lock already exists; inspect board state and lock before retry: "
                f"path={path} owner={existing}"
            ) from exc
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            try:
                path.unlink()
            except OSError:
                pass
            raise
        return cls(path, token, payload)

    def record(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "token_sha256": hashlib.sha256(self.token.encode("ascii")).hexdigest(),
            "owner": {key: value for key, value in self.owner.items() if key != "token"},
            "acquired": self.acquired,
            "stale_lock_auto_recovery": False,
        }

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8", errors="strict"))
            if not isinstance(payload, dict) or payload.get("token") != self.token:
                # Never remove a lock that another process replaced or owns.
                return
            self.path.unlink()
            self.acquired = False
        except FileNotFoundError:
            self.acquired = False
        except (OSError, UnicodeError, json.JSONDecodeError):
            # Preserve an ambiguous lock for explicit human/agent inspection.
            return


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve(strict=False) if path.is_absolute() else (ROOT / path).resolve(strict=False)


def normalized_path(value: str | Path) -> str:
    return str(resolve_path(value)).replace("\\", "/").casefold()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_int(value: str | int | None, *, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    return int(value, 0)


def parse_authorization_file(path: Path) -> tuple[dict[str, str], list[str], list[str]]:
    fields: dict[str, str] = {}
    markers: list[str] = []
    duplicates: list[str] = []
    text = path.read_text(encoding="utf-8", errors="strict")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            markers.append(line)
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in fields:
            duplicates.append(key)
        fields[key] = value
    return fields, markers, duplicates


def current_git_state() -> tuple[str | None, list[str] | None, str | None]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, None, str(exc)
    if head.returncode != 0 or status.returncode != 0:
        detail = (head.stderr + status.stderr).strip() or "git command failed"
        return None, None, detail
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    return head.stdout.strip().lower(), dirty, None


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--authorization-file", default="")
    parser.add_argument("--authorization-sha256", default="")
    parser.add_argument("--board-id", default="")
    parser.add_argument("--expected-part", default="")
    parser.add_argument("--expected-target", default="")
    parser.add_argument("--source-commit", default="")
    parser.add_argument("--plan-file", default="")
    parser.add_argument("--plan-sha256", default="")
    parser.add_argument("--bitstream", default="")
    parser.add_argument("--bitstream-sha256", default="")
    parser.add_argument("--xsa", default="")
    parser.add_argument("--xsa-sha256", default="")
    parser.add_argument("--elf", default="")
    parser.add_argument("--elf-sha256", default="")
    parser.add_argument("--profile", default="")
    parser.add_argument("--profile-sha256", default="")
    parser.add_argument("--active-xdc", default="")
    parser.add_argument("--active-xdc-sha256", default="")
    parser.add_argument("--pinmap", default="")
    parser.add_argument("--pinmap-sha256", default="")
    parser.add_argument("--register-map", default="")
    parser.add_argument("--register-map-sha256", default="")
    parser.add_argument("--shutdown-bitstream", default="")
    parser.add_argument("--shutdown-bitstream-sha256", default="")
    parser.add_argument("--ltx", default="")
    parser.add_argument("--ltx-sha256", default="")
    parser.add_argument("--max-runtime-sec", type=int)
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--no-ethernet", action="store_true")
    parser.add_argument("--no-motion", action="store_true")
    parser.add_argument("--lane-count", type=int)
    parser.add_argument("--max-lane-mask", default="")
    parser.add_argument("--abort-file", default=str(DEFAULT_ABORT_FILE.relative_to(ROOT)))
    parser.add_argument("--vivado-path", default="")
    parser.add_argument("--hw-server-url", default="localhost:3121")


def _require_value(errors: list[str], label: str, value: Any) -> bool:
    if value is None or value == "":
        errors.append(f"missing required execution control: {label}")
        return False
    return True


def _validate_artifacts(args: argparse.Namespace, errors: list[str]) -> dict[str, dict[str, Any]]:
    artifacts: dict[str, dict[str, Any]] = {}
    for definition in ARTIFACT_DEFINITIONS:
        raw_path = getattr(args, definition.path_attr, "")
        expected = getattr(args, definition.sha_attr, "")
        if not raw_path and not expected and not definition.required:
            continue
        if not raw_path:
            errors.append(f"missing artifact path: --{definition.path_attr.replace('_', '-')}")
            continue
        if not expected:
            errors.append(f"missing expected SHA256: --{definition.sha_attr.replace('_', '-')}")
            continue
        path = resolve_path(raw_path)
        entry: dict[str, Any] = {
            "path": str(path),
            "expected_sha256": expected.lower(),
            "exists": path.is_file(),
        }
        if not SHA256_RE.fullmatch(expected):
            errors.append(f"invalid SHA256 syntax for {definition.name}: {expected}")
            entry["actual_sha256"] = "NOT_COMPUTED"
        elif not path.is_file():
            errors.append(f"artifact file missing: {definition.name}={path}")
            entry["actual_sha256"] = "MISSING"
        else:
            actual = sha256_file(path)
            entry["actual_sha256"] = actual
            if actual != expected.lower():
                errors.append(
                    f"artifact SHA256 mismatch for {definition.name}: expected={expected.lower()} actual={actual} path={path}"
                )
        artifacts[definition.name] = entry
    return artifacts


def _validate_authorization(
    args: argparse.Namespace,
    artifacts: dict[str, dict[str, Any]],
    errors: list[str],
) -> tuple[dict[str, str], dict[str, Any]]:
    raw_auth = getattr(args, "authorization_file", "")
    expected_auth_sha = getattr(args, "authorization_sha256", "")
    metadata: dict[str, Any] = {"exists": False, "path": raw_auth or "MISSING"}
    if not raw_auth:
        errors.append("missing required execution control: --authorization-file")
        return {}, metadata
    auth_path = resolve_path(raw_auth)
    metadata["path"] = str(auth_path)
    metadata["exists"] = auth_path.is_file()
    authorization_root = (ROOT / ".hardware_authorization").resolve(strict=False)
    try:
        auth_path.relative_to(authorization_root)
    except ValueError:
        errors.append(f"P7 authorization file must be under {authorization_root}: {auth_path}")
    if not auth_path.is_file():
        errors.append(f"P7 authorization file missing: {auth_path}")
        return {}, metadata
    if not expected_auth_sha:
        errors.append("missing expected SHA256: --authorization-sha256")
    elif not SHA256_RE.fullmatch(expected_auth_sha):
        errors.append(f"invalid authorization SHA256 syntax: {expected_auth_sha}")
    actual_auth_sha = sha256_file(auth_path)
    metadata["actual_sha256"] = actual_auth_sha
    metadata["expected_sha256"] = expected_auth_sha.lower() if expected_auth_sha else "MISSING"
    if expected_auth_sha and SHA256_RE.fullmatch(expected_auth_sha) and actual_auth_sha != expected_auth_sha.lower():
        errors.append(
            f"authorization SHA256 mismatch: expected={expected_auth_sha.lower()} actual={actual_auth_sha}"
        )
    try:
        fields, markers, duplicates = parse_authorization_file(auth_path)
    except (OSError, UnicodeError) as exc:
        errors.append(f"unable to parse P7 authorization file: {exc}")
        return {}, metadata
    metadata["markers"] = markers
    metadata["duplicate_keys"] = duplicates
    if duplicates:
        errors.append(f"duplicate authorization keys: {', '.join(sorted(set(duplicates)))}")
    if AUTH_MARKER not in markers:
        errors.append(f"authorization marker missing: {AUTH_MARKER}")

    exact_fields = {
        "AUTHORIZED_STAGE": AUTHORIZED_STAGE,
        "USER_HARDWARE_AUTHORIZATION_FOR_P7": "GRANTED",
        "BOARD_ID": getattr(args, "board_id", ""),
        "EXPECTED_PART": getattr(args, "expected_part", ""),
        "EXPECTED_TARGET": getattr(args, "expected_target", ""),
        "SOURCE_COMMIT": getattr(args, "source_commit", "").lower(),
        "SHUTDOWN_ON_EXIT": "required",
        "NO_ETHERNET": "true",
        "NO_MOTION": "true",
        "LANE_COUNT": "2",
        "MAX_LANE_MASK": "0x3",
    }
    for key, expected in exact_fields.items():
        observed = fields.get(key)
        if observed is None:
            errors.append(f"authorization field missing: {key}")
        elif not expected:
            errors.append(f"execution control missing for authorization comparison: {key}")
        elif observed.casefold() != expected.casefold():
            errors.append(f"authorization field mismatch: {key} expected={expected} observed={observed}")

    auth_runtime_text = fields.get("MAX_RUNTIME_SEC", "")
    try:
        auth_runtime = int(auth_runtime_text, 10)
    except ValueError:
        auth_runtime = 0
        errors.append(f"authorization MAX_RUNTIME_SEC is invalid: {auth_runtime_text or 'MISSING'}")
    requested_runtime = getattr(args, "max_runtime_sec", None)
    if auth_runtime < 1 or auth_runtime > MAX_P7_RUNTIME_SEC:
        errors.append(f"authorization MAX_RUNTIME_SEC must be in 1..{MAX_P7_RUNTIME_SEC}: {auth_runtime}")
    if requested_runtime and auth_runtime < requested_runtime:
        errors.append(
            f"authorization runtime is lower than requested: authorized={auth_runtime} requested={requested_runtime}"
        )

    for definition in ARTIFACT_DEFINITIONS:
        if definition.name not in artifacts:
            continue
        entry = artifacts[definition.name]
        observed_path = fields.get(definition.auth_path_key)
        observed_sha = fields.get(definition.auth_sha_key)
        if observed_path is None:
            errors.append(f"authorization artifact path missing: {definition.auth_path_key}")
        elif normalized_path(observed_path) != normalized_path(entry["path"]):
            errors.append(
                f"authorization artifact path mismatch: {definition.auth_path_key} expected={entry['path']} observed={observed_path}"
            )
        if observed_sha is None:
            errors.append(f"authorization artifact SHA256 missing: {definition.auth_sha_key}")
        elif observed_sha.lower() != entry["expected_sha256"]:
            errors.append(
                f"authorization artifact SHA256 mismatch: {definition.auth_sha_key} "
                f"expected={entry['expected_sha256']} observed={observed_sha.lower()}"
            )
    return fields, metadata


def validate_request(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not getattr(args, "execute_hardware", False):
        errors.append("missing required execution control: --execute-hardware")
    if os.environ.get(AUTH_ENV) != AUTH_ENV_VALUE:
        errors.append(f"external environment authorization required: {AUTH_ENV}={AUTH_ENV_VALUE}")
    for label, value in (
        ("--board-id", getattr(args, "board_id", "")),
        ("--expected-part", getattr(args, "expected_part", "")),
        ("--expected-target", getattr(args, "expected_target", "")),
        ("--source-commit", getattr(args, "source_commit", "")),
        ("--vivado-path", getattr(args, "vivado_path", "")),
    ):
        _require_value(errors, label, value)

    source_commit = getattr(args, "source_commit", "")
    if source_commit and not COMMIT_RE.fullmatch(source_commit):
        errors.append(f"source commit must be a full 40-hex commit: {source_commit}")
    git_head: str | None = None
    dirty_files: list[str] | None = None
    git_error: str | None = None
    if source_commit:
        git_head, dirty_files, git_error = current_git_state()
        if git_error:
            errors.append(f"unable to establish source commit: {git_error}")
        elif git_head != source_commit.lower():
            errors.append(f"source commit mismatch: requested={source_commit.lower()} current={git_head}")
        if dirty_files:
            warnings.append("workspace has uncommitted changes; frozen artifact hashes remain authoritative")

    runtime = getattr(args, "max_runtime_sec", None)
    if runtime is None:
        errors.append("missing required execution control: --max-runtime-sec")
    elif runtime < 1 or runtime > MAX_P7_RUNTIME_SEC:
        errors.append(f"max runtime must be in 1..{MAX_P7_RUNTIME_SEC}: {runtime}")
    if not getattr(args, "shutdown_on_exit", False):
        errors.append("missing required execution control: --shutdown-on-exit")
    if not getattr(args, "no_ethernet", False):
        errors.append("missing required execution control: --no-ethernet")
    if not getattr(args, "no_motion", False):
        errors.append("missing required execution control: --no-motion")
    if getattr(args, "lane_count", None) != 2:
        errors.append(f"lane count must be exactly 2: {getattr(args, 'lane_count', None)}")
    try:
        max_lane_mask = parse_int(getattr(args, "max_lane_mask", ""))
    except ValueError:
        max_lane_mask = None
        errors.append(f"invalid max lane mask: {getattr(args, 'max_lane_mask', '')}")
    if max_lane_mask is None or max_lane_mask < 1 or max_lane_mask > 0x3:
        errors.append(f"max lane mask must be in 0x1..0x3: {getattr(args, 'max_lane_mask', '') or 'MISSING'}")

    abort_file = resolve_path(getattr(args, "abort_file", str(DEFAULT_ABORT_FILE)))
    if abort_file.exists():
        errors.append(f"operator abort file is present: {abort_file}")

    vivado_path_value = getattr(args, "vivado_path", "")
    vivado_path = Path(vivado_path_value).resolve(strict=False) if vivado_path_value else None
    if vivado_path and not vivado_path.is_file():
        errors.append(f"Vivado executable missing: {vivado_path}")
    hw_server_url = getattr(args, "hw_server_url", "")
    if not LOCAL_HW_SERVER_RE.fullmatch(hw_server_url or ""):
        errors.append(f"hw_server URL must be local and explicit: {hw_server_url or 'MISSING'}")
    if not DEFAULT_PREFLIGHT_TCL.is_file():
        errors.append(f"P7 preflight Tcl missing: {DEFAULT_PREFLIGHT_TCL}")

    artifacts = _validate_artifacts(args, errors)
    auth_fields, auth_metadata = _validate_authorization(args, artifacts, errors)

    report = {
        "P7_HARDWARE_SAFETY": "PASS" if not errors else "BLOCKED",
        "ready_for_hardware_preflight": not errors,
        "hardware_actions_executed": False,
        "programmed_fpga": False,
        "drove_tfdu_txd": False,
        "started_ps_elf": False,
        "authorization_environment_present": os.environ.get(AUTH_ENV) == AUTH_ENV_VALUE,
        "authorization": auth_metadata,
        "authorization_fields": auth_fields,
        "source_commit_requested": source_commit or "MISSING",
        "source_commit_current": git_head or "UNKNOWN",
        "dirty_files": dirty_files if dirty_files is not None else [],
        "max_runtime_sec": runtime,
        "lane_count": getattr(args, "lane_count", None),
        "max_lane_mask": None if max_lane_mask is None else f"0x{max_lane_mask:x}",
        "no_ethernet": bool(getattr(args, "no_ethernet", False)),
        "no_motion": bool(getattr(args, "no_motion", False)),
        "shutdown_on_exit": bool(getattr(args, "shutdown_on_exit", False)),
        "abort_file": str(abort_file),
        "abort_file_present": abort_file.exists(),
        "hw_server_url": hw_server_url,
        "preflight_tcl": str(DEFAULT_PREFLIGHT_TCL),
        "preflight_tcl_sha256": sha256_file(DEFAULT_PREFLIGHT_TCL) if DEFAULT_PREFLIGHT_TCL.is_file() else "MISSING",
        "artifacts": artifacts,
        "errors": errors,
        "warnings": warnings,
    }
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the P7 hardware authorization boundary without connecting to hardware."
    )
    add_common_arguments(parser)
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_request(args)
    if not args.execute_hardware:
        report["P7_HARDWARE_SAFETY"] = "DRY_RUN_ONLY"
        report["reason"] = "default path performs validation only and never connects to hardware"
        report["ready_for_hardware_preflight"] = False
        return_code = 0
    else:
        report["reason"] = (
            "all execution controls validated offline; no hardware action was performed by this validator"
            if not report["errors"]
            else "one or more mandatory execution controls failed"
        )
        return_code = 0 if not report["errors"] else 2
    if args.json_summary:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"P7_HARDWARE_SAFETY: {report['P7_HARDWARE_SAFETY']}")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
        for error in report["errors"]:
            print(f"BLOCKED: {error}")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
