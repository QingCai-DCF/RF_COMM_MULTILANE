# P2 Simulation Baseline Summary

generated_at_utc: 2026-07-09T11:05:45+00:00
current_commit: 4768ef76c1d9bc6042d4058f52eef5fc0da5ca01
command: python tools/run_simulation_gate.py
RESULT: FAIL
REASON: P2 simulation baseline failed
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P2_SIMULATION_BASELINE: FAIL
P1_RECHECK: NOT_RUN_STANDALONE
SIMULATOR_DETECTION: PASS
PYTHON_REFERENCE_MODEL: PASS
HDL_SIMULATION: PASS
TFDU6102_BEHAVIOR_MODEL: PASS
TFDU_LANE_PHY_TESTS: PASS
4PPM_PULSE_SMOKE: PASS
NO_HARDWARE_SCAN: FAIL

## Generated Summaries

- evidence/generated/p2_repo_intake.md
- evidence/generated/simulator_detection_summary.md
- evidence/generated/tfdu6102_reference_model_summary.md
- evidence/generated/tfdu6102_behavior_model_summary.md
- evidence/generated/tfdu_lane_phy_sim_summary.md
- evidence/generated/ir_4ppm_pulse_smoke_summary.md
- evidence/generated/simulation_gate_summary.md
- evidence/generated/p2_simulation_baseline_summary.md
- evidence/simulation/sim_results.json
- evidence/simulation/test_matrix.md

## PASS

- P2_REPO_INTAKE
- P1_EVIDENCE_REVIEW
- PYTHON_REFERENCE_MODEL
- tb_tfdu_lane_phy_reset_shutdown
- tb_tfdu_lane_phy_startup_gate
- tb_tfdu_lane_phy_txd_default_low
- tb_tfdu_lane_phy_txd_stuck_high_guard
- tb_tfdu_lane_phy_rx_active_low
- tb_tfdu_lane_phy_pulse_width
- tb_tfdu6102_behavior_model_smoke
- tb_tfdu6102_pair_link_smoke
- tb_tfdu_multilane_generate_smoke
- tb_tfdu_negative_no_startup_tx
- tb_tfdu_negative_mode_low_fir_drop
- tb_tfdu_negative_stuck_high
- tb_ir_4ppm_pulse_smoke

## FAIL

- NO_HARDWARE_SCAN: no-hardware static scan completed

## SKIP_WITH_REASON

- none

## Verification run

- `python tools/sim/detect_simulator.py`
- `python sim/scripts/run_reference_tests.py --json`
- `python tools/check_no_hardware_actions.py`

NEXT_RECOMMENDED_STAGE: P2_FIXUPS
