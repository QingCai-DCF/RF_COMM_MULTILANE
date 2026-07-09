# P5 Protocol Metrics Summary

generated_at_utc: 2026-07-09T15:42:46+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS_WITH_NOTES
reason: P5 protocol metrics extracted from P5 hardware evidence
hardware_actions_executed: false
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P5_PROTOCOL_METRICS: PASS_WITH_NOTES
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
METRIC_SOURCE_COUNT: 9
LATENCY_COUNTER_STATUS: SEE_JSON
THROUGHPUT_COUNTER_STATUS: SEE_JSON

## Totals

- frames_sent: 2300
- frames_rx_good: 4000
- ack_seen: 4000
- crc_bad: 0
- payload_mismatch: 0
- retry_count: 0
- retry_exhausted: 0
- tx_fail: 0
- txd_high_total_cycles: 193664
- txd_high_consecutive_max_cycles: 48
- duty_violation_count: 0

## Boundary

- This script only summarizes fresh P5 evidence under `evidence/hardware/p5/`.
- P4 evidence is not promoted to P5 protocol metric PASS.
