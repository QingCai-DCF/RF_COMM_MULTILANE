#ifndef P10_1_SERVICE_H
#define P10_1_SERVICE_H

#include <stddef.h>
#include <stdint.h>

#include "p10_1_contract.h"
#include "p10_1_hal.h"

#define P10_1_SERVICE_SCHEMA_VERSION UINT32_C(1)
#define P10_1_SERVICE_MAX_BUFFERS 16U
#define P10_1_TRACE_EVENT_NAME_BYTES 16U
#define P10_1_PERF_CAPABILITY UINT32_C(0x50313031)

typedef enum p10_1_service_state {
  P10_1_SERVICE_READY = 0,
  P10_1_SERVICE_CONFIGURED = 1,
  P10_1_SERVICE_RUNNING = 2,
  P10_1_SERVICE_STOPPING = 3,
  P10_1_SERVICE_COMPLETE = 4,
  P10_1_SERVICE_ABORTED = 5,
  P10_1_SERVICE_FAULT = 6
} p10_1_service_state_t;

typedef struct p10_1_trace_record {
  uint64_t timestamp;
  uint32_t generation;
  uint32_t event_id;
  uint32_t arg0;
  uint32_t arg1;
  uint32_t reserved0;
  uint32_t reserved1;
} p10_1_trace_record_t;

typedef struct p10_1_trace_ring {
  p10_1_trace_record_t *records;
  uint32_t depth;
  uint32_t write_index;
  uint32_t read_index;
  uint32_t write_generation;
  uint32_t clear_generation;
  uint64_t overflow_count;
} p10_1_trace_ring_t;

typedef struct p10_1_buffer {
  uint8_t *address;
  uint32_t capacity;
  uint32_t length;
  uint32_t generation;
  uint32_t descriptor_token;
  uint64_t offset;
  uint32_t final_segment;
  p10_1_buffer_state_t state;
  uint32_t owner;
} p10_1_buffer_t;

typedef struct p10_1_perf_config {
  uint32_t schema_version;
  uint32_t direction;
  uint32_t lane_mask;
  uint32_t duration_seconds;
  uint64_t total_bytes;
  uint32_t object_size_bytes;
  uint32_t segment_size_bytes;
  uint32_t payload_pattern;
  uint32_t seed;
  uint32_t buffer_count;
  uint32_t ring_depth;
  uint32_t descriptor_batch;
  uint32_t ack_threshold;
  uint32_t outstanding;
  uint32_t hash_mode;
  uint32_t warmup_segments;
  uint32_t formal_window;
  uint32_t stream_id;
  uint32_t object_id;
  uint32_t generation;
} p10_1_perf_config_t;

typedef struct p10_1_perf_counters {
  uint32_t snapshot_generation;
  uint32_t reserved;
  uint64_t start_ticks;
  uint64_t end_ticks;
  uint64_t application_bytes_accepted;
  uint64_t application_bytes_committed;
  uint64_t frame_bytes_acked;
  uint64_t wire_bytes;
  uint64_t descriptors_submitted;
  uint64_t descriptors_completed;
  uint64_t dma_stall_cycles;
  uint64_t axis_stall_cycles;
  uint64_t queue_occupancy_high_watermark;
  uint64_t ack_wait_cycles;
  uint64_t direction_quiet_cycles;
  uint64_t ps_prepare_ticks;
  uint64_t crc_sha_ticks;
  uint64_t trace_overflow_count;
  uint64_t descriptor_leak_count;
  uint64_t double_completion_count;
  uint64_t abort_count;
  uint64_t watchdog_kick_count;
  uint64_t atomic_commit_count;
  uint64_t integrity_error_count;
  uint64_t retry_exhausted_count;
} p10_1_perf_counters_t;

typedef struct p10_1_service {
  p10_1_hal_t hal;
  p10_1_trace_ring_t trace;
  p10_1_perf_config_t config;
  p10_1_perf_counters_t counters;
  p10_1_buffer_t buffers[P10_1_SERVICE_MAX_BUFFERS];
  p10_1_service_state_t state;
  uint64_t next_offset;
  uint64_t next_verify_offset;
  uint32_t next_buffer;
  uint32_t next_descriptor_token;
  uint32_t outstanding_descriptors;
  uint32_t final_crc32;
  uint8_t final_sha256[32];
  uint32_t fault_code;
} p10_1_service_t;

enum p10_1_trace_event {
  P10_1_TRACE_PERF_START = 1,
  P10_1_TRACE_OBJECT_ALLOC = 2,
  P10_1_TRACE_PAYLOAD_PREP_START = 3,
  P10_1_TRACE_PAYLOAD_PREP_END = 4,
  P10_1_TRACE_CRC_START = 5,
  P10_1_TRACE_CRC_END = 6,
  P10_1_TRACE_SHA_START = 7,
  P10_1_TRACE_SHA_END = 8,
  P10_1_TRACE_CACHE_FLUSH_START = 9,
  P10_1_TRACE_CACHE_FLUSH_END = 10,
  P10_1_TRACE_DESC_SUBMIT = 11,
  P10_1_TRACE_DMA_TX_START = 12,
  P10_1_TRACE_DMA_TX_END = 13,
  P10_1_TRACE_REMOTE_RX_COMPLETE = 14,
  P10_1_TRACE_CACHE_INVALIDATE_START = 15,
  P10_1_TRACE_CACHE_INVALIDATE_END = 16,
  P10_1_TRACE_REASSEMBLY_COMPLETE = 17,
  P10_1_TRACE_HASH_VERIFY_COMPLETE = 18,
  P10_1_TRACE_ATOMIC_COMMIT = 19,
  P10_1_TRACE_OBJECT_FAIL = 20,
  P10_1_TRACE_PERF_STOP = 21
};

int p10_1_trace_init(p10_1_trace_ring_t *ring,
                     p10_1_trace_record_t *storage, uint32_t depth);
void p10_1_trace_push(p10_1_trace_ring_t *ring, uint64_t timestamp,
                      uint32_t event_id, uint32_t arg0, uint32_t arg1);
uint32_t p10_1_trace_snapshot(const p10_1_trace_ring_t *ring,
                             p10_1_trace_record_t *output, uint32_t capacity,
                             uint32_t *generation, uint64_t *overflow_count);
void p10_1_trace_clear(p10_1_trace_ring_t *ring);

int p10_1_service_init(p10_1_service_t *service, const p10_1_hal_t *hal,
                       p10_1_trace_record_t *trace_storage,
                       uint32_t trace_depth, uint8_t **buffers,
                       uint32_t buffer_count, uint32_t buffer_capacity);
int p10_1_service_configure(p10_1_service_t *service,
                            const p10_1_perf_config_t *config);
int p10_1_service_command(p10_1_service_t *service,
                          p10_1_perf_command_t command);
int p10_1_service_step(p10_1_service_t *service);
int p10_1_service_snapshot(p10_1_service_t *service,
                           p10_1_perf_counters_t *snapshot);

#endif
