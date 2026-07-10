#include "ir_driver.h"
#include "ir_regs.h"

#include <stdint.h>
#include <string.h>

#define WORDS 256U
#define P6_CTRL_SHUTDOWN (1U << 5)
#define P6_STATUS_BUSY (1U << 3)
#define TFDU_REASON UINT32_C(0x54464455)
#define P6_MAILBOX_IDLE UINT32_C(0x50364944)

typedef struct mock_mmio {
  uint32_t words[WORDS];
  int accept_shutdown;
} mock_mmio_t;

static uint32_t mock_read(void *context, uint32_t offset) {
  mock_mmio_t *mock = (mock_mmio_t *)context;
  return mock->words[offset / 4U];
}

static void mock_write(void *context, uint32_t offset, uint32_t value) {
  mock_mmio_t *mock = (mock_mmio_t *)context;
  mock->words[offset / 4U] = value;
  if (offset == IR_REG_P6_CTRL && (value & P6_CTRL_SHUTDOWN) != 0U &&
      mock->accept_shutdown) {
    mock->words[IR_REG_CONTROL / 4U] = 0U;
    mock->words[IR_REG_STATUS / 4U] = 0U;
    mock->words[IR_REG_P6_STATUS / 4U] = 0U;
    mock->words[IR_REG_SAFETY_SHUTDOWN_REASON / 4U] = TFDU_REASON;
    mock->words[IR_REG_P6_SHUTDOWN_REASON / 4U] = TFDU_REASON;
    mock->words[IR_REG_P6_MAILBOX_STATUS / 4U] = P6_MAILBOX_IDLE;
  }
}

int main(void) {
  mock_mmio_t mock;
  ir_mmio_t io;
  memset(&mock, 0, sizeof(mock));
  mock.accept_shutdown = 1;
  io.ctx = &mock;
  io.read32 = mock_read;
  io.write32 = mock_write;
  if (ir_driver_shutdown(&io) != 0) return 1;
  if (mock.words[IR_REG_P6_SHUTDOWN_REASON / 4U] != TFDU_REASON) return 2;
  memset(&mock, 0, sizeof(mock));
  mock.words[IR_REG_P6_STATUS / 4U] = P6_STATUS_BUSY;
  mock.words[IR_REG_P6_MAILBOX_STATUS / 4U] = P6_MAILBOX_IDLE;
  if (ir_driver_shutdown(&io) != -2) return 3;
  io.read32 = 0;
  if (ir_driver_shutdown(&io) != -1) return 4;
  return 0;
}
