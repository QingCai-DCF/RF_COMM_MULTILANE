# Pending Hardware Acceptance

This bootstrap does not run hardware. Hardware-related content is limited to
scripts, safe-wrapper templates, and acceptance paths.

`AB_L1` must be rerun on real hardware with a raw matrix before lane1 is treated
as reliable. Any future hardware run must use a safe wrapper, force TFDU
shutdown afterwards, and verify `SHUTDOWN_EXIT=0` or `TFDU_SHUTDOWN_PROGRAMMED`.

M6 created the hardware-preparation wrappers under `scripts/hw/` only. They
default to `REFUSED_NO_ALLOW_HARDWARE`, print the active profile SHA256, and
write hash manifests before any authorized run path. The shutdown wrapper still
requires a shutdown bitstream at `shutdown_bitstream/tfdu_shutdown_j10_j11.bit`
or an authorized pre-run build of that artifact.
