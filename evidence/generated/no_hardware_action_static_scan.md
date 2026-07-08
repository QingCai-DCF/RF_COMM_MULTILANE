# No Hardware Action Static Scan

RESULT: PASS
REASON: no unguarded active hardware actions found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Findings

- none

## Allowed / Informational

- `scripts/check_no_hardware_calls.py`: connect_hw_server, open_hw, program_hw_devices (guarded script)
- `scripts/import_rf_comm.py`: connect_hw_server, open_hw, program_hw_devices (guarded script)
- `tools/p1_lib.py`: connect_hw_server, fpga -f, open_hw, open_hw_target, program_hw_devices, refresh_hw_device, serial.serial, socket.connect, targets -set, xsdb (guarded script)
