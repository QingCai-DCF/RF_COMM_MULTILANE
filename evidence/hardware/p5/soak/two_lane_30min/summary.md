# Two Lane 30Min Soak

generated_at_utc: 2026-07-09T15:42:46+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS
reason: authorized P5 hardware stage executed
hardware_actions_executed: true
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

TWO_LANE_30MIN_SOAK: PASS
TWO_LANE_300S_SOAK_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit`
BITSTREAM_SHA256: `32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372`
PROFILE: `profiles/p5/p5_two_lane_30min_soak.json`
PROFILE_SHA256: `7b5d43e392ed0532592823041a46d6741f83c261221b541e2bf0a5c203a07f51`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_two_lane_soak_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `7f993141f5c2c3d1d733fc8fa0441f7bc5f6b095d867b7870a049b3ed55dd6ac`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/two_lane_30min_soak`

## Counters

SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x3
ACK_LANE_MASK_READBACK: 0x3
A_SENT_FRAMES_PER_LANE: 1800
REQUESTED_FRAMES_PER_LANE: 1800
LANE0_RX_GOOD: 1800
LANE1_RX_GOOD: 1800
TOTAL_RX_GOOD: 3600
LANE0_ACK_SENT: 1800
LANE1_ACK_SENT: 1800
SOAK_SENT_FRAMES_PER_LANE: 1800
SOAK_LANE0_RX_GOOD: 1800
SOAK_LANE1_RX_GOOD: 1800
CRC_BAD: 0
PAYLOAD_MISMATCH: 0
TX_RETRY_EXHAUSTED: 0
TX_FAIL: 0
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 8
TXD_HIGH_TOTAL_CYCLES: 4352
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0

## Boundary

- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.
- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
