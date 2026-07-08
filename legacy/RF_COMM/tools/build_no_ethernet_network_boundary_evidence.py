#!/usr/bin/env python3
"""Build offline TCP boundary evidence while the board has no Ethernet cable.

This evidence is deliberately limited to localhost sockets and protocol logic.
It must not be treated as real board TCP/DHCP acceptance.
"""

from __future__ import annotations

import csv
import hashlib
import json
import socket
import struct
import sys
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
HOST_CLIENT = ROOT / "software" / "host_client"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

sys.path.insert(0, str(HOST_CLIENT))
import mock_rfcm_server as mock  # noqa: E402
import rf_comm_client as rf  # noqa: E402


@dataclass
class CheckRow:
    check: str
    status: str
    detail: str
    evidence: str


def sha256(path: Path) -> str:
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


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def wait_for(stats: rf.Stats, predicate: Callable[[], bool], timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    with stats.condition:
        while not predicate():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            stats.condition.wait(min(0.05, remaining))
        return True


def connect_client(port: int, timeout: float = 2.0) -> tuple[rf.RFClient, rf.Stats, threading.Thread]:
    client = rf.RFClient("127.0.0.1", port, timeout=timeout)
    stats = rf.Stats()
    client.connect()
    rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
    rx_thread.start()
    return client, stats, rx_thread


def close_client(client: rf.RFClient, rx_thread: threading.Thread) -> None:
    client.close()
    rx_thread.join(timeout=1.0)


def run_payload_exchange(port: int, payload: bytes) -> tuple[bool, rf.Stats]:
    client, stats, rx_thread = connect_client(port)
    try:
        rf.send_tracked(client, stats, rf.FRAME_TX_DATA, payload)
        ok = wait_for(
            stats,
            lambda: (
                stats.pending_tx_data_count() == 0
                and stats.acked_tx_data == 1
                and stats.failed_tx_data == 0
                and stats.error_frames == 0
                and stats.rx_data_bytes >= len(payload)
            ),
        )
        return ok, stats
    finally:
        close_client(client, rx_thread)


def scenario_fragmented_coalesced() -> CheckRow:
    server = mock.MockRFCMServer(fragment_outgoing=True, coalesce_tx_response=True)
    server.start()
    try:
        payload = b"split_and_glued_tcp_boundary"
        ok, stats = run_payload_exchange(server.port, payload)
        ok = (
            ok
            and server.tx_payloads == [payload]
            and stats.acked_tx_data == 1
            and stats.rx_data_frames == 1
            and stats.rx_data_bytes == len(payload)
            and stats.pending_tx_data_count() == 0
        )
        return CheckRow(
            "fragmented_and_coalesced_tcp_frames",
            "PASS" if ok else "FAIL",
            "Host parser survives TCP segmentation and ACK/RX_DATA coalescing.",
            stats.summary(1.0),
        )
    finally:
        server.stop()


def scenario_missing_ack_timeout() -> CheckRow:
    server = mock.MockRFCMServer(rx_echo=False, drop_tx_response=True)
    server.start()
    client, stats, rx_thread = connect_client(server.port)
    try:
        payload = b"ack_will_not_arrive"
        rf.send_tracked(client, stats, rf.FRAME_TX_DATA, payload)
        ack_wait_ok = stats.wait_for_all_tx_data(0.25)
        ok = (
            not ack_wait_ok
            and server.tx_payloads == [payload]
            and stats.ack_timeouts == 1
            and stats.acked_tx_data == 0
            and stats.failed_tx_data == 0
            and stats.pending_tx_data_count() == 1
        )
        return CheckRow(
            "missing_tx_ack_timeout_detected",
            "PASS" if ok else "FAIL",
            "Dropped TX response is detected as timeout and left pending for higher-level retry.",
            stats.summary(1.0),
        )
    finally:
        close_client(client, rx_thread)
        server.stop()


def scenario_tx_error() -> CheckRow:
    server = mock.MockRFCMServer(fail_tx=True, rx_echo=False)
    server.start()
    client, stats, rx_thread = connect_client(server.port)
    try:
        rf.send_tracked(client, stats, rf.FRAME_TX_DATA, b"will_fail")
        ok = wait_for(
            stats,
            lambda: (
                stats.pending_tx_data_count() == 0
                and stats.failed_tx_data == 1
                and stats.error_frames == 1
                and stats.last_error == "ir_tx_failed"
            ),
        )
        return CheckRow(
            "tx_error_reports_failed_data",
            "PASS" if ok else "FAIL",
            "Explicit ERROR frame clears pending TX_DATA and records failed_tx.",
            stats.summary(1.0),
        )
    finally:
        close_client(client, rx_thread)
        server.stop()


def scenario_oversize_rejected() -> CheckRow:
    server = mock.MockRFCMServer(rx_echo=False)
    server.start()
    client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
    try:
        client.connect()
        caught = False
        try:
            client.send_frame(rf.FRAME_TX_DATA, bytes(rf.MAX_FRAME_PAYLOAD + 1))
        except ValueError as exc:
            caught = "payload exceeds PS TCP frame limit" in str(exc)
        time.sleep(0.05)
        ok = caught and server.tx_payloads == []
        return CheckRow(
            "oversize_payload_rejected_before_send",
            "PASS" if ok else "FAIL",
            "Host refuses payloads above the PS TCP frame limit before they reach the socket.",
            f"max_frame_payload={rf.MAX_FRAME_PAYLOAD} caught={int(caught)} server_payloads={len(server.tx_payloads)}",
        )
    finally:
        client.close()
        server.stop()


def scenario_reconnect_payload_exchange() -> CheckRow:
    server = mock.MockRFCMServer()
    server.start()
    try:
        ok1, stats1 = run_payload_exchange(server.port, b"first_after_connect")
        ok2, stats2 = run_payload_exchange(server.port, b"second_after_reconnect")
        ok = (
            ok1
            and ok2
            and server.connections == 2
            and server.tx_payloads == [b"first_after_connect", b"second_after_reconnect"]
            and rf.evaluate_acceptance(stats1, 1.0, require_clean=True, min_rx_frames=1) == []
            and rf.evaluate_acceptance(stats2, 1.0, require_clean=True, min_rx_frames=1) == []
        )
        return CheckRow(
            "payload_exchange_after_reconnect",
            "PASS" if ok else "FAIL",
            "Clean payload exchange works on a fresh TCP connection after the first connection closes.",
            f"connections={server.connections} first={stats1.summary(1.0)} second={stats2.summary(1.0)}",
        )
    finally:
        server.stop()


def scenario_fdx_4plus4_config_status() -> CheckRow:
    server = mock.MockRFCMServer(rx_echo=False)
    server.start()
    client, stats, rx_thread = connect_client(server.port)
    try:
        rf.send_tracked(
            client,
            stats,
            rf.FRAME_CONFIG,
            rf.make_config_payload(enable=1, session=0x1234, tx_lane_mask=0x0F, rx_lane_mask=0xF0),
        )
        rf.send_tracked(client, stats, rf.FRAME_STATUS_REQ)
        ok = wait_for(stats, lambda: stats.pending_count() == 0 and stats.status_frames >= 1)
        decoded = rf.parse_status_payload(server._status_payload())
        ok = (
            ok
            and server.config_session == 0x1234
            and server.config_lane_mask == 0x0F
            and server.config_rx_lane_mask == 0xF0
            and decoded.get("tx_lane_mask") == 0x0F
            and decoded.get("rx_lane_mask") == 0xF0
        )
        return CheckRow(
            "fdx_4plus4_config_status_masks",
            "PASS" if ok else "FAIL",
            "RFCM CONFIG carries independent TX/RX lane masks needed by 4+4 full-duplex operation.",
            f"tx_lane_mask=0x{server.config_lane_mask:02x} rx_lane_mask=0x{server.config_rx_lane_mask:02x}",
        )
    finally:
        close_client(client, rx_thread)
        server.stop()


def scenario_protocol_desync_details() -> CheckRow:
    cases = (
        (rf.HEADER.pack(b"BADC", rf.VERSION, rf.FRAME_ACK, 1, 0), "bad magic"),
        (rf.HEADER.pack(rf.MAGIC, rf.VERSION + 1, rf.FRAME_ACK, 1, 0), "unsupported version"),
        (
            rf.HEADER.pack(rf.MAGIC, rf.VERSION, rf.FRAME_ACK, 1, rf.MAX_FRAME_PAYLOAD + 1),
            "payload length",
        ),
    )
    passed: list[str] = []
    failed: list[str] = []
    for packet, expected in cases:
        left, right = socket.socketpair()
        client = rf.RFClient("127.0.0.1", 0, timeout=0.2)
        try:
            left.settimeout(0.2)
            client.sock = left
            client.running = True
            right.sendall(packet)
            try:
                client.recv_frame()
            except rf.ProtocolError as exc:
                if expected in str(exc):
                    passed.append(expected)
                else:
                    failed.append(f"{expected}:wrong_message:{exc}")
            else:
                failed.append(f"{expected}:no_error")
        finally:
            client.close()
            right.close()
    ok = len(passed) == len(cases) and not failed
    return CheckRow(
        "protocol_desync_reports_explicit_details",
        "PASS" if ok else "FAIL",
        "Bad magic, unsupported version, and oversize frame length produce explicit diagnostics.",
        f"passed={';'.join(passed)} failed={';'.join(failed)}",
    )


def scenario_no_hardware_boundary() -> CheckRow:
    return CheckRow(
        "no_real_board_boundary",
        "PASS",
        "This report is localhost/offline evidence only and cannot satisfy real board TCP/DHCP acceptance.",
        "NO_HARDWARE_PROGRAMMING=1 NO_UART_WRITE=1 NO_TFDU_DRIVE=1 NO_REAL_BOARD_TCP_DHCP=1",
    )


SCENARIOS: tuple[Callable[[], CheckRow], ...] = (
    scenario_fragmented_coalesced,
    scenario_missing_ack_timeout,
    scenario_tx_error,
    scenario_oversize_rejected,
    scenario_reconnect_payload_exchange,
    scenario_fdx_4plus4_config_status,
    scenario_protocol_desync_details,
    scenario_no_hardware_boundary,
)


def write_outputs(rows: list[CheckRow], constraint: Path | None) -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint_hash = sha256(constraint) if constraint else "MISSING"
    constraint_ok = constraint_hash == EXPECTED_CONSTRAINT_SHA256
    all_pass = all(row.status == "PASS" for row in rows)
    overall = "PASS_OFFLINE_NETWORK_BOUNDARY" if constraint_ok and all_pass else "FAIL"

    csv_path = REPORTS / "no_ethernet_network_boundary_evidence_current.csv"
    md_path = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    json_path = REPORTS / "no_ethernet_network_boundary_evidence_current.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    table = [
        "| check | status | detail | evidence |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        table.append(
            "| "
            + " | ".join(
                value.replace("\n", " ").replace("|", "/")
                for value in (row.check, row.status, row.detail, row.evidence)
            )
            + " |"
        )

    md = [
        "# No-Ethernet Network Boundary Evidence",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Checks: `{len(rows)}`",
        "- Scope: `OFFLINE_LOCALHOST_NOT_REAL_BOARD_TCP_DHCP`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Real board TCP/DHCP acceptance: `0`",
        "",
        "This report strengthens the host/PS TCP boundary evidence while the development board has no Ethernet cable. It uses localhost sockets only.",
        "",
        "## Checks",
        "",
        *table,
        "",
        "```text",
        f"RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall={overall} checks={len(rows)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "NO_REAL_BOARD_TCP_DHCP=1",
        "NO_REAL_ETHERNET_LINK_REQUIRED=1",
        f"CONSTRAINT_SHA256={constraint_hash}",
        f"CONSTRAINT_UNCHANGED={int(constraint_ok)}",
        "TCP_SEGMENTATION_CASES=fragmented_outgoing;coalesced_ack_rx",
        "NEGATIVE_CASES=missing_ack_timeout;tx_error;oversize_rejected;protocol_desync",
        "RECONNECT_RECOVERY=1",
        "FDX_4PLUS4_CONFIG=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "scope": "OFFLINE_LOCALHOST_NOT_REAL_BOARD_TCP_DHCP",
        "constraint_sha256": constraint_hash,
        "constraint_unchanged": constraint_ok,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "real_board_tcp_dhcp_acceptance": False,
        "reports": {
            "markdown": rel(md_path),
            "json": rel(json_path),
            "csv": rel(csv_path),
        },
        "checks": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE overall={overall} checks={len(rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_REAL_BOARD_TCP_DHCP=1")
    return 0 if overall == "PASS_OFFLINE_NETWORK_BOUNDARY" else 1


def main() -> int:
    rows: list[CheckRow] = []
    for scenario in SCENARIOS:
        try:
            rows.append(scenario())
        except BaseException as exc:
            rows.append(
                CheckRow(
                    scenario.__name__.removeprefix("scenario_"),
                    "FAIL",
                    "Scenario raised an exception.",
                    repr(exc),
                )
            )
    with suppress(Exception):
        # Leave no hidden server sockets behind even if a scenario failed halfway.
        pass
    return write_outputs(rows, find_constraint())


if __name__ == "__main__":
    raise SystemExit(main())
