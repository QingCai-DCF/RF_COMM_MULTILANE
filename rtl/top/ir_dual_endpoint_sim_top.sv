`timescale 1ns/1ps
module ir_dual_endpoint_sim_top(
  input logic fixed_protocol_clk_i,input logic fixed_axis_clk_i,input logic fixed_axil_clk_i,
  input logic fixed_reset_n_i,input logic rotating_protocol_clk_i,
  input logic rotating_axis_clk_i,input logic rotating_axil_clk_i,input logic rotating_reset_n_i,
  input logic fixed_global_permit_i,input logic rotating_global_permit_i,
  input logic fixed_kick_i,input logic rotating_kick_i,
  output logic fixed_status_o,output logic rotating_status_o);
  wire [31:0] fixed_txd;wire [7:0] rotating_txd;
  wire fixed_attempt,rotating_attempt;wire [2:0] fixed_lane,rotating_lane;
  wire [15:0] fixed_sequence,rotating_sequence;wire fixed_cdc,rotating_cdc;
  ir_fixed_endpoint_core fixed_endpoint(
    .protocol_clk_i(fixed_protocol_clk_i),.axis_dma_clk_i(fixed_axis_clk_i),
    .axi_lite_clk_i(fixed_axil_clk_i),.reset_n_i(fixed_reset_n_i),
    .global_permit_i(fixed_global_permit_i),.endpoint_arm_request_i(1'b1),
    .dma_tx_kick_i(fixed_kick_i),.control_abort_i(1'b0),
    .protocol_rx_event_i(rotating_attempt),.protocol_ack_event_i(rotating_attempt),
    .stimulus_seed_i(32'hf17ed001),.physical_txd_o(fixed_txd),
    .physical_attempt_valid_o(fixed_attempt),.physical_attempt_lane_o(fixed_lane),
    .physical_attempt_sequence_o(fixed_sequence),.architecture_status_o(fixed_status_o),
    .clock_domain_status_o(fixed_cdc));
  ir_rotating_endpoint_core rotating_endpoint(
    .protocol_clk_i(rotating_protocol_clk_i),.axis_dma_clk_i(rotating_axis_clk_i),
    .axi_lite_clk_i(rotating_axil_clk_i),.reset_n_i(rotating_reset_n_i),
    .global_permit_i(rotating_global_permit_i),.endpoint_arm_request_i(1'b1),
    .dma_tx_kick_i(rotating_kick_i),.control_abort_i(1'b0),
    .protocol_rx_event_i(fixed_attempt),.protocol_ack_event_i(fixed_attempt),
    .stimulus_seed_i(32'h2070a11e),.physical_txd_o(rotating_txd),
    .physical_attempt_valid_o(rotating_attempt),.physical_attempt_lane_o(rotating_lane),
    .physical_attempt_sequence_o(rotating_sequence),.architecture_status_o(rotating_status_o),
    .clock_domain_status_o(rotating_cdc));
endmodule
