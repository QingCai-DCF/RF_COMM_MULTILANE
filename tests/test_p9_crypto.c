#include "p9_crypto.h"
#include "p9_runtime_protocol.h"

#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

static int expect_sha(const uint8_t *data, size_t size,
                      const uint8_t expected[32]) {
  uint8_t observed[32];
  p9_sha256(data, size, observed);
  if (memcmp(observed, expected, sizeof(observed)) != 0) {
    for (size_t index = 0U; index < sizeof(observed); ++index)
      printf("%02x", observed[index]);
    putchar('\n');
  }
  return memcmp(observed, expected, sizeof(observed)) == 0 ? 0 : 1;
}

static uint32_t reference_crc32(const uint8_t *data, size_t size) {
  uint32_t crc = UINT32_C(0xffffffff);
  for (size_t index = 0U; index < size; ++index) {
    crc ^= data[index];
    for (uint32_t bit = 0U; bit < 8U; ++bit)
      crc = (crc >> 1U) ^
          ((crc & 1U) != 0U ? UINT32_C(0xedb88320) : 0U);
  }
  return ~crc;
}

int main(void) {
  static const uint8_t sha_empty[32] = {
      0xe3,0xb0,0xc4,0x42,0x98,0xfc,0x1c,0x14,
      0x9a,0xfb,0xf4,0xc8,0x99,0x6f,0xb9,0x24,
      0x27,0xae,0x41,0xe4,0x64,0x9b,0x93,0x4c,
      0xa4,0x95,0x99,0x1b,0x78,0x52,0xb8,0x55};
  static const uint8_t sha_abc[32] = {
      0xba,0x78,0x16,0xbf,0x8f,0x01,0xcf,0xea,
      0x41,0x41,0x40,0xde,0x5d,0xae,0x22,0x23,
      0xb0,0x03,0x61,0xa3,0x96,0x17,0x7a,0x9c,
      0xb4,0x10,0xff,0x61,0xf2,0x00,0x15,0xad};
  static const uint8_t abc[] = {'a','b','c'};
  static const uint8_t digits[] = "123456789";
  uint8_t reference_data[4096];
  uint8_t changed_data[4096];
  size_t first_mismatch = SIZE_MAX;
  int empty_ok = expect_sha(NULL, 0U, sha_empty) == 0;
  int abc_ok = expect_sha(abc, sizeof(abc), sha_abc) == 0;
  uint32_t crc = p9_crc32(digits, sizeof(digits) - 1U);
  uint32_t generator = UINT32_C(0x31415926);
  for (size_t index = 0U; index < sizeof(reference_data); ++index) {
    generator = generator * UINT32_C(1664525) + UINT32_C(1013904223);
    reference_data[index] = (uint8_t)(generator >> 24U);
  }
  memcpy(changed_data, reference_data, sizeof(changed_data));
  changed_data[2049] ^= UINT8_C(0x80);
  uint32_t reference_crc = reference_crc32(
      reference_data, sizeof(reference_data));
  uint32_t incremental_state = p9_crc32_begin();
  incremental_state = p9_crc32_update(
      incremental_state, reference_data, 17U);
  incremental_state = p9_crc32_update(
      incremental_state, reference_data + 17U,
      sizeof(reference_data) - 17U);
  uint32_t compare_state = p9_crc32_update_compare(
      p9_crc32_begin(), reference_data, reference_data,
      sizeof(reference_data), &first_mismatch);
  int equal_compare_ok =
      first_mismatch == SIZE_MAX &&
      p9_crc32_end(compare_state) == reference_crc;
  compare_state = p9_crc32_update_compare(
      p9_crc32_begin(), reference_data, changed_data,
      sizeof(reference_data), &first_mismatch);
  int mismatch_compare_ok =
      first_mismatch == 2049U &&
      p9_crc32_end(compare_state) ==
          reference_crc32(changed_data, sizeof(changed_data));
  if (!empty_ok || !abc_ok || crc != UINT32_C(0xcbf43926) ||
      p9_crc32(reference_data, sizeof(reference_data)) != reference_crc ||
      p9_crc32_end(incremental_state) != reference_crc ||
      !equal_compare_ok || !mismatch_compare_ok ||
      sizeof(p9_mailbox_t) > 1024U ||
      (offsetof(p9_mailbox_t, pl_register_snapshot) & 3U) != 0U) {
    printf("EMPTY_OK=%d ABC_OK=%d CRC=%08x EQUAL_COMPARE=%d "
           "MISMATCH_COMPARE=%d MAILBOX=%u SNAPSHOT_OFFSET=%u\n",
           empty_ok, abc_ok, (unsigned)crc, equal_compare_ok,
           mismatch_compare_ok, (unsigned)sizeof(p9_mailbox_t),
           (unsigned)offsetof(p9_mailbox_t, pl_register_snapshot));
    puts("P9_CRYPTO_PROTOCOL_TEST=FAIL");
    return 1;
  }
  puts("P9_CRYPTO_PROTOCOL_TEST=PASS");
  return 0;
}
