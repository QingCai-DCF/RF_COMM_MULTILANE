#!/usr/bin/env python3
import argparse, csv, json, re
from pathlib import Path

PORT_RE = re.compile(r"set_property\s+(PACKAGE_PIN|IOSTANDARD)\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]")

SIGNAL_MAP = {
    "ir_mode_out_0": ("A", "Mode"),
    "ir_rx_in_0": ("A", "Rxd"),
    "ir_sd_0": ("A", "SD"),
    "ir_tx_out_0": ("A", "Txd"),
    "loop_mode_b0": ("B", "Mode"),
    "loop_rx_b0": ("B", "Rxd"),
    "loop_sd_b0": ("B", "SD"),
    "loop_tx_b0": ("B", "Txd"),
}

def parse_port(port):
    m = re.match(r"([A-Za-z0-9_]+)\[(\d+)\]", port)
    base, lane = (m.group(1), int(m.group(2))) if m else (port, 0)
    side, signal = SIGNAL_MAP.get(base, ("UNKNOWN", base))
    return lane, side, signal

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xdc", required=True)
    ap.add_argument("--out", required=True)
    ns = ap.parse_args()
    data = {}
    for line in Path(ns.xdc).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = PORT_RE.search(line)
        if not m:
            continue
        prop, value, port = m.groups()
        data.setdefault(port, {})[prop] = value
    rows = []
    for port in sorted(data):
        lane, side, signal = parse_port(port)
        rows.append({
            "lane": lane,
            "side": side,
            "logical_endpoint": f"lane{lane}_{side}",
            "signal": signal,
            "port": port,
            "package_pin": data[port].get("PACKAGE_PIN", ""),
            "iostandard": data[port].get("IOSTANDARD", "LVCMOS33"),
            "connector": "J10" if lane == 0 else "J11",
            "notes": "generated from active top PORT1.xdc",
        })
    out = Path(ns.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lane","side","logical_endpoint","signal","port","package_pin","iostandard","connector","notes"])
        writer.writeheader()
        writer.writerows(rows)
    json_out = out.with_suffix(".json")
    json_out.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PINMAP_GENERATED=1 rows={len(rows)} out={out}")

if __name__ == "__main__":
    main()
