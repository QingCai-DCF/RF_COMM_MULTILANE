# P8C TFDU safety completion summary

_RF_COMM_MULTILANE · P8C offline acceptance · 2026-07-18_

---

## 📋 Executive summary

P8C has completed the exact TFDU6102 duty guard, continuous-high protection, endpoint-local single `GLOBAL_PERMIT` architecture, mapping/epoch safety integration, register-map extension, multi-profile simulation, and offline regression. The accepted scope is **portable RTL function / offline verification**, with final status `PASS`.

- Source commit: `e8be6ffddd1b59b13b6bf3e0c32c02c6a66b6134`
- Evidence checkpoint: `c44b0d45133bf75c9c71f53dde77f3dc186ad131`
- Annotated tag: `p8c-pass`, targeting the evidence checkpoint
- Baseline retained: `p8b-pass` at `80c8433eac1a09a32c9018460f8b76286c4a72a7`
- Machine-state revision: `P8C-1`
- Next program stage: `P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE`
- Hardware authorization: `false`; no real hardware action was executed and no hardware scope was promoted

The canonical [project constraints](../PROJECT_CONSTRAINTS.txt) were not modified. Their retained SHA256 is `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758`.

## 🎯 Delivered safety behavior

| Area | Accepted behavior |
| --- | --- |
| Exact rolling duty | Every physical TFDU module is accounted independently over every clock-aligned `1 ms` sliding window |
| Hard duty limit | Strict `<20%`; the canonical 64 MHz implementation permits at most `12,799` high cycles in a `64,000`-cycle window |
| Design target | Requests are throttled to `≤18%`, or `11,520` high cycles per canonical window |
| Continuous high | Physical `Txd` high duration is limited to `≤1 µs`, or `64` canonical clock cycles |
| Startup | Normal RX/TX operation is held until the required `500 µs` shutdown-exit delay completes |
| Permit architecture | Exactly one local active-high `GLOBAL_PERMIT` exists per endpoint; no dual, heartbeat, per-bank, or per-lane permit was added |
| Permit drop | Deassertion reaches the final RTL TX kill path without PS, protocol, AXI polling, or a normal frame transition |
| Permit reassertion | Explicit re-arm is required and an interrupted partial frame cannot resume |
| Fault containment | Stuck-high, illegal one-hot, invalid module, stale epoch, duty, frame-admission, SD, startup, and shutdown guards kill TX |
| Receive-only mode | Acquisition can continue with `GLOBAL_PERMIT=0` while all physical TX paths remain hard-disabled |
| Software boundary | Software can observe status and request arm but cannot create, override, or bypass physical permit high |

The canonical safety source is [config/tfdu_safety.yaml](../config/tfdu_safety.yaml), with SHA256 `e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06`.

## ✅ Verification result

| Verification scope | Result | Direct evidence |
| --- | --- | --- |
| P8C final acceptance | `PASS` | [p8c_final_summary.json](../evidence/generated/p8c_final_summary.json) |
| Safety configuration generation | `PASS` | [p8c_safety_config_summary.json](../evidence/generated/p8c_safety_config_summary.json) |
| Python exact-duty reference | `PASS` | [p8c_exact_sliding_duty_reference_summary.json](../evidence/generated/p8c_exact_sliding_duty_reference_summary.json) |
| RTL exact-duty XSIM | `PASS` | [p8c_exact_sliding_duty_rtl_summary.json](../evidence/generated/p8c_exact_sliding_duty_rtl_summary.json) |
| Single-permit architecture | `PASS` | [p8c_single_global_permit_architecture_summary.json](../evidence/generated/p8c_single_global_permit_architecture_summary.json) |
| Multi-profile matrix | `PASS` | [p8c_profile_matrix_summary.json](../evidence/generated/p8c_profile_matrix_summary.json) |
| OOC resource and timing audit | `PASS` | [p8c_resource_audit_summary.json](../evidence/generated/p8c_resource_audit_summary.json) |
| Register-map RTL and host driver | `PASS` | [p8c_register_map_summary.json](../evidence/generated/p8c_register_map_summary.json) |
| P0–P8B preservation regression | `PASS` | [p8c_p0_p8b_regression_summary.json](../evidence/generated/p8c_p0_p8b_regression_summary.json) |
| Integrated P0–P8C offline gate | `PASS` | [offline_gate_summary.json](../evidence/generated/offline_gate_summary.json) |
| Evidence artifact manifest | `PASS`, 115 artifacts | [artifact_sha256_manifest.json](../evidence/generated/p8c_raw/artifact_sha256_manifest.json) |

The Python campaign covered `35,000` randomized adversarial cases using seeds `1`, `7`, `17`, `31`, `127`, `1024`, and `20260718`, plus `4,096` reduced exhaustive cases. RTL-to-Python cycle-trace comparison completed with `250` records and no mismatch.

All five mandatory vector matrices passed:

- Exact-duty targeted vectors
- Continuous-high vectors
- Permit and fault-injection vectors
- One-hot and path/epoch vectors
- Multi-profile vectors

Eight XSIM benches completed compile, elaborate, and run phases with return code `0`. The standalone P8C gate, PowerShell wrapper, and integrated offline regression all completed successfully. A final `--verify-existing` audit also returned `PASS` against a clean checkpoint.

## 📊 OOC profile results

| Profile | Physical modules | LUT | FF | BRAM36 | Timing constraints | Critical warnings |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| `Z7010_2LANE_DEV` | 2 | 364 | 307 | 4 | Met | 0 |
| `Z7020_ROTATING_8LANE_MODEL` | 8 | 1,402 | 1,201 | 16 | Met | 0 |
| `Z7020_FIXED_32MODULE_ACCOUNTING_MODEL` | 32 | 5,519 | 4,777 | 64 | Met | 0 |

These are out-of-context logic-model results. Reported wrapper I/O delay gaps are preserved in the raw reports and do not constitute final board timing closure or Z7020 hardware acceptance.

## ⚠️ Scope boundaries

P8C does not change any existing hardware acceptance boundary.

| Scope | Current status |
| --- | --- |
| P7 stationary two-lane application | `PASS` |
| Current Z7010 platform | `PLATFORM_LIMITED_PASS` |
| Z7020 target | `PENDING_Z7020_HW` |
| Rotation | `PENDING_FINAL_MECHANICAL` |
| Final product hardware | `PENDING_HW` |
| Physical `GLOBAL_PERMIT` implementation and partial-power behavior | `PENDING_D17` |
| Z7010 permit-pin freeze | `PENDING_P9_PIN_FREEZE` |
| External TFDU duty measurement | `PENDING_P9_OR_LATER` |
| Simultaneous-TX power acceptance | `PENDING_HARDWARE_POWER_STAGE` |

No offline result in this stage claims electrical, optical, mechanical, rotating, sector-bank, Z7020, or final-product hardware acceptance. The architecture also makes no stuck-high detection, dual-channel safety, SIL, PL, or redundant-safety claim for the single active-high permit itself.

## 📦 Repository checkpoint

The P8C implementation and evidence were preserved through the following commit sequence:

| Commit | Purpose |
| --- | --- |
| `e0a5f10e90d10387ccf2ac0e2f70ba531c3d6d6c` | Initial P8C implementation |
| `b9d6af421239dec8dadea3f84fd280f98b770f31` | Bounded full-regression timeout correction |
| `cca4dcff4e4b2906b16becd4123cfe2c4676abe7` | P0–P7 static-safety regression preservation |
| `9612b47433870dfeda4c2d0646093103fef111c4` | SystemVerilog static-mode declaration correction |
| `e8be6ffddd1b59b13b6bf3e0c32c02c6a66b6134` | Immutable P8B checkpoint evidence preservation and final P8C source |
| `c44b0d45133bf75c9c71f53dde77f3dc186ad131` | P8C evidence checkpoint tagged `p8c-pass` |

Canonical status and traceability are available in:

- [PROJECT_STATUS.md](../PROJECT_STATUS.md)
- [config/project_state.json](../config/project_state.json)
- [config/project_requirements.yaml](../config/project_requirements.yaml)
- [REQUIREMENT_TRACEABILITY_MATRIX.md](REQUIREMENT_TRACEABILITY_MATRIX.md)
- [P8C_TFDU_SAFETY_ARCHITECTURE.md](P8C_TFDU_SAFETY_ARCHITECTURE.md)
- [TFDU6102_SAFETY_SUMMARY.md](TFDU6102_SAFETY_SUMMARY.md)
- [tfdu6102_safety_contract.md](tfdu6102_safety_contract.md)

## 🔧 Re-verification

The immutable evidence checkpoint can be checked without executing hardware:

```powershell
$env:NO_HARDWARE = '1'
python scripts/run_p8c_safety_gate.py --verify-existing --json-summary
```

Expected result: `status=PASS`, `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`, `NO_HARDWARE_ACTIONS_EXECUTED=true`, and a clean worktree.
