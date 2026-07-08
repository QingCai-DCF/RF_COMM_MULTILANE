# BAD_DIR Root Cause Table

Generated: 2026-06-28T01:52:46+08:00

| field | current value |
| --- | --- |
| BAD_DIR final | AB_L1 at raw-pulse layer |
| BAD_DIR candidate | AB_L1 |
| TX pulse | yes for AB_L1 |
| RX raw pulse | no for AB_L1 |
| preamble growth | no |
| CRC pass | no |
| frame good | no |
| ACK pending | no; lane0 ACK-only/framed protocol evidence passes by UART end-to-end stats |
| ACK TX start | B-side ACK/debug activity observed as auxiliary evidence |
| ACK RX seen | accepted end-to-end UART evidence: sent equals rx_ok with tx_fail=0 |
| most likely current layer | RX raw path / physical direction / fixed-pose optical path / pin or TFDU side for AB_L1 |
| excluded so far | AB_L1 is not a no-TX-pulse case and is not required for the lane0-only degraded workaround |
| still unknown | physical/root cause of the `AB_L1` raw RX failure without microscope or fixture changes |
| next required condition | optional RX microscope or physical inspection for AB_L1; not required for constrained lane0-only baseline |
| current workaround | reliable degraded payload mode uses lane0 only, payload lane mask 0x1 and ACK lane mask 0x1 |

```text
RF_COMM_BAD_DIR_ROOT_CAUSE status=RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE
BAD_DIR_FINAL=AB_L1
BAD_DIR_LAYER=NO_RX_RAW_PULSE
P1_BA_DIRECTIONS_CLASSIFIED=1
ACK_LAYER_CLASSIFIED=1
ACK_PROTOCOL_PASS=1
DEGRADED_RELIABLE_MODE_PASS=1
```
