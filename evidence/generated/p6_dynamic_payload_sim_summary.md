# P6 Dynamic Payload Simulation Summary

generated_at_utc: 2026-07-10T09:15:54+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: dynamic payload reference simulation completed
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

P6_DYNAMIC_PAYLOAD_SIM: PASS
HARDWARE_ACCEPTANCE: PENDING_HW
positive_case_count: 480
negative_case_count: 3
P6_DYNAMIC_PAYLOAD_HDL_SIM: PASS
csv: `evidence/simulation/p6/dynamic_payload/p6_dynamic_payload_sim.csv`
hdl_run_log: `evidence/simulation/p6/dynamic_payload_engine/logs/tb_p6_dynamic_transport_engine.xsim.log`
lane_mask > 0x3 rejected before hardware TX: true

## Boundary

- This is a deterministic reference simulation of P6 payload, CRC/digest, lane-mask, and reject logic.
- It is not hardware evidence and does not by itself authorize a P6 local transport PASS.
