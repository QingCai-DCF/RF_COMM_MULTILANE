`timescale 1ns/1ps
`default_nettype wire

module p10_1_buffer_pool #(
  parameter int unsigned BUFFER_COUNT = 8,
  localparam int unsigned INDEX_W = $clog2(BUFFER_COUNT)
) (
  input  logic                 clk,
  input  logic                 rst_n,
  input  logic                 allocate_i,
  output logic                 allocate_valid_o,
  output logic [INDEX_W-1:0]   allocate_index_o,
  output logic [31:0]          allocate_generation_o,
  input  logic                 reclaim_i,
  input  logic [INDEX_W-1:0]   reclaim_index_i,
  input  logic [31:0]          reclaim_generation_i,
  output logic [31:0]          free_count_o,
  output logic [63:0]          double_reclaim_count_o
);
  logic [BUFFER_COUNT-1:0] free_q;
  logic [31:0] generation_q [0:BUFFER_COUNT-1];
  integer search_index;
  integer reset_index;
  logic found;

  always_comb begin
    allocate_valid_o = 1'b0;
    allocate_index_o = '0;
    allocate_generation_o = '0;
    found = 1'b0;
    for (search_index = 0; search_index < BUFFER_COUNT;
         search_index = search_index + 1) begin
      if (!found && free_q[search_index]) begin
        found = 1'b1;
        allocate_valid_o = allocate_i;
        allocate_index_o = search_index[INDEX_W-1:0];
        allocate_generation_o = generation_q[search_index];
      end
    end
    free_count_o = $countones(free_q);
  end

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      free_q <= '1;
      double_reclaim_count_o <= '0;
      for (reset_index = 0; reset_index < BUFFER_COUNT;
           reset_index = reset_index + 1)
        generation_q[reset_index] <= '0;
    end else begin
      if (allocate_i && allocate_valid_o)
        free_q[allocate_index_o] <= 1'b0;
      if (reclaim_i) begin
        if (free_q[reclaim_index_i] ||
            generation_q[reclaim_index_i] != reclaim_generation_i)
          double_reclaim_count_o <= double_reclaim_count_o + 1'b1;
        else begin
          free_q[reclaim_index_i] <= 1'b1;
          generation_q[reclaim_index_i] <=
              generation_q[reclaim_index_i] + 1'b1;
        end
      end
    end
  end
endmodule

`default_nettype wire
