#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p5_lib import FAIL, GENERATED, PASS, ROOT, load_json, write_markdown


FORBIDDEN_PASS_PHRASES = [
    "ETHERNET_ACCEPTANCE: PASS",
    "PC_TO_PS_TCP: PASS",
    "DHCP_ACCEPTANCE: PASS",
    "STATIC_IP_ACCEPTANCE: PASS",
    "REAL_ETHERNET: PASS",
    "TCP_BOARD_LINK: PASS",
]


def _scan_text(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [phrase for phrase in FORBIDDEN_PASS_PHRASES if phrase in text]


def check() -> dict:
    profiles = sorted((ROOT / "profiles" / "p5").glob("*.json"))
    failures = []
    for profile in profiles:
        data = load_json(profile)
        if data.get("network_cable_connected") is not False:
            failures.append(f"{profile}: network_cable_connected is not false")
        if data.get("ethernet_enabled") is not False:
            failures.append(f"{profile}: ethernet_enabled is not false")
    for relpath in [
        "PROJECT_STATUS.md",
        "docs/PROJECT_STATUS.md",
        "README.md",
        "evidence/generated/p5_2lane_protocol_stabilization_summary.md",
    ]:
        hits = _scan_text(ROOT / relpath)
        failures.extend(f"{relpath}: forbidden Ethernet PASS phrase `{hit}`" for hit in hits)

    result = PASS if not failures else FAIL
    lines = [
        f"NO_ETHERNET_GATE: {result}",
        "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
        "NETWORK_CABLE_CONNECTED: false",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Checks",
        "",
        "- Real TCP, DHCP, static-IP, and board-IP Ethernet acceptance are deferred.",
        "- Host offline stub, mock transport, file transport, JTAG/AXI payload injection, and PS local static tests remain allowed.",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(
        GENERATED / "p5_no_ethernet_hardware_tests_summary.md",
        "P5 No Ethernet Hardware Tests Summary",
        result,
        "Ethernet runtime acceptance is deferred because no network cable is connected" if result == PASS else "Ethernet gate found forbidden pass claims",
        lines,
    )
    return {
        "NO_ETHERNET_GATE": result,
        "ETHERNET_ACCEPTANCE": "DEFERRED_NO_NETWORK_CABLE",
        "failures": failures,
        "summary": "evidence/generated/p5_no_ethernet_hardware_tests_summary.md",
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check P5 does not claim or run real Ethernet hardware acceptance.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = check()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"NO_ETHERNET_GATE: {payload['NO_ETHERNET_GATE']}")
        print("ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE")
        print("NO_HARDWARE_ACTIONS_EXECUTED: true")
    return 0 if payload["NO_ETHERNET_GATE"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
