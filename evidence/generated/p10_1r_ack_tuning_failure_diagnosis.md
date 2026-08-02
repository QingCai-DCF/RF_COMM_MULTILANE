# P10.1R ACK tuning failure diagnosis

Status: **FAIL_DIAGNOSED**. This document explains the immutable failed run; it is not hardware PASS evidence.

## Direct evidence

- Run: `p10_1r_20260802T050724Z_8bb75904_73f39c68_04cb1b1f`
- Failure checkpoint: `fa4e0237c3d30035a7db5efe7437965e76eec0ce`
- Raw ACK-stage summary SHA256: `f78a8f8e7234ce3aa6292f72340e47086e8c822c196978017df6af930d277c89`
- F→R committed exactly 15,000,000 bytes with CRC32, SHA256, byte integrity, atomic-commit, descriptor, retry, duty, pulse-width, and shutdown checks clean.
- Measured goodput was 3,658,361.060 bit/s. Fixed PL elapsed time was 32.801574641 s.
- Sender payload preparation consumed 142,502,078 PS ticks, or 0.427506222 s at 333,333,343 Hz.
- Receiver integrity verification consumed 1,306,486,402 PS ticks, or 3.919459092 s.
- The 60,729 DATA frames used 2,060 ACKs: 29.4801 DATA frames per ACK. Inter-object control consumed only 0.015468 s.
- Exact rolling-duty maxima were 11,504 high cycles per active sender module; the 18% target threshold is 11,520 cycles. No duty or continuous-high fault occurred.

## First-principles reconciliation

The application gate includes payload preparation and receiver verification. Removing only those directly measured serial CPU intervals gives:

```text
transport interval
= 32.801574640625
  - 142502078 / 333333343
  - 1306486402 / 333333343
= 28.454609326687 s

reconciled transport rate
= 120000000 / 28.454609326687
= 4217242.929688 bit/s
```

The measured run exceeded 30 seconds by 2.801575 s, while receiver verification alone consumed 3.919459 s.

## Root cause

The active receiver clean path rereads every object seven times: input/output CRC32, input/output SHA256, byte comparison, incremental output CRC32, and incremental output SHA256. The input stream CRC32/SHA256 had already been computed during slot preparation. The frozen CRC32 implementation was also correct but bit-at-a-time.

The direct evidence therefore identifies `SERIAL_REDUNDANT_CPU_INTEGRITY_VERIFICATION` as the actionable cause. ACK aggregation, inter-object optical control, duty throttling, corruption, retries, and resource leakage are not supported as the cause of this failure.

## Bounded remediation

The optimized clean path will retain direct byte equality with first-mismatch reporting, one incremental input CRC32/SHA256, one incremental output CRC32/SHA256, and atomic commit after all comparisons. Byte comparison and output CRC32 will share one memory pass; output SHA256 remains an independent pass. Per-object CRC/SHA classification is retained on the error path. CRC32 will use a verified reflected nibble-table update.

No RTL protocol, safety path, duty schedule, `GLOBAL_PERMIT`, pinmap, or lane mapping change is justified by this diagnosis. New firmware artifacts and fresh direct hardware acceptance remain mandatory.

No hardware action was executed while producing this diagnosis.
