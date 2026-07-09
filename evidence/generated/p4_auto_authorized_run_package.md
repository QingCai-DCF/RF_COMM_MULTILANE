# P4 Auto Authorized Run Package

generated_at_utc: 2026-07-09T10:03:08+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: READY
reason: exact authorized-run inputs recorded without executing hardware
hardware_actions_executed: false
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4_AUTO_AUTHORIZED_RUN_PACKAGE: READY
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
AUTHORIZATION_STATUS_AT_GENERATION: AUTHORIZED
PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS: AUTHORIZED
RF_COMM_HW_AUTH_REQUIRED: `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`
BOARD_ID: `AX7010`
STAGE: `two_lane_300s_soak`
MAX_RUNTIME_SEC: 360
AUTHORIZATION_FILE: `.hardware_authorization/P4_AUTO_APPROVED.txt`
BITSTREAM: `evidence/hardware/p4_auto/bitstreams/protocol_two_lane_soak/protocol_two_lane_soak_4768ef7_6bcb3ca2762eadd5.bit`
BITSTREAM_SHA256: `6bcb3ca2762eadd50c3b278159c42dc43bb3d9c3394f8055a3631df22a787e93`
PROFILE_PATH: `profiles/p4_auto_two_lane_300s_soak.json`
PROFILE_SHA256: `2e1ef5bed537c59d9a616f45a921b803c4cdf95ee18db7de32247cf76cb79e6d`
ACTIVE_PINMAP_HASH: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
ACTIVE_XDC_HASH: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_two_lane_soak_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `7f993141f5c2c3d1d733fc8fa0441f7bc5f6b095d867b7870a049b3ed55dd6ac`

## Projected Missing Controls Before Run

- none

## PowerShell

```powershell
$env:RF_COMM_HW_AUTH='I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW'
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run_p4_auto_hardware_acceptance.ps1 -AllowHardware -ExecuteHardware -AuthorizationFile .hardware_authorization\P4_AUTO_APPROVED.txt -UserConfirmedSupplyOk -NoManualIntervention -ShutdownOnExit -MaxRuntimeSec 360 -Stage two_lane_300s_soak -BoardId AX7010 -Bitstream evidence\hardware\p4_auto\bitstreams\protocol_two_lane_soak\protocol_two_lane_soak_4768ef7_6bcb3ca2762eadd5.bit -BitstreamSha256 6bcb3ca2762eadd50c3b278159c42dc43bb3d9c3394f8055a3631df22a787e93 -ProfilePath profiles\p4_auto_two_lane_300s_soak.json -ProfileSha256 2e1ef5bed537c59d9a616f45a921b803c4cdf95ee18db7de32247cf76cb79e6d -ActivePinmapHash 4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a -ActiveXdcHash cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990 -JsonSummary -SkipRecheck
```

## Python

```powershell
$env:RF_COMM_HW_AUTH='I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW'
python tools/run_p4_auto_hardware_acceptance.py --allow-hardware --execute-hardware --authorization-file .hardware_authorization/P4_AUTO_APPROVED.txt --user-confirmed-supply-ok --no-manual-intervention --shutdown-on-exit --max-runtime-sec 360 --stage two_lane_300s_soak --board-id AX7010 --bitstream evidence/hardware/p4_auto/bitstreams/protocol_two_lane_soak/protocol_two_lane_soak_4768ef7_6bcb3ca2762eadd5.bit --bitstream-sha256 6bcb3ca2762eadd50c3b278159c42dc43bb3d9c3394f8055a3631df22a787e93 --profile-path profiles/p4_auto_two_lane_300s_soak.json --profile-sha256 2e1ef5bed537c59d9a616f45a921b803c4cdf95ee18db7de32247cf76cb79e6d --active-pinmap-hash 4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a --active-xdc-hash cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990 --json-summary --skip-recheck
```

## Boundary

- This package records the exact artifact hashes and command arguments for the next authorized run.
- It does not execute hardware and does not promote hardware acceptance.
