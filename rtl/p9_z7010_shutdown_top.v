`timescale 1ns/1ps

// Immutable fail-closed image for the current four-TFDU / two-lane AX7010
// wiring.  No clock, processor, state element, arm path, or TX request exists.
module p9_z7010_shutdown_top (
  output [1:0] ir_mode_out_0,
  input  [1:0] ir_rx_in_0,
  output [1:0] ir_sd_0,
  output [1:0] ir_tx_out_0,
  output [1:0] loop_mode_b0,
  input  [1:0] loop_rx_b0,
  output [1:0] loop_sd_b0,
  output [1:0] loop_tx_b0
);
  assign ir_mode_out_0 = 2'b11;
  assign loop_mode_b0 = 2'b11;
  assign ir_sd_0 = 2'b11;
  assign loop_sd_b0 = 2'b11;
  assign ir_tx_out_0 = 2'b00;
  assign loop_tx_b0 = 2'b00;
  wire unused_rx = ^{ir_rx_in_0, loop_rx_b0};
endmodule
