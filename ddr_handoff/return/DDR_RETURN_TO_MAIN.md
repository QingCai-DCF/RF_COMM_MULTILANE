# DDR specialist return to main

## Status

- status: `READY_FOR_MAIN_INTEGRATION_DIAGNOSTIC_STAGE62_STREAK_PASS`;
- branch: `diag/ddr-external-master-r37-53571e`;
- Stage 62 packaging baseline:
  `53571e305846f89bf3da8c146f5a07bdb003f606`;
- corrected AX7010 artifact commit:
  `a7bc060aa29f15815891af463b1f7ff1d600cb31`;
- Stage 62 evidence-harvest fix commit:
  `6e8043716a6797257bbc46c172c287abed93198d`;
- Campaign D evidence commit:
  `1e6b5185cb1f0bdc2de0f148e715e1c726cb8b5e`;
- hardware acceptance: `PENDING_HW`;
- formal acceptance claimed: `false`;
- diagnostic evidence valid: `true`.

## Campaign D result

The user-created, existing-validator-approved Campaign D authorizations were
reverified with the campaign envelope and all 33 immutable inputs. Fresh live
safety checks found no active project runner, XSDB transaction, Vivado
transaction, execution lock, or established client connection to the resident
listening-only `hw_server`.

The three authorized original functional Stage 62 runs then completed in
strict sequence:

| Run | Stage 62 | Boundary | 4 KiB | 64 KiB | 1 MiB | Shutdown-after |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `p7_20260714_ddr_external_campaign_d_01` | PASS | 48/48 | 1/1 | 4/4 | 4/4 | PASS |
| `p7_20260714_ddr_external_campaign_d_02` | PASS | 48/48 | 1/1 | 4/4 | 4/4 | PASS |
| `p7_20260714_ddr_external_campaign_d_03` | PASS | 48/48 | 1/1 | 4/4 | 4/4 | PASS |

Across the campaign, 1,275 raw evidence records were independently rehashed
with zero mismatches and zero partial files. Each run used the immutable
shutdown image
`bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`
before and after execution. All three shutdown-after return codes are zero and
all three results contain `TFDU_SHUTDOWN_PROGRAMMED` plus
`P7_SHUTDOWN_RESULT=PASS`.

No fourth authorization or run was created. Stages 1-61, full stages 1-66,
stationary, Ethernet, and motion were not run and receive zero coverage.

## Technical conclusion

Campaign C2 had already shown that the corrected AX7010 PS7/DDR artifacts
support exact external-master self-loops, additional patterns, and isolated
microtests. C2-08 then isolated the remaining failure to slow byte-valued host
evidence reads after firmware completion, not to a proven DDR transport data
failure.

Commit `6e8043716a6797257bbc46c172c287abed93198d` preserved the full Stage 62
matrix and changed only the bounded host evidence path: phase-local preloads,
an immutable 4 KiB double-word readback probe, aligned double-word evidence
harvest, service shutdown before final 1 MiB evidence reads, and conservative
partial-attempt reporting. Campaign D confirms this minimal fix on hardware
for three consecutive original Stage 62 runs.

The authorization validator, firmware, RTL, expected payloads, CRC, SHA,
memcmp, trace, descriptor, guard, wipe, and runtime bounds were not weakened.

## Evidence

- closure:
  `ddr_debug/campaign_d/CAMPAIGN_D_CLOSURE.json`;
- closure SHA256:
  `704408f18f355684d002bcfa7c198ab45626657c15a724c75823f7fcc6d68cf3`;
- evidence audit test:
  `tests/test_ddr_campaign_d_evidence.py`;
- audit result: 4/4 PASS;
- run summaries:
  - D-01: `5dd354d263d69cfbd33dfb9e9ef2fa67c0b78dac2945ef5822b88a58c7064f2e`;
  - D-02: `7cf2cc3e275695101d2840c9649d0c57f9ed5573072fbd31293301ad857e602d`;
  - D-03: `9377d387a49865ce63fc575892f12d78004297d2251005d35369a93bb81e81db`;
- raw manifests:
  - D-01: `d6a823d900c41b697ecfef491b51dfcc692c221bb78ebc42cbfe59395501cee2`;
  - D-02: `4d95d8f8b89ae7e0145d018aad2b61aadf993c23536e36f3a69ba43bf3d63e55`;
  - D-03: `cc71fa80c3a4d5f24d4ef22bc58aaeded850f3f7e4b892463d5e1e70984a447d`.

## Prior offline checkpoint

- focused changed-path suite: 91 PASS;
- complete top-level discovery: 181 PASS, one invocation;
- complete `tests/p7` discovery: 42 PASS, one invocation;
- canonical clean-source P7 gate: PASS;
- offline gate SHA256:
  `2b71e7305312b718800dbf9a3b989dcf5edf382452392173b96c8a93fd8d20e2`.

## Main-thread integration boundary

Review and integrate the specialist range after
`53571e305846f89bf3da8c146f5a07bdb003f606`, including the minimal fix commit
and Campaign D evidence commit above. Do not run Campaign D again and do not
reuse any Campaign D authorization.

This handoff does not claim full-project, stages 1-61, formal stages 1-66,
stationary, Ethernet, motion/rotation, soak, or product-final PASS. Those
remain outside the authorized diagnostic scope, so `HARDWARE_ACCEPTANCE` stays
`PENDING_HW`.
