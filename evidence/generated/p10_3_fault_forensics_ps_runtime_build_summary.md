# P10.3F AX7020 role-bound first-fault PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A0A0 | `328d6bccb2071485ebcd04c8e32052efe8057fe1d0007bcfe1868d9d827ff775` | `330ebffd7de59df6fa6e6c20e39187885b521a73fba7d85697ed13e81a388600` |
| rotating | PASS | 0x0001A0A0 | `6a5cce6f21fa2800292c1869a009ff50c9adeaec5571a1f2a649fc8e1c1a3e7b` | `83e74bd963c23a639fd5dfb28d554e83264b79272ab1c4da4883a98216d586e0` |
