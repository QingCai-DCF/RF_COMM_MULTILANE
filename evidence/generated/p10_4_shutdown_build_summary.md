# P10.4 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `dcb9d3c37eba1de9521ca0f1c87f725d8f52e9dc02791f8f16a1136e715f6453` | `7550b0edf6c98802eb4c4413d3d699f3db671411b7b9b02a36a661509ed632ee` | `artifacts/p10_4/6c7418e630d07be54e01d51ba05d90d6ceac3990/7550b0edf6c98802eb4c4413d3d699f3db671411b7b9b02a36a661509ed632ee/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `855b7c8398c35ca88f2c87bfb515332ad7c3f02d168af8eaf4f16a0c7b6e6397` | `300a70c4c584b4489b87e9127225698315a6abc20bba0f9217da667eb6a642fe` | `artifacts/p10_4/6c7418e630d07be54e01d51ba05d90d6ceac3990/300a70c4c584b4489b87e9127225698315a6abc20bba0f9217da667eb6a642fe/p10_ax7020_rotating_shutdown.bit` |
