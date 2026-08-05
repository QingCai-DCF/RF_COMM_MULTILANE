# P10.4 direction-switch host timing remediation

## Scope and disposition

Run `p10_4_20260805T125932Z_a32afe5b_6f915067_ace48b07` remains an immutable
`PARTIAL` run. Both endpoints reached verified shutdown. This remediation changes
only the host XSDB executor and its offline tests; it does not change the frozen
bitstreams, XSA, BSP, ELF, PHY, protocol, duty, permit, kill, or shutdown logic.

## Direct observations

- Direction-switch windows through `switch_08_f2r` passed.
- All nine completed `switch_08_r2f` commands emitted `P10_CASE_PASS` and
  `P10_3F_SAFETY_GATE_PASS`.
- The last terminal mailbox dumps were written at `14:20:45.851Z` and
  `14:20:45.900Z`. Mandatory post-terminal P10.1 result dumps completed at
  `14:20:54.315Z` and `14:20:54.344Z`.
- The window then failed the old `deadline + 500 ms` host completion check with
  `elapsed=38335 ms`; there was no frozen PL first-fault record.
- Final fixed and rotating shutdown status was `PASS`.

The executor source orders `p10_wait_pair_terminal` before mailbox and snapshot
capture. The evidence therefore identifies a host/JTAG post-terminal capture
latency event, not a data-integrity, PL-safety, or physical-TX failure.

## Remediation

The executor now:

1. records board-active elapsed time immediately after both endpoint commands
   become terminal and before evidence reads;
2. continues to perform the complete mailbox, performance, GPIO, coherent safety,
   and first-fault checks;
3. admits no new transfer after the scheduled traffic deadline;
4. records scheduled duration, host elapsed time, board-active time, and explicit
   post-terminal observation overrun separately;
5. allows at most 15,000 ms of bounded post-terminal observation latency and
   fails closed beyond that limit.

The hardware first-fault TX-kill/full-shutdown path remains independent of host
timing. A new current-run authorization is required before hardware is retried.

## Immutable evidence

- Archived evidence checkpoint: `267a625f31c2f75a0245683411b9c5919d0b46ed`
- XSDB result SHA256:
  `c9066f9cec744550a134067ea2c272667620937f118b47323761fd492be119e8`
- Direction-switch stage summary SHA256:
  `c09595089dead46c7060456da339576f923d869e6a56eb302c6eb1ea1384fdd5`
- Final orchestrator result SHA256:
  `91afa5ce922e5d83bfe7c701486b01e5b1772765aaeb1b283416f4b725801ec9`
- Run evidence manifest SHA256:
  `3142c3da8a76ba8306402172be6ace7f00a928981f45b02f7c943979cbbb8ed5`
