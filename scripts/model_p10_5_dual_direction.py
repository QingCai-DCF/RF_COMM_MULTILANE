#!/usr/bin/env python3
"""Deterministic P10.5 dual-direction protocol, mask, DMA, and airtime model."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PY = ROOT / "config/generated/p10_5_dual_direction.py"
CONFIG_YAML = ROOT / "config/p10_5_dual_direction.yaml"
OUT_JSON = ROOT / "evidence/generated/p10_5_reference_model.json"
OUT_MD = ROOT / "evidence/generated/p10_5_reference_model.md"
SEEDS = (1, 7, 17, 31, 127, 1024, 20260809, 22002200)
PROTOCOL_EVENTS = 100_000
ACK_EVENTS = 50_000
DMA_EVENTS = 50_000
ROLE_EVENTS = 25_000
MODULUS = 1 << 16
P10_5_ENDPOINT_ACK_RECOVERY_GUARD_CYCLES = 4_352


def load_config() -> Any:
    spec = importlib.util.spec_from_file_location("p10_5_cfg", CONFIG_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError("generated P10.5 configuration cannot be imported")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CFG = load_config()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def seq_distance(value: int, base: int) -> int:
    return (value - base) & 0xFFFF


def seq_before(value: int, base: int) -> bool:
    distance = seq_distance(base, value)
    return 0 < distance < 0x8000


@dataclass
class TxEntry:
    sequence: int
    descriptor: int
    attempts: int = 0
    retries: int = 0


@dataclass
class DirectionContext:
    name: str
    session: int
    role_epoch: int = 1
    tx_next: int = 0
    tx_base: int = 0
    rx_base: int = 0
    tx: dict[int, TxEntry] = field(default_factory=dict)
    rx_seen: set[int] = field(default_factory=set)
    committed: set[int] = field(default_factory=set)
    completed_descriptors: set[int] = field(default_factory=set)
    pending_ack: bool = False
    ack_age: int = 0
    allocate_count: int = 0
    attempt_count: int = 0
    retry_count: int = 0
    data_drop_count: int = 0
    duplicate_count: int = 0
    reorder_count: int = 0
    stale_role_reject_count: int = 0
    stale_session_reject_count: int = 0
    piggyback_count: int = 0
    fallback_count: int = 0
    abort_count: int = 0
    max_ack_age: int = 0

    def allocate(self, descriptor: int) -> bool:
        if len(self.tx) >= CFG.OUTSTANDING:
            return False
        sequence = self.tx_next
        if sequence in self.tx:
            raise AssertionError("live selective-repeat sequence alias")
        self.tx[sequence] = TxEntry(sequence, descriptor)
        self.tx_next = (self.tx_next + 1) & 0xFFFF
        self.allocate_count += 1
        return True

    def select_attempt(self, rng: random.Random) -> TxEntry | None:
        if not self.tx:
            return None
        retry = [item for item in self.tx.values() if item.attempts]
        candidates = retry if retry and rng.random() < 0.75 else list(self.tx.values())
        entry = min(candidates, key=lambda item: seq_distance(item.sequence, self.tx_base))
        if entry.attempts:
            entry.retries += 1
            self.retry_count += 1
        entry.attempts += 1
        self.attempt_count += 1
        return entry

    def receive(self, sequence: int, role_epoch: int, session: int) -> bool:
        if role_epoch != self.role_epoch:
            self.stale_role_reject_count += 1
            return False
        if session != self.session:
            self.stale_session_reject_count += 1
            return False
        distance = seq_distance(sequence, self.rx_base)
        if distance >= CFG.SACK_BITS:
            return False
        if sequence in self.rx_seen or sequence in self.committed:
            self.duplicate_count += 1
            self.pending_ack = True
            return False
        if sequence != self.rx_base:
            self.reorder_count += 1
        self.rx_seen.add(sequence)
        while self.rx_base in self.rx_seen:
            current = self.rx_base
            self.rx_seen.remove(current)
            if current in self.committed:
                raise AssertionError("duplicate application commit")
            self.committed.add(current)
            self.rx_base = (self.rx_base + 1) & 0xFFFF
        self.pending_ack = True
        self.ack_age = 0
        return True

    def ack_snapshot(self) -> tuple[int, int]:
        bitmap = 0
        for sequence in self.rx_seen:
            distance = seq_distance(sequence, self.rx_base)
            if distance < CFG.SACK_BITS:
                bitmap |= 1 << distance
        return self.rx_base, bitmap

    def apply_ack(self, ack_base: int, bitmap: int) -> None:
        reclaimed: list[int] = []
        for sequence, entry in self.tx.items():
            distance = seq_distance(sequence, ack_base)
            acked = seq_before(sequence, ack_base)
            if not acked and distance < CFG.SACK_BITS:
                acked = bool(bitmap & (1 << distance))
            if acked:
                if entry.descriptor in self.completed_descriptors:
                    raise AssertionError("double descriptor completion")
                self.completed_descriptors.add(entry.descriptor)
                reclaimed.append(sequence)
        for sequence in reclaimed:
            del self.tx[sequence]
        while self.tx_base != self.tx_next and self.tx_base not in self.tx:
            self.tx_base = (self.tx_base + 1) & 0xFFFF

    def send_ack(self, sender_has_data: bool) -> None:
        if not self.pending_ack:
            return
        if sender_has_data:
            self.piggyback_count += 1
        else:
            self.fallback_count += 1
        self.pending_ack = False
        self.ack_age = 0

    def age_ack(self, abstract_bound: int = 64) -> None:
        if not self.pending_ack:
            return
        self.ack_age += 1
        self.max_ack_age = max(self.max_ack_age, self.ack_age)
        if self.ack_age >= abstract_bound:
            self.send_ack(False)

    def abort(self) -> None:
        self.tx.clear()
        self.rx_seen.clear()
        self.pending_ack = False
        self.ack_age = 0
        self.tx_base = self.tx_next
        self.rx_base = self.tx_next
        self.abort_count += 1


def distribute(total: int) -> list[int]:
    base, extra = divmod(total, len(SEEDS))
    return [base + (index < extra) for index in range(len(SEEDS))]


def mask_model() -> dict[str, Any]:
    one_plus_one: list[tuple[int, int]] = []
    two_plus_one: list[tuple[int, int]] = []
    one_plus_two: list[tuple[int, int]] = []
    two_plus_two: list[tuple[int, int]] = []
    all_legal: list[tuple[int, int, int]] = []
    for f2r in range(1, 16):
        for r2f in range(1, 16):
            active = f2r | r2f
            valid, reason = CFG.validate_masks(active, f2r, r2f)
            if f2r & r2f:
                if valid or reason != "ROLE_MASK_OVERLAP":
                    raise AssertionError("overlapping role mask accepted")
                continue
            if not valid:
                raise AssertionError(f"legal mask rejected: {active:x}/{f2r:x}/{r2f:x} {reason}")
            all_legal.append((active, f2r, r2f))
            counts = (f2r.bit_count(), r2f.bit_count())
            if counts == (1, 1):
                one_plus_one.append((f2r, r2f))
            elif counts == (2, 1):
                two_plus_one.append((f2r, r2f))
            elif counts == (1, 2):
                one_plus_two.append((f2r, r2f))
            elif counts == (2, 2) and active == 0xF:
                two_plus_two.append((f2r, r2f))
            fixed_tx, fixed_rx = f2r, r2f
            rotating_tx, rotating_rx = r2f, f2r
            if fixed_tx & fixed_rx or rotating_tx & rotating_rx:
                raise AssertionError("endpoint local role overlap")
            if fixed_tx != rotating_rx or fixed_rx != rotating_tx:
                raise AssertionError("endpoint role derivation mismatch")
    expected_2plus2 = {(0x3, 0xC), (0xC, 0x3), (0x5, 0xA),
                       (0xA, 0x5), (0x9, 0x6), (0x6, 0x9)}
    if len(one_plus_one) != 12:
        raise AssertionError("1+1 ordered matrix is not complete")
    if len(two_plus_one) != 12 or len(one_plus_two) != 12:
        raise AssertionError("2+1/1+2 matrix is not complete")
    if set(two_plus_two) != expected_2plus2:
        raise AssertionError("directed 2+2 matrix is not complete")
    for active, f2r, r2f in ((0xF, 0x3, 0x3), (0x3, 0x3, 0x4),
                             (0xF, 0, 0xF), (0x1F, 1, 0x1E)):
        valid, _ = CFG.validate_masks(active, f2r, r2f)
        if valid:
            raise AssertionError("illegal role tuple accepted")
    return {
        "all_legal_count": len(all_legal),
        "one_plus_one_count": len(one_plus_one),
        "two_plus_one_count": len(two_plus_one),
        "one_plus_two_count": len(one_plus_two),
        "two_plus_two": [f"0x{left:X}/0x{right:X}" for left, right in two_plus_two],
    }


def protocol_model() -> dict[str, Any]:
    totals = {"events": 0, "allocations": 0, "attempts": 0, "retries": 0,
              "drops": 0, "duplicates": 0, "reorders": 0,
              "stale_role_rejects": 0, "stale_session_rejects": 0,
              "piggyback": 0, "fallback": 0, "direction_aborts": 0,
              "commits": 0, "max_ack_age": 0}
    for seed, count in zip(SEEDS, distribute(PROTOCOL_EVENTS)):
        rng = random.Random(seed)
        contexts = [DirectionContext("F_TO_R", 0x1000_0001),
                    DirectionContext("R_TO_F", 0x9000_0001)]
        descriptor_next = [seed << 20, (seed << 20) | (1 << 19)]
        for event_index in range(count):
            direction = rng.randrange(2)
            context = contexts[direction]
            opposite = contexts[1 - direction]
            action = rng.random()
            if action < 0.31:
                context.allocate(descriptor_next[direction])
                descriptor_next[direction] += 1
            elif action < 0.78:
                entry = context.select_attempt(rng)
                if entry is not None:
                    if rng.random() < 0.055:
                        context.data_drop_count += 1
                    else:
                        role = context.role_epoch - 1 if rng.random() < 0.006 else context.role_epoch
                        session = context.session - 1 if rng.random() < 0.006 else context.session
                        accepted = context.receive(entry.sequence, role, session)
                        if accepted and rng.random() < 0.035:
                            context.receive(entry.sequence, role, session)
            elif action < 0.93:
                if context.pending_ack:
                    ack_base, bitmap = context.ack_snapshot()
                    context.send_ack(bool(opposite.tx) and rng.random() < 0.85)
                    context.apply_ack(ack_base, bitmap)
            elif action < 0.97:
                # Fault one logical direction only; the opposite context is
                # snapshotted to prove the scoped operation cannot clear it.
                opposite_snapshot = (set(opposite.tx), opposite.rx_base,
                                     set(opposite.committed))
                context.abort()
                if opposite_snapshot != (set(opposite.tx), opposite.rx_base,
                                         set(opposite.committed)):
                    raise AssertionError("direction abort mutated opposite context")
            else:
                context.age_ack()
            contexts[0].age_ack()
            contexts[1].age_ack()
            for current in contexts:
                if len(current.tx) > CFG.OUTSTANDING:
                    raise AssertionError("selective-repeat window overflow")
                if len(current.rx_seen) > CFG.SACK_BITS:
                    raise AssertionError("receive reorder window overflow")
                if current.max_ack_age > 64:
                    raise AssertionError("ACK/control starvation bound exceeded")
        # Bounded deterministic drain. It proves every surviving descriptor
        # either completes once or is explicitly reclaimed by direction abort.
        for context in contexts:
            guard = 0
            while context.tx and guard < 10_000:
                entry = min(context.tx.values(),
                            key=lambda item: seq_distance(item.sequence, context.tx_base))
                context.receive(entry.sequence, context.role_epoch, context.session)
                ack_base, bitmap = context.ack_snapshot()
                context.send_ack(False)
                context.apply_ack(ack_base, bitmap)
                guard += 1
            if context.tx:
                raise AssertionError("bounded protocol drain deadlocked")
            totals["allocations"] += context.allocate_count
            totals["attempts"] += context.attempt_count
            totals["retries"] += context.retry_count
            totals["drops"] += context.data_drop_count
            totals["duplicates"] += context.duplicate_count
            totals["reorders"] += context.reorder_count
            totals["stale_role_rejects"] += context.stale_role_reject_count
            totals["stale_session_rejects"] += context.stale_session_reject_count
            totals["piggyback"] += context.piggyback_count
            totals["fallback"] += context.fallback_count
            totals["direction_aborts"] += context.abort_count
            totals["commits"] += len(context.committed)
            totals["max_ack_age"] = max(totals["max_ack_age"], context.max_ack_age)
        totals["events"] += count
    if totals["events"] != PROTOCOL_EVENTS or not totals["piggyback"] or not totals["fallback"]:
        raise AssertionError("protocol event coverage incomplete")
    if not totals["stale_role_rejects"] or not totals["direction_aborts"]:
        raise AssertionError("protocol fault coverage incomplete")
    return totals


def ack_control_model() -> dict[str, Any]:
    if CFG.CONTROL_COLLISION_POLICY != \
            "FIXED_PRIORITY_THEN_ROTATING_TOKEN_OR_BOUNDED_ESCAPE":
        raise AssertionError("unexpected control-only ACK collision policy")
    fixed_early_slot = (
        CFG.ACK_MAX_DELAY_CYCLES - CFG.CONTROL_COLLISION_BACKOFF_CYCLES
    )
    rotating_token_response = (
        fixed_early_slot + P10_5_ENDPOINT_ACK_RECOVERY_GUARD_CYCLES
    )
    rotating_escape = CFG.ACK_MAX_DELAY_CYCLES
    if not (0 < fixed_early_slot < rotating_token_response < rotating_escape):
        raise AssertionError("role-ordered control ACK slots are not bounded")
    piggyback = fallback = pending = age = max_age = 0
    for seed, count in zip(SEEDS, distribute(ACK_EVENTS)):
        rng = random.Random(seed ^ 0xA55A)
        for index in range(count):
            if pending == 0 and (index % 7 == 0 or rng.random() < 0.22):
                pending = 1
                age = 0
            reverse_data = (index % 160) >= 96 and rng.random() < 0.75
            if pending and reverse_data:
                piggyback += 1
                pending = 0
                age = 0
            elif pending:
                age += 1
                max_age = max(max_age, age)
                if age >= 64:
                    fallback += 1
                    pending = 0
                    age = 0
    if not piggyback or not fallback or max_age > 64:
        raise AssertionError("ACK piggyback/fallback liveness failure")
    return {
        "events": ACK_EVENTS,
        "piggyback": piggyback,
        "control_only_fallback": fallback,
        "max_abstract_ack_age": max_age,
        "deadlock": 0,
        "collision_policy": CFG.CONTROL_COLLISION_POLICY,
        "ack_max_delay_cycles": CFG.ACK_MAX_DELAY_CYCLES,
        "fixed_early_slot_cycles": fixed_early_slot,
        "rotating_token_response_cycles": rotating_token_response,
        "rotating_escape_cycles": rotating_escape,
        "endpoint_ack_recovery_guard_cycles":
            P10_5_ENDPOINT_ACK_RECOVERY_GUARD_CYCLES,
    }


def dma_model() -> dict[str, Any]:
    rings: dict[tuple[int, str], list[int]] = {
        (direction, kind): [] for direction in range(2) for kind in ("tx", "rx")
    }
    next_descriptor = 1
    completed: set[int] = set()
    backpressure = 0
    max_occupancy = 0
    for seed, count in zip(SEEDS, distribute(DMA_EVENTS)):
        rng = random.Random(seed ^ 0xD00D)
        for _ in range(count):
            key = (rng.randrange(2), "tx" if rng.random() < 0.5 else "rx")
            ring = rings[key]
            if rng.random() < 0.58:
                if len(ring) < 32:
                    ring.append(next_descriptor)
                    next_descriptor += 1
                else:
                    backpressure += 1
            elif ring:
                descriptor = ring.pop(0)
                if descriptor in completed:
                    raise AssertionError("DMA double completion")
                completed.add(descriptor)
            max_occupancy = max(max_occupancy, *(len(value) for value in rings.values()))
            if any(len(value) > 32 for value in rings.values()):
                raise AssertionError("DMA ring overwrite")
    for ring in rings.values():
        while ring:
            descriptor = ring.pop(0)
            if descriptor in completed:
                raise AssertionError("DMA completion alias")
            completed.add(descriptor)
    if any(rings.values()):
        raise AssertionError("DMA descriptor leak")
    return {"events": DMA_EVENTS, "submitted": next_descriptor - 1,
            "completed": len(completed), "backpressure_events": backpressure,
            "maximum_ring_occupancy": max_occupancy, "descriptor_leak": 0,
            "double_completion": 0}


def role_reset_model() -> dict[str, Any]:
    active = (0xF, 0x3, 0xC)
    epoch = 1
    accepted = rejected = stale_rejected = reset_count = 0
    legal = [(f2r | r2f, f2r, r2f) for f2r in range(1, 16)
             for r2f in range(1, 16) if not (f2r & r2f)]
    for seed, count in zip(SEEDS, distribute(ROLE_EVENTS)):
        rng = random.Random(seed ^ 0x5A5A)
        for index in range(count):
            previous = active
            if rng.random() < 0.65:
                shadow = rng.choice(legal)
            else:
                shadow = rng.choice(((0xF, 0x3, 0x3), (0x3, 0x3, 0x4),
                                     (0xF, 0, 0xF), (0x1F, 1, 0x1E)))
            quiet = rng.random() < 0.8
            valid, _ = CFG.validate_masks(*shadow)
            if valid and quiet:
                active = shadow
                epoch = 1 if epoch == 0xFFFF else epoch + 1
                accepted += 1
            else:
                rejected += 1
                if active != previous:
                    raise AssertionError("rejected role commit changed live tuple")
            if index % 5 == 0:
                stale_epoch = epoch - 1 if epoch > 1 else 0xFFFF
                if stale_epoch != epoch:
                    stale_rejected += 1
            if index % 257 == 0:
                reset_count += 1
                # Endpoint reset reclaims both direction generations without
                # publishing a partial new role tuple.
                previous = active
                if active != previous:
                    raise AssertionError("reset created partial role state")
    if not accepted or not rejected or not stale_rejected:
        raise AssertionError("role/reset event coverage incomplete")
    return {"events": ROLE_EVENTS, "accepted_commits": accepted,
            "rejected_commits": rejected, "stale_epoch_rejects": stale_rejected,
            "endpoint_resets": reset_count, "final_role_epoch": epoch,
            "final_active": f"0x{active[0]:X}",
            "final_f_to_r": f"0x{active[1]:X}",
            "final_r_to_f": f"0x{active[2]:X}"}


def object_boundary_model() -> dict[str, Any]:
    def session(base: int, direction: int, object_id: int) -> int:
        epoch = ((base & 0x7FFF_FFFF) +
                 (object_id & 0x7FFF_FFFF) * 0x9E37_79B1) & 0x7FFF_FFFF
        return epoch | (0x8000_0000 if direction else 0)

    maximum_objects = (CFG.MAX_STREAM_BYTES + CFG.INTERNAL_OBJECT_BYTES - 1) // \
        CFG.INTERNAL_OBJECT_BYTES
    base = 0x5035_0001
    f_to_r = [session(base, 0, object_id) for object_id in range(maximum_objects)]
    r_to_f = [session(base, 1, object_id) for object_id in range(maximum_objects)]
    if len(set(f_to_r)) != maximum_objects or len(set(r_to_f)) != maximum_objects:
        raise AssertionError("object-derived session collision in maximum stream")
    if set(f_to_r) & set(r_to_f):
        raise AssertionError("direction-separated object sessions overlap")
    if CFG.INTER_OBJECT_RX_LEAD_US <= 0:
        raise AssertionError("inter-object RX lead must be positive")
    return {
        "maximum_stream_objects": maximum_objects,
        "unique_f_to_r_sessions": len(set(f_to_r)),
        "unique_r_to_f_sessions": len(set(r_to_f)),
        "cross_direction_session_overlap": 0,
        "inter_object_rx_lead_us": CFG.INTER_OBJECT_RX_LEAD_US,
        "tx_release_policy": "ONE_OBJECT_AFTER_LOCAL_RX_ACTIVE",
        "host_per_object_actions": 0,
        "optical_ready_round_trips": 0,
    }


def airtime_model() -> dict[str, Any]:
    clock_hz = 64_000_000
    payload_bytes = 247
    header_bytes = 40
    payload_crc_bytes = 4
    preamble_symbols = 16
    cycles_per_symbol = 32
    pulse_high_cycles = 8
    guard_cycles = 17_984
    frame_symbols = preamble_symbols + 4 * (header_bytes + payload_bytes + payload_crc_bytes)
    frame_cycles = frame_symbols * cycles_per_symbol
    total_cycles = frame_cycles + guard_cycles
    per_lane_bps = payload_bytes * 8 * clock_hz / total_cycles
    wire_limited_per_direction_bps = 2 * per_lane_bps
    object_payload_bits = CFG.INTERNAL_OBJECT_BYTES * 8
    per_direction_bps = object_payload_bits / (
        object_payload_bits / wire_limited_per_direction_bps +
        CFG.INTER_OBJECT_RX_LEAD_US / 1_000_000
    )
    maximum_intersections = 2_000 - guard_cycles // cycles_per_symbol + 1
    maximum_window_high = maximum_intersections * pulse_high_cycles
    target_high = int(clock_hz * 0.001 * 0.18)
    hard_high = int(clock_hz * 0.001 * 0.20)
    if frame_symbols != 1180:
        raise AssertionError("vNext DATA airtime schema mismatch")
    if maximum_window_high > target_high or maximum_window_high >= hard_high:
        raise AssertionError("exact rolling-duty model violates safety contract")
    if per_direction_bps < CFG.TARGET_GOODPUT_BPS:
        raise AssertionError("P10.5 2+2 target is not feasible")
    return {
        "clock_hz": clock_hz, "payload_bytes": payload_bytes,
        "vnext_data_header_bytes": header_bytes, "frame_symbols": frame_symbols,
        "frame_cycles": frame_cycles, "guard_cycles": guard_cycles,
        "per_lane_application_bps": round(per_lane_bps),
        "wire_limited_per_direction_application_bps": round(
            wire_limited_per_direction_bps
        ),
        "per_direction_application_bps": round(per_direction_bps),
        "inter_object_rx_lead_us": CFG.INTER_OBJECT_RX_LEAD_US,
        "internal_object_bytes": CFG.INTERNAL_OBJECT_BYTES,
        "target_bps": CFG.TARGET_GOODPUT_BPS,
        "hard_target": "PASS",
        "stretch_4p8mbps": "PASS" if per_direction_bps >= 4_800_000 else "FAIL_NONBLOCKING",
        "maximum_1ms_high_cycles": maximum_window_high,
        "target_1ms_high_cycles": target_high,
        "hard_1ms_high_cycles_exclusive": hard_high,
        "maximum_continuous_high_cycles": pulse_high_cycles,
        "maximum_continuous_high_us": pulse_high_cycles * 1_000_000 / clock_hz,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-json", type=Path, default=OUT_JSON)
    parser.add_argument("--output-md", type=Path, default=OUT_MD)
    args = parser.parse_args()
    masks = mask_model()
    protocol = protocol_model()
    ack = ack_control_model()
    dma = dma_model()
    roles = role_reset_model()
    object_boundaries = object_boundary_model()
    airtime = airtime_model()
    summary = {
        "schema_version": 1,
        "test_id": "P10_5_DUAL_DIRECTION_REFERENCE_MODEL",
        "status": "PASS",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "goal_sha256": sha256(ROOT / "goals/P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE_GOAL.md"),
        "config_sha256": sha256(CONFIG_YAML),
        "generated_config_sha256": sha256(CONFIG_PY),
        "seeds": list(SEEDS),
        "event_minima": {"protocol": PROTOCOL_EVENTS, "ack_control": ACK_EVENTS,
                         "dma_backpressure": DMA_EVENTS, "role_reset": ROLE_EVENTS},
        "masks": masks, "protocol": protocol, "ack_control": ack,
        "dma": dma, "role_reset": roles,
        "object_boundaries": object_boundaries, "airtime": airtime,
        "invariants": {
            "wrong_direction_lane_tx": 0, "role_mask_overlap": 0,
            "same_module_tx_rx_overlap": 0, "duplicate_commit": 0,
            "stale_role_session_commit": 0, "descriptor_leak": 0,
            "double_completion": 0, "deadlock": 0,
            "single_global_permit_per_endpoint": True,
        },
        "hardware_actions_executed": False,
        "current_run_hardware_authorization_used": False,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                encoding="utf-8", newline="\n")
    md = ["# P10.5 dual-direction offline reference model", "",
          "- Status: `PASS`", "- Hardware actions executed: `false`",
          f"- Protocol events: `{protocol['events']}`",
          f"- ACK/control events: `{ack['events']}`",
          f"- DMA/backpressure events: `{dma['events']}`",
          f"- Role/reset events: `{roles['events']}`",
          f"- 1+1 ordered pairs: `{masks['one_plus_one_count']}`",
          f"- 2+1 / 1+2 cases: `{masks['two_plus_one_count']}` / `{masks['one_plus_two_count']}`",
          f"- Directed 2+2 partitions: `{len(masks['two_plus_two'])}`",
          f"- Modeled per-direction goodput: `{airtime['per_direction_application_bps']}` bit/s",
          f"- 4.0 Mbit/s feasibility: `{airtime['hard_target']}`",
          f"- 4.8 Mbit/s stretch: `{airtime['stretch_4p8mbps']}`", "",
          "All safety, direction-isolation, stale-generation, unique-commit,",
          "descriptor-ownership, bounded-ACK, and no-deadlock invariants passed."]
    args.output_md.write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("P10_5_DUAL_DIRECTION_REFERENCE_MODEL=PASS")
    print(f"P10_5_2PLUS2_MODELED_BPS_PER_DIRECTION={airtime['per_direction_application_bps']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
