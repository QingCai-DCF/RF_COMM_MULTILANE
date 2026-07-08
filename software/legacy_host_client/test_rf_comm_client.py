#!/usr/bin/env python3
"""Offline protocol tests for the RF_COMM PC-side TCP client."""

from __future__ import annotations

import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from contextlib import suppress
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_acceptance_log as ral
import mock_rfcm_server as mock
import rf_comm_client as rf


def pack_frame(frame_type: int, seq: int, payload: bytes = b"") -> bytes:
    return rf.HEADER.pack(rf.MAGIC, rf.VERSION, frame_type, seq, len(payload)) + payload


def recv_exact(sock: socket.socket, nbytes: int) -> bytes | None:
    data = bytearray()
    while len(data) < nbytes:
        try:
            chunk = sock.recv(nbytes - len(data))
        except socket.timeout:
            continue
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def recv_frame(sock: socket.socket) -> rf.Frame | None:
    header = recv_exact(sock, rf.HEADER.size)
    if header is None:
        return None
    magic, version, frame_type, seq, length = rf.HEADER.unpack(header)
    if magic != rf.MAGIC or version != rf.VERSION or length > rf.MAX_FRAME_PAYLOAD:
        raise RuntimeError("mock server protocol desync")
    payload = recv_exact(sock, length)
    if payload is None:
        return None
    return rf.Frame(frame_type, seq, payload)


class MockRFCMServer:
    def __init__(self, *, fail_tx: bool = False, rx_echo: bool = True,
                 fragment_outgoing: bool = False,
                 coalesce_tx_response: bool = False,
                 drop_tx_response: bool = False) -> None:
        self.fail_tx = fail_tx
        self.rx_echo = rx_echo
        self.fragment_outgoing = fragment_outgoing
        self.coalesce_tx_response = coalesce_tx_response
        self.drop_tx_response = drop_tx_response
        self.ready = threading.Event()
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.connections = 0
        self.tx_payloads: list[bytes] = []
        self.config_enable = 1
        self.config_session = 1
        self.config_lane_mask = 1
        self.config_rx_lane_mask = 1
        self.mode = rf.MODE_NETWORK_MEMORY_ECHO
        self.errors: list[BaseException] = []
        self._server: socket.socket | None = None
        self.port = 0

    def _send_raw(self, sock: socket.socket, payload: bytes) -> None:
        if not self.fragment_outgoing:
            sock.sendall(payload)
            return
        for idx in range(0, len(payload), 3):
            sock.sendall(payload[idx:idx + 3])
            time.sleep(0.001)

    def start(self) -> None:
        self.thread.start()
        if not self.ready.wait(5.0):
            raise RuntimeError("mock server did not start")

    def stop(self) -> None:
        self.stop_event.set()
        if self._server is not None:
            with suppress(OSError):
                self._server.close()
        self.thread.join(timeout=2.0)
        if self.errors:
            raise AssertionError(f"mock server errors: {self.errors!r}")

    def _send(self, sock: socket.socket, frame_type: int, seq: int, payload: bytes = b"") -> None:
        self._send_raw(sock, pack_frame(frame_type, seq, payload))

    def _status_payload(self) -> bytes:
        fields = (
            0x00000001,  # status
            0x00000002,  # sticky
            0x00000004,  # pending
            0x00000008,  # inflight
            0x00000010,  # acked
            0x00000020,  # rx_bitmap
            len(self.tx_payloads),
            0,
            len(self.tx_payloads) if self.rx_echo else 0,
            0,
            self.config_lane_mask,
            self.config_rx_lane_mask,
            0x04030201,
            0x08070605,
            0x0c0b0a09,
            0x100f0e0d,
        )
        return struct.pack("<16I", *fields)

    def _handle_command(self, sock: socket.socket, frame: rf.Frame) -> None:
        try:
            command = frame.payload.decode("ascii").strip()
        except UnicodeDecodeError:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_BAD_ARG")
            return

        if not command:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_BAD_ARG")
        elif command == "PING":
            self._send(sock, rf.FRAME_ACK, frame.seq, b"PONG")
        elif command == "GET_VERSION":
            self._send(sock, rf.FRAME_ACK, frame.seq, b"VERSION 1")
        elif command in ("GET_BUILD_ID", "READ build_id"):
            self._send(sock, rf.FRAME_ACK, frame.seq, b"BUILD_ID rf_comm_ps_bridge")
        elif command in ("STATUS", "READ counters", "READ pspl_status"):
            self._send(sock, rf.FRAME_STATUS_RSP, frame.seq, self._status_payload())
        elif command == "READ network_status":
            self._send(sock, rf.FRAME_ACK, frame.seq, b"network_status tcp_connected=1 port=5001")
        elif command.startswith("CONFIG payload_bytes "):
            value = command.removeprefix("CONFIG payload_bytes ")
            if not value.isdigit() or int(value) <= 0 or int(value) > rf.MAX_FRAME_PAYLOAD:
                self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_BAD_ARG")
            else:
                self._send(sock, rf.FRAME_ACK, frame.seq, b"payload_bytes_accepted")
        elif command == "CONFIG mode network_memory_echo":
            self.mode = rf.MODE_NETWORK_MEMORY_ECHO
            self.config_enable = 0
            self._send(sock, rf.FRAME_ACK, frame.seq, b"network_memory_echo")
        elif command == "CONFIG mode pspl_synth_loopback":
            self.mode = rf.MODE_PSPL_SYNTH_LOOPBACK
            self.config_enable = 0
            self._send(sock, rf.FRAME_ACK, frame.seq, b"pspl_synth_loopback")
        elif command in (
            "CONFIG mode ir_physical",
            "START ir_tx",
            "START 2lane",
            "START ir_physical",
        ):
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE")
        elif command in ("CLEAR", "CLEAR counters", "CLEAR sticky"):
            self.tx_payloads.clear()
            self._send(sock, rf.FRAME_ACK, frame.seq, b"cleared")
        elif command == "START":
            self.config_enable = 0
            self._send(sock, rf.FRAME_ACK, frame.seq, b"started_network_mode")
        elif command == "STOP":
            self.config_enable = 0
            self._send(sock, rf.FRAME_ACK, frame.seq, b"stopped")
        elif command == "SHUTDOWN_SAFE":
            self.config_enable = 0
            self._send(sock, rf.FRAME_ACK, frame.seq, b"shutdown_safe")
        else:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_UNKNOWN_CMD")

    def _handle_client(self, sock: socket.socket) -> None:
        self._send(sock, rf.FRAME_ACK, 0, b"connected")
        while not self.stop_event.is_set():
            try:
                frame = recv_frame(sock)
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
                if len(frame.payload) not in (8, 12, 16):
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
                    continue
                if (frame.payload[0] & rf.CONFIG_RX_LANE_MASK) and len(frame.payload) < 12:
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
                    continue
                if (frame.payload[0] & rf.CONFIG_MODE) and len(frame.payload) < 16:
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
                    continue
                mask, enable, session, lane_mask = struct.unpack("<BBHI", frame.payload[:8])
                rx_lane_mask = (
                    struct.unpack("<I", frame.payload[8:12])[0]
                    if len(frame.payload) >= 12 else lane_mask
                )
                mode = (
                    struct.unpack("<I", frame.payload[12:16])[0]
                    if len(frame.payload) >= 16 else self.mode
                )
                valid_mask = (
                    rf.CONFIG_ENABLE | rf.CONFIG_SESSION | rf.CONFIG_LANE_MASK |
                    rf.CONFIG_RX_LANE_MASK | rf.CONFIG_MODE
                )
                if mask & ~valid_mask:
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_mask")
                    continue
                if (mask & rf.CONFIG_MODE) and mode == rf.MODE_IR_PHYSICAL:
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE")
                    continue
                if (mask & rf.CONFIG_MODE) and mode not in (
                    rf.MODE_NETWORK_MEMORY_ECHO,
                    rf.MODE_PSPL_SYNTH_LOOPBACK,
                ):
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_mode")
                    continue
                if mask & rf.CONFIG_ENABLE:
                    self.config_enable = 1 if enable else 0
                if mask & rf.CONFIG_SESSION:
                    self.config_session = session
                if mask & rf.CONFIG_LANE_MASK:
                    self.config_lane_mask = lane_mask
                    if not (mask & rf.CONFIG_RX_LANE_MASK):
                        self.config_rx_lane_mask = lane_mask
                if mask & rf.CONFIG_RX_LANE_MASK:
                    self.config_rx_lane_mask = rx_lane_mask
                if mask & rf.CONFIG_MODE:
                    self.mode = mode
                self._send(sock, rf.FRAME_ACK, frame.seq, rf.MODE_LABELS.get(self.mode, "unknown").encode("ascii"))
            elif frame.frame_type == rf.FRAME_COMMAND:
                self._handle_command(sock, frame)
            elif frame.frame_type == rf.FRAME_TX_DATA:
                self.tx_payloads.append(frame.payload)
                if self.drop_tx_response:
                    continue
                if self.fail_tx:
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"ir_tx_failed")
                else:
                    ack = pack_frame(
                        rf.FRAME_ACK,
                        frame.seq,
                        b"pspl_synth_started" if self.mode == rf.MODE_PSPL_SYNTH_LOOPBACK else b"memory_echo_done",
                    )
                    rx_data = pack_frame(
                        rf.FRAME_RX_DATA,
                        0x8000 + len(self.tx_payloads),
                        frame.payload,
                    ) if self.rx_echo else b""
                    if self.coalesce_tx_response and rx_data:
                        self._send_raw(sock, ack + rx_data)
                    else:
                        self._send_raw(sock, ack)
                        if rx_data:
                            self._send_raw(sock, rx_data)
            else:
                self._send(sock, rf.FRAME_ERROR, frame.seq, b"unknown_frame_type")

    def _run(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind(("127.0.0.1", 0))
                server.listen()
                server.settimeout(0.1)
                self._server = server
                self.port = server.getsockname()[1]
                self.ready.set()
                while not self.stop_event.is_set():
                    try:
                        sock, _ = server.accept()
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


class RFClientOfflineTests(unittest.TestCase):
    def wait_for_pending_empty(self, stats: rf.Stats, timeout: float = 2.0) -> bool:
        return stats.wait_for_all_pending(timeout)

    def run_payload_exchange(self, port: int, payload: bytes) -> rf.Stats:
        client = rf.RFClient("127.0.0.1", port, timeout=2.0)
        stats = rf.Stats()
        client.connect()
        rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
        rx_thread.start()
        try:
            rf.send_tracked(client, stats, rf.FRAME_TX_DATA, payload)
            deadline = time.monotonic() + 3.0
            with stats.condition:
                while (
                    (stats.pending_tx_data_count() > 0 or stats.rx_data_bytes < len(payload))
                    and time.monotonic() < deadline
                ):
                    stats.condition.wait(0.05)
            self.assertEqual(stats.acked_tx_data, 1)
            self.assertEqual(stats.failed_tx_data, 0)
            self.assertEqual(stats.error_frames, 0)
            self.assertEqual(stats.pending_tx_data_count(), 0)
            self.assertEqual(stats.rx_data_frames, 1)
            self.assertEqual(stats.rx_data_bytes, len(payload))
            return stats
        finally:
            client.close()
            rx_thread.join(timeout=1.0)

    def test_status_tx_ack_rx_data_and_summary(self) -> None:
        server = MockRFCMServer()
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, rf.FRAME_HELLO)
            rf.send_tracked(client, stats, rf.FRAME_STATUS_REQ)
            self.assertTrue(self.wait_for_pending_empty(stats, timeout=5.0))

            sent = 0
            sent_bytes = 0
            for index in range(3):
                payload = rf.make_payload(index, 16)
                rf.send_tracked(client, stats, rf.FRAME_TX_DATA, payload)
                sent += 1
                sent_bytes += len(payload)

                deadline = time.monotonic() + 5.0
                with stats.condition:
                    while (
                        (stats.pending_tx_data_count() > 0 or stats.rx_data_frames < sent)
                        and time.monotonic() < deadline
                    ):
                        stats.condition.wait(0.05)
                self.assertEqual(stats.pending_tx_data_count(), 0)
            self.assertEqual(sent, 3)
            self.assertEqual(sent_bytes, 48)
            self.assertEqual(stats.acked_tx_data, 3)
            self.assertEqual(stats.failed_tx_data, 0)
            self.assertGreaterEqual(stats.status_frames, 1)
            self.assertEqual(stats.rx_data_frames, 3)
            self.assertEqual(stats.rx_data_bytes, 48)
            self.assertIn("tx_packets=3", stats.summary(max(time.monotonic() - stats.started_at, 1e-6)))
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_payload_exchange_still_works_after_reconnect(self) -> None:
        server = MockRFCMServer()
        server.start()
        try:
            first = self.run_payload_exchange(server.port, b"first_after_connect")
            second = self.run_payload_exchange(server.port, b"second_after_reconnect")
            self.assertEqual(server.connections, 2)
            self.assertEqual(server.tx_payloads, [b"first_after_connect", b"second_after_reconnect"])
            self.assertEqual(rf.evaluate_acceptance(first, 1.0, require_clean=True, min_rx_frames=1), [])
            self.assertEqual(rf.evaluate_acceptance(second, 1.0, require_clean=True, min_rx_frames=1), [])
        finally:
            server.stop()

    def test_standalone_mock_server_module_supports_acceptance_flow(self) -> None:
        server = mock.MockRFCMServer()
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, rf.FRAME_HELLO)
            rf.send_tracked(
                client,
                stats,
                rf.FRAME_CONFIG,
                rf.make_config_payload(enable=1, session=0x1234, lane_mask=0x1),
            )
            self.assertTrue(self.wait_for_pending_empty(stats, timeout=5.0))
            sent, sent_bytes = rf.run_repeated_tx(
                client,
                stats,
                count=4,
                duration=None,
                payload_size=24,
                interval=0.0,
                status_interval=0.0,
                window=1,
                ack_timeout=2.0,
                wait_ack=True,
            )
            deadline = time.monotonic() + 3.0
            with stats.condition:
                while stats.rx_data_frames < 4 and time.monotonic() < deadline:
                    stats.condition.wait(0.05)
            self.assertEqual(sent, 4)
            self.assertEqual(sent_bytes, 96)
            self.assertEqual(stats.acked_tx_data, 4)
            self.assertEqual(stats.rx_data_frames, 4)
            self.assertEqual(stats.rx_data_bytes, 96)
            self.assertEqual(server.config_session, 0x1234)
            self.assertEqual(server.config_lane_mask, 0x1)
            self.assertEqual(
                rf.evaluate_acceptance(stats, 1.0, require_clean=True, min_rx_frames=4),
                [],
            )
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_unknown_command_reports_error_and_clears_pending(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, 0x7E, b"bad")
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.error_frames, 1)
            self.assertEqual(stats.last_error, "unknown_frame_type")
            self.assertEqual(stats.pending_tx_data_count(), 0)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_bad_config_reports_error_and_clears_pending(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            bad_payload = struct.pack("<BBHI", rf.CONFIG_RX_LANE_MASK, 0, 0, 0x00000003)
            rf.send_tracked(client, stats, rf.FRAME_CONFIG, bad_payload)
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.error_frames, 1)
            self.assertEqual(stats.last_error, "bad_config_payload")
            self.assertEqual(stats.pending_tx_data_count(), 0)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_acceptance_passes_clean_mock_traffic(self) -> None:
        server = MockRFCMServer()
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.run_repeated_tx(
                client,
                stats,
                count=2,
                duration=None,
                payload_size=16,
                interval=0.0,
                status_interval=0.0,
                window=1,
                ack_timeout=2.0,
                wait_ack=True,
            )
            deadline = time.monotonic() + 2.0
            with stats.condition:
                while stats.rx_data_frames < 2 and time.monotonic() < deadline:
                    stats.condition.wait(0.05)
            failures = rf.evaluate_acceptance(
                stats,
                max(time.monotonic() - stats.started_at, 1e-6),
                require_clean=True,
                min_tx_mbps=0.0,
                min_rx_frames=2,
            )
            self.assertEqual(failures, [])
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_segmented_app_payload_sends_8192_bytes_over_512_byte_frames(self) -> None:
        server = MockRFCMServer()
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            sent, sent_bytes, sent_fragments = rf.run_repeated_app_tx(
                client,
                stats,
                count=2,
                duration=None,
                app_payload_size=8192,
                frame_payload_size=rf.MAX_FRAME_PAYLOAD,
                interval=0.0,
                status_interval=0.0,
                window=1,
                ack_timeout=2.0,
                wait_ack=True,
            )
            deadline = time.monotonic() + 5.0
            with stats.condition:
                while stats.rx_data_frames < 32 and time.monotonic() < deadline:
                    stats.condition.wait(0.05)
            self.assertEqual(sent, 2)
            self.assertEqual(sent_bytes, 16384)
            self.assertEqual(sent_fragments, 32)
            self.assertEqual(stats.app_tx_packets, 2)
            self.assertEqual(stats.app_tx_bytes, 16384)
            self.assertEqual(stats.app_tx_fragments, 32)
            self.assertEqual(len(server.tx_payloads), 32)
            self.assertTrue(all(len(payload) <= rf.MAX_FRAME_PAYLOAD for payload in server.tx_payloads))
            self.assertEqual(stats.acked_tx_data, 32)
            self.assertEqual(stats.rx_data_frames, 32)
            self.assertEqual(stats.rx_data_bytes, 16384)
            self.assertEqual(stats.payload_mismatch, 0)
            self.assertIn("app_tx_packets=2", stats.summary(1.0))
            self.assertEqual(
                rf.evaluate_acceptance(stats, 1.0, require_clean=True, min_rx_frames=32),
                [],
            )
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_acceptance_reports_timeout_pending_and_threshold_failures(self) -> None:
        stats = rf.Stats()
        stats.tx_data_bytes = 8
        stats.ack_timeouts = 1
        stats.pending[7] = (rf.FRAME_TX_DATA, time.monotonic())

        failures = rf.evaluate_acceptance(
            stats,
            elapsed=1.0,
            require_clean=True,
            min_tx_mbps=1.0,
            min_rx_frames=1,
        )

        self.assertIn("ack_timeouts=1", failures)
        self.assertIn("pending_frames=1", failures)
        self.assertIn("pending_tx=1", failures)
        self.assertTrue(any(item.startswith("tx_mbps=") for item in failures))
        self.assertIn("rx_data_frames=0<min_rx_frames=1", failures)

    def test_csv_log_contains_summary_and_acceptance_markers(self) -> None:
        server = MockRFCMServer()
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                csv_path = Path(tmp_dir) / "acceptance.csv"
                rc = rf.main([
                    "--host", "127.0.0.1",
                    "--port", str(server.port),
                    "--repeat", "2",
                    "--payload-size", "16",
                    "--window", "1",
                    "--ack-timeout", "2",
                    "--require-clean",
                    "--min-rx-frames", "2",
                    "--csv-log", str(csv_path),
                    "--quiet",
                ])
                self.assertEqual(rc, 0)
                analysis = ral.analyze_csv(csv_path)
                self.assertIn("SENT_SUMMARY", analysis.markers)
                self.assertIn("SUMMARY", analysis.markers)
                self.assertIn("ACCEPTANCE_PASS", analysis.markers)
                failures = ral.evaluate_log(
                    analysis,
                    require_pass=True,
                    min_duration=0.0,
                    max_errors=0,
                    min_status_frames=0,
                    min_rx_frames=2,
                    min_tx_mbps=0.0,
                    min_rx_mbps=None,
                )
                self.assertEqual(failures, [])
        finally:
            server.stop()

    def test_csv_log_records_segmented_app_payload_summary(self) -> None:
        server = MockRFCMServer()
        server.start()
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                csv_path = Path(tmp_dir) / "segmented_acceptance.csv"
                rc = rf.main([
                    "--host", "127.0.0.1",
                    "--port", str(server.port),
                    "--repeat", "2",
                    "--app-payload-size", "1024",
                    "--payload-size", "256",
                    "--window", "1",
                    "--ack-timeout", "2",
                    "--require-clean",
                    "--min-rx-frames", "8",
                    "--csv-log", str(csv_path),
                    "--quiet",
                ])
                self.assertEqual(rc, 0)
                analysis = ral.analyze_csv(csv_path)
                self.assertEqual(analysis.sent_summary["sent_packets"], "2")
                self.assertEqual(analysis.sent_summary["sent_bytes"], "2048")
                self.assertEqual(analysis.sent_summary["fragment_frames"], "8")
                self.assertEqual(analysis.sent_summary["frame_payload_size"], "256")
                self.assertEqual(analysis.sent_summary["app_payload_size"], "1024")
                self.assertEqual(analysis.summary["app_tx_packets"], "2")
                self.assertEqual(analysis.summary["app_tx_bytes"], "2048")
                self.assertEqual(analysis.summary["app_tx_fragments"], "8")
                self.assertEqual(
                    ral.evaluate_log(
                        analysis,
                        require_pass=True,
                        min_duration=0.0,
                        max_errors=0,
                        min_status_frames=0,
                        min_rx_frames=8,
                        min_tx_mbps=0.0,
                        min_rx_mbps=None,
                    ),
                    [],
                )
        finally:
            server.stop()

    def test_acceptance_log_analysis_reports_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "bad.csv"
            csv_path.write_text(
                "time_s,type,seq,payload_len,detail\n"
                "0.000000,ERROR,7,9,ERROR seq=7 ir_tx_failed\n"
                "0.100000,SUMMARY,,,summary elapsed_s=0.100 errors=1 status=0 rx_data=0 tx_mbps=0.000000 rx_mbps=0.000000\n",
                encoding="utf-8",
            )
            analysis = ral.analyze_csv(csv_path)
            failures = ral.evaluate_log(
                analysis,
                require_pass=True,
                min_duration=1.0,
                max_errors=0,
                min_status_frames=1,
                min_rx_frames=1,
                min_tx_mbps=0.1,
                min_rx_mbps=0.1,
            )
            self.assertTrue(any("ACCEPTANCE_PASS marker missing" in item for item in failures))
            self.assertTrue(any(item.startswith("duration_s=") for item in failures))
            self.assertIn("errors=1>max_errors=0", failures)
            self.assertIn("status_frames=0<min_status_frames=1", failures)
            self.assertIn("rx_data_frames=0<min_rx_frames=1", failures)

    def test_config_command_updates_link_settings(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            payload = rf.make_config_payload(enable=0, session=0x1234, lane_mask=0x00000003)
            rf.send_tracked(client, stats, rf.FRAME_CONFIG, payload)
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.ack_frames, 2)  # connection banner + CONFIG ACK
            self.assertEqual(server.config_enable, 0)
            self.assertEqual(server.config_session, 0x1234)
            self.assertEqual(server.config_lane_mask, 0x00000003)
            self.assertEqual(server.config_rx_lane_mask, 0x00000003)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_config_command_updates_independent_rx_lane_mask(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            payload = rf.make_config_payload(tx_lane_mask=0x00000003, rx_lane_mask=0x0000000c)
            self.assertEqual(len(payload), 12)
            rf.send_tracked(client, stats, rf.FRAME_CONFIG, payload)
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.ack_frames, 2)  # connection banner + CONFIG ACK
            self.assertEqual(server.config_lane_mask, 0x00000003)
            self.assertEqual(server.config_rx_lane_mask, 0x0000000c)
            status = rf.format_frame(rf.Frame(rf.FRAME_STATUS_RSP, 7, server._status_payload()))
            decoded = rf.parse_status_payload(server._status_payload())
            self.assertIn("tx_lane_mask=0x00000003", status)
            self.assertIn("rx_lane_mask=0x0000000c", status)
            self.assertIn("tx_lane_count=0x04030201", status)
            self.assertIn("rx_lane_good_count=0x08070605", status)
            self.assertIn("rx_lane_crc_count=0x0c0b0a09", status)
            self.assertIn("rx_lane_err_count=0x100f0e0d", status)
            self.assertEqual(decoded["tx_lane_mask"], 0x00000003)
            self.assertEqual(decoded["rx_lane_mask"], 0x0000000c)
            self.assertEqual(decoded["tx_lane_count"], 0x04030201)
            self.assertEqual(decoded["rx_lane_good_count"], 0x08070605)
            self.assertEqual(decoded["rx_lane_crc_count"], 0x0C0B0A09)
            self.assertEqual(decoded["rx_lane_err_count"], 0x100F0E0D)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_config_mode_selects_n03_safe_paths(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            payload = rf.make_config_payload(mode="pspl_synth_loopback")
            self.assertEqual(len(payload), 16)
            self.assertEqual(payload[0], rf.CONFIG_MODE)
            rf.send_tracked(client, stats, rf.FRAME_CONFIG, payload)
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(server.mode, rf.MODE_PSPL_SYNTH_LOOPBACK)
            self.assertEqual(stats.error_frames, 0)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_ir_physical_mode_is_deferred_for_n03(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(
                client,
                stats,
                rf.FRAME_CONFIG,
                rf.make_config_payload(mode="ir_physical"),
            )
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.error_frames, 1)
            self.assertEqual(stats.last_error, "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE")
            self.assertEqual(server.mode, rf.MODE_NETWORK_MEMORY_ECHO)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_n03_ascii_command_protocol_covers_safe_commands(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            for command in (
                "PING",
                "GET_VERSION",
                "GET_BUILD_ID",
                "READ network_status",
                "READ counters",
                "CONFIG payload_bytes 64",
                "CONFIG mode pspl_synth_loopback",
                "START",
                "STOP",
                "SHUTDOWN_SAFE",
            ):
                rf.send_tracked(client, stats, rf.FRAME_COMMAND, command.encode("ascii"))
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.error_frames, 0)
            self.assertGreaterEqual(stats.ack_frames, 10)
            self.assertGreaterEqual(stats.status_frames, 1)
            self.assertEqual(server.mode, rf.MODE_PSPL_SYNTH_LOOPBACK)
            self.assertEqual(server.config_enable, 0)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_n03_ascii_command_protocol_rejects_ir_and_unknown_commands(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, rf.FRAME_COMMAND, b"START ir_tx")
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.error_frames, 1)
            self.assertEqual(stats.last_error, "ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE")
            rf.send_tracked(client, stats, rf.FRAME_COMMAND, b"UNKNOWN_CMD")
            self.assertTrue(self.wait_for_pending_empty(stats))
            self.assertEqual(stats.error_frames, 2)
            self.assertEqual(stats.last_error, "ERR_UNKNOWN_CMD")
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_n03_ascii_command_protocol_rejects_bad_payload_sizes(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            for command in (b"CONFIG payload_bytes 0", b"CONFIG payload_bytes too_large"):
                rf.send_tracked(client, stats, rf.FRAME_COMMAND, command)
                self.assertTrue(self.wait_for_pending_empty(stats))
                self.assertEqual(stats.last_error, "ERR_BAD_ARG")
            self.assertEqual(stats.error_frames, 2)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_payload_mismatch_is_a_clean_acceptance_failure(self) -> None:
        stats = rf.Stats()
        stats.payload_mismatch = 1
        failures = rf.evaluate_acceptance(stats, elapsed=1.0, require_clean=True)
        self.assertIn("payload_mismatch=1", failures)

    def test_status_parser_accepts_legacy_48_byte_payload(self) -> None:
        fields = (
            0x00000001,
            0x00000002,
            0x00000004,
            0x00000008,
            0x00000010,
            0x00000020,
            3,
            0,
            2,
            0,
            0x00000003,
            0x0000000c,
        )
        status = rf.format_frame(
            rf.Frame(rf.FRAME_STATUS_RSP, 9, struct.pack("<12I", *fields))
        )
        decoded = rf.parse_status_payload(struct.pack("<12I", *fields))
        self.assertIn("tx_lane_mask=0x00000003", status)
        self.assertIn("rx_lane_mask=0x0000000c", status)
        self.assertNotIn("tx_lane_count", status)
        self.assertEqual(decoded["tx_lane_mask"], 0x00000003)
        self.assertEqual(decoded["rx_lane_mask"], 0x0000000C)
        self.assertNotIn("tx_lane_count", decoded)

    def test_status_parser_reports_malformed_lengths(self) -> None:
        payloads = (
            b"",
            struct.pack("<9I", *range(9)),
            struct.pack("<11I", *range(11)),
            struct.pack("<13I", *range(13)),
            struct.pack("<15I", *range(15)),
        )
        for payload in payloads:
            with self.subTest(length=len(payload)):
                self.assertEqual(rf.parse_status_payload(payload), {})
                rendered = rf.format_frame(rf.Frame(rf.FRAME_STATUS_RSP, 3, payload))
                self.assertIn(f"malformed_status_payload_len={len(payload)}", rendered)
                self.assertIn("data=", rendered)

    def test_final_target_lane_mask_config_payloads(self) -> None:
        half_duplex_payload = rf.make_config_payload(enable=1, session=0x1234, lane_mask=0x000000FF)
        full_duplex_payload = rf.make_config_payload(
            enable=1,
            session=0x1234,
            tx_lane_mask=0x0000000F,
            rx_lane_mask=0x000000F0,
        )
        self.assertEqual(len(half_duplex_payload), 8)
        self.assertEqual(len(full_duplex_payload), 12)
        self.assertEqual(half_duplex_payload[0], rf.CONFIG_ENABLE | rf.CONFIG_SESSION | rf.CONFIG_LANE_MASK)
        self.assertEqual(
            full_duplex_payload[0],
            rf.CONFIG_ENABLE | rf.CONFIG_SESSION | rf.CONFIG_LANE_MASK | rf.CONFIG_RX_LANE_MASK,
        )
        self.assertEqual(struct.unpack("<I", half_duplex_payload[4:8])[0], 0x000000FF)
        self.assertEqual(struct.unpack("<I", full_duplex_payload[4:8])[0], 0x0000000F)
        self.assertEqual(struct.unpack("<I", full_duplex_payload[8:12])[0], 0x000000F0)

    def test_fragmented_and_coalesced_tcp_frames(self) -> None:
        server = MockRFCMServer(fragment_outgoing=True, coalesce_tx_response=True)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, rf.FRAME_TX_DATA, b"split_and_glued")
            deadline = time.monotonic() + 2.0
            with stats.condition:
                while (stats.rx_data_frames < 1 or stats.pending_tx_data_count() > 0) and time.monotonic() < deadline:
                    stats.condition.wait(0.05)
            self.assertEqual(server.tx_payloads, [b"split_and_glued"])
            self.assertEqual(stats.acked_tx_data, 1)
            self.assertEqual(stats.rx_data_frames, 1)
            self.assertEqual(stats.rx_data_bytes, len(b"split_and_glued"))
            self.assertEqual(stats.pending_tx_data_count(), 0)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_missing_tx_ack_counts_timeout_and_keeps_pending_frame(self) -> None:
        server = MockRFCMServer(rx_echo=False, drop_tx_response=True)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, rf.FRAME_TX_DATA, b"ack_will_not_arrive")
            self.assertFalse(stats.wait_for_all_tx_data(0.25))
            self.assertEqual(server.tx_payloads, [b"ack_will_not_arrive"])
            self.assertEqual(stats.ack_timeouts, 1)
            self.assertEqual(stats.acked_tx_data, 0)
            self.assertEqual(stats.failed_tx_data, 0)
            self.assertEqual(stats.pending_tx_data_count(), 1)
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_tx_error_marks_failed_data(self) -> None:
        server = MockRFCMServer(fail_tx=True, rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        stats = rf.Stats()
        try:
            client.connect()
            rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
            rx_thread.start()
            rf.send_tracked(client, stats, rf.FRAME_TX_DATA, b"will_fail")
            self.assertTrue(stats.wait_for_all_tx_data(2.0))
            self.assertEqual(stats.acked_tx_data, 0)
            self.assertEqual(stats.failed_tx_data, 1)
            self.assertEqual(stats.error_frames, 1)
            self.assertEqual(stats.last_error, "ir_tx_failed")
        finally:
            client.close()
            with suppress(UnboundLocalError):
                rx_thread.join(timeout=1.0)
            server.stop()

    def test_payload_limit_rejects_oversize_tx_frame(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        client = rf.RFClient("127.0.0.1", server.port, timeout=2.0)
        try:
            client.connect()
            with self.assertRaises(ValueError):
                client.send_frame(rf.FRAME_TX_DATA, bytes(rf.MAX_FRAME_PAYLOAD + 1))
            time.sleep(0.05)
            self.assertEqual(server.tx_payloads, [])
        finally:
            client.close()
            server.stop()

    def test_recv_frame_reports_protocol_desync_details(self) -> None:
        cases = (
            (
                rf.HEADER.pack(b"BADC", rf.VERSION, rf.FRAME_ACK, 1, 0),
                "bad magic",
            ),
            (
                rf.HEADER.pack(rf.MAGIC, rf.VERSION + 1, rf.FRAME_ACK, 1, 0),
                "unsupported version",
            ),
            (
                rf.HEADER.pack(
                    rf.MAGIC,
                    rf.VERSION,
                    rf.FRAME_ACK,
                    1,
                    rf.MAX_FRAME_PAYLOAD + 1,
                ),
                "payload length",
            ),
        )
        for packet, pattern in cases:
            with self.subTest(pattern=pattern):
                left, right = socket.socketpair()
                client = rf.RFClient("127.0.0.1", 0, timeout=0.2)
                try:
                    left.settimeout(0.2)
                    client.sock = left
                    client.running = True
                    right.sendall(packet)
                    with self.assertRaisesRegex(rf.ProtocolError, pattern):
                        client.recv_frame()
                finally:
                    client.close()
                    right.close()

    def test_generated_payload_limit_accepts_full_tcp_frame_size(self) -> None:
        self.assertEqual(rf.MAX_GENERATED_PAYLOAD, rf.MAX_FRAME_PAYLOAD)
        self.assertEqual(len(rf.make_payload(0, rf.MAX_FRAME_PAYLOAD)), rf.MAX_FRAME_PAYLOAD)

    def test_reconnect_cycles(self) -> None:
        server = MockRFCMServer(rx_echo=False)
        server.start()
        try:
            ok = rf.run_reconnect_cycles("127.0.0.1", server.port, cycles=2, delay=0.0, timeout=2.0)
            self.assertTrue(ok)
            self.assertEqual(server.connections, 2)
        finally:
            server.stop()

    def test_reconnect_cycles_require_payload_echo_when_requested(self) -> None:
        server = MockRFCMServer(rx_echo=True)
        server.start()
        try:
            ok = rf.run_reconnect_cycles(
                "127.0.0.1",
                server.port,
                cycles=3,
                delay=0.0,
                timeout=2.0,
                payload_size=32,
            )
            self.assertTrue(ok)
            self.assertEqual(server.connections, 3)
            self.assertEqual(len(server.tx_payloads), 3)
            self.assertTrue(all(len(payload) == 32 for payload in server.tx_payloads))
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
