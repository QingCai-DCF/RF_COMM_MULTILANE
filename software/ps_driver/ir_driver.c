#include "ir_driver.h"
#include "ir_regs.h"

int ir_driver_apply_profile(void) {
  /* Offline stub documents the required order: reset, write profile, commit,
     readback critical registers, enable PHY, wait startup, clear counters,
     start/poll/stop/shutdown/read final counters. */
  return 0;
}

int ir_driver_shutdown(void) {
  return 0;
}
