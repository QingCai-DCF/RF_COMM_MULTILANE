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

The first paired-release remediation (`ee0332ef2ab3eb74f6380fb1b9a174d2a4af0c36`)
made that sequencing observable but still called `START_OBJECT` only after
each CPU saw its own host release. Its immutable capability run
`p10_5_20260809T155409Z_ee0332ef_3cbf6424_806af6cc` measured a 7989-us
sequential release-write skew. Rotating transmitted 18 initial frames during
that interval, before fixed had an active RX object. Both 262144-byte objects
eventually committed with clean CRC/SHA/DMA evidence, but those 18 frames
later produced exactly 18 rotating retries/timeouts. The runner correctly
failed closed and preserved both shutdown markers. Reversing host write order
would only move this failure to the other direction.

The later immutable run
`p10_5_20260809T230540Z_ec4dc468_f7fe756b_f3a5718e` proved that the paired
first-object launch was clean but exposed the same race at an internal object
boundary. Both endpoints committed four 256-KiB objects with matching
CRC32/SHA256 and clean DMA/safety/shutdown evidence. Rotating had zero retry
or timeout. Fixed recorded exactly 255 retries and 255 retransmission
timeouts, while rotating admitted exactly the required 4248 unique F-to-R
DATA frames. The 255 extra fixed attempts were not admitted while the peer's
next receive object was closed. Firmware had released all four initial TX
chains at the first host barrier and refilled later chains without deferral,
so queued MM2S data could reach a newly opened local object before the peer
had opened the matching receive context. This failed run remains immutable;
it is the direct evidence for extending RX-first/TX-deferred sequencing to
every internal object.

## New invariant

Command 15 now has a two-phase first-object launch:

1. The host stages and submits both complete role-bound mailboxes.
2. Each firmware instance initializes DMA, commits role masks, enables and
   arms the endpoint, prepares the initial buffers, queues every initial RX
   descriptor, and deliberately retains every initial TX descriptor in CPU
   ownership.
3. Firmware programs both direction contexts and asserts `START_OBJECT`.
   The RX object is now active and able to admit the peer's first frame, but
   MM2S has no hardware-owned TX descriptor and therefore cannot provide DATA
   to the PL transmitter.
4. Each endpoint records the active context and held descriptor count,
   publishes `P10_1_RUNTIME_PRIMED`, and waits.
5. The host verifies both endpoint roles, masks, epochs, safety state,
   receive-enable state, active RX object, exact held-descriptor count, zero
   released-descriptor count, and equality between RX-submitted and TX-held
   descriptor counts.
6. Only then does the host set bit 31 of the mailbox `protocol_fault_flags`
   word on both endpoints. Firmware masks this host-only bit from every PL
   protocol-fault register write.
7. Each endpoint records release evidence and submits only object 0's TX
   descriptor chain. Both peer RX objects were already active before either
   write, so host/JTAG release skew cannot discard the first DATA window.
   Firmware then publishes `P10_1_RUNTIME_RUNNING`.
8. Every later object remains autonomous. Firmware programs an object-derived,
   direction-separated session epoch, starts the local RX/TX context while
   that object's TX descriptors remain CPU-owned, applies the configured
   5000-us receiver-lead interval, rechecks the live dual context, and only
   then submits that one object's TX chain. The next object may transfer while
   the CPU verifies the previous object, but a future object's DATA is never
   prequeued into MM2S.

Failure to observe release within 60000 ms enters the existing fail-closed
stream error path, which immediately shuts down and verifies the endpoint.
Subsequent objects preserve pipelining without a host or optical per-object
handshake; the receiver lead is a bounded local firmware interval.

## Evidence contract

The append-only runtime result tail records:

- `p10_5_launch_barrier_waited`;
- `p10_5_launch_release_seen`;
- `p10_5_launch_wait_ticks_low/high`;
- `p10_5_launch_rx_object_prestarted`;
- `p10_5_launch_tx_descriptors_held`;
- `p10_5_launch_tx_descriptors_released`;
- `p10_5_launch_prestart_context_status`.

Words 224..227 additionally record:

- total initial TX descriptors held while all initial RX chains are queued;
- the configured inter-object receiver-lead interval;
- the number of deferred object TX chains actually released;
- the number of unique object sessions programmed.

Every command-15 hardware PASS requires both endpoint result records to show
one barrier wait, one release, a bounded nonzero wait time, an active dual RX
context before release, a nonzero first-object held count, exact first-object
held/released equality at completion, exact normal-run object/session/release
counts, and zero transport timeouts. XSDB additionally verifies that
`START_OBJECT` is active on both endpoints, that no TX descriptor has been
released, and that the RX-submitted count equals the separately recorded total
initial TX-held count; it records `P10_5_PAIR_PRIMED` plus paired release-write
skew. Old artifacts and all failed runs remain immutable and do not inherit
any result from the repaired bundle.

The live `P10_5_ROLE_STATUS` gate at this point is `0x1B` under mask `0x1F`:
mode active, role epoch valid, object active, and dual-direction active, with
the mutually exclusive idle bit clear.  The quiet post-object capability
readback remains a separate check and must not be reused as the launch gate.

## Safety boundary

The barrier is host/firmware/DMA launch sequencing only. It does not
participate in `GLOBAL_PERMIT`, SD, Mode, final Txd kill, rolling-duty
enforcement, stuck-high protection, or receive admission. While blocked, the
PL object and RX context are active, but the complete initial TX descriptor
queue remains CPU-owned, so application DATA cannot reach the PL scheduler.
This is a restrictive startup invariant, not an additional permit channel.
The independent hardware TX-kill and full-shutdown paths remain highest
priority. Any error, timeout, abort, or normal stage exit retains the
campaign's dual-board shutdown wrapper.
