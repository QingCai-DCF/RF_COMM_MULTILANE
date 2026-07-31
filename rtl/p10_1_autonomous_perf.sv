`timescale 1ns/1ps
`default_nettype wire

module p10_1_autonomous_perf #(
  parameter int unsigned DATA_WIDTH = 32
) (
  input  logic                     clk,
  input  logic                     rst_n,
  input  logic                     configure_i,
  input  logic [63:0]              total_bytes_i,
  input  logic [31:0]              seed_i,
  input  logic [31:0]              stream_id_i,
  input  logic [31:0]              object_id_i,
  input  logic [31:0]              generation_i,
  input  logic                     start_i,
  input  logic                     abort_i,
  output logic [DATA_WIDTH-1:0]    m_axis_tdata,
  output logic [DATA_WIDTH/8-1:0]  m_axis_tkeep,
  output logic                     m_axis_tlast,
  output logic                     m_axis_tvalid,
  input  logic                     m_axis_tready,
  input  logic [DATA_WIDTH-1:0]    verify_tdata_i,
  input  logic [DATA_WIDTH/8-1:0]  verify_tkeep_i,
  input  logic                     verify_tlast_i,
  input  logic                     verify_tvalid_i,
  output logic                     verify_tready_o,
  output logic                     active_o,
  output logic                     complete_o,
  output logic                     aborted_o,
  output logic [63:0]              generated_bytes_o,
  output logic [63:0]              verified_bytes_o,
  output logic [63:0]              pattern_error_count_o,
  output logic [63:0]              atomic_commit_count_o
);
  logic [63:0] configured_bytes_q;
  logic [31:0] seed_q;
  logic [31:0] stream_id_q;
  logic [31:0] object_id_q;
  logic [31:0] generation_q;
  logic [31:0] expected_verify_q;
  logic [7:0] keep_count;
  logic [7:0] generator_keep_count;
  integer keep_index;

  always_comb begin
    keep_count = '0;
    generator_keep_count = '0;
    for (keep_index = 0; keep_index < DATA_WIDTH/8; keep_index = keep_index + 1)
      keep_count = keep_count + verify_tkeep_i[keep_index];
    for (keep_index = 0; keep_index < DATA_WIDTH/8; keep_index = keep_index + 1)
      generator_keep_count =
          generator_keep_count + m_axis_tkeep[keep_index];
  end

  assign m_axis_tdata = (seed_q ^ stream_id_q ^ object_id_q ^ generation_q)
                        + generated_bytes_o[31:0];
  assign m_axis_tkeep = (configured_bytes_q - generated_bytes_o >= DATA_WIDTH/8)
      ? {DATA_WIDTH/8{1'b1}}
      : ((1 << (configured_bytes_q - generated_bytes_o)) - 1);
  assign m_axis_tlast = active_o &&
      generated_bytes_o + generator_keep_count >= configured_bytes_q;
  assign m_axis_tvalid = active_o;
  assign verify_tready_o = active_o;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      configured_bytes_q <= '0;
      seed_q <= '0;
      stream_id_q <= '0;
      object_id_q <= '0;
      generation_q <= '0;
      expected_verify_q <= '0;
      active_o <= 1'b0;
      complete_o <= 1'b0;
      aborted_o <= 1'b0;
      generated_bytes_o <= '0;
      verified_bytes_o <= '0;
      pattern_error_count_o <= '0;
      atomic_commit_count_o <= '0;
    end else begin
      if (configure_i && !active_o) begin
        configured_bytes_q <= total_bytes_i;
        seed_q <= seed_i;
        stream_id_q <= stream_id_i;
        object_id_q <= object_id_i;
        generation_q <= generation_i;
      end
      if (start_i && !active_o && configured_bytes_q != 0) begin
        active_o <= 1'b1;
        complete_o <= 1'b0;
        aborted_o <= 1'b0;
        generated_bytes_o <= '0;
        verified_bytes_o <= '0;
        expected_verify_q <= seed_q ^ stream_id_q ^ object_id_q ^ generation_q;
      end
      if (abort_i && active_o) begin
        active_o <= 1'b0;
        aborted_o <= 1'b1;
        complete_o <= 1'b0;
      end
      if (m_axis_tvalid && m_axis_tready)
        generated_bytes_o <= generated_bytes_o + generator_keep_count;
      if (verify_tvalid_i && verify_tready_o) begin
        if (verify_tdata_i != expected_verify_q)
          pattern_error_count_o <= pattern_error_count_o + 1'b1;
        verified_bytes_o <= verified_bytes_o + keep_count;
        expected_verify_q <= expected_verify_q + DATA_WIDTH/8;
        if (verify_tlast_i) begin
          active_o <= 1'b0;
          complete_o <= pattern_error_count_o == 0;
          if (pattern_error_count_o == 0)
            atomic_commit_count_o <= atomic_commit_count_o + 1'b1;
        end
      end
    end
  end
endmodule

`default_nettype wire
