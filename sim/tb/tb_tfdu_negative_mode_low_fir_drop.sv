`timescale 1ns/1ps
module tb_tfdu_negative_mode_low_fir_drop;
  reg Txd;
  reg SD;
  reg Mode;
  reg optical_i;
  wire Rxd;

  tfdu6102_behavior_model #(.STARTUP_US(1)) dut (
    .Txd(Txd), .SD(SD), .Mode(Mode), .optical_i(optical_i), .optical_o(), .Rxd(Rxd),
    .startup_done(), .protect_fault()
  );

  task automatic check(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  initial begin
    Txd = 1'b0;
    SD = 1'b1;
    Mode = 1'b0;
    optical_i = 1'b0;
    #100;
    SD = 1'b0;
    #1200;
    optical_i = 1'b1;
    #125;
    optical_i = 1'b0;
    #500;
    check(Rxd == 1'b1, "Mode low drops FIR pulse and keeps Rxd idle");
    $display("TB_TFDU_NEGATIVE_MODE_LOW_FIR_DROP_PASS=1");
    $finish;
  end
endmodule
