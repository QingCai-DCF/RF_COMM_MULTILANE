# P3 No Hardware Static Scan

generated_at_utc: 2026-07-09T10:17:34+00:00
repo: C:\Users\user\Documents\RF_COMM_MULTILANE
HEAD: 4768ef76c1d9bc6042d4058f52eef5fc0da5ca01
RESULT: PASS
REASON: no unguarded hardware actions found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P3_NO_HARDWARE_STATIC_SCAN: PASS
- scanned files: 948
- risky files classified: 186

| Path | Hits | Classification | Reason |
| --- | --- | --- | --- |
| `plan.md` | connect_hw_server, hw_server, open_hw, program_hw_devices, stop | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `PROJECT_STATUS.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `.hardware_authorization/P4_AUTO_APPROVED.txt` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/BITSTREAM_CANDIDATE_POLICY.md` | connect_hw_server, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/HARDWARE_ACCEPTANCE_RUNBOOK.md` | stop | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/PROJECT_STATUS.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `scripts/check_m5_static.py` | hw_server | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/check_no_hardware_calls.py` | connect_hw_server, hw_server, open_hw, program_hw_devices | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `scripts/import_rf_comm.py` | connect_hw_server, hw_server, open_hw, program_hw_devices | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p1_lib.py` | JTAG, connect_hw_server, fpga -f, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.Serial, socket.connect, xsdb | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p3_pre_hw_lib.py` | /dev/mem, JTAG, connect_hw_server, current_hw_device, devmem, download_bitstream, fpga -f, hw_server, lwip live target, open_hw, open_hw_target, program_bitstream, program_hw_devices, refresh_hw_device, serial.Serial, socket.connect, xilinx hardware server, xsdb | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p4_auto_authorization.py` | JTAG, xsdb | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p4_auto_lib.py` | xsdb | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/p4_hw_execution.py` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/run_p4_auto_hardware_acceptance.py` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `tools/run_p4_hardware_acceptance.py` | JTAG | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
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
| `evidence/hardware/p4/p4_environment_capture.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4/p4_environment_capture.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4/p4_safe_idle_programming.tcl.txt` | program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/p4_auto_tool_versions.txt` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/authorization/P4_AUTO_USER_AUTHORIZATION.md` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane0_ack_retry_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane0_frame_crc_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_ack_retry_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_frame_crc_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/protocol_smoke/p4_auto_two_lane_minimal_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/raw_lane_matrix/p4_auto_raw_lane_matrix_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/raw_pulse_smoke/p4_auto_raw_pulse_smoke_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/safe_idle_direct_proxy/p4_auto_safe_idle_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/soak/p4_auto_lane0_300s_soak_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/soak/p4_auto_two_lane_300s_soak_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/hardware/p4_auto/tfdu_control_idle/p4_auto_tfdu_control_idle_programming.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/nonhardware_build_summary.md` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_tfdu_control_idle/rf_comm_nonhardware_tfdu_control_idle.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | COM[0-9], JTAG, mwr, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_tfdu_control_idle/rf_comm_nonhardware_tfdu_control_idle.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_tfdu_control_idle/rf_comm_nonhardware_tfdu_control_idle.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_tfdu_control_idle_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_safe_idle/rf_comm_nonhardware_safe_idle.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_safe_idle/rf_comm_nonhardware_safe_idle.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_safe_idle/rf_comm_nonhardware_safe_idle.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_safe_idle_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_raw_pulse/rf_comm_nonhardware_raw_pulse.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_raw_pulse/rf_comm_nonhardware_raw_pulse.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_raw_pulse/rf_comm_nonhardware_raw_pulse.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_raw_pulse_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_raw_lane_matrix/rf_comm_nonhardware_raw_lane_matrix.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_raw_lane_matrix/rf_comm_nonhardware_raw_lane_matrix.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_raw_lane_matrix/rf_comm_nonhardware_raw_lane_matrix.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_raw_lane_matrix_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_two_lane_soak/rf_comm_nonhardware_protocol_two_lane_soak.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_two_lane_soak/rf_comm_nonhardware_protocol_two_lane_soak.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_two_lane_soak/rf_comm_nonhardware_protocol_two_lane_soak.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_two_lane_soak_ila_sim_netlist.v` | JTAG, mrd, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_two_lane_minimal/rf_comm_nonhardware_protocol_two_lane_minimal.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_two_lane_minimal/rf_comm_nonhardware_protocol_two_lane_minimal.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_two_lane_minimal/rf_comm_nonhardware_protocol_two_lane_minimal.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_two_lane_minimal_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane1_ack/rf_comm_nonhardware_protocol_lane1_ack.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane1_ack/rf_comm_nonhardware_protocol_lane1_ack.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane1_ack/rf_comm_nonhardware_protocol_lane1_ack.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane1_ack_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane1/rf_comm_nonhardware_protocol_lane1.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane1/rf_comm_nonhardware_protocol_lane1.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane1/rf_comm_nonhardware_protocol_lane1.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane1_ila_sim_netlist.v` | JTAG, dow, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0_soak/rf_comm_nonhardware_protocol_lane0_soak.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0_soak/rf_comm_nonhardware_protocol_lane0_soak.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0_soak/rf_comm_nonhardware_protocol_lane0_soak.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane0_soak_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0_ack/rf_comm_nonhardware_protocol_lane0_ack.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0_ack/rf_comm_nonhardware_protocol_lane0_ack.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0_ack/rf_comm_nonhardware_protocol_lane0_ack.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane0_ack_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0/rf_comm_nonhardware_protocol_lane0.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0/rf_comm_nonhardware_protocol_lane0.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project_protocol_lane0/rf_comm_nonhardware_protocol_lane0.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane0_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project/rf_comm_nonhardware.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project/rf_comm_nonhardware.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_stub.v` | xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `evidence/generated/vivado/project/rf_comm_nonhardware.cache/ip/2023.1/5/2/52ec30c1831c373e/p4_auto_safe_idle_ila_sim_netlist.v` | JTAG, xsdb | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `docs/legacy/AGENTS.RF_COMM.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `dist/rf_comm_multilane_p4_results_20260709_000557/PROJECT_STATUS.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `dist/rf_comm_multilane_p4_results_20260709_000557/docs/PROJECT_STATUS.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `dist/rf_comm_multilane_p4_results_20260709_000557/tools/p4_hw_execution.py` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `dist/rf_comm_multilane_p4_results_20260709_000557/tools/run_p4_hardware_acceptance.py` | JTAG | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `dist/rf_comm_multilane_p4_results_20260709_000557/scripts/hw/program_tfdu_shutdown_safe.ps1` | stop | SAFE_DRY_RUN_GUARDED | script contains dry-run or authorization guard markers |
| `dist/rf_comm_multilane_p4_results_20260709_000557/scripts/legacy_safe_tools/program_tfdu_shutdown.tcl` | program_hw_devices, refresh_hw_device | SKIP_WITH_REASON | legacy/reference hardware material, not a P3 execution entrypoint |
| `dist/rf_comm_multilane_p4_results_20260709_000557/evidence/hardware/p4/p4_environment_capture.md` | JTAG | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `dist/rf_comm_multilane_p4_results_20260709_000557/evidence/hardware/p4/p4_environment_capture.tcl.txt` | JTAG, connect_hw_server, current_hw_device, hw_server, open_hw, open_hw_target | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
| `dist/rf_comm_multilane_p4_results_20260709_000557/evidence/hardware/p4/p4_safe_idle_programming.tcl.txt` | program_hw_devices, refresh_hw_device | SAFE_DOCUMENTATION_ONLY | documentation or generated evidence mention |
