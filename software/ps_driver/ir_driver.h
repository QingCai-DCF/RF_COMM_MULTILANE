#pragma once
#include <stdint.h>

typedef uint32_t (*ir_read32_fn)(void *ctx, uint32_t offset);
typedef void (*ir_write32_fn)(void *ctx, uint32_t offset, uint32_t value);

typedef struct {
  void *ctx;
  ir_read32_fn read32;
  ir_write32_fn write32;
} ir_mmio_t;

typedef struct {
  uint32_t payload_lane_mask;
  uint32_t rx_lane_mask;
  uint32_t ack_lane_mask;
  uint32_t session;
  uint32_t payload_len;
  uint32_t fragment_bytes;
  uint32_t cnt_chip_max;
  uint32_t cnt_preamble;
  uint32_t detect_window;
  uint32_t guard_cycles;
  uint32_t retry_timeout;
  uint32_t startup_us;
  uint32_t duty_window;
  uint32_t duty_max_permille;
  uint32_t stuck_high_limit_us;
} ir_profile_config_t;

typedef struct {
  uint32_t status;
  uint32_t retry_count;
  uint32_t error_counts;
  uint32_t tx_pulse;
  uint32_t rx_raw_pulse;
  uint32_t frame_good;
  uint32_t frame_bad;
  uint32_t ack_sent;
  uint32_t ack_seen;
} ir_driver_counters_t;

typedef struct {
  uint32_t session;
  uint32_t lane_mask;
  uint32_t ack_lane_mask;
  uint32_t payload_len;
  uint32_t pattern_id;
  uint32_t seed;
  uint32_t timeout_cycles;
} ir_p6_payload_config_t;

typedef struct {
  uint32_t status;
  uint32_t mailbox_status;
  uint32_t payload_crc32;
  uint32_t rx_payload_crc32;
  uint32_t rx_payload_len;
  uint32_t tx_count;
  uint32_t rx_good_count_l0;
  uint32_t rx_good_count_l1;
  uint32_t crc_bad;
  uint32_t payload_mismatch;
  uint32_t retry_count;
  uint32_t retry_exhausted;
  uint32_t tx_fail;
  uint32_t txd_high_consecutive_max;
  uint32_t duty_violation;
  uint32_t shutdown_reason;
  uint32_t error_code;
  uint32_t sticky_error;
  uint32_t rx_digest;
} ir_p6_payload_result_t;

int ir_driver_initialize(const ir_mmio_t *io, const ir_profile_config_t *profile, uint32_t startup_max_polls);
int ir_driver_apply_profile(const ir_mmio_t *io, const ir_profile_config_t *profile);
int ir_driver_wait_startup(const ir_mmio_t *io, uint32_t max_polls);
int ir_driver_start_transaction(const ir_mmio_t *io);
int ir_driver_poll_done(const ir_mmio_t *io, uint32_t max_polls);
int ir_driver_read_final_counters(const ir_mmio_t *io, ir_driver_counters_t *counters);
int ir_driver_run_transaction(const ir_mmio_t *io, uint32_t max_polls, ir_driver_counters_t *final_counters);
int ir_driver_stop(const ir_mmio_t *io);
int ir_driver_shutdown(const ir_mmio_t *io);
int ir_driver_p6_write_payload(const ir_mmio_t *io, const uint8_t *payload, uint32_t payload_len);
int ir_driver_p6_read_rx_payload(const ir_mmio_t *io, uint8_t *payload, uint32_t payload_capacity, uint32_t *payload_len);
int ir_driver_p6_commit_payload(const ir_mmio_t *io, const ir_p6_payload_config_t *config);
int ir_driver_p6_start(const ir_mmio_t *io);
int ir_driver_p6_get_status(const ir_mmio_t *io, uint32_t *status);
int ir_driver_p6_start_and_poll(const ir_mmio_t *io, uint32_t max_polls, ir_p6_payload_result_t *result);
int ir_driver_p6_read_result(const ir_mmio_t *io, ir_p6_payload_result_t *result);
int ir_driver_p6_reset(const ir_mmio_t *io);
int ir_driver_p6_stop(const ir_mmio_t *io);
int ir_driver_p6_run_payload_no_shutdown(
    const ir_mmio_t *io,
    const ir_p6_payload_config_t *config,
    const uint8_t *payload,
    uint32_t max_polls,
    ir_p6_payload_result_t *result);
int ir_driver_p6_run_mailbox_payload(
    const ir_mmio_t *io,
    const ir_p6_payload_config_t *config,
    const uint8_t *payload,
    uint32_t max_polls,
    ir_p6_payload_result_t *result);
