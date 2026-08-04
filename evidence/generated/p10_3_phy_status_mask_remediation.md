# P10.3 PHY status mask remediation

Status: **PASS (offline runner/evaluator remediation only)**

The failed run `p10_3_20260804T100428Z_d4eef729_3d8cd207_a8459eef` did not establish an R2-to-F2 connectivity result. It passed the F2-to-R2 64- and 1024-pulse cases, then stopped before launching R2 because the XSDB runner misread normal fixed-endpoint startup as a safety fault. Both endpoint shutdowns passed.

`P9_PHY_STATUS` packs three fields of width `2*LANE_COUNT` as `{safety, startup, ready}`. The old literal `0x00000F00` is the safety field only for two lanes. With four lanes it overlaps startup bits; the four-lane safety field is `0x00FF0000`. The XSDB guard and Python mailbox evaluator now derive the field from the current lane count and still fail closed on the actual safety bits.

Verification completed without hardware:

- 20 focused P10/P10.3 unit tests: PASS
- Python compilation: PASS
- no-hardware-action check: PASS
- frozen bitstream/XSA/BSP/ELF bundle: unchanged

Machine-readable record: `evidence/generated/p10_3_phy_status_mask_remediation.json`.
