`timescale 1ns/1ps
module tb_ir_4ppm_pulse_smoke;
  reg clk = 1'b0;
  always #5 clk = ~clk;

  reg rst;
  reg enable;
  reg [1:0] tx_symbol;
  reg tx_symbol_valid;
  wire tx_symbol_ready;
  wire tx_symbol_done;
  wire tx_pulse;
  wire txd_o;
  wire sd_o;
  wire mode_o;
  wire model_rxd;
  wire tx_stuck_fault;
  wire [31:0] rx_pulse_count;

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(4),
    .TX_PULSE_CYCLES(5),
    .DETECT_START_CYCLES(1),
    .DETECT_END_CYCLES(6)
  ) codec (
    .clk(clk),
    .rst_n(!rst),
    .enable(enable),
    .tx_symbol(tx_symbol),
    .tx_symbol_valid(tx_symbol_valid),
    .tx_symbol_ready(tx_symbol_ready),
    .tx_symbol_done(tx_symbol_done),
    .tx_preamble_valid(1'b0),
    .tx_preamble_ready(),
    .tx_preamble_done(),
    .tx_pulse(tx_pulse),
    .rx_align(1'b0),
    .rx_pulse_active(1'b0),
    .rx_symbol(),
    .rx_symbol_valid(),
    .rx_symbol_error(),
    .rx_preamble_valid(),
    .rx_preamble_count(),
    .rx_symbol_chips(),
    .debug_status()
  );

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2), .TXD_MAX_HIGH_US(20)) tx_lane (
    .clk(clk), .rst(rst), .enable(enable), .tx_req(1'b1), .tx_pulse_in(tx_pulse), .rxd_i(1'b1),
    .tx_ready(), .rx_ready(), .rx_raw_active(), .txd_o(txd_o), .sd_o(sd_o), .mode_o(mode_o),
    .startup_done(), .tx_stuck_fault(tx_stuck_fault), .rx_pulse_count(), .rx_last_pulse_width_cycles(),
    .tx_high_max_cycles()
  );

  tfdu6102_behavior_model #(.STARTUP_US(1)) model (
    .Txd(txd_o), .SD(sd_o), .Mode(mode_o), .optical_i(txd_o), .optical_o(), .Rxd(model_rxd),
    .startup_done(), .protect_fault()
  );

  tfdu_lane_phy_p2 #(.CLK_HZ(1_000_000), .STARTUP_US(2), .TXD_MAX_HIGH_US(20)) rx_lane (
    .clk(clk), .rst(rst), .enable(enable), .tx_req(1'b0), .tx_pulse_in(1'b0), .rxd_i(model_rxd),
    .tx_ready(), .rx_ready(), .rx_raw_active(), .txd_o(), .sd_o(), .mode_o(),
    .startup_done(), .tx_stuck_fault(), .rx_pulse_count(rx_pulse_count), .rx_last_pulse_width_cycles(),
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

  task automatic wait_ready;
    integer timeout;
    begin
      timeout = 0;
      while (!tx_symbol_ready && timeout < 1000) begin
        tick(1);
        timeout = timeout + 1;
      end
      check(timeout < 1000, "tx_symbol_ready timeout");
    end
  endtask

  task automatic wait_done;
    integer timeout;
    begin
      timeout = 0;
      while (!tx_symbol_done && timeout < 1000) begin
        tick(1);
        timeout = timeout + 1;
      end
      check(timeout < 1000, "tx_symbol_done timeout");
    end
  endtask

  initial begin
    rst = 1'b1;
    enable = 1'b0;
    tx_symbol = 2'b00;
    tx_symbol_valid = 1'b0;
    tick(3);
    rst = 1'b0;
    enable = 1'b1;
    #2000;
    wait_ready();
    tx_symbol = 2'b10;
    tx_symbol_valid = 1'b1;
    tick(1);
    tx_symbol_valid = 1'b0;
    wait_done();
    tick(30);
    check(rx_pulse_count > 0, "TFDU model converts one 4PPM pulse to low-active Rxd pulse");
    check(tx_stuck_fault == 1'b0, "4PPM pulse does not trip stuck-high guard");
    $display("TB_IR_4PPM_PULSE_SMOKE_PASS=1");
    $finish;
  end
endmodule
