# P7 PS Core Hardware Readiness

P7_PS_CORE_HARDWARE_READINESS: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

- host_command_cache_disabled_or_isolated: PASS
- deadline_frozen_in_private_context: PASS
- active_transfer_obeys_absolute_deadline: PASS
- stop_abort_shutdown_observed_during_active_object: PASS
- shutdown_readback_verified: PASS
- failure_cleanup_shutdown_first: PASS
- failure_wipe_uses_private_validated_range: PASS
- integrity_crc_sha_immutable_chunk_snapshot: PASS
- critical_payload_copies_are_volatile_byte_verified: PASS
- first_error_diagnostic_is_atomic_and_first_only: PASS
- stage62_first_error_prepare_is_first_only: PASS
- first_error_capture_precedes_validation_and_is_input_bound: PASS
- stage62_diagnostic_fixed_ocm_section: PASS
- stage62_copy_four_snapshot_classification: PASS
- stage62_diagnostic_crc_publish_order: PASS
- stage62_only_microtest_bypasses_pl_and_is_disassembly_bound: PASS
- pre_repair_encode_raw_compared_to_fixed_input_reference: PASS
- p6_tx_mmio_readback_and_rx_boundaries_observed: PASS
- local_payload_buffers_are_64_byte_aligned: PASS
- end_to_end_output_compare_is_independent: PASS
- nonzero_output_canary_is_manifest_bound: PASS
- integrity_failure_snapshot_precedes_output_wipe: PASS
- integrity_failure_snapshot_mailbox_diagnostic: PASS
- descriptor_ready_published_last: PASS
- terminal_descriptor_stable_snapshot: PASS
- phy_reenabled_and_startup_ready_waited: PASS
- runtime_terminal_after_exact_deadline: PASS
- runtime_elapsed_seqlock_and_monotonic_reader: PASS
- runtime_elapsed_causal_request_release: PASS
- object_latency_start_precedes_input_integrity: PASS
- firmware_stationary_admission_cutoff: PASS
- contained_child_tree_reaped_before_shutdown: PASS
- strict_ring_host_publication_supported: PASS
- stationary_identity_ledger_bound: PASS
- native_shutdown_readback_test: PASS
- native_payload_alignment_matrix_test: PASS
- native_stage62_diagnostic_matrix_test: PASS
- native_stage62_microtest_layout_test: PASS
- p7_python_and_codec_tests: PASS
- real_vitis_build_source_bound: PASS
