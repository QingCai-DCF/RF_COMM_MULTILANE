# P10.2 crosstalk and 1+1 plan

Status: `OFFLINE_DEFINITION_ONLY`

No P10.2 hardware action is authorized. The canonical matrix is
`config/p10_2_crosstalk_matrix.yaml`.

The future 4×4 campaign excites each of `TX_F0`, `TX_F1`, `TX_R0`, and
`TX_R1` separately while recording all of `RX_F0`, `RX_F1`, `RX_R0`, and
`RX_R1`. Each cell records raw edges, normalized pulses, false preambles,
false frames, CRC-valid false frames, local/remote ratio, and cross-lane
ratio. The raw counts, window, detector thresholds, artifacts, board roles,
lane mask, and optical geometry must be frozen before execution.

The separate 1+1 case uses lane0 for F0→R0 and lane1 for R1→F1. It is a
two-direction experiment and must not be described as final 4+4 full duplex.
CRC/SHA/SACK, bounded retry, frame admission, the exact per-module rolling
duty guard, the one local active-high `GLOBAL_PERMIT` per endpoint, and
shutdown handling remain mandatory and unchanged.
