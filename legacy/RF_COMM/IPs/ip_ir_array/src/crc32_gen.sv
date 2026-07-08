
import ir_protocol_pkg::*;

module crc32_gen (
  input  logic        clk,
  input  logic        rst_n,
  input  logic        init,
  input  logic        calc,
  input  logic [7:0]  data_in,
  output logic [31:0] crc_out
);
  logic [31:0] crc_reg;

  always_ff @(posedge clk) begin
    if (!rst_n)       crc_reg <= 32'hFFFF_FFFF;
    else if (init)    crc_reg <= 32'hFFFF_FFFF;
    else if (calc)    crc_reg <= crc32_next_byte(data_in, crc_reg);
  end

  assign crc_out = crc_reg;
endmodule
