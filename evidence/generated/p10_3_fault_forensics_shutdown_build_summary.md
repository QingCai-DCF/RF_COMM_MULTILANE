# P10.3F AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `0b30535de8c115ed6887a945a4c3d5e434b6756e3f82bb44fab8970079c8d65e` | `227e41e23ae9081b8e879dc6aca6b50120332ca002029ccf44e2059dee179561` | `artifacts/p10_3_fault_forensics/5b2e9e8a22038b15308faf435163f1787054f41d/227e41e23ae9081b8e879dc6aca6b50120332ca002029ccf44e2059dee179561/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `b8a36552c8dbe14b4482672b2f253e40e8092b11a84649341414da46ed3f6aea` | `ec749d8058384ff52a2a04fe36a0fa1ce99346a87eeefe967e0f320cddb23ed2` | `artifacts/p10_3_fault_forensics/5b2e9e8a22038b15308faf435163f1787054f41d/ec749d8058384ff52a2a04fe36a0fa1ce99346a87eeefe967e0f320cddb23ed2/p10_ax7020_rotating_shutdown.bit` |
