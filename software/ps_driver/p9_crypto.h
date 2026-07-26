#ifndef P9_CRYPTO_H
#define P9_CRYPTO_H

#include <stddef.h>
#include <stdint.h>

uint32_t p9_crc32(const uint8_t *data, size_t size);
void p9_sha256(const uint8_t *data, size_t size, uint8_t output[32]);

#endif
