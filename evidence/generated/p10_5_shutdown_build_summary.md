# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `97df12e496b5f40eeea69ca9a11468909287e7fda60e65d21e3e67a521c39514` | `artifacts/p10_5/e3693553673a6a9b1053172fd1ab4b2d6eb1024d/97df12e496b5f40eeea69ca9a11468909287e7fda60e65d21e3e67a521c39514/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `c733d7f4d0f375fe5ff17fb22d1e253221d9b97b4a4f7d63ad4d0ce4fa02ff60` | `artifacts/p10_5/e3693553673a6a9b1053172fd1ab4b2d6eb1024d/c733d7f4d0f375fe5ff17fb22d1e253221d9b97b4a4f7d63ad4d0ce4fa02ff60/p10_ax7020_rotating_shutdown.bit` |
