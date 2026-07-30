`timescale 1ns/1ps
`default_nettype none

// P10 AX7020 post-configuration shutdown image.
//
// This image establishes the configured PL intent required by the TFDU6102
// contract: Mode=HIGH (static MIR/FIR), SD=HIGH (shutdown), and Txd=LOW.
// It cannot establish those levels before configuration or under partial
// power; P10-SAFETY-POWERUP-001 therefore remains a hardware-admission block.
module p10_ax7020_shutdown_top (
  output wire [1:0] tfdu_mode_o,
  input  wire [1:0] tfdu_rxd_i,
  output wire [1:0] tfdu_sd_o,
  output wire [1:0] tfdu_txd_o
);
  assign tfdu_mode_o = 2'b11;
  assign tfdu_sd_o = 2'b11;
  assign tfdu_txd_o = 2'b00;

  // Keep the two physical input pads explicit without allowing them to affect
  // any output or the safe shutdown state.
  wire unused_rxd = ^tfdu_rxd_i;
endmodule

`default_nettype wire
