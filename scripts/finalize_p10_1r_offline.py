#!/usr/bin/env python3
"""Freeze the P10.1R no-hardware remediation checkpoint.

This finalizer deliberately stops before creating a current-run hardware
authorization.  It validates the immutable source-bound artifacts and offline
evidence, updates only offline-capable requirements, and leaves every direct
hardware acceptance requirement PENDING.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATE = ROOT / "config/project_state.json"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
PROJECT_STATUS = ROOT / "PROJECT_STATUS.md"

SOURCE_COMMIT = ""
FAILURE_TAG = "p10.1-hardware-performance-fail-20260801"
FAILURE_TAG_OBJECT = "6359cb1113884365a01f1a6a2b1d84d17a6b8f2d"
FAILURE_TAG_COMMIT = "991cc8a6cc5fd656178f9a3ddd9bb7c2f9c84151"
GOAL_SHA256 = "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
DETERMINISTIC_TIMESTAMP = "2026-08-02T00:00:00Z"

GOAL = ROOT / "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
PIPELINE_CONFIG = ROOT / "config/performance/p10_1_pipeline.yaml"
RUNTIME_CONFIG = ROOT / "config/performance/p10_1r_hardware_runtime.yaml"
ADMISSION_CONFIG = ROOT / "config/tfdu_rx_admission.yaml"
MEASUREMENT_CONTRACT = ROOT / "docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md"
GUARD_SELECTION = GENERATED / "p10_1r_echo_guard_selection.json"
P8D_PRECONDITION_FAILURE = (
    GENERATED / "p10_1r_p8d_detached_precondition_failure/summary.json"
)

INPUTS = {
    "repo_intake": GENERATED / "p10_1r_repo_intake.json",
    "failure_baseline": GENERATED / "p10_1r_failure_baseline_summary.json",
    "rx_admission_design": GENERATED / "p10_1r_rx_admission_design.json",
    "self_echo_model": GENERATED / "p10_1r_self_echo_model.json",
    "ack_pipeline_model": GENERATED / "p10_1r_ack_pipeline_model.json",
    "boundary_ack_remediation": (
        GENERATED / "p10_1r_boundary_ack_skew_remediation.json"
    ),
    "focused_xsim": GENERATED / "p10_1r_xsim/summary.json",
    "dual_endpoint_regression": (
        GENERATED / "p10_1r_dual_endpoint_regression/summary.json"
    ),
    "functional_build": GENERATED / "p10_1r_functional_build_summary.json",
    "shutdown_build": GENERATED / "p10_1r_shutdown_build_summary.json",
    "runtime_build": GENERATED / "p10_1r_ps_runtime_build_summary.json",
    "full_offline_gate": (
        GENERATED / "p10_1r_full_offline_regression/summary.json"
    ),
    "p8c_regression": (
        GENERATED / "p10_1r_full_offline_regression/p8c/p8c_final_summary.json"
    ),
    "p8d_regression": (
        GENERATED / "p10_1r_full_offline_regression/p8d/p8d_final_summary.json"
    ),
}

OFFLINE_REQUIREMENTS = {
    "P10_1R-ECHO-001": {
        "test_id": "P10_1R_FOCUSED_XSIM",
        "scope": "P10_1R_OFFLINE_RTL_IMPLEMENTATION_PASS_HARDWARE_PENDING",
        "evidence": ("focused_xsim", "functional_build"),
        "followup": (
            "Direct four-module admission counters remain pending under a new "
            "artifact-bound current-run authorization."
        ),
    },
    "P10_1R-ECHO-003": {
        "test_id": "P10_1R_FOCUSED_XSIM",
        "scope": "P10_1R_OFFLINE_OBSERVABILITY_PASS_HARDWARE_PENDING",
        "evidence": ("focused_xsim", "functional_build"),
        "followup": (
            "Hardware must populate raw echo-tail maximum, p99, and p99.9; no "
            "hardware count is inferred from the model."
        ),
    },
    "P10_1R-ECHO-004": {
        "test_id": "P10_1R_FOCUSED_XSIM",
        "scope": "P10_1R_OFFLINE_RTL_IMPLEMENTATION_PASS_HARDWARE_PENDING",
        "evidence": ("focused_xsim", "dual_endpoint_regression"),
        "followup": "The direct 4x4 receive-admission matrix remains pending.",
    },
    "P10_1R-ACK-001": {
        "test_id": "P10_1R_ACK_PIPELINE_PERFORMANCE_MODEL",
        "scope": "P10_1R_OFFLINE_PROTOCOL_PASS_HARDWARE_PENDING",
        "evidence": ("ack_pipeline_model", "focused_xsim", "functional_build"),
        "followup": (
            "Direct ACK-window telemetry and final hardware tuning remain pending."
        ),
    },
    "P10_1R-ACK-002": {
        "test_id": "P10_1R_FOCUSED_XSIM",
        "scope": "P10_1R_OFFLINE_PROTOCOL_PASS_HARDWARE_PENDING",
        "evidence": ("focused_xsim", "runtime_build"),
        "followup": (
            "Direct inter-object timing must confirm that object boundaries do "
            "not create a hidden hardware turnaround."
        ),
    },
    "P10_1R-ACK-003": {
        "test_id": "P10_1R_ACK_PIPELINE_PERFORMANCE_MODEL",
        "scope": "P10_1R_OFFLINE_PIPELINE_PASS_HARDWARE_PENDING",
        "evidence": ("ack_pipeline_model", "focused_xsim", "runtime_build"),
        "followup": (
            "Direct descriptor, completion, and occupancy telemetry remain pending."
        ),
    },
    "P10_1R-ACK-004": {
        "test_id": "P10_1R-DUAL-LANE-BOUNDARY-ACK-SKEW-REMEDIATION",
        "scope": "P10_1R_OFFLINE_BOUNDARY_ACK_PASS_HARDWARE_PENDING",
        "evidence": (
            "boundary_ack_remediation",
            "focused_xsim",
            "dual_endpoint_regression",
            "functional_build",
        ),
        "followup": (
            "Direct dual-lane ACK hardware telemetry must confirm zero avoidable "
            "turnaround timeout under the frozen artifact bundle."
        ),
    },
    "P10_1R-HOST-001": {
        "test_id": "P10_1R_ACK_PIPELINE_PERFORMANCE_MODEL",
        "scope": "P10_1R_OFFLINE_SOFTWARE_PASS_HARDWARE_PENDING",
        "evidence": ("ack_pipeline_model", "runtime_build"),
        "followup": (
            "The formal hardware window must report host command counts and "
            "segments per command."
        ),
    },
}

HARDWARE_REQUIREMENTS = (
    "P10_1R-ECHO-002",
    "P10_1R-ECHO-005",
    "P10_1R-PERF-001",
    "P10_1R-PERF-002",
    "P10_1R-STREAM-001",
    "P10_1R-STREAM-002",
    "P10_1R-SOAK-001",
)

DEVICE_CAPACITY = {
    "lut": 53200,
    "ff": 106400,
    "bram36_equivalent": 140.0,
    "dsp": 220,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def record(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "bytes": path.stat().st_size, "sha256": sha256(path)}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel(path)} must contain a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_pair(stem: str, title: str, payload: dict[str, Any], body: list[str]) -> None:
    json_path = GENERATED / f"{stem}.json"
    md_path = GENERATED / f"{stem}.md"
    write_json(json_path, payload)
    lines = [
        f"# {title}",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Test ID: `{payload.get('test_id')}`",
        "- Hardware actions executed: `false`",
        "- Current-run hardware authorization: `false`",
        "",
        *body,
    ]
    errors = payload.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in errors)
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, capture_output=True, check=check
    )


def run_check(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        errors="replace",
        env={
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
    )
    return {
        "command": subprocess.list2cmdline(command),
        "return_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def is_read_only(path: Path) -> bool:
    info = path.stat()
    attributes = getattr(info, "st_file_attributes", None)
    if attributes is not None and hasattr(stat, "FILE_ATTRIBUTE_READONLY"):
        return bool(attributes & stat.FILE_ATTRIBUTE_READONLY)
    return not bool(info.st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def verify_artifact(
    item: dict[str, Any], label: str, errors: list[str]
) -> dict[str, Any] | None:
    path_value = item.get("path")
    expected = str(item.get("sha256", "")).lower()
    if not isinstance(path_value, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        errors.append(f"{label}: malformed artifact record")
        return None
    path = (ROOT / path_value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{label}: path escapes repository")
        return None
    if not path.is_file():
        errors.append(f"{label}: missing {path_value}")
        return None
    actual = sha256(path)
    read_only = is_read_only(path)
    if actual != expected:
        errors.append(f"{label}: SHA256 mismatch")
    if expected not in path.parts:
        errors.append(f"{label}: digest absent from content-addressed path")
    if SOURCE_COMMIT not in path.parts:
        errors.append(f"{label}: source commit absent from artifact path")
    if item.get("read_only") is not True or not read_only:
        errors.append(f"{label}: artifact is not read-only")
    return {
        "path": rel(path),
        "bytes": path.stat().st_size,
        "sha256": actual,
        "read_only": read_only,
        "built_source_commit": SOURCE_COMMIT,
    }


def parse_resources(path: Path, limits: dict[str, float]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"^\|\s*p10_ps_system_wrapper\s*\|\s*\(top\)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        text,
        re.MULTILINE,
    )
    if match is None:
        return {"status": "FAIL", "error": "top utilization row not found"}
    total_lut, _, _, _, ff, ramb36, ramb18, dsp = (
        int(value) for value in match.groups()
    )
    used = {
        "lut": total_lut,
        "ff": ff,
        "bram36_equivalent": ramb36 + ramb18 / 2.0,
        "dsp": dsp,
    }
    percent = {
        name: used[name] / DEVICE_CAPACITY[name] * 100.0 for name in used
    }
    return {
        "status": "PASS",
        "used": used,
        "capacity": DEVICE_CAPACITY,
        "percent": percent,
        "limits_percent": limits,
        "within_limits": all(percent[name] <= limits[name] for name in limits),
        "report": record(path),
    }


def update_state(artifact_freeze: Path, artifacts: dict[str, Any]) -> None:
    state = load_json(STATE)
    state["current_program_stage"] = (
        "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION"
    )
    state["current_run_hardware_authorization"] = False
    state["p10_1r_status"] = "OFFLINE_READY_HARDWARE_PENDING"
    state["two_lane_speed_stability"] = "PENDING_DIRECT_HARDWARE_REACCEPTANCE"
    state["last_verified_commit"] = SOURCE_COMMIT
    state["p11_status"] = "NOT_STARTED"
    state["p11_hardware_ready"] = False
    state["p10_1r_remediation"] = {
        "status": "OFFLINE_READY_HARDWARE_PENDING",
        "base_failure_tag": FAILURE_TAG,
        "source_commit": SOURCE_COMMIT,
        "goal_path": rel(GOAL),
        "goal_sha256": GOAL_SHA256,
        "source_artifact_freeze": "PASS",
        "artifact_freeze_path": rel(artifact_freeze),
        "artifact_freeze_sha256": sha256(artifact_freeze),
        "artifacts": artifacts,
        "candidate_guard_cycles": {
            "F0": 4096,
            "F1": 4096,
            "R0": 4096,
            "R1": 4096,
        },
        "selected_guard_cycles": {
            "F0": 4096,
            "F1": 4096,
            "R0": 4096,
            "R1": 4096,
        },
        "candidate_guard_hardware_measured": True,
        "guard_selection": record(GUARD_SELECTION),
        "current_run_hardware_authorization": False,
        "new_artifact_hardware_validation": "PENDING_NEW_CURRENT_RUN_AUTHORIZATION",
        "hardware_actions_executed": False,
        "network_used": False,
        "p11_started": False,
    }
    STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def update_requirements(payloads: dict[str, dict[str, Any]]) -> None:
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("requirements"), list):
        raise ValueError("config/project_requirements.yaml has invalid structure")
    by_id = {
        item.get("requirement_id"): item
        for item in document["requirements"]
        if isinstance(item, dict)
    }
    for requirement_id, spec in OFFLINE_REQUIREMENTS.items():
        item = by_id.get(requirement_id)
        if not isinstance(item, dict):
            raise ValueError(f"missing requirement {requirement_id}")
        bindings = [record(INPUTS[name]) for name in spec["evidence"]]
        item["status"] = "PASS"
        item["verification_scope"] = spec["scope"]
        item["verification_stage"] = (
            "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_OFFLINE"
        )
        item["test_id"] = spec["test_id"]
        item["evidence_path"] = bindings[0]["path"]
        item["artifact_hash"] = bindings[0]["sha256"]
        item["artifact_hashes"] = [
            {"path": binding["path"], "sha256": binding["sha256"]}
            for binding in bindings
        ]
        item["hardware_followup"] = spec["followup"]
    for requirement_id in HARDWARE_REQUIREMENTS:
        item = by_id.get(requirement_id)
        if not isinstance(item, dict):
            raise ValueError(f"missing requirement {requirement_id}")
        item["status"] = "PENDING"
        item["test_id"] = None
        item["artifact_hashes"] = []
        item.pop("artifact_hash", None)

    mutable_hashes = {
        rel(STATE): sha256(STATE),
        rel(PROJECT_STATUS): sha256(PROJECT_STATUS),
    }
    for item in document["requirements"]:
        if not isinstance(item, dict):
            continue
        bindings = item.get("artifact_hashes")
        if not isinstance(bindings, list):
            continue
        for binding in bindings:
            if isinstance(binding, dict) and binding.get("path") in mutable_hashes:
                binding["sha256"] = mutable_hashes[binding["path"]]
        if (
            bindings
            and isinstance(bindings[0], dict)
            and bindings[0].get("path") in mutable_hashes
        ):
            item["artifact_hash"] = bindings[0]["sha256"]

    REQUIREMENTS.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    global SOURCE_COMMIT
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []

    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    branch = git("branch", "--show-current").stdout.strip()
    head = git("rev-parse", "HEAD").stdout.strip()
    try:
        source_candidate = str(
            load_json(INPUTS["functional_build"]).get("source_commit", "")
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        source_candidate = ""
        errors.append(f"cannot determine immutable artifact source: {exc}")
    if not re.fullmatch(r"[0-9a-f]{40}", source_candidate):
        errors.append("functional-build artifact source is not a full Git commit")
        SOURCE_COMMIT = head
    else:
        SOURCE_COMMIT = source_candidate
    source_is_ancestor = (
        git("merge-base", "--is-ancestor", SOURCE_COMMIT, "HEAD", check=False).returncode
        == 0
    )
    failure_target = git("rev-parse", f"{FAILURE_TAG}^{{}}", check=False).stdout.strip()
    failure_object = git("rev-parse", FAILURE_TAG, check=False).stdout.strip()
    failure_type = git("cat-file", "-t", FAILURE_TAG, check=False).stdout.strip()
    if branch != "p10.1r/2lane-speed-stability-remediation":
        errors.append(f"unexpected branch {branch}")
    if not source_is_ancestor:
        errors.append("immutable P10.1R source commit is not an ancestor of HEAD")
    if (
        failure_target != FAILURE_TAG_COMMIT
        or failure_object != FAILURE_TAG_OBJECT
        or failure_type != "tag"
    ):
        errors.append("failure baseline annotated tag target changed")
    if not GOAL.is_file() or sha256(GOAL) != GOAL_SHA256:
        errors.append("P10.1R Goal SHA256 mismatch")

    guard_selection: dict[str, Any] = {}
    try:
        guard_selection = load_json(GUARD_SELECTION)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"invalid guard-selection evidence: {exc}")
    if guard_selection:
        if guard_selection.get("status") != "PASS":
            errors.append("guard-selection status is not PASS")
        if guard_selection.get("selected_final_guard_cycles") != 4096:
            errors.append("guard-selection final value mismatch")
        if guard_selection.get("maximum_observed_post_tx_echo_tail_cycles") != 0:
            errors.append("guard-selection measured maximum mismatch")
        if guard_selection.get("raw_same_module_echo_count") != 4000:
            errors.append("guard-selection raw echo count mismatch")
        if guard_selection.get("violations", {}).get("accepted_same_module_frames") != 0:
            errors.append("guard-selection accepted same-module frame mismatch")
        selection_shutdown = guard_selection.get("shutdown", {})
        if not (
            selection_shutdown.get("SHUTDOWN_FIXED") == "PASS"
            and selection_shutdown.get("SHUTDOWN_ROTATING") == "PASS"
            and selection_shutdown.get("all_attempts_confirmed") is True
        ):
            errors.append("guard-selection shutdown evidence mismatch")

    payloads: dict[str, dict[str, Any]] = {}
    for name, path in INPUTS.items():
        if not path.is_file():
            errors.append(f"missing input evidence {rel(path)}")
            continue
        try:
            payload = load_json(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid input evidence {rel(path)}: {exc}")
            continue
        payloads[name] = payload
        if payload.get("status") not in {"PASS", "PASS_WITH_PENDING_TOOL"}:
            errors.append(f"{name}: status is not PASS")
        if payload.get("source_commit") != SOURCE_COMMIT:
            errors.append(f"{name}: source commit mismatch")
        if payload.get("hardware_actions_executed") not in {False, None}:
            errors.append(f"{name}: claims hardware actions")
        if payload.get("current_run_hardware_authorization") not in {False, None}:
            errors.append(f"{name}: claims current hardware authorization")

    diagnostic_payload: dict[str, Any] = {}
    if not P8D_PRECONDITION_FAILURE.is_file():
        errors.append(
            f"missing diagnostic evidence {rel(P8D_PRECONDITION_FAILURE)}"
        )
    else:
        try:
            diagnostic_payload = load_json(P8D_PRECONDITION_FAILURE)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid P8D precondition failure evidence: {exc}")
        if diagnostic_payload:
            if diagnostic_payload.get("status") != "RECORDED_PRECONDITION_FAILURE":
                errors.append("P8D precondition failure status mismatch")
            diagnostic_source = str(diagnostic_payload.get("source_commit", ""))
            diagnostic_source_is_ancestor = (
                bool(re.fullmatch(r"[0-9a-f]{40}", diagnostic_source))
                and git(
                    "merge-base",
                    "--is-ancestor",
                    diagnostic_source,
                    SOURCE_COMMIT,
                    check=False,
                ).returncode
                == 0
            )
            if not diagnostic_source_is_ancestor:
                errors.append(
                    "P8D precondition failure source is not an ancestor of "
                    "the final artifact source"
                )
            if diagnostic_payload.get("hardware_actions_executed") is not False:
                errors.append("P8D precondition failure claims hardware actions")
            if diagnostic_payload.get("current_run_hardware_authorization") is not False:
                errors.append("P8D precondition failure claims hardware authorization")
            diagnostic_records = list(diagnostic_payload.get("raw_evidence", []))
            corrected = diagnostic_payload.get("corrected_rerun", {})
            diagnostic_records.extend(
                record
                for record in (
                    corrected.get("final_summary"),
                    corrected.get("baseline_checks"),
                )
                if isinstance(record, dict)
            )
            for diagnostic_record in diagnostic_records:
                diagnostic_record_path = diagnostic_record.get("path", "")
                diagnostic_path = ROOT / diagnostic_record_path
                if (
                    diagnostic_source
                    and diagnostic_source != SOURCE_COMMIT
                    and diagnostic_record_path.startswith(
                        "evidence/generated/p10_1r_full_offline_regression/"
                    )
                ):
                    historical_root = (
                        "evidence/generated/p10_1r_full_offline_regression_"
                        f"{diagnostic_source[:8]}/"
                    )
                    historical_path = ROOT / diagnostic_record_path.replace(
                        "evidence/generated/p10_1r_full_offline_regression/",
                        historical_root,
                        1,
                    )
                    if historical_path.is_file():
                        diagnostic_path = historical_path
                if not diagnostic_path.is_file():
                    errors.append(
                        "missing P8D diagnostic artifact "
                        f"{diagnostic_record.get('path')}"
                    )
                    continue
                if diagnostic_path.stat().st_size != diagnostic_record.get("bytes"):
                    errors.append(
                        "P8D diagnostic artifact byte count mismatch: "
                        f"{diagnostic_record.get('path')}"
                    )
                if sha256(diagnostic_path) != diagnostic_record.get("sha256"):
                    errors.append(
                        "P8D diagnostic artifact SHA256 mismatch: "
                        f"{diagnostic_record.get('path')}"
                    )

    functional = payloads.get("functional_build", {})
    shutdown = payloads.get("shutdown_build", {})
    runtime = payloads.get("runtime_build", {})
    pipeline = yaml.safe_load(PIPELINE_CONFIG.read_text(encoding="utf-8"))
    runtime_config = yaml.safe_load(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    admission = yaml.safe_load(ADMISSION_CONFIG.read_text(encoding="utf-8"))
    resource_cfg = pipeline.get("resource_limits", {})
    limits = {
        "lut": float(resource_cfg.get("lut_max_percent", 70)),
        "ff": float(resource_cfg.get("ff_max_percent", 70)),
        "bram36_equivalent": float(resource_cfg.get("bram_max_percent", 75)),
        "dsp": float(resource_cfg.get("dsp_max_percent", 50)),
    }

    frozen_by_role: dict[str, dict[str, Any]] = {}
    role_payloads: dict[str, dict[str, Any]] = {}
    for role in ("fixed", "rotating"):
        role_errors: list[str] = []
        build = next(
            (item for item in functional.get("roles", []) if item.get("role") == role),
            {},
        )
        runtime_role = next(
            (item for item in runtime.get("roles", []) if item.get("role") == role),
            {},
        )
        shutdown_role = next(
            (item for item in shutdown.get("roles", []) if item.get("role") == role),
            {},
        )
        artifacts: dict[str, Any] = {}
        for kind in ("bitstream", "xsa"):
            verified = verify_artifact(
                build.get("artifacts", {}).get(kind, {}),
                f"{role} {kind}",
                role_errors,
            )
            if verified:
                artifacts[kind] = verified
        for kind in ("bsp", "elf"):
            verified = verify_artifact(
                runtime_role.get("artifacts", {}).get(kind, {}),
                f"{role} {kind}",
                role_errors,
            )
            if verified:
                artifacts[kind] = verified
        verified_shutdown = verify_artifact(
            shutdown_role.get("artifact", {}),
            f"{role} shutdown bitstream",
            role_errors,
        )
        if verified_shutdown:
            artifacts["shutdown_bitstream"] = verified_shutdown

        markers = build.get("markers", {})
        timing = {
            "wns_ns": float(markers.get("P10_WNS_NS", -1)),
            "whs_ns": float(markers.get("P10_WHS_NS", -1)),
            "tns_ns": float(markers.get("P10_TNS_NS", -1)),
        }
        if not (
            timing["wns_ns"] >= 0
            and timing["whs_ns"] >= 0
            and timing["tns_ns"] == 0
            and markers.get("P10_DRC_CRITICAL_COUNT") == "0"
            and markers.get("P10_DRC_ERROR_COUNT") == "0"
            and markers.get("P10_CDC_CRITICAL_COUNT") == "0"
            and markers.get("P10_REQP_1839_COUNT") == "0"
            and markers.get("P10_METHODOLOGY_CRITICAL_COUNT") == "0"
            and markers.get("P10_ETHERNET_ENABLED") == "false"
        ):
            role_errors.append("timing/DRC/CDC/REQP/methodology hard gate failed")
        utilization_path = (
            GENERATED / f"vivado/p10_1r/{role}/post_route_utilization.rpt"
        )
        resources = (
            parse_resources(utilization_path, limits)
            if utilization_path.is_file()
            else {"status": "FAIL", "error": "utilization report missing"}
        )
        if resources.get("status") != "PASS" or not resources.get("within_limits"):
            role_errors.append("resource hard gate failed")
        if build.get("status") != "PASS" or runtime_role.get("status") != "PASS":
            role_errors.append("functional or runtime build status failed")
        if shutdown_role.get("status") != "PASS":
            role_errors.append("shutdown build status failed")
        errors.extend(f"{role}: {item}" for item in role_errors)
        frozen_by_role[role] = artifacts
        role_payloads[role] = {
            "schema_version": 1,
            "test_id": f"P10_1R-{role.upper()}-IMMUTABLE-OFFLINE-BUILD",
            "generated_at_utc": DETERMINISTIC_TIMESTAMP,
            "status": "PASS" if not role_errors else "FAIL",
            "source_commit": SOURCE_COMMIT,
            "profile": build.get("profile"),
            "part": functional.get("part"),
            "no_hardware": True,
            "hardware_actions_executed": False,
            "current_run_hardware_authorization": False,
            "network_used": False,
            "timing": timing,
            "implementation_markers": markers,
            "resources": resources,
            "artifacts": artifacts,
            "errors": role_errors,
        }
        write_pair(
            f"p10_1r_{role}_build",
            f"P10.1R {role} immutable offline build",
            role_payloads[role],
            [
                f"The `{role}` functional bitstream, XSA, BSP, ELF, and shutdown "
                "bitstream are content-addressed and source-bound.",
                "",
                "This routed-build PASS has no hardware acceptance meaning.",
            ],
        )

    artifact_freeze_path = GENERATED / "p10_1r_artifact_freeze.json"
    artifact_inputs = [
        GOAL,
        PIPELINE_CONFIG,
        RUNTIME_CONFIG,
        ADMISSION_CONFIG,
        MEASUREMENT_CONTRACT,
        ROOT / "config/register_map/ir_axi_regs.yaml",
        ROOT / "config/register_map/generated/ir_regs_manifest.json",
        GUARD_SELECTION,
        ROOT / "board_profiles/ax7020_fixed_2lane/pinmap.csv",
        ROOT / "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
        ROOT / "board_profiles/ax7020_rotating_2lane/pinmap.csv",
        ROOT / "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
    ]
    artifact_freeze = {
        "schema_version": 1,
        "test_id": "P10_1R-IMMUTABLE-ARTIFACT-FREEZE",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS" if not errors else "FAIL",
        "source_commit": SOURCE_COMMIT,
        "branch": branch,
        "base_failure_tag": FAILURE_TAG,
        "base_failure_tag_object": FAILURE_TAG_OBJECT,
        "base_failure_tag_commit": FAILURE_TAG_COMMIT,
        "goal": record(GOAL) if GOAL.is_file() else None,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating_role": "AX7020-R/JTAG:210512180081",
        },
        "lane_mapping": {"lane0": "F0-R0", "lane1": "F1-R1"},
        "purpose": "FINAL_ACCEPTANCE",
        "acceptance_eligible": True,
        "allowed_hardware_stages": [
            "preflight",
            "echo_tail",
            "crosstalk",
            "phy_sanity",
            "ack_tuning",
            "performance",
            "streaming_64m",
            "formal_30min",
        ],
        "pl_build_identity": {
            "fixed": "0x50325346",
            "rotating": "0x50325352",
        },
        "guard_selection": record(GUARD_SELECTION),
        "old_hardware_results_inherited": False,
        "roles": frozen_by_role,
        "inputs": [record(path) for path in artifact_inputs if path.is_file()],
        "errors": errors.copy(),
    }
    write_pair(
        "p10_1r_artifact_freeze",
        "P10.1R immutable artifact freeze",
        artifact_freeze,
        [
            "All candidate and shutdown artifacts are frozen below "
            f"`artifacts/p10_1r/{SOURCE_COMMIT}/<sha256>/`.",
            "",
            "Any later RTL, protocol, XDC, firmware, or artifact hash change "
            "invalidates direct-hardware applicability and requires a new freeze.",
        ],
    )

    authorization = {
        "schema_version": 1,
        "test_id": "P10_1R-CURRENT-RUN-AUTHORIZATION-READINESS",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PENDING_NEW_AUTHORIZATION",
        "scope": "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION",
        "source_commit": SOURCE_COMMIT,
        "goal_sha256": GOAL_SHA256,
        "current_run_hardware_authorization": False,
        "authorization_granted": True,
        "user_authorization_available": True,
        "authorization_consumed": False,
        "hardware_actions_executed": False,
        "network_used": False,
        "maximum_formal_runtime_seconds": 1800,
        "maximum_lane_mask": "0x3",
        "board_binding": artifact_freeze["board_binding"],
        "artifact_freeze": record(artifact_freeze_path),
        "artifacts": frozen_by_role,
        "shutdown_strategy": {
            "shutdown_before_every_stage": True,
            "shutdown_on_error": True,
            "shutdown_on_timeout": True,
            "shutdown_on_ctrl_c": True,
            "shutdown_on_normal_exit": True,
            "both_role_shutdown_marker_required": True,
        },
        "prohibited": [
            "Ethernet",
            "movement_or_rotation",
            "rewiring_or_module_exchange",
            "lane_mask_above_0x3",
            "P11_or_8x32_or_600rpm_promotion",
        ],
        "next_required_user_action": (
            "NONE; create a fresh immutable run-bound authorization record "
            "from the user's existing P10.1R authorization"
        ),
    }
    write_pair(
        "p10_1r_authorization",
        "P10.1R current-run authorization readiness",
        authorization,
        [
            "The user authorization exists, but no run-bound authorization record "
            "has been created or consumed by this offline run.",
            "",
            "Hardware execution must not begin until a fresh immutable current-run "
            "record is bound to the exact frozen hashes in this record.",
        ],
    )

    if not errors:
        update_state(artifact_freeze_path, frozen_by_role)
        status_write = run_check(
            [sys.executable, "scripts/generate_project_status.py", "--write"]
        )
        if status_write["status"] != "PASS":
            errors.append("project status generation failed")
        else:
            update_requirements(payloads)
            trace_write = run_check(
                [
                    sys.executable,
                    "scripts/generate_requirement_traceability.py",
                    "--write",
                ]
            )
            if trace_write["status"] != "PASS":
                errors.append("requirement traceability generation failed")

    checks = [
        run_check([sys.executable, "scripts/generate_project_status.py", "--check"]),
        run_check(
            [sys.executable, "scripts/generate_requirement_traceability.py", "--check"]
        ),
        run_check([sys.executable, "scripts/check_p8a_consistency.py", "--check"]),
        run_check([sys.executable, "scripts/check_no_hardware_calls.py"]),
        run_check(["git", "diff", "--check"]),
    ]
    for check in checks:
        if check["status"] != "PASS":
            errors.append(f"consistency command failed: {check['command']}")

    consistency = {
        "schema_version": 1,
        "test_id": "P10_1R-EVIDENCE-CONSISTENCY",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "PASS" if not errors else "FAIL",
        "source_commit": SOURCE_COMMIT,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "input_evidence": {
            name: record(path) for name, path in INPUTS.items() if path.is_file()
        },
        "diagnostic_evidence": (
            record(P8D_PRECONDITION_FAILURE)
            if P8D_PRECONDITION_FAILURE.is_file()
            else None
        ),
        "role_build_evidence": {
            role: record(GENERATED / f"p10_1r_{role}_build.json")
            for role in ("fixed", "rotating")
        },
        "artifact_freeze": record(artifact_freeze_path),
        "authorization_readiness": record(GENERATED / "p10_1r_authorization.json"),
        "canonical_files": [
            record(REQUIREMENTS),
            record(STATE),
            record(PROJECT_STATUS),
            record(TRACEABILITY),
        ],
        "offline_requirements": {
            requirement_id: "PASS" for requirement_id in OFFLINE_REQUIREMENTS
        },
        "direct_hardware_requirements": {
            requirement_id: "PENDING" for requirement_id in HARDWARE_REQUIREMENTS
        },
        "checks": checks,
        "errors": errors.copy(),
    }
    write_pair(
        "p10_1r_evidence_consistency",
        "P10.1R offline evidence consistency",
        consistency,
        [
            "Offline-capable requirements are bound to exact source-generated "
            "evidence. Direct-hardware requirements remain PENDING.",
        ],
    )

    model = payloads.get("ack_pipeline_model", {})
    perf = model.get("performance", {})
    final = {
        "schema_version": 1,
        "test_id": "P10_1R-OFFLINE-FINAL-CHECKPOINT",
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "status": "OFFLINE_READY_HARDWARE_PENDING" if not errors else "FAIL",
        "branch": branch,
        "source_commit": SOURCE_COMMIT,
        "head_when_finalized": head,
        "base_failure_tag": FAILURE_TAG,
        "goal_sha256": GOAL_SHA256,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "hardware_movement": False,
        "wiring_changed": False,
        "candidate_guard_cycles": {
            "F0": 4096,
            "F1": 4096,
            "R0": 4096,
            "R1": 4096,
        },
        "selected_guard_cycles": {
            "F0": 4096,
            "F1": 4096,
            "R0": 4096,
            "R1": 4096,
        },
        "candidate_guard_hardware_measured": True,
        "guard_selection": record(GUARD_SELECTION),
        "modeled_goodput_bps": {
            "fixed_to_rotating": perf.get("modeled_fixed_to_rotating_bps"),
            "rotating_to_fixed": perf.get("modeled_rotating_to_fixed_bps"),
        },
        "measured_hardware_goodput_bps": {
            "fixed_to_rotating": "PENDING",
            "rotating_to_fixed": "PENDING",
        },
        "same_module_raw_echo_count": "PENDING_HARDWARE_MEASUREMENT",
        "same_module_blanked_frame_count": "PENDING_HARDWARE_MEASUREMENT",
        "same_module_accepted_data_count": "PENDING_HARDWARE_MEASUREMENT",
        "cross_lane_accepted_data_count": "PENDING_HARDWARE_MEASUREMENT",
        "frozen_protocol_defaults": {
            "endpoint_burst_frames": runtime_config["protocol"]["endpoint_burst_frames"],
            "ack_threshold": runtime_config["protocol"]["ack_threshold"],
            "ack_max_delay_cycles": runtime_config["protocol"]["ack_max_delay_cycles"],
            "boundary_ack_requires_cumulative_base_past_tag": runtime_config[
                "protocol"
            ]["boundary_ack_requires_cumulative_base_past_tag"],
            "boundary_ack_settle_fallback_cycles": runtime_config["protocol"][
                "boundary_ack_settle_fallback_cycles"
            ],
            "objects_in_flight": runtime_config["pipeline"][
                "minimum_concurrent_host_objects_or_equivalent"
            ],
        },
        "artifact_freeze": record(artifact_freeze_path),
        "authorization_readiness": record(GENERATED / "p10_1r_authorization.json"),
        "evidence_consistency": record(
            GENERATED / "p10_1r_evidence_consistency.json"
        ),
        "p10_functional_status_preserved": "PASS",
        "p10_1_failure_baseline_preserved": "FAIL",
        "p11_status": "NOT_STARTED",
        "direct_hardware_status": "PENDING_NEW_CURRENT_RUN_AUTHORIZATION",
        "old_hardware_results_applicable_to_new_artifacts": False,
        "p8d_detached_precondition_failure_preserved": (
            record(P8D_PRECONDITION_FAILURE)
            if P8D_PRECONDITION_FAILURE.is_file()
            else None
        ),
        "errors": errors.copy(),
    }
    write_pair(
        "p10_1r_offline_final_summary",
        "P10.1R offline remediation final checkpoint",
        final,
        [
            "The focused RTL/model regressions, exact-source complete offline "
            "regression, fixed/rotating routed builds, shutdown builds, BSPs, and "
            "ELFs are complete.",
            "",
            "This checkpoint is not a P10.1R hardware PASS. The calibration-selected "
            "guard is frozen, but rebuilt-artifact echo-tail verification, direct "
            "admission counters, 4.0 Mbit/s "
            "goodput, 5x64 MiB streaming, and the 1800-second run remain PENDING.",
        ],
    )

    print(f"P10_1R_OFFLINE_FINAL={final['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
