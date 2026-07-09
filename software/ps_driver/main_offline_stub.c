#include "ir_driver.h"
#include "ir_profile.h"
#include "ir_regs.h"

enum {
  MOCK_CONTROL_ENABLE_PHY = 1u << 1,
  MOCK_CONTROL_START = 1u << 2,
  MOCK_P6_CTRL_COMMIT = 1u << 2,
  MOCK_P6_CTRL_START = 1u << 3,
  MOCK_STATUS_PHY_READY = 1u << 0,
  MOCK_STATUS_BUSY = 1u << 1,
  MOCK_STATUS_TX_DONE = 1u << 2,
  MOCK_STATUS_RX_DONE = 1u << 3,
  MOCK_P6_STATUS_READY = 1u << 1,
  MOCK_P6_STATUS_COMMITTED = 1u << 2,
  MOCK_P6_STATUS_DONE = 1u << 4,
};

typedef struct {
  uint32_t regs[IR_REG_P6_CAPS / 4u + 1u];
  uint32_t p6_payload_words[64u];
  uint32_t p6_rx_words[64u];
  uint32_t p6_payload_word_index;
  uint32_t p6_rx_word_index;
  uint32_t status_reads_after_start;
} mock_context_t;

static uint32_t mock_read32(void *ctx, uint32_t offset) {
  mock_context_t *mock = (mock_context_t *)ctx;
  if (offset == IR_REG_PROFILE_ID) return 0x47312201u;
  if (offset == IR_REG_P6_CAPS) return 0x060300F7u;
  if (offset == IR_REG_P6_PAYLOAD_WORD_DATA) return mock->p6_payload_words[mock->p6_payload_word_index & 63u];
  if (offset == IR_REG_P6_RX_WORD_DATA) return mock->p6_rx_words[mock->p6_rx_word_index & 63u];
  if (offset == IR_REG_STATUS && (mock->regs[IR_REG_STATUS / 4u] & MOCK_STATUS_BUSY)) {
    mock->status_reads_after_start++;
    if (mock->status_reads_after_start >= 2u) {
      mock->regs[IR_REG_STATUS / 4u] = MOCK_STATUS_PHY_READY | MOCK_STATUS_TX_DONE | MOCK_STATUS_RX_DONE;
      mock->regs[IR_REG_COUNTER_TX_PULSE / 4u] = 16u;
      mock->regs[IR_REG_COUNTER_RX_RAW_PULSE / 4u] = 16u;
      mock->regs[IR_REG_COUNTER_FRAME_GOOD / 4u] = 1u;
      mock->regs[IR_REG_COUNTER_ACK_SENT / 4u] = 1u;
      mock->regs[IR_REG_COUNTER_ACK_SEEN / 4u] = 1u;
    }
  }
  return mock->regs[offset / 4u];
}

static void mock_write32(void *ctx, uint32_t offset, uint32_t value) {
  mock_context_t *mock = (mock_context_t *)ctx;
  mock->regs[offset / 4u] = value;
  if (offset == IR_REG_P6_PAYLOAD_WORD_INDEX) {
    mock->p6_payload_word_index = value & 63u;
  }
  if (offset == IR_REG_P6_PAYLOAD_WORD_DATA) {
    mock->p6_payload_words[mock->p6_payload_word_index & 63u] = value;
  }
  if (offset == IR_REG_P6_RX_WORD_INDEX) {
    mock->p6_rx_word_index = value & 63u;
  }
  if (offset == IR_REG_CONTROL && (value & MOCK_CONTROL_ENABLE_PHY)) {
    mock->regs[IR_REG_STATUS / 4u] = MOCK_STATUS_PHY_READY;
  }
  if (offset == IR_REG_CONTROL && (value & MOCK_CONTROL_START)) {
    mock->status_reads_after_start = 0u;
    mock->regs[IR_REG_STATUS / 4u] = MOCK_STATUS_PHY_READY | MOCK_STATUS_BUSY;
  }
  if (offset == IR_REG_P6_CTRL && (value & MOCK_P6_CTRL_COMMIT)) {
    mock->regs[IR_REG_P6_STATUS / 4u] = MOCK_P6_STATUS_READY | MOCK_P6_STATUS_COMMITTED;
    mock->regs[IR_REG_P6_PAYLOAD_CRC32 / 4u] = 0xCAFE2201u;
    mock->regs[IR_REG_P6_MAILBOX_STATUS / 4u] = 0x5036434Du;
  }
  if (offset == IR_REG_P6_CTRL && (value & MOCK_P6_CTRL_START)) {
    uint32_t word_count = ((mock->regs[IR_REG_P6_PAYLOAD_LEN / 4u] & 0xFFFFu) + 3u) / 4u;
    for (uint32_t word = 0u; word < word_count; word++) {
      mock->p6_rx_words[word] = mock->p6_payload_words[word];
    }
    mock->regs[IR_REG_P6_STATUS / 4u] = MOCK_P6_STATUS_READY | MOCK_P6_STATUS_COMMITTED | MOCK_P6_STATUS_DONE;
    mock->regs[IR_REG_P6_RX_PAYLOAD_LEN / 4u] = mock->regs[IR_REG_P6_PAYLOAD_LEN / 4u] & 0xFFFFu;
    mock->regs[IR_REG_P6_RX_PAYLOAD_CRC32 / 4u] = mock->regs[IR_REG_P6_PAYLOAD_CRC32 / 4u];
    mock->regs[IR_REG_P6_RX_DIGEST / 4u] = mock->regs[IR_REG_P6_PAYLOAD_CRC32 / 4u];
    mock->regs[IR_REG_P6_TX_COUNT / 4u] = 1u;
    if (mock->regs[IR_REG_P6_LANE_MASK / 4u] & 1u) mock->regs[IR_REG_P6_RX_GOOD_COUNT_L0 / 4u] = 1u;
    if (mock->regs[IR_REG_P6_LANE_MASK / 4u] & 2u) mock->regs[IR_REG_P6_RX_GOOD_COUNT_L1 / 4u] = 1u;
    mock->regs[IR_REG_P6_MAILBOX_STATUS / 4u] = 0x50364F4Bu;
  }
}

int main(void) {
  static mock_context_t mock;
  ir_driver_counters_t counters;
  ir_p6_payload_result_t p6_result;
  uint8_t payload[16u];
  uint8_t rx_payload[16u];
  uint32_t rx_len = 0u;
  ir_p6_payload_config_t p6_config = {
    .session = 0x2201u,
    .lane_mask = 0x3u,
    .ack_lane_mask = 0x3u,
    .payload_len = 16u,
    .pattern_id = 4u,
    .seed = 0x2201u,
    .timeout_cycles = 64000u,
  };
  ir_mmio_t io = {
    .ctx = &mock,
    .read32 = mock_read32,
    .write32 = mock_write32,
  };
  if (ir_driver_initialize(&io, &IR_PROFILE_G1_LANE0_BASELINE, 16u)) return 1;
  if (ir_driver_run_transaction(&io, 16u, &counters)) return 2;
  if (counters.frame_good != 1u || counters.frame_bad != 0u) return 3;
  if (ir_driver_shutdown(&io)) return 4;
  for (uint32_t idx = 0u; idx < 16u; idx++) payload[idx] = (uint8_t)idx;
  if (ir_driver_p6_run_mailbox_payload(&io, &p6_config, payload, 16u, &p6_result)) return 5;
  if (p6_result.tx_count != 1u || p6_result.rx_good_count_l0 != 1u || p6_result.rx_good_count_l1 != 1u) return 6;
  if (p6_result.crc_bad != 0u || p6_result.payload_mismatch != 0u || p6_result.tx_fail != 0u) return 7;
  if (ir_driver_p6_read_rx_payload(&io, rx_payload, sizeof(rx_payload), &rx_len)) return 8;
  if (rx_len != 16u) return 9;
  for (uint32_t idx = 0u; idx < 16u; idx++) {
    if (rx_payload[idx] != payload[idx]) return 10;
  }
  return 0;
}
