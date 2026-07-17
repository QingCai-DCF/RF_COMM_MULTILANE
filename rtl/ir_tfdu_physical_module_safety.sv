`timescale 1ns/1ps
`default_nettype none
`include "generated/tfdu_safety_config.svh"

// Safety state owned by one physical TFDU module. Logical-lane, mapping,
// permit, SD, and frame transitions do not reset its rolling history.
module ir_tfdu_physical_module_safety #(
  parameter integer CLOCK_HZ = `TFDU_SAFETY_CANONICAL_CLOCK_HZ,
  parameter integer STARTUP_US = `TFDU_SAFETY_RECEIVER_STARTUP_US,
  parameter integer WINDOW_US = `TFDU_SAFETY_ROLLING_WINDOW_US,
  parameter integer HARD_PERCENT_STRICT_LT = `TFDU_SAFETY_HARD_PERCENT_STRICT_LT,
  parameter integer TARGET_PERCENT_MAX = `TFDU_SAFETY_TARGET_PERCENT_MAX,
  parameter integer MAX_CONTINUOUS_HIGH_US = `TFDU_SAFETY_MAX_CONTINUOUS_HIGH_US
) (
  input  wire         clk,
  input  wire         rst_n,
  input  wire         history_invalidate_i,
  input  wire         safety_fault_clear_i,
  input  wire         telemetry_clear_i,
  input  wire         sd_active_i,
  input  wire         tx_request_i,
  output reg          txd_pre_final_o,
  output reg          startup_done_o,
  output reg  [31:0]  continuous_high_cycles_o,
  output reg  [31:0]  longest_high_cycles_seen_o,
  output reg          stuck_high_fault_o,
  output reg  [31:0]  stuck_high_fault_count_o,
  output reg  [31:0]  stuck_high_kill_count_o,
  output wire [31:0]  rolling_high_cycles_o,
  output wire [31:0]  rolling_high_cycles_max_seen_o,
  output wire [31:0]  rolling_window_cycles_o,
  output wire [31:0]  hard_limit_cycles_o,
  output wire [31:0]  target_limit_cycles_o,
  output wire [31:0]  duty_headroom_cycles_o,
  output wire         duty_target_throttle_o,
  output wire [31:0]  duty_target_throttle_count_o,
  output wire         duty_hard_fault_o,
  output wire [31:0]  duty_hard_fault_count_o,
  output wire         duty_history_valid_o,
  output wire         duty_recovery_cooldown_active_o,
  output wire [31:0]  duty_recovery_cooldown_remaining_o,
  output wire [31:0]  actual_or_conservative_charge_count_o
);
  localparam longint unsigned STARTUP_PRODUCT = CLOCK_HZ * STARTUP_US;
  localparam integer STARTUP_CYCLES = STARTUP_PRODUCT / 1_000_000;
  localparam longint unsigned MAX_HIGH_PRODUCT = CLOCK_HZ * MAX_CONTINUOUS_HIGH_US;
  localparam integer MAX_CONTINUOUS_CYCLES = MAX_HIGH_PRODUCT / 1_000_000;

  reg [31:0] startup_count_q;
  wire target_admit_next;
  wire hard_violation_next;
  wire [32:0] continuous_after_current;
  wire continuous_overrun_request;
  wire safety_clear_or_invalidate;

  assign continuous_after_current = txd_pre_final_o ?
      ({1'b0, continuous_high_cycles_o} + 1'b1) : 33'd0;
  assign continuous_overrun_request = tx_request_i && txd_pre_final_o &&
      (continuous_after_current >= MAX_CONTINUOUS_CYCLES);
  assign safety_clear_or_invalidate = safety_fault_clear_i || history_invalidate_i;

  initial begin
    if (STARTUP_PRODUCT == 0 || (STARTUP_PRODUCT % 1_000_000) != 0)
      $fatal(1, "P8C STARTUP_CYCLES conversion must be exact and nonzero");
    if (MAX_HIGH_PRODUCT == 0 || (MAX_HIGH_PRODUCT % 1_000_000) != 0)
      $fatal(1, "P8C MAX_CONTINUOUS_CYCLES conversion must be exact and nonzero");
    if (MAX_CONTINUOUS_HIGH_US > 1)
      $fatal(1, "P8C MAX_CONTINUOUS_TXD_HIGH_US must be <= 1");
  end

  ir_tfdu_exact_duty_accountant #(
    .CLOCK_HZ(CLOCK_HZ),
    .WINDOW_US(WINDOW_US),
    .HARD_PERCENT_STRICT_LT(HARD_PERCENT_STRICT_LT),
    .TARGET_PERCENT_MAX(TARGET_PERCENT_MAX)
  ) u_exact_duty_accountant (
    .clk(clk),
    .rst_n(rst_n),
    .history_invalidate_i(history_invalidate_i),
    .safety_fault_clear_i(safety_fault_clear_i),
    .telemetry_clear_i(telemetry_clear_i),
    .charge_i(txd_pre_final_o),
    .target_request_i(tx_request_i && startup_done_o && duty_history_valid_o && !stuck_high_fault_o),
    .target_admit_next_o(target_admit_next),
    .hard_violation_next_o(hard_violation_next),
    .rolling_high_cycles_o(rolling_high_cycles_o),
    .rolling_high_cycles_max_seen_o(rolling_high_cycles_max_seen_o),
    .rolling_window_cycles_o(rolling_window_cycles_o),
    .hard_limit_cycles_o(hard_limit_cycles_o),
    .target_limit_cycles_o(target_limit_cycles_o),
    .duty_headroom_cycles_o(duty_headroom_cycles_o),
    .duty_target_throttle_o(duty_target_throttle_o),
    .duty_target_throttle_count_o(duty_target_throttle_count_o),
    .duty_hard_fault_o(duty_hard_fault_o),
    .duty_hard_fault_count_o(duty_hard_fault_count_o),
    .duty_history_valid_o(duty_history_valid_o),
    .duty_recovery_cooldown_active_o(duty_recovery_cooldown_active_o),
    .duty_recovery_cooldown_remaining_o(duty_recovery_cooldown_remaining_o),
    .actual_or_conservative_charge_count_o(actual_or_conservative_charge_count_o)
  );

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      startup_done_o <= 1'b0;
      startup_count_q <= 32'd0;
    end else if (sd_active_i) begin
      startup_done_o <= 1'b0;
      startup_count_q <= 32'd0;
    end else if (!startup_done_o) begin
      if (startup_count_q == STARTUP_CYCLES-1) begin
        startup_done_o <= 1'b1;
      end else begin
        startup_count_q <= startup_count_q + 1'b1;
      end
    end
  end

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      txd_pre_final_o <= 1'b0;
      continuous_high_cycles_o <= 32'd0;
      longest_high_cycles_seen_o <= 32'd0;
      stuck_high_fault_o <= 1'b0;
      stuck_high_fault_count_o <= 32'd0;
      stuck_high_kill_count_o <= 32'd0;
    end else if (safety_clear_or_invalidate) begin
      txd_pre_final_o <= 1'b0;
      continuous_high_cycles_o <= 32'd0;
      if (safety_fault_clear_i)
        stuck_high_fault_o <= 1'b0;
    end else begin
      if (txd_pre_final_o) begin
        continuous_high_cycles_o <= continuous_after_current[31:0];
        if (continuous_after_current > longest_high_cycles_seen_o)
          longest_high_cycles_seen_o <= continuous_after_current[31:0];
      end else begin
        continuous_high_cycles_o <= 32'd0;
      end

      if (continuous_overrun_request && !stuck_high_fault_o) begin
        txd_pre_final_o <= 1'b0;
        stuck_high_fault_o <= 1'b1;
        stuck_high_fault_count_o <= stuck_high_fault_count_o + 1'b1;
        stuck_high_kill_count_o <= stuck_high_kill_count_o + 1'b1;
      end else if (sd_active_i || !startup_done_o || !duty_history_valid_o ||
                   duty_recovery_cooldown_active_o || duty_hard_fault_o ||
                   hard_violation_next || stuck_high_fault_o) begin
        txd_pre_final_o <= 1'b0;
      end else if (tx_request_i && target_admit_next) begin
        txd_pre_final_o <= 1'b1;
      end else begin
        txd_pre_final_o <= 1'b0;
      end

      if (telemetry_clear_i) begin
        longest_high_cycles_seen_o <= continuous_high_cycles_o;
        // Sticky faults and event counts intentionally survive telemetry clear.
      end
    end
  end
endmodule

`default_nettype wire
