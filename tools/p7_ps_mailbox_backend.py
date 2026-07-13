#!/usr/bin/env python3
"""Host-side codec for the versioned P7 PS mailbox.

This module only packs and validates memory images. Hardware access is kept in
the explicit authorized runner. Descriptor submission is deliberately
two-phase: write :meth:`DescriptorRequest.pack_body` first, then publish the
separate READY word returned by :func:`pack_ready_publication_word`.
"""
from __future__ import annotations

import hashlib
import struct
import zlib
from dataclasses import dataclass

P7_MAILBOX_BASE = 0x00020000
P7_DESCRIPTOR_BASE = 0x00020100
P7_MAILBOX_BYTES = 0x100
P7_DESCRIPTOR_BYTES = 0x100
P7_QUEUE_DEPTH = 8
P7_DDR_BASE = 0x00100000
P7_DDR_END_EXCLUSIVE = 0x20000000
P7_MAX_OBJECT_BYTES = 8 * 1024 * 1024
P7_MAX_CHUNK_BYTES = 215
P7_TRACE_BYTES = 64
P7_ALIGNMENT = 64
P7_UINT32_MAX = 0xFFFFFFFF
P7_KNOWN_GOOD_TXD_HIGH_CYCLES = 8
P7_FAILURE_SNAPSHOT_BASE = 0x00021000
P7_FIRST_ERROR_DIAGNOSTIC_MAGIC = 0x44433750
P7_FIRST_ERROR_DIAGNOSTIC_BYTES = 320
P7_FIRST_ERROR_SNAPSHOT_BYTES = 64
P7_DIAGNOSTIC_MISSING_BYTE = 0x100
P7_DIAGNOSTIC_NOT_APPLICABLE = P7_UINT32_MAX

P7_FIRST_ERROR_STAGE_NAMES = {
    1: "INPUT_REF",
    2: "ENCODE_RAW",
    3: "ENCODE_REPAIR",
    4: "P6_TX_LOCAL",
    5: "P6_TX_MMIO_READBACK",
    6: "P6_RX_LOCAL",
    7: "RECEIVED",
    8: "DDR_OUTPUT_IMMEDIATE_READBACK",
    9: "DDR_OUTPUT_END_TO_END",
    10: "INTEGRITY_SNAPSHOT",
}
_P7_FIRST_ERROR_ALLOWED_ERRORS = {
    1: frozenset({24}),
    2: frozenset({25}),
    3: frozenset({21}),
    4: frozenset({26}),
    5: frozenset({27}),
    6: frozenset({28}),
    7: frozenset({22, 29}),
    8: frozenset({23, 30}),
    9: frozenset({31}),
    10: frozenset({13, 14}),
}

P7_MAILBOX_MAGIC = 0x424D3750
P7_DESCRIPTOR_MAGIC = 0x53443750
P7_RUNTIME_VERSION = 1

P7_SERVICE_BOOTING = 0
P7_SERVICE_READY = 1

P7_CONTROL_NONE = 0
P7_CONTROL_RUN = 1
P7_CONTROL_STOP = 2
P7_CONTROL_ABORT = 3
P7_CONTROL_CLEAR = 4
P7_CONTROL_SHUTDOWN = 5

P7_RUNTIME_AUTO_DEADLINE = 1 << 0
P7_RUNTIME_DEADLINE_REACHED = 1 << 1

P7_DESCRIPTOR_TRANSFER = 1
P7_DESCRIPTOR_FREE = 0
P7_DESCRIPTOR_READY = 1
P7_DESCRIPTOR_RUNNING = 2
P7_DESCRIPTOR_COMPLETE = 3
P7_DESCRIPTOR_FAILED = 4
P7_DESCRIPTOR_ABORTED = 5
P7_DESCRIPTOR_REJECTED = 6
P7_DESCRIPTOR_STATUS_OFFSET = 3 * 4

P7_LANE0_ONLY = 1
P7_LANE1_ONLY = 2
P7_STRIPE_ROUND_ROBIN = 3
P7_REPLICATE_0X3 = 4

_KNOWN_CONTROL_COMMANDS = frozenset(
    {
        P7_CONTROL_NONE,
        P7_CONTROL_RUN,
        P7_CONTROL_STOP,
        P7_CONTROL_ABORT,
        P7_CONTROL_CLEAR,
        P7_CONTROL_SHUTDOWN,
    }
)
_TERMINAL_DESCRIPTOR_STATUSES = frozenset(
    {
        P7_DESCRIPTOR_COMPLETE,
        P7_DESCRIPTOR_FAILED,
        P7_DESCRIPTOR_ABORTED,
        P7_DESCRIPTOR_REJECTED,
    }
)
_WORDS = struct.Struct("<64I")
_STATUS_WORD = struct.Struct("<I")
_FIRST_ERROR_HEADER_WORDS = struct.Struct("<48I")


def _require_u32(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an unsigned 32-bit integer")
    if not 0 <= value <= P7_UINT32_MAX:
        raise ValueError(f"{name} is outside uint32")
    return value


def decode_runtime_elapsed_snapshot(
    sequence_before: int,
    low: int,
    high: int,
    sequence_after: int,
    *,
    previous: int = 0,
) -> int:
    """Decode one host-side seqlock snapshot and reject tears/regression.

    This pure helper mirrors the XSDB reader and makes rollover interleavings
    directly testable without connecting to hardware.
    """
    before = _require_u32("runtime elapsed sequence before", sequence_before)
    low_word = _require_u32("runtime elapsed low", low)
    high_word = _require_u32("runtime elapsed high", high)
    after = _require_u32("runtime elapsed sequence after", sequence_after)
    if isinstance(previous, bool) or not isinstance(previous, int) or not 0 <= previous <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("previous runtime elapsed ticks must be uint64")
    if before != after or (before & 1):
        raise ValueError("runtime elapsed snapshot is not protected by one stable even sequence")
    value = low_word | (high_word << 32)
    if value < previous:
        raise ValueError("runtime elapsed snapshot regressed")
    return value


def _ranges_overlap(a_address: int, a_size: int, b_address: int, b_size: int) -> bool:
    return (
        a_size != 0
        and b_size != 0
        and a_address < b_address + b_size
        and b_address < a_address + a_size
    )


def fragment_count_for_length(length: int) -> int:
    """Return the canonical RFAP fragment count, including one empty fragment."""
    if isinstance(length, bool) or not isinstance(length, int):
        raise ValueError("object length must be an integer")
    if not 0 <= length <= P7_MAX_OBJECT_BYTES:
        raise ValueError("object length is outside the P7 limit")
    return 1 if length == 0 else (length + P7_MAX_CHUNK_BYTES - 1) // P7_MAX_CHUNK_BYTES


def descriptor_status_address(slot: int) -> int:
    """Return the address of a slot's publication/status word."""
    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < P7_QUEUE_DEPTH:
        raise ValueError(f"descriptor slot must be in 0..{P7_QUEUE_DEPTH - 1}")
    return P7_DESCRIPTOR_BASE + slot * P7_DESCRIPTOR_BYTES + P7_DESCRIPTOR_STATUS_OFFSET


def pack_ready_publication_word() -> bytes:
    """Return the four-byte write that publishes a fully written descriptor."""
    return _STATUS_WORD.pack(P7_DESCRIPTOR_READY)


def descriptor_ready_publication(slot: int) -> tuple[int, bytes]:
    """Return ``(address, data)`` for a slot's final READY publication write."""
    return descriptor_status_address(slot), pack_ready_publication_word()


def unpack_status_word(raw: int | bytes | bytearray | memoryview) -> int:
    """Decode a status read represented either as a uint32 or four bytes."""
    if isinstance(raw, bool):
        raise ValueError("descriptor status must be uint32 or four bytes")
    if isinstance(raw, int):
        return _require_u32("descriptor status", raw)
    encoded = bytes(raw)
    if len(encoded) != _STATUS_WORD.size:
        raise ValueError("descriptor status read must contain exactly four bytes")
    return _STATUS_WORD.unpack(encoded)[0]


def sha256_words(data: bytes) -> tuple[int, ...]:
    digest = hashlib.sha256(data).digest()
    return tuple(
        int.from_bytes(digest[index : index + 4], "big")
        for index in range(0, 32, 4)
    )


def words_sha256(words: tuple[int, ...] | list[int]) -> str:
    if len(words) != 8:
        raise ValueError("SHA256 word array must contain eight words")
    return b"".join(int(word).to_bytes(4, "big") for word in words).hex()


def unpack_first_error_diagnostic(raw: bytes) -> dict[str, object]:
    """Decode and fail-closed validate one committed P7CD first-error image."""
    if len(raw) != P7_FIRST_ERROR_DIAGNOSTIC_BYTES:
        raise ValueError("first-error diagnostic must contain exactly 320 bytes")
    words = list(_FIRST_ERROR_HEADER_WORDS.unpack(raw[:192]))
    if words[0] != P7_FIRST_ERROR_DIAGNOSTIC_MAGIC:
        raise ValueError("first-error diagnostic commit magic is missing")
    if words[1] != P7_RUNTIME_VERSION:
        raise ValueError("first-error diagnostic version is unsupported")
    stage = words[2]
    error_code = words[3]
    if stage not in P7_FIRST_ERROR_STAGE_NAMES:
        raise ValueError("first-error diagnostic stage is invalid")
    if error_code not in _P7_FIRST_ERROR_ALLOWED_ERRORS[stage]:
        raise ValueError("first-error diagnostic stage/error pair is invalid")
    expected_length = words[8]
    actual_length = words[9]
    first_bad_offset = words[10]
    expected_byte = words[11]
    actual_byte = words[12]
    if expected_length > P7_MAX_OBJECT_BYTES or actual_length > P7_MAX_OBJECT_BYTES:
        raise ValueError("first-error diagnostic length exceeds the P7 object limit")
    max_length = max(expected_length, actual_length)
    if max_length == 0 or first_bad_offset >= max_length:
        raise ValueError("first-error diagnostic mismatch offset is out of range")
    if expected_byte > P7_DIAGNOSTIC_MISSING_BYTE or actual_byte > P7_DIAGNOSTIC_MISSING_BYTE:
        raise ValueError("first-error diagnostic byte value is invalid")
    if (first_bad_offset >= expected_length) != (
        expected_byte == P7_DIAGNOSTIC_MISSING_BYTE
    ):
        raise ValueError("first-error expected-byte sentinel contradicts length")
    if (first_bad_offset >= actual_length) != (
        actual_byte == P7_DIAGNOSTIC_MISSING_BYTE
    ):
        raise ValueError("first-error actual-byte sentinel contradicts length")
    if expected_byte == actual_byte:
        raise ValueError("first-error diagnostic bytes do not describe a mismatch")
    fragment_index = words[6]
    lane_mask = words[7]
    if stage in (9, 10):
        if fragment_index != P7_DIAGNOSTIC_NOT_APPLICABLE or lane_mask != 0:
            raise ValueError("object-level first-error identity is invalid")
    elif fragment_index == P7_DIAGNOSTIC_NOT_APPLICABLE or lane_mask not in (1, 2, 3):
        raise ValueError("fragment-level first-error identity is invalid")
    snapshot_offset = words[17]
    snapshot_length = words[18]
    if (
        snapshot_length == 0
        or snapshot_length > P7_FIRST_ERROR_SNAPSHOT_BYTES
        or snapshot_offset > first_bad_offset
        or snapshot_offset + snapshot_length > max_length
        or not snapshot_offset <= first_bad_offset < snapshot_offset + snapshot_length
    ):
        raise ValueError("first-error diagnostic snapshot geometry is invalid")
    if words[19] != 0 or any(words[36:48]):
        raise ValueError("first-error diagnostic reserved words are nonzero")
    expected_snapshot = raw[192:256]
    actual_snapshot = raw[256:320]
    for index in range(P7_FIRST_ERROR_SNAPSHOT_BYTES):
        source_index = snapshot_offset + index
        if (index >= snapshot_length or source_index >= expected_length) and expected_snapshot[index] != 0:
            raise ValueError("first-error expected snapshot padding is nonzero")
        if (index >= snapshot_length or source_index >= actual_length) and actual_snapshot[index] != 0:
            raise ValueError("first-error actual snapshot padding is nonzero")
    relative_bad = first_bad_offset - snapshot_offset
    if first_bad_offset < expected_length and expected_snapshot[relative_bad] != expected_byte:
        raise ValueError("first-error expected byte disagrees with snapshot")
    if first_bad_offset < actual_length and actual_snapshot[relative_bad] != actual_byte:
        raise ValueError("first-error actual byte disagrees with snapshot")
    expected_sha256 = words_sha256(words[20:28])
    actual_sha256 = words_sha256(words[28:36])
    if snapshot_offset == 0 and snapshot_length >= expected_length:
        expected_full = expected_snapshot[:expected_length]
        if zlib.crc32(expected_full) & P7_UINT32_MAX != words[15]:
            raise ValueError("first-error expected CRC32 disagrees with full snapshot")
        if hashlib.sha256(expected_full).hexdigest() != expected_sha256:
            raise ValueError("first-error expected SHA256 disagrees with full snapshot")
    if snapshot_offset == 0 and snapshot_length >= actual_length:
        actual_full = actual_snapshot[:actual_length]
        if zlib.crc32(actual_full) & P7_UINT32_MAX != words[16]:
            raise ValueError("first-error actual CRC32 disagrees with full snapshot")
        if hashlib.sha256(actual_full).hexdigest() != actual_sha256:
            raise ValueError("first-error actual SHA256 disagrees with full snapshot")
    return {
        "magic": words[0],
        "version": words[1],
        "stage": stage,
        "stage_name": P7_FIRST_ERROR_STAGE_NAMES[stage],
        "error_code": error_code,
        "session_epoch": words[4],
        "object_id": words[5],
        "fragment_index": fragment_index,
        "lane_mask": lane_mask,
        "expected_length": expected_length,
        "actual_length": actual_length,
        "first_bad_offset": first_bad_offset,
        "expected_byte": expected_byte,
        "actual_byte": actual_byte,
        "expected_address": words[13],
        "actual_address": words[14],
        "expected_address_low6": words[13] & 0x3F,
        "actual_address_low6": words[14] & 0x3F,
        "expected_crc32": words[15],
        "actual_crc32": words[16],
        "snapshot_offset": snapshot_offset,
        "snapshot_length": snapshot_length,
        "expected_sha256": expected_sha256,
        "actual_sha256": actual_sha256,
        "expected_snapshot": expected_snapshot[:snapshot_length].hex(),
        "actual_snapshot": actual_snapshot[:snapshot_length].hex(),
        "words": words,
    }


def validate_range(address: int, length: int) -> None:
    _require_u32("address", address)
    if isinstance(length, bool) or not isinstance(length, int):
        raise ValueError("object length must be an integer")
    if address % P7_ALIGNMENT:
        raise ValueError("address is not 64-byte aligned")
    if not 0 <= length <= P7_MAX_OBJECT_BYTES:
        raise ValueError("object length is outside the P7 limit")
    end = address + length
    if address < P7_DDR_BASE or end > P7_DDR_END_EXCLUSIVE:
        raise ValueError("object range is outside validated PS DDR")


@dataclass(slots=True)
class DescriptorRequest:
    session_epoch: int
    object_id: int
    input_address: int
    output_address: int
    data: bytes
    lane_policy: int
    max_retries: int = 3
    unavailable_lane_mask: int = 0
    unavailable_after_fragment: int = 0
    abort_after_fragment: int = P7_UINT32_MAX
    trace_address: int = 0
    trace_capacity: int = 0

    def validate(self) -> None:
        _require_u32("session_epoch", self.session_epoch)
        _require_u32("object_id", self.object_id)
        _require_u32("input_address", self.input_address)
        _require_u32("output_address", self.output_address)
        _require_u32("lane_policy", self.lane_policy)
        _require_u32("max_retries", self.max_retries)
        _require_u32("unavailable_lane_mask", self.unavailable_lane_mask)
        _require_u32("unavailable_after_fragment", self.unavailable_after_fragment)
        _require_u32("abort_after_fragment", self.abort_after_fragment)
        _require_u32("trace_address", self.trace_address)
        _require_u32("trace_capacity", self.trace_capacity)

        object_length = len(self.data)
        validate_range(self.input_address, object_length)
        validate_range(self.output_address, object_length)
        if _ranges_overlap(
            self.input_address,
            object_length,
            self.output_address,
            object_length,
        ):
            raise ValueError("input and output ranges overlap")
        if self.lane_policy not in (
            P7_LANE0_ONLY,
            P7_LANE1_ONLY,
            P7_STRIPE_ROUND_ROBIN,
            P7_REPLICATE_0X3,
        ):
            raise ValueError("lane policy is invalid")
        if self.max_retries > 8:
            raise ValueError("max_retries is outside 0..8")
        if self.unavailable_lane_mask & ~0x3:
            raise ValueError("unavailable lane mask exceeds 0x3")

        if self.trace_capacity:
            fragment_count = fragment_count_for_length(object_length)
            if self.trace_capacity < fragment_count:
                raise ValueError("trace capacity is smaller than fragment count")
            trace_bytes = self.trace_capacity * P7_TRACE_BYTES
            validate_range(self.trace_address, trace_bytes)
            if _ranges_overlap(
                self.trace_address,
                trace_bytes,
                self.input_address,
                object_length,
            ) or _ranges_overlap(
                self.trace_address,
                trace_bytes,
                self.output_address,
                object_length,
            ):
                raise ValueError("trace range overlaps input or output")

    def pack_body(self) -> bytes:
        """Pack a non-published descriptor body whose status remains FREE."""
        self.validate()
        words = [0] * 64
        words[0:16] = [
            P7_DESCRIPTOR_MAGIC,
            P7_RUNTIME_VERSION,
            P7_DESCRIPTOR_TRANSFER,
            P7_DESCRIPTOR_FREE,
            self.session_epoch,
            self.object_id,
            self.input_address,
            self.output_address,
            len(self.data),
            zlib.crc32(self.data) & P7_UINT32_MAX,
            self.lane_policy,
            self.max_retries,
            self.unavailable_lane_mask,
            self.unavailable_after_fragment,
            self.abort_after_fragment,
            self.trace_address,
        ]
        words[16] = self.trace_capacity
        words[24:32] = sha256_words(self.data)
        return _WORDS.pack(*words)

    def pack(self) -> bytes:
        """Compatibility alias for the safe, non-published descriptor body."""
        return self.pack_body()


def unpack_descriptor(raw: bytes) -> dict[str, object]:
    if len(raw) != P7_DESCRIPTOR_BYTES:
        raise ValueError("descriptor must contain exactly 256 bytes")
    words = list(_WORDS.unpack(raw))
    return {
        "magic": words[0],
        "version": words[1],
        "command": words[2],
        "status": words[3],
        "session_epoch": words[4],
        "object_id": words[5],
        "input_address": words[6],
        "output_address": words[7],
        "object_length": words[8],
        "expected_crc32": words[9],
        "lane_policy": words[10],
        "max_retries": words[11],
        "unavailable_lane_mask": words[12],
        "unavailable_after_fragment": words[13],
        "abort_after_fragment": words[14],
        "trace_address": words[15],
        "trace_capacity": words[16],
        "error_code": words[17],
        "bytes_completed": words[18],
        "fragments_total": words[19],
        "fragments_completed": words[20],
        "output_crc32": words[21],
        "fragment_attempts": words[22],
        "fallback_count": words[23],
        "expected_sha256": words_sha256(words[24:32]),
        "input_sha256": words_sha256(words[32:40]),
        "output_sha256": words_sha256(words[40:48]),
        "p6_retry_count": words[48],
        "p6_retry_exhausted": words[49],
        "p6_tx_fail": words[50],
        "p6_crc_bad": words[51],
        "p6_payload_mismatch": words[52],
        "max_txd_high_cycles": words[53],
        "duty_violation_count": words[54],
        "lane0_fragments": words[55],
        "lane1_fragments": words[56],
        "replicated_fragments": words[57],
        "start_ticks": words[58] | (words[59] << 32),
        "end_ticks": words[60] | (words[61] << 32),
        "restart_count": words[62],
        "completion_sequence": words[63],
        "words": words,
    }


def unpack_stable_terminal_descriptor(
    status_before: int | bytes | bytearray | memoryview,
    raw: bytes,
    status_after: int | bytes | bytearray | memoryview,
) -> dict[str, object]:
    """Validate a status/body/status read and decode a stable terminal image."""
    before = unpack_status_word(status_before)
    after = unpack_status_word(status_after)
    result = unpack_descriptor(raw)
    if before != after:
        raise ValueError(
            f"descriptor status changed during snapshot: {before} -> {after}"
        )
    if result["status"] != before:
        raise ValueError(
            f"descriptor body status={result['status']} does not match snapshot={before}"
        )
    if before not in _TERMINAL_DESCRIPTOR_STATUSES:
        raise ValueError(f"descriptor status={before} is not terminal")
    return result


def pack_mailbox(
    *,
    control_command: int = P7_CONTROL_RUN,
    queue_depth: int = P7_QUEUE_DEPTH,
    max_runtime_seconds: int = 1800,
    calibration_window_seconds: int = 300,
    sample_interval_seconds: int = 10,
    scheduling_cutoff_seconds: int = 0,
    admission_guard_seconds: int = 0,
) -> bytes:
    _require_u32("control_command", control_command)
    _require_u32("queue_depth", queue_depth)
    _require_u32("max_runtime_seconds", max_runtime_seconds)
    _require_u32("calibration_window_seconds", calibration_window_seconds)
    _require_u32("sample_interval_seconds", sample_interval_seconds)
    _require_u32("scheduling_cutoff_seconds", scheduling_cutoff_seconds)
    _require_u32("admission_guard_seconds", admission_guard_seconds)
    if control_command not in _KNOWN_CONTROL_COMMANDS:
        raise ValueError("control command is invalid")
    if not 1 <= queue_depth <= P7_QUEUE_DEPTH:
        raise ValueError(f"queue depth must be in 1..{P7_QUEUE_DEPTH}")
    if not 1 <= max_runtime_seconds <= 1800:
        raise ValueError("max runtime must be in 1..1800 seconds")
    if not 0 <= calibration_window_seconds <= max_runtime_seconds:
        raise ValueError("calibration window must fit inside max runtime")
    if not 1 <= sample_interval_seconds <= max_runtime_seconds:
        raise ValueError("sample interval must fit inside max runtime")
    if scheduling_cutoff_seconds == 0:
        if admission_guard_seconds != 0:
            raise ValueError("admission guard requires a nonzero scheduling cutoff")
    elif not (
        1 <= admission_guard_seconds < scheduling_cutoff_seconds < max_runtime_seconds
    ):
        raise ValueError("stationary admission guard/cutoff must fit strictly inside runtime")
    words = [0] * 64
    words[0] = P7_MAILBOX_MAGIC
    words[1] = P7_RUNTIME_VERSION
    words[2] = P7_SERVICE_BOOTING
    words[3] = control_command
    words[4] = queue_depth
    words[25] = max_runtime_seconds
    words[26] = P7_RUNTIME_AUTO_DEADLINE
    words[31] = calibration_window_seconds
    words[32] = sample_interval_seconds
    words[37] = scheduling_cutoff_seconds
    words[38] = admission_guard_seconds
    return _WORDS.pack(*words)


def unpack_mailbox(raw: bytes) -> dict[str, int | list[int]]:
    if len(raw) != P7_MAILBOX_BYTES:
        raise ValueError("mailbox control must contain exactly 256 bytes")
    words = list(_WORDS.unpack(raw))
    return {
        "magic": words[0],
        "version": words[1],
        "service_state": words[2],
        "control_command": words[3],
        "queue_depth": words[4],
        "queue_occupancy": words[5],
        "queue_high_watermark": words[6],
        "backpressure_events": words[7],
        "objects_requested": words[8],
        "objects_completed": words[9],
        "objects_failed": words[10],
        "fragments_completed": words[11],
        "bytes_completed": words[12] | (words[13] << 32),
        "current_session_epoch": words[14],
        "current_object_id": words[15],
        "current_fragment_index": words[16],
        "last_error_code": words[17],
        "shutdown_result": words[18],
        "heartbeat": words[19],
        "stop_count": words[20],
        "abort_count": words[21],
        "restart_count": words[22],
        "completion_sequence": words[23],
        "consumer_hint": words[24],
        "max_runtime_seconds": words[25],
        "runtime_flags": words[26],
        "runtime_start_ticks": words[27] | (words[28] << 32),
        "runtime_elapsed_ticks": words[29] | (words[30] << 32),
        "calibration_window_seconds": words[31],
        "sample_interval_seconds": words[32],
        "last_sample_sequence": words[33],
        "runtime_elapsed_sequence": words[34],
        "runtime_elapsed_request": words[35],
        "runtime_elapsed_ack": words[36],
        "scheduling_cutoff_seconds": words[37],
        "admission_guard_seconds": words[38],
        "failure_snapshot_address": words[39],
        "failure_snapshot_bytes": words[40],
        "failure_snapshot_status": words[41],
        "failure_snapshot_magic_readback": words[42],
        "words": words,
    }


def _preferred_lane(policy: int, fragment_index: int) -> int:
    if policy == P7_LANE0_ONLY:
        return 0x1
    if policy == P7_LANE1_ONLY:
        return 0x2
    if policy == P7_STRIPE_ROUND_ROBIN:
        return 0x1 if fragment_index % 2 == 0 else 0x2
    return 0x3


def _expected_lane_distribution(
    request: DescriptorRequest, fragment_count: int
) -> tuple[int, int, int] | None:
    lane0 = 0
    lane1 = 0
    replicated = 0
    for fragment_index in range(fragment_count):
        unavailable = (
            request.unavailable_lane_mask
            if fragment_index >= request.unavailable_after_fragment
            else 0
        )
        preferred = _preferred_lane(request.lane_policy, fragment_index)
        lane = preferred & ~unavailable & 0x3
        if lane == 0 and preferred == 0x1 and not unavailable & 0x2:
            lane = 0x2
        elif lane == 0 and preferred == 0x2 and not unavailable & 0x1:
            lane = 0x1
        if lane == 0:
            return None
        if lane & 0x1:
            lane0 += 1
        if lane & 0x2:
            lane1 += 1
        if lane == 0x3:
            replicated += 1
    return lane0, lane1, replicated


def validate_completed(
    request: DescriptorRequest,
    raw: bytes,
    output: bytes,
    *,
    expected_completion_sequence: int | None = None,
) -> dict[str, object]:
    """Validate that a COMPLETE descriptor belongs to exactly this request."""
    request.validate()
    result = unpack_descriptor(raw)
    failures: list[str] = []
    data = request.data
    object_length = len(data)
    fragment_count = fragment_count_for_length(object_length)
    expected_crc = zlib.crc32(data) & P7_UINT32_MAX
    expected_sha = hashlib.sha256(data).hexdigest()

    expected_fields = {
        "magic": P7_DESCRIPTOR_MAGIC,
        "version": P7_RUNTIME_VERSION,
        "command": P7_DESCRIPTOR_TRANSFER,
        "session_epoch": request.session_epoch,
        "object_id": request.object_id,
        "input_address": request.input_address,
        "output_address": request.output_address,
        "object_length": object_length,
        "expected_crc32": expected_crc,
        "lane_policy": request.lane_policy,
        "max_retries": request.max_retries,
        "unavailable_lane_mask": request.unavailable_lane_mask,
        "unavailable_after_fragment": request.unavailable_after_fragment,
        "abort_after_fragment": request.abort_after_fragment,
        "trace_address": request.trace_address,
        "trace_capacity": request.trace_capacity,
    }
    for key, expected in expected_fields.items():
        if result[key] != expected:
            failures.append(f"{key}={result[key]} expected={expected}")

    if result["status"] != P7_DESCRIPTOR_COMPLETE:
        failures.append(f"status={result['status']}")
    if result["error_code"] != 0:
        failures.append(f"error_code={result['error_code']}")
    if result["expected_sha256"] != expected_sha:
        failures.append("expected SHA256 does not match request")
    if result["bytes_completed"] != object_length or len(output) != object_length:
        failures.append("length mismatch")
    if result["fragments_total"] != fragment_count:
        failures.append(
            f"fragments_total={result['fragments_total']} expected={fragment_count}"
        )
    if result["fragments_completed"] != fragment_count:
        failures.append(
            f"fragments_completed={result['fragments_completed']} expected={fragment_count}"
        )
    attempts = int(result["fragment_attempts"])
    if attempts != fragment_count:
        failures.append(
            f"fragment_attempts={attempts} expected exactly one P7 submission per fragment={fragment_count}"
        )
    if int(result["p6_retry_count"]) > fragment_count * request.max_retries:
        failures.append(
            f"p6_retry_count={result['p6_retry_count']} exceeds per-fragment acceptance cap "
            f"{request.max_retries} across {fragment_count} fragments"
        )

    completion_sequence = int(result["completion_sequence"])
    if completion_sequence == 0:
        failures.append("completion_sequence=0")
    if expected_completion_sequence is not None:
        _require_u32("expected_completion_sequence", expected_completion_sequence)
        if completion_sequence != expected_completion_sequence:
            failures.append(
                f"completion_sequence={completion_sequence} "
                f"expected={expected_completion_sequence}"
            )

    if result["output_crc32"] != expected_crc:
        failures.append("descriptor CRC32 mismatch")
    if zlib.crc32(output) & P7_UINT32_MAX != expected_crc:
        failures.append("host output CRC32 mismatch")
    if output != data:
        failures.append("byte-for-byte output mismatch")
    if result["input_sha256"] != expected_sha or result["output_sha256"] != expected_sha:
        failures.append("descriptor SHA256 mismatch")
    if hashlib.sha256(output).hexdigest() != expected_sha:
        failures.append("host output SHA256 mismatch")

    for key in (
        "p6_retry_exhausted",
        "p6_tx_fail",
        "p6_crc_bad",
        "p6_payload_mismatch",
        "duty_violation_count",
    ):
        if result[key] != 0:
            failures.append(f"{key}={result[key]}")
    if int(result["max_txd_high_cycles"]) > P7_KNOWN_GOOD_TXD_HIGH_CYCLES:
        failures.append(
            f"max_txd_high_cycles={result['max_txd_high_cycles']} "
            f"> {P7_KNOWN_GOOD_TXD_HIGH_CYCLES}"
        )

    expected_distribution = _expected_lane_distribution(request, fragment_count)
    if expected_distribution is None:
        failures.append("lane policy has no usable lane for a completed object")
    else:
        for key, expected in zip(
            ("lane0_fragments", "lane1_fragments", "replicated_fragments"),
            expected_distribution,
        ):
            if result[key] != expected:
                failures.append(f"{key}={result[key]} expected={expected}")

    return {"passed": not failures, "failures": failures, "descriptor": result}
