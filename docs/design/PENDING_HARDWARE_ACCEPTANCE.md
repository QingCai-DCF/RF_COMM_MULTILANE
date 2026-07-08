# Pending Hardware Acceptance

This bootstrap does not run hardware. Hardware-related content is limited to
scripts, safe-wrapper templates, and acceptance paths.

`AB_L1` must be rerun on real hardware with a raw matrix before lane1 is treated
as reliable. Any future hardware run must use a safe wrapper, force TFDU
shutdown afterwards, and verify `SHUTDOWN_EXIT=0` or `TFDU_SHUTDOWN_PROGRAMMED`.
