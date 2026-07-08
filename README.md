# RF_COMM_MULTILANE

No-hardware rebuild workspace for the TFDU6102 RF_COMM project.

Imported legacy source: `C:\Users\user\Documents\RF_COMM`

Canonical inputs:
- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- P1 active profile mirror: `constraints/ACTIVE_PROFILE.json`
- P1 active pinmap mirror: `constraints/pinmap_active.csv`
- Register map: `config/register_map/ir_axi_regs.yaml`
- Bootstrap gates: `python scripts/run_offline_gates.py`
- P1 offline hardening gates: `python tools/run_offline_gate.py --allow-skips --json-summary`
- P2 simulation gate: `python tools/run_simulation_gate.py --allow-skips --json-summary`
- P1+P2 combined gate: `python tools/run_offline_gate.py --allow-skips --json-summary --include-simulation`

Hardware is not run by default. Hardware-related items remain
`HARDWARE_ACCEPTANCE: PENDING_HW` until the user explicitly authorizes a safe
wrapper run and shutdown evidence is captured.

Offline PASS does not mean TFDU6102 hardware, lane0, lane1, two-lane, Ethernet,
rotation, soak, or product-final acceptance has passed. Evidence lives under
`evidence/generated/`; future hardware placeholders live under
`evidence/hardware/`.

P2 adds an offline TFDU6102 lane PHY simulation baseline. If no HDL simulator
is installed, the HDL testbenches are reported as `SKIP_WITH_REASON` and the
Python reference model remains required.
