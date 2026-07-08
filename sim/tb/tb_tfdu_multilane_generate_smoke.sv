`timescale 1ns/1ps
module tfdu_multilane_fixture #(
  parameter integer LANE_COUNT = 2,
  parameter integer LANE_MASK = 1
)(
  input wire clk,
  input wire rst,
  output wire [LANE_COUNT-1:0] txd,
  output wire [LANE_COUNT-1:0] sd
);
  genvar i;
  generate
    for (i = 0; i < LANE_COUNT; i = i + 1) begin : gen_lane
      wire lane_enable = ((LANE_MASK >> i) & 1) != 0;
      tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2)) lane (
        .clk(clk), .rst(rst), .enable(lane_enable), .tx_req(1'b0), .tx_pulse_in(1'b0), .rxd_i(1'b1),
        .tx_ready(), .rx_ready(), .rx_raw_active(), .txd_o(txd[i]), .sd_o(sd[i]), .mode_o(),
        .startup_done(), .tx_stuck_fault(), .rx_pulse_count(), .rx_last_pulse_width_cycles(),
        .tx_high_max_cycles()
      );
    end
  endgenerate
endmodule

module tb_tfdu_multilane_generate_smoke;
  reg clk = 1'b0;
  always #5 clk = ~clk;
  reg rst;
  wire [0:0] txd1;
  wire [0:0] sd1;
  wire [1:0] txd2;
  wire [1:0] sd2;
  wire [7:0] txd8;
  wire [7:0] sd8;

  tfdu_multilane_fixture #(.LANE_COUNT(1), .LANE_MASK(1)) lanes1 (.clk(clk), .rst(rst), .txd(txd1), .sd(sd1));
  tfdu_multilane_fixture #(.LANE_COUNT(2), .LANE_MASK(1)) lanes2 (.clk(clk), .rst(rst), .txd(txd2), .sd(sd2));
  tfdu_multilane_fixture #(.LANE_COUNT(8), .LANE_MASK(8'h05)) lanes8 (.clk(clk), .rst(rst), .txd(txd8), .sd(sd8));

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
    tick(2);
    rst = 1'b0;
    tick(5);
    check(sd1[0] == 1'b0, "LANE_COUNT=1 enabled lane releases shutdown");
    check(sd2[0] == 1'b0, "lane mask enables lane0");
    check(sd2[1] == 1'b1, "lane mask disables lane1 into safe shutdown");
    check(txd2[1] == 1'b0, "disabled lane1 holds txd low");
    check(sd8[0] == 1'b0 && sd8[2] == 1'b0, "8-lane mask enables selected lanes");
    check(sd8[1] == 1'b1 && sd8[3] == 1'b1 && sd8[7] == 1'b1, "8-lane mask disables other lanes");
    $display("TB_TFDU_MULTILANE_GENERATE_SMOKE_PASS=1");
    $finish;
  end
endmodule
