`timescale 1ns/1ps
module ir_sack_codec #(
  parameter int SACK_BITS = 64
) (
  input  logic [15:0]                ack_base_i,
  input  logic [SACK_BITS-1:0]       sack_bitmap_i,
  input  logic [$clog2(SACK_BITS):0] bitmap_width_i,
  input  logic [15:0]                query_sequence_i,
  output logic                       query_cumulative_acked_o,
  output logic                       query_sack_acked_o,
  output logic                       query_acked_o,
  output logic                       malformed_o
);
  import ir_seq_math_pkg::*;

  logic [15:0] distance;
  always_comb begin
    distance = seq_distance(query_sequence_i, ack_base_i);
    query_cumulative_acked_o = seq_before(query_sequence_i, ack_base_i);
    query_sack_acked_o = 1'b0;
    malformed_o = (bitmap_width_i < 32) || (bitmap_width_i > SACK_BITS);
    for (int bit_index = 0; bit_index < SACK_BITS; bit_index++) begin
      if ((bit_index >= bitmap_width_i) && sack_bitmap_i[bit_index]) begin
        malformed_o = 1'b1;
      end
    end
    if (!malformed_o && (distance < bitmap_width_i)) begin
      query_sack_acked_o = sack_bitmap_i[distance];
    end
    query_acked_o = !malformed_o &&
                    (query_cumulative_acked_o || query_sack_acked_o);
  end
endmodule
