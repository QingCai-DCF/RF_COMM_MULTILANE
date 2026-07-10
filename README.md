# RF_COMM_MULTILANE

Rebuild workspace for the TFDU6102 RF_COMM project.

Canonical inputs:

- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map: `config/register_map/ir_axi_regs.yaml`
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

Current stage summary:

- P0_BOOTSTRAP: PASS
- P1_OFFLINE_HARDENING: PASS
- P2_SIMULATION_BASELINE: PASS
- P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
- P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
- P5_2LANE_PROTOCOL_STABILIZATION: PASS_WITH_NOTES
- P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET: PASS
- HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: PASS
- P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PENDING_HW
- HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PENDING_HW
- PS_PL_PHY_PL_PS_APPLICATION_PASS: false
- STATIONARY_30MIN: PENDING_HW
- ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
- ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
- EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
- PRODUCT_FINAL_ACCEPTANCE: PENDING
- PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

P6 is stationary, two-lane, local/JTAG/AXI/PS-driver scoped evidence. It is not Ethernet, rotation, 8-lane, or product-final acceptance.

P7 implementation is present, but P7 hardware acceptance remains pending until the
authorized real-PS path and the single 1800-second stationary run complete. The
required primary path is PS input memory -> real P7 PS ELF/application service ->
AXI/PL -> the physical two-lane TFDU link -> PL/AXI -> PS output memory. Direct
JTAG/AXI is auxiliary bring-up and cross-check evidence; it cannot set the real-PS
application PASS by itself. Current host ingress is JTAG/AXI plus the PS mailbox;
the disabled TCP adapter has not been validated with a real Ethernet cable.

The one allowed final P7 run is exactly 1800 seconds: 300 seconds of embedded
calibration followed by 1500 seconds of acceptance, with no separate calibration
or two-hour P7 soak. Application striping alternates single-lane fragments;
replication uses P6 mask `0x3` and is not striping. Software-injected lane
unavailability tests scheduler fallback only and are not evidence of a real
optical fault. P7 remains stationary, no-Ethernet, no-motion, two-lane scope, and
product-final acceptance remains pending.
