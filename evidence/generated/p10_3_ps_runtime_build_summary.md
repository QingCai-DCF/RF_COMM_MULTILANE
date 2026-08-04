# P10.3 AX7020 role-bound four-lane PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A0A0 | `f4c9bd6fa8ae8bbbad3a927f19759c8605c253258613d72271c8aa202e27fa3a` | `d0c57af71efe5c4a9a984a6b74334414035996fb1352f96931796f1881650cae` |
| rotating | PASS | 0x0001A0A0 | `fd2edb95306323e4c8796368d3425487994e7471b115b8543d20053f10d6f01a` | `fab469f35477b56fe25d37f0c2c4b94e648b308ea73cc75abd81483e3a1ae1e1` |
