# DDR specialist test results

Status: `READY_FOR_MAIN_INTEGRATION_DIAGNOSTIC_STAGE62_STREAK_PASS`

`HARDWARE_ACCEPTANCE: PENDING_HW`

## Campaign D authorization and immutable-input gate

- three exact single-run authorizations: PASS;
- campaign envelope SHA256:
  `fdefc66d0c1c381c5e0502e227865d27ced3a0ac7a77f93e7717df06030df564`;
- fixed-input lock SHA256:
  `05fb5661e756c94694ed7d9ba7942bdeeb670969d53c5f37e636714ee1c79a43`;
- fixed artifacts rehashed before each run and after the campaign: 33/33;
- fixed-artifact hash changes: 0;
- authorization hash changes: 0;
- existing validator combinations passed before execution: 3/3;
- authorization validator modified: false.

The current-harness-only confirmation binds B_RX1 to J11 pin 33 / FPGA G15,
revision `UNVERSIONED`. The legacy D19 / J11 pin 26 mapping was not used.

## Campaign D hardware results

| Run | PS elapsed | Result | Summary SHA256 | Raw manifest SHA256 | Shutdown |
| --- | ---: | --- | --- | --- | --- |
| D-01 | 507.990 s | PASS | `5dd354d263d69cfbd33dfb9e9ef2fa67c0b78dac2945ef5822b88a58c7064f2e` | `d6a823d900c41b697ecfef491b51dfcc692c221bb78ebc42cbfe59395501cee2` | PASS |
| D-02 | 517.110 s | PASS | `7cf2cc3e275695101d2840c9649d0c57f9ed5573072fbd31293301ad857e602d` | `4d95d8f8b89ae7e0145d018aad2b61aadf993c23536e36f3a69ba43bf3d63e55` | PASS |
| D-03 | 502.600 s | PASS | `9377d387a49865ce63fc575892f12d78004297d2251005d35369a93bb81e81db` | `cc71fa80c3a4d5f24d4ef22bc58aaeded850f3f7e4b892463d5e1e70984a447d` | PASS |

Every run records:

- `P7_PS_APPLICATION_SAFE_STAGE=PASS`;
- Stage 62 attempted, executed, and completed;
- 48/48 boundary cases PASS;
- one 4 KiB checkpoint PASS;
- four 64 KiB cases PASS;
- four 1 MiB cases PASS;
- zero postprocess failures and payload mismatches;
- zero stationary objects and samples;
- PS return code 0 and no timeout;
- shutdown-before and shutdown-after return code 0;
- canonical shutdown image programmed after execution;
- `HARDWARE_ACCEPTANCE=PENDING_HW`, diagnostic-only, no acceptance coverage.

Campaign totals: 144 boundary cases, three 4 KiB checkpoints, twelve 64 KiB
cases, twelve 1 MiB cases, 1,275 rehashed raw evidence records, zero partial
files, and zero hash mismatches.

## Durable evidence audit

Command:

```text
python -B -m unittest tests.test_ddr_campaign_d_evidence
```

Result: `PASS`, 4 tests, 0 failures, 0 errors.

The audit reopens all three committed summaries and raw manifests, checks the
bounded Stage 62 scope, rehashes all 1,275 committed raw records, and verifies
the three shutdown results.

## Prior required complete suites

Before the Campaign D authorization checkpoint, the source-bound complete
suite driver recorded:

- top-level discovery: 181/181 PASS, invocation count 1;
- `tests/p7` discovery: 42/42 PASS, invocation count 1;
- total: 223 tests;
- canonical clean-source offline gate: PASS, 13/13 checks;
- offline cache status: BYPASS;
- no hardware actions during that offline checkpoint.

The post-campaign change is evidence and handoff packaging only; no execution
input, validator, firmware, or RTL was changed after authorization.

## Final safety state

- active project runner: false;
- active XSDB transaction: false;
- active Vivado transaction: false;
- hardware execution lock: free;
- established `hw_server` client connections: 0;
- resident listening-only `hw_server`: allowed;
- latest shutdown-after: PASS;
- safe shutdown complete: true.

No fourth Campaign D run, stages 1-61, full stages 1-66, stationary, Ethernet,
or motion run was performed. Formal hardware acceptance remains pending.
