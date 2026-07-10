#!/usr/bin/env python3
"""RF_COMM P7 application protocol v1 reference implementation.

The module is transport neutral.  It never opens a network connection and it
does not perform hardware actions.  P6 protects each encoded fragment with its
frame/payload CRC; this layer protects the complete object with CRC32 and lets
the host compare SHA256 after an atomic output commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

MAGIC = b"RFAP"
VERSION = 1
HEADER_BYTES = 32
P6_MAX_PAYLOAD_BYTES = 247
MAX_CHUNK_BYTES = P6_MAX_PAYLOAD_BYTES - HEADER_BYTES
MAX_OBJECT_BYTES = 8 * 1024 * 1024

FLAG_FIRST = 0x01
FLAG_LAST = 0x02
FLAG_RETRANSMIT = 0x04
FLAG_CONTROL = 0x08
KNOWN_FLAGS = FLAG_FIRST | FLAG_LAST | FLAG_RETRANSMIT | FLAG_CONTROL

_HEADER = struct.Struct("<4sBBHIIIHHHHI")
assert _HEADER.size == HEADER_BYTES


class ProtocolError(ValueError):
    """Raised when a fragment violates the RFAP v1 contract."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AppHeader:
    session_epoch: int
    object_id: int
    total_length: int
    fragment_index: int
    fragment_count: int
    chunk_length: int
    object_crc32: int
    flags: int = 0
    reserved: int = 0

    def validate(self) -> None:
        for name, value, limit in (
            ("session_epoch", self.session_epoch, 0xFFFFFFFF),
            ("object_id", self.object_id, 0xFFFFFFFF),
            ("total_length", self.total_length, 0xFFFFFFFF),
            ("fragment_index", self.fragment_index, 0xFFFF),
            ("fragment_count", self.fragment_count, 0xFFFF),
            ("chunk_length", self.chunk_length, 0xFFFF),
            ("object_crc32", self.object_crc32, 0xFFFFFFFF),
            ("flags", self.flags, 0xFF),
            ("reserved", self.reserved, 0xFFFF),
        ):
            if not isinstance(value, int) or not 0 <= value <= limit:
                raise ProtocolError("FIELD_RANGE", f"{name} is outside 0..{limit}")
        if self.total_length > MAX_OBJECT_BYTES:
            raise ProtocolError("OBJECT_TOO_LARGE", f"total_length exceeds {MAX_OBJECT_BYTES}")
        if self.fragment_count == 0:
            raise ProtocolError("FRAGMENT_COUNT_ZERO", "fragment_count must be nonzero")
        if self.fragment_index >= self.fragment_count:
            raise ProtocolError("FRAGMENT_INDEX_RANGE", "fragment_index must be below fragment_count")
        if self.chunk_length > MAX_CHUNK_BYTES:
            raise ProtocolError("CHUNK_TOO_LARGE", f"chunk_length exceeds {MAX_CHUNK_BYTES}")
        if self.reserved != 0:
            raise ProtocolError("RESERVED_NONZERO", "reserved must be zero")
        if self.flags & ~KNOWN_FLAGS:
            raise ProtocolError("FLAGS_UNKNOWN", "flags contain undefined bits")
        expected_first = self.fragment_index == 0
        expected_last = self.fragment_index == self.fragment_count - 1
        if bool(self.flags & FLAG_FIRST) != expected_first:
            raise ProtocolError("FIRST_FLAG", "FIRST flag does not match fragment index")
        if bool(self.flags & FLAG_LAST) != expected_last:
            raise ProtocolError("LAST_FLAG", "LAST flag does not match fragment index")
        expected_count = max(1, (self.total_length + MAX_CHUNK_BYTES - 1) // MAX_CHUNK_BYTES)
        if self.fragment_count != expected_count:
            raise ProtocolError("FRAGMENT_COUNT", "fragment_count is inconsistent with total_length")
        expected_chunk = 0 if self.total_length == 0 else min(
            MAX_CHUNK_BYTES, self.total_length - self.fragment_index * MAX_CHUNK_BYTES
        )
        if self.chunk_length != expected_chunk:
            raise ProtocolError("CHUNK_LENGTH", "chunk_length is inconsistent with object geometry")

    def encode(self) -> bytes:
        self.validate()
        return _HEADER.pack(
            MAGIC,
            VERSION,
            self.flags,
            HEADER_BYTES,
            self.session_epoch,
            self.object_id,
            self.total_length,
            self.fragment_index,
            self.fragment_count,
            self.chunk_length,
            self.reserved,
            self.object_crc32,
        )

    @classmethod
    def decode(cls, raw: bytes) -> "AppHeader":
        if len(raw) < HEADER_BYTES:
            raise ProtocolError("HEADER_TRUNCATED", "fragment is shorter than the fixed header")
        (
            magic,
            version,
            flags,
            header_len,
            session_epoch,
            object_id,
            total_length,
            fragment_index,
            fragment_count,
            chunk_length,
            reserved,
            object_crc32,
        ) = _HEADER.unpack_from(raw)
        if magic != MAGIC:
            raise ProtocolError("MAGIC", "invalid RFAP magic")
        if version != VERSION:
            raise ProtocolError("VERSION", "unsupported RFAP version")
        if header_len != HEADER_BYTES:
            raise ProtocolError("HEADER_LENGTH", "header_len must be 32")
        header = cls(
            session_epoch=session_epoch,
            object_id=object_id,
            total_length=total_length,
            fragment_index=fragment_index,
            fragment_count=fragment_count,
            chunk_length=chunk_length,
            object_crc32=object_crc32,
            flags=flags,
            reserved=reserved,
        )
        header.validate()
        return header


@dataclass(frozen=True, slots=True)
class AppFragment:
    header: AppHeader
    chunk: bytes

    def encode(self) -> bytes:
        if len(self.chunk) != self.header.chunk_length:
            raise ProtocolError("CHUNK_SIZE", "chunk bytes do not match chunk_length")
        encoded = self.header.encode() + self.chunk
        if not 1 <= len(encoded) <= P6_MAX_PAYLOAD_BYTES:
            raise ProtocolError("P6_PAYLOAD_SIZE", "encoded fragment exceeds the P6 payload contract")
        return encoded

    @classmethod
    def decode(cls, raw: bytes) -> "AppFragment":
        header = AppHeader.decode(raw)
        if len(raw) != HEADER_BYTES + header.chunk_length:
            raise ProtocolError("FRAGMENT_SIZE", "encoded fragment has trailing or missing bytes")
        return cls(header=header, chunk=bytes(raw[HEADER_BYTES:]))


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def fragment_count(total_length: int) -> int:
    if not 0 <= total_length <= MAX_OBJECT_BYTES:
        raise ProtocolError("OBJECT_TOO_LARGE", "object length is outside the supported range")
    return max(1, (total_length + MAX_CHUNK_BYTES - 1) // MAX_CHUNK_BYTES)


def segment_object(data: bytes, *, session_epoch: int, object_id: int) -> list[AppFragment]:
    if len(data) > MAX_OBJECT_BYTES:
        raise ProtocolError("OBJECT_TOO_LARGE", f"object exceeds {MAX_OBJECT_BYTES} bytes")
    count = fragment_count(len(data))
    digest = crc32(data)
    result: list[AppFragment] = []
    for index in range(count):
        start = index * MAX_CHUNK_BYTES
        chunk = data[start : start + MAX_CHUNK_BYTES]
        flags = (FLAG_FIRST if index == 0 else 0) | (FLAG_LAST if index == count - 1 else 0)
        header = AppHeader(
            session_epoch=session_epoch,
            object_id=object_id,
            total_length=len(data),
            fragment_index=index,
            fragment_count=count,
            chunk_length=len(chunk),
            object_crc32=digest,
            flags=flags,
        )
        result.append(AppFragment(header, chunk))
    return result


class Reassembler:
    """Bounded strict-order reassembler with idempotent duplicate handling."""

    def __init__(self, *, expected_session_epoch: int | None = None, max_object_bytes: int = MAX_OBJECT_BYTES):
        self.expected_session_epoch = expected_session_epoch
        self.max_object_bytes = max_object_bytes
        self._identity: tuple[int, int, int, int, int] | None = None
        self._chunks: list[bytes | None] = []
        self._next_index = 0
        self.duplicates = 0
        self.out_of_order = 0
        self.state = "EMPTY"

    @property
    def complete(self) -> bool:
        return self.state == "COMPLETE"

    @property
    def missing_count(self) -> int:
        return sum(chunk is None for chunk in self._chunks)

    def abort(self) -> None:
        self.state = "ABORTED"
        self._chunks = []

    def add(self, encoded: bytes) -> str:
        if self.state in {"REJECTED", "ABORTED"}:
            raise ProtocolError("STATE", f"cannot add a fragment while state={self.state}")
        fragment = AppFragment.decode(encoded)
        h = fragment.header
        if self.state == "COMPLETE":
            identity = (h.session_epoch, h.object_id, h.total_length, h.fragment_count, h.object_crc32)
            if identity != self._identity or self._chunks[h.fragment_index] != fragment.chunk:
                raise ProtocolError("OBJECT_REPLAY_CONFLICT", "completed object replay conflicts with committed data")
            self.duplicates += 1
            return "DUPLICATE_SAME_COMPLETE"
        if self.expected_session_epoch is not None and h.session_epoch != self.expected_session_epoch:
            self.state = "REJECTED"
            raise ProtocolError("STALE_SESSION", "fragment belongs to a stale session epoch")
        if h.total_length > self.max_object_bytes:
            self.state = "REJECTED"
            raise ProtocolError("OBJECT_TOO_LARGE", "object exceeds reassembler bound")
        identity = (h.session_epoch, h.object_id, h.total_length, h.fragment_count, h.object_crc32)
        if self._identity is None:
            self._identity = identity
            self._chunks = [None] * h.fragment_count
            self.state = "ASSEMBLING"
        elif identity != self._identity:
            self.state = "REJECTED"
            raise ProtocolError("METADATA_MISMATCH", "fragment metadata changed within an object")
        prior = self._chunks[h.fragment_index]
        if prior is not None:
            if prior != fragment.chunk:
                self.state = "REJECTED"
                raise ProtocolError("DUPLICATE_DIFFERENT", "duplicate fragment contains different data")
            self.duplicates += 1
            return "DUPLICATE_SAME"
        if h.fragment_index != self._next_index:
            self.out_of_order += 1
            self.state = "REJECTED"
            raise ProtocolError("OUT_OF_ORDER", "v1 strict-order window is zero")
        self._chunks[h.fragment_index] = fragment.chunk
        self._next_index += 1
        if self._next_index == len(self._chunks):
            data = b"".join(chunk or b"" for chunk in self._chunks)
            if len(data) != h.total_length:
                self.state = "REJECTED"
                raise ProtocolError("TOTAL_LENGTH", "reassembled length does not match total_length")
            if crc32(data) != h.object_crc32:
                self.state = "REJECTED"
                raise ProtocolError("OBJECT_CRC32", "whole-object CRC32 mismatch")
            self.state = "COMPLETE"
            return "COMPLETE"
        return "ACCEPTED"

    def data(self) -> bytes:
        if not self.complete:
            raise ProtocolError("PARTIAL_OBJECT", "partial object cannot be committed")
        return b"".join(chunk or b"" for chunk in self._chunks)


def atomic_commit(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def reassemble_encoded(fragments: Iterable[bytes], *, expected_session_epoch: int) -> bytes:
    reassembler = Reassembler(expected_session_epoch=expected_session_epoch)
    for fragment in fragments:
        reassembler.add(fragment)
    return reassembler.data()


def iter_object_fragments(data: bytes, *, session_epoch: int, object_id: int) -> Iterator[bytes]:
    for fragment in segment_object(data, session_epoch=session_epoch, object_id=object_id):
        yield fragment.encode()


def _self_test() -> dict[str, object]:
    sizes = (0, 1, 2, 30, 214, 215, 216, 246, 247, 248, 430, 431, 432, 1024, 4096, 65536, 1048576)
    cases = 0
    for size in sizes:
        data = bytes((index * 17 + size) & 0xFF for index in range(size))
        encoded = list(iter_object_fragments(data, session_epoch=0x10203040, object_id=size + 1))
        output = reassemble_encoded(encoded, expected_session_epoch=0x10203040)
        if output != data:
            raise AssertionError(f"roundtrip failed for size {size}")
        cases += 1
    return {
        "P7_APP_PROTOCOL_SELF_TEST": "PASS",
        "cases": cases,
        "max_chunk_bytes": MAX_CHUNK_BYTES,
        "max_object_bytes": MAX_OBJECT_BYTES,
        "sha256": hashlib.sha256(b"RFAP-v1").hexdigest(),
        "network_used": False,
        "hardware_actions_executed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RFAP v1 protocol reference")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.self_test:
        parser.error("--self-test is required")
    result = _self_test()
    print(json.dumps(result, ensure_ascii=False) if args.json else result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
