#ifndef P10_1_HAL_H
#define P10_1_HAL_H

#include <stddef.h>
#include <stdint.h>

/* OS-independent hardware abstraction used by the production performance
 * service. Bare-metal, FreeRTOS, and host-native ports implement this exact
 * interface; the state machine itself contains no scheduler dependency. */
typedef struct p10_1_hal {
  void *context;
  uint64_t (*timer_now)(void *context);
  uint64_t (*timer_frequency)(void *context);
  int (*payload_generate)(void *context, uint32_t pattern, uint32_t seed,
                          uint64_t offset, uint8_t *buffer, size_t length);
  void (*integrity_begin)(void *context);
  void (*integrity_update)(void *context, const uint8_t *data, size_t length);
  int (*integrity_final)(void *context, uint32_t *crc32, uint8_t sha256[32]);
  int (*cache_flush)(void *context, uintptr_t address, size_t length);
  int (*cache_invalidate)(void *context, uintptr_t address, size_t length);
  int (*dma_submit)(void *context, uint32_t descriptor_token,
                    uintptr_t address, size_t length);
  /* dma_poll_complete returns 0 when the named descriptor completed,
   * a positive value while it remains pending, and a negative value on
   * an unrecoverable DMA error. */
  int (*dma_poll_complete)(void *context, uint32_t descriptor_token);
  int (*remote_verify_segment)(void *context, uint32_t stream_id,
                               uint32_t object_id, uint32_t generation,
                               uint64_t offset, const uint8_t *data,
                               size_t length, int final_segment);
  int (*remote_atomic_commit)(void *context, uint32_t stream_id,
                              uint32_t object_id, uint32_t generation,
                              uint64_t total_length, uint32_t crc32,
                              const uint8_t sha256[32]);
  void (*watchdog_kick)(void *context);
  void (*telemetry_publish)(void *context, const void *snapshot,
                            size_t snapshot_size);
} p10_1_hal_t;

#endif
