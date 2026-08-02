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
P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION: PASS
P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET: PASS
P10_1_OFFLINE_STATUS: PASS
P10_1_HARDWARE_STATUS: FAIL
P10_1R_STATUS: IN_PROGRESS
P11_OFFICIAL_STAGE_STATUS: NOT_STARTED
P11_HARDWARE_READY: false
CURRENT_PROGRAM_STAGE: P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
LAST_HARDWARE_AUTHORIZATION_CONSUMED: true
LAST_HARDWARE_STAGE: P10_1
LAST_HARDWARE_RUN_ID: p10_1_hw_20260801T090528Z_bb6ce78a_1585d1ad_9ad4f85f
LAST_SHUTDOWN_FIXED: PASS
LAST_SHUTDOWN_ROTATING: PASS
```

The P7 PASS is limited to the stationary two-lane application path on the current Z7010 development platform. It is not Z7020, sector-bank, rotating, Ethernet, 8-lane, or final-product acceptance.

## Program stages

| Stage | Status |
|---|---|
| `P0_BOOTSTRAP` | `PASS` |
| `P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION` | `IN_PROGRESS` |
| `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `PASS` |
| `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `FAIL` |
| `P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET` | `PASS` |
| `P1_OFFLINE_HARDENING` | `PASS` |
| `P2_SIMULATION_BASELINE` | `PASS` |
| `P3_PRE_HW_ACCEPTANCE_PACKAGE` | `PASS` |
| `P4_AUTO_HARDWARE_ACCEPTANCE` | `PASS_WITH_PROXY_ILA_EVIDENCE` |
| `P5_2LANE_PROTOCOL_STABILIZATION` | `PASS_WITH_NOTES` |
| `P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET` | `PASS` |
| `P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE` | `PASS` |
| `P8A_CANONICAL_REQUIREMENTS_STATE` | `PASS` |
| `P8B_GEOMETRY_MAPPING_HANDOVER` | `PASS` |
| `P8C_TFDU_SAFETY_SINGLE_GLOBAL_PERMIT` | `PASS` |
| `P8D_SELECTIVE_REPEAT_DMA` | `PASS` |
| `P8E_DUAL_TARGET_BUILD_TIMING_CDC` | `PASS` |
| `P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION` | `PASS` |

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

## P8C portable-function acceptance

- Status: `PASS` (offline RTL/model scope only)
- Source commit: `e8be6ffddd1b59b13b6bf3e0c32c02c6a66b6134`
- Evidence: `evidence/generated/p8c_final_summary.json`
- Single global permit RTL: `PASS`
- Exact rolling duty RTL: `PASS`
- Physical permit implementation: `PENDING_D17`
- Z7010 permit pin freeze: `PENDING_P9_PIN_FREEZE`
- External duty measurement: `PENDING_P9_OR_LATER`

## P8D portable data-plane acceptance

- Status: `PASS` (offline RTL/software/model scope only)
- Source commit: `d28eef6aea8f545282076dd1a19a344adb12ccd9`
- Evidence: `evidence/generated/p8d_acceptance_core.json`
- 16 Mbit/s architecture model: `PASS`
- 19.2 Mbit/s stretch model: `FAIL`
- Real AXI DMA, DDR/cache coherency, Z7020 hardware, rotation, and final timing/CDC remain pending.

## P9 post-checkpoint closeout

- P9 run: `p9_20260729T134551Z_6d88b7854219_ac75bfe61bfc`
- P9 source commit: `6d88b7854219c8b514ef36109a456ffbda4972d8`
- P9 annotated tag: `p9-z7010-2lane-pass`
- P9 evidence checkpoint: `818d335c229d7b92223c279159aab84a5207ef92`
- Closeout evidence: `evidence/generated/p9_post_checkpoint_closeout.json`
- Current-run authorization: `false`
- Last authorization consumed: `true`
- External TFDU duty measurement: `PENDING_EXTERNAL_MEASUREMENT`
- Physical GLOBAL_PERMIT implementation: `PENDING_D17`
- AB_L1 legacy/current P9 stationary: `BAD_DIR` / `PASS`
- This P9 closeout record is historical; P10 later completed its explicitly scoped stationary AX7020 two-lane run.

## P10 scoped AX7020 dual-node hardware acceptance

- Status: `PASS` (`AX7020_DUAL_NODE_STATIONARY_2LANE_NO_ETHERNET_HARDWARE_VALIDATION` only)
- Formal run: `p10_formal_20260730T181535Z_03`
- Hardware source commit: `8aa3879c5a8a5a4ed327b1084575bcfcc953f06b`
- Formal evidence freeze commit: `16684884708223bf7fb9b05145164e6155496cc8`
- Evidence: `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json`
- Evidence SHA256: `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- Evidence manifest: `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json`
- Fixed / rotating-role IDs: `AX7020-F/JTAG:210249855178` / `AX7020-R/JTAG:210512180081`
- Shutdown fixed / rotating: `PASS` / `PASS`
- Scope: stationary, two independent AX7020 endpoints, two optical lanes, no Ethernet, no motion.
- Ethernet, SPI, physical GLOBAL_PERMIT D17, external TFDU duty measurement, handover, 8x32, 600 rpm, and product-final acceptance remain pending.

## P10 post-acceptance closeout and analysis

- Closeout status: `PASS`
- Closeout evidence: `evidence/generated/p10_closeout_summary.json`
- Remote checkpoint evidence: `evidence/generated/p10_remote_push_summary.json`
- Current-run authorization: `false`
- Last authorization consumed: `true`
- Goodput audit: `PASS` (`CURRENT_FINAL_GOODPUT_FIELDS_NOT_SUITABLE_FOR_SCALING`)
- Current final goodput eligible for 8-lane projection: `false`
- P11 official stage: `NOT_STARTED`
- P11 hardware ready: `false`
- P10 remains a scoped PASS; the post-acceptance metric audit does not promote or revoke hardware scope.

## P10.1 extended offline performance and streaming readiness

- Offline status: `PASS` (`P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_NO_HARDWARE` only)
- Evidence: `evidence/generated/p10_1_performance_model.json`
- Modeled application goodput: `4189709.129513542 bit/s`
- 4.0 Mbit/s scale-equivalent feasibility: `PASS`
- Real hardware goodput: `FAIL`
- Offline sub-scope hardware actions executed: `false`
- P11 official stage / hardware ready: `NOT_STARTED` / `false`
- This offline PASS remains limited to feasibility, routed implementation, software, simulation, and dry-run evidence; any real AX7020 result is recorded separately below.

## P10.1 scoped AX7020 hardware performance campaign

- Status: `FAIL`
- Run ID: `p10_1_hw_20260801T090528Z_bb6ce78a_1585d1ad_9ad4f85f`
- Source commit: `bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1`
- Fixed / rotating-role IDs: `AX7020-F/JTAG:210249855178` / `AX7020-R/JTAG:210512180081`
- Final evidence: `evidence/generated/p10_1_hw_final_summary.json`
- F→R / R→F application goodput: `2587436.3002872` / `2585671.4991892674` bit/s
- Shutdown fixed / rotating: `PASS` / `PASS`
- Hardware actions / network / movement: `true` / `false` / `false`
- Scope remains stationary dual AX7020, two lanes, no Ethernet and no movement; it does not promote P11, 8x32, 600 rpm, physical GLOBAL_PERMIT, external duty, or product-final acceptance.

`AB_L1_BAD_DIR` remains immutable history. The later lane1 evidence resolves usability only for the explicitly named stationary Z7010 two-lane scope and is not extrapolated to future hardware.

## Architecture and pending gates

- GLOBAL_PERMIT architecture: `SINGLE_ACTIVE_HIGH_PER_ENDPOINT`
- Fixed endpoint permit count: `1`
- Rotating endpoint permit count: `1`
- Implementation status: `RTL_PORTABLE_FUNCTION_PASS_PHYSICAL_PENDING_D17`

| Gate | Status |
|---|---|
| `D12_CORE_BOARD` | `PENDING` |
| `D13_ABZ` | `PENDING` |
| `D14_SPI` | `PENDING` |
| `D15_TFDU_LIFECYCLE_PROCUREMENT` | `PENDING` |
| `D16_SYSTEM_OPTICAL_SAFETY` | `PENDING` |
| `D17_SINGLE_GLOBAL_PERMIT_IMPLEMENTATION` | `PENDING` |
| `BATTERY` | `PENDING` |
| `ENVIRONMENT` | `PENDING` |
| `OPTICS` | `PENDING` |

Last verified evidence commit: `8bb759047276e5bb9952403013d1d33cea6bba92`.

P8A, P8B, and completed P8C/P8D portable-function gates were executed with `NO_HARDWARE=1`; they do not create or promote hardware acceptance scope.
