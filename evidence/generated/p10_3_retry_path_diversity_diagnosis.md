# P10.3F retry path-diversity diagnosis

- Status: `PASS` for diagnosis only; this is not a hardware acceptance result.
- Preserved failed run: `p10_3f_full_20260804T231038Z_81e05d27_9ae79d14_e7389fda`
- Failed stage/case: `degrade` / `degrade_static_unavailable_8`
- Final shutdown: fixed `PASS`, rotating `PASS`
- Hardware actions performed for this diagnosis: `false`

## Direct observations

The fixed endpoint stopped with ACK base 11420, next sequence 11451, 11,466
attempts, 29 retries, 30 timeouts, 14 migrations, and one exhausted entry. The
rotating endpoint stopped at RX base 11419 with SACK `0x000FFFFE`. It accepted
2,820,492 application bytes.

| Lane | Fixed scheduled | Fixed retries selected | Fixed retry migrations | Rotating DATA good | Rotating CRC bad |
|---:|---:|---:|---:|---:|---:|
| 0 | 3822 | 9 | 8 | 3822 | 0 |
| 1 | 3822 | 11 | 0 | 3797 | 1 |
| 2 | 3822 | 6 | 6 | 3821 | 0 |
| 3 (unavailable by test) | 0 | 0 | 0 | 0 | 0 |

The 11 retries selected onto lane 1 had no matching migration. The previous
RTL allowed the immediately failed lane to compete again, so a concentrated
lane-1 loss episode could spend the bounded retry budget on that same path even
while lanes 0 and 2 remained safe and eligible. This is a scheduler
path-diversity weakness exposed by the run; the physical cause of the lane-1
loss itself is not established by these digital records.

No digital TX safety violation was observed. Fixed-side maximum continuous-high
was 16 cycles (0.25 us at 64 MHz), maximum rolling duty was 11,504/64,000 =
17.975%, and all four safety-fault flags and hard-fault counters were zero.
This does not substitute for omitted oscilloscope, current, temperature, or
optical-detector measurements.

## Remediation basis

To enforce existing requirement `P10_3-ARQ-001`, a timed-out retry now excludes
its immediately previous lane whenever another safe eligible lane exists. It
may reuse the previous lane only when that lane is the sole eligible path, so
4-to-3-to-2-to-1 degradation retains forward progress.

The change only removes a lane from the scheduler selection mask. It cannot
assert `GLOBAL_PERMIT`, arm an endpoint, create lane permit/PHY readiness/duty
headroom/frame admission, or override TX kill. New artifacts and complete
offline and hardware reacceptance remain mandatory; no old hardware PASS is
inherited.

Machine-readable record:
`evidence/generated/p10_3_retry_path_diversity_diagnosis.json`.
