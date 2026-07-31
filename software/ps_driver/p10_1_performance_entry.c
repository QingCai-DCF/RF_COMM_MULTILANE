#include <stdint.h>

#include "p10_1_contract.h"
#include "p10_1_service.h"

#ifndef P10_1_ENDPOINT_ROLE
#error P10_1_ENDPOINT_ROLE must be fixed at compile time
#endif

#if P10_1_ENDPOINT_ROLE != 1 && P10_1_ENDPOINT_ROLE != 2
#error P10_1_ENDPOINT_ROLE must be 1 (fixed) or 2 (rotating)
#endif

/* Offline-linked role identity. Platform startup binds the HAL and calls the
 * service; this entry is deliberately inert until a future authorized runner
 * performs safe boot and explicit configuration. */
const volatile uint32_t p10_1_endpoint_role
    __attribute__((used, section(".p10_1_identity"))) = P10_1_ENDPOINT_ROLE;
const volatile uint32_t p10_1_performance_capability
    __attribute__((used, section(".p10_1_identity"))) =
    P10_1_PERF_CAPABILITY;
const volatile uint64_t p10_1_max_stream_size
    __attribute__((used, section(".p10_1_identity"))) =
    P10_1_MAX_STREAM_SIZE_BYTES;

void p10_1_performance_entry(void) {
  for (;;) {
    __asm__ volatile("wfi");
  }
}
