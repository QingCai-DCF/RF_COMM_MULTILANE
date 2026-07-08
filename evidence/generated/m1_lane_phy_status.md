# M1 TFDU Lane PHY Status

M1_TFDU_LANE_PHY_RTL_IMPLEMENTED=1
TFDU_BEHAVIOR_MODEL_IMPLEMENTED=1
TB_TFDU_LANE_PHY_SMOKE_CREATED=1
TFDU_SAFETY_STATIC=PASS
LANE_PHY_SIM=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

The current workstation does not expose `verilator`, `iverilog`, or `vivado` on
PATH. `scripts/run_offline_gates.py` will compile/run
`sim/tb/tb_tfdu_lane_phy_smoke.sv` automatically when a supported SystemVerilog
tool is available. Until then, M1 is implemented and statically gated, but the
SV simulation pass remains unclaimed.
