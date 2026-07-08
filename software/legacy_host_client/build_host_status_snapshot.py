#!/usr/bin/env python3
"""Build a PC-side status snapshot from RF_COMM offline evidence.

This is an offline host-view report generator. It does not open sockets,
program hardware, write UART, or drive TFDU boards. Its purpose is to prove
that the host software can present the device/link/TX/RX/error/statistics
fields required by the target from current logs and model outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_acceptance_log import analyze_csv


ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "reports"
HOST_LOGS = ROOT / "software" / "host_client" / "logs"


@dataclass
class SnapshotVerdict:
    overall: str
    host_log_ok: bool
    no_ethernet_gate_ok: bool
    two_ax7010_model_ok: bool
    display_fields_ok: bool
    no_hardware_action: bool
    failures: list[str]


def latest(pattern: str, base: Path = ROOT) -> Path | None:
    files = [path for path in base.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def read_text(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def parse_key_values(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)=('[^']*'|[^ \r\n]+)", text):
        value = match.group(2)
        if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
            value = value[1:-1]
        pairs[match.group(1)] = value
    return pairs


def load_json(path: Path | None) -> dict[str, object]:
    if path is None:
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value), 0)
    except (TypeError, ValueError):
        return default


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return default


def rel(path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def build_snapshot(args: argparse.Namespace) -> dict[str, object]:
    host_csv = args.csv_log or latest("offline_mock_single_lane_*.csv", HOST_LOGS)
    no_eth_summary = args.no_ethernet_summary or latest("reports/no_ethernet_network_offline_acceptance_*.summary.txt")
    two_ax_json = args.two_ax7010_json or REPORTS / "two_ax7010_end_to_end_model_current.json"

    failures: list[str] = []
    if host_csv is None:
        failures.append("missing host CSV log")
        host_analysis = None
    else:
        host_analysis = analyze_csv(host_csv)

    no_eth_text = read_text(no_eth_summary)
    no_eth_fields = parse_key_values(no_eth_text)
    two_ax = load_json(two_ax_json)
    two_link = two_ax.get("link", {}) if isinstance(two_ax.get("link"), dict) else {}
    two_config = two_ax.get("config", {}) if isinstance(two_ax.get("config"), dict) else {}
    fdx_config = two_config.get("fdx_4plus4", {}) if isinstance(two_config.get("fdx_4plus4"), dict) else {}

    host_log_ok = False
    host_summary: dict[str, str] = {}
    if host_analysis is not None:
        host_summary = host_analysis.summary
        host_log_ok = (
            "ACCEPTANCE_PASS" in host_analysis.markers
            and host_analysis.effective_error_count() == 0
            and host_analysis.summary_int("pending") == 0
            and host_analysis.summary_int("ack_timeouts") == 0
            and host_analysis.summary_int("acked_tx") == host_analysis.summary_int("tx_packets")
            and host_analysis.summary_int("rx_data") > 0
        )
        if not host_log_ok:
            failures.append("host log does not prove clean accepted traffic")

    no_ethernet_gate_ok = (
        no_eth_fields.get("NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS") == "1"
        and no_eth_fields.get("NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT") == "11"
        and no_eth_fields.get("NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT") == "0"
        and no_eth_fields.get("NO_REAL_BOARD_TCP_DHCP") == "1"
        and no_eth_fields.get("NO_REAL_TWO_AX7010_TRAFFIC") == "1"
    )
    if not no_ethernet_gate_ok:
        failures.append("latest no-Ethernet gate is missing or not PASS")

    no_hardware_action = (
        no_eth_fields.get("NO_HARDWARE_PROGRAMMING") == "1"
        and no_eth_fields.get("NO_UART_WRITE") == "1"
        and no_eth_fields.get("NO_TFDU_DRIVE") == "1"
    )
    if not no_hardware_action:
        failures.append("no-hardware-action markers are missing")

    two_ax7010_model_ok = (
        two_ax.get("result") == "TWO_AX7010_END_TO_END_OFFLINE_PASS"
        and as_int(two_link.get("hdx_tx_lane_coverage")) == 0xFF
        and as_int(two_link.get("hdx_rx_lane_coverage")) == 0xFF
        and as_int(two_link.get("fdx_a_to_b_tx_lane_coverage")) == 0x0F
        and as_int(two_link.get("fdx_a_to_b_rx_lane_coverage")) == 0x0F
        and as_int(two_link.get("fdx_b_to_a_tx_lane_coverage")) == 0xF0
        and as_int(two_link.get("fdx_b_to_a_rx_lane_coverage")) == 0xF0
        and as_int(two_link.get("reconnect_queued_rx")) > 0
    )
    if not two_ax7010_model_ok:
        failures.append("two-AX7010 model does not prove 8-lane HDX plus 4+4 FDX coverage")

    display_fields = {
        "device_connection_state": "OFFLINE_MOCK_CONNECTED" if host_log_ok else "UNKNOWN",
        "network_state": "REAL_BOARD_TCP_DHCP_DEFERRED_NO_ETHERNET" if no_ethernet_gate_ok else "UNKNOWN",
        "ip_address": "NOT_AVAILABLE_NO_ETHERNET",
        "tcp_reconnect_state": "OFFLINE_RECONNECT_COVERED" if no_ethernet_gate_ok else "UNKNOWN",
        "tx_packets": host_summary.get("tx_packets", "0"),
        "tx_bytes": host_summary.get("tx_bytes", "0"),
        "tx_mbps": host_summary.get("tx_mbps", "0"),
        "acked_tx": host_summary.get("acked_tx", "0"),
        "failed_tx": host_summary.get("failed_tx", "0"),
        "ack_timeouts": host_summary.get("ack_timeouts", "0"),
        "rx_packets": host_summary.get("rx_data", "0"),
        "rx_bytes": host_summary.get("rx_data_bytes", "0"),
        "rx_mbps": host_summary.get("rx_mbps", "0"),
        "error_frames": host_summary.get("errors", "0"),
        "pending_frames": host_summary.get("pending", "0"),
        "rtt_min_ms": host_summary.get("rtt_min_ms", "nan"),
        "rtt_avg_ms": host_summary.get("rtt_avg_ms", "nan"),
        "rtt_max_ms": host_summary.get("rtt_max_ms", "nan"),
        "last_error": host_summary.get("last_error", ""),
        "hdx_tx_lane_coverage": f"0x{as_int(two_link.get('hdx_tx_lane_coverage')):02x}",
        "hdx_rx_lane_coverage": f"0x{as_int(two_link.get('hdx_rx_lane_coverage')):02x}",
        "fdx_a_to_b_tx_lane_coverage": f"0x{as_int(two_link.get('fdx_a_to_b_tx_lane_coverage')):02x}",
        "fdx_b_to_a_tx_lane_coverage": f"0x{as_int(two_link.get('fdx_b_to_a_tx_lane_coverage')):02x}",
        "route_probe_events": str(as_int(two_link.get("route_probe_events"))),
        "reconnect_queued_rx": str(as_int(two_link.get("reconnect_queued_rx"))),
        "fdx_config_a_tx_lane_mask": str(fdx_config.get("a_tx_lane_mask", "")),
        "fdx_config_b_tx_lane_mask": str(fdx_config.get("b_tx_lane_mask", "")),
    }

    required_display_fields = (
        "device_connection_state",
        "network_state",
        "ip_address",
        "tx_packets",
        "rx_packets",
        "error_frames",
        "pending_frames",
        "rtt_avg_ms",
        "hdx_tx_lane_coverage",
        "fdx_a_to_b_tx_lane_coverage",
        "fdx_b_to_a_tx_lane_coverage",
        "reconnect_queued_rx",
    )
    display_fields_ok = all(display_fields.get(field, "") != "" for field in required_display_fields)
    if not display_fields_ok:
        failures.append("required host display fields are incomplete")

    verdict = SnapshotVerdict(
        overall="PASS" if not failures else "FAIL",
        host_log_ok=host_log_ok,
        no_ethernet_gate_ok=no_ethernet_gate_ok,
        two_ax7010_model_ok=two_ax7010_model_ok,
        display_fields_ok=display_fields_ok,
        no_hardware_action=no_hardware_action,
        failures=failures,
    )
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "verdict": asdict(verdict),
        "inputs": {
            "host_csv": rel(host_csv),
            "no_ethernet_summary": rel(no_eth_summary),
            "two_ax7010_json": rel(two_ax_json),
        },
        "display_fields": display_fields,
        "host_log": {
            "rows": host_analysis.row_count if host_analysis is not None else 0,
            "duration_s": host_analysis.duration if host_analysis is not None else 0.0,
            "markers": sorted(host_analysis.markers) if host_analysis is not None else [],
            "summary": host_summary,
        },
        "no_ethernet": {
            "pass_count": no_eth_fields.get("NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT", ""),
            "fail_count": no_eth_fields.get("NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT", ""),
            "acceptance_pass": no_eth_fields.get("NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS", ""),
            "real_tcp_dhcp": "NOT_RUN_NO_ETHERNET",
            "real_two_ax7010": "NOT_RUN_NO_ETHERNET",
        },
        "two_ax7010": {
            "result": two_ax.get("result", ""),
            "repeat": two_ax.get("repeat", ""),
            "fdx_repeat": two_ax.get("fdx_repeat", ""),
            "aggregate_tcp_model_mbps": two_ax.get("aggregate_tcp_model_mbps", ""),
            "link": two_link,
            "config": two_config,
        },
    }


def write_outputs(snapshot: dict[str, object], args: argparse.Namespace) -> None:
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    display_fields = snapshot["display_fields"]
    assert isinstance(display_fields, dict)
    verdict = snapshot["verdict"]
    assert isinstance(verdict, dict)

    if args.csv_output is not None:
        args.csv_output.parent.mkdir(parents=True, exist_ok=True)
        with args.csv_output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["section", "field", "value"])
            writer.writerow(["verdict", "overall", verdict["overall"]])
            for key, value in display_fields.items():
                writer.writerow(["display", key, value])

    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        inputs = snapshot["inputs"]
        assert isinstance(inputs, dict)
        failures = verdict.get("failures", [])
        lines = [
            "# Host Status Snapshot",
            "",
            f"Generated: {snapshot['generated']}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{verdict['overall']}`",
            "- Evidence type: `OFFLINE_HOST_VIEW_NOT_REAL_BOARD_TCP`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "",
            "## Inputs",
            "",
            f"- Host CSV: `{inputs['host_csv']}`",
            f"- No-Ethernet gate: `{inputs['no_ethernet_summary']}`",
            f"- Two-AX7010 model: `{inputs['two_ax7010_json']}`",
            "",
            "## Display Fields",
            "",
            "| field | value |",
            "| --- | --- |",
        ]
        for key, value in display_fields.items():
            lines.append(f"| `{key}` | `{value}` |")
        if failures:
            lines += ["", "## Failures", ""]
            for failure in failures:
                lines.append(f"- `{failure}`")
        args.markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-log", type=Path)
    parser.add_argument("--no-ethernet-summary", type=Path)
    parser.add_argument("--two-ax7010-json", type=Path)
    parser.add_argument("--json-output", type=Path, default=REPORTS / "host_status_snapshot_current.json")
    parser.add_argument("--markdown-output", type=Path, default=REPORTS / "host_status_snapshot_current.md")
    parser.add_argument("--csv-output", type=Path, default=REPORTS / "host_status_snapshot_current.csv")
    args = parser.parse_args(argv)

    snapshot = build_snapshot(args)
    write_outputs(snapshot, args)
    verdict = snapshot["verdict"]
    assert isinstance(verdict, dict)
    display = snapshot["display_fields"]
    assert isinstance(display, dict)
    print(
        "RF_COMM_HOST_STATUS_SNAPSHOT "
        f"overall={verdict['overall']} "
        f"host_log_ok={int(bool(verdict['host_log_ok']))} "
        f"no_ethernet_gate_ok={int(bool(verdict['no_ethernet_gate_ok']))} "
        f"two_ax7010_model_ok={int(bool(verdict['two_ax7010_model_ok']))} "
        f"display_fields_ok={int(bool(verdict['display_fields_ok']))} "
        f"tx_packets={display.get('tx_packets')} rx_packets={display.get('rx_packets')} "
        f"errors={display.get('error_frames')} pending={display.get('pending_frames')} "
        f"hdx_tx={display.get('hdx_tx_lane_coverage')} "
        f"fdx_a_to_b_tx={display.get('fdx_a_to_b_tx_lane_coverage')} "
        f"fdx_b_to_a_tx={display.get('fdx_b_to_a_tx_lane_coverage')} "
        f"no_hardware_action={int(bool(verdict['no_hardware_action']))}"
    )
    return 0 if verdict["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
