# P10.1R AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `3a4bbc524da1644782cebc8e9b6f990252b6ecc0b09f3e6da7a2b17f00134d13` | `494f6f7ed4c54c1f0a8d6dbcae5d5a81827a1de0944be75fb4e7f8c96cd38ddc` | `artifacts/p10_1r/60581a2074fd0021af9e2bf2c7cf96ec20cbcf92/494f6f7ed4c54c1f0a8d6dbcae5d5a81827a1de0944be75fb4e7f8c96cd38ddc/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `ff7ee1a393e7f4ad364a423167c3c75253d33d700dadbca43702bc52d3e9072c` | `783c7d38f6b17cbc5002290c90f2e18d5db1a94ad9b9d9bf600be3ff5356eeab` | `artifacts/p10_1r/60581a2074fd0021af9e2bf2c7cf96ec20cbcf92/783c7d38f6b17cbc5002290c90f2e18d5db1a94ad9b9d9bf600be3ff5356eeab/p10_ax7020_rotating_shutdown.bit` |
