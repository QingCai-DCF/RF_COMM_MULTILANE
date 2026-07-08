#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = (
    "open_" + "hw",
    "connect_" + "hw_server",
    "program_" + "hw_devices",
    "x" + "sct",
)


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


def main() -> int:
    errors: list[str] = []
    tcl = (ROOT / "scripts/vivado_nonhardware_build.tcl").read_text(encoding="utf-8", errors="ignore")
    runner = (ROOT / "scripts/run_vivado_nonhardware_build.py").read_text(encoding="utf-8", errors="ignore")
    top = (ROOT / "rtl/ir_top_new.sv").read_text(encoding="utf-8", errors="ignore")
    pinmap_rows = list(csv.DictReader((ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv").open(encoding="utf-8")))

    require("create_project" in tcl and "read_xdc" in tcl, "M5_VIVADO_PROJECT_AND_XDC_SCRIPTED", errors)
    require("synth_design" in tcl and "opt_design" in tcl and "place_design" in tcl and "route_design" in tcl, "M5_SYNTH_IMPL_ROUTE_SCRIPTED", errors)
    require("report_drc" in tcl and "report_timing_summary" in tcl and "report_utilization" in tcl, "M5_REPORTS_SCRIPTED", errors)
    require("write_bitstream" not in tcl, "M5_NO_BITSTREAM_GENERATION", errors)
    require(not any(token in tcl.lower() for token in FORBIDDEN), "M5_TCL_HAS_NO_HARDWARE_CALLS", errors)
    require(not any(token in runner.lower() for token in FORBIDDEN), "M5_RUNNER_HAS_NO_HARDWARE_CALLS", errors)
    require("resolve_vivado_executable" in runner and "VIVADO_PATH_ON_PATH" in runner, "M5_RUNNER_RECORDS_VIVADO_DISCOVERY", errors)
    require("XILINX_VIVADO_2023_1_BAT_AVAILABLE" in runner, "M5_RUNNER_RECORDS_VIVADO_BAT_FALLBACK", errors)
    require("evidence/generated/vivado" in runner and "nonhardware_build_summary" in runner, "M5_RUNNER_WRITES_EVIDENCE", errors)
    require("ir_top_new" in tcl and "set_property top ir_top_new" in tcl, "M5_CANONICAL_TOP_SELECTED", errors)

    for row in pinmap_rows:
        base = row["port"].split("[", 1)[0]
        require(base in top, f"M5_TOP_HAS_PORT_{row['port']}", errors)
    require("ir_sd_0 = 2'b11" in top and "loop_sd_b0 = 2'b11" in top, "M5_TOP_DEFAULTS_TFDU_SHUTDOWN", errors)
    require("ir_tx_out_0 = 2'b00" in top and "loop_tx_b0 = 2'b00" in top, "M5_TOP_DEFAULTS_TX_IDLE_LOW", errors)
    require("ir_mode_out_0 = 2'b11" in top and "loop_mode_b0 = 2'b11" in top, "M5_TOP_DEFAULTS_MODE_HIGH", errors)

    print(f"M5_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
