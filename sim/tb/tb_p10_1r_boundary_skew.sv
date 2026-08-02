`timescale 1ns/1ps
`default_nettype none

`define P10_1R_BOUNDARY_SKEW
`include "tb_p10_dual_endpoint_pair.sv"

module tb_p10_1r_boundary_skew;
  tb_p10_dual_endpoint_pair implementation();
endmodule

`default_nettype wire
