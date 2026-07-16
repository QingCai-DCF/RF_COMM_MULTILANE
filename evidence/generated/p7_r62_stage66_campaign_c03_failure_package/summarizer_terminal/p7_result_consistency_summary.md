# consistency

RESULT: FAIL
REASON: evidence consistency failed closed
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

- `evidence/hardware/p7/p7_run_sequence_ledger.json`

## Checks

- No additional checks recorded.

## Metrics

- `inventory_files`: `10494`
- `selected_provenance_rows`: `0`
- `stationary_attempts`: `0`
- `zero_coverage_diagnostic_runs`: `12`
- `full_duration_stationary_attempts`: `0`
- `qualified_stationary_passes`: `0`
- `run_count`: `27`
- `listed_executed_summaries`: `27`
- `passed_coverage_keys`: `[]`
- `ledger_sha256`: `f047c05818d831a937dbe2a6bc4505d187e20d47972334266b3a26978745f6bc`

## Errors

- uncommitted/partial hardware evidence files remain: ['evidence/hardware/p7/stage62_functional/p7_20260714_ddr_external_campaign_c2_08/p7_ps_application_raw_result.log.partial.write_partial']
- hardware footprint has no parseable final safe-wrapper summary: evidence/hardware/p7/stage62_microtest/p7_20260714_stage62_microtest_r35_diag_only/p7_ps_application_raw_result.log
- hardware footprint has no parseable final safe-wrapper summary: evidence/hardware/p7/stage62_microtest/p7_20260714_stage62_microtest_r35_diag_only/shutdown_after_result.txt
- hardware footprint has no parseable final safe-wrapper summary: evidence/hardware/p7/stage62_microtest/p7_20260714_stage62_microtest_r35_diag_only/shutdown_before_result.txt
- run sequence offline checkpoint SHA256 mismatch
- run sequence offline checkpoint recorded actual SHA256 mismatch
- offline checkpoint source_commit does not match the frozen ledger commit
- offline checkpoint omits one or more critical P7 source hashes
- offline checkpoint source changed after freeze: AGENTS.md
- offline checkpoint source changed after freeze: docs/P7_RUNTIME_OPTIMIZATION_CONSTRAINTS.md
- offline checkpoint source changed after freeze: evidence/generated/p7_ps_core_hardware_readiness.json
- offline checkpoint source changed after freeze: evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json
- offline checkpoint source changed after freeze: evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json
- offline checkpoint source changed after freeze: scripts/hw/p7_ps_application_execute.tcl
- offline checkpoint source changed after freeze: scripts/hw/run_p7_jtag_axi_stage_safe.py
- offline checkpoint source changed after freeze: scripts/hw/run_p7_ps_application_stage_safe.py
- offline checkpoint source changed after freeze: software/ps_driver/p7_app_service.c
- offline checkpoint source changed after freeze: tools/generate_p7_authorized_sequence_plan.py
- offline checkpoint source changed after freeze: tools/p7_jtag_backend.py
- offline checkpoint source changed after freeze: tools/run_p7_authorized_hardware_sequence.py
- offline checkpoint source changed after freeze: tools/run_p7_gate.py
- offline checkpoint source changed after freeze: tools/run_p7_ps_core_offline.py
- offline checkpoint source changed after freeze: tools/summarize_p7_hardware.py
- run sequence entry 0 diagnostic source mismatch
- run sequence entry 0 historical epoch binding mismatch
- run sequence entry 1 diagnostic source mismatch
- run sequence entry 1 historical epoch binding mismatch
- run sequence entry 2 diagnostic source mismatch
- run sequence entry 2 historical epoch binding mismatch
- run sequence entry 3 diagnostic source mismatch
- run sequence entry 3 historical epoch binding mismatch
- run sequence entry 4 diagnostic source mismatch
- run sequence entry 4 historical epoch binding mismatch
- run sequence entry 5 diagnostic source mismatch
- run sequence entry 5 historical epoch binding mismatch
- run sequence entry 6 diagnostic source mismatch
- run sequence entry 6 historical epoch binding mismatch
- run sequence entry 7 diagnostic source mismatch
- run sequence entry 7 historical epoch binding mismatch
- run sequence entry 8 diagnostic source mismatch
- run sequence entry 8 historical epoch binding mismatch
- run sequence entry 9 diagnostic source mismatch
- run sequence entry 9 historical epoch binding mismatch
- run sequence entry 10 diagnostic source mismatch
- run sequence entry 10 historical epoch binding mismatch
- run sequence entry 11 diagnostic source mismatch
- run sequence entry 11 historical epoch binding mismatch
- run sequence entry 12 diagnostic source mismatch
- run sequence entry 12 historical epoch binding mismatch
- run sequence entry 13 diagnostic source mismatch
- run sequence entry 13 historical epoch binding mismatch
- run sequence entry 14 diagnostic source mismatch
- run sequence entry 14 historical epoch binding mismatch
- run sequence entry 15 diagnostic source mismatch
- run sequence entry 15 historical epoch binding mismatch
- run sequence entry 16 diagnostic source mismatch
- run sequence entry 16 historical epoch binding mismatch
- run sequence entry 17 diagnostic source mismatch
- run sequence entry 17 historical epoch binding mismatch
- run sequence entry 18 diagnostic source mismatch
- run sequence entry 18 historical epoch binding mismatch
- run sequence entry 19 diagnostic source mismatch
- run sequence entry 19 historical epoch binding mismatch
- run sequence entry 20 diagnostic source mismatch
- run sequence entry 20 historical epoch binding mismatch
- run sequence entry 21 diagnostic source mismatch
- run sequence entry 21 historical epoch binding mismatch
- run sequence entry 22 diagnostic source mismatch
- run sequence entry 22 historical epoch binding mismatch
- run sequence entry 23 diagnostic source mismatch
- run sequence entry 23 historical epoch binding mismatch
- run sequence entry 24 diagnostic source mismatch
- run sequence entry 24 historical epoch binding mismatch
- run sequence entry 25 diagnostic source mismatch
- run sequence entry 25 historical epoch binding mismatch
- run sequence entry 26 diagnostic source mismatch
- run sequence entry 26 historical epoch binding mismatch
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
  "repo": "D:\\CodexWorktrees\\stage66prep_dd768f5\\RF_COMM_MULTILANE",
  "uart_access": null
}
```

