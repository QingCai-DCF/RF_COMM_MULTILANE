`timescale 1ns/1ps
`default_nettype wire

module p10_1_event_fifo #(
  parameter int unsigned WIDTH = 64,
  parameter int unsigned DEPTH = 256,
  localparam int unsigned PTR_W = $clog2(DEPTH)
) (
  input  logic                 clk,
  input  logic                 rst_n,
  input  logic                 clear_i,
  input  logic                 push_i,
  input  logic [WIDTH-1:0]     push_data_i,
  input  logic                 pop_i,
  output logic [WIDTH-1:0]     pop_data_o,
  output logic                 empty_o,
  output logic                 full_o,
  output logic [PTR_W:0]       occupancy_o,
  output logic [31:0]          generation_o,
  output logic [63:0]          overflow_count_o
);
  logic [WIDTH-1:0] storage [0:DEPTH-1];
  logic [PTR_W-1:0] write_ptr_q;
  logic [PTR_W-1:0] read_ptr_q;

  initial begin
    if (DEPTH < 2 || (DEPTH & (DEPTH - 1)) != 0)
      $error("P10.1 event FIFO depth must be a power of two");
  end

  assign empty_o = occupancy_o == 0;
  assign full_o = occupancy_o == DEPTH;
  assign pop_data_o = empty_o ? '0 : storage[read_ptr_q];

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      write_ptr_q <= '0;
      read_ptr_q <= '0;
      occupancy_o <= '0;
      generation_o <= '0;
      overflow_count_o <= '0;
    end else if (clear_i) begin
      write_ptr_q <= '0;
      read_ptr_q <= '0;
      occupancy_o <= '0;
      generation_o <= generation_o + 1'b1;
      overflow_count_o <= '0;
    end else begin
      if (push_i && !full_o) begin
        storage[write_ptr_q] <= push_data_i;
        write_ptr_q <= write_ptr_q + 1'b1;
      end else if (push_i && full_o) begin
        // Trace loss is counted but never backpressures the data plane.
        overflow_count_o <= overflow_count_o + 1'b1;
      end
      if (pop_i && !empty_o)
        read_ptr_q <= read_ptr_q + 1'b1;
      unique case ({push_i && !full_o, pop_i && !empty_o})
        2'b10: occupancy_o <= occupancy_o + 1'b1;
        2'b01: occupancy_o <= occupancy_o - 1'b1;
        default: occupancy_o <= occupancy_o;
      endcase
    end
  end
endmodule

`default_nettype wire
