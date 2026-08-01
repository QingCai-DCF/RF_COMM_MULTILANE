`timescale 1ns/1ps
`default_nettype none

`define P10_1R_FOCUSED
`include "tb_p10_dual_endpoint_pair.sv"

// Exact P10.1R focused-test top name.  P10_1R_FOCUSED selects the bounded
// two-direction subset in the canonical dual-endpoint testbench.
module tb_p10_1r_dual_endpoint;
  tb_p10_dual_endpoint_pair implementation();
endmodule

`default_nettype wire
