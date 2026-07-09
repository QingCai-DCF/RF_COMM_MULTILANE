# P6 Host File Transport Local Backend Summary

generated_at_utc: 2026-07-09T17:40:49+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `7a5f0ca068f983d85a6b85c95fa0d4fa3eee4ff2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: host file memory backend executed without Ethernet or hardware actions
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

P6_HOST_FILE_TRANSPORT_LOCAL_BACKEND: PASS
P6_HOST_FILE_TRANSPORT_JTAG: BLOCKED_BY_RUNTIME_ENVIRONMENT
reason: local memory backend validates file payload flow; live JTAG/AXI remains blocked without rebuilt top AXI ingress

## Transfers

| Input | Status | Match | Output | Log |
| --- | --- | --- | --- | --- |
| `evidence/hardware/p6/host_file_transport_jtag/input_payloads/small_text.bin` | PASS | true | `evidence/hardware/p6/host_file_transport_jtag/local_backend_outputs/small_text.bin` | `evidence/hardware/p6/host_file_transport_jtag/local_backend_logs/small_text.bin.log` |
| `evidence/hardware/p6/host_file_transport_jtag/input_payloads/counter_247.bin` | PASS | true | `evidence/hardware/p6/host_file_transport_jtag/local_backend_outputs/counter_247.bin` | `evidence/hardware/p6/host_file_transport_jtag/local_backend_logs/counter_247.bin.log` |
| `evidence/hardware/p6/host_file_transport_jtag/input_payloads/prbs_247.bin` | PASS | true | `evidence/hardware/p6/host_file_transport_jtag/local_backend_outputs/prbs_247.bin` | `evidence/hardware/p6/host_file_transport_jtag/local_backend_logs/prbs_247.bin.log` |
| `evidence/hardware/p6/host_file_transport_jtag/input_payloads/random_seeded_247.bin` | PASS | true | `evidence/hardware/p6/host_file_transport_jtag/local_backend_outputs/random_seeded_247.bin` | `evidence/hardware/p6/host_file_transport_jtag/local_backend_logs/random_seeded_247.bin.log` |
