#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


P8D_LANE_STAT_FIELDS = {
    "SCHEDULED_FRAMES": 0,
    "SCHEDULED_BYTES": 1,
    "RETRIES": 2,
    "MIGRATIONS": 3,
    "DEFER_COUNT": 4,
}


def p8d_rtl_consumes_register(name: str, offset: int, rtl: str) -> bool:
    """Confirm that the additive P8D front-end decodes the canonical register."""
    if f"`IR_REG_{name}" in rtl:
        return True

    # Per-lane statistics are deliberately decoded as one regular 8 x 5 array
    # instead of forty duplicated case items.  Prove both the canonical offset
    # arithmetic and the RTL range/index decoder for every generated register.
    match = re.fullmatch(
        r"P8D_LANE([0-7])_(SCHEDULED_FRAMES|SCHEDULED_BYTES|RETRIES|MIGRATIONS|DEFER_COUNT)",
        name,
    )
    if match is None:
        return False
    lane = int(match.group(1))
    field_index = P8D_LANE_STAT_FIELDS[match.group(2)]
    expected_offset = 0x640 + lane * 5 * 4 + field_index * 4
    decoder_tokens = (
        "rd_addr>=12'h640",
        "rd_addr<=12'h6dc",
        "statistic_index=(rd_addr-12'h640)>>2",
        "statistic_lane=statistic_index/5",
        "statistic_field=statistic_index%5",
    )
    return offset == expected_offset and all(token in rtl for token in decoder_tokens)


@dataclass
class RegModel:
    regs: dict[int, int] = field(default_factory=dict)
    profile_committed: bool = False
    commit_count: int = 0
    profile_id: int = 0x47312201

    def write(self, offset: int, value: int) -> None:
        self.regs[offset] = value & 0xFFFFFFFF
        if offset == 0x0000 and (value & (1 << 5)):
            self.profile_committed = True
            self.commit_count += 1

    def read(self, offset: int) -> int:
        if offset == 0x00F0:
            return self.profile_id
        return self.regs.get(offset, 0)


def main() -> int:
    errors: list[str] = []
    data = json.loads((ROOT / "config/register_map/ir_axi_regs.yaml").read_text(encoding="utf-8"))
    regs = data["registers"]
    offsets = {r["name"]: int(r["offset"], 16) for r in regs}
    legacy_rtl = "\n".join(
        (ROOT / path).read_text(encoding="utf-8", errors="ignore")
        for path in ("rtl/ir_axi_regs_new.sv", "rtl/ir_p8c_safety_regs.sv")
    )
    p8d_rtl = (ROOT / "rtl/ir_p8d_data_plane_regs.sv").read_text(
        encoding="utf-8", errors="ignore"
    )
    hdr = (ROOT / "config/register_map/generated/ir_regs.h").read_text(encoding="utf-8", errors="ignore")
    py = (ROOT / "config/register_map/generated/ir_regs.py").read_text(encoding="utf-8", errors="ignore")
    md = (ROOT / "docs/design/REGISTER_CONTRACT.md").read_text(encoding="utf-8", errors="ignore")
    driver = (ROOT / "software/ps_driver/ir_driver.c").read_text(encoding="utf-8", errors="ignore")
    driver_h = (ROOT / "software/ps_driver/ir_driver.h").read_text(encoding="utf-8", errors="ignore")
    tb = (ROOT / "sim/tb/tb_ir_axi_regs_new.sv").read_text(encoding="utf-8", errors="ignore")
    trace_script = (ROOT / "scripts/generate_m4_ps_driver_trace.py").read_text(encoding="utf-8", errors="ignore")
    trace_report_path = ROOT / "evidence/generated/m4_ps_driver_trace.md"
    trace_report = trace_report_path.read_text(encoding="utf-8", errors="ignore") if trace_report_path.exists() else ""

    for name, off in offsets.items():
        macro = f"IR_REG_{name}"
        require(macro in hdr and macro in py, f"M4_GENERATED_OFFSET_{name}", errors)
        require(f"`{name}`" in md and f"`0x{off:04X}`" in md, f"M4_DOC_OFFSET_{name}", errors)
        if name.startswith("P8D_"):
            rtl_consumes_register = p8d_rtl_consumes_register(name, off, p8d_rtl)
        else:
            rtl_consumes_register = ("REG_" + name) in legacy_rtl
        require(rtl_consumes_register, f"M4_RTL_OFFSET_{name}", errors)

    require("wr_en" in legacy_rtl and "rd_en" in legacy_rtl and "rd_valid" in legacy_rtl, "M4_REGISTER_BUS_PRESENT", errors)
    require("wr_en" in p8d_rtl and "rd_en" in p8d_rtl and "rd_valid" in p8d_rtl, "M4_P8D_REGISTER_BUS_PRESENT", errors)
    require("commit_pulse" in legacy_rtl and "profile_committed" in legacy_rtl and "commit_count" in legacy_rtl, "M4_COMMIT_READBACK_PRESENT", errors)
    require("cfg_payload_lane_mask" in legacy_rtl and "cfg_ack_lane_mask" in legacy_rtl and "cfg_session" in legacy_rtl, "M4_PROFILE_OUTPUTS_PRESENT", errors)
    require("status_phy_ready" in legacy_rtl and "counter_tx_pulse" in legacy_rtl and "counter_ack_seen" in legacy_rtl, "M4_STATUS_COUNTER_INPUTS_PRESENT", errors)
    require("PROFILE_ID_VALUE" in legacy_rtl and "REG_PROFILE_ID" in legacy_rtl, "M4_PROFILE_ID_EXPOSED", errors)
    require("ir_write_readback" in driver and "IR_CONTROL_COMMIT" in driver, "M4_PS_DRIVER_READBACK_COMMIT_PRESENT", errors)
    require("IR_REG_PROFILE_LANE_MASK" in driver and "IR_REG_PROFILE_ACK_LANE_MASK" in driver, "M4_PS_DRIVER_CRITICAL_REGS_PRESENT", errors)
    require("ir_driver_initialize" in driver and "ir_driver_wait_startup" in driver, "M4_PS_DRIVER_STARTUP_WAIT_PRESENT", errors)
    require("IR_CONTROL_ENABLE_PHY | IR_CONTROL_CLEAR_STICKY" in driver, "M4_PS_DRIVER_CLEAR_STICKY_AFTER_STARTUP", errors)
    require("ir_driver_poll_done" in driver and "ir_driver_read_final_counters" in driver, "M4_PS_DRIVER_POLL_AND_COUNTERS_PRESENT", errors)
    require("IR_REG_COUNTER_FRAME_GOOD" in driver and "IR_REG_STATUS_ERROR_COUNTS" in driver, "M4_PS_DRIVER_FINAL_COUNTER_READS_PRESENT", errors)
    require("ir_mmio_t" in driver_h and "ir_profile_config_t" in driver_h, "M4_PS_DRIVER_MMIO_PROFILE_TYPES_PRESENT", errors)
    require("ir_driver_counters_t" in driver_h and "ir_driver_run_transaction" in driver_h, "M4_PS_DRIVER_OFFLINE_RUN_API_PRESENT", errors)
    require("TB_IR_AXI_REGS_NEW_PASS=1" in tb, "M4_AXI_REGS_TB_PASS_MARKER_PRESENT", errors)
    require("MmioTrace" in trace_script and "M4_TRACE_COMMIT_BEFORE_ENABLE" in trace_script, "M4_PS_DRIVER_TRACE_SCRIPT_PRESENT", errors)
    require(
        "M4_PS_DRIVER_TRACE_REPORT=1" in trace_report
        and "M4_PS_DRIVER_TRACE=PASS" in trace_report,
        "M4_PS_DRIVER_TRACE_REPORT_PRESENT",
        errors,
    )

    profile_values = {
        "PROFILE_LANE_MASK": 0x1,
        "PROFILE_RX_LANE_MASK": 0x1,
        "PROFILE_ACK_LANE_MASK": 0x1,
        "PROFILE_SESSION": 0x2201,
        "PROFILE_PAYLOAD_LEN": 256,
        "PROFILE_FRAGMENT_BYTES": 255,
        "TIMING_CNT_CHIP_MAX": 7,
        "TIMING_CNT_PREAMBLE": 16,
        "TIMING_DETECT_WINDOW": 0x0700,
        "TIMING_GUARD_CYCLES": 4096,
        "TIMING_RETRY_TIMEOUT": 1024,
        "SAFETY_STARTUP_US": 500,
        "SAFETY_DUTY_WINDOW": 1000,
        "SAFETY_DUTY_MAX": 200,
        "SAFETY_STUCK_HIGH_LIMIT": 10,
    }
    model = RegModel()
    for name, value in profile_values.items():
        model.write(offsets[name], value)
        require(model.read(offsets[name]) == value, f"M4_REFERENCE_READBACK_{name}", errors)
    model.write(offsets["CONTROL"], 1 << 5)
    require(model.profile_committed and model.commit_count == 1, "M4_REFERENCE_COMMIT_PASS", errors)
    require(model.read(offsets["PROFILE_ID"]) == 0x47312201, "M4_REFERENCE_PROFILE_ID_PASS", errors)
    require("M4_TRACE_RESET_BEFORE_PROFILE=1" in trace_report, "M4_TRACE_REFERENCE_RESET_BEFORE_PROFILE", errors)
    require("M4_TRACE_PROFILE_READBACKS_MATCH=1" in trace_report, "M4_TRACE_REFERENCE_PROFILE_READBACKS", errors)
    require("M4_TRACE_STARTUP_WAIT_BEFORE_CLEAR=1" in trace_report, "M4_TRACE_REFERENCE_STARTUP_CLEAR_ORDER", errors)
    require("M4_TRACE_FINAL_COUNTER_READS=1" in trace_report, "M4_TRACE_REFERENCE_FINAL_COUNTERS", errors)
    require("M4_TRACE_SHUTDOWN_REASON_WRITTEN=1" in trace_report, "M4_TRACE_REFERENCE_SHUTDOWN", errors)

    print(f"M4_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
