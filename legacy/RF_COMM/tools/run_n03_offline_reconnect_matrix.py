#!/usr/bin/env python3
"""Run the N03 reconnect matrix against the localhost RFCM mock server.

This is offline evidence only. It proves host protocol/reconnect tooling and
mock PS bridge behavior without touching FPGA, UART, TFDU, or real Ethernet.
"""

from __future__ import annotations

import argparse
import csv
import json
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


@dataclass
class ReconnectRow:
    case: str
    cycle: int
    total_cycles: int
    payload_bytes: int
    rx_data_frames: int
    rx_data_bytes: int
    payload_mismatch: int
    error_frames: int
    ack_timeouts: int
    pending_frames: int
    failed_tx: int
    status_frames: int
    last_error: str
    elapsed_s: str
    result: str
    current_status: str
    scope: str
    evidence: str


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def run_cycle(
    *,
    case: str,
    cycle: int,
    total_cycles: int,
    port: int,
    timeout: float,
    payload_bytes: int,
    payload_pattern: str,
) -> ReconnectRow:
    client = rf.RFClient("127.0.0.1", port, timeout=timeout)
    stats = rf.Stats()
    started = time.monotonic()
    failures: list[str] = []
    try:
        client.connect()
        rx_thread = threading.Thread(target=rf.receiver, args=(client, stats, True), daemon=True)
        rx_thread.start()
        rf.send_tracked(client, stats, rf.FRAME_HELLO)
        rf.send_tracked(client, stats, rf.FRAME_STATUS_REQ)
        min_rx_frames = 0
        if payload_bytes > 0:
            rf.send_tracked(
                client,
                stats,
                rf.FRAME_TX_DATA,
                rf.make_payload(cycle - 1, payload_bytes, payload_pattern),
            )
            min_rx_frames = 1
        if not rf.wait_for_reconnect_cycle(stats, min_rx_frames, max(timeout, 0.8)):
            failures.append("pending_response_timeout")
        elapsed = max(time.monotonic() - started, 1e-6)
        failures.extend(
            rf.evaluate_acceptance(
                stats,
                elapsed,
                require_clean=True,
                min_rx_frames=min_rx_frames,
            )
        )
    except OSError as exc:
        elapsed = max(time.monotonic() - started, 1e-6)
        failures.append(f"connect_or_io={exc}")
    finally:
        client.close()
        if "rx_thread" in locals():
            rx_thread.join(timeout=1.0)

    with stats.condition:
        pending_frames = stats.pending_count()
        result = "PASS" if not failures else "FAIL"
        return ReconnectRow(
            case=case,
            cycle=cycle,
            total_cycles=total_cycles,
            payload_bytes=payload_bytes,
            rx_data_frames=stats.rx_data_frames,
            rx_data_bytes=stats.rx_data_bytes,
            payload_mismatch=stats.payload_mismatch,
            error_frames=stats.error_frames,
            ack_timeouts=stats.ack_timeouts,
            pending_frames=pending_frames,
            failed_tx=stats.failed_tx_data,
            status_frames=stats.status_frames,
            last_error=stats.last_error,
            elapsed_s=f"{elapsed:.6f}",
            result=result,
            current_status=(
                "PASS_OFFLINE_LOCALHOST_REAL_BOARD_PENDING"
                if result == "PASS"
                else "FAIL_OFFLINE_LOCALHOST"
            ),
            scope="OFFLINE_LOCALHOST_NOT_REAL_BOARD_LINK_RECOVERY",
            evidence=stats.summary(elapsed) + ("" if not failures else " failures=" + ";".join(failures)),
        )


def run_case(
    *,
    case: str,
    cycles: int,
    payload_bytes: int,
    payload_pattern: str,
    timeout: float,
    server: mock.MockRFCMServer,
) -> list[ReconnectRow]:
    return [
        run_cycle(
            case=case,
            cycle=cycle,
            total_cycles=cycles,
            port=server.port,
            timeout=timeout,
            payload_bytes=payload_bytes,
            payload_pattern=payload_pattern,
        )
        for cycle in range(1, cycles + 1)
    ]


def write_reports(rows: list[ReconnectRow], server_log: Path) -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    all_pass = all(row.result == "PASS" for row in rows)
    hello_rows = [row for row in rows if row.case == "hello_status_reconnect_10x"]
    payload_rows = [row for row in rows if row.case == "payload_echo_reconnect_20x"]
    hello_pass = len(hello_rows) == 10 and all(row.result == "PASS" for row in hello_rows)
    payload_pass = len(payload_rows) == 20 and all(row.result == "PASS" for row in payload_rows)
    overall = "PASS_OFFLINE_LOCALHOST_RECONNECT_MATRIX" if all_pass else "FAIL"

    csv_path = REPORTS / "n03_offline_reconnect_matrix_current.csv"
    md_path = REPORTS / "n03_offline_reconnect_matrix_current.md"
    json_path = REPORTS / "n03_offline_reconnect_matrix_current.json"
    summary_path = REPORTS / "n03_offline_reconnect_matrix_current.summary.txt"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    table = [
        "| case | cycle | payload_bytes | rx_data_bytes | status_frames | result | status |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        table.append(
            f"| {row.case} | {row.cycle}/{row.total_cycles} | {row.payload_bytes} | "
            f"{row.rx_data_bytes} | {row.status_frames} | {row.result} | {row.current_status} |"
        )

    md = [
        "# N03 Offline Reconnect Matrix",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- HELLO/STATUS reconnect 10x: `{'PASS' if hello_pass else 'FAIL'}`",
        f"- Payload echo reconnect 20x: `{'PASS' if payload_pass else 'FAIL'}`",
        "- Scope: `OFFLINE_LOCALHOST_NOT_REAL_BOARD_LINK_RECOVERY`",
        "- Real board link recovery acceptance: `0`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This matrix exercises the N03 reconnect cycle counts requested by the plan against the localhost RFCM mock server. It does not replace real Ethernet disconnect/reconnect or cable unplug/replug evidence.",
        "",
        "## Matrix",
        "",
        *table,
        "",
        "```text",
        f"N03_OFFLINE_RECONNECT_MATRIX_PASS={int(all_pass)}",
        f"N03_OFFLINE_RECONNECT_HELLO_10X_PASS={int(hello_pass)}",
        f"N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS={int(payload_pass)}",
        "NO_REAL_BOARD_LINK_RECOVERY_CLAIM=1",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "scope": "OFFLINE_LOCALHOST_NOT_REAL_BOARD_LINK_RECOVERY",
        "real_board_link_recovery_acceptance": False,
        "hello_status_reconnect_10x_pass": hello_pass,
        "payload_echo_reconnect_20x_pass": payload_pass,
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
        f"N03_OFFLINE_RECONNECT_MATRIX_BEGIN {generated}",
        f"N03_OFFLINE_RECONNECT_MATRIX_STATUS={overall}",
        f"N03_OFFLINE_RECONNECT_MATRIX_PASS={int(all_pass)}",
        f"N03_OFFLINE_RECONNECT_HELLO_10X_PASS={int(hello_pass)}",
        f"N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS={int(payload_pass)}",
        f"N03_OFFLINE_RECONNECT_MATRIX_ROWS={len(rows)}",
        f"N03_OFFLINE_RECONNECT_MATRIX_MD={rel(md_path)}",
        f"N03_OFFLINE_RECONNECT_MATRIX_CSV={rel(csv_path)}",
        f"N03_OFFLINE_RECONNECT_MATRIX_JSON={rel(json_path)}",
        f"N03_OFFLINE_RECONNECT_MATRIX_SERVER_LOG={rel(server_log)}",
        "NO_REAL_BOARD_LINK_RECOVERY_CLAIM=1",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        f"N03_OFFLINE_RECONNECT_MATRIX_END {datetime.now().isoformat(timespec='seconds')}",
    ]
    summary_path.write_text("\n".join(summary) + "\n", encoding="utf-8")

    for line in summary:
        print(line)
    return 0 if all_pass else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hello-cycles", type=int, default=10)
    parser.add_argument("--payload-cycles", type=int, default=20)
    parser.add_argument("--payload-size", type=int, default=64)
    parser.add_argument("--payload-pattern", choices=("incremental", "synth_ramp", "zero", "ff"), default="incremental")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)

    if args.hello_cycles <= 0:
        parser.error("--hello-cycles must be positive")
    if args.payload_cycles <= 0:
        parser.error("--payload-cycles must be positive")
    if args.payload_size <= 0 or args.payload_size > rf.MAX_FRAME_PAYLOAD:
        parser.error(f"--payload-size must be in the range 1..{rf.MAX_FRAME_PAYLOAD}")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")

    REPORTS.mkdir(parents=True, exist_ok=True)
    server_log = REPORTS / "n03_offline_reconnect_matrix_current.server.log"
    if server_log.exists():
        server_log.unlink()

    rows: list[ReconnectRow] = []
    server = mock.MockRFCMServer(log_file=server_log)
    server.start()
    try:
        rows.extend(
            run_case(
                case="hello_status_reconnect_10x",
                cycles=args.hello_cycles,
                payload_bytes=0,
                payload_pattern=args.payload_pattern,
                timeout=args.timeout,
                server=server,
            )
        )
        rows.extend(
            run_case(
                case="payload_echo_reconnect_20x",
                cycles=args.payload_cycles,
                payload_bytes=args.payload_size,
                payload_pattern=args.payload_pattern,
                timeout=args.timeout,
                server=server,
            )
        )
    finally:
        server.stop()

    return write_reports(rows, server_log)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
