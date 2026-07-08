#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_BOOTSTRAP_MARKERS = [
    "PROJECT_BOOTSTRAP_DONE=1",
    "RF_COMM_SOURCE_IMPORTED=1",
    "PROJECT_CONSTRAINTS_COPIED=1",
    "AGENTS_MD_CREATED=1",
    "TFDU_DATASHEET_COPIED_OR_PENDING_RECORDED=1",
    "LEGACY_EVIDENCE_IMPORTED=1",
    "ACTIVE_XDC_ARCHIVED=1",
    "LEGACY_XDC_CONFLICT_ARCHIVED=1",
    "PINMAP_GENERATED=1",
    "CANONICAL_XDC_GENERATED=1",
    "G1_PROFILE_CREATED=1",
    "LANE1_DEFAULT_DISABLED=1",
    "TFDU_SAFETY_DOC_CREATED=1",
    "NEW_RTL_SKELETON_CREATED=1",
    "REGISTER_MAP_SINGLE_SOURCE_CREATED=1",
    "NO_HARDWARE_ACTIONS_EXECUTED=1",
]

FORBIDDEN_PASS_ROWS = {
    "Ethernet real board": "PASS",
    "Rotation 600 rpm": "PASS",
    "2-hour soak": "PASS",
    "8-lane": "PASS",
}

FORBIDDEN_CLAIM_LINES = [
    "REAL_HARDWARE_PASS",
    "ETHERNET_PASS",
    "ROTATION_PASS",
    "TWO_HOUR_SOAK_PASS",
    "EIGHT_LANE_PASS",
    "AB_L1_FIXED",
]


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


def parse_matrix_rows(text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| Stage"):
            continue
        parts = [part.strip() for part in line.strip("|").split("|")]
        if len(parts) >= 2:
            rows[parts[0]] = parts[1]
    return rows


def main() -> int:
    errors: list[str] = []
    bootstrap_text = (ROOT / "evidence/generated/bootstrap_markers.md").read_text(encoding="utf-8", errors="ignore")
    offline_summary = json.loads((ROOT / "evidence/generated/offline_gate_summary.json").read_text(encoding="utf-8"))
    matrix_text = (ROOT / "docs/design/ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8", errors="ignore")
    audit_text = (ROOT / "evidence/generated/plan_completion_audit.md").read_text(encoding="utf-8", errors="ignore")

    for marker in REQUIRED_BOOTSTRAP_MARKERS:
      require(marker in bootstrap_text, f"PLAN_MARKER_{marker.split('=')[0]}", errors)

    require(offline_summary.get("status") in {"PASS", "PASS_WITH_PENDING_TOOL"}, "PLAN_OFFLINE_GATES_RAN_WITHOUT_HARD_FAIL", errors)
    require(offline_summary.get("no_hardware") is True, "PLAN_OFFLINE_SUMMARY_NO_HARDWARE_TRUE", errors)
    hard_fail = [r for r in offline_summary.get("results", []) if r.get("returncode") != 0]
    require(not hard_fail, "PLAN_OFFLINE_RESULTS_NO_HARD_FAIL", errors)
    no_hw_results = [
        r for r in offline_summary.get("results", [])
        if r.get("name") == "no_hardware_calls" and "NO_HARDWARE_ACTIONS_EXECUTED=1" in r.get("stdout", "")
    ]
    require(bool(no_hw_results), "PLAN_NO_HARDWARE_SCAN_PASS", errors)

    rows = parse_matrix_rows(matrix_text)
    for stage, forbidden_status in FORBIDDEN_PASS_ROWS.items():
        status = rows.get(stage, "")
        require(status != forbidden_status and "PENDING" in status, f"PLAN_NONCLAIM_{stage.upper().replace(' ', '_').replace('-', '_')}", errors)

    exact_claim_lines = {
        line.strip()
        for rel in ("docs", "evidence/generated")
        for path in (ROOT / rel).rglob("*.md")
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
    }
    for claim in FORBIDDEN_CLAIM_LINES:
        require(claim not in exact_claim_lines and f"{claim}=1" not in exact_claim_lines, f"PLAN_FORBIDDEN_CLAIM_{claim}_ABSENT", errors)

    require("PLAN_COMPLETION_AUDIT_STATUS=OFFLINE_PROGRESS_WITH_PENDING_TOOL" in audit_text, "PLAN_AUDIT_STATUS_RECORDED", errors)
    require("OFFLINE_GATE_STATUS=PASS_WITH_PENDING_TOOL" in audit_text, "PLAN_AUDIT_OFFLINE_STATUS_RECORDED", errors)

    print(f"PLAN_COMPLETION_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
