# P4 Hardware Acceptance Summary

generated_at_utc: 2026-07-08T15:50:15+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
RESULT: FAIL_WITH_EVIDENCE
REASON: P4 did not reach hardware acceptance
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: FAIL_WITH_EVIDENCE

P4_HARDWARE_ACCEPTANCE: FAIL_WITH_EVIDENCE
COMMIT: 4768ef76c1d9bc6042d4058f52eef5fc0da5ca01
AUTHORIZED: true
AUTHORIZATION_FILE: .hardware_authorization/P4_APPROVED.txt
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: FAIL_WITH_EVIDENCE
P1_RECHECK: PASS
P2_RECHECK: PASS
P3_RECHECK: PASS
SAFE_IDLE_PROFILE_AUDIT: PASS
P4_ENVIRONMENT_CAPTURE: PASS
SAFE_IDLE: PASS_WITH_LIMITED_READBACK
TFDU_CONTROL_IDLE: SKIP_WITH_REASON
RAW_PULSE_SMOKE: SKIP_WITH_REASON
RAW_LANE_MATRIX: SKIP_WITH_REASON
LANE0_FRAME_CRC: SKIP_WITH_REASON
LANE0_ACK_RETRY: SKIP_WITH_REASON
LANE1_FRAME_CRC: SKIP_WITH_REASON
LANE1_ACK_RETRY: SKIP_WITH_REASON
TWO_LANE_MINIMAL: SKIP_WITH_REASON
LANE0_300S_SOAK: SKIP_WITH_REASON
TWO_LANE_300S_SOAK: SKIP_WITH_REASON
SHUTDOWN_ON_EXIT: PASS
STOP_CONDITIONS_TRIGGERED: none
NEXT_RECOMMENDED_STAGE: P4_SAFE_IDLE_DIRECT_READBACK_INSTRUMENTATION

## Generated Summaries

- `evidence/generated/p4_repo_intake.md`
- `evidence/generated/p4_recheck_p1_p2_p3_summary.md`
- `evidence/generated/p4_authorization_gate_summary.md`
- `evidence/generated/p4_safe_idle_profile_audit.md`
- `evidence/generated/p4_hardware_acceptance_summary.md`
- `evidence/generated/p4_hardware_acceptance_gate_summary.md`
- `evidence/generated/p4_no_hardware_or_authorized_hardware_scan.md`
- `evidence/hardware/p4/p4_authorized_run_results.json`
- `evidence/hardware/p4/p4_environment_capture.md`
- `evidence/hardware/p4/p4_authorization_record.md`
- `evidence/generated/p4_safe_idle_profile_audit.md`
- `evidence/hardware/p4/p4_bitstream_candidate_manifest.md`

## PASS

- P4.0 repo intake + P1/P2/P3 recheck
- P4.3 safe-idle profile audit
- P4.2 hardware environment capture
- P4.4 safe-idle bitstream programming
- shutdown-on-exit

## FAIL

- P4 hardware acceptance did not reach all required stages

## SKIP_WITH_REASON

- P4.2 hardware environment capture: PASS
- P4.4 safe-idle programming/readback: PASS_WITH_LIMITED_READBACK
- P4.5 TFDU control idle: SKIP_WITH_REASON: blocked until direct safe-idle TFDU pin readback or ILA/proxy evidence is available
- P4.6 raw pulse smoke: SKIP_WITH_REASON: blocked until direct safe-idle TFDU pin readback or ILA/proxy evidence is available
- P4.7 raw lane matrix: SKIP_WITH_REASON: blocked until direct safe-idle TFDU pin readback or ILA/proxy evidence is available
- P4.8-P4.12 protocol/soak stages: SKIP_WITH_REASON: blocked until direct safe-idle TFDU pin readback or ILA/proxy evidence is available
