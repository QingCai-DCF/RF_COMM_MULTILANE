#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "config/register_map/generated"))
import ir_regs as regs  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: dict[str, Any]) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False))


def payload_word(payload: bytes, word_index: int) -> int:
    value = 0
    for byte_lane in range(4):
        offset = word_index * 4 + byte_lane
        if offset < len(payload):
            value |= payload[offset] << (8 * byte_lane)
    return value


def lfsr_bytes(width: int, seed: int, length: int) -> bytes:
    state = seed
    mask = (1 << width) - 1
    out = bytearray()
    for _ in range(length):
        value = 0
        for bit_index in range(8):
            feedback = ((state >> (width - 1)) ^ (state >> (width - 2))) & 1
            state = ((state << 1) | feedback) & mask
            value |= (state & 1) << bit_index
        out.append(value)
    return bytes(out)


def make_payload(pattern: str, length: int) -> bytes:
    name = pattern.lower()
    if name in {"zeros", "zero"}:
        return bytes(length)
    if name in {"ones", "ff"}:
        return bytes([0xFF]) * length
    if name in {"0xaa", "aa"}:
        return bytes([0xAA]) * length
    if name in {"0x55", "55"}:
        return bytes([0x55]) * length
    if name in {"counter", "counter8"}:
        return bytes(index & 0xFF for index in range(length))
    if name in {"walking_one", "walking1"}:
        return bytes(1 << (index % 8) for index in range(length))
    if name in {"walking_zero", "walking0"}:
        return bytes((~(1 << (index % 8))) & 0xFF for index in range(length))
    if name == "prbs7":
        return lfsr_bytes(7, 0x5A, length)
    if name == "prbs15":
        return lfsr_bytes(15, 0x4A5A, length)
    if name in {"deterministic_random", "random"}:
        state = 0x2201
        out = bytearray()
        for _ in range(length):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            out.append((state >> 24) & 0xFF)
        return bytes(out)
    raise ValueError(f"unsupported P6 payload pattern: {pattern}")


def build_case(lines: list[str], prefix: str, payload: bytes, lane_mask: int, base: int) -> None:
    def addr(offset: int) -> str:
        return f"0x{base + offset:08x}"

    def assertion(offset: int, mask: int, expected: int, key: str) -> None:
        lines.append(f"ASSERT {addr(offset)} 0x{mask:08x} 0x{expected:08x} {prefix}_{key}")

    crc = zlib.crc32(payload) & 0xFFFFFFFF
    words = (len(payload) + 3) // 4
    tx_base = getattr(regs, "IR_REG_P6_PAYLOAD_WINDOW_BASE", 0x200)
    rx_base = getattr(regs, "IR_REG_P6_RX_WINDOW_BASE", 0x300)
    lines += [f"# {prefix}", f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000001", "WAIT 1"]
    for word_index in range(words):
        value = payload_word(payload, word_index)
        lines.append(f"W {addr(tx_base + 4 * word_index)} 0x{value:08x}")
    for word_index in range(words):
        assertion(tx_base + 4 * word_index, 0xFFFFFFFF, payload_word(payload, word_index), f"TXW{word_index}")
    lines += [
        f"W {addr(regs.IR_REG_P6_SESSION)} 0x00002201",
        f"W {addr(regs.IR_REG_P6_LANE_MASK)} 0x{lane_mask:08x}",
        f"W {addr(regs.IR_REG_P6_ACK_LANE_MASK)} 0x{lane_mask:08x}",
        f"W {addr(regs.IR_REG_P6_PAYLOAD_LEN)} 0x{len(payload):08x}",
        f"W {addr(regs.IR_REG_P6_TIMEOUT_CYCLES)} 0x0061a800",
        f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000004",
        f"POLL {addr(regs.IR_REG_P6_STATUS)} 0x00000004 0x00000004 2000 {prefix}_COMMIT",
    ]
    assertion(regs.IR_REG_P6_PAYLOAD_CRC32, 0xFFFFFFFF, crc, "TXCRC")
    lines += [
        f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000008",
        f"POLL {addr(regs.IR_REG_P6_STATUS)} 0x00000010 0x00000010 10000 {prefix}_DONE",
    ]
    assertion(regs.IR_REG_P6_STATUS, 0x000000F0, 0x00000010, "STATUS")
    assertion(regs.IR_REG_P6_MAILBOX_STATUS, 0xFFFFFFFF, 0x50364F4B, "MAILBOX")
    assertion(regs.IR_REG_P6_RX_PAYLOAD_LEN, 0x0000FFFF, len(payload), "RXLEN")
    assertion(regs.IR_REG_P6_RX_PAYLOAD_CRC32, 0xFFFFFFFF, crc, "RXCRC")
    assertion(regs.IR_REG_P6_RX_DIGEST, 0xFFFFFFFF, crc, "RXDIGEST")
    assertion(regs.IR_REG_P6_TX_COUNT, 0xFFFFFFFF, 1, "TXCOUNT")
    assertion(regs.IR_REG_P6_RX_GOOD_COUNT_L0, 0xFFFFFFFF, 1 if lane_mask & 1 else 0, "RXGOOD0")
    assertion(regs.IR_REG_P6_RX_GOOD_COUNT_L1, 0xFFFFFFFF, 1 if lane_mask & 2 else 0, "RXGOOD1")
    for offset, key in (
        (regs.IR_REG_P6_CRC_BAD, "CRCBAD"),
        (regs.IR_REG_P6_PAYLOAD_MISMATCH, "MISMATCH"),
        (regs.IR_REG_P6_RETRY_EXHAUSTED, "RETRYEXHAUSTED"),
        (regs.IR_REG_P6_TX_FAIL, "TXFAIL"),
        (regs.IR_REG_P6_DUTY_VIOLATION, "DUTY"),
        (regs.IR_REG_P6_ERROR_CODE, "ERROR"),
        (regs.IR_REG_P6_STICKY_ERROR, "STICKY"),
    ):
        assertion(offset, 0xFFFFFFFF, 0, key)
    assertion(regs.IR_REG_P6_TXD_HIGH_CONSECUTIVE_MAX, 0xFFFFFFFF, 8, "TXDHIGHMAX")
    assertion(regs.IR_REG_COUNTER_FRAME_GOOD, 0xFFFFFFFF, 1, "FRAMEGOOD")
    assertion(regs.IR_REG_COUNTER_FRAME_BAD, 0xFFFFFFFF, 0, "FRAMEBAD")
    assertion(regs.IR_REG_COUNTER_ACK_SENT, 0xFFFFFFFF, 1, "ACKSENT")
    assertion(regs.IR_REG_COUNTER_ACK_SEEN, 0xFFFFFFFF, 1, "ACKSEEN")
    for word_index in range(words):
        valid_bytes = min(4, len(payload) - 4 * word_index)
        valid_mask = (1 << (8 * valid_bytes)) - 1
        assertion(
            rx_base + 4 * word_index,
            valid_mask,
            payload_word(payload, word_index) & valid_mask,
            f"RXW{word_index}",
        )
    lines.append(f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000030")


def build_negative(lines: list[str], prefix: str, *, base: int, session: int, lane: int, ack: int, error: int) -> None:
    def addr(offset: int) -> str:
        return f"0x{base + offset:08x}"

    lines += [
        f"# {prefix}",
        f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000001", "WAIT 1",
        f"W {addr(getattr(regs, 'IR_REG_P6_PAYLOAD_WINDOW_BASE', 0x200))} 0x000000a5",
        f"W {addr(regs.IR_REG_P6_SESSION)} 0x{session:08x}",
        f"W {addr(regs.IR_REG_P6_LANE_MASK)} 0x{lane:08x}",
        f"W {addr(regs.IR_REG_P6_ACK_LANE_MASK)} 0x{ack:08x}",
        f"W {addr(regs.IR_REG_P6_PAYLOAD_LEN)} 0x00000001",
        f"W {addr(regs.IR_REG_P6_TIMEOUT_CYCLES)} 0x00010000",
        f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000004",
        f"ASSERT {addr(regs.IR_REG_P6_STATUS)} 0x00000070 0x00000070 {prefix}_REJECT_STATUS",
        f"ASSERT {addr(regs.IR_REG_P6_ERROR_CODE)} 0xffffffff 0x{error:08x} {prefix}_ERROR",
        f"ASSERT {addr(regs.IR_REG_P6_STICKY_ERROR)} 0xffffffff 0x00000001 {prefix}_STICKY",
        f"ASSERT {addr(regs.IR_REG_P6_TX_COUNT)} 0xffffffff 0x00000000 {prefix}_NO_TX",
        f"ASSERT {addr(regs.IR_REG_COUNTER_TX_PULSE)} 0xffffffff 0x00000000 {prefix}_NO_TX_PULSES",
        f"ASSERT {addr(regs.IR_REG_P6_TXD_HIGH_CONSECUTIVE_MAX)} 0xffffffff 0x00000000 {prefix}_NO_TXD_HIGH",
        f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000002",
        f"ASSERT {addr(regs.IR_REG_P6_STICKY_ERROR)} 0xffffffff 0x00000000 {prefix}_STICKY_CLEAR",
        f"ASSERT {addr(regs.IR_REG_P6_ERROR_CODE)} 0xffffffff 0x00000000 {prefix}_ERROR_CLEAR",
        f"W {addr(regs.IR_REG_P6_CTRL)} 0x00000030",
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one shutdown-bounded P6 hardware payload matrix over JTAG/AXI.")
    parser.add_argument("--lane-mask", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--stage-name", required=True)
    parser.add_argument("--include-negative", action="store_true")
    parser.add_argument("--max-runtime-sec", type=int, required=True)
    parser.add_argument("--base-address", default="0x43c00000")
    parser.add_argument("--jtag-frequency-hz", type=int, default=10_000_000)
    args = parser.parse_args()

    lane_mask = int(args.lane_mask, 0)
    if lane_mask not in (1, 2, 3):
        raise SystemExit("lane mask must be 0x1, 0x2, or 0x3")
    profile = (ROOT / args.profile).resolve()
    evidence_dir = (ROOT / args.evidence_dir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    profile_data = json.loads(profile.read_text(encoding="utf-8"))
    cases = [(int(length), str(pattern)) for length in profile_data["payload_length"] for pattern in profile_data["payload_pattern"]]
    positive_masks = [1, 2, 3] if args.include_negative else [lane_mask]
    base = int(args.base_address, 0)
    lines = ["# P6 live physical matrix; no Ethernet, no motion, lane mask bounded to 0x3."]
    rows: list[dict[str, Any]] = []
    case_index = 0
    for positive_mask in positive_masks:
        for length, pattern in cases:
            prefix = f"C{case_index:03d}_M{positive_mask}_{pattern.upper().replace('0X', 'X')}_L{length}"
            payload = make_payload(pattern, length)
            build_case(lines, prefix, payload, positive_mask, base)
            rows.append({
                "case_index": case_index,
                "length": length,
                "pattern": pattern,
                "lane_mask": f"0x{positive_mask:x}",
                "ack_lane_mask": f"0x{positive_mask:x}",
                "crc32": f"0x{zlib.crc32(payload) & 0xffffffff:08x}",
                "result": "PASS_IF_STAGE_PASS",
            })
            case_index += 1
    negative_cases = 0
    if args.include_negative:
        build_negative(lines, "NEG_SESSION", base=base, session=0x2202, lane=lane_mask, ack=lane_mask, error=1)
        build_negative(lines, "NEG_ACK_MASK", base=base, session=0x2201, lane=lane_mask, ack=1 if lane_mask != 1 else 2, error=3)
        # The authorized hardware boundary forbids even attempting a lane mask
        # above 0x3.  That rejection is covered by the register integration
        # simulation; live hardware exercises only in-scope session/ACK rejects.
        negative_cases = 2

    txn_file = evidence_dir / "p6_jtag_axi_matrix_transactions.txt"
    result_file = evidence_dir / "p6_jtag_axi_matrix_raw_result.log"
    write_text(txn_file, "\n".join(lines))
    candidate_path = ROOT / "evidence/generated/vivado/p6_jtag_candidate/p6_jtag_candidate_build_summary.json"
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    bitstream = ROOT / candidate["artifacts"]["bit"]["immutable"]
    ltx = ROOT / candidate["artifacts"]["ltx"]["immutable"]
    active_xdc = ROOT / "constraints/active/PORT1.generated.xdc"
    pinmap = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
    shutdown = ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
    command = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/hw/run_p6_jtag_axi_stage_safe.ps1",
        "-Stage", args.stage_name,
        "-Bitstream", str(bitstream), "-BitstreamSha256", sha256_file(bitstream),
        "-Ltx", str(ltx), "-LtxSha256", sha256_file(ltx),
        "-Profile", str(profile), "-ProfileSha256", sha256_file(profile),
        "-ActiveXdcSha256", sha256_file(active_xdc), "-PinmapSha256", sha256_file(pinmap),
        "-ShutdownBitstreamSha256", sha256_file(shutdown),
        "-TransactionFile", str(txn_file), "-ResultFile", str(result_file), "-EvidenceDir", str(evidence_dir),
        "-LaneCount", "2", "-MaxLaneMask", "0x3", "-MaxRuntimeSec", str(args.max_runtime_sec),
        "-JtagFrequencyHz", str(args.jtag_frequency_hz), "-NoEthernet", "-NoMotion", "-ShutdownOnExit",
    ]
    env = os.environ.copy()
    env["RF_COMM_HW_AUTH"] = "P6_LOCAL_TRANSPORT_APPROVED"
    proc = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
    write_text(evidence_dir / "matrix_wrapper.stdout.log", proc.stdout)
    write_text(evidence_dir / "matrix_wrapper.stderr.log", proc.stderr)
    raw_text = result_file.read_text(encoding="utf-8", errors="ignore") if result_file.exists() else ""
    safe_text = (evidence_dir / "p6_safe_stage_summary.log").read_text(encoding="utf-8", errors="ignore") if (evidence_dir / "p6_safe_stage_summary.log").exists() else ""
    passed = proc.returncode == 0 and "P6_JTAG_AXI_TRANSACTIONS=PASS" in raw_text and "P6_SAFE_STAGE_STATUS=PASS" in safe_text
    for row in rows:
        row["result"] = "PASS" if passed else "FAIL_OR_NOT_REACHED"
    csv_path = evidence_dir / "p6_jtag_axi_matrix.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "P6_JTAG_AXI_HARDWARE_MATRIX": "PASS" if passed else "FAIL",
        "stage": args.stage_name,
        "generated_at_utc": now_iso(),
        "positive_cases": len(rows),
        "negative_cases": negative_cases,
        "lane_mask": f"0x{lane_mask:x}",
        "positive_lane_masks": [f"0x{mask:x}" for mask in positive_masks],
        "simulation_only_negative_cases": ["lane mask >0x3 rejected before hardware TX"],
        "ack_lane_mask": f"0x{lane_mask:x}",
        "bitstream": rel(bitstream),
        "bitstream_sha256": sha256_file(bitstream),
        "ltx": rel(ltx),
        "ltx_sha256": sha256_file(ltx),
        "profile": rel(profile),
        "profile_sha256": sha256_file(profile),
        "transaction_file": rel(txn_file),
        "raw_result": rel(result_file),
        "csv": rel(csv_path),
        "safe_wrapper_returncode": proc.returncode,
        "shutdown_before": "BEFORE_STAGE_SHUTDOWN_EXIT=0" in safe_text,
        "shutdown_after": "AFTER_STAGE_SHUTDOWN_EXIT=0" in safe_text,
        "ethernet_used": False,
        "motion_used": False,
        "hardware_actions_executed": True,
    }
    write_json(evidence_dir / "p6_jtag_axi_matrix_summary.json", summary)
    write_text(evidence_dir / "summary.md", "\n".join([
        f"# {args.stage_name}", "", f"P6_JTAG_AXI_HARDWARE_MATRIX: {summary['P6_JTAG_AXI_HARDWARE_MATRIX']}",
        f"POSITIVE_CASES: {len(rows)}", f"NEGATIVE_CASES: {negative_cases}",
        f"LANE_MASK: 0x{lane_mask:x}", f"BITSTREAM_SHA256: {summary['bitstream_sha256']}",
        f"SHUTDOWN_BEFORE: {summary['shutdown_before']}", f"SHUTDOWN_AFTER: {summary['shutdown_after']}",
        "ETHERNET_USED: false", "MOTION_USED: false",
    ]))
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
