# Campaign C2 closure and C2-08 failure analysis

Status: `STOPPED_SAFETY_FAILURE_RECOVERED`  
Hardware acceptance: `PENDING_HW`  
Source commit: `a7bc060aa29f15815891af463b1f7ff1d600cb31`

Campaign C2 stopped after C2-08. C2-01 through C2-07 passed their bounded diagnostic checks and their primary shutdown-after barriers. C2-08 attempted formal Stage 62, exceeded the 1020-second XSDB process bound while harvesting evidence, and then failed its primary shutdown-after because the terminated XSDB transaction still held the cable. C2-09 and C2-10 were correctly not started and their unused authorization files are invalidated.

A separate bounded recovery-only action programmed the fixed shutdown image and reached `SHUTDOWN_EXIT=0`. Its retained evidence shows `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1` and `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`; the post-recovery runner, XSDB, Vivado, temporary `cs_server`, and runner lock checks were clear.

## Results retained

- C2-01 and C2-02: original Stage 62 fixture through the external master, zero readback mismatches.
- C2-03: isolated Case C, 29 bytes, `COPY_OK`, output wipe verified.
- C2-04: `A5 5A 3C C3` external-master pattern, zero readback mismatches.
- C2-05: nonzero-counter external-master pattern, zero readback mismatches.
- C2-06: isolated Case D, 31 bytes, `COPY_OK`, output wipe verified.
- C2-07: isolated Case B, 32 bytes, `COPY_OK`, output wipe verified.
- C2-08: formal Stage 62 attempted but not completed; no acceptance credit.
- C2-09 and C2-10: not started and invalidated by the campaign stop rule.

## Correct Stage 62 scope

`--stage62-only` selects formal sequence ordinal 62, `ps_functional`. Its boundary48, 4 KiB, four 64 KiB, and four 1 MiB phases are the internal vectors required by that one formal stage. They are not formal stages 1 through 61 and must not be bypassed. The earlier interpretation that C2-08 ran “pre-Stage62” work was incorrect.

The wrapper field `functional_stages_1_61_executed=false` therefore remains correct as a formal-sequence statement. It does not mean that Stage 62's internal boundary and large-object phases were skipped. C2-08's immutable partial evidence proves that formal Stage 62 was attempted but that its complete evidence and postprocess contract were not finished.

## Exact C2-08 progress

The offline audit decoded the retained binary descriptors and compared every retained output directly with its immutable input:

- all 48 boundary cases are `COMPLETE`, error 0, exact output equality, with complete sequences 1 through 48 and trace files present;
- the 4 KiB checkpoint is `COMPLETE`, error 0, exact output equality, sequence 49;
- all four 64 KiB cases are `COMPLETE`, error 0, exact output equality, sequences 50 through 53;
- the first 1 MiB case descriptor is `COMPLETE`, error 0, 4,878 fragments, sequence 54, and its descriptor-published output SHA256 equals the immutable input SHA256;
- the first 1 MiB object took 14,250,015,258 PS ticks, approximately 42.750 seconds;
- the host-side 1 MiB output file never completed before the parent killed XSDB 391.503 seconds after that terminal descriptor was retained.

The detailed hash-bound record is [C2_08_PARTIAL_EVIDENCE_AUDIT.json](C2_08_PARTIAL_EVIDENCE_AUDIT.json). This partial progress is diagnostic evidence only and cannot satisfy Stage 62.

## Root cause

The old evidence path called:

```text
mrd -size b -bin -file <path> <address> <byte_count>
```

XSDB's final argument counts values. In C2-08, each 64 KiB output read took about 33 seconds and each 19,520-byte trace read took about 10 seconds. Those retained timings imply roughly 527 seconds for a 1 MiB byte-valued output read plus 158 seconds for its 312,192-byte trace. The first 1 MiB firmware object had already completed; the bounded parent expired during the host evidence read.

Classification: `BYTE_WIDE_LARGE_EVIDENCE_HARVEST_EXCEEDED_BOUNDED_OUTER_WINDOW`.

AMD UG1400 documents `mrd` value-count semantics, byte/half-word/word/double-word sizes, and that a target without native double-word access uses two word accesses: <https://docs.amd.com/r/2022.2-English/ug1400-vitis-embedded/mrd>.

## Minimal fix

The fix preserves the complete internal Stage 62 matrix and the existing 900-second service limit, 1020-second candidate bound, authorization validator, expected bytes, CRC/SHA checks, traces, guard checks, and parser acceptance rules:

1. Functional main-case input/output/trace preloads are deferred to their actual 64 KiB and 1 MiB phases, removing 10,239,744 bytes of duplicate initial JTAG downloads.
2. Aligned evidence blocks of at least 4 KiB use double-word binary `mrd`, reducing the value count by eight. Small or unaligned evidence retains the byte path.
3. Before the 4 KiB descriptor is published, an immutable 4 KiB input must round-trip byte-exact through the double-word read path. Any size/order/tool incompatibility fails closed before the risk increases.
4. After all four 1 MiB descriptors are terminal, the host commands and verifies clean PS service/TFDU driver shutdown before collecting the large immutable output and trace files.
5. The postprocessor requires fresh phase-local-preload, double-word-probe, pre-evidence-shutdown, and evidence-mode markers.
6. A timeout's stdout/partial markers may conservatively prove that candidate programming or ELF download happened, but can never substitute for the atomic final result or promote PASS.

A timing estimate based only on C2-08's retained measurements is approximately 783 seconds against the unchanged 1020-second candidate bound. That estimate is not acceptance evidence; only a newly authorized run with a new run ID can validate the fix.

## Required next step

Keep hardware stopped. Complete focused and canonical offline validation, freeze every changed runner/Tcl/parser/configuration hash, and generate a new run-specific authorization-preparation package. Any hardware retry requires new run IDs, new hash-bound authorization, a fresh live safety gate, and shutdown/recovery. C2-08, C2-09, and C2-10 must not be reused.
