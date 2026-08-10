# Lane 3 connectivity result — P10.5 run 111841

`LANE3_CONNECTIVITY_RESULT=FAIL`

- Evidence level: `RAW_AB_BA` from the lane-matching four-lane P10.5 artifact
- Physical lane: lane3 (`F3=B0020`, `R3=B0025`)
- Fixed bitstream SHA256: `4015142eb2a009d7924103b38c8b7fe61649d7da13c6ae354dff510438e3619d`
- Rotating bitstream SHA256: `79607d0190d12c6160e0ff2d937a5ae0a8e208a85d0b5bd3f6f975de35b23205`
- Run: `p10_5_20260810T111841Z_e1f8c01a_4015142e_79607d01`

## Direction results

- `F3_TO_R3_RAW=PASS_RAW_PHYSICAL_ONLY`: F3 physical TX count `12,847,821`; R3 raw RX count `12,847,821`.
- `R3_TO_F3_RAW=FAIL_NO_RX_ACTIVITY`: R3 physical TX count `427,200`; F3 raw RX count `0`.

The failed reverse direction caused both protocol endpoints to exhaust retries (`0x50090004`). The frozen transport states retained 31 fixed-side and 17 rotating-side outstanding frames. No safety, rolling-duty, continuous-high, CRC/SHA, or DMA-leak error was recorded.

## Waveform and verdict boundary

The tested TX pin emits active-high 4-PPM pulses; the receiving FPGA input treats the TFDU `Rxd` signal as active-low. Each symbol selects one of four pulse positions. This report establishes only stationary, artifact-matched raw physical activity at the FPGA-visible pins. It does not constitute an external electrical/optical measurement or permanent module-failure diagnosis.

## Shutdown

`SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`.

Raw evidence is under `evidence/hardware/p10_5/p10_5_20260810T111841Z_e1f8c01a_4015142e_79607d01/` and its manifest SHA256 is `c00138ab94fcee802ec66a05b3d2bb62a88abcb6735bd81fa58a3e3a6b2fd8f1`.
