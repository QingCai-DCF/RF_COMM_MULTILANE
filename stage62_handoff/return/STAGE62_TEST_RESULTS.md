# Stage62 specialist test results

## Offline checkpoint

- Clean source commit: `16d621d4b2fe5720e33a56adb1b19ad262feac25`
- Complete regression summary SHA256:
  `d717601080dd37fa197a9b038835df364e73d1c036789f57f27fc496ef51a431`
- Top-level discovery: 138 tests, one invocation, PASS.
- `tests/p7` discovery: 42 tests, one invocation, PASS.
- Total: 180 tests, PASS.
- Source remained unchanged and clean across both suites.

## Canonical offline gate

- `P7_OFFLINE_GATE=PASS`
- 13/13 required checks PASS.
- `OFFLINE_CACHE_STATUS=BYPASS`
- `OFFLINE_REAL_BUILD_PROCESS_RAN=true`
- `hardware_actions_executed=false`
- `HARDWARE_ACCEPTANCE=PENDING_HW`
- Summary SHA256:
  `f7906bff7b1c1a62472f80a84b9febadc0589479c653a1e8a29a57c80dc25bda`

## Hardware and dry-validation results

| Iteration | Run | Result | Diagnostic use | Acceptance use |
|---|---|---|---|---|
| iter_01 | R33 | PLAN_GENERATION_BLOCKED_NO_HARDWARE | none | none |
| excluded | R34 | ABORTED_MANUAL_PAUSE | invalid | invalid |
| iter_02 | R35 | FAIL_WRAPPER_POSTPROCESS | invalid | invalid |
| iter_03 | R36 Case A | PASS_DIAGNOSTIC_ONLY / COPY_OK | OCM-to-OCM only | none |
| iter_04 | R37 Case B setup | FAIL_DDR_PRESTART_READBACK | lower-level DDR boundary | none |

R36 and R37 exact dry validations passed before their launches. Each used a
new run ID, scoped authorization, immutable artifact hashes, length 30,
alignment 0/0, no Ethernet, no motion, lane mask at most `0x3`, and the official
shutdown-before/after wrapper. R37 failure was followed by independent
recovery-only shutdown PASS.

No original Stage62 run, Case C/D, functional stage, formal full sequence, or
stationary run was executed by these microtests. No hardware acceptance PASS is
claimed.
