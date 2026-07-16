#!/usr/bin/env python3
"""Source-bound Vivado helper identity validation for P7 hardware wrappers.

The runtime validator is intentionally hardware-free.  It hashes executable
bytes in Python, obtains Windows version/AuthentiCode metadata through one
fixed source-bound PowerShell probe, and requires one complete runtime profile.
Historical SHA profiles remain available only to validate immutable evidence.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = (ROOT / "config" / "p7_vivado_helper_identity_profiles.json").resolve()
EXPECTED_MANIFEST_SHA256 = "67645bc53ae6c484204604ae3741bbce2d24fb7dbff6a5e63e8ea1a68972ed94"
MANIFEST_SCHEMA = "rf-comm-p7-vivado-helper-identity-profiles-v1"
PROBE_SCHEMA = "rf-comm-p7-vivado-helper-identity-probe-v1"
VALIDATION_SCHEMA = "rf-comm-p7-vivado-helper-identity-validation-v1"
EXPECTED_VIVADO_HELPER_ROLES = ("cs_server", "rdi_xsdb", "cmd", "conhost")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
THUMBPRINT_RE = re.compile(r"^[0-9A-F]{40}$")

_RECORD_KEYS = frozenset(
    {
        "path",
        "sha256",
        "bytes",
        "file_version",
        "product_version",
        "company_name",
        "signature_status",
        "signature_type",
        "signer_subject",
        "signer_thumbprint",
    }
)
_PROBE_RECORD_KEYS = frozenset((_RECORD_KEYS - {"sha256"}) | {"role"})


class IdentityManifestError(RuntimeError):
    """Raised when the source-bound identity manifest is malformed or changed."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if type(payload) is not dict:
        raise IdentityManifestError(f"JSON root must be an object: {path}")
    return payload


def _validate_hash_map(value: Any, label: str) -> dict[str, str]:
    if type(value) is not dict or set(value) != set(EXPECTED_VIVADO_HELPER_ROLES):
        raise IdentityManifestError(f"{label} must contain the exact four helper roles")
    result: dict[str, str] = {}
    for role in EXPECTED_VIVADO_HELPER_ROLES:
        digest = value.get(role)
        if type(digest) is not str or SHA256_RE.fullmatch(digest) is None:
            raise IdentityManifestError(f"{label} has malformed SHA256 for role={role}")
        result[role] = digest
    return result


def _validate_identity_record(value: Any, label: str) -> dict[str, Any]:
    if type(value) is not dict or set(value) != _RECORD_KEYS:
        raise IdentityManifestError(f"{label} identity record keys are not exact")
    if type(value["path"]) is not str or not Path(value["path"]).is_absolute():
        raise IdentityManifestError(f"{label} path must be absolute")
    if type(value["sha256"]) is not str or SHA256_RE.fullmatch(value["sha256"]) is None:
        raise IdentityManifestError(f"{label} SHA256 is malformed")
    if type(value["bytes"]) is not int or isinstance(value["bytes"], bool) or value["bytes"] <= 0:
        raise IdentityManifestError(f"{label} byte length is malformed")
    for key in (
        "file_version",
        "product_version",
        "company_name",
        "signature_status",
        "signature_type",
        "signer_subject",
        "signer_thumbprint",
    ):
        if type(value[key]) is not str:
            raise IdentityManifestError(f"{label} {key} must be a string")
    if value["signature_status"] != "Valid":
        raise IdentityManifestError(f"{label} signature status must be Valid")
    if value["signature_type"] not in {"Authenticode", "Catalog"}:
        raise IdentityManifestError(f"{label} signature type is unsupported")
    if not value["signer_subject"] or THUMBPRINT_RE.fullmatch(value["signer_thumbprint"]) is None:
        raise IdentityManifestError(f"{label} signer identity is malformed")
    return dict(value)


def _load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.is_file() or MANIFEST_PATH.is_symlink():
        raise IdentityManifestError(f"helper identity manifest is missing/non-regular: {MANIFEST_PATH}")
    actual_sha = sha256_file(MANIFEST_PATH)
    if actual_sha != EXPECTED_MANIFEST_SHA256:
        raise IdentityManifestError(
            "helper identity manifest SHA256 mismatch: "
            f"expected={EXPECTED_MANIFEST_SHA256} actual={actual_sha}"
        )
    payload = _load_json_object(MANIFEST_PATH)
    if set(payload) != {
        "schema",
        "manifest_id",
        "current_runtime_profile_id",
        "identity_probe",
        "probe_host",
        "profiles",
    }:
        raise IdentityManifestError("helper identity manifest top-level keys are not exact")
    if payload.get("schema") != MANIFEST_SCHEMA:
        raise IdentityManifestError(f"helper identity manifest schema must be {MANIFEST_SCHEMA}")
    if type(payload.get("manifest_id")) is not str or not payload["manifest_id"]:
        raise IdentityManifestError("helper identity manifest ID is malformed")

    probe = payload.get("identity_probe")
    if type(probe) is not dict or set(probe) != {"path", "sha256"}:
        raise IdentityManifestError("identity probe binding is malformed")
    probe_path = (ROOT / str(probe.get("path", ""))).resolve(strict=False)
    try:
        probe_path.relative_to(ROOT)
    except ValueError as exc:
        raise IdentityManifestError("identity probe escapes repository root") from exc
    if (
        not probe_path.is_file()
        or probe_path.is_symlink()
        or type(probe.get("sha256")) is not str
        or SHA256_RE.fullmatch(probe["sha256"]) is None
        or sha256_file(probe_path) != probe["sha256"]
    ):
        raise IdentityManifestError("identity probe path/SHA256 binding failed")

    probe_host = _validate_identity_record(payload.get("probe_host"), "probe_host")
    profiles = payload.get("profiles")
    if type(profiles) is not dict or not profiles:
        raise IdentityManifestError("helper identity profiles are missing")
    current_id = payload.get("current_runtime_profile_id")
    if type(current_id) is not str or current_id not in profiles:
        raise IdentityManifestError("current runtime helper profile ID is missing")
    runtime_ids: list[str] = []
    normalized_profiles: dict[str, dict[str, Any]] = {}
    for profile_id, profile in profiles.items():
        if type(profile_id) is not str or not profile_id or type(profile) is not dict:
            raise IdentityManifestError("helper profile ID/record is malformed")
        runtime_eligible = profile.get("runtime_eligible")
        purpose = profile.get("purpose")
        if type(runtime_eligible) is not bool or type(purpose) is not str or not purpose:
            raise IdentityManifestError(f"helper profile metadata is malformed: {profile_id}")
        if runtime_eligible:
            if set(profile) != {"runtime_eligible", "purpose", "records"}:
                raise IdentityManifestError(f"runtime helper profile keys are not exact: {profile_id}")
            records = profile.get("records")
            if type(records) is not dict or set(records) != set(EXPECTED_VIVADO_HELPER_ROLES):
                raise IdentityManifestError(f"runtime helper records are incomplete: {profile_id}")
            normalized_records = {
                role: _validate_identity_record(records[role], f"{profile_id}:{role}")
                for role in EXPECTED_VIVADO_HELPER_ROLES
            }
            normalized_profiles[profile_id] = {
                "runtime_eligible": True,
                "purpose": purpose,
                "records": normalized_records,
                "sha256_by_role": {
                    role: normalized_records[role]["sha256"]
                    for role in EXPECTED_VIVADO_HELPER_ROLES
                },
            }
            runtime_ids.append(profile_id)
        else:
            if set(profile) != {"runtime_eligible", "purpose", "sha256_by_role"}:
                raise IdentityManifestError(f"historical helper profile keys are not exact: {profile_id}")
            normalized_profiles[profile_id] = {
                "runtime_eligible": False,
                "purpose": purpose,
                "sha256_by_role": _validate_hash_map(
                    profile.get("sha256_by_role"), f"{profile_id}:sha256_by_role"
                ),
            }
    if runtime_ids != [current_id]:
        raise IdentityManifestError("exactly the current profile must be runtime eligible")
    return {
        **payload,
        "manifest_path": str(MANIFEST_PATH),
        "manifest_sha256": actual_sha,
        "probe_path": str(probe_path),
        "probe_host": probe_host,
        "profiles": normalized_profiles,
    }


_MANIFEST = _load_manifest()
CURRENT_VIVADO_HELPER_HASH_PROFILE_ID = str(_MANIFEST["current_runtime_profile_id"])
APPROVED_VIVADO_HELPER_SHA256_PROFILES = {
    profile_id: dict(profile["sha256_by_role"])
    for profile_id, profile in _MANIFEST["profiles"].items()
}
EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE = dict(
    APPROVED_VIVADO_HELPER_SHA256_PROFILES[CURRENT_VIVADO_HELPER_HASH_PROFILE_ID]
)
EXPECTED_VIVADO_HELPER_PATHS_BY_ROLE = {
    role: str(
        _MANIFEST["profiles"][CURRENT_VIVADO_HELPER_HASH_PROFILE_ID]["records"][role][
            "path"
        ]
    )
    for role in EXPECTED_VIVADO_HELPER_ROLES
}


def approved_vivado_helper_hash_profile_id(value: Any) -> str | None:
    """Return an exact complete historical/runtime profile ID; never mix roles."""

    if type(value) is not dict or set(value) != set(EXPECTED_VIVADO_HELPER_ROLES):
        return None
    if any(type(value[role]) is not str or SHA256_RE.fullmatch(value[role]) is None for role in EXPECTED_VIVADO_HELPER_ROLES):
        return None
    for profile_id, expected in APPROVED_VIVADO_HELPER_SHA256_PROFILES.items():
        if value == expected:
            return profile_id
    return None


def _windows_key(path: str | Path) -> str:
    return str(Path(path).resolve(strict=False)).replace("/", "\\").casefold()


def _system_directory() -> Path:
    if os.name != "nt":
        return Path(r"C:\WINDOWS\System32")
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetSystemDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetSystemDirectoryW.restype = wintypes.UINT
    buffer = ctypes.create_unicode_buffer(32768)
    length = int(kernel32.GetSystemDirectoryW(buffer, len(buffer)))
    if length < 1 or length >= len(buffer):
        raise OSError(ctypes.get_last_error(), "GetSystemDirectoryW failed")
    return Path(buffer.value).resolve(strict=False)


def derive_helper_paths(vivado_path: str | Path) -> dict[str, str]:
    launcher = Path(vivado_path).resolve(strict=False)
    helper_dir = launcher.parent / "unwrapped" / "win64.o"
    system32 = _system_directory()
    return {
        "cs_server": str((helper_dir / "cs_server.exe").resolve(strict=False)),
        "rdi_xsdb": str((helper_dir / "rdi_xsdb.exe").resolve(strict=False)),
        "cmd": str((system32 / "cmd.exe").resolve(strict=False)),
        "conhost": str((system32 / "conhost.exe").resolve(strict=False)),
    }


def _hash_records(paths: Mapping[str, str]) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    records: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    if set(paths) != set(EXPECTED_VIVADO_HELPER_ROLES):
        return {}, [{"error_code": "HELPER_PATH_ROLE_SET_MISMATCH", "detail": "helper path role set is not exact"}]
    for role in EXPECTED_VIVADO_HELPER_ROLES:
        path = Path(paths[role])
        try:
            if not path.is_file() or path.is_symlink():
                raise OSError("path is missing, non-file, or symlink")
            records[role] = {
                "path": str(path.resolve(strict=False)),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        except OSError as exc:
            errors.append(
                {
                    "error_code": "HELPER_FILE_READ_FAILED",
                    "detail": f"role={role} path={path} {type(exc).__name__}: {exc}",
                }
            )
    return records, errors


def verify_runtime_helper_hashes_by_paths(
    paths: Mapping[str, str] | Sequence[str],
) -> tuple[bool, dict[str, str], str, str | None]:
    """Re-hash exact helper paths and require the sole runtime-eligible profile."""

    if not isinstance(paths, Mapping):
        if len(paths) != len(EXPECTED_VIVADO_HELPER_ROLES):
            return False, {}, "approved helper path contract is malformed", None
        path_map = dict(zip(EXPECTED_VIVADO_HELPER_ROLES, paths))
    else:
        path_map = dict(paths)
    records, errors = _hash_records(path_map)
    hashes = {role: record["sha256"] for role, record in records.items()}
    if errors:
        return False, hashes, errors[0]["detail"], None
    profile_id = approved_vivado_helper_hash_profile_id(hashes)
    if profile_id != CURRENT_VIVADO_HELPER_HASH_PROFILE_ID:
        return (
            False,
            hashes,
            "complete Vivado helper hash map does not match the exact runtime-eligible profile",
            profile_id,
        )
    current_records = _MANIFEST["profiles"][CURRENT_VIVADO_HELPER_HASH_PROFILE_ID]["records"]
    for role in EXPECTED_VIVADO_HELPER_ROLES:
        if _windows_key(records[role]["path"]) != _windows_key(current_records[role]["path"]):
            return False, hashes, f"runtime helper absolute path mismatch: role={role}", profile_id
        if records[role]["bytes"] != current_records[role]["bytes"]:
            return False, hashes, f"runtime helper byte length mismatch: role={role}", profile_id
    return True, hashes, "", profile_id


def _probe_environment(system32: Path, probe_host: Path) -> dict[str, str]:
    windows_root = system32.parent
    temp = Path(os.environ.get("TEMP", str(windows_root / "Temp"))).resolve(strict=False)
    env = {
        "SystemRoot": str(windows_root),
        "WINDIR": str(windows_root),
        "COMSPEC": str((system32 / "cmd.exe").resolve(strict=False)),
        "PATH": os.pathsep.join((str(system32), str(probe_host.parent))),
        "TEMP": str(temp),
        "TMP": str(temp),
    }
    # FileVersionInfo resolution for serviced Windows system files depends on
    # the process architecture/profile folders.  Copy only this fixed,
    # non-authorization whitelist; arbitrary caller variables and all RF_COMM
    # authorization state are deliberately excluded.
    for key in (
        "ALLUSERSPROFILE",
        "APPDATA",
        "CommonProgramFiles",
        "CommonProgramFiles(x86)",
        "CommonProgramW6432",
        "HOMEDRIVE",
        "HOMEPATH",
        "LOCALAPPDATA",
        "NUMBER_OF_PROCESSORS",
        "OS",
        "PROCESSOR_ARCHITECTURE",
        "PROCESSOR_IDENTIFIER",
        "PROCESSOR_LEVEL",
        "PROCESSOR_REVISION",
        "ProgramData",
        "ProgramFiles",
        "ProgramFiles(x86)",
        "ProgramW6432",
        "PSModulePath",
        "PUBLIC",
        "SystemDrive",
        "USERDOMAIN",
        "USERNAME",
        "USERPROFILE",
    ):
        value = os.environ.get(key)
        if value is not None:
            env[key] = value
    return env


def _run_probe(argv: list[str], env: Mapping[str, str]) -> subprocess.CompletedProcess[str]:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    return subprocess.run(
        argv,
        cwd=ROOT,
        env=dict(env),
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        timeout=30,
        check=False,
        creationflags=creationflags,
    )


def validate_vivado_helper_identity(
    vivado_path: str | Path,
    *,
    probe_runner: Callable[[list[str], Mapping[str, str]], subprocess.CompletedProcess[str]] | None = None,
) -> dict[str, Any]:
    """Validate complete helper identity without opening or mutating hardware."""

    result: dict[str, Any] = {
        "schema": VALIDATION_SCHEMA,
        "phase": "VIVADO_HELPER_IDENTITY",
        "status": "FAIL",
        "error_code": "UNSET",
        "hardware_actions_executed": False,
        "hardware_connection_attempted": False,
        "tfdu_touched": False,
        "ethernet_transport_used": False,
        "motion_used": False,
        "campaign_lock_created": False,
        "campaign_attempt_created": False,
        "manifest": {
            "path": str(MANIFEST_PATH),
            "sha256": EXPECTED_MANIFEST_SHA256,
            "manifest_id": _MANIFEST["manifest_id"],
        },
        "runtime_profile_id": CURRENT_VIVADO_HELPER_HASH_PROFILE_ID,
        "errors": [],
    }

    def fail(code: str, detail: str) -> None:
        result["errors"].append({"error_code": code, "detail": detail})
        if result["error_code"] == "UNSET":
            result["error_code"] = code

    launcher = Path(vivado_path).resolve(strict=False)
    result["vivado_launcher"] = str(launcher)
    if launcher.name.casefold() != "vivado.bat" or launcher.parent.name.casefold() != "bin":
        fail("VIVADO_LAUNCHER_PATH_MISMATCH", "Vivado launcher must be the exact bin/vivado.bat path shape")
    try:
        helper_paths = derive_helper_paths(launcher)
    except OSError as exc:
        fail("SYSTEM_DIRECTORY_QUERY_FAILED", f"{type(exc).__name__}: {exc}")
        helper_paths = {}
    result["derived_helper_paths"] = helper_paths
    if helper_paths:
        hashed, hash_errors = _hash_records(helper_paths)
        result["observed_file_records"] = hashed
        for item in hash_errors:
            fail(item["error_code"], item["detail"])
        hashes = {role: record["sha256"] for role, record in hashed.items()}
        result["observed_sha256_by_role"] = hashes
        profile_id = approved_vivado_helper_hash_profile_id(hashes)
        result["observed_complete_hash_profile_id"] = profile_id
        if profile_id != CURRENT_VIVADO_HELPER_HASH_PROFILE_ID:
            fail(
                "VIVADO_HELPER_RUNTIME_HASH_PROFILE_MISMATCH",
                "helper hashes do not match the sole runtime-eligible complete profile",
            )
        expected_records = _MANIFEST["profiles"][CURRENT_VIVADO_HELPER_HASH_PROFILE_ID]["records"]
        for role in EXPECTED_VIVADO_HELPER_ROLES:
            if role not in hashed:
                continue
            if _windows_key(hashed[role]["path"]) != _windows_key(expected_records[role]["path"]):
                fail("VIVADO_HELPER_ABSOLUTE_PATH_MISMATCH", f"role={role}")
            if hashed[role]["bytes"] != expected_records[role]["bytes"]:
                fail("VIVADO_HELPER_BYTE_LENGTH_MISMATCH", f"role={role}")

    probe_path = Path(_MANIFEST["probe_path"])
    probe_host_expected = _MANIFEST["probe_host"]
    probe_host = Path(probe_host_expected["path"]).resolve(strict=False)
    result["identity_probe"] = {
        "path": str(probe_path),
        "sha256": sha256_file(probe_path),
    }
    result["probe_host_file_record"] = {
        "path": str(probe_host),
        "sha256": None,
        "bytes": None,
    }
    try:
        if not probe_host.is_file() or probe_host.is_symlink():
            raise OSError("probe host is missing, non-file, or symlink")
        result["probe_host_file_record"]["sha256"] = sha256_file(probe_host)
        result["probe_host_file_record"]["bytes"] = probe_host.stat().st_size
    except OSError as exc:
        fail("PROBE_HOST_READ_FAILED", f"{type(exc).__name__}: {exc}")
    else:
        if result["probe_host_file_record"]["sha256"] != probe_host_expected["sha256"]:
            fail("PROBE_HOST_SHA256_MISMATCH", "fixed PowerShell probe host SHA256 changed")
        if result["probe_host_file_record"]["bytes"] != probe_host_expected["bytes"]:
            fail("PROBE_HOST_BYTE_LENGTH_MISMATCH", "fixed PowerShell probe host byte length changed")

    if helper_paths and not result["errors"]:
        system32 = Path(helper_paths["cmd"]).parent
        env = _probe_environment(system32, probe_host)
        argv = [
            str(probe_host),
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(probe_path),
            "-CsServer",
            helper_paths["cs_server"],
            "-RdiXsdb",
            helper_paths["rdi_xsdb"],
            "-Cmd",
            helper_paths["cmd"],
            "-Conhost",
            helper_paths["conhost"],
        ]
        result["probe_exact_argv"] = argv
        result["probe_environment"] = env
        runner = probe_runner or _run_probe
        try:
            completed = runner(argv, env)
        except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
            fail("IDENTITY_PROBE_LAUNCH_FAILED", f"{type(exc).__name__}: {exc}")
        else:
            result["probe_returncode"] = int(completed.returncode)
            result["probe_stderr"] = completed.stderr
            if completed.returncode != 0:
                fail("IDENTITY_PROBE_NONZERO", f"returncode={completed.returncode}")
            elif completed.stderr:
                fail("IDENTITY_PROBE_STDERR_NONEMPTY", completed.stderr)
            else:
                try:
                    probe_payload = json.loads(completed.stdout)
                except (json.JSONDecodeError, TypeError) as exc:
                    fail("IDENTITY_PROBE_JSON_INVALID", f"{type(exc).__name__}: {exc}")
                else:
                    result["probe_payload"] = probe_payload
                    if type(probe_payload) is not dict or set(probe_payload) != {
                        "schema",
                        "probe_host",
                        "records",
                    }:
                        fail("IDENTITY_PROBE_SCHEMA_INVALID", "probe top-level keys are not exact")
                    elif probe_payload.get("schema") != PROBE_SCHEMA:
                        fail("IDENTITY_PROBE_SCHEMA_INVALID", "probe schema marker mismatch")
                    else:
                        observed_records = probe_payload.get("records")
                        if type(observed_records) is not list or len(observed_records) != 4:
                            fail("IDENTITY_PROBE_RECORD_SET_INVALID", "probe must return exactly four records")
                        else:
                            by_role: dict[str, dict[str, Any]] = {}
                            for record in observed_records:
                                if type(record) is not dict or set(record) != _PROBE_RECORD_KEYS:
                                    fail("IDENTITY_PROBE_RECORD_INVALID", "probe record keys are not exact")
                                    continue
                                role = record.get("role")
                                if role not in EXPECTED_VIVADO_HELPER_ROLES or role in by_role:
                                    fail("IDENTITY_PROBE_RECORD_INVALID", f"probe role is unknown/duplicate: {role}")
                                    continue
                                by_role[str(role)] = record
                            expected_records = _MANIFEST["profiles"][CURRENT_VIVADO_HELPER_HASH_PROFILE_ID]["records"]
                            for role in EXPECTED_VIVADO_HELPER_ROLES:
                                if role not in by_role:
                                    fail("IDENTITY_PROBE_RECORD_MISSING", f"role={role}")
                                    continue
                                expected_metadata = {
                                    key: expected_records[role][key]
                                    for key in _RECORD_KEYS
                                    if key not in {"sha256", "path"}
                                }
                                observed_metadata = {
                                    key: by_role[role][key]
                                    for key in _PROBE_RECORD_KEYS
                                    if key not in {"role", "path"}
                                }
                                if (
                                    _windows_key(by_role[role]["path"])
                                    != _windows_key(expected_records[role]["path"])
                                    or observed_metadata != expected_metadata
                                ):
                                    fail("VIVADO_HELPER_METADATA_MISMATCH", f"role={role}")
                        host_record = probe_payload.get("probe_host")
                        if type(host_record) is not dict or set(host_record) != _PROBE_RECORD_KEYS:
                            fail("PROBE_HOST_METADATA_INVALID", "probe host metadata keys are not exact")
                        else:
                            expected_host_metadata = {
                                key: probe_host_expected[key]
                                for key in _RECORD_KEYS
                                if key not in {"sha256", "path"}
                            }
                            observed_host_metadata = {
                                key: host_record[key]
                                for key in _PROBE_RECORD_KEYS
                                if key not in {"role", "path"}
                            }
                            if (
                                host_record.get("role") != "probe_host"
                                or _windows_key(host_record["path"])
                                != _windows_key(probe_host_expected["path"])
                                or observed_host_metadata != expected_host_metadata
                            ):
                                fail("PROBE_HOST_METADATA_MISMATCH", "PowerShell probe host identity changed")

    if not result["errors"]:
        result["status"] = "PASS"
        result["error_code"] = "NONE"
    return result


def validate_identity_validation_report(value: Any) -> list[str]:
    """Revalidate a persisted PASS report without launching the metadata probe."""

    errors: list[str] = []
    if type(value) is not dict:
        return ["Vivado helper identity validation report is missing/not an object"]
    expected_scalars = {
        "schema": VALIDATION_SCHEMA,
        "phase": "VIVADO_HELPER_IDENTITY",
        "status": "PASS",
        "error_code": "NONE",
        "hardware_actions_executed": False,
        "hardware_connection_attempted": False,
        "tfdu_touched": False,
        "ethernet_transport_used": False,
        "motion_used": False,
        "campaign_lock_created": False,
        "campaign_attempt_created": False,
        "runtime_profile_id": CURRENT_VIVADO_HELPER_HASH_PROFILE_ID,
        "observed_complete_hash_profile_id": CURRENT_VIVADO_HELPER_HASH_PROFILE_ID,
        "probe_returncode": 0,
        "probe_stderr": "",
    }
    for key, expected in expected_scalars.items():
        if value.get(key) != expected:
            errors.append(f"Vivado helper identity report field mismatch: {key}")
    if value.get("errors") != []:
        errors.append("Vivado helper identity PASS report contains errors")

    manifest = value.get("manifest")
    manifest_path = Path(str(manifest.get("path", ""))) if type(manifest) is dict else Path()
    if (
        type(manifest) is not dict
        or set(manifest) != {"path", "sha256", "manifest_id"}
        or not manifest_path.is_absolute()
        or tuple(part.casefold() for part in manifest_path.parts[-2:])
        != ("config", "p7_vivado_helper_identity_profiles.json")
        or manifest.get("sha256") != EXPECTED_MANIFEST_SHA256
        or manifest.get("manifest_id") != _MANIFEST["manifest_id"]
    ):
        errors.append("Vivado helper identity manifest binding mismatch")
    expected_records = _MANIFEST["profiles"][CURRENT_VIVADO_HELPER_HASH_PROFILE_ID][
        "records"
    ]
    observed_hashes = value.get("observed_sha256_by_role")
    if observed_hashes != EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE:
        errors.append("Vivado helper identity observed SHA256 profile mismatch")
    file_records = value.get("observed_file_records")
    if type(file_records) is not dict or set(file_records) != set(
        EXPECTED_VIVADO_HELPER_ROLES
    ):
        errors.append("Vivado helper identity observed file records are incomplete")
    else:
        for role in EXPECTED_VIVADO_HELPER_ROLES:
            record = file_records[role]
            if type(record) is not dict or set(record) != {"path", "sha256", "bytes"}:
                errors.append(f"Vivado helper identity file record is malformed: role={role}")
                continue
            if (
                _windows_key(record["path"]) != _windows_key(expected_records[role]["path"])
                or record["sha256"] != expected_records[role]["sha256"]
                or record["bytes"] != expected_records[role]["bytes"]
            ):
                errors.append(f"Vivado helper identity file record mismatch: role={role}")

    probe = value.get("identity_probe")
    probe_path = Path(str(probe.get("path", ""))) if type(probe) is dict else Path()
    if (
        type(probe) is not dict
        or set(probe) != {"path", "sha256"}
        or not probe_path.is_absolute()
        or tuple(part.casefold() for part in probe_path.parts[-3:])
        != ("scripts", "hw", "p7_helper_identity_probe.ps1")
        or probe.get("sha256") != _MANIFEST["identity_probe"]["sha256"]
    ):
        errors.append("Vivado helper identity probe binding mismatch")
    host_file = value.get("probe_host_file_record")
    expected_host = _MANIFEST["probe_host"]
    if type(host_file) is not dict or set(host_file) != {"path", "sha256", "bytes"}:
        errors.append("Vivado helper identity probe-host file record is malformed")
    elif (
        _windows_key(host_file["path"]) != _windows_key(expected_host["path"])
        or host_file["sha256"] != expected_host["sha256"]
        or host_file["bytes"] != expected_host["bytes"]
    ):
        errors.append("Vivado helper identity probe-host file record mismatch")

    payload = value.get("probe_payload")
    if type(payload) is not dict or set(payload) != {"schema", "probe_host", "records"}:
        errors.append("Vivado helper identity probe payload is malformed")
    elif payload.get("schema") != PROBE_SCHEMA:
        errors.append("Vivado helper identity probe payload schema mismatch")
    else:
        records = payload.get("records")
        if type(records) is not list or len(records) != len(EXPECTED_VIVADO_HELPER_ROLES):
            errors.append("Vivado helper identity probe payload record set is incomplete")
        else:
            by_role = {
                item.get("role"): item
                for item in records
                if type(item) is dict and item.get("role") in EXPECTED_VIVADO_HELPER_ROLES
            }
            if set(by_role) != set(EXPECTED_VIVADO_HELPER_ROLES):
                errors.append("Vivado helper identity probe payload roles are incomplete/duplicate")
            else:
                for role in EXPECTED_VIVADO_HELPER_ROLES:
                    item = by_role[role]
                    if set(item) != _PROBE_RECORD_KEYS:
                        errors.append(f"Vivado helper identity probe record keys mismatch: role={role}")
                        continue
                    expected_metadata = {
                        key: expected_records[role][key]
                        for key in _RECORD_KEYS
                        if key not in {"sha256", "path"}
                    }
                    observed_metadata = {
                        key: item[key]
                        for key in _PROBE_RECORD_KEYS
                        if key not in {"role", "path"}
                    }
                    if (
                        _windows_key(item["path"])
                        != _windows_key(expected_records[role]["path"])
                        or observed_metadata != expected_metadata
                    ):
                        errors.append(f"Vivado helper identity probe metadata mismatch: role={role}")
        host = payload.get("probe_host")
        if type(host) is not dict or set(host) != _PROBE_RECORD_KEYS:
            errors.append("Vivado helper identity probe-host metadata is malformed")
        else:
            expected_metadata = {
                key: expected_host[key]
                for key in _RECORD_KEYS
                if key not in {"sha256", "path"}
            }
            observed_metadata = {
                key: host[key]
                for key in _PROBE_RECORD_KEYS
                if key not in {"role", "path"}
            }
            if (
                host.get("role") != "probe_host"
                or _windows_key(host["path"]) != _windows_key(expected_host["path"])
                or observed_metadata != expected_metadata
            ):
                errors.append("Vivado helper identity probe-host metadata mismatch")
    return errors


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Validate source-bound P7 Vivado helper identities without hardware.")
    parser.add_argument("--vivado-path", required=True)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    report = validate_vivado_helper_identity(args.vivado_path)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json_summary else f"P7_VIVADO_HELPER_IDENTITY={report['status']}")
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
