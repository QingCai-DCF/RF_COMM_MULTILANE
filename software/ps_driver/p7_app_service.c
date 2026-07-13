#include "p7_app_service.h"
#include "p7_admission_contract.h"

#include "xil_cache.h"
#include "xil_io.h"
#include "xil_types.h"
#include "xpseudo_asm.h"
#include "xtime_l.h"

#include <string.h>

#define P7_P6_SESSION UINT32_C(0x2201)
#define P7_P6_TIMEOUT_CYCLES UINT32_C(64000000)
#define P7_KNOWN_GOOD_TXD_HIGH_CYCLES UINT32_C(8)
#define P7_FRAGMENT_ADMISSION_GUARD_TICKS \
  ((uint64_t)COUNTS_PER_SECOND / UINT64_C(2))
#define P7_SHUTDOWN_GUARD_TICKS \
  ((uint64_t)COUNTS_PER_SECOND / UINT64_C(10))

enum {
  P7_P6_STATUS_READY = 1u << 1,
  P7_P6_STATUS_BUSY = 1u << 3,
  P7_P6_STATUS_DONE = 1u << 4,
  P7_P6_STATUS_FAIL = 1u << 5,
  P7_P6_STATUS_CONFIG_REJECTED = 1u << 6,
  P7_P6_STATUS_TIMEOUT = 1u << 7,
};

_Static_assert(sizeof(p7_mailbox_control_t) == 256U,
               "P7 mailbox control must be 256 bytes");
_Static_assert(sizeof(p7_object_descriptor_t) == 256U,
               "P7 descriptor must be 256 bytes");
_Static_assert(sizeof(p7_fragment_trace_t) == 64U,
               "P7 fragment trace must be 64 bytes");
_Static_assert(sizeof(p7_failure_snapshot_header_t) == 64U,
               "P7 failure snapshot header must be 64 bytes");
_Static_assert(sizeof(p7_first_error_diagnostic_t) == 320U,
               "P7 first-error diagnostic must be 320 bytes");
_Static_assert(RF_APP_P6_MAX_PAYLOAD_BYTES <= P7_LOCAL_PAYLOAD_BYTES,
               "P7 local payload storage must contain the protocol maximum");
_Static_assert(RF_TRANSPORT_MAX_PAYLOAD_BYTES ==
                   RF_APP_P6_MAX_PAYLOAD_BYTES,
               "P7 transport and RFAP protocol payload limits must agree");
_Static_assert((P7_FAILURE_SNAPSHOT_BASEADDR & (P7_DDR_ALIGNMENT - 1U)) == 0U,
               "P7 failure snapshot must be 64-byte aligned");
_Static_assert(P7_FAILURE_SNAPSHOT_BASEADDR >=
                   P7_DESCRIPTOR_BASEADDR +
                       P7_DESCRIPTOR_QUEUE_DEPTH * P7_DESCRIPTOR_BYTES,
               "P7 failure snapshot must not overlap the descriptor queue");
_Static_assert(P7_FAILURE_SNAPSHOT_BASEADDR + P7_FAILURE_SNAPSHOT_TOTAL_BYTES <=
                   P7_INPUT_REFERENCE_BASEADDR,
               "P7 failure snapshot must precede fixed input reference");
_Static_assert((P7_INPUT_REFERENCE_BASEADDR & (P7_DDR_ALIGNMENT - 1U)) == 0U,
               "P7 input reference must be 64-byte aligned");
_Static_assert(P7_INPUT_REFERENCE_BASEADDR + P7_LOCAL_PAYLOAD_BYTES <=
                   P7_P6_TX_READBACK_BASEADDR,
               "P7 input reference must not overlap TX readback scratch");
_Static_assert((P7_P6_TX_READBACK_BASEADDR & (P7_DDR_ALIGNMENT - 1U)) == 0U,
               "P7 TX readback scratch must be 64-byte aligned");
_Static_assert(P7_P6_TX_READBACK_BASEADDR + P7_LOCAL_PAYLOAD_BYTES <=
                   P7_MAILBOX_RESERVED_END,
               "P7 diagnostic scratch must remain in reserved OCM");

typedef struct p7_sha256_context {
  uint32_t state[8];
  uint64_t total_bytes;
  uint8_t block[64];
  uint32_t block_used;
} p7_sha256_context_t;

typedef struct p7_service_context {
  const ir_mmio_t *io;
  volatile p7_mailbox_control_t *mailbox;
  uint64_t start_ticks;
  uint64_t runtime_limit_ticks;
  uint64_t shutdown_deadline_ticks;
  uint64_t completion_deadline_ticks;
  uint64_t admission_cutoff_ticks;
  uint64_t admission_guard_ticks;
  uint32_t queue_depth;
  uint32_t consumer_index;
  uint32_t identity_valid;
  uint32_t current_epoch;
  uint32_t last_object_id;
  uint32_t require_new_epoch;
  uint32_t fault_latched;
  uint32_t auto_deadline_reached;
  uint32_t abort_command_counted;
  uint32_t shutdown_attempted;
  int shutdown_status;
} p7_service_context_t;

typedef struct p7_p6_backend_context {
  const ir_mmio_t *io;
  p7_service_context_t *service;
  const p7_object_descriptor_t *request;
  uint8_t tx_payload[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)));
  uint8_t rx_payload[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)));
  size_t tx_size;
  size_t rx_size;
  uint32_t lane_mask;
  uint32_t fragment_index;
  uint32_t diagnostic_error;
  uint32_t token;
  int run_status;
  ir_p6_payload_result_t p6;
  rf_transport_metrics_t metrics;
} p7_p6_backend_context_t;

_Static_assert(_Alignof(p7_p6_backend_context_t) >= P7_DDR_ALIGNMENT,
               "P7 backend context must preserve 64-byte member alignment");
_Static_assert((offsetof(p7_p6_backend_context_t, tx_payload) &
                (P7_DDR_ALIGNMENT - 1U)) == 0U,
               "P7 local TX payload must be 64-byte aligned");
_Static_assert((offsetof(p7_p6_backend_context_t, rx_payload) &
                (P7_DDR_ALIGNMENT - 1U)) == 0U,
               "P7 local RX payload must be 64-byte aligned");

static uint32_t p7_publish_failure_snapshot_diagnostic(
    volatile p7_mailbox_control_t *mailbox, uint32_t status,
    uint32_t address, uint32_t bytes, uint32_t magic_readback);

static uint32_t p7_rotr(uint32_t value, uint32_t count) {
  return (value >> count) | (value << (32U - count));
}

static uint32_t p7_read_be32(const uint8_t *input) {
  return ((uint32_t)input[0] << 24) | ((uint32_t)input[1] << 16) |
         ((uint32_t)input[2] << 8) | (uint32_t)input[3];
}

static void p7_write_be32(uint8_t *output, uint32_t value) {
  output[0] = (uint8_t)(value >> 24);
  output[1] = (uint8_t)(value >> 16);
  output[2] = (uint8_t)(value >> 8);
  output[3] = (uint8_t)value;
}

static void p7_sha256_transform(p7_sha256_context_t *context,
                                const uint8_t block[64]) {
  static const uint32_t constants[64] = {
      UINT32_C(0x428a2f98), UINT32_C(0x71374491), UINT32_C(0xb5c0fbcf),
      UINT32_C(0xe9b5dba5), UINT32_C(0x3956c25b), UINT32_C(0x59f111f1),
      UINT32_C(0x923f82a4), UINT32_C(0xab1c5ed5), UINT32_C(0xd807aa98),
      UINT32_C(0x12835b01), UINT32_C(0x243185be), UINT32_C(0x550c7dc3),
      UINT32_C(0x72be5d74), UINT32_C(0x80deb1fe), UINT32_C(0x9bdc06a7),
      UINT32_C(0xc19bf174), UINT32_C(0xe49b69c1), UINT32_C(0xefbe4786),
      UINT32_C(0x0fc19dc6), UINT32_C(0x240ca1cc), UINT32_C(0x2de92c6f),
      UINT32_C(0x4a7484aa), UINT32_C(0x5cb0a9dc), UINT32_C(0x76f988da),
      UINT32_C(0x983e5152), UINT32_C(0xa831c66d), UINT32_C(0xb00327c8),
      UINT32_C(0xbf597fc7), UINT32_C(0xc6e00bf3), UINT32_C(0xd5a79147),
      UINT32_C(0x06ca6351), UINT32_C(0x14292967), UINT32_C(0x27b70a85),
      UINT32_C(0x2e1b2138), UINT32_C(0x4d2c6dfc), UINT32_C(0x53380d13),
      UINT32_C(0x650a7354), UINT32_C(0x766a0abb), UINT32_C(0x81c2c92e),
      UINT32_C(0x92722c85), UINT32_C(0xa2bfe8a1), UINT32_C(0xa81a664b),
      UINT32_C(0xc24b8b70), UINT32_C(0xc76c51a3), UINT32_C(0xd192e819),
      UINT32_C(0xd6990624), UINT32_C(0xf40e3585), UINT32_C(0x106aa070),
      UINT32_C(0x19a4c116), UINT32_C(0x1e376c08), UINT32_C(0x2748774c),
      UINT32_C(0x34b0bcb5), UINT32_C(0x391c0cb3), UINT32_C(0x4ed8aa4a),
      UINT32_C(0x5b9cca4f), UINT32_C(0x682e6ff3), UINT32_C(0x748f82ee),
      UINT32_C(0x78a5636f), UINT32_C(0x84c87814), UINT32_C(0x8cc70208),
      UINT32_C(0x90befffa), UINT32_C(0xa4506ceb), UINT32_C(0xbef9a3f7),
      UINT32_C(0xc67178f2)};
  uint32_t words[64];
  uint32_t a;
  uint32_t b;
  uint32_t c;
  uint32_t d;
  uint32_t e;
  uint32_t f;
  uint32_t g;
  uint32_t h;

  for (uint32_t index = 0U; index < 16U; ++index) {
    words[index] = p7_read_be32(block + 4U * index);
  }
  for (uint32_t index = 16U; index < 64U; ++index) {
    uint32_t x = words[index - 15U];
    uint32_t y = words[index - 2U];
    uint32_t s0 = p7_rotr(x, 7U) ^ p7_rotr(x, 18U) ^ (x >> 3U);
    uint32_t s1 = p7_rotr(y, 17U) ^ p7_rotr(y, 19U) ^ (y >> 10U);
    words[index] = words[index - 16U] + s0 + words[index - 7U] + s1;
  }
  a = context->state[0];
  b = context->state[1];
  c = context->state[2];
  d = context->state[3];
  e = context->state[4];
  f = context->state[5];
  g = context->state[6];
  h = context->state[7];
  for (uint32_t index = 0U; index < 64U; ++index) {
    uint32_t s1 = p7_rotr(e, 6U) ^ p7_rotr(e, 11U) ^ p7_rotr(e, 25U);
    uint32_t choose = (e & f) ^ ((~e) & g);
    uint32_t temp1 = h + s1 + choose + constants[index] + words[index];
    uint32_t s0 = p7_rotr(a, 2U) ^ p7_rotr(a, 13U) ^ p7_rotr(a, 22U);
    uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
    uint32_t temp2 = s0 + majority;
    h = g;
    g = f;
    f = e;
    e = d + temp1;
    d = c;
    c = b;
    b = a;
    a = temp1 + temp2;
  }
  context->state[0] += a;
  context->state[1] += b;
  context->state[2] += c;
  context->state[3] += d;
  context->state[4] += e;
  context->state[5] += f;
  context->state[6] += g;
  context->state[7] += h;
}

static void p7_sha256_init(p7_sha256_context_t *context) {
  static const uint32_t initial[8] = {
      UINT32_C(0x6a09e667), UINT32_C(0xbb67ae85), UINT32_C(0x3c6ef372),
      UINT32_C(0xa54ff53a), UINT32_C(0x510e527f), UINT32_C(0x9b05688c),
      UINT32_C(0x1f83d9ab), UINT32_C(0x5be0cd19)};
  memcpy(context->state, initial, sizeof(initial));
  context->total_bytes = 0U;
  context->block_used = 0U;
}

static void p7_sha256_update(p7_sha256_context_t *context,
                             const uint8_t *data, size_t size) {
  if (size == 0U) return;
  context->total_bytes += size;
  while (size != 0U) {
    size_t available = 64U - context->block_used;
    size_t take = size < available ? size : available;
    memcpy(context->block + context->block_used, data, take);
    context->block_used += (uint32_t)take;
    data += take;
    size -= take;
    if (context->block_used == 64U) {
      p7_sha256_transform(context, context->block);
      context->block_used = 0U;
    }
  }
}

static void p7_sha256_final(p7_sha256_context_t *context, uint8_t output[32]) {
  uint64_t total_bits = context->total_bytes * UINT64_C(8);
  context->block[context->block_used++] = UINT8_C(0x80);
  if (context->block_used > 56U) {
    memset(context->block + context->block_used, 0, 64U - context->block_used);
    p7_sha256_transform(context, context->block);
    context->block_used = 0U;
  }
  memset(context->block + context->block_used, 0, 56U - context->block_used);
  for (uint32_t index = 0U; index < 8U; ++index) {
    context->block[63U - index] = (uint8_t)(total_bits >> (8U * index));
  }
  p7_sha256_transform(context, context->block);
  for (uint32_t index = 0U; index < 8U; ++index) {
    p7_write_be32(output + 4U * index, context->state[index]);
  }
}

static void p7_sha256(const uint8_t *data, size_t size, uint8_t output[32]) {
  p7_sha256_context_t context;
  p7_sha256_init(&context);
  p7_sha256_update(&context, data, size);
  p7_sha256_final(&context, output);
}

static uint32_t p7_digest_word(const uint8_t digest[32], uint32_t index) {
  return p7_read_be32(digest + 4U * index);
}

static void p7_copy_digest_words(volatile uint32_t output[8],
                                 const uint8_t digest[32]) {
  for (uint32_t index = 0U; index < 8U; ++index) {
    output[index] = p7_digest_word(digest, index);
  }
}

static int p7_digest_matches_words(const uint8_t digest[32],
                                   const uint32_t expected[8]) {
  for (uint32_t index = 0U; index < 8U; ++index) {
    if (p7_digest_word(digest, index) != expected[index]) return 0;
  }
  return 1;
}

static void p7_flush(const volatile void *address, uint32_t size) {
  if (size != 0U) {
    Xil_DCacheFlushRange((INTPTR)address, size);
  }
}

static void p7_invalidate(const volatile void *address, uint32_t size) {
  if (size != 0U) {
    Xil_DCacheInvalidateRange((INTPTR)address, size);
  }
}

static void p7_split_ticks(uint64_t ticks, volatile uint32_t *low,
                           volatile uint32_t *high) {
  *low = (uint32_t)ticks;
  *high = (uint32_t)(ticks >> 32);
}

static void p7_publish_runtime_elapsed(
    volatile p7_mailbox_control_t *mailbox, uint64_t ticks,
    uint32_t request) {
  uint32_t sequence = mailbox->runtime_elapsed_sequence;
  if ((sequence & 1U) != 0U) sequence += 1U;
  mailbox->runtime_elapsed_sequence = sequence + 1U;
  dmb();
  mailbox->runtime_elapsed_ticks_low = (uint32_t)ticks;
  mailbox->runtime_elapsed_ticks_high = (uint32_t)(ticks >> 32);
  dmb();
  mailbox->runtime_elapsed_sequence = sequence + 2U;
  dmb();
  mailbox->runtime_elapsed_ack = request;
  dmb();
}

static uint32_t p7_read_runtime_elapsed_request(
    volatile p7_mailbox_control_t *mailbox) {
  p7_invalidate(&mailbox->runtime_elapsed_request,
                sizeof(mailbox->runtime_elapsed_request));
  return mailbox->runtime_elapsed_request;
}

static uint64_t p7_get_ticks(void) {
  XTime value;
  XTime_GetTime(&value);
  return (uint64_t)value;
}

static uint64_t p7_runtime_elapsed(const p7_service_context_t *service,
                                   uint64_t now) {
  return now - service->start_ticks;
}

static int p7_runtime_expired(p7_service_context_t *service) {
  volatile p7_mailbox_control_t *mailbox = service->mailbox;
  /* Observe the host request before sampling the timer.  The ACK therefore
   * proves that its published tick is causally later than the request. */
  uint32_t request = p7_read_runtime_elapsed_request(mailbox);
  uint64_t current = p7_get_ticks();
  uint64_t elapsed = p7_runtime_elapsed(service, current);
  if (request != mailbox->runtime_elapsed_ack) {
    p7_publish_runtime_elapsed(mailbox, elapsed, request);
  }
  if (current >= service->shutdown_deadline_ticks) {
    mailbox->runtime_flags |= P7_RUNTIME_DEADLINE_REACHED;
    service->auto_deadline_reached = 1U;
    return 1;
  }
  return 0;
}

static int p7_runtime_has_budget(p7_service_context_t *service,
                                 uint64_t reserve_ticks) {
  uint64_t now = p7_get_ticks();
  if (now >= service->shutdown_deadline_ticks) return 0;
  return service->shutdown_deadline_ticks - now > reserve_ticks;
}

static int p7_descriptor_admission_allowed(
    const p7_service_context_t *service) {
  return p7_admission_deadline_allowed(
      p7_get_ticks(), service->admission_cutoff_ticks,
      service->admission_guard_ticks);
}

static uint32_t p7_control_command(p7_service_context_t *service) {
  p7_invalidate(&service->mailbox->control_command,
                sizeof(service->mailbox->control_command));
  return service->mailbox->control_command;
}

static int p7_stop_and_shutdown(p7_service_context_t *service) {
  if (service->shutdown_attempted == 0U) {
    service->shutdown_status = ir_driver_shutdown(service->io);
    service->shutdown_attempted = 1U;
    service->mailbox->shutdown_result =
        service->shutdown_status == 0 ? 0U : 1U;
  }
  return service->shutdown_status;
}

static int p7_active_stop_requested(p7_service_context_t *service) {
  uint32_t command = p7_control_command(service);
  return command == P7_CONTROL_STOP || command == P7_CONTROL_ABORT ||
         command == P7_CONTROL_SHUTDOWN || p7_runtime_expired(service);
}

/* The P7 hardware boundary must not depend on an opaque word-copy routine.
 * r27/r30 captured a deterministic half-word-zeroed payload even though the
 * P6 fragment compared equal before the DDR output write.  Volatile byte
 * accesses make each transfer observable, and the second pass fails closed
 * before the copied bytes can contribute to a successful descriptor. */
typedef struct p7_mismatch_observation {
  uint32_t offset;
  uint32_t expected_byte;
  uint32_t actual_byte;
} p7_mismatch_observation_t;

static void p7_reset_mismatch(p7_mismatch_observation_t *observation) {
  if (observation == NULL) return;
  observation->offset = UINT32_MAX;
  observation->expected_byte = P7_DIAGNOSTIC_MISSING_BYTE;
  observation->actual_byte = P7_DIAGNOSTIC_MISSING_BYTE;
}

static __attribute__((noinline)) int p7_copy_bytes_verified(
    volatile uint8_t *destination, const volatile uint8_t *source,
    uint32_t size, p7_mismatch_observation_t *observation) {
  p7_reset_mismatch(observation);
  if ((destination == NULL || source == NULL) && size != 0U) return 0;
  for (uint32_t index = 0U; index < size; ++index) {
    destination[index] = source[index];
  }
  dsb();
  for (uint32_t index = 0U; index < size; ++index) {
    uint32_t expected_byte = source[index];
    uint32_t actual_byte = destination[index];
    if (actual_byte != expected_byte) {
      if (observation != NULL) {
        observation->offset = index;
        observation->expected_byte = expected_byte;
        observation->actual_byte = actual_byte;
      }
      return 0;
    }
  }
  return 1;
}

static __attribute__((noinline)) int p7_bytes_equal_volatile(
    const volatile uint8_t *left, const volatile uint8_t *right,
    uint32_t size, p7_mismatch_observation_t *observation) {
  p7_reset_mismatch(observation);
  if ((left == NULL || right == NULL) && size != 0U) return 0;
  dsb();
  for (uint32_t index = 0U; index < size; ++index) {
    uint32_t expected_byte = left[index];
    uint32_t actual_byte = right[index];
    if (actual_byte != expected_byte) {
      if (observation != NULL) {
        observation->offset = index;
        observation->expected_byte = expected_byte;
        observation->actual_byte = actual_byte;
      }
      return 0;
    }
  }
  return 1;
}

static int p7_integrity_checked(p7_service_context_t *service,
                                const uint8_t *data, uint32_t size,
                                uint32_t *crc_out, uint8_t sha_out[32],
                                uint8_t *retained_snapshot,
                                uint32_t *retained_length) {
  static const uint32_t crc_table[16] = {
      UINT32_C(0x00000000), UINT32_C(0x1db71064),
      UINT32_C(0x3b6e20c8), UINT32_C(0x26d930ac),
      UINT32_C(0x76dc4190), UINT32_C(0x6b6b51f4),
      UINT32_C(0x4db26158), UINT32_C(0x5005713c),
      UINT32_C(0xedb88320), UINT32_C(0xf00f9344),
      UINT32_C(0xd6d6a3e8), UINT32_C(0xcb61b38c),
      UINT32_C(0x9b64c2b0), UINT32_C(0x86d3d2d4),
      UINT32_C(0xa00ae278), UINT32_C(0xbdbdf21c)};
  p7_sha256_context_t sha;
  uint8_t snapshot[256] __attribute__((aligned(64)));
  uint32_t crc = UINT32_C(0xffffffff);
  uint32_t offset = 0U;
  if ((data == NULL && size != 0U) || crc_out == NULL || sha_out == NULL ||
      ((retained_snapshot == NULL) != (retained_length == NULL))) {
    return 0;
  }
  if (retained_length != NULL) *retained_length = 0U;
  p7_sha256_init(&sha);
  while (offset < size) {
    uint32_t chunk = size - offset;
    if (chunk > 256U) chunk = 256U;
    if (p7_active_stop_requested(service)) {
      (void)p7_stop_and_shutdown(service);
      return 0;
    }
    /* CRC32 and SHA256 must consume one immutable observation.  The buffers
     * live in DDR and are also visible to JTAG/PL, so independently rereading
     * the same address for each digest can publish a self-contradictory
     * terminal descriptor if cache visibility changes between those reads. */
    p7_invalidate(data + offset, chunk);
    memcpy(snapshot, data + offset, chunk);
    if (retained_snapshot != NULL &&
        offset < P7_FAILURE_SNAPSHOT_MAX_BYTES) {
      uint32_t retained = P7_FAILURE_SNAPSHOT_MAX_BYTES - offset;
      if (retained > chunk) retained = chunk;
      memcpy(retained_snapshot + offset, snapshot, retained);
      *retained_length = offset + retained;
    }
    for (uint32_t index = 0U; index < chunk; ++index) {
      crc ^= snapshot[index];
      crc = crc_table[crc & UINT32_C(0x0f)] ^ (crc >> 4);
      crc = crc_table[crc & UINT32_C(0x0f)] ^ (crc >> 4);
    }
    p7_sha256_update(&sha, snapshot, chunk);
    offset += chunk;
  }
  if (p7_active_stop_requested(service)) {
    (void)p7_stop_and_shutdown(service);
    return 0;
  }
  *crc_out = crc ^ UINT32_C(0xffffffff);
  p7_sha256_final(&sha, sha_out);
  return 1;
}

static void p7_hash_volatile_bytes(const volatile uint8_t *data,
                                   uint32_t size, uint32_t *crc_out,
                                   uint8_t sha_out[32],
                                   uint32_t observed_offset,
                                   uint32_t observed_byte) {
  static const uint32_t crc_table[16] = {
      UINT32_C(0x00000000), UINT32_C(0x1db71064),
      UINT32_C(0x3b6e20c8), UINT32_C(0x26d930ac),
      UINT32_C(0x76dc4190), UINT32_C(0x6b6b51f4),
      UINT32_C(0x4db26158), UINT32_C(0x5005713c),
      UINT32_C(0xedb88320), UINT32_C(0xf00f9344),
      UINT32_C(0xd6d6a3e8), UINT32_C(0xcb61b38c),
      UINT32_C(0x9b64c2b0), UINT32_C(0x86d3d2d4),
      UINT32_C(0xa00ae278), UINT32_C(0xbdbdf21c)};
  p7_sha256_context_t sha;
  uint8_t observation[64] __attribute__((aligned(64)));
  uint32_t crc = UINT32_C(0xffffffff);
  uint32_t offset = 0U;
  p7_sha256_init(&sha);
  while (offset < size) {
    uint32_t chunk = size - offset;
    if (chunk > sizeof(observation)) chunk = sizeof(observation);
    for (uint32_t index = 0U; index < chunk; ++index) {
      uint32_t absolute_index = offset + index;
      observation[index] = absolute_index == observed_offset &&
                                   observed_byte <= UINT8_MAX
                               ? (uint8_t)observed_byte
                               : data[absolute_index];
      crc ^= observation[index];
      crc = (crc >> 4) ^ crc_table[crc & 0x0fU];
      crc = (crc >> 4) ^ crc_table[crc & 0x0fU];
    }
    p7_sha256_update(&sha, observation, chunk);
    offset += chunk;
  }
  *crc_out = crc ^ UINT32_C(0xffffffff);
  p7_sha256_final(&sha, sha_out);
}

static uint32_t p7_first_mismatch_offset(
    const volatile uint8_t *expected, uint32_t expected_length,
    const volatile uint8_t *actual, uint32_t actual_length) {
  uint32_t common = expected_length < actual_length ? expected_length
                                                     : actual_length;
  p7_mismatch_observation_t observation;
  if (!p7_bytes_equal_volatile(expected, actual, common, &observation)) {
    return observation.offset;
  }
  return expected_length == actual_length ? UINT32_MAX : common;
}

static int p7_compare_object_checked(
    p7_service_context_t *service, const volatile uint8_t *expected,
    const volatile uint8_t *actual, uint32_t size,
    p7_mismatch_observation_t *observation) {
  uint32_t offset = 0U;
  if (observation == NULL) return -1;
  p7_reset_mismatch(observation);
  while (offset < size) {
    uint32_t chunk = size - offset;
    p7_mismatch_observation_t local;
    if (chunk > 256U) chunk = 256U;
    if (p7_active_stop_requested(service)) return -1;
    p7_invalidate((const void *)(expected + offset), chunk);
    p7_invalidate((const void *)(actual + offset), chunk);
    if (!p7_bytes_equal_volatile(expected + offset, actual + offset, chunk,
                                 &local)) {
      *observation = local;
      observation->offset += offset;
      return 0;
    }
    offset += chunk;
  }
  return 1;
}

static uint32_t p7_publish_first_error_diagnostic(
    volatile p7_mailbox_control_t *mailbox,
    const p7_object_descriptor_t *request, uint32_t stage,
    uint32_t error_code, uint32_t fragment_index, uint32_t lane_mask,
    const volatile uint8_t *expected, uint32_t expected_length,
    const volatile uint8_t *actual, uint32_t actual_length,
    const p7_mismatch_observation_t *observation) {
  const uint32_t address = P7_FAILURE_SNAPSHOT_BASEADDR;
  const uint32_t total_bytes = P7_FIRST_ERROR_DIAGNOSTIC_TOTAL_BYTES;
  p7_first_error_diagnostic_t diagnostic;
  volatile p7_first_error_diagnostic_t *published;
  uint8_t expected_sha[32];
  uint8_t actual_sha[32];
  uint32_t mismatch;
  uint32_t max_length;
  uint32_t magic_readback;
  uint32_t observed_expected_byte = P7_DIAGNOSTIC_MISSING_BYTE;
  uint32_t observed_actual_byte = P7_DIAGNOSTIC_MISSING_BYTE;

  if (mailbox == NULL || request == NULL ||
      (expected == NULL && expected_length != 0U) ||
      (actual == NULL && actual_length != 0U)) {
    if (mailbox == NULL) return P7_FAILURE_SNAPSHOT_STATUS_NULL_SNAPSHOT;
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_NULL_SNAPSHOT, 0U, 0U, 0U);
  }
  /* A nonzero marker belongs to the first already-published observation.
   * Never overwrite it with a later consequence of the same failure. */
  if (Xil_In32(address) != 0U) return mailbox->failure_snapshot_status;
  max_length = expected_length > actual_length ? expected_length
                                                : actual_length;
  mismatch = observation != NULL ? observation->offset : UINT32_MAX;
  if (mismatch < max_length &&
      observation->expected_byte <= P7_DIAGNOSTIC_MISSING_BYTE &&
      observation->actual_byte <= P7_DIAGNOSTIC_MISSING_BYTE &&
      observation->expected_byte != observation->actual_byte &&
      ((mismatch >= expected_length) ==
       (observation->expected_byte == P7_DIAGNOSTIC_MISSING_BYTE)) &&
      ((mismatch >= actual_length) ==
       (observation->actual_byte == P7_DIAGNOSTIC_MISSING_BYTE))) {
    observed_expected_byte = observation->expected_byte;
    observed_actual_byte = observation->actual_byte;
  } else {
    mismatch = p7_first_mismatch_offset(expected, expected_length, actual,
                                        actual_length);
    if (mismatch < max_length) {
      observed_expected_byte = mismatch < expected_length
                                   ? expected[mismatch]
                                   : P7_DIAGNOSTIC_MISSING_BYTE;
      observed_actual_byte = mismatch < actual_length
                                 ? actual[mismatch]
                                 : P7_DIAGNOSTIC_MISSING_BYTE;
    }
  }
  if (mismatch == UINT32_MAX) {
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_ZERO_LENGTH, 0U, 0U, 0U);
  }
  memset(&diagnostic, 0, sizeof(diagnostic));
  diagnostic.version = P7_RUNTIME_VERSION;
  diagnostic.stage = stage;
  diagnostic.error_code = error_code;
  diagnostic.session_epoch = request->session_epoch;
  diagnostic.object_id = request->object_id;
  diagnostic.fragment_index = fragment_index;
  diagnostic.lane_mask = lane_mask;
  diagnostic.expected_length = expected_length;
  diagnostic.actual_length = actual_length;
  diagnostic.first_bad_offset = mismatch;
  diagnostic.expected_byte = observed_expected_byte;
  diagnostic.actual_byte = observed_actual_byte;
  diagnostic.expected_address = (uint32_t)(uintptr_t)expected;
  diagnostic.actual_address = (uint32_t)(uintptr_t)actual;
  p7_hash_volatile_bytes(expected, expected_length,
                         &diagnostic.expected_crc32, expected_sha, mismatch,
                         observed_expected_byte);
  p7_hash_volatile_bytes(actual, actual_length, &diagnostic.actual_crc32,
                         actual_sha, mismatch, observed_actual_byte);
  p7_copy_digest_words(diagnostic.expected_sha256, expected_sha);
  p7_copy_digest_words(diagnostic.actual_sha256, actual_sha);
  diagnostic.snapshot_offset = mismatch > 32U ? mismatch - 32U : 0U;
  diagnostic.snapshot_length = max_length - diagnostic.snapshot_offset;
  if (diagnostic.snapshot_length > P7_FIRST_ERROR_SNAPSHOT_BYTES) {
    diagnostic.snapshot_length = P7_FIRST_ERROR_SNAPSHOT_BYTES;
  }
  for (uint32_t index = 0U; index < diagnostic.snapshot_length; ++index) {
    uint32_t source_index = diagnostic.snapshot_offset + index;
    if (source_index < expected_length) {
      diagnostic.expected_snapshot[index] =
          source_index == mismatch && observed_expected_byte <= UINT8_MAX
              ? (uint8_t)observed_expected_byte
              : expected[source_index];
    }
    if (source_index < actual_length) {
      diagnostic.actual_snapshot[index] =
          source_index == mismatch && observed_actual_byte <= UINT8_MAX
              ? (uint8_t)observed_actual_byte
              : actual[source_index];
    }
  }
  published =
      (volatile p7_first_error_diagnostic_t *)(uintptr_t)address;
  memcpy((void *)published, &diagnostic, sizeof(diagnostic));
  p7_flush((const void *)(uintptr_t)address, total_bytes);
  Xil_Out32(address, P7_FIRST_ERROR_DIAGNOSTIC_MAGIC);
  dsb();
  p7_flush(&published->magic, sizeof(published->magic));
  dsb();
  magic_readback = Xil_In32(address);
  if (magic_readback != P7_FIRST_ERROR_DIAGNOSTIC_MAGIC) {
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_MARKER_READBACK_FAILED, address,
        total_bytes, magic_readback);
  }
  return p7_publish_failure_snapshot_diagnostic(
      mailbox, P7_FAILURE_SNAPSHOT_STATUS_PUBLISHED, address, total_bytes,
      magic_readback);
}

static int p7_p6_open(rf_transport_backend_t *backend) {
  p7_p6_backend_context_t *context =
      (p7_p6_backend_context_t *)backend->context;
  memset(&context->metrics, 0, sizeof(context->metrics));
  context->token = 0U;
  context->diagnostic_error = P7_ERROR_NONE;
  return RF_TRANSPORT_OK;
}

static int p7_p6_capabilities(rf_transport_backend_t *backend,
                              rf_transport_capabilities_t *capabilities) {
  (void)backend;
  capabilities->max_payload_bytes = RF_TRANSPORT_MAX_PAYLOAD_BYTES;
  capabilities->allowed_lane_mask = RF_TRANSPORT_ALLOWED_LANE_MASK;
  capabilities->queue_depth = 1U;
  capabilities->flags = 0U;
  return RF_TRANSPORT_OK;
}

static int p7_p6_wait_phy_ready(p7_p6_backend_context_t *context) {
  for (uint32_t poll = 0U; poll < P7_P6_MAX_POLLS; ++poll) {
    uint32_t status = 0U;
    if (p7_active_stop_requested(context->service)) return -1;
    if (ir_driver_p6_get_status(context->io, &status) != 0) return -2;
    if ((status & (P7_P6_STATUS_FAIL | P7_P6_STATUS_CONFIG_REJECTED |
                   P7_P6_STATUS_TIMEOUT)) != 0U) {
      return -3;
    }
    if ((status & P7_P6_STATUS_READY) != 0U) return 0;
  }
  return -4;
}

static void p7_p6_snapshot_and_shutdown(p7_p6_backend_context_t *context) {
  /* Preserve the live P6 failure/safety counters before shutdown changes the
   * register state.  The result remains evidence even when setup/start fails. */
  (void)ir_driver_p6_read_result(context->io, &context->p6);
  (void)p7_stop_and_shutdown(context->service);
}

static int p7_p6_submit(rf_transport_backend_t *backend,
                        const uint8_t *payload, size_t payload_size,
                        uint32_t lane_mask, uint32_t *token_out) {
  p7_p6_backend_context_t *context =
      (p7_p6_backend_context_t *)backend->context;
  ir_p6_payload_config_t config;
  volatile uint8_t *tx_readback =
      (volatile uint8_t *)(uintptr_t)P7_P6_TX_READBACK_BASEADDR;
  uint32_t observed_size = 0U;
  p7_mismatch_observation_t mismatch;
  if (payload_size == 0U || payload_size > RF_TRANSPORT_MAX_PAYLOAD_BYTES ||
      (lane_mask != 1U && lane_mask != 2U && lane_mask != 3U)) {
    return RF_TRANSPORT_ERR_ARGUMENT;
  }
  if (!p7_copy_bytes_verified(
          (volatile uint8_t *)context->tx_payload,
          (const volatile uint8_t *)payload, (uint32_t)payload_size,
          &mismatch)) {
    context->diagnostic_error = P7_ERROR_P6_TX_LOCAL_COPY;
    (void)p7_publish_first_error_diagnostic(
        context->service->mailbox, context->request,
        P7_FIRST_ERROR_STAGE_P6_TX_LOCAL, context->diagnostic_error,
        context->fragment_index, lane_mask,
        (const volatile uint8_t *)payload, (uint32_t)payload_size,
        (const volatile uint8_t *)context->tx_payload,
        (uint32_t)payload_size, &mismatch);
    (void)p7_stop_and_shutdown(context->service);
    return RF_TRANSPORT_ERR_IO;
  }
  context->tx_size = payload_size;
  context->rx_size = 0U;
  context->lane_mask = lane_mask;
  context->diagnostic_error = P7_ERROR_NONE;
  memset(&context->p6, 0, sizeof(context->p6));
  memset(&config, 0, sizeof(config));
  config.session = P7_P6_SESSION;
  config.lane_mask = lane_mask;
  config.ack_lane_mask = lane_mask;
  config.payload_len = (uint32_t)payload_size;
  config.pattern_id = 0U;
  config.seed = context->token + 1U;
  config.timeout_cycles = P7_P6_TIMEOUT_CYCLES;
  context->run_status = -1;
  if (!p7_runtime_has_budget(context->service,
                             P7_FRAGMENT_ADMISSION_GUARD_TICKS)) {
    context->run_status = -20;
    (void)p7_stop_and_shutdown(context->service);
  } else {
    context->service->shutdown_attempted = 0U;
    context->service->shutdown_status = -1;
  }
  if (context->run_status == -1 && ir_driver_p6_reset(context->io) != 0) {
    context->run_status = -2;
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1 &&
             ir_driver_p6_write_payload(context->io, context->tx_payload,
                                         config.payload_len) != 0) {
    context->run_status = -3;
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1) {
    memset((void *)tx_readback, 0xa5, P7_LOCAL_PAYLOAD_BYTES);
  }
  if (context->run_status == -1 &&
             ir_driver_p6_read_tx_payload(
                 context->io, (uint8_t *)tx_readback,
                 P7_LOCAL_PAYLOAD_BYTES, config.payload_len) != 0) {
    context->diagnostic_error = P7_ERROR_P6_TX_MMIO_READBACK;
    context->run_status = -13;
    (void)p7_publish_first_error_diagnostic(
        context->service->mailbox, context->request,
        P7_FIRST_ERROR_STAGE_P6_TX_MMIO_READBACK,
        context->diagnostic_error, context->fragment_index, lane_mask,
        (const volatile uint8_t *)context->tx_payload, config.payload_len,
        tx_readback, 0U, NULL);
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1 &&
             !p7_bytes_equal_volatile(
                  (const volatile uint8_t *)context->tx_payload, tx_readback,
                  config.payload_len, &mismatch)) {
    context->diagnostic_error = P7_ERROR_P6_TX_MMIO_READBACK;
    context->run_status = -13;
    (void)p7_publish_first_error_diagnostic(
        context->service->mailbox, context->request,
        P7_FIRST_ERROR_STAGE_P6_TX_MMIO_READBACK,
        context->diagnostic_error, context->fragment_index, lane_mask,
        (const volatile uint8_t *)context->tx_payload, config.payload_len,
        tx_readback, config.payload_len, &mismatch);
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1 &&
             ir_driver_p6_commit_payload(context->io, &config) != 0) {
    context->run_status = -4;
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1 &&
             p7_p6_wait_phy_ready(context) != 0) {
    context->run_status = -12;
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1 &&
             ir_driver_p6_start(context->io) != 0) {
    context->run_status = -5;
    p7_p6_snapshot_and_shutdown(context);
  } else if (context->run_status == -1) {
    uint32_t status = 0U;
    context->run_status = -6;
    for (uint32_t poll = 0U; poll < P7_P6_MAX_POLLS; ++poll) {
      if (p7_active_stop_requested(context->service)) {
        context->run_status = -7;
        break;
      }
      if (ir_driver_p6_get_status(context->io, &status) != 0) {
        context->run_status = -8;
        break;
      }
      if ((status & (P7_P6_STATUS_FAIL | P7_P6_STATUS_CONFIG_REJECTED |
                     P7_P6_STATUS_TIMEOUT)) != 0U) {
        context->run_status = -9;
        break;
      }
      if ((status & P7_P6_STATUS_DONE) != 0U &&
          (status & P7_P6_STATUS_BUSY) == 0U) {
        context->run_status = 0;
        break;
      }
    }
    (void)ir_driver_p6_read_result(context->io, &context->p6);
    if (context->run_status == 0) {
      if (ir_driver_p6_stop(context->io) != 0) {
        context->run_status = -10;
        (void)p7_stop_and_shutdown(context->service);
      }
    } else {
      (void)p7_stop_and_shutdown(context->service);
    }
  }
  if (context->run_status == 0) {
    if (ir_driver_p6_read_rx_payload(context->io, context->rx_payload,
                                     RF_APP_P6_MAX_PAYLOAD_BYTES,
                                     &observed_size) == 0) {
      context->rx_size = observed_size;
      p7_reset_mismatch(&mismatch);
      if (context->rx_size != context->tx_size ||
          !p7_bytes_equal_volatile(
              (const volatile uint8_t *)context->tx_payload,
              (const volatile uint8_t *)context->rx_payload,
               (uint32_t)(context->rx_size < context->tx_size
                              ? context->rx_size
                              : context->tx_size),
               &mismatch)) {
        context->diagnostic_error = P7_ERROR_P6_RX_LOCAL_MISMATCH;
        context->run_status = -14;
        (void)p7_publish_first_error_diagnostic(
            context->service->mailbox, context->request,
            P7_FIRST_ERROR_STAGE_P6_RX_LOCAL, context->diagnostic_error,
            context->fragment_index, lane_mask,
            (const volatile uint8_t *)context->tx_payload,
            (uint32_t)context->tx_size,
            (const volatile uint8_t *)context->rx_payload,
            (uint32_t)context->rx_size, &mismatch);
        (void)p7_stop_and_shutdown(context->service);
      }
    } else {
      context->diagnostic_error = P7_ERROR_P6_RX_LOCAL_MISMATCH;
      context->run_status = -14;
      (void)p7_publish_first_error_diagnostic(
          context->service->mailbox, context->request,
          P7_FIRST_ERROR_STAGE_P6_RX_LOCAL, context->diagnostic_error,
          context->fragment_index, lane_mask,
          (const volatile uint8_t *)context->tx_payload,
          (uint32_t)context->tx_size,
          (const volatile uint8_t *)context->rx_payload, 0U, NULL);
      (void)p7_stop_and_shutdown(context->service);
    }
  }
  context->token += 1U;
  *token_out = context->token;
  context->metrics.fragments_submitted += 1U;
  context->metrics.bytes_submitted += payload_size;
  context->metrics.retry_count += context->p6.retry_count;
  context->metrics.retry_exhausted += context->p6.retry_exhausted;
  context->metrics.tx_fail += context->p6.tx_fail;
  context->metrics.crc_bad += context->p6.crc_bad;
  context->metrics.payload_mismatch += context->p6.payload_mismatch;
  context->metrics.duty_violation_count += context->p6.duty_violation;
  if (context->p6.txd_high_consecutive_max >
      context->metrics.txd_high_consecutive_max) {
    context->metrics.txd_high_consecutive_max =
        context->p6.txd_high_consecutive_max;
  }
  return RF_TRANSPORT_OK;
}

static int p7_p6_poll(rf_transport_backend_t *backend, uint32_t token,
                      uint32_t max_polls,
                      rf_transport_fragment_result_t *result) {
  p7_p6_backend_context_t *context =
      (p7_p6_backend_context_t *)backend->context;
  (void)max_polls;
  if (token != context->token) return RF_TRANSPORT_ERR_STATE;
  memset(result, 0, sizeof(*result));
  result->token = token;
  result->lane_mask = context->lane_mask;
  result->payload_bytes = (uint32_t)context->rx_size;
  result->retry_count = context->p6.retry_count;
  result->retry_exhausted = context->p6.retry_exhausted;
  result->tx_fail = context->p6.tx_fail;
  result->crc_bad = context->p6.crc_bad;
  result->payload_mismatch = context->p6.payload_mismatch;
  result->txd_high_consecutive_max = context->p6.txd_high_consecutive_max;
  result->duty_violation_count = context->p6.duty_violation;
  /* The earliest local/MMIO boundary failure is the primary diagnosis.  A
   * later result-register snapshot must not replace its stage/error identity. */
  result->error_code = context->diagnostic_error;
  if (result->error_code == 0U) result->error_code = context->p6.error_code;
  if (result->error_code == 0U && context->p6.sticky_error != 0U) {
    result->error_code = P7_ERROR_P6_RESULT;
  }
  if (result->error_code == 0U && context->run_status != 0) {
    result->error_code =
        context->run_status == -20 || p7_runtime_expired(context->service)
            ? P7_ERROR_RUNTIME_LIMIT
            : (context->run_status == -7 ? P7_ERROR_ABORTED
                                         : P7_ERROR_P6_SUBMIT);
  }
  result->accepted = context->run_status == 0 &&
                     context->rx_size == context->tx_size &&
                     (context->p6.status & P7_P6_STATUS_DONE) != 0U &&
                     (context->p6.status &
                      (P7_P6_STATUS_BUSY | P7_P6_STATUS_FAIL |
                       P7_P6_STATUS_CONFIG_REJECTED |
                       P7_P6_STATUS_TIMEOUT)) == 0U &&
                     context->p6.error_code == 0U &&
                     context->p6.sticky_error == 0U &&
                     context->p6.tx_count != 0U &&
                     ((context->lane_mask & 1U) == 0U ||
                      context->p6.rx_good_count_l0 != 0U) &&
                     ((context->lane_mask & 2U) == 0U ||
                      context->p6.rx_good_count_l1 != 0U) &&
                     context->p6.retry_exhausted == 0U &&
                     context->p6.tx_fail == 0U && context->p6.crc_bad == 0U &&
                     context->p6.payload_mismatch == 0U &&
                     context->p6.duty_violation == 0U &&
                     context->p6.txd_high_consecutive_max <=
                         P7_KNOWN_GOOD_TXD_HIGH_CYCLES;
  if (result->accepted != 0U) {
    context->metrics.fragments_completed += 1U;
    context->metrics.bytes_completed += context->rx_size;
  } else {
    context->metrics.fragments_failed += 1U;
  }
  return RF_TRANSPORT_OK;
}

static int p7_p6_read(rf_transport_backend_t *backend, uint32_t token,
                      uint8_t *payload, size_t payload_capacity,
                      size_t *payload_size) {
  p7_p6_backend_context_t *context =
      (p7_p6_backend_context_t *)backend->context;
  p7_mismatch_observation_t mismatch;
  if (token != context->token || payload_capacity < context->rx_size) {
    return RF_TRANSPORT_ERR_BUFFER;
  }
  if (!p7_copy_bytes_verified(
          (volatile uint8_t *)payload,
          (const volatile uint8_t *)context->rx_payload,
          (uint32_t)context->rx_size, &mismatch)) {
    context->diagnostic_error = P7_ERROR_RECEIVED_INPUT_MISMATCH;
    (void)p7_publish_first_error_diagnostic(
        context->service->mailbox, context->request,
        P7_FIRST_ERROR_STAGE_RECEIVED, context->diagnostic_error,
        context->fragment_index, context->lane_mask,
        (const volatile uint8_t *)context->rx_payload,
        (uint32_t)context->rx_size, (const volatile uint8_t *)payload,
        (uint32_t)context->rx_size, &mismatch);
    (void)p7_stop_and_shutdown(context->service);
    return RF_TRANSPORT_ERR_IO;
  }
  *payload_size = context->rx_size;
  return RF_TRANSPORT_OK;
}

static int p7_p6_abort(rf_transport_backend_t *backend) {
  p7_p6_backend_context_t *context =
      (p7_p6_backend_context_t *)backend->context;
  return ir_driver_p6_stop(context->io) == 0 ? RF_TRANSPORT_OK
                                             : RF_TRANSPORT_ERR_IO;
}

static int p7_p6_close(rf_transport_backend_t *backend) {
  (void)backend;
  return RF_TRANSPORT_OK;
}

static int p7_p6_metrics(rf_transport_backend_t *backend,
                         rf_transport_metrics_t *metrics) {
  p7_p6_backend_context_t *context =
      (p7_p6_backend_context_t *)backend->context;
  *metrics = context->metrics;
  return RF_TRANSPORT_OK;
}

static const rf_transport_backend_ops_t p7_p6_ops = {
    p7_p6_open,  p7_p6_capabilities, p7_p6_submit, p7_p6_poll,
    p7_p6_read,  p7_p6_abort,        p7_p6_close,  p7_p6_metrics};

static int p7_range_valid(uint32_t address, uint32_t size) {
  uint64_t end = (uint64_t)address + (uint64_t)size;
  if ((address & (P7_DDR_ALIGNMENT - 1U)) != 0U) return 0;
  if (address < P7_DDR_BASEADDR || end > P7_DDR_END_EXCLUSIVE ||
      end < address) {
    return 0;
  }
  return 1;
}

static int p7_ranges_overlap(uint32_t a_address, uint32_t a_size,
                             uint32_t b_address, uint32_t b_size) {
  uint64_t a_end = (uint64_t)a_address + a_size;
  uint64_t b_end = (uint64_t)b_address + b_size;
  return a_size != 0U && b_size != 0U && a_address < b_end &&
         b_address < a_end;
}

static uint32_t p7_publish_failure_snapshot_diagnostic(
    volatile p7_mailbox_control_t *mailbox, uint32_t status,
    uint32_t address, uint32_t bytes, uint32_t magic_readback) {
  mailbox->failure_snapshot_address = address;
  mailbox->failure_snapshot_bytes = bytes;
  mailbox->failure_snapshot_magic_readback = magic_readback;
  dmb();
  mailbox->failure_snapshot_status = status;
  dmb();
  p7_flush(mailbox, sizeof(*mailbox));
  return status;
}

static uint32_t p7_publish_integrity_failure_snapshot(
    volatile p7_mailbox_control_t *mailbox,
    const p7_object_descriptor_t *request, const uint8_t *snapshot,
    uint32_t captured_length, uint32_t output_crc,
    const uint8_t output_sha[32], uint32_t error_code) {
  const uint32_t address = P7_FAILURE_SNAPSHOT_BASEADDR;
  const uint32_t total_bytes = P7_FAILURE_SNAPSHOT_TOTAL_BYTES;
  uint32_t magic_readback;
  p7_failure_snapshot_header_t header;
  volatile p7_failure_snapshot_header_t *published;
  uint8_t *published_data;
  if (snapshot == NULL)
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_NULL_SNAPSHOT, 0U, 0U, 0U);
  if (output_sha == NULL)
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_NULL_SHA256, 0U, 0U, 0U);
  if (captured_length == 0U)
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_ZERO_LENGTH, 0U, 0U, 0U);
  if (captured_length > P7_FAILURE_SNAPSHOT_MAX_BYTES)
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_LENGTH_LIMIT, 0U, captured_length,
        0U);
  memset(&header, 0, sizeof(header));
  header.version = P7_RUNTIME_VERSION;
  header.session_epoch = request->session_epoch;
  header.object_id = request->object_id;
  header.object_length = request->object_length;
  header.captured_length = captured_length;
  header.output_crc32 = output_crc;
  header.error_code = error_code;
  p7_copy_digest_words(header.output_sha256, output_sha);
  published =
      (volatile p7_failure_snapshot_header_t *)(uintptr_t)address;
  published_data = (uint8_t *)(uintptr_t)(address + sizeof(header));
  memcpy((void *)published, &header, sizeof(header));
  memset(published_data, 0, P7_FAILURE_SNAPSHOT_MAX_BYTES);
  memcpy(published_data, snapshot, captured_length);
  p7_flush((const void *)(uintptr_t)address, total_bytes);
  Xil_Out32(address, P7_FAILURE_SNAPSHOT_MAGIC);
  dsb();
  p7_flush(&published->magic, sizeof(published->magic));
  dsb();
  magic_readback = Xil_In32(address);
  if (magic_readback != P7_FAILURE_SNAPSHOT_MAGIC)
    return p7_publish_failure_snapshot_diagnostic(
        mailbox, P7_FAILURE_SNAPSHOT_STATUS_MARKER_READBACK_FAILED, address,
        total_bytes, magic_readback);
  return p7_publish_failure_snapshot_diagnostic(
      mailbox, P7_FAILURE_SNAPSHOT_STATUS_PUBLISHED, address, total_bytes,
      magic_readback);
}

static uint32_t p7_preferred_lane(uint32_t policy, uint32_t index) {
  if (policy == RF_APP_LANE_POLICY_LANE0_ONLY) return 1U;
  if (policy == RF_APP_LANE_POLICY_LANE1_ONLY) return 2U;
  if (policy == RF_APP_LANE_POLICY_STRIPE_ROUND_ROBIN) {
    return (index & 1U) == 0U ? 1U : 2U;
  }
  if (policy == RF_APP_LANE_POLICY_REPLICATE_0X3) return 3U;
  return 0U;
}

static uint32_t p7_select_lane(uint32_t policy, uint32_t preferred,
                               uint32_t unavailable) {
  uint32_t usable = preferred & (~unavailable) & 3U;
  if (usable != 0U) return usable;
  if (policy == RF_APP_LANE_POLICY_STRIPE_ROUND_ROBIN && preferred == 1U &&
      (unavailable & 2U) == 0U) {
    return 2U;
  }
  if (policy == RF_APP_LANE_POLICY_STRIPE_ROUND_ROBIN && preferred == 2U &&
      (unavailable & 1U) == 0U) {
    return 1U;
  }
  if (policy == RF_APP_LANE_POLICY_REPLICATE_0X3 && preferred == 3U) {
    if ((unavailable & 1U) == 0U) {
      return 1U;
    }
    if ((unavailable & 2U) == 0U) {
      return 2U;
    }
  }
  return 0U;
}

static void p7_publish_descriptor(volatile p7_object_descriptor_t *descriptor,
                                  uint32_t status) {
  descriptor->status = P7_DESCRIPTOR_RUNNING;
  p7_flush(descriptor, sizeof(*descriptor));
  descriptor->status = status;
  p7_flush(&descriptor->status, sizeof(descriptor->status));
}

static void p7_publish_mailbox(volatile p7_mailbox_control_t *mailbox) {
  p7_flush(mailbox, sizeof(*mailbox));
}

static void p7_assign_terminal_sequence(
    volatile p7_mailbox_control_t *mailbox,
    volatile p7_object_descriptor_t *descriptor) {
  mailbox->completion_sequence += 1U;
  descriptor->completion_sequence = mailbox->completion_sequence;
}

static void p7_reset_descriptor_results(
    volatile p7_object_descriptor_t *descriptor) {
  descriptor->error_code = P7_ERROR_NONE;
  descriptor->bytes_completed = 0U;
  descriptor->fragments_total = 0U;
  descriptor->fragments_completed = 0U;
  descriptor->output_crc32 = 0U;
  descriptor->fragment_attempts = 0U;
  descriptor->fallback_count = 0U;
  for (uint32_t index = 0U; index < 8U; ++index) {
    descriptor->input_sha256[index] = 0U;
    descriptor->output_sha256[index] = 0U;
  }
  descriptor->p6_retry_count = 0U;
  descriptor->p6_retry_exhausted = 0U;
  descriptor->p6_tx_fail = 0U;
  descriptor->p6_crc_bad = 0U;
  descriptor->p6_payload_mismatch = 0U;
  descriptor->max_txd_high_cycles = 0U;
  descriptor->duty_violation_count = 0U;
  descriptor->lane0_fragments = 0U;
  descriptor->lane1_fragments = 0U;
  descriptor->replicated_fragments = 0U;
  descriptor->start_ticks_low = 0U;
  descriptor->start_ticks_high = 0U;
  descriptor->end_ticks_low = 0U;
  descriptor->end_ticks_high = 0U;
}

static void p7_wipe_partial(const p7_object_descriptor_t *request,
                            uint32_t completed,
                            volatile p7_object_descriptor_t *descriptor) {
  if (completed > request->object_length) completed = request->object_length;
  /* The output file is prefilled with a nonzero canary.  A terminal failure
   * must erase the entire privately validated output range, including bytes
   * that were never reached, so the host cannot mistake an unwritten canary
   * for application data or a partial commit. */
  if (request->object_length != 0U &&
      request->object_length <= P7_MAX_OBJECT_BYTES &&
      p7_range_valid(request->output_address, request->object_length)) {
    uint8_t *output = (uint8_t *)(uintptr_t)request->output_address;
    memset(output, 0, request->object_length);
    p7_flush(output, request->object_length);
  }
  (void)completed;
  descriptor->bytes_completed = 0U;
}

static int p7_validate_descriptor(
    const p7_object_descriptor_t *request,
    const p7_service_context_t *service, uint16_t *fragment_count) {
  uint32_t trace_bytes;
  if (request->magic != P7_DESCRIPTOR_MAGIC ||
      request->version != P7_RUNTIME_VERSION ||
      request->command != P7_DESCRIPTOR_COMMAND_TRANSFER ||
      request->status != P7_DESCRIPTOR_READY) {
    return P7_ERROR_DESCRIPTOR;
  }
  if (request->object_length > P7_MAX_OBJECT_BYTES) {
    return P7_ERROR_OBJECT_TOO_LARGE;
  }
  if (!p7_range_valid(request->input_address, request->object_length) ||
      !p7_range_valid(request->output_address, request->object_length)) {
    return P7_ERROR_ADDRESS;
  }
  if (p7_ranges_overlap(request->input_address, request->object_length,
                        request->output_address, request->object_length)) {
    return P7_ERROR_OVERLAP;
  }
  if (request->lane_policy < RF_APP_LANE_POLICY_LANE0_ONLY ||
      request->lane_policy > RF_APP_LANE_POLICY_REPLICATE_0X3 ||
      (request->unavailable_lane_mask & ~3U) != 0U ||
      request->max_retries > P7_MAX_P6_RETRY_ACCEPTANCE) {
    return P7_ERROR_LANE_POLICY;
  }
  if (rf_app_fragment_count(request->object_length, fragment_count) !=
      RF_APP_OK) {
    return P7_ERROR_FRAGMENT_GEOMETRY;
  }
  if (request->trace_capacity != 0U) {
    if (request->trace_capacity < *fragment_count ||
        request->trace_capacity >
            (P7_MAX_OBJECT_BYTES / sizeof(p7_fragment_trace_t))) {
      return P7_ERROR_TRACE_RANGE;
    }
    trace_bytes = request->trace_capacity * sizeof(p7_fragment_trace_t);
    if (!p7_range_valid(request->trace_address, trace_bytes) ||
        p7_ranges_overlap(request->trace_address, trace_bytes,
                          request->input_address, request->object_length) ||
        p7_ranges_overlap(request->trace_address, trace_bytes,
                          request->output_address, request->object_length)) {
      return P7_ERROR_TRACE_RANGE;
    }
  }
  if (service->identity_valid != 0U &&
      request->session_epoch < service->current_epoch) {
    return P7_ERROR_STALE_SESSION;
  }
  if (service->require_new_epoch != 0U && service->identity_valid != 0U &&
      request->session_epoch <= service->current_epoch) {
    return P7_ERROR_STALE_SESSION;
  }
  if (service->identity_valid != 0U &&
      request->session_epoch == service->current_epoch &&
      request->object_id <= service->last_object_id) {
    return P7_ERROR_OBJECT_ID_COLLISION;
  }
  return P7_ERROR_NONE;
}

static void p7_record_trace(const p7_object_descriptor_t *request,
                            uint32_t fragment_index, uint32_t fragment_count,
                            uint32_t lane_mask, uint32_t attempts,
                            const rf_transport_fragment_result_t *result,
                            uint64_t start, uint64_t end) {
  if (request->trace_capacity == 0U ||
      fragment_index >= request->trace_capacity) {
    return;
  }
  p7_fragment_trace_t *trace =
      &((p7_fragment_trace_t *)(uintptr_t)request->trace_address)
           [fragment_index];
  memset(trace, 0, sizeof(*trace));
  trace->magic = P7_TRACE_MAGIC;
  trace->session_epoch = request->session_epoch;
  trace->object_id = request->object_id;
  trace->fragment_index_count =
      (fragment_count << 16) | (fragment_index & UINT32_C(0xffff));
  trace->lane_mask = lane_mask;
  trace->attempt_count = attempts;
  trace->result = result->accepted;
  trace->error_code = result->error_code;
  trace->start_ticks_low = (uint32_t)start;
  trace->start_ticks_high = (uint32_t)(start >> 32);
  trace->end_ticks_low = (uint32_t)end;
  trace->end_ticks_high = (uint32_t)(end >> 32);
  trace->p6_retry_count = result->retry_count;
  trace->p6_retry_exhausted = result->retry_exhausted;
  trace->p6_tx_fail = result->tx_fail;
  trace->p6_error_code = result->error_code;
  p7_flush(trace, sizeof(*trace));
}

static int p7_process_descriptor(
    p7_service_context_t *service,
    volatile p7_object_descriptor_t *descriptor) {
  const ir_mmio_t *io = service->io;
  volatile p7_mailbox_control_t *mailbox = service->mailbox;
  p7_object_descriptor_t request;
  p7_p6_backend_context_t backend_context;
  rf_transport_backend_t backend;
  rf_transport_capabilities_t capabilities;
  volatile uint8_t *input_reference =
      (volatile uint8_t *)(uintptr_t)P7_INPUT_REFERENCE_BASEADDR;
  uint16_t fragment_count = 0U;
  uint8_t input_sha[32];
  uint8_t output_sha[32];
  uint8_t output_snapshot[P7_FAILURE_SNAPSHOT_MAX_BYTES]
      __attribute__((aligned(64)));
  uint32_t output_snapshot_length = 0U;
  uint32_t input_crc;
  uint32_t output_crc;
  uint32_t completed_bytes = 0U;
  uint32_t sticky_unavailable = 0U;
  uint32_t fallback_reported_mask = 0U;
  p7_mismatch_observation_t end_to_end_mismatch;
  uint64_t object_start;
  uint64_t object_end;
  int end_to_end_status;
  int error;

  p7_invalidate(descriptor, sizeof(*descriptor));
  memcpy(&request, (const void *)descriptor, sizeof(request));
  error = p7_validate_descriptor(&request, service, &fragment_count);
  p7_reset_descriptor_results(descriptor);
  if (error != P7_ERROR_NONE) {
    (void)p7_stop_and_shutdown(service);
    /* The rejected descriptor has not established a private, nonoverlapping
     * output range.  Never write through an unvalidated output address. */
    descriptor->error_code = (uint32_t)error;
    mailbox->objects_failed += 1U;
    mailbox->last_error_code = (uint32_t)error;
    mailbox->service_state = P7_SERVICE_STOPPED;
    service->fault_latched = 1U;
    p7_assign_terminal_sequence(mailbox, descriptor);
    p7_publish_descriptor(descriptor, P7_DESCRIPTOR_REJECTED);
    p7_publish_mailbox(mailbox);
    return error;
  }
  service->shutdown_attempted = 0U;
  service->shutdown_status = -1;
  descriptor->fragments_total = fragment_count;
  descriptor->status = P7_DESCRIPTOR_RUNNING;
  object_start = p7_get_ticks();
  p7_split_ticks(object_start, &descriptor->start_ticks_low,
                 &descriptor->start_ticks_high);
  p7_flush(descriptor, sizeof(*descriptor));
  mailbox->objects_requested += 1U;
  mailbox->service_state = P7_SERVICE_RUNNING;
  if (service->identity_valid != 0U &&
      request.session_epoch != service->current_epoch) {
    mailbox->restart_count += 1U;
  }
  service->identity_valid = 1U;
  service->current_epoch = request.session_epoch;
  service->last_object_id = request.object_id;
  service->require_new_epoch = 0U;
  mailbox->current_session_epoch = request.session_epoch;
  mailbox->current_object_id = request.object_id;
  p7_publish_mailbox(mailbox);
  p7_invalidate((const void *)(uintptr_t)request.input_address,
                request.object_length);
  if (!p7_integrity_checked(
          service, (const uint8_t *)(uintptr_t)request.input_address,
          request.object_length, &input_crc, input_sha, NULL, NULL)) {
    error = p7_runtime_expired(service) ? P7_ERROR_RUNTIME_LIMIT
                                        : P7_ERROR_ABORTED;
    goto failed;
  }
  p7_copy_digest_words(descriptor->input_sha256, input_sha);
  if (input_crc != request.expected_crc32) {
    error = P7_ERROR_OBJECT_CRC;
    goto failed;
  }
  if (!p7_digest_matches_words(input_sha, request.expected_sha256)) {
    error = P7_ERROR_OBJECT_SHA256;
    goto failed;
  }

  memset(&backend_context, 0, sizeof(backend_context));
  backend_context.io = io;
  backend_context.service = service;
  backend.ops = &p7_p6_ops;
  backend.context = &backend_context;
  if (rf_transport_open(&backend) != RF_TRANSPORT_OK ||
      rf_transport_get_capabilities(&backend, &capabilities) !=
          RF_TRANSPORT_OK ||
      capabilities.max_payload_bytes != RF_APP_P6_MAX_PAYLOAD_BYTES ||
      capabilities.allowed_lane_mask != 3U) {
    error = P7_ERROR_P6_SUBMIT;
    goto failed;
  }
  for (uint32_t fragment_index = 0U; fragment_index < fragment_count;
       ++fragment_index) {
    uint32_t offset = fragment_index * RF_APP_MAX_CHUNK_BYTES;
    uint32_t remaining = request.object_length - offset;
    uint32_t chunk_length = remaining > RF_APP_MAX_CHUNK_BYTES
                                ? RF_APP_MAX_CHUNK_BYTES
                                : remaining;
    uint32_t flags = (fragment_index == 0U ? RF_APP_FLAG_FIRST : 0U) |
                     (fragment_index + 1U == fragment_count
                          ? RF_APP_FLAG_LAST
                          : 0U);
    rf_app_header_t header;
    uint8_t encoded[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)));
    uint8_t received[P7_LOCAL_PAYLOAD_BYTES] __attribute__((aligned(64)));
    size_t encoded_size = 0U;
    size_t received_size = 0U;
    uint32_t injected_unavailable =
        fragment_index >= request.unavailable_after_fragment
            ? request.unavailable_lane_mask
            : 0U;
    uint32_t preferred =
        p7_preferred_lane(request.lane_policy, fragment_index);
    uint32_t lane;
    uint32_t token = 0U;
    uint32_t attempts = 1U;
    p7_mismatch_observation_t mismatch;
    rf_transport_fragment_result_t result;
    uint64_t fragment_start;
    uint64_t fragment_end;
    int fragment_ok = 0;

    sticky_unavailable |= injected_unavailable;
    lane = p7_select_lane(request.lane_policy, preferred,
                          sticky_unavailable);
    if ((request.lane_policy == RF_APP_LANE_POLICY_STRIPE_ROUND_ROBIN ||
         request.lane_policy == RF_APP_LANE_POLICY_REPLICATE_0X3) &&
        lane != 0U && lane != preferred) {
      uint32_t newly_reported =
          (preferred & sticky_unavailable) & ~fallback_reported_mask;
      descriptor->fallback_count +=
          ((newly_reported & 1U) != 0U ? 1U : 0U) +
          ((newly_reported & 2U) != 0U ? 1U : 0U);
      fallback_reported_mask |= newly_reported;
    }
    if (p7_active_stop_requested(service) ||
        fragment_index == request.abort_after_fragment) {
      error = p7_runtime_expired(service) ? P7_ERROR_RUNTIME_LIMIT
                                          : P7_ERROR_ABORTED;
      (void)rf_transport_abort(&backend);
      goto failed;
    }
    if (lane == 0U) {
      error = P7_ERROR_ALL_LANES_UNAVAILABLE;
      goto failed;
    }
    if (!p7_runtime_has_budget(service,
                               P7_FRAGMENT_ADMISSION_GUARD_TICKS)) {
      error = P7_ERROR_RUNTIME_LIMIT;
      goto failed;
    }
    memset(&header, 0, sizeof(header));
    header.session_epoch = request.session_epoch;
    header.object_id = request.object_id;
    header.total_length = request.object_length;
    header.fragment_index = (uint16_t)fragment_index;
    header.fragment_count = fragment_count;
    header.chunk_length = (uint16_t)chunk_length;
    header.object_crc32 = request.expected_crc32;
    header.flags = (uint8_t)flags;
    backend_context.request = &request;
    backend_context.fragment_index = fragment_index;
    if (chunk_length != 0U) {
      p7_invalidate(
          (const void *)(uintptr_t)(request.input_address + offset),
          chunk_length);
      memset((void *)input_reference, 0, P7_LOCAL_PAYLOAD_BYTES);
      if (!p7_copy_bytes_verified(
              input_reference,
              (const volatile uint8_t *)(uintptr_t)(request.input_address +
                                                     offset),
              chunk_length, &mismatch)) {
        error = P7_ERROR_INPUT_REFERENCE_COPY;
        (void)p7_publish_first_error_diagnostic(
            mailbox, &request, P7_FIRST_ERROR_STAGE_INPUT_REF,
            (uint32_t)error, fragment_index, lane,
            (const volatile uint8_t *)(uintptr_t)(request.input_address +
                                                   offset),
            chunk_length, input_reference, chunk_length, &mismatch);
        goto failed;
      }
    }
    if (rf_app_encode_fragment(
            &header,
            (const uint8_t *)(uintptr_t)(request.input_address + offset),
            chunk_length, encoded, RF_APP_P6_MAX_PAYLOAD_BYTES,
            &encoded_size) !=
        RF_APP_OK) {
      error = P7_ERROR_FRAGMENT_GEOMETRY;
      goto failed;
    }
    if (chunk_length != 0U) {
      if (!p7_bytes_equal_volatile(
              input_reference,
              (const volatile uint8_t *)(encoded + RF_APP_HEADER_BYTES),
              chunk_length, &mismatch)) {
        error = P7_ERROR_ENCODE_RAW_MISMATCH;
        (void)p7_publish_first_error_diagnostic(
            mailbox, &request, P7_FIRST_ERROR_STAGE_ENCODE_RAW,
            (uint32_t)error, fragment_index, lane, input_reference,
            chunk_length,
            (const volatile uint8_t *)(encoded + RF_APP_HEADER_BYTES),
            chunk_length, &mismatch);
        goto failed;
      }
      /* Preserve the verified byte-copy hardening, but only after the raw
       * encoder observation above has proved that it is not hiding the first
       * corruption boundary. */
      if (!p7_copy_bytes_verified(
              (volatile uint8_t *)(encoded + RF_APP_HEADER_BYTES),
              input_reference, chunk_length, &mismatch)) {
        error = P7_ERROR_FRAGMENT_ENCODE_COPY;
        (void)p7_publish_first_error_diagnostic(
            mailbox, &request, P7_FIRST_ERROR_STAGE_ENCODE_REPAIR,
            (uint32_t)error, fragment_index, lane, input_reference,
            chunk_length,
            (const volatile uint8_t *)(encoded + RF_APP_HEADER_BYTES),
            chunk_length, &mismatch);
        goto failed;
      }
    }
    fragment_start = p7_get_ticks();
    memset(&result, 0, sizeof(result));
    descriptor->fragment_attempts += 1U;
    if (rf_transport_submit_fragment(&backend, encoded, encoded_size, lane,
                                     &token) != RF_TRANSPORT_OK) {
      result.accepted = 0U;
      result.error_code = backend_context.diagnostic_error != P7_ERROR_NONE
                              ? backend_context.diagnostic_error
                              : P7_ERROR_P6_SUBMIT;
    } else if (rf_transport_poll_fragment_result(
                   &backend, token, P7_P6_MAX_POLLS, &result) !=
               RF_TRANSPORT_OK) {
      result.accepted = 0U;
      result.error_code = P7_ERROR_P6_SUBMIT;
    }
    descriptor->p6_retry_count += result.retry_count;
    descriptor->p6_retry_exhausted += result.retry_exhausted;
    descriptor->p6_tx_fail += result.tx_fail;
    descriptor->p6_crc_bad += result.crc_bad;
    descriptor->p6_payload_mismatch += result.payload_mismatch;
    descriptor->duty_violation_count += result.duty_violation_count;
    if (result.txd_high_consecutive_max >
        descriptor->max_txd_high_cycles) {
      descriptor->max_txd_high_cycles = result.txd_high_consecutive_max;
    }
    /* P6 owns physical ARQ.  max_retries is the fail-closed per-fragment
     * acceptance cap for those visible P6 retries; P7 never replays a
     * safety-significant failure at the application layer. */
    if (result.retry_count > request.max_retries) {
      result.accepted = 0U;
      if (result.error_code == 0U) result.error_code = P7_ERROR_P6_RESULT;
    }
    fragment_ok = result.accepted != 0U;
    fragment_end = p7_get_ticks();
    if (!fragment_ok) {
      if (result.error_code == P7_ERROR_RUNTIME_LIMIT) {
        error = P7_ERROR_RUNTIME_LIMIT;
      } else if (result.error_code == P7_ERROR_ABORTED) {
        error = P7_ERROR_ABORTED;
      } else if (p7_active_stop_requested(service)) {
        error = p7_runtime_expired(service) ? P7_ERROR_RUNTIME_LIMIT
                                            : P7_ERROR_ABORTED;
      } else if (result.error_code >= P7_ERROR_P6_TX_LOCAL_COPY &&
                 result.error_code <= P7_ERROR_P6_RX_LOCAL_MISMATCH) {
        error = (int)result.error_code;
      } else {
        error = P7_ERROR_P6_RESULT;
      }
      result.accepted = 0U;
      if (result.error_code == 0U) result.error_code = (uint32_t)error;
      p7_record_trace(&request, fragment_index, fragment_count, lane,
                      attempts,
                      &result, fragment_start, fragment_end);
      goto failed;
    }
    {
      int read_status = rf_transport_read_fragment(
          &backend, token, received, RF_APP_P6_MAX_PAYLOAD_BYTES,
          &received_size);
      p7_reset_mismatch(&mismatch);
      int received_matches =
          read_status == RF_TRANSPORT_OK && received_size == encoded_size &&
          p7_bytes_equal_volatile(
              (const volatile uint8_t *)encoded,
              (const volatile uint8_t *)received, (uint32_t)encoded_size,
              &mismatch);
      if (!received_matches) {
        error = backend_context.diagnostic_error != P7_ERROR_NONE
                    ? (int)backend_context.diagnostic_error
                    : (received_size == encoded_size
                           ? P7_ERROR_FRAGMENT_TRANSFER_COPY
                           : P7_ERROR_FRAGMENT_MISMATCH);
        if (backend_context.diagnostic_error == P7_ERROR_NONE &&
            read_status == RF_TRANSPORT_OK) {
          (void)p7_publish_first_error_diagnostic(
              mailbox, &request, P7_FIRST_ERROR_STAGE_RECEIVED,
              (uint32_t)error, fragment_index, lane,
              (const volatile uint8_t *)encoded, (uint32_t)encoded_size,
              (const volatile uint8_t *)received, (uint32_t)received_size,
              &mismatch);
        }
        result.accepted = 0U;
        result.error_code = (uint32_t)error;
        p7_record_trace(&request, fragment_index, fragment_count, lane,
                        attempts, &result, fragment_start, fragment_end);
        goto failed;
      }
    }
    {
      rf_app_fragment_view_t view;
      if (rf_app_decode_fragment(received, received_size, &view) != RF_APP_OK ||
          view.header.session_epoch != request.session_epoch ||
          view.header.object_id != request.object_id ||
          view.header.fragment_index != fragment_index ||
          view.header.fragment_count != fragment_count ||
          view.header.total_length != request.object_length ||
          view.header.object_crc32 != request.expected_crc32 ||
          view.chunk_size != chunk_length) {
        error = P7_ERROR_FRAGMENT_MISMATCH;
        result.accepted = 0U;
        result.error_code = (uint32_t)error;
        p7_record_trace(&request, fragment_index, fragment_count, lane,
                        attempts, &result, fragment_start,
                        fragment_end);
        goto failed;
      }
      if (chunk_length != 0U &&
          !p7_bytes_equal_volatile(
              input_reference, (const volatile uint8_t *)view.chunk,
              chunk_length, &mismatch)) {
        error = P7_ERROR_RECEIVED_INPUT_MISMATCH;
        (void)p7_publish_first_error_diagnostic(
            mailbox, &request, P7_FIRST_ERROR_STAGE_RECEIVED,
            (uint32_t)error, fragment_index, lane, input_reference,
            chunk_length, (const volatile uint8_t *)view.chunk,
            chunk_length, &mismatch);
        result.accepted = 0U;
        result.error_code = (uint32_t)error;
        p7_record_trace(&request, fragment_index, fragment_count, lane,
                        attempts, &result, fragment_start, fragment_end);
        goto failed;
      }
      if (chunk_length != 0U) {
        if (!p7_copy_bytes_verified(
                (volatile uint8_t *)(uintptr_t)(request.output_address +
                                                offset),
                (const volatile uint8_t *)view.chunk, chunk_length,
                &mismatch)) {
          error = P7_ERROR_OUTPUT_COPY;
          (void)p7_publish_first_error_diagnostic(
              mailbox, &request,
              P7_FIRST_ERROR_STAGE_DDR_OUTPUT_IMMEDIATE_READBACK,
              (uint32_t)error, fragment_index, lane, input_reference,
              chunk_length,
              (const volatile uint8_t *)(uintptr_t)(request.output_address +
                                                     offset),
              chunk_length, &mismatch);
          result.accepted = 0U;
          result.error_code = (uint32_t)error;
          completed_bytes = offset + chunk_length;
          p7_record_trace(&request, fragment_index, fragment_count, lane,
                          attempts, &result, fragment_start, fragment_end);
          goto failed;
        }
        if (!p7_bytes_equal_volatile(
                input_reference,
                (const volatile uint8_t *)(uintptr_t)(request.output_address +
                                                       offset),
                chunk_length, &mismatch)) {
          error = P7_ERROR_DDR_OUTPUT_IMMEDIATE_READBACK;
          (void)p7_publish_first_error_diagnostic(
              mailbox, &request,
              P7_FIRST_ERROR_STAGE_DDR_OUTPUT_IMMEDIATE_READBACK,
              (uint32_t)error, fragment_index, lane, input_reference,
              chunk_length,
              (const volatile uint8_t *)(uintptr_t)(request.output_address +
                                                     offset),
              chunk_length, &mismatch);
          result.accepted = 0U;
          result.error_code = (uint32_t)error;
          completed_bytes = offset + chunk_length;
          p7_record_trace(&request, fragment_index, fragment_count, lane,
                          attempts, &result, fragment_start, fragment_end);
          goto failed;
        }
      }
    }
    p7_record_trace(&request, fragment_index, fragment_count, lane,
                    attempts, &result, fragment_start, fragment_end);
    completed_bytes += chunk_length;
    descriptor->bytes_completed = completed_bytes;
    descriptor->fragments_completed += 1U;
    mailbox->fragments_completed += 1U;
    mailbox->current_fragment_index = fragment_index;
    if ((lane & 1U) != 0U) descriptor->lane0_fragments += 1U;
    if ((lane & 2U) != 0U) descriptor->lane1_fragments += 1U;
    if (lane == 3U) descriptor->replicated_fragments += 1U;
    p7_flush(descriptor, sizeof(*descriptor));
    p7_publish_mailbox(mailbox);
  }

  (void)rf_transport_close(&backend);
  p7_flush((const void *)(uintptr_t)request.output_address,
           request.object_length);
  if (!p7_integrity_checked(
          service, (const uint8_t *)(uintptr_t)request.output_address,
          request.object_length, &output_crc, output_sha, output_snapshot,
          &output_snapshot_length)) {
    error = p7_runtime_expired(service) ? P7_ERROR_RUNTIME_LIMIT
                                        : P7_ERROR_ABORTED;
    goto failed;
  }
  descriptor->output_crc32 = output_crc;
  p7_copy_digest_words(descriptor->output_sha256, output_sha);
  end_to_end_status = p7_compare_object_checked(
      service,
      (const volatile uint8_t *)(uintptr_t)request.input_address,
      (const volatile uint8_t *)(uintptr_t)request.output_address,
      request.object_length, &end_to_end_mismatch);
  if (end_to_end_status < 0) {
    error = p7_runtime_expired(service) ? P7_ERROR_RUNTIME_LIMIT
                                        : P7_ERROR_ABORTED;
    goto failed;
  }
  if (end_to_end_status == 0) {
    error = P7_ERROR_DDR_OUTPUT_END_TO_END;
    (void)p7_publish_first_error_diagnostic(
        mailbox, &request, P7_FIRST_ERROR_STAGE_DDR_OUTPUT_END_TO_END,
        (uint32_t)error, P7_DIAGNOSTIC_NOT_APPLICABLE, 0U,
        (const volatile uint8_t *)(uintptr_t)request.input_address,
        request.object_length,
        (const volatile uint8_t *)(uintptr_t)request.output_address,
        request.object_length, &end_to_end_mismatch);
    goto failed;
  }
  if (descriptor->fragments_completed != fragment_count ||
      descriptor->bytes_completed != request.object_length ||
      output_crc != request.expected_crc32) {
    error = P7_ERROR_OBJECT_CRC;
    (void)p7_publish_integrity_failure_snapshot(
        mailbox, &request, output_snapshot, output_snapshot_length,
        output_crc, output_sha, (uint32_t)error);
    goto failed;
  }
  if (!p7_digest_matches_words(output_sha, request.expected_sha256)) {
    error = P7_ERROR_OBJECT_SHA256;
    (void)p7_publish_integrity_failure_snapshot(
        mailbox, &request, output_snapshot, output_snapshot_length,
        output_crc, output_sha, (uint32_t)error);
    goto failed;
  }
  object_end = p7_get_ticks();
  p7_split_ticks(object_end, &descriptor->end_ticks_low,
                 &descriptor->end_ticks_high);
  mailbox->objects_completed += 1U;
  mailbox->bytes_completed_low += request.object_length;
  if (mailbox->bytes_completed_low < request.object_length) {
    mailbox->bytes_completed_high += 1U;
  }
  mailbox->last_error_code = P7_ERROR_NONE;
  p7_assign_terminal_sequence(mailbox, descriptor);
  p7_publish_descriptor(descriptor, P7_DESCRIPTOR_COMPLETE);
  mailbox->service_state = P7_SERVICE_READY;
  p7_publish_mailbox(mailbox);
  return P7_ERROR_NONE;

failed:
  (void)p7_stop_and_shutdown(service);
  p7_wipe_partial(&request, completed_bytes, descriptor);
  descriptor->error_code = (uint32_t)error;
  object_end = p7_get_ticks();
  p7_split_ticks(object_end, &descriptor->end_ticks_low,
                 &descriptor->end_ticks_high);
  mailbox->objects_failed += 1U;
  mailbox->last_error_code = (uint32_t)error;
  if (error == P7_ERROR_ABORTED) {
    mailbox->abort_count += 1U;
    if (p7_control_command(service) == P7_CONTROL_ABORT) {
      service->abort_command_counted = 1U;
    }
  }
  service->require_new_epoch = 1U;
  service->fault_latched = 1U;
  p7_assign_terminal_sequence(mailbox, descriptor);
  p7_publish_descriptor(
      descriptor,
      error == P7_ERROR_ABORTED ? P7_DESCRIPTOR_ABORTED
                                : P7_DESCRIPTOR_FAILED);
  mailbox->service_state = P7_SERVICE_STOPPED;
  p7_publish_mailbox(mailbox);
  return error;
}

static uint32_t p7_queue_occupancy(
    volatile p7_object_descriptor_t *descriptors, uint32_t queue_depth) {
  uint32_t occupancy = 0U;
  for (uint32_t index = 0U; index < queue_depth; ++index) {
    p7_invalidate(&descriptors[index].status,
                  sizeof(descriptors[index].status));
    if (descriptors[index].status != P7_DESCRIPTOR_FREE) {
      occupancy += 1U;
    }
  }
  return occupancy;
}

static void p7_abort_ready(volatile p7_mailbox_control_t *mailbox,
                           volatile p7_object_descriptor_t *descriptors,
                           uint32_t queue_depth) {
  for (uint32_t index = 0U; index < queue_depth; ++index) {
    p7_invalidate(&descriptors[index], sizeof(descriptors[index]));
    if (descriptors[index].status == P7_DESCRIPTOR_READY) {
      p7_reset_descriptor_results(&descriptors[index]);
      descriptors[index].error_code = P7_ERROR_ABORTED;
      p7_assign_terminal_sequence(mailbox, &descriptors[index]);
      p7_publish_descriptor(&descriptors[index], P7_DESCRIPTOR_ABORTED);
      mailbox->objects_failed += 1U;
    }
  }
}

static void p7_reject_late_admission(
    volatile p7_mailbox_control_t *mailbox,
    volatile p7_object_descriptor_t *descriptor) {
  uint64_t now = p7_get_ticks();
  p7_reset_descriptor_results(descriptor);
  descriptor->error_code = P7_ERROR_RUNTIME_LIMIT;
  p7_split_ticks(now, &descriptor->start_ticks_low,
                 &descriptor->start_ticks_high);
  p7_split_ticks(now, &descriptor->end_ticks_low, &descriptor->end_ticks_high);
  p7_assign_terminal_sequence(mailbox, descriptor);
  p7_publish_descriptor(descriptor, P7_DESCRIPTOR_REJECTED);
  mailbox->objects_failed += 1U;
  mailbox->last_error_code = P7_ERROR_RUNTIME_LIMIT;
  p7_publish_mailbox(mailbox);
}

int p7_app_service_run(const ir_mmio_t *io,
                       volatile p7_mailbox_control_t *mailbox,
                       volatile p7_object_descriptor_t *descriptors) {
  p7_service_context_t service;
  uint32_t full_latched = 0U;
  uint32_t idle_loops = 0U;
  uint32_t previous_command = UINT32_MAX;
  uint32_t exit_requested = 0U;
  uint32_t requested_runtime;
  uint32_t final_runtime_request;
  uint64_t final_runtime_now;
  int shutdown_status;
  if (io == NULL || mailbox == NULL || descriptors == NULL) return -1;
  p7_invalidate(mailbox, sizeof(*mailbox));
  requested_runtime = mailbox->max_runtime_seconds;
  if (mailbox->magic != P7_MAILBOX_MAGIC ||
      mailbox->version != P7_RUNTIME_VERSION ||
      mailbox->queue_depth == 0U ||
      mailbox->queue_depth > P7_DESCRIPTOR_QUEUE_DEPTH ||
      requested_runtime == 0U ||
      requested_runtime > P7_MAX_RUNTIME_SECONDS ||
      mailbox->calibration_window_seconds > requested_runtime ||
       mailbox->sample_interval_seconds == 0U ||
       mailbox->sample_interval_seconds > requested_runtime ||
       mailbox->runtime_elapsed_sequence != 0U ||
       mailbox->runtime_elapsed_request != 0U ||
       mailbox->runtime_elapsed_ack != 0U ||
       ((mailbox->scheduling_cutoff_seconds == 0U) !=
        (mailbox->admission_guard_seconds == 0U)) ||
       (mailbox->scheduling_cutoff_seconds != 0U &&
        (mailbox->admission_guard_seconds >=
             mailbox->scheduling_cutoff_seconds ||
         mailbox->scheduling_cutoff_seconds >= requested_runtime)) ||
       (mailbox->runtime_flags & P7_RUNTIME_AUTO_DEADLINE) == 0U ||
      (mailbox->control_command != P7_CONTROL_RUN &&
       mailbox->control_command != P7_CONTROL_NONE &&
       mailbox->control_command != P7_CONTROL_STOP)) {
    shutdown_status = ir_driver_shutdown(io);
    mailbox->last_error_code = P7_ERROR_RUNTIME_LIMIT;
    mailbox->service_state = P7_SERVICE_FATAL;
    mailbox->shutdown_result = shutdown_status == 0 ? 0U : 1U;
    p7_publish_mailbox(mailbox);
    return -2;
  }
  memset(&service, 0, sizeof(service));
  service.io = io;
  service.mailbox = mailbox;
  service.queue_depth = mailbox->queue_depth;
  service.shutdown_status = -1;
  mailbox->service_state = P7_SERVICE_BOOTING;
  mailbox->queue_occupancy = 0U;
  mailbox->queue_high_watermark = 0U;
  mailbox->backpressure_events = 0U;
  mailbox->objects_requested = 0U;
  mailbox->objects_completed = 0U;
  mailbox->objects_failed = 0U;
  mailbox->fragments_completed = 0U;
  mailbox->bytes_completed_low = 0U;
  mailbox->bytes_completed_high = 0U;
  mailbox->current_session_epoch = 0U;
  mailbox->current_object_id = 0U;
  mailbox->current_fragment_index = 0U;
  mailbox->last_error_code = P7_ERROR_NONE;
  mailbox->shutdown_result = UINT32_MAX;
  mailbox->heartbeat = 0U;
  mailbox->stop_count = 0U;
  mailbox->abort_count = 0U;
  mailbox->restart_count = 0U;
  mailbox->completion_sequence = 0U;
  mailbox->consumer_hint = 0U;
  mailbox->runtime_flags = P7_RUNTIME_AUTO_DEADLINE;
  mailbox->runtime_elapsed_sequence = 0U;
  mailbox->runtime_elapsed_request = 0U;
  mailbox->runtime_elapsed_ack = 0U;
  mailbox->failure_snapshot_address = 0U;
  mailbox->failure_snapshot_bytes = 0U;
  mailbox->failure_snapshot_status = P7_FAILURE_SNAPSHOT_STATUS_NONE;
  mailbox->failure_snapshot_magic_readback = 0U;
  memset((void *)(uintptr_t)P7_FAILURE_SNAPSHOT_BASEADDR, 0,
         P7_FAILURE_SNAPSHOT_TOTAL_BYTES);
  p7_flush((const void *)(uintptr_t)P7_FAILURE_SNAPSHOT_BASEADDR,
           P7_FAILURE_SNAPSHOT_TOTAL_BYTES);
  memset((void *)(uintptr_t)P7_INPUT_REFERENCE_BASEADDR, 0,
         P7_LOCAL_PAYLOAD_BYTES);
  memset((void *)(uintptr_t)P7_P6_TX_READBACK_BASEADDR, 0,
         P7_LOCAL_PAYLOAD_BYTES);
  p7_flush((const void *)(uintptr_t)P7_INPUT_REFERENCE_BASEADDR,
           P7_LOCAL_PAYLOAD_BYTES);
  p7_flush((const void *)(uintptr_t)P7_P6_TX_READBACK_BASEADDR,
           P7_LOCAL_PAYLOAD_BYTES);
  for (uint32_t index = 0U; index < P7_DESCRIPTOR_QUEUE_DEPTH; ++index) {
    memset((void *)&descriptors[index], 0, sizeof(descriptors[index]));
    p7_flush(&descriptors[index], sizeof(descriptors[index]));
  }
  if (p7_stop_and_shutdown(&service) != 0) {
    mailbox->last_error_code = P7_ERROR_P6_RESULT;
    mailbox->service_state = P7_SERVICE_FATAL;
    p7_publish_mailbox(mailbox);
    return -3;
  }
  service.start_ticks = p7_get_ticks();
  service.runtime_limit_ticks =
      (uint64_t)requested_runtime * (uint64_t)COUNTS_PER_SECOND;
  service.shutdown_deadline_ticks =
      service.start_ticks + service.runtime_limit_ticks -
      P7_SHUTDOWN_GUARD_TICKS;
  service.completion_deadline_ticks =
      service.start_ticks + service.runtime_limit_ticks;
  service.admission_cutoff_ticks =
      mailbox->scheduling_cutoff_seconds == 0U
          ? 0U
          : service.start_ticks +
                (uint64_t)mailbox->scheduling_cutoff_seconds *
                    (uint64_t)COUNTS_PER_SECOND;
  service.admission_guard_ticks =
      (uint64_t)mailbox->admission_guard_seconds *
      (uint64_t)COUNTS_PER_SECOND;
  p7_split_ticks(service.start_ticks, &mailbox->runtime_start_ticks_low,
                 &mailbox->runtime_start_ticks_high);
  p7_publish_runtime_elapsed(mailbox, 0U, 0U);
  mailbox->service_state = P7_SERVICE_READY;
  p7_publish_mailbox(mailbox);

  for (;;) {
    uint32_t occupancy;
    uint32_t processed = 0U;
    uint32_t command = p7_control_command(&service);
    if (p7_runtime_expired(&service)) break;
    if (command == P7_CONTROL_SHUTDOWN) break;
    if (command == P7_CONTROL_STOP || command == P7_CONTROL_NONE) {
      service.abort_command_counted = 0U;
      if (mailbox->service_state != P7_SERVICE_STOPPED) {
        (void)p7_stop_and_shutdown(&service);
        mailbox->service_state = P7_SERVICE_STOPPED;
        mailbox->stop_count += 1U;
        p7_publish_mailbox(mailbox);
      }
    } else if (command == P7_CONTROL_ABORT) {
      if (previous_command != P7_CONTROL_ABORT) {
        (void)p7_stop_and_shutdown(&service);
        p7_abort_ready(mailbox, descriptors, service.queue_depth);
        if (service.abort_command_counted == 0U) {
          mailbox->abort_count += 1U;
        }
        service.abort_command_counted = 0U;
        mailbox->last_error_code = P7_ERROR_ABORTED;
        mailbox->service_state = P7_SERVICE_STOPPED;
        service.require_new_epoch = service.identity_valid;
        service.fault_latched = 1U;
        p7_publish_mailbox(mailbox);
      }
    } else if (command == P7_CONTROL_CLEAR) {
      service.abort_command_counted = 0U;
      if (previous_command != P7_CONTROL_CLEAR) {
        mailbox->last_error_code = P7_ERROR_NONE;
        service.fault_latched = 0U;
        mailbox->service_state = P7_SERVICE_STOPPED;
        p7_publish_mailbox(mailbox);
      }
    } else if (command == P7_CONTROL_RUN) {
      service.abort_command_counted = 0U;
      if (service.fault_latched == 0U) {
        mailbox->service_state = P7_SERVICE_READY;
        occupancy = p7_queue_occupancy(descriptors, service.queue_depth);
        mailbox->queue_occupancy = occupancy;
        if (occupancy > mailbox->queue_high_watermark) {
          mailbox->queue_high_watermark = occupancy;
        }
        if (occupancy == service.queue_depth && full_latched == 0U) {
          mailbox->backpressure_events += 1U;
          full_latched = 1U;
        } else if (occupancy < service.queue_depth) {
          full_latched = 0U;
        }
        p7_invalidate(&descriptors[service.consumer_index],
                      sizeof(descriptors[service.consumer_index]));
        if (descriptors[service.consumer_index].status ==
            P7_DESCRIPTOR_READY) {
          if (p7_descriptor_admission_allowed(&service)) {
            (void)p7_process_descriptor(
                &service, &descriptors[service.consumer_index]);
          } else {
            /* Firmware is the final admission authority.  A host READY that
             * arrives inside the stationary cutoff guard is terminally
             * rejected without opening P6 or driving TFDU TXD. */
            p7_reject_late_admission(
                mailbox, &descriptors[service.consumer_index]);
          }
          service.consumer_index =
              (service.consumer_index + 1U) % service.queue_depth;
          mailbox->consumer_hint = service.consumer_index;
          processed = 1U;
        }
      }
    } else {
      mailbox->last_error_code = P7_ERROR_DESCRIPTOR;
      service.fault_latched = 1U;
      (void)p7_stop_and_shutdown(&service);
      exit_requested = 1U;
    }
    occupancy = p7_queue_occupancy(descriptors, service.queue_depth);
    mailbox->queue_occupancy = occupancy;
    if (occupancy > mailbox->queue_high_watermark) {
      mailbox->queue_high_watermark = occupancy;
    }
    if (occupancy == service.queue_depth && full_latched == 0U) {
      mailbox->backpressure_events += 1U;
      full_latched = 1U;
    } else if (occupancy < service.queue_depth) {
      full_latched = 0U;
    }
    if (processed == 0U) {
      idle_loops += 1U;
      if ((idle_loops & UINT32_C(0x3ff)) == 0U) {
        mailbox->heartbeat += 1U;
        p7_publish_mailbox(mailbox);
      }
      for (volatile uint32_t spin = 0U; spin < 1000U; ++spin) {
      }
    } else {
      idle_loops = 0U;
    }
    previous_command = command;
    if (exit_requested != 0U) break;
  }
  shutdown_status = p7_stop_and_shutdown(&service);
  if (service.auto_deadline_reached != 0U) {
    while (p7_get_ticks() < service.completion_deadline_ticks) {
    }
  }
  /* The final timer snapshot is a release record: read the last visible host
   * request first, sample time second, publish the seqlock/ACK, and expose a
   * terminal service_state only after that record is complete. */
  final_runtime_request = p7_read_runtime_elapsed_request(mailbox);
  final_runtime_now = p7_get_ticks();
  mailbox->shutdown_result = shutdown_status == 0 ? 0U : 1U;
  p7_publish_runtime_elapsed(
      mailbox, p7_runtime_elapsed(&service, final_runtime_now),
      final_runtime_request);
  dmb();
  mailbox->service_state =
      shutdown_status == 0 ? P7_SERVICE_SHUTDOWN : P7_SERVICE_FATAL;
  dmb();
  p7_publish_mailbox(mailbox);
  return shutdown_status == 0 ? 0 : -3;
}
