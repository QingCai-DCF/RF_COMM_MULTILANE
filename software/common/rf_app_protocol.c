#include "rf_app_protocol.h"

#include <string.h>

static uint16_t read_u16_le(const uint8_t *input) {
  return (uint16_t)((uint16_t)input[0] | ((uint16_t)input[1] << 8));
}

static uint32_t read_u32_le(const uint8_t *input) {
  return (uint32_t)input[0] | ((uint32_t)input[1] << 8) |
         ((uint32_t)input[2] << 16) | ((uint32_t)input[3] << 24);
}

static void write_u16_le(uint8_t *output, uint16_t value) {
  output[0] = (uint8_t)(value & UINT16_C(0x00ff));
  output[1] = (uint8_t)(value >> 8);
}

static void write_u32_le(uint8_t *output, uint32_t value) {
  output[0] = (uint8_t)(value & UINT32_C(0x000000ff));
  output[1] = (uint8_t)((value >> 8) & UINT32_C(0x000000ff));
  output[2] = (uint8_t)((value >> 16) & UINT32_C(0x000000ff));
  output[3] = (uint8_t)(value >> 24);
}

const char *rf_app_error_code(rf_app_status_t status) {
  switch (status) {
  case RF_APP_OK:
    return "OK";
  case RF_APP_ERR_NULL:
    return "NULL";
  case RF_APP_ERR_FIELD_RANGE:
    return "FIELD_RANGE";
  case RF_APP_ERR_OBJECT_TOO_LARGE:
    return "OBJECT_TOO_LARGE";
  case RF_APP_ERR_FRAGMENT_COUNT_ZERO:
    return "FRAGMENT_COUNT_ZERO";
  case RF_APP_ERR_FRAGMENT_INDEX_RANGE:
    return "FRAGMENT_INDEX_RANGE";
  case RF_APP_ERR_CHUNK_TOO_LARGE:
    return "CHUNK_TOO_LARGE";
  case RF_APP_ERR_RESERVED_NONZERO:
    return "RESERVED_NONZERO";
  case RF_APP_ERR_FLAGS_UNKNOWN:
    return "FLAGS_UNKNOWN";
  case RF_APP_ERR_FIRST_FLAG:
    return "FIRST_FLAG";
  case RF_APP_ERR_LAST_FLAG:
    return "LAST_FLAG";
  case RF_APP_ERR_FRAGMENT_COUNT:
    return "FRAGMENT_COUNT";
  case RF_APP_ERR_CHUNK_LENGTH:
    return "CHUNK_LENGTH";
  case RF_APP_ERR_HEADER_TRUNCATED:
    return "HEADER_TRUNCATED";
  case RF_APP_ERR_MAGIC:
    return "MAGIC";
  case RF_APP_ERR_VERSION:
    return "VERSION";
  case RF_APP_ERR_HEADER_LENGTH:
    return "HEADER_LENGTH";
  case RF_APP_ERR_CHUNK_SIZE:
    return "CHUNK_SIZE";
  case RF_APP_ERR_P6_PAYLOAD_SIZE:
    return "P6_PAYLOAD_SIZE";
  case RF_APP_ERR_FRAGMENT_SIZE:
    return "FRAGMENT_SIZE";
  case RF_APP_ERR_OUTPUT_TOO_SMALL:
    return "OUTPUT_TOO_SMALL";
  default:
    return "UNKNOWN";
  }
}

uint32_t rf_app_crc32(const uint8_t *data, size_t size) {
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
  size_t index;

  if (data == NULL && size != 0U) {
    return 0U;
  }
  for (index = 0U; index < size; ++index) {
    crc ^= data[index];
    crc = table[crc & UINT32_C(0x0f)] ^ (crc >> 4);
    crc = table[crc & UINT32_C(0x0f)] ^ (crc >> 4);
  }
  return crc ^ UINT32_C(0xffffffff);
}

rf_app_status_t rf_app_fragment_count(uint32_t total_length,
                                      uint16_t *count_out) {
  uint32_t count;

  if (count_out == NULL) {
    return RF_APP_ERR_NULL;
  }
  if (total_length > RF_APP_MAX_OBJECT_BYTES) {
    return RF_APP_ERR_OBJECT_TOO_LARGE;
  }
  count = total_length == 0U
              ? 1U
              : (total_length + (uint32_t)RF_APP_MAX_CHUNK_BYTES - 1U) /
                    (uint32_t)RF_APP_MAX_CHUNK_BYTES;
  if (count == 0U || count > UINT16_MAX) {
    return RF_APP_ERR_FIELD_RANGE;
  }
  *count_out = (uint16_t)count;
  return RF_APP_OK;
}

rf_app_status_t rf_app_validate_header(const rf_app_header_t *header) {
  uint16_t expected_count = 0U;
  uint16_t expected_chunk = 0U;
  uint64_t offset;
  uint32_t remaining;
  int expected_first;
  int expected_last;
  rf_app_status_t status;

  if (header == NULL) {
    return RF_APP_ERR_NULL;
  }
  if (header->total_length > RF_APP_MAX_OBJECT_BYTES) {
    return RF_APP_ERR_OBJECT_TOO_LARGE;
  }
  if (header->fragment_count == 0U) {
    return RF_APP_ERR_FRAGMENT_COUNT_ZERO;
  }
  if (header->fragment_index >= header->fragment_count) {
    return RF_APP_ERR_FRAGMENT_INDEX_RANGE;
  }
  if (header->chunk_length > RF_APP_MAX_CHUNK_BYTES) {
    return RF_APP_ERR_CHUNK_TOO_LARGE;
  }
  if (header->reserved != 0U) {
    return RF_APP_ERR_RESERVED_NONZERO;
  }
  if ((header->flags & (uint8_t)~RF_APP_KNOWN_FLAGS) != 0U) {
    return RF_APP_ERR_FLAGS_UNKNOWN;
  }

  expected_first = header->fragment_index == 0U;
  expected_last = header->fragment_index ==
                  (uint16_t)(header->fragment_count - 1U);
  if ((((header->flags & RF_APP_FLAG_FIRST) != 0U) ? 1 : 0) !=
      expected_first) {
    return RF_APP_ERR_FIRST_FLAG;
  }
  if ((((header->flags & RF_APP_FLAG_LAST) != 0U) ? 1 : 0) !=
      expected_last) {
    return RF_APP_ERR_LAST_FLAG;
  }

  status = rf_app_fragment_count(header->total_length, &expected_count);
  if (status != RF_APP_OK) {
    return status;
  }
  if (header->fragment_count != expected_count) {
    return RF_APP_ERR_FRAGMENT_COUNT;
  }

  if (header->total_length != 0U) {
    offset = (uint64_t)header->fragment_index *
             (uint64_t)RF_APP_MAX_CHUNK_BYTES;
    remaining = (uint32_t)((uint64_t)header->total_length - offset);
    expected_chunk = (uint16_t)(remaining > RF_APP_MAX_CHUNK_BYTES
                                    ? RF_APP_MAX_CHUNK_BYTES
                                    : remaining);
  }
  if (header->chunk_length != expected_chunk) {
    return RF_APP_ERR_CHUNK_LENGTH;
  }
  return RF_APP_OK;
}

rf_app_status_t rf_app_encode_header(
    const rf_app_header_t *header,
    uint8_t output[RF_APP_HEADER_BYTES]) {
  rf_app_status_t status;

  if (header == NULL || output == NULL) {
    return RF_APP_ERR_NULL;
  }
  status = rf_app_validate_header(header);
  if (status != RF_APP_OK) {
    return status;
  }
  output[0] = (uint8_t)'R';
  output[1] = (uint8_t)'F';
  output[2] = (uint8_t)'A';
  output[3] = (uint8_t)'P';
  output[4] = RF_APP_VERSION;
  output[5] = header->flags;
  write_u16_le(output + 6, RF_APP_HEADER_BYTES);
  write_u32_le(output + 8, header->session_epoch);
  write_u32_le(output + 12, header->object_id);
  write_u32_le(output + 16, header->total_length);
  write_u16_le(output + 20, header->fragment_index);
  write_u16_le(output + 22, header->fragment_count);
  write_u16_le(output + 24, header->chunk_length);
  write_u16_le(output + 26, header->reserved);
  write_u32_le(output + 28, header->object_crc32);
  return RF_APP_OK;
}

rf_app_status_t rf_app_decode_header(const uint8_t *input, size_t input_size,
                                     rf_app_header_t *header_out) {
  rf_app_header_t header;

  if (input == NULL || header_out == NULL) {
    return RF_APP_ERR_NULL;
  }
  if (input_size < RF_APP_HEADER_BYTES) {
    return RF_APP_ERR_HEADER_TRUNCATED;
  }
  if (input[0] != (uint8_t)'R' || input[1] != (uint8_t)'F' ||
      input[2] != (uint8_t)'A' || input[3] != (uint8_t)'P') {
    return RF_APP_ERR_MAGIC;
  }
  if (input[4] != RF_APP_VERSION) {
    return RF_APP_ERR_VERSION;
  }
  if (read_u16_le(input + 6) != RF_APP_HEADER_BYTES) {
    return RF_APP_ERR_HEADER_LENGTH;
  }

  header.flags = input[5];
  header.session_epoch = read_u32_le(input + 8);
  header.object_id = read_u32_le(input + 12);
  header.total_length = read_u32_le(input + 16);
  header.fragment_index = read_u16_le(input + 20);
  header.fragment_count = read_u16_le(input + 22);
  header.chunk_length = read_u16_le(input + 24);
  header.reserved = read_u16_le(input + 26);
  header.object_crc32 = read_u32_le(input + 28);

  {
    rf_app_status_t status = rf_app_validate_header(&header);
    if (status != RF_APP_OK) {
      return status;
    }
  }
  *header_out = header;
  return RF_APP_OK;
}

rf_app_status_t rf_app_encode_fragment(
    const rf_app_header_t *header, const uint8_t *chunk, size_t chunk_size,
    uint8_t *output, size_t output_capacity, size_t *output_size) {
  size_t encoded_size;
  rf_app_status_t status;

  if (header == NULL || output == NULL || output_size == NULL ||
      (chunk == NULL && chunk_size != 0U)) {
    return RF_APP_ERR_NULL;
  }
  if (chunk_size != (size_t)header->chunk_length) {
    return RF_APP_ERR_CHUNK_SIZE;
  }
  status = rf_app_validate_header(header);
  if (status != RF_APP_OK) {
    return status;
  }
  encoded_size = (size_t)RF_APP_HEADER_BYTES + chunk_size;
  if (encoded_size == 0U || encoded_size > RF_APP_P6_MAX_PAYLOAD_BYTES) {
    return RF_APP_ERR_P6_PAYLOAD_SIZE;
  }
  if (output_capacity < encoded_size) {
    return RF_APP_ERR_OUTPUT_TOO_SMALL;
  }
  status = rf_app_encode_header(header, output);
  if (status != RF_APP_OK) {
    return status;
  }
  if (chunk_size != 0U) {
    memcpy(output + RF_APP_HEADER_BYTES, chunk, chunk_size);
  }
  *output_size = encoded_size;
  return RF_APP_OK;
}

rf_app_status_t rf_app_decode_fragment(const uint8_t *input,
                                       size_t input_size,
                                       rf_app_fragment_view_t *fragment_out) {
  rf_app_header_t header;
  rf_app_status_t status;

  if (input == NULL || fragment_out == NULL) {
    return RF_APP_ERR_NULL;
  }
  status = rf_app_decode_header(input, input_size, &header);
  if (status != RF_APP_OK) {
    return status;
  }
  if (input_size !=
      (size_t)RF_APP_HEADER_BYTES + (size_t)header.chunk_length) {
    return RF_APP_ERR_FRAGMENT_SIZE;
  }
  fragment_out->header = header;
  fragment_out->chunk = input + RF_APP_HEADER_BYTES;
  fragment_out->chunk_size = header.chunk_length;
  return RF_APP_OK;
}
