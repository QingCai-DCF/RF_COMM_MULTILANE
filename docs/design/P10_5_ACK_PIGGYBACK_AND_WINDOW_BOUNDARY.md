# P10.5 ACK piggyback and receive-window boundary remediation

## Immutable failed observation

Run `p10_5_20260810T005649Z_4254f3ea_0465f6da_35edea20` used source
`4254f3eaefa57eff88fc4d3e0df39740c5da0d58`. Its simultaneous 1 MiB
capability object committed with matching CRC and SHA-256 in both directions,
but failed the unweakened transport gate:

- fixed reported 48 TX timeouts/retries and rotating reported 159;
- retry exhaustion, application CRC/SHA mismatch, descriptor leak, direction
  rejection, role-epoch rejection, and frozen safety faults were all zero;
- control-only ACK counts were 2919 fixed and 2826 rotating, while DATA
  piggybacks were only 705 and 730;
- the four active optical paths reported exact peer raw-pulse correspondence;
  this is direct evidence against an unknown physical-open explanation for
  this run, but it is not external electrical or optical metrology;
- both boards completed verified shutdown.

The failed run and artifacts remain immutable. No PASS is inherited by this
remediation.

## Root causes

Three coupled RTL defects were exposed.

1. A successful DATA piggyback did not consume aggregation events that were
   already represented by its live cumulative ACK/SACK/credit snapshot. Those
   stale events regenerated redundant control-only ACKs and repeatedly
   competed with the opposite-direction DATA carrier.
2. Every ordered fragment delivery forced a control event, even when reverse
   application DATA was available to carry the updated snapshot. This created
   thousands of control-only frames instead of using bounded fallback.
3. At the circular 32-frame receive-window boundary, the copy coordinator
   classified a pending sequence against the pre-edge base while the output
   backend retired that base on the same edge. Sequence `base+32` could skip
   payload copy as a future frame, then become admissible one cycle later.
   Metadata could therefore refer to the previous payload occupying the same
   modulo-32 BRAM slot. The credit-reopen regression exposed the exact first
   reuse at byte `32 * 247 = 7904`.

## Corrected invariants

- A DATA piggyback consumes all earlier aggregation events and retains only a
  receive/control event occurring on the same edge.
- Ordered delivery marks cumulative ACK state dirty. A zero-to-nonzero credit
  transition or duplicate requiring re-ACK forces fallback; other changes
  prefer the next reverse DATA piggyback. The shared dirty-age timer starts at
  the first uncarried state change and forces control-only fallback at the
  configured 64,000-cycle bound.
- TX allocation requires both occupancy headroom and
  `tx_next_sequence - tx_ack_base < WINDOW_SIZE`; a transiently free modulo
  slot cannot expand the sequence span beyond the advertised window.
- RX copy classification uses the base that includes a simultaneous delivery
  retirement. An in-window frame is never submitted L1-valid unless its
  payload was actually copied into the reorder store. Invalid-session, old,
  or still-future frames remain observable to the selective-repeat classifier
  without gaining admission.

The first implementation expressed that same-edge retirement as
`effective_base = base + 1` before each modular subtraction. Routed evidence
at source `2b5eded212a17c3b3af63100ab385a82b0c7c04c` showed that this cascaded
two 16-bit carry chains into the receive-copy FSM: fixed WNS was `-1.551 ns`
and rotating WNS was `-1.834 ns`. The failed routed reports and the already
successful shutdown artifacts remain immutable evidence.

The timing remediation preserves the boundary semantics without the extra
adder. A registered `RXC_CLASSIFY` stage separates pending-lane selection from
window admission, and a boundary predicate handles the only changed cases:
when the base retires on the same edge, distance zero is the retired entry and
distance `WINDOW_SIZE` is newly admissible. The copied-payload fail-closed
check remains authoritative. Focused `tb_p10_5_control_only_ack` regression
again crosses the first modulo-32 slot reuse with exact byte equality before a
new routed build is admitted.

These changes are monitoring/control-plane and bounded-window corrections.
They do not alter the single `GLOBAL_PERMIT`, SD/Mode, final Txd kill, exact
sliding-duty guard, stuck-high guard, lane-role masks, module wiring, or
shutdown wrapper.

## Mandatory regression

- `tb_ir_selective_repeat_tx` observes the reclaim-before-base-advance
  interval and requires allocation to remain blocked until the cumulative
  base moves.
- `tb_ir_sack_ack_aggregation` requires a piggyback to consume old events and
  preserve a same-edge event.
- `tb_p10_5_control_only_ack` includes simultaneous dual-direction DMA,
  control-only fallback, and the 8500-byte credit-reopen case crossing the
  modulo-32 payload-store boundary with exact byte equality.

Passing simulation only qualifies a new build candidate. New fixed/rotating
bitstreams, XSA, BSP, and ELF must be frozen by SHA-256 and must complete the
full hardware campaign with `transport timeout=0` before P10.5 can pass.
