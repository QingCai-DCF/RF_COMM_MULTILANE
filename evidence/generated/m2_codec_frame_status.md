# M2 4PPM Codec And Frame L1 Status

M2_4PPM_CODEC_RTL_IMPLEMENTED=1
M2_FRAME_L1_RTL_IMPLEMENTED=1
M2_4PPM_CODEC_TB_CREATED=1
M2_FRAME_L1_TB_CREATED=1
M2_STATIC_REFERENCE_CHECKS=PASS
M2_4PPM_CODEC_SIM=PENDING_TOOL
M2_FRAME_L1_SIM=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/check_m2_static.py` verifies the required RTL structures and Python
reference vectors for 4PPM symbol mapping, frame CRC, session mismatch, lane
mask mismatch, and payload length mismatch. SystemVerilog simulation remains
unclaimed until `iverilog`, `verilator`, or a Vivado batch simulator is
available on PATH.
