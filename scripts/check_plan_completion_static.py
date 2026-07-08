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

REQUIRED_PASS_GATES = [
    "project_integrity",
    "xdc_conflicts",
    "tfdu_safety_static",
    "m1_tfdu_model_reference",
    "register_map_generation",
    "no_hardware_calls",
    "sv_port_contracts",
    "host_client_unit_tests",
    "m2_detect_window_sweep",
    "m2_static_reference_checks",
    "m3_crc_bad_ack_reference",
    "m3_static_reference_checks",
    "m4_ps_driver_trace",
    "m4_static_reference_checks",
    "scheduler_static_checks",
    "m5_static_nonhardware_build_checks",
    "m6_static_hardware_prep_checks",
    "m6_refusal_runtime",
    "generate_plan_completion_audit",
]

REQUIRED_TOOL_GATED_GATES = [
    "ps_driver_c_compile",
    "m5_vivado_nonhardware_build",
    "lane_phy_sim",
    "m2_4ppm_codec_sim",
    "m2_frame_l1_sim",
    "m2_4ppm_model_integration_sim",
    "m3_lane0_ack_only_sim",
    "m4_axi_regs_sim",
    "scheduler_sim",
]

AUDIT_REQUIRED_TEXT = [
    ("SV port contract coverage", "PLAN_AUDIT_SV_PORT_CONTRACT_RECORDED"),
    ("m4_ps_driver_trace", "PLAN_AUDIT_M4_PS_DRIVER_TRACE_RECORDED"),
    ("m6_refusal_runtime", "PLAN_AUDIT_M6_REFUSAL_RUNTIME_RECORDED"),
    ("PLAN_FORBIDDEN_CLAIM_REAL_HARDWARE_PASS_ABSENT=1", "PLAN_AUDIT_NO_REAL_HARDWARE_CLAIM_RECORDED"),
    ("PLAN_FORBIDDEN_CLAIM_ETHERNET_PASS_ABSENT=1", "PLAN_AUDIT_NO_ETHERNET_CLAIM_RECORDED"),
    ("PLAN_FORBIDDEN_CLAIM_ROTATION_PASS_ABSENT=1", "PLAN_AUDIT_NO_ROTATION_CLAIM_RECORDED"),
    ("PLAN_FORBIDDEN_CLAIM_TWO_HOUR_SOAK_PASS_ABSENT=1", "PLAN_AUDIT_NO_SOAK_CLAIM_RECORDED"),
    ("PLAN_FORBIDDEN_CLAIM_EIGHT_LANE_PASS_ABSENT=1", "PLAN_AUDIT_NO_EIGHT_LANE_CLAIM_RECORDED"),
    ("PLAN_FORBIDDEN_CLAIM_AB_L1_FIXED_ABSENT=1", "PLAN_AUDIT_NO_AB_L1_FIXED_CLAIM_RECORDED"),
    ("VIVADO_PATH_ON_PATH=0", "PLAN_AUDIT_VIVADO_PATH_ABSENCE_RECORDED"),
    (r"XILINX_VIVADO_2023_1_BIN=D:\Xilinx\Vivado\2023.1\bin", "PLAN_AUDIT_VIVADO_BAT_PATH_RECORDED"),
    ("XILINX_SIM_TOOLCHAIN_BAT_AVAILABLE=1", "PLAN_AUDIT_XILINX_SIM_BAT_AVAILABLE_RECORDED"),
    ("IVERILOG_ON_PATH=0", "PLAN_AUDIT_IVERILOG_ABSENCE_RECORDED"),
    ("VERILATOR_ON_PATH=0", "PLAN_AUDIT_VERILATOR_ABSENCE_RECORDED"),
    ("VITIS_CROSS_GCC_AVAILABLE=1", "PLAN_AUDIT_VITIS_CROSS_GCC_RECORDED"),
    ("M4_PS_DRIVER_C_COMPILE_MODE=CROSS_SYNTAX_ONLY", "PLAN_AUDIT_PS_DRIVER_CROSS_COMPILE_RECORDED"),
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


def marker_name(gate: str) -> str:
    return gate.upper().replace("-", "_")


def main() -> int:
    errors: list[str] = []
    bootstrap_text = (ROOT / "evidence/generated/bootstrap_markers.md").read_text(encoding="utf-8", errors="ignore")
    offline_summary = json.loads((ROOT / "evidence/generated/offline_gate_summary.json").read_text(encoding="utf-8"))
    matrix_text = (ROOT / "docs/design/ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8", errors="ignore")
    audit_text = (ROOT / "evidence/generated/plan_completion_audit.md").read_text(encoding="utf-8", errors="ignore")
    results_by_name = {r.get("name"): r for r in offline_summary.get("results", [])}

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
    for gate in REQUIRED_PASS_GATES:
        result = results_by_name.get(gate)
        require(
            result is not None and result.get("returncode") == 0 and result.get("status") != "PENDING_TOOL",
            f"PLAN_GATE_{marker_name(gate)}_PASS",
            errors,
        )
    for gate in REQUIRED_TOOL_GATED_GATES:
        result = results_by_name.get(gate)
        require(
            result is not None and result.get("returncode") == 0 and result.get("status") in {None, "PENDING_TOOL"},
            f"PLAN_GATE_{marker_name(gate)}_PASS_OR_PENDING_TOOL",
            errors,
        )

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

    require(
        "PLAN_COMPLETION_AUDIT_STATUS=PASS" in audit_text
        or "PLAN_COMPLETION_AUDIT_STATUS=OFFLINE_PROGRESS_WITH_PENDING_TOOL" in audit_text,
        "PLAN_AUDIT_STATUS_RECORDED",
        errors,
    )
    require(
        "OFFLINE_GATE_STATUS=PASS" in audit_text
        or "OFFLINE_GATE_STATUS=PASS_WITH_PENDING_TOOL" in audit_text,
        "PLAN_AUDIT_OFFLINE_STATUS_RECORDED",
        errors,
    )
    for text, marker in AUDIT_REQUIRED_TEXT:
        require(text in audit_text, marker, errors)

    print(f"PLAN_COMPLETION_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
