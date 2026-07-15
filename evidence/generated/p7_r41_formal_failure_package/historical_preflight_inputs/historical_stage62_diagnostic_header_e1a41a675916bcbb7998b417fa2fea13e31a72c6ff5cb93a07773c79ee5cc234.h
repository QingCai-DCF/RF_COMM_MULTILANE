#ifndef P7_STAGE62_DIAGNOSTIC_H
#define P7_STAGE62_DIAGNOSTIC_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum p7_copy_diagnostic_classification {
  P7_COPY_DIAGNOSTIC_COPY_OK = 0,
  P7_COPY_DIAGNOSTIC_SOURCE_CHANGED = 1,
  P7_COPY_DIAGNOSTIC_DEST_UNCHANGED = 2,
  P7_COPY_DIAGNOSTIC_DEST_WRONG_VALUE = 3,
  P7_COPY_DIAGNOSTIC_DEST_PARTIAL_WRITE = 4,
  P7_COPY_DIAGNOSTIC_READBACK_VISIBILITY_SUSPECT = 5,
  P7_COPY_DIAGNOSTIC_CANARY_PRECHECK_FAILED = 6,
  P7_COPY_DIAGNOSTIC_RECORD_INVALID = 7
};

enum p7_copy_diagnostic_capture_flags {
  P7_COPY_DIAGNOSTIC_CAPTURE_SOURCE_BEFORE = 1u << 0,
  P7_COPY_DIAGNOSTIC_CAPTURE_SOURCE_AFTER = 1u << 1,
  P7_COPY_DIAGNOSTIC_CAPTURE_DESTINATION_BEFORE = 1u << 2,
  P7_COPY_DIAGNOSTIC_CAPTURE_DESTINATION_AFTER = 1u << 3,
  P7_COPY_DIAGNOSTIC_CAPTURE_CANARY_VERIFIED = 1u << 4,
  P7_COPY_DIAGNOSTIC_CAPTURE_COPY_EXECUTED = 1u << 5,
  P7_COPY_DIAGNOSTIC_CAPTURE_RUNTIME_REGISTERS = 1u << 6,
  P7_COPY_DIAGNOSTIC_CAPTURE_PAGE_TABLES = 1u << 7,
  P7_COPY_DIAGNOSTIC_CAPTURE_PL310 = 1u << 8,
  P7_COPY_DIAGNOSTIC_CAPTURE_GENERIC_PAIR = 1u << 9
};

uint32_t p7_stage62_classify_copy_observation(
    const volatile uint8_t *source_before,
    const volatile uint8_t *source_after,
    const volatile uint8_t *destination_before,
    const volatile uint8_t *destination_after, uint32_t size);

int p7_stage62_snapshot_matches_byte(const volatile uint8_t *snapshot,
                                     uint32_t size, uint8_t expected,
                                     uint32_t *first_bad);

uint32_t p7_stage62_reconcile_independent_readback(
    const volatile uint8_t *cpu_readback,
    const volatile uint8_t *independent_readback, uint32_t size);

uint32_t p7_stage62_record_crc32(const volatile uint8_t *record,
                                uint32_t size);

#ifdef __cplusplus
}
#endif

#endif
