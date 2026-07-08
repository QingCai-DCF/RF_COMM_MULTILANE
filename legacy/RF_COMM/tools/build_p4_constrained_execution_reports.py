#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def file_sha(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def latest(pattern: str) -> Path | None:
    matches = sorted(REPORTS.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def kv_pairs(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def has_measured_rows(path: Path) -> bool:
    rows = read_csv_rows(path)
    for row in rows:
        status = row.get("status", "")
        if status and not status.startswith("NOT_EXECUTED"):
            return True
    return False


def int_field(row: dict[str, str], key: str, default: int = 0) -> int:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def float_field(row: dict[str, str], key: str, default: float = 0.0) -> float:
    value = row.get(key, "")
    if value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default


def txack_row_clean(row: dict[str, str], require_failure_counters: bool = False) -> bool:
    sent = int_field(row, "sent")
    rx_ok = int_field(row, "rx_ok")
    checks = [
        sent > 0,
        rx_ok == sent,
        int_field(row, "tx_fail") == 0,
        float_field(row, "loss_ppm") == 0.0,
        int_field(row, "rx_timeout") == 0,
        int_field(row, "rx_bad") == 0,
        int_field(row, "rx_mismatch") == 0,
        row.get("last_error", "") == "none",
        int_field(row, "shutdown_exit") == 0,
    ]
    if require_failure_counters:
        checks.extend(
            [
                int_field(row, "tx_start_count") > 0,
                int_field(row, "tx_done_count") > 0,
                int_field(row, "tx_retry_exhausted_count") == 0,
            ]
        )
    return all(checks)


def p4a02_state() -> dict[str, object]:
    path = REPORTS / "P4A_02_rx_tuning_ab_results.csv"
    rows = read_csv_rows(path)
    measured = [row for row in rows if row.get("status", "") and not row.get("status", "").startswith("NOT_EXECUTED")]
    builds = {"BuildA": [], "BuildB": []}
    for row in measured:
        if row.get("build") in builds:
            builds[row["build"]].append(row)
    completed = len(builds["BuildA"]) >= 5 and len(builds["BuildB"]) >= 5
    clean = {
        build: len(rows_for_build) >= 5 and all(txack_row_clean(row, require_failure_counters=True) for row in rows_for_build[:5])
        for build, rows_for_build in builds.items()
    }

    selected = ""
    verdict = "NOT_EXECUTED"
    reason = "5x300s A/B not executed"
    if completed:
        if clean["BuildB"] and not clean["BuildA"]:
            selected = "BuildB"
            verdict = "PASS"
            reason = "BuildB 5/5 clean; BuildA not clean"
        elif clean["BuildA"] and not clean["BuildB"]:
            selected = "BuildA"
            verdict = "PASS"
            reason = "BuildA 5/5 clean; BuildB not clean"
        elif clean["BuildA"] and clean["BuildB"]:
            totals = {}
            for build, rows_for_build in builds.items():
                totals[build] = (
                    sum(int_field(row, "tx_retry_count_total") for row in rows_for_build[:5]),
                    max(int_field(row, "max_retry_seen") for row in rows_for_build[:5]),
                    sum(int_field(row, "ack_timeout_count") for row in rows_for_build[:5]),
                )
            selected = "BuildA" if totals["BuildA"] < totals["BuildB"] else "BuildB"
            verdict = "PASS"
            reason = f"Both builds 5/5 clean; selected {selected} by retry/timeout tuple {totals[selected]}"
        else:
            verdict = "FAIL"
            reason = "Both builds had at least one non-clean run; do not promote"

    return {
        "completed": completed,
        "verdict": verdict,
        "selected": selected,
        "reason": reason,
        "build_a_measured": len(builds["BuildA"]),
        "build_b_measured": len(builds["BuildB"]),
        "build_a_clean": clean["BuildA"],
        "build_b_clean": clean["BuildB"],
    }


def p4a03_state() -> dict[str, object]:
    path = REPORTS / "P4A_03_lane0_10x300_requal.csv"
    rows = read_csv_rows(path)
    measured = [row for row in rows if row.get("status", "") and not row.get("status", "").startswith("NOT_EXECUTED")]
    completed = len(measured) >= 10
    passed = completed and all(txack_row_clean(row, require_failure_counters=False) for row in measured[:10])
    if passed:
        reason = "10/10 300s lane0 runs clean"
        verdict = "PASS"
    elif completed:
        reason = "At least one 300s lane0 run failed hard criteria"
        verdict = "FAIL"
    else:
        reason = "10x300s not executed"
        verdict = "NOT_EXECUTED"
    selected = measured[0].get("selected_tuning", "") if measured else ""
    return {
        "completed": completed,
        "passed": passed,
        "verdict": verdict,
        "reason": reason,
        "measured": len(measured),
        "selected": selected,
    }


def aggregate_source_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    found = 0
    for path in sorted(paths):
        if not path.exists() or not path.is_file():
            continue
        found += 1
        rel_name = rel(path).replace("\\", "/")
        h.update(rel_name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    if found == 0:
        return "MISSING"
    return h.hexdigest().upper()


def p3_lane0_rows() -> list[dict[str, str]]:
    path = REPORTS / "P3_01_lane0_requal_on_P2PSPL_bit.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        sent = int(row.get("sent") or "0")
        tx_fail = int(row.get("tx_fail") or "0")
        exact_loss = tx_fail / sent if sent else 0.0
        row["exact_loss"] = f"{exact_loss:.12f}"
        row["loss_ppm"] = f"{exact_loss * 1_000_000:.6f}"
    return rows


def build_summary(profile: str) -> Path | None:
    return latest(f"build_{profile}_*.summary.txt")


def artifact_from_summary(summary: Path | None, name: str) -> tuple[str, str, str]:
    if summary is None or not summary.exists():
        return ("", "NOT_BUILT_FOR_P4", "MISSING")
    text = read(summary)
    preserved_pattern = re.compile(rf"P4_PROFILE_ARTIFACT name={re.escape(name)} path=(?P<path>.*?) size=(?P<size>\d+) sha256=(?P<sha>[A-Fa-f0-9]+)")
    match = preserved_pattern.search(text)
    if match:
        return (match.group("path"), f"PRESERVED_FROM_{summary.name}", match.group("sha").upper())
    pattern = re.compile(rf"ARTIFACT name={re.escape(name)} path=(?P<path>.*?) size=(?P<size>\d+) sha256=(?P<sha>[A-Fa-f0-9]+)")
    match = pattern.search(text)
    if not match:
        return ("", f"NOT_FOUND_IN_{summary.name}", "MISSING")
    return (match.group("path"), f"FROM_{summary.name}", match.group("sha").upper())


def known_artifacts() -> dict[str, Path]:
    return {
        "bit": ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1" / "design_shiboqi_wrapper.bit",
        "ltx": ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1" / "design_shiboqi_wrapper.ltx",
        "xsa": ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.xsa",
        "current_elf": ROOT / "software" / "_vitis_ws_ps_ps_loopback" / "rf_comm_ps_ps_loopback" / "Debug" / "rf_comm_ps_ps_loopback.elf",
        "p3_txonly_elf": REPORTS / "P3_07_txonly_observability_20260628_192113.elf",
        "p3_roundtrip_elf": REPORTS / "P3_07_roundtrip_observability_20260628_192113.elf",
    }


def manifest_rows(profile: str, psps_tx_only: str, rx_tuning: str) -> list[dict[str, str]]:
    summary = build_summary(profile)
    artifacts = known_artifacts()
    rows: list[dict[str, str]] = []
    for name in ("bit", "ltx", "xsa", "elf"):
        path_text, status, sha = artifact_from_summary(summary, name)
        if path_text:
            path = Path(path_text)
        elif name == "elf":
            if psps_tx_only == "1":
                path = artifacts["current_elf"]
                status = "CURRENT_WORKSPACE_ELF_USED_BY_P4A_SMOKE"
            else:
                path = artifacts["p3_roundtrip_elf"]
                status = "P3_ROUNDTRIP_CANDIDATE_NOT_P4_BUILD"
            sha = file_sha(path)
        else:
            path = artifacts[name]
            status = "CURRENT_WORKSPACE_ARTIFACT_NOT_P4_BUILD"
            sha = file_sha(path)
        rows.append(
            {
                "object": name,
                "path": rel(path),
                "sha256": sha,
                "status": status,
            }
        )
    source_hash = aggregate_source_hash(
        [
            ROOT / "software" / "host_uart_operator" / "rf_comm_uart_operator.py",
            ROOT / "software" / "ps_ps_loopback" / "src" / "main.c",
            ROOT / "IPs" / "ip_ir_array" / "src" / "ir_stream_array_top_axi.sv",
            ROOT / "IPs" / "ip_ir_array" / "src" / "ir_stream_bidir_b0_bd.v",
            ROOT / "tools" / "build_p4_profile.ps1",
            ROOT / "tools" / "run_p4a_failure_counter_smoke_safe.ps1",
        ]
    )
    rows.append(
        {
            "object": "source_hash",
            "path": "selected P4-relevant source files",
            "sha256": source_hash,
            "status": "AGGREGATED_SELECTED_SOURCE_HASH",
        }
    )
    rows.append(
        {
            "object": "build_command",
            "path": (
                f"powershell -NoProfile -ExecutionPolicy Bypass -File tools\\build_p4_profile.ps1 "
                f"-Profile {profile} -RxTuning {rx_tuning} -StageSeconds 60 -PayloadBytes 256"
            ),
            "sha256": "",
            "status": "COMMAND_RECORDED_NOT_RUN_BY_REPORT_GENERATOR",
        }
    )
    rows.append(
        {
            "object": "profile_parameters",
            "path": f"PSPS_TX_ONLY={psps_tx_only}; lane_mask=0x1; ack_mask=0x1; payload=256; rx_tuning={rx_tuning}",
            "sha256": "",
            "status": "EXPLICIT_PROFILE",
        }
    )
    return rows


def build_manifest(profile: str, psps_tx_only: str, rx_tuning: str, purpose: str) -> None:
    rows = manifest_rows(profile, psps_tx_only, rx_tuning)
    write(
        REPORTS / f"{profile}_build_manifest.md",
        "\n".join(
            [
                f"# {profile} Build Manifest",
                "",
                f"- Status: {'P4_BUILD_SUMMARY_FOUND' if build_summary(profile) else 'NOT_BUILT_FOR_P4'}",
                f"- Purpose: {purpose}",
                f"- `PSPS_TX_ONLY = {psps_tx_only}`",
                "- Lane mask: `0x1`",
                "- ACK mask: `0x1`",
                f"- RX tuning: `{rx_tuning}`",
                "",
                md_table(["object", "path / value", "sha256", "status"], [[r["object"], r["path"], r["sha256"], r["status"]] for r in rows]),
                "",
                "This manifest is a candidate manifest. It does not promote P4 unless the matching hardware gates pass.",
                "",
            ]
        ),
    )


def build_baseline_policy() -> None:
    write(
        REPORTS / "P4_00_baseline_policy.md",
        "\n".join(
            [
                "# P4-00 Baseline Policy",
                "",
                "P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED_PASS remains last accepted baseline.",
                "P3A/P3B package is instrumentation/documentation only.",
                "P4 artifacts are candidate artifacts until gates pass.",
                "",
                "```text",
                "LAST_ACCEPTED_BASELINE = P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED_PASS",
                "P3A_P3B_DESKTOP_REVIEW_COMPLETE = 1",
                "P3A_P3B_HARDWARE_BASELINE_PASS = 0",
                "P4_CONSTRAINED_TXACK_OPERATIONAL_BASELINE_PASS is resolved in P4_promotion_gate.md",
                "P4_CONSTRAINED_IR_DATA_ECHO_BASELINE_PASS is resolved in P4_promotion_gate.md",
                "FINAL_TARGET_PASS = 0",
                "REAL_ETHERNET_PASS = 0",
                "REAL_ROTATION_PASS = 0",
                "REAL_2LANE_FULL_PASS = 0",
                "```",
                "",
            ]
        ),
    )


def build_profiles() -> None:
    rows = [
        ["P4A_TXACK_DIAG", "1", "0x1", "0x1", "256", "lane0 TX/ACK stability and failure counter capture", "Allowed before B0 echo"],
        ["P4B_DATA_ROUNDTRIP_DIAG", "0", "0x1", "0x1", "<=256", "real IR DATA echo roundtrip attempt", "Use only after B0 DATA echo responder is implemented/enabled"],
    ]
    write(
        REPORTS / "P4_01_build_profiles.md",
        "\n".join(
            [
                "# P4-01 Build Profiles",
                "",
                "The P4 profiles are explicit; no operator build should rely on the default `PSPS_TX_ONLY` macro.",
                "",
                md_table(["profile", "PSPS_TX_ONLY", "lane_mask", "ack_mask", "payload", "purpose", "gate"], rows),
                "",
                "RX tuning candidates:",
                "",
                "```text",
                "BuildA: detect_start=3, detect_end=7, realign=1",
                "BuildB: detect_start=0, detect_end=5, realign=0",
                "```",
                "",
                "Build entry:",
                "",
                "```powershell",
                "powershell -NoProfile -ExecutionPolicy Bypass -File tools\\build_p4_profile.ps1 -Profile P4A_TXACK_DIAG -RxTuning BuildB -StageSeconds 60 -PayloadBytes 256",
                "powershell -NoProfile -ExecutionPolicy Bypass -File tools\\build_p4_profile.ps1 -Profile P4B_DATA_ROUNDTRIP_DIAG -RxTuning BuildB -StageSeconds 60 -PayloadBytes 256",
                "```",
                "",
            ]
        ),
    )


def build_failure_smoke() -> bool:
    log_path = REPORTS / "P4A_01_failure_counter_smoke.log"
    if not log_path.exists():
        write(
            log_path,
            "\n".join(
                [
                    "P4A_01_FAILURE_COUNTER_SMOKE_NOT_EXECUTED=1",
                    "REASON=requires P4A_TXACK_DIAG hardware run",
                    "RUN_COMMAND=powershell -NoProfile -ExecutionPolicy Bypass -File tools\\run_p4a_failure_counter_smoke_safe.ps1",
                    "",
                ]
            ),
        )
    text = read(log_path)
    passed = "UART_OPERATOR_P4_FAILURE_SMOKE_PASS=1" in text or "P4A_FAILURE_COUNTER_SMOKE_PASS=1" in text
    status = "PASS" if passed else "NOT_EXECUTED_OR_FAIL"
    start_lines = [line for line in text.splitlines() if "UARTOP_RESULT command=START" in line]
    failure_lines = [line for line in text.splitlines() if "item=failure_counters" in line]
    dma_lines = [line for line in text.splitlines() if "item=dma_obs" in line]
    start = kv_pairs(start_lines[-1]) if start_lines else {}
    failure = kv_pairs(failure_lines[-1]) if failure_lines else {}
    dma = kv_pairs(dma_lines[-1]) if dma_lines else {}
    summary_rows = [
        ["sent", start.get("sent", "")],
        ["rx_ok", start.get("rx_ok", "")],
        ["tx_fail", start.get("tx_fail", "")],
        ["loss", start.get("loss", "")],
        ["last_error", start.get("last_error", failure.get("last_error", ""))],
        ["tx_start_count", failure.get("tx_start_count", "")],
        ["tx_done_count", failure.get("tx_done_count", "")],
        ["tx_retry_count_total", failure.get("tx_retry_count_total", "")],
        ["ack_timeout_count", failure.get("ack_timeout_count", "")],
        ["max_retry_seen", failure.get("max_retry_seen", "")],
        ["s2mm_timeout_count", dma.get("s2mm_timeout_count", "")],
    ]
    write(
        REPORTS / "P4A_01_failure_counter_smoke.md",
        "\n".join(
            [
                "# P4A-01 Failure Counter Smoke",
                "",
                f"- Status: {status}",
                f"- Log: `{rel(log_path)}`",
                "- Required command sequence is implemented by `software\\host_uart_operator\\rf_comm_uart_operator.py --mode p4-failure-smoke`.",
                "- Safe wrapper: `tools\\run_p4a_failure_counter_smoke_safe.ps1`.",
                "",
                "Pass requires:",
                "",
                "```text",
                "READ failure_counters rc=0",
                "tx_start_count > 0",
                "tx_done_count > 0",
                "START tx_fail = 0",
                "last_error = none",
                "SHUTDOWN rc=0",
                "```",
                "",
                md_table(["metric", "value"], summary_rows),
                "",
                f"`P4A_FAILURE_COUNTER_SMOKE_PASS = {1 if passed else 0}`",
                "",
            ]
        ),
    )
    return passed


def build_rx_tuning_ab() -> None:
    fields = [
        "build",
        "run",
        "detect_start",
        "detect_end",
        "realign",
        "stage_seconds",
        "payload_bytes",
        "lane_mask",
        "ack_mask",
        "sent",
        "rx_ok",
        "tx_fail",
        "exact_loss",
        "loss_ppm",
        "rx_timeout",
        "rx_bad",
        "rx_mismatch",
        "last_error",
        "shutdown_exit",
        "tx_start_count",
        "tx_done_count",
        "tx_retry_count_total",
        "max_retry_seen",
        "tx_retry_exhausted_count",
        "ack_timeout_count",
        "recovery_count",
        "status",
        "evidence",
    ]
    csv_path = REPORTS / "P4A_02_rx_tuning_ab_results.csv"
    if has_measured_rows(csv_path):
        state = p4a02_state()
        rows = read_csv_rows(csv_path)
        write(
            REPORTS / "P4A_02_rx_tuning_ab_report.md",
            "\n".join(
                [
                    "# P4A-02 RX Tuning A/B Report",
                    "",
                    f"- Status: {state['verdict']}",
                    f"- BuildA measured runs: {state['build_a_measured']}/5; clean={1 if state['build_a_clean'] else 0}.",
                    f"- BuildB measured runs: {state['build_b_measured']}/5; clean={1 if state['build_b_clean'] else 0}.",
                    f"- Selected tuning: `{state['selected'] or 'NONE'}`.",
                    f"- Reason: {state['reason']}.",
                    f"- CSV: `{rel(csv_path)}`",
                    "",
                    md_table(
                        ["build", "run", "sent", "rx_ok", "tx_fail", "loss_ppm", "tx_retry_count_total", "max_retry_seen", "ack_timeout_count", "status"],
                        [
                            [
                                row.get("build", ""),
                                row.get("run", ""),
                                row.get("sent", ""),
                                row.get("rx_ok", ""),
                                row.get("tx_fail", ""),
                                row.get("loss_ppm", ""),
                                row.get("tx_retry_count_total", ""),
                                row.get("max_retry_seen", ""),
                                row.get("ack_timeout_count", ""),
                                row.get("status", ""),
                            ]
                            for row in rows
                        ],
                    ),
                    "",
                ]
            ),
        )
        return

    rows: list[dict[str, object]] = []
    configs = [("BuildA", 3, 7, 1), ("BuildB", 0, 5, 0)]
    for build, ds, de, realign in configs:
        for run in range(1, 6):
            rows.append(
                {
                    "build": build,
                    "run": run,
                    "detect_start": ds,
                    "detect_end": de,
                    "realign": realign,
                    "stage_seconds": 300,
                    "payload_bytes": 256,
                    "lane_mask": "0x1",
                    "ack_mask": "0x1",
                    "status": "NOT_EXECUTED_HARDWARE_REQUIRED",
                    "evidence": "pending P4A_TXACK_DIAG A/B run",
                }
            )
    write_csv(csv_path, fields, rows)
    write(
        REPORTS / "P4A_02_rx_tuning_ab_report.md",
        "\n".join(
            [
                "# P4A-02 RX Tuning A/B Report",
                "",
                "- Status: NOT_EXECUTED_HARDWARE_REQUIRED",
                "- BuildA: detect 3..7, realign=1.",
                "- BuildB: detect 0..5, realign=0.",
                "- Each build still requires 5 x 300s lane0 TX/ACK hardware runs.",
                "- No tuning is promoted by this desktop report.",
                f"- CSV: `{rel(csv_path)}`",
                "",
            ]
        ),
    )


def build_requal() -> None:
    fields = [
        "run",
        "selected_tuning",
        "stage_seconds",
        "payload_bytes",
        "lane_mask",
        "ack_mask",
        "sent",
        "rx_ok",
        "tx_fail",
        "loss_ppm",
        "rx_timeout",
        "rx_bad",
        "rx_mismatch",
        "last_error",
        "shutdown_exit",
        "tx_retry_count_total",
        "max_retry_seen",
        "ack_timeout_count",
        "ack_late_count",
        "recovery_count",
        "status",
        "evidence",
    ]
    csv_path = REPORTS / "P4A_03_lane0_10x300_requal.csv"
    if has_measured_rows(csv_path):
        state = p4a03_state()
        rows = read_csv_rows(csv_path)
        write(
            REPORTS / "P4A_03_lane0_10x300_requal_report.md",
            "\n".join(
                [
                    "# P4A-03 Lane0 10x300s Requalification",
                    "",
                    f"- Status: {state['verdict']}",
                    f"- `P4A_LANE0_TX_ACK_STABILITY_PASS = {1 if state['passed'] else 0}`",
                    f"- Selected tuning: `{state['selected'] or 'UNKNOWN'}`.",
                    f"- Measured runs: {state['measured']}/10.",
                    f"- Reason: {state['reason']}.",
                    f"- CSV: `{rel(csv_path)}`",
                    "",
                    md_table(
                        ["run", "sent", "rx_ok", "tx_fail", "loss_ppm", "rx_timeout", "rx_bad", "rx_mismatch", "last_error", "shutdown_exit", "status"],
                        [
                            [
                                row.get("run", ""),
                                row.get("sent", ""),
                                row.get("rx_ok", ""),
                                row.get("tx_fail", ""),
                                row.get("loss_ppm", ""),
                                row.get("rx_timeout", ""),
                                row.get("rx_bad", ""),
                                row.get("rx_mismatch", ""),
                                row.get("last_error", ""),
                                row.get("shutdown_exit", ""),
                                row.get("status", ""),
                            ]
                            for row in rows
                        ],
                    ),
                    "",
                ]
            ),
        )
        return

    rows = [
        {
            "run": i,
            "selected_tuning": "PENDING_P4A_02",
            "stage_seconds": 300,
            "payload_bytes": 256,
            "lane_mask": "0x1",
            "ack_mask": "0x1",
            "status": "NOT_EXECUTED_HARDWARE_REQUIRED",
            "evidence": "pending selected tuning and 10x300s run",
        }
        for i in range(1, 11)
    ]
    write_csv(csv_path, fields, rows)
    write(
        REPORTS / "P4A_03_lane0_10x300_requal_report.md",
        "\n".join(
            [
                "# P4A-03 Lane0 10x300s Requalification",
                "",
                "- Status: NOT_EXECUTED_HARDWARE_REQUIRED",
                "- `P4A_LANE0_TX_ACK_STABILITY_PASS = 0`",
                "- Reason: P4A-02 tuning selection and 10 clean hardware runs are not available.",
                "- P3 historical blocker remains active: P3-1B-2 had `tx_fail=2`.",
                f"- CSV: `{rel(csv_path)}`",
                "",
            ]
        ),
    )


def build_roundtrip_decision() -> None:
    write(
        REPORTS / "P4B_00_roundtrip_route_decision.md",
        "\n".join(
            [
                "# P4B-00 Roundtrip Route Decision",
                "",
                "- Status: DECISION_COMPLETE_FOR_CURRENT_TOPOLOGY",
                "- Selected current path: Path A.",
                "- `IR_L0_PAYLOAD_ROUNDTRIP_NOT_APPLICABLE_IN_CURRENT_TOPOLOGY = 1`",
                "- `P4B_IR_L0_DATA_ECHO_ROUNDTRIP_PASS = 0`",
                "",
                "Current topology supports A PS -> A PL -> IR DATA -> B PL -> IR ACK -> A PL TX_DONE.",
                "It does not yet prove B PL -> IR DATA echo -> A PL m_axis_rx -> DMA S2MM -> A PS payload compare.",
                "",
                "Command naming boundary:",
                "",
                "```text",
                "TEST tx_dma_ack        # TX/ACK only",
                "TEST rx_dma_synth      # synthetic PL RX -> S2MM -> PS compare",
                "TEST ir_data_roundtrip # real B0 DATA echo -> A S2MM -> PS compare",
                "```",
                "",
            ]
        ),
    )


def build_echo_design() -> None:
    write(
        REPORTS / "P4B_01_b0_echo_responder_design.md",
        "\n".join(
            [
                "# P4B-01 B0 DATA Echo Responder Design",
                "",
                "- Status: DESIGN_REQUIREMENTS_CAPTURED_NOT_IMPLEMENTED",
                "- Gate dependency: do not implement or run before P4A lane0 stability is restored.",
                "",
                "Required behavior:",
                "",
                "```text",
                "A PS DDR payload -> A PL MM2S -> A lane0 IR DATA -> B0 receives DATA",
                "B0 sends ACK as before",
                "B0 after guard sends DATA_ECHO back on lane0",
                "A PL receives DATA_ECHO -> A m_axis_rx -> A S2MM -> A PS DDR -> payload compare",
                "```",
                "",
                "Design constraints:",
                "",
                md_table(
                    ["requirement", "status"],
                    [
                        ["debug/test mode only", "REQUIRED"],
                        ["echo frame distinguishable from ACK", "REQUIRED"],
                        ["no infinite echo loop", "REQUIRED"],
                        ["app seq or verifiable sequence", "REQUIRED"],
                        ["payload 16/64/256 bytes", "REQUIRED"],
                        ["A-side DATA forward to m_axis_rx", "REQUIRED"],
                        ["separate ACK-consumed and DATA-forwarded counters", "REQUIRED"],
                    ],
                ),
                "",
            ]
        ),
    )
    write(
        REPORTS / "P4B_01_b0_echo_responder_sim_report.md",
        "\n".join(
            [
                "# P4B-01 B0 DATA Echo Responder Sim Report",
                "",
                "- Status: NOT_EXECUTED_IMPLEMENTATION_REQUIRED",
                "- No RTL smoke result is claimed.",
                "- Required smoke markers remain pending: B ACK count, B DATA_ECHO count, A rx_data_frame_count, A data_forwarded_to_axis_count, S2MM done.",
                "",
            ]
        ),
    )


def build_ir_roundtrip_results() -> None:
    fields = [
        "case",
        "payload_bytes",
        "count",
        "seconds",
        "sent",
        "tx_ok",
        "tx_fail",
        "dma_rx_packets",
        "rx_ok",
        "rx_timeout",
        "rx_bad",
        "rx_mismatch",
        "verified_bytes",
        "core_tvalid",
        "core_tlast",
        "mux_tvalid",
        "mux_tlast",
        "s2mm_arm_count",
        "s2mm_done_count",
        "s2mm_error_count",
        "s2mm_timeout_count",
        "rx_ack_frame_count",
        "rx_data_frame_count",
        "ack_consumed_internal_count",
        "data_forwarded_to_axis_count",
        "last_error",
        "status",
    ]
    cases = [
        ("IR_RT_016_10", 16, 10, ""),
        ("IR_RT_064_10", 64, 10, ""),
        ("IR_RT_064_100", 64, 100, ""),
        ("IR_RT_256_100", 256, 100, ""),
        ("IR_RT_256_60S", 256, "", 60),
    ]
    rows = [
        {
            "case": case,
            "payload_bytes": payload,
            "count": count,
            "seconds": seconds,
            "status": "NOT_EXECUTED_WAITING_FOR_B0_ECHO_RESPONDER",
        }
        for case, payload, count, seconds in cases
    ]
    write_csv(REPORTS / "P4B_02_ir_data_roundtrip_results.csv", fields, rows)
    write(
        REPORTS / "P4B_02_ir_data_roundtrip_report.md",
        "\n".join(
            [
                "# P4B-02 IR DATA Roundtrip Report",
                "",
                "- Status: NOT_EXECUTED_WAITING_FOR_B0_ECHO_RESPONDER",
                "- `P4B_IR_L0_DATA_ECHO_ROUNDTRIP_PASS = 0`",
                f"- CSV: `{rel(REPORTS / 'P4B_02_ir_data_roundtrip_results.csv')}`",
                "",
            ]
        ),
    )


def build_observability_map() -> None:
    counters = [
        "rx_raw_pulse_count",
        "rx_frame_good_count",
        "rx_ack_frame_count",
        "rx_data_frame_count",
        "rx_crc_fail_count",
        "rx_header_drop_count",
        "rx_session_drop_count",
        "rx_type_drop_count",
        "rx_len_drop_count",
        "ack_consumed_internal_count",
        "data_forwarded_to_axis_count",
        "axis_rx_tvalid_count",
        "axis_rx_tready_count",
        "axis_rx_tlast_count",
        "axis_rx_byte_count",
        "s2mm_arm_count",
        "s2mm_done_count",
        "s2mm_error_count",
        "s2mm_timeout_count",
    ]
    rows = [
        {
            "counter": counter,
            "implementation_status": "REQUIRED_FOR_PATH_B",
            "current_source": "not a confirmed RTL counter in current P4 evidence",
        }
        for counter in counters
    ]
    write_csv(REPORTS / "P4B_03_rx_observability_readout.csv", ["counter", "implementation_status", "current_source"], rows)
    write(
        REPORTS / "P4B_03_rx_observability_rtl_counter_map.md",
        "\n".join(
            [
                "# P4B-03 RX Observability RTL Counter Map",
                "",
                "- Status: SPECIFIED_NOT_IMPLEMENTED_AS_VERIFIED_RTL_READOUT",
                "- Current `READ rx_frame_obs` remains partial/derived unless a future RTL register map proves otherwise.",
                f"- CSV: `{rel(REPORTS / 'P4B_03_rx_observability_readout.csv')}`",
                "",
                md_table(["counter", "status"], [[counter, "REQUIRED_FOR_PATH_B"] for counter in counters]),
                "",
            ]
        ),
    )


def build_lane1_outputs() -> None:
    fields = ["repeat", "direction", "expected", "observed", "classification", "status", "evidence"]
    directions = [
        ("A_TX0_to_B_RX0", "raw pulse present"),
        ("A_TX1_to_B_RX1", "raw pulse absent before P4"),
        ("B_TX0_to_A_RX0", "raw pulse candidate"),
        ("B_TX1_to_A_RX1", "raw pulse capable before P4"),
    ]
    rows = []
    for repeat in range(1, 4):
        for direction, expected in directions:
            rows.append(
                {
                    "repeat": repeat,
                    "direction": direction,
                    "expected": expected,
                    "classification": "NOT_RETESTED_IN_P4",
                    "status": "NOT_EXECUTED_WAITING_FOR_P4A_PASS",
                    "evidence": "lane1 diagnostics gated behind lane0 stability",
                }
            )
    write_csv(REPORTS / "P4C_01_AB_L1_deep_diag_matrix.csv", fields, rows)
    write(
        REPORTS / "P4C_01_AB_L1_deep_diag_report.md",
        "\n".join(
            [
                "# P4C-01 AB_L1 Deep Diagnostic Report",
                "",
                "- Status: NOT_EXECUTED_WAITING_FOR_P4A_PASS",
                "- Purpose is classification only, not lane1 repair or promotion.",
                "- Existing boundary remains: A->B lane1 far B_RX1 had no raw pulse; B->A lane1 had raw pulse capability.",
                f"- CSV: `{rel(REPORTS / 'P4C_01_AB_L1_deep_diag_matrix.csv')}`",
                "",
            ]
        ),
    )
    write(
        REPORTS / "P4D_01_BA_L1_asymmetric_protocol_candidate.md",
        "\n".join(
            [
                "# P4D-01 BA_L1 Asymmetric Protocol Candidate",
                "",
                "- Status: NOT_EXECUTED_WAITING_FOR_DEPENDENCIES",
                "- Required first: `P4A_LANE0_TX_ACK_STABILITY_PASS = 1`.",
                "- Required boundary: A-side DATA RX path semantics are explicit.",
                "- Required boundary: P4B echo roundtrip pass or explicit decision that real DATA return is not needed.",
                "- `P4D_BA_L1_ASYMMETRIC_PROTOCOL_CANDIDATE_PASS = 0`",
                "- `REAL_2LANE_FULL_PASS = 0`",
                "",
            ]
        ),
    )


def build_promotion_gate(failure_smoke_pass: bool) -> None:
    lane0_rows = p3_lane0_rows()
    blocker = next((row for row in lane0_rows if row.get("run_id") == "P3-1B-2"), None)
    blocker_text = ""
    if blocker:
        blocker_text = f"P3-1B-2: sent={blocker.get('sent')} rx_ok={blocker.get('rx_ok')} tx_fail={blocker.get('tx_fail')} loss_ppm={blocker.get('loss_ppm')}"
    p4a02 = p4a02_state()
    p4a03 = p4a03_state()
    txack_pass = bool(failure_smoke_pass and p4a02["verdict"] == "PASS" and p4a03["passed"])
    txack_status = "PASS" if txack_pass else "0"
    promotion_status = "PASS" if txack_pass else "FAIL"
    promotion_reason = (
        "P4A failure counter smoke, RX tuning A/B, and 10x300s lane0 requalification passed."
        if txack_pass
        else str(p4a03["reason"] if p4a02["verdict"] == "PASS" else p4a02["reason"])
    )
    matrix_rows = [
        ["P4_00_baseline_policy", "PASS", "P2 remains last accepted baseline"],
        ["P4_01_build_profiles", "PASS", "profiles and manifests generated"],
        ["P4A_01_failure_counter_smoke", "PASS" if failure_smoke_pass else "0", "hardware smoke required for pass"],
        ["P4A_02_rx_tuning_ab", p4a02["verdict"], p4a02["reason"]],
        ["P4A_03_lane0_10x300_requal", p4a03["verdict"], p4a03["reason"]],
        ["P4B_00_roundtrip_route_decision", "PASS", "Path A selected for current topology"],
        ["P4B_01_b0_echo_responder", "0", "not implemented"],
        ["P4B_02_ir_data_roundtrip", "0", "not executed"],
        ["P4B_03_rx_observability_rtl", "0", "spec only"],
        ["P4C_01_AB_L1_deep_diag", "0", "gated behind P4A"],
        ["P4D_01_BA_L1_asym_candidate", "0", "gated behind P4A/P4B"],
    ]
    write(
        REPORTS / "P4_acceptance_matrix.md",
        "\n".join(
            [
                "# P4 Acceptance Matrix",
                "",
                md_table(["item", "status", "reason"], matrix_rows),
                "",
            ]
        ),
    )
    write(
        REPORTS / "P4_promotion_gate.md",
        "\n".join(
            [
                "# P4 Promotion Gate",
                "",
                f"- `P4_CONSTRAINED_TXACK_OPERATIONAL_BASELINE_PASS = {1 if txack_pass else 0}`",
                "- `P4_CONSTRAINED_IR_DATA_ECHO_BASELINE_PASS = 0`",
                f"- Promotion gate: {promotion_status}",
                f"- Reason: {promotion_reason}",
                f"- Selected P4A tuning: `{p4a02['selected'] or p4a03['selected'] or 'NONE'}`",
                f"- P4A TX/ACK matrix status: {txack_status}",
                f"- Active P3 blocker: {blocker_text or 'P3 lane0 blocker evidence unavailable'}",
                "- Forbidden promotions remain 0: FINAL_TARGET_PASS, REAL_ETHERNET_PASS, REAL_ROTATION_PASS, REAL_2LANE_FULL_PASS.",
                "",
            ]
        ),
    )


def build_index() -> None:
    outputs = [
        "P4_00_baseline_policy.md",
        "P4_01_build_profiles.md",
        "P4A_TXACK_DIAG_build_manifest.md",
        "P4B_DATA_ROUNDTRIP_DIAG_build_manifest.md",
        "P4A_01_failure_counter_smoke.md",
        "P4A_01_failure_counter_smoke.log",
        "P4A_02_rx_tuning_ab_results.csv",
        "P4A_02_rx_tuning_ab_report.md",
        "P4A_03_lane0_10x300_requal.csv",
        "P4A_03_lane0_10x300_requal_report.md",
        "P4B_00_roundtrip_route_decision.md",
        "P4B_01_b0_echo_responder_design.md",
        "P4B_01_b0_echo_responder_sim_report.md",
        "P4B_02_ir_data_roundtrip_results.csv",
        "P4B_02_ir_data_roundtrip_report.md",
        "P4B_03_rx_observability_rtl_counter_map.md",
        "P4B_03_rx_observability_readout.csv",
        "P4C_01_AB_L1_deep_diag_matrix.csv",
        "P4C_01_AB_L1_deep_diag_report.md",
        "P4D_01_BA_L1_asymmetric_protocol_candidate.md",
        "P4_acceptance_matrix.md",
        "P4_promotion_gate.md",
    ]
    rows = [[name, "YES" if (REPORTS / name).exists() else "MISSING"] for name in outputs]
    write(
        REPORTS / "P4_00_plan_execution_index.md",
        "\n".join(
            [
                "# P4 Plan Execution Index",
                "",
                f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
                "- Scope: desktop-completable P4 execution package plus explicit hardware-pending gates.",
                "- Constraint: no P4 artifact is promoted without required hardware evidence.",
                "",
                md_table(["output", "present"], rows),
                "",
            ]
        ),
    )


def main() -> int:
    build_baseline_policy()
    build_profiles()
    build_manifest("P4A_TXACK_DIAG", "1", "BuildB", "lane0 TX/ACK stability and retry/failure counter capture")
    build_manifest("P4B_DATA_ROUNDTRIP_DIAG", "0", "BuildB", "real IR DATA echo roundtrip attempt")
    failure_smoke_pass = build_failure_smoke()
    build_rx_tuning_ab()
    build_requal()
    build_roundtrip_decision()
    build_echo_design()
    build_ir_roundtrip_results()
    build_observability_map()
    build_lane1_outputs()
    build_promotion_gate(failure_smoke_pass)
    build_index()
    print("P4_CONSTRAINED_EXECUTION_REPORTS_BUILT=1")
    print(f"REPORT_INDEX={REPORTS / 'P4_00_plan_execution_index.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
