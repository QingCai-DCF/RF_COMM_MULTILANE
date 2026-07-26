`timescale 1ns/1ps
module tb_tfdu_lane_phy_smoke;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic enable_phy;
  logic clear_sticky;
  logic tx_pulse_req;
  logic rxd;
  logic Txd;
  logic SD;
  logic Mode;
  logic phy_ready;
  logic rx_pulse_active;
  logic startup_done;
  logic shutdown_active;
  logic fault_stuck_high;
  logic fault_duty_limit;
  logic [31:0] rx_raw_count;
  logic [31:0] tx_pulse_count;
  logic [31:0] rx_pulse_width_min;
  logic [31:0] rx_pulse_width_max;
  logic [31:0] rx_last_timestamp;
  logic [31:0] tx_high_width_current;
  logic [31:0] duty_window_count;
  logic [31:0] duty_high_count;
  logic [31:0] tx_high_width_max_seen;
  logic [31:0] duty_high_max_seen;
  logic [31:0] duty_hard_limit_cycles;
  logic [31:0] duty_target_limit_cycles;
  logic [31:0] duty_headroom_cycles;
  logic [31:0] duty_target_throttle_count;
  logic [31:0] duty_hard_fault_count;

  logic duty_rst_n;
  logic duty_enable_phy;
  logic duty_tx_pulse_req;
  logic duty_rxd;
  logic duty_Txd;
  logic duty_SD;
  logic duty_Mode;
  logic duty_phy_ready;
  logic duty_fault_stuck_high;
  logic duty_fault_duty_limit;

  tfdu_lane_phy #(
    .CLK_HZ(1_000_000),
    .TFDU_STARTUP_US(5),
    .TX_STUCK_HIGH_LIMIT_US(3),
    .DUTY_WINDOW_US(20),
    .DUTY_MAX_PERMILLE(1000)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .enable_phy(enable_phy),
    .clear_sticky(clear_sticky),
    .tx_pulse_req(tx_pulse_req),
    .rxd(rxd),
    .Txd(Txd),
    .SD(SD),
    .Mode(Mode),
    .phy_ready(phy_ready),
    .rx_pulse_active(rx_pulse_active),
    .startup_done(startup_done),
    .shutdown_active(shutdown_active),
    .fault_stuck_high(fault_stuck_high),
    .fault_duty_limit(fault_duty_limit),
    .rx_raw_count(rx_raw_count),
    .tx_pulse_count(tx_pulse_count),
    .rx_pulse_width_min(rx_pulse_width_min),
    .rx_pulse_width_max(rx_pulse_width_max),
    .rx_last_timestamp(rx_last_timestamp),
    .tx_high_width_current(tx_high_width_current),
    .duty_window_count(duty_window_count),
    .duty_high_count(duty_high_count),
    .tx_high_width_max_seen(tx_high_width_max_seen),
    .duty_high_max_seen(duty_high_max_seen),
    .duty_hard_limit_cycles(duty_hard_limit_cycles),
    .duty_target_limit_cycles(duty_target_limit_cycles),
    .duty_headroom_cycles(duty_headroom_cycles),
    .duty_target_throttle_count(duty_target_throttle_count),
    .duty_hard_fault_count(duty_hard_fault_count)
  );

  tfdu_lane_phy #(
    .CLK_HZ(1_000_000),
    .TFDU_STARTUP_US(2),
    .TX_STUCK_HIGH_LIMIT_US(50),
    .DUTY_WINDOW_US(10),
    .DUTY_MAX_PERMILLE(300)
  ) duty_dut (
    .clk(clk),
    .rst_n(duty_rst_n),
    .enable_phy(duty_enable_phy),
    .clear_sticky(1'b0),
    .tx_pulse_req(duty_tx_pulse_req),
    .rxd(duty_rxd),
    .Txd(duty_Txd),
    .SD(duty_SD),
    .Mode(duty_Mode),
    .phy_ready(duty_phy_ready),
    .rx_pulse_active(),
    .startup_done(),
    .shutdown_active(),
    .fault_stuck_high(duty_fault_stuck_high),
    .fault_duty_limit(duty_fault_duty_limit),
    .rx_raw_count(),
    .tx_pulse_count(),
    .rx_pulse_width_min(),
    .rx_pulse_width_max(),
    .rx_last_timestamp(),
    .tx_high_width_current(),
    .duty_window_count(),
    .duty_high_count(),
    .tx_high_width_max_seen(),
    .duty_high_max_seen(),
    .duty_hard_limit_cycles(),
    .duty_target_limit_cycles(),
    .duty_headroom_cycles(),
    .duty_target_throttle_count(),
    .duty_hard_fault_count()
  );

  task automatic check_expect(input bit cond, input string msg);
    if (!cond) begin
      $fatal(1, "EXPECT_FAIL: %s", msg);
    end
  endtask

  task automatic tick(input int n);
    repeat (n) @(posedge clk);
  endtask

  initial begin
    rst_n = 1'b0;
    enable_phy = 1'b0;
    clear_sticky = 1'b0;
    tx_pulse_req = 1'b0;
    rxd = 1'b1;
    duty_rst_n = 1'b0;
    duty_enable_phy = 1'b0;
    duty_tx_pulse_req = 1'b0;
    duty_rxd = 1'b1;
    tick(2);

    check_expect(SD == 1'b1, "reset drives shutdown");
    check_expect(Txd == 1'b0, "reset drives Txd idle low");
    check_expect(Mode == 1'b1, "static high-speed Mode=1");

    rst_n = 1'b1;
    enable_phy = 1'b1;
    tick(19);
    check_expect(phy_ready == 1'b0, "phy_ready stays low before startup delay");
    tick(3);
    check_expect(phy_ready == 1'b1, "phy_ready after startup delay");
    check_expect(SD == 1'b0, "SD released after enable");

    tx_pulse_req = 1'b1;
    tick(1);
    tx_pulse_req = 1'b0;
    tick(2);
    check_expect(tx_pulse_count == 32'd1, "tx_pulse_count increments on pulse start");

    rxd = 1'b0;
    tick(3);
    rxd = 1'b1;
    tick(4);
    check_expect(rx_raw_count == 32'd1, "low-active RX pulse increments raw counter");
    check_expect(rx_pulse_width_min != 32'd0, "RX pulse min width recorded");
    check_expect(rx_pulse_width_max >= rx_pulse_width_min, "RX pulse max width recorded");
    check_expect(rx_last_timestamp != 32'd0, "RX timestamp recorded");

    tx_pulse_req = 1'b1;
    tick(6);
    tx_pulse_req = 1'b0;
    tick(2);
    check_expect(fault_stuck_high == 1'b1, "long-high fault trips");
    check_expect(SD == 1'b1, "long-high fault forces shutdown");

    duty_rst_n = 1'b1;
    duty_enable_phy = 1'b1;
    tick(12);
    check_expect(duty_phy_ready == 1'b1, "duty DUT ready");
    duty_tx_pulse_req = 1'b1;
    tick(5);
    duty_tx_pulse_req = 1'b0;
    tick(2);
    check_expect(duty_fault_duty_limit == 1'b1, "duty-limit fault trips");
    check_expect(duty_SD == 1'b1, "duty-limit fault forces shutdown");

    $display("TB_TFDU_LANE_PHY_SMOKE_PASS=1");
    $finish;
  end
endmodule
