// Auto-generated from config/tfdu_safety.yaml; do not edit.
`timescale 1ns/1ps
package tfdu_safety_pkg;
  localparam int unsigned CANONICAL_CLOCK_HZ = 64000000;
  localparam int unsigned RECEIVER_STARTUP_US = 500;
  localparam int unsigned ROLLING_DUTY_WINDOW_US = 1000;
  localparam int unsigned HARD_PERCENT_STRICT_LT = 20;
  localparam int unsigned TARGET_PERCENT_MAX = 18;
  localparam int unsigned LONG_TERM_WINDOW_MS = 100;
  localparam int unsigned LONG_TERM_TARGET_PERCENT_MAX = 18;
  localparam int unsigned MAX_CONTINUOUS_TXD_HIGH_US = 1;
  localparam int unsigned GLOBAL_PERMIT_ASSERT_FILTER_CYCLES = 4;
  localparam int unsigned CANONICAL_WINDOW_CYCLES = 64000;
  localparam int unsigned CANONICAL_STARTUP_CYCLES = 32000;
  localparam int unsigned CANONICAL_MAX_CONTINUOUS_CYCLES = 64;
  localparam int unsigned CANONICAL_HARD_MAX_HIGH_CYCLES = 12799;
  localparam int unsigned CANONICAL_TARGET_MAX_HIGH_CYCLES = 11520;

  typedef enum logic [4:0] {
    TX_KILL_NONE = 5'd0,
    TX_KILL_RESET_OR_FULL_SHUTDOWN = 5'd1,
    TX_KILL_GLOBAL_PERMIT_LOW = 5'd2,
    TX_KILL_NOT_ARMED = 5'd3,
    TX_KILL_FATAL_FAULT = 5'd4,
    TX_KILL_ILLEGAL_ONE_HOT = 5'd5,
    TX_KILL_INVALID_SELECTED_MODULE = 5'd6,
    TX_KILL_STALE_OR_INVALID_PATH_EPOCH = 5'd7,
    TX_KILL_STARTUP_NOT_COMPLETE = 5'd8,
    TX_KILL_DUTY_TARGET_THROTTLE = 5'd9,
    TX_KILL_DUTY_HARD_FAULT = 5'd10,
    TX_KILL_STUCK_HIGH_FAULT = 5'd11,
    TX_KILL_FRAME_NOT_ADMITTED = 5'd12,
    TX_KILL_SD_ACTIVE = 5'd13,
    TX_KILL_HISTORY_COOLDOWN = 5'd14,
    TX_KILL_PARTIAL_FRAME_ABORTED = 5'd15
  } tx_kill_reason_t;
endpackage
