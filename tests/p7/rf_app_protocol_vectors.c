#include "rf_app_protocol.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_CAPACITY 65536U
#define NAME_CAPACITY 128U
#define HEX_HEADER_CAPACITY (RF_APP_HEADER_BYTES * 2U + 1U)
#define HEX_CHUNK_CAPACITY (RF_APP_MAX_CHUNK_BYTES * 2U + 1U)
#define HEX_FRAGMENT_CAPACITY (RF_APP_P6_MAX_PAYLOAD_BYTES * 2U + 1U)
#define OBJECT_CHECK_BYTES 4096U
#define HEX_OBJECT_CAPACITY (OBJECT_CHECK_BYTES * 2U + 1U)

#if RF_APP_HEADER_BYTES != 32
#error "RFAP header must remain 32 bytes"
#endif
#if RF_APP_MAX_CHUNK_BYTES != 215
#error "RFAP chunk geometry must remain 215 bytes"
#endif
#if RF_APP_P6_MAX_PAYLOAD_BYTES != 247
#error "P6 payload boundary must remain 247 bytes"
#endif

static int json_get_string(const char *line, const char *key, char *output,
                           size_t output_capacity) {
  char pattern[96];
  const char *start;
  const char *end;
  size_t length;

  if (snprintf(pattern, sizeof(pattern), "\"%s\":\"", key) < 0) {
    return 0;
  }
  start = strstr(line, pattern);
  if (start == NULL) {
    return 0;
  }
  start += strlen(pattern);
  end = strchr(start, '"');
  if (end == NULL) {
    return 0;
  }
  length = (size_t)(end - start);
  if (length + 1U > output_capacity) {
    return 0;
  }
  memcpy(output, start, length);
  output[length] = '\0';
  return 1;
}

static int json_get_u64(const char *line, const char *key, uint64_t *value) {
  char pattern[96];
  const char *start;
  char *end = NULL;
  unsigned long long parsed;

  if (snprintf(pattern, sizeof(pattern), "\"%s\":", key) < 0) {
    return 0;
  }
  start = strstr(line, pattern);
  if (start == NULL) {
    return 0;
  }
  start += strlen(pattern);
  parsed = strtoull(start, &end, 10);
  if (end == start) {
    return 0;
  }
  *value = (uint64_t)parsed;
  return 1;
}

static int hex_nibble(char value) {
  if (value >= '0' && value <= '9') {
    return value - '0';
  }
  if (value >= 'a' && value <= 'f') {
    return value - 'a' + 10;
  }
  if (value >= 'A' && value <= 'F') {
    return value - 'A' + 10;
  }
  return -1;
}

static int hex_decode(const char *text, uint8_t *output,
                      size_t output_capacity, size_t *output_size) {
  size_t text_length = strlen(text);
  size_t byte_count;
  size_t index;

  if ((text_length & 1U) != 0U) {
    return 0;
  }
  byte_count = text_length / 2U;
  if (byte_count > output_capacity) {
    return 0;
  }
  for (index = 0U; index < byte_count; ++index) {
    int high = hex_nibble(text[index * 2U]);
    int low = hex_nibble(text[index * 2U + 1U]);
    if (high < 0 || low < 0) {
      return 0;
    }
    output[index] = (uint8_t)((high << 4) | low);
  }
  *output_size = byte_count;
  return 1;
}

static int load_header(const char *line, rf_app_header_t *header) {
  uint64_t session_epoch;
  uint64_t object_id;
  uint64_t total_length;
  uint64_t fragment_index;
  uint64_t fragment_count;
  uint64_t chunk_length;
  uint64_t object_crc32;
  uint64_t flags;
  uint64_t reserved;

  if (!json_get_u64(line, "session_epoch", &session_epoch) ||
      !json_get_u64(line, "object_id", &object_id) ||
      !json_get_u64(line, "total_length", &total_length) ||
      !json_get_u64(line, "fragment_index", &fragment_index) ||
      !json_get_u64(line, "fragment_count", &fragment_count) ||
      !json_get_u64(line, "chunk_length", &chunk_length) ||
      !json_get_u64(line, "object_crc32", &object_crc32) ||
      !json_get_u64(line, "flags", &flags) ||
      !json_get_u64(line, "reserved", &reserved)) {
    return 0;
  }
  if (session_epoch > UINT32_MAX || object_id > UINT32_MAX ||
      total_length > UINT32_MAX || fragment_index > UINT16_MAX ||
      fragment_count > UINT16_MAX || chunk_length > UINT16_MAX ||
      object_crc32 > UINT32_MAX || flags > UINT8_MAX ||
      reserved > UINT16_MAX) {
    return 0;
  }
  header->session_epoch = (uint32_t)session_epoch;
  header->object_id = (uint32_t)object_id;
  header->total_length = (uint32_t)total_length;
  header->fragment_index = (uint16_t)fragment_index;
  header->fragment_count = (uint16_t)fragment_count;
  header->chunk_length = (uint16_t)chunk_length;
  header->object_crc32 = (uint32_t)object_crc32;
  header->flags = (uint8_t)flags;
  header->reserved = (uint16_t)reserved;
  return 1;
}

static int headers_equal(const rf_app_header_t *left,
                         const rf_app_header_t *right) {
  return left->session_epoch == right->session_epoch &&
         left->object_id == right->object_id &&
         left->total_length == right->total_length &&
         left->fragment_index == right->fragment_index &&
         left->fragment_count == right->fragment_count &&
         left->chunk_length == right->chunk_length &&
         left->object_crc32 == right->object_crc32 &&
         left->flags == right->flags && left->reserved == right->reserved;
}

static int vector_failure(const char *name, const char *message) {
  fprintf(stderr, "VECTOR_FAIL name=%s reason=%s\n", name, message);
  return 0;
}

static int check_valid_vector(const char *line) {
  char name[NAME_CAPACITY];
  char header_hex[HEX_HEADER_CAPACITY];
  char chunk_hex[HEX_CHUNK_CAPACITY];
  char encoded_hex[HEX_FRAGMENT_CAPACITY];
  char object_hex[HEX_OBJECT_CAPACITY];
  uint8_t expected_header[RF_APP_HEADER_BYTES];
  uint8_t chunk[RF_APP_MAX_CHUNK_BYTES];
  uint8_t expected_encoded[RF_APP_P6_MAX_PAYLOAD_BYTES];
  uint8_t object[OBJECT_CHECK_BYTES];
  uint8_t actual_header[RF_APP_HEADER_BYTES];
  uint8_t actual_encoded[RF_APP_P6_MAX_PAYLOAD_BYTES];
  size_t expected_header_size = 0U;
  size_t chunk_size = 0U;
  size_t expected_encoded_size = 0U;
  size_t object_size = 0U;
  size_t actual_encoded_size = 0U;
  uint64_t chunk_crc32;
  uint64_t check_object_crc;
  uint64_t offset;
  rf_app_header_t header;
  rf_app_header_t decoded_header;
  rf_app_fragment_view_t decoded_fragment;
  rf_app_status_t status;

  if (!json_get_string(line, "name", name, sizeof(name)) ||
      !json_get_string(line, "header_hex", header_hex,
                       sizeof(header_hex)) ||
      !json_get_string(line, "chunk_hex", chunk_hex, sizeof(chunk_hex)) ||
      !json_get_string(line, "encoded_hex", encoded_hex,
                       sizeof(encoded_hex)) ||
      !json_get_string(line, "object_hex", object_hex,
                       sizeof(object_hex)) ||
      !json_get_u64(line, "chunk_crc32", &chunk_crc32) ||
      !json_get_u64(line, "check_object_crc", &check_object_crc) ||
      !load_header(line, &header)) {
    return vector_failure("unparsed_valid", "JSON fields missing");
  }
  if (!hex_decode(header_hex, expected_header, sizeof(expected_header),
                  &expected_header_size) ||
      !hex_decode(chunk_hex, chunk, sizeof(chunk), &chunk_size) ||
      !hex_decode(encoded_hex, expected_encoded, sizeof(expected_encoded),
                  &expected_encoded_size) ||
      !hex_decode(object_hex, object, sizeof(object), &object_size)) {
    return vector_failure(name, "hex decode failed");
  }
  if (expected_header_size != RF_APP_HEADER_BYTES ||
      expected_encoded_size != RF_APP_HEADER_BYTES + chunk_size) {
    return vector_failure(name, "golden byte lengths are inconsistent");
  }

  status = rf_app_validate_header(&header);
  if (status != RF_APP_OK) {
    return vector_failure(name, rf_app_error_code(status));
  }
  status = rf_app_encode_header(&header, actual_header);
  if (status != RF_APP_OK ||
      memcmp(actual_header, expected_header, RF_APP_HEADER_BYTES) != 0) {
    return vector_failure(name, "C header encode differs from Python");
  }
  status = rf_app_decode_header(expected_header, expected_header_size,
                                &decoded_header);
  if (status != RF_APP_OK || !headers_equal(&header, &decoded_header)) {
    return vector_failure(name, "C header decode differs from Python");
  }
  status = rf_app_encode_fragment(
      &header, chunk_size == 0U ? NULL : chunk, chunk_size, actual_encoded,
      sizeof(actual_encoded), &actual_encoded_size);
  if (status != RF_APP_OK || actual_encoded_size != expected_encoded_size ||
      memcmp(actual_encoded, expected_encoded, expected_encoded_size) != 0) {
    return vector_failure(name, "C fragment encode differs from Python");
  }
  status = rf_app_decode_fragment(expected_encoded, expected_encoded_size,
                                  &decoded_fragment);
  if (status != RF_APP_OK ||
      !headers_equal(&header, &decoded_fragment.header) ||
      decoded_fragment.chunk_size != chunk_size ||
      (chunk_size != 0U &&
       memcmp(decoded_fragment.chunk, chunk, chunk_size) != 0)) {
    return vector_failure(name, "C fragment decode differs from Python");
  }
  if (rf_app_crc32(chunk_size == 0U ? NULL : chunk, chunk_size) !=
      (uint32_t)chunk_crc32) {
    return vector_failure(name, "C chunk CRC32 differs from Python");
  }
  if (check_object_crc != 0U) {
    if (object_size != header.total_length ||
        rf_app_crc32(object_size == 0U ? NULL : object, object_size) !=
            header.object_crc32) {
      return vector_failure(name, "C object CRC32 differs from Python");
    }
    offset = (uint64_t)header.fragment_index * RF_APP_MAX_CHUNK_BYTES;
    if (offset + chunk_size > object_size ||
        (chunk_size != 0U &&
         memcmp(object + (size_t)offset, chunk, chunk_size) != 0)) {
      return vector_failure(name, "chunk does not match object geometry");
    }
  }
  return 1;
}

static int check_invalid_vector(const char *line) {
  char name[NAME_CAPACITY];
  char operation[64];
  char expected_error[64];
  char raw_hex[HEX_FRAGMENT_CAPACITY + 4U];
  char chunk_hex[HEX_CHUNK_CAPACITY];
  uint8_t raw[RF_APP_P6_MAX_PAYLOAD_BYTES + 2U];
  uint8_t chunk[RF_APP_MAX_CHUNK_BYTES];
  uint8_t output[RF_APP_P6_MAX_PAYLOAD_BYTES];
  size_t raw_size = 0U;
  size_t chunk_size = 0U;
  size_t output_size = 0U;
  uint64_t total_length;
  uint16_t count = 0U;
  rf_app_header_t header;
  rf_app_fragment_view_t fragment;
  rf_app_status_t status;

  if (!json_get_string(line, "name", name, sizeof(name)) ||
      !json_get_string(line, "operation", operation, sizeof(operation)) ||
      !json_get_string(line, "expected_error", expected_error,
                       sizeof(expected_error))) {
    return vector_failure("unparsed_invalid", "JSON fields missing");
  }
  if (strcmp(operation, "decode_header") == 0 ||
      strcmp(operation, "decode_fragment") == 0) {
    if (!json_get_string(line, "raw_hex", raw_hex, sizeof(raw_hex)) ||
        !hex_decode(raw_hex, raw, sizeof(raw), &raw_size)) {
      return vector_failure(name, "invalid raw_hex");
    }
    status = strcmp(operation, "decode_header") == 0
                 ? rf_app_decode_header(raw, raw_size, &header)
                 : rf_app_decode_fragment(raw, raw_size, &fragment);
  } else if (strcmp(operation, "encode_fragment") == 0) {
    if (!load_header(line, &header) ||
        !json_get_string(line, "chunk_hex", chunk_hex,
                         sizeof(chunk_hex)) ||
        !hex_decode(chunk_hex, chunk, sizeof(chunk), &chunk_size)) {
      return vector_failure(name, "invalid encode fields");
    }
    status = rf_app_encode_fragment(
        &header, chunk_size == 0U ? NULL : chunk, chunk_size, output,
        sizeof(output), &output_size);
  } else if (strcmp(operation, "fragment_count") == 0) {
    if (!json_get_u64(line, "total_length", &total_length) ||
        total_length > UINT32_MAX) {
      return vector_failure(name, "invalid total_length field");
    }
    status = rf_app_fragment_count((uint32_t)total_length, &count);
  } else {
    return vector_failure(name, "unknown invalid-vector operation");
  }
  if (strcmp(rf_app_error_code(status), expected_error) != 0) {
    fprintf(stderr,
            "VECTOR_FAIL name=%s expected_error=%s actual_error=%s\n", name,
            expected_error, rf_app_error_code(status));
    return 0;
  }
  return 1;
}

int main(int argc, char **argv) {
  FILE *handle;
  char *line;
  unsigned long valid_count = 0UL;
  unsigned long invalid_count = 0UL;
  unsigned long failures = 0UL;

  if (argc != 2) {
    fprintf(stderr, "usage: %s <p7_app_protocol_vectors.json>\n", argv[0]);
    return 2;
  }
  if (rf_app_crc32((const uint8_t *)"123456789", 9U) !=
      UINT32_C(0xcbf43926)) {
    fprintf(stderr, "CRC32_SELF_TEST=FAIL\n");
    return 3;
  }
  handle = fopen(argv[1], "rb");
  if (handle == NULL) {
    perror("open vectors");
    return 4;
  }
  line = (char *)malloc(LINE_CAPACITY);
  if (line == NULL) {
    fclose(handle);
    return 5;
  }
  while (fgets(line, (int)LINE_CAPACITY, handle) != NULL) {
    if (strstr(line, "\"kind\":\"valid\"") != NULL) {
      ++valid_count;
      if (!check_valid_vector(line)) {
        ++failures;
      }
    } else if (strstr(line, "\"kind\":\"invalid\"") != NULL) {
      ++invalid_count;
      if (!check_invalid_vector(line)) {
        ++failures;
      }
    }
  }
  free(line);
  fclose(handle);

  printf("{\"P7_C_GOLDEN_VECTOR_HARNESS\":\"%s\","
         "\"valid_vectors\":%lu,\"invalid_vectors\":%lu,"
         "\"total_vectors\":%lu,\"failures\":%lu,"
         "\"header_bytes\":%u,\"p6_max_payload_bytes\":%u,"
         "\"max_chunk_bytes\":%u,\"max_object_bytes\":%" PRIu32 ","
         "\"flag_first\":%u,\"flag_last\":%u,"
         "\"flag_retransmit\":%u,\"flag_control\":%u,"
         "\"lane0_only\":%u,\"lane1_only\":%u,"
         "\"stripe_round_robin\":%u,\"replicate_0x3\":%u}\n",
         failures == 0UL ? "PASS" : "FAIL", valid_count, invalid_count,
         valid_count + invalid_count, failures, (unsigned)RF_APP_HEADER_BYTES,
         (unsigned)RF_APP_P6_MAX_PAYLOAD_BYTES,
         (unsigned)RF_APP_MAX_CHUNK_BYTES, RF_APP_MAX_OBJECT_BYTES,
         (unsigned)RF_APP_FLAG_FIRST, (unsigned)RF_APP_FLAG_LAST,
         (unsigned)RF_APP_FLAG_RETRANSMIT, (unsigned)RF_APP_FLAG_CONTROL,
         (unsigned)RF_APP_LANE_POLICY_LANE0_ONLY,
         (unsigned)RF_APP_LANE_POLICY_LANE1_ONLY,
         (unsigned)RF_APP_LANE_POLICY_STRIPE_ROUND_ROBIN,
         (unsigned)RF_APP_LANE_POLICY_REPLICATE_0X3);
  return failures == 0UL ? 0 : 1;
}
