#!/usr/bin/env python3
"""Read-only verification of the frozen P10-family closeout baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

P10_5_SOURCE = "e1f8c01ab084571627380367422f0bda2c0aed87"
P10_5_EVIDENCE = "6546a9bd749f0daae6696ac22d18007937210722"
P10_5_FINAL = "0a79ee8be21a199e7ba14bd65fcd72638f7160e0"
P10_5_PASS_TAG = "p10.5-2plus2-dual-direction-pass"
P10_5_PASS_OBJECT = "a0fe8b02a638fc5a8fc21d80488a7c8c294b7a68"
P10_5_AUDIT = Path("evidence/generated/p10_5_20260830_run4_final_audit.json")
P10_5_AUDIT_SHA = "e74f02e886b3b9e8b34a59aa8048dd7ac464c3e270020f42093e5a33ba8638d8"
P10_5_FREEZE = Path("evidence/generated/p10_5_artifact_freeze.json")
P10_5_FREEZE_SHA = "1c15558675db7135543351f3f5b5be0f95cae1ab5b8c4d2e9de645a3bd5a534b"
P10_5_FINAL_SUMMARY = Path("evidence/generated/p10_5_final_summary.json")
P10_5_FINAL_SUMMARY_SHA = "b267fcd3a9a8a8a7d562285f32eae1623d81221fcf2eae6c85030d9350156a99"
P10_5_SHUTDOWN = Path("evidence/generated/p10_5_shutdown.json")
P10_5_SHUTDOWN_SHA = "1cecac6f96f865680f5e51a71ecf6d2f83ef0aba84839564b28bd4f2d0d15449"
P10_5_CONSISTENCY = Path("evidence/generated/p10_5_evidence_consistency.json")
P10_5_CONSISTENCY_SHA = "12d95466a8577c32aed93dfc91f7bce4fe54c9b4991c498632c3f816e85dfe60"
P10_5_AUTH = Path("config/p10_5_current_run_hardware_authorization.json")
P10_5_AUTH_SHA = "d239cd3dd57812824a56d846f302b28fe143d03d46cc2e2ea94eb5f5df18d2dd"

P10_4_PASS_TAG = "p10.4-autonomous-4lane-hardening-pass"
P10_4_PASS_OBJECT = "2e050f943a80ccae38790771da8e298d11fe7c79"
P10_4_PASS_TARGET = "7987e6385b65fa2c7ed7d3a008c1ecbdf323ffa8"
P10_4_CLOSED_TAG = "p10.4-autonomous-4lane-hardening-closed"
P10_4_CLOSED_OBJECT = "e9afcc66ffe549c30e9642cca4a66f95a27f793a"
P10_4_CLOSED_TARGET = "bcbe5b51469ac499fb0a17a89cb9f5a4bbda6676"
P10_4_ARCHIVE = Path(os.environ.get(
    "P10_4_WORKTREE_ARCHIVE",
    r"D:\codex备份\RF_COMM_SPACE_CLEANUP_ARCHIVE_20260831\worktree_data\RF_COMM_MULTILANE_P10_4.tar.zst",
))
P10_4_ARCHIVE_SHA = "4fdb7b1db433e213bd0ab5bd49e07df3f9d87517f933406b0f29ae5e7c57f42c"
P10_4_ARCHIVE_BYTES = 1060861145
P10_4_ARCHIVE_PREFIX = PurePosixPath("RF_COMM_MULTILANE_P10_4")
P10_4_ARCHIVE_VALIDATION = Path(
    r"D:\codex备份\RF_COMM_SPACE_CLEANUP_ARCHIVE_20260831\manifests\RF_COMM_MULTILANE_P10_4.validation.json"
)
P10_4_ARCHIVE_VALIDATION_SHA = "90d82df47d7d847697d7e520761af4350a00ef2ec9461b7cfcc7f053b72616fc"
P10_4_ARCHIVE_FILE_MANIFEST = Path(
    r"D:\codex备份\RF_COMM_SPACE_CLEANUP_ARCHIVE_20260831\manifests\RF_COMM_MULTILANE_P10_4.files.csv"
)
P10_4_ARCHIVE_FILE_MANIFEST_SHA = "8adfe5873436b32d5637fab6f42747f29bafafa10bbcd17dbc235e83586d56df"

BASELINE_COMMANDS = {
    "P10": [sys.executable, "scripts/verify_p10_frozen_existing.py"],
    "P10_3": [sys.executable, "scripts/verify_p10_3_existing.py"],
    "P10_2": [sys.executable, "scripts/verify_p10_2_existing.py"],
    "P10_1R": [sys.executable, "scripts/verify_p10_1r_existing.py"],
    "P8C": [sys.executable, "scripts/verify_p8c_existing.py"],
}


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not a mapping: {path}")
    return value


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def verify_tag(
    name: str, expected_object: str, expected_target: str, errors: list[str]
) -> dict[str, str]:
    try:
        object_type = git("cat-file", "-t", name)
        tag_object = git("rev-parse", name)
        target = git("rev-list", "-n", "1", name)
    except subprocess.SubprocessError as exc:
        errors.append(f"tag lookup failed for {name}: {exc}")
        return {"name": name, "type": "MISSING", "object": "", "target": ""}
    require(object_type == "tag", f"{name} is not annotated", errors)
    require(tag_object == expected_object, f"{name} object changed", errors)
    require(target == expected_target, f"{name} target changed", errors)
    return {"name": name, "type": object_type, "object": tag_object, "target": target}


def is_ancestor(older: str, newer: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def verify_record(
    record: dict[str, Any], label: str, errors: list[str]
) -> dict[str, Any]:
    path = ROOT / str(record.get("path", ""))
    require(path.is_file(), f"missing {label}: {path}", errors)
    if not path.is_file():
        return {"path": str(path), "status": "MISSING"}
    actual_sha = sha256(path)
    actual_bytes = path.stat().st_size
    require(actual_sha == record.get("sha256"), f"SHA256 mismatch: {label}", errors)
    if "bytes" in record:
        require(actual_bytes == record.get("bytes"), f"byte mismatch: {label}", errors)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": actual_sha,
        "bytes": actual_bytes,
        "status": "PASS",
    }


def verify_run_manifest(path: Path, errors: list[str]) -> dict[str, Any]:
    manifest = load_json(path)
    run_root = path.parent.parent
    files = manifest.get("files", [])
    require(isinstance(files, list), f"manifest files is not a list: {path}", errors)
    if not isinstance(files, list):
        files = []
    failures: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            failures.append("<malformed record>")
            continue
        item_path = Path(str(item.get("path", "")))
        candidate = (
            ROOT / item_path
            if item_path.parts and item_path.parts[0] == "evidence"
            else run_root / item_path
        )
        try:
            valid = (
                candidate.is_file()
                and candidate.stat().st_size == item.get("bytes")
                and sha256(candidate) == item.get("sha256")
            )
        except OSError:
            valid = False
        if not valid:
            failures.append(str(item.get("path", "<missing path>")))
    require(manifest.get("file_count") == len(files), f"manifest count mismatch: {path}", errors)
    require(not failures, f"manifest verification failures: {path}: {failures[:5]}", errors)
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "declared_files": manifest.get("file_count"),
        "verified_files": len(files) - len(failures),
        "failures": failures[:20],
    }


def verify_p10_4_run_manifests(
    paths: list[Path], errors: list[str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Verify P10.4 manifests, using the byte-exact retired-worktree archive.

    The historical runner wrote ``*.log`` files covered by its immutable SHA256
    manifests, but the repository-wide ``*.log`` ignore rule kept those files out
    of Git.  The retired P10.4 worktree was independently archived and validated
    before deletion.  This function never restores files into the repository: it
    extracts only missing manifest members into a temporary directory and hashes
    them there.
    """

    internal: list[dict[str, Any]] = []
    missing: list[tuple[int, dict[str, Any], PurePosixPath]] = []
    for manifest_index, path in enumerate(paths):
        manifest = load_json(path)
        files = manifest.get("files", [])
        require(isinstance(files, list), f"manifest files is not a list: {path}", errors)
        if not isinstance(files, list):
            files = []
        require(manifest.get("file_count") == len(files),
                f"manifest count mismatch: {path}", errors)
        local_verified = 0
        invalid_local: list[str] = []
        for item in files:
            if not isinstance(item, dict):
                invalid_local.append("<malformed record>")
                continue
            pure = PurePosixPath(str(item.get("path", "")))
            if pure.is_absolute() or ".." in pure.parts or not pure.parts:
                invalid_local.append(str(item.get("path", "<unsafe path>")))
                continue
            candidate = ROOT.joinpath(*pure.parts)
            if not candidate.exists():
                missing.append((manifest_index, item, pure))
                continue
            try:
                valid = (
                    candidate.is_file()
                    and candidate.stat().st_size == item.get("bytes")
                    and sha256(candidate) == item.get("sha256")
                )
            except OSError:
                valid = False
            if valid:
                local_verified += 1
            else:
                invalid_local.append(str(item.get("path", "<invalid path>")))
        require(not invalid_local,
                f"P10.4 local manifest content mismatch: {path}: {invalid_local[:5]}",
                errors)
        internal.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": sha256(path),
            "declared_files": manifest.get("file_count"),
            "local_verified_files": local_verified,
            "archive_verified_files": 0,
            "invalid_local": invalid_local,
            "archive_failures": [],
        })

    archive_errors: list[str] = []
    archive_verified = 0
    archive_sha = ""
    validation_sha = ""
    file_manifest_sha = ""
    if missing:
        if not P10_4_ARCHIVE.is_file():
            archive_errors.append(f"missing archive: {P10_4_ARCHIVE}")
        else:
            archive_sha = sha256(P10_4_ARCHIVE)
            if archive_sha != P10_4_ARCHIVE_SHA:
                archive_errors.append("P10.4 retired-worktree archive SHA256 mismatch")
            if P10_4_ARCHIVE.stat().st_size != P10_4_ARCHIVE_BYTES:
                archive_errors.append("P10.4 retired-worktree archive byte count mismatch")

        validation: dict[str, Any] = {}
        if not P10_4_ARCHIVE_VALIDATION.is_file():
            archive_errors.append(
                f"missing archive validation: {P10_4_ARCHIVE_VALIDATION}"
            )
        else:
            validation_sha = sha256(P10_4_ARCHIVE_VALIDATION)
            if validation_sha != P10_4_ARCHIVE_VALIDATION_SHA:
                archive_errors.append("P10.4 archive validation SHA256 mismatch")
            validation = load_json(P10_4_ARCHIVE_VALIDATION)
            for field in (
                "full_extract_file_sha256_match",
                "full_extract_directory_set_match",
                "final_source_sha256_match",
            ):
                if validation.get(field) is not True:
                    archive_errors.append(f"P10.4 archive validation field is not true: {field}")
            if str(validation.get("archive_sha256", "")).lower() != P10_4_ARCHIVE_SHA:
                archive_errors.append("P10.4 archive validation binds a different archive")
            if validation.get("archive_bytes") != P10_4_ARCHIVE_BYTES:
                archive_errors.append("P10.4 archive validation byte count changed")

        if not P10_4_ARCHIVE_FILE_MANIFEST.is_file():
            archive_errors.append(
                f"missing archive file manifest: {P10_4_ARCHIVE_FILE_MANIFEST}"
            )
        else:
            file_manifest_sha = sha256(P10_4_ARCHIVE_FILE_MANIFEST)
            if file_manifest_sha != P10_4_ARCHIVE_FILE_MANIFEST_SHA:
                archive_errors.append("P10.4 archive file-manifest SHA256 mismatch")
            if validation and str(
                validation.get("source_file_manifest_sha256", "")
            ).lower() != P10_4_ARCHIVE_FILE_MANIFEST_SHA:
                archive_errors.append(
                    "P10.4 archive validation binds a different file manifest"
                )

        if not archive_errors:
            with tempfile.TemporaryDirectory(prefix="p10_4_archive_verify_") as temp_name:
                temp = Path(temp_name)
                member_list = temp / "members.txt"
                members = [P10_4_ARCHIVE_PREFIX / pure for _, _, pure in missing]
                member_list.write_text(
                    "\n".join(member.as_posix() for member in members) + "\n",
                    encoding="utf-8",
                    newline="\n",
                )
                extracted = subprocess.run(
                    [
                        "tar", "-x", "-f", str(P10_4_ARCHIVE),
                        "-C", str(temp), "-T", str(member_list),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                if extracted.returncode != 0:
                    archive_errors.append(
                        "P10.4 selective archive extraction failed: "
                        + extracted.stderr[-1000:]
                    )
                else:
                    for (manifest_index, item, pure), member in zip(missing, members):
                        target = temp.joinpath(*member.parts)
                        try:
                            valid = (
                                target.is_file()
                                and target.stat().st_size == item.get("bytes")
                                and sha256(target) == item.get("sha256")
                            )
                        except OSError:
                            valid = False
                        if valid:
                            internal[manifest_index]["archive_verified_files"] += 1
                            archive_verified += 1
                        else:
                            path_text = str(item.get("path", "<missing path>"))
                            internal[manifest_index]["archive_failures"].append(path_text)

    for result in internal:
        verified = result["local_verified_files"] + result["archive_verified_files"]
        result["verified_files"] = verified
        result["failures"] = (
            result.pop("invalid_local") + result.pop("archive_failures")
        )[:20]
        require(
            verified == result["declared_files"] and not result["failures"],
            f"P10.4 manifest is not fully verified: {result['path']} "
            f"({verified}/{result['declared_files']})",
            errors,
        )
    for message in archive_errors:
        errors.append(message)

    archive_status = (
        "PASS"
        if not archive_errors and archive_verified == len(missing)
        else "FAIL"
    )
    return internal, {
        "status": archive_status,
        "mode": "read_only_selective_temporary_extract",
        "archive_path": str(P10_4_ARCHIVE),
        "archive_sha256": archive_sha,
        "archive_bytes": P10_4_ARCHIVE_BYTES,
        "validation_path": str(P10_4_ARCHIVE_VALIDATION),
        "validation_sha256": validation_sha,
        "file_manifest_path": str(P10_4_ARCHIVE_FILE_MANIFEST),
        "file_manifest_sha256": file_manifest_sha,
        "requested_files": len(missing),
        "verified_files": archive_verified,
        "frozen_evidence_modified": False,
    }


def verify_p10_5(errors: list[str]) -> dict[str, Any]:
    pass_tag = verify_tag(
        P10_5_PASS_TAG, P10_5_PASS_OBJECT, P10_5_FINAL, errors
    )
    require(is_ancestor(P10_5_SOURCE, P10_5_EVIDENCE),
            "P10.5 source is not an ancestor of evidence checkpoint", errors)
    require(is_ancestor(P10_5_EVIDENCE, P10_5_FINAL),
            "P10.5 evidence is not an ancestor of final checkpoint", errors)
    require(is_ancestor(P10_5_FINAL, "HEAD"),
            "P10.5 final checkpoint is not an ancestor of HEAD", errors)

    immutable = (
        (P10_5_AUDIT, P10_5_AUDIT_SHA, "audit"),
        (P10_5_FREEZE, P10_5_FREEZE_SHA, "artifact freeze"),
        (P10_5_FINAL_SUMMARY, P10_5_FINAL_SUMMARY_SHA, "final summary"),
        (P10_5_SHUTDOWN, P10_5_SHUTDOWN_SHA, "shutdown"),
        (P10_5_CONSISTENCY, P10_5_CONSISTENCY_SHA, "evidence consistency"),
        (P10_5_AUTH, P10_5_AUTH_SHA, "authorization"),
    )
    for path, expected, label in immutable:
        require(path.is_file(), f"missing P10.5 {label}: {path}", errors)
        if path.is_file():
            require(sha256(ROOT / path) == expected,
                    f"P10.5 {label} hash changed", errors)

    audit = load_json(ROOT / P10_5_AUDIT)
    freeze = load_json(ROOT / P10_5_FREEZE)
    final = load_json(ROOT / P10_5_FINAL_SUMMARY)
    shutdown = load_json(ROOT / P10_5_SHUTDOWN)
    consistency = load_json(ROOT / P10_5_CONSISTENCY)
    authorization = load_json(ROOT / P10_5_AUTH)
    state = load_json(ROOT / "config/project_state.json")

    require(audit.get("status") == "PASS_WITH_NONBLOCKING_LIMITS",
            "P10.5 audit status changed", errors)
    require(audit.get("artifact_source_commit") == P10_5_SOURCE,
            "P10.5 audit source changed", errors)
    require(audit.get("mandatory_results", {}).get("all_14_hardware_stages") == "PASS",
            "P10.5 mandatory stage result is not PASS", errors)
    require(audit.get("performance", {}).get("f_to_r_4mbps_target") == "PASS" and
            audit.get("performance", {}).get("r_to_f_4mbps_target") == "PASS",
            "P10.5 mandatory 4 Mbit/s result changed", errors)
    require(audit.get("performance", {}).get("f_to_r_4p8mbps_stretch") ==
            "FAIL_NONBLOCKING" and
            audit.get("performance", {}).get("r_to_f_4p8mbps_stretch") ==
            "FAIL_NONBLOCKING", "P10.5 stretch classification changed", errors)
    require(audit.get("formal", {}).get("transport_timeout") == 0,
            "P10.5 formal transport timeout is not zero", errors)
    require(audit.get("scope_boundaries", {}).get("p11_status") == "NOT_STARTED",
            "P11 was promoted in P10.5 audit", errors)

    require(freeze.get("status") == "PASS" and freeze.get("acceptance_eligible") is True,
            "P10.5 artifact freeze is not acceptance-eligible PASS", errors)
    require(freeze.get("artifact_source_commit") == P10_5_SOURCE,
            "P10.5 artifact source changed", errors)
    artifact_records: list[dict[str, Any]] = []
    for item in freeze.get("artifacts", []):
        if not isinstance(item, dict):
            errors.append("malformed P10.5 artifact record")
            continue
        require(item.get("read_only") is True,
                f"P10.5 artifact is not read-only: {item.get('path')}", errors)
        artifact_records.append(verify_record(item, "P10.5 artifact", errors))

    offline_inputs = freeze.get("offline_inputs", {})
    wiring = verify_record(offline_inputs.get("actual_wiring", {}),
                           "P10.5 wiring", errors)
    module_inventory = verify_record(offline_inputs.get("module_inventory", {}),
                                     "P10.5 module inventory", errors)

    manifest_meta = audit.get("manifest_verification", {})
    manifest_path = ROOT / str(manifest_meta.get("path", ""))
    require(manifest_path.is_file(), "P10.5 evidence manifest is missing", errors)
    manifest_result = {
        "path": str(manifest_path), "declared_files": 0,
        "verified_files": 0, "failures": ["missing"], "sha256": "",
    }
    if manifest_path.is_file():
        require(sha256(manifest_path) == manifest_meta.get("sha256"),
                "P10.5 evidence manifest hash changed", errors)
        manifest_result = verify_run_manifest(manifest_path, errors)
        require(manifest_result["declared_files"] == 1107 and
                manifest_result["verified_files"] == 1107,
                "P10.5 evidence manifest is not 1107/1107", errors)

    require(final.get("status") == "PASS" and final.get("SHUTDOWN_FIXED") == "PASS" and
            final.get("SHUTDOWN_ROTATING") == "PASS",
            "P10.5 runner final/shutdown changed", errors)
    require(shutdown.get("status") == "PASS" and shutdown.get("SHUTDOWN_FIXED") == "PASS" and
            shutdown.get("SHUTDOWN_ROTATING") == "PASS",
            "P10.5 shutdown evidence changed", errors)
    require(consistency.get("status") == "PASS",
            "P10.5 evidence consistency changed", errors)
    require(authorization.get("consumed") is True and
            authorization.get("current_run_hardware_authorization") is False and
            authorization.get("authorized") is False,
            "P10.5 authorization is reusable or open", errors)

    campaign = state.get("p10_5_dual_direction", {})
    require(state.get("p10_5_status") == "PASS_WITH_NONBLOCKING_LIMITS" and
            campaign.get("status") == "PASS_WITH_NONBLOCKING_LIMITS",
            "P10.5 canonical state classification changed", errors)
    require(campaign.get("mandatory_hardware_gates") == "PASS",
            "P10.5 canonical mandatory result is not PASS", errors)
    require(state.get("current_run_hardware_authorization") is False and
            state.get("last_hardware_authorization_consumed") is True,
            "canonical current authorization is open", errors)
    require(state.get("last_hardware_stage") == "P10_5" and
            state.get("last_hardware_evidence_checkpoint") == P10_5_EVIDENCE,
            "canonical last-hardware identity changed", errors)
    require(state.get("last_shutdown_fixed") == "PASS" and
            state.get("last_shutdown_rotating") == "PASS",
            "canonical last shutdown changed", errors)
    require(state.get("p11_status") == "NOT_STARTED" and
            campaign.get("p11_status") == "NOT_STARTED",
            "P11 state changed", errors)

    return {
        "source_commit": P10_5_SOURCE,
        "evidence_checkpoint": P10_5_EVIDENCE,
        "final_checkpoint": P10_5_FINAL,
        "pass_tag": P10_5_PASS_TAG,
        "pass_tag_object": pass_tag["object"],
        "pass_tag_target": pass_tag["target"],
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "mandatory_result": "PASS",
        "formal_run_id": audit.get("run_id"),
        "board_binding": audit.get("board_binding"),
        "artifact_sha256": audit.get("artifact_sha256"),
        "artifacts": artifact_records,
        "wiring": wiring,
        "module_inventory": module_inventory,
        "manifest_path": manifest_result["path"],
        "manifest_sha256": manifest_result["sha256"],
        "manifest_declared_files": manifest_result["declared_files"],
        "manifest_verified_files": manifest_result["verified_files"],
        "application_goodput_bps": {
            "F_TO_R": audit.get("performance", {}).get("f_to_r_application_goodput_bps"),
            "R_TO_F": audit.get("performance", {}).get("r_to_f_application_goodput_bps"),
        },
        "committed_bytes": {
            "F_TO_R": audit.get("formal", {}).get("committed_bytes_f_to_r"),
            "R_TO_F": audit.get("formal", {}).get("committed_bytes_r_to_f"),
        },
        "stretch_4p8mbps": {
            "F_TO_R": audit.get("performance", {}).get("f_to_r_4p8mbps_stretch"),
            "R_TO_F": audit.get("performance", {}).get("r_to_f_4p8mbps_stretch"),
        },
        "shutdown_fixed": "PASS",
        "shutdown_rotating": "PASS",
        "authorization_consumed": True,
        "authorization_reusable": False,
        "p11_status": "NOT_STARTED",
    }


def verify_p10_4(errors: list[str]) -> dict[str, Any]:
    pass_tag = verify_tag(P10_4_PASS_TAG, P10_4_PASS_OBJECT, P10_4_PASS_TARGET, errors)
    closed_tag = verify_tag(
        P10_4_CLOSED_TAG, P10_4_CLOSED_OBJECT, P10_4_CLOSED_TARGET, errors
    )
    require(is_ancestor(P10_4_PASS_TARGET, P10_4_CLOSED_TARGET),
            "P10.4 pass target is not an ancestor of closed target", errors)
    require(is_ancestor(P10_4_CLOSED_TARGET, "HEAD"),
            "P10.4 closed target is not an ancestor of HEAD", errors)
    state = load_json(ROOT / "config/project_state.json")
    campaign = state.get("p10_4_acceptance", {})
    require(state.get("p10_4_status") == "PASS_WITH_NONBLOCKING_LIMITS" and
            campaign.get("status") == "PASS_WITH_NONBLOCKING_LIMITS",
            "P10.4 canonical status changed", errors)
    require(campaign.get("hardware_evidence_checkpoint") ==
            "f53d98252dfa85d73f35d49ebf5dc01323bcb4e7",
            "P10.4 evidence checkpoint changed", errors)
    require(campaign.get("authorization_consumed") is True and
            campaign.get("current_run_hardware_authorization") is False,
            "P10.4 authorization is not consumed", errors)
    require(campaign.get("shutdown_fixed") == "PASS" and
            campaign.get("shutdown_rotating") == "PASS",
            "P10.4 shutdown changed", errors)
    for key in (
        "final_summary", "composite_manifest", "evidence_consistency",
        "completion_audit", "offline_closure",
    ):
        path = ROOT / str(campaign.get(f"{key}_path", ""))
        expected = campaign.get(f"{key}_sha256")
        require(path.is_file(), f"P10.4 {key} missing", errors)
        if path.is_file():
            require(sha256(path) == expected, f"P10.4 {key} hash changed", errors)
    manifest_paths: list[Path] = []
    for key in ("parent_manifest", "suffix_manifest"):
        path = ROOT / str(campaign.get(f"{key}_path", ""))
        expected = campaign.get(f"{key}_sha256")
        require(path.is_file(), f"P10.4 {key} missing", errors)
        if path.is_file():
            require(sha256(path) == expected, f"P10.4 {key} hash changed", errors)
            manifest_paths.append(path)
    manifests, archive_provenance = verify_p10_4_run_manifests(
        manifest_paths, errors
    )
    return {
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "source_commit": campaign.get("source_commit"),
        "evidence_checkpoint": campaign.get("hardware_evidence_checkpoint"),
        "pass_tag": pass_tag,
        "closed_tag": closed_tag,
        "accepted_scope": "stationary autonomous AX7020 four-lane half-duplex hardening",
        "pending_scope": ["simultaneous bidirectional 2+2 in P10.4 artifacts"],
        "manifests": manifests,
        "archive_provenance": archive_provenance,
    }


def run_baseline(name: str, command: list[str], errors: list[str]) -> dict[str, Any]:
    env = dict(os.environ)
    env.update({
        "NO_HARDWARE": "1",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
    })
    result = subprocess.run(
        command, cwd=ROOT, env=env, text=True, capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        errors.append(f"{name} verify-existing failed: {result.stdout}{result.stderr}")
    return {
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "command": command,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "hardware_actions_executed": False,
    }


def collect() -> dict[str, Any]:
    errors: list[str] = []
    require(os.environ.get("NO_HARDWARE") == "1", "NO_HARDWARE must be 1", errors)
    require(os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower()
            in {"false", "0", "no"},
            "CURRENT_RUN_HARDWARE_AUTHORIZATION must be false", errors)
    p10_5: dict[str, Any] = {}
    p10_4: dict[str, Any] = {}
    try:
        p10_5 = verify_p10_5(errors)
        p10_4 = verify_p10_4(errors)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
            subprocess.SubprocessError) as exc:
        errors.append(f"frozen closeout verification exception: {exc}")
    baselines = {
        name: run_baseline(name, command, errors)
        for name, command in BASELINE_COMMANDS.items()
    }
    return {
        "schema_version": 1,
        "test_id": "P10-FAMILY-CLOSEOUT-VERIFY-EXISTING",
        "status": "PASS" if not errors else "FAIL",
        "p10_5": p10_5,
        "p10_4": p10_4,
        "baselines": baselines,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "p11_status": "NOT_STARTED",
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = collect()
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"P10_FAMILY_VERIFY_EXISTING={payload['status']}")
        print("NO_HARDWARE_ACTIONS_EXECUTED=true")
        print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
        print("P11_STATUS=NOT_STARTED")
        for error in payload["errors"]:
            print(f"ERROR={error}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
