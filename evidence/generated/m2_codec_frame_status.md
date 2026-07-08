# M2 4PPM Codec And Frame L1 Status

M2_4PPM_CODEC_RTL_IMPLEMENTED=1
M2_4PPM_PREAMBLE_BEHAVIOR_IMPLEMENTED=1
M2_FRAME_L1_RTL_IMPLEMENTED=1
M2_FRAME_L1_NO_ACK_RETRY=1
M2_4PPM_CODEC_TB_CREATED=1
M2_4PPM_PREAMBLE_TB_CREATED=1
M2_4PPM_TFDU_MODEL_INTEGRATION_TB_CREATED=1
M2_4PPM_TFDU_MODEL_PREAMBLE_TB_CREATED=1
M2_FRAME_L1_TB_CREATED=1
M2_STATIC_REFERENCE_CHECKS=PASS
M2_4PPM_CODEC_SIM=PENDING_TOOL
M2_4PPM_MODEL_INTEGRATION_SIM=PENDING_TOOL
M2_FRAME_L1_SIM=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/check_m2_static.py` verifies the required RTL structures and Python
reference vectors for 4PPM symbol mapping, frame CRC, session mismatch, lane
mask mismatch, and payload length mismatch. It also verifies that the 4PPM
model-integration testbench instantiates `tfdu6102_behavior_model`, decodes
low-active `Rxd` through the abstract pulse-stream RX interface, and exercises
the `CNT_PREAMBLE` transmit and receive path instead of only checking that the
parameter name exists. SystemVerilog simulation remains unclaimed until
`iverilog`, `verilator`, or a Vivado batch simulator is available on PATH.
