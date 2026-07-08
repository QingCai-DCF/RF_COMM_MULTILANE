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

ACTIVE_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "PORT1.xdc"
DRAFT_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "target_ir_array_draft.xdc"
CANDIDATE_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "target_ir_array_8lane_candidate.xdc"
A_ONLY_CANDIDATE_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "target_ir_array_8lane_a_only_candidate.xdc"
SHUTDOWN_XDC = ROOT / "tools" / "tfdu_shutdown_j10_j11.xdc"
SHUTDOWN_CANDIDATE_TOP = ROOT / "tools" / "tfdu_shutdown_8lane_candidate_top.v"
SHUTDOWN_CANDIDATE_XDC = ROOT / "tools" / "tfdu_shutdown_8lane_candidate.xdc"
SHUTDOWN_CANDIDATE_BUILD_TCL = ROOT / "tools" / "build_tfdu_shutdown_8lane_candidate.tcl"
SHUTDOWN_CANDIDATE_JSON = REPORTS / "8lane_shutdown_candidate_current.json"
SHUTDOWN_BUILD_JSON = REPORTS / "8lane_shutdown_build_current.json"
CANDIDATE_PROJECT_BUILD_JSON = REPORTS / "8lane_candidate_project_build_current.json"
EXTERNAL_PROJECT_BUILD_JSON = REPORTS / "8lane_external_project_build_current.json"
EXTERNAL_LANE_RESOURCE_SCAN_JSON = REPORTS / "external_lane_resource_scan_current.json"
EXTERNAL_RESOURCE_OPTION_SCAN_JSON = REPORTS / "external_resource_option_scan_current.json"
EXTERNAL_REDUCED_LANE_RESOURCE_SCAN_JSON = REPORTS / "external_reduced_lane_resource_scan_current.json"
EXTERNAL_REDUCED_5TO8_EXTENSION_JSON = REPORTS / "external_reduced_5to8_extension_current.json"
EXTERNAL_REDUCED_5LANE_FRAG32_JSON = REPORTS / "external_reduced_5lane_frag32_current.json"
EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_JSON = REPORTS / "external_reduced_5lane_frag32_route_current.json"
EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM_JSON = REPORTS / "external_reduced_5lane_frag32_bitstream_current.json"
EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_JSON = REPORTS / "external_reduced_8lane_frag16_bitstream_current.json"
EXTERNAL_REDUCED_ROUTE_JSON = REPORTS / "external_reduced_2lane_route_current.json"
EXTERNAL_REDUCED_4LANE_ROUTE_JSON = REPORTS / "external_reduced_4lane_route_current.json"
EXTERNAL_REDUCED_4LANE_BITSTREAM_JSON = REPORTS / "external_reduced_4lane_bitstream_current.json"
EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN_JSON = REPORTS / "external_reduced_4lane_bringup_plan_current.json"
HW_CONFIG_TCL = ROOT / "tools" / "configure_lane0_ab_hw_loopback.tcl"
POST_SUMMARY = ROOT / "reports" / "post_g1_target_sim_gate_20260627_002848.summary.txt"


@dataclass
class ReadinessItem:
    item_id: str
    requirement: str
    status: str
    evidence: str
    note: str


@dataclass
class PortAssignment:
    endpoint: str
    lane: int
    signal: str
    port: str
    package_pin: str
    iostandard: str
    source: str


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


def parse_xdc_assignments(path: Path) -> list[PortAssignment]:
    text = read_text(path)
    pin_by_port: dict[str, str] = {}
    iostd_by_port: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pin_match = re.search(r"set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{?([^}\]]+(?:\][^}]*)?)\}?\]", stripped)
        iostd_match = re.search(r"set_property\s+IOSTANDARD\s+(\S+)\s+\[get_ports\s+\{?([^}\]]+(?:\][^}]*)?)\}?\]", stripped)
        if pin_match:
            pin_by_port[pin_match.group(2).strip()] = pin_match.group(1).strip().strip('"')
        if iostd_match:
            iostd_by_port[iostd_match.group(2).strip()] = iostd_match.group(1).strip().strip('"')

    assignments: list[PortAssignment] = []
    for port, pin in sorted(pin_by_port.items()):
        parsed = parse_tfdu_port(port)
        if parsed is None:
            continue
        endpoint, lane, signal = parsed
        assignments.append(
            PortAssignment(
                endpoint=endpoint,
                lane=lane,
                signal=signal,
                port=port,
                package_pin=pin,
                iostandard=iostd_by_port.get(port, ""),
                source=rel(path),
            )
        )
    return assignments


def parse_tfdu_port(port: str) -> tuple[str, int, str] | None:
    mapping = {
        "ir_mode_out_0": ("A", "MODE"),
        "ir_rx_in_0": ("A", "RX"),
        "ir_sd_0": ("A", "SD"),
        "ir_tx_out_0": ("A", "TX"),
        "loop_mode_b0": ("B", "MODE"),
        "loop_rx_b0": ("B", "RX"),
        "loop_sd_b0": ("B", "SD"),
        "loop_tx_b0": ("B", "TX"),
    }
    match = re.fullmatch(r"([A-Za-z0-9_]+)\[(\d+)\]", port)
    if match is None:
        return None
    base = match.group(1)
    if base not in mapping:
        return None
    endpoint, signal = mapping[base]
    return endpoint, int(match.group(2)), signal


def lane_coverage(assignments: list[PortAssignment], endpoint: str, lane_count: int = 8) -> tuple[list[int], dict[int, list[str]]]:
    signals_by_lane: dict[int, set[str]] = {lane: set() for lane in range(lane_count)}
    for assignment in assignments:
        if assignment.endpoint == endpoint and 0 <= assignment.lane < lane_count:
            signals_by_lane[assignment.lane].add(assignment.signal)
    complete_lanes = [lane for lane, signals in signals_by_lane.items() if signals == {"MODE", "RX", "SD", "TX"}]
    missing = {
        lane: sorted({"MODE", "RX", "SD", "TX"} - signals)
        for lane, signals in signals_by_lane.items()
        if signals != {"MODE", "RX", "SD", "TX"}
    }
    return complete_lanes, missing


def duplicate_pins(assignments: list[PortAssignment]) -> dict[str, list[str]]:
    pins: dict[str, list[str]] = {}
    for assignment in assignments:
        pins.setdefault(assignment.package_pin, []).append(assignment.port)
    return {pin: ports for pin, ports in pins.items() if len(ports) > 1}


def coverage_summary(assignments: list[PortAssignment], lane_count: int = 8) -> tuple[list[int], list[int], dict[str, list[int]]]:
    a_lanes, _ = lane_coverage(assignments, "A", lane_count=lane_count)
    b_lanes, _ = lane_coverage(assignments, "B", lane_count=lane_count)
    return a_lanes, b_lanes, {"A": a_lanes, "B": b_lanes}


def max_lane_limit_from_tcl(text: str) -> int | None:
    variable_match = re.search(r"set\s+max_hw_lane_count\s+(\d+)", text)
    if variable_match is not None:
        return int(variable_match.group(1))
    match = re.search(r"\$lane_count\s*>\s*(\d+)\}?\s*\{\s*\n\s*error\s+\"IR_LANE_COUNT must be in 1\.\.(\d+)", text)
    if match is not None:
        return int(match.group(1))
    match = re.search(r"IR_LANE_COUNT must be in 1\.\.(\d+)", text)
    if match is not None:
        return int(match.group(1))
    return None


def draft_todo_count(text: str) -> int:
    return len(re.findall(r"<TODO_PIN>", text))


def overall_status(items: list[ReadinessItem]) -> str:
    if any(item.status == "FAIL" for item in items):
        return "FAIL"
    if any(
        item.status in {"BLOCKER", "PARTIAL", "SYNTH_PASS_IMPL_RESOURCE_BLOCKED", "PLACE_PASS_ONLY_1LANE"}
        for item in items
    ):
        return "NOT_READY_FOR_REAL_8LANE_HARDWARE"
    return "READY_FOR_REAL_8LANE_HARDWARE"


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
    constraint = find_hard_constraint()
    active_assignments = parse_xdc_assignments(ACTIVE_XDC)
    candidate_assignments = parse_xdc_assignments(CANDIDATE_XDC)
    a_only_assignments = parse_xdc_assignments(A_ONLY_CANDIDATE_XDC)
    hw_tcl_text = read_text(HW_CONFIG_TCL)
    draft_text = read_text(DRAFT_XDC)
    candidate_text = read_text(CANDIDATE_XDC)
    a_only_candidate_text = read_text(A_ONLY_CANDIDATE_XDC)
    shutdown_text = read_text(SHUTDOWN_XDC)
    shutdown_candidate = read_json(SHUTDOWN_CANDIDATE_JSON)
    shutdown_build = read_json(SHUTDOWN_BUILD_JSON)
    candidate_project_build = read_json(CANDIDATE_PROJECT_BUILD_JSON)
    external_project_build = read_json(EXTERNAL_PROJECT_BUILD_JSON)
    external_lane_scan = read_json(EXTERNAL_LANE_RESOURCE_SCAN_JSON)
    external_option_scan = read_json(EXTERNAL_RESOURCE_OPTION_SCAN_JSON)
    external_reduced_lane_scan = read_json(EXTERNAL_REDUCED_LANE_RESOURCE_SCAN_JSON)
    external_reduced_5to8_extension = read_json(EXTERNAL_REDUCED_5TO8_EXTENSION_JSON)
    external_reduced_5lane_frag32 = read_json(EXTERNAL_REDUCED_5LANE_FRAG32_JSON)
    external_reduced_5lane_frag32_route = read_json(EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_JSON)
    external_reduced_5lane_frag32_bitstream = read_json(EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM_JSON)
    external_reduced_8lane_frag16_bitstream = read_json(EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_JSON)
    external_reduced_route = read_json(EXTERNAL_REDUCED_ROUTE_JSON)
    external_reduced_4lane_route = read_json(EXTERNAL_REDUCED_4LANE_ROUTE_JSON)
    external_reduced_4lane_bitstream = read_json(EXTERNAL_REDUCED_4LANE_BITSTREAM_JSON)
    external_reduced_4lane_bringup = read_json(EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN_JSON)
    shutdown_candidate_top_text = read_text(SHUTDOWN_CANDIDATE_TOP)
    shutdown_candidate_xdc_text = read_text(SHUTDOWN_CANDIDATE_XDC)
    shutdown_candidate_build_text = read_text(SHUTDOWN_CANDIDATE_BUILD_TCL)
    post_summary_text = read_text(POST_SUMMARY)

    a_lanes, a_missing = lane_coverage(active_assignments, "A")
    b_lanes, b_missing = lane_coverage(active_assignments, "B")
    dupes = duplicate_pins(active_assignments)
    candidate_a_lanes, candidate_b_lanes, _ = coverage_summary(candidate_assignments)
    candidate_dupes = duplicate_pins(candidate_assignments)
    a_only_a_lanes, a_only_b_lanes, _ = coverage_summary(a_only_assignments)
    a_only_dupes = duplicate_pins(a_only_assignments)
    candidate_complete = (
        CANDIDATE_XDC.exists()
        and len(candidate_assignments) == 64
        and len(candidate_a_lanes) == 8
        and len(candidate_b_lanes) == 8
        and not candidate_dupes
        and "This is a candidate for review" in candidate_text
        and "D19" in candidate_text
    )
    a_only_complete = (
        A_ONLY_CANDIDATE_XDC.exists()
        and len(a_only_assignments) == 32
        and len(a_only_a_lanes) == 8
        and len(a_only_b_lanes) == 0
        and not a_only_dupes
        and "IR_B_MODE=external" in a_only_candidate_text
        and "excludes loop_*" in a_only_candidate_text
    )
    lane_limit = max_lane_limit_from_tcl(hw_tcl_text)
    rtl_sim_ok = all(
        marker in post_summary_text
        for marker in [
            "LOOPBACK_8LANE_PASS",
            "LOOPBACK_8LANE_AUTOROUTE_PASS",
            "LOOPBACK_FULL_DUPLEX_4PLUS4_LANE_PASS",
            "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS",
        ]
    )
    vector_port_proc_ok = "proc recreate_tfdu_vector_port" in hw_tcl_text and "create_bd_port -dir $dir -from $hi -to 0 $name" in hw_tcl_text
    external_mode_ok = 'if {$b_mode eq "external"}' in hw_tcl_text
    draft_todos = draft_todo_count(draft_text)
    shutdown_ports = sorted(set(re.findall(r"\[get_ports\s+(j1[01]_[ab]_(?:mode|sd|tx|rx))\]", shutdown_text)))
    shutdown_lane_markers = len(shutdown_ports)
    shutdown_candidate_ok = (
        shutdown_candidate.get("overall") == "CANDIDATE_SHUTDOWN_GENERATED_REVIEW_REQUIRED"
        and shutdown_candidate.get("output_count") == 48
        and shutdown_candidate.get("input_count") == 16
        and len(shutdown_candidate.get("assignments", [])) == 64
        and "tfdu_shutdown_8lane_candidate_top" in shutdown_candidate_top_text
        and "assign ir_sd_0       = 8'hff" in shutdown_candidate_top_text
        and "assign loop_sd_b0    = 8'hff" in shutdown_candidate_top_text
        and "read_verilog [file join $repo_root \"tools\" \"tfdu_shutdown_8lane_candidate_top.v\"]" in shutdown_candidate_build_text
        and "tfdu_shutdown_8lane_candidate.bit" in shutdown_candidate_build_text
        and "Candidate only" in shutdown_candidate_xdc_text
    )
    shutdown_build_ok = (
        shutdown_build.get("overall") == "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED"
        and shutdown_build.get("vivado_errors") == 0
        and shutdown_build.get("vivado_critical_warnings") == 0
        and shutdown_build.get("candidate_pinmap_rows") == 64
        and shutdown_build.get("no_hardware_programming") is True
        and shutdown_build.get("no_uart_write") is True
        and shutdown_build.get("no_tfdu_drive") is True
        and (ROOT / shutdown_build.get("bitstream", "")).exists()
    )
    candidate_project_synth_pass_resource_blocked = (
        candidate_project_build.get("overall") == "SYNTH_PASS_IMPL_BLOCKED_LUT_OVERUTILIZED"
        and candidate_project_build.get("synthesis_pass") is True
        and candidate_project_build.get("implementation_resource_blocked") is True
        and candidate_project_build.get("required_luts") == 21125
        and candidate_project_build.get("available_luts") == 17600
        and candidate_project_build.get("candidate_xdc_removed_after_build") is True
        and candidate_project_build.get("xpr_clean") is True
        and candidate_project_build.get("no_hardware_programming") is True
    )
    external_resources = external_project_build.get("resources", [])
    external_resource_summary = "; ".join(
        f"{item.get('resource')}: {item.get('required')}/{item.get('available')}"
        for item in external_resources
    )
    external_project_synth_pass_resource_blocked = (
        external_project_build.get("overall") == "SYNTH_PASS_IMPL_BLOCKED_RESOURCE_OVERUTILIZED"
        and external_project_build.get("synthesis_pass") is True
        and external_project_build.get("implementation_resource_blocked") is True
        and external_project_build.get("candidate_xdc_removed_after_build") is True
        and external_project_build.get("port1_xdc_restored") is True
        and external_project_build.get("xpr_clean") is True
        and external_project_build.get("no_hardware_programming") is True
        and len(external_resources) >= 3
    )
    external_scan_overall = external_lane_scan.get("overall")
    external_scan_max_place_pass = external_lane_scan.get("max_place_pass_lane_count")
    external_scan_first_blocked = external_lane_scan.get("first_resource_blocked_lane_count")
    external_scan_results = external_lane_scan.get("lane_results", [])
    external_lane_resource_scan_ok = (
        external_scan_overall == "PLACE_PASS_ONLY_1LANE"
        and external_scan_max_place_pass == 1
        and external_scan_first_blocked == 2
        and external_lane_scan.get("scan_done") is True
        and external_lane_scan.get("restored_2lane_stream_bidir") is True
        and external_lane_scan.get("no_hardware_programming") is True
        and external_lane_scan.get("no_uart_write") is True
        and external_lane_scan.get("no_tfdu_drive") is True
        and len(external_scan_results) == 8
    )
    external_option_overall = external_option_scan.get("overall")
    external_option_results = external_option_scan.get("results", [])
    external_option_meta = external_option_scan.get("meta", {})
    external_option_result = external_option_results[0] if external_option_results else {}
    external_option_ok = (
        external_option_overall == "PLACE_PASS_REDUCED_2LANE"
        and external_option_scan.get("scan_done") is True
        and external_option_scan.get("restored_2lane_stream_bidir") is True
        and external_option_scan.get("no_hardware_programming") is True
        and external_option_scan.get("no_uart_write") is True
        and external_option_scan.get("no_tfdu_drive") is True
        and external_option_meta.get("scan_lanes") == "2"
        and external_option_meta.get("fragment_bytes") == "64"
        and external_option_meta.get("tx_async_fifo_depth") == "128"
        and external_option_meta.get("rx_async_fifo_depth") == "128"
        and external_option_result.get("status") == "PLACE_PASS_REDUCED_PROFILE"
    )
    external_reduced_lane_overall = external_reduced_lane_scan.get("overall")
    external_reduced_lane_meta = external_reduced_lane_scan.get("meta", {})
    external_reduced_lane_results = external_reduced_lane_scan.get("lane_results", [])
    external_reduced_lane_max_place_pass = external_reduced_lane_scan.get("max_place_pass_lane_count")
    external_reduced_lane_first_blocked = external_reduced_lane_scan.get("first_resource_blocked_lane_count")
    external_reduced_lane_ok = (
        external_reduced_lane_overall == "PLACE_PASS_REDUCED_UP_TO_4LANE"
        and external_reduced_lane_scan.get("scan_done") is True
        and external_reduced_lane_scan.get("restored_2lane_stream_bidir") is True
        and external_reduced_lane_scan.get("no_hardware_programming") is True
        and external_reduced_lane_scan.get("no_uart_write") is True
        and external_reduced_lane_scan.get("no_tfdu_drive") is True
        and external_reduced_lane_meta.get("scan_lanes") == "1 2 3 4"
        and external_reduced_lane_meta.get("fragment_bytes") == "64"
        and external_reduced_lane_meta.get("tx_async_fifo_depth") == "128"
        and external_reduced_lane_meta.get("rx_async_fifo_depth") == "128"
        and external_reduced_lane_max_place_pass == 4
        and external_reduced_lane_first_blocked is None
        and len(external_reduced_lane_results) == 4
        and all(item.get("status") == "PLACE_PASS_REDUCED_PROFILE" for item in external_reduced_lane_results)
    )
    external_reduced_5to8_overall = external_reduced_5to8_extension.get("overall")
    external_reduced_5to8_results = external_reduced_5to8_extension.get("lane_results", [])
    external_reduced_5to8_meta = external_reduced_5to8_extension.get("meta", {})
    external_reduced_5to8_lane5 = next(
        (item for item in external_reduced_5to8_results if item.get("lane_count") == 5),
        {},
    )
    external_reduced_5to8_lane6 = next(
        (item for item in external_reduced_5to8_results if item.get("lane_count") == 6),
        {},
    )
    external_reduced_5to8_ok = (
        external_reduced_5to8_overall == "FIRST_BLOCKED_AT_5LANE_REDUCED_PROFILE"
        and external_reduced_5to8_extension.get("lane5_resource_blocked") is True
        and external_reduced_5to8_extension.get("first_blocked_lane_count") == 5
        and external_reduced_5to8_extension.get("max_place_pass_lane_count") == 4
        and external_reduced_5to8_extension.get("stopped_after_lane6_stall") is True
        and external_reduced_5to8_extension.get("restored_2lane_stream_bidir") is True
        and external_reduced_5to8_extension.get("no_hardware_programming") is True
        and external_reduced_5to8_extension.get("no_uart_write") is True
        and external_reduced_5to8_extension.get("no_tfdu_drive") is True
        and external_reduced_5to8_meta.get("scan_lanes") == "5 6 7 8"
        and external_reduced_5to8_meta.get("fragment_bytes") == "64"
        and external_reduced_5to8_meta.get("tx_async_fifo_depth") == "128"
        and external_reduced_5to8_meta.get("rx_async_fifo_depth") == "128"
        and external_reduced_5to8_lane5.get("status") == "PLACE_RESOURCE_BLOCKED"
        and external_reduced_5to8_lane5.get("total_luts") == 17801
        and external_reduced_5to8_lane5.get("available_luts") == 17600
        and external_reduced_5to8_lane5.get("slice_required") == 3869
        and external_reduced_5to8_lane5.get("slice_available") == 3845
        and external_reduced_5to8_lane5.get("control_sets") == 1274
        and external_reduced_5to8_lane6.get("status") == "STOPPED_AFTER_STALL"
    )
    external_reduced_5lane_frag32_overall = external_reduced_5lane_frag32.get("overall")
    external_reduced_5lane_frag32_meta = external_reduced_5lane_frag32.get("meta", {})
    external_reduced_5lane_frag32_resources = external_reduced_5lane_frag32.get("resources", {})
    external_reduced_5lane_frag32_comparison = external_reduced_5lane_frag32.get("comparison_to_fragment64_lane5", {})
    external_reduced_5lane_frag32_ok = (
        external_reduced_5lane_frag32_overall == "PLACE_PASS_5LANE_FRAG32_REDUCED_PROFILE"
        and external_reduced_5lane_frag32.get("place_design_pass") is True
        and external_reduced_5lane_frag32.get("restored_2lane_stream_bidir") is True
        and external_reduced_5lane_frag32.get("no_hardware_programming") is True
        and external_reduced_5lane_frag32.get("no_uart_write") is True
        and external_reduced_5lane_frag32.get("no_tfdu_drive") is True
        and external_reduced_5lane_frag32.get("real_tcp_dhcp_deferred") is True
        and external_reduced_5lane_frag32_meta.get("scan_lanes") == "5"
        and external_reduced_5lane_frag32_meta.get("fragment_bytes") == "32"
        and external_reduced_5lane_frag32_meta.get("max_packet_bytes") == "128"
        and external_reduced_5lane_frag32_meta.get("tx_async_fifo_depth") == "128"
        and external_reduced_5lane_frag32_meta.get("rx_async_fifo_depth") == "128"
        and external_reduced_5lane_frag32_meta.get("stream_phy_dbg_select") == "6"
        and external_reduced_5lane_frag32_resources.get("slice_luts") == 10697
        and external_reduced_5lane_frag32_resources.get("slice_luts_available") == 17600
        and external_reduced_5lane_frag32_resources.get("slice_registers") == 14001
        and external_reduced_5lane_frag32_resources.get("control_sets") == 918
    )
    external_reduced_5lane_frag32_route_overall = external_reduced_5lane_frag32_route.get("overall")
    external_reduced_5lane_frag32_route_meta = external_reduced_5lane_frag32_route.get("meta", {})
    external_reduced_5lane_frag32_route_timing = external_reduced_5lane_frag32_route.get("timing", {})
    external_reduced_5lane_frag32_route_route = external_reduced_5lane_frag32_route.get("route", {})
    external_reduced_5lane_frag32_route_ok = (
        external_reduced_5lane_frag32_route_overall == "ROUTE_TIMING_PASS_REDUCED_5LANE_FRAG32"
        and external_reduced_5lane_frag32_route.get("synthesis_pass") is True
        and external_reduced_5lane_frag32_route.get("route_pass") is True
        and external_reduced_5lane_frag32_route.get("timing_pass") is True
        and external_reduced_5lane_frag32_route.get("routing_clean") is True
        and external_reduced_5lane_frag32_route.get("drc_no_critical_or_error") is True
        and external_reduced_5lane_frag32_route.get("restored_2lane_stream_bidir") is True
        and external_reduced_5lane_frag32_route.get("no_hardware_programming") is True
        and external_reduced_5lane_frag32_route.get("no_uart_write") is True
        and external_reduced_5lane_frag32_route.get("no_tfdu_drive") is True
        and external_reduced_5lane_frag32_route.get("real_tcp_dhcp_deferred") is True
        and external_reduced_5lane_frag32_route_meta.get("lane_count") == "5"
        and external_reduced_5lane_frag32_route_meta.get("fragment_bytes") == "32"
        and external_reduced_5lane_frag32_route_meta.get("max_packet_bytes") == "128"
        and external_reduced_5lane_frag32_route_meta.get("stream_phy_dbg_select") == "6"
        and external_reduced_5lane_frag32_route_timing.get("wns_ns") == 1.571
        and external_reduced_5lane_frag32_route_timing.get("whs_ns") == 0.012
        and external_reduced_5lane_frag32_route_route.get("routing_errors") == 0
    )
    external_reduced_5lane_frag32_bitstream_overall = external_reduced_5lane_frag32_bitstream.get("overall")
    external_reduced_5lane_frag32_bitstream_timing = external_reduced_5lane_frag32_bitstream.get("timing", {})
    external_reduced_5lane_frag32_bitstream_route = external_reduced_5lane_frag32_bitstream.get("route", {})
    external_reduced_5lane_frag32_bitstream_ok = (
        external_reduced_5lane_frag32_bitstream_overall == "PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED"
        and external_reduced_5lane_frag32_bitstream.get("profile_ok") is True
        and external_reduced_5lane_frag32_bitstream.get("timing_pass") is True
        and external_reduced_5lane_frag32_bitstream.get("routing_clean") is True
        and external_reduced_5lane_frag32_bitstream.get("drc_no_critical_or_error") is True
        and external_reduced_5lane_frag32_bitstream.get("no_hardware_programming") is True
        and external_reduced_5lane_frag32_bitstream.get("no_uart_write") is True
        and external_reduced_5lane_frag32_bitstream.get("no_tfdu_drive") is True
        and external_reduced_5lane_frag32_bitstream.get("real_tcp_dhcp_deferred") is True
        and external_reduced_5lane_frag32_bitstream.get("bitstream_size_bytes", 0) > 0
        and external_reduced_5lane_frag32_bitstream.get("bitstream_sha256") == "64213BD459D5CF8E6A487DC601D8942F1D938858AFAE5039CBB46FF3A39A903E"
        and external_reduced_5lane_frag32_bitstream_timing.get("wns_ns") == 1.571
        and external_reduced_5lane_frag32_bitstream_timing.get("whs_ns") == 0.012
        and external_reduced_5lane_frag32_bitstream_route.get("routing_errors") == 0
    )
    external_reduced_8lane_frag16_bitstream_overall = external_reduced_8lane_frag16_bitstream.get("overall")
    external_reduced_8lane_frag16_bitstream_timing = external_reduced_8lane_frag16_bitstream.get("timing", {})
    external_reduced_8lane_frag16_bitstream_route = external_reduced_8lane_frag16_bitstream.get("route", {})
    external_reduced_8lane_frag16_bitstream_ok = (
        external_reduced_8lane_frag16_bitstream_overall == "PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED"
        and external_reduced_8lane_frag16_bitstream.get("profile_ok") is True
        and external_reduced_8lane_frag16_bitstream.get("raw_target_capacity") is True
        and external_reduced_8lane_frag16_bitstream.get("timing_pass") is True
        and external_reduced_8lane_frag16_bitstream.get("routing_clean") is True
        and external_reduced_8lane_frag16_bitstream.get("drc_no_critical_or_error") is True
        and external_reduced_8lane_frag16_bitstream.get("no_hardware_programming") is True
        and external_reduced_8lane_frag16_bitstream.get("no_uart_write") is True
        and external_reduced_8lane_frag16_bitstream.get("no_tfdu_drive") is True
        and external_reduced_8lane_frag16_bitstream.get("real_tcp_dhcp_deferred") is True
        and external_reduced_8lane_frag16_bitstream.get("bitstream_size_bytes", 0) > 0
        and external_reduced_8lane_frag16_bitstream.get("bitstream_sha256") == "F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778"
        and external_reduced_8lane_frag16_bitstream_timing.get("wns_ns") == 1.153
        and external_reduced_8lane_frag16_bitstream_timing.get("whs_ns") == 0.009
        and external_reduced_8lane_frag16_bitstream_route.get("routing_errors") == 0
    )
    external_route_overall = external_reduced_route.get("overall")
    external_route_timing = external_reduced_route.get("timing", {})
    external_route_route = external_reduced_route.get("route", {})
    external_route_ok = (
        external_route_overall == "ROUTE_TIMING_PASS_REDUCED_2LANE"
        and external_reduced_route.get("synthesis_pass") is True
        and external_reduced_route.get("route_pass") is True
        and external_reduced_route.get("timing_pass") is True
        and external_reduced_route.get("routing_clean") is True
        and external_reduced_route.get("restored_2lane_stream_bidir") is True
        and external_reduced_route.get("no_hardware_programming") is True
        and external_reduced_route.get("no_uart_write") is True
        and external_reduced_route.get("no_tfdu_drive") is True
    )
    external_route_4lane_overall = external_reduced_4lane_route.get("overall")
    external_route_4lane_timing = external_reduced_4lane_route.get("timing", {})
    external_route_4lane_route = external_reduced_4lane_route.get("route", {})
    external_route_4lane_ok = (
        external_route_4lane_overall == "ROUTE_TIMING_PASS_REDUCED_4LANE"
        and external_reduced_4lane_route.get("synthesis_pass") is True
        and external_reduced_4lane_route.get("route_pass") is True
        and external_reduced_4lane_route.get("timing_pass") is True
        and external_reduced_4lane_route.get("routing_clean") is True
        and external_reduced_4lane_route.get("restored_2lane_stream_bidir") is True
        and external_reduced_4lane_route.get("no_hardware_programming") is True
        and external_reduced_4lane_route.get("no_uart_write") is True
        and external_reduced_4lane_route.get("no_tfdu_drive") is True
    )
    external_bitstream_4lane_overall = external_reduced_4lane_bitstream.get("overall")
    external_bitstream_4lane_timing = external_reduced_4lane_bitstream.get("timing", {})
    external_bitstream_4lane_route = external_reduced_4lane_bitstream.get("route", {})
    external_bitstream_4lane_ok = (
        external_bitstream_4lane_overall == "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED"
        and external_reduced_4lane_bitstream.get("timing_pass") is True
        and external_reduced_4lane_bitstream.get("routing_clean") is True
        and external_reduced_4lane_bitstream.get("drc_no_critical_or_error") is True
        and external_reduced_4lane_bitstream.get("no_hardware_programming") is True
        and external_reduced_4lane_bitstream.get("no_uart_write") is True
        and external_reduced_4lane_bitstream.get("no_tfdu_drive") is True
        and external_reduced_4lane_bitstream.get("bitstream_size_bytes", 0) > 0
    )
    external_bringup_4lane_overall = external_reduced_4lane_bringup.get("overall")
    external_bringup_4lane_ok = (
        external_bringup_4lane_overall == "READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN"
        and external_reduced_4lane_bringup.get("manual_review_required") is True
        and external_reduced_4lane_bringup.get("continuous_physical_run_cap_seconds") == 600
        and external_reduced_4lane_bringup.get("no_hardware_programming") is True
        and external_reduced_4lane_bringup.get("no_uart_write") is True
        and external_reduced_4lane_bringup.get("no_tfdu_drive") is True
        and len(external_reduced_4lane_bringup.get("pin_assignments", [])) == 16
        and len(external_reduced_4lane_bringup.get("probe_plan", [])) >= 4
        and len(external_reduced_4lane_bringup.get("phases", [])) >= 6
    )

    items = [
        ReadinessItem(
            "HARD-CONSTRAINT",
            "Root hard target remains unchanged before evaluating 8-lane hardware readiness.",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            rel(constraint),
            f"sha256={sha256(constraint)}",
        ),
        ReadinessItem(
            "RTL-8LANE-SIM",
            "RTL/model evidence covers 8-lane packet loopback, autoroute, 4+4 full-duplex, and capped rotating autoroute.",
            "PASS" if rtl_sim_ok else "MISSING",
            rel(POST_SUMMARY),
            "8-lane simulation/model evidence exists." if rtl_sim_ok else "Required 8-lane simulation markers were not found.",
        ),
        ReadinessItem(
            "BD-VECTOR-PORTS",
            "The hardware configuration script can create vector TFDU BD ports.",
            "PASS" if vector_port_proc_ok else "MISSING",
            rel(HW_CONFIG_TCL),
            "recreate_tfdu_vector_port creates [lane_count-1:0] ports." if vector_port_proc_ok else "Vector BD port helper missing.",
        ),
        ReadinessItem(
            "HW-SCRIPT-LANE-LIMIT",
            "The hardware configuration script must allow IR_LANE_COUNT=8 for real 8-lane hardware builds.",
            "BLOCKER" if lane_limit is not None and lane_limit < 8 else "PASS",
            rel(HW_CONFIG_TCL),
            f"Current parsed limit is 1..{lane_limit}; 8-lane hardware build is still blocked here."
            if lane_limit is not None and lane_limit < 8
            else f"Current parsed limit is 1..{lane_limit}.",
        ),
        ReadinessItem(
            "ACTIVE-XDC-A-ENDPOINT",
            "Active XDC must constrain eight A-endpoint TFDU lanes.",
            "PARTIAL" if len(a_lanes) < 8 else "PASS",
            rel(ACTIVE_XDC),
            f"Complete A endpoint lanes in active XDC: {len(a_lanes)}/8 ({a_lanes}); missing={a_missing}.",
        ),
        ReadinessItem(
            "ACTIVE-XDC-B-INTERNAL",
            "Board-internal A/B hardware loopback XDC must constrain the B/internal partner lanes when used.",
            "PARTIAL" if len(b_lanes) < 8 else "PASS",
            rel(ACTIVE_XDC),
            f"Complete B/internal endpoint lanes in active XDC: {len(b_lanes)}/8 ({b_lanes}); missing={b_missing}.",
        ),
        ReadinessItem(
            "ACTIVE-XDC-DUPLICATE-PINS",
            "Active TFDU PACKAGE_PIN assignments must not overlap.",
            "PASS" if not dupes else "FAIL",
            rel(ACTIVE_XDC),
            "No duplicate active TFDU package pins found." if not dupes else f"Duplicate pins: {dupes}",
        ),
        ReadinessItem(
            "DRAFT-XDC-8LANE-COVERAGE",
            "Draft XDC should not contain unresolved TODO pins for the 8-lane target.",
            "SUPERSEDED_BY_CANDIDATE" if draft_todos > 0 and candidate_complete else ("BLOCKER" if draft_todos > 0 else "PASS"),
            rel(DRAFT_XDC),
            f"Draft contains {draft_todos} TODO pin placeholders and only templates through lane 3."
            if draft_todos > 0
            else "No TODO pin placeholders found.",
        ),
        ReadinessItem(
            "CANDIDATE-XDC-8LANE-COVERAGE",
            "A generated candidate XDC should cover all 8 A-endpoint lanes and all 8 board-internal B lanes without duplicate package pins.",
            "PASS_CANDIDATE_REVIEW_REQUIRED" if candidate_complete else "MISSING",
            rel(CANDIDATE_XDC),
            f"Candidate has {len(candidate_assignments)}/64 assignments, A lanes={candidate_a_lanes}, B lanes={candidate_b_lanes}, duplicate_pins={candidate_dupes}; D19 remains excluded for manual review."
            if candidate_assignments
            else "No candidate 8-lane XDC assignments found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-XDC-8LANE",
            "A generated A-only external candidate XDC should cover all 8 A-endpoint lanes for a two-AX7010 topology without constraining local loop_* B ports.",
            "PASS_CANDIDATE_REVIEW_REQUIRED" if a_only_complete else "MISSING",
            rel(A_ONLY_CANDIDATE_XDC),
            f"A-only external candidate has {len(a_only_assignments)}/32 assignments, A lanes={a_only_a_lanes}, B lanes={a_only_b_lanes}, duplicate_pins={a_only_dupes}; intended for IR_B_MODE=external."
            if a_only_assignments
            else "No A-only external 8-lane XDC assignments found.",
        ),
        ReadinessItem(
            "SHUTDOWN-XDC-COVERAGE",
            "Shutdown bitstream constraints must cover every TFDU board that can be driven in a physical 8-lane run.",
            "PARTIAL" if shutdown_lane_markers < 32 else "PASS",
            rel(SHUTDOWN_XDC),
            f"Shutdown XDC currently has {shutdown_lane_markers} unique TFDU ports ({shutdown_ports}); existing shutdown coverage is J10/J11 scoped, not 8-lane scoped.",
        ),
        ReadinessItem(
            "CANDIDATE-SHUTDOWN-COVERAGE",
            "A generated 8-lane shutdown candidate should cover all candidate TFDU pins, drive MODE/TX low, drive SD high, and leave RX as constrained inputs.",
            "PASS_CANDIDATE_REVIEW_REQUIRED" if shutdown_candidate_ok else "MISSING",
            rel(SHUTDOWN_CANDIDATE_JSON),
            "Candidate shutdown covers 64/64 TFDU signals, drives 48 outputs to shutdown state, constrains 16 RX inputs, and has a build Tcl; bitstream build status is tracked separately."
            if shutdown_candidate_ok
            else "Missing or stale 8-lane shutdown candidate files.",
        ),
        ReadinessItem(
            "CANDIDATE-SHUTDOWN-BITSTREAM",
            "The generated 8-lane shutdown candidate should be buildable into a bitstream before any physical 8-lane TFDU run.",
            "PASS_CANDIDATE_REVIEW_REQUIRED" if shutdown_build_ok else "MISSING",
            rel(SHUTDOWN_BUILD_JSON),
            "Candidate shutdown bitstream was generated offline with 0 errors, 0 critical warnings, and only the known ZPS7-1 pure-PL Zynq DRC warning; it has not been programmed."
            if shutdown_build_ok
            else "No passing 8-lane shutdown bitstream build report found.",
        ),
        ReadinessItem(
            "CANDIDATE-HW-PROJECT-BUILD",
            "The 8-lane candidate hardware project should at least reach synthesis, and any implementation blocker should be classified before hardware promotion.",
            "SYNTH_PASS_IMPL_RESOURCE_BLOCKED" if candidate_project_synth_pass_resource_blocked else "MISSING",
            rel(CANDIDATE_PROJECT_BUILD_JSON),
            "8-lane stream_bidir candidate reaches synthesis, then implementation is blocked by XC7Z010 LUT over-utilization: 21125 required vs 17600 available; no hardware was programmed."
            if candidate_project_synth_pass_resource_blocked
            else "No classified 8-lane candidate project build result found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-PROJECT-BUILD",
            "The 8-lane A-only external hardware project should be built far enough to classify whether one AX7010 side of the final two-system topology fits XC7Z010.",
            "SYNTH_PASS_IMPL_RESOURCE_BLOCKED" if external_project_synth_pass_resource_blocked else "MISSING",
            rel(EXTERNAL_PROJECT_BUILD_JSON),
            f"8-lane A-only external candidate reaches synthesis, then implementation is blocked by XC7Z010 resource over-utilization: {external_resource_summary}; no hardware was programmed."
            if external_project_synth_pass_resource_blocked
            else "No classified 8-lane A-only external project build result found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-LANE-SCAN",
            "The A-only external hardware profile should be scanned by lane count to identify the largest XC7Z010 profile that can at least reach placement.",
            "PLACE_PASS_ONLY_1LANE" if external_lane_resource_scan_ok else "MISSING",
            rel(EXTERNAL_LANE_RESOURCE_SCAN_JSON),
            f"Lane-count scan shows max place-pass lane count {external_scan_max_place_pass}; lane {external_scan_first_blocked} and above are blocked by resource DRC. No hardware was programmed or driven."
            if external_lane_resource_scan_ok
            else "No classified A-only external lane resource scan found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-2LANE",
            "A reduced-resource A-only external option should show whether the 2-lane hardware profile can be made placement-feasible on XC7Z010.",
            "PASS_REDUCED_2LANE_PLACE" if external_option_ok else "MISSING",
            rel(EXTERNAL_RESOURCE_OPTION_SCAN_JSON),
            "Reduced external 2-lane option reaches place_design with fragment=64 and TX/RX async FIFOs=128; this is only placement evidence, not route/timing/bitstream/hardware acceptance."
            if external_option_ok
            else "No classified reduced-resource 2-lane external option scan found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-1TO4LANE",
            "The reduced-resource A-only external profile should be scanned from 1 to 4 lanes to check whether the final two-AX7010 expansion direction has placement headroom beyond 2 lanes.",
            "PASS_REDUCED_UP_TO_4LANE_PLACE" if external_reduced_lane_ok else "MISSING",
            rel(EXTERNAL_REDUCED_LANE_RESOURCE_SCAN_JSON),
            "Reduced external profile reaches place_design for 1, 2, 3, and 4 lanes with fragment=64 and TX/RX async FIFOs=128; this is place/resource evidence only, not route/timing/bitstream/TCP-DHCP/two-AX7010/TFDU hardware acceptance."
            if external_reduced_lane_ok
            else "No classified reduced-resource 1..4 lane external resource scan found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-5TO8-BOUNDARY",
            "The reduced-resource A-only external profile should be checked beyond 4 lanes to identify the first XC7Z010 resource boundary before treating 4 lanes as the current endpoint.",
            "PASS_FIRST_BLOCKED_5LANE" if external_reduced_5to8_ok else "MISSING",
            rel(EXTERNAL_REDUCED_5TO8_EXTENSION_JSON),
            "Reduced external extension scan shows lane 5 first fails placement at LUT 17801/17600, slice demand 3869/3845, and 1274 control sets; lanes 6..8 were not pursued after the first blocked boundary, no hardware was programmed, and the project was restored."
            if external_reduced_5to8_ok
            else "No classified reduced-resource 5..8 lane extension boundary report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-5LANE-FRAG32",
            "A smaller-packet reduced external profile should check whether the 5-lane boundary is caused by frame/cache sizing rather than lane count alone.",
            "PASS_PLACE_5LANE_FRAG32" if external_reduced_5lane_frag32_ok else "MISSING",
            rel(EXTERNAL_REDUCED_5LANE_FRAG32_JSON),
            "Reduced 5-lane external profile with fragment=32 and max_packet=128 reaches place_design at LUT 10697/17600, registers 14001/35200, BRAM 4.5/60, and 918 control sets; this is offline place evidence only and does not claim final 8-lane hardware acceptance."
            if external_reduced_5lane_frag32_ok
            else "No classified reduced-resource 5-lane fragment=32 place report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-5LANE-FRAG32-ROUTE",
            "The reduced 5-lane fragment=32 external profile should route and meet timing before it can be considered a stronger offline expansion candidate.",
            "PASS_ROUTE_TIMING_5LANE_FRAG32" if external_reduced_5lane_frag32_route_ok else "MISSING",
            rel(EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_JSON),
            f"Reduced 5-lane fragment=32 profile reaches route_design with WNS={external_reduced_5lane_frag32_route_timing.get('wns_ns')} ns, WHS={external_reduced_5lane_frag32_route_timing.get('whs_ns')} ns, routing_errors={external_reduced_5lane_frag32_route_route.get('routing_errors')}, and no critical/error DRC rows; this is offline route/timing evidence only."
            if external_reduced_5lane_frag32_route_ok
            else "No classified reduced-resource 5-lane fragment=32 route/timing report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-5LANE-FRAG32-BITSTREAM",
            "The reduced 5-lane fragment=32 external profile should produce an offline candidate bitstream before any later safe hardware/ILA review.",
            "PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED" if external_reduced_5lane_frag32_bitstream_ok else "MISSING",
            rel(EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM_JSON),
            f"Reduced 5-lane fragment=32 candidate bitstream exists with WNS={external_reduced_5lane_frag32_bitstream_timing.get('wns_ns')} ns, WHS={external_reduced_5lane_frag32_bitstream_timing.get('whs_ns')} ns, routing_errors={external_reduced_5lane_frag32_bitstream_route.get('routing_errors')}, size={external_reduced_5lane_frag32_bitstream.get('bitstream_size_bytes')} bytes, sha256={external_reduced_5lane_frag32_bitstream.get('bitstream_sha256')}; it has not been programmed."
            if external_reduced_5lane_frag32_bitstream_ok
            else "No classified reduced-resource 5-lane fragment=32 offline bitstream report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-8LANE-FRAG16-BITSTREAM",
            "A reduced 8-lane fragment=16 external profile should route, meet timing, and produce an offline bitstream before any final-rate raw PHY candidate can be reviewed.",
            "PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED" if external_reduced_8lane_frag16_bitstream_ok else "MISSING",
            rel(EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_JSON),
            f"Reduced 8-lane fragment=16 candidate bitstream exists with raw 32/16 Mbit/s lane capacity, WNS={external_reduced_8lane_frag16_bitstream_timing.get('wns_ns')} ns, WHS={external_reduced_8lane_frag16_bitstream_timing.get('whs_ns')} ns, routing_errors={external_reduced_8lane_frag16_bitstream_route.get('routing_errors')}, size={external_reduced_8lane_frag16_bitstream.get('bitstream_size_bytes')} bytes, sha256={external_reduced_8lane_frag16_bitstream.get('bitstream_sha256')}; it has not been programmed."
            if external_reduced_8lane_frag16_bitstream_ok
            else "No classified reduced-resource 8-lane fragment=16 offline bitstream report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-2LANE-ROUTE",
            "A reduced-resource A-only external 2-lane option should route and meet timing before it is considered a viable offline hardware profile.",
            "PASS_ROUTE_TIMING_REDUCED_2LANE" if external_route_ok else "MISSING",
            rel(EXTERNAL_REDUCED_ROUTE_JSON),
            f"Reduced external 2-lane option reaches route_design with WNS={external_route_timing.get('wns_ns')} ns, WHS={external_route_timing.get('whs_ns')} ns, routing_errors={external_route_route.get('routing_errors')}; no hardware was programmed."
            if external_route_ok
            else "No classified reduced-resource 2-lane route/timing report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-4LANE-ROUTE",
            "A reduced-resource A-only external 4-lane option should route and meet timing before it is considered the best current offline expansion profile for the two-AX7010 direction.",
            "PASS_ROUTE_TIMING_REDUCED_4LANE" if external_route_4lane_ok else "MISSING",
            rel(EXTERNAL_REDUCED_4LANE_ROUTE_JSON),
            f"Reduced external 4-lane option reaches route_design with WNS={external_route_4lane_timing.get('wns_ns')} ns, WHS={external_route_4lane_timing.get('whs_ns')} ns, routing_errors={external_route_4lane_route.get('routing_errors')}; no hardware was programmed."
            if external_route_4lane_ok
            else "No classified reduced-resource 4-lane route/timing report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-4LANE-BITSTREAM",
            "A reduced-resource A-only external 4-lane option should produce an offline candidate bitstream before any later safe hardware/ILA review.",
            "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" if external_bitstream_4lane_ok else "MISSING",
            rel(EXTERNAL_REDUCED_4LANE_BITSTREAM_JSON),
            f"Reduced external 4-lane candidate bitstream exists with WNS={external_bitstream_4lane_timing.get('wns_ns')} ns, WHS={external_bitstream_4lane_timing.get('whs_ns')} ns, routing_errors={external_bitstream_4lane_route.get('routing_errors')}, size={external_reduced_4lane_bitstream.get('bitstream_size_bytes')} bytes; it has not been programmed."
            if external_bitstream_4lane_ok
            else "No classified reduced-resource 4-lane offline bitstream report found.",
        ),
        ReadinessItem(
            "A-ONLY-EXTERNAL-REDUCED-4LANE-BRINGUP-PLAN",
            "A reduced-resource A-only external 4-lane option should have a safety-bounded ILA/bring-up plan before any future hardware programming.",
            "READY_FOR_MANUAL_REVIEW_NO_HARDWARE_RUN" if external_bringup_4lane_ok else "MISSING",
            rel(EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN_JSON),
            "Reduced external 4-lane bring-up plan covers pinmap review, passive ILA probes, shutdown-before/after rules, 600 s cap, and the current no-Ethernet boundary."
            if external_bringup_4lane_ok
            else "No classified reduced-resource 4-lane bring-up plan found.",
        ),
        ReadinessItem(
            "EXTERNAL-ENDPOINT-MODE",
            "The current hardware script has an external-endpoint path for using only the PS-controlled endpoint.",
            "PASS" if external_mode_ok else "MISSING",
            rel(HW_CONFIG_TCL),
            "IR_B_MODE=external path exists." if external_mode_ok else "No external endpoint mode found.",
        ),
        ReadinessItem(
            "NO-HARDWARE-ACTION",
            "This readiness run must not program FPGA, write UART, send TX data, or drive TFDU boards.",
            "PASS",
            "tools/check_8lane_hardware_readiness.py",
            "Static file/report parser only; no Vivado hardware session is opened.",
        ),
    ]
    status = overall_status(items)
    generated = datetime.now().isoformat(timespec="seconds")

    md_path = REPORTS / "8lane_hardware_readiness_current.md"
    json_path = REPORTS / "8lane_hardware_readiness_current.json"
    csv_path = REPORTS / "8lane_hardware_readiness_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "requirement", "status", "evidence", "note"])
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    assignment_rows = [
        [
            item.endpoint,
            str(item.lane),
            item.signal,
            item.port,
            item.package_pin,
            item.iostandard,
            item.source,
        ]
        for item in active_assignments
    ]
    item_rows = [[item.item_id, item.requirement, item.status, item.evidence, item.note] for item in items]
    md = [
        "# 8-Lane Hardware Readiness",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{status}`",
        f"- Active A-endpoint lane coverage: `{len(a_lanes)}/8`",
        f"- Active B/internal lane coverage: `{len(b_lanes)}/8`",
        f"- Candidate A/B 8-lane XDC coverage: `{len(candidate_a_lanes)}/8`, `{len(candidate_b_lanes)}/8`",
        f"- Candidate A-only external 8-lane XDC coverage: `{len(a_only_a_lanes)}/8`, B ports `{len(a_only_b_lanes)}/8`",
        f"- Candidate A-only external lane-count scan: `{external_scan_overall or 'MISSING'}`; max place-pass lane `{external_scan_max_place_pass}`; first resource-blocked lane `{external_scan_first_blocked}`",
        f"- Reduced A-only external 2-lane option: `{external_option_overall or 'MISSING'}`; fragment `{external_option_meta.get('fragment_bytes')}`; TX/RX FIFO `{external_option_meta.get('tx_async_fifo_depth')}/{external_option_meta.get('rx_async_fifo_depth')}`",
        f"- Reduced A-only external 1..4 lane scan: `{external_reduced_lane_overall or 'MISSING'}`; max place-pass lane `{external_reduced_lane_max_place_pass}`; first resource-blocked lane `{external_reduced_lane_first_blocked}`",
        f"- Reduced A-only external 5..8 lane extension: `{external_reduced_5to8_overall or 'MISSING'}`; first blocked lane `{external_reduced_5to8_extension.get('first_blocked_lane_count')}`; lane5 LUTs `{external_reduced_5to8_lane5.get('total_luts')}/{external_reduced_5to8_lane5.get('available_luts')}`; lane5 slices `{external_reduced_5to8_lane5.get('slice_required')}/{external_reduced_5to8_lane5.get('slice_available')}`",
        f"- Reduced A-only external 5-lane fragment=32 probe: `{external_reduced_5lane_frag32_overall or 'MISSING'}`; LUTs `{external_reduced_5lane_frag32_resources.get('slice_luts')}/{external_reduced_5lane_frag32_resources.get('slice_luts_available')}`; control sets `{external_reduced_5lane_frag32_resources.get('control_sets')}`; LUT delta vs 5lane fragment=64 `{external_reduced_5lane_frag32_comparison.get('lut_delta_vs_fragment64')}`",
        f"- Reduced A-only external 5-lane fragment=32 route/timing: `{external_reduced_5lane_frag32_route_overall or 'MISSING'}`; WNS `{external_reduced_5lane_frag32_route_timing.get('wns_ns')}` ns; WHS `{external_reduced_5lane_frag32_route_timing.get('whs_ns')}` ns; route errors `{external_reduced_5lane_frag32_route_route.get('routing_errors')}`",
        f"- Reduced A-only external 5-lane fragment=32 candidate bitstream: `{external_reduced_5lane_frag32_bitstream_overall or 'MISSING'}`; size `{external_reduced_5lane_frag32_bitstream.get('bitstream_size_bytes')}` bytes; sha256 `{external_reduced_5lane_frag32_bitstream.get('bitstream_sha256')}`",
        f"- Reduced A-only external 8-lane fragment=16 candidate bitstream: `{external_reduced_8lane_frag16_bitstream_overall or 'MISSING'}`; raw half `{external_reduced_8lane_frag16_bitstream.get('raw_half_mbps')}` Mbit/s; raw fdx/dir `{external_reduced_8lane_frag16_bitstream.get('raw_fdx_per_dir_mbps')}` Mbit/s; WNS `{external_reduced_8lane_frag16_bitstream_timing.get('wns_ns')}` ns; size `{external_reduced_8lane_frag16_bitstream.get('bitstream_size_bytes')}` bytes; sha256 `{external_reduced_8lane_frag16_bitstream.get('bitstream_sha256')}`",
        f"- Reduced A-only external 2-lane route/timing: `{external_route_overall or 'MISSING'}`; WNS `{external_route_timing.get('wns_ns')}` ns; WHS `{external_route_timing.get('whs_ns')}` ns",
        f"- Reduced A-only external 4-lane route/timing: `{external_route_4lane_overall or 'MISSING'}`; WNS `{external_route_4lane_timing.get('wns_ns')}` ns; WHS `{external_route_4lane_timing.get('whs_ns')}` ns",
        f"- Reduced A-only external 4-lane candidate bitstream: `{external_bitstream_4lane_overall or 'MISSING'}`; size `{external_reduced_4lane_bitstream.get('bitstream_size_bytes')}` bytes",
        f"- Reduced A-only external 4-lane bring-up plan: `{external_bringup_4lane_overall or 'MISSING'}`",
        f"- Hardware script lane limit: `1..{lane_limit}`",
        "- No hardware was programmed; no UART was written; no TFDU was driven.",
        "",
        "This report does not claim real 8-lane hardware acceptance. It identifies the concrete blockers before an 8-lane physical run can be safe or meaningful.",
        "",
        "## Readiness Items",
        "",
        md_table(["id", "requirement", "status", "evidence", "note"], item_rows),
        "",
        "## Active TFDU Pin Assignments",
        "",
        md_table(["endpoint", "lane", "signal", "port", "package_pin", "iostandard", "source"], assignment_rows),
        "",
        f"RF_COMM_8LANE_HARDWARE_READINESS overall={status} a_lanes={len(a_lanes)}/8 b_lanes={len(b_lanes)}/8 script_lane_limit={lane_limit}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": status,
        "hard_constraint_sha256": sha256(constraint),
        "a_endpoint_complete_lanes": a_lanes,
        "a_endpoint_missing": a_missing,
        "b_internal_complete_lanes": b_lanes,
        "b_internal_missing": b_missing,
        "candidate_a_endpoint_complete_lanes": candidate_a_lanes,
        "candidate_b_internal_complete_lanes": candidate_b_lanes,
        "candidate_duplicate_pins": candidate_dupes,
        "candidate_xdc": rel(CANDIDATE_XDC),
        "a_only_candidate_a_endpoint_complete_lanes": a_only_a_lanes,
        "a_only_candidate_b_internal_complete_lanes": a_only_b_lanes,
        "a_only_candidate_duplicate_pins": a_only_dupes,
        "a_only_candidate_xdc": rel(A_ONLY_CANDIDATE_XDC),
        "duplicate_pins": dupes,
        "hardware_script_lane_limit": lane_limit,
        "draft_todo_pin_count": draft_todos,
        "shutdown_tfdu_signal_marker_count": shutdown_lane_markers,
        "candidate_shutdown_ready_for_review": shutdown_candidate_ok,
        "candidate_shutdown_bitstream_ready_for_review": shutdown_build_ok,
        "candidate_shutdown_json": rel(SHUTDOWN_CANDIDATE_JSON),
        "candidate_shutdown_build_json": rel(SHUTDOWN_BUILD_JSON),
        "candidate_project_build_json": rel(CANDIDATE_PROJECT_BUILD_JSON),
        "candidate_project_synth_pass_resource_blocked": candidate_project_synth_pass_resource_blocked,
        "candidate_project_required_luts": candidate_project_build.get("required_luts"),
        "candidate_project_available_luts": candidate_project_build.get("available_luts"),
        "external_project_build_json": rel(EXTERNAL_PROJECT_BUILD_JSON),
        "external_project_synth_pass_resource_blocked": external_project_synth_pass_resource_blocked,
        "external_project_resources": external_resources,
        "external_project_resource_summary": external_resource_summary,
        "external_lane_resource_scan_json": rel(EXTERNAL_LANE_RESOURCE_SCAN_JSON),
        "external_lane_scan_overall": external_scan_overall,
        "external_lane_scan_max_place_pass_lane_count": external_scan_max_place_pass,
        "external_lane_scan_first_resource_blocked_lane_count": external_scan_first_blocked,
        "external_lane_scan_results": external_scan_results,
        "external_lane_resource_scan_ok": external_lane_resource_scan_ok,
        "external_resource_option_scan_json": rel(EXTERNAL_RESOURCE_OPTION_SCAN_JSON),
        "external_resource_option_scan_overall": external_option_overall,
        "external_resource_option_scan_meta": external_option_meta,
        "external_resource_option_scan_results": external_option_results,
        "external_resource_option_scan_ok": external_option_ok,
        "external_reduced_lane_resource_scan_json": rel(EXTERNAL_REDUCED_LANE_RESOURCE_SCAN_JSON),
        "external_reduced_lane_resource_scan_overall": external_reduced_lane_overall,
        "external_reduced_lane_resource_scan_meta": external_reduced_lane_meta,
        "external_reduced_lane_resource_scan_results": external_reduced_lane_results,
        "external_reduced_lane_resource_scan_max_place_pass_lane_count": external_reduced_lane_max_place_pass,
        "external_reduced_lane_resource_scan_first_resource_blocked_lane_count": external_reduced_lane_first_blocked,
        "external_reduced_lane_resource_scan_ok": external_reduced_lane_ok,
        "external_reduced_5to8_extension_json": rel(EXTERNAL_REDUCED_5TO8_EXTENSION_JSON),
        "external_reduced_5to8_extension_overall": external_reduced_5to8_overall,
        "external_reduced_5to8_extension_meta": external_reduced_5to8_meta,
        "external_reduced_5to8_extension_results": external_reduced_5to8_results,
        "external_reduced_5to8_extension_first_blocked_lane_count": external_reduced_5to8_extension.get("first_blocked_lane_count"),
        "external_reduced_5to8_extension_max_place_pass_lane_count": external_reduced_5to8_extension.get("max_place_pass_lane_count"),
        "external_reduced_5to8_extension_lane5": external_reduced_5to8_lane5,
        "external_reduced_5to8_extension_ok": external_reduced_5to8_ok,
        "external_reduced_5lane_frag32_json": rel(EXTERNAL_REDUCED_5LANE_FRAG32_JSON),
        "external_reduced_5lane_frag32_overall": external_reduced_5lane_frag32_overall,
        "external_reduced_5lane_frag32_meta": external_reduced_5lane_frag32_meta,
        "external_reduced_5lane_frag32_resources": external_reduced_5lane_frag32_resources,
        "external_reduced_5lane_frag32_comparison": external_reduced_5lane_frag32_comparison,
        "external_reduced_5lane_frag32_ok": external_reduced_5lane_frag32_ok,
        "external_reduced_5lane_frag32_route_json": rel(EXTERNAL_REDUCED_5LANE_FRAG32_ROUTE_JSON),
        "external_reduced_5lane_frag32_route_overall": external_reduced_5lane_frag32_route_overall,
        "external_reduced_5lane_frag32_route_meta": external_reduced_5lane_frag32_route_meta,
        "external_reduced_5lane_frag32_route_timing": external_reduced_5lane_frag32_route_timing,
        "external_reduced_5lane_frag32_route_route": external_reduced_5lane_frag32_route_route,
        "external_reduced_5lane_frag32_route_ok": external_reduced_5lane_frag32_route_ok,
        "external_reduced_5lane_frag32_bitstream_json": rel(EXTERNAL_REDUCED_5LANE_FRAG32_BITSTREAM_JSON),
        "external_reduced_5lane_frag32_bitstream_overall": external_reduced_5lane_frag32_bitstream_overall,
        "external_reduced_5lane_frag32_bitstream_timing": external_reduced_5lane_frag32_bitstream_timing,
        "external_reduced_5lane_frag32_bitstream_route": external_reduced_5lane_frag32_bitstream_route,
        "external_reduced_5lane_frag32_bitstream_size_bytes": external_reduced_5lane_frag32_bitstream.get("bitstream_size_bytes"),
        "external_reduced_5lane_frag32_bitstream_sha256": external_reduced_5lane_frag32_bitstream.get("bitstream_sha256"),
        "external_reduced_5lane_frag32_bitstream_ok": external_reduced_5lane_frag32_bitstream_ok,
        "external_reduced_8lane_frag16_bitstream_json": rel(EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_JSON),
        "external_reduced_8lane_frag16_bitstream_overall": external_reduced_8lane_frag16_bitstream_overall,
        "external_reduced_8lane_frag16_bitstream_timing": external_reduced_8lane_frag16_bitstream_timing,
        "external_reduced_8lane_frag16_bitstream_route": external_reduced_8lane_frag16_bitstream_route,
        "external_reduced_8lane_frag16_bitstream_size_bytes": external_reduced_8lane_frag16_bitstream.get("bitstream_size_bytes"),
        "external_reduced_8lane_frag16_bitstream_sha256": external_reduced_8lane_frag16_bitstream.get("bitstream_sha256"),
        "external_reduced_8lane_frag16_bitstream_raw_half_mbps": external_reduced_8lane_frag16_bitstream.get("raw_half_mbps"),
        "external_reduced_8lane_frag16_bitstream_raw_fdx_per_dir_mbps": external_reduced_8lane_frag16_bitstream.get("raw_fdx_per_dir_mbps"),
        "external_reduced_8lane_frag16_bitstream_ok": external_reduced_8lane_frag16_bitstream_ok,
        "external_reduced_2lane_route_json": rel(EXTERNAL_REDUCED_ROUTE_JSON),
        "external_reduced_2lane_route_overall": external_route_overall,
        "external_reduced_2lane_route_timing": external_route_timing,
        "external_reduced_2lane_route_route": external_route_route,
        "external_reduced_2lane_route_ok": external_route_ok,
        "external_reduced_4lane_route_json": rel(EXTERNAL_REDUCED_4LANE_ROUTE_JSON),
        "external_reduced_4lane_route_overall": external_route_4lane_overall,
        "external_reduced_4lane_route_timing": external_route_4lane_timing,
        "external_reduced_4lane_route_route": external_route_4lane_route,
        "external_reduced_4lane_route_ok": external_route_4lane_ok,
        "external_reduced_4lane_bitstream_json": rel(EXTERNAL_REDUCED_4LANE_BITSTREAM_JSON),
        "external_reduced_4lane_bitstream_overall": external_bitstream_4lane_overall,
        "external_reduced_4lane_bitstream_timing": external_bitstream_4lane_timing,
        "external_reduced_4lane_bitstream_route": external_bitstream_4lane_route,
        "external_reduced_4lane_bitstream_size_bytes": external_reduced_4lane_bitstream.get("bitstream_size_bytes"),
        "external_reduced_4lane_bitstream_sha256": external_reduced_4lane_bitstream.get("bitstream_sha256"),
        "external_reduced_4lane_bitstream_ok": external_bitstream_4lane_ok,
        "external_reduced_4lane_bringup_plan_json": rel(EXTERNAL_REDUCED_4LANE_BRINGUP_PLAN_JSON),
        "external_reduced_4lane_bringup_plan_overall": external_bringup_4lane_overall,
        "external_reduced_4lane_bringup_plan_ok": external_bringup_4lane_ok,
        "candidate_shutdown_top": rel(SHUTDOWN_CANDIDATE_TOP),
        "candidate_shutdown_xdc": rel(SHUTDOWN_CANDIDATE_XDC),
        "candidate_shutdown_build_tcl": rel(SHUTDOWN_CANDIDATE_BUILD_TCL),
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "items": [asdict(item) for item in items],
        "assignments": [asdict(item) for item in active_assignments],
        "candidate_assignments": [asdict(item) for item in candidate_assignments],
        "a_only_candidate_assignments": [asdict(item) for item in a_only_assignments],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_8LANE_HARDWARE_READINESS overall={status} a_lanes={len(a_lanes)}/8 b_lanes={len(b_lanes)}/8 script_lane_limit={lane_limit}")
    return 0 if status != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
