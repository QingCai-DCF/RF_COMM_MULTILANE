# P10.1 hardware-performance AX7020 PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728` | `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8` |
| rotating | PASS | 0x0001A070 | `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0` | `d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5` |
