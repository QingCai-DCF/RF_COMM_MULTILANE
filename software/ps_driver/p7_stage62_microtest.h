#ifndef P7_STAGE62_MICROTEST_H
#define P7_STAGE62_MICROTEST_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define P7_STAGE62_MICROTEST_CONTROL_ADDRESS UINT32_C(0x00022300)
#define P7_STAGE62_MICROTEST_OCM_SOURCE_ADDRESS UINT32_C(0x00022400)
#define P7_STAGE62_MICROTEST_OCM_DESTINATION_ADDRESS UINT32_C(0x00022500)
#define P7_STAGE62_MICROTEST_DDR_SOURCE_ADDRESS UINT32_C(0x00100000)
#define P7_STAGE62_MICROTEST_DDR_DESTINATION_ADDRESS UINT32_C(0x00900000)
#define P7_STAGE62_MICROTEST_FIXTURE_BYTES UINT32_C(256)
#define P7_STAGE62_MICROTEST_TARGET_OFFSET UINT32_C(64)
#define P7_STAGE62_MICROTEST_CONTROL_MAGIC UINT32_C(0x434d3750) /* P7MC */
#define P7_STAGE62_MICROTEST_RECORD_MAGIC UINT32_C(0x544d3750) /* P7MT */
#define P7_STAGE62_MICROTEST_VERSION UINT32_C(1)
#define P7_STAGE62_MICROTEST_RECORD_BYTES UINT32_C(1536)
#define P7_STAGE62_MICROTEST_HEADER_BYTES UINT32_C(512)
#define P7_STAGE62_MICROTEST_SOURCE_GUARD UINT32_C(0x3c)
#define P7_STAGE62_MICROTEST_DESTINATION_GUARD UINT32_C(0xc3)
#define P7_STAGE62_MICROTEST_DESTINATION_CANARY UINT32_C(0xa5)

enum p7_stage62_microtest_case {
  P7_STAGE62_MICROTEST_OCM_TO_OCM = 1,
  P7_STAGE62_MICROTEST_OCM_TO_DDR = 2,
  P7_STAGE62_MICROTEST_DDR_TO_OCM = 3,
  P7_STAGE62_MICROTEST_DDR_TO_DDR = 4
};

enum p7_stage62_microtest_state {
  P7_STAGE62_MICROTEST_ARMED = 1,
  P7_STAGE62_MICROTEST_RUNNING = 2,
  P7_STAGE62_MICROTEST_COMPLETE = 3,
  P7_STAGE62_MICROTEST_FAILED = 4
};

enum p7_stage62_microtest_space {
  P7_STAGE62_MICROTEST_SPACE_OCM = 1,
  P7_STAGE62_MICROTEST_SPACE_DDR = 2
};

enum p7_stage62_microtest_error {
  P7_STAGE62_MICROTEST_ERROR_NONE = 0,
  P7_STAGE62_MICROTEST_ERROR_CONTROL = 1,
  P7_STAGE62_MICROTEST_ERROR_PRECHECK = 2,
  P7_STAGE62_MICROTEST_ERROR_COPY_OBSERVATION = 3,
  P7_STAGE62_MICROTEST_ERROR_GUARD = 4,
  P7_STAGE62_MICROTEST_ERROR_PUBLICATION = 5,
  P7_STAGE62_MICROTEST_ERROR_WIPE = 6
};

enum p7_stage62_microtest_first_bad_domain {
  P7_STAGE62_MICROTEST_BAD_NONE = 0,
  P7_STAGE62_MICROTEST_BAD_SOURCE_BEFORE = 1,
  P7_STAGE62_MICROTEST_BAD_DESTINATION_BEFORE = 2,
  P7_STAGE62_MICROTEST_BAD_SOURCE_AFTER = 3,
  P7_STAGE62_MICROTEST_BAD_DESTINATION_AFTER = 4,
  P7_STAGE62_MICROTEST_BAD_SOURCE_GUARD = 5,
  P7_STAGE62_MICROTEST_BAD_DESTINATION_GUARD = 6
};

typedef struct __attribute__((aligned(64))) p7_stage62_microtest_control {
  uint32_t magic;
  uint32_t version;
  uint32_t case_id;
  uint32_t transfer_length;
  uint32_t source_alignment;
  uint32_t destination_alignment;
  uint32_t run_id_crc32;
  uint32_t immutable_crc32;
  volatile uint32_t state;
  volatile uint32_t result;
  volatile uint32_t record_address;
  volatile uint32_t record_bytes;
  volatile uint32_t record_magic_readback;
  volatile uint32_t wipe_verified;
  uint32_t diagnostic_only;
  uint32_t coverage_claimed;
} p7_stage62_microtest_control_t;

typedef struct __attribute__((aligned(64))) p7_stage62_microtest_record {
  uint32_t magic;
  uint32_t version;
  uint32_t record_length;
  uint32_t sequence;
  uint32_t record_crc32;
  uint32_t terminal_status;
  uint32_t classification;
  uint32_t error_code;
  uint32_t case_id;
  uint32_t transfer_length;
  uint32_t source_fixture_address;
  uint32_t destination_fixture_address;
  uint32_t source_target_address;
  uint32_t destination_target_address;
  uint32_t source_alignment;
  uint32_t destination_alignment;
  uint32_t source_mod4;
  uint32_t destination_mod4;
  uint32_t source_mod64;
  uint32_t destination_mod64;
  uint32_t source_space;
  uint32_t destination_space;
  uint32_t first_bad_domain;
  uint32_t first_bad_index;
  uint32_t expected_byte;
  uint32_t observed_byte;
  uint32_t source_before_byte;
  uint32_t source_after_byte;
  uint32_t destination_before_byte;
  uint32_t destination_after_byte;
  uint32_t source_guards_before_ok;
  uint32_t destination_guards_before_ok;
  uint32_t source_pattern_before_ok;
  uint32_t destination_canary_before_ok;
  uint32_t source_guards_after_ok;
  uint32_t destination_guards_after_ok;
  uint32_t source_pattern_after_ok;
  uint32_t copy_executed;
  uint32_t output_wipe_required;
  uint32_t output_wipe_byte;
  uint32_t source_guard_byte;
  uint32_t destination_guard_byte;
  uint32_t output_canary_byte;
  uint32_t pattern_base;
  uint32_t capture_flags;
  uint32_t stack_pointer;
  uint32_t sctlr;
  uint32_t actlr;
  uint32_t ttbr0;
  uint32_t ttbr1;
  uint32_t ttbcr;
  uint32_t dacr;
  uint32_t source_l1_descriptor_address;
  uint32_t source_l1_descriptor;
  uint32_t source_l2_descriptor_address;
  uint32_t source_l2_descriptor;
  uint32_t destination_l1_descriptor_address;
  uint32_t destination_l1_descriptor;
  uint32_t destination_l2_descriptor_address;
  uint32_t destination_l2_descriptor;
  uint32_t pl310_control;
  uint32_t pl310_aux_control;
  uint32_t pl310_cache_type;
  uint32_t pl310_raw_interrupt_status;
  uint32_t mmu_enabled;
  uint32_t dcache_enabled;
  uint32_t icache_enabled;
  uint32_t run_id_crc32;
  uint32_t control_crc32;
  uint32_t control_consumed;
  uint32_t diagnostic_only;
  uint32_t coverage_claimed;
  uint32_t source_before_crc32;
  uint32_t source_after_crc32;
  uint32_t destination_before_crc32;
  uint32_t destination_after_crc32;
  uint32_t record_address;
  uint32_t record_bytes;
  uint32_t source_target_offset;
  uint32_t destination_target_offset;
  uint8_t source_before_sha256[32];
  uint8_t source_after_sha256[32];
  uint8_t destination_before_sha256[32];
  uint8_t destination_after_sha256[32];
  uint32_t reserved[16];
  uint8_t source_before[256];
  uint8_t source_after[256];
  uint8_t destination_before[256];
  uint8_t destination_after[256];
} p7_stage62_microtest_record_t;

/* Returns 0 when the fixed control block is all-zero, 1 after a handled PASS,
 * and -1 after a handled fail-closed diagnostic.  No PL/MMIO access occurs. */
int p7_stage62_microtest_try_run(void);

void p7_stage62_microtest_copy_bytes(volatile uint8_t *destination,
                                     const volatile uint8_t *source,
                                     uint32_t size);

#ifdef __cplusplus
}
#endif

#endif
