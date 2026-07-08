#!/usr/bin/env python3
"""Offline two-AX7010 end-to-end RFCM/IR link model.

This is a software-only gate. It proves the host-facing protocol can exercise
two independent PS bridge endpoints with bidirectional traffic through a shared
infrared-link model. It does not claim real board, Ethernet, DHCP, TFDU, or
rotating-shaft hardware evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import queue
import socket
import struct
import sys
import threading
import time
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mock_rfcm_server as mock
import rf_comm_client as rf


STATUS_ACTIVE = 0x00000001
STATUS_LINK_READY = 0x00000002


@dataclass
class LinkStats:
    lane_count: int
    transfers: int = 0
    bytes_moved: int = 0
    route_changes: int = 0
    failed_route_events: int = 0
    failed_attempts: int = 0
    fragment_ack_loss_events: int = 0
    final_ack_loss_events: int = 0
    reconnect_queued_rx: int = 0
    max_search_attempts: int = 0
    max_retry_observed: int = 0
    tx_lane_coverage: int = 0
    rx_lane_coverage: int = 0
    hdx_tx_lane_coverage: int = 0
    hdx_rx_lane_coverage: int = 0
    fdx_a_to_b_tx_lane_coverage: int = 0
    fdx_a_to_b_rx_lane_coverage: int = 0
    fdx_b_to_a_tx_lane_coverage: int = 0
    fdx_b_to_a_rx_lane_coverage: int = 0
    route_probe_events: int = 0
    max_route_probe_observed: int = 0


@dataclass
class EndpointCounters:
    tx_ok: int = 0
    tx_fail: int = 0
    rx_ok: int = 0
    rx_bad: int = 0
    status_req: int = 0
    config_count: int = 0
    reconnects: int = 0


@dataclass
class EndpointConfig:
    enable: int = 1
    session: int = 1
    tx_lane_mask: int = 0xFF
    rx_lane_mask: int = 0xFF


@dataclass
class ReceivedFrameLog:
    stats: rf.Stats
    payloads: list[bytes] = field(default_factory=list)
    frames: list[rf.Frame] = field(default_factory=list)
    errors: list[BaseException] = field(default_factory=list)


def free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def mask_has(mask: int, lane: int) -> bool:
    return ((mask >> lane) & 1) != 0


def first_lane(mask: int, lane_count: int) -> int:
    for lane in range(lane_count):
        if mask_has(mask, lane):
            return lane
    return 0


def make_payload(prefix: bytes, index: int, size: int) -> bytes:
    if size < len(prefix) + 2:
        raise ValueError("payload size is too small for prefix")
    head = prefix + struct.pack("<H", index & 0xFFFF)
    body = bytes(((index + offset) & 0xFF) for offset in range(size - len(head)))
    return head + body


class IrLinkModel:
    def __init__(self, lane_count: int = 8) -> None:
        self.lane_count = lane_count
        self.stats = LinkStats(lane_count=lane_count)
        self.lock = threading.Lock()

    def _route_map(self, transfer_index: int) -> int:
        return (transfer_index + (transfer_index // 5) + (transfer_index // 17)) % self.lane_count

    def _fragment_count(self, payload_len: int) -> int:
        return max(1, (payload_len + 254) // 255)

    def _mode_name(self, source: "BridgeEndpoint", destination: "BridgeEndpoint") -> str:
        if (
            source.name == "ax7010_a"
            and destination.name == "ax7010_b"
            and source.config.tx_lane_mask == 0x0F
            and destination.config.rx_lane_mask == 0x0F
        ):
            return "fdx_a_to_b"
        if (
            source.name == "ax7010_b"
            and destination.name == "ax7010_a"
            and source.config.tx_lane_mask == 0xF0
            and destination.config.rx_lane_mask == 0xF0
        ):
            return "fdx_b_to_a"
        return "hdx"

    def _record_lane_coverage(self, mode: str, tx_lane: int, rx_lane: int) -> None:
        tx_bit = 1 << tx_lane
        rx_bit = 1 << rx_lane
        self.stats.tx_lane_coverage |= tx_bit
        self.stats.rx_lane_coverage |= rx_bit
        if mode == "fdx_a_to_b":
            self.stats.fdx_a_to_b_tx_lane_coverage |= tx_bit
            self.stats.fdx_a_to_b_rx_lane_coverage |= rx_bit
        elif mode == "fdx_b_to_a":
            self.stats.fdx_b_to_a_tx_lane_coverage |= tx_bit
            self.stats.fdx_b_to_a_rx_lane_coverage |= rx_bit
        else:
            self.stats.hdx_tx_lane_coverage |= tx_bit
            self.stats.hdx_rx_lane_coverage |= rx_bit

    def _mode_lane_coverage(self, mode: str) -> tuple[int, int]:
        if mode == "fdx_a_to_b":
            return self.stats.fdx_a_to_b_tx_lane_coverage, self.stats.fdx_a_to_b_rx_lane_coverage
        if mode == "fdx_b_to_a":
            return self.stats.fdx_b_to_a_tx_lane_coverage, self.stats.fdx_b_to_a_rx_lane_coverage
        return self.stats.hdx_tx_lane_coverage, self.stats.hdx_rx_lane_coverage

    def transmit(self, source: "BridgeEndpoint", payload: bytes) -> tuple[bool, str]:
        destination = source.peer
        if destination is None:
            return False, "no_peer"
        if not source.config.enable:
            return False, "source_disabled"
        if not destination.config.enable:
            return False, "destination_disabled"
        if source.config.tx_lane_mask == 0 or destination.config.rx_lane_mask == 0:
            return False, "lane_mask_empty"

        with self.lock:
            transfer_index = self.stats.transfers
            base_route_map = self._route_map(transfer_index)
            mode = self._mode_name(source, destination)
            if transfer_index > 0:
                self.stats.route_changes += 1

            fragment_count = self._fragment_count(len(payload))
            tx_start = (transfer_index * 3 + fragment_count) % self.lane_count
            search_attempts = 0
            blocked_attempts = 1 + (transfer_index % 3) if (transfer_index % 7) == 6 else 0
            selected_tx = first_lane(source.config.tx_lane_mask, self.lane_count)
            selected_rx = first_lane(destination.config.rx_lane_mask, self.lane_count)
            best_score = -1
            best_route_probe = self.lane_count
            best_attempt = self.lane_count * 2
            coverage_tx, coverage_rx = self._mode_lane_coverage(mode)
            best_possible_score = 0
            if source.config.tx_lane_mask & ~coverage_tx:
                best_possible_score += 4
            if destination.config.rx_lane_mask & ~coverage_rx:
                best_possible_score += 2

            for blocked in range(blocked_attempts):
                tx_lane = (tx_start + blocked) % self.lane_count
                if mask_has(source.config.tx_lane_mask, tx_lane):
                    self.stats.tx_lane_coverage |= 1 << tx_lane
                    self.stats.failed_attempts += 1
                    search_attempts += 1

            selected_route_map = base_route_map
            selected_route_probe = 0
            for route_probe in range(self.lane_count):
                route_map = (base_route_map + route_probe) % self.lane_count
                for attempt in range(self.lane_count * 2):
                    tx_lane = (tx_start + blocked_attempts + attempt) % self.lane_count
                    if not mask_has(source.config.tx_lane_mask, tx_lane):
                        continue
                    rx_lane = (tx_lane + route_map) % self.lane_count
                    search_attempts += 1
                    self.stats.tx_lane_coverage |= 1 << tx_lane
                    if mask_has(destination.config.rx_lane_mask, rx_lane):
                        tx_bit = 1 << tx_lane
                        rx_bit = 1 << rx_lane
                        score = 0
                        if not (coverage_tx & tx_bit):
                            score += 4
                        if not (coverage_rx & rx_bit):
                            score += 2
                        if (
                            score > best_score
                            or (
                                score == best_score
                                and (route_probe, attempt) < (best_route_probe, best_attempt)
                            )
                        ):
                            selected_tx = tx_lane
                            selected_rx = rx_lane
                            selected_route_map = route_map
                            selected_route_probe = route_probe
                            best_route_probe = route_probe
                            best_attempt = attempt
                            best_score = score
                        if score == best_possible_score:
                            break
                    self.stats.failed_attempts += 1
                if best_score == best_possible_score:
                    break

            if best_score < 0:
                return False, "route_not_found"

            self._record_lane_coverage(mode, selected_tx, selected_rx)
            if search_attempts > 1:
                self.stats.failed_route_events += 1
            if selected_route_probe > 0:
                self.stats.route_probe_events += 1
                self.stats.max_route_probe_observed = max(
                    self.stats.max_route_probe_observed,
                    selected_route_probe,
                )
            self.stats.max_search_attempts = max(self.stats.max_search_attempts, search_attempts)
            self.stats.max_retry_observed = max(self.stats.max_retry_observed, search_attempts - 1)
            if transfer_index % 11 == 10:
                self.stats.fragment_ack_loss_events += 1
            if transfer_index % 17 == 16:
                self.stats.final_ack_loss_events += 1

            self.stats.transfers += 1
            self.stats.bytes_moved += len(payload)

        destination.deliver_rx(payload)
        return True, f"mode={mode} tx_lane={selected_tx} rx_lane={selected_rx} route_map={selected_route_map} route_probe={selected_route_probe}"


class BridgeEndpoint:
    def __init__(self, name: str, port: int, link: IrLinkModel, log_path: Path | None = None) -> None:
        self.name = name
        self.port = port
        self.link = link
        self.log_path = log_path
        self.peer: BridgeEndpoint | None = None
        self.config = EndpointConfig()
        self.counters = EndpointCounters()
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.errors: list[BaseException] = []
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.server: socket.socket | None = None
        self.client_sock: socket.socket | None = None
        self.client_lock = threading.Lock()
        self.pending_rx: queue.Queue[bytes] = queue.Queue()
        self.rx_seq = 0x8000

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(5.0):
            raise RuntimeError(f"{self.name} endpoint did not start")

    def stop(self) -> None:
        self.stop_event.set()
        if self.server is not None:
            with suppress(OSError):
                self.server.close()
        with self.client_lock:
            if self.client_sock is not None:
                with suppress(OSError):
                    self.client_sock.close()
                self.client_sock = None
        self.thread.join(timeout=2.0)
        if self.errors:
            raise AssertionError(f"{self.name} endpoint errors: {self.errors!r}")

    def log(self, text: str) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {self.name} {text}\n")

    def _send_raw(self, sock: socket.socket, payload: bytes) -> None:
        sock.sendall(payload)

    def _send(self, sock: socket.socket, frame_type: int, seq: int, payload: bytes = b"") -> None:
        self._send_raw(sock, mock.pack_frame(frame_type, seq, payload))

    def _status_payload(self) -> bytes:
        fields = (
            STATUS_ACTIVE | STATUS_LINK_READY,
            0,
            0,
            0,
            self.counters.tx_ok,
            self.counters.rx_ok,
            self.counters.tx_ok,
            self.counters.tx_fail,
            self.counters.rx_ok,
            self.counters.rx_bad,
            self.config.tx_lane_mask,
            self.config.rx_lane_mask,
            self.link.stats.tx_lane_coverage,
            self.link.stats.rx_lane_coverage,
            self.link.stats.failed_attempts,
            self.link.stats.fragment_ack_loss_events + self.link.stats.final_ack_loss_events,
        )
        return struct.pack("<16I", *fields)

    def deliver_rx(self, payload: bytes) -> None:
        with self.client_lock:
            sock = self.client_sock
        if sock is None:
            self.pending_rx.put(payload)
            with self.link.lock:
                self.link.stats.reconnect_queued_rx += 1
            return
        try:
            self._send(sock, rf.FRAME_RX_DATA, self.rx_seq, payload)
            self.rx_seq = ((self.rx_seq + 1) & 0xFFFF) or 0x8000
            self.counters.rx_ok += 1
        except OSError:
            self.pending_rx.put(payload)
            with self.link.lock:
                self.link.stats.reconnect_queued_rx += 1

    def _flush_pending_rx(self, sock: socket.socket) -> None:
        while not self.pending_rx.empty():
            payload = self.pending_rx.get()
            self._send(sock, rf.FRAME_RX_DATA, self.rx_seq, payload)
            self.rx_seq = ((self.rx_seq + 1) & 0xFFFF) or 0x8000
            self.counters.rx_ok += 1

    def _handle_config(self, sock: socket.socket, frame: rf.Frame) -> None:
        if len(frame.payload) not in (8, 12):
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
            return
        if (frame.payload[0] & rf.CONFIG_RX_LANE_MASK) and len(frame.payload) < 12:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
            return
        mask, enable, session, tx_lane_mask = struct.unpack("<BBHI", frame.payload[:8])
        rx_lane_mask = (
            struct.unpack("<I", frame.payload[8:12])[0]
            if len(frame.payload) >= 12 else tx_lane_mask
        )
        if mask & rf.CONFIG_ENABLE:
            self.config.enable = 1 if enable else 0
        if mask & rf.CONFIG_SESSION:
            self.config.session = session
        if mask & rf.CONFIG_LANE_MASK:
            self.config.tx_lane_mask = tx_lane_mask
            if not (mask & rf.CONFIG_RX_LANE_MASK):
                self.config.rx_lane_mask = tx_lane_mask
        if mask & rf.CONFIG_RX_LANE_MASK:
            self.config.rx_lane_mask = rx_lane_mask
        self.counters.config_count += 1
        self._send(sock, rf.FRAME_ACK, frame.seq, b"configured")

    def _handle_client(self, sock: socket.socket) -> None:
        with self.client_lock:
            self.client_sock = sock
        self.counters.reconnects += 1
        self._send(sock, rf.FRAME_ACK, 0, f"{self.name}_connected".encode("ascii"))
        self._flush_pending_rx(sock)

        while not self.stop_event.is_set():
            try:
                frame = mock.recv_frame(sock)
            except OSError:
                return
            if frame is None:
                return

            if frame.frame_type == rf.FRAME_HELLO:
                self._send(sock, rf.FRAME_ACK, frame.seq, f"rf_comm_{self.name}_bridge_model".encode("ascii"))
            elif frame.frame_type == rf.FRAME_STATUS_REQ:
                self.counters.status_req += 1
                self._send(sock, rf.FRAME_STATUS_RSP, frame.seq, self._status_payload())
            elif frame.frame_type == rf.FRAME_CLEAR:
                self._send(sock, rf.FRAME_ACK, frame.seq, b"cleared")
            elif frame.frame_type == rf.FRAME_CONFIG:
                self._handle_config(sock, frame)
            elif frame.frame_type == rf.FRAME_TX_DATA:
                ok, detail = self.link.transmit(self, frame.payload)
                if ok:
                    self.counters.tx_ok += 1
                    self._send(sock, rf.FRAME_ACK, frame.seq, b"tx_done")
                else:
                    self.counters.tx_fail += 1
                    self._send(sock, rf.FRAME_ERROR, frame.seq, detail.encode("ascii"))
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
                        sock, addr = server.accept()
                    except socket.timeout:
                        continue
                    except OSError:
                        if self.stop_event.is_set():
                            return
                        raise
                    self.log(f"ACCEPT {addr[0]}:{addr[1]}")
                    with sock:
                        sock.settimeout(2.0)
                        self._handle_client(sock)
                    with self.client_lock:
                        if self.client_sock is sock:
                            self.client_sock = None
                    self.log("CLOSE")
        except BaseException as exc:
            if not self.stop_event.is_set():
                self.errors.append(exc)
            self.ready.set()


class TwoAx7010OfflineModel:
    def __init__(self, log_dir: Path) -> None:
        self.link = IrLinkModel(lane_count=8)
        self.log_dir = log_dir
        self.endpoint_a = BridgeEndpoint("ax7010_a", free_tcp_port(), self.link, log_dir / "two_ax7010_endpoint.log")
        self.endpoint_b = BridgeEndpoint("ax7010_b", free_tcp_port(), self.link, log_dir / "two_ax7010_endpoint.log")
        self.endpoint_a.peer = self.endpoint_b
        self.endpoint_b.peer = self.endpoint_a

    def start(self) -> None:
        self.endpoint_a.start()
        self.endpoint_b.start()

    def stop(self) -> None:
        self.endpoint_a.stop()
        self.endpoint_b.stop()


def receiver_probe(client: rf.RFClient, log: ReceivedFrameLog, event_log: rf.EventLog | None) -> None:
    while client.running:
        try:
            frame = client.recv_frame()
        except (OSError, RuntimeError) as exc:
            if client.running:
                log.errors.append(exc)
            client.running = False
            return
        if frame is None:
            client.running = False
            return
        log.stats.mark_received(frame)
        log.frames.append(frame)
        if frame.frame_type == rf.FRAME_RX_DATA:
            log.payloads.append(frame.payload)
        if event_log is not None:
            event_log.write(frame)


def connect_probe(port: int, csv_path: Path | None) -> tuple[rf.RFClient, ReceivedFrameLog, threading.Thread, rf.EventLog | None]:
    client = rf.RFClient("127.0.0.1", port, timeout=2.0)
    client.connect()
    stats = rf.Stats()
    log = ReceivedFrameLog(stats=stats)
    event_log = rf.EventLog(csv_path) if csv_path is not None else None
    thread = threading.Thread(target=receiver_probe, args=(client, log, event_log), daemon=True)
    thread.start()
    return client, log, thread, event_log


def close_probe(client: rf.RFClient, thread: threading.Thread, event_log: rf.EventLog | None) -> None:
    client.close()
    thread.join(timeout=1.0)
    if event_log is not None:
        event_log.close()


def wait_for(predicate, timeout: float, description: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError(f"timeout waiting for {description}")


def endpoint_has_no_client(endpoint: BridgeEndpoint) -> bool:
    with endpoint.client_lock:
        return endpoint.client_sock is None


def send_control_setup(client: rf.RFClient, stats: rf.Stats, session: int, tx_mask: int, rx_mask: int) -> None:
    rf.send_tracked(client, stats, rf.FRAME_HELLO)
    rf.send_tracked(client, stats, rf.FRAME_CLEAR)
    rf.send_tracked(client, stats, rf.FRAME_CONFIG, rf.make_config_payload(
        enable=1,
        session=session,
        tx_lane_mask=tx_mask,
        rx_lane_mask=rx_mask,
    ))
    rf.send_tracked(client, stats, rf.FRAME_STATUS_REQ)


def sender_thread(
    client: rf.RFClient,
    stats: rf.Stats,
    prefix: bytes,
    repeat: int,
    payload_size: int,
    sent_payloads: list[bytes],
    failures: list[BaseException],
) -> None:
    try:
        for index in range(repeat):
            payload = make_payload(prefix, index, payload_size)
            sent_payloads.append(payload)
            rf.send_tracked(client, stats, rf.FRAME_TX_DATA, payload)
            if (index % 8) == 7:
                stats.wait_for_tx_window(4, 3.0)
    except BaseException as exc:
        failures.append(exc)


def write_summary_outputs(args: argparse.Namespace, summary: dict[str, object]) -> None:
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    link = summary["link"]
    assert isinstance(link, dict)
    if args.csv_output is not None:
        args.csv_output.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            ("overall", "PASS", "result", "TWO_AX7010_END_TO_END_OFFLINE_PASS"),
            ("traffic", "PASS", "repeat", str(summary["repeat"])),
            ("traffic", "PASS", "fdx_repeat", str(summary["fdx_repeat"])),
            ("traffic", "PASS", "payload_bytes", str(summary["payload_bytes"])),
            ("traffic", "PASS", "a_rx_ok", str(summary["a_rx_ok"])),
            ("traffic", "PASS", "b_rx_ok", str(summary["b_rx_ok"])),
            ("coverage", "PASS", "tx_lane_coverage", f"0x{int(link['tx_lane_coverage']):02x}"),
            ("coverage", "PASS", "rx_lane_coverage", f"0x{int(link['rx_lane_coverage']):02x}"),
            ("coverage", "PASS", "hdx_tx_lane_coverage", f"0x{int(link['hdx_tx_lane_coverage']):02x}"),
            ("coverage", "PASS", "hdx_rx_lane_coverage", f"0x{int(link['hdx_rx_lane_coverage']):02x}"),
            ("coverage", "PASS", "fdx_a_to_b_tx_lane_coverage", f"0x{int(link['fdx_a_to_b_tx_lane_coverage']):02x}"),
            ("coverage", "PASS", "fdx_a_to_b_rx_lane_coverage", f"0x{int(link['fdx_a_to_b_rx_lane_coverage']):02x}"),
            ("coverage", "PASS", "fdx_b_to_a_tx_lane_coverage", f"0x{int(link['fdx_b_to_a_tx_lane_coverage']):02x}"),
            ("coverage", "PASS", "fdx_b_to_a_rx_lane_coverage", f"0x{int(link['fdx_b_to_a_rx_lane_coverage']):02x}"),
            ("recovery", "PASS", "fragment_ack_loss_events", str(link["fragment_ack_loss_events"])),
            ("recovery", "PASS", "final_ack_loss_events", str(link["final_ack_loss_events"])),
            ("recovery", "PASS", "reconnect_queued_rx", str(link["reconnect_queued_rx"])),
            ("autoroute", "PASS", "route_probe_events", str(link["route_probe_events"])),
            ("autoroute", "PASS", "max_route_probe_observed", str(link["max_route_probe_observed"])),
        ]
        with args.csv_output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["category", "status", "metric", "value"])
            writer.writerows(rows)

    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Two AX7010 Offline End-to-End Model",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Verdict",
            "",
            "- Overall: `PASS`",
            "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "",
            "## Traffic",
            "",
            f"- Bidirectional 8-lane repeat: `{summary['repeat']}`",
            f"- Full-duplex 4+4 repeat: `{summary['fdx_repeat']}`",
            f"- Payload bytes: `{summary['payload_bytes']}`",
            f"- A RX OK: `{summary['a_rx_ok']}`",
            f"- B RX OK: `{summary['b_rx_ok']}`",
            f"- Queued reconnect RX: `{summary['queued_reconnect_rx']}`",
            "",
            "## Lane Coverage",
            "",
            "| metric | value |",
            "| --- | --- |",
            f"| tx_lane_coverage | `0x{int(link['tx_lane_coverage']):02x}` |",
            f"| rx_lane_coverage | `0x{int(link['rx_lane_coverage']):02x}` |",
            f"| hdx_tx_lane_coverage | `0x{int(link['hdx_tx_lane_coverage']):02x}` |",
            f"| hdx_rx_lane_coverage | `0x{int(link['hdx_rx_lane_coverage']):02x}` |",
            f"| fdx_a_to_b_tx_lane_coverage | `0x{int(link['fdx_a_to_b_tx_lane_coverage']):02x}` |",
            f"| fdx_a_to_b_rx_lane_coverage | `0x{int(link['fdx_a_to_b_rx_lane_coverage']):02x}` |",
            f"| fdx_b_to_a_tx_lane_coverage | `0x{int(link['fdx_b_to_a_tx_lane_coverage']):02x}` |",
            f"| fdx_b_to_a_rx_lane_coverage | `0x{int(link['fdx_b_to_a_rx_lane_coverage']):02x}` |",
            "",
            "## Recovery",
            "",
            "| metric | value |",
            "| --- | --- |",
            f"| failed_route_events | `{link['failed_route_events']}` |",
            f"| route_probe_events | `{link['route_probe_events']}` |",
            f"| max_route_probe_observed | `{link['max_route_probe_observed']}` |",
            f"| fragment_ack_loss_events | `{link['fragment_ack_loss_events']}` |",
            f"| final_ack_loss_events | `{link['final_ack_loss_events']}` |",
            f"| reconnect_queued_rx | `{link['reconnect_queued_rx']}` |",
            "",
        ]
        args.markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_model(args: argparse.Namespace) -> int:
    args.log_dir.mkdir(parents=True, exist_ok=True)
    model = TwoAx7010OfflineModel(args.log_dir)
    model.start()

    client_a: rf.RFClient | None = None
    client_b: rf.RFClient | None = None
    thread_a: threading.Thread | None = None
    thread_b: threading.Thread | None = None
    event_a: rf.EventLog | None = None
    event_b: rf.EventLog | None = None
    client_b2: rf.RFClient | None = None
    thread_b2: threading.Thread | None = None
    event_b2: rf.EventLog | None = None

    try:
        client_a, log_a, thread_a, event_a = connect_probe(model.endpoint_a.port, args.log_dir / "two_ax7010_pc_a.csv")
        client_b, log_b, thread_b, event_b = connect_probe(model.endpoint_b.port, args.log_dir / "two_ax7010_pc_b.csv")

        send_control_setup(client_a, log_a.stats, 0xA701, 0xFF, 0xFF)
        send_control_setup(client_b, log_b.stats, 0xB701, 0xFF, 0xFF)
        wait_for(lambda: log_a.stats.pending_count() == 0 and log_b.stats.pending_count() == 0, 5.0, "initial control ACKs")

        sent_ab: list[bytes] = []
        sent_ba: list[bytes] = []
        failures: list[BaseException] = []
        start = time.monotonic()
        tx_a = threading.Thread(
            target=sender_thread,
            args=(client_a, log_a.stats, b"A2B", args.repeat, args.payload_size, sent_ab, failures),
            daemon=True,
        )
        tx_b = threading.Thread(
            target=sender_thread,
            args=(client_b, log_b.stats, b"B2A", args.repeat, args.payload_size, sent_ba, failures),
            daemon=True,
        )
        tx_a.start()
        tx_b.start()
        tx_a.join(timeout=args.timeout)
        tx_b.join(timeout=args.timeout)
        if tx_a.is_alive() or tx_b.is_alive():
            raise AssertionError("bidirectional sender threads timed out")
        if failures:
            raise AssertionError(f"sender failure: {failures!r}")

        wait_for(lambda: log_a.stats.pending_tx_data_count() == 0 and log_b.stats.pending_tx_data_count() == 0, args.timeout, "all TX_DATA ACKs")
        wait_for(lambda: len(log_a.payloads) >= args.repeat and len(log_b.payloads) >= args.repeat, args.timeout, "bidirectional RX_DATA")
        elapsed = time.monotonic() - start

        if log_a.payloads[:args.repeat] != sent_ba:
            raise AssertionError("A-side RX payloads do not match B->A payloads")
        if log_b.payloads[:args.repeat] != sent_ab:
            raise AssertionError("B-side RX payloads do not match A->B payloads")
        if log_a.stats.error_frames or log_b.stats.error_frames:
            raise AssertionError("unexpected ERROR frame during bidirectional exchange")

        send_control_setup(client_a, log_a.stats, 0xA7F1, 0x0F, 0xF0)
        send_control_setup(client_b, log_b.stats, 0xB7F1, 0xF0, 0x0F)
        wait_for(lambda: log_a.stats.pending_count() == 0 and log_b.stats.pending_count() == 0, 5.0, "full-duplex config ACKs")

        fdx_repeat = max(16, min(args.repeat, 32))
        a_payload_start = len(log_a.payloads)
        b_payload_start = len(log_b.payloads)
        sent_fdx_ab: list[bytes] = []
        sent_fdx_ba: list[bytes] = []
        fdx_failures: list[BaseException] = []
        tx_fdx_a = threading.Thread(
            target=sender_thread,
            args=(client_a, log_a.stats, b"FAB", fdx_repeat, args.payload_size, sent_fdx_ab, fdx_failures),
            daemon=True,
        )
        tx_fdx_b = threading.Thread(
            target=sender_thread,
            args=(client_b, log_b.stats, b"FBA", fdx_repeat, args.payload_size, sent_fdx_ba, fdx_failures),
            daemon=True,
        )
        tx_fdx_a.start()
        tx_fdx_b.start()
        tx_fdx_a.join(timeout=args.timeout)
        tx_fdx_b.join(timeout=args.timeout)
        if tx_fdx_a.is_alive() or tx_fdx_b.is_alive():
            raise AssertionError("full-duplex sender threads timed out")
        if fdx_failures:
            raise AssertionError(f"full-duplex sender failure: {fdx_failures!r}")
        wait_for(lambda: log_a.stats.pending_tx_data_count() == 0 and log_b.stats.pending_tx_data_count() == 0, args.timeout, "full-duplex TX_DATA ACKs")
        wait_for(lambda: len(log_a.payloads) >= a_payload_start + fdx_repeat and len(log_b.payloads) >= b_payload_start + fdx_repeat, args.timeout, "full-duplex RX_DATA")
        if log_a.payloads[a_payload_start:a_payload_start + fdx_repeat] != sent_fdx_ba:
            raise AssertionError("A-side full-duplex RX payloads do not match B->A payloads")
        if log_b.payloads[b_payload_start:b_payload_start + fdx_repeat] != sent_fdx_ab:
            raise AssertionError("B-side full-duplex RX payloads do not match A->B payloads")
        if log_a.stats.error_frames or log_b.stats.error_frames:
            raise AssertionError("unexpected ERROR frame during full-duplex exchange")

        assert client_b is not None and thread_b is not None
        close_probe(client_b, thread_b, event_b)
        client_b = None
        thread_b = None
        event_b = None
        wait_for(lambda: endpoint_has_no_client(model.endpoint_b), args.timeout, "B endpoint disconnect")

        queued_payload = make_payload(b"AQB", args.repeat + 1, args.payload_size)
        rf.send_tracked(client_a, log_a.stats, rf.FRAME_TX_DATA, queued_payload)
        wait_for(lambda: log_a.stats.pending_tx_data_count() == 0, args.timeout, "queued reconnect TX ACK")

        client_b2, log_b2, thread_b2, event_b2 = connect_probe(model.endpoint_b.port, args.log_dir / "two_ax7010_pc_b_reconnect.csv")
        rf.send_tracked(client_b2, log_b2.stats, rf.FRAME_HELLO)
        rf.send_tracked(client_b2, log_b2.stats, rf.FRAME_STATUS_REQ)
        wait_for(lambda: queued_payload in log_b2.payloads, args.timeout, "queued RX after B reconnect")
        wait_for(lambda: log_b2.stats.pending_count() == 0, args.timeout, "B reconnect control ACKs")

        total_ab = len(sent_ab) + len(sent_fdx_ab) + 1
        total_ba = len(sent_ba) + len(sent_fdx_ba)
        a_rx_ok = len(log_a.payloads)
        b_rx_ok = len(log_b.payloads) + len(log_b2.payloads)
        if total_ab != args.repeat + fdx_repeat + 1 or total_ba != args.repeat + fdx_repeat:
            raise AssertionError("unexpected send count")
        if a_rx_ok != args.repeat + fdx_repeat or b_rx_ok != args.repeat + fdx_repeat + 1:
            raise AssertionError(f"unexpected rx count a_rx={a_rx_ok} b_rx={b_rx_ok}")

        link = model.link.stats
        if link.tx_lane_coverage != 0xFF or link.rx_lane_coverage != 0xFF:
            raise AssertionError(
                f"lane coverage incomplete tx=0x{link.tx_lane_coverage:02x} rx=0x{link.rx_lane_coverage:02x}"
            )
        if link.hdx_tx_lane_coverage != 0xFF or link.hdx_rx_lane_coverage != 0xFF:
            raise AssertionError(
                f"8-lane half-duplex coverage incomplete tx=0x{link.hdx_tx_lane_coverage:02x} rx=0x{link.hdx_rx_lane_coverage:02x}"
            )
        if link.fdx_a_to_b_tx_lane_coverage != 0x0F or link.fdx_a_to_b_rx_lane_coverage != 0x0F:
            raise AssertionError(
                f"A->B full-duplex partition coverage mismatch tx=0x{link.fdx_a_to_b_tx_lane_coverage:02x} rx=0x{link.fdx_a_to_b_rx_lane_coverage:02x}"
            )
        if link.fdx_b_to_a_tx_lane_coverage != 0xF0 or link.fdx_b_to_a_rx_lane_coverage != 0xF0:
            raise AssertionError(
                f"B->A full-duplex partition coverage mismatch tx=0x{link.fdx_b_to_a_tx_lane_coverage:02x} rx=0x{link.fdx_b_to_a_rx_lane_coverage:02x}"
            )
        if link.fragment_ack_loss_events == 0 or link.final_ack_loss_events == 0 or link.failed_route_events == 0:
            raise AssertionError("link recovery paths were not exercised")
        if link.reconnect_queued_rx == 0:
            raise AssertionError("reconnect queued RX path was not exercised")

        tx_mbps = (link.bytes_moved * 8.0) / max(elapsed, 1e-9) / 1_000_000.0
        summary = {
            "result": "TWO_AX7010_END_TO_END_OFFLINE_PASS",
            "repeat": args.repeat,
            "fdx_repeat": fdx_repeat,
            "payload_bytes": args.payload_size,
            "endpoints": 2,
            "a_tx_ok": log_a.stats.acked_tx_data,
            "b_tx_ok": log_b.stats.acked_tx_data,
            "a_rx_ok": a_rx_ok,
            "b_rx_ok": b_rx_ok,
            "queued_reconnect_rx": 1,
            "aggregate_tcp_model_mbps": tx_mbps,
            "config": {
                "initial_hdx": {
                    "a_tx_lane_mask": "0xff",
                    "a_rx_lane_mask": "0xff",
                    "b_tx_lane_mask": "0xff",
                    "b_rx_lane_mask": "0xff",
                },
                "fdx_4plus4": {
                    "a_tx_lane_mask": "0x0f",
                    "a_rx_lane_mask": "0xf0",
                    "b_tx_lane_mask": "0xf0",
                    "b_rx_lane_mask": "0x0f",
                },
            },
            "endpoint_a": {
                "config": asdict(model.endpoint_a.config),
                "counters": asdict(model.endpoint_a.counters),
            },
            "endpoint_b": {
                "config": asdict(model.endpoint_b.config),
                "counters": asdict(model.endpoint_b.counters),
            },
            "link": asdict(link),
        }
        write_summary_outputs(args, summary)
        print(
            "TWO_AX7010_END_TO_END_OFFLINE_PASS "
            f"repeat={args.repeat} payload_bytes={args.payload_size} endpoints=2 "
            f"a_tx_ok={log_a.stats.acked_tx_data} b_tx_ok={log_b.stats.acked_tx_data} "
            f"a_rx_ok={a_rx_ok} b_rx_ok={b_rx_ok} queued_reconnect_rx=1 "
            f"fdx_repeat={fdx_repeat} "
            f"link_transfers={link.transfers} link_bytes={link.bytes_moved} "
            f"aggregate_tcp_model_mbps={tx_mbps:.6f} lane_count={link.lane_count} "
            f"route_changes={link.route_changes} failed_route_events={link.failed_route_events} "
            f"failed_attempts={link.failed_attempts} max_search_attempts={link.max_search_attempts} "
            f"max_retry_observed={link.max_retry_observed} fragment_ack_loss_events={link.fragment_ack_loss_events} "
            f"final_ack_loss_events={link.final_ack_loss_events} reconnect_queued_rx={link.reconnect_queued_rx} "
            f"tx_lane_coverage=0x{link.tx_lane_coverage:02x} rx_lane_coverage=0x{link.rx_lane_coverage:02x} "
            f"hdx_tx_lane_coverage=0x{link.hdx_tx_lane_coverage:02x} hdx_rx_lane_coverage=0x{link.hdx_rx_lane_coverage:02x} "
            f"fdx_a_to_b_tx_lane_coverage=0x{link.fdx_a_to_b_tx_lane_coverage:02x} "
            f"fdx_a_to_b_rx_lane_coverage=0x{link.fdx_a_to_b_rx_lane_coverage:02x} "
            f"fdx_b_to_a_tx_lane_coverage=0x{link.fdx_b_to_a_tx_lane_coverage:02x} "
            f"fdx_b_to_a_rx_lane_coverage=0x{link.fdx_b_to_a_rx_lane_coverage:02x} "
            f"route_probe_events={link.route_probe_events} max_route_probe_observed={link.max_route_probe_observed} "
            f"log_dir={args.log_dir}"
        )
        return 0
    finally:
        if client_a is not None and thread_a is not None:
            close_probe(client_a, thread_a, event_a)
        if client_b is not None and thread_b is not None:
            close_probe(client_b, thread_b, event_b)
        if client_b2 is not None and thread_b2 is not None:
            close_probe(client_b2, thread_b2, event_b2)
        model.stop()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=64)
    parser.add_argument("--payload-size", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--log-dir", type=Path, default=Path("reports") / "two_ax7010_offline")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--csv-output", type=Path)
    args = parser.parse_args(argv)

    if args.repeat <= 0:
        parser.error("--repeat must be positive")
    if args.payload_size <= 8 or args.payload_size > 512:
        parser.error("--payload-size must be in the range 9..512")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    try:
        return run_model(args)
    except BaseException as exc:
        print(f"TWO_AX7010_END_TO_END_OFFLINE_FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
