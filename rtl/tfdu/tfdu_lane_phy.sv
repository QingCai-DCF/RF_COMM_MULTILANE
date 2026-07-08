`timescale 1ns/1ps
`default_nettype none
// P2 offline TFDU lane PHY wrapper. Not integrated into the production top by
// default. Rxd active-low inversion is centralized here.
module tfdu_lane_phy_p2 #(
  parameter integer CLK_HZ = 64_000_000,
  parameter integer STARTUP_US = 500,
  parameter integer TXD_MAX_HIGH_US = 70,
  parameter integer STATIC_MODE_HIGH = 1
)(
  input  wire clk,
  input  wire rst,
  input  wire enable,
  input  wire tx_req,
  input  wire tx_pulse_in,
  input  wire rxd_i,
  output wire tx_ready,
  output wire rx_ready,
  output wire rx_raw_active,
  output reg  txd_o,
  output reg  sd_o,
  output reg  mode_o,
  output reg  startup_done,
  output reg  tx_stuck_fault,
  output reg [31:0] rx_pulse_count,
  output reg [31:0] rx_last_pulse_width_cycles,
  output reg [31:0] tx_high_max_cycles
);
  localparam integer CYCLES_PER_US = (CLK_HZ + 999_999) / 1_000_000;
  localparam integer STARTUP_CYCLES = (CYCLES_PER_US * STARTUP_US) < 1 ? 1 : (CYCLES_PER_US * STARTUP_US);
  localparam integer TXD_MAX_HIGH_CYCLES = (CYCLES_PER_US * TXD_MAX_HIGH_US) < 1 ? 1 : (CYCLES_PER_US * TXD_MAX_HIGH_US);

  reg [31:0] startup_count;
  reg [31:0] tx_high_cycles;
  reg [31:0] rx_low_cycles;
  reg rxd_meta;
  reg rxd_sync;
  reg rxd_sync_d;
  wire tx_allowed;
  wire fault_active;

  assign fault_active = tx_stuck_fault;
  assign tx_ready = enable && startup_done && !fault_active && !sd_o;
  assign rx_ready = enable && startup_done && !fault_active && !sd_o;
  assign rx_raw_active = rx_ready && !rxd_sync;
  assign tx_allowed = tx_ready && tx_req && tx_pulse_in;

  always @(posedge clk) begin
    if (rst) begin
      txd_o <= 1'b0;
      sd_o <= 1'b1;
      mode_o <= STATIC_MODE_HIGH ? 1'b1 : 1'b0;
      startup_done <= 1'b0;
      tx_stuck_fault <= 1'b0;
      rx_pulse_count <= 32'd0;
      rx_last_pulse_width_cycles <= 32'd0;
      tx_high_max_cycles <= 32'd0;
      startup_count <= 32'd0;
      tx_high_cycles <= 32'd0;
      rx_low_cycles <= 32'd0;
      rxd_meta <= 1'b1;
      rxd_sync <= 1'b1;
      rxd_sync_d <= 1'b1;
    end else begin
      mode_o <= STATIC_MODE_HIGH ? 1'b1 : 1'b0;
      rxd_meta <= rxd_i;
      rxd_sync <= rxd_meta;
      rxd_sync_d <= rxd_sync;

      if (!enable || fault_active) begin
        txd_o <= 1'b0;
        sd_o <= 1'b1;
        startup_done <= 1'b0;
        startup_count <= 32'd0;
        tx_high_cycles <= 32'd0;
        rx_low_cycles <= 32'd0;
      end else begin
        sd_o <= 1'b0;
        if (!startup_done) begin
          txd_o <= 1'b0;
          if (startup_count >= STARTUP_CYCLES[31:0] - 1'b1) begin
            startup_done <= 1'b1;
          end else begin
            startup_count <= startup_count + 1'b1;
          end
        end else if (tx_allowed) begin
          txd_o <= 1'b1;
        end else begin
          txd_o <= 1'b0;
        end
      end

      if (tx_allowed) begin
        tx_high_cycles <= tx_high_cycles + 1'b1;
        if (tx_high_cycles + 1'b1 > tx_high_max_cycles) begin
          tx_high_max_cycles <= tx_high_cycles + 1'b1;
        end
        if (tx_high_cycles >= TXD_MAX_HIGH_CYCLES[31:0] - 1'b1) begin
          tx_stuck_fault <= 1'b1;
          txd_o <= 1'b0;
        end
      end else begin
        tx_high_cycles <= 32'd0;
      end

      if (rx_ready) begin
        if (!rxd_sync && rxd_sync_d) begin
          rx_pulse_count <= rx_pulse_count + 1'b1;
          rx_low_cycles <= 32'd1;
        end else if (!rxd_sync) begin
          rx_low_cycles <= rx_low_cycles + 1'b1;
        end else if (rxd_sync && !rxd_sync_d) begin
          rx_last_pulse_width_cycles <= rx_low_cycles;
          rx_low_cycles <= 32'd0;
        end
      end
    end
  end
endmodule
`default_nettype wire
