#!/usr/bin/env python3
"""Offline source checks for the Zynq PS lwIP bridge.

These checks are intentionally source-level because the current accepted scope
does not require board access. They guard the PS/PC networking requirements so
TCP/DHCP support cannot silently disappear from the bring-up bridge.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[1]
SRC = ROOT / "src"
HOST = ROOT.parent / "host_client"
REPORTS = PROJECT_ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


class CheckFailed(Exception):
    pass


def read(path: Path) -> str:
    if not path.exists():
        raise CheckFailed(f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_constraint() -> Path | None:
    for path in PROJECT_ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def macro(text: str, name: str) -> str:
    match = re.search(rf"^\s*#define\s+{re.escape(name)}\s+(.+?)\s*$", text, re.MULTILINE)
    if match is None:
        raise CheckFailed(f"missing macro {name}")
    return re.sub(r"/\*.*?\*/", "", match.group(1)).strip()


def macro_int(text: str, name: str) -> int:
    value = macro(text, name)
    value = re.sub(r"([0-9])(?:[uUlL]+)", r"\1", value)
    value = value.strip()
    if re.fullmatch(r"'(.)'", value):
        return ord(value[1])
    if not re.fullmatch(r"[0-9xXa-fA-F\s<>()|+.-]+", value):
        raise CheckFailed(f"unsupported macro value for {name}: {value}")
    return int(eval(value, {"__builtins__": {}}, {}))


def py_const_int(text: str, name: str) -> int:
    match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(.+?)\s*$", text, re.MULTILINE)
    if match is None:
        raise CheckFailed(f"missing Python constant {name}")
    value = match.group(1).strip()
    if not re.fullmatch(r"[0-9xXa-fA-F\s<>()|+.-]+", value):
        raise CheckFailed(f"unsupported Python constant value for {name}: {value}")
    return int(eval(value, {"__builtins__": {}}, {}))


def require(checks: list[str], name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        raise CheckFailed(f"{name}{': ' + detail if detail else ''}")
    checks.append(name)


def require_re(checks: list[str], name: str, text: str, pattern: str) -> None:
    require(checks, name, re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None, pattern)


def check_group(name: str) -> str:
    if name.startswith("dhcp_") or name.startswith("static_") or name in {
        "no_dhcp_static_fallback",
        "network_poll_loop",
    }:
        return "dhcp_static_network"
    if name.startswith("tcp_") or name.startswith("accept_") or name.startswith("client_"):
        return "tcp_connection"
    if name.startswith("parser_") or name.startswith("recv_") or name.startswith("oversize_"):
        return "tcp_parser_robustness"
    if name.startswith("handles_") or name.startswith("status_") or name.startswith("config_") or name.startswith("tx_data_") or name.startswith("poll_"):
        return "rfcm_bridge_behavior"
    if name.startswith("protocol_") or name.startswith("frame_") or name.startswith("python_"):
        return "pc_ps_protocol_contract"
    return "core"


def write_reports(checks: list[str], failures: list[str]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    constraint_path = find_constraint()
    constraint_hash = sha256(constraint_path) if constraint_path else ""
    pass_count = len(checks)
    fail_count = len(failures)
    overall = "PASS" if fail_count == 0 and pass_count > 0 else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")

    rows = [
        {
            "check": name,
            "group": check_group(name),
            "status": "PASS",
            "detail": "source pattern/value present",
        }
        for name in checks
    ]
    rows.extend(
        {
            "check": f"failure_{idx}",
            "group": "failure",
            "status": "FAIL",
            "detail": failure,
        }
        for idx, failure in enumerate(failures, start=1)
    )

    md_path = REPORTS / "ps_lwip_bridge_static_current.md"
    json_path = REPORTS / "ps_lwip_bridge_static_current.json"
    csv_path = REPORTS / "ps_lwip_bridge_static_current.csv"

    md_lines = [
        "# PS lwIP Bridge Static Evidence",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Checks passed: `{pass_count}`",
        f"- Failures: `{fail_count}`",
        "- Scope: `OFFLINE_SOURCE_ONLY_NOT_REAL_BOARD_TCP_DHCP`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Real board TCP/DHCP acceptance: `0`",
        "",
        "This report checks that the PS lwIP bridge source still contains DHCP startup, static-IP fallback, TCP listen/accept/reconnect handling, RFCM frame parsing, IR status/error forwarding, and PC protocol compatibility. It is source evidence only and does not replace real board Ethernet/DHCP acceptance.",
        "",
        "## Checks",
        "",
        "| check | group | status | detail |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        detail = row["detail"].replace("|", "/")
        md_lines.append(f"| {row['check']} | {row['group']} | {row['status']} | {detail} |")
    md_lines.extend(
        [
            "",
            "```text",
            f"RF_COMM_PS_LWIP_BRIDGE_STATIC overall={overall} checks={pass_count} failures={fail_count}",
            "DHCP_SOURCE_READY=1" if overall == "PASS" else "DHCP_SOURCE_READY=0",
            "STATIC_FALLBACK_SOURCE_READY=1" if overall == "PASS" else "STATIC_FALLBACK_SOURCE_READY=0",
            "TCP_BRIDGE_SOURCE_READY=1" if overall == "PASS" else "TCP_BRIDGE_SOURCE_READY=0",
            "RFCM_PROTOCOL_SOURCE_READY=1" if overall == "PASS" else "RFCM_PROTOCOL_SOURCE_READY=0",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "NO_REAL_BOARD_TCP_DHCP=1",
            f"CONSTRAINT_SHA256={constraint_hash}",
            f"CONSTRAINT_UNCHANGED={int(constraint_hash == EXPECTED_CONSTRAINT_SHA256)}",
            "```",
        ]
    )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "scope": "OFFLINE_SOURCE_ONLY_NOT_REAL_BOARD_TCP_DHCP",
        "checks_passed": pass_count,
        "failures": fail_count,
        "constraint": {
            "path": rel(constraint_path),
            "sha256": constraint_hash,
            "unchanged": constraint_hash == EXPECTED_CONSTRAINT_SHA256,
        },
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "no_real_board_tcp_dhcp": True,
        "rows": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["check", "group", "status", "detail"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")


def main() -> int:
    checks: list[str] = []
    failures: list[str] = []

    try:
        main_c = read(SRC / "main.c")
        bridge_c = read(SRC / "tcp_bridge.c")
        rf_h = read(SRC / "rf_protocol.h")
        host_py = read(HOST / "rf_comm_client.py")
        main_flat = normalize(main_c)
        bridge_flat = normalize(bridge_c)

        require(checks, "tcp_port_5001", macro_int(main_c, "RF_TCP_PORT") == 5001)
        require(checks, "dhcp_wait_positive", macro_int(main_c, "DHCP_WAIT_ITERATIONS") > 0)
        require_re(checks, "dhcp_header_included", main_c, r'#include\s+"lwip/dhcp\.h"')
        require_re(checks, "dhcp_compile_guard", main_c, r"#if\s+LWIP_DHCP")
        require_re(checks, "dhcp_start", main_c, r"dhcp_start\s*\(\s*&server_netif\s*\)")
        require_re(checks, "dhcp_timeout_counter", main_c, r"dhcp_timoutcntr\s*=\s*DHCP_WAIT_ITERATIONS")
        require_re(
            checks,
            "dhcp_poll_wait_loop",
            main_flat,
            r"while \(\(server_netif\.ip_addr\.addr == 0u\) && \(dhcp_timoutcntr > 0\)\) \{ xemacif_input\(&server_netif\); \}",
        )
        require_re(checks, "dhcp_timeout_static_fallback", main_flat, r"if \(server_netif\.ip_addr\.addr == 0u\) \{ .* set_static_fallback\(&server_netif\); \}")
        require_re(checks, "no_dhcp_static_fallback", main_c, r"#else\s+set_static_fallback\s*\(\s*&server_netif\s*\)")
        require_re(checks, "static_ip_address", main_flat, r"IP4_ADDR\(&\(netif->ip_addr\), 192, 168, 10, 2\)")
        require_re(checks, "static_netmask", main_flat, r"IP4_ADDR\(&\(netif->netmask\), 255, 255, 255, 0\)")
        require_re(checks, "static_gateway", main_flat, r"IP4_ADDR\(&\(netif->gw\), 192, 168, 10, 1\)")
        require_re(checks, "network_poll_loop", main_flat, r"while \(1\) \{ .* tcp_fasttmr\(\); .* tcp_slowtmr\(\); .* xemacif_input\(&server_netif\); tcp_bridge_poll\(\); \}")

        require_re(checks, "tcp_new_bind_listen", bridge_flat, r"tcp_new\(\).*tcp_bind\(pcb, IP_ADDR_ANY, port\).*tcp_listen\(pcb\).*tcp_accept\(g_bridge\.listen_pcb, bridge_accept\)")
        require_re(checks, "accept_single_client_guard", bridge_flat, r"if \(g_bridge\.client_pcb != NULL\) \{ return bridge_close_pcb\(new_pcb\); \}")
        require_re(checks, "accept_callbacks", bridge_flat, r"tcp_arg\(new_pcb, &g_bridge\); tcp_recv\(new_pcb, bridge_recv\); tcp_err\(new_pcb, bridge_err\); tcp_nagle_disable\(new_pcb\);")
        require_re(checks, "connected_banner", bridge_flat, r'bridge_send_text\(RF_FRAME_ACK, 0u, "connected"\)')
        require_re(checks, "client_close_clears_callbacks", bridge_flat, r"tcp_arg\(pcb, NULL\); tcp_recv\(pcb, NULL\); tcp_err\(pcb, NULL\);")
        require_re(checks, "client_close_aborts_on_close_error", bridge_flat, r"close_err = tcp_close\(pcb\); if \(close_err != ERR_OK\) \{ tcp_abort\(pcb\); return ERR_ABRT; \}")
        require_re(checks, "client_close_clears_rx_buffer", bridge_flat, r"g_bridge\.client_pcb = NULL; g_bridge\.rx_len = 0u; return bridge_close_pcb\(pcb\);")
        require_re(checks, "tcp_error_callback_clears_state", bridge_flat, r"static void bridge_err.*g_bridge\.client_pcb = NULL; g_bridge\.rx_len = 0u;")
        require_re(checks, "recv_error_or_close_closes_client", bridge_flat, r"if \(err != ERR_OK \|\| p == NULL\) \{ .* return bridge_close_client\(\); \}")
        require_re(checks, "recv_acknowledges_tcp_bytes", bridge_c, r"tcp_recved\s*\(\s*pcb\s*,\s*p->tot_len\s*\)")
        require_re(checks, "recv_handles_pbuf_chain", bridge_flat, r"for \(q = p; q != NULL; q = q->next\)")
        require_re(checks, "recv_overflow_reports_error", bridge_flat, r'bridge_send_text\(RF_FRAME_ERROR, 0u, "tcp_rx_overflow"\)')
        require_re(checks, "parser_reports_bad_magic", bridge_flat, r'bridge_send_text\(RF_FRAME_ERROR, 0u, "bad_magic"\)')
        require_re(checks, "parser_reports_bad_magic_once_per_parse", bridge_flat, r"desync_reported == 0.*bad_magic.*desync_reported = 1")
        require_re(checks, "parser_resyncs_on_bad_magic", bridge_flat, r"pos\+\+; continue;")
        require_re(checks, "parser_reports_unsupported_version", bridge_flat, r'bridge_send_text\(RF_FRAME_ERROR, seq, "unsupported_version"\)')
        require_re(checks, "parser_clears_rx_on_unsupported_version", bridge_flat, r"unsupported_version.*g_bridge\.rx_len = 0u; return;")
        require_re(checks, "parser_waits_for_partial_frame", bridge_flat, r"if \(g_bridge\.rx_len - pos < RF_PROTO_HEADER_BYTES \+ length\) \{ break; \}")
        require_re(checks, "parser_memmove_keeps_tail", bridge_flat, r"memmove\(g_bridge\.rx_buf, &g_bridge\.rx_buf\[pos\], g_bridge\.rx_len - pos\)")
        require_re(checks, "oversize_payload_error", bridge_flat, r'bridge_send_text\(RF_FRAME_ERROR, seq, "payload_too_large"\)')
        require_re(checks, "send_uses_copy_and_output", bridge_flat, r"tcp_write\(.*TCP_WRITE_FLAG_COPY\).*tcp_output\(g_bridge\.client_pcb\)")
        require_re(checks, "send_checks_tcp_sndbuf", bridge_c, r"tcp_sndbuf\s*\(\s*g_bridge\.client_pcb\s*\)\s*<\s*\(RF_PROTO_HEADER_BYTES \+ length\)")

        for name in ("HELLO", "STATUS_REQ", "CLEAR", "CONFIG", "COMMAND", "TX_DATA"):
            require_re(checks, f"handles_{name.lower()}", bridge_c, rf"case\s+RF_FRAME_{name}\s*:")
        require_re(checks, "status_response_64_bytes", bridge_flat, r"uint8_t payload\[64\].*bridge_send_frame\(RF_FRAME_STATUS_RSP, seq, payload, sizeof\(payload\)\)")
        require_re(checks, "command_ping_pong", bridge_flat, r'PING.*PONG')
        require_re(checks, "command_get_version", bridge_flat, r'GET_VERSION.*VERSION 1')
        require_re(checks, "command_read_status", bridge_flat, r'READ counters.*bridge_send_status')
        require_re(checks, "command_payload_bytes", bridge_flat, r'CONFIG payload_bytes .*payload_bytes_accepted')
        require_re(checks, "command_ir_start_deferred", bridge_flat, r'START ir_tx.*ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE')
        require_re(checks, "command_unknown_error", bridge_flat, r'ERR_UNKNOWN_CMD')
        require_re(checks, "config_rejects_bad_payload", bridge_flat, r'length != 8u && length != 12u && length != 16u.*bad_config_payload')
        require_re(checks, "config_requires_rx_mask_extension", bridge_flat, r"RF_CONFIG_RX_LANE_MASK.*length < 12u.*bad_config_payload")
        require_re(checks, "config_requires_mode_extension", bridge_flat, r"RF_CONFIG_MODE.*length < 16u.*bad_config_payload")
        require_re(checks, "ir_physical_deferred", bridge_flat, r'RF_MODE_IR_PHYSICAL.*ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE')
        require_re(checks, "default_network_memory_echo", bridge_flat, r"g_bridge\.mode = RF_MODE_NETWORK_MEMORY_ECHO")
        require_re(checks, "tx_data_memory_echo", bridge_flat, r"RF_MODE_NETWORK_MEMORY_ECHO.*memory_echo_done.*bridge_send_frame\(RF_FRAME_RX_DATA")
        require_re(checks, "tx_data_pspl_synth", bridge_flat, r"RF_MODE_PSPL_SYNTH_LOOPBACK.*ir_hw_inject_rx_synthetic")
        require_re(checks, "poll_forwards_synth_rx_data", bridge_flat, r"g_bridge\.mode != RF_MODE_PSPL_SYNTH_LOOPBACK.*return;.*ir_hw_poll_payload\(.*bridge_send_frame\(RF_FRAME_RX_DATA")
        require_re(checks, "poll_forwards_synth_error", bridge_flat, r"status == XST_FAILURE.*bridge_send_text\(RF_FRAME_ERROR")

        require(checks, "protocol_magic_matches", bytes(macro_int(rf_h, f"RF_PROTO_MAGIC{i}") for i in range(4)) == b"RFCM")
        require(checks, "python_magic_matches", re.search(r'^MAGIC\s*=\s*b"RFCM"\s*$', host_py, re.MULTILINE) is not None)
        for c_name, py_name in (
            ("RF_PROTO_VERSION", "VERSION"),
            ("RF_PROTO_HEADER_BYTES", "HEADER.size"),
            ("RF_PROTO_MAX_PAYLOAD", "MAX_PAYLOAD"),
        ):
            if py_name == "HEADER.size":
                require(checks, "protocol_header_size_12", macro_int(rf_h, c_name) == 12)
            elif py_name == "MAX_PAYLOAD":
                require(checks, "protocol_max_payload_512", macro_int(rf_h, c_name) == 512)
            else:
                require(checks, "protocol_version_1", macro_int(rf_h, c_name) == py_const_int(host_py, py_name))

        for frame in (
            "HELLO",
            "STATUS_REQ",
            "STATUS_RSP",
            "ACK",
            "ERROR",
            "TX_DATA",
            "RX_DATA",
            "CLEAR",
            "CONFIG",
            "COMMAND",
        ):
            require(
                checks,
                f"frame_{frame.lower()}_matches_pc",
                macro_int(rf_h, f"RF_FRAME_{frame}") == py_const_int(host_py, f"FRAME_{frame}"),
            )

        for config in ("ENABLE", "SESSION", "LANE_MASK", "RX_LANE_MASK", "MODE"):
            require(
                checks,
                f"config_{config.lower()}_matches_pc",
                macro_int(rf_h, f"RF_CONFIG_{config}") == py_const_int(host_py, f"CONFIG_{config}"),
            )
        for mode in ("NETWORK_MEMORY_ECHO", "PSPL_SYNTH_LOOPBACK", "IR_PHYSICAL"):
            require(
                checks,
                f"mode_{mode.lower()}_matches_pc",
                macro_int(rf_h, f"RF_MODE_{mode}") == py_const_int(host_py, f"MODE_{mode}"),
            )
    except CheckFailed as exc:
        failures.append(str(exc))

    if failures:
        write_reports(checks, failures)
        for failure in failures:
            print(f"PS_BRIDGE_STATIC_CHECK_FAIL {failure}")
        print("PS_BRIDGE_STATIC_CHECKS_FAIL")
        return 1

    write_reports(checks, failures)
    print(
        "PS_BRIDGE_STATIC_CHECKS_PASS "
        f"checks={len(checks)} dhcp=1 tcp=1 protocol=1 reconnect=1"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
