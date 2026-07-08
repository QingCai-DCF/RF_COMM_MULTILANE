`timescale 1ns/1ps
module ir_top_new (
  output logic [1:0] ir_mode_out_0,
  input  logic [1:0] ir_rx_in_0,
  output logic [1:0] ir_sd_0,
  output logic [1:0] ir_tx_out_0,
  output logic [1:0] loop_mode_b0,
  input  logic [1:0] loop_rx_b0,
  output logic [1:0] loop_sd_b0,
  output logic [1:0] loop_tx_b0
);
  logic [3:0] unused_rx_inputs;

  assign unused_rx_inputs = {ir_rx_in_0, loop_rx_b0};

  // Safe non-hardware build top: high-speed Mode is asserted, TFDU shutdown is
  // asserted, and transmit pins are held idle low. Functional integration uses
  // the canonical RTL blocks separately until a clocked board wrapper is added.
  always_comb begin
    ir_mode_out_0 = 2'b11;
    loop_mode_b0 = 2'b11;
    ir_sd_0 = 2'b11;
    loop_sd_b0 = 2'b11;
    ir_tx_out_0 = 2'b00;
    loop_tx_b0 = 2'b00;
  end
endmodule
