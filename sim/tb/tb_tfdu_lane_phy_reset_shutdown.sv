`timescale 1ns/1ps
module tb_tfdu_lane_phy_reset_shutdown;
  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst;
  reg enable;
  reg tx_req;
  reg tx_pulse_in;
  reg rxd_i;
  wire tx_ready;
  wire rx_ready;
  wire rx_raw_active;
  wire txd_o;
  wire sd_o;
  wire mode_o;
  wire startup_done;
  wire tx_stuck_fault;
  wire [31:0] rx_pulse_count;
  wire [31:0] rx_last_pulse_width_cycles;
  wire [31:0] tx_high_max_cycles;

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(5)) dut (
    .clk(clk),
    .rst(rst),
    .enable(enable),
    .tx_req(tx_req),
    .tx_pulse_in(tx_pulse_in),
    .rxd_i(rxd_i),
    .tx_ready(tx_ready),
    .rx_ready(rx_ready),
    .rx_raw_active(rx_raw_active),
    .txd_o(txd_o),
    .sd_o(sd_o),
    .mode_o(mode_o),
    .startup_done(startup_done),
    .tx_stuck_fault(tx_stuck_fault),
    .rx_pulse_count(rx_pulse_count),
    .rx_last_pulse_width_cycles(rx_last_pulse_width_cycles),
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
    rxd_i = 1'b1;
    tick(2);
    check(txd_o == 1'b0, "reset drives txd_o low");
    check(sd_o == 1'b1, "reset drives sd_o shutdown high");
    check(mode_o == 1'b1, "reset drives static Mode high");
    check(startup_done == 1'b0, "reset clears startup_done");
    check(tx_ready == 1'b0, "reset clears tx_ready");
    check(rx_ready == 1'b0, "reset clears rx_ready");
    $display("TB_TFDU_LANE_PHY_RESET_SHUTDOWN_PASS=1");
    $finish;
  end
endmodule
