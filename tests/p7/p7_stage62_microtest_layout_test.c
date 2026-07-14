#include "p7_stage62_microtest.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

_Static_assert(sizeof(p7_stage62_microtest_control_t) == 64U,
               "microtest control layout drift");
_Static_assert(sizeof(p7_stage62_microtest_record_t) == 1536U,
               "microtest record layout drift");
_Static_assert(offsetof(p7_stage62_microtest_record_t, source_before) == 512U,
               "microtest source-before offset drift");
_Static_assert(offsetof(p7_stage62_microtest_record_t, source_after) == 768U,
               "microtest source-after offset drift");
_Static_assert(offsetof(p7_stage62_microtest_record_t, destination_before) ==
                   1024U,
               "microtest destination-before offset drift");
_Static_assert(offsetof(p7_stage62_microtest_record_t, destination_after) ==
                   1280U,
               "microtest destination-after offset drift");

int main(void) {
  if ((P7_STAGE62_MICROTEST_CONTROL_ADDRESS & 63U) != 0U ||
      (P7_STAGE62_MICROTEST_OCM_SOURCE_ADDRESS & 63U) != 0U ||
      (P7_STAGE62_MICROTEST_OCM_DESTINATION_ADDRESS & 63U) != 0U ||
      P7_STAGE62_MICROTEST_CONTROL_ADDRESS < UINT32_C(0x00022300) ||
      P7_STAGE62_MICROTEST_OCM_SOURCE_ADDRESS <
          P7_STAGE62_MICROTEST_CONTROL_ADDRESS +
              sizeof(p7_stage62_microtest_control_t) ||
      P7_STAGE62_MICROTEST_OCM_DESTINATION_ADDRESS <
          P7_STAGE62_MICROTEST_OCM_SOURCE_ADDRESS +
              P7_STAGE62_MICROTEST_FIXTURE_BYTES ||
      P7_STAGE62_MICROTEST_OCM_DESTINATION_ADDRESS +
              P7_STAGE62_MICROTEST_FIXTURE_BYTES >
          UINT32_C(0x00030000)) {
    return 1;
  }
  if (P7_STAGE62_MICROTEST_TARGET_OFFSET + 3U + 32U >
      P7_STAGE62_MICROTEST_FIXTURE_BYTES) {
    return 2;
  }
  printf("P7_STAGE62_MICROTEST_LAYOUT=PASS\n");
  printf("P7_STAGE62_MICROTEST_CONTROL_BYTES=%lu\n",
         (unsigned long)sizeof(p7_stage62_microtest_control_t));
  printf("P7_STAGE62_MICROTEST_RECORD_BYTES=%lu\n",
         (unsigned long)sizeof(p7_stage62_microtest_record_t));
  printf("P7_STAGE62_MICROTEST_CASES=A,B,C,D\n");
  printf("P7_STAGE62_MICROTEST_LENGTH_RANGE=29..32\n");
  printf("P7_STAGE62_MICROTEST_ALIGNMENT_RANGE=0..3\n");
  printf("P7_STAGE62_MICROTEST_CANARY=0xA5\n");
  return 0;
}
