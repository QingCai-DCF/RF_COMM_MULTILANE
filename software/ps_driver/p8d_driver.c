#include "p8d_driver.h"

#include <string.h>

#include "ir_regs.h"

_Static_assert(sizeof(p8d_descriptor_t) == P8D_DESCRIPTOR_BYTES,
               "P8D descriptor layout must remain 64 bytes");

enum {
  P8D_DESC_VERSION_SHIFT = 0,
  P8D_DESC_STATE_SHIFT = 8,
  P8D_DESC_GENERATION_SHIFT = 16,
  P8D_DESC_VERSION_MASK = 0xFFu,
  P8D_DESC_STATE_MASK = 0xFFu,
};

static uint32_t descriptor_header(uint8_t state, uint16_t generation) {
  return 1u | ((uint32_t)state << P8D_DESC_STATE_SHIFT) |
         ((uint32_t)generation << P8D_DESC_GENERATION_SHIFT);
}
static uint8_t descriptor_state(const p8d_descriptor_t *descriptor) {
  return (uint8_t)((descriptor->version_state_generation >> P8D_DESC_STATE_SHIFT) &
                   P8D_DESC_STATE_MASK);
}

static uint16_t descriptor_generation(const p8d_descriptor_t *descriptor) {
  return (uint16_t)(descriptor->version_state_generation >> P8D_DESC_GENERATION_SHIFT);
}

static int valid_driver(const p8d_driver_t *driver) {
  return driver != NULL && driver->io.read32 != NULL && driver->io.write32 != NULL;
}

static int cache_flush(p8d_driver_t *driver, uintptr_t address, size_t length) {
  if (driver->cache.flush != NULL && driver->cache.flush(driver->cache.ctx, address, length) != 0) {
    return P8D_ERR_CACHE;
  }
  if (driver->cache.ownership_barrier != NULL) {
    driver->cache.ownership_barrier(driver->cache.ctx);
  }
  return P8D_OK;
}

static int cache_invalidate(p8d_driver_t *driver, uintptr_t address, size_t length) {
  if (driver->cache.invalidate != NULL &&
      driver->cache.invalidate(driver->cache.ctx, address, length) != 0) {
    return P8D_ERR_CACHE;
  }
  if (driver->cache.ownership_barrier != NULL) {
    driver->cache.ownership_barrier(driver->cache.ctx);
  }
  return P8D_OK;
}

static int init_ring(p8d_ring_t *ring, p8d_descriptor_t *descriptors,
                     uint32_t depth, int receive_ring) {
  uint32_t index;
  if (ring == NULL || descriptors == NULL || depth < 2u || depth > 65536u) {
    return P8D_ERR_ARGUMENT;
  }
  if (((uintptr_t)descriptors & (P8D_DESCRIPTOR_ALIGNMENT_BYTES - 1u)) != 0u) {
    return P8D_ERR_ARGUMENT;
  }
  memset(descriptors, 0, (size_t)depth * sizeof(*descriptors));
  ring->descriptors = descriptors;
  ring->depth = depth;
  ring->producer = 0u;
  ring->consumer = 0u;
  ring->generation = 1u;
  ring->is_rx = receive_ring ? 1u : 0u;
  for (index = 0u; index < depth; index++) {
    descriptors[index].version_state_generation =
        descriptor_header(P8D_DESC_FREE, ring->generation);
    descriptors[index].next_index = (index + 1u) % depth;
  }
  return P8D_OK;
}

static int post_descriptor(p8d_driver_t *driver, p8d_ring_t *ring,
                           uintptr_t buffer_address, uint32_t capacity,
                           uint32_t requested_length, uint32_t stream_id,
                           uint32_t object_id, uint32_t user_tag) {
  p8d_descriptor_t *descriptor;
  uint32_t index;
  int rc;
  if (!valid_driver(driver) || ring == NULL || ring->descriptors == NULL ||
      capacity == 0u || requested_length > capacity) {
    return P8D_ERR_ARGUMENT;
  }
  if (ring->producer - ring->consumer >= ring->depth) {
    return P8D_ERR_RING_FULL;
  }
  index = ring->producer % ring->depth;
  descriptor = &ring->descriptors[index];
  if (descriptor_state(descriptor) != P8D_DESC_FREE &&
      descriptor_state(descriptor) != P8D_DESC_CPU_RECLAIMED) {
    return P8D_ERR_OWNERSHIP;
  }
  memset(descriptor, 0, sizeof(*descriptor));
  descriptor->version_state_generation =
      descriptor_header(P8D_DESC_CPU_PREPARED, ring->generation);
  descriptor->buffer_address = (uint64_t)buffer_address;
  descriptor->buffer_capacity = capacity;
  descriptor->requested_length = requested_length;
  descriptor->stream_id = stream_id;
  descriptor->object_id = object_id;
  descriptor->user_tag = user_tag;
  descriptor->session_epoch = driver->session_epoch;
  descriptor->next_index = (index + 1u) % ring->depth;
  rc = cache_flush(driver, buffer_address, requested_length);
  if (rc != P8D_OK) return rc;
  rc = cache_flush(driver, (uintptr_t)descriptor, sizeof(*descriptor));
  if (rc != P8D_OK) return rc;
  descriptor->version_state_generation =
      descriptor_header(P8D_DESC_HW_OWNED, ring->generation);
  if (driver->cache.ownership_barrier != NULL) {
    driver->cache.ownership_barrier(driver->cache.ctx);
  }
  ring->producer++;
  return P8D_OK;
}

int p8d_query_capabilities(p8d_driver_t *driver, p8d_capabilities_t *capabilities) {
  if (!valid_driver(driver) || capabilities == NULL) return P8D_ERR_ARGUMENT;
  capabilities->protocol_version = driver->io.read32(driver->io.ctx, IR_REG_P8D_L2_PROTOCOL_VERSION);
  capabilities->capabilities = driver->io.read32(driver->io.ctx, IR_REG_P8D_L2_CAPABILITIES);
  capabilities->maximum_outstanding =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_TX_WINDOW_SIZE);
  capabilities->sack_window_bits =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_SACK_WINDOW_BITS);
  capabilities->sequence_width_bits = P8D_SEQUENCE_WIDTH;
  capabilities->tx_ring_depth = driver->io.read32(driver->io.ctx, IR_REG_P8D_TX_RING_DEPTH);
  capabilities->rx_ring_depth = driver->io.read32(driver->io.ctx, IR_REG_P8D_RX_RING_DEPTH);
  capabilities->axis_data_width_bits = (capabilities->capabilities >> 16) & 0xFFu;
  if (capabilities->protocol_version != P8D_VNEXT_MODE_VERSION ||
      capabilities->maximum_outstanding < 32u || capabilities->sack_window_bits < 32u) {
    return P8D_ERR_CAPABILITY;
  }
  return P8D_OK;
}

int p8d_configure_session(p8d_driver_t *driver, const p8d_session_config_t *config) {
  if (!valid_driver(driver) || config == NULL ||
      (config->protocol_mode != P8D_LEGACY_MODE_VERSION &&
       config->protocol_mode != P8D_VNEXT_MODE_VERSION)) return P8D_ERR_ARGUMENT;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_SESSION_EPOCH, config->session_epoch);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_PATH_EPOCH, config->path_epoch);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_PROTOCOL_MODE, config->protocol_mode);
  driver->session_epoch = config->session_epoch;
  return P8D_OK;
}

int p8d_configure_window(p8d_driver_t *driver, const p8d_window_config_t *config) {
  if (!valid_driver(driver) || config == NULL || config->tx_window_size < 32u ||
      config->rx_window_size < 32u || config->sack_window_bits < 32u ||
      config->sack_window_bits > config->tx_window_size ||
      config->maximum_retry > P8D_MAX_RETRY) return P8D_ERR_ARGUMENT;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_TX_WINDOW_SIZE, config->tx_window_size);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_RX_WINDOW_SIZE, config->rx_window_size);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_SACK_WINDOW_BITS, config->sack_window_bits);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_RETRY_CONFIG,
                     (config->maximum_retry & 0xFFu) | (config->rto_initial_cycles << 8));
  return P8D_OK;
}

int p8d_configure_scheduler(p8d_driver_t *driver, const p8d_scheduler_config_t *config) {
  uint32_t lane;
  if (!valid_driver(driver) || config == NULL || config->active_lane_mask == 0u ||
      config->starvation_bound == 0u) return P8D_ERR_ARGUMENT;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_SCHEDULER_ACTIVE_MASK,
                     config->active_lane_mask);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_SCHEDULER_STARVATION_BOUND,
                     config->starvation_bound);
  for (lane = 0u; lane < 8u; lane++) {
    if (config->weights[lane] == 0u) return P8D_ERR_ARGUMENT;
    driver->io.write32(driver->io.ctx,
                       IR_REG_P8D_SCHEDULER_WEIGHT0 + lane * 4u,
                       config->weights[lane]);
  }
  return P8D_OK;
}

int p8d_init_tx_ring(p8d_driver_t *driver, p8d_descriptor_t *descriptors, uint32_t depth) {
  if (driver == NULL) return P8D_ERR_ARGUMENT;
  return init_ring(&driver->tx_ring, descriptors, depth, 0);
}

int p8d_init_rx_ring(p8d_driver_t *driver, p8d_descriptor_t *descriptors, uint32_t depth) {
  if (driver == NULL) return P8D_ERR_ARGUMENT;
  return init_ring(&driver->rx_ring, descriptors, depth, 1);
}

int p8d_submit_tx_descriptor(p8d_driver_t *driver, uintptr_t buffer_address,
                             uint32_t length, uint32_t stream_id,
                             uint32_t object_id, uint32_t user_tag) {
  return post_descriptor(driver, &driver->tx_ring, buffer_address, length, length,
                         stream_id, object_id, user_tag);
}

int p8d_post_rx_descriptor(p8d_driver_t *driver, uintptr_t buffer_address,
                           uint32_t capacity, uint32_t stream_id,
                           uint32_t object_id, uint32_t user_tag) {
  return post_descriptor(driver, &driver->rx_ring, buffer_address, capacity, capacity,
                         stream_id, object_id, user_tag);
}

int p8d_poll_completion(p8d_driver_t *driver, int receive_ring,
                        p8d_descriptor_t **descriptor) {
  p8d_ring_t *ring;
  p8d_descriptor_t *candidate;
  int rc;
  if (driver == NULL || descriptor == NULL) return P8D_ERR_ARGUMENT;
  ring = receive_ring ? &driver->rx_ring : &driver->tx_ring;
  if (ring->consumer >= ring->producer) return P8D_ERR_NO_COMPLETION;
  candidate = &ring->descriptors[ring->consumer % ring->depth];
  rc = cache_invalidate(driver, (uintptr_t)candidate, sizeof(*candidate));
  if (rc != P8D_OK) return rc;
  if (descriptor_generation(candidate) != ring->generation) return P8D_ERR_STALE_GENERATION;
  if (descriptor_state(candidate) != P8D_DESC_HW_COMPLETED &&
      descriptor_state(candidate) != P8D_DESC_ERROR &&
      descriptor_state(candidate) != P8D_DESC_ABORTED) return P8D_ERR_NO_COMPLETION;
  if (receive_ring && descriptor_state(candidate) == P8D_DESC_HW_COMPLETED) {
    rc = cache_invalidate(driver, (uintptr_t)candidate->buffer_address,
                          candidate->actual_length);
    if (rc != P8D_OK) return rc;
  }
  *descriptor = candidate;
  return P8D_OK;
}

int p8d_reap_completion(p8d_driver_t *driver, int receive_ring) {
  p8d_ring_t *ring;
  p8d_descriptor_t *descriptor;
  int rc;
  if (driver == NULL) return P8D_ERR_ARGUMENT;
  ring = receive_ring ? &driver->rx_ring : &driver->tx_ring;
  rc = p8d_poll_completion(driver, receive_ring, &descriptor);
  if (rc != P8D_OK) return rc;
  descriptor->version_state_generation =
      descriptor_header(P8D_DESC_CPU_RECLAIMED, ring->generation);
  ring->consumer++;
  return P8D_OK;
}

int p8d_abort_stream_or_object(p8d_driver_t *driver, uint32_t stream_id,
                               uint32_t object_id) {
  if (!valid_driver(driver)) return P8D_ERR_ARGUMENT;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_ABORT_STREAM_ID, stream_id);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_ABORT_OBJECT_ID, object_id);
  driver->io.write32(driver->io.ctx, IR_REG_P8D_CONTROL,
                     IR_P8D_CONTROL_ABORT_REQUEST_MASK);
  return P8D_OK;
}

int p8d_reset_data_plane(p8d_driver_t *driver) {
  uint32_t index;
  p8d_ring_t *rings[2];
  uint32_t ring_index;
  if (!valid_driver(driver)) return P8D_ERR_ARGUMENT;
  rings[0] = &driver->tx_ring;
  rings[1] = &driver->rx_ring;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_CONTROL,
                     IR_P8D_CONTROL_RESET_REQUEST_MASK);
  for (ring_index = 0u; ring_index < 2u; ring_index++) {
    p8d_ring_t *ring = rings[ring_index];
    if (ring->descriptors == NULL) continue;
    ring->generation = (uint16_t)(ring->generation + 1u);
    if (ring->generation == 0u) ring->generation = 1u;
    for (index = 0u; index < ring->depth; index++) {
      uint8_t state = descriptor_state(&ring->descriptors[index]);
      if (state == P8D_DESC_CPU_PREPARED || state == P8D_DESC_HW_OWNED) {
        ring->descriptors[index].version_state_generation =
            descriptor_header(P8D_DESC_ABORTED, ring->generation);
        ring->descriptors[index].error_code = 2u;
      } else {
        ring->descriptors[index].version_state_generation =
            descriptor_header(P8D_DESC_FREE, ring->generation);
      }
    }
    ring->consumer = ring->producer;
  }
  driver->session_epoch = 0u;
  return P8D_OK;
}

int p8d_snapshot_counters(p8d_driver_t *driver, p8d_counter_snapshot_t *snapshot) {
  if (!valid_driver(driver) || snapshot == NULL) return P8D_ERR_ARGUMENT;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_CONTROL,
                     IR_P8D_CONTROL_SNAPSHOT_REQUEST_MASK);
  snapshot->global_outstanding_count =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_GLOBAL_OUTSTANDING_COUNT);
  snapshot->global_outstanding_high_watermark =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_GLOBAL_OUTSTANDING_HIGH_WATERMARK);
  snapshot->tx_retry_count = driver->io.read32(driver->io.ctx, IR_REG_P8D_TX_RETRY_COUNT);
  snapshot->migration_count = driver->io.read32(driver->io.ctx, IR_REG_P8D_MIGRATION_COUNT);
  snapshot->rx_duplicate_count =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_RX_DUPLICATE_COUNT);
  snapshot->descriptor_complete_count =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_DESCRIPTOR_COMPLETE_COUNT);
  snapshot->descriptor_error_count =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_DESCRIPTOR_ERROR_COUNT);
  snapshot->axis_tx_stall_cycles =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_AXIS_TX_STALL_CYCLES);
  snapshot->axis_rx_stall_cycles =
      driver->io.read32(driver->io.ctx, IR_REG_P8D_AXIS_RX_STALL_CYCLES);
  return P8D_OK;
}

int p8d_clear_sticky_errors(p8d_driver_t *driver) {
  if (!valid_driver(driver)) return P8D_ERR_ARGUMENT;
  driver->io.write32(driver->io.ctx, IR_REG_P8D_CONTROL,
                     IR_P8D_CONTROL_CLEAR_STICKY_REQUEST_MASK);
  return P8D_OK;
}
