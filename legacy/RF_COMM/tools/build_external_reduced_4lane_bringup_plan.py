from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

BITSTREAM_JSON = REPORTS / "external_reduced_4lane_bitstream_current.json"
ROUTE_JSON = REPORTS / "external_reduced_4lane_route_current.json"
SHUTDOWN_JSON = REPORTS / "8lane_shutdown_build_current.json"
XDC = REPORTS / "external_lane_scan_xdcs" / "target_ir_array_external_4lane_scan.xdc"
PREFLIGHT_PS1 = ROOT / "tools" / "check_hw_target.ps1"
SHUTDOWN_TCL = ROOT / "tools" / "program_tfdu_shutdown_8lane_candidate.tcl"
OLD_SHUTDOWN_TCL = ROOT / "tools" / "program_tfdu_shutdown.tcl"


@dataclass
class BringupItem:
    item_id: str
    status: str
    evidence: str
    note: str


@dataclass
class PinAssignment:
    lane: int
    signal: str
    port: str
    package_pin: str
    iostandard: str


@dataclass
class ProbePlan:
    probe: str
    signal: str
    width: int
    purpose: str
    trigger_hint: str


@dataclass
class PhasePlan:
    phase: str
    purpose: str
    allowed_now: str
    command_or_path: str
    pass_criteria: str
    abort_or_shutdown: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def parse_assignments(path: Path) -> list[PinAssignment]:
    text = read_text(path)
    pin_by_port: dict[str, str] = {}
    iostd_by_port: dict[str, str] = {}
    for line in text.splitlines():
        pin_match = re.search(r"set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]", line)
        iostd_match = re.search(r"set_property\s+IOSTANDARD\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]", line)
        if pin_match:
            pin_by_port[pin_match.group(2)] = pin_match.group(1)
        if iostd_match:
            iostd_by_port[iostd_match.group(2)] = iostd_match.group(1)

    assignments: list[PinAssignment] = []
    for port, pin in sorted(pin_by_port.items()):
        match = re.fullmatch(r"(ir_(?:mode_out|rx_in|sd|tx_out)_0)\[(\d+)\]", port)
        if not match:
            continue
        base, lane_text = match.groups()
        signal = {
            "ir_mode_out_0": "MODE",
            "ir_rx_in_0": "RX",
            "ir_sd_0": "SD",
            "ir_tx_out_0": "TX",
        }[base]
        assignments.append(
            PinAssignment(
                lane=int(lane_text),
                signal=signal,
                port=port,
                package_pin=pin,
                iostandard=iostd_by_port.get(port, ""),
            )
        )
    return sorted(assignments, key=lambda item: (item.lane, ["MODE", "RX", "SD", "TX"].index(item.signal)))


def lane_pin_ok(assignments: list[PinAssignment]) -> bool:
    signals_by_lane: dict[int, set[str]] = {}
    pins: list[str] = []
    for assignment in assignments:
        signals_by_lane.setdefault(assignment.lane, set()).add(assignment.signal)
        pins.append(assignment.package_pin)
    return (
        len(assignments) == 16
        and sorted(signals_by_lane) == [0, 1, 2, 3]
        and all(signals == {"MODE", "RX", "SD", "TX"} for signals in signals_by_lane.values())
        and len(set(pins)) == len(pins)
    )


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    bitstream = read_json(BITSTREAM_JSON)
    route = read_json(ROUTE_JSON)
    shutdown = read_json(SHUTDOWN_JSON)
    assignments = parse_assignments(XDC)

    bitstream_path = ROOT / bitstream.get("bitstream", "")
    shutdown_path = ROOT / shutdown.get("bitstream", "")
    hard_constraint_ok = constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256
    bitstream_ok = (
        bitstream.get("overall") == "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED"
        and bitstream_path.exists()
        and bitstream.get("no_hardware_programming") is True
        and bitstream.get("no_tfdu_drive") is True
    )
    route_ok = (
        route.get("overall") == "ROUTE_TIMING_PASS_REDUCED_4LANE"
        and route.get("timing_pass") is True
        and route.get("routing_clean") is True
    )
    shutdown_ok = (
        shutdown.get("overall") == "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED"
        and shutdown_path.exists()
        and shutdown.get("vivado_errors") == 0
        and shutdown.get("vivado_critical_warnings") == 0
    )
    pins_ok = lane_pin_ok(assignments)
    safety_scripts_ok = PREFLIGHT_PS1.exists() and SHUTDOWN_TCL.exists() and OLD_SHUTDOWN_TCL.exists()

    items = [
        BringupItem("HARD-CONSTRAINT", "PASS" if hard_constraint_ok else "FAIL", rel(constraint), f"sha256={sha256(constraint)}"),
        BringupItem("REDUCED-4LANE-BITSTREAM", "PASS" if bitstream_ok else "FAIL", rel(BITSTREAM_JSON), f"bitstream={bitstream.get('bitstream')} sha256={bitstream.get('bitstream_sha256')} size={bitstream.get('bitstream_size_bytes')}"),
        BringupItem("REDUCED-4LANE-ROUTE", "PASS" if route_ok else "FAIL", rel(ROUTE_JSON), f"WNS={route.get('timing', {}).get('wns_ns')} WHS={route.get('timing', {}).get('whs_ns')} route_errors={route.get('route', {}).get('routing_errors')}"),
        BringupItem("SHUTDOWN-CANDIDATE", "PASS" if shutdown_ok else "FAIL", rel(SHUTDOWN_JSON), f"bitstream={shutdown.get('bitstream')} sha256={shutdown.get('bitstream_sha256')}"),
        BringupItem("PINMAP-4LANE", "PASS_REVIEW_REQUIRED" if pins_ok else "FAIL", rel(XDC), "16 A-endpoint assignments cover lanes 0..3 with no duplicate package pins; manual connector review is still required."),
        BringupItem("SAFETY-SCRIPTS", "PASS" if safety_scripts_ok else "FAIL", "tools", f"preflight={rel(PREFLIGHT_PS1)} shutdown8={rel(SHUTDOWN_TCL)} legacy_shutdown={rel(OLD_SHUTDOWN_TCL)}"),
        BringupItem("ETHERNET-BOUNDARY", "DEFERRED_NO_ETHERNET", rel(BITSTREAM_JSON), "Development board has no Ethernet cable; do not run real TCP/DHCP or two-AX7010 network acceptance."),
        BringupItem("NO-HARDWARE-ACTION", "PASS", "tools/build_external_reduced_4lane_bringup_plan.py", "This generator only reads files and writes reports; it does not open hardware, program FPGA, write UART, or drive TFDU."),
    ]
    failed = [item for item in items if item.status == "FAIL"]
    overall = "READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN" if not failed else "PLAN_INCOMPLETE"

    probes = [
        ProbePlan("probe0", "ir_array_top_axi_0/ir_tx_out[3:0]", 4, "A-side optical TX lane activity", "trigger on nonzero; then lane-specific eq4'h1, eq4'h2, eq4'h4, eq4'h8"),
        ProbePlan("probe1", "ir_array_top_axi_0/ir_rx_in[3:0]", 4, "A-side optical RX input idle/activity", "trigger or compare against expected idle/transition pattern after TX"),
        ProbePlan("probe2", "ir_array_top_axi_0/ir_sd[3:0]", 4, "TFDU shutdown/enable state per lane", "verify shutdown state before/after physical run; verify intended enable only during short run"),
        ProbePlan("probe3", "ir_array_top_axi_0/ir_mode_out[3:0]", 4, "TFDU mode pin state per lane", "verify normal mode level is stable before enabling traffic"),
        ProbePlan("optional4", "protocol counters/status, if exposed by future debug build", 32, "Frame/packet decode state and error latch", "capture only after physical pins show expected transitions"),
    ]

    phases = [
        PhasePlan("P0", "Offline review of bitstream, route, pinmap, and shutdown evidence.", "yes", "python tools/build_external_reduced_4lane_bringup_plan.py", "overall=READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN", "No shutdown needed; no hardware touched."),
        PhasePlan("P1", "JTAG/USB visibility preflight only.", "yes, if board is connected by USB/JTAG", "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\check_hw_target.ps1", "HW_PREFLIGHT_RESULT PASS", "No TFDU drive; no bitstream programming."),
        PhasePlan("P2", "Program shutdown candidate before any TFDU wiring/traffic review.", "future manual hardware step", "vivado -mode batch -source tools/program_tfdu_shutdown_8lane_candidate.tcl", "TFDU_SHUTDOWN_8LANE_CANDIDATE_PROGRAMMED", "If this fails, stop and do not program the 4-lane candidate."),
        PhasePlan("P3", "Program reduced 4-lane candidate only after pinmap/manual wiring review.", "future manual hardware step", f"candidate bitstream: {rel(bitstream_path)}", "Device programs and TFDU pins remain idle until controlled traffic starts.", "Immediately program 8-lane shutdown on any error or after the short window."),
        PhasePlan("P4", "Passive ILA capture with no static diagnostic waveform.", "future manual hardware step", "Use a 4-lane adaptation of capture_2lane_ila_once.tcl; trigger on A_TX nonzero or lane-specific TX.", "CSV contains A_TX lane transitions, A_RX idle/activity, SD/MODE stable levels.", "Continuous physical window <= 600 s; prefer <= 60 s for first smoke."),
        PhasePlan("P5", "Escalate from pin activity to protocol traffic only after physical signals are sane.", "future, still no Ethernet until cable exists", "Host/PS higher-level acceptance remains deferred while Ethernet is absent.", "No lane stuck, no unrecovered error, expected route coverage.", "Program shutdown candidate at end of every TFDU-driven run."),
    ]

    md_path = REPORTS / "external_reduced_4lane_bringup_plan_current.md"
    json_path = REPORTS / "external_reduced_4lane_bringup_plan_current.json"
    csv_path = REPORTS / "external_reduced_4lane_bringup_plan_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "status", "evidence", "note"])
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    pin_rows = [[str(a.lane), a.signal, a.port, a.package_pin, a.iostandard] for a in assignments]
    probe_rows = [[p.probe, p.signal, str(p.width), p.purpose, p.trigger_hint] for p in probes]
    phase_rows = [[p.phase, p.purpose, p.allowed_now, p.command_or_path, p.pass_criteria, p.abort_or_shutdown] for p in phases]
    item_rows = [[item.item_id, item.status, item.evidence, item.note] for item in items]

    md = [
        "# External Reduced 4-Lane Bring-Up Plan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Reduced 4-lane candidate bitstream: `{rel(bitstream_path)}`",
        f"- Candidate bitstream SHA256: `{bitstream.get('bitstream_sha256')}`",
        f"- Shutdown candidate bitstream: `{rel(shutdown_path)}`",
        f"- Shutdown bitstream SHA256: `{shutdown.get('bitstream_sha256')}`",
        "- Current board Ethernet: `not connected`; real TCP/DHCP and two-AX7010 network acceptance remain deferred.",
        "- This plan did not program FPGA hardware, write UART, send TX data, or drive TFDU boards.",
        "",
        "## Safety Rules",
        "",
        "- Do not program the reduced 4-lane candidate until the pinmap and connector wiring have been manually reviewed.",
        "- Program the 8-lane shutdown candidate before and after any future TFDU-driven run.",
        "- Keep each continuous physical TFDU/TX window at or below 600 seconds; use a much shorter first smoke window.",
        "- Do not use static diagnostic waveforms on connected TFDU boards.",
        "- Do not retry real TCP/DHCP or two-AX7010 network acceptance while the board has no Ethernet cable.",
        "",
        "## Readiness Items",
        "",
        md_table(["id", "status", "evidence", "note"], item_rows),
        "",
        "## 4-Lane A-Side Pin Matrix",
        "",
        md_table(["lane", "signal", "port", "package_pin", "iostandard"], pin_rows),
        "",
        "## Passive ILA Probe Plan",
        "",
        md_table(["probe", "signal", "width", "purpose", "trigger_hint"], probe_rows),
        "",
        "## Bring-Up Phases",
        "",
        md_table(["phase", "purpose", "allowed_now", "command_or_path", "pass_criteria", "abort_or_shutdown"], phase_rows),
        "",
        f"RF_COMM_EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN overall={overall} bitstream_sha256={bitstream.get('bitstream_sha256')} shutdown_sha256={shutdown.get('bitstream_sha256')} lanes=4",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "current_board_ethernet": "not_connected",
        "real_tcp_dhcp_deferred": True,
        "continuous_physical_run_cap_seconds": 600,
        "reduced_4lane_bitstream": rel(bitstream_path),
        "reduced_4lane_bitstream_sha256": bitstream.get("bitstream_sha256"),
        "shutdown_bitstream": rel(shutdown_path),
        "shutdown_bitstream_sha256": shutdown.get("bitstream_sha256"),
        "manual_review_required": True,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "items": [asdict(item) for item in items],
        "pin_assignments": [asdict(item) for item in assignments],
        "probe_plan": [asdict(item) for item in probes],
        "phases": [asdict(item) for item in phases],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN overall={overall} bitstream_sha256={bitstream.get('bitstream_sha256')} shutdown_sha256={shutdown.get('bitstream_sha256')} lanes=4")
    return 0 if overall != "PLAN_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
