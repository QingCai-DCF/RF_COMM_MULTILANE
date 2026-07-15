# Project Status

Project: RF_COMM_MULTILANE
Current branch: codex/p7-stationary-application
P6 baseline commit: ca041d4877b831de84fe7829788ac835b0b46acd
P7 offline checkpoint source commit: `37182768047dc4afdc18699a1142852418b382b5` (see `evidence/generated/p7_r40validate_3718276_checkpoint.json`)

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
STAGE62_AUTHORIZATION_CONTRACT_REPAIR: IMPLEMENTED_AND_OFFLINE_VALIDATED
P7_CURRENT_HEAD_OFFLINE_GATE: NOT_RUN_PREPARATION_COMMIT_BINDS_VALIDATED_SOURCE_3718276
P7_BOUND_EXECUTION_SOURCE_OFFLINE_GATE: PASS_13_OF_13
P7_LATEST_CLEAN_SOURCE_REGRESSION_SOURCE: 37182768047dc4afdc18699a1142852418b382b5
P7_LATEST_CLEAN_SOURCE_REGRESSION: PASS_201_PLUS_42
P7_LATEST_CANONICAL_GATE_SOURCE: 37182768047dc4afdc18699a1142852418b382b5
P7_LATEST_CANONICAL_GATE: PASS_13_OF_13
P7_NEW_HARDWARE_RUN_READY: true
P7_LATEST_DIAGNOSTIC_RUN: p7_20260715_stationary_app_r39_diag_suffix55
P7_LATEST_DIAGNOSTIC_RUN_STATUS: IMMUTABLE_FAIL_NEVER_RESUME
P7_LATEST_DIAGNOSTIC_SOURCE: 1d0c30fa7988acc0ae345cfec1c1917a56f07592
P7_LATEST_DIAGNOSTIC_PLAN_SHA256: fb44c68f2a740d43a143eff024a80450b3e803cfe2be7282f362f85aaa1fbc0f
P7_LATEST_DIAGNOSTIC_LEDGER_SHA256: f77a32c84f39a11bcf3b2e63738b7d491c8d2e823b2068bd979072c6a991e4f5
R39_DIAGNOSTIC_TERMINAL_PASS_ORDINALS: 1_2_3_4_55_THROUGH_63
R39_DIAGNOSTIC_FAILED_ORDINAL: 64
R39_DIAGNOSTIC_STAGE65: NOT_RUN
R39_ACCEPTANCE_COVERAGE_CLAIMED: false
R39_STAGE62_TERMINAL_RESULT: PASS_DIAGNOSTIC_ZERO_COVERAGE
R39_STAGE64_TERMINAL_RESULT: FAIL_STAGE
R39_INDEPENDENT_SHUTDOWN_RECOVERY: PASS_SEPARATE_FROM_STAGE_RESULT
R39_SOURCE_REPAIR: IMPLEMENTED_AND_CLEAN_CHECKPOINT_PASS
P7_NEXT_DIAGNOSTIC_RUN: p7_20260715_stationary_app_r40_diag_suffix55
P7_NEXT_DIAGNOSTIC_RUN_STATUS: READY_NO_HARDWARE_LAUNCH
P7_NEXT_DIAGNOSTIC_SOURCE: 37182768047dc4afdc18699a1142852418b382b5
P7_NEXT_DIAGNOSTIC_PLAN_SHA256: 27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e
P7_NEXT_DIAGNOSTIC_PLAN_MODE: DIAGNOSTIC_SUFFIX_55
P7_NEXT_DIAGNOSTIC_STAGE66_PRESENT: false
P7_NEXT_DIAGNOSTIC_ACCEPTANCE_COVERAGE_CLAIMED: false
P7_NEXT_DIAGNOSTIC_HARDWARE_LAUNCHED: false
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
The confirmed defect was that the generated PS authorization omitted both
`P7_EXECUTION_SCOPE=P7_PS_APPLICATION_STAGE` and `P7_RUN_ID=NONE`, while the
execution Tcl required them; the generator and offline wrapper validator have
an offline-only repair that now passes a new clean-source checkpoint. The first clean
validation attempt at source `229299db9c6c5098d30ae5922508f4426546e665`
accurately failed: top-level discovery was 190 tests with two failures and two
errors, while `tests/p7` passed 42/42, with each suite invoked exactly once.
Seven byte-exact r34 package logs had been ignored rather than tracked, and the
fresh worktree had not yet materialized the generated AX7010 Vivado/Vitis board
contract inputs. This checkpoint is preserved as non-hardware FAIL evidence and
must not be rerun at the same source. That historical preparation block was
later superseded by the clean source checkpoint described below.

At the next clean source `7c6b50ff3450562b95c59029ec225f6d365541f9`,
fresh cache-bypass P6 Vivado and P7 Vitis builds passed, the complete generated
board contract passed with zero errors, and the once-only complete suites
passed 191/191 plus 42/42. The canonical gate then accurately failed 12/13:
only `P7_PS_CORE_HARDWARE_READINESS` was false. The independent core check
required the explicit Stage62-only authorization tuple literal, while the
normal-PS repair had generalized both scopes into a conditional tuple. Runtime
semantics and every complete test passed, but the static gate failed closed.
The wrapper now keeps explicit tuples for both scopes and tests both branches.
On clean source `1d0c30fa7988acc0ae345cfec1c1917a56f07592`, top-level
discovery passed 192/192 and `tests/p7` passed 42/42, each invoked exactly once.
The canonical gate reused the hash-bound suite summary with zero duplicate
complete-suite invocations and passed 13/13. Exact summary SHA256 values are
`5bb9560fae3b7439843ef8a788d1bde7621657f73d19880569476f9492d8e34a`
for the suites, `6a4c530c89668c98bf3d320e483928180816336bb109eab68752c93bd632bb98`
for the gate, and
`a5a796191553354b54fd8dc1785a76847b02bbc79a45b5bb3229107470a2d40b`
for PS core readiness. No hardware action occurred. The diagnostic-only plan
`p7_20260715_stationary_app_r39_diag_suffix55` was then generated at that exact
source. Its immutable plan SHA256 is
`fb44c68f2a740d43a143eff024a80450b3e803cfe2be7282f362f85aaa1fbc0f`;
the independent executor dry validation and all 15 authorization audits pass.
It contains only ordinals 1--4 and 55--65, claims zero coverage, remains
`PENDING_HW`, and contains no stage 66 or stationary launch.

r39 was launched once without `--resume` and is now immutable `FAIL`. Its
ledger SHA256 is
`f77a32c84f39a11bcf3b2e63738b7d491c8d2e823b2068bd979072c6a991e4f5`.
Ordinals 1--4 and 55--63 reached terminal diagnostic PASS with shutdown-after
PASS, but contribute zero acceptance coverage. Stage 64 ended `FAIL_STAGE`
because the duplicate-replay descriptor was correctly rejected while its
1 MiB nonzero output canary remained unwiped; stage 65 did not run. The raw PS
child returned zero and emitted its abort/restart PASS markers, but the outer
wrapper correctly rejected the result with `slot 2: failed/aborted output was
not atomically wiped`. Stage-summary SHA256 is
`8749cac8523752abc7b59c5b611258ff5abfcad3d15252a0576bb0057e381102`.
The confirmed historical source gap is limited to the validation-reject path:
after all descriptor-controlled ranges were structurally validated, an
identity-policy rejection published `REJECTED` without erasing the private
output range. This is not a payload or DDR-corruption finding.

The source repair now carries an explicit `private_output_validated` bit from
descriptor validation and wipes only a structurally trusted private output
after shutdown and before publishing the rejection. Structurally invalid
descriptors remain write-free. Focused stage-wrapper checks pass 41/41, the
r39 package/history/tamper checks pass 7/7, and the full focused summarizer
history/tamper module passes 16/16. The subsequent clean-checkpoint chain is
now fully preserved: source `5a99b98c...` passed 199+42 complete tests but
failed the canonical gate 12/13 on a stale first-wipe static search; source
`6999166b...` then failed one of 201 top-level tests because the r39 current
checker SHA binding was stale, while `tests/p7` passed 42/42. Neither source
was rerun. After the scoped checker and binding repairs, clean source
`37182768047dc4afdc18699a1142852418b382b5` passed 201/201 plus 42/42,
each suite invoked exactly once, and the canonical gate passed 13/13 with zero
duplicate complete-suite invocations. All of these are non-hardware results.

The first independent recovery invocation failed closed at authorization with
`NO_HARDWARE_ACTIONS_EXECUTED=1`. A second, separately authorized recovery then
recorded `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`, `SHUTDOWN_EXIT=0`, and PASS. It is
separate from the r39 stage result. Raw r39 evidence remains a 743-file,
796,712,508-byte immutable tree with SHA256
`d8e77dde31fa229c08b84fb779e7a805e18e53f20522f7256824f4e9f32bd69f`;
the portable failure package tree SHA256 is
`dbb1974da49b7be1efcc0c68f073a4ccf00fff024a9b3f7b44e92c0fc7056ef3`.
The new, unused diagnostic ID
`p7_20260715_stationary_app_r40_diag_suffix55` is prepared but not launched.
Its fail-closed impact decision starts at ordinal 55 because the source, XSA,
ELF, and PS bitstream changed from r39, so r39's PASS observations at 55--63
cannot support a skip to 64. The exact r40 plan SHA256 is
`27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e`.
It contains only ordinals 1--4 and 55--65, has zero stage 66/stationary entries,
claims zero acceptance coverage, and remains `PENDING_HW`. All 15 child dry
validations, the independent plan audit, and the separately invoked executor
dry validation pass with no hardware process launched. The final
build-materialization proof SHA256 is
`349f20dcf6d2bacae028fba49893f6d2f435268483350e2cade03084e920505b`;
the suite summary is `1f397f78c5325271015d19b623090fe56c432ed62329a7501e1b67beae4cbb85`,
the canonical gate is `cf6a6d6c839f1e0251279964f5b73b56967f5440e3687253fb78b149ea0886a5`,
and PS core readiness is `c3961b381bb7f9276064f7220908640b7969bdbd02dfb877ad5453095b616d5d`.
The 12-file portable checkpoint tree is `cf6fc3176e2801ae56e8cb40bd769bf9a7910219aacef17d42dec0c6a86a8955`.
If hardware execution is entered, use only this exact r40 plan from its bound
source workspace, never use `--resume`, stop on the first failure, preserve raw
evidence, and perform independent recovery before retiring the ID. No Campaign
D or r39 authorization may be reused.

The final P7 stationary test is a single 1800-second run containing 300 seconds
of embedded calibration and 1500 seconds of acceptance. It is not an additional
two-hour soak. Available scope is two physical lanes, no Ethernet, and no hardware
motion. Striping alternates single-lane fragments, while replication uses mask
0x3; they are different semantics. Software-injected lane unavailability proves
only scheduler fallback and is not a real optical-path fault. Product-final
acceptance remains pending Ethernet, rotation, and target lane-count validation.
