# P10.3 stationary four-lane hardware closeout

- Status: `PASS`
- Run ID: `p10_3f_full_20260805T065127Z_e356dd92_1ff0885f_82ef5093`
- Evidence commit: `e64c04843d5d996f8d66d650fafaf3a43a2dd7dc`
- Planned PASS tag: `p10.3-ax7020-stationary-4lane-pass`
- Stages: `23/23 PASS`
- Direct observations: `457`
- F→R / R→F application goodput: `8416570.026666667` / `8444532.053333333` bit/s
- Formal runtime: `1800.011` s
- Formal committed bytes F→R / R→F: `921698304` / `926941184`
- Fixed / rotating shutdown: `PASS` / `PASS`
- Current-run hardware authorization: `false` (consumed)
- Network / movement / rotation / realignment / rewiring: `false`

Campaign-wide CRC-bad, deadlock and transport-timeout counters came only from controlled fault-injection stages; the formal stage itself passed its zero-error checks. No such diagnostic counter is reclassified as an unexpected acceptance failure.

External power/duty instrumentation was omitted by user instruction, so external electrical/duty acceptance remains pending. This PASS does not promote P11, 8×32, 600 rpm, or product-final acceptance.
