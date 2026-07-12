# P3 Hardware Script Dry Run Summary

generated_at_utc: 2026-07-12T00:18:10+00:00
repo: C:\Users\user\Documents\RF_COMM_MULTILANE
HEAD: 28e7bb8f5266d654aefdbd3fede7b7dae7ab584e
RESULT: PASS
REASON: hardware placeholder scripts default to dry-run and reject unauthorized execution
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

HARDWARE_SCRIPT_DRY_RUNS: PASS

| Script | Result | Detail |
| --- | --- | --- |
| `tools/hw_preflight.py` | PASS | dry-run rc=0 |
| `tools/hw_preflight.py` | PASS | unauthorized execute rc=2 |
| `tools/hw_raw_phy_smoke.py` | PASS | dry-run rc=0 |
| `tools/hw_raw_phy_smoke.py` | PASS | unauthorized execute rc=2 |
| `tools/hw_raw_lane_matrix.py` | PASS | dry-run rc=0 |
| `tools/hw_raw_lane_matrix.py` | PASS | unauthorized execute rc=2 |
| `tools/hw_shutdown.py` | PASS | dry-run rc=0 |
| `tools/hw_shutdown.py` | PASS | unauthorized execute rc=2 |
| `tools/hw_collect_evidence.py` | PASS | dry-run rc=0 |
| `tools/hw_collect_evidence.py` | PASS | unauthorized execute rc=2 |
