from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class MatrixItem:
    item_id: str
    category: str
    requirement: str
    verification_scope: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def latest(pattern: str) -> Path | None:
    matches = sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if all(needle in text for needle in needles):
            return path
    return None


def contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def contains_re(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None


def audit_item_status(text: str, item_id: str) -> str:
    pattern = rf"^\| {re.escape(item_id)} \| [^\n]*? \| ([^|]+?) \|"
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        return ""
    return match.group(1).strip()


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def build_items() -> tuple[list[MatrixItem], dict[str, str]]:
    constraint = find_hard_constraint()
    constraint_text = read_text(constraint)
    g1_report = REPORTS / "G1_acceptance_report.md"
    g1_text = read_text(g1_report)
    post_status = REPORTS / "post_g1_target_status_current.md"
    post_status_text = read_text(post_status)
    full_audit = REPORTS / "full_target_audit_current_20260626.md"
    full_audit_text = read_text(full_audit)
    post_summary = latest("reports/post_g1_target_sim_gate_*.summary.txt")
    post_summary_text = read_text(post_summary)
    post_cases = latest("reports/post_g1_target_sim_gate_*.cases.csv")
    no_eth_summary = latest_containing(
        "reports/no_ethernet_network_offline_acceptance_*.summary.txt",
        ["NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1", "NO_REAL_BOARD_TCP_DHCP=1"],
    )
    no_eth_text = read_text(no_eth_summary)
    no_eth_csv = latest_containing(
        "reports/no_ethernet_network_offline_acceptance_*.cases.csv",
        [
            "ps_bridge_static",
            "host_offline_mock_acceptance",
            "network_fault_recovery_model",
            "two_ax7010_direct_offline_model",
            "rotating_shaft_safe_wrapper_dry_run_cap",
            "product_loop_safe_wrapper_dry_run_cap",
            "eight_lane_hardware_safe_wrapper_dry_run_cap",
        ],
    )
    no_eth_csv_text = read_text(no_eth_csv)
    rate_boundary = REPORTS / "rate_boundary_proof_20260627.md"
    rate_boundary_text = read_text(rate_boundary)
    payload_gap_closure = REPORTS / "payload_gap_closure_current.md"
    payload_gap_closure_text = read_text(payload_gap_closure)
    reduced8_bitstream = REPORTS / "external_reduced_8lane_frag16_bitstream_current.md"
    reduced8_bitstream_text = read_text(reduced8_bitstream)
    reduced8_bitstream_csv = REPORTS / "external_reduced_8lane_frag16_bitstream_current.csv"
    reduced8_bitstream_csv_text = read_text(reduced8_bitstream_csv)
    full_system_twin = REPORTS / "full_system_capped_digital_twin_current.md"
    full_system_twin_text = read_text(full_system_twin)
    rotating_autoroute_offline = REPORTS / "rotating_autoroute_offline_evidence_current.md"
    rotating_autoroute_offline_text = read_text(rotating_autoroute_offline)
    two_ax_model = REPORTS / "two_ax7010_end_to_end_model_current.md"
    two_ax_model_text = read_text(two_ax_model)
    host_status_snapshot = REPORTS / "host_status_snapshot_current.md"
    host_status_snapshot_text = read_text(host_status_snapshot)
    no_eth_boundary = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    no_eth_boundary_text = read_text(no_eth_boundary)
    no_eth_boundary_csv = REPORTS / "no_ethernet_network_boundary_evidence_current.csv"
    no_eth_boundary_csv_text = read_text(no_eth_boundary_csv)
    ps_lwip_static = REPORTS / "ps_lwip_bridge_static_current.md"
    ps_lwip_static_text = read_text(ps_lwip_static)
    ps_lwip_static_csv = REPORTS / "ps_lwip_bridge_static_current.csv"
    ps_lwip_static_csv_text = read_text(ps_lwip_static_csv)
    target_consistency = REPORTS / "target_consistency_check_20260626.md"
    target_consistency_text = read_text(target_consistency)
    boot_audit = REPORTS / "boot_artifact_audit_current.md"
    boot_audit_text = read_text(boot_audit)
    ps_bridge_static = ROOT / "software" / "ps_lwip_bridge" / "check_ps_bridge_static.py"
    host_acceptance = ROOT / "software" / "host_client" / "run_acceptance.ps1"
    two_ax_safe = ROOT / "tools" / "run_two_ax7010_end_to_end_acceptance_safe.ps1"
    no_eth_tool = ROOT / "tools" / "run_no_ethernet_network_offline_acceptance.ps1"

    constraint_ok = constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256
    g1_hw_ok = contains_all(g1_text, ["SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS", "sent=267892", "rx_ok=267892", "tx_fail=0", "HW_WINDOW_TO_SHUTDOWN_END_SECONDS=582.2"])
    g1_fragment_ok = contains_all(g1_text, ["256-byte fragmented payload", "LOOPBACK_SINGLE_LANE_256B_LATENCY_PASS", "256 bytes, 16 fragments"])
    g1_crc_ok = contains_all(g1_text, ["CRC rejection", "LOOPBACK_CRC_SINGLE_LANE_PASS"])
    g1_retry_exhaust_ok = contains_all(g1_text, ["retry exhausted reporting", "LOOPBACK_RETRY_EXHAUST_SINGLE_LANE_PASS"])
    g1_recover_ok = contains_all(g1_text, ["recovery after error", "LOOPBACK_RECOVER_AFTER_EXHAUST_SINGLE_LANE_PASS"])
    g1_ack_loss_ok = contains_all(g1_text, ["ACK-loss recovery", "IR_STREAM_ACK_LOSS_RECOVERY_PASS"])
    g1_feedback_ok = contains_all(g1_text, ["AXI status/config counters", "AXI_REGS_CONFIG_MASKS_PASS", "AXI_TOP_LANE_COUNTERS_PASS"])
    multi8_ok = contains_all(post_summary_text, ["LOOPBACK_8LANE_PASS", "max_busy_lanes=8", "max_inflight_frags=8"])
    maxfrag8_ok = contains_all(post_summary_text, ["LOOPBACK_8LANE_MAX_FRAGMENT_PASS", "payload_bytes=2040", "fragment_bytes=255"])
    fdx4_ok = contains_all(post_summary_text, ["LOOPBACK_FULL_DUPLEX_4PLUS4_LANE_PASS", "max_a_busy=4", "max_b_busy=4", "max_total_busy=8"])
    autoroute8_ok = contains_all(post_summary_text, ["LOOPBACK_8LANE_AUTOROUTE_PASS", "good_src_coverage=11111111", "tx_attempt_coverage=11111111"])
    impair_ok = contains_all(post_summary_text, ["LOOPBACK_MULTI_LANE_IMPAIR_PASS", "ab_lane0_drops=1", "ba_ack_drops=1"])
    degrade_ok = contains_all(post_summary_text, ["LOOPBACK_MULTI_LANE_DEGRADE_PASS", "masks=1111,1110,0101,1000,1111"])
    rotating_sim_ok = contains_all(post_summary_text, ["LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS", "rpm=600", "shaft_diameter_mm=200"])
    rotating_capped_model_ok = contains_all(post_summary_text, ["ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS", "runtime_cap_seconds=600", "rotations=6000", "sectors=48000", "lane_count=8"])
    rotating_2h_model_ok = contains_all(post_summary_text, ["ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS", "seconds=7200", "rotations=72000", "sectors=288000"])
    full_twin_ok = (
        contains_all(post_summary_text, ["FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS", "runtime_cap_seconds=600", "tcp_reconnect_events=30", "dhcp_static_fallback_events=22", "unrecovered_errors=0", "deadlock_events=0"])
        and contains_all(
            full_system_twin_text,
            [
                "- Overall: `PASS`",
                "OFFLINE_MODEL_NOT_HARDWARE",
                "fdx_a_to_b_tx_lane_coverage",
                "`0x0f`",
                "fdx_a_to_b_rx_lane_coverage",
                "`0x0f`",
                "fdx_b_to_a_tx_lane_coverage",
                "`0xf0`",
                "fdx_b_to_a_rx_lane_coverage",
                "`0xf0`",
                "deadlock_events",
                "`0`",
            ],
        )
    )
    rotating_autoroute_offline_ok = contains_all(
        rotating_autoroute_offline_text,
        [
            "RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall=PASS_OFFLINE_ROTATING_AUTOROUTE_EVIDENCE checks=13",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "REAL_ROTATING_SHAFT_ACCEPTANCE=0",
            "eight_lane_autoroute",
            "eight_lane_capped_rotating_model",
            "two_hour_equivalent_model",
            "two_ax7010_offline_route_reconnect",
            "dynamic_permutation_autoroute",
            "network_fault_recovery",
        ],
    )
    two_ax_offline_ok = (
        contains_all(post_summary_text, ["TWO_AX7010_END_TO_END_OFFLINE_PASS", "endpoints=2", "queued_reconnect_rx=1", "tx_lane_coverage=0xff", "rx_lane_coverage=0xff"])
        and contains_all(two_ax_model_text, ["- Overall: `PASS`", "hdx_tx_lane_coverage", "`0xff`", "fdx_a_to_b_tx_lane_coverage", "`0x0f`", "fdx_b_to_a_tx_lane_coverage", "`0xf0`", "reconnect_queued_rx"])
    )
    ps_pc_offline_ok = contains_all(post_summary_text, ["PS_PC_OFFLINE_GATES_PASS", "static=1", "unittest=1", "offline_mock=1"])
    host_status_snapshot_ok = contains_all(
        host_status_snapshot_text,
        [
            "- Overall: `PASS`",
            "OFFLINE_HOST_VIEW_NOT_REAL_BOARD_TCP",
            "No hardware programming: `1`",
            "No UART write: `1`",
            "No TFDU drive: `1`",
            "`device_connection_state`",
            "`network_state`",
            "`tx_packets`",
            "`rx_packets`",
            "`error_frames`",
            "`pending_frames`",
            "`hdx_tx_lane_coverage`",
            "`0xff`",
            "`fdx_a_to_b_tx_lane_coverage`",
            "`0x0f`",
            "`fdx_b_to_a_tx_lane_coverage`",
            "`0xf0`",
        ],
    )
    network_fault_model_ok = contains_all(no_eth_text, ["RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall=PASS scenarios=7", "tcp_reset_reconnect", "dhcp_timeout_static_fallback", "queued_rx_after_reconnect"])
    no_eth_boundary_ok = (
        contains_all(
            no_eth_boundary_text,
            [
                "RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall=PASS_OFFLINE_NETWORK_BOUNDARY checks=8",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                "NO_REAL_BOARD_TCP_DHCP=1",
                "NO_REAL_ETHERNET_LINK_REQUIRED=1",
                "TCP_SEGMENTATION_CASES=fragmented_outgoing;coalesced_ack_rx",
                "NEGATIVE_CASES=missing_ack_timeout;tx_error;oversize_rejected;protocol_desync",
                "RECONNECT_RECOVERY=1",
                "FDX_4PLUS4_CONFIG=1",
            ],
        )
        and contains_all(
            no_eth_boundary_csv_text,
            [
                "fragmented_and_coalesced_tcp_frames,PASS",
                "missing_tx_ack_timeout_detected,PASS",
                "tx_error_reports_failed_data,PASS",
                "oversize_payload_rejected_before_send,PASS",
                "payload_exchange_after_reconnect,PASS",
                "fdx_4plus4_config_status_masks,PASS",
                "protocol_desync_reports_explicit_details,PASS",
                "no_real_board_boundary,PASS",
            ],
        )
    )
    no_eth_ok = contains_all(no_eth_text, ["NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1", "NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT=11", "NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT=0"]) and network_fault_model_ok
    ps_lwip_static_ok = (
        contains_all(
            ps_lwip_static_text,
            [
                "RF_COMM_PS_LWIP_BRIDGE_STATIC overall=PASS checks=64 failures=0",
                "DHCP_SOURCE_READY=1",
                "STATIC_FALLBACK_SOURCE_READY=1",
                "TCP_BRIDGE_SOURCE_READY=1",
                "RFCM_PROTOCOL_SOURCE_READY=1",
                "NO_REAL_BOARD_TCP_DHCP=1",
                f"CONSTRAINT_SHA256={EXPECTED_CONSTRAINT_SHA256}",
            ],
        )
        and contains_all(
            ps_lwip_static_csv_text,
            [
                "dhcp_start,dhcp_static_network,PASS",
                "dhcp_timeout_static_fallback,dhcp_static_network,PASS",
                "static_ip_address,dhcp_static_network,PASS",
                "tcp_new_bind_listen,tcp_connection,PASS",
            ],
        )
    )
    raw_rate_ok = contains_all(post_summary_text, ["IR_PHY_RATE_MODEL_PASS", "raw_mbps=4.000000", "half_duplex_raw_mbps=32.000000", "full_duplex_per_dir_raw_mbps=16.000000"])
    rate_boundary_ok = (
        contains_all(rate_boundary_text, ["RATE_BOUNDARY_PROOF_PASS", "raw PHY capacity"])
        and contains_all(post_summary_text, ["raw_half_8lane_mbps=32.000000", "raw_fdx_4lane_per_dir_mbps=16.000000", "rate_claim_must_be_raw_phy=1"])
    )
    reduced8_bitstream_raw_ok = (
        contains_all(
            reduced8_bitstream_text,
            [
                "RF_COMM_EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM overall=PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED",
                "Raw capacity: `32.000 Mbit/s half-duplex`, `16.000 Mbit/s per direction full-duplex with 4+4 lane partition`.",
                "Bitstream SHA256: `F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778`",
                "No FPGA was programmed; no UART was written; no TFDU was driven.",
            ],
        )
        and contains_all(reduced8_bitstream_csv_text, ["RAW-CAPACITY,PASS_RAW_32_16", "BITSTREAM-FILE,PASS", "TIMING,PASS"])
    )
    payload_boundary_ok = contains_all(post_summary_text, ["best_packet_ack_half_mbps=28.966188", "best_packet_ack_fdx_mbps=14.483094", "meets_32_16_packet_ack_count=0"])
    payload_gap_closure_ok = contains_all(
        payload_gap_closure_text,
        [
            "- Overall: `PASS_RAW_ONLY_GAP_CLASSIFIED`",
            "OFFLINE_RATE_MODEL_NOT_HARDWARE",
            "Current packet-ACK half-duplex payload",
            "28.966188",
            "Current packet-ACK full-duplex payload per direction",
            "14.483094",
            "At least `4.418945` Mbit/s per lane",
            "`9` half-duplex lanes",
            "`5` lanes per direction",
            "cannot be honestly closed as 32/16 Mbit/s effective payload",
        ],
    )
    boot_ok = (
        contains_all(boot_audit_text, ["| ps_lwip_bridge | PASS |", "| ps_ps_loopback | PASS |"])
        and boot_audit_text.count("stale inputs: `none`") >= 2
        and boot_audit_text.count("app markers missing: `none`") >= 2
    )
    host_runtime_cap_ok = contains_all(read_text(host_acceptance), ["$MaxContinuousRunSeconds = 600", "[Math]::Min($requestedDurationSeconds, $MaxContinuousRunSeconds)"])
    board_tcp_missing = audit_item_status(full_audit_text, "BOARD-TCP-DHCP") == "MISSING_HARDWARE"
    two_system_missing = audit_item_status(full_audit_text, "TWO-AX7010-SYSTEMS") == "MISSING_HARDWARE"
    eight_lane_hw_missing = audit_item_status(full_audit_text, "EIGHT-LANE-HARDWARE") == "MISSING_HARDWARE"
    real_rotation_missing = audit_item_status(full_audit_text, "REAL-ROTATING-SHAFT") == "MISSING_HARDWARE"

    items = [
        MatrixItem("C01", "constraint", "Root hard constraint file is unchanged and remains the controlling target.", "file hash", "PASS" if constraint_ok else "FAIL", rel(constraint), f"sha256={sha256(constraint)}"),
        MatrixItem("C02", "platform", "ZYNQ-7010 boot artifacts exist and are current for the PS lwIP bridge and PS-PS loopback packages.", "artifact audit", "PASS_ARTIFACT" if boot_ok else "MISSING", rel(boot_audit), "Boot audit reports pass=2, warn=0, fail=0." if boot_ok else "Boot package evidence missing or stale."),
        MatrixItem("F01", "function", "PS can initiate data transfer toward the infrared transmit path.", "single-lane hardware plus protocol simulation", "PASS_HW_G1" if g1_hw_ok else "MISSING", rel(g1_report), "G1 capped physical lane0 run has sent=rx_ok=267892 and tx_fail=0." if g1_hw_ok else "Missing G1 hardware send evidence."),
        MatrixItem("F02", "function", "Infrared receive path can return data to PS.", "single-lane hardware plus protocol simulation", "PASS_HW_G1" if g1_hw_ok else "MISSING", rel(g1_report), "G1 capped physical lane0 run has rx_ok=267892 and no loss." if g1_hw_ok else "Missing G1 receive evidence."),
        MatrixItem("F03", "function", "Packets larger than one infrared frame are fragmented and reassembled.", "RTL simulation plus G1 hardware payload", "PASS_SIM_HW_G1" if g1_fragment_ok and g1_hw_ok else "MISSING", rel(g1_report), "256-byte/16-fragment simulation passes and G1 hardware uses 256-byte payload." if g1_fragment_ok and g1_hw_ok else "Missing fragmented payload evidence."),
        MatrixItem("F04", "function", "Send complete, receive complete, error, retry, busy/idle, and link counters are observable.", "RTL/AXI simulation and host status parsing", "PASS_SIM_OFFLINE" if g1_feedback_ok and ps_pc_offline_ok else "MISSING", rel(g1_report), "AXI config/status counters and PC status response parsing are covered." if g1_feedback_ok and ps_pc_offline_ok else "Missing status/counter evidence."),
        MatrixItem("F05", "function", "Sender and receiver use an acknowledgement mechanism.", "RTL simulation and G1 run counters", "PASS_SIM_HW_G1" if g1_ack_loss_ok and g1_hw_ok else "MISSING", rel(g1_report), "ACK-loss recovery simulation passes; hardware capped run completes without failed TX." if g1_ack_loss_ok and g1_hw_ok else "Missing ACK evidence."),
        MatrixItem("F06", "function", "Lost fragment/ACK cases trigger retry and recovery.", "RTL impairment simulation", "PASS_SIM" if g1_ack_loss_ok and impair_ok else "MISSING", rel(post_summary), "ACK loss and multi-lane impair cases pass." if g1_ack_loss_ok and impair_ok else "Missing retry/recovery evidence."),
        MatrixItem("F07", "function", "CRC error frames are detected and are not accepted as valid data.", "RTL simulation", "PASS_SIM" if g1_crc_ok else "MISSING", rel(g1_report), "CRC single-lane simulation rejects invalid frame." if g1_crc_ok else "Missing CRC rejection evidence."),
        MatrixItem("F08", "function", "Retry exhaustion, protocol errors, receive errors, and bad payloads report explicit error status.", "RTL simulation and PC host tests", "PASS_SIM_OFFLINE" if g1_retry_exhaust_ok and ps_pc_offline_ok else "MISSING", rel(g1_report), "Retry exhausted and host error handling are covered." if g1_retry_exhaust_ok and ps_pc_offline_ok else "Missing error reporting evidence."),
        MatrixItem("F09", "function", "The link can recover and accept a new transfer after an exhausted or abnormal transfer.", "RTL simulation", "PASS_SIM" if g1_recover_ok else "MISSING", rel(g1_report), "Recover-after-exhaust simulation passes." if g1_recover_ok else "Missing post-error recovery evidence."),
        MatrixItem("F10", "function", "Design expands to up to 8 infrared lanes.", "RTL simulation only", "PASS_SIM_ONLY" if multi8_ok and maxfrag8_ok else "MISSING", rel(post_summary), "8-lane loopback and 2040-byte max-fragment 8-lane cases pass." if multi8_ok and maxfrag8_ok else "Missing 8-lane simulation evidence."),
        MatrixItem("F11", "function", "Rotating-side TX/RX correspondence can be found automatically as mapping changes.", "RTL simulation/model only", "PASS_SIM_MODEL" if autoroute8_ok and rotating_sim_ok and rotating_autoroute_offline_ok else "MISSING", rel(rotating_autoroute_offline), "Consolidated offline report covers 8-lane autoroute, 20 cm/600 rpm rotating stress, capped rotating model, two-AX7010 offline routing, and network fault recovery." if autoroute8_ok and rotating_sim_ok and rotating_autoroute_offline_ok else "Missing autoroute simulation/model evidence."),
        MatrixItem("F12", "function", "PC host can send commands, configuration, TX data, status queries, and clear commands to PS.", "offline TCP/mock and static source checks", "PASS_OFFLINE_NO_ETHERNET" if no_eth_ok and ps_pc_offline_ok and no_eth_boundary_ok else "MISSING", rel(no_eth_boundary), "No-Ethernet offline gate and boundary evidence cover host unit tests, mock traffic, reconnect, TCP fragmentation/coalescing, missing ACK timeout, TX error, oversize rejection, 4+4 lane-mask config, and PS bridge static checks." if no_eth_ok and ps_pc_offline_ok and no_eth_boundary_ok else "Missing PC-to-PS offline evidence."),
        MatrixItem("F13", "function", "PS can upload RX data, send results, receive results, errors, retry statistics, and health status to the host.", "offline TCP/mock and status parsing", "PASS_OFFLINE_NO_ETHERNET" if no_eth_ok and ps_pc_offline_ok and no_eth_boundary_ok else "MISSING", rel(no_eth_boundary), "Host offline mock, network fault model, and boundary evidence log ACK, RX data, status response, queued RX after reconnect, explicit ERROR handling, errors=0 for clean paths, and pending=0 after normal completion." if no_eth_ok and ps_pc_offline_ok and no_eth_boundary_ok else "Missing PS-to-PC upload evidence."),
        MatrixItem("N01", "network", "PS-to-PC communication supports TCP and reconnect behavior.", "offline plus safe real wrapper; no Ethernet real run", "PASS_OFFLINE_NO_ETHERNET" if no_eth_ok and no_eth_boundary_ok else "MISSING", rel(no_eth_boundary), "Offline TCP mock/reconnect, network fault recovery, reconnect payload exchange, TCP fragmentation/coalescing, and no-real-board boundary scenarios pass; real board TCP remains deferred by no Ethernet." if no_eth_ok and no_eth_boundary_ok else "Missing offline TCP evidence."),
        MatrixItem("N02", "network", "DHCP is supported, with static IP fallback for deployment/debug.", "source static check; real DHCP not run", "PASS_SOURCE_NO_ETHERNET" if ps_lwip_static_ok else "MISSING", rel(ps_lwip_static), "Structured PS lwIP static report confirms DHCP start/wait/timeout, static fallback 192.168.10.2/24, TCP bridge readiness, and no-real-board boundary; real DHCP still requires Ethernet." if ps_lwip_static_ok else "Missing DHCP/static source evidence."),
        MatrixItem("N03", "network", "Real board PS-to-PC TCP/DHCP acceptance passes on hardware.", "real board Ethernet test", "DEFERRED_NO_ETHERNET" if board_tcp_missing else "PASS_HW", rel(full_audit), "Current board/network condition has no Ethernet link; safe wrapper blocks on ethernet_link_not_up." if board_tcp_missing else "Real board TCP/DHCP evidence found."),
        MatrixItem("N04", "network", "Two complete AX7010 systems exchange PC traffic through the infrared link.", "real two-system hardware test", "MISSING_HARDWARE" if two_system_missing else "PASS_HW", rel(full_audit), "Offline two-endpoint model now passes 8-lane HDX plus RFCM-configured 4+4 FDX lane masks, but no two complete AX7010 hardware evidence exists." if two_system_missing and two_ax_offline_ok else ("Offline two-endpoint model is incomplete and no two complete AX7010 hardware evidence exists." if two_system_missing else "Two-system hardware evidence found.")),
        MatrixItem("P01", "performance", "Single lane raw PHY is 4 Mbit/s at 64 MHz.", "RTL timing/rate model", "PASS_SIM_RAW" if raw_rate_ok else "MISSING", rel(post_summary), "IR_PHY_RATE_MODEL_PASS reports raw_mbps=4.000000." if raw_rate_ok else "Missing raw rate evidence."),
        MatrixItem("P02", "performance", "8-lane half-duplex raw capacity reaches 32 Mbit/s and 4+4 full-duplex reaches 16 Mbit/s per direction.", "RTL model/arithmetic proof plus offline 8-lane bitstream candidate", "PASS_RAW_OFFLINE_BITSTREAM" if raw_rate_ok and rate_boundary_ok and reduced8_bitstream_raw_ok else "MISSING", rel(reduced8_bitstream), "Raw 32/16 capacity is proven by RTL arithmetic and by the reduced 8-lane fragment=16 offline candidate bitstream; sha256=F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778. This remains offline raw-PHY evidence, not effective payload or hardware acceptance." if raw_rate_ok and rate_boundary_ok and reduced8_bitstream_raw_ok else "Missing raw 32/16 offline bitstream evidence."),
        MatrixItem("P03", "performance", "Effective payload and PC-to-PC throughput are reported separately from raw PHY capacity.", "arithmetic proof, design-space model, and gap-closure model", "PASS_RAW_ONLY_BOUNDARY_DOCUMENTED" if payload_boundary_ok and rate_boundary_ok and payload_gap_closure_ok else "MISSING", rel(payload_gap_closure), "Best current packet-ACK payload is 28.966/14.483 Mbit/s; payload-gap model classifies 32/16 as raw-only unless per-lane raw rate rises to about 4.419 Mbit/s, lane count exceeds 8, or the target is explicitly changed. This passes the reporting-separation requirement, but does not claim 32/16 as effective payload." if payload_boundary_ok and rate_boundary_ok and payload_gap_closure_ok else "Missing payload boundary or gap-closure evidence."),
        MatrixItem("P04", "performance", "Full-duplex 4+4 lane partition can operate concurrently.", "RTL simulation plus full-system model", "PASS_SIM_ONLY" if fdx4_ok and full_twin_ok else "MISSING", rel(full_system_twin), "fdx_4plus4 passes with max_a_busy=4, max_b_busy=4, max_total_busy=8; full-system model records A->B TX/RX coverage 0x0f and B->A TX/RX coverage 0xf0." if fdx4_ok and full_twin_ok else "Missing full-duplex 4+4 simulation/model evidence."),
        MatrixItem("P05", "performance", "PC-side network path should not be the bottleneck for IR throughput.", "offline/source readiness only", "PASS_OFFLINE_NO_ETHERNET" if no_eth_ok and no_eth_boundary_ok else "MISSING", rel(no_eth_boundary), "Offline network protocol path is clean under normal and TCP-boundary scenarios; real Ethernet throughput cannot be checked without Ethernet." if no_eth_ok and no_eth_boundary_ok else "Missing network-side offline evidence."),
        MatrixItem("S01", "stability", "Continuous multi-packet traffic does not lose synchronization or deadlock in the accepted G1 scope.", "G1 capped hardware run and RTL regressions", "PASS_HW_G1" if g1_hw_ok else "MISSING", rel(g1_report), "Capped 540 s traffic stage delivered 267892/267892 packets with no TX fail." if g1_hw_ok else "Missing capped G1 stability evidence."),
        MatrixItem("S02", "stability", "Short impairments, lane changes, and route changes do not deadlock the model/simulation.", "RTL simulation/model", "PASS_SIM_MODEL" if impair_ok and degrade_ok and full_twin_ok else "MISSING", rel(full_system_twin), "Impair/degrade/full-system model pass with unrecovered_errors=0, deadlock_events=0, and explicit half/full-duplex lane coverage." if impair_ok and degrade_ok and full_twin_ok else "Missing impairment stability evidence."),
        MatrixItem("S03", "stability", "20 cm diameter, 600 rpm rotating-shaft behavior is covered in simulation/model.", "simulation/model only", "PASS_SIM_MODEL" if rotating_sim_ok and rotating_capped_model_ok and rotating_autoroute_offline_ok else "MISSING", rel(rotating_autoroute_offline), "Rotating stress, capped 8-lane rotating model, full-system twin, and no-overclaim boundary are consolidated in the offline evidence report." if rotating_sim_ok and rotating_capped_model_ok and rotating_autoroute_offline_ok else "Missing rotating model evidence."),
        MatrixItem("S04", "stability", "2-hour rotating stability target is modeled, while physical continuous tests obey the active 10-minute cap.", "model plus operational runtime cap", "PASS_MODEL_CAPPED_RUNTIME" if rotating_2h_model_ok and rotating_capped_model_ok and host_runtime_cap_ok and rotating_autoroute_offline_ok else "MISSING", rel(rotating_autoroute_offline), "2 h equivalent model exists, 8-lane model is capped at 600 s per the active safety rule, and the consolidated report marks this as offline/model evidence only." if rotating_2h_model_ok and host_runtime_cap_ok and rotating_autoroute_offline_ok else "Missing 2 h model or runtime cap evidence."),
        MatrixItem("S05", "stability", "Real 20 cm / 600 rpm rotating-shaft communication is physically validated.", "real rotating-shaft hardware test", "MISSING_HARDWARE" if real_rotation_missing else "PASS_HW", rel(rotating_autoroute_offline) if real_rotation_missing else rel(full_audit), "Consolidated simulation/model evidence exists and explicitly records REAL_ROTATING_SHAFT_ACCEPTANCE=0; no physical rotating shaft evidence exists." if real_rotation_missing else "Physical rotating evidence found."),
        MatrixItem("R01", "robustness", "Single and multiple lost fragments, ACK loss, CRC errors, and short blockages are handled.", "RTL simulation/model", "PASS_SIM_MODEL" if g1_ack_loss_ok and g1_crc_ok and impair_ok and full_twin_ok else "MISSING", rel(full_system_twin), "ACK loss, CRC rejection, multi-lane impair, short blockage, TCP reconnect, DHCP fallback, and full-system recovery paths pass." if g1_ack_loss_ok and g1_crc_ok and impair_ok and full_twin_ok else "Missing robustness evidence."),
        MatrixItem("R02", "robustness", "Duplicate/old/bad frames and protocol errors do not become accepted payload.", "RTL/host defensive tests", "PASS_SIM_OFFLINE" if g1_crc_ok and ps_pc_offline_ok else "MISSING", rel(g1_report), "CRC and protocol/host defensive tests are covered." if g1_crc_ok and ps_pc_offline_ok else "Missing bad-frame defense evidence."),
        MatrixItem("R03", "robustness", "Network abnormal conditions are reported and allow reconnect/reinitialization.", "offline and safe real wrapper", "PASS_OFFLINE_NO_ETHERNET" if no_eth_ok and no_eth_boundary_ok and board_tcp_missing else "MISSING", rel(no_eth_boundary), "Offline model covers TCP reset reconnect, host restart, cable-replug style reconnect, DHCP address change, DHCP timeout static fallback, queued RX after reconnect, missing TX ACK timeout, ERROR frames, oversize rejection, and protocol-desync diagnostics; safe real wrapper reports ethernet_link_not_up under current condition." if no_eth_ok and no_eth_boundary_ok else "Missing network abnormal evidence."),
        MatrixItem("H01", "host", "Host software can act as debug/control/data entry point.", "offline CLI acceptance", "PASS_OFFLINE_NO_ETHERNET" if no_eth_ok else "MISSING", rel(no_eth_summary), "rf_comm_client plus run_acceptance cover status/config/TX/reconnect flows offline." if no_eth_ok else "Missing host offline evidence."),
        MatrixItem("H02", "host", "Host can display device/link/TX/RX/error/statistics information.", "offline host status snapshot", "PASS_OFFLINE_NO_ETHERNET" if ps_pc_offline_ok and host_status_snapshot_ok else "MISSING", rel(host_status_snapshot), "Host status snapshot displays device/network state, TX/RX packets and rates, errors, pending frames, RTT, HDX 0xff coverage, 4+4 FDX lane masks, reconnect state, and no-hardware-action markers under the current no-Ethernet boundary." if ps_pc_offline_ok and host_status_snapshot_ok else "Missing explicit host status display snapshot."),
        MatrixItem("A01", "acceptance", "Full PC - PS - PL IR - external IR loop is closed on real hardware.", "real end-to-end product test", "PARTIAL_G1_ONLY" if g1_hw_ok and board_tcp_missing else "MISSING_HARDWARE", rel(full_audit), "Single-board/single-lane IR path is physically accepted; PC/PS real network and two-system end-to-end are not." if g1_hw_ok else "Missing real loop evidence."),
        MatrixItem("A02", "acceptance", "Up to 8 TFDU lanes are physically wired and validated.", "real 8-lane hardware test", "MISSING_HARDWARE" if eight_lane_hw_missing else "PASS_HW", rel(full_audit), "8-lane digital simulation passes, but real 8-lane TFDU hardware validation is absent." if eight_lane_hw_missing else "8-lane hardware evidence found."),
    ]

    meta = {
        "constraint": rel(constraint),
        "g1_report": rel(g1_report),
        "post_summary": rel(post_summary),
        "post_cases": rel(post_cases),
        "post_status": rel(post_status),
        "full_audit": rel(full_audit),
        "no_ethernet_summary": rel(no_eth_summary),
        "no_ethernet_csv": rel(no_eth_csv),
        "no_ethernet_boundary": rel(no_eth_boundary),
        "no_ethernet_boundary_csv": rel(no_eth_boundary_csv),
        "ps_lwip_bridge_static": rel(ps_lwip_static),
        "ps_lwip_bridge_static_csv": rel(ps_lwip_static_csv),
        "host_status_snapshot": rel(host_status_snapshot),
        "target_consistency": rel(target_consistency),
        "rate_boundary": rel(rate_boundary),
        "payload_gap_closure": rel(payload_gap_closure),
        "reduced8_bitstream": rel(reduced8_bitstream),
        "reduced8_bitstream_csv": rel(reduced8_bitstream_csv),
        "rotating_autoroute_offline": rel(rotating_autoroute_offline),
        "boot_audit": rel(boot_audit),
        "ps_bridge_static": rel(ps_bridge_static),
        "host_acceptance": rel(host_acceptance),
        "two_ax_safe": rel(two_ax_safe),
        "no_eth_tool": rel(no_eth_tool),
        "target_contains_tcp_dhcp": str(int("TCP" in constraint_text and "DHCP" in constraint_text)),
        "target_contains_rotation": str(int("600 rpm" in constraint_text and "20 cm" in constraint_text)),
    }
    return items, meta


def overall_status(items: list[MatrixItem]) -> str:
    blocking = {
        "FAIL",
        "MISSING",
        "MISSING_HARDWARE",
        "DEFERRED_NO_ETHERNET",
        "PARTIAL_G1_ONLY",
    }
    if any(item.status == "FAIL" for item in items):
        return "FAIL"
    if any(item.status in blocking for item in items):
        return "INCOMPLETE_REQUIREMENT_MATRIX"
    return "FULL_TARGET_MATRIX_PASS"


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    items, meta = build_items()
    status = overall_status(items)
    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "target_acceptance_matrix_current.md"
    json_path = REPORTS / "target_acceptance_matrix_current.json"
    csv_path = REPORTS / "target_acceptance_matrix_current.csv"

    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(items[0]).keys()))
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    md_rows = [
        [
            item.item_id,
            item.category,
            item.requirement,
            item.verification_scope,
            item.status,
            item.evidence,
            item.note,
        ]
        for item in items
    ]
    md = [
        "# RF_COMM Target Acceptance Matrix",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{status}`",
        f"- Requirements tracked: `{len(items)}`",
        "",
        "This matrix expands the hard project target into requirement-level evidence. It does not redefine the target; real hardware items remain incomplete until proven by hardware evidence.",
        "",
        "## Status Counts",
        "",
        md_table(["status", "count"], [[k, str(v)] for k, v in sorted(counts.items())]),
        "",
        "## Matrix",
        "",
        md_table(["id", "category", "requirement", "verification scope", "status", "evidence", "note"], md_rows),
        "",
        f"RF_COMM_TARGET_ACCEPTANCE_MATRIX overall={status}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": status,
        "meta": meta,
        "status_counts": counts,
        "items": [asdict(item) for item in items],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_TARGET_ACCEPTANCE_MATRIX overall={status} tracked={len(items)}")
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
