`timescale 1ns/1ps
module tb_tfdu6102_pair_link_smoke;
  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst;
  reg enable;
  reg a_tx_req;
  reg a_tx_pulse;
  reg b_tx_req;
  reg b_tx_pulse;
  wire a_txd;
  wire a_sd;
  wire a_mode;
  wire b_txd;
  wire b_sd;
  wire b_mode;
  wire a_rxd;
  wire b_rxd;
  wire a_ready;
  wire b_ready;
  wire [31:0] a_rx_count;
  wire [31:0] b_rx_count;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2), .TXD_MAX_HIGH_US(20)) lane_a (
    .clk(clk), .rst(rst), .enable(enable), .tx_req(a_tx_req), .tx_pulse_in(a_tx_pulse), .rxd_i(a_rxd),
    .tx_ready(a_ready), .rx_ready(), .rx_raw_active(), .txd_o(a_txd), .sd_o(a_sd), .mode_o(a_mode),
    .startup_done(), .tx_stuck_fault(), .rx_pulse_count(a_rx_count), .rx_last_pulse_width_cycles(),
    .tx_high_max_cycles()
  );

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2), .TXD_MAX_HIGH_US(20)) lane_b (
    .clk(clk), .rst(rst), .enable(enable), .tx_req(b_tx_req), .tx_pulse_in(b_tx_pulse), .rxd_i(b_rxd),
    .tx_ready(b_ready), .rx_ready(), .rx_raw_active(), .txd_o(b_txd), .sd_o(b_sd), .mode_o(b_mode),
    .startup_done(), .tx_stuck_fault(), .rx_pulse_count(b_rx_count), .rx_last_pulse_width_cycles(),
    .tx_high_max_cycles()
  );

  tfdu6102_behavior_model #(.STARTUP_US(1)) a_to_b (
    .Txd(a_txd), .SD(a_sd), .Mode(a_mode), .optical_i(a_txd), .optical_o(), .Rxd(b_rxd),
    .startup_done(), .protect_fault()
  );

  tfdu6102_behavior_model #(.STARTUP_US(1)) b_to_a (
    .Txd(b_txd), .SD(b_sd), .Mode(b_mode), .optical_i(b_txd), .optical_o(), .Rxd(a_rxd),
    .startup_done(), .protect_fault()
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
    a_tx_req = 1'b0;
    a_tx_pulse = 1'b0;
    b_tx_req = 1'b0;
    b_tx_pulse = 1'b0;
    tick(3);
    rst = 1'b0;
    enable = 1'b1;
    #2000;
    tick(5);
    check(a_ready && b_ready, "both wrappers ready");
    a_tx_req = 1'b1;
    a_tx_pulse = 1'b1;
    tick(1);
    a_tx_pulse = 1'b0;
    tick(20);
    check(b_rx_count > 0, "A pulse increments B raw counter");
    b_tx_req = 1'b1;
    b_tx_pulse = 1'b1;
    tick(1);
    b_tx_pulse = 1'b0;
    tick(20);
    check(a_rx_count > 0, "B pulse increments A raw counter");
    enable = 1'b0;
    tick(2);
    check(a_sd == 1'b1 && b_sd == 1'b1, "shutdown stops both directions");
    $display("TB_TFDU6102_PAIR_LINK_SMOKE_PASS=1");
    $finish;
  end
endmodule
