# P10.1R AX7020 two-lane speed and stability final summary

- Status: `PASS`
- Source commit: `39df17155ce82e38366fbdac00c79584f0fe1afa`
- Planned checkpoint tag: `p10.1r-2lane-speed-stability-pass`
- Current-run hardware authorization: `false`
- Hardware actions in recorded runs: `true`
- Hardware actions during finalization: `false`
- Network / movement / rewiring: `false` / `false` / `false`

## Acceptance result

- F→R sustained application goodput: `4501886.293333333 bit/s`
- R→F sustained application goodput: `4501886.293333333 bit/s`
- Formal runtime: `1800.009 s`
- Formal committed bytes F→R / R→F: `436207616` / `436207616`
- 64 MiB objects F→R / R→F: `5` / `5`
- Same-module raw echo / accepted DATA: `4000` / `0`
- Cross-lane accepted DATA: `0`
- Maximum observed Txd high: `16.0 cycles`

## Counter closure

- CRC bad / SHA mismatch: `0.0` / `0.0`
- Partial / duplicate / stale commit: `0.0` / `0.0` / `0.0`
- Retry exhausted / descriptor leak / double completion: `0.0` / `0.0` / `0.0`
- Deadlock / duty / continuous-high violation: `0` / `0.0` / `0`

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

## Scope retained

This PASS is limited to the frozen stationary AX7020 two-lane half-duplex no-Ethernet artifact bundle. P11, 1+1 full duplex, 8×32, 600 rpm, physical GLOBAL_PERMIT, external TFDU electrical/duty measurement, and product-final acceptance remain outside scope.

Physical observation of the four PL LEDs in shutdown remains pending; the shutdown programming and marker evidence proves configuration intent, not the voltage or visible state at the LED pins.
