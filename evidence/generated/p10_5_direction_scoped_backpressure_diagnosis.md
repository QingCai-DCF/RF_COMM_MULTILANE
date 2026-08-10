# P10.5 direction-scoped DMA backpressure diagnosis

- Status: `DIAGNOSED_HOST_HARNESS_FALSE_NEGATIVE`
- Failed run: `p10_5_20260810T101302Z_e1f8c01a_4015142e_79607d01`
- Immutable evidence checkpoint: `e22aadb4571920640c2c1ebde679ec210ed24a03`
- Final run status: `FAIL`; this record does not promote it to PASS.
- Both final shutdown markers: `PASS`

Firmware injects DMA TX backpressure only on the endpoint whose local TX
direction matches the selected fault target.  Direct evidence is symmetric:

- F_TO_R: fixed delta `3196992`; rotating delta `0`.
- R_TO_F: rotating delta `3196994`; fixed delta `0`.
- The diagnostic arm bit is clear after both injections.

All Tcl fault cases, including both abort directions, passed.  The host runner
nevertheless required the unaffected peer to report a positive local injected
stall delta, producing two false-negative errors.  The remediation validates
positive evidence on the injected sender and zero/leak-free evidence on the
unaffected peer.

The remediated runner was replayed offline against all 20 fault pairs (40
endpoint results) from the immutable failed run.  The post-fix error list was
empty.  This replay validates the host predicate only; it is not hardware PASS.

No RTL, protocol, firmware, bitstream, XSA, BSP or ELF input changes.  A new
harness freeze and authorization are still required, followed by a complete
campaign rerun; no prior hardware stage result is inherited.
