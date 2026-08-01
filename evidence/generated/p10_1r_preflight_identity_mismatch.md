# P10.1R preflight identity mismatch

Status: `FAIL_CLOSED`

Run ID: `p10_1r_20260801T184156Z_493955d5_080a35e6_18287e66`

Both boards were uniquely bound and the frozen functional bitstreams were programmed. Preflight then rejected the fixed endpoint before either ELF was downloaded or any protocol case ran: the observed P10.1R PL build ID was `0x50315246`, while the XSDB executor still required the older P10 value `0x50313046`.

Source inspection also found the same stale values in the role-bound PS firmware (`0x50313046` / `0x50313052`), while the RTL defines `0x50315246` / `0x50315252`. The next run therefore requires corrected host and firmware identity checks plus newly frozen ELF artifacts; this failed run is not reusable.

All initial, stage-before, stage-after, and finally shutdown attempts reported `SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, and `SHUTDOWN_EXIT=0`.

The adjacent JSON is the authoritative machine-readable diagnosis and binds the immutable raw evidence hashes.
