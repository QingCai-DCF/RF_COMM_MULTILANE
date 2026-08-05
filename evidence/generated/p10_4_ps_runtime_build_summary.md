# P10.4 AX7020 role-bound hardened PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `1144c8d40ed1d19ccca0a02d711185a1980756f9a6523c03fd7ebc9f86ea4b8d` | `684b77830634e311a46cd877e826493680f1bd001e4d9b2d1c03f8a3fafbaecc` |
| rotating | PASS | 0x0001A070 | `b42a2c176cde62698838890d8976f842c4ad6c6d8674a0e6f1651a7d8037c2c5` | `56b7d3ac9d312c3a07d47a747d0ed4ed66b3123788baca543d5f03b049cf5dec` |
