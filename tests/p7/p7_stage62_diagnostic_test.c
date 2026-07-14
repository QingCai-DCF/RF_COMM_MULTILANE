#include "p7_app_service.h"
#include "p7_stage62_diagnostic.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define P7_DIAGNOSTIC_MATRIX_MAX_BYTES 247U
#define P7_DIAGNOSTIC_MATRIX_ALIGNMENT 64U
#define P7_DIAGNOSTIC_MATRIX_STORAGE_BYTES 384U

static int require_classification(uint32_t expected, const uint8_t *before,
                                  const uint8_t *after,
                                  const uint8_t *destination_before,
                                  const uint8_t *destination_after,
                                  uint32_t size) {
  return p7_stage62_classify_copy_observation(
             before, after, destination_before, destination_after, size) ==
         expected;
}

static uint32_t reference_record_crc32(const uint8_t *record, uint32_t size) {
  uint32_t crc = UINT32_C(0xffffffff);
  for (uint32_t index = 0U; index < size; ++index) {
    uint8_t value =
        (index < 4U || (index >= 16U && index < 20U)) ? 0U : record[index];
    crc ^= value;
    for (uint32_t bit = 0U; bit < 8U; ++bit) {
      crc = (crc >> 1) ^
            ((crc & 1U) != 0U ? UINT32_C(0xedb88320) : 0U);
    }
  }
  return crc ^ UINT32_C(0xffffffff);
}

static int run_alignment_matrix(uint32_t *case_count) {
  uint8_t source_before[P7_DIAGNOSTIC_MATRIX_STORAGE_BYTES]
      __attribute__((aligned(64)));
  uint8_t source_after[P7_DIAGNOSTIC_MATRIX_STORAGE_BYTES]
      __attribute__((aligned(64)));
  uint8_t destination_before[P7_DIAGNOSTIC_MATRIX_STORAGE_BYTES]
      __attribute__((aligned(64)));
  uint8_t destination_after[P7_DIAGNOSTIC_MATRIX_STORAGE_BYTES]
      __attribute__((aligned(64)));

  *case_count = 0U;
  for (uint32_t source_mod64 = 0U;
       source_mod64 < P7_DIAGNOSTIC_MATRIX_ALIGNMENT; ++source_mod64) {
    memset(source_before, 0x69, sizeof(source_before));
    memset(source_after, 0x69, sizeof(source_after));
    for (uint32_t index = 0U; index < P7_DIAGNOSTIC_MATRIX_MAX_BYTES;
         ++index) {
      uint8_t value = (uint8_t)(0x11U + index * 37U + source_mod64 * 13U);
      source_before[source_mod64 + index] = value == 0U ? 0x7bU : value;
    }
    memcpy(source_after + source_mod64, source_before + source_mod64,
           P7_DIAGNOSTIC_MATRIX_MAX_BYTES);
    for (uint32_t destination_mod64 = 0U;
         destination_mod64 < P7_DIAGNOSTIC_MATRIX_ALIGNMENT;
         ++destination_mod64) {
      memset(destination_before, P7_OUTPUT_CANARY_BYTE,
             sizeof(destination_before));
      memset(destination_after, P7_OUTPUT_CANARY_BYTE,
             sizeof(destination_after));
      if ((((uintptr_t)(source_before + source_mod64)) & 63U) !=
              source_mod64 ||
          (((uintptr_t)(destination_after + destination_mod64)) & 63U) !=
              destination_mod64) {
        return 0;
      }
      for (uint32_t length = 1U;
           length <= P7_DIAGNOSTIC_MATRIX_MAX_BYTES; ++length) {
        memcpy(destination_after + destination_mod64,
               source_before + source_mod64, length);
        if (!require_classification(
                P7_COPY_DIAGNOSTIC_COPY_OK,
                source_before + source_mod64, source_after + source_mod64,
                destination_before + destination_mod64,
                destination_after + destination_mod64, length)) {
          return 0;
        }
        if (destination_mod64 != 0U &&
            destination_after[destination_mod64 - 1U] !=
                P7_OUTPUT_CANARY_BYTE) {
          return 0;
        }
        if (destination_after[destination_mod64 + length] !=
            P7_OUTPUT_CANARY_BYTE) {
          return 0;
        }
        *case_count += 1U;
      }
    }
  }
  return 1;
}

int main(void) {
  uint8_t source_before[247] __attribute__((aligned(64)));
  uint8_t source_after[247] __attribute__((aligned(64)));
  uint8_t destination_before[247] __attribute__((aligned(64)));
  uint8_t destination_after[247] __attribute__((aligned(64)));
  uint32_t first_bad = UINT32_MAX;
  uint32_t matrix_cases = 0U;
  uint8_t record[P7_FIRST_ERROR_DIAGNOSTIC_TOTAL_BYTES]
      __attribute__((aligned(64)));

  for (uint32_t index = 0U; index < sizeof(source_before); ++index) {
    source_before[index] = (uint8_t)(index + 1U);
  }
  memcpy(source_after, source_before, sizeof(source_before));
  memset(destination_before, P7_OUTPUT_CANARY_BYTE,
         sizeof(destination_before));
  memcpy(destination_after, source_before, sizeof(source_before));
  if (sizeof(p7_first_error_diagnostic_t) != 1536U ||
      _Alignof(p7_first_error_diagnostic_t) != 64U ||
      offsetof(p7_first_error_diagnostic_t, source_before) != 512U ||
      offsetof(p7_first_error_diagnostic_t, source_after) != 768U ||
      offsetof(p7_first_error_diagnostic_t, destination_before) != 1024U ||
      offsetof(p7_first_error_diagnostic_t, destination_after) != 1280U) {
    return 1;
  }
  if (!require_classification(P7_COPY_DIAGNOSTIC_COPY_OK, source_before,
                              source_after, destination_before,
                              destination_after, sizeof(source_before))) {
    return 2;
  }
  source_after[11] ^= 0x55U;
  if (!require_classification(P7_COPY_DIAGNOSTIC_SOURCE_CHANGED,
                              source_before, source_after, destination_before,
                              destination_after, sizeof(source_before))) {
    return 3;
  }
  source_after[11] = source_before[11];
  memcpy(destination_after, destination_before, sizeof(destination_after));
  if (!require_classification(P7_COPY_DIAGNOSTIC_DEST_UNCHANGED,
                              source_before, source_after, destination_before,
                              destination_after, sizeof(source_before))) {
    return 4;
  }
  memset(source_before, 0x11, sizeof(source_before));
  memcpy(source_after, source_before, sizeof(source_before));
  memset(destination_after, 0x3c, sizeof(destination_after));
  if (!require_classification(P7_COPY_DIAGNOSTIC_DEST_WRONG_VALUE,
                              source_before, source_after, destination_before,
                              destination_after, sizeof(source_before))) {
    return 5;
  }
  memcpy(destination_after, source_before, sizeof(destination_after));
  destination_after[5] = P7_OUTPUT_CANARY_BYTE;
  if (!require_classification(P7_COPY_DIAGNOSTIC_DEST_PARTIAL_WRITE,
                              source_before, source_after, destination_before,
                              destination_after, sizeof(source_before))) {
    return 6;
  }
  if (p7_stage62_classify_copy_observation(
          NULL, source_after, destination_before, destination_after, 1U) !=
      P7_COPY_DIAGNOSTIC_RECORD_INVALID) {
    return 7;
  }
  memset(destination_before, P7_OUTPUT_CANARY_BYTE,
         sizeof(destination_before));
  if (!p7_stage62_snapshot_matches_byte(
          destination_before, sizeof(destination_before),
          (uint8_t)P7_OUTPUT_CANARY_BYTE, &first_bad) ||
      first_bad != UINT32_MAX) {
    return 8;
  }
  destination_before[29] = 0x00U;
  if (p7_stage62_snapshot_matches_byte(
          destination_before, sizeof(destination_before),
          (uint8_t)P7_OUTPUT_CANARY_BYTE, &first_bad) ||
      first_bad != 29U) {
    return 9;
  }
  memcpy(destination_before, source_before, sizeof(destination_before));
  memcpy(destination_after, source_before, sizeof(destination_after));
  if (p7_stage62_reconcile_independent_readback(
          destination_before, destination_after,
          sizeof(destination_before)) != P7_COPY_DIAGNOSTIC_COPY_OK) {
    return 10;
  }
  destination_after[30] ^= 0x80U;
  if (p7_stage62_reconcile_independent_readback(
          destination_before, destination_after,
          sizeof(destination_before)) !=
      P7_COPY_DIAGNOSTIC_READBACK_VISIBILITY_SUSPECT) {
    return 11;
  }
  if (!run_alignment_matrix(&matrix_cases) || matrix_cases != 1011712U) {
    return 12;
  }
  for (uint32_t index = 0U; index < sizeof(record); ++index) {
    record[index] = (uint8_t)(index * 29U + 7U);
  }
  if (p7_stage62_record_crc32(record, sizeof(record)) !=
          reference_record_crc32(record, sizeof(record)) ||
      p7_stage62_record_crc32(record, sizeof(record)) == 0U) {
    return 13;
  }

  puts("P7_STAGE62_DIAGNOSTIC_LAYOUT=PASS");
  puts("P7_STAGE62_DIAGNOSTIC_CLASSIFICATIONS=PASS");
  puts("P7_STAGE62_DIAGNOSTIC_CANARY=PASS");
  puts("P7_STAGE62_DIAGNOSTIC_INDEPENDENT_READBACK=PASS");
  puts("P7_STAGE62_DIAGNOSTIC_LENGTH_RANGE=1..247");
  puts("P7_STAGE62_DIAGNOSTIC_SOURCE_MOD64_COUNT=64");
  puts("P7_STAGE62_DIAGNOSTIC_DESTINATION_MOD64_COUNT=64");
  puts("P7_STAGE62_DIAGNOSTIC_SOURCE_DESTINATION_MOD4_PAIRS=16");
  printf("P7_STAGE62_DIAGNOSTIC_MATRIX_CASES=%lu\n",
         (unsigned long)matrix_cases);
  puts("P7_STAGE62_DIAGNOSTIC_RECORD_CRC32=PASS");
  puts("P7_STAGE62_DIAGNOSTIC_RECORD_BYTES=1536");
  return 0;
}
