#ifndef P9_CRYPTO_H
#define P9_CRYPTO_H

#include <stddef.h>
#include <stdint.h>

typedef struct p9_sha256_context {
  uint32_t state[8];
  uint64_t total_bytes;
  uint8_t block[64];
  uint32_t block_used;
} p9_sha256_context_t;

uint32_t p9_crc32_begin(void);
uint32_t p9_crc32_update(uint32_t state, const uint8_t *data, size_t size);
uint32_t p9_crc32_end(uint32_t state);
uint32_t p9_crc32(const uint8_t *data, size_t size);
void p9_sha256_init(p9_sha256_context_t *context);
void p9_sha256_update(p9_sha256_context_t *context,
                      const uint8_t *data, size_t size);
void p9_sha256_final(p9_sha256_context_t *context, uint8_t output[32]);
void p9_sha256(const uint8_t *data, size_t size, uint8_t output[32]);

#endif
