# Simulation

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P2 simulation is an offline baseline. Files in this tree may compile or run
local digital simulations, Python reference tests, and static checks only. They
must not connect to a board, program a device, open a real serial endpoint, or
promote hardware acceptance.

The simulation baseline validates control polarity, startup gating, pulse-level
timing contracts, and lane generate behavior before any future authorized
hardware stage.
