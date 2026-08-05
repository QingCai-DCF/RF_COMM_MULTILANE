# P10.4 AX7020 role-bound hardened PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A0A0 | `1fef9fbce356f9ed0050b7439d2df9877a2afce288350de05d4362c20e21f977` | `684b77830634e311a46cd877e826493680f1bd001e4d9b2d1c03f8a3fafbaecc` |
| rotating | PASS | 0x0001A0A0 | `137df0a51bae046e54e9636997b1cd80a686b2dc73483857fca6dff85b84c13e` | `56b7d3ac9d312c3a07d47a747d0ed4ed66b3123788baca543d5f03b049cf5dec` |
