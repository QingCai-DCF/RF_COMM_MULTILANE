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
| `P6_CTRL` | `0x0100` | P6 local transport reset, clear sticky, commit, start, stop, shutdown |
| `P6_STATUS` | `0x0104` | P6 ready, committed, busy, done, fail, config rejected, timeout status |
| `P6_SESSION` | `0x0108` | P6 session id |
| `P6_LANE_MASK` | `0x010C` | P6 payload lane mask, limited to 0x1, 0x2, or 0x3 |
| `P6_ACK_LANE_MASK` | `0x0110` | P6 ACK lane mask, must match payload lane mask for P6 |
| `P6_PAYLOAD_LEN` | `0x0114` | P6 dynamic payload length, 1..247 bytes |
| `P6_PAYLOAD_PATTERN_ID` | `0x0118` | P6 payload pattern identifier |
| `P6_PAYLOAD_SEED` | `0x011C` | P6 payload seed for deterministic generation |
| `P6_PAYLOAD_CRC32` | `0x0120` | P6 committed TX payload CRC32 readback |
| `P6_RX_PAYLOAD_CRC32` | `0x0124` | P6 RX payload CRC32 readback |
| `P6_RX_PAYLOAD_LEN` | `0x0128` | P6 RX payload length readback |
| `P6_TX_COUNT` | `0x012C` | P6 local transport TX transaction count |
| `P6_RX_GOOD_COUNT_L0` | `0x0130` | P6 lane0 good RX transaction count |
| `P6_RX_GOOD_COUNT_L1` | `0x0134` | P6 lane1 good RX transaction count |
| `P6_CRC_BAD` | `0x0138` | P6 CRC bad counter |
| `P6_PAYLOAD_MISMATCH` | `0x013C` | P6 payload mismatch counter |
| `P6_RETRY_COUNT` | `0x0140` | P6 retry counter |
| `P6_RETRY_EXHAUSTED` | `0x0144` | P6 retry exhausted counter |
| `P6_TX_FAIL` | `0x0148` | P6 TX fail counter |
| `P6_TXD_HIGH_CONSECUTIVE_MAX` | `0x014C` | P6 maximum consecutive TXD-high cycles |
| `P6_DUTY_VIOLATION` | `0x0150` | P6 duty window violation counter |
| `P6_SHUTDOWN_REASON` | `0x0154` | P6 shutdown reason |
| `P6_MAILBOX_STATUS` | `0x0158` | P6 PS/JTAG mailbox status |
| `P6_TIMEOUT_CYCLES` | `0x015C` | P6 bounded timeout cycles |
| `P6_ERROR_CODE` | `0x0160` | P6 last bounded error code |
| `P6_STICKY_ERROR` | `0x0164` | P6 sticky error bits cleared by P6_CTRL clear |
| `P6_RX_DIGEST` | `0x0168` | P6 RX digest mirror |
| `P6_PAYLOAD_WORD_INDEX` | `0x016C` | P6 payload RAM word index |
| `P6_PAYLOAD_WORD_DATA` | `0x0170` | P6 payload RAM indexed word data |
| `P6_RX_WORD_INDEX` | `0x0174` | P6 RX payload RAM word index |
| `P6_RX_WORD_DATA` | `0x0178` | P6 RX payload RAM indexed word data |
| `P6_CAPS` | `0x017C` | P6 local transport capabilities and maximum payload |
| `P6_PAYLOAD_WINDOW_BASE` | `0x0200` | P6 direct TX payload window base; 64 little-endian words through 0x02FC |
| `P6_RX_WINDOW_BASE` | `0x0300` | P6 direct RX payload window base; 64 little-endian words through 0x03FC |
