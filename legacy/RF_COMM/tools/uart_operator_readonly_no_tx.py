#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path


READONLY_COMMANDS: list[tuple[str, str, float]] = [
    ("STATUS", "STATUS", 10.0),
    ("READ build_id", "READ", 10.0),
    ("READ regmap_version", "READ", 10.0),
    ("READ rx_frame_obs", "READ", 10.0),
    ("READ dma_obs", "READ", 10.0),
    ("READ failure_counters", "READ", 10.0),
    ("DUMP per_lane_counters", "DUMP", 10.0),
    ("CLEAR counters", "CLEAR", 10.0),
    ("CLEAR error", "CLEAR", 10.0),
    ("STATUS", "STATUS", 10.0),
    ("READ failure_counters", "READ", 10.0),
    ("SHUTDOWN", "SHUTDOWN", 10.0),
]
OPTIONAL_COMMAND_PREFIXES = {"DUMP"}

FORBIDDEN_RX_PATTERNS = [
    re.compile(r"UARTOP_EVENT\s+command=START\b"),
    re.compile(r"UARTOP_RESULT\s+command=START\b"),
    re.compile(r"UARTOP_RESULT\s+command=TEST\b"),
    re.compile(r"\bRESULT\s+test_id="),
    re.compile(r"\bPSPS_STAGE_(BEGIN|SUMMARY)\b"),
    re.compile(r"\bTX_DATA\b"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read RF_COMM UART operator status without START/TEST/TX commands."
    )
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--ready-timeout", type=float, default=40.0)
    parser.add_argument("--transcript", default="reports/P2_register_status_readonly_transcript.log")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def append_line(lines: list[str], line: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    lines.append(f"{stamp} {line}")


def kv_pairs(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line))


def check_forbidden(line: str) -> None:
    for pattern in FORBIDDEN_RX_PATTERNS:
        if pattern.search(line):
            raise RuntimeError(f"forbidden no-TX marker observed: {line}")


def open_serial(port: str, baud: int):
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("pyserial is required: python -m pip install pyserial") from exc
    return serial.Serial(port=port, baudrate=baud, timeout=0.2)


def read_line(ser) -> str | None:
    raw = ser.readline()
    if not raw:
        return None
    return raw.decode("utf-8", errors="replace").strip()


def read_until(ser, token: str, timeout: float, lines: list[str]) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_line(lines, f"RX {line}")
        check_forbidden(line)
        if token in line:
            return line
    raise TimeoutError(f"timed out waiting for {token}")


def send_command(ser, command: str, expected: str, timeout: float, lines: list[str]) -> str:
    if command.split()[0].upper() in {"START", "TEST"}:
        raise RuntimeError(f"readonly runner refuses to send {command}")
    optional = command.split()[0].upper() in OPTIONAL_COMMAND_PREFIXES
    append_line(lines, f"TX {command}")
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()
    result = ""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_line(lines, f"RX {line}")
        check_forbidden(line)
        if f"UARTOP_RESULT command={expected}" in line:
            result = line
            break
        if optional and "UARTOP_RESULT command=UNKNOWN" in line:
            append_line(lines, f"CHECK optional_command_unsupported command={command}")
            return line
    if not result:
        raise TimeoutError(f"timed out waiting for UARTOP_RESULT command={expected}")
    values = kv_pairs(result)
    if values.get("rc") != "0":
        raise RuntimeError(f"{command} returned nonzero rc: {result}")
    return result


def parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def validate_readonly_results(results: list[str], lines: list[str]) -> None:
    failure_reads = [
        line for line in results
        if "UARTOP_RESULT command=READ" in line and "item=failure_counters" in line
    ]
    if not failure_reads:
        raise RuntimeError("missing READ failure_counters result")

    for idx, line in enumerate(failure_reads, start=1):
        values = kv_pairs(line)
        tx_start_count = parse_int(values.get("tx_start_count"))
        tx_done_count = parse_int(values.get("tx_done_count"))
        tx_retry_count = parse_int(values.get("tx_retry_count_total"))
        tx_retry_exhausted = parse_int(values.get("tx_retry_exhausted_count"))
        ack_timeout_count = parse_int(values.get("ack_timeout_count"))
        if tx_start_count is None or tx_done_count is None:
            raise RuntimeError(f"failure_counters missing TX counts: {line}")
        if tx_start_count != 0 or tx_done_count != 0:
            raise RuntimeError(f"TX counters changed during no-TX readout: {line}")
        for name, value in (
            ("tx_retry_count_total", tx_retry_count),
            ("tx_retry_exhausted_count", tx_retry_exhausted),
            ("ack_timeout_count", ack_timeout_count),
        ):
            if value is not None and value != 0:
                raise RuntimeError(f"{name} is nonzero during no-TX readout: {line}")
        append_line(lines, f"CHECK failure_counters_{idx}_tx_zero=1")

    build_lines = [
        line for line in results
        if "UARTOP_RESULT command=READ" in line and "item=build_id" in line
    ]
    if not build_lines:
        raise RuntimeError("missing READ build_id result")
    build_values = kv_pairs(build_lines[-1])
    payload_limit = parse_int(build_values.get("payload_limit"))
    if payload_limit is None or payload_limit < 16:
        raise RuntimeError(f"operator payload limit is invalid: {build_lines[-1]}")
    append_line(lines, "CHECK payload_limit_ge_16=1")


def write_transcript(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_dry(args: argparse.Namespace, lines: list[str]) -> int:
    append_line(lines, "UART_OPERATOR_READONLY_NO_TX_DRY_RUN=1")
    append_line(lines, f"PORT={args.port} BAUD={args.baud}")
    for command, expected, timeout in READONLY_COMMANDS:
        append_line(lines, f"PLAN command={command} expected={expected} timeout_s={timeout}")
    append_line(lines, "NO_START_COMMAND_IN_PLAN=1")
    append_line(lines, "NO_TEST_COMMAND_IN_PLAN=1")
    append_line(lines, "UART_OPERATOR_READONLY_NO_TX_PASS=DRY_RUN")
    return 0


def run_serial(args: argparse.Namespace, lines: list[str]) -> int:
    append_line(lines, "UART_OPERATOR_READONLY_NO_TX_BEGIN")
    append_line(lines, f"PORT={args.port} BAUD={args.baud}")
    results: list[str] = []
    with open_serial(args.port, args.baud) as ser:
        ready = read_until(ser, "UARTOP_READY", args.ready_timeout, lines)
        append_line(lines, f"READY_LINE={ready}")
        try:
            initial_status = read_until(ser, "UARTOP_RESULT command=STATUS", 5.0, lines)
            results.append(initial_status)
        except TimeoutError:
            append_line(lines, "WARN initial STATUS line not observed after UARTOP_READY")

        for command, expected, timeout in READONLY_COMMANDS:
            results.append(send_command(ser, command, expected, timeout, lines))

    validate_readonly_results(results, lines)
    append_line(lines, "NO_START_COMMAND_SENT=1")
    append_line(lines, "NO_TEST_COMMAND_SENT=1")
    append_line(lines, "NO_TX_DATA_SENT=1")
    append_line(lines, "UART_OPERATOR_READONLY_NO_TX_PASS=1")
    append_line(lines, "UART_OPERATOR_READONLY_NO_TX_END")
    return 0


def main() -> int:
    args = parse_args()
    transcript = Path(args.transcript)
    lines: list[str] = []
    try:
        rc = run_dry(args, lines) if args.dry_run else run_serial(args, lines)
    except Exception as exc:
        append_line(lines, f"UART_OPERATOR_READONLY_NO_TX_FAILURE={exc}")
        rc = 1
    finally:
        write_transcript(transcript, lines)
    return rc


if __name__ == "__main__":
    sys.exit(main())
