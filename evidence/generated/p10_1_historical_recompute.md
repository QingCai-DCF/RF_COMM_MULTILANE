# P10.1 historical performance recomputation

- Status: `PASS`
- Test ID: `P10_1-HISTORICAL-PERFORMANCE-RECOMPUTE`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

## Historical 5.7 kbit/s fields

| Direction | Value (bit/s) | Provenance | Class | Scaling eligible |
|---|---:|---|---|---|
| F_TO_R | 5767.861069534447 | P10-E/dma_size_1 (1 byte) | DIAGNOSTIC_MICROTRANSFER | false |
| R_TO_F | 5785.116365442897 | P10-E/dma_ring32_wrap_23 (1 byte) | DIAGNOSTIC_MICROTRANSFER | false |

The legacy arithmetic is exact; the semantic error was heterogeneous global-minimum selection. No frozen P10 file was edited.

## Machine-readable evidence

`evidence/generated/p10_1_historical_recompute.json`
