#!/usr/bin/env python3
"""Generate a current evidence-backed completion audit for RF_COMM plan work."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
CONSTRAINT = ROOT / "项目约束(目标）.txt"


@dataclass
class AuditItem:
    item_id: str
    area: str
    requirement: str
    status: str
    evidence: str
    note: str


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    # PowerShell 5 Out-File frequently writes UTF-16LE without a BOM when
    # redirected through nested scripts. If many NUL bytes are present, prefer
    # UTF-16LE before falling back to UTF-8.
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def contains(path: Path | None, pattern: str) -> bool:
    if path is None:
        return False
    return re.search(pattern, read_text(path), re.MULTILINE | re.DOTALL) is not None


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def latest_matching(pattern: str, forbidden: list[str] | None = None) -> Path | None:
    forbidden = forbidden or []
    paths = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        text = read_text(path)
        if all(re.search(expr, text, re.MULTILINE | re.DOTALL) is None for expr in forbidden):
            return path
    return None


def latest_any(*patterns: str) -> Path | None:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def exists_rel(rel: str) -> bool:
    return (ROOT / rel).exists()


def status_from(condition: bool, true_status: str = "PASS", false_status: str = "MISSING") -> str:
    return true_status if condition else false_status


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def collect_items() -> list[AuditItem]:
    items: list[AuditItem] = []

    constraint_hash = sha256(CONSTRAINT) if CONSTRAINT.exists() else "MISSING"
    items.append(
        AuditItem(
            "C0",
            "Hard constraint",
            "Root project constraint file exists and has not been edited during recent work.",
            status_from(constraint_hash == "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"),
            "项目约束(目标）.txt",
            f"sha256={constraint_hash}",
        )
    )

    items.append(
        AuditItem(
            "P0-1",
            "Evidence freeze",
            "Historical/current evidence lock and known-good/current config diff exist.",
            status_from(exists_rel("evidence_lock_20260625.csv") and exists_rel("config_diff_known_good_vs_current.md")),
            "evidence_lock_20260625.csv; config_diff_known_good_vs_current.md",
            "Used to distinguish known-good lane0/2-lane runs from current regression candidates.",
        )
    )

    sim_log = ROOT / "reports/simulation_gates_2lane_stream_bidir_rxmicroscope_seq_20260626_022622.out.log"
    sim_meta = ROOT / "reports/simulation_gates_2lane_stream_bidir_rxmicroscope_seq_20260626_022622.meta.txt"
    items.append(
        AuditItem(
            "SIM-2L",
            "RTL simulation",
            "Current 2-lane stream_bidir/rx-microscope simulation gate passes.",
            status_from(
                contains(sim_meta, r"code=0")
                and contains(sim_log, r"AXI_RX_MICROSCOPE_SESSION_MISMATCH_PASS")
                and contains(sim_log, r"IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS")
                and contains(sim_log, r"PS_BRIDGE_STATIC_CHECKS_PASS")
                and contains(sim_log, r"\[PASS\] host_offline_acceptance")
            ),
            f"{rel(sim_log)}; {rel(sim_meta)}",
            "Includes RX microscope, 2-lane perf, bidirectional single-lane, PS bridge static, and host offline acceptance markers in that simulation gate.",
        )
    )

    project_log = ROOT / "reports/project_gates_2lane_stream_bidir_ila_20260626_024119.out.log"
    project_meta = ROOT / "reports/project_gates_2lane_stream_bidir_ila_20260626_024119.meta.txt"
    items.append(
        AuditItem(
            "PG-2L-ILA",
            "Vivado build",
            "Current 2-lane ILA image passes project/timing/utilization gates.",
            status_from(
                contains(project_meta, r"code=0")
                and contains(project_log, r"\[PASS\] bitstream")
                and contains(project_log, r"\[PASS\] xsa")
                and contains(project_log, r"\[PASS\] timing")
                and contains(project_log, r"\[PASS\] utilization")
                and contains(project_log, r"\[PASS\] host_offline_acceptance")
            ),
            f"{rel(project_log)}; {rel(project_meta)}",
            "Latest build is ready for hardware debug once JTAG target is visible.",
        )
    )

    artifact_paths = [
        ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.bit",
        ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.ltx",
        ROOT / "TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa",
        ROOT / "software/_boot/BOOT.BIN",
        ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
    ]
    artifact_note = "; ".join(f"{path.name}={sha256(path) if path.exists() else 'MISSING'}" for path in artifact_paths)
    items.append(
        AuditItem(
            "ARTIFACTS",
            "Build artifacts",
            "Current bit/LTX/XSA/BOOT and shutdown bitstream are present.",
            status_from(all(path.exists() for path in artifact_paths)),
            "; ".join(rel(path) for path in artifact_paths),
            artifact_note,
        )
    )

    boot_audit = ROOT / "reports/boot_artifact_audit_current_20260626.md"
    boot_audit_json = ROOT / "reports/boot_artifact_audit_current_20260626.json"
    boot_audit_pass = (
        contains(boot_audit, r"\| ps_lwip_bridge \| PASS \|")
        and contains(boot_audit, r"\| ps_ps_loopback \| PASS \|")
        and contains(boot_audit, r"app markers missing: `none`")
    )
    items.append(
        AuditItem(
            "BOOT-AUDIT",
            "Build artifacts",
            "PS lwIP bridge and PS-PS loopback SD BOOT packages are component-hash audited and current.",
            status_from(boot_audit_pass),
            f"{rel(boot_audit)}; {rel(boot_audit_json)}",
            "Proves BIF component existence, hashes, input freshness, and expected UART/application markers.",
        )
    )

    latest_drc_triage = latest("reports/drc_triage_current_*.md")
    drc_triage_pass = (
        latest_drc_triage is not None
        and contains(latest_drc_triage, r"TRIAGED_NOT_RELEASE_READY")
        and contains(latest_drc_triage, r"FIX_CONSTRAINTS_BEFORE_RELEASE")
        and contains(latest_drc_triage, r"OPTIMIZE_BEFORE_4_OR_8_LANE")
    )
    items.append(
        AuditItem(
            "DRC-TRIAGE",
            "Release prerequisites",
            "Current DRC/methodology warnings are triaged into waiver candidates and pre-release actions.",
            status_from(drc_triage_pass),
            rel(latest_drc_triage),
            "This proves documentation and classification only; release/4-or-8-lane expansion still requires fixes, formal waivers, or clean release-build DRC.",
        )
    )

    matrix_script = ROOT / "tools/run_2lane_matrix_safe.ps1"
    p1_mapping_script = ROOT / "tools/run_p1_lane_mapping_matrix_safe.ps1"
    analyzer_script = ROOT / "tools/analyze_2lane_ila_csv.py"
    matrix_summary = ROOT / "reports/2lane_matrix_safe_20260626_030720.summary.txt"
    latest_p1_mapping = latest("reports/p1_lane_mapping_matrix_safe_*.summary.txt")
    latest_p1_mapping_hw = latest_matching("reports/p1_lane_mapping_matrix_safe_*.summary.txt", forbidden=[r"(?m)^DRY_RUN=1\b"])
    p0_root_script = ROOT / "tools/run_p0_rx_root_cause_safe.ps1"
    latest_p0_root = latest("reports/p0_rx_root_cause_safe_*.summary.txt")
    p0_ack_script = ROOT / "tools/run_p0_ack_only_safe.ps1"
    latest_p0_ack = latest("reports/p0_ack_only_safe_*.summary.txt")
    p0_ack_build_script = ROOT / "tools/build_p0_ack_only_artifacts.ps1"
    latest_p0_ack_build = latest("reports/p0_ack_only_build_*.summary.txt")
    latest_debug_decode = ROOT / "reports/ila_2lane_matrix_analysis_debug_decode_current.md"
    readiness_script = ROOT / "tools/check_plan_readiness.py"
    latest_readiness = latest("reports/plan_readiness_current_*.md")
    latest_readiness_json = latest("reports/plan_readiness_current_*.json")
    snapshot_script = ROOT / "tools/write_plan_execution_snapshot.py"
    latest_snapshot = latest("reports/plan_execution_snapshot_current_*.md")
    latest_snapshot_json = latest("reports/plan_execution_snapshot_current_*.json")
    active_guard_script = ROOT / "tools/check_active_artifact_stage.py"
    latest_active_guard = latest("reports/active_artifact_guard_current_*.md")
    latest_active_guard_json = latest("reports/active_artifact_guard_current_*.json")
    jtag_blocker_script = ROOT / "tools/analyze_jtag_blocker.py"
    latest_jtag_blocker = latest_any("reports/jtag_blocker_current_*.md", "reports/jtag_blocker_analysis_current_*.md")
    latest_jtag_blocker_json = latest_any("reports/jtag_blocker_current_*.json", "reports/jtag_blocker_analysis_current_*.json")
    jtag_checklist_script = ROOT / "tools/write_jtag_recovery_checklist.py"
    latest_jtag_checklist = latest("reports/jtag_recovery_checklist_current_*.md")
    latest_jtag_checklist_json = latest("reports/jtag_recovery_checklist_current_*.json")
    latest_jtag_recovery = latest("reports/jtag_recovery_then_resume_*.summary.txt")
    items.append(
        AuditItem(
            "P1-1-TOOLS",
            "2-lane matrix",
            "Safe lane-specific matrix runner and offline ILA CSV analyzer exist and are validated.",
            status_from(
                p1_mapping_script.exists()
                and matrix_script.exists()
                and analyzer_script.exists()
                and latest_p1_mapping is not None
                and contains(latest_p1_mapping, r"P1_SCOPE=P1-1 lane mapping raw-pulse matrix")
                and (
                    contains(latest_p1_mapping, r"DRY_RUN_NO_HARDWARE_DONE=1")
                    or contains(latest_p1_mapping, r"P1_LANE_MAPPING_BLOCKED_NO_PROGRAMMING=1")
                    or contains(latest_p1_mapping, r"PREFLIGHT_PASS_PARSED=1")
                )
            ),
            f"{rel(p1_mapping_script)}; {rel(matrix_script)}; {rel(analyzer_script)}; {rel(matrix_summary)}; {rel(latest_p1_mapping)}",
            "P1 wrapper covers A lane0/lane1 and B lane0/lane1 triggers; runners block before programming unless HW preflight parses PASS plus HW_PREFLIGHT_ZYNQ.",
        )
    )

    p0_root_tool_pass = (
        p0_root_script.exists()
        and analyzer_script.exists()
        and latest_p0_root is not None
        and (
            contains(latest_p0_root, r"P0_RX_ROOT_CAUSE_BLOCKED_NO_PROGRAMMING=1")
            or contains(latest_p0_root, r"DRY_RUN_NO_HARDWARE_DONE=1")
        )
        and contains(latest_debug_decode, r"B Debug Classes")
    )
    items.append(
        AuditItem(
            "P0-RX-TOOL",
            "RX root cause",
            "Safe P0 RX-root-cause runner and debug-aware offline ILA analyzer are prepared.",
            status_from(p0_root_tool_pass),
            f"{rel(p0_root_script)}; {rel(analyzer_script)}; {rel(latest_p0_root)}; {rel(latest_debug_decode)}",
            "This proves tooling readiness only; P0-4/P0-5 still need fresh hardware CSV captures after JTAG recovery.",
        )
    )

    p0_ack_tool_pass = (
        p0_ack_script.exists()
        and latest_p0_ack is not None
        and contains(latest_p0_ack, r"P0_SCOPE=P0-6 ACK-only return-path orchestration")
        and contains(latest_p0_ack, r"ACK_ONLY_REQUIRED_CONFIG=")
        and (
            contains(latest_p0_ack, r"DRY_RUN_NO_HARDWARE_DONE=1")
            or contains(latest_p0_ack, r"P0_ACK_ONLY_BLOCKED_NO_RX_PASS_EVIDENCE=1")
            or contains(latest_p0_ack, r"P0_ACK_ONLY_BLOCKED_NO_PROGRAMMING=1")
        )
    )
    items.append(
        AuditItem(
            "P0-ACK-TOOL",
            "ACK-only",
            "Safe P0 ACK-only orchestration runner exists and enforces RX/JTAG gates before TFDU drive.",
            status_from(p0_ack_tool_pass),
            f"{rel(p0_ack_script)}; {rel(latest_p0_ack)}",
            "This proves tooling readiness only; P0-6 still needs ACK-only bit/config evidence plus fresh hardware ACK counters/waveforms.",
        )
    )

    p0_ack_build_tool_pass = (
        p0_ack_build_script.exists()
        and latest_p0_ack_build is not None
        and contains(latest_p0_ack_build, r"BUILD_ENV IR_B_MODE=stream_bidir")
        and contains(latest_p0_ack_build, r"BUILD_ENV IR_B2A_ENABLE=0")
        and contains(latest_p0_ack_build, r"BUILD_ENV IR_B2A_FREE_RUN=0")
        and contains(latest_p0_ack_build, r"ILA_COMMAND=")
        and contains(latest_p0_ack_build, r"DRY_RUN_NO_VIVADO_DONE=1")
    )
    items.append(
        AuditItem(
            "P0-ACK-BUILD-TOOL",
            "ACK-only",
            "ACK-only bit/XSA/ELF build wrapper is prepared with explicit config, 2-lane ILA insertion, and P-core affinity.",
            status_from(p0_ack_build_tool_pass),
            f"{rel(p0_ack_build_script)}; {rel(latest_p0_ack_build)}",
            "This is a non-destructive dry-run proof of the build recipe; no ACK-only bitstream is claimed until RunBuild produces hashed artifacts.",
        )
    )

    readiness_pass = (
        readiness_script.exists()
        and latest_readiness is not None
        and latest_readiness_json is not None
        and contains(latest_readiness, r"PLAN_READINESS_SUMMARY")
        and contains(latest_readiness, r"G1_JTAG_ACCESS")
        and contains(latest_readiness, r"BLOCKED_BY_PREREQUISITES")
    )
    items.append(
        AuditItem(
            "PLAN-READINESS",
            "Plan gates",
            "Evidence-backed stage readiness gate is generated and prevents skipping hardware/DRC prerequisites.",
            status_from(readiness_pass),
            f"{rel(readiness_script)}; {rel(latest_readiness)}; {rel(latest_readiness_json)}",
            "PASS here means the readiness gate exists and is evidence-backed; the gate verdict itself is currently BLOCKED_BY_PREREQUISITES.",
        )
    )

    snapshot_pass = (
        snapshot_script.exists()
        and latest_snapshot is not None
        and latest_snapshot_json is not None
        and contains(latest_snapshot, r"PLAN_EXECUTION_SNAPSHOT")
        and contains(latest_snapshot, r"active_artifact=2LANE_ILA_BASELINE")
        and contains(latest_snapshot, r"ack_only=DRY_RUN_RECIPE_ONLY")
    )
    items.append(
        AuditItem(
            "PLAN-SNAPSHOT",
            "Plan gates",
            "Current active artifact, ACK-only recipe, next commands, and safety state are captured in one snapshot.",
            status_from(snapshot_pass),
            f"{rel(snapshot_script)}; {rel(latest_snapshot)}; {rel(latest_snapshot_json)}",
            "This is a process/evidence snapshot only; it does not claim any new hardware pass.",
        )
    )

    active_guard_pass = (
        active_guard_script.exists()
        and latest_active_guard is not None
        and latest_active_guard_json is not None
        and contains(latest_active_guard, r"ACTIVE_ARTIFACT_GUARD stage=P1_2LANE_ILA_BASELINE")
        and contains(latest_active_guard, r"result=PASS")
    )
    items.append(
        AuditItem(
            "ACTIVE-ARTIFACT-GUARD",
            "Plan gates",
            "Active bit/LTX/XSA/BOOT/shutdown/constraint hashes are checked before P1 hardware retry.",
            status_from(active_guard_pass),
            f"{rel(active_guard_script)}; {rel(latest_active_guard)}; {rel(latest_active_guard_json)}",
            "This prevents mixing the P1 2-lane ILA baseline with ACK-only or stale artifacts; it performs no hardware action.",
        )
    )

    jtag_blocker_pass = (
        jtag_blocker_script.exists()
        and latest_jtag_blocker is not None
        and latest_jtag_blocker_json is not None
        and contains(latest_jtag_blocker, r"JTAG_BLOCKER_ANALYSIS status=(BLOCKED_NO_HW_TARGET|JTAG_READY)")
        and contains(latest_jtag_blocker, r"hardware_action=none programming=none tfdu_drive=none")
    )
    items.append(
        AuditItem(
            "JTAG-BLOCKER-ANALYSIS",
            "Hardware access",
            "Current JTAG blocker is classified from USB/PnP/driver/preflight evidence without programming.",
            status_from(jtag_blocker_pass),
            f"{rel(jtag_blocker_script)}; {rel(latest_jtag_blocker)}; {rel(latest_jtag_blocker_json)}",
            "Diagnostic evidence only; the separate JTAG item decides whether hardware access is currently ready.",
        )
    )

    jtag_checklist_pass = (
        jtag_checklist_script.exists()
        and latest_jtag_checklist is not None
        and latest_jtag_checklist_json is not None
        and contains(latest_jtag_checklist, r"JTAG_RECOVERY_CHECKLIST classification=EXPECTED_AX7010_FT232HL_VISIBLE_BUT_NO_VIVADO_TARGET")
        and contains(latest_jtag_checklist, r"hardware_action=none programming=none tfdu_drive=none")
    )
    items.append(
        AuditItem(
            "JTAG-RECOVERY-CHECKLIST",
            "Hardware access",
            "AX7010 manual/PnP evidence is converted into an ordered JTAG recovery checklist.",
            status_from(jtag_checklist_pass),
            f"{rel(jtag_checklist_script)}; {rel(latest_jtag_checklist)}; {rel(latest_jtag_checklist_json)}",
            "This narrows recovery work to power/reset, JTAG connector, J13, and driver binding; it does not prove JTAG access.",
        )
    )

    jtag_recovery_chain_pass = (
        latest_jtag_recovery is not None
        and contains(latest_jtag_recovery, r"RESUME_COMMAND=.*run_p1_lane_mapping_matrix_safe\.ps1")
        and contains(latest_jtag_recovery, r"TRIGGER_MODES=a_tx_lane0,a_tx_lane1,b_tx_lane0,b_tx_lane1")
        and contains(latest_jtag_recovery, r"MAX_TFDU_WINDOW_SECONDS=300")
        and contains(latest_jtag_recovery, r"NO_SYSTEM_DRIVER_CHANGE_DONE=1")
        and contains(latest_jtag_recovery, r"NO_RESUME_RUN_DONE=1")
    )
    items.append(
        AuditItem(
            "JTAG-RECOVERY-CHAIN",
            "Hardware access",
            "Elevated driver-recovery dry-run now resumes into the current P1 four-direction safe matrix entry.",
            status_from(jtag_recovery_chain_pass),
            f"{rel(latest_jtag_recovery)}; tools/run_jtag_driver_recovery_then_resume.ps1; tools/run_p1_lane_mapping_matrix_safe.ps1",
            "Dry-run proof only: no system driver change, no FPGA programming, and no TFDU run were performed.",
        )
    )

    latest_preflight = latest("reports/hw_target_preflight_*.summary.txt")
    latest_matrix = latest("reports/2lane_matrix_safe_*.summary.txt")
    latest_resume = latest("reports/plan_hw_resume_safe_*.summary.txt")
    latest_jtag_diag = latest("reports/jtag_usb_diag_*.summary.txt")
    preflight_text = read_text(latest_preflight) + "\n" + read_text(latest_matrix) + "\n" + read_text(latest_resume)
    jtag_pass = "HW_PREFLIGHT_RESULT PASS" in preflight_text and "HW_PREFLIGHT_ZYNQ" in preflight_text
    jtag_fail = "FAIL_NO_TARGET" in preflight_text
    p1_hw_failed = (
        contains(latest_p1_mapping_hw, r"RUN_ILA_TIMEOUT")
        or contains(latest_p1_mapping_hw, r"RUN_MISSING_ILA_CSV")
        or contains(latest_p1_mapping_hw, r"MATRIX_EFFECTIVE_EXIT=[1-9]\d*")
    )
    jtag_note = (
        "Current evidence enumerates the Zynq target; P1 lane mapping is the next hardware gate."
        if jtag_pass
        else "Current evidence still shows FAIL_NO_TARGET, so hardware tests are intentionally gated."
    )
    items.append(
        AuditItem(
            "JTAG",
            "Hardware access",
            "Vivado Hardware Manager can enumerate the Zynq target.",
            "PASS" if jtag_pass else ("WAITING_HARDWARE" if jtag_fail else "UNKNOWN"),
            f"{rel(latest_preflight)}; {rel(latest_matrix)}; {rel(latest_resume)}; {rel(latest_jtag_diag)}",
            jtag_note,
        )
    )

    items.append(
        AuditItem(
            "P1-1-HW",
            "2-lane matrix",
            "Fresh lane0/lane1 A->B and B->A physical matrix is captured and classified.",
            "FAIL_HARDWARE" if p1_hw_failed else ("WAITING_HARDWARE" if not jtag_pass else "READY_TO_RUN"),
            f"{rel(p1_mapping_script)}; {rel(latest_p1_mapping_hw)}",
            "Latest P1 evidence has lane timeout/missing CSV; fix lane1 physical/trigger path before protocol restore."
            if p1_hw_failed
            else "Execution command: powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p1_lane_mapping_matrix_safe.ps1 -StopOnFail",
        )
    )

    ps_pc_summary = latest("reports/ps_pc_offline_gates_*.summary.txt")
    items.append(
        AuditItem(
            "P2-OFFLINE",
            "PS/PC network",
            "PS bridge source-level TCP/DHCP/reconnect checks and host offline mock acceptance pass.",
            status_from(ps_pc_summary is not None and contains(ps_pc_summary, r"PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1")),
            rel(ps_pc_summary),
            "Latest offline gate only: proves protocol/tooling, not real AX7010 Ethernet or DHCP on hardware.",
        )
    )

    uart_probe_script = ROOT / "tools/probe_ps_uart_boot_safe.ps1"
    latest_uart_probe = latest("reports/ps_uart_boot_probe_*.summary.txt")
    latest_uart_text = read_text(latest_uart_probe)
    uart_verdict_match = re.search(r"(?m)^UART_PROBE_VERDICT=(.+)$", latest_uart_text)
    uart_verdict = uart_verdict_match.group(1).strip() if uart_verdict_match else "NO_PROBE"
    uart_safe = (
        uart_probe_script.exists()
        and "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1" in latest_uart_text
        and "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1" in latest_uart_text
        and "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1" in latest_uart_text
    )
    items.append(
        AuditItem(
            "P2-UART-TOOL",
            "PS/PC network",
            "Safe UART boot probe exists and latest run did not write UART, program FPGA, or drive TFDU.",
            status_from(uart_safe),
            f"{rel(uart_probe_script)}; {rel(latest_uart_probe)}",
            f"latest_uart_verdict={uart_verdict}",
        )
    )

    board_smoke_script = ROOT / "tools/run_ps_pc_board_smoke_safe.ps1"
    latest_board_smoke = latest("reports/ps_pc_board_smoke_safe_*.summary.txt")
    latest_board_smoke_text = read_text(latest_board_smoke)
    board_smoke_safe_tool = (
        board_smoke_script.exists()
        and (
            "SMOKE_BLOCKED_NO_TARGET_HOST=1" in latest_board_smoke_text
            or "SMOKE_DRY_RUN=1" in latest_board_smoke_text
            or "SMOKE_VERDICT=PASS_REAL_BOARD_HELLO_STATUS" in latest_board_smoke_text
            or "SMOKE_VERDICT=FAIL_OR_NO_BOARD_RESPONSE" in latest_board_smoke_text
        )
        and "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1" in latest_board_smoke_text
        and "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1" in latest_board_smoke_text
    )
    items.append(
        AuditItem(
            "P2-SMOKE-TOOL",
            "PS/PC network",
            "Safe real-board TCP smoke wrapper exists and latest run avoided TX_DATA and FPGA programming.",
            status_from(board_smoke_safe_tool),
            f"{rel(board_smoke_script)}; {rel(latest_board_smoke)}",
            "Runs HELLO/STATUS only when a target host is known; latest summary is not a full board PASS unless SMOKE_VERDICT says so.",
        )
    )

    bridge_uart_ready = "UART_PROBE_VERDICT=PASS_PS_LWIP_BRIDGE_READY" in latest_uart_text
    board_smoke_pass = "SMOKE_VERDICT=PASS_REAL_BOARD_HELLO_STATUS" in latest_board_smoke_text
    items.append(
        AuditItem(
            "P2-BOARD",
            "PS/PC network",
            "Real AX7010 PS-to-PC TCP/DHCP smoke test passes.",
            "PASS" if board_smoke_pass else ("READY_TO_TEST_TCP" if bridge_uart_ready else "WAITING_HARDWARE"),
            f"{rel(latest_uart_probe)}; {rel(latest_board_smoke)}",
            "Needs TCP HELLO/STATUS acceptance against the real board; latest UART verdict="
            f"{uart_verdict}.",
        )
    )

    items.append(
        AuditItem(
            "P2-END2END",
            "End-to-end",
            "PC -> PS -> PL/IR -> peer -> PS -> PC end-to-end loop is verified.",
            "WAITING_HARDWARE",
            "",
            "Requires at least stable lane closed loop plus PS/PC real network smoke.",
        )
    )

    items.append(
        AuditItem(
            "M6",
            "2-lane protocol",
            "Current 2-lane protocol is restored on real hardware with low loss and no deadlock.",
            "WAITING_HARDWARE",
            "",
            "Raw pulse historical evidence is not sufficient; needs fresh UART/ILA/AXI evidence after JTAG recovery.",
        )
    )

    items.append(
        AuditItem(
            "M8",
            "Soak",
            "Stationary soak demonstrates sustained stable communication.",
            "NOT_STARTED",
            "",
            "Must obey TFDU runtime safety rule and shutdown after physical windows.",
        )
    )

    items.append(
        AuditItem(
            "M9",
            "Rotation",
            "20 cm shaft, 600 rpm, at least 2 h stable communication is verified.",
            "NOT_STARTED",
            "",
            "Final mechanical/rotation requirement; no current hardware evidence.",
        )
    )

    items.append(
        AuditItem(
            "M10",
            "Expansion",
            "4/8-lane expansion and final 32 Mbit/s half-duplex / 16 Mbit/s full-duplex targets are verified.",
            "NOT_STARTED",
            rel(latest_drc_triage),
            "Requires stable 2-lane baseline, PC-to-PC/soak evidence, and DRC fixes or formal waivers before expansion.",
        )
    )

    return items


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def render_markdown(items: list[AuditItem]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    rows = [
        [item.item_id, item.area, item.requirement, item.status, item.evidence, item.note]
        for item in items
    ]
    pass_claims = [
        item.requirement
        for item in items
        if item.status == "PASS"
    ]
    not_claims = [
        item.requirement
        for item in items
        if item.status != "PASS"
    ]
    return "\n".join(
        [
            "# RF_COMM Current Plan Completion Audit",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Status Counts",
            "",
            md_table(["status", "count"], [[key, str(value)] for key, value in sorted(counts.items())]),
            "",
            "## Requirement Evidence Table",
            "",
            md_table(["id", "area", "requirement", "status", "evidence", "note"], rows),
            "",
            "## Claims Currently Supported",
            "",
            "\n".join(f"- {claim}" for claim in pass_claims),
            "",
            "## Claims Not Yet Supported",
            "",
            "\n".join(f"- {claim}" for claim in not_claims),
            "",
            "## Next Unblocked Work",
            "",
            "- Keep running offline/software gates after changes.",
            "- Use `reports/plan_readiness_current_20260626.md` as the stage gate before any expansion or long hardware work.",
            "- After hardware/JTAG recovery, run `tools/run_p1_lane_mapping_matrix_safe.ps1` first.",
            "- Only after fresh matrix evidence passes, continue real 2-lane protocol and PS/PC board smoke.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="Markdown output path.")
    parser.add_argument("--json", type=Path, default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    items = collect_items()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or (REPORTS / f"plan_completion_audit_{stamp}.md")
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(items), encoding="utf-8")
    print(f"WROTE_MARKDOWN={out}")

    if args.json:
        json_out = args.json if args.json.is_absolute() else ROOT / args.json
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WROTE_JSON={json_out}")

    pass_count = sum(1 for item in items if item.status == "PASS")
    waiting_count = sum(1 for item in items if item.status == "WAITING_HARDWARE")
    missing_count = sum(1 for item in items if item.status in {"MISSING", "UNKNOWN"})
    print(f"PLAN_AUDIT_SUMMARY pass={pass_count} waiting_hardware={waiting_count} missing_or_unknown={missing_count} total={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
