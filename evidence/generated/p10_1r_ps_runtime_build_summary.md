# P10.1R AX7020 role-bound PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `85a7a10c8a4240c3ce860748eb887802266927edd9435ec79a676a7a7e9d44a0` | `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8` |
| rotating | PASS | 0x0001A070 | `01500cb532c4d8e296f30ff81aca31c1b836a2203ad3c2b0731751b6acabae55` | `d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5` |
