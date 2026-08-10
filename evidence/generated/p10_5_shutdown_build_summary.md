# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `64144fbbccc6eb2987e5b2718c6b7a0db3e660570700017b53a4c9ecb8005e17` | `artifacts/p10_5/4254f3eaefa57eff88fc4d3e0df39740c5da0d58/64144fbbccc6eb2987e5b2718c6b7a0db3e660570700017b53a4c9ecb8005e17/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `f7d295030180ded0581b4b718ab64bd69a9103544b75179d21db5646fa218187` | `artifacts/p10_5/4254f3eaefa57eff88fc4d3e0df39740c5da0d58/f7d295030180ded0581b4b718ab64bd69a9103544b75179d21db5646fa218187/p10_ax7020_rotating_shutdown.bit` |
