`timescale 1ns/1ps
module tb_tfdu_negative_no_startup_tx;
  reg clk = 1'b0;
  always #5 clk = ~clk;
  reg rst;
  reg enable;
  wire txd_o;
  wire tx_ready;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(10)) dut (
    .clk(clk), .rst(rst), .enable(enable), .tx_req(1'b1), .tx_pulse_in(1'b1), .rxd_i(1'b1),
    .tx_ready(tx_ready), .rx_ready(), .rx_raw_active(), .txd_o(txd_o), .sd_o(), .mode_o(),
    .startup_done(), .tx_stuck_fault(), .rx_pulse_count(), .rx_last_pulse_width_cycles(),
    .tx_high_max_cycles()
  );

  task automatic tick(input integer n);
    repeat (n) @(posedge clk);
  endtask

  task automatic check(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  initial begin
    rst = 1'b1;
    enable = 1'b0;
    tick(2);
    rst = 1'b0;
    enable = 1'b1;
    tick(5);
    check(tx_ready == 1'b0, "startup not done keeps tx_ready low");
    check(txd_o == 1'b0, "startup not done blocks TX pulse");
    $display("TB_TFDU_NEGATIVE_NO_STARTUP_TX_PASS=1");
    $finish;
  end
endmodule
