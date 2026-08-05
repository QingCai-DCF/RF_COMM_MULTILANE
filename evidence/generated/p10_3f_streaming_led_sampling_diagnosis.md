# P10.3F streaming PS-LED sampling diagnosis

- Result: `HOST_EVALUATOR_FALSE_NEGATIVE`
- Preserved run: `p10_3f_full_20260805T010748Z_f07b6932_1ff0885f_82ef5093`
- Original run/stage status remains: `FAIL`
- Final shutdown: fixed `PASS`, rotating `PASS`

The hardware ledger proves that the failure was in the host verdict, not an
absence of PS LED activity. The evaluator inspected only the first
`*_active` row, which is captured as soon as either endpoint enters RUNNING
and can precede sender MM2S activity. Periodic rows with the exact command
label are direct GPIO readbacks during the same sustained command.

For fixed-to-rotating traffic, 59 sender-TX-active and 64 receiver-RX-active
samples were recorded. For rotating-to-fixed traffic, the corresponding
counts were also 59 and 64. All ten 64 MiB aggregate commands and their
per-command safety gates passed in XSDB.

The corrected evaluator accepts only edge-adjacent or periodic samples bound
to the same authorized command label; it still excludes terminal, safe-boot,
and unrelated-command rows. No bitstream, XSA, BSP, or ELF changed. The old
run is not reclassified or promoted: a new immutable host freeze,
current-run authorization, and full campaign are required.

Machine-readable details and exact source hashes are in
`evidence/generated/p10_3f_streaming_led_sampling_diagnosis.json`.
