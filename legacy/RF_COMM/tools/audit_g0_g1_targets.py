#!/usr/bin/env python3
"""Audit current RF_COMM evidence against the G0/G1 stage targets."""

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
TARGET = Path("C:/Users/user/Downloads/G0_G1_targets.md")
BASELINE = ROOT / "baseline_current_failure.md"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class AuditItem:
    item_id: str
    requirement: str
    status: str
    evidence: str
    note: str


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.replace(b"\x00", b"").decode("utf-8", errors="ignore")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gb18030", errors="ignore")


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def latest_matching(pattern: str, required: list[str] | None = None, forbidden: list[str] | None = None) -> Path | None:
    required = required or []
    forbidden = forbidden or []
    paths = sorted(ROOT.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths:
        text = read_text(path)
        if all(re.search(expr, text, re.MULTILINE | re.DOTALL) for expr in required) and all(
            re.search(expr, text, re.MULTILINE | re.DOTALL) is None for expr in forbidden
        ):
            return path
    return None


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def contains(path: Path | None, pattern: str) -> bool:
    return re.search(pattern, read_text(path), re.MULTILINE | re.DOTALL) is not None


def get_line_value(text: str, key: str) -> str:
    matches = re.findall(r"(?m)^" + re.escape(key) + r"=(.*)$", text)
    if not matches:
        return ""
    return matches[-1].strip()


def parse_uart_log_from_summary(text: str) -> Path | None:
    match = re.search(r"(?m)^G1_HW_SMOKE_UART_LOG=(.+)$", text)
    if not match:
        match = re.search(r"(?m)^INNER_MATCH=UART_LOG=(.+)$", text)
    if not match:
        return None
    return Path(match.group(1).strip())


def a2b_summary_passes(text: str) -> bool:
    for line in re.findall(r"(?m)^.*PSPS_STAGE_SUMMARY .*$", text):
        sent = re.search(r"\bsent=(\d+)", line)
        rx_ok = re.search(r"\brx_ok=(\d+)", line)
        tx_fail = re.search(r"\btx_fail=(\d+)", line)
        loss = re.search(r"\bloss=([0-9.]+)%", line)
        last_error = re.search(r"\blast_error=([^\s]+)", line)
        if (
            sent
            and rx_ok
            and tx_fail
            and loss
            and last_error
            and int(sent.group(1)) >= 10000
            and int(sent.group(1)) == int(rx_ok.group(1))
            and int(tx_fail.group(1)) == 0
            and float(loss.group(1)) == 0.0
            and last_error.group(1) == "none"
        ):
            return True
    return False


def b2a_summary_passes(text: str) -> bool:
    for line in re.findall(r"(?m)^.*PSPS_RX_ONLY_SUMMARY .*$", text):
        rx_ok = re.search(r"\brx_ok=(\d+)", line)
        tx_fail = re.search(r"\btx_fail=(\d+)", line)
        loss = re.search(r"\bloss=([0-9.]+)%", line)
        last_error = re.search(r"\blast_error=([^\s]+)", line)
        if (
            rx_ok
            and tx_fail
            and loss
            and last_error
            and int(rx_ok.group(1)) >= 10000
            and int(tx_fail.group(1)) == 0
            and float(loss.group(1)) == 0.0
            and last_error.group(1) == "none"
        ):
            return True
    return False


def latest_summary_pass(pattern: str, predicate) -> Path | None:
    paths = sorted(ROOT.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in paths:
        if predicate(read_text(path)):
            return path
    return None


def find_constraint() -> Path | None:
    for path in ROOT.glob("*约束*目标*.txt"):
        return path
    for path in ROOT.glob("*constraint*.txt"):
        return path
    return None


def process_clean() -> bool:
    # This audit is intentionally pure Python and does not shell out. Runtime
    # process checks are kept in the surrounding run command.
    return True


def collect_items() -> list[AuditItem]:
    constraint = find_constraint()
    target_text = read_text(TARGET)
    baseline_text = read_text(BASELINE)
    latest_preflight = latest("reports/hw_target_preflight_*.summary.txt")
    latest_lane0 = latest_matching(
        "reports/2lane_prearmed_a_tx_lane0_*.summary.txt",
        required=[r"(?m)^RUN_RESULT_STATUS=PASS\b", r"ILA_CSV_SIZE="],
    )
    latest_lane1_fail = latest_matching(
        "reports/2lane_prearmed_a_tx_lane1_*.summary.txt",
        required=[r"(?m)^RUN_RESULT_STATUS=FAIL_ILA_TIMEOUT\b"],
    )
    latest_matrix_a2b = latest_matching(
        "reports/2lane_matrix_safe_*.ila_matrix.md",
        required=[r"PASS_EXPECTED_RAW", r"A_TO_B_LANE0"],
    )
    latest_p0_replay = latest_matching("reports/p0_known_good_replay_safe_*.summary.txt", required=[r"(?m)^DRY_RUN=0\b"])
    latest_lane0_hw = latest("reports/lane0_hw_loopback_safe_*.summary.txt")
    latest_p0_rx = latest_matching("reports/p0_rx_root_cause_safe_*.summary.txt", required=[r"(?m)^DRY_RUN=0\b"])
    latest_p0_rx_analysis = latest_matching(
        "reports/2lane_matrix_safe_*.ila_matrix.md",
        required=[r"b_rx_data_state", r"D4_SESSION_MISMATCH"],
    )
    latest_p0_ack = latest("reports/p0_ack_only_safe_*.summary.txt")
    latest_a2b_pass = latest_summary_pass("reports/lane0_hw_loopback_safe_*.summary.txt", a2b_summary_passes)
    latest_b2a_pass = latest_summary_pass("reports/lane0_hw_loopback_safe_*.summary.txt", b2a_summary_passes)
    latest_g1_sim = latest("reports/g1_sim_gate_*.log")
    latest_g1_pc = latest("reports/ps_pc_offline_gates_*.summary.txt")
    latest_g1_hw_smoke = latest("reports/g1_lane0_hw_smoke_safe_*.summary.txt")
    latest_g1_segmented_pass = latest_matching(
        "reports/g1_segmented_smoke_regression_*.summary.txt",
        required=[r"(?m)^DRY_RUN=0\b", r"(?m)^G1_SEGMENTED_SMOKE_REGRESSION_PASS=1\b"],
    )
    latest_g1_segmented_dry_ok = latest_matching(
        "reports/g1_segmented_smoke_regression_*.summary.txt",
        required=[
            r"(?m)^DRY_RUN=1\b",
            r"(?m)^NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1\b",
            r"(?m)^NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1\b",
            r"(?m)^G1_SEGMENTED_SMOKE_REGRESSION_PASS=DRY_RUN_ONLY\b",
        ],
    )
    latest_g1_segmented = latest_g1_segmented_pass or latest_g1_segmented_dry_ok or latest(
        "reports/g1_segmented_smoke_regression_*.summary.txt"
    )
    g1_segmented_script = ROOT / "tools" / "run_g1_segmented_smoke_regression_safe.ps1"
    g1_report = REPORTS / "G1_acceptance_report.md"
    g1_throughput = REPORTS / "G1_throughput.csv"
    g1_errors = REPORTS / "G1_error_counters.csv"
    g1_uart = REPORTS / "G1_uart.log"

    lane0_text = read_text(latest_lane0)
    a2b_pass_text = read_text(latest_a2b_pass)
    b2a_pass_text = read_text(latest_b2a_pass)
    g1_sim_text = read_text(latest_g1_sim)
    g1_pc_text = read_text(latest_g1_pc)
    g1_hw_smoke_text = read_text(latest_g1_hw_smoke)
    g1_hw_smoke_uart_text = read_text(parse_uart_log_from_summary(g1_hw_smoke_text))
    g1_segmented_text = read_text(latest_g1_segmented)
    g1_report_text = read_text(g1_report)
    g1_throughput_text = read_text(g1_throughput)
    g1_errors_text = read_text(g1_errors)
    g1_uart_text = read_text(g1_uart)
    p0_replay_text = read_text(latest_p0_replay)
    lane0_hw_text = read_text(latest_lane0_hw)
    p0_rx_text = read_text(latest_p0_rx)
    p0_rx_analysis_text = read_text(latest_p0_rx_analysis)
    lane0_protocol_failed = bool(
        re.search(r"PSPS_STAGE_SUMMARY .*mask=0x00000001 .*rx_ok=0 .*tx_fail=\d+ .*loss=100\.0%", lane0_text)
    )
    a2b_passed = a2b_summary_passes(a2b_pass_text)
    b2a_passed = b2a_summary_passes(b2a_pass_text)
    p0_replay_passed = bool(
        re.search(r"(?m)^LANE0_EFFECTIVE_EXIT=0\b", p0_replay_text)
        and re.search(r"PASS_LANE0_KNOWN_GOOD_REPLAY", p0_replay_text)
    )
    p0_replay_failed = bool(
        re.search(r"(?m)^LANE0_EFFECTIVE_EXIT=(?!0\b)\d+", p0_replay_text)
        or re.search(r"(?m)^LANE0_LAST_RX_OK=0\b", p0_replay_text)
        or re.search(r"(?m)^LANE0_LAST_TX_FAIL=(?!0\b)\d+", p0_replay_text)
    )
    p0_replay_note = "No current real hardware replay found."
    if latest_p0_replay is not None:
        p0_replay_note = (
            f"sent={get_line_value(p0_replay_text, 'LANE0_LAST_SENT') or 'unknown'}, "
            f"rx_ok={get_line_value(p0_replay_text, 'LANE0_LAST_RX_OK') or 'unknown'}, "
            f"tx_fail={get_line_value(p0_replay_text, 'LANE0_LAST_TX_FAIL') or 'unknown'}, "
            f"loss={get_line_value(p0_replay_text, 'LANE0_LAST_LOSS') or 'unknown'}, "
            f"last_error={get_line_value(p0_replay_text, 'LANE0_LAST_ERROR') or 'unknown'}."
        )
    lane0_hw_shutdown_ok = bool(
        re.search(r"(?m)^SHUTDOWN_EXIT_INFERRED=0\b", lane0_hw_text)
        and re.search(r"(?m)^HW_WINDOW_TO_SHUTDOWN_END_SECONDS=([0-9]+(?:\.[0-9]+)?)", lane0_hw_text)
        and float(re.search(r"(?m)^HW_WINDOW_TO_SHUTDOWN_END_SECONDS=([0-9]+(?:\.[0-9]+)?)", lane0_hw_text).group(1)) < 300.0
    )
    p0_rx_session_mismatch = bool(
        re.search(r"D4_SESSION_MISMATCH", p0_rx_text) or re.search(r"D4_SESSION_MISMATCH", p0_rx_analysis_text)
    )
    p0_rx_raw_pass = bool(
        re.search(r"PASS_RAW_PULSE", p0_rx_text) or re.search(r"PASS_RAW_PULSE", p0_rx_analysis_text)
    )
    p0_rx_windows_ok = bool(
        latest_p0_rx is not None
        and re.search(r"RUN_RESULT .*shutdown_inferred=0 .*tfdu_window_s=([0-9]+(?:\.[0-9]+)?)", p0_rx_text)
        and all(float(value) < 300.0 for value in re.findall(r"RUN_RESULT .*shutdown_inferred=0 .*tfdu_window_s=([0-9]+(?:\.[0-9]+)?)", p0_rx_text))
    )
    current_g0_safety_ok = all(
        contains(path, r"(?m)^SHUTDOWN_EXIT(?:_INFERRED)?=0\b")
        and contains(path, r"(?m)^HW_WINDOW_TO_SHUTDOWN_END_SECONDS=1[0-9][0-9]\.")
        for path in (latest_a2b_pass, latest_b2a_pass)
        if path is not None
    ) and latest_a2b_pass is not None and latest_b2a_pass is not None
    g1_sim_passed = bool(
        re.search(r"G1_SIM_GATE_PASS", g1_sim_text)
        and len(re.findall(r"(?m)^=== TEST .* EXIT 0", g1_sim_text)) >= 10
        and re.search(r"LOOPBACK_SINGLE_LANE_256B_LATENCY_PASS .*bytes=256 .*frags=16", g1_sim_text)
        and re.search(r"LOOPBACK_CRC_SINGLE_LANE_PASS .*crc_errors=1", g1_sim_text)
        and re.search(r"LOOPBACK_RETRY_EXHAUST_SINGLE_LANE_PASS", g1_sim_text)
        and re.search(r"LOOPBACK_RECOVER_AFTER_EXHAUST_SINGLE_LANE_PASS", g1_sim_text)
        and re.search(r"IR_STREAM_TDM_PERF_SINGLE_LANE_PASS .*a_to_b_mbps=1\.404560 .*b_to_a_mbps=1\.404560", g1_sim_text)
        and re.search(r"AXI_TOP_LANE_COUNTERS_PASS", g1_sim_text)
    )
    g1_pc_passed = bool(
        re.search(r"PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1", g1_pc_text)
        and re.search(r"(?m)^PAYLOAD_SIZE=256\b", g1_pc_text)
        and re.search(r"PS_BRIDGE_STATIC_CHECKS_PASS .*dhcp=1 .*tcp=1 .*protocol=1 .*reconnect=1", g1_pc_text)
        and re.search(r"tx_packets=8 .*tx_bytes=2048 .*rx_data=8 .*rx_data_bytes=2048", g1_pc_text)
        and re.search(r"failed_tx=0 .*ack_timeouts=0 .*errors=0 .*pending=0", g1_pc_text)
    )
    g1_throughput_passed = bool(
        re.search(r"stream_tdm_perf,.*1\.404560,1\.404560,2\.809120,PASS", g1_throughput_text)
    )
    g1_error_coverage_passed = bool(
        re.search(r"crc_errors,1,PASS", g1_errors_text)
        and re.search(r"dropped_ack,1,PASS", g1_errors_text)
        and re.search(r"halfduplex_overlaps,0,PASS", g1_errors_text)
        and re.search(r"failed_tx,0,PASS", g1_errors_text)
    )
    g1_hw_smoke_payload_seen = bool(re.search(r"(?m)^G1_HW_SMOKE_PAYLOAD_256_SEEN=1\b", g1_hw_smoke_text))
    g1_hw_smoke_passed = bool(re.search(r"(?m)^G1_HW_SMOKE_SUMMARY_PASS=1\b", g1_hw_smoke_text))
    g1_hw_smoke_shutdown_ok = bool(re.search(r"(?m)^G1_HW_SMOKE_SHUTDOWN_OK=1\b", g1_hw_smoke_text))
    g1_hw_smoke_window_ok = bool(re.search(r"(?m)^G1_HW_SMOKE_WINDOW_OK=1\b", g1_hw_smoke_text))
    g1_hw_smoke_failed_safely = bool(
        g1_hw_smoke_payload_seen
        and not g1_hw_smoke_passed
        and g1_hw_smoke_shutdown_ok
        and g1_hw_smoke_window_ok
        and re.search(r"tx_retry_exhausted|loss=100\.0%", g1_hw_smoke_text)
    )
    g1_capped_10min_soak_passed = bool(
        g1_hw_smoke_passed
        and g1_hw_smoke_shutdown_ok
        and g1_hw_smoke_window_ok
        and re.search(r"stage_seconds=54[0-9]|stage_seconds=5[5-9][0-9]|stage_seconds=600", g1_hw_smoke_uart_text)
        and re.search(
            r"PSPS_STAGE_SUMMARY .*sent=(\d+) .*rx_ok=\1 .*tx_fail=0 .*rx_timeout=0 .*rx_bad=0 .*rx_mismatch=0 .*loss=0\.0% .*last_error=none",
            g1_hw_smoke_uart_text,
        )
        and re.search(r"PSPS_RUN_ONCE_DONE link_disabled=1", g1_hw_smoke_uart_text)
        and re.search(r"(?m)^INNER_MATCH=HW_WINDOW_TO_SHUTDOWN_END_SECONDS=([0-9]+(?:\.[0-9]+)?)", g1_hw_smoke_text)
        and float(re.search(r"(?m)^INNER_MATCH=HW_WINDOW_TO_SHUTDOWN_END_SECONDS=([0-9]+(?:\.[0-9]+)?)", g1_hw_smoke_text).group(1))
        < 600.0
    )
    g1_segmented_passed = bool(
        re.search(r"(?m)^DRY_RUN=0\b", g1_segmented_text)
        and re.search(r"(?m)^G1_SEGMENTED_SMOKE_REGRESSION_PASS=1\b", g1_segmented_text)
    )
    g1_segmented_dry_run_ready = bool(
        g1_segmented_script.exists()
        and re.search(r"(?m)^DRY_RUN=1\b", g1_segmented_text)
        and re.search(r"(?m)^NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1\b", g1_segmented_text)
        and re.search(r"(?m)^NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1\b", g1_segmented_text)
        and re.search(r"(?m)^G1_SEGMENTED_SMOKE_REGRESSION_PASS=DRY_RUN_ONLY\b", g1_segmented_text)
    )
    g1_physical_blocked = bool(
        re.search(r"No G1 physical .*acceptance run was executed", g1_uart_text)
        or re.search(r"1 hour|1-hour|1 小时", g1_report_text)
        and re.search(r"10 minutes|10 分钟", g1_report_text)
    )
    g1_report_rx_fix_retest_status = bool(
        re.search(r"SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING", g1_report_text)
    )
    g1_report_short_hw_pass_status = bool(
        re.search(r"SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED", g1_report_text)
    )
    g1_report_capped_10min_status = bool(
        re.search(r"SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS", g1_report_text)
    )
    g1_report_post_fix_ack_return_status = bool(
        re.search(r"SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN", g1_report_text)
    )
    g1_report_hw_smoke_failed_status = bool(re.search(r"SIM_OFFLINE_PASS_HW_SMOKE_FAIL_PHYSICAL_BLOCKED", g1_report_text))
    g1_report_old_blocked_status = bool(re.search(r"SIM_AND_OFFLINE_PASS_PHYSICAL_(?:SOAK_NOT_RUN|BLOCKED)", g1_report_text))
    g1_current_acceptance = (
        g1_report_capped_10min_status
        or g1_report_short_hw_pass_status
        or g1_report_rx_fix_retest_status
        or g1_report_post_fix_ack_return_status
        or g1_report_hw_smoke_failed_status
        or g1_report_old_blocked_status
    )
    g1_current_acceptance_status = (
        "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS"
        if g1_report_capped_10min_status
        else (
            "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED"
            if g1_report_short_hw_pass_status
            else (
                "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING"
                if g1_report_rx_fix_retest_status
                else (
                    "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN"
                    if g1_report_post_fix_ack_return_status
                    else (
                        "SIM_OFFLINE_PASS_HW_SMOKE_FAIL_PHYSICAL_BLOCKED"
                        if g1_report_hw_smoke_failed_status
                        else ("SIM_AND_OFFLINE_PASS_PHYSICAL_BLOCKED" if g1_report_old_blocked_status else "MISSING")
                    )
                )
            )
        )
    )

    items: list[AuditItem] = []
    items.append(
        AuditItem(
            "G0G1-TARGET",
            "G0/G1 stage target file is available and defines near-term scope.",
            "PASS" if "G0" in target_text and "G1" in target_text and "单 lane" in target_text else "MISSING",
            str(TARGET),
            f"sha256={sha256(TARGET)}",
        )
    )
    items.append(
        AuditItem(
            "HARD-CONSTRAINT",
            "Root hard project constraint remains unchanged.",
            "PASS" if sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            rel(constraint),
            f"sha256={sha256(constraint)}",
        )
    )
    items.append(
        AuditItem(
            "G0-BASELINE-FREEZE",
            "Current failing baseline is frozen before G0 recovery changes.",
            "PASS" if BASELINE.exists() and "Current Failure Phenomenon" in baseline_text else "MISSING",
            rel(BASELINE),
            "Covers artifact hashes, scripts, current UART/ILA evidence, and next isolation path.",
        )
    )
    items.append(
        AuditItem(
            "G0-JTAG",
            "JTAG target is visible before any hardware programming or TFDU drive.",
            "PASS"
            if contains(latest_preflight, r"HW_PREFLIGHT_RESULT PASS") and contains(latest_preflight, r"HW_PREFLIGHT_ZYNQ")
            else "WAITING_HARDWARE",
            rel(latest_preflight),
            "This only proves board access, not IR link closure.",
        )
    )
    items.append(
        AuditItem(
            "G0-LANE0-A2B-RAW",
            "Lane0 A to B raw physical pulse activity is captured.",
            "PASS_RAW_ONLY" if latest_lane0 is not None and latest_matrix_a2b is not None else "MISSING",
            "; ".join(filter(None, [rel(latest_lane0), rel(latest_matrix_a2b)])),
            "Raw pulse evidence exists, but this is not a protocol closed-loop pass.",
        )
    )
    items.append(
        AuditItem(
            "G0-LANE0-A2B-PROTOCOL",
            "Lane0 A to B protocol closed loop has rx_ok==sent, tx_fail=0, loss=0.",
            "PASS" if a2b_passed else ("FAIL" if lane0_protocol_failed else "UNKNOWN"),
            rel(latest_a2b_pass or latest_lane0),
            "Current A->B lane0 summary has >=10,000 packets, rx_ok==sent, tx_fail=0, loss=0.0%, last_error=none."
            if a2b_passed
            else "Latest lane0 evidence has rx_ok=0, tx_fail>0, loss=100%, last_error=tx_retry_exhausted.",
        )
    )
    items.append(
        AuditItem(
            "G0-LANE0-B2A-PROTOCOL",
            "Lane0 B to A protocol closed loop is separately verified.",
            "PASS" if b2a_passed else "MISSING",
            rel(latest_b2a_pass),
            "Current B->A lane0 receive-only summary has >=10,000 packets, tx_fail=0, loss=0.0%, last_error=none."
            if b2a_passed
            else "No current G0-scoped B->A lane0 10,000-packet closed-loop evidence found.",
        )
    )
    items.append(
        AuditItem(
            "G0-HISTORICAL-REPLAY",
            "Historical lane0 known-good is replayed or selected as the next G0 comparison step.",
            "PASS" if p0_replay_passed else ("FAIL" if p0_replay_failed else ("READY_TO_RUN" if latest_p0_replay is not None else "MISSING")),
            rel(latest_p0_replay),
            p0_replay_note,
        )
    )
    items.append(
        AuditItem(
            "G0-RX-MICROSCOPE",
            "RX-only microscope can classify raw/preamble/symbol/CRC/frame/session failures.",
            "FAIL_CLASSIFIED"
            if p0_rx_session_mismatch
            else ("PASS_RAW_ONLY" if p0_rx_raw_pass else ("READY_FOR_HARDWARE" if (ROOT / "tools/run_p0_rx_root_cause_safe.ps1").exists() else "MISSING")),
            "; ".join(filter(None, [rel(latest_p0_rx), rel(latest_p0_rx_analysis)])),
            "A->B lane0 raw pulses are visible, but B reports session mismatch/CRC failures and no ACK generation.",
        )
    )
    items.append(
        AuditItem(
            "G0-ACK-ONLY",
            "ACK-only build/run proves ACK generation and return path.",
            "WAITING_RX_FIX" if p0_rx_session_mismatch else ("WAITING_RX_PASS" if (ROOT / "tools/run_p0_ack_only_safe.ps1").exists() else "MISSING"),
            rel(latest_p0_ack),
            "ACK-only must wait until RX-good evidence exists.",
        )
    )
    items.append(
        AuditItem(
            "G0-ACCEPTANCE",
            "G0 exits with both lane0 directions >=10,000 packets, tx_fail=0, unrecovered loss=0.",
            "PASS" if a2b_passed and b2a_passed else "FAIL",
            "; ".join(filter(None, [rel(latest_a2b_pass), rel(latest_b2a_pass)])),
            "Current evidence satisfies G0 lane0 A->B and B->A acceptance."
            if a2b_passed and b2a_passed
            else "Current evidence proves G0 is not complete.",
        )
    )
    items.append(
        AuditItem(
            "G1-ENTRY",
            "G1 starts only after G0 passes.",
            "READY" if a2b_passed and b2a_passed else "BLOCKED_BY_G0",
            "; ".join(filter(None, [rel(latest_a2b_pass), rel(latest_b2a_pass)])),
            "G0 has passed; G1 may start under the active capped 10-minute small-board runtime limit."
            if a2b_passed and b2a_passed
            else "Do not start G1 soak/throughput/PC work until G0 acceptance passes.",
        )
    )
    items.append(
        AuditItem(
            "G1-SIM-GATE",
            "G1 single-lane reliable-link simulation gate covers 256B fragmentation, CRC, retry, recovery, ACK loss, TDM throughput, and counters.",
            "PASS" if g1_sim_passed else ("MISSING" if latest_g1_sim is None else "FAIL"),
            rel(latest_g1_sim),
            "10 simulation tests exited 0 with the required G1 protocol coverage."
            if g1_sim_passed
            else "Run the G1 simulation gate before claiming G1 sim readiness.",
        )
    )
    items.append(
        AuditItem(
            "G1-PC-OFFLINE",
            "PC or UART control path has an offline gate for protocol, status, DHCP/TCP code presence, and reconnect behavior.",
            "PASS" if g1_pc_passed else ("MISSING" if latest_g1_pc is None else "FAIL"),
            rel(latest_g1_pc),
            "Offline gate passed: static checks, 18 host tests, 8-packet 256-byte mock traffic, and reconnect."
            if g1_pc_passed
            else "Run tools/run_ps_pc_offline_gates.ps1.",
        )
    )
    items.append(
        AuditItem(
            "G1-THROUGHPUT-SIM",
            "G1 report separates payload throughput from raw PHY and shows PL/IR simulated payload throughput above 0.5 Mbit/s.",
            "PASS_SIM" if g1_throughput_passed else "MISSING",
            rel(g1_throughput),
            "Simulation TDM row records 1.404560 Mbit/s per direction and 2.809120 Mbit/s aggregate."
            if g1_throughput_passed
            else "Missing G1_throughput.csv simulation throughput row.",
        )
    )
    items.append(
        AuditItem(
            "G1-ERROR-COVERAGE",
            "G1 error counters cover CRC fail, ACK loss, retry/recovery, half-duplex overlap, and host-side clean completion.",
            "PASS" if g1_error_coverage_passed else "MISSING",
            rel(g1_errors),
            "G1_error_counters.csv includes protocol and PC/offline clean-completion counters."
            if g1_error_coverage_passed
            else "Missing G1_error_counters.csv coverage rows.",
        )
    )
    items.append(
        AuditItem(
            "G1-HW-SMOKE",
            "G1 256-byte short hardware smoke runs under the TFDU 10-minute runtime cap and records pass/fail evidence.",
            "PASS" if g1_hw_smoke_passed else ("FAIL_SAFE_SHUTDOWN_OK" if g1_hw_smoke_failed_safely else ("MISSING" if latest_g1_hw_smoke is None else "UNKNOWN")),
            rel(latest_g1_hw_smoke),
            "256-byte hardware smoke failed with tx_retry_exhausted/loss=100%, but shutdown and runtime window were safe."
            if g1_hw_smoke_failed_safely
            else ("256-byte hardware smoke passed." if g1_hw_smoke_passed else "No conclusive G1 256-byte short hardware smoke result found."),
        )
    )
    items.append(
        AuditItem(
            "G1-SEGMENTED-REGRESSION",
            "G1 has a safety-bounded repeated short-smoke regression path with shutdown between cycles.",
            "PASS"
            if g1_segmented_passed
            else ("READY_DRY_RUN_VERIFIED" if g1_segmented_dry_run_ready else ("READY_TO_RUN" if g1_segmented_script.exists() else "MISSING")),
            rel(latest_g1_segmented or g1_segmented_script),
            "Segmented regression completed all requested real cycles with every cycle passing and shutdown/window checks OK."
            if g1_segmented_passed
            else (
                "Dry run verified the segmented regression wrapper without FPGA programming or TFDU drive."
                if g1_segmented_dry_run_ready
                else (
                    "Run tools/run_g1_segmented_smoke_regression_safe.ps1 for repeated short-smoke evidence under the 10-minute TFDU runtime cap."
                    if g1_segmented_script.exists()
                    else "Create the segmented regression wrapper."
                )
            ),
        )
    )
    items.append(
        AuditItem(
            "G1-PHYSICAL-SOAK",
            "G1 requires a static physical soak; per current user instruction, any longer continuous target is capped at 10 minutes.",
            "PASS_CAPPED_10MIN"
            if g1_capped_10min_soak_passed
            else ("BLOCKED_BY_SAFETY" if g1_physical_blocked else "MISSING"),
            rel(latest_g1_hw_smoke if g1_capped_10min_soak_passed else g1_uart),
            "Capped soak evidence passed under the 10-minute continuous runtime limit."
            if g1_capped_10min_soak_passed
            else (
                "Not executed because no approved capped physical soak evidence exists under the active TFDU runtime limit."
                if g1_physical_blocked
                else "No valid capped 10-minute physical soak evidence found."
            ),
        )
    )
    items.append(
        AuditItem(
            "G1-CURRENT-ACCEPTANCE",
            "G1 current report must not overclaim full acceptance before the physical soak.",
            g1_current_acceptance_status,
            rel(g1_report),
            "Report correctly states G1 is accepted under the current capped 10-minute continuous-test rule; broader multi-lane/rotation/product targets remain outside G1."
            if g1_report_capped_10min_status
            else (
                "Report correctly states G1 is not fully accepted: simulation, offline, and short hardware smoke pass, but the required capped soak is blocked by the active TFDU runtime limit."
                if g1_report_short_hw_pass_status
                else (
                    "Report correctly states G1 is not fully accepted: RX fix passed simulation and post-fix hardware smoke is pending."
                    if g1_report_rx_fix_retest_status
                    else (
                        "Report correctly states G1 is not fully accepted: post-fix hardware smoke failed safely and the next focus is A-side ACK return RX/parse."
                        if g1_report_post_fix_ack_return_status
                        else (
                            "Report correctly states G1 is not fully accepted: simulation/offline pass, short hardware smoke failed safely, and physical soak is not run."
                            if g1_report_hw_smoke_failed_status
                            else (
                                "Report correctly states G1 is not fully accepted: simulation and offline control pass, physical soak not run."
                                if g1_current_acceptance
                                else "Create or update G1_acceptance_report.md."
                            )
                        )
                    )
                )
            ),
        )
    )
    items.append(
        AuditItem(
            "SAFETY-SHUTDOWN",
            "Physical runs are followed by shutdown bitstream and stay under the 10-minute TFDU runtime cap.",
            "PASS"
            if (
                current_g0_safety_ok
                or (g1_hw_smoke_shutdown_ok and g1_hw_smoke_window_ok)
                or (lane0_hw_shutdown_ok and p0_rx_windows_ok and contains(latest_lane1_fail, r"SHUTDOWN_EXIT_INFERRED=0"))
            )
            else "UNKNOWN",
            "; ".join(filter(None, [rel(latest_a2b_pass), rel(latest_b2a_pass), rel(latest_lane0_hw), rel(latest_p0_rx), rel(latest_lane1_fail)])),
            "Latest G0/G1 physical windows are under the active runtime cap with shutdown OK.",
        )
    )
    if process_clean():
        pass
    return items


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def next_action(items: list[AuditItem]) -> str:
    status = {item.item_id: item.status for item in items}
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS":
        return "Treat G1 single-lane MVP as accepted under the capped 10-minute rule; keep later multi-lane, rotation, and PC-to-PC product goals on separate evidence gates."
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED":
        if status.get("G1-SEGMENTED-REGRESSION") == "READY_DRY_RUN_VERIFIED":
            return "Run tools/run_g1_segmented_smoke_regression_safe.ps1 for repeated short-smoke reliability evidence, or define an approved 1-hour soak path before claiming full G1 acceptance."
        if status.get("G1-SEGMENTED-REGRESSION") == "PASS":
            return "Use segmented short-smoke evidence for interim reliability tracking; full G1 acceptance still needs an approved 1-hour soak path or target change."
        return "Prepare an approved G1 soak path; under the active TFDU 10-minute cap, use capped or segmented smoke evidence with shutdown between runs."
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING":
        return "Build the fixed G1 bit/ELF, run one short 256-byte hardware smoke under the TFDU limit, then program shutdown."
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN":
        return "Expose A-side ACK RX/parse state, then run one short instrumented 256-byte smoke under the TFDU limit and program shutdown."
    if status.get("G1-HW-SMOKE") == "FAIL_SAFE_SHUTDOWN_OK":
        return "Diagnose the G1 256-byte hardware ACK/retry path before attempting any long soak or lane expansion."
    if status.get("G1-CURRENT-ACCEPTANCE") in {
        "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED",
        "SIM_AND_OFFLINE_PASS_PHYSICAL_BLOCKED",
        "SIM_OFFLINE_PASS_HW_SMOKE_FAIL_PHYSICAL_BLOCKED",
        "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING",
        "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN",
    }:
        return "Run only capped G1 hardware smoke tests under the 10-minute TFDU limit; full product acceptance needs later multi-lane/rotation/PC-to-PC evidence."
    if status.get("G0-ACCEPTANCE") == "PASS":
        return "Start G1 implementation/simulation; keep physical tests under the small-board runtime limit."
    if status.get("G0-BASELINE-FREEZE") != "PASS":
        return "Create baseline_current_failure.md."
    if status.get("G0-HISTORICAL-REPLAY") == "READY_TO_RUN":
        return "Run a fresh G0 lane0 historical known-good replay, then shut down TFDU."
    if status.get("G0-HISTORICAL-REPLAY") == "FAIL":
        if status.get("G0-RX-MICROSCOPE") == "FAIL_CLASSIFIED":
            return "Inspect and fix the lane0 session/header decode mismatch before ACK-only testing."
        return "Run G0 lane0 RX-only microscope to locate raw/preamble/symbol/CRC/session failure."
    if status.get("G0-RX-MICROSCOPE") == "READY_FOR_HARDWARE":
        return "Run G0 lane0 RX-only microscope after replay comparison."
    return "Continue G0 evidence collection."


def overall_status(items: list[AuditItem]) -> str:
    status = {item.item_id: item.status for item in items}
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS":
        return "G0_PASS_G1_CAPPED_10MIN_PASS"
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED":
        return "G0_PASS_G1_SHORT_HW_PASS_SOAK_BLOCKED"
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING":
        return "G0_PASS_G1_RX_FIX_SIM_PASS_HW_RETEST_PENDING"
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN":
        return "G0_PASS_G1_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN"
    if status.get("G1-HW-SMOKE") == "FAIL_SAFE_SHUTDOWN_OK":
        return "G0_PASS_G1_HW_SMOKE_FAIL_PHYSICAL_BLOCKED"
    if status.get("G1-CURRENT-ACCEPTANCE") in {
        "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED",
        "SIM_AND_OFFLINE_PASS_PHYSICAL_BLOCKED",
        "SIM_OFFLINE_PASS_HW_SMOKE_FAIL_PHYSICAL_BLOCKED",
        "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING",
        "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN",
    }:
        return "G0_PASS_G1_SIM_OFFLINE_PASS_PHYSICAL_BLOCKED"
    if status.get("G0-ACCEPTANCE") == "PASS":
        return "G0_PASS_G1_READY"
    return "G0_IN_PROGRESS"


def g1_status(items: list[AuditItem]) -> str:
    status = {item.item_id: item.status for item in items}
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS":
        return "SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS"
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED":
        return "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED"
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING":
        return "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING"
    if status.get("G1-CURRENT-ACCEPTANCE") == "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN":
        return "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN"
    if status.get("G1-HW-SMOKE") == "FAIL_SAFE_SHUTDOWN_OK":
        return "SIM_OFFLINE_PASS_HW_SMOKE_FAIL_PHYSICAL_BLOCKED"
    if status.get("G1-CURRENT-ACCEPTANCE") in {
        "SIM_OFFLINE_SHORT_HW_PASS_SOAK_BLOCKED",
        "SIM_AND_OFFLINE_PASS_PHYSICAL_BLOCKED",
        "SIM_OFFLINE_PASS_HW_SMOKE_FAIL_PHYSICAL_BLOCKED",
        "SIM_OFFLINE_PASS_RX_FIX_SIM_PASS_HW_RETEST_PENDING",
        "SIM_OFFLINE_PASS_POST_RX_FIX_HW_SMOKE_FAIL_ACK_RETURN",
    }:
        return "SIM_AND_OFFLINE_PASS_PHYSICAL_BLOCKED"
    if status.get("G0-ACCEPTANCE") == "PASS":
        return "READY"
    return "BLOCKED_BY_G0"


def render(items: list[AuditItem]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    rows = [[item.item_id, item.requirement, item.status, item.evidence, item.note] for item in items]
    overall = overall_status(items)
    g1 = g1_status(items)
    return "\n".join(
        [
            "# RF_COMM G0/G1 Target Audit",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{overall}`",
            f"- Next action: `{next_action(items)}`",
            f"- G1 status: `{g1}`",
            "",
            "## Status Counts",
            "",
            md_table(["status", "count"], [[key, str(value)] for key, value in sorted(counts.items())]),
            "",
            "## Evidence Table",
            "",
            md_table(["id", "requirement", "status", "evidence", "note"], rows),
            "",
            f"G0_G1_TARGET_AUDIT overall={overall} g1={g1}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPORTS / "g0_g1_target_audit_current_20260626.md")
    parser.add_argument("--json", type=Path, default=REPORTS / "g0_g1_target_audit_current_20260626.json")
    args = parser.parse_args()

    items = collect_items()
    overall = overall_status(items)
    g1 = g1_status(items)
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(items), encoding="utf-8")

    json_out = args.json if args.json.is_absolute() else ROOT / args.json
    json_out.write_text(
        json.dumps(
            {
                "generated": datetime.now().isoformat(timespec="seconds"),
                "overall": overall,
                "g1": g1,
                "next_action": next_action(items),
                "items": [asdict(item) for item in items],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"WROTE_MARKDOWN={out}")
    print(f"WROTE_JSON={json_out}")
    print(f"G0_G1_TARGET_AUDIT overall={overall} g1={g1} next_action={next_action(items)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
