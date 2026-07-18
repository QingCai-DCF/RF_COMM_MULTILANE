`timescale 1ns/1ps
package ir_seq_math_pkg;
  localparam int unsigned IR_SEQUENCE_WIDTH = 16;
  localparam logic [15:0] IR_SEQUENCE_HALF_SPACE = 16'h8000;

  function automatic logic [15:0] seq_distance(
    input logic [15:0] seq_value,
    input logic [15:0] base
  );
    seq_distance = seq_value - base;
  endfunction

  function automatic logic seq_before(
    input logic [15:0] a,
    input logic [15:0] b
  );
    logic [15:0] distance;
    begin
      distance = b - a;
      seq_before = (distance != 16'd0) && (distance < IR_SEQUENCE_HALF_SPACE);
    end
  endfunction

  function automatic logic seq_in_window(
    input logic [15:0] seq_value,
    input logic [15:0] base,
    input logic [15:0] size
  );
    seq_in_window = (size != 16'd0) && (size < IR_SEQUENCE_HALF_SPACE) &&
                    ((seq_value - base) < size);
  endfunction
endpackage
