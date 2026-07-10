#ifndef RF_APP_PROTOCOL_H
#define RF_APP_PROTOCOL_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* config/p7_app_protocol.yaml: RF_COMM application protocol v1. */
#define RF_APP_MAGIC_ASCII "RFAP"
#define RF_APP_MAGIC_U32_LE UINT32_C(0x50414652)
#define RF_APP_VERSION UINT8_C(1)
#define RF_APP_HEADER_BYTES UINT16_C(32)
#define RF_APP_P6_MAX_PAYLOAD_BYTES UINT16_C(247)
#define RF_APP_MAX_CHUNK_BYTES UINT16_C(215)
#define RF_APP_MAX_OBJECT_BYTES UINT32_C(8388608)
#define RF_APP_DESCRIPTOR_QUEUE_DEPTH UINT8_C(8)
#define RF_APP_OUT_OF_ORDER_WINDOW UINT8_C(0)

#define RF_APP_FLAG_FIRST UINT8_C(0x01)
#define RF_APP_FLAG_LAST UINT8_C(0x02)
#define RF_APP_FLAG_RETRANSMIT UINT8_C(0x04)
#define RF_APP_FLAG_CONTROL UINT8_C(0x08)
#define RF_APP_KNOWN_FLAGS                                                     \
  ((uint8_t)(RF_APP_FLAG_FIRST | RF_APP_FLAG_LAST |                           \
             RF_APP_FLAG_RETRANSMIT | RF_APP_FLAG_CONTROL))

#define RF_APP_LANE_POLICY_LANE0_ONLY UINT8_C(1)
#define RF_APP_LANE_POLICY_LANE1_ONLY UINT8_C(2)
#define RF_APP_LANE_POLICY_STRIPE_ROUND_ROBIN UINT8_C(3)
#define RF_APP_LANE_POLICY_REPLICATE_0X3 UINT8_C(4)
#define RF_APP_ALLOWED_LANE_MASK_BITS UINT8_C(0x03)

typedef enum rf_app_status {
  RF_APP_OK = 0,
  RF_APP_ERR_NULL,
  RF_APP_ERR_FIELD_RANGE,
  RF_APP_ERR_OBJECT_TOO_LARGE,
  RF_APP_ERR_FRAGMENT_COUNT_ZERO,
  RF_APP_ERR_FRAGMENT_INDEX_RANGE,
  RF_APP_ERR_CHUNK_TOO_LARGE,
  RF_APP_ERR_RESERVED_NONZERO,
  RF_APP_ERR_FLAGS_UNKNOWN,
  RF_APP_ERR_FIRST_FLAG,
  RF_APP_ERR_LAST_FLAG,
  RF_APP_ERR_FRAGMENT_COUNT,
  RF_APP_ERR_CHUNK_LENGTH,
  RF_APP_ERR_HEADER_TRUNCATED,
  RF_APP_ERR_MAGIC,
  RF_APP_ERR_VERSION,
  RF_APP_ERR_HEADER_LENGTH,
  RF_APP_ERR_CHUNK_SIZE,
  RF_APP_ERR_P6_PAYLOAD_SIZE,
  RF_APP_ERR_FRAGMENT_SIZE,
  RF_APP_ERR_OUTPUT_TOO_SMALL
} rf_app_status_t;

typedef struct rf_app_header {
  uint32_t session_epoch;
  uint32_t object_id;
  uint32_t total_length;
  uint16_t fragment_index;
  uint16_t fragment_count;
  uint16_t chunk_length;
  uint32_t object_crc32;
  uint8_t flags;
  uint16_t reserved;
} rf_app_header_t;

typedef struct rf_app_fragment_view {
  rf_app_header_t header;
  const uint8_t *chunk;
  size_t chunk_size;
} rf_app_fragment_view_t;

const char *rf_app_error_code(rf_app_status_t status);

uint32_t rf_app_crc32(const uint8_t *data, size_t size);

rf_app_status_t rf_app_fragment_count(uint32_t total_length,
                                      uint16_t *count_out);

rf_app_status_t rf_app_validate_header(const rf_app_header_t *header);

rf_app_status_t rf_app_encode_header(
    const rf_app_header_t *header,
    uint8_t output[RF_APP_HEADER_BYTES]);

rf_app_status_t rf_app_decode_header(const uint8_t *input, size_t input_size,
                                     rf_app_header_t *header_out);

rf_app_status_t rf_app_encode_fragment(
    const rf_app_header_t *header, const uint8_t *chunk, size_t chunk_size,
    uint8_t *output, size_t output_capacity, size_t *output_size);

rf_app_status_t rf_app_decode_fragment(const uint8_t *input,
                                       size_t input_size,
                                       rf_app_fragment_view_t *fragment_out);

#ifdef __cplusplus
}
#endif

#endif
