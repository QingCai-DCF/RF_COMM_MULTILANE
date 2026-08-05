# P10.4 connector-local ACK RX quarantine

Status: remediation candidate; fresh artifacts and hardware acceptance required.

The first P10.4 hardware campaign preserved application integrity and every TFDU safety invariant, but the final compatibility segment accumulated physical CRC rejects on the receiver adjacent to the ACK transmitter. With lane mask `0x3`, ACK lane0 exposed lane1 and produced two rotating-side rejects. With lane mask `0xC`, ACK lane2 exposed lane3 and the fixed-side counter reached 929. The earlier 8x8 matrix independently recorded raw connector-neighbour coupling, including F2-to-F3 raw edges, while accepted non-target DATA/control remained zero.

The remediation extends only the RX admission trigger. Each lane continues to quarantine itself from its own actual final physical Txd. In addition, it quarantines the other lane on the same two-module connector while that adjacent module is emitting an actual physical ACK. The source is evaluated after arm, `GLOBAL_PERMIT`, final TX kill, exact-duty, pulse-width, stuck-high and other TFDU safety gates. A scheduled or requested ACK is insufficient.

The connector domains are fixed by the as-wired AX7020 profile:

- J10: lane0/lane1 (`F0/F1` or `R0/R1`)
- J11: lane2/lane3 (`F2/F3` or `R2/R3`)

Ordinary DATA TX on the peer lane does not blank the other receiver, preserving the P10.1R lane-independence contract. An ACK on J10 does not blank J11, and an ACK on J11 does not blank J10; therefore the disjoint connector pair needed by a future 2+2 datapath remains open. The existing 4,096-cycle post-TX guard, 256-cycle idle qualification and fail-closed 131,072-cycle maximum are reused unchanged.

This is a monitor/admission-only path. It cannot assert TX, create or override `GLOBAL_PERMIT`, change SD or Mode, bypass TX kill, alter duty accounting, schedule a frame, create backpressure or participate in flow control. Blanked raw edges remain visible through the existing admission telemetry. The LED RX event remains downstream of valid-frame admission and is not driven from raw Rxd.

The old P10.4 artifact bundle and its `PARTIAL` result remain immutable. This RTL change requires new fixed and rotating bitstreams, XSA, BSP and ELF hashes, complete offline verification, a fresh current-run authorization and a fresh hardware campaign. The mandatory acceptance condition remains physical `CRC_BAD=0`; this design does not waive or reinterpret that counter.
