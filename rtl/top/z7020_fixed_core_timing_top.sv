`timescale 1ns/1ps
module z7020_fixed_core_timing_top(
  input logic protocol_clk_i,input logic axis_dma_clk_i,input logic axi_lite_clk_i,
  input logic reset_n_i,input logic global_permit_i,input logic endpoint_arm_request_i,
  input logic dma_tx_kick_i,input logic control_abort_i,input logic protocol_rx_event_i,
  input logic protocol_ack_event_i,input logic [31:0] stimulus_seed_i,
  output logic [31:0] physical_txd_o,output logic physical_attempt_valid_o,
  output logic [2:0] physical_attempt_lane_o,output logic [15:0] physical_attempt_sequence_o,
  output logic architecture_status_o,output logic clock_domain_status_o);
  ir_fixed_endpoint_core u_top(.*);
endmodule
