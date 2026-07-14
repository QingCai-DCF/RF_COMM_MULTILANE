# R36 Stage62 microtest summary

`p7_20260714_stage62_microtest_r36_diag_only` is an immutable,
zero-coverage diagnostic-only PASS for Case A only: a 30-byte aligned
OCM-to-OCM copy.

- The official wrapper returned 0 and published `P7_PS_APPLICATION_SAFE_STAGE=PASS`.
- The independent classification is `COPY_OK`; the dedicated record has
  `error_code=0`, `first_bad_domain=0`, and `first_bad_index=UINT32_MAX`.
- The immutable source before/after hashes match, and final OCM destination
  readback matches the copied bytes.
- Output wipe was independently verified.
- Shutdown-before and shutdown-after both returned 0 and passed.
- Functional stages 1-61, Stage62, and stationary were not executed.
- This result gives no DDR or acceptance coverage. `HARDWARE_ACCEPTANCE` stays
  `PENDING_HW`.

Authoritative machine-readable result:
`p7_ps_application_stage_summary.json` SHA256
`9c674685445c6d3655e110231622a81fcbf4c3a70ddfd43c44a50b75b536c315`.
