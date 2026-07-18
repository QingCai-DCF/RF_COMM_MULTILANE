# P8D L2 vNext Selective-Repeat Protocol

## Session negotiation

The two atomic session modes are `LEGACY_STOP_AND_WAIT` (version 1) and `SELECTIVE_REPEAT_VNEXT` (version 2). Negotiation exchanges protocol versions, 16-bit sequence support, maximum outstanding, SACK width, ACK aggregation, path epoch, and streaming capability. vNext requires outstanding and SACK values of at least 32 and all listed capabilities. A vNext request to a legacy peer explicitly falls back to v1 when v1 is common; otherwise it is rejected. A session never silently mixes v1 and v2 framing.

## Modular sequence rules

For 16-bit values:

```text
seq_distance(a, b) = (a - b) mod 65536
seq_before(a, b)   = 0 < seq_distance(b, a) < 32768
seq_in_window(s,b,n) = n != 0 and n < 32768 and seq_distance(s,b) < n
```

These are the only ordering rules used by RTL and the Python model. Plain unsigned less-than is not a sequence-order operation. `0xffff` followed by `0x0000` has distance one.

## Logical vNext data header

The RTL boundary carries the following protected logical fields. When serialized, multibyte scalars use little endian to match RFAP vNext and the descriptor contract. L1 CRC covers the versioned header and payload.

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 1 | protocol version (`2`) |
| 1 | 1 | frame type (`1` data) |
| 2 | 2 | header bytes (`32`) |
| 4 | 4 | session epoch |
| 8 | 2 | global sequence |
| 10 | 2 | attempt path epoch |
| 12 | 2 | payload length |
| 14 | 1 | flags |
| 15 | 1 | traffic priority |
| 16 | 4 | stream ID |
| 20 | 4 | object ID |
| 24 | 4 | fragment offset low 32 bits |
| 28 | 1 | attempt number |
| 29 | 3 | reserved, zero on transmit and ignored on receive |

Object identity and offsets wider than this L2 fragment field remain in the RFAP vNext protected header; L2 sequence identity is never derived from lane identity.

## ACK/SACK

The logical ACK begins with a 24-byte fixed portion followed by 4 or 8 bitmap bytes:

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 1 | protocol version (`2`) |
| 1 | 1 | frame type (`2` ACK/SACK) |
| 2 | 2 | total ACK header bytes |
| 4 | 4 | session epoch |
| 8 | 2 | ACK base |
| 10 | 1 | bitmap width, 32 or 64 |
| 11 | 1 | ACK reason |
| 12 | 2 | receiver credit |
| 14 | 2 | receiver path epoch, or zero if absent |
| 16 | 4 | flags |
| 20 | 4 | reserved, zero |
| 24 | 4/8 | bitmap, bit zero first |

`ack_base` is the lowest sequence not yet delivered contiguously. Bitmap bit `i` means sequence `ack_base + i` has been received. A session mismatch, width below 32, width above negotiated capability, set bits beyond the declared width, or cumulative base outside the active TX span fails closed. Duplicate ACKs are idempotent. A later cumulative ACK/SACK subsumes a lost earlier ACK.

ACK emission occurs at the first bounded trigger: frame threshold, maximum delay, low receiver credit, blocked gap, control/fault event, direction boundary, or peer request. ACK loss cannot permanently stall the TX window because every later ACK carries cumulative base and the current SACK state.

## Retry and stale-path rules

An attempt is identified by `(session epoch, sequence, attempt number, path epoch, lane)`. The frame is identified by `(session epoch, sequence)`. Only an unacknowledged frame may create a new attempt. Current and one previous path epoch are accepted by default so an already-launched valid frame can arrive after handover; older or future epochs are rejected. A session reset clears both windows and makes old data, ACKs, and ring generations stale.

Retry exhaustion, malformed ACK/SACK, gap timeout, ring corruption, and stream abort all produce bounded terminal/error outcomes; none creates an unbounded queue or retry loop.
