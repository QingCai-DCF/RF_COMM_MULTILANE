# P10.1 reset-recovery rebootstrap remediation

`P10_1-HW-RESET-RECOVERY-REBOOTSTRAP-REMEDIATION: PASS`

This is an offline orchestration-remediation result, not a hardware acceptance result. No bitstream, XSA, BSP, ELF, runtime tuning value, or acceptance threshold changed.

## Direct evidence and diagnosis

The immutable faults run `p10_1_hw_20260801T040257Z_bfff4836_1585d1ad_9ad4f85f` passed `dma_reset_sender_f_to_r_64m`: both endpoints recorded the expected abort, reset/reclaim activity, zero commit, and safe final state. Its immediate clean successor, `post_dma_reset_clean_f_to_r_64m`, accepted and committed zero bytes. Fixed terminated with P10.1 status `260` and error detail `0x50090004` (TX retry exhaustion); rotating terminated with status `259` (DMA completion failure). Both final shutdown checks passed.

The direct boundary is important: the reset fault was observed and handled, while the post-reset clean transfer was not. The evidence supports the inference that the two independent services can remain in different transport epochs after reset-class recovery. It does not support blaming the TFDU wiring or replacing the frozen FPGA/software artifacts.

Abort-at-25-percent and abort-at-75-percent already passed their clean successors without reboot, so abort-only flags are deliberately excluded from this remediation.

## Remediation

After a successful expected-recovery snapshot for `DMA_RESET_SENDER` (bit 18), `PL_RESET` (bit 19), or `DMA_RESET_RECEIVER` (bit 24), the XSDB orchestrator now:

1. preserves the already-captured expected-recovery dumps;
2. requests shutdown before each endpoint reboot;
3. reboots fixed and rotating PS services and redownloads their unchanged, role-bound frozen ELFs;
4. waits for both service-ready markers;
5. verifies both role-specific PL identities and safe shutdown state;
6. admits the immutable clean successor only after `P10_1_RESET_RECOVERY_REBOOT_PASS`.

The former unconditional CPU resume path is skipped after this rebootstrap. Bits 16 and 17 (abort-only vectors) keep the existing resume behavior.

## Offline validation

- P10.1 runner tests: 18/18 PASS.
- P10.1 finalizer tests: 10/10 PASS.
- Python compile: PASS.
- XSDB Tcl parse through the argument guard: PASS.
- `git diff --check`: PASS.
- Hardware actions during remediation: false.
- Current-run hardware authorization: false.

The next admissible step is a new faults-only current-run authorization followed by a shutdown-before hardware retry. No faults-stage or broader P10.1 hardware PASS is claimed by this document.

Machine-readable evidence: `evidence/generated/p10_1_hw_reset_recovery_rebootstrap_remediation.json`.
