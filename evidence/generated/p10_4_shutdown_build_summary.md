# P10.4 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `dcb9d3c37eba1de9521ca0f1c87f725d8f52e9dc02791f8f16a1136e715f6453` | `730d850ae68ec8acb7a0d46b65d3f3c596a296d6ed059c9ab5b8ae6be96a03a3` | `artifacts/p10_4/a32afe5bf744892b39325ac640a1bfaa2b5c6cf2/730d850ae68ec8acb7a0d46b65d3f3c596a296d6ed059c9ab5b8ae6be96a03a3/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `855b7c8398c35ca88f2c87bfb515332ad7c3f02d168af8eaf4f16a0c7b6e6397` | `b63b0e128aa7d6dcfc5d3e58a164529c7259b252d9bd26330e9657596ae342d8` | `artifacts/p10_4/a32afe5bf744892b39325ac640a1bfaa2b5c6cf2/b63b0e128aa7d6dcfc5d3e58a164529c7259b252d9bd26330e9657596ae342d8/p10_ax7020_rotating_shutdown.bit` |
