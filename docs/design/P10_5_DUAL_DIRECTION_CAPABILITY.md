# P10.5 Dual-Direction Capability

> Generated from `config/p10_5_dual_direction.yaml`; do not edit by hand.

- Capability: `CAP_SIMULTANEOUS_BIDIRECTIONAL_V1`
- Capability version: `1`
- Configuration SHA256: `875b75fc1b6170076d2a549d12d56a6e46d01a632718cb82774dfc5991b48be3`
- Modes: `LEGACY_BUNDLE_HALF_DUPLEX`, `SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL`
- Primary masks: active `0xF`, F→R `0x3`, R→F `0xC`
- Per-direction selective-repeat/SACK: `32` / `32`
- ACK: CRC-protected DATA piggyback with bounded control-only fallback
- Autonomous runtime: mailbox command `15`, simultaneous MM2S/S2MM, up to `0x70000000` bytes per direction
- Initial launch: both endpoints activate RX with every initial TX descriptor CPU-held, publish `PRIMED`, then release both TX queues with mailbox mask `0x80000000` within `60000` ms
- Safety: one active-high `GLOBAL_PERMIT` per endpoint; no direction or lane permit was added
- Compatibility: legacy half-duplex remains the reset/default mode
