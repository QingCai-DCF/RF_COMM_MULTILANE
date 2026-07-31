# P10.1 Dual-node performance and observability plan

Status: `OFFLINE_PLAN_ONLY`

Current-run hardware authorization: `false`. This document does not authorize JTAG, FPGA programming, PS ELF execution, UART, TFDU drive, or any other hardware action.

## Why P10.1 exists

The P10 hardware acceptance is valid for its stationary two-node/two-lane scope, but its final ~5.7 kbit/s fields are global minima from one-byte DMA diagnostics. They are not suitable for scaling. The source-backed audit is `evidence/generated/p10_goodput_measurement_audit.json` (`e24039778e5aafa8fc59ece1fc699ba33fcbe5d239ff64eea3d25e3ab7a36d14`).

## Measurement contract

The machine-readable contract is `config/performance/p10_1_measurement_contract.yaml` (`d0b01d859c9da61e8efc66e2e44ea3a82601c8b4a3caafb69b00ebb45dc76559`). It fixes four distinct metrics:

- `PHY_RAW_BPS`: configured raw lane capability; never label it application throughput.
- `FRAME_GOODPUT_BPS`: deduplicated accepted frame-payload bits divided by an explicit frame window.
- `APPLICATION_GOODPUT_BPS`: exactly-once atomically published useful bits divided by an explicit application window.
- `OBJECT_COMPLETION_BPS`: useful bits in completed atomic objects divided by the first-admit to final-publish window; also record objects/s.

Every metric record must include start/end timestamp and clock source, numerator bytes, warm-up and idle policy, host/JTAG staging inclusion, direction, lane mask, object/fragment sizes, and the raw-log path plus SHA-256. One raw log must deterministically produce both JSON and Markdown.

## Required segmented timing

Instrument host load, PS generation, CRC32, SHA-256, cache flush, descriptor submit, DMA TX, PL queue, on-air transfer, ACK/SACK, DMA RX, cache invalidate, reassembly, receive SHA-256, atomic publish, and host readback. For every segment report count, mean, p50, p95, p99, and maximum. Missing instrumentation must be `SKIP_WITH_REASON`, not zero.

## Comparison matrix

1. Mode A: local DDR/DMA.
2. Mode B: dual-board digital/no-optical path, only if the design explicitly supports it.
3. Mode C: real optical path.

Mode B is diagnostic and cannot replace Mode C. Use identical workload, build, lane mask, object sizes, integrity checks, and measurement windows across comparable modes.

## Optimization order

First correct metric semantics and add observability. Then test a target-resident multi-object pipeline rather than XSDB-serialized one-object transactions. Optimize payload generation/hash strategy, descriptor batching, ring occupancy, cache ownership, ACK aggregation, queue depth, and readback only after segmented evidence identifies the bottleneck. Do not disable CRC/SHA, exactly-once publication, SACK/retry rules, duty guards, TX kill, or shutdown behavior.

## Later optional campaigns

- P10.2: 4x4 crosstalk matrix and 1+1 concurrent full duplex.
- P10.3: larger objects and FreeRTOS characterization, if FreeRTOS is selected.

Both are hardware campaigns and require a new explicit current-run authorization with immutable artifacts and bounded safe shutdown.

## Exit criteria

- Metric windows and units reproduce exactly from raw evidence.
- The difference among raw, frame, application, object, PS-command, XSDB-wall, and full-soak throughput is explicit.
- Pipeline scaling and its bottleneck breakdown are credible.
- Integrity and TFDU safety evidence do not regress.
- No result is extrapolated to 8 lanes, rotation, or final product without direct evidence.
