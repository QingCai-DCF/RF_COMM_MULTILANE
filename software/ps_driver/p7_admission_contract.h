#ifndef P7_ADMISSION_CONTRACT_H
#define P7_ADMISSION_CONTRACT_H

#include <stdint.h>

/* Pure stationary admission boundary shared with the native offline test.
 * A zero cutoff disables the gate.  At or inside the guard, READY must be
 * rejected before p7_process_descriptor opens P6 or can drive TFDU TXD. */
static inline int p7_admission_deadline_allowed(
    uint64_t now_ticks, uint64_t cutoff_ticks, uint64_t guard_ticks) {
  if (cutoff_ticks == 0U) return 1;
  if (now_ticks >= cutoff_ticks) return 0;
  return cutoff_ticks - now_ticks > guard_ticks;
}

#endif
