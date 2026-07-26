# P9 P8E Immutable Baseline Recheck

- Status: `PASS`
- Test ID: `P9-00-P8E-IMMUTABLE-BASELINE-RECHECK`
- P8E checkpoint: `57ff1079b10a5c0de156b621820774bbb111c5ee`
- Artifact manifest: `1765` files, `535658195` bytes
- Hardware actions executed: `false`

The first exact verification retained its `781` missing and `161` hash-mismatch result. The user-authorized read-only worktree contained all `1765` manifest artifacts with zero missing files and zero hash mismatches. Those bytes were copied only into the P9 worktree and every target hash was checked after copying. The repeated exact `P8E_VERIFY_EXISTING` gate passed with an empty error list.

The read-only source remained on `p8/integration` at `57ff1079b10a5c0de156b621820774bbb111c5ee`; its Git status was unchanged (`?? docs/audit/`) before and after validation. The adjacent JSON and referenced raw logs are authoritative.
