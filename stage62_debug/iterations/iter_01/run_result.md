# Iteration 01 result

Result: `PLAN_GENERATION_BLOCKED_NO_HARDWARE`

The generator completed the JTAG child dry validations, then the PS functional
child dry validation failed with:

`P7 ELF allocated image end does not match the build summary OCM boundary`

No sequence plan or execution ledger was created.  No Vivado or XSDB hardware
command ran, no candidate was programmed, and no ELF was started.  Acceptance
coverage remains zero and `HARDWARE_ACCEPTANCE=PENDING_HW`.

R33 will not be overwritten or reused.  The next eligible ID is R34.
