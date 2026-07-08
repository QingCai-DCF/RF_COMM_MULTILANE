#!/usr/bin/env python3
"""Run an N03-8 localhost payload matrix against the offline RFCM mock server.

This is a host/tooling gate only. It does not contact the development board,
program hardware, write UART, or drive TFDU/IR traffic, and it must not be used
as real board throughput evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
HOST_CLIENT = ROOT / "software" / "host_client"

sys.path.insert(0, str(HOST_CLIENT))
import mock_rfcm_server as mock  # noqa: E402
import rf_comm_client as rf  # noqa: E402


DEFAULT_PAYLOAD_SIZES = (16, 64, 128, 256, 512, 1024, 4096, 8192)
MODES = (
    ("pc_ps_memory_echo", rf.MODE_NETWORK_MEMORY_ECHO, "incremental"),
    ("pc_ps_pl_synth_loopback", rf.MODE_PSPL_SYNTH_LOOPBACK, "synth_ramp"),
)


@dataclass
class MatrixRow:
    mode: str
    payload_bytes: int
    repeat: int
    frame_payload_size: int
    fragment_frames: int
    app_tx_bytes: int
    rx_data_frames: int
    rx_data_bytes: int
    pc_tx_mbps: str
    pc_rx_mbps: str
    roundtrip_goodput_mbps: str
    packets_per_second: str
    latency_min_ms: str
    latency_p50_ms: str
    latency_p95_ms: str
    latency_max_ms: str
    payload_mismatch: int
    error_frames: int
    ack_timeouts: int
    pending_frames: int
    failed_tx: int
    last_error: str
    result: str
    current_status: str
    scope: str
    evidence: str


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def wait_for(stats: rf.Stats, predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    with stats.condition:
        while not predicate():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            stats.condition.wait(min(0.05, remaining))
        return True


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * pct / 100.0
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[lower]
    ratio = pos - lower
    return ordered[lower] * (1.0 - ratio) + ordered[upper] * ratio


def ms_text(value: float | None) -> str:
    if value is None:
        return "nan"
    return f"{value * 1000.0:.3f}"


def rate_mbps(byte_count: int, elapsed: float) -> float:
    return (byte_count * 8.0) / max(elapsed, 1e-9) / 1_000_000.0


def connect_client(port: int, timeout: float) -> tuple[rf.RFClient, rf.Stats, threading.Thread]:
    client = rf.RFClient("127.0.0.1", port, timeout=timeout)
    stats = rf.Stats()
    client.connect()
    rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
    rx_thread.start()
    return client, stats, rx_thread


def close_client(client: rf.RFClient, rx_thread: threading.Thread) -> None:
    client.close()
    rx_thread.join(timeout=1.0)


def run_case(
    server: mock.MockRFCMServer,
    *,
    mode_label: str,
    mode_value: int,
    payload_bytes: int,
    pattern: str,
    repeat: int,
    frame_payload_size: int,
    window: int,
    ack_timeout: float,
    timeout: float,
) -> MatrixRow:
    client, stats, rx_thread = connect_client(server.port, timeout)
    fragments = 0
    sent_packets = 0
    started = time.monotonic()
    try:
        rf.send_tracked(
            client,
            stats,
            rf.FRAME_CONFIG,
            rf.make_config_payload(enable=0, session=0x1234, lane_mask=0x1, mode=mode_value),
        )
        config_ok = wait_for(stats, lambda: stats.pending_count() == 0, ack_timeout)
        started = time.monotonic()
        if config_ok:
            for index in range(repeat):
                payload = rf.make_payload(index, payload_bytes, pattern)
                fragment_count, ok = rf.send_segmented_payload(
                    client,
                    stats,
                    payload,
                    frame_payload_size,
                    window,
                    ack_timeout,
                    True,
                )
                fragments += fragment_count
                if not ok:
                    break
                stats.mark_app_payload_sent(len(payload), fragment_count)
                sent_packets += 1
            stats.wait_for_all_tx_data(ack_timeout)
            expected_rx_bytes = payload_bytes * sent_packets
            wait_for(stats, lambda: stats.rx_data_bytes >= expected_rx_bytes, ack_timeout)
        elapsed = time.monotonic() - started
    finally:
        close_client(client, rx_thread)

    expected_fragments = sum(
        math.ceil(payload_bytes / frame_payload_size) for _ in range(sent_packets)
    )
    expected_bytes = payload_bytes * sent_packets
    with stats.condition:
        pending_frames = stats.pending_count()
        samples = list(stats.tx_data_rtt_samples)
        failures = []
        if not config_ok:
            failures.append("config_not_acked")
        if sent_packets != repeat:
            failures.append(f"sent_packets={sent_packets}<repeat={repeat}")
        if fragments != expected_fragments:
            failures.append(f"fragment_frames={fragments}<expected={expected_fragments}")
        if stats.rx_data_bytes != expected_bytes:
            failures.append(f"rx_data_bytes={stats.rx_data_bytes}<expected={expected_bytes}")
        if stats.payload_mismatch:
            failures.append(f"payload_mismatch={stats.payload_mismatch}")
        if stats.error_frames:
            failures.append(f"error_frames={stats.error_frames}")
        if stats.ack_timeouts:
            failures.append(f"ack_timeouts={stats.ack_timeouts}")
        if pending_frames:
            failures.append(f"pending_frames={pending_frames}")
        if stats.failed_tx_data:
            failures.append(f"failed_tx={stats.failed_tx_data}")

        result = "PASS" if not failures else "FAIL"
        evidence = stats.summary(elapsed)
        if failures:
            evidence += " failures=" + ";".join(failures)
        return MatrixRow(
            mode=mode_label,
            payload_bytes=payload_bytes,
            repeat=repeat,
            frame_payload_size=frame_payload_size,
            fragment_frames=fragments,
            app_tx_bytes=stats.app_tx_bytes,
            rx_data_frames=stats.rx_data_frames,
            rx_data_bytes=stats.rx_data_bytes,
            pc_tx_mbps=f"{rate_mbps(stats.tx_data_bytes, elapsed):.6f}",
            pc_rx_mbps=f"{rate_mbps(stats.rx_data_bytes, elapsed):.6f}",
            roundtrip_goodput_mbps=f"{rate_mbps(stats.rx_data_bytes, elapsed):.6f}",
            packets_per_second=f"{sent_packets / max(elapsed, 1e-9):.3f}",
            latency_min_ms=ms_text(min(samples) if samples else None),
            latency_p50_ms=ms_text(percentile(samples, 50.0)),
            latency_p95_ms=ms_text(percentile(samples, 95.0)),
            latency_max_ms=ms_text(max(samples) if samples else None),
            payload_mismatch=stats.payload_mismatch,
            error_frames=stats.error_frames,
            ack_timeouts=stats.ack_timeouts,
            pending_frames=pending_frames,
            failed_tx=stats.failed_tx_data,
            last_error=stats.last_error,
            result=result,
            current_status=(
                "PASS_OFFLINE_LOCALHOST_REAL_BOARD_PENDING"
                if result == "PASS"
                else "FAIL_OFFLINE_LOCALHOST"
            ),
            scope="OFFLINE_LOCALHOST_NOT_REAL_BOARD_THROUGHPUT",
            evidence=evidence,
        )


def parse_payload_sizes(text: str) -> tuple[int, ...]:
    sizes: list[int] = []
    for part in text.split(","):
        value = int(part.strip(), 0)
        if value <= 0:
            raise argparse.ArgumentTypeError("payload sizes must be positive")
        sizes.append(value)
    return tuple(sizes)


def write_reports(rows: list[MatrixRow], server_log: Path) -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    all_pass = all(row.result == "PASS" for row in rows)
    overall = "PASS_OFFLINE_LOCALHOST_MATRIX" if all_pass else "FAIL"

    csv_path = REPORTS / "n03_offline_payload_matrix_current.csv"
    md_path = REPORTS / "n03_offline_payload_matrix_current.md"
    json_path = REPORTS / "n03_offline_payload_matrix_current.json"
    summary_path = REPORTS / "n03_offline_payload_matrix_current.summary.txt"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    table = [
        "| mode | payload_bytes | repeat | fragments | rx_data_bytes | p50_ms | p95_ms | result | status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        table.append(
            f"| {row.mode} | {row.payload_bytes} | {row.repeat} | {row.fragment_frames} | "
            f"{row.rx_data_bytes} | {row.latency_p50_ms} | {row.latency_p95_ms} | "
            f"{row.result} | {row.current_status} |"
        )

    md = [
        "# N03 Offline Payload Matrix",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Rows: `{len(rows)}`",
        "- Scope: `OFFLINE_LOCALHOST_NOT_REAL_BOARD_THROUGHPUT`",
        "- Real board throughput acceptance: `0`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This matrix exercises the N03 payload sizes against the localhost RFCM mock server. It proves host protocol, segmentation, ACK, RX echo, and metric capture plumbing only.",
        "",
        "## Matrix",
        "",
        *table,
        "",
        "```text",
        f"N03_OFFLINE_PAYLOAD_MATRIX_PASS={int(all_pass)}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_ROWS={len(rows)}",
        "NO_REAL_BOARD_THROUGHPUT_CLAIM=1",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "scope": "OFFLINE_LOCALHOST_NOT_REAL_BOARD_THROUGHPUT",
        "real_board_throughput_acceptance": False,
        "reports": {
            "markdown": rel(md_path),
            "csv": rel(csv_path),
            "json": rel(json_path),
            "summary": rel(summary_path),
            "server_log": rel(server_log),
        },
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    summary = [
        f"N03_OFFLINE_PAYLOAD_MATRIX_BEGIN {generated}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_STATUS={overall}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_PASS={int(all_pass)}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_ROWS={len(rows)}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_MD={rel(md_path)}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_CSV={rel(csv_path)}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_JSON={rel(json_path)}",
        f"N03_OFFLINE_PAYLOAD_MATRIX_SERVER_LOG={rel(server_log)}",
        "NO_REAL_BOARD_THROUGHPUT_CLAIM=1",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        f"N03_OFFLINE_PAYLOAD_MATRIX_END {datetime.now().isoformat(timespec='seconds')}",
    ]
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

    for line in summary:
        print(line)
    return 0 if all_pass else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--payload-sizes", type=parse_payload_sizes, default=DEFAULT_PAYLOAD_SIZES)
    parser.add_argument("--frame-payload-size", type=int, default=rf.MAX_FRAME_PAYLOAD)
    parser.add_argument("--window", type=int, default=4)
    parser.add_argument("--ack-timeout", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)

    if args.repeat <= 0:
        parser.error("--repeat must be positive")
    if args.frame_payload_size <= 0 or args.frame_payload_size > rf.MAX_FRAME_PAYLOAD:
        parser.error(f"--frame-payload-size must be in the range 1..{rf.MAX_FRAME_PAYLOAD}")
    if args.window <= 0:
        parser.error("--window must be positive")
    if args.ack_timeout <= 0:
        parser.error("--ack-timeout must be positive")

    rows: list[MatrixRow] = []
    REPORTS.mkdir(parents=True, exist_ok=True)
    server_log = REPORTS / "n03_offline_payload_matrix_current.server.log"
    if server_log.exists():
        server_log.unlink()

    server = mock.MockRFCMServer(log_file=server_log)
    server.start()
    try:
        for mode_label, mode_value, pattern in MODES:
            for payload_bytes in args.payload_sizes:
                rows.append(
                    run_case(
                        server,
                        mode_label=mode_label,
                        mode_value=mode_value,
                        payload_bytes=payload_bytes,
                        pattern=pattern,
                        repeat=args.repeat,
                        frame_payload_size=args.frame_payload_size,
                        window=args.window,
                        ack_timeout=args.ack_timeout,
                        timeout=args.timeout,
                    )
                )
    finally:
        server.stop()

    return write_reports(rows, server_log)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
