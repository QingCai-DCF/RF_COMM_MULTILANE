# P10.1 tuning candidate qualification

Status: **PASS** for offline qualification and plan correction only. The new
candidate still requires a hardware tuning retry.

Run `p10_1_hw_20260801T031417Z_bfff4836_1585d1ad_9ad4f85f` completed six
tuning candidates and then rejected the composite candidate
`ring8 + batch1 + 64 KiB object`. Both outer shutdown markers are PASS and the
current-run authorization is consumed.

The fixed sender reported P10.1 status `0x104` (`PL_OBJECT`) with PL object
error `0x50090004`, which the RTL defines as TX retry exhaustion. The rotating
receiver reported `0x103` (`DMA_COMPLETION`). Neither endpoint published an
application commit; CRC, SHA, integrity, partial-commit, duplicate-commit and
stale-commit counters all remained zero.

This observation qualifies only that exact composite configuration. It does
not prove that `descriptor_batch=1` is unsupported for every object size or
ring depth.

The replacement `tune_batch1` candidate now changes only one parameter from
the mandatory/default configuration:

- buffer count: 4
- ring depth: 16
- descriptor batch: 1
- object size: 256 KiB
- descriptor size: 64 KiB

The runner SHA256 is
`8d807a0b86444655d74c902cb6db774f5c089d86e389a61e1c72e751de4fdefe`.
No bitstream or ELF changed. A new authorization must bind that runner before
the tuning retry.

Machine-readable evidence is in
`evidence/generated/p10_1_hw_tuning_candidate_qualification.json`.
