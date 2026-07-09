#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config" / "register_map" / "generated"))
import ir_regs as regs  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
BLOCKED = "BLOCKED_BY_RUNTIME_ENVIRONMENT"

P6_CTRL_CLEAR_STICKY = 1 << 1
P6_CTRL_COMMIT = 1 << 2
P6_CTRL_START = 1 << 3
P6_CTRL_STOP = 1 << 4
P6_CTRL_SHUTDOWN = 1 << 5

P6_STATUS_READY = 1 << 1
P6_STATUS_COMMITTED = 1 << 2
P6_STATUS_BUSY = 1 << 3
P6_STATUS_DONE = 1 << 4
P6_STATUS_FAIL = 1 << 5
P6_STATUS_CONFIG_REJECTED = 1 << 6
P6_STATUS_TIMEOUT = 1 << 7

P6_ERROR_SESSION = 1
P6_ERROR_LANE_MASK = 2
P6_ERROR_ACK_MASK = 3
P6_ERROR_PAYLOAD_LEN = 4
P6_ERROR_TIMEOUT = 5
P6_ERROR_NOT_COMMITTED = 6

MAX_PAYLOAD_BYTES = 247


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def payload_word(payload: bytes, word_index: int) -> int:
    value = 0
    for lane in range(4):
        idx = word_index * 4 + lane
        if idx < len(payload):
            value |= payload[idx] << (8 * lane)
    return value


def unpack_word(word: int, length: int, word_index: int, out: bytearray) -> None:
    for lane in range(4):
        idx = word_index * 4 + lane
        if idx < length:
            out[idx] = (word >> (8 * lane)) & 0xFF


@dataclass
class MemoryBackend:
    regs: dict[int, int] = field(default_factory=dict)
    payload_words: list[int] = field(default_factory=lambda: [0] * 64)
    rx_words: list[int] = field(default_factory=lambda: [0] * 64)
    payload_index: int = 0
    rx_index: int = 0
    committed: bool = False

    def __post_init__(self) -> None:
        self.regs[regs.IR_REG_P6_STATUS] = P6_STATUS_READY
        self.regs[regs.IR_REG_P6_SESSION] = 0x2201
        self.regs[regs.IR_REG_P6_LANE_MASK] = 0x1
        self.regs[regs.IR_REG_P6_ACK_LANE_MASK] = 0x1
        self.regs[regs.IR_REG_P6_TIMEOUT_CYCLES] = 64000
        self.regs[regs.IR_REG_P6_CAPS] = 0x060300F7

    def read32(self, offset: int) -> int:
        if offset == regs.IR_REG_P6_PAYLOAD_WORD_DATA:
            return self.payload_words[self.payload_index & 63]
        if offset == regs.IR_REG_P6_RX_WORD_DATA:
            return self.rx_words[self.rx_index & 63]
        return self.regs.get(offset, 0)

    def write32(self, offset: int, value: int) -> None:
        value &= 0xFFFFFFFF
        if offset == regs.IR_REG_P6_PAYLOAD_WORD_INDEX:
            self.payload_index = value & 63
            self.regs[offset] = self.payload_index
            return
        if offset == regs.IR_REG_P6_RX_WORD_INDEX:
            self.rx_index = value & 63
            self.regs[offset] = self.rx_index
            return
        if offset == regs.IR_REG_P6_PAYLOAD_WORD_DATA:
            self.payload_words[self.payload_index & 63] = value
            self.regs[offset] = value
            return
        self.regs[offset] = value
        if offset == regs.IR_REG_P6_CTRL:
            self._control(value)

    def _reject(self, error_code: int) -> None:
        self.regs[regs.IR_REG_P6_ERROR_CODE] = error_code
        self.regs[regs.IR_REG_P6_STICKY_ERROR] = self.regs.get(regs.IR_REG_P6_STICKY_ERROR, 0) | 1
        self.regs[regs.IR_REG_P6_STATUS] = (
            P6_STATUS_READY | P6_STATUS_DONE | P6_STATUS_FAIL | P6_STATUS_CONFIG_REJECTED
        )
        self.regs[regs.IR_REG_P6_MAILBOX_STATUS] = 0x50364C46

    def _validate(self, require_commit: bool) -> int:
        session = self.regs.get(regs.IR_REG_P6_SESSION, 0)
        lane_mask = self.regs.get(regs.IR_REG_P6_LANE_MASK, 0)
        ack_mask = self.regs.get(regs.IR_REG_P6_ACK_LANE_MASK, 0)
        payload_len = self.regs.get(regs.IR_REG_P6_PAYLOAD_LEN, 0) & 0xFFFF
        timeout = self.regs.get(regs.IR_REG_P6_TIMEOUT_CYCLES, 0)
        if require_commit and not self.committed:
            return P6_ERROR_NOT_COMMITTED
        if session != 0x2201:
            return P6_ERROR_SESSION
        if lane_mask not in (1, 2, 3):
            return P6_ERROR_LANE_MASK
        if ack_mask != lane_mask:
            return P6_ERROR_ACK_MASK
        if payload_len == 0 or payload_len > MAX_PAYLOAD_BYTES:
            return P6_ERROR_PAYLOAD_LEN
        if timeout == 0:
            return P6_ERROR_TIMEOUT
        return 0

    def _control(self, value: int) -> None:
        if value & P6_CTRL_CLEAR_STICKY:
            self.regs[regs.IR_REG_P6_ERROR_CODE] = 0
            self.regs[regs.IR_REG_P6_STICKY_ERROR] = 0
            self.regs[regs.IR_REG_P6_STATUS] = P6_STATUS_READY | (P6_STATUS_COMMITTED if self.committed else 0)
        if value & P6_CTRL_COMMIT:
            error = self._validate(require_commit=False)
            if error:
                self.committed = False
                self._reject(error)
                return
            length = self.regs[regs.IR_REG_P6_PAYLOAD_LEN] & 0xFFFF
            data = self.payload_bytes(length)
            self.regs[regs.IR_REG_P6_PAYLOAD_CRC32] = zlib.crc32(data) & 0xFFFFFFFF
            self.committed = True
            self.regs[regs.IR_REG_P6_STATUS] = P6_STATUS_READY | P6_STATUS_COMMITTED
            self.regs[regs.IR_REG_P6_MAILBOX_STATUS] = 0x5036434D
        if value & P6_CTRL_START:
            error = self._validate(require_commit=True)
            if error:
                self._reject(error)
                return
            length = self.regs[regs.IR_REG_P6_PAYLOAD_LEN] & 0xFFFF
            data = self.payload_bytes(length)
            digest = zlib.crc32(data) & 0xFFFFFFFF
            for idx in range(64):
                self.rx_words[idx] = self.payload_words[idx]
            self.regs[regs.IR_REG_P6_RX_PAYLOAD_LEN] = length
            self.regs[regs.IR_REG_P6_RX_PAYLOAD_CRC32] = digest
            self.regs[regs.IR_REG_P6_RX_DIGEST] = digest
            self.regs[regs.IR_REG_P6_TX_COUNT] = self.regs.get(regs.IR_REG_P6_TX_COUNT, 0) + 1
            lane_mask = self.regs[regs.IR_REG_P6_LANE_MASK]
            if lane_mask & 1:
                self.regs[regs.IR_REG_P6_RX_GOOD_COUNT_L0] = self.regs.get(regs.IR_REG_P6_RX_GOOD_COUNT_L0, 0) + 1
            if lane_mask & 2:
                self.regs[regs.IR_REG_P6_RX_GOOD_COUNT_L1] = self.regs.get(regs.IR_REG_P6_RX_GOOD_COUNT_L1, 0) + 1
            self.regs[regs.IR_REG_P6_STATUS] = P6_STATUS_READY | P6_STATUS_COMMITTED | P6_STATUS_DONE
            self.regs[regs.IR_REG_P6_MAILBOX_STATUS] = 0x50364F4B
        if value & P6_CTRL_STOP:
            self.regs[regs.IR_REG_P6_STATUS] = self.regs.get(regs.IR_REG_P6_STATUS, P6_STATUS_READY) & ~P6_STATUS_BUSY
        if value & P6_CTRL_SHUTDOWN:
            self.regs[regs.IR_REG_P6_SHUTDOWN_REASON] = 0x54464455

    def payload_bytes(self, length: int) -> bytes:
        out = bytearray(length)
        for word_index in range((length + 3) // 4):
            unpack_word(self.payload_words[word_index], length, word_index, out)
        return bytes(out)

    def rx_bytes(self, length: int) -> bytes:
        out = bytearray(length)
        for word_index in range((length + 3) // 4):
            unpack_word(self.rx_words[word_index], length, word_index, out)
        return bytes(out)


def run_memory_transfer(payload: bytes, lane_mask: int, ack_mask: int, session: int) -> tuple[dict[str, Any], bytes]:
    backend = MemoryBackend()
    backend.write32(regs.IR_REG_P6_CTRL, P6_CTRL_CLEAR_STICKY)
    backend.write32(regs.IR_REG_P6_SESSION, session)
    backend.write32(regs.IR_REG_P6_LANE_MASK, lane_mask)
    backend.write32(regs.IR_REG_P6_ACK_LANE_MASK, ack_mask)
    backend.write32(regs.IR_REG_P6_PAYLOAD_LEN, len(payload))
    backend.write32(regs.IR_REG_P6_PAYLOAD_PATTERN_ID, 0)
    backend.write32(regs.IR_REG_P6_PAYLOAD_SEED, 0x2201)
    backend.write32(regs.IR_REG_P6_TIMEOUT_CYCLES, 64000)
    for word_index in range((len(payload) + 3) // 4):
        backend.write32(regs.IR_REG_P6_PAYLOAD_WORD_INDEX, word_index)
        backend.write32(regs.IR_REG_P6_PAYLOAD_WORD_DATA, payload_word(payload, word_index))
        if backend.read32(regs.IR_REG_P6_PAYLOAD_WORD_DATA) != payload_word(payload, word_index):
            raise RuntimeError(f"payload readback mismatch at word {word_index}")
    backend.write32(regs.IR_REG_P6_CTRL, P6_CTRL_COMMIT)
    backend.write32(regs.IR_REG_P6_CTRL, P6_CTRL_START)
    rx_len = backend.read32(regs.IR_REG_P6_RX_PAYLOAD_LEN) & 0xFFFF
    rx_payload = backend.rx_bytes(rx_len)
    summary = {
        "status": backend.read32(regs.IR_REG_P6_STATUS),
        "mailbox_status": backend.read32(regs.IR_REG_P6_MAILBOX_STATUS),
        "payload_len": len(payload),
        "payload_crc32": f"0x{backend.read32(regs.IR_REG_P6_PAYLOAD_CRC32):08x}",
        "rx_payload_len": rx_len,
        "rx_payload_crc32": f"0x{backend.read32(regs.IR_REG_P6_RX_PAYLOAD_CRC32):08x}",
        "rx_digest": f"0x{backend.read32(regs.IR_REG_P6_RX_DIGEST):08x}",
        "tx_count": backend.read32(regs.IR_REG_P6_TX_COUNT),
        "rx_good_count_l0": backend.read32(regs.IR_REG_P6_RX_GOOD_COUNT_L0),
        "rx_good_count_l1": backend.read32(regs.IR_REG_P6_RX_GOOD_COUNT_L1),
        "crc_bad": backend.read32(regs.IR_REG_P6_CRC_BAD),
        "payload_mismatch": backend.read32(regs.IR_REG_P6_PAYLOAD_MISMATCH),
        "retry_exhausted": backend.read32(regs.IR_REG_P6_RETRY_EXHAUSTED),
        "tx_fail": backend.read32(regs.IR_REG_P6_TX_FAIL),
        "error_code": backend.read32(regs.IR_REG_P6_ERROR_CODE),
        "sticky_error": backend.read32(regs.IR_REG_P6_STICKY_ERROR),
    }
    backend.write32(regs.IR_REG_P6_CTRL, P6_CTRL_STOP | P6_CTRL_SHUTDOWN)
    summary["shutdown_reason"] = f"0x{backend.read32(regs.IR_REG_P6_SHUTDOWN_REASON):08x}"
    return summary, rx_payload


def write_xsdb_template(path: Path, base_addr: int, input_file: Path, output_file: Path) -> None:
    lines = [
        "# P6 JTAG/AXI local transport template.",
        "# This template intentionally does not open Ethernet, DHCP, or TCP board transport.",
        "# It requires a live PS/JTAG-to-AXI path and a P6 bitstream exposing the register window.",
        f"set base 0x{base_addr:08x}",
        f"set input_file {{{input_file.as_posix()}}}",
        f"set output_file {{{output_file.as_posix()}}}",
        'puts "P6_JTAG_AXI_TEMPLATE_READY=1"',
        'puts "P6_JTAG_AXI_REQUIRES_LIVE_AXI_MASTER=1"',
    ]
    write_text(path, "\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P6 local no-Ethernet host transport wrapper.")
    parser.add_argument("--backend", choices=["memory", "jtag-axi"], default="memory")
    parser.add_argument("--input-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--lane-mask", default="0x3")
    parser.add_argument("--ack-lane-mask", default="0x3")
    parser.add_argument("--session", default="0x2201")
    parser.add_argument("--base-address", default="0x43c00000")
    parser.add_argument("--allow-live-jtag", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)

    input_file = Path(args.input_file)
    output_file = Path(args.output_file)
    lane_mask = int(args.lane_mask, 0)
    ack_mask = int(args.ack_lane_mask, 0)
    session = int(args.session, 0)
    base_address = int(args.base_address, 0)
    payload = input_file.read_bytes()
    evidence_dir = ROOT / "evidence" / "hardware" / "p6" / "host_file_transport_jtag"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    if args.backend == "jtag-axi" and not args.allow_live_jtag:
      template = evidence_dir / "p6_jtag_axi_transport_template.tcl"
      write_xsdb_template(template, base_address, input_file, output_file)
      summary = {
          "P6_HOST_FILE_TRANSPORT_JTAG": BLOCKED,
          "generated_at_utc": now_iso(),
          "reason": "live JTAG/AXI execution requires an integrated PS7/JTAG-to-AXI register path and explicit --allow-live-jtag",
          "template": rel(template),
          "input_file": rel(input_file),
          "output_file": rel(output_file),
          "script_hardware_actions_executed": False,
          "source_evidence_contains_hardware_actions": False,
          "ethernet_used": False,
      }
      write_json(evidence_dir / "p6_jtag_axi_transport_summary.json", summary)
      if args.json_summary:
          print(json.dumps(summary, ensure_ascii=False))
      return 2

    if args.backend == "jtag-axi":
        xsdb = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat")
        if not xsdb.exists():
            summary = {
                "P6_HOST_FILE_TRANSPORT_JTAG": BLOCKED,
                "generated_at_utc": now_iso(),
                "reason": "xsdb.bat missing; cannot run live JTAG/AXI transport",
                "script_hardware_actions_executed": False,
                "ethernet_used": False,
            }
            write_json(evidence_dir / "p6_jtag_axi_transport_summary.json", summary)
            if args.json_summary:
                print(json.dumps(summary, ensure_ascii=False))
            return 2
        summary = {
            "P6_HOST_FILE_TRANSPORT_JTAG": BLOCKED,
            "generated_at_utc": now_iso(),
            "reason": "live JTAG/AXI implementation is scaffolded but no verified PS7/JTAG-to-AXI base path exists in this rebuilt top",
            "xsdb": str(xsdb),
            "script_hardware_actions_executed": False,
            "ethernet_used": False,
        }
        write_json(evidence_dir / "p6_jtag_axi_transport_summary.json", summary)
        if args.json_summary:
            print(json.dumps(summary, ensure_ascii=False))
        return 2

    try:
        transfer, rx_payload = run_memory_transfer(payload, lane_mask, ack_mask, session)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(rx_payload)
        match = payload == rx_payload
        result = PASS if match and transfer["crc_bad"] == 0 and transfer["payload_mismatch"] == 0 else FAIL
        summary = {
            "P6_HOST_FILE_TRANSPORT_LOCAL_BACKEND": result,
            "P6_HOST_FILE_TRANSPORT_JTAG": BLOCKED,
            "generated_at_utc": now_iso(),
            "reason": "memory backend validates P6 register-window/file flow; live JTAG/AXI remains blocked until hardware AXI path is integrated",
            "input_file": rel(input_file),
            "output_file": rel(output_file),
            "input_sha256": sha256_hex(payload),
            "output_sha256": sha256_hex(rx_payload),
            "input_crc32": f"0x{zlib.crc32(payload) & 0xFFFFFFFF:08x}",
            "output_crc32": f"0x{zlib.crc32(rx_payload) & 0xFFFFFFFF:08x}",
            "input_output_match": match,
            "lane_mask": f"0x{lane_mask:x}",
            "ack_lane_mask": f"0x{ack_mask:x}",
            "session": f"0x{session:04x}",
            "transfer": transfer,
            "script_hardware_actions_executed": False,
            "source_evidence_contains_hardware_actions": False,
            "ethernet_used": False,
        }
        write_json(evidence_dir / "p6_jtag_axi_transport_summary.json", summary)
        if args.json_summary:
            print(json.dumps(summary, ensure_ascii=False))
        return 0 if result == PASS else 1
    except Exception as exc:
        summary = {
            "P6_HOST_FILE_TRANSPORT_LOCAL_BACKEND": FAIL,
            "P6_HOST_FILE_TRANSPORT_JTAG": BLOCKED,
            "generated_at_utc": now_iso(),
            "reason": str(exc),
            "script_hardware_actions_executed": False,
            "ethernet_used": False,
        }
        write_json(evidence_dir / "p6_jtag_axi_transport_summary.json", summary)
        if args.json_summary:
            print(json.dumps(summary, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
