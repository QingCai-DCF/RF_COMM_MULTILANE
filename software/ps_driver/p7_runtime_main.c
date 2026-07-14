#include "p7_app_service.h"
#include "p7_stage62_microtest.h"

#include "xil_cache.h"
#include "xil_io.h"

#include <stdint.h>

#ifndef IR_PL_BASEADDR
#define IR_PL_BASEADDR UINT32_C(0x43C00000)
#endif

typedef struct p7_mmio_context {
  UINTPTR base;
} p7_mmio_context_t;

static uint32_t p7_read32(void *context, uint32_t offset) {
  p7_mmio_context_t *mmio = (p7_mmio_context_t *)context;
  return Xil_In32(mmio->base + offset);
}

static void p7_write32(void *context, uint32_t offset, uint32_t value) {
  p7_mmio_context_t *mmio = (p7_mmio_context_t *)context;
  Xil_Out32(mmio->base + offset, value);
}

int main(void) {
  /* The mailbox and descriptors are written asynchronously by XSDB/JTAG.
   * Disable the Cortex-A9 data cache before touching shared memory so host
   * commands cannot be overwritten by dirty cache-line writeback. */
  Xil_DCacheDisable();
  int microtest_status = p7_stage62_microtest_try_run();
  if (microtest_status != 0) {
    /* The isolated Stage62 microtest never constructs an MMIO context and
     * therefore cannot touch PL registers or drive a functional stage. */
    return microtest_status > 0 ? 0 : 1;
  }
  p7_mmio_context_t context = {
      .base = (UINTPTR)IR_PL_BASEADDR,
  };
  ir_mmio_t io = {
      .ctx = &context,
      .read32 = p7_read32,
      .write32 = p7_write32,
  };
  volatile p7_mailbox_control_t *mailbox =
      (volatile p7_mailbox_control_t *)(uintptr_t)P7_MAILBOX_BASEADDR;
  volatile p7_object_descriptor_t *descriptors =
      (volatile p7_object_descriptor_t *)(uintptr_t)P7_DESCRIPTOR_BASEADDR;
  int status = p7_app_service_run(&io, mailbox, descriptors);
  /* p7_app_service_run owns and verifies shutdown on every return path.  Do
   * not issue a second unreported shutdown whose readback result could be
   * discarded or contradict the published terminal mailbox state. */
  return status == 0 ? 0 : 1;
}
