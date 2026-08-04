# P10.3 first-fault forensic follow-up

## Scope

This follow-up adds reset-independent PL evidence capture and a bounded transfer staircase to the AX7020 four-lane design. It is an offline artifact change. It does not inherit any prior P10/P10.1/P10.1R/P10.3 hardware PASS and it does not authorize a hardware run.

The user excluded the manual portions of the requested investigation. Oscilloscope probes, VCC1/VCC2 measurements, current/temperature logging, photodiode measurements, physical trigger cabling, and all other manual intervention are outside this follow-up. No claim about external electrical or optical waveforms is made.

## Safety ordering

The detected TFDU stuck-high and rolling-duty faults remain connected directly to the existing hardware TX-kill path. A detected fault forces all local physical Txd outputs low and all local SD outputs high without waiting for AXI, PS firmware, XSDB, parsing, or evidence storage.

The forensic recorder latches `first_fault_hold_o` on the first capture. That signal can only add a persistent TX kill and effective full shutdown. It is not a permit, does not enable a transmitter, does not provide data-path backpressure, and does not modify lane scheduling, ARQ, payload, or DMA state.

The endpoint therefore follows this order:

1. Hardware detects a safety or terminal object fault.
2. The direct hardware path kills physical TX and enters full shutdown.
3. The recorder freezes the causal snapshot and captures eight following protocol-clock cycles.
4. XSDB reads the frozen evidence while the functional image remains shut down.
5. The host writes the SHA256 digest and archive-commit marker.
6. Only then may the independent shutdown bitstream be loaded and verified on both boards.

Failure to archive does not delay or undo the hardware TX kill. After a bounded archive attempt, safety takes priority and the independent shutdown image must still be loaded; the archive failure must be reported as evidence loss, never as PASS.

## Persistence boundary

`rtl/p10_fault_forensics.sv` intentionally has no reset input that clears capture state. AXI reset, PS reset, transport reset, a runtime soft reset, and a functional full-shutdown request do not erase a frozen snapshot or its event BRAM. Reset state itself is observed in the event stream.

This is volatile PL state. FPGA reconfiguration and loss of PL power necessarily erase it. “Reset/shutdown does not clear” therefore means resets and shutdowns within the running functional image; it cannot mean persistence across loading another bitstream. The archive tool must run before the independent shutdown image is programmed.

## Frozen snapshot schema

For a four-lane endpoint the snapshot contains 64 little-endian 32-bit words:

| Words | Meaning |
|---|---|
| 0–7 | magic, schema, dimensions, fault timestamp/cause, packed safety/control state |
| 8–15 | object, lane/raw state, TX/ACK/RX sequence, outstanding/SACK state |
| 16–23 | attempts, retries, exhaustion, timeouts, migration, byte counts, local module readiness/fault bits |
| 24–63 | ten words for each local module 0–3 |

Each module record contains physical TX count, current and maximum continuous-high cycles, current and maximum rolling-duty high cycles, duty headroom, hard-fault count, packed SD/Mode/permit/kill/fault/reset/ready/startup state, raw RX count, and target-throttle count.

`P10_FF_STATUS` reports frozen, post-tail complete, ordered snapshot/event reads complete, archive committed, clear armed, persistent hold, effective shutdown, TX kill, and current direct capture-fault state.

## Circular event BRAM

The store is implemented as eight independent 256 x 32-bit simple-dual-port
banks. Functional Vivado signoff requires physical RAMB primitives below the
forensic hierarchy; distributed-LUT RAM is not accepted as evidence that the
requested BRAM recorder was built.

The event store is 256 entries by eight words (256 bits). Entries 0–247 are a circular pre-fault history. Entries 248–255 are a fixed eight-cycle post-fault tail. The first-fault event is part of the pre-fault region and the tail records the actual transition into kill/full-shutdown.

Event records contain a timestamp, packed physical/control state, object ID, TX next/ACK-base sequence, retry count, and an event-specific tag. Tags preserve fault cause, checkpoint ID, object error, lane state, retry exhaustion, TX-burst transition, or the selected module’s physical TX count.

## Archive and clear protocol

Snapshot words and event words must be read in complete ascending order. Out-of-order reads reset the corresponding completion interlock. The host writes all eight SHA256 words only after it has created and verified the canonical raw binary and parsed JSON. Writing `0x41524348` commits the archive only when both ordered-read interlocks and the post-fault tail are complete.

Explicit in-image clear is a two-key operation: `0x46524F5A`, followed within one second by `0x434C5241`. The bounded interval is long enough for authenticated XSDB/JTAG writes. Clear is rejected unless archive commit is set, effective full shutdown and TX kill are active, all physical Txd signals are low, all SD signals are high, and the original capture condition is no longer asserted. Neither reset nor shutdown is a clear command. The default operational flow does not clear; it archives and then programs the independent shutdown bitstream.

Raw evidence consists of:

- the canonical `.bin` word stream;
- a parsed `.json` document;
- a `.sha256` file covering the binary;
- XSDB capture/commit logs and immutable run metadata.

## Staircase contract

Long-transfer admission is changed to exact 1, 4, 16, 64, and 256 KiB levels in both directions on lane mask `0xF`. A level-specific checkpoint event is written before traffic. Both directions must complete and their atomic snapshots must pass all safety, integrity, protocol, descriptor, continuous-high, and rolling-duty gates before the next size is admitted.

The 1800-second formal test may start only after the entire staircase passes. The protocol object size remains 256 KiB. After that admission gate, a board-autonomous command may contain multiple internal objects, up to 64 MiB per command. The host is not in the per-object fast path. The PL first-fault monitor remains active throughout each aggregate command and immediately forces TX kill/full shutdown on a detected fault; the host checks a coherent safety snapshot after each completed aggregate command before launching another. The maximum formal runtime remains 1800 seconds.

## Aggregate-command remediation

The immutable run `p10_3f_full_20260804T172941Z_6e8d939a_a6ecd8e6_a5491982` completed 64 MiB in both two-lane directions but measured only about 1.83 and 1.86 Mbit/s. Its host wrapper had expanded each 64-MiB transfer into 256 separate 256-KiB mailbox commands, including host re-prime, resume, dump, and verification overhead at every internal-object boundary. That run remains FAIL evidence and is not reclassified.

The corrected orchestration issues one 64-MiB board-autonomous stream command whose firmware/RTL data path still uses 256-KiB objects, 64-KiB segments, the existing selective-repeat/SACK protocol, the unchanged duty and continuous-high guards, and the unchanged single `GLOBAL_PERMIT` safety path. Timed windows use bounded 1/4/16/64-MiB aggregate commands. This changes host orchestration only; it does not weaken the per-module rolling-duty, pulse-width, permit, SD, Mode, Txd-kill, or first-fault requirements.

## Deterministic unacknowledged-frame migration evidence

The immutable run
`p10_3f_full_20260804T181517Z_f113566f_a6ecd8e6_a5491982` remains FAIL
evidence. It reached the degradation stage after the preceding stages passed,
but the lane-1 fault was applied after all frames previously scheduled on that
lane had already been acknowledged. Consequently that run could not directly
observe an unacknowledged retry migrating away from lane 1. The successful
fault-mask readback is not reclassified as migration evidence.

The next immutable run,
`p10_3f_full_20260804T191055Z_dae5fdd1_a6ecd8e6_a5491982`, also remains FAIL
evidence. Its first-ACK suppression procedure did observe a full 32-frame
window on every injected lane. However, the receiver's direction-boundary ACK
request remains asserted while turnaround is pending, so consuming the first
drop token allowed another cumulative ACK immediately. Lane 1 was acknowledged
before the lane-unavailable write took effect and therefore finished with zero
retry migrations. That run's successful stages, failed degradation result,
raw observations, and verified dual-board shutdown are preserved without
reclassification.

The second remediation keeps the functional bitstream and all safety paths
unchanged and deliberately suppresses no ACK. Each diagnostic command starts
with the target lane as its only sender lane, applies the existing bounded
CRC-corruption diagnostic to its first physical DATA attempts, and uses a
case-local high scheduler weight for that target. The receiver is returned to
all-lanes-available before traffic. After receiver priming but before
publishing the sender command, XSDB captures coherent sender and receiver
baselines for target scheduling, target physical TX, target CRC rejection,
physical good-ACK count, drop count, and migration count. Immediately after
launch it requires direct evidence of all of the following:

- between one and 32 outstanding frames;
- positive target-lane scheduling and physical-TX deltas from the pre-launch
  baseline;
- a positive target-lane receiver CRC-bad delta, directly proving rejection of
  a physical target-lane DATA frame;
- unchanged TX ACK base equal to the command's initial sequence;
- zero dropped ACKs; and
- zero migrations before fault injection.

XSDB then atomically replaces the sender's target-only availability state with
the single target-lane unavailable bit, reads it back, and immediately re-reads
TX ACK base. The post-write ACK base must still equal the initial sequence.
The CRC-rejection delta and the two ACK-base observations directly prove that
a current-object target-lane physical transmission was unacknowledged when the
fault took effect, rather than relying on cumulative historical counters or
wall-clock timing. The first timed-out retry can use one of the three remaining
healthy lanes. Acceptance still requires successful object completion, all
integrity and safety gates, and a non-zero terminal migration count. The
target-only start, controlled CRC fault, and target weighting are confined to
these migration diagnostics and do not alter normal scheduler fairness vectors.

## Immutable CRC-migration run and evaluator boundary

The immutable run
`p10_3f_full_20260804T200335Z_e77e3ad4_a6ecd8e6_a5491982` remains FAIL
evidence and is not reclassified. Its XSDB degradation stage returned PASS and
directly observed 32 outstanding frames on every target lane, a target-lane CRC
rejection delta of three on every target lane, unchanged ACK base zero before
and immediately after each fault write, zero dropped ACKs, zero prior
migrations, exact fault-mask readback, and terminal retry-migration counts of
3, 3, 4, and 11 for lanes 0 through 3 respectively. Target-lane scheduled-frame
deltas were 13, 19, 13, and 10; target physical-TX deltas were 11489, 18841,
12581, and 9128. These are current-object observations rather than historical
counter inference.

The host evaluator nevertheless failed that run because it added each
injected case's target-only setup mask (`0xE`, `0xD`, `0xB`, `0x7`) to the
standalone static-degrade matrix. The standalone matrix is independently
defined by unavailable masks `0x1`, `0x2`, `0x4`, `0x8`, `0x3`, and `0x7`;
injection setup masks are not additional static-matrix cases. The corrected
classifier excludes every case with a nonzero `injectmask` from that static
inventory while retaining all direct migration checks unchanged.

The failed run ended with `SHUTDOWN_FIXED=PASS`,
`SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, and
`SHUTDOWN_EXIT=0`. The host-only classifier correction does not inherit or
promote the prior run's partial results. A new immutable host bundle,
current-run authorization, complete campaign, evidence manifest, and verified
dual-board shutdown are still required for acceptance.

## Immutable lane-3 host-race run

The immutable run
`p10_3f_full_20260804T204115Z_b77883df_a6ecd8e6_a5491982` also remains FAIL
evidence and is not reclassified. It completed every stage through the static
mask matrix. Direct in-flight migration cases for lanes 0, 1, and 2 completed,
and each captured a target-lane physical transmission, receiver CRC rejection,
unchanged initial ACK base, zero dropped ACKs, and zero prior migrations before
the host wrote the lane-unavailable mask. In the lane-3 case the same trigger
precondition was observed (`outstanding=3`, target scheduled delta `23`, target
physical-TX delta `23006`, target CRC-bad delta `3`, ACK base `0`, and zero prior
migrations), but the cumulative ACK base advanced after the observation and
before XSDB could complete and verify the mask write. The stage therefore
failed closed with `P10 ACK base advanced before lane-fault write was verified`;
lane 3 and its recovery case were not published as complete.

The run's frozen forensic archives and all earlier stage evidence remain
immutable. The final independent shutdown reported `SHUTDOWN_FIXED=PASS` and
`SHUTDOWN_ROTATING=PASS`. These partial results are not inherited by a new
artifact bundle or used to claim current hardware acceptance.

## PL-atomic retry-migration trigger

The remediation removes host latency from the target-to-healthy transition.
Protocol fault flag bit 16 requests the validation-only atomic diagnostic and
bits 17:18 select the target lane; bit 4 must also request bad CRC, bits 3:0
must be clear, the target must be selected and externally available, and any
invalid combination makes object start fail closed. The sender initially makes
only the target lane internally eligible. When the deliberately CRC-bad target
DATA frame reaches the final accepted `serializer_done` event, the same PL
clock clears target-only eligibility and marks that target unavailable. Any
externally supplied unavailable mask is always ORed with this internal mask and
can never be overridden.

The transition simultaneously freezes the target mask, frame sequence,
cumulative ACK base, outstanding count, total attempt count, target physical
Txd pulse count, trigger count, prior migration count, and target scheduler
count. Registers `P9_AUTO_MIGRATION_STATUS` through
`P9_AUTO_MIGRATION_TARGET_SCHEDULED_COUNT` expose that evidence. The host no
longer writes the lane-fault mask for this command; it only reads the frozen PL
event and the receiver's independent target-lane CRC-bad counter, then requires
successful completion with a nonzero terminal retry-migration count. The
diagnostic evidence survives a functional shutdown, but an explicit inactive
counter clear or a new object may reset it. It is separate from the
first-fault snapshot, whose reset/shutdown persistence and archive-before-clear
contract are unchanged.

This diagnostic can only restrict scheduler eligibility. It cannot create or
raise `GLOBAL_PERMIT`, endpoint arm, lane permit, PHY readiness, duty headroom,
frame admission, or a physical TX request, and it cannot bypass SD, Mode,
continuous-high, rolling-duty, one-hot, TX-kill, or first-fault full-shutdown
logic. Because the RTL, register map, firmware, and hardware scripts changed,
the old bitstreams and every prior hardware result remain bound only to their
old hashes. A new immutable bitstream/XSA/BSP/ELF bundle, complete offline
gates, current-run authorization, full hardware campaign, and verified
dual-board shutdown are required.

## Evidence limits

The PL counters and event recorder can show what the implemented digital logic requested and what its internal safety monitors observed. They are not a substitute for an oscilloscope, rail-current measurement, module temperature measurement, or optical detector. Because the user excluded those manual measurements, this follow-up cannot independently prove actual pin voltage, optical pulse energy, rail droop, current, or temperature.
