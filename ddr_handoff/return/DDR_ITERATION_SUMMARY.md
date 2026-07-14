# DDR specialist iteration summary

## From C2 failure to bounded fix

Campaign C2 proved corrected AX7010 PS/DDR operation through exact
external-master self-loops, pattern variants, and isolated Stage 62
microtests. Its first original functional Stage 62 attempt completed all 48
boundary cases, the 4 KiB checkpoint, all four 64 KiB descriptors, and the
first 1 MiB firmware descriptor. The bounded parent expired while the host was
still reading large evidence one byte-valued XSDB item at a time.

The retained C2 evidence therefore isolated the remaining root cause as:

`BYTE_WIDE_LARGE_EVIDENCE_HARVEST_EXCEEDED_BOUNDED_OUTER_WINDOW`

It did not prove a DDR payload failure. Independent recovery after C2
programmed the canonical shutdown image and recorded a successful shutdown.

Commit `6e8043716a6797257bbc46c172c287abed93198d` made the minimal host-side
repair while preserving the complete Stage 62 matrix and all payload,
descriptor, trace, guard, wipe, SHA, CRC, memcmp, and runtime semantics:

1. phase-local functional input preloads;
2. aligned double-word evidence reads;
3. an immutable 4 KiB double-word readback probe;
4. service shutdown before final 1 MiB evidence harvest;
5. fail-closed marker and atomic-result validation;
6. conservative separation of attempted actions from completion/PASS.

## Campaign D execution

After the user manually created and verified the three exact single-run
authorizations, the campaign envelope, all 33 immutable inputs, and live safety
state were revalidated. Runs D-01, D-02, and D-03 then executed serially under
the safe wrapper. Each completed original functional Stage 62 and both
shutdown barriers.

The three-run streak contains:

- 144/144 boundary cases PASS;
- 3/3 4 KiB checkpoints PASS;
- 12/12 64 KiB cases PASS;
- 12/12 1 MiB cases PASS;
- 1,275/1,275 raw evidence hashes exact;
- zero partial evidence files;
- zero payload mismatches or postprocess failures;
- three successful shutdown-after results.

No safety failure, fixed-input hash change, or authorization hash change
occurred. The campaign ended after exactly three runs; no fourth authorization
or run exists.

## Scope and conclusion

Campaign D confirms the Stage 62 evidence-harvest fix on hardware for three
consecutive original vectors. It also preserves the earlier C2 low-level
external-master evidence. This resolves the DDR specialist diagnostic goal and
is ready for main-thread integration.

The direct task constraint prohibited stages 1-61, full stages 1-66, and
stationary. Ethernet and motion were also prohibited. None was run, and none
receives acceptance coverage. The runs remain diagnostic-only and
`HARDWARE_ACCEPTANCE` remains `PENDING_HW`.

Durable closure:
`ddr_debug/campaign_d/CAMPAIGN_D_CLOSURE.json` at evidence commit
`1e6b5185cb1f0bdc2de0f148e715e1c726cb8b5e`.

## Next boundary

The next action is main-thread review and integration of the specialist commit
range after Stage 62 packaging baseline
`53571e305846f89bf3da8c146f5a07bdb003f606`. Do not rerun Campaign D or reuse
its authorizations. Any later formal acceptance campaign is a separate scope
with new run IDs, new authorization, and its own required coverage.
