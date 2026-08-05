# P10.4 AX7020 dual four-lane shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on every configured lane and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `dcb9d3c37eba1de9521ca0f1c87f725d8f52e9dc02791f8f16a1136e715f6453` | `4405a72a78518b0476a7b630968ec653cea00379dfbd279a5fc363b6cafce02c` | `artifacts/p10_4/161bef2f181c41d50853ba590f19d81fa89c68b6/4405a72a78518b0476a7b630968ec653cea00379dfbd279a5fc363b6cafce02c/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `855b7c8398c35ca88f2c87bfb515332ad7c3f02d168af8eaf4f16a0c7b6e6397` | `08148643afcd064a24a1669dd6864f1851079075a1b0efc8add521bb95bd9046` | `artifacts/p10_4/161bef2f181c41d50853ba590f19d81fa89c68b6/08148643afcd064a24a1669dd6864f1851079075a1b0efc8add521bb95bd9046/p10_ax7020_rotating_shutdown.bit` |
