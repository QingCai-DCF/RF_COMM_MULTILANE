#!/usr/bin/env python3
"""Generate every P8D protocol/configuration consumer from one YAML source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/p8d_data_plane.yaml"
JSON_OUT = ROOT / "config/generated/p8d_data_plane_constants.json"
SCHEMA_OUT = ROOT / "config/generated/p8d_data_plane_schema_validation.json"
SV_OUT = ROOT / "rtl/generated/ir_p8d_data_plane_pkg.sv"
C_OUT = ROOT / "software/ps_driver/p8d_data_plane_config.h"
PY_OUT = ROOT / "tools/generated/p8d_data_plane_config.py"
PY_INIT = ROOT / "tools/generated/__init__.py"
MD_OUT = ROOT / "docs/generated/P8D_DATA_PLANE_PARAMETERS.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_config() -> dict[str, Any]:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("P8D configuration must be a mapping")
    return data


def validate(data: dict[str, Any]) -> dict[str, Any]:
    required = {
        "protocol_version", "legacy_mode_version", "vnext_mode_version",
        "sequence_width_bits", "global_outstanding_default",
        "global_outstanding_by_profile", "sack_window_bits_by_profile",
        "rx_reorder_window", "duplicate_history_depth", "max_retry",
        "retry_backoff_policy", "rto_initial_cycles", "rto_min_cycles",
        "rto_max_cycles", "ack_aggregation_frame_threshold",
        "ack_aggregation_max_delay_cycles", "ack_credit_low_watermark",
        "scheduler_type", "scheduler_weight_width", "scheduler_default_weights",
        "retry_priority_policy", "control_priority_policy", "starvation_bound",
        "axis_data_width_by_profile", "axis_user_width", "axis_keep_enabled",
        "max_frame_bytes", "max_l1_payload_bytes", "rfap_v1_useful_chunk_bytes",
        "tx_ring_depth", "rx_ring_depth", "descriptor_alignment_bytes",
        "descriptor_generation_bits", "ring_index_bits", "payload_buffer_strategy",
        "retransmission_storage_strategy", "session_epoch_width", "path_epoch_width",
        "stream_id_width", "object_id_width", "airtime_model_parameters",
        "duty_design_target", "duty_hard_limit", "handover_service_gap_source",
    }
    missing = sorted(required - set(data))
    errors: list[str] = []
    if missing:
        errors.append("missing keys: " + ", ".join(missing))
    seq_width = int(data.get("sequence_width_bits", 0))
    seq_space = 1 << seq_width if seq_width > 0 else 0
    if seq_width < 16:
        errors.append("sequence_width_bits must be >=16")
    profiles = set(data.get("global_outstanding_by_profile", {}))
    if profiles != set(data.get("sack_window_bits_by_profile", {})):
        errors.append("outstanding and SACK profile sets differ")
    if profiles != set(data.get("axis_data_width_by_profile", {})):
        errors.append("outstanding and AXIS profile sets differ")
    for profile in sorted(profiles):
        outstanding = int(data["global_outstanding_by_profile"][profile])
        sack = int(data["sack_window_bits_by_profile"][profile])
        axis = int(data["axis_data_width_by_profile"][profile])
        if outstanding < 32 or outstanding >= seq_space // 2:
            errors.append(f"{profile}: invalid global outstanding")
        if sack < 32 or sack > outstanding:
            errors.append(f"{profile}: invalid SACK width")
        if outstanding & (outstanding - 1):
            errors.append(f"{profile}: RTL profile window must be power-of-two")
        if axis not in (32, 64, 128) or axis % 8:
            errors.append(f"{profile}: invalid AXIS width")
    if int(data.get("rx_reorder_window", 0)) < 32:
        errors.append("rx_reorder_window must be >=32")
    if not (0 < int(data.get("rto_min_cycles", 0)) <= int(data.get("rto_initial_cycles", 0))
            <= int(data.get("rto_max_cycles", 0))):
        errors.append("RTO bounds are not monotonic")
    if int(data.get("max_retry", -1)) < 0:
        errors.append("max_retry must be bounded and nonnegative")
    if int(data.get("descriptor_bytes", 0)) != 64:
        errors.append("descriptor_bytes must be 64 for layout v1")
    descriptor_fields = data.get("descriptor_layout", {}).get("fields", [])
    occupied: set[int] = set()
    for field in descriptor_fields:
        offset = int(field["offset"])
        width = int(field["width_bits"])
        if width not in (16, 32, 64) or offset + width // 8 > 64:
            errors.append(f"invalid descriptor field {field.get('name')}")
            continue
        field_bytes = set(range(offset, offset + width // 8))
        if occupied & field_bytes:
            errors.append(f"overlapping descriptor field {field.get('name')}")
        occupied |= field_bytes
    design = float(data.get("duty_design_target", 0))
    hard = float(data.get("duty_hard_limit", 0))
    if not (0 < design <= 0.18 and design < hard <= 0.20):
        errors.append("duty targets must preserve <=18% design and <=20% hard bounds")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "status": "PASS",
        "profile_count": len(profiles),
        "profiles": sorted(profiles),
        "sequence_space": seq_space,
        "active_window_less_than_half_space": True,
        "minimum_outstanding": min(int(v) for v in data["global_outstanding_by_profile"].values()),
        "minimum_sack_bits": min(int(v) for v in data["sack_window_bits_by_profile"].values()),
        "descriptor_layout_bytes_covered": len(occupied),
    }


def macro_name(profile: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in profile.upper())


def render(data: dict[str, Any], report: dict[str, Any]) -> dict[Path, str]:
    digest = sha256(SOURCE)
    profiles = sorted(data["global_outstanding_by_profile"])
    scalar = {
        "SEQUENCE_WIDTH": int(data["sequence_width_bits"]),
        "GLOBAL_OUTSTANDING_DEFAULT": int(data["global_outstanding_default"]),
        "RX_REORDER_WINDOW": int(data["rx_reorder_window"]),
        "DUPLICATE_HISTORY_DEPTH": int(data["duplicate_history_depth"]),
        "MAX_RETRY": int(data["max_retry"]),
        "RTO_INITIAL_CYCLES": int(data["rto_initial_cycles"]),
        "RTO_MIN_CYCLES": int(data["rto_min_cycles"]),
        "RTO_MAX_CYCLES": int(data["rto_max_cycles"]),
        "ACK_AGGREGATION_FRAME_THRESHOLD": int(data["ack_aggregation_frame_threshold"]),
        "ACK_AGGREGATION_MAX_DELAY_CYCLES": int(data["ack_aggregation_max_delay_cycles"]),
        "ACK_CREDIT_LOW_WATERMARK": int(data["ack_credit_low_watermark"]),
        "MAX_ACK_PAYLOAD_BYTES": int(data["max_ack_payload_bytes"]),
        "SCHEDULER_WEIGHT_WIDTH": int(data["scheduler_weight_width"]),
        "STARVATION_BOUND": int(data["starvation_bound"]),
        "MAX_FRAME_BYTES": int(data["max_frame_bytes"]),
        "MAX_L1_PAYLOAD_BYTES": int(data["max_l1_payload_bytes"]),
        "RFAP_V1_USEFUL_CHUNK_BYTES": int(data["rfap_v1_useful_chunk_bytes"]),
        "TX_RING_DEPTH": int(data["tx_ring_depth"]),
        "RX_RING_DEPTH": int(data["rx_ring_depth"]),
        "DESCRIPTOR_BYTES": int(data["descriptor_bytes"]),
        "DESCRIPTOR_ALIGNMENT_BYTES": int(data["descriptor_alignment_bytes"]),
        "DESCRIPTOR_GENERATION_BITS": int(data["descriptor_generation_bits"]),
        "RING_INDEX_BITS": int(data["ring_index_bits"]),
        "SESSION_EPOCH_WIDTH": int(data["session_epoch_width"]),
        "PATH_EPOCH_WIDTH": int(data["path_epoch_width"]),
        "ACCEPTED_PREVIOUS_PATH_EPOCHS": int(data["accepted_previous_path_epochs"]),
        "STREAM_ID_WIDTH": int(data["stream_id_width"]),
        "OBJECT_ID_WIDTH": int(data["object_id_width"]),
        "AXIS_USER_WIDTH": int(data["axis_user_width"]),
    }
    sv = [
        "// Auto-generated from config/p8d_data_plane.yaml; do not edit.",
        "package ir_p8d_data_plane_pkg;",
        f"  localparam logic [255:0] P8D_CONFIG_SHA256 = 256'h{digest};",
        f"  localparam int unsigned P8D_LEGACY_MODE_VERSION = {int(data['legacy_mode_version'])};",
        f"  localparam int unsigned P8D_VNEXT_MODE_VERSION = {int(data['vnext_mode_version'])};",
    ]
    c = [
        "#pragma once", "#include <stdint.h>", "",
        "/* Auto-generated from config/p8d_data_plane.yaml; do not edit. */",
        f"#define P8D_CONFIG_SHA256 \"{digest}\"",
        f"#define P8D_LEGACY_MODE_VERSION {int(data['legacy_mode_version'])}u",
        f"#define P8D_VNEXT_MODE_VERSION {int(data['vnext_mode_version'])}u",
    ]
    py = [
        '"""Auto-generated P8D data-plane constants; do not edit."""',
        f"P8D_CONFIG_SHA256 = {digest!r}",
        f"P8D_LEGACY_MODE_VERSION = {int(data['legacy_mode_version'])}",
        f"P8D_VNEXT_MODE_VERSION = {int(data['vnext_mode_version'])}",
    ]
    for name, value in scalar.items():
        sv.append(f"  localparam int unsigned P8D_{name} = {value};")
        c.append(f"#define P8D_{name} {value}u")
        py.append(f"P8D_{name} = {value}")
    for profile in profiles:
        name = macro_name(profile)
        values = {
            "GLOBAL_OUTSTANDING": int(data["global_outstanding_by_profile"][profile]),
            "SACK_WINDOW_BITS": int(data["sack_window_bits_by_profile"][profile]),
            "AXIS_DATA_WIDTH": int(data["axis_data_width_by_profile"][profile]),
        }
        for suffix, value in values.items():
            sv.append(f"  localparam int unsigned P8D_{name}_{suffix} = {value};")
            c.append(f"#define P8D_{name}_{suffix} {value}u")
            py.append(f"P8D_{name}_{suffix} = {value}")
    weights = ", ".join(str(int(v)) for v in data["scheduler_default_weights"])
    py += [f"P8D_SCHEDULER_DEFAULT_WEIGHTS = ({weights})", ""]
    c += [
        "", "typedef enum {",
        "  P8D_DESC_FREE = 0, P8D_DESC_CPU_PREPARED = 1, P8D_DESC_HW_OWNED = 2,",
        "  P8D_DESC_HW_COMPLETED = 3, P8D_DESC_CPU_RECLAIMED = 4,",
        "  P8D_DESC_ERROR = 5, P8D_DESC_ABORTED = 6",
        "} p8d_descriptor_state_t;", "",
    ]
    sv += [
        "  typedef enum logic [3:0] {",
        "    P8D_TX_FREE=4'd0, P8D_TX_ALLOCATED=4'd1, P8D_TX_QUEUED=4'd2,",
        "    P8D_TX_SCHEDULED=4'd3, P8D_TX_IN_FLIGHT=4'd4, P8D_TX_ACKED=4'd5,",
        "    P8D_TX_RETRY_PENDING=4'd6, P8D_TX_ABORT_PENDING=4'd7,",
        "    P8D_TX_FAILED=4'd8, P8D_TX_RECLAIMABLE=4'd9",
        "  } p8d_tx_state_t;",
        "endpackage", "",
    ]
    descriptor_json = {
        "version": data["descriptor_layout"]["version"],
        "bytes": data["descriptor_bytes"],
        "alignment_bytes": data["descriptor_alignment_bytes"],
        "fields": data["descriptor_layout"]["fields"],
    }
    constants_json = {
        "schema_version": 1,
        "configuration_id": data["configuration_id"],
        "source_path": "config/p8d_data_plane.yaml",
        "source_sha256": digest,
        "validation": report,
        "profiles": {
            profile: {
                "global_outstanding": data["global_outstanding_by_profile"][profile],
                "sack_window_bits": data["sack_window_bits_by_profile"][profile],
                "axis_data_width": data["axis_data_width_by_profile"][profile],
            } for profile in profiles
        },
        "descriptor": descriptor_json,
        "config": data,
    }
    schema_json = {
        "schema_version": 1,
        "test_id": "P8D-CANONICAL-CONFIG-SCHEMA",
        "profile": "P8D_MULTI_PROFILE_OFFLINE",
        "status": report["status"],
        "source_path": "config/p8d_data_plane.yaml",
        "source_sha256": digest,
        "validation": report,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    md = [
        "# P8D Data-Plane Parameters", "",
        "> Generated from `config/p8d_data_plane.yaml`; do not edit by hand.", "",
        f"- Configuration: `{data['configuration_id']}`",
        f"- Source SHA256: `{digest}`",
        f"- Sequence width: `{data['sequence_width_bits']}` bits",
        f"- Descriptor: `{data['descriptor_bytes']}` bytes, `{data['descriptor_alignment_bytes']}`-byte aligned",
        f"- Scheduler: `{data['scheduler_type']}`", "",
        "| Profile | Global outstanding | SACK bits | AXI-Stream data width |", "|---|---:|---:|---:|",
    ]
    for profile in profiles:
        md.append(f"| `{profile}` | {data['global_outstanding_by_profile'][profile]} | "
                  f"{data['sack_window_bits_by_profile'][profile]} | {data['axis_data_width_by_profile'][profile]} |")
    md += [
        "", "## Bounded recovery", "",
        f"- Maximum retries: `{data['max_retry']}`",
        f"- RTO: `{data['rto_min_cycles']}` .. `{data['rto_max_cycles']}` cycles",
        f"- ACK threshold / maximum delay: `{data['ack_aggregation_frame_threshold']}` frames / "
        f"`{data['ack_aggregation_max_delay_cycles']}` cycles",
        f"- TX/RX ring depth: `{data['tx_ring_depth']}` / `{data['rx_ring_depth']}`",
        "", "## Safety boundary", "",
        "P8D consumes P8B mapping/path metadata and P8C safety admission. It does not create or override `GLOBAL_PERMIT`, clear physical duty history, or claim hardware DMA/DDR acceptance.", "",
    ]
    return {
        JSON_OUT: json.dumps(constants_json, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        SCHEMA_OUT: json.dumps(schema_json, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        SV_OUT: "\n".join(sv),
        C_OUT: "\n".join(c),
        PY_OUT: "\n".join(py),
        PY_INIT: '"""Generated protocol constants."""\n',
        MD_OUT: "\n".join(md),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    data = load_config()
    report = validate(data)
    outputs = render(data, report)
    stale: list[str] = []
    for path, content in outputs.items():
        if args.verify:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    summary = {
        "status": "FAIL" if stale else "PASS",
        "test_id": "P8D-CANONICAL-CONFIG",
        "profile": "P8D_MULTI_PROFILE_OFFLINE",
        "source_path": "config/p8d_data_plane.yaml",
        "source_sha256": sha256(SOURCE),
        "outputs": [path.relative_to(ROOT).as_posix() for path in outputs],
        "stale_outputs": stale,
        "validation": report,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    print(json.dumps(summary, sort_keys=True) if args.json_summary else
          f"P8D_DATA_PLANE_CONFIG={summary['status']}\nP8D_DATA_PLANE_CONFIG_SHA256={summary['source_sha256']}")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
