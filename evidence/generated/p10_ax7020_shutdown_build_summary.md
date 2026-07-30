# P10 AX7020 dual shutdown build

- Status: `PASS`
- Hardware actions executed: `false`
- Part: `xc7z020clg400-2`
- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes.
- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).
- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.

| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |
|---|---|---|---|---|
| fixed | PASS | `c96f85544f9f5815b205045f7ddac0acbd43cc17681c0679de82919438cb112b` | `d849da80c485519ae6300398cdf0b09dc5838941bd14bdf71cb26c01ec9e3fe3` | `artifacts/p10/c96f85544f9f5815b205045f7ddac0acbd43cc17681c0679de82919438cb112b/d849da80c485519ae6300398cdf0b09dc5838941bd14bdf71cb26c01ec9e3fe3/p10_ax7020_fixed_shutdown.bit` |
| rotating | PASS | `c794ee8c8aad8103a861780cc49d36fa2cf57f03b5982763f640ef09cd54a01d` | `cf269e67f2f7aa246b792d5c378168e10913d2af10ccd5dcd5a97b62f679b148` | `artifacts/p10/c794ee8c8aad8103a861780cc49d36fa2cf57f03b5982763f640ef09cd54a01d/cf269e67f2f7aa246b792d5c378168e10913d2af10ccd5dcd5a97b62f679b148/p10_ax7020_rotating_shutdown.bit` |
