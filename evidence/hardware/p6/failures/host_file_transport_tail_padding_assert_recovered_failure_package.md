# P6 Host File Transport Recovered Failure Package

P6_FAILURE_PACKAGE: RECOVERED_TEST_HARNESS_ASSERTION

- stage: `host_file_transport_jtag`
- root cause: the 30-byte case asserted stale, out-of-length padding bytes in the final RX RAM word
- valid payload bytes, CRC, digest, length, both lane counters, ACK, and output file all matched
- CRC_BAD/PAYLOAD_MISMATCH/RETRY_EXHAUSTED/TX_FAIL/DUTY/ERROR/STICKY: `0`
- BEFORE_STAGE_SHUTDOWN_EXIT: `0`
- AFTER_STAGE_SHUTDOWN_EXIT: `0`
- SHUTDOWN_EXIT: `0`
- fix: mask only the unused bytes of the final RX word, then rerun the full four-file stage
- this package is historical recovered evidence and must not be promoted in place of the fresh rerun
