# Project Status

> Generated from `config/project_state.json` by `scripts/generate_project_status.py`; do not edit by hand.

## Canonical scoped status

```text
P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE: PASS
CURRENT_Z7010_PLATFORM_ACCEPTANCE: PLATFORM_LIMITED_PASS
Z7020_TARGET_ACCEPTANCE: PENDING_Z7020_HW
ROTATION_ACCEPTANCE: PENDING_FINAL_MECHANICAL
FINAL_PRODUCT_HARDWARE_ACCEPTANCE: PENDING_HW
PRODUCT_FINAL_ACCEPTANCE: PENDING
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
```

The P7 PASS is limited to the stationary two-lane application path on the current Z7010 development platform. It is not Z7020, sector-bank, rotating, Ethernet, 8-lane, or final-product acceptance.

## Program stages

| Stage | Status |
|---|---|
| `P0_BOOTSTRAP` | `PASS` |
| `P1_OFFLINE_HARDENING` | `PASS` |
| `P2_SIMULATION_BASELINE` | `PASS` |
| `P3_PRE_HW_ACCEPTANCE_PACKAGE` | `PASS` |
| `P4_AUTO_HARDWARE_ACCEPTANCE` | `PASS_WITH_PROXY_ILA_EVIDENCE` |
| `P5_2LANE_PROTOCOL_STABILIZATION` | `PASS_WITH_NOTES` |
| `P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET` | `PASS` |
| `P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE` | `PASS` |
| `P8A_CANONICAL_REQUIREMENTS_STATE` | `PASS` |
| `P8B_GEOMETRY_MAPPING_HANDOVER` | `PENDING` |
| `P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT` | `PENDING` |
| `P8D_SELECTIVE_REPEAT_DMA` | `PENDING` |
| `P8E_DUAL_TARGET_BUILD_TIMING_CDC` | `PENDING` |

## P7 canonical evidence

- Profile: `Z7010_2LANE_DEV`
- Test ID: `P7-R74-FORMAL-FULL`
- Formal run: `p7_20260717_stationary_app_r74_formal_full`
- Hardware source commit: `911e1a303ff58593cac5ff4c4b70150d17f9a26b`
- Evidence commit: `5006731277e49d9f2ddaa04a4726949674be5b27`
- Evidence: `evidence/generated/p7_final_acceptance_summary.json`
- Evidence SHA256: `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b`
- Bitstream SHA256: `756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a`
- PS ELF SHA256: `2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949`
- Shutdown-before/after: `PASS` / `PASS`

## Legacy failure reconciliation

| Record | Current interpretation | Evidence |
|---|---|---|
| `AB_L1_BAD_DIR` | `HISTORICAL_RETAINED` | `evidence/imported/evidence/final/BAD_DIR_fault_report.md` |
| `P7_R41_FORMAL_STAGE66_FAIL` | `HISTORICAL_IMMUTABLE_FAIL_RETAINED` | `evidence/generated/p7_r41_formal_failure.json` |
| `AB_L1_CURRENT_P7_SCOPE` | `RESOLVED_FOR_P7_STATIONARY_2LANE_ONLY` | `evidence/generated/p7_lane1_promotion_summary.json` |
| `P7_R41_HOST_SORT_OVERFLOW` | `SOURCE_FIX_OFFLINE_VALIDATED_R41_REMAINS_FAILED` | `evidence/generated/p7_r41_postfailure_validation.json` |

`AB_L1_BAD_DIR` remains immutable history. The later lane1 evidence resolves usability only for the explicitly named P7 stationary Z7010 two-lane scope and is not extrapolated to future hardware.

## Architecture and pending gates

- GLOBAL_PERMIT architecture: `SINGLE_ACTIVE_HIGH_PER_ENDPOINT`
- Fixed endpoint permit count: `1`
- Rotating endpoint permit count: `1`
- Implementation status: `PENDING_P8C_D17`

| Gate | Status |
|---|---|
| `P8B` | `PENDING` |
| `P8C` | `PENDING` |
| `P8D` | `PENDING` |
| `P8E` | `PENDING` |
| `D12_CORE_BOARD` | `PENDING` |
| `D13_ABZ` | `PENDING` |
| `D14_SPI` | `PENDING` |
| `D15_TFDU_LIFECYCLE_PROCUREMENT` | `PENDING` |
| `D16_SYSTEM_OPTICAL_SAFETY` | `PENDING` |
| `D17_SINGLE_GLOBAL_PERMIT_IMPLEMENTATION` | `PENDING` |
| `BATTERY` | `PENDING` |
| `ENVIRONMENT` | `PENDING` |
| `OPTICS` | `PENDING` |

Last verified evidence commit: `5006731277e49d9f2ddaa04a4726949674be5b27`.

P8A was completed offline with `NO_HARDWARE=1`; it does not create or promote any hardware acceptance scope.
