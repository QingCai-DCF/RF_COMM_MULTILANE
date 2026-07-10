#ifndef RF_TRANSPORT_BACKEND_H
#define RF_TRANSPORT_BACKEND_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define RF_TRANSPORT_MAX_PAYLOAD_BYTES UINT32_C(247)
#define RF_TRANSPORT_ALLOWED_LANE_MASK UINT32_C(0x3)

typedef enum rf_transport_status {
  RF_TRANSPORT_OK = 0,
  RF_TRANSPORT_ERR_ARGUMENT = -1,
  RF_TRANSPORT_ERR_STATE = -2,
  RF_TRANSPORT_ERR_CAPABILITY = -3,
  RF_TRANSPORT_ERR_IO = -4,
  RF_TRANSPORT_ERR_TIMEOUT = -5,
  RF_TRANSPORT_ERR_ABORTED = -6,
  RF_TRANSPORT_ERR_BUFFER = -7
} rf_transport_status_t;

typedef struct rf_transport_capabilities {
  uint32_t max_payload_bytes;
  uint32_t allowed_lane_mask;
  uint32_t queue_depth;
  uint32_t flags;
} rf_transport_capabilities_t;

typedef struct rf_transport_fragment_result {
  uint32_t token;
  uint32_t accepted;
  uint32_t lane_mask;
  uint32_t payload_bytes;
  uint32_t retry_count;
  uint32_t retry_exhausted;
  uint32_t tx_fail;
  uint32_t crc_bad;
  uint32_t payload_mismatch;
  uint32_t txd_high_consecutive_max;
  uint32_t duty_violation_count;
  uint32_t error_code;
} rf_transport_fragment_result_t;

typedef struct rf_transport_metrics {
  uint64_t fragments_submitted;
  uint64_t fragments_completed;
  uint64_t fragments_failed;
  uint64_t bytes_submitted;
  uint64_t bytes_completed;
  uint64_t retry_count;
  uint64_t retry_exhausted;
  uint64_t tx_fail;
  uint64_t crc_bad;
  uint64_t payload_mismatch;
  uint32_t txd_high_consecutive_max;
  uint64_t duty_violation_count;
} rf_transport_metrics_t;

struct rf_transport_backend;
typedef struct rf_transport_backend rf_transport_backend_t;

typedef struct rf_transport_backend_ops {
  int (*open)(rf_transport_backend_t *backend);
  int (*get_capabilities)(rf_transport_backend_t *backend,
                          rf_transport_capabilities_t *capabilities);
  int (*submit_fragment)(rf_transport_backend_t *backend,
                         const uint8_t *payload, size_t payload_size,
                         uint32_t lane_mask, uint32_t *token_out);
  int (*poll_fragment_result)(rf_transport_backend_t *backend, uint32_t token,
                              uint32_t max_polls,
                              rf_transport_fragment_result_t *result);
  int (*read_fragment)(rf_transport_backend_t *backend, uint32_t token,
                       uint8_t *payload, size_t payload_capacity,
                       size_t *payload_size);
  int (*abort)(rf_transport_backend_t *backend);
  int (*close)(rf_transport_backend_t *backend);
  int (*get_metrics)(rf_transport_backend_t *backend,
                     rf_transport_metrics_t *metrics);
} rf_transport_backend_ops_t;

struct rf_transport_backend {
  const rf_transport_backend_ops_t *ops;
  void *context;
};

int rf_transport_open(rf_transport_backend_t *backend);
int rf_transport_get_capabilities(
    rf_transport_backend_t *backend,
    rf_transport_capabilities_t *capabilities);
int rf_transport_submit_fragment(rf_transport_backend_t *backend,
                                 const uint8_t *payload,
                                 size_t payload_size, uint32_t lane_mask,
                                 uint32_t *token_out);
int rf_transport_poll_fragment_result(
    rf_transport_backend_t *backend, uint32_t token, uint32_t max_polls,
    rf_transport_fragment_result_t *result);
int rf_transport_read_fragment(rf_transport_backend_t *backend,
                               uint32_t token, uint8_t *payload,
                               size_t payload_capacity,
                               size_t *payload_size);
int rf_transport_abort(rf_transport_backend_t *backend);
int rf_transport_close(rf_transport_backend_t *backend);
int rf_transport_get_metrics(rf_transport_backend_t *backend,
                             rf_transport_metrics_t *metrics);

#ifdef __cplusplus
}
#endif

#endif
