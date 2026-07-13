#ifndef P7_APP_SERVICE_H
#define P7_APP_SERVICE_H

#include <stddef.h>
#include <stdint.h>

#include "ir_driver.h"
#include "rf_app_protocol.h"
#include "rf_transport_backend.h"

#ifdef __cplusplus
extern "C" {
#endif

#define P7_MAILBOX_BASEADDR UINT32_C(0x00020000)
#define P7_MAILBOX_CONTROL_BYTES UINT32_C(0x00000100)
#define P7_DESCRIPTOR_BYTES UINT32_C(0x00000100)
#define P7_DESCRIPTOR_QUEUE_DEPTH UINT32_C(8)
#define P7_DESCRIPTOR_BASEADDR                                           \
  (P7_MAILBOX_BASEADDR + P7_MAILBOX_CONTROL_BYTES)
#define P7_FAILURE_SNAPSHOT_BASEADDR UINT32_C(0x00021000)
#define P7_INPUT_REFERENCE_BASEADDR UINT32_C(0x00022000)
#define P7_P6_TX_READBACK_BASEADDR UINT32_C(0x00022100)
#define P7_MAILBOX_RESERVED_END UINT32_C(0x00030000)

#define P7_DDR_BASEADDR UINT32_C(0x00100000)
#define P7_DDR_END_EXCLUSIVE UINT32_C(0x20000000)
#define P7_DDR_ALIGNMENT UINT32_C(64)
#define P7_MAX_OBJECT_BYTES RF_APP_MAX_OBJECT_BYTES
#define P7_MAX_P6_RETRY_ACCEPTANCE UINT32_C(8)
#define P7_P6_MAX_POLLS UINT32_C(2000000)
#define P7_MAX_RUNTIME_SECONDS UINT32_C(1800)

#define P7_MAILBOX_MAGIC UINT32_C(0x424d3750) /* P7MB, little endian */
#define P7_DESCRIPTOR_MAGIC UINT32_C(0x53443750) /* P7DS */
#define P7_TRACE_MAGIC UINT32_C(0x52543750) /* P7TR */
#define P7_FAILURE_SNAPSHOT_MAGIC UINT32_C(0x53463750) /* P7FS */
#define P7_FIRST_ERROR_DIAGNOSTIC_MAGIC UINT32_C(0x44433750) /* P7CD */
#define P7_FAILURE_SNAPSHOT_MAX_BYTES UINT32_C(256)
#define P7_FAILURE_SNAPSHOT_TOTAL_BYTES                                 \
  (UINT32_C(64) + P7_FAILURE_SNAPSHOT_MAX_BYTES)
#define P7_FAILURE_SNAPSHOT_STATUS_NONE UINT32_C(0)
#define P7_FAILURE_SNAPSHOT_STATUS_PUBLISHED UINT32_C(1)
#define P7_FAILURE_SNAPSHOT_STATUS_NULL_SNAPSHOT UINT32_C(2)
#define P7_FAILURE_SNAPSHOT_STATUS_NULL_SHA256 UINT32_C(3)
#define P7_FAILURE_SNAPSHOT_STATUS_ZERO_LENGTH UINT32_C(4)
#define P7_FAILURE_SNAPSHOT_STATUS_LENGTH_LIMIT UINT32_C(5)
#define P7_FAILURE_SNAPSHOT_STATUS_ADDRESS_OVERFLOW UINT32_C(6)
#define P7_FAILURE_SNAPSHOT_STATUS_RANGE_INVALID UINT32_C(7)
#define P7_FAILURE_SNAPSHOT_STATUS_INPUT_OVERLAP UINT32_C(8)
#define P7_FAILURE_SNAPSHOT_STATUS_OUTPUT_OVERLAP UINT32_C(9)
#define P7_FAILURE_SNAPSHOT_STATUS_TRACE_OVERLAP UINT32_C(10)
#define P7_FAILURE_SNAPSHOT_STATUS_MARKER_READBACK_FAILED UINT32_C(11)
#define P7_FIRST_ERROR_SNAPSHOT_BYTES UINT32_C(64)
#define P7_FIRST_ERROR_DIAGNOSTIC_TOTAL_BYTES UINT32_C(320)
#define P7_LOCAL_PAYLOAD_BYTES UINT32_C(256)
#define P7_DIAGNOSTIC_MISSING_BYTE UINT32_C(0x100)
#define P7_DIAGNOSTIC_NOT_APPLICABLE UINT32_MAX
#define P7_RUNTIME_VERSION UINT32_C(1)

enum p7_first_error_stage {
  P7_FIRST_ERROR_STAGE_INPUT_REF = 1,
  P7_FIRST_ERROR_STAGE_ENCODE_RAW = 2,
  P7_FIRST_ERROR_STAGE_ENCODE_REPAIR = 3,
  P7_FIRST_ERROR_STAGE_P6_TX_LOCAL = 4,
  P7_FIRST_ERROR_STAGE_P6_TX_MMIO_READBACK = 5,
  P7_FIRST_ERROR_STAGE_P6_RX_LOCAL = 6,
  P7_FIRST_ERROR_STAGE_RECEIVED = 7,
  P7_FIRST_ERROR_STAGE_DDR_OUTPUT_IMMEDIATE_READBACK = 8,
  P7_FIRST_ERROR_STAGE_DDR_OUTPUT_END_TO_END = 9,
  P7_FIRST_ERROR_STAGE_INTEGRITY_SNAPSHOT = 10
};

enum p7_service_state {
  P7_SERVICE_BOOTING = 0,
  P7_SERVICE_READY = 1,
  P7_SERVICE_RUNNING = 2,
  P7_SERVICE_STOPPED = 3,
  P7_SERVICE_SHUTDOWN = 4,
  P7_SERVICE_FATAL = 5
};

enum p7_control_command {
  P7_CONTROL_NONE = 0,
  P7_CONTROL_RUN = 1,
  P7_CONTROL_STOP = 2,
  P7_CONTROL_ABORT = 3,
  P7_CONTROL_CLEAR = 4,
  P7_CONTROL_SHUTDOWN = 5
};

enum p7_runtime_flags {
  P7_RUNTIME_AUTO_DEADLINE = 1u << 0,
  P7_RUNTIME_DEADLINE_REACHED = 1u << 1
};

enum p7_descriptor_command {
  P7_DESCRIPTOR_COMMAND_NONE = 0,
  P7_DESCRIPTOR_COMMAND_TRANSFER = 1
};

enum p7_descriptor_status {
  P7_DESCRIPTOR_FREE = 0,
  P7_DESCRIPTOR_READY = 1,
  P7_DESCRIPTOR_RUNNING = 2,
  P7_DESCRIPTOR_COMPLETE = 3,
  P7_DESCRIPTOR_FAILED = 4,
  P7_DESCRIPTOR_ABORTED = 5,
  P7_DESCRIPTOR_REJECTED = 6
};

enum p7_error_code {
  P7_ERROR_NONE = 0,
  P7_ERROR_DESCRIPTOR = 1,
  P7_ERROR_ADDRESS = 2,
  P7_ERROR_RANGE_OVERFLOW = 3,
  P7_ERROR_OVERLAP = 4,
  P7_ERROR_OBJECT_TOO_LARGE = 5,
  P7_ERROR_FRAGMENT_GEOMETRY = 6,
  P7_ERROR_LANE_POLICY = 7,
  P7_ERROR_ALL_LANES_UNAVAILABLE = 8,
  P7_ERROR_P6_SUBMIT = 9,
  P7_ERROR_P6_RESULT = 10,
  P7_ERROR_P6_RX = 11,
  P7_ERROR_FRAGMENT_MISMATCH = 12,
  P7_ERROR_OBJECT_CRC = 13,
  P7_ERROR_OBJECT_SHA256 = 14,
  P7_ERROR_ABORTED = 15,
  P7_ERROR_STALE_SESSION = 16,
  P7_ERROR_TRACE_RANGE = 17,
  P7_ERROR_QUEUE = 18,
  P7_ERROR_OBJECT_ID_COLLISION = 19,
  P7_ERROR_RUNTIME_LIMIT = 20,
  P7_ERROR_FRAGMENT_ENCODE_COPY = 21,
  P7_ERROR_FRAGMENT_TRANSFER_COPY = 22,
  P7_ERROR_OUTPUT_COPY = 23,
  P7_ERROR_INPUT_REFERENCE_COPY = 24,
  P7_ERROR_ENCODE_RAW_MISMATCH = 25,
  P7_ERROR_P6_TX_LOCAL_COPY = 26,
  P7_ERROR_P6_TX_MMIO_READBACK = 27,
  P7_ERROR_P6_RX_LOCAL_MISMATCH = 28,
  P7_ERROR_RECEIVED_INPUT_MISMATCH = 29,
  P7_ERROR_DDR_OUTPUT_IMMEDIATE_READBACK = 30,
  P7_ERROR_DDR_OUTPUT_END_TO_END = 31
};

/* Exactly 256 bytes. Descriptor status is the publication/commit word and is
 * always written last when the service publishes a terminal result. SHA256
 * arrays contain the standard digest as eight big-endian 32-bit words. */
typedef struct __attribute__((aligned(64))) p7_object_descriptor {
  uint32_t magic;
  uint32_t version;
  uint32_t command;
  volatile uint32_t status;
  uint32_t session_epoch;
  uint32_t object_id;
  uint32_t input_address;
  uint32_t output_address;
  uint32_t object_length;
  uint32_t expected_crc32;
  uint32_t lane_policy;
  uint32_t max_retries;
  uint32_t unavailable_lane_mask;
  uint32_t unavailable_after_fragment;
  uint32_t abort_after_fragment;
  uint32_t trace_address;
  uint32_t trace_capacity;
  uint32_t error_code;
  uint32_t bytes_completed;
  uint32_t fragments_total;
  uint32_t fragments_completed;
  uint32_t output_crc32;
  uint32_t fragment_attempts;
  uint32_t fallback_count;
  uint32_t expected_sha256[8];
  uint32_t input_sha256[8];
  uint32_t output_sha256[8];
  uint32_t p6_retry_count;
  uint32_t p6_retry_exhausted;
  uint32_t p6_tx_fail;
  uint32_t p6_crc_bad;
  uint32_t p6_payload_mismatch;
  uint32_t max_txd_high_cycles;
  uint32_t duty_violation_count;
  uint32_t lane0_fragments;
  uint32_t lane1_fragments;
  uint32_t replicated_fragments;
  uint32_t start_ticks_low;
  uint32_t start_ticks_high;
  uint32_t end_ticks_low;
  uint32_t end_ticks_high;
  uint32_t restart_count;
  uint32_t completion_sequence;
} p7_object_descriptor_t;

/* Exactly 256 bytes at P7_MAILBOX_BASEADDR. */
typedef struct __attribute__((aligned(64))) p7_mailbox_control {
  uint32_t magic;
  uint32_t version;
  volatile uint32_t service_state;
  volatile uint32_t control_command;
  uint32_t queue_depth;
  uint32_t queue_occupancy;
  uint32_t queue_high_watermark;
  uint32_t backpressure_events;
  uint32_t objects_requested;
  uint32_t objects_completed;
  uint32_t objects_failed;
  uint32_t fragments_completed;
  uint32_t bytes_completed_low;
  uint32_t bytes_completed_high;
  uint32_t current_session_epoch;
  uint32_t current_object_id;
  uint32_t current_fragment_index;
  uint32_t last_error_code;
  uint32_t shutdown_result;
  uint32_t heartbeat;
  uint32_t stop_count;
  uint32_t abort_count;
  uint32_t restart_count;
  uint32_t completion_sequence;
  uint32_t consumer_hint;
  uint32_t max_runtime_seconds;
  uint32_t runtime_flags;
  uint32_t runtime_start_ticks_low;
  uint32_t runtime_start_ticks_high;
  uint32_t runtime_elapsed_ticks_low;
  uint32_t runtime_elapsed_ticks_high;
  uint32_t calibration_window_seconds;
  uint32_t sample_interval_seconds;
  uint32_t last_sample_sequence;
  /* Even values delimit an immutable elapsed-tick snapshot.  The writer
   * publishes odd -> low/high -> even so non-atomic JTAG readers cannot
   * accept a torn 64-bit value at a low-word rollover. */
  volatile uint32_t runtime_elapsed_sequence;
  volatile uint32_t runtime_elapsed_request;
  volatile uint32_t runtime_elapsed_ack;
  /* Zero disables the stationary-only admission cutoff.  When nonzero, PS
   * rejects (without transmitting) any READY descriptor it observes inside
   * admission_guard_seconds of this runtime-relative cutoff. */
  uint32_t scheduling_cutoff_seconds;
  uint32_t admission_guard_seconds;
  /* Firmware publishes these before a terminal integrity-failure descriptor.
   * They make snapshot rejection/publication machine-readable even if the
   * host cannot observe the separate DDR publication marker. */
  volatile uint32_t failure_snapshot_address;
  volatile uint32_t failure_snapshot_bytes;
  volatile uint32_t failure_snapshot_status;
  volatile uint32_t failure_snapshot_magic_readback;
  uint32_t reserved[21];
} p7_mailbox_control_t;

/* Exactly 64 bytes; the optional DDR trace buffer must have one entry per
 * fragment so every final fragment attempt remains machine-readable. */
typedef struct __attribute__((aligned(64))) p7_fragment_trace {
  uint32_t magic;
  uint32_t session_epoch;
  uint32_t object_id;
  uint32_t fragment_index_count;
  uint32_t lane_mask;
  uint32_t attempt_count;
  uint32_t result;
  uint32_t error_code;
  uint32_t start_ticks_low;
  uint32_t start_ticks_high;
  uint32_t end_ticks_low;
  uint32_t end_ticks_high;
  uint32_t p6_retry_count;
  uint32_t p6_retry_exhausted;
  uint32_t p6_tx_fail;
  uint32_t p6_error_code;
} p7_fragment_trace_t;

/* Exactly 64 bytes.  On an object-integrity rejection the service publishes
 * this header in the fixed OCM diagnostic region, followed by the
 * first at most 256 bytes from the same immutable snapshot consumed by both
 * output digests.  The host captures and wipes the diagnostic region before
 * the stage exits; the normal output range is still wiped before FAILED is
 * published. */
typedef struct __attribute__((aligned(64))) p7_failure_snapshot_header {
  volatile uint32_t magic;
  uint32_t version;
  uint32_t session_epoch;
  uint32_t object_id;
  uint32_t object_length;
  uint32_t captured_length;
  uint32_t output_crc32;
  uint32_t error_code;
  uint32_t output_sha256[8];
} p7_failure_snapshot_header_t;

/* Exactly 320 bytes in the fixed OCM diagnostic region.  The first mismatch
 * is published once, with magic written and read back last.  SHA256 arrays
 * contain standard digest words in big-endian word order.  A byte value of
 * P7_DIAGNOSTIC_MISSING_BYTE means that side ended before first_bad_offset. */
typedef struct __attribute__((aligned(64))) p7_first_error_diagnostic {
  volatile uint32_t magic;
  uint32_t version;
  uint32_t stage;
  uint32_t error_code;
  uint32_t session_epoch;
  uint32_t object_id;
  uint32_t fragment_index;
  uint32_t lane_mask;
  uint32_t expected_length;
  uint32_t actual_length;
  uint32_t first_bad_offset;
  uint32_t expected_byte;
  uint32_t actual_byte;
  uint32_t expected_address;
  uint32_t actual_address;
  uint32_t expected_crc32;
  uint32_t actual_crc32;
  uint32_t snapshot_offset;
  uint32_t snapshot_length;
  uint32_t reserved_metadata;
  uint32_t expected_sha256[8];
  uint32_t actual_sha256[8];
  uint32_t reserved_header[12];
  uint8_t expected_snapshot[P7_FIRST_ERROR_SNAPSHOT_BYTES];
  uint8_t actual_snapshot[P7_FIRST_ERROR_SNAPSHOT_BYTES];
} p7_first_error_diagnostic_t;

int p7_app_service_run(const ir_mmio_t *io,
                       volatile p7_mailbox_control_t *mailbox,
                       volatile p7_object_descriptor_t *descriptors);

#ifdef __cplusplus
}
#endif

#endif
