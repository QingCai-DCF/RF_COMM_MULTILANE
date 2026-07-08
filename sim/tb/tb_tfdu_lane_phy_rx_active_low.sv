`timescale 1ns/1ps
module tb_tfdu_lane_phy_rx_active_low;
  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst;
  reg enable;
  reg rxd_i;
  wire rx_raw_active;
  wire startup_done;
  wire [31:0] rx_pulse_count;
  wire [31:0] rx_last_pulse_width_cycles;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2)) dut (
    .clk(clk),
    .rst(rst),
    .enable(enable),
    .tx_req(1'b0),
    .tx_pulse_in(1'b0),
    .rxd_i(rxd_i),
    .tx_ready(),
    .rx_ready(),
    .rx_raw_active(rx_raw_active),
    .txd_o(),
    .sd_o(),
    .mode_o(),
    .startup_done(startup_done),
    .tx_stuck_fault(),
    .rx_pulse_count(rx_pulse_count),
    .rx_last_pulse_width_cycles(rx_last_pulse_width_cycles),
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
    rxd_i = 1'b1;
    tick(2);
    rst = 1'b0;
    enable = 1'b1;
    tick(5);
    check(startup_done == 1'b1, "startup completes");
    check(rx_raw_active == 1'b0, "rxd_i high is idle");
    rxd_i = 1'b0;
    tick(4);
    check(rx_raw_active == 1'b1, "rxd_i low is active");
    check(rx_pulse_count == 32'd1, "low-active pulse counted once");
    rxd_i = 1'b1;
    tick(4);
    check(rx_raw_active == 1'b0, "return high clears active");
    check(rx_last_pulse_width_cycles != 32'd0, "pulse width recorded");
    $display("TB_TFDU_LANE_PHY_RX_ACTIVE_LOW_PASS=1");
    $finish;
  end
endmodule
