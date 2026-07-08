# Acceptance Matrix

| Stage | Status | Automation path |
|---|---|---|
| Import RF_COMM | PASS | manifest + sha256 |
| Constraint copy | PASS | constraint hash equality |
| XDC canonicalization | PASS | generated XDC equals active reference mapping |
| TFDU safety static | PASS | `scripts/check_tfdu_safety_static.py` |
| Multilane scheduler static | PASS | `scripts/check_scheduler_static.py` |
| Lane PHY sim | PENDING_TOOL | `sim/tb/tb_tfdu_lane_phy_smoke.sv` |
| 4PPM codec sim | PENDING_TOOL | `sim/tb/tb_tfdu_4ppm_codec.sv` |
| Lane0 frame CRC sim | PENDING_TOOL | `sim/tb/tb_lane0_frame_crc.sv` |
| Lane0 ACK sim | PENDING_TOOL | `sim/tb/tb_lane0_ack_only.sv` |
| Multilane scheduler sim | PENDING_TOOL | `sim/tb/tb_ir_multilane_scheduler.sv` |
| Vivado build | PENDING_TOOL | no hardware by default |
| M6 hardware prep wrappers | PASS | `scripts/check_m6_static.py`; wrappers refuse unless `-AllowHardware` |
| PS driver offline | PASS | host protocol unit test + generated headers |
| Host client offline protocol | PASS | encode/decode, error events, reconnect state machine mock |
| Ethernet real board | PENDING_HW_OR_DEFERRED | not automated unless user authorizes |
| Rotation 600 rpm | PENDING_EXTERNAL_FIXTURE | not automated by Codex |
| 2-hour soak | PENDING_HW | not automated by default |
| 8-lane | PENDING_DESIGN | blocked until lane1 and power strategy resolved |
