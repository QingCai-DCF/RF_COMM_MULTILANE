`timescale 1ns/1ps
module level_sync #(
  parameter int STAGES = 2,
  parameter logic RESET_VALUE = 1'b0
) (
  input  logic clk_i,
  input  logic reset_n_i,
  input  logic async_level_i,
  output logic level_o
);
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [STAGES-1:0] sync_pipe;
  initial if (STAGES < 2) $error("level_sync requires at least two stages");
  always_ff @(posedge clk_i or negedge reset_n_i) begin
    if (!reset_n_i) sync_pipe <= {STAGES{RESET_VALUE}};
    else sync_pipe <= {sync_pipe[STAGES-2:0], async_level_i};
  end
  assign level_o = sync_pipe[STAGES-1];
endmodule
