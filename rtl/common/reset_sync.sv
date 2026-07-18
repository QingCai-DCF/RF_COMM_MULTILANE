`timescale 1ns/1ps
// Asynchronous assertion, per-domain synchronous deassertion.
module reset_sync #(
  parameter int STAGES = 3
) (
  input  logic clk_i,
  input  logic async_reset_n_i,
  output logic reset_n_o
);
  (* ASYNC_REG="TRUE", SHREG_EXTRACT="NO" *) logic [STAGES-1:0] reset_pipe;
  initial if (STAGES < 2) $error("reset_sync requires at least two stages");
  always_ff @(posedge clk_i or negedge async_reset_n_i) begin
    if (!async_reset_n_i) reset_pipe <= '0;
    else reset_pipe <= {reset_pipe[STAGES-2:0], 1'b1};
  end
  assign reset_n_o = reset_pipe[STAGES-1];
endmodule
