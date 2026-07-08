from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
MATRIX_CSV = REPORTS / "target_acceptance_matrix_current.csv"
READINESS_JSON = REPORTS / "8lane_hardware_readiness_current.json"
EXPECTED_OPEN_IDS = ["N03", "N04", "S05", "A01", "A02"]
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class RemainingAcceptanceItem:
    item_id: str
    current_status: str
    requirement: str
    current_blocker: str
    preconditions: list[str]
    required_hardware: list[str]
    safe_command: str
    pass_criteria: list[str]
    evidence_patterns: list[str]
    safety_guard: list[str]
    shutdown_requirement: str
    implementation_gap: str
    notes: list[str]


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


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def load_open_rows() -> dict[str, dict[str, str]]:
    if not MATRIX_CSV.exists():
        raise FileNotFoundError(f"Missing target acceptance matrix: {MATRIX_CSV}")
    with MATRIX_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = {row.get("item_id", ""): row for row in csv.DictReader(f)}
    open_rows = {
        item_id: rows[item_id]
        for item_id in EXPECTED_OPEN_IDS
        if item_id in rows and rows[item_id].get("status") in {"DEFERRED_NO_ETHERNET", "MISSING_HARDWARE", "PARTIAL_G1_ONLY"}
    }
    missing = [item_id for item_id in EXPECTED_OPEN_IDS if item_id not in open_rows]
    if missing:
        raise RuntimeError(f"Remaining hardware plan is stale; missing open rows: {', '.join(missing)}")
    extra_open = [
        item_id
        for item_id, row in rows.items()
        if row.get("status") in {"DEFERRED_NO_ETHERNET", "MISSING_HARDWARE", "PARTIAL_G1_ONLY"} and item_id not in EXPECTED_OPEN_IDS
    ]
    if extra_open:
        raise RuntimeError(f"Unexpected open target rows not covered by this plan: {', '.join(extra_open)}")
    return open_rows


def make_items(open_rows: dict[str, dict[str, str]]) -> list[RemainingAcceptanceItem]:
    hw_loop_tcl = ROOT / "tools" / "configure_lane0_ab_hw_loopback.tcl"
    hw_loop_text = read_text(hw_loop_tcl)
    readiness = read_json(READINESS_JSON)
    script_limit = readiness.get("hardware_script_lane_limit")
    a_lanes = len(readiness.get("a_endpoint_complete_lanes", []))
    b_lanes = len(readiness.get("b_internal_complete_lanes", []))
    candidate_a_lanes = len(readiness.get("candidate_a_endpoint_complete_lanes", []))
    candidate_b_lanes = len(readiness.get("candidate_b_internal_complete_lanes", []))
    candidate_shutdown_ready = bool(readiness.get("candidate_shutdown_ready_for_review"))
    candidate_shutdown_bitstream_ready = bool(readiness.get("candidate_shutdown_bitstream_ready_for_review"))
    candidate_project_resource_blocked = bool(readiness.get("candidate_project_synth_pass_resource_blocked"))
    candidate_required_luts = readiness.get("candidate_project_required_luts")
    candidate_available_luts = readiness.get("candidate_project_available_luts")
    external_project_resource_blocked = bool(readiness.get("external_project_synth_pass_resource_blocked"))
    external_resource_summary = readiness.get("external_project_resource_summary") or ""
    external_scan_overall = readiness.get("external_lane_scan_overall")
    external_scan_max_place_pass = readiness.get("external_lane_scan_max_place_pass_lane_count")
    external_scan_first_blocked = readiness.get("external_lane_scan_first_resource_blocked_lane_count")
    external_scan_resource_blocked = external_scan_overall == "PLACE_PASS_ONLY_1LANE"
    external_option_overall = readiness.get("external_resource_option_scan_overall")
    external_option_meta = readiness.get("external_resource_option_scan_meta") or {}
    external_option_ok = bool(readiness.get("external_resource_option_scan_ok"))
    external_reduced_lane_overall = readiness.get("external_reduced_lane_resource_scan_overall")
    external_reduced_lane_meta = readiness.get("external_reduced_lane_resource_scan_meta") or {}
    external_reduced_lane_max_place_pass = readiness.get("external_reduced_lane_resource_scan_max_place_pass_lane_count")
    external_reduced_lane_first_blocked = readiness.get("external_reduced_lane_resource_scan_first_resource_blocked_lane_count")
    external_reduced_lane_ok = bool(readiness.get("external_reduced_lane_resource_scan_ok"))
    external_route_overall = readiness.get("external_reduced_2lane_route_overall")
    external_route_timing = readiness.get("external_reduced_2lane_route_timing") or {}
    external_route_route = readiness.get("external_reduced_2lane_route_route") or {}
    external_route_ok = bool(readiness.get("external_reduced_2lane_route_ok"))
    external_route_4lane_overall = readiness.get("external_reduced_4lane_route_overall")
    external_route_4lane_timing = readiness.get("external_reduced_4lane_route_timing") or {}
    external_route_4lane_route = readiness.get("external_reduced_4lane_route_route") or {}
    external_route_4lane_ok = bool(readiness.get("external_reduced_4lane_route_ok"))
    external_route_5lane_frag32_overall = readiness.get("external_reduced_5lane_frag32_route_overall")
    external_route_5lane_frag32_timing = readiness.get("external_reduced_5lane_frag32_route_timing") or {}
    external_route_5lane_frag32_route = readiness.get("external_reduced_5lane_frag32_route_route") or {}
    external_route_5lane_frag32_ok = bool(readiness.get("external_reduced_5lane_frag32_route_ok"))
    external_bitstream_5lane_frag32_overall = readiness.get("external_reduced_5lane_frag32_bitstream_overall")
    external_bitstream_5lane_frag32_size = readiness.get("external_reduced_5lane_frag32_bitstream_size_bytes")
    external_bitstream_5lane_frag32_sha = readiness.get("external_reduced_5lane_frag32_bitstream_sha256")
    external_bitstream_5lane_frag32_ok = bool(readiness.get("external_reduced_5lane_frag32_bitstream_ok"))
    external_bitstream_8lane_frag16_overall = readiness.get("external_reduced_8lane_frag16_bitstream_overall")
    external_bitstream_8lane_frag16_size = readiness.get("external_reduced_8lane_frag16_bitstream_size_bytes")
    external_bitstream_8lane_frag16_sha = readiness.get("external_reduced_8lane_frag16_bitstream_sha256")
    external_bitstream_8lane_frag16_raw_half = readiness.get("external_reduced_8lane_frag16_bitstream_raw_half_mbps")
    external_bitstream_8lane_frag16_raw_fdx = readiness.get("external_reduced_8lane_frag16_bitstream_raw_fdx_per_dir_mbps")
    external_bitstream_8lane_frag16_ok = bool(readiness.get("external_reduced_8lane_frag16_bitstream_ok"))
    external_bitstream_4lane_overall = readiness.get("external_reduced_4lane_bitstream_overall")
    external_bitstream_4lane_size = readiness.get("external_reduced_4lane_bitstream_size_bytes")
    external_bitstream_4lane_sha = readiness.get("external_reduced_4lane_bitstream_sha256")
    external_bitstream_4lane_ok = bool(readiness.get("external_reduced_4lane_bitstream_ok"))
    external_bringup_4lane_overall = readiness.get("external_reduced_4lane_bringup_plan_overall")
    external_bringup_4lane_ok = bool(readiness.get("external_reduced_4lane_bringup_plan_ok"))
    external_5to8_overall = readiness.get("external_reduced_5to8_extension_overall")
    external_5to8_lane5 = readiness.get("external_reduced_5to8_extension_lane5") or {}
    external_5to8_ok = bool(readiness.get("external_reduced_5to8_extension_ok"))
    draft_todos = readiness.get("draft_todo_pin_count")
    if script_limit is not None and int(script_limit) < 8:
        lane8_gap = (
            f"Current hardware configuration script limits IR_LANE_COUNT to 1..{script_limit}; "
            "a real 8-lane hardware build/constraint path is still required."
        )
    elif candidate_a_lanes == 8 and candidate_b_lanes == 8 and a_lanes < 8:
        if candidate_shutdown_ready and candidate_shutdown_bitstream_ready and candidate_project_resource_blocked:
            external_gap = (
                f" The A-only external 8-lane profile for the two-AX7010 topology also reaches synthesis but is resource-blocked on XC7Z010 ({external_resource_summary});"
                if external_project_resource_blocked
                else ""
            )
            external_scan_gap = (
                f" lane-count scan of that external profile confirms only {external_scan_max_place_pass} lane reaches place_design, with lane {external_scan_first_blocked} and above resource-blocked;"
                if external_scan_resource_blocked
                else ""
            )
            external_option_gap = (
                " a reduced 2-lane external option with "
                f"fragment={external_option_meta.get('fragment_bytes')}, "
                f"TX/RX FIFO={external_option_meta.get('tx_async_fifo_depth')}/{external_option_meta.get('rx_async_fifo_depth')} "
                "does reach place_design, so resource reduction is a viable next build direction, but it is not route/timing/bitstream/hardware acceptance;"
                if external_option_ok
                else ""
            )
            external_reduced_lane_gap = (
                " a reduced 1..4-lane external scan using "
                f"fragment={external_reduced_lane_meta.get('fragment_bytes')}, "
                f"TX/RX FIFO={external_reduced_lane_meta.get('tx_async_fifo_depth')}/{external_reduced_lane_meta.get('rx_async_fifo_depth')} "
                f"reaches place_design up to {external_reduced_lane_max_place_pass} lanes with first blocked lane {external_reduced_lane_first_blocked}; "
                "this improves the offline expansion evidence, but it is still not route/timing/bitstream/TCP-DHCP/two-AX7010/TFDU hardware acceptance;"
                if external_reduced_lane_ok
                else ""
            )
            external_route_gap = (
                " the same reduced 2-lane external option also reaches route_design and meets timing "
                f"(WNS={external_route_timing.get('wns_ns')} ns, WHS={external_route_timing.get('whs_ns')} ns, routing_errors={external_route_route.get('routing_errors')}); "
                "this proves an offline route/timing-feasible 2-lane profile, but still does not prove bitstream programming, TCP/DHCP, two-AX7010, TFDU hardware, or rotating-shaft acceptance;"
                if external_route_ok
                else ""
            )
            external_route_4lane_gap = (
                " the reduced 4-lane external option now also reaches route_design and meets timing "
                f"(WNS={external_route_4lane_timing.get('wns_ns')} ns, WHS={external_route_4lane_timing.get('whs_ns')} ns, routing_errors={external_route_4lane_route.get('routing_errors')}); "
                "this remains offline lower-rate expansion evidence, not TCP/DHCP, two-AX7010, TFDU hardware, or rotating-shaft acceptance;"
                if external_route_4lane_ok
                else ""
            )
            external_bitstream_4lane_gap = (
                f" that reduced 4-lane option also has an offline candidate bitstream ({external_bitstream_4lane_size} bytes, sha256={external_bitstream_4lane_sha}); "
                "it is ready for manual review but has not been programmed or accepted on TFDU hardware;"
                if external_bitstream_4lane_ok
                else ""
            )
            external_route_5lane_frag32_gap = (
                " the reduced 5-lane fragment=32 external option reaches route_design and meets timing "
                f"(WNS={external_route_5lane_frag32_timing.get('wns_ns')} ns, WHS={external_route_5lane_frag32_timing.get('whs_ns')} ns, routing_errors={external_route_5lane_frag32_route.get('routing_errors')}); "
                "this proves the current strongest reduced offline build path, but it is still lower-rate small-packet evidence rather than final 32/16 Mbit/s hardware acceptance;"
                if external_route_5lane_frag32_ok
                else ""
            )
            external_bitstream_5lane_frag32_gap = (
                f" that reduced 5-lane fragment=32 option also has an offline candidate bitstream ({external_bitstream_5lane_frag32_size} bytes, sha256={external_bitstream_5lane_frag32_sha}); "
                "it has not been programmed, has not been accepted on TFDU hardware, and remains review-required;"
                if external_bitstream_5lane_frag32_ok
                else ""
            )
            external_bitstream_8lane_frag16_gap = (
                f" a reduced 8-lane fragment=16 option now has an offline candidate bitstream ({external_bitstream_8lane_frag16_size} bytes, sha256={external_bitstream_8lane_frag16_sha}) "
                f"with raw half={external_bitstream_8lane_frag16_raw_half} Mbit/s and raw full-duplex-per-direction={external_bitstream_8lane_frag16_raw_fdx} Mbit/s; "
                "it reaches the final raw lane-count target offline but has not been programmed, pin-reviewed for real hardware, accepted on TFDU hardware, accepted over TCP/DHCP, or validated on a rotating shaft;"
                if external_bitstream_8lane_frag16_ok
                else ""
            )
            external_bringup_4lane_gap = (
                " a reduced 4-lane bring-up/ILA plan is ready for manual review and records the pinmap, passive ILA probes, shutdown-before/after rule, 600 s cap, and no-Ethernet boundary;"
                if external_bringup_4lane_ok
                else ""
            )
            external_5to8_gap = (
                " a reduced 5..8-lane extension scan confirms the first reduced-profile resource boundary at lane 5 "
                f"(LUT={external_5to8_lane5.get('total_luts')}/{external_5to8_lane5.get('available_luts')}, "
                f"slices={external_5to8_lane5.get('slice_required')}/{external_5to8_lane5.get('slice_available')}, "
                f"control_sets={external_5to8_lane5.get('control_sets')});"
                if external_5to8_ok
                else ""
            )
            lane8_gap = (
                f"8-lane candidate XDC now covers {candidate_a_lanes}/8 A-endpoint lanes and {candidate_b_lanes}/8 board-internal B lanes, "
                "candidate shutdown coverage is ready for review, and the candidate shutdown bitstream has been built offline. "
                f"The 8-lane stream_bidir hardware project reaches synthesis but implementation is blocked on XC7Z010 LUT capacity "
                f"({candidate_required_luts} required vs {candidate_available_luts} available); "
                f"{external_gap}{external_scan_gap}{external_option_gap}{external_reduced_lane_gap}{external_route_gap}{external_route_4lane_gap}{external_bitstream_4lane_gap}{external_route_5lane_frag32_gap}{external_bitstream_5lane_frag32_gap}{external_bitstream_8lane_frag16_gap}{external_bringup_4lane_gap}{external_5to8_gap} "
                "a dedicated 8-lane hardware safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate; "
                "manual pin review, shutdown-flow review, real TFDU wiring, Ethernet/network preconditions, and controlled hardware acceptance are required before real 8-lane hardware use."
            )
        elif candidate_shutdown_ready and candidate_shutdown_bitstream_ready:
            lane8_gap = (
                f"8-lane candidate XDC now covers {candidate_a_lanes}/8 A-endpoint lanes and {candidate_b_lanes}/8 board-internal B lanes, "
                "candidate shutdown coverage is ready for review, and the candidate shutdown bitstream has been built offline, but "
                f"active XDC still constrains only {a_lanes}/8 A-endpoint lanes and {b_lanes}/8 B lanes; "
                "candidate pinmap/shutdown still requires manual review and controlled hardware programming before hardware use."
            )
        elif candidate_shutdown_ready:
            lane8_gap = (
                f"8-lane candidate XDC now covers {candidate_a_lanes}/8 A-endpoint lanes and {candidate_b_lanes}/8 board-internal B lanes, "
                "and candidate shutdown coverage is also ready for review, but "
                f"active XDC still constrains only {a_lanes}/8 A-endpoint lanes and {b_lanes}/8 B lanes; "
                "candidate pinmap/shutdown requires manual review before hardware use."
            )
        else:
            lane8_gap = (
                f"8-lane candidate XDC now covers {candidate_a_lanes}/8 A-endpoint lanes and {candidate_b_lanes}/8 board-internal B lanes, "
                f"but active XDC still constrains only {a_lanes}/8 A-endpoint lanes and {b_lanes}/8 B lanes; "
                "candidate pinmap requires manual review before hardware use."
            )
    elif a_lanes < 8:
        lane8_gap = (
            f"Hardware configuration script now allows 8 lanes, but active XDC constrains only {a_lanes}/8 A-endpoint lanes "
            f"and {b_lanes}/8 board-internal B lanes; draft TODO pin placeholders={draft_todos}."
        )
    elif "IR_LANE_COUNT must be in 1..4" in hw_loop_text:
        lane8_gap = "Current hardware configuration script limits IR_LANE_COUNT to 1..4; a real 8-lane hardware build/constraint path is still required."
    else:
        lane8_gap = "8-lane script/XDC readiness is not the current blocker; real 8-lane hardware validation is still required."
    runtime_cap = "Continuous physical traffic must stay at or below 600 s; longer target durations are counted as 600 s."
    shutdown_after_tfdu = "Required after every physical run that drives TFDU/TX: program the shutdown bitstream before the next non-test operation."

    return [
        RemainingAcceptanceItem(
            item_id="N03",
            current_status=open_rows["N03"]["status"],
            requirement=open_rows["N03"]["requirement"],
            current_blocker="Development board Ethernet is not connected and this cannot be changed right now.",
            preconditions=[
                "Ethernet cable/link is physically present and link-up is observable.",
                "PS lwIP bridge BOOT.BIN is running on the board.",
                "Board IP is known from DHCP or static fallback.",
                "COM3 UART probe is optional; use -SkipUartProbe if USB/UART is unstable but IP is known.",
            ],
            required_hardware=[
                "One AX7010/ZYNQ-7010 board.",
                "Host PC network interface connected to the board network.",
                "No TFDU board is required for this PS-to-PC network acceptance.",
            ],
            safe_command=(
                "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_ps_pc_tcp_dhcp_acceptance_safe.ps1 "
                "-TargetHost <board_ip> -UseStaticFallback -ComPort COM3 -UartProbeSeconds 20 "
                "-ReconnectCycles 4 -TimeoutSeconds 5.0"
            ),
            pass_criteria=[
                "BOARD_TCP_DHCP_ACCEPTANCE_PASS=1",
                "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=0",
                "SMOKE_OK=1",
                "RECONNECT_OK=1",
                "DHCP_OR_STATIC_EVIDENCE_OK=1",
                "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1",
                "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
                "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1",
            ],
            evidence_patterns=[
                "reports/real_acceptance_template/ps_pc_tcp_dhcp_summary_template.txt",
                "reports/real_acceptance_evidence_validation_current.*",
                "reports/ps_pc_tcp_dhcp_acceptance_safe_*.summary.txt",
                "reports/ps_pc_tcp_dhcp_acceptance_safe_*.md",
                "reports/ps_pc_tcp_dhcp_acceptance_safe_*.smoke.log",
                "reports/ps_pc_tcp_dhcp_acceptance_safe_*.reconnect.log",
            ],
            safety_guard=[
                "This test must not program FPGA hardware.",
                "This test must not drive TFDU or send IR TX data.",
                "If Ethernet is still absent, the correct outcome is BLOCKED, not repeated retries.",
            ],
            shutdown_requirement="Not required because this network-only test does not drive TFDU/TX.",
            implementation_gap="No code gap known; blocked by missing Ethernet link. A real-acceptance evidence template/validator exists so this item cannot be marked real-pass from dry-run or offline logs.",
            notes=[
                "This item proves real PS-to-PC TCP/DHCP/reconnect only; it does not prove IR traffic.",
                "Use tools/validate_real_acceptance_evidence.py --mode ps_pc_tcp_dhcp against the real summary before claiming acceptance.",
                runtime_cap,
            ],
        ),
        RemainingAcceptanceItem(
            item_id="N04",
            current_status=open_rows["N04"]["status"],
            requirement=open_rows["N04"]["requirement"],
            current_blocker="Only offline two-endpoint model evidence exists; two complete AX7010 systems have not been run together.",
            preconditions=[
                "Two complete AX7010 systems are available and powered.",
                "Each system has Ethernet link and a known IP address.",
                "Each system is running the PS bridge image compatible with the host RFCM client.",
                "IR lanes are wired/aligned between systems and initial lane masks are selected.",
                runtime_cap,
            ],
            required_hardware=[
                "Two AX7010/ZYNQ-7010 boards.",
                "Two PS Ethernet links or a network path from host PC to both boards.",
                "TFDU boards and optical path for the selected lanes.",
            ],
            safe_command=(
                "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_two_ax7010_end_to_end_acceptance_safe.ps1 "
                "-TargetHostA <ax7010_a_ip> -TargetHostB <ax7010_b_ip> -AllowTraffic -ProgramShutdownAfterRun "
                "-Repeat 32 -PayloadSize 256 -TimeoutSeconds 5.0 -ReconnectCycles 4 -DurationSeconds 600"
            ),
            pass_criteria=[
                "TWO_AX7010_REAL_ACCEPTANCE_PASS=1",
                "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=0",
                "SMOKE_BOTH_OK=1",
                "RECONNECT_BOTH_OK=1",
                "BIDIRECTIONAL_TRAFFIC_OK=1",
                "TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1",
                "Payload integrity is preserved in both directions.",
                "No deadlock or unrecovered error is reported.",
            ],
            evidence_patterns=[
                "reports/real_acceptance_template/two_ax7010_summary_template.txt",
                "reports/real_acceptance_template/two_ax7010_criteria_template.csv",
                "reports/real_acceptance_evidence_validation_current.*",
                "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
                "reports/two_ax7010_end_to_end_acceptance_safe_*.md",
                "reports/two_ax7010_end_to_end_acceptance_safe_*.criteria.csv",
                "reports/two_ax7010_end_to_end_acceptance_safe_*/real_traffic*.log",
            ],
            safety_guard=[
                "Run only after Ethernet and optical lane preconditions are true.",
                "Use -AllowTraffic only when intentional real traffic is safe.",
                "Use -ProgramShutdownAfterRun for every real TFDU/TX run.",
                "Do not exceed 600 s continuous TFDU/TX activity.",
            ],
            shutdown_requirement=shutdown_after_tfdu,
            implementation_gap="No additional safe wrapper gap known; real hardware is missing/not connected. The two-AX7010 wrapper now requires -ProgramShutdownAfterRun for real traffic and reports TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1 before real acceptance can pass.",
            notes=[
                "The existing offline model already covers two endpoints and 8-lane routing, but it is not real hardware acceptance.",
                "The current board has no Ethernet, so this item is not runnable now.",
                "Use tools/validate_real_acceptance_evidence.py --mode two_ax7010 against the real summary before claiming acceptance.",
            ],
        ),
        RemainingAcceptanceItem(
            item_id="S05",
            current_status=open_rows["S05"]["status"],
            requirement=open_rows["S05"]["requirement"],
            current_blocker="No real 20 cm / 600 rpm rotating-shaft fixture evidence exists.",
            preconditions=[
                "Real rotating-shaft fixture has approximately 20 cm diameter and can run at 600 rpm.",
                "Two-system IR path or equivalent rotating optical path is assembled.",
                "Fixture speed and diameter metadata are logged with the communication evidence.",
                "Fixture CSV should pass tools/validate_rotating_fixture_log.py before real acceptance is claimed.",
                "Each continuous communication segment is capped at 600 s under the active safety rule.",
            ],
            required_hardware=[
                "Rotating-shaft fixture, 20 cm class diameter.",
                "600 rpm speed control/measurement.",
                "AX7010/TFDU systems arranged across the rotating interface.",
                "Host logging for payload, link, retry, reconnect, and error statistics.",
            ],
            safe_command=(
                "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_rotating_shaft_acceptance_safe.ps1 "
                "-TargetHostA <ax7010_a_ip> -TargetHostB <ax7010_b_ip> -AllowTraffic -ProgramShutdownAfterRun "
                "-ShaftDiameterMm 200 -Rpm 600 -FixtureLogPath <fixture_log.csv> -DurationSeconds 600 "
                "-Repeat 32 -PayloadSize 256 -TimeoutSeconds 5.0 -ReconnectCycles 4"
            ),
            pass_criteria=[
                "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=1",
                "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=0",
                "ROTATING_SHAFT_SHUTDOWN_AFTER_RUN_PASS=1",
                "Real run metadata includes shaft_diameter_mm about 200 and rpm about 600.",
                "Continuous communication is stable for the capped 600 s acceptance window.",
                "All payload checks pass; retry/recovery may occur but no unrecovered error or deadlock occurs.",
                "Route/lane statistics show communication survived periodic alignment changes.",
                "If a longer 2-hour target is referenced, it is represented by model evidence or segmented runs; each physical continuous segment remains capped at 600 s.",
            ],
            evidence_patterns=[
                "reports/rotating_fixture_log_template.csv",
                "reports/rotating_fixture_log_validation_current.*",
                "reports/real_acceptance_template/rotating_shaft_summary_template.txt",
                "reports/real_acceptance_evidence_validation_current.*",
                "reports/rotating_shaft_acceptance_safe_*.summary.txt",
                "reports/rotating_shaft_acceptance_safe_*.md",
                "reports/rotating_shaft_acceptance_safe_*.criteria.csv",
                "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
                "reports/rotating_shaft_real_acceptance_*.md",
                "reports/rotating_shaft_real_acceptance_*.csv",
            ],
            safety_guard=[
                "The dedicated wrapper blocks real traffic unless -AllowTraffic and -ProgramShutdownAfterRun are both set.",
                "Do not run the TFDU boards continuously for more than 600 s.",
                "Stop immediately on optical misalignment that causes persistent TX failures.",
                "Keep shutdown programming as the last step of each physical run.",
            ],
            shutdown_requirement=shutdown_after_tfdu,
            implementation_gap="Dedicated safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate; fixture-log and real-acceptance evidence validators/templates exist for 20 cm / 600 rpm / 600 s segment evidence; real acceptance still needs Ethernet, two-system/IR hardware, a non-template fixture log, evidence-validator pass, and shutdown-after-run execution.",
            notes=[
                "Simulation/model evidence already covers 20 cm, 600 rpm, and 8-lane autoroute under the cap.",
                "The rotating fixture log template is readiness evidence only and is not real rotating-shaft acceptance.",
                "Use tools/validate_real_acceptance_evidence.py --mode rotating_shaft against the real summary, criteria CSV, and fixture validation report before claiming acceptance.",
                "This item remains real fixture acceptance, not simulation.",
            ],
        ),
        RemainingAcceptanceItem(
            item_id="A01",
            current_status=open_rows["A01"]["status"],
            requirement=open_rows["A01"]["requirement"],
            current_blocker="Single-board/single-lane IR is accepted, but real PC-PS-PL-IR-external-IR product loop is not closed.",
            preconditions=[
                "N03 real PS-to-PC TCP/DHCP acceptance has passed.",
                "At least one real IR lane is wired between the product endpoints.",
                "For two-system product acceptance, N04 has passed or is being run as part of this item.",
                "Host logs collect command, payload, status, retry, error, and reconnect records.",
            ],
            required_hardware=[
                "Host PC.",
                "One or two AX7010/ZYNQ-7010 systems, depending on the acceptance topology.",
                "TFDU transmitter/receiver boards for the selected lane set.",
                "Ethernet link to the PS side under test.",
            ],
            safe_command=(
                "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_product_loop_acceptance_safe.ps1 "
                "-Topology two_ax7010 -TargetHostA <ax7010_a_ip> -TargetHostB <ax7010_b_ip> "
                "-AllowTraffic -ProgramShutdownAfterRun -DurationSeconds 600 -Repeat 32 -PayloadSize 256 "
                "-TimeoutSeconds 5.0 -ReconnectCycles 4"
            ),
            pass_criteria=[
                "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=1",
                "PRODUCT_LOOP_REAL_ACCEPTANCE_BLOCKED=0",
                "PRODUCT_LOOP_SHUTDOWN_AFTER_RUN_PASS=1",
                "PC-to-PS command/config/TX data is accepted.",
                "PS-to-PC RX data/status/error/statistics are returned.",
                "IR payload traverses the real PL/TFDU path and is verified end-to-end.",
                "TCP reconnect and link recovery remain usable after a short interruption.",
                "No data corruption, unrecovered error, or state-machine deadlock appears in the capped run.",
            ],
            evidence_patterns=[
                "reports/real_acceptance_template/product_loop_summary_template.txt",
                "reports/real_acceptance_evidence_validation_current.*",
                "reports/product_loop_acceptance_safe_*.summary.txt",
                "reports/product_loop_acceptance_safe_*.md",
                "reports/product_loop_acceptance_safe_*.criteria.csv",
                "reports/ps_pc_tcp_dhcp_acceptance_safe_*.summary.txt",
                "reports/two_ax7010_end_to_end_acceptance_safe_*.summary.txt",
                "reports/*product_loop*_acceptance*.md",
            ],
            safety_guard=[
                "The dedicated wrapper blocks real traffic unless -AllowTraffic and -ProgramShutdownAfterRun are both set.",
                "Do not classify network-only or simulation-only evidence as full product loop acceptance.",
                "Do not exceed 600 s continuous TFDU/TX activity.",
                "Keep shutdown programming after every real TFDU/TX run.",
            ],
            shutdown_requirement=shutdown_after_tfdu,
            implementation_gap="Dedicated safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate; a real-acceptance evidence template/validator exists; real product-loop acceptance still needs Ethernet, selected one-board/two-board topology, real IR path, evidence-validator pass, and shutdown-after-run execution.",
            notes=[
                "Current G1 lane0 hardware evidence is necessary but not sufficient for this product-level item.",
                "No Ethernet is currently connected, so the real PC/PS portion is deferred.",
                "Use tools/validate_real_acceptance_evidence.py --mode product_loop against the real summary and criteria CSV before claiming acceptance.",
            ],
        ),
        RemainingAcceptanceItem(
            item_id="A02",
            current_status=open_rows["A02"]["status"],
            requirement=open_rows["A02"]["requirement"],
            current_blocker="8-lane digital simulation passes, but real 8-TFDU hardware wiring has not been validated.",
            preconditions=[
                "Eight TFDU boards are available and wired to a validated pin map.",
                "The Vivado project and XDC expose eight lane TX/RX/SD/MODE signals on real pins.",
                "The hardware build supports IR_LANE_COUNT=8.",
                "Initial tests are segmented and each continuous physical run is capped at 600 s.",
            ],
            required_hardware=[
                "Eight TFDU small boards for the lane array.",
                "AX7010 GPIO capacity and verified pin constraints for all lane signals.",
                "Optical alignment or board-loopback arrangement for all lanes.",
                "Reviewed and built 8-lane shutdown bitstream ready before the first TFDU-driven run.",
            ],
            safe_command=(
                "powershell -NoProfile -ExecutionPolicy Bypass -File .\\tools\\run_8lane_hardware_acceptance_safe.ps1 "
                "-Profile full_8lane_stream_bidir -LaneCount 8 -TargetHostA <ax7010_a_ip> -TargetHostB <ax7010_b_ip> "
                "-AllowTraffic -PinmapReviewed -ShutdownBitstreamReviewed -ProgramShutdownBeforeRun -ProgramShutdownAfterRun "
                "-DurationSeconds 600 -Repeat 32 -PayloadSize 256 -TimeoutSeconds 5.0 -ReconnectCycles 4 "
                "-TxLaneMaskA 0xff -RxLaneMaskA 0xff -TxLaneMaskB 0xff -RxLaneMaskB 0xff"
            ),
            pass_criteria=[
                "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=1",
                "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=0",
                "EIGHT_LANE_HARDWARE_SHUTDOWN_BEFORE_RUN_PASS=1",
                "EIGHT_LANE_HARDWARE_SHUTDOWN_AFTER_RUN_PASS=1",
                "All eight TX lane pins show expected activity when enabled one at a time and together.",
                "All eight RX lane pins receive valid payload/frames with no stuck lane.",
                "Lane coverage reports tx_lane_coverage=0xff and rx_lane_coverage=0xff.",
                "8-lane half-duplex raw PHY capacity and 4+4 full-duplex raw PHY capacity are measured or derived from the real enabled lane count.",
                "Autoroute/recovery statistics cover all lanes without deadlock.",
            ],
            evidence_patterns=[
                "reports/real_acceptance_template/eight_lane_summary_template.txt",
                "reports/real_acceptance_evidence_validation_current.*",
                "reports/8lane_hardware_acceptance_safe_*.summary.txt",
                "reports/8lane_hardware_acceptance_safe_*.md",
                "reports/8lane_hardware_acceptance_safe_*.criteria.csv",
                "reports/*8lane*hardware*acceptance*.summary.txt",
                "reports/*8lane*hardware*acceptance*.md",
                "reports/*8lane*pinmap*.csv",
            ],
            safety_guard=[
                "The dedicated wrapper blocks real traffic unless pinmap review, shutdown bitstream review, -AllowTraffic, -ProgramShutdownBeforeRun, and -ProgramShutdownAfterRun are all set.",
                "The wrapper blocks real 8-lane traffic until pinmap review, shutdown bitstream review, and explicit traffic/programming switches are all present; unreduced full profiles remain resource-blocked, while the reduced 8-lane fragment=16 profile is offline-only.",
                "Do not run 8 TFDU boards until pin mapping and shutdown flow are verified.",
                "Limit each physical continuous test to 600 s.",
                "Program shutdown bitstream after every TFDU-driven hardware run.",
            ],
            shutdown_requirement=shutdown_after_tfdu,
            implementation_gap=lane8_gap,
            notes=[
                "This is the only remaining lane-count item that needs both hardware wiring and project/tool support.",
                "A generated 8-lane candidate pinmap may be used as a review starting point, but it is not physical validation.",
                "A generated 8-lane shutdown candidate bitstream now exists as an offline build artifact, but it is not a programmed/proven shutdown flow for real 8-lane hardware.",
                "The current full 8-lane stream_bidir hardware candidate is resource-blocked on XC7Z010 after synthesis; smaller hardware profiles or a larger device must be evaluated before real 8-lane hardware validation.",
                "The 8-lane A-only external profile for the final two-AX7010 topology is also resource-blocked on XC7Z010 after synthesis; lane count, buffering, protocol state, or device size must be reduced before promoting 8-lane hardware.",
                "The A-only external lane-count scan currently reaches place_design only at 1 lane; 2 lanes and above are resource-blocked in the current BD/protocol profile.",
                f"The reduced A-only external 2-lane option is {external_option_overall or 'missing'} with fragment={external_option_meta.get('fragment_bytes')} and TX/RX FIFO={external_option_meta.get('tx_async_fifo_depth')}/{external_option_meta.get('rx_async_fifo_depth')}; this indicates a resource-reduction path, not final hardware acceptance.",
                f"The reduced A-only external 1..4-lane scan is {external_reduced_lane_overall or 'missing'} with max place-pass lane={external_reduced_lane_max_place_pass}, first blocked lane={external_reduced_lane_first_blocked}, fragment={external_reduced_lane_meta.get('fragment_bytes')}, and TX/RX FIFO={external_reduced_lane_meta.get('tx_async_fifo_depth')}/{external_reduced_lane_meta.get('rx_async_fifo_depth')}; this is offline place/resource evidence only.",
                f"The reduced A-only external 2-lane route/timing result is {external_route_overall or 'missing'} with WNS={external_route_timing.get('wns_ns')} ns, WHS={external_route_timing.get('whs_ns')} ns, and routing_errors={external_route_route.get('routing_errors')}; this is still offline evidence only.",
                f"The reduced A-only external 4-lane route/timing result is {external_route_4lane_overall or 'missing'} with WNS={external_route_4lane_timing.get('wns_ns')} ns, WHS={external_route_4lane_timing.get('whs_ns')} ns, and routing_errors={external_route_4lane_route.get('routing_errors')}; this is still offline evidence only.",
                f"The reduced A-only external 4-lane candidate bitstream result is {external_bitstream_4lane_overall or 'missing'} with size={external_bitstream_4lane_size} bytes and sha256={external_bitstream_4lane_sha}; this has not been programmed or accepted on TFDU hardware.",
                f"The reduced A-only external 5-lane fragment=32 route/timing result is {external_route_5lane_frag32_overall or 'missing'} with WNS={external_route_5lane_frag32_timing.get('wns_ns')} ns, WHS={external_route_5lane_frag32_timing.get('whs_ns')} ns, and routing_errors={external_route_5lane_frag32_route.get('routing_errors')}; this is the strongest reduced offline build path so far, but it remains lower-rate small-packet evidence.",
                f"The reduced A-only external 5-lane fragment=32 candidate bitstream result is {external_bitstream_5lane_frag32_overall or 'missing'} with size={external_bitstream_5lane_frag32_size} bytes and sha256={external_bitstream_5lane_frag32_sha}; this has not been programmed or accepted on TFDU hardware.",
                f"The reduced A-only external 8-lane fragment=16 candidate bitstream result is {external_bitstream_8lane_frag16_overall or 'missing'} with size={external_bitstream_8lane_frag16_size} bytes, sha256={external_bitstream_8lane_frag16_sha}, raw_half={external_bitstream_8lane_frag16_raw_half} Mbit/s, and raw_fdx_per_dir={external_bitstream_8lane_frag16_raw_fdx} Mbit/s; this is the strongest current raw-target offline profile, but it has not been programmed or accepted on TFDU hardware.",
                f"The reduced A-only external 4-lane bring-up/ILA plan is {external_bringup_4lane_overall or 'missing'}; it is a review checklist, not hardware acceptance.",
                f"The reduced A-only external 5..8-lane fragment=64 extension result is {external_5to8_overall or 'missing'}; lane 5 fails placement at LUT={external_5to8_lane5.get('total_luts')}/{external_5to8_lane5.get('available_luts')}, slices={external_5to8_lane5.get('slice_required')}/{external_5to8_lane5.get('slice_available')}, control_sets={external_5to8_lane5.get('control_sets')}; the fragment=32 5-lane result shows packet/cache sizing is the current reduction lever.",
                "A dedicated 8-lane hardware safe wrapper exists and dry-run evidence proves the 600 s cap/no-hardware gate, while previewing the current full 8-lane resource and no-Ethernet blockers.",
                "Use tools/validate_real_acceptance_evidence.py --mode eight_lane against the real summary and criteria CSV before claiming acceptance.",
            ],
        ),
    ]


def flatten(values: list[str]) -> str:
    return " | ".join(values)


def md_list(values: list[str]) -> list[str]:
    return [f"- {value}" for value in values]


def write_markdown(path: Path, items: list[RemainingAcceptanceItem], generated: str) -> None:
    lines: list[str] = [
        "# Remaining Hardware Acceptance Plan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        "- Overall: `WAITING_FOR_EXTERNAL_HARDWARE`",
        "- Current board Ethernet: `not connected`",
        "- Continuous physical run cap: `600 seconds`",
        "- This file does not change the project target; it only maps remaining target rows to future real-hardware acceptance steps.",
        "",
        "## Remaining Items",
        "",
        "| id | status | blocker | shutdown | implementation gap |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in items:
        lines.append(
            f"| {item.item_id} | {item.current_status} | {item.current_blocker} | {item.shutdown_requirement} | {item.implementation_gap} |"
        )

    for item in items:
        lines.extend(
            [
                "",
                f"## {item.item_id} - {item.requirement}",
                "",
                f"Current status: `{item.current_status}`",
                "",
                "Current blocker:",
                "",
                f"- {item.current_blocker}",
                "",
                "Preconditions:",
                "",
                *md_list(item.preconditions),
                "",
                "Required hardware:",
                "",
                *md_list(item.required_hardware),
                "",
                "Safe command or controlled path:",
                "",
                "```powershell",
                item.safe_command,
                "```",
                "",
                "Pass criteria:",
                "",
                *md_list(item.pass_criteria),
                "",
                "Evidence patterns:",
                "",
                *md_list(item.evidence_patterns),
                "",
                "Safety guard:",
                "",
                *md_list(item.safety_guard),
                "",
                f"Shutdown requirement: {item.shutdown_requirement}",
                "",
                f"Implementation gap: {item.implementation_gap}",
                "",
                "Notes:",
                "",
                *md_list(item.notes),
            ]
        )

    lines.extend(
        [
            "",
            "RF_COMM_REMAINING_HARDWARE_ACCEPTANCE_PLAN overall=WAITING_FOR_EXTERNAL_HARDWARE items=5",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, items: list[RemainingAcceptanceItem]) -> None:
    fieldnames = [
        "item_id",
        "current_status",
        "requirement",
        "current_blocker",
        "preconditions",
        "required_hardware",
        "safe_command",
        "pass_criteria",
        "evidence_patterns",
        "safety_guard",
        "shutdown_requirement",
        "implementation_gap",
        "notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = asdict(item)
            for key, value in list(row.items()):
                if isinstance(value, list):
                    row[key] = flatten(value)
            writer.writerow(row)


def validate(items: list[RemainingAcceptanceItem]) -> None:
    ids = [item.item_id for item in items]
    if ids != EXPECTED_OPEN_IDS:
        raise RuntimeError(f"Plan item order changed or incomplete: {ids}")
    for item in items:
        if not item.pass_criteria:
            raise RuntimeError(f"{item.item_id} has no pass criteria")
        if not item.safety_guard:
            raise RuntimeError(f"{item.item_id} has no safety guard")
        if "600" not in flatten(item.preconditions + item.safety_guard + item.notes) and item.item_id != "N03":
            raise RuntimeError(f"{item.item_id} does not mention the 600 s cap")
    if "Ethernet is not connected" not in items[0].current_blocker:
        raise RuntimeError("N03 does not preserve the current no-Ethernet blocker")
    if not (
        "1..4" in items[-1].implementation_gap
        or "active XDC" in items[-1].implementation_gap
        or "candidate XDC" in items[-1].implementation_gap
        or "real 8-lane hardware validation" in items[-1].implementation_gap
    ):
        raise RuntimeError("A02 does not capture the current 8-lane hardware implementation gap")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    constraint = find_hard_constraint()
    if constraint is None:
        raise RuntimeError("Hard constraint file was not found by expected hash")

    open_rows = load_open_rows()
    items = make_items(open_rows)
    validate(items)

    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "remaining_hardware_acceptance_plan_current.md"
    json_path = REPORTS / "remaining_hardware_acceptance_plan_current.json"
    csv_path = REPORTS / "remaining_hardware_acceptance_plan_current.csv"

    write_markdown(md_path, items, generated)
    write_csv(csv_path, items)
    payload = {
        "generated": generated,
        "overall": "WAITING_FOR_EXTERNAL_HARDWARE",
        "hard_constraint_sha256": sha256(constraint),
        "matrix_csv": str(MATRIX_CSV.relative_to(ROOT)),
        "current_board_ethernet": "not_connected",
        "continuous_physical_run_cap_seconds": 600,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "items": [asdict(item) for item in items],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print("RF_COMM_REMAINING_HARDWARE_ACCEPTANCE_PLAN overall=WAITING_FOR_EXTERNAL_HARDWARE items=5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
