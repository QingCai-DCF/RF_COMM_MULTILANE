# P10.1R AX7020 role-bound PS runtime build

- Status: `PASS`
- Hardware actions executed: `false`
- Runtime transport: JTAG/OCM mailbox plus independent local AXI DMA; Ethernet is disabled.
- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.

| Role | Build | ELF end | ELF SHA256 | BSP SHA256 |
|---|---|---|---|---|
| fixed | PASS | 0x0001A070 | `d83989db202670707a75d360312ef795ab93b3cf8fa9eae44d5eb344d57b4adb` | `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8` |
| rotating | PASS | 0x0001A070 | `9c111371ff265e600186589ba932e89a482d890a20324b28be2998c6d5212702` | `d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5` |
