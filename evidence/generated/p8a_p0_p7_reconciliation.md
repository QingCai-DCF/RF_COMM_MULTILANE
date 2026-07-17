# P8A P0-P7 Evidence Reconciliation

P0_P7_EVIDENCE_RECONCILIATION: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_SCOPE_PROMOTED: false

## Current scoped status

```text
P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE: PASS
CURRENT_Z7010_PLATFORM_ACCEPTANCE: PLATFORM_LIMITED_PASS
Z7020_TARGET_ACCEPTANCE: PENDING_Z7020_HW
ROTATION_ACCEPTANCE: PENDING_FINAL_MECHANICAL
FINAL_PRODUCT_HARDWARE_ACCEPTANCE: PENDING_HW
```

## Stage resolution

| Stage | Status | Profile | Test ID |
|---|---|---|---|
| `P0_BOOTSTRAP` | `PASS` | `Z7010_2LANE_DEV` | `P0-BOOTSTRAP-MARKERS` |
| `P1_OFFLINE_HARDENING` | `PASS` | `Z7010_2LANE_DEV` | `P1-OFFLINE-HARDENING` |
| `P2_SIMULATION_BASELINE` | `PASS` | `Z7010_2LANE_DEV` | `P3-P2-RECHECK-PLUS-P7-REGRESSION` |
| `P3_PRE_HW_ACCEPTANCE_PACKAGE` | `PASS` | `Z7010_2LANE_DEV` | `P3-PRE-HW-PACKAGE` |
| `P4_AUTO_HARDWARE_ACCEPTANCE` | `PASS_WITH_PROXY_ILA_EVIDENCE` | `Z7010_2LANE_DEV` | `P4-AUTO-HW-PROXY` |
| `P5_2LANE_PROTOCOL_STABILIZATION` | `PASS_WITH_NOTES` | `Z7010_2LANE_DEV` | `P5-2LANE-PROTOCOL` |
| `P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET` | `PASS` | `Z7010_2LANE_DEV` | `P6-EVIDENCE-CONSISTENCY` |
| `P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE` | `PASS` | `Z7010_2LANE_DEV` | `P7-R74-FORMAL-FULL` |

## Preserved contradictions and resolution

| Conflict | Historical status | Resolution | History preserved |
|---|---|---|---|
| `P2_EARLY_FAIL_VS_CURRENT_PASS` | `FAIL` | `SUPERSEDED_FOR_CURRENT_P2_STATUS_BY_LATER_P2_RECHECK_AND_P7_REGRESSION` | `true` |
| `AB_L1_LEGACY_BAD_DIR_VS_CURRENT_P7_USABILITY` | `BAD_DIR` | `RESOLVED_FOR_P7_STATIONARY_2LANE_ONLY` | `true` |
| `P7_R41_FAIL_VS_P7_R74_PASS` | `IMMUTABLE_FAIL` | `R41_REMAINS_FAILED; LATER_DISTINCT_R74_FORMAL_RUN_IS_CURRENT_CANONICAL_PASS` | `true` |
| `PRE_V3_1_STATUS_VS_CURRENT_CANONICAL_STATE` | `P7_PENDING_HW` | `SUPERSEDED_BY_CONFIG_PROJECT_STATE_AND_GENERATED_ROOT_STATUS` | `true` |

## Input artifacts

| Path | SHA256 | Bytes |
|---|---|---:|
| `evidence/generated/bootstrap_markers.md` | `23896dd01858df8afe68d450acf6940402d0c9090e999b8a5e890ca66468ff70` | 570 |
| `evidence/generated/p1_offline_hardening_summary.json` | `dc7ce195885dea366186107bfe027f1b0ed6a72dfe0643a29ecf12fe7eb9078c` | 31660 |
| `evidence/generated/p2_simulation_baseline_summary.md` | `e2bcef152d0b48bfcbdbd9e5066a165890602a10d1afcc49339117e6b8fc8568` | 1840 |
| `evidence/generated/p3_pre_hw_acceptance_package_summary.md` | `c02b445c23af4148260fa44ec168eee2414b8bc3522fbdaa4b858402efcd50e4` | 1575 |
| `evidence/generated/p4_auto_hardware_acceptance_summary.json` | `2bb5105d2ad280fb85cfcc0870c284e4743257cc1b0e117970d24a6bcf6b9b45` | 2566 |
| `evidence/generated/p5_2lane_protocol_stabilization_summary.json` | `dc9d36fb22c1f9175649afd8d5f121f8fb47a9056d02173136930afe8412a57b` | 11628 |
| `evidence/generated/p6_evidence_consistency_summary.json` | `477ae48aaafa9da114d183b309bea4476203372046c012f0fe812e6fd6f71681` | 58 |
| `evidence/generated/p7_offline_gate_summary.json` | `9ade79534e5b07cd9f2d806b4f8b2a3645c595ba3d6f46bbf80394e40069d883` | 20780 |
| `evidence/generated/p7_lane1_promotion_summary.json` | `6cc4cb4141133c7381874873137bfe78d5d73d337cf9c663b51ce5d1851a6363` | 1795 |
| `evidence/generated/p7_final_acceptance_summary.json` | `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b` | 1273547 |
| `evidence/generated/p7_final_acceptance_summary.md` | `702a32cf72601474b56e35bb3fac57ed9b97da8a4e681a8bf1c5089907caf624` | 8317 |
| `evidence/hardware/p7/p7_run_sequence_ledger.json` | `ab6138a0d6229985f127cf24fd418d2d4026a02a21b7776bdbb6be2fc608a2c4` | 1846000 |
| `evidence/generated/p7_r41_formal_failure.json` | `32bddfebc13630ab4261d4ab7b83851fb89800b84afdbb393f3983620d8a61a8` | 5422 |
| `evidence/imported/evidence/final/BAD_DIR_fault_report.md` | `e24245750107dd4fede13650bd3a796f4d8de97c37a9b13356b06c7ba5f7ebf7` | 1263 |
| `docs/legacy_stage_rules/P7_PRE_V3_1_PROJECT_STATUS.md` | `452bd17d1922065a44f783d80c977d073ad7fd7e1f0cb0b2c1b099248d5e8fe9` | 20506 |

The P7 r74 PASS does not rewrite the immutable r41 FAIL or the legacy AB_L1 BAD_DIR record. It only establishes the latest canonical stationary Z7010 two-lane application scope.
