#include "p7_stage62_microtest.h"

#include "p7_app_service.h"
#include "p7_stage62_diagnostic.h"
#include "xil_io.h"

#include <stddef.h>
#include <stdint.h>

#define P7_PL310_BASEADDR UINT32_C(0xf8f02000)
#define P7_PL310_CACHE_TYPE_OFFSET UINT32_C(0x004)
#define P7_PL310_CONTROL_OFFSET UINT32_C(0x100)
#define P7_PL310_AUX_CONTROL_OFFSET UINT32_C(0x104)
#define P7_PL310_RAW_INTERRUPT_STATUS_OFFSET UINT32_C(0x21c)

_Static_assert(sizeof(p7_stage62_microtest_control_t) == 64U,
               "P7 Stage62 microtest control must be 64 bytes");
_Static_assert(_Alignof(p7_stage62_microtest_control_t) == 64U,
               "P7 Stage62 microtest control must be 64-byte aligned");
_Static_assert(sizeof(p7_stage62_microtest_record_t) ==
                   P7_STAGE62_MICROTEST_RECORD_BYTES,
               "P7 Stage62 microtest record must be 1536 bytes");
_Static_assert(offsetof(p7_stage62_microtest_record_t, source_before) ==
                   P7_STAGE62_MICROTEST_HEADER_BYTES,
               "P7 Stage62 microtest snapshots must follow 512-byte header");
_Static_assert(offsetof(p7_stage62_microtest_record_t, source_after) == 768U &&
                   offsetof(p7_stage62_microtest_record_t,
                            destination_before) == 1024U &&
                   offsetof(p7_stage62_microtest_record_t,
                            destination_after) == 1280U,
               "P7 Stage62 microtest snapshots must be fixed and aligned");

static uint32_t p7_microtest_crc32(const volatile uint8_t *data,
                                   uint32_t size) {
  static const uint32_t table[16] = {
      UINT32_C(0x00000000), UINT32_C(0x1db71064),
      UINT32_C(0x3b6e20c8), UINT32_C(0x26d930ac),
      UINT32_C(0x76dc4190), UINT32_C(0x6b6b51f4),
      UINT32_C(0x4db26158), UINT32_C(0x5005713c),
      UINT32_C(0xedb88320), UINT32_C(0xf00f9344),
      UINT32_C(0xd6d6a3e8), UINT32_C(0xcb61b38c),
      UINT32_C(0x9b64c2b0), UINT32_C(0x86d3d2d4),
      UINT32_C(0xa00ae278), UINT32_C(0xbdbdf21c)};
  uint32_t crc = UINT32_C(0xffffffff);
  for (uint32_t index = 0U; index < size; ++index) {
    crc ^= data[index];
    crc = (crc >> 4) ^ table[crc & 0x0fU];
    crc = (crc >> 4) ^ table[crc & 0x0fU];
  }
  return crc ^ UINT32_C(0xffffffff);
}

static uint32_t p7_read_stack_pointer(void) {
  uint32_t value;
  __asm__ volatile("mov %0, sp" : "=r"(value));
  return value;
}

static uint32_t p7_read_sctlr(void) {
  uint32_t value;
  __asm__ volatile("mrc p15, 0, %0, c1, c0, 0" : "=r"(value));
  return value;
}

static uint32_t p7_read_actlr(void) {
  uint32_t value;
  __asm__ volatile("mrc p15, 0, %0, c1, c0, 1" : "=r"(value));
  return value;
}

static uint32_t p7_read_ttbr0(void) {
  uint32_t value;
  __asm__ volatile("mrc p15, 0, %0, c2, c0, 0" : "=r"(value));
  return value;
}

static uint32_t p7_read_ttbr1(void) {
  uint32_t value;
  __asm__ volatile("mrc p15, 0, %0, c2, c0, 1" : "=r"(value));
  return value;
}

static uint32_t p7_read_ttbcr(void) {
  uint32_t value;
  __asm__ volatile("mrc p15, 0, %0, c2, c0, 2" : "=r"(value));
  return value;
}

static uint32_t p7_read_dacr(void) {
  uint32_t value;
  __asm__ volatile("mrc p15, 0, %0, c3, c0, 0" : "=r"(value));
  return value;
}

static void p7_capture_translation_descriptor(
    uint32_t virtual_address, uint32_t sctlr, uint32_t ttbr0,
    uint32_t ttbr1, uint32_t ttbcr, uint32_t *l1_address,
    uint32_t *l1_value, uint32_t *l2_address, uint32_t *l2_value) {
  uint32_t n = ttbcr & 7U;
  uint32_t use_ttbr1 =
      n != 0U && (virtual_address >> (32U - n)) != 0U;
  uint32_t base;
  uint32_t index;
  *l1_address = UINT32_MAX;
  *l1_value = UINT32_MAX;
  *l2_address = UINT32_MAX;
  *l2_value = UINT32_MAX;
  if ((sctlr & 1U) == 0U) return;
  if (use_ttbr1 != 0U) {
    base = ttbr1 & UINT32_C(0xffffc000);
    index = (virtual_address >> 20) & UINT32_C(0x0fff);
  } else {
    uint32_t alignment_bits = 14U - n;
    uint32_t index_bits = 12U - n;
    uint32_t base_mask = ~((UINT32_C(1) << alignment_bits) - 1U);
    uint32_t index_mask = (UINT32_C(1) << index_bits) - 1U;
    base = ttbr0 & base_mask;
    index = (virtual_address >> 20) & index_mask;
  }
  *l1_address = base + index * 4U;
  *l1_value = Xil_In32(*l1_address);
  if ((*l1_value & 3U) == 1U) {
    *l2_address = (*l1_value & UINT32_C(0xfffffc00)) +
                  ((virtual_address >> 12) & UINT32_C(0x00ff)) * 4U;
    *l2_value = Xil_In32(*l2_address);
  }
}

static void p7_zero_volatile(volatile uint8_t *data, uint32_t size) {
  for (uint32_t index = 0U; index < size; ++index) data[index] = 0U;
  dsb();
}

static void p7_snapshot(volatile uint8_t *destination,
                        const volatile uint8_t *source) {
  for (uint32_t index = 0U; index < P7_STAGE62_MICROTEST_FIXTURE_BYTES;
       ++index) {
    destination[index] = source[index];
  }
  dsb();
}

void __attribute__((noinline)) p7_stage62_microtest_copy_bytes(
    volatile uint8_t *destination, const volatile uint8_t *source,
    uint32_t size) {
  for (uint32_t index = 0U; index < size; ++index) {
    uint8_t value = source[index];
    destination[index] = value;
  }
  dsb();
}

static uint32_t p7_pattern_base(uint32_t case_id) {
  static const uint8_t bases[4] = {0x11U, 0x41U, 0x71U, 0xd1U};
  return case_id >= 1U && case_id <= 4U ? bases[case_id - 1U] : 0U;
}

static uint32_t p7_first_fixture_mismatch(const volatile uint8_t *fixture,
                                          uint32_t target_offset,
                                          uint32_t length,
                                          uint8_t outside,
                                          uint8_t pattern_base,
                                          uint8_t inside,
                                          uint32_t use_pattern,
                                          uint32_t *expected,
                                          uint32_t *observed) {
  for (uint32_t index = 0U; index < P7_STAGE62_MICROTEST_FIXTURE_BYTES;
       ++index) {
    uint8_t wanted = outside;
    if (index >= target_offset && index < target_offset + length) {
      wanted = use_pattern != 0U
                   ? (uint8_t)(pattern_base + index - target_offset)
                   : inside;
    }
    if (fixture[index] != wanted) {
      *expected = wanted;
      *observed = fixture[index];
      return index;
    }
  }
  *expected = UINT32_C(0x100);
  *observed = UINT32_C(0x100);
  return UINT32_MAX;
}

static void p7_capture_runtime(p7_stage62_microtest_record_t *record) {
  record->stack_pointer = p7_read_stack_pointer();
  record->sctlr = p7_read_sctlr();
  record->actlr = p7_read_actlr();
  record->ttbr0 = p7_read_ttbr0();
  record->ttbr1 = p7_read_ttbr1();
  record->ttbcr = p7_read_ttbcr();
  record->dacr = p7_read_dacr();
  p7_capture_translation_descriptor(
      record->source_target_address, record->sctlr, record->ttbr0,
      record->ttbr1, record->ttbcr,
      &record->source_l1_descriptor_address, &record->source_l1_descriptor,
      &record->source_l2_descriptor_address, &record->source_l2_descriptor);
  p7_capture_translation_descriptor(
      record->destination_target_address, record->sctlr, record->ttbr0,
      record->ttbr1, record->ttbcr,
      &record->destination_l1_descriptor_address,
      &record->destination_l1_descriptor,
      &record->destination_l2_descriptor_address,
      &record->destination_l2_descriptor);
  record->pl310_control =
      Xil_In32(P7_PL310_BASEADDR + P7_PL310_CONTROL_OFFSET);
  record->pl310_aux_control =
      Xil_In32(P7_PL310_BASEADDR + P7_PL310_AUX_CONTROL_OFFSET);
  record->pl310_cache_type =
      Xil_In32(P7_PL310_BASEADDR + P7_PL310_CACHE_TYPE_OFFSET);
  record->pl310_raw_interrupt_status =
      Xil_In32(P7_PL310_BASEADDR + P7_PL310_RAW_INTERRUPT_STATUS_OFFSET);
  record->mmu_enabled = record->sctlr & 1U;
  record->dcache_enabled = (record->sctlr >> 2) & 1U;
  record->icache_enabled = (record->sctlr >> 12) & 1U;
}

static void p7_hash_snapshots(p7_stage62_microtest_record_t *record) {
  record->source_before_crc32 = p7_microtest_crc32(
      record->source_before, P7_STAGE62_MICROTEST_FIXTURE_BYTES);
  record->source_after_crc32 = p7_microtest_crc32(
      record->source_after, P7_STAGE62_MICROTEST_FIXTURE_BYTES);
  record->destination_before_crc32 = p7_microtest_crc32(
      record->destination_before, P7_STAGE62_MICROTEST_FIXTURE_BYTES);
  record->destination_after_crc32 = p7_microtest_crc32(
      record->destination_after, P7_STAGE62_MICROTEST_FIXTURE_BYTES);
  p7_sha256_bytes(record->source_before,
                  P7_STAGE62_MICROTEST_FIXTURE_BYTES,
                  record->source_before_sha256);
  p7_sha256_bytes(record->source_after,
                  P7_STAGE62_MICROTEST_FIXTURE_BYTES,
                  record->source_after_sha256);
  p7_sha256_bytes(record->destination_before,
                  P7_STAGE62_MICROTEST_FIXTURE_BYTES,
                  record->destination_before_sha256);
  p7_sha256_bytes(record->destination_after,
                  P7_STAGE62_MICROTEST_FIXTURE_BYTES,
                  record->destination_after_sha256);
}

static uint32_t p7_publish_record(p7_stage62_microtest_record_t *record) {
  record->record_crc32 = 0U;
  record->magic = 0U;
  dsb();
  record->record_crc32 = p7_stage62_record_crc32(
      (const volatile uint8_t *)record, P7_STAGE62_MICROTEST_RECORD_BYTES);
  dsb();
  record->magic = P7_STAGE62_MICROTEST_RECORD_MAGIC;
  dsb();
  return Xil_In32(P7_FAILURE_SNAPSHOT_BASEADDR);
}

static int p7_control_is_zero(
    const volatile p7_stage62_microtest_control_t *control) {
  const volatile uint8_t *bytes = (const volatile uint8_t *)control;
  for (uint32_t index = 0U; index < sizeof(*control); ++index) {
    if (bytes[index] != 0U) return 0;
  }
  return 1;
}

int p7_stage62_microtest_try_run(void) {
  volatile p7_stage62_microtest_control_t *control =
      (volatile p7_stage62_microtest_control_t *)(uintptr_t)
          P7_STAGE62_MICROTEST_CONTROL_ADDRESS;
  p7_stage62_microtest_record_t *record =
      (p7_stage62_microtest_record_t *)(uintptr_t)
          p7_stage62_diagnostic_storage();
  volatile uint8_t *source_fixture = NULL;
  volatile uint8_t *destination_fixture = NULL;
  volatile uint8_t *source_target = NULL;
  volatile uint8_t *destination_target = NULL;
  uint32_t source_space = 0U;
  uint32_t destination_space = 0U;
  uint32_t pattern_base = p7_pattern_base(control->case_id);
  uint32_t source_offset = P7_STAGE62_MICROTEST_TARGET_OFFSET +
                           control->source_alignment;
  uint32_t destination_offset = P7_STAGE62_MICROTEST_TARGET_OFFSET +
                                control->destination_alignment;
  uint32_t control_crc = p7_microtest_crc32(
      (const volatile uint8_t *)control, 7U * sizeof(uint32_t));
  uint32_t valid_control;
  uint32_t expected = UINT32_C(0x100);
  uint32_t observed = UINT32_C(0x100);
  uint32_t bad = UINT32_MAX;
  uint32_t magic_readback;
  uint32_t wipe_verified = 0U;

  if (p7_control_is_zero(control)) return 0;
  control->state = P7_STAGE62_MICROTEST_RUNNING;
  control->result = P7_COPY_DIAGNOSTIC_RECORD_INVALID;
  control->record_address = P7_FAILURE_SNAPSHOT_BASEADDR;
  control->record_bytes = P7_STAGE62_MICROTEST_RECORD_BYTES;
  control->record_magic_readback = 0U;
  control->wipe_verified = 0U;
  dsb();

  p7_zero_volatile((volatile uint8_t *)record,
                   P7_STAGE62_MICROTEST_RECORD_BYTES);
  record->version = P7_STAGE62_MICROTEST_VERSION;
  record->record_length = P7_STAGE62_MICROTEST_RECORD_BYTES;
  record->sequence = 1U;
  record->terminal_status = P7_STAGE62_MICROTEST_FAILED;
  record->classification = P7_COPY_DIAGNOSTIC_RECORD_INVALID;
  record->error_code = P7_STAGE62_MICROTEST_ERROR_CONTROL;
  record->first_bad_domain = P7_STAGE62_MICROTEST_BAD_NONE;
  record->first_bad_index = UINT32_MAX;
  record->expected_byte = UINT32_C(0x100);
  record->observed_byte = UINT32_C(0x100);
  record->case_id = control->case_id;
  record->transfer_length = control->transfer_length;
  record->source_alignment = control->source_alignment;
  record->destination_alignment = control->destination_alignment;
  record->run_id_crc32 = control->run_id_crc32;
  record->control_crc32 = control->immutable_crc32;
  record->control_consumed = 1U;
  record->diagnostic_only = control->diagnostic_only;
  record->coverage_claimed = control->coverage_claimed;
  record->record_address = P7_FAILURE_SNAPSHOT_BASEADDR;
  record->record_bytes = P7_STAGE62_MICROTEST_RECORD_BYTES;
  record->output_wipe_required = 1U;
  record->output_wipe_byte = 0U;
  record->source_guard_byte = P7_STAGE62_MICROTEST_SOURCE_GUARD;
  record->destination_guard_byte = P7_STAGE62_MICROTEST_DESTINATION_GUARD;
  record->output_canary_byte = P7_STAGE62_MICROTEST_DESTINATION_CANARY;
  record->pattern_base = pattern_base;

  valid_control =
      control->magic == P7_STAGE62_MICROTEST_CONTROL_MAGIC &&
      control->version == P7_STAGE62_MICROTEST_VERSION &&
      control->case_id >= P7_STAGE62_MICROTEST_OCM_TO_OCM &&
      control->case_id <= P7_STAGE62_MICROTEST_DDR_TO_DDR &&
      control->transfer_length >= 29U && control->transfer_length <= 32U &&
      control->source_alignment <= 3U &&
      control->destination_alignment <= 3U &&
      control->immutable_crc32 == control_crc &&
      control->diagnostic_only == 1U && control->coverage_claimed == 0U;

  if (valid_control != 0U) {
    record->error_code = P7_STAGE62_MICROTEST_ERROR_NONE;
    source_fixture = (volatile uint8_t *)(uintptr_t)(
        control->case_id <= P7_STAGE62_MICROTEST_OCM_TO_DDR
            ? P7_STAGE62_MICROTEST_OCM_SOURCE_ADDRESS
            : P7_STAGE62_MICROTEST_DDR_SOURCE_ADDRESS);
    destination_fixture = (volatile uint8_t *)(uintptr_t)(
        (control->case_id == P7_STAGE62_MICROTEST_OCM_TO_OCM ||
         control->case_id == P7_STAGE62_MICROTEST_DDR_TO_OCM)
            ? P7_STAGE62_MICROTEST_OCM_DESTINATION_ADDRESS
            : P7_STAGE62_MICROTEST_DDR_DESTINATION_ADDRESS);
    source_space =
        control->case_id <= P7_STAGE62_MICROTEST_OCM_TO_DDR
            ? P7_STAGE62_MICROTEST_SPACE_OCM
            : P7_STAGE62_MICROTEST_SPACE_DDR;
    destination_space =
        (control->case_id == P7_STAGE62_MICROTEST_OCM_TO_OCM ||
         control->case_id == P7_STAGE62_MICROTEST_DDR_TO_OCM)
            ? P7_STAGE62_MICROTEST_SPACE_OCM
            : P7_STAGE62_MICROTEST_SPACE_DDR;
    source_target = source_fixture + source_offset;
    destination_target = destination_fixture + destination_offset;
    record->source_fixture_address = (uint32_t)(uintptr_t)source_fixture;
    record->destination_fixture_address =
        (uint32_t)(uintptr_t)destination_fixture;
    record->source_target_address = (uint32_t)(uintptr_t)source_target;
    record->destination_target_address =
        (uint32_t)(uintptr_t)destination_target;
    record->source_target_offset = source_offset;
    record->destination_target_offset = destination_offset;
    record->source_mod4 = record->source_target_address & 3U;
    record->destination_mod4 = record->destination_target_address & 3U;
    record->source_mod64 = record->source_target_address & 63U;
    record->destination_mod64 = record->destination_target_address & 63U;
    record->source_space = source_space;
    record->destination_space = destination_space;
    p7_capture_runtime(record);
    p7_snapshot(record->source_before, source_fixture);
    p7_snapshot(record->destination_before, destination_fixture);
    record->capture_flags =
        P7_COPY_DIAGNOSTIC_CAPTURE_SOURCE_BEFORE |
        P7_COPY_DIAGNOSTIC_CAPTURE_DESTINATION_BEFORE |
        P7_COPY_DIAGNOSTIC_CAPTURE_RUNTIME_REGISTERS |
        P7_COPY_DIAGNOSTIC_CAPTURE_PAGE_TABLES |
        P7_COPY_DIAGNOSTIC_CAPTURE_PL310 |
        P7_COPY_DIAGNOSTIC_CAPTURE_GENERIC_PAIR;

    bad = p7_first_fixture_mismatch(
        record->source_before, source_offset, control->transfer_length,
        P7_STAGE62_MICROTEST_SOURCE_GUARD, (uint8_t)pattern_base, 0U, 1U,
        &expected, &observed);
    record->source_guards_before_ok = bad == UINT32_MAX;
    record->source_pattern_before_ok = bad == UINT32_MAX;
    if (bad != UINT32_MAX) {
      record->first_bad_domain = P7_STAGE62_MICROTEST_BAD_SOURCE_BEFORE;
      record->first_bad_index = bad;
      record->expected_byte = expected;
      record->observed_byte = observed;
      record->classification = P7_COPY_DIAGNOSTIC_RECORD_INVALID;
      record->error_code = P7_STAGE62_MICROTEST_ERROR_PRECHECK;
    } else {
      bad = p7_first_fixture_mismatch(
          record->destination_before, destination_offset,
          control->transfer_length,
          P7_STAGE62_MICROTEST_DESTINATION_GUARD, 0U,
          P7_STAGE62_MICROTEST_DESTINATION_CANARY, 0U, &expected, &observed);
      record->destination_guards_before_ok = bad == UINT32_MAX;
      record->destination_canary_before_ok = bad == UINT32_MAX;
      if (bad != UINT32_MAX) {
        record->first_bad_domain =
            P7_STAGE62_MICROTEST_BAD_DESTINATION_BEFORE;
        record->first_bad_index = bad;
        record->expected_byte = expected;
        record->observed_byte = observed;
        record->classification = P7_COPY_DIAGNOSTIC_CANARY_PRECHECK_FAILED;
        record->error_code = P7_STAGE62_MICROTEST_ERROR_PRECHECK;
      } else {
        record->capture_flags |= P7_COPY_DIAGNOSTIC_CAPTURE_CANARY_VERIFIED;
        p7_stage62_microtest_copy_bytes(destination_target, source_target,
                                        control->transfer_length);
        record->copy_executed = 1U;
        record->capture_flags |= P7_COPY_DIAGNOSTIC_CAPTURE_COPY_EXECUTED;
      }
    }

    p7_snapshot(record->source_after, source_fixture);
    p7_snapshot(record->destination_after, destination_fixture);
    record->capture_flags |= P7_COPY_DIAGNOSTIC_CAPTURE_SOURCE_AFTER |
                             P7_COPY_DIAGNOSTIC_CAPTURE_DESTINATION_AFTER;
    if (record->copy_executed != 0U) {
      record->classification = p7_stage62_classify_copy_observation(
          record->source_before + source_offset,
          record->source_after + source_offset,
          record->destination_before + destination_offset,
          record->destination_after + destination_offset,
          control->transfer_length);
      if (record->classification != P7_COPY_DIAGNOSTIC_COPY_OK) {
        record->error_code = P7_STAGE62_MICROTEST_ERROR_COPY_OBSERVATION;
        for (uint32_t index = 0U; index < control->transfer_length; ++index) {
          if (record->source_before[source_offset + index] !=
              record->destination_after[destination_offset + index]) {
            record->first_bad_domain =
                P7_STAGE62_MICROTEST_BAD_DESTINATION_AFTER;
            record->first_bad_index = index;
            record->expected_byte =
                record->source_before[source_offset + index];
            record->observed_byte =
                record->destination_after[destination_offset + index];
            record->source_before_byte =
                record->source_before[source_offset + index];
            record->source_after_byte =
                record->source_after[source_offset + index];
            record->destination_before_byte =
                record->destination_before[destination_offset + index];
            record->destination_after_byte =
                record->destination_after[destination_offset + index];
            break;
          }
        }
      }
    }
    bad = p7_first_fixture_mismatch(
        record->source_after, source_offset, control->transfer_length,
        P7_STAGE62_MICROTEST_SOURCE_GUARD, (uint8_t)pattern_base, 0U, 1U,
        &expected, &observed);
    record->source_guards_after_ok = bad == UINT32_MAX;
    record->source_pattern_after_ok = bad == UINT32_MAX;
    if (bad != UINT32_MAX) {
      record->classification = P7_COPY_DIAGNOSTIC_SOURCE_CHANGED;
      record->error_code = P7_STAGE62_MICROTEST_ERROR_GUARD;
      record->first_bad_domain = P7_STAGE62_MICROTEST_BAD_SOURCE_GUARD;
      record->first_bad_index = bad;
      record->expected_byte = expected;
      record->observed_byte = observed;
    }
    bad = p7_first_fixture_mismatch(
        record->destination_after, destination_offset,
        control->transfer_length, P7_STAGE62_MICROTEST_DESTINATION_GUARD,
        (uint8_t)pattern_base, 0U, 1U, &expected, &observed);
    record->destination_guards_after_ok = bad == UINT32_MAX;
    if (bad != UINT32_MAX &&
        (bad < destination_offset ||
         bad >= destination_offset + control->transfer_length)) {
      record->classification = P7_COPY_DIAGNOSTIC_DEST_WRONG_VALUE;
      record->error_code = P7_STAGE62_MICROTEST_ERROR_GUARD;
      record->first_bad_domain =
          P7_STAGE62_MICROTEST_BAD_DESTINATION_GUARD;
      record->first_bad_index = bad;
      record->expected_byte = expected;
      record->observed_byte = observed;
    }
    record->terminal_status =
        record->classification == P7_COPY_DIAGNOSTIC_COPY_OK
            ? P7_STAGE62_MICROTEST_COMPLETE
            : P7_STAGE62_MICROTEST_FAILED;
  } else {
    p7_capture_runtime(record);
  }

  p7_hash_snapshots(record);
  magic_readback = p7_publish_record(record);
  if (magic_readback != P7_STAGE62_MICROTEST_RECORD_MAGIC) {
    control->result = P7_COPY_DIAGNOSTIC_RECORD_INVALID;
    control->record_magic_readback = magic_readback;
    dsb();
    control->state = P7_STAGE62_MICROTEST_FAILED;
    dsb();
    return -1;
  }

  /* Publication must precede erasure so the first observation survives, but
   * every valid diagnostic request must erase its destination target even
   * when a fixture precheck prevented the copy itself. */
  if (valid_control != 0U && destination_target != NULL) {
    p7_zero_volatile(destination_target, control->transfer_length);
    wipe_verified = 1U;
    for (uint32_t index = 0U; index < control->transfer_length; ++index) {
      if (destination_target[index] != 0U) {
        wipe_verified = 0U;
        break;
      }
    }
  }
  control->result = record->classification;
  control->record_magic_readback = magic_readback;
  control->wipe_verified = wipe_verified;
  dsb();
  if (record->classification == P7_COPY_DIAGNOSTIC_COPY_OK &&
      wipe_verified != 0U) {
    control->state = P7_STAGE62_MICROTEST_COMPLETE;
    dsb();
    return 1;
  }
  control->state = P7_STAGE62_MICROTEST_FAILED;
  dsb();
  return -1;
}
