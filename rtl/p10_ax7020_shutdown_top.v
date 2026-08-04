`timescale 1ns/1ps
`default_nettype none

// P10 AX7020 post-configuration shutdown image.
//
// This image establishes the configured PL intent required by the TFDU6102
// contract: Mode=HIGH (static MIR/FIR), SD=HIGH (shutdown), and Txd=LOW.
// It cannot establish those levels before configuration or under partial
// power; P10-SAFETY-POWERUP-001 therefore remains a hardware-admission block.
module p10_ax7020_shutdown_top #(
  parameter integer LANE_COUNT = 2
) (
  output wire [LANE_COUNT-1:0] tfdu_mode_o,
  input  wire [LANE_COUNT-1:0] tfdu_rxd_i,
  output wire [LANE_COUNT-1:0] tfdu_sd_o,
  output wire [LANE_COUNT-1:0] tfdu_txd_o,
  output wire [3:0] pl_activity_led_n_o
);
  initial begin
    if (LANE_COUNT != 2 && LANE_COUNT != 4)
      $error("P10 AX7020 shutdown LANE_COUNT must be 2 or 4");
  end

  assign tfdu_mode_o = {LANE_COUNT{1'b1}};
  assign tfdu_sd_o = {LANE_COUNT{1'b1}};
  assign tfdu_txd_o = {LANE_COUNT{1'b0}};
  // AX7020 PL user LEDs are active-low.  A shutdown image must explicitly
  // drive every LED high/off; leaving these pads absent allowed the board LED
  // loads to appear lit after programming the previous shutdown image.
  assign pl_activity_led_n_o = 4'b1111;

  // Keep the two physical input pads explicit without allowing them to affect
  // any output or the safe shutdown state.
  wire unused_rxd = ^tfdu_rxd_i;
endmodule

`default_nettype wire
