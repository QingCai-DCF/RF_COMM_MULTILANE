# No Hardware Action Static Scan

RESULT: PASS
REASON: no unguarded active hardware actions found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Findings

- none

## Allowed / Informational

- `scripts/check_no_hardware_calls.py`: connect_hw_server, open_hw, program_hw_devices (guarded script)
- `scripts/import_rf_comm.py`: connect_hw_server, hardware manager, open_hw, program_hw_devices (guarded script)
- `scripts/hw/p6_jtag_axi_transactions.tcl`: program_hw_devices, refresh_hw_device (guarded script)
- `scripts/hw/p6_ps_runtime_execute.tcl`: con, dow, fpga -f, mwr, targets -set (guarded script)
- `scripts/hw/p7_hw_preflight.tcl`: connect_hw_server, open_hw, open_hw_target (guarded script)
- `scripts/hw/p7_jtag_axi_transactions.tcl`: connect_hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (guarded script)
- `scripts/hw/p7_ps_application_execute.tcl`: con, dow, fpga -f, mrd, mwr (guarded script)
- `tools/p1_lib.py`: /dev/tty, connect_hw_server, fpga -f, hardware manager, open_hw, open_hw_target, program bitstream, program_hw_devices, refresh_hw_device, serial port real device, serial.serial, socket.connect, targets -set (guarded script)
- `tools/p3_pre_hw_lib.py`: connect_hw_server, fpga -f, hardware manager, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.serial, socket.connect (guarded script)
- `tools/p4_hw_execution.py`: connect_hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (guarded script)
- `tools/p5_hw_execution.py`: connect_hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (guarded script)
- `tools/run_p4_auto_hardware_acceptance.py`: connect_hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (guarded script)
- `tools/run_p6_local_transport_no_ethernet.py`: connect_hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (guarded script)
- `tools/summarize_p7_hardware.py`: open_hw, program_hw_devices (guarded script)
- `docs/BITSTREAM_CANDIDATE_POLICY.md`: connect_hw_server, hardware manager, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (documentation mention)
- `docs/SIMULATION_GATE.md`: hardware manager (documentation mention)
- `evidence/generated/no_hardware_action_static_scan.md`: /dev/tty, connect_hw_server, fpga -f, hardware manager, open_hw, open_hw_target, program bitstream, program_hw_devices, refresh_hw_device, serial port real device, serial.serial, socket.connect, targets -set (generated evidence mention)
- `evidence/generated/p3_bitstream_build_audit_summary.md`: hardware manager (generated evidence mention)
- `evidence/generated/p3_no_hardware_static_scan.md`: connect_hw_server, fpga -f, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.serial, socket.connect (generated evidence mention)
- `evidence/generated/vivado/post_route_p6_local_transport.dcp`: con (generated evidence mention)
- `evidence/generated/vivado/post_route_protocol_lane0.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_route_protocol_lane0_ack.dcp`: con, mrd, mwr (generated evidence mention)
- `evidence/generated/vivado/post_route_protocol_lane0_soak.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_route_protocol_lane1.dcp`: dow (generated evidence mention)
- `evidence/generated/vivado/post_route_protocol_two_lane_minimal.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_route_protocol_two_lane_soak.dcp`: mwr (generated evidence mention)
- `evidence/generated/vivado/post_route_raw_lane_matrix.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_route_raw_pulse.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_route_safe_idle.dcp`: dow (generated evidence mention)
- `evidence/generated/vivado/post_route_tfdu_control_idle.dcp`: con (generated evidence mention)
- `evidence/generated/vivado/post_synth_protocol_lane0_soak.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_synth_protocol_lane1.dcp`: mwr (generated evidence mention)
- `evidence/generated/vivado/post_synth_protocol_lane1_ack.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/post_synth_protocol_two_lane_soak.dcp`: con (generated evidence mention)
- `evidence/generated/vivado/p6_jtag_candidate/post_route_p6_jtag_candidate.dcp`: dow (generated evidence mention)
- `evidence/generated/vivado/p6_jtag_candidate/post_route_physopt_p6_jtag_candidate.dcp`: con, dow (generated evidence mention)
- `evidence/generated/vivado/p6_jtag_candidate/post_synth_p6_jtag_candidate.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/project_safe_idle/rf_comm_nonhardware_safe_idle.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_safe_idle_ila.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/project_safe_idle/rf_comm_nonhardware_safe_idle.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_safe_idle_ila_sim_netlist.vhdl`: con (generated evidence mention)
- `evidence/generated/vivado/project_raw_lane_matrix/rf_comm_nonhardware_raw_lane_matrix.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_raw_lane_matrix_ila_sim_netlist.v`: dow (generated evidence mention)
- `evidence/generated/vivado/project_protocol_two_lane_minimal/rf_comm_nonhardware_protocol_two_lane_minimal.cache/ip/2023.1/a/a/aa79e133a2fcc388/dbg_hub_sim_netlist.vhdl`: mwr (generated evidence mention)
- `evidence/generated/vivado/project_protocol_lane1_ack/rf_comm_nonhardware_protocol_lane1_ack.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane1_ack_ila.dcp`: mrd (generated evidence mention)
- `evidence/generated/vivado/project_protocol_lane1/rf_comm_nonhardware_protocol_lane1.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane1_ila.dcp`: mwr (generated evidence mention)
- `evidence/generated/vivado/project_protocol_lane0_soak/rf_comm_nonhardware_protocol_lane0_soak.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane0_soak_ila.dcp`: con (generated evidence mention)
- `evidence/generated/vivado/project_protocol_lane0_soak/rf_comm_nonhardware_protocol_lane0_soak.cache/ip/2023.1/4/6/466575e241d26bca/p4_auto_protocol_lane0_soak_ila_sim_netlist.vhdl`: con (generated evidence mention)
