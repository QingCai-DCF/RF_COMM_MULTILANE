# P6 PS Runtime Environment Summary

generated_at_utc: 2026-07-10T09:15:55+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: toolchain and rebuilt-top XSA candidates are present
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

P6_PS_RUNTIME_ENVIRONMENT: PASS
reason: toolchain and rebuilt-top XSA candidates are present
xsct_exists: true
xsdb_exists: true
runtime_source: `software/ps_driver/p6_runtime_mailbox.c` sha256=`b2fd8e1eb8f32658e75e4956ed51976dd6b89a82e8f730d5825f3692ad5c6749`
rebuilt_xsa_candidate_count: 11
legacy_or_imported_xsa_candidate_count: 0
syntax_only_accepted_as_pass: false

## Boundary

- Legacy/imported XSA artifacts are read-only reference inputs and are not accepted as rebuilt P6 runtime platforms.
- PS runtime PASS requires a real ELF build/run over the rebuilt top, not syntax-only compilation.
