# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `607f6cb66c3139b9c6474eaff841fc08dafb0fe2fa6fcf6d94e6aefef6438bf0` | `artifacts/p10_5/2b5eded212a17c3b3af63100ab385a82b0c7c04c/607f6cb66c3139b9c6474eaff841fc08dafb0fe2fa6fcf6d94e6aefef6438bf0/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `f36f9e46e7af3f142e77aeafa6fb8e6197569b8eb2850ca485ff245afb35c8d6` | `artifacts/p10_5/2b5eded212a17c3b3af63100ab385a82b0c7c04c/f36f9e46e7af3f142e77aeafa6fb8e6197569b8eb2850ca485ff245afb35c8d6/p10_ax7020_rotating_shutdown.bit` |
