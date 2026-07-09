# P5 P4 Evidence Reconciliation

generated_at_utc: 2026-07-09T14:50:41+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS_WITH_NOTES
reason: P4 normalized evidence table generated
hardware_actions_executed: false
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4_EVIDENCE_RECONCILIATION: PASS_WITH_NOTES
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4 had stale/generated summary inconsistencies; P5 uses normalized evidence and fresh P5 reruns.

| Item | Final JSON | Generated | Hardware evidence | Normalized status |
| --- | --- | --- | --- | --- |
| P4_AUTO_HARDWARE_ACCEPTANCE | PASS | PASS `evidence/generated/p4_auto_hardware_acceptance_summary.md` | PASS `evidence/generated/p4_auto_hardware_acceptance_summary.json` | PASS_WITH_DIRECT_SUMMARY |
| SAFE_IDLE_DIRECT_PROXY | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_safe_idle_direct_proxy_summary.md` | PASS_OFFLINE_ILA_INSTRUMENTED `evidence/hardware/p4_auto/safe_idle_direct_proxy/readback.json`<br>UNKNOWN `evidence/hardware/p4_auto/safe_idle_direct_proxy/p4_auto_safe_idle_program_result.json`<br>BLOCKED_BY_AUTOMATION_GAP `evidence/hardware/p4_auto/safe_idle_direct_proxy/p4_auto_safe_idle_direct_proxy_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| TFDU_CONTROL_IDLE | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_tfdu_control_idle_summary.md` | PASS `evidence/hardware/p4_auto/tfdu_control_idle/p4_auto_tfdu_control_idle_program_result.json`<br>BLOCKED_BY_AUTOMATION_GAP `evidence/hardware/p4_auto/tfdu_control_idle/p4_auto_tfdu_control_idle_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| RAW_PULSE_SMOKE_L0 | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_raw_pulse_smoke_summary.md` | UNKNOWN `evidence/hardware/p4_auto/raw_pulse_smoke/raw_pulse_smoke.json`<br>PASS `evidence/hardware/p4_auto/raw_pulse_smoke/p4_auto_raw_pulse_smoke_program_result.json`<br>UNKNOWN `evidence/hardware/p4_auto/ila/raw_pulse_smoke/raw_pulse_parse_result.json` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| RAW_LANE_MATRIX | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_raw_lane_matrix_summary.md` | PASS `evidence/hardware/p4_auto/raw_lane_matrix/p4_auto_raw_lane_matrix_program_result.json`<br>PASS `evidence/hardware/p4_auto/ila/raw_lane_matrix/raw_lane_matrix_parse_result.json`<br>PASS `evidence/hardware/p4_auto/raw_lane_matrix/ila_or_axi_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| LANE0_FRAME_CRC | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_lane0_frame_crc_summary.md` | PASS `evidence/hardware/p4_auto/protocol_smoke/lane0_frame_crc_readback.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane0_frame_crc_program_result.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/lane0_frame_crc_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| LANE0_ACK_RETRY | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_lane0_ack_retry_summary.md` | PASS `evidence/hardware/p4_auto/protocol_smoke/lane0_ack_retry_readback.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane0_ack_retry_program_result.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/lane0_ack_retry_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| LANE1_FRAME_CRC | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_lane1_frame_crc_summary.md` | PASS `evidence/hardware/p4_auto/protocol_smoke/lane1_frame_crc_readback.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_frame_crc_program_result.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/lane1_frame_crc_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| LANE1_ACK_RETRY | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_lane1_ack_retry_summary.md` | PASS `evidence/hardware/p4_auto/protocol_smoke/lane1_ack_retry_readback.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/p4_auto_lane1_ack_retry_program_result.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/lane1_ack_retry_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| TWO_LANE_MINIMAL | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_two_lane_minimal_summary.md` | PASS `evidence/hardware/p4_auto/protocol_smoke/two_lane_minimal_readback.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/p4_auto_two_lane_minimal_program_result.json`<br>PASS `evidence/hardware/p4_auto/protocol_smoke/two_lane_minimal_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| LANE0_300S_SOAK | PASS | BLOCKED_BY_AUTOMATION_GAP `evidence/generated/p4_auto_lane0_300s_soak_summary.md` | PASS `evidence/hardware/p4_auto/soak/lane0_300s_soak_readback.json`<br>PASS `evidence/hardware/p4_auto/soak/p4_auto_lane0_300s_soak_program_result.json`<br>PASS `evidence/hardware/p4_auto/soak/lane0_300s_soak_summary.md` | PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY |
| TWO_LANE_300S_SOAK | PASS | PASS `evidence/generated/p4_auto_two_lane_300s_soak_summary.md` | PASS `evidence/hardware/p4_auto/soak/two_lane_300s_soak_readback.json`<br>PASS `evidence/hardware/p4_auto/soak/p4_auto_two_lane_300s_soak_program_result.json`<br>PASS `evidence/hardware/p4_auto/soak/two_lane_300s_soak_summary.md` | PASS_WITH_DIRECT_SUMMARY |

## Boundary

- This reconciliation is historical P4 intake only.
- It does not promote P5 hardware stages to PASS.
- Fresh P5 hardware stages remain pending until an explicitly authorized P5 run creates P5 evidence.
