# P10.1R hardware evidence consistency

- Status: `PASS`
- Source commit: `39df17155ce82e38366fbdac00c79584f0fe1afa`
- Current-run hardware authorization: `false`
- Hardware actions in the recorded campaign: `true`
- Hardware actions during this finalization: `false`
- Network used: `false`
- Hardware movement / rewiring: `false` / `false`

## Immutable run coverage

| Stage | Run ID | Manifest files | Fixed shutdown | Rotating shutdown |
|---|---|---:|---|---|
| `preflight` | `p10_1r_20260803T130535Z_39df1715_56533798_df0c60f6` | 59 | PASS | PASS |
| `echo_tail` | `p10_1r_20260803T103315Z_39df1715_56533798_df0c60f6` | 47 | PASS | PASS |
| `crosstalk` | `p10_1r_20260803T114324Z_39df1715_56533798_df0c60f6` | 91 | PASS | PASS |
| `phy_sanity` | `p10_1r_20260803T114645Z_39df1715_56533798_df0c60f6` | 59 | PASS | PASS |
| `ack_tuning` | `p10_1r_20260803T114906Z_39df1715_56533798_df0c60f6` | 47 | PASS | PASS |
| `performance` | `p10_1r_20260803T115204Z_39df1715_56533798_df0c60f6` | 203 | PASS | PASS |
| `streaming_64m` | `p10_1r_20260803T120402Z_39df1715_56533798_df0c60f6` | 135 | PASS | PASS |
| `formal_30min` | `p10_1r_20260803T123306Z_39df1715_56533798_df0c60f6` | 143 | PASS | PASS |

## Mandatory exit gates

- `FAILURE_BASELINE_FROZEN`: `PASS`
- `OLD_AUTHORIZATION_CLOSED`: `PASS`
- `PER_MODULE_TX_RX_EXCLUSION`: `PASS`
- `OTHER_LANE_NOT_BLANKED`: `PASS`
- `DECODER_CLEAR_ON_TX`: `PASS`
- `POST_TX_GUARD_MEASURED`: `PASS`
- `LOCAL_SOURCE_REJECTION`: `PASS`
- `SAME_MODULE_RAW_ECHO_OBSERVABLE`: `PASS`
- `SAME_MODULE_ACCEPTED_DATA_ZERO`: `PASS`
- `NON_TARGET_ACCEPTED_CRC_VALID_ZERO`: `PASS`
- `CROSS_LANE_ACCEPTED_ZERO`: `PASS`
- `ACK_BUNDLE_WINDOW`: `PASS`
- `NO_PER_OBJECT_TURNAROUND`: `PASS`
- `MULTI_OBJECT_PIPELINE`: `PASS`
- `HOST_NOT_IN_FAST_PATH`: `PASS`
- `F_TO_R_APPLICATION_GOODPUT_4MBPS`: `PASS`
- `R_TO_F_APPLICATION_GOODPUT_4MBPS`: `PASS`
- `STREAMING_64M_F_TO_R_5X`: `PASS`
- `STREAMING_64M_R_TO_F_5X`: `PASS`
- `STREAM_ABORT_RESET_RECOVERY`: `PASS`
- `STATIONARY_30MIN`: `PASS`
- `CRC_BAD_ZERO`: `PASS`
- `SHA_MISMATCH_ZERO`: `PASS`
- `PARTIAL_DUPLICATE_STALE_ZERO`: `PASS`
- `RETRY_EXHAUSTED_ZERO`: `PASS`
- `DESCRIPTOR_LEAK_ZERO`: `PASS`
- `DOUBLE_COMPLETION_ZERO`: `PASS`
- `DEADLOCK_ZERO`: `PASS`
- `DUTY_VIOLATION_ZERO`: `PASS`
- `CONTINUOUS_HIGH_VIOLATION_ZERO`: `PASS`
- `SHUTDOWN_FIXED`: `PASS`
- `SHUTDOWN_ROTATING`: `PASS`
- `EVIDENCE_CONSISTENCY`: `PASS`

The pre-existing offline consistency evidence remains at `p10_1r_evidence_consistency.json`; it was not overwritten. The adjacent JSON is authoritative for the hardware campaign.
