#include "p10_1_service.h"

#include <string.h>

enum {
  P10_1_OWNER_POOL = 0,
  P10_1_OWNER_GENERATOR = 1,
  P10_1_OWNER_DMA = 2,
  P10_1_OWNER_REMOTE = 3,
  P10_1_OWNER_RECLAIM = 4
};

static uint64_t p10_1_now(p10_1_service_t *service) {
  return service->hal.timer_now(service->hal.context);
}

static void p10_1_event(p10_1_service_t *service, uint32_t event_id,
                        uint32_t arg0, uint32_t arg1) {
  p10_1_trace_push(&service->trace, p10_1_now(service), event_id, arg0, arg1);
}

static void p10_1_zero_counters(p10_1_service_t *service) {
  uint32_t generation = service->counters.snapshot_generation + 2U;
  memset(&service->counters, 0, sizeof(service->counters));
  service->counters.snapshot_generation = generation;
}

static int p10_1_hal_complete(const p10_1_hal_t *hal) {
  return hal != NULL && hal->timer_now != NULL &&
         hal->timer_frequency != NULL && hal->payload_generate != NULL &&
         hal->integrity_begin != NULL && hal->integrity_update != NULL &&
         hal->integrity_final != NULL && hal->cache_flush != NULL &&
         hal->cache_invalidate != NULL && hal->dma_submit != NULL &&
         hal->dma_poll_complete != NULL &&
         hal->remote_verify_segment != NULL &&
         hal->remote_atomic_commit != NULL && hal->watchdog_kick != NULL;
}

int p10_1_service_init(p10_1_service_t *service, const p10_1_hal_t *hal,
                       p10_1_trace_record_t *trace_storage,
                       uint32_t trace_depth, uint8_t **buffers,
                       uint32_t buffer_count, uint32_t buffer_capacity) {
  uint32_t index;
  if (service == NULL || !p10_1_hal_complete(hal) || buffers == NULL ||
      buffer_count < 2U || buffer_count > P10_1_SERVICE_MAX_BUFFERS ||
      buffer_capacity == 0U)
    return -1;
  memset(service, 0, sizeof(*service));
  service->hal = *hal;
  if (p10_1_trace_init(&service->trace, trace_storage, trace_depth) != 0)
    return -2;
  for (index = 0U; index < buffer_count; ++index) {
    if (buffers[index] == NULL)
      return -3;
    service->buffers[index].address = buffers[index];
    service->buffers[index].capacity = buffer_capacity;
    service->buffers[index].state = P10_1_BUFFER_FREE;
    service->buffers[index].owner = P10_1_OWNER_POOL;
  }
  service->config.buffer_count = buffer_count;
  service->state = P10_1_SERVICE_READY;
  return 0;
}

int p10_1_service_configure(p10_1_service_t *service,
                            const p10_1_perf_config_t *config) {
  if (service == NULL || config == NULL ||
      service->state == P10_1_SERVICE_RUNNING ||
      config->schema_version != P10_1_SERVICE_SCHEMA_VERSION ||
      config->lane_mask == 0U || (config->lane_mask & ~UINT32_C(0x3)) != 0U ||
      config->total_bytes == 0U ||
      config->total_bytes > P10_1_MAX_STREAM_SIZE_BYTES ||
      config->segment_size_bytes == 0U ||
      config->segment_size_bytes > service->buffers[0].capacity ||
      config->buffer_count < 2U ||
      config->buffer_count > service->config.buffer_count ||
      config->ring_depth < config->descriptor_batch ||
      config->outstanding == 0U)
    return -1;
  service->config = *config;
  service->next_offset = 0U;
  service->next_verify_offset = 0U;
  service->next_buffer = 0U;
  service->next_descriptor_token = 1U;
  service->outstanding_descriptors = 0U;
  service->fault_code = 0U;
  service->state = P10_1_SERVICE_CONFIGURED;
  return 0;
}

static void p10_1_reclaim_all(p10_1_service_t *service) {
  uint32_t index;
  for (index = 0U; index < service->config.buffer_count; ++index) {
    p10_1_buffer_t *buffer = &service->buffers[index];
    if (buffer->state != P10_1_BUFFER_FREE) {
      buffer->state = P10_1_BUFFER_RECLAIMABLE;
      buffer->owner = P10_1_OWNER_RECLAIM;
      buffer->length = 0U;
      buffer->offset = 0U;
      buffer->final_segment = 0U;
      ++buffer->generation;
      buffer->state = P10_1_BUFFER_FREE;
      buffer->owner = P10_1_OWNER_POOL;
    }
  }
  service->outstanding_descriptors = 0U;
}

int p10_1_service_command(p10_1_service_t *service,
                          p10_1_perf_command_t command) {
  if (service == NULL)
    return -1;
  switch (command) {
    case P10_1_COMMAND_PERF_CAPS:
    case P10_1_COMMAND_PERF_STATUS:
    case P10_1_COMMAND_PERF_SNAPSHOT:
      return 0;
    case P10_1_COMMAND_PERF_CONFIG:
      return service->state == P10_1_SERVICE_CONFIGURED ? 0 : -2;
    case P10_1_COMMAND_PERF_START:
      if (service->state != P10_1_SERVICE_CONFIGURED)
        return -3;
      p10_1_zero_counters(service);
      service->counters.start_ticks = p10_1_now(service);
      service->hal.integrity_begin(service->hal.context);
      service->state = P10_1_SERVICE_RUNNING;
      p10_1_event(service, P10_1_TRACE_PERF_START,
                  service->config.stream_id, service->config.object_id);
      return 0;
    case P10_1_COMMAND_PERF_STOP:
      if (service->state != P10_1_SERVICE_RUNNING)
        return -4;
      service->state = P10_1_SERVICE_STOPPING;
      return 0;
    case P10_1_COMMAND_PERF_ABORT:
      if (service->state != P10_1_SERVICE_RUNNING &&
          service->state != P10_1_SERVICE_STOPPING)
        return -5;
      p10_1_reclaim_all(service);
      ++service->counters.abort_count;
      service->counters.end_ticks = p10_1_now(service);
      service->state = P10_1_SERVICE_ABORTED;
      p10_1_event(service, P10_1_TRACE_OBJECT_FAIL, 0U, 0U);
      return 0;
    case P10_1_COMMAND_PERF_CLEAR:
      if (service->state == P10_1_SERVICE_RUNNING)
        return -6;
      p10_1_reclaim_all(service);
      p10_1_zero_counters(service);
      p10_1_trace_clear(&service->trace);
      service->state = P10_1_SERVICE_READY;
      return 0;
    default:
      return -7;
  }
}

static int p10_1_fail(p10_1_service_t *service, uint32_t fault_code) {
  service->fault_code = fault_code;
  service->state = P10_1_SERVICE_FAULT;
  p10_1_reclaim_all(service);
  p10_1_event(service, P10_1_TRACE_OBJECT_FAIL, fault_code, 0U);
  return -(int)fault_code;
}

static p10_1_buffer_t *p10_1_find_free(p10_1_service_t *service) {
  uint32_t scan;
  for (scan = 0U; scan < service->config.buffer_count; ++scan) {
    uint32_t index = (service->next_buffer + scan) %
                     service->config.buffer_count;
    if (service->buffers[index].state == P10_1_BUFFER_FREE) {
      service->next_buffer = (index + 1U) % service->config.buffer_count;
      return &service->buffers[index];
    }
  }
  return NULL;
}

static int p10_1_prepare_and_submit(p10_1_service_t *service) {
  p10_1_buffer_t *buffer;
  uint64_t remaining;
  uint64_t prepare_start;
  uint64_t hash_start;
  uint32_t length;
  uint32_t token;
  int final_segment;
  if (service->next_offset >= service->config.total_bytes)
    return 0;
  if (service->outstanding_descriptors >= service->config.outstanding ||
      service->outstanding_descriptors >= service->config.ring_depth)
    return 0;
  buffer = p10_1_find_free(service);
  if (buffer == NULL)
    return 0;
  buffer->state = P10_1_BUFFER_FILLING;
  buffer->owner = P10_1_OWNER_GENERATOR;
  buffer->offset = service->next_offset;
  p10_1_event(service, P10_1_TRACE_OBJECT_ALLOC,
              (uint32_t)(buffer - service->buffers), buffer->generation);
  remaining = service->config.total_bytes - service->next_offset;
  length = remaining < service->config.segment_size_bytes
               ? (uint32_t)remaining
               : service->config.segment_size_bytes;
  final_segment = remaining == length;
  buffer->final_segment = final_segment ? 1U : 0U;
  prepare_start = p10_1_now(service);
  p10_1_event(service, P10_1_TRACE_PAYLOAD_PREP_START, length, 0U);
  if (service->hal.payload_generate(
          service->hal.context, service->config.payload_pattern,
          service->config.seed, service->next_offset, buffer->address,
          length) != 0)
    return p10_1_fail(service, 3U);
  p10_1_event(service, P10_1_TRACE_PAYLOAD_PREP_END, length, 0U);
  service->counters.ps_prepare_ticks += p10_1_now(service) - prepare_start;
  hash_start = p10_1_now(service);
  p10_1_event(service, P10_1_TRACE_CRC_START, length, 0U);
  service->hal.integrity_update(service->hal.context, buffer->address, length);
  p10_1_event(service, P10_1_TRACE_CRC_END, length, 0U);
  service->counters.crc_sha_ticks += p10_1_now(service) - hash_start;
  p10_1_event(service, P10_1_TRACE_CACHE_FLUSH_START, length, 0U);
  if (service->hal.cache_flush(service->hal.context,
                               (uintptr_t)buffer->address, length) != 0)
    return p10_1_fail(service, 4U);
  p10_1_event(service, P10_1_TRACE_CACHE_FLUSH_END, length, 0U);
  buffer->length = length;
  buffer->state = P10_1_BUFFER_READY;
  buffer->owner = P10_1_OWNER_DMA;
  token = service->next_descriptor_token++;
  buffer->descriptor_token = token;
  p10_1_event(service, P10_1_TRACE_DESC_SUBMIT, token, length);
  if (service->hal.dma_submit(service->hal.context, token,
                              (uintptr_t)buffer->address, length) != 0)
    return p10_1_fail(service, 5U);
  ++service->counters.descriptors_submitted;
  ++service->outstanding_descriptors;
  if (service->outstanding_descriptors >
      service->counters.queue_occupancy_high_watermark)
    service->counters.queue_occupancy_high_watermark =
        service->outstanding_descriptors;
  buffer->state = P10_1_BUFFER_DMA_OWNED;
  p10_1_event(service, P10_1_TRACE_DMA_TX_START, token, length);
  service->next_offset += length;
  return 1;
}

static int p10_1_poll_dma(p10_1_service_t *service) {
  uint32_t index;
  for (index = 0U; index < service->config.buffer_count; ++index) {
    p10_1_buffer_t *buffer = &service->buffers[index];
    int status;
    if (buffer->state != P10_1_BUFFER_DMA_OWNED)
      continue;
    status = service->hal.dma_poll_complete(
        service->hal.context, buffer->descriptor_token);
    if (status < 0)
      return p10_1_fail(service, 6U);
    if (status > 0) {
      ++service->counters.dma_stall_cycles;
      continue;
    }
    ++service->counters.descriptors_completed;
    p10_1_event(service, P10_1_TRACE_DMA_TX_END,
                buffer->descriptor_token, buffer->length);
    buffer->state = P10_1_BUFFER_IN_FLIGHT;
  }
  return 0;
}

static p10_1_buffer_t *p10_1_next_verify_buffer(
    p10_1_service_t *service) {
  uint32_t index;
  for (index = 0U; index < service->config.buffer_count; ++index) {
    p10_1_buffer_t *buffer = &service->buffers[index];
    if (buffer->state == P10_1_BUFFER_IN_FLIGHT &&
        buffer->offset == service->next_verify_offset)
      return buffer;
  }
  return NULL;
}

static int p10_1_verify_one(p10_1_service_t *service) {
  p10_1_buffer_t *buffer = p10_1_next_verify_buffer(service);
  int final_segment;
  if (buffer == NULL)
    return 0;
  final_segment = buffer->final_segment != 0U;
  buffer->state = P10_1_BUFFER_REMOTE_RECEIVED;
  buffer->owner = P10_1_OWNER_REMOTE;
  p10_1_event(service, P10_1_TRACE_REMOTE_RX_COMPLETE,
              buffer->descriptor_token, buffer->length);
  buffer->state = P10_1_BUFFER_VERIFYING;
  p10_1_event(service, P10_1_TRACE_CACHE_INVALIDATE_START,
              buffer->descriptor_token, buffer->length);
  if (service->hal.cache_invalidate(
          service->hal.context, (uintptr_t)buffer->address,
          buffer->length) != 0)
    return p10_1_fail(service, 10U);
  p10_1_event(service, P10_1_TRACE_CACHE_INVALIDATE_END,
              buffer->descriptor_token, buffer->length);
  if (service->hal.remote_verify_segment(
          service->hal.context, service->config.stream_id,
          service->config.object_id, service->config.generation,
          buffer->offset, buffer->address, buffer->length,
          final_segment) != 0)
    return p10_1_fail(service, 7U);
  service->counters.application_bytes_accepted += buffer->length;
  service->counters.frame_bytes_acked += buffer->length;
  service->counters.wire_bytes += buffer->length;
  service->next_verify_offset += buffer->length;
  if (service->outstanding_descriptors == 0U) {
    ++service->counters.double_completion_count;
    return p10_1_fail(service, 11U);
  }
  --service->outstanding_descriptors;
  if (final_segment) {
    if (service->hal.integrity_final(service->hal.context,
                                     &service->final_crc32,
                                     service->final_sha256) != 0)
      return p10_1_fail(service, 8U);
    p10_1_event(service, P10_1_TRACE_HASH_VERIFY_COMPLETE,
                service->final_crc32, 0U);
    if (service->hal.remote_atomic_commit(
            service->hal.context, service->config.stream_id,
            service->config.object_id, service->config.generation,
            service->config.total_bytes, service->final_crc32,
            service->final_sha256) != 0)
      return p10_1_fail(service, 9U);
    service->counters.application_bytes_committed =
        service->config.total_bytes;
    ++service->counters.atomic_commit_count;
    p10_1_event(service, P10_1_TRACE_ATOMIC_COMMIT,
                service->config.object_id, service->config.generation);
    service->counters.end_ticks = p10_1_now(service);
    service->state = P10_1_SERVICE_COMPLETE;
    p10_1_event(service, P10_1_TRACE_PERF_STOP, 0U, 0U);
  }
  buffer->state = P10_1_BUFFER_COMMITTED;
  buffer->state = P10_1_BUFFER_RECLAIMABLE;
  buffer->owner = P10_1_OWNER_RECLAIM;
  ++buffer->generation;
  buffer->length = 0U;
  buffer->offset = 0U;
  buffer->final_segment = 0U;
  buffer->state = P10_1_BUFFER_FREE;
  buffer->owner = P10_1_OWNER_POOL;
  return service->state == P10_1_SERVICE_COMPLETE ? 1 : 0;
}

int p10_1_service_step(p10_1_service_t *service) {
  uint32_t submitted = 0U;
  int result;
  if (service == NULL)
    return -1;
  if (service->state == P10_1_SERVICE_STOPPING) {
    p10_1_reclaim_all(service);
    service->counters.end_ticks = p10_1_now(service);
    service->state = P10_1_SERVICE_COMPLETE;
    p10_1_event(service, P10_1_TRACE_PERF_STOP, 0U, 0U);
    return 1;
  }
  if (service->state != P10_1_SERVICE_RUNNING)
    return 0;
  result = p10_1_poll_dma(service);
  if (result < 0)
    return result;
  result = p10_1_verify_one(service);
  if (result != 0)
    return result;
  while (submitted < service->config.descriptor_batch) {
    result = p10_1_prepare_and_submit(service);
    if (result < 0)
      return result;
    if (result == 0)
      break;
    ++submitted;
  }
  if (service->next_offset >= service->config.total_bytes &&
      service->outstanding_descriptors == 0U &&
      service->state == P10_1_SERVICE_RUNNING)
    return p10_1_fail(service, 20U);
  service->hal.watchdog_kick(service->hal.context);
  ++service->counters.watchdog_kick_count;
  service->counters.trace_overflow_count = service->trace.overflow_count;
  return 0;
}

int p10_1_service_snapshot(p10_1_service_t *service,
                           p10_1_perf_counters_t *snapshot) {
  uint32_t generation;
  if (service == NULL || snapshot == NULL)
    return -1;
  generation = service->counters.snapshot_generation;
  service->counters.snapshot_generation = generation + 1U;
  *snapshot = service->counters;
  snapshot->snapshot_generation = generation + 2U;
  service->counters.snapshot_generation = generation + 2U;
  if (service->hal.telemetry_publish != NULL)
    service->hal.telemetry_publish(service->hal.context, snapshot,
                                   sizeof(*snapshot));
  return 0;
}
