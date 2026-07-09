# P5 Two-Lane Scope Summary

generated_at_utc: 2026-07-09T14:50:41+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS
reason: P5 profiles and active pinmap are constrained to lanes 0 and 1
hardware_actions_executed: false
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

TWO_LANE_SCOPE_GATE: PASS
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Checks

- active pinmap lanes: `[0, 1]`
- allowed lane masks: 0x1, 0x2, 0x3
- forbidden lane masks: 0x4..0xff
- P5 profiles must not describe 4-lane or 8-lane acceptance.
