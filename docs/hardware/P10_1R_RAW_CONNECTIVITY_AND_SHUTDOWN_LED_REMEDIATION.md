# P10.1R raw connectivity and shutdown-LED remediation

## Scope

This change is limited to two defects found during the P10.1R stationary
two-board investigation:

1. the raw connectivity stimulus used a five-clock Txd pulse; and
2. the standalone shutdown image omitted the four AX7020 active-low PL LED
   outputs.

The user reported replacing the fixed-side F1 TFDU small board before the next
hardware run. Codex does not infer a serial number or marking for that module
and will not move, exchange, or rewire any board or module during the run.

## Raw stimulus repair

The transport clock is 64 MHz, so one clock is 15.625 ns. The old raw pulse was
five clocks, or 78.125 ns. Normal 4PPM transmission uses an eight-clock optical
chip, or 125 ns. The remediated raw generator therefore uses exactly eight
clocks per requested pulse.

This is not a safety bypass. A raw request still traverses endpoint arm,
direction routing, `GLOBAL_PERMIT`/TX-kill, per-module one-hot, continuous-high,
stuck-high, exact sliding-duty and final physical Txd accounting. Focused XSIM
requires every one of the four directions to show a final physical Txd maximum
of exactly eight clocks. The 125 ns pulse is well below the project limit of
1 us, and the hardware echo sweep retains a spacing of 1024 clocks, giving a
requested high fraction of 8/1024 = 0.78125% before any additional guard can
suppress a request.

The hardware result remains `RAW_PHYSICAL_ONLY`: 1000 received raw observations
in a direction establish pulse-level optical connectivity only. They do not
establish valid-frame, CRC, streaming, performance, crosstalk, or P10.1R Goal
acceptance.

## Shutdown LED repair

AX7020 LED1 through LED4 are Bank 35, 3.3 V, active-low outputs on M14, M15,
K16 and J16. The role XDC files already constrained these pins, but the previous
standalone shutdown top did not expose the LED port. The new shutdown top drives
`pl_activity_led_n_o=4'b1111`, which is the all-off vector, alongside
`Mode=2'b11`, `SD=2'b11` and `Txd=2'b00`.

XSIM and routed-build markers prove the configured design intent. JTAG
programming success plus shutdown markers prove that the content-addressed
shutdown bitstream was loaded. Neither is direct electrical measurement of the
LED pins; physical visual confirmation remains a user-observable follow-up.

The complete exact-source offline replay is stored separately under
`evidence/generated/p10_1r_raw_led_full_offline_regression/`; it does not
overwrite the earlier P10.1R replay evidence.

## Current hardware boundary

After a clean source commit, complete offline regression, dual-role functional
and shutdown implementation, XSA/BSP/ELF build and exact SHA256 freeze, the
current run is authorized only for the `echo_tail` stage. That stage executes
1000 raw samples in each order: F1 to R1, R1 to F1, F0 to R0 and R0 to F0. It
does not execute framed objects, performance, streaming, crosstalk, rotation,
Ethernet, module exchange or rewiring. Shutdown is required before, after, on
error, timeout, interrupt, normal exit and in the final safety handler.
