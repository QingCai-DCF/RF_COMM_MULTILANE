#include "ir_driver.h"
#include "ir_profile.h"
#include "ir_regs.h"

enum {
  MOCK_CONTROL_ENABLE_PHY = 1u << 1,
  MOCK_CONTROL_START = 1u << 2,
  MOCK_STATUS_PHY_READY = 1u << 0,
  MOCK_STATUS_BUSY = 1u << 1,
  MOCK_STATUS_TX_DONE = 1u << 2,
  MOCK_STATUS_RX_DONE = 1u << 3,
};

typedef struct {
  uint32_t regs[IR_REG_PROFILE_ID / 4u + 1u];
  uint32_t status_reads_after_start;
} mock_context_t;

static uint32_t mock_read32(void *ctx, uint32_t offset) {
  mock_context_t *mock = (mock_context_t *)ctx;
  if (offset == IR_REG_PROFILE_ID) return 0x47312201u;
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
  if (offset == IR_REG_CONTROL && (value & MOCK_CONTROL_ENABLE_PHY)) {
    mock->regs[IR_REG_STATUS / 4u] = MOCK_STATUS_PHY_READY;
  }
  if (offset == IR_REG_CONTROL && (value & MOCK_CONTROL_START)) {
    mock->status_reads_after_start = 0u;
    mock->regs[IR_REG_STATUS / 4u] = MOCK_STATUS_PHY_READY | MOCK_STATUS_BUSY;
  }
}

int main(void) {
  static mock_context_t mock;
  ir_driver_counters_t counters;
  ir_mmio_t io = {
    .ctx = &mock,
    .read32 = mock_read32,
    .write32 = mock_write32,
  };
  if (ir_driver_initialize(&io, &IR_PROFILE_G1_LANE0_BASELINE, 16u)) return 1;
  if (ir_driver_run_transaction(&io, 16u, &counters)) return 2;
  if (counters.frame_good != 1u || counters.frame_bad != 0u) return 3;
  if (ir_driver_shutdown(&io)) return 4;
  return 0;
}
