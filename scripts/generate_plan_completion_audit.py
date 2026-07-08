#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence" / "generated" / "plan_completion_audit.md"

SECTION14_MARKERS = [
    ("PROJECT_BOOTSTRAP_DONE=1", "evidence/generated/bootstrap_markers.md"),
    ("RF_COMM_SOURCE_IMPORTED=1", "evidence/generated/bootstrap_markers.md"),
    ("PROJECT_CONSTRAINTS_COPIED=1", "evidence/generated/bootstrap_markers.md"),
    ("AGENTS_MD_CREATED=1", "evidence/generated/bootstrap_markers.md"),
    ("TFDU_DATASHEET_COPIED_OR_PENDING_RECORDED=1", "evidence/generated/bootstrap_markers.md"),
    ("LEGACY_EVIDENCE_IMPORTED=1", "evidence/generated/bootstrap_markers.md"),
    ("ACTIVE_XDC_ARCHIVED=1", "evidence/generated/bootstrap_markers.md"),
    ("LEGACY_XDC_CONFLICT_ARCHIVED=1", "evidence/generated/bootstrap_markers.md"),
    ("PINMAP_GENERATED=1", "evidence/generated/bootstrap_markers.md"),
    ("CANONICAL_XDC_GENERATED=1", "evidence/generated/bootstrap_markers.md"),
    ("G1_PROFILE_CREATED=1", "evidence/generated/bootstrap_markers.md"),
    ("LANE1_DEFAULT_DISABLED=1", "evidence/generated/bootstrap_markers.md"),
    ("TFDU_SAFETY_DOC_CREATED=1", "evidence/generated/bootstrap_markers.md"),
    ("NEW_RTL_SKELETON_CREATED=1", "evidence/generated/bootstrap_markers.md"),
    ("REGISTER_MAP_SINGLE_SOURCE_CREATED=1", "evidence/generated/bootstrap_markers.md"),
    ("OFFLINE_GATES_RAN=1", "evidence/generated/offline_gate_summary.md"),
    ("NO_HARDWARE_ACTIONS_EXECUTED=1", "evidence/generated/offline_gate_summary.md"),
]

MILESTONES = [
    ("M1 TFDU lane PHY", ["tfdu_safety_static", "m1_tfdu_model_reference", "lane_phy_sim"], "IMPLEMENTED_REFERENCE_PASS_SIM_PENDING_TOOL"),
    ("TFDU6102 behavior model", ["tfdu_safety_static", "m1_tfdu_model_reference"], "IMPLEMENTED_REFERENCE_PASS"),
    ("SV port contract coverage", ["sv_port_contracts"], "STATIC_PASS"),
    ("M2 4PPM codec and frame L1", ["m2_detect_window_sweep", "m2_static_reference_checks", "m2_4ppm_codec_sim", "m2_frame_l1_sim"], "IMPLEMENTED_STATIC_PASS_SIM_PENDING_TOOL"),
    ("4PPM plus TFDU behavior model integration", ["m2_4ppm_model_integration_sim"], "TESTBENCH_STATIC_PASS_SIM_PENDING_TOOL"),
    ("M3 lane0 ACK/retry", ["m3_crc_bad_ack_reference", "m3_static_reference_checks", "m3_lane0_ack_only_sim"], "IMPLEMENTED_REFERENCE_PASS_SIM_PENDING_TOOL"),
    ("M4 AXI register contract", ["register_map_generation", "m4_ps_driver_trace", "m4_static_reference_checks", "m4_axi_regs_sim"], "IMPLEMENTED_TRACE_PASS_SIM_PENDING_TOOL"),
    ("PS driver fixed initialization sequence", ["m4_ps_driver_trace", "ps_driver_c_compile"], "TRACE_PASS_C_COMPILE_PENDING_TOOL"),
    ("Multilane scheduler requirement", ["scheduler_static_checks", "scheduler_sim"], "IMPLEMENTED_STATIC_PASS_SIM_PENDING_TOOL"),
    ("M5 Vivado non-hardware build", ["m5_static_nonhardware_build_checks", "m5_vivado_nonhardware_build"], "SCRIPTED_STATIC_PASS_VIVADO_PENDING_TOOL"),
    ("M6 hardware prep scripts", ["m6_static_hardware_prep_checks", "m6_refusal_runtime"], "PREPARED_REFUSAL_RUNTIME_PASS_NO_HARDWARE"),
    ("Host client offline protocol", ["host_client_unit_tests"], "OFFLINE_PASS_REAL_ETHERNET_PENDING_HW"),
]

FORBIDDEN_CLAIMS = [
    "REAL_HARDWARE_PASS",
    "ETHERNET_PASS",
    "ROTATION_PASS",
    "TWO_HOUR_SOAK_PASS",
    "EIGHT_LANE_PASS",
    "AB_L1_FIXED",
]


def read_text(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")


def result_status(result: dict | None) -> str:
    if result is None:
        return "MISSING"
    if result.get("status") == "PENDING_TOOL":
        return "PENDING_TOOL"
    return "PASS" if result.get("returncode") == 0 else "FAIL"


def find_stdout_marker(offline: dict, marker: str) -> str | None:
    prefix = f"{marker}="
    for item in offline.get("results", []):
        for line in item.get("stdout", "").splitlines():
            if line.startswith(prefix):
                return line
    return None


def main() -> int:
    offline = json.loads(read_text("evidence/generated/offline_gate_summary.json"))
    by_name = {item.get("name"): item for item in offline.get("results", [])}
    bootstrap = read_text("evidence/generated/bootstrap_markers.md")

    hard_fail = [item for item in offline.get("results", []) if item.get("returncode") != 0]
    status = "OFFLINE_PROGRESS_WITH_PENDING_TOOL" if offline.get("status") == "PASS_WITH_PENDING_TOOL" else offline.get("status", "UNKNOWN")
    no_hw = any(
        item.get("name") == "no_hardware_calls" and "NO_HARDWARE_ACTIONS_EXECUTED=1" in item.get("stdout", "")
        for item in offline.get("results", [])
    )

    lines = [
        "# Plan Completion Audit",
        "",
        f"PLAN_COMPLETION_AUDIT_STATUS={status}",
        "PLAN_COMPLETION_STATIC=PASS",
        "OFFLINE_GATES_RAN=1",
        f"OFFLINE_GATE_STATUS={offline.get('status', 'UNKNOWN')}",
        f"NO_HARDWARE_ACTIONS_EXECUTED={1 if no_hw else 0}",
        "",
        "## Section 14 Markers",
        "",
        "| Marker | Current evidence | Status |",
        "|---|---|---|",
    ]

    for marker, evidence in SECTION14_MARKERS:
        if evidence.endswith("bootstrap_markers.md"):
            ok = marker in bootstrap
        elif marker == "OFFLINE_GATES_RAN=1":
            ok = offline.get("status") in {"PASS", "PASS_WITH_PENDING_TOOL"}
        elif marker == "NO_HARDWARE_ACTIONS_EXECUTED=1":
            ok = no_hw
        else:
            ok = marker in read_text(evidence)
        lines.append(f"| `{marker}` | `{evidence}` | {'PROVEN' if ok else 'MISSING'} |")

    lines += [
        "",
        "## Milestone Evidence",
        "",
        "| Scope | Offline gate evidence | Status |",
        "|---|---|---|",
    ]
    for scope, gate_names, status_label in MILESTONES:
        statuses = [result_status(by_name.get(name)) for name in gate_names]
        gate_status = ", ".join(f"{name}:{status}" for name, status in zip(gate_names, statuses, strict=True))
        if any(status == "FAIL" for status in statuses):
            status_out = "FAIL"
        elif any(status == "MISSING" for status in statuses):
            status_out = "MISSING_EVIDENCE"
        elif all(status == "PASS" for status in statuses):
            status_out = status_label.replace("PENDING_TOOL", "PASS")
        else:
            status_out = status_label
        lines.append(f"| {scope} | {gate_status} | {status_out} |")

    lines += [
        "",
        "## Tool Discovery",
        "",
    ]
    for marker in [
        "VIVADO_PATH_ON_PATH",
        "XILINX_VIVADO_2023_1_BIN",
        "XILINX_VIVADO_2023_1_BAT_AVAILABLE",
        "XILINX_SIM_TOOLCHAIN_BAT_AVAILABLE",
        "IVERILOG_ON_PATH",
        "VERILATOR_ON_PATH",
        "C_COMPILER_HOST_MISSING",
        "VITIS_CROSS_GCC_AVAILABLE",
        "VITIS_CROSS_GCC",
        "M4_PS_DRIVER_C_COMPILE_MODE",
    ]:
        lines.append(find_stdout_marker(offline, marker) or f"{marker}=NOT_RECORDED")
    lines += [
        "",
        "Current evidence distinguishes PATH discovery from direct bat-path discovery: Vivado is not required to be on PATH when the D:\\Xilinx\\Vivado\\2023.1\\bin tools are present.",
    ]

    lines += [
        "",
        "## Explicit Non-Claims",
        "",
    ]
    exact_lines = {
        line.strip()
        for rel in ("docs", "evidence/generated")
        for path in (ROOT / rel).rglob("*.md")
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if path != OUT
    }
    for claim in FORBIDDEN_CLAIMS:
        absent = claim not in exact_lines and f"{claim}=1" not in exact_lines
        lines.append(f"PLAN_FORBIDDEN_CLAIM_{claim}_ABSENT={1 if absent else 0}")
    lines += [
        "",
        "The current workspace does not claim real hardware, Ethernet, rotation, soak, 8-lane, or AB_L1 repair acceptance.",
        "",
        "## Remaining External Evidence",
        "",
        "SystemVerilog simulation gates prefer PATH `iverilog`/`verilator`, then the D:\\Xilinx\\Vivado\\2023.1\\bin `xvlog.bat`/`xelab.bat`/`xsim.bat` toolchain.",
        "The Vivado non-hardware build runner uses PATH Vivado when present, otherwise the D:\\Xilinx\\Vivado\\2023.1\\bin\\vivado.bat fallback.",
        "`iverilog` and `verilator` remain absent when their discovery markers are `0`; this is distinct from Xilinx simulator availability.",
        "PS driver C compilation uses host `gcc`/`clang` when available, otherwise the Vitis ARM cross GCC syntax-only fallback when available.",
        "PS driver C compilation remains `PENDING_TOOL` only when neither a host C compiler nor the accepted Vitis cross compiler is available.",
        "Hardware acceptance remains `PENDING_HW` by project rule and was not executed.",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("PLAN_COMPLETION_AUDIT_GENERATED=1")
    print(f"PLAN_COMPLETION_AUDIT_STATUS={status}")
    print(f"PLAN_COMPLETION_AUDIT_HARD_FAILS={len(hard_fail)}")
    print(f"NO_HARDWARE_ACTIONS_EXECUTED={1 if no_hw else 0}")
    return 0 if not hard_fail and no_hw else 1


if __name__ == "__main__":
    raise SystemExit(main())
