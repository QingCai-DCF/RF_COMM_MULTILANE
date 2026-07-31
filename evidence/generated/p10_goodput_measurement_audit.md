# P10 goodput measurement audit

Audit status: `PASS` (the audit completed; this is not a new hardware-performance PASS).

## Finding

The two ~5.7 kbit/s fields are mathematically reproducible, but they are not campaign application goodput. The finalizer takes the minimum over every command-3 row in all stages. The minima are one-byte P10-E DMA/ring diagnostics:

- F→R: `5767.861070` bit/s from `P10-E/dma_size_1`.
- R→F: `5785.116365` bit/s from `P10-E/dma_ring32_wrap_23`.

There is no bit/byte or timer-frequency error in those two calculations. The semantic problem is aggregation and labeling: the numerator may be encoded bytes, the denominator is one sender PS command, and the result excludes host/JTAG staging and the full 30-minute window.

## Recomputed useful-throughput views

- P10-I useful PS-command range: `642062.003` to `851742.381` bit/s.
- P10-I useful XSDB-case wall-time range: `140034.188` to `464536.937` bit/s.
- P10-J full 1800.003 s useful throughput: `656014.267` bit/s aggregate, `328007.133` bit/s per direction.

These are different measurement windows and must not be compared as if they were the same metric. P10 launched one object at a time through XSDB, including per-object receiver priming and mailbox dumps; it did not demonstrate a saturated multi-object pipeline.

## Decision

- P10 scoped hardware acceptance remains `PASS`.
- Current final goodput fields are not eligible for 8-lane or final-product projection.
- P10.1 must establish exact metric contracts, segmented timing, and a pipeline benchmark before any scaling claim.
- No hardware action was executed for this audit.
