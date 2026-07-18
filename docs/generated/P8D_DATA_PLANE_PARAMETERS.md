# P8D Data-Plane Parameters

> Generated from `config/p8d_data_plane.yaml`; do not edit by hand.

- Configuration: `P8D_DATA_PLANE_V1`
- Source SHA256: `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- Sequence width: `16` bits
- Descriptor: `64` bytes, `64`-byte aligned
- Scheduler: `weighted_deficit_round_robin_bytes`

| Profile | Global outstanding | SACK bits | AXI-Stream data width |
|---|---:|---:|---:|
| `Z7010_2LANE_DEV` | 32 | 32 | 32 |
| `Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE` | 64 | 64 | 64 |
| `Z7020_ROTATING_8LANE_MODEL` | 64 | 64 | 64 |

## Bounded recovery

- Maximum retries: `7`
- RTO: `32000` .. `512000` cycles
- ACK threshold / maximum delay: `8` frames / `32000` cycles
- TX/RX ring depth: `64` / `64`

## Safety boundary

P8D consumes P8B mapping/path metadata and P8C safety admission. It does not create or override `GLOBAL_PERMIT`, clear physical duty history, or claim hardware DMA/DDR acceptance.
