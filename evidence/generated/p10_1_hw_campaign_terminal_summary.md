# P10.1 hardware campaign terminal summary

- Status: `FAIL`
- Test ID: `P10_1-HW-FINAL-ACCEPTANCE`
- Hardware actions executed: `true`
- Current-run hardware authorization: `false`

## Errors

- BOARD_AUTONOMOUS_FAST_PATH
- HOST_NOT_IN_FAST_PATH
- F_TO_R_APPLICATION_GOODPUT_4MBPS
- R_TO_F_APPLICATION_GOODPUT_4MBPS
- CROSSTALK_4X4_MATRIX_ACCEPTANCE
- NON_TARGET_CRC_VALID_FALSE_FRAME_ZERO
- STATIONARY_30MIN

## Terminal classification

- Overall acceptance: `FAIL`
- Classification: `FAIL_WITH_PERFORMANCE_EVIDENCE_AND_CROSSTALK_GATE_FAILURE`
- P10 functional acceptance remains preserved; this result is scoped to P10.1 performance/crosstalk.
- P11 hardware readiness remains `false`.

## Direct formal measurements

- F→R active application goodput: `2587436.300287 bit/s`
- R→F active application goodput: `2585671.499189 bit/s`
- Corrected model: `4189709.129514 bit/s`
- F→R measured/model: `0.617569435`
- R→F measured/model: `0.617148212`
- Formal elapsed: `1800.037 s`
- Formal committed bytes per direction: `236978176`
- Integrity/resource/safety counters listed in the machine-readable summary are all zero; maximum Txd high was 16 cycles at 64 MHz (0.25 µs).

## Mandatory failures

- Both formal directions remained below 4.0 Mbit/s.
- Each formal direction used 25 host control commands, failing the frozen host-fast-path exclusion gate.
- The complete 4×4 matrix found 16,984 non-target CRC-valid frames in sender-side same-lane near-end paths; the required value is zero.
- Therefore the stationary 30-minute acceptance is `FAIL`, despite completing the 1800-second window with zero integrity and internal safety violations.

## Preserved passes and nonblocking results

- Baseline, adaptive tuning, sustained pipeline, both 64 MiB streams, nine digital fault/recovery vectors, timer crosscheck, safe boot, and all dual-board shutdowns passed.
- The 1+1 experiment is `SKIP_WITH_REASON`: the frozen endpoint exposes one endpoint-wide direction bit, not independent per-lane directions.
- Optional 128 MiB streaming was not executed and has no PASS claim.

## Evidence binding

- Terminal selection: `evidence/hardware/p10_1/terminal_campaign_selection.json`
- Source commit: `bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1`
- Formal run: `p10_1_hw_20260801T090528Z_bb6ce78a_1585d1ad_9ad4f85f`
- Fixed board: `AX7020-F/JTAG:210249855178`
- Rotating board: `AX7020-R/JTAG:210512180081`
- Hardware authorization is consumed and currently `false`.
- No Ethernet, movement, rotation, obscuration, module exchange, or rewiring was used.

## Machine-readable evidence

`evidence/generated/p10_1_hw_campaign_terminal_summary.json`
