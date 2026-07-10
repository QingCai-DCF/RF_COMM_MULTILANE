#include "ir_driver.h"
#include "ir_regs.h"

#ifndef IR_PL_BASEADDR
#define IR_PL_BASEADDR 0x43C00000u
#endif

#ifndef P6_RESULT_MAILBOX_BASEADDR
#define P6_RESULT_MAILBOX_BASEADDR 0x00020000u
#endif

enum {
  P6_RUNTIME_MAGIC = 0x50365254u,
  P6_RUNTIME_PAYLOAD_BYTES = 247u,
  P6_RUNTIME_MAX_POLLS = 1000000u,
};

typedef struct {
  volatile uint32_t *base;
} p6_mmio_context_t;

static uint32_t p6_read32(void *ctx, uint32_t offset) {
  p6_mmio_context_t *mmio = (p6_mmio_context_t *)ctx;
  return mmio->base[offset / 4u];
}

static void p6_write32(void *ctx, uint32_t offset, uint32_t value) {
  p6_mmio_context_t *mmio = (p6_mmio_context_t *)ctx;
  mmio->base[offset / 4u] = value;
}

static void p6_fill_payload(uint8_t *payload, uint32_t length) {
  uint32_t state = 0x00002201u;
  for (uint32_t idx = 0u; idx < length; idx++) {
    state = (1664525u * state) + 1013904223u;
    payload[idx] = (uint8_t)(state >> 24);
  }
}

static void p6_write_result_mailbox(int status, const ir_p6_payload_result_t *result) {
  volatile uint32_t *mailbox = (volatile uint32_t *)P6_RESULT_MAILBOX_BASEADDR;
  mailbox[0] = P6_RUNTIME_MAGIC;
  mailbox[1] = (uint32_t)status;
  mailbox[2] = result ? result->status : 0u;
  mailbox[3] = result ? result->mailbox_status : 0u;
  mailbox[4] = result ? result->payload_crc32 : 0u;
  mailbox[5] = result ? result->rx_payload_crc32 : 0u;
  mailbox[6] = result ? result->rx_payload_len : 0u;
  mailbox[7] = result ? result->tx_count : 0u;
  mailbox[8] = result ? result->rx_good_count_l0 : 0u;
  mailbox[9] = result ? result->rx_good_count_l1 : 0u;
  mailbox[10] = result ? result->crc_bad : 0u;
  mailbox[11] = result ? result->payload_mismatch : 0u;
  mailbox[12] = result ? result->retry_exhausted : 0u;
  mailbox[13] = result ? result->tx_fail : 0u;
  mailbox[14] = result ? result->error_code : 0u;
  mailbox[15] = result ? result->sticky_error : 0u;
}

int main(void) {
  static uint8_t payload[P6_RUNTIME_PAYLOAD_BYTES];
  static uint8_t rx_payload[P6_RUNTIME_PAYLOAD_BYTES];
  uint32_t rx_payload_len = 0u;
  ir_p6_payload_result_t result = {0};
  p6_mmio_context_t ctx = {
    .base = (volatile uint32_t *)IR_PL_BASEADDR,
  };
  ir_mmio_t io = {
    .ctx = &ctx,
    .read32 = p6_read32,
    .write32 = p6_write32,
  };
  ir_p6_payload_config_t config = {
    .session = 0x2201u,
    .lane_mask = 0x3u,
    .ack_lane_mask = 0x3u,
    .payload_len = P6_RUNTIME_PAYLOAD_BYTES,
    .pattern_id = 9u,
    .seed = 0x00002201u,
    .timeout_cycles = 64000000u,
  };

  p6_fill_payload(payload, P6_RUNTIME_PAYLOAD_BYTES);
  int status = ir_driver_p6_run_mailbox_payload(&io, &config, payload, P6_RUNTIME_MAX_POLLS, &result);
  if (status == 0) {
    if (ir_driver_p6_read_rx_payload(&io, rx_payload, sizeof(rx_payload), &rx_payload_len) != 0 ||
        rx_payload_len != P6_RUNTIME_PAYLOAD_BYTES) {
      status = -20;
    } else {
      for (uint32_t idx = 0u; idx < P6_RUNTIME_PAYLOAD_BYTES; idx++) {
        if (rx_payload[idx] != payload[idx]) {
          status = -21;
          break;
        }
      }
    }
  }
  (void)ir_driver_shutdown(&io);
  p6_write_result_mailbox(status, &result);
  return status == 0 ? 0 : 1;
}
