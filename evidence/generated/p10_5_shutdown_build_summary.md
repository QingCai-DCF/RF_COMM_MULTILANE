# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `51ba96fad87fbc7878972c6624c1e4ae951494c5b2b594fba06b54af6919424a` | `artifacts/p10_5/ee0332ef2ab3eb74f6380fb1b9a174d2a4af0c36/51ba96fad87fbc7878972c6624c1e4ae951494c5b2b594fba06b54af6919424a/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `bf543fd40595eca03b796f375b1647c0759aba2768dad6edf5dbe24677854c7d` | `artifacts/p10_5/ee0332ef2ab3eb74f6380fb1b9a174d2a4af0c36/bf543fd40595eca03b796f375b1647c0759aba2768dad6edf5dbe24677854c7d/p10_ax7020_rotating_shutdown.bit` |
