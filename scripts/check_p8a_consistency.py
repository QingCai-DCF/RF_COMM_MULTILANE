#!/usr/bin/env python3
"""Fail-closed P8A constraint, state, requirement, and evidence consistency gate."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from p8a_common import (
    RECONCILIATION_JSON_PATH,
    RECONCILIATION_MD_PATH,
    REQUIREMENTS_PATH,
    ROOT,
    STATE_PATH,
    STATUS_PATH,
    TRACEABILITY_PATH,
    dump_json,
    load_json,
    load_yaml,
    render_project_status,
    render_traceability,
    sha256_file,
    validate_requirements,
    validate_state,
)
from reconcile_p0_p7_evidence import build_reconciliation, render_reconciliation


SUMMARY_JSON = ROOT / "evidence/generated/p8a_consistency_summary.json"
SUMMARY_MD = ROOT / "evidence/generated/p8a_consistency_summary.md"


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def exact_file_errors(path: Path, expected: str, label: str) -> list[str]:
    if not path.is_file():
        return [f"{label} is missing"]
    if path.read_bytes() != expected.encode("utf-8"):
        return [f"{label} is stale or not generator-owned"]
    return []


def canonical_constraint_errors() -> list[str]:
    errors: list[str] = []
    canonical = ROOT / "PROJECT_CONSTRAINTS.txt"
    changelog = ROOT / "PROJECT_CONSTRAINTS_CHANGELOG.md"
    legacy = ROOT / "docs/legacy/项目约束(目标）.txt"
    pointer = ROOT / "PROJECT_CONSTRAINTS.md"
    archived_mirror = ROOT / "docs/historical/PROJECT_CONSTRAINTS_V3_READABLE_MIRROR.md"
    working_draft = ROOT / "PROJECT_CONSTRAINTS_WORKING_DRAFT.md"
    require(canonical.is_file(), "PROJECT_CONSTRAINTS.txt is missing", errors)
    canonical_text = canonical.read_text(encoding="utf-8", errors="strict") if canonical.is_file() else ""
    require("DOCUMENT_VERSION: 3.1" in canonical_text, "canonical document is not V3.1", errors)
    require("CANONICAL_PROJECT_CONSTRAINT: PROJECT_CONSTRAINTS.txt" in canonical_text, "canonical self-declaration missing", errors)
    require("LEGACY_PROJECT_CONSTRAINT_STATUS: SUPERSEDED" in canonical_text, "legacy superseded marker missing", errors)
    require("GLOBAL_PERMIT_ARCHITECTURE: SINGLE_ACTIVE_HIGH_PER_ENDPOINT" in canonical_text, "single GLOBAL_PERMIT marker missing", errors)
    require(legacy.is_file(), "superseded legacy constraint is missing", errors)
    require(not (ROOT / "项目约束(目标）.txt").exists(), "legacy constraint must not remain at repository root", errors)
    require(changelog.is_file(), "constraint changelog is missing", errors)
    changelog_text = changelog.read_text(encoding="utf-8", errors="strict") if changelog.is_file() else ""
    canonical_sha = sha256_file(canonical) if canonical.is_file() else ""
    require(f"NEW_PROJECT_CONSTRAINT_SHA256: {canonical_sha}" in changelog_text, "canonical constraint hash is absent from changelog", errors)
    require(pointer.is_file(), "PROJECT_CONSTRAINTS.md non-normative pointer is missing", errors)
    pointer_text = pointer.read_text(encoding="utf-8", errors="strict") if pointer.is_file() else ""
    require("DOCUMENT_STATUS: NON_NORMATIVE_POINTER" in pointer_text, "PROJECT_CONSTRAINTS.md must be non-normative", errors)
    require("PROJECT_CONSTRAINTS.txt" in pointer_text, "constraint pointer does not name the canonical file", errors)
    require(archived_mirror.is_file(), "superseded V3 Markdown mirror is missing", errors)
    archived_text = archived_mirror.read_text(encoding="utf-8", errors="strict") if archived_mirror.is_file() else ""
    require(
        "DOCUMENT_STATUS: HISTORICAL_SUPERSEDED_READING_MIRROR" in archived_text,
        "superseded V3 Markdown mirror lacks a historical status marker",
        errors,
    )
    require(
        "SUPERSEDED_BY: PROJECT_CONSTRAINTS.txt" in archived_text,
        "superseded V3 Markdown mirror does not point to the canonical constraint",
        errors,
    )
    require(working_draft.is_file(), "working draft is missing", errors)
    if working_draft.is_file():
        require("DOCUMENT_STATUS: NON_NORMATIVE_WORKING_DRAFT" in working_draft.read_text(encoding="utf-8"), "working draft lacks non-normative marker", errors)
    return errors


def status_surface_errors(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="strict")
    docs_status = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8", errors="strict")
    require("config/project_state.json" in readme and "PROJECT_STATUS.md" in readme, "README must point to canonical state/status", errors)
    for stale in (
        "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PENDING_HW",
        "HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PENDING_HW",
    ):
        require(stale not in readme, f"README contains stale status: {stale}", errors)
        require(stale not in docs_status, f"docs/PROJECT_STATUS.md contains stale status: {stale}", errors)
    require("NON_CANONICAL_POINTER" in docs_status, "docs/PROJECT_STATUS.md must be a non-canonical pointer", errors)
    require((ROOT / "docs/legacy_stage_rules/P3_P4_RULES.md").is_file(), "historical P3/P4 rules index is missing", errors)
    for rel in (
        "docs/P3_PRE_HW_ACCEPTANCE_PACKAGE.md",
        "docs/P4_PRE_HW_ACCEPTANCE_PACKAGE.md",
        "docs/P4_HARDWARE_ACCEPTANCE_PLAN.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8", errors="strict")
        require("HISTORICAL_STAGE_RULE" in text, f"{rel} is not marked historical", errors)
    require(state.get("p7_status") == "PASS", "canonical state no longer preserves P7 PASS", errors)
    return errors


def build_summary() -> dict[str, Any]:
    state = load_json(STATE_PATH)
    requirements = load_yaml(REQUIREMENTS_PATH)

    canonical_errors = canonical_constraint_errors()
    state_errors = validate_state(state, ROOT)
    state_errors.extend(exact_file_errors(STATUS_PATH, render_project_status(state), "PROJECT_STATUS.md"))
    state_errors.extend(status_surface_errors(state))

    requirement_errors = validate_requirements(requirements, ROOT)
    requirement_errors.extend(
        exact_file_errors(
            TRACEABILITY_PATH,
            render_traceability(requirements),
            "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
        )
    )

    expected_reconciliation = build_reconciliation(ROOT)
    reconciliation_errors = list(expected_reconciliation["errors"])
    reconciliation_errors.extend(
        exact_file_errors(
            RECONCILIATION_JSON_PATH,
            dump_json(expected_reconciliation),
            "P8A reconciliation JSON",
        )
    )
    reconciliation_errors.extend(
        exact_file_errors(
            RECONCILIATION_MD_PATH,
            render_reconciliation(expected_reconciliation),
            "P8A reconciliation Markdown",
        )
    )
    state_stage_by_name = state.get("stage_status", {})
    for stage in expected_reconciliation["stages"]:
        if state_stage_by_name.get(stage["stage"]) != stage["status"]:
            reconciliation_errors.append(
                f"state/reconciliation conflict for {stage['stage']}: "
                f"{state_stage_by_name.get(stage['stage'])!r} != {stage['status']!r}"
            )

    no_hardware_errors: list[str] = []
    require(state.get("current_run_hardware_authorization") is False, "current hardware authorization is not false", no_hardware_errors)
    require(state.get("p8a_no_hardware_actions_executed") is True, "P8A no-hardware marker is not true", no_hardware_errors)
    require(expected_reconciliation.get("no_hardware_actions_executed") is True, "reconciliation no-hardware marker is not true", no_hardware_errors)
    require(expected_reconciliation.get("hardware_scope_promoted") is False, "P8A promoted hardware scope", no_hardware_errors)

    gates = {
        "CANONICAL_CONSTRAINT_GATE": {
            "status": "PASS" if not canonical_errors else "FAIL",
            "errors": canonical_errors,
        },
        "PROJECT_STATE_CONSISTENCY": {
            "status": "PASS" if not state_errors else "FAIL",
            "errors": state_errors,
        },
        "REQUIREMENT_TRACEABILITY_BASELINE": {
            "status": "PASS" if not requirement_errors else "FAIL",
            "errors": requirement_errors,
        },
        "P0_P7_EVIDENCE_RECONCILIATION": {
            "status": "PASS" if not reconciliation_errors else "FAIL",
            "errors": reconciliation_errors,
        },
        "NO_HARDWARE_ACTIONS_EXECUTED": {
            "status": "PASS" if not no_hardware_errors else "FAIL",
            "value": True if not no_hardware_errors else False,
            "errors": no_hardware_errors,
        },
    }
    status = "PASS" if all(gate["status"] == "PASS" for gate in gates.values()) else "FAIL"
    inputs = []
    for path in (
        ROOT / "PROJECT_CONSTRAINTS.txt",
        STATE_PATH,
        REQUIREMENTS_PATH,
        STATUS_PATH,
        TRACEABILITY_PATH,
        RECONCILIATION_JSON_PATH,
        RECONCILIATION_MD_PATH,
    ):
        inputs.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(path) if path.is_file() else None,
            }
        )
    return {
        "schema_version": 1,
        "stage": "P8A",
        "status": status,
        "no_hardware_actions_executed": True,
        "hardware_scope_promoted": False,
        "preserved_scope": {
            "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE": state.get("p7_status"),
            "CURRENT_Z7010_PLATFORM_ACCEPTANCE": state.get("current_z7010_platform_status"),
            "Z7020_TARGET_ACCEPTANCE": state.get("z7020_target_status"),
            "ROTATION_ACCEPTANCE": state.get("rotation_status"),
            "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": state.get("final_product_status"),
        },
        "gates": gates,
        "input_artifacts": inputs,
    }


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# P8A Consistency Summary",
        "",
        f"P8A_STATUS: {summary['status']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_SCOPE_PROMOTED: false",
        "",
        "## Exit gates",
        "",
        "```text",
    ]
    for name, gate in summary["gates"].items():
        if name == "NO_HARDWARE_ACTIONS_EXECUTED":
            lines.append(f"{name}: {str(gate['value']).lower() if gate['status'] == 'PASS' else 'false'}")
        else:
            lines.append(f"{name}: {gate['status']}")
    lines += ["```", "", "## Preserved scope", "", "```text"]
    for name, value in summary["preserved_scope"].items():
        lines.append(f"{name}: {value}")
    lines += ["```", ""]
    all_errors = [
        (name, error)
        for name, gate in summary["gates"].items()
        for error in gate["errors"]
    ]
    if all_errors:
        lines += ["## Errors", ""]
        lines.extend(f"- `{name}`: {error}" for name, error in all_errors)
        lines.append("")
    lines += [
        "P8A is an offline canonicalization checkpoint. It preserves the scoped P7 hardware PASS and leaves Z7020, rotation, and final-product hardware acceptance pending.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    summary = build_summary()
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    SUMMARY_MD.write_text(render_summary(summary), encoding="utf-8", newline="\n")
    for name, gate in summary["gates"].items():
        if name == "NO_HARDWARE_ACTIONS_EXECUTED":
            print(f"{name}={1 if gate['status'] == 'PASS' else 0}")
        else:
            print(f"{name}={gate['status']}")
        for error in gate["errors"]:
            print(f"ERROR[{name}]: {error}")
    print(f"P8A_STATUS={summary['status']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
