#include "ir_driver.h"
#include "ir_profile.h"
#include "ir_regs.h"

static uint32_t mock_regs[IR_REG_PROFILE_ID / 4u + 1u];

static uint32_t mock_read32(void *ctx, uint32_t offset) {
  uint32_t *regs = (uint32_t *)ctx;
  if (offset == IR_REG_PROFILE_ID) return 0x47312201u;
  return regs[offset / 4u];
}

static void mock_write32(void *ctx, uint32_t offset, uint32_t value) {
  uint32_t *regs = (uint32_t *)ctx;
  regs[offset / 4u] = value;
}

int main(void) {
  ir_mmio_t io = {
    .ctx = mock_regs,
    .read32 = mock_read32,
    .write32 = mock_write32,
  };
  if (ir_driver_apply_profile(&io, &IR_PROFILE_G1_LANE0_BASELINE)) return 1;
  if (ir_driver_start_transaction(&io)) return 2;
  if (ir_driver_stop(&io)) return 3;
  if (ir_driver_shutdown(&io)) return 4;
  return 0;
}
