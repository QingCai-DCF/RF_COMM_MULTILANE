# P10.1R AX7020 role-bound PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `48cca2655cc8f6b8d76e527e914eccd4602d20ca4cc5b6130ffd672ade6d15e1` | `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8` |
| rotating | PASS | 0x0001A070 | `ed6d416e95bbbd55a134b004865ed2ff28e20ac8cad0802de76fb0ae8561c141` | `d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5` |
