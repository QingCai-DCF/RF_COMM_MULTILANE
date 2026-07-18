#pragma once

#include <stddef.h>
#include <stdint.h>

#include "ir_driver.h"
#include "p8d_data_plane_config.h"

#ifdef __cplusplus
extern "C" {
#endif
typedef int (*p8d_cache_range_fn)(void *ctx, uintptr_t address, size_t length);
typedef void (*p8d_memory_barrier_fn)(void *ctx);

typedef struct {
  void *ctx;
  p8d_cache_range_fn flush;
  p8d_cache_range_fn invalidate;
  p8d_memory_barrier_fn ownership_barrier;
} p8d_cache_ops_t;

typedef struct {
  uint32_t version_state_generation;
  uint32_t flags_priority_lane_policy;
  uint64_t buffer_address;
  uint32_t buffer_capacity;
  uint32_t requested_length;
  uint32_t actual_length;
  uint32_t stream_id;
  uint32_t object_id;
  uint32_t user_tag;
  uint32_t session_epoch;
  uint16_t completion_status;
  uint16_t error_code;
  uint32_t next_index;
  uint32_t reserved0;
  uint64_t timestamp_or_cookie;
} p8d_descriptor_t;

typedef struct {
  p8d_descriptor_t *descriptors;
  uint32_t depth;
  uint32_t producer;
  uint32_t consumer;
  uint16_t generation;
  uint8_t is_rx;
} p8d_ring_t;

typedef struct {
  uint32_t protocol_version;
  uint32_t capabilities;
  uint32_t maximum_outstanding;
  uint32_t sack_window_bits;
  uint32_t sequence_width_bits;
  uint32_t tx_ring_depth;
  uint32_t rx_ring_depth;
  uint32_t axis_data_width_bits;
} p8d_capabilities_t;

typedef struct {
  uint32_t session_epoch;
  uint16_t path_epoch;
  uint8_t protocol_mode;
  uint8_t reserved;
} p8d_session_config_t;

typedef struct {
  uint32_t tx_window_size;
  uint32_t rx_window_size;
  uint32_t sack_window_bits;
  uint32_t maximum_retry;
  uint32_t rto_initial_cycles;
} p8d_window_config_t;

typedef struct {
  uint32_t active_lane_mask;
  uint8_t weights[8];
  uint32_t starvation_bound;
} p8d_scheduler_config_t;

typedef struct {
  uint32_t global_outstanding_count;
  uint32_t global_outstanding_high_watermark;
  uint32_t tx_retry_count;
  uint32_t migration_count;
  uint32_t rx_duplicate_count;
  uint32_t descriptor_complete_count;
  uint32_t descriptor_error_count;
  uint32_t axis_tx_stall_cycles;
  uint32_t axis_rx_stall_cycles;
} p8d_counter_snapshot_t;

typedef struct {
  ir_mmio_t io;
  p8d_cache_ops_t cache;
  p8d_ring_t tx_ring;
  p8d_ring_t rx_ring;
  uint32_t session_epoch;
  uint16_t generation;
} p8d_driver_t;

enum {
  P8D_OK = 0,
  P8D_ERR_ARGUMENT = -1,
  P8D_ERR_CAPABILITY = -2,
  P8D_ERR_RING_FULL = -3,
  P8D_ERR_OWNERSHIP = -4,
  P8D_ERR_CACHE = -5,
  P8D_ERR_STALE_GENERATION = -6,
  P8D_ERR_NO_COMPLETION = -7,
};

int p8d_query_capabilities(p8d_driver_t *driver, p8d_capabilities_t *capabilities);
int p8d_configure_session(p8d_driver_t *driver, const p8d_session_config_t *config);
int p8d_configure_window(p8d_driver_t *driver, const p8d_window_config_t *config);
int p8d_configure_scheduler(p8d_driver_t *driver, const p8d_scheduler_config_t *config);
int p8d_init_tx_ring(p8d_driver_t *driver, p8d_descriptor_t *descriptors, uint32_t depth);
int p8d_init_rx_ring(p8d_driver_t *driver, p8d_descriptor_t *descriptors, uint32_t depth);
int p8d_submit_tx_descriptor(p8d_driver_t *driver, uintptr_t buffer_address,
                             uint32_t length, uint32_t stream_id,
                             uint32_t object_id, uint32_t user_tag);
int p8d_post_rx_descriptor(p8d_driver_t *driver, uintptr_t buffer_address,
                           uint32_t capacity, uint32_t stream_id,
                           uint32_t object_id, uint32_t user_tag);
int p8d_poll_completion(p8d_driver_t *driver, int receive_ring, p8d_descriptor_t **descriptor);
int p8d_reap_completion(p8d_driver_t *driver, int receive_ring);
int p8d_abort_stream_or_object(p8d_driver_t *driver, uint32_t stream_id, uint32_t object_id);
int p8d_reset_data_plane(p8d_driver_t *driver);
int p8d_snapshot_counters(p8d_driver_t *driver, p8d_counter_snapshot_t *snapshot);
int p8d_clear_sticky_errors(p8d_driver_t *driver);

#ifdef __cplusplus
}
#endif
