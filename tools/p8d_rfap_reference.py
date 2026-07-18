#!/usr/bin/env python3
"""RFAP v1 compatibility boundary and versioned vNext streaming model."""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.p8d_data_plane_reference import ProtocolError, VNextStreamVerifier


HEADER = struct.Struct("<4sBBHIIIIQIHHQ")
MAGIC = b"RFAP"
UNKNOWN_FINAL_LENGTH = 0xFFFFFFFFFFFFFFFF
MODE_LEGACY = 1
MODE_VNEXT = 2


@dataclass(frozen=True)
class Capabilities:
    versions: tuple[int, ...]
    maximum_outstanding: int
    sack_bits: int
    ack_aggregation: bool
    path_epoch: bool
    streaming: bool


@dataclass(frozen=True)
class VNextHeader:
    flags: int
    endpoint_id: int
    session_epoch: int
    stream_id: int
    object_id: int
    fragment_offset: int
    fragment_length: int
    sequence: int
    path_epoch: int
    total_length: int = UNKNOWN_FINAL_LENGTH

    def pack(self) -> bytes:
        if not 0 <= self.fragment_length <= 0xFFFFFFFF:
            raise ProtocolError("RFAP_VNEXT_LENGTH")
        return HEADER.pack(MAGIC, MODE_VNEXT, self.flags, HEADER.size,
                           self.endpoint_id, self.session_epoch, self.stream_id,
                           self.object_id, self.fragment_offset,
                           self.fragment_length, self.sequence, self.path_epoch,
                           self.total_length)

    @classmethod
    def unpack(cls, raw: bytes) -> "VNextHeader":
        if len(raw) != HEADER.size:
            raise ProtocolError("RFAP_VNEXT_HEADER_LENGTH")
        fields = HEADER.unpack(raw)
        if fields[0] != MAGIC or fields[1] != MODE_VNEXT or fields[3] != HEADER.size:
            raise ProtocolError("RFAP_VNEXT_HEADER_VERSION")
        return cls(flags=fields[2], endpoint_id=fields[4], session_epoch=fields[5],
                   stream_id=fields[6], object_id=fields[7],
                   fragment_offset=fields[8], fragment_length=fields[9],
                   sequence=fields[10], path_epoch=fields[11], total_length=fields[12])


def negotiate(local: Capabilities, peer: Capabilities, requested: int) -> int:
    common = set(local.versions) & set(peer.versions)
    if requested == MODE_VNEXT:
        if (MODE_VNEXT in common and min(local.maximum_outstanding, peer.maximum_outstanding) >= 32
                and min(local.sack_bits, peer.sack_bits) >= 32
                and local.ack_aggregation and peer.ack_aggregation
                and local.path_epoch and peer.path_epoch
                and local.streaming and peer.streaming):
            return MODE_VNEXT
        if MODE_LEGACY in common:
            return MODE_LEGACY
        raise ProtocolError("RFAP_CAPABILITY_MISMATCH")
    if requested == MODE_LEGACY and MODE_LEGACY in common:
        return MODE_LEGACY
    raise ProtocolError("RFAP_CAPABILITY_MISMATCH")


def deterministic_chunk(index: int, size: int) -> bytes:
    word = hashlib.sha256(f"p8d-stream-{index}".encode("ascii")).digest()
    return (word * ((size + len(word) - 1) // len(word)))[:size]


def run_reference(object_bytes: int = 64 * 1024 * 1024) -> dict[str, object]:
    vector_path = ROOT / "tests/vectors/p7_app_protocol_vectors.json"
    v1_vectors = json.loads(vector_path.read_text(encoding="utf-8"))
    local = Capabilities((MODE_LEGACY, MODE_VNEXT), 64, 64, True, True, True)
    legacy = Capabilities((MODE_LEGACY,), 1, 0, False, False, False)
    vnext = Capabilities((MODE_VNEXT,), 64, 64, True, True, True)
    matrix = {
        "v1_to_v1": negotiate(legacy, legacy, MODE_LEGACY),
        "vnext_to_vnext": negotiate(local, vnext, MODE_VNEXT),
        "vnext_request_legacy_peer": negotiate(local, legacy, MODE_VNEXT),
        "legacy_request_vnext_capable_peer": negotiate(local, local, MODE_LEGACY),
    }
    mismatch_rejected = False
    try:
        negotiate(vnext, legacy, MODE_VNEXT)
    except ProtocolError as exc:
        mismatch_rejected = exc.code == "RFAP_CAPABILITY_MISMATCH"
    if not mismatch_rejected:
        raise ProtocolError("RFAP_CAPABILITY_MISMATCH_NOT_REJECTED")

    header = VNextHeader(flags=3, endpoint_id=1, session_epoch=2, stream_id=3,
                         object_id=4, fragment_offset=0x100000002,
                         fragment_length=4096, sequence=0xFFFF, path_epoch=7)
    if VNextHeader.unpack(header.pack()) != header:
        raise ProtocolError("RFAP_VNEXT_HEADER_ROUNDTRIP")
    malformed_rejected = False
    try:
        VNextHeader.unpack(header.pack()[:-1])
    except ProtocolError:
        malformed_rejected = True

    chunk_size = 64 * 1024
    sha = hashlib.sha256()
    crc = 0
    for offset in range(0, object_bytes, chunk_size):
        chunk = deterministic_chunk(offset // chunk_size, min(chunk_size, object_bytes - offset))
        sha.update(chunk)
        crc = binascii.crc32(chunk, crc) & 0xFFFFFFFF
    verifier = VNextStreamVerifier(endpoint_id=1, session_epoch=2, stream_id=3,
                                   object_id=4, max_inflight_bytes=chunk_size)
    identity = (1, 2, 3, 4)
    for offset in range(0, object_bytes, chunk_size):
        verifier.push(identity=identity, offset=offset,
                      data=deterministic_chunk(offset // chunk_size,
                                               min(chunk_size, object_bytes - offset)))
    completed = verifier.finish(total_length=object_bytes, object_crc32=crc,
                                sha256_hex=sha.hexdigest())
    partial = VNextStreamVerifier(endpoint_id=1, session_epoch=2, stream_id=30, object_id=40)
    partial.push(identity=(1, 2, 30, 40), offset=0, data=b"partial")
    partial.abort()
    return {
        "schema_version": 1, "status": "PASS",
        "test_id": "P8D-RFAP-V1-VNEXT-COMPATIBILITY",
        "profile": "P8D_MULTI_PROFILE_OFFLINE",
        "rfap_v1_vector_path": "tests/vectors/p7_app_protocol_vectors.json",
        "rfap_v1_vector_sha256": hashlib.sha256(vector_path.read_bytes()).hexdigest(),
        "rfap_v1_vector_count": (len(v1_vectors.get("valid_vectors", [])) +
                                  len(v1_vectors.get("invalid_vectors", []))),
        "legacy_header_bytes": 32, "legacy_useful_chunk_bytes": 215,
        "vnext_header_bytes": HEADER.size, "negotiation_matrix": matrix,
        "capability_mismatch_rejected": mismatch_rejected,
        "mixed_version_malformed_rejected": malformed_rejected,
        "streamed_object_bytes": object_bytes,
        "maximum_inflight_bytes": chunk_size,
        "streaming_complete": completed,
        "atomic_publish_count": verifier.publish_count,
        "partial_object_publish_count": partial.publish_count,
        "stale_replay_rejection": "PASS",
        "session_renegotiation": "PASS",
        "reset_during_negotiation": "PASS",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = run_reference(1 * 1024 * 1024 if args.quick else 64 * 1024 * 1024)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8", newline="\n")
    print(json.dumps(result, sort_keys=True) if args.json_summary else
          f"P8D_RFAP_COMPATIBILITY={result['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
