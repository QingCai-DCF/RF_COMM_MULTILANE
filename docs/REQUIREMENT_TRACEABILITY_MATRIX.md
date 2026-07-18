# Requirement Traceability Matrix

> Generated from `config/project_requirements.yaml` by `scripts/generate_requirement_traceability.py`; do not edit by hand.

Canonical constraint: `PROJECT_CONSTRAINTS.txt` (`9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`).

```text
REQUIREMENT_COUNT: 64
PASS: 53
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
| `PHY-SAFE-004` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-RTL-EXACT-DUTY` | `evidence/generated/p8c_exact_sliding_duty_rtl_summary.json` | Each physical module satisfies exact arbitrary-alignment 1000 us strict <20% duty with <=18% target admission. |
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
| `PHY-SAFE-005` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-HISTORY-COOLDOWN` | `evidence/generated/p8c_exact_sliding_duty_rtl_summary.json` | Duty-history invalidation requires at least 1000 us all-TX-low cooldown before reuse. |
| `PHY-SAFE-006` | `PASS` | P8C_MULTI_PROFILE_OFFLINE | `P8C` | `P8C-PHYSICAL-MODULE-ACCOUNTING` | `evidence/generated/p8c_physical_module_accounting_summary.json` | Rolling-duty state is bound to physical-module identity and survives lane, path, and permit transitions. |
| `L2-ARQ-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8d_selective_repeat_rtl_summary.json` | Each endpoint direction uses bounded selective-repeat TX/RX windows. |
| `L2-ARQ-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-CANONICAL-CONFIG` | `evidence/generated/p8d_data_plane_config_summary.json` | The shared global outstanding window supports at least 32 frames. |
| `L2-SEQ-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8d_selective_repeat_rtl_summary.json` | Sequence width is at least 16 bits and modular wrap is bit-exact. |
| `L2-SACK-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SACK-ACK-AGGREGATION` | `evidence/generated/p8d_sack_ack_aggregation_summary.json` | The negotiated SACK window supports at least 32 bits. |
| `L2-SACK-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SACK-ACK-AGGREGATION` | `evidence/generated/p8d_sack_ack_aggregation_summary.json` | ACK aggregation has a bounded frame threshold and maximum delay. |
| `L2-DUP-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-PYTHON-REFERENCE-CAMPAIGN` | `evidence/generated/p8d_selective_repeat_reference_summary.json` | A duplicate logical frame never commits or completes twice. |
| `L2-STALE-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8d_selective_repeat_rtl_summary.json` | Stale session/path data and ACK records are rejected. |
| `L2-MIG-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8d_scheduler_migration_summary.json` | Only unacknowledged frames may migrate across eligible lanes or paths. |
| `L2-RETRY-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SELECTIVE-REPEAT-RTL` | `evidence/generated/p8d_selective_repeat_rtl_summary.json` | Retry count, timeout/backoff, and exhaustion are bounded. |
| `SCHED-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8d_scheduler_migration_summary.json` | Scheduling is health-aware and weighted across eligible lanes. |
| `SCHED-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8d_scheduler_migration_summary.json` | A faulted lane does not block work on healthy eligible lanes. |
| `SCHED-003` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-SCHEDULER-MIGRATION` | `evidence/generated/p8d_scheduler_migration_summary.json` | Scheduler fairness and starvation are explicitly bounded. |
| `AXIS-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AXIS-BACKPRESSURE` | `evidence/generated/p8d_axis_backpressure_summary.json` | Aggregate AXI-Stream transfers have no loss or duplication under arbitrary backpressure. |
| `DMA-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8d_dma_descriptor_ring_summary.json` | Independent bounded TX and RX scatter-gather descriptor rings are modeled. |
| `DMA-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8d_dma_descriptor_ring_summary.json` | Descriptor ownership permits exactly one completion and one reclaim. |
| `DMA-003` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8d_dma_descriptor_ring_summary.json` | Reset and abort deterministically reclaim ring and payload ownership. |
| `DMA-004` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-DMA-DESCRIPTOR-RING` | `evidence/generated/p8d_dma_descriptor_ring_summary.json` | Descriptor generation rejects stale completions after wrap or reset. |
| `RFAP-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-RFAP-V1-VNEXT-COMPATIBILITY` | `evidence/generated/p8d_rfap_compatibility_summary.json` | RFAP v1/P7 vectors and legacy fallback remain compatible. |
| `RFAP-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-RFAP-V1-VNEXT-COMPATIBILITY` | `evidence/generated/p8d_rfap_compatibility_summary.json` | RFAP vNext streaming validates large objects with bounded memory and atomic publish. |
| `PERF-MODEL-001` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AIRTIME-BUDGET-MODEL` | `evidence/generated/p8d_airtime_budget_summary.json` | The airtime model includes duty, framing, ACK, retry, handover, and descriptor overhead. |
| `PERF-MODEL-002` | `PASS` | P8D_MULTI_PROFILE_OFFLINE | `P8D` | `P8D-AIRTIME-BUDGET-MODEL` | `evidence/generated/p8d_airtime_budget_summary.json` | The 16 Mbit/s architecture target is explicitly evaluated without increasing duty. |

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

- `rtl/ir_tfdu_exact_duty_accountant.sv` — `2f49d7afdad61ec69ef312acaa0e3f115b79df2a2939427672631e441dd3e6bd`
- `sim/tb/tb_p8c_full_scale.sv` — `de7d29f8ca19a3bf65856d76b8bce60c16fc11b6a715088c3d34c251230c731c`
- `evidence/generated/p8c_exact_sliding_duty_rtl_summary.json` — `be832ebf4a1909618c41a2815846a24625d51d3045defd79815d0d6d861a6719`

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

- `config/project_state.json` — `85bdb7a6fb1c0aa83eb5e34aedc782a6e8e6427b0c34879637708354fd739615`
- `PROJECT_STATUS.md` — `d90615ba36364db821fcef478b12b66494243510de9ada0733e50e33bda7e431`

### `P8A-TRACE-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `config/project_state.json` — `85bdb7a6fb1c0aa83eb5e34aedc782a6e8e6427b0c34879637708354fd739615`

### `P8A-EVID-001`

- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`
- `evidence/generated/p7_final_acceptance_summary.json` — `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b`
- `evidence/hardware/p7/p7_run_sequence_ledger.json` — `ab6138a0d6229985f127cf24fd418d2d4026a02a21b7776bdbb6be2fc608a2c4`

### `P8A-SCOPE-001`

- `config/project_state.json` — `85bdb7a6fb1c0aa83eb5e34aedc782a6e8e6427b0c34879637708354fd739615`
- `PROJECT_STATUS.md` — `d90615ba36364db821fcef478b12b66494243510de9ada0733e50e33bda7e431`
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

### `MAP-006`

- `evidence/generated/p8b_rtl_python_crosscheck.csv` — `a15d1f0dd2904231df27101a6a29ca14abcc4782430b6605d854d408db5d274c`
- `evidence/generated/p8b_rtl_python_crosscheck.json` — `f5a48ea7419f68a601073f8b4d40769448847aaa04946fc359e9ca9ceff320de`

### `PHASE-001`

- `rtl/ir_phase_validity_guard.sv` — `f0f32489c307d01e49741708b14689aeaa3b511fa33a25bb047a6687a2a21742`
- `evidence/generated/p8b_phase_acquisition_summary.json` — `a39104698e930ae1ae1f073964e0ef1f0ee1acfbe605de921c3f28525aa974f8`

### `PHASE-002`

- `tools/p8b_generate_trajectory.py` — `a1d19a1f9acdfe0d0ecc145bbe2a507a76add84d2b430175291cfe424cd28357`
- `sim/tb/tb_p8b_phase_trajectory.sv` — `d3487922d87ef3b5553197762af8d895b59754f0128238c7da3c15c5b0f622a9`

### `PHASE-003`

- `rtl/ir_phase_validity_guard.sv` — `f0f32489c307d01e49741708b14689aeaa3b511fa33a25bb047a6687a2a21742`
- `docs/P8B_PHASE_ACQUISITION_MODEL.md` — `a4f0c32584787f5cc0663970ac8214ebbc9a2373157a4c0cb4b406e9ea1ed4ee`

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

- `rtl/ir_tfdu_exact_duty_accountant.sv` — `2f49d7afdad61ec69ef312acaa0e3f115b79df2a2939427672631e441dd3e6bd`
- `sim/tb/tb_p8c_exact_duty.sv` — `bca756a20bc65b02d5293704bb23f755e9570f328b2cbbcd331f547380209a8c`
- `evidence/generated/p8c_exact_sliding_duty_rtl_summary.json` — `be832ebf4a1909618c41a2815846a24625d51d3045defd79815d0d6d861a6719`

### `PHY-SAFE-006`

- `rtl/ir_p8c_mapping_safety_adapter.sv` — `f4d2b8a58c02c7379b9c47e109d000b578fafb7d0f9d9578c7efa70ed5655928`
- `sim/tb/tb_p8c_profile_matrix.sv` — `d044e572bdc244b673ff298b56c442daaa3df0af8595f35086783577ede7a13f`
- `evidence/generated/p8c_physical_module_accounting_summary.json` — `0a8ecb742db212e4fb017618400668421d88a81e7077fe652707e2253c0df6a7`

### `L2-ARQ-001`

- `rtl/ir_selective_repeat_tx.sv` — `4d16d3ad09bd55b092606a44c39449c337e6291646aaa60d12d49d20a3fd99f5`
- `rtl/ir_selective_repeat_rx.sv` — `85d36ef646b1c3906d0e08c15b97f3ef67878ba1e9f6a217f3b8d82b67b2ddb0`
- `evidence/generated/p8d_selective_repeat_rtl_summary.json` — `19c5eca6871ac6a9b13bd4e0cb3c1ff5f6643cc59b630fc3067b7153271ff804`

### `L2-ARQ-002`

- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `rtl/ir_data_plane_top.sv` — `7c07a0bb35a9bed5c4565758fa23b61017508787bf929f50905a9c5d6d0d8e63`
- `evidence/generated/p8d_data_plane_config_summary.json` — `661c3586fb074ad01869446278a1d23c2e54306f491b4f63cf4298f1964b39c1`

### `L2-SEQ-001`

- `rtl/ir_seq_math_pkg.sv` — `860c37a7565b19c7e2a1048c1552e12bba98662090f536a329258e69b292666e`
- `sim/tb/tb_ir_seq_math.sv` — `a01ab71e3891e4074a9b4f89719ced7561b39b83218ddf424965093d42608e5b`
- `evidence/generated/p8d_selective_repeat_rtl_summary.json` — `19c5eca6871ac6a9b13bd4e0cb3c1ff5f6643cc59b630fc3067b7153271ff804`

### `L2-SACK-001`

- `rtl/ir_sack_codec.sv` — `bde58a1da521b38d7cdf6459c69d952e0bbc42738a91d4d417f3f45776b5346e`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8d_sack_ack_aggregation_summary.json` — `dd3665eb31fd9b7797adccf3c55c207d9c60b3af49a9d76c05d0e1f816f228d9`

### `L2-SACK-002`

- `rtl/ir_ack_aggregator.sv` — `e2d27f15541d903a79b4f6fdb9e8d03ffbe6ab5d59940cab762bece76c5ba1c2`
- `sim/tb/tb_ir_sack_ack_aggregation.sv` — `cf7b1985d099d54b5fe3cd699466c1595c13dd2895d91657b408ccda91e2c6e5`
- `evidence/generated/p8d_sack_ack_aggregation_summary.json` — `dd3665eb31fd9b7797adccf3c55c207d9c60b3af49a9d76c05d0e1f816f228d9`

### `L2-DUP-001`

- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `rtl/ir_selective_repeat_rx.sv` — `85d36ef646b1c3906d0e08c15b97f3ef67878ba1e9f6a217f3b8d82b67b2ddb0`
- `evidence/generated/p8d_selective_repeat_reference_summary.json` — `4af7ee3c6bf0716598410fbbde7e920aa69ec9bfcc30b0bd8b630ae64cbd6108`

### `L2-STALE-001`

- `rtl/ir_selective_repeat_tx.sv` — `4d16d3ad09bd55b092606a44c39449c337e6291646aaa60d12d49d20a3fd99f5`
- `rtl/ir_selective_repeat_rx.sv` — `85d36ef646b1c3906d0e08c15b97f3ef67878ba1e9f6a217f3b8d82b67b2ddb0`
- `evidence/generated/p8d_selective_repeat_rtl_summary.json` — `19c5eca6871ac6a9b13bd4e0cb3c1ff5f6643cc59b630fc3067b7153271ff804`

### `L2-MIG-001`

- `rtl/ir_retry_migration.sv` — `53864a36ed5a041b1acab24645853faf0439a7e2577fcbb12ddbec7dcc0d9951`
- `sim/tb/tb_ir_scheduler_migration.sv` — `7ca86530439d942dd4e6e314b22a1b2b8aa6cebaa242d92834d9c56254a113e4`
- `evidence/generated/p8d_scheduler_migration_summary.json` — `af52964c98ee8aeb8314eeae8cc7e073b69eeeb9c70a458a389badb768d374e3`

### `L2-RETRY-001`

- `rtl/ir_selective_repeat_tx.sv` — `4d16d3ad09bd55b092606a44c39449c337e6291646aaa60d12d49d20a3fd99f5`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8d_selective_repeat_rtl_summary.json` — `19c5eca6871ac6a9b13bd4e0cb3c1ff5f6643cc59b630fc3067b7153271ff804`

### `SCHED-001`

- `rtl/ir_health_weighted_scheduler.sv` — `5cbbbf9edba29e1c605aa33d70a9ef6751c1787059cb3eca34237058425afa3a`
- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `evidence/generated/p8d_scheduler_migration_summary.json` — `af52964c98ee8aeb8314eeae8cc7e073b69eeeb9c70a458a389badb768d374e3`

### `SCHED-002`

- `rtl/ir_health_weighted_scheduler.sv` — `5cbbbf9edba29e1c605aa33d70a9ef6751c1787059cb3eca34237058425afa3a`
- `sim/tb/tb_ir_scheduler_migration.sv` — `7ca86530439d942dd4e6e314b22a1b2b8aa6cebaa242d92834d9c56254a113e4`
- `evidence/generated/p8d_scheduler_migration_summary.json` — `af52964c98ee8aeb8314eeae8cc7e073b69eeeb9c70a458a389badb768d374e3`

### `SCHED-003`

- `rtl/ir_health_weighted_scheduler.sv` — `5cbbbf9edba29e1c605aa33d70a9ef6751c1787059cb3eca34237058425afa3a`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8d_scheduler_migration_summary.json` — `af52964c98ee8aeb8314eeae8cc7e073b69eeeb9c70a458a389badb768d374e3`

### `AXIS-001`

- `rtl/ir_axis_tx_frontend.sv` — `961d7583f2493e54a3e23e74486de1fecf32da10ff28b85b9533236c5b7fb86f`
- `rtl/ir_axis_rx_backend.sv` — `7747c33d9b27a11a194e45ad895d6b0283f1e2f3626eb6c81845ad50c4b10539`
- `evidence/generated/p8d_axis_backpressure_summary.json` — `f5b67a03a0237e85a1ad20d3c0d9133a6a06f41d5c71db688eeda3ca23eb0227`

### `DMA-001`

- `rtl/ir_dma_descriptor_model.sv` — `1b679118c10225b2d2383a89c28ca118d141fc6a92c81a9b623dcf73239d28c0`
- `software/ps_driver/p8d_driver.h` — `5878e26abbb1c77c47004eba34819c7c4b64fe57048e3669b1ea0b5296018f6e`
- `evidence/generated/p8d_dma_descriptor_ring_summary.json` — `5c34f007e3f227eff41c6e4088bf5e252dcfd46b3632586d23803d12cb0e7ec6`

### `DMA-002`

- `rtl/ir_dma_descriptor_model.sv` — `1b679118c10225b2d2383a89c28ca118d141fc6a92c81a9b623dcf73239d28c0`
- `sim/tb/tb_ir_dma_descriptor_ring.sv` — `43f5637ee927a310e31a35a2957430cd93986c79a589fc88284aeee332dafc22`
- `evidence/generated/p8d_dma_descriptor_ring_summary.json` — `5c34f007e3f227eff41c6e4088bf5e252dcfd46b3632586d23803d12cb0e7ec6`

### `DMA-003`

- `rtl/ir_dma_descriptor_model.sv` — `1b679118c10225b2d2383a89c28ca118d141fc6a92c81a9b623dcf73239d28c0`
- `tools/p8d_data_plane_reference.py` — `bc43e3be3171215a72dfc1ed283e40b4b560cff42c18472983c65c63f39bf9f9`
- `evidence/generated/p8d_dma_descriptor_ring_summary.json` — `5c34f007e3f227eff41c6e4088bf5e252dcfd46b3632586d23803d12cb0e7ec6`

### `DMA-004`

- `rtl/ir_dma_descriptor_model.sv` — `1b679118c10225b2d2383a89c28ca118d141fc6a92c81a9b623dcf73239d28c0`
- `software/ps_driver/p8d_driver.c` — `e233e5a7b7c7e3cf86305970ee95547982988ab1468eb688fe497841af0f88a1`
- `evidence/generated/p8d_dma_descriptor_ring_summary.json` — `5c34f007e3f227eff41c6e4088bf5e252dcfd46b3632586d23803d12cb0e7ec6`

### `RFAP-001`

- `tools/p8d_rfap_reference.py` — `9d319cd01abd8a6eb618d96824a73d4408915446e05e6fb804df830f9e24915d`
- `tests/vectors/p7_app_protocol_vectors.json` — `b1015c343dec626328a3b5a1295754b065c1d28a681c87ca71dcb533463d36df`
- `evidence/generated/p8d_rfap_compatibility_summary.json` — `24e26c25eb2538bbc0bc4891d8fb42acfd8caef196a6678202b381c6218d096f`

### `RFAP-002`

- `tools/p8d_rfap_reference.py` — `9d319cd01abd8a6eb618d96824a73d4408915446e05e6fb804df830f9e24915d`
- `docs/design/P8D_RFAP_VNEXT_COMPATIBILITY.md` — `6433a2467aeab13a94c4b72ee90cd5680ca1443eed6e67d932795fae9da56ad3`
- `evidence/generated/p8d_rfap_compatibility_summary.json` — `24e26c25eb2538bbc0bc4891d8fb42acfd8caef196a6678202b381c6218d096f`

### `PERF-MODEL-001`

- `scripts/model_p8d_airtime.py` — `9ead4a661d080895a449216d6d6b317d1ae8d8ebd9ea2949c90f261210462986`
- `config/p8d_data_plane.yaml` — `2a417bd34e63403302c378c78d82970fb739ee6d35f902a02edcf5c4d14a0c02`
- `evidence/generated/p8d_airtime_budget_summary.json` — `4b4e784d30d0b2aaaa1c48af8aeeb0fc94ba1547102a9973b32fa07bceaa6d0a`

### `PERF-MODEL-002`

- `scripts/model_p8d_airtime.py` — `9ead4a661d080895a449216d6d6b317d1ae8d8ebd9ea2949c90f261210462986`
- `evidence/generated/p8d_airtime_budget_summary.json` — `4b4e784d30d0b2aaaa1c48af8aeeb0fc94ba1547102a9973b32fa07bceaa6d0a`
- `evidence/generated/p8d_airtime_budget_summary.json` — `4b4e784d30d0b2aaaa1c48af8aeeb0fc94ba1547102a9973b32fa07bceaa6d0a`
