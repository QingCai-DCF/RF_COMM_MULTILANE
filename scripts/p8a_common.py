#!/usr/bin/env python3
"""Shared validation and rendering helpers for the P8A canonical baseline."""

from __future__ import annotations

import hashlib
import functools
import json
import re
import subprocess
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

P8D_REQUIREMENT_IDS = {
    "L2-ARQ-001", "L2-ARQ-002", "L2-SEQ-001", "L2-SACK-001", "L2-SACK-002",
    "L2-DUP-001", "L2-STALE-001", "L2-MIG-001", "L2-RETRY-001",
    "SCHED-001", "SCHED-002", "SCHED-003", "AXIS-001",
    "DMA-001", "DMA-002", "DMA-003", "DMA-004",
    "RFAP-001", "RFAP-002", "PERF-MODEL-001", "PERF-MODEL-002",
}

P8E_REQUIREMENT_IDS = {
    "BUILD-001", "BUILD-002",
    "TIMING-001", "TIMING-002", "TIMING-003", "TIMING-004",
    "CDC-001", "CDC-002", "CDC-003", "CDC-004", "RDC-001",
    "DRC-001", "DRC-002",
    "RESOURCE-001", "RESOURCE-002", "RESOURCE-003",
    "AXIDMA-001", "AXIDMA-002",
    "PROFILE-001", "PROFILE-002", "REPRO-001",
}

P9_REQUIREMENT_IDS = {
    "P9-HW-001", "P9-HW-002", "P9-HW-003",
    "P9-PHY-001", "P9-PHY-002", "P9-PHY-003", "P9-PHY-004",
    "P9-SAFE-001", "P9-SAFE-002", "P9-SAFE-003", "P9-SAFE-004",
    "P9-L2-001", "P9-L2-002", "P9-L2-003",
    "P9-L3-001", "P9-L3-002", "P9-L3-003",
    "P9-DMA-001", "P9-DMA-002", "P9-DMA-003", "P9-DMA-004",
    "P9-RFAP-001", "P9-RFAP-002", "P9-RFAP-003",
    "P9-PERF-001", "P9-SOAK-001", "P9-EVID-001",
}

P9_CLOSEOUT_REQUIREMENT_IDS = {"P9-CLOSEOUT-001"}

P9_SCOPE = "Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"

P10_REQUIREMENT_IDS = {
    "P10-HW-001",
    "P10-PHY-001", "P10-PHY-002",
    "P10-L2-001",
    "P10-DMA-001",
    "P10-SYS-001",
    "P10-OBJ-001",
    "P10-REC-001",
    "P10-SCHED-001",
    "P10-PERF-001",
    "P10-SOAK-001",
    "P10-EVID-001",
}

P10_CLOSEOUT_REQUIREMENT_IDS = {"P10-CLOSEOUT-001"}
P10_POST_ACCEPTANCE_ANALYSIS_REQUIREMENT_IDS = {"P10-PERF-MEAS-001"}
P10_1_OFFLINE_REQUIREMENT_IDS = {
    "PERF-MEAS-001", "PERF-MEAS-002", "PERF-MEAS-003", "PERF-MEAS-004",
    "PERF-FINAL-001",
    "PERF-OBS-001", "PERF-OBS-002", "PERF-OBS-003",
    "PERF-AUTO-001", "PERF-AUTO-002",
    "PERF-PIPE-001", "PERF-PIPE-002", "PERF-PIPE-003",
    "PERF-STREAM-001", "PERF-STREAM-002",
    "HWPREP-P10_1-001",
}
P10_1_EXTENDED_MODEL_REQUIREMENT_IDS = {"PERF-MODEL-001", "PERF-MODEL-002"}
P10_1_PENDING_HARDWARE_REQUIREMENT_IDS = {"PERF-HW-001"}
P11_READINESS_REQUIREMENT_IDS = {
    "P11-READY-001", "P11-READY-002", "P11-READY-003",
}

P10_SCOPE = "AX7020_DUAL_NODE_STATIONARY_2LANE_NO_ETHERNET_HARDWARE_VALIDATION"
P10_STAGE = "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET"
P10_NEXT_STAGE = "P10_POST_ACCEPTANCE_ANALYSIS"
P10_1_OFFLINE_STAGE = (
    "P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS"
)
P10_1_NEXT_STAGE = (
    "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE"
)
P10_1_OFFLINE_SCOPE = (
    "P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_NO_HARDWARE"
)
P10_CLOSEOUT_SCOPE = "P10_POST_ACCEPTANCE_METADATA_ONLY_NO_HARDWARE"
P10_ANALYSIS_SCOPE = "P10_POST_ACCEPTANCE_ANALYSIS_NO_HARDWARE"

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


@functools.lru_cache(maxsize=None)
def sha256_artifact(path: Path, root: Path) -> str:
    """Hash canonical Git bytes for a clean tracked file, otherwise working bytes."""
    try:
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", relative],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        clean = subprocess.run(
            ["git", "diff", "--quiet", "--", relative],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
        if tracked and clean:
            canonical = subprocess.check_output(["git", "show", f":{relative}"], cwd=root)
            return hashlib.sha256(canonical).hexdigest()
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return sha256_file(path)


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
    elif SHA256_RE.fullmatch(digest) and sha256_artifact(path, root) != digest:
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
        "p8d_status",
        "p8e_status",
        "p9_status",
        "p10_status",
        "p10_1_offline_status",
        "p10_1_hardware_status",
        "p11_status",
        "p11_hardware_ready",
        "last_hardware_stage",
        "last_hardware_run_id",
        "last_shutdown_fixed",
        "last_shutdown_rotating",
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
    p8d_stage = stage_status.get("P8D_SELECTIVE_REPEAT_DMA") if isinstance(stage_status, dict) else None
    p8d_pass = p8d_stage == "PASS"
    p8e_stage = stage_status.get("P8E_DUAL_TARGET_BUILD_TIMING_CDC") if isinstance(stage_status, dict) else None
    p8e_pass = p8e_stage == "PASS"
    p9_stage = stage_status.get(
        "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"
    ) if isinstance(stage_status, dict) else None
    p10_stage = stage_status.get(P10_STAGE) if isinstance(stage_status, dict) else None
    if not isinstance(stage_status, dict):
        errors.append("stage_status must be a mapping")
    else:
        expected_stages = dict(EXPECTED_STAGE_STATUS)
        if p8c_pass:
            expected_stages["P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT"] = "PASS"
        if p8d_stage in {"IN_PROGRESS", "PASS"}:
            expected_stages["P8D_SELECTIVE_REPEAT_DMA"] = p8d_stage
        if p8e_stage in {"IN_PROGRESS", "PASS"}:
            expected_stages["P8E_DUAL_TARGET_BUILD_TIMING_CDC"] = p8e_stage
        if p9_stage is not None:
            expected_stages[
                "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"
            ] = p9_stage
        if p10_stage is not None:
            expected_stages[P10_STAGE] = p10_stage
        for key, expected in expected_stages.items():
            if stage_status.get(key) != expected:
                errors.append(f"stage_status.{key} must be {expected}")
        if p8d_stage not in {"PENDING", "IN_PROGRESS", "PASS"}:
            errors.append("stage_status.P8D_SELECTIVE_REPEAT_DMA has invalid status")
        if p8e_stage not in {"PENDING", "IN_PROGRESS", "PASS"}:
            errors.append("stage_status.P8E_DUAL_TARGET_BUILD_TIMING_CDC has invalid status")
        if p9_stage not in {
            "PENDING_CURRENT_RUN_AUTHORIZATION", "IN_PROGRESS", "PASS", "PARTIAL", "FAIL"
        }:
            errors.append("P9 hardware-validation stage has invalid status")
        if p10_stage not in {"IN_PROGRESS", "PASS", "PARTIAL", "FAIL"}:
            errors.append("P10 hardware-validation stage has invalid status")
    if state.get("p8d_status") != p8d_stage:
        errors.append("p8d_status must match stage_status.P8D_SELECTIVE_REPEAT_DMA")
    if state.get("p8e_status") != p8e_stage:
        errors.append("p8e_status must match stage_status.P8E_DUAL_TARGET_BUILD_TIMING_CDC")
    if state.get("p9_status") != p9_stage:
        errors.append("p9_status must match the P9 hardware-validation stage")
    if state.get("p10_status") != p10_stage:
        errors.append("p10_status must match the P10 hardware-validation stage")
    authorization_consumed = state.get("last_hardware_authorization_consumed") is True
    p10_authorization = state.get("p10_current_run_authorization", {})
    p10_authorization_consumed = (
        isinstance(p10_authorization, dict)
        and p10_authorization.get("consumed") is True
    )
    expected_authorization = (
        p10_stage in {"IN_PROGRESS", "PASS", "PARTIAL", "FAIL"}
        and not p10_authorization_consumed
        if p10_stage is not None
        else (
            p9_stage in {"IN_PROGRESS", "PASS", "PARTIAL", "FAIL"}
            and not authorization_consumed
        )
    )
    if state.get("current_run_hardware_authorization") is not expected_authorization:
        errors.append(
            "current_run_hardware_authorization must match the validated P9 run lifecycle"
        )

    profiles = state.get("current_profiles", [])
    if not isinstance(profiles, list):
        errors.append("current_profiles must be a list")
    else:
        profile_names = {item.get("profile") for item in profiles if isinstance(item, dict)}
        if "Z7010_2LANE_DEV" not in profile_names:
            errors.append("current_profiles must include Z7010_2LANE_DEV")
        if p8e_pass:
            required_p8e_profiles = {
                "Z7020_FIXED_8LANE_32MODULE_CORE",
                "Z7020_ROTATING_8LANE_CORE",
            }
            if not required_p8e_profiles.issubset(profile_names):
                errors.append("current_profiles must include both P8E exact-part Z7020 core profiles")
        elif "Z7020_8LANE_TARGET" not in profile_names:
            errors.append("current_profiles must include pending Z7020_8LANE_TARGET")
        if p10_stage == "PASS":
            required_p10_profiles = {
                "P10_AX7020_FIXED_2LANE",
                "P10_AX7020_ROTATING_2LANE",
            }
            if not required_p10_profiles.issubset(profile_names):
                errors.append("current_profiles must include both scoped P10 AX7020 profiles")

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

    if p9_stage == "PASS" and authorization_consumed:
        p9_lane1 = state.get("ab_l1_status", {})
        if not isinstance(p9_lane1, dict):
            errors.append("ab_l1_status must be a mapping after P9 closeout")
        else:
            if p9_lane1.get("legacy_status") != "BAD_DIR":
                errors.append("ab_l1_status.legacy_status must retain BAD_DIR")
            if p9_lane1.get("current_p9_stationary_status") != "PASS":
                errors.append("ab_l1_status.current_p9_stationary_status must be PASS")
            exclusions = set(p9_lane1.get("not_extrapolated_to", []))
            required_exclusions = {"Z7020", "SECTOR_BANK", "ROTATION", "FINAL_PRODUCT"}
            if not required_exclusions.issubset(exclusions):
                errors.append("P9 AB_L1 PASS must not be extrapolated beyond stationary Z7010 scope")

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
        if p9_stage == "PASS" and authorization_consumed:
            if architecture.get("global_permit_physical_implementation") != "PENDING_D17":
                errors.append("global permit physical implementation must remain PENDING_D17")
            if architecture.get("external_tfdu_duty_measurement") != "PENDING_EXTERNAL_MEASUREMENT":
                errors.append("external TFDU duty measurement must remain pending external measurement")

    if p8c_pass:
        if p10_stage == "PASS" and p10_authorization_consumed:
            if state.get("p10_1_offline_status") == "PASS":
                p10_1_hardware_status = state.get("p10_1_hardware_status")
                if p10_1_hardware_status == "PASS":
                    expected_program_stage = "P11_PREREQUISITE_ACQUISITION"
                elif p10_1_hardware_status in {"PARTIAL", "FAIL"}:
                    expected_program_stage = "P10_1_PERFORMANCE_REMEDIATION"
                else:
                    expected_program_stage = P10_1_NEXT_STAGE
            elif state.get("p10_1_offline_status") == "IN_PROGRESS":
                expected_program_stage = P10_1_OFFLINE_STAGE
            else:
                expected_program_stage = P10_NEXT_STAGE
        elif p10_stage in {"IN_PROGRESS", "PARTIAL", "FAIL"}:
            expected_program_stage = P10_STAGE
        elif p9_stage == "PASS" and authorization_consumed:
            expected_program_stage = "P9_COMPLETE_P10_NOT_STARTED"
        elif p9_stage == "PASS":
            expected_program_stage = "P10A_Z7020_SINGLE_BOARD_MIGRATION"
        elif p8e_pass:
            expected_program_stage = (
                "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"
            )
        elif p8d_pass:
            expected_program_stage = "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING"
        else:
            expected_program_stage = "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE"
        if state.get("current_program_stage") != expected_program_stage:
            errors.append(f"current_program_stage must be {expected_program_stage}")
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

    if p8d_pass:
        if state.get("p8d_no_hardware_actions_executed") is not True:
            errors.append("p8d_no_hardware_actions_executed must be true")
        if not p8e_pass and state.get("p8e_status") not in {"PENDING", "IN_PROGRESS"}:
            errors.append("p8e_status must remain PENDING/IN_PROGRESS until P8E closure")
        p8d = state.get("p8d_acceptance", {})
        if not isinstance(p8d, dict):
            errors.append("p8d_acceptance must be a mapping after P8D PASS")
        else:
            expected_p8d = {
                "status": "PASS", "profile": "P8D_MULTI_PROFILE_OFFLINE",
                "test_id": "P8D-ACCEPTANCE-CORE", "hardware_actions_executed": False,
                "hardware_scope_promoted": False,
            }
            for key, value in expected_p8d.items():
                if p8d.get(key) != value:
                    errors.append(f"p8d_acceptance.{key} must be {value}")
            try:
                evidence = resolve_repo_path(root, p8d.get("evidence_path"))
                digest = str(p8d.get("evidence_sha256", "")).lower()
                if not evidence.is_file() or not SHA256_RE.fullmatch(digest) or sha256_file(evidence) != digest:
                    errors.append("P8D acceptance evidence path/hash mismatch")
            except (TypeError, ValueError) as exc:
                errors.append(f"P8D acceptance evidence path invalid: {exc}")
            if not re.fullmatch(r"[0-9a-f]{40}", str(p8d.get("source_commit", "")).lower()):
                errors.append("p8d_acceptance.source_commit must be a full Git commit hash")

    if p8e_pass:
        if state.get("p8e_no_hardware_actions_executed") is not True:
            errors.append("p8e_no_hardware_actions_executed must be true")
        if state.get("p8_portable_architecture_status") != "PASS":
            errors.append("p8_portable_architecture_status must be PASS after P8E closure")
        if state.get("p9_status") not in {
            "PENDING_CURRENT_RUN_AUTHORIZATION", "IN_PROGRESS", "PASS", "PARTIAL", "FAIL"
        }:
            errors.append("p9_status has an invalid hardware-validation lifecycle value")
        p8e = state.get("p8e_acceptance", {})
        if not isinstance(p8e, dict):
            errors.append("p8e_acceptance must be a mapping after P8E PASS")
        else:
            expected_p8e = {
                "status": "PASS",
                "profile": "P8E_MULTI_PROFILE_OFFLINE",
                "scope": "PORTABLE_ARCHITECTURE_PASS / OFFLINE_ROUTED_IMPLEMENTATION",
                "test_id": "P8E-DUAL-TARGET-BUILD-CDC-RESOURCE-TIMING-FINAL",
                "hardware_actions_executed": False,
                "hardware_scope_promoted": False,
            }
            for key, value in expected_p8e.items():
                if p8e.get(key) != value:
                    errors.append(f"p8e_acceptance.{key} must be {value}")
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P8E final evidence"),
                ("artifact_manifest_path", "artifact_manifest_sha256", "P8E artifact manifest"),
                ("build_matrix_path", "build_matrix_sha256", "P8E build matrix"),
                ("clock_reset_path", "clock_reset_sha256", "P8E clock/reset config"),
            ):
                try:
                    artifact = resolve_repo_path(root, p8e.get(path_key))
                    digest = str(p8e.get(hash_key, "")).lower()
                    if not artifact.is_file() or not SHA256_RE.fullmatch(digest) or sha256_file(artifact) != digest:
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")
            if not re.fullmatch(r"[0-9a-f]{40}", str(p8e.get("source_commit", "")).lower()):
                errors.append("p8e_acceptance.source_commit must be a full Git commit hash")

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

    if p9_stage == "PASS" and authorization_consumed:
        closeout = state.get("p9_post_checkpoint_closeout", {})
        if not isinstance(closeout, dict) or closeout.get("status") != "PASS":
            errors.append("P9 post-checkpoint closeout metadata must be PASS")
        else:
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P9 closeout evidence"),
                ("git_metadata_path", "git_metadata_sha256", "P9 Git checkpoint metadata"),
            ):
                try:
                    artifact = resolve_repo_path(root, closeout.get(path_key))
                    digest = str(closeout.get(hash_key, "")).lower()
                    if not artifact.is_file() or not SHA256_RE.fullmatch(digest) or sha256_file(artifact) != digest:
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")
            if closeout.get("hardware_actions_executed") is not False:
                errors.append("P9 closeout must not execute hardware actions")
            if closeout.get("p10_started") is not False:
                errors.append("P9 closeout must not start P10")

    if p10_stage == "PASS":
        if not p10_authorization_consumed:
            errors.append("P10 current-run authorization must be consumed after P10 PASS")
        else:
            expected_auth = {
                "status": "CONSUMED_AFTER_P10_ACCEPTANCE",
                "consumed": True,
                "reusable_for_future_run": False,
            }
            for key, value in expected_auth.items():
                if p10_authorization.get(key) != value:
                    errors.append(f"p10_current_run_authorization.{key} must be {value}")
            errors.extend(
                hash_record_errors(
                    {
                        "path": p10_authorization.get("path"),
                        "sha256": p10_authorization.get("sha256"),
                    },
                    root,
                    "p10_current_run_authorization",
                )
            )

        p10 = state.get("p10_acceptance", {})
        if not isinstance(p10, dict):
            errors.append("p10_acceptance must be a mapping after P10 PASS")
        else:
            expected_p10 = {
                "status": "PASS",
                "profile": "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET",
                "scope": P10_SCOPE,
                "test_id": "P10-FASTTRACK-FINAL",
                "hardware_actions_executed": True,
                "network_used": False,
                "no_hardware_movement": True,
                "rotation_executed": False,
                "rewiring_executed": False,
                "maximum_lane_mask_used": "0x3",
                "shutdown_fixed": "PASS",
                "shutdown_rotating": "PASS",
            }
            for key, value in expected_p10.items():
                if p10.get(key) != value:
                    errors.append(f"p10_acceptance.{key} must be {value}")
            mandatory_claims = p10.get("mandatory_claims", {})
            for claim in (
                "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET",
                "DUAL_Z7020_INDEPENDENT_ENDPOINTS",
                "DUAL_Z7020_2LANE_OPTICAL_LINK",
                "DUAL_Z7020_PS_PL_PHY_PL_PS",
                "STATIONARY_2LANE_30MIN",
            ):
                if not isinstance(mandatory_claims, dict) or mandatory_claims.get(claim) != "PASS":
                    errors.append(f"p10_acceptance.mandatory_claims.{claim} must be PASS")
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P10 final evidence"),
                ("evidence_manifest_path", "evidence_manifest_sha256", "P10 evidence manifest"),
                ("generated_summary_path", "generated_summary_sha256", "P10 generated summary"),
            ):
                try:
                    artifact = resolve_repo_path(root, p10.get(path_key))
                    digest = str(p10.get(hash_key, "")).lower()
                    if (
                        not artifact.is_file()
                        or not SHA256_RE.fullmatch(digest)
                        or sha256_artifact(artifact, root) != digest
                    ):
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")
            if not re.fullmatch(r"[0-9a-f]{40}", str(p10.get("source_commit", "")).lower()):
                errors.append("p10_acceptance.source_commit must be a full Git commit hash")
            if not re.fullmatch(
                r"[0-9a-f]{40}",
                str(p10.get("formal_evidence_freeze_commit", "")).lower(),
            ):
                errors.append("p10_acceptance.formal_evidence_freeze_commit must be a full Git commit hash")
            pending = p10.get("unchanged_pending_scopes", {})
            expected_pending = {
                "ETHERNET": "DEFERRED_NO_NETWORK_CABLE",
                "SPI": "PENDING",
                "PHYSICAL_GLOBAL_PERMIT": "PENDING_D17",
                "EXTERNAL_TFDU_DUTY": "PENDING_EXTERNAL_MEASUREMENT",
                "HANDOVER": "PENDING_P11",
                "8X32": "PENDING_P12",
                "600RPM": "PENDING_P13",
                "PRODUCT_FINAL": "PENDING",
            }
            for key, value in expected_pending.items():
                if not isinstance(pending, dict) or pending.get(key) != value:
                    errors.append(f"p10_acceptance.unchanged_pending_scopes.{key} must be {value}")

        p10_1_campaign = state.get("p10_1_hardware_campaign", {})
        p10_1_is_latest_hardware = (
            isinstance(p10_1_campaign, dict)
            and p10_1_campaign.get("hardware_actions_executed") is True
            and state.get("p10_1_hardware_status")
            in {"IN_PROGRESS", "PASS", "PARTIAL", "FAIL"}
        )
        expected_last_hardware = (
            {
                "last_hardware_stage": "P10_1",
                "last_hardware_run_id": p10_1_campaign.get("run_id"),
                "last_shutdown_fixed": p10_1_campaign.get("shutdown_fixed"),
                "last_shutdown_rotating": p10_1_campaign.get(
                    "shutdown_rotating"
                ),
            }
            if p10_1_is_latest_hardware
            else {
                "last_hardware_stage": "P10",
                "last_hardware_run_id": "p10_formal_20260730T181535Z_03",
                "last_shutdown_fixed": "PASS",
                "last_shutdown_rotating": "PASS",
            }
        )
        for key, value in expected_last_hardware.items():
            if state.get(key) != value:
                errors.append(
                    f"{key} must be {value} after the latest hardware campaign"
                )

        closeout = state.get("p10_post_acceptance_closeout", {})
        if not isinstance(closeout, dict) or closeout.get("status") != "PASS":
            errors.append("P10 post-acceptance closeout metadata must be PASS")
        else:
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P10 closeout evidence"),
                ("git_metadata_path", "git_metadata_sha256", "P10 Git checkpoint metadata"),
                ("remote_push_path", "remote_push_sha256", "P10 remote push evidence"),
            ):
                try:
                    artifact = resolve_repo_path(root, closeout.get(path_key))
                    digest = str(closeout.get(hash_key, "")).lower()
                    if (
                        not artifact.is_file()
                        or not SHA256_RE.fullmatch(digest)
                        or sha256_artifact(artifact, root) != digest
                    ):
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")
            if closeout.get("hardware_actions_executed") is not False:
                errors.append("P10 closeout must not execute hardware actions")
            if closeout.get("p11_started") is not False:
                errors.append("P10 closeout must not start P11")

        audit = state.get("p10_goodput_measurement_audit", {})
        if not isinstance(audit, dict) or audit.get("status") != "PASS":
            errors.append("P10 goodput measurement audit must be PASS")
        else:
            try:
                artifact = resolve_repo_path(root, audit.get("evidence_path"))
                digest = str(audit.get("evidence_sha256", "")).lower()
                if (
                    not artifact.is_file()
                    or not SHA256_RE.fullmatch(digest)
                    or sha256_artifact(artifact, root) != digest
                ):
                    errors.append("P10 goodput audit path/hash mismatch")
            except (TypeError, ValueError) as exc:
                errors.append(f"P10 goodput audit path invalid: {exc}")
            if audit.get("eligible_for_final_8lane_projection") is not False:
                errors.append("P10 current goodput fields must not be eligible for final 8-lane projection")
            if audit.get("hardware_actions_executed") is not False:
                errors.append("P10 goodput audit must be offline")

        p11 = state.get("p11_readiness", {})
        if not isinstance(p11, dict):
            errors.append("p11_readiness must be a mapping")
        else:
            expected_p11 = {
                "status": "NOT_READY",
                "official_stage_status": "NOT_STARTED",
                "hardware_ready": False,
                "current_run_hardware_authorization": False,
            }
            for key, value in expected_p11.items():
                if p11.get(key) != value:
                    errors.append(f"p11_readiness.{key} must be {value}")

    p10_1_offline = state.get("p10_1_offline_status")
    if p10_1_offline not in {"IN_PROGRESS", "PASS"}:
        errors.append("p10_1_offline_status must be IN_PROGRESS or PASS")
    if state.get("p10_1_hardware_status") not in {
        "PENDING_CURRENT_RUN_AUTHORIZATION",
        "IN_PROGRESS_OFFLINE_ARTIFACT_FREEZE",
        "AUTHORIZED_NOT_STARTED",
        "IN_PROGRESS",
        "PASS",
        "PARTIAL",
        "FAIL",
    }:
        errors.append(
            "p10_1_hardware_status has an invalid scoped campaign state"
        )
    if state.get("p11_status") != "NOT_STARTED":
        errors.append("p11_status must remain NOT_STARTED")
    if state.get("p11_hardware_ready") is not False:
        errors.append("p11_hardware_ready must remain false")
    if p10_1_offline == "PASS":
        p10_1_hardware_status = state.get("p10_1_hardware_status")
        hardware_campaign = state.get("p10_1_hardware_campaign", {})
        if p10_1_hardware_status in {
            "PENDING_CURRENT_RUN_AUTHORIZATION",
            "IN_PROGRESS_OFFLINE_ARTIFACT_FREEZE",
            "AUTHORIZED_NOT_STARTED",
        }:
            if state.get("p10_1_no_hardware_actions_executed") is not True:
                errors.append(
                    "P10.1 pre-hardware state requires no hardware actions"
                )
        elif not isinstance(hardware_campaign, dict) or (
            hardware_campaign.get("hardware_actions_executed") is not True
        ):
            errors.append(
                "P10.1 hardware state requires scoped hardware-action evidence"
            )
        if stage_status.get(P10_1_OFFLINE_STAGE) != "PASS":
            errors.append(f"stage_status.{P10_1_OFFLINE_STAGE} must be PASS")
        acceptance = state.get("p10_1_performance_and_observability", {})
        if not isinstance(acceptance, dict):
            errors.append("p10_1_performance_and_observability must be a mapping")
        else:
            expected_p10_1 = {
                "status": "PASS",
                "verification_scope": P10_1_OFFLINE_SCOPE,
                "scale_equivalent_4mbps_feasibility": "PASS",
                "hardware_experiments_authorized": False,
                "hardware_actions_executed": False,
            }
            for key, value in expected_p10_1.items():
                if acceptance.get(key) != value:
                    errors.append(
                        f"p10_1_performance_and_observability.{key} must be {value}"
                    )
            if acceptance.get("real_hardware_goodput_status") not in {
                "PENDING_CURRENT_RUN_AUTHORIZATION",
                "IN_PROGRESS_OFFLINE_ARTIFACT_FREEZE",
                "AUTHORIZED_NOT_STARTED",
                "IN_PROGRESS",
                "PASS",
                "PARTIAL",
                "FAIL",
            }:
                errors.append(
                    "p10_1_performance_and_observability."
                    "real_hardware_goodput_status has an invalid scoped state"
                )
            for path_key, hash_key, label in (
                ("evidence_path", "evidence_sha256", "P10.1 offline evidence"),
                (
                    "measurement_contract_path",
                    "measurement_contract_sha256",
                    "P10.1 measurement contract",
                ),
            ):
                try:
                    artifact = resolve_repo_path(root, acceptance.get(path_key))
                    digest = str(acceptance.get(hash_key, "")).lower()
                    if (
                        not artifact.is_file()
                        or not SHA256_RE.fullmatch(digest)
                        or sha256_artifact(artifact, root) != digest
                    ):
                        errors.append(f"{label} path/hash mismatch")
                except (TypeError, ValueError) as exc:
                    errors.append(f"{label} path invalid: {exc}")

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
    missing_p8d = sorted(P8D_REQUIREMENT_IDS - present)
    missing_p9 = sorted(P9_REQUIREMENT_IDS - present)
    missing_p9_closeout = sorted(P9_CLOSEOUT_REQUIREMENT_IDS - present)
    missing_p10 = sorted(P10_REQUIREMENT_IDS - present)
    missing_p10_closeout = sorted(P10_CLOSEOUT_REQUIREMENT_IDS - present)
    missing_p10_analysis = sorted(P10_POST_ACCEPTANCE_ANALYSIS_REQUIREMENT_IDS - present)
    missing_p10_1 = sorted(P10_1_OFFLINE_REQUIREMENT_IDS - present)
    missing_p10_1_hardware = sorted(
        P10_1_PENDING_HARDWARE_REQUIREMENT_IDS - present
    )
    missing_p11_readiness = sorted(P11_READINESS_REQUIREMENT_IDS - present)
    if missing_initial:
        errors.append(f"missing initial requirement IDs: {', '.join(missing_initial)}")
    if missing_p8a:
        errors.append(f"missing P8A requirement IDs: {', '.join(missing_p8a)}")
    if missing_p8d:
        errors.append(f"missing P8D requirement IDs: {', '.join(missing_p8d)}")
    if missing_p9:
        errors.append(f"missing P9 requirement IDs: {', '.join(missing_p9)}")
    if missing_p9_closeout:
        errors.append(f"missing P9 closeout requirement IDs: {', '.join(missing_p9_closeout)}")
    if missing_p10:
        errors.append(f"missing P10 requirement IDs: {', '.join(missing_p10)}")
    if missing_p10_closeout:
        errors.append(f"missing P10 closeout requirement IDs: {', '.join(missing_p10_closeout)}")
    if missing_p10_analysis:
        errors.append(
            "missing P10 post-acceptance analysis requirement IDs: "
            + ", ".join(missing_p10_analysis)
        )
    if missing_p10_1:
        errors.append("missing P10.1 offline requirement IDs: " + ", ".join(missing_p10_1))
    if missing_p10_1_hardware:
        errors.append(
            "missing P10.1 hardware requirement IDs: "
            + ", ".join(missing_p10_1_hardware)
        )
    if missing_p11_readiness:
        errors.append(
            "missing P11 readiness requirement IDs: "
            + ", ".join(missing_p11_readiness)
        )

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
    p8d_closed = any(by_id.get(req_id, {}).get("status") == "PASS" for req_id in P8D_REQUIREMENT_IDS)
    p8e_closed = any(by_id.get(req_id, {}).get("status") == "PASS" for req_id in P8E_REQUIREMENT_IDS)
    p9_closed = any(by_id.get(req_id, {}).get("status") == "PASS" for req_id in P9_REQUIREMENT_IDS)
    p10_closed = any(by_id.get(req_id, {}).get("status") == "PASS" for req_id in P10_REQUIREMENT_IDS)
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
    if p8d_closed:
        for req_id in P8D_REQUIREMENT_IDS:
            item = by_id.get(req_id, {})
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P8D portable-function closure")
            if item.get("verification_scope") != "PORTABLE_FUNCTION_PASS / OFFLINE_RTL_SOFTWARE_MODEL":
                errors.append(f"{req_id} must declare P8D portable offline verification scope")
            if not item.get("hardware_followup"):
                errors.append(f"{req_id} must retain explicit hardware follow-up")
            if not SHA256_RE.fullmatch(str(item.get("artifact_hash", "")).lower()):
                errors.append(f"{req_id} must declare a primary artifact_hash")
    if p8e_closed:
        missing_p8e = sorted(P8E_REQUIREMENT_IDS - set(by_id))
        if missing_p8e:
            errors.append(f"missing P8E requirement IDs: {', '.join(missing_p8e)}")
        for req_id in P8E_REQUIREMENT_IDS & set(by_id):
            item = by_id[req_id]
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P8E portable architecture closure")
            if item.get("verification_scope") != "PORTABLE_ARCHITECTURE_PASS / OFFLINE_ROUTED_IMPLEMENTATION":
                errors.append(f"{req_id} must declare P8E portable routed-offline verification scope")
            if not item.get("hardware_followup"):
                errors.append(f"{req_id} must retain explicit hardware follow-up")
            if not SHA256_RE.fullmatch(str(item.get("artifact_hash", "")).lower()):
                errors.append(f"{req_id} must declare a primary artifact_hash")
    if p9_closed:
        for req_id in P9_REQUIREMENT_IDS:
            item = by_id.get(req_id, {})
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P9 hardware closure")
            if item.get("verification_scope") != P9_SCOPE:
                errors.append(f"{req_id} must declare the exact platform-limited P9 scope")
            if not item.get("hardware_followup"):
                errors.append(f"{req_id} must retain broader-hardware follow-up")
            if not SHA256_RE.fullmatch(str(item.get("artifact_hash", "")).lower()):
                errors.append(f"{req_id} must declare a primary artifact_hash")
        for req_id in P9_CLOSEOUT_REQUIREMENT_IDS:
            item = by_id.get(req_id, {})
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P9 post-checkpoint closeout")
            if item.get("verification_scope") != "P9_POST_CHECKPOINT_METADATA_ONLY_NO_HARDWARE":
                errors.append(f"{req_id} must declare the no-hardware closeout scope")
    if p10_closed:
        for req_id in P10_REQUIREMENT_IDS:
            item = by_id.get(req_id, {})
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P10 hardware closure")
            if item.get("verification_scope") != P10_SCOPE:
                errors.append(f"{req_id} must declare the exact scoped P10 hardware scope")
            if not item.get("hardware_followup"):
                errors.append(f"{req_id} must retain broader-hardware follow-up")
            if not SHA256_RE.fullmatch(str(item.get("artifact_hash", "")).lower()):
                errors.append(f"{req_id} must declare a primary artifact_hash")
        for req_id in P10_CLOSEOUT_REQUIREMENT_IDS:
            item = by_id.get(req_id, {})
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P10 post-acceptance closeout")
            if item.get("verification_scope") != P10_CLOSEOUT_SCOPE:
                errors.append(f"{req_id} must declare the no-hardware P10 closeout scope")
        for req_id in P10_POST_ACCEPTANCE_ANALYSIS_REQUIREMENT_IDS:
            item = by_id.get(req_id, {})
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after the offline P10 metric audit")
            if item.get("verification_scope") != P10_ANALYSIS_SCOPE:
                errors.append(f"{req_id} must declare the no-hardware P10 analysis scope")
    if P10_1_OFFLINE_REQUIREMENT_IDS.issubset(by_id):
        for req_id in P10_1_OFFLINE_REQUIREMENT_IDS:
            item = by_id[req_id]
            if item.get("status") != "PASS":
                errors.append(f"{req_id} must be PASS after P10.1 offline closure")
            if item.get("verification_scope") != P10_1_OFFLINE_SCOPE:
                errors.append(f"{req_id} must declare the exact P10.1 offline scope")
            if not item.get("hardware_followup"):
                errors.append(f"{req_id} must retain direct-hardware follow-up")
            if not SHA256_RE.fullmatch(str(item.get("artifact_hash", "")).lower()):
                errors.append(f"{req_id} must declare a primary artifact_hash")
    for req_id in P10_1_EXTENDED_MODEL_REQUIREMENT_IDS:
        item = by_id.get(req_id, {})
        bindings = {
            record.get("path")
            for record in item.get("artifact_hashes", [])
            if isinstance(record, dict)
        }
        if "evidence/generated/p10_1_performance_model.json" not in bindings:
            errors.append(f"{req_id} must bind the P10.1 performance model extension")
    for req_id in P10_1_PENDING_HARDWARE_REQUIREMENT_IDS:
        item = by_id.get(req_id, {})
        if item.get("status") != "PENDING":
            errors.append(f"{req_id} must remain PENDING until a new authorized run")
    for req_id in P11_READINESS_REQUIREMENT_IDS:
        item = by_id.get(req_id, {})
        if item.get("status") != "PENDING":
            errors.append(f"{req_id} must remain PENDING while P11 is not ready")
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
        f"P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION: {state['p9_status']}",
        f"P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET: {state['p10_status']}",
        f"P10_1_OFFLINE_STATUS: {state['p10_1_offline_status']}",
        f"P10_1_HARDWARE_STATUS: {state['p10_1_hardware_status']}",
        f"P11_OFFICIAL_STAGE_STATUS: {state['p11_status']}",
        f"P11_HARDWARE_READY: {str(state['p11_hardware_ready']).lower()}",
        f"CURRENT_PROGRAM_STAGE: {state['current_program_stage']}",
        f"CURRENT_RUN_HARDWARE_AUTHORIZATION: {str(state['current_run_hardware_authorization']).lower()}",
        f"LAST_HARDWARE_AUTHORIZATION_CONSUMED: {str(state.get('last_hardware_authorization_consumed', False)).lower()}",
        f"LAST_HARDWARE_STAGE: {state['last_hardware_stage']}",
        f"LAST_HARDWARE_RUN_ID: {state['last_hardware_run_id']}",
        f"LAST_SHUTDOWN_FIXED: {state['last_shutdown_fixed']}",
        f"LAST_SHUTDOWN_ROTATING: {state['last_shutdown_rotating']}",
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

    if isinstance(state.get("p8d_acceptance"), dict):
        p8d = state["p8d_acceptance"]
        lines += [
            "",
            "## P8D portable data-plane acceptance",
            "",
            f"- Status: `{p8d['status']}` (offline RTL/software/model scope only)",
            f"- Source commit: `{p8d['source_commit']}`",
            f"- Evidence: `{p8d['evidence_path']}`",
            f"- 16 Mbit/s architecture model: `{p8d['architecture_16mbps_feasibility']}`",
            f"- 19.2 Mbit/s stretch model: `{p8d['stretch_19p2mbps_feasibility']}`",
            "- Real AXI DMA, DDR/cache coherency, Z7020 hardware, rotation, and final timing/CDC remain pending.",
        ]

    if isinstance(state.get("p9_post_checkpoint_closeout"), dict):
        closeout = state["p9_post_checkpoint_closeout"]
        lane1 = state["ab_l1_status"]
        architecture = state["architecture_status"]
        p9 = state["p9_acceptance"]
        lines += [
            "",
            "## P9 post-checkpoint closeout",
            "",
            f"- P9 run: `{p9['run_id']}`",
            f"- P9 source commit: `{p9['source_commit']}`",
            f"- P9 annotated tag: `{p9['evidence_checkpoint_tag']}`",
            f"- P9 evidence checkpoint: `{p9['evidence_checkpoint_commit']}`",
            f"- Closeout evidence: `{closeout['evidence_path']}`",
            f"- Current-run authorization: `{str(state['current_run_hardware_authorization']).lower()}`",
            f"- Last authorization consumed: `{str(state['last_hardware_authorization_consumed']).lower()}`",
            f"- External TFDU duty measurement: `{architecture['external_tfdu_duty_measurement']}`",
            f"- Physical GLOBAL_PERMIT implementation: `{architecture['global_permit_physical_implementation']}`",
            f"- AB_L1 legacy/current P9 stationary: `{lane1['legacy_status']}` / `{lane1['current_p9_stationary_status']}`",
            (
                "- This P9 closeout record is historical; P10 later completed its explicitly scoped "
                "stationary AX7020 two-lane run."
                if state.get("p10_status") == "PASS"
                else "- P10 remains not started; Z7020, rotation, and final-product hardware acceptance remain pending."
            ),
        ]
    if isinstance(state.get("p10_acceptance"), dict):
        p10 = state["p10_acceptance"]
        lines += [
            "",
            "## P10 scoped AX7020 dual-node hardware acceptance",
            "",
            f"- Status: `{p10['status']}` (`{p10['scope']}` only)",
            f"- Formal run: `{p10['run_id']}`",
            f"- Hardware source commit: `{p10['source_commit']}`",
            f"- Formal evidence freeze commit: `{p10['formal_evidence_freeze_commit']}`",
            f"- Evidence: `{p10['evidence_path']}`",
            f"- Evidence SHA256: `{p10['evidence_sha256']}`",
            f"- Evidence manifest: `{p10['evidence_manifest_path']}`",
            f"- Fixed / rotating-role IDs: `{p10['fixed_board_id']}` / `{p10['rotating_board_id']}`",
            f"- Shutdown fixed / rotating: `{p10['shutdown_fixed']}` / `{p10['shutdown_rotating']}`",
            "- Scope: stationary, two independent AX7020 endpoints, two optical lanes, no Ethernet, no motion.",
            "- Ethernet, SPI, physical GLOBAL_PERMIT D17, external TFDU duty measurement, handover, 8x32, 600 rpm, and product-final acceptance remain pending.",
        ]
    if isinstance(state.get("p10_post_acceptance_closeout"), dict):
        closeout = state["p10_post_acceptance_closeout"]
        audit = state["p10_goodput_measurement_audit"]
        p11 = state["p11_readiness"]
        lines += [
            "",
            "## P10 post-acceptance closeout and analysis",
            "",
            f"- Closeout status: `{closeout['status']}`",
            f"- Closeout evidence: `{closeout['evidence_path']}`",
            f"- Remote checkpoint evidence: `{closeout['remote_push_path']}`",
            f"- Current-run authorization: `{str(state['current_run_hardware_authorization']).lower()}`",
            f"- Last authorization consumed: `{str(state['last_hardware_authorization_consumed']).lower()}`",
            f"- Goodput audit: `{audit['status']}` (`{audit['outcome']}`)",
            f"- Current final goodput eligible for 8-lane projection: `{str(audit['eligible_for_final_8lane_projection']).lower()}`",
            f"- P11 official stage: `{p11['official_stage_status']}`",
            f"- P11 hardware ready: `{str(p11['hardware_ready']).lower()}`",
            "- P10 remains a scoped PASS; the post-acceptance metric audit does not promote or revoke hardware scope.",
        ]
    if isinstance(state.get("p10_1_performance_and_observability"), dict):
        p10_1 = state["p10_1_performance_and_observability"]
        lines += [
            "",
            "## P10.1 extended offline performance and streaming readiness",
            "",
            f"- Offline status: `{state['p10_1_offline_status']}` (`{p10_1.get('verification_scope')}` only)",
            f"- Evidence: `{p10_1.get('evidence_path')}`",
            f"- Modeled application goodput: `{p10_1.get('modeled_application_goodput_bps')} bit/s`",
            f"- 4.0 Mbit/s scale-equivalent feasibility: `{p10_1.get('scale_equivalent_4mbps_feasibility')}`",
            f"- Real hardware goodput: `{p10_1.get('real_hardware_goodput_status')}`",
            f"- Offline sub-scope hardware actions executed: `{str(p10_1.get('hardware_actions_executed')).lower()}`",
            f"- P11 official stage / hardware ready: `{state['p11_status']}` / `{str(state['p11_hardware_ready']).lower()}`",
            "- This offline PASS remains limited to feasibility, routed implementation, software, simulation, and dry-run evidence; any real AX7020 result is recorded separately below.",
        ]
    if isinstance(state.get("p10_1_hardware_campaign"), dict):
        campaign = state["p10_1_hardware_campaign"]
        lines += [
            "",
            "## P10.1 scoped AX7020 hardware performance campaign",
            "",
            f"- Status: `{campaign.get('status')}`",
            f"- Run ID: `{campaign.get('run_id', 'NOT_RUN')}`",
            f"- Source commit: `{campaign.get('source_commit', 'NOT_FROZEN')}`",
            f"- Fixed / rotating-role IDs: `{campaign.get('fixed_board_id')}` / `{campaign.get('rotating_board_id')}`",
            f"- Final evidence: `{campaign.get('final_evidence_path', 'PENDING')}`",
            f"- F→R / R→F application goodput: `{campaign.get('f_to_r_application_goodput_bps', 'PENDING')}` / `{campaign.get('r_to_f_application_goodput_bps', 'PENDING')}` bit/s",
            f"- Shutdown fixed / rotating: `{campaign.get('shutdown_fixed', 'PENDING')}` / `{campaign.get('shutdown_rotating', 'PENDING')}`",
            f"- Hardware actions / network / movement: `{str(campaign.get('hardware_actions_executed', False)).lower()}` / `{str(campaign.get('network_used', False)).lower()}` / `{str(campaign.get('hardware_movement', False)).lower()}`",
            "- Scope remains stationary dual AX7020, two lanes, no Ethernet and no movement; it does not promote P11, 8x32, 600 rpm, physical GLOBAL_PERMIT, external duty, or product-final acceptance.",
        ]
    lines += [
        "",
        "`AB_L1_BAD_DIR` remains immutable history. The later lane1 evidence resolves usability only for the explicitly named stationary Z7010 two-lane scope and is not extrapolated to future hardware.",
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
        "P8A, P8B, and completed P8C/P8D portable-function gates were executed with `NO_HARDWARE=1`; they do not create or promote hardware acceptance scope.",
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
