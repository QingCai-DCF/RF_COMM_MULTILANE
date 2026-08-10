# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `cbeb747c0cd549c0bc4785f4f877f48879db0ea45a09ef32dea1a383fda2d3ca` | `artifacts/p10_5/43cdde9f23600b2bff9a7f14f4c520876c50b070/cbeb747c0cd549c0bc4785f4f877f48879db0ea45a09ef32dea1a383fda2d3ca/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `3f4bdadbeeff05c1f0ae0025efba7de57b0875013821c6d62edddef6bfec9925` | `artifacts/p10_5/43cdde9f23600b2bff9a7f14f4c520876c50b070/3f4bdadbeeff05c1f0ae0025efba7de57b0875013821c6d62edddef6bfec9925/p10_ax7020_rotating_shutdown.bit` |
