`timescale 1ns/1ps
module z7010_2lane_dev_top(
  input logic protocol_clk_i,input logic axis_dma_clk_i,input logic axi_lite_clk_i,
  input logic reset_n_i,input logic global_permit_i,input logic endpoint_arm_request_i,
  input logic dma_tx_kick_i,input logic control_abort_i,input logic protocol_ack_event_i,
  input logic [31:0] stimulus_seed_i,
  input logic [1:0] ir_rx_in_0,input logic [1:0] loop_rx_b0,
  output wire [1:0] ir_tx_out_0,output wire [1:0] ir_sd_0,
  output wire [1:0] ir_mode_out_0,output wire [1:0] loop_tx_b0,
  output wire [1:0] loop_sd_b0,output wire [1:0] loop_mode_b0,
  output wire architecture_status_o,output wire clock_domain_status_o);
  import ir_p8e_profile_pkg::*;
  wire [1:0] physical_txd;
  wire [1:0] ir_rx_buffered,loop_rx_buffered;
  wire [1:0] ir_sd_internal={2{!reset_n_i}};
  genvar io_index;
  generate
    for(io_index=0;io_index<2;io_index=io_index+1) begin: g_z7010_board_io
      IBUF u_ir_rx_ibuf(.I(ir_rx_in_0[io_index]),.O(ir_rx_buffered[io_index]));
      (* DONT_TOUCH="TRUE" *) IBUF u_loop_rx_ibuf(
        .I(loop_rx_b0[io_index]),.O(loop_rx_buffered[io_index]));
      OBUF u_ir_tx_obuf(.I(physical_txd[io_index]),.O(ir_tx_out_0[io_index]));
      OBUF u_ir_sd_obuf(.I(ir_sd_internal[io_index]),.O(ir_sd_0[io_index]));
      OBUF u_ir_mode_obuf(.I(1'b1),.O(ir_mode_out_0[io_index]));
      OBUF u_loop_tx_obuf(.I(1'b0),.O(loop_tx_b0[io_index]));
      OBUF u_loop_sd_obuf(.I(1'b1),.O(loop_sd_b0[io_index]));
      OBUF u_loop_mode_obuf(.I(1'b1),.O(loop_mode_b0[io_index]));
    end
  endgenerate
  wire physical_attempt_valid;
  wire physical_attempt_lane;
  wire [15:0] physical_attempt_sequence;
  wire protocol_rx_event=^ir_rx_buffered;
  ir_endpoint_core #(.LANE_COUNT(P8E_Z7010_2LANE_DEV_LANE_COUNT),
    .WINDOW_SIZE(P8E_Z7010_2LANE_DEV_TX_WINDOW),
    .SACK_BITS(P8E_Z7010_2LANE_DEV_SACK_BITS),
    .PHYSICAL_MODULE_COUNT(P8E_Z7010_2LANE_DEV_PHYSICAL_MODULE_COUNT)) u_top(
    .protocol_clk_i,.axis_dma_clk_i,.axi_lite_clk_i,.reset_n_i,.global_permit_i,
    .endpoint_arm_request_i,.dma_tx_kick_i,.control_abort_i,.protocol_rx_event_i(protocol_rx_event),
    .protocol_ack_event_i,.stimulus_seed_i,.physical_txd_o(physical_txd),
    .physical_attempt_valid_o(physical_attempt_valid),
    .physical_attempt_lane_o(physical_attempt_lane),
    .physical_attempt_sequence_o(physical_attempt_sequence),
    .architecture_status_o,.clock_domain_status_o);
  wire unused=^{loop_rx_buffered,physical_attempt_valid,physical_attempt_lane,
    physical_attempt_sequence};
endmodule
