# P10.5 zero-credit reopen invariant

## Direct hardware observation

Immutable run
`p10_5_20260809T193616Z_33273a1a_3aa03b83_605dd1b6` used source
`33273a1a8e6fb785881fb2aa65a5fbaa3150a03c`, fixed functional bitstream
`3aa03b83993147d59f8d72a04257aae3ddbaa6a0f68143683681ae0c07822837`,
and rotating functional bitstream
`605dd1b660cfc5484c2baddd72fca8195f422093e706706c5b0e493b5fd12ffb`.
Safe-start and dual-direction capability passed, including the RX-first,
TX-deferred paired launch barrier. The first 1+1 case then failed closed after
both command-15 services reached `P10_1_RUNTIME_STATUS_DMA_COMPLETION`.

The terminal P10.5 snapshots identified a symmetric protocol stall rather
than an optical identity, CRC, DMA-setup, or TFDU safety failure:

- fixed TX/RX bytes were 116090/101268; rotating TX/RX bytes were
  109174/108184;
- both TX windows held 32 outstanding frames and both last-observed peer
  credits were zero;
- both local RX windows had drained and reported 32 free credits;
- direction-reject, role-epoch-reject, CRC, retry-exhausted, safety-fault,
  and continuous-high violations were zero;
- fixed and rotating produced 509123 and 483132 physical TX pulses on their
  selected lanes, with matching raw receive counts at the peer;
- first-fault evidence was archived and both final shutdown markers passed.

This state proves that the sender was blocked by a stale zero-credit ACK after
the receiver had already released its reorder entries to AXI.

## Root cause

The P10.5 ACK dirty flag was asserted when an RX frame entered the reorder
window, but not when an in-order delivery left that window. Delivery can
advance cumulative ACK base, shift SACK, and reopen receiver credit without a
new optical DATA acceptance. If the final advertised snapshot captured the
full-window transient (`credit=0`), both directions could drain locally while
each remote transmitter remained permanently credit-blocked.

There was a second clearing race in the control-only path: dirty state was
cleared when a queued ACK reached serializer start, even if ACK state changed
after the immutable control header had been captured.

## Corrected invariant

For a live P10.5 RX context:

1. either RX acceptance or ordered AXI delivery marks cumulative ACK state
   dirty;
2. delivery is delayed by one PL cycle before it requests a control snapshot,
   so the snapshot observes the post-delivery base/SACK/credit values;
3. a piggyback clears dirty only if no acceptance or delivery occurred on the
   capture edge;
4. a control-only ACK clears dirty when its immutable header is captured, not
   later when serialization begins; any intervening change therefore remains
   pending;
5. when peer credit is zero and no DATA can carry a piggyback, the delayed
   delivery request forces a fresh control-only ACK and reopens the peer.

The fix does not change `GLOBAL_PERMIT`, SD, Mode, final Txd kill, duty/stuck
guards, lane-role masks, object admission, or the shutdown wrapper.

## Direct regression

`tb_p10_5_dual_direction` now backpressures both AXI receive consumers until
both transmitted ACK streams advertise zero credit with all 32 reorder slots
occupied. It then releases both consumers without admitting another optical
DATA frame. PASS requires both control-only ACK counters to advance, both
transmitters to resume, 8500 bytes to commit in each direction with exact byte
equality, and `TB_P10_5_CREDIT_REOPEN=PASS`.

The focused post-fix XSIM evidence is under
`evidence/generated/p10_5_credit_reopen_xsim_v2`. Hardware acceptance remains
pending a newly frozen artifact bundle and a new current-run authorization;
the failed run above is immutable and receives no retroactive PASS.
