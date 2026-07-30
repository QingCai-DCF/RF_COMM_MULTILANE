# P10 Fast-Track Mid-Run Transition

- Timestamp UTC: `2026-07-30T08:31:51.4366135Z`
- Worktree: `C:\Users\user\Documents\RF_COMM_MULTILANE_P10`
- Branch: `p10/ax7020-dual-node-2lane`
- HEAD: `1c06dfba97f40d8a3a568832c29a7bb1ac166340`
- Superseded Goal SHA256: `5a81eeea8cf5bb0ff9d41c237a2af097f58cf71d1d208825dfb6144b5d6e23a3`
- Fast-track override source: `C:\Users\user\Downloads\P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md`
- Fast-track override SHA256: `b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603`
- Old running command: `python scripts/run_offline_gates.py --include-p8e --verify-existing-vivado --json-summary`
- Old command disposition: `TERMINATED_BY_FASTTRACK_OVERRIDE`
- Terminated process chain: `31236 -> 20024 -> 11492 -> 12612 -> 31360`
- Terminated process types: `python -> python -> python -> cmd -> vivado`
- Hardware actions attributable to the old command: `false`
- Pre-existing `hw_server` PID 36668 (started 2026-07-28) was observed and was neither started nor contacted by this transition.
- Tracked dirty paths at transition: 98

## Dirty path snapshot

```text
 M constraints/legacy_conflicts/xdc_conflict_report.md
 M evidence/generated/m1_tfdu_model_reference.json
 M evidence/generated/m1_tfdu_model_reference.md
 M evidence/generated/m2_detect_window_sweep.json
 M evidence/generated/m2_detect_window_sweep.md
 M evidence/generated/m3_crc_bad_ack_reference.json
 M evidence/generated/m3_crc_bad_ack_reference.md
 M evidence/generated/m4_ps_driver_trace.json
 M evidence/generated/m4_ps_driver_trace.md
 M evidence/generated/m6_refusal_runtime.json
 M evidence/generated/m6_refusal_runtime.md
 M evidence/generated/offline_gate_summary.json
 M evidence/generated/offline_gate_summary.md
 M evidence/generated/p8a_consistency_summary.json
 M evidence/generated/p8e_constraint_audit_summary.json
 M evidence/generated/p8e_constraint_audit_summary.md
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/build_config.tcl
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/build_markers.txt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_cdc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_check_timing.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_clock_interaction.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_exceptions.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_hold_paths.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_methodology.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_power.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_pulse_width.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_setup_paths.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_route_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_synth_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_synth_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/post_synth_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Default/vivado_stdout_stderr.log
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/build_config.tcl
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/build_markers.txt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_cdc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_check_timing.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_clock_interaction.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_exceptions.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_hold_paths.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_methodology.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_power.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_pulse_width.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_setup_paths.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_route_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_synth_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_synth_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/post_synth_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7010_2LANE_DEV_IMPLEMENTATION/Performance_Explore/vivado_stdout_stderr.log
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/build_config.tcl
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/build_markers.txt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_cdc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_check_timing.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_clock_interaction.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_exceptions.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_hold_paths.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_methodology.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_power.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_pulse_width.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_setup_paths.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_route_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_synth_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_synth_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/post_synth_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Default/vivado_stdout_stderr.log
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Performance_Explore/build_config.tcl
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Performance_Explore/post_synth_drc.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Performance_Explore/post_synth_timing_summary.rpt
 M evidence/generated/p8e_raw/build_matrix/Z7020_ROTATING_8LANE_CORE_IMPLEMENTATION/Performance_Explore/post_synth_utilization.rpt
 M evidence/generated/p8e_raw/build_matrix/build_matrix_gate.log
 M evidence/generated/p8e_raw/config/canonical_generation_verify.log
 M evidence/generated/p8e_raw/constraints/constraint_audit.json
 M evidence/generated/p8e_raw/constraints/constraint_audit.log
 M evidence/generated/p8e_raw/intake/arm_compiler_version.log
 M evidence/generated/p8e_raw/intake/vivado_version.log
 M evidence/generated/p8e_raw/simulation/dual_endpoint_reference.json
 M evidence/generated/p8e_raw/simulation/dual_endpoint_reference.log
 M evidence/generated/p8e_raw/simulation/p8e_axi_dma_adapter/run.log
 M evidence/generated/p8e_raw/simulation/p8e_cdc_reset_matrix/run.log
 M evidence/generated/p8e_raw/simulation/p8e_dual_endpoint/run.log
 M evidence/generated/p8e_raw/software/host_profile_tests.log
 M evidence/generated/p8e_raw/software/p8e_profile_z7010_2lane_dev.log
 M evidence/generated/p8e_raw/software/p8e_profile_z7020_fixed_8lane.log
 M evidence/generated/p8e_raw/software/p8e_profile_z7020_rotating_8lane.log
 M evidence/generated/p8e_repo_intake.json
 M evidence/generated/p8e_repo_intake.md
 M evidence/generated/p8e_source_manifest_summary.json
 M evidence/generated/p8e_source_manifest_summary.md
 M evidence/generated/plan_completion_audit.md
 M evidence/generated/sv_port_contracts.json
 M evidence/generated/sv_port_contracts.md
 M evidence/generated/vivado/nonhardware_build_summary.json
 M evidence/generated/vivado/nonhardware_build_summary.md
```

All listed tracked changes were generated by the interrupted offline gate. They are recorded here before targeted restoration; the pre-existing untracked old Goal is intentionally preserved.
