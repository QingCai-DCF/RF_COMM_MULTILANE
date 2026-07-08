# M1 TFDU Lane PHY Status

M1_TFDU_LANE_PHY_RTL_IMPLEMENTED=1
TFDU_BEHAVIOR_MODEL_IMPLEMENTED=1
TFDU_BEHAVIOR_MODEL_TIMING_RANGES=1
TFDU_BEHAVIOR_MODEL_PULSE_LOSS_CONFIGURABLE=1
TFDU_BEHAVIOR_MODEL_NEAR_END_ECHO_OPTIONAL=1
TFDU_BEHAVIOR_MODEL_LONG_HIGH_PROTECTION=1
M1_TFDU_MODEL_REFERENCE_REPORT_CREATED=1
TB_TFDU_LANE_PHY_SMOKE_CREATED=1
TFDU_SAFETY_STATIC=PASS
LANE_PHY_SIM=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

The current workstation does not expose `verilator`, `iverilog`, or `vivado` on
PATH. `scripts/run_offline_gates.py` will compile/run
`sim/tb/tb_tfdu_lane_phy_smoke.sv` automatically when a supported SystemVerilog
tool is available. The offline TFDU model reference report at
`evidence/generated/m1_tfdu_model_reference.md` checks the model contract for
startup, low-active RX, 125 ns and 250 ns pulse width ranges, jitter, pulse
loss, near-end echo settings, and long-high optical disable. Until a simulator
is available, M1 is implemented and statically/reference gated, but the SV
simulation pass remains unclaimed.
