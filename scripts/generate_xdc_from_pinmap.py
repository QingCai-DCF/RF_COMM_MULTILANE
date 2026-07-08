#!/usr/bin/env python3
import argparse, csv
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pinmap", required=True)
    ap.add_argument("--out", required=True)
    ns = ap.parse_args()
    rows = list(csv.DictReader(open(ns.pinmap, encoding="utf-8")))
    lines = [
        "# Generated from board_profiles/ax7010_tfdu_j10_j11_pinmap.csv.",
        "# Do not hand-edit; update the pinmap and regenerate.",
    ]
    for row in rows:
        lines.append(f"set_property PACKAGE_PIN {row['package_pin']} [get_ports {{{row['port']}}}]")
        lines.append(f"set_property IOSTANDARD {row['iostandard']} [get_ports {{{row['port']}}}]")
    lines.append("")
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"CANONICAL_XDC_GENERATED=1 out={out}")

if __name__ == "__main__":
    main()
