# P6 Local Transport Implementation Summary

generated_at_utc: 2026-07-09T17:40:44+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `7a5f0ca068f983d85a6b85c95fa0d4fa3eee4ff2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: P6 implementation files are present
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

P6_LOCAL_TRANSPORT_IMPLEMENTATION: PASS
implemented P6 register-window payload RAM/mailbox, payload_len readback, payload CRC/readback, RX digest/readback, lane/ACK masks, bounded rejects, and sticky clear
PS runtime mailbox source and host no-Ethernet local transport wrapper are present

## Files

- `rtl/ir_axi_regs_new.sv` sha256=`757d0660ab463ed8da690087142cc5f00b6691d12f67afb28e0d152bcde27dd7`
- `sim/tb/tb_p6_local_transport_regs.sv` sha256=`2fb758f58abaeeecd88b1d6d1ab0ed43b70c30527453c87550a8b2362484de68`
- `software/ps_driver/ir_driver.c` sha256=`6e4ed94087bf755da043f63327ed71e48704d196900a2b5e0c6af608677ad170`
- `software/ps_driver/ir_driver.h` sha256=`ad851923e4eb4c09d78307a230a7ba3ca9b63266a388777b7f3758d9dee63453`
- `software/ps_driver/p6_runtime_mailbox.c` sha256=`89db0842d774c5fa408f6953f1b72edab8a13b3299d55f3b9c8ee9e3c430e183`
- `tools/p6_jtag_axi_transport.py` sha256=`bd8a2640863ba8441a0e4e4ee7390966188f908f774127e958723127a4341b49`
- `config/register_map/ir_axi_regs.yaml` sha256=`e7ba25cf23e1e90804b95b9f6540bcbf683247fdf94a5b701e533910f6f66fda`
- `config/register_map/generated/ir_regs.h` sha256=`b3c6e65475ace56b280fe0c15b1a0c4c37fb510246cb842d0546bbfea9241aab`
