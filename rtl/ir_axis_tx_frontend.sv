`timescale 1ns/1ps
module ir_axis_tx_frontend #(
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
  localparam int KEEP_WIDTH = DATA_WIDTH / 8;
  logic descriptor_active;
  logic [31:0] expected_length;
  logic [31:0] byte_count;
  logic [USER_WIDTH-1:0] descriptor_user;
  logic buffer_valid;
  logic [DATA_WIDTH-1:0] buffer_data;
  logic [KEEP_WIDTH-1:0] buffer_keep;
  logic buffer_last;
  logic [USER_WIDTH-1:0] buffer_user;

  function automatic integer keep_bytes(input logic [KEEP_WIDTH-1:0] keep);
    integer count;
    begin
      count = 0;
      for (int byte_index = 0; byte_index < KEEP_WIDTH; byte_index++)
        if (keep[byte_index]) count = count + 1;
      keep_bytes = count;
    end
  endfunction

  function automatic logic keep_contiguous(input logic [KEEP_WIDTH-1:0] keep);
    logic seen_zero;
    begin
      seen_zero = 1'b0;
      keep_contiguous = (keep != '0);
      for (int byte_index = 0; byte_index < KEEP_WIDTH; byte_index++) begin
        if (!keep[byte_index]) seen_zero = 1'b1;
        else if (seen_zero) keep_contiguous = 1'b0;
      end
    end
  endfunction

  assign descriptor_ready_o = !descriptor_active && !buffer_valid;
  assign s_axis_tready_o = descriptor_active && (!buffer_valid || m_axis_tready_i);
  assign m_axis_tvalid_o = buffer_valid;
  assign m_axis_tdata_o = buffer_data;
  assign m_axis_tkeep_o = buffer_keep;
  assign m_axis_tlast_o = buffer_last;
  assign m_axis_tuser_o = buffer_user;

  always_ff @(posedge clk or negedge rst_n) begin
    integer beat_bytes;
    logic malformed;
    if (!rst_n) begin
      descriptor_active <= 1'b0;
      expected_length <= 32'd0;
      byte_count <= 32'd0;
      descriptor_user <= '0;
      buffer_valid <= 1'b0;
      buffer_data <= '0;
      buffer_keep <= '0;
      buffer_last <= 1'b0;
      buffer_user <= '0;
      descriptor_complete_pulse_o <= 1'b0;
      protocol_error_pulse_o <= 1'b0;
      stall_cycles_o <= 32'd0;
      protocol_error_count_o <= 32'd0;
      packet_count_o <= 32'd0;
    end else begin
      descriptor_complete_pulse_o <= 1'b0;
      protocol_error_pulse_o <= 1'b0;
      if (clear_counters_i) begin
        stall_cycles_o <= 32'd0;
        protocol_error_count_o <= 32'd0;
        packet_count_o <= 32'd0;
      end
      if (buffer_valid && !m_axis_tready_i) stall_cycles_o <= stall_cycles_o + 1'b1;
      if (buffer_valid && m_axis_tready_i) buffer_valid <= 1'b0;
      if (descriptor_valid_i && descriptor_ready_o) begin
        descriptor_active <= (descriptor_length_i != 0);
        expected_length <= descriptor_length_i;
        byte_count <= 32'd0;
        descriptor_user <= descriptor_user_i;
        if (descriptor_length_i == 0) begin
          protocol_error_pulse_o <= 1'b1;
          protocol_error_count_o <= protocol_error_count_o + 1'b1;
        end
      end
      if (s_axis_tvalid_i && s_axis_tready_o) begin
        beat_bytes = keep_bytes(s_axis_tkeep_i);
        malformed = !keep_contiguous(s_axis_tkeep_i) ||
                    (!s_axis_tlast_i && s_axis_tkeep_i != {KEEP_WIDTH{1'b1}}) ||
                    (s_axis_tlast_i && (byte_count + beat_bytes != expected_length)) ||
                    (!s_axis_tlast_i && (byte_count + beat_bytes >= expected_length)) ||
                    (s_axis_tuser_i != descriptor_user);
        buffer_valid <= 1'b1;
        buffer_data <= s_axis_tdata_i;
        buffer_keep <= s_axis_tkeep_i;
        buffer_last <= s_axis_tlast_i;
        buffer_user <= s_axis_tuser_i;
        byte_count <= byte_count + beat_bytes;
        if (malformed) begin
          protocol_error_pulse_o <= 1'b1;
          protocol_error_count_o <= protocol_error_count_o + 1'b1;
        end
        if (s_axis_tlast_i) begin
          descriptor_active <= 1'b0;
          descriptor_complete_pulse_o <= !malformed;
          if (!malformed) packet_count_o <= packet_count_o + 1'b1;
        end
      end
    end
  end
endmodule
