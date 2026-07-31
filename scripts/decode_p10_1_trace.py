#!/usr/bin/env python3
"""Decode fixed-size P10.1 trace records into deterministic JSON."""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


RECORD = struct.Struct("<QIIIIII")
EVENT_NAMES = {
    1: "PERF_START", 2: "OBJECT_ALLOC", 3: "PAYLOAD_PREP_START",
    4: "PAYLOAD_PREP_END", 5: "CRC_START", 6: "CRC_END",
    7: "SHA_START", 8: "SHA_END", 9: "CACHE_FLUSH_START",
    10: "CACHE_FLUSH_END", 11: "DESC_SUBMIT", 12: "DMA_TX_START",
    13: "DMA_TX_END", 14: "REMOTE_RX_COMPLETE",
    15: "CACHE_INVALIDATE_START", 16: "CACHE_INVALIDATE_END",
    17: "REASSEMBLY_COMPLETE", 18: "HASH_VERIFY_COMPLETE",
    19: "ATOMIC_COMMIT", 20: "OBJECT_FAIL", 21: "PERF_STOP",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = args.input.read_bytes()
    if len(payload) % RECORD.size:
        raise SystemExit("trace byte count is not a multiple of the 32-byte record")
    records = []
    for offset in range(0, len(payload), RECORD.size):
        timestamp, generation, event_id, arg0, arg1, reserved0, reserved1 = RECORD.unpack_from(payload, offset)
        if reserved0 or reserved1:
            raise SystemExit(f"trace reserved field is nonzero at byte {offset}")
        records.append({
            "timestamp": timestamp,
            "generation": generation,
            "event_id": event_id,
            "event": EVENT_NAMES.get(event_id, f"UNKNOWN_{event_id}"),
            "arg0": arg0,
            "arg1": arg1,
        })
    output = json.dumps({"schema_version": 1, "record_count": len(records), "records": records},
                        indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8", newline="\n")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
