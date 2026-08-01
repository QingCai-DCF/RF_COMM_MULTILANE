# P10.1 bounded adaptive tuning

- Status: `FAIL`
- Test ID: `P10_1-HW-ADAPTIVE-TUNING`
- Hardware actions executed: `true`
- Current-run hardware authorization: `false`

## Errors

- XSDB PASS marker missing
- observation count 7 is below minimum 11
- immutable plan case missing: tune_batch4
- immutable plan case missing: tune_batch8
- immutable plan case missing: tune_batch16
- exactly one final endpoint shutdown row is required
- tune_batch1:fixed:service_state
- tune_batch1:fixed:status
- tune_batch1:fixed:timer_firmware
- tune_batch1:fixed:timer_host_recomputed
- tune_batch1:fixed:accepted
- tune_batch1:fixed:committed
- tune_batch1:fixed:single_atomic_commit
- tune_batch1:fixed:remote_commit
- tune_batch1:fixed:objects
- tune_batch1:fixed:descriptors
- tune_batch1:rotating:service_state
- tune_batch1:rotating:status
- tune_batch1:rotating:timer_firmware
- tune_batch1:rotating:timer_host_recomputed
- tune_batch1:rotating:accepted
- tune_batch1:rotating:committed
- tune_batch1:rotating:single_atomic_commit
- tune_batch1:rotating:remote_commit
- tune_batch1:rotating:objects
- tune_batch1:rotating:descriptors
- tune_batch1: physical wire bytes do not exceed application payload
- tune_batch1:sender:pl_application_accepted
- tune_batch1:sender:pl_tx_object_packets
- tune_batch1:receiver:pl_application_committed
- tune_batch1:receiver:pl_frame_acked_payload
- tune_batch1:receiver:pl_rx_object_packets

## Machine-readable evidence

`evidence/generated/p10_1_hw_tuning_summary.json`
