# RF_COMM G0 Current Failure Baseline

Generated: 2026-06-26

Purpose: freeze the current failing baseline for G0 step 1 before making any
G0 recovery changes.

This file is evidence only. It does not modify RTL, XDC, block design, PS
software, host software, bitstreams, or `项目约束(目标）.txt`.

## Target Scope

- Stage target source: `C:/Users/user/Downloads/G0_G1_targets.md`
- Stage target SHA256: `C80508F7FB20DAB14374AD5FAE4D7F90DDF6D49DF032A985FADC4D58595CF5D0`
- Hard project constraint SHA256: `CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11`
- Active near-term scope: G0, lane0 single-lane hardware closed loop
- Out of G0 scope: lane1, 2 lane, 4/8 lane, rotation, DHCP/TCP full acceptance, long soak

Current safety constraint still applies: TFDU small boards must not be driven
continuously for more than 5 minutes per physical experiment, and shutdown
bitstream must be programmed after each physical run.

## Active Artifact Set

| item | path | SHA256 |
| --- | --- | --- |
| bitstream | `TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.bit` | `96963E740D9B115C0E60A89B355C9EB775716F2DE06E30C0EB6048DF441DAA5B` |
| LTX | `TFDU_VFIR_Client_Array/TFDU_VFIR_Client.runs/impl_1/design_shiboqi_wrapper.ltx` | `32805D7AE4FDFB411F74E821A6CCF99702C879E825318548224640062F18913C` |
| XSA | `TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa` | `E7A137FA96507C1E1A3290B1A548711E4F560E68834FF490588946B8FFA3D17F` |
| BOOT.BIN | `software/_boot/BOOT.BIN` | `4C753690E35F5D3ED2F611E3D83602BF4A94CE260E34FBF241F24378BBF7C30D` |
| PS-PS loopback ELF | `software/_vitis_ws_ps_ps_loopback/rf_comm_ps_ps_loopback/Debug/rf_comm_ps_ps_loopback.elf` | `1D4F85F65328C00143EBD5A10E823CB58D2201543171C2842B343A9DCB6FB027` |
| shutdown bitstream | `shutdown_bitstream/tfdu_shutdown_j10_j11.bit` | `F72680DD3EDA852E64F0B844F54D372368FDB3BDEB775B75507623E6DC167765` |

Active artifact guard evidence:

- `reports/active_artifact_guard_current_20260626.md`
- Stage: `P1_2LANE_ILA_BASELINE`
- Result: `PASS`

Important interpretation: the current active image is a 2-lane ILA baseline,
not a dedicated G0 lane0-only acceptance image.

## Test Script Set

| script | SHA256 |
| --- | --- |
| `tools/run_2lane_hw_prearmed_ila_safe.ps1` | `31B704E166EDA4DDF034656167F794D243A4A84C6E886FC43A8FB34733F69C7B` |
| `tools/run_2lane_matrix_safe.ps1` | `D89F63A164A4E2D527E04E6965140BDE72BC8847EAA5E0D49E7E39ECCC0F6C88` |
| `tools/run_p1_lane_mapping_matrix_safe.ps1` | `6CFD4F4C957E21D5805F7FD50C0569B4821C6F6395179E8648B69F99A6CAFA16` |
| `tools/analyze_2lane_ila_csv.py` | `F43338052BE75347F937FCFF67908B7CA33E1E1A394402850483BBBA4DAFF6F0` |
| `tools/check_active_artifact_stage.py` | `F3D4CC6B1AF1E2B3DD2EBDADD77D0B6D184D8405A0EE484AA00D8B0190F5DEA4` |

## Build / Run Identity

- Git repository: not present (`git rev-parse` reports not a git repository).
- Latest current project gate: `reports/project_gates_2lane_stream_bidir_ila_20260626_024119.meta.txt`
- Project gate result: `PROJECT_GATES_2LANE_ILA_EXIT code=0`
- Vivado version in use: 2023.1
- JTAG preflight: pass, latest evidence includes `HW_PREFLIGHT_ZYNQ xc7z010_1`

## Current Configuration Snapshot

Derived from `config_diff_known_good_vs_current.md` and latest hardware logs.

| field | current failing / active value |
| --- | --- |
| lane under G0 target | `lane0` |
| latest lane mask in failing UART run | `0x00000001` |
| latest session in failing UART run | `0x2201` for 2026-06-26 P1 lane0 raw run |
| current build family | 2-lane stream/bidir ILA baseline |
| `CNT_CHIP_MAX` | current config comparison lists `31` for current failing configs |
| `CNT_PREAMBLE` | `64` |
| `RX_DETECT_WINDOW` | `0..10` in current failing configs |
| `RX_DATA_PHASE_DELAY_CYCLES` | `0` |
| `IR_B_RX_LANE_MASK` | current config comparison lists `3` |
| `IR_B_ACK_LANE_MASK` | current config comparison lists `3` |
| `IR_B_EXPECTED_A_LANE_MASK` | current config comparison lists `3` |

Historical known-good comparison:

- `known-good lane0`: `lane0_hw_loopback_safe_20260605_115655`, `sent=32632`, `rx_ok=32632`, `tx_fail=0`, `loss=0.0%`
- `P0 replay lane0`: `lane0_hw_loopback_safe_20260625_230834`, `sent=11267`, `rx_ok=11267`, `tx_fail=0`, `loss=0.0%`
- Current failing lane0 example in config diff: `lane0_hw_loopback_safe_20260625_161733`, `sent=3212`, `rx_ok=0`, `tx_fail=3212`, `loss=100.0%`, `last_error=tx_retry_exhausted`

## Latest Hardware Evidence

### Lane0 A to B raw pulse evidence

Summary:

- `reports/2lane_prearmed_a_tx_lane0_20260626_114837.summary.txt`
- `reports/ila_2lane_prearmed_a_tx_lane0_20260626_114837.summary.txt`
- `reports/ila_2lane_prearmed_a_tx_lane0_20260626_114837.csv`

Result:

- ILA armed: `ILA_ARMED=1`
- ILA capture done: `ILA2_CAPTURE_DONE`
- CSV size: `633666`
- Script result: `RUN_RESULT_STATUS=PASS`
- Hardware window to shutdown end: `55.4 s`
- Shutdown: `SHUTDOWN_EXIT_INFERRED=0`

UART protocol result from the same run:

```text
PSPS_STAGE_SUMMARY stage=lane-mask mask=0x00000001 sent=2234 rx_ok=0 tx_fail=2234
loss=100.0% win_rx_mbps=0.000 rx_good=0x00000000 rx_crc=0x00000000
rx_err=0xD2000000 phy0=0xEC000000 last_error=tx_retry_exhausted
```

Interpretation:

- Raw A to B lane0 pulse activity exists.
- G0 closed loop is not proven because `rx_ok=0`, `tx_fail=2234`, and `loss=100%`.
- ACK/return path is not proven.

### Lane1 failure observed during prior P1 work

This is out of G0 scope but explains why the project is being narrowed to G0:

- `reports/2lane_prearmed_a_tx_lane1_20260626_115218.summary.txt`
- `RUN_RESULT_STATUS=FAIL_ILA_TIMEOUT`
- `RUN_EXIT_CODE=3`
- `ILA_CSV_MISSING=1`
- `HW_WINDOW_TO_SHUTDOWN_END_SECONDS=138.5`
- `SHUTDOWN_EXIT_INFERRED=0`

## Current Failure Phenomenon

The current active artifact can generate raw lane0 activity, but the protocol
closed loop fails:

- `rx_ok=0`
- `tx_fail` grows with `sent`
- `loss=100%`
- `last_error=tx_retry_exhausted`
- `rx_good=0`
- `rx_err` is non-zero (`0xD2000000` in latest lane0 run)
- no evidence yet of valid DATA-to-ACK sequence correspondence
- no evidence yet of lane0 B to A closed loop in the current active image

G0 acceptance is therefore not satisfied.

## Suspect Areas to Isolate Next

The evidence points to a protocol/RX/ACK classification problem rather than a
simple JTAG access failure.

Priority suspects:

1. RX stage failure after raw pulse arrival: preamble, symbol decode, CRC, frame/header/session/seq, or mask.
2. ACK path not enabled or not selected for the current endpoint/mask/session.
3. Current 2-lane/bidir configuration leaking into the intended G0 lane0-only test.
4. Timing/config regression relative to known-good lane0 (`CNT_CHIP_MAX`, detect window, B endpoint mode, session/mask).

## G0 Next Command Direction

Do not proceed to G1, 2-lane protocol restore, PC-to-PC, DHCP/TCP, rotation, or
long soak from this baseline.

Next aligned work:

1. Replay the historical lane0 known-good configuration with fresh hashes and logs.
2. If replay passes, compare current active config against the replay one variable at a time.
3. If replay fails, treat hardware/TFDU/pose/power as the primary suspect.
4. Build or select a G0 RX-only microscope image for lane0 A to B and B to A.
5. Only after `rx_good>0` is stable, run an ACK-only lane0 build.

G0 acceptance remains:

```text
lane0 A->B: >= 10,000 packets, tx_fail=0, unrecovered loss=0
lane0 B->A: >= 10,000 packets, tx_fail=0, unrecovered loss=0
ACK visible and matched to DATA seq
all evidence traceable to one bit/elf/script set
```
