# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `258b0c4a317b1791f282fdd7532381fe5d94260187771705207070f8eb033bc6` | `artifacts/p10_5/613ca80e8f551dfdc2d521cc7611b8d7777fde1b/258b0c4a317b1791f282fdd7532381fe5d94260187771705207070f8eb033bc6/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `2e30bec0f76563fbc1e54335034b9c9ebc52b1807a4c521540b68f7f83fc9003` | `artifacts/p10_5/613ca80e8f551dfdc2d521cc7611b8d7777fde1b/2e30bec0f76563fbc1e54335034b9c9ebc52b1807a4c521540b68f7f83fc9003/p10_ax7020_rotating_shutdown.bit` |
