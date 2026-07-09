# P3 Bitstream Build Audit Summary

generated_at_utc: 2026-07-09T10:17:26+00:00
repo: C:\Users\user\Documents\RF_COMM_MULTILANE
HEAD: 4768ef76c1d9bc6042d4058f52eef5fc0da5ca01
RESULT: PASS
REASON: non-hardware Vivado scripts audited; no hardware manager command found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

BITSTREAM_BUILD_AUDIT: PASS
BITSTREAM_GENERATION: BITSTREAM_GENERATED_NO_HW
HARDWARE_ACCEPTANCE: PENDING_HW

## Audited Scripts

- `scripts/vivado_nonhardware_build.tcl`
- `scripts/run_vivado_nonhardware_build.py`
- `scripts/vivado/create_project_offline.tcl`
- `scripts/vivado/validate_project_offline.tcl`

## Candidate Metadata

- bitstream path: `evidence/generated/vivado/ir_top_new_safe_idle.bit`
- bitstream SHA256: `7158965bd4cb7fd8530625f84bc69f849c40707760a5f810116053217db65905`
- generated from commit: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
- status: BITSTREAM_GENERATED_NO_HW only if metadata exists
- hardware status: PENDING_HW
