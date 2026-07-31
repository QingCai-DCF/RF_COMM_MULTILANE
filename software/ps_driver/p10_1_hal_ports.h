#ifndef P10_1_HAL_PORTS_H
#define P10_1_HAL_PORTS_H

#include "p10_1_hal.h"

/* The adapters expose task/event entry points without placing an RTOS API in
 * the core service. Platform startup code binds concrete DMA/cache/timer
 * functions into p10_1_hal_t. */
typedef struct p10_1_task_hooks {
  int (*dma_completion_task_wait)(void *context, uint32_t timeout_ticks);
  int (*performance_control_task_wait)(void *context, uint32_t timeout_ticks);
  int (*trace_drain_task_wait)(void *context, uint32_t timeout_ticks);
  void (*watchdog_notify)(void *context);
  void (*telemetry_notify)(void *context);
  void *context;
} p10_1_task_hooks_t;

int p10_1_baremetal_hal_bind(p10_1_hal_t *destination,
                             const p10_1_hal_t *platform);
int p10_1_freertos_hal_bind(p10_1_hal_t *destination,
                            const p10_1_hal_t *platform,
                            const p10_1_task_hooks_t *hooks);
int p10_1_host_hal_bind(p10_1_hal_t *destination,
                        const p10_1_hal_t *platform);

#endif
