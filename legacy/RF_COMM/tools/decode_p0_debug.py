#!/usr/bin/env python3
"""Decode P0 RF_COMM UART/debug status lines into failure classes."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
from dataclasses import dataclass
from typing import Iterable


KEYVAL_RE = re.compile(r"([A-Za-z0-9_]+)=([^ \t\r\n]+)")

STICKY_BITS = (
    (0, "tx_done"),
    (1, "rx_done"),
    (2, "tx_overflow"),
    (3, "tx_retry_exhausted"),
    (4, "rx_header_error"),
    (5, "rx_protocol_error"),
    (6, "rx_frame_overflow"),
    (7, "rx_crc_error"),
    (8, "rx_overrun"),
)

RX_STATE = {
    0: "IDLE",
    1: "PREAMBLE",
    2: "DATA_ALIGN",
    3: "DATA",
    4: "CHECK",
    5: "FLUSH",
}


@dataclass
class Record:
    source: str
    line_no: int
    tag: str
    fields: dict[str, str]


def parse_int(text: str | None, default: int = 0) -> int:
    if text is None:
        return default
    cleaned = text.strip().rstrip("%,;")
    try:
        return int(cleaned, 0)
    except ValueError:
        return default


def lane_counts(value: int) -> list[int]:
    return [(value >> (8 * lane)) & 0xFF for lane in range(4)]


def sticky_names(value: int) -> str:
    names = [name for bit, name in STICKY_BITS if value & (1 << bit)]
    return ",".join(names) if names else "none"


def decode_phy_debug(value: int) -> str:
    top_nibble = (value >> 28) & 0xF
    top_byte = (value >> 24) & 0xFF
    if value == 0:
        return "zero/no_debug"

    if top_nibble == 0xD:
        subtype = (value >> 24) & 0xF
        if subtype == 0x1:
            return (
                "rx_reassembly_timeout "
                f"ctx_valid={(value >> 23) & 1} ctx_complete={(value >> 22) & 1} "
                f"bitmap=0x{(value >> 16) & 0xF:X} frag_count={(value >> 12) & 0xF} "
                f"total_low8={(value >> 4) & 0xFF} seq_low4={value & 0xF}"
            )
        if subtype == 0x2:
            return (
                "rx_data_parse_fail "
                f"is_ack={(value >> 23) & 1} ack_ok={(value >> 22) & 1} "
                f"data_ok={(value >> 21) & 1} hdr_bad={(value >> 20) & 1} "
                f"frag_idx={(value >> 16) & 0xF} frag_count={(value >> 12) & 0xF} "
                f"total_low8={(value >> 4) & 0xFF} payload_low4={value & 0xF}"
            )
        if subtype == 0x3:
            return (
                "rx_context_mismatch "
                f"seq={(value >> 20) & 0xF}/ctx={(value >> 16) & 0xF} "
                f"frag_count={(value >> 12) & 0xF}/ctx={(value >> 8) & 0xF} "
                f"total_low4={(value >> 4) & 0xF}/ctx={value & 0xF}"
            )
        if subtype == 0x4:
            return (
                "rx_session_mismatch "
                f"seen_low12=0x{(value >> 12) & 0xFFF:03X} "
                f"expected_low12=0x{value & 0xFFF:03X}"
            )
        if subtype == 0x5:
            return (
                "rx_protocol_crc_fail "
                f"session_low8=0x{(value >> 16) & 0xFF:02X} "
                f"seq_low8=0x{(value >> 8) & 0xFF:02X} frame_len={value & 0xFF}"
            )
        if subtype == 0x6:
            return (
                "rx_data_shape_fail "
                f"frag_idx={(value >> 20) & 0xF} frag_count={(value >> 16) & 0xF} "
                f"total_low8={(value >> 8) & 0xFF} payload_len={value & 0xFF}"
            )
        if subtype == 0x7:
            return (
                "app_payload_mismatch "
                f"raw_idx={(value >> 16) & 0xFF} "
                f"expected=0x{(value >> 8) & 0xFF:02X} got=0x{value & 0xFF:02X}"
            )
        if subtype == 0x8:
            return (
                "app_length_mismatch "
                f"last_raw_idx={(value >> 16) & 0xFF} "
                f"expected_last_idx=0x{(value >> 8) & 0xFF:02X}"
            )
        if subtype == 0x9:
            return (
                "rx_data_accept_ack_queued "
                f"lane={(value >> 20) & 0xF} frag_idx={(value >> 16) & 0xF} "
                f"frag_count={(value >> 12) & 0xF} payload_len={(value >> 8) & 0xF} "
                f"seq_low8=0x{value & 0xFF:02X}"
            )
        return f"rx_debug_D{subtype:X} raw=0x{value:08X}"

    if top_byte == 0xEC:
        return (
            "b_endpoint_summary "
            f"ack_lane1={(value >> 16) & 0xFF} "
            f"ack_lane0={(value >> 8) & 0xFF} "
            f"b_rx_good={value & 0xFF}"
        )

    if top_nibble in (0xA, 0xC):
        return f"stream_debug raw=0x{value:08X}"

    rx_active = (value >> 31) & 1
    pulse_active = (value >> 30) & 1
    chip_seen = (value >> 29) & 1
    sym_valid = (value >> 28) & 1
    state = (value >> 25) & 0x7
    ticks = (value >> 22) & 0x7
    chip_idx = (value >> 20) & 0x3
    sym_capture = (value >> 16) & 0xF
    preamble = (value >> 8) & 0xFF
    byte_cnt = (value >> 4) & 0xF
    invalid = value & 0xF
    return (
        "rx_phy "
        f"active={rx_active} pulse={pulse_active} chip={chip_seen} sym={sym_valid} "
        f"state={RX_STATE.get(state, str(state))} ticks={ticks} chip_idx={chip_idx} "
        f"sym=0x{sym_capture:X} preamble={preamble} byte_cnt_low4={byte_cnt} invalid={invalid}"
    )


def classify(fields: dict[str, str]) -> str:
    sent = parse_int(fields.get("sent"))
    rx_ok = parse_int(fields.get("rx_ok"))
    tx_fail = parse_int(fields.get("tx_fail"))
    sticky = parse_int(fields.get("sticky"))
    rx_good = parse_int(fields.get("rx_good"))
    rx_crc = parse_int(fields.get("rx_crc"))
    rx_err = parse_int(fields.get("rx_err"))
    phy0 = parse_int(fields.get("phy0"))
    pre_phy0 = parse_int(fields.get("pre_phy0"))
    last_error = fields.get("last_error", "")

    phy_text = decode_phy_debug(phy0)
    pre_phy_text = decode_phy_debug(pre_phy0)

    if sent and rx_ok == sent and tx_fail == 0:
        return "PASS: end-to-end payload verified"
    if "rx_session_mismatch" in phy_text or "rx_session_mismatch" in pre_phy_text:
        return "PROTOCOL: session mismatch after frame decode"
    if "rx_protocol_crc_fail" in phy_text or "rx_protocol_crc_fail" in pre_phy_text:
        return "PROTOCOL: IR protocol header CRC failed"
    if "rx_data_shape_fail" in phy_text or "rx_data_shape_fail" in pre_phy_text:
        return "PROTOCOL: IR data header/length shape failed"
    if "app_payload_mismatch" in phy_text or "app_payload_mismatch" in pre_phy_text:
        return "APP: payload/lane-mask checker mismatch"
    if "app_length_mismatch" in phy_text or "app_length_mismatch" in pre_phy_text:
        return "APP: payload length checker mismatch"
    if "rx_data_accept_ack_queued" in phy_text or "rx_data_accept_ack_queued" in pre_phy_text:
        if tx_fail:
            return "ACK/PATH: data accepted and ACK queued, transmitter still failed"
        return "PASS-EVIDENCE: data accepted and ACK queued"
    if rx_crc != 0 or (sticky & (1 << 7)):
        return "PHY/FRAME: lane CRC errors present"
    if rx_err != 0 or (sticky & ((1 << 4) | (1 << 5) | (1 << 6) | (1 << 8))):
        return "RX: header/protocol/overflow/overrun error present"
    if rx_good != 0 and rx_ok == 0:
        return "APP/ACK: lane frames arrived but PS payload was not accepted"
    if ((phy0 >> 24) & 0xFF) == 0xEC and (phy0 & 0xFF) != 0 and tx_fail:
        return "ACK/PATH: B accepted payload, A still failed waiting for ACK"
    if phy0 != 0 or pre_phy0 != 0:
        return "INCONCLUSIVE: signal/debug activity exists but no verified payload"
    if "retry" in last_error:
        return "LOW_LEVEL_OR_ACK: retry exhausted with no decoded evidence"
    return "INCONCLUSIVE"


def iter_records(paths: Iterable[str]) -> Iterable[Record]:
    for path in paths:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as handle:
                for line_no, line in enumerate(handle, 1):
                    if not any(tag in line for tag in ("PSPS_STATS", "PSPS_STAGE_SUMMARY", "PSPS_TDM_STATS", "PSPS_TDM_STAGE_SUMMARY")):
                        continue
                    fields = {key: value for key, value in KEYVAL_RE.findall(line)}
                    if not fields:
                        continue
                    tag = "PSPS"
                    for candidate in ("PSPS_STAGE_SUMMARY", "PSPS_STATS", "PSPS_TDM_STAGE_SUMMARY", "PSPS_TDM_STATS"):
                        if candidate in line:
                            tag = candidate
                            break
                    yield Record(path, line_no, tag, fields)
        except OSError:
            continue


def collect_paths(args: argparse.Namespace) -> list[str]:
    if args.inputs:
        paths: list[str] = []
        for item in args.inputs:
            expanded = glob.glob(item)
            paths.extend(expanded if expanded else [item])
        return sorted(set(paths))
    return sorted(glob.glob(os.path.join("reports", "*.summary.txt")) + glob.glob(os.path.join("reports", "uart_*.log")))


def write_markdown(records: list[Record], output: str) -> None:
    now = dt.datetime.now().isoformat(timespec="seconds")
    lines = [
        "# P0 Debug Decode",
        "",
        f"Generated: {now}",
        "",
        "| Source | Line | Tag | Stage | Sent | Rx OK | Tx Fail | Sticky | Lane Good | Lane CRC | Lane Err | phy0 decode | pre_phy0 decode | Classification |",
        "|---|---:|---|---|---:|---:|---:|---|---|---|---|---|---|---|",
    ]
    for record in records:
        f = record.fields
        phy0 = parse_int(f.get("phy0"))
        pre_phy0 = parse_int(f.get("pre_phy0"))
        sticky = parse_int(f.get("sticky"))
        row = [
            os.path.basename(record.source),
            str(record.line_no),
            record.tag,
            f.get("stage", ""),
            str(parse_int(f.get("sent"))),
            str(parse_int(f.get("rx_ok"))),
            str(parse_int(f.get("tx_fail"))),
            sticky_names(sticky),
            "/".join(str(v) for v in lane_counts(parse_int(f.get("rx_good")))),
            "/".join(str(v) for v in lane_counts(parse_int(f.get("rx_crc")))),
            "/".join(str(v) for v in lane_counts(parse_int(f.get("rx_err")))),
            decode_phy_debug(phy0),
            decode_phy_debug(pre_phy0),
            classify(f),
        ]
        escaped = [cell.replace("|", "\\|").replace("\n", " ") for cell in row]
        lines.append("| " + " | ".join(escaped) + " |")

    with open(output, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", help="Summary/UART log paths or globs.")
    parser.add_argument("-o", "--output", default="p0_debug_decode_20260625.md")
    parser.add_argument("--last", type=int, default=120, help="Keep only the last N decoded records.")
    args = parser.parse_args()

    paths = collect_paths(args)
    records = list(iter_records(paths))
    if args.last > 0:
        records = records[-args.last:]
    write_markdown(records, args.output)
    print(f"decoded_records={len(records)} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
