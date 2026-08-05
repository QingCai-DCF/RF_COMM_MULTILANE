# P10.3F AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `0b30535de8c115ed6887a945a4c3d5e434b6756e3f82bb44fab8970079c8d65e` | `df394f8a5d4eb68613749df78af43dab7705e87b3cbf091db8f69dd33cce251c` | `artifacts/p10_3_fault_forensics/7fc3a7cb03f9ee19793403f9f1deaef139b11d7d/df394f8a5d4eb68613749df78af43dab7705e87b3cbf091db8f69dd33cce251c/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `b8a36552c8dbe14b4482672b2f253e40e8092b11a84649341414da46ed3f6aea` | `1fc058e1b83f5ef9d0a4a37090515301559c9e81f218b4de218577542d8fefa0` | `artifacts/p10_3_fault_forensics/7fc3a7cb03f9ee19793403f9f1deaef139b11d7d/1fc058e1b83f5ef9d0a4a37090515301559c9e81f218b4de218577542d8fefa0/p10_ax7020_rotating_shutdown.bit` |
