#include "ir_driver.h"
#include "ir_regs.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum {
  TEST_BUFFER_BYTES = 384,
  TEST_CASES = 1000,
  TEST_MAX_PAYLOAD_BYTES = 247,
  TEST_PAYLOAD_WORDS = 64
};

typedef struct mock_mmio {
  uint32_t payload_index;
  uint32_t payload_words[TEST_PAYLOAD_WORDS];
} mock_mmio_t;

static uint32_t mock_read32(void *opaque, uint32_t offset) {
  mock_mmio_t *mock = (mock_mmio_t *)opaque;
  if (offset == IR_REG_P6_PAYLOAD_WORD_INDEX) return mock->payload_index;
  if (offset == IR_REG_P6_PAYLOAD_WORD_DATA) {
    if (mock->payload_index >= TEST_PAYLOAD_WORDS) return UINT32_MAX;
    return mock->payload_words[mock->payload_index];
  }
  return 0U;
}

static void mock_write32(void *opaque, uint32_t offset, uint32_t value) {
  mock_mmio_t *mock = (mock_mmio_t *)opaque;
  if (offset == IR_REG_P6_PAYLOAD_WORD_INDEX) {
    mock->payload_index = value;
  } else if (offset == IR_REG_P6_PAYLOAD_WORD_DATA &&
             mock->payload_index < TEST_PAYLOAD_WORDS) {
    mock->payload_words[mock->payload_index] = value;
  }
}

int main(void) {
  _Alignas(64) uint8_t source[TEST_BUFFER_BYTES];
  _Alignas(64) uint8_t destination[TEST_BUFFER_BYTES];
  uint8_t lengths_seen[TEST_MAX_PAYLOAD_BYTES + 1U] = {0};
  uint8_t source_mod64_seen[64] = {0};
  uint8_t destination_mod64_seen[64] = {0};
  uint8_t mod4_pairs_seen[4][4] = {{0}};
  mock_mmio_t mock;
  ir_mmio_t io = {&mock, mock_read32, mock_write32};

  if (((uintptr_t)source & 63U) != 0U ||
      ((uintptr_t)destination & 63U) != 0U) {
    return 5;
  }
  memset(&mock, 0, sizeof(mock));
  if (ir_driver_p6_read_tx_payload(&io, destination, sizeof(destination), 0U) !=
      -2) {
    return 1;
  }
  if (ir_driver_p6_read_tx_payload(&io, destination, 246U, 247U) != -2) {
    return 2;
  }
  if (ir_driver_p6_read_tx_payload(&io, destination, sizeof(destination),
                                   248U) != -2) {
    return 3;
  }
  if (ir_driver_p6_read_tx_payload(&io, NULL, sizeof(destination), 1U) != -1) {
    return 4;
  }
  for (uint32_t test_case = 0U; test_case < TEST_CASES; ++test_case) {
    uint32_t length = (test_case % TEST_MAX_PAYLOAD_BYTES) + 1U;
    uint32_t source_offset = (test_case * 17U) & 63U;
    uint32_t destination_offset =
        (test_case * 29U + test_case / 4U) & 63U;
    lengths_seen[length] = 1U;
    source_mod64_seen[source_offset] = 1U;
    destination_mod64_seen[destination_offset] = 1U;
    mod4_pairs_seen[source_offset & 3U][destination_offset & 3U] = 1U;
    memset(&mock, 0, sizeof(mock));
    memset(source, 0x3c, sizeof(source));
    memset(destination, 0xa5, sizeof(destination));
    for (uint32_t index = 0U; index < length; ++index) {
      source[source_offset + index] =
          (uint8_t)(((test_case + index * 37U) % 255U) + 1U);
    }
    if (ir_driver_p6_write_payload(&io, source + source_offset, length) != 0) {
      return 10;
    }
    if (ir_driver_p6_read_tx_payload(&io, destination + destination_offset,
                                     TEST_BUFFER_BYTES - destination_offset,
                                     length) != 0) {
      return 11;
    }
    if (memcmp(source + source_offset, destination + destination_offset,
               length) != 0) {
      return 12;
    }
    for (uint32_t index = 0U; index < destination_offset; ++index) {
      if (destination[index] != 0xa5U) return 13;
    }
    for (uint32_t index = destination_offset + length;
         index < TEST_BUFFER_BYTES; ++index) {
      if (destination[index] != 0xa5U) return 14;
    }
  }
  for (uint32_t length = 1U; length <= TEST_MAX_PAYLOAD_BYTES; ++length) {
    if (lengths_seen[length] == 0U) return 20;
  }
  for (uint32_t offset = 0U; offset < 64U; ++offset) {
    if (source_mod64_seen[offset] == 0U) return 21;
    if (destination_mod64_seen[offset] == 0U) return 22;
  }
  for (uint32_t source_mod4 = 0U; source_mod4 < 4U; ++source_mod4) {
    for (uint32_t destination_mod4 = 0U; destination_mod4 < 4U;
         ++destination_mod4) {
      if (mod4_pairs_seen[source_mod4][destination_mod4] == 0U) return 23;
    }
  }
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_CASES=1000");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_LENGTH_RANGE=1..247");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_SOURCE_MOD64_COUNT=64");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_DESTINATION_MOD64_COUNT=64");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_SOURCE_DESTINATION_MOD4_PAIRS=16");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_ARGUMENT_LIMITS=PASS");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_BUFFER_BASE_ALIGNMENT=64");
  puts("P7_PAYLOAD_ALIGNMENT_MATRIX_CANARY=0xA5");
  return 0;
}
