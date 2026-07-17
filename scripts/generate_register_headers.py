#!/usr/bin/env python3
"""Generate all software/document/RTL register-map consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "config/register_map/ir_axi_regs.yaml"
OUT = ROOT / "config/register_map/generated"
SV_OUT = ROOT / "rtl/generated/ir_register_map_defs.svh"


def source_hash() -> str:
    return hashlib.sha256(SRC.read_bytes()).hexdigest()


def version_value(version: str) -> int:
    match = re.fullmatch(r"P(\d+)([A-Z]?)-(\d+)", version)
    if not match:
        raise ValueError(f"unsupported register_map_version: {version}")
    stage = int(match.group(1))
    suffix = 0 if not match.group(2) else ord(match.group(2)) - ord("A") + 1
    revision = int(match.group(3))
    return (stage << 24) | (suffix << 16) | revision


def field_shift_width(field: dict[str, Any]) -> tuple[int, int]:
    if "bit" in field:
        return int(field["bit"]), 1
    return int(field["lsb"]), int(field["width"])


def render(data: dict[str, Any]) -> dict[Path, str]:
    regs = data["registers"]
    offsets = [int(reg["offset"], 0) for reg in regs]
    if len(offsets) != len(set(offsets)):
        raise ValueError("duplicate register offsets")
    if offsets != sorted(offsets):
        raise ValueError("register offsets must be monotonically increasing")

    map_hash = source_hash()
    map_hash_low = int(map_hash[-8:], 16)
    map_version_text = str(data.get("register_map_version", "P0-0"))
    map_version_value = version_value(map_version_text)

    h = [
        "#pragma once",
        "#include <stdint.h>",
        "",
        f"#define IR_REGISTER_MAP_VERSION 0x{map_version_value:08X}u",
        f"#define IR_REGISTER_MAP_HASH_LOW 0x{map_hash_low:08X}u",
        "",
    ]
    py = [
        "# Auto-generated from config/register_map/ir_axi_regs.yaml",
        f"IR_REGISTER_MAP_VERSION = 0x{map_version_value:08X}",
        f"IR_REGISTER_MAP_HASH_LOW = 0x{map_hash_low:08X}",
        "",
    ]
    sv = [
        "// Auto-generated from config/register_map/ir_axi_regs.yaml; do not edit.",
        "`ifndef IR_REGISTER_MAP_DEFS_SVH",
        "`define IR_REGISTER_MAP_DEFS_SVH",
        f"`define IR_REGISTER_MAP_VERSION 32'h{map_version_value:08X}",
        f"`define IR_REGISTER_MAP_HASH_LOW 32'h{map_hash_low:08X}",
    ]
    md = [
        "# IR AXI Register Contract",
        "",
        "> Generated from `config/register_map/ir_axi_regs.yaml`; do not edit by hand.",
        "",
        f"- Register map version: `{map_version_text}` (`0x{map_version_value:08X}`)",
        f"- Canonical source SHA256: `{map_hash}`",
        "- P0-P7 offsets and semantics are preserved; P8C is additive from `0x0400`.",
        "",
        "| Name | Offset | Access | Description |",
        "|---|---:|---|---|",
    ]

    for reg in regs:
        reg_name = str(reg["name"])
        macro = "IR_REG_" + reg_name
        off_text = str(reg["offset"])
        off_value = int(off_text, 0)
        access = str(reg.get("access", "LEGACY"))
        h.append(f"#define {macro} {off_text}u")
        py.append(f"{macro} = {off_text}")
        sv.append(f"`define {macro} 12'h{off_value:03X}")
        md.append(f"| `{reg_name}` | `{off_text}` | `{access}` | {reg['description']} |")
        for field in reg.get("fields", []):
            shift, width = field_shift_width(field)
            if shift < 0 or width < 1 or shift + width > 32:
                raise ValueError(f"invalid field range: {reg_name}.{field['name']}")
            mask = ((1 << width) - 1) << shift
            field_macro = f"IR_{reg_name}_{field['name']}"
            h.append(f"#define {field_macro}_SHIFT {shift}u")
            h.append(f"#define {field_macro}_MASK 0x{mask:08X}u")
            py.append(f"{field_macro}_SHIFT = {shift}")
            py.append(f"{field_macro}_MASK = 0x{mask:08X}")
            sv.append(f"`define {field_macro}_SHIFT {shift}")
            sv.append(f"`define {field_macro}_MASK 32'h{mask:08X}")

    sv.extend(["`endif", ""])
    manifest = {
        "schema_version": 1,
        "register_map_version": map_version_text,
        "register_map_version_value": f"0x{map_version_value:08X}",
        "source_path": "config/register_map/ir_axi_regs.yaml",
        "source_sha256": map_hash,
        "hash_low": f"0x{map_hash_low:08X}",
        "register_count": len(regs),
        "p8c_additive_base": "0x0400",
        "legacy_compatible": True,
    }
    outputs = {
        OUT / "ir_regs.h": "\n".join(h) + "\n",
        OUT / "ir_regs.py": "\n".join(py) + "\n",
        OUT / "ir_regs.md": "\n".join(md) + "\n",
        OUT / "ir_regs_manifest.json": json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        SV_OUT: "\n".join(sv),
    }
    outputs[ROOT / "software/ps_driver/ir_regs.h"] = outputs[OUT / "ir_regs.h"]
    outputs[ROOT / "docs/design/REGISTER_CONTRACT.md"] = outputs[OUT / "ir_regs.md"]
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(SRC.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2:
        raise SystemExit("register map schema_version must be 2")
    outputs = render(data)
    if not args.verify:
        OUT.mkdir(parents=True, exist_ok=True)
        SV_OUT.parent.mkdir(parents=True, exist_ok=True)
    for path, content in outputs.items():
        if args.verify:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"generated register artifact is stale: {path.relative_to(ROOT)}")
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    print("REGISTER_MAP_SINGLE_SOURCE_CREATED=1")
    print(f"REGISTER_MAP_SHA256={source_hash()}")
    print(f"REGISTER_MAP_VERSION={data['register_map_version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
