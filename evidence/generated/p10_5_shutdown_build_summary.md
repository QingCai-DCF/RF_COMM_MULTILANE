# P10.5 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `e4a4e7f4c9ec1f81458ed37899a7a4139fad6621b3bc7de883b73af3beaafcff` | `b01f1813989960310d56d19d17cbfc31d7af296ae40e55c8bbaeedcfd9d48da3` | `artifacts/p10_5/ec4dc468a217e0e8db7b0c5c08b3d0ff3a59662d/b01f1813989960310d56d19d17cbfc31d7af296ae40e55c8bbaeedcfd9d48da3/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `7925fb089e5f7868717d28607b6de7e368c52d1fb67fcf29b1dd3ae887988d9a` | `8ee61e157ac38679517138d1980910d8681511bacc8e4b6e83ccf730e08347b1` | `artifacts/p10_5/ec4dc468a217e0e8db7b0c5c08b3d0ff3a59662d/8ee61e157ac38679517138d1980910d8681511bacc8e4b6e83ccf730e08347b1/p10_ax7020_rotating_shutdown.bit` |
