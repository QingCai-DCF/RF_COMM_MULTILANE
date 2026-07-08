from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

REQUIRED_LINKS = [
    "A_TO_B_LANE0",
    "A_TO_B_LANE1",
    "B_TO_A_LANE0",
    "B_TO_A_LANE1",
]

ROW_SPECS = [
    ("A_TO_B_LANE0", "a_tx_lane0", "A", 0, "B", 0, True),
    ("A_TO_B_LANE1", "a_tx_lane1", "A", 1, "B", 1, True),
    ("B_TO_A_LANE0", "b_tx_lane0", "B", 0, "A", 0, True),
    ("B_TO_A_LANE1", "b_tx_lane1", "B", 1, "A", 1, True),
    ("A_TO_B_CROSS_0_TO_1", "a_tx_lane0", "A", 0, "B", 1, False),
    ("A_TO_B_CROSS_1_TO_0", "a_tx_lane1", "A", 1, "B", 0, False),
    ("B_TO_A_CROSS_0_TO_1", "b_tx_lane0", "B", 0, "A", 1, False),
    ("B_TO_A_CROSS_1_TO_0", "b_tx_lane1", "B", 1, "A", 0, False),
]


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def is_transient_file_lock(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (32, 33)


def write_text_with_retry(path: Path, text: str, encoding: str = "utf-8", max_wait_seconds: int = 120) -> None:
    start = time.monotonic()
    announced = False
    while True:
        try:
            path.write_text(text, encoding=encoding)
            if announced:
                elapsed = int(time.monotonic() - start)
                print(f"WAIT_FILE_CLEAR path={path} elapsed_s={elapsed}")
            return
        except OSError as exc:
            if not is_transient_file_lock(exc):
                raise
            elapsed = time.monotonic() - start
            if elapsed >= max_wait_seconds:
                print(f"WAIT_FILE_TIMEOUT path={path} elapsed_s={int(elapsed)} error={exc}")
                raise
            if not announced:
                print(f"WAIT_FILE_LOCK path={path} error={exc}")
                announced = True
            time.sleep(1)


def rel(path: str | Path | None) -> str:
    if path is None or str(path) == "":
        return ""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def blank_if_none(value: Any) -> Any:
    return "" if value is None else value


def signal_key(signal: str, lane: int) -> str:
    return f"{signal}{lane}"


def signal_state(signals: dict[str, Any], side: str, kind: str, lane: int) -> str:
    key = signal_key(f"{side.lower()}_{kind}", lane)
    metric = signals.get(key, {})
    if not metric:
        return ""
    return "init={initial};final={final};stuck={stuck};active={active}".format(
        initial=blank_if_none(metric.get("initial_value")),
        final=blank_if_none(metric.get("final_value")),
        stuck=blank_if_none(metric.get("stuck_active")),
        active=blank_if_none(metric.get("active_samples")),
    )


def rx_width(signals: dict[str, Any], link: dict[str, Any]) -> Any:
    key = signal_key(str(link.get("rx_signal", "")), int(link.get("rx_lane", 0)))
    metric = signals.get(key, {})
    return blank_if_none(metric.get("median_width"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def snapshot_rows_by_link(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("link")): row for row in snapshot.get("rows", [])}


def analyzer_by_trigger(paths: Iterable[Path]) -> dict[str, dict[str, Any]]:
    by_trigger: dict[str, dict[str, Any]] = {}
    for path in paths:
        if not path.exists():
            continue
        payload = load_json(path)
        if not isinstance(payload, list):
            continue
        for item in payload:
            trigger = str(item.get("trigger_mode", ""))
            if trigger:
                copied = dict(item)
                copied["_source_json"] = str(path)
                by_trigger[trigger] = copied
    return by_trigger


def latest_matrix_analyzer_paths() -> list[Path]:
    for path in sorted(REPORTS.glob("2lane_matrix_safe_*.summary.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if "MATRIX_ANALYSIS_JSON_EXIT=0" not in text:
            continue
        match = re.search(r"(?m)^MATRIX_ANALYSIS_JSON=(.+)$", text)
        if not match:
            continue
        analyzer_path = Path(match.group(1).strip())
        if analyzer_path.exists():
            return [analyzer_path]
    return []


def classify_link(link: dict[str, Any], required: bool, snapshot_row: dict[str, Any]) -> str:
    if not required:
        return snapshot_row.get("classification", "")
    verdict = str(link.get("verdict", ""))
    if verdict == "PASS_RAW_PULSE":
        return "PASS_PHYSICAL_RAW_PULSE"
    if verdict == "FAIL_NO_RX_ACTIVITY":
        return "FAIL_PHYSICAL_RX_MISSING"
    if verdict in ("NO_TX_ACTIVITY", ""):
        return "EVIDENCE_MISSING_REQUIRED_LINK"
    return snapshot_row.get("classification", "")


def parse_kv_line(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for match in re.finditer(r"([A-Za-z0-9_]+)=([^\s]+)", line):
        result[match.group(1)] = match.group(2)
    return result


def latest_attempts_by_trigger() -> dict[str, dict[str, Any]]:
    attempts: dict[str, dict[str, Any]] = {}
    for path in sorted(REPORTS.glob("2lane_matrix_safe_*.summary.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if not text:
            continue
        for match in re.finditer(
            r"(?m)^RUN_DIAGNOSTIC trigger=(\S+) effective_exit=(\S+) run_status=(\S+) run_exit_reported=(\S+) ila_timeout=(\S+) ila_csv_missing=(\S+)",
            text,
        ):
            trigger = match.group(1)
            if trigger in attempts:
                continue
            run_result = re.search(
                rf"(?m)^RUN_RESULT trigger={re.escape(trigger)} .*?shutdown_exit=(\S*) shutdown_inferred=(\S*) tfdu_window_s=(\S*) ila_csv=(\S*)",
                text,
            )
            restore = re.search(r"(?m)^AUTOBUILD_ELF_RESTORE_OK=(\S+)", text)
            final_uart_line = ""
            for uart_match in re.finditer(r"(?m)^UART_MATCH=(PSPS_(?:TDM_)?STAGE_SUMMARY .*)$", text):
                final_uart_line = uart_match.group(1)
            final_uart = parse_kv_line(final_uart_line)
            attempts[trigger] = {
                "summary": rel(path),
                "effective_exit": match.group(2),
                "run_status": match.group(3),
                "run_exit_reported": match.group(4),
                "ila_timeout": match.group(5),
                "ila_csv_missing": match.group(6),
                "shutdown_exit": run_result.group(1) if run_result else "",
                "shutdown_inferred": run_result.group(2) if run_result else "",
                "tfdu_window_s": run_result.group(3) if run_result else "",
                "ila_csv": rel(run_result.group(4)) if run_result else "",
                "autobuild_elf_restore_ok": restore.group(1) if restore else "",
                "uart_last_error": final_uart.get("last_error", ""),
                "uart_tx_lane": final_uart.get("tx_lane", ""),
                "uart_rx_good": final_uart.get("rx_good", ""),
                "uart_rx_err": final_uart.get("rx_err", ""),
                "uart_txp": final_uart.get("txp", ""),
                "uart_txi": final_uart.get("txi", ""),
                "uart_txa": final_uart.get("txa", ""),
                "uart_rxb": final_uart.get("rxb", ""),
            }
    return attempts


def build_row(
    row_name: str,
    trigger: str,
    tx_side: str,
    tx_lane: int,
    rx_side: str,
    rx_lane: int,
    required: bool,
    entry: dict[str, Any] | None,
    snapshot_by_link: dict[str, dict[str, Any]],
    latest_attempts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    snapshot_row = snapshot_by_link.get(row_name, {})
    latest_attempt = latest_attempts.get(trigger, {})
    latest_attempt_fields = {
        "latest_attempt_summary": latest_attempt.get("summary", ""),
        "latest_attempt_status": latest_attempt.get("run_status", ""),
        "latest_attempt_exit": latest_attempt.get("effective_exit", ""),
        "latest_attempt_shutdown": latest_attempt.get("shutdown_exit", "") or latest_attempt.get("shutdown_inferred", ""),
        "latest_attempt_tfdu_window_s": latest_attempt.get("tfdu_window_s", ""),
        "latest_attempt_ila_timeout": latest_attempt.get("ila_timeout", ""),
        "latest_attempt_ila_csv_missing": latest_attempt.get("ila_csv_missing", ""),
        "latest_attempt_elf_restore_ok": latest_attempt.get("autobuild_elf_restore_ok", ""),
        "latest_attempt_last_error": latest_attempt.get("uart_last_error", ""),
        "latest_attempt_tx_lane": latest_attempt.get("uart_tx_lane", ""),
        "latest_attempt_rx_good": latest_attempt.get("uart_rx_good", ""),
        "latest_attempt_rx_err": latest_attempt.get("uart_rx_err", ""),
        "latest_attempt_txp": latest_attempt.get("uart_txp", ""),
        "latest_attempt_txi": latest_attempt.get("uart_txi", ""),
        "latest_attempt_txa": latest_attempt.get("uart_txa", ""),
        "latest_attempt_rxb": latest_attempt.get("uart_rxb", ""),
    }
    if entry and row_name in entry.get("links", {}):
        link = entry["links"][row_name]
        signals = entry.get("signals", {})
        row = {
            "tx_side": tx_side,
            "tx_lane": tx_lane,
            "rx_side": rx_side,
            "rx_lane": rx_lane,
            "row_name": row_name,
            "trigger_mode": trigger,
            "expected_main": entry.get("expected", ""),
            "required_main_link": int(required),
            "tx_pulse_count": blank_if_none(link.get("tx_pulses")),
            "local_self_echo_count": blank_if_none(link.get("near_rx_pulses")),
            "remote_rx_pulse_count": blank_if_none(link.get("rx_pulses")),
            "remote_rx_delay_cycles": blank_if_none(link.get("first_delay_samples")),
            "remote_rx_width_cycles": rx_width(signals, link),
            "sd_state": signal_state(signals, tx_side, "sd", tx_lane),
            "mode_state": signal_state(signals, tx_side, "mode", tx_lane),
            "verdict": link.get("verdict", ""),
            "wrapper_verdict": entry.get("verdict", ""),
            "classification": classify_link(link, required, snapshot_row),
            "evidence_csv": rel(entry.get("csv_path")),
            "evidence_json": rel(entry.get("_source_json", snapshot_row.get("evidence_json", ""))),
            "reason": entry.get("verdict_reason", snapshot_row.get("reason", "")),
        }
        row.update(latest_attempt_fields)
        return row

    missing_verdict = "MISSING_EVIDENCE_REQUIRED_LINK" if required else "MISSING_EVIDENCE_NO_TRIGGER"
    row = {
        "tx_side": tx_side,
        "tx_lane": tx_lane,
        "rx_side": rx_side,
        "rx_lane": rx_lane,
        "row_name": row_name,
        "trigger_mode": trigger,
        "expected_main": row_name if required else "",
        "required_main_link": int(required),
        "tx_pulse_count": blank_if_none(snapshot_row.get("tx_pulses")),
        "local_self_echo_count": blank_if_none(snapshot_row.get("near_rx_pulses")),
        "remote_rx_pulse_count": blank_if_none(snapshot_row.get("far_rx_pulses")),
        "remote_rx_delay_cycles": blank_if_none(snapshot_row.get("first_delay_samples")),
        "remote_rx_width_cycles": "",
        "sd_state": "",
        "mode_state": "",
        "verdict": missing_verdict,
        "wrapper_verdict": "MISSING_TRIGGER_OR_CSV",
        "classification": snapshot_row.get("classification", "EVIDENCE_MISSING_REQUIRED_LINK" if required else ""),
        "evidence_csv": rel(snapshot_row.get("evidence_csv", "")),
        "evidence_json": rel(snapshot_row.get("evidence_json", "")),
        "reason": snapshot_row.get("reason", "trigger evidence is absent from the latest analyzer JSON"),
    }
    row.update(latest_attempt_fields)
    return row


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        cleaned = [str(blank_if_none(v)).replace("|", "/").replace("\n", " ") for v in row]
        lines.append("| " + " | ".join(cleaned) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build MD P7.2 raw-matrix deliverables from the current snapshot/analyzer evidence.")
    parser.add_argument("--snapshot", type=Path, default=REPORTS / "2lane_physical_failure_snapshot_current.json")
    parser.add_argument("--csv-out", type=Path, default=REPORTS / "P7_01_2lane_raw_matrix.csv")
    parser.add_argument("--md-out", type=Path, default=REPORTS / "P7_01_2lane_raw_matrix_report.md")
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    snapshot = load_json(args.snapshot)
    snapshot_by_link = snapshot_rows_by_link(snapshot)
    snapshot_analyzer_paths = [ROOT / src for src in snapshot.get("sources", [])]
    analyzer_paths = latest_matrix_analyzer_paths() or snapshot_analyzer_paths
    analyzer = analyzer_by_trigger(analyzer_paths)
    latest_attempts = latest_attempts_by_trigger()

    rows = [
        build_row(row_name, trigger, tx_side, tx_lane, rx_side, rx_lane, required, analyzer.get(trigger), snapshot_by_link, latest_attempts)
        for row_name, trigger, tx_side, tx_lane, rx_side, rx_lane, required in ROW_SPECS
    ]

    fieldnames = [
        "tx_side",
        "tx_lane",
        "rx_side",
        "rx_lane",
        "row_name",
        "trigger_mode",
        "expected_main",
        "required_main_link",
        "tx_pulse_count",
        "local_self_echo_count",
        "remote_rx_pulse_count",
        "remote_rx_delay_cycles",
        "remote_rx_width_cycles",
        "sd_state",
        "mode_state",
        "verdict",
        "wrapper_verdict",
        "classification",
        "evidence_csv",
        "evidence_json",
        "reason",
        "latest_attempt_summary",
        "latest_attempt_status",
        "latest_attempt_exit",
        "latest_attempt_shutdown",
        "latest_attempt_tfdu_window_s",
        "latest_attempt_ila_timeout",
        "latest_attempt_ila_csv_missing",
        "latest_attempt_elf_restore_ok",
        "latest_attempt_last_error",
        "latest_attempt_tx_lane",
        "latest_attempt_rx_good",
        "latest_attempt_rx_err",
        "latest_attempt_txp",
        "latest_attempt_txi",
        "latest_attempt_txa",
        "latest_attempt_rxb",
    ]
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    write_text_with_retry(args.csv_out, csv_buffer.getvalue(), encoding="utf-8-sig")

    required_rows = [row for row in rows if row["required_main_link"]]
    required_status = []
    for row in required_rows:
        remote_rx = row["remote_rx_pulse_count"]
        remote_ok = isinstance(remote_rx, int) and remote_rx > 0
        required_status.append(remote_ok and row["verdict"] == "PASS_RAW_PULSE")
    p7_pass = all(required_status)
    result = "PASS_ALL_REQUIRED_LINKS" if p7_pass else "BLOCK_REQUIRED_LINK_EVIDENCE_MISSING"
    generated = datetime.now().isoformat(timespec="seconds")

    main_table = md_table(
        ["Direction", "TX", "Remote RX", "Near echo", "Verdict", "Classification", "Evidence"],
        [
            [
                row["row_name"],
                row["tx_pulse_count"],
                row["remote_rx_pulse_count"],
                row["local_self_echo_count"],
                row["verdict"],
                row["classification"],
                row["evidence_csv"],
            ]
            for row in required_rows
        ],
    )
    cross_table = md_table(
        ["Cross row", "TX", "Remote RX", "Near echo", "Verdict", "Trigger"],
        [
            [row["row_name"], row["tx_pulse_count"], row["remote_rx_pulse_count"], row["local_self_echo_count"], row["verdict"], row["trigger_mode"]]
            for row in rows
            if not row["required_main_link"]
        ],
    )
    def next_check_text(row: dict[str, Any]) -> str:
        base = snapshot_by_link.get(str(row["row_name"]), {}).get("next_check", "")
        if row.get("latest_attempt_status") == "FAIL_ILA_TIMEOUT":
            return (
                f"Latest `{row['trigger_mode']}` attempt armed ILA but produced no CSV. "
                f"UART ended with last_error={row.get('latest_attempt_last_error', '')}, "
                f"tx_lane={row.get('latest_attempt_tx_lane', '')}, txp={row.get('latest_attempt_txp', '')}, "
                f"txi={row.get('latest_attempt_txi', '')}, txa={row.get('latest_attempt_txa', '')}, "
                f"rxb={row.get('latest_attempt_rxb', '')}, rx_good={row.get('latest_attempt_rx_good', '')}, "
                f"rx_err={row.get('latest_attempt_rx_err', '')}. "
                "Before changing far-end RX wiring, inspect B-side lane1 TX generation/profile, trigger selection, SD/MODE levels, and whether the rebuilt PS profile actually drives B lane1."
            )
        return base

    next_checks = md_table(
        ["Link", "Next check"],
        [[row["row_name"], next_check_text(row)] for row in required_rows if snapshot_by_link.get(row["row_name"], {}).get("status") != "PASS"],
    )
    latest_attempt_table = md_table(
        [
            "Direction",
            "Trigger",
            "Latest status",
            "Exit",
            "Shutdown",
            "TFDU window s",
            "ILA timeout",
            "CSV missing",
            "ELF restore",
            "last_error",
            "tx_lane",
            "txp",
            "txi",
            "txa",
            "rxb",
            "rx_good",
            "rx_err",
            "Summary",
        ],
        [
            [
                row["row_name"],
                row["trigger_mode"],
                row["latest_attempt_status"],
                row["latest_attempt_exit"],
                row["latest_attempt_shutdown"],
                row["latest_attempt_tfdu_window_s"],
                row["latest_attempt_ila_timeout"],
                row["latest_attempt_ila_csv_missing"],
                row["latest_attempt_elf_restore_ok"],
                row["latest_attempt_last_error"],
                row["latest_attempt_tx_lane"],
                row["latest_attempt_txp"],
                row["latest_attempt_txi"],
                row["latest_attempt_txa"],
                row["latest_attempt_rxb"],
                row["latest_attempt_rx_good"],
                row["latest_attempt_rx_err"],
                row["latest_attempt_summary"],
            ]
            for row in required_rows
        ],
    )
    b_tx_lane1_attempt = next((row for row in required_rows if row["row_name"] == "B_TO_A_LANE1"), {})
    b_tx_lane1_status = b_tx_lane1_attempt.get("latest_attempt_status", "")
    b_tx_lane1_summary = b_tx_lane1_attempt.get("latest_attempt_summary", "")
    if b_tx_lane1_status:
        b_tx_lane1_interpretation = (
            f"- `B_TO_A_LANE1`: latest wrapper attempt returned `{b_tx_lane1_status}` "
            f"with summary `{b_tx_lane1_summary}`; no usable ILA CSV was produced, so this is not remote raw-pulse PASS evidence. "
            f"UART ended with last_error=`{b_tx_lane1_attempt.get('latest_attempt_last_error', '')}`, "
            f"tx_lane=`{b_tx_lane1_attempt.get('latest_attempt_tx_lane', '')}`, "
            f"txp/txi/txa=`{b_tx_lane1_attempt.get('latest_attempt_txp', '')}`/`{b_tx_lane1_attempt.get('latest_attempt_txi', '')}`/`{b_tx_lane1_attempt.get('latest_attempt_txa', '')}`, "
            f"rxb=`{b_tx_lane1_attempt.get('latest_attempt_rxb', '')}`."
        )
    else:
        b_tx_lane1_interpretation = "- `B_TO_A_LANE1`: required evidence is missing from the latest analyzer JSON because the `b_tx_lane1` run timed out or did not produce a usable CSV."

    md = [
        "# P7.2 2-lane raw matrix report",
        "",
        f"Generated: {generated} +08:00",
        "",
        "## Verdict",
        "",
        f"`P7_2LANE_REMOTE_RAW_MATRIX_PASS = {int(p7_pass)}`",
        "",
        f"`P7_01_2LANE_RAW_MATRIX_RESULT = {result}`",
        "",
        "This is raw physical evidence only. It does not prove protocol DATA roundtrip, Ethernet, rotation, full 2-lane protocol baseline, 4/8-lane scaling, or long-duration stability.",
        "",
        "## Current Evidence",
        "",
        f"- Snapshot: `{rel(args.snapshot)}`",
        f"- Snapshot generated: `{snapshot.get('generated', '')}`",
        f"- Snapshot overall: `{snapshot.get('overall', '')}`",
        f"- Snapshot failures: `{snapshot.get('failures', '')}`",
        f"- Far-end RX missing with near echo: `{snapshot.get('far_rx_missing_with_near_echo', '')}`",
        "- No hardware programming by this builder: `1`",
        "- No UART write by this builder: `1`",
        "- No TFDU drive by this builder: `1`",
        "",
        "Analyzer sources:",
        "",
        *[f"- `{rel(path)}`" for path in analyzer_paths],
        "",
        "## Main Direction Results",
        "",
        main_table,
        "",
        "## Latest Wrapper Attempts",
        "",
        "These rows show the latest safe wrapper attempt per required trigger, including attempts that did not produce an analyzer CSV.",
        "",
        latest_attempt_table,
        "",
        "## Cross-Row Boundary",
        "",
        "Cross rows are recorded for diagnostic context only. They must not be promoted as main-link PASS evidence.",
        "",
        cross_table,
        "",
        "## Interpretation",
        "",
        "- `A_TO_B_LANE0`: raw TX and expected remote RX pulse activity are present.",
        "- `A_TO_B_LANE1`: A-side TX and near self echo are present, but expected B-side lane1 RX has zero raw pulses.",
        "- `B_TO_A_LANE0`: B-side TX and near self echo are present, but expected A-side lane0 RX has zero raw pulses.",
        b_tx_lane1_interpretation,
        "",
        "Because P7.2 requires all four main directions to have remote raw pulses, this evidence does not satisfy P7.2. Do not advance this evidence to `P7_2LANE_REMOTE_RAW_MATRIX_PASS=1`.",
        "",
        "## Next Checks",
        "",
        next_checks,
        "",
        "## Artifact Traceability",
        "",
        "- P7.1 freeze: `reports/P7_00_2lane_physical_freeze.md`",
        "- P7.1 artifact hashes: `reports/P7_00_artifact_hashes.txt`",
        "- P7.1 pin map: `reports/P7_00_lane_pin_map.md`",
        "- Current raw matrix CSV: `reports/P7_01_2lane_raw_matrix.csv`",
        "- Current failure snapshot: `reports/2lane_physical_failure_snapshot_current.md`",
        "",
        "```text",
        f"RF_COMM_P7_2_RAW_MATRIX_DELIVERABLE overall={result} p7_pass={int(p7_pass)} rows={len(rows)} required={len(required_rows)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "P7_3_AUTO_RUN_BY_THIS_SCRIPT=0",
        "```",
    ]
    write_text_with_retry(args.md_out, "\n".join(md) + "\n", encoding="utf-8")

    print(f"WROTE_CSV={args.csv_out}")
    print(f"WROTE_MARKDOWN={args.md_out}")
    print(f"RF_COMM_P7_2_RAW_MATRIX_DELIVERABLE overall={result} p7_pass={int(p7_pass)} rows={len(rows)} required={len(required_rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("P7_3_AUTO_RUN_BY_THIS_SCRIPT=0")
    return 0 if not p7_pass else 0


if __name__ == "__main__":
    raise SystemExit(main())
