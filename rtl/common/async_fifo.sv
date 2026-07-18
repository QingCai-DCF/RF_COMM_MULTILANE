`timescale 1ns/1ps
// Power-of-two Gray-pointer asynchronous FIFO.  This primitive is reserved for
// sustained streams; pulse_sync/toggle_handshake are used for sparse control.
module async_fifo #(
  parameter int WIDTH = 64,
  parameter int DEPTH = 8
) (
  input  logic wr_clk_i,
  input  logic wr_reset_n_i,
  input  logic wr_valid_i,
  output logic wr_ready_o,
  input  logic [WIDTH-1:0] wr_data_i,
  input  logic rd_clk_i,
  input  logic rd_reset_n_i,
  output logic rd_valid_o,
  input  logic rd_ready_i,
  output logic [WIDTH-1:0] rd_data_o
);
  localparam int ADDR_WIDTH = $clog2(DEPTH);
  localparam int PTR_WIDTH = ADDR_WIDTH + 1;
  (* ram_style="distributed" *) logic [WIDTH-1:0] memory [0:DEPTH-1];
  logic [PTR_WIDTH-1:0] wr_binary, wr_gray, rd_binary, rd_gray;
  logic [PTR_WIDTH-1:0] wr_binary_next, wr_gray_next;
  logic [PTR_WIDTH-1:0] rd_binary_next, rd_gray_next;
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [PTR_WIDTH-1:0]
      rd_gray_sync1, rd_gray_sync2, wr_gray_sync1, wr_gray_sync2;
  logic full, empty;
  initial if (DEPTH < 4 || (DEPTH & (DEPTH-1)) != 0)
    $error("async_fifo DEPTH must be a power of two >=4");
  assign wr_binary_next = wr_binary + (wr_valid_i && wr_ready_o);
  assign wr_gray_next = (wr_binary_next >> 1) ^ wr_binary_next;
  assign rd_binary_next = rd_binary + (rd_valid_o && rd_ready_i);
  assign rd_gray_next = (rd_binary_next >> 1) ^ rd_binary_next;
  assign full = wr_gray_next ==
      {~rd_gray_sync2[PTR_WIDTH-1:PTR_WIDTH-2], rd_gray_sync2[PTR_WIDTH-3:0]};
  assign empty = rd_gray == wr_gray_sync2;
  assign wr_ready_o = !full;
  assign rd_valid_o = !empty;
  assign rd_data_o = memory[rd_binary[ADDR_WIDTH-1:0]];
  always_ff @(posedge wr_clk_i or negedge wr_reset_n_i) begin
    if (!wr_reset_n_i) begin
      wr_binary <= '0; wr_gray <= '0; rd_gray_sync1 <= '0; rd_gray_sync2 <= '0;
    end else begin
      rd_gray_sync1 <= rd_gray; rd_gray_sync2 <= rd_gray_sync1;
      if (wr_valid_i && wr_ready_o)
        memory[wr_binary[ADDR_WIDTH-1:0]] <= wr_data_i;
      wr_binary <= wr_binary_next; wr_gray <= wr_gray_next;
    end
  end
  always_ff @(posedge rd_clk_i or negedge rd_reset_n_i) begin
    if (!rd_reset_n_i) begin
      rd_binary <= '0; rd_gray <= '0; wr_gray_sync1 <= '0; wr_gray_sync2 <= '0;
    end else begin
      wr_gray_sync1 <= wr_gray; wr_gray_sync2 <= wr_gray_sync1;
      rd_binary <= rd_binary_next; rd_gray <= rd_gray_next;
    end
  end
endmodule
