# P10.3 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `62688c0eee0b7742dff15dd11cbaf4b062e6df96735ce09f05b4469411d2d2ad` | `027159d3b028aa164ed25858c868b70bc014514c0f220af731c82470cbcafc28` | `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/027159d3b028aa164ed25858c868b70bc014514c0f220af731c82470cbcafc28/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `19a5cdf70394867852a97c6d28da2560690b2a41549ad31e48304df3b34dda4f` | `204d79b7f01fc6b755316c011d09df958996c0ee9628b68492b842ff28e2847d` | `artifacts/p10_3/d4eef729e91c60fc7a72fa68c95fcd4a569fcffc/204d79b7f01fc6b755316c011d09df958996c0ee9628b68492b842ff28e2847d/p10_ax7020_rotating_shutdown.bit` |
