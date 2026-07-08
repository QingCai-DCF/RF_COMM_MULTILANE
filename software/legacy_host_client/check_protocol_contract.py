#!/usr/bin/env python3
"""Offline RFCM protocol contract check between the PS bridge and PC client."""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rf_comm_client as rf


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
PS_SRC = ROOT / "software" / "ps_lwip_bridge" / "src"


@dataclass
class CheckRow:
    item: str
    status: str
    evidence: str
    note: str


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def macro_value(text: str, name: str) -> str:
    match = re.search(rf"^\s*#define\s+{re.escape(name)}\s+(.+?)\s*$", text, re.MULTILINE)
    if match is None:
        raise ValueError(f"missing macro {name}")
    return re.sub(r"/\*.*?\*/", "", match.group(1)).strip()


def macro_int(text: str, name: str) -> int:
    value = macro_value(text, name)
    value = re.sub(r"([0-9])(?:[uUlL]+)", r"\1", value)
    if re.fullmatch(r"'(.)'", value):
        return ord(value[1])
    if not re.fullmatch(r"[0-9xXa-fA-F\s<>()|+.-]+", value):
        raise ValueError(f"unsupported macro value {name}={value}")
    return int(eval(value, {"__builtins__": {}}, {}))


def add(rows: list[CheckRow], item: str, ok: bool, evidence: str, note: str) -> None:
    rows.append(CheckRow(item, "PASS" if ok else "FAIL", evidence, note))


def status_layout_from_bridge(bridge_c: str) -> list[tuple[int, str]]:
    found = re.findall(r"rf_put_u32_le\(&payload\[(\d+)\],\s*status\.(\w+)\);", bridge_c)
    return [(int(offset), name) for offset, name in found]


def md_table(rows: list[CheckRow]) -> str:
    lines = [
        "| item | status | evidence | note |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                cell.replace("\n", " ").replace("|", "/")
                for cell in (row.item, row.status, row.evidence, row.note)
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows: list[CheckRow] = []

    rf_h = read(PS_SRC / "rf_protocol.h")
    bridge_c = read(PS_SRC / "tcp_bridge.c")

    frame_macros = {
        "HELLO": rf.FRAME_HELLO,
        "STATUS_REQ": rf.FRAME_STATUS_REQ,
        "STATUS_RSP": rf.FRAME_STATUS_RSP,
        "ACK": rf.FRAME_ACK,
        "ERROR": rf.FRAME_ERROR,
        "TX_DATA": rf.FRAME_TX_DATA,
        "RX_DATA": rf.FRAME_RX_DATA,
        "CLEAR": rf.FRAME_CLEAR,
        "CONFIG": rf.FRAME_CONFIG,
        "COMMAND": rf.FRAME_COMMAND,
    }
    config_macros = {
        "ENABLE": rf.CONFIG_ENABLE,
        "SESSION": rf.CONFIG_SESSION,
        "LANE_MASK": rf.CONFIG_LANE_MASK,
        "RX_LANE_MASK": rf.CONFIG_RX_LANE_MASK,
        "MODE": rf.CONFIG_MODE,
    }
    mode_macros = {
        "NETWORK_MEMORY_ECHO": rf.MODE_NETWORK_MEMORY_ECHO,
        "PSPL_SYNTH_LOOPBACK": rf.MODE_PSPL_SYNTH_LOOPBACK,
        "IR_PHYSICAL": rf.MODE_IR_PHYSICAL,
    }

    magic = bytes(macro_int(rf_h, f"RF_PROTO_MAGIC{i}") for i in range(4))
    add(rows, "magic", magic == rf.MAGIC, magic.decode("ascii", errors="replace"), "PS and PC protocol magic must match.")
    add(rows, "version", macro_int(rf_h, "RF_PROTO_VERSION") == rf.VERSION, str(rf.VERSION), "PS and PC protocol version must match.")
    add(rows, "header_bytes", macro_int(rf_h, "RF_PROTO_HEADER_BYTES") == rf.HEADER.size, str(rf.HEADER.size), "Wire header must remain 12 bytes.")
    add(rows, "max_payload", macro_int(rf_h, "RF_PROTO_MAX_PAYLOAD") == rf.MAX_FRAME_PAYLOAD, str(rf.MAX_FRAME_PAYLOAD), "PS and PC frame payload limits must match.")

    for name, value in frame_macros.items():
        ps_value = macro_int(rf_h, f"RF_FRAME_{name}")
        add(rows, f"frame_{name.lower()}", ps_value == value, f"ps=0x{ps_value:02x} pc=0x{value:02x}", "Frame type value must match.")

    for name, value in config_macros.items():
        ps_value = macro_int(rf_h, f"RF_CONFIG_{name}")
        add(rows, f"config_{name.lower()}", ps_value == value, f"ps=0x{ps_value:02x} pc=0x{value:02x}", "Config bit value must match.")

    for name, value in mode_macros.items():
        ps_value = macro_int(rf_h, f"RF_MODE_{name}")
        add(rows, f"mode_{name.lower()}", ps_value == value, f"ps={ps_value} pc={value}", "N03 bridge mode value must match.")

    layout = status_layout_from_bridge(bridge_c)
    expected_layout = [(index * 4, name) for index, name in enumerate(rf.STATUS_FIELDS_FULL)]
    add(
        rows,
        "status_payload_layout",
        layout == expected_layout,
        ";".join(f"{offset}:{name}" for offset, name in layout),
        "PS status payload field offsets must match the PC parser labels.",
    )
    add(
        rows,
        "status_payload_size",
        "uint8_t payload[64]" in bridge_c and "bridge_send_frame(RF_FRAME_STATUS_RSP, seq, payload, sizeof(payload))" in bridge_c,
        "64 bytes",
        "PS bridge must send the full 16-word status payload.",
    )

    sample_status = bytes()
    for value in range(1, len(rf.STATUS_FIELDS_FULL) + 1):
        sample_status += value.to_bytes(4, "little")
    decoded_status = rf.parse_status_payload(sample_status)
    add(
        rows,
        "pc_status_parser_full",
        list(decoded_status.keys()) == list(rf.STATUS_FIELDS_FULL) and decoded_status["rx_lane_err_count"] == 16,
        ",".join(decoded_status.keys()),
        "PC parser must decode the full 64-byte status payload.",
    )

    half_duplex_payload = rf.make_config_payload(enable=1, session=0x1234, lane_mask=0x000000FF)
    full_duplex_payload = rf.make_config_payload(enable=1, session=0x1234, tx_lane_mask=0x0000000F, rx_lane_mask=0x000000F0)
    n03_mode_payload = rf.make_config_payload(mode="network_memory_echo")
    half_ok = len(half_duplex_payload) == 8 and half_duplex_payload[0] == (
        rf.CONFIG_ENABLE | rf.CONFIG_SESSION | rf.CONFIG_LANE_MASK
    )
    full_ok = len(full_duplex_payload) == 12 and full_duplex_payload[0] == (
        rf.CONFIG_ENABLE | rf.CONFIG_SESSION | rf.CONFIG_LANE_MASK | rf.CONFIG_RX_LANE_MASK
    )
    add(rows, "final_half_duplex_8lane_mask", half_ok, "lane_mask=0x000000ff len=8", "Final raw 32 Mbit/s half-duplex profile uses all 8 lanes.")
    add(rows, "final_full_duplex_4plus4_masks", full_ok, "tx=0x0000000f rx=0x000000f0 len=12", "Final raw 16 Mbit/s per-direction profile uses independent TX/RX masks.")
    add(rows, "n03_mode_payload", len(n03_mode_payload) == 16 and n03_mode_payload[0] == rf.CONFIG_MODE, "mode=network_memory_echo len=16", "N03 mode config uses the 16-byte CONFIG extension.")

    add(rows, "no_hardware_programming", True, "NO_HARDWARE_PROGRAMMING=1", "This check reads source files only.")
    add(rows, "no_uart_write", True, "NO_UART_WRITE=1", "No serial device is opened.")
    add(rows, "no_tfdu_drive", True, "NO_TFDU_DRIVE=1", "No FPGA, TX_DATA hardware path, or TFDU board is touched.")

    overall = "PASS" if all(row.status == "PASS" for row in rows) else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "protocol_contract_current.md"
    json_path = REPORTS / "protocol_contract_current.json"
    csv_path = REPORTS / "protocol_contract_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    payload: dict[str, Any] = {
        "generated": generated,
        "overall": overall,
        "checks": [asdict(row) for row in rows],
        "status_fields": list(rf.STATUS_FIELDS_FULL),
        "frame_types": frame_macros,
        "config_bits": config_macros,
        "modes": mode_macros,
        "final_masks": {
            "half_duplex_8lane": "0x000000ff",
            "full_duplex_tx": "0x0000000f",
            "full_duplex_rx": "0x000000f0",
        },
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = [
        "# RFCM Protocol Contract",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This offline check compares the PS lwIP bridge protocol source with the PC client implementation. It is not real TCP/DHCP hardware acceptance.",
        "",
        "## Checks",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_PROTOCOL_CONTRACT overall={overall} checks={len(rows)} status_fields={len(rf.STATUS_FIELDS_FULL)} frame_types={len(frame_macros)} config_bits={len(config_macros)} modes={len(mode_macros)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_PROTOCOL_CONTRACT overall={overall} checks={len(rows)} status_fields={len(rf.STATUS_FIELDS_FULL)} frame_types={len(frame_macros)} config_bits={len(config_macros)} modes={len(mode_macros)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
