# P8D DMA Descriptor and Ring Contract

P8D freezes a software-visible SG contract and a synthesizable behavioral ownership model. It does not claim real AXI DMA, DDR, HP-port, or Zynq cache-coherency acceptance.

## Descriptor v1

Descriptors are little-endian, 64-byte aligned, and exactly 64 bytes. `version_state_generation` packs version in bits 7:0, ownership state in 15:8, and generation in 31:16.

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 4 | version/state/generation |
| 4 | 4 | flags/priority/lane policy |
| 8 | 8 | buffer address |
| 16 | 4 | buffer capacity |
| 20 | 4 | requested length |
| 24 | 4 | actual length |
| 28 | 4 | stream ID |
| 32 | 4 | object ID |
| 36 | 4 | user tag |
| 40 | 4 | session epoch |
| 44 | 2 | completion status |
| 46 | 2 | error code |
| 48 | 4 | next/ring index |
| 52 | 4 | reserved zero |
| 56 | 8 | timestamp or opaque cookie |

## Ownership

```text
FREE -> CPU_PREPARED -> HW_OWNED -> HW_COMPLETED | ERROR -> CPU_RECLAIMED
CPU_PREPARED | HW_OWNED -> ABORTED -> CPU_RECLAIMED
CPU_RECLAIMED -> CPU_PREPARED (next producer wrap/generation)
```

CPU writes payload and descriptor only before transferring `CPU_PREPARED`; hardware does not reuse a descriptor until CPU reclaim. A valid hardware completion must match both index state and the current nonzero 16-bit generation. Duplicate, wrong-state, and stale-generation completions are rejected and cannot advance the CPU consumer or produce a second completion.

TX and RX use independent 64-entry rings. Each ring uses monotonic 32-bit producer, hardware-consumer, and CPU-consumer counters; the masked low bits address the power-of-two storage. Occupancy is `producer - cpu_consumer`, so equal masked indices are not ambiguous. Full state backpressures CPU preparation.

Abort/reset increments generation (skipping zero), stops hardware ownership, and converts every prepared/owned descriptor to a bounded aborted completion or deterministic reclaimed state. Old-generation completions cannot contaminate the new ring. The model reports prepared/owned leak count; acceptance requires zero after drain/reclaim.

## Cache and barrier sequence

TX:

1. CPU writes payload and descriptor.
2. CPU invokes profile cache flush callbacks for payload and descriptor.
3. CPU executes the ownership barrier callback.
4. Hardware owns/reads, then publishes completion.
5. CPU invalidates status if the profile requires it and reclaims.

RX:

1. CPU posts an empty buffer and flushes/invalidates as required.
2. CPU executes the ownership barrier callback.
3. Hardware writes payload/status and publishes completion.
4. CPU invalidates descriptor and payload, consumes, then reclaims.

The portable driver contains callback abstractions and no BSP base address. A P8E/P9 platform profile must bind them to actual cache maintenance and memory barriers before hardware use.
