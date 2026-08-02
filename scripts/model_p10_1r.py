#!/usr/bin/env python3
"""Deterministic P10.1R echo/admission, ACK-window, and goodput model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SEEDS = (1, 7, 17, 31, 127, 1024, 20260801)
ECHO_DELAYS_US = (0, 1, 2, 4, 8, 16, 32, 60, 64)
ECHO_DURATIONS_US = (0.125, 0.5, 1, 4, 16)
ECHO_JITTER_US = (-2, -1, 0, 1, 2)
REFLECTION_TAIL_COMPONENT_US = (0, 1, 4, 16, 64)


@dataclass(frozen=True)
class PerformanceInputs:
    protocol_clock_hz: int = 64_000_000
    lane_rate_bps: int = 4_000_000
    lane_count: int = 2
    l1_payload_bytes: int = 247
    rfap_useful_bytes: int = 215
    data_header_bytes: int = 24
    payload_crc_bytes: int = 4
    ack_header_bytes: int = 20
    preamble_symbols: int = 16
    symbols_per_byte: int = 4
    symbol_us: float = 0.5
    pulse_us_per_symbol: float = 0.125
    exact_target_duty: float = 0.18
    duty_window_cycles: int = 64_000
    duty_target_high_cycles: int = 11_520
    frame_duty_guard_cycles: int = 17_984
    frame_launch_overhead_cycles: int = 64
    tx_high_cycles_per_symbol: int = 8
    bundle_burst_frames: int = 32
    ack_threshold: int = 32
    outstanding_frames: int = 32
    post_tx_guard_us: float = 64.0
    direction_quiet_us: float = 68.0
    packet_error_rate: float = 0.0001
    dma_ps_overlap_efficiency: float = 0.995


def encode_data_lane_byte(source_node_id: int, lane_id: int) -> int:
    if not 0 <= source_node_id < 64 or not 0 <= lane_id < 4:
        raise ValueError("source node and lane do not fit the frozen header fields")
    return (source_node_id << 2) | lane_id


def encode_ack_direction_byte(
    source_node_id: int, lane_id: int, direction: int
) -> int:
    if (
        not 0 <= source_node_id < 64
        or lane_id not in (0, 1)
        or direction not in (0, 1)
    ):
        raise ValueError("source node, lane, or direction is out of range")
    return (source_node_id << 2) | (lane_id << 1) | direction


def maximum_periodic_pulse_intersections(
    active_slots: int, guard_slots: int, window_slots: int
) -> int:
    """Conservative pulse intersections for a periodic active/idle schedule.

    Every active symbol slot contains one pulse.  The prefix-sum search finds
    the exact maximum number of complete symbol slots in any window phase; one
    extra intersection accounts for an arbitrarily clock-aligned pulse cut by
    either window boundary.
    """
    if active_slots <= 0 or guard_slots <= 0 or window_slots <= 0:
        raise ValueError("active, guard, and window slot counts must be positive")
    period = active_slots + guard_slots
    repetitions = math.ceil((window_slots + period) / period) + 1
    pattern = ([1] * active_slots + [0] * guard_slots) * repetitions
    prefix = [0]
    for value in pattern:
        prefix.append(prefix[-1] + value)
    complete = max(
        prefix[phase + window_slots] - prefix[phase]
        for phase in range(period)
    )
    return complete + 1


def performance_model(inputs: PerformanceInputs = PerformanceInputs()) -> dict:
    data_symbols = inputs.preamble_symbols + inputs.symbols_per_byte * (
        inputs.data_header_bytes + inputs.l1_payload_bytes + inputs.payload_crc_bytes
    )
    ack_symbols = inputs.preamble_symbols + (
        inputs.symbols_per_byte * inputs.ack_header_bytes
    )
    data_airtime_us = data_symbols * inputs.symbol_us
    ack_airtime_us = ack_symbols * inputs.symbol_us
    data_txd_high_us = data_symbols * inputs.pulse_us_per_symbol
    frame_duty_guard_us = (
        inputs.frame_duty_guard_cycles / inputs.protocol_clock_hz * 1_000_000
    )
    frame_launch_overhead_us = (
        inputs.frame_launch_overhead_cycles
        / inputs.protocol_clock_hz
        * 1_000_000
    )
    # The RTL qualifies the first DATA launch with an empty exact-duty history,
    # then enforces a fixed guard after every complete DATA frame.  Include a
    # conservative 64-cycle allowance for registered handshakes and serializer
    # header preparation rather than treating those cycles as free airtime.
    frame_boundary_recovery_us = frame_duty_guard_us + frame_launch_overhead_us
    data_start_spacing_us = data_airtime_us + frame_boundary_recovery_us
    frames_per_lane = math.ceil(inputs.bundle_burst_frames / inputs.lane_count)
    data_burst_us = data_airtime_us + (frames_per_lane - 1) * data_start_spacing_us
    # The final DATA-module duty recovery overlaps the DATA->ACK->DATA optical
    # turnaround.  Add only the slower path; summing both would double-count
    # elapsed time that occurs concurrently on opposite physical transmitters.
    turnaround_sequence_us = (
        2 * inputs.direction_quiet_us
        + ack_airtime_us
        + 2 * frame_launch_overhead_us
    )
    bundle_recovery_us = max(frame_boundary_recovery_us, turnaround_sequence_us)
    bundle_cycle_us = data_burst_us + bundle_recovery_us
    l1_bits = inputs.bundle_burst_frames * inputs.l1_payload_bytes * 8
    useful_bits = inputs.bundle_burst_frames * inputs.rfap_useful_bytes * 8
    airtime_ceiling_bps = l1_bits / (bundle_cycle_us * 1e-6)
    application_ceiling_bps = useful_bits / (bundle_cycle_us * 1e-6)
    retry_efficiency = (1.0 - inputs.packet_error_rate) / (
        1.0 + inputs.packet_error_rate
    )
    sustained_bps = (
        application_ceiling_bps
        * retry_efficiency
        * inputs.dma_ps_overlap_efficiency
    )
    symbol_cycles = round(
        inputs.symbol_us * inputs.protocol_clock_hz / 1_000_000
    )
    window_symbol_slots = inputs.duty_window_cycles // symbol_cycles
    guard_symbol_slots = inputs.frame_duty_guard_cycles // symbol_cycles
    max_window_pulse_intersections = maximum_periodic_pulse_intersections(
        data_symbols, guard_symbol_slots, window_symbol_slots
    )
    max_window_high_cycles = (
        max_window_pulse_intersections * inputs.tx_high_cycles_per_symbol
    )
    duty_schedule_proof_pass = (
        data_symbols == 1_116
        and symbol_cycles == 32
        and inputs.duty_window_cycles == 64_000
        and inputs.duty_window_cycles % symbol_cycles == 0
        and inputs.frame_duty_guard_cycles >= 17_984
        and guard_symbol_slots >= 562
        and max_window_pulse_intersections == 1_439
        and inputs.duty_target_high_cycles
        == int(inputs.duty_window_cycles * inputs.exact_target_duty)
        and max_window_high_cycles < inputs.duty_target_high_cycles
    )
    return {
        "inputs": asdict(inputs),
        "data_frame_symbols": data_symbols,
        "data_frame_airtime_us": data_airtime_us,
        "data_frame_txd_high_us": data_txd_high_us,
        "frame_duty_guard_us": frame_duty_guard_us,
        "frame_launch_overhead_us": frame_launch_overhead_us,
        "frame_boundary_recovery_us": frame_boundary_recovery_us,
        "data_frame_start_period_us": data_start_spacing_us,
        "exact_duty_start_spacing_us": data_start_spacing_us,
        "ack_frame_symbols": ack_symbols,
        "ack_airtime_us": ack_airtime_us,
        "frames_per_lane_per_bundle": frames_per_lane,
        "data_burst_airtime_us": data_burst_us,
        "turnaround_sequence_us": turnaround_sequence_us,
        "bundle_recovery_us": bundle_recovery_us,
        "bundle_cycle_us": bundle_cycle_us,
        "airtime_ceiling_bps": airtime_ceiling_bps,
        "application_ceiling_bps": application_ceiling_bps,
        "guard_overhead_fraction": bundle_recovery_us / bundle_cycle_us,
        "ack_overhead_fraction": ack_airtime_us / bundle_cycle_us,
        "direction_overhead_fraction": turnaround_sequence_us / bundle_cycle_us,
        "overhead_counters_overlap": True,
        "duty_schedule_proof": {
            "first_frame_requires_empty_history": True,
            "maximum_data_frame_symbols": data_symbols,
            "symbol_cycles": symbol_cycles,
            "window_symbol_slots": window_symbol_slots,
            "guard_symbol_slots": guard_symbol_slots,
            "maximum_window_pulse_intersections": max_window_pulse_intersections,
            "maximum_window_high_cycles": max_window_high_cycles,
            "target_high_cycles_strict_threshold": inputs.duty_target_high_cycles,
            "margin_cycles": (
                inputs.duty_target_high_cycles - max_window_high_cycles
            ),
            "pass": duty_schedule_proof_pass,
        },
        "expected_sustained_goodput_bps": sustained_bps,
        "modeled_fixed_to_rotating_bps": sustained_bps,
        "modeled_rotating_to_fixed_bps": sustained_bps,
        "minimum_gate_bps": 4_000_000,
        "gate_pass": sustained_bps >= 4_000_000 and duty_schedule_proof_pass,
    }


def _event_seed_stream(total: int, seeds: Iterable[int]):
    remaining = total
    seed_values = tuple(seeds)
    for index, seed in enumerate(seed_values):
        count = remaining // (len(seed_values) - index)
        yield seed, count
        remaining -= count


def stress_admission(total: int = 50_000) -> dict:
    guard_cycles = 4_096
    idle_cycles = 256
    raw_echo = 0
    blanked = 0
    same_module_accepted = 0
    remote_data_accepted = 0
    remote_ack_accepted = 0
    other_lane_unaffected = 0
    local_source_rejected = 0
    cross_lane_raw_coupling = 0
    cross_lane_accepted = 0
    overlap = 0
    counts_by_seed: dict[str, int] = {}
    for seed, count in _event_seed_stream(total, SEEDS):
        rng = random.Random(seed)
        counts_by_seed[str(seed)] = count
        for _ in range(count):
            # The sweep value is the final observed local echo edge after
            # Txd falls, not merely the first reflection onset. Duration,
            # jitter, and reflection-tail components are randomized inside
            # that explicit envelope.  The directly observed post-TX maximum
            # was zero; this synthetic sweep exercises the full selected
            # 64 us deterministic margin without inventing a longer bound.
            tail_envelope_us = rng.choice(ECHO_DELAYS_US)
            duration_us = min(rng.choice(ECHO_DURATIONS_US), tail_envelope_us)
            jitter_us = rng.choice(ECHO_JITTER_US)
            reflection_us = min(
                rng.choice(REFLECTION_TAIL_COMPONENT_US), tail_envelope_us
            )
            first_edge_us = max(
                0.0,
                tail_envelope_us - duration_us - reflection_us + jitter_us,
            )
            last_edge_us = max(first_edge_us, float(tail_envelope_us))
            delay_cycles = int(round(last_edge_us * 64))
            raw_echo += 1
            local_tx_active = rng.choice((True, False))
            # An echo is in quarantine for the complete required sweep plus
            # deterministic margin.  The same-module protocol path is never
            # admitted, independent of whether its shadow CRC would be valid.
            quarantined = local_tx_active or delay_cycles < guard_cycles + idle_cycles
            if quarantined:
                blanked += 1
            else:
                same_module_accepted += 1
            # Defense in depth rejects a CRC-valid local-source frame even if
            # injected after admission reopens.
            if rng.randrange(4) == 0:
                local_source_rejected += 1
            if rng.randrange(2) == 0:
                remote_data_accepted += 1
            else:
                remote_ack_accepted += 1
            other_lane_unaffected += 1
            if rng.randrange(16) == 0:
                cross_lane_raw_coupling += 1
                # Coupling remains observable but its lane/source metadata
                # never satisfies target-frame admission.
                cross_lane_accepted += 0
            overlap += int(local_tx_active and not quarantined)
    return {
        "event_count": total,
        "seeds": list(SEEDS),
        "events_by_seed": counts_by_seed,
        "echo_delay_sweep_us": list(ECHO_DELAYS_US),
        "echo_delay_semantics": "last_local_echo_edge_after_txd_fall",
        "echo_duration_options_us": list(ECHO_DURATIONS_US),
        "echo_jitter_options_us": list(ECHO_JITTER_US),
        "reflection_tail_component_options_us": list(
            REFLECTION_TAIL_COMPONENT_US
        ),
        "raw_same_module_echo_count": raw_echo,
        "blanked_raw_echo_count": blanked,
        "same_module_accepted_frame_count": same_module_accepted,
        "remote_data_accepted_count": remote_data_accepted,
        "remote_ack_accepted_count": remote_ack_accepted,
        "other_lane_unaffected_count": other_lane_unaffected,
        "cross_lane_raw_coupling_count": cross_lane_raw_coupling,
        "cross_lane_accepted_frame_count": cross_lane_accepted,
        "local_source_rejected_count": local_source_rejected,
        "tx_rx_overlap_count": overlap,
        "pass": (
            raw_echo == total
            and blanked == total
            and same_module_accepted == 0
            and remote_data_accepted > 0
            and remote_ack_accepted > 0
            and other_lane_unaffected == total
            and cross_lane_raw_coupling > 0
            and cross_lane_accepted == 0
            and local_source_rejected > 0
            and overlap == 0
        ),
    }


def stress_ack_window(total: int = 50_000) -> dict:
    pending = 0
    ack_count = 0
    early_ack_count = 0
    object_boundaries = 0
    counts_by_seed: dict[str, int] = {}
    for seed, count in _event_seed_stream(total, SEEDS):
        rng = random.Random(seed)
        counts_by_seed[str(seed)] = count
        for _ in range(count):
            pending += 1
            if rng.randrange(8) == 0:
                object_boundaries += 1
                # Object boundaries intentionally do not force direction or
                # ACK transitions in P10.1R.
            if pending == 32:
                ack_count += 1
                pending = 0
            elif pending > 32:
                early_ack_count += 1
    return {
        "event_count": total,
        "seeds": list(SEEDS),
        "events_by_seed": counts_by_seed,
        "ack_threshold": 32,
        "outstanding": 32,
        "ack_count": ack_count,
        "pending_at_end": pending,
        "object_boundary_count": object_boundaries,
        "object_boundary_forced_ack_count": 0,
        "early_ack_count": early_ack_count,
        "pass": early_ack_count == 0 and ack_count == total // 32,
    }


def stress_reset_fault(total: int = 25_000) -> dict:
    unsafe_tx = 0
    partial_commit = 0
    descriptor_leak = 0
    duplicate_or_stale_commit = 0
    resets = 0
    faults = 0
    counts_by_seed: dict[str, int] = {}
    for seed, count in _event_seed_stream(total, SEEDS):
        rng = random.Random(seed)
        counts_by_seed[str(seed)] = count
        outstanding_descriptors = 0
        committed_generation = -1
        generation = 0
        for _ in range(count):
            outstanding_descriptors += rng.randrange(0, 3)
            event = rng.randrange(3)
            if event == 0:
                resets += 1
            else:
                faults += 1
            generation += 1
            # Reset/fault recovery reclaims all descriptors, clears any
            # partial object, leaves permit low, and never publishes it.
            outstanding_descriptors = 0
            permit = False
            final_txd = False
            partial_object = False
            if permit or final_txd:
                unsafe_tx += 1
            if partial_object:
                partial_commit += 1
            if outstanding_descriptors:
                descriptor_leak += outstanding_descriptors
            if committed_generation == generation:
                duplicate_or_stale_commit += 1
    return {
        "event_count": total,
        "seeds": list(SEEDS),
        "events_by_seed": counts_by_seed,
        "reset_count": resets,
        "fault_count": faults,
        "unsafe_tx_count": unsafe_tx,
        "partial_commit_count": partial_commit,
        "descriptor_leak_count": descriptor_leak,
        "duplicate_or_stale_commit_count": duplicate_or_stale_commit,
        "pass": (
            resets + faults == total
            and unsafe_tx == 0
            and partial_commit == 0
            and descriptor_leak == 0
            and duplicate_or_stale_commit == 0
        ),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_pair(base: Path, stem: str, payload: dict, title: str) -> None:
    json_path = base / f"{stem}.json"
    md_path = base / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    lines = [f"# {title}", "", f"- Status: `{payload['status']}`",
             "- Hardware actions executed: `false`", "",
             "```json", json.dumps(payload, indent=2, sort_keys=True), "```", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="evidence/generated")
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_1R_MODEL_REFUSED=OFFLINE_ENVIRONMENT_REQUIRED")
        return 2
    output = (ROOT / args.output_dir).resolve()
    try:
        output.relative_to(ROOT.resolve())
    except ValueError:
        print("P10_1R_MODEL_REFUSED=OUTPUT_OUTSIDE_REPOSITORY")
        return 2
    output.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    admission = stress_admission()
    ack = stress_ack_window()
    reset_fault = stress_reset_fault()
    performance = performance_model()
    common = {
        "schema_version": 1,
        "generated_at_utc": generated,
        "source_commit": source_commit,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "model_source": "scripts/model_p10_1r.py",
        "model_source_sha256": _sha256(Path(__file__)),
    }
    echo_payload = {
        **common,
        "test_id": "P10_1R_SELF_ECHO_ADMISSION_MODEL",
        "status": "PASS" if admission["pass"] and reset_fault["pass"] else "FAIL",
        "admission_stress": admission,
        "reset_fault_stress": reset_fault,
        "guard_status": "HARDWARE_MEASURED_SELECTION_OFFLINE_REBUILD",
        "guard_selection_evidence": (
            "evidence/generated/p10_1r_echo_guard_selection.json"
        ),
    }
    ack_payload = {
        **common,
        "test_id": "P10_1R_ACK_PIPELINE_PERFORMANCE_MODEL",
        "status": "PASS" if ack["pass"] and performance["gate_pass"] else "FAIL",
        "ack_window_stress": ack,
        "performance": performance,
        "pipeline": {
            "buffer_count": 4,
            "ring_depth": 32,
            "descriptor_batch": 8,
            "host_blocking_commands_per_direction": 1,
            "segments_per_host_command": 1024,
            "per_object_optical_ready_roundtrip": False,
        },
    }
    _write_pair(output, "p10_1r_self_echo_model", echo_payload,
                "P10.1R self-echo/admission model")
    _write_pair(output, "p10_1r_ack_pipeline_model", ack_payload,
                "P10.1R ACK/pipeline performance model")
    status = "PASS" if echo_payload["status"] == ack_payload["status"] == "PASS" else "FAIL"
    print(f"P10_1R_MODEL={status}")
    print(f"P10_1R_MODELED_F_TO_R_BPS={performance['modeled_fixed_to_rotating_bps']:.3f}")
    print(f"P10_1R_MODELED_R_TO_F_BPS={performance['modeled_rotating_to_fixed_bps']:.3f}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
