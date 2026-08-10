# P10.5 AX7020 split-lane dual-direction PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001E0A0 | `28910e6005f1fb5b1f718c24714966617e123efacc5fde34731a71041521fbb0` | `9e68339dc17476a9c6920e78fadeeefc52d2c9c396e3dda91e6f49f81417729a` |
| rotating | PASS | 0x0001E0A0 | `f74b71c53ab21df695e2ae3439e560b0f5efcbfc865300e988a1a80118691065` | `48cc070b90a89302372322e473bb01db3d5a5cbb883fdf15e41055823a4dc58c` |
