# M3 CRC Bad ACK Suppression Reference

M3_CRC_BAD_ACK_SUPPRESSION_REPORT=1
M3_CRC_BAD_FRAME_DETECTED=1
M3_CRC_BAD_ACK_SUPPRESSED=1
M3_CRC_BAD_RETRY_EXHAUSTED=1
M3_CRC_BAD_ACK_REFERENCE=PASS

| Item | Value |
|---|---|
| frame crc ok | False |
| ack sent | False |
| ARQ tx attempts | 3 |
| ARQ timeouts | 3 |
| ARQ retry exhausted | True |

This is an offline cross-layer reference for the lane0 ACK-only requirement: a CRC-bad L1 frame must not produce ACK, so L2 must observe ACK loss and exhaust retries according to the configured timeout/retry policy.
