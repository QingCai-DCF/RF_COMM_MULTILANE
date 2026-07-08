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

enum {
  IR_STATUS_PHY_READY = 1u << 0,
  IR_STATUS_BUSY = 1u << 1,
  IR_STATUS_TX_DONE = 1u << 2,
  IR_STATUS_RX_DONE = 1u << 3,
  IR_STATUS_TX_FAIL = 1u << 4,
};

static int ir_write_readback(const ir_mmio_t *io, uint32_t offset, uint32_t value) {
  io->write32(io->ctx, offset, value);
  return (io->read32(io->ctx, offset) == value) ? 0 : -1;
}

static int ir_driver_write_profile_registers(const ir_mmio_t *io, const ir_profile_config_t *profile) {
  if (!io || !io->read32 || !io->write32 || !profile) return -1;

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
  return 0;
}

int ir_driver_wait_startup(const ir_mmio_t *io, uint32_t max_polls) {
  if (!io || !io->read32) return -1;
  for (uint32_t poll = 0; poll < max_polls; poll++) {
    uint32_t status = io->read32(io->ctx, IR_REG_STATUS);
    if (status & IR_STATUS_PHY_READY) {
      return 0;
    }
    if (status & IR_STATUS_TX_FAIL) {
      return -2;
    }
  }
  return -3;
}

int ir_driver_initialize(const ir_mmio_t *io, const ir_profile_config_t *profile, uint32_t startup_max_polls) {
  if (!io || !io->read32 || !io->write32 || !profile) return -1;

  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_RESET);

  int write_result = ir_driver_write_profile_registers(io, profile);
  if (write_result) return write_result;

  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_COMMIT);
  if (io->read32(io->ctx, IR_REG_PROFILE_ID) == 0u) return -17;

  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_ENABLE_PHY);
  if (ir_driver_wait_startup(io, startup_max_polls)) return -18;

  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_ENABLE_PHY | IR_CONTROL_CLEAR_STICKY);
  return 0;
}

int ir_driver_apply_profile(const ir_mmio_t *io, const ir_profile_config_t *profile) {
  return ir_driver_initialize(io, profile, 1024u);
}

int ir_driver_start_transaction(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_ENABLE_PHY | IR_CONTROL_START);
  return 0;
}

int ir_driver_poll_done(const ir_mmio_t *io, uint32_t max_polls) {
  if (!io || !io->read32) return -1;
  for (uint32_t poll = 0; poll < max_polls; poll++) {
    uint32_t status = io->read32(io->ctx, IR_REG_STATUS);
    if (status & IR_STATUS_TX_FAIL) {
      return -2;
    }
    if ((status & (IR_STATUS_TX_DONE | IR_STATUS_RX_DONE)) != 0u && (status & IR_STATUS_BUSY) == 0u) {
      return 0;
    }
  }
  return -3;
}

int ir_driver_read_final_counters(const ir_mmio_t *io, ir_driver_counters_t *counters) {
  if (!io || !io->read32 || !counters) return -1;
  counters->status = io->read32(io->ctx, IR_REG_STATUS);
  counters->retry_count = io->read32(io->ctx, IR_REG_STATUS_RETRY_COUNT);
  counters->error_counts = io->read32(io->ctx, IR_REG_STATUS_ERROR_COUNTS);
  counters->tx_pulse = io->read32(io->ctx, IR_REG_COUNTER_TX_PULSE);
  counters->rx_raw_pulse = io->read32(io->ctx, IR_REG_COUNTER_RX_RAW_PULSE);
  counters->frame_good = io->read32(io->ctx, IR_REG_COUNTER_FRAME_GOOD);
  counters->frame_bad = io->read32(io->ctx, IR_REG_COUNTER_FRAME_BAD);
  counters->ack_sent = io->read32(io->ctx, IR_REG_COUNTER_ACK_SENT);
  counters->ack_seen = io->read32(io->ctx, IR_REG_COUNTER_ACK_SEEN);
  return 0;
}

int ir_driver_run_transaction(const ir_mmio_t *io, uint32_t max_polls, ir_driver_counters_t *final_counters) {
  if (!io) return -1;
  int result = ir_driver_start_transaction(io);
  if (result) return result;
  result = ir_driver_poll_done(io, max_polls);
  if (ir_driver_stop(io)) return -4;
  if (ir_driver_read_final_counters(io, final_counters)) return -5;
  return result;
}

int ir_driver_stop(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_ENABLE_PHY | IR_CONTROL_STOP);
  return 0;
}

int ir_driver_shutdown(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_STOP);
  io->write32(io->ctx, IR_REG_SAFETY_SHUTDOWN_REASON, 0x54464455u);
  return 0;
}
