#!/usr/bin/env python3
"""Generate all P8E profile consumers from the canonical build matrix."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "config/p8e_build_matrix.yaml"
JSON_OUT = ROOT / "config/generated/p8e_build_profiles.json"
SCHEMA_OUT = ROOT / "config/generated/p8e_build_schema_validation.json"
SV_OUT = ROOT / "rtl/generated/ir_p8e_profile_pkg.sv"
C_OUT = ROOT / "software/ps_driver/p8e_profile_config.h"
PY_OUT = ROOT / "tools/generated/p8e_profile_config.py"
MD_OUT = ROOT / "docs/generated/P8E_BUILD_PROFILES.md"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def symbol(profile_id: str) -> str:
    mapping = {
        "Z7010_2LANE_DEV_IMPLEMENTATION": "Z7010_2LANE_DEV",
        "Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION": "Z7020_FIXED_8LANE",
        "Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION": "Z7020_ROTATING_8LANE",
    }
    return mapping[profile_id]


def load_validate() -> tuple[dict[str, Any], dict[str, Any]]:
    data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    errors: list[str] = []
    if not isinstance(data, dict):
        raise ValueError("P8E build matrix must be a mapping")
    profiles = data.get("profiles", [])
    expected = {
        "Z7010_2LANE_DEV_IMPLEMENTATION",
        "Z7020_FIXED_8LANE_32MODULE_CORE_IMPLEMENTATION",
        "Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION",
    }
    ids = {item.get("profile_id") for item in profiles}
    if ids != expected:
        errors.append(f"implementation profile set mismatch: {sorted(ids)}")
    required = {
        "profile_id", "profile_version", "software_profile_id", "endpoint_role_code",
        "part", "endpoint_role", "lane_count", "physical_module_count", "tx_window",
        "rx_window", "sack_bits", "descriptor_ring_depth", "axis_data_width",
        "clock_target_mhz", "top_module", "source_manifest", "board_pinmap",
        "board_xdc", "status_scope",
    }
    software_ids: set[int] = set()
    for item in profiles:
        missing = required - set(item)
        if missing:
            errors.append(f"{item.get('profile_id')}: missing {sorted(missing)}")
            continue
        profile_id = str(item["profile_id"])
        try:
            symbol(profile_id)
        except KeyError:
            errors.append(f"{profile_id}: no generated symbol mapping")
        software_id = int(item["software_profile_id"])
        if software_id in software_ids:
            errors.append(f"duplicate software_profile_id 0x{software_id:08X}")
        software_ids.add(software_id)
        lane_count = int(item["lane_count"])
        tx_window = int(item["tx_window"])
        rx_window = int(item["rx_window"])
        sack_bits = int(item["sack_bits"])
        if lane_count not in (2, 8):
            errors.append(f"{profile_id}: lane_count must be 2 or 8")
        if min(tx_window, rx_window, sack_bits) < 32:
            errors.append(f"{profile_id}: 32 outstanding/SACK minimum violated")
        if sack_bits > tx_window or tx_window not in (32, 64) or rx_window not in (32, 64):
            errors.append(f"{profile_id}: invalid window/SACK relationship")
        if int(item["clock_target_mhz"]) != 64:
            errors.append(f"{profile_id}: canonical 64 MHz target changed")
        if int(item["descriptor_ring_depth"]) != 64:
            errors.append(f"{profile_id}: descriptor ring depth must remain 64")
        if int(item["axis_data_width"]) != 64:
            errors.append(f"{profile_id}: P8E AXIS width must remain 64")
        is_z7020 = str(item["part"]).startswith("xc7z020")
        if is_z7020 and (item["board_pinmap"] != "PENDING_D12" or item["board_xdc"] != "PENDING_D12"):
            errors.append(f"{profile_id}: Z7020 pins/XDC must remain PENDING_D12")
        if not (ROOT / str(item["source_manifest"])).is_file():
            errors.append(f"{profile_id}: source manifest missing")
    strategies = data.get("strategies", [])
    if {item.get("id") for item in strategies} != {"Default", "Performance_Explore"}:
        errors.append("Default and Performance_Explore strategies are mandatory")
    for item in strategies:
        for key in ("synth_directive", "place_directive", "phys_opt_directive", "route_directive", "seed"):
            if key not in item:
                errors.append(f"strategy {item.get('id')}: missing {key}")
    if errors:
        raise ValueError("; ".join(errors))
    return data, {
        "status": "PASS",
        "profile_count": len(profiles),
        "strategy_count": len(strategies),
        "minimum_outstanding": min(int(item["tx_window"]) for item in profiles),
        "minimum_sack_bits": min(int(item["sack_bits"]) for item in profiles),
        "z7020_board_inputs_pending_d12": True,
        "common_source_core": data["common_source_core"],
    }


def render(data: dict[str, Any], validation: dict[str, Any]) -> dict[Path, str]:
    source_sha = digest(SOURCE)
    hash_low = int(source_sha[-8:], 16)
    hash_high = int(source_sha[-16:-8], 16)
    profiles = sorted(data["profiles"], key=lambda item: item["profile_id"])
    sv = [
        "// Auto-generated from config/p8e_build_matrix.yaml; do not edit.",
        "package ir_p8e_profile_pkg;",
        f"  localparam logic [255:0] P8E_BUILD_MATRIX_SHA256 = 256'h{source_sha};",
        f"  localparam int unsigned P8E_BUILD_HASH_LOW = 32'h{hash_low:08x};",
        f"  localparam int unsigned P8E_BUILD_HASH_HIGH = 32'h{hash_high:08x};",
    ]
    c = [
        "#pragma once", "", "/* Auto-generated from config/p8e_build_matrix.yaml; do not edit. */",
        f"#define P8E_BUILD_MATRIX_SHA256 \"{source_sha}\"",
        f"#define P8E_BUILD_HASH_LOW 0x{hash_low:08X}u",
        f"#define P8E_BUILD_HASH_HIGH 0x{hash_high:08X}u",
    ]
    py = [
        '\"\"\"Auto-generated P8E build profile constants; do not edit.\"\"\"',
        f"P8E_BUILD_MATRIX_SHA256 = {source_sha!r}",
        f"P8E_BUILD_HASH_LOW = 0x{hash_low:08X}",
        f"P8E_BUILD_HASH_HIGH = 0x{hash_high:08X}",
        "PROFILES = {",
    ]
    normalized_profiles: dict[str, Any] = {}
    for profile in profiles:
        name = symbol(profile["profile_id"])
        values = {
            "PROFILE_ID": int(profile["software_profile_id"]),
            "PROFILE_VERSION": int(profile["profile_version"]),
            "ENDPOINT_ROLE": int(profile["endpoint_role_code"]),
            "LANE_COUNT": int(profile["lane_count"]),
            "PHYSICAL_MODULE_COUNT": int(profile["physical_module_count"]),
            "TX_WINDOW": int(profile["tx_window"]),
            "RX_WINDOW": int(profile["rx_window"]),
            "SACK_BITS": int(profile["sack_bits"]),
            "DESCRIPTOR_RING_DEPTH": int(profile["descriptor_ring_depth"]),
            "AXIS_DATA_WIDTH": int(profile["axis_data_width"]),
            "CLOCK_TARGET_MHZ": int(profile["clock_target_mhz"]),
        }
        for suffix, value in values.items():
            if suffix == "PROFILE_ID":
                sv.append(f"  localparam int unsigned P8E_{name}_{suffix} = 32'h{value:08x};")
                c.append(f"#define P8E_{name}_{suffix} 0x{value:08X}u")
            else:
                sv.append(f"  localparam int unsigned P8E_{name}_{suffix} = {value};")
                c.append(f"#define P8E_{name}_{suffix} {value}u")
        normalized_profiles[profile["profile_id"]] = {
            **values,
            "part": profile["part"],
            "top_module": profile["top_module"],
            "source_manifest": profile["source_manifest"],
            "board_pinmap": profile["board_pinmap"],
            "board_xdc": profile["board_xdc"],
        }
        py.append(f"    {profile['profile_id']!r}: {normalized_profiles[profile['profile_id']]!r},")
    sv += ["endpackage", ""]
    c.append("")
    py += ["}", ""]
    normalized = {
        "schema_version": 1,
        "source_path": "config/p8e_build_matrix.yaml",
        "source_sha256": source_sha,
        "validation": validation,
        "strategies": data["strategies"],
        "profiles": normalized_profiles,
    }
    schema = {
        "schema_version": 1,
        "test_id": "P8E-CANONICAL-BUILD-CONFIG",
        "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "status": "PASS",
        "source_path": "config/p8e_build_matrix.yaml",
        "source_sha256": source_sha,
        "validation": validation,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    md = [
        "# P8E Build Profiles", "",
        "> Generated from `config/p8e_build_matrix.yaml`; do not edit by hand.", "",
        f"- Source SHA256: `{source_sha}`",
        f"- Common-source core: `{data['common_source_core']}`",
        "- Hardware scope: `NONE`", "",
        "| Profile | Part | Role | Lanes | Modules | TX/RX/SACK | Board input |", "|---|---|---|---:|---:|---|---|",
    ]
    for profile in profiles:
        board = profile["board_xdc"]
        md.append(
            f"| `{profile['profile_id']}` | `{profile['part']}` | `{profile['endpoint_role']}` | "
            f"{profile['lane_count']} | {profile['physical_module_count']} | "
            f"{profile['tx_window']}/{profile['rx_window']}/{profile['sack_bits']} | `{board}` |"
        )
    md += ["", "The two exact-part Z7020 profiles intentionally retain board pins and board I/O timing as `PENDING_D12`.", ""]
    return {
        JSON_OUT: json.dumps(normalized, indent=2, sort_keys=True) + "\n",
        SCHEMA_OUT: json.dumps(schema, indent=2, sort_keys=True) + "\n",
        SV_OUT: "\n".join(sv),
        C_OUT: "\n".join(c),
        PY_OUT: "\n".join(py),
        MD_OUT: "\n".join(md),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    data, validation = load_validate()
    outputs = render(data, validation)
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
        "test_id": "P8E-CANONICAL-BUILD-CONFIG",
        "source_path": "config/p8e_build_matrix.yaml",
        "source_sha256": digest(SOURCE),
        "outputs": [path.relative_to(ROOT).as_posix() for path in outputs],
        "stale_outputs": stale,
        "validation": validation,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
    }
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P8E_BUILD_CONFIG={summary['status']}")
        print(f"P8E_BUILD_MATRIX_SHA256={summary['source_sha256']}")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
