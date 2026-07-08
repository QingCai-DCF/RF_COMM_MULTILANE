#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


def main() -> int:
    errors: list[str] = []
    rtl = (ROOT / "rtl/ir_multilane_scheduler.sv").read_text(encoding="utf-8", errors="ignore")
    tb = (ROOT / "sim/tb/tb_ir_multilane_scheduler.sv").read_text(encoding="utf-8", errors="ignore")

    require("DEFAULT_LANE_ENABLE_MASK" in rtl and "1'b1" in rtl, "SCHED_DEFAULT_LANE0_ENABLED", errors)
    require("LANE1_DEFAULT_DISABLED" in rtl, "SCHED_LANE1_DEFAULT_DISABLED_MARKER", errors)
    require('known_bad_raw_direction = "AB_L1"' in rtl, "SCHED_KNOWN_BAD_AB_L1_MARKER", errors)
    require("KNOWN_BAD_RAW_DIRECTION_MASK" in rtl and "lane1_reliable_blocked" in rtl, "SCHED_AB_L1_BLOCK_PRESENT", errors)
    require("requested_lane_enable_readback" in rtl and "lane_enable_readback" in rtl, "SCHED_ENABLE_READBACK_PRESENT", errors)
    require("sticky_bad_lane_mask" in rtl and "lane_fault_pulse" in rtl, "SCHED_STICKY_BAD_LANE_PRESENT", errors)
    require("fallback_to_lane0_active" in rtl and "effective_reliable_lane_mask" in rtl, "SCHED_FALLBACK_PRESENT", errors)
    require("selected_tx_lane" in rtl and "first_enabled_lane" in rtl, "SCHED_SELECTED_LANE_PRESENT", errors)
    require("TB_IR_MULTILANE_SCHEDULER_PASS=1" in tb, "SCHED_TB_PASS_MARKER_PRESENT", errors)
    require("lane1 reliable enable request is blocked" in tb, "SCHED_TB_LANE1_BLOCK_CASE", errors)
    require("scheduler falls forward to lane2" in tb, "SCHED_TB_FAULT_FALLBACK_CASE", errors)

    print(f"SCHED_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
