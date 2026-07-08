# Source Migration Map

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

| Source path | New path | Status | Reason | Class |
| --- | --- | --- | --- | --- |
| `C:/Users/user/Documents/RF_COMM` | `legacy/RF_COMM` | imported_reference | read-only legacy reference | reference |
| `rtl/legacy_reference` | `rtl/legacy_reference` | imported_reference | not canonical build input | reference |
| `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv` | `constraints/pinmap_active.csv` | derived | active P1 pinmap mirror | active |
| `constraints/active/PORT1.generated.xdc` | `constraints/active/PORT1.generated.xdc` | active | generated from canonical pinmap | active |
