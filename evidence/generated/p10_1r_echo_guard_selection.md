# P10.1R echo guard selection

- Status: `PASS`
- Run ID: `p10_1r_20260801T190357Z_38f83531_080a35e6_18287e66`
- Samples: `1000/module`, `4000` total
- Raw same-module echo observations: `4000`
- Accepted same-module frames: `0`
- Maximum observed post-TX echo tail: `0 cycles`
- Deterministic margin: `4096 cycles`
- Selected final post-TX guard: `4096 cycles`
- Separate idle qualification retained: `256 cycles`
- Final dual-board shutdown: `PASS`

The measured same-module activity occurred while physical TX was active; no
post-TX tail was observed in this stationary four-module sample. The selected
guard is therefore the deterministic margin. This calibration bundle is not
acceptance-eligible. A new complete artifact build and full hardware campaign
are required before any P10.1R acceptance claim.

The adjacent JSON is authoritative and binds every raw PSV and summary SHA256.
