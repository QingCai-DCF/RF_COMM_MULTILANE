# P4 Auto TFDU Control Idle Authorized Run Package

generated_at_utc: 2026-07-09T05:11:02+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: READY
reason: exact TFDU_CONTROL_IDLE authorized-run inputs recorded without executing hardware
hardware_actions_executed: false
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4_AUTO_AUTHORIZED_RUN_PACKAGE: READY
P4_AUTO_STAGE: TFDU_CONTROL_IDLE
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS: BLOCKED_NOT_AUTHORIZED
RF_COMM_HW_AUTH_REQUIRED: `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`
BOARD_ID: `AX7010`
MAX_RUNTIME_SEC: 60
AUTHORIZATION_FILE: `.hardware_authorization/P4_AUTO_APPROVED.txt`
BITSTREAM: `evidence/hardware/p4_auto/bitstreams/tfdu_control_idle/tfdu_control_idle_4768ef7_16129e5951e58d1f.bit`
BITSTREAM_SHA256: `16129e5951e58d1f80b4610804b35dbbcd0803fcf570622512e32bfc1101fa8f`
PROFILE_PATH: `profiles/p4_auto_tfdu_control_idle.json`
PROFILE_SHA256: `1b9e9ec53039a3f1560fe58edbafd0b0f6b4fdf1dcf64b30c93329da45419462`
ACTIVE_PINMAP_HASH: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
ACTIVE_XDC_HASH: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_tfdu_control_idle_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `85d3b0176b125a1ab433cbb64dc8f024d8d6e48d1d61b862f60746b8a6681927`

## Projected Missing Controls Before Run

- `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`

## Python

```powershell
$env:RF_COMM_HW_AUTH='I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW'
python tools/run_p4_auto_hardware_acceptance.py --allow-hardware --execute-hardware --authorization-file .hardware_authorization\P4_AUTO_APPROVED.txt --user-confirmed-supply-ok --no-manual-intervention --shutdown-on-exit --max-runtime-sec 60 --board-id AX7010 --stage tfdu_control_idle --bitstream evidence/hardware/p4_auto/bitstreams/tfdu_control_idle/tfdu_control_idle_4768ef7_16129e5951e58d1f.bit --bitstream-sha256 16129e5951e58d1f80b4610804b35dbbcd0803fcf570622512e32bfc1101fa8f --profile-path profiles/p4_auto_tfdu_control_idle.json --profile-sha256 1b9e9ec53039a3f1560fe58edbafd0b0f6b4fdf1dcf64b30c93329da45419462 --active-pinmap-hash 4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a --active-xdc-hash cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990 --json-summary --skip-recheck
```

## Boundary

- This package records exact TFDU_CONTROL_IDLE inputs.
- TX remains commanded low; this is not raw pulse/protocol/lane/soak acceptance.
