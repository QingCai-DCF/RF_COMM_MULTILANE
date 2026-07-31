#include "p10_1_service.h"

#include <string.h>

static int p10_1_power_of_two(uint32_t value) {
  return value >= 2U && (value & (value - 1U)) == 0U;
}

int p10_1_trace_init(p10_1_trace_ring_t *ring,
                     p10_1_trace_record_t *storage, uint32_t depth) {
  if (ring == NULL || storage == NULL || !p10_1_power_of_two(depth))
    return -1;
  memset(storage, 0, sizeof(*storage) * depth);
  memset(ring, 0, sizeof(*ring));
  ring->records = storage;
  ring->depth = depth;
  return 0;
}

void p10_1_trace_push(p10_1_trace_ring_t *ring, uint64_t timestamp,
                      uint32_t event_id, uint32_t arg0, uint32_t arg1) {
  p10_1_trace_record_t *record;
  uint32_t outstanding;
  if (ring == NULL || ring->records == NULL || ring->depth == 0U)
    return;
  outstanding = ring->write_index - ring->read_index;
  if (outstanding >= ring->depth) {
    ++ring->overflow_count;
    return; /* Debug overflow is deliberately non-blocking. */
  }
  record = &ring->records[ring->write_index & (ring->depth - 1U)];
  record->timestamp = timestamp;
  record->generation = ring->write_generation;
  record->event_id = event_id;
  record->arg0 = arg0;
  record->arg1 = arg1;
  record->reserved0 = 0U;
  record->reserved1 = 0U;
  ++ring->write_index;
  if ((ring->write_index & (ring->depth - 1U)) == 0U)
    ++ring->write_generation;
}

uint32_t p10_1_trace_snapshot(const p10_1_trace_ring_t *ring,
                             p10_1_trace_record_t *output, uint32_t capacity,
                             uint32_t *generation, uint64_t *overflow_count) {
  uint32_t count;
  uint32_t index;
  if (ring == NULL || output == NULL || generation == NULL ||
      overflow_count == NULL || ring->records == NULL)
    return 0U;
  count = ring->write_index - ring->read_index;
  if (count > ring->depth)
    count = ring->depth;
  if (count > capacity)
    count = capacity;
  for (index = 0U; index < count; ++index)
    output[index] =
        ring->records[(ring->read_index + index) & (ring->depth - 1U)];
  *generation = ring->write_generation;
  *overflow_count = ring->overflow_count;
  return count;
}

void p10_1_trace_clear(p10_1_trace_ring_t *ring) {
  if (ring == NULL)
    return;
  ring->read_index = ring->write_index;
  ++ring->clear_generation;
}
