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
- Diagnostic runs never include the final stationary stage.  Only a later new
  formal run that executes the complete immutable acceptance sequence from its
  first stage may launch the single stationary stage.
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
