#include "p7_stage62_diagnostic.h"

#include <stddef.h>

static uint32_t first_mismatch(const volatile uint8_t *left,
                               const volatile uint8_t *right,
                               uint32_t size) {
  for (uint32_t index = 0U; index < size; ++index) {
    if (left[index] != right[index]) return index;
  }
  return UINT32_MAX;
}

uint32_t p7_stage62_classify_copy_observation(
    const volatile uint8_t *source_before,
    const volatile uint8_t *source_after,
    const volatile uint8_t *destination_before,
    const volatile uint8_t *destination_after, uint32_t size) {
  uint32_t expected_count = 0U;
  uint32_t unchanged_count = 0U;
  if ((source_before == NULL || source_after == NULL ||
       destination_before == NULL || destination_after == NULL) &&
      size != 0U) {
    return P7_COPY_DIAGNOSTIC_RECORD_INVALID;
  }
  if (first_mismatch(source_before, source_after, size) != UINT32_MAX) {
    return P7_COPY_DIAGNOSTIC_SOURCE_CHANGED;
  }
  if (first_mismatch(source_before, destination_after, size) == UINT32_MAX) {
    return P7_COPY_DIAGNOSTIC_COPY_OK;
  }
  if (first_mismatch(destination_before, destination_after, size) ==
      UINT32_MAX) {
    return P7_COPY_DIAGNOSTIC_DEST_UNCHANGED;
  }
  for (uint32_t index = 0U; index < size; ++index) {
    if (destination_after[index] == source_before[index]) expected_count += 1U;
    if (destination_after[index] == destination_before[index]) {
      unchanged_count += 1U;
    }
  }
  if (expected_count != 0U || unchanged_count != 0U) {
    return P7_COPY_DIAGNOSTIC_DEST_PARTIAL_WRITE;
  }
  return P7_COPY_DIAGNOSTIC_DEST_WRONG_VALUE;
}

int p7_stage62_snapshot_matches_byte(const volatile uint8_t *snapshot,
                                     uint32_t size, uint8_t expected,
                                     uint32_t *first_bad) {
  if (first_bad != NULL) *first_bad = UINT32_MAX;
  if (snapshot == NULL && size != 0U) return 0;
  for (uint32_t index = 0U; index < size; ++index) {
    if (snapshot[index] != expected) {
      if (first_bad != NULL) *first_bad = index;
      return 0;
    }
  }
  return 1;
}

uint32_t p7_stage62_reconcile_independent_readback(
    const volatile uint8_t *cpu_readback,
    const volatile uint8_t *independent_readback, uint32_t size) {
  if ((cpu_readback == NULL || independent_readback == NULL) && size != 0U) {
    return P7_COPY_DIAGNOSTIC_RECORD_INVALID;
  }
  return first_mismatch(cpu_readback, independent_readback, size) == UINT32_MAX
             ? P7_COPY_DIAGNOSTIC_COPY_OK
             : P7_COPY_DIAGNOSTIC_READBACK_VISIBILITY_SUSPECT;
}

uint32_t p7_stage62_record_crc32(const volatile uint8_t *record,
                                uint32_t size) {
  static const uint32_t crc_table[16] = {
      UINT32_C(0x00000000), UINT32_C(0x1db71064),
      UINT32_C(0x3b6e20c8), UINT32_C(0x26d930ac),
      UINT32_C(0x76dc4190), UINT32_C(0x6b6b51f4),
      UINT32_C(0x4db26158), UINT32_C(0x5005713c),
      UINT32_C(0xedb88320), UINT32_C(0xf00f9344),
      UINT32_C(0xd6d6a3e8), UINT32_C(0xcb61b38c),
      UINT32_C(0x9b64c2b0), UINT32_C(0x86d3d2d4),
      UINT32_C(0xa00ae278), UINT32_C(0xbdbdf21c)};
  uint32_t crc = UINT32_C(0xffffffff);
  if (record == NULL && size != 0U) return 0U;
  for (uint32_t index = 0U; index < size; ++index) {
    uint8_t value =
        (index < 4U || (index >= 16U && index < 20U)) ? 0U : record[index];
    crc ^= value;
    crc = (crc >> 4) ^ crc_table[crc & 0x0fU];
    crc = (crc >> 4) ^ crc_table[crc & 0x0fU];
  }
  return crc ^ UINT32_C(0xffffffff);
}
