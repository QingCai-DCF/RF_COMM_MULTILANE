module cdc_sync #(
  parameter int WIDTH = 1
)(
  input  logic             clk_dst,
  input  logic             rst_n,
  input  logic [WIDTH-1:0] data_in,
  output logic [WIDTH-1:0] data_out
);
  (* ASYNC_REG = "TRUE" *) logic [WIDTH-1:0] sync_ff1;
  (* ASYNC_REG = "TRUE" *) logic [WIDTH-1:0] sync_ff2;

  always_ff @(posedge clk_dst) begin
    if (!rst_n) begin
      sync_ff1 <= '0;
      sync_ff2 <= '0;
      data_out <= '0;
    end else begin
      sync_ff1 <= data_in;
      sync_ff2 <= sync_ff1;
      data_out <= sync_ff2;
    end
  end
endmodule
