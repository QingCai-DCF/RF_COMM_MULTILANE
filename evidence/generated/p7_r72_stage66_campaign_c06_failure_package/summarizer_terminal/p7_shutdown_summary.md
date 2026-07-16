# shutdown

RESULT: PASS
REASON: every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker
GENERATED_AT_UTC: 2026-07-16T16:36:25+00:00
REPO: C:\Users\user\Documents\RF_COMM_MULTILANE
HEAD: INCONSISTENT_OR_MISSING
HARDWARE_ACTIONS_EXECUTED_BY_SUMMARIZER: false
HARDWARE_ACTIONS_EXECUTED: false
PROGRAMMED_FPGA: False
DROVE_TFDU_TXD: None
ENABLED_TFDU_RECEIVER: None
SHUTDOWN_EXIT: None
NETWORK_USED: false
MOTION_USED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Evidence

- `evidence/hardware/p7/authorized_sequence/p7_20260716_stationary_app_r72_diag_stage66_c06/001_p7_safe_idle/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260716_stationary_app_r72_diag_stage66_c06/002_p7_p6_frame_regression_m1/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260716_stationary_app_r72_diag_stage66_c06/003_p7_p6_frame_regression_m2/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260716_stationary_app_r72_diag_stage66_c06/004_p7_p6_frame_regression_m3/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260716_stationary_app_r72_diag_stage66_c06/066_p7_ps_stationary/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `audited_hardware_runs`: `5`

## Errors

- None.

## Hardware evidence envelope

### profile

```json
[]
```

### bitstream

```json
[]
```

### ltx

```json
[]
```

### xsa

```json
[]
```

### elf

```json
[]
```

### authorization

```json
[]
```

### input_file_hashes

```json
[]
```

### output_file_hashes

```json
[]
```

### shutdown_before

```json
[]
```

### shutdown_after

```json
[]
```

### envelope_status

```json
{
  "HEAD": "INCONSISTENT_OR_MISSING",
  "SHUTDOWN_EXIT": null,
  "drove_tfdu_txd": null,
  "enabled_tfdu_receiver": null,
  "hardware_actions_executed": false,
  "programmed_fpga": false,
  "repo": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE",
  "uart_access": null
}
```

