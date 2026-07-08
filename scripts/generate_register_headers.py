#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "config/register_map/ir_axi_regs.yaml"
OUT = ROOT / "config/register_map/generated"

def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    regs = data["registers"]
    OUT.mkdir(parents=True, exist_ok=True)
    h = ["#pragma once", "#include <stdint.h>", ""]
    py = ["# Auto-generated from config/register_map/ir_axi_regs.yaml", ""]
    md = ["# IR AXI Register Contract", "", "| Name | Offset | Description |", "|---|---:|---|"]
    for r in regs:
        name = "IR_REG_" + r["name"]
        off = r["offset"]
        h.append(f"#define {name} {off}u")
        py.append(f"{name} = {off}")
        md.append(f"| `{r['name']}` | `{off}` | {r['description']} |")
    (OUT / "ir_regs.h").write_text("\n".join(h) + "\n", encoding="utf-8")
    (OUT / "ir_regs.py").write_text("\n".join(py) + "\n", encoding="utf-8")
    (OUT / "ir_regs.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (ROOT / "software/ps_driver/ir_regs.h").write_text((OUT / "ir_regs.h").read_text(encoding="utf-8"), encoding="utf-8")
    (ROOT / "docs/design/REGISTER_CONTRACT.md").write_text((OUT / "ir_regs.md").read_text(encoding="utf-8"), encoding="utf-8")
    print("REGISTER_MAP_SINGLE_SOURCE_CREATED=1")

if __name__ == "__main__":
    main()
