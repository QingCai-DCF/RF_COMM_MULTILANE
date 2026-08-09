# P10.5 Dual-Direction Capability

> Generated from `config/p10_5_dual_direction.yaml`; do not edit by hand.

- Capability: `CAP_SIMULTANEOUS_BIDIRECTIONAL_V1`
- Capability version: `1`
- Configuration SHA256: `fb79523627256fb10258e13bc5bbd1e1c0fab5214b916bbbac44aeb17e5a1db6`
- Modes: `LEGACY_BUNDLE_HALF_DUPLEX`, `SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL`
- Primary masks: active `0xF`, F→R `0x3`, R→F `0xC`
- Per-direction selective-repeat/SACK: `32` / `32`
- ACK: CRC-protected DATA piggyback with bounded control-only fallback
- Autonomous runtime: mailbox command `15`, simultaneous MM2S/S2MM, up to `0x70000000` bytes per direction
- Safety: one active-high `GLOBAL_PERMIT` per endpoint; no direction or lane permit was added
- Compatibility: legacy half-duplex remains the reset/default mode
