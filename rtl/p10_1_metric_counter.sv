`timescale 1ns/1ps
`default_nettype wire

module p10_1_metric_counter #(
  parameter int unsigned WIDTH = 64
) (
  input  logic                   clk,
  input  logic                   rst_n,
  input  logic                   clear_i,
  input  logic                   add_valid_i,
  input  logic [WIDTH-1:0]       add_value_i,
  output logic [WIDTH-1:0]       value_o,
  output logic                   wrap_o
);
  logic [WIDTH:0] sum;
  always_comb sum = {1'b0, value_o} + {1'b0, add_value_i};

  always_ff @(posedge clk) begin
    if (!rst_n || clear_i) begin
      value_o <= '0;
      wrap_o <= 1'b0;
    end else if (add_valid_i) begin
      value_o <= sum[WIDTH-1:0];
      wrap_o <= wrap_o | sum[WIDTH];
    end
  end
endmodule

`default_nettype wire
