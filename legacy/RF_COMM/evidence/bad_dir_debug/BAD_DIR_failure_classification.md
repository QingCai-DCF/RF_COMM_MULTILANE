# BAD_DIR Failure Classification

Generated: 2026-06-28T01:52:46+08:00

Status: `RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE`

Current fresh P1.1 evidence captures all four raw-pulse directions. The failing raw-layer direction is `AB_L1`. This is a raw RX-layer classification only. Lane0 ACK-only and degraded payload evidence now pass, so the constrained-stage workaround is lane0-only operation while `AB_L1` remains excluded.

## Current Observations

| direction | current classification | evidence |
| --- | --- | --- |
| AB_L0 | PASS | `evidence/lane_matrix/rxonly_matrix.md` |
| BA_L0 | PASS | `evidence/lane_matrix/rxonly_matrix.md` |
| AB_L1 | NO_RX_RAW_PULSE | `evidence/lane_matrix/rxonly_matrix.md` |
| BA_L1 | PASS | `evidence/lane_matrix/rxonly_matrix.md` |

```text
RF_COMM_BAD_DIR_CLASSIFICATION status=RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE
BAD_DIR_FINAL=AB_L1
BAD_DIR_LAYER=NO_RX_RAW_PULSE
P1_MATRIX_COMPLETE=1
ACK_LAYER_CLASSIFIED=1
ACK_PROTOCOL_PASS=1
DEGRADED_RELIABLE_MODE_PASS=1
```
