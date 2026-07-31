`timescale 1ns/1ps
`default_nettype wire

module p10_1_axis_sustained #(
  parameter int unsigned DATA_WIDTH = 32,
  localparam int unsigned KEEP_WIDTH = DATA_WIDTH / 8
) (
  input  logic                      clk,
  input  logic                      rst_n,
  input  logic                      clear_i,
  input  logic [DATA_WIDTH-1:0]     s_axis_tdata,
  input  logic [KEEP_WIDTH-1:0]     s_axis_tkeep,
  input  logic                      s_axis_tlast,
  input  logic                      s_axis_tvalid,
  output logic                      s_axis_tready,
  output logic [DATA_WIDTH-1:0]     m_axis_tdata,
  output logic [KEEP_WIDTH-1:0]     m_axis_tkeep,
  output logic                      m_axis_tlast,
  output logic                      m_axis_tvalid,
  input  logic                      m_axis_tready,
  output logic [63:0]               accepted_bytes_o,
  output logic [63:0]               accepted_beats_o,
  output logic [63:0]               stall_cycles_o,
  output logic [63:0]               first_beat_latency_o,
  output logic [63:0]               last_beat_latency_o
);
  logic [63:0] cycle_q;
  logic first_seen_q;
  integer byte_index;
  logic [7:0] accepted_byte_count;

  always_comb begin
    accepted_byte_count = '0;
    for (byte_index = 0; byte_index < KEEP_WIDTH; byte_index = byte_index + 1)
      accepted_byte_count = accepted_byte_count + s_axis_tkeep[byte_index];
  end

  // The monitor is a transparent skid-free stage. Metadata remains stable
  // because it is sourced directly from the upstream AXIS contract.
  assign s_axis_tready = m_axis_tready;
  assign m_axis_tdata = s_axis_tdata;
  assign m_axis_tkeep = s_axis_tkeep;
  assign m_axis_tlast = s_axis_tlast;
  assign m_axis_tvalid = s_axis_tvalid;

  always_ff @(posedge clk) begin
    if (!rst_n || clear_i) begin
      cycle_q <= '0;
      first_seen_q <= 1'b0;
      accepted_bytes_o <= '0;
      accepted_beats_o <= '0;
      stall_cycles_o <= '0;
      first_beat_latency_o <= '0;
      last_beat_latency_o <= '0;
    end else begin
      cycle_q <= cycle_q + 1'b1;
      if (s_axis_tvalid && !s_axis_tready)
        stall_cycles_o <= stall_cycles_o + 1'b1;
      if (s_axis_tvalid && s_axis_tready) begin
        accepted_bytes_o <= accepted_bytes_o + accepted_byte_count;
        accepted_beats_o <= accepted_beats_o + 1'b1;
        last_beat_latency_o <= cycle_q;
        if (!first_seen_q) begin
          first_seen_q <= 1'b1;
          first_beat_latency_o <= cycle_q;
        end
      end
    end
  end
endmodule

`default_nettype wire
