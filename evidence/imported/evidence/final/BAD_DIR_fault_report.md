# BAD_DIR Fault Report

Generated: 2026-06-28T01:52:46+08:00

Status: `RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE`

| required field | current value |
| --- | --- |
| BAD_DIR 是哪个方向 | AB_L1 at raw-pulse layer |
| 是否 TX 有 pulse | yes for AB_L1 |
| 是否 RX raw 有 pulse | no for AB_L1 |
| 是否 preamble 有增长 | no |
| 是否 CRC pass | no |
| 是否 frame good | no |
| 是否 ACK pending | no for lane0 degraded path |
| 是否 ACK TX start | yes, auxiliary B-side ACK evidence observed |
| 是否 ACK RX seen | yes by UART end-to-end protocol counters |
| 最可能原因 | AB_L1 raw RX path / physical direction / fixed-pose optical path / pin or TFDU side |
| 已排除原因 | AB_L1 is not a TX-not-started failure and is not on the accepted lane0 degraded path |
| 下一步需要什么外部条件 | optional RX microscope or physical inspection if AB_L1 repair is required; not required for constrained baseline |
| 当前 workaround | lane0-only degraded mode with payload lane mask 0x1 and ACK lane mask 0x1 |

```text
RF_COMM_BAD_DIR_FAULT_REPORT status=RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE
BAD_DIR_FINAL=AB_L1
BAD_DIR_LAYER=NO_RX_RAW_PULSE
ACK_LAYER_CLASSIFIED=1
ACK_PROTOCOL_PASS=1
DEGRADED_RELIABLE_MODE_PASS=1
```
