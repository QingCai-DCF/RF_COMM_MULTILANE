# Constrained Acceptance Matrix

Generated: 2026-06-28T01:52:46+08:00

Overall: `CONSTRAINED_2LANE_STATIC_BASELINE_PASS`

This is the target-stage matrix for `CONSTRAINED_2LANE_STATIC_BASELINE`. It is not a final product PASS and does not claim real Ethernet, real rotation, or real 4/8-lane TFDU acceptance.

| ID | 项目 | 当前是否可做 | 当前状态 | 证据 | 备注 |
| --- | --- | --- | --- | --- | --- |
| C01 | G1 single lane frozen baseline | yes | PASS | evidence/G1_freeze/G1_frozen_summary.txt | G1 frozen baseline short smoke is recorded. |
| C02 | 2 lane four-direction matrix | yes | PASS_RAW_MATRIX_COMPLETE | evidence/lane_matrix/rxonly_matrix.md | Fresh raw-pulse matrix is complete; BAD_DIR raw layer is AB_L1. |
| C03 | BAD_DIR root cause classification | yes | PASS_RAW_LAYER_CLASSIFIED | evidence/bad_dir_debug/BAD_DIR_failure_classification.md | AB_L1 is classified as NO_RX_RAW_PULSE at raw layer; lane0-only degraded mode excludes it. |
| C04 | degraded mode smoke | yes | PASS_DEGRADED_SMOKE | evidence/degraded_mode/current_degraded_mode.md | Lane0 degraded smoke passes: sent=260068 rx_ok=260068 tx_fail=0. |
| C05 | stationary capped soak | yes | PASS_CAPPED_STATIONARY_DEGRADED_SOAK | evidence/degraded_mode/current_degraded_mode.md | stage_seconds=300 window_to_shutdown_end_s=371.9. |
| C06 | UART control acceptance | yes | PASS_PS_LOCAL_UART_OBSERVED_WITH_OFFLINE_CONTROL_PROTOCOL | evidence/software_uart/uart_control_acceptance.md | PS-local run covers START/STOP/READ/SHUTDOWN; offline protocol gates cover STATUS/CONFIG/CLEAR. |
| C07 | host mock protocol | yes | PASS_OFFLINE_MOCK | evidence/software_offline/host_mock_test_summary.md | Localhost/mock only; not real Ethernet. |
| N03 | real Ethernet TCP/DHCP | no | DEFERRED_NO_ETHERNET | evidence/deferred/N03_ethernet_deferred.md | Current condition has no Ethernet cable. |
| S05 | real rotating 600 rpm | no | DEFERRED_NO_ROTATION_FIXTURE_MODEL_AVAILABLE | evidence/deferred/S05_rotation_deferred.md | No real rotation fixture/movement. |
| A02 | 8 lane TFDU hardware | no | DEFERRED_ONLY_2LANE_HARDWARE |  | Target explicitly excludes real 4/8-lane TFDU hardware in current stage. |

## Current Blockers

`NONE`

```text
RF_COMM_CONSTRAINED_ACCEPTANCE_MATRIX overall=CONSTRAINED_2LANE_STATIC_BASELINE_PASS
CONSTRAINED_2LANE_STATIC_BASELINE_PASS=1
REAL_TCP_DHCP_PASS=0
REAL_ROTATION_PASS=0
REAL_8LANE_TFDU_PASS=0
```
