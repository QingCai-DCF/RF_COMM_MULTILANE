#!/usr/bin/env python3
"""Build the deterministic P8A reconciliation of P0-P7 status evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from p8a_common import (
    RECONCILIATION_JSON_PATH,
    RECONCILIATION_MD_PATH,
    ROOT,
    dump_json,
    sha256_file,
)


P7_SOURCE_COMMIT = "911e1a303ff58593cac5ff4c4b70150d17f9a26b"
P7_EVIDENCE_COMMIT = "5006731277e49d9f2ddaa04a4726949674be5b27"
P7_RUN_ID = "p7_20260717_stationary_app_r74_formal_full"

INPUT_PATHS = [
    "evidence/generated/bootstrap_markers.md",
    "evidence/generated/p1_offline_hardening_summary.json",
    "evidence/generated/p2_simulation_baseline_summary.md",
    "evidence/generated/p3_pre_hw_acceptance_package_summary.md",
    "evidence/generated/p4_auto_hardware_acceptance_summary.json",
    "evidence/generated/p5_2lane_protocol_stabilization_summary.json",
    "evidence/generated/p6_evidence_consistency_summary.json",
    "evidence/generated/p7_offline_gate_summary.json",
    "evidence/generated/p7_lane1_promotion_summary.json",
    "evidence/generated/p7_final_acceptance_summary.json",
    "evidence/generated/p7_final_acceptance_summary.md",
    "evidence/hardware/p7/p7_run_sequence_ledger.json",
    "evidence/generated/p7_r41_formal_failure.json",
    "evidence/imported/evidence/final/BAD_DIR_fault_report.md",
    "docs/legacy_stage_rules/P7_PRE_V3_1_PROJECT_STATUS.md",
]


def read_json(root: Path, rel: str, errors: list[str]) -> dict[str, Any]:
    path = root / rel
    if not path.is_file():
        errors.append(f"missing evidence: {rel}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"invalid JSON {rel}: {exc}")
        return {}


def read_text(root: Path, rel: str, errors: list[str]) -> str:
    path = root / rel
    if not path.is_file():
        errors.append(f"missing evidence: {rel}")
        return ""
    return path.read_text(encoding="utf-8", errors="strict")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def evidence_record(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    record: dict[str, Any] = {"path": rel}
    if path.is_file():
        record["sha256"] = sha256_file(path)
        record["size_bytes"] = path.stat().st_size
    else:
        record["sha256"] = None
        record["size_bytes"] = None
    return record


def build_reconciliation(root: Path = ROOT) -> dict[str, Any]:
    errors: list[str] = []
    bootstrap = read_text(root, "evidence/generated/bootstrap_markers.md", errors)
    p1 = read_json(root, "evidence/generated/p1_offline_hardening_summary.json", errors)
    p2_historical = read_text(root, "evidence/generated/p2_simulation_baseline_summary.md", errors)
    p3 = read_text(root, "evidence/generated/p3_pre_hw_acceptance_package_summary.md", errors)
    p4 = read_json(root, "evidence/generated/p4_auto_hardware_acceptance_summary.json", errors)
    p5 = read_json(root, "evidence/generated/p5_2lane_protocol_stabilization_summary.json", errors)
    p6 = read_json(root, "evidence/generated/p6_evidence_consistency_summary.json", errors)
    p7_offline = read_json(root, "evidence/generated/p7_offline_gate_summary.json", errors)
    lane1 = read_json(root, "evidence/generated/p7_lane1_promotion_summary.json", errors)
    p7 = read_json(root, "evidence/generated/p7_final_acceptance_summary.json", errors)
    p7_md = read_text(root, "evidence/generated/p7_final_acceptance_summary.md", errors)
    ledger = read_json(root, "evidence/hardware/p7/p7_run_sequence_ledger.json", errors)
    r41 = read_json(root, "evidence/generated/p7_r41_formal_failure.json", errors)
    bad_dir = read_text(root, "evidence/imported/evidence/final/BAD_DIR_fault_report.md", errors)
    pre_v31_status = read_text(root, "docs/legacy_stage_rules/P7_PRE_V3_1_PROJECT_STATUS.md", errors)

    for marker in (
        "PROJECT_BOOTSTRAP_DONE=1",
        "RF_COMM_SOURCE_IMPORTED=1",
        "NO_HARDWARE_ACTIONS_EXECUTED=1",
    ):
        require(marker in bootstrap, f"P0 bootstrap marker missing: {marker}", errors)
    require(p1.get("status") == "PASS", "P1 summary is not PASS", errors)
    require("P2_SIMULATION_BASELINE: FAIL" in p2_historical, "historical P2 FAIL record is not preserved", errors)
    require("P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS" in p3, "P3 summary is not PASS", errors)
    require("P2_RECHECK: PASS" in p3, "P3 did not record the superseding P2 recheck PASS", errors)
    require(p4.get("P4_AUTO_HARDWARE_ACCEPTANCE") == "PASS", "P4 auto summary is not PASS", errors)
    require(p5.get("P5_2LANE_PROTOCOL_STABILIZATION") == "PASS_WITH_NOTES", "P5 summary is not PASS_WITH_NOTES", errors)
    require(p6.get("P6_EVIDENCE_CONSISTENCY") == "PASS", "P6 evidence consistency is not PASS", errors)
    require(p7_offline.get("P7_OFFLINE_GATE") == "PASS", "P7 offline regression is not PASS", errors)
    require(p7_offline.get("NO_HARDWARE_ACTIONS_EXECUTED") is True, "P7 offline gate lacks no-hardware marker", errors)
    require(lane1.get("P7_LANE1_RELIABILITY_PROMOTION_GATE") == "PASS", "latest lane1 promotion gate is not PASS", errors)
    require(lane1.get("source_evidence_contains_hardware_actions") is True, "lane1 promotion lost hardware-evidence provenance", errors)

    p7_expected = {
        "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET": "PASS",
        "HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION": "PASS",
        "STATIONARY_2LANE_APPLICATION_ACCEPTANCE": "PASS",
        "STATIONARY_30MIN": "PASS",
        "PS_PL_PHY_PL_PS_APPLICATION_PASS": True,
        "PRODUCT_FINAL_ACCEPTANCE": "PENDING",
        "SOURCE_COMMIT": P7_SOURCE_COMMIT,
        "SHUTDOWN_BEFORE": "PASS",
        "SHUTDOWN_AFTER": "PASS",
        "SHUTDOWN_EXIT": 0,
    }
    for key, value in p7_expected.items():
        require(p7.get(key) == value, f"P7 final JSON {key} must be {value!r}", errors)
    require(p7.get("FAIL") == [], "P7 final JSON contains failures", errors)
    require(p7.get("PENDING_HW") == [], "P7 final stationary scope remains pending", errors)
    require(p7.get("BITSTREAM_SHA256") == "756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a", "P7 bitstream hash changed", errors)
    require(p7.get("PS_ELF_SHA256") == "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949", "P7 ELF hash changed", errors)
    require(P7_RUN_ID in json.dumps(p7, ensure_ascii=False), "P7 r74 formal run ID is absent from final JSON provenance", errors)

    for marker in (
        "P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PASS",
        "HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PASS",
        "STATIONARY_2LANE_APPLICATION_ACCEPTANCE: PASS",
        "PRODUCT_FINAL_ACCEPTANCE: PENDING",
        "SHUTDOWN_BEFORE: PASS",
        "SHUTDOWN_AFTER: PASS",
    ):
        require(marker in p7_md, f"P7 final Markdown marker missing: {marker}", errors)
    require(
        "limited to a stationary, local, two-lane application path" in p7_md,
        "P7 final Markdown lost its scope boundary",
        errors,
    )

    runs = ledger.get("runs", [])
    require(isinstance(runs, list) and bool(runs), "P7 raw ledger has no runs", errors)
    if isinstance(runs, list) and runs:
        final_run = runs[-1]
        require(final_run.get("run_id") == "066_p7_ps_stationary", "P7 raw ledger terminal run is not stationary ordinal 66", errors)
        require(final_run.get("stage") == "stationary", "P7 raw ledger terminal stage is not stationary", errors)
        require(final_run.get("result") == "PASS", "P7 raw ledger terminal stationary result is not PASS", errors)
        require(final_run.get("returncode") == 0, "P7 raw ledger terminal return code is nonzero", errors)
        require(final_run.get("source_commit") == P7_SOURCE_COMMIT, "P7 raw ledger source commit changed", errors)
        require(final_run.get("shutdown_before", {}).get("passed") is True, "P7 raw ledger shutdown-before is not PASS", errors)
        require(final_run.get("shutdown_after", {}).get("passed") is True, "P7 raw ledger shutdown-after is not PASS", errors)

    require(r41.get("run_status") == "IMMUTABLE_FORMAL_FAIL_NEVER_RESUME_RESTART_COPY_OR_REUSE", "r41 immutable failure history changed", errors)
    require(r41.get("execution", {}).get("failed_ordinal") == 66, "r41 failed ordinal history changed", errors)
    require(r41.get("stationary", {}).get("completed_1800_seconds") is False, "r41 incomplete stationary history changed", errors)
    require(r41.get("shutdown", {}).get("safe_shutdown_complete") is True, "r41 shutdown history changed", errors)
    require("BAD_DIR" in bad_dir and "AB_L1" in bad_dir, "AB_L1 BAD_DIR legacy record is incomplete", errors)
    require("Historical Project Status Before V3.1 / P8A" in pre_v31_status, "pre-V3.1 status archive is not explicitly historical", errors)

    inputs = [evidence_record(root, rel) for rel in INPUT_PATHS]
    stages = [
        {
            "stage": "P0_BOOTSTRAP",
            "status": "PASS",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P0-BOOTSTRAP-MARKERS",
            "evidence": [evidence_record(root, "evidence/generated/bootstrap_markers.md")],
        },
        {
            "stage": "P1_OFFLINE_HARDENING",
            "status": "PASS",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P1-OFFLINE-HARDENING",
            "evidence": [evidence_record(root, "evidence/generated/p1_offline_hardening_summary.json")],
        },
        {
            "stage": "P2_SIMULATION_BASELINE",
            "status": "PASS",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P3-P2-RECHECK-PLUS-P7-REGRESSION",
            "evidence": [
                evidence_record(root, "evidence/generated/p3_pre_hw_acceptance_package_summary.md"),
                evidence_record(root, "evidence/generated/p7_offline_gate_summary.json"),
            ],
        },
        {
            "stage": "P3_PRE_HW_ACCEPTANCE_PACKAGE",
            "status": "PASS",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P3-PRE-HW-PACKAGE",
            "evidence": [evidence_record(root, "evidence/generated/p3_pre_hw_acceptance_package_summary.md")],
        },
        {
            "stage": "P4_AUTO_HARDWARE_ACCEPTANCE",
            "status": "PASS_WITH_PROXY_ILA_EVIDENCE",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P4-AUTO-HW-PROXY",
            "evidence": [evidence_record(root, "evidence/generated/p4_auto_hardware_acceptance_summary.json")],
        },
        {
            "stage": "P5_2LANE_PROTOCOL_STABILIZATION",
            "status": "PASS_WITH_NOTES",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P5-2LANE-PROTOCOL",
            "evidence": [evidence_record(root, "evidence/generated/p5_2lane_protocol_stabilization_summary.json")],
        },
        {
            "stage": "P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET",
            "status": "PASS",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P6-EVIDENCE-CONSISTENCY",
            "evidence": [evidence_record(root, "evidence/generated/p6_evidence_consistency_summary.json")],
        },
        {
            "stage": "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE",
            "status": "PASS",
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P7-R74-FORMAL-FULL",
            "evidence": [
                evidence_record(root, "evidence/generated/p7_final_acceptance_summary.json"),
                evidence_record(root, "evidence/generated/p7_final_acceptance_summary.md"),
                evidence_record(root, "evidence/hardware/p7/p7_run_sequence_ledger.json"),
            ],
        },
    ]

    return {
        "schema_version": 1,
        "stage": "P8A",
        "status": "PASS" if not errors else "FAIL",
        "no_hardware_actions_executed": True,
        "hardware_scope_promoted": False,
        "current_scoped_status": {
            "P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE": "PASS",
            "CURRENT_Z7010_PLATFORM_ACCEPTANCE": "PLATFORM_LIMITED_PASS",
            "Z7020_TARGET_ACCEPTANCE": "PENDING_Z7020_HW",
            "ROTATION_ACCEPTANCE": "PENDING_FINAL_MECHANICAL",
            "FINAL_PRODUCT_HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
        "p7_current": {
            "run_id": P7_RUN_ID,
            "source_commit": P7_SOURCE_COMMIT,
            "evidence_commit": P7_EVIDENCE_COMMIT,
            "profile": "Z7010_2LANE_DEV",
            "test_id": "P7-R74-FORMAL-FULL",
            "bitstream_sha256": "756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a",
            "ps_elf_sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
            "shutdown_before": "PASS",
            "shutdown_after": "PASS",
        },
        "stages": stages,
        "historical_conflicts": [
            {
                "conflict_id": "P2_EARLY_FAIL_VS_CURRENT_PASS",
                "historical_status": "FAIL",
                "historical_evidence": "evidence/generated/p2_simulation_baseline_summary.md",
                "resolution": "SUPERSEDED_FOR_CURRENT_P2_STATUS_BY_LATER_P2_RECHECK_AND_P7_REGRESSION",
                "history_preserved": True,
            },
            {
                "conflict_id": "AB_L1_LEGACY_BAD_DIR_VS_CURRENT_P7_USABILITY",
                "historical_status": "BAD_DIR",
                "historical_evidence": "evidence/imported/evidence/final/BAD_DIR_fault_report.md",
                "resolution": "RESOLVED_FOR_P7_STATIONARY_2LANE_ONLY",
                "current_evidence": "evidence/generated/p7_lane1_promotion_summary.json",
                "not_extrapolated_to": ["Z7020", "SECTOR_BANK", "ROTATION", "FINAL_PRODUCT"],
                "history_preserved": True,
            },
            {
                "conflict_id": "P7_R41_FAIL_VS_P7_R74_PASS",
                "historical_status": "IMMUTABLE_FAIL",
                "historical_evidence": "evidence/generated/p7_r41_formal_failure.json",
                "resolution": "R41_REMAINS_FAILED; LATER_DISTINCT_R74_FORMAL_RUN_IS_CURRENT_CANONICAL_PASS",
                "current_evidence": "evidence/generated/p7_final_acceptance_summary.json",
                "history_preserved": True,
            },
            {
                "conflict_id": "PRE_V3_1_STATUS_VS_CURRENT_CANONICAL_STATE",
                "historical_status": "P7_PENDING_HW",
                "historical_evidence": "docs/legacy_stage_rules/P7_PRE_V3_1_PROJECT_STATUS.md",
                "resolution": "SUPERSEDED_BY_CONFIG_PROJECT_STATE_AND_GENERATED_ROOT_STATUS",
                "history_preserved": True,
            },
        ],
        "input_artifacts": inputs,
        "errors": errors,
    }


def render_reconciliation(data: dict[str, Any]) -> str:
    lines = [
        "# P8A P0-P7 Evidence Reconciliation",
        "",
        f"P0_P7_EVIDENCE_RECONCILIATION: {data['status']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_SCOPE_PROMOTED: false",
        "",
        "## Current scoped status",
        "",
        "```text",
    ]
    for key, value in data["current_scoped_status"].items():
        lines.append(f"{key}: {value}")
    lines += ["```", "", "## Stage resolution", "", "| Stage | Status | Profile | Test ID |", "|---|---|---|---|"]
    for stage in data["stages"]:
        lines.append(f"| `{stage['stage']}` | `{stage['status']}` | `{stage['profile']}` | `{stage['test_id']}` |")
    lines += ["", "## Preserved contradictions and resolution", "", "| Conflict | Historical status | Resolution | History preserved |", "|---|---|---|---|"]
    for conflict in data["historical_conflicts"]:
        lines.append(
            f"| `{conflict['conflict_id']}` | `{conflict['historical_status']}` | `{conflict['resolution']}` | `{str(conflict['history_preserved']).lower()}` |"
        )
    lines += ["", "## Input artifacts", "", "| Path | SHA256 | Bytes |", "|---|---|---:|"]
    for record in data["input_artifacts"]:
        lines.append(f"| `{record['path']}` | `{record['sha256']}` | {record['size_bytes']} |")
    if data["errors"]:
        lines += ["", "## Errors", ""] + [f"- {error}" for error in data["errors"]]
    lines += [
        "",
        "The P7 r74 PASS does not rewrite the immutable r41 FAIL or the legacy AB_L1 BAD_DIR record. It only establishes the latest canonical stationary Z7010 two-lane application scope.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or verify P0-P7 evidence reconciliation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()

    data = build_reconciliation(ROOT)
    expected_json = dump_json(data)
    expected_md = render_reconciliation(data)
    errors = list(data["errors"])
    if args.write:
        RECONCILIATION_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        RECONCILIATION_JSON_PATH.write_text(expected_json, encoding="utf-8", newline="\n")
        RECONCILIATION_MD_PATH.write_text(expected_md, encoding="utf-8", newline="\n")
    if args.check:
        if not RECONCILIATION_JSON_PATH.is_file() or RECONCILIATION_JSON_PATH.read_bytes() != expected_json.encode("utf-8"):
            errors.append("P8A reconciliation JSON is stale")
        if not RECONCILIATION_MD_PATH.is_file() or RECONCILIATION_MD_PATH.read_bytes() != expected_md.encode("utf-8"):
            errors.append("P8A reconciliation Markdown is stale")

    for error in errors:
        print(f"ERROR: {error}")
    print(f"P0_P7_EVIDENCE_RECONCILIATION={'PASS' if not errors else 'FAIL'}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=1")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
