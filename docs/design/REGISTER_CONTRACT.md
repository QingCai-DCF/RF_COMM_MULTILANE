# IR AXI Register Contract

> Generated from `config/register_map/ir_axi_regs.yaml`; do not edit by hand.

- Register map version: `P8C-1` (`0x08030001`)
- Canonical source SHA256: `9993ae99c883a921f61bf1af8f1aca54b8a89fa7cd53452f435a6ed992c7fd2d`
- P0-P7 offsets and semantics are preserved; P8C is additive from `0x0400`.

| Name | Offset | Access | Description |
|---|---:|---|---|
| `CONTROL` | `0x0000` | `LEGACY` | reset, enable_phy, start, stop, clear_sticky, commit |
| `PROFILE_LANE_MASK` | `0x0004` | `LEGACY` | payload lane mask |
| `PROFILE_RX_LANE_MASK` | `0x0008` | `LEGACY` | receive lane mask |
| `PROFILE_ACK_LANE_MASK` | `0x000C` | `LEGACY` | ACK lane mask |
| `PROFILE_SESSION` | `0x0010` | `LEGACY` | session id |
| `PROFILE_PAYLOAD_LEN` | `0x0014` | `LEGACY` | payload length |
| `PROFILE_FRAGMENT_BYTES` | `0x0018` | `LEGACY` | fragment byte limit |
| `TIMING_CNT_CHIP_MAX` | `0x0020` | `LEGACY` | 4PPM chip cycles minus one |
| `TIMING_CNT_PREAMBLE` | `0x0024` | `LEGACY` | preamble symbols |
| `TIMING_DETECT_WINDOW` | `0x0028` | `LEGACY` | detect start/end packed |
| `TIMING_GUARD_CYCLES` | `0x002C` | `LEGACY` | guard cycles |
| `TIMING_RETRY_TIMEOUT` | `0x0030` | `LEGACY` | retry timeout |
| `SAFETY_STARTUP_US` | `0x0040` | `LEGACY` | TFDU startup delay |
| `SAFETY_DUTY_WINDOW` | `0x0044` | `LEGACY` | rolling duty window |
| `SAFETY_DUTY_MAX` | `0x0048` | `LEGACY` | max duty permille |
| `SAFETY_STUCK_HIGH_LIMIT` | `0x004C` | `LEGACY` | TX stuck-high limit |
| `SAFETY_SHUTDOWN_REASON` | `0x0050` | `LEGACY` | shutdown reason |
| `STATUS` | `0x0060` | `LEGACY` | phy_ready, busy, done, fail bits |
| `STATUS_RETRY_COUNT` | `0x0064` | `LEGACY` | retry count |
| `STATUS_ERROR_COUNTS` | `0x0068` | `LEGACY` | crc/session/mask bad counters packed |
| `COUNTER_TX_PULSE` | `0x0080` | `LEGACY` | TX pulse count |
| `COUNTER_RX_RAW_PULSE` | `0x0084` | `LEGACY` | RX raw pulse count |
| `COUNTER_FRAME_GOOD` | `0x0088` | `LEGACY` | good frame count |
| `COUNTER_FRAME_BAD` | `0x008C` | `LEGACY` | bad frame count |
| `COUNTER_ACK_SENT` | `0x0090` | `LEGACY` | ACK sent count |
| `COUNTER_ACK_SEEN` | `0x0094` | `LEGACY` | ACK seen count |
| `PROFILE_ID` | `0x00F0` | `LEGACY` | profile id/hash low word |
| `P6_CTRL` | `0x0100` | `LEGACY` | P6 local transport reset, clear sticky, commit, start, stop, shutdown |
| `P6_STATUS` | `0x0104` | `LEGACY` | P6 ready, committed, busy, done, fail, config rejected, timeout status |
| `P6_SESSION` | `0x0108` | `LEGACY` | P6 session id |
| `P6_LANE_MASK` | `0x010C` | `LEGACY` | P6 payload lane mask, limited to 0x1, 0x2, or 0x3 |
| `P6_ACK_LANE_MASK` | `0x0110` | `LEGACY` | P6 ACK lane mask, must match payload lane mask for P6 |
| `P6_PAYLOAD_LEN` | `0x0114` | `LEGACY` | P6 dynamic payload length, 1..247 bytes |
| `P6_PAYLOAD_PATTERN_ID` | `0x0118` | `LEGACY` | P6 payload pattern identifier |
| `P6_PAYLOAD_SEED` | `0x011C` | `LEGACY` | P6 payload seed for deterministic generation |
| `P6_PAYLOAD_CRC32` | `0x0120` | `LEGACY` | P6 committed TX payload CRC32 readback |
| `P6_RX_PAYLOAD_CRC32` | `0x0124` | `LEGACY` | P6 RX payload CRC32 readback |
| `P6_RX_PAYLOAD_LEN` | `0x0128` | `LEGACY` | P6 RX payload length readback |
| `P6_TX_COUNT` | `0x012C` | `LEGACY` | P6 local transport TX transaction count |
| `P6_RX_GOOD_COUNT_L0` | `0x0130` | `LEGACY` | P6 lane0 good RX transaction count |
| `P6_RX_GOOD_COUNT_L1` | `0x0134` | `LEGACY` | P6 lane1 good RX transaction count |
| `P6_CRC_BAD` | `0x0138` | `LEGACY` | P6 CRC bad counter |
| `P6_PAYLOAD_MISMATCH` | `0x013C` | `LEGACY` | P6 payload mismatch counter |
| `P6_RETRY_COUNT` | `0x0140` | `LEGACY` | P6 retry counter |
| `P6_RETRY_EXHAUSTED` | `0x0144` | `LEGACY` | P6 retry exhausted counter |
| `P6_TX_FAIL` | `0x0148` | `LEGACY` | P6 TX fail counter |
| `P6_TXD_HIGH_CONSECUTIVE_MAX` | `0x014C` | `LEGACY` | P6 maximum consecutive TXD-high cycles |
| `P6_DUTY_VIOLATION` | `0x0150` | `LEGACY` | P6 duty window violation counter |
| `P6_SHUTDOWN_REASON` | `0x0154` | `LEGACY` | P6 shutdown reason |
| `P6_MAILBOX_STATUS` | `0x0158` | `LEGACY` | P6 PS/JTAG mailbox status |
| `P6_TIMEOUT_CYCLES` | `0x015C` | `LEGACY` | P6 bounded timeout cycles |
| `P6_ERROR_CODE` | `0x0160` | `LEGACY` | P6 last bounded error code |
| `P6_STICKY_ERROR` | `0x0164` | `LEGACY` | P6 sticky error bits cleared by P6_CTRL clear |
| `P6_RX_DIGEST` | `0x0168` | `LEGACY` | P6 RX digest mirror |
| `P6_PAYLOAD_WORD_INDEX` | `0x016C` | `LEGACY` | P6 payload RAM word index |
| `P6_PAYLOAD_WORD_DATA` | `0x0170` | `LEGACY` | P6 payload RAM indexed word data |
| `P6_RX_WORD_INDEX` | `0x0174` | `LEGACY` | P6 RX payload RAM word index |
| `P6_RX_WORD_DATA` | `0x0178` | `LEGACY` | P6 RX payload RAM indexed word data |
| `P6_CAPS` | `0x017C` | `LEGACY` | P6 local transport capabilities and maximum payload |
| `P6_PAYLOAD_WINDOW_BASE` | `0x0200` | `LEGACY` | P6 direct TX payload window base; 64 little-endian words through 0x02FC |
| `P6_RX_WINDOW_BASE` | `0x0300` | `LEGACY` | P6 direct RX payload window base; 64 little-endian words through 0x03FC |
| `P8C_CONTROL` | `0x0400` | `WO` | P8C safety control request pulses; no permit override |
| `P8C_PERMIT_STATUS` | `0x0404` | `RO` | Read-only raw/synchronized/effective permit and endpoint safety state |
| `P8C_PERMIT_RISE_COUNT` | `0x0408` | `RO` | Sampled raw permit rising-edge count |
| `P8C_PERMIT_FALL_COUNT` | `0x040C` | `RO` | Sampled raw permit falling-edge count |
| `P8C_PERMIT_DROP_DURING_FRAME_COUNT` | `0x0410` | `RO` | Permit drops observed while a frame was active |
| `P8C_PERMIT_REARM_COUNT` | `0x0414` | `RO` | Accepted explicit endpoint arm transactions |
| `P8C_LAST_REASONS` | `0x0418` | `RO` | Last global permit drop reason and last TX kill reason |
| `P8C_BANK_FAULT_MASK` | `0x041C` | `RO` | Physical-module-expanded bank fault mask |
| `P8C_LANE_TX_PERMIT_MASK` | `0x0420` | `RO` | Lane-local TX permission mask; not a global permit |
| `P8C_EFFECTIVE_TX_ENABLE_MASK` | `0x0424` | `RO` | Actual physical TX output mask after final raw permit kill |
| `P8C_PHYSICAL_MODULE_SELECTED_MASK` | `0x0428` | `RO` | Current physical module selection mask |
| `P8C_ARM_STATUS` | `0x042C` | `RO` | Arm accept/reject observability |
| `P8C_SNAPSHOT_INDEX` | `0x0430` | `RW` | Physical module index captured by the next atomic snapshot request |
| `P8C_SNAPSHOT_ROLLING_HIGH` | `0x0440` | `RO` | Atomic snapshot rolling high cycles |
| `P8C_SNAPSHOT_ROLLING_MAX` | `0x0444` | `RO` | Atomic snapshot maximum rolling high cycles |
| `P8C_SNAPSHOT_WINDOW_CYCLES` | `0x0448` | `RO` | Exact rolling window cycles |
| `P8C_SNAPSHOT_HARD_LIMIT` | `0x044C` | `RO` | Strict less-than-20-percent integer limit |
| `P8C_SNAPSHOT_TARGET_LIMIT` | `0x0450` | `RO` | Less-than-or-equal-to-18-percent design target |
| `P8C_SNAPSHOT_DUTY_HEADROOM` | `0x0454` | `RO` | Remaining target headroom cycles |
| `P8C_SNAPSHOT_TARGET_THROTTLE_COUNT` | `0x0458` | `RO` | Target-policy throttle event count |
| `P8C_SNAPSHOT_HARD_FAULT_COUNT` | `0x045C` | `RO` | Sticky hard duty fault event count |
| `P8C_SNAPSHOT_CONTINUOUS_HIGH` | `0x0460` | `RO` | Current continuous high cycles |
| `P8C_SNAPSHOT_LONGEST_HIGH` | `0x0464` | `RO` | Longest observed high stretch cycles |
| `P8C_SNAPSHOT_STUCK_FAULT_COUNT` | `0x0468` | `RO` | Sticky continuous-high fault event count |
| `P8C_SNAPSHOT_STUCK_KILL_COUNT` | `0x046C` | `RO` | Continuous-high kill count |
| `P8C_SNAPSHOT_COOLDOWN_REMAINING` | `0x0470` | `RO` | History recovery cooldown cycles remaining |
| `P8C_SNAPSHOT_CHARGE_COUNT` | `0x0474` | `RO` | Actual or conservatively charged TX-high cycle count |
| `P8C_SNAPSHOT_FLAGS` | `0x0478` | `RO` | Atomic per-module safety flags |
| `P8C_SNAPSHOT_RX_PULSE_COUNT` | `0x047C` | `RO` | Receive-only active-low RX pulse count |
| `P8C_REGISTER_MAP_VERSION` | `0x04F0` | `RO` | P8C register map version encoding |
| `P8C_REGISTER_MAP_HASH_LOW` | `0x04F4` | `RO` | Low 32 bits of canonical register-map SHA256 |
