# P10.5 AX7020 split-lane dual-direction PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001E0A0 | `3e50c18065a273ee6b65d368aba2717ef0d6be953f00ef7ab688e3515ab35cc7` | `9e68339dc17476a9c6920e78fadeeefc52d2c9c396e3dda91e6f49f81417729a` |
| rotating | PASS | 0x0001E0A0 | `056816efa612b3aa36a1dc7df59c8c022b0d4e16c28a11c1cee5a4ead628fd7e` | `48cc070b90a89302372322e473bb01db3d5a5cbb883fdf15e41055823a4dc58c` |
