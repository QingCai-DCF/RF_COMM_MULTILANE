# P10.4 AX7020 role-bound hardened PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A0A0 | `dce91dd7172851da0ea0c6794c8eabf61f4214fddffdcb38002e1ae1404d61fb` | `684b77830634e311a46cd877e826493680f1bd001e4d9b2d1c03f8a3fafbaecc` |
| rotating | PASS | 0x0001A0A0 | `a15b4b4472070632e1c4273392ddc500bd4e389e7bc2035301a1c3e2d55984e1` | `56b7d3ac9d312c3a07d47a747d0ed4ed66b3123788baca543d5f03b049cf5dec` |
