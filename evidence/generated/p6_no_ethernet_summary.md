# P6 No Ethernet Summary

generated_at_utc: 2026-07-09T16:50:11+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b863a2377f4dbb6dd70bcf8064f138739cf0d00`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: P6 Ethernet scope gate
script_hardware_actions_executed: false
source_evidence_contains_hardware_actions: false
stage_programmed_fpga: false
stage_drove_tfdu_txd: false
stage_enabled_tfdu_receiver: false
shutdown_on_exit_observed: false
product_final_acceptance: pending
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
max_lane_mask: 0x3

P6_NO_ETHERNET: PASS
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
NETWORK_CABLE_CONNECTED: false

## Checks

- P6 profiles require no network.
- P6 runner forbids Ethernet acceptance, DHCP, static-IP board link, and TCP board transport.
