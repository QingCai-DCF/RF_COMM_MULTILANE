# P10.1 preflight semantic remediation

Status: **PASS** for the host-side semantic remediation only.

No hardware action was executed during this remediation, and no byte in the
immutable third-preflight run directory was changed. The historical
`stage_summary.json` remains `FAIL` with its original SHA256 so the audit trail
is preserved.

## Bound immutable evidence

- Run ID: `p10_1_hw_20260801T015919Z_bfff4836_1585d1ad_9ad4f85f`
- Historical stage summary SHA256:
  `8d3601c9a4baae4c8fd9b94aa16ee92dfa39abe9f042c79d7e28d3b4dea9b7f3`
- Orchestrator result SHA256:
  `3a73c0aa7be930d26f5fd96e0f42db6b9ec54b5a0681fda81b7581059ea354c0`
- Hardware observations: 11

## Corrected semantics

Timer accuracy is checked locally on each endpoint by comparing its PS timer
with its PL timer. Sender and receiver elapsed intervals enclose different
local work, so their cross-endpoint elapsed skew is retained as an
informational observation and is not a clock-accuracy gate. The immutable
preflight data has a maximum local PS/PL error of
`2.6528736911115144e-06%`; its maximum cross-endpoint skew is
`3.8111963110524907%`.

The intentional recovery case writes `ABORT_OBJECT`. The PL register named
`P10_1_INTEGRITY_ERROR_COUNT` is wired to the rising edge of transport
`object_fail`, so that case must observe exactly one edge per endpoint. The
captured fixed and rotating values are both `1`; the independent PS CRC, SHA,
and pattern-integrity checks remain zero. Normal cases still require the PL
counter to remain zero.

The finalizer also honors the immutable
`USER_OVERRIDE_NO_LIMIT_UNTIL_CAMPAIGN_TERMINAL` policy instead of reviving the
superseded Goal section-23 bounded retry disposition.

## Read-only result and validation

Re-evaluating the immutable stage with `write_summary=False` changes the
computed result from 12 semantic errors to `PASS` with no errors. This does not
rewrite or relabel the historical evidence and does not claim full-campaign
hardware acceptance.

- 26 focused unit tests: PASS
- Python compilation: PASS
- no-hardware-call check: PASS (`NO_HARDWARE_ACTIONS_EXECUTED=1`)
- `git diff --check`: PASS
- complete legacy bootstrap gate: not claimed; its existing Vivado-output
  verification reports unrelated pre-existing legacy output/plan-audit
  failures, and all generated changes from that diagnostic invocation were
  restored.

Machine-readable details are in
`evidence/generated/p10_1_hw_preflight_semantic_remediation.json`.
