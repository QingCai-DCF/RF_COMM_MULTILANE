`timescale 1ns/1ps
module tb_ir_seq_math;
  import ir_seq_math_pkg::*;

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "SEQ_MATH_EXPECT_FAIL: %s", message);
  endtask

  initial begin
    check_expect(seq_distance(16'h0000, 16'hffff) == 16'h0001,
           "ffff-to-zero distance must wrap to one");
    check_expect(seq_distance(16'hffff, 16'h0000) == 16'hffff,
           "zero-to-ffff backward distance must wrap");
    check_expect(seq_before(16'hffff, 16'h0000), "ffff is immediately before zero");
    check_expect(!seq_before(16'h0000, 16'hffff), "zero is not before ffff");
    check_expect(!seq_before(16'h1234, 16'h1234), "equal values are not ordered");
    check_expect(seq_in_window(16'h0000, 16'hfff0, 16'd32),
           "wrapped value lies inside window");
    check_expect(!seq_in_window(16'h0020, 16'hfff0, 16'd32),
           "value outside wrapped window is rejected");
    check_expect(!seq_in_window(16'h0000, 16'h0000, 16'h8000),
           "half-space window is forbidden");
    for (int offset = 0; offset < 512; offset++) begin
      logic [15:0] value;
      value = 16'hff00 + offset;
      check_expect(seq_distance(value, 16'hff00) == offset[15:0],
             "distance is bit-exact across wrap");
      check_expect(seq_in_window(value, 16'hff00, 16'd512),
             "all 512 wrapped window members accepted");
    end
    $display("P8D_SEQUENCE_WIDTH_16_PASS=1");
    $display("P8D_SEQUENCE_WRAP_PASS=1");
    $display("TB_IR_SEQ_MATH_PASS=1");
    $finish;
  end
endmodule
