# BAD_DIR Parameter Sweep Summary

Generated: 2026-06-28T01:52:46+08:00

Status: `OPTIONAL_MICROSCOPE_FOR_AB_L1`

The constrained lane0-only baseline no longer needs an ACK protocol fix. A small sweep or microscope pass can still be used to diagnose `AB_L1`, but it should not be mixed into the accepted lane0 degraded configuration.

Suggested sweep remains:

| parameter | values |
| --- | --- |
| detect window | 0..5, 0..7, 0..10 |
| preamble realign | 0, 1 |
| retry | 12 |
| payload | 64B, 256B |
| fragment | 64B |

```text
RF_COMM_BAD_DIR_PARAM_SWEEP status=OPTIONAL_MICROSCOPE_FOR_AB_L1
BAD_DIR_FINAL=AB_L1
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
