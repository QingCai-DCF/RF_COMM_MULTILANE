# No Hardware Action Static Scan

RESULT: PASS
REASON: no unguarded active hardware actions found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Findings

- none

## Allowed / Informational

- `scripts/check_m5_static.py`: hw_server (guarded script)
- `scripts/check_no_hardware_calls.py`: connect_hw_server, hw_server, open_hw, program_hw_devices (guarded script)
- `scripts/import_rf_comm.py`: connect_hw_server, hardware manager, hw_server, open_hw, program_hw_devices (guarded script)
- `scripts/hw/run_g1_lane0_replay_safe.ps1`: jtag (guarded script)
- `scripts/hw/run_lane0_raw_matrix_safe.ps1`: jtag (guarded script)
- `tools/p1_lib.py`: /dev/tty, connect_hw_server, fpga -f, hardware manager, hw_server, jtag, open_hw, open_hw_target, program bitstream, program_hw_devices, refresh_hw_device, serial port real device, serial.serial, socket.connect, targets -set, xsdb (guarded script)
- `tools/p3_pre_hw_lib.py`: connect_hw_server, fpga -f, hardware manager, hw_server, jtag, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.serial, socket.connect, xsdb (guarded script)
- `docs/BITSTREAM_CANDIDATE_POLICY.md`: connect_hw_server, hardware manager, hw_server, open_hw, open_hw_target, program_hw_devices, refresh_hw_device (documentation mention)
- `docs/SIMULATION_GATE.md`: hardware manager (documentation mention)
- `evidence/generated/no_hardware_action_static_scan.md`: /dev/tty, connect_hw_server, fpga -f, hardware manager, hw_server, jtag, open_hw, open_hw_target, program bitstream, program_hw_devices, refresh_hw_device, serial port real device, serial.serial, socket.connect, targets -set, xsdb (generated evidence mention)
- `evidence/generated/p3_bitstream_build_audit_summary.md`: hardware manager (generated evidence mention)
- `evidence/generated/p3_no_hardware_static_scan.md`: connect_hw_server, fpga -f, hw_server, jtag, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.serial, socket.connect, xsdb (generated evidence mention)
