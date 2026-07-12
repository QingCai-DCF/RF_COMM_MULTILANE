# consistency

RESULT: FAIL
REASON: evidence consistency failed closed
GENERATED_AT_UTC: 2026-07-12T13:59:43+00:00
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

- `evidence/hardware/p7/p7_run_sequence_ledger.json`

## Checks

- No additional checks recorded.

## Metrics

- `inventory_files`: `6378`
- `selected_provenance_rows`: `0`
- `stationary_attempts`: `0`
- `full_duration_stationary_attempts`: `0`
- `qualified_stationary_passes`: `0`
- `run_count`: `13`
- `listed_executed_summaries`: `13`
- `passed_coverage_keys`: `[]`
- `ledger_sha256`: `337edf8b2f154b24783c383e4d95c656c9c2f48630193f75d2b1cdf93095513a`

## Errors

- run sequence offline checkpoint SHA256 mismatch
- run sequence offline checkpoint recorded actual SHA256 mismatch
- offline checkpoint source_commit does not match the frozen ledger commit
- offline checkpoint source changed after freeze: evidence/generated/p7_ps_core_hardware_readiness.json
- offline checkpoint source changed after freeze: evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json
- offline checkpoint source changed after freeze: scripts/hw/p7_ps_application_execute.tcl
- offline checkpoint source changed after freeze: scripts/hw/run_p7_ps_application_stage_safe.py
- offline checkpoint source changed after freeze: software/ps_driver/p7_app_service.c
- offline checkpoint source changed after freeze: software/ps_driver/p7_app_service.h
- offline checkpoint source changed after freeze: tools/p7_ps_mailbox_backend.py
- offline checkpoint source changed after freeze: tools/run_p7_ps_core_offline.py
- offline checkpoint source changed after freeze: tools/summarize_p7_hardware.py
- run sequence ledger does not list every executed hardware summary exactly once

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

