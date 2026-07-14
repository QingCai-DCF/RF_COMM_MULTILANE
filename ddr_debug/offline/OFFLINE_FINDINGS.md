# DDR / External-Master Offline Checkpoint

Status: `OFFLINE_HOST_PATH_AUDIT_PASS`

`HARDWARE_ACCEPTANCE: PENDING_HW`

No hardware action, build, Stage 1-61 run, Stage 62 run, full-sequence run, or stationary run was performed in this checkpoint.

## Bound R37 observation

The immutable R37 Case B evidence was re-read as raw bytes and bound back to its recorded command, execution plan, and attested Tcl source:

- external-master destination fixture: 256 bytes, SHA256 `b7ef71102905bfadd7b60c7ff310f2a9adf2a31f327c18c2c9c1411119ea7776`;
- fixture byte at offset 9: `0xC3`;
- prestart raw readback: 256 bytes, SHA256 `3198a52a7e09dde9d05a82db251f6497845399c4d749c8441fa39866ca92f3bb`;
- readback byte at offset 9: `0x00`;
- exactly one mismatch, at absolute address `0x00900009`;
- intended firmware copy target: `0x00900040`;
- recorded host command SHA256: `15f045392ce5e21923801985dcb6b7255fa0eb9966eef92f469f3f398814513c`;
- attested Tcl SHA256: `7bff43ee1605c2885d7c2dd4e1557de3bc03803a6be68e1ffe7929899fb7e967`.

The Tcl control flow writes `stage62_microtest_destination_fixture.bin` with `dow -data` to the Case B fixed hexadecimal destination `0x00900000`, performs a raw byte dump, requires exact file equality, and reaches `con` only after that equality check. R37 failed at the equality check. Therefore the CPU was not released, the firmware microtest did not execute, Stage 62 did not execute, and TFDU Txd was not driven.

The machine-readable audit is in `r37_host_prestart_audit.json`.

## Host-side hypotheses excluded offline

The following deterministic explanations do not fit the bound evidence:

- wrong or stale fixture contents;
- offset-9 expected byte changed from `0xC3`;
- decimal-versus-hexadecimal address parsing;
- destination offset accidentally changed to the intended firmware target;
- text-mode newline conversion;
- host comparison endianness or byte-packing normalization;
- parsing a formatted memory dump instead of the raw binary readback;
- CPU, P6, Stage 62, or TFDU activity overwriting the byte before the prestart check.

This does not identify the lower-level mechanism. The earliest unresolved boundary remains the external-master write/completion/readback self-loop. Candidate mechanisms still include the `dow -data` write path, transaction completion/visibility, the external-master read path, PS interconnect, DDR initialization/controller/training, and board-level DDR.

AMD's XSDB documentation defines `dow -data <file> <addr>` as a binary-file download and separately defines scalar and binary-file `mwr` access-width semantics. The diagnostic tool emits one scalar command per value so XSDB cannot silently coalesce a byte list into wider accesses:

- <https://docs.amd.com/r/2024.2-English/ug1725-xsdb-reference-guide/dow>
- <https://docs.amd.com/r/2023.1-English/ug1400-vitis-embedded/mwr?contentId=DulkT2wCYsoIWIA0wHKORw>

## Prepared offline tooling

`tools/ddr_external_master_diagnostic.py` now provides:

- strict `0x` plus eight-hex-digit address parsing;
- enforcement of the slot-0 output scratch window `0x00900000..0x010FFFFF`;
- original fixture, `A5 5A 3C C3`, nonzero counter, and PRBS15 patterns;
- raw binary comparison with exact mismatch count and first address;
- reviewable `download`, block, byte, halfword, and word transaction plans;
- an explicit same-target completion read before independent raw readback;
- new-directory-only offline case materialization with fixture and command-plan SHA256;
- a nine-new-run minimum pattern/repetition matrix.

The generated command plans are not standalone hardware authorization and must not be pasted into XSDB. They require integration into the project safe wrapper, immutable authorization binding, lock acquisition, shutdown-before, containment, and shutdown-after.

## Pre-hardware checkpoint

At `2026-07-14T09:45:35.8446218+08:00`:

- `active_runner=false`;
- `active_xsdb_transaction=false`;
- `active_vivado_transaction=false`;
- the only `hw_server.exe` was resident with listening sockets only and no established transaction;
- all checked project runner locks were absent;
- the latest R37 recovery summary SHA256 was `1ef257e6e1ea7d7724522bc042de32ae96b1bdcf620db8b712ad8a090051e2b9` and contained `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`, `SHUTDOWN_EXIT=0`, and `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`;
- `RF_COMM_HW_AUTH` was unset;
- no R38/DDR run-bound authorization file existed.

Accordingly, the external-master self-loop and all later hardware stages are:

`SKIP_WITH_REASON=RF_COMM_HW_AUTH_UNSET_AND_NEW_RUN_BOUND_AUTHORIZATION_ABSENT`

The earliest next diagnostic stage is the original Case B external-master prestart self-loop under a new run ID. R34, R35, R36, and R37 remain immutable and must not be rerun, resumed, or reused. The entries in `pending_external_master_matrix.json` are plans only; none is a hardware run or acceptance evidence.

## Content-addressed artifact materialization

After the first complete-suite invocation exposed missing ignored binary inputs in this linked worktree, six exact Stage 62/P6 inputs were copied read-only from the ended Stage 62 worktree at commit `53571e305846f89bf3da8c146f5a07bdb003f606`. Every source was checked for exact size and SHA256 before copy; every destination was required to be absent and was rehashed after copy. No source file was modified and no build or hardware action occurred.

The materialized inputs are the P6 JTAG bitstream, P6 PS bitstream, XSA, Stage 62 ELF, generated `ps7_init.tcl`, and canonical shutdown bitstream. Their machine-readable provenance is in `artifact_materialization.json`.

The only two failures from the one complete-suite invocation were then rerun by exact test name, not by repeating either complete suite. Both passed:

- `test_p6_jtag_candidate_binds_axi4_bursts_through_axi4lite_converter`;
- `test_real_r1_through_r31_hardware_epochs_validate_and_failed_stage_tamper_fails_closed`.

The immutable original complete-suite summary remains `FAIL` and is not rewritten. Combined evidence now shows 186 passing tests in that invocation plus exact focused PASS evidence for its two environment-dependent failures, with source commit unchanged. This is an offline remediation checkpoint, not hardware or formal acceptance.
