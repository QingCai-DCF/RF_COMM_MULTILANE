# P5 Authorized Run Package Summary

generated_at_utc: 2026-07-09T14:50:41+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: READY_AUTHORIZED
reason: P5 authorized-run inputs recorded without executing hardware
hardware_actions_executed: false
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P5_AUTHORIZED_RUN_PACKAGE: READY_AUTHORIZED
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
AUTHORIZATION_STATUS_AT_GENERATION: AUTHORIZED
PROJECTED_AUTHORIZATION_WITH_PACKAGE_ARGS: AUTHORIZED
RF_COMM_HW_AUTH_REQUIRED: `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`
BOARD_ID: `AX7010`
STAGE: `two_lane_30min_soak`
MARKER: `TWO_LANE_30MIN_SOAK`
MAX_RUNTIME_SEC: 1860
LANE_COUNT: 2
AUTHORIZATION_FILE: `.hardware_authorization/P5_2LANE_APPROVED.txt`
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit`
BITSTREAM_SHA256: `32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372`
PROFILE: `profiles/p5/p5_two_lane_30min_soak.json`
PROFILE_SHA256: `7b5d43e392ed0532592823041a46d6741f83c261221b541e2bf0a5c203a07f51`
ACTIVE_PINMAP_HASH: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
ACTIVE_XDC_HASH: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
SHUTDOWN_BITSTREAM: `shutdown_bitstream/tfdu_shutdown_j10_j11.bit`
SHUTDOWN_BITSTREAM_SHA256: `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`

## Projected Missing Controls Before Run

- none

## PowerShell

```powershell
$env:RF_COMM_HW_AUTH='I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW'
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run_p5_gate.ps1 -AllowHardware -ExecuteHardware -AuthorizationFile .hardware_authorization\P5_2LANE_APPROVED.txt -BoardId AX7010 -ShutdownOnExit -MaxRuntimeSec 1860 -StageFilter two_lane_30min_soak -LaneCount 2 -Profile profiles\p5\p5_two_lane_30min_soak.json -ProfileSha256 7b5d43e392ed0532592823041a46d6741f83c261221b541e2bf0a5c203a07f51 -Bitstream evidence\generated\vivado\ir_top_new_protocol_two_lane_soak.bit -BitstreamSha256 32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372 -ActivePinmapHash 4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a -ActiveXdcHash cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990 -ShutdownBitstream shutdown_bitstream\tfdu_shutdown_j10_j11.bit -ShutdownBitstreamSha256 bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810 -SkipEthernet -SkipMotion -StopOnFirstFail -JsonSummary
```

## Python

```powershell
$env:RF_COMM_HW_AUTH='I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW'
python tools/run_p5_gate.py --allow-hardware --execute-hardware --authorization-file .hardware_authorization/P5_2LANE_APPROVED.txt --board-id AX7010 --shutdown-on-exit --max-runtime-sec 1860 --stage-filter two_lane_30min_soak --lane-count 2 --profile profiles/p5/p5_two_lane_30min_soak.json --profile-sha256 7b5d43e392ed0532592823041a46d6741f83c261221b541e2bf0a5c203a07f51 --bitstream evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit --bitstream-sha256 32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372 --active-pinmap-hash 4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a --active-xdc-hash cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990 --shutdown-bitstream shutdown_bitstream/tfdu_shutdown_j10_j11.bit --shutdown-bitstream-sha256 bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810 --skip-ethernet --skip-motion --stop-on-first-fail --json-summary
```

## Boundary

- This package records the exact artifact hashes and command arguments for a future authorized P5 run.
- It does not execute hardware and does not promote P5 hardware acceptance.
- The current P5 runner still refuses to claim PASS unless fresh P5 hardware evidence and shutdown logs exist.
