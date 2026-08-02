# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `1ec78139732b4f792af6847719b3935e93d387e7864d4434fe190d4dadae0588` | `artifacts/p10_1r/e38b0772f02c898ebe9b53f6ac3c1bda06a4210c/1ec78139732b4f792af6847719b3935e93d387e7864d4434fe190d4dadae0588/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `74309bce36973df55db39c9a2c1f425385d8c654fc68770602037c39296b394e` | `artifacts/p10_1r/e38b0772f02c898ebe9b53f6ac3c1bda06a4210c/74309bce36973df55db39c9a2c1f425385d8c654fc68770602037c39296b394e/p10_ax7020_rotating_shutdown.bit` |
