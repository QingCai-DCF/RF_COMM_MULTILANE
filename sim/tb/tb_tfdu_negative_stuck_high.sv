`timescale 1ns/1ps
module tb_tfdu_negative_stuck_high;
  reg clk = 1'b0;
  always #5 clk = ~clk;
  reg rst;
  reg enable;
  wire txd_o;
  wire sd_o;
  wire tx_stuck_fault;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2), .TXD_MAX_HIGH_US(3)) dut (
    .clk(clk), .rst(rst), .enable(enable), .tx_req(1'b1), .tx_pulse_in(1'b1), .rxd_i(1'b1),
    .tx_ready(), .rx_ready(), .rx_raw_active(), .txd_o(txd_o), .sd_o(sd_o), .mode_o(),
    .startup_done(), .tx_stuck_fault(tx_stuck_fault), .rx_pulse_count(), .rx_last_pulse_width_cycles(),
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
    tick(10);
    check(tx_stuck_fault == 1'b1, "stuck-high fault is reported");
    check(txd_o == 1'b0, "fault blocks TX output");
    check(sd_o == 1'b1, "fault returns shutdown safe");
    $display("TB_TFDU_NEGATIVE_STUCK_HIGH_PASS=1");
    $finish;
  end
endmodule
