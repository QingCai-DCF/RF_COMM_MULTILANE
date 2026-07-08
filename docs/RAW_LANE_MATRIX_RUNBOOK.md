# Raw Lane Matrix Runbook

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Future P4 matrix order covers every installed lane and direction:

AB_L0, BA_L0, AB_L1, BA_L1, AB_L2, BA_L2, AB_L3, BA_L3, AB_L4, BA_L4,
AB_L5, BA_L5, AB_L6, BA_L6, AB_L7, BA_L7.

For each lane/direction record TX pulse count, remote RX raw count, local idle
level, remote idle level, scope capture path, logic analyzer path, VCC2
measurement path, shutdown log path, pass/fail, and failure classification.

Failure classifications:

- NO_TX_PIN_PULSE
- TX_PIN_PULSE_BUT_NO_OPTICAL
- OPTICAL_PRESENT_BUT_NO_RXD
- RXD_PRESENT_BUT_NO_FPGA_COUNTER
- COUNTER_PRESENT_BUT_PROTOCOL_FAIL
- XDC_OR_PINMAP_MISMATCH
- POWER_OR_VCC2_DROOP
- UNKNOWN
