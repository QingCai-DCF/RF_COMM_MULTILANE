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
LANE_PHY_SIM=PASS
NO_HARDWARE_ACTIONS_EXECUTED=1

Current PATH discovery records `IVERILOG_ON_PATH=0`, `VERILATOR_ON_PATH=0`, and
`VIVADO_PATH_ON_PATH=0`, but the D:\Xilinx\Vivado\2023.1\bin Xilinx simulator
bat tools are available and `scripts/run_offline_gates.py` uses them to run
`sim/tb/tb_tfdu_lane_phy_smoke.sv`. The offline TFDU model reference report at
`evidence/generated/m1_tfdu_model_reference.md` checks the model contract for
startup, low-active RX, 125 ns and 250 ns pulse width ranges, jitter, pulse
loss, near-end echo settings, and long-high optical disable. M1 now has both
static/reference evidence and Xilinx xsim simulation evidence.
