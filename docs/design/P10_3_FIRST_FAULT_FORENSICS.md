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

The 1800-second formal test may start only after the entire staircase passes. It uses at most one 256 KiB autonomous command at a time, keeps the protocol object size at 256 KiB, and checks each completed command before launching another. The maximum formal runtime remains 1800 seconds.

## Evidence limits

The PL counters and event recorder can show what the implemented digital logic requested and what its internal safety monitors observed. They are not a substitute for an oscilloscope, rail-current measurement, module temperature measurement, or optical detector. Because the user excluded those manual measurements, this follow-up cannot independently prove actual pin voltage, optical pulse energy, rail droop, current, or temperature.
