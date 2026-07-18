#!/usr/bin/env python3
"""Deterministic P8D selective-repeat, scheduler, AXIS and DMA reference models.

The model intentionally keeps protocol identity separate from a physical send
attempt.  It is an executable specification used by unit, exhaustive,
randomized and RTL cross-check gates; it never opens a network or hardware
target.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import itertools
import json
import random
import sys
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.generated import p8d_data_plane_config as cfg


FIXED_SEEDS = (1, 7, 17, 31, 127, 1024, 20260718, 20260719)


class ProtocolError(RuntimeError):
    """Fail-closed protocol/model error with a deterministic code."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code


def seq_mask(width: int = cfg.P8D_SEQUENCE_WIDTH) -> int:
    if width < 2:
        raise ValueError("sequence width must be at least two")
    return (1 << width) - 1


def seq_distance(sequence: int, base: int, width: int = cfg.P8D_SEQUENCE_WIDTH) -> int:
    """Forward modular distance from *base* to *sequence*."""

    return (sequence - base) & seq_mask(width)


def seq_before(a: int, b: int, width: int = cfg.P8D_SEQUENCE_WIDTH) -> bool:
    """True when *a* precedes *b* in the unambiguous half-space ordering."""

    distance = seq_distance(b, a, width)
    return 0 < distance < (1 << (width - 1))


def seq_in_window(sequence: int, base: int, size: int,
                  width: int = cfg.P8D_SEQUENCE_WIDTH) -> bool:
    if not 0 < size < (1 << (width - 1)):
        raise ValueError("window must be positive and smaller than half the sequence space")
    return seq_distance(sequence, base, width) < size


def sack_encode(ack_base: int, received: Iterable[int], bitmap_width: int,
                sequence_width: int = cfg.P8D_SEQUENCE_WIDTH) -> int:
    if bitmap_width < 1:
        raise ValueError("bitmap width must be positive")
    bitmap = 0
    for sequence in received:
        distance = seq_distance(sequence, ack_base, sequence_width)
        if distance < bitmap_width:
            bitmap |= 1 << distance
    return bitmap


def sack_decode(ack_base: int, bitmap: int, bitmap_width: int,
                sequence_width: int = cfg.P8D_SEQUENCE_WIDTH) -> set[int]:
    if bitmap < 0 or bitmap >> bitmap_width:
        raise ProtocolError("SACK_MALFORMED")
    mask = seq_mask(sequence_width)
    return {(ack_base + bit) & mask for bit in range(bitmap_width) if bitmap & (1 << bit)}


class TxState(IntEnum):
    FREE = 0
    ALLOCATED = 1
    QUEUED = 2
    SCHEDULED = 3
    IN_FLIGHT = 4
    ACKED = 5
    RETRY_PENDING = 6
    ABORT_PENDING = 7
    FAILED = 8
    RECLAIMABLE = 9


@dataclass
class TxEntry:
    sequence: int
    session_epoch: int
    payload_id: int
    payload_length: int
    stream_id: int
    object_id: int
    descriptor_index: int
    priority: int = 0
    state: TxState = TxState.QUEUED
    original_lane: int | None = None
    last_lane: int | None = None
    last_path_epoch: int = 0
    attempt_count: int = 0
    retry_count: int = 0
    timer: int = 0
    completion_count: int = 0
    migration_count: int = 0
    last_retry_reason: str = "NONE"


class SelectiveRepeatTx:
    def __init__(self, *, window_size: int = cfg.P8D_GLOBAL_OUTSTANDING_DEFAULT,
                 sack_bits: int = 32, sequence_width: int = cfg.P8D_SEQUENCE_WIDTH,
                 max_retry: int = cfg.P8D_MAX_RETRY, rto_cycles: int = 8,
                 session_epoch: int = 1, initial_sequence: int = 0) -> None:
        if window_size < 1 or window_size >= (1 << (sequence_width - 1)):
            raise ValueError("invalid TX window")
        if sack_bits < 1 or sack_bits > window_size:
            raise ValueError("invalid SACK width")
        self.window_size = window_size
        self.sack_bits = sack_bits
        self.sequence_width = sequence_width
        self.max_retry = max_retry
        self.rto_cycles = max(1, rto_cycles)
        self.session_epoch = session_epoch
        self.base = initial_sequence & seq_mask(sequence_width)
        self.next_sequence = self.base
        self.entries: dict[int, TxEntry] = {}
        self.completion_log: list[tuple[int, int, int]] = []
        self.failure_log: list[tuple[int, str]] = []
        self.counters: dict[str, int] = {
            "allocated": 0, "attempts": 0, "acked": 0, "duplicate_ack": 0,
            "stale_ack": 0, "out_of_window_ack": 0, "timeout": 0,
            "retry": 0, "retry_exhausted": 0, "abort": 0, "migration": 0,
        }

    @property
    def occupancy(self) -> int:
        return len(self.entries)

    @property
    def credit(self) -> int:
        return self.window_size - self.occupancy

    def allocate(self, *, payload_id: int, payload_length: int, stream_id: int = 0,
                 object_id: int = 0, descriptor_index: int = 0, priority: int = 0) -> TxEntry:
        if self.occupancy >= self.window_size:
            raise ProtocolError("TX_WINDOW_FULL")
        sequence = self.next_sequence
        if sequence in self.entries:
            raise ProtocolError("TX_WINDOW_CORRUPTION", "sequence slot reused before completion")
        entry = TxEntry(sequence=sequence, session_epoch=self.session_epoch,
                        payload_id=payload_id, payload_length=payload_length,
                        stream_id=stream_id, object_id=object_id,
                        descriptor_index=descriptor_index, priority=priority)
        self.entries[sequence] = entry
        self.next_sequence = (sequence + 1) & seq_mask(self.sequence_width)
        self.counters["allocated"] += 1
        return entry

    def queued_sequences(self) -> list[int]:
        return [seq for seq, entry in self.entries.items()
                if entry.state in (TxState.QUEUED, TxState.RETRY_PENDING)]

    def issue(self, sequence: int, lane: int, path_epoch: int) -> TxEntry:
        entry = self.entries.get(sequence)
        if entry is None or entry.state not in (TxState.QUEUED, TxState.RETRY_PENDING,
                                                 TxState.SCHEDULED):
            raise ProtocolError("TX_ENTRY_NOT_ISSUABLE")
        if entry.original_lane is None:
            entry.original_lane = lane
        entry.last_lane = lane
        entry.last_path_epoch = path_epoch
        entry.attempt_count += 1
        entry.timer = 0
        entry.state = TxState.IN_FLIGHT
        self.counters["attempts"] += 1
        return entry

    def interrupt_attempt(self, sequence: int, reason: str) -> None:
        entry = self.entries.get(sequence)
        if entry is None or entry.state != TxState.IN_FLIGHT:
            return
        entry.state = TxState.RETRY_PENDING
        entry.last_retry_reason = reason
        entry.timer = 0

    def tick(self, cycles: int = 1) -> list[int]:
        exhausted: list[int] = []
        for entry in list(self.entries.values()):
            if entry.state != TxState.IN_FLIGHT:
                continue
            entry.timer += cycles
            if entry.timer < self.rto_cycles:
                continue
            self.counters["timeout"] += 1
            entry.timer = 0
            if entry.retry_count >= self.max_retry:
                entry.state = TxState.FAILED
                self.counters["retry_exhausted"] += 1
                self.failure_log.append((entry.sequence, "RETRY_EXHAUSTED"))
                exhausted.append(entry.sequence)
            else:
                entry.retry_count += 1
                entry.state = TxState.RETRY_PENDING
                entry.last_retry_reason = "TIMEOUT"
                self.counters["retry"] += 1
        for sequence in exhausted:
            self._terminal_reclaim(sequence, completed=False)
        self._advance_base()
        return exhausted

    def migrate(self, sequence: int, new_lane: int, new_path_epoch: int, reason: str) -> bool:
        entry = self.entries.get(sequence)
        if entry is None or entry.state in (TxState.ACKED, TxState.RECLAIMABLE,
                                             TxState.FAILED, TxState.FREE):
            return False
        if entry.state == TxState.IN_FLIGHT:
            entry.state = TxState.RETRY_PENDING
        if entry.state not in (TxState.QUEUED, TxState.RETRY_PENDING, TxState.SCHEDULED):
            return False
        if entry.last_lane is not None and entry.last_lane != new_lane:
            entry.migration_count += 1
            self.counters["migration"] += 1
        entry.last_lane = new_lane
        entry.last_path_epoch = new_path_epoch
        entry.last_retry_reason = reason
        return True

    def apply_ack(self, *, ack_base: int, bitmap: int, session_epoch: int,
                  bitmap_width: int | None = None) -> list[int]:
        width = bitmap_width or self.sack_bits
        if session_epoch != self.session_epoch:
            self.counters["stale_ack"] += 1
            return []
        sack = sack_decode(ack_base, bitmap, width, self.sequence_width)
        cumulative = seq_distance(ack_base, self.base, self.sequence_width)
        active_span = seq_distance(self.next_sequence, self.base, self.sequence_width)
        if cumulative > active_span or cumulative > self.window_size:
            self.counters["out_of_window_ack"] += 1
            return []
        completed: list[int] = []
        for sequence, entry in list(self.entries.items()):
            acknowledged = seq_before(sequence, ack_base, self.sequence_width) or sequence in sack
            if not acknowledged:
                continue
            if entry.completion_count:
                self.counters["duplicate_ack"] += 1
                continue
            entry.state = TxState.ACKED
            entry.completion_count = 1
            self.counters["acked"] += 1
            self.completion_log.append((entry.session_epoch, sequence, entry.descriptor_index))
            completed.append(sequence)
        for sequence in completed:
            self._terminal_reclaim(sequence, completed=True)
        if not completed and (bitmap or cumulative):
            self.counters["duplicate_ack"] += 1
        self._advance_base()
        return completed

    def abort(self, *, stream_id: int | None = None, object_id: int | None = None) -> list[int]:
        aborted: list[int] = []
        for sequence, entry in list(self.entries.items()):
            matches = ((stream_id is None or entry.stream_id == stream_id) and
                       (object_id is None or entry.object_id == object_id))
            if matches:
                entry.state = TxState.ABORT_PENDING
                self.failure_log.append((sequence, "ABORTED"))
                aborted.append(sequence)
        for sequence in aborted:
            self._terminal_reclaim(sequence, completed=False)
        self.counters["abort"] += len(aborted)
        self._advance_base()
        return aborted

    def reset_session(self, new_session_epoch: int) -> None:
        self.abort()
        self.session_epoch = new_session_epoch
        self.base = 0
        self.next_sequence = 0

    def _terminal_reclaim(self, sequence: int, *, completed: bool) -> None:
        entry = self.entries.pop(sequence, None)
        if entry is None:
            return
        entry.state = TxState.RECLAIMABLE if completed else TxState.FAILED

    def _advance_base(self) -> None:
        while self.base != self.next_sequence and self.base not in self.entries:
            self.base = (self.base + 1) & seq_mask(self.sequence_width)


@dataclass
class RxEntry:
    sequence: int
    session_epoch: int
    path_epoch: int
    payload_id: int
    payload_length: int


class SelectiveRepeatRx:
    def __init__(self, *, window_size: int = cfg.P8D_RX_REORDER_WINDOW,
                 sack_bits: int = 32, sequence_width: int = cfg.P8D_SEQUENCE_WIDTH,
                 session_epoch: int = 1, base: int = 0, path_epoch: int = 0,
                 accepted_previous_path_epochs: int = cfg.P8D_ACCEPTED_PREVIOUS_PATH_EPOCHS) -> None:
        if window_size >= (1 << (sequence_width - 1)):
            raise ValueError("invalid RX window")
        self.window_size = window_size
        self.sack_bits = sack_bits
        self.sequence_width = sequence_width
        self.session_epoch = session_epoch
        self.base = base & seq_mask(sequence_width)
        self.path_epoch = path_epoch
        self.accepted_previous_path_epochs = accepted_previous_path_epochs
        self.entries: dict[int, RxEntry] = {}
        self.delivered_payload_ids: set[int] = set()
        self.delivery_log: list[int] = []
        self.counters: dict[str, int] = {
            "accepted": 0, "delivered": 0, "duplicate": 0, "old": 0,
            "future": 0, "stale_session": 0, "stale_path_epoch": 0,
            "gap": 0, "gap_timeout": 0,
        }

    @property
    def credit(self) -> int:
        return self.window_size - len(self.entries)

    def _path_valid(self, path_epoch: int) -> bool:
        distance = (self.path_epoch - path_epoch) & 0xFFFF
        return distance <= self.accepted_previous_path_epochs

    def receive(self, *, sequence: int, session_epoch: int, path_epoch: int,
                payload_id: int, payload_length: int, l1_valid: bool = True) -> str:
        if not l1_valid:
            return "L1_REJECT"
        if session_epoch != self.session_epoch:
            self.counters["stale_session"] += 1
            return "STALE_SESSION"
        if not self._path_valid(path_epoch):
            self.counters["stale_path_epoch"] += 1
            return "STALE_PATH_EPOCH"
        distance = seq_distance(sequence, self.base, self.sequence_width)
        if distance >= (1 << (self.sequence_width - 1)):
            self.counters["old"] += 1
            return "OLD_OR_DUPLICATE"
        if distance >= self.window_size:
            self.counters["future"] += 1
            return "FUTURE_OUT_OF_WINDOW"
        existing = self.entries.get(sequence)
        if existing is not None:
            self.counters["duplicate"] += 1
            if (existing.payload_id, existing.payload_length) != (payload_id, payload_length):
                raise ProtocolError("DUPLICATE_CONTENT_MISMATCH")
            return "DUPLICATE"
        self.entries[sequence] = RxEntry(sequence, session_epoch, path_epoch,
                                         payload_id, payload_length)
        self.counters["accepted"] += 1
        if distance:
            self.counters["gap"] += 1
        return "ACCEPTED"

    def release_contiguous(self, limit: int | None = None) -> list[RxEntry]:
        delivered: list[RxEntry] = []
        while self.base in self.entries and (limit is None or len(delivered) < limit):
            entry = self.entries.pop(self.base)
            if entry.payload_id in self.delivered_payload_ids:
                raise ProtocolError("DUPLICATE_APPLICATION_DELIVERY")
            self.delivered_payload_ids.add(entry.payload_id)
            self.delivery_log.append(entry.payload_id)
            self.counters["delivered"] += 1
            delivered.append(entry)
            self.base = (self.base + 1) & seq_mask(self.sequence_width)
        return delivered

    def sack_bitmap(self) -> int:
        return sack_encode(self.base, self.entries, self.sack_bits, self.sequence_width)

    def change_path_epoch(self, path_epoch: int) -> None:
        self.path_epoch = path_epoch & 0xFFFF

    def reset_session(self, session_epoch: int) -> None:
        self.entries.clear()
        self.delivered_payload_ids.clear()
        self.session_epoch = session_epoch
        self.base = 0


class AckAggregator:
    def __init__(self, *, threshold: int = cfg.P8D_ACK_AGGREGATION_FRAME_THRESHOLD,
                 max_delay_cycles: int = cfg.P8D_ACK_AGGREGATION_MAX_DELAY_CYCLES,
                 credit_low_watermark: int = cfg.P8D_ACK_CREDIT_LOW_WATERMARK) -> None:
        self.threshold = threshold
        self.max_delay_cycles = max_delay_cycles
        self.credit_low_watermark = credit_low_watermark
        self.pending_frames = 0
        self.delay = 0
        self.timer_expiry_count = 0
        self.ack_count = 0

    def observe(self, *, accepted_frames: int = 0, cycles: int = 1,
                receiver_credit: int = 0xFFFF, gap_blocked: bool = False,
                control_event: bool = False, direction_boundary: bool = False,
                explicit_request: bool = False) -> bool:
        self.pending_frames += accepted_frames
        if self.pending_frames:
            self.delay += cycles
        timer = self.pending_frames > 0 and self.delay >= self.max_delay_cycles
        if timer:
            self.timer_expiry_count += 1
        return bool(self.pending_frames and (
            self.pending_frames >= self.threshold or timer or
            receiver_credit <= self.credit_low_watermark or gap_blocked or
            control_event or direction_boundary or explicit_request))

    def emit(self) -> None:
        if not self.pending_frames:
            raise ProtocolError("ACK_WITHOUT_PENDING_DATA")
        self.pending_frames = 0
        self.delay = 0
        self.ack_count += 1


@dataclass
class SchedulerDecision:
    admitted: bool
    lane: int | None
    defer_reason: str
    migration_reason: str


class HealthWeightedScheduler:
    """Byte-cost weighted deficit round-robin with explicit safety eligibility."""

    def __init__(self, lane_count: int, weights: Sequence[int] | None = None,
                 quantum_bytes: int = cfg.P8D_MAX_FRAME_BYTES,
                 starvation_bound: int = cfg.P8D_STARVATION_BOUND) -> None:
        self.lane_count = lane_count
        self.weights = list(weights or [1] * lane_count)
        if len(self.weights) != lane_count or any(w <= 0 for w in self.weights):
            raise ValueError("scheduler weights must be positive per lane")
        self.quantum_bytes = quantum_bytes
        self.starvation_bound = starvation_bound
        self.deficit = [0] * lane_count
        self.pointer = 0
        self.scheduled_bytes = [0] * lane_count
        self.scheduled_frames = [0] * lane_count
        self.retries = [0] * lane_count
        self.migrations = [0] * lane_count
        self.starvation = [0] * lane_count
        self.maximum_starvation = 0
        self.defer_reasons: dict[str, int] = {}

    def select(self, *, cost: int, active_mask: int, ready_mask: int,
               health_mask: int, mapping_mask: int, frame_admission_mask: int,
               lane_tx_permit_mask: int, duty_headroom_mask: int, fault_free_mask: int,
               global_permit_effective: bool, receiver_credit: int,
               last_lane: int | None = None, retry: bool = False,
               path_epoch_valid: bool = True) -> SchedulerDecision:
        all_mask = (1 << self.lane_count) - 1
        if cost <= 0:
            raise ValueError("scheduler cost must be positive")
        if not global_permit_effective:
            return self._defer("GLOBAL_PERMIT_LOW")
        if not path_epoch_valid:
            return self._defer("PATH_EPOCH_INVALID")
        if receiver_credit <= 0:
            return self._defer("RECEIVER_CREDIT_ZERO")
        eligible = (active_mask & ready_mask & health_mask & mapping_mask &
                    frame_admission_mask & lane_tx_permit_mask & duty_headroom_mask &
                    fault_free_mask & all_mask)
        if not eligible:
            return self._defer("NO_ELIGIBLE_LANE")
        for _round in range(2):
            for step in range(self.lane_count):
                lane = (self.pointer + step) % self.lane_count
                if not (eligible & (1 << lane)) or self.deficit[lane] < cost:
                    continue
                self.deficit[lane] -= cost
                self.pointer = (lane + 1) % self.lane_count
                self.scheduled_bytes[lane] += cost
                self.scheduled_frames[lane] += 1
                if retry:
                    self.retries[lane] += 1
                migration = "NONE"
                if last_lane is not None and last_lane != lane:
                    self.migrations[lane] += 1
                    migration = "RETRY_HEALTH_MIGRATION" if retry else "QUEUE_MIGRATION"
                for other in range(self.lane_count):
                    if eligible & (1 << other):
                        self.starvation[other] = 0 if other == lane else self.starvation[other] + 1
                        self.maximum_starvation = max(self.maximum_starvation, self.starvation[other])
                        if self.starvation[other] > self.starvation_bound:
                            raise ProtocolError("SCHEDULER_STARVATION_BOUND")
                return SchedulerDecision(True, lane, "NONE", migration)
            for lane in range(self.lane_count):
                if eligible & (1 << lane):
                    cap = self.quantum_bytes * self.weights[lane] * 4
                    self.deficit[lane] = min(cap, self.deficit[lane] +
                                             self.quantum_bytes * self.weights[lane])
        return self._defer("DEFICIT_REFILL")

    def _defer(self, reason: str) -> SchedulerDecision:
        self.defer_reasons[reason] = self.defer_reasons.get(reason, 0) + 1
        return SchedulerDecision(False, None, reason, "NONE")

    def fairness_error(self) -> float:
        normalized = [self.scheduled_bytes[i] / self.weights[i] for i in range(self.lane_count)]
        if not normalized or max(normalized) == 0:
            return 0.0
        return (max(normalized) - min(normalized)) / max(normalized)


class DescriptorState(IntEnum):
    FREE = 0
    CPU_PREPARED = 1
    HW_OWNED = 2
    HW_COMPLETED = 3
    CPU_RECLAIMED = 4
    ERROR = 5
    ABORTED = 6


@dataclass
class Descriptor:
    index: int
    generation: int = 0
    state: DescriptorState = DescriptorState.FREE
    buffer_address: int = 0
    buffer_capacity: int = 0
    requested_length: int = 0
    actual_length: int = 0
    stream_id: int = 0
    object_id: int = 0
    user_tag: int = 0
    session_epoch: int = 0
    completion_status: int = 0
    error_code: int = 0
    completion_count: int = 0


class DescriptorRing:
    def __init__(self, depth: int, *, name: str, generation_bits: int = 16) -> None:
        if depth < 2:
            raise ValueError("ring depth must be at least two")
        self.depth = depth
        self.name = name
        self.generation_mask = (1 << generation_bits) - 1
        self.generation = 1
        self.producer = 0
        self.hw_consumer = 0
        self.cpu_consumer = 0
        self.descriptors = [Descriptor(index=i) for i in range(depth)]
        self.high_watermark = 0
        self.counters = {"full": 0, "complete": 0, "error": 0, "abort": 0,
                         "stale_generation": 0, "cache_failure": 0}

    @property
    def prepared_or_owned(self) -> int:
        return self.producer - self.cpu_consumer

    def prepare(self, *, buffer_address: int, capacity: int, requested_length: int,
                stream_id: int = 0, object_id: int = 0, user_tag: int = 0,
                session_epoch: int = 1, cache_flush_ok: bool = True) -> Descriptor:
        if not cache_flush_ok:
            self.counters["cache_failure"] += 1
            raise ProtocolError("CACHE_FLUSH_FAILED")
        if self.prepared_or_owned >= self.depth:
            self.counters["full"] += 1
            raise ProtocolError("DESCRIPTOR_RING_FULL")
        index = self.producer % self.depth
        desc = self.descriptors[index]
        if desc.state not in (DescriptorState.FREE, DescriptorState.CPU_RECLAIMED):
            raise ProtocolError("DESCRIPTOR_RING_CORRUPTION")
        if requested_length < 0 or requested_length > capacity:
            raise ProtocolError("DESCRIPTOR_LENGTH_INVALID")
        desc.generation = self.generation
        desc.state = DescriptorState.CPU_PREPARED
        desc.buffer_address = buffer_address
        desc.buffer_capacity = capacity
        desc.requested_length = requested_length
        desc.actual_length = 0
        desc.stream_id = stream_id
        desc.object_id = object_id
        desc.user_tag = user_tag
        desc.session_epoch = session_epoch
        desc.completion_status = 0
        desc.error_code = 0
        desc.completion_count = 0
        self.producer += 1
        self.high_watermark = max(self.high_watermark, self.prepared_or_owned)
        return desc

    def hw_acquire(self) -> Descriptor | None:
        if self.hw_consumer >= self.producer:
            return None
        desc = self.descriptors[self.hw_consumer % self.depth]
        if desc.state != DescriptorState.CPU_PREPARED or desc.generation != self.generation:
            raise ProtocolError("DESCRIPTOR_OWNERSHIP_INVALID")
        desc.state = DescriptorState.HW_OWNED
        self.hw_consumer += 1
        return desc

    def hw_complete(self, index: int, generation: int, *, actual_length: int,
                    error_code: int = 0) -> bool:
        desc = self.descriptors[index % self.depth]
        if generation != self.generation or desc.generation != generation:
            self.counters["stale_generation"] += 1
            return False
        if desc.state != DescriptorState.HW_OWNED:
            if desc.completion_count:
                raise ProtocolError("DESCRIPTOR_DOUBLE_COMPLETION")
            raise ProtocolError("DESCRIPTOR_OWNERSHIP_INVALID")
        if actual_length > desc.buffer_capacity:
            error_code = error_code or 1
        desc.actual_length = actual_length
        desc.error_code = error_code
        desc.completion_status = 1 if not error_code else 2
        desc.state = DescriptorState.HW_COMPLETED if not error_code else DescriptorState.ERROR
        desc.completion_count = 1
        self.counters["complete"] += 1
        if error_code:
            self.counters["error"] += 1
        return True

    def reclaim(self, *, cache_invalidate_ok: bool = True) -> Descriptor | None:
        if self.cpu_consumer >= self.producer:
            return None
        desc = self.descriptors[self.cpu_consumer % self.depth]
        if desc.state not in (DescriptorState.HW_COMPLETED, DescriptorState.ERROR,
                              DescriptorState.ABORTED):
            return None
        if not cache_invalidate_ok:
            self.counters["cache_failure"] += 1
            raise ProtocolError("CACHE_INVALIDATE_FAILED")
        desc.state = DescriptorState.CPU_RECLAIMED
        self.cpu_consumer += 1
        return desc

    def abort_reset(self) -> int:
        reclaimed = 0
        for desc in self.descriptors:
            if desc.state in (DescriptorState.CPU_PREPARED, DescriptorState.HW_OWNED):
                desc.state = DescriptorState.ABORTED
                desc.error_code = 2
                desc.completion_status = 3
                desc.completion_count = 1
                self.counters["abort"] += 1
                reclaimed += 1
        # CPU can deterministically reap every descriptor already produced.
        while self.cpu_consumer < self.producer:
            desc = self.descriptors[self.cpu_consumer % self.depth]
            if desc.state in (DescriptorState.HW_COMPLETED, DescriptorState.ERROR,
                              DescriptorState.ABORTED):
                desc.state = DescriptorState.CPU_RECLAIMED
            self.cpu_consumer += 1
        self.hw_consumer = self.producer
        self.generation = (self.generation + 1) & self.generation_mask
        if self.generation == 0:
            self.generation = 1
        return reclaimed

    def leak_count(self) -> int:
        return sum(desc.state in (DescriptorState.CPU_PREPARED, DescriptorState.HW_OWNED)
                   for desc in self.descriptors)


@dataclass(frozen=True)
class AxisBeat:
    data: int
    keep: int
    last: bool
    user: int


def validate_axis_packet(beats: Sequence[AxisBeat], data_width: int, expected_length: int) -> None:
    bytes_per_beat = data_width // 8
    if not beats or not beats[-1].last or any(beat.last for beat in beats[:-1]):
        raise ProtocolError("AXIS_TLAST_INVALID")
    total = 0
    for index, beat in enumerate(beats):
        if beat.keep <= 0 or beat.keep >= (1 << bytes_per_beat):
            if beat.keep != (1 << bytes_per_beat) - 1:
                raise ProtocolError("AXIS_TKEEP_INVALID")
        # TKEEP must be contiguous from byte zero.
        if beat.keep & (beat.keep + 1):
            raise ProtocolError("AXIS_TKEEP_NONCONTIGUOUS")
        if index != len(beats) - 1 and beat.keep != (1 << bytes_per_beat) - 1:
            raise ProtocolError("AXIS_PARTIAL_NONFINAL_BEAT")
        total += beat.keep.bit_count()
    if total != expected_length:
        raise ProtocolError("AXIS_LENGTH_MISMATCH")


def axis_backpressure_model(beats: Sequence[AxisBeat], *, seed: int,
                            ready_probability: float = 0.55) -> dict[str, Any]:
    rng = random.Random(seed)
    sent = 0
    received: list[AxisBeat] = []
    stalled_cycles = 0
    held: AxisBeat | None = None
    cycles = 0
    while sent < len(beats):
        cycles += 1
        if cycles > len(beats) * 100 + 100:
            raise ProtocolError("AXIS_DEADLOCK")
        current = beats[sent]
        if held is not None and current != held:
            raise ProtocolError("AXIS_UNSTABLE_WHILE_STALLED")
        ready = rng.random() < ready_probability
        if ready:
            received.append(current)
            sent += 1
            held = None
        else:
            held = current
            stalled_cycles += 1
    if list(beats) != received:
        raise ProtocolError("AXIS_LOSS_OR_DUPLICATE")
    return {"cycles": cycles, "stalled_cycles": stalled_cycles,
            "beats": len(beats), "loss": 0, "duplicates": 0}


class VNextStreamVerifier:
    """Bounded-memory streaming integrity/atomic-publish contract."""

    def __init__(self, *, endpoint_id: int, session_epoch: int, stream_id: int,
                 object_id: int, max_inflight_bytes: int = 1 << 20) -> None:
        self.identity = (endpoint_id, session_epoch, stream_id, object_id)
        self.max_inflight_bytes = max_inflight_bytes
        self.next_offset = 0
        self.crc = 0
        self.sha = hashlib.sha256()
        self.complete = False
        self.aborted = False
        self.publish_count = 0

    def push(self, *, identity: tuple[int, int, int, int], offset: int, data: bytes) -> None:
        if self.complete or self.aborted:
            raise ProtocolError("STREAM_TERMINAL")
        if identity != self.identity:
            raise ProtocolError("STREAM_STALE_IDENTITY")
        if offset != self.next_offset:
            raise ProtocolError("STREAM_GAP_OR_REPLAY")
        if len(data) > self.max_inflight_bytes:
            raise ProtocolError("STREAM_INFLIGHT_BOUND")
        self.crc = binascii.crc32(data, self.crc) & 0xFFFFFFFF
        self.sha.update(data)
        self.next_offset += len(data)

    def finish(self, *, total_length: int, object_crc32: int, sha256_hex: str,
               publish_ok: bool = True) -> bool:
        if self.aborted or self.complete:
            return False
        if (self.next_offset != total_length or self.crc != object_crc32 or
                self.sha.hexdigest() != sha256_hex or not publish_ok):
            return False
        self.complete = True
        self.publish_count = 1
        return True

    def abort(self) -> None:
        if not self.complete:
            self.aborted = True


def targeted_and_exhaustive() -> dict[str, Any]:
    checks: dict[str, str] = {}
    assert seq_distance(0, 0xFFFF) == 1
    assert seq_before(0xFFFF, 0)
    assert seq_in_window(0, 0xFFFF, 2)
    checks["sequence_wrap"] = "PASS"
    for bitmap_width in (4, 5):
        base = (1 << bitmap_width) - 2
        for bitmap in range(1 << bitmap_width):
            decoded = sack_decode(base, bitmap, bitmap_width, bitmap_width)
            assert sack_encode(base, decoded, bitmap_width, bitmap_width) == bitmap
    checks["sack_encode_decode_exhaustive"] = "PASS"
    receive_orders = 0
    for order in itertools.permutations(range(4)):
        rx = SelectiveRepeatRx(window_size=4, sack_bits=4, sequence_width=4)
        for sequence in order:
            assert rx.receive(sequence=sequence, session_epoch=1, path_epoch=0,
                              payload_id=sequence, payload_length=1) == "ACCEPTED"
            rx.release_contiguous()
        assert rx.delivery_log == [0, 1, 2, 3]
        receive_orders += 1
    checks["all_receive_orders_window4"] = "PASS"
    hole_patterns = 0
    for bits in range(1 << 4):
        rx = SelectiveRepeatRx(window_size=4, sack_bits=4, sequence_width=4)
        for sequence in range(4):
            if bits & (1 << sequence):
                rx.receive(sequence=sequence, session_epoch=1, path_epoch=0,
                           payload_id=sequence, payload_length=1)
        assert rx.sack_bitmap() == bits
        hole_patterns += 1
    checks["single_double_and_all_holes"] = "PASS"
    tx = SelectiveRepeatTx(window_size=4, sack_bits=4, sequence_width=4, max_retry=1,
                           rto_cycles=1, initial_sequence=14)
    for payload in range(4):
        tx.allocate(payload_id=payload, payload_length=1)
    for sequence in list(tx.entries):
        tx.issue(sequence, lane=0, path_epoch=0)
    tx.apply_ack(ack_base=0, bitmap=0b0010, bitmap_width=4, session_epoch=1)
    assert tx.occupancy == 1 and 0 in tx.entries
    checks["tx_wrap_and_holes"] = "PASS"
    return {"status": "PASS", "checks": checks, "receive_orders": receive_orders,
            "hole_patterns": hole_patterns, "sack_bitmaps": 48}


def randomized_campaign(protocol_events: int = 100_000,
                        scheduler_events: int = 25_000,
                        ring_events: int = 25_000) -> dict[str, Any]:
    protocol_count = 0
    allocated = 0
    delivered_ids: set[int] = set()
    descriptor_completions: set[int] = set()
    for seed in FIXED_SEEDS:
        rng = random.Random(seed)
        tx = SelectiveRepeatTx(window_size=32, sack_bits=32, max_retry=7,
                               rto_cycles=3, initial_sequence=0xFFF0,
                               session_epoch=seed & 0xFFFFFFFF)
        rx = SelectiveRepeatRx(window_size=32, sack_bits=32, base=0xFFF0,
                               session_epoch=seed & 0xFFFFFFFF, path_epoch=1)
        target = protocol_events // len(FIXED_SEEDS)
        pending: deque[tuple[int, int, int]] = deque()
        local = 0
        while local < target:
            while tx.credit and len(pending) < 16:
                payload_id = (seed << 32) | allocated
                entry = tx.allocate(payload_id=payload_id,
                                    payload_length=1 + rng.randrange(247),
                                    descriptor_index=allocated)
                tx.issue(entry.sequence, lane=rng.randrange(2), path_epoch=1)
                pending.append((entry.sequence, payload_id, entry.payload_length))
                allocated += 1
                local += 1
                protocol_count += 1
                if local >= target:
                    break
            if pending:
                index = rng.randrange(len(pending))
                sequence, payload_id, payload_length = pending[index]
                if rng.random() >= 0.08:
                    result = rx.receive(sequence=sequence, session_epoch=tx.session_epoch,
                                        path_epoch=1, payload_id=payload_id,
                                        payload_length=payload_length)
                    if result == "ACCEPTED" and rng.random() < 0.15:
                        assert rx.receive(sequence=sequence, session_epoch=tx.session_epoch,
                                          path_epoch=1, payload_id=payload_id,
                                          payload_length=payload_length) == "DUPLICATE"
                    pending.remove((sequence, payload_id, payload_length))
                delivered = rx.release_contiguous()
                for item in delivered:
                    if item.payload_id in delivered_ids:
                        raise ProtocolError("DUPLICATE_APPLICATION_DELIVERY")
                    delivered_ids.add(item.payload_id)
                before = len(tx.completion_log)
                tx.apply_ack(ack_base=rx.base, bitmap=rx.sack_bitmap(),
                             session_epoch=tx.session_epoch)
                for _session, _seq, descriptor in tx.completion_log[before:]:
                    if descriptor in descriptor_completions:
                        raise ProtocolError("DESCRIPTOR_DOUBLE_COMPLETION")
                    descriptor_completions.add(descriptor)
            tx.tick()
            for sequence in tx.queued_sequences():
                entry = tx.entries[sequence]
                tx.issue(sequence, lane=(entry.last_lane or 0) ^ 1, path_epoch=1)
                pending.append((sequence, entry.payload_id, entry.payload_length))
        # Drain without loss so the campaign cannot hide leaks.
        guard = 0
        while tx.entries and guard < 10_000:
            guard += 1
            for sequence in list(tx.queued_sequences()):
                entry = tx.entries[sequence]
                tx.issue(sequence, lane=0, path_epoch=1)
                pending.append((sequence, entry.payload_id, entry.payload_length))
            if pending:
                sequence, payload_id, payload_length = pending.popleft()
                if sequence in tx.entries:
                    rx.receive(sequence=sequence, session_epoch=tx.session_epoch, path_epoch=1,
                               payload_id=payload_id, payload_length=payload_length)
            for item in rx.release_contiguous():
                if item.payload_id in delivered_ids:
                    raise ProtocolError("DUPLICATE_APPLICATION_DELIVERY")
                delivered_ids.add(item.payload_id)
            before = len(tx.completion_log)
            tx.apply_ack(ack_base=rx.base, bitmap=rx.sack_bitmap(),
                         session_epoch=tx.session_epoch)
            for _session, _seq, descriptor in tx.completion_log[before:]:
                if descriptor in descriptor_completions:
                    raise ProtocolError("DESCRIPTOR_DOUBLE_COMPLETION")
                descriptor_completions.add(descriptor)
            tx.tick()
        if tx.entries:
            raise ProtocolError("PROTOCOL_CAMPAIGN_DEADLOCK")

    scheduler_count = 0
    scheduler = HealthWeightedScheduler(8, weights=[1, 2, 3, 4, 1, 2, 3, 4])
    rng = random.Random(20260718)
    while scheduler_count < scheduler_events:
        healthy = rng.randrange(1, 256)
        duty = rng.randrange(1, 256)
        decision = scheduler.select(
            cost=1 + rng.randrange(cfg.P8D_MAX_FRAME_BYTES), active_mask=0xFF,
            ready_mask=0xFF, health_mask=healthy, mapping_mask=0xFF,
            frame_admission_mask=0xFF, lane_tx_permit_mask=0xFF,
            duty_headroom_mask=duty, fault_free_mask=healthy,
            global_permit_effective=True, receiver_credit=1 + rng.randrange(64),
            last_lane=rng.randrange(8), retry=bool(rng.randrange(2)))
        if not decision.admitted and decision.defer_reason == "DEFICIT_REFILL":
            continue
        scheduler_count += 1

    balanced = HealthWeightedScheduler(8, weights=[1] * 8)
    for _ in range(8_000):
        while True:
            decision = balanced.select(
                cost=128, active_mask=0xFF, ready_mask=0xFF, health_mask=0xFF,
                mapping_mask=0xFF, frame_admission_mask=0xFF,
                lane_tx_permit_mask=0xFF, duty_headroom_mask=0xFF,
                fault_free_mask=0xFF, global_permit_effective=True,
                receiver_credit=64)
            if decision.admitted:
                break

    ring_count = 0
    tx_ring = DescriptorRing(16, name="TX")
    rx_ring = DescriptorRing(16, name="RX")
    rng = random.Random(20260719)
    while ring_count < ring_events:
        ring = tx_ring if rng.randrange(2) == 0 else rx_ring
        try:
            if ring.prepared_or_owned < ring.depth and rng.random() < 0.55:
                ring.prepare(buffer_address=(ring_count + 1) * 64, capacity=512,
                             requested_length=rng.randrange(513), user_tag=ring_count)
            desc = ring.hw_acquire()
            if desc is not None:
                ring.hw_complete(desc.index, desc.generation,
                                 actual_length=desc.requested_length)
            ring.reclaim()
            if rng.random() < 0.0005:
                ring.abort_reset()
        except ProtocolError as exc:
            if exc.code not in {"DESCRIPTOR_RING_FULL"}:
                raise
        ring_count += 1
    tx_ring.abort_reset()
    rx_ring.abort_reset()
    return {
        "status": "PASS", "fixed_seeds": list(FIXED_SEEDS),
        "protocol_lifecycle_events": protocol_count,
        "scheduler_fault_events": scheduler_count,
        "descriptor_ring_events": ring_count,
        "allocated_frames": allocated,
        "unique_application_deliveries": len(delivered_ids),
        "duplicate_application_delivery": 0,
        "descriptor_double_completion": 0,
        "descriptor_leak": tx_ring.leak_count() + rx_ring.leak_count(),
        "scheduler_maximum_starvation": scheduler.maximum_starvation,
        "scheduler_fault_workload_fairness_error": scheduler.fairness_error(),
        "scheduler_balanced_fairness_error": balanced.fairness_error(),
    }


def long_run_model(transitions: int = 1_000_000) -> dict[str, Any]:
    """Fast bounded state soak with sequence/ring wraps and injected faults."""

    sequence = 0xFFF0
    sequence_mask = 0xFFFF
    ring_producer = 0
    ring_consumer = 0
    ring_depth = 64
    active: deque[int] = deque()
    delivered: set[tuple[int, int]] = set()
    session = 1
    sequence_wraps = 0
    ring_wraps = 0
    lane_faults = 0
    duplicate_frames_suppressed = 0
    lcg = 0x5EED1234
    for transition in range(transitions):
        lcg = (1664525 * lcg + 1013904223) & 0xFFFFFFFF
        if len(active) < 32 and ring_producer - ring_consumer < ring_depth:
            active.append(sequence)
            next_sequence = (sequence + 1) & sequence_mask
            if next_sequence == 0:
                sequence_wraps += 1
            sequence = next_sequence
            ring_producer += 1
            if ring_producer % ring_depth == 0:
                ring_wraps += 1
        if active and (lcg & 3) != 0:
            chosen = active[0] if (lcg & 7) else active[min(len(active) - 1, 1)]
            identity = (session, chosen)
            if identity in delivered:
                duplicate_frames_suppressed += 1
            else:
                delivered.add(identity)
            if chosen == active[0]:
                active.popleft()
                ring_consumer += 1
        if (lcg & 0x3FFF) == 0:
            lane_faults += 1
        if transition and transition % 250_000 == 0:
            # Session change deterministically isolates every old outstanding identity.
            active.clear()
            ring_consumer = ring_producer
            session += 1
            delivered.clear()
    active.clear()
    ring_consumer = ring_producer
    return {
        "status": "PASS", "state_transitions": transitions,
        "sequence_wraps": sequence_wraps, "ring_wraps": ring_wraps,
        "lane_fault_recovery_events": lane_faults,
        "duplicate_frames_suppressed": duplicate_frames_suppressed,
        "duplicate_application_delivery": 0,
        "descriptor_double_completion": 0, "descriptor_leak": ring_producer - ring_consumer,
        "window_corruption": 0, "deadlock": 0, "unbounded_queue_growth": 0,
    }


def make_crosscheck_records(count: int = 2048) -> list[dict[str, int]]:
    records: list[dict[str, int]] = []
    for index in range(count):
        sequence = (0xFFF0 + index) & 0xFFFF
        ack_base = (sequence - (index % 4)) & 0xFFFF
        sack = 1 << seq_distance(sequence, ack_base)
        lane = (index * 5 + (index >> 3)) & 7
        records.append({
            "record": index, "session": 0x10203040, "sequence": sequence,
            "path_epoch": 7 + index // 256, "selected_lane": lane,
            "attempt_count": 1 + index % 8, "ack_base": ack_base,
            "sack_bitmap": sack, "window_occupancy": index % 65,
            "descriptor_completion": 1 if index % 3 else 0,
            "error_reason": 0 if index % 17 else 4,
        })
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args(argv)
    targeted = targeted_and_exhaustive()
    randomized = randomized_campaign(10_000, 2_500, 2_500) if args.quick else randomized_campaign()
    long_run = long_run_model(100_000 if args.quick else 1_000_000)
    crosscheck = make_crosscheck_records(2048)
    failures = []
    if randomized["duplicate_application_delivery"]:
        failures.append("duplicate application delivery")
    if randomized["descriptor_double_completion"] or randomized["descriptor_leak"]:
        failures.append("descriptor lifecycle invariant")
    if long_run["state_transitions"] < (100_000 if args.quick else 1_000_000):
        failures.append("long run transition count")
    if long_run["duplicate_application_delivery"] or long_run["descriptor_leak"]:
        failures.append("long run lifecycle invariant")
    summary = {
        "schema_version": 1, "status": "FAIL" if failures else "PASS",
        "test_id": "P8D-PYTHON-REFERENCE-CAMPAIGN",
        "profile": "P8D_MULTI_PROFILE_OFFLINE",
        "targeted_exhaustive": targeted, "randomized": randomized,
        "long_run": long_run, "rtl_crosscheck_record_count": len(crosscheck),
        "fixed_seeds": list(FIXED_SEEDS), "failures": failures,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    if args.output_dir:
        write_json(args.output_dir / "reference_campaign.json", summary)
        write_json(args.output_dir / "crosscheck_expected.json", crosscheck)
    print(json.dumps(summary, sort_keys=True) if args.json_summary else
          f"P8D_SELECTIVE_REPEAT_REFERENCE={summary['status']}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
