#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from p5_lib import GENERATED, PASS, PASS_WITH_NOTES, PASS_WITH_SKIPS, ROOT, load_json, parse_markers, rel, validate_profile, write_json, write_markdown


PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED = "PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED"
PASSISH = {PASS, PASS_WITH_NOTES, PASS_WITH_SKIPS, PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED}
EXPECTED_PROFILES = [
    "profiles/p5/p5_safe_idle_recheck.json",
    "profiles/p5/p5_tfdu_control_idle_recheck.json",
    "profiles/p5/p5_raw_lane_matrix_fresh.json",
    "profiles/p5/p5_lane0_frame_crc_100.json",
    "profiles/p5/p5_lane1_frame_crc_100.json",
    "profiles/p5/p5_lane0_ack_retry_100.json",
    "profiles/p5/p5_lane1_ack_retry_100.json",
    "profiles/p5/p5_two_lane_minimal_100.json",
    "profiles/p5/p5_lane0_payload_sweep.json",
    "profiles/p5/p5_lane1_payload_sweep.json",
    "profiles/p5/p5_two_lane_payload_sweep.json",
    "profiles/p5/p5_two_lane_mask_regression.json",
    "profiles/p5/p5_retry_fault_injection_sim.json",
    "profiles/p5/p5_retry_fault_injection_hw_optional.json",
    "profiles/p5/p5_two_lane_30min_soak.json",
    "profiles/p5/p5_two_lane_2h_soak_optional.json",
]


def _exists(relpath: str) -> bool:
    return (ROOT / relpath).exists()


def _marker(relpath: str, key: str) -> str:
    return parse_markers(ROOT / relpath).get(key, "MISSING") if _exists(relpath) else "MISSING"


def _json_value(relpath: str, key: str) -> Any:
    data = load_json(ROOT / relpath)
    return data.get(key, "MISSING") if isinstance(data, dict) else "MISSING"


def _row(item: str, status: str, evidence: str, notes: str = "") -> dict[str, str]:
    return {"item": item, "status": status, "evidence": evidence, "notes": notes}


def _script_help(script: str) -> str:
    try:
        proc = subprocess.run([sys.executable, script, "--help"], cwd=ROOT, text=True, capture_output=True, timeout=30)
        return proc.stdout + proc.stderr
    except Exception as exc:
        return str(exc)


def audit() -> dict[str, Any]:
    rows: list[dict[str, str]] = []

    intake_files = [
        "evidence/generated/p5_repo_intake.md",
        "evidence/generated/p5_current_head.txt",
        "evidence/generated/p5_git_status_before.txt",
    ]
    rows.append(
        _row(
            "P5.0 repo intake",
            PASS if all(_exists(path) for path in intake_files) else "MISSING_EVIDENCE",
            ", ".join(intake_files),
            f"P5_REPO_INTAKE={_marker('evidence/generated/p5_repo_intake.md', 'P5_REPO_INTAKE')}",
        )
    )

    p4_reconcile = _json_value("evidence/generated/p5_p4_evidence_reconciliation.json", "P4_EVIDENCE_RECONCILIATION")
    rows.append(
        _row(
            "P5.1 P4 evidence reconciliation",
            PASS if p4_reconcile in PASSISH else "INCOMPLETE",
            "evidence/generated/p5_p4_evidence_reconciliation.json",
            f"P4_EVIDENCE_RECONCILIATION={p4_reconcile}",
        )
    )

    p1p2p3 = _marker("evidence/generated/p5_recheck_p1_p2_p3_p4_summary.md", "P1_P2_P3_RECHECK")
    rows.append(
        _row(
            "P5.2 P1/P2/P3/P4 recheck",
            PASS if p1p2p3 == PASS else "INCOMPLETE",
            "evidence/generated/p5_recheck_p1_p2_p3_p4_summary.md",
            f"P1_P2_P3_RECHECK={p1p2p3}",
        )
    )

    gate_specs = [
        ("P5.3 no Ethernet gate", "evidence/generated/p5_no_ethernet_hardware_tests_summary.md", "NO_ETHERNET_GATE"),
        ("P5.4 no motion gate", "evidence/generated/p5_no_motion_tests_summary.md", "NO_MOTION_GATE"),
        ("P5.5 two-lane scope gate", "evidence/generated/p5_2lane_scope_summary.md", "TWO_LANE_SCOPE_GATE"),
    ]
    for item, path, key in gate_specs:
        value = _marker(path, key)
        rows.append(_row(item, PASS if value == PASS else "INCOMPLETE", path, f"{key}={value}"))

    profile_failures = []
    for relpath in EXPECTED_PROFILES:
        path = ROOT / relpath
        if not path.exists():
            profile_failures.append(f"{relpath}: missing")
            continue
        data = load_json(path)
        errors = validate_profile(data) if isinstance(data, dict) else ["invalid JSON object"]
        if errors:
            profile_failures.append(f"{relpath}: {', '.join(errors)}")
    rows.append(
        _row(
            "P5.6 P5 profiles",
            PASS if not profile_failures else "INCOMPLETE",
            "profiles/p5/*.json, evidence/generated/p5_profiles_summary.md",
            "; ".join(profile_failures) if profile_failures else "all expected profiles exist and validate",
        )
    )

    help_text = _script_help("tools/run_p5_2lane_protocol_stabilization.py")
    required_flags = [
        "--dry-run",
        "--allow-hardware",
        "--execute-hardware",
        "--authorization-file",
        "--board-id",
        "--max-runtime-sec",
        "--profile",
        "--json-summary",
        "--stage-filter",
        "--stop-on-first-fail",
        "--skip-ethernet",
        "--skip-motion",
        "--lane-count",
    ]
    missing_flags = [flag for flag in required_flags if flag not in help_text]
    runner_files = [
        "tools/run_p5_2lane_protocol_stabilization.py",
        "tools/run_p5_2lane_protocol_stabilization.ps1",
        "tools/p5_hardware_authorization.py",
        ".hardware_authorization/P5_2LANE_APPROVED.txt.template",
        "evidence/generated/p5_hardware_authorization_summary.md",
        "evidence/generated/p5_hardware_stage_plan_summary.md",
        "evidence/generated/p5_authorized_run_package_summary.md",
    ]
    rows.append(
        _row(
            "P5.7 unified P5 runner",
            PASS if not missing_flags and all(_exists(path) for path in runner_files) else "INCOMPLETE",
            ", ".join(runner_files),
            "missing flags: " + ", ".join(missing_flags) if missing_flags else "required CLI flags present",
        )
    )

    hardware_specs = [
        ("P5.8 safe-idle recheck", "evidence/generated/p5_safe_idle_recheck_summary.md", "SAFE_IDLE_RECHECK"),
        ("P5.8 TFDU-control idle recheck", "evidence/generated/p5_tfdu_control_idle_recheck_summary.md", "TFDU_CONTROL_IDLE_RECHECK"),
        ("P5.9 fresh raw lane matrix", "evidence/generated/p5_raw_lane_matrix_summary.md", "RAW_LANE_MATRIX_FRESH"),
        ("P5.10 lane0 frame/CRC 100", "evidence/generated/p5_lane0_frame_crc_100_summary.md", "LANE0_FRAME_CRC_100"),
        ("P5.10 lane1 frame/CRC 100", "evidence/generated/p5_lane1_frame_crc_100_summary.md", "LANE1_FRAME_CRC_100"),
        ("P5.11 lane0 ACK/retry 100", "evidence/generated/p5_lane0_ack_retry_100_summary.md", "LANE0_ACK_RETRY_100"),
        ("P5.11 lane1 ACK/retry 100", "evidence/generated/p5_lane1_ack_retry_100_summary.md", "LANE1_ACK_RETRY_100"),
        ("P5.12 two-lane minimal 100", "evidence/generated/p5_two_lane_minimal_100_summary.md", "TWO_LANE_MINIMAL_100"),
        ("P5.13 payload sweep", "evidence/generated/p5_payload_sweep_summary.md", "PAYLOAD_SWEEP"),
        ("P5.14 mask regression", "evidence/generated/p5_mask_regression_summary.md", "MASK_REGRESSION"),
        ("P5.16 two-lane 30min soak", "evidence/generated/p5_two_lane_30min_soak_summary.md", "TWO_LANE_30MIN_SOAK"),
    ]
    for item, path, key in hardware_specs:
        value = _marker(path, key)
        status = PASS if value in PASSISH else "PENDING_HW" if value == "PENDING_HW_NOT_EXECUTED" else "INCOMPLETE"
        rows.append(_row(item, status, path, f"{key}={value}"))

    retry_status = _marker("evidence/generated/p5_retry_fault_injection_summary.md", "RETRY_FAULT_INJECTION_SIM")
    rows.append(
        _row(
            "P5.15 retry/fault injection",
            PASS if retry_status == PASS else "INCOMPLETE",
            "evidence/generated/p5_retry_fault_injection_summary.md",
            f"RETRY_FAULT_INJECTION_SIM={retry_status}",
        )
    )

    metrics_status = _json_value("evidence/generated/p5_protocol_metrics_summary.json", "P5_PROTOCOL_METRICS")
    rows.append(
        _row(
            "P5.17 protocol metrics",
            PASS if metrics_status in PASSISH else "PENDING_HW" if metrics_status == "SKIP_WITH_REASON" else "INCOMPLETE",
            "evidence/generated/p5_protocol_metrics_summary.json",
            f"P5_PROTOCOL_METRICS={metrics_status}",
        )
    )

    consistency = _marker("evidence/generated/p5_evidence_consistency_summary.md", "EVIDENCE_CONSISTENCY")
    rows.append(
        _row(
            "P5.18 evidence consistency",
            PASS if consistency in PASSISH else "INCOMPLETE",
            "evidence/generated/p5_evidence_consistency_summary.md",
            f"EVIDENCE_CONSISTENCY={consistency}",
        )
    )

    required_doc_markers = [
        "P0_BOOTSTRAP: PASS",
        "P1_OFFLINE_HARDENING: PASS",
        "P2_SIMULATION_BASELINE: PASS",
        "P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS",
        "P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE",
        "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
        "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
        "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
    ]
    doc_failures = []
    for relpath in ["PROJECT_STATUS.md", "docs/PROJECT_STATUS.md", "README.md"]:
        text = (ROOT / relpath).read_text(encoding="utf-8", errors="ignore") if _exists(relpath) else ""
        for marker in required_doc_markers:
            if marker not in text:
                doc_failures.append(f"{relpath}: missing {marker}")
    rows.append(
        _row(
            "P5.19 project status docs",
            PASS if not doc_failures else "INCOMPLETE",
            "PROJECT_STATUS.md, docs/PROJECT_STATUS.md, README.md",
            "; ".join(doc_failures) if doc_failures else "required status markers present",
        )
    )

    gate_files = ["tools/run_p5_gate.py", "tools/run_p5_gate.ps1", "evidence/generated/p5_2lane_protocol_stabilization_summary.md", "evidence/generated/p5_2lane_protocol_stabilization_summary.json"]
    rows.append(
        _row(
            "P5.20 total gate",
            PASS if all(_exists(path) for path in gate_files) else "INCOMPLETE",
            ", ".join(gate_files),
            f"P5_2LANE_PROTOCOL_STABILIZATION={_json_value('evidence/generated/p5_2lane_protocol_stabilization_summary.json', 'P5_2LANE_PROTOCOL_STABILIZATION')}",
        )
    )

    hard_pending = [row for row in rows if row["status"] == "PENDING_HW"]
    incomplete = [row for row in rows if row["status"] == "INCOMPLETE"]
    result = "IN_PROGRESS" if incomplete or hard_pending else PASS
    payload = {
        "P5_PLAN_REQUIREMENTS_AUDIT": result,
        "rows": rows,
        "pending_hw_count": len(hard_pending),
        "incomplete_count": len(incomplete),
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(GENERATED / "p5_plan_requirements_audit_summary.json", payload)

    lines = [
        f"P5_PLAN_REQUIREMENTS_AUDIT: {result}",
        f"PENDING_HW_ITEMS: {len(hard_pending)}",
        f"INCOMPLETE_ITEMS: {len(incomplete)}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "| Item | Status | Evidence | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(f"| {row['item']} | {row['status']} | `{row['evidence']}` | {row['notes']} |")
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- This is an audit of current P5 plan coverage, not a hardware execution report.",
            "- PENDING_HW items require explicit authorized P5 hardware evidence before P5 can pass.",
        ]
    )
    write_markdown(
        GENERATED / "p5_plan_requirements_audit_summary.md",
        "P5 Plan Requirements Audit Summary",
        result,
        "P5 plan audit generated from current evidence",
        lines,
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit current P5 evidence against the P5 plan without touching hardware.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = audit()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"P5_PLAN_REQUIREMENTS_AUDIT: {payload['P5_PLAN_REQUIREMENTS_AUDIT']}")
        print(f"PENDING_HW_ITEMS: {payload['pending_hw_count']}")
        print(f"INCOMPLETE_ITEMS: {payload['incomplete_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
