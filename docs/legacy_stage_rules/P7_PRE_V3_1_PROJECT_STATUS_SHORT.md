# Historical Short Project Status Before V3.1 / P8A

> Historical snapshot only. The generated root `PROJECT_STATUS.md` now owns current status.

Project: RF_COMM_MULTILANE
Current branch: codex/p7-stationary-application
P6 baseline commit: ca041d4877b831de84fe7829788ac835b0b46acd
P7 offline checkpoint source commit: `946ccbad66d64d715ad6745449b95f6c261ddf76` (see `evidence/generated/p7_r41validate_946ccba_checkpoint.json`)

P0_BOOTSTRAP: PASS
P1_OFFLINE_HARDENING: PASS
P2_SIMULATION_BASELINE: PASS
P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
P5_2LANE_PROTOCOL_STABILIZATION: PASS_WITH_NOTES
P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET: PASS
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: PASS
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PENDING_HW
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PENDING_HW
PS_PL_PHY_PL_PS_APPLICATION_PASS: false
P7_LATEST_FORMAL_RUN: p7_20260715_stationary_app_r41_formal_full
P7_LATEST_FORMAL_RUN_STATUS: IMMUTABLE_FAIL_NEVER_RESUME_RESTART_COPY_OR_REUSE
R41_FORMAL_STAGE_PREFIX_OBSERVED_PASS: 1_THROUGH_65
R41_FORMAL_FAILED_ORDINAL: 66
R41_ACCEPTANCE_COVERAGE_CLAIMED: false
R41_STATIONARY_AUTHORIZED_ATTEMPTS: 1
R41_STATIONARY_ATTEMPT_CONSUMED: true
R41_STATIONARY_COMPLETED_1800_SECONDS: false
R41_STATIONARY_RERUN_PERMITTED_UNDER_CURRENT_CONSTRAINT: false
R41_INDEPENDENT_SHUTDOWN_RECOVERY: PASS_SEPARATE_FROM_FAILED_STAGE
STATIONARY_30MIN: FAIL_INCOMPLETE
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

USER_CONFIRMED_SUPPLY_OK: true
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3

P6 is stationary, two-lane, local/JTAG/AXI/PS-driver scoped evidence.
P6 is not Ethernet acceptance.
P6 is not rotation acceptance.
P6 is not 8-lane acceptance.
P6 is not product-final acceptance.

Current P6 result is PASS. Acceptance is derived from the dynamic payload physical RTL simulation, immutable JTAG/AXI and PS candidates, authorized stationary two-lane hardware matrices, host file round-trip, PS mailbox execution, fallback negatives, and the bounded 2-hour soak evidence. Existing P5 evidence remains P5-only context.

P7 implementation/hardware-acceptance status remains PENDING_HW. P7 hardware
acceptance may advance only through the real PS input-memory -> P7 PS ELF/application service ->
AXI/PL -> physical TFDU -> PL/AXI -> PS output-memory path. Direct JTAG/AXI is an
auxiliary ingress and cross-check path; current host ingress is JTAG/AXI plus the
PS mailbox. The disabled TCP adapter has not been tested over a real Ethernet
cable and contributes no P7 PASS evidence.

The single authorized P7 stationary attempt ran in r41 after same-run stages
1--65 reached terminal PASS, but Stage 66 failed after one sample and four
terminal objects; 1800 seconds did not complete. r41 is immutable FAIL, claims
no acceptance coverage, and may never be resumed, restarted, copied, or reused.
The attempt is consumed and no further Stage 66 run is permitted under the
current constraint. Shutdown-before/after and independent recovery passed but
do not change the failed stage. The confirmed host-side Tcl sort-overflow fix is
offline-validated only; no hardware rerun occurred and hardware acceptance
remains `PENDING_HW`.
