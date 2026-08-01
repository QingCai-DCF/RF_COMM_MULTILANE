# P10.1 hardware-performance AX7020 PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `27177f776520d3266cf7733b4a905d1eceb24a71b871797ae4dfa9f7aab9ac93` | `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8` |
| rotating | PASS | 0x0001A070 | `3f023515e87cad79ec92cbb1353a1079b43356b1656904be7dacf39148c83fee` | `d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5` |
