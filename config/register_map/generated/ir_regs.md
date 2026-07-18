# IR AXI Register Contract

> Generated from `config/register_map/ir_axi_regs.yaml`; do not edit by hand.

- Register map version: `P8D-1` (`0x08040001`)
- Canonical source SHA256: `8f029023d7871a7b8351c9c9256164d34a0ec2954754c261c31da410851d34b1`
- Compatibility: P0-P8C offsets and meanings are preserved; P8D is additive from 0x0500.

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
| `P8D_CONTROL` | `0x0500` | `WO` | P8D request pulses; no physical permit or safety override |
| `P8D_STATUS` | `0x0504` | `RO` | Data-plane state and atomic snapshot validity |
| `P8D_L2_PROTOCOL_VERSION` | `0x0508` | `RO` | Negotiated-capable L2 vNext protocol version |
| `P8D_L2_CAPABILITIES` | `0x050C` | `RO` | SACK, aggregation, path-epoch, streaming, AXIS width capabilities |
| `P8D_PROTOCOL_MODE` | `0x0510` | `RW` | Atomic session mode: legacy stop-and-wait or selective-repeat vNext |
| `P8D_SESSION_EPOCH` | `0x0514` | `RW` | Current data-plane session epoch |
| `P8D_PATH_EPOCH` | `0x0518` | `RW` | Current accepted path epoch |
| `P8D_TX_WINDOW_SIZE` | `0x051C` | `RW` | Global TX selective-repeat window size |
| `P8D_RX_WINDOW_SIZE` | `0x0520` | `RW` | Global RX reorder window size |
| `P8D_RETRY_CONFIG` | `0x0524` | `RW` | Bounded maximum retry and initial RTO configuration |
| `P8D_TX_NEXT_SEQUENCE` | `0x0528` | `RO` | Next globally allocated TX sequence |
| `P8D_TX_ACK_BASE` | `0x052C` | `RO` | Lowest TX sequence not cumulatively acknowledged |
| `P8D_RX_BASE_SEQUENCE` | `0x0530` | `RO` | Lowest RX sequence not contiguously delivered |
| `P8D_GLOBAL_OUTSTANDING_COUNT` | `0x0534` | `RO` | Current global outstanding count |
| `P8D_GLOBAL_OUTSTANDING_HIGH_WATERMARK` | `0x0538` | `RO` | Atomic snapshot global outstanding high watermark |
| `P8D_SACK_WINDOW_BITS` | `0x053C` | `RW` | Negotiated SACK bitmap width |
| `P8D_LAST_SACK_BITMAP_LOW` | `0x0540` | `RO` | Atomic snapshot SACK bits 31:0 |
| `P8D_LAST_SACK_BITMAP_HIGH` | `0x0544` | `RO` | Atomic snapshot SACK bits 63:32 |
| `P8D_ACK_AGGREGATION_COUNT` | `0x0548` | `RO` | Frames accumulated into ACK batches |
| `P8D_ACK_TIMER_EXPIRY_COUNT` | `0x054C` | `RO` | Maximum ACK delay expirations |
| `P8D_ACK_FRAMES_SENT` | `0x0550` | `RO` | Aggregated ACK frames sent |
| `P8D_ACK_FRAMES_RECEIVED` | `0x0554` | `RO` | ACK/SACK frames received |
| `P8D_DUPLICATE_ACK_COUNT` | `0x0558` | `RO` | Duplicate ACK count |
| `P8D_STALE_ACK_COUNT` | `0x055C` | `RO` | Old-session ACK rejection count |
| `P8D_OUT_OF_WINDOW_ACK_COUNT` | `0x0560` | `RO` | Future or malformed ACK-window rejection count |
| `P8D_TX_RETRY_COUNT` | `0x0564` | `RO` | TX retry attempt count |
| `P8D_TX_RETRY_EXHAUSTED_COUNT` | `0x0568` | `RO` | Bounded retry exhaustion count |
| `P8D_TIMEOUT_COUNT` | `0x056C` | `RO` | RTO expiry count |
| `P8D_MIGRATION_COUNT` | `0x0570` | `RO` | Unacknowledged-entry migration count |
| `P8D_LANE_FAULT_MIGRATION_COUNT` | `0x0574` | `RO` | Lane-fault-triggered migration count |
| `P8D_DUTY_DEFER_COUNT` | `0x0578` | `RO` | P8C duty-headroom scheduler deferrals |
| `P8D_PERMIT_DEFER_COUNT` | `0x057C` | `RO` | GLOBAL_PERMIT-effective scheduler deferrals |
| `P8D_MAPPING_DEFER_COUNT` | `0x0580` | `RO` | P8B mapping-invalid scheduler deferrals |
| `P8D_RX_OUT_OF_ORDER_COUNT` | `0x0584` | `RO` | Accepted out-of-order data count |
| `P8D_RX_DUPLICATE_COUNT` | `0x0588` | `RO` | Suppressed duplicate data count |
| `P8D_RX_OLD_COUNT` | `0x058C` | `RO` | Old sequence rejection count |
| `P8D_RX_FUTURE_COUNT` | `0x0590` | `RO` | Future out-of-window rejection count |
| `P8D_RX_STALE_SESSION_COUNT` | `0x0594` | `RO` | Stale session data rejection count |
| `P8D_RX_STALE_PATH_EPOCH_COUNT` | `0x0598` | `RO` | Stale path-attempt rejection count |
| `P8D_RX_GAP_COUNT` | `0x059C` | `RO` | RX reorder gap observation count |
| `P8D_RX_GAP_TIMEOUT_COUNT` | `0x05A0` | `RO` | Bounded gap recovery expiry count |
| `P8D_SCHEDULER_ACTIVE_MASK` | `0x05A4` | `RW` | Logical lane scheduling enable mask |
| `P8D_SCHEDULER_STARVATION_BOUND` | `0x05A8` | `RW` | Configured bounded-starvation limit |
| `P8D_SCHEDULER_DEFER_REASON` | `0x05AC` | `RO` | Last scheduler defer reason |
| `P8D_SCHEDULER_WEIGHT0` | `0x05B0` | `RW` | Lane 0 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT1` | `0x05B4` | `RW` | Lane 1 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT2` | `0x05B8` | `RW` | Lane 2 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT3` | `0x05BC` | `RW` | Lane 3 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT4` | `0x05C0` | `RW` | Lane 4 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT5` | `0x05C4` | `RW` | Lane 5 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT6` | `0x05C8` | `RW` | Lane 6 byte-deficit weight |
| `P8D_SCHEDULER_WEIGHT7` | `0x05CC` | `RW` | Lane 7 byte-deficit weight |
| `P8D_SCHEDULER_STARVATION_MAX` | `0x05D0` | `RO` | Maximum observed eligible-lane starvation cycles |
| `P8D_TX_RING_DEPTH` | `0x05D4` | `RW` | Independent TX descriptor ring depth |
| `P8D_TX_RING_PRODUCER` | `0x05D8` | `RO` | Monotonic TX producer counter |
| `P8D_TX_RING_CONSUMER` | `0x05DC` | `RO` | Monotonic TX consumer counter |
| `P8D_TX_RING_GENERATION` | `0x05E0` | `RO` | TX generation/epoch |
| `P8D_TX_RING_HIGH_WATERMARK` | `0x05E4` | `RO` | TX ring high watermark |
| `P8D_TX_RING_FULL_COUNT` | `0x05E8` | `RO` | TX ring full backpressure count |
| `P8D_RX_RING_DEPTH` | `0x05EC` | `RW` | Independent RX descriptor ring depth |
| `P8D_RX_RING_PRODUCER` | `0x05F0` | `RO` | Monotonic RX producer counter |
| `P8D_RX_RING_CONSUMER` | `0x05F4` | `RO` | Monotonic RX consumer counter |
| `P8D_RX_RING_GENERATION` | `0x05F8` | `RO` | RX generation/epoch |
| `P8D_RX_RING_HIGH_WATERMARK` | `0x05FC` | `RO` | RX ring high watermark |
| `P8D_RX_RING_FULL_COUNT` | `0x0600` | `RO` | RX ring full backpressure count |
| `P8D_DESCRIPTOR_COMPLETE_COUNT` | `0x0604` | `RO` | Single descriptor completion count |
| `P8D_DESCRIPTOR_ERROR_COUNT` | `0x0608` | `RO` | Descriptor error completion count |
| `P8D_DESCRIPTOR_ABORT_COUNT` | `0x060C` | `RO` | Deterministically aborted descriptors |
| `P8D_DESCRIPTOR_STALE_GENERATION_COUNT` | `0x0610` | `RO` | Rejected stale-generation completion count |
| `P8D_AXIS_TX_STALL_CYCLES` | `0x0614` | `RO` | TX AXI-Stream backpressure cycles |
| `P8D_AXIS_RX_STALL_CYCLES` | `0x0618` | `RO` | RX AXI-Stream backpressure cycles |
| `P8D_AXIS_PROTOCOL_ERROR_COUNT` | `0x061C` | `RO` | Malformed TKEEP/TLAST/length count |
| `P8D_PAYLOAD_STORE_USED` | `0x0620` | `RO` | Shared frame-store allocation count |
| `P8D_PAYLOAD_STORE_HIGH_WATERMARK` | `0x0624` | `RO` | Shared frame-store high watermark |
| `P8D_ABORT_STREAM_ID` | `0x0628` | `RW` | Stream correlation for bounded abort |
| `P8D_ABORT_OBJECT_ID` | `0x062C` | `RW` | Object correlation for bounded abort |
| `P8D_REGISTER_MAP_VERSION` | `0x0630` | `RO` | P8D register-map version encoding |
| `P8D_REGISTER_MAP_HASH_LOW` | `0x0634` | `RO` | Low 32 bits of canonical register-map SHA256 |
| `P8D_LANE0_SCHEDULED_FRAMES` | `0x0640` | `RO` | Lane 0 scheduled frames |
| `P8D_LANE0_SCHEDULED_BYTES` | `0x0644` | `RO` | Lane 0 scheduled bytes |
| `P8D_LANE0_RETRIES` | `0x0648` | `RO` | Lane 0 retries |
| `P8D_LANE0_MIGRATIONS` | `0x064C` | `RO` | Lane 0 migrations |
| `P8D_LANE0_DEFER_COUNT` | `0x0650` | `RO` | Lane 0 deferrals |
| `P8D_LANE1_SCHEDULED_FRAMES` | `0x0654` | `RO` | Lane 1 scheduled frames |
| `P8D_LANE1_SCHEDULED_BYTES` | `0x0658` | `RO` | Lane 1 scheduled bytes |
| `P8D_LANE1_RETRIES` | `0x065C` | `RO` | Lane 1 retries |
| `P8D_LANE1_MIGRATIONS` | `0x0660` | `RO` | Lane 1 migrations |
| `P8D_LANE1_DEFER_COUNT` | `0x0664` | `RO` | Lane 1 deferrals |
| `P8D_LANE2_SCHEDULED_FRAMES` | `0x0668` | `RO` | Lane 2 scheduled frames |
| `P8D_LANE2_SCHEDULED_BYTES` | `0x066C` | `RO` | Lane 2 scheduled bytes |
| `P8D_LANE2_RETRIES` | `0x0670` | `RO` | Lane 2 retries |
| `P8D_LANE2_MIGRATIONS` | `0x0674` | `RO` | Lane 2 migrations |
| `P8D_LANE2_DEFER_COUNT` | `0x0678` | `RO` | Lane 2 deferrals |
| `P8D_LANE3_SCHEDULED_FRAMES` | `0x067C` | `RO` | Lane 3 scheduled frames |
| `P8D_LANE3_SCHEDULED_BYTES` | `0x0680` | `RO` | Lane 3 scheduled bytes |
| `P8D_LANE3_RETRIES` | `0x0684` | `RO` | Lane 3 retries |
| `P8D_LANE3_MIGRATIONS` | `0x0688` | `RO` | Lane 3 migrations |
| `P8D_LANE3_DEFER_COUNT` | `0x068C` | `RO` | Lane 3 deferrals |
| `P8D_LANE4_SCHEDULED_FRAMES` | `0x0690` | `RO` | Lane 4 scheduled frames |
| `P8D_LANE4_SCHEDULED_BYTES` | `0x0694` | `RO` | Lane 4 scheduled bytes |
| `P8D_LANE4_RETRIES` | `0x0698` | `RO` | Lane 4 retries |
| `P8D_LANE4_MIGRATIONS` | `0x069C` | `RO` | Lane 4 migrations |
| `P8D_LANE4_DEFER_COUNT` | `0x06A0` | `RO` | Lane 4 deferrals |
| `P8D_LANE5_SCHEDULED_FRAMES` | `0x06A4` | `RO` | Lane 5 scheduled frames |
| `P8D_LANE5_SCHEDULED_BYTES` | `0x06A8` | `RO` | Lane 5 scheduled bytes |
| `P8D_LANE5_RETRIES` | `0x06AC` | `RO` | Lane 5 retries |
| `P8D_LANE5_MIGRATIONS` | `0x06B0` | `RO` | Lane 5 migrations |
| `P8D_LANE5_DEFER_COUNT` | `0x06B4` | `RO` | Lane 5 deferrals |
| `P8D_LANE6_SCHEDULED_FRAMES` | `0x06B8` | `RO` | Lane 6 scheduled frames |
| `P8D_LANE6_SCHEDULED_BYTES` | `0x06BC` | `RO` | Lane 6 scheduled bytes |
| `P8D_LANE6_RETRIES` | `0x06C0` | `RO` | Lane 6 retries |
| `P8D_LANE6_MIGRATIONS` | `0x06C4` | `RO` | Lane 6 migrations |
| `P8D_LANE6_DEFER_COUNT` | `0x06C8` | `RO` | Lane 6 deferrals |
| `P8D_LANE7_SCHEDULED_FRAMES` | `0x06CC` | `RO` | Lane 7 scheduled frames |
| `P8D_LANE7_SCHEDULED_BYTES` | `0x06D0` | `RO` | Lane 7 scheduled bytes |
| `P8D_LANE7_RETRIES` | `0x06D4` | `RO` | Lane 7 retries |
| `P8D_LANE7_MIGRATIONS` | `0x06D8` | `RO` | Lane 7 migrations |
| `P8D_LANE7_DEFER_COUNT` | `0x06DC` | `RO` | Lane 7 deferrals |
