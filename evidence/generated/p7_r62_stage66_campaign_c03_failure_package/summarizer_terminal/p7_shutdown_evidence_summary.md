# shutdown

RESULT: PASS
REASON: every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker
GENERATED_AT_UTC: 2026-07-16T10:14:39+00:00
REPO: D:\CodexWorktrees\stage66prep_dd768f5\RF_COMM_MULTILANE
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

- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/001_p7_safe_idle/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/002_p7_p6_frame_regression_m1/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/003_p7_p6_frame_regression_m2/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/004_p7_p6_frame_regression_m3/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/056_p7_large_jtag_64k_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/058_p7_large_jtag_1m_l0_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/059_p7_large_jtag_1m_l1_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/060_p7_large_jtag_1m_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/061_p7_large_jtag_1m_rep3_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/062_p7_ps_functional/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `audited_hardware_runs`: `12`

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
  "repo": "D:\\CodexWorktrees\\stage66prep_dd768f5\\RF_COMM_MULTILANE",
  "uart_access": null
}
```

