# Lane 1 connectivity probe — 20260803T062846Z

`LANE1_CONNECTIVITY_RESULT=FAIL`

- Evidence level: `RAW_AB_BA` / `RAW_PHYSICAL_ONLY`
- Physical pairing: `F1-R1`
- F1 to R1: `FAIL` at sample 0; fixed final lane1 TX count `1`, rotating lane1 raw `0`
- R1 to F1: `PASS`, fixed raw `1000/1000`
- Run: `p10_1r_20260803T062846Z_cce2180b_c1370686_bfb1c51d`
- Fixed bitstream SHA256: `c13706860a003721d45e9a6fd90f444825aaa1b342a74a095079eceffa856a27`
- Rotating bitstream SHA256: `bfb1c51d639188ea60392c8ceb39b25276e12b819c8e2ee0c5ae3ef63497639f`
- Fixed ELF SHA256: `0d3963ce7fbcaab95373ebec97f4c62712bd216f041a23547c9006024e219db4`
- Rotating ELF SHA256: `5abf3d3d597b14e182d07665609a8dd8ff05d7c6159fd2deb1f81813723c035e`
- Raw log: `evidence/hardware/p10_1r/p10_1r_20260803T062846Z_cce2180b_c1370686_bfb1c51d/echo_tail/xsdb.result.txt`
- Shutdown: fixed PASS, rotating PASS, `TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`

The probe transmits active-high final-Txd pulses and observes the remote active-low Rxd path after synchronization. The frozen PHY uses 4-PPM symbols (`00=1000`, `01=0100`, `10=0010`, `11=0001`). The one-way negative observation does not identify whether the loss is optical, in the fixed F1 transmitter half, in the rotating R1 receiver half, or in their external electrical path.

Boundary: stationary AX7020 two-lane setup only; no DATA-roundtrip PASS, throughput PASS, Ethernet, motion, rotation, P11, 8x32, or product acceptance.
