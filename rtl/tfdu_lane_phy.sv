`timescale 1ns/1ps
`default_nettype none
`include "generated/tfdu_safety_config.svh"

// Legacy P0-P7 lane-facing compatibility wrapper. P8C production endpoint
// safety is implemented by ir_tfdu_safety_endpoint. This wrapper now uses the
// same exact physical-module accountant, replacing the historical fixed 1 ms
// bucket while preserving the established port contract.
module tfdu_lane_phy #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer TFDU_STARTUP_US = 500,
  parameter integer TX_STUCK_HIGH_LIMIT_US = 10,
  parameter integer DUTY_WINDOW_US = 1000,
  parameter integer DUTY_MAX_PERMILLE = 200
) (
  input  wire         clk,
  input  wire         rst_n,
  input  wire         enable_phy,
  input  wire         clear_sticky,
  input  wire         tx_pulse_req,
  input  wire         rxd,
  output wire         Txd,
  output wire         SD,
  output wire         Mode,
  output wire         phy_ready,
  output wire         rx_pulse_active,
  output wire         startup_done,
  output wire         shutdown_active,
  output reg          fault_stuck_high,
  output reg          fault_duty_limit,
  output reg  [31:0]  rx_raw_count,
  output reg  [31:0]  tx_pulse_count,
  output reg  [31:0]  rx_pulse_width_min,
  output reg  [31:0]  rx_pulse_width_max,
  output reg  [31:0]  rx_last_timestamp,
  output wire [31:0]  tx_high_width_current,
  output wire [31:0]  duty_window_count,
  output wire [31:0]  duty_high_count
);
  // Compatibility parameters remain visible for older profiles. The active
  // protection is intentionally clamped to the canonical P8C 1 us/18% target.
  localparam integer LEGACY_PARAMETER_CONTRACT =
      TX_STUCK_HIGH_LIMIT_US + DUTY_MAX_PERMILLE;
  localparam wire MODE_STATIC_HIGH = 1'b1;

  reg rxd_ff1;
  reg rxd_sync;
  reg rxd_sync_d;
  reg [31:0] rx_low_width;
  reg [31:0] cycle_timestamp;
  reg txd_d;
  wire txd_pre_final;
  wire module_startup_done;
  wire module_stuck_fault;
  wire module_duty_hard_fault;
  wire duty_target_throttle;
  wire history_valid;
  wire cooldown_active;
  wire [31:0] rolling_window_cycles;
  wire [31:0] rolling_high_cycles;
  wire local_shutdown;

  assign Mode = MODE_STATIC_HIGH;
  assign local_shutdown = !enable_phy || fault_stuck_high || fault_duty_limit;
  assign SD = local_shutdown;
  assign shutdown_active = SD;
  assign Txd = txd_pre_final && !local_shutdown;
  assign startup_done = module_startup_done;
  assign phy_ready = enable_phy && module_startup_done && history_valid &&
      !cooldown_active && !fault_stuck_high && !fault_duty_limit;
  assign rx_pulse_active = phy_ready && !rxd_sync;
  assign duty_window_count = rolling_window_cycles;
  assign duty_high_count = rolling_high_cycles;

  ir_tfdu_physical_module_safety #(
    .CLOCK_HZ(CLK_HZ),
    .STARTUP_US(TFDU_STARTUP_US),
    .WINDOW_US(DUTY_WINDOW_US),
    .HARD_PERCENT_STRICT_LT(`TFDU_SAFETY_HARD_PERCENT_STRICT_LT),
    .TARGET_PERCENT_MAX(`TFDU_SAFETY_TARGET_PERCENT_MAX),
    .MAX_CONTINUOUS_HIGH_US(`TFDU_SAFETY_MAX_CONTINUOUS_HIGH_US)
  ) u_p8c_physical_safety (
    .clk(clk),
    .rst_n(rst_n),
    .history_invalidate_i(1'b0),
    .safety_fault_clear_i(clear_sticky),
    .telemetry_clear_i(clear_sticky),
    .sd_active_i(local_shutdown),
    .tx_request_i(enable_phy && tx_pulse_req && !fault_stuck_high && !fault_duty_limit),
    .txd_pre_final_o(txd_pre_final),
    .startup_done_o(module_startup_done),
    .continuous_high_cycles_o(tx_high_width_current),
    .longest_high_cycles_seen_o(),
    .stuck_high_fault_o(module_stuck_fault),
    .stuck_high_fault_count_o(),
    .stuck_high_kill_count_o(),
    .rolling_high_cycles_o(rolling_high_cycles),
    .rolling_high_cycles_max_seen_o(),
    .rolling_window_cycles_o(rolling_window_cycles),
    .hard_limit_cycles_o(),
    .target_limit_cycles_o(),
    .duty_headroom_cycles_o(),
    .duty_target_throttle_o(duty_target_throttle),
    .duty_target_throttle_count_o(),
    .duty_hard_fault_o(module_duty_hard_fault),
    .duty_hard_fault_count_o(),
    .duty_history_valid_o(history_valid),
    .duty_recovery_cooldown_active_o(cooldown_active),
    .duty_recovery_cooldown_remaining_o(),
    .actual_or_conservative_charge_count_o()
  );

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      fault_stuck_high <= 1'b0;
      fault_duty_limit <= 1'b0;
      rx_raw_count <= 32'd0;
      tx_pulse_count <= 32'd0;
      rx_pulse_width_min <= 32'd0;
      rx_pulse_width_max <= 32'd0;
      rx_last_timestamp <= 32'd0;
      rx_low_width <= 32'd0;
      cycle_timestamp <= 32'd0;
      rxd_ff1 <= 1'b1;
      rxd_sync <= 1'b1;
      rxd_sync_d <= 1'b1;
      txd_d <= 1'b0;
    end else begin
      cycle_timestamp <= cycle_timestamp + 1'b1;
      rxd_ff1 <= rxd;
      rxd_sync <= rxd_ff1;
      rxd_sync_d <= rxd_sync;
      txd_d <= Txd;

      if (clear_sticky) begin
        fault_stuck_high <= 1'b0;
        fault_duty_limit <= 1'b0;
        rx_raw_count <= 32'd0;
        tx_pulse_count <= 32'd0;
        rx_pulse_width_min <= 32'd0;
        rx_pulse_width_max <= 32'd0;
        rx_last_timestamp <= 32'd0;
      end else begin
        if (module_stuck_fault)
          fault_stuck_high <= 1'b1;
        if (module_duty_hard_fault || duty_target_throttle)
          fault_duty_limit <= 1'b1;
        if (!txd_d && Txd)
          tx_pulse_count <= tx_pulse_count + 1'b1;
      end

      if (phy_ready) begin
        if (!rxd_sync && rxd_sync_d) begin
          rx_raw_count <= rx_raw_count + 1'b1;
          rx_last_timestamp <= cycle_timestamp;
          rx_low_width <= 32'd1;
        end else if (!rxd_sync) begin
          rx_low_width <= rx_low_width + 1'b1;
        end else if (rxd_sync && !rxd_sync_d) begin
          if (rx_pulse_width_min == 0 || rx_low_width < rx_pulse_width_min)
            rx_pulse_width_min <= rx_low_width;
          if (rx_low_width > rx_pulse_width_max)
            rx_pulse_width_max <= rx_low_width;
          rx_low_width <= 32'd0;
        end
      end else begin
        rx_low_width <= 32'd0;
      end
    end
  end

  wire _unused_legacy_parameters = (LEGACY_PARAMETER_CONTRACT == 0);
endmodule

`default_nettype wire
