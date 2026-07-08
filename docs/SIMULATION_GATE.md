# Simulation Gate

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Simulator Detection

`tools/sim/detect_simulator.py` checks, in order:

1. `iverilog` plus `vvp`
2. `verilator`
3. `xvlog`, `xelab`, and `xsim`
4. `vivado -version` as compile-tool availability only
5. Python reference fallback

Missing HDL tools are reported as `SKIP_WITH_REASON`, never as `PASS`.

## Python Reference Tests

`python sim/scripts/run_reference_tests.py --json` runs dependency-free tests
for shutdown idle, static high-speed mode, startup wait, high-active TX,
low-active RX, stuck-high protection, 125 ns and 250 ns pulse mapping, mode-low
FIR drop, shutdown TX blocking, and startup-time RX drop.

## HDL Simulation Tests

When an executable HDL simulator is available, the gate compiles and runs the
P2 testbench matrix under `sim/tb/`. Without an HDL simulator, those entries are
explicit skips and the Python reference tests remain mandatory.

## Result Paths

- `evidence/generated/simulator_detection_summary.md`
- `evidence/generated/tfdu6102_reference_model_summary.md`
- `evidence/generated/tfdu6102_behavior_model_summary.md`
- `evidence/generated/tfdu_lane_phy_sim_summary.md`
- `evidence/generated/ir_4ppm_pulse_smoke_summary.md`
- `evidence/generated/simulation_gate_summary.md`
- `evidence/generated/p2_simulation_baseline_summary.md`
- `evidence/simulation/sim_results.json`
- `evidence/simulation/test_matrix.md`
- `evidence/simulation/logs/*.log`

## Common Failures

- Python reference assertion failure: fix the model contract or tests.
- HDL compile failure: fix the named testbench source list or RTL syntax.
- HDL runtime failure: inspect the matching log in `evidence/simulation/logs`.
- No HDL simulator: install a local simulator or accept `PASS_WITH_SKIPS`.
- No-hardware scan failure: remove unguarded hardware access from active code.

## Adding A Testbench

Add the `.sv` file under `sim/tb/`, list it in `sim/tb/README.md`, and add a
source-list entry in `tools/run_simulation_gate.py`.

## Hardware Access Prevention

The simulation gate defaults to no-hardware mode. It does not use Vivado
Hardware Manager, board programming, XSCT hardware targets, real serial
endpoints, TFDU pin driving, or bitstream loading. Documentation may mention
forbidden operations only as forbidden operations.
