# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `d5bdc3140244afe88293713fe6a8d87ca9d2352362993ae005b923d1fb61e999` | `artifacts/p10_5/997dad5c3d69e0adeec3316404389504f82a5df2/d5bdc3140244afe88293713fe6a8d87ca9d2352362993ae005b923d1fb61e999/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `f0f02b2588d5f5e0f20a7f709980cb1d2273147220287e396bda173b2369c9f5` | `artifacts/p10_5/997dad5c3d69e0adeec3316404389504f82a5df2/f0f02b2588d5f5e0f20a7f709980cb1d2273147220287e396bda173b2369c9f5/p10_ax7020_rotating_shutdown.bit` |
