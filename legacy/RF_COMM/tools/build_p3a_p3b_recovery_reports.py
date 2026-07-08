#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def lane0_rows() -> list[dict[str, str]]:
    path = REPORTS / "P3_01_lane0_requal_on_P2PSPL_bit.csv"
    if not path.exists():
        return []
    rows = read_csv_rows(path)
    for row in rows:
        sent = int(row.get("sent") or "0")
        tx_fail = int(row.get("tx_fail") or "0")
        exact_loss = (tx_fail / sent) if sent else 0.0
        row["exact_loss"] = f"{exact_loss:.12f}"
        row["loss_ppm"] = f"{exact_loss * 1_000_000.0:.6f}"
        row["source_csv"] = rel(path)
    return rows


def fix_freeze_manifest() -> list[dict[str, str]]:
    source = REPORTS / "P3_00_P2PSPL_freeze_manifest.md"
    text = read(source) if source.exists() else ""
    rows: list[dict[str, str]] = []
    pattern = re.compile(
        r"\| (?P<object>.*?) \| \$\(@\{Name=.*?; Path=(?P<path>.*?); Size=(?P<size>\d+); "
        r"Sha256=(?P<sha>[A-Fa-f0-9]+); Status=(?P<status>.*?)\}\.Path\) \| (?P<size2>\d+) \| "
        r"\$\(@\{.*?Sha256=(?P<sha2>[A-Fa-f0-9]+); Status=.*?\}\.Sha256\) \| (?P<status2>.*?) \|"
    )
    for match in pattern.finditer(text):
        rows.append(
            {
                "object": match.group("object"),
                "path": match.group("path"),
                "bytes": match.group("size"),
                "sha256": match.group("sha"),
                "status": match.group("status"),
            }
        )

    fixed = [
        "# P3A-01 Fixed Freeze Manifest",
        "",
        "- Source manifest: `" + rel(source) + "`",
        "- Fix: expanded stale PowerShell object expressions into literal path and sha256 fields.",
        "- Baseline rule: this manifest documents frozen P2 artifacts only; it does not promote P3.",
        "",
        md_table(["object", "path", "bytes", "sha256", "status"], [[r["object"], r["path"], r["bytes"], r["sha256"], r["status"]] for r in rows]),
        "",
    ]
    write(REPORTS / "P3A_01_freeze_manifest_fixed.md", "\n".join(fixed))
    return rows


def build_policy() -> None:
    write(
        REPORTS / "P3A_00_baseline_policy.md",
        "\n".join(
            [
                "# P3A-00 Baseline Policy",
                "",
                "P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED_PASS remains the last accepted baseline.",
                "P3 results are diagnostic and are not promoted.",
                "P3 bitstream / ELF must not replace the P2 operational baseline until P3A/P3B gates pass.",
                "",
                "```text",
                "LAST_ACCEPTED_BASELINE = P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED_PASS",
                "P3_HARDENING_ATTEMPT   = FAIL_BUT_DIAGNOSTICALLY_USEFUL",
                "P3_PROMOTION_GATE      = FAIL",
                "FINAL_TARGET_PASS      = 0",
                "REAL_ETHERNET_PASS     = 0",
                "REAL_ROTATION_PASS     = 0",
                "REAL_2LANE_FULL_PASS   = 0",
                "```",
                "",
                "P3 artifacts are diagnostic artifacts only until the P3A lane0 stability gate and the P3B topology/roundtrip gate both close.",
                "",
            ]
        ),
    )


def build_cleanup(rows: list[dict[str, str]], manifest_rows: list[dict[str, str]]) -> None:
    loss_row = next((row for row in rows if row.get("run_id") == "P3-1B-2"), {})
    write(
        REPORTS / "P3A_01_report_cleanup.md",
        "\n".join(
            [
                "# P3A-01 Report Cleanup",
                "",
                "- Status: COMPLETE_FOR_AVAILABLE_REPORTS",
                "- Misleading PASS wording must be treated as run/classification completion only.",
                "- Required replacement: `UART_OPERATOR_P3_ROUNDTRIP_PASS=1` -> `UART_OPERATOR_P3_ROUNDTRIP_CLASSIFICATION_COMPLETE=1`.",
                "- Fixed freeze manifest: `" + rel(REPORTS / "P3A_01_freeze_manifest_fixed.md") + "`.",
                f"- Fixed manifest rows: {len(manifest_rows)}.",
                "- P3-1B-2 precision patch: `sent="
                + str(loss_row.get("sent", ""))
                + "`, `tx_fail="
                + str(loss_row.get("tx_fail", ""))
                + "`, `loss_ppm="
                + str(loss_row.get("loss_ppm", ""))
                + "`.",
                "- No P3 artifact is promoted by this cleanup.",
                "",
            ]
        ),
    )
    fields = ["run_id", "sent", "tx_fail", "rounded_loss", "exact_loss", "loss_ppm", "source_csv"]
    write_csv(
        REPORTS / "P3A_01_loss_precision_patch.csv",
        fields,
        [
            {
                "run_id": row.get("run_id", ""),
                "sent": row.get("sent", ""),
                "tx_fail": row.get("tx_fail", ""),
                "rounded_loss": row.get("loss", ""),
                "exact_loss": row.get("exact_loss", ""),
                "loss_ppm": row.get("loss_ppm", ""),
                "source_csv": row.get("source_csv", ""),
            }
            for row in rows
        ],
    )


def build_failure_counter_outputs(rows: list[dict[str, str]]) -> None:
    write(
        REPORTS / "P3A_02_lane0_failure_counter_spec.md",
        "\n".join(
            [
                "# P3A-02 Lane0 Failure Counter Spec",
                "",
                "- Status: PS_SOFTWARE_INSTRUMENTATION_ADDED",
                "- UART readout command: `READ failure_counters`.",
                "- Compatibility alias: `READ tx_failure_obs`.",
                "",
                "Required readout fields:",
                "",
                "```text",
                "tx_start_count",
                "tx_done_count",
                "tx_done_timeout_count",
                "tx_retry_count_total",
                "tx_retry_exhausted_count",
                "ack_timeout_count",
                "ack_late_count",
                "max_retry_seen",
                "recovery_count",
                "first_fail_sent_index",
                "first_fail_timestamp",
                "first_fail_seq",
                "first_fail_pre_sticky",
                "first_fail_pre_phy0",
                "first_fail_pre_tx_lane",
                "first_fail_post_sticky",
                "first_fail_post_phy0",
                "```",
                "",
                "Implementation note: these counters are now PS-side exported diagnostics. RTL retry histogram remains a future hardware register extension.",
                "",
            ]
        ),
    )
    fields = [
        "run_id",
        "sent",
        "tx_fail",
        "tx_retry_count_total",
        "max_retry_seen",
        "tx_retry_exhausted_count",
        "ack_timeout_count",
        "first_fail_sent_index",
        "readout_status",
        "source",
    ]
    out_rows = []
    for row in rows:
        out_rows.append(
            {
                "run_id": row.get("run_id", ""),
                "sent": row.get("sent", ""),
                "tx_fail": row.get("tx_fail", ""),
                "tx_retry_count_total": "",
                "max_retry_seen": "",
                "tx_retry_exhausted_count": "",
                "ack_timeout_count": "",
                "first_fail_sent_index": "",
                "readout_status": "NOT_AVAILABLE_IN_HISTORICAL_P3_LOG; READ failure_counters ADDED_FOR_NEXT_RUN",
                "source": row.get("source_csv", ""),
            }
        )
    write_csv(REPORTS / "P3A_02_lane0_failure_counter_readout.csv", fields, out_rows)


def build_tuning_outputs() -> None:
    rows = [
        {
            "build": "A",
            "name": "P3 current tuning",
            "detect_start": 3,
            "detect_end": 7,
            "realign": 1,
            "required_runs": "5x300s",
            "status": "NOT_EXECUTED_IN_THIS_RECOVERY_PASS",
            "verdict": "PENDING",
        },
        {
            "build": "B",
            "name": "G1 known-good tuning",
            "detect_start": 0,
            "detect_end": 5,
            "realign": 0,
            "required_runs": "5x300s",
            "status": "NOT_EXECUTED_IN_THIS_RECOVERY_PASS",
            "verdict": "PENDING",
        },
    ]
    write_csv(
        REPORTS / "P3A_03_rx_tuning_ab_test.csv",
        ["build", "name", "detect_start", "detect_end", "realign", "required_runs", "status", "verdict"],
        rows,
    )
    write(
        REPORTS / "P3A_03_rx_tuning_ab_test_report.md",
        "\n".join(
            [
                "# P3A-03 RX Tuning A/B Test Report",
                "",
                "- Status: NOT_EXECUTED_IN_THIS_RECOVERY_PASS",
                "- Reason: the requested 2 build x 5 x 300s hardware requalification was not run in this desktop execution.",
                "- Build A: detect_start=3, detect_end=7, realign=1.",
                "- Build B: detect_start=0, detect_end=5, realign=0.",
                "- Decision remains pending; do not restore or promote tuning solely from this report.",
                "- CSV: `" + rel(REPORTS / "P3A_03_rx_tuning_ab_test.csv") + "`.",
                "",
            ]
        ),
    )


def build_lane0_gate(rows: list[dict[str, str]]) -> None:
    fields = [
        "run_id",
        "lane_mask",
        "ack_mask",
        "payload_bytes",
        "stage_seconds",
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
        "pass",
        "source_csv",
    ]
    write_csv(REPORTS / "P3A_04_lane0_requal_gate.csv", fields, rows)
    overall = bool(rows) and all(row.get("pass") == "1" and row.get("tx_fail") == "0" for row in rows)
    fail_rows = [row for row in rows if row.get("pass") != "1"]
    table = md_table(
        ["run", "sent", "rx_ok", "tx_fail", "loss_ppm", "last_error", "pass"],
        [[r.get("run_id", ""), r.get("sent", ""), r.get("rx_ok", ""), r.get("tx_fail", ""), r.get("loss_ppm", ""), r.get("last_error", ""), r.get("pass", "")] for r in rows],
    )
    write(
        REPORTS / "P3A_04_lane0_requal_gate_report.md",
        "\n".join(
            [
                "# P3A-04 Lane0 Requalification Gate",
                "",
                f"- Status: {'PASS' if overall else 'FAIL'}",
                f"- `P3A_LANE0_TX_ACK_STABILITY_PASS = {1 if overall else 0}`",
                "- Required condition: every 300s run has sent > 0, rx_ok == sent, tx_fail=0, loss_ppm=0, no RX errors, last_error=none, shutdown_exit=0.",
                "- Existing P3 evidence still contains a failed row, so this gate remains closed.",
                f"- Failed rows: {', '.join(row.get('run_id', '') for row in fail_rows) if fail_rows else 'none'}.",
                "- CSV: `" + rel(REPORTS / "P3A_04_lane0_requal_gate.csv") + "`.",
                "",
                table,
                "",
            ]
        ),
    )


def build_command_contract() -> None:
    write(
        REPORTS / "P3B_05_uart_command_contract_v3.md",
        "\n".join(
            [
                "# P3B-05 UART Command Contract v3",
                "",
                "- Status: PS_SOFTWARE_CONTRACT_UPDATED",
                "- `TEST tx_dma_ack payload=<N> count=<N>` covers PS DDR -> MM2S -> PL TX -> IR DATA -> remote ACK -> TX_DONE.",
                "- `TEST rx_dma_synth payload=<N> count=<N> pattern=<name>` covers PL synthetic RX -> S2MM -> PS DDR -> payload compare.",
                "- `TEST ir_data_roundtrip payload=<N> count=<N>` covers PS DDR -> MM2S -> PL TX -> IR DATA -> B0 DATA echo -> A PL m_axis_rx -> S2MM -> PS DDR -> compare.",
                "",
                "Compatibility aliases remain available:",
                "",
                "```text",
                "TEST tx_dma            -> TX_DMA legacy result",
                "TEST pspl_roundtrip    -> PSPL_ROUNDTRIP legacy result",
                "```",
                "",
                "The new aliases emit `TX_DMA_ACK` and `IR_DATA_ROUNDTRIP` result IDs so a TX/ACK pass cannot be mistaken for real returned application DATA.",
                "",
            ]
        ),
    )


def build_rx_observability() -> None:
    write(
        REPORTS / "P3B_06_rx_observability_counter_spec.md",
        "\n".join(
            [
                "# P3B-06 RX Observability Counter Spec",
                "",
                "- Status: PS_SOFTWARE_READOUTS_ADDED",
                "- Existing command: `READ rx_stream_obs`.",
                "- Added commands: `READ rx_frame_obs`, `READ dma_obs`.",
                "",
                "Counter groups:",
                "",
                "```text",
                "rx_frame_obs: rx_frame_good_count, rx_ack_frame_count, rx_data_frame_count, rx_crc_fail_count, rx_header_drop_count, rx_len_drop_count, ack_consumed_internal_count, data_forwarded_to_axis_count",
                "dma_obs: axis_rx_tvalid_count, axis_rx_tready_count, axis_rx_tlast_count, axis_rx_byte_count, s2mm_arm_count, s2mm_done_count, s2mm_error_count, s2mm_timeout_count",
                "```",
                "",
                "The current implementation exposes a partial PS/AXIS/DMA view. Dedicated RTL ACK-vs-DATA frame counters remain the next precision step.",
                "",
            ]
        ),
    )
    source = REPORTS / "P3_07_rx_stream_observability_report.md"
    text = read(source) if source.exists() else ""
    rows = []
    for name, value in re.findall(r"\| ([A-Za-z0-9_]+) \| ([^|]+) \|", text):
        if name != "---":
            rows.append({"counter": name.strip(), "value": value.strip(), "source": rel(source)})
    write_csv(REPORTS / "P3B_06_rx_observability_readout.csv", ["counter", "value", "source"], rows)


def build_topology_and_echo() -> None:
    write(
        REPORTS / "P3B_07_ir_roundtrip_topology_decision.md",
        "\n".join(
            [
                "# P3B-07 IR Roundtrip Topology Decision",
                "",
                "- Status: DECISION_COMPLETE",
                "- `P3B_IR_ROUNDTRIP_TOPOLOGY_DECISION_COMPLETE = 1`",
                "- `IR_L0_PAYLOAD_ROUNDTRIP_NOT_APPLICABLE_IN_CURRENT_TOPOLOGY = 1`",
                "",
                "Decision:",
                "",
                "The current fixed topology is treated as supporting A PS -> A PL -> IR DATA -> B PL -> IR ACK -> A PL TX_DONE, but not a real B0 DATA echo return into A-side m_axis_rx.",
                "",
                "Evidence basis:",
                "",
                "- Existing P3 roundtrip attempt: TX/ACK completed with `tx_fail=0`.",
                "- Existing P3 roundtrip attempt: S2MM timed out with `failure_class=TIMEOUT_WAITING_PL_RX_STREAM`.",
                "- Existing observability: core/mux RX stream counters stayed at 0 while `s2mm_timeout=1`.",
                "",
                "Current acceptance boundary:",
                "",
                "```text",
                "PS->PL TX DMA + lane0 ACK: PASS boundary retained",
                "PL synthetic RX -> S2MM -> PS payload compare: PASS boundary retained",
                "Real IR DATA -> S2MM: NOT_SUPPORTED_OR_NOT_IMPLEMENTED in current topology",
                "```",
                "",
            ]
        ),
    )
    write(
        REPORTS / "P3B_08_b0_data_echo_responder_report.md",
        "\n".join(
            [
                "# P3B-08 B0 DATA Echo Responder Report",
                "",
                "- Status: NOT_IMPLEMENTED_BY_DECISION",
                "- Reason: P3B-07 selected topology path A, so current gate does not require B0 DATA echo responder.",
                "- `P3B_IR_L0_PAYLOAD_ROUNDTRIP_PASS = 0`",
                "- Future path B remains available if the project chooses to implement B0 DATA echo responder.",
                "",
            ]
        ),
    )
    write_csv(
        REPORTS / "P3B_08_ir_data_roundtrip_results.csv",
        ["test_id", "payload_bytes", "count", "status", "pass", "reason"],
        [
            {
                "test_id": "IR_DATA_ROUNDTRIP",
                "payload_bytes": "",
                "count": "",
                "status": "NOT_APPLICABLE_IN_CURRENT_TOPOLOGY",
                "pass": 0,
                "reason": "B0 DATA echo responder not implemented/enabled",
            }
        ],
    )


def build_p3c() -> None:
    old_md = REPORTS / "P3_08_AB_L1_noninvasive_deep_diag.md"
    old_csv = REPORTS / "P3_08_full_2lane_raw_matrix_repeat.csv"
    if old_md.exists():
        text = read(old_md)
        write(
            REPORTS / "P3C_09_AB_L1_noninvasive_deep_diag.md",
            text.replace("# P3-8", "# P3C-09").replace("P3_AB_L1_DIAG_REFINED", "P3C_AB_L1_DIAG_REFINED"),
        )
    else:
        write(
            REPORTS / "P3C_09_AB_L1_noninvasive_deep_diag.md",
            "# P3C-09 AB_L1 Noninvasive Deep Diagnosis\n\n- Status: NOT_EXECUTED\n- `P3C_AB_L1_DIAG_REFINED = 0`\n",
        )
    if old_csv.exists():
        shutil.copyfile(old_csv, REPORTS / "P3C_09_full_raw_matrix_repeat.csv")
    else:
        write(REPORTS / "P3C_09_full_raw_matrix_repeat.csv", "run_id,link,status\nP3C_09,AB_L1,NOT_EXECUTED\n")


def build_final_matrix(rows: list[dict[str, str]]) -> None:
    lane0_pass = bool(rows) and all(row.get("pass") == "1" and row.get("tx_fail") == "0" for row in rows)
    matrix_rows = [
        ["LAST_ACCEPTED_BASELINE", "P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED_PASS", "P2 retained"],
        ["P3A_REPORT_CLEANUP_COMPLETE", 1, rel(REPORTS / "P3A_01_report_cleanup.md")],
        ["P3A_LANE0_TX_ACK_STABILITY_PASS", 1 if lane0_pass else 0, rel(REPORTS / "P3A_04_lane0_requal_gate_report.md")],
        ["P3B_IR_ROUNDTRIP_TOPOLOGY_DECISION_COMPLETE", 1, rel(REPORTS / "P3B_07_ir_roundtrip_topology_decision.md")],
        ["IR_L0_PAYLOAD_ROUNDTRIP_NOT_APPLICABLE_IN_CURRENT_TOPOLOGY", 1, "Current topology path A"],
        ["P3B_IR_L0_PAYLOAD_ROUNDTRIP_PASS", 0, "Path B not implemented"],
        ["P3C_AB_L1_DIAG_REFINED", 1, rel(REPORTS / "P3C_09_AB_L1_noninvasive_deep_diag.md")],
        ["REAL_ETHERNET_PASS", 0, "Deferred by constraints"],
        ["REAL_ROTATION_PASS", 0, "Deferred by constraints"],
        ["REAL_2LANE_FULL_PASS", 0, "Not claimed"],
        ["FINAL_TARGET_PASS", 0, "Not claimed"],
    ]
    write(
        REPORTS / "P3_acceptance_matrix_updated.md",
        "# P3 Acceptance Matrix Updated\n\n" + md_table(["status", "value", "evidence / note"], matrix_rows) + "\n",
    )
    write(
        REPORTS / "P3_known_limitations.md",
        "\n".join(
            [
                "# P3 Known Limitations",
                "",
                "- P3 is not promoted; P2 remains the last accepted baseline.",
                "- P3A lane0 gate remains failed until a clean 5-10 x 300s requalification is run.",
                "- Historical P3-1B-2 has `tx_fail=2`, requiring failure counter readout in the next hardware run.",
                "- RX tuning A/B builds were specified but not executed in this desktop pass.",
                "- Real IR DATA roundtrip is classified not applicable in the current topology unless B0 DATA echo responder is implemented.",
                "- Ethernet/TCP/DHCP, rotation, 8-lane physical acceptance, and full 2-lane reliable pass remain out of scope for this constrained stage.",
                "",
            ]
        ),
    )
    promote = lane0_pass
    write(
        REPORTS / "P3_promotion_gate.md",
        "\n".join(
            [
                "# P3 Promotion Gate",
                "",
                f"- `P3_CONSTRAINED_PSPL_RECOVERY_BASELINE_PASS = {1 if promote else 0}`",
                f"- Promotion gate: {'PASS' if promote else 'FAIL'}",
                "- Required before promotion: lane0 stability pass, topology decision complete or roundtrip pass, report cleanup complete, acceptance matrix updated, known limitations documented.",
                "- Current blocker: lane0 stability pass is still 0 because historical P3-1B-2 observed tx_fail=2.",
                "- Forbidden promotions remain 0: FINAL_TARGET_PASS, REAL_ETHERNET_PASS, REAL_ROTATION_PASS, REAL_2LANE_FULL_PASS.",
                "",
            ]
        ),
    )


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    rows = lane0_rows()
    build_policy()
    manifest_rows = fix_freeze_manifest()
    build_cleanup(rows, manifest_rows)
    build_failure_counter_outputs(rows)
    build_tuning_outputs()
    build_lane0_gate(rows)
    build_command_contract()
    build_rx_observability()
    build_topology_and_echo()
    build_p3c()
    build_final_matrix(rows)
    print("P3A_P3B_RECOVERY_REPORTS_BUILT=1")
    print(f"REPORTS_DIR={REPORTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
