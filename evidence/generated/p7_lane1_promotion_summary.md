# P7 Lane1 Reliability Promotion Gate

P7_LANE1_RELIABILITY_PROMOTION_GATE: PASS
HARDWARE_ACTIONS_EXECUTED: false
SOURCE_EVIDENCE_CONTAINS_HARDWARE_ACTIONS: true

## Checks

- raw_stage_pass: PASS
- raw_ab_l1: PASS
- raw_ba_l1: PASS
- raw_safety: PASS
- frame_crc_100: PASS
- frame_session_mask_readback: PASS
- frame_safety_shutdown: PASS
- ack_100: PASS
- ack_session_masks_readback: PASS
- ack_errors_safety_shutdown: PASS
- p6_lane1_160: PASS
- p6_shutdown: PASS
- p6_immutable_hash: PASS

## Boundary

- promotion eligibility from existing matching evidence; P7 still requires fresh staged regression before acceptance
