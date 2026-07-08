#pragma once
#include <stdint.h>

typedef uint32_t (*ir_read32_fn)(void *ctx, uint32_t offset);
typedef void (*ir_write32_fn)(void *ctx, uint32_t offset, uint32_t value);

typedef struct {
  void *ctx;
  ir_read32_fn read32;
  ir_write32_fn write32;
} ir_mmio_t;

typedef struct {
  uint32_t payload_lane_mask;
  uint32_t rx_lane_mask;
  uint32_t ack_lane_mask;
  uint32_t session;
  uint32_t payload_len;
  uint32_t fragment_bytes;
  uint32_t cnt_chip_max;
  uint32_t cnt_preamble;
  uint32_t detect_window;
  uint32_t guard_cycles;
  uint32_t retry_timeout;
  uint32_t startup_us;
  uint32_t duty_window;
  uint32_t duty_max_permille;
  uint32_t stuck_high_limit_us;
} ir_profile_config_t;

int ir_driver_apply_profile(const ir_mmio_t *io, const ir_profile_config_t *profile);
int ir_driver_start_transaction(const ir_mmio_t *io);
int ir_driver_stop(const ir_mmio_t *io);
int ir_driver_shutdown(const ir_mmio_t *io);
