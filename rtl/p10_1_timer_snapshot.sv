`timescale 1ns/1ps
`default_nettype wire

module p10_1_timer_snapshot #(
  parameter int unsigned WIDTH = 64
) (
  input  logic                 clk,
  input  logic                 rst_n,
  input  logic                 object_reset_i,
  input  logic                 snapshot_i,
  output logic [WIDTH-1:0]     timer_o,
  output logic [WIDTH-1:0]     snapshot_o,
  output logic [31:0]          generation_o
);
  logic publish_pending_q;
  // object_reset_i is intentionally not used to clear the long-lived timer.
  logic object_reset_observed_q;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      timer_o <= '0;
      snapshot_o <= '0;
      generation_o <= '0;
      publish_pending_q <= 1'b0;
      object_reset_observed_q <= 1'b0;
    end else begin
      timer_o <= timer_o + 1'b1;
      object_reset_observed_q <= object_reset_observed_q | object_reset_i;
      if (snapshot_i && !publish_pending_q) begin
        generation_o <= generation_o + 1'b1; // odd: update in progress
        snapshot_o <= timer_o;
        publish_pending_q <= 1'b1;
      end else if (publish_pending_q) begin
        generation_o <= generation_o + 1'b1; // even: coherent snapshot
        publish_pending_q <= 1'b0;
      end
    end
  end
endmodule

`default_nettype wire
