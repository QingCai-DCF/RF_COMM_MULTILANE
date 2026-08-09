# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `94ca2ecb311e4dd06e3c0029ed176fc65584a8f88820f69b3e1339bcead3c90e` | `artifacts/p10_5/33273a1a8e6fb785881fb2aa65a5fbaa3150a03c/94ca2ecb311e4dd06e3c0029ed176fc65584a8f88820f69b3e1339bcead3c90e/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `f7112fcd2b0ed74935764db9390945623261c1c6a8c144f3e983cf1ebd8e1a26` | `artifacts/p10_5/33273a1a8e6fb785881fb2aa65a5fbaa3150a03c/f7112fcd2b0ed74935764db9390945623261c1c6a8c144f3e983cf1ebd8e1a26/p10_ax7020_rotating_shutdown.bit` |
