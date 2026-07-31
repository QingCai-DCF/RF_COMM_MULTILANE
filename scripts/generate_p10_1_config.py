#!/usr/bin/env python3
"""Validate canonical P10.1 YAML and generate all language consumers."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from p10_1_common import ROOT, evidence_base, load_yaml, rel, sha256, stable_json, write_pair, write_text


CONFIG_DIR = ROOT / "config/performance"
CONFIGS = {
    "measurement": CONFIG_DIR / "p10_1_measurement_contract.yaml",
    "pipeline": CONFIG_DIR / "p10_1_pipeline.yaml",
    "streaming": CONFIG_DIR / "p10_1_streaming.yaml",
    "tests": CONFIG_DIR / "p10_1_test_matrix.yaml",
}
SV_OUT = ROOT / "rtl/generated/p10_1_contract_pkg.sv"
C_OUT = ROOT / "software/ps_driver/p10_1_contract.h"
PY_OUT = ROOT / "scripts/generated/p10_1_contract.py"
JSON_OUT = ROOT / "config/performance/generated/p10_1_contract.json"
MD_OUT = ROOT / "docs/design/P10_1_GENERATED_CONTRACT.md"


def require(mapping: dict[str, Any], path: str, expected_type: type | tuple[type, ...]) -> Any:
    cursor: Any = mapping
    for component in path.split("."):
        if not isinstance(cursor, dict) or component not in cursor:
            raise ValueError(f"missing canonical field {path}")
        cursor = cursor[component]
    if not isinstance(cursor, expected_type):
        raise ValueError(f"canonical field {path} has invalid type")
    return cursor


def validate(documents: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    try:
        measurement = documents["measurement"]
        pipeline = documents["pipeline"]
        streaming = documents["streaming"]
        tests = documents["tests"]
        if require(measurement, "schema_version", int) != 2:
            errors.append("measurement schema_version must be 2")
        if require(pipeline, "schema_version", int) != 1:
            errors.append("pipeline schema_version must be 1")
        if require(streaming, "schema_version", int) != 1:
            errors.append("streaming schema_version must be 1")
        if require(tests, "schema_version", int) != 1:
            errors.append("test matrix schema_version must be 1")
        required_metrics = {
            "PHY_RAW_BPS",
            "FRAME_GOODPUT_BPS",
            "APPLICATION_GOODPUT_BPS",
            "OBJECT_COMPLETION_BPS",
            "ENDPOINT_TO_ENDPOINT_GOODPUT_BPS",
            "HOST_ORCHESTRATED_GOODPUT_BPS",
        }
        metrics = require(measurement, "metrics", dict)
        if set(metrics) != required_metrics:
            errors.append("measurement metric set does not match the P10.1 contract")
        required_classes = {
            "PHY_RAW",
            "FRAME_SUSTAINED",
            "APPLICATION_SUSTAINED",
            "OBJECT_SINGLE",
            "HOST_ORCHESTRATED",
            "DIAGNOSTIC_MICROTRANSFER",
            "SOAK_WINDOW",
        }
        if set(require(measurement, "measurement_classes", list)) != required_classes:
            errors.append("measurement class set does not match the P10.1 contract")
        required_record_fields = {
            "metric_name", "measurement_class", "direction", "lane_mask",
            "committed_application_bytes", "wire_bytes", "frame_payload_bytes",
            "object_count", "start_event", "end_event", "start_timestamp",
            "end_timestamp", "timer_source", "timer_frequency", "elapsed_seconds",
            "units", "warmup_included", "idle_included", "host_staging_included",
            "diagnostic_only", "eligible_for_scaling", "integrity_error_count",
            "retry_exhausted_count", "timer_crosscheck_status", "run_id", "case_id",
            "artifact_sha256",
        }
        missing_fields = required_record_fields - set(
            require(measurement, "metric_record_required_fields", list)
        )
        if missing_fields:
            errors.append("metric record fields missing: " + ", ".join(sorted(missing_fields)))
        if require(measurement, "scaling_eligibility.minimum_committed_bytes_per_direction", int) != 16 * 1024 * 1024:
            errors.append("scaling byte threshold must be exactly 16 MiB per direction")
        if require(measurement, "scaling_eligibility.alternative_minimum_duration_seconds_per_direction", int) != 30:
            errors.append("scaling duration threshold must be exactly 30 seconds per direction")
        if require(measurement, "timer.pl_counter_width_bits", int) != 64:
            errors.append("PL timer counter width must be 64")
        if require(pipeline, "defaults.lane_mask", int) & ~0x3:
            errors.append("default lane mask exceeds the two-lane P10 scope")
        if require(pipeline, "performance_targets.scale_equivalent_hard_bps_per_half_duplex_direction", int) != 4_000_000:
            errors.append("P10.1 hard modeled target must remain 4.0 Mbit/s")
        if require(pipeline, "performance_targets.stretch_bps_per_half_duplex_direction", int) != 4_800_000:
            errors.append("P10.1 stretch modeled target must remain 4.8 Mbit/s")
        if require(streaming, "mandatory_stream_size_bytes", int) != 64 * 1024 * 1024:
            errors.append("mandatory streaming size must be 64 MiB")
        if require(streaming, "optional_stream_size_bytes", int) != 128 * 1024 * 1024:
            errors.append("optional streaming size must be 128 MiB")
        if require(pipeline, "trace.overflow_blocks_fast_path", bool):
            errors.append("trace overflow must not block the fast path")
        campaign = require(tests, "random_campaigns", dict)
        minima = {
            "buffer_descriptor_events": 100_000,
            "stream_abort_reset_events": 50_000,
            "metric_finalizer_cases": 50_000,
            "trace_overflow_snapshot_cases": 25_000,
        }
        for name, minimum in minima.items():
            if int(campaign.get(name, 0)) < minimum:
                errors.append(f"{name} campaign is below {minimum}")
    except (TypeError, ValueError) as exc:
        errors.append(str(exc))
    return errors


def canonical_values(documents: dict[str, dict[str, Any]]) -> dict[str, int]:
    measurement = documents["measurement"]
    pipeline = documents["pipeline"]
    streaming = documents["streaming"]
    return {
        "PL_TIMER_FREQUENCY_HZ": int(measurement["timer"]["pl_frequency_hz"]),
        "PL_TIMER_COUNTER_WIDTH_BITS": int(measurement["timer"]["pl_counter_width_bits"]),
        "PS_TIMER_FREQUENCY_HZ": int(measurement["timer"]["ps_frequency_hz"]),
        "PS_TRACE_DEPTH_RECORDS": int(pipeline["trace"]["ps_trace_depth_records"]),
        "PL_EVENT_FIFO_DEPTH_RECORDS": int(pipeline["trace"]["pl_event_fifo_depth_records"]),
        "BUFFER_COUNT": int(pipeline["defaults"]["buffer_count"]),
        "BUFFER_SIZE_BYTES": int(pipeline["defaults"]["buffer_size_bytes"]),
        "RING_DEPTH": int(pipeline["defaults"]["descriptor_ring_depth"]),
        "DESCRIPTOR_BATCH": int(pipeline["defaults"]["descriptor_batch"]),
        "INTERRUPT_COALESCING": int(pipeline["defaults"]["interrupt_coalescing"]),
        "SEGMENT_SIZE_BYTES": int(streaming["segment_size_bytes"]),
        "MAX_STREAM_SIZE_BYTES": int(streaming["maximum_stream_size_bytes"]),
        "ACK_AGGREGATION_THRESHOLD": int(pipeline["defaults"]["ack_aggregation_threshold"]),
        "DIRECTION_WINDOW_US": int(pipeline["defaults"]["direction_window_us"]),
        "OUTSTANDING_FRAMES": int(pipeline["defaults"]["outstanding_frames"]),
        "LANE_MASK": int(pipeline["defaults"]["lane_mask"]),
        "MEASUREMENT_DURATION_SECONDS": int(pipeline["defaults"]["formal_measurement_duration_seconds"]),
        "HARD_TARGET_BPS": int(pipeline["performance_targets"]["scale_equivalent_hard_bps_per_half_duplex_direction"]),
        "STRETCH_TARGET_BPS": int(pipeline["performance_targets"]["stretch_bps_per_half_duplex_direction"]),
        "MANDATORY_STREAM_SIZE_BYTES": int(streaming["mandatory_stream_size_bytes"]),
        "OPTIONAL_STREAM_SIZE_BYTES": int(streaming["optional_stream_size_bytes"]),
    }


def render_outputs(documents: dict[str, dict[str, Any]]) -> dict[Path, str]:
    values = canonical_values(documents)
    config_hashes = {name: sha256(path) for name, path in CONFIGS.items()}
    bundle = {"schema_version": 1, "config_sha256": config_hashes, "values": values}

    sv = [
        "// Generated from config/performance/p10_1_*.yaml; do not edit.",
        "package p10_1_contract_pkg;",
    ]
    c = [
        "#pragma once",
        "#include <stdint.h>",
        "/* Generated from config/performance/p10_1_*.yaml; do not edit. */",
    ]
    py = [
        "# Generated from config/performance/p10_1_*.yaml; do not edit.",
        f"CONFIG_SHA256 = {config_hashes!r}",
    ]
    md = [
        "# P10.1 generated configuration contract",
        "",
        "> Generated from the four canonical files under `config/performance`; do not edit by hand.",
        "",
        "| Parameter | Value |",
        "|---|---:|",
    ]
    for name, value in values.items():
        sv.append(f"  localparam longint unsigned P10_1_{name} = {value};")
        c.append(f"#define P10_1_{name} UINT64_C({value})")
        py.append(f"P10_1_{name} = {value}")
        md.append(f"| `P10_1_{name}` | `{value}` |")
    command_names = documents["streaming"]["commands"]
    state_names = documents["pipeline"]["buffer_states"]
    c.extend(["", "typedef enum p10_1_perf_command {"])
    sv.extend(["", "  typedef enum logic [3:0] {"])
    for index, name in enumerate(command_names):
        comma = "," if index + 1 < len(command_names) else ""
        c.append(f"  P10_1_COMMAND_{name} = {index + 1}{comma}")
        sv.append(f"    P10_1_COMMAND_{name} = 4'd{index + 1}{comma}")
    c.extend(["} p10_1_perf_command_t;", "", "typedef enum p10_1_buffer_state {"])
    sv.extend(["  } p10_1_perf_command_t;", "", "  typedef enum logic [3:0] {"])
    for index, name in enumerate(state_names):
        comma = "," if index + 1 < len(state_names) else ""
        c.append(f"  P10_1_BUFFER_{name} = {index}{comma}")
        sv.append(f"    P10_1_BUFFER_{name} = 4'd{index}{comma}")
    c.extend(["} p10_1_buffer_state_t;", ""])
    sv.extend(["  } p10_1_buffer_state_t;", "endpackage", ""])
    py.append("PERF_COMMANDS = " + repr({name: index + 1 for index, name in enumerate(command_names)}))
    py.append("BUFFER_STATES = " + repr({name: index for index, name in enumerate(state_names)}))
    py.append("")
    md.extend(["", "## Canonical source hashes", ""])
    for name, digest in config_hashes.items():
        md.append(f"- `{rel(CONFIGS[name])}`: `{digest}`")
    return {
        SV_OUT: "\n".join(sv),
        C_OUT: "\n".join(c),
        PY_OUT: "\n".join(py),
        JSON_OUT: stable_json(bundle).rstrip(),
        MD_OUT: "\n".join(md),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    documents = {name: load_yaml(path) for name, path in CONFIGS.items()}
    errors = validate(documents)
    outputs = render_outputs(documents) if not errors else {}
    stale: list[str] = []
    for path, content in outputs.items():
        expected = content.rstrip() + "\n"
        if args.write:
            write_text(path, content)
        elif not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(rel(path))
    errors.extend(f"stale generated artifact: {path}" for path in stale)
    payload = evidence_base(
        "P10_1-MEASUREMENT-CONTRACT-SCHEMA",
        status="PASS" if not errors else "FAIL",
        config_files=[
            {"path": rel(path), "sha256": sha256(path)} for path in CONFIGS.values()
        ],
        generated_files=[
            {"path": rel(path), "sha256": sha256(path)}
            for path in outputs
            if path.is_file()
        ],
        canonical_values=canonical_values(documents) if not errors else {},
        errors=errors,
    )
    if args.write or not errors:
        write_pair(
            "p10_1_measurement_contract",
            "P10.1 measurement contract and schema validation",
            payload,
            [
                "## Result",
                "",
                "All metric names, measurement classes, eligibility fields, timer widths, pipeline constants, "
                "stream sizes, test campaigns, and performance targets are generated from the canonical YAML set.",
            ],
        )
    print(f"P10_1_SCHEMA_VALIDATION={payload['status']}")
    print(f"P10_1_GENERATED_ARTIFACT_COUNT={len(outputs)}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
