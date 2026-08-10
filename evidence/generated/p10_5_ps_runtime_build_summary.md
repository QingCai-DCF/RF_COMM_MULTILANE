# P10.5 AX7020 split-lane dual-direction PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001E0A0 | `05b6b416a420568760ec02b276b6dfa5afd045c79079edf79c8a888c7611455a` | `9e68339dc17476a9c6920e78fadeeefc52d2c9c396e3dda91e6f49f81417729a` |
| rotating | PASS | 0x0001E0A0 | `a16770e195f30d9a51a8c0693e6b31cf0b340cc01817923d6fd9404793c68082` | `48cc070b90a89302372322e473bb01db3d5a5cbb883fdf15e41055823a4dc58c` |
