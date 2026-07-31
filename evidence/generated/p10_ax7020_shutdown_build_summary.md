# P10 AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `b09c9a51bdef26f9c3a2d16513519496f845daddea736b62a8650fab5d3212ea` | `ae8c2e603cab2e8d74e3dc635efb7e55fcbb5bb91899805be524ff4126e7e4f1` | `artifacts/p10/b09c9a51bdef26f9c3a2d16513519496f845daddea736b62a8650fab5d3212ea/ae8c2e603cab2e8d74e3dc635efb7e55fcbb5bb91899805be524ff4126e7e4f1/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ee2b2c555615b682778c0384a341e197cce5369d9fc7d92bfa8f213d78309c8b` | `5cd97ee81a288b11ce369ebd24f4ed5573ccdb52e53949685aebb6d1eb7d1d7b` | `artifacts/p10/ee2b2c555615b682778c0384a341e197cce5369d9fc7d92bfa8f213d78309c8b/5cd97ee81a288b11ce369ebd24f4ed5573ccdb52e53949685aebb6d1eb7d1d7b/p10_ax7020_rotating_shutdown.bit` |
