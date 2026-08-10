# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `9b4c0ce6c9bc64c9d2118d346b3dbbb4a21c964228600631a143fdd896d6a2d3` | `artifacts/p10_5/a2f7148efc3643a096f59f0a7730e3bcd7adb486/9b4c0ce6c9bc64c9d2118d346b3dbbb4a21c964228600631a143fdd896d6a2d3/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `2f19f0533705ad4b8bd3ada6d2d4ae72c88a0c43e428346d0a32e4633c78f133` | `artifacts/p10_5/a2f7148efc3643a096f59f0a7730e3bcd7adb486/2f19f0533705ad4b8bd3ada6d2d4ae72c88a0c43e428346d0a32e4633c78f133/p10_ax7020_rotating_shutdown.bit` |
