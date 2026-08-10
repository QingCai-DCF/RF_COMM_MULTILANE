# P10.5 Dual-Direction Capability

> Generated from `config/p10_5_dual_direction.yaml`; do not edit by hand.

- Capability: `CAP_SIMULTANEOUS_BIDIRECTIONAL_V1`
- Capability version: `1`
- Configuration SHA256: `24f200aca983191633f87d0974fb4034cbdbaa88c5c45a2742172e9744304d46`
- Modes: `LEGACY_BUNDLE_HALF_DUPLEX`, `SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL`
- Primary masks: active `0xF`, F→R `0x3`, R→F `0xC`
- Per-direction selective-repeat/SACK: `32` / `32`
- ACK: CRC-protected DATA piggyback with bounded control-only fallback
- Control-only ACK collision policy: `FIXED_PRIORITY_THEN_ROTATING_TOKEN_OR_BOUNDED_ESCAPE`; fixed uses the early slot at ACK max-delay minus `32000` cycles, while rotating responds after the fixed token plus the existing post-TX receiver-recovery guard or escapes at the unchanged ACK max-delay bound
- Autonomous runtime: mailbox command `15`, simultaneous MM2S/S2MM, up to `0x70000000` bytes per direction
- Initial launch: both endpoints activate RX with every initial TX descriptor CPU-held, publish `PRIMED`, then release only both object-0 TX chains with mailbox mask `0x80000000` within `60000` ms
- Object boundaries: every object keeps its TX descriptors CPU-held until its local RX context is active; objects after the paired first launch apply a `5000`-us receiver-lead interval and use a direction-separated, object-derived session epoch before releasing only that object's TX chain
- Safety: one active-high `GLOBAL_PERMIT` per endpoint; no direction or lane permit was added
- Compatibility: legacy half-duplex remains the reset/default mode
