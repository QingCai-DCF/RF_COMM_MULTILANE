# RF_COMM_MULTILANE

No-hardware rebuild workspace for the TFDU6102 RF_COMM project.

Imported legacy source: `C:\Users\user\Documents\RF_COMM`

Canonical inputs:
- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map: `config/register_map/ir_axi_regs.yaml`
- P1 offline hardening gates: `python tools/run_offline_gate.py --allow-skips --json-summary`
- P2 simulation gate: `python tools/run_simulation_gate.py --allow-skips --json-summary`
- P5 dry-run gate: `python tools/run_p5_gate.py --json-summary --skip-ethernet --skip-motion --lane-count 2`

Hardware is not run by default. Hardware-related items remain `HARDWARE_ACCEPTANCE: PENDING_HW` unless the user explicitly authorizes a safe wrapper run and shutdown evidence is captured.

Current stage summary:
- P0_BOOTSTRAP: PASS
- P1_OFFLINE_HARDENING: PASS
- P2_SIMULATION_BASELINE: PASS
- P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
- P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
- P5_2LANE_PROTOCOL_STABILIZATION: PASS_WITH_NOTES
- ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
- ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
- EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE

P5 evidence is stationary, 2-lane, JTAG/ILA/proxy based when hardware is explicitly authorized. It is not Ethernet, rotation, 8-lane, or product-final acceptance.
