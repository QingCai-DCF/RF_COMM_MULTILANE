# M3 Lane0 ACK/Retry Status

M3_ARQ_L2_RTL_IMPLEMENTED=1
M3_LANE0_ACK_ONLY_TB_CREATED=1
M3_STATIC_REFERENCE_CHECKS=PASS
M3_PAYLOAD_ACK_MASKS_SEPARATE=1
M3_ACK_SEEN_REFERENCE=PASS
M3_ACK_LOST_RETRY_REFERENCE=PASS
M3_RETRY_EXHAUSTED_REFERENCE=PASS
M3_ACK_SESSION_MISMATCH_REFERENCE=PASS
M3_ACK_MASK_MISMATCH_REFERENCE=PASS
M3_ACK_DUPLICATE_EXPIRED_LATE_REFERENCE=PASS
M3_CRC_BAD_ACK_REFERENCE=PASS
M3_LANE0_ACK_ONLY_SIM=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/check_m3_static.py` verifies the required RTL structures and a Python
reference ARQ model for lane0 ACK-only behavior, including ACK seen, ACK lost
retry, retry exhaustion, session mismatch, ACK lane mask mismatch, duplicate
ACK, expired/out-of-order ACK, and late ACK. It also requires
`evidence/generated/m3_crc_bad_ack_reference.md`, which proves that a CRC-bad
L1 frame suppresses ACK and drives the L2 retry-exhausted path in the offline
reference model. SystemVerilog simulation remains unclaimed until `iverilog`,
`verilator`, or a Vivado batch simulator is available on PATH.
