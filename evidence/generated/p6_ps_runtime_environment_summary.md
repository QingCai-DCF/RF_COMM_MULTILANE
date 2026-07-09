# P6 PS Runtime Environment Summary

generated_at_utc: 2026-07-09T17:40:49+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `7a5f0ca068f983d85a6b85c95fa0d4fa3eee4ff2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: BLOCKED_BY_RUNTIME_ENVIRONMENT
reason: no rebuilt-top XSA/PS7 hardware platform found outside legacy/imported evidence
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

P6_PS_RUNTIME_ENVIRONMENT: BLOCKED_BY_RUNTIME_ENVIRONMENT
reason: no rebuilt-top XSA/PS7 hardware platform found outside legacy/imported evidence
xsct_exists: true
xsdb_exists: true
runtime_source: `software/ps_driver/p6_runtime_mailbox.c` sha256=`89db0842d774c5fa408f6953f1b72edab8a13b3299d55f3b9c8ee9e3c430e183`
rebuilt_xsa_candidate_count: 0
legacy_or_imported_xsa_candidate_count: 0
syntax_only_accepted_as_pass: false

## Boundary

- Legacy/imported XSA artifacts are read-only reference inputs and are not accepted as rebuilt P6 runtime platforms.
- PS runtime PASS requires a real ELF build/run over the rebuilt top, not syntax-only compilation.
