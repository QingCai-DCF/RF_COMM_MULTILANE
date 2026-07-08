# RF_COMM_MULTILANE

No-hardware bootstrap of a TFDU6102 RF_COMM rebuild workspace.

Imported legacy source: `C:\Users\user\Documents\RF_COMM`

Canonical entry points:
- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map: `config/register_map/ir_axi_regs.yaml`
- Offline gates: `python scripts/run_offline_gates.py`
- Hardware prep wrappers: `scripts/hw/`

Hardware is not run by default. Hardware-related items remain `PENDING_HW`
until the user explicitly authorizes a safe wrapper run and shutdown evidence is
captured.

Current offline gate status is `PASS_WITH_PENDING_TOOL`: static and Python
checks pass, while SystemVerilog simulation and Vivado execution are recorded as
`PENDING_TOOL` on this workstation.
