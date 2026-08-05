# P10.3 Stationary Four-Lane Closeout

```text
P10_3_CLOSEOUT: PASS
P10_3_EVIDENCE_COMMIT: e64c04843d5d996f8d66d650fafaf3a43a2dd7dc
P10_3_FINAL_CHECKPOINT: e647f066bbba8b36660e5f0bc43c79adc872c4c0
P10_3_PASS_TAG: p10.3-ax7020-stationary-4lane-pass
P10_3_PASS_TAG_TARGET: e647f066bbba8b36660e5f0bc43c79adc872c4c0
P10_3_CLOSED_TAG: p10.3-ax7020-stationary-4lane-closed
FORMAL_RUN_ID: p10_3f_full_20260805T065127Z_e356dd92_1ff0885f_82ef5093
STAGES: 23/23 PASS
DIRECT_OBSERVATIONS: 457
FORMAL_RUNTIME_SECONDS: 1800.011
SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
AUTHORIZATION_CONSUMED: true
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
HARDWARE_ACTIONS_EXECUTED_DURING_CLOSEOUT: false
```

The immutable P10.3 PASS tag remains unchanged. The closeout binds the fixed board
`AX7020-F/JTAG:210249855178`, the rotating-role board
`AX7020-R/JTAG:210512180081`, all eight active module IDs, the actual wiring,
the fixed and rotating shutdown/functional/XSA/BSP/ELF hashes, and the complete
3,900-file run manifest.

External four-lane power and TFDU duty acceptance remain `PENDING_NOT_IN_SCOPE`.
P11, 8×32, 600 rpm, Ethernet/SPI and product-final acceptance are not promoted.
