#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


READONLY_COMMANDS: list[tuple[str, str, float]] = [
    ("STATUS", "STATUS", 10.0),
    ("READ build_id", "READ", 10.0),
    ("READ regmap_version", "READ", 10.0),
    ("READ failure_counters", "READ", 10.0),
    ("DUMP per_lane_counters", "DUMP", 10.0),
    ("CLEAR counters", "CLEAR", 10.0),
    ("CLEAR error", "CLEAR", 10.0),
    ("STATUS", "STATUS", 10.0),
    ("READ failure_counters", "READ", 10.0),
]

FORBIDDEN_REGISTER_PHASE_PATTERNS = [
    re.compile(r"UARTOP_EVENT\s+command=START\b"),
    re.compile(r"UARTOP_RESULT\s+command=START\b"),
    re.compile(r"UARTOP_RESULT\s+command=TEST\b"),
    re.compile(r"\bRESULT\s+test_id="),
    re.compile(r"\bPSPS_STAGE_(BEGIN|SUMMARY)\b"),
    re.compile(r"\bTX_DATA\b"),
]


@dataclass(frozen=True)
class RoundtripCase:
    phase: str
    label: str
    lane_mask: int
    ack_mask: int
    session: int
    payload: int
    count: int
    required_lanes: tuple[int, ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Single-board 2-lane existing-path UART/JTAG evidence runner."
    )
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--ready-timeout", type=float, default=90.0)
    parser.add_argument(
        "--mode",
        choices=("existing-path-roundtrip", "capability-scan", "lane-ack-matrix"),
        default="existing-path-roundtrip",
    )
    parser.add_argument("--loopback-mode", default="PL_INTERNAL")
    parser.add_argument("--payload-sizes", default="16,64,256")
    parser.add_argument("--session", type=lambda value: int(value, 0), default=0x2201)
    parser.add_argument("--lane-repeat", type=int, default=8)
    parser.add_argument("--two-lane-repeat", type=int, default=16)
    parser.add_argument("--stress-repeat", type=int, default=100)
    parser.add_argument("--stress-seconds", type=int, default=60)
    parser.add_argument("--stage-seconds", type=int, default=5)
    parser.add_argument("--enable-fault-injection", action="store_true")
    parser.add_argument("--transcript", default="reports/single_board_loopback_operator.log")
    parser.add_argument("--log-dir", default="")
    parser.add_argument("--summary-json", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--allow-start",
        action="store_true",
        help="Compatibility option; existing-path mode sends TEST commands only when --apply is used.",
    )
    return parser.parse_args()


def timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def append_line(lines: list[str], line: str) -> None:
    lines.append(f"{timestamp()} {line}")


def append_phase(all_lines: list[str], phase_lines: dict[str, list[str]], phase: str, line: str) -> None:
    stamped = f"{timestamp()} {line}"
    all_lines.append(stamped)
    phase_lines.setdefault(phase, []).append(stamped)


def write_text(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_payload_sizes(text: str) -> list[int]:
    values: list[int] = []
    for token in re.split(r"[,\s]+", text.strip()):
        if not token:
            continue
        values.append(int(token, 0))
    return values or [16, 64, 256]


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


def kv_pairs(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line))


def int_value(values: dict[str, str], key: str, default: int = 0) -> int:
    raw = values.get(key)
    if raw is None:
        return default
    try:
        return int(raw, 0)
    except ValueError:
        return default


def wait_for_token(
    ser,
    token: str,
    timeout_s: float,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
    phase: str,
    forbid_register_tx: bool = False,
) -> str:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_phase(all_lines, phase_lines, phase, f"RX {line}")
        if forbid_register_tx:
            for pattern in FORBIDDEN_REGISTER_PHASE_PATTERNS:
                if pattern.search(line):
                    raise RuntimeError(f"forbidden register-phase TX marker observed: {line}")
        if token in line:
            return line
    raise TimeoutError(f"timed out waiting for {token}")


def send_command(
    ser,
    command: str,
    expected: str,
    timeout_s: float,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
    phase: str,
    require_rc0: bool = True,
    forbid_register_tx: bool = False,
) -> str:
    append_phase(all_lines, phase_lines, phase, f"TX {command}")
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()
    result = wait_for_token(
        ser,
        f"UARTOP_RESULT command={expected}",
        timeout_s,
        all_lines,
        phase_lines,
        phase,
        forbid_register_tx=forbid_register_tx,
    )
    if require_rc0 and kv_pairs(result).get("rc") != "0":
        raise RuntimeError(f"{command} returned nonzero rc: {result}")
    return result


def wait_for_result_line(
    ser,
    test_id: str,
    timeout_s: float,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
    phase: str,
) -> str:
    deadline = time.monotonic() + timeout_s
    wanted = f"RESULT test_id={test_id}"
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_phase(all_lines, phase_lines, phase, f"RX {line}")
        if wanted in line:
            return line
    raise TimeoutError(f"timed out waiting for {wanted}")


def send_test_command(
    ser,
    command: str,
    test_id: str,
    timeout_s: float,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
    phase: str,
) -> tuple[str, str]:
    append_phase(all_lines, phase_lines, phase, f"TX {command}")
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()
    test_line = wait_for_token(
        ser,
        f"UARTOP_RESULT command=TEST",
        timeout_s,
        all_lines,
        phase_lines,
        phase,
    )
    if f"test_id={test_id}" not in test_line:
        raise RuntimeError(f"unexpected TEST result while waiting for {test_id}: {test_line}")
    result_line = wait_for_result_line(
        ser,
        test_id,
        5.0,
        all_lines,
        phase_lines,
        phase,
    )
    return test_line, result_line


def byte_delta(before: int, after: int, lane: int) -> int:
    shift = lane * 8
    return (((after >> shift) & 0xFF) - ((before >> shift) & 0xFF)) & 0xFF


def result_line_pass(values: dict[str, str], expected_count: int | None) -> bool:
    if values.get("rc") != "0" or values.get("pass") != "1":
        return False
    sent = int_value(values, "sent")
    rx_ok = int_value(values, "rx_ok")
    if expected_count is not None and sent != expected_count:
        return False
    if sent <= 0 or rx_ok != sent:
        return False
    return (
        int_value(values, "tx_fail") == 0
        and int_value(values, "rx_timeout") == 0
        and int_value(values, "rx_bad") == 0
        and int_value(values, "rx_mismatch") == 0
        and values.get("last_error") == "none"
    )


def failure_delta_clean(before: dict[str, str], after: dict[str, str]) -> bool:
    checked = ("tx_retry_exhausted_count", "ack_timeout_count")
    for key in checked:
        if int_value(after, key) - int_value(before, key) != 0:
            return False
    return True


def status_idle(values: dict[str, str]) -> bool:
    return values.get("rc") == "0" and values.get("last_error") == "none" and int_value(values, "status") == 0


def run_register_status(
    ser,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, Any]:
    phase = "02_register_status_no_tx"
    append_phase(all_lines, phase_lines, phase, "REGISTER_STATUS_PHASE_BEGIN")
    results: list[str] = []
    for command, expected, timeout_s in READONLY_COMMANDS:
        results.append(
            send_command(
                ser,
                command,
                expected,
                timeout_s,
                all_lines,
                phase_lines,
                phase,
                forbid_register_tx=True,
            )
        )

    clear_counters = any(
        "UARTOP_RESULT command=CLEAR" in line and "item=counters" in line and kv_pairs(line).get("rc") == "0"
        for line in results
    )
    clear_error = any(
        "UARTOP_RESULT command=CLEAR" in line and "before_sticky=" in line and kv_pairs(line).get("rc") == "0"
        for line in results
    )
    failure_reads = [
        kv_pairs(line)
        for line in results
        if "UARTOP_RESULT command=READ" in line and "item=failure_counters" in line
    ]
    no_tx = all(
        int_value(values, "tx_start_count") == 0 and int_value(values, "tx_done_count") == 0
        for values in failure_reads
    )
    last_status_line = next((line for line in reversed(results) if "UARTOP_RESULT command=STATUS" in line), "")
    idle_after_clear = status_idle(kv_pairs(last_status_line))
    passed = clear_counters and clear_error and no_tx and idle_after_clear
    summary = {
        "PS_PL_REGISTER_STATUS_AUTO_PASS": 1 if passed else 0,
        "NO_TX_DATA_SENT_DURING_REGISTER_PHASE": 1 if no_tx else 0,
        "CLEAR_COUNTERS_PASS": 1 if clear_counters else 0,
        "CLEAR_ERROR_PASS": 1 if clear_error else 0,
        "STATUS_IDLE_AFTER_CLEAR": 1 if idle_after_clear else 0,
    }
    for key, value in summary.items():
        append_phase(all_lines, phase_lines, phase, f"{key}={value}")
    append_phase(all_lines, phase_lines, phase, "REGISTER_STATUS_PHASE_END")
    return summary


def configure_roundtrip(
    ser,
    case: RoundtripCase,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> None:
    commands = [
        ("CLEAR counters", "CLEAR", 10.0),
        ("CLEAR error", "CLEAR", 10.0),
        (f"CONFIG lane_mask 0x{case.lane_mask:X}", "CONFIG", 10.0),
        (f"CONFIG session 0x{case.session:X}", "CONFIG", 10.0),
        (f"CONFIG ack_mask 0x{case.ack_mask:X}", "CONFIG", 10.0),
        (f"CONFIG payload_bytes {case.payload}", "CONFIG", 10.0),
        ("CONFIG stage_seconds 5", "CONFIG", 10.0),
    ]
    for command, expected, timeout_s in commands:
        send_command(ser, command, expected, timeout_s, all_lines, phase_lines, case.phase)


def read_status_snapshot(
    ser,
    phase: str,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, str]:
    return kv_pairs(send_command(ser, "DUMP per_lane_counters", "DUMP", 10.0, all_lines, phase_lines, phase))


def read_failure_snapshot(
    ser,
    phase: str,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, str]:
    return kv_pairs(send_command(ser, "READ failure_counters", "READ", 10.0, all_lines, phase_lines, phase))


def run_roundtrip_case(
    ser,
    case: RoundtripCase,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, Any]:
    append_phase(all_lines, phase_lines, case.phase, f"ROUNDTRIP_CASE_BEGIN label={case.label}")
    try:
        configure_roundtrip(ser, case, all_lines, phase_lines)
        counters_before = read_status_snapshot(ser, case.phase, all_lines, phase_lines)
        failures_before = read_failure_snapshot(ser, case.phase, all_lines, phase_lines)
        command = f"TEST pspl_roundtrip payload={case.payload} count={case.count}"
        test_line, result_line = send_test_command(
            ser,
            command,
            "PSPL_ROUNDTRIP",
            max(60.0, float(case.count) * 2.0 + 30.0),
            all_lines,
            phase_lines,
            case.phase,
        )
        counters_after = read_status_snapshot(ser, case.phase, all_lines, phase_lines)
        failures_after = read_failure_snapshot(ser, case.phase, all_lines, phase_lines)
        final_status = kv_pairs(send_command(ser, "STATUS", "STATUS", 10.0, all_lines, phase_lines, case.phase))
        values = kv_pairs(test_line)
        tx_deltas = {
            str(lane): byte_delta(int_value(counters_before, "tx_lane"), int_value(counters_after, "tx_lane"), lane)
            for lane in case.required_lanes
        }
        rx_deltas = {
            str(lane): byte_delta(int_value(counters_before, "rx_good"), int_value(counters_after, "rx_good"), lane)
            for lane in case.required_lanes
        }
        lanes_participated = all(delta > 0 for delta in tx_deltas.values()) and all(
            delta > 0 for delta in rx_deltas.values()
        )
        pass_value = (
            result_line_pass(values, case.count)
            and lanes_participated
            and failure_delta_clean(failures_before, failures_after)
            and status_idle(final_status)
        )
        summary = {
            "label": case.label,
            "command": command,
            "pass": 1 if pass_value else 0,
            "test": values,
            "result_line": result_line,
            "tx_lane_delta": tx_deltas,
            "rx_good_delta": rx_deltas,
            "lanes_participated": 1 if lanes_participated else 0,
            "failure_delta_clean": 1 if failure_delta_clean(failures_before, failures_after) else 0,
            "state_idle_after_test": 1 if status_idle(final_status) else 0,
        }
    except Exception as exc:
        append_phase(all_lines, phase_lines, case.phase, f"ROUNDTRIP_CASE_FAILURE={exc}")
        summary = {
            "label": case.label,
            "pass": 0,
            "failure": str(exc),
            "lanes_participated": 0,
            "failure_delta_clean": 0,
            "state_idle_after_test": 0,
        }
    append_phase(all_lines, phase_lines, case.phase, f"{case.label}_PASS={summary['pass']}")
    append_phase(all_lines, phase_lines, case.phase, "ROUNDTRIP_CASE_END")
    return summary


def run_short_stress(
    ser,
    payload_sizes: list[int],
    stress_repeat: int,
    stress_seconds: int,
    session: int,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, Any]:
    phase = "06_2lane_existing_path_short_stress"
    append_phase(all_lines, phase_lines, phase, "SHORT_STRESS_BEGIN")
    test_results: list[dict[str, Any]] = []
    passed = 1
    try:
        base_case = RoundtripCase(
            phase=phase,
            label="STRESS_SETUP",
            lane_mask=0x3,
            ack_mask=0x3,
            session=session,
            payload=16,
            count=1,
            required_lanes=(0, 1),
        )
        configure_roundtrip(ser, base_case, all_lines, phase_lines)
        counters_before = read_status_snapshot(ser, phase, all_lines, phase_lines)
        failures_before = read_failure_snapshot(ser, phase, all_lines, phase_lines)

        matrix: list[tuple[int, int | None, int | None]] = []
        for payload in payload_sizes:
            count = 50 if payload >= 256 else stress_repeat
            matrix.append((payload, count, None))
        matrix.append((16, None, stress_seconds))

        for payload, count, seconds in matrix:
            if count is not None:
                command = f"TEST pspl_roundtrip payload={payload} count={count}"
                timeout_s = max(90.0, float(count) * 2.0 + 60.0)
                expected_count: int | None = count
            else:
                command = f"TEST pspl_roundtrip payload={payload} seconds={seconds}"
                timeout_s = float(seconds or 0) + 120.0
                expected_count = None
            test_line, result_line = send_test_command(
                ser,
                command,
                "PSPL_ROUNDTRIP",
                timeout_s,
                all_lines,
                phase_lines,
                phase,
            )
            values = kv_pairs(test_line)
            test_pass = result_line_pass(values, expected_count)
            test_results.append(
                {
                    "command": command,
                    "pass": 1 if test_pass else 0,
                    "test": values,
                    "result_line": result_line,
                }
            )
            append_phase(all_lines, phase_lines, phase, f"STRESS_TEST_PASS={1 if test_pass else 0} command={command}")
            if not test_pass:
                passed = 0
                break

        counters_after = read_status_snapshot(ser, phase, all_lines, phase_lines)
        failures_after = read_failure_snapshot(ser, phase, all_lines, phase_lines)
        final_status = kv_pairs(send_command(ser, "STATUS", "STATUS", 10.0, all_lines, phase_lines, phase))
        tx_deltas = {
            str(lane): byte_delta(int_value(counters_before, "tx_lane"), int_value(counters_after, "tx_lane"), lane)
            for lane in (0, 1)
        }
        rx_deltas = {
            str(lane): byte_delta(int_value(counters_before, "rx_good"), int_value(counters_after, "rx_good"), lane)
            for lane in (0, 1)
        }
        lanes_participated = all(delta > 0 for delta in tx_deltas.values()) and all(
            delta > 0 for delta in rx_deltas.values()
        )
        clean_failures = failure_delta_clean(failures_before, failures_after)
        idle = status_idle(final_status)
        passed = int(bool(passed and lanes_participated and clean_failures and idle))
        summary = {
            "pass": passed,
            "tests": test_results,
            "tx_lane_delta": tx_deltas,
            "rx_good_delta": rx_deltas,
            "lanes_participated": 1 if lanes_participated else 0,
            "failure_delta_clean": 1 if clean_failures else 0,
            "state_idle_after_test": 1 if idle else 0,
        }
    except Exception as exc:
        append_phase(all_lines, phase_lines, phase, f"SHORT_STRESS_FAILURE={exc}")
        summary = {"pass": 0, "tests": test_results, "failure": str(exc)}
    append_phase(all_lines, phase_lines, phase, f"SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS={summary['pass']}")
    append_phase(all_lines, phase_lines, phase, "SHORT_STRESS_END")
    return summary


def run_lane_ack_matrix(
    ser,
    args: argparse.Namespace,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, Any]:
    phase = "16_lane_ack_matrix"
    append_phase(all_lines, phase_lines, phase, "LANE_ACK_MATRIX_BEGIN")
    matrix_cases = [
        ("lane0_ack0", 0x1, 0x1, (0,)),
        ("lane0_ack1", 0x1, 0x2, (0, 1)),
        ("lane0_ack01", 0x1, 0x3, (0, 1)),
        ("lane1_ack0", 0x2, 0x1, (0, 1)),
        ("lane1_ack1", 0x2, 0x2, (1,)),
        ("lane1_ack01", 0x2, 0x3, (0, 1)),
        ("lane01_ack0", 0x3, 0x1, (0, 1)),
        ("lane01_ack1", 0x3, 0x2, (0, 1)),
        ("lane01_ack01", 0x3, 0x3, (0, 1)),
    ]
    results: list[dict[str, Any]] = []
    for label, lane_mask, ack_mask, observed_lanes in matrix_cases:
        case = RoundtripCase(
            phase=phase,
            label=label,
            lane_mask=lane_mask,
            ack_mask=ack_mask,
            session=args.session,
            payload=16,
            count=2,
            required_lanes=observed_lanes,
        )
        append_phase(
            all_lines,
            phase_lines,
            phase,
            f"MATRIX_CASE_BEGIN label={label} lane_mask=0x{lane_mask:X} ack_mask=0x{ack_mask:X}",
        )
        try:
            configure_roundtrip(ser, case, all_lines, phase_lines)
            counters_before = read_status_snapshot(ser, phase, all_lines, phase_lines)
            failures_before = read_failure_snapshot(ser, phase, all_lines, phase_lines)
            command = "TEST pspl_roundtrip payload=16 count=2"
            test_line, result_line = send_test_command(
                ser,
                command,
                "PSPL_ROUNDTRIP",
                60.0,
                all_lines,
                phase_lines,
                phase,
            )
            counters_after = read_status_snapshot(ser, phase, all_lines, phase_lines)
            failures_after = read_failure_snapshot(ser, phase, all_lines, phase_lines)
            values = kv_pairs(test_line)
            tx_deltas = {
                str(lane): byte_delta(int_value(counters_before, "tx_lane"), int_value(counters_after, "tx_lane"), lane)
                for lane in (0, 1)
            }
            rx_deltas = {
                str(lane): byte_delta(int_value(counters_before, "rx_good"), int_value(counters_after, "rx_good"), lane)
                for lane in (0, 1)
            }
            tx_ack_pass = (
                values.get("rc") == "0"
                and values.get("pass") == "1"
                and int_value(values, "sent") == 2
                and int_value(values, "tx_ok") == 2
                and int_value(values, "tx_fail") == 0
            )
            roundtrip_pass = result_line_pass(values, 2)
            clean_failures = failure_delta_clean(failures_before, failures_after)
            result = {
                "label": label,
                "lane_mask": f"0x{lane_mask:X}",
                "ack_mask": f"0x{ack_mask:X}",
                "tx_ack_pass": 1 if tx_ack_pass else 0,
                "roundtrip_pass": 1 if roundtrip_pass else 0,
                "failure_delta_clean": 1 if clean_failures else 0,
                "tx_lane_delta": tx_deltas,
                "rx_good_delta": rx_deltas,
                "test": values,
                "result_line": result_line,
            }
        except Exception as exc:
            append_phase(all_lines, phase_lines, phase, f"MATRIX_CASE_FAILURE label={label} error={exc}")
            result = {
                "label": label,
                "lane_mask": f"0x{lane_mask:X}",
                "ack_mask": f"0x{ack_mask:X}",
                "tx_ack_pass": 0,
                "roundtrip_pass": 0,
                "failure": str(exc),
            }
        results.append(result)
        append_phase(
            all_lines,
            phase_lines,
            phase,
            "MATRIX_CASE_RESULT "
            f"label={label} lane_mask=0x{lane_mask:X} ack_mask=0x{ack_mask:X} "
            f"tx_ack_pass={result.get('tx_ack_pass', 0)} roundtrip_pass={result.get('roundtrip_pass', 0)} "
            f"tx_lane_delta={result.get('tx_lane_delta', {})} rx_good_delta={result.get('rx_good_delta', {})}",
        )
        append_phase(all_lines, phase_lines, phase, "MATRIX_CASE_END")
    append_phase(all_lines, phase_lines, phase, "LANE_ACK_MATRIX_END")
    return {
        "LANE_ACK_MATRIX_DIAGNOSTIC_DONE": 1,
        "lane_ack_matrix": results,
    }


def run_capability_scan(
    ser,
    args: argparse.Namespace,
    all_lines: list[str],
    phase_lines: dict[str, list[str]],
) -> dict[str, Any]:
    phase = "capability_scan"
    append_phase(all_lines, phase_lines, phase, "CAPABILITY_SCAN_BEGIN")
    for command, expected, timeout_s in READONLY_COMMANDS[:5]:
        send_command(ser, command, expected, timeout_s, all_lines, phase_lines, phase)
    probe = send_command(
        ser,
        f"CONFIG loopback_mode {args.loopback_mode}",
        "CONFIG",
        10.0,
        all_lines,
        phase_lines,
        phase,
        require_rc0=False,
    )
    present = 1 if kv_pairs(probe).get("rc") == "0" else 0
    append_phase(all_lines, phase_lines, phase, f"LOOPBACK_MODE_REGISTER_PRESENT={present}")
    append_phase(all_lines, phase_lines, phase, "CAPABILITY_SCAN_END")
    return {"LOOPBACK_MODE_REGISTER_PRESENT": present}


def dry_run(args: argparse.Namespace, all_lines: list[str], phase_lines: dict[str, list[str]]) -> dict[str, Any]:
    append_phase(all_lines, phase_lines, "dry_run", "UART_OPERATOR_SINGLE_BOARD_LOOPBACK_DRY_RUN=1")
    append_phase(all_lines, phase_lines, "dry_run", f"MODE={args.mode}")
    append_phase(all_lines, phase_lines, "dry_run", f"PORT={args.port} BAUD={args.baud}")
    append_phase(all_lines, phase_lines, "dry_run", f"SESSION=0x{args.session:04X}")
    append_phase(all_lines, phase_lines, "dry_run", "PLAN register_status_no_tx=1")
    for command, expected, timeout_s in READONLY_COMMANDS:
        append_phase(all_lines, phase_lines, "dry_run", f"PLAN command={command} expected={expected} timeout_s={timeout_s}")
    append_phase(all_lines, phase_lines, "dry_run", "PLAN lane0_existing_path=TEST pspl_roundtrip payload=16 count=8")
    append_phase(all_lines, phase_lines, "dry_run", "PLAN lane1_existing_path=TEST pspl_roundtrip payload=16 count=8")
    append_phase(all_lines, phase_lines, "dry_run", "PLAN 2lane_existing_path=TEST pspl_roundtrip payload=16 count=16")
    append_phase(all_lines, phase_lines, "dry_run", "PLAN 2lane_short_stress=payload_matrix_plus_60s")
    if args.mode == "lane-ack-matrix":
        append_phase(all_lines, phase_lines, "dry_run", "PLAN lane_ack_matrix=9_short_pspl_roundtrip_cases")
    append_phase(all_lines, phase_lines, "dry_run", "NO_HARDWARE_ACTION=1")
    return {
        "DRY_RUN_READY": 1,
        "PS_PL_REGISTER_STATUS_AUTO_PASS": "DRY_RUN_READY",
        "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS": "DRY_RUN_READY",
        "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS": "DRY_RUN_READY",
        "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS": "DRY_RUN_READY",
        "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS": "DRY_RUN_READY",
    }


def run_apply(args: argparse.Namespace, all_lines: list[str], phase_lines: dict[str, list[str]]) -> dict[str, Any]:
    append_line(all_lines, "UART_OPERATOR_SINGLE_BOARD_LOOPBACK_BEGIN")
    append_line(all_lines, f"MODE={args.mode} PORT={args.port} BAUD={args.baud}")
    payload_sizes = parse_payload_sizes(args.payload_sizes)
    summary: dict[str, Any] = {
        "payload_sizes": payload_sizes,
        "stress_seconds": args.stress_seconds,
        "session": f"0x{args.session:04X}",
    }
    with open_serial(args.port, args.baud) as ser:
        ser.reset_input_buffer()
        wait_for_token(ser, "UARTOP_READY", args.ready_timeout, all_lines, phase_lines, "uart_ready")
        if args.mode == "capability-scan":
            summary.update(run_capability_scan(ser, args, all_lines, phase_lines))
        elif args.mode == "lane-ack-matrix":
            register_summary = run_register_status(ser, all_lines, phase_lines)
            summary.update(register_summary)
            summary.update(run_lane_ack_matrix(ser, args, all_lines, phase_lines))
        else:
            register_summary = run_register_status(ser, all_lines, phase_lines)
            summary.update(register_summary)
            cases = [
                RoundtripCase(
                    "03_lane0_existing_path_roundtrip",
                    "SINGLE_BOARD_LANE0_EXISTING_PATH",
                    0x1,
                    0x1,
                    args.session,
                    16,
                    args.lane_repeat,
                    (0,),
                ),
                RoundtripCase(
                    "04_lane1_existing_path_roundtrip",
                    "SINGLE_BOARD_LANE1_EXISTING_PATH",
                    0x2,
                    0x2,
                    args.session,
                    16,
                    args.lane_repeat,
                    (1,),
                ),
                RoundtripCase(
                    "05_2lane_existing_path_roundtrip",
                    "SINGLE_BOARD_2LANE_EXISTING_PATH",
                    0x3,
                    0x3,
                    args.session,
                    16,
                    args.two_lane_repeat,
                    (0, 1),
                ),
            ]
            case_results: dict[str, Any] = {}
            for case in cases:
                result = run_roundtrip_case(ser, case, all_lines, phase_lines)
                case_results[case.label] = result
                summary[f"{case.label}_PASS"] = int(result.get("pass", 0))
            if summary.get("SINGLE_BOARD_2LANE_EXISTING_PATH_PASS") == 1:
                stress = run_short_stress(
                    ser,
                    payload_sizes,
                    args.stress_repeat,
                    args.stress_seconds,
                    args.session,
                    all_lines,
                    phase_lines,
                )
            else:
                stress = {"pass": 0, "blocked": "2lane_minimum_roundtrip_not_passed"}
                append_phase(
                    all_lines,
                    phase_lines,
                    "06_2lane_existing_path_short_stress",
                    "SHORT_STRESS_BLOCKED=2lane_minimum_roundtrip_not_passed",
                )
            summary["cases"] = case_results
            summary["short_stress"] = stress
            summary["SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS"] = int(stress.get("pass", 0))
            summary["SINGLE_BOARD_2LANE_SHORT_STRESS_PASS"] = int(stress.get("pass", 0))
        try:
            shutdown = send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, all_lines, phase_lines, "operator_shutdown")
            summary["OPERATOR_SHUTDOWN_PASS"] = 1 if kv_pairs(shutdown).get("rc") == "0" else 0
        except Exception as exc:
            append_phase(all_lines, phase_lines, "operator_shutdown", f"OPERATOR_SHUTDOWN_FAILURE={exc}")
            summary["OPERATOR_SHUTDOWN_PASS"] = 0
            summary["OPERATOR_SHUTDOWN_FAILURE"] = str(exc)
    append_line(all_lines, "UART_OPERATOR_SINGLE_BOARD_LOOPBACK_END")
    return summary


def write_phase_logs(log_dir: Path, phase_lines: dict[str, list[str]]) -> None:
    name_map = {
        "02_register_status_no_tx": "02_register_status_no_tx.log",
        "03_lane0_existing_path_roundtrip": "03_lane0_existing_path_roundtrip.log",
        "04_lane1_existing_path_roundtrip": "04_lane1_existing_path_roundtrip.log",
        "05_2lane_existing_path_roundtrip": "05_2lane_existing_path_roundtrip.log",
        "06_2lane_existing_path_short_stress": "06_2lane_existing_path_short_stress.log",
        "16_lane_ack_matrix": "16_lane_ack_matrix.log",
    }
    for phase, file_name in name_map.items():
        lines = phase_lines.get(phase, [f"{timestamp()} {phase.upper()}_NOT_RUN=1"])
        write_text(log_dir / file_name, lines)


def main() -> int:
    args = parse_args()
    transcript = Path(args.transcript)
    if not transcript.is_absolute():
        transcript = Path.cwd() / transcript
    log_dir = Path(args.log_dir) if args.log_dir else transcript.parent
    if not log_dir.is_absolute():
        log_dir = Path.cwd() / log_dir
    summary_json = Path(args.summary_json) if args.summary_json else log_dir / "operator_summary.json"
    if not summary_json.is_absolute():
        summary_json = Path.cwd() / summary_json

    all_lines: list[str] = []
    phase_lines: dict[str, list[str]] = {}
    rc = 0
    summary: dict[str, Any]
    try:
        if args.dry_run or not args.apply:
            summary = dry_run(args, all_lines, phase_lines)
        else:
            summary = run_apply(args, all_lines, phase_lines)
            if args.mode == "existing-path-roundtrip":
                required = (
                    "PS_PL_REGISTER_STATUS_AUTO_PASS",
                    "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS",
                    "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS",
                    "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS",
                    "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS",
                    "OPERATOR_SHUTDOWN_PASS",
                )
                rc = 0 if all(summary.get(key) == 1 for key in required) else 20
    except Exception as exc:
        append_line(all_lines, f"UART_OPERATOR_SINGLE_BOARD_LOOPBACK_FAILURE={exc}")
        summary = {"failure": str(exc)}
        rc = 1
    finally:
        write_text(transcript, all_lines)
        write_phase_logs(log_dir, phase_lines)
        summary_json.parent.mkdir(parents=True, exist_ok=True)
        summary_json.write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    print(f"TRANSCRIPT={transcript}")
    print(f"OPERATOR_SUMMARY_JSON={summary_json}")
    for key in (
        "PS_PL_REGISTER_STATUS_AUTO_PASS",
        "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS",
        "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS",
        "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS",
        "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS",
        "SINGLE_BOARD_2LANE_SHORT_STRESS_PASS",
        "OPERATOR_SHUTDOWN_PASS",
    ):
        if key in summary:
            print(f"{key}={summary[key]}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
