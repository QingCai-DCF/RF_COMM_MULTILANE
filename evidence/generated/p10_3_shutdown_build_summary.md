# P10.3 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `62688c0eee0b7742dff15dd11cbaf4b062e6df96735ce09f05b4469411d2d2ad` | `bcd158fe43346f0c04ea67967f94c641d7ccdf7754a4f983e4d4b57f22ba3a0b` | `artifacts/p10_3/8b9563a37728a81850223f938e0b06e5772ec039/bcd158fe43346f0c04ea67967f94c641d7ccdf7754a4f983e4d4b57f22ba3a0b/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `19a5cdf70394867852a97c6d28da2560690b2a41549ad31e48304df3b34dda4f` | `e5185fe3b69a10c2cc17a840434eea387dc1035e353fb9938dd02afd2fb60316` | `artifacts/p10_3/8b9563a37728a81850223f938e0b06e5772ec039/e5185fe3b69a10c2cc17a840434eea387dc1035e353fb9938dd02afd2fb60316/p10_ax7020_rotating_shutdown.bit` |
