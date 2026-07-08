#!/usr/bin/env python3
"""PC-side TCP client for the RF_COMM PS bridge."""

from __future__ import annotations

import argparse
import binascii
import csv
import os
import socket
import struct
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path


MAGIC = b"RFCM"
VERSION = 1
HEADER = struct.Struct("<4sBBHI")

FRAME_HELLO = 0x01
FRAME_STATUS_REQ = 0x02
FRAME_STATUS_RSP = 0x03
FRAME_ACK = 0x04
FRAME_ERROR = 0x05
FRAME_TX_DATA = 0x10
FRAME_RX_DATA = 0x11
FRAME_CLEAR = 0x20
FRAME_CONFIG = 0x21
FRAME_COMMAND = 0x22

CONFIG_ENABLE = 1 << 0
CONFIG_SESSION = 1 << 1
CONFIG_LANE_MASK = 1 << 2
CONFIG_RX_LANE_MASK = 1 << 3
CONFIG_MODE = 1 << 4

MODE_NETWORK_MEMORY_ECHO = 0
MODE_PSPL_SYNTH_LOOPBACK = 1
MODE_IR_PHYSICAL = 2

MODE_NAMES = {
    "network_memory_echo": MODE_NETWORK_MEMORY_ECHO,
    "memory_echo": MODE_NETWORK_MEMORY_ECHO,
    "pc_ps_memory_echo": MODE_NETWORK_MEMORY_ECHO,
    "pspl_synth_loopback": MODE_PSPL_SYNTH_LOOPBACK,
    "synthetic_loopback": MODE_PSPL_SYNTH_LOOPBACK,
    "ir_physical": MODE_IR_PHYSICAL,
}

MODE_LABELS = {
    MODE_NETWORK_MEMORY_ECHO: "network_memory_echo",
    MODE_PSPL_SYNTH_LOOPBACK: "pspl_synth_loopback",
    MODE_IR_PHYSICAL: "ir_physical",
}

MAX_FRAME_PAYLOAD = 512
MAX_PAYLOAD = MAX_FRAME_PAYLOAD
MAX_GENERATED_PAYLOAD = int(
    os.environ.get("RF_COMM_MAX_GENERATED_PAYLOAD", str(MAX_FRAME_PAYLOAD))
)
MAX_APP_PAYLOAD = int(os.environ.get("RF_COMM_MAX_APP_PAYLOAD", "8192"))

STATUS_FIELDS_BASE = (
    "status",
    "sticky",
    "tx_frag_pending",
    "tx_frag_inflight",
    "tx_frag_acked",
    "rx_recv_bitmap",
    "tx_ok",
    "tx_fail",
    "rx_ok",
    "rx_bad",
)
STATUS_FIELDS_LANE_MASKS = STATUS_FIELDS_BASE + (
    "tx_lane_mask",
    "rx_lane_mask",
)
STATUS_FIELDS_FULL = STATUS_FIELDS_LANE_MASKS + (
    "tx_lane_count",
    "rx_lane_good_count",
    "rx_lane_crc_count",
    "rx_lane_err_count",
)

TYPE_NAMES = {
    FRAME_HELLO: "HELLO",
    FRAME_STATUS_REQ: "STATUS_REQ",
    FRAME_STATUS_RSP: "STATUS_RSP",
    FRAME_ACK: "ACK",
    FRAME_ERROR: "ERROR",
    FRAME_TX_DATA: "TX_DATA",
    FRAME_RX_DATA: "RX_DATA",
    FRAME_CLEAR: "CLEAR",
    FRAME_CONFIG: "CONFIG",
    FRAME_COMMAND: "COMMAND",
}


class ProtocolError(RuntimeError):
    """Raised when a TCP peer violates the RFCM wire protocol."""


@dataclass
class Frame:
    frame_type: int
    seq: int
    payload: bytes


@dataclass
class Stats:
    started_at: float = field(default_factory=time.monotonic)
    tx_frames: int = 0
    tx_data_frames: int = 0
    tx_data_bytes: int = 0
    rx_frames: int = 0
    ack_frames: int = 0
    error_frames: int = 0
    rx_data_frames: int = 0
    rx_data_bytes: int = 0
    rx_payload_matches: int = 0
    payload_mismatch: int = 0
    status_frames: int = 0
    acked_tx_data: int = 0
    failed_tx_data: int = 0
    ack_timeouts: int = 0
    app_tx_packets: int = 0
    app_tx_bytes: int = 0
    app_tx_fragments: int = 0
    rtt_min: float | None = None
    rtt_max: float = 0.0
    rtt_sum: float = 0.0
    rtt_count: int = 0
    rtt_samples: list[float] = field(default_factory=list)
    tx_data_rtt_samples: list[float] = field(default_factory=list)
    last_error: str = ""
    pending: dict[int, tuple[int, float]] = field(default_factory=dict)
    expected_rx_payloads: deque[bytes] = field(default_factory=deque)
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.Lock())
    )

    def mark_sent(self, seq: int, frame_type: int, payload_len: int,
                  payload: bytes = b"") -> None:
        now = time.monotonic()
        with self.condition:
            self.tx_frames += 1
            if frame_type == FRAME_TX_DATA:
                self.tx_data_frames += 1
                self.tx_data_bytes += payload_len
                self.expected_rx_payloads.append(bytes(payload))
            self.pending[seq] = (frame_type, now)
            self.condition.notify_all()

    def mark_app_payload_sent(self, payload_len: int, fragment_count: int) -> None:
        with self.condition:
            self.app_tx_packets += 1
            self.app_tx_bytes += payload_len
            self.app_tx_fragments += fragment_count
            self.condition.notify_all()

    def mark_received(self, frame: Frame) -> None:
        now = time.monotonic()
        with self.condition:
            self.rx_frames += 1
            if frame.frame_type == FRAME_ACK:
                self.ack_frames += 1
            elif frame.frame_type == FRAME_ERROR:
                self.error_frames += 1
                self.last_error = frame.payload.decode("ascii", errors="replace")
            elif frame.frame_type == FRAME_RX_DATA:
                self.rx_data_frames += 1
                self.rx_data_bytes += len(frame.payload)
                if self.expected_rx_payloads:
                    expected = self.expected_rx_payloads.popleft()
                    if expected == frame.payload:
                        self.rx_payload_matches += 1
                    else:
                        self.payload_mismatch += 1
                        self.last_error = "payload_mismatch"
            elif frame.frame_type == FRAME_STATUS_RSP:
                self.status_frames += 1

            if frame.frame_type in (FRAME_ACK, FRAME_ERROR, FRAME_STATUS_RSP):
                pending = self.pending.pop(frame.seq, None)
                if pending is not None:
                    sent_type, sent_at = pending
                    rtt = now - sent_at
                    self.rtt_count += 1
                    self.rtt_sum += rtt
                    self.rtt_max = max(self.rtt_max, rtt)
                    self.rtt_min = rtt if self.rtt_min is None else min(self.rtt_min, rtt)
                    self.rtt_samples.append(rtt)
                    if sent_type == FRAME_TX_DATA:
                        self.tx_data_rtt_samples.append(rtt)
                    if sent_type == FRAME_TX_DATA and frame.frame_type == FRAME_ACK:
                        self.acked_tx_data += 1
                    elif sent_type == FRAME_TX_DATA and frame.frame_type == FRAME_ERROR:
                        self.failed_tx_data += 1
            self.condition.notify_all()

    def pending_tx_data_count(self) -> int:
        return sum(1 for frame_type, _ in self.pending.values()
                   if frame_type == FRAME_TX_DATA)

    def pending_count(self) -> int:
        return len(self.pending)

    def wait_for_all_pending(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self.condition.wait(remaining)
            return True

    def wait_for_tx_window(self, max_inflight: int, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.pending_tx_data_count() >= max_inflight:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.ack_timeouts += 1
                    return False
                self.condition.wait(remaining)
            return True

    def wait_for_all_tx_data(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.pending_tx_data_count() > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.ack_timeouts += self.pending_tx_data_count()
                    return False
                self.condition.wait(remaining)
            return True

    def summary(self, elapsed: float) -> str:
        safe_elapsed = max(elapsed, 1e-9)
        tx_mbps = (self.tx_data_bytes * 8.0) / safe_elapsed / 1_000_000.0
        rx_mbps = (self.rx_data_bytes * 8.0) / safe_elapsed / 1_000_000.0
        if self.rtt_count:
            rtt_avg = self.rtt_sum / self.rtt_count
            rtt_text = (
                f"rtt_min_ms={self.rtt_min * 1000.0:.3f} "
                f"rtt_avg_ms={rtt_avg * 1000.0:.3f} "
                f"rtt_max_ms={self.rtt_max * 1000.0:.3f}"
            )
        else:
            rtt_text = "rtt_min_ms=nan rtt_avg_ms=nan rtt_max_ms=nan"
        return (
            f"elapsed_s={elapsed:.3f} "
            f"tx_packets={self.tx_data_frames} tx_bytes={self.tx_data_bytes} "
            f"app_tx_packets={self.app_tx_packets} "
            f"app_tx_bytes={self.app_tx_bytes} "
            f"app_tx_fragments={self.app_tx_fragments} "
            f"tx_mbps={tx_mbps:.6f} acked_tx={self.acked_tx_data} "
            f"failed_tx={self.failed_tx_data} ack_timeouts={self.ack_timeouts} "
            f"rx_frames={self.rx_frames} ack={self.ack_frames} "
            f"errors={self.error_frames} rx_data={self.rx_data_frames} "
            f"rx_data_bytes={self.rx_data_bytes} rx_mbps={rx_mbps:.6f} "
            f"payload_match={self.rx_payload_matches} "
            f"payload_mismatch={self.payload_mismatch} "
            f"status={self.status_frames} pending={len(self.pending)} "
            f"{rtt_text} last_error={self.last_error!r}"
        )


class EventLog:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("w", newline="", encoding="utf-8")
        self.writer = csv.writer(self.file)
        self.lock = threading.Lock()
        self.started_at = time.monotonic()
        self.writer.writerow(("time_s", "type", "seq", "payload_len", "detail"))

    def write(self, frame: Frame) -> None:
        with self.lock:
            self.writer.writerow((
                f"{time.monotonic() - self.started_at:.6f}",
                TYPE_NAMES.get(frame.frame_type, f"0x{frame.frame_type:02x}"),
                frame.seq,
                len(frame.payload),
                format_frame(frame),
            ))
            self.file.flush()

    def write_marker(self, event_type: str, detail: str) -> None:
        with self.lock:
            self.writer.writerow((
                f"{time.monotonic() - self.started_at:.6f}",
                event_type,
                "",
                "",
                detail,
            ))
            self.file.flush()

    def close(self) -> None:
        with self.lock:
            self.file.close()


class RFClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.seq = 1
        self.sock: socket.socket | None = None
        self.lock = threading.Lock()
        self.running = False

    def connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), self.timeout)
        sock.settimeout(0.5)
        self.sock = sock
        self.running = True

    def reconnect_forever(self, delay: float = 1.0) -> None:
        while True:
            try:
                self.connect()
                return
            except OSError as exc:
                print(f"connect failed: {exc}; retrying in {delay:.1f}s")
                time.sleep(delay)

    def close(self) -> None:
        self.running = False
        if self.sock is not None:
            self.sock.close()
            self.sock = None

    def send_frame(self, frame_type: int, payload: bytes = b"") -> int:
        if len(payload) > MAX_FRAME_PAYLOAD:
            raise ValueError("payload exceeds PS TCP frame limit")
        if self.sock is None:
            raise RuntimeError("not connected")
        with self.lock:
            seq = self.seq
            self.seq = (self.seq + 1) & 0xFFFF
            if self.seq == 0:
                self.seq = 1
            packet = HEADER.pack(MAGIC, VERSION, frame_type, seq, len(payload)) + payload
            self.sock.sendall(packet)
            return seq

    def read_exact(self, nbytes: int) -> bytes | None:
        assert self.sock is not None
        chunks: list[bytes] = []
        remaining = nbytes
        while remaining:
            try:
                chunk = self.sock.recv(remaining)
            except socket.timeout:
                if not self.running:
                    return None
                continue
            if not chunk:
                return None
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def recv_frame(self) -> Frame | None:
        header = self.read_exact(HEADER.size)
        if header is None:
            return None
        magic, version, frame_type, seq, length = HEADER.unpack(header)
        if magic != MAGIC:
            raise ProtocolError(f"bad magic {magic!r}, expected {MAGIC!r}")
        if version != VERSION:
            raise ProtocolError(f"unsupported version {version}, expected {VERSION}")
        if length > MAX_FRAME_PAYLOAD:
            raise ProtocolError(
                f"payload length {length} exceeds limit {MAX_FRAME_PAYLOAD}"
            )
        payload = self.read_exact(length)
        if payload is None:
            return None
        return Frame(frame_type, seq, payload)


def parse_hex(text: str) -> bytes:
    clean = "".join(text.split())
    if clean.startswith("0x"):
        clean = clean[2:]
    try:
        return binascii.unhexlify(clean)
    except binascii.Error as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_u16(text: str) -> int:
    try:
        value = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not 0 <= value <= 0xFFFF:
        raise argparse.ArgumentTypeError("value must be in the range 0..0xffff")
    return value


def parse_u32(text: str) -> int:
    try:
        value = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    if not 0 <= value <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("value must be in the range 0..0xffffffff")
    return value


def parse_mode(text: str) -> int:
    key = text.strip().lower().replace("-", "_")
    if key in MODE_NAMES:
        return MODE_NAMES[key]
    try:
        value = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"mode must be one of {sorted(set(MODE_NAMES))} or a numeric value"
        ) from exc
    if not 0 <= value <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("mode must be in the range 0..0xffffffff")
    return value


def make_config_payload(enable: int | None = None,
                        session: int | None = None,
                        lane_mask: int | None = None,
                        tx_lane_mask: int | None = None,
                        rx_lane_mask: int | None = None,
                        mode: int | str | None = None) -> bytes:
    if lane_mask is not None and tx_lane_mask is not None:
        raise ValueError("use either lane_mask or tx_lane_mask, not both")
    mask = 0
    enable_byte = 0
    session_value = 0
    tx_lane_value = 0
    rx_lane_value = 0
    mode_value = 0
    if enable is not None:
        mask |= CONFIG_ENABLE
        enable_byte = 1 if enable else 0
    if session is not None:
        mask |= CONFIG_SESSION
        session_value = session
    if lane_mask is not None or tx_lane_mask is not None:
        mask |= CONFIG_LANE_MASK
        tx_lane_value = lane_mask if lane_mask is not None else tx_lane_mask
    if rx_lane_mask is not None:
        mask |= CONFIG_RX_LANE_MASK
        rx_lane_value = rx_lane_mask
    if mode is not None:
        mask |= CONFIG_MODE
        if isinstance(mode, str):
            try:
                mode_value = MODE_NAMES[mode]
            except KeyError as exc:
                raise ValueError(f"unknown mode {mode!r}") from exc
        else:
            mode_value = mode
    if mask == 0:
        raise ValueError("at least one config field must be provided")
    if not 0 <= mode_value <= 0xFFFFFFFF:
        raise ValueError("mode must be a u32 value")
    if mode is not None:
        return struct.pack("<BBHIII", mask, enable_byte, session_value, tx_lane_value, rx_lane_value, mode_value)
    if rx_lane_mask is None:
        return struct.pack("<BBHI", mask, enable_byte, session_value, tx_lane_value)
    return struct.pack("<BBHII", mask, enable_byte, session_value, tx_lane_value, rx_lane_value)


def parse_status_payload(payload: bytes) -> dict[str, int]:
    if len(payload) >= 64:
        fields = struct.unpack("<16I", payload[:64])
        labels = STATUS_FIELDS_FULL
    elif len(payload) == 48:
        fields = struct.unpack("<12I", payload[:48])
        labels = STATUS_FIELDS_LANE_MASKS
    elif len(payload) == 40:
        fields = struct.unpack("<10I", payload[:40])
        labels = STATUS_FIELDS_BASE
    else:
        return {}
    return dict(zip(labels, fields))


def format_frame(frame: Frame) -> str:
    name = TYPE_NAMES.get(frame.frame_type, f"0x{frame.frame_type:02x}")
    if frame.frame_type == FRAME_STATUS_RSP:
        status = parse_status_payload(frame.payload)
        if status:
            body = " ".join(f"{label}=0x{value:08x}" for label, value in status.items())
            return f"{name} seq={frame.seq} {body}"
        return (
            f"{name} seq={frame.seq} malformed_status_payload_len={len(frame.payload)} "
            f"data={frame.payload.hex()}"
        )
    if frame.frame_type in (FRAME_ACK, FRAME_ERROR):
        try:
            text = frame.payload.decode("ascii", errors="replace")
        except UnicodeDecodeError:
            text = frame.payload.hex()
        return f"{name} seq={frame.seq} {text}"
    if frame.frame_type == FRAME_RX_DATA:
        return f"{name} seq={frame.seq} len={len(frame.payload)} data={frame.payload.hex()}"
    return f"{name} seq={frame.seq} len={len(frame.payload)} data={frame.payload.hex()}"


def send_tracked(client: RFClient, stats: Stats,
                 frame_type: int, payload: bytes = b"") -> int:
    if len(payload) > MAX_FRAME_PAYLOAD:
        raise ValueError("payload exceeds PS TCP frame limit")
    if client.sock is None:
        raise RuntimeError("not connected")
    with client.lock:
        seq = client.seq
        client.seq = (client.seq + 1) & 0xFFFF
        if client.seq == 0:
            client.seq = 1
        packet = HEADER.pack(MAGIC, VERSION, frame_type, seq, len(payload)) + payload
        stats.mark_sent(seq, frame_type, len(payload), payload)
        try:
            client.sock.sendall(packet)
        except OSError:
            with stats.condition:
                stats.pending.pop(seq, None)
                stats.condition.notify_all()
            raise
        return seq


def receiver(client: RFClient, stats: Stats, quiet: bool = False,
             event_log: EventLog | None = None) -> None:
    while client.running:
        try:
            frame = client.recv_frame()
        except (OSError, RuntimeError) as exc:
            if client.running:
                print(f"receive error: {exc}")
            client.running = False
            return
        if frame is None:
            client.running = False
            return
        stats.mark_received(frame)
        if event_log is not None:
            event_log.write(frame)
        if not quiet:
            print(format_frame(frame))


def make_payload(index: int, size: int, pattern: str = "incremental") -> bytes:
    if size <= 0:
        raise ValueError("payload size must be positive")
    if pattern == "incremental":
        return bytes(((index + offset) & 0xFF) for offset in range(size))
    if pattern == "synth_ramp":
        return bytes((offset & 0xFF) for offset in range(size))
    if pattern == "zero":
        return bytes(size)
    if pattern == "ff":
        return bytes((0xFF for _ in range(size)))
    raise ValueError(f"unknown payload pattern {pattern!r}")


def run_repeated_tx(client: RFClient, stats: Stats, count: int,
                    duration: float | None, payload_size: int, interval: float,
                    status_interval: float, window: int,
                    ack_timeout: float, wait_ack: bool,
                    payload_pattern: str = "incremental") -> tuple[int, int]:
    sent = 0
    sent_bytes = 0
    start = time.monotonic()
    next_status = start + status_interval if status_interval > 0 else None

    while client.running:
        now = time.monotonic()
        if count > 0 and sent >= count:
            break
        if duration is not None and (now - start) >= duration:
            break

        if next_status is not None and now >= next_status:
            send_tracked(client, stats, FRAME_STATUS_REQ)
            next_status = now + status_interval

        if wait_ack and not stats.wait_for_tx_window(window, ack_timeout):
            print("ack timeout while waiting for TX window")
            break

        payload = make_payload(sent, payload_size, payload_pattern)
        send_tracked(client, stats, FRAME_TX_DATA, payload)
        sent += 1
        sent_bytes += len(payload)
        if interval > 0:
            time.sleep(interval)

    if wait_ack:
        stats.wait_for_all_tx_data(ack_timeout)
    return sent, sent_bytes


def send_segmented_payload(client: RFClient, stats: Stats, payload: bytes,
                           frame_payload_size: int, window: int,
                           ack_timeout: float, wait_ack: bool) -> tuple[int, bool]:
    if frame_payload_size <= 0 or frame_payload_size > MAX_FRAME_PAYLOAD:
        raise ValueError(f"frame payload size must be in the range 1..{MAX_FRAME_PAYLOAD}")
    fragments = 0
    for offset in range(0, len(payload), frame_payload_size):
        if wait_ack and not stats.wait_for_tx_window(window, ack_timeout):
            return fragments, False
        send_tracked(client, stats, FRAME_TX_DATA, payload[offset:offset + frame_payload_size])
        fragments += 1
    return fragments, True


def run_repeated_app_tx(client: RFClient, stats: Stats, count: int,
                        duration: float | None, app_payload_size: int,
                        frame_payload_size: int, interval: float,
                        status_interval: float, window: int,
                        ack_timeout: float, wait_ack: bool,
                        payload_pattern: str = "incremental") -> tuple[int, int, int]:
    sent = 0
    sent_bytes = 0
    sent_fragments = 0
    start = time.monotonic()
    next_status = start + status_interval if status_interval > 0 else None

    while client.running:
        now = time.monotonic()
        if count > 0 and sent >= count:
            break
        if duration is not None and (now - start) >= duration:
            break

        if next_status is not None and now >= next_status:
            send_tracked(client, stats, FRAME_STATUS_REQ)
            next_status = now + status_interval

        payload = make_payload(sent, app_payload_size, payload_pattern)
        fragment_count, ok = send_segmented_payload(
            client, stats, payload, frame_payload_size, window,
            ack_timeout, wait_ack
        )
        if not ok:
            print("ack timeout while waiting for segmented TX window")
            break
        stats.mark_app_payload_sent(len(payload), fragment_count)
        sent += 1
        sent_bytes += len(payload)
        sent_fragments += fragment_count
        if interval > 0:
            time.sleep(interval)

    if wait_ack:
        stats.wait_for_all_tx_data(ack_timeout)
    return sent, sent_bytes, sent_fragments


def mbps(byte_count: int, elapsed: float) -> float:
    return (byte_count * 8.0) / max(elapsed, 1e-9) / 1_000_000.0


def evaluate_acceptance(stats: Stats, elapsed: float, *,
                        require_clean: bool = False,
                        min_tx_mbps: float | None = None,
                        min_rx_mbps: float | None = None,
                        min_rx_frames: int = 0) -> list[str]:
    failures: list[str] = []
    with stats.condition:
        pending_count = len(stats.pending)
        pending_tx_count = stats.pending_tx_data_count()
        tx_rate = mbps(stats.tx_data_bytes, elapsed)
        rx_rate = mbps(stats.rx_data_bytes, elapsed)

        if require_clean:
            if stats.error_frames:
                failures.append(f"error_frames={stats.error_frames}")
            if stats.failed_tx_data:
                failures.append(f"failed_tx={stats.failed_tx_data}")
            if stats.ack_timeouts:
                failures.append(f"ack_timeouts={stats.ack_timeouts}")
            if stats.payload_mismatch:
                failures.append(f"payload_mismatch={stats.payload_mismatch}")
            if pending_count:
                failures.append(f"pending_frames={pending_count}")
            if pending_tx_count:
                failures.append(f"pending_tx={pending_tx_count}")
        if min_tx_mbps is not None and tx_rate < min_tx_mbps:
            failures.append(f"tx_mbps={tx_rate:.6f}<min_tx_mbps={min_tx_mbps:.6f}")
        if min_rx_mbps is not None and rx_rate < min_rx_mbps:
            failures.append(f"rx_mbps={rx_rate:.6f}<min_rx_mbps={min_rx_mbps:.6f}")
        if min_rx_frames > 0 and stats.rx_data_frames < min_rx_frames:
            failures.append(f"rx_data_frames={stats.rx_data_frames}<min_rx_frames={min_rx_frames}")
    return failures


def wait_for_reconnect_cycle(stats: Stats, min_rx_frames: int,
                             timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    with stats.condition:
        while stats.pending or stats.rx_data_frames < min_rx_frames:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                if stats.pending_tx_data_count() > 0:
                    stats.ack_timeouts += stats.pending_tx_data_count()
                return False
            stats.condition.wait(remaining)
    return True


def run_reconnect_cycles(host: str, port: int, cycles: int,
                         delay: float, timeout: float,
                         payload_size: int = 0,
                         payload_pattern: str = "incremental") -> bool:
    ok = True
    for cycle in range(cycles):
        client = RFClient(host, port, timeout)
        stats = Stats()
        try:
            cycle_started = time.monotonic()
            client.connect()
            rx_thread = threading.Thread(
                target=receiver, args=(client, stats, False), daemon=True
            )
            rx_thread.start()
            send_tracked(client, stats, FRAME_HELLO)
            send_tracked(client, stats, FRAME_STATUS_REQ)
            min_rx_frames = 0
            if payload_size > 0:
                send_tracked(
                    client,
                    stats,
                    FRAME_TX_DATA,
                    make_payload(cycle, payload_size, payload_pattern),
                )
                min_rx_frames = 1
            if not wait_for_reconnect_cycle(stats, min_rx_frames, max(timeout, 0.8)):
                print(f"reconnect cycle {cycle + 1}/{cycles}: pending response timeout")
                ok = False
            elapsed = max(time.monotonic() - cycle_started, 1e-6)
            failures = evaluate_acceptance(
                stats,
                elapsed,
                require_clean=True,
                min_rx_frames=min_rx_frames,
            )
            if failures:
                print(
                    f"reconnect cycle {cycle + 1}/{cycles}: acceptance failures "
                    + ";".join(failures)
                )
                ok = False
            print(f"reconnect cycle {cycle + 1}/{cycles}: {stats.summary(elapsed)}")
        except OSError as exc:
            print(f"reconnect cycle {cycle + 1}/{cycles} failed: {exc}")
            ok = False
        finally:
            client.close()
            if "rx_thread" in locals():
                rx_thread.join(timeout=1.0)
                del rx_thread
        if delay > 0 and cycle + 1 < cycles:
            time.sleep(delay)
    return ok


def interactive(client: RFClient, stats: Stats) -> None:
    print("commands: hello, status, clear, config <enable|session|lane|txlane|rxlane> <value>, sendhex <hex>, sendtext <text>, quit")
    while client.running:
        try:
            line = input("rf> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        cmd, _, arg = line.partition(" ")
        cmd = cmd.lower()
        if cmd in ("quit", "exit"):
            break
        if cmd == "hello":
            send_tracked(client, stats, FRAME_HELLO)
        elif cmd == "status":
            send_tracked(client, stats, FRAME_STATUS_REQ)
        elif cmd == "clear":
            send_tracked(client, stats, FRAME_CLEAR)
        elif cmd == "config":
            key, _, value = arg.partition(" ")
            key = key.lower()
            if key == "enable":
                send_tracked(client, stats, FRAME_CONFIG, make_config_payload(enable=parse_u16(value)))
            elif key == "session":
                send_tracked(client, stats, FRAME_CONFIG, make_config_payload(session=parse_u16(value)))
            elif key in ("lane", "lane_mask", "lanemask"):
                send_tracked(client, stats, FRAME_CONFIG, make_config_payload(lane_mask=parse_u32(value)))
            elif key in ("txlane", "tx_lane", "tx_lane_mask", "txlanemask"):
                send_tracked(client, stats, FRAME_CONFIG, make_config_payload(tx_lane_mask=parse_u32(value)))
            elif key in ("rxlane", "rx_lane", "rx_lane_mask", "rxlanemask"):
                send_tracked(client, stats, FRAME_CONFIG, make_config_payload(rx_lane_mask=parse_u32(value)))
            elif key == "mode":
                send_tracked(client, stats, FRAME_CONFIG, make_config_payload(mode=parse_mode(value)))
            else:
                print("usage: config <enable|session|lane|txlane|rxlane|mode> <value>")
        elif cmd == "sendhex":
            send_tracked(client, stats, FRAME_TX_DATA, parse_hex(arg))
        elif cmd == "sendtext":
            send_tracked(client, stats, FRAME_TX_DATA, arg.encode("utf-8"))
        else:
            print("unknown command")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.10.2")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--retry", action="store_true", help="reconnect until the PS bridge is available")
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--hello", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--config-enable", type=int, choices=(0, 1), help="set IR link enable bit")
    parser.add_argument("--config-session", type=parse_u16, help="set IR protocol session id, accepts decimal or 0x...")
    parser.add_argument("--config-lane-mask", type=parse_u32, help="set legacy combined TX/RX IR lane mask, accepts decimal or 0x...")
    parser.add_argument("--config-tx-lane-mask", type=parse_u32, help="set TX IR lane mask, accepts decimal or 0x...")
    parser.add_argument("--config-rx-lane-mask", type=parse_u32, help="set RX IR lane mask, accepts decimal or 0x...")
    parser.add_argument("--config-mode", type=parse_mode, help="set N03 bridge mode: network_memory_echo, pspl_synth_loopback, or ir_physical")
    parser.add_argument("--send-hex", type=parse_hex)
    parser.add_argument("--send-text")
    parser.add_argument("--command", action="append", default=[], help="send an ASCII N03 command frame, for example PING or READ counters")
    parser.add_argument("--listen", action="store_true")
    parser.add_argument("--repeat", type=int, default=0, help="send this many generated TX_DATA packets")
    parser.add_argument("--duration", type=float, help="send generated TX_DATA packets for this many seconds")
    parser.add_argument("--payload-size", type=int, default=32, help=f"generated TX_DATA payload bytes, max {MAX_GENERATED_PAYLOAD}")
    parser.add_argument("--app-payload-size", type=int, help=f"application payload bytes before RFCM segmentation, max {MAX_APP_PAYLOAD}")
    parser.add_argument("--payload-pattern", choices=("incremental", "synth_ramp", "zero", "ff"), default="incremental")
    parser.add_argument("--interval", type=float, default=0.0, help="delay between generated packets")
    parser.add_argument("--status-interval", type=float, default=0.0, help="periodically request status while repeating")
    parser.add_argument("--window", type=int, default=1, help="maximum unacknowledged TX_DATA packets while repeating")
    parser.add_argument("--ack-timeout", type=float, default=3.0, help="seconds to wait for ACK/window progress")
    parser.add_argument("--no-wait-ack", action="store_true", help="stream repeated TX_DATA without ACK window control")
    parser.add_argument("--csv-log", type=Path, help="write received frames to a CSV event log")
    parser.add_argument("--require-clean", action="store_true", help="exit nonzero if errors, TX failures, ACK timeouts, or pending frames remain")
    parser.add_argument("--min-tx-mbps", type=float, help="exit nonzero if measured TX_DATA send throughput is below this value")
    parser.add_argument("--min-rx-mbps", type=float, help="exit nonzero if measured RX_DATA receive throughput is below this value")
    parser.add_argument("--min-rx-frames", type=int, default=0, help="exit nonzero unless at least this many RX_DATA frames are received")
    parser.add_argument("--expect-error", help="exit zero only if an ERROR frame containing this text is received")
    parser.add_argument("--reconnect-cycles", type=int, default=0, help="connect, query, close, and reconnect this many times")
    parser.add_argument("--reconnect-delay", type=float, default=1.0)
    parser.add_argument("--reconnect-payload-size", type=int, default=0, help="also send this many TX_DATA bytes after reconnect, max 512")
    parser.add_argument("--reconnect-payload-pattern", choices=("incremental", "synth_ramp", "zero", "ff"), default="incremental")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    if args.payload_size <= 0 or args.payload_size > MAX_GENERATED_PAYLOAD:
        parser.error(f"--payload-size must be in the range 1..{MAX_GENERATED_PAYLOAD}")
    if args.app_payload_size is not None:
        if args.app_payload_size <= 0 or args.app_payload_size > MAX_APP_PAYLOAD:
            parser.error(f"--app-payload-size must be in the range 1..{MAX_APP_PAYLOAD}")
        if args.repeat <= 0 and args.duration is None:
            parser.error("--app-payload-size requires --repeat or --duration")
    if args.window <= 0:
        parser.error("--window must be positive")
    if args.ack_timeout <= 0:
        parser.error("--ack-timeout must be positive")
    if args.min_tx_mbps is not None and args.min_tx_mbps < 0:
        parser.error("--min-tx-mbps must be nonnegative")
    if args.min_rx_mbps is not None and args.min_rx_mbps < 0:
        parser.error("--min-rx-mbps must be nonnegative")
    if args.min_rx_frames < 0:
        parser.error("--min-rx-frames must be nonnegative")
    if args.reconnect_payload_size < 0 or args.reconnect_payload_size > MAX_FRAME_PAYLOAD:
        parser.error(f"--reconnect-payload-size must be in the range 0..{MAX_FRAME_PAYLOAD}")

    if args.reconnect_cycles > 0:
        return 0 if run_reconnect_cycles(
            args.host, args.port, args.reconnect_cycles,
            args.reconnect_delay, args.timeout,
            args.reconnect_payload_size,
            args.reconnect_payload_pattern,
        ) else 1

    client = RFClient(args.host, args.port, args.timeout)
    if args.retry:
        client.reconnect_forever()
    else:
        client.connect()

    stats = Stats()
    event_log = EventLog(args.csv_log) if args.csv_log is not None else None
    started_at = time.monotonic()
    acceptance_failures: list[str] = []
    rx_thread = threading.Thread(
        target=receiver, args=(client, stats, args.quiet, event_log), daemon=True
    )
    rx_thread.start()

    if args.hello:
        send_tracked(client, stats, FRAME_HELLO)
    if args.status:
        send_tracked(client, stats, FRAME_STATUS_REQ)
    if args.clear:
        send_tracked(client, stats, FRAME_CLEAR)
    config_requested = (
        args.config_enable is not None or
        args.config_session is not None or
        args.config_lane_mask is not None or
        args.config_tx_lane_mask is not None or
        args.config_rx_lane_mask is not None or
        args.config_mode is not None
    )
    if config_requested:
        send_tracked(client, stats, FRAME_CONFIG, make_config_payload(
            enable=args.config_enable,
            session=args.config_session,
            lane_mask=args.config_lane_mask,
            tx_lane_mask=args.config_tx_lane_mask,
            rx_lane_mask=args.config_rx_lane_mask,
            mode=args.config_mode,
        ))
    if args.send_hex is not None:
        send_tracked(client, stats, FRAME_TX_DATA, args.send_hex)
    if args.send_text is not None:
        send_tracked(client, stats, FRAME_TX_DATA, args.send_text.encode("utf-8"))
    for command in args.command:
        send_tracked(client, stats, FRAME_COMMAND, command.encode("ascii"))
    repeated = args.repeat > 0 or args.duration is not None
    sent = 0
    sent_bytes = 0
    sent_fragments = 0
    if repeated:
        if args.app_payload_size is None:
            sent, sent_bytes = run_repeated_tx(
                client, stats, args.repeat, args.duration, args.payload_size,
                args.interval, args.status_interval, args.window,
                args.ack_timeout, not args.no_wait_ack,
                args.payload_pattern
            )
            sent_fragments = sent
        else:
            sent, sent_bytes, sent_fragments = run_repeated_app_tx(
                client, stats, args.repeat, args.duration, args.app_payload_size,
                args.payload_size, args.interval, args.status_interval,
                args.window, args.ack_timeout, not args.no_wait_ack,
                args.payload_pattern
            )

    one_shot = any((
        args.hello,
        args.status,
        args.clear,
        config_requested,
        args.send_hex is not None,
        args.send_text is not None,
        bool(args.command),
    ))
    try:
        if args.listen or one_shot or repeated:
            while client.running:
                time.sleep(0.1)
                if (one_shot or repeated) and not args.listen:
                    time.sleep(0.7)
                    break
        else:
            interactive(client, stats)
    finally:
        client.close()
        rx_thread.join(timeout=1.0)
        elapsed = time.monotonic() - started_at
        if repeated:
            sent_summary = (
                "sent_summary "
                f"sent_packets={sent} sent_bytes={sent_bytes} "
                f"fragment_frames={sent_fragments} "
                f"frame_payload_size={args.payload_size} "
                f"app_payload_size={args.app_payload_size or 0} "
            )
            summary = "summary " + stats.summary(elapsed)
            print(sent_summary)
            print(summary)
            if event_log is not None:
                event_log.write_marker("SENT_SUMMARY", sent_summary)
                event_log.write_marker("SUMMARY", summary)
        if (args.require_clean or args.min_tx_mbps is not None or
                args.min_rx_mbps is not None or args.min_rx_frames > 0 or
                args.expect_error is not None):
            acceptance_failures = evaluate_acceptance(
                stats,
                elapsed,
                require_clean=args.require_clean and args.expect_error is None,
                min_tx_mbps=args.min_tx_mbps,
                min_rx_mbps=args.min_rx_mbps,
                min_rx_frames=args.min_rx_frames,
            )
            if args.expect_error is not None:
                with stats.condition:
                    if stats.error_frames == 0:
                        acceptance_failures.append("expected_error_missing")
                    elif args.expect_error not in stats.last_error:
                        acceptance_failures.append(
                            f"expected_error={args.expect_error!r} last_error={stats.last_error!r}"
                        )
            if acceptance_failures:
                for failure in acceptance_failures:
                    print(f"acceptance_fail {failure}")
                    if event_log is not None:
                        event_log.write_marker("ACCEPTANCE_FAIL_REASON", failure)
                print("acceptance FAIL")
                if event_log is not None:
                    event_log.write_marker("ACCEPTANCE_FAIL", ";".join(acceptance_failures))
            else:
                print("acceptance PASS")
                if event_log is not None:
                    event_log.write_marker("ACCEPTANCE_PASS", "acceptance PASS")
        if event_log is not None:
            event_log.close()
    return 1 if acceptance_failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
