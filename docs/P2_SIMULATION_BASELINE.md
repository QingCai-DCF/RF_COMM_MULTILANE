# P2 Simulation Baseline

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Goal

Move the project from P1 offline hardening into a repeatable TFDU6102 lane PHY
and pulse-level simulation baseline.

## Non-Goals

P2 does not validate real TFDU6102 hardware, lane0, lane1, two-lane routing,
Ethernet, rotation, soak, product readiness, supply quality, optical distance,
or mechanical alignment.

## File List

- `sim/models/tfdu6102_behavior_model.sv`
- `sim/models/tfdu6102_behavior_model.v`
- `sim/models/tfdu6102_reference.py`
- `rtl/tfdu/tfdu_lane_phy.sv`
- `sim/tests/test_tfdu6102_reference.py`
- `sim/scripts/run_reference_tests.py`
- `tools/sim/detect_simulator.py`
- `tools/run_simulation_gate.py`
- `tools/run_simulation_gate.ps1`
- `docs/TFDU_LANE_PHY_SPEC.md`
- `docs/SIMULATION_GATE.md`

## Testbench Matrix

See `sim/tb/README.md` and `evidence/simulation/test_matrix.md`.

## Run

```powershell
python tools/run_simulation_gate.py --json-summary --allow-skips
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_simulation_gate.ps1 -JsonSummary -AllowSkips
python tools/run_offline_gate.py --allow-skips --json-summary --include-simulation
powershell -NoProfile -ExecutionPolicy Bypass -File tools/run_offline_gate.ps1 -AllowSkips -JsonSummary -IncludeSimulation
```

## Result Meanings

- `PASS`: Python reference tests and all HDL testbenches passed with an HDL
  simulator.
- `PASS_WITH_SKIPS`: Python reference tests passed, no-hardware scan passed,
  and unavailable HDL simulation is recorded as `SKIP_WITH_REASON`.
- `FAIL`: P1 recheck, Python reference tests, no-hardware scan, evidence
  generation, or available HDL testbenches failed.
- `SKIP_WITH_REASON`: a specific tool-backed item did not run and says why.

## Why P2 Is Not Hardware Acceptance

P2 uses local digital models. It cannot verify IRED current, VCC2 droop,
decoupling placement, optical alignment, board wiring, TFDU tolerance, or
runtime board behavior. Hardware acceptance remains `PENDING_HW`.
