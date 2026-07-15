# P7 Runtime Optimization Constraints

This policy reduces repeated P7 diagnostic and offline work without weakening
hardware safety or changing the immutable formal acceptance sequence.  It
applies to all subsequent P7 run IDs unless a stricter active authorization
overrides it.

## Non-negotiable boundary

- A failed hardware run is immutable, is never resumed, and is followed by an
  independent shutdown recovery before another hardware run.
- Every new hardware attempt uses a new run ID, a clean checkpoint, scoped
  authorization, immutable input hashes, complete dry validation, and the
  existing shutdown-before/after safe wrappers.
- Diagnostic runs always record `DIAGNOSTIC_ONLY`, `coverage_claimed=false`,
  and `HARDWARE_ACCEPTANCE=PENDING_HW`.  A skipped or historical stage never
  contributes formal acceptance coverage.
- Ordinary diagnostic runs never include the final stationary stage.  The only
  exception is the explicitly authorized, machine-counted Stage 66 diagnostic
  campaign in `config/p7_stage66_diagnostic_campaign_policy.json`.  A campaign
  run is exactly formal ordinals 1--4 followed by standalone ordinal 66, uses a
  collision-checked new run ID, remains `DIAGNOSTIC_ONLY` with zero coverage and
  `HARDWARE_ACCEPTANCE=PENDING_HW`, and may run the exact 1800-second stationary
  window.  The campaign stops at its first complete Stage 66 PASS or after ten
  actually launched hardware run IDs, whichever comes first.  This exception
  neither changes nor contributes coverage to the later formal 1--66 run.
- No optimization may add Ethernet, motion, a lane mask above `0x3`, modify the
  legacy RF_COMM project, or alter/replace the external existing `hw_server`.

## Adaptive diagnostic suffix selection

Do not blindly replay an already diagnosed suffix after every failure.  For a
new diagnostic run:

1. Execute the mandatory safety/regression prefix defined by the active safe
   diagnostic plan (currently formal ordinals 1--4).
2. After that prefix, start at the earliest unresolved stage, or at the earliest
   earlier stage whose transitive consumed inputs changed since its last exact
   diagnostic PASS.
3. A prior stage may be skipped only when machine-readable provenance proves
   that every input it consumes is unchanged: wrapper/Tcl source, bitstream,
   LTX/XSA/ELF as applicable, profile, transaction file, backend manifest,
   register map, XDC, pinmap, authorization-relevant settings, and tool/runtime
   identity required by that stage.
4. If impact cannot be proved, fail closed and include the uncertain/affected
   stage.  Source-commit ancestry or a human assertion alone is insufficient.
5. The new plan must record each skipped ordinal, the bound prior run/summary
   SHA256, the unchanged-input proof, the selected first unresolved ordinal,
   and the fact that skipped stages claim zero coverage.

Example: after a diagnostic run passes ordinals 55--61 and fails at 62, a
PS-wrapper-only fix may use a new diagnostic run containing ordinals 1--4 and
62--65 if exact input-impact evidence proves that the JTAG stages 55--61 consume
no changed input.  This does not replace the later formal 1--66 run.

## Content-addressed offline build caching

- Prefer a fail-closed content-addressed cache for expensive offline Vivado and
  Vitis build substeps when their complete transitive inputs are unchanged.
- A cache key must bind at least the tool executable hash/version, target part,
  build options, RTL, XDC, IP configuration, build Tcl, board profile, pinmap,
  register map, software/build inputs, and every other file consumed by the
  cached substep.
- A cache hit must re-hash and validate all declared outputs and reports.  A
  missing field, mismatch, unsupported tool identity, or ambiguous dependency
  is a cache miss and triggers the real build.
- Cache reuse is offline only.  Never reuse an authorization, execution ledger,
  shutdown result, raw hardware evidence, or hardware PASS across run IDs.
- The gate summary must record `OFFLINE_CACHE_STATUS=HIT|MISS|BYPASS`, the cache
  key, validated output hashes, and whether any real build process ran.
- Before authorizing the final formal full hardware run, execute and preserve at
  least one cache-bypassed canonical offline gate on the exact clean source.

## Regression invocation deduplication

- During development, run focused tests for changed code and its direct safety
  consumers.
- Before a commit/checkpoint used for hardware authorization, run each required
  complete suite exactly once.  Do not separately rerun a suite when the same
  tests are already included in a canonical discovery command.
- Keep separately discovered suites (for example `tests/p7`) separate when they
  are not included by the top-level discovery command.
- Any code or evidence-validator change after the complete run invalidates that
  result and requires the affected focused tests plus one new final complete
  run.
- Record exact commands, discovered test counts, return codes, and
  `FULL_SUITE_INVOCATION_COUNT`; deduplication means removing duplicate
  execution, never omitting required tests.

## Optimizations requiring separate explicit authorization

The following are not enabled by this policy: increasing JTAG frequency,
keeping a persistent Vivado hardware session across independent stages,
grouping cases across required shutdown barriers, weakening containment or
shutdown checks, changing the formal acceptance sequence, or substituting PS,
offline, simulation, proxy, or historical evidence for a required hardware
stage.

## Bounded Stage 66 diagnostic campaign exception

The active user authorization dated 2026-07-15 narrowly overrides the ordinary
diagnostic stationary prohibition and the earlier project-wide single-attempt
stationary limit.  It does not override any other safety or evidence rule.

- The immutable r41 formal run remains `FAIL` and can never be resumed,
  restarted, copied, or reused.  Its frozen ledger identity is bound by the
  campaign policy.
- At most ten diagnostic hardware run IDs may actually launch.  A preparation
  blocked before hardware does not consume the numerical allowance, but its run
  ID remains retired under the normal fail-closed collision rules.
- Each launched campaign run executes only the mandatory prefix ordinals 1--4
  and standalone ordinal 66.  It may execute ordinal 66 for exactly 1800
  seconds, but remains diagnostic-only and claims no acceptance coverage.
- The persistent campaign ledger is updated before the first child hardware
  wrapper can launch.  It enforces the next attempt number, unique run ID,
  maximum count, unresolved-recovery barrier, and stop-after-first-PASS rule.
- A failure, timeout, exception, or orphaned launch intent permanently retires
  that run ID and requires separately authorized independent shutdown recovery
  before another campaign plan can validate.
- After the first complete 1800-second diagnostic PASS, no additional campaign
  run may launch.  The final repair is then committed and a new clean source
  must pass the required complete suites exactly once, a cache-bypassed
  canonical offline gate, new scoped authorization, immutable hashes, and dry
  validation before a different formal run ID executes the full ordinals
  1--66.  Only that formal run contributes acceptance coverage, and its Stage
  66 may launch once.
