# P8D selective-repeat and aggregate data-plane completion summary

_RF_COMM_MULTILANE - P8D offline acceptance - 2026-07-18_

## Executive summary

P8D completed the bounded selective-repeat/SACK protocol, health-aware scheduling and retry migration, aggregate AXI-Stream front/back ends, independent DMA descriptor-ring model, RFAP v1/vNext compatibility, airtime model, multi-profile simulation, OOC resource audit, and P0-P8C regression. The accepted scope is **portable RTL/software/model acceptance**, with final status `PASS`.

- Source commit: `d28eef6aea8f545282076dd1a19a344adb12ccd9`
- Evidence checkpoint: resolved by the peeled target of annotated tag `p8d-pass` after the evidence commit
- P8C baseline: `p8c-pass` at `c44b0d45133bf75c9c71f53dde77f3dc186ad131`
- Machine-state revision: `P8D-1`
- Next program stage: `P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING`
- Hardware authorization: `false`; no hardware action was executed and no hardware scope was promoted

The canonical [project constraints](../PROJECT_CONSTRAINTS.txt) were not modified. Their retained SHA256 is `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`.

## Delivered data-plane behavior

| Area | Accepted behavior |
| --- | --- |
| Sequence and windows | One 16-bit modular sequence space per direction; shared bounded TX/RX windows with 32-entry Z7010 and 64-entry Z7020 profiles |
| ACK/SACK | Versioned cumulative ACK plus 32/64-bit SACK, receiver credit, bounded ACK aggregation, duplicate/stale/out-of-window rejection, and ACK-loss recovery |
| Delivery integrity | Duplicate application delivery, ACK completion, and descriptor double completion remain zero across retry, reordering, migration, reset, and wrap |
| Scheduling | Health-aware weighted scheduling with bounded starvation, lane-fault isolation, duty/permit/mapping deferral, and retry migration of unacknowledged entries only |
| AXI-Stream | Aggregate TX/RX ownership with stable `TVALID` under stall, `TKEEP`/`TLAST` validation, arbitrary backpressure, and deterministic malformed-packet errors |
| DMA model | Independent bounded TX/RX rings, explicit ownership states, generation protection, single completion, abort/reset reclaim, and zero descriptor leak |
| Payload retention | Shared global retransmission/reorder storage; per-lane queues retain references rather than duplicate full payload windows |
| RFAP | P7 RFAP v1 vectors remain compatible; vNext supports bounded-memory 64 MiB streaming, capability negotiation, abort/restart, integrity checks, and atomic publish |
| Safety integration | P8B path/mapping epochs and P8C duty/single-`GLOBAL_PERMIT` final-kill semantics remain authoritative; interrupted physical attempts restart only at a full frame boundary |
| CDC/reset | Async descriptor handshake was exercised at 1:1, 2:1, 3:2, and asynchronous phase relationships; final CDC/timing sign-off remains P8E scope |

The canonical parameter source is [config/p8d_data_plane.yaml](../config/p8d_data_plane.yaml), with SHA256 `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`. The extended register-map SHA256 is `8f029023d7871a7b8351c9c9256164d34a0ec2954754c261c31da410851d34b1`.

## Verification result

| Verification scope | Result | Direct evidence |
| --- | --- | --- |
| P8D final acceptance | `PASS` | [p8d_final_summary.json](../evidence/generated/p8d_final_summary.json) |
| Selective-repeat reference campaign | `PASS` | [p8d_selective_repeat_reference_summary.json](../evidence/generated/p8d_selective_repeat_reference_summary.json) |
| Selective-repeat/integration RTL | `PASS` | [p8d_selective_repeat_rtl_summary.json](../evidence/generated/p8d_selective_repeat_rtl_summary.json) |
| SACK and ACK aggregation | `PASS` | [p8d_sack_ack_aggregation_summary.json](../evidence/generated/p8d_sack_ack_aggregation_summary.json) |
| Scheduler and retry migration | `PASS` | [p8d_scheduler_migration_summary.json](../evidence/generated/p8d_scheduler_migration_summary.json) |
| AXI-Stream backpressure | `PASS` | [p8d_axis_backpressure_summary.json](../evidence/generated/p8d_axis_backpressure_summary.json) |
| DMA descriptor/ring model | `PASS` | [p8d_dma_descriptor_ring_summary.json](../evidence/generated/p8d_dma_descriptor_ring_summary.json) |
| PS driver offline contract | `PASS` | [p8d_ps_driver_summary.json](../evidence/generated/p8d_ps_driver_summary.json) |
| RFAP v1/vNext compatibility | `PASS` | [p8d_rfap_compatibility_summary.json](../evidence/generated/p8d_rfap_compatibility_summary.json) |
| Airtime/goodput model | `PASS` | [p8d_airtime_budget_summary.json](../evidence/generated/p8d_airtime_budget_summary.json) |
| Multi-profile/resource audit | `PASS` | [p8d_resource_audit_summary.json](../evidence/generated/p8d_resource_audit_summary.json) |
| Register-map consistency | `PASS` | [p8d_register_map_summary.json](../evidence/generated/p8d_register_map_summary.json) |
| P0-P8C preservation regression | `PASS` | [p8d_p0_p8c_regression_summary.json](../evidence/generated/p8d_p0_p8c_regression_summary.json) |
| Integrated full offline gate | `PASS` | [offline_gate_summary.json](../evidence/generated/offline_gate_summary.json) |
| Evidence consistency | `PASS` | [p8d_evidence_consistency_summary.json](../evidence/generated/p8d_evidence_consistency_summary.json) |
| Artifact manifest | `PASS`, 422 artifacts | [artifact_sha256_manifest.json](../evidence/generated/p8d_raw/artifact_sha256_manifest.json) |

The deterministic campaign recorded eight fixed seeds and completed `100,000` protocol lifecycle events, `25,000` scheduler/fault events, `25,000` descriptor/ring events, and a `1,000,000`-transition long run. It observed 12 sequence wraps and 11,720 ring wraps with zero duplicate application delivery, descriptor double completion, descriptor leak, window corruption, deadlock, or unbounded queue growth. RTL/Python comparison covered 2,048 records with zero mismatch. All mandatory XSIM compile/elaborate/run phases returned code `0`.

The selected immutable raw run is `evidence/generated/p8d_raw/formal_d28eef6aea8f_attempt_001`. Earlier failed attempts are retained rather than deleted; the final run is selected explicitly by the acceptance core and artifact manifest.

## Airtime result

The 8-lane baseline model uses the P8C 18% duty design target and reports approximately `17.035 Mbit/s` modeled application goodput, so `8LANE_16MBPS_ARCHITECTURE_FEASIBILITY=PASS`.

`19P2MBPS_STRETCH_FEASIBILITY=FAIL` is retained as an explicit, non-blocking model outcome: the frozen RFAP v1 frame/chunk geometry has an 18%-duty useful ceiling below 19.2 Mbit/s. No duty, CRC, SACK, integrity, or safety threshold was weakened to hide this gap. This is an offline architecture-model result, not hardware throughput evidence.

## OOC profile results

| Profile | LUT | FF | BRAM36 | DSP | Capacity/resource result | Timing scope |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `Z7010_2LANE_DEV` | 14,123 | 4,047 | 8 | 0 | `PASS`, fits xc7z010 | `NOT_MET_PENDING_P8E` |
| `Z7020_ROTATING_8LANE_MODEL` | 31,116 | 7,860 | 24 | 0 | `PASS`, 58.49% LUT | `NOT_MET_PENDING_P8E` |
| `Z7020_FIXED_32MODULE_ACCOUNTING_MODEL_WITH_8LANE_DATA_PLANE` | 35,200 | 11,437 | 72 | 0 | `PASS`, 66.17% LUT / 51.43% BRAM36 | `NOT_MET_PENDING_P8E` |

These are out-of-context architecture-feasibility results. Negative OOC timing slack is recorded directly and is not treated as P8E implementation, CDC, I/O-delay, or timing closure.

## Scope boundaries

| Scope | Preserved status |
| --- | --- |
| P7 stationary two-lane application | `PASS` |
| Current Z7010 platform | `PLATFORM_LIMITED_PASS` |
| Z7020 target | `PENDING_Z7020_HW` |
| Rotation | `PENDING_FINAL_MECHANICAL` |
| Final product hardware | `PENDING_HW` |
| Physical `GLOBAL_PERMIT` implementation | `PENDING_D17` |
| External TFDU duty measurement | `PENDING_P9_OR_LATER` |

P8D does not claim real AXI DMA/DDR/cache-coherency operation, Z7020 hardware, electrical/optical throughput, rotation, sector-bank hardware, or final-product acceptance.

## Canonical status and re-verification

Canonical status and traceability are available in:

- [PROJECT_STATUS.md](../PROJECT_STATUS.md)
- [config/project_state.json](../config/project_state.json)
- [config/project_requirements.yaml](../config/project_requirements.yaml)
- [REQUIREMENT_TRACEABILITY_MATRIX.md](REQUIREMENT_TRACEABILITY_MATRIX.md)

After the evidence checkpoint and annotated tag are created, the immutable evidence can be checked without hardware:

```powershell
$env:NO_HARDWARE = '1'
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = 'false'
python scripts/run_p8d_data_plane_gate.py --verify-existing --json-summary
```

Expected result: `status=PASS`, the peeled `p8d-pass` target is the evidence checkpoint, `NO_HARDWARE_ACTIONS_EXECUTED=true`, and the worktree is clean.
