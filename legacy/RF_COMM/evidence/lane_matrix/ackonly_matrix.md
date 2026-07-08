# P1 ACK-Only Matrix

Generated: 2026-06-28T01:52:46+08:00

Status: `ACK_ONLY_PASS`

ACK-only testing has now been executed with the lane0 ACK-only artifact. Protocol acceptance is based on the UART end-to-end stage summaries: each trigger run must have nonzero `sent`, `sent == rx_ok`, zero unrecovered errors, `last_error=none`, lane0 raw pulse evidence in both directions, and shutdown-after-run.

| trigger | raw_verdict | uart_sent | uart_rx_ok | uart_tx_fail | last_error | run_log |
| --- | --- | --- | --- | --- | --- | --- |
| a_tx_lane0 | PASS_EXPECTED_RAW | 6643 | 6643 | 0 | none | reports/2lane_matrix_safe_20260628_012647.a_tx_lane0.run.log |
| b_rx_check_state | PASS_ANY_A_TO_B | 6743 | 6743 | 0 | none | reports/2lane_matrix_safe_20260628_012647.b_rx_check_state.run.log |
| b_rx_flush_state | PASS_ANY_A_TO_B | 6717 | 6717 | 0 | none | reports/2lane_matrix_safe_20260628_012647.b_rx_flush_state.run.log |
| b_tx_lane0 | PASS_EXPECTED_RAW | 6710 | 6710 | 0 | none | reports/2lane_matrix_safe_20260628_012647.b_tx_lane0.run.log |

## Evidence Boundary

- RX-only matrix: `evidence/lane_matrix/rxonly_matrix.md`
- Constrained baseline summary: `reports/constrained_2lane_static_baseline_current.summary.txt`
- ACK safe summary: `reports/p0_ack_only_safe_20260628_012612_488_41700.summary.txt`
- ACK matrix JSON: `reports/2lane_matrix_safe_20260628_012647.ila_matrix.json`

```text
RF_COMM_ACKONLY_MATRIX status=ACK_ONLY_PASS
ACK_ONLY_RUN_COMPLETE=1
ACK_PHYSICAL_RAW_PASS=1
ACK_PROTOCOL_PASS=1
ACK_HARDWARE_PASS=1
B_ACK_SEEN=1
B_RX_GOOD_SEEN=0
UART_PROTOCOL_GATE=sent_eq_rx_ok_zero_errors
SOURCE_RUN_HARDWARE_PROGRAMMING=1
SOURCE_RUN_SHUTDOWN_AFTER_EACH_RUN=1
SOURCE_RUN_MAX_TFDU_WINDOW_SECONDS=56.1
DOCUMENT_GENERATION_NO_HARDWARE_PROGRAMMING=1
DOCUMENT_GENERATION_NO_UART_WRITE=1
DOCUMENT_GENERATION_NO_TFDU_DRIVE=1
```
