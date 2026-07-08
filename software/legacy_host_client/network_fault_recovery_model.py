#!/usr/bin/env python3
"""Offline PS/PC network fault recovery model for RF_COMM.

This model exercises the host-facing RFCM protocol through localhost sockets.
It does not use a real board, real Ethernet, UART, FPGA programming, or TFDU
traffic. The goal is to keep the TCP/DHCP/reconnect target behavior testable
while the development board has no Ethernet cable.
"""

from __future__ import annotations

import argparse
import csv
import json
import socket
import struct
import sys
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mock_rfcm_server as mock
import rf_comm_client as rf


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"


@dataclass
class ScenarioResult:
    name: str
    status: str
    reconnects: int
    payloads_ok: int
    status_ok: int
    queued_rx_ok: int
    dhcp_rebind_ok: int
    static_fallback_ok: int
    detail: str


@dataclass
class FaultEndpoint:
    name: str
    port: int = 0
    tx_payloads: list[bytes] = field(default_factory=list)
    queued_rx: list[bytes] = field(default_factory=list)
    close_after_tx_count: int | None = None

    def __post_init__(self) -> None:
        self.ready = threading.Event()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.errors: list[BaseException] = []
        self.server: socket.socket | None = None
        self.connections = 0
        self.config_session = 1
        self.config_tx_lane_mask = 0xFF
        self.config_rx_lane_mask = 0xFF

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(5.0):
            raise RuntimeError(f"{self.name} endpoint did not become ready")

    def stop(self) -> None:
        self.stop_event.set()
        if self.server is not None:
            with suppress(OSError):
                self.server.close()
        self.thread.join(timeout=2.0)
        if self.errors:
            raise AssertionError(f"{self.name} endpoint errors: {self.errors!r}")

    def queue_rx(self, payload: bytes) -> None:
        self.queued_rx.append(payload)

    def _status_payload(self) -> bytes:
        fields = (
            0x00000003,  # active + link ready
            0,
            len(self.queued_rx),
            0,
            len(self.tx_payloads),
            len(self.tx_payloads),
            len(self.tx_payloads),
            0,
            len(self.tx_payloads),
            0,
            self.config_tx_lane_mask,
            self.config_rx_lane_mask,
            self.config_tx_lane_mask,
            self.config_rx_lane_mask,
            0,
            0,
        )
        return struct.pack("<16I", *fields)

    def _send(self, sock: socket.socket, frame_type: int, seq: int, payload: bytes = b"") -> None:
        sock.sendall(mock.pack_frame(frame_type, seq, payload))

    def _flush_queued_rx(self, sock: socket.socket) -> None:
        while self.queued_rx:
            payload = self.queued_rx.pop(0)
            self._send(sock, rf.FRAME_RX_DATA, 0x8000 + len(self.tx_payloads) + len(payload), payload)

    def _handle_config(self, frame: rf.Frame) -> bytes:
        if len(frame.payload) not in (8, 12):
            return b"bad_config_payload"
        if (frame.payload[0] & rf.CONFIG_RX_LANE_MASK) and len(frame.payload) < 12:
            return b"bad_config_payload"
        mask, _enable, session, tx_lane_mask = struct.unpack("<BBHI", frame.payload[:8])
        rx_lane_mask = struct.unpack("<I", frame.payload[8:12])[0] if len(frame.payload) == 12 else tx_lane_mask
        if mask & rf.CONFIG_SESSION:
            self.config_session = session
        if mask & rf.CONFIG_LANE_MASK:
            self.config_tx_lane_mask = tx_lane_mask
            if not (mask & rf.CONFIG_RX_LANE_MASK):
                self.config_rx_lane_mask = tx_lane_mask
        if mask & rf.CONFIG_RX_LANE_MASK:
            self.config_rx_lane_mask = rx_lane_mask
        return b"configured"

    def _handle_client(self, sock: socket.socket) -> None:
        self._send(sock, rf.FRAME_ACK, 0, b"connected")
        self._flush_queued_rx(sock)
        while not self.stop_event.is_set():
            try:
                frame = mock.recv_frame(sock)
            except OSError:
                return
            if frame is None:
                return
            if frame.frame_type == rf.FRAME_HELLO:
                self._send(sock, rf.FRAME_ACK, frame.seq, b"rf_comm_ps_bridge")
            elif frame.frame_type == rf.FRAME_STATUS_REQ:
                self._send(sock, rf.FRAME_STATUS_RSP, frame.seq, self._status_payload())
            elif frame.frame_type == rf.FRAME_CLEAR:
                self._send(sock, rf.FRAME_ACK, frame.seq, b"cleared")
            elif frame.frame_type == rf.FRAME_CONFIG:
                result = self._handle_config(frame)
                self._send(sock, rf.FRAME_ACK, frame.seq, result)
            elif frame.frame_type == rf.FRAME_TX_DATA:
                self.tx_payloads.append(frame.payload)
                self._send(sock, rf.FRAME_ACK, frame.seq, b"tx_done")
                self._send(sock, rf.FRAME_RX_DATA, 0x8000 + len(self.tx_payloads), frame.payload)
                if self.close_after_tx_count is not None and len(self.tx_payloads) >= self.close_after_tx_count:
                    return
            else:
                self._send(sock, rf.FRAME_ERROR, frame.seq, b"unknown_frame_type")

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("127.0.0.1", self.port))
                server.listen()
                server.settimeout(0.1)
                self.server = server
                self.port = server.getsockname()[1]
                self.ready.set()
                while not self.stop_event.is_set():
                    try:
                        sock, _addr = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        if self.stop_event.is_set():
                            return
                        raise
                    self.connections += 1
                    with sock:
                        sock.settimeout(2.0)
                        self._handle_client(sock)
        except BaseException as exc:
            self.errors.append(exc)
            self.ready.set()


def wait_for(stats: rf.Stats, predicate, timeout: float = 3.0) -> bool:
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


def exchange_once(port: int, payload: bytes, timeout: float = 3.0) -> tuple[bool, rf.Stats]:
    client, stats, rx_thread = connect_client(port)
    try:
        rf.send_tracked(client, stats, rf.FRAME_HELLO)
        rf.send_tracked(client, stats, rf.FRAME_STATUS_REQ)
        rf.send_tracked(
            client,
            stats,
            rf.FRAME_CONFIG,
            rf.make_config_payload(enable=1, session=0x1234, tx_lane_mask=0x0F, rx_lane_mask=0xF0),
        )
        rf.send_tracked(client, stats, rf.FRAME_TX_DATA, payload)
        ok = wait_for(
            stats,
            lambda: (
                stats.pending_tx_data_count() == 0
                and stats.status_frames >= 1
                and stats.rx_data_bytes >= len(payload)
                and stats.failed_tx_data == 0
                and stats.error_frames == 0
            ),
            timeout,
        )
        return ok, stats
    finally:
        close_client(client, rx_thread)


def scenario_baseline() -> ScenarioResult:
    endpoint = FaultEndpoint("baseline")
    endpoint.start()
    try:
        ok, stats = exchange_once(endpoint.port, b"baseline_payload")
        return ScenarioResult("baseline_tcp", "PASS" if ok else "FAIL", endpoint.connections, stats.rx_data_frames, stats.status_frames, 0, 0, 0, stats.summary(1.0))
    finally:
        endpoint.stop()


def scenario_tcp_reset_reconnect() -> ScenarioResult:
    endpoint = FaultEndpoint("tcp_reset", close_after_tx_count=1)
    endpoint.start()
    try:
        ok1, _stats1 = exchange_once(endpoint.port, b"before_reset")
        ok2, stats2 = exchange_once(endpoint.port, b"after_reset")
        ok = ok1 and ok2 and endpoint.connections >= 2
        return ScenarioResult("tcp_reset_reconnect", "PASS" if ok else "FAIL", endpoint.connections, stats2.rx_data_frames, stats2.status_frames, 0, 0, 0, f"first={int(ok1)} second={int(ok2)}")
    finally:
        endpoint.stop()


def scenario_host_restart() -> ScenarioResult:
    endpoint = FaultEndpoint("host_restart")
    endpoint.start()
    try:
        ok1, _stats1 = exchange_once(endpoint.port, b"host_before_restart")
        time.sleep(0.05)
        ok2, stats2 = exchange_once(endpoint.port, b"host_after_restart")
        ok = ok1 and ok2 and endpoint.connections >= 2
        return ScenarioResult("host_restart", "PASS" if ok else "FAIL", endpoint.connections, stats2.rx_data_frames, stats2.status_frames, 0, 0, 0, f"payloads={len(endpoint.tx_payloads)}")
    finally:
        endpoint.stop()


def scenario_cable_replug() -> ScenarioResult:
    endpoint = FaultEndpoint("cable_replug")
    started = threading.Event()

    def delayed_start() -> None:
        time.sleep(0.25)
        endpoint.start()
        started.set()

    thread = threading.Thread(target=delayed_start, daemon=True)
    thread.start()
    client = rf.RFClient("127.0.0.1", 65500, timeout=0.1)
    reconnects = 0
    ok = False
    try:
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            if started.is_set():
                client.port = endpoint.port
            try:
                client.connect()
                ok = True
                break
            except OSError:
                reconnects += 1
                time.sleep(0.05)
        if not ok:
            return ScenarioResult("cable_replug_reconnect", "FAIL", reconnects, 0, 0, 0, 0, 0, "client never reconnected")
        client.close()
        payload_ok, stats = exchange_once(endpoint.port, b"after_cable_replug")
        return ScenarioResult("cable_replug_reconnect", "PASS" if payload_ok and reconnects > 0 else "FAIL", reconnects + 1, stats.rx_data_frames, stats.status_frames, 0, 0, 0, f"initial_refused={reconnects}")
    finally:
        client.close()
        thread.join(timeout=1.0)
        if endpoint.ready.is_set():
            endpoint.stop()


def scenario_dhcp_rebind() -> ScenarioResult:
    old_endpoint = FaultEndpoint("dhcp_old")
    new_endpoint = FaultEndpoint("dhcp_new")
    old_endpoint.start()
    new_endpoint.start()
    try:
        ok1, _stats1 = exchange_once(old_endpoint.port, b"dhcp_old_address")
        old_endpoint.stop()
        ok2, stats2 = exchange_once(new_endpoint.port, b"dhcp_new_address")
        ok = ok1 and ok2 and new_endpoint.connections >= 1
        return ScenarioResult("dhcp_address_change", "PASS" if ok else "FAIL", old_endpoint.connections + new_endpoint.connections, stats2.rx_data_frames, stats2.status_frames, 0, 1 if ok else 0, 0, f"old_port={old_endpoint.port} new_port={new_endpoint.port}")
    finally:
        if old_endpoint.ready.is_set() and not old_endpoint.stop_event.is_set():
            old_endpoint.stop()
        new_endpoint.stop()


def scenario_static_fallback() -> ScenarioResult:
    static_endpoint = FaultEndpoint("static_fallback")
    static_endpoint.start()
    dhcp_port = 65501
    try:
        fallback_used = False
        try:
            exchange_once(dhcp_port, b"should_not_connect", timeout=0.2)
        except OSError:
            fallback_used = True
        except Exception:
            fallback_used = True
        ok, stats = exchange_once(static_endpoint.port, b"static_fallback_payload")
        passed = ok and fallback_used
        return ScenarioResult("dhcp_timeout_static_fallback", "PASS" if passed else "FAIL", static_endpoint.connections, stats.rx_data_frames, stats.status_frames, 0, 0, 1 if passed else 0, f"fallback_used={int(fallback_used)} static_port={static_endpoint.port}")
    finally:
        static_endpoint.stop()


def scenario_queued_rx_after_reconnect() -> ScenarioResult:
    endpoint = FaultEndpoint("queued_rx")
    endpoint.start()
    try:
        client, stats, rx_thread = connect_client(endpoint.port)
        close_client(client, rx_thread)
        endpoint.queue_rx(b"queued_while_host_down")
        client2, stats2, rx_thread2 = connect_client(endpoint.port)
        try:
            ok = wait_for(stats2, lambda: stats2.rx_data_bytes >= len(b"queued_while_host_down"), timeout=3.0)
            return ScenarioResult("queued_rx_after_reconnect", "PASS" if ok else "FAIL", endpoint.connections, stats2.rx_data_frames, stats2.status_frames, 1 if ok else 0, 0, 0, stats2.summary(1.0))
        finally:
            close_client(client2, rx_thread2)
    finally:
        endpoint.stop()


def write_reports(prefix: Path, results: list[ScenarioResult]) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    md_path = prefix.with_suffix(".md")
    json_path = prefix.with_suffix(".json")
    csv_path = prefix.with_suffix(".csv")
    overall = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"
    generated = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    md = [
        "# Network Fault Recovery Offline Model",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- Real Ethernet: `not used`",
        "- FPGA programming: `not performed`",
        "- UART write: `not performed`",
        "- TFDU drive: `not performed`",
        "",
        "## Scenarios",
        "",
        "| scenario | status | reconnects | payloads_ok | status_ok | queued_rx_ok | dhcp_rebind_ok | static_fallback_ok | detail |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        md.append(
            f"| {result.name} | {result.status} | {result.reconnects} | {result.payloads_ok} | {result.status_ok} | "
            f"{result.queued_rx_ok} | {result.dhcp_rebind_ok} | {result.static_fallback_ok} | {result.detail.replace('|', '/')} |"
        )
    md.extend(
        [
            "",
            "```text",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "NO_REAL_BOARD_TCP_DHCP=1",
            f"RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall={overall} scenarios={len(results)}",
            "```",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "no_real_board_tcp_dhcp": True,
        "scenarios": [asdict(result) for result in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-prefix", type=Path, default=REPORTS / "network_fault_recovery_model_current")
    args = parser.parse_args()

    prefix = args.report_prefix
    if not prefix.is_absolute():
        prefix = ROOT / prefix

    scenarios = [
        scenario_baseline,
        scenario_tcp_reset_reconnect,
        scenario_host_restart,
        scenario_cable_replug,
        scenario_dhcp_rebind,
        scenario_static_fallback,
        scenario_queued_rx_after_reconnect,
    ]
    results = [scenario() for scenario in scenarios]
    write_reports(prefix, results)
    overall = "PASS" if all(result.status == "PASS" for result in results) else "FAIL"
    print(f"RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall={overall} scenarios={len(results)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    for result in results:
        print(f"SCENARIO name={result.name} status={result.status} reconnects={result.reconnects} detail={result.detail}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
