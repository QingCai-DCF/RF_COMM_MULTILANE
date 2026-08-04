# P10.3F AX7020 role-bound first-fault PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A0A0 | `7ea3542ac346eb567371cd7635ebcb597f10df7b51b756e76ab57e9e03077b40` | `330ebffd7de59df6fa6e6c20e39187885b521a73fba7d85697ed13e81a388600` |
| rotating | PASS | 0x0001A0A0 | `c21f8c9c0d88783b1163d3c20c17ac49ff7b2463511abf9ddf3889f3152d1f7d` | `83e74bd963c23a639fd5dfb28d554e83264b79272ab1c4da4883a98216d586e0` |
