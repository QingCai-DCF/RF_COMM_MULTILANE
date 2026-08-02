# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `bf627696f2a51edaaa1698c293e6004b2f690b4bf7711c97e5757e1c54dcd58f` | `artifacts/p10_1r/8bb759047276e5bb9952403013d1d33cea6bba92/bf627696f2a51edaaa1698c293e6004b2f690b4bf7711c97e5757e1c54dcd58f/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `e8efaef320ce35025bf58f888921f3e70a150eb662dc9baf5777f86b3616e587` | `artifacts/p10_1r/8bb759047276e5bb9952403013d1d33cea6bba92/e8efaef320ce35025bf58f888921f3e70a150eb662dc9baf5777f86b3616e587/p10_ax7020_rotating_shutdown.bit` |
