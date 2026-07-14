# P7 Stage 62 current-run handoff

This handoff freezes the main thread after diagnostic run `p7_20260713_stationary_app_r32_diag_suffix55`. It records observed evidence only. It does not turn diagnostic PASS stages into acceptance coverage, does not claim Stage 62 functional execution, and keeps `HARDWARE_ACCEPTANCE=PENDING_HW`.

## A. Git baseline

- Repository: `C:\Users\user\Documents\RF_COMM_MULTILANE`
- Branch: `codex/p7-stationary-application`
- HEAD: `f002e80aeb575b2b3aea8ce34909dd65584140d9`
- Merge-base with local `main`: `ca041d4877b831de84fe7829788ac835b0b46acd`
- Working tree clean: `false`
- Pre-handoff `git status --short --untracked-files=all`: 482 records (26 tracked modifications and 456 untracked files). The exact output is archived at `C:\Users\user\Documents\RF_COMM_MULTILANE\stage62_handoff\current\evidence\git_status_short_pre_handoff.txt`, SHA256 `90b78240e220bdec5350d481bf89c80e34db2e73554ed6a87a3c1638504f9c2d`.
- Exhaustive pre-handoff untracked inventory: `C:\Users\user\Documents\RF_COMM_MULTILANE\stage62_handoff\current\UNTRACKED_FILES.txt`, 456 files, SHA256 `74c99bf70ccc96a5ad3ffd9b51b80965df0a8623762515c8453bf5921a9c663b`. The snapshot was taken before this handoff directory contained files; handoff files are enumerated by `CURRENT_RUN_MANIFEST.json`.
- Binary-capable tracked diff: `C:\Users\user\Documents\RF_COMM_MULTILANE\stage62_handoff\current\BASELINE.patch`, 118814 bytes, SHA256 `221dd5692419e68e5c8ba8717b31957589cd8b1f5f913f843396cd70fd9ea2be`.
- The r32 source commit is exactly HEAD `f002e80...`. The complete regression record was generated on a clean source tree and binds that commit. The later tracked dirt consists only of the 26 generated evidence files listed below; the pre-handoff untracked files are r32 runtime evidence under `evidence/hardware/p7`. No source, test, runner, profile, constraint, or authorization input changed after the clean checkpoint.

Tracked working-tree diff files:

```text
evidence/generated/p7_2lane_scope_summary.md
evidence/generated/p7_application_protocol_summary.md
evidence/generated/p7_artifact_provenance_summary.json
evidence/generated/p7_artifact_provenance_summary.md
evidence/generated/p7_backend_conformance_summary.md
evidence/generated/p7_fault_recovery_summary.md
evidence/generated/p7_file_integrity_summary.md
evidence/generated/p7_fragmentation_reassembly_summary.md
evidence/generated/p7_lane1_promotion_summary.json
evidence/generated/p7_lane_scheduler_summary.md
evidence/generated/p7_no_ethernet_summary.md
evidence/generated/p7_no_motion_summary.md
evidence/generated/p7_offline_gate_summary.json
evidence/generated/p7_offline_gate_summary.md
evidence/generated/p7_offline_test_run.json
evidence/generated/p7_protocol_vector_summary.md
evidence/generated/p7_ps_core_hardware_readiness.json
evidence/generated/p7_ps_core_hardware_readiness.md
evidence/generated/p7_ps_runtime_build_summary.json
evidence/generated/p7_ps_runtime_summary.md
evidence/generated/p7_queue_backpressure_summary.md
evidence/generated/p7_repo_intake.md
evidence/generated/p7_repo_intake_summary.json
evidence/generated/p7_repo_intake_summary.md
evidence/generated/p7_segmentation_reassembly_summary.md
evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json
```

The complete untracked file list is intentionally not duplicated here; `UNTRACKED_FILES.txt` is the canonical list and records classification, byte count, and SHA256 for every file.

## B. Build baseline

- ELF: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\artifacts\p7_runtime_26f93c15b66be63bed6fa469edaed4578eab2cd64b58e9eeb4b447ebf952503c.elf`; 315160 bytes; SHA256 `26f93c15b66be63bed6fa469edaed4578eab2cd64b58e9eeb4b447ebf952503c`.
- Linker map: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\artifacts\p7_runtime_76fc4a82a46a5e7b2c52a997eaed7a1ee682e32cca71920cb855d92ca4d64825.map`; 85298 bytes; SHA256 `76fc4a82a46a5e7b2c52a997eaed7a1ee682e32cca71920cb855d92ca4d64825`.
- Full disassembly: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\generated\vitis\p7_ps_runtime\p7_runtime_disassembly.txt`; 498675 bytes; SHA256 `ddbcbc17f26e117d75d3abc4c7c9b56fc79eb06cc43588f1e304166b6f59f1f3`.
- Candidate bitstream: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p6\bitstreams\p6_ps_dynamic_transport_34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249.bit`; 2083856 bytes; SHA256 `34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249`.
- XSA: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p6\bitstreams\p6_ps_dynamic_transport_b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9.xsa`; 560408 bytes; SHA256 `b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9`.
- BSP identity: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\artifacts\p7_bsp_xparameters_eae65eb30388bbd72f40b3699cae81c773d12279f2500b99a09c5b2a37b44c76.h`; SHA256 `eae65eb30388bbd72f40b3699cae81c773d12279f2500b99a09c5b2a37b44c76`.
- Platform identity: `C:\Users\user\Documents\RF_COMM_MULTILANE\build\p7_ps_vitis_workspace\p7_platform\export\p7_platform\p7_platform.xpfm`; SHA256 `6f41de6e0861e16fa0d1892e625be505fc33fee924628e0a5f66d7ce1eea6811`.
- PS7 init: `C:\Users\user\Documents\RF_COMM_MULTILANE\build\p7_ps_vitis_workspace\p7_platform\hw\ps7_init.tcl`; SHA256 `84e478d79c0b7bfe6dfc45a5a99ab850c30c7db11d8fec1dae064133dd64b448`.
- Compiler: `D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-gcc.exe`; `arm-xilinx-eabi-gcc.exe (GCC) 12.2.0`.
- Linker: `D:\Xilinx\Vitis\2023.1\gnu\aarch32\nt\gcc-arm-none-eabi\bin\arm-none-eabi-ld.exe`; `GNU ld (GNU Binutils) 2.39.0.20220819`.
- Build command: `D:\Xilinx\Vitis\2023.1\bin\xsct.bat scripts/build_p7_ps_runtime.tcl C:\Users\user\Documents\RF_COMM_MULTILANE C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p6\bitstreams\p6_ps_dynamic_transport_b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9.xsa`.
- Compile flags: `-Wall -O0 -g3 -c -fmessage-length=0 -fstack-usage -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard` plus the platform BSP include and dependency-generation flags.
- Link flags: `-mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard -Wl,-build-id=none -Wl,-Map=... -specs=Xilinx.spec -Wl,-T -Wl,../src/lscript.ld` plus the platform BSP library path.
- Optimization: `-O0`. LTO: not enabled. Canonical offline gate cache status: `BYPASS`; gate result 13/13 PASS, SHA256 `894160354835811665a51b7594abf936777a935f4eabec3824f82a52bff9a6b9`. Complete clean-source regression: 167/167 PASS, SHA256 `2ad76a470e2bb990fa2871bed14466db30f33caa230048a21449283d9758c4a2`.
- Cache/MMU runtime caveat: the firmware source calls `Xil_DCacheDisable()`, but r32 never started the ELF, so that call was not exercised. MMU state was not independently measured and remains `UNKNOWN` for r32.
- ELF/run binding: the r32 Stage 62 authorization and attempted command bind this exact ELF SHA256. The ELF corresponds to the planned r32 candidate, but shutdown-before failed before candidate programming, ELF download, or ELF start; it is therefore not an executed r32 artifact.

Large artifacts were not copied into the handoff directory:

| Artifact | UTC generation time | Git ignored | Git tracked |
|---|---:|---:|---:|
| ELF above | `2026-07-13T08:28:10.8869059Z` | true | true |
| linker map above | `2026-07-13T08:28:10.8869059Z` | false | true |
| full disassembly above | `2026-07-13T08:28:11.1970249Z` | false | true |
| candidate bitstream above | `2026-07-10T12:42:28.4991922Z` | true | false |
| XSA above | `2026-07-10T12:42:30.9131285Z` | true | false |

## C. Current run

- Run ID: `p7_20260713_stationary_app_r32_diag_suffix55`.
- Run mode: `DIAGNOSTIC_SUFFIX_55`, `coverage_claimed=false`, `HARDWARE_ACCEPTANCE=PENDING_HW`; ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65` were planned. No Stage 66 was present.
- Ledger start: `2026-07-13T08:42:35.013574+00:00`.
- Ledger terminal update: `2026-07-13T10:34:34.329993+00:00`.
- Terminal status: `FAILED` (`ledger.status=FAIL`). Attempts: 12; completed diagnostic stages: 11; failure index: 11 (ordinal 62).
- Sequence runner exit code: `1`. Stage 62 wrapper exit code: `1`. Neither process timed out; the contained Stage 62 wrapper tree was reaped.
- Firmware error code: `NOT_AVAILABLE_CANDIDATE_NOT_STARTED`. Wrapper status: `P7_PS_APPLICATION_SAFE_STAGE=FAIL_SHUTDOWN_BEFORE`.
- Stage 62 wrapper interval: `2026-07-13T10:32:50.377743+00:00` to `2026-07-13T10:34:34.188238+00:00`.
- Stage 62 execution semantics: the ordinal-62 safe wrapper was invoked, but shutdown-before failed with raw rc 125 and no programming marker. The candidate bitstream was not programmed, the PS ELF was not downloaded or started, and the functional workload was refused. Therefore Stage 62 functional execution is `false`, not a hardware functional FAIL/PASS observation.
- Result descriptor: `MISSING_NOT_CREATED`; only offline-prepared descriptor templates exist in the immutable bundle. No hardware result descriptor exists for r32.
- Mailbox: `MISSING_NOT_CREATED`; `postprocess.mailbox={}` and no final mailbox capture exists.
- First-error/OCM record: `MISSING_NOT_CREATED`; summary reports `present=false`, `required=false` because the candidate never started. This is not a diagnostic PASS.
- Output wipe: `NOT_APPLICABLE_NO_APPLICATION_OUTPUT`. No r32 application output was created, so there is no pre-wipe snapshot and no pre-wipe content may be inferred.
- Planned address information, not an execution claim: descriptor ring base `0x00020100`; boundary-8 input `0x00100000`, output `0x00900000`, trace `0x01100000`, object/fragment length 30, lane policy 1. The complete unexecuted address plan is archived as `evidence\r32_stage62_execution_plan.txt`. No address was materialized by the r32 candidate.
- Lane policy: two lanes authorized, maximum lane mask `0x3`; no Ethernet, no motion; boundary 8 was planned lane0-only. JTAG was 1 MHz. The external legacy `hw_server` remained outside the run's ownership and was not touched.
- Timeout parameters: sequence `--max-runtime-sec 1800`; Stage 62 service `--max-runtime-sec 900`; preflight 60 seconds; shutdown 60 seconds. r32 failed before these workload limits and did not time out.
- Shutdown-before result: FAIL, programming attempted `0`, no TFDU shutdown marker; exact result SHA256 `11f9d86a465d1a91fa72c982044c65c46f0a9b4c932f82fae622c77ad4d1642f`.
- Wrapper shutdown-after: PASS, programming attempted `1`, exact frozen-shutdown marker present, process tree reaped; SHA256 `a01660d60b018a350eca153636b1e5926be82b5723b49226fdcaa50ee23abce2`.
- Independent approved recovery: PASS with `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`, normalized `SHUTDOWN_EXIT=0`; SHA256 `8ded9071051f0d9732d7d374954e8b535c3f2df3a9c17868502348f587aea850`.
- Last valid terminal fact: `candidate/ELF stage was refused because shutdown-before failed`, followed by `P7_PS_APPLICATION_SAFE_STAGE=FAIL_SHUTDOWN_BEFORE` and a valid shutdown-after PASS record.
- Evidence gaps are explicit: no executed descriptor, mailbox, OCM first-error record, application output, pre-wipe snapshot, or firmware code exists for r32.
- Process state at handoff: no r32 sequence runner, Stage 62 wrapper, Vivado, XSDB, or run-owned cs_server remains. Scoped `RF_COMM_HW_AUTH` is cleared. External legacy `hw_server.exe` PID 45220 remains running and untouched.

Full sequence command:

```text
python -B tools/run_p7_authorized_hardware_sequence.py --sequence-plan C:\Users\user\Documents\RF_COMM_MULTILANE\.hardware_authorization\p7_20260713_stationary_app_r32_diag_suffix55_sequence_plan.txt --sequence-plan-sha256 118da778c5620cbbc01d2673699a7b835d8994b125b4af31b1dea498be8f1a68 --execution-ledger C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260713_stationary_app_r32_diag_suffix55\sequence_execution_ledger.json --source-commit f002e80aeb575b2b3aea8ce34909dd65584140d9 --max-runtime-sec 1800 --shutdown-on-exit --no-ethernet --no-motion --lane-count 2 --max-lane-mask 0x3 --execute-hardware --json-summary
```

The scoped environment value `RF_COMM_HW_AUTH=P7_STATIONARY_APP_LAYER_APPROVED` existed only for that invocation and was removed afterward. The exact ordinal-62 child argv is preserved in the ledger.

Key original evidence:

- Sequence plan: `C:\Users\user\Documents\RF_COMM_MULTILANE\.hardware_authorization\p7_20260713_stationary_app_r32_diag_suffix55_sequence_plan.txt`; SHA256 `118da778c5620cbbc01d2673699a7b835d8994b125b4af31b1dea498be8f1a68`.
- Sequence ledger: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260713_stationary_app_r32_diag_suffix55\sequence_execution_ledger.json`; SHA256 `18d2c870058b086fbe6765f602ace2608bf34a2f8cbadf7524bf6ae044efa800`.
- Stage 62 summary: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260713_stationary_app_r32_diag_suffix55\062_p7_ps_functional\p7_ps_application_stage_summary.json`; SHA256 `a8792667cbc5740c350cef9a08796c2d635cfb76055139fa214bf33b99c77f21`.
- Stage 62 wrapper stdout: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260713_stationary_app_r32_diag_suffix55\.sequence_execution_ledger_wrapper_logs\062_p7_ps_functional.stdout.log`; SHA256 `260dd9d56a38970e7a3f8628dbfe99fd2bb37160420b2b9fdffe738d2ee0a6ce`.
- Raw-evidence manifest: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260713_stationary_app_r32_diag_suffix55\062_p7_ps_functional\p7_raw_evidence_sha256_manifest.json`; SHA256 `795780364252752ed29c65e7a6309f457b68e2b0d4aacef2408985066ca383cf`; 248/248 records independently matched, with no missing or mismatched record.
- Recovery directory: `C:\Users\user\Documents\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260713_stationary_app_r32_diag_suffix55\recovery_shutdown_after_failed_stage062_20260713T103550Z`.

## D. Current known technical conclusions

These conclusions come from immutable r31 evidence; r32 did not execute the candidate and adds no Stage 62 data-path observation.

- R31's first visible failure is `P7_ERROR_OUTPUT_COPY`, error 23, boundary index 8, object length 30, descriptor status 4.
- P6 before/after payload comparison and protocol validation passed; descriptor P6 retry/exhaustion/TX/CRC/payload-mismatch counters are zero. The current first visible failing boundary is the copy from the local OCM/stack `view.chunk` to DDR output or its immediate readback.
- The r31 ELF disassembly confirms that `p7_copy_bytes_verified` uses byte operations `LDRB` and `STRB` and a `DSB`; the exact excerpt is archived in `evidence\r31_p7_copy_bytes_verified_disassembly.txt`.
- R31 lacks a nonzero destination canary.
- R31 lacks an immutable `source_before` reference and lacks `source_after`, `destination_before`, and `destination_after` snapshots.
- R31 lacks `first_bad_index` and expected/observed byte fields.
- The r31 host output file was captured after failure wipe. Its 30 zero bytes cannot represent or reconstruct pre-wipe output content.
- R31's overwrite-first hardening replaced the raw encoder payload before later checks. It therefore cannot prove that the original `rf_app_encode_fragment`/`ENCODE_RAW` memcpy was correct.
- Ordinary P6/PHY random error and a generic memcpy defect are no longer primary candidates. Investigation should remain at the earliest observable Stage 62 corruption boundary and distinguish original encode, local buffers, MMIO readback, received data, DDR copy, and immediate DDR readback.
- The historical 32-bit layout with `rx_payload` at offset 255 is a confirmed alignment hazard and a strong boundary of interest, but it is not a proven root cause.
- The current f002/r32 firmware adds canary, immutable reference, and first-error diagnostics, but r32's shutdown-before failure means none of those diagnostics ran on hardware.

Machine-readable r31 descriptor/trace decodes and the exact raw result are in `stage62_handoff\current\evidence`.

## E. Next-thread scope

The specialist thread may work only on Stage 62 diagnosis, Stage 62 microtests, necessary offline tests, necessary builds and ELF disassembly checks, and directly related parser/runner/diagnostic-record changes. All modifications must occur in an independent worktree and independent branch based on `f002e80aeb575b2b3aea8ce34909dd65584140d9`.

It must not modify other-stage PASS criteria, expected payload/CRC/SHA values, remove or bypass memcmp/CRC/SHA/guards, remove failure output wipe, change formal or stationary acceptance, change RTL or DDR initialization without evidence, run stages 1–66, run the 1800-second stationary stage, or merge automatically. Full boundaries are repeated in `NEXT_THREAD_SCOPE.md`.

The frozen main thread must execute no project command until the exact unlock phrase is received:

`恢复主线程：读取 stage62_handoff/return/STAGE62_RETURN_TO_MAIN.md`
