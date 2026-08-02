# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `6ca0c42b93cdac8785a89948cfa14bc8c366d7a514394bd4a8dd9ae3becb3fdf` | `artifacts/p10_1r/cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d/6ca0c42b93cdac8785a89948cfa14bc8c366d7a514394bd4a8dd9ae3becb3fdf/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `66da73c6310887d6617ccb010f9804bb879aad0fe781e952ba713e31232fc6c6` | `artifacts/p10_1r/cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d/66da73c6310887d6617ccb010f9804bb879aad0fe781e952ba713e31232fc6c6/p10_ax7020_rotating_shutdown.bit` |
