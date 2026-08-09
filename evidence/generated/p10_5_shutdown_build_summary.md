# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `3b9dcde246dd736e212631c1d7a4e205293278c5de663beb903e09fdf282f455` | `artifacts/p10_5/c8241bb6dac852752c7eba70c2a1584aa9700059/3b9dcde246dd736e212631c1d7a4e205293278c5de663beb903e09fdf282f455/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `510b613b49de792f09060073c18f264eeb87e6b158431505857fc199fa5c59ba` | `artifacts/p10_5/c8241bb6dac852752c7eba70c2a1584aa9700059/510b613b49de792f09060073c18f264eeb87e6b158431505857fc199fa5c59ba/p10_ax7020_rotating_shutdown.bit` |
