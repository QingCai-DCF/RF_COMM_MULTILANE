# P10.4 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `dcb9d3c37eba1de9521ca0f1c87f725d8f52e9dc02791f8f16a1136e715f6453` | `9953eb47ae60f24c822223bf768860c7509dddbc3c622406764e484b4cb3108e` | `artifacts/p10_4/9101095609adac0503201b064caaf2f5456fc183/9953eb47ae60f24c822223bf768860c7509dddbc3c622406764e484b4cb3108e/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `855b7c8398c35ca88f2c87bfb515332ad7c3f02d168af8eaf4f16a0c7b6e6397` | `74717152e1078f0efb9b68773233ecff82fcdc00993f5fdcd7908197701ed722` | `artifacts/p10_4/9101095609adac0503201b064caaf2f5456fc183/74717152e1078f0efb9b68773233ecff82fcdc00993f5fdcd7908197701ed722/p10_ax7020_rotating_shutdown.bit` |
