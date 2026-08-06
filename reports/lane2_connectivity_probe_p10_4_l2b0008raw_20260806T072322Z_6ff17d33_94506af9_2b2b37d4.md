# P10.4 F2=B0008/R2=B0023 RAW connectivity retest

- Result: `PASS`
- Run ID: `p10_4_l2b0008raw_20260806T072322Z_6ff17d33_94506af9_2b2b37d4`
- Evidence class: `RAW_PHYSICAL_ONLY`
- Pair: `F2=B0008` ↔ `R2=B0023`
- Lane mask: `0x4`
- Traffic: receive-only startup, then exactly 64 and 1024 raw pulses per direction

| Direction | Requested | Result | Physical TX | Remote raw RX | Max TX-high cycles |
|---|---:|---|---:|---:|---:|
| F2_TO_R2 | 64 | PASS | 64 | 64 | 8 |
| F2_TO_R2 | 1024 | PASS | 1024 | 1024 | 8 |
| R2_TO_F2 | 64 | PASS | 64 | 64 | 8 |
| R2_TO_F2 | 1024 | PASS | 1024 | 1024 | 8 |

- Shutdown fixed: `PASS`
- Shutdown rotating: `PASS`
- Current-run hardware authorization: `false` (consumed)

This is only a fresh static RAW physical-connectivity result. It does not replace the prior P10.4 FAIL_CLOSED evidence or prove framed data, streaming, performance, four-lane robustness, external electrical behavior, rotation, or P11.
