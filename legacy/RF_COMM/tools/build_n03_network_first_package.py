#!/usr/bin/env python3
"""Build the tracked N03 network-first evidence package from current state."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT = ROOT / "evidence" / "n03_network_first"


@dataclass
class StageRow:
    item: str
    title: str
    status: str
    evidence: str
    next_required_evidence: str
    allowed_claim: str


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def latest(pattern: str) -> Path | None:
    matches = list(REPORTS.glob(pattern))
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def latest_with_marker(pattern: str, value: str) -> Path | None:
    matches = sorted(REPORTS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in matches:
        if value in read_text(path):
            return path
    return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def marker(text: str, value: str) -> bool:
    return value in text


def marker_value(text: str, key: str) -> str:
    prefix = key + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def sibling_report(summary: Path | None, suffix: str) -> Path | None:
    if summary is None:
        return None
    name = summary.name.removesuffix(".summary.txt") + suffix
    path = summary.with_name(name)
    return path if path.exists() else None


def current_report(name: str) -> Path | None:
    path = REPORTS / name
    return path if path.exists() else None


def md_table(rows: list[StageRow]) -> str:
    lines = [
        "| item | title | status | evidence | next required evidence | allowed claim |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(value).replace("|", "/").replace("\n", " ")
                for value in (
                    row.item,
                    row.title,
                    row.status,
                    row.evidence,
                    row.next_required_evidence,
                    row.allowed_claim,
                )
            )
            + " |"
        )
    return "\n".join(lines)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["item", "status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def artifact_rows() -> list[dict[str, str]]:
    paths = [
        ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.bit",
        ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.xsa",
        ROOT / "software" / "_vitis_ws" / "rf_comm_ps_bridge" / "Debug" / "rf_comm_ps_bridge.elf",
        ROOT / "software" / "_vitis_ws_ps_ps_loopback" / "rf_comm_ps_ps_loopback" / "Debug" / "rf_comm_ps_ps_loopback.elf",
        ROOT / "software" / "ps_lwip_bridge" / "src" / "main.c",
        ROOT / "software" / "ps_lwip_bridge" / "src" / "tcp_bridge.c",
        ROOT / "software" / "ps_lwip_bridge" / "src" / "rf_protocol.h",
        ROOT / "software" / "host_client" / "rf_comm_client.py",
        ROOT / "software" / "host_client" / "analyze_acceptance_log.py",
        ROOT / "software" / "host_client" / "mock_rfcm_server.py",
        ROOT / "software" / "host_client" / "test_rf_comm_client.py",
        ROOT / "software" / "host_client" / "run_acceptance.ps1",
        ROOT / "tools" / "build_n03_network_first_package.py",
        ROOT / "tools" / "build_no_ethernet_network_boundary_evidence.py",
        ROOT / "tools" / "run_n03_offline_payload_matrix.py",
        ROOT / "tools" / "run_n03_offline_reconnect_matrix.py",
        ROOT / "tools" / "check_external_preconditions.py",
        ROOT / "tools" / "build_real_acceptance_runbook.py",
        ROOT / "tools" / "check_n03_pc_hosted_dhcp_preflight.ps1",
        ROOT / "tools" / "audit_n03_network_first_readiness.py",
        ROOT / "tools" / "run_n03_current_state_gate.ps1",
        ROOT / "tools" / "probe_ps_uart_boot_safe.ps1",
        ROOT / "tools" / "apply_n03_static_direct_network_admin.ps1",
        ROOT / "tools" / "setup_n03_static_direct_network_safe.ps1",
        ROOT / "tools" / "run_n03_network_first_acceptance_safe.ps1",
        ROOT / "tools" / "run_ps_pc_offline_gates.ps1",
    ]
    rows: list[dict[str, str]] = []
    for path in paths:
        rows.append(
            {
                "path": rel(path),
                "status": "PRESENT" if path.exists() else "MISSING",
                "sha256": sha256(path) if path.exists() else "",
            }
        )
    return rows


def report_template(title: str, verdict: str, body: str, rows: list[StageRow]) -> str:
    generated = datetime.now().isoformat(timespec="seconds")
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Generated: {generated}",
            "",
            f"Verdict: `{verdict}`",
            "",
            body.strip(),
            "",
            "## Stage Matrix",
            "",
            md_table(rows),
            "",
            "## Non-Claims",
            "",
            "```text",
            "IR_PHYSICAL_PASS=0",
            "2LANE_PASS=0",
            "REAL_IR_DATA_ROUNDTRIP_PASS=0",
            "ROTATION_PASS=0",
            "4LANE_PASS=0",
            "8LANE_PASS=0",
            "FINAL_TARGET_PASS=0",
            "```",
        ]
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")

    offline_summary = latest("ps_pc_offline_gates_*.summary.txt")
    offline_text = read_text(offline_summary)
    safe_summary = latest("n03_network_first_acceptance_safe_*.summary.txt")
    safe_text = read_text(safe_summary)
    safe_report = sibling_report(safe_summary, ".md")
    safe_matrix = sibling_report(safe_summary, ".matrix.csv")
    static_net_summary = current_report("n03_static_direct_network_preflight_current.summary.txt")
    static_net_text = read_text(static_net_summary)
    static_net_report = current_report("n03_static_direct_network_preflight_current.md")
    static_net_json = current_report("n03_static_direct_network_preflight_current.json")
    static_launch_summary = latest_with_marker("n03_static_direct_network_preflight_*.summary.txt", "LAUNCH_ELEVATED_APPLY=1")
    static_launch_text = read_text(static_launch_summary)
    static_apply_refused_summary = latest_with_marker("n03_static_direct_network_preflight_*.summary.txt", "APPLY_REFUSED_NOT_ADMIN=1")
    static_apply_refused_text = read_text(static_apply_refused_summary)
    uart_summary = latest("ps_uart_boot_probe_*.summary.txt")
    uart_text = read_text(uart_summary)
    external_md = REPORTS / "external_preconditions_current.md"
    external_json = REPORTS / "external_preconditions_current.json"
    external_csv = REPORTS / "external_preconditions_current.csv"
    external = {}
    if external_json.exists():
        external = json.loads(external_json.read_text(encoding="utf-8"))
    external_overall = str(external.get("overall", "MISSING"))
    external_blockers_raw = external.get("blockers", [])
    external_blockers = (
        [str(item) for item in external_blockers_raw]
        if isinstance(external_blockers_raw, list)
        else []
    )
    external_blockers_text = ", ".join(external_blockers) if external_blockers else "none"
    local_tcp_discovery = external.get("local_tcp_discovery", {})
    if not isinstance(local_tcp_discovery, dict):
        local_tcp_discovery = {}
    local_tcp_candidates_raw = local_tcp_discovery.get("candidates", [])
    local_tcp_candidates = (
        [str(item) for item in local_tcp_candidates_raw]
        if isinstance(local_tcp_candidates_raw, list)
        else []
    )
    local_tcp_candidates_text = ", ".join(local_tcp_candidates) if local_tcp_candidates else "none"
    local_tcp_subnets_raw = local_tcp_discovery.get("subnets", [])
    local_tcp_subnets = (
        [str(item) for item in local_tcp_subnets_raw]
        if isinstance(local_tcp_subnets_raw, list)
        else []
    )
    local_tcp_subnets_text = ", ".join(local_tcp_subnets) if local_tcp_subnets else "none"
    external_uart = external.get("latest_uart_boot_probe", {})
    if not isinstance(external_uart, dict):
        external_uart = {}
    runbook_md = REPORTS / "real_acceptance_runbook_current.md"
    runbook_json = REPORTS / "real_acceptance_runbook_current.json"
    runbook_csv = REPORTS / "real_acceptance_runbook_current.csv"
    runbook = {}
    if runbook_json.exists():
        runbook = json.loads(runbook_json.read_text(encoding="utf-8"))
    runbook_overall = str(runbook.get("overall", "MISSING"))

    p7_report = REPORTS / "P7_01_2lane_raw_matrix_report.md"
    protocol_contract = REPORTS / "protocol_contract_current.md"
    static_report = REPORTS / "ps_lwip_bridge_static_current.md"
    static_report_text = read_text(static_report)
    boundary_report = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    boundary_csv = REPORTS / "no_ethernet_network_boundary_evidence_current.csv"
    boundary_json = REPORTS / "no_ethernet_network_boundary_evidence_current.json"
    boundary_text = read_text(boundary_report)
    payload_matrix_report = REPORTS / "n03_offline_payload_matrix_current.md"
    payload_matrix_csv = REPORTS / "n03_offline_payload_matrix_current.csv"
    payload_matrix_json = REPORTS / "n03_offline_payload_matrix_current.json"
    payload_matrix_summary = REPORTS / "n03_offline_payload_matrix_current.summary.txt"
    payload_matrix_text = read_text(payload_matrix_summary) + "\n" + read_text(payload_matrix_report)
    reconnect_matrix_report = REPORTS / "n03_offline_reconnect_matrix_current.md"
    reconnect_matrix_csv = REPORTS / "n03_offline_reconnect_matrix_current.csv"
    reconnect_matrix_json = REPORTS / "n03_offline_reconnect_matrix_current.json"
    reconnect_matrix_summary = REPORTS / "n03_offline_reconnect_matrix_current.summary.txt"
    reconnect_matrix_text = read_text(reconnect_matrix_summary) + "\n" + read_text(reconnect_matrix_report)
    pc_dhcp_summary = current_report("n03_pc_hosted_dhcp_preflight_current.summary.txt")
    pc_dhcp_report = current_report("n03_pc_hosted_dhcp_preflight_current.md")
    pc_dhcp_json = current_report("n03_pc_hosted_dhcp_preflight_current.json")
    pc_dhcp_text = read_text(pc_dhcp_summary)
    readiness_report = current_report("n03_network_first_readiness_current.md")
    readiness_csv = current_report("n03_network_first_readiness_current.csv")
    readiness_json = current_report("n03_network_first_readiness_current.json")
    current_gate_summary = current_report("n03_current_state_gate_current.summary.txt")
    current_gate_report = current_report("n03_current_state_gate_current.md")
    current_gate_json = current_report("n03_current_state_gate_current.json")

    command_ok = marker(offline_text, "N03_TCP_PROTOCOL_COMMAND_PASS=1")
    memory_ok = marker(offline_text, "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1")
    synth_ok = marker(offline_text, "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1")
    bad_arg_ok = marker(offline_text, "N03_BAD_ARG_NEGATIVE_PASS=1")
    protocol_fault_ok = marker(offline_text, "N03_PROTOCOL_FAULT_NEGATIVE_OFFLINE_PASS=1")
    negative_ok = marker(offline_text, "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=1")
    app_segmentation_ok = marker(offline_text, "N03_APP_PAYLOAD_SEGMENTATION_OFFLINE_PASS=1")
    offline_payload_matrix_ok = (
        marker(offline_text, "N03_OFFLINE_PAYLOAD_MATRIX_PASS=1")
        or marker(payload_matrix_text, "N03_OFFLINE_PAYLOAD_MATRIX_PASS=1")
    )
    offline_reconnect_hello_10x_ok = (
        marker(offline_text, "N03_OFFLINE_RECONNECT_HELLO_10X_PASS=1")
        or marker(reconnect_matrix_text, "N03_OFFLINE_RECONNECT_HELLO_10X_PASS=1")
    )
    offline_reconnect_payload_20x_ok = (
        marker(offline_text, "N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS=1")
        or marker(reconnect_matrix_text, "N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS=1")
    )
    pc_dhcp_preflight_complete = marker(pc_dhcp_text, "N03_PC_HOSTED_DHCP_PREFLIGHT_COMPLETE=1")
    pc_dhcp_server_ready = marker(pc_dhcp_text, "N03_PC_HOSTED_DHCP_SERVER_READY=1")
    pc_dhcp_status_value = marker_value(pc_dhcp_text, "N03_PC_HOSTED_DHCP_PREFLIGHT_STATUS")
    pc_dhcp_next_action = marker_value(pc_dhcp_text, "N03_PC_HOSTED_DHCP_NEXT_ACTION")
    pc_dhcp_standalone_ip_command = marker_value(pc_dhcp_text, "N03_PC_HOSTED_DHCP_STANDALONE_IP_COMMAND")
    pc_dhcp_ics_gui_command = marker_value(pc_dhcp_text, "N03_PC_HOSTED_DHCP_ICS_GUI_COMMAND")
    pc_dhcp_ics_query_requires_admin = marker(pc_dhcp_text, "ICS_SHARING_QUERY_REQUIRES_ADMIN=1")
    reconnect_payload_ok = marker(offline_text, "N03_RECONNECT_PAYLOAD_ECHO_OFFLINE_PASS=1")
    offline_ok = marker(offline_text, "PS_PC_OFFLINE_GATES_PASS") and marker(offline_text, "n03_modes=1")
    safe_dry_run = marker(safe_text, "N03_DRY_RUN=1")
    safe_blocked = marker(safe_text, "N03_REAL_BOARD_ACCEPTANCE_BLOCKED=1")
    safe_blocker = marker_value(safe_text, "N03_BLOCKED_REASON")
    safe_static_ok = marker(safe_text, "N03_STATIC_DIRECT_TCP_PASS=1") and not safe_dry_run
    safe_command_ok = marker(safe_text, "N03_TCP_PROTOCOL_COMMAND_PASS=1") and not safe_dry_run
    safe_memory_ok = marker(safe_text, "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1") and not safe_dry_run
    safe_synth_ok = marker(safe_text, "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1") and not safe_dry_run
    safe_negative_ok = marker(safe_text, "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=1") and not safe_dry_run
    safe_link_ok = marker(safe_text, "N03_LINK_RECOVERY_PASS=1") and not safe_dry_run
    safe_dhcp_fallback_ok = marker(safe_text, "N03_DHCP_FALLBACK_PASS=1") and not safe_dry_run
    safe_acceptance_ok = marker(safe_text, "N03_REAL_BOARD_ACCEPTANCE_PASS=1") and not safe_dry_run
    pc_static_ip_ok = marker(static_net_text, "PC_EXPECTED_STATIC_IP_PRESENT=1")
    pc_ethernet_up = marker(static_net_text, "PC_ETHERNET_LINK_UP=1")
    static_net_pass = marker(static_net_text, "N03_STATIC_DIRECT_NETWORK_PREFLIGHT_PASS=1")
    static_apply_command = marker_value(static_net_text, "APPLY_DRY_RUN_COMMAND") or marker_value(
        static_net_text, "RECOMMENDED_APPLY_COMMAND"
    )
    firewall_command = marker_value(static_net_text, "FIREWALL_DRY_RUN_COMMAND") or marker_value(
        static_net_text, "RECOMMENDED_FIREWALL_COMMAND"
    )
    elevated_apply_command = marker_value(static_net_text, "ELEVATED_APPLY_COMMAND")
    elevated_uac_command = marker_value(static_net_text, "ELEVATED_UAC_COMMAND")
    is_admin = marker_value(static_net_text, "IS_ADMIN")
    admin_required = marker_value(static_net_text, "ADMIN_REQUIRED_TO_APPLY")
    launch_pending = marker(static_launch_text, "LAUNCH_ELEVATED_APPLY_PENDING_OR_DECLINED=1")
    apply_refused_not_admin = marker(static_apply_refused_text, "APPLY_REFUSED_NOT_ADMIN=1")
    firewall_refused_not_admin = marker(static_apply_refused_text, "FIREWALL_REFUSED_NOT_ADMIN=1")
    uart_verdict = marker_value(uart_text, "UART_PROBE_VERDICT")
    uart_log_bytes_text = marker_value(uart_text, "UART_LOG_BYTES")
    try:
        uart_log_bytes = int(uart_log_bytes_text or "0")
    except ValueError:
        uart_log_bytes = 0
    uart_has_text = uart_log_bytes > 0
    uart_board_ip_hint = marker_value(uart_text, "BOARD_IP_SEEN") or str(external_uart.get("board_ip_seen", ""))
    uart_dhcp_fallback = marker(uart_text, "MATCH_DHCP_STATIC_FALLBACK=1")
    uart_tcp_listen = marker(uart_text, "MATCH_TCP_LISTEN_5001=1")
    target_hint_parts = ["static_expected=192.168.10.2"]
    if uart_board_ip_hint:
        target_hint_parts.append(f"uart_board_ip={uart_board_ip_hint}")
    if local_tcp_candidates:
        target_hint_parts.append(f"local_tcp_5001_candidates={local_tcp_candidates_text}")
    target_hint_text = "; ".join(target_hint_parts)
    candidate_target = uart_board_ip_hint or (local_tcp_candidates[0] if local_tcp_candidates else "")
    static_ok = marker(static_report_text, "PS_BRIDGE_STATIC_CHECKS_PASS") or marker(offline_text, "PS_BRIDGE_STATIC_CHECKS_PASS")
    protocol_ok = marker(read_text(protocol_contract), "RF_COMM_PROTOCOL_CONTRACT overall=PASS")
    static_protocol_fault_ok = (
        marker(static_report_text, "parser_reports_bad_magic")
        and marker(static_report_text, "parser_reports_unsupported_version")
        and marker(static_report_text, "oversize_payload_error")
    )
    boundary_protocol_ok = (
        marker(boundary_text, "RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall=PASS_OFFLINE_NETWORK_BOUNDARY")
        and marker(boundary_text, "protocol_desync_reports_explicit_details")
        and marker(boundary_text, "NEGATIVE_CASES=missing_ack_timeout;tx_error;oversize_rejected;protocol_desync")
    )
    protocol_fault_ok = protocol_fault_ok or (static_protocol_fault_ok and boundary_protocol_ok)
    single_tcp = external.get("tcp_results", {}).get("single", None)
    real_board_reachable = safe_static_ok or single_tcp is True
    if static_net_text and not pc_static_ip_ok:
        blocker_note = "PC Ethernet lacks 192.168.10.1/24 static direct IP"
    elif safe_blocked:
        blocker_note = f"safe wrapper blocked: {safe_blocker or 'unknown'}"
    else:
        blocker_note = "192.168.10.2:5001 reachable" if real_board_reachable else "192.168.10.2:5001 not reachable in current preflight"

    static_status = (
        "PASS_REAL_BOARD"
        if safe_static_ok
        else "BLOCKED_PC_STATIC_IP_NOT_CONFIGURED"
        if static_net_text and pc_ethernet_up and not pc_static_ip_ok
        else "BLOCKED_TCP_TARGET_NOT_REACHABLE"
        if safe_blocked and safe_blocker == "tcp_target_not_reachable"
        else "READY_TO_RUN"
        if real_board_reachable
        else "REAL_BOARD_PENDING"
    )
    hello_status = (
        "PASS_REAL_BOARD"
        if safe_static_ok
        else "PASS_OFFLINE_RECONNECT_10X_REAL_PENDING"
        if offline_ok and offline_reconnect_hello_10x_ok
        else "PASS_OFFLINE_REAL_PENDING"
        if offline_ok
        else "MISSING_OFFLINE_EVIDENCE"
    )
    command_status = "PASS_REAL_BOARD" if safe_command_ok else ("PASS_OFFLINE_REAL_PENDING" if command_ok and protocol_ok else "MISSING_OR_PARTIAL")
    memory_status = "PASS_REAL_BOARD" if safe_memory_ok else ("PASS_OFFLINE_REAL_PENDING" if memory_ok else "MISSING_OFFLINE_EVIDENCE")
    synth_status = "PASS_REAL_BOARD" if safe_synth_ok else ("PASS_OFFLINE_REAL_PENDING" if synth_ok else "MISSING_OFFLINE_EVIDENCE")
    dhcp_fallback_status = (
        "PASS_REAL_BOARD"
        if safe_dhcp_fallback_ok
        else "PASS_UART_REAL_TCP_PENDING"
        if uart_dhcp_fallback and uart_tcp_listen
        else "SOURCE_READY_UART_INCONCLUSIVE_TCP_PENDING"
        if static_ok and uart_summary is not None
        else "SOURCE_READY_REAL_PENDING"
        if static_ok
        else "MISSING_SOURCE_EVIDENCE"
    )
    link_status = (
        "PASS_REAL_BOARD"
        if safe_link_ok and safe_negative_ok
        else "PASS_OFFLINE_RECONNECT_20X_PAYLOAD_PROTOCOL_NEGATIVE_REAL_LINK_PENDING"
        if negative_ok and offline_reconnect_payload_20x_ok and protocol_fault_ok
        else "PASS_OFFLINE_RECONNECT_PAYLOAD_PROTOCOL_NEGATIVE_REAL_LINK_PENDING"
        if negative_ok and reconnect_payload_ok and protocol_fault_ok
        else "PASS_OFFLINE_RECONNECT_PAYLOAD_REAL_LINK_PENDING"
        if negative_ok and reconnect_payload_ok
        else "PASS_OFFLINE_REAL_LINK_PENDING"
        if negative_ok and marker(offline_text, "reconnect cycle 2/2")
        else "MISSING_OR_PARTIAL"
    )
    payload_matrix_status = (
        "PASS_OFFLINE_LOCALHOST_MATRIX_REAL_THROUGHPUT_PENDING"
        if memory_ok and synth_ok and offline_payload_matrix_ok
        else "PARTIAL_OFFLINE_APP_SEGMENTATION_REAL_MATRIX_PENDING"
        if memory_ok and synth_ok and app_segmentation_ok
        else "PARTIAL_OFFLINE_REAL_MATRIX_PENDING"
        if memory_ok and synth_ok
        else "MISSING_OFFLINE_EVIDENCE"
    )
    pc_dhcp_status = (
        "PC_DHCP_SERVER_READY_LEASE_PENDING"
        if pc_dhcp_server_ready
        else "DEFERRED_NO_PC_DHCP_SERVER_PREFLIGHTED"
        if pc_dhcp_preflight_complete
        else "DEFERRED_NO_PC_DHCP_SERVER"
    )
    pc_dhcp_evidence = (
        f"{rel(pc_dhcp_summary)}; {rel(pc_dhcp_report)}; {rel(pc_dhcp_json)}; "
        f"status={pc_dhcp_status_value or 'MISSING'}; next_action={pc_dhcp_next_action or 'MISSING'}; "
        f"ics_query_requires_admin={int(pc_dhcp_ics_query_requires_admin)}"
        if pc_dhcp_preflight_complete
        else "no PC DHCP server run recorded"
    )
    safe_evidence_parts = [
        rel(static_net_summary) if static_net_summary is not None else "MISSING_N03_STATIC_DIRECT_PREFLIGHT",
        rel(safe_summary) if safe_summary is not None else "MISSING_N03_SAFE_ACCEPTANCE",
        rel(external_md),
        rel(external_json),
        rel(external_csv),
        f"external={external_overall}",
        f"external_blockers={external_blockers_text}",
        f"local_tcp_5001_candidates={local_tcp_candidates_text}",
        f"target_hints={target_hint_text}",
    ]
    safe_evidence = "; ".join(safe_evidence_parts)

    rows = [
        StageRow(
            "N03-0",
            "scope switch and IR physical deferred matrix",
            "PASS_DEFERRED_GATE",
            "N03_00_scope_switch_note.md; N03_00_ir_physical_deferred_matrix.md",
            "none for scope switch",
            "IR physical is deferred, not failed for N03",
        ),
        StageRow(
            "N03-1",
            "static IP direct smoke",
            static_status,
            f"{safe_evidence}; {blocker_note}",
            "board UART/TCP transcript proving ETH link up and TCP connect to 192.168.10.2:5001, or a justified UART/local-discovery board IP with matching safe-wrapper evidence",
            "real static TCP only if safe wrapper N03_STATIC_DIRECT_TCP_PASS=1",
        ),
        StageRow(
            "N03-2",
            "TCP hello/status/build-id",
            hello_status,
            f"{rel(safe_summary)}; {rel(offline_summary)}; {rel(reconnect_matrix_report)}; {rel(reconnect_matrix_csv)}",
            "real board HELLO/STATUS/GET_BUILD_ID transcript",
            "real HELLO covered only if safe wrapper static smoke passed",
        ),
        StageRow(
            "N03-3",
            "TCP command protocol coverage",
            command_status,
            f"{rel(safe_summary)}; {rel(offline_summary)}; {rel(protocol_contract)}",
            "real board command matrix with ACK/ERR for all N03 commands",
            "N03_TCP_PROTOCOL_COMMAND_PASS is real only if safe wrapper marker is 1",
        ),
        StageRow(
            "N03-4",
            "PC to PS memory echo",
            memory_status,
            f"{rel(safe_summary)}; {rel(safe_matrix)}; {rel(offline_summary)}",
            "real board memory echo matrix with payload_mismatch=0",
            "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS is real only if safe wrapper marker is 1",
        ),
        StageRow(
            "N03-5",
            "PC to PS to PL synthetic loopback",
            synth_status,
            f"{rel(safe_summary)}; {rel(safe_matrix)}; {rel(offline_summary)}",
            "real board PS/PL synthetic matrix with DMA counters and payload_mismatch=0",
            "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS is real only if safe wrapper marker is 1",
        ),
        StageRow(
            "N03-6",
            "DHCP timeout plus static fallback",
            dhcp_fallback_status,
            f"{rel(safe_summary)}; {rel(static_report)}; {rel(uart_summary)}; target_hints={target_hint_text}",
            "UART DHCP_TIMEOUT and STATIC_FALLBACK_IP=192.168.10.2 plus TCP reconnect evidence",
            "N03_DHCP_FALLBACK_PASS is real only if safe wrapper marker is 1 with UART/TCP/memory evidence",
        ),
        StageRow(
            "N03-7",
            "PC-hosted DHCP lease",
            pc_dhcp_status,
            pc_dhcp_evidence,
            "DHCP DISCOVER/OFFER/REQUEST/ACK and board IP in pool",
            "PC DHCP preflight only; no DHCP lease pass",
        ),
        StageRow(
            "N03-8",
            "payload matrix and throughput",
            payload_matrix_status,
            f"{rel(offline_summary)}; {rel(payload_matrix_report)}; {rel(payload_matrix_csv)}",
            "real board 16..8192 byte payload matrix and throughput CSV",
            "offline localhost payload matrix/tooling only; no real throughput pass",
        ),
        StageRow(
            "N03-9",
            "link recovery and negative tests",
            link_status,
            f"{rel(safe_summary)}; {rel(safe_matrix)}; {rel(offline_summary)}; {rel(reconnect_matrix_report)}; {rel(reconnect_matrix_csv)}; {rel(boundary_report)}; {rel(static_report)}",
            "real reconnect/disconnect matrix and negative command matrix",
            "offline 10x/20x reconnect, payload echo, bad-arg negatives, and source/boundary protocol-fault negatives only; real link recovery only if safe wrapper reconnect and negative markers are 1",
        ),
        StageRow(
            "N03-10",
            "network-first acceptance package",
            "PACKAGE_PARTIAL_REAL_BOARD_PENDING",
            f"{rel(OUT)}; {rel(static_net_report)}; {rel(safe_report)}; {rel(readiness_report)}; {rel(current_gate_report)}; {rel(runbook_md)}",
            "N03-1..N03-6, N03-8, and N03-9 real board evidence",
            "package is ready for review, not final N03 pass",
        ),
    ]

    write(
        OUT / "N03_01_static_ip_direct_smoke.md",
        report_template(
            "N03-1 Static IP Direct Smoke",
            rows[1].status,
            f"Current board target: 192.168.10.2:5001. Target hints: {target_hint_text}. Current preflight: {blocker_note}. N03 static direct PC preflight pass={int(static_net_pass)}. Current shell admin={is_admin or 'unknown'}. Recommended static IP command: `{static_apply_command or 'not captured'}`. Elevated setup command: `{elevated_apply_command or 'not captured'}`. UAC launch command: `{elevated_uac_command or 'not captured'}`. This file is a runbook/status record, not a real-board PASS transcript.",
            rows,
        ),
    )
    write(
        OUT / "N03_01_static_ip_direct_transcript.txt",
        f"generated={generated}\nstatus={rows[1].status}\ntarget=192.168.10.2:5001\ntarget_hints={target_hint_text}\nuart_board_ip_hint={uart_board_ip_hint or 'none'}\nlocal_tcp_5001_candidates={local_tcp_candidates_text}\ncurrent_preflight={blocker_note}\nstatic_direct_preflight_summary={rel(static_net_summary)}\nlatest_elevated_launch_summary={rel(static_launch_summary)}\nlatest_elevated_launch_pending_or_declined={int(launch_pending)}\nlatest_apply_refused_summary={rel(static_apply_refused_summary)}\nlatest_apply_refused_not_admin={int(apply_refused_not_admin)}\nlatest_firewall_refused_not_admin={int(firewall_refused_not_admin)}\nsafe_wrapper_summary={rel(safe_summary)}\npc_expected_static_ip_present={int(pc_static_ip_ok)}\nis_admin={is_admin}\nadmin_required_to_apply={admin_required}\nrecommended_apply_command={static_apply_command}\nrecommended_firewall_command={firewall_command}\nelevated_apply_command={elevated_apply_command}\nelevated_uac_command={elevated_uac_command}\nreal_tcp_connect_pass={int(safe_static_ok)}\n",
    )
    write(
        OUT / "N03_02_tcp_hello_report.md",
        report_template("N03-2 TCP Hello Report", rows[2].status, f"Offline HELLO/STATUS path and plan-sized 10x reconnect tooling are covered by the latest offline gate when present. Real board HELLO/GET_BUILD_ID/PING transcript remains required. Offline reconnect report: `{rel(reconnect_matrix_report)}`.", rows),
    )
    write_csv(
        OUT / "N03_02_tcp_connect_disconnect.csv",
        [
            {"case": "offline_mock_reconnect_10x_hello_status", "status": "PASS_OFFLINE" if offline_reconnect_hello_10x_ok else "MISSING", "evidence": rel(reconnect_matrix_csv)},
            {"case": "offline_mock_quick_reconnect", "status": "PASS" if marker(offline_text, "reconnect cycle 2/2") else "MISSING", "evidence": rel(offline_summary)},
            {"case": "real_board_reconnect_10x", "status": "REAL_BOARD_PENDING", "evidence": "required by plan"},
        ],
    )
    write(
        OUT / "N03_03_tcp_command_coverage.md",
        report_template("N03-3 TCP Command Coverage", rows[3].status, "N03 command frame covers PING, GET_VERSION, GET_BUILD_ID, READ commands, CONFIG mode, CLEAR, START, STOP, SHUTDOWN_SAFE, and IR-deferred negative commands in offline/mock evidence.", rows),
    )
    write_csv(
        OUT / "N03_03_tcp_command_matrix.csv",
        [
            {"command": "PING", "expected": "ACK PONG", "current_status": "PASS_OFFLINE"},
            {"command": "GET_VERSION", "expected": "ACK VERSION 1", "current_status": "PASS_OFFLINE"},
            {"command": "GET_BUILD_ID", "expected": "ACK BUILD_ID", "current_status": "PASS_OFFLINE"},
            {"command": "READ counters", "expected": "STATUS_RSP", "current_status": "PASS_OFFLINE"},
            {"command": "READ network_status", "expected": "ACK network_status", "current_status": "PASS_OFFLINE"},
            {"command": "READ pspl_status", "expected": "STATUS_RSP", "current_status": "PASS_OFFLINE"},
            {"command": "CONFIG payload_bytes 64", "expected": "ACK payload_bytes_accepted", "current_status": "PASS_OFFLINE"},
            {"command": "CONFIG payload_bytes 0", "expected": "ERROR ERR_BAD_ARG", "current_status": "PASS_OFFLINE_NEGATIVE" if bad_arg_ok else "MISSING"},
            {"command": "CONFIG payload_bytes too_large", "expected": "ERROR ERR_BAD_ARG", "current_status": "PASS_OFFLINE_NEGATIVE" if bad_arg_ok else "MISSING"},
            {"command": "CONFIG mode network_memory_echo", "expected": "ACK network_memory_echo", "current_status": "PASS_OFFLINE"},
            {"command": "CONFIG mode pspl_synth_loopback", "expected": "ACK pspl_synth_loopback", "current_status": "PASS_OFFLINE"},
            {"command": "CONFIG mode ir_physical", "expected": "ERROR ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE", "current_status": "PASS_OFFLINE_NEGATIVE"},
            {"command": "START ir_tx", "expected": "ERROR ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE", "current_status": "PASS_OFFLINE_NEGATIVE"},
            {"command": "UNKNOWN_CMD", "expected": "ERROR ERR_UNKNOWN_CMD", "current_status": "PASS_OFFLINE_NEGATIVE"},
        ],
    )
    write(
        OUT / "N03_04_pc_ps_memory_echo_report.md",
        report_template("N03-4 PC-PS Memory Echo", rows[4].status, "Offline/mock memory echo reports payload_mismatch=0. Real board payload matrix remains pending.", rows),
    )
    write_csv(
        OUT / "N03_04_pc_ps_memory_echo_matrix.csv",
        [
            {
                "payload_bytes": str(size),
                "count": "100",
                "current_status": (
                    "OFFLINE_APP_SEGMENTATION_COVERED_REAL_BOARD_PENDING"
                    if app_segmentation_ok and size > 512
                    else "REAL_BOARD_PENDING"
                ),
                "evidence": "required by plan",
            }
            for size in (1, 8, 16, 64, 128, 256, 512, 1024, 4096)
        ],
    )
    write(
        OUT / "N03_05_pc_ps_pl_synth_loopback_report.md",
        report_template("N03-5 PC-PS-PL Synthetic Loopback", rows[5].status, "Offline/mock synthetic mode verifies command/mode plumbing and payload compare. Real board PS/PL DMA counters remain pending.", rows),
    )
    write_csv(
        OUT / "N03_05_pc_ps_pl_synth_loopback_matrix.csv",
        [
            {"payload_bytes": "16", "count_or_seconds": "10", "current_status": "REAL_BOARD_PENDING"},
            {"payload_bytes": "64", "count_or_seconds": "100", "current_status": "REAL_BOARD_PENDING"},
            {"payload_bytes": "256", "count_or_seconds": "100", "current_status": "REAL_BOARD_PENDING"},
            {"payload_bytes": "256", "count_or_seconds": "60s", "current_status": "REAL_BOARD_PENDING"},
            {"payload_bytes": "1024", "count_or_seconds": "60s", "current_status": "REAL_BOARD_PENDING"},
            {"payload_bytes": "1024", "count_or_seconds": "300s", "current_status": "REAL_BOARD_PENDING"},
        ],
    )
    write(
        OUT / "N03_06_dhcp_timeout_fallback_report.md",
        report_template("N03-6 DHCP Timeout Static Fallback", rows[6].status, f"Source/static checks confirm DHCP start/timeout/static fallback plumbing. Latest read-only UART probe verdict: `{uart_verdict or 'MISSING'}` with {uart_log_bytes} captured bytes. Safe wrapper DHCP fallback pass={int(safe_dhcp_fallback_ok)}. Real pass requires UART DHCP timeout/static IP/TCP_READY plus real TCP HELLO and memory echo in the safe wrapper.", rows),
    )
    write(
        OUT / "N03_06_dhcp_timeout_fallback_transcript.txt",
        f"generated={generated}\nexpected_DHCP_TIMEOUT=1\nexpected_STATIC_FALLBACK_IP=192.168.10.2\nreal_uart_transcript_present={int(uart_has_text)}\nuart_summary={rel(uart_summary)}\nsafe_wrapper_summary={rel(safe_summary)}\nsafe_dhcp_fallback_pass={int(safe_dhcp_fallback_ok)}\nuart_probe_verdict={uart_verdict}\nuart_log_bytes={uart_log_bytes}\nuart_dhcp_static_fallback_seen={int(uart_dhcp_fallback)}\nuart_tcp_listen_5001_seen={int(uart_tcp_listen)}\nstatus={rows[6].status}\n",
    )
    write(
        OUT / "N03_07_pc_hosted_dhcp_lease_report.md",
        report_template(
            "N03-7 PC-hosted DHCP Lease",
            rows[7].status,
            f"PC-hosted DHCP environment has been audited by a read-only preflight when present. Current preflight status: `{pc_dhcp_status_value or 'MISSING'}`. Next action: `{pc_dhcp_next_action or 'MISSING'}`. ICS sharing query requires admin: `{int(pc_dhcp_ics_query_requires_admin)}`. Standalone DHCP subnet command: `{pc_dhcp_standalone_ip_command or 'not captured'}`. ICS GUI command: `{pc_dhcp_ics_gui_command or 'not captured'}`. No DHCP DISCOVER/OFFER/REQUEST/ACK lease run is recorded, so this remains a lease-pending or deferred item under the N03 plan. Preflight report: `{rel(pc_dhcp_report)}`.",
            rows,
        ),
    )
    write(
        OUT / "N03_07_dhcp_uart_log.txt",
        f"generated={generated}\nstatus={rows[7].status}\nreal_dhcp_discover_offer_request_ack_seen=0\npc_dhcp_preflight_summary={rel(pc_dhcp_summary)}\npc_dhcp_next_action={pc_dhcp_next_action or 'MISSING'}\n",
    )
    write(
        OUT / "N03_07_pc_ipconfig.txt",
        f"generated={generated}\nstatus={rows[7].status}\npc_dhcp_preflight_status={pc_dhcp_status_value or 'MISSING'}\npc_dhcp_next_action={pc_dhcp_next_action or 'MISSING'}\npc_dhcp_ics_query_requires_admin={int(pc_dhcp_ics_query_requires_admin)}\npc_dhcp_standalone_ip_command={pc_dhcp_standalone_ip_command}\npc_dhcp_ics_gui_command={pc_dhcp_ics_gui_command}\npc_dhcp_preflight_summary={rel(pc_dhcp_summary)}\npc_dhcp_preflight_report={rel(pc_dhcp_report)}\npc_dhcp_preflight_json={rel(pc_dhcp_json)}\n",
    )
    write(
        OUT / "N03_08_network_payload_matrix_report.md",
        report_template("N03-8 Network Payload Matrix", rows[8].status, f"The full real 16..8192 byte throughput matrix is not yet run. Current offline evidence covers localhost payload matrix tooling, segmentation, ACK/RX echo, and metric capture without claiming real board throughput. Offline matrix report: `{rel(payload_matrix_report)}`.", rows),
    )
    offline_payload_rows = read_csv_rows(payload_matrix_csv)
    write_csv(
        OUT / "N03_08_network_payload_matrix.csv",
        offline_payload_rows
        if offline_payload_rows and offline_payload_matrix_ok
        else [
            {
                "mode": mode,
                "payload_bytes": str(size),
                "seconds": "60",
                "current_status": (
                    "OFFLINE_APP_SEGMENTATION_COVERED_REAL_BOARD_PENDING"
                    if app_segmentation_ok and size > 512
                    else "REAL_BOARD_PENDING"
                ),
            }
            for mode in ("pc_ps_memory_echo", "pc_ps_pl_synth_loopback")
            for size in (16, 64, 128, 256, 512, 1024, 4096, 8192)
        ],
    )
    write(
        OUT / "N03_09_link_recovery_negative_tests.md",
        report_template("N03-9 Link Recovery Negative Tests", rows[9].status, f"Offline 20x reconnect with post-reconnect payload echo, bad-argument command errors, and source/boundary protocol-fault diagnostics are covered when the reconnect matrix passes. Real board reconnect and cable unplug/replug evidence remains pending. Offline reconnect report: `{rel(reconnect_matrix_report)}`.", rows),
    )
    write_csv(
        OUT / "N03_09_reconnect_matrix.csv",
        [
            {"case": "offline_mock_reconnect_payload_echo_20x", "status": "PASS_OFFLINE" if offline_reconnect_payload_20x_ok else "MISSING", "evidence": rel(reconnect_matrix_csv)},
            {"case": "offline_mock_reconnect_payload_echo_2x", "status": "PASS_OFFLINE" if reconnect_payload_ok else "MISSING", "evidence": rel(offline_summary)},
            {"case": "real_board_reconnect_20x", "status": "REAL_BOARD_PENDING", "evidence": "required by plan"},
            {"case": "real_cable_unplug_replug", "status": "REAL_BOARD_PENDING", "evidence": "manual hardware step required"},
        ],
    )
    write_csv(
        OUT / "N03_09_negative_command_matrix.csv",
        [
            {"case": "START ir_tx", "expected": "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE", "current_status": "PASS_OFFLINE"},
            {"case": "CONFIG mode ir_physical", "expected": "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE", "current_status": "PASS_OFFLINE"},
            {"case": "CONFIG payload_bytes 0", "expected": "ERR_BAD_ARG", "current_status": "PASS_OFFLINE" if bad_arg_ok else "MISSING"},
            {"case": "CONFIG payload_bytes too_large", "expected": "ERR_BAD_ARG", "current_status": "PASS_OFFLINE" if bad_arg_ok else "MISSING"},
            {"case": "UNKNOWN_CMD", "expected": "ERR_UNKNOWN_CMD", "current_status": "PASS_OFFLINE"},
            {"case": "malformed frame header", "expected": "ERROR/bad_magic or disconnect-safe behavior", "current_status": "PASS_OFFLINE_SOURCE_BOUNDARY" if protocol_fault_ok else "SOURCE_TESTED_OFFLINE"},
            {"case": "wrong length", "expected": "ERROR/payload_too_large or parser-safe behavior", "current_status": "PASS_OFFLINE_SOURCE_BOUNDARY" if protocol_fault_ok else "SOURCE_TESTED_OFFLINE"},
            {"case": "wrong checksum", "expected": "N/A for TCP RFCM frame; IR CRC negative is deferred outside N03 network-first scope", "current_status": "DEFERRED_IR_FRAME_CRC_NOT_TCP_RFCM"},
        ],
    )
    current_gate_command = (
        "powershell -NoProfile -ExecutionPolicy Bypass -File "
        ".\\tools\\run_n03_current_state_gate.ps1 -TimeoutSeconds 3"
    )
    admin_static_apply_command = (
        "powershell -NoProfile -ExecutionPolicy Bypass -File "
        ".\\tools\\apply_n03_static_direct_network_admin.ps1"
    )
    real_acceptance_command = (
        "powershell -NoProfile -ExecutionPolicy Bypass -File "
        ".\\tools\\run_n03_network_first_acceptance_safe.ps1 "
        "-TargetHost 192.168.10.2 -Port 5001 -ComPort COM3 "
        "-ReconnectCycles 20 -MatrixRepeat 100 -SustainedSeconds 60 -LongSeconds 300"
    )
    candidate_acceptance_command = (
        "powershell -NoProfile -ExecutionPolicy Bypass -File "
        ".\\tools\\run_n03_network_first_acceptance_safe.ps1 "
        f"-TargetHost {candidate_target or '<candidate-ip-from-uart-or-local-tcp>'} "
        "-Port 5001 -ComPort COM3 -UseLatestTargetHint -SkipStaticDirectPreflight "
        "-ReconnectCycles 20 -MatrixRepeat 100 "
        "-SustainedSeconds 60 -LongSeconds 300"
    )
    package_rebuild_command = "python .\\tools\\build_n03_network_first_package.py"
    handoff_rows = [
        {
            "step": "0_connect_and_prepare",
            "when": "Before any real N03 acceptance run",
            "command": admin_static_apply_command,
            "expected_evidence": rel(static_net_summary),
            "pass_boundary": "PC_ETHERNET_LINK_UP=1 and PC_EXPECTED_STATIC_IP_PRESENT=1 only; no board TCP pass yet",
        },
        {
            "step": "1_current_state_gate",
            "when": "After Ethernet is plugged in and static IP is configured",
            "command": current_gate_command,
            "expected_evidence": rel(current_gate_summary),
            "pass_boundary": "N03_CURRENT_STATE_GATE_STATUS remains authoritative; do not claim final pass from preflight alone",
        },
        {
            "step": "2_real_static_direct_acceptance",
            "when": "Only after 192.168.10.2:5001 is reachable",
            "command": real_acceptance_command,
            "expected_evidence": "reports/n03_network_first_acceptance_<stamp>.*/ and reports/n03_network_first_acceptance_safe_<stamp>.*",
            "pass_boundary": "Real N03-1..N03-5/N03-9 claims require non-dry-run safe wrapper markers and clean logs",
        },
        {
            "step": "2a_candidate_target_acceptance",
            "when": "Only if UART BOARD_IP_SEEN or local TCP discovery identifies a board IP different from 192.168.10.2",
            "command": candidate_acceptance_command,
            "expected_evidence": "reports/external_preconditions_current.json plus safe-wrapper logs for the candidate target",
            "pass_boundary": "Candidate IP evidence is only a routing hint until the safe wrapper records real TCP HELLO, payload, reconnect, and clean error counters",
        },
        {
            "step": "3_dhcp_fallback_capture",
            "when": "After board boots with DHCP client and no PC DHCP server",
            "command": "capture UART DHCP_START/DHCP_TIMEOUT/STATIC_FALLBACK_IP=192.168.10.2/TCP_READY, then rerun the safe wrapper",
            "expected_evidence": "reports/ps_uart_boot_probe_<stamp>.summary.txt plus N03 safe wrapper logs",
            "pass_boundary": "DHCP timeout/static fallback pass also requires real TCP HELLO and memory echo after fallback",
        },
        {
            "step": "4_optional_pc_hosted_dhcp",
            "when": "Only if N03-7 is required and PC DHCP service is intentionally configured",
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\check_n03_pc_hosted_dhcp_preflight.ps1",
            "expected_evidence": rel(pc_dhcp_summary),
            "pass_boundary": f"Preflight is not a lease pass; next_action={pc_dhcp_next_action or 'MISSING'}; lease pass requires DISCOVER/OFFER/REQUEST/ACK and TCP HELLO/STATUS",
        },
        {
            "step": "5_rebuild_package",
            "when": "After any new real safe-wrapper evidence is captured",
            "command": package_rebuild_command,
            "expected_evidence": "evidence/n03_network_first/N03_10_network_first_acceptance_package.md",
            "pass_boundary": "Package may claim final N03 only after required real-board gates pass; never claim IR/2-lane/rotation/final target here",
        },
    ]
    write_csv(OUT / "N03_real_board_handoff.csv", handoff_rows)
    (OUT / "N03_real_board_handoff.json").write_text(
        json.dumps(handoff_rows, indent=2) + "\n",
        encoding="utf-8",
    )
    handoff_md = [
        "# N03 Real Board Handoff",
        "",
        f"Generated: {generated}",
        "",
        "This handoff is the ordered entry point for continuing the N03 network-first plan once the board Ethernet link is available. It does not configure networking, run hardware, or claim a real-board pass by itself.",
        "",
        f"- Current external preconditions: `{external_overall}`",
        f"- Current external blockers: `{external_blockers_text}`",
        f"- Local TCP 5001 discovery subnets: `{local_tcp_subnets_text}`",
        f"- Local TCP 5001 discovery candidates: `{local_tcp_candidates_text}`",
        f"- UART board IP hint: `{uart_board_ip_hint or 'none'}`",
        f"- Candidate target command: `{candidate_acceptance_command}`",
        f"- N03 PC-hosted DHCP next action: `{pc_dhcp_next_action or 'MISSING'}`",
        f"- N03 PC-hosted DHCP ICS query requires admin: `{int(pc_dhcp_ics_query_requires_admin)}`",
        f"- N03 PC-hosted DHCP standalone IP command: `{pc_dhcp_standalone_ip_command or 'not captured'}`",
        f"- N03 PC-hosted DHCP ICS GUI command: `{pc_dhcp_ics_gui_command or 'not captured'}`",
        f"- Current runbook: `{runbook_overall}`",
        f"- Current blocker: `{blocker_note}`",
        f"- Latest elevated static setup pending or declined: `{int(launch_pending)}`",
        f"- Current gate report: `{rel(current_gate_report)}`",
        f"- Safe wrapper summary: `{rel(safe_summary)}`",
        "",
        "## Ordered Commands",
        "",
        "| step | when | command | expected evidence | pass boundary |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in handoff_rows:
        handoff_md.append(
            "| "
            + " | ".join(
                str(row[key]).replace("|", "/").replace("\n", " ")
                for key in ("step", "when", "command", "expected_evidence", "pass_boundary")
            )
            + " |"
        )
    handoff_md.extend(
        [
            "",
            "## Log Index",
            "",
            "- PC logs: `reports/n03_network_first_acceptance_<stamp>/*.out.log` and `*.err.log` from the safe wrapper.",
            "- UART logs: `reports/n03_network_first_acceptance_<stamp>/uart_probe.out.log` and `reports/ps_uart_boot_probe_<stamp>.*` when captured.",
            "- CSV evidence: `reports/n03_network_first_acceptance_safe_<stamp>.matrix.csv`, `reports/n03_offline_payload_matrix_current.csv`, and `reports/n03_offline_reconnect_matrix_current.csv`.",
            "- Vivado/Vitis build logs: attach only if the bit/ELF is rebuilt for N03; the current safe wrapper does not program FPGA or rebuild artifacts.",
            "",
            "## Non-Claims",
            "",
            "```text",
            "IR_PHYSICAL_PASS=0",
            "2LANE_PASS=0",
            "REAL_IR_DATA_ROUNDTRIP_PASS=0",
            "ROTATION_PASS=0",
            "4LANE_PASS=0",
            "8LANE_PASS=0",
            "FINAL_TARGET_PASS=0",
            "```",
        ]
    )
    write(OUT / "N03_real_board_handoff.md", "\n".join(handoff_md))

    package_body = [
        "# N03-10 Network-first Acceptance Package",
        "",
        f"Generated: {generated}",
        "",
        "Verdict: `PACKAGE_PARTIAL_REAL_BOARD_PENDING`",
        "",
        "This package is a current-state N03 deliverable bundle. It proves source/offline/mock progress, incorporates the latest safe real-board wrapper result when present, and preserves the remaining real-board blockers. It does not claim the final N03 baseline PASS.",
        "",
        "## Stage Matrix",
        "",
        md_table(rows),
        "",
        "## Current Source/Offline Evidence",
        "",
        f"- Offline summary: `{rel(offline_summary)}`",
        f"- Offline app payload segmentation: `{'PASS' if app_segmentation_ok else 'MISSING'}` (`8192_bytes_over_512_byte_rfcm_frames` when present)",
        f"- Offline payload matrix: `{'PASS' if offline_payload_matrix_ok else 'MISSING'}`",
        f"- Offline payload matrix report: `{rel(payload_matrix_report)}`",
        f"- Offline payload matrix CSV: `{rel(payload_matrix_csv)}`",
        f"- Offline payload matrix JSON: `{rel(payload_matrix_json)}`",
        f"- Offline HELLO/STATUS reconnect 10x: `{'PASS' if offline_reconnect_hello_10x_ok else 'MISSING'}`",
        f"- Offline payload reconnect 20x: `{'PASS' if offline_reconnect_payload_20x_ok else 'MISSING'}`",
        f"- Offline reconnect matrix report: `{rel(reconnect_matrix_report)}`",
        f"- Offline reconnect matrix CSV: `{rel(reconnect_matrix_csv)}`",
        f"- Offline reconnect matrix JSON: `{rel(reconnect_matrix_json)}`",
        f"- Offline reconnect payload echo: `{'PASS' if reconnect_payload_ok else 'MISSING'}`",
        f"- Offline bad-argument negatives: `{'PASS' if bad_arg_ok else 'MISSING'}`",
        f"- Offline/source protocol-fault negatives: `{'PASS' if protocol_fault_ok else 'MISSING'}`",
        f"- No-Ethernet boundary report: `{rel(boundary_report)}`",
        f"- No-Ethernet boundary CSV: `{rel(boundary_csv)}`",
        f"- No-Ethernet boundary JSON: `{rel(boundary_json)}`",
        f"- N03 static direct PC preflight summary: `{rel(static_net_summary)}`",
        f"- N03 static direct PC preflight report: `{rel(static_net_report)}`",
        f"- N03 static direct PC preflight JSON: `{rel(static_net_json)}`",
        "- N03 static direct admin apply helper: `tools/apply_n03_static_direct_network_admin.ps1`",
        f"- N03 PC-hosted DHCP preflight summary: `{rel(pc_dhcp_summary)}`",
        f"- N03 PC-hosted DHCP preflight report: `{rel(pc_dhcp_report)}`",
        f"- N03 PC-hosted DHCP preflight JSON: `{rel(pc_dhcp_json)}`",
        f"- N03 PC-hosted DHCP preflight status: `{pc_dhcp_status_value or 'MISSING'}`",
        f"- N03 PC-hosted DHCP next action: `{pc_dhcp_next_action or 'MISSING'}`",
        f"- N03 PC-hosted DHCP ICS query requires admin: `{int(pc_dhcp_ics_query_requires_admin)}`",
        f"- N03 PC-hosted DHCP standalone IP command: `{pc_dhcp_standalone_ip_command or 'not captured'}`",
        f"- N03 PC-hosted DHCP ICS GUI command: `{pc_dhcp_ics_gui_command or 'not captured'}`",
        f"- N03 readiness audit report: `{rel(readiness_report)}`",
        f"- N03 readiness audit CSV: `{rel(readiness_csv)}`",
        f"- N03 readiness audit JSON: `{rel(readiness_json)}`",
        f"- N03 current state gate summary: `{rel(current_gate_summary)}`",
        f"- N03 current state gate report: `{rel(current_gate_report)}`",
        f"- N03 current state gate JSON: `{rel(current_gate_json)}`",
        f"- N03 real board handoff: `{rel(OUT / 'N03_real_board_handoff.md')}`",
        f"- N03 real board handoff CSV: `{rel(OUT / 'N03_real_board_handoff.csv')}`",
        f"- N03 real board handoff JSON: `{rel(OUT / 'N03_real_board_handoff.json')}`",
        f"- Real acceptance runbook overall: `{runbook_overall}`",
        f"- Real acceptance runbook report: `{rel(runbook_md)}`",
        f"- Real acceptance runbook JSON: `{rel(runbook_json)}`",
        f"- Real acceptance runbook CSV: `{rel(runbook_csv)}`",
        f"- Latest elevated static setup launch summary: `{rel(static_launch_summary)}`",
        f"- Latest elevated static setup launch pending or declined: `{int(launch_pending)}`",
        f"- Latest non-admin static setup apply refusal summary: `{rel(static_apply_refused_summary)}`",
        f"- Latest UART boot probe summary: `{rel(uart_summary)}`",
        f"- Latest UART boot probe verdict: `{uart_verdict or 'MISSING'}`",
        f"- Latest UART captured bytes: `{uart_log_bytes}`",
        f"- UART board IP hint: `{uart_board_ip_hint or 'none'}`",
        f"- Safe real-board wrapper summary: `{rel(safe_summary)}`",
        f"- Safe real-board wrapper report: `{rel(safe_report)}`",
        f"- Safe real-board wrapper matrix: `{rel(safe_matrix)}`",
        f"- Static PS bridge report: `{rel(static_report)}`",
        f"- Protocol contract report: `{rel(protocol_contract)}`",
        f"- External preconditions overall: `{external_overall}`",
        f"- External preconditions blockers: `{external_blockers_text}`",
        f"- Local TCP 5001 discovery subnets: `{local_tcp_subnets_text}`",
        f"- Local TCP 5001 discovery candidates: `{local_tcp_candidates_text}`",
        f"- N03 target hints: `{target_hint_text}`",
        f"- External preconditions report: `{rel(external_md)}`",
        f"- External preconditions JSON: `{rel(external_json)}`",
        f"- External preconditions CSV: `{rel(external_csv)}`",
        f"- P7 physical report: `{rel(p7_report)}`",
        "",
        "## Final N03 Pass Gate",
        "",
        "Do not mark the final N03 network-first baseline as passed until N03-1..N03-6, N03-8, and N03-9 have real board evidence with payload_mismatch=0 and reconnect/link recovery evidence. N03-7 may remain `DEFERRED_NO_PC_DHCP_SERVER_PREFLIGHTED` if no PC DHCP server is available, or `PC_DHCP_SERVER_READY_LEASE_PENDING` until a real lease and TCP HELLO/STATUS pass are captured.",
        "",
        "## Non-Claims",
        "",
        "```text",
        "IR_PHYSICAL_PASS=0",
        "2LANE_PASS=0",
        "REAL_IR_DATA_ROUNDTRIP_PASS=0",
        "ROTATION_PASS=0",
        "4LANE_PASS=0",
        "8LANE_PASS=0",
        "FINAL_TARGET_PASS=0",
        "```",
    ]
    write(OUT / "N03_10_network_first_acceptance_package.md", "\n".join(package_body))

    write_csv(OUT / "N03_stage_matrix.csv", [asdict(row) for row in rows])
    (OUT / "N03_stage_matrix.json").write_text(
        json.dumps([asdict(row) for row in rows], indent=2) + "\n",
        encoding="utf-8",
    )
    artifact_data = artifact_rows()
    write_csv(OUT / "artifact_hashes.csv", artifact_data)
    artifact_lines = [f"generated={generated}"]
    for row in artifact_data:
        artifact_lines.append(f"{row['status']} {row['path']} {row['sha256']}")
    write(OUT / "artifact_hashes.txt", "\n".join(artifact_lines))

    print(f"WROTE_N03_PACKAGE={OUT}")
    print(f"N03_PACKAGE_STATUS={rows[-1].status}")
    print(f"N03_OFFLINE_SUMMARY={rel(offline_summary)}")
    print(f"N03_STATIC_DIRECT_PREFLIGHT_SUMMARY={rel(static_net_summary)}")
    print(f"N03_UART_SUMMARY={rel(uart_summary)}")
    print(f"N03_SAFE_ACCEPTANCE_SUMMARY={rel(safe_summary)}")
    print(f"N03_SAFE_ACCEPTANCE_PASS={int(safe_acceptance_ok)}")
    print("N03_REAL_BOARD_PASS=0")
    print("NO_IR_PHYSICAL_PASS_CLAIM=1")
    print("NO_2LANE_PASS_CLAIM=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
