# P4 Auto Bitstream Provenance Summary

generated_at_utc: 2026-07-09T10:03:57+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: PASS
reason: generated safe-idle bitstream copied to an immutable P4_AUTO path
hardware_actions_executed: false
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4_AUTO_BITSTREAM_PROVENANCE: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
GENERATED_BITSTREAM_PATH_FORBIDDEN_AS_AUTH_OBJECT: `evidence/generated/vivado/ir_top_new_safe_idle.bit`
GENERATED_BITSTREAM_SHA256: `7158965bd4cb7fd8530625f84bc69f849c40707760a5f810116053217db65905`
BITSTREAM_MANIFEST_CSV: `evidence/hardware/p4_auto/bitstreams/bitstream_manifest.csv`
BITSTREAM_MANIFEST_JSON: `evidence/hardware/p4_auto/bitstreams/bitstream_manifest.json`
SAFE_IDLE_DEBUG_PROBE_INTEGRATED: true
SAFE_IDLE_DEBUG_PROBES: `evidence/generated/vivado/p4_auto_protocol_two_lane_soak_debug.ltx`
SAFE_IDLE_DEBUG_PROBES_SHA256: `7f993141f5c2c3d1d733fc8fa0441f7bc5f6b095d867b7870a049b3ed55dd6ac`

## Immutable Bitstreams

- `evidence/hardware/p4_auto/bitstreams/safe_idle/safe_idle_4768ef7_7158965bd4cb7fd8.bit`
- `evidence/hardware/p4_auto/bitstreams/tfdu_control_idle/tfdu_control_idle_4768ef7_b34f387f69b9e486.bit`
- `evidence/hardware/p4_auto/bitstreams/instrumented_idle/instrumented_idle_4768ef7_7158965bd4cb7fd8.bit`
- `evidence/hardware/p4_auto/bitstreams/raw_pulse/raw_pulse_4768ef7_d37d2bf60cd827d7.bit`
- `evidence/hardware/p4_auto/bitstreams/raw_lane_matrix/raw_lane_matrix_4768ef7_075e20ee59b37cd0.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_lane0/protocol_lane0_4768ef7_1d8521ed58bb53a2.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_lane0_ack/protocol_lane0_ack_4768ef7_bb33b0189e0d1114.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_lane1/protocol_lane1_4768ef7_7b051ec173da8eab.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_lane1_ack/protocol_lane1_ack_4768ef7_830628cdc2d8428b.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_two_lane_minimal/protocol_two_lane_minimal_4768ef7_0c101d476b896919.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_lane0_soak/protocol_lane0_soak_4768ef7_a9b59572935d2810.bit`
- `evidence/hardware/p4_auto/bitstreams/protocol_two_lane_soak/protocol_two_lane_soak_4768ef7_6bcb3ca2762eadd5.bit`

## Stage Rows

| Stage | Status | Immutable Path | SHA256 | Used For Programming |
| --- | --- | --- | --- | --- |
| safe_idle | PASS | `evidence/hardware/p4_auto/bitstreams/safe_idle/safe_idle_4768ef7_7158965bd4cb7fd8.bit` | `7158965bd4cb7fd8530625f84bc69f849c40707760a5f810116053217db65905` | false |
| tfdu_control_idle | PASS | `evidence/hardware/p4_auto/bitstreams/tfdu_control_idle/tfdu_control_idle_4768ef7_b34f387f69b9e486.bit` | `b34f387f69b9e4861e3d4dc7d230ced15bbe7032325e4874e1cc60a52e242bed` | false |
| instrumented_idle | PASS | `evidence/hardware/p4_auto/bitstreams/instrumented_idle/instrumented_idle_4768ef7_7158965bd4cb7fd8.bit` | `7158965bd4cb7fd8530625f84bc69f849c40707760a5f810116053217db65905` | false |
| raw_pulse | PASS | `evidence/hardware/p4_auto/bitstreams/raw_pulse/raw_pulse_4768ef7_d37d2bf60cd827d7.bit` | `d37d2bf60cd827d7c51b3f400ced30b12e83bfa345c8a04460d113d84f551db8` | false |
| raw_lane_matrix | PASS | `evidence/hardware/p4_auto/bitstreams/raw_lane_matrix/raw_lane_matrix_4768ef7_075e20ee59b37cd0.bit` | `075e20ee59b37cd0697c8f350c2d3e158d58829b4cffe06a91f5b7199aa525e0` | false |
| protocol_lane0 | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_lane0/protocol_lane0_4768ef7_1d8521ed58bb53a2.bit` | `1d8521ed58bb53a236e50b0e7d66e62d5db5d0988b09bf44a763b7289aa37b00` | false |
| protocol_lane0_ack | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_lane0_ack/protocol_lane0_ack_4768ef7_bb33b0189e0d1114.bit` | `bb33b0189e0d11147ae7749c718440fe36446a9c757499d06b985c8c7b63016d` | false |
| protocol_lane1 | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_lane1/protocol_lane1_4768ef7_7b051ec173da8eab.bit` | `7b051ec173da8eab1dda3905f94f22583c79d41a10c2a3d5612202cac8b96620` | false |
| protocol_lane1_ack | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_lane1_ack/protocol_lane1_ack_4768ef7_830628cdc2d8428b.bit` | `830628cdc2d8428bcd42467e29865161e6737ac92c0f53f2007fa8c71e962855` | false |
| protocol_two_lane_minimal | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_two_lane_minimal/protocol_two_lane_minimal_4768ef7_0c101d476b896919.bit` | `0c101d476b8969196ba6f1d9b82d146b59c59bde8612a1950268e6f19d1f0f35` | false |
| protocol_lane0_soak | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_lane0_soak/protocol_lane0_soak_4768ef7_a9b59572935d2810.bit` | `a9b59572935d28102e574dc9ada176cfd1371500669a4089f03971c160122b3f` | false |
| protocol_two_lane_soak | PASS | `evidence/hardware/p4_auto/bitstreams/protocol_two_lane_soak/protocol_two_lane_soak_4768ef7_6bcb3ca2762eadd5.bit` | `6bcb3ca2762eadd50c3b278159c42dc43bb3d9c3394f8055a3631df22a787e93` | true |
