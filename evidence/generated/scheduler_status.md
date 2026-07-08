# Multilane Scheduler Status

SCHEDULER_RTL_IMPLEMENTED=1
SCHEDULER_TB_CREATED=1
SCHEDULER_STATIC_CHECKS=PASS
SCHED_DEFAULT_LANE0_ENABLED=1
SCHED_LANE1_DEFAULT_DISABLED_MARKER=1
SCHED_KNOWN_BAD_AB_L1_MARKER=1
SCHED_AB_L1_BLOCK_PRESENT=1
SCHED_ENABLE_READBACK_PRESENT=1
SCHED_STICKY_BAD_LANE_PRESENT=1
SCHED_FAULT_FALLBACK_PRESENT=1
SCHED_SELECTED_LANE_PRESENT=1
SCHED_SIM=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

`rtl/ir_multilane_scheduler.sv` now implements profile-mask latching,
lane-enable readback, known-bad AB_L1 blocking, sticky bad-lane isolation, and
fallback to the next healthy reliable lane. The dedicated simulation testbench
is included in the offline gate list; the current workstation still reports it
as `PENDING_TOOL` when no SystemVerilog simulator is available.
