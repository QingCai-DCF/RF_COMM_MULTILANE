# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `5a969e37d78a7c4cd108c3fbe43227b735b58acb4b9a596f2305b64aabcf8d0d` | `artifacts/p10_1r/a1ac5457bc1555312c00dda81f2e2ad3a7c9751a/5a969e37d78a7c4cd108c3fbe43227b735b58acb4b9a596f2305b64aabcf8d0d/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `11b8a8020b96e16fa603b7b9e9b7323a02749f77fcbe1eed0dfdece2e488fe11` | `artifacts/p10_1r/a1ac5457bc1555312c00dda81f2e2ad3a7c9751a/11b8a8020b96e16fa603b7b9e9b7323a02749f77fcbe1eed0dfdece2e488fe11/p10_ax7020_rotating_shutdown.bit` |
