# P8D-00 baseline offline regression attempt 3

- Result: `PASS`
- Command: `python scripts/run_offline_gates.py --include-p8c --json-summary`
- Runtime: `3600.4 seconds`
- Runner bound: `5400 seconds`
- Results: `33`, with `0` failures and `0` pending tools
- P8B included: `true`, return code `0`
- P8C included: `true`, return code `0`
- Hardware actions executed: `false`

The complete existing P0–P8C offline regression ran with real available
non-hardware tools. The aggregate result was `PASS`; no hardware scope was
evaluated or promoted.

One hundred fourteen generated tracked outputs were copied byte-for-byte under
`tracked_outputs` before restoring the immutable P8C checkpoint artifacts. The
runner removed `evidence/generated/p8c_raw/p0_p8b_full_regression.log`; that
deletion is explicitly recorded here and the checkpoint copy is restored after
preservation.

Key hashes:

- Offline JSON: `9488663acd2adaff6292c15aa792281c1d2269a1e6076631b141aef0654ca84e`
- Offline Markdown: `d2d4edaec634c89b1bc8f3635f086b6c905b961750a50edbdc2f627f753a7358`
- P8C final JSON: `c9b27e493f26ef2053e59811be113674adc47c5bd144eed79213a168dfc0660d`
- P8C final Markdown: `d47f1a7b58ee7a5fc6c28d3c855aa5566ffa2430336498572f35abfe28cc0b0c`
