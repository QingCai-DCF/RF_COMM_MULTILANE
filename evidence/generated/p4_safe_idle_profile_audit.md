# P4 Safe Idle Profile Audit

generated_at_utc: 2026-07-08T15:48:08+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
RESULT: PASS
REASON: P4 dry-run profiles satisfy safe-idle constraints
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4_SAFE_IDLE_PROFILE_AUDIT: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Profile Files

- `profiles/p4_safe_idle.json` sha256=`f876d051fc1d39972254b00de7832ab587d354801731b86e67623b629939231d`
- `profiles/p4_lane0_safe_smoke.json` sha256=`ae9e1c186154dd1f23fae3f0ab00c7c8f9d7d5d26b11e7a36e4287438cee85b4`
- `profiles/p4_lane_matrix_safe_smoke.json` sha256=`5a1b95721bd64c54e70fcba04b635c5a477d92fb2f6e96439ae5a64006b7afe0`

## Checks

- profiles_valid: PASS
- active_xdc_present: PASS
- pinmap_present: PASS
- tfdu_contract_present: PASS
- active_rtl_txd_guard_10us: PASS
- ps_profile_txd_guard_10us: PASS

## Active Hashes

- agents_md: `1573dcf000ddd07dca8676419e6845d22bf61a524b645398233a569f3f663a9e`
- constraint_file: `cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11`
- active_profile: `7c932dfed5d29298cdfad2164aed2fcfca554aadbe4aed86eed7715864f9f2b1`
- active_xdc: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
- pinmap: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
- tfdu_safety_contract: `ff8f94e0aaba1d4bad239de59fea46a7a044f779e95bc04f00269d9fce5f03ae`
- tfdu_safety_summary: `0bc9af6cfeeb9dae03a9cafe7a645bcbfee8522454a18d3cbd6f816bd8861a0f`
