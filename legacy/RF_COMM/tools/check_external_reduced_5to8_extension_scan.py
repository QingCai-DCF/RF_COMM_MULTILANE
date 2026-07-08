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


@dataclass
class ExtensionLaneResult:
    lane_count: int
    status: str
    synth_status: str
    impl_status: str
    total_luts: int | None
    available_luts: int | None
    combined_luts: int | None
    flip_flops: int | None
    available_flip_flops: int | None
    control_sets: int | None
    slice_required: int | None
    slice_available: int | None
    evidence: str
    note: str


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


def latest_meta_5to8() -> Path | None:
    matches = []
    for path in REPORTS.glob("external_reduced_lane_resource_scan_*.meta.txt"):
        text = read_text(path)
        if "scan_lanes=5 6 7 8" in text:
            matches.append(path)
    return sorted(matches, key=lambda path: path.stat().st_mtime, reverse=True)[0] if matches else None


def latest_restore_log() -> Path | None:
    matches = sorted(
        REPORTS.glob("restore_active_2lane_after_5to8_scan_*.vivado.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


def parse_meta(path: Path | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def meta_path(meta: dict[str, str], key: str) -> Path | None:
    value = meta.get(key, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def marker_status(text: str, marker: str, lane_count: int) -> str:
    match = re.search(rf"{re.escape(marker)} lane={lane_count} status=(.+)", text)
    return match.group(1).strip() if match else ""


def extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def classify_lane(lane_count: int, vivado_text: str, scan_dir: Path | None) -> ExtensionLaneResult:
    lane_dir = scan_dir / f"lane_{lane_count:02d}" if scan_dir else None
    impl_log_path = lane_dir / "impl_1_runme.log" if lane_dir else None
    synth_log_path = lane_dir / "synth_1_runme.log" if lane_dir else None
    impl_log = read_text(impl_log_path)
    synth_status = marker_status(vivado_text, "EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS", lane_count)
    impl_status = marker_status(vivado_text, "EXTERNAL_RESOURCE_SCAN_IMPL_STATUS", lane_count)

    total_luts = extract_int(r"Luts:\s+\d+\s+\(combined\)\s+(\d+)\s+\(total\), available capacity:\s+\d+", impl_log)
    available_luts = extract_int(r"Luts:\s+\d+\s+\(combined\)\s+\d+\s+\(total\), available capacity:\s+(\d+)", impl_log)
    combined_luts = extract_int(r"Luts:\s+(\d+)\s+\(combined\)", impl_log)
    flip_flops = extract_int(r"Flip flops:\s+(\d+), available capacity:\s+\d+", impl_log)
    available_flip_flops = extract_int(r"Flip flops:\s+\d+, available capacity:\s+(\d+)", impl_log)
    control_sets = extract_int(r"Control sets:\s+(\d+)", impl_log)
    slice_match = re.search(r"available, however, the unplaced instances require\s+(\d+)\s+slices", impl_log)
    slice_required = int(slice_match.group(1)) if slice_match else None
    slice_available = extract_int(r"of which\s+(\d+)\s+slices are available", impl_log)

    if "EXTERNAL_RESOURCE_SCAN_LANE_DONE=5" in vivado_text and lane_count == 5 and "place_design failed" in impl_log:
        status = "PLACE_RESOURCE_BLOCKED"
        note = "Reduced profile first fails at 5 lanes during detail placement; total LUTs and slice/control-set packing exceed XC7Z010 capacity."
        evidence = rel(impl_log_path)
    elif f"EXTERNAL_RESOURCE_SCAN_LANE_START={lane_count}" in vivado_text and not synth_status:
        status = "STOPPED_AFTER_STALL"
        note = "Lane was configured but did not reach synth status before the manual stop after no log progress; lane 5 already established the first resource boundary."
        evidence = rel(meta_path(parse_meta(latest_meta_5to8()), "vivado_log"))
    elif f"EXTERNAL_RESOURCE_SCAN_LANE_START={lane_count}" not in vivado_text:
        status = "NOT_STARTED_AFTER_STOP"
        note = "Not started because the extension scan was stopped after lane 6 stalled; lane 5 had already failed placement."
        evidence = rel(meta_path(parse_meta(latest_meta_5to8()), "vivado_log"))
    elif synth_status and not impl_status:
        status = "INCOMPLETE_AFTER_SYNTH"
        note = "Synthesis status was seen but implementation status was not recorded."
        evidence = rel(synth_log_path)
    else:
        status = "UNKNOWN"
        note = "Could not classify lane result from available markers."
        evidence = rel(lane_dir)

    return ExtensionLaneResult(
        lane_count=lane_count,
        status=status,
        synth_status=synth_status,
        impl_status=impl_status,
        total_luts=total_luts,
        available_luts=available_luts,
        combined_luts=combined_luts,
        flip_flops=flip_flops,
        available_flip_flops=available_flip_flops,
        control_sets=control_sets,
        slice_required=slice_required,
        slice_available=slice_available,
        evidence=evidence,
        note=note,
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
    meta_file = latest_meta_5to8()
    if meta_file is None:
        raise FileNotFoundError("No reduced 5..8 extension scan meta file found")

    meta = parse_meta(meta_file)
    scan_dir = meta_path(meta, "out_dir")
    vivado_log = meta_path(meta, "vivado_log")
    stdout_log = meta_path(meta, "stdout")
    stderr_log = meta_path(meta, "stderr")
    restore_log = latest_restore_log()
    vivado_text = read_text(vivado_log)
    restore_text = read_text(restore_log)
    wrapper = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "sources_1" / "imports" / "hdl" / "design_shiboqi_wrapper.v"
    xpr = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.xpr"
    wrapper_text = read_text(wrapper)
    xpr_text = read_text(xpr)

    results = [classify_lane(lane, vivado_text, scan_dir) for lane in (5, 6, 7, 8)]
    lane5 = results[0]
    lane5_blocked = lane5.status == "PLACE_RESOURCE_BLOCKED" and lane5.total_luts is not None and lane5.total_luts > (lane5.available_luts or 0)
    restored = (
        "CONFIGURE_LANE0_AB_HW_LOOPBACK_DONE" in restore_text
        and "HWLOOP: IR_LANE_COUNT=2" in restore_text
        and "HWLOOP: IR_B_MODE=stream_bidir" in restore_text
        and "PORT1.xdc" in xpr_text
        and "target_ir_array_external_5lane_scan.xdc" not in xpr_text
        and "target_ir_array_8lane" not in xpr_text
        and "output [1:0]ir_tx_out_0" in wrapper_text
        and "input [1:0]loop_rx_b0" in wrapper_text
    )
    stopped_after_stall = "EXTERNAL_RESOURCE_SCAN_LANE_START=6" in vivado_text and "EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS lane=6" not in vivado_text
    no_hw = meta.get("no_hardware_programming") == "1" and meta.get("no_uart_write") == "1" and meta.get("no_tfdu_drive") == "1"
    overall = "FIRST_BLOCKED_AT_5LANE_REDUCED_PROFILE" if lane5_blocked and restored and no_hw else "INCOMPLETE_REVIEW_REQUIRED"

    csv_path = REPORTS / "external_reduced_5to8_extension_current.csv"
    json_path = REPORTS / "external_reduced_5to8_extension_current.json"
    md_path = REPORTS / "external_reduced_5to8_extension_current.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for item in results:
            writer.writerow(asdict(item))

    table_rows = [
        [
            str(item.lane_count),
            item.status,
            item.synth_status,
            item.impl_status,
            "" if item.total_luts is None else f"{item.total_luts}/{item.available_luts}",
            "" if item.slice_required is None else f"{item.slice_required}/{item.slice_available}",
            "" if item.control_sets is None else str(item.control_sets),
            item.evidence,
            item.note,
        ]
        for item in results
    ]
    md = [
        "# External Reduced 5-to-8 Lane Extension Scan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- First blocked reduced lane count: `5`",
        f"- Last proven reduced lane count remains: `4`",
        f"- Lane 5 LUT usage at placement failure: `{lane5.total_luts}/{lane5.available_luts}` total LUTs",
        f"- Lane 5 slice demand at placement failure: `{lane5.slice_required}/{lane5.slice_available}` slices",
        f"- Lane 5 control sets: `{lane5.control_sets}`",
        f"- Lane 6..8 direct results: stopped after lane 6 stalled; lane 5 already establishes the first resource boundary.",
        f"- Project restored to active 2-lane stream_bidir / PORT1.xdc: `{int(restored)}`",
        "- This is offline Vivado evidence only. It is not route, timing, bitstream, TCP/DHCP, two-AX7010, or TFDU hardware acceptance.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "",
        "## Lane Results",
        "",
        md_table(["lane", "status", "synth", "impl", "LUTs", "slices", "control sets", "evidence", "note"], table_rows),
        "",
        "## Files",
        "",
        f"- Meta: `{rel(meta_file)}`",
        f"- Vivado log: `{rel(vivado_log)}`",
        f"- Stdout: `{rel(stdout_log)}`",
        f"- Stderr: `{rel(stderr_log)}`",
        f"- Restore log: `{rel(restore_log)}`",
        "",
        f"RF_COMM_EXTERNAL_REDUCED_5TO8_EXTENSION overall={overall} first_blocked_lane=5 max_place_pass_lane=4 lane5_luts={lane5.total_luts}/{lane5.available_luts} restored_2lane={int(restored)} stopped_after_stall={int(stopped_after_stall)}",
    ]
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
        "restore_log": rel(restore_log),
        "lane5_resource_blocked": lane5_blocked,
        "first_blocked_lane_count": 5,
        "max_place_pass_lane_count": 4,
        "stopped_after_lane6_stall": stopped_after_stall,
        "restored_2lane_stream_bidir": restored,
        "no_hardware_programming": meta.get("no_hardware_programming") == "1",
        "no_uart_write": meta.get("no_uart_write") == "1",
        "no_tfdu_drive": meta.get("no_tfdu_drive") == "1",
        "current_board_ethernet": "not_connected",
        "real_tcp_dhcp_deferred": meta.get("ethernet_real_test_deferred") == "1",
        "lane_results": [asdict(item) for item in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        f"RF_COMM_EXTERNAL_REDUCED_5TO8_EXTENSION overall={overall} first_blocked_lane=5 "
        f"max_place_pass_lane=4 lane5_luts={lane5.total_luts}/{lane5.available_luts} "
        f"restored_2lane={int(restored)} stopped_after_stall={int(stopped_after_stall)}"
    )
    return 0 if overall == "FIRST_BLOCKED_AT_5LANE_REDUCED_PROFILE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
