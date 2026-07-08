from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


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
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def parse_meta(path: Path | None) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        meta[key.strip()] = value.strip()
    return meta


def meta_path(meta: dict[str, str], key: str) -> Path | None:
    value = meta.get(key, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def latest_frag32_meta() -> Path | None:
    matches: list[Path] = []
    for path in REPORTS.glob("external_reduced_lane_resource_scan_*.meta.txt"):
        meta = parse_meta(path)
        if (
            meta.get("scan_lanes") == "5"
            and meta.get("fragment_bytes") == "32"
            and meta.get("max_packet_bytes") == "128"
            and meta.get("tx_async_fifo_depth") == "128"
            and meta.get("rx_async_fifo_depth") == "128"
            and meta.get("stream_phy_dbg_select") == "6"
        ):
            matches.append(path)
    return max(matches, key=lambda p: p.stat().st_mtime) if matches else None


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return int(match.group(1)) if match else None


def extract_float(pattern: str, text: str) -> float | None:
    match = re.search(pattern, text, flags=re.MULTILINE)
    return float(match.group(1)) if match else None


def row_int(name: str, text: str) -> tuple[int | None, int | None, float | None]:
    pattern = rf"^\|\s*{re.escape(name)}\s*\|\s*([0-9.]+)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None, None, None
    used_raw, avail_raw, pct_raw = match.groups()
    return int(float(used_raw)), int(float(avail_raw)), float(pct_raw)


def row_float(name: str, text: str) -> tuple[float | None, float | None, float | None]:
    pattern = rf"^\|\s*{re.escape(name)}\s*\|\s*([0-9.]+)\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|"
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        return None, None, None
    used_raw, avail_raw, pct_raw = match.groups()
    return float(used_raw), float(avail_raw), float(pct_raw)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    meta_file = latest_frag32_meta()
    if meta_file is None:
        raise FileNotFoundError("No 5-lane fragment=32 reduced scan meta file found")

    meta = parse_meta(meta_file)
    scan_dir = meta_path(meta, "out_dir")
    vivado_log = meta_path(meta, "vivado_log")
    stdout_log = meta_path(meta, "stdout")
    stderr_log = meta_path(meta, "stderr")
    lane_dir = scan_dir / "lane_05" if scan_dir else None
    impl_log = lane_dir / "impl_1_runme.log" if lane_dir else None
    synth_log = lane_dir / "synth_1_runme.log" if lane_dir else None
    util_rpt = lane_dir / "utilization_placed.rpt" if lane_dir else None
    control_rpt = lane_dir / "control_sets_placed.rpt" if lane_dir else None
    io_rpt = lane_dir / "io_placed.rpt" if lane_dir else None

    vivado_text = read_text(vivado_log)
    impl_text = read_text(impl_log)
    util_text = read_text(util_rpt)
    control_text = read_text(control_rpt)
    wrapper = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "sources_1" / "imports" / "hdl" / "design_shiboqi_wrapper.v"
    xpr = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.xpr"
    wrapper_text = read_text(wrapper)
    xpr_text = read_text(xpr)

    slice_luts, slice_luts_avail, slice_luts_pct = row_int("Slice LUTs", util_text)
    lut_logic, lut_logic_avail, lut_logic_pct = row_int("LUT as Logic", util_text)
    lut_memory, lut_memory_avail, lut_memory_pct = row_int("LUT as Memory", util_text)
    slice_regs, slice_regs_avail, slice_regs_pct = row_int("Slice Registers", util_text)
    bram_tiles, bram_tiles_avail, bram_tiles_pct = row_float("Block RAM Tile", util_text)
    bonded_iob, bonded_iob_avail, bonded_iob_pct = row_int("Bonded IOB", util_text)
    dsp, dsp_avail, dsp_pct = row_int("DSPs", util_text)
    control_sets = extract_int(r"\|\s*Total control sets\s*\|\s*(\d+)\s*\|", control_text)

    synth_status_match = re.search(r"EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS lane=5 status=(.+)", vivado_text)
    impl_status_match = re.search(r"EXTERNAL_RESOURCE_SCAN_IMPL_STATUS lane=5 status=(.+)", vivado_text)
    synth_status = synth_status_match.group(1).strip() if synth_status_match else ""
    impl_status = impl_status_match.group(1).strip() if impl_status_match else ""
    place_pass = "place_design completed successfully" in impl_text
    restored = (
        "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_DONE" in vivado_text
        and "EXTERNAL_RESOURCE_SCAN_DONE lanes=5" in vivado_text
        and "PORT1.xdc" in xpr_text
        and "target_ir_array_external_5lane_scan.xdc" not in xpr_text
        and "target_ir_array_8lane" not in xpr_text
        and "output [1:0]ir_tx_out_0" in wrapper_text
        and "input [1:0]loop_rx_b0" in wrapper_text
    )
    no_hw = (
        meta.get("no_hardware_programming") == "1"
        and meta.get("no_uart_write") == "1"
        and meta.get("no_tfdu_drive") == "1"
    )
    no_ethernet = meta.get("ethernet_real_test_deferred") == "1"

    boundary64 = read_json(REPORTS / "external_reduced_5to8_extension_current.json")
    boundary64_lane5 = next(
        (item for item in boundary64.get("lane_results", []) if item.get("lane_count") == 5),
        {},
    )
    boundary64_luts = boundary64_lane5.get("total_luts")
    boundary64_control_sets = boundary64_lane5.get("control_sets")
    lut_delta_vs_64 = slice_luts - boundary64_luts if isinstance(boundary64_luts, int) and slice_luts is not None else None
    control_delta_vs_64 = (
        control_sets - boundary64_control_sets
        if isinstance(boundary64_control_sets, int) and control_sets is not None
        else None
    )

    overall = (
        "PLACE_PASS_5LANE_FRAG32_REDUCED_PROFILE"
        if place_pass and restored and no_hw and no_ethernet and slice_luts is not None and slice_luts < 17600
        else "INCOMPLETE_REVIEW_REQUIRED"
    )

    csv_path = REPORTS / "external_reduced_5lane_frag32_current.csv"
    json_path = REPORTS / "external_reduced_5lane_frag32_current.json"
    md_path = REPORTS / "external_reduced_5lane_frag32_current.md"
    rows = [
        ["SYNTH", "PASS" if "Complete" in synth_status else "MISSING", synth_status, rel(synth_log)],
        ["PLACE", "PASS" if place_pass else "MISSING", impl_status, rel(impl_log)],
        ["LUTS", "PASS" if slice_luts is not None and slice_luts < 17600 else "MISSING", f"{slice_luts}/{slice_luts_avail}", rel(util_rpt)],
        ["REGISTERS", "PASS" if slice_regs is not None else "MISSING", f"{slice_regs}/{slice_regs_avail}", rel(util_rpt)],
        ["CONTROL-SETS", "INFO" if control_sets is not None else "MISSING", str(control_sets), rel(control_rpt)],
        ["RESTORE-2LANE", "PASS" if restored else "MISSING", "active project restored to PORT1.xdc and 2lane wrapper", rel(vivado_log)],
        ["NO-HARDWARE-ACTION", "PASS" if no_hw else "MISSING", "no FPGA programming, no UART write, no TFDU drive", rel(meta_file)],
        ["NO-ETHERNET-BOUNDARY", "DEFERRED" if no_ethernet else "MISSING", "real TCP/DHCP remains deferred without Ethernet cable", rel(meta_file)],
    ]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item", "status", "value", "evidence"])
        writer.writerows(rows)

    md = [
        "# External Reduced 5-Lane Fragment-32 Scan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- Profile: `5lane / fragment_bytes=32 / max_packet_bytes=128 / tx_fifo=128 / rx_fifo=128 / stream_phy_dbg_select=6`",
        f"- Synthesis status: `{synth_status}`",
        f"- Implementation status marker: `{impl_status}`",
        f"- Place result: `{'PASS' if place_pass else 'MISSING'}`",
        f"- Placed LUTs: `{slice_luts}/{slice_luts_avail}` ({slice_luts_pct}%)",
        f"- LUT as logic: `{lut_logic}/{lut_logic_avail}` ({lut_logic_pct}%)",
        f"- LUT as memory: `{lut_memory}/{lut_memory_avail}` ({lut_memory_pct}%)",
        f"- Slice registers: `{slice_regs}/{slice_regs_avail}` ({slice_regs_pct}%)",
        f"- BRAM tiles: `{bram_tiles}/{bram_tiles_avail}` ({bram_tiles_pct}%)",
        f"- DSPs: `{dsp}/{dsp_avail}` ({dsp_pct}%)",
        f"- Bonded IOB: `{bonded_iob}/{bonded_iob_avail}` ({bonded_iob_pct}%)",
        f"- Control sets: `{control_sets}`",
        f"- LUT delta versus 5lane fragment=64 failure: `{lut_delta_vs_64}`",
        f"- Control-set delta versus 5lane fragment=64 failure: `{control_delta_vs_64}`",
        f"- Project restored to active 2-lane stream_bidir / PORT1.xdc: `{int(restored)}`",
        "- This is offline Vivado place evidence only. It is not route, timing, bitstream, TCP/DHCP, two-AX7010, rotating-shaft, or TFDU hardware acceptance.",
        "- The development board currently has no Ethernet cable, so real PS-to-PC TCP/DHCP acceptance remains deferred.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "",
        "## Evidence Table",
        "",
        "| Item | Status | Value | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for item, status, value, evidence in rows:
        md.append(f"| `{item}` | `{status}` | {value.replace('|', '/')} | `{evidence}` |")
    md.extend(
        [
            "",
            "## Files",
            "",
            f"- Meta: `{rel(meta_file)}`",
            f"- Vivado log: `{rel(vivado_log)}`",
            f"- Stdout: `{rel(stdout_log)}`",
            f"- Stderr: `{rel(stderr_log)}`",
            f"- Impl log: `{rel(impl_log)}`",
            f"- Placed utilization: `{rel(util_rpt)}`",
            f"- Placed control sets: `{rel(control_rpt)}`",
            f"- Placed IO: `{rel(io_rpt)}`",
            "",
            (
                "RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32 "
                f"overall={overall} lane=5 fragment_bytes=32 max_packet_bytes=128 "
                f"luts={slice_luts}/{slice_luts_avail} regs={slice_regs}/{slice_regs_avail} "
                f"bram_tiles={bram_tiles}/{bram_tiles_avail} control_sets={control_sets} "
                f"restored_2lane={int(restored)} no_ethernet={int(no_ethernet)}"
            ),
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "meta": meta,
        "meta_file": rel(meta_file),
        "vivado_log": rel(vivado_log),
        "stdout": rel(stdout_log),
        "stderr": rel(stderr_log),
        "impl_log": rel(impl_log),
        "synth_log": rel(synth_log),
        "utilization_placed": rel(util_rpt),
        "control_sets_placed": rel(control_rpt),
        "io_placed": rel(io_rpt),
        "synth_status": synth_status,
        "impl_status": impl_status,
        "place_design_pass": place_pass,
        "restored_2lane_stream_bidir": restored,
        "no_hardware_programming": meta.get("no_hardware_programming") == "1",
        "no_uart_write": meta.get("no_uart_write") == "1",
        "no_tfdu_drive": meta.get("no_tfdu_drive") == "1",
        "current_board_ethernet": "not_connected",
        "real_tcp_dhcp_deferred": no_ethernet,
        "resources": {
            "slice_luts": slice_luts,
            "slice_luts_available": slice_luts_avail,
            "slice_luts_percent": slice_luts_pct,
            "lut_as_logic": lut_logic,
            "lut_as_logic_available": lut_logic_avail,
            "lut_as_logic_percent": lut_logic_pct,
            "lut_as_memory": lut_memory,
            "lut_as_memory_available": lut_memory_avail,
            "lut_as_memory_percent": lut_memory_pct,
            "slice_registers": slice_regs,
            "slice_registers_available": slice_regs_avail,
            "slice_registers_percent": slice_regs_pct,
            "bram_tiles": bram_tiles,
            "bram_tiles_available": bram_tiles_avail,
            "bram_tiles_percent": bram_tiles_pct,
            "dsp": dsp,
            "dsp_available": dsp_avail,
            "dsp_percent": dsp_pct,
            "bonded_iob": bonded_iob,
            "bonded_iob_available": bonded_iob_avail,
            "bonded_iob_percent": bonded_iob_pct,
            "control_sets": control_sets,
        },
        "comparison_to_fragment64_lane5": {
            "fragment64_total_luts": boundary64_luts,
            "fragment64_control_sets": boundary64_control_sets,
            "lut_delta_vs_fragment64": lut_delta_vs_64,
            "control_set_delta_vs_fragment64": control_delta_vs_64,
        },
        "rows": [
            {"item": item, "status": status, "value": value, "evidence": evidence}
            for item, status, value, evidence in rows
        ],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_EXTERNAL_REDUCED_5LANE_FRAG32 "
        f"overall={overall} lane=5 fragment_bytes=32 max_packet_bytes=128 "
        f"luts={slice_luts}/{slice_luts_avail} regs={slice_regs}/{slice_regs_avail} "
        f"bram_tiles={bram_tiles}/{bram_tiles_avail} control_sets={control_sets} "
        f"restored_2lane={int(restored)} no_ethernet={int(no_ethernet)}"
    )
    return 0 if overall == "PLACE_PASS_5LANE_FRAG32_REDUCED_PROFILE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
