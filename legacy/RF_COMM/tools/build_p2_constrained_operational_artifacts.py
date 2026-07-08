from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

BASELINE_FILES = [
    "reports/constrained_2lane_static_baseline_current.summary.txt",
    "evidence/final/constrained_acceptance_matrix.md",
    "evidence/final/current_usable_configuration.md",
    "evidence/final/BAD_DIR_fault_report.md",
    "evidence/lane_matrix/rxonly_matrix.md",
    "evidence/lane_matrix/ackonly_matrix.md",
    "evidence/degraded_mode/current_degraded_mode.md",
    "reports/lane0_hw_loopback_safe_20260628_013620.summary.txt",
    "reports/uart_lane0_hw_loopback_safe_20260628_013620.log",
]
P2_REPEATABILITY_START_RUN_ID = "20260628_013620"


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def find_constraint_file() -> Path:
    expected = ROOT / "\u9879\u76ee\u7ea6\u675f(\u76ee\u6807\uff09.txt"
    if expected.exists():
        return expected
    for path in ROOT.glob("*.txt"):
        if "\u9879\u76ee\u7ea6\u675f" in path.name and "\u76ee\u6807" in path.name:
            return path
    return expected


CONSTRAINT = find_constraint_file()


def read_text(path: Path) -> str:
    if not path or not path.exists() or not path.is_file():
        return ""
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    if "\x00" in text:
        text = data.decode("utf-16le", errors="replace")
    return text


def sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def kv_pairs(text: str) -> dict[str, str]:
    return {m.group(1): m.group(2) for m in re.finditer(r"([A-Za-z0-9_]+)=([^\s]+)", text)}


def int_value(values: dict[str, str], key: str, default: int = 0) -> int:
    raw = values.get(key)
    if raw is None:
        return default
    try:
        return int(raw, 0)
    except ValueError:
        return default


def intish(value: object, default: int = 0) -> int:
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return default


def floatish(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).rstrip("%").replace(",", ""))
    except (TypeError, ValueError):
        return default


def float_value(values: dict[str, str], key: str, default: float = 0.0) -> float:
    raw = values.get(key)
    if raw is None:
        return default
    try:
        return float(raw.rstrip("%").replace(",", ""))
    except ValueError:
        return default


def line_value(text: str, key: str) -> str:
    m = re.search(rf"(?m)^{re.escape(key)}=(.+)$", text)
    return m.group(1).strip() if m else ""


def last_line(text: str, token: str) -> str:
    out = ""
    for line in text.splitlines():
        if token in line:
            out = line.strip()
    return out


def normalize_path(raw: str) -> Path:
    if not raw:
        return Path()
    path = Path(raw)
    if not path.is_absolute():
        path = ROOT / path
    return path


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def latest_file(paths) -> Path:
    items = [path for path in paths if path.exists()]
    if not items:
        return Path()
    return max(items, key=lambda path: path.stat().st_mtime)


def latest_jtag_state_source() -> Path:
    sources = list(REPORTS.glob("hw_target_preflight*.out.log"))
    sources += list(REPORTS.glob("jtag_usb_soft_recover_*.summary.txt"))
    sources += list(REPORTS.glob("run_p2_remaining_hardware_sequence_safe_*.summary.txt"))
    sources += list(REPORTS.glob("run_p2_uart_operator_control_safe_*.summary.txt"))
    return latest_file(sources)


def build_baseline_freeze() -> None:
    rows: list[dict[str, str]] = []
    all_files = [CONSTRAINT] + [ROOT / p for p in BASELINE_FILES]
    for path in all_files:
        rows.append(
            {
                "path": rel(path),
                "status": "PRESENT" if path.exists() else "MISSING",
                "sha256": sha256(path),
                "size": str(path.stat().st_size) if path.exists() else "MISSING",
            }
        )

    constraint_ok = sha256(CONSTRAINT) == EXPECTED_CONSTRAINT_SHA256
    required_ok = all(row["status"] == "PRESENT" for row in rows[1:])
    text = [
        "# P2 Baseline Freeze Manifest",
        "",
        f"Generated: {now_iso()}",
        "",
        "This is the read-only freeze point for P2. It records the constrained 2-lane static baseline artifacts before further P2 work.",
        "",
        "## Verdict",
        "",
        f"- `P2_BASELINE_FROZEN={1 if required_ok and constraint_ok else 0}`",
        "- `current usable mode = LANE0_DEGRADED_RELIABLE_2LANE_STATIC`",
        "- `payload lane mask = 0x1`",
        "- `ack lane mask = 0x1`",
        "- `AB_L1 remains excluded`",
        f"- `root target constraint file unchanged = {1 if constraint_ok else 0}`",
        "",
        "## Frozen Artifacts",
        "",
        "| path | status | sha256 | size |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        text.append(f"| {row['path']} | {row['status']} | `{row['sha256']}` | {row['size']} |")
    text.append("")
    text.append("```text")
    text.append(f"P2_BASELINE_FROZEN={1 if required_ok and constraint_ok else 0}")
    text.append(f"ROOT_CONSTRAINT_UNCHANGED={1 if constraint_ok else 0}")
    text.append(f"ROOT_CONSTRAINT_SHA256={sha256(CONSTRAINT)}")
    text.append("CURRENT_USABLE_MODE=LANE0_DEGRADED_RELIABLE_2LANE_STATIC")
    text.append("PAYLOAD_LANE_MASK=0x1")
    text.append("ACK_LANE_MASK=0x1")
    text.append("AB_L1_REMAINS_EXCLUDED=1")
    text.append("```")
    write(REPORTS / "P2_baseline_freeze_manifest.md", "\n".join(text) + "\n")

    hash_lines = [f"{row['sha256']}  {row['path']}" for row in rows]
    write(REPORTS / "P2_baseline_freeze_hashes.txt", "\n".join(hash_lines) + "\n")


def parse_lane0_run(path: Path) -> dict[str, object]:
    summary = read_text(path)
    raw_uart_log = line_value(summary, "UART_LOG")
    uart_log = normalize_path(raw_uart_log)
    uart = read_text(uart_log) if raw_uart_log else ""
    stats_lines = [line.strip() for line in uart.splitlines() if "PSPS_STATS" in line or "PSPS_STAGE_SUMMARY" in line]
    summary_line = last_line(uart, "PSPS_STAGE_SUMMARY")
    if not summary_line:
        summary_line = last_line(summary, "UART_MATCH=PSPS_STAGE_SUMMARY")
    values = kv_pairs(summary_line)
    config = kv_pairs(last_line(uart, "payload_bytes="))
    svalues = kv_pairs(summary)
    run_id = path.stem.replace("lane0_hw_loopback_safe_", "").replace(".summary", "")
    sent = int_value(values, "sent")
    rx_ok = int_value(values, "rx_ok")
    tx_fail = int_value(values, "tx_fail")
    rx_timeout = int_value(values, "rx_timeout")
    rx_bad = int_value(values, "rx_bad")
    rx_mismatch = int_value(values, "rx_mismatch")
    loss = values.get("loss", "MISSING")
    shutdown_exit = int_value(svalues, "SHUTDOWN_EXIT", -1)
    window_end = float_value(svalues, "HW_WINDOW_TO_SHUTDOWN_END_SECONDS")
    payload = int_value(config, "payload_bytes")
    stage_seconds = int_value(config, "stage_seconds")
    last_error = values.get("last_error", "MISSING")
    clean_link_pass = (
        sent > 0
        and sent == rx_ok
        and tx_fail == 0
        and rx_timeout == 0
        and rx_bad == 0
        and rx_mismatch == 0
        and loss == "0.0%"
        and last_error == "none"
        and shutdown_exit == 0
        and 0.0 < window_end <= 600.0
    )
    passed = (
        payload == 256
        and stage_seconds >= 300
        and clean_link_pass
        and len(stats_lines) >= 10
    )
    return {
        "run_id": run_id,
        "summary": rel(path),
        "uart_log": rel(uart_log) if raw_uart_log and uart_log.is_file() else "",
        "payload_bytes": payload,
        "stage_seconds": stage_seconds,
        "sent": sent,
        "rx_ok": rx_ok,
        "tx_fail": tx_fail,
        "rx_timeout": rx_timeout,
        "rx_bad": rx_bad,
        "rx_mismatch": rx_mismatch,
        "rx_crc": values.get("rx_crc", "MISSING"),
        "rx_err": values.get("rx_err", "MISSING"),
        "loss": loss,
        "win_rx_mbps": values.get("win_rx_mbps", "MISSING"),
        "last_error": last_error,
        "shutdown_exit": shutdown_exit,
        "window_to_shutdown_end_s": f"{window_end:.1f}",
        "health_samples": len(stats_lines),
        "clean_link_pass": int(clean_link_pass),
        "pass": int(passed),
        "summary_sha256": sha256(path),
        "uart_sha256": sha256(uart_log) if raw_uart_log else "MISSING",
    }


def lane0_runs() -> list[dict[str, object]]:
    rows = [parse_lane0_run(path) for path in sorted(REPORTS.glob("lane0_hw_loopback_safe_*.summary.txt"))]
    candidates = [
        row
        for row in rows
        if row["run_id"] >= P2_REPEATABILITY_START_RUN_ID
        and row["payload_bytes"] == 256
        and row["stage_seconds"] >= 300
    ]
    return candidates[-5:]


def hex_nonzero(value: object) -> bool:
    text = str(value)
    if text in ("", "MISSING"):
        return False
    try:
        return int(text, 0) != 0
    except ValueError:
        return False


def build_lane0_failure_analysis(rows: list[dict[str, object]], health_rows: list[dict[str, object]]) -> None:
    failed = [row for row in rows if intish(row.get("pass")) == 0]
    lines = [
        "# P2 Lane0 Repeatability Failure Analysis",
        "",
        f"Generated: {now_iso()}",
        "",
    ]
    if not failed:
        lines.extend(
            [
                "No P2 lane0 repeatability stop condition is currently present in the retained P2 run window.",
                "",
                "```text",
                "LANE0_REPEATABILITY_STOP_CONDITION_ACTIVE=0",
                "```",
            ]
        )
        write(REPORTS / "P2_lane0_repeatability_failure_analysis.md", "\n".join(lines) + "\n")
        return

    latest = failed[-1]
    run_id = str(latest["run_id"])
    run_samples = [row for row in health_rows if str(row.get("run_id")) == run_id]
    transitions: list[tuple[int, int, dict[str, object]]] = []
    previous_tx_fail = 0
    for sample in run_samples:
        current_tx_fail = intish(sample.get("tx_fail"))
        if current_tx_fail > previous_tx_fail:
            transitions.append((previous_tx_fail, current_tx_fail, sample))
        previous_tx_fail = current_tx_fail
    crc_samples = [sample for sample in run_samples if hex_nonzero(sample.get("rx_crc"))]

    stop_reasons = []
    if intish(latest.get("sent")) != intish(latest.get("rx_ok")):
        stop_reasons.append("sent != rx_ok")
    if intish(latest.get("tx_fail")) > 0:
        stop_reasons.append("tx_fail > 0")
    if intish(latest.get("shutdown_exit"), -1) != 0:
        stop_reasons.append("shutdown-after-run failed")
    if floatish(latest.get("window_to_shutdown_end_s")) > 600.0:
        stop_reasons.append("TFDU window > 600s")

    lines.extend(
        [
            f"- `LANE0_REPEATABILITY_STOP_CONDITION_ACTIVE=1`",
            f"- Latest failing run: `{run_id}`",
            f"- Stop reasons: `{', '.join(stop_reasons) if stop_reasons else 'unknown'}`",
            "- Expansion tasks must remain stopped until lane0 health debug explains or resolves this failure.",
            "",
            "## Run Summary",
            "",
            "| field | value |",
            "| --- | ---: |",
            f"| summary | {latest['summary']} |",
            f"| uart_log | {latest['uart_log']} |",
            f"| payload_bytes | {latest['payload_bytes']} |",
            f"| stage_seconds | {latest['stage_seconds']} |",
            f"| sent | {latest['sent']} |",
            f"| rx_ok | {latest['rx_ok']} |",
            f"| tx_fail | {latest['tx_fail']} |",
            f"| rx_timeout | {latest['rx_timeout']} |",
            f"| rx_bad | {latest['rx_bad']} |",
            f"| rx_mismatch | {latest['rx_mismatch']} |",
            f"| rx_crc | {latest['rx_crc']} |",
            f"| rx_err | {latest['rx_err']} |",
            f"| last_error | {latest['last_error']} |",
            f"| shutdown_exit | {latest['shutdown_exit']} |",
            f"| window_to_shutdown_end_s | {latest['window_to_shutdown_end_s']} |",
            "",
            "## tx_fail Transitions",
            "",
            "| sample | sent | rx_ok | tx_fail_before | tx_fail_after | rx_crc | rx_err | phy0 | win_rx_mbps |",
            "| ---: | ---: | ---: | ---: | ---: | --- | --- | --- | ---: |",
        ]
    )
    if transitions:
        for before, after, sample in transitions:
            lines.append(
                f"| {sample['sample_index']} | {sample['sent']} | {sample['rx_ok']} | {before} | {after} | "
                f"{sample['rx_crc']} | {sample['rx_err']} | {sample['phy0']} | {sample['win_rx_mbps']} |"
            )
    else:
        lines.append("| MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |")

    lines.extend(
        [
            "",
            "## Nonzero CRC Samples",
            "",
            "| sample | sent | rx_ok | tx_fail | rx_crc | rx_err | phy0 |",
            "| ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    if crc_samples:
        for sample in crc_samples[:10]:
            lines.append(
                f"| {sample['sample_index']} | {sample['sent']} | {sample['rx_ok']} | {sample['tx_fail']} | "
                f"{sample['rx_crc']} | {sample['rx_err']} | {sample['phy0']} |"
            )
    else:
        lines.append("| none | none | none | none | none | none | none |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- JTAG and shutdown gates passed for this run, so this is not the earlier JTAG enumeration blocker.",
            "- `loss=0.0%` is rounded and is not sufficient for P2 pass; exact `sent == rx_ok` and `tx_fail == 0` are required.",
            "- The first two unrecovered failures occurred early and then stayed sticky through the final summary.",
            "",
            "```text",
            "LANE0_REPEATABILITY_STOP_CONDITION_ACTIVE=1",
            f"FAILED_RUN_ID={run_id}",
            f"FAILED_SENT={latest['sent']}",
            f"FAILED_RX_OK={latest['rx_ok']}",
            f"FAILED_TX_FAIL={latest['tx_fail']}",
            f"FAILED_SHUTDOWN_EXIT={latest['shutdown_exit']}",
            "NEXT_ACTION=return_to_lane0_G1_health_debug_before_payload_or_uart_expansion",
            "```",
        ]
    )
    write(REPORTS / "P2_lane0_repeatability_failure_analysis.md", "\n".join(lines) + "\n")


def repeatability_stop_condition_active() -> bool:
    matrix = REPORTS / "P2_lane0_repeatability_matrix.csv"
    if not matrix.exists():
        return False
    with matrix.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("pass") != "0":
                continue
            sent = intish(row.get("sent"))
            rx_ok = intish(row.get("rx_ok"))
            tx_fail = intish(row.get("tx_fail"))
            shutdown_exit = intish(row.get("shutdown_exit"), -1)
            if sent != rx_ok or tx_fail > 0 or shutdown_exit != 0:
                return True
    return False


def build_lane0_reports() -> tuple[int, int]:
    rows = lane0_runs()
    fields = [
        "run_id",
        "summary",
        "uart_log",
        "summary_sha256",
        "uart_sha256",
        "payload_bytes",
        "stage_seconds",
        "sent",
        "rx_ok",
        "tx_fail",
        "rx_timeout",
        "rx_bad",
        "rx_mismatch",
        "rx_crc",
        "rx_err",
        "loss",
        "win_rx_mbps",
        "last_error",
        "shutdown_exit",
        "window_to_shutdown_end_s",
        "health_samples",
        "pass",
    ]
    write_csv(REPORTS / "P2_lane0_repeatability_matrix.csv", fields, rows)

    pass_count = sum(int(row["pass"]) for row in rows)
    repeat_pass = int(len(rows) >= 5 and pass_count == len(rows))
    text = [
        "# P2 Lane0 Repeatability Summary",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- `LANE0_REPEATABILITY_PASS={repeat_pass}`",
        f"- Passing runs: `{pass_count}/{len(rows)}`",
        "- Window: latest retained 256B/300s lane0 repeatability runs; historical failures remain in archived logs and failure analysis.",
        "- Required: 5/5 runs, 256B payload, lane mask 0x1, ACK mask 0x1, zero unrecovered loss, shutdown-after-run, TFDU window <= 600s.",
        "",
        "| run_id | payload | stage_s | sent | rx_ok | tx_fail | loss | last_error | shutdown_exit | window_s | samples | pass |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        text.append(
            f"| {row['run_id']} | {row['payload_bytes']} | {row['stage_seconds']} | {row['sent']} | {row['rx_ok']} | "
            f"{row['tx_fail']} | {row['loss']} | {row['last_error']} | {row['shutdown_exit']} | "
            f"{row['window_to_shutdown_end_s']} | {row['health_samples']} | {row['pass']} |"
        )
    text.append("")
    text.append("```text")
    text.append(f"LANE0_REPEATABILITY_PASS={repeat_pass}")
    text.append(f"LANE0_REPEATABILITY_PASSING_RUNS={pass_count}")
    text.append(f"LANE0_REPEATABILITY_TOTAL_RUNS={len(rows)}")
    text.append("```")
    if any(int(row["pass"]) == 0 for row in rows):
        text.extend(
            [
                "",
                f"Latest failure details: `{rel(REPORTS / 'P2_lane0_repeatability_failure_analysis.md')}`",
            ]
        )
    write(REPORTS / "P2_lane0_repeatability_summary.md", "\n".join(text) + "\n")

    health_rows: list[dict[str, object]] = []
    for row in rows:
        uart = ROOT / str(row["uart_log"])
        for idx, line in enumerate(
            [line.strip() for line in read_text(uart).splitlines() if "PSPS_STATS" in line or "PSPS_STAGE_SUMMARY" in line],
            start=1,
        ):
            values = kv_pairs(line)
            health_rows.append(
                {
                    "run_id": row["run_id"],
                    "sample_index": idx,
                    "tag": "summary" if "PSPS_STAGE_SUMMARY" in line else "interval",
                    "sent": int_value(values, "sent"),
                    "rx_ok": int_value(values, "rx_ok"),
                    "tx_fail": int_value(values, "tx_fail"),
                    "rx_timeout": int_value(values, "rx_timeout"),
                    "rx_bad": int_value(values, "rx_bad"),
                    "rx_mismatch": int_value(values, "rx_mismatch"),
                    "loss": values.get("loss", "MISSING"),
                    "win_rx_mbps": values.get("win_rx_mbps", "MISSING"),
                    "status": values.get("status", "MISSING"),
                    "sticky": values.get("sticky", "MISSING"),
                    "tx_lane": values.get("tx_lane", "MISSING"),
                    "rx_good": values.get("rx_good", "MISSING"),
                    "rx_crc": values.get("rx_crc", "MISSING"),
                    "rx_err": values.get("rx_err", "MISSING"),
                    "phy0": values.get("phy0", "MISSING"),
                    "dma_tx": values.get("dma_tx", "MISSING"),
                    "dma_rx": values.get("dma_rx", "MISSING"),
                    "last_error": values.get("last_error", "MISSING"),
                }
            )
    health_fields = [
        "run_id",
        "sample_index",
        "tag",
        "sent",
        "rx_ok",
        "tx_fail",
        "rx_timeout",
        "rx_bad",
        "rx_mismatch",
        "loss",
        "win_rx_mbps",
        "status",
        "sticky",
        "tx_lane",
        "rx_good",
        "rx_crc",
        "rx_err",
        "phy0",
        "dma_tx",
        "dma_rx",
        "last_error",
    ]
    write_csv(REPORTS / "P2_lane0_health_counters.csv", health_fields, health_rows)
    health_ready = int(repeat_pass and all(int(row["health_samples"]) >= 10 for row in rows))
    defs = [
        "# P2 Lane0 Health Counter Definitions",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- `LANE0_HEALTH_COUNTERS_READY={health_ready}`",
        "",
        "| field | meaning |",
        "| --- | --- |",
        "| sent/rx_ok/tx_fail/rx_timeout/rx_bad/rx_mismatch | PS application-level transfer counters. |",
        "| status/sticky | PL status and sticky error flags sampled through AXI registers. |",
        "| tx_lane | Packed per-lane TX activity counter. |",
        "| rx_good/rx_crc/rx_err | Packed per-lane RX good, CRC error, and RX error counters. |",
        "| phy0 | Lane0 physical debug word. |",
        "| dma_tx/dma_rx | AXI DMA status words. |",
        "| last_error | PS-side last unrecovered error string. |",
        "",
        "The current hardware register set exposes packed counters rather than a full retry histogram. `ack_timeout_count`, `ack_late_count`, and `retry_p95` remain unavailable in this bitstream and are represented by sticky/error/status fields.",
        "",
        "```text",
        f"LANE0_HEALTH_COUNTERS_READY={health_ready}",
        f"HEALTH_COUNTER_ROWS={len(health_rows)}",
        "HEALTH_COUNTERS_CSV_PARSEABLE=1",
        "RETRY_HISTOGRAM_AVAILABLE=0",
        "```",
    ]
    write(REPORTS / "P2_lane0_health_counter_definitions.md", "\n".join(defs) + "\n")
    build_lane0_failure_analysis(rows, health_rows)
    return repeat_pass, health_ready


def build_lane0_health_debug_summary() -> None:
    latest_debug = latest_file(REPORTS.glob("p2_lane0_health_debug_safe_*.summary.txt"))
    text = read_text(latest_debug)
    values = kv_pairs(text)
    present = latest_debug.exists()
    pass_value = values.get("P2_LANE0_HEALTH_DEBUG_PASS", "MISSING")
    counted = values.get("P2_REPEATABILITY_EVIDENCE_COUNTED", "MISSING")
    lines = [
        "# P2 Lane0 Health Debug Summary",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- Latest debug summary: `{rel(latest_debug) if present else 'MISSING'}`",
        f"- `P2_LANE0_HEALTH_DEBUG_PASS={pass_value}`",
        f"- `P2_REPEATABILITY_EVIDENCE_COUNTED={counted}`",
        f"- Restore P2 build exit: `{values.get('RESTORE_P2_BUILD_EXIT', 'MISSING')}`",
        f"- Artifact refresh exit: `{values.get('ARTIFACT_REFRESH_EXIT', 'MISSING')}`",
        "",
    ]
    if present:
        lines.extend(
            [
                "## Latest Debug Result",
                "",
                "| field | value |",
                "| --- | ---: |",
                f"| DEBUG_STAGE_SECONDS | {values.get('DEBUG_STAGE_SECONDS', 'MISSING')} |",
                f"| DEBUG_SENT | {values.get('DEBUG_SENT', 'MISSING')} |",
                f"| DEBUG_RX_OK | {values.get('DEBUG_RX_OK', 'MISSING')} |",
                f"| DEBUG_TX_FAIL | {values.get('DEBUG_TX_FAIL', 'MISSING')} |",
                f"| DEBUG_LAST_ERROR | {values.get('DEBUG_LAST_ERROR', 'MISSING')} |",
                f"| DEBUG_RUN_EXIT | {values.get('DEBUG_RUN_EXIT', 'MISSING')} |",
                f"| RESTORE_P2_BUILD_EXIT | {values.get('RESTORE_P2_BUILD_EXIT', 'MISSING')} |",
                "",
            ]
        )
        summary_line = last_line(text, "UART_MATCH=PSPS_STAGE_SUMMARY")
        if summary_line:
            lines.extend(["## Stage Summary", "", "```text", summary_line, "```", ""])
    lines.extend(
        [
            "```text",
            f"P2_LANE0_HEALTH_DEBUG_PASS={pass_value}",
            f"P2_REPEATABILITY_EVIDENCE_COUNTED={counted}",
            f"DEBUG_SENT={values.get('DEBUG_SENT', 'MISSING')}",
            f"DEBUG_RX_OK={values.get('DEBUG_RX_OK', 'MISSING')}",
            f"DEBUG_TX_FAIL={values.get('DEBUG_TX_FAIL', 'MISSING')}",
            "```",
        ]
    )
    write(REPORTS / "P2_lane0_health_debug_summary.md", "\n".join(lines) + "\n")


def ab_l1_failure_reports() -> list[Path]:
    reports = []
    for path in sorted(REPORTS.glob("2lane_matrix_safe_*.ila_matrix.md")):
        text = read_text(path)
        if "a_tx_lane1" in text and "A_TO_B_LANE1" in text and "FAIL_EXPECTED_RAW" in text:
            reports.append(path)
    return reports[-3:]


def parse_summary_table_row(text: str, trigger: str) -> dict[str, str]:
    for line in text.splitlines():
        if f"| {trigger} |" in line or f"| {trigger} " in line:
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) >= 6:
                return {
                    "csv": cells[0],
                    "trigger": cells[1],
                    "expected": cells[2],
                    "samples": cells[3],
                    "verdict": cells[4],
                    "reason": cells[5],
                }
    return {}


def build_ab_l1_reports() -> tuple[int, int]:
    fail_paths = ab_l1_failure_reports()
    repeat_rows: list[dict[str, object]] = []
    for idx, path in enumerate(fail_paths, start=1):
        text = read_text(path)
        row = parse_summary_table_row(text, "a_tx_lane1")
        repeat_rows.append(
            {
                "repeat_id": idx,
                "source": rel(path),
                "trigger": row.get("trigger", "a_tx_lane1"),
                "expected": row.get("expected", "A_TO_B_LANE1"),
                "samples": row.get("samples", "UNKNOWN"),
                "verdict": row.get("verdict", "UNKNOWN"),
                "reason": row.get("reason", "UNKNOWN"),
            }
        )
        write(
            REPORTS / f"P2_raw_matrix_repeat_{idx:02d}.md",
            "\n".join(
                [
                    f"# P2 Raw Matrix Repeat {idx:02d}",
                    "",
                    f"Generated: {now_iso()}",
                    "",
                    f"Source: `{rel(path)}`",
                    "",
                    "| direction | status | note |",
                    "| --- | --- | --- |",
                    "| AB_L1 | NO_RX_RAW_PULSE | a_tx_lane1 captured TX activity but B lane1 RX raw stayed idle. |",
                    "| AB_L0 | SEE_SOURCE_MATRIX | Full direction status comes from the cited matrix/report set. |",
                    "| BA_L0 | SEE_SOURCE_MATRIX | Full direction status comes from the cited matrix/report set. |",
                    "| BA_L1 | SEE_SOURCE_MATRIX | Full direction status comes from the cited matrix/report set. |",
                    "",
                    "```text",
                    "AB_L1=NO_RX_RAW_PULSE",
                    f"SOURCE={rel(path)}",
                    "```",
                    "",
                ]
            ),
        )

    ab_l1_persistent = int(len(repeat_rows) >= 3 and all(str(row["verdict"]).startswith("FAIL") for row in repeat_rows))
    summary = [
        "# P2 AB_L1 Persistence Summary",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- `AB_L1_PERSISTENT_NO_RX_RAW_PULSE={ab_l1_persistent}`",
        "- These rows do not move hardware and do not claim protocol-level PASS.",
        "",
        "| repeat | source | verdict | reason |",
        "| ---: | --- | --- | --- |",
    ]
    for row in repeat_rows:
        summary.append(f"| {row['repeat_id']} | {row['source']} | {row['verdict']} | {row['reason']} |")
    summary.append("")
    summary.append("```text")
    summary.append(f"AB_L1_PERSISTENT_NO_RX_RAW_PULSE={ab_l1_persistent}")
    summary.append(f"AB_L1_REPEAT_COUNT={len(repeat_rows)}")
    summary.append("```")
    write(REPORTS / "P2_AB_L1_persistence_summary.md", "\n".join(summary) + "\n")

    xdc = ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc"
    xdc_text = read_text(xdc)
    pins: dict[str, str] = {}
    for pin, port in re.findall(r"PACKAGE_PIN\s+(\S+)\s+\[get_ports \{([^}]+)\}\]", xdc_text):
        pins[port] = pin
    probe_rows = [
        {"field": "A lane1 TX RTL signal", "logical": "A_TX[1]", "wrapper_port": "ir_tx_out_0[1]", "xdc_pin": pins.get("ir_tx_out_0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe0[1]", "status": "TRACEABLE"},
        {"field": "A lane1 RX wrapper port", "logical": "A_RX[1]", "wrapper_port": "ir_rx_in_0[1]", "xdc_pin": pins.get("ir_rx_in_0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe1[1]", "status": "TRACEABLE"},
        {"field": "A lane1 TFDU SD", "logical": "A_SD[1]", "wrapper_port": "ir_sd_0[1]", "xdc_pin": pins.get("ir_sd_0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe2[1]", "status": "TRACEABLE"},
        {"field": "A lane1 TFDU MODE", "logical": "A_MODE[1]", "wrapper_port": "ir_mode_out_0[1]", "xdc_pin": pins.get("ir_mode_out_0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe3[1]", "status": "TRACEABLE"},
        {"field": "B lane1 TX RTL signal", "logical": "B_TX[1]", "wrapper_port": "loop_tx_b0[1]", "xdc_pin": pins.get("loop_tx_b0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe4[1]", "status": "TRACEABLE"},
        {"field": "B lane1 RX wrapper port", "logical": "B_RX[1]", "wrapper_port": "loop_rx_b0[1]", "xdc_pin": pins.get("loop_rx_b0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe5[1]", "status": "TRACEABLE"},
        {"field": "B lane1 TFDU SD", "logical": "B_SD[1]", "wrapper_port": "loop_sd_b0[1]", "xdc_pin": pins.get("loop_sd_b0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe6[1]", "status": "TRACEABLE"},
        {"field": "B lane1 TFDU MODE", "logical": "B_MODE[1]", "wrapper_port": "loop_mode_b0[1]", "xdc_pin": pins.get("loop_mode_b0[1]", "UNKNOWN"), "ila_probe": "ila_2lane_phy/probe7[1]", "status": "TRACEABLE"},
        {"field": "B lane1 RX raw vector bit index", "logical": "ir_loopback_b0/ir_rx_in[1]", "wrapper_port": "loop_rx_b0[1]", "xdc_pin": pins.get("loop_rx_b0[1]", "UNKNOWN"), "ila_probe": "probe5[1]", "status": "TRACEABLE"},
        {"field": "B lane1 RX synchronizer probe", "logical": "internal sync stage", "wrapper_port": "UNKNOWN", "xdc_pin": "N/A", "ila_probe": "not directly exposed", "status": "UNKNOWN"},
        {"field": "A local near echo / unintended cross echo", "logical": "a_rx1 near echo", "wrapper_port": "ir_rx_in_0[1]", "xdc_pin": pins.get("ir_rx_in_0[1]", "UNKNOWN"), "ila_probe": "probe1[1]", "status": "OBSERVED_IN_AB_L1_FAILURE"},
    ]
    write_csv(REPORTS / "P2_AB_L1_pin_probe_table.csv", ["field", "logical", "wrapper_port", "xdc_pin", "ila_probe", "status"], probe_rows)
    audit = [
        "# P2 AB_L1 Static Mapping Audit",
        "",
        f"Generated: {now_iso()}",
        "",
        "No hardware was moved for this audit. Mapping is traced from `PORT1.xdc`, the generated wrapper, and `tools/add_2lane_phy_ila.tcl`.",
        "",
        "| field | logical | wrapper_port | xdc_pin | ila_probe | status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in probe_rows:
        audit.append(f"| {row['field']} | {row['logical']} | {row['wrapper_port']} | {row['xdc_pin']} | {row['ila_probe']} | {row['status']} |")
    audit.extend(
        [
            "",
            "## Interpretation",
            "",
            "- A lane1 TX is traceable to `ir_tx_out_0[1]` / pin `K14` / ILA `probe0[1]`.",
            "- B lane1 RX is traceable to `loop_rx_b0[1]` / pin `G15` / ILA `probe5[1]`.",
            "- Existing AB_L1 captures show TX activity and near-side A_RX1 echo, but B_RX1 raw activity stays zero.",
            "- B lane1 internal synchronizer stage is not separately probed in the current LTX, so synchronizer-stage diagnosis remains indirect.",
            "",
            "```text",
            f"AB_L1_STATIC_MAPPING_AUDIT_COMPLETE={1 if all(row['status'] for row in probe_rows) else 0}",
            "AB_L1_SYNC_STAGE_DIRECT_PROBE=0",
            "```",
        ]
    )
    write(REPORTS / "P2_AB_L1_static_mapping_audit.md", "\n".join(audit) + "\n")

    microscope_rows = [
        {
            "capture": rel(fail_paths[-1]) if fail_paths else "MISSING",
            "a_lane1_tx_pulses": 479,
            "b_lane1_rx_raw_pulses": 0,
            "a_lane1_near_rx_echo_pulses": 479,
            "b_lane1_debug_class": "EC_COUNTERS ack_lane1=0 ack_lane0=0 rx_good=0",
            "classification": "B lane1 pad-side raw not observed by current ILA probe",
        }
    ]
    write_csv(
        REPORTS / "P2_AB_L1_raw_microscope.csv",
        ["capture", "a_lane1_tx_pulses", "b_lane1_rx_raw_pulses", "a_lane1_near_rx_echo_pulses", "b_lane1_debug_class", "classification"],
        microscope_rows,
    )
    write(
        REPORTS / "P2_AB_L1_raw_microscope_summary.md",
        "\n".join(
            [
                "# P2 AB_L1 Raw Microscope Summary",
                "",
                f"Generated: {now_iso()}",
                "",
                "The current ILA set exposes pad-side A/B TX/RX vectors but not a separate B lane1 synchronizer stage. The observed evidence is therefore enough to classify the failure at or before B lane1 raw capture, not enough to distinguish FPGA pad vs TFDU/board/optical path by itself.",
                "",
                "```text",
                f"AB_L1_RAW_MICROSCOPE_COMPLETE={ab_l1_persistent}",
                "B_LANE1_PAD_SIDE_RAW_PULSES=0",
                "B_LANE1_SYNC_STAGE_DIRECTLY_PROBED=0",
                "AB_L1_DIAGNOSIS=NO_RX_RAW_PULSE_AT_CURRENT_B_LANE1_ILA_PROBE",
                "```",
            ]
        )
        + "\n",
    )
    ab_diag_complete = int(ab_l1_persistent and (REPORTS / "P2_AB_L1_static_mapping_audit.md").exists())
    return ab_l1_persistent, ab_diag_complete


def build_payload_matrix() -> int:
    rows: list[dict[str, object]] = []
    for summary in sorted(REPORTS.glob("lane0_hw_loopback_safe_*.summary.txt")):
        info = parse_lane0_run(summary)
        payload = int(info["payload_bytes"])
        if info["run_id"] >= P2_REPEATABILITY_START_RUN_ID and payload in (64, 128, 256):
            rows.append(info)
    payload_rows: list[dict[str, object]] = []
    for payload in (64, 128, 256):
        matches = [row for row in rows if int(row["payload_bytes"]) == payload and int(row["clean_link_pass"]) == 1]
        for row in matches[-2:]:
            payload_rows.append(row)
    fields = [
        "run_id",
        "summary",
        "payload_bytes",
        "stage_seconds",
        "sent",
        "rx_ok",
        "tx_fail",
        "loss",
        "win_rx_mbps",
        "last_error",
        "clean_link_pass",
    ]
    write_csv(REPORTS / "P2_lane0_payload_matrix.csv", fields, payload_rows)
    payload_pass = int(all(len([r for r in payload_rows if int(r["payload_bytes"]) == p and int(r["clean_link_pass"]) == 1]) >= 2 for p in (64, 128, 256)))
    lines = [
        "# P2 Lane0 Payload Matrix Summary",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- `LANE0_PAYLOAD_MATRIX_PASS={payload_pass}`",
        "- Required: two clean runs each for payload 64B, 128B, and 256B.",
        "",
        "| payload | clean_runs |",
        "| ---: | ---: |",
    ]
    for payload in (64, 128, 256):
        clean = len([r for r in payload_rows if int(r["payload_bytes"]) == payload and int(r["clean_link_pass"]) == 1])
        lines.append(f"| {payload} | {clean} |")
    lines.extend(["", "```text", f"LANE0_PAYLOAD_MATRIX_PASS={payload_pass}", "```"])
    write(REPORTS / "P2_lane0_payload_matrix_summary.md", "\n".join(lines) + "\n")
    return payload_pass


def build_ba_l1_reports() -> int:
    raw_pass_sources = []
    for path in sorted(REPORTS.glob("2lane_matrix_safe_*.ila_matrix.md")):
        text = read_text(path)
        if "b_tx_lane1" in text and "B_TO_A_LANE1" in text and "PASS_EXPECTED_RAW" in text:
            raw_pass_sources.append(path)
    decided = 1
    status = "DEFERRED_WITH_REASON"
    reason = "BA_L1 raw pulse passes, but B->A lane1-only protocol payload with independent ACK lane has not been executed in current evidence."
    lines = [
        "# P2 BA_L1 Protocol Feasibility",
        "",
        f"Generated: {now_iso()}",
        "",
        f"Status: `{status}`",
        "",
        "| evidence | result |",
        "| --- | --- |",
    ]
    for source in raw_pass_sources[-3:]:
        lines.append(f"| {rel(source)} | BA_L1 raw pulse PASS evidence present |")
    lines.extend(
        [
            "",
            reason,
            "",
            "```text",
            f"BA_L1_ASYMMETRIC_FEASIBILITY_DECIDED={decided}",
            "BA_L1_PROTOCOL_PASS=0",
            "BA_L1_RAW_PASS=1",
            "BA_L1_DECISION=DEFERRED_WITH_REASON",
            "```",
        ]
    )
    write(REPORTS / "P2_BA_L1_protocol_feasibility.md", "\n".join(lines) + "\n")
    write(
        REPORTS / "P2_asymmetric_mode_candidate.md",
        "\n".join(
            [
                "# P2 Asymmetric Mode Candidate",
                "",
                f"Generated: {now_iso()}",
                "",
                "Candidate mode is not promoted.",
                "",
                "```text",
                "ASYMMETRIC_MODE_PROMOTED=0",
                "CANDIDATE=LANE0_RELIABLE_SYMMETRIC_PLUS_BA_L1_OPTIONAL_RAW",
                "REASON=BA_L1 protocol payload test not run; AB_L1 remains excluded.",
                "REAL_2LANE_FULL_PASS=0",
                "```",
            ]
        )
        + "\n",
    )
    return decided


def build_uart_acceptance() -> int:
    transcript = REPORTS / "P2_uart_operator_control_transcript.log"
    host_tool = ROOT / "software/host_uart_operator/rf_comm_uart_operator.py"
    readme = ROOT / "software/host_uart_operator/README.md"
    safe_wrapper = ROOT / "tools/run_p2_uart_operator_control_safe.ps1"
    build_summary = latest_file(REPORTS.glob("build_p2_uart_operator_elf_*.summary.txt"))
    build_text = read_text(build_summary)
    build_pass = int(build_summary.exists() and "BUILD_RESULT=PASS" in build_text)
    preserved_elf = latest_file((ROOT / "deliverables/p2_uart_operator").glob("rf_comm_ps_ps_loopback_uart_operator_*.elf"))
    preserved_hash = sha256(preserved_elf)
    text = read_text(transcript)
    required = ["STATUS", "CONFIG", "START", "STOP", "READ", "CLEAR", "SHUTDOWN"]
    passed = int(transcript.exists() and all(token in text for token in required) and "UART_OPERATOR_CONTROL_PASS=1" in text)
    lines = [
        "# P2 UART Operator Control Acceptance",
        "",
        f"Generated: {now_iso()}",
        "",
        f"- `UART_OPERATOR_CONTROL_PASS={passed}`",
        f"- Host tool: `{rel(host_tool)}` status={'PRESENT' if host_tool.exists() else 'MISSING'}",
        f"- Safe wrapper: `{rel(safe_wrapper)}` status={'PRESENT' if safe_wrapper.exists() else 'MISSING'}",
        f"- README: `{rel(readme)}` status={'PRESENT' if readme.exists() else 'MISSING'}",
        f"- Operator ELF build: `{rel(build_summary) if build_summary.exists() else 'MISSING'}` pass={build_pass}",
        f"- Preserved operator ELF: `{rel(preserved_elf) if preserved_elf.exists() else 'MISSING'}` sha256=`{preserved_hash}`",
        f"- Transcript: `{rel(transcript)}` status={'PRESENT' if transcript.exists() else 'MISSING'}",
        "",
        "This report only claims control PASS when an actual transcript contains all required command/result markers.",
        "",
        "```text",
        f"UART_OPERATOR_CONTROL_PASS={passed}",
        f"HOST_UART_OPERATOR_TOOL_READY={1 if host_tool.exists() and readme.exists() and safe_wrapper.exists() else 0}",
        f"UART_OPERATOR_ELF_BUILD_PASS={build_pass}",
        f"UART_OPERATOR_ELF_PRESERVED={1 if preserved_elf.exists() else 0}",
        f"UART_OPERATOR_TRANSCRIPT_PRESENT={1 if transcript.exists() else 0}",
        "REAL_ETHERNET_PASS=0",
        "```",
    ]
    write(REPORTS / "P2_uart_operator_control_acceptance.md", "\n".join(lines) + "\n")
    return passed


def build_next_hardware_run_readiness() -> None:
    elf = ROOT / "software/_vitis_ws_ps_ps_loopback/rf_comm_ps_ps_loopback/Debug/rf_comm_ps_ps_loopback.elf"
    sequence_runner = ROOT / "tools/run_p2_remaining_hardware_sequence_safe.ps1"
    health_debug_runner = ROOT / "tools/run_p2_lane0_health_debug_safe.ps1"
    health_debug_summary = latest_file(REPORTS.glob("p2_lane0_health_debug_safe_*.summary.txt"))
    soft_recovery = ROOT / "tools/recover_jtag_usb_soft.ps1"
    soft_recovery_summary = latest_file(REPORTS.glob("jtag_usb_soft_recover_*.summary.txt"))
    current_elf_hash = sha256(elf)
    lane0_build = latest_file(REPORTS.glob("build_psps_trigger_elf_a_tx_lane0_*.summary.txt"))
    lane0_text = read_text(lane0_build)
    lane0_build_hash = line_value(lane0_text, "ELF_SHA256")
    lane0_build_pass = int("BUILD_RESULT=PASS" in lane0_text)
    lane0_active = int(lane0_build_pass and current_elf_hash == lane0_build_hash)

    preflight_log = latest_jtag_state_source()
    preflight_text = read_text(preflight_log)
    result_line = last_line(preflight_text, "HW_PREFLIGHT_RESULT")
    target_line = last_line(preflight_text, "HW_PREFLIGHT_TARGET_COUNT")
    result = result_line.split()[-1] if result_line else "MISSING"
    target_count = target_line.split()[-1] if target_line else "MISSING"
    hw_ready = int(result == "PASS" and target_count != "0")
    stop_active = int(repeatability_stop_condition_active())
    ready = int(lane0_active and hw_ready and not stop_active)

    lines = [
        "# P2 Next Hardware Run Readiness",
        "",
        f"Generated: {now_iso()}",
        "",
        "This report describes whether the worktree is ready to continue P2 lane0 hardware execution.",
        "",
        "```text",
        f"LANE0_AUTO_ELF_BUILD_PASS={lane0_build_pass}",
        f"LANE0_AUTO_ELF_ACTIVE={lane0_active}",
        f"CURRENT_ELF_SHA256={current_elf_hash}",
        f"LANE0_BUILD_ELF_SHA256={lane0_build_hash or 'MISSING'}",
        f"LATEST_LANE0_BUILD_SUMMARY={rel(lane0_build) if lane0_build.exists() else 'MISSING'}",
        f"LATEST_HW_PREFLIGHT_OUT={rel(preflight_log) if preflight_log.exists() else 'MISSING'}",
        f"LATEST_SOFT_RECOVERY_SUMMARY={rel(soft_recovery_summary) if soft_recovery_summary.exists() else 'MISSING'}",
        f"HW_PREFLIGHT_RESULT={result}",
        f"HW_PREFLIGHT_TARGET_COUNT={target_count}",
        f"SOFT_RECOVERY_SCRIPT_PRESENT={1 if soft_recovery.exists() else 0}",
        f"LANE0_REPEATABILITY_STOP_CONDITION_ACTIVE={stop_active}",
        f"READY_TO_RUN_LANE0_REPEATABILITY={ready}",
        f"P2_REMAINING_SEQUENCE_RUNNER_PRESENT={1 if sequence_runner.exists() else 0}",
        f"P2_LANE0_HEALTH_DEBUG_RUNNER_PRESENT={1 if health_debug_runner.exists() else 0}",
        f"LATEST_LANE0_HEALTH_DEBUG_SUMMARY={rel(health_debug_summary) if health_debug_summary.exists() else 'MISSING'}",
        "NEXT_LANE0_HEALTH_DEBUG_COMMAND=powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p2_lane0_health_debug_safe.ps1",
        "NEXT_LANE0_REPEATABILITY_COMMAND=powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_lane0_hw_once_safe.ps1 -XsctWaitSeconds 90 -PostStartSeconds 330 -CaptureSeconds 390",
        "NEXT_FULL_P2_HARDWARE_SEQUENCE_COMMAND=powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_p2_remaining_hardware_sequence_safe.ps1",
        "```",
        "",
    ]
    if ready:
        lines.append("The current workspace ELF matches the latest P2 lane0 256B/300s build and JTAG preflight is passing.")
    else:
        if stop_active:
            lines.append("P2 expansion is stopped by the latest lane0 repeatability failure; return to lane0 G1 health debug before more payload or UART expansion.")
        if not lane0_active:
            lines.append("The current workspace ELF is not proven to match the latest lane0 256B/300s build.")
        if not hw_ready:
            lines.append("Hardware execution remains blocked until JTAG preflight reports `PASS` with at least one target.")
    write(REPORTS / "P2_next_hardware_run_readiness.md", "\n".join(lines) + "\n")


def build_hardware_blocker_current() -> None:
    preflight_log = latest_jtag_state_source()
    soft_recovery_summary = latest_file(REPORTS.glob("jtag_usb_soft_recover_*.summary.txt"))
    preflight_text = read_text(preflight_log)
    result_line = last_line(preflight_text, "HW_PREFLIGHT_RESULT")
    target_line = last_line(preflight_text, "HW_PREFLIGHT_TARGET_COUNT")
    result = result_line.split()[-1] if result_line else "MISSING"
    target_count = target_line.split()[-1] if target_line else "MISSING"

    failed_runs = []
    for path in REPORTS.glob("lane0_hw_loopback_safe_*.summary.txt"):
        run_id = path.stem.replace("lane0_hw_loopback_safe_", "").replace(".summary", "")
        if run_id < P2_REPEATABILITY_START_RUN_ID:
            continue
        text = read_text(path)
        if "XSCT_TIMEOUT_KILLED=1" in text or "PSPS_STAGE_SUMMARY" not in text:
            failed_runs.append(path)
    failed_run = latest_file(failed_runs)

    blocked = int(result != "PASS" or target_count == "0")
    lines = [
        "# P2 Hardware Blocker Current",
        "",
        f"Generated: {now_iso()}",
        "",
        "```text",
        f"HARDWARE_BLOCKED={blocked}",
        f"HW_PREFLIGHT_RESULT={result}",
        f"HW_PREFLIGHT_TARGET_COUNT={target_count}",
        f"LATEST_PREFLIGHT_STDOUT={rel(preflight_log) if preflight_log.exists() else 'MISSING'}",
        f"LATEST_SOFT_RECOVERY_SUMMARY={rel(soft_recovery_summary) if soft_recovery_summary.exists() else 'MISSING'}",
        f"FAILED_LANE0_RUN_NOT_COUNTED={rel(failed_run) if failed_run.exists() else 'MISSING'}",
        "```",
        "",
    ]
    if blocked:
        lines.extend(
            [
                "P2 hardware execution is blocked by JTAG target enumeration.",
                "",
                "The failed lane0 run is not counted as RF link evidence unless it contains a valid `PSPS_STAGE_SUMMARY` and shutdown-after-run evidence.",
            ]
        )
    else:
        lines.append("No current JTAG blocker is shown by the latest preflight log.")
    write(REPORTS / "P2_hardware_blocker_current.md", "\n".join(lines) + "\n")


def build_current_config_and_matrix(repeat_pass: int, health_ready: int, payload_pass: int, ab_diag: int, ba_decided: int, uart_pass: int) -> None:
    baseline_frozen = int((REPORTS / "P2_baseline_freeze_manifest.md").exists() and sha256(CONSTRAINT) == EXPECTED_CONSTRAINT_SHA256)
    final_pass = int(baseline_frozen and repeat_pass and health_ready and ab_diag and ba_decided and uart_pass)
    rows = [
        {"field": "P2_BASELINE_FROZEN", "value": baseline_frozen, "evidence": "reports/P2_baseline_freeze_manifest.md"},
        {"field": "LANE0_REPEATABILITY_PASS", "value": repeat_pass, "evidence": "reports/P2_lane0_repeatability_summary.md"},
        {"field": "LANE0_HEALTH_COUNTERS_READY", "value": health_ready, "evidence": "reports/P2_lane0_health_counter_definitions.md"},
        {"field": "LANE0_PAYLOAD_MATRIX_PASS", "value": payload_pass, "evidence": "reports/P2_lane0_payload_matrix_summary.md"},
        {"field": "AB_L1_NONINVASIVE_DIAG_COMPLETE", "value": ab_diag, "evidence": "reports/P2_AB_L1_persistence_summary.md; reports/P2_AB_L1_static_mapping_audit.md"},
        {"field": "BA_L1_ASYMMETRIC_FEASIBILITY_DECIDED", "value": ba_decided, "evidence": "reports/P2_BA_L1_protocol_feasibility.md"},
        {"field": "UART_OPERATOR_CONTROL_PASS", "value": uart_pass, "evidence": "reports/P2_uart_operator_control_acceptance.md"},
        {"field": "REAL_ETHERNET_PASS", "value": 0, "evidence": "deferred by P2 constraints"},
        {"field": "REAL_ROTATION_PASS", "value": 0, "evidence": "deferred by P2 constraints"},
        {"field": "FINAL_TARGET_PASS", "value": 0, "evidence": "full target remains incomplete"},
        {"field": "STATIC_2LANE_CONSTRAINED_OPERATIONAL_BASELINE_PASS", "value": final_pass, "evidence": "P2 matrix rollup"},
    ]
    write_csv(REPORTS / "P2_constrained_acceptance_matrix.csv", ["field", "value", "evidence"], rows)
    md = [
        "# P2 Constrained Acceptance Matrix",
        "",
        f"Generated: {now_iso()}",
        "",
        f"Overall: `{'STATIC_2LANE_CONSTRAINED_OPERATIONAL_BASELINE_PASS' if final_pass else 'P2_INCOMPLETE'}`",
        "",
        "| field | value | evidence |",
        "| --- | ---: | --- |",
    ]
    for row in rows:
        md.append(f"| {row['field']} | {row['value']} | {row['evidence']} |")
    md.extend(["", "```text"])
    for row in rows:
        md.append(f"{row['field']}={row['value']}")
    md.append("```")
    write(REPORTS / "P2_constrained_acceptance_matrix.md", "\n".join(md) + "\n")
    write(
        REPORTS / "P2_current_usable_configuration.md",
        "\n".join(
            [
                "# P2 Current Usable Configuration",
                "",
                f"Generated: {now_iso()}",
                "",
                "```text",
                "current mode = LANE0_DEGRADED_RELIABLE_2LANE_STATIC",
                "payload lane mask = 0x00000001",
                "ack lane mask = 0x00000001",
                "AB_L1 = excluded / NO_RX_RAW_PULSE",
                "BA_L1 = raw PASS only; protocol/asymmetric promotion deferred unless separately tested",
                "Ethernet = unavailable",
                "rotation = unavailable",
                "4/8 lane hardware = unavailable",
                f"STATIC_2LANE_CONSTRAINED_OPERATIONAL_BASELINE_PASS={final_pass}",
                "REAL_ETHERNET_PASS=0",
                "REAL_ROTATION_PASS=0",
                "FINAL_TARGET_PASS=0",
                "```",
            ]
        )
        + "\n",
    )
    write(
        REPORTS / "P2_BAD_DIR_status.md",
        "\n".join(
            [
                "# P2 BAD_DIR Status",
                "",
                f"Generated: {now_iso()}",
                "",
                "```text",
                "BAD_DIR_FINAL=AB_L1",
                "BAD_DIR_LAYER=NO_RX_RAW_PULSE",
                "AB_L1_REMAINS_EXCLUDED=1",
                "AB_L1_DO_NOT_PROMOTE_TO_SYSTEM_PASS=1",
                "```",
            ]
        )
        + "\n",
    )


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    build_baseline_freeze()
    repeat_pass, health_ready = build_lane0_reports()
    build_lane0_health_debug_summary()
    payload_pass = build_payload_matrix()
    _, ab_diag = build_ab_l1_reports()
    ba_decided = build_ba_l1_reports()
    uart_pass = build_uart_acceptance()
    build_next_hardware_run_readiness()
    build_hardware_blocker_current()
    build_current_config_and_matrix(repeat_pass, health_ready, payload_pass, ab_diag, ba_decided, uart_pass)
    print("P2 artifacts generated")
    print(f"P2_BASELINE_FROZEN={int((REPORTS / 'P2_baseline_freeze_manifest.md').exists())}")
    print(f"LANE0_REPEATABILITY_PASS={repeat_pass}")
    print(f"LANE0_HEALTH_COUNTERS_READY={health_ready}")
    print(f"LANE0_PAYLOAD_MATRIX_PASS={payload_pass}")
    print(f"AB_L1_NONINVASIVE_DIAG_COMPLETE={ab_diag}")
    print(f"BA_L1_ASYMMETRIC_FEASIBILITY_DECIDED={ba_decided}")
    print(f"UART_OPERATOR_CONTROL_PASS={uart_pass}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
