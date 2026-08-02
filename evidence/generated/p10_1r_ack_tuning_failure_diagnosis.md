# P10.1R ACK-tuning failure diagnosis

- Status: `FAIL_WITH_EVIDENCE`
- Run ID: `p10_1r_20260802T002938Z_e38b0772_7e24b993_0c6533e9`
- Source commit: `e38b0772f02c898ebe9b53f6ac3c1bda06a4210c`
- Failed stage: `ack_tuning`
- Hardware actions executed: `true`
- Final shutdown: fixed `PASS`, rotating `PASS`

The ACK-lane identity remediation worked: preflight, echo-tail, 4x4 crosstalk, and 4 Mbit/s PHY sanity all passed. The first F-to-R ACK-tuning transfer then remained in the healthy running state but did not complete its 16 MiB command before the paired-command deadline. All 12 shutdown records contain `SHUTDOWN_EXIT=0`, `TFDU_SHUTDOWN_PROGRAMMED=1`, and dual-board `PASS` markers.

## Direct telemetry

Between the first and last 5-second snapshots, the rotating receiver accepted 30,674 additional CRC-valid DATA frames over 25.058 seconds. Even crediting every frame with the maximum 247-byte L1 payload, this is only:

```text
30,674 * 247 * 8 / 25.058 = 2,418,861.202 bit/s
```

The sender accepted 1,039 additional ACKs over the same interval, or 29.523 DATA frames per ACK. Thus the `>=24` ACK-density objective was already met; the throughput failure cannot be repaired by merely relaxing the XSDB timeout. At the final snapshot, at most 9,099,480 of 16,777,216 requested bytes had crossed as L1 payload, projecting about 55.313 seconds for completion at that rate.

## Root cause

The model assumes a 775 us average-duty start spacing for a full DATA frame. The implemented admission gate instead requires all 8,928 Txd-high cycles of the next full frame to be free at its start. With an exact 1 ms target budget of 11,520 cycles, a following frame cannot start until the preceding history falls to 2,592 cycles or less. This conservative whole-frame reservation discards the benefit of high cycles expiring while the new frame is being serialized and approximately halves the achievable two-lane payload rate.

There is also an independent orchestration defect: 16 MiB in exactly 30 seconds requires 4,473,924.267 bit/s, while the offline model predicted only 4,427,415.552 bit/s and therefore 30.315 seconds. Fixing that test-size mismatch alone would still leave the directly measured rate below the 4,000,000 bit/s Goal gate.

## Required remediation

Implement and prove a frame-boundary admission schedule that accounts for the exact sliding window while guaranteeing no target-duty throttle can corrupt a frame. The exact duty accountant, strict hard limit, complete-frame integrity, GLOBAL_PERMIT, final TX kill, SD, Mode, and shutdown behavior must remain unchanged. Then regenerate the model, rebuild and freeze both bitstreams/XSA/BSP/ELF under new hashes, and rerun the complete hardware campaign under a fresh authorization.

Machine-readable detail is in `evidence/generated/p10_1r_ack_tuning_failure_diagnosis.json`.
