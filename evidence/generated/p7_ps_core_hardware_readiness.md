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
- integrity_failure_snapshot_precedes_output_wipe: PASS
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
- p7_python_and_codec_tests: PASS
- real_vitis_build_source_bound: PASS
