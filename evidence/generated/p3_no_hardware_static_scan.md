# P3 No Hardware Static Scan

generated_at_utc: 2026-07-08T14:23:30+00:00
repo: C:\Users\user\Documents\RF_COMM_MULTILANE
HEAD: c3abf1171228f52f400e6e4a3233472e1dad90bf
RESULT: PASS
REASON: no unguarded hardware actions found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P3_NO_HARDWARE_STATIC_SCAN: PASS
- scanned files: 687
- risky files classified: 116

| Path | Hits | Classification | Reason |
| --- | --- | --- | --- |
| `plan.md` | connect_hw_server, hw_server, open_hw, program_hw_devices, stop | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/BITSTREAM_CANDIDATE_POLICY.md` | connect_hw_server, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/HARDWARE_ACCEPTANCE_RUNBOOK.md` | stop | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `scripts/check_m5_static.py` | hw_server | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/check_no_hardware_calls.py` | connect_hw_server, hw_server, open_hw, program_hw_devices | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/import_rf_comm.py` | connect_hw_server, hw_server, open_hw, program_hw_devices | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p1_lib.py` | JTAG, connect_hw_server, fpga -f, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.Serial, socket.connect, xsdb | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p3_pre_hw_lib.py` | /dev/mem, JTAG, connect_hw_server, current_hw_device, devmem, download_bitstream, fpga -f, hw_server, lwip live target, open_hw, open_hw_target, program_bitstream, program_hw_devices, refresh_hw_device, serial.Serial, socket.connect, xilinx hardware server, xsdb | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `software/legacy_host_client/run_acceptance.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_host_uart_operator/README.md` | COM[0-9], JTAG, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_host_uart_operator/rf_comm_uart_operator.py` | COM[0-9], serial.Serial | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_ps_lwip_bridge/README.md` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_ps_lwip_bridge/run_on_hw.tcl` | con, dow, fpga -f, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_ps_ps_loopback/program_fpga_init_ps7.tcl` | fpga -f, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_ps_ps_loopback/README.md` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_ps_ps_loopback/run_elf_only.tcl` | con, dow, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `software/legacy_ps_ps_loopback/run_on_hw.tcl` | con, dow, fpga -f, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `sim/tb/tb_lane0_ack_only.sv` | stop | SAFE_DOCUMENTATION_ONLY | RTL or simulation source; no host hardware action entrypoint |
| `scripts/hw/program_tfdu_shutdown_safe.ps1` | stop | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/hw/run_g1_lane0_replay_safe.ps1` | COM[0-9], stop | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/hw/run_lane0_raw_matrix_safe.ps1` | COM[0-9], stop | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/legacy_safe_tools/program_tfdu_shutdown.tcl` | program_hw_devices, refresh_hw_device | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `scripts/legacy_safe_tools/run_lane0_hw_once_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `scripts/legacy_safe_tools/run_lane_remap_probe_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `scripts/legacy_safe_tools/run_p2_register_status_readonly_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `scripts/legacy_safe_tools/uart_operator_readonly_no_tx.py` | COM[0-9], serial.Serial | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/baseline_current_failure.md` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/config_diff_known_good_vs_current.md` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/import_sha256s.txt` | xsdb | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/TFDU_VFIR_Client_Array/ps7_init.tcl` | mwr | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/analyze_jtag_blocker.py` | COM[0-9], JTAG, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/audit_full_target.py` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/audit_g0_g1_targets.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/audit_plan_completion.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/audit_plan_items.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_external_reduced_4lane_bringup_plan.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_g0_lane0_artifacts.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_lane1_periodic_tx_artifacts.ps1` | JTAG, con, dow, fpga -f, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_n03_network_first_package.py` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_p0_ack_only_artifacts.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_p2_constrained_operational_artifacts.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/build_remaining_hardware_acceptance_plan.py` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/capture_2lane_ila_once.tcl` | refresh_hw_device | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/check_8lane_candidate_project_build.py` | open_hw, program_hw_devices | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/check_8lane_external_project_build.py` | open_hw, program_hw_devices | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/check_8lane_shutdown_build.py` | open_hw, program_hw_devices | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/check_hw_target.ps1` | COM[0-9], JTAG, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/check_hw_target.tcl` | connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/check_plan_readiness.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/diagnose_jtag_usb.ps1` | COM[0-9], JTAG, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/generate_evidence_lock.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/hw_check.tcl` | hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/hw_connect_utils.tcl` | connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/list_hw_debug_cores.tcl` | refresh_hw_device | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/probe_ps_uart_boot_safe.ps1` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/program_pin_static_diag.tcl` | fpga -f | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/program_tfdu_shutdown.tcl` | program_hw_devices, refresh_hw_device | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/program_tfdu_shutdown_8lane_candidate.tcl` | program_hw_devices, refresh_hw_device | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/recover_jtag_usb_soft.ps1` | COM[0-9], hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/repair_jtag_drivers_admin.ps1` | COM[0-9], hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/restore_p1_2lane_ila_baseline.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_2lane_hw_prearmed_ila_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_2lane_matrix_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_8lane_hardware_acceptance_safe.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_failed_2lane_links_safe.ps1` | COM[0-9], hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_g1_lane0_hw_smoke_safe.ps1` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_g1_segmented_smoke_regression_safe.ps1` | COM[0-9], hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_jtag_driver_recovery_then_resume.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_lane0_hw_once_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_lane0_programming_artifact_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_lane_remap_probe_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_md_p7_resume_safe.ps1` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_n03_current_state_gate.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_n03_network_first_acceptance_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_no_ethernet_network_offline_acceptance.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p0_ack_only_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p0_known_good_replay_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p0_rx_root_cause_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p1_lane_mapping_matrix_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p2_lane0_health_debug_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p2_pspl_data_exchange_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p2_register_status_readonly_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p2_remaining_hardware_sequence_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p2_uart_operator_control_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p4a_failure_counter_smoke_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p4a_txack_requal_sequence_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p5_rx_synth_combined_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p6_ir_data_roundtrip_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p7a04_tfdu_shutdown_self_echo_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p7a_rx_only_ila_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p7_02_b2a_lane0_rxonly_focus_safe.ps1` | COM[0-9], hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_p7_2lane_rebuild_matrix_safe.ps1` | COM[0-9], hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_plan_hardware_resume_safe.ps1` | COM[0-9], hw_server, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_post_g1_target_sim_gate.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_product_loop_acceptance_safe.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_project_gates.ps1` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_ps_pc_board_smoke_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_ps_pc_offline_gates.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_ps_pc_tcp_dhcp_acceptance_safe.ps1` | COM[0-9], stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_real_acceptance_sequence_safe.ps1` | COM[0-9] | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_rotating_shaft_acceptance_safe.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_single_board_2lane_loopback_acceptance.ps1` | COM[0-9], JTAG, stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/run_two_ax7010_end_to_end_acceptance_safe.ps1` | stop | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/uart_operator_readonly_no_tx.py` | COM[0-9], serial.Serial | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/uart_operator_single_board_loopback.py` | COM[0-9], JTAG, serial.Serial | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/write_jtag_recovery_checklist.py` | COM[0-9], JTAG, hw_server | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/write_plan_execution_snapshot.py` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/tools/write_simulation_evidence_report.ps1` | JTAG | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/IPs/ip_ir_array/src/bd_f066_ila_lib_0.v` | xsdb | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `legacy/RF_COMM/IPs/ip_ir_array/src/xsdbm_v3_0_0/xsdbm_v3_0_vl_rfs.v` | xsdb | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `evidence/generated/no_hardware_action_static_scan.md` | JTAG, connect_hw_server, fpga -f, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.Serial, socket.connect, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/p3_no_hardware_static_scan.md` | /dev/mem, JTAG, connect_hw_server, current_hw_device, devmem, download_bitstream, fpga -f, hw_server, lwip live target, open_hw, open_hw_target, program_bitstream, program_hw_devices, refresh_hw_device, serial.Serial, socket.connect, xilinx hardware server, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/imported/baseline_current_failure.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/imported/config_diff_known_good_vs_current.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/imported/n03_network_first/N03_real_board_handoff.md` | COM[0-9] | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/legacy/AGENTS.RF_COMM.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
