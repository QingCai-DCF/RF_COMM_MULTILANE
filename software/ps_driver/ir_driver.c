#include "ir_driver.h"
#include "ir_regs.h"

enum {
  IR_CONTROL_RESET = 1u << 0,
  IR_CONTROL_ENABLE_PHY = 1u << 1,
  IR_CONTROL_START = 1u << 2,
  IR_CONTROL_STOP = 1u << 3,
  IR_CONTROL_CLEAR_STICKY = 1u << 4,
  IR_CONTROL_COMMIT = 1u << 5,
};

static int ir_write_readback(const ir_mmio_t *io, uint32_t offset, uint32_t value) {
  io->write32(io->ctx, offset, value);
  return (io->read32(io->ctx, offset) == value) ? 0 : -1;
}

int ir_driver_apply_profile(const ir_mmio_t *io, const ir_profile_config_t *profile) {
  if (!io || !io->read32 || !io->write32 || !profile) return -1;

  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_RESET);
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_CLEAR_STICKY);

  if (ir_write_readback(io, IR_REG_PROFILE_LANE_MASK, profile->payload_lane_mask)) return -2;
  if (ir_write_readback(io, IR_REG_PROFILE_RX_LANE_MASK, profile->rx_lane_mask)) return -3;
  if (ir_write_readback(io, IR_REG_PROFILE_ACK_LANE_MASK, profile->ack_lane_mask)) return -4;
  if (ir_write_readback(io, IR_REG_PROFILE_SESSION, profile->session)) return -5;
  if (ir_write_readback(io, IR_REG_PROFILE_PAYLOAD_LEN, profile->payload_len)) return -6;
  if (ir_write_readback(io, IR_REG_PROFILE_FRAGMENT_BYTES, profile->fragment_bytes)) return -7;
  if (ir_write_readback(io, IR_REG_TIMING_CNT_CHIP_MAX, profile->cnt_chip_max)) return -8;
  if (ir_write_readback(io, IR_REG_TIMING_CNT_PREAMBLE, profile->cnt_preamble)) return -9;
  if (ir_write_readback(io, IR_REG_TIMING_DETECT_WINDOW, profile->detect_window)) return -10;
  if (ir_write_readback(io, IR_REG_TIMING_GUARD_CYCLES, profile->guard_cycles)) return -11;
  if (ir_write_readback(io, IR_REG_TIMING_RETRY_TIMEOUT, profile->retry_timeout)) return -12;
  if (ir_write_readback(io, IR_REG_SAFETY_STARTUP_US, profile->startup_us)) return -13;
  if (ir_write_readback(io, IR_REG_SAFETY_DUTY_WINDOW, profile->duty_window)) return -14;
  if (ir_write_readback(io, IR_REG_SAFETY_DUTY_MAX, profile->duty_max_permille)) return -15;
  if (ir_write_readback(io, IR_REG_SAFETY_STUCK_HIGH_LIMIT, profile->stuck_high_limit_us)) return -16;

  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_COMMIT);
  (void)io->read32(io->ctx, IR_REG_PROFILE_ID);
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_ENABLE_PHY);
  return 0;
}

int ir_driver_start_transaction(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_ENABLE_PHY | IR_CONTROL_START);
  return 0;
}

int ir_driver_stop(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_STOP);
  return 0;
}

int ir_driver_shutdown(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_STOP);
  io->write32(io->ctx, IR_REG_SAFETY_SHUTDOWN_REASON, 0x54464455u);
  return 0;
}
