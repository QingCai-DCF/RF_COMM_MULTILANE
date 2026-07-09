#include "ir_profile.h"

const ir_profile_config_t IR_PROFILE_G1_LANE0_BASELINE = {
  .payload_lane_mask = IR_PROFILE_LANE_MASK,
  .rx_lane_mask = IR_PROFILE_LANE_MASK,
  .ack_lane_mask = IR_PROFILE_LANE_MASK,
  .session = IR_PROFILE_SESSION,
  .payload_len = IR_PROFILE_PAYLOAD_BYTES,
  .fragment_bytes = IR_PROFILE_FRAGMENT_BYTES,
  .cnt_chip_max = 7u,
  .cnt_preamble = 16u,
  .detect_window = (7u << 8) | 0u,
  .guard_cycles = 4096u,
  .retry_timeout = 1024u,
  .startup_us = 500u,
  .duty_window = 1000u,
  .duty_max_permille = 200u,
  .stuck_high_limit_us = 10u,
};
