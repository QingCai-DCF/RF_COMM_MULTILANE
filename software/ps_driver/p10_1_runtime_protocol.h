#ifndef P10_1_RUNTIME_PROTOCOL_H
#define P10_1_RUNTIME_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

/*
 * The P9/P10 control mailbox occupies 0x00020000..0x000203ff.  The role-bound
 * P10.1 runtime publishes a second, append-only result page immediately after
 * it.  Every field is a 32-bit word so XSDB can take an unambiguous binary
 * snapshot while either Cortex-A9 is stopped.
 */
#define P10_1_RUNTIME_MAILBOX_BASEADDR UINT32_C(0x00020400)
#define P10_1_RUNTIME_MAGIC UINT32_C(0x31303150) /* P101, little endian */
#define P10_1_RUNTIME_SCHEMA_VERSION UINT32_C(1)
#define P10_1_RUNTIME_PL_TIMER_HZ UINT32_C(64000000)
#define P10_1_RUNTIME_MAX_TIMEOUT_MS UINT32_C(1800000)
#define P10_1_RUNTIME_MAX_STREAM_BYTES UINT32_C(0x20000000)
#define P10_1_RUNTIME_MAX_OBJECT_BYTES UINT32_C(0x04000000)
#define P10_1_RUNTIME_SIGNAL_PULSES UINT32_C(16)
#define P10_1_RUNTIME_SIGNAL_SPACING_CYCLES UINT32_C(1024)

enum p10_1_runtime_state {
  P10_1_RUNTIME_EMPTY = 0,
  P10_1_RUNTIME_INITIALIZING = 1,
  P10_1_RUNTIME_PRIMING = 2,
  P10_1_RUNTIME_PRIMED = 3,
  P10_1_RUNTIME_RUNNING = 4,
  P10_1_RUNTIME_VERIFYING = 5,
  P10_1_RUNTIME_COMPLETE = 6,
  P10_1_RUNTIME_EXPECTED_ABORT = 7,
  P10_1_RUNTIME_FAULT = 8,
  P10_1_RUNTIME_SHUTDOWN = 9,
};

enum p10_1_runtime_status {
  P10_1_RUNTIME_STATUS_OK = 0,
  P10_1_RUNTIME_STATUS_BAD_ARGUMENT = 0x101,
  P10_1_RUNTIME_STATUS_DMA_CHAIN = 0x102,
  P10_1_RUNTIME_STATUS_DMA_COMPLETION = 0x103,
  P10_1_RUNTIME_STATUS_PL_OBJECT = 0x104,
  P10_1_RUNTIME_STATUS_INTEGRITY = 0x105,
  P10_1_RUNTIME_STATUS_SIGNAL_TIMEOUT = 0x106,
  P10_1_RUNTIME_STATUS_TIMER = 0x107,
  P10_1_RUNTIME_STATUS_REMOTE_COMMIT = 0x108,
  P10_1_RUNTIME_STATUS_ABORT_RECOVERY = 0x109,
};

enum p10_1_runtime_flags {
  P10_1_RUNTIME_FLAG_PATTERN_SHIFT = 8,
  P10_1_RUNTIME_FLAG_PATTERN_MASK = 0x0fU << 8,
  P10_1_RUNTIME_FLAG_EXPECT_ABORT_25 = 1U << 16,
  P10_1_RUNTIME_FLAG_EXPECT_ABORT_75 = 1U << 17,
  P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_SENDER = 1U << 18,
  P10_1_RUNTIME_FLAG_EXPECT_PL_RESET = 1U << 19,
  P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT = 1U << 20,
  P10_1_RUNTIME_FLAG_STALE_SEGMENT = 1U << 21,
  /*
   * Bits 22 and 23 are host-orchestrated service-reset vectors. Firmware
   * records them, while the XSDB executor resets the selected Cortex-A9
   * during the active stream.
   */
  P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_SENDER = 1U << 22,
  P10_1_RUNTIME_FLAG_EXPECT_PS_RESET_RECEIVER = 1U << 23,
  P10_1_RUNTIME_FLAG_EXPECT_DMA_RESET_RECEIVER = 1U << 24,
  /* P10.4 role-selective PL reset: only the endpoint that is the local
   * transmitter for the requested direction resets its PL data plane.  The
   * earlier bit-19 vector deliberately retains its historical both-endpoint
   * semantics for immutable P10.1/P10.3 replay. */
  P10_1_RUNTIME_FLAG_EXPECT_ABORT_50 = 1U << 25,
  P10_1_RUNTIME_FLAG_EXPECT_PL_RESET_LOCAL_TX = 1U << 26,
  /* P10.5 direction-fault acceptance controls. These bits are accepted only
   * by command 15 and never weaken the final TX kill or TFDU safety guards. */
  P10_5_RUNTIME_FLAG_DIRECTION_FAULT_TEST = 1U << 27,
  P10_5_RUNTIME_FLAG_FAULT_TARGET_R2F = 1U << 28,
  P10_5_RUNTIME_FLAG_ABORT_TARGET_DIRECTION = 1U << 29,
  P10_5_RUNTIME_FLAG_DMA_TX_BACKPRESSURE = 1U << 30,
  P10_5_RUNTIME_FLAG_STALE_ROLE_EPOCH_ONCE = 1U << 31,
};

typedef struct p10_1_runtime_result {
  volatile uint32_t magic;
  volatile uint32_t schema_version;
  volatile uint32_t firmware_build_id;
  volatile uint32_t endpoint_role;
  volatile uint32_t service_state;
  volatile uint32_t status;
  volatile uint32_t command_sequence;
  volatile uint32_t flags;

  volatile uint32_t lane_mask;
  volatile uint32_t direction;
  volatile uint32_t rate_select;
  volatile uint32_t total_bytes;
  volatile uint32_t object_bytes;
  volatile uint32_t descriptor_bytes;
  volatile uint32_t descriptor_count_per_object;
  volatile uint32_t object_count;
  volatile uint32_t ring_depth;
  volatile uint32_t descriptor_batch;
  volatile uint32_t buffer_count;
  volatile uint32_t ack_threshold;
  volatile uint32_t outstanding_frames;
  volatile uint32_t timeout_ms;
  volatile uint32_t session_epoch;
  volatile uint32_t path_epoch;
  volatile uint32_t first_object_id;
  volatile uint32_t payload_pattern;

  volatile uint32_t ps_start_ticks_low;
  volatile uint32_t ps_start_ticks_high;
  volatile uint32_t ps_end_ticks_low;
  volatile uint32_t ps_end_ticks_high;
  volatile uint32_t ps_elapsed_ticks_low;
  volatile uint32_t ps_elapsed_ticks_high;
  volatile uint32_t pl_start_ticks_low;
  volatile uint32_t pl_start_ticks_high;
  volatile uint32_t pl_end_ticks_low;
  volatile uint32_t pl_end_ticks_high;
  volatile uint32_t pl_elapsed_ticks_low;
  volatile uint32_t pl_elapsed_ticks_high;
  volatile uint32_t ps_timer_frequency_hz;
  volatile uint32_t pl_timer_frequency_hz;
  volatile uint32_t timer_error_ppm;
  volatile uint32_t timer_crosscheck_pass;

  volatile uint32_t application_bytes_accepted_low;
  volatile uint32_t application_bytes_accepted_high;
  volatile uint32_t application_bytes_committed_low;
  volatile uint32_t application_bytes_committed_high;
  volatile uint32_t wire_bytes_low;
  volatile uint32_t wire_bytes_high;
  volatile uint32_t descriptors_submitted_low;
  volatile uint32_t descriptors_submitted_high;
  volatile uint32_t descriptors_completed_low;
  volatile uint32_t descriptors_completed_high;
  volatile uint32_t objects_submitted;
  volatile uint32_t objects_completed;
  volatile uint32_t atomic_commit_count;
  volatile uint32_t host_command_count;
  volatile uint32_t fast_path_segment_count;
  volatile uint32_t remote_commit_confirmed;

  volatile uint32_t partial_commit_count;
  volatile uint32_t duplicate_commit_count;
  volatile uint32_t stale_commit_count;
  volatile uint32_t descriptor_leak_count;
  volatile uint32_t double_completion_count;
  volatile uint32_t integrity_error_count;
  volatile uint32_t crc_bad_count;
  volatile uint32_t sha_mismatch_count;
  volatile uint32_t retry_exhausted_count;
  volatile uint32_t abort_count;
  volatile uint32_t dma_reset_count;
  volatile uint32_t pl_reset_count;
  volatile uint32_t first_mismatch_offset;
  volatile uint32_t last_error_detail;

  volatile uint32_t input_crc32;
  volatile uint32_t output_crc32;
  volatile uint32_t input_sha256[8];
  volatile uint32_t output_sha256[8];

  volatile uint32_t payload_prepare_ticks_low;
  volatile uint32_t payload_prepare_ticks_high;
  volatile uint32_t integrity_verify_ticks_low;
  volatile uint32_t integrity_verify_ticks_high;
  volatile uint32_t inter_object_signal_ticks_low;
  volatile uint32_t inter_object_signal_ticks_high;

  volatile uint32_t perf_snapshot_generation;
  volatile uint32_t perf_application_accepted_low;
  volatile uint32_t perf_application_accepted_high;
  volatile uint32_t perf_application_committed_low;
  volatile uint32_t perf_application_committed_high;
  volatile uint32_t perf_frame_acked_low;
  volatile uint32_t perf_frame_acked_high;
  volatile uint32_t perf_wire_bytes_low;
  volatile uint32_t perf_wire_bytes_high;
  volatile uint32_t perf_descriptor_submitted;
  volatile uint32_t perf_descriptor_completed;
  volatile uint32_t perf_dma_stall_low;
  volatile uint32_t perf_dma_stall_high;
  volatile uint32_t perf_axis_stall_low;
  volatile uint32_t perf_axis_stall_high;
  volatile uint32_t perf_queue_occupancy;
  volatile uint32_t perf_ack_wait_low;
  volatile uint32_t perf_ack_wait_high;
  volatile uint32_t perf_direction_quiet_low;
  volatile uint32_t perf_direction_quiet_high;
  volatile uint32_t perf_integrity_error_count;
  volatile uint32_t perf_retry_exhausted_count;
  volatile uint32_t perf_descriptor_leak_count;
  volatile uint32_t perf_double_completion_count;

  volatile uint32_t raw_rx_before[4];
  volatile uint32_t raw_rx_after[4];
  volatile uint32_t physical_tx_before[4];
  volatile uint32_t physical_tx_after[4];
  volatile uint32_t duty_high_max_after[4];
  volatile uint32_t duty_hard_fault_after[4];
  volatile uint32_t tx_high_max_after[4];
  volatile uint32_t physical_data_good_by_lane_after[2];
  volatile uint32_t physical_ack_good_by_lane_after[2];
  volatile uint32_t physical_crc_bad_by_lane_after[2];
  volatile uint32_t physical_frame_bad_by_lane_after[2];
  volatile uint32_t physical_preamble_by_lane_after[2];
  volatile uint32_t physical_symbol_error_by_lane_after[2];

  volatile uint32_t shutdown_attempt_count;
  volatile uint32_t shutdown_verified_count;
  volatile uint32_t final_pl_status;
  volatile uint32_t final_phy_status;
  /*
   * These consume the first two words of the schema-v1 reserved tail. Existing
   * word offsets remain stable and old readers may still treat them as
   * reserved.
   */
  volatile uint32_t descriptors_reclaimed_by_reset;
  volatile uint32_t injected_fault_observed_count;
  /* P10.4 append-only, direct hardware counter semantics.  The legacy
   * perf_ack_wait field remains at words 112/113 for compatibility and is
   * DEPRECATED_AMBIGUOUS; new code must use these named fields. */
  volatile uint32_t perf_outstanding_unacked_low;
  volatile uint32_t perf_outstanding_unacked_high;
  volatile uint32_t perf_tx_idle_due_to_ack_low;
  volatile uint32_t perf_tx_idle_due_to_ack_high;
  volatile uint32_t perf_window_full_stall_low;
  volatile uint32_t perf_window_full_stall_high;
  volatile uint32_t perf_receiver_credit_stall_low;
  volatile uint32_t perf_receiver_credit_stall_high;
  volatile uint32_t perf_direction_turnaround_idle_low;
  volatile uint32_t perf_direction_turnaround_idle_high;
  /* P10.5 append-only autonomous dual-direction evidence.  These fields are
   * populated only by command 15; command 13 leaves them zero. */
  volatile uint32_t p10_5_dual_direction_mode;
  volatile uint32_t p10_5_active_mask;
  volatile uint32_t p10_5_f2r_mask;
  volatile uint32_t p10_5_r2f_mask;
  volatile uint32_t p10_5_local_tx_mask;
  volatile uint32_t p10_5_local_rx_mask;
  volatile uint32_t p10_5_role_epoch;
  volatile uint32_t p10_5_context_status;
  volatile uint32_t p10_5_piggyback_ack_tx_count;
  volatile uint32_t p10_5_piggyback_ack_rx_count;
  volatile uint32_t p10_5_control_only_ack_count;
  volatile uint32_t p10_5_direction_reject_count;
  volatile uint32_t p10_5_role_epoch_reject_count;
  volatile uint32_t p10_5_tx_bytes;
  volatile uint32_t p10_5_rx_bytes;
  volatile uint32_t p10_5_tx_retry_count;
  volatile uint32_t p10_5_tx_timeout_count;
  volatile uint32_t p10_5_tx_axis_stall;
  volatile uint32_t p10_5_rx_axis_stall;
  volatile uint32_t p10_5_control_queue_occupancy;
  volatile uint32_t p10_5_tx_window_occupancy;
  volatile uint32_t p10_5_rx_window_occupancy;
  volatile uint32_t p10_5_tx_receiver_credit;
  volatile uint32_t p10_5_rx_receiver_credit;
  volatile uint32_t p10_5_ack_tx_bytes;
  volatile uint32_t p10_5_ack_rx_bytes;
  volatile uint32_t p10_5_control_tx_bytes;
  volatile uint32_t p10_5_application_committed_bytes;
  volatile uint32_t p10_5_duration_target_ms;
  volatile uint32_t p10_5_duration_elapsed_ms;
  volatile uint32_t p10_5_stream_ceiling_bytes;
  volatile uint32_t p10_5_prefetched_objects_reclaimed;
  volatile uint32_t p10_5_fault_test_kind;
  volatile uint32_t p10_5_fault_target_direction;
  volatile uint32_t p10_5_unaffected_progress_bytes;
  volatile uint32_t p10_5_affected_commit_count;
  volatile uint32_t p10_5_fault_recovery_pass;
  volatile uint32_t p10_5_diagnostic_status_before;
  volatile uint32_t p10_5_diagnostic_status_after;
  volatile uint32_t p10_5_diagnostic_stall_delta;
  volatile uint32_t reserved[12];
} p10_1_runtime_result_t;

_Static_assert(offsetof(p10_1_runtime_result_t, service_state) == 4U * 4U,
               "P10.1 service-state word moved");
_Static_assert(offsetof(p10_1_runtime_result_t, ps_start_ticks_low) ==
                   26U * 4U,
               "P10.1 timer word moved");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        descriptors_reclaimed_by_reset) == 164U * 4U,
               "P10.1 recovery word moved");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        injected_fault_observed_count) == 165U * 4U,
               "P10.1 injected-fault word moved");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        perf_outstanding_unacked_low) == 166U * 4U,
               "P10.4 split-counter tail moved");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        perf_direction_turnaround_idle_high) == 175U * 4U,
               "P10.4 split-counter tail length changed");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        p10_5_dual_direction_mode) == 176U * 4U,
               "P10.5 autonomous evidence tail moved");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        p10_5_application_committed_bytes) == 203U * 4U,
               "P10.5 autonomous evidence tail length changed");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        p10_5_prefetched_objects_reclaimed) == 207U * 4U,
               "P10.5 duration evidence tail length changed");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        p10_5_fault_test_kind) == 208U * 4U,
               "P10.5 direction-fault evidence tail moved");
_Static_assert(offsetof(p10_1_runtime_result_t,
                        p10_5_diagnostic_stall_delta) == 215U * 4U,
               "P10.5 direction-fault evidence tail length changed");
_Static_assert(sizeof(p10_1_runtime_result_t) <= 2048U,
               "P10.1 result must fit the reserved two-KiB OCM window");

#endif
