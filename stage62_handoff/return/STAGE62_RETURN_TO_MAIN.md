# Stage62 specialist return to main

## Status and commits

- STATUS: `BLOCKED_NEEDS_MAIN_DECISION`
- reason: `LOWER_LEVEL_DDR_OR_EXTERNAL_MASTER_BOUNDARY`
- base run ID: `p7_20260713_stationary_app_r32_diag_suffix55`
- base commit: `f002e80aeb575b2b3aea8ce34909dd65584140d9`
- specialist branch: `diag/stage62-p7_20260713_stationary_app_r32_diag_suffix55-f002e80`
- diagnostic commit: `6f379e37fe2f3bc330436b634fa40276fff0c146`
- structural-fix commit: `NONE`
- root-fix commit: `NONE`
- final technical/evidence commit: `054f31fe022fffff517bfa8982e5145681966ce6`
- final commit: `SELF_HANDOFF_COMMIT` (resolved to the exact hash in the
  specialist terminal machine-readable output)
- handoff packaging commit: the commit containing this file; use the
  `final_commit` value in the specialist's terminal machine-readable output.
- binary-preserving patch: `stage62_handoff/return/STAGE62_PATCH.diff`
- patch SHA256:
  `f5ee5078d519d2bf83e09023a113f625fb35e2287e42458f7369937fee7da096`
- patch size: `8699880` bytes
- evidence manifest: `stage62_handoff/return/STAGE62_EVIDENCE_MANIFEST.json`

## First proven failure boundary

R36 validly passed only the aligned 30-byte Case A control, fixed OCM source to
OCM scratch. R37 then attempted Case B under a new run ID. Before CPU release,
the canonical harness wrote and independently read back the immutable 256-byte
DDR destination fixture at `0x00900000`. Exactly one byte differed:

- offset: `9`
- absolute address: `0x00900009`
- expected: `0xC3`
- observed: `0x00`
- intended firmware copy target: `0x00900040`

The OCM source fixture and OCM control readbacks were exact. The failure is
therefore earlier than the firmware microtest copy and earlier than original
Stage62. R37 did not publish a firmware record and did not execute Stage62.

## Root cause and workaround

The precise lower-level root cause is not confirmed. The evidence identifies an
external-master DDR prestart write/readback failure. Remaining mechanisms
include the DAP/XSDB access path, PS interconnect, DDR controller,
initialization/training, or board-level DDR. Those areas are outside the Stage62
specialist authorization. No workaround was introduced, and no expected data,
CRC, SHA, memcmp, guard, wipe, or acceptance condition was weakened.

## Excluded or narrowed hypotheses

- A universal failure of the isolated byte-copy helper is inconsistent with
  the exact R36 OCM-to-OCM `COPY_OK` record.
- The exact ELF implements the isolated helper with byte loads/stores and a DSB;
  it has no microtest `memcpy`/`memmove` call.
- The TFDU/P6/PHY/lane path was bypassed by both microtests. The wrapper records
  `drove_tfdu_txd=false` and `enabled_tfdu_receiver=false`.
- R37 neither proves nor disproves the Stage62 application copy, because the
  independent DDR prestart gate stopped before CPU release.
- The precise DDR/interconnect/training/board mechanism remains unresolved.

## Iterations and runs

- R33 / iter_01: dry generation blocked; no hardware launch; ID retired.
- R34: `ABORTED_MANUAL_PAUSE`, `INVALID_FOR_DIAGNOSIS`,
  `INVALID_FOR_ACCEPTANCE`, `stage62_executed=false`; excluded entirely.
- R35 / iter_02: immutable `FAIL_WRAPPER_POSTPROCESS`; diagnostic invalid;
  independent shutdown recovery passed; never resume or reuse.
- R36 / iter_03: immutable `PASS_DIAGNOSTIC_ONLY` for Case A OCM-to-OCM;
  zero acceptance coverage; shutdown-before/after passed.
- R37 / iter_04: immutable `FAIL_DDR_PRESTART_READBACK` for Case B setup;
  exact one-byte DDR prestart mismatch; shutdown-after and independent recovery
  passed; never resume or reuse.

Specialist hardware launches: 3 (R35, R36, R37). R34 is an excluded external
full-sequence attempt and is not counted as specialist diagnostic evidence.

## Modified areas

The specialist commits add or update only Stage62 diagnostics, the isolated
Stage62 microtest harness and parser, directly related tests/build gates,
runtime-optimization constraints already authorized by the user, and evidence/
handoff artifacts. No RTL, DDR initialization/training, bitstream, formal
acceptance condition, legacy checkout, or main checkout was modified.

## Tests and exact artifacts

- Complete suites at clean source `16d621d4...`: 138 top-level tests plus 42
  `tests/p7` tests, each suite invoked exactly once, all PASS.
- Canonical offline gate: 13/13 PASS, cache bypassed, real build ran, no
  hardware actions, `HARDWARE_ACCEPTANCE=PENDING_HW`.
- ELF SHA256:
  `9f13ce1e340897fc159f40ac45a66099a70717411a587f922a424f217f0b0570`
- linker map SHA256:
  `1c384c9520879150e255769f623fbd5e92ffb9db27be09d75ead698d7d1f07e1`
- bitstream SHA256:
  `34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249`
- XSA SHA256:
  `b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9`
- shutdown bitstream SHA256:
  `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`

## Consecutive passes and unfinished validation

Original Stage62 consecutive passing run IDs: `NONE` (0). Case A's single
diagnostic PASS is not Stage62 or acceptance coverage. Cases C/D, the original
Stage62 vector, lengths 29/31/32, any required alignment expansion, the three
new-ID Stage62 passes, functional stages, full 1-66 formal run, and stationary
remain unexecuted or pending. No full-project PASS is claimed.

## Suggested cherry-pick order

Review and cherry-pick the ordered specialist range after the base commit:

`git cherry-pick f002e80aeb575b2b3aea8ce34909dd65584140d9..054f31fe022fffff517bfa8982e5145681966ce6`

Then separately cherry-pick the handoff packaging commit identified by the
terminal `final_commit`. Do not cherry-pick only the last evidence commit; the
diagnostic/harness commits are ordered dependencies.

## Main-thread next action

Open a separately authorized lower-level DDR/external-master investigation.
Start from the exact `0x00900000` fixture and `0x00900009` mismatch, preserve
new run IDs and shutdown barriers, and distinguish XSDB/DAP transaction
semantics from PS interconnect, DDR initialization/training/controller, and
board DDR. Only after that boundary is understood and repaired should a new
specialist run repeat Case B, then conditionally C/D and original Stage62.

## Do not do

- Do not resume or reuse R34, R35, R36, or R37.
- Do not use R34/R35 or skipped stages as diagnosis or acceptance coverage.
- Do not run Case C/D or another Stage62 specialist hardware run from this
  blocked worktree.
- Do not promote R36 to a DDR, Stage62, or acceptance PASS.
- Do not run stationary or claim full-project acceptance.
- Do not auto-merge this branch or modify the frozen main checkout.

Safe shutdown is complete. No active project runner, XSDB transaction, Vivado
transaction, or runner lock remained at handoff capture. The existing external
hw_server was not modified.
