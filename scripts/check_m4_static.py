#!/usr/bin/env python3
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(cond: bool, marker: str, errors: list[str]) -> None:
    print(f"{marker}={1 if cond else 0}")
    if not cond:
        errors.append(marker)


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
    rtl = (ROOT / "rtl/ir_axi_regs_new.sv").read_text(encoding="utf-8", errors="ignore")
    hdr = (ROOT / "config/register_map/generated/ir_regs.h").read_text(encoding="utf-8", errors="ignore")
    py = (ROOT / "config/register_map/generated/ir_regs.py").read_text(encoding="utf-8", errors="ignore")
    md = (ROOT / "docs/design/REGISTER_CONTRACT.md").read_text(encoding="utf-8", errors="ignore")
    driver = (ROOT / "software/ps_driver/ir_driver.c").read_text(encoding="utf-8", errors="ignore")
    driver_h = (ROOT / "software/ps_driver/ir_driver.h").read_text(encoding="utf-8", errors="ignore")
    tb = (ROOT / "sim/tb/tb_ir_axi_regs_new.sv").read_text(encoding="utf-8", errors="ignore")

    for name, off in offsets.items():
        macro = f"IR_REG_{name}"
        rtl_name = "REG_" + name
        require(macro in hdr and macro in py, f"M4_GENERATED_OFFSET_{name}", errors)
        require(f"`{name}`" in md and f"`0x{off:04X}`" in md, f"M4_DOC_OFFSET_{name}", errors)
        require(rtl_name in rtl, f"M4_RTL_OFFSET_{name}", errors)

    require("wr_en" in rtl and "rd_en" in rtl and "rd_valid" in rtl, "M4_REGISTER_BUS_PRESENT", errors)
    require("commit_pulse" in rtl and "profile_committed" in rtl and "commit_count" in rtl, "M4_COMMIT_READBACK_PRESENT", errors)
    require("cfg_payload_lane_mask" in rtl and "cfg_ack_lane_mask" in rtl and "cfg_session" in rtl, "M4_PROFILE_OUTPUTS_PRESENT", errors)
    require("status_phy_ready" in rtl and "counter_tx_pulse" in rtl and "counter_ack_seen" in rtl, "M4_STATUS_COUNTER_INPUTS_PRESENT", errors)
    require("PROFILE_ID_VALUE" in rtl and "REG_PROFILE_ID" in rtl, "M4_PROFILE_ID_EXPOSED", errors)
    require("ir_write_readback" in driver and "IR_CONTROL_COMMIT" in driver, "M4_PS_DRIVER_READBACK_COMMIT_PRESENT", errors)
    require("IR_REG_PROFILE_LANE_MASK" in driver and "IR_REG_PROFILE_ACK_LANE_MASK" in driver, "M4_PS_DRIVER_CRITICAL_REGS_PRESENT", errors)
    require("ir_mmio_t" in driver_h and "ir_profile_config_t" in driver_h, "M4_PS_DRIVER_MMIO_PROFILE_TYPES_PRESENT", errors)
    require("TB_IR_AXI_REGS_NEW_PASS=1" in tb, "M4_AXI_REGS_TB_PASS_MARKER_PRESENT", errors)

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
        "SAFETY_STUCK_HIGH_LIMIT": 20,
    }
    model = RegModel()
    for name, value in profile_values.items():
        model.write(offsets[name], value)
        require(model.read(offsets[name]) == value, f"M4_REFERENCE_READBACK_{name}", errors)
    model.write(offsets["CONTROL"], 1 << 5)
    require(model.profile_committed and model.commit_count == 1, "M4_REFERENCE_COMMIT_PASS", errors)
    require(model.read(offsets["PROFILE_ID"]) == 0x47312201, "M4_REFERENCE_PROFILE_ID_PASS", errors)

    print(f"M4_STATIC={'PASS' if not errors else 'FAIL'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
