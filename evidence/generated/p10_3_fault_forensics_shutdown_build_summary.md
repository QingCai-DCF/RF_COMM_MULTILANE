# P10.3F AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `0b30535de8c115ed6887a945a4c3d5e434b6756e3f82bb44fab8970079c8d65e` | `f19329cff2fc2ef01f657ffeab8d84f865ea5a3a20978c522d9d58b0c32a745d` | `artifacts/p10_3_fault_forensics/21f159e3fdb250d1a25e9f521e104d6240d9caae/f19329cff2fc2ef01f657ffeab8d84f865ea5a3a20978c522d9d58b0c32a745d/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `b8a36552c8dbe14b4482672b2f253e40e8092b11a84649341414da46ed3f6aea` | `91c047f498095e17adf429f60aaa2d4a34459f2e70e902873a2c1b6a188492c9` | `artifacts/p10_3_fault_forensics/21f159e3fdb250d1a25e9f521e104d6240d9caae/91c047f498095e17adf429f60aaa2d4a34459f2e70e902873a2c1b6a188492c9/p10_ax7020_rotating_shutdown.bit` |
