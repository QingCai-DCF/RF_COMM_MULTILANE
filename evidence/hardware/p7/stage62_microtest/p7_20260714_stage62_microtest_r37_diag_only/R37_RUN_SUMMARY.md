# R37 Stage62 microtest summary

`p7_20260714_stage62_microtest_r37_diag_only` is an immutable
`FAIL_DDR_PRESTART_READBACK` run. It must never be resumed or reused.

Case B planned a 30-byte aligned OCM-to-DDR copy. Before releasing the CPU,
the canonical XSDB harness wrote and independently read back the immutable
256-byte DDR destination fixture at `0x00900000`. Exactly one byte differed:
offset 9 (`0x00900009`) was expected to be `0xC3` but read as `0x00`.
The intended copy target begins at offset 64 (`0x00900040`), so the first
failure precedes the firmware copy. OCM source and control readbacks were exact.

Consequences:

- No dedicated firmware microtest record was published.
- No Case B application-copy PASS/FAIL conclusion is claimed.
- Functional stages 1-61, Stage62, and stationary were not executed.
- No acceptance coverage is claimed; `HARDWARE_ACCEPTANCE=PENDING_HW`.
- The precise lower-level mechanism remains unresolved. The evidence moves the
  next investigation to the external-master/PS-interconnect/DDR-init-or-training/
  board-DDR boundary, outside this specialist's authorization.

The wrapper's shutdown-after returned 0 and passed. A separate recovery-only
shutdown program also passed with `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1` and
`SHUTDOWN_EXIT=0`.
