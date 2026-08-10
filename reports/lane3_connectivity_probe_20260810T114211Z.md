# Lane 3 connectivity result — P10.5 blocking recheck

`LANE3_CONNECTIVITY_RESULT=FAIL`

- Evidence level: `RAW_AB_BA` from the exact four-lane P10.5 artifact
- Requested physical lane: lane3 (`F3=B0020`, `R3=B0025`)
- Run: `p10_5_20260810T114211Z_e1f8c01a_4015142e_79607d01`
- Fixed bitstream SHA256: `4015142eb2a009d7924103b38c8b7fe61649d7da13c6ae354dff510438e3619d`
- Rotating bitstream SHA256: `79607d0190d12c6160e0ff2d937a5ae0a8e208a85d0b5bd3f6f975de35b23205`

## Direction result

`R3_TO_F3_RAW=FAIL_NO_RX_ACTIVITY`

R3 produced 284,852 physical TX counts while F3 recorded zero raw RX counts. A simultaneous control direction proved the test was live: F0 produced 284,280 physical TX counts and R0 recorded exactly 284,280 raw RX counts. Both endpoints ultimately reported retry exhaustion (`0x50090004`).

The immediately preceding independent run also recorded R3 TX `427,200` and F3 raw RX `0`, while its opposite `F3 -> R3` direction had matched TX/RX counts of `12,847,821`. The repeated asymmetry therefore blocks a bidirectional lane3 PASS.

## Safety and waveform boundary

The TX pin emits active-high 4-PPM pulses and the receiving FPGA observes the TFDU active-low `Rxd`. No duty, continuous-high, stuck-high, CRC/SHA, or DMA-leak fault was observed. This is direct FPGA-visible digital evidence for the exact artifact and stationary setup; it is not an external electrical/optical measurement and does not identify the physical component at fault.

## Shutdown

Both boards passed shutdown-before and shutdown-after. Final markers are `SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, and `SHUTDOWN_EXIT=0`.

The immutable run summary SHA256 is `4a743564d96dcb96539d63b4979cb1f45c765089aadca3b269160fc3d59288eb`; the run evidence manifest SHA256 is `eac07f95cfb8f73e2c1231498257a5af7c534debfef69dfc5aea69814bbefb2a`.
