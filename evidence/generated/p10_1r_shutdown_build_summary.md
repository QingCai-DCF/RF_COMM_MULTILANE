# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes and `PL_LED_N=0xF` (all four active-low LEDs off).
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `be03ff7553f32984fecfba7b73450a7d5e997f1d8a15b4394faeb7d1dc390410` | `0d0f4fbf2b35518094aec58728461f505c225a5f1aef647d3917259564fc279a` | `artifacts/p10_1r/39df17155ce82e38366fbdac00c79584f0fe1afa/0d0f4fbf2b35518094aec58728461f505c225a5f1aef647d3917259564fc279a/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `556d3b86cbf1526a1c9cc6dcd22b6c47dbc7579c370119949e40baafecaf142e` | `a0abfef77d566a6baaf51242d95cae679e63cb9e34f423595f3faae7bcfbac27` | `artifacts/p10_1r/39df17155ce82e38366fbdac00c79584f0fe1afa/a0abfef77d566a6baaf51242d95cae679e63cb9e34f423595f3faae7bcfbac27/p10_ax7020_rotating_shutdown.bit` |
