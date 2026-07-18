# P8D RFAP v1 and vNext Compatibility

RFAP v1 remains byte-exact and retains P7 fragmentation/reassembly, CRC32, endpoint SHA256 comparison, abort/restart, partial-object rejection, and atomic publish. vNext is selected only by explicit session negotiation; adding L2 sequence/SACK metadata does not alter a legacy v1 frame.

## RFAP vNext header

`tools/p8d_rfap_reference.py` freezes the 48-byte little-endian layout `&lt;4sBBHIIIIQIHHQ`:

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 4 | magic `RFAP` |
| 4 | 1 | version (`2`) |
| 5 | 1 | flags |
| 6 | 2 | header bytes (`48`) |
| 8 | 4 | endpoint ID |
| 12 | 4 | session epoch |
| 16 | 4 | stream ID |
| 20 | 4 | object ID |
| 24 | 8 | fragment offset |
| 32 | 4 | fragment length |
| 36 | 2 | L2 sequence |
| 38 | 2 | path epoch |
| 40 | 8 | total length, or all ones when unknown |

The identity tuple is `(endpoint ID, session epoch, stream ID, object ID)`. Offset must equal the next expected offset; replay, gap, stale identity, terminal-state input, and a fragment above the in-flight bound fail closed.

Streaming integrity is incremental: CRC32 and SHA256 state are updated for each bounded chunk. The receiver publishes exactly once only after end marker/length, CRC32, SHA256, and destination publish all succeed. Abort, disconnect, malformed input, or integrity mismatch leaves publish count zero. A 64 MiB reference object is processed with 64 KiB chunks, demonstrating large-object support without whole-object buffering.

## Negotiation matrix

| Request/peer | Result |
|---|---|
| v1 to v1 | v1 |
| vNext to vNext-capable peer | vNext |
| vNext request to legacy peer with common v1 | explicit v1 fallback |
| vNext request with no common compatible mode | reject |
| legacy request to vNext-capable peer | v1 |
| mixed-version malformed header | reject |

Renegotiation creates a new session epoch. Reset during negotiation publishes no object and requires a new negotiation. These model results do not promote P7’s stationary 2-lane hardware scope.
