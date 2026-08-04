# P10.3 repository regression classification

## Result

The P10.3-focused offline regression is **PASS**: 109 tests ran with zero failures and zero errors. This is an offline classification result only. It does not promote P10.3 hardware acceptance, which remains **FAIL / IN_PROGRESS_BLOCKED**.

No RTL, firmware, hardware runner, configuration, frozen artifact, or immutable hardware evidence was changed. Commit `75b120763ad18402b9d3e4f727bb586807298422` changes four test files only, aligning old two-lane assertions with the existing P10.3 four-lane implementation:

- duplicate-past-sequence remains protocol-only, while lane-unavailable state remains the bounded physical injection input;
- reset recovery verifies the role-specific expected profile instead of hard-coding P10.1 profile IDs;
- disabled legacy firmware is excluded from active-runtime checks;
- serializer/duty checks use `LANE_COUNT` and `eligibility_lane`;
- formal checks bind repeated bounded 64-MiB commands and `p10_max_lane_mask`.

`python scripts/check_no_hardware_calls.py` returned `NO_HARDWARE_ACTIONS_EXECUTED=1`. The pre-existing `hw_server` process (PID 36668, started 2026-07-28) was not started, stopped, or connected by this offline checkpoint. Current-run hardware authorization is false and consumed.

## Full repository suite

The exact post-remediation discovery run executed 528 tests and remained fail-closed with 10 failures and 16 errors. None is a residual P10.3 live-source assertion:

- 8 failures and 16 errors require absent historical P6/P7 local evidence, generated Vivado/Vitis artifacts, or historical fixture/closure context. Those inputs were not fabricated or regenerated.
- 1 failure reports 101 mismatches in an immutable P10.1 run manifest. Old evidence was not rewritten.
- 1 failure is the old P10.1 identity-only runtime audit. P10.2/P10.3 runtime generalization is intentionally outside that historical audit, so the audit remains fail-closed.

The machine-readable file lists every residual test ID and its disposition.

## P10.3 Definition of Done

Completed evidence includes eight unique module identities, wiring hash binding, immutable artifacts, preflight PASS, and verified shutdown on both endpoints. Module intake failed on the R2-to-F2 direction, so the 8x8 matrix and every later performance, protocol, streaming, and 30-minute stage were not run.

The latest direct evidence shows:

- the rotating endpoint was correctly selected as sender;
- R2's internal final physical-TX path counted 64 events;
- F2's synchronized raw-Rxd path counted 5 events;
- software direction control and P10.3 lane indexing passed audit.

This does not isolate a component. The remaining physical fault domain includes R2 TX/power/interconnect, both J11 lane2 external paths, the optical path/alignment, and F2 RX/power/interconnect.

## Required continuation boundary

No further hardware run is authorized. The Goal bounds JTAG connect to 3, programming to 2, and diagnostic run IDs per stage to 2; five P10.3 run IDs and three module-intake executions already exist. A safe continuation requires:

1. powered-off physical inspection/isolation of the R2-to-F2 external path; and
2. an explicit P10.3 retry-limit override plus a new immutable current-run authorization.

Historical P10.1 retry overrides and consumed P10.3 authorizations do not authorize a new P10.3 run.
