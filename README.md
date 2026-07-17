# RF_COMM_MULTILANE

Rebuild workspace for the TFDU6102 RF_COMM project.

Canonical inputs:

- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map: `config/register_map/ir_axi_regs.yaml`
- Requirements: `config/project_requirements.yaml`
- Machine state: `config/project_state.json`
- Generated status: `PROJECT_STATUS.md`
- Requirement traceability: `docs/REQUIREMENT_TRACEABILITY_MATRIX.md`
- Offline gate: `python scripts/run_offline_gates.py`
- P6 no-Ethernet gate: `python tools/run_p6_gate.py --json-summary`
- P7 final clean source-binding gate: `python tools/run_p7_gate.py --json-summary --allow-skips --skip-ps-build`
- P7 authorized sequence dry-run: `python tools/run_p7_authorized_hardware_sequence.py --sequence-plan <plan> --sequence-plan-sha256 <sha256> --json-summary`
- P7 hardware evidence consistency: `python tools/summarize_p7_hardware.py --json-summary`

P6 local transport tooling:

- Full simulation: `python scripts/run_p6_dynamic_transport_sim.py`
- Host JTAG/AXI file transport: `python tools/run_p6_host_file_transport_matrix.py`
- PS mailbox runtime: `python tools/run_p6_ps_runtime_safe.py`
- Shutdown-bounded hardware sequence dry-run: `python tools/run_p6_authorized_hardware_sequence.py --json-summary`
- Full authorized sequence requires explicit hardware flags and includes the real 7200-second soak.

Canonical status is generated from `config/project_state.json`; see
[`PROJECT_STATUS.md`](PROJECT_STATUS.md) instead of duplicating status fields here.

The preserved current hardware result is the stationary, local, two-lane P7
application PASS on the Z7010 development platform. This remains a
platform-limited result. Z7020, sector-bank, rotating, Ethernet, 8-lane, and
final-product acceptance remain pending. P8A is an offline canonicalization
checkpoint and performed no hardware action.
