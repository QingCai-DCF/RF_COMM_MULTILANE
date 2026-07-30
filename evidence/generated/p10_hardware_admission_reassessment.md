# P10 hardware-admission reassessment

- Result: `PASS_READY_FOR_SCOPED_P10_HARDWARE`.
- `P10-SAFETY-POWERUP-001`: `PENDING_D17_NONBLOCKING_FOR_P10_SCOPED_NO_POWER_CYCLE_RUN`; it is not a P10 blocker in the already-powered, no-intentional-power-cycle scope.
- Current P10 hardware admission: `true`.
- Current blocker: `NONE`.
- JTAG role state: `BOUND_EXPLICIT_SERIAL_TO_ROLE: AX7020-F=210249855178, AX7020-R=210512180081`.

Configured reset/fault and the two frozen shutdown builds drive `Mode=0x3`, `SD=0x3`, and `Txd=0x0`. During the ordinary configuration interval, PUDC_B-enabled pull-ups are expected to make both SD and Txd high; the TFDU6102 truth table makes SD high inhibit optical TX. This does not prove Txd-low, FPGA-unconfigured fail-low, or partial-power fail-low.

The missing external fail-low and physical final-kill properties remain `PENDING_D17`, exactly as recorded by the canonical safety contract, project state, P9 final PASS boundary, and P10 fast-track unchanged-pending scope. This reassessment neither waives those requirements nor creates a hardware/product safety PASS.

Scoped guards: no intentional power cycle, explicit serial-to-role binding before programming, role-matched shutdown images first, abort on target/rail/safe-state anomaly, and shutdown-before/on-error/after for every active stage.
