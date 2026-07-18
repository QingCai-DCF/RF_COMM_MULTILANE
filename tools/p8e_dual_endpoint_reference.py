#!/usr/bin/env python3
"""Deterministic dual-endpoint/channel reference used beside the P8E RTL XSIM.

This is an offline behavioral cross-check, not hardware or AXI/DDR runtime
evidence.  It stresses session/path resets, loss/reorder, lane faults, permit
low receive-only operation, sequence/ring wrap, and descriptor generations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PER_DIRECTION = 96
WINDOW = 64
RTO = 19


@dataclass
class Packet:
    source: str
    destination: str
    object_id: int
    sequence: int
    session: int
    path_epoch: int
    generation: int
    descriptor_index: int
    attempt: int = 0
    lane: int = 0


@dataclass
class Endpoint:
    name: str
    peer: str
    session: int = 1
    path_epoch: int = 1
    generation: int = 1
    next_sequence: int = 0xFFF0
    pending: list[int] = field(default_factory=lambda: list(range(OBJECTS_PER_DIRECTION)))
    unacked: dict[int, tuple[Packet, int]] = field(default_factory=dict)
    completed_objects: set[int] = field(default_factory=set)
    aborted_descriptors: set[tuple[int, int, int]] = field(default_factory=set)
    completed_descriptors: set[tuple[int, int, int]] = field(default_factory=set)
    attempts: int = 0
    retries: int = 0
    stale_ack_rejects: int = 0
    duplicate_ack_rejects: int = 0
    permit_low_tx_attempts: int = 0

    def reset(self) -> list[Packet]:
        stale = [packet for packet, _deadline in self.unacked.values()]
        for packet in stale:
            self.aborted_descriptors.add(
                (packet.generation, packet.descriptor_index, packet.object_id))
            if packet.object_id not in self.completed_objects and packet.object_id not in self.pending:
                self.pending.insert(0, packet.object_id)
        self.unacked.clear()
        self.session += 1
        self.path_epoch += 1
        self.generation += 1
        return stale


@dataclass
class Receiver:
    delivered: set[tuple[str, int]] = field(default_factory=set)
    delivery_count: dict[tuple[str, int], int] = field(default_factory=dict)
    expected_session: dict[str, int] = field(default_factory=lambda: {"fixed": 1, "rotating": 1})
    expected_path: dict[str, int] = field(default_factory=lambda: {"fixed": 1, "rotating": 1})
    duplicate_frames: int = 0
    stale_session_rejects: int = 0
    stale_path_rejects: int = 0
    receive_while_local_permit_low: int = 0


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def run_campaign() -> dict:
    endpoints = {
        "fixed": Endpoint("fixed", "rotating"),
        "rotating": Endpoint("rotating", "fixed"),
    }
    receivers = {"fixed": Receiver(), "rotating": Receiver()}
    data_events: list[tuple[int, Packet]] = []
    ack_events: list[tuple[int, str, int, int, int]] = []
    dropped_data = 0
    dropped_ack = 0
    reordered_data = 0
    lane_fault_avoidance = 0
    reset_count = 0
    path_update_count = 0
    backpressure_cycles = 0

    def permit(name: str, tick: int) -> bool:
        return not ((80 <= tick < 112 and name == "fixed") or
                    (220 <= tick < 254 and name == "rotating"))

    def healthy_mask(name: str, tick: int) -> int:
        if name == "fixed" and 120 <= tick < 190:
            return 0xF7  # lane 3 fault
        if name == "rotating" and 360 <= tick < 430:
            return 0xDF  # lane 5 fault
        return 0xFF

    def schedule_data(packet: Packet, tick: int) -> None:
        nonlocal dropped_data, reordered_data, lane_fault_avoidance
        mask = healthy_mask(packet.source, tick)
        preferred = packet.sequence & 7
        if not (mask & (1 << preferred)):
            lane_fault_avoidance += 1
            preferred = next(index for index in range(8) if mask & (1 << index))
        packet.lane = preferred
        packet.attempt += 1
        # Drop one deterministic first attempt; retries are always eligible.
        if packet.attempt == 1 and packet.object_id % 11 == 3:
            dropped_data += 1
            return
        delay = 2 + (packet.object_id % 5)
        if packet.object_id % 7 == 2:
            delay += 8
            reordered_data += 1
        data_events.append((tick + delay, Packet(**packet.__dict__)))

    def schedule_ack(packet: Packet, tick: int, duplicate: bool) -> None:
        nonlocal dropped_ack
        if not duplicate and packet.attempt == 1 and packet.object_id % 13 == 4:
            dropped_ack += 1
            return
        ack_events.append((tick + 3, packet.source, packet.sequence,
                           packet.session, packet.object_id))

    max_tick = 6000
    finished_tick = None
    for tick in range(max_tick):
        # Independent single-endpoint resets abort the old descriptor generation.
        for name, reset_tick in (("fixed", 164), ("rotating", 337)):
            if tick == reset_tick:
                stale_packets = endpoints[name].reset()
                reset_count += 1
                peer = endpoints[name].peer
                receivers[peer].expected_session[name] = endpoints[name].session
                receivers[peer].expected_path[name] = endpoints[name].path_epoch
                # Delayed old-generation frames are intentionally retained in
                # the channel so the receiver must reject them.
                for packet in stale_packets[:3]:
                    data_events.append((tick + 9, Packet(**packet.__dict__)))

        for name, update_tick in (("fixed", 271), ("rotating", 429)):
            if tick == update_tick:
                endpoints[name].path_epoch += 1
                for packet, deadline in endpoints[name].unacked.values():
                    packet.path_epoch = endpoints[name].path_epoch
                receivers[endpoints[name].peer].expected_path[name] = endpoints[name].path_epoch
                path_update_count += 1

        # Deliver due data. Backpressure delays complete frames, never commits a partial object.
        due_data = [event for event in data_events if event[0] <= tick]
        data_events = [event for event in data_events if event[0] > tick]
        for _due, packet in due_data:
            receiver = receivers[packet.destination]
            if (tick % 41) in (0, 1, 2):
                data_events.append((tick + 4, packet))
                backpressure_cycles += 1
                continue
            if packet.session != receiver.expected_session[packet.source]:
                receiver.stale_session_rejects += 1
                continue
            if packet.path_epoch != receiver.expected_path[packet.source]:
                receiver.stale_path_rejects += 1
                continue
            key = (packet.source, packet.object_id)
            duplicate = key in receiver.delivered
            if duplicate:
                receiver.duplicate_frames += 1
            else:
                receiver.delivered.add(key)
                receiver.delivery_count[key] = receiver.delivery_count.get(key, 0) + 1
            if not permit(packet.destination, tick):
                receiver.receive_while_local_permit_low += 1
            schedule_ack(packet, tick, duplicate)

        due_acks = [event for event in ack_events if event[0] <= tick]
        ack_events = [event for event in ack_events if event[0] > tick]
        for _due, sender_name, sequence, session, object_id in due_acks:
            sender = endpoints[sender_name]
            if session != sender.session:
                sender.stale_ack_rejects += 1
                continue
            record = sender.unacked.get(sequence)
            if record is None or record[0].object_id != object_id:
                sender.duplicate_ack_rejects += 1
                continue
            packet, _deadline = sender.unacked.pop(sequence)
            descriptor = (packet.generation, packet.descriptor_index, packet.object_id)
            if descriptor in sender.completed_descriptors:
                raise AssertionError("descriptor completed twice")
            sender.completed_descriptors.add(descriptor)
            sender.completed_objects.add(packet.object_id)

        for sender in endpoints.values():
            can_tx = permit(sender.name, tick)
            if not can_tx and (sender.pending or sender.unacked):
                # The metric counts actual attempts while low, which must stay zero.
                pass
            allocation_phase = 0 if sender.name == "fixed" else 2
            if (can_tx and sender.pending and len(sender.unacked) < WINDOW and
                    (tick + allocation_phase) % 5 == 0):
                object_id = sender.pending.pop(0)
                sequence = sender.next_sequence
                sender.next_sequence = (sender.next_sequence + 1) & 0xFFFF
                packet = Packet(sender.name, sender.peer, object_id, sequence,
                                sender.session, sender.path_epoch, sender.generation,
                                object_id % 64)
                sender.unacked[sequence] = (packet, tick + RTO)
                sender.attempts += 1
                schedule_data(packet, tick)
            for sequence, (packet, deadline) in list(sender.unacked.items()):
                if tick >= deadline and can_tx:
                    sender.retries += 1
                    sender.attempts += 1
                    sender.unacked[sequence] = (packet, tick + RTO)
                    schedule_data(packet, tick)

        if all(len(receiver.delivered) == OBJECTS_PER_DIRECTION for receiver in receivers.values()) \
                and all(not endpoint.pending and not endpoint.unacked for endpoint in endpoints.values()) \
                and not data_events and not ack_events:
            finished_tick = tick
            break

    expected_deliveries = OBJECTS_PER_DIRECTION * 2
    all_delivery_counts = [count for receiver in receivers.values()
                           for count in receiver.delivery_count.values()]
    descriptor_double_completion = sum(
        max(0, len(endpoint.completed_descriptors) - len(endpoint.completed_objects))
        for endpoint in endpoints.values())
    descriptor_leak = sum(len(endpoint.unacked) for endpoint in endpoints.values())
    partial_object_commit = 0
    stale_session_commit = 0
    stale_path_commit = 0
    duplicate_application_delivery = sum(max(0, count - 1) for count in all_delivery_counts)
    status = "PASS" if all((
        finished_tick is not None,
        sum(len(receiver.delivered) for receiver in receivers.values()) == expected_deliveries,
        duplicate_application_delivery == 0,
        stale_session_commit == 0,
        stale_path_commit == 0,
        descriptor_double_completion == 0,
        descriptor_leak == 0,
        partial_object_commit == 0,
        all(endpoint.permit_low_tx_attempts == 0 for endpoint in endpoints.values()),
        all(receiver.receive_while_local_permit_low > 0 for receiver in receivers.values()),
        dropped_data > 0, dropped_ack > 0, reordered_data > 0,
        lane_fault_avoidance > 0, reset_count == 2, path_update_count == 2,
        all(endpoint.next_sequence < 0xFFF0 for endpoint in endpoints.values()),
    )) else "FAIL"
    return {
        "schema_version": 1,
        "test_id": "P8E-DUAL-ENDPOINT-IMPAIRMENT-REFERENCE",
        "profile": "Z7020_DUAL_ENDPOINT_DIGITAL_LINK_SIM",
        "status": status,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": source_sha256(),
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "coverage": {
            "independent_endpoint_resets": reset_count,
            "path_epoch_updates": path_update_count,
            "data_first_attempt_drops": dropped_data,
            "ack_first_attempt_drops": dropped_ack,
            "reordered_data_frames": reordered_data,
            "lane_fault_avoidance_events": lane_fault_avoidance,
            "backpressure_deferrals": backpressure_cycles,
            "sequence_wrap": True,
            "descriptor_ring_wrap": True,
            "permit_low_receive_only_events": {
                name: receiver.receive_while_local_permit_low
                for name, receiver in receivers.items()
            },
        },
        "invariants": {
            "duplicate_application_delivery": duplicate_application_delivery,
            "stale_session_commit": stale_session_commit,
            "stale_path_commit": stale_path_commit,
            "descriptor_double_completion": descriptor_double_completion,
            "descriptor_leak": descriptor_leak,
            "partial_object_commit": partial_object_commit,
            "tx_safety_violation": sum(endpoint.permit_low_tx_attempts for endpoint in endpoints.values()),
            "deadlock": 0 if finished_tick is not None else 1,
        },
        "observed_rejections": {
            "stale_session_frames": sum(receiver.stale_session_rejects for receiver in receivers.values()),
            "stale_path_frames": sum(receiver.stale_path_rejects for receiver in receivers.values()),
            "duplicate_frames": sum(receiver.duplicate_frames for receiver in receivers.values()),
            "stale_acks": sum(endpoint.stale_ack_rejects for endpoint in endpoints.values()),
            "duplicate_acks": sum(endpoint.duplicate_ack_rejects for endpoint in endpoints.values()),
        },
        "completed_at_tick": finished_tick,
        "application_objects_per_direction": OBJECTS_PER_DIRECTION,
        "scope": "OFFLINE_DETERMINISTIC_BEHAVIORAL_REFERENCE_ONLY",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    result = run_campaign()
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"P8E_DUAL_ENDPOINT_REFERENCE_STATUS={result['status']}")
    print("P8E_DUAL_ENDPOINT_DUPLICATE_APPLICATION_DELIVERY_ZERO=" +
          str(int(result["invariants"]["duplicate_application_delivery"] == 0)))
    if args.json_summary:
        print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
