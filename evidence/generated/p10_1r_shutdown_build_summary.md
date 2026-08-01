# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `0e8c4771bb66f46b62688bf17acd998a7efad4c4a9a3bb862acad0ef47581259` | `artifacts/p10_1r/493955d5788942ac448a9cfd99c97f0c526281fe/0e8c4771bb66f46b62688bf17acd998a7efad4c4a9a3bb862acad0ef47581259/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `00fcd7eabea623f516b0ee07cd60511087292d4481538619e82d5aa9e79bd52c` | `artifacts/p10_1r/493955d5788942ac448a9cfd99c97f0c526281fe/00fcd7eabea623f516b0ee07cd60511087292d4481538619e82d5aa9e79bd52c/p10_ax7020_rotating_shutdown.bit` |
