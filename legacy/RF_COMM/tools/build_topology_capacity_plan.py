from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
RAW_PER_LANE_MBPS = 4.0
TARGET_HALF_RAW_MBPS = 32.0
TARGET_FDX_PER_DIR_RAW_MBPS = 16.0


@dataclass
class CapacityRow:
    profile_id: str
    scope: str
    evidence: str
    lanes_available: int
    half_duplex_lanes: int
    fdx_lanes_per_direction: int
    half_duplex_raw_mbps: float
    fdx_raw_per_direction_mbps: float
    meets_32_16_raw_capacity: str
    implementation_status: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def raw_capacity(half_lanes: int, fdx_lanes: int) -> tuple[float, float, str]:
    half = half_lanes * RAW_PER_LANE_MBPS
    fdx = fdx_lanes * RAW_PER_LANE_MBPS
    meets = half >= TARGET_HALF_RAW_MBPS and fdx >= TARGET_FDX_PER_DIR_RAW_MBPS
    return half, fdx, "YES" if meets else "NO"


def build_rows(
    readiness: dict[str, Any],
    route4: dict[str, Any],
    bit4: dict[str, Any],
    boundary5: dict[str, Any],
    frag32_5lane: dict[str, Any],
    route5_frag32: dict[str, Any],
    bit5_frag32: dict[str, Any],
    bit8_frag16: dict[str, Any],
) -> list[CapacityRow]:
    rows: list[CapacityRow] = []

    half, fdx, meets = raw_capacity(2, 1)
    rows.append(
        CapacityRow(
            "active_2lane_stream_bidir",
            "current restored Vivado project",
            "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.xpr",
            2,
            2,
            1,
            half,
            fdx,
            meets,
            "ACTIVE_G1_SCOPE_ONLY",
            "Active project is intentionally restored to the proven 2-lane stream_bidir scope; it is not a final-rate profile.",
        )
    )

    half, fdx, meets = raw_capacity(8, 4)
    rows.append(
        CapacityRow(
            "full_8lane_stream_bidir_candidate",
            "single AX7010 board-internal A/B candidate",
            readiness.get("candidate_project_build_json", ""),
            8,
            8,
            4,
            half,
            fdx,
            meets,
            "RESOURCE_BLOCKED_ON_XC7Z010",
            (
                "Meets raw 32/16 lane arithmetic, but implementation is blocked: "
                f"Slice LUTs {readiness.get('candidate_project_required_luts')}/"
                f"{readiness.get('candidate_project_available_luts')}."
            ),
        )
    )

    half, fdx, meets = raw_capacity(8, 4)
    rows.append(
        CapacityRow(
            "a_only_external_8lane_candidate",
            "one AX7010 endpoint for final two-system topology",
            readiness.get("external_project_build_json", ""),
            8,
            8,
            4,
            half,
            fdx,
            meets,
            "RESOURCE_BLOCKED_ON_XC7Z010",
            "Meets raw 32/16 lane arithmetic, but A-only external 8-lane build is resource-blocked: "
            + str(readiness.get("external_project_resource_summary", "resource summary missing")),
        )
    )

    half, fdx, meets = raw_capacity(4, 2)
    bit_sha = bit4.get("bitstream_sha256", "MISSING")
    wns = route4.get("timing", {}).get("wns_ns", "MISSING")
    lut_row = next((r for r in route4.get("utilization", []) if r.get("resource") == "Slice LUTs"), {})
    lane5 = boundary5.get("lane_results", [{}])[0] if boundary5.get("lane_results") else {}
    lane5_boundary = (
        " 5-lane reduced extension fails placement: "
        f"LUT={lane5.get('total_luts', 'MISSING')}/{lane5.get('available_luts', 'MISSING')}, "
        f"slices={lane5.get('slice_required', 'MISSING')}/{lane5.get('slice_available', 'MISSING')}, "
        f"control_sets={lane5.get('control_sets', 'MISSING')}; "
        "therefore 4 lanes is the current reduced XC7Z010 endpoint boundary."
        if boundary5.get("overall") == "FIRST_BLOCKED_AT_5LANE_REDUCED_PROFILE"
        else " No 5-lane reduced extension boundary report is available."
    )
    rows.append(
        CapacityRow(
            "reduced_4lane_external_candidate",
            "best current reduced-resource AX7010 endpoint",
            bit4.get("bitstream", ""),
            4,
            4,
            2,
            half,
            fdx,
            meets,
            "ROUTE_TIMING_BITSTREAM_READY_REVIEW_REQUIRED",
            (
                "Routes and meets timing offline, but is a lower-rate bring-up profile: "
                f"WNS={wns} ns, LUT={lut_row.get('used', 'MISSING')}/{lut_row.get('available', 'MISSING')}, "
                f"bitstream_sha256={bit_sha}.{lane5_boundary}"
            ),
        )
    )

    half, fdx, meets = raw_capacity(5, 2)
    frag32_resources = frag32_5lane.get("resources", {})
    frag32_compare = frag32_5lane.get("comparison_to_fragment64_lane5", {})
    rows.append(
        CapacityRow(
            "reduced_5lane_frag32_place_probe",
            "offline reduced-resource AX7010 endpoint probe",
            frag32_5lane.get("utilization_placed", ""),
            5,
            5,
            2,
            half,
            fdx,
            meets,
            "PLACE_PASS_ONLY_SMALL_PACKET_PROFILE"
            if frag32_5lane.get("overall") == "PLACE_PASS_5LANE_FRAG32_REDUCED_PROFILE"
            else "MISSING",
            (
                "A smaller-packet 5-lane profile reaches place_design offline, indicating the earlier 5-lane "
                "fragment=64 failure is mainly a frame/cache resource-pressure boundary rather than lane count alone: "
                f"LUT={frag32_resources.get('slice_luts', 'MISSING')}/"
                f"{frag32_resources.get('slice_luts_available', 'MISSING')}, "
                f"control_sets={frag32_resources.get('control_sets', 'MISSING')}, "
                f"LUT_delta_vs_fragment64={frag32_compare.get('lut_delta_vs_fragment64', 'MISSING')}. "
                "It is not route/timing/bitstream/hardware acceptance and does not meet the final 32/16 raw target."
            ),
        )
    )

    half, fdx, meets = raw_capacity(5, 2)
    route5_timing = route5_frag32.get("timing", {})
    route5_route = route5_frag32.get("route", {})
    route5_lut = next((r for r in route5_frag32.get("utilization", []) if r.get("resource") == "Slice LUTs"), {})
    rows.append(
        CapacityRow(
            "reduced_5lane_frag32_route_candidate",
            "offline reduced-resource AX7010 endpoint route/timing candidate",
            route5_frag32.get("timing_report", ""),
            5,
            5,
            2,
            half,
            fdx,
            meets,
            "ROUTE_TIMING_PASS_SMALL_PACKET_PROFILE"
            if route5_frag32.get("overall") == "ROUTE_TIMING_PASS_REDUCED_5LANE_FRAG32"
            else "MISSING",
            (
                "The 5-lane fragment=32 profile now routes and meets timing offline: "
                f"WNS={route5_timing.get('wns_ns', 'MISSING')} ns, "
                f"WHS={route5_timing.get('whs_ns', 'MISSING')} ns, "
                f"route_errors={route5_route.get('routing_errors', 'MISSING')}, "
                f"LUT={route5_lut.get('used', 'MISSING')}/{route5_lut.get('available', 'MISSING')}. "
                "It is still a lower-rate small-packet profile, not bitstream-ready yet, and does not meet the final 32/16 raw target."
            ),
        )
    )

    half, fdx, meets = raw_capacity(5, 2)
    bit5_timing = bit5_frag32.get("timing", {})
    bit5_route = bit5_frag32.get("route", {})
    bit5_lut = next((r for r in bit5_frag32.get("utilization", []) if r.get("resource") == "Slice LUTs"), {})
    rows.append(
        CapacityRow(
            "reduced_5lane_frag32_bitstream_candidate",
            "previous reduced-resource AX7010 endpoint",
            bit5_frag32.get("bitstream", ""),
            5,
            5,
            2,
            half,
            fdx,
            meets,
            "ROUTE_TIMING_BITSTREAM_READY_REVIEW_REQUIRED"
            if bit5_frag32.get("overall") == "PASS_OFFLINE_5LANE_FRAG32_BITSTREAM_READY_REVIEW_REQUIRED"
            else "MISSING",
            (
                "The 5-lane fragment=32 profile now has an offline candidate bitstream: "
                f"WNS={bit5_timing.get('wns_ns', 'MISSING')} ns, "
                f"WHS={bit5_timing.get('whs_ns', 'MISSING')} ns, "
                f"route_errors={bit5_route.get('routing_errors', 'MISSING')}, "
                f"LUT={bit5_lut.get('used', 'MISSING')}/{bit5_lut.get('available', 'MISSING')}, "
                f"bitstream_sha256={bit5_frag32.get('bitstream_sha256', 'MISSING')}. "
                "It is still a lower-rate small-packet profile and does not meet the final 32/16 raw target."
            ),
        )
    )

    half, fdx, meets = raw_capacity(8, 4)
    bit8_timing = bit8_frag16.get("timing", {})
    bit8_route = bit8_frag16.get("route", {})
    bit8_lut = next((r for r in bit8_frag16.get("utilization", []) if r.get("resource") == "Slice LUTs"), {})
    rows.append(
        CapacityRow(
            "reduced_8lane_frag16_bitstream_candidate",
            "best current reduced-resource AX7010 endpoint for final raw lane count",
            bit8_frag16.get("bitstream", ""),
            8,
            8,
            4,
            half,
            fdx,
            meets,
            "ROUTE_TIMING_BITSTREAM_READY_REVIEW_REQUIRED"
            if bit8_frag16.get("overall") == "PASS_OFFLINE_8LANE_FRAG16_BITSTREAM_READY_REVIEW_REQUIRED"
            else "MISSING",
            (
                "The 8-lane fragment=16 profile has an offline candidate bitstream and meets the final raw lane arithmetic: "
                f"WNS={bit8_timing.get('wns_ns', 'MISSING')} ns, "
                f"WHS={bit8_timing.get('whs_ns', 'MISSING')} ns, "
                f"route_errors={bit8_route.get('routing_errors', 'MISSING')}, "
                f"LUT={bit8_lut.get('used', 'MISSING')}/{bit8_lut.get('available', 'MISSING')}, "
                f"bitstream_sha256={bit8_frag16.get('bitstream_sha256', 'MISSING')}. "
                "It remains a small-packet offline candidate and still needs manual pin review, real TFDU hardware, two-AX7010, TCP/DHCP, and rotating-shaft acceptance."
            ),
        )
    )

    half, fdx, meets = raw_capacity(8, 4)
    rows.append(
        CapacityRow(
            "rtl_8lane_simulation_model",
            "simulation/model only",
            "reports/post_g1_target_sim_gate_20260627_002848.summary.txt",
            8,
            8,
            4,
            half,
            fdx,
            meets,
            "SIMULATION_ONLY",
            "Digital model proves 8-lane raw-capacity behavior, autoroute, and 4+4 full-duplex partition, but it is not a fitted XC7Z010 hardware profile.",
        )
    )
    return rows


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    constraint = find_constraint()
    readiness_path = REPORTS / "8lane_hardware_readiness_current.json"
    route4_path = REPORTS / "external_reduced_4lane_route_current.json"
    bit4_path = REPORTS / "external_reduced_4lane_bitstream_current.json"
    boundary5_path = REPORTS / "external_reduced_5to8_extension_current.json"
    frag32_5lane_path = REPORTS / "external_reduced_5lane_frag32_current.json"
    route5_frag32_path = REPORTS / "external_reduced_5lane_frag32_route_current.json"
    bit5_frag32_path = REPORTS / "external_reduced_5lane_frag32_bitstream_current.json"
    bit8_frag16_path = REPORTS / "external_reduced_8lane_frag16_bitstream_current.json"

    readiness = read_json(readiness_path)
    route4 = read_json(route4_path)
    bit4 = read_json(bit4_path)
    boundary5 = read_json(boundary5_path)
    frag32_5lane = read_json(frag32_5lane_path)
    route5_frag32 = read_json(route5_frag32_path)
    bit5_frag32 = read_json(bit5_frag32_path)
    bit8_frag16 = read_json(bit8_frag16_path)
    rows = build_rows(readiness, route4, bit4, boundary5, frag32_5lane, route5_frag32, bit5_frag32, bit8_frag16)

    best_buildable = "reduced_8lane_frag16_bitstream_candidate"
    final_ready = any(
        row.meets_32_16_raw_capacity == "YES" and row.implementation_status.startswith("ROUTE_TIMING_BITSTREAM")
        for row in rows
    )
    overall = "FINAL_RAW_TARGET_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" if final_ready else "NO_FINAL_RATE_HARDWARE_PROFILE_READY"
    generated = datetime.now().isoformat(timespec="seconds")

    md_path = REPORTS / "topology_capacity_plan_current.md"
    json_path = REPORTS / "topology_capacity_plan_current.json"
    csv_path = REPORTS / "topology_capacity_plan_current.csv"

    csv_fields = list(asdict(rows[0]).keys())
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md_rows = [
        [
            row.profile_id,
            row.scope,
            str(row.lanes_available),
            f"{row.half_duplex_raw_mbps:.3f}",
            f"{row.fdx_raw_per_direction_mbps:.3f}",
            row.meets_32_16_raw_capacity,
            row.implementation_status,
            row.evidence,
            row.note,
        ]
        for row in rows
    ]
    md = [
        "# RF_COMM Topology Capacity Plan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Best current buildable endpoint profile: `{best_buildable}`",
        f"- Raw PHY per lane: `{RAW_PER_LANE_MBPS:.3f} Mbit/s`",
        f"- Final half-duplex raw target: `{TARGET_HALF_RAW_MBPS:.3f} Mbit/s`",
        f"- Final full-duplex raw target per direction: `{TARGET_FDX_PER_DIR_RAW_MBPS:.3f} Mbit/s`",
        f"- Hard constraint unchanged: `{sha256(constraint)}`",
        "",
        "This report is conservative: full-duplex capacity is counted as dedicated directional lanes. It does not claim effective payload throughput, TCP throughput, or real hardware acceptance.",
        "",
        "This generator is offline/read-only. It does not invoke Vivado, program FPGA hardware, write UART, send TX data, or drive TFDU boards.",
        "",
        "## Capacity Matrix",
        "",
        md_table(
            [
                "profile",
                "scope",
                "lanes",
                "half raw Mbit/s",
                "fdx per-dir raw Mbit/s",
                "meets 32/16 raw",
                "implementation status",
                "evidence",
                "note",
            ],
            md_rows,
        ),
        "",
        "## Engineering Consequence",
        "",
        "- The current RTL/model can represent the final 8-lane raw-capacity target.",
        "- The full 8-lane hardware profiles meet the raw lane arithmetic but are resource-blocked on XC7Z010.",
        "- The reduced 8-lane fragment=16 profile is now the strongest current offline hardware-build candidate and reaches the final raw lane arithmetic.",
        "- The reduced 5-lane fragment=64 extension fails placement, while 5-lane fragment=32 and 8-lane fragment=16 both build offline; frame/cache sizing is therefore a concrete resource lever.",
        "- The 5-lane fragment=32 profile now reaches route_design, meets timing, and produces a candidate bitstream; it remains below the final 32/16 Mbit/s raw target but proves the packet/cache sizing lever.",
        "- The 8-lane fragment=16 candidate meets the 32/16 Mbit/s raw PHY target, but it is still not effective-payload, TCP/DHCP, two-AX7010, TFDU hardware, or rotating-shaft acceptance.",
        "- Reaching product acceptance still requires manual pin review, real hardware wiring, shutdown-flow review, network acceptance after Ethernet exists, and rotating-shaft validation.",
        "",
        f"RF_COMM_TOPOLOGY_CAPACITY_PLAN overall={overall} best_buildable_profile={best_buildable} target_raw_half_mbps={TARGET_HALF_RAW_MBPS:.3f} target_raw_fdx_per_dir_mbps={TARGET_FDX_PER_DIR_RAW_MBPS:.3f}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "best_buildable_profile": best_buildable,
        "raw_per_lane_mbps": RAW_PER_LANE_MBPS,
        "target_half_raw_mbps": TARGET_HALF_RAW_MBPS,
        "target_fdx_per_dir_raw_mbps": TARGET_FDX_PER_DIR_RAW_MBPS,
        "hard_constraint_sha256": sha256(constraint),
        "inputs": {
            "constraint": rel(constraint),
            "readiness": rel(readiness_path),
            "route4": rel(route4_path),
            "bitstream4": rel(bit4_path),
            "boundary5": rel(boundary5_path),
            "frag32_5lane": rel(frag32_5lane_path),
            "route5_frag32": rel(route5_frag32_path),
            "bit5_frag32": rel(bit5_frag32_path),
        },
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_TOPOLOGY_CAPACITY_PLAN "
        f"overall={overall} best_buildable_profile={best_buildable} "
        f"target_raw_half_mbps={TARGET_HALF_RAW_MBPS:.3f} "
        f"target_raw_fdx_per_dir_mbps={TARGET_FDX_PER_DIR_RAW_MBPS:.3f}"
    )
    return 0 if sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else 1


if __name__ == "__main__":
    raise SystemExit(main())
