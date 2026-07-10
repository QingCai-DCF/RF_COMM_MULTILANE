# P7 Application Protocol v1

P7 adds a transport-neutral object layer above the unchanged P6 physical and
frame transport. P6 still accepts one payload of 1 through 247 bytes. Every P7
fragment is a normal P6 payload containing a fixed 32-byte RFAP header followed
by at most 215 object bytes.

Byte order is little-endian. The header layout is:

| Offset | Size | Field | Rule |
| ---: | ---: | --- | --- |
| 0 | 4 | magic | ASCII RFAP |
| 4 | 1 | version | 1 |
| 5 | 1 | flags | FIRST=1, LAST=2, RETRANSMIT=4, CONTROL=8 |
| 6 | 2 | header_len | 32 |
| 8 | 4 | session_epoch | Application session, independent of the P6 session |
| 12 | 4 | object_id | Unique inside a session epoch |
| 16 | 4 | total_length | Complete object length |
| 20 | 2 | fragment_index | Zero based |
| 22 | 2 | fragment_count | max(1, ceil(total_length / 215)) |
| 24 | 2 | chunk_length | 0 through 215 |
| 26 | 2 | reserved | Must be zero |
| 28 | 4 | object_crc32 | CRC32 of the complete object |

An empty object is one FIRST+LAST header-only fragment. It is still a 32-byte
P6 payload; P6 is never asked to send a zero-byte frame.

## Validation and completion

The v1 receiver is bounded and strict-order. It accepts an identical duplicate
idempotently, rejects a duplicate with different data, and rejects a fragment
that arrives ahead of the next expected index. All fragments in an object must
keep the same epoch, object ID, total length, fragment count and object CRC32.

An object becomes COMPLETE only after every fragment is present, the summed
chunk length equals total_length, and whole-object CRC32 matches. Host file
output is written to a partial file and atomically replaced only after the host
SHA256 of input and output also matches. Abort, stale session, missing fragment,
CRC failure, or SHA mismatch can never publish a completed file.

## Lane policies

| Policy | Per-fragment P6 lane mask | Meaning |
| --- | --- | --- |
| LANE0_ONLY | 0x1 | lane0 only |
| LANE1_ONLY | 0x2 | lane1 only |
| STRIPE_ROUND_ROBIN | alternating 0x1, 0x2 | application striping |
| REPLICATE_0X3 | 0x3 | P6 replication; not striping |

Software lane-unavailable injection occurs before submission to P6. Fallback
keeps the same epoch, object ID, fragment index, header and chunk, changes only
the allowed lane mask, and is bounded. It is scheduler evidence, not an optical
fault claim.

## Integrity boundary

P6 frame CRC and P6 payload CRC protect each encoded RFAP fragment. The RFAP
object_crc32 protects the complete reassembled object. SHA256 is compared at
the host and PS application-service boundary. P6 RX_DIGEST is a CRC32 value and
must not be reported as SHA256.

## PS retry and latency semantics

The PS service submits each RFAP fragment to P6 exactly once. P6 retains
ownership of its bounded physical/frame ARQ. The descriptor `max_retries`
field is therefore a fail-closed **per-fragment P6 retry acceptance cap**, not
permission for the P7 service to replay a safety-significant failed transfer.
A P6 result whose reported retry count exceeds that cap fails the object and
enters shutdown. `fragment_attempts` counts P7 submissions and must equal the
generated fragment count for a completed object; `p6_retry_count` is reported
separately and is never silently folded into that field.

PS object latency starts immediately after a valid descriptor enters RUNNING,
before input CRC32/SHA256, and ends after reassembly plus output CRC32/SHA256.
Fragment latency uses PS global-timer ticks only around the individual P6
transport operation. Host JTAG/DAP timing is reported separately and is never
presented as optical-only latency.

## Scope

RFAP v1 uses no Ethernet, DHCP, TCP, UDP, hardware motion, or lane mask above
0x3. A disabled TCP adapter may implement the backend interface, but it must not
connect, bind, or listen and cannot contribute PASS evidence.
