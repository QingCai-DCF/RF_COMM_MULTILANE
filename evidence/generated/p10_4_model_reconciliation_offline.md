# P10.4 offline performance model

- Status: `PASS`
- Hardware actions executed: `false`
- Measured reconciliation: `PENDING_CURRENT_ARTIFACT_HARDWARE`

| Metric | Ceiling (bit/s) | Payload bytes | Meaning |
|---|---:|---:|---|
| `PHY_RAW_BPS` | 16000000.000 | 0 | configured 4PPM raw bit capability before framing, duty, ACK, or retry |
| `FRAME_GOODPUT_BPS` | 9409523.810 | 247 | deduplicated accepted L1 payload bits over the modeled bundle cycle |
| `RFAP_USEFUL_BPS` | 8190476.190 | 215 | useful RFAP bytes before retry and DMA/PS overlap efficiency |
| `APPLICATION_GOODPUT_BPS` | 9361539.943 | 247 | integrity-verified remotely committed command-object bytes |
| `HOST_ORCHESTRATED_BPS` | 9361539.943 | 247 | physical upper bound only; host connect/load/dump overhead can only reduce it |

The 8 Mbit/s retention target is model-feasible. The 9.0 and 9.6 Mbit/s targets are nonblocking and are not made feasible by weakening duty, guard, ACK/SACK, retry, or integrity assumptions.
