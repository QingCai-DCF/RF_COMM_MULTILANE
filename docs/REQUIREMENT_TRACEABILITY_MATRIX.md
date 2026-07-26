# Requirement Traceability Matrix

> Generated from `config/project_requirements.yaml` by `scripts/generate_requirement_traceability.py`; do not edit by hand.

Canonical constraint: `PROJECT_CONSTRAINTS.txt` (`9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`).

```text
REQUIREMENT_COUNT: 85
PASS: 74
PENDING: 11
FAIL: 0
WAIVED: 0
```

A PENDING requirement is not a failure and is not a PASS. P8A baseline PASS means the requirement inventory and traceability machinery are complete; it does not promote unverified product requirements.

| Requirement ID | Status | Profile | Verification stage | Test ID | Evidence | Requirement |
|---|---|---|---|---|---|---|
| `SYS-ARCH-001` | `PENDING` | Z7020_8LANE_DUAL_ENDPOINT | `P10B` | — | — | 最终固定侧和旋转侧必须为两个独立 Zynq 节点。 |
| `SYS-GEO-001` | `PENDING` | Z7020_ROTATING_8LANE_FINAL | `P12` | — | — | 旋转侧必须布置 8 个 TFDU，45° 等间隔。 |
| `SYS-GEO-002` | `PENDING` | Z7020_FIXED_8LANE_FINAL | `P12` | — | — | 固定侧必须布置 32 个 TFDU，11.25° 等间隔。 |
| `SYS-MOTION-001` | `PENDING` | FINAL_PRODUCT_600RPM | `P13` | — | — | 系统必须支持正反转、停启和任意连续轨迹，且 \|rpm\| <= 600。 |
| `SYS-PERMIT-001` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-SINGLE-GLOBAL-PERMIT` | `evidence/generated/p8c_single_global_permit_architecture_summary.json` | Each independent endpoint has exactly one local active-high GLOBAL_PERMIT input. |
| `SYS-PERMIT-002` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-PERMIT-FAULT-INJECTION` | `evidence/generated/p8c_permit_fault_injection_summary.json` | GLOBAL_PERMIT low forces every local physical Txd output low through the final RTL kill. |
| `SYS-PERMIT-003` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-STATIC-SINGLE-PERMIT` | `evidence/generated/p8c_single_global_permit_architecture_summary.json` | Canonical RTL has no dual, heartbeat, per-bank, or per-lane external global permit channel. |
| `SYS-PERMIT-004` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-PERMIT-FAULT-INJECTION` | `evidence/generated/p8c_permit_fault_injection_summary.json` | Permit reassertion requires explicit re-arm and cannot resume a partial frame. |
| `PHY-SAFE-001` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-TFDU-POLARITY-MODE` | `evidence/generated/p8c_continuous_high_guard_summary.json` | TFDU6102 Txd/Rxd/SD polarity and static high-speed Mode semantics are correct in portable RTL. |
| `PHY-SAFE-002` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-FULL-SCALE-STARTUP` | `evidence/generated/p8c_exact_sliding_duty_rtl_summary.json` | Normal RX/TX is blocked for at least 500 us after shutdown exit. |
| `PHY-SAFE-003` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-RTL-CONTINUOUS-HIGH` | `evidence/generated/p8c_continuous_high_guard_summary.json` | Portable RTL limits continuous physical Txd high to at most 1 us and latches MAX+1 fault. |
| `PHY-SAFE-004` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-RTL-EXACT-DUTY` | `evidence/generated/p8e_p0_p8d_regression_summary.json` | Each physical module satisfies exact arbitrary-alignment 1000 us strict <20% duty with <=18% target admission. |
| `MAP-001` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-PYTHON-MAPPING-EXHAUSTIVE` | `evidence/generated/p8b_mapping_exhaustive_summary.json` | Current mapping shall be a complete eight-lane fixed-module and bank permutation for every m0. |
| `MAP-002` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-FORWARD-REVERSE-WRAP` | `evidence/generated/p8b_mapping_exhaustive_summary.json` | Forward and reverse candidate mappings shall be complete permutations with correct slot/bank wrap. |
| `MAP-003` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-PATH-EPOCH-ATOMICITY` | `evidence/generated/p8b_path_epoch_summary.json` | Mapping commit shall be atomic and increment path epoch exactly once per accepted request. |
| `PERF-HD-001` | `PENDING` | FINAL_PRODUCT_600RPM_HALF_DUPLEX | `P13_P15` | — | — | 600 rpm 半双工 application goodput 必须 >=16 Mbit/s。 |
| `PERF-FD-001` | `PENDING` | FINAL_PRODUCT_600RPM_FULL_DUPLEX | `P15` | — | — | 600 rpm 全双工 application goodput 必须 >=8 Mbit/s/方向。 |
| `DATA-001` | `PENDING` | ALL_APPLICATION_PROFILES | `P8D_P13_P15` | — | — | 错误、partial、stale 或 duplicate 对象不得提交。 |
| `EVID-001` | `PENDING` | ALL_PROFILES | `CONTINUOUS` | — | — | 每个 PASS 必须绑定 profile、test ID 和 evidence path。 |
| `EVID-002` | `PENDING` | ALL_FORMAL_RUNS | `CONTINUOUS` | — | — | 正式 artifact 必须内容寻址并以 SHA256 冻结。 |
| `SAFE-OPT-001` | `PENDING` | FINAL_PRODUCT_OPTICAL_SAFETY | `D16_P15` | — | — | 系统级光学安全通过前不得放宽人员接近控制。 |
| `MECH-001` | `PENDING` | FINAL_PRODUCT_600RPM | `P13` | — | — | 600 rpm 前必须完成留存、动平衡和分级升速。 |
| `P8A-CANON-001` | `PASS` | P8A_BASELINE | `P8A` | `P8A-CANONICAL-CONSTRAINT-GATE` | `PROJECT_CONSTRAINTS.txt` | PROJECT_CONSTRAINTS.txt 必须是唯一 canonical technical constraint，旧目标文件必须保持 superseded。 |
| `P8A-STATE-001` | `PASS` | P8A_BASELINE | `P8A` | `P8A-PROJECT-STATE-CONSISTENCY` | `PROJECT_STATUS.md` | config/project_state.json 必须是机器状态唯一事实源，PROJECT_STATUS.md 必须由它生成。 |
| `P8A-TRACE-001` | `PASS` | P8A_BASELINE | `P8A` | `P8A-REQUIREMENT-TRACEABILITY-BASELINE` | `config/project_requirements.yaml` | V3.1 初始关键 requirement ID 和 P8A requirement ID 必须具备完整机器可读追踪字段。 |
| `P8A-EVID-001` | `PASS` | P8A_BASELINE | `P8A` | `P8A-P0-P7-EVIDENCE-RECONCILIATION` | `evidence/generated/p8a_p0_p7_reconciliation.json` | P0-P7 final JSON、Markdown 和 raw evidence 必须完成显式 reconciliation，历史失败不得删除。 |
| `P8A-SCOPE-001` | `PASS` | P8A_BASELINE | `P8A` | `P8A-SCOPE-NONPROMOTION-GATE` | `PROJECT_STATUS.md` | P8A 离线结果不得提升、擦除或模糊任何硬件 scope。 |
| `P8A-LEGACY-001` | `PASS` | P8A_BASELINE | `P8A` | `P8A-LEGACY-CURRENT-SCOPE-RECONCILIATION` | `evidence/generated/p8a_p0_p7_reconciliation.json` | AB_L1 BAD_DIR 和 P7 r41 FAIL 必须保留，当前 lane1 可用性只能按最新 P7 scope 解释。 |
| `MAP-004` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-CROSSBAR-DATA` | `evidence/generated/p8b_crossbar_summary.json` | The explicit 8x8 crossbar shall route distinguishable current/candidate data and expose inverse bank owners. |
| `MAP-005` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-MAPPING-UNIT` | `evidence/generated/p8b_simulation_gate_summary.json` | Shadow mapping shall be context-bound and shall not control active/TX ownership before atomic commit. |
| `MAP-006` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-RTL-PYTHON-CROSSCHECK` | `evidence/generated/p8b_rtl_python_crosscheck.json` | RTL mapping outputs shall match the independent Python reference for all 512 direction/lane tuples. |
| `PHASE-001` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-PHASE-ACQUISITION` | `evidence/generated/p8b_phase_acquisition_summary.json` | Invalid, stale, uncertain, faulted or mismatched phase inputs shall fail closed into acquisition. |
| `PHASE-002` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-TRAJECTORY-RANDOMIZED` | `evidence/generated/p8b_phase_acquisition_summary.json` | Stop, restart and reversal shall require a fresh mapping and shall not reuse stale candidate context. |
| `PHASE-003` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-PHASE-ACQUISITION` | `evidence/generated/p8b_phase_acquisition_summary.json` | Phase-age motion shall use the 600 rpm bound without assuming constant speed or acceleration. |
| `HANDOVER-001` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-HDL-PHASE-ACQUISITION` | `evidence/generated/p8b_handover_timing_summary.json` | Six handover intervals shall be measured separately and logic timing targets shall pass. |
| `HANDOVER-002` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-PYTHON-GEOMETRY-NOMINAL` | `evidence/generated/p8b_handover_timing_summary.json` | Handover angular consumption and remaining margin shall be reported as nominal/provisional only. |
| `GEO-MODEL-001` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-PYTHON-GEOMETRY-NOMINAL` | `evidence/generated/p8b_geometry_nominal_summary.json` | Nominal D200/D600 geometry shall match the closed-form reference values. |
| `GEO-MODEL-002` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-PYTHON-GEOMETRY-GAPS` | `evidence/generated/p8b_geometry_gap_ledger.json` | Unknown geometry tolerances shall remain null/PENDING and block worst-case hardware acceptance. |
| `EVID-P8B-001` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-REQUIREMENT-TRACEABILITY` | `evidence/generated/p8b_rtl_python_crosscheck.json` | Every P8B PASS shall bind a profile, test ID, evidence path and content hashes without promoting hardware scope. |
| `SYS-PERMIT-005` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-RAW-PERMIT-FINAL-KILL` | `evidence/generated/p8c_permit_fault_injection_summary.json` | Raw permit deassert reaches the final RTL Txd kill without PS or normal frame completion. |
| `SYS-PERMIT-006` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-RECEIVE-ONLY-ACQUISITION` | `evidence/generated/p8c_receive_only_acquisition_summary.json` | Permit low allows controlled receive-only acquisition while every physical TX remains disabled. |
| `PHY-SAFE-005` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-HISTORY-COOLDOWN` | `evidence/generated/p8e_p0_p8d_regression_summary.json` | Duty-history invalidation requires at least 1000 us all-TX-low cooldown before reuse. |
| `PHY-SAFE-006` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-PHYSICAL-MODULE-ACCOUNTING` | `evidence/generated/p8c_physical_module_accounting_summary.json` | Rolling-duty state is bound to physical-module identity and survives lane, path, and permit transitions. |
| `L2-ARQ-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Each endpoint direction uses bounded selective-repeat TX/RX windows. |
| `L2-ARQ-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-CANONICAL-CONFIG` | `evidence/generated/p8e_raw/r8d/p8d_data_plane_config_summary.json` | The shared global outstanding window supports at least 32 frames. |
| `L2-SEQ-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8e_raw/r8d/p8d_selective_repeat_rtl_summary.json` | Sequence width is at least 16 bits and modular wrap is bit-exact. |
| `L2-SACK-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SACK-ACK-AGGREGATION` | `evidence/generated/p8e_raw/r8d/p8d_sack_ack_aggregation_summary.json` | The negotiated SACK window supports at least 32 bits. |
| `L2-SACK-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SACK-ACK-AGGREGATION` | `evidence/generated/p8e_raw/r8d/p8d_sack_ack_aggregation_summary.json` | ACK aggregation has a bounded frame threshold and maximum delay. |
| `L2-DUP-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-PYTHON-REFERENCE-CAMPAIGN` | `evidence/generated/p8e_precompletion_reverification_summary.json` | A duplicate logical frame never commits or completes twice. |
| `L2-STALE-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Stale session/path data and ACK records are rejected. |
| `L2-MIG-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Only unacknowledged frames may migrate across eligible lanes or paths. |
| `L2-RETRY-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Retry count, timeout/backoff, and exhaustion are bounded. |
| `SCHED-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Scheduling is health-aware and weighted across eligible lanes. |
| `SCHED-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8e_precompletion_reverification_summary.json` | A faulted lane does not block work on healthy eligible lanes. |
| `SCHED-003` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Scheduler fairness and starvation are explicitly bounded. |
| `AXIS-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AXIS-BACKPRESSURE` | `evidence/generated/p8e_raw/r8d/p8d_axis_backpressure_summary.json` | Aggregate AXI-Stream transfers have no loss or duplication under arbitrary backpressure. |
| `DMA-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Independent bounded TX and RX scatter-gather descriptor rings are modeled. |
| `DMA-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Descriptor ownership permits exactly one completion and one reclaim. |
| `DMA-003` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Reset and abort deterministically reclaim ring and payload ownership. |
| `DMA-004` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Descriptor generation rejects stale completions after wrap or reset. |
| `RFAP-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-RFAP-V1-VNEXT-COMPATIBILITY` | `evidence/generated/p8e_raw/r8d/p8d_rfap_compatibility_summary.json` | RFAP v1/P7 vectors and legacy fallback remain compatible. |
| `RFAP-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-RFAP-V1-VNEXT-COMPATIBILITY` | `evidence/generated/p8e_raw/r8d/p8d_rfap_compatibility_summary.json` | RFAP vNext streaming validates large objects with bounded memory and atomic publish. |
| `PERF-MODEL-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AIRTIME-BUDGET-MODEL` | `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` | The airtime model includes duty, framing, ACK, retry, handover, and descriptor overhead. |
| `PERF-MODEL-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AIRTIME-BUDGET-MODEL` | `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` | The 16 Mbit/s architecture target is explicitly evaluated without increasing duty. |
| `BUILD-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-DUAL-TARGET-BUILD-MATRIX` | `evidence/generated/p8e_build_matrix_summary.json` | Z7010 and exact-part Z7020 use a common-source reproducible build matrix. |
| `BUILD-002` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-SOURCE-MANIFEST-COMMON-CORE` | `evidence/generated/p8e_source_manifest_summary.json` | Fixed and rotating endpoint role wrappers remain thin consumers of one common core. |
| `TIMING-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-DUAL-TARGET-BUILD-MATRIX` | `evidence/generated/p8e_build_matrix_summary.json` | All formal core clocks have nonnegative routed setup and hold slack with zero TNS. |
| `TIMING-002` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CANONICAL-BUILD-CONFIG` | `evidence/generated/p8e_timing_architecture_summary.json` | The 64 MHz protocol/PHY target is preserved in every implementation profile. |
| `TIMING-003` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CONSTRAINT-LINT` | `evidence/generated/p8e_constraint_audit_summary.json` | Routed implementation has zero unconstrained internal endpoints. |
| `TIMING-004` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-DUAL-TARGET-BUILD-MATRIX` | `evidence/generated/p8e_build_matrix_summary.json` | Timing closure is robust across the documented Default and Performance_Explore strategies. |
| `CDC-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CDC-RDC-CLOSURE` | `evidence/generated/p8e_cdc_rdc_summary.json` | All active CDC crossings are classified by the routed CDC and clock-interaction audits. |
| `CDC-002` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CDC-RDC-CLOSURE` | `evidence/generated/p8e_cdc_rdc_summary.json` | Unsafe multi-bit direct CDC crossings are zero. |
| `CDC-003` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CDC-RDC-CLOSURE` | `evidence/generated/p8e_cdc_rdc_summary.json` | Reset deassertion is synchronized independently in each active clock domain. |
| `CDC-004` | `PASS` | Z7020_DUAL_ENDPOINT_DIGITAL_LINK_SIM | `P8E` | `P8E-DUAL-ENDPOINT-DIGITAL-SIM` | `evidence/generated/p8e_dual_endpoint_sim_summary.json` | Independent reset cannot commit a stale completion into the new generation. |
| `RDC-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CDC-RDC-CLOSURE` | `evidence/generated/p8e_cdc_rdc_summary.json` | Reset-domain crossings are structurally audited and exercise independent recovery. |
| `DRC-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-RESET-BRAM-REQP1839` | `evidence/generated/p8e_reset_bram_summary.json` | Vivado REQP-1839 violations are zero without suppression or waiver. |
| `DRC-002` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-DUAL-TARGET-BUILD-MATRIX` | `evidence/generated/p8e_build_matrix_summary.json` | Critical DRC and critical methodology violations are zero. |
| `RESOURCE-001` | `PASS` | Z7020_FIXED_AND_ROTATING_CORE_OFFLINE | `P8E` | `P8E-RESOURCE-MARGIN` | `evidence/generated/p8e_resource_margin_summary.json` | Exact-part Z7020 utilization remains below canonical resource limits. |
| `RESOURCE-002` | `PASS` | Z7010_2LANE_DEV_IMPLEMENTATION | `P8E` | `P8E-RESOURCE-MARGIN` | `evidence/generated/p8e_resource_margin_summary.json` | The Z7010 profile fits without deleting mandatory safety, CRC, SACK, or recovery semantics. |
| `RESOURCE-003` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-RESOURCE-MARGIN` | `evidence/generated/p8e_resource_margin_summary.json` | Resource margin is explicitly reported for every profile and implementation strategy. |
| `AXIDMA-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-AXI-DMA-STATIC-ADAPTER` | `evidence/generated/p8e_axi_dma_static_integration_summary.json` | A vendor-isolation AXI DMA interface adapter is statically integrated offline. |
| `AXIDMA-002` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-AXI-DMA-STATIC-ADAPTER` | `evidence/generated/p8e_axi_dma_static_integration_summary.json` | AXI-Stream and descriptor contracts preserve TLAST, TKEEP, backpressure, completion, abort, and generation semantics. |
| `PROFILE-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-CONSTRAINT-LINT` | `evidence/generated/p8e_constraint_audit_summary.json` | The canonical Z7010 board XDC is isolated from every Z7020 profile. |
| `PROFILE-002` | `PASS` | Z7020_FIXED_AND_ROTATING_D12_INPUT | `P8E` | `P8E-Z7020-IO-BUDGET` | `evidence/generated/p8e_io_budget_summary.json` | Unknown Z7020 board pins and board I/O timing remain PENDING_D12 and are not invented. |
| `REPRO-001` | `PASS` | P8E_MULTI_PROFILE_OFFLINE | `P8E` | `P8E-EVIDENCE-CONSISTENCY` | `evidence/generated/p8e_evidence_consistency_summary.json` | The clean-checkout batch implementation and evidence flow is reproducible and content-addressed. |

## PASS artifact bindings

### `SYS-PERMIT-001`

- `rtl/ir_tfdu_safety_endpoint.sv` — `b5ed87792283b0cf0c495d5f813a37268ca779addd0aa3ce8613136d64afb315`
- `config/tfdu_safety.yaml` — `e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06`
- `evidence/generated/p8c_single_global_permit_architecture_summary.json` — `8f3e1de16d01fb0b63477bb30e6accf7be048791228d4cf89bd1c21620c6c287`

### `SYS-PERMIT-002`

- `rtl/ir_tfdu_safety_endpoint.sv` — `b5ed87792283b0cf0c495d5f813a37268ca779addd0aa3ce8613136d64afb315`
- `sim/tb/tb_p8c_endpoint_safety.sv` — `bd067f0d5e7e2ddfd84b30f7983c4edda9dc22be19df994a08cfd6fd562f1593`
- `evidence/generated/p8c_permit_fault_injection_summary.json` — `f3badd716d4817d35376afa908319a3ffb9d63c143a9aa6c2c26ca13198a8ea9`

### `SYS-PERMIT-003`

- `config/p8c_active_sources.json` — `6e8a9753a02f8db8913ddd0caac25cb3c5ee3e8927b756446a72b9ee036cabb2`
- `scripts/check_p8c_safety_static.py` — `6d7fc502066b59b9b545dd3146b1598f2d228e6dabd7bda27ffc7e1aff07b9a7`
- `evidence/generated/p8c_single_global_permit_architecture_summary.json` — `8f3e1de16d01fb0b63477bb30e6accf7be048791228d4cf89bd1c21620c6c287`

### `SYS-PERMIT-004`

- `rtl/ir_tfdu_safety_endpoint.sv` — `b5ed87792283b0cf0c495d5f813a37268ca779addd0aa3ce8613136d64afb315`
- `sim/tb/tb_p8c_endpoint_safety.sv` — `bd067f0d5e7e2ddfd84b30f7983c4edda9dc22be19df994a08cfd6fd562f1593`
- `evidence/generated/p8c_permit_fault_injection_summary.json` — `f3badd716d4817d35376afa908319a3ffb9d63c143a9aa6c2c26ca13198a8ea9`

### `PHY-SAFE-001`

- `rtl/ir_tfdu_physical_module_safety.sv` — `428a40acf4f5638294d8fd516c3ba86fbe3e90ce0bc0a2ddc9b2a4051020ac19`
- `rtl/ir_tfdu_safety_endpoint.sv` — `b5ed87792283b0cf0c495d5f813a37268ca779addd0aa3ce8613136d64afb315`
- `evidence/generated/p8c_continuous_high_guard_summary.json` — `3e6122f662a9b7dd08b23b3a4f8c701de3b2b8ed8ca781f5b642cf3dbae25fa1`

### `PHY-SAFE-002`

- `rtl/ir_tfdu_physical_module_safety.sv` — `428a40acf4f5638294d8fd516c3ba86fbe3e90ce0bc0a2ddc9b2a4051020ac19`
- `sim/tb/tb_p8c_full_scale.sv` — `de7d29f8ca19a3bf65856d76b8bce60c16fc11b6a715088c3d34c251230c731c`
- `evidence/generated/p8c_exact_sliding_duty_rtl_summary.json` — `be832ebf4a1909618c41a2815846a24625d51d3045defd79815d0d6d861a6719`

### `PHY-SAFE-003`

- `rtl/ir_tfdu_physical_module_safety.sv` — `428a40acf4f5638294d8fd516c3ba86fbe3e90ce0bc0a2ddc9b2a4051020ac19`
- `sim/tb/tb_p8c_physical_safety.sv` — `51f5705b35a659b7a4363fed34da3ebe81ebdef95b5b1c9d961b5d77d7a5d34b`
- `evidence/generated/p8c_continuous_high_guard_summary.json` — `3e6122f662a9b7dd08b23b3a4f8c701de3b2b8ed8ca781f5b642cf3dbae25fa1`

### `PHY-SAFE-004`

- `rtl/ir_tfdu_exact_duty_accountant.sv` — `05385eee22ad7ace59da7ced41296ce0480fcd0339d8dee3194534cc5af9cb2f`
- `sim/tb/tb_p8c_full_scale.sv` — `de7d29f8ca19a3bf65856d76b8bce60c16fc11b6a715088c3d34c251230c731c`
- `evidence/generated/p8e_p0_p8d_regression_summary.json` — `176a7cbab52778f8a341ead51d9df9c0ebbe7e916e07b1fdd73b0c8fbe25032a`

### `MAP-001`

- `rtl/ir_path_mapping_pkg.sv` — `6be70a692a1b39ecae347c52b9440fd6f7b1e41434362423aeb53519dabd505b`
- `evidence/generated/p8b_mapping_exhaustive_summary.json` — `449b5f8647fe2670f4c8463244e22de1d0c9c728a6098d3bb2ed3d0a0193a8ce`

### `MAP-002`

- `tools/p8b_mapping_reference.py` — `d9d97209cb6f41fe4f389d697d4ac7a638101d1537516235abe35fc320f54565`
- `evidence/generated/p8b_mapping_exhaustive_summary.json` — `449b5f8647fe2670f4c8463244e22de1d0c9c728a6098d3bb2ed3d0a0193a8ce`

### `MAP-003`

- `rtl/ir_path_epoch_commit.sv` — `1cd34f339393fdfce3f554d33501ba12a65b3daf85190ffa01bad2d95890db4c`
- `evidence/generated/p8b_path_epoch_summary.json` — `ba231b341867cd5fb4a4e3501405c478b6914017e50c43402d79cbf0f0d94ec0`

### `P8A-CANON-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `PROJECT_CONSTRAINTS_CHANGELOG.md` — `f51da907122d1673bc3b657779997742df474ed391cd1a6772e0371da8cc176b`

### `P8A-STATE-001`

- `config/project_state.json` — `0c88eaaf7df1c32feabe548f78e63b63e2230349289690089b7616af6df66661`
- `PROJECT_STATUS.md` — `3dfc562073efeb08e63ca5fcf5655c8c3ece2598057e4c53083fd72b39e18208`

### `P8A-TRACE-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `config/project_state.json` — `0c88eaaf7df1c32feabe548f78e63b63e2230349289690089b7616af6df66661`

### `P8A-EVID-001`

- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`
- `evidence/generated/p7_final_acceptance_summary.json` — `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b`
- `evidence/hardware/p7/p7_run_sequence_ledger.json` — `ab6138a0d6229985f127cf24fd418d2d4026a02a21b7776bdbb6be2fc608a2c4`

### `P8A-SCOPE-001`

- `config/project_state.json` — `0c88eaaf7df1c32feabe548f78e63b63e2230349289690089b7616af6df66661`
- `PROJECT_STATUS.md` — `3dfc562073efeb08e63ca5fcf5655c8c3ece2598057e4c53083fd72b39e18208`
- `evidence/generated/p7_final_acceptance_summary.md` — `702a32cf72601474b56e35bb3fac57ed9b97da8a4e681a8bf1c5089907caf624`

### `P8A-LEGACY-001`

- `evidence/imported/evidence/final/BAD_DIR_fault_report.md` — `e24245750107dd4fede13650bd3a796f4d8de97c37a9b13356b06c7ba5f7ebf7`
- `evidence/generated/p7_lane1_promotion_summary.json` — `6cc4cb4141133c7381874873137bfe78d5d73d337cf9c663b51ce5d1851a6363`
- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`

### `MAP-004`

- `rtl/ir_bank_lane_crossbar.sv` — `97be64e23308e85768866c8bc5037d9f4f2bfb3670a9981915d3f5686519e886`
- `evidence/generated/p8b_crossbar_summary.json` — `21117b5297c9d1921e18ccac39d06066bf1fbc3f9566649d007a960474db08c1`

### `MAP-005`

- `rtl/ir_path_mapping_engine.sv` — `248691b1186dfcd4524e8a988aa2424e4b2853852fea2fb645c0ac4c66613d2c`
- `sim/tb/tb_p8b_mapping_unit.sv` — `7d7baaa638ebd81da3a44ada810d324252b47602472de493e5a1dad5eae5e30a`
- `evidence/generated/p8b_simulation_gate_summary.json` — `c9debf536967242b5776159574936154e943726c2782909c787308985369ab12`

### `MAP-006`

- `evidence/generated/p8b_rtl_python_crosscheck.csv` — `a15d1f0dd2904231df27101a6a29ca14abcc4782430b6605d854d408db5d274c`
- `evidence/generated/p8b_rtl_python_crosscheck.json` — `f5a48ea7419f68a601073f8b4d40769448847aaa04946fc359e9ca9ceff320de`

### `PHASE-001`

- `rtl/ir_phase_validity_guard.sv` — `f0f32489c307d01e49741708b14689aeaa3b511fa33a25bb047a6687a2a21742`
- `evidence/generated/p8b_phase_acquisition_summary.json` — `a39104698e930ae1ae1f073964e0ef1f0ee1acfbe605de921c3f28525aa974f8`

### `PHASE-002`

- `tools/p8b_generate_trajectory.py` — `a1d19a1f9acdfe0d0ecc145bbe2a507a76add84d2b430175291cfe424cd28357`
- `sim/tb/tb_p8b_phase_trajectory.sv` — `d3487922d87ef3b5553197762af8d895b59754f0128238c7da3c15c5b0f622a9`
- `evidence/generated/p8b_phase_acquisition_summary.json` — `a39104698e930ae1ae1f073964e0ef1f0ee1acfbe605de921c3f28525aa974f8`

### `PHASE-003`

- `rtl/ir_phase_validity_guard.sv` — `f0f32489c307d01e49741708b14689aeaa3b511fa33a25bb047a6687a2a21742`
- `docs/P8B_PHASE_ACQUISITION_MODEL.md` — `a4f0c32584787f5cc0663970ac8214ebbc9a2373157a4c0cb4b406e9ea1ed4ee`
- `evidence/generated/p8b_phase_acquisition_summary.json` — `a39104698e930ae1ae1f073964e0ef1f0ee1acfbe605de921c3f28525aa974f8`

### `HANDOVER-001`

- `rtl/ir_handover_metrics.sv` — `f5f4862a0b439f08404fe249732fe108c0be0d6bc4cc77a4850d906ec046d4ab`
- `evidence/generated/p8b_handover_timing_summary.json` — `9ec81796af32ef1a26f06fdf2c5ad31aa9a3b1ef52b0d92d36956a370b2842e7`

### `HANDOVER-002`

- `config/geometry/optical_geometry.yaml` — `ed047dec336af273d0f56e4c400f7ce7f2e8440a6a04869c367e46e8152824b0`
- `evidence/generated/p8b_handover_timing_summary.json` — `9ec81796af32ef1a26f06fdf2c5ad31aa9a3b1ef52b0d92d36956a370b2842e7`

### `GEO-MODEL-001`

- `tools/p8b_geometry_model.py` — `35b3d36bf086d2e4ef135ddacffbb2dfa01551dce351057feacda758fff0530b`
- `evidence/generated/p8b_geometry_nominal_summary.json` — `c195a04d316bc1d3a99c0c1b3fa47e6ae81c0d21cddc6017ce7057aa5091fa41`

### `GEO-MODEL-002`

- `config/geometry/optical_geometry.yaml` — `ed047dec336af273d0f56e4c400f7ce7f2e8440a6a04869c367e46e8152824b0`
- `evidence/generated/p8b_geometry_gap_ledger.json` — `ea11b045a2bc422e89d556033d99e761c3705c069177f1eca15e4042725c742f`
- `evidence/generated/p8b_geometry_worst_case_summary.json` — `748605a0bb9b07f9b2abab1abd0f1030e2c2bd121fa21c5af698ef5a56f0b30c`

### `EVID-P8B-001`

- `evidence/generated/p8b_mapping_exhaustive_summary.json` — `449b5f8647fe2670f4c8463244e22de1d0c9c728a6098d3bb2ed3d0a0193a8ce`
- `evidence/generated/p8b_geometry_nominal_summary.json` — `c195a04d316bc1d3a99c0c1b3fa47e6ae81c0d21cddc6017ce7057aa5091fa41`
- `evidence/generated/p8b_rtl_python_crosscheck.json` — `f5a48ea7419f68a601073f8b4d40769448847aaa04946fc359e9ca9ceff320de`

### `SYS-PERMIT-005`

- `rtl/ir_tfdu_safety_endpoint.sv` — `b5ed87792283b0cf0c495d5f813a37268ca779addd0aa3ce8613136d64afb315`
- `sim/tb/tb_p8c_endpoint_safety.sv` — `bd067f0d5e7e2ddfd84b30f7983c4edda9dc22be19df994a08cfd6fd562f1593`
- `evidence/generated/p8c_permit_fault_injection_summary.json` — `f3badd716d4817d35376afa908319a3ffb9d63c143a9aa6c2c26ca13198a8ea9`

### `SYS-PERMIT-006`

- `rtl/ir_tfdu_safety_endpoint.sv` — `b5ed87792283b0cf0c495d5f813a37268ca779addd0aa3ce8613136d64afb315`
- `sim/tb/tb_p8c_endpoint_safety.sv` — `bd067f0d5e7e2ddfd84b30f7983c4edda9dc22be19df994a08cfd6fd562f1593`
- `evidence/generated/p8c_receive_only_acquisition_summary.json` — `5cc50500f336232e2fad211cc8b611114ce25ddc470d73b0675a4670886fbab8`

### `PHY-SAFE-005`

- `rtl/ir_tfdu_exact_duty_accountant.sv` — `05385eee22ad7ace59da7ced41296ce0480fcd0339d8dee3194534cc5af9cb2f`
- `sim/tb/tb_p8c_exact_duty.sv` — `bca756a20bc65b02d5293704bb23f755e9570f328b2cbbcd331f547380209a8c`
- `evidence/generated/p8e_p0_p8d_regression_summary.json` — `176a7cbab52778f8a341ead51d9df9c0ebbe7e916e07b1fdd73b0c8fbe25032a`

### `PHY-SAFE-006`

- `rtl/ir_p8c_mapping_safety_adapter.sv` — `f4d2b8a58c02c7379b9c47e109d000b578fafb7d0f9d9578c7efa70ed5655928`
- `sim/tb/tb_p8c_profile_matrix.sv` — `d044e572bdc244b673ff298b56c442daaa3df0af8595f35086783577ede7a13f`
- `evidence/generated/p8c_physical_module_accounting_summary.json` — `0a8ecb742db212e4fb017618400668421d88a81e7077fe652707e2253c0df6a7`

### `L2-ARQ-001`

- `rtl/ir_selective_repeat_tx.sv` — `4b8a88322ce0e25b7530b44294ef3511192d17cce2b385dcc6da15e521522c9c`
- `rtl/ir_selective_repeat_rx.sv` — `25b5cf6ff573ba01a31370bd44ae1bdd4d6367160e4d11b472cea17856a70cb4`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `L2-ARQ-002`

- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `rtl/ir_data_plane_top.sv` — `7c07a0bb35a9bed5c4565758fa23b61017508787bf929f50905a9c5d6d0d8e63`
- `evidence/generated/p8e_raw/r8d/p8d_data_plane_config_summary.json` — `cf243210e4ce089cf626cfa69254dcd32a5af906a02a7553f568332eba47b647`

### `L2-SEQ-001`

- `rtl/ir_seq_math_pkg.sv` — `860c37a7565b19c7e2a1048c1552e12bba98662090f536a329258e69b292666e`
- `sim/tb/tb_ir_seq_math.sv` — `a01ab71e3891e4074a9b4f89719ced7561b39b83218ddf424965093d42608e5b`
- `evidence/generated/p8e_raw/r8d/p8d_selective_repeat_rtl_summary.json` — `8c10791a2e5018f955cc48e8705e18736259fbf733988e4b63fc7e6c6c6c867f`

### `L2-SACK-001`

- `rtl/ir_sack_codec.sv` — `bde58a1da521b38d7cdf6459c69d952e0bbc42738a91d4d417f3f45776b5346e`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_raw/r8d/p8d_sack_ack_aggregation_summary.json` — `2789797027ec4de5305acd562858b22a8138ee917e85602bc4e07a0833a0725f`

### `L2-SACK-002`

- `rtl/ir_ack_aggregator.sv` — `e2d27f15541d903a79b4f6fdb9e8d03ffbe6ab5d59940cab762bece76c5ba1c2`
- `sim/tb/tb_ir_sack_ack_aggregation.sv` — `cf7b1985d099d54b5fe3cd699466c1595c13dd2895d91657b408ccda91e2c6e5`
- `evidence/generated/p8e_raw/r8d/p8d_sack_ack_aggregation_summary.json` — `2789797027ec4de5305acd562858b22a8138ee917e85602bc4e07a0833a0725f`

### `L2-DUP-001`

- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `rtl/ir_selective_repeat_rx.sv` — `25b5cf6ff573ba01a31370bd44ae1bdd4d6367160e4d11b472cea17856a70cb4`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `L2-STALE-001`

- `rtl/ir_selective_repeat_tx.sv` — `4b8a88322ce0e25b7530b44294ef3511192d17cce2b385dcc6da15e521522c9c`
- `rtl/ir_selective_repeat_rx.sv` — `25b5cf6ff573ba01a31370bd44ae1bdd4d6367160e4d11b472cea17856a70cb4`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `L2-MIG-001`

- `rtl/ir_retry_migration.sv` — `53864a36ed5a041b1acab24645853faf0439a7e2577fcbb12ddbec7dcc0d9951`
- `sim/tb/tb_ir_scheduler_migration.sv` — `13d002591719507d5940ad98d9079f1fbba755f1d686a2e14db93ba1706bbfa7`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `L2-RETRY-001`

- `rtl/ir_selective_repeat_tx.sv` — `4b8a88322ce0e25b7530b44294ef3511192d17cce2b385dcc6da15e521522c9c`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `SCHED-001`

- `rtl/ir_health_weighted_scheduler.sv` — `f4b25acaf44ce3728abd0d51c6b7c509f695221d11a623cf3b02ae54d515d236`
- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `SCHED-002`

- `rtl/ir_health_weighted_scheduler.sv` — `f4b25acaf44ce3728abd0d51c6b7c509f695221d11a623cf3b02ae54d515d236`
- `sim/tb/tb_ir_scheduler_migration.sv` — `13d002591719507d5940ad98d9079f1fbba755f1d686a2e14db93ba1706bbfa7`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `SCHED-003`

- `rtl/ir_health_weighted_scheduler.sv` — `f4b25acaf44ce3728abd0d51c6b7c509f695221d11a623cf3b02ae54d515d236`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `AXIS-001`

- `rtl/ir_axis_tx_frontend.sv` — `961d7583f2493e54a3e23e74486de1fecf32da10ff28b85b9533236c5b7fb86f`
- `rtl/ir_axis_rx_backend.sv` — `7747c33d9b27a11a194e45ad895d6b0283f1e2f3626eb6c81845ad50c4b10539`
- `evidence/generated/p8e_raw/r8d/p8d_axis_backpressure_summary.json` — `2a74758cfd517a0212268c15410a0dfade805ac06304b030cecd9432a7def129`

### `DMA-001`

- `rtl/ir_dma_descriptor_model.sv` — `f4009747f8607c8f8bc3d400a092fcd06058a9b289806e8f6a03c5fcdf29eb81`
- `software/ps_driver/p8d_driver.h` — `5878e26abbb1c77c47004eba34819c7c4b64fe57048e3669b1ea0b5296018f6e`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `DMA-002`

- `rtl/ir_dma_descriptor_model.sv` — `f4009747f8607c8f8bc3d400a092fcd06058a9b289806e8f6a03c5fcdf29eb81`
- `sim/tb/tb_ir_dma_descriptor_ring.sv` — `b795dd33940fc639df971190d5c1bba0dc0d99bba6076e58753575c5fd008574`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `DMA-003`

- `rtl/ir_dma_descriptor_model.sv` — `f4009747f8607c8f8bc3d400a092fcd06058a9b289806e8f6a03c5fcdf29eb81`
- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `DMA-004`

- `rtl/ir_dma_descriptor_model.sv` — `f4009747f8607c8f8bc3d400a092fcd06058a9b289806e8f6a03c5fcdf29eb81`
- `software/ps_driver/p8d_driver.c` — `e233e5a7b7c7e3cf86305970ee95547982988ab1468eb688fe497841af0f88a1`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `RFAP-001`

- `tools/p8d_rfap_reference.py` — `9d319cd01abd8a6eb618d96824a73d4408915446e05e6fb804df830f9e24915d`
- `tests/vectors/p7_app_protocol_vectors.json` — `b1015c343dec626328a3b5a1295754b065c1d28a681c87ca71dcb533463d36df`
- `evidence/generated/p8e_raw/r8d/p8d_rfap_compatibility_summary.json` — `ba8b897d3b407ca7cb1c204923a2dcba8ef49c13397dc119f48e1b7d651c7e2e`

### `RFAP-002`

- `tools/p8d_rfap_reference.py` — `9d319cd01abd8a6eb618d96824a73d4408915446e05e6fb804df830f9e24915d`
- `docs/design/P8D_RFAP_VNEXT_COMPATIBILITY.md` — `6433a2467aeab13a94c4b72ee90cd5680ca1443eed6e67d932795fae9da56ad3`
- `evidence/generated/p8e_raw/r8d/p8d_rfap_compatibility_summary.json` — `ba8b897d3b407ca7cb1c204923a2dcba8ef49c13397dc119f48e1b7d651c7e2e`

### `PERF-MODEL-001`

- `scripts/model_p8d_airtime.py` — `9ead4a661d080895a449216d6d6b317d1ae8d8ebd9ea2949c90f261210462986`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` — `178093e79f912d194079a7d75cfb28d1e0858f0a0ba5ec824aafd1378cb5b9f1`

### `PERF-MODEL-002`

- `scripts/model_p8d_airtime.py` — `9ead4a661d080895a449216d6d6b317d1ae8d8ebd9ea2949c90f261210462986`
- `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` — `178093e79f912d194079a7d75cfb28d1e0858f0a0ba5ec824aafd1378cb5b9f1`

### `BUILD-001`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `rtl/top/ir_endpoint_core.sv` — `dbd1c089ca87f995ab659ab0f89882bb16a1e28257ae60e4d9fff64f5b330155`
- `evidence/generated/p8e_build_matrix_summary.json` — `6eb6204b8396ed3660b0fedd3aca99b20907ec639aeb6897c23308289b5aab99`

### `BUILD-002`

- `rtl/top/ir_fixed_endpoint_core.sv` — `e1e754b5f1ef909b60663f143975e5a34ce70ba70d9758d4e8df3d16ab80ccb4`
- `rtl/top/ir_rotating_endpoint_core.sv` — `61ef025deb381fdcde71bac75e21085911228c12ffafc348d37b65648e1afb0b`
- `evidence/generated/p8e_source_manifest_summary.json` — `2017ca460f21beb16539847f9f8f9a66e8b4a6cd269a5f07234a5cb7cf0a8e40`

### `TIMING-001`

- `scripts/vivado/run_p8e_build.tcl` — `659c4c4bcf7125b52dddc12165f454bc8cbb138b364434fd46dbf71b2698499a`
- `constraints/core/common_clocks.xdc` — `5729ef1fb8204366a15ca09cbdd7400cdaead4d5a7d4ed71f614946b88e17b58`
- `evidence/generated/p8e_build_matrix_summary.json` — `6eb6204b8396ed3660b0fedd3aca99b20907ec639aeb6897c23308289b5aab99`

### `TIMING-002`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `config/p8e_clock_reset.yaml` — `0b22a8073d494bdb78dc04b9832d55e27bd772572d1dad5c1b95b1010af769f2`
- `evidence/generated/p8e_timing_architecture_summary.json` — `a3b2d2bf6a61855a51805c1b8cae5aef6a7ff1575c880b6610fa6d055c0c315f`

### `TIMING-003`

- `constraints/core/common_clocks.xdc` — `5729ef1fb8204366a15ca09cbdd7400cdaead4d5a7d4ed71f614946b88e17b58`
- `scripts/check_p8e_constraints.py` — `e1e66ca031b8073ac6f8f7c985a60f4fca7536443be8f2a70be2a32138adbc61`
- `evidence/generated/p8e_constraint_audit_summary.json` — `fb42d2af50483781cd94a3af1492e7e31750954478a3fd8c2ed0b615de8e054e`

### `TIMING-004`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `scripts/run_p8e_build_matrix.py` — `1e24d24a34faad722b589fdf52bf5ed9939e2354104d98daab1fe67c80b0ff0e`
- `evidence/generated/p8e_build_matrix_summary.json` — `6eb6204b8396ed3660b0fedd3aca99b20907ec639aeb6897c23308289b5aab99`

### `CDC-001`

- `config/p8e_clock_reset.yaml` — `0b22a8073d494bdb78dc04b9832d55e27bd772572d1dad5c1b95b1010af769f2`
- `constraints/core/cdc_exceptions.xdc` — `a3123be01abc5815b31de4a67871512fa89b465be3013e0e9efae73d85250fab`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `16bb8404b62c95d2c47cd00667a9660a0b9685e03fe6d3a3fde58342134c4106`

### `CDC-002`

- `rtl/common/toggle_handshake.sv` — `27b7e5cbc7e7fba919fd6c379c1c8538af567d3b9ba3b6d92c686390a1e3fb9b`
- `rtl/common/async_fifo.sv` — `a969bcfee4c37d2e3ffc771987f4e3830561606bb74fc9dfbd8c59f69cd65d32`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `16bb8404b62c95d2c47cd00667a9660a0b9685e03fe6d3a3fde58342134c4106`

### `CDC-003`

- `rtl/common/reset_sync.sv` — `d75b79556cdc4be58fe3eba9d4dc5a7d59c44785978c517df92029c5096d75c4`
- `sim/tb/tb_p8e_cdc_reset_matrix.sv` — `c2944ce2f1c1ac1553ea818cdb6161d99ad7ee9b93d5f719888ca9521dbded2b`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `16bb8404b62c95d2c47cd00667a9660a0b9685e03fe6d3a3fde58342134c4106`

### `CDC-004`

- `sim/tb/tb_p8e_dual_endpoint.sv` — `6b60476c5c8277baa8f21e2405c36cfc89c5a68b72fb3732419d6501e35addee`
- `tools/p8e_dual_endpoint_reference.py` — `bb68400c6a52aa3498dc9e4e61ae6033ff53dc6a6b26491112dbca349fd42d08`
- `evidence/generated/p8e_dual_endpoint_sim_summary.json` — `0fac980958eda656bea4fdbb9ffc1d79b09ea809fa8bc0f2109e95c1f66cbb2a`

### `RDC-001`

- `config/p8e_clock_reset.yaml` — `0b22a8073d494bdb78dc04b9832d55e27bd772572d1dad5c1b95b1010af769f2`
- `sim/tb/tb_p8e_cdc_reset_matrix.sv` — `c2944ce2f1c1ac1553ea818cdb6161d99ad7ee9b93d5f719888ca9521dbded2b`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `16bb8404b62c95d2c47cd00667a9660a0b9685e03fe6d3a3fde58342134c4106`

### `DRC-001`

- `rtl/ir_shared_payload_store.sv` — `a4b44c58b862208127302e8e3bd67a5f5a405f2c0c9af6b1e38a54cc8e06a62a`
- `rtl/ir_tfdu_exact_duty_accountant.sv` — `05385eee22ad7ace59da7ced41296ce0480fcd0339d8dee3194534cc5af9cb2f`
- `evidence/generated/p8e_reset_bram_summary.json` — `f1824daed55ddbe1b38518bbacff1df151c6a5cf51c5cd835e18a4e2b1c45295`

### `DRC-002`

- `scripts/vivado/run_p8e_build.tcl` — `659c4c4bcf7125b52dddc12165f454bc8cbb138b364434fd46dbf71b2698499a`
- `scripts/run_p8e_build_matrix.py` — `1e24d24a34faad722b589fdf52bf5ed9939e2354104d98daab1fe67c80b0ff0e`
- `evidence/generated/p8e_build_matrix_summary.json` — `6eb6204b8396ed3660b0fedd3aca99b20907ec639aeb6897c23308289b5aab99`

### `RESOURCE-001`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `rtl/ir_p8d_resource_tops.sv` — `231a30033c7763a6e8b0daae07a924a4dc46ce3788b14d0a692d365dd9b37e98`
- `evidence/generated/p8e_resource_margin_summary.json` — `ec89ce55bb448580b220df65b3a247a471101cc5fea22072f1670b30cc3c9035`

### `RESOURCE-002`

- `rtl/top/z7010_2lane_dev_top.sv` — `fc937858f269a6db06ab5088e4a193df37f7c772171191391c3d569eaef619a4`
- `rtl/ir_p8d_resource_tops.sv` — `231a30033c7763a6e8b0daae07a924a4dc46ce3788b14d0a692d365dd9b37e98`
- `evidence/generated/p8e_resource_margin_summary.json` — `ec89ce55bb448580b220df65b3a247a471101cc5fea22072f1670b30cc3c9035`

### `RESOURCE-003`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `evidence/generated/p8e_resource_margin_summary.json` — `ec89ce55bb448580b220df65b3a247a471101cc5fea22072f1670b30cc3c9035`

### `AXIDMA-001`

- `rtl/platform/axi_dma_adapter.sv` — `7fded9593295a6a80d9dbf044f68815f8975913f36d9680c7c7e01007033037b`
- `docs/design/P8E_AXI_DMA_STATIC_INTEGRATION.md` — `ff09ab752575137f6c62a83255a5a9e6b9ecfe4f467c0fe9b11a45b5074c7b92`
- `evidence/generated/p8e_axi_dma_static_integration_summary.json` — `c495647cea7e8b22208973134eaf2185171f2fc02ec3104e2c6a357639241216`

### `AXIDMA-002`

- `rtl/platform/axi_dma_adapter.sv` — `7fded9593295a6a80d9dbf044f68815f8975913f36d9680c7c7e01007033037b`
- `sim/tb/tb_axi_dma_adapter.sv` — `0e13fcaaf8b8dbf905d75a7aec877d30ff73e9ad171e939d31cd7cd97f9220e2`
- `evidence/generated/p8e_axi_dma_static_integration_summary.json` — `c495647cea7e8b22208973134eaf2185171f2fc02ec3104e2c6a357639241216`

### `PROFILE-001`

- `constraints/active/PORT1.generated.xdc` — `f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344`
- `scripts/check_p8e_constraints.py` — `e1e66ca031b8073ac6f8f7c985a60f4fca7536443be8f2a70be2a32138adbc61`
- `evidence/generated/p8e_constraint_audit_summary.json` — `fb42d2af50483781cd94a3af1492e7e31750954478a3fd8c2ed0b615de8e054e`

### `PROFILE-002`

- `config/board_requirements/z7020_fixed_io_requirements.yaml` — `c75d8c7cf14c0760d8bca51eb6ee702e8677a3c4357a5f094f104e04e11482a0`
- `config/board_requirements/z7020_rotating_io_requirements.yaml` — `b45a6c72f5dfdac506645a5363806104face6d3e990502a26a2be43066856af2`
- `evidence/generated/p8e_io_budget_summary.json` — `ed7cdb4db15107d6623b7ecafe897ee133df88394f2b9133ad6f5f65c70f6f4f`

### `REPRO-001`

- `scripts/run_p8e_dual_target_gate.py` — `c70c96284643f07a7c3f13396a76a9931cecc8623027cf7c815d5be1b6430084`
- `scripts/run_p8e_build_matrix.py` — `1e24d24a34faad722b589fdf52bf5ed9939e2354104d98daab1fe67c80b0ff0e`
- `evidence/generated/p8e_evidence_consistency_summary.json` — `4ec3add3453d73bf7622d190cf50abc71ff496cfa2a93c028887744b5fcdf48a`
