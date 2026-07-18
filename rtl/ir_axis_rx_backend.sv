`timescale 1ns/1ps
module ir_axis_rx_backend #(
  parameter int DATA_WIDTH = 64,
  parameter int USER_WIDTH = 64
) (
  input  logic                      clk,
  input  logic                      rst_n,
  input  logic                      clear_counters_i,
  input  logic                      descriptor_valid_i,
  output logic                      descriptor_ready_o,
  input  logic [31:0]               descriptor_length_i,
  input  logic [USER_WIDTH-1:0]     descriptor_user_i,
  input  logic                      s_axis_tvalid_i,
  output logic                      s_axis_tready_o,
  input  logic [DATA_WIDTH-1:0]     s_axis_tdata_i,
  input  logic [DATA_WIDTH/8-1:0]   s_axis_tkeep_i,
  input  logic                      s_axis_tlast_i,
  input  logic [USER_WIDTH-1:0]     s_axis_tuser_i,
  output logic                      m_axis_tvalid_o,
  input  logic                      m_axis_tready_i,
  output logic [DATA_WIDTH-1:0]     m_axis_tdata_o,
  output logic [DATA_WIDTH/8-1:0]   m_axis_tkeep_o,
  output logic                      m_axis_tlast_o,
  output logic [USER_WIDTH-1:0]     m_axis_tuser_o,
  output logic                      descriptor_complete_pulse_o,
  output logic                      protocol_error_pulse_o,
  output logic [31:0]               stall_cycles_o,
  output logic [31:0]               protocol_error_count_o,
  output logic [31:0]               packet_count_o
);
  ir_axis_tx_frontend #(.DATA_WIDTH(DATA_WIDTH), .USER_WIDTH(USER_WIDTH)) u_elastic (
    .clk(clk), .rst_n(rst_n), .clear_counters_i(clear_counters_i),
    .descriptor_valid_i(descriptor_valid_i), .descriptor_ready_o(descriptor_ready_o),
    .descriptor_length_i(descriptor_length_i), .descriptor_user_i(descriptor_user_i),
    .s_axis_tvalid_i(s_axis_tvalid_i), .s_axis_tready_o(s_axis_tready_o),
    .s_axis_tdata_i(s_axis_tdata_i), .s_axis_tkeep_i(s_axis_tkeep_i),
    .s_axis_tlast_i(s_axis_tlast_i), .s_axis_tuser_i(s_axis_tuser_i),
    .m_axis_tvalid_o(m_axis_tvalid_o), .m_axis_tready_i(m_axis_tready_i),
    .m_axis_tdata_o(m_axis_tdata_o), .m_axis_tkeep_o(m_axis_tkeep_o),
    .m_axis_tlast_o(m_axis_tlast_o), .m_axis_tuser_o(m_axis_tuser_o),
    .descriptor_complete_pulse_o(descriptor_complete_pulse_o),
    .protocol_error_pulse_o(protocol_error_pulse_o), .stall_cycles_o(stall_cycles_o),
    .protocol_error_count_o(protocol_error_count_o), .packet_count_o(packet_count_o)
  );
endmodule
