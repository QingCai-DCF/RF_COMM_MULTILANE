# P10.1 64 MiB streaming and recovery

- Status: `FAIL`
- Test ID: `P10_1-HW-STREAMING-64M-RECOVERY`
- Hardware actions executed: `true`
- Current-run hardware authorization: `false`

## Errors

- streaming stage summary is missing
- XSDB PASS marker missing
- observation count 6 is below minimum 19
- immutable plan case missing: dma_reset_receiver_f_to_r_64m
- immutable plan case missing: post_dma_receiver_clean_f_to_r_64m
- immutable plan case missing: pl_reset_r_to_f_64m
- immutable plan case missing: post_pl_reset_clean_r_to_f_64m
- immutable plan case missing: duplicate_segment_f_to_r_64m
- immutable plan case missing: post_duplicate_clean_f_to_r_64m
- immutable plan case missing: stale_segment_r_to_f_64m
- immutable plan case missing: post_stale_clean_r_to_f_64m
- immutable plan case missing: post_sender_ps_reset_clean_f_to_r_64m
- immutable plan case missing: post_receiver_ps_reset_clean_f_to_r_64m
- immutable plan case missing: sender_ps_service_reset_f_to_r
- immutable plan case missing: receiver_ps_service_reset_f_to_r
- exactly one final endpoint shutdown row is required
- post_dma_reset_clean_f_to_r_64m:fixed:service_state
- post_dma_reset_clean_f_to_r_64m:fixed:status
- post_dma_reset_clean_f_to_r_64m:fixed:timer_firmware
- post_dma_reset_clean_f_to_r_64m:fixed:timer_host_recomputed
- post_dma_reset_clean_f_to_r_64m:fixed:accepted
- post_dma_reset_clean_f_to_r_64m:fixed:committed
- post_dma_reset_clean_f_to_r_64m:fixed:single_atomic_commit
- post_dma_reset_clean_f_to_r_64m:fixed:remote_commit
- post_dma_reset_clean_f_to_r_64m:fixed:objects
- post_dma_reset_clean_f_to_r_64m:fixed:descriptors
- post_dma_reset_clean_f_to_r_64m:rotating:service_state
- post_dma_reset_clean_f_to_r_64m:rotating:status
- post_dma_reset_clean_f_to_r_64m:rotating:timer_firmware
- post_dma_reset_clean_f_to_r_64m:rotating:timer_host_recomputed
- post_dma_reset_clean_f_to_r_64m:rotating:accepted
- post_dma_reset_clean_f_to_r_64m:rotating:committed
- post_dma_reset_clean_f_to_r_64m:rotating:single_atomic_commit
- post_dma_reset_clean_f_to_r_64m:rotating:remote_commit
- post_dma_reset_clean_f_to_r_64m:rotating:objects
- post_dma_reset_clean_f_to_r_64m:rotating:descriptors
- post_dma_reset_clean_f_to_r_64m: physical wire bytes do not exceed application payload
- post_dma_reset_clean_f_to_r_64m:sender:pl_application_accepted
- post_dma_reset_clean_f_to_r_64m:sender:pl_tx_object_packets
- post_dma_reset_clean_f_to_r_64m:receiver:pl_application_committed
- post_dma_reset_clean_f_to_r_64m:receiver:pl_frame_acked_payload
- post_dma_reset_clean_f_to_r_64m:receiver:pl_rx_object_packets
- fault/recovery vector count mismatch
- post-recovery clean-vector count mismatch

## Machine-readable evidence

`evidence/generated/p10_1_hw_streaming_64m_summary.json`
