# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `f5cbde1b3a0695ef3cc3aa7a3489d15b3416e98a0993f4dbb263444b6f7ad540` | `artifacts/p10_5/eefca40c115babbfc08f9c06c6bb118534641c04/f5cbde1b3a0695ef3cc3aa7a3489d15b3416e98a0993f4dbb263444b6f7ad540/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `d6eee65b31f36cd7dedea988d275421410d113b0383b4dbdb93d14283e0191b8` | `artifacts/p10_5/eefca40c115babbfc08f9c06c6bb118534641c04/d6eee65b31f36cd7dedea988d275421410d113b0383b4dbdb93d14283e0191b8/p10_ax7020_rotating_shutdown.bit` |
