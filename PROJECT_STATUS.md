# Project Status

Project: RF_COMM_MULTILANE
Current branch: codex/p7-stationary-application
P6 baseline commit: ca041d4877b831de84fe7829788ac835b0b46acd
P7 offline checkpoint source commit: `4bc49b1684be5eac655d75314f0da95e0bc1ffa8` (see `evidence/generated/p7_offline_gate_summary.json`)

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
P7_OFFLINE_GATE: PASS
P7_OFFLINE_CACHE_STATUS: BYPASS
P7_LATEST_FORMAL_RUN: p7_20260715_stationary_app_r34_formal_full
P7_LATEST_FORMAL_RUN_STATUS: IMMUTABLE_FAIL_NEVER_RESUME
R34_FORMAL_STAGE_PREFIX_OBSERVED_PASS: 1_THROUGH_61
R34_ACCEPTANCE_COVERAGE_CLAIMED: false
R34_STAGE62_ATTEMPTED: false
R34_STAGE62_EXECUTED: false
R34_STATIONARY_ATTEMPTS: 0
STAGE62_AUTHORIZATION_CONTRACT_REPAIR: IMPLEMENTED_OFFLINE_PENDING_CLEAN_CHECKPOINT
P7_CURRENT_HEAD_OFFLINE_GATE: NOT_RUN_AFTER_STATIC_REPAIR
P7_LATEST_CLEAN_SOURCE_REGRESSION_SOURCE: 7c6b50ff3450562b95c59029ec225f6d365541f9
P7_LATEST_CLEAN_SOURCE_REGRESSION: PASS_191_PLUS_42
P7_LATEST_CANONICAL_GATE_SOURCE: 7c6b50ff3450562b95c59029ec225f6d365541f9
P7_LATEST_CANONICAL_GATE: FAIL_PRECONDITION_PS_CORE_STATIC_SCOPE_LITERAL
P7_NEW_HARDWARE_RUN_READY: false
STAGE62_DIAGNOSTIC_FUNCTIONAL_STREAK: PASS_3_OF_3
STAGE62_SPECIALIST_INTEGRATION: READY
CAMPAIGN_D_DIAGNOSTIC_ONLY: true
CAMPAIGN_D_ACCEPTANCE_COVERAGE: 0
SAFE_SHUTDOWN_COMPLETE: true
PS_PL_PHY_PL_PS_APPLICATION_PASS: false
STATIONARY_30MIN: PENDING_HW
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

P7 implementation/pre-hardware status is PENDING_HW. P7 hardware acceptance may
advance only through the real PS input-memory -> P7 PS ELF/application service ->
AXI/PL -> physical TFDU -> PL/AXI -> PS output-memory path. Direct JTAG/AXI is an
auxiliary ingress and cross-check path; current host ingress is JTAG/AXI plus the
PS mailbox. The disabled TCP adapter has not been tested over a real Ethernet
cable and contributes no P7 PASS evidence.

Campaign D supplies three consecutive diagnostic-only Stage 62 functional
passes and safe shutdown evidence. It contributes zero formal acceptance
coverage and does not cover stages 1--61, a complete stages 1--66 run, or the
1800-second stationary stage. The specialist package is integrated and the
fresh clean-source offline checkpoint passes, but hardware acceptance remains
`PENDING_HW`.

The later full-plan r34 run is immutable `FAIL` and must never be resumed. Its
outer ledger records exact PASS observations for stages 1--61, followed by a
stage 62 authorization-contract failure before the candidate bitstream or PS
ELF started. Both stage-local shutdown barriers and the separate recovery
passed, but neither changes stage 62 or r34 to PASS. Stage 66 was not attempted.
The confirmed defect is that the generated PS authorization omitted both
`P7_EXECUTION_SCOPE=P7_PS_APPLICATION_STAGE` and `P7_RUN_ID=NONE`, while the
execution Tcl required them; the generator and offline wrapper validator have
an offline-only repair pending a new clean-source checkpoint. The first clean
validation attempt at source `229299db9c6c5098d30ae5922508f4426546e665`
accurately failed: top-level discovery was 190 tests with two failures and two
errors, while `tests/p7` passed 42/42, with each suite invoked exactly once.
Seven byte-exact r34 package logs had been ignored rather than tracked, and the
fresh worktree had not yet materialized the generated AX7010 Vivado/Vitis board
contract inputs. This checkpoint is preserved as non-hardware FAIL evidence and
must not be rerun at the same source. A new hardware run is not ready.

At the next clean source `7c6b50ff3450562b95c59029ec225f6d365541f9`,
fresh cache-bypass P6 Vivado and P7 Vitis builds passed, the complete generated
board contract passed with zero errors, and the once-only complete suites
passed 191/191 plus 42/42. The canonical gate then accurately failed 12/13:
only `P7_PS_CORE_HARDWARE_READINESS` was false. The independent core check
required the explicit Stage62-only authorization tuple literal, while the
normal-PS repair had generalized both scopes into a conditional tuple. Runtime
semantics and every complete test passed, but the static gate failed closed.
The wrapper now keeps explicit tuples for both scopes and tests both branches;
this offline repair requires a new clean-source checkpoint. No hardware run is
ready.

The final P7 stationary test is a single 1800-second run containing 300 seconds
of embedded calibration and 1500 seconds of acceptance. It is not an additional
two-hour soak. Available scope is two physical lanes, no Ethernet, and no hardware
motion. Striping alternates single-lane fragments, while replication uses mask
0x3; they are different semantics. Software-injected lane unavailability proves
only scheduler fallback and is not a real optical-path fault. Product-final
acceptance remains pending Ethernet, rotation, and target lane-count validation.
