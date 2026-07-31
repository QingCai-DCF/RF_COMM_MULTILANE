#include "p10_1_hal_ports.h"

#include <string.h>

int p10_1_freertos_hal_bind(p10_1_hal_t *destination,
                            const p10_1_hal_t *platform,
                            const p10_1_task_hooks_t *hooks) {
  if (destination == NULL || platform == NULL || hooks == NULL ||
      hooks->dma_completion_task_wait == NULL ||
      hooks->performance_control_task_wait == NULL ||
      hooks->trace_drain_task_wait == NULL ||
      hooks->watchdog_notify == NULL || hooks->telemetry_notify == NULL)
    return -1;
  memcpy(destination, platform, sizeof(*destination));
  return 0;
}
