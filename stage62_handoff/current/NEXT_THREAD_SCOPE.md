# Stage 62 specialist-thread scope

## Required isolation

- Base commit: `f002e80aeb575b2b3aea8ce34909dd65584140d9`.
- Use an independent Git worktree and an independent branch.
- Treat r31 and r32 as immutable FAIL runs; never resume, copy, or relabel either run.
- Read evidence in place or copy only the explicitly needed evidence into the specialist worktree. Do not mutate this frozen handoff.
- Do not merge automatically into the frozen main branch.

## Allowed work

- Stage 62-specific diagnosis.
- Stage 62-specific microtests.
- Necessary offline tests focused on the Stage 62 hypothesis under investigation.
- Necessary builds and exact ELF map/stack/disassembly verification.
- Parser, runner, and diagnostic-record changes directly required to observe Stage 62.
- Evidence-based comparison of `INPUT_REF -> ENCODE_RAW -> ENCODE_REPAIR -> P6_TX_LOCAL -> P6_TX_MMIO_READBACK -> P6_RX_LOCAL -> RECEIVED -> DDR_OUTPUT_IMMEDIATE_READBACK -> DDR_OUTPUT_END_TO_END -> INTEGRITY_SNAPSHOT`.
- Machine-readable first-error publication that is atomic, first-only, input-bound, and captured before output wipe.

## Default prohibitions

- Do not modify any other stage's PASS condition.
- Do not modify expected payload, expected CRC, or expected SHA values.
- Do not delete, bypass, weaken, or redefine memcmp, CRC, SHA, guard, or immutable-input checks.
- Do not remove or delay failure output wipe merely to aid interactive inspection.
- Do not change formal acceptance or stationary acceptance.
- Do not change RTL without evidence locating the first corruption at or below the RTL/MMIO boundary.
- Do not change DDR initialization without evidence.
- Do not execute a full stages 1–66 run.
- Do not execute Stage 66 or any 1800-second stationary run.
- Do not use Ethernet, move hardware, exceed lane mask `0x3`, touch the external legacy `hw_server`, or modify `C:\Users\user\Documents\RF_COMM`.

Any later hardware execution requires separate user authorization, a new run ID, mandatory safety prefix, immutable input hashes, dry/offline gates, shutdown-before/after, first-failure stop, raw evidence preservation, independent recovery, and zero acceptance coverage for a diagnostic run. This handoff does not grant that authorization.
