#!/usr/bin/env python3
"""Audit RF_COMM plan.md checklist and milestones against current evidence."""

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
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class PlanItem:
    item_id: str
    plan_ref: str
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


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def contains(path: Path | None, pattern: str) -> bool:
    return re.search(pattern, read_text(path), re.MULTILINE | re.DOTALL) is not None


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def latest_matching(pattern: str, forbidden: list[str] | None = None) -> Path | None:
    forbidden = forbidden or []
    paths = sorted(ROOT.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
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
    return max(paths, key=lambda path: path.stat().st_mtime)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def collect_items() -> list[PlanItem]:
    constraint_sha = sha256(CONSTRAINT) if CONSTRAINT.exists() else "MISSING"
    hard_constraint_ok = constraint_sha == EXPECTED_CONSTRAINT_SHA256

    latest_preflight = latest("reports/hw_target_preflight_*.summary.txt")
    latest_matrix = latest("reports/2lane_matrix_safe_*.summary.txt")
    latest_resume = latest("reports/plan_hw_resume_safe_*.summary.txt")
    latest_jtag_diag = latest("reports/jtag_usb_diag_*.summary.txt")
    latest_p0_replay = latest("reports/p0_known_good_replay_safe_*.summary.txt")
    latest_p0_root = latest("reports/p0_rx_root_cause_safe_*.summary.txt")
    latest_p0_ack = latest("reports/p0_ack_only_safe_*.summary.txt")
    latest_p0_ack_build = latest("reports/p0_ack_only_build_*.summary.txt")
    latest_p1_mapping = latest("reports/p1_lane_mapping_matrix_safe_*.summary.txt")
    latest_p1_mapping_hw = latest_matching("reports/p1_lane_mapping_matrix_safe_*.summary.txt", forbidden=[r"(?m)^DRY_RUN=1\b"])
    latest_debug_decode = latest("reports/ila_2lane_matrix_analysis_debug_decode_current.md")
    latest_drc_triage = latest("reports/drc_triage_current_*.md")
    latest_readiness = latest("reports/plan_readiness_current_*.md")
    latest_readiness_json = latest("reports/plan_readiness_current_*.json")
    latest_snapshot = latest("reports/plan_execution_snapshot_current_*.md")
    latest_snapshot_json = latest("reports/plan_execution_snapshot_current_*.json")
    latest_active_guard = latest("reports/active_artifact_guard_current_*.md")
    latest_active_guard_json = latest("reports/active_artifact_guard_current_*.json")
    latest_jtag_blocker = latest_any("reports/jtag_blocker_current_*.md", "reports/jtag_blocker_analysis_current_*.md")
    latest_jtag_blocker_json = latest_any("reports/jtag_blocker_current_*.json", "reports/jtag_blocker_analysis_current_*.json")
    latest_jtag_checklist = latest("reports/jtag_recovery_checklist_current_*.md")
    latest_jtag_checklist_json = latest("reports/jtag_recovery_checklist_current_*.json")
    latest_jtag_recovery = latest("reports/jtag_recovery_then_resume_*.summary.txt")
    hw_text = read_text(latest_preflight) + "\n" + read_text(latest_matrix) + "\n" + read_text(latest_resume)
    jtag_pass = "HW_PREFLIGHT_RESULT PASS" in hw_text and "HW_PREFLIGHT_ZYNQ" in hw_text
    jtag_fail = "FAIL_NO_TARGET" in hw_text
    hw_wait = "READY_TO_RUN" if jtag_pass else "WAITING_HARDWARE"
    p1_hw_failed = (
        contains(latest_p1_mapping_hw, r"RUN_ILA_TIMEOUT")
        or contains(latest_p1_mapping_hw, r"RUN_MISSING_ILA_CSV")
        or contains(latest_p1_mapping_hw, r"MATRIX_EFFECTIVE_EXIT=[1-9]\d*")
    )
    jtag_replay_note = (
        "Safe replay wrapper exists; JTAG is currently visible, so the next proof is a fresh guarded hardware run."
        if jtag_pass
        else "Safe replay wrapper exists and currently blocks before programming because JTAG target is not visible."
    )

    sim_log = latest("reports/simulation_gates_2lane_stream_bidir_rxmicroscope_seq_*.out.log")
    sim_meta = latest("reports/simulation_gates_2lane_stream_bidir_rxmicroscope_seq_*.meta.txt")
    sim_rx_microscope = (
        contains(sim_meta, r"code=0")
        and contains(sim_log, r"AXI_RX_MICROSCOPE_SESSION_MISMATCH_PASS")
        and contains(sim_log, r"IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS")
    )

    project_log = latest("reports/project_gates_2lane_stream_bidir_ila_*.out.log")
    project_meta = latest("reports/project_gates_2lane_stream_bidir_ila_*.meta.txt")
    current_ila_build = (
        contains(project_meta, r"code=0")
        and contains(project_log, r"\[PASS\] bitstream")
        and contains(project_log, r"\[PASS\] timing")
        and contains(project_log, r"\[PASS\] utilization")
    )

    latest_offline = latest("reports/ps_pc_offline_gates_*.summary.txt")
    offline_pass = contains(latest_offline, r"PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1")

    boot_audit = ROOT / "reports/boot_artifact_audit_current_20260626.md"
    boot_audit_json = ROOT / "reports/boot_artifact_audit_current_20260626.json"
    boot_pass = (
        contains(boot_audit, r"\| ps_lwip_bridge \| PASS \|")
        and contains(boot_audit, r"\| ps_ps_loopback \| PASS \|")
        and contains(boot_audit, r"app markers missing: `none`")
    )

    latest_uart = latest("reports/ps_uart_boot_probe_*.summary.txt")
    latest_smoke = latest("reports/ps_pc_board_smoke_safe_*.summary.txt")
    board_smoke_pass = contains(latest_smoke, r"SMOKE_VERDICT=PASS_REAL_BOARD_HELLO_STATUS")
    uart_ready = contains(latest_uart, r"UART_PROBE_VERDICT=PASS_PS_LWIP_BRIDGE_READY")

    matrix_tool = ROOT / "tools/run_2lane_matrix_safe.ps1"
    p1_mapping_tool = ROOT / "tools/run_p1_lane_mapping_matrix_safe.ps1"
    matrix_analyzer = ROOT / "tools/analyze_2lane_ila_csv.py"
    matrix_tool_ready = matrix_tool.exists() and p1_mapping_tool.exists() and matrix_analyzer.exists()
    p0_replay_tool = ROOT / "tools/run_p0_known_good_replay_safe.ps1"
    p0_root_tool = ROOT / "tools/run_p0_rx_root_cause_safe.ps1"
    p0_ack_tool = ROOT / "tools/run_p0_ack_only_safe.ps1"
    p0_ack_build_tool = ROOT / "tools/build_p0_ack_only_artifacts.ps1"
    lane0_tool = ROOT / "tools/run_lane0_hw_once_safe.ps1"
    readiness_tool = ROOT / "tools/check_plan_readiness.py"
    snapshot_tool = ROOT / "tools/write_plan_execution_snapshot.py"
    active_guard_tool = ROOT / "tools/check_active_artifact_stage.py"
    jtag_blocker_tool = ROOT / "tools/analyze_jtag_blocker.py"
    jtag_checklist_tool = ROOT / "tools/write_jtag_recovery_checklist.py"

    evidence_lock = ROOT / "evidence_lock_20260625.csv"
    config_diff = ROOT / "config_diff_known_good_vs_current.md"

    items: list[PlanItem] = [
        PlanItem(
            "C0",
            "AGENTS.md / project constraint",
            "Hard project constraint is present and unchanged.",
            "PASS" if hard_constraint_ok else "FAIL",
            rel(CONSTRAINT),
            f"sha256={constraint_sha}",
        ),
        PlanItem(
            "P0-1",
            "plan section 16",
            "Generate evidence lock and known-good/current configuration diff.",
            "PASS" if evidence_lock.exists() and config_diff.exists() else "MISSING",
            f"{rel(evidence_lock)}; {rel(config_diff)}",
            "This is the only immediate checklist item fully completed without hardware.",
        ),
        PlanItem(
            "P0-2",
            "plan section 16",
            "Replay historical 2026-06-05 single-lane known-good configuration.",
            hw_wait,
            f"{rel(p0_replay_tool)}; {rel(lane0_tool)}; {rel(latest_p0_replay)}; {rel(latest_preflight)}; {rel(latest_jtag_diag)}",
            jtag_replay_note,
        ),
        PlanItem(
            "P0-3",
            "plan section 16",
            "Replay historical 2026-06-06 two-lane known-good configuration.",
            hw_wait,
            f"{rel(p0_replay_tool)}; {rel(latest_p0_replay)}; {rel(latest_matrix)}; {rel(latest_resume)}; {rel(latest_jtag_diag)}",
            "Safe replay wrapper targets b_tx_nonzero two-lane replay but needs fresh board evidence with sent>=1000, loss=0, tx_fail=0.",
        ),
        PlanItem(
            "P0-4",
            "plan section 16",
            "Run session/mask matching matrix and distinguish low-level RX from application checker failures.",
            "PARTIAL_SIM_PASS" if sim_rx_microscope else "MISSING",
            f"{rel(sim_log)}; {rel(sim_meta)}; {rel(p0_root_tool)}; {rel(latest_p0_root)}; {rel(latest_debug_decode)}",
            "Simulation has session/mismatch coverage and a safe current-build capture wrapper exists; true session/mask variant hardware cases still need JTAG and matching rebuild/config recipes.",
        ),
        PlanItem(
            "P0-5",
            "plan section 16",
            "Use RX microscope build to classify B-side failure point.",
            "READY_FOR_HARDWARE" if current_ila_build and sim_rx_microscope else "MISSING",
            f"{rel(project_log)}; {rel(project_meta)}; {rel(p0_root_tool)}; {rel(latest_p0_root)}; {rel(latest_debug_decode)}",
            "Current 2-lane ILA image, debug-aware offline analyzer, and safe RX-root-cause runner are ready, but no fresh hardware classification exists.",
        ),
        PlanItem(
            "P0-6",
            "plan section 16",
            "Run ACK-only build and verify ACK return path without B free-run payload.",
            hw_wait,
            f"{rel(p0_ack_tool)}; {rel(latest_p0_ack)}; {rel(latest_preflight)}; {rel(latest_matrix)}; {rel(latest_resume)}; {rel(latest_jtag_diag)}",
            "Requires a fresh lane RX pass, ACK-only bit/config evidence, JTAG access, and ACK counters/waveforms before hardware verification can pass.",
        ),
        PlanItem(
            "P0-6-TOOLS",
            "plan section 16",
            "Prepare a safe ACK-only runner that blocks without RX evidence or JTAG target visibility.",
            "PASS"
            if p0_ack_tool.exists()
            and contains(latest_p0_ack, r"P0_SCOPE=P0-6 ACK-only return-path orchestration")
            and contains(latest_p0_ack, r"ACK_ONLY_REQUIRED_CONFIG=")
            and (
                contains(latest_p0_ack, r"DRY_RUN_NO_HARDWARE_DONE=1")
                or contains(latest_p0_ack, r"P0_ACK_ONLY_BLOCKED_NO_RX_PASS_EVIDENCE=1")
                or contains(latest_p0_ack, r"P0_ACK_ONLY_BLOCKED_NO_PROGRAMMING=1")
            )
            else "MISSING",
            f"{rel(p0_ack_tool)}; {rel(latest_p0_ack)}",
            "Tooling is ready, but it does not prove P0-6 itself; the current latest run intentionally blocked before programming.",
        ),
        PlanItem(
            "P0-6-BUILD-TOOLS",
            "plan section 16",
            "Prepare a reproducible ACK-only bit/XSA/ELF build wrapper with ILA observability.",
            "PASS"
            if p0_ack_build_tool.exists()
            and contains(latest_p0_ack_build, r"BUILD_ENV IR_B_MODE=stream_bidir")
            and contains(latest_p0_ack_build, r"BUILD_ENV IR_B2A_ENABLE=0")
            and contains(latest_p0_ack_build, r"BUILD_ENV IR_B2A_FREE_RUN=0")
            and contains(latest_p0_ack_build, r"ILA_COMMAND=")
            and contains(latest_p0_ack_build, r"DRY_RUN_NO_VIVADO_DONE=1")
            else "MISSING",
            f"{rel(p0_ack_build_tool)}; {rel(latest_p0_ack_build)}",
            "Dry-run proves the recipe and commands only; P0-6 still needs a RunBuild artifact plus hardware ACK evidence.",
        ),
        PlanItem(
            "P1-1",
            "plan section 16",
            "Run lane mapping matrix for A/B, lane0/lane1, both directions.",
            "FAIL_HARDWARE" if p1_hw_failed else ("READY_FOR_HARDWARE" if matrix_tool_ready and not jtag_pass else "READY_TO_RUN"),
            f"{rel(p1_mapping_tool)}; {rel(matrix_tool)}; {rel(matrix_analyzer)}; {rel(latest_p1_mapping_hw)}",
            "Latest P1 hardware run stopped on a_tx_lane1: ILA timeout and missing CSV."
            if p1_hw_failed
            else "Safe lane-specific matrix runner exists for A lane0/lane1 and B lane0/lane1 triggers, and blocks before programming unless JTAG preflight passes.",
        ),
        PlanItem(
            "P1-2",
            "plan section 16",
            "Restore current two-lane protocol on real hardware.",
            "BLOCKED_BY_P1" if p1_hw_failed else hw_wait,
            "",
            "Depends on lane0/lane1 RX-only, ACK-only, and mapping matrix evidence.",
        ),
        PlanItem(
            "P2-1",
            "plan section 16",
            "Rebuild and audit BOOT.BIN against current bit/xsa/elf inputs.",
            "PASS" if boot_pass else "MISSING",
            f"{rel(boot_audit)}; {rel(boot_audit_json)}",
            "Audits local SD images only; does not prove SD boot on board.",
        ),
        PlanItem(
            "P2-2",
            "plan section 16",
            "Run PC-to-PC smoke over real AX7010 PS/PL/IR path.",
            "PASS" if board_smoke_pass else ("READY_TO_TEST_TCP" if uart_ready else "WAITING_HARDWARE"),
            f"{rel(latest_uart)}; {rel(latest_smoke)}; {rel(latest_offline)}",
            "Offline host/PS protocol gate passes, but real board TCP/IR path is not proven.",
        ),
        PlanItem(
            "P3",
            "plan section 16",
            "Proceed to 4/8-lane expansion and rotation testing.",
            "NOT_STARTED",
            rel(latest_drc_triage),
            "Blocked by plan prerequisites: 2-lane current pass, PC-to-PC pass, soak, and DRC/waiver work. DRC triage exists but release/expansion is not DRC-ready yet.",
        ),
        PlanItem(
            "P3-DRC-TRIAGE",
            "plan sections 13/16",
            "Current DRC/methodology warnings are classified into waiver candidates and pre-release actions.",
            "PASS" if latest_drc_triage is not None and contains(latest_drc_triage, r"TRIAGED_NOT_RELEASE_READY") else "MISSING",
            rel(latest_drc_triage),
            "This is a triage record, not a formal Vivado waiver or a claim that P3 may start.",
        ),
        PlanItem(
            "PLAN-READINESS",
            "supporting gate",
            "Evidence-backed stage readiness gate exists and blocks progression when prerequisites are missing.",
            "PASS"
            if readiness_tool.exists()
            and contains(latest_readiness, r"PLAN_READINESS_SUMMARY")
            and contains(latest_readiness, r"G1_JTAG_ACCESS")
            and contains(latest_readiness, r"BLOCKED_BY_PREREQUISITES")
            else "MISSING",
            f"{rel(readiness_tool)}; {rel(latest_readiness)}; {rel(latest_readiness_json)}",
            "This is a process gate; current readiness verdict is expected to remain blocked until hardware evidence exists.",
        ),
        PlanItem(
            "PLAN-SNAPSHOT",
            "supporting gate",
            "Current active artifact, ACK-only recipe, next commands, and safety state are captured in one snapshot.",
            "PASS"
            if snapshot_tool.exists()
            and contains(latest_snapshot, r"PLAN_EXECUTION_SNAPSHOT")
            and contains(latest_snapshot, r"active_artifact=2LANE_ILA_BASELINE")
            and contains(latest_snapshot, r"ack_only=DRY_RUN_RECIPE_ONLY")
            else "MISSING",
            f"{rel(snapshot_tool)}; {rel(latest_snapshot)}; {rel(latest_snapshot_json)}",
            "Snapshot prevents confusing the current P1 2-lane ILA baseline with the ACK-only dry-run recipe.",
        ),
        PlanItem(
            "ACTIVE-ARTIFACT-GUARD",
            "supporting gate",
            "Active artifact hashes are verified as the P1 two-lane ILA baseline before P1 hardware retry.",
            "PASS"
            if active_guard_tool.exists()
            and contains(latest_active_guard, r"ACTIVE_ARTIFACT_GUARD stage=P1_2LANE_ILA_BASELINE")
            and contains(latest_active_guard, r"result=PASS")
            else "MISSING",
            f"{rel(active_guard_tool)}; {rel(latest_active_guard)}; {rel(latest_active_guard_json)}",
            "This is a no-hardware guard; it does not prove lane connectivity.",
        ),
        PlanItem(
            "JTAG-BLOCKER-ANALYSIS",
            "supporting gate",
            "JTAG blocker is classified from USB/PnP/driver/preflight evidence.",
            "PASS"
            if jtag_blocker_tool.exists()
            and contains(latest_jtag_blocker, r"JTAG_BLOCKER_ANALYSIS status=(BLOCKED_NO_HW_TARGET|JTAG_READY)")
            and contains(latest_jtag_blocker, r"hardware_action=none programming=none tfdu_drive=none")
            else "MISSING",
            f"{rel(jtag_blocker_tool)}; {rel(latest_jtag_blocker)}; {rel(latest_jtag_blocker_json)}",
            "Diagnostic support only; the current preflight decides whether Vivado enumerates Zynq.",
        ),
        PlanItem(
            "JTAG-RECOVERY-CHECKLIST",
            "supporting gate",
            "AX7010 manual/PnP evidence is turned into an ordered JTAG recovery checklist.",
            "PASS"
            if jtag_checklist_tool.exists()
            and contains(latest_jtag_checklist, r"JTAG_RECOVERY_CHECKLIST classification=EXPECTED_AX7010_FT232HL_VISIBLE_BUT_NO_VIVADO_TARGET")
            and contains(latest_jtag_checklist, r"hardware_action=none programming=none tfdu_drive=none")
            else "MISSING",
            f"{rel(jtag_checklist_tool)}; {rel(latest_jtag_checklist)}; {rel(latest_jtag_checklist_json)}",
            "Checklist support only; JTAG access remains WAITING_HARDWARE until Vivado enumerates Zynq.",
        ),
        PlanItem(
            "JTAG-RECOVERY-CHAIN",
            "supporting gate",
            "Elevated driver-recovery dry-run is wired to the current P1 four-direction safe matrix entry.",
            "PASS"
            if latest_jtag_recovery is not None
            and contains(latest_jtag_recovery, r"RESUME_COMMAND=.*run_p1_lane_mapping_matrix_safe\.ps1")
            and contains(latest_jtag_recovery, r"TRIGGER_MODES=a_tx_lane0,a_tx_lane1,b_tx_lane0,b_tx_lane1")
            and contains(latest_jtag_recovery, r"MAX_TFDU_WINDOW_SECONDS=300")
            and contains(latest_jtag_recovery, r"NO_SYSTEM_DRIVER_CHANGE_DONE=1")
            and contains(latest_jtag_recovery, r"NO_RESUME_RUN_DONE=1")
            else "MISSING",
            f"{rel(latest_jtag_recovery)}; tools/run_jtag_driver_recovery_then_resume.ps1",
            "Dry-run support only; elevated recovery has not been applied in this shell.",
        ),
        PlanItem(
            "M0",
            "plan section 18",
            "Evidence freeze milestone.",
            "PASS" if evidence_lock.exists() and config_diff.exists() else "MISSING",
            f"{rel(evidence_lock)}; {rel(config_diff)}",
            "All later claims should reference artifact/config evidence.",
        ),
        PlanItem(
            "M1",
            "plan section 18",
            "Known-good lane0 reproduced on current hardware.",
            hw_wait,
            f"{rel(p0_replay_tool)}; {rel(lane0_tool)}; {rel(latest_p0_replay)}; {rel(latest_preflight)}; {rel(latest_jtag_diag)}",
            "Requires current fresh hardware run; replay tool is prepared and guarded by JTAG preflight.",
        ),
        PlanItem(
            "M2",
            "plan section 18",
            "Known-good two-lane reproduced on current hardware.",
            hw_wait,
            f"{rel(p0_replay_tool)}; {rel(latest_p0_replay)}; {rel(latest_matrix)}; {rel(latest_resume)}; {rel(latest_jtag_diag)}",
            "Requires current fresh hardware run; replay tool is prepared and guarded by JTAG preflight.",
        ),
        PlanItem(
            "M3",
            "plan section 18",
            "Current RX root cause classified.",
            "PARTIAL_SIM_PASS" if sim_rx_microscope else "MISSING",
            f"{rel(sim_log)}; {rel(project_log)}; {rel(p0_root_tool)}; {rel(latest_p0_root)}; {rel(latest_debug_decode)}",
            "Simulation/build/tooling support exists; current hardware failure class is not proven.",
        ),
        PlanItem(
            "M4",
            "plan section 18",
            "Lane0 current ACK closed.",
            hw_wait,
            "",
            "Requires B rx_good, B ACK TX, A ack_seen, and A tx_fail=0 on hardware.",
        ),
        PlanItem(
            "M5",
            "plan section 18",
            "Lane1 current ACK closed.",
            "BLOCKED_BY_P1" if p1_hw_failed else hw_wait,
            "",
            "Requires same proof as lane0 for lane1.",
        ),
        PlanItem(
            "M6",
            "plan section 18",
            "Two-lane current restored.",
            "BLOCKED_BY_P1" if p1_hw_failed else hw_wait,
            "",
            "Requires sent>=10000, loss<0.1%, and no deadlock on hardware.",
        ),
        PlanItem(
            "M7",
            "plan section 18",
            "PC-to-PC smoke passes through host, PS, PL, IR, peer, PS, host.",
            "PASS" if board_smoke_pass else "WAITING_HARDWARE",
            f"{rel(latest_uart)}; {rel(latest_smoke)}; {rel(latest_offline)}",
            "Latest real-board smoke is not PASS; offline mock is PASS.",
        ),
        PlanItem(
            "M8",
            "plan section 18",
            "Stationary soak passes.",
            "NOT_STARTED",
            "",
            "Must obey TFDU runtime limit and shutdown after physical windows.",
        ),
        PlanItem(
            "M9",
            "plan section 18",
            "600 rpm, about 20 cm shaft, 2-hour rotation test passes.",
            "NOT_STARTED",
            "",
            "Final mechanical validation has no current evidence.",
        ),
        PlanItem(
            "M10",
            "plan section 18",
            "4/8-lane expansion meets final throughput targets.",
            "NOT_STARTED",
            "",
            "Requires stable two-lane baseline and release/resource work first.",
        ),
        PlanItem(
            "P2-OFFLINE",
            "supporting gate",
            "PS/PC source-level DHCP/TCP/reconnect and host offline mock acceptance pass after latest host changes.",
            "PASS" if offline_pass else "FAIL",
            rel(latest_offline),
            "This is a support gate for P2; it is not a real-board TCP/DHCP pass.",
        ),
    ]
    return items


def render_markdown(items: list[PlanItem]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    rows = [
        [item.item_id, item.plan_ref, item.requirement, item.status, item.evidence, item.note]
        for item in items
    ]
    return "\n".join(
        [
            "# RF_COMM Plan Item Audit",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Status Counts",
            "",
            md_table(["status", "count"], [[key, str(value)] for key, value in sorted(counts.items())]),
            "",
            "## Item Evidence Table",
            "",
            md_table(["id", "plan_ref", "requirement", "status", "evidence", "note"], rows),
            "",
            "## Interpretation",
            "",
            "- PASS means the current evidence proves that item at the item scope.",
            "- PARTIAL_SIM_PASS means simulation/offline evidence exists, but plan hardware scope is not proven.",
            "- READY_FOR_HARDWARE means scripts/artifacts are prepared but hardware evidence is still required.",
            "- WAITING_HARDWARE means the next proof requires JTAG, SD boot, UART, TCP, or TFDU hardware state.",
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
    out = args.out or (REPORTS / f"plan_item_audit_{stamp}.md")
    out = out if out.is_absolute() else ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(items), encoding="utf-8")
    print(f"WROTE_MARKDOWN={out}")

    if args.json:
        json_out = args.json if args.json.is_absolute() else ROOT / args.json
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps([asdict(item) for item in items], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WROTE_JSON={json_out}")

    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    summary = " ".join(f"{key.lower()}={counts[key]}" for key in sorted(counts))
    print(f"PLAN_ITEM_AUDIT_SUMMARY {summary} total={len(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
