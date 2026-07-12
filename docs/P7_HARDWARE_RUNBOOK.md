# P7 stationary local application hardware runbook

This runbook is limited to stationary, local, two-lane P7 application transport. It does not authorize Ethernet, DHCP/TCP board traffic, hardware movement/rotation, lane masks above `0x3`, an additional calibration run, or product-final acceptance.

The normal state is `NO_HARDWARE=1`. Hardware execution is permitted only with a user-owned P7 authorization file, the external `RF_COMM_HW_AUTH=P7_STATIONARY_APP_LAYER_APPROVED` environment value, immutable path+SHA256 inputs, a bounded runtime, and a safe wrapper that independently programs the TFDU shutdown image before and after the stage. The wrapper must remain responsible for shutdown after timeout, exception, Ctrl+C, abort-file detection, or a nonzero child exit.

## Non-negotiable acceptance boundary

A hardware stage is complete only when all of the following are preserved in its run directory:

- the safe-wrapper JSON summary and raw command/XSDB/JTAG log;
- a `hardware_execution_lock` record for the canonical `.hardware_authorization/P7_HARDWARE_EXECUTION.lock`, with `acquired=true`, `stale_lock_auto_recovery=false`, a valid token SHA256, and owner fields matching the wrapper, stage/mode, and exact run directory;
- every child process has return code exactly `0` and no timeout/interruption flag;
- every launched preflight, shutdown-before, candidate, and shutdown-after child records `process_tree_reaped=true`, a supported OS containment kind, `containment_assigned=true`, `containment_closed=true`, and `descendant_count_after=0`; the event log must prove `candidate_child_reaped` occurred before `shutdown_after_started`;
- shutdown-before and shutdown-after each have return code `0` plus an exactly parsed `TFDU_SHUTDOWN_PROGRAMMED=<nonempty>` or `SHUTDOWN_EXIT=0` marker and a fresh exact `P7_SHUTDOWN_RESULT=PASS` record; duplicate marker keys are rejected;
- the authorization, plan, candidate bitstream, XSA, ELF, profile, active XDC, pinmap, register map, shutdown image, and any LTX/transaction/bundle manifest still match their authorized SHA256 values;
- the fresh live cable/board, part, IDCODE, and exact target match the authorization record;
- `network_used=false`, `motion_used=false`, two lanes, and maximum lane mask `0x3` are recorded;
- the raw object ledger proves size, CRC32, SHA256, fragment coverage, lane counters, retry/error counters, safety counters, and atomic completion.
- the run-local `p7_raw_evidence_sha256_manifest.json` commits every raw PS evidence file, reports no partial files, and itself remains bound by the wrapper summary.

Dry-runs, simulations, offline backend manifests, historical P6 evidence, Markdown conclusions, and the JTAG parser alone cannot be promoted to P7 hardware PASS. A direct JTAG result is auxiliary; `PS_PL_PHY_PL_PS_APPLICATION_PASS` can be true only after the real P7 PS ELF/runtime path passes.

If shutdown-after is absent or fails, stop all subsequent transmitting stages. Preserve the failed run directory, do not overwrite or delete it, and restore shutdown through the approved bounded project shutdown path before any further candidate programming. Never convert a missing tool or missing evidence into PASS; record `SKIP_WITH_REASON` and leave final hardware acceptance pending.

## 1. Offline gates and immutable freeze

Run the mutable offline work below without the hardware authorization environment
variable, then commit the complete P7 source checkpoint and require a clean
worktree:

```powershell
python scripts/run_offline_gates.py
python scripts/build_p7_ps_runtime.py
python tools/run_p7_ps_core_offline.py
python -B -m unittest tests.test_summarize_p7_hardware -v
git status --porcelain=v1 --untracked-files=all
```

After that source commit, run the source-binding gate exactly once:

```powershell
python tools/run_p7_gate.py --json-summary --allow-skips --skip-ps-build
```

Do not amend its generated summaries into the source checkpoint, and do not run
the PS build, PS-core readiness tool, P7 gate, or another commit between this
freeze and sequence execution. The gate already regenerates and hashes the
PS-core readiness attestation; rerunning that timestamped tool would invalidate
the frozen checkpoint input hash.

Require the P6 recheck, P7 protocol vectors, segmentation/reassembly, backend conformance, real Vitis ELF build, no-Ethernet, no-motion, two-lane scope, TFDU6102 safety, source-bound PS-core readiness, and immutable-artifact gates to pass. Offline summaries must retain `HARDWARE_ACCEPTANCE: PENDING_HW`.

The final pre-hardware offline checkpoint must be regenerated after the final code commit, from a clean worktree. Its JSON must embed the exact 40-hex `source_commit`, `dirty_worktree=false`, the `source_tree_listing_sha256`, and an exact-count `checkpoint_input_hashes` map containing the critical C/Tcl/wrapper/containment/summarizer sources. The chronology ledger independently re-hashes every listed file, recomputes the Git tree-listing digest when the repository is available, and rejects a caller-supplied commit that is not already bound inside this immutable checkpoint; an older offline PASS cannot be relabeled with a newer hardware commit. The resulting `evidence/generated/` changes are deliberate post-gate dirt accepted by the sequence generator; any source, documentation, profile, configuration, or `evidence/hardware/` change remains a blocker.

Freeze every execution input under a content-addressed or SHA256-named path. Record hashes rather than relying on filenames:

```powershell
$Head = (git rev-parse HEAD).Trim().ToLowerInvariant()
$PlanSha = (Get-FileHash -Algorithm SHA256 -LiteralPath <frozen-p7-plan>).Hash.ToLowerInvariant()
$BitSha = (Get-FileHash -Algorithm SHA256 -LiteralPath <immutable-bit>).Hash.ToLowerInvariant()
$XsaSha = (Get-FileHash -Algorithm SHA256 -LiteralPath <immutable-xsa>).Hash.ToLowerInvariant()
$ElfSha = (Get-FileHash -Algorithm SHA256 -LiteralPath <immutable-p7-elf>).Hash.ToLowerInvariant()
$ProfileSha = (Get-FileHash -Algorithm SHA256 -LiteralPath <mode-profile>).Hash.ToLowerInvariant()
$ShutdownSha = (Get-FileHash -Algorithm SHA256 -LiteralPath shutdown_bitstream/tfdu_shutdown_j10_j11.bit).Hash.ToLowerInvariant()
```

The authorization file must bind the exact source commit, board/part/target, runtime, mode or JTAG stage name, all artifact paths and hashes, and the mode-specific PS or transaction/manifest extension fields. Because `P7_PS_MODE` and `P7_JTAG_STAGE_NAME` are exact authorization fields, use a distinct immutable authorization file for each PS mode and each direct-JTAG case. Do not edit an authorization file after hashing it.

## 2. Dry-run validation

Generate the complete immutable 66-stage sequence plan only after the final clean
gate. The generator binds the source commit, offline-checkpoint path and SHA256,
all canonical artifact/profile/configuration paths and hashes, exact live target,
per-stage authorization files, unique evidence directories, and the sole final
stationary launch. It does not set `RF_COMM_HW_AUTH` or launch a hardware tool.
Use `python tools/generate_p7_authorized_sequence_plan.py --help` for the complete
required argument list.

Then validate that exact plan without `--execute-hardware` and without the
external authorization environment:

```powershell
$SequencePlan = '<generated-sequence-plan>'
$SequencePlanSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SequencePlan).Hash.ToLowerInvariant()
python tools/run_p7_authorized_hardware_sequence.py `
  --sequence-plan $SequencePlan `
  --sequence-plan-sha256 $SequencePlanSha `
  --json-summary
```

Require `P7_AUTHORIZED_HARDWARE_SEQUENCE: DRY_RUN_VALIDATED`. A bare executor
invocation that reports `DRY_RUN_ONLY` has not validated the sequence plan. Any
dry-run is never hardware evidence.

The common child-wrapper argument block below documents fields emitted by the
generator. It is an explanatory excerpt, not a manually executable alternative
to the generated plan and executor:

```powershell
$Common = @(
  '--authorization-file', '<authorization-file>',
  '--authorization-sha256', '<authorization-sha256>',
  '--board-id', '210512180081',
  '--expected-part', 'xc7z010clg400-1',
  '--expected-target', 'localhost:3121/xilinx_tcf/Digilent/210512180081',
  '--source-commit', '<40-hex-source-commit>',
  '--plan-file', '<frozen-p7-plan>', '--plan-sha256', '<plan-sha256>',
  '--bitstream', '<immutable-bit>', '--bitstream-sha256', '<bit-sha256>',
  '--xsa', '<immutable-xsa>', '--xsa-sha256', '<xsa-sha256>',
  '--elf', '<immutable-p7-elf>', '--elf-sha256', '<elf-sha256>',
  '--profile', '<mode-profile>', '--profile-sha256', '<profile-sha256>',
  '--active-xdc', 'constraints/active/PORT1.generated.xdc', '--active-xdc-sha256', '<xdc-sha256>',
  '--pinmap', 'board_profiles/ax7010_tfdu_j10_j11_pinmap.csv', '--pinmap-sha256', '<pinmap-sha256>',
  '--register-map', 'config/register_map/ir_axi_regs.yaml', '--register-map-sha256', '<register-map-sha256>',
  '--shutdown-bitstream', 'shutdown_bitstream/tfdu_shutdown_j10_j11.bit', '--shutdown-bitstream-sha256', '<shutdown-sha256>',
  '--ltx', '<immutable-ltx>', '--ltx-sha256', '<ltx-sha256>',
  '--shutdown-on-exit', '--no-ethernet', '--no-motion', '--lane-count', '2', '--max-lane-mask', '0x3',
  '--vivado-path', 'D:/Xilinx/Vivado/2023.1/bin/vivado.bat', '--hw-server-url', 'localhost:3121'
)
```

## 3. Risk-ordered hardware stages

Actual hardware execution must use the executor, its plan hash, and its atomic
execution ledger. Never copy a child command from this runbook and invoke it by
hand. Set the authorization environment only around the single executor command,
and remove it immediately afterwards:

```powershell
$env:RF_COMM_HW_AUTH = 'P7_STATIONARY_APP_LAYER_APPROVED'
try {
  $ExecutionLedger = '<unique-evidence-root>/sequence_execution_ledger.json'
  python tools/run_p7_authorized_hardware_sequence.py `
    --sequence-plan $SequencePlan `
    --sequence-plan-sha256 $SequencePlanSha `
    --execution-ledger $ExecutionLedger `
    --source-commit $Head `
    --max-runtime-sec 1800 `
    --shutdown-on-exit --no-ethernet --no-motion `
    --lane-count 2 --max-lane-mask 0x3 `
    --execute-hardware `
    --json-summary
} finally {
  Remove-Item Env:RF_COMM_HW_AUTH -ErrorAction SilentlyContinue
}
```

Never proceed to the next risk tier unless the current wrapper returns `0`, its semantic/postprocess gate is PASS, and shutdown-after is independently valid.

### Diagnostic suffix mode

When explicitly authorized after a failed full run, the generator may use
`--diagnostic-suffix55` with a new run ID containing `diag_suffix55`. This mode
contains only formal ordinals 1--4 and 55--65 (15 stages total), excludes the
stationary stage, and must declare `DIAGNOSTIC_ONLY`, `coverage_claimed=false`,
and `HARDWARE_ACCEPTANCE=PENDING_HW` in its hashed plan and stage authorizations.
It is a single-attempt diagnostic epoch: `--resume` is forbidden. A failure
still requires independent shutdown recovery and a new run ID. Diagnostic PASS
records contribute no final acceptance coverage; after all suffix defects are
fixed, a new formal 66-stage run must start from stage 1 and is the only run
permitted to launch the one-time stationary stage.

For later failures inside that suffix, use the adaptive mode only when the new
generator can create and the executor can independently revalidate a hashed
`rf-comm-p7-diagnostic-impact-proof-v1`.  Pass
`--diagnostic-first-ordinal <N>` plus the exact prior run ID, sequence-plan
path/hash, and terminal execution-ledger path/hash.  The generated matrix is
always formal ordinals 1--4 followed by the contiguous unresolved suffix
`N..65`; it never includes 66.  The proof binds every skipped exact PASS
summary, the prior FAIL ledger, all stage-consumed artifact hashes and runtime
settings, a closed JTAG wrapper/Tcl/backend/register dependency set, the exact
sequence symbols imported by the JTAG wrapper, regenerated transaction/input
and normalized backend-manifest hashes, and Python/Vivado/helper identity.
Any missing field, changed hash, uncertain dependency, or tamper blocks plan
generation/validation and requires starting at the earliest affected stage.
The proof and skipped stages explicitly contribute zero acceptance coverage.

All P7 wrappers share one exclusive board lock. Never launch two wrappers concurrently, never delete or auto-recover a lock as "stale", and do not use non-overlapping timestamps as a substitute for the recorded lock acquisition. If a lock remains after a crash, stop and inspect the physical board/shutdown state before a human-authorized recovery.

### 3.1 Safe-idle recheck

Run the dedicated no-application-fragment safe-idle/readback stage first through `run_p7_jtag_axi_stage_safe.py --semantic-mode safe-idle`. The authorization must bind `P7_JTAG_SEMANTIC_MODE=safe-idle` and the exact transaction. This mode forbids an RFAP backend manifest, START, COMMIT, and payload writes; the only permitted write is the final P6 `STOP|SHUTDOWN`. It must read/assert every required status and counter, run the strict safe-idle parser after shutdown, and record `drove_tfdu_txd=false`, `enabled_tfdu_receiver=false`, and `uart_access=false`.

```powershell
python scripts/hw/run_p7_jtag_axi_stage_safe.py @Common `
  --execute-hardware --semantic-mode safe-idle --stage-name p7_safe_idle_recheck `
  --transaction-file <safe-idle-transaction> --transaction-sha256 <transaction-sha256> `
  --max-runtime-sec <bounded-seconds> --stage-timeout-sec <bounded-seconds> `
  --evidence-dir <unique-safe-idle-evidence-dir> --json-summary
```

The hash-frozen transaction and raw result must cover these keys:

```text
SAFE_STATUS (BUSY/FAIL/CONFIG_ERROR/TIMEOUT bits clear)
SAFE_TX_COUNT=0
SAFE_RX_GOOD_L0=0
SAFE_RX_GOOD_L1=0
SAFE_CRC_BAD=0
SAFE_PAYLOAD_MISMATCH=0
SAFE_RETRY_EXHAUSTED=0
SAFE_TX_FAIL=0
SAFE_TXD_HIGH_MAX=0
SAFE_DUTY_VIOLATION=0
SAFE_ERROR_CODE=0
SAFE_STICKY_ERROR=0
```

If no canonical stage produces these readbacks without transmitting an application fragment, record `SKIP_WITH_REASON`; do not infer safe-idle PASS from preflight, a dry-run, or shutdown programming alone.

### 3.2 P6 one-frame regression

Run lane masks `0x1`, `0x2`, and `0x3`, at least ten known payload frames per mask. Require zero CRC bad, payload mismatch, retry exhausted, TX fail, and duty violations; require the configured TXD-high safety maximum. The semantic evidence must retain the three frame counts and zero-valued counters. A later large-object run does not retroactively prove that this lower-risk stage occurred in order.

The consistency tool also accepts three separately authorized direct-backend runs named as P6 frame regression stages when their strict parser summaries are bound to the safe-wrapper raw logs: `LANE0_ONLY`, `LANE1_ONLY`, and `REPLICATE_0X3`, each with at least ten parsed fragments. `STRIPE_ROUND_ROBIN` is not a substitute for the required `0x3` mask because each striped fragment uses only one lane.

### 3.3 Direct-JTAG fragment boundary matrix

Before any large-object JTAG run, generate and execute all `12 lengths x 4 policies = 48` strict backend bundles. Required lengths are `0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024`; required policies are lane0-only, lane1-only, stripe, and replicate. Name each authorized stage `fragment_boundary_<length>_<policy>_<pattern>` so the intended pair remains recoverable even if an attempt fails before postprocessing. Each pair uses latest-attempt acceptance semantics: preserve earlier failures and audit their shutdown, but only the latest attempt for that exact length/policy may satisfy the matrix.

Generate the 48 offline bundles first. `<immutable-input-of-$Length-bytes>` must be a pre-created, hash-frozen file of exactly that length; use a distinct immutable authorization and evidence directory for each subsequent wrapper command:

```powershell
$BoundaryLengths = 0,1,30,214,215,216,247,248,430,431,432,1024
$BoundaryPolicies = 'LANE0_ONLY','LANE1_ONLY','STRIPE_ROUND_ROBIN','REPLICATE_0X3'
foreach ($Length in $BoundaryLengths) {
  foreach ($Policy in $BoundaryPolicies) {
    $Case = "fragment_boundary_${Length}_${Policy}_deterministic_random"
    python tools/p7_jtag_backend.py generate `
      --input-file <immutable-input-of-$Length-bytes> `
      --transaction-file <bundle-root>/$Case/transactions.txt `
      --manifest <bundle-root>/$Case/bundle_manifest.json `
      --session-epoch <epoch> --object-id <unique-object-id> --lane-policy $Policy `
      --jtag-frequency-hz 1000000 --authorized-runtime-sec <bounded-seconds>
    # Hash/review the bundle, create the exact per-case authorization, then invoke
    # run_p7_jtag_axi_stage_safe.py once with --stage-name $Case.
  }
}
```

Do not proceed to large JTAG until all 48 strict parser summaries are bound to their safe-wrapper raw logs and pass. The PS functional mode later repeats this boundary matrix as an independent real-PS regression; it does not replace this earlier risk gate.

### 3.4 Direct JTAG/AXI auxiliary large-object matrix

Generate each bundle offline. The generator never executes hardware:

```powershell
python tools/p7_jtag_backend.py generate `
  --input-file <immutable-input> `
  --transaction-file <run-dir>/transactions.txt `
  --manifest <run-dir>/bundle_manifest.json `
  --session-epoch <epoch> --object-id <object-id> `
  --lane-policy <LANE0_ONLY|LANE1_ONLY|STRIPE_ROUND_ROBIN|REPLICATE_0X3> `
  --jtag-frequency-hz 1000000 --authorized-runtime-sec <bounded-seconds>
```

Then run the generated transaction only through the safe wrapper:

```powershell
python scripts/hw/run_p7_jtag_axi_stage_safe.py @Common `
  --execute-hardware `
  --stage-name <large_object_jtag_size_policy_pattern> `
  --transaction-file <run-dir>/transactions.txt --transaction-sha256 <transaction-sha256> `
  --backend-manifest <run-dir>/bundle_manifest.json --backend-manifest-sha256 <manifest-sha256> `
  --jtag-frequency-hz 1000000 `
  --max-runtime-sec <bounded-seconds> --stage-timeout-sec <bounded-seconds> `
  --evidence-dir <unique-evidence-dir> --json-summary
```

The wrapper performs the strict backend parse after shutdown and binds the parser to the exact run-local raw log. The required auxiliary matrix, in execution order, is:

- 4 KiB deterministic-random on stripe;
- 64 KiB counter, PRBS15, deterministic-random, and all-byte-values on stripe;
- 1 MiB deterministic-random on lane0-only, lane1-only, stripe, and replicate.

Each case must preserve the backend manifest, transaction file, raw result, reassembled output, parser JSON, safe-wrapper JSON, event log, and shutdown logs. A parser result from a mock or a different raw log is invalid.

The live JTAG debug master is full AXI4 and feeds an explicit Xilinx AXI protocol converter whose downstream interface remains the existing safety-reviewed AXI4-Lite peripheral. Only naturally consecutive words in the TX payload window (`0x200..0x2fc`) and TX/RX readback windows (`0x200..0x3fc`) may use `INCR` bursts, bounded to 64 words; the converter serializes every beat into ordered AXI4-Lite accesses. Other adjacent same-direction independent control/status operations may use at most 16 `LEN=1` transactions in one `run_hw_axi -queue` call. Every P6 control-register write at offset `0x100` (`CLEAR`, `COMMIT`, `START`, `STOP`, or `SHUTDOWN`) is a dependency barrier: flush all pending transactions first, execute that control write alone, and never put it in a queued call. Direction changes, polls/assertions, `END`, address discontinuity for a burst, a control dependency, and either size bound force a flush. The active JTAG_AXI IP must be built with `CONFIG.PROTOCOL=0`, `CONFIG.RD_TXN_QUEUE_LENGTH=16`, and `CONFIG.WR_TXN_QUEUE_LENGTH=16`; the converter must bind `SI_PROTOCOL=AXI4` and `MI_PROTOCOL=AXI4LITE`. The content-addressed build summary and offline Vivado property inspection must prove those settings before authorization. The executor preserves the original DSL operation count, authorization checks, dependency order, validation order, and per-word result evidence. Dry validation reports burst, queued-single, and standalone ordered-control metrics separately, requires zero queued control writes, and never treats the downstream converter as reducing the logical AXI operation count. No performance optimization may increase the 1800-second authorization ceiling.

Vivado renders a multiword JTAG-AXI `DATA` property most-significant word first: the rightmost rendered word maps to the lowest `INCR` address. The Tcl writer must therefore reverse the natural low-to-high DSL word list before creating a multiword write transaction, and the Tcl reader must reverse the rendered property-word index before assigning per-address evidence keys. The offline Tcl stub test must prove both directions with distinct word values; otherwise a write/read pair can appear self-consistent while the target memory contains whole-burst word reversal.

The PS safe wrapper uses the same JTAG Tcl entrypoint for its mandatory shutdown-before and shutdown-after barriers. Its `SHUTDOWN` argv must therefore remain byte-for-byte aligned with the JTAG wrapper's 17-argument contract, including both `max_operations` and `max_transaction_bytes` before `max_runtime_sec`. A focused offline test must count and position all 17 Tcl arguments; a read-only preflight PASS cannot promote a PS stage whose shutdown argv is rejected before programming.

For each required tuple, the summary must recompute the positive per-fragment poll-latency upper-bound distribution from the strict fragment ledger, prove that the object transport upper bound is their sum, and verify the poll-bound application-goodput lower-bound formula. It must separately report host-monotonic child elapsed time and host end-to-end goodput, explicitly labeled as including Vivado/programming/JTAG/polling/host overhead and not as optical-only latency. These JTAG bounds are auxiliary and are never substituted for PS application metrics.

### 3.5 Real PS functional and recovery modes

Use the same immutable PS bit/XSA/ELF/core-readiness inputs for all PS modes. Include the generated `ps7_init.tcl`, build summaries, active profile, lane1 promotion record, and deterministic input file with their hashes:

```powershell
$PsExtra = @(
  '--input-file', '<immutable-input>', '--input-sha256', '<input-sha256>',
  '--ps7-init', 'build/p7_ps_vitis_workspace/p7_platform/hw/ps7_init.tcl', '--ps7-init-sha256', '<ps7-init-sha256>',
  '--p6-build-summary', 'evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json', '--p6-build-summary-sha256', '<p6-summary-sha256>',
  '--p7-build-summary', 'evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json', '--p7-build-summary-sha256', '<p7-summary-sha256>',
  '--core-readiness-attestation', 'evidence/generated/p7_ps_core_hardware_readiness.json', '--core-readiness-attestation-sha256', '<readiness-sha256>',
  '--active-profile', 'board_profiles/ACTIVE_PROFILE.json', '--active-profile-sha256', '<active-profile-sha256>',
  '--lane1-promotion-summary', 'evidence/generated/p7_lane1_promotion_summary.json', '--lane1-promotion-summary-sha256', '<promotion-sha256>',
  '--xsdb-path', 'D:/Xilinx/Vitis/2023.1/bin/xsdb.bat', '--jtag-frequency-hz', '1000000'
)
```

Run in this order, with a distinct authorization file and evidence directory per mode:

```powershell
python scripts/hw/run_p7_ps_application_stage_safe.py @Common @PsExtra --execute-hardware --mode functional     --max-runtime-sec 900 --evidence-dir <functional-dir> --json-summary
python scripts/hw/run_p7_ps_application_stage_safe.py @Common @PsExtra --execute-hardware --mode fault-fallback --max-runtime-sec 900 --evidence-dir <fallback-dir>   --json-summary
python scripts/hw/run_p7_ps_application_stage_safe.py @Common @PsExtra --execute-hardware --mode abort-restart  --max-runtime-sec 900 --evidence-dir <abort-dir>      --json-summary
python scripts/hw/run_p7_ps_application_stage_safe.py @Common @PsExtra --execute-hardware --mode queue          --max-runtime-sec 900 --evidence-dir <queue-dir>      --json-summary
```

The functional stage must retain all eight 1 MiB/64 KiB policy-pattern cases and all `12 lengths x 4 policies = 48` boundary cases. Fault evidence must be labeled `SOFTWARE_INJECTED_SCHEDULER_FAULT`; it is not evidence of a real optical obstruction. Abort/restart must prove partial-output wipe, shutdown, new epoch, successful recovery, and duplicate replay rejection. Queue evidence must prove depth 1, depth 8 FIFO, producer backpressure, overflow rejection before DDR write, STOP, and ABORT while queued.

### 3.6 The single final 1800-second run

This is the last transmitting hardware stage. Exactly one stationary launch
intent is allowed, regardless of its observed duration or outcome. Do not run a
separate calibration or a two-hour soak. Use the dedicated stationary
authorization file and profile generated into the reviewed sequence plan:

```powershell
python scripts/hw/run_p7_ps_application_stage_safe.py @Common @PsExtra `
  --execute-hardware --mode stationary `
  --max-runtime-sec 1800 --calibration-sec 300 --acceptance-sec 1500 `
  --sample-interval-sec 30 --idle-deadline-margin-sec 60 `
  --stationary-object-bytes 65536 `
  --evidence-dir evidence/hardware/p7/ps_application/stationary/<run-id> `
  --json-summary
```

Acceptance requires an exact configured runtime of 1800 seconds, observed terminal host wall time from 1800.0 through 1801.5 seconds, exactly 10 calibration samples plus 50 acceptance samples, and the final sample bound to the safe terminal state. The same run must cover 4 KiB, 64 KiB, and 1 MiB objects; lane0-only, lane1-only, stripe, and replicate; both directions of controlled software fallback; CRC32/SHA256/fragment ledgers; queue/backpressure; retries; lane utilization; latency; Txd-high/duty safety; and final shutdown. Acceptance median rolling goodput must be at least 80% of calibration median. The final 30-second rolling sample may be zero after the intentional drain; cumulative `application_goodput_bps` and both window medians must still be positive.

Samples are canonical PS-time windows, not delayed host-observation snapshots: samples 1 through 60 are exactly the `n x 30 s` thresholds. Cumulative counters and current/rolling goodput are rebuilt from immutable terminal records whose `end_ticks - runtime_start_ticks` fall at or before each threshold; interval object latency uses only terminals after the preceding threshold. Queue state is a later host observation, so its PS-time field is explicitly a `queue_observation_not_before_ticks` lower bound rather than a canonical threshold value; the final lower bound must bind the terminal mailbox runtime. The independent host wall watchdog is bounded separately and is not required to match the PS clock within an invented cross-clock tolerance.

The embedded calibration summary is anchored to sample 10 at the 300-second boundary. It must report cumulative objects/bytes/fragments, lane0/lane1 physical transmission shares, replicated logical-fragment fraction, controlled fallback, queue/backpressure, all ten interval latency summaries, and the acceptance-to-calibration median-goodput ratio. There is no additional calibration runtime.

Every completed object must have a raw `P7_STATIONARY_TERMINAL_BUNDLE_<sequence>_CAPTURED=1` marker and immutable descriptor-result, output, and fragment-trace files. The aggregator independently decodes every nonzero 64-byte binary fragment-trace record and reconciles its magic, identity, fragment geometry, lane mask, fallback direction, attempts, P6 errors, PS timer interval, counters, and latency ledger. The trace validator must also reconcile CRC32, SHA256, and contiguous terminal sequence. The `object_latency_*` fields measure PS object processing from a valid descriptor entering RUNNING through output CRC32/SHA256 completion. Host descriptor publication and JTAG terminal observation are excluded, so do not relabel this as host-to-host end-to-end latency.

Lane counters are policy-specific:

- lane0-only: `(lane0, lane1, replicated) = (fragments, 0, 0)`;
- lane1-only: `(0, fragments, 0)`;
- stripe without injection: both lanes used, sum equals fragments, difference at most one, replicated zero;
- replicate: `(fragments, fragments, fragments)`;
- controlled fallback: the injected-unavailable lane may appear only before the configured cutoff and the final counters must match the declared fallback policy.

The final stationary launch intent is one-shot: it may be launched only once. A short failure, abort, or crash remains immutable and shutdown-audited and leaves the final result FAIL/BLOCKED; it must not trigger an automatic second stationary launch. More than one stationary launch intent, or any hardware stage after a qualified stationary run, makes consistency fail. The qualified stationary run must be the literal final executed hardware candidate.

## 4. Offline evidence consistency and summaries

After the final shutdown, generate the deterministic chronology ledger from the immutable offline checkpoint and every executed safe-wrapper summary. This operation performs no hardware action:

```powershell
$OfflineCheckpoint = 'evidence/generated/p7_offline_gate_summary.json'
$OfflineCheckpointSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $OfflineCheckpoint).Hash.ToLowerInvariant()
python tools/summarize_p7_hardware.py `
  --generate-sequence-ledger `
  --offline-checkpoint-summary $OfflineCheckpoint `
  --offline-checkpoint-sha256 $OfflineCheckpointSha `
  --offline-checkpoint-commit <40-hex-offline-checkpoint-commit> `
  --json-summary
```

The generated file is exactly `evidence/hardware/p7/p7_run_sequence_ledger.json`, schema `rf-comm-p7-run-sequence-ledger-v1`. Its offline checkpoint binds the source commit and summary hash. Every run entry binds the risk index, attempted and passed coverage keys, exact argv, child return code, the full wrapper `authorized_execution_begin` through `authorized_execution_end` UTC interval, the candidate-child UTC interval and host-monotonic elapsed duration, safe-wrapper summary SHA256, raw-log and event-log SHA256, hardware-lock acquisition record, source commit, and both shutdown result/stdout hashes and exact markers. It must list every executed P7 wrapper summary exactly once, in non-overlapping full-wrapper chronological order.

The ledger enforces this progression:

```text
offline checkpoint
-> safe idle
-> P6 lane0/lane1/mask0x3 regressions
-> direct JTAG 48-case fragment boundary matrix
-> direct JTAG 4 KiB, then 64 KiB, then 1 MiB large-object tiers
-> PS functional
-> software fault/fallback
-> abort/restart
-> queue/backpressure
-> the unique qualified stationary run, last
```

A failed or short attempt remains in the ledger and clears its attempted coverage. A non-stationary risk tier may be rerun only through a newly reviewed immutable plan, but a higher tier cannot begin until every prerequisite coverage key is restored to PASS. Stationary is different: after any stationary launch intent it must never be rerun, and a short run, failure, abort, or crash leaves the result FAIL/BLOCKED. A full-duration/qualified stationary PASS must be the final hardware run. Missing exact argv or UTC boundaries, overlapping runs, an unlisted summary, a summary/log hash mismatch, or a later hardware run after stationary makes consistency fail.

Run the summarizer only after the ledger is generated. It performs no hardware action:

```powershell
Remove-Item Env:RF_COMM_HW_AUTH -ErrorAction SilentlyContinue
python tools/summarize_p7_hardware.py --json-summary
```

Exit codes are:

- `0`: all mandatory hardware evidence is present and consistent;
- `1`: a failure, false-PASS, tamper, inconsistent target/commit/artifact, invalid shutdown, proxy promotion, or duplicate stationary run was found;
- `2`: hardware evidence is incomplete or explicitly skipped; summaries remain `PENDING_HW`/`SKIP_WITH_REASON`.

The tool recursively inventories `evidence/hardware/p7`, re-hashes linked artifacts and manifests, binds JTAG parser output to the safe-wrapper raw log, validates the real PS path and per-object/sample ledgers, and emits all canonical and alias Markdown/JSON summaries plus provenance and CSV ledgers under `evidence/generated`. Application metrics are emitted under both `p7_application_metrics_summary` and the required root `p7_performance_summary` aliases. The final Markdown/JSON records the source evidence commit separately from `COMMIT: PENDING_FINAL_EVIDENCE_COMMIT`, lists generated summaries and the next recommended stage, renders the user/physical-scope fields, and keeps product-final acceptance at `PENDING`.

Before committing:

```powershell
python -B -m unittest tests.test_summarize_p7_hardware -v
git diff --check
git status --short
```

Final P7 PASS remains explicitly bounded:

```text
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT
```
