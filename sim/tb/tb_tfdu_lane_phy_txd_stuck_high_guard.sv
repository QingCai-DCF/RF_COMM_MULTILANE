`timescale 1ns/1ps
module tb_tfdu_lane_phy_txd_stuck_high_guard;
  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst;
  reg enable;
  reg tx_req;
  reg tx_pulse_in;
  wire txd_o;
  wire sd_o;
  wire startup_done;
  wire tx_stuck_fault;
  wire [31:0] tx_high_max_cycles;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2), .TXD_MAX_HIGH_US(3)) dut (
    .clk(clk),
    .rst(rst),
    .enable(enable),
    .tx_req(tx_req),
    .tx_pulse_in(tx_pulse_in),
    .rxd_i(1'b1),
    .tx_ready(),
    .rx_ready(),
    .rx_raw_active(),
    .txd_o(txd_o),
    .sd_o(sd_o),
    .mode_o(),
    .startup_done(startup_done),
    .tx_stuck_fault(tx_stuck_fault),
    .rx_pulse_count(),
    .rx_last_pulse_width_cycles(),
    .tx_high_max_cycles(tx_high_max_cycles)
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
    tx_req = 1'b0;
    tx_pulse_in = 1'b0;
    tick(2);
    rst = 1'b0;
    enable = 1'b1;
    tick(4);
    check(startup_done == 1'b1, "startup completes");
    tx_req = 1'b1;
    tx_pulse_in = 1'b1;
    tick(6);
    check(tx_stuck_fault == 1'b1, "continuous tx high trips sticky fault");
    check(tx_high_max_cycles >= 32'd3, "high stretch recorded");
    check(txd_o == 1'b0, "fault clamps txd_o low");
    check(sd_o == 1'b1, "fault returns lane to shutdown safe");
    $display("TB_TFDU_LANE_PHY_TXD_STUCK_HIGH_GUARD_PASS=1");
    $finish;
  end
endmodule
