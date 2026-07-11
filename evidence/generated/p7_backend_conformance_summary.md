# P7 Backend Conformance

generated_at_utc: 2026-07-11T16:58:56+00:00
P7_BACKEND_CONFORMANCE: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Details

- command: C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe -m unittest discover -s tests/p7 -p test_*.py -v
- returncode: 0
- test_output_tail: er_rejected (test_p7_application.ProtocolTests.test_out_of_order_rejected) ... ok
test_pattern_matrix (test_p7_application.ProtocolTests.test_pattern_matrix) ... ok
test_size_matrix (test_p7_application.ProtocolTests.test_size_matrix) ... ok
test_stale_session_rejected (test_p7_application.ProtocolTests.test_stale_session_rejected) ... ok
test_completed_descriptor_integrity (test_p7_application.PsMailboxCodecTests.test_completed_descriptor_integrity) ... ok
test_completed_descriptor_rejects_safety_and_lane_mismatch (test_p7_application.PsMailboxCodecTests.test_completed_descriptor_rejects_safety_and_lane_mismatch) ... ok
test_completed_descriptor_rejects_stale_identity_and_sequence (test_p7_application.PsMailboxCodecTests.test_completed_descriptor_rejects_stale_identity_and_sequence) ... ok
test_descriptor_ready_is_a_separate_last_publication (test_p7_application.PsMailboxCodecTests.test_descriptor_ready_is_a_separate_last_publication) ... ok
test_descriptor_roundtrip (test_p7_application.PsMailboxCodecTests.test_descriptor_roundtrip) ... ok
test_invalid_ps_ranges_rejected (test_p7_application.PsMailboxCodecTests.test_invalid_ps_ranges_rejected) ... ok
test_mailbox_codec (test_p7_application.PsMailboxCodecTests.test_mailbox_codec) ... ok
test_mailbox_runtime_bounds (test_p7_application.PsMailboxCodecTests.test_mailbox_runtime_bounds) ... ok
test_runtime_elapsed_seqlock_rejects_rollover_tears_and_regression (test_p7_application.PsMailboxCodecTests.test_runtime_elapsed_seqlock_rejects_rollover_tears_and_regression) ... ok
test_terminal_snapshot_rejects_torn_reads (test_p7_application.PsMailboxCodecTests.test_terminal_snapshot_rejects_torn_reads) ... ok
test_trace_geometry_overlap_and_end_boundary (test_p7_application.PsMailboxCodecTests.test_trace_geometry_overlap_and_end_boundary) ... ok
test_uint32_identity_boundaries (test_p7_application.PsMailboxCodecTests.test_uint32_identity_boundaries) ... ok
test_abort_and_restart_new_epoch (test_p7_application.TransportTests.test_abort_and_restart_new_epoch) ... ok
test_atomic_file_commit (test_p7_application.TransportTests.test_atomic_file_commit) ... ok
test_backend_conformance (test_p7_application.TransportTests.test_backend_conformance) ... ok
test_both_lanes_unavailable_bounded_failure (test_p7_application.TransportTests.test_both_lanes_unavailable_bounded_failure) ... ok
test_lane_fallback (test_p7_application.TransportTests.test_lane_fallback) ... ok
test_queue_backpressure_and_order (test_p7_application.TransportTests.test_queue_backpressure_and_order) ... ok
test_replication_semantics (test_p7_application.TransportTests.test_replication_semantics) ... ok
test_tcp_stub_cannot_open (test_p7_application.TransportTests.test_tcp_stub_cannot_open) ... ok
test_embedded_self_test (test_p7_jtag_backend.P7JtagBackendTests.test_embedded_self_test) ... ok
test_error_counter_and_rx_corruption_are_rejected (test_p7_jtag_backend.P7JtagBackendTests.test_error_counter_and_rx_corruption_are_rejected) ... ok
test_large_object_operation_formula_and_limits (test_p7_jtag_backend.P7JtagBackendTests.test_large_object_operation_formula_and_limits) ... ok
test_memory_mock_roundtrip_sizes_and_lane_policies (test_p7_jtag_backend.P7JtagBackendTests.test_memory_mock_roundtrip_sizes_and_lane_policies) ... ok
test_missing_and_duplicate_raw_keys_are_rejected_atomically (test_p7_jtag_backend.P7JtagBackendTests.test_missing_and_duplicate_raw_keys_are_rejected_atomically) ... ok
test_real_r5_clear_scoped_raw_pulse_evidence_parses (test_p7_jtag_backend.P7JtagBackendTests.test_real_r5_clear_scoped_raw_pulse_evidence_parses) ... ok
test_real_r8_retry_evidence_parses (test_p7_jtag_backend.P7JtagBackendTests.test_real_r8_retry_evidence_parses) ... ok
test_retry_delta_allows_duplicate_valid_frames_and_is_bounded (test_p7_jtag_backend.P7JtagBackendTests.test_retry_delta_allows_duplicate_valid_frames_and_is_bounded) ... ok

----------------------------------------------------------------------
Ran 39 tests in 1.329s

OK

- sizes_include_0_to_1MiB: True
- negative_cases_present: True
- backends: ["local_stub", "mock_jtag_axi", "mock_ps_mailbox", "tcp_stub_disabled"]
