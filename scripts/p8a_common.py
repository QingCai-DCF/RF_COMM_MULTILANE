#!/usr/bin/env python3
"""Shared validation and rendering helpers for the P8A canonical baseline."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "config/project_state.json"
REQUIREMENTS_PATH = ROOT / "config/project_requirements.yaml"
STATUS_PATH = ROOT / "PROJECT_STATUS.md"
TRACEABILITY_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
RECONCILIATION_JSON_PATH = ROOT / "evidence/generated/p8a_p0_p7_reconciliation.json"
RECONCILIATION_MD_PATH = ROOT / "evidence/generated/p8a_p0_p7_reconciliation.md"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

INITIAL_REQUIREMENT_IDS = {
    "SYS-ARCH-001",
    "SYS-GEO-001",
    "SYS-GEO-002",
    "SYS-MOTION-001",
    "SYS-PERMIT-001",
    "SYS-PERMIT-002",
    "SYS-PERMIT-003",
    "SYS-PERMIT-004",
    "PHY-SAFE-001",
    "PHY-SAFE-002",
    "PHY-SAFE-003",
    "PHY-SAFE-004",
    "MAP-001",
    "MAP-002",
    "MAP-003",
    "PERF-HD-001",
    "PERF-FD-001",
    "DATA-001",
    "EVID-001",
    "EVID-002",
    "SAFE-OPT-001",
    "MECH-001",
}

P8A_REQUIREMENT_IDS = {
    "P8A-CANON-001",
    "P8A-STATE-001",
    "P8A-TRACE-001",
    "P8A-EVID-001",
    "P8A-SCOPE-001",
    "P8A-LEGACY-001",
}

P8B_REQUIREMENT_IDS = {
    "MAP-001", "MAP-002", "MAP-003", "MAP-004", "MAP-005", "MAP-006",
    "PHASE-001", "PHASE-002", "PHASE-003", "HANDOVER-001", "HANDOVER-002",
    "GEO-MODEL-001", "GEO-MODEL-002", "EVID-P8B-001",
}

P8C_REQUIREMENT_IDS = {
    "SYS-PERMIT-001", "SYS-PERMIT-002", "SYS-PERMIT-003", "SYS-PERMIT-004",
    "SYS-PERMIT-005", "SYS-PERMIT-006",
    "PHY-SAFE-001", "PHY-SAFE-002", "PHY-SAFE-003", "PHY-SAFE-004",
    "PHY-SAFE-005", "PHY-SAFE-006",
}

REQUIRED_REQUIREMENT_FIELDS = {
    "requirement_id",
    "requirement_text",
    "profile",
    "verification_method",
    "verification_stage",
    "test_id",
    "evidence_path",
    "status",
    "waiver",
    "artifact_hashes",
}

EXPECTED_STAGE_STATUS = {
    "P0_BOOTSTRAP": "PASS",
    "P1_OFFLINE_HARDENING": "PASS",
    "P2_SIMULATION_BASELINE": "PASS",
    "P3_PRE_HW_ACCEPTANCE_PACKAGE": "PASS",
    "P4_AUTO_HARDWARE_ACCEPTANCE": "PASS_WITH_PROXY_ILA_EVIDENCE",
    "P5_2LANE_PROTOCOL_STABILIZATION": "PASS_WITH_NOTES",
    "P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET": "PASS",
    "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE": "PASS",
    "P8A_CANONICAL_REQUIREMENTS_STATE": "PASS",
    "P8B_GEOMETRY_MAPPING_HANDOVER": "PASS",
    "P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT": "PENDING",
    "P8D_SELECTIVE_REPEAT_DMA": "PENDING",
    "P8E_DUAL_TARGET_BUILD_TIMING_CDC": "PENDING",
}

EXPECTED_TOP_LEVEL_STATUS = {
    "p7_status": "PASS",
    "current_z7010_platform_status": "PLATFORM_LIMITED_PASS",
    "z7020_target_status": "PENDING_Z7020_HW",
    "rotation_status": "PENDING_FINAL_MECHANICAL",
    "final_product_status": "PENDING_HW",
    "product_final_acceptance": "PENDING",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def resolve_repo_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("path must be a non-empty string")
    pure = PurePosixPath(value.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"path escapes repository: {value}")
    resolved = (root / Path(*pure.parts)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes repository: {value}") from exc
    return resolved


def hash_record_errors(record: Any, root: Path, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{label}: artifact hash record must be a mapping"]
    path_value = record.get("path")
    digest = str(record.get("sha256", "")).lower()
    if not SHA256_RE.fullmatch(digest):
        errors.append(f"{label}: invalid SHA256")
    try:
        path = resolve_repo_path(root, path_value)
    except (TypeError, ValueError) as exc:
        errors.append(f"{label}: {exc}")
        return errors
    if not path.is_file():
        errors.append(f"{label}: missing artifact {path_value}")
    elif SHA256_RE.fullmatch(digest) and sha256_file(path) != digest:
        errors.append(f"{label}: SHA256 mismatch for {path_value}")
    return errors


def validate_state(state: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "project",
        "canonical_constraint",
        "p7_status",
        "current_z7010_platform_status",
        "z7020_target_status",
        "rotation_status",
        "final_product_status",
        "product_final_acceptance",
        "current_run_hardware_authorization",
        "current_profiles",
        "legacy_known_failures",
        "resolved_failures",
        "pending_gates",
        "last_verified_commit",
        "stage_status",
        "p7_evidence",
        "architecture_status",
    }
    missing = sorted(required - set(state))
    if missing:
        errors.append(f"project state missing fields: {', '.join(missing)}")

    if state.get("schema_version") != 1:
        errors.append("project state schema_version must be 1")
    if state.get("project") != "RF_COMM_MULTILANE":
        errors.append("project state project must be RF_COMM_MULTILANE")

    for key, expected in EXPECTED_TOP_LEVEL_STATUS.items():
        if state.get(key) != expected:
            errors.append(f"{key} must remain {expected}")
    if state.get("current_run_hardware_authorization") is not False:
        errors.append("current_run_hardware_authorization must be false")
    if state.get("no_hardware_default") is not True:
        errors.append("no_hardware_default must be true")
    if state.get("p8a_no_hardware_actions_executed") is not True:
        errors.append("p8a_no_hardware_actions_executed must be true")

    canonical = state.get("canonical_constraint", {})
    if not isinstance(canonical, dict):
        errors.append("canonical_constraint must be a mapping")
    else:
        if canonical.get("path") != "PROJECT_CONSTRAINTS.txt":
            errors.append("canonical constraint path must be PROJECT_CONSTRAINTS.txt")
        errors.extend(hash_record_errors(canonical, root, "canonical_constraint"))

    stage_status = state.get("stage_status", {})
    p8c_pass = isinstance(stage_status, dict) and stage_status.get(
        "P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT") == "PASS"
    if not isinstance(stage_status, dict):
        errors.append("stage_status must be a mapping")
    else:
        expected_stages = dict(EXPECTED_STAGE_STATUS)
        if p8c_pass:
            expected_stages["P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT"] = "PASS"
        for key, expected in expected_stages.items():
            if stage_status.get(key) != expected:
                errors.append(f"stage_status.{key} must be {expected}")

    profiles = state.get("current_profiles", [])
    if not isinstance(profiles, list):
        errors.append("current_profiles must be a list")
    else:
        profile_names = {item.get("profile") for item in profiles if isinstance(item, dict)}
        if "Z7010_2LANE_DEV" not in profile_names:
            errors.append("current_profiles must include Z7010_2LANE_DEV")
        if "Z7020_8LANE_TARGET" not in profile_names:
            errors.append("current_profiles must include pending Z7020_8LANE_TARGET")

    legacy = state.get("legacy_known_failures", [])
    legacy_by_id = {
        item.get("failure_id"): item for item in legacy if isinstance(item, dict)
    } if isinstance(legacy, list) else {}
    ab_l1 = legacy_by_id.get("AB_L1_BAD_DIR")
    if not ab_l1 or ab_l1.get("status") != "HISTORICAL_RETAINED":
        errors.append("AB_L1_BAD_DIR history must be retained")
    elif ab_l1.get("evidence_path"):
        try:
            evidence = resolve_repo_path(root, ab_l1["evidence_path"])
            if not evidence.is_file():
                errors.append("AB_L1_BAD_DIR evidence path is missing")
        except ValueError as exc:
            errors.append(str(exc))

    resolved = state.get("resolved_failures", [])
    resolved_by_id = {
        item.get("failure_id"): item for item in resolved if isinstance(item, dict)
    } if isinstance(resolved, list) else {}
    current_lane1 = resolved_by_id.get("AB_L1_CURRENT_P7_SCOPE")
    if not current_lane1 or current_lane1.get("status") != "RESOLVED_FOR_P7_STATIONARY_2LANE_ONLY":
        errors.append("current AB_L1 usability must be scoped to P7 stationary 2-lane only")
    else:
        exclusions = set(current_lane1.get("not_extrapolated_to", []))
        required_exclusions = {"Z7020", "SECTOR_BANK", "ROTATION", "FINAL_PRODUCT"}
        if not required_exclusions.issubset(exclusions):
            errors.append("AB_L1 current resolution must exclude Z7020/sector-bank/rotation/final product")

    p7 = state.get("p7_evidence", {})
    if not isinstance(p7, dict):
        errors.append("p7_evidence must be a mapping")
    else:
        expected = {
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P7-R74-FORMAL-FULL",
            "status": "PASS",
            "source_commit": "911e1a303ff58593cac5ff4c4b70150d17f9a26b",
        }
        for key, value in expected.items():
            if p7.get(key) != value:
                errors.append(f"p7_evidence.{key} must be {value}")
        evidence_path = p7.get("evidence_path")
        evidence_sha = str(p7.get("evidence_sha256", "")).lower()
        try:
            evidence = resolve_repo_path(root, evidence_path)
            if not evidence.is_file():
                errors.append("P7 canonical evidence path is missing")
            elif not SHA256_RE.fullmatch(evidence_sha) or sha256_file(evidence) != evidence_sha:
                errors.append("P7 canonical evidence SHA256 mismatch")
        except (TypeError, ValueError) as exc:
            errors.append(f"P7 canonical evidence path invalid: {exc}")
        artifacts = p7.get("artifact_hashes", {})
        for name in ("bitstream", "ps_elf", "stationary_profile", "functional_profile"):
            digest = str(artifacts.get(name, "")).lower() if isinstance(artifacts, dict) else ""
            if not SHA256_RE.fullmatch(digest):
                errors.append(f"p7_evidence artifact hash missing or invalid: {name}")

    architecture = state.get("architecture_status", {})
    if not isinstance(architecture, dict):
        errors.append("architecture_status must be a mapping")
    else:
        expected_arch = {
            "global_permit_architecture": "SINGLE_ACTIVE_HIGH_PER_ENDPOINT",
            "fixed_endpoint_global_permit_count": 1,
            "rotating_endpoint_global_permit_count": 1,
            "implementation_status": (
                "RTL_PORTABLE_FUNCTION_PASS_PHYSICAL_PENDING_D17"
                if p8c_pass else "PENDING_P8C_D17"
            ),
        }
        for key, value in expected_arch.items():
            if architecture.get(key) != value:
                errors.append(f"architecture_status.{key} must be {value}")

    if p8c_pass:
        if state.get("current_program_stage") != "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE":
            errors.append("current_program_stage must advance to P8D after P8C PASS")
        if state.get("p8c_no_hardware_actions_executed") is not True:
            errors.append("p8c_no_hardware_actions_executed must be true")
        p8c = state.get("p8c_acceptance", {})
        if not isinstance(p8c, dict):
            errors.append("p8c_acceptance must be a mapping after P8C PASS")
        else:
            expected_p8c = {
                "status": "PASS",
                "profile": "P8C_MULTI_PROFILE_OFFLINE",
                "test_id": "P8C-FINAL-ACCEPTANCE",
                "hardware_actions_executed": False,
                "hardware_scope_promoted": False,
                "global_permit_physical_implementation": "PENDING_D17",
                "z7010_global_permit_pin_freeze": "PENDING_P9_PIN_FREEZE",
                "tfdu_duty_hardware_measurement": "PENDING_P9_OR_LATER",
            }
            for key, value in expected_p8c.items():
                if p8c.get(key) != value:
                    errors.append(f"p8c_acceptance.{key} must be {value}")
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P8C final evidence"),
                ("safety_config_path", "safety_config_sha256", "P8C safety config"),
            ):
                try:
                    artifact = resolve_repo_path(root, p8c.get(path_key))
                    digest = str(p8c.get(hash_key, "")).lower()
                    if not artifact.is_file() or not SHA256_RE.fullmatch(digest) or sha256_file(artifact) != digest:
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")
            if not re.fullmatch(r"[0-9a-f]{40}", str(p8c.get("source_commit", "")).lower()):
                errors.append("p8c_acceptance.source_commit must be a full Git commit hash")

    if state.get("stage_status", {}).get("P8B_GEOMETRY_MAPPING_HANDOVER") == "PASS":
        p8b = state.get("p8b_acceptance", {})
        if not isinstance(p8b, dict):
            errors.append("p8b_acceptance must be a mapping after P8B PASS")
        else:
            expected_p8b = {
                "status": "PASS",
                "profile": "D200_D600_8X32",
                "test_id": "P8B-OFFLINE-FULL-REGRESSION",
                "worst_case_geometry_acceptance": "PENDING_WITH_EXPLICIT_GAPS",
                "logic_model_timing_target": "PASS",
                "hardware_actions_executed": False,
            }
            for key, value in expected_p8b.items():
                if p8b.get(key) != value:
                    errors.append(f"p8b_acceptance.{key} must be {value}")
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P8B acceptance core"),
                ("geometry_config_path", "geometry_config_sha256", "P8B geometry config"),
                ("full_regression_path", "full_regression_sha256", "P8B full regression"),
            ):
                try:
                    artifact = resolve_repo_path(root, p8b.get(path_key))
                    digest = str(p8b.get(hash_key, "")).lower()
                    if not artifact.is_file() or not SHA256_RE.fullmatch(digest) or sha256_file(artifact) != digest:
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")
            source_commit = str(p8b.get("source_commit", "")).lower()
            if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
                errors.append("p8b_acceptance.source_commit must be a full Git commit hash")

    commit = str(state.get("last_verified_commit", "")).lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("last_verified_commit must be a full Git commit hash")
    return errors


def validate_requirements(document: dict[str, Any], root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    if document.get("schema_version") != 1:
        errors.append("requirements schema_version must be 1")
    if document.get("canonical_constraint") != "PROJECT_CONSTRAINTS.txt":
        errors.append("requirements canonical_constraint must be PROJECT_CONSTRAINTS.txt")
    canonical_sha = str(document.get("canonical_constraint_sha256", "")).lower()
    canonical_path = root / "PROJECT_CONSTRAINTS.txt"
    if not canonical_path.is_file() or canonical_sha != sha256_file(canonical_path):
        errors.append("requirements canonical constraint SHA256 mismatch")

    requirements = document.get("requirements")
    if not isinstance(requirements, list):
        return errors + ["requirements must be a list"]

    ids = [item.get("requirement_id") for item in requirements if isinstance(item, dict)]
    duplicates = sorted(req_id for req_id, count in Counter(ids).items() if count > 1)
    if duplicates:
        errors.append(f"duplicate requirement IDs: {', '.join(duplicates)}")
    present = set(ids)
    missing_initial = sorted(INITIAL_REQUIREMENT_IDS - present)
    missing_p8a = sorted(P8A_REQUIREMENT_IDS - present)
    if missing_initial:
        errors.append(f"missing initial requirement IDs: {', '.join(missing_initial)}")
    if missing_p8a:
        errors.append(f"missing P8A requirement IDs: {', '.join(missing_p8a)}")

    allowed_statuses = {"PASS", "PENDING", "FAIL", "WAIVED"}
    by_id: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(requirements):
        label = f"requirements[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be a mapping")
            continue
        req_id = item.get("requirement_id")
        if isinstance(req_id, str):
            by_id[req_id] = item
            label = req_id
        missing_fields = sorted(REQUIRED_REQUIREMENT_FIELDS - set(item))
        if missing_fields:
            errors.append(f"{label} missing fields: {', '.join(missing_fields)}")
        status = item.get("status")
        if status not in allowed_statuses:
            errors.append(f"{label} has invalid status {status}")
        if not isinstance(item.get("requirement_text"), str) or not item.get("requirement_text"):
            errors.append(f"{label} requirement_text must be non-empty")
        if not isinstance(item.get("verification_method"), str) or not item.get("verification_method"):
            errors.append(f"{label} verification_method must be non-empty")
        if not isinstance(item.get("verification_stage"), str) or not item.get("verification_stage"):
            errors.append(f"{label} verification_stage must be non-empty")

        waiver = item.get("waiver")
        if status == "WAIVED" and not waiver:
            errors.append(f"{label} WAIVED status requires waiver metadata")
        if status != "WAIVED" and waiver is not None:
            errors.append(f"{label} non-WAIVED status must have null waiver")

        hashes = item.get("artifact_hashes")
        if not isinstance(hashes, list):
            errors.append(f"{label} artifact_hashes must be a list")
            hashes = []
        if status == "PASS":
            if not item.get("profile"):
                errors.append(f"{label} PASS requires profile")
            if not item.get("test_id"):
                errors.append(f"{label} PASS requires test_id")
            evidence_path = item.get("evidence_path")
            try:
                evidence = resolve_repo_path(root, evidence_path)
                if not evidence.is_file():
                    errors.append(f"{label} PASS evidence path is missing")
            except (TypeError, ValueError) as exc:
                errors.append(f"{label} PASS evidence path invalid: {exc}")
            if not hashes:
                errors.append(f"{label} PASS requires artifact_hashes")
        for hash_index, record in enumerate(hashes):
            errors.extend(hash_record_errors(record, root, f"{label}.artifact_hashes[{hash_index}]"))

    p8c_closed = any(by_id.get(req_id, {}).get("status") == "PASS" for req_id in P8C_REQUIREMENT_IDS)
    for req_id in INITIAL_REQUIREMENT_IDS - P8B_REQUIREMENT_IDS - P8C_REQUIREMENT_IDS:
        if req_id in by_id and by_id[req_id].get("status") != "PENDING":
            errors.append(f"{req_id} must remain PENDING until its scoped verification closes")
    for req_id in P8A_REQUIREMENT_IDS:
        if req_id in by_id and by_id[req_id].get("status") != "PASS":
            errors.append(f"{req_id} must be PASS for the P8A baseline")
    for req_id in P8B_REQUIREMENT_IDS:
        if req_id in by_id and by_id[req_id].get("status") != "PASS":
            errors.append(f"{req_id} must be PASS after P8B closure")
    if p8c_closed:
        missing_p8c = sorted(P8C_REQUIREMENT_IDS - set(by_id))
        if missing_p8c:
            errors.append(f"missing P8C requirement IDs: {', '.join(missing_p8c)}")
        for req_id in P8C_REQUIREMENT_IDS & set(by_id):
            item = by_id[req_id]
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P8C portable-function closure")
            if item.get("verification_scope") != "PORTABLE_FUNCTION_PASS / OFFLINE_RTL":
                errors.append(f"{req_id} must declare portable offline RTL verification scope")
            if not item.get("hardware_followup"):
                errors.append(f"{req_id} must retain explicit hardware follow-up")
            if not SHA256_RE.fullmatch(str(item.get("artifact_hash", "")).lower()):
                errors.append(f"{req_id} must declare a primary artifact_hash")
    return errors


def _md(value: Any) -> str:
    if value is None:
        return "—"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_project_status(state: dict[str, Any]) -> str:
    stages = state["stage_status"]
    p7 = state["p7_evidence"]
    lines = [
        "# Project Status",
        "",
        "> Generated from `config/project_state.json` by `scripts/generate_project_status.py`; do not edit by hand.",
        "",
        "## Canonical scoped status",
        "",
        "```text",
        f"P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE: {state['p7_status']}",
        f"CURRENT_Z7010_PLATFORM_ACCEPTANCE: {state['current_z7010_platform_status']}",
        f"Z7020_TARGET_ACCEPTANCE: {state['z7020_target_status']}",
        f"ROTATION_ACCEPTANCE: {state['rotation_status']}",
        f"FINAL_PRODUCT_HARDWARE_ACCEPTANCE: {state['final_product_status']}",
        f"PRODUCT_FINAL_ACCEPTANCE: {state['product_final_acceptance']}",
        f"CURRENT_RUN_HARDWARE_AUTHORIZATION: {str(state['current_run_hardware_authorization']).lower()}",
        "```",
        "",
        "The P7 PASS is limited to the stationary two-lane application path on the current Z7010 development platform. It is not Z7020, sector-bank, rotating, Ethernet, 8-lane, or final-product acceptance.",
        "",
        "## Program stages",
        "",
        "| Stage | Status |",
        "|---|---|",
    ]
    for stage, status in stages.items():
        lines.append(f"| `{_md(stage)}` | `{_md(status)}` |")

    lines += [
        "",
        "## P7 canonical evidence",
        "",
        f"- Profile: `{p7['profile']}`",
        f"- Test ID: `{p7['test_id']}`",
        f"- Formal run: `{p7['run_id']}`",
        f"- Hardware source commit: `{p7['source_commit']}`",
        f"- Evidence commit: `{p7['evidence_commit']}`",
        f"- Evidence: `{p7['evidence_path']}`",
        f"- Evidence SHA256: `{p7['evidence_sha256']}`",
        f"- Bitstream SHA256: `{p7['artifact_hashes']['bitstream']}`",
        f"- PS ELF SHA256: `{p7['artifact_hashes']['ps_elf']}`",
        "- Shutdown-before/after: `PASS` / `PASS`",
        "",
        "## Legacy failure reconciliation",
        "",
        "| Record | Current interpretation | Evidence |",
        "|---|---|---|",
    ]
    for item in state["legacy_known_failures"]:
        lines.append(
            f"| `{_md(item['failure_id'])}` | `{_md(item['status'])}` | `{_md(item['evidence_path'])}` |"
        )
    for item in state["resolved_failures"]:
        lines.append(
            f"| `{_md(item['failure_id'])}` | `{_md(item['status'])}` | `{_md(item['evidence_path'])}` |"
        )

    if isinstance(state.get("p8c_acceptance"), dict):
        p8c = state["p8c_acceptance"]
        lines += [
            "",
            "## P8C portable-function acceptance",
            "",
            f"- Status: `{p8c['status']}` (offline RTL/model scope only)",
            f"- Source commit: `{p8c['source_commit']}`",
            f"- Evidence: `{p8c['evidence_path']}`",
            f"- Single global permit RTL: `{p8c['single_global_permit_rtl_architecture']}`",
            f"- Exact rolling duty RTL: `{p8c['exact_rolling_duty_rtl_property']}`",
            f"- Physical permit implementation: `{p8c['global_permit_physical_implementation']}`",
            f"- Z7010 permit pin freeze: `{p8c['z7010_global_permit_pin_freeze']}`",
            f"- External duty measurement: `{p8c['tfdu_duty_hardware_measurement']}`",
        ]

    lines += [
        "",
        "`AB_L1_BAD_DIR` remains immutable history. The later lane1 evidence resolves usability only for the explicitly named P7 stationary Z7010 two-lane scope and is not extrapolated to future hardware.",
        "",
        "## Architecture and pending gates",
        "",
        f"- GLOBAL_PERMIT architecture: `{state['architecture_status']['global_permit_architecture']}`",
        "- Fixed endpoint permit count: `1`",
        "- Rotating endpoint permit count: `1`",
        f"- Implementation status: `{state['architecture_status']['implementation_status']}`",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    for gate in state["pending_gates"]:
        lines.append(f"| `{_md(gate['gate_id'])}` | `{_md(gate['status'])}` |")
    lines += [
        "",
        f"Last verified evidence commit: `{state['last_verified_commit']}`.",
        "",
        "P8A, P8B, and any completed P8C portable-function gate were executed with `NO_HARDWARE=1`; they do not create or promote hardware acceptance scope.",
        "",
    ]
    return "\n".join(lines)


def render_traceability(document: dict[str, Any]) -> str:
    requirements = document["requirements"]
    counts = Counter(item["status"] for item in requirements)
    lines = [
        "# Requirement Traceability Matrix",
        "",
        "> Generated from `config/project_requirements.yaml` by `scripts/generate_requirement_traceability.py`; do not edit by hand.",
        "",
        f"Canonical constraint: `PROJECT_CONSTRAINTS.txt` (`{document['canonical_constraint_sha256']}`).",
        "",
        "```text",
        f"REQUIREMENT_COUNT: {len(requirements)}",
        f"PASS: {counts.get('PASS', 0)}",
        f"PENDING: {counts.get('PENDING', 0)}",
        f"FAIL: {counts.get('FAIL', 0)}",
        f"WAIVED: {counts.get('WAIVED', 0)}",
        "```",
        "",
        "A PENDING requirement is not a failure and is not a PASS. P8A baseline PASS means the requirement inventory and traceability machinery are complete; it does not promote unverified product requirements.",
        "",
        "| Requirement ID | Status | Profile | Verification stage | Test ID | Evidence | Requirement |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in requirements:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{_md(item['requirement_id'])}`",
                    f"`{_md(item['status'])}`",
                    _md(item["profile"]),
                    f"`{_md(item['verification_stage'])}`",
                    f"`{_md(item['test_id'])}`" if item["test_id"] else "—",
                    f"`{_md(item['evidence_path'])}`" if item["evidence_path"] else "—",
                    _md(item["requirement_text"]),
                ]
            )
            + " |"
        )

    lines += ["", "## PASS artifact bindings", ""]
    for item in requirements:
        if item["status"] != "PASS":
            continue
        lines += [f"### `{item['requirement_id']}`", ""]
        for record in item["artifact_hashes"]:
            lines.append(f"- `{record['path']}` — `{record['sha256']}`")
        lines.append("")
    return "\n".join(lines)


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
