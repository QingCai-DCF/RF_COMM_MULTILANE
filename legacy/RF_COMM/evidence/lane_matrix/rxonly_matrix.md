# P1.1 RX-Only Raw-Pulse Matrix

Generated: 2026-06-28T00:03:00+08:00

Status: `COMPLETE_WITH_BAD_DIR`

This is a raw-pulse physical matrix for the current constrained 2-lane static target. It proves pin-level pulse arrival only; it does not prove ACK, CRC, payload integrity, degraded-mode stability, Ethernet, or rotating operation.

## Source

- Analyzer report: `reports/2lane_matrix_safe_20260627_235014.ila_matrix.md`
- Analyzer JSON: `reports/2lane_matrix_safe_20260627_235014.ila_matrix.json`
- Matrix summary: `reports/2lane_matrix_safe_20260627_235014.summary.txt`

## Matrix

| direction | tx_pulse_seen | rx_raw_pulse_seen | preamble_seen | crc_ok | rx_good | verdict | evidence_csv | reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AB_L0 | 479 | 465 | N/A_RAW_ONLY | N/A_RAW_ONLY | N/A_RAW_ONLY | PASS | evidence/lane_matrix/rxonly_AB_L0.csv | A_TO_B_LANE0 has TX and corresponding RX pulse activity |
| BA_L0 | 228 | 226 | N/A_RAW_ONLY | N/A_RAW_ONLY | N/A_RAW_ONLY | PASS | evidence/lane_matrix/rxonly_BA_L0.csv | B_TO_A_LANE0 has TX and corresponding RX pulse activity |
| AB_L1 | 479 | 0 | N/A_RAW_ONLY | N/A_RAW_ONLY | N/A_RAW_ONLY | NO_RX_RAW_PULSE | evidence/lane_matrix/rxonly_AB_L1.csv | A_TO_B_LANE1 verdict=FAIL_NO_RX_ACTIVITY near_rx_echo=a_rx1:pulses=479:delay=1 |
| BA_L1 | 479 | 460 | N/A_RAW_ONLY | N/A_RAW_ONLY | N/A_RAW_ONLY | PASS | evidence/lane_matrix/rxonly_BA_L1.csv | B_TO_A_LANE1 has TX and corresponding RX pulse activity |

## Interpretation

- Complete directions captured: `AB_L0,BA_L0,AB_L1,BA_L1`
- Raw-pulse passing directions: `AB_L0,BA_L0,BA_L1`
- Raw-pulse failing directions: `AB_L1`
- Current BAD_DIR at raw-pulse layer: `AB_L1`

```text
RF_COMM_RXONLY_MATRIX status=COMPLETE_WITH_BAD_DIR
P1_MATRIX_COMPLETE=1
BAD_DIR_RAW_LAYER=AB_L1
AB_L0=PASS
BA_L0=PASS
AB_L1=NO_RX_RAW_PULSE
BA_L1=PASS
ACK_HARDWARE_PASS=0
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
