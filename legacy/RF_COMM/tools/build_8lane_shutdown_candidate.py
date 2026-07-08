from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PINMAP_CSV = REPORTS / "8lane_candidate_pinmap_current.csv"
TOP_V = ROOT / "tools" / "tfdu_shutdown_8lane_candidate_top.v"
XDC = ROOT / "tools" / "tfdu_shutdown_8lane_candidate.xdc"
BUILD_TCL = ROOT / "tools" / "build_tfdu_shutdown_8lane_candidate.tcl"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
OUTPUT_SIGNALS = {"MODE", "SD", "TX"}
INPUT_SIGNALS = {"RX"}


@dataclass
class ShutdownAssignment:
    endpoint: str
    lane: int
    signal: str
    port: str
    package_pin: str
    direction: str
    shutdown_value: str
    source_origin: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_pinmap() -> list[dict[str, str]]:
    if not PINMAP_CSV.exists():
        raise FileNotFoundError(f"Missing candidate pinmap CSV: {PINMAP_CSV}")
    with PINMAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 64:
        raise RuntimeError(f"Expected 64 candidate pinmap rows, got {len(rows)}")
    return rows


def make_shutdown_assignments(rows: list[dict[str, str]]) -> list[ShutdownAssignment]:
    assignments: list[ShutdownAssignment] = []
    for row in rows:
        signal = row["signal"]
        if signal in OUTPUT_SIGNALS:
            direction = "output"
            shutdown_value = "1" if signal == "SD" else "0"
        elif signal in INPUT_SIGNALS:
            direction = "input"
            shutdown_value = "input"
        else:
            raise RuntimeError(f"Unexpected signal in pinmap: {signal}")
        assignments.append(
            ShutdownAssignment(
                endpoint=row["endpoint"],
                lane=int(row["lane"]),
                signal=signal,
                port=row["port"],
                package_pin=row["package_pin"],
                direction=direction,
                shutdown_value=shutdown_value,
                source_origin=row.get("origin", ""),
                note="Derived from 8-lane candidate pinmap; review before building or programming hardware.",
            )
        )
    return assignments


def validate(assignments: list[ShutdownAssignment]) -> None:
    if len(assignments) != 64:
        raise RuntimeError(f"Expected 64 shutdown assignments, got {len(assignments)}")
    pins: dict[str, list[str]] = {}
    for item in assignments:
        pins.setdefault(item.package_pin, []).append(item.port)
    dupes = {pin: ports for pin, ports in pins.items() if len(ports) > 1}
    if dupes:
        raise RuntimeError(f"Duplicate package pins in shutdown candidate: {dupes}")
    for endpoint in ["A", "B"]:
        for lane in range(8):
            got = {
                item.signal
                for item in assignments
                if item.endpoint == endpoint and item.lane == lane
            }
            if got != {"MODE", "RX", "SD", "TX"}:
                raise RuntimeError(f"Missing shutdown signals for endpoint={endpoint} lane={lane}: {got}")
    if any(item.package_pin == "D19" for item in assignments):
        raise RuntimeError("D19 is present in shutdown candidate even though it should remain excluded")


def write_top() -> None:
    text = """module tfdu_shutdown_8lane_candidate_top (
  output wire [7:0] ir_mode_out_0,
  input  wire [7:0] ir_rx_in_0,
  output wire [7:0] ir_sd_0,
  output wire [7:0] ir_tx_out_0,

  output wire [7:0] loop_mode_b0,
  input  wire [7:0] loop_rx_b0,
  output wire [7:0] loop_sd_b0,
  output wire [7:0] loop_tx_b0
);
  assign ir_mode_out_0 = 8'h00;
  assign ir_sd_0       = 8'hff;
  assign ir_tx_out_0   = 8'h00;

  assign loop_mode_b0  = 8'h00;
  assign loop_sd_b0    = 8'hff;
  assign loop_tx_b0    = 8'h00;

  wire unused_rx = (^ir_rx_in_0) ^ (^loop_rx_b0);
endmodule
"""
    TOP_V.write_text(text, encoding="utf-8")


def write_xdc(assignments: list[ShutdownAssignment], generated: str) -> None:
    lines = [
        "###############################################################################",
        "# 8-lane TFDU shutdown candidate constraints",
        "#",
        f"# Generated: {generated}",
        "# Source: reports/8lane_candidate_pinmap_current.csv",
        "#",
        "# Candidate only: build/review before hardware use.",
        "# This file is not used by the current program_tfdu_shutdown.tcl path.",
        "###############################################################################",
        "",
    ]
    for item in assignments:
        lines.append(f"# {item.port} endpoint={item.endpoint} lane={item.lane} signal={item.signal} shutdown={item.shutdown_value} origin={item.source_origin}")
        lines.append(f"set_property PACKAGE_PIN {item.package_pin} [get_ports {{{item.port}}}]")
        lines.append(f"set_property IOSTANDARD LVCMOS33 [get_ports {{{item.port}}}]")
    output_ports = sorted(item.port for item in assignments if item.direction == "output")
    lines.extend(
        [
            "",
            "set_property DRIVE 4 [get_ports {",
            "  " + " ".join(output_ports),
            "}]",
            "set_property SLEW SLOW [get_ports {",
            "  " + " ".join(output_ports),
            "}]",
            "",
        ]
    )
    XDC.write_text("\n".join(lines), encoding="utf-8")


def write_build_tcl() -> None:
    text = """set repo_root [file normalize [file join [file dirname [info script]] ".."]]
set out_dir [file join $repo_root "shutdown_bitstream"]
file mkdir $out_dir

set_param general.maxThreads 16

set bit_file [file join $out_dir "tfdu_shutdown_8lane_candidate.bit"]
set dcp_file [file join $out_dir "tfdu_shutdown_8lane_candidate_routed.dcp"]
set util_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_utilization.rpt"]
set timing_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_timing_summary.rpt"]
set drc_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_drc.rpt"]
set io_rpt [file join $out_dir "tfdu_shutdown_8lane_candidate_io.rpt"]

read_verilog [file join $repo_root "tools" "tfdu_shutdown_8lane_candidate_top.v"]
read_xdc [file join $repo_root "tools" "tfdu_shutdown_8lane_candidate.xdc"]

synth_design -top tfdu_shutdown_8lane_candidate_top -part xc7z010clg400-1
report_utilization -file $util_rpt
opt_design
place_design
route_design
report_drc -file $drc_rpt
report_timing_summary -file $timing_rpt
report_io -file $io_rpt
write_checkpoint -force $dcp_file
write_bitstream -force $bit_file
puts "TFDU_SHUTDOWN_8LANE_CANDIDATE_BITSTREAM_READY $bit_file"
"""
    BUILD_TCL.write_text(text, encoding="utf-8")


def write_reports(assignments: list[ShutdownAssignment], generated: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "8lane_shutdown_candidate_current.md"
    json_path = REPORTS / "8lane_shutdown_candidate_current.json"
    csv_path = REPORTS / "8lane_shutdown_candidate_current.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(assignments[0]).keys()))
        writer.writeheader()
        for item in assignments:
            writer.writerow(asdict(item))

    output_count = sum(1 for item in assignments if item.direction == "output")
    input_count = sum(1 for item in assignments if item.direction == "input")
    md = [
        "# 8-Lane Shutdown Candidate",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        "- Overall: `CANDIDATE_SHUTDOWN_GENERATED_REVIEW_REQUIRED`",
        "- Shutdown assignments: `64/64`",
        f"- Outputs driven to shutdown state: `{output_count}`",
        f"- RX inputs constrained and absorbed: `{input_count}`",
        "- This is not a programmed shutdown bitstream.",
        "",
        "## Generated Files",
        "",
        f"- Verilog top: `{rel(TOP_V)}`",
        f"- XDC: `{rel(XDC)}`",
        f"- Build Tcl: `{rel(BUILD_TCL)}`",
        "",
        "## Safety",
        "",
        "- No FPGA was programmed.",
        "- No UART was written.",
        "- No TFDU was driven.",
        "- Existing `program_tfdu_shutdown.tcl` still points to the proven J10/J11 shutdown bitstream.",
        "",
        "## Shutdown Table",
        "",
        "| endpoint | lane | signal | port | package_pin | direction | shutdown_value | origin |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in assignments:
        md.append(
            f"| {item.endpoint} | {item.lane} | {item.signal} | {item.port} | {item.package_pin} | {item.direction} | {item.shutdown_value} | {item.source_origin} |"
        )
    md.extend(
        [
            "",
            "RF_COMM_8LANE_SHUTDOWN_CANDIDATE overall=CANDIDATE_SHUTDOWN_GENERATED_REVIEW_REQUIRED assignments=64",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": "CANDIDATE_SHUTDOWN_GENERATED_REVIEW_REQUIRED",
        "hard_constraint_sha256": sha256(find_hard_constraint()),
        "pinmap_csv": rel(PINMAP_CSV),
        "top_v": rel(TOP_V),
        "xdc": rel(XDC),
        "build_tcl": rel(BUILD_TCL),
        "output_count": output_count,
        "input_count": input_count,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "assignments": [asdict(item) for item in assignments],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    if find_hard_constraint() is None:
        raise RuntimeError("Hard constraint file was not found by expected hash")
    assignments = make_shutdown_assignments(load_pinmap())
    validate(assignments)
    generated = datetime.now().isoformat(timespec="seconds")
    write_top()
    write_xdc(assignments, generated)
    write_build_tcl()
    write_reports(assignments, generated)
    print(f"WROTE_VERILOG={TOP_V}")
    print(f"WROTE_XDC={XDC}")
    print(f"WROTE_TCL={BUILD_TCL}")
    print(f"WROTE_MARKDOWN={REPORTS / '8lane_shutdown_candidate_current.md'}")
    print(f"WROTE_JSON={REPORTS / '8lane_shutdown_candidate_current.json'}")
    print(f"WROTE_CSV={REPORTS / '8lane_shutdown_candidate_current.csv'}")
    print("RF_COMM_8LANE_SHUTDOWN_CANDIDATE overall=CANDIDATE_SHUTDOWN_GENERATED_REVIEW_REQUIRED assignments=64")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
