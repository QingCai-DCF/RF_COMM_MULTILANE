# Requirement Traceability Matrix

> Generated from `config/project_requirements.yaml` by `scripts/generate_requirement_traceability.py`; do not edit by hand.

Canonical constraint: `PROJECT_CONSTRAINTS.txt` (`9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`).

```text
REQUIREMENT_COUNT: 43
PASS: 32
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

- `config/project_state.json` — `e52f7e46a9f4ada89b083e9c318748a25c694069227f47a6ccf4a00e42eab175`
- `PROJECT_STATUS.md` — `028207231aa6af20a5b7622b274d43de9a21381dfd400826c6f8f5e7e9ce0ea4`

### `P8A-TRACE-001`

- `PROJECT_CONSTRAINTS.txt` — `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`
- `config/project_state.json` — `e52f7e46a9f4ada89b083e9c318748a25c694069227f47a6ccf4a00e42eab175`

### `P8A-EVID-001`

- `evidence/generated/p8a_p0_p7_reconciliation.json` — `8d3de8a562e72c8c635099c24090ee33c15b585b265090aa83d14881e3d1f76d`
- `evidence/generated/p7_final_acceptance_summary.json` — `a47b77e7c0ea0843eddaa0657408fe536af52fca3f7aa8395ba0902f4f01bc3b`
- `evidence/hardware/p7/p7_run_sequence_ledger.json` — `ab6138a0d6229985f127cf24fd418d2d4026a02a21b7776bdbb6be2fc608a2c4`

### `P8A-SCOPE-001`

- `config/project_state.json` — `e52f7e46a9f4ada89b083e9c318748a25c694069227f47a6ccf4a00e42eab175`
- `PROJECT_STATUS.md` — `028207231aa6af20a5b7622b274d43de9a21381dfd400826c6f8f5e7e9ce0ea4`
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
