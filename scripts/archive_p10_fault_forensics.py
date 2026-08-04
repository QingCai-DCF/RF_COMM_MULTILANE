#!/usr/bin/env python3
"""Convert XSDB first-fault word dumps into canonical binary/JSON evidence.

This program performs no hardware access.  The XSDB capture script leaves the
functional FPGA image in full shutdown; this converter validates the complete
ordered read, writes the raw little-endian binary, parses it, and records its
SHA256 before a separate XSDB archive-commit operation is allowed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any, Iterable


MAGIC0 = 0x46303150  # bytes: P10F
MAGIC1 = 0x57415246  # bytes: FRAW
BINARY_SCHEMA = 1
HEADER_WORDS = 16
SNAPSHOT_MAGIC = 0x46465331
SNAPSHOT_SCHEMA = 0x00010001
ROLE_IDS = {"fixed": 1, "rotating": 2}
ROLE_NAMES = {value: key for key, value in ROLE_IDS.items()}
STATUS_NAMES = (
    "frozen",
    "post_trace_complete",
    "snapshot_read_complete",
    "event_read_complete",
    "archive_committed",
    "clear_armed",
    "first_fault_hold",
    "effective_full_shutdown",
    "tx_kill",
    "capture_fault_current",
)
REQUIRED_META = (
    "capabilities",
    "status",
    "fault_sequence",
    "fault_timestamp_low",
    "fault_timestamp_high",
    "fault_cause",
    "snapshot_words",
    "pre_event_count",
    "post_event_count",
    "total_event_count",
    "event_depth",
    "event_words",
)


def parse_u32(value: str) -> int:
    parsed = int(value, 0)
    if not 0 <= parsed <= 0xFFFFFFFF:
        raise ValueError(f"value outside uint32: {value}")
    return parsed


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_psv(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    if not lines:
        raise ValueError(f"empty forensic PSV: {path}")
    header = lines[0].split("|")
    if len(header) != 3 or header[:2] != ["P10_FF_PSV", "1"]:
        raise ValueError(f"invalid forensic PSV header: {path}")
    role = header[2]
    if role not in ROLE_IDS:
        raise ValueError(f"invalid forensic role: {role}")

    meta: dict[str, int] = {}
    snapshots: dict[int, int] = {}
    events: dict[tuple[int, int], int] = {}
    ended = False
    for line_number, line in enumerate(lines[1:], 2):
        fields = line.split("|")
        if fields[0] == "META" and len(fields) == 3:
            if fields[1] in meta:
                raise ValueError(f"duplicate META {fields[1]} at line {line_number}")
            meta[fields[1]] = parse_u32(fields[2])
        elif fields[0] == "SNAPSHOT" and len(fields) == 3:
            index = int(fields[1], 10)
            if index < 0 or index in snapshots:
                raise ValueError(f"invalid snapshot index at line {line_number}")
            snapshots[index] = parse_u32(fields[2])
        elif fields[0] == "EVENT" and len(fields) == 4:
            key = (int(fields[1], 10), int(fields[2], 10))
            if min(key) < 0 or key in events:
                raise ValueError(f"invalid event index at line {line_number}")
            events[key] = parse_u32(fields[3])
        elif fields[0] == "END" and len(fields) == 2 and fields[1] == role:
            if line_number != len(lines):
                raise ValueError("data appears after forensic END record")
            ended = True
        else:
            raise ValueError(f"invalid forensic PSV line {line_number}: {line}")
    if not ended:
        raise ValueError("forensic PSV END record is missing")
    missing = [key for key in REQUIRED_META if key not in meta]
    if missing:
        raise ValueError(f"missing forensic metadata: {missing}")

    caps = meta["capabilities"]
    snapshot_words = meta["snapshot_words"]
    total_events = meta["total_event_count"]
    event_words = meta["event_words"]
    frozen = bool(meta["status"] & 1)
    if (caps >> 24) != 0x46:
        raise ValueError(f"forensic capability magic mismatch: 0x{caps:08X}")
    if (caps & 0xFF) != snapshot_words or ((caps >> 8) & 0xFF) != event_words:
        raise ValueError("forensic capability dimensions disagree with metadata")
    if meta["pre_event_count"] + meta["post_event_count"] != total_events:
        raise ValueError("forensic event counts do not sum")
    if total_events > meta["event_depth"]:
        raise ValueError("forensic event count exceeds BRAM depth")
    if frozen:
        if not meta["status"] & (1 << 1):
            raise ValueError("frozen capture is missing its post-fault tail")
        if sorted(snapshots) != list(range(snapshot_words)):
            raise ValueError("snapshot ordered read is incomplete")
        expected_events = [
            (entry, word)
            for entry in range(total_events)
            for word in range(event_words)
        ]
        if sorted(events) != expected_events:
            raise ValueError("event ordered read is incomplete")
    elif snapshots or events or total_events:
        raise ValueError("mutable non-frozen evidence must not be serialized")

    return {
        "role": role,
        "meta": meta,
        "snapshot_words": [snapshots[index] for index in range(snapshot_words)]
        if frozen else [],
        "event_records": [
            [events[(entry, word)] for word in range(event_words)]
            for entry in range(total_events)
        ] if frozen else [],
        "source_psv": str(path.resolve()),
    }


def serialize_record(record: dict[str, Any]) -> bytes:
    meta = record["meta"]
    header = [
        MAGIC0,
        MAGIC1,
        BINARY_SCHEMA,
        ROLE_IDS[record["role"]],
        meta["capabilities"],
        meta["status"],
        meta["fault_sequence"],
        meta["fault_timestamp_low"],
        meta["fault_timestamp_high"],
        meta["fault_cause"],
        meta["snapshot_words"],
        meta["pre_event_count"],
        meta["post_event_count"],
        meta["total_event_count"],
        meta["event_depth"],
        meta["event_words"],
    ]
    words = [*header, *record["snapshot_words"]]
    for event in record["event_records"]:
        words.extend(event)
    return struct.pack(f"<{len(words)}I", *words)


def parse_binary(data: bytes) -> dict[str, Any]:
    if len(data) < HEADER_WORDS * 4 or len(data) % 4:
        raise ValueError("forensic binary length is invalid")
    words = list(struct.unpack(f"<{len(data) // 4}I", data))
    if words[0:3] != [MAGIC0, MAGIC1, BINARY_SCHEMA]:
        raise ValueError("forensic binary magic/schema mismatch")
    if words[3] not in ROLE_NAMES:
        raise ValueError("forensic binary role is invalid")
    meta = dict(zip(REQUIRED_META, words[4:16], strict=True))
    payload_snapshot_words = meta["snapshot_words"] if meta["status"] & 1 else 0
    payload_event_words = (
        meta["total_event_count"] * meta["event_words"]
        if meta["status"] & 1 else 0
    )
    expected_words = HEADER_WORDS + payload_snapshot_words + payload_event_words
    if len(words) != expected_words:
        raise ValueError(
            f"forensic binary word count {len(words)} != {expected_words}"
        )
    snapshot = words[HEADER_WORDS:HEADER_WORDS + payload_snapshot_words]
    event_flat = words[HEADER_WORDS + payload_snapshot_words:]
    events = [
        event_flat[index:index + meta["event_words"]]
        for index in range(0, len(event_flat), meta["event_words"])
    ]
    if meta["status"] & 1:
        if len(snapshot) < 24 or snapshot[0] != SNAPSHOT_MAGIC or \
                snapshot[1] != SNAPSHOT_SCHEMA:
            raise ValueError("frozen snapshot magic/schema mismatch")
        if snapshot[2] != meta["snapshot_words"]:
            raise ValueError("snapshot word count does not match binary header")
    return {
        "role": ROLE_NAMES[words[3]],
        "meta": meta,
        "snapshot_words": snapshot,
        "event_records": events,
    }


def bits(value: int, names: Iterable[str]) -> dict[str, bool]:
    return {name: bool(value & (1 << index)) for index, name in enumerate(names)}


def decode_record(record: dict[str, Any], digest: str) -> dict[str, Any]:
    meta = record["meta"]
    snapshot = record["snapshot_words"]
    module_count = (meta["capabilities"] >> 20) & 0xF
    lane_count = (meta["capabilities"] >> 16) & 0xF
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "FROZEN" if meta["status"] & 1 else "NO_FAULT",
        "role": record["role"],
        "binary_sha256": digest,
        "capabilities": f"0x{meta['capabilities']:08X}",
        "status_word": f"0x{meta['status']:08X}",
        "status_bits": bits(meta["status"], STATUS_NAMES),
        "lane_count": lane_count,
        "module_count": module_count,
        "fault_sequence": meta["fault_sequence"],
        "fault_timestamp_cycles": (
            (meta["fault_timestamp_high"] << 32) | meta["fault_timestamp_low"]
        ),
        "fault_cause": f"0x{meta['fault_cause']:08X}",
        "event_counts": {
            "pre": meta["pre_event_count"],
            "post": meta["post_event_count"],
            "total": meta["total_event_count"],
        },
        "snapshot": None,
        "events": [],
    }
    if not snapshot:
        return result

    packed_status = snapshot[7]
    result["snapshot"] = {
        "magic": f"0x{snapshot[0]:08X}",
        "schema": f"0x{snapshot[1]:08X}",
        "timestamp_cycles": (snapshot[5] << 32) | snapshot[4],
        "fault_cause": f"0x{snapshot[6]:08X}",
        "packed_status": f"0x{packed_status:08X}",
        "object_id": f"0x{snapshot[8]:08X}",
        "object_error": f"0x{snapshot[9]:08X}",
        "lane_state": f"0x{snapshot[10]:08X}",
        "tx_next_sequence": snapshot[11] & 0xFFFF,
        "tx_ack_base": snapshot[11] >> 16,
        "tx_outstanding": (snapshot[12] >> 16) & 0x3F,
        "tx_outstanding_high_watermark": (snapshot[12] >> 22) & 0x3F,
        "rx_base_sequence": snapshot[13] & 0xFFFF,
        "rx_sack_bitmap": f"0x{snapshot[14]:08X}",
        "raw_state": f"0x{snapshot[15]:08X}",
        "tx_attempt_count": snapshot[16],
        "tx_retry_count": snapshot[17],
        "tx_retry_exhausted_count": snapshot[18],
        "tx_timeout_count": snapshot[19],
        "tx_migration_count": snapshot[20],
        "input_byte_count": snapshot[21],
        "output_byte_count": snapshot[22],
        "module_summary": f"0x{snapshot[23]:08X}",
        "modules": [],
    }
    for module in range(module_count):
        base = 24 + 10 * module
        values = snapshot[base:base + 10]
        flags = values[7]
        result["snapshot"]["modules"].append({
            "module_index": module,
            "physical_tx_count": values[0],
            "continuous_high_current_cycles": values[1],
            "continuous_high_max_cycles": values[2],
            "rolling_duty_current_cycles": values[3],
            "rolling_duty_max_cycles": values[4],
            "rolling_duty_headroom_cycles": values[5],
            "hard_fault_count": values[6],
            "flags": f"0x{flags:08X}",
            "physical_txd": bool(flags & (1 << 0)),
            "sd": bool(flags & (1 << 1)),
            "mode": bool(flags & (1 << 2)),
            "safety_fault": bool(flags & (1 << 3)),
            "endpoint_armed": bool(flags & (1 << 4)),
            "tx_kill": bool(flags & (1 << 5)),
            "effective_shutdown": bool(flags & (1 << 6)),
            "functional_reset_asserted": bool(flags & (1 << 7)),
            "phy_ready": bool(flags & (1 << 8)),
            "startup_done": bool(flags & (1 << 9)),
            "raw_rx_count": values[8],
            "target_throttle_count": values[9],
        })

    for index, event in enumerate(record["event_records"]):
        word0 = event[0]
        result["events"].append({
            "index": index,
            "magic": f"0x{word0 >> 16:04X}",
            "event_code": f"0x{(word0 >> 8) & 0xFF:02X}",
            "module_index": word0 & 0xFF,
            "timestamp_cycles": (event[2] << 32) | event[1],
            "packed_status": f"0x{event[3]:08X}",
            "object_id": f"0x{event[4]:08X}",
            "tx_next_sequence": event[5] & 0xFFFF,
            "tx_ack_base": event[5] >> 16,
            "tx_retry_count": event[6],
            "tag": f"0x{event[7]:08X}",
        })
    return result


def write_archive(record: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    role = record["role"]
    raw = serialize_record(record)
    reparsed = parse_binary(raw)
    if reparsed["role"] != role:
        raise ValueError("binary round-trip role mismatch")
    digest = sha256_bytes(raw)
    binary_path = output_dir / f"{role}.p10ff.bin"
    json_path = output_dir / f"{role}.p10ff.json"
    sha_path = output_dir / f"{role}.p10ff.sha256"
    binary_path.write_bytes(raw)
    parsed = decode_record(reparsed, digest)
    parsed["raw_binary"] = str(binary_path.resolve())
    json_path.write_text(
        json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    sha_path.write_text(f"{digest}  {binary_path.name}\n", encoding="ascii")
    if sha256_bytes(binary_path.read_bytes()) != digest:
        raise RuntimeError("written forensic binary SHA256 mismatch")
    return {
        "role": role,
        "status": parsed["status"],
        "binary": str(binary_path.resolve()),
        "binary_sha256": digest,
        "json": str(json_path.resolve()),
        "sha256_file": str(sha_path.resolve()),
        "digest_words_little_endian": [
            f"0x{word:08X}" for word in struct.unpack("<8I", bytes.fromhex(digest))
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--psv",
        type=Path,
        action="append",
        required=True,
        help="XSDB PSV file; repeat for the fixed and rotating endpoints.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    records = [parse_psv(path.resolve()) for path in args.psv]
    roles = [record["role"] for record in records]
    if len(set(roles)) != len(roles):
        raise ValueError(f"duplicate forensic roles: {roles}")
    archives = [write_archive(record, args.output_dir.resolve()) for record in records]
    summary = {
        "schema_version": 1,
        "status": "PASS",
        "hardware_actions_executed": False,
        "archives": archives,
    }
    summary_path = args.summary.resolve() if args.summary else \
        args.output_dir.resolve() / "p10_fault_forensics_archive_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("P10_FAULT_FORENSICS_ARCHIVE=PASS")
    print(f"P10_FAULT_FORENSICS_ARCHIVE_SUMMARY={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
