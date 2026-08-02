# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `159eb3ca0ab04f6d3c6795896b349e5b8390b16a88ddfb5e2bcb0069fd192624` | `artifacts/p10_1r/af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c/159eb3ca0ab04f6d3c6795896b349e5b8390b16a88ddfb5e2bcb0069fd192624/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `ff5079f4876336e650bcdb93fce38ac3acf3a127fbf012ff87dbaf3cb061e1ad` | `artifacts/p10_1r/af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c/ff5079f4876336e650bcdb93fce38ac3acf3a127fbf012ff87dbaf3cb061e1ad/p10_ax7020_rotating_shutdown.bit` |
