`timescale 1ns/1ps
module tb_tfdu_lane_phy_startup_gate;
  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst;
  reg enable;
  reg tx_req;
  reg tx_pulse_in;
  wire tx_ready;
  wire rx_ready;
  wire txd_o;
  wire sd_o;
  wire startup_done;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(5)) dut (
    .clk(clk),
    .rst(rst),
    .enable(enable),
    .tx_req(tx_req),
    .tx_pulse_in(tx_pulse_in),
    .rxd_i(1'b1),
    .tx_ready(tx_ready),
    .rx_ready(rx_ready),
    .rx_raw_active(),
    .txd_o(txd_o),
    .sd_o(sd_o),
    .mode_o(),
    .startup_done(startup_done),
    .tx_stuck_fault(),
    .rx_pulse_count(),
    .rx_last_pulse_width_cycles(),
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
    tx_req = 1'b1;
    tx_pulse_in = 1'b1;
    tick(2);
    rst = 1'b0;
    enable = 1'b1;
    tick(1);
    check(sd_o == 1'b0, "enable releases shutdown");
    check(tx_ready == 1'b0, "tx_ready blocked before startup");
    check(rx_ready == 1'b0, "rx_ready blocked before startup");
    check(txd_o == 1'b0, "txd_o blocked before startup");
    tick(4);
    check(startup_done == 1'b1, "startup_done set after configured delay");
    check(tx_ready == 1'b1, "tx_ready set after startup");
    check(rx_ready == 1'b1, "rx_ready set after startup");
    $display("TB_TFDU_LANE_PHY_STARTUP_GATE_PASS=1");
    $finish;
  end
endmodule
