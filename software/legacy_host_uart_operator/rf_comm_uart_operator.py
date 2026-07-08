#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path


CONTROL_COMMAND_PLAN = [
    ("STATUS", "STATUS", 10.0),
    ("CONFIG lane_mask {lane_mask}", "CONFIG", 10.0),
    ("CONFIG ack_mask {ack_mask}", "CONFIG", 10.0),
    ("CONFIG payload_bytes {payload_bytes}", "CONFIG", 10.0),
    ("CONFIG stage_seconds {stage_seconds}", "CONFIG", 10.0),
    ("READ counters", "READ", 10.0),
    ("CLEAR error", "CLEAR", 10.0),
    ("START", "START", None),
    ("STOP", "STOP", 10.0),
    ("READ counters", "READ", 10.0),
    ("SHUTDOWN", "SHUTDOWN", 10.0),
]

RX_SYNTH_MATRIX = [
    ("RX_SYN_01", 16, 100, "incrementing"),
    ("RX_SYN_02", 64, 1000, "pseudo"),
    ("RX_SYN_03", 128, 1000, "pseudo"),
    ("RX_SYN_04", 256, 1000, "pseudo"),
]

P3_RX_SYNTH_MATRIX = [
    ("RX_SYNTH_001_INC", 1, 1000, "incrementing"),
    ("RX_SYNTH_008_PSEUDO", 8, 1000, "pseudo"),
    ("RX_SYNTH_015_PSEUDO", 15, 1000, "pseudo"),
    ("RX_SYNTH_016_PSEUDO", 16, 1000, "pseudo"),
    ("RX_SYNTH_063_PSEUDO", 63, 1000, "pseudo"),
    ("RX_SYNTH_064_PSEUDO", 64, 10000, "pseudo"),
    ("RX_SYNTH_127_PSEUDO", 127, 1000, "pseudo"),
    ("RX_SYNTH_128_PSEUDO", 128, 10000, "pseudo"),
    ("RX_SYNTH_255_PSEUDO", 255, 1000, "pseudo"),
    ("RX_SYNTH_256_PSEUDO", 256, 100000, "pseudo"),
    ("RX_SYNTH_256_INC", 256, 100000, "incrementing"),
    ("RX_SYNTH_256_ZERO", 256, 100000, "zero"),
    ("RX_SYNTH_256_ONES", 256, 100000, "ones"),
]

P3_ROUNDTRIP_SEQUENCE = [
    ("RT_016_10", "TEST pspl_roundtrip payload=16 count=10"),
    ("RT_064_10", "TEST pspl_roundtrip payload=64 count=10"),
    ("RT_064_100", "TEST pspl_roundtrip payload=64 count=100"),
    ("RT_256_100", "TEST pspl_roundtrip payload=256 count=100"),
    ("RT_064_30S", "TEST pspl_roundtrip payload=64 seconds=30"),
    ("RT_256_60S", "TEST pspl_roundtrip payload=256 seconds=60"),
]

P4_FAILURE_COUNTER_SEQUENCE = [
    ("READ build_id", "READ", 10.0),
    ("READ failure_counters", "READ", 10.0),
    ("CONFIG lane_mask {lane_mask}", "CONFIG", 10.0),
    ("CONFIG ack_mask {ack_mask}", "CONFIG", 10.0),
    ("CONFIG payload_bytes {payload_bytes}", "CONFIG", 10.0),
    ("CONFIG stage_seconds {stage_seconds}", "CONFIG", 10.0),
    ("CLEAR sticky", "CLEAR", 10.0),
    ("CLEAR error", "CLEAR", 10.0),
    ("START", "START", None),
    ("READ counters", "READ", 10.0),
    ("READ failure_counters", "READ", 10.0),
    ("READ dma_obs", "READ", 10.0),
    ("SHUTDOWN", "SHUTDOWN", 10.0),
]

P4_IR_ROUNDTRIP_SEQUENCE = [
    ("IR_RT_016_10", "TEST ir_data_roundtrip payload=16 count=10"),
    ("IR_RT_064_10", "TEST ir_data_roundtrip payload=64 count=10"),
    ("IR_RT_064_100", "TEST ir_data_roundtrip payload=64 count=100"),
    ("IR_RT_256_100", "TEST ir_data_roundtrip payload=256 count=100"),
    ("IR_RT_256_60S", "TEST ir_data_roundtrip payload=256 seconds=60"),
]

P6_IR_ROUNDTRIP_5X300_SEQUENCE = [
    ("IR_RT_256_300S_1", "TEST ir_data_roundtrip payload=256 seconds=300"),
    ("IR_RT_256_300S_2", "TEST ir_data_roundtrip payload=256 seconds=300"),
    ("IR_RT_256_300S_3", "TEST ir_data_roundtrip payload=256 seconds=300"),
    ("IR_RT_256_300S_4", "TEST ir_data_roundtrip payload=256 seconds=300"),
    ("IR_RT_256_300S_5", "TEST ir_data_roundtrip payload=256 seconds=300"),
]

P5_RX_SYNTH_COMBINED_MATRIX = [
    ("P5_RX_SYN_001_INC", 1, 1000, "incrementing"),
    ("P5_RX_SYN_064_PSEUDO", 64, 1000, "pseudo"),
    ("P5_RX_SYN_255_ONES", 255, 1000, "ones"),
    ("P5_RX_SYN_256_PSEUDO", 256, 10000, "pseudo"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RF_COMM P2 UART operator acceptance runner")
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--lane-mask", default="0x1")
    parser.add_argument("--ack-mask", default="0x1")
    parser.add_argument("--payload-bytes", type=int, default=256)
    parser.add_argument("--stage-seconds", type=int, default=300)
    parser.add_argument(
        "--mode",
        choices=(
            "control",
            "pspl-data",
            "p3-rx-stress",
            "p3-negative",
            "p3-roundtrip",
            "p4-failure-smoke",
            "p4-ir-roundtrip",
            "p6-ir-roundtrip-5x300",
            "p5-rx-synth-combined",
        ),
        default="control",
    )
    parser.add_argument("--tx-count", type=int, default=100)
    parser.add_argument("--rx-stress-count", type=int, default=10000)
    parser.add_argument("--p3-reduced-stress-count", type=int, default=10000)
    parser.add_argument("--skip-rx-stress", action="store_true")
    parser.add_argument("--ready-timeout", type=float, default=30.0)
    parser.add_argument("--transcript", default="reports/P2_uart_operator_control_transcript.log")
    return parser.parse_args()


def open_serial(port: str, baud: int):
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("pyserial is required: python -m pip install pyserial") from exc
    return serial.Serial(port=port, baudrate=baud, timeout=0.2)


def append_line(lines: list[str], line: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    lines.append(f"{stamp} {line}")


def read_line(ser) -> str | None:
    raw = ser.readline()
    if not raw:
        return None
    return raw.decode("utf-8", errors="replace").strip()


def wait_for_token(ser, token: str, timeout: float, lines: list[str]) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_line(lines, f"RX {line}")
        if token in line:
            return line
    raise TimeoutError(f"Timed out waiting for {token}")


def send_command(ser, command: str, expected: str, timeout: float, lines: list[str]) -> str:
    append_line(lines, f"TX {command}")
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()
    return wait_for_token(ser, f"UARTOP_RESULT command={expected}", timeout, lines)


def wait_for_result_line(ser, test_id: str, timeout: float, lines: list[str]) -> str:
    deadline = time.monotonic() + timeout
    wanted = f"RESULT test_id={test_id}"
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_line(lines, f"RX {line}")
        if wanted in line:
            return line
    raise TimeoutError(f"Timed out waiting for {wanted}")


def send_test_command(ser, command: str, test_id: str, timeout: float, lines: list[str]) -> tuple[str, str]:
    append_line(lines, f"TX {command}")
    ser.write((command + "\r\n").encode("ascii"))
    ser.flush()

    deadline = time.monotonic() + timeout
    test_line = ""
    while time.monotonic() < deadline:
        line = read_line(ser)
        if line is None:
            continue
        append_line(lines, f"RX {line}")
        if "UARTOP_RESULT command=TEST" in line and f"test_id={test_id}" in line:
            test_line = line
            break
    if not test_line:
        raise TimeoutError(f"Timed out waiting for TEST {test_id}")

    result_line = wait_for_result_line(ser, test_id, 5.0, lines)
    return test_line, result_line


def kv_pairs(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line))


def result_is_clean_start(line: str) -> bool:
    values = kv_pairs(line)
    int_fields = {
        "sent": 1,
        "rx_ok": 1,
        "tx_fail": 0,
        "rx_timeout": 0,
        "rx_bad": 0,
        "rx_mismatch": 0,
    }
    for key, minimum in int_fields.items():
        if key not in values:
            return False
        try:
            parsed = int(values[key], 0)
        except ValueError:
            return False
        if minimum == 0 and parsed != 0:
            return False
        if minimum == 1 and parsed < 1:
            return False
    return (
        values.get("sent") == values.get("rx_ok")
        and values.get("loss") == "0.0%"
        and values.get("last_error") == "none"
    )


def result_is_pass(line: str) -> bool:
    values = kv_pairs(line)
    test_id = values.get("test_id")
    if test_id == "TX_DMA":
        return (
            values.get("rc") == "0"
            and values.get("pass") == "1"
            and values.get("tx_fail") == "0"
            and values.get("last_error") == "none"
            and values.get("sent") == values.get("ack_ok")
        )
    if test_id == "PSPL_ROUNDTRIP":
        return (
            values.get("rc") == "0"
            and values.get("pass") == "1"
            and values.get("tx_fail") == "0"
            and values.get("rx_timeout") == "0"
            and values.get("rx_bad") == "0"
            and values.get("rx_mismatch") == "0"
            and values.get("last_error") == "none"
        )
    return (
        values.get("rc") == "0"
        and values.get("pass") == "1"
        and values.get("rx_timeout") == "0"
        and values.get("rx_bad") == "0"
        and values.get("rx_mismatch") == "0"
        and values.get("last_error") == "none"
    )


def require_rc0(result: str, command: str) -> None:
    values = kv_pairs(result)
    if values.get("rc") != "0":
        raise RuntimeError(f"{command} failed: {result}")


def result_detected_negative(line: str) -> bool:
    values = kv_pairs(line)
    detected_fields = ("rx_bad", "rx_mismatch", "rx_timeout")
    detected = any(int(values.get(field, "0"), 0) > 0 for field in detected_fields)
    return values.get("test_id") == "RX_DMA_SYNTH" and values.get("pass") == "0" and detected


def common_pspl_setup(ser, args: argparse.Namespace, lines: list[str], payload_bytes: int | None = None) -> None:
    payload = payload_bytes if payload_bytes is not None else args.payload_bytes
    commands = [
        ("STATUS", "STATUS", 10.0),
        ("READ build_id", "READ", 10.0),
        ("READ regmap_version", "READ", 10.0),
        (f"CONFIG lane_mask {args.lane_mask}", "CONFIG", 10.0),
        (f"CONFIG ack_mask {args.ack_mask}", "CONFIG", 10.0),
        (f"CONFIG payload_bytes {payload}", "CONFIG", 10.0),
        ("CLEAR counters", "CLEAR", 10.0),
        ("CLEAR sticky", "CLEAR", 10.0),
    ]
    for command, expected, timeout in commands:
        result = send_command(ser, command, expected, timeout, lines)
        values = kv_pairs(result)
        if values.get("rc") != "0":
            raise RuntimeError(f"{command} failed: {result}")


def run_control_plan(ser, args: argparse.Namespace, lines: list[str]) -> None:
    start_result = ""
    for template, expected, timeout in CONTROL_COMMAND_PLAN:
        command = template.format(
            lane_mask=args.lane_mask,
            ack_mask=args.ack_mask,
            payload_bytes=args.payload_bytes,
            stage_seconds=args.stage_seconds,
        )
        effective_timeout = timeout
        if effective_timeout is None:
            effective_timeout = float(args.stage_seconds) + 60.0
        result = send_command(ser, command, expected, effective_timeout, lines)
        values = kv_pairs(result)
        if values.get("rc") != "0":
            raise RuntimeError(f"{command} failed: {result}")
        if expected == "START":
            start_result = result
    if not result_is_clean_start(start_result):
        raise RuntimeError(f"START counters are not clean: {start_result}")


def run_pspl_data_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []

    common_pspl_setup(ser, args, lines, payload_bytes=64)

    for payload in (64, args.payload_bytes):
        test_id = "TX_DMA"
        command = f"TEST tx_dma payload={payload} count={args.tx_count}"
        test_line, result_line = send_test_command(ser, command, test_id, 60.0, lines)
        values = kv_pairs(test_line)
        values["case"] = f"TX_DMA_{payload}"
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    result = send_command(ser, "CLEAR counters", "CLEAR", 10.0, lines)
    if kv_pairs(result).get("rc") != "0":
        raise RuntimeError(f"CLEAR counters failed: {result}")

    matrix = list(RX_SYNTH_MATRIX)
    if not args.skip_rx_stress:
        matrix.append(("RX_SYN_05", args.payload_bytes, args.rx_stress_count, "pseudo"))

    for case_id, payload, count, pattern in matrix:
        command = f"TEST rx_dma_synth payload={payload} count={count} pattern={pattern}"
        timeout = max(30.0, min(300.0, 30.0 + count / 100.0))
        test_line, result_line = send_test_command(ser, command, "RX_DMA_SYNTH", timeout, lines)
        values = kv_pairs(test_line)
        values["case"] = case_id
        values["payload"] = str(payload)
        values["count"] = str(count)
        values["pattern_name"] = pattern
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    for command, expected in (
        ("READ rx_last_error", "READ"),
        ("DUMP rx_first_bad", "DUMP"),
        ("DUMP per_lane_counters", "DUMP"),
        ("READ counters", "READ"),
        ("SHUTDOWN", "SHUTDOWN"),
    ):
        result = send_command(ser, command, expected, 10.0, lines)
        if kv_pairs(result).get("rc") != "0":
            raise RuntimeError(f"{command} failed: {result}")

    return results


def run_p3_rx_stress_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    common_pspl_setup(ser, args, lines, payload_bytes=args.payload_bytes)

    for case_id, payload, count, pattern in P3_RX_SYNTH_MATRIX:
        effective_count = count
        reduced = "0"
        if count == 100000 and args.p3_reduced_stress_count < count:
            effective_count = args.p3_reduced_stress_count
            reduced = "1"
        command = f"TEST rx_dma_synth payload={payload} count={effective_count} pattern={pattern}"
        timeout = max(30.0, min(900.0, 30.0 + effective_count / 100.0))
        test_line, result_line = send_test_command(ser, command, "RX_DMA_SYNTH", timeout, lines)
        values = kv_pairs(test_line)
        values["case"] = case_id
        values["payload"] = str(payload)
        values["count"] = str(effective_count)
        values["pattern_name"] = pattern
        values["reduced_stress"] = reduced
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, lines)
    return results


def run_p3_negative_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    common_pspl_setup(ser, args, lines, payload_bytes=64)

    negative_command = "TEST rx_dma_synth payload=64 count=1 pattern=pseudo expect_pattern=incrementing"
    test_line, result_line = send_test_command(ser, negative_command, "RX_DMA_SYNTH", 30.0, lines)
    values = kv_pairs(test_line)
    values["case"] = "NEG_EXPECT_PATTERN_MISMATCH"
    values["error_injection"] = "expect_pattern_mismatch"
    values["expected_error"] = "rx_mismatch"
    values["result_line"] = result_line
    results.append(values)
    if not result_detected_negative(test_line):
        raise RuntimeError(f"{negative_command} did not detect the injected error: {test_line}")

    send_command(ser, "CLEAR sticky", "CLEAR", 10.0, lines)
    recovery_command = "TEST rx_dma_synth payload=64 count=1 pattern=pseudo"
    recovery_line, recovery_result = send_test_command(ser, recovery_command, "RX_DMA_SYNTH", 30.0, lines)
    recovery_values = kv_pairs(recovery_line)
    recovery_values["case"] = "NEG_RECOVERY_GOOD_PACKET"
    recovery_values["error_injection"] = "none"
    recovery_values["expected_error"] = "none"
    recovery_values["result_line"] = recovery_result
    results.append(recovery_values)
    if not result_is_pass(recovery_line):
        raise RuntimeError(f"Recovery packet did not pass: {recovery_line}")

    send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, lines)
    return results


def run_p3_roundtrip_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    common_pspl_setup(ser, args, lines, payload_bytes=args.payload_bytes)

    for case_id, command in P3_ROUNDTRIP_SEQUENCE:
        test_id = "PSPL_ROUNDTRIP"
        timeout = 120.0
        if "seconds=30" in command:
            timeout = 120.0
        elif "seconds=60" in command:
            timeout = 180.0
        test_line, result_line = send_test_command(ser, command, test_id, timeout, lines)
        values = kv_pairs(test_line)
        values["case"] = case_id
        values["command"] = command
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    send_command(ser, "READ rx_stream_obs", "READ", 10.0, lines)
    send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, lines)
    return results


def run_p4_failure_smoke_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    start_result = ""
    last_failure_counter_line = ""
    shutdown_line = ""

    for template, expected, timeout in P4_FAILURE_COUNTER_SEQUENCE:
        command = template.format(
            lane_mask=args.lane_mask,
            ack_mask=args.ack_mask,
            payload_bytes=args.payload_bytes,
            stage_seconds=args.stage_seconds,
        )
        effective_timeout = timeout
        if effective_timeout is None:
            effective_timeout = float(args.stage_seconds) + 60.0
        result = send_command(ser, command, expected, effective_timeout, lines)
        require_rc0(result, command)
        values = kv_pairs(result)
        values["sequence_command"] = command
        results.append(values)
        if command == "START":
            start_result = result
        elif command == "READ failure_counters":
            last_failure_counter_line = result
        elif command == "SHUTDOWN":
            shutdown_line = result

    if not result_is_clean_start(start_result):
        raise RuntimeError(f"START counters are not clean: {start_result}")

    failure_values = kv_pairs(last_failure_counter_line)
    for field in (
        "tx_start_count",
        "tx_done_count",
        "tx_retry_count_total",
        "tx_retry_exhausted_count",
        "ack_timeout_count",
        "max_retry_seen",
        "last_error",
    ):
        if field not in failure_values:
            raise RuntimeError(f"READ failure_counters missing {field}: {last_failure_counter_line}")
    if int(failure_values["tx_start_count"], 0) <= 0:
        raise RuntimeError(f"tx_start_count did not increment: {last_failure_counter_line}")
    if int(failure_values["tx_done_count"], 0) <= 0:
        raise RuntimeError(f"tx_done_count did not increment: {last_failure_counter_line}")
    if int(kv_pairs(start_result).get("tx_fail", "1"), 0) != 0:
        raise RuntimeError(f"START reported tx_fail: {start_result}")
    if failure_values.get("last_error") != "none":
        raise RuntimeError(f"failure counter last_error is not none: {last_failure_counter_line}")
    require_rc0(shutdown_line, "SHUTDOWN")
    return results


def run_p4_ir_roundtrip_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    common_pspl_setup(ser, args, lines, payload_bytes=args.payload_bytes)

    for case_id, command in P4_IR_ROUNDTRIP_SEQUENCE:
        test_id = "IR_DATA_ROUNDTRIP"
        timeout = 120.0
        if "seconds=60" in command:
            timeout = 180.0
        test_line, result_line = send_test_command(ser, command, test_id, timeout, lines)
        values = kv_pairs(test_line)
        values["case"] = case_id
        values["command"] = command
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    for command in ("READ rx_frame_obs", "READ dma_obs"):
        try:
            send_command(ser, command, "READ", 10.0, lines)
        except Exception as exc:
            append_line(lines, f"WARN {command} {exc}")
    send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, lines)
    return results


def run_p6_ir_roundtrip_5x300_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    common_pspl_setup(ser, args, lines, payload_bytes=args.payload_bytes)

    for case_id, command in P6_IR_ROUNDTRIP_5X300_SEQUENCE:
        send_command(ser, "CLEAR counters", "CLEAR", 10.0, lines)
        send_command(ser, "CLEAR sticky", "CLEAR", 10.0, lines)
        test_line, result_line = send_test_command(
            ser,
            command,
            "IR_DATA_ROUNDTRIP",
            420.0,
            lines,
        )
        values = kv_pairs(test_line)
        values["case"] = case_id
        values["command"] = command
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    for command in ("READ rx_frame_obs", "READ dma_obs"):
        try:
            send_command(ser, command, "READ", 10.0, lines)
        except Exception as exc:
            append_line(lines, f"WARN {command} {exc}")
    send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, lines)
    return results


def run_p5_rx_synth_combined_plan(ser, args: argparse.Namespace, lines: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    common_pspl_setup(ser, args, lines, payload_bytes=args.payload_bytes)

    for case_id, payload, count, pattern in P5_RX_SYNTH_COMBINED_MATRIX:
        command = f"TEST rx_dma_synth payload={payload} count={count} pattern={pattern}"
        timeout = max(30.0, min(300.0, 30.0 + count / 100.0))
        test_line, result_line = send_test_command(ser, command, "RX_DMA_SYNTH", timeout, lines)
        values = kv_pairs(test_line)
        values["case"] = case_id
        values["payload"] = str(payload)
        values["count"] = str(count)
        values["pattern_name"] = pattern
        values["result_line"] = result_line
        results.append(values)
        if not result_is_pass(test_line):
            raise RuntimeError(f"{command} did not pass: {test_line}")

    negative_command = "TEST rx_dma_synth payload=64 count=1 pattern=pseudo expect_pattern=incrementing"
    negative_line, negative_result = send_test_command(ser, negative_command, "RX_DMA_SYNTH", 30.0, lines)
    negative_values = kv_pairs(negative_line)
    negative_values["case"] = "P5_NEG_EXPECT_PATTERN_MISMATCH"
    negative_values["error_injection"] = "expect_pattern_mismatch"
    negative_values["expected_error"] = "rx_mismatch"
    negative_values["result_line"] = negative_result
    results.append(negative_values)
    if not result_detected_negative(negative_line):
        raise RuntimeError(f"{negative_command} did not detect the injected error: {negative_line}")

    send_command(ser, "CLEAR sticky", "CLEAR", 10.0, lines)
    recovery_command = "TEST rx_dma_synth payload=64 count=1 pattern=pseudo"
    recovery_line, recovery_result = send_test_command(ser, recovery_command, "RX_DMA_SYNTH", 30.0, lines)
    recovery_values = kv_pairs(recovery_line)
    recovery_values["case"] = "P5_NEG_RECOVERY_GOOD_PACKET"
    recovery_values["error_injection"] = "none"
    recovery_values["expected_error"] = "none"
    recovery_values["result_line"] = recovery_result
    results.append(recovery_values)
    if not result_is_pass(recovery_line):
        raise RuntimeError(f"Recovery packet did not pass: {recovery_line}")

    for command in ("READ dma_obs", "READ failure_counters", "READ counters"):
        result = send_command(ser, command, "READ", 10.0, lines)
        require_rc0(result, command)

    send_command(ser, "SHUTDOWN", "SHUTDOWN", 10.0, lines)
    return results


def main() -> int:
    args = parse_args()
    transcript = Path(args.transcript)
    if not transcript.is_absolute():
        transcript = Path.cwd() / transcript
    transcript.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    pass_marker = 0
    failure = ""

    if args.mode == "control":
        append_line(lines, "UART_OPERATOR_CONTROL_BEGIN")
    elif args.mode == "pspl-data":
        append_line(lines, "UART_OPERATOR_PSPL_DATA_BEGIN")
    else:
        append_line(lines, f"UART_OPERATOR_{args.mode.upper().replace('-', '_')}_BEGIN")
    append_line(lines, f"PORT={args.port} BAUD={args.baud}")
    append_line(lines, f"LANE_MASK={args.lane_mask} ACK_MASK={args.ack_mask}")
    append_line(lines, f"PAYLOAD_BYTES={args.payload_bytes} STAGE_SECONDS={args.stage_seconds}")
    append_line(lines, f"MODE={args.mode} TX_COUNT={args.tx_count} RX_STRESS_COUNT={args.rx_stress_count} SKIP_RX_STRESS={int(args.skip_rx_stress)}")

    try:
        with open_serial(args.port, args.baud) as ser:
            ser.reset_input_buffer()
            wait_for_token(ser, "UARTOP_READY", args.ready_timeout, lines)
            if args.mode == "control":
                run_control_plan(ser, args, lines)
            elif args.mode == "pspl-data":
                run_pspl_data_plan(ser, args, lines)
            elif args.mode == "p3-rx-stress":
                run_p3_rx_stress_plan(ser, args, lines)
            elif args.mode == "p3-negative":
                run_p3_negative_plan(ser, args, lines)
            elif args.mode == "p3-roundtrip":
                run_p3_roundtrip_plan(ser, args, lines)
            elif args.mode == "p4-failure-smoke":
                run_p4_failure_smoke_plan(ser, args, lines)
            elif args.mode == "p4-ir-roundtrip":
                run_p4_ir_roundtrip_plan(ser, args, lines)
            elif args.mode == "p6-ir-roundtrip-5x300":
                run_p6_ir_roundtrip_5x300_plan(ser, args, lines)
            elif args.mode == "p5-rx-synth-combined":
                run_p5_rx_synth_combined_plan(ser, args, lines)
            pass_marker = 1
    except Exception as exc:
        failure = str(exc)
        append_line(lines, f"ERROR {failure}")

    if args.mode == "control":
        append_line(lines, f"UART_OPERATOR_CONTROL_PASS={pass_marker}")
    elif args.mode == "pspl-data":
        append_line(lines, f"UART_OPERATOR_PSPL_DATA_PASS={pass_marker}")
    else:
        append_line(lines, f"UART_OPERATOR_{args.mode.upper().replace('-', '_')}_PASS={pass_marker}")
    if failure:
        if args.mode == "control":
            append_line(lines, f"UART_OPERATOR_CONTROL_FAILURE={failure}")
        elif args.mode == "pspl-data":
            append_line(lines, f"UART_OPERATOR_PSPL_DATA_FAILURE={failure}")
        else:
            append_line(lines, f"UART_OPERATOR_{args.mode.upper().replace('-', '_')}_FAILURE={failure}")
    if args.mode == "control":
        append_line(lines, "UART_OPERATOR_CONTROL_END")
    elif args.mode == "pspl-data":
        append_line(lines, "UART_OPERATOR_PSPL_DATA_END")
    else:
        append_line(lines, f"UART_OPERATOR_{args.mode.upper().replace('-', '_')}_END")
    transcript.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"TRANSCRIPT={transcript}")
    if args.mode == "control":
        print(f"UART_OPERATOR_CONTROL_PASS={pass_marker}")
    elif args.mode == "pspl-data":
        print(f"UART_OPERATOR_PSPL_DATA_PASS={pass_marker}")
    else:
        print(f"UART_OPERATOR_{args.mode.upper().replace('-', '_')}_PASS={pass_marker}")
    if failure:
        if args.mode == "control":
            print(f"UART_OPERATOR_CONTROL_FAILURE={failure}")
        elif args.mode == "pspl-data":
            print(f"UART_OPERATOR_PSPL_DATA_FAILURE={failure}")
        else:
            print(f"UART_OPERATOR_{args.mode.upper().replace('-', '_')}_FAILURE={failure}")
    return 0 if pass_marker else 1


if __name__ == "__main__":
    raise SystemExit(main())
