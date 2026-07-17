# Historical Project Status Before V3.1 / P8A

> Historical snapshot only. It predates the canonical P7 r74 PASS evidence and must not override `config/project_state.json` or the generated root `PROJECT_STATUS.md`.

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
P7_OFFLINE_GATE: PASS
P7_OFFLINE_CACHE_STATUS: BYPASS
P7_LATEST_FORMAL_RUN: p7_20260715_stationary_app_r41_formal_full
P7_LATEST_FORMAL_RUN_STATUS: IMMUTABLE_FAIL_NEVER_RESUME_RESTART_COPY_OR_REUSE
P7_LATEST_FORMAL_SOURCE: 946ccbad66d64d715ad6745449b95f6c261ddf76
P7_LATEST_FORMAL_PLAN_SHA256: a37d652de98239b8e654a9467b21bdcb660c3d896ad40e1415de7c8e1ed5f794
P7_LATEST_FORMAL_LEDGER_SHA256: a86ec2a8e326a5354e9e79abed71ca938a3aa7a54b6936bc961beaf668ddba64
R41_FORMAL_STAGE_PREFIX_OBSERVED_PASS: 1_THROUGH_65
R41_FORMAL_FAILED_ORDINAL: 66
R41_FORMAL_STAGE66_RESULT: FAIL_STAGE
R41_ACCEPTANCE_COVERAGE_CLAIMED: false
R41_STATIONARY_AUTHORIZED_ATTEMPTS: 1
R41_STATIONARY_ATTEMPT_CONSUMED: true
R41_STATIONARY_SAMPLE_COUNT: 1
R41_STATIONARY_TERMINAL_OBJECT_COUNT: 4
R41_STATIONARY_COMPLETED_1800_SECONDS: false
R41_STATIONARY_RERUN_PERMITTED_UNDER_CURRENT_CONSTRAINT: false
R41_STAGE66_SHUTDOWN_BEFORE: PASS
R41_STAGE66_SHUTDOWN_AFTER: PASS
R41_INDEPENDENT_SHUTDOWN_RECOVERY: PASS_SEPARATE_FROM_FAILED_STAGE
R41_HOST_TCL_ROOT_CAUSE: CONFIRMED_SIGNED_32_BIT_LATENCY_SORT_OVERFLOW
R41_HOST_TCL_FIX: IMPLEMENTED_AND_OFFLINE_VALIDATED_NO_HARDWARE_RERUN
P7_CURRENT_HEAD_OFFLINE_GATE: NOT_RUN_POSTFAILURE_HOST_FIX_IS_NOT_HARDWARE_ACCEPTANCE_SOURCE
P7_BOUND_EXECUTION_SOURCE_OFFLINE_GATE: PASS_13_OF_13
P7_LATEST_CLEAN_SOURCE_REGRESSION_SOURCE: 946ccbad66d64d715ad6745449b95f6c261ddf76
P7_LATEST_CLEAN_SOURCE_REGRESSION: PASS_210_PLUS_42
P7_LATEST_CANONICAL_GATE_SOURCE: 946ccbad66d64d715ad6745449b95f6c261ddf76
P7_LATEST_CANONICAL_GATE: PASS_13_OF_13
P7_NEW_HARDWARE_RUN_READY: false
P7_LATEST_DIAGNOSTIC_RUN: p7_20260715_stationary_app_r40_diag_suffix55
P7_LATEST_DIAGNOSTIC_RUN_STATUS: COMPLETED_DIAGNOSTIC_PASS_NEVER_REUSE_OR_RESUME
P7_LATEST_DIAGNOSTIC_SOURCE: 37182768047dc4afdc18699a1142852418b382b5
P7_LATEST_DIAGNOSTIC_PLAN_SHA256: 27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e
P7_LATEST_DIAGNOSTIC_LEDGER_SHA256: 756c83030a6224b0381b7a90f0bf9085e3fe59eebe09957a9b68008ae9ca77a5
R40_DIAGNOSTIC_TERMINAL_PASS_ORDINALS: 1_2_3_4_55_THROUGH_65
R40_DIAGNOSTIC_FAILED_ORDINAL: NONE
R40_ACCEPTANCE_COVERAGE_CLAIMED: false
R40_STAGE66_ATTEMPT_COUNT: 0
R40_STATIONARY_STARTED: false
R40_SAFE_SHUTDOWN_COMPLETE: true
R39_DIAGNOSTIC_TERMINAL_PASS_ORDINALS: 1_2_3_4_55_THROUGH_63
R39_DIAGNOSTIC_FAILED_ORDINAL: 64
R39_DIAGNOSTIC_STAGE65: NOT_RUN
R39_ACCEPTANCE_COVERAGE_CLAIMED: false
R39_STAGE62_TERMINAL_RESULT: PASS_DIAGNOSTIC_ZERO_COVERAGE
R39_STAGE64_TERMINAL_RESULT: FAIL_STAGE
R39_INDEPENDENT_SHUTDOWN_RECOVERY: PASS_SEPARATE_FROM_STAGE_RESULT
R39_SOURCE_REPAIR: IMPLEMENTED_AND_CLEAN_CHECKPOINT_PASS
P7_NEXT_FORMAL_RUN_ID: NONE_UNDER_CURRENT_SINGLE_STATIONARY_ATTEMPT_CONSTRAINT
P7_NEXT_FORMAL_RUN_STATUS: NOT_AUTHORIZED
P7_NEXT_FORMAL_PLAN_CREATED: false
P7_NEXT_FORMAL_AUTHORIZATION_CREATED: false
P7_NEXT_FORMAL_HARDWARE_LAUNCHED: false
STAGE62_DIAGNOSTIC_FUNCTIONAL_STREAK: PASS_3_OF_3
STAGE62_SPECIALIST_INTEGRATION: READY
MAIN_THREAD_RESUME_READY: false
MAIN_THREAD_TERMINAL_STATE: FROZEN_R41_FORMAL_FAIL
CAMPAIGN_D_DIAGNOSTIC_ONLY: true
CAMPAIGN_D_ACCEPTANCE_COVERAGE: 0
SAFE_SHUTDOWN_COMPLETE: true
PS_PL_PHY_PL_PS_APPLICATION_PASS: false
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
The diagnostic ID `p7_20260715_stationary_app_r40_diag_suffix55` was launched
exactly once from clean source
`37182768047dc4afdc18699a1142852418b382b5`, using plan SHA256
`27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e`
and without `--resume`. The exact terminal ledger SHA256 is
`756c83030a6224b0381b7a90f0bf9085e3fe59eebe09957a9b68008ae9ca77a5`.
All 15 planned ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`
reached terminal diagnostic PASS, every child return code was zero, and every
stage recorded both shutdown-before and shutdown-after PASS with closed
containment and no remaining descendants. No independent recovery was needed
or run. The external `hw_server` PID 45220 remained untouched, no Ethernet or
motion was used, and the maximum lane mask remained `0x3`.

r40 is a completed diagnostic-only run and must never be reused or resumed. It
contributes zero formal acceptance coverage, remains
`HARDWARE_ACCEPTANCE=PENDING_HW`, contains no stage 66, and did not start the
1800-second stationary stage. The monitor observed tool-cell exit code zero but
its separate `Start-Process` exit-code field was blank; no executor process exit
code is invented. The executor's exact stdout records `DIAGNOSTIC_PASS`, all
ledger child return codes are zero, and the exact stderr is empty.

The immutable original r40 evidence remains in the validation worktree as an
836-file, 797,132,623-byte tree with zero partial files and canonical SHA256
`2702bb0019ddb5899a82c6aa8d6eea775612168a8e0d4d962f0c5fee0db270a2`.
The portable 129-file package under
`evidence/generated/p7_r40_diagnostic_pass_package` is 60,394,279 bytes with
zero partial files and canonical SHA256
`c66d889d6d6e46a22a83b897284b689c064500a218962b1ab3e1d34a9c0e2570`.
It losslessly archives all 15 exact stage summaries and raw result logs,
directly preserves all shutdown/preflight/raw-manifest records, and freezes 69
authorization, checkpoint, source, tool, configuration, and immutable artifact
inputs. The machine classification SHA256 is
`28aa31bcc122e65e3269dc6030f815a542190fee252434fc8bd8d08585371d9e`.

The formal-acceptance summarizer was invoked offline once against only this
diagnostic suffix. It exited one and failed closed, as required for a run that
lacks the full formal prefix and stationary stage; its shutdown summary is
PASS and its stationary summary is `PENDING_HW`. This aggregate FAIL is not a
diagnostic stage failure and does not override the exact r40 ledger. The
72-file replay tree SHA256 is
`d8d69008655da29dbdfd74a178cd8ee65724ac68a8678ec60f1f8785b649f5c8`;
the focused r40 package/history/tamper/summarizer tests pass 9/9. Their
machine record SHA256 is
`eebed533fb20df4f214f2e198dbc277512c340702ced1bbf9fb09c875418dcf8`.

The first fresh checkout after the r40 evidence freeze exposed twelve already
manifested `.log`, bitstream, LTX, XSA, and ELF objects that were present and
hash-exact in the original package but ignored and absent from the Git tree.
The focused package test at source `680f0c7e...` therefore failed 6/9; those
exact bytes were force-tracked without repackaging in `1daa8920...`. The first
required-suite attempt at that new source was interrupted by an accidentally
short outer tool timeout before any complete result existed. That source was
retired and was not rerun. At source `9cbea83c...`, the once-only complete
suites naturally finished with 209/210 plus 42/42 because nine ignored
generated AX7010 board-contract prerequisites had not yet been materialized;
the canonical gate was not run and that source was also retired. All three
precondition events are preserved and claim no hardware result.

Fresh cache-bypassed Vivado and Vitis builds then ran from source
`b6a934de...` and were frozen into main commit
`946ccbad66d64d715ad6745449b95f6c261ddf76`. The P6 PS bitstream SHA256 is
`532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0`,
XSA is `e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1`,
P7 ELF is `3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644`,
and linker map is
`0ec32b6d5828ab9f1061a6a1157962a4c74f1e0a3f25c679560e7fa0730a096b`.
The build and integrated commit trees are identical. Materialization proof
SHA256 `0dc8fd72ae71087954c8c52f691c3fb2ab8d9352b0e7529861b40d7d15ca7338`
binds the nine ignored prerequisites and tool identities without claiming a
canonical cache hit.

On exact clean source `946ccbad...`, the required complete-suite driver ran
once and passed 210/210 plus 42/42, each suite invoked exactly once. Summary
SHA256 is `83f878f3f374cf59504b4b9d87d7d2b512c0ea7e45316ef7ce480347662ee3d8`.
The canonical gate consumed that exact summary without duplicate suite
invocation and passed 13/13; gate SHA256 is
`85358dd1d4069f4953b2c205bcbb87680b7a45bdda3203f22f0e835a28cd946a`
and PS-core readiness passed 40/40 with SHA256
`a55f0e7d4c62c82403c117cbddf2c5686d86e47bade0b8ca4193ecb5178524d6`.
The exact 12-file checkpoint package is
`evidence/generated/p7_r41validate_946ccba_checkpoint`, canonical tree SHA256
`944366420fba2f8fffc63ca59c8ab0bad827c30e828e3b7808ae5464f181a8fe`;
its machine classification is
`evidence/generated/p7_r41validate_946ccba_checkpoint.json`. No hardware action
occurred and `HARDWARE_ACCEPTANCE=PENDING_HW`.

The collision-free formal run ID
`p7_20260715_stationary_app_r41_formal_full` is now dry-prepared at exact source
`946ccbad66d64d715ad6745449b95f6c261ddf76` in the isolated execution
worktree. The 25 post-gate generated outputs and nine ignored board-contract
prerequisites were materialized hash-exactly before generation; source
materialization record SHA256 is
`9737e5dcfc4fecc0fca57afde88de5ca122474d440a42d20e0196aefcee4ee33`.
No non-generated tracked source is dirty.

The generated formal plan contains every ordinal 1--66 exactly once. Plan
SHA256 is `a37d652de98239b8e654a9467b21bdcb660c3d896ad40e1415de7c8e1ed5f794`.
It has 66 unique scoped authorizations with canonical tree SHA256
`0d6406a772e5705fde96e9fd61f377c36f4c4c8422f0d7a170766be45f15bb60`,
no `--resume`, and exactly one stationary stage at ordinal 66. That stage binds
1800 seconds as 300 seconds calibration plus 1500 seconds acceptance and may be
admitted only after the same run's stages 1--65 pass.

The generator passed all 66 child-wrapper dry validations with zero errors;
manifest SHA256 is
`ea77c8d55ba6e52130c95beeffa0004b508aa40022d3f7c002a1629668119aa6`.
The independent plan audit passed with SHA256
`030ffa7973c0e8771dbda2c873e2017513481f7a286e93f1a3052980fb408010`,
and the separately invoked executor dry validation passed all 66 argv vectors
with SHA256
`70a984533384eb82eb146203620aeb9e583a92525d3e1d052de98e920da7bc28`.
The final preparation status is
`evidence/generated/p7_r41_formal_preparation_status.json`; selfcheck SHA256 is
`6bbfd30cdff1d0ab911d4c9bd62d5ea1d678f158035a6886c0ae8f868d0dd4e3`.

At the dry-preparation checkpoint described above, r41 had not yet launched,
its evidence root and ledger did not yet exist, and the stationary attempt was
unstarted. That paragraph is a historical preparation record and is superseded
by the terminal r41 result below. Campaign D, r39, and r40 authorization must
not be reused.

The final P7 stationary test was admitted once in r41 after the same run's stages
1--65 reached exact terminal PASS. Stage 66 then failed after one sample and four
terminal objects with `integer value too large to represent`; the required 1800
seconds did not complete. The run and stage remain FAIL, contribute no acceptance
coverage, and must never be resumed, restarted, copied, or reused. The single
authorized stationary attempt is consumed, so no further Stage 66 run is permitted
under the current constraint.

The confirmed failure mechanism is host-side XSCT Tcl `lsort -integer` applying a
signed 32-bit conversion to observed latency tick values between 17,875,676,347
and 51,321,168,692. Production Tcl now uses an explicit wide-integer comparator.
XSCT reproduces the historical error and validates the replacement, and 70 focused
package/history/tamper/wrapper/summarizer tests pass. These are offline-only results;
no hardware or stationary rerun occurred, and `HARDWARE_ACCEPTANCE` remains
`PENDING_HW`. Stage 66 shutdown-before/after and the independent shutdown recovery
all passed, but recovery does not change the failed stage result.

Exact machine records are `evidence/generated/p7_r41_formal_failure.json`,
`evidence/generated/p7_r41_postfailure_validation.json`, and
`evidence/generated/p7_r41_summarizer_replay_result.json`. The portable failure
package tree SHA256 is
`bf710e4207146ceb27476ab86b91d9e31bc61ef63716bc48ce41ea96f1095cb7`;
the original 834,613,170-byte raw tree remains inventoried as SHA256
`3501544a5fcd13458cbeb280e3e0a617430e8d8671ef8be5d90f5b6e7ebefa91`.
No Ethernet or motion was used, the maximum lane mask was `0x3`, and external
`hw_server` PID 45220 was not touched. Product-final acceptance remains pending.
