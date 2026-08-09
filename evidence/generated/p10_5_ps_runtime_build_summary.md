# P10.5 AX7020 split-lane dual-direction PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001E0A0 | `9027a7ddadfba53d661ba419c7dd51794e19488339e3c20d0b6026073a7038a1` | `9e68339dc17476a9c6920e78fadeeefc52d2c9c396e3dda91e6f49f81417729a` |
| rotating | PASS | 0x0001E0A0 | `7a444a3b841a6b7a6b5d684d17edcc0e0022e2cb623397b65125f8a7ea2bbf36` | `48cc070b90a89302372322e473bb01db3d5a5cbb883fdf15e41055823a4dc58c` |
