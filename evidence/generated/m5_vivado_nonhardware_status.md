# M5 Vivado Non-Hardware Build Status

M5_VIVADO_BATCH_TCL_CREATED=1
M5_VIVADO_RUNNER_CREATED=1
M5_STATIC_NONHARDWARE_BUILD_CHECKS=PASS
M5_CANONICAL_TOP_CREATED=1
M5_CANONICAL_TOP_MATCHES_PINMAP_PORTS=1
M5_CANONICAL_TOP_DEFAULTS_TFDU_SHUTDOWN=1
M5_CANONICAL_TOP_DEFAULTS_TX_IDLE_LOW=1
M5_VIVADO_NONHARDWARE_BUILD=PENDING_TOOL
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/vivado_nonhardware_build.tcl` creates a batch Vivado project, reads the
canonical generated XDC, selects `ir_top_new` as the top, and runs synth,
implementation, DRC, timing, and utilization reports into
`evidence/generated/vivado/`. The current workstation does not expose Vivado on
PATH, so the actual Vivado run is recorded as `PENDING_TOOL` rather than PASS.
