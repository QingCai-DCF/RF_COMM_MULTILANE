# P6 PS Runtime Recovered Failure Package

P6_FAILURE_PACKAGE: RECOVERED_XSDB_TARGET_ALIAS

- stage: `ps_driver_runtime`
- root cause: XSDB exposed `APU`, both Cortex-A9 cores, and `xc7z010`, but no `DAP` alias
- the failure occurred before programming the P6 candidate or starting TFDU transport
- shutdown bitstream was programmed both before and after the failed stage
- SHUTDOWN_EXIT: `0`
- fix: use the equivalent APU system-reset target when the optional DAP alias is absent
- this package is historical recovered evidence and must not replace a fresh PS mailbox runtime PASS
