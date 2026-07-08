from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass(frozen=True)
class GuardRow:
    item: str
    guard: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def is_transient_file_lock(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (32, 33)


def write_text_with_retry(path: Path, text: str, encoding: str = "utf-8", max_wait_seconds: int = 120) -> None:
    start = time.monotonic()
    announced = False
    while True:
        try:
            path.write_text(text, encoding=encoding)
            if announced:
                elapsed = int(time.monotonic() - start)
                print(f"WAIT_FILE_CLEAR path={path} elapsed_s={elapsed}")
            return
        except OSError as exc:
            if not is_transient_file_lock(exc):
                raise
            elapsed = time.monotonic() - start
            if elapsed >= max_wait_seconds:
                print(f"WAIT_FILE_TIMEOUT path={path} elapsed_s={int(elapsed)} error={exc}")
                raise
            if not announced:
                print(f"WAIT_FILE_LOCK path={path} error={exc}")
                announced = True
            time.sleep(1)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def add(rows: list[GuardRow], item: str, guard: str, ok: bool, evidence: Path | None, pass_note: str, fail_note: str) -> None:
    rows.append(GuardRow(item, guard, "PASS" if ok else "FAIL", rel(evidence), pass_note if ok else fail_note))


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if contains_all(text, needles):
            return path
    return None


def wrapper_common_guard(text: str) -> bool:
    return contains_all(
        text,
        [
            "[switch]$AllowTraffic",
            "[switch]$DryRun",
            "$maxContinuousRunSeconds = 600",
            "if ($effectiveDurationSeconds -gt $maxContinuousRunSeconds)",
            "$effectiveDurationSeconds = $maxContinuousRunSeconds",
            "Write-SummaryLine \"DURATION_SECONDS_EFFECTIVE=$effectiveDurationSeconds\"",
            "$blockedReasons.Add(\"allow_traffic_not_set\")",
            "NO_TX_DATA_TO_REAL_BOARDS=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
            "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=0",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
            "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=1",
            "ethernet_link_not_up",
        ],
    )


def shutdown_after_guard(text: str) -> bool:
    return contains_all(
        text,
        [
            "[switch]$ProgramShutdownAfterRun",
            "$blockedReasons.Add(\"program_shutdown_after_run_not_set\")",
            "PROGRAM_SHUTDOWN_AFTER_RUN=$([int]$ProgramShutdownAfterRun.IsPresent)",
        ],
    )


def physical_matrix_gate_guard(text: str) -> bool:
    return contains_all(
        text,
        [
            "$physicalGateScript = Join-Path $repoRoot \"tools\\check_physical_matrix_gate.ps1\"",
            "function Invoke-PhysicalMatrixGate",
            "PHYSICAL_MATRIX_GATE_EXIT=$exitCode",
            "$blockedReasons.Add(\"physical_matrix_not_passing\")",
            "NO_TX_DATA_TO_REAL_BOARDS_FINAL=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT_FINAL=1",
        ],
    )


def build_rows() -> tuple[list[GuardRow], dict[str, str]]:
    constraint = find_constraint()
    physical_gate = ROOT / "tools" / "check_physical_matrix_gate.ps1"
    ps_pc = ROOT / "tools" / "run_ps_pc_tcp_dhcp_acceptance_safe.ps1"
    two_ax = ROOT / "tools" / "run_two_ax7010_end_to_end_acceptance_safe.ps1"
    product = ROOT / "tools" / "run_product_loop_acceptance_safe.ps1"
    rotating = ROOT / "tools" / "run_rotating_shaft_acceptance_safe.ps1"
    eightlane = ROOT / "tools" / "run_8lane_hardware_acceptance_safe.ps1"
    sequence = ROOT / "tools" / "run_real_acceptance_sequence_safe.ps1"
    p1_lane_mapping = ROOT / "tools" / "run_p1_lane_mapping_matrix_safe.ps1"
    md_p7_resume = ROOT / "tools" / "run_md_p7_resume_safe.ps1"
    failed_link_retest = ROOT / "tools" / "run_failed_2lane_links_safe.ps1"
    repeat_failure_guard = ROOT / "tools" / "check_repeat_physical_failure_guard.py"
    physical_snapshot_builder = ROOT / "tools" / "build_2lane_physical_failure_snapshot.py"
    two_lane_matrix = ROOT / "tools" / "run_2lane_matrix_safe.ps1"
    two_lane_prearmed = ROOT / "tools" / "run_2lane_hw_prearmed_ila_safe.ps1"
    sequence_summary = REPORTS / "real_acceptance_sequence_safe_current.summary.txt"
    sequence_md = REPORTS / "real_acceptance_sequence_safe_current.md"
    sequence_csv = REPORTS / "real_acceptance_sequence_safe_current.stages.csv"
    readiness_md = REPORTS / "remaining_acceptance_readiness_current.md"
    duration_cap_md = REPORTS / "duration_cap_compliance_current.md"
    promotion_gate_md = REPORTS / "real_acceptance_promotion_gate_current.md"
    physical_gate_selftest_md = REPORTS / "physical_matrix_gate_selftest_current.md"

    physical_gate_text = read_text(physical_gate)
    ps_pc_text = read_text(ps_pc)
    two_ax_text = read_text(two_ax)
    product_text = read_text(product)
    rotating_text = read_text(rotating)
    eightlane_text = read_text(eightlane)
    sequence_text = read_text(sequence)
    p1_lane_mapping_text = read_text(p1_lane_mapping)
    md_p7_resume_text = read_text(md_p7_resume)
    failed_link_retest_text = read_text(failed_link_retest)
    repeat_failure_guard_text = read_text(repeat_failure_guard)
    physical_snapshot_builder_text = read_text(physical_snapshot_builder)
    two_lane_matrix_text = read_text(two_lane_matrix)
    two_lane_prearmed_text = read_text(two_lane_prearmed)
    sequence_summary_text = read_text(sequence_summary)
    sequence_md_text = read_text(sequence_md)
    sequence_csv_text = read_text(sequence_csv)
    readiness_text = read_text(readiness_md)
    duration_cap_text = read_text(duration_cap_md)
    promotion_text = read_text(promotion_gate_md)
    physical_gate_selftest_text = read_text(physical_gate_selftest_md)

    two_ax_dryrun = latest_containing(
        "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
        ["TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"],
    )
    product_dryrun = latest_containing(
        "reports/product_loop_acceptance_safe_*.summary.txt",
        ["PRODUCT_LOOP_DRY_RUN=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"],
    )
    rotating_dryrun = latest_containing(
        "reports/rotating_shaft_acceptance_safe_*.summary.txt",
        ["ROTATING_SHAFT_DRY_RUN=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"],
    )
    eightlane_dryrun = latest_containing(
        "reports/8lane_hardware_acceptance_safe_*.summary.txt",
        ["EIGHT_LANE_HARDWARE_DRY_RUN=1", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1"],
    )
    p1_dryrun = latest_containing(
        "reports/p1_lane_mapping_matrix_safe_*.summary.txt",
        ["DRY_RUN=1", "DRY_RUN_NO_HARDWARE_DONE=1"],
    )
    md_p7_resume_dryrun = latest_containing(
        "reports/md_p7_resume_safe_*.summary.txt",
        ["EFFECTIVE_DRY_RUN=1", "FAILED_LINK_RETEST_EXIT=0", "NO_TFDU_DRIVE=1"],
    )
    md_p7_resume_refresh_only = latest_containing(
        "reports/md_p7_resume_safe_*.summary.txt",
        [
            "REFRESH_P7_ARTIFACTS_ONLY=1",
            "REFRESH_ONLY_NO_CHILD_RETEST=1",
            "P7_01_DELIVERABLE_REFRESH_EXIT=0",
            "NO_TFDU_DRIVE=1",
        ],
    )
    md_p7_resume_marker_timeout = latest_containing(
        "reports/md_p7_resume_safe_*.summary.txt",
        [
            "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER=1",
            "REAL_RUN_REQUESTED=1",
            "WAIT_PHYSICAL_ADJUSTMENT_MARKER_TIMEOUT",
            "NO_TFDU_DRIVE=1",
        ],
    )
    md_p7_resume_stale_marker_timeout = latest_containing(
        "reports/md_p7_resume_safe_*.summary.txt",
        [
            "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER=1",
            "ALLOW_EXISTING_PHYSICAL_ADJUSTMENT_MARKER=0",
            "WAIT_PHYSICAL_ADJUSTMENT_MARKER_STALE",
            "reason=marker_older_than_wait_start",
            "NO_TFDU_DRIVE=1",
        ],
    )
    md_p7_resume_marker_only_clear = latest_containing(
        "reports/md_p7_resume_safe_*.summary.txt",
        [
            "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER_ONLY=1",
            "MARKER_ONLY_NO_CHILD_RETEST=1",
            "WAIT_PHYSICAL_ADJUSTMENT_MARKER_CLEAR",
            "MARKER_ONLY_EXIT=0",
            "NO_TFDU_DRIVE=1",
        ],
    )
    two_lane_matrix_autobuild_restore = latest_containing(
        "reports/2lane_matrix_safe_*.summary.txt",
        [
            "AUTO_BUILD_PS_ELF_PER_TRIGGER=1",
            "GUARD_ONLY=1",
            "GUARD_ONLY_NO_HARDWARE_PROGRAMMING=1",
            "GUARD_ONLY_NO_UART_WRITE=1",
            "GUARD_ONLY_NO_TFDU_DRIVE=1",
            "AUTOBUILD_ELF_RESTORE_REQUIRED=1",
            "AUTOBUILD_ELF_RESTORE_OK=1",
            "MATRIX_OVERALL_EXIT=0",
        ],
    )
    failed_link_retest_dryrun = latest_containing(
        "reports/failed_2lane_links_safe_*.summary.txt",
        ["DRY_RUN=1", "EFFECTIVE_DRY_RUN=1", "WAIT_SKIPPED_DRY_RUN=1", "NO_TFDU_DRIVE=1"],
    )
    failed_link_wait_only = latest_containing(
        "reports/failed_2lane_links_safe_*.summary.txt",
        ["WAIT_ONLY=1", "WAIT_ONLY_TRANSIENT_BLOCKER_CHECK=1", "NO_TFDU_DRIVE=1"],
    )
    repeat_failure_guard_blocked = latest_containing(
        "reports/repeat_physical_failure_guard_*.md",
        ["RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall=BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT", "NO_TFDU_DRIVE=1"],
    )
    failed_link_retest_repeat_block = latest_containing(
        "reports/failed_2lane_links_safe_*.summary.txt",
        ["REPEAT_FAILURE_GUARD_BLOCKED=1", "PHYSICAL_ADJUSTMENT_REQUIRED_BEFORE_REAL_RETEST=1", "NO_TFDU_DRIVE=1"],
    )

    two_ax_dryrun_text = read_text(two_ax_dryrun)
    product_dryrun_text = read_text(product_dryrun)
    rotating_dryrun_text = read_text(rotating_dryrun)
    eightlane_dryrun_text = read_text(eightlane_dryrun)
    p1_dryrun_text = read_text(p1_dryrun)
    md_p7_resume_dryrun_text = read_text(md_p7_resume_dryrun)
    md_p7_resume_refresh_only_text = read_text(md_p7_resume_refresh_only)
    md_p7_resume_marker_timeout_text = read_text(md_p7_resume_marker_timeout)
    md_p7_resume_stale_marker_timeout_text = read_text(md_p7_resume_stale_marker_timeout)
    md_p7_resume_marker_only_clear_text = read_text(md_p7_resume_marker_only_clear)
    two_lane_matrix_autobuild_restore_text = read_text(two_lane_matrix_autobuild_restore)
    failed_link_retest_dryrun_text = read_text(failed_link_retest_dryrun)
    failed_link_wait_only_text = read_text(failed_link_wait_only)
    repeat_failure_guard_blocked_text = read_text(repeat_failure_guard_blocked)
    failed_link_retest_repeat_block_text = read_text(failed_link_retest_repeat_block)

    rows: list[GuardRow] = []
    add(
        rows,
        "GLOBAL",
        "hard_constraint_unchanged",
        constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256,
        constraint,
        f"sha256={sha256(constraint)}",
        "hard constraint is missing or changed",
    )
    add(
        rows,
        "N03",
        "network_only_no_tfdu_or_fpga",
        contains_all(
            ps_pc_text,
            [
                "[switch]$DryRun",
                "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1",
                "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
                "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1",
                "BOARD_TCP_DHCP_BLOCKED_REASON=$reason",
                "BOARD_TCP_DHCP_ACCEPTANCE_PASS=0",
                "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=1",
                "ethernet_link_not_up",
                "exit 20",
            ],
        ),
        ps_pc,
        "board TCP/DHCP wrapper is network-only and records no FPGA programming, no TFDU drive, and no IR TX data",
        "board TCP/DHCP wrapper no-side-effect or no-Ethernet guard is incomplete",
    )
    add(
        rows,
        "GLOBAL",
        "physical_matrix_gate_script_blocks_required_link_failures",
        contains_all(
            physical_gate_text,
            [
                "classify_2lane_physical_matrix.py",
                "--latest-by-link",
                "--require-links",
                "PHYSICAL_MATRIX_GATE_RESULT=PASS",
                "PHYSICAL_MATRIX_GATE_RESULT=BLOCK",
            ],
        ),
        physical_gate,
        "shared physical-matrix gate classifies latest lane evidence and blocks when required links are not passing",
        "shared physical-matrix gate is missing or does not block required-link failures",
    )
    add(
        rows,
        "GLOBAL",
        "physical_matrix_gate_selftest_passes",
        contains_all(
            physical_gate_selftest_text,
            [
                "RF_COMM_PHYSICAL_MATRIX_GATE_SELFTEST overall=PASS cases=4 checks=8 failures=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        physical_gate_selftest_md,
        "physical-matrix gate self-test proves pass, required-link fail, missing-link fail, and latest-by-link behavior",
        "physical-matrix gate self-test is missing or failing",
    )
    add(
        rows,
        "N04",
        "two_ax7010_real_traffic_guard",
        wrapper_common_guard(two_ax_text)
        and shutdown_after_guard(two_ax_text)
        and "$willUseRealTraffic = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent -and -not $OfflineModel.IsPresent)" in two_ax_text
        and "$blockedReasons.Add(\"tcp_a_not_reachable\")" in two_ax_text
        and "$blockedReasons.Add(\"tcp_b_not_reachable\")" in two_ax_text,
        two_ax,
        "two-AX7010 wrapper requires AllowTraffic, shutdown-after-run, non-dry-run mode, TCP reachability, and 600 s cap before real TFDU traffic",
        "two-AX7010 wrapper guard contract is incomplete",
    )
    add(
        rows,
        "N04",
        "two_ax7010_requires_physical_matrix_gate",
        physical_matrix_gate_guard(two_ax_text),
        two_ax,
        "two-AX7010 real traffic is blocked until the required 2lane physical matrix links pass",
        "two-AX7010 wrapper is missing the physical-matrix gate or final no-drive markers",
    )
    add(
        rows,
        "A01",
        "product_loop_real_traffic_guard",
        wrapper_common_guard(product_text)
        and shutdown_after_guard(product_text)
        and "$willUseRealTraffic = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent)" in product_text
        and "$blockedReasons.Add(\"tcp_a_not_reachable\")" in product_text
        and "$blockedReasons.Add(\"tcp_b_not_reachable\")" in product_text
        and "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=0" in product_text,
        product,
        "product-loop wrapper requires AllowTraffic, shutdown-after-run, non-dry-run mode, TCP reachability, and 600 s cap before real product-loop TFDU traffic",
        "product-loop wrapper guard contract is incomplete",
    )
    add(
        rows,
        "A01",
        "product_loop_requires_physical_matrix_gate",
        physical_matrix_gate_guard(product_text),
        product,
        "product-loop real traffic is blocked until the required 2lane physical matrix links pass",
        "product-loop wrapper is missing the physical-matrix gate or final no-drive markers",
    )
    add(
        rows,
        "S05",
        "rotating_shaft_fixture_and_shutdown_guard",
        wrapper_common_guard(rotating_text)
        and shutdown_after_guard(rotating_text)
        and contains_all(
            rotating_text,
            [
                "shaft_diameter_target_out_of_range",
                "rpm_target_out_of_range",
                "fixture_log_required_for_real_acceptance",
                "fixture_log_invalid",
                "TARGET_DIAMETER_OK=$([int]$diameterTargetOk)",
                "TARGET_RPM_OK=$([int]$rpmTargetOk)",
                "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=0",
            ],
        ),
        rotating,
        "rotating wrapper requires target 200 mm / 600 rpm metadata, real fixture log, AllowTraffic, shutdown-after-run, TCP reachability, and 600 s cap",
        "rotating-shaft wrapper fixture/shutdown guard contract is incomplete",
    )
    add(
        rows,
        "S05",
        "rotating_shaft_requires_physical_matrix_gate",
        physical_matrix_gate_guard(rotating_text) and "NO_HARDWARE_PROGRAMMING_DONE_BY_THIS_SCRIPT_FINAL=1" in rotating_text,
        rotating,
        "rotating-shaft real traffic is blocked until the required 2lane physical matrix links pass",
        "rotating-shaft wrapper is missing the physical-matrix gate or final no-drive/no-programming markers",
    )
    add(
        rows,
        "A02",
        "eightlane_review_shutdown_and_pinmap_guard",
        contains_all(
            eightlane_text,
            [
                "[switch]$PinmapReviewed",
                "[switch]$ShutdownBitstreamReviewed",
                "[switch]$ProgramShutdownBeforeRun",
                "[switch]$ProgramShutdownAfterRun",
                "[switch]$AllowTraffic",
                "[switch]$DryRun",
                "$maxContinuousRunSeconds = 600",
                "$blockedReasons.Add(\"allow_traffic_not_set\")",
                "$blockedReasons.Add(\"pinmap_not_reviewed\")",
                "$blockedReasons.Add(\"shutdown_bitstream_not_reviewed\")",
                "$blockedReasons.Add(\"program_shutdown_before_run_not_set\")",
                "$blockedReasons.Add(\"program_shutdown_after_run_not_set\")",
                "SHUTDOWN_REQUIRED_BEFORE_THIS_RUN=1",
                "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=1",
                "SHUTDOWN_REQUIRED_BEFORE_THIS_RUN=0",
                "SHUTDOWN_REQUIRED_AFTER_THIS_RUN=0",
                "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
                "NO_TX_DATA_TO_REAL_BOARDS=1",
                "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=0",
            ],
        ),
        eightlane,
        "8-lane wrapper requires pinmap review, shutdown-bitstream review, shutdown-before, shutdown-after, AllowTraffic, TCP reachability, and 600 s cap before real 8-TFDU traffic",
        "8-lane wrapper review/shutdown guard contract is incomplete",
    )
    add(
        rows,
        "A02",
        "eightlane_requires_physical_matrix_gate",
        physical_matrix_gate_guard(eightlane_text) and "NO_HARDWARE_PROGRAMMING_DONE_BY_THIS_SCRIPT_FINAL=1" in eightlane_text,
        eightlane,
        "8-lane real hardware acceptance is blocked until the required 2lane physical matrix links pass",
        "8-lane wrapper is missing the physical-matrix gate or final no-drive/no-programming markers",
    )
    add(
        rows,
        "SEQUENCE",
        "preflight_blocks_wrappers_before_real_traffic",
        contains_all(
            sequence_text,
            [
                "$blockDuePreflight = ($preflightBlockers.Count -gt 0 -and -not $SkipPreflightBlock.IsPresent)",
                "STAGE_BLOCKED id=$($plan.Id) reason=$blockedReason",
                "RequiresTrafficSwitch = $true",
                "DrivesTfdu = $true",
                "WRAPPER_DRY_RUN name=$Name",
                "EXECUTED_WRAPPERS=$executedWrappers",
                "NO_HARDWARE_PROGRAMMING=$noHardwareProgramming",
                "NO_UART_WRITE=$noUartWrite",
                "NO_TFDU_DRIVE=$noTfduDrive",
            ],
        ),
        sequence,
        "top-level sequence runs preflight/readiness first and blocks real wrappers under current blockers unless explicitly bypassed",
        "top-level sequence preflight/wrapper guard contract is incomplete",
    )
    add(
        rows,
        "SEQUENCE",
        "current_no_ethernet_executes_zero_wrappers",
        contains_all(
            sequence_summary_text + "\n" + sequence_md_text + "\n" + sequence_csv_text,
            [
                "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET stages=5",
                "PREFLIGHT_OVERALL=BLOCKED_NO_ETHERNET",
                "EXECUTED_WRAPPERS=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        )
        and sequence_csv_text.count(',"0","1"') >= 5,
        sequence_summary,
        "current no-Ethernet sequence plans all five stages but executes zero hardware wrappers",
        "current safe sequence no-Ethernet evidence is incomplete",
    )
    add(
        rows,
        "P1",
        "lane_mapping_parent_timeout_emergency_shutdown",
        contains_all(
            p1_lane_mapping_text,
            [
                "function Invoke-EmergencyShutdown",
                "program_tfdu_shutdown.tcl",
                "EMERGENCY_SHUTDOWN_START reason=$Reason",
                "if ($matrixExitRaw -eq 124)",
                "MATRIX_EMERGENCY_SHUTDOWN_EXIT=$emergencyShutdownExit",
                "MATRIX_REPORTED_OVERALL_EXIT=$matrixReportedOverallExit",
                "MATRIX_EXIT_OVERRIDDEN_BY_REPORTED_OVERALL_EXIT=1",
                "NO_TFDU_DRIVE_BEFORE_PREFLIGHT_PASS=1",
            ],
        ),
        p1_lane_mapping,
        "P1 parent wrapper runs emergency shutdown if the matrix child times out, blocks TFDU drive before preflight pass, and propagates reported matrix gate failures",
        "P1 parent wrapper lacks emergency shutdown, preflight TFDU guard markers, or reported matrix failure propagation",
    )
    add(
        rows,
        "P1",
        "two_lane_matrix_timeout_and_shutdown_after_each_run",
        contains_all(
            two_lane_matrix_text,
            [
                "function Invoke-EmergencyShutdown",
                "single_run_process_timeout",
                "RUN_EMERGENCY_SHUTDOWN trigger=$mode",
                "shutdown_after_run_missing_or_failed=1",
                "RUN_STOP_ON_SHUTDOWN_FAIL trigger=$mode",
                "RUN_SAFETY_VIOLATION trigger=$mode tfdu_window_s=$tfduWindow limit_s=$MaxTfduWindowSeconds",
                "[void](Write-SummaryLine \"MATRIX_ANALYSIS_FAIL_VERDICTS=$($failures -join ',')\")",
                "$analysisPassResult = @(Test-MatrixAnalysisPass -JsonPath $matrixAnalysisJson)",
                "MATRIX_ANALYSIS_PASS_PARSED=$([int]$analysisPassed)",
                "MATRIX_OVERALL_EXIT=$overallExit",
            ],
        ),
        two_lane_matrix,
        "2lane matrix wrapper emergency-shuts down timed-out child runs, fails if shutdown-after-run evidence is missing, and propagates ILA analysis failures",
        "2lane matrix wrapper lacks timeout emergency shutdown, shutdown-after-run enforcement, window cap checks, or ILA failure propagation",
    )
    add(
        rows,
        "P1",
        "two_lane_matrix_autobuild_restores_original_ps_elf",
        contains_all(
            two_lane_matrix_text,
            [
                "function Copy-ItemWithRetry",
                "WAIT_FILE_COPY_LOCK source=$Source destination=$Destination",
                "$autoBuildElfPath = Join-Path $repoRoot \"software\\_vitis_ws_ps_ps_loopback\\rf_comm_ps_ps_loopback\\Debug\\rf_comm_ps_ps_loopback.elf\"",
                "function Backup-AutoBuildElf",
                "AUTOBUILD_ELF_RESTORE_REQUIRED=1",
                "AUTOBUILD_ELF_ORIGINAL_SHA256=$script:AutoBuildElfOriginalHash",
                "AUTOBUILD_ELF_BACKUP_PATH=$script:AutoBuildElfBackupPath",
                "function Restore-AutoBuildElf",
                "AUTOBUILD_ELF_RESTORED_SHA256=$restoredHash",
                "AUTOBUILD_ELF_RESTORE_OK=$([int]$restoreOk)",
                "$autoBuildRestoreOk = @(Restore-AutoBuildElf)",
                "$overallExit = 32",
            ],
        ),
        two_lane_matrix,
        "2lane matrix wrapper backs up and restores the original PS ELF after per-trigger auto-builds, with file-lock wait/retry around backup and restore copies",
        "2lane matrix wrapper can auto-build trigger ELFs without proving original ELF restoration or file-lock wait/retry",
    )
    add(
        rows,
        "P1",
        "latest_two_lane_matrix_autobuild_restore_no_hardware",
        contains_all(
            two_lane_matrix_autobuild_restore_text,
            [
                "AUTO_BUILD_PS_ELF_PER_TRIGGER=1",
                "GUARD_ONLY=1",
                "GUARD_ONLY_NO_HARDWARE_PROGRAMMING=1",
                "GUARD_ONLY_NO_UART_WRITE=1",
                "GUARD_ONLY_NO_TFDU_DRIVE=1",
                "TRIGGER_MODES=b_tx_lane1",
                "RUN_AUTOBUILD_MATCH trigger=b_tx_lane1 TRIGGER_MODE=b_tx_lane1",
                "AUTOBUILD_ELF_ORIGINAL_SHA256=",
                "AUTOBUILD_ELF_RESTORED_SHA256=",
                "AUTOBUILD_ELF_RESTORE_OK=1",
                "MATRIX_OVERALL_EXIT=0",
            ],
        ),
        two_lane_matrix_autobuild_restore,
        "latest 2lane matrix GuardOnly auto-build exercised b_tx_lane1 trigger ELF generation and restored the original PS ELF without hardware, UART, or TFDU action",
        "latest 2lane matrix GuardOnly auto-build restore evidence is missing or lacks no-hardware/restored-ELF markers",
    )
    add(
        rows,
        "P1",
        "prearmed_single_run_finally_shutdown",
        contains_all(
            two_lane_prearmed_text,
            [
                "finally {",
                "SHUTDOWN_START=$($shutdownStart.ToString('o'))",
                "program_tfdu_shutdown.tcl",
                "SHUTDOWN_TIMEOUT_SECONDS=$ShutdownTimeoutSeconds",
                "SHUTDOWN_TIMEOUT_KILLED=1",
                "HW_WINDOW_TO_SHUTDOWN_END_SECONDS",
                "RUN_RESULT_STATUS=FAIL_SHUTDOWN",
            ],
        ),
        two_lane_prearmed,
        "single prearmed 2lane run programs shutdown in finally, records the TFDU window, and fails if shutdown fails",
        "single prearmed 2lane run lacks finally-shutdown, timeout, window, or failure markers",
    )
    add(
        rows,
        "P1",
        "latest_p1_dryrun_no_hardware",
        contains_all(
            p1_dryrun_text,
            [
                "DRY_RUN=1",
                "DRY_RUN_NO_ARTIFACT_GUARD_DONE=1",
                "DRY_RUN_NO_PREFLIGHT_DONE=1",
                "DRY_RUN_NO_HARDWARE_DONE=1",
            ],
        ),
        p1_dryrun,
        "latest P1 dry-run exercised the safe command path without hardware, UART, or TFDU action",
        "latest P1 dry-run evidence is missing or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "current_report_writers_wait_on_file_locks",
        contains_all(
            physical_snapshot_builder_text + "\n" + read_text(ROOT / "tools" / "check_safe_wrapper_guard_contract.py"),
            [
                "def write_text_with_retry",
                "WAIT_FILE_LOCK path=",
                "WAIT_FILE_CLEAR path=",
                "getattr(exc, \"winerror\", None) in (32, 33)",
                "write_text_with_retry(json_path",
                "write_text_with_retry(csv_path",
                "write_text_with_retry(md_path",
            ],
        ),
        physical_snapshot_builder,
        "shared current-report writers wait and retry on transient file locks before writing snapshot and guard-contract outputs",
        "current-report writers do not prove file-lock wait/retry behavior for shared current outputs",
    )
    add(
        rows,
        "P1",
        "p7_wrapper_summary_writers_wait_on_file_locks",
        all(
            contains_all(
                text,
                [
                    "function Test-TransientFileWriteBlock",
                    "function Write-TextFileWithRetry",
                    "WAIT_FILE_LOCK path=$Path",
                    "WAIT_FILE_CLEAR path=$Path",
                    "WAIT_FILE_TIMEOUT path=$Path",
                    "function Add-ContentWithRetry",
                    "function Set-ContentWithRetry",
                    "Add-ContentWithRetry -Path $summaryLog -Value $Line",
                    "Set-ContentWithRetry -Path $summaryLog",
                ],
            )
            for text in [md_p7_resume_text, failed_link_retest_text, p1_lane_mapping_text, two_lane_matrix_text]
        ),
        md_p7_resume,
        "P7 MD resume, failed-link, P1 parent, and 2lane matrix wrappers wait and retry on transient summary file locks",
        "one or more P7 wrapper summary writers lack file-lock wait/retry markers",
    )
    add(
        rows,
        "P1",
        "md_p7_resume_stage_gate_preserves_p7_2_and_default_dryrun",
        contains_all(
            md_p7_resume_text,
            [
                "[switch]$AllowTraffic",
                "[switch]$PhysicalAdjusted",
                "[string]$PhysicalAdjustmentNote = \"\"",
                "[switch]$WaitForPhysicalAdjustmentMarker",
                "[switch]$WaitForPhysicalAdjustmentMarkerOnly",
                "[string]$PhysicalAdjustmentMarkerPath = \"\"",
                "[switch]$AllowExistingPhysicalAdjustmentMarker",
                "[switch]$DryRun",
                "[switch]$RefreshP7ArtifactsOnly",
                "$effectiveDryRun = ($DryRun.IsPresent -or -not $AllowTraffic.IsPresent)",
                "function Wait-PhysicalAdjustmentMarker",
                "$freshEnough = ($AllowExistingPhysicalAdjustmentMarker.IsPresent -or $markerLastWrite -ge $start)",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_STALE path=$Path",
                "marker_older_than_wait_start",
                "ALLOW_EXISTING_PHYSICAL_ADJUSTMENT_MARKER=$([int]$AllowExistingPhysicalAdjustmentMarker.IsPresent)",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_ENABLED=1",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_CLEAR path=$Path",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_TIMEOUT path=$Path",
                "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER_ONLY=$([int]$WaitForPhysicalAdjustmentMarkerOnly.IsPresent)",
                "MARKER_ONLY_NO_CHILD_RETEST=1",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_ONLY_IMPLIES_WAIT=1",
                "PHYSICAL_ADJUSTMENT_DECLARED_SOURCE=marker_only",
                "MARKER_ONLY_EXIT=0",
                "PHYSICAL_ADJUSTMENT_DECLARED_SOURCE=marker",
                "PHYSICAL_ADJUSTED_EFFECTIVE=$([int]$physicalAdjustedEffective)",
                "PHYSICAL_ADJUSTMENT_NOTE_EFFECTIVE=$physicalAdjustmentNoteEffective",
                "run_failed_2lane_links_safe.ps1",
                "NO_P7_3_BEFORE_P7_2_RAW_PASS=1",
                "TRANSIENT_BLOCKER_WAIT_DELEGATED_TO_CHILD_WRAPPERS=1",
                "PHYSICAL_ADJUSTMENT_REQUIRED_BEFORE_REAL_RETEST=1",
                "PHYSICAL_ADJUSTMENT_NOTE_REQUIRED=1",
                "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        md_p7_resume,
        "MD P7 resume wrapper preserves the P7.2 gate, defaults to dry-run without AllowTraffic, requires physical-adjustment notes for stale physical failures, and delegates transient waiting to child wrappers",
        "MD P7 resume wrapper is missing the P7.2 gate, default dry-run behavior, physical-adjustment guard, or no-drive markers",
    )
    add(
        rows,
        "P1",
        "md_p7_resume_refreshes_p7_01_after_real_retest",
        contains_all(
            md_p7_resume_text,
            [
                "$p7RawDeliverablesBuilder = Join-Path $repoRoot \"tools\\build_p7_2_raw_matrix_deliverables.py\"",
                "[switch]$RefreshP7ArtifactsOnly",
                "REFRESH_ONLY_NO_CHILD_RETEST=1",
                "REFRESH_ONLY_NO_HARDWARE_PROGRAMMING=1",
                "REFRESH_ONLY_NO_UART_WRITE=1",
                "REFRESH_ONLY_NO_TFDU_DRIVE=1",
                "$script:LastP7PostRetestRefreshExit = $deliverableExit",
                "REFRESH_ONLY_EXIT=$refreshOnlyExit",
                "function Invoke-P7PostRetestRefresh",
                "POST_RETEST_REFRESH_ATTEMPTED=1",
                "POST_RETEST_REFRESH_REASON=real_child_retest_completed",
                "SNAPSHOT_REFRESH_EXIT=$refreshExit",
                "P7_01_DELIVERABLE_REFRESH_EXIT=$deliverableExit",
                "P7_01_DELIVERABLE_REFRESH_MATCH=$($line.Line)",
                "POST_RETEST_REFRESH_EXIT=$postRetestRefreshExit",
                "NEXT_MD_STAGE_AFTER_REFRESH=P7.3",
                "NEXT_MD_STAGE_AFTER_REFRESH=P7.2",
                "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0",
                "Invoke-P7PostRetestRefresh -RetestExit $childExit",
            ],
        ),
        md_p7_resume,
        "MD P7 resume wrapper refreshes the failure snapshot and P7_01 raw-matrix deliverables after a real child retest returns, including failed retests, without auto-running P7.3",
        "MD P7 resume wrapper does not prove post-retest snapshot/P7_01 refresh or P7.3 no-auto-run behavior",
    )
    add(
        rows,
        "P1",
        "latest_md_p7_resume_refresh_only_no_hardware",
        contains_all(
            md_p7_resume_refresh_only_text,
            [
                "REFRESH_P7_ARTIFACTS_ONLY=1",
                "REFRESH_ONLY_NO_CHILD_RETEST=1",
                "REFRESH_ONLY_NO_HARDWARE_PROGRAMMING=1",
                "REFRESH_ONLY_NO_UART_WRITE=1",
                "REFRESH_ONLY_NO_TFDU_DRIVE=1",
                "SNAPSHOT_REFRESH_EXIT=0",
                "P7_01_DELIVERABLE_REFRESH_EXIT=0",
                "REFRESH_ONLY_EXIT=0",
                "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        )
        and "FAILED_LINK_RETEST_COMMAND=" not in md_p7_resume_refresh_only_text,
        md_p7_resume_refresh_only,
        "latest MD P7 refresh-only run rebuilt snapshot/P7_01 deliverables without child retest, hardware, UART, or TFDU action",
        "latest MD P7 refresh-only evidence is missing, reached child retest, or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "latest_md_p7_resume_dryrun_no_hardware",
        contains_all(
            md_p7_resume_dryrun_text,
            [
                "CURRENT_MD_STAGE=P7.2",
                "P7_2LANE_REMOTE_RAW_MATRIX_PASS=0",
                "EFFECTIVE_DRY_RUN=1",
                "FAILED_LINK_RETEST_EXIT=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        md_p7_resume_dryrun,
        "latest MD P7 resume dry-run stayed at P7.2, delegated to failed-link dry-run, and executed no hardware, UART, or TFDU action",
        "latest MD P7 resume dry-run evidence is missing or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "latest_md_p7_resume_marker_timeout_no_hardware",
        contains_all(
            md_p7_resume_marker_timeout_text,
            [
                "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER=1",
                "REAL_RUN_REQUESTED=1",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_ENABLED=1",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_TIMEOUT",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        )
        and "FAILED_LINK_RETEST_COMMAND=" not in md_p7_resume_marker_timeout_text,
        md_p7_resume_marker_timeout,
        "latest MD P7 marker-wait timeout blocked before child retest and executed no hardware, UART, or TFDU action",
        "latest MD P7 marker-wait timeout evidence is missing, reached child retest, or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "latest_md_p7_resume_stale_marker_timeout_no_hardware",
        contains_all(
            md_p7_resume_stale_marker_timeout_text,
            [
                "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER=1",
                "ALLOW_EXISTING_PHYSICAL_ADJUSTMENT_MARKER=0",
                "REAL_RUN_REQUESTED=1",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_STALE",
                "reason=marker_older_than_wait_start",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_TIMEOUT",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        )
        and "FAILED_LINK_RETEST_COMMAND=" not in md_p7_resume_stale_marker_timeout_text,
        md_p7_resume_stale_marker_timeout,
        "latest MD P7 stale marker run refused a pre-existing marker before child retest and executed no hardware, UART, or TFDU action",
        "latest MD P7 stale-marker evidence is missing, reached child retest, or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "latest_md_p7_resume_marker_only_clear_no_hardware",
        contains_all(
            md_p7_resume_marker_only_clear_text,
            [
                "WAIT_FOR_PHYSICAL_ADJUSTMENT_MARKER_ONLY=1",
                "MARKER_ONLY_NO_CHILD_RETEST=1",
                "MARKER_ONLY_NO_HARDWARE_PROGRAMMING=1",
                "MARKER_ONLY_NO_UART_WRITE=1",
                "MARKER_ONLY_NO_TFDU_DRIVE=1",
                "WAIT_PHYSICAL_ADJUSTMENT_MARKER_CLEAR",
                "PHYSICAL_ADJUSTMENT_DECLARED_SOURCE=marker_only",
                "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0",
                "MARKER_ONLY_EXIT=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        )
        and "FAILED_LINK_RETEST_COMMAND=" not in md_p7_resume_marker_only_clear_text,
        md_p7_resume_marker_only_clear,
        "latest MD P7 marker-only run proved a fresh marker clears the wait path without child retest, hardware, UART, or TFDU action",
        "latest MD P7 marker-only clear evidence is missing, reached child retest, or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "failed_link_retest_requires_allow_traffic_for_real_hardware",
        contains_all(
            failed_link_retest_text,
            [
                "[switch]$AllowTraffic",
                "[switch]$PhysicalAdjusted",
                "[string]$PhysicalAdjustmentNote = \"\"",
                "[switch]$OverrideRepeatFailureGuard",
                "[switch]$DryRun",
                "$realRunRequested = ($AllowTraffic.IsPresent -and -not $DryRun.IsPresent)",
                "$effectiveDryRun = -not $realRunRequested",
                "check_repeat_physical_failure_guard.py",
                "PHYSICAL_ADJUSTMENT_NOTE_REQUIRED=1",
                "PHYSICAL_ADJUSTMENT_DECLARED_FOR_LINKS=$($failedLinks -join ',')",
                "REPEAT_FAILURE_GUARD_BLOCKED=1",
                "PHYSICAL_ADJUSTMENT_REQUIRED_BEFORE_REAL_RETEST=1",
                "NO_HARDWARE_PROGRAMMING_UNLESS_ALLOW_TRAFFIC=1",
                "NO_UART_WRITE_UNLESS_ALLOW_TRAFFIC=1",
                "NO_TFDU_DRIVE_UNLESS_ALLOW_TRAFFIC=1",
                "DRY_RUN_NO_HARDWARE_PROGRAMMING=1",
                "DRY_RUN_NO_UART_WRITE=1",
                "DRY_RUN_NO_TFDU_DRIVE=1",
                "CHILD_WRAPPER_ENFORCES_PREFLIGHT_AND_SHUTDOWN=1",
            ],
        ),
        failed_link_retest,
        "failed-link retest wrapper selects only current failed 2lane links and defaults to dry-run unless AllowTraffic is set",
        "failed-link retest wrapper is missing AllowTraffic/default-dry-run/no-drive guard markers",
    )
    add(
        rows,
        "P1",
        "failed_link_wait_only_waits_without_hardware",
        contains_all(
            failed_link_retest_text,
            [
                "[switch]$WaitOnly",
                "WAIT_ONLY_TRANSIENT_BLOCKER_CHECK=1",
                "WAIT_ONLY_NEED_COM_PORT=1",
                "WAIT_ONLY_NO_REPEAT_FAILURE_GUARD=1",
                "WAIT_ONLY_NO_CHILD_RETEST=1",
                "Wait-ExternalBlockers -Phase \"wait_only_transient_blockers\" -NeedComPort $true",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        failed_link_retest,
        "failed-link wrapper has a wait-only mode that can validate COM/process transient blockers without repeat guard, child retest, or hardware action",
        "failed-link wrapper is missing wait-only COM wait/no-hardware guard markers",
    )
    add(
        rows,
        "P1",
        "latest_failed_link_wait_only_no_hardware",
        contains_all(
            failed_link_wait_only_text,
            [
                "WAIT_ONLY=1",
                "WAIT_ONLY_TRANSIENT_BLOCKER_CHECK=1",
                "WAIT_ONLY_NEED_COM_PORT=1",
                "WAIT_CLEAR phase=wait_only_transient_blockers",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        failed_link_wait_only,
        "latest failed-link wait-only run reached wait clear and executed no hardware, UART, or TFDU action",
        "latest failed-link wait-only evidence is missing or lacks no-hardware/wait-clear markers",
    )
    add(
        rows,
        "P1",
        "repeat_physical_failure_guard_is_read_only_and_blocks_stale_retests",
        contains_all(
            repeat_failure_guard_text,
            [
                "Guard against repeating the same physical-link hardware test without adjustment",
                "BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                "classify_one",
            ],
        ),
        repeat_failure_guard,
        "repeat-failure guard is read-only and blocks stale repeated far-end RX-missing retests",
        "repeat-failure guard script is missing read-only/no-drive/block markers",
    )
    add(
        rows,
        "P1",
        "latest_repeat_failure_guard_blocks_without_hardware",
        contains_all(
            repeat_failure_guard_blocked_text + "\n" + failed_link_retest_repeat_block_text,
            [
                "RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall=BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT",
                "REPEAT_FAILURE_GUARD_BLOCKED=1",
                "PHYSICAL_ADJUSTMENT_REQUIRED_BEFORE_REAL_RETEST=1",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        failed_link_retest_repeat_block,
        "latest real-mode stale retest was blocked before hardware because no physical adjustment was declared",
        "latest stale-retest block evidence is missing or lacks no-hardware markers",
    )
    add(
        rows,
        "P1",
        "latest_failed_link_retest_dryrun_no_hardware",
        contains_all(
            failed_link_retest_dryrun_text,
            [
                "EFFECTIVE_DRY_RUN=1",
                "SELECTED_FAILED_LINKS=",
                "SELECTED_TRIGGER_MODES=",
                "DRY_RUN_NO_HARDWARE_PROGRAMMING=1",
                "DRY_RUN_NO_UART_WRITE=1",
                "DRY_RUN_NO_TFDU_DRIVE=1",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        failed_link_retest_dryrun,
        "latest failed-link retest dry-run selected failed links and executed no hardware, UART, or TFDU action",
        "latest failed-link retest dry-run evidence is missing or lacks no-hardware markers",
    )
    add(
        rows,
        "DRYRUN",
        "latest_wrapper_dryruns_are_no_tfdu",
        contains_all(two_ax_dryrun_text, ["NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", "NO_TX_DATA_TO_REAL_BOARDS=1", "TWO_AX7010_REAL_ACCEPTANCE_PASS=0"])
        and contains_all(product_dryrun_text, ["NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", "NO_TX_DATA_TO_REAL_BOARDS=1", "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=0"])
        and contains_all(rotating_dryrun_text, ["NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", "NO_TX_DATA_TO_REAL_BOARDS=1", "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=0"])
        and contains_all(eightlane_dryrun_text, ["NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", "NO_TX_DATA_TO_REAL_BOARDS=1", "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=0"]),
        two_ax_dryrun,
        "latest safe-wrapper dry-run/blocker evidence records no real TX data and no TFDU drive",
        "latest safe-wrapper dry-run/blocker evidence is missing no-TFDU markers",
    )
    add(
        rows,
        "READINESS",
        "readiness_and_promotion_preserve_blockers",
        contains_all(
            readiness_text + "\n" + promotion_text,
            [
                "RF_COMM_REMAINING_ACCEPTANCE_READINESS overall=BLOCKED_EXTERNAL_PRECONDITIONS items=5",
                "current_board_ethernet_cable_unavailable",
                "current_board_ethernet_condition_not_changeable_now",
                "RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall=BLOCKED_NOT_PROMOTABLE items=5 promotable=0",
                "PROMOTED_TO_REAL_PASS_BY_THIS_SCRIPT=0",
                "TEMPLATE_OR_DRY_RUN_PROMOTION_ALLOWED=0",
            ],
        ),
        readiness_md,
        "readiness and promotion gates preserve the current no-Ethernet blockers and do not promote any real acceptance item",
        "readiness/promotion blocker evidence is incomplete",
    )
    add(
        rows,
        "DURATION",
        "duration_cap_gate_still_passes",
        contains_all(
            duration_cap_text,
            [
                "RF_COMM_DURATION_CAP_COMPLIANCE overall=PASS_DURATION_CAP_600S checks=16 failures=0",
                "MAX_CONTINUOUS_RUN_SECONDS=600",
                "REAL_PHYSICAL_RUN_GT_600_ALLOWED=0",
                "NO_TFDU_DRIVE=1",
            ],
        ),
        duration_cap_md,
        "duration-cap gate confirms no live path is allowed to exceed 600 s",
        "duration-cap compliance evidence is missing or failing",
    )

    meta = {
        "constraint": rel(constraint),
        "constraint_sha256": sha256(constraint),
        "physical_gate": rel(physical_gate),
        "ps_pc_wrapper": rel(ps_pc),
        "two_ax7010_wrapper": rel(two_ax),
        "product_loop_wrapper": rel(product),
        "rotating_shaft_wrapper": rel(rotating),
        "eightlane_wrapper": rel(eightlane),
        "sequence_wrapper": rel(sequence),
        "p1_lane_mapping_wrapper": rel(p1_lane_mapping),
        "md_p7_resume_wrapper": rel(md_p7_resume),
        "failed_link_retest_wrapper": rel(failed_link_retest),
        "repeat_failure_guard": rel(repeat_failure_guard),
        "physical_snapshot_builder": rel(physical_snapshot_builder),
        "two_lane_matrix_wrapper": rel(two_lane_matrix),
        "two_lane_prearmed_wrapper": rel(two_lane_prearmed),
        "two_lane_matrix_autobuild_restore": rel(two_lane_matrix_autobuild_restore),
        "sequence_summary": rel(sequence_summary),
        "sequence_csv": rel(sequence_csv),
        "readiness_md": rel(readiness_md),
        "duration_cap_md": rel(duration_cap_md),
        "promotion_gate_md": rel(promotion_gate_md),
        "physical_gate_selftest_md": rel(physical_gate_selftest_md),
        "two_ax7010_dryrun": rel(two_ax_dryrun),
        "product_loop_dryrun": rel(product_dryrun),
        "rotating_shaft_dryrun": rel(rotating_dryrun),
        "eightlane_dryrun": rel(eightlane_dryrun),
        "p1_dryrun": rel(p1_dryrun),
        "md_p7_resume_dryrun": rel(md_p7_resume_dryrun),
        "md_p7_resume_refresh_only": rel(md_p7_resume_refresh_only),
        "md_p7_resume_marker_timeout": rel(md_p7_resume_marker_timeout),
        "md_p7_resume_stale_marker_timeout": rel(md_p7_resume_stale_marker_timeout),
        "md_p7_resume_marker_only_clear": rel(md_p7_resume_marker_only_clear),
        "failed_link_retest_dryrun": rel(failed_link_retest_dryrun),
        "failed_link_wait_only": rel(failed_link_wait_only),
        "repeat_failure_guard_blocked": rel(repeat_failure_guard_blocked),
        "failed_link_retest_repeat_block": rel(failed_link_retest_repeat_block),
    }
    return rows, meta


def md_table(rows: list[GuardRow]) -> str:
    lines = [
        "| item | guard | status | evidence | note |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [row.item, row.guard, row.status, row.evidence, row.note]
            ).replace("\n", " ").replace("|", "/")
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows, meta = build_rows()
    failures = [row for row in rows if row.status == "FAIL"]
    overall = "PASS_SAFE_WRAPPER_GUARDS" if not failures else "FAIL_SAFE_WRAPPER_GUARDS"
    generated = datetime.now().isoformat(timespec="seconds")

    md_path = REPORTS / "safe_wrapper_guard_contract_current.md"
    json_path = REPORTS / "safe_wrapper_guard_contract_current.json"
    csv_path = REPORTS / "safe_wrapper_guard_contract_current.csv"

    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=list(asdict(rows[0]).keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(asdict(row))
    write_text_with_retry(csv_path, csv_buffer.getvalue(), encoding="utf-8-sig")

    md = [
        "# Safe Wrapper Guard Contract",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Guards checked: `{len(rows)}`",
        f"- Failures: `{len(failures)}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Wrapper execution performed by this check: `0`",
        "",
        "This read-only check verifies that future real-acceptance wrappers keep their safety interlocks before any board, TFDU, or network traffic can be treated as real acceptance.",
        "",
        "## Guards",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall={overall} guards={len(rows)} failures={len(failures)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "WRAPPER_EXECUTION_DONE_BY_THIS_CHECK=0",
        "REAL_TRAFFIC_REQUIRES_ALLOW_TRAFFIC=1",
        "REAL_TFDU_TRAFFIC_REQUIRES_SHUTDOWN_AFTER=1",
        "EIGHT_LANE_REQUIRES_SHUTDOWN_BEFORE_AFTER_AND_REVIEW=1",
        "CURRENT_NO_ETHERNET_EXECUTES_ZERO_WRAPPERS=1",
        "```",
    ]
    write_text_with_retry(md_path, "\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "guards": len(rows),
        "failures": len(failures),
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "wrapper_execution_done_by_this_check": False,
        "real_traffic_requires_allow_traffic": True,
        "real_tfdu_traffic_requires_shutdown_after": True,
        "eight_lane_requires_shutdown_before_after_and_review": True,
        "current_no_ethernet_executes_zero_wrappers": True,
        "meta": meta,
        "rows": [asdict(row) for row in rows],
    }
    write_text_with_retry(json_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall={overall} guards={len(rows)} failures={len(failures)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("WRAPPER_EXECUTION_DONE_BY_THIS_CHECK=0")
    print("REAL_TRAFFIC_REQUIRES_ALLOW_TRAFFIC=1")
    print("REAL_TFDU_TRAFFIC_REQUIRES_SHUTDOWN_AFTER=1")
    print("EIGHT_LANE_REQUIRES_SHUTDOWN_BEFORE_AFTER_AND_REVIEW=1")
    print("CURRENT_NO_ETHERNET_EXECUTES_ZERO_WRAPPERS=1")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
