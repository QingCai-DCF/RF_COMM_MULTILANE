# P10.1R integrity-pipeline remediation

- Status: `PASS_OFFLINE_HARDWARE_PENDING`
- Implementation checkpoint: `8d19744e651cf3b0c56780b1f6fb18473c87b859`
- Hardware actions executed: `false`

The immutable failed run measured 3.919459 seconds of receiver verification inside a 32.801575-second fixed-side interval. Its transport-only reconciliation is 28.454609 seconds, or 4,217,243 bit/s, but that calculation is diagnostic evidence and is not hardware PASS.

The receiver clean path previously made seven full passes over every segment. It now makes two: byte equality is fused with the incremental output CRC32 update, followed by one incremental output SHA256 pass. Input CRC32/SHA256 remains the single incremental calculation performed during slot preparation. A first mismatch is still reported exactly; per-segment input/output CRC/SHA classification runs on the error path; final stream CRC32 and SHA256 equality still gates the one atomic commit.

The reflected CRC32 implementation uses a 16-entry nibble table. A bit-at-a-time test oracle, the standard `123456789 → cbf43926` vector, deterministic 4,096-byte equivalence, split incremental updates, equal fused comparison, and first-mismatch fused comparison all pass. The P10.1R model and hardware-runner unit suites also pass (20 tests).

No RTL protocol, duty/safety logic, `GLOBAL_PERMIT`, pinmap, XDC, or lane mapping changed. New source-bound ELF and artifact hashes plus fresh direct hardware acceptance are required; no prior hardware result is inherited.
