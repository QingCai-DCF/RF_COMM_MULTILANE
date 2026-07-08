# Testbenches

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P2 testbench matrix:

- `tb_tfdu_lane_phy_reset_shutdown.sv`
- `tb_tfdu_lane_phy_startup_gate.sv`
- `tb_tfdu_lane_phy_txd_default_low.sv`
- `tb_tfdu_lane_phy_txd_stuck_high_guard.sv`
- `tb_tfdu_lane_phy_rx_active_low.sv`
- `tb_tfdu_lane_phy_pulse_width.sv`
- `tb_tfdu6102_behavior_model_smoke.sv`
- `tb_tfdu6102_pair_link_smoke.sv`
- `tb_tfdu_multilane_generate_smoke.sv`
- `tb_tfdu_negative_no_startup_tx.sv`
- `tb_tfdu_negative_mode_low_fir_drop.sv`
- `tb_tfdu_negative_stuck_high.sv`
- `tb_ir_4ppm_pulse_smoke.sv`

These are offline-only tests. HDL tests may be reported as
`SKIP_WITH_REASON` when no local HDL simulator is available; Python reference
tests still run.
