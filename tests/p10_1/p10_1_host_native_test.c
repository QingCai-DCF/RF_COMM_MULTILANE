#include "p10_1_service.h"
#include "p10_1_hal_ports.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct host_context {
  uint64_t ticks;
  uint64_t frequency;
  uint64_t generated_bytes;
  uint64_t integrity_bytes;
  uint64_t verified_bytes;
  uint64_t committed_bytes;
  uint32_t last_token;
  uint32_t watchdog_kicks;
  uint32_t telemetry_count;
  uint32_t force_dma_error;
  uint32_t dma_completion_delay_polls;
  uint32_t dma_pending[256];
  uint32_t dma_outstanding;
  uint32_t max_dma_outstanding;
} host_context_t;

static uint64_t host_timer_now(void *opaque) {
  host_context_t *context = (host_context_t *)opaque;
  context->ticks += 101U;
  return context->ticks;
}

static uint64_t host_timer_frequency(void *opaque) {
  return ((host_context_t *)opaque)->frequency;
}

static int host_generate(void *opaque, uint32_t pattern, uint32_t seed,
                         uint64_t offset, uint8_t *buffer, size_t length) {
  host_context_t *context = (host_context_t *)opaque;
  size_t index;
  (void)pattern;
  for (index = 0U; index < length; ++index)
    buffer[index] = (uint8_t)((offset + index + seed) & 0xffU);
  context->generated_bytes += length;
  return 0;
}

static void host_integrity_begin(void *opaque) {
  ((host_context_t *)opaque)->integrity_bytes = 0U;
}

static void host_integrity_update(void *opaque, const uint8_t *data,
                                  size_t length) {
  host_context_t *context = (host_context_t *)opaque;
  (void)data;
  context->integrity_bytes += length;
}

static int host_integrity_final(void *opaque, uint32_t *crc32,
                                uint8_t sha256[32]) {
  host_context_t *context = (host_context_t *)opaque;
  *crc32 = (uint32_t)context->integrity_bytes ^ UINT32_C(0x10203040);
  memset(sha256, (int)(context->integrity_bytes & 0xffU), 32U);
  return 0;
}

static int host_cache(void *opaque, uintptr_t address, size_t length) {
  (void)opaque;
  return address != 0U && length != 0U ? 0 : -1;
}

static int host_dma_submit(void *opaque, uint32_t token, uintptr_t address,
                           size_t length) {
  host_context_t *context = (host_context_t *)opaque;
  (void)address;
  (void)length;
  context->last_token = token;
  context->dma_pending[token & 255U] =
      context->dma_completion_delay_polls + 1U;
  ++context->dma_outstanding;
  if (context->dma_outstanding > context->max_dma_outstanding)
    context->max_dma_outstanding = context->dma_outstanding;
  return context->force_dma_error ? -1 : 0;
}

static int host_dma_complete(void *opaque, uint32_t token) {
  host_context_t *context = (host_context_t *)opaque;
  uint32_t *pending = &context->dma_pending[token & 255U];
  if (*pending == 0U)
    return -1;
  --*pending;
  if (*pending != 0U)
    return 1;
  --context->dma_outstanding;
  return 0;
}

static int host_remote_verify(void *opaque, uint32_t stream_id,
                              uint32_t object_id, uint32_t generation,
                              uint64_t offset, const uint8_t *data,
                              size_t length, int final_segment) {
  host_context_t *context = (host_context_t *)opaque;
  (void)stream_id;
  (void)object_id;
  (void)generation;
  (void)offset;
  (void)data;
  (void)final_segment;
  context->verified_bytes += length;
  return 0;
}

static int host_atomic_commit(void *opaque, uint32_t stream_id,
                              uint32_t object_id, uint32_t generation,
                              uint64_t total_length, uint32_t crc32,
                              const uint8_t sha256[32]) {
  host_context_t *context = (host_context_t *)opaque;
  (void)stream_id;
  (void)object_id;
  (void)generation;
  (void)crc32;
  (void)sha256;
  if (context->verified_bytes != total_length)
    return -1;
  context->committed_bytes = total_length;
  return 0;
}

static void host_watchdog(void *opaque) {
  ++((host_context_t *)opaque)->watchdog_kicks;
}

static void host_telemetry(void *opaque, const void *snapshot,
                           size_t snapshot_size) {
  host_context_t *context = (host_context_t *)opaque;
  (void)snapshot;
  if (snapshot_size == sizeof(p10_1_perf_counters_t))
    ++context->telemetry_count;
}

static p10_1_hal_t host_hal(host_context_t *context) {
  p10_1_hal_t hal;
  memset(&hal, 0, sizeof(hal));
  hal.context = context;
  hal.timer_now = host_timer_now;
  hal.timer_frequency = host_timer_frequency;
  hal.payload_generate = host_generate;
  hal.integrity_begin = host_integrity_begin;
  hal.integrity_update = host_integrity_update;
  hal.integrity_final = host_integrity_final;
  hal.cache_flush = host_cache;
  hal.cache_invalidate = host_cache;
  hal.dma_submit = host_dma_submit;
  hal.dma_poll_complete = host_dma_complete;
  hal.remote_verify_segment = host_remote_verify;
  hal.remote_atomic_commit = host_atomic_commit;
  hal.watchdog_kick = host_watchdog;
  hal.telemetry_publish = host_telemetry;
  return hal;
}

static p10_1_perf_config_t valid_config(uint64_t total_bytes,
                                        uint32_t segment_bytes) {
  p10_1_perf_config_t config;
  memset(&config, 0, sizeof(config));
  config.schema_version = P10_1_SERVICE_SCHEMA_VERSION;
  config.direction = 0U;
  config.lane_mask = 3U;
  config.duration_seconds = 30U;
  config.total_bytes = total_bytes;
  config.object_size_bytes = (uint32_t)total_bytes;
  config.segment_size_bytes = segment_bytes;
  config.payload_pattern = 2U;
  config.seed = 20260731U;
  config.buffer_count = 4U;
  config.ring_depth = 16U;
  config.descriptor_batch = 4U;
  config.ack_threshold = 16U;
  config.outstanding = 32U;
  config.hash_mode = 1U;
  config.formal_window = 1U;
  config.stream_id = 17U;
  config.object_id = 31U;
  config.generation = 7U;
  return config;
}

static int run_clean(void) {
  host_context_t context = {0};
  p10_1_service_t service;
  p10_1_trace_record_t trace[256];
  p10_1_trace_record_t snapshot_trace[256];
  p10_1_perf_counters_t counters;
  p10_1_hal_t platform;
  p10_1_hal_t bound;
  p10_1_perf_config_t config;
  uint8_t storage[4][4096];
  uint8_t *buffers[4] = {storage[0], storage[1], storage[2], storage[3]};
  uint32_t trace_generation;
  uint64_t trace_overflow;
  uint32_t trace_count;
  int result;
  context.frequency = 64000000U;
  context.dma_completion_delay_polls = 1U;
  platform = host_hal(&context);
  if (p10_1_host_hal_bind(&bound, &platform) != 0)
    return 1;
  if (p10_1_service_init(&service, &bound, trace, 256U, buffers, 4U,
                         sizeof(storage[0])) != 0)
    return 2;
  config = valid_config(64U * 1024U, sizeof(storage[0]));
  if (p10_1_service_configure(&service, &config) != 0 ||
      p10_1_service_command(&service, P10_1_COMMAND_PERF_CONFIG) != 0 ||
      p10_1_service_command(&service, P10_1_COMMAND_PERF_START) != 0)
    return 3;
  do {
    result = p10_1_service_step(&service);
  } while (result == 0);
  if (result != 1 || service.state != P10_1_SERVICE_COMPLETE ||
      context.generated_bytes != config.total_bytes ||
      context.integrity_bytes != config.total_bytes ||
      context.verified_bytes != config.total_bytes ||
      context.committed_bytes != config.total_bytes)
    return 4;
  if (p10_1_service_snapshot(&service, &counters) != 0 ||
      counters.application_bytes_committed != config.total_bytes ||
      counters.descriptors_submitted != counters.descriptors_completed ||
      counters.queue_occupancy_high_watermark < 2U ||
      context.max_dma_outstanding < 2U ||
      counters.atomic_commit_count != 1U ||
      counters.descriptor_leak_count != 0U ||
      counters.double_completion_count != 0U)
    return 5;
  trace_count = p10_1_trace_snapshot(&service.trace, snapshot_trace, 256U,
                                     &trace_generation, &trace_overflow);
  if (trace_count == 0U || trace_overflow != 0U ||
      context.telemetry_count != 1U)
    return 6;
  return 0;
}

static int run_abort_restart(void) {
  host_context_t context = {0};
  p10_1_service_t service;
  p10_1_trace_record_t trace[16];
  p10_1_hal_t hal;
  p10_1_perf_config_t config;
  uint8_t storage[2][1024];
  uint8_t *buffers[2] = {storage[0], storage[1]};
  context.frequency = 64000000U;
  hal = host_hal(&context);
  if (p10_1_service_init(&service, &hal, trace, 16U, buffers, 2U,
                         sizeof(storage[0])) != 0)
    return 1;
  config = valid_config(4096U, sizeof(storage[0]));
  config.buffer_count = 2U;
  if (p10_1_service_configure(&service, &config) != 0 ||
      p10_1_service_command(&service, P10_1_COMMAND_PERF_START) != 0 ||
      p10_1_service_step(&service) != 0 ||
      p10_1_service_command(&service, P10_1_COMMAND_PERF_ABORT) != 0 ||
      service.state != P10_1_SERVICE_ABORTED ||
      service.counters.application_bytes_committed != 0U)
    return 2;
  if (p10_1_service_command(&service, P10_1_COMMAND_PERF_CLEAR) != 0 ||
      p10_1_service_configure(&service, &config) != 0)
    return 3;
  return 0;
}

static int run_fail_closed(void) {
  host_context_t context = {0};
  p10_1_service_t service;
  p10_1_trace_record_t trace[16];
  p10_1_hal_t hal;
  p10_1_perf_config_t config;
  uint8_t storage[2][1024];
  uint8_t *buffers[2] = {storage[0], storage[1]};
  context.frequency = 64000000U;
  context.force_dma_error = 1U;
  hal = host_hal(&context);
  if (p10_1_service_init(&service, &hal, trace, 16U, buffers, 2U,
                         sizeof(storage[0])) != 0)
    return 1;
  config = valid_config(4096U, sizeof(storage[0]));
  config.buffer_count = 2U;
  if (p10_1_service_configure(&service, &config) != 0 ||
      p10_1_service_command(&service, P10_1_COMMAND_PERF_START) != 0)
    return 2;
  if (p10_1_service_step(&service) >= 0 ||
      service.state != P10_1_SERVICE_FAULT ||
      service.counters.application_bytes_committed != 0U)
    return 3;
  return 0;
}

int main(void) {
  int clean = run_clean();
  int abort_restart = run_abort_restart();
  int fail_closed = run_fail_closed();
  if (clean != 0 || abort_restart != 0 || fail_closed != 0) {
    fprintf(stderr, "clean=%d abort_restart=%d fail_closed=%d\n",
            clean, abort_restart, fail_closed);
    return 1;
  }
  puts("P10_1_HOST_NATIVE_PRODUCTION_SERVICE=PASS");
  puts("P10_1_BUFFER_OWNERSHIP=PASS");
  puts("P10_1_DESCRIPTOR_BATCHING=PASS");
  puts("P10_1_ABORT_RESTART=PASS");
  puts("P10_1_COUNTER_SNAPSHOT=PASS");
  return 0;
}
