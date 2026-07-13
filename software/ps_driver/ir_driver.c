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
  IR_TFDU_SHUTDOWN_REASON = 0x54464455u,
  IR_P6_MAILBOX_IDLE = 0x50364944u,
  IR_SHUTDOWN_READBACK_POLLS = 4096u,
};

enum {
  IR_STATUS_PHY_READY = 1u << 0,
  IR_STATUS_BUSY = 1u << 1,
  IR_STATUS_TX_DONE = 1u << 2,
  IR_STATUS_RX_DONE = 1u << 3,
  IR_STATUS_TX_FAIL = 1u << 4,
};

enum {
  IR_P6_CTRL_RESET = 1u << 0,
  IR_P6_CTRL_CLEAR_STICKY = 1u << 1,
  IR_P6_CTRL_COMMIT = 1u << 2,
  IR_P6_CTRL_START = 1u << 3,
  IR_P6_CTRL_STOP = 1u << 4,
  IR_P6_CTRL_SHUTDOWN = 1u << 5,
};

enum {
  IR_P6_STATUS_READY = 1u << 1,
  IR_P6_STATUS_COMMITTED = 1u << 2,
  IR_P6_STATUS_BUSY = 1u << 3,
  IR_P6_STATUS_DONE = 1u << 4,
  IR_P6_STATUS_FAIL = 1u << 5,
  IR_P6_STATUS_CONFIG_REJECTED = 1u << 6,
  IR_P6_STATUS_TIMEOUT = 1u << 7,
};

enum {
  IR_P6_MAX_PAYLOAD_BYTES = 247u,
  IR_P6_MAX_PAYLOAD_WORDS = 64u,
};

static int ir_write_readback(const ir_mmio_t *io, uint32_t offset, uint32_t value) {
  io->write32(io->ctx, offset, value);
  return (io->read32(io->ctx, offset) == value) ? 0 : -1;
}

static uint32_t ir_pack_payload_word(const uint8_t *payload, uint32_t payload_len, uint32_t word_index) {
  uint32_t value = 0u;
  uint32_t base = word_index * 4u;
  for (uint32_t lane = 0u; lane < 4u; lane++) {
    uint32_t byte_index = base + lane;
    if (byte_index < payload_len) {
      value |= ((uint32_t)payload[byte_index]) << (8u * lane);
    }
  }
  return value;
}

static void ir_unpack_payload_word(uint32_t word, uint8_t *payload, uint32_t payload_len, uint32_t word_index) {
  uint32_t base = word_index * 4u;
  for (uint32_t lane = 0u; lane < 4u; lane++) {
    uint32_t byte_index = base + lane;
    if (byte_index < payload_len) {
      payload[byte_index] = (uint8_t)((word >> (8u * lane)) & 0xFFu);
    }
  }
}

static int ir_p6_validate_config(const ir_p6_payload_config_t *config) {
  if (!config) return -1;
  if (config->session != 0x2201u) return -2;
  if (!(config->lane_mask == 0x1u || config->lane_mask == 0x2u || config->lane_mask == 0x3u)) return -3;
  if (config->ack_lane_mask != config->lane_mask) return -4;
  if (config->payload_len == 0u || config->payload_len > IR_P6_MAX_PAYLOAD_BYTES) return -5;
  if (config->timeout_cycles == 0u) return -6;
  return 0;
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
  if (!io || !io->read32 || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_CONTROL, IR_CONTROL_STOP);
  io->write32(io->ctx, IR_REG_SAFETY_SHUTDOWN_REASON,
              IR_TFDU_SHUTDOWN_REASON);
  io->write32(io->ctx, IR_REG_P6_CTRL, IR_P6_CTRL_SHUTDOWN);
  io->write32(io->ctx, IR_REG_P6_SHUTDOWN_REASON,
              IR_TFDU_SHUTDOWN_REASON);
  for (uint32_t poll = 0u; poll < IR_SHUTDOWN_READBACK_POLLS; ++poll) {
    uint32_t status = io->read32(io->ctx, IR_REG_P6_STATUS);
    uint32_t legacy_status = io->read32(io->ctx, IR_REG_STATUS);
    uint32_t control = io->read32(io->ctx, IR_REG_CONTROL);
    uint32_t reason = io->read32(io->ctx, IR_REG_P6_SHUTDOWN_REASON);
    uint32_t safety_reason =
        io->read32(io->ctx, IR_REG_SAFETY_SHUTDOWN_REASON);
    uint32_t mailbox = io->read32(io->ctx, IR_REG_P6_MAILBOX_STATUS);
    if ((status & (IR_P6_STATUS_BUSY | 1u)) == 0u &&
        (legacy_status & IR_STATUS_BUSY) == 0u && (control & 1u) == 0u &&
        reason == IR_TFDU_SHUTDOWN_REASON &&
        safety_reason == IR_TFDU_SHUTDOWN_REASON &&
        mailbox == IR_P6_MAILBOX_IDLE) {
      return 0;
    }
  }
  return -2;
}

int ir_driver_p6_write_payload(const ir_mmio_t *io, const uint8_t *payload, uint32_t payload_len) {
  if (!io || !io->read32 || !io->write32 || !payload) return -1;
  if (payload_len == 0u || payload_len > IR_P6_MAX_PAYLOAD_BYTES) return -2;
  uint32_t word_count = (payload_len + 3u) / 4u;
  for (uint32_t word_index = 0u; word_index < word_count; word_index++) {
    uint32_t word = ir_pack_payload_word(payload, payload_len, word_index);
    if (ir_write_readback(io, IR_REG_P6_PAYLOAD_WORD_INDEX, word_index)) return -3;
    if (ir_write_readback(io, IR_REG_P6_PAYLOAD_WORD_DATA, word)) return -4;
  }
  return 0;
}

int ir_driver_p6_read_tx_payload(const ir_mmio_t *io, uint8_t *payload,
                                 uint32_t payload_capacity,
                                 uint32_t payload_len) {
  if (!io || !io->read32 || !io->write32 || !payload) return -1;
  if (payload_len == 0u || payload_len > payload_capacity ||
      payload_len > IR_P6_MAX_PAYLOAD_BYTES) {
    return -2;
  }
  uint32_t word_count = (payload_len + 3u) / 4u;
  for (uint32_t word_index = 0u; word_index < word_count; word_index++) {
    if (ir_write_readback(io, IR_REG_P6_PAYLOAD_WORD_INDEX, word_index))
      return -3;
    ir_unpack_payload_word(io->read32(io->ctx, IR_REG_P6_PAYLOAD_WORD_DATA),
                           payload, payload_len, word_index);
  }
  return 0;
}

int ir_driver_p6_read_rx_payload(const ir_mmio_t *io, uint8_t *payload, uint32_t payload_capacity, uint32_t *payload_len) {
  if (!io || !io->read32 || !io->write32 || !payload || !payload_len) return -1;
  uint32_t observed_len = io->read32(io->ctx, IR_REG_P6_RX_PAYLOAD_LEN) & 0xFFFFu;
  if (observed_len > payload_capacity || observed_len > IR_P6_MAX_PAYLOAD_BYTES) return -2;
  uint32_t word_count = (observed_len + 3u) / 4u;
  for (uint32_t word_index = 0u; word_index < word_count; word_index++) {
    if (ir_write_readback(io, IR_REG_P6_RX_WORD_INDEX, word_index)) return -3;
    ir_unpack_payload_word(io->read32(io->ctx, IR_REG_P6_RX_WORD_DATA), payload, observed_len, word_index);
  }
  *payload_len = observed_len;
  return 0;
}

int ir_driver_p6_commit_payload(const ir_mmio_t *io, const ir_p6_payload_config_t *config) {
  if (!io || !io->read32 || !io->write32) return -1;
  int validation = ir_p6_validate_config(config);
  if (validation) return validation;
  io->write32(io->ctx, IR_REG_P6_CTRL, IR_P6_CTRL_CLEAR_STICKY);
  if (ir_write_readback(io, IR_REG_P6_SESSION, config->session)) return -10;
  if (ir_write_readback(io, IR_REG_P6_LANE_MASK, config->lane_mask)) return -11;
  if (ir_write_readback(io, IR_REG_P6_ACK_LANE_MASK, config->ack_lane_mask)) return -12;
  if (ir_write_readback(io, IR_REG_P6_PAYLOAD_LEN, config->payload_len)) return -13;
  if (ir_write_readback(io, IR_REG_P6_PAYLOAD_PATTERN_ID, config->pattern_id)) return -14;
  if (ir_write_readback(io, IR_REG_P6_PAYLOAD_SEED, config->seed)) return -15;
  if (ir_write_readback(io, IR_REG_P6_TIMEOUT_CYCLES, config->timeout_cycles)) return -16;
  io->write32(io->ctx, IR_REG_P6_CTRL, IR_P6_CTRL_COMMIT);
  for (uint32_t poll = 0u; poll < 4096u; poll++) {
    uint32_t status = io->read32(io->ctx, IR_REG_P6_STATUS);
    if ((status & (IR_P6_STATUS_FAIL | IR_P6_STATUS_CONFIG_REJECTED | IR_P6_STATUS_TIMEOUT)) != 0u) return -18;
    if ((status & IR_P6_STATUS_COMMITTED) != 0u) return 0;
  }
  return -17;
}

int ir_driver_p6_read_result(const ir_mmio_t *io, ir_p6_payload_result_t *result) {
  if (!io || !io->read32 || !result) return -1;
  result->status = io->read32(io->ctx, IR_REG_P6_STATUS);
  result->mailbox_status = io->read32(io->ctx, IR_REG_P6_MAILBOX_STATUS);
  result->payload_crc32 = io->read32(io->ctx, IR_REG_P6_PAYLOAD_CRC32);
  result->rx_payload_crc32 = io->read32(io->ctx, IR_REG_P6_RX_PAYLOAD_CRC32);
  result->rx_payload_len = io->read32(io->ctx, IR_REG_P6_RX_PAYLOAD_LEN);
  result->tx_count = io->read32(io->ctx, IR_REG_P6_TX_COUNT);
  result->rx_good_count_l0 = io->read32(io->ctx, IR_REG_P6_RX_GOOD_COUNT_L0);
  result->rx_good_count_l1 = io->read32(io->ctx, IR_REG_P6_RX_GOOD_COUNT_L1);
  result->crc_bad = io->read32(io->ctx, IR_REG_P6_CRC_BAD);
  result->payload_mismatch = io->read32(io->ctx, IR_REG_P6_PAYLOAD_MISMATCH);
  result->retry_count = io->read32(io->ctx, IR_REG_P6_RETRY_COUNT);
  result->retry_exhausted = io->read32(io->ctx, IR_REG_P6_RETRY_EXHAUSTED);
  result->tx_fail = io->read32(io->ctx, IR_REG_P6_TX_FAIL);
  result->txd_high_consecutive_max = io->read32(io->ctx, IR_REG_P6_TXD_HIGH_CONSECUTIVE_MAX);
  result->duty_violation = io->read32(io->ctx, IR_REG_P6_DUTY_VIOLATION);
  result->shutdown_reason = io->read32(io->ctx, IR_REG_P6_SHUTDOWN_REASON);
  result->error_code = io->read32(io->ctx, IR_REG_P6_ERROR_CODE);
  result->sticky_error = io->read32(io->ctx, IR_REG_P6_STICKY_ERROR);
  result->rx_digest = io->read32(io->ctx, IR_REG_P6_RX_DIGEST);
  return 0;
}

int ir_driver_p6_start(const ir_mmio_t *io) {
  if (!io || !io->read32 || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_P6_CTRL, IR_P6_CTRL_START);
  return 0;
}

int ir_driver_p6_get_status(const ir_mmio_t *io, uint32_t *status) {
  if (!io || !io->read32 || !status) return -1;
  *status = io->read32(io->ctx, IR_REG_P6_STATUS);
  return 0;
}

int ir_driver_p6_start_and_poll(const ir_mmio_t *io, uint32_t max_polls, ir_p6_payload_result_t *result) {
  if (!io || !io->read32 || !io->write32) return -1;
  if (ir_driver_p6_start(io)) return -1;
  for (uint32_t poll = 0u; poll < max_polls; poll++) {
    uint32_t status = io->read32(io->ctx, IR_REG_P6_STATUS);
    if ((status & (IR_P6_STATUS_FAIL | IR_P6_STATUS_CONFIG_REJECTED | IR_P6_STATUS_TIMEOUT)) != 0u) {
      if (result) (void)ir_driver_p6_read_result(io, result);
      return -2;
    }
    if ((status & IR_P6_STATUS_DONE) != 0u && (status & IR_P6_STATUS_BUSY) == 0u) {
      if (result) (void)ir_driver_p6_read_result(io, result);
      return 0;
    }
  }
  if (result) (void)ir_driver_p6_read_result(io, result);
  return -3;
}

int ir_driver_p6_reset(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_P6_CTRL, IR_P6_CTRL_RESET);
  return 0;
}

int ir_driver_p6_stop(const ir_mmio_t *io) {
  if (!io || !io->write32) return -1;
  io->write32(io->ctx, IR_REG_P6_CTRL, IR_P6_CTRL_STOP);
  return 0;
}

int ir_driver_p6_run_payload_no_shutdown(
    const ir_mmio_t *io,
    const ir_p6_payload_config_t *config,
    const uint8_t *payload,
    uint32_t max_polls,
    ir_p6_payload_result_t *result) {
  if (!io || !config || !payload) return -1;
  if (ir_driver_p6_reset(io)) return -2;
  if (ir_driver_p6_write_payload(io, payload, config->payload_len)) return -3;
  if (ir_driver_p6_commit_payload(io, config)) return -4;
  int run_result = ir_driver_p6_start_and_poll(io, max_polls, result);
  if (ir_driver_p6_stop(io)) return -5;
  return run_result;
}

int ir_driver_p6_run_mailbox_payload(
    const ir_mmio_t *io,
    const ir_p6_payload_config_t *config,
    const uint8_t *payload,
    uint32_t max_polls,
    ir_p6_payload_result_t *result) {
  if (!io || !config || !payload) return -1;
  int run_result = ir_driver_p6_run_payload_no_shutdown(io, config, payload, max_polls, result);
  if (ir_driver_shutdown(io)) return -4;
  return run_result;
}
