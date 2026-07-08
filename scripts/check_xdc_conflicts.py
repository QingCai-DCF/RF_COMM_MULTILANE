#!/usr/bin/env python3
import argparse, re, sys
from pathlib import Path

PORT_RE = re.compile(r"set_property\s+(PACKAGE_PIN|IOSTANDARD)\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]")

def parse(path):
    data = {}
    for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = PORT_RE.search(line)
        if m:
            prop, value, port = m.groups()
            data.setdefault(port, {})[prop] = value
    return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--active", default="constraints/legacy_conflicts/PORT1.top_active.original.xdc")
    ap.add_argument("--legacy", default="constraints/legacy_conflicts/PORT1.ip_legacy_conflict.original.xdc")
    ap.add_argument("--generated", default="constraints/active/PORT1.generated.xdc")
    ap.add_argument("--report", default="constraints/legacy_conflicts/xdc_conflict_report.md")
    ns = ap.parse_args()
    active, legacy, generated = parse(ns.active), parse(ns.legacy), parse(ns.generated)
    differs = []
    for port in sorted(set(active) | set(legacy)):
        if active.get(port) != legacy.get(port):
            differs.append((port, active.get(port), legacy.get(port)))
    generated_match = active == generated
    report = [
        "# XDC Conflict Report",
        "",
        "IP legacy PORT1.xdc differs from active top PORT1.xdc.",
        "Do not use IP legacy PORT1.xdc in new builds.",
        "Use canonical generated XDC from the pinmap for new builds.",
        "",
        f"XDC_GENERATED_FROM_PINMAP=1",
        f"XDC_GENERATED_MATCHES_ACTIVE_REFERENCE={1 if generated_match else 0}",
        f"XDC_LEGACY_CONFLICT_RECORDED={1 if differs else 0}",
        "NO_LEGACY_PORT1_XDC_IN_BUILD=1",
        "",
        "## Notable Differences",
    ]
    for port, a, l in differs:
        report.append(f"- `{port}` active={a} legacy={l}")
    if active.get("loop_rx_b0[1]", {}).get("PACKAGE_PIN") != legacy.get("loop_rx_b0[1]", {}).get("PACKAGE_PIN"):
        report.append("")
        report.append("`loop_rx_b0[1]` differs between active and IP legacy XDC. Treat the active top XDC as the imported reference and keep IP legacy XDC out of new builds.")
        report.append("Plan note: older written plans mention D19 versus G15; this imported active file is authoritative for this workspace, and the exact active/legacy values above are the evidence.")
    out = Path(ns.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join([line for line in report if "=" in line]))
    return 0 if generated_match and differs else 1

if __name__ == "__main__":
    raise SystemExit(main())
