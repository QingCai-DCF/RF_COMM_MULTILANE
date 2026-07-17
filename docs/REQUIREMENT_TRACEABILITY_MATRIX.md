# Requirement Traceability Matrix

> Generated from `config/project_requirements.yaml` by `scripts/generate_requirement_traceability.py`; do not edit by hand.

Canonical constraint: `PROJECT_CONSTRAINTS.txt` (`9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`).

```text
REQUIREMENT_COUNT: 39
PASS: 20
PENDING: 19
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
| `SYS-PERMIT-001` | `PENDING` | Z7020_8LANE_DUAL_ENDPOINT | `P8C_D17` | — | — | 每个独立端点各有且仅有一根本地 active-high GLOBAL_PERMIT。 |
| `SYS-PERMIT-002` | `PENDING` | Z7020_8LANE_DUAL_ENDPOINT | `P8C_D17` | — | — | GLOBAL_PERMIT=0 必须关闭本端全部物理 TX。 |
| `SYS-PERMIT-003` | `PENDING` | ALL_ENDPOINT_PROFILES | `P8C_D17` | — | — | 禁止双 permit、permit heartbeat、per-bank permit 和 per-lane external GLOBAL_PERMIT。 |
| `SYS-PERMIT-004` | `PENDING` | ALL_ENDPOINT_PROFILES | `P8C` | — | — | permit 重新上升必须重新 arm，且不得恢复半帧。 |
| `PHY-SAFE-001` | `PENDING` | ALL_TFDU_PROFILES | `P8C_P9_P12` | — | — | TFDU6102 的 Txd/Rxd/SD 极性和 static high-speed Mode 必须正确。 |
| `PHY-SAFE-002` | `PENDING` | ALL_TFDU_PROFILES | `P8C_P9` | — | — | 退出 shutdown 后必须等待至少 500 µs 才允许正常 RX/TX。 |
| `PHY-SAFE-003` | `PENDING` | ALL_TFDU_PROFILES | `P8C_P9` | — | — | 项目 MAX_CONTINUOUS_TXD_HIGH_US 必须 <= 1 µs。 |
| `PHY-SAFE-004` | `PENDING` | ALL_TFDU_PROFILES | `P8C_P9` | — | — | 每模块任意 clock-aligned 1000 µs 滑动窗口 duty 必须严格 <20%，设计目标 <=18%。 |
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
| `EVID-P8B-001` | `PASS` | P8B_D200_D600_8X32_OFFLINE | `P8B` | `P8B-REQUIREMENT-TRACEABILITY` | `evidence/generated/p8b_acceptance_core.json` | Every P8B PASS shall bind a profile, test ID, evidence path and content hashes without promoting hardware scope. |

## PASS artifact bindings

### `MAP-001`

- `rtl/ir_path_mapping_pkg.sv` — `6be70a692a1b39ecae347c52b9440fd6f7b1e41434362423aeb53519dabd505b`
- `evidence/generated/p8b_mapping_exhaustive_summary.json` — `bc06d52e78048f8fef19b9b7ceb7948b909f30a89bd033c5da7c24b000fe5327`

### `MAP-002`

- `tools/p8b_mapping_reference.py` — `d9d97209cb6f41fe4f389d697d4ac7a638101d1537516235abe35fc320f54565`
- `evidence/generated/p8b_mapping_exhaustive_summary.json` — `bc06d52e78048f8fef19b9b7ceb7948b909f30a89bd033c5da7c24b000fe5327`

### `MAP-003`

- `rtl/ir_path_epoch_commit.sv` — `1cd34f339393fdfce3f554d33501ba12a65b3daf85190ffa01bad2d95890db4c`
- `evidence/generated/p8b_path_epoch_summary.json` — `cb24066cf519af635b078b5058c2fb79a5506a044457d5e01cc7cc5afa1486af`

### `P8A-CANON-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `PROJECT_CONSTRAINTS_CHANGELOG.md` — `f51da907122d1673bc3b657779997742df474ed391cd1a6772e0371da8cc176b`

### `P8A-STATE-001`

- `config/project_state.json` — `05943ff1dae2118252d795977e6afea9ef9f7e26148473ff34814bf369932456`
- `PROJECT_STATUS.md` — `716cee29bfdc5f5e04bb1bb31ea50e5543c493742ef57ad885ecec8ff8bf78cc`

### `P8A-TRACE-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `config/project_state.json` — `05943ff1dae2118252d795977e6afea9ef9f7e26148473ff34814bf369932456`

### `P8A-EVID-001`

- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`
- `evidence/generated/p7_final_acceptance_summary.json` — `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b`
- `evidence/hardware/p7/p7_run_sequence_ledger.json` — `ab6138a0d6229985f127cf24fd418d2d4026a02a21b7776bdbb6be2fc608a2c4`

### `P8A-SCOPE-001`

- `config/project_state.json` — `05943ff1dae2118252d795977e6afea9ef9f7e26148473ff34814bf369932456`
- `PROJECT_STATUS.md` — `716cee29bfdc5f5e04bb1bb31ea50e5543c493742ef57ad885ecec8ff8bf78cc`
- `evidence/generated/p7_final_acceptance_summary.md` — `702a32cf72601474b56e35bb3fac57ed9b97da8a4e681a8bf1c5089907caf624`

### `P8A-LEGACY-001`

- `evidence/imported/evidence/final/BAD_DIR_fault_report.md` — `e24245750107dd4fede13650bd3a796f4d8de97c37a9b13356b06c7ba5f7ebf7`
- `evidence/generated/p7_lane1_promotion_summary.json` — `6cc4cb4141133c7381874873137bfe78d5d73d337cf9c663b51ce5d1851a6363`
- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`

### `MAP-004`

- `rtl/ir_bank_lane_crossbar.sv` — `97be64e23308e85768866c8bc5037d9f4f2bfb3670a9981915d3f5686519e886`
- `evidence/generated/p8b_crossbar_summary.json` — `ac573ebaca0d5e8844d5c1a060e4017c455b4967f362d677e08930a8e53b9958`

### `MAP-005`

- `rtl/ir_path_mapping_engine.sv` — `248691b1186dfcd4524e8a988aa2424e4b2853852fea2fb645c0ac4c66613d2c`
- `sim/tb/tb_p8b_mapping_unit.sv` — `7d7baaa638ebd81da3a44ada810d324252b47602472de493e5a1dad5eae5e30a`

### `MAP-006`

- `evidence/generated/p8b_rtl_python_crosscheck.csv` — `ac520c1c9478efe12dd373793a103d357e57761199f4f3d37e2c96750552b3a2`
- `evidence/generated/p8b_rtl_python_crosscheck.json` — `4baa93d5b7830e6263d40498cb7bf1f8b907c2041be38165d98cfb93d3e27136`

### `PHASE-001`

- `rtl/ir_phase_validity_guard.sv` — `f0f32489c307d01e49741708b14689aeaa3b511fa33a25bb047a6687a2a21742`
- `evidence/generated/p8b_phase_acquisition_summary.json` — `983967e52b5c415bdd1b75ef28a820037e0eb59ceb43eec123b3f7f1c4fc2e4c`

### `PHASE-002`

- `tools/p8b_generate_trajectory.py` — `a1d19a1f9acdfe0d0ecc145bbe2a507a76add84d2b430175291cfe424cd28357`
- `sim/tb/tb_p8b_phase_trajectory.sv` — `d3487922d87ef3b5553197762af8d895b59754f0128238c7da3c15c5b0f622a9`

### `PHASE-003`

- `rtl/ir_phase_validity_guard.sv` — `f0f32489c307d01e49741708b14689aeaa3b511fa33a25bb047a6687a2a21742`
- `docs/P8B_PHASE_ACQUISITION_MODEL.md` — `a4f0c32584787f5cc0663970ac8214ebbc9a2373157a4c0cb4b406e9ea1ed4ee`

### `HANDOVER-001`

- `rtl/ir_handover_metrics.sv` — `f5f4862a0b439f08404fe249732fe108c0be0d6bc4cc77a4850d906ec046d4ab`
- `evidence/generated/p8b_handover_timing_summary.json` — `eef32a3a7c7a75a3f1bdca20df3c78efbb85992f1930afa0da8d5da7752c5dd0`

### `HANDOVER-002`

- `config/geometry/optical_geometry.yaml` — `ed047dec336af273d0f56e4c400f7ce7f2e8440a6a04869c367e46e8152824b0`
- `evidence/generated/p8b_handover_timing_summary.json` — `eef32a3a7c7a75a3f1bdca20df3c78efbb85992f1930afa0da8d5da7752c5dd0`

### `GEO-MODEL-001`

- `tools/p8b_geometry_model.py` — `35b3d36bf086d2e4ef135ddacffbb2dfa01551dce351057feacda758fff0530b`
- `evidence/generated/p8b_geometry_nominal_summary.json` — `0a2783f15ca841a986c5408ec58908b63612b0547e0a1de0a10d6f9577b237c5`

### `GEO-MODEL-002`

- `config/geometry/optical_geometry.yaml` — `ed047dec336af273d0f56e4c400f7ce7f2e8440a6a04869c367e46e8152824b0`
- `evidence/generated/p8b_geometry_gap_ledger.json` — `1c8fed77ff9d5842447a3449a911fe79d4591dab28bc8d83f99b2957da6aa2ea`
- `evidence/generated/p8b_geometry_worst_case_summary.json` — `24268224d90bd0ef075b7b76a94cdab5f60db40552fdcabcce946c3914eb1174`

### `EVID-P8B-001`

- `evidence/generated/p8b_acceptance_core.json` — `eb3628dae5d064ce6b31ece3ffdc2f99ff8e51130c265127b77c3316d4d92d40`
- `evidence/generated/offline_gate_summary.json` — `4108eedd8632b80f734f9f74675b4e4463fb69df10f1987c217fe595709801a5`
- `evidence/generated/p8b_rtl_python_crosscheck.json` — `4baa93d5b7830e6263d40498cb7bf1f8b907c2041be38165d98cfb93d3e27136`
