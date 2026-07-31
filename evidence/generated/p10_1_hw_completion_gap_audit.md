# P10.1 hardware completion gap audit

## Result

`P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE: FAIL`

The campaign cannot continue under the current Goal. Both permitted `preflight` run IDs were consumed, the second run failed before completing preflight, and section 23 limits each diagnostic stage to two new run IDs. No third hardware run was started.

The previous immutable current-run authorization was valid for the captured run, but is now consumed. `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`.

## Directly established facts

- Offline base recheck, model/airtime reconciliation, artifact provenance, target role binding, shutdown-before, and shutdown-after have direct PASS evidence.
- Attempt 2 completed target identity, a real one-byte F-to-R transfer with matching CRC/SHA, short ring wrap, and idle-heavy checks.
- Attempt 2 then failed because XSDB could not observe the rotating receiver's cacheable `PRIMED` publication.
- The cache-publication defect was corrected offline and both role-specific ELFs were rebuilt and frozen.
- The corrected ELFs have not been run on hardware, so they carry no hardware PASS.
- Baseline, tuning, sustained pipeline, 64 MiB streaming, fault recovery, half-duplex goodput, 4x4 crosstalk, 1+1, and the 1800-second formal run were not executed.
- Zero counters from the incomplete preflight are not evidence for the formal zero-error gates.

The machine-readable gate-by-gate audit is `evidence/generated/p10_1_hw_completion_gap_audit.json`.

## Retry boundary

| Item | Value |
|---|---:|
| Goal section | 23 |
| Permitted new `preflight` run IDs | 2 |
| Used | 2 |
| Remaining | 0 |
| Explicit retry-limit override | absent |
| Third preflight authorized | false |

Run IDs:

1. `p10_1_hw_20260731T211516Z_fd40629d_20ba7ef6_a1e3fbf5`
2. `p10_1_hw_20260731T214947Z_ddf4a064_1585d1ad_9ad4f85f`

## Fail-closed continuation guard

Checkpoint `4294b33b2bc99f16798535f6af72de4bf716c108` adds a cross-run budget gate to the hardware orchestrator. It reconstructs stage attempts from immutable `evidence/hardware/p10_1/<run_id>/stages/<stage>/` content and refuses both authorization generation and hardware execution when the budget is exhausted.

An override, if explicitly granted by the user, must be bound to one unique new run ID, the exact requested stages, Goal SHA256, both fixed JTAG identities, runtime/lane limits, prohibited operations, and the complete shutdown policy. It is non-reusable. The runner has no command that creates this override.

Offline verification:

- 33 focused unit tests: PASS
- canonical project consistency: PASS
- requirement traceability check: PASS
- actual historical preflight budget probe: PASS (2/2 detected, missing override refused)
- hardware actions for this audit: false

## Required continuation authorization

To continue the Goal, the user must explicitly authorize exactly one additional `preflight` new run ID and explicitly override the section 23 two-run limit for that run. A suitable unambiguous instruction is:

> 我明确覆盖 P10.1 Hardware Goal 第23节中 preflight 每阶段最多2个新 run_id 的限制，仅授权1个额外 preflight 新 run_id；并重新授权该唯一新 run_id 在原 Goal、原板卡绑定、原1800秒上限和原 shutdown 策略内执行完整 P10.1 硬件 campaign。

Until that statement is received and bound into a machine-readable one-run authorization, the correct state is fail closed: no JTAG connection, no programming, no ELF execution, and no TFDU drive.
