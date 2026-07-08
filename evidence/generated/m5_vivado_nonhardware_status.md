# M5 Vivado Non-Hardware Build Status

M5_VIVADO_BATCH_TCL_CREATED=1
M5_VIVADO_RUNNER_CREATED=1
M5_STATIC_NONHARDWARE_BUILD_CHECKS=PASS
M5_CANONICAL_TOP_CREATED=1
M5_CANONICAL_TOP_MATCHES_PINMAP_PORTS=1
M5_CANONICAL_TOP_DEFAULTS_TFDU_SHUTDOWN=1
M5_CANONICAL_TOP_DEFAULTS_TX_IDLE_LOW=1
M5_VIVADO_NONHARDWARE_BUILD=PASS
NO_HARDWARE_ACTIONS_EXECUTED=1

`scripts/vivado_nonhardware_build.tcl` creates a batch Vivado project, reads the
canonical generated XDC, selects `ir_top_new` as the top, and runs synth,
implementation, DRC, timing, and utilization reports into
`evidence/generated/vivado/`. Current PATH discovery records `VIVADO_PATH_ON_PATH=0`,
but D:\Xilinx\Vivado\2023.1\bin\vivado.bat is available and the non-hardware
batch run completed with `VIVADO_EXIT_CODE=0`.
