`timescale 1ns/1ps
module tfdu_lane_phy #(
  parameter int CLK_HZ = 64_000_000,
  parameter int TFDU_STARTUP_US = 500,
  parameter int TX_STUCK_HIGH_LIMIT_US = 10,
  parameter int DUTY_WINDOW_US = 1000,
  parameter int DUTY_MAX_PERMILLE = 200
) (
  input  logic clk,
  input  logic rst_n,
  input  logic enable_phy,
  input  logic clear_sticky,
  input  logic tx_pulse_req,
  input  logic rxd,
  output logic Txd,
  output logic SD,
  output logic Mode,
  output logic phy_ready,
  output logic rx_pulse_active,
  output logic startup_done,
  output logic shutdown_active,
  output logic fault_stuck_high,
  output logic fault_duty_limit,
  output logic [31:0] rx_raw_count,
  output logic [31:0] tx_pulse_count,
  output logic [31:0] rx_pulse_width_min,
  output logic [31:0] rx_pulse_width_max,
  output logic [31:0] rx_last_timestamp,
  output logic [31:0] tx_high_width_current,
  output logic [31:0] duty_window_count,
  output logic [31:0] duty_high_count
);
  localparam bit MODE_STATIC_HIGH = 1'b1; // Mode=1 high-speed static policy.
  localparam int CYCLES_PER_US = (CLK_HZ + 999_999) / 1_000_000;
  localparam int STARTUP_CYCLES = (CYCLES_PER_US * TFDU_STARTUP_US) < 1 ? 1 : (CYCLES_PER_US * TFDU_STARTUP_US);
  localparam int STUCK_HIGH_CYCLES = (CYCLES_PER_US * TX_STUCK_HIGH_LIMIT_US) < 1 ? 1 : (CYCLES_PER_US * TX_STUCK_HIGH_LIMIT_US);
  localparam int DUTY_WINDOW_CYCLES = (CYCLES_PER_US * DUTY_WINDOW_US) < 1 ? 1 : (CYCLES_PER_US * DUTY_WINDOW_US);
  localparam int DUTY_LIMIT_CYCLES = ((DUTY_WINDOW_CYCLES * DUTY_MAX_PERMILLE) / 1000) < 1 ? 1 : ((DUTY_WINDOW_CYCLES * DUTY_MAX_PERMILLE) / 1000);

  logic rxd_ff1;
  logic rxd_sync;
  logic rxd_sync_d;
  logic [31:0] startup_ctr;
  logic [31:0] rx_low_width;
  logic [31:0] cycle_timestamp;
  logic txd_next;

  assign Mode = MODE_STATIC_HIGH;
  assign rx_pulse_active = ~rxd_sync; // TFDU6102 Rxd is low-active.
  assign shutdown_active = SD;
  assign phy_ready = startup_done && !SD && !fault_stuck_high && !fault_duty_limit;

  always_comb begin
    txd_next = 1'b0;
    if (phy_ready && tx_pulse_req) begin
      txd_next = 1'b1;
    end
  end

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      Txd <= 1'b0;
      SD <= 1'b1;
      startup_done <= 1'b0;
      fault_stuck_high <= 1'b0;
      fault_duty_limit <= 1'b0;
      rx_raw_count <= 32'd0;
      tx_pulse_count <= 32'd0;
      rx_pulse_width_min <= 32'd0;
      rx_pulse_width_max <= 32'd0;
      rx_last_timestamp <= 32'd0;
      tx_high_width_current <= 32'd0;
      duty_window_count <= 32'd0;
      duty_high_count <= 32'd0;
      startup_ctr <= 32'd0;
      rx_low_width <= 32'd0;
      cycle_timestamp <= 32'd0;
      rxd_ff1 <= 1'b1;
      rxd_sync <= 1'b1;
      rxd_sync_d <= 1'b1;
    end else begin
      cycle_timestamp <= cycle_timestamp + 1'b1;
      rxd_ff1 <= rxd;
      rxd_sync <= rxd_ff1;
      rxd_sync_d <= rxd_sync;

      if (clear_sticky) begin
        fault_stuck_high <= 1'b0;
        fault_duty_limit <= 1'b0;
        rx_raw_count <= 32'd0;
        tx_pulse_count <= 32'd0;
        rx_pulse_width_min <= 32'd0;
        rx_pulse_width_max <= 32'd0;
        rx_last_timestamp <= 32'd0;
      end

      if (!enable_phy || fault_stuck_high || fault_duty_limit) begin
        Txd <= 1'b0;
        SD <= 1'b1;
        startup_done <= 1'b0;
        startup_ctr <= 32'd0;
        tx_high_width_current <= 32'd0;
      end else begin
        SD <= 1'b0;
        if (!startup_done) begin
          Txd <= 1'b0;
          if (startup_ctr >= STARTUP_CYCLES[31:0] - 1'b1) begin
            startup_done <= 1'b1;
          end else begin
            startup_ctr <= startup_ctr + 1'b1;
          end
        end else begin
          Txd <= txd_next;
          if (!Txd && txd_next) begin
            tx_pulse_count <= tx_pulse_count + 1'b1;
          end
        end
      end

      if (txd_next) begin
        tx_high_width_current <= tx_high_width_current + 1'b1;
        if (tx_high_width_current >= STUCK_HIGH_CYCLES[31:0] - 1'b1) begin
          fault_stuck_high <= 1'b1;
        end
      end else begin
        tx_high_width_current <= 32'd0;
      end

      if (duty_window_count >= DUTY_WINDOW_CYCLES[31:0] - 1'b1) begin
        duty_window_count <= 32'd0;
        duty_high_count <= txd_next ? 32'd1 : 32'd0;
      end else begin
        duty_window_count <= duty_window_count + 1'b1;
        if (txd_next) begin
          duty_high_count <= duty_high_count + 1'b1;
        end
      end
      if (duty_high_count >= DUTY_LIMIT_CYCLES[31:0] && txd_next) begin
        fault_duty_limit <= 1'b1;
      end

      if (!rxd_sync && rxd_sync_d) begin
        rx_raw_count <= rx_raw_count + 1'b1;
        rx_last_timestamp <= cycle_timestamp;
        rx_low_width <= 32'd1;
      end else if (!rxd_sync) begin
        rx_low_width <= rx_low_width + 1'b1;
      end else if (rxd_sync && !rxd_sync_d) begin
        if (rx_pulse_width_min == 32'd0 || rx_low_width < rx_pulse_width_min) begin
          rx_pulse_width_min <= rx_low_width;
        end
        if (rx_low_width > rx_pulse_width_max) begin
          rx_pulse_width_max <= rx_low_width;
        end
        rx_low_width <= 32'd0;
      end
    end
  end
endmodule
