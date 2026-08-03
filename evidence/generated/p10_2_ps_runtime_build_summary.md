# P10.2 AX7020 role-bound four-lane PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `9e7dbb39dc21e6a44b0a0a23abbf784e67af656e625027ce2bda19f72fee5802` | `ce293deeaeec749fcddb086855f67819ff32aaf85d8433fa3861ca4da08a563b` |
| rotating | PASS | 0x0001A070 | `a987603bde262a47a86e47b4505f518f03ce49e41b63db89d5daa17dac8a4c04` | `812eac6d7c32a80dd5450bf23b5d7026e302009b4e14b403b6e5a5b75099820b` |
