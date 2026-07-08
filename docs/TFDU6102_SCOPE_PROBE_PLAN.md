# TFDU6102 Scope Probe Plan

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Required P4 Channels

- Txd at FPGA pin or TFDU pin
- Rxd at TFDU pin
- SD at TFDU pin
- Mode at TFDU pin
- VCC1 near TFDU
- VCC2 near TFDU
- GND reference near TFDU
- optional optical detector output

## Capture Windows

- pre-trigger idle
- startup window
- single pulse window
- pulse train window
- shutdown window
- stuck-high guard test window
- VCC2 droop during TX burst

## Artifact Names

- `evidence/hardware/scope_captures/<test_id>_<lane>_<direction>_<signal>.png`
- `evidence/hardware/scope_captures/<test_id>_<lane>_<direction>.csv`
- `evidence/hardware/logic_analyzer/<test_id>_<lane>_<direction>.vcd`
