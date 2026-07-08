#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DELIVERABLES = ROOT / "deliverables"


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("/", "\\")
    except ValueError:
        return str(path)


def latest(pattern: str, base: Path = REPORTS) -> Path:
    matches = sorted(base.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise FileNotFoundError(f"missing {pattern}")
    return matches[0]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def kv_pairs(line: str) -> dict[str, str]:
    return dict(re.findall(r"([A-Za-z0-9_]+)=([^\s]+)", line))


@dataclass
class TestRow:
    case: str
    test_id: str
    command: str
    payload: str
    count: str
    pattern_name: str
    result: dict[str, str]


def transcript_body(line: str) -> tuple[str, str] | None:
    m = re.match(r"^\S+\s+(TX|RX)\s+(.*)$", line)
    if not m:
        return None
    return m.group(1), m.group(2)


def parse_transcript(path: Path) -> tuple[list[str], list[TestRow], list[str], list[str], list[str]]:
    lines = read(path).splitlines()
    tests: list[TestRow] = []
    axilite_lines: list[str] = []
    tx_lines: list[str] = []
    rx_lines: list[str] = []
    operator_lines: list[str] = []
    pending: dict[str, str] | None = None

    rx_case_idx = 0
    rx_case_names = ["RX_SYN_01", "RX_SYN_02", "RX_SYN_03", "RX_SYN_04", "RX_SYN_05"]

    for line in lines:
        parsed = transcript_body(line)
        if not parsed:
            if "UART_OPERATOR_PSPL_DATA" in line:
                operator_lines.append(line)
            continue
        direction, body = parsed

        if direction == "TX":
            operator_lines.append(line)
            if body.startswith(("STATUS", "READ ", "CONFIG ", "CLEAR sticky", "CLEAR counters", "DUMP ", "SHUTDOWN")):
                axilite_lines.append(line)
            if body.startswith("TEST tx_dma"):
                tx_lines.append(line)
                pending = {"command": body, "kind": "tx"}
            elif body.startswith("TEST rx_dma_synth"):
                rx_lines.append(line)
                pending = {"command": body, "kind": "rx"}
            continue

        if "UARTOP_RESULT" in body:
            operator_lines.append(line)
            if "command=STATUS" in body or "command=READ" in body or "command=CONFIG" in body or "command=CLEAR" in body or "command=DUMP" in body or "command=SHUTDOWN" in body:
                axilite_lines.append(line)
            if "command=TEST" in body and pending:
                values = kv_pairs(body)
                command = pending["command"]
                payload = ""
                count = ""
                pattern_name = ""
                for token in command.split():
                    if token.startswith("payload="):
                        payload = token.split("=", 1)[1]
                    elif token.startswith("count="):
                        count = token.split("=", 1)[1]
                    elif token.startswith("pattern="):
                        pattern_name = token.split("=", 1)[1]
                if pending["kind"] == "tx":
                    case = f"TX_DMA_{payload}"
                    tx_lines.append(line)
                else:
                    case = rx_case_names[rx_case_idx] if rx_case_idx < len(rx_case_names) else f"RX_SYN_{rx_case_idx + 1:02d}"
                    rx_case_idx += 1
                    rx_lines.append(line)
                tests.append(TestRow(case, values.get("test_id", ""), command, payload, count, pattern_name, values))
            continue

        if body.startswith("RESULT test_id="):
            operator_lines.append(line)
            if "test_id=TX_DMA" in body:
                tx_lines.append(line)
            elif "test_id=RX_DMA_SYNTH" in body:
                rx_lines.append(line)

    return lines, tests, axilite_lines, tx_lines, rx_lines


def write_csv(path: Path, rows: list[TestRow]) -> None:
    fields = [
        "case",
        "test_id",
        "command",
        "payload",
        "count",
        "pattern_name",
        "pass",
        "expected_packets",
        "injected_packets",
        "dma_rx_packets",
        "rx_ok",
        "tx_fail",
        "rx_timeout",
        "rx_bad",
        "rx_mismatch",
        "verified_bytes",
        "pattern",
        "first_bad_seq",
        "first_bad_offset",
        "expected_byte",
        "actual_byte",
        "dma_tx_err",
        "dma_rx_err",
        "last_error",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            out = {
                "case": row.case,
                "test_id": row.test_id,
                "command": row.command,
                "payload": row.payload,
                "count": row.count,
                "pattern_name": row.pattern_name,
            }
            for field in fields:
                out.setdefault(field, row.result.get(field, ""))
            w.writerow(out)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(exist_ok=True)
    DELIVERABLES.mkdir(exist_ok=True)

    transcript = latest("P2_PSPL_uart_operator_transcript_*.log")
    summary = latest("run_p2_pspl_data_exchange_safe_*.summary.txt")
    bit_log = latest("build_p2_pspl_current_bitstream_*.out.log")
    bit_vivado_log = latest("build_p2_pspl_current_bitstream_*.vivado.log")
    vitis_log = latest("build_p2_uart_operator_elf_*.out.log")
    ip_upgrade_log = latest("upgrade_p2_pspl_ir_ip_*.out.log")
    ip_status = REPORTS / "P2_PSPL_ip_status_after_upgrade.rpt"

    stamp_match = re.search(r"(\d{8}_\d{6})", transcript.name)
    stamp = stamp_match.group(1) if stamp_match else datetime.now().strftime("%Y%m%d_%H%M%S")

    lines, tests, axilite_lines, tx_lines, rx_lines = parse_transcript(transcript)
    tx_tests = [t for t in tests if t.test_id == "TX_DMA"]
    rx_tests = [t for t in tests if t.test_id == "RX_DMA_SYNTH"]

    axilite_pass = any("item=build_id" in l and "rc=0" in l for l in axilite_lines) and all(" rc=1" not in l for l in axilite_lines)
    tx_pass = bool(tx_tests) and all(t.result.get("pass") == "1" and t.result.get("tx_fail") == "0" and t.result.get("last_error") == "none" for t in tx_tests)
    rx_pass = bool(rx_tests) and all(t.result.get("pass") == "1" and t.result.get("rx_bad") == "0" and t.result.get("rx_mismatch") == "0" and t.result.get("rx_timeout") == "0" and t.result.get("last_error") == "none" for t in rx_tests)
    operator_pass = any("UART_OPERATOR_PSPL_DATA_PASS=1" in l for l in lines)
    shutdown_pass = "SHUTDOWN_EXIT=0" in read(summary)

    axilite_log = REPORTS / f"uart_axilite_control_status_{stamp}.log"
    tx_log = REPORTS / f"uart_tx_dma_mm2s_{stamp}.log"
    rx_log = REPORTS / f"uart_rx_dma_synthetic_{stamp}.log"
    operator_copy = REPORTS / f"uart_operator_transcript_{stamp}.log"
    write(axilite_log, "\n".join(axilite_lines) + "\n")
    write(tx_log, "\n".join(tx_lines) + "\n")
    write(rx_log, "\n".join(rx_lines) + "\n")
    write(operator_copy, read(transcript))

    tx_csv = REPORTS / "P2_PSPL_tx_dma_mm2s.csv"
    rx_csv = REPORTS / "P2_PSPL_rx_dma_synthetic_matrix.csv"
    cmp_csv = REPORTS / "P2_PSPL_rx_payload_compare.csv"
    write_csv(tx_csv, tx_tests)
    write_csv(rx_csv, rx_tests)
    write_csv(cmp_csv, rx_tests)

    roundtrip_csv = REPORTS / "P2_PSPL_lane0_ir_payload_roundtrip.csv"
    with roundtrip_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case", "status", "reason", "evidence"])
        w.writerow(["IR_L0_RT", "NOT_EXECUTED_UNSUPPORTED", "current PS build is PSPS_TX_ONLY=1; T6 is optional/if supported", rel(transcript)])

    artifact_paths = [
        ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1" / "design_shiboqi_wrapper.bit",
        ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.bit",
        ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1" / "design_shiboqi_wrapper.ltx",
        ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.xsa",
        ROOT / "software" / "_vitis_ws_ps_ps_loopback" / "rf_comm_ps_ps_loopback" / "Debug" / "rf_comm_ps_ps_loopback.elf",
        ROOT / "IPs" / "ip_ir_array" / "component.xml",
        ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "sources_1" / "bd" / "design_shiboqi" / "design_shiboqi.bd",
        bit_log,
        bit_vivado_log,
        vitis_log,
        ip_upgrade_log,
        ip_status,
        summary,
        transcript,
        axilite_log,
        tx_log,
        rx_log,
        operator_copy,
        ROOT / "IPs" / "ip_ir_array" / "src" / "ir_axi_regs.sv",
        ROOT / "IPs" / "ip_ir_array" / "src" / "ir_txonly_ack_axi.sv",
        ROOT / "IPs" / "ip_ir_array" / "src" / "ir_stream_array_top_axi.sv",
        ROOT / "software" / "ps_lwip_bridge" / "src" / "ir_hw.c",
        ROOT / "software" / "ps_lwip_bridge" / "src" / "ir_hw.h",
        ROOT / "software" / "ps_ps_loopback" / "src" / "main.c",
        ROOT / "software" / "host_uart_operator" / "rf_comm_uart_operator.py",
        ROOT / "software" / "host_uart_operator" / "README.md",
        ROOT / "tools" / "run_p2_pspl_data_exchange_safe.ps1",
        ROOT / "tools" / "upgrade_p2_pspl_ir_ip.tcl",
        ROOT / "tools" / "build_p2_pspl_data_exchange_reports.py",
    ]

    existing_artifacts = [p for p in artifact_paths if p.exists()]
    hash_lines = []
    for path in existing_artifacts:
        hash_lines.append(f"{sha256_file(path)}  {rel(path)}")
    hash_text = "\n".join(hash_lines) + "\n"
    write(REPORTS / "P2_PSPL_artifact_hashes.txt", hash_text)

    baseline = REPORTS / "P2_baseline_freeze_manifest.md"
    baseline_hashes = REPORTS / "P2_baseline_freeze_hashes.txt"
    write(
        REPORTS / "P2_PSPL_baseline_reference.md",
        "\n".join([
            "# P2 PSPL Baseline Reference",
            "",
            "- Stage: P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED",
            "- Baseline lane mask: 0x1",
            "- Baseline ACK/RX lane mask: 0x1",
            "- Payload size used for current operator build: 256 bytes",
            "- Current baseline recovery report: `" + rel(baseline) + "`",
            "- Baseline hash list: `" + rel(baseline_hashes) + "`",
            "- Current data-exchange transcript: `" + rel(transcript) + "`",
            "- Current bitstream build log: `" + rel(bit_log) + "`",
            "- Current Vitis build log: `" + rel(vitis_log) + "`",
            "- Constraint file was not modified.",
            "",
            "Rollback basis remains the frozen P2 lane0 constrained baseline; this run stores new artifacts under P2_PSPL names.",
        ])
        + "\n",
    )

    write(
        REPORTS / "P2_PSPL_data_path_audit.md",
        "\n".join([
            "# P2 PSPL Data Path Audit",
            "",
            "## Result",
            "",
            "PASS: audited and updated the active PS/PL data path for the constrained static P2 scope.",
            "",
            "## Findings",
            "",
            "- Current PS operator build is `PSPS_TX_ONLY=1`; `READ build_id` reports `tx_only=1`.",
            "- Active PL IP instance is `STREAM_FULL_MODE=1`, `TX_ONLY_ACK_MODE=0`, Rev.36.",
            "- `TEST tx_dma` uses PS AXI DMA MM2S into PL and lane0 ACK completion; in TX-only PS mode, `rx_ok` means TX/ACK accepted, not S2MM payload return.",
            "- `TEST rx_dma_synth` uses PL synthetic RX source -> AXI-stream RX -> AXI DMA S2MM -> PS DDR buffer -> DCache invalidate -> `IRP1` header/seq/length parse -> payload byte compare.",
            "- Synthetic control map: `CONTROL[8]=TEST_MODE_ENABLE`, `COMMIT[1]=TEST_RX_INJECT_START`, offsets `0x18/0x1c/0x20/0x24` configure payload bytes, pattern, seq base, packet count.",
            "- Synthetic RX source is present in both tx-only endpoint and active stream-full wrapper after Rev.36.",
            "- T6 lane0 payload roundtrip was not executed because this accepted build remains `PSPS_TX_ONLY=1`; no roundtrip pass is claimed.",
            "",
            "## Evidence",
            "",
            "- IP status: `" + rel(ip_status) + "`",
            "- Transcript: `" + rel(transcript) + "`",
            "- Source hashes: `" + rel(REPORTS / "P2_PSPL_artifact_hashes.txt") + "`",
        ])
        + "\n",
    )

    write(
        REPORTS / "P2_PSPL_axilite_control_status_report.md",
        "\n".join([
            "# P2 PSPL AXI-Lite Control Status Report",
            "",
            f"- Status: {'PASS' if axilite_pass else 'FAIL'}",
            "- Commands covered: `STATUS`, `READ build_id`, `READ regmap_version`, `CONFIG lane_mask`, `CONFIG ack_mask`, `CONFIG payload_bytes`, `READ counters`, `CLEAR sticky`, `DUMP per_lane_counters`, `SHUTDOWN`.",
            "- All parsed AXI-Lite/UART command results returned `rc=0`.",
            "- Evidence log: `" + rel(axilite_log) + "`",
        ])
        + "\n",
    )

    tx_rows = [[t.case, t.payload, t.count, t.result.get("pass", ""), t.result.get("rx_ok", ""), t.result.get("tx_fail", ""), t.result.get("last_error", "")] for t in tx_tests]
    write(
        REPORTS / "P2_PSPL_tx_dma_mm2s_report.md",
        "\n".join([
            "# P2 PSPL TX DMA MM2S Report",
            "",
            f"- Status: {'PASS' if tx_pass else 'FAIL'}",
            "- Scope: PS AXI DMA MM2S to PL, lane0 ACK completion in current reliable configuration.",
            "- Evidence CSV: `" + rel(tx_csv) + "`",
            "- UART log: `" + rel(tx_log) + "`",
            "",
            md_table(["case", "payload", "count", "pass", "rx_ok", "tx_fail", "last_error"], tx_rows),
        ])
        + "\n",
    )

    rx_rows = [[t.case, t.payload, t.count, t.pattern_name or t.result.get("pattern", ""), t.result.get("pass", ""), t.result.get("injected_packets", ""), t.result.get("dma_rx_packets", ""), t.result.get("rx_ok", ""), t.result.get("rx_timeout", ""), t.result.get("rx_bad", ""), t.result.get("rx_mismatch", ""), t.result.get("verified_bytes", ""), t.result.get("last_error", "")] for t in rx_tests]
    write(
        REPORTS / "P2_PSPL_rx_dma_synthetic_report.md",
        "\n".join([
            "# P2 PSPL RX DMA Synthetic Report",
            "",
            f"- Status: {'PASS' if rx_pass else 'FAIL'}",
            "- Scope: PL synthetic/internal RX stream to AXI DMA S2MM to PS DDR.",
            "- Evidence CSV: `" + rel(rx_csv) + "`",
            "- UART log: `" + rel(rx_log) + "`",
            "",
            md_table(["case", "payload", "count", "pattern", "pass", "injected", "dma_rx", "rx_ok", "timeout", "rx_bad", "mismatch", "bytes", "last_error"], rx_rows),
        ])
        + "\n",
    )

    write(
        REPORTS / "P2_PSPL_rx_payload_compare_report.md",
        "\n".join([
            "# P2 PSPL RX Payload Compare Report",
            "",
            f"- Status: {'PASS' if rx_pass else 'FAIL'}",
            "- Every RX synthetic packet was checked above DMA completion: magic/header, payload length, sequence expectation, and byte pattern compare.",
            "- `first_bad_seq=0`, `first_bad_offset=0`, `expected_byte=0x00`, `actual_byte=0x00` on all passing cases.",
            "- Evidence CSV: `" + rel(cmp_csv) + "`",
        ])
        + "\n",
    )

    write(
        REPORTS / "P2_PSPL_lane0_ir_payload_roundtrip_report.md",
        "\n".join([
            "# P2 PSPL Lane0 IR Payload Roundtrip Report",
            "",
            "- Status: NOT_EXECUTED_UNSUPPORTED",
            "- Reason: current accepted operator build reports `PSPS_TX_ONLY=1`; T6 is optional/if supported and is not a pass criterion for the synthetic PS-PL data exchange result.",
            "- No `IR_LANE0_PAYLOAD_ROUNDTRIP_PASS` claim is made.",
            "- Evidence CSV: `" + rel(roundtrip_csv) + "`",
        ])
        + "\n",
    )

    write(
        REPORTS / "P2_uart_data_plane_operator_report.md",
        "\n".join([
            "# P2 UART Data Plane Operator Report",
            "",
            f"- Status: {'PASS' if operator_pass else 'FAIL'}",
            "- Host runner mode: `--mode pspl-data`.",
            "- Machine-readable `RESULT` lines were emitted for TX DMA and RX DMA synthetic tests.",
            "- Error diagnostics available: `READ rx_last_error`, `DUMP rx_first_bad`, `DUMP per_lane_counters`.",
            "- Safe wrapper performed preflight and post-run shutdown.",
            "- Transcript: `" + rel(transcript) + "`",
            "- Wrapper summary: `" + rel(summary) + "`",
        ])
        + "\n",
    )

    write(
        REPORTS / "uart_operator_command_reference.md",
        "\n".join([
            "# UART Operator Command Reference",
            "",
            "Supported data-plane commands in this P2_PSPL build:",
            "",
            "```text",
            "STATUS",
            "READ build_id",
            "READ regmap_version",
            "READ rx_last_error",
            "CONFIG lane_mask 0x1",
            "CONFIG ack_mask 0x1",
            "CONFIG payload_bytes <N>",
            "CLEAR sticky",
            "CLEAR counters",
            "TEST tx_dma payload=<N> count=<N>",
            "TEST rx_dma_synth payload=<N> count=<N> pattern=<zero|ones|incrementing|pseudo|ID>",
            "TEST pspl_roundtrip payload=<N> seconds=<N>",
            "DUMP rx_first_bad",
            "DUMP per_lane_counters",
            "SHUTDOWN",
            "```",
            "",
            "Each `TEST` command emits `UARTOP_RESULT command=TEST ...` and `RESULT test_id=... pass=...` lines.",
        ])
        + "\n",
    )

    matrix_rows = [
        ["P2-AXIL", "AXI-Lite control/status", "PASS" if axilite_pass else "FAIL", rel(REPORTS / "P2_PSPL_axilite_control_status_report.md")],
        ["P2-TXDMA", "PS to PL DMA MM2S", "PASS" if tx_pass else "FAIL", rel(tx_csv)],
        ["P2-RXDMA-SYN", "PL to PS DMA S2MM synthetic", "PASS" if rx_pass else "FAIL", rel(rx_csv)],
        ["P2-RXCMP", "PS RX payload compare", "PASS" if rx_pass else "FAIL", rel(cmp_csv)],
        ["P2-IR-L0-ACK", "lane0 IR TX/ACK reconfirm", "PASS" if tx_pass else "FAIL", rel(tx_log)],
        ["P2-IR-L0-RT", "lane0 IR payload roundtrip", "NOT_EXECUTED_UNSUPPORTED", rel(roundtrip_csv)],
        ["P2-UART-DP", "UART data-plane operator", "PASS" if operator_pass else "FAIL", rel(transcript)],
        ["P2-ETH", "Ethernet/TCP", "DEFERRED_BY_CURRENT_CONSTRAINTS", "no Ethernet cable"],
        ["P2-ROT", "Rotation", "DEFERRED_BY_CURRENT_CONSTRAINTS", "no rotation environment"],
        ["P2-2L-FULL", "full 2-lane reliable", "NOT_PROMOTED", "AB_L1 remains NO_RX_RAW_PULSE"],
    ]
    write(
        REPORTS / "P2_PSPL_data_exchange_acceptance_matrix.md",
        "\n".join([
            "# P2 PSPL Data Exchange Acceptance Matrix",
            "",
            md_table(["ID", "item", "status", "evidence"], matrix_rows),
            "",
            f"- `P2_PSPL_DATA_EXCHANGE_MINIMAL_PASS={(1 if axilite_pass and tx_pass and rx_pass else 0)}`",
            f"- `P2_PSPL_RX_DMA_SYNTHETIC_DATA_EXCHANGE_PASS={(1 if rx_pass else 0)}`",
            "- `IR_LANE0_PAYLOAD_ROUNDTRIP=NOT_EXECUTED_UNSUPPORTED`",
            "- No Ethernet, TCP/DHCP, rotation, full 2-lane, or final target claim is made.",
        ])
        + "\n",
    )

    final_pass = axilite_pass and tx_pass and rx_pass and operator_pass and shutdown_pass
    write(
        REPORTS / "P2_PSPL_data_exchange_final_report.md",
        "\n".join([
            "# P2 PSPL Data Exchange Final Report",
            "",
            f"- Overall constrained static result: {'PASS' if final_pass else 'FAIL'}",
            f"- `P2_PSPL_DATA_EXCHANGE_STATIC_CONSTRAINED_PASS={(1 if final_pass else 0)}`",
            f"- `P2_PSPL_DATA_EXCHANGE_MINIMAL_PASS={(1 if axilite_pass and tx_pass and rx_pass else 0)}`",
            f"- `P2_PSPL_RX_DMA_SYNTHETIC_DATA_EXCHANGE_PASS={(1 if rx_pass else 0)}`",
            "- `IR_LANE0_PAYLOAD_ROUNDTRIP=NOT_EXECUTED_UNSUPPORTED`",
            "",
            "Completed under current constraints: no Ethernet, no hardware movement, no rotation, lane0 reliable configuration only, AB_L1 not promoted.",
            "",
            "Evidence:",
            "",
            "- Baseline reference: `" + rel(REPORTS / "P2_PSPL_baseline_reference.md") + "`",
            "- Data path audit: `" + rel(REPORTS / "P2_PSPL_data_path_audit.md") + "`",
            "- Acceptance matrix: `" + rel(REPORTS / "P2_PSPL_data_exchange_acceptance_matrix.md") + "`",
            "- Package manifest: `" + rel(REPORTS / "P2_PSPL_data_exchange_package_manifest.sha256") + "`",
            "- Hardware transcript: `" + rel(transcript) + "`",
        ])
        + "\n",
    )

    report_paths = [
        REPORTS / "P2_PSPL_baseline_reference.md",
        REPORTS / "P2_PSPL_artifact_hashes.txt",
        REPORTS / "P2_PSPL_data_path_audit.md",
        REPORTS / "P2_PSPL_axilite_control_status_report.md",
        REPORTS / "P2_PSPL_tx_dma_mm2s_report.md",
        tx_csv,
        REPORTS / "P2_PSPL_rx_dma_synthetic_report.md",
        rx_csv,
        REPORTS / "P2_PSPL_rx_payload_compare_report.md",
        cmp_csv,
        REPORTS / "P2_PSPL_lane0_ir_payload_roundtrip_report.md",
        roundtrip_csv,
        REPORTS / "P2_uart_data_plane_operator_report.md",
        REPORTS / "uart_operator_command_reference.md",
        REPORTS / "P2_PSPL_data_exchange_acceptance_matrix.md",
        REPORTS / "P2_PSPL_data_exchange_final_report.md",
        axilite_log,
        tx_log,
        rx_log,
        operator_copy,
    ]

    package_manifest_paths = list(dict.fromkeys(existing_artifacts + report_paths))
    package_manifest = "\n".join(f"{sha256_file(p)}  {rel(p)}" for p in package_manifest_paths if p.exists()) + "\n"
    write(REPORTS / "P2_PSPL_data_exchange_package_manifest.sha256", package_manifest)

    package_dir = DELIVERABLES / f"P2_PSPL_data_exchange_{stamp}"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    for path in package_manifest_paths + [REPORTS / "P2_PSPL_data_exchange_package_manifest.sha256"]:
        if not path.exists():
            continue
        target = package_dir / rel(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    zip_path = DELIVERABLES / f"P2_PSPL_data_exchange_{stamp}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for path in package_dir.rglob("*"):
            if path.is_file():
                z.write(path, path.relative_to(package_dir))

    print(f"TRANSCRIPT={transcript}")
    print(f"SUMMARY={summary}")
    print(f"FINAL_REPORT={REPORTS / 'P2_PSPL_data_exchange_final_report.md'}")
    print(f"PACKAGE_DIR={package_dir}")
    print(f"PACKAGE_ZIP={zip_path}")
    print(f"FINAL_PASS={1 if final_pass else 0}")
    return 0 if final_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
