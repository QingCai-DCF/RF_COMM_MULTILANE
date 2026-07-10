#include "p7_admission_contract.h"

#include <stdint.h>

int main(void) {
  const uint64_t cutoff = UINT64_C(1740) * UINT64_C(1000);
  const uint64_t guard = UINT64_C(1) * UINT64_C(1000);
  unsigned transmit_calls = 0U;

  if (!p7_admission_deadline_allowed(cutoff - guard - 1U, cutoff, guard)) {
    return 1;
  }
  if (p7_admission_deadline_allowed(cutoff - guard, cutoff, guard)) {
    return 2;
  }
  if (p7_admission_deadline_allowed(cutoff, cutoff, guard)) {
    return 3;
  }
  if (p7_admission_deadline_allowed(cutoff + 1U, cutoff, guard)) {
    return 4;
  }
  if (!p7_admission_deadline_allowed(UINT64_C(999999), 0U, 0U)) {
    return 5;
  }

  /* Model the exact call-site guard: a late READY takes the reject branch and
   * must not invoke the processing/transmit path. */
  if (p7_admission_deadline_allowed(cutoff - guard, cutoff, guard)) {
    transmit_calls += 1U;
  }
  return transmit_calls == 0U ? 0 : 6;
}
