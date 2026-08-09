# P10.5 paired first-object launch barrier

## Observed failure

Two immutable hardware runs using source commit
`613ca80e8f551dfdc2d521cc7611b8d7777fde1b` reproduced the same bounded
failure in `capability_primary`:

- `p10_5_20260809T131712Z_613ca80e_c8bdbdb7_4b4c0789`
- `p10_5_20260809T132251Z_613ca80e_c8bdbdb7_4b4c0789`

In both runs, fixed completed 262144 bytes with zero retry/timeout, while
rotating completed 262144 bytes with exactly two retries and two retransmission
timeouts. CRC, SHA256, atomic commit, DMA accounting, safety checks, and final
shutdown all passed. The campaign still failed closed because P10.5 requires
zero transport timeout.

The repeated direction-specific count matches the two rotating TX lanes. The
host had staged both mailboxes but released rotating before fixed; firmware
then programmed and started each endpoint independently. The most specific
code-and-evidence explanation is loss of the first frame on each rotating TX
lane before fixed had programmed its receive object context. This is a root
cause hypothesis to be tested by the new artifact bundle, not a retroactive
reinterpretation of either failed run.

## New invariant

Command 15 now has a two-phase first-object launch:

1. The host stages and submits both complete role-bound mailboxes.
2. Each firmware instance initializes DMA, commits role masks, enables and
   arms the endpoint, queues the initial buffers, and programs both local TX
   and local RX object contexts.
3. Each endpoint publishes `P10_1_RUNTIME_PRIMED` and waits without asserting
   `START_OBJECT`.
4. The host verifies both endpoint roles, masks, epochs, safety state,
   receive-enable state, and barrier evidence.
5. Only then does the host set bit 31 of the mailbox `protocol_fault_flags`
   word on both endpoints. Firmware masks this host-only bit from every PL
   protocol-fault register write.
6. Each endpoint records release evidence, starts its local direction, and
   publishes `P10_1_RUNTIME_RUNNING`.

Failure to observe release within 60000 ms enters the existing fail-closed
stream error path, which immediately shuts down and verifies the endpoint.
Subsequent objects keep the existing pipelined behavior and do not add a
per-object optical handshake.

## Evidence contract

The append-only runtime result tail records:

- `p10_5_launch_barrier_waited`;
- `p10_5_launch_release_seen`;
- `p10_5_launch_wait_ticks_low/high`.

Every command-15 hardware PASS requires both endpoint result records to show
one barrier wait, one release, a bounded nonzero wait time, and zero transport
timeouts. XSDB additionally records `P10_5_PAIR_PRIMED` and the paired release
write skew. Old artifacts and the two failed runs remain immutable and do not
inherit any result from the repaired bundle.

## Safety boundary

The barrier is host/firmware launch sequencing only. It does not participate
in `GLOBAL_PERMIT`, SD, Mode, final Txd kill, rolling-duty enforcement, stuck
high protection, or any receive admission decision. While blocked, the PL
object is inactive and physical TX has not started. Any error, timeout, abort,
or normal stage exit retains the campaign's dual-board shutdown wrapper.
