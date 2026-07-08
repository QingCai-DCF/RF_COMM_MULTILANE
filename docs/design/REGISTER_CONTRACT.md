# IR AXI Register Contract

| Name | Offset | Description |
|---|---:|---|
| `CONTROL` | `0x0000` | reset, enable_phy, start, stop, clear_sticky, commit |
| `PROFILE_LANE_MASK` | `0x0004` | payload lane mask |
| `PROFILE_RX_LANE_MASK` | `0x0008` | receive lane mask |
| `PROFILE_ACK_LANE_MASK` | `0x000C` | ACK lane mask |
| `PROFILE_SESSION` | `0x0010` | session id |
| `PROFILE_PAYLOAD_LEN` | `0x0014` | payload length |
| `PROFILE_FRAGMENT_BYTES` | `0x0018` | fragment byte limit |
| `TIMING_CNT_CHIP_MAX` | `0x0020` | 4PPM chip cycles minus one |
| `TIMING_CNT_PREAMBLE` | `0x0024` | preamble symbols |
| `TIMING_DETECT_WINDOW` | `0x0028` | detect start/end packed |
| `TIMING_GUARD_CYCLES` | `0x002C` | guard cycles |
| `TIMING_RETRY_TIMEOUT` | `0x0030` | retry timeout |
| `SAFETY_STARTUP_US` | `0x0040` | TFDU startup delay |
| `SAFETY_DUTY_WINDOW` | `0x0044` | rolling duty window |
| `SAFETY_DUTY_MAX` | `0x0048` | max duty permille |
| `SAFETY_STUCK_HIGH_LIMIT` | `0x004C` | TX stuck-high limit |
| `SAFETY_SHUTDOWN_REASON` | `0x0050` | shutdown reason |
| `STATUS` | `0x0060` | phy_ready, busy, done, fail bits |
| `STATUS_RETRY_COUNT` | `0x0064` | retry count |
| `STATUS_ERROR_COUNTS` | `0x0068` | crc/session/mask bad counters packed |
| `COUNTER_TX_PULSE` | `0x0080` | TX pulse count |
| `COUNTER_RX_RAW_PULSE` | `0x0084` | RX raw pulse count |
| `COUNTER_FRAME_GOOD` | `0x0088` | good frame count |
| `COUNTER_FRAME_BAD` | `0x008C` | bad frame count |
| `COUNTER_ACK_SENT` | `0x0090` | ACK sent count |
| `COUNTER_ACK_SEEN` | `0x0094` | ACK seen count |
| `PROFILE_ID` | `0x00F0` | profile id/hash low word |
