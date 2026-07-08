#!/usr/bin/env python3
"""Local RFCM protocol server used to exercise the PC acceptance flow offline."""

from __future__ import annotations

import argparse
import socket
import struct
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

try:
    import rf_comm_client as rf
except ImportError:  # pragma: no cover - useful when imported as a package
    from . import rf_comm_client as rf  # type: ignore


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
    """Small TCP implementation of the PS bridge protocol for offline tests."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        fail_tx: bool = False,
        rx_echo: bool = True,
        fragment_outgoing: bool = False,
        coalesce_tx_response: bool = False,
        drop_tx_response: bool = False,
        ready_file: Path | None = None,
        log_file: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.fail_tx = fail_tx
        self.rx_echo = rx_echo
        self.fragment_outgoing = fragment_outgoing
        self.coalesce_tx_response = coalesce_tx_response
        self.drop_tx_response = drop_tx_response
        self.ready_file = ready_file
        self.log_file = log_file
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
        self._log_lock = threading.Lock()

    def log(self, text: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
        if self.log_file is None:
            print(line, flush=True)
            return
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self._log_lock:
            with self.log_file.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def _write_ready(self) -> None:
        message = f"MOCK_RFCM_SERVER_READY host={self.host} port={self.port}"
        if self.ready_file is not None:
            self.ready_file.parent.mkdir(parents=True, exist_ok=True)
            self.ready_file.write_text(message + "\n", encoding="utf-8")
        self.log(message)

    def _send_raw(self, sock: socket.socket, payload: bytes) -> None:
        if not self.fragment_outgoing:
            sock.sendall(payload)
            return
        for idx in range(0, len(payload), 3):
            sock.sendall(payload[idx:idx + 3])
            time.sleep(0.001)

    def _send(self, sock: socket.socket, frame_type: int, seq: int, payload: bytes = b"") -> None:
        self._send_raw(sock, pack_frame(frame_type, seq, payload))

    def _status_payload(self) -> bytes:
        fields = (
            0x00000001,
            0x00000000,
            0x00000000,
            0x00000000,
            len(self.tx_payloads),
            len(self.tx_payloads) if self.rx_echo else 0,
            len(self.tx_payloads),
            0,
            len(self.tx_payloads) if self.rx_echo else 0,
            0,
            self.config_lane_mask,
            self.config_rx_lane_mask,
            0x04030201,
            0x08070605,
            0x0C0B0A09,
            0x100F0E0D,
        )
        return struct.pack("<16I", *fields)

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

    def _handle_config(self, sock: socket.socket, frame: rf.Frame) -> None:
        if len(frame.payload) not in (8, 12, 16):
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
            return
        if (frame.payload[0] & rf.CONFIG_RX_LANE_MASK) and len(frame.payload) < 12:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
            return
        if (frame.payload[0] & rf.CONFIG_MODE) and len(frame.payload) < 16:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_payload")
            return

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
            return
        if (mask & rf.CONFIG_MODE) and mode == rf.MODE_IR_PHYSICAL:
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE")
            return
        if (mask & rf.CONFIG_MODE) and mode not in (
            rf.MODE_NETWORK_MEMORY_ECHO,
            rf.MODE_PSPL_SYNTH_LOOPBACK,
        ):
            self._send(sock, rf.FRAME_ERROR, frame.seq, b"bad_config_mode")
            return
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
        self.log(
            "CONFIG "
            f"enable={self.config_enable} session=0x{self.config_session:04x} "
            f"tx_lane_mask=0x{self.config_lane_mask:08x} "
            f"rx_lane_mask=0x{self.config_rx_lane_mask:08x} "
            f"mode={rf.MODE_LABELS.get(self.mode, str(self.mode))}"
        )
        self._send(sock, rf.FRAME_ACK, frame.seq, rf.MODE_LABELS.get(self.mode, "unknown").encode("ascii"))

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
            self._send(sock, rf.FRAME_ACK, frame.seq, b"BUILD_ID rf_comm_ps_bridge_mock")
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
                self._send(sock, rf.FRAME_ACK, frame.seq, b"rf_comm_ps_bridge_mock")
            elif frame.frame_type == rf.FRAME_STATUS_REQ:
                self._send(sock, rf.FRAME_STATUS_RSP, frame.seq, self._status_payload())
            elif frame.frame_type == rf.FRAME_CLEAR:
                self._send(sock, rf.FRAME_ACK, frame.seq, b"cleared")
            elif frame.frame_type == rf.FRAME_CONFIG:
                self._handle_config(sock, frame)
            elif frame.frame_type == rf.FRAME_COMMAND:
                self._handle_command(sock, frame)
            elif frame.frame_type == rf.FRAME_TX_DATA:
                self.tx_payloads.append(frame.payload)
                self.log(f"TX_DATA seq={frame.seq} len={len(frame.payload)}")
                if self.drop_tx_response:
                    continue
                if self.fail_tx:
                    self._send(sock, rf.FRAME_ERROR, frame.seq, b"ir_tx_failed")
                    continue
                ack_text = (
                    b"pspl_synth_started"
                    if self.mode == rf.MODE_PSPL_SYNTH_LOOPBACK else
                    b"memory_echo_done"
                )
                ack = pack_frame(rf.FRAME_ACK, frame.seq, ack_text)
                rx_data = (
                    pack_frame(rf.FRAME_RX_DATA, 0x8000 + len(self.tx_payloads), frame.payload)
                    if self.rx_echo else b""
                )
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
                server.bind((self.host, self.port))
                server.listen()
                server.settimeout(0.1)
                self._server = server
                self.port = server.getsockname()[1]
                self._write_ready()
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
                    self.connections += 1
                    self.log(f"ACCEPT addr={addr[0]}:{addr[1]} connections={self.connections}")
                    with sock:
                        sock.settimeout(2.0)
                        self._handle_client(sock)
                    self.log(f"CLOSE connections={self.connections}")
        except BaseException as exc:
            if not self.stop_event.is_set():
                self.errors.append(exc)
                self.log(f"ERROR {exc!r}")
            self.ready.set()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=15001)
    parser.add_argument("--ready-file", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--duration", type=float, default=0.0)
    parser.add_argument("--fail-tx", action="store_true")
    parser.add_argument("--no-rx-echo", action="store_true")
    parser.add_argument("--fragment-outgoing", action="store_true")
    parser.add_argument("--coalesce-tx-response", action="store_true")
    parser.add_argument("--drop-tx-response", action="store_true")
    args = parser.parse_args(argv)

    server = MockRFCMServer(
        host=args.host,
        port=args.port,
        fail_tx=args.fail_tx,
        rx_echo=not args.no_rx_echo,
        fragment_outgoing=args.fragment_outgoing,
        coalesce_tx_response=args.coalesce_tx_response,
        drop_tx_response=args.drop_tx_response,
        ready_file=args.ready_file,
        log_file=args.log,
    )
    server.start()
    started = time.monotonic()
    try:
        while True:
            if args.duration > 0.0 and (time.monotonic() - started) >= args.duration:
                break
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
