# Requirement Traceability Matrix

> Generated from `config/project_requirements.yaml` by `scripts/generate_requirement_traceability.py`; do not edit by hand.

Canonical constraint: `PROJECT_CONSTRAINTS.txt` (`9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`).

```text
REQUIREMENT_COUNT: 183
PASS: 147
PENDING: 31
FAIL: 5
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
| `L2-ARQ-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p9_final_source_p8d_19bdeced/p8d_selective_repeat_rtl_summary.json` | Each endpoint direction uses bounded selective-repeat TX/RX windows. |
| `L2-ARQ-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P10-P8D-SOURCE-BINDING-REVERIFICATION` | `evidence/generated/p10_p8d_source_reverification/summary.json` | The shared global outstanding window supports at least 32 frames. |
| `L2-SEQ-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8e_raw/r8d/p8d_selective_repeat_rtl_summary.json` | Sequence width is at least 16 bits and modular wrap is bit-exact. |
| `L2-SACK-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SACK-ACK-AGGREGATION` | `evidence/generated/p8e_raw/r8d/p8d_sack_ack_aggregation_summary.json` | The negotiated SACK window supports at least 32 bits. |
| `L2-SACK-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P10-P8D-SOURCE-BINDING-REVERIFICATION` | `evidence/generated/p10_p8d_source_reverification/summary.json` | ACK aggregation has a bounded frame threshold and maximum delay. |
| `L2-DUP-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-PYTHON-REFERENCE-CAMPAIGN` | `evidence/generated/p8e_precompletion_reverification_summary.json` | A duplicate logical frame never commits or completes twice. |
| `L2-STALE-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p9_final_source_p8d_19bdeced/p8d_selective_repeat_rtl_summary.json` | Stale session/path data and ACK records are rejected. |
| `L2-MIG-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8e_precompletion_reverification_summary.json` | Only unacknowledged frames may migrate across eligible lanes or paths. |
| `L2-RETRY-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p9_final_source_p8d_19bdeced/p8d_selective_repeat_rtl_summary.json` | Retry count, timeout/backoff, and exhaustion are bounded. |
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
| `PERF-MODEL-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AIRTIME-BUDGET-MODEL` | `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` | The airtime model includes duty, framing, ACK, retry, handover, and descriptor overhead. The P10.1 extension also closes a complete dual-node streaming sensitivity model without changing the original P8D scope. |
| `PERF-MODEL-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AIRTIME-BUDGET-MODEL` | `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` | The 16 Mbit/s architecture target is explicitly evaluated without increasing duty. The P10.1 extension directly evaluates the current two-lane 4.0 Mbit/s-per-direction scale-equivalent target without increasing duty. |
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
| `P9-HW-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-02-IMMUTABLE-ARTIFACT-FREEZE` | `evidence/generated/p9_artifact_freeze_summary.json` | Immutable candidate, shutdown, XSA, BSP, runner, and ELF provenance is hash-bound. |
| `P9-HW-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-HW-002-SHUTDOWN` | `evidence/generated/p9_shutdown_summary.json` | Safe boot, shutdown-before, shutdown-on-exit, and shutdown-after are confirmed. |
| `P9-HW-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-HW-003` | `evidence/generated/p9_authorization_summary.json` | The formal run is bound to the current user authorization and immutable artifacts. |
| `P9-PHY-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-PHY-001` | `evidence/generated/p9_raw_lane_matrix_summary.json` | Fresh AB/BA raw counters pass for both logical lanes and four physical directions. |
| `P9-PHY-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-PHY-002` | `evidence/generated/p9_phy_4mbps_summary.json` | Lane 0 operates at the configured 4 Mbit/s raw PHY rate. |
| `P9-PHY-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-PHY-003` | `evidence/generated/p9_phy_4mbps_summary.json` | Lane 1 operates at the configured 4 Mbit/s raw PHY rate. |
| `P9-PHY-004` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-PHY-004` | `evidence/generated/p9_phy_4mbps_summary.json` | Both lanes concurrently provide 8 Mbit/s aggregate raw capability. |
| `P9-SAFE-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-SAFE-001` | `evidence/generated/p9_tfdu_safety_summary.json` | All four TFDU paths observe the hardware startup wait before readiness. |
| `P9-SAFE-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-SAFE-002` | `evidence/generated/p9_tfdu_safety_summary.json` | Hardware runtime continuous-high telemetry remains at or below one microsecond. |
| `P9-SAFE-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-SAFE-003` | `evidence/generated/p9_tfdu_safety_summary.json` | Exact 1 ms rolling-duty runtime accounting remains below the strict hard limit and design target. |
| `P9-SAFE-004` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-SAFE-004` | `evidence/generated/p9_tfdu_safety_summary.json` | Disarm reaches final TX kill, aborts the active train, and explicit re-arm does not resume it. |
| `P9-L2-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-L2-001` | `evidence/generated/p9_selective_repeat_summary.json` | The real optical runtime exercises a 32-outstanding selective-repeat window. |
| `P9-L2-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-L2-002` | `evidence/generated/p9_sack_ack_summary.json` | The real optical runtime exercises 32-bit SACK and bounded ACK aggregation. |
| `P9-L2-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-L2-003` | `evidence/generated/p9_sack_ack_summary.json` | Sequence wrap, loss, reorder, stale, CRC, duplicate, and retry recovery preserve exactly-once delivery. |
| `P9-L3-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-L3-001` | `evidence/generated/p9_scheduler_migration_summary.json` | The two-lane hardware scheduler runs single-lane, equal, and weighted profiles. |
| `P9-L3-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-L3-002` | `evidence/generated/p9_scheduler_migration_summary.json` | Unavailable, invalid-mapping, and duty-throttled lanes are isolated from scheduling. |
| `P9-L3-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-L3-003` | `evidence/generated/p9_scheduler_migration_summary.json` | Only unacknowledged work migrates to the healthy lane and clean acknowledged work never migrates. |
| `P9-DMA-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-DMA-001` | `evidence/generated/p9_dma_ddr_cache_summary.json` | The PS runtime uses the implemented AXI DMA scatter-gather engine and DDR buffers. |
| `P9-DMA-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-DMA-002` | `evidence/generated/p9_dma_ddr_cache_summary.json` | Cache flush, invalidate, barrier, cache-enabled, and cache-disabled ownership paths are exercised. |
| `P9-DMA-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-DMA-003` | `evidence/generated/p9_dma_ddr_cache_summary.json` | Each real DMA descriptor completes and is reclaimed exactly once without leak. |
| `P9-DMA-004` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-DMA-004` | `evidence/generated/p9_dma_ddr_cache_summary.json` | Idle/queued reset, abort, soft reset, stale completion, reboot, and recovery are verified. |
| `P9-RFAP-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-RFAP-001` | `evidence/generated/p9_rfap_runtime_summary.json` | RFAP v1 is parsed, reassembled, integrity checked, and atomically published at runtime. |
| `P9-RFAP-002` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-RFAP-002` | `evidence/generated/p9_rfap_runtime_summary.json` | RFAP vNext streaming is parsed and atomically published through the frozen PS/PL runtime. |
| `P9-RFAP-003` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-RFAP-003` | `evidence/generated/p9_rfap_runtime_summary.json` | Fresh A-to-B and B-to-A objects preserve CRC32, SHA-256, and zero partial publish. |
| `P9-PERF-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-PERF-001` | `evidence/generated/p9_performance_summary.json` | PS preparation, DMA, PL completion, integrity, frame, and application throughput are characterized. |
| `P9-SOAK-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-SOAK-001` | `evidence/generated/p9_stationary_30min_summary.json` | The exact 1800-second stationary two-lane formal soak completes without mandatory-gate violation. |
| `P9-EVID-001` | `PASS` | Z7010_2LANE_DEV | `P9` | `P9-EVID-001` | `evidence/generated/p9_evidence_consistency_summary.json` | The complete formal run has raw logs, immutable hashes, shutdown evidence, and consistent summaries. |
| `P9-CLOSEOUT-001` | `PASS` | REPOSITORY_POST_CHECKPOINT_CLOSEOUT | `P9_POST_CHECKPOINT_CLOSEOUT` | `P9-CLOSEOUT-001` | `evidence/generated/p9_post_checkpoint_closeout.json` | A completed P9 hardware run must have its current-run authorization marked consumed and false without changing the frozen P9 evidence checkpoint. |
| `P10-HW-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-A-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_a/stage_summary.json` | Role-bound fixed and rotating AX7020 artifacts complete safe boot and bounded shutdown. |
| `P10-PHY-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-B-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_b/stage_summary.json` | All four physical optical directions pass fresh raw-lane transfer and crosstalk isolation. |
| `P10-PHY-002` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-C-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_c/stage_summary.json` | Lane 0 and lane 1 each pass bidirectional 4 Mbit/s operation and concurrent 8 Mbit/s raw capability. |
| `P10-L2-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-D-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_d/stage_summary.json` | Selective repeat, 32-bit SACK, ACK aggregation, wrap, loss, reorder, duplicate, stale, and retry behavior pass. |
| `P10-DMA-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-E-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_e/stage_summary.json` | Both endpoints pass real AXI DMA scatter-gather, role-local DDR, cache ownership, reset, and descriptor accounting. |
| `P10-SYS-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-F-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_f/stage_summary.json` | Two independent PS runtimes and resets operate without shared RAM across the optical PS-PL-PHY-PL-PS path. |
| `P10-OBJ-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-F-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_f/stage_summary.json` | Fresh fixed-to-rotating and rotating-to-fixed objects preserve CRC32, SHA-256, and atomic exactly-once publication. |
| `P10-REC-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-G-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_g/stage_summary.json` | Endpoint reboot and reset recovery reject stale completion and deliver a fresh post-recovery object. |
| `P10-SCHED-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-H-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_h/stage_summary.json` | Lane selection, equal weighting, lane fault isolation, retry migration, and acknowledged-frame immobility pass. |
| `P10-PERF-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-I-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_i/stage_summary.json` | P10 characterizes PHY, frame, application, DMA, PS, and airtime performance without promoting the final-product threshold. |
| `P10-SOAK-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-J-HARDWARE` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_j/stage_summary.json` | The single formal stationary two-lane run remains clean for at least 1800 active seconds with no Ethernet or motion. |
| `P10-EVID-001` | `PASS` | P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET | `P10` | `P10-FASTTRACK-FINAL` | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` | One complete formal A-J run has consistent summaries, raw logs, SHA-256 manifest, and double final shutdown evidence. |
| `P10-CLOSEOUT-001` | `PASS` | P10_POST_ACCEPTANCE_CLOSEOUT | `P10_POST_ACCEPTANCE_CLOSEOUT` | `P10-CLOSEOUT-001` | `evidence/generated/p10_closeout_summary.json` | P10 post-acceptance closeout shall consume the current-run authorization, freeze Git/remote checkpoint metadata, preserve the scoped PASS, and execute no hardware action. |
| `P10-PERF-MEAS-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_AND_OBSERVABILITY | `P10_POST_ACCEPTANCE_ANALYSIS` | `P10-GOODPUT-MEASUREMENT-AUDIT` | `evidence/generated/p10_goodput_measurement_audit.json` | P10 performance fields shall have reproducible units, numerator, denominator, window, and provenance; unsuitable fields shall not be used for 8-lane or final-product projection. |
| `PERF-MEAS-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-MEASUREMENT-CONTRACT` | `evidence/generated/p10_1_measurement_contract.json` | Metric names, numerators, windows, units, classes, and provenance shall be explicit and schema-validated. |
| `PERF-MEAS-002` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-FINALIZER-FIX` | `evidence/generated/p10_1_finalizer_fix.json` | Diagnostic microtransfers shall never be selected as sustained application goodput or scaling evidence. |
| `PERF-MEAS-003` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-HISTORICAL-RECOMPUTE` | `evidence/generated/p10_1_historical_recompute.json` | Frozen P10 performance evidence shall be reproducibly recomputed without rewriting its historical summary. |
| `PERF-MEAS-004` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-TIMER-CROSSCHECK` | `evidence/generated/p10_1_timer_crosscheck.json` | Every formal case shall cross-check independent timer sources within the frozen tolerance or report a fixed boundary. |
| `PERF-FINAL-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-FINALIZER-FIX` | `evidence/generated/p10_1_finalizer_fix.json` | The metric finalizer shall deterministically select by metric, class, direction, eligibility, run, and aggregation rule. |
| `PERF-OBS-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-OBSERVABILITY` | `evidence/generated/p10_1_observability.json` | The PS service shall provide a preallocated nonblocking trace ring with generation, overflow, snapshot, and clear semantics. |
| `PERF-OBS-002` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-OBSERVABILITY` | `evidence/generated/p10_1_observability.json` | The PL data path shall provide a nonblocking event FIFO whose overflow cannot stall the fast path. |
| `PERF-OBS-003` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-OBSERVABILITY` | `evidence/generated/p10_1_observability.json` | Per-stage bytes, descriptors, stalls, queue, ACK, retry, duty, and direction counters shall use coherent snapshots. |
| `PERF-AUTO-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-AUTONOMOUS-PERF-MODE` | `evidence/generated/p10_1_autonomous_perf_mode.json` | Each endpoint shall support a target-resident deterministic performance data generator controlled at low frequency by the host. |
| `PERF-AUTO-002` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-AUTONOMOUS-PERF-MODE` | `evidence/generated/p10_1_autonomous_perf_mode.json` | The remote endpoint shall verify length, pattern, CRC32, SHA256, identity, generation, and exactly-once atomic commit. |
| `PERF-PIPE-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-MULTI-BUFFER-PIPELINE` | `evidence/generated/p10_1_buffer_pipeline.json` | The target service shall support multi-buffer staged ownership with explicit generation and no leak or double reclaim. |
| `PERF-PIPE-002` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-DESCRIPTOR-BATCHING` | `evidence/generated/p10_1_descriptor_batching.json` | Descriptor rings shall support bounded batching, wrap, exactly-once completion, and zero descriptor leaks. |
| `PERF-PIPE-003` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-DESCRIPTOR-BATCHING` | `evidence/generated/p10_1_descriptor_batching.json` | Cache maintenance shall be modeled and implemented as a batchable ownership boundary; non-cacheable mode is diagnostic only. |
| `PERF-STREAM-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-STREAMING-64M` | `evidence/generated/p10_1_streaming_64m.json` | The offline architecture shall stream a 64 MiB object across descriptors with incremental integrity and atomic publication. |
| `PERF-STREAM-002` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-STREAMING-64M` | `evidence/generated/p10_1_streaming_64m.json` | Abort, reset, duplicate, missing, stale, out-of-order, and wrap cases shall produce no partial, wrong, duplicate, or stale publication. |
| `HWPREP-P10_1-001` | `PASS` | P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY | `P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS` | `P10_1-HARDWARE-RUNNER-DRY-RUN` | `evidence/generated/p10_1_hardware_dry_run.json` | The future P10.1 hardware runner shall fail closed on authorization, identity, artifact, shutdown, lane, network, motion, and runtime errors. |
| `PERF-HW-001` | `PENDING` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE` | — | `docs/plans/P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE_PLAN.md` | Real AX7020 sustained application goodput shall meet at least 4.0 Mbit/s in each tested half-duplex direction under the frozen measurement contract. |
| `P11-READY-001` | `PENDING` | P11_HARDWARE_READINESS | `P11_NOT_STARTED` | — | `docs/P11_FIVE_MODULE_INVENTORY_PLAN.md` | P11 shall have a fifth compatible and fully inventoried TFDU6102 small board. |
| `P11-READY-002` | `PENDING` | P11_HARDWARE_READINESS | `P11_NOT_STARTED` | — | `docs/P11_FIXTURE_REQUIREMENTS.md` | P11 shall have accepted four-fixed-module and one-rotating-module fixtures bound to as-built geometry. |
| `P11-READY-003` | `PENDING` | P11_HARDWARE_READINESS | `P11_NOT_STARTED` | — | `docs/P11_ABZ_INPUT_REQUIREMENTS.md` | P11 shall have a selected and electrically verified ABZ source, pin/profile/XDC path, and phase/acquisition budget. |
| `P10_1_HW-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-CURRENT-RUN-AUTHORIZATION` | `evidence/generated/p10_1_hw_authorization_summary.json` | The P10.1 hardware campaign shall use a new immutable current-run authorization bound to the exact Goal, source, board identities, artifacts, limits, and shutdown policy. |
| `P10_1_HW-002` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-IMMUTABLE-ARTIFACTS` | `evidence/generated/p10_1_hw_artifact_summary.json` | Both AX7020 roles shall use independently routed, content-addressed performance bitstreams, XSA, BSP, and ELF built from one clean source commit. |
| `P10_1_TIME-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-TIMER-CROSSCHECK` | `evidence/generated/p10_1_hw_timer_summary.json` | PS and PL elapsed-time measurements for every sustained hardware stream shall cross-check within one percent, with host time retained only as an orchestration view. |
| `P10_1_METRIC-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-METRIC-SEMANTICS-AUTONOMY` | `evidence/generated/p10_1_hw_metric_semantics_summary.json` | Hardware application goodput shall count only remotely verified, atomically committed application bytes and shall exclude diagnostic microtransfers and host staging time. |
| `P10_1_AUTO-001` | `FAIL` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-METRIC-SEMANTICS-AUTONOMY` | `evidence/generated/p10_1_hw_metric_semantics_summary.json` | Sustained performance shall execute autonomously on the two boards, with the host absent from per-object and per-segment fast paths. |
| `P10_1_PIPE-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-SUSTAINED-PIPELINE` | `evidence/generated/p10_1_hw_pipeline_summary.json` | The target-resident runtime shall sustain a real multi-buffer, descriptor-batched, cache-enabled pipeline in both directions without per-object drain. |
| `P10_1_STREAM-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-STREAMING-64M-RECOVERY` | `evidence/generated/p10_1_hw_streaming_64m_summary.json` | A 64 MiB descriptor-chained F-to-R stream shall complete with incremental CRC32/SHA256 and one atomic application commit. |
| `P10_1_STREAM-002` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-STREAMING-64M-RECOVERY` | `evidence/generated/p10_1_hw_streaming_64m_summary.json` | A 64 MiB descriptor-chained R-to-F stream shall complete with incremental CRC32/SHA256 and one atomic application commit. |
| `P10_1_STREAM-003` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-STREAMING-64M-RECOVERY` | `evidence/generated/p10_1_hw_streaming_64m_summary.json` | Abort, PS reset, DMA reset, PL reset, duplicate, and stale-stream vectors shall never commit and shall be followed by a clean 64 MiB recovery stream without descriptor leakage. |
| `P10_1_PERF-001` | `FAIL` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-HALF-DUPLEX-4MBPS` | `evidence/generated/p10_1_hw_half_duplex_summary.json` | F-to-R two-lane half-duplex sustained application goodput shall be at least 4,000,000 bit/s for at least 300 seconds and 150 MiB committed. |
| `P10_1_PERF-002` | `FAIL` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-HALF-DUPLEX-4MBPS` | `evidence/generated/p10_1_hw_half_duplex_summary.json` | R-to-F two-lane half-duplex sustained application goodput shall be at least 4,000,000 bit/s for at least 300 seconds and 150 MiB committed. |
| `P10_1_PERF-003` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-HALF-DUPLEX-4MBPS` | `evidence/generated/p10_1_hw_half_duplex_summary.json` | Measured sustained goodput and its primary bottleneck shall be reconciled with the corrected physical-airtime model without exceeding the same-protocol ceiling. |
| `P10_1_XTALK-001` | `FAIL` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-CROSSTALK-4X4` | `evidence/generated/p10_1_hw_crosstalk_summary.json` | The stationary two-board setup shall produce a direct 4-by-4 TX-to-RX raw and framed crosstalk matrix with zero non-target CRC-valid false frames. |
| `P10_1_FD-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-1PLUS1-DIRECT-CAPABILITY` | `evidence/generated/p10_1_hw_1plus1_summary.json` | The campaign shall directly determine whether lane0 F-to-R and lane1 R-to-F simultaneous 1+1 operation is supported, and shall preserve an explicit nonblocking result when the frozen endpoint direction contract prevents it. |
| `P10_1_SOAK-001` | `FAIL` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-STATIONARY-30MIN` | `evidence/generated/p10_1_hw_stationary_30min_summary.json` | One complete 1800-second stationary performance run shall retain at least 4 Mbit/s in both formal directions with zero integrity, resource, retry, deadlock, or internal safety violations. |
| `P10_1_SAFE-001` | `PASS` | P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE | `P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE` | `P10_1-HW-SHUTDOWN-BOTH` | `evidence/generated/p10_1_hw_shutdown_summary.json` | Every stage and all error, timeout, interrupt, and normal exits shall end with independently verified shutdown of both bound AX7020 endpoints. |
| `OBS-LED-001` | `PASS` | P10_1_AX7020_PL_ACTIVITY_LED_OBSERVABILITY | `P10_1_AX7020_PL_ACTIVITY_LED_OFFLINE` | `P10_1-LED-MAPPING-001` | `evidence/generated/p10_1_led_offline_acceptance_leaf.json` | Both AX7020 roles shall use the same active-low PL LED mapping, with LED1/LED2 showing lane0 TX/RX and LED3/LED4 showing lane1 TX/RX on the exact official Bank 35 pins. |
| `OBS-LED-002` | `PASS` | P10_1_AX7020_PL_ACTIVITY_LED_OBSERVABILITY | `P10_1_AX7020_PL_ACTIVITY_LED_OFFLINE` | `P10_1-LED-EVENT-SEMANTICS-001` | `evidence/generated/p10_1_led_offline_acceptance_leaf.json` | TX indication shall tap the final role-local physical Txd output, while RX indication shall use only a completed CRC-valid per-lane frame event and shall remain available during receive-only operation. |
| `OBS-LED-003` | `PASS` | P10_1_AX7020_PL_ACTIVITY_LED_OBSERVABILITY | `P10_1_AX7020_PL_ACTIVITY_LED_OFFLINE` | `P10_1-LED-HOLD-SHUTDOWN-001` | `evidence/generated/p10_1_led_offline_acceptance_leaf.json` | A shared 1 ms tick shall provide an approximately 200 ms visual hold, with sustained activity remaining lit and reset, safety fault, or effective full shutdown immediately forcing all LEDs off and clearing every hold. |
| `OBS-LED-004` | `PASS` | P10_1_AX7020_PL_ACTIVITY_LED_OBSERVABILITY | `P10_1_AX7020_PL_ACTIVITY_LED_OFFLINE` | `P10_1-LED-NONINTERFERENCE-001` | `evidence/generated/p10_1_led_offline_acceptance_leaf.json` | The PL LED implementation shall be a pure monitor tap with no feedback, backpressure, or influence on Txd, SD, Mode, GLOBAL_PERMIT, TX kill, frame admission, reset, or fault handling. |
| `OBS-LED-HW-001` | `PENDING` | P10_1_AX7020_PL_ACTIVITY_LED_HARDWARE_FOLLOWUP | `PENDING_NEW_BITSTREAM_HARDWARE_VALIDATION` | — | `docs/hardware/P10_1_AX7020_PL_ACTIVITY_LED_DESIGN.md` | The LED-enabled fixed and rotating AX7020 bitstreams shall receive new direct hardware validation before their LED behavior or pre-existing P10/P10.1 functions are assigned a hardware PASS. |
| `P10_1R-ECHO-001` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Each TFDU module shall exclude frame admission whenever its own final physical Txd is active. |
| `P10_1R-ECHO-002` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Same-module accepted DATA frames shall remain exactly zero in the direct four-module campaign. |
| `P10_1R-ECHO-003` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Raw same-module Rxd activity shall remain synchronized, counted, timestamped, and atomically observable while protocol admission is blanked. |
| `P10_1R-ECHO-004` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | A local transmission on one module shall not blank receive admission on the other lane. |
| `P10_1R-ECHO-005` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | The final per-module post-TX guard shall be bounded and no shorter than the measured maximum echo tail plus deterministic margin. |
| `P10_1R-ECHO-006` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Every accepted CRC-valid DATA or ACK frame shall carry a logical lane identity matching the receiving physical lane. |
| `P10_1R-ACK-001` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | The two-lane bundle shall sustain a DATA burst and ACK threshold of at least 24 frames, with 32 as the frozen default. |
| `P10_1R-ACK-002` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Object boundaries shall not force an optical direction turnaround, ready round trip, receiver re-prime, or global pipeline drain. |
| `P10_1R-ACK-003` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | At least four objects or equivalent streaming segments shall remain prepared, DMA-owned, in flight, verifying, or committing across the continuous pipeline. |
| `P10_1R-HOST-001` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_OFFLINE_REVALIDATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | The host shall not participate in the per-object fast path; each direction shall use at most four blocking commands and at least 1000 segments per command. |
| `P10_1R-PERF-001` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Fixed-to-rotating two-lane half-duplex sustained application goodput shall be at least 4,000,000 bit/s. |
| `P10_1R-PERF-002` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Rotating-to-fixed two-lane half-duplex sustained application goodput shall be at least 4,000,000 bit/s. |
| `P10_1R-STREAM-001` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Fixed-to-rotating transfer shall complete five independent 64 MiB objects with matching incremental CRC32 and SHA256 and atomic commit. |
| `P10_1R-STREAM-002` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | Rotating-to-fixed transfer shall complete five independent 64 MiB objects with matching incremental CRC32 and SHA256 and atomic commit. |
| `P10_1R-SOAK-001` | `PENDING` | P10_1R_AX7020_2LANE_REMEDIATION | `P10_1R_HARDWARE_REMEDIATION` | — | `docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md` | One 1800-second stationary run shall retain both directional speed targets with zero integrity, protocol, descriptor, safety, deadlock, or shutdown errors. |

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
- `evidence/generated/p8e_p0_p8d_regression_summary.json` — `88b1a88b9e35d4e12bfc720410dce7e37607238ac4ea1e20b6987689971e1ab6`

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

- `config/project_state.json` — `9eb4d2f3a2e7c153c49a98316f87c5ad407e48187b36a374f2e0195b7083394e`
- `PROJECT_STATUS.md` — `2e78615520846385808b185557b027946c139233061f94d154098d1e8c169106`

### `P8A-TRACE-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `config/project_state.json` — `9eb4d2f3a2e7c153c49a98316f87c5ad407e48187b36a374f2e0195b7083394e`

### `P8A-EVID-001`

- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`
- `evidence/generated/p7_final_acceptance_summary.json` — `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b`
- `evidence/hardware/p7/p7_run_sequence_ledger.json` — `ab6138a0d6229985f127cf24fd418d2d4026a02a21b7776bdbb6be2fc608a2c4`

### `P8A-SCOPE-001`

- `config/project_state.json` — `9eb4d2f3a2e7c153c49a98316f87c5ad407e48187b36a374f2e0195b7083394e`
- `PROJECT_STATUS.md` — `2e78615520846385808b185557b027946c139233061f94d154098d1e8c169106`
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
- `evidence/generated/p8b_simulation_gate_summary.json` — `fe58521eb5dd9052ff6a65df3af1b875392d1044a0c8c5e16bf65167d5f2b863`

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
- `evidence/generated/p8e_p0_p8d_regression_summary.json` — `88b1a88b9e35d4e12bfc720410dce7e37607238ac4ea1e20b6987689971e1ab6`

### `PHY-SAFE-006`

- `rtl/ir_p8c_mapping_safety_adapter.sv` — `f4d2b8a58c02c7379b9c47e109d000b578fafb7d0f9d9578c7efa70ed5655928`
- `sim/tb/tb_p8c_profile_matrix.sv` — `d044e572bdc244b673ff298b56c442daaa3df0af8595f35086783577ede7a13f`
- `evidence/generated/p8c_physical_module_accounting_summary.json` — `0a8ecb742db212e4fb017618400668421d88a81e7077fe652707e2253c0df6a7`

### `L2-ARQ-001`

- `rtl/ir_selective_repeat_tx.sv` — `48baa0852b5beed2fca7009dbc7dbc9facbe343e2a85ee72a0d36ed46c0ac25f`
- `rtl/ir_selective_repeat_rx.sv` — `fd3ab2a4588951e217e70cb1a548354affcb5f76f7183e3257599aada8124028`
- `evidence/generated/p9_final_source_p8d_19bdeced/p8d_selective_repeat_rtl_summary.json` — `d05dc4bb99e184cb3a45a1eacc9973e79f3fbf95be4bb8127c3fdca4cef33389`

### `L2-ARQ-002`

- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `rtl/ir_data_plane_top.sv` — `8205959e9d3602224aec1dac2a476b3b150fdf86921f1ff545aa47f3d40b6eab`
- `evidence/generated/p10_p8d_source_reverification/summary.json` — `cfd688fe36572d929f57d50bfc9dba1a2cfdef8b1a5a8b2b6c29a6dd427a7a8f`

### `L2-SEQ-001`

- `rtl/ir_seq_math_pkg.sv` — `860c37a7565b19c7e2a1048c1552e12bba98662090f536a329258e69b292666e`
- `sim/tb/tb_ir_seq_math.sv` — `a01ab71e3891e4074a9b4f89719ced7561b39b83218ddf424965093d42608e5b`
- `evidence/generated/p8e_raw/r8d/p8d_selective_repeat_rtl_summary.json` — `cf333bf444f41f9a8d9af29987a7a1f78ef76ba84a9e65dc2f0fdc751b8d2418`

### `L2-SACK-001`

- `rtl/ir_sack_codec.sv` — `bde58a1da521b38d7cdf6459c69d952e0bbc42738a91d4d417f3f45776b5346e`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_raw/r8d/p8d_sack_ack_aggregation_summary.json` — `4e94640c66f08534a4baa422b214b3dab61381010a2f071e2f77674ee1322dc8`

### `L2-SACK-002`

- `rtl/ir_ack_aggregator.sv` — `bb149d456f09c006f6181fdd313de97e46a8fd21df1c1764f14d57079051dafa`
- `sim/tb/tb_ir_sack_ack_aggregation.sv` — `926ef09ea677487e14a9defd87419208bbfd97fee947527e3552e9ed9ad1c075`
- `evidence/generated/p10_p8d_source_reverification/summary.json` — `cfd688fe36572d929f57d50bfc9dba1a2cfdef8b1a5a8b2b6c29a6dd427a7a8f`

### `L2-DUP-001`

- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `rtl/ir_selective_repeat_rx.sv` — `fd3ab2a4588951e217e70cb1a548354affcb5f76f7183e3257599aada8124028`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `L2-STALE-001`

- `rtl/ir_selective_repeat_tx.sv` — `48baa0852b5beed2fca7009dbc7dbc9facbe343e2a85ee72a0d36ed46c0ac25f`
- `rtl/ir_selective_repeat_rx.sv` — `fd3ab2a4588951e217e70cb1a548354affcb5f76f7183e3257599aada8124028`
- `evidence/generated/p9_final_source_p8d_19bdeced/p8d_selective_repeat_rtl_summary.json` — `d05dc4bb99e184cb3a45a1eacc9973e79f3fbf95be4bb8127c3fdca4cef33389`

### `L2-MIG-001`

- `rtl/ir_retry_migration.sv` — `53864a36ed5a041b1acab24645853faf0439a7e2577fcbb12ddbec7dcc0d9951`
- `sim/tb/tb_ir_scheduler_migration.sv` — `a9f2fc05f9ef5184c775e94d6bc742262ed26dda37df319a86d3a8b492474c8d`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `L2-RETRY-001`

- `rtl/ir_selective_repeat_tx.sv` — `48baa0852b5beed2fca7009dbc7dbc9facbe343e2a85ee72a0d36ed46c0ac25f`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p9_final_source_p8d_19bdeced/p8d_selective_repeat_rtl_summary.json` — `d05dc4bb99e184cb3a45a1eacc9973e79f3fbf95be4bb8127c3fdca4cef33389`

### `SCHED-001`

- `rtl/ir_health_weighted_scheduler.sv` — `0513e5e22f235f5180725fecdb43320e58d624dbca30ffde895f7119ad8efa7a`
- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `SCHED-002`

- `rtl/ir_health_weighted_scheduler.sv` — `0513e5e22f235f5180725fecdb43320e58d624dbca30ffde895f7119ad8efa7a`
- `sim/tb/tb_ir_scheduler_migration.sv` — `a9f2fc05f9ef5184c775e94d6bc742262ed26dda37df319a86d3a8b492474c8d`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `SCHED-003`

- `rtl/ir_health_weighted_scheduler.sv` — `0513e5e22f235f5180725fecdb43320e58d624dbca30ffde895f7119ad8efa7a`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_precompletion_reverification_summary.json` — `d73981e29e772e026fcbf219daf5e23fc7ee90ec78f1c45a3602ff88812b5bdf`

### `AXIS-001`

- `rtl/ir_axis_tx_frontend.sv` — `961d7583f2493e54a3e23e74486de1fecf32da10ff28b85b9533236c5b7fb86f`
- `rtl/ir_axis_rx_backend.sv` — `7747c33d9b27a11a194e45ad895d6b0283f1e2f3626eb6c81845ad50c4b10539`
- `evidence/generated/p8e_raw/r8d/p8d_axis_backpressure_summary.json` — `02a9f08946cb227b956a98c5edc984076f76e3ae30f54bf1387fc04530507fcf`

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
- `evidence/generated/p8e_raw/r8d/p8d_rfap_compatibility_summary.json` — `50964a6185df19d6cb670cb633a2134c8fd9dbe0fd2afb0365f06c04353316ab`

### `RFAP-002`

- `tools/p8d_rfap_reference.py` — `9d319cd01abd8a6eb618d96824a73d4408915446e05e6fb804df830f9e24915d`
- `docs/design/P8D_RFAP_VNEXT_COMPATIBILITY.md` — `6433a2467aeab13a94c4b72ee90cd5680ca1443eed6e67d932795fae9da56ad3`
- `evidence/generated/p8e_raw/r8d/p8d_rfap_compatibility_summary.json` — `50964a6185df19d6cb670cb633a2134c8fd9dbe0fd2afb0365f06c04353316ab`

### `PERF-MODEL-001`

- `scripts/model_p8d_airtime.py` — `9ead4a661d080895a449216d6d6b317d1ae8d8ebd9ea2949c90f261210462986`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` — `9afa54ffcc485c0b2438f93eac9727a93260ac2849aa9d2b0bfc9f9877864d75`
- `evidence/generated/p10_1_performance_model.json` — `bb75f5ac204263646bc6c7dd999530d837f4563c38bfddfc11968d5b478bacb9`

### `PERF-MODEL-002`

- `scripts/model_p8d_airtime.py` — `9ead4a661d080895a449216d6d6b317d1ae8d8ebd9ea2949c90f261210462986`
- `evidence/generated/p8e_raw/r8d/p8d_airtime_budget_summary.json` — `9afa54ffcc485c0b2438f93eac9727a93260ac2849aa9d2b0bfc9f9877864d75`
- `evidence/generated/p10_1_performance_model.json` — `bb75f5ac204263646bc6c7dd999530d837f4563c38bfddfc11968d5b478bacb9`

### `BUILD-001`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `rtl/top/ir_endpoint_core.sv` — `dbd1c089ca87f995ab659ab0f89882bb16a1e28257ae60e4d9fff64f5b330155`
- `evidence/generated/p8e_build_matrix_summary.json` — `cf8ab50efe7dd3c11e72f2068b0f6ed985d3e2a8758eab09eab29f8fa2a9cc22`

### `BUILD-002`

- `rtl/top/ir_fixed_endpoint_core.sv` — `e1e754b5f1ef909b60663f143975e5a34ce70ba70d9758d4e8df3d16ab80ccb4`
- `rtl/top/ir_rotating_endpoint_core.sv` — `61ef025deb381fdcde71bac75e21085911228c12ffafc348d37b65648e1afb0b`
- `evidence/generated/p8e_source_manifest_summary.json` — `42d9044b0c505881793f5de02a54d02e6008eb280e26ede9a2a837814e07c5d1`

### `TIMING-001`

- `scripts/vivado/run_p8e_build.tcl` — `659c4c4bcf7125b52dddc12165f454bc8cbb138b364434fd46dbf71b2698499a`
- `constraints/core/common_clocks.xdc` — `5729ef1fb8204366a15ca09cbdd7400cdaead4d5a7d4ed71f614946b88e17b58`
- `evidence/generated/p8e_build_matrix_summary.json` — `cf8ab50efe7dd3c11e72f2068b0f6ed985d3e2a8758eab09eab29f8fa2a9cc22`

### `TIMING-002`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `config/p8e_clock_reset.yaml` — `0b22a8073d494bdb78dc04b9832d55e27bd772572d1dad5c1b95b1010af769f2`
- `evidence/generated/p8e_timing_architecture_summary.json` — `94f878bfea0585c4aee7a27f766760aba6dfda323f983ab6423bd1bb20e61f50`

### `TIMING-003`

- `constraints/core/common_clocks.xdc` — `5729ef1fb8204366a15ca09cbdd7400cdaead4d5a7d4ed71f614946b88e17b58`
- `scripts/check_p8e_constraints.py` — `e1e66ca031b8073ac6f8f7c985a60f4fca7536443be8f2a70be2a32138adbc61`
- `evidence/generated/p8e_constraint_audit_summary.json` — `c58b124bcb29e82661d322f83a73c4e65ac6c1a1dcb193cf21b105a0685f2f17`

### `TIMING-004`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `scripts/run_p8e_build_matrix.py` — `1e24d24a34faad722b589fdf52bf5ed9939e2354104d98daab1fe67c80b0ff0e`
- `evidence/generated/p8e_build_matrix_summary.json` — `cf8ab50efe7dd3c11e72f2068b0f6ed985d3e2a8758eab09eab29f8fa2a9cc22`

### `CDC-001`

- `config/p8e_clock_reset.yaml` — `0b22a8073d494bdb78dc04b9832d55e27bd772572d1dad5c1b95b1010af769f2`
- `constraints/core/cdc_exceptions.xdc` — `a3123be01abc5815b31de4a67871512fa89b465be3013e0e9efae73d85250fab`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `1c6ec904b518912f4eaeda817476fed426b60d193e3eb6fe832a10ac38011d64`

### `CDC-002`

- `rtl/common/toggle_handshake.sv` — `27b7e5cbc7e7fba919fd6c379c1c8538af567d3b9ba3b6d92c686390a1e3fb9b`
- `rtl/common/async_fifo.sv` — `a969bcfee4c37d2e3ffc771987f4e3830561606bb74fc9dfbd8c59f69cd65d32`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `1c6ec904b518912f4eaeda817476fed426b60d193e3eb6fe832a10ac38011d64`

### `CDC-003`

- `rtl/common/reset_sync.sv` — `d75b79556cdc4be58fe3eba9d4dc5a7d59c44785978c517df92029c5096d75c4`
- `sim/tb/tb_p8e_cdc_reset_matrix.sv` — `c2944ce2f1c1ac1553ea818cdb6161d99ad7ee9b93d5f719888ca9521dbded2b`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `1c6ec904b518912f4eaeda817476fed426b60d193e3eb6fe832a10ac38011d64`

### `CDC-004`

- `sim/tb/tb_p8e_dual_endpoint.sv` — `6b60476c5c8277baa8f21e2405c36cfc89c5a68b72fb3732419d6501e35addee`
- `tools/p8e_dual_endpoint_reference.py` — `bb68400c6a52aa3498dc9e4e61ae6033ff53dc6a6b26491112dbca349fd42d08`
- `evidence/generated/p8e_dual_endpoint_sim_summary.json` — `ac2557537dbd475b7999b70450525379237cc1fd6a550459cab226e461655d1d`

### `RDC-001`

- `config/p8e_clock_reset.yaml` — `0b22a8073d494bdb78dc04b9832d55e27bd772572d1dad5c1b95b1010af769f2`
- `sim/tb/tb_p8e_cdc_reset_matrix.sv` — `c2944ce2f1c1ac1553ea818cdb6161d99ad7ee9b93d5f719888ca9521dbded2b`
- `evidence/generated/p8e_cdc_rdc_summary.json` — `1c6ec904b518912f4eaeda817476fed426b60d193e3eb6fe832a10ac38011d64`

### `DRC-001`

- `rtl/ir_shared_payload_store.sv` — `a4b44c58b862208127302e8e3bd67a5f5a405f2c0c9af6b1e38a54cc8e06a62a`
- `rtl/ir_tfdu_exact_duty_accountant.sv` — `05385eee22ad7ace59da7ced41296ce0480fcd0339d8dee3194534cc5af9cb2f`
- `evidence/generated/p8e_reset_bram_summary.json` — `de22334479642394c6a7716beda9d097c4921bb8c9eaf1cfb1b9aa7cc537d180`

### `DRC-002`

- `scripts/vivado/run_p8e_build.tcl` — `659c4c4bcf7125b52dddc12165f454bc8cbb138b364434fd46dbf71b2698499a`
- `scripts/run_p8e_build_matrix.py` — `1e24d24a34faad722b589fdf52bf5ed9939e2354104d98daab1fe67c80b0ff0e`
- `evidence/generated/p8e_build_matrix_summary.json` — `cf8ab50efe7dd3c11e72f2068b0f6ed985d3e2a8758eab09eab29f8fa2a9cc22`

### `RESOURCE-001`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `rtl/ir_p8d_resource_tops.sv` — `ef32ee89fa2fceb43c34294976bb2166bf61c49cb601c2a698af8208851ac110`
- `evidence/generated/p8e_resource_margin_summary.json` — `c759b29fbf1907567c2a98e26de0695223d01845f58306ea47db32e5f117c4f8`

### `RESOURCE-002`

- `rtl/top/z7010_2lane_dev_top.sv` — `fc937858f269a6db06ab5088e4a193df37f7c772171191391c3d569eaef619a4`
- `rtl/ir_p8d_resource_tops.sv` — `ef32ee89fa2fceb43c34294976bb2166bf61c49cb601c2a698af8208851ac110`
- `evidence/generated/p8e_resource_margin_summary.json` — `c759b29fbf1907567c2a98e26de0695223d01845f58306ea47db32e5f117c4f8`

### `RESOURCE-003`

- `config/p8e_build_matrix.yaml` — `5835f796b3d81f5eccf52d06151f432414dc241437ae176328484e8cf7edc502`
- `evidence/generated/p8e_resource_margin_summary.json` — `c759b29fbf1907567c2a98e26de0695223d01845f58306ea47db32e5f117c4f8`

### `AXIDMA-001`

- `rtl/platform/axi_dma_adapter.sv` — `7fded9593295a6a80d9dbf044f68815f8975913f36d9680c7c7e01007033037b`
- `docs/design/P8E_AXI_DMA_STATIC_INTEGRATION.md` — `ff09ab752575137f6c62a83255a5a9e6b9ecfe4f467c0fe9b11a45b5074c7b92`
- `evidence/generated/p8e_axi_dma_static_integration_summary.json` — `509e428b72c56575791800863d7fa8956f504dc8a69b06f311e8ca34ed1612f2`

### `AXIDMA-002`

- `rtl/platform/axi_dma_adapter.sv` — `7fded9593295a6a80d9dbf044f68815f8975913f36d9680c7c7e01007033037b`
- `sim/tb/tb_axi_dma_adapter.sv` — `0e13fcaaf8b8dbf905d75a7aec877d30ff73e9ad171e939d31cd7cd97f9220e2`
- `evidence/generated/p8e_axi_dma_static_integration_summary.json` — `509e428b72c56575791800863d7fa8956f504dc8a69b06f311e8ca34ed1612f2`

### `PROFILE-001`

- `constraints/active/PORT1.generated.xdc` — `f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344`
- `scripts/check_p8e_constraints.py` — `e1e66ca031b8073ac6f8f7c985a60f4fca7536443be8f2a70be2a32138adbc61`
- `evidence/generated/p8e_constraint_audit_summary.json` — `c58b124bcb29e82661d322f83a73c4e65ac6c1a1dcb193cf21b105a0685f2f17`

### `PROFILE-002`

- `config/board_requirements/z7020_fixed_io_requirements.yaml` — `c75d8c7cf14c0760d8bca51eb6ee702e8677a3c4357a5f094f104e04e11482a0`
- `config/board_requirements/z7020_rotating_io_requirements.yaml` — `b45a6c72f5dfdac506645a5363806104face6d3e990502a26a2be43066856af2`
- `evidence/generated/p8e_io_budget_summary.json` — `880b91789f72cc6910a9404186374cebf64738e2bbe0e3762133f545f29ac2fc`

### `REPRO-001`

- `scripts/run_p8e_dual_target_gate.py` — `95d39ae4681019b1e00e4bccbc39d4ea492361cba5fd52cf4aabe04ad42047b5`
- `scripts/run_p8e_build_matrix.py` — `1e24d24a34faad722b589fdf52bf5ed9939e2354104d98daab1fe67c80b0ff0e`
- `evidence/generated/p8e_evidence_consistency_summary.json` — `a8a6ce3923d43b298bc2b83922ac76901148a7d3098be5e9720fb2502dbfd07f`

### `P9-HW-001`

- `evidence/generated/p9_artifact_freeze_summary.json` — `ed030b098778bc9a5b8300cdeaecf6415e82d138a50b5955fcd4e2d0625b6bf6`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-HW-002`

- `evidence/generated/p9_shutdown_summary.json` — `b941ab88477ab5950b90aee5af71ffe31e292aca08d0ee4202c52efc788c3788`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-HW-003`

- `evidence/generated/p9_authorization_summary.json` — `dba87d0213e46ce213589e4a6f6cc5127f827f4c836698039388d76e035efcca`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-PHY-001`

- `evidence/generated/p9_raw_lane_matrix_summary.json` — `6e0a485539625bb9fb3a5a0c10414fdb2756d4c551e70584161bec37ec5120ac`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-PHY-002`

- `evidence/generated/p9_phy_4mbps_summary.json` — `cd3bfd4d3e80d25fa26f1b3b0227f3022f061451b99d32c49ebffba85090e1d3`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-PHY-003`

- `evidence/generated/p9_phy_4mbps_summary.json` — `cd3bfd4d3e80d25fa26f1b3b0227f3022f061451b99d32c49ebffba85090e1d3`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-PHY-004`

- `evidence/generated/p9_phy_4mbps_summary.json` — `cd3bfd4d3e80d25fa26f1b3b0227f3022f061451b99d32c49ebffba85090e1d3`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-SAFE-001`

- `evidence/generated/p9_tfdu_safety_summary.json` — `a47851869324028271aff095a1560df30842d7fef3e9ad089f6f4b5ac94067e5`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-SAFE-002`

- `evidence/generated/p9_tfdu_safety_summary.json` — `a47851869324028271aff095a1560df30842d7fef3e9ad089f6f4b5ac94067e5`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-SAFE-003`

- `evidence/generated/p9_tfdu_safety_summary.json` — `a47851869324028271aff095a1560df30842d7fef3e9ad089f6f4b5ac94067e5`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-SAFE-004`

- `evidence/generated/p9_tfdu_safety_summary.json` — `a47851869324028271aff095a1560df30842d7fef3e9ad089f6f4b5ac94067e5`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-L2-001`

- `evidence/generated/p9_selective_repeat_summary.json` — `5d509307281ba62c12219813ec4ae4460cbee70936eec4e79b5c028c7c3a7d99`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-L2-002`

- `evidence/generated/p9_sack_ack_summary.json` — `c678044a4035ee9450bb0224a817d36a86287360ce04d006a6d5a08368b3ebba`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-L2-003`

- `evidence/generated/p9_sack_ack_summary.json` — `c678044a4035ee9450bb0224a817d36a86287360ce04d006a6d5a08368b3ebba`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-L3-001`

- `evidence/generated/p9_scheduler_migration_summary.json` — `71d83c1a2286267f0dc6a52fa508e7212732d8a2807012820357f045560dd4ae`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-L3-002`

- `evidence/generated/p9_scheduler_migration_summary.json` — `71d83c1a2286267f0dc6a52fa508e7212732d8a2807012820357f045560dd4ae`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-L3-003`

- `evidence/generated/p9_scheduler_migration_summary.json` — `71d83c1a2286267f0dc6a52fa508e7212732d8a2807012820357f045560dd4ae`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-DMA-001`

- `evidence/generated/p9_dma_ddr_cache_summary.json` — `99c825017f5c1b33621a326d4fb4c82909069619ab67d2ba1d5d2c8d428f986a`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-DMA-002`

- `evidence/generated/p9_dma_ddr_cache_summary.json` — `99c825017f5c1b33621a326d4fb4c82909069619ab67d2ba1d5d2c8d428f986a`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-DMA-003`

- `evidence/generated/p9_dma_ddr_cache_summary.json` — `99c825017f5c1b33621a326d4fb4c82909069619ab67d2ba1d5d2c8d428f986a`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-DMA-004`

- `evidence/generated/p9_dma_ddr_cache_summary.json` — `99c825017f5c1b33621a326d4fb4c82909069619ab67d2ba1d5d2c8d428f986a`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-RFAP-001`

- `evidence/generated/p9_rfap_runtime_summary.json` — `77a72e67561febdbbea062a65ec9f95670dc5da9ddf0fcd02e9f256567686412`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-RFAP-002`

- `evidence/generated/p9_rfap_runtime_summary.json` — `77a72e67561febdbbea062a65ec9f95670dc5da9ddf0fcd02e9f256567686412`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-RFAP-003`

- `evidence/generated/p9_rfap_runtime_summary.json` — `77a72e67561febdbbea062a65ec9f95670dc5da9ddf0fcd02e9f256567686412`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-PERF-001`

- `evidence/generated/p9_performance_summary.json` — `a709f75441a8abb6384a90f3c557f781309673536363e0daa22287d55ccb7cef`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-SOAK-001`

- `evidence/generated/p9_stationary_30min_summary.json` — `66e53376d759ecb3a7dab95b13ed3f194ca67577412a457cb7f72cb6eb7e6a10`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-EVID-001`

- `evidence/generated/p9_evidence_consistency_summary.json` — `6d0ac181bb47cafdc7906319784f46275407030a52144ab9a48dc16994eacfd6`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308/ir_p9_z7010_2lane_candidate.bit` — `ac75bfe61bfc639d6411462980ad2406293bd3054d8d5f2063879a78bb75d308`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8/ir_p9_shutdown_z7010.bit` — `a116b0153c0001d0d881b404f09ab33e689693c379bbccc4daa36f17f5d82ed8`
- `artifacts/p9/6d88b7854219c8b514ef36109a456ffbda4972d8/2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1/p9_runtime.elf` — `2e235a0ccc365133985f2d569784500f23ea57a8a0470c9c732ad0efdf2637b1`

### `P9-CLOSEOUT-001`

- `evidence/generated/p9_post_checkpoint_closeout.json` — `c886c3ee1d402f6c992190b0651edad388923ad625210f4c4b1afe933fb184a4`
- `evidence/generated/p9_git_checkpoint_metadata.json` — `28e6becb22d548d17957f78e0eb793a0022e9c25816619def4ddcf7b1f4d6116`

### `P10-HW-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_a/stage_summary.json` — `0660b549af14f4e0e21c424dfc92e3f15958f288d43501df75b6c7bc97fa4ebc`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`
- `config/p10_fasttrack_current_run_authorization.json` — `850c4fa46f38d32745585bf5c3bc3643b4f069f68a1b1bc571eb0c98fac69c83`

### `P10-PHY-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_b/stage_summary.json` — `839b5c6bec674dabc1787021cd45fcf70477d23ac2e97d0dd78fdabf6e959a0f`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-PHY-002`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_c/stage_summary.json` — `3a10f3ff157b21084f68934996b837947d00117888cbdc38a00fb6ef2e3d2c06`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-L2-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_d/stage_summary.json` — `622d8ed1be39346c9275d0e9e16291d875ade8941c72c28ba453cae6b066949d`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-DMA-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_e/stage_summary.json` — `60a21256df4c353eb50dcfd3f5000aa17ddcfec30fdb21346126e1320e0e182f`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-SYS-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_f/stage_summary.json` — `44b6e42a043445ab9f1de8ee66bb8eb66d84662a02bcb2009bef0940d2cc0e8d`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`
- `evidence/generated/p10_dual_endpoint_architecture_audit.json` — `70a2aa0925d33a730d3d76c7e1c7b0cda13a079ad119e990ff32908aeb05e653`

### `P10-OBJ-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_f/stage_summary.json` — `44b6e42a043445ab9f1de8ee66bb8eb66d84662a02bcb2009bef0940d2cc0e8d`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-REC-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_g/stage_summary.json` — `231654f44dfa300848aaeba2ddddde499b40e4ad956895da78da047b8787954d`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-SCHED-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_h/stage_summary.json` — `820e6a1bb0615f730231e24635fe0ce3ca0dda8a036dd5ec55dbda27dd78daec`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-PERF-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_i/stage_summary.json` — `ed6fdd822e761abee823a2989206fb21bf2549ed3781fb760782afd6beee1bbc`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-SOAK-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_j/stage_summary.json` — `f799b659b2f1a3502d7fa6544d49bae61b443420a0725df1bec451ae44ffd6f3`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-EVID-001`

- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-CLOSEOUT-001`

- `evidence/generated/p10_closeout_summary.json` — `fce819b60643705399a6318536c2f11a828bdfb1318c71794f0e212fdacc170b`
- `evidence/generated/p10_git_checkpoint_metadata.json` — `4f7d41b033372dd77aa41b23698a66b0c5c8616684b1a4debafacc550cc96a18`
- `evidence/generated/p10_remote_push_summary.json` — `56228b0a867d2360b6d85d4f68b2657230c5fc5b63a53e51533ce076c6f3b062`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/orchestrator_result.json` — `ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/final/run_evidence_sha256_manifest.json` — `2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281`

### `P10-PERF-MEAS-001`

- `evidence/generated/p10_goodput_measurement_audit.json` — `e24039778e5aafa8fc59ece1fc699ba33fcbe5d239ff64eea3d25e3ab7a36d14`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_i/stage_summary.json` — `ed6fdd822e761abee823a2989206fb21bf2549ed3781fb760782afd6beee1bbc`
- `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_j/stage_summary.json` — `f799b659b2f1a3502d7fa6544d49bae61b443420a0725df1bec451ae44ffd6f3`
- `scripts/p10_hardware_runtime.py` — `ac13ca787d765207ec5e5e39101e353a38d86d35e065b2bd05d8d026c3acb099`
- `software/ps_driver/p9_runtime_main.c` — `3839dd4c4c5c4f70adee1f0dd07bf3661a4be32179fff4d1a2ff76c0d22d3679`
- `config/performance/p10_1_measurement_contract.yaml` — `5d5e3abbb3579b0c9c7a2021a261bc3f905eb131dda6a8130aae85d1f74fc9d1`
- `docs/plans/P10_1_DUAL_NODE_PERFORMANCE_AND_OBSERVABILITY_PLAN.md` — `3ba81b88ffce572df2de038568485aaeec473283e8e6c0cbfec53c4614f1ed74`
- `evidence/generated/p10_goodput_runtime_source_reverification.json` — `9eb81c5238ee93d312802200f2581072961de695304c792e6d4d6762b39b7a0f`

### `PERF-MEAS-001`

- `evidence/generated/p10_1_measurement_contract.json` — `749c3a1b4dc726c0b9150fcee92ac85b7dcb467ff75f2a062e704854c8f8e9e9`

### `PERF-MEAS-002`

- `evidence/generated/p10_1_finalizer_fix.json` — `8655b9d0848c8fd9a9609af660f368208b0555ffd35f3d48c2da9bdcc59dfd0e`

### `PERF-MEAS-003`

- `evidence/generated/p10_1_historical_recompute.json` — `2505a0ade4eb36c2318ce7831153557fb569f344027aa1729d16965a22ff1755`

### `PERF-MEAS-004`

- `evidence/generated/p10_1_timer_crosscheck.json` — `6fa0c12bf125dc9031ce20a39599ce59bbeaf18135bbc38c6436e888e9ec624e`

### `PERF-FINAL-001`

- `evidence/generated/p10_1_finalizer_fix.json` — `8655b9d0848c8fd9a9609af660f368208b0555ffd35f3d48c2da9bdcc59dfd0e`

### `PERF-OBS-001`

- `evidence/generated/p10_1_observability.json` — `3feb851e0c8f724a0e8e801baaafe557667d2cb1d1db1945023f108b84657c92`

### `PERF-OBS-002`

- `evidence/generated/p10_1_observability.json` — `3feb851e0c8f724a0e8e801baaafe557667d2cb1d1db1945023f108b84657c92`

### `PERF-OBS-003`

- `evidence/generated/p10_1_observability.json` — `3feb851e0c8f724a0e8e801baaafe557667d2cb1d1db1945023f108b84657c92`

### `PERF-AUTO-001`

- `evidence/generated/p10_1_autonomous_perf_mode.json` — `fa30f67bf016890a7b4590fde588a555101d4d6a662196af908c142e4021a19e`

### `PERF-AUTO-002`

- `evidence/generated/p10_1_autonomous_perf_mode.json` — `fa30f67bf016890a7b4590fde588a555101d4d6a662196af908c142e4021a19e`

### `PERF-PIPE-001`

- `evidence/generated/p10_1_buffer_pipeline.json` — `a11b0c745e64a7a74bbc4f9c70e7b70d9ea32ea79db98d0e727e006bc6ae0f5c`

### `PERF-PIPE-002`

- `evidence/generated/p10_1_descriptor_batching.json` — `51c578bd5e711a1679a448508d49500065cf2c5eabecd3fbdf177967e8c330e1`

### `PERF-PIPE-003`

- `evidence/generated/p10_1_descriptor_batching.json` — `51c578bd5e711a1679a448508d49500065cf2c5eabecd3fbdf177967e8c330e1`

### `PERF-STREAM-001`

- `evidence/generated/p10_1_streaming_64m.json` — `d7e8406389acec94ad2e082bc0ffd8b536d64a65a3f03c14429d5065978f722a`

### `PERF-STREAM-002`

- `evidence/generated/p10_1_streaming_64m.json` — `d7e8406389acec94ad2e082bc0ffd8b536d64a65a3f03c14429d5065978f722a`

### `HWPREP-P10_1-001`

- `evidence/generated/p10_1_hardware_dry_run.json` — `1fe81b4a9222f9b44c2e03b6e237ae250912017a6e1b5083913291021441e27d`

### `P10_1_HW-001`

- `evidence/generated/p10_1_hw_authorization_summary.json` — `e7cb69cde20c6c7155adbe22041da7ed6564918725a3f8b7dacd6cb931ca7ba5`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_HW-002`

- `evidence/generated/p10_1_hw_artifact_summary.json` — `2d3d61877c178d8eb5ffa31e2d99914ba204cd7498983e6b277506ecf7741581`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/7f7f6cc154b3a50bd6c37f3fe0d0fddb867f585065616c7cf173952081fd94a1/p10_ax7020_fixed_functional.xsa` — `7f7f6cc154b3a50bd6c37f3fe0d0fddb867f585065616c7cf173952081fd94a1`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8/p10_ax7020_fixed_bsp.zip` — `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10/c96f85544f9f5815b205045f7ddac0acbd43cc17681c0679de82919438cb112b/d849da80c485519ae6300398cdf0b09dc5838941bd14bdf71cb26c01ec9e3fe3/p10_ax7020_fixed_shutdown.bit` — `d849da80c485519ae6300398cdf0b09dc5838941bd14bdf71cb26c01ec9e3fe3`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/89d766c05a960061d366a7a58812dc59b23054d2d0dcb37abc26155c04a13aea/p10_ax7020_rotating_functional.xsa` — `89d766c05a960061d366a7a58812dc59b23054d2d0dcb37abc26155c04a13aea`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5/p10_ax7020_rotating_bsp.zip` — `d46f9574d64bc8a464f3cc60392ff1bee2c44fd841bb4ae31df185ca14c868a5`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10/c794ee8c8aad8103a861780cc49d36fa2cf57f03b5982763f640ef09cd54a01d/cf269e67f2f7aa246b792d5c378168e10913d2af10ccd5dcd5a97b62f679b148/p10_ax7020_rotating_shutdown.bit` — `cf269e67f2f7aa246b792d5c378168e10913d2af10ccd5dcd5a97b62f679b148`

### `P10_1_TIME-001`

- `evidence/generated/p10_1_hw_timer_summary.json` — `729dc59679cd5f32cf30e1ec1e42ec44ec85661611f31189aedd9dfb514e20d6`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_METRIC-001`

- `evidence/generated/p10_1_hw_metric_semantics_summary.json` — `6e433a5ce0eb9cac2e8b5bf9e4f0ff4cd983e64e1c41048b1e72094da3804f9c`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_PIPE-001`

- `evidence/generated/p10_1_hw_pipeline_summary.json` — `b759120fff315e82efc34d2383b49be7e85d237357a6b40e199556517dac986e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_STREAM-001`

- `evidence/generated/p10_1_hw_streaming_64m_summary.json` — `fbd8305413f6ac78aed2a1c0deb938e8231fb05215920d75e3f1407f774cc555`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_STREAM-002`

- `evidence/generated/p10_1_hw_streaming_64m_summary.json` — `fbd8305413f6ac78aed2a1c0deb938e8231fb05215920d75e3f1407f774cc555`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_STREAM-003`

- `evidence/generated/p10_1_hw_streaming_64m_summary.json` — `fbd8305413f6ac78aed2a1c0deb938e8231fb05215920d75e3f1407f774cc555`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_PERF-003`

- `evidence/generated/p10_1_hw_half_duplex_summary.json` — `2f10fbc77ac2b667ce835fa174ab21b3d3717b940f0291860bca6e04e6e01e19`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_FD-001`

- `evidence/generated/p10_1_hw_1plus1_summary.json` — `90ebb7a7a94b1d7adf9c8abc5873e050a0976e43fa93aad61258f5afb92a8bca`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `P10_1_SAFE-001`

- `evidence/generated/p10_1_hw_shutdown_summary.json` — `e6ea3ba32352df1184ec709a1e15e4fa6f44dd9abfd76c5d683f546f8ccf41ae`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728/p10_fixed_runtime.elf` — `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e/p10_ax7020_fixed_functional.bit` — `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0/p10_rotating_runtime.elf` — `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- `artifacts/p10_1/bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1/9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f/p10_ax7020_rotating_functional.bit` — `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- `config/hardware/p10_active_wiring.yaml` — `64022daa974e7c848b037da837180b1051a05ca946643fd4b185d9ff74c5540f`

### `OBS-LED-001`

- `evidence/generated/p10_1_led_offline_acceptance_leaf.json` — `d3be7a623810c9878b201d9e16d1174de909701b25ccc62440dc1db0b029c422`

### `OBS-LED-002`

- `evidence/generated/p10_1_led_offline_acceptance_leaf.json` — `d3be7a623810c9878b201d9e16d1174de909701b25ccc62440dc1db0b029c422`

### `OBS-LED-003`

- `evidence/generated/p10_1_led_offline_acceptance_leaf.json` — `d3be7a623810c9878b201d9e16d1174de909701b25ccc62440dc1db0b029c422`

### `OBS-LED-004`

- `evidence/generated/p10_1_led_offline_acceptance_leaf.json` — `d3be7a623810c9878b201d9e16d1174de909701b25ccc62440dc1db0b029c422`
