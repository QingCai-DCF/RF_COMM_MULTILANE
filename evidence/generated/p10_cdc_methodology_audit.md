# P10 CDC, methodology, and bus-skew audit

Scoped result: `PASS_WITH_DOCUMENTED_VENDOR_WARNINGS_AND_EXTERNAL_IO_GAP`.

| Role | CDC-3 info | CDC-15 warning | Unsafe CDC | LUTAR-1 | PDRC-190 | TIMING-9 | TIMING-18 | Minimum bus-skew slack (ns) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed | 68 | 74 | 0 | 3 | 32 | 1 | 6 | 9.346 |
| rotating | 68 | 74 | 0 | 3 | 32 | 1 | 6 | 9.069 |

- Every CDC-15 detail is inside the generated AXI-Stream clock converter's XPM asynchronous FIFO; no non-vendor CDC-15 or critical/error CDC was found.
- The three LUTAR-1 warnings per role are confined to the generated HP0 AXI4-to-AXI3 interconnect. No endpoint-local LUT async-reset warning remains.
- The 32 PDRC-190 warnings per role are confined to generated AXI DMA register synchronization placement.
- TIMING-9 is bounded by the detailed CDC audit and positive routed bus-skew results.
- TIMING-18 remains open for six external TFDU ports per role. This is an explicit external-I/O timing gap and does not authorize hardware.
- Hardware actions executed: `false`; hardware admission: `false`.
