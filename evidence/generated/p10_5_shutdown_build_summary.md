# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `2539aafd5eb21fcb17a55cb12c7c8d0ff4fcd351a5ae2abee133a8d4d2c88723` | `artifacts/p10_5/e1f8c01ab084571627380367422f0bda2c0aed87/2539aafd5eb21fcb17a55cb12c7c8d0ff4fcd351a5ae2abee133a8d4d2c88723/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `2f303bda57710b35c1b4bcd572eff5b12943244053ceae8d36a1995e50ac5534` | `artifacts/p10_5/e1f8c01ab084571627380367422f0bda2c0aed87/2f303bda57710b35c1b4bcd572eff5b12943244053ceae8d36a1995e50ac5534/p10_ax7020_rotating_shutdown.bit` |
