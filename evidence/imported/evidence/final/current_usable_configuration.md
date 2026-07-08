# Current Usable Configuration

Generated: 2026-06-28T01:52:46+08:00

## Current Status

Current safe operating mode for the constrained 2-lane target is `LANE0_DEGRADED_RELIABLE_2LANE_STATIC`: lane0 carries payload and ACK, while `AB_L1` remains excluded by the raw-layer BAD_DIR classification.

| field | value |
| --- | --- |
| 当前可用 lane / direction | lane0 degraded reliable path: AB_L0 and BA_L0 |
| 当前禁用 lane / direction | AB_L1 for reliable payload/ACK until raw RX fault is resolved |
| payload lane mask | 0x00000001 |
| ack lane mask | 0x00000001 |
| retry 参数 | 12 |
| detect window 参数 | ACK-only G1-sized build: A detect 0..5, B detect 0..7 |
| payload / fragment 参数 | payload=256 bytes; hardware packet/transfer bytes=264; fragment=255 |
| 预期吞吐 | degraded capped soak window rx Mbps=1.775 |
| 已验证时长 | degraded window to shutdown end seconds=371.9, stage_seconds=300 |
| 已知限制 | no Ethernet, no rotation fixture, AB_L1 raw-layer BAD_DIR, no real 4/8-lane TFDU hardware acceptance |

```text
RF_COMM_CURRENT_USABLE_CONFIGURATION status=LANE0_DEGRADED_RELIABLE_2LANE_STATIC
ACK_PROTOCOL_PASS=1
DEGRADED_RELIABLE_MODE_PASS=1
DEGRADED_SENT=260068
DEGRADED_RX_OK=260068
DEGRADED_TX_FAIL=0
G1_FROZEN_BASELINE_AVAILABLE=1
```
