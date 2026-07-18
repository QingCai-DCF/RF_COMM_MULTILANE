#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "ir_regs.h"
#include "p8d_driver.h"

typedef struct {
  uint32_t regs[2048];
  uint32_t flush_count;
  uint32_t invalidate_count;
  uint32_t barrier_count;
} mock_t;

static uint32_t read32(void *ctx, uint32_t offset) {
  mock_t *mock = (mock_t *)ctx;
  return mock->regs[offset / 4u];
}

static void write32(void *ctx, uint32_t offset, uint32_t value) {
  mock_t *mock = (mock_t *)ctx;
  mock->regs[offset / 4u] = value;
}

static int flush(void *ctx, uintptr_t address, size_t length) {
  mock_t *mock = (mock_t *)ctx;
  if (address == 0u || length == 0u) return -1;
  mock->flush_count++;
  return 0;
}

static int invalidate(void *ctx, uintptr_t address, size_t length) {
  mock_t *mock = (mock_t *)ctx;
  if (address == 0u || length == 0u) return -1;
  mock->invalidate_count++;
  return 0;
}

static void barrier(void *ctx) {
  ((mock_t *)ctx)->barrier_count++;
}

int main(void) {
  mock_t mock;
  p8d_driver_t driver;
  p8d_capabilities_t capabilities;
  p8d_session_config_t session = {0x12345678u, 7u, P8D_VNEXT_MODE_VERSION, 0u};
  p8d_window_config_t window = {32u, 32u, 32u, 7u, 64000u};
  p8d_scheduler_config_t scheduler = {3u, {1u, 2u, 1u, 1u, 1u, 1u, 1u, 1u}, 4096u};
  p8d_descriptor_t *tx = NULL;
  p8d_descriptor_t *rx = NULL;
  p8d_descriptor_t *completion = NULL;
  uint8_t payload[128];
  int rc = 0;

  memset(&mock, 0, sizeof(mock));
  memset(&driver, 0, sizeof(driver));
  tx = (p8d_descriptor_t *)_aligned_malloc(4u * sizeof(*tx), P8D_DESCRIPTOR_ALIGNMENT_BYTES);
  rx = (p8d_descriptor_t *)_aligned_malloc(4u * sizeof(*rx), P8D_DESCRIPTOR_ALIGNMENT_BYTES);
  if (tx == NULL || rx == NULL) return 1;
  driver.io.ctx = &mock;
  driver.io.read32 = read32;
  driver.io.write32 = write32;
  driver.cache.ctx = &mock;
  driver.cache.flush = flush;
  driver.cache.invalidate = invalidate;
  driver.cache.ownership_barrier = barrier;
  mock.regs[IR_REG_P8D_L2_PROTOCOL_VERSION / 4u] = P8D_VNEXT_MODE_VERSION;
  mock.regs[IR_REG_P8D_L2_CAPABILITIES / 4u] = (32u << 16) | 0x7Fu;
  mock.regs[IR_REG_P8D_TX_WINDOW_SIZE / 4u] = 32u;
  mock.regs[IR_REG_P8D_SACK_WINDOW_BITS / 4u] = 32u;
  mock.regs[IR_REG_P8D_TX_RING_DEPTH / 4u] = 64u;
  mock.regs[IR_REG_P8D_RX_RING_DEPTH / 4u] = 64u;
  if (p8d_query_capabilities(&driver, &capabilities) != P8D_OK) rc = 2;
  if (!rc && p8d_configure_session(&driver, &session) != P8D_OK) rc = 3;
  if (!rc && p8d_configure_window(&driver, &window) != P8D_OK) rc = 4;
  if (!rc && p8d_configure_scheduler(&driver, &scheduler) != P8D_OK) rc = 5;
  if (!rc && p8d_init_tx_ring(&driver, tx, 4u) != P8D_OK) rc = 6;
  if (!rc && p8d_init_rx_ring(&driver, rx, 4u) != P8D_OK) rc = 7;
  memset(payload, 0xA5, sizeof(payload));
  if (!rc && p8d_submit_tx_descriptor(&driver, (uintptr_t)payload, sizeof(payload),
                                       3u, 4u, 5u) != P8D_OK) rc = 8;
  if (!rc) {
    tx[0].actual_length = sizeof(payload);
    tx[0].completion_status = 1u;
    tx[0].version_state_generation =
        1u | ((uint32_t)P8D_DESC_HW_COMPLETED << 8) | ((uint32_t)1u << 16);
  }
  if (!rc && p8d_poll_completion(&driver, 0, &completion) != P8D_OK) rc = 9;
  if (!rc && (completion == NULL || completion->actual_length != sizeof(payload))) rc = 10;
  if (!rc && p8d_reap_completion(&driver, 0) != P8D_OK) rc = 11;
  if (!rc && p8d_post_rx_descriptor(&driver, (uintptr_t)payload, sizeof(payload),
                                     3u, 4u, 6u) != P8D_OK) rc = 12;
  if (!rc && p8d_abort_stream_or_object(&driver, 3u, 4u) != P8D_OK) rc = 13;
  if (!rc && p8d_reset_data_plane(&driver) != P8D_OK) rc = 14;
  if (!rc && (mock.flush_count < 2u || mock.invalidate_count < 1u ||
              mock.barrier_count < 1u)) rc = 15;
  _aligned_free(tx);
  _aligned_free(rx);
  return rc;
}
