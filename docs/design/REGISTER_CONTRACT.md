# IR AXI Register Contract

> Generated from `config/register_map/ir_axi_regs.yaml`; do not edit by hand.

- Register map version: `P10-4` (`0x0A000004`)
- Canonical source SHA256: `06c2105e05cbad4dd780316cf44dd857b13a32dad584e2df2ab4a5b8bcfecb39`
- Compatibility: P0-P10.3F offsets and meanings are preserved; P10.4 appends unambiguous performance counters at 0x0D84-0x0DAC and a fail-closed local-source test injection at 0x0DB0-0x0DBC.

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
| `P9_ID` | `0x0700` | `RO` | P9 Z7010 stationary two-lane peripheral identity |
| `P9_BUILD_ID` | `0x0704` | `RO` | P9 functional build identity |
| `P9_PROFILE_ID` | `0x0708` | `RO` | Z7010 two-lane development profile identity |
| `P9_REGISTER_MAP_VERSION` | `0x070C` | `RO` | Canonical generated register-map version |
| `P9_REGISTER_MAP_HASH_LOW` | `0x0710` | `RO` | Low 32 bits of canonical register-map SHA256 |
| `P9_CAPABILITIES` | `0x0714` | `RO` | Payload, window, module, lane and protocol capabilities |
| `P9_CONTROL` | `0x0718` | `WO` | Fail-closed P9 control request pulses and receiver enable commands |
| `P9_STATUS` | `0x071C` | `RO` | Endpoint, object, stream and raw-generator status |
| `P9_PHY_STATUS` | `0x0720` | `RO` | Per-module ready, startup and sticky safety masks |
| `P9_OBJECT_ERROR` | `0x0724` | `RO` | Sticky P9 object error code |
| `P9_OBJECT_CONFIG` | `0x0728` | `RW` | Lane mask, PHY rate and payload direction |
| `P9_LANE_WEIGHTS` | `0x072C` | `RW` | Two 8-bit health-weighted scheduler weights |
| `P9_SESSION_EPOCH` | `0x0730` | `RW` | P9 selective-repeat session epoch |
| `P9_PATH_EPOCH` | `0x0734` | `RW` | P9 physical-attempt path epoch |
| `P9_OBJECT_ID` | `0x0738` | `RW` | P9 object identity |
| `P9_FAULT_INJECTION` | `0x073C` | `RW` | Bounded DATA/ACK drop counts and live lane-unavailable mask |
| `P9_RAW_CONFIG` | `0x0740` | `RW` | Raw pulse lane mask and direction |
| `P9_RAW_TARGET` | `0x0744` | `RW` | Raw pulse train target count |
| `P9_RAW_SPACING` | `0x0748` | `RW` | Raw pulse spacing in 64 MHz cycles |
| `P9_RAW_SENT_COUNT` | `0x074C` | `RO` | Completed raw pulse trains |
| `P9_INPUT_BYTE_COUNT` | `0x0750` | `RO` | Accepted AXI DMA MM2S bytes |
| `P9_OUTPUT_BYTE_COUNT` | `0x0754` | `RO` | Delivered AXI DMA S2MM bytes |
| `P9_TX_SEQUENCE_BASE` | `0x0758` | `RO` | Packed TX next sequence and cumulative ACK base |
| `P9_WINDOW_STATUS` | `0x075C` | `RO` | RX base, outstanding count and outstanding high watermark |
| `P9_SACK_BITMAP` | `0x0760` | `RO` | Current 32-bit SACK bitmap |
| `P9_TX_ATTEMPT_COUNT` | `0x0764` | `RO` | Physical DATA attempt handshakes |
| `P9_TX_RETRY_COUNT` | `0x0768` | `RO` | Selective-repeat retries |
| `P9_TX_RETRY_EXHAUSTED_COUNT` | `0x076C` | `RO` | Bounded retry exhaustion count |
| `P9_TX_TIMEOUT_COUNT` | `0x0770` | `RO` | RTO expiry count |
| `P9_TX_MIGRATION_COUNT` | `0x0774` | `RO` | Unacknowledged-attempt lane migration count |
| `P9_RX_DUPLICATE_COUNT` | `0x0778` | `RO` | Suppressed duplicate DATA frames |
| `P9_ACK_AGGREGATION_COUNT` | `0x077C` | `RO` | DATA frames accumulated for ACK/SACK |
| `P9_ACK_TIMER_EXPIRY_COUNT` | `0x0780` | `RO` | ACK maximum-delay expirations |
| `P9_ACK_FRAMES_SENT` | `0x0784` | `RO` | Reverse optical ACK/SACK frames sent |
| `P9_DUPLICATE_ACK_COUNT` | `0x0788` | `RO` | Duplicate ACK observations |
| `P9_STALE_ACK_COUNT` | `0x078C` | `RO` | Stale-session ACK rejections |
| `P9_OUT_OF_WINDOW_ACK_COUNT` | `0x0790` | `RO` | Malformed or future ACK-window rejections |
| `P9_RX_STALE_SESSION_COUNT` | `0x0794` | `RO` | Stale-session DATA rejections |
| `P9_RX_STALE_PATH_COUNT` | `0x0798` | `RO` | Stale-path DATA rejections |
| `P9_PHYSICAL_DATA_GOOD` | `0x079C` | `RO` | Direction-selected good physical DATA frames |
| `P9_PHYSICAL_ACK_GOOD` | `0x07A0` | `RO` | Direction-selected good physical ACK frames |
| `P9_PHYSICAL_CRC_BAD` | `0x07A4` | `RO` | All-module physical CRC failures |
| `P9_PHYSICAL_DROP_DATA` | `0x07A8` | `RO` | Injected DATA frame drops |
| `P9_PHYSICAL_DROP_ACK` | `0x07AC` | `RO` | Injected ACK frame drops |
| `P9_LANE0_SCHEDULED_FRAMES` | `0x07B0` | `RO` | Lane 0 scheduled frame count |
| `P9_LANE1_SCHEDULED_FRAMES` | `0x07B4` | `RO` | Lane 1 scheduled frame count |
| `P9_LANE0_SCHEDULED_BYTES` | `0x07B8` | `RO` | Lane 0 scheduled byte count |
| `P9_LANE1_SCHEDULED_BYTES` | `0x07BC` | `RO` | Lane 1 scheduled byte count |
| `P9_LANE0_RETRIES` | `0x07C0` | `RO` | Lane 0 retry count |
| `P9_LANE1_RETRIES` | `0x07C4` | `RO` | Lane 1 retry count |
| `P9_LANE0_MIGRATIONS` | `0x07C8` | `RO` | Lane 0 migration count |
| `P9_LANE1_MIGRATIONS` | `0x07CC` | `RO` | Lane 1 migration count |
| `P9_SCHEDULER_STARVATION_MAX` | `0x07D0` | `RO` | Maximum eligible-lane starvation |
| `P9_RAW_RX_A0` | `0x07D4` | `RO` | A-side lane 0 raw active-low pulse count |
| `P9_RAW_RX_A1` | `0x07D8` | `RO` | A-side lane 1 raw active-low pulse count |
| `P9_RAW_RX_B0` | `0x07DC` | `RO` | B-side lane 0 raw active-low pulse count |
| `P9_RAW_RX_B1` | `0x07E0` | `RO` | B-side lane 1 raw active-low pulse count |
| `P9_PHYSICAL_TX_A0` | `0x07E4` | `RO` | A-side lane 0 physical pulse count |
| `P9_PHYSICAL_TX_A1` | `0x07E8` | `RO` | A-side lane 1 physical pulse count |
| `P9_PHYSICAL_TX_B0` | `0x07EC` | `RO` | B-side lane 0 physical pulse count |
| `P9_PHYSICAL_TX_B1` | `0x07F0` | `RO` | B-side lane 1 physical pulse count |
| `P9_TX_HIGH_MAX_A0` | `0x07F4` | `RO` | A-side lane 0 maximum continuous Txd high cycles |
| `P9_TX_HIGH_MAX_A1` | `0x07F8` | `RO` | A-side lane 1 maximum continuous Txd high cycles |
| `P9_TX_HIGH_MAX_B0` | `0x07FC` | `RO` | B-side lane 0 maximum continuous Txd high cycles |
| `P9_TX_HIGH_MAX_B1` | `0x0800` | `RO` | B-side lane 1 maximum continuous Txd high cycles |
| `P9_DUTY_MAX_A0` | `0x0804` | `RO` | A-side lane 0 maximum rolling-window high cycles |
| `P9_DUTY_MAX_A1` | `0x0808` | `RO` | A-side lane 1 maximum rolling-window high cycles |
| `P9_DUTY_MAX_B0` | `0x080C` | `RO` | B-side lane 0 maximum rolling-window high cycles |
| `P9_DUTY_MAX_B1` | `0x0810` | `RO` | B-side lane 1 maximum rolling-window high cycles |
| `P9_DUTY_CURRENT_A0` | `0x0814` | `RO` | A-side lane 0 current rolling-window high cycles |
| `P9_DUTY_CURRENT_A1` | `0x0818` | `RO` | A-side lane 1 current rolling-window high cycles |
| `P9_DUTY_CURRENT_B0` | `0x081C` | `RO` | B-side lane 0 current rolling-window high cycles |
| `P9_DUTY_CURRENT_B1` | `0x0820` | `RO` | B-side lane 1 current rolling-window high cycles |
| `P9_DUTY_HEADROOM_A0` | `0x0824` | `RO` | A-side lane 0 target-duty headroom cycles |
| `P9_DUTY_HEADROOM_A1` | `0x0828` | `RO` | A-side lane 1 target-duty headroom cycles |
| `P9_DUTY_HEADROOM_B0` | `0x082C` | `RO` | B-side lane 0 target-duty headroom cycles |
| `P9_DUTY_HEADROOM_B1` | `0x0830` | `RO` | B-side lane 1 target-duty headroom cycles |
| `P9_DUTY_THROTTLE_A0` | `0x0834` | `RO` | A-side lane 0 target-duty throttle count |
| `P9_DUTY_THROTTLE_A1` | `0x0838` | `RO` | A-side lane 1 target-duty throttle count |
| `P9_DUTY_THROTTLE_B0` | `0x083C` | `RO` | B-side lane 0 target-duty throttle count |
| `P9_DUTY_THROTTLE_B1` | `0x0840` | `RO` | B-side lane 1 target-duty throttle count |
| `P9_DUTY_HARD_FAULT_A0` | `0x0844` | `RO` | A-side lane 0 hard-duty fault count |
| `P9_DUTY_HARD_FAULT_A1` | `0x0848` | `RO` | A-side lane 1 hard-duty fault count |
| `P9_DUTY_HARD_FAULT_B0` | `0x084C` | `RO` | B-side lane 0 hard-duty fault count |
| `P9_DUTY_HARD_FAULT_B1` | `0x0850` | `RO` | B-side lane 1 hard-duty fault count |
| `P9_DUTY_WINDOW_CYCLES` | `0x0854` | `RO` | Exact 1 ms rolling duty window cycles |
| `P9_DUTY_HARD_LIMIT` | `0x0858` | `RO` | Strict less-than-20-percent high-cycle limit |
| `P9_DUTY_TARGET_LIMIT` | `0x085C` | `RO` | Less-than-or-equal-to-18-percent target high cycles |
| `P9_INITIAL_SEQUENCE` | `0x0860` | `RW` | Bounded validation-only selective-repeat initial sequence |
| `P9_PROTOCOL_FAULT_FLAGS` | `0x0864` | `RW` | Bounded validation fault injection; scheduler-only mapping and target-duty masks never bypass physical safety |
| `P9_RX_OUT_OF_ORDER_COUNT` | `0x0868` | `RO` | Current-run accepted out-of-order frame count |
| `P9_RX_OLD_COUNT` | `0x086C` | `RO` | Current-run old-sequence rejection count |
| `P9_RX_FUTURE_COUNT` | `0x0870` | `RO` | Current-run future-window rejection count |
| `P9_RX_GAP_COUNT` | `0x0874` | `RO` | Current-run reorder-gap observation count |
| `P9_RX_DELIVERY_COUNT` | `0x0878` | `RO` | Current-run ordered delivery count |
| `P9_RX_PROTOCOL_ERROR_COUNT` | `0x087C` | `RO` | Current-run receive protocol error count |
| `P9_PHYSICAL_FRAME_BAD_COUNT` | `0x0880` | `RO` | Current-run physical parser rejected-frame count |
| `P9_PHYSICAL_PREAMBLE_COUNT` | `0x0884` | `RO` | Current-run physical preamble count |
| `P9_PHYSICAL_SYMBOL_ERROR_COUNT` | `0x0888` | `RO` | Current-run physical symbol error count |
| `P10_1_PHYSICAL_DATA_GOOD_LANE0` | `0x088C` | `RO` | P10.1 lane0 CRC-valid DATA frame count for crosstalk attribution |
| `P10_1_PHYSICAL_DATA_GOOD_LANE1` | `0x0890` | `RO` | P10.1 lane1 CRC-valid DATA frame count for crosstalk attribution |
| `P10_1_PHYSICAL_ACK_GOOD_LANE0` | `0x0894` | `RO` | P10.1 lane0 CRC-valid ACK frame count |
| `P10_1_PHYSICAL_ACK_GOOD_LANE1` | `0x0898` | `RO` | P10.1 lane1 CRC-valid ACK frame count |
| `P10_1_PHYSICAL_CRC_BAD_LANE0` | `0x089C` | `RO` | P10.1 lane0 physical CRC failure count |
| `P10_1_PHYSICAL_CRC_BAD_LANE1` | `0x08A0` | `RO` | P10.1 lane1 physical CRC failure count |
| `P10_1_PHYSICAL_FRAME_BAD_LANE0` | `0x08A4` | `RO` | P10.1 lane0 rejected physical frame count |
| `P10_1_PHYSICAL_FRAME_BAD_LANE1` | `0x08A8` | `RO` | P10.1 lane1 rejected physical frame count |
| `P10_1_PHYSICAL_PREAMBLE_LANE0` | `0x08AC` | `RO` | P10.1 lane0 physical preamble count |
| `P10_1_PHYSICAL_PREAMBLE_LANE1` | `0x08B0` | `RO` | P10.1 lane1 physical preamble count |
| `P10_1_PHYSICAL_SYMBOL_ERROR_LANE0` | `0x08B4` | `RO` | P10.1 lane0 physical symbol error count |
| `P10_1_PHYSICAL_SYMBOL_ERROR_LANE1` | `0x08B8` | `RO` | P10.1 lane1 physical symbol error count |
| `P9_AUTO_MIGRATION_STATUS` | `0x08BC` | `RO` | Atomic bad-CRC retry-migration arm, trigger, target and effective lane-unavailable state |
| `P9_AUTO_MIGRATION_SEQUENCE` | `0x08C0` | `RO` | Atomic trigger sequence in bits 15:0 and pre-trigger cumulative ACK base in bits 31:16 |
| `P9_AUTO_MIGRATION_WINDOW` | `0x08C4` | `RO` | Atomic trigger-time outstanding frame count in bits 5:0 |
| `P9_AUTO_MIGRATION_ATTEMPT_COUNT` | `0x08C8` | `RO` | TX attempt count atomically captured when the bad-CRC target frame completed |
| `P9_AUTO_MIGRATION_PHYSICAL_TX_COUNT` | `0x08CC` | `RO` | Target module physical Txd pulse count atomically captured at trigger |
| `P9_AUTO_MIGRATION_TRIGGER_COUNT` | `0x08D0` | `RO` | Explicit-clear current-run atomic auto-migration trigger count |
| `P9_EFFECTIVE_LANE_UNAVAILABLE` | `0x08D4` | `RO` | Live external OR validation-internal lane-unavailable mask |
| `P9_AUTO_MIGRATION_PREVIOUS_MIGRATION_COUNT` | `0x08D8` | `RO` | TX migration count atomically captured at trigger; must be zero for the direct current-object precondition |
| `P9_AUTO_MIGRATION_TARGET_SCHEDULED_COUNT` | `0x08DC` | `RO` | Target-lane scheduler frame count atomically captured at trigger |
| `P10_1_PERF_CAPS` | `0x0900` | `RO` | P10.1 autonomous performance capability identity |
| `P10_1_PERF_VERSION` | `0x0904` | `RO` | P10.1 performance command and metric schema version |
| `P10_1_PERF_COMMAND` | `0x0908` | `RW` | Versioned PERF_CAPS/CONFIG/START/STATUS/SNAPSHOT/STOP/ABORT/CLEAR command |
| `P10_1_PERF_STATUS` | `0x090C` | `RO` | Autonomous service state, fault, completion, and active flags |
| `P10_1_PERF_CONFIG0` | `0x0910` | `RW` | Direction, lane mask, hash mode, and formal-window configuration |
| `P10_1_PERF_DURATION_SECONDS` | `0x0914` | `RW` | Formal measurement duration in seconds |
| `P10_1_TOTAL_BYTES_LOW` | `0x0918` | `RW` | Configured total application bytes bits 31:0 |
| `P10_1_TOTAL_BYTES_HIGH` | `0x091C` | `RW` | Configured total application bytes bits 63:32 |
| `P10_1_OBJECT_SIZE_BYTES` | `0x0920` | `RW` | Configured logical object size |
| `P10_1_SEGMENT_SIZE_BYTES` | `0x0924` | `RW` | Configured streaming segment size |
| `P10_1_PATTERN_SEED` | `0x0928` | `RW` | Payload pattern and deterministic seed |
| `P10_1_PIPELINE_CONFIG` | `0x092C` | `RW` | Buffer count, descriptor ring depth, and descriptor batch |
| `P10_1_PROTOCOL_CONFIG` | `0x0930` | `RW` | ACK threshold, outstanding frames, and interrupt coalescing |
| `P10_1_SNAPSHOT_CONTROL` | `0x0934` | `RW` | Atomic counter/timer snapshot and explicit clear requests |
| `P10_1_SNAPSHOT_GENERATION` | `0x0938` | `RO` | Even generation denotes one coherent counter snapshot |
| `P10_1_TIMER_SNAPSHOT_LOW` | `0x093C` | `RO` | Atomic PL timer snapshot bits 31:0 |
| `P10_1_TIMER_SNAPSHOT_HIGH` | `0x0940` | `RO` | Atomic PL timer snapshot bits 63:32 |
| `P10_1_APPLICATION_ACCEPTED_LOW` | `0x0944` | `RO` | Application bytes accepted bits 31:0 |
| `P10_1_APPLICATION_ACCEPTED_HIGH` | `0x0948` | `RO` | Application bytes accepted bits 63:32 |
| `P10_1_APPLICATION_COMMITTED_LOW` | `0x094C` | `RO` | Remotely committed application bytes bits 31:0 |
| `P10_1_APPLICATION_COMMITTED_HIGH` | `0x0950` | `RO` | Remotely committed application bytes bits 63:32 |
| `P10_1_FRAME_ACKED_LOW` | `0x0954` | `RO` | Deduplicated frame payload bytes acknowledged bits 31:0 |
| `P10_1_FRAME_ACKED_HIGH` | `0x0958` | `RO` | Deduplicated frame payload bytes acknowledged bits 63:32 |
| `P10_1_WIRE_BYTES_LOW` | `0x095C` | `RO` | Wire bytes including protocol overhead bits 31:0 |
| `P10_1_WIRE_BYTES_HIGH` | `0x0960` | `RO` | Wire bytes including protocol overhead bits 63:32 |
| `P10_1_DESCRIPTOR_SUBMITTED` | `0x0964` | `RO` | Descriptors submitted in the current formal window |
| `P10_1_DESCRIPTOR_COMPLETED` | `0x0968` | `RO` | Descriptors completed exactly once in the current formal window |
| `P10_1_DMA_STALL_LOW` | `0x096C` | `RO` | DMA stall cycles bits 31:0 |
| `P10_1_DMA_STALL_HIGH` | `0x0970` | `RO` | DMA stall cycles bits 63:32 |
| `P10_1_AXIS_STALL_LOW` | `0x0974` | `RO` | AXI-Stream backpressure stall cycles bits 31:0 |
| `P10_1_AXIS_STALL_HIGH` | `0x0978` | `RO` | AXI-Stream backpressure stall cycles bits 63:32 |
| `P10_1_QUEUE_OCCUPANCY` | `0x097C` | `RO` | Current and high-water queue occupancy |
| `P10_1_ACK_WAIT_LOW` | `0x0980` | `RO` | ACK/SACK wait cycles bits 31:0 |
| `P10_1_ACK_WAIT_HIGH` | `0x0984` | `RO` | ACK/SACK wait cycles bits 63:32 |
| `P10_1_DIRECTION_QUIET_LOW` | `0x0988` | `RO` | Direction quiet cycles bits 31:0 |
| `P10_1_DIRECTION_QUIET_HIGH` | `0x098C` | `RO` | Direction quiet cycles bits 63:32 |
| `P10_1_PS_PREPARE_LOW` | `0x0990` | `RO` | PS payload-preparation timer ticks bits 31:0 |
| `P10_1_PS_PREPARE_HIGH` | `0x0994` | `RO` | PS payload-preparation timer ticks bits 63:32 |
| `P10_1_CRC_SHA_LOW` | `0x0998` | `RO` | CRC/SHA timer ticks bits 31:0 |
| `P10_1_CRC_SHA_HIGH` | `0x099C` | `RO` | CRC/SHA timer ticks bits 63:32 |
| `P10_1_TRACE_STATUS` | `0x09A0` | `RO` | PS trace and PL event FIFO occupancy, generation, and overflow |
| `P10_1_STREAM_STATUS` | `0x09A4` | `RO` | Stream active, abort, restart, generation, and atomic-publish status |
| `P10_1_EVENT_FIFO_DATA` | `0x09A8` | `RO` | Nonblocking PL event FIFO pop data |
| `P10_1_EVENT_FIFO_STATUS` | `0x09AC` | `RO` | PL event FIFO occupancy, empty/full, generation, and overflow |
| `P10_1_INTEGRITY_ERROR_COUNT` | `0x09B0` | `RO` | CRC/SHA/pattern verification failure count |
| `P10_1_RETRY_EXHAUSTED_COUNT` | `0x09B4` | `RO` | Bounded retry exhaustion count in the measurement window |
| `P10_1_DESCRIPTOR_LEAK_COUNT` | `0x09B8` | `RO` | Descriptors not reclaimed at terminal state |
| `P10_1_DOUBLE_COMPLETION_COUNT` | `0x09BC` | `RO` | Duplicate descriptor completion attempts |
| `P10_1R_SNAPSHOT_CONTROL` | `0x0A00` | `WO` | Bit 0 atomically snapshots all P10.1R RX-admission counters and timestamps |
| `P10_1R_SNAPSHOT_GENERATION` | `0x0A04` | `RO` | Even generation incremented by two for each completed atomic P10.1R snapshot |
| `P10_1R_CAPS` | `0x0A08` | `RO` | P10.1R RX-admission capability and schema identity |
| `P10_1R_ADMISSION_STATUS` | `0x0A0C` | `RO` | Snapshotted per-lane quarantine, post-TX guard, admission-enable, and local-node identity |
| `P10_1R_RAW_RX_PULSE_LANE0` | `0x0A10` | `RO` | Snapshotted local module lane0 raw Rxd pulse count |
| `P10_1R_RAW_RX_PULSE_LANE1` | `0x0A14` | `RO` | Snapshotted local module lane1 raw Rxd pulse count |
| `P10_1R_RAW_WHILE_LOCAL_TX_LANE0` | `0x0A18` | `RO` | Snapshotted lane0 raw Rxd pulses observed while final physical Txd was high |
| `P10_1R_RAW_WHILE_LOCAL_TX_LANE1` | `0x0A1C` | `RO` | Snapshotted lane1 raw Rxd pulses observed while final physical Txd was high |
| `P10_1R_BLANKED_RAW_PULSE_LANE0` | `0x0A20` | `RO` | Snapshotted lane0 raw pulses withheld by receive admission |
| `P10_1R_BLANKED_RAW_PULSE_LANE1` | `0x0A24` | `RO` | Snapshotted lane1 raw pulses withheld by receive admission |
| `P10_1R_BLANKED_FRAME_START_LANE0` | `0x0A28` | `RO` | Snapshotted lane0 shadow-decoder preambles observed during quarantine |
| `P10_1R_BLANKED_FRAME_START_LANE1` | `0x0A2C` | `RO` | Snapshotted lane1 shadow-decoder preambles observed during quarantine |
| `P10_1R_BLANKED_CRC_VALID_LANE0` | `0x0A30` | `RO` | Snapshotted lane0 CRC-valid shadow frames observed during quarantine; never admitted |
| `P10_1R_BLANKED_CRC_VALID_LANE1` | `0x0A34` | `RO` | Snapshotted lane1 CRC-valid shadow frames observed during quarantine; never admitted |
| `P10_1R_LOCAL_SOURCE_REJECT_LANE0` | `0x0A38` | `RO` | Snapshotted lane0 CRC-valid frames rejected because source_node_id equals local_node_id |
| `P10_1R_LOCAL_SOURCE_REJECT_LANE1` | `0x0A3C` | `RO` | Snapshotted lane1 CRC-valid frames rejected because source_node_id equals local_node_id |
| `P10_1R_ACCEPTED_REMOTE_LANE0` | `0x0A40` | `RO` | Snapshotted lane0 CRC-valid remote frames accepted for the local object role |
| `P10_1R_ACCEPTED_REMOTE_LANE1` | `0x0A44` | `RO` | Snapshotted lane1 CRC-valid remote frames accepted for the local object role |
| `P10_1R_POST_TX_GUARD_TOTAL_LANE0` | `0x0A48` | `RO` | Snapshotted lane0 accumulated post-TX quarantine cycles |
| `P10_1R_POST_TX_GUARD_TOTAL_LANE1` | `0x0A4C` | `RO` | Snapshotted lane1 accumulated post-TX quarantine cycles |
| `P10_1R_POST_TX_GUARD_MAX_LANE0` | `0x0A50` | `RO` | Snapshotted lane0 maximum post-TX quarantine duration |
| `P10_1R_POST_TX_GUARD_MAX_LANE1` | `0x0A54` | `RO` | Snapshotted lane1 maximum post-TX quarantine duration |
| `P10_1R_ECHO_TAIL_MAX_LANE0` | `0x0A58` | `RO` | Snapshotted lane0 maximum raw echo-tail offset after final local Txd |
| `P10_1R_ECHO_TAIL_MAX_LANE1` | `0x0A5C` | `RO` | Snapshotted lane1 maximum raw echo-tail offset after final local Txd |
| `P10_1R_DECODER_CLEAR_COUNT_LANE0` | `0x0A60` | `RO` | Snapshotted lane0 decoder-clear assertion count |
| `P10_1R_DECODER_CLEAR_COUNT_LANE1` | `0x0A64` | `RO` | Snapshotted lane1 decoder-clear assertion count |
| `P10_1R_LAST_TXD_RISE_LANE0` | `0x0A68` | `RO` | Snapshotted lane0 last final physical Txd rising-edge timestamp |
| `P10_1R_LAST_TXD_RISE_LANE1` | `0x0A6C` | `RO` | Snapshotted lane1 last final physical Txd rising-edge timestamp |
| `P10_1R_LAST_TXD_FALL_LANE0` | `0x0A70` | `RO` | Snapshotted lane0 last final physical Txd falling-edge timestamp |
| `P10_1R_LAST_TXD_FALL_LANE1` | `0x0A74` | `RO` | Snapshotted lane1 last final physical Txd falling-edge timestamp |
| `P10_1R_FIRST_RXD_AFTER_TX_LANE0` | `0x0A78` | `RO` | Snapshotted lane0 first local raw Rxd edge timestamp after final Txd |
| `P10_1R_FIRST_RXD_AFTER_TX_LANE1` | `0x0A7C` | `RO` | Snapshotted lane1 first local raw Rxd edge timestamp after final Txd |
| `P10_1R_LAST_RXD_AFTER_TX_LANE0` | `0x0A80` | `RO` | Snapshotted lane0 last local raw Rxd edge timestamp after final Txd |
| `P10_1R_LAST_RXD_AFTER_TX_LANE1` | `0x0A84` | `RO` | Snapshotted lane1 last local raw Rxd edge timestamp after final Txd |
| `P10_1R_TX_RX_OVERLAP_VIOLATION` | `0x0A88` | `RO` | Snapshotted structural final-Txd and RX-admission overlap violations |
| `P10_1R_RX_ADMISSION_VIOLATION` | `0x0A8C` | `RO` | Snapshotted fail-closed maximum-quarantine violations |
| `P10_1R_NON_TARGET_ACCEPTED` | `0x0A90` | `RO` | Snapshotted accepted CRC-valid frames on lanes outside the configured lane mask |
| `P10_1R_CROSS_LANE_ACCEPTED` | `0x0A94` | `RO` | Snapshotted accepted frames whose encoded logical lane differs from the receiving physical lane |
| `P10_1R_MIN_POST_TX_GUARD_CYCLES` | `0x0A98` | `RO` | Hardware-measured post-TX guard selection; final artifact acceptance must reverify it |
| `P10_1R_RXD_IDLE_QUAL_CYCLES` | `0x0A9C` | `RO` | Offline candidate Rxd idle qualification interval |
| `P10_1R_MAX_ECHO_QUARANTINE_CYCLES` | `0x0AA0` | `RO` | Fail-closed maximum echo quarantine interval |
| `P10_1R_DECODER_CLEAR_CYCLES` | `0x0AA4` | `RO` | Minimum decoder clear interval in protocol clocks |
| `P10_1R_ADMISSION_CONFIG_FLAGS` | `0x0AA8` | `RO` | Bit0 local-source rejection enabled; bit1 guard measurement telemetry enabled |
| `P10_2_SNAPSHOT_CONTROL` | `0x0B00` | `WO` | Bit 0 atomically snapshots the P10.2 four-lane/per-module telemetry window |
| `P10_2_SNAPSHOT_GENERATION` | `0x0B04` | `RO` | Even generation incremented by two for each completed atomic P10.2 snapshot |
| `P10_2_SNAPSHOT_SCHEMA` | `0x0B08` | `RO` | P10.2 snapshot schema identity 0x50310201 |
| `P10_2_SNAPSHOT_DATA_BASE` | `0x0B0C` | `RO` | Base of 128 coherent 32-bit snapshot words through 0x0D08; words 0-7 global, 8+12*lane per-lane, 56+8*module per-module, 120-127 safety/schema |
| `P10_FF_CAPABILITIES` | `0x0D10` | `RO` | First-fault recorder identity, lane/module count, event words, and snapshot words |
| `P10_FF_STATUS` | `0x0D14` | `RO` | Frozen/post-trace/read/archive/clear/hold/shutdown/kill/direct-fault status bits |
| `P10_FF_FAULT_SEQUENCE` | `0x0D18` | `RO` | Monotonic first-fault capture sequence since PL configuration |
| `P10_FF_FAULT_TIMESTAMP_LOW` | `0x0D1C` | `RO` | Frozen first-fault 64 MHz timestamp bits 31:0 |
| `P10_FF_FAULT_TIMESTAMP_HIGH` | `0x0D20` | `RO` | Frozen first-fault 64 MHz timestamp bits 63:32 |
| `P10_FF_FAULT_CAUSE` | `0x0D24` | `RO` | Frozen module safety/object/retry cause vector |
| `P10_FF_SNAPSHOT_WORDS` | `0x0D28` | `RO` | Number of immutable 32-bit words in the first-fault snapshot |
| `P10_FF_PRE_EVENT_COUNT` | `0x0D2C` | `RO` | Chronological pre-fault circular BRAM event count |
| `P10_FF_POST_EVENT_COUNT` | `0x0D30` | `RO` | Bounded post-fault kill/shutdown trace event count |
| `P10_FF_TOTAL_EVENT_COUNT` | `0x0D34` | `RO` | Total chronological pre-fault plus post-fault event count |
| `P10_FF_EVENT_DEPTH` | `0x0D38` | `RO` | Total BRAM event capacity including reserved post-fault tail |
| `P10_FF_SNAPSHOT_INDEX` | `0x0D3C` | `RW` | Indirect immutable first-fault snapshot word index |
| `P10_FF_SNAPSHOT_DATA` | `0x0D40` | `RO` | Indexed first-fault snapshot word; ordered reads participate in archive interlock |
| `P10_FF_EVENT_INDEX` | `0x0D44` | `RW` | Indirect chronological event entry index |
| `P10_FF_EVENT_WORD_INDEX` | `0x0D48` | `RW` | Indirect event word index 0..7 |
| `P10_FF_EVENT_DATA` | `0x0D4C` | `RO` | Indexed synchronous BRAM event word; ordered reads participate in archive interlock |
| `P10_FF_ARCHIVE_DIGEST0` | `0x0D50` | `RW` | Archived raw-binary SHA256 word 0, little-endian |
| `P10_FF_ARCHIVE_DIGEST1` | `0x0D54` | `RW` | Archived raw-binary SHA256 word 1, little-endian |
| `P10_FF_ARCHIVE_DIGEST2` | `0x0D58` | `RW` | Archived raw-binary SHA256 word 2, little-endian |
| `P10_FF_ARCHIVE_DIGEST3` | `0x0D5C` | `RW` | Archived raw-binary SHA256 word 3, little-endian |
| `P10_FF_ARCHIVE_DIGEST4` | `0x0D60` | `RW` | Archived raw-binary SHA256 word 4, little-endian |
| `P10_FF_ARCHIVE_DIGEST5` | `0x0D64` | `RW` | Archived raw-binary SHA256 word 5, little-endian |
| `P10_FF_ARCHIVE_DIGEST6` | `0x0D68` | `RW` | Archived raw-binary SHA256 word 6, little-endian |
| `P10_FF_ARCHIVE_DIGEST7` | `0x0D6C` | `RW` | Archived raw-binary SHA256 word 7, little-endian |
| `P10_FF_ARCHIVE_COMMIT` | `0x0D70` | `WO` | Write 0x41524348 only after raw read, SHA256 verification, JSON parsing, and archival |
| `P10_FF_CLEAR_KEY` | `0x0D74` | `WO` | Explicit bounded two-key clear: 0x46524F5A then 0x434C5241 while fully shut down |
| `P10_FF_CLEAR_AUDIT` | `0x0D78` | `RO` | Accepted clear count bits 15:0 and rejected archive/clear count bits 31:16 |
| `P10_FF_CHECKPOINT` | `0x0D7C` | `RW` | Write an observational staircase/checkpoint tag into the pre-fault event ring |
| `P10_FF_READ_PROGRESS` | `0x0D80` | `RO` | Frozen/read/archive progress and frozen event count summary |
| `P10_4_COUNTER_SCHEMA` | `0x0D84` | `RO` | P10.4 split performance-counter schema identity 0x50310401 |
| `P10_4_OUTSTANDING_UNACKED_LOW` | `0x0D88` | `RO` | Snapshotted cycles with an active object and one or more unacknowledged frames; accurate alias for deprecated ambiguous ACK_WAIT |
| `P10_4_OUTSTANDING_UNACKED_HIGH` | `0x0D8C` | `RO` | High word of P10_4_OUTSTANDING_UNACKED |
| `P10_4_TX_IDLE_DUE_TO_ACK_LOW` | `0x0D90` | `RO` | Snapshotted sender cycles deliberately idle after a physical DATA burst while awaiting reverse ACK |
| `P10_4_TX_IDLE_DUE_TO_ACK_HIGH` | `0x0D94` | `RO` | High word of P10_4_TX_IDLE_DUE_TO_ACK |
| `P10_4_WINDOW_FULL_STALL_LOW` | `0x0D98` | `RO` | Snapshotted payload-allocation cycles blocked by a directly full selective-repeat window |
| `P10_4_WINDOW_FULL_STALL_HIGH` | `0x0D9C` | `RO` | High word of P10_4_WINDOW_FULL_STALL |
| `P10_4_RECEIVER_CREDIT_STALL_LOW` | `0x0DA0` | `RO` | Snapshotted ready-attempt cycles blocked specifically by zero peer receiver credit |
| `P10_4_RECEIVER_CREDIT_STALL_HIGH` | `0x0DA4` | `RO` | High word of P10_4_RECEIVER_CREDIT_STALL |
| `P10_4_DIRECTION_TURNAROUND_IDLE_LOW` | `0x0DA8` | `RO` | Snapshotted idle cycles in explicit DATA/ACK half-duplex turnaround and guard states |
| `P10_4_DIRECTION_TURNAROUND_IDLE_HIGH` | `0x0DAC` | `RO` | High word of P10_4_DIRECTION_TURNAROUND_IDLE |
| `P10_4_LOCAL_SOURCE_TEST_CONTROL` | `0x0DB0` | `WO` | Write 0x4C53 in bits31:16 and a nonzero lane mask in bits3:0; accepted only while full-shutdown, TX-killed, and object-idle; creates no Txd |
| `P10_4_LOCAL_SOURCE_TEST_STATUS` | `0x0DB4` | `RO` | Bit31 injection-safe now; bits3:0 last accepted lane mask |
| `P10_4_LOCAL_SOURCE_TEST_ACCEPT_COUNT` | `0x0DB8` | `RO` | Accepted fail-closed digital source-ID injection command count |
| `P10_4_LOCAL_SOURCE_TEST_REJECT_COUNT` | `0x0DBC` | `RO` | Rejected malformed or unsafe local-source test command count |
