# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `293e0cffa19caa6f1a1b86bf7d07bb59bc5dd6a44bf0e6be449c7adfdfd0e349` | `artifacts/p10_5/dcbeb75a21b0026675dd8bb99b87a32905a28393/293e0cffa19caa6f1a1b86bf7d07bb59bc5dd6a44bf0e6be449c7adfdfd0e349/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `8cec4a0de7c7084d9ee680a665b715626551c940440767ecf5bec30ae83e4344` | `artifacts/p10_5/dcbeb75a21b0026675dd8bb99b87a32905a28393/8cec4a0de7c7084d9ee680a665b715626551c940440767ecf5bec30ae83e4344/p10_ax7020_rotating_shutdown.bit` |
