#ifndef P9_RUNTIME_PROTOCOL_H
#define P9_RUNTIME_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#define P9_MAILBOX_BASEADDR UINT32_C(0x00020000)
#define P9_TX_BD_BASEADDR UINT32_C(0x01000000)
#define P9_RX_BD_BASEADDR UINT32_C(0x01001000)
#define P9_TX_BUFFER_BASEADDR UINT32_C(0x02000000)
#define P9_RX_BUFFER_BASEADDR UINT32_C(0x06000000)
#define P9_MAX_OBJECT_BYTES UINT32_C(0x04000000)
#define P9_MAILBOX_MAGIC UINT32_C(0x424d3950) /* P9MB */
#define P9_RUNTIME_BUILD_ID UINT32_C(0x50090009)
#define P9_MAILBOX_SCHEMA_VERSION UINT32_C(5)
#define P9_PL_SNAPSHOT_WORDS 99U
#define P9_TERMINAL_WINDOW_VALID UINT32_C(0x5457494e) /* TWIN */

enum p9_service_state {
  P9_SERVICE_BOOT = 0,
  P9_SERVICE_READY = 1,
  P9_SERVICE_SUBMITTED = 2,
  P9_SERVICE_RUNNING = 3,
  P9_SERVICE_COMPLETE = 4,
  P9_SERVICE_FAULT = 5,
  P9_SERVICE_SHUTDOWN = 6,
};

enum p9_command {
  P9_COMMAND_NONE = 0,
  P9_COMMAND_IDENTITY_SAFE_IDLE = 1,
  P9_COMMAND_RAW_MATRIX = 2,
  P9_COMMAND_OBJECT_TRANSFER = 3,
  P9_COMMAND_RING_DIAGNOSTIC = 4,
  P9_COMMAND_DMA_RESET_IDLE = 5,
  P9_COMMAND_DMA_RESET_QUEUED = 6,
  P9_COMMAND_ABORT_OUTSTANDING = 7,
  P9_COMMAND_PL_SOFT_RESET = 8,
  P9_COMMAND_STALE_COMPLETION = 9,
  P9_COMMAND_SHUTDOWN = 10,
  P9_COMMAND_IDLE_NOISE = 11,
  P9_COMMAND_PERMIT_DROP_DIAGNOSTIC = 12,
};

enum p9_runtime_status {
  P9_RUNTIME_OK = 0,
  P9_RUNTIME_BAD_COMMAND = 1,
  P9_RUNTIME_BAD_ARGUMENT = 2,
  P9_RUNTIME_PL_IDENTITY = 3,
  P9_RUNTIME_SAFE_IDLE = 4,
  P9_RUNTIME_PHY_NOT_READY = 5,
  P9_RUNTIME_ARM_FAILED = 6,
  P9_RUNTIME_DMA_CONFIG = 7,
  P9_RUNTIME_DMA_RING = 8,
  P9_RUNTIME_DMA_SUBMIT = 9,
  P9_RUNTIME_DMA_TIMEOUT = 10,
  P9_RUNTIME_DMA_COMPLETION = 11,
  P9_RUNTIME_PL_OBJECT = 12,
  P9_RUNTIME_PAYLOAD_MISMATCH = 13,
  P9_RUNTIME_RAW_TIMEOUT = 14,
  P9_RUNTIME_RESET_FAILED = 15,
  P9_RUNTIME_EXPECTED_ABORT = 16,
  P9_RUNTIME_RFAP_VALIDATION = 17,
  P9_RUNTIME_PERMIT_DROP = 18,
};

enum p9_command_flags {
  P9_FLAG_ALLOW_EXPECTED_OBJECT_FAILURE = 1U << 0,
  P9_FLAG_GENERATE_PAYLOAD_IN_PS = 1U << 1,
  P9_FLAG_RFAP_V1_PAYLOAD = 1U << 2,
  P9_FLAG_RFAP_VNEXT_PAYLOAD = 1U << 3,
};

/* The host writes command_sequence last and the firmware writes
 * response_sequence/state last.  Every field is a 32-bit naturally aligned
 * word so XSDB can atomically inspect or update it. */
typedef struct p9_mailbox {
  volatile uint32_t magic;
  volatile uint32_t schema_version;
  volatile uint32_t firmware_build_id;
  volatile uint32_t service_state;
  volatile uint32_t boot_count;
  volatile uint32_t command;
  volatile uint32_t command_sequence;
  volatile uint32_t response_sequence;
  volatile uint32_t command_status;
  volatile uint32_t command_flags;
  volatile uint32_t lane_mask;
  volatile uint32_t direction;
  volatile uint32_t rate_select;
  volatile uint32_t lane_weights;
  volatile uint32_t object_size;
  volatile uint32_t ring_depth;
  volatile uint32_t cache_mode;
  volatile uint32_t tx_offset;
  volatile uint32_t rx_offset;
  volatile uint32_t timeout_ms;
  volatile uint32_t session_epoch;
  volatile uint32_t path_epoch;
  volatile uint32_t object_id;
  volatile uint32_t drop_data_count;
  volatile uint32_t drop_ack_count;
  volatile uint32_t lane_unavailable_mask;
  volatile uint32_t raw_target;
  volatile uint32_t raw_spacing_cycles;
  volatile uint32_t stale_token;
  volatile uint32_t initial_sequence;
  volatile uint32_t protocol_fault_flags;
  volatile uint32_t idle_duration_ms;

  volatile uint32_t pl_id;
  volatile uint32_t pl_build_id;
  volatile uint32_t pl_profile_id;
  volatile uint32_t pl_register_map_version;
  volatile uint32_t pl_register_map_hash_low;
  volatile uint32_t pl_capabilities;
  volatile uint32_t dma_device_id;
  volatile uint32_t dma_base_address;
  volatile uint32_t dma_has_sg;
  volatile uint32_t dma_addr_width;
  volatile uint32_t dma_sg_length_width;
  volatile uint32_t dma_mm2s_data_width;
  volatile uint32_t dma_s2mm_data_width;
  volatile uint32_t dma_mm2s_burst;
  volatile uint32_t dma_s2mm_burst;
  volatile uint32_t dma_mm2s_dre;
  volatile uint32_t dma_s2mm_dre;
  volatile uint32_t descriptor_alignment;
  volatile uint32_t cache_line_bytes;
  volatile uint32_t interrupt_mm2s_id;
  volatile uint32_t interrupt_s2mm_id;

  volatile uint32_t start_ticks_low;
  volatile uint32_t start_ticks_high;
  volatile uint32_t end_ticks_low;
  volatile uint32_t end_ticks_high;
  volatile uint32_t elapsed_ticks_low;
  volatile uint32_t elapsed_ticks_high;
  volatile uint32_t counts_per_second;
  volatile uint32_t actual_rx_length;
  volatile uint32_t input_crc32;
  volatile uint32_t output_crc32;
  volatile uint32_t input_sha256[8];
  volatile uint32_t output_sha256[8];
  volatile uint32_t first_mismatch_offset;

  volatile uint32_t tx_submitted;
  volatile uint32_t tx_completed;
  volatile uint32_t rx_submitted;
  volatile uint32_t rx_completed;
  volatile uint32_t tx_producer_index;
  volatile uint32_t tx_consumer_index;
  volatile uint32_t rx_producer_index;
  volatile uint32_t rx_consumer_index;
  volatile uint32_t tx_producer_generation;
  volatile uint32_t tx_consumer_generation;
  volatile uint32_t rx_producer_generation;
  volatile uint32_t rx_consumer_generation;
  volatile uint32_t tx_ring_full_observed;
  volatile uint32_t rx_ring_full_observed;
  volatile uint32_t tx_ring_empty_observed;
  volatile uint32_t rx_ring_empty_observed;
  volatile uint32_t tx_double_completion;
  volatile uint32_t rx_double_completion;
  volatile uint32_t descriptor_leak_count;
  volatile uint32_t stale_completion_rejected;
  volatile uint32_t cache_flush_count;
  volatile uint32_t cache_invalidate_count;
  volatile uint32_t memory_barrier_count;
  volatile uint32_t cache_enabled_exercised;
  volatile uint32_t cache_disabled_exercised;
  volatile uint32_t misaligned_transfer_handled;
  volatile uint32_t dma_reset_count;
  volatile uint32_t dma_reset_while_queued_count;
  volatile uint32_t object_abort_count;
  volatile uint32_t pl_soft_reset_count;
  volatile uint32_t shutdown_attempt_count;
  volatile uint32_t shutdown_verified_count;
  volatile uint32_t last_dma_tx_status;
  volatile uint32_t last_dma_rx_status;
  volatile uint32_t last_completion_token;
  volatile uint32_t last_error_detail;

  volatile uint32_t pl_register_snapshot[P9_PL_SNAPSHOT_WORDS];

  /* Direct PS/runtime latency instrumentation.  Each pair is a 64-bit TTC
   * count with the low word first. */
  volatile uint32_t payload_prepare_ticks_low;
  volatile uint32_t payload_prepare_ticks_high;
  volatile uint32_t dma_tx_completion_ticks_low;
  volatile uint32_t dma_tx_completion_ticks_high;
  volatile uint32_t dma_rx_completion_ticks_low;
  volatile uint32_t dma_rx_completion_ticks_high;
  volatile uint32_t pl_completion_ticks_low;
  volatile uint32_t pl_completion_ticks_high;
  volatile uint32_t integrity_verify_ticks_low;
  volatile uint32_t integrity_verify_ticks_high;
  volatile uint32_t object_runtime_ticks_low;
  volatile uint32_t object_runtime_ticks_high;

  /* Permit-drop diagnostic captures all four physical module counters before
   * drop, after drop, and after an explicit re-arm. */
  volatile uint32_t permit_tx_before_drop[4];
  volatile uint32_t permit_tx_after_drop[4];
  volatile uint32_t permit_tx_after_rearm[4];
  volatile uint32_t permit_status_after_drop;
  volatile uint32_t permit_status_after_rearm;
  volatile uint32_t permit_raw_sent_before_drop;
  volatile uint32_t permit_raw_sent_after_drop;
  volatile uint32_t permit_raw_sent_after_rearm;
  volatile uint32_t permit_result_flags;

  /* Runtime RFAP parser/reassembly evidence. */
  volatile uint32_t rfap_mode;
  volatile uint32_t rfap_fragment_count;
  volatile uint32_t rfap_useful_bytes;
  volatile uint32_t rfap_validation_pass;
  volatile uint32_t rfap_partial_publish_count;
  volatile uint32_t rfap_atomic_publish_count;
  volatile uint32_t rfap_useful_crc32;

  /* Object-terminal selective-repeat state captured directly from PL before
   * the mandatory full shutdown clears the TX window.  The command sequence
   * binds the capture to this mailbox transaction; valid is published last. */
  volatile uint32_t terminal_window_valid;
  volatile uint32_t terminal_window_command_sequence;
  volatile uint32_t terminal_tx_sequence_base;
  volatile uint32_t terminal_window_status;
} p9_mailbox_t;

_Static_assert(offsetof(p9_mailbox_t, pl_register_snapshot) == 116U * 4U,
               "P9 PL snapshot mailbox offset changed");
_Static_assert(offsetof(p9_mailbox_t, payload_prepare_ticks_low) == 215U * 4U,
               "P9 appended telemetry mailbox offset changed");
_Static_assert(offsetof(p9_mailbox_t, terminal_window_valid) == 252U * 4U,
               "P9 terminal window mailbox offset changed");
_Static_assert(sizeof(p9_mailbox_t) == 256U * 4U,
               "P9 mailbox schema-5 layout must be exactly 256 words");
_Static_assert(sizeof(p9_mailbox_t) <= 1024U,
               "P9 mailbox must remain inside one OCM page");

#endif
