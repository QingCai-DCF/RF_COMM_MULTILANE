#!/usr/bin/env python3
"""Generate P10.5 RTL, C, Python, register-doc, and capability consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/p10_5_dual_direction.yaml"
OUTPUTS = {
    "sv": ROOT / "rtl/generated/p10_5_dual_direction_pkg.sv",
    "c": ROOT / "software/ps_driver/p10_5_dual_direction_config.h",
    "py": ROOT / "config/generated/p10_5_dual_direction.py",
    "doc": ROOT / "docs/design/P10_5_DUAL_DIRECTION_CAPABILITY.md",
    "caps": ROOT / "config/generated/p10_5_capability_table.json",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value), 0)


def render(data: dict[str, Any]) -> dict[str, str]:
    source_sha = sha256(SOURCE)
    lane_count = as_int(data["lane_count"])
    active = as_int(data["active_lane_mask"])
    f2r = as_int(data["f_to_r_lane_mask"])
    r2f = as_int(data["r_to_f_lane_mask"])
    per = data["per_direction"]
    ctrl = data["control"]
    wire = data["wire"]
    perf = data["performance_targets"]
    runtime = data["runtime"]
    if lane_count != 4 or active != 0xF:
        raise ValueError("P10.5 current AX7020 scope requires four active lanes")
    if f2r == 0 or r2f == 0 or (f2r & r2f) or ((f2r | r2f) & ~active):
        raise ValueError("P10.5 primary direction masks must be nonzero, disjoint subsets")
    if as_int(per["sack_window"]) != 32 or as_int(per["outstanding"]) != 32:
        raise ValueError("P10.5 freezes the verified 32-frame SR/SACK context per direction")
    if as_int(runtime["autonomous_dual_stream_command"]) != 15 or \
            as_int(runtime["maximum_stream_bytes"]) > 0x7FFFFFFF or \
            as_int(runtime["internal_object_bytes"]) != 262144 or \
            as_int(runtime["descriptor_bytes"]) != 65536 or \
            as_int(runtime["ring_depth"]) != 32 or \
            as_int(runtime["buffer_count"]) != 4 or \
            as_int(runtime["descriptor_batch"]) != 8:
        raise ValueError("P10.5 autonomous runtime contract is not the frozen SG design")

    sv = f"""// Generated from config/p10_5_dual_direction.yaml; do not edit.
package p10_5_dual_direction_pkg;
  localparam logic [31:0] P10_5_CAPABILITY_VERSION = 32'h0000_0001;
  localparam logic [31:0] P10_5_CAPABILITY_WORD = 32'h5035_021F;
  localparam logic [31:0] P10_5_CONFIG_HASH_LOW = 32'h{source_sha[-8:].upper()};
  localparam int P10_5_LANE_COUNT = {lane_count};
  localparam logic [3:0] P10_5_ACTIVE_LANE_MASK = 4'h{active:X};
  localparam logic [3:0] P10_5_F_TO_R_LANE_MASK = 4'h{f2r:X};
  localparam logic [3:0] P10_5_R_TO_F_LANE_MASK = 4'h{r2f:X};
  localparam int P10_5_ROLE_EPOCH_WIDTH = {as_int(data['role_epoch_width'])};
  localparam int P10_5_SEQUENCE_WIDTH = {as_int(per['sequence_width'])};
  localparam int P10_5_OUTSTANDING = {as_int(per['outstanding'])};
  localparam int P10_5_SACK_BITS = {as_int(per['sack_window'])};
  localparam int P10_5_ACK_THRESHOLD = {as_int(per['ack_threshold'])};
  localparam int P10_5_ACK_MAX_DELAY_CYCLES = {as_int(per['ack_max_delay_cycles'])};
  localparam logic P10_5_PIGGYBACK_ENABLE = 1'b{1 if ctrl['piggyback_enable'] else 0};
  localparam logic P10_5_CONTROL_ONLY_ACK_ENABLE = 1'b{1 if ctrl['control_only_ack_fallback'] else 0};
  typedef enum logic {{ P10_5_DIR_F_TO_R = 1'b0, P10_5_DIR_R_TO_F = 1'b1 }} p10_5_direction_t;
  typedef enum logic {{ P10_5_MODE_LEGACY = 1'b0, P10_5_MODE_SPLIT = 1'b1 }} p10_5_mode_t;
endpackage
"""
    c = f"""#pragma once
#include <stdint.h>
/* Generated from config/p10_5_dual_direction.yaml; do not edit. */
#define P10_5_CAPABILITY_VERSION UINT32_C(0x00000001)
#define P10_5_CAPABILITY_WORD UINT32_C(0x5035021F)
#define P10_5_CONFIG_HASH_LOW UINT32_C(0x{source_sha[-8:].upper()})
#define P10_5_LANE_COUNT UINT32_C({lane_count})
#define P10_5_ACTIVE_LANE_MASK UINT32_C(0x{active:X})
#define P10_5_F_TO_R_LANE_MASK UINT32_C(0x{f2r:X})
#define P10_5_R_TO_F_LANE_MASK UINT32_C(0x{r2f:X})
#define P10_5_MODE_LEGACY_BUNDLE_HALF_DUPLEX UINT32_C(0)
#define P10_5_MODE_SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL UINT32_C(1)
#define P10_5_DIRECTION_F_TO_R UINT32_C(0)
#define P10_5_DIRECTION_R_TO_F UINT32_C(1)
#define P10_5_OUTSTANDING UINT32_C({as_int(per['outstanding'])})
#define P10_5_SACK_BITS UINT32_C({as_int(per['sack_window'])})
#define P10_5_ACK_THRESHOLD UINT32_C({as_int(per['ack_threshold'])})
#define P10_5_ACK_MAX_DELAY_CYCLES UINT32_C({as_int(per['ack_max_delay_cycles'])})
#define P10_5_TARGET_GOODPUT_BPS UINT32_C({as_int(perf['application_goodput_bps_per_direction'])})
#define P10_5_FORMAL_RUNTIME_SECONDS UINT32_C({as_int(data['formal_runtime_seconds'])})
#define P10_5_AUTONOMOUS_DUAL_STREAM_COMMAND UINT32_C({as_int(runtime['autonomous_dual_stream_command'])})
#define P10_5_MAX_STREAM_BYTES UINT32_C(0x{as_int(runtime['maximum_stream_bytes']):08X})
#define P10_5_INTERNAL_OBJECT_BYTES UINT32_C({as_int(runtime['internal_object_bytes'])})
#define P10_5_DESCRIPTOR_BYTES UINT32_C({as_int(runtime['descriptor_bytes'])})
#define P10_5_RUNTIME_RING_DEPTH UINT32_C({as_int(runtime['ring_depth'])})
#define P10_5_RUNTIME_BUFFER_COUNT UINT32_C({as_int(runtime['buffer_count'])})
#define P10_5_RUNTIME_DESCRIPTOR_BATCH UINT32_C({as_int(runtime['descriptor_batch'])})
"""
    py = f'''# Generated from config/p10_5_dual_direction.yaml; do not edit.
P10_5_CAPABILITY_VERSION = 1
P10_5_CAPABILITY_WORD = 0x5035021F
P10_5_CONFIG_SHA256 = "{source_sha}"
P10_5_CONFIG_HASH_LOW = 0x{source_sha[-8:].upper()}
LANE_COUNT = {lane_count}
ACTIVE_LANE_MASK = 0x{active:X}
F_TO_R_LANE_MASK = 0x{f2r:X}
R_TO_F_LANE_MASK = 0x{r2f:X}
MODE_LEGACY_BUNDLE_HALF_DUPLEX = 0
MODE_SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL = 1
DIR_F_TO_R = 0
DIR_R_TO_F = 1
OUTSTANDING = {as_int(per['outstanding'])}
SACK_BITS = {as_int(per['sack_window'])}
ACK_THRESHOLD = {as_int(per['ack_threshold'])}
ACK_MAX_DELAY_CYCLES = {as_int(per['ack_max_delay_cycles'])}
TARGET_GOODPUT_BPS = {as_int(perf['application_goodput_bps_per_direction'])}
FORMAL_RUNTIME_SECONDS = {as_int(data['formal_runtime_seconds'])}
AUTONOMOUS_DUAL_STREAM_COMMAND = {as_int(runtime['autonomous_dual_stream_command'])}
MAX_STREAM_BYTES = 0x{as_int(runtime['maximum_stream_bytes']):08X}
INTERNAL_OBJECT_BYTES = {as_int(runtime['internal_object_bytes'])}
DESCRIPTOR_BYTES = {as_int(runtime['descriptor_bytes'])}
RUNTIME_RING_DEPTH = {as_int(runtime['ring_depth'])}
RUNTIME_BUFFER_COUNT = {as_int(runtime['buffer_count'])}
RUNTIME_DESCRIPTOR_BATCH = {as_int(runtime['descriptor_batch'])}

def validate_masks(active, f_to_r, r_to_f, require_both=True):
    known = (1 << LANE_COUNT) - 1
    if active & ~known or f_to_r & ~known or r_to_f & ~known:
        return False, "UNKNOWN_LANE_BIT"
    if f_to_r & r_to_f:
        return False, "ROLE_MASK_OVERLAP"
    if (f_to_r | r_to_f) & ~active:
        return False, "ROLE_MASK_OUTSIDE_ACTIVE"
    if require_both and (not f_to_r or not r_to_f):
        return False, "EMPTY_REQUIRED_DIRECTION"
    return True, "NONE"
'''
    caps = {
        "schema_version": 1,
        "capability": data["capability_name"],
        "protocol_capability_version": data["protocol_capability_version"],
        "config_sha256": source_sha,
        "max_lane_count": lane_count,
        "max_tx_lanes": lane_count - 1,
        "max_rx_lanes": lane_count - 1,
        "mask_width": lane_count,
        "per_direction_outstanding": per["outstanding"],
        "per_direction_sack_width": per["sack_window"],
        "piggyback_support": bool(ctrl["piggyback_enable"]),
        "control_only_ack_support": bool(ctrl["control_only_ack_fallback"]),
        "role_epoch_support": True,
        "legacy_half_duplex_support": True,
        "primary_masks": {"active": active, "f_to_r": f2r, "r_to_f": r2f},
        "autonomous_runtime": {
            "command": as_int(runtime["autonomous_dual_stream_command"]),
            "maximum_stream_bytes": as_int(runtime["maximum_stream_bytes"]),
            "internal_object_bytes": as_int(runtime["internal_object_bytes"]),
            "descriptor_bytes": as_int(runtime["descriptor_bytes"]),
            "ring_depth": as_int(runtime["ring_depth"]),
            "buffer_count": as_int(runtime["buffer_count"]),
            "descriptor_batch": as_int(runtime["descriptor_batch"]),
        },
    }
    doc = f"""# P10.5 Dual-Direction Capability

> Generated from `config/p10_5_dual_direction.yaml`; do not edit by hand.

- Capability: `{data['capability_name']}`
- Capability version: `{data['protocol_capability_version']}`
- Configuration SHA256: `{source_sha}`
- Modes: `LEGACY_BUNDLE_HALF_DUPLEX`, `SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL`
- Primary masks: active `0x{active:X}`, F→R `0x{f2r:X}`, R→F `0x{r2f:X}`
- Per-direction selective-repeat/SACK: `{per['outstanding']}` / `{per['sack_window']}`
- ACK: CRC-protected DATA piggyback with bounded control-only fallback
- Autonomous runtime: mailbox command `{runtime['autonomous_dual_stream_command']}`, simultaneous MM2S/S2MM, up to `0x{as_int(runtime['maximum_stream_bytes']):08X}` bytes per direction
- Safety: one active-high `GLOBAL_PERMIT` per endpoint; no direction or lane permit was added
- Compatibility: legacy half-duplex remains the reset/default mode
"""
    return {"sv": sv, "c": c, "py": py, "doc": doc,
            "caps": json.dumps(caps, indent=2, sort_keys=True) + "\n"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    rendered = render(data)
    errors: list[str] = []
    for key, path in OUTPUTS.items():
        content = rendered[key]
        if args.verify:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                errors.append(path.relative_to(ROOT).as_posix())
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="\n")
    if errors:
        print("P10_5_CONFIG_GENERATION=FAIL")
        print("MISMATCH=" + ",".join(errors))
        return 1
    print("P10_5_CONFIG_GENERATION=PASS")
    print("CONFIG_SHA256=" + sha256(SOURCE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
