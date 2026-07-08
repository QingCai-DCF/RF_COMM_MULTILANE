`timescale 1ns/1ps
module tb_tfdu_4ppm_model_integration;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic enable;
  logic [1:0] tx_symbol;
  logic tx_symbol_valid;
  logic tx_symbol_ready;
  logic tx_symbol_done;
  logic tx_preamble_valid;
  logic tx_preamble_ready;
  logic tx_preamble_done;
  logic tx_pulse;

  logic sd_n_shutdown;
  logic mode_high_speed;
  logic model_rxd;
  logic rx_align;
  logic [1:0] rx_symbol;
  logic rx_symbol_valid;
  logic rx_symbol_error;
  logic rx_preamble_valid;
  logic [15:0] rx_preamble_count;
  logic [3:0] rx_symbol_chips;

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(31),
    .CNT_PREAMBLE(4),
    .TX_PULSE_CYCLES(13),
    .DETECT_START_CYCLES(14),
    .DETECT_END_CYCLES(30)
  ) tx_codec (
    .clk(clk),
    .rst_n(rst_n),
    .enable(enable),
    .tx_symbol(tx_symbol),
    .tx_symbol_valid(tx_symbol_valid),
    .tx_symbol_ready(tx_symbol_ready),
    .tx_symbol_done(tx_symbol_done),
    .tx_preamble_valid(tx_preamble_valid),
    .tx_preamble_ready(tx_preamble_ready),
    .tx_preamble_done(tx_preamble_done),
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

  tfdu6102_behavior_model #(
    .STARTUP_US(1),
    .JITTER_NS(20),
    .PULSE_LOSS_PERMILLE(0),
    .LONG_HIGH_LIMIT_US(80),
    .NEAR_END_ECHO(1'b0)
  ) tfdu_model (
    .Txd(tx_pulse),
    .SD(sd_n_shutdown),
    .Mode(mode_high_speed),
    .Rxd(model_rxd)
  );

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(31),
    .CNT_PREAMBLE(4),
    .TX_PULSE_CYCLES(13),
    .DETECT_START_CYCLES(14),
    .DETECT_END_CYCLES(30)
  ) rx_codec (
    .clk(clk),
    .rst_n(rst_n),
    .enable(enable),
    .tx_symbol(2'b00),
    .tx_symbol_valid(1'b0),
    .tx_symbol_ready(),
    .tx_symbol_done(),
    .tx_preamble_valid(1'b0),
    .tx_preamble_ready(),
    .tx_preamble_done(),
    .tx_pulse(),
    .rx_align(rx_align),
    .rx_pulse_active(~model_rxd),
    .rx_symbol(rx_symbol),
    .rx_symbol_valid(rx_symbol_valid),
    .rx_symbol_error(rx_symbol_error),
    .rx_preamble_valid(rx_preamble_valid),
    .rx_preamble_count(rx_preamble_count),
    .rx_symbol_chips(rx_symbol_chips),
    .debug_status()
  );

  task automatic check_expect(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic tick(input int n);
    repeat (n) @(posedge clk);
  endtask

  function automatic logic [3:0] ref_encode(input logic [1:0] d);
    begin
      case (d)
        2'b00: ref_encode = 4'b1000;
        2'b01: ref_encode = 4'b0100;
        2'b10: ref_encode = 4'b0010;
        default: ref_encode = 4'b0001;
      endcase
    end
  endfunction

  task automatic send_symbol_through_model(input logic [1:0] sym);
    int timeout;
    begin
      rx_align <= 1'b1;
      tick(1);
      rx_align <= 1'b0;
      wait (tx_symbol_ready);
      tx_symbol <= sym;
      tx_symbol_valid <= 1'b1;
      tick(1);
      tx_symbol_valid <= 1'b0;
      timeout = 0;
      while (!rx_symbol_valid && !rx_symbol_error && timeout < 200) begin
        tick(1);
        timeout++;
      end
      check_expect(rx_symbol_valid, "model-coupled RX reports a valid 4PPM symbol");
      check_expect(!rx_symbol_error, "model-coupled RX reports no 4PPM symbol error");
      check_expect(rx_symbol == sym, "model-coupled RX symbol matches TX symbol");
      check_expect(rx_symbol_chips == ref_encode(sym), "model-coupled RX chips match 4PPM mapping");
      tick(2);
    end
  endtask

  task automatic send_preamble_through_model;
    int timeout;
    bit saw_done;
    bit saw_rx_preamble;
    logic [15:0] observed_preamble_count;
    begin
      rx_align <= 1'b1;
      tick(1);
      rx_align <= 1'b0;
      wait (tx_preamble_ready);
      tx_preamble_valid <= 1'b1;
      tick(1);
      tx_preamble_valid <= 1'b0;
      timeout = 0;
      saw_done = 1'b0;
      saw_rx_preamble = 1'b0;
      observed_preamble_count = 16'd0;
      while (!(saw_done && saw_rx_preamble) && !rx_symbol_error && timeout < 1200) begin
        if (tx_preamble_done) saw_done = 1'b1;
        if (rx_preamble_valid) begin
          saw_rx_preamble = 1'b1;
          observed_preamble_count = rx_preamble_count;
        end
        tick(1);
        timeout++;
      end
      if (tx_preamble_done) saw_done = 1'b1;
      if (rx_preamble_valid) begin
        saw_rx_preamble = 1'b1;
        observed_preamble_count = rx_preamble_count;
      end
      check_expect(saw_done, "model-coupled TX preamble completes");
      check_expect(saw_rx_preamble, "model-coupled RX detects CNT_PREAMBLE preamble symbols");
      check_expect(!rx_symbol_error, "model-coupled preamble reports no 4PPM symbol error");
      check_expect(observed_preamble_count == 16'd4, "model-coupled RX preamble count matches CNT_PREAMBLE");
      tick(2);
    end
  endtask

  initial begin
    rst_n = 1'b0;
    enable = 1'b0;
    tx_symbol = 2'b00;
    tx_symbol_valid = 1'b0;
    tx_preamble_valid = 1'b0;
    sd_n_shutdown = 1'b1;
    mode_high_speed = 1'b1;
    rx_align = 1'b0;
    tick(5);

    rst_n = 1'b1;
    enable = 1'b1;
    sd_n_shutdown = 1'b0;
    tick(120);
    check_expect(model_rxd == 1'b1, "TFDU model Rxd idles high after startup");

    send_preamble_through_model();
    send_symbol_through_model(2'b00);
    send_symbol_through_model(2'b01);
    send_symbol_through_model(2'b10);
    send_symbol_through_model(2'b11);

    $display("M2_4PPM_MODEL_PREAMBLE_PATH_PASS=1");
    $display("TB_TFDU_4PPM_MODEL_INTEGRATION_PASS=1");
    $finish;
  end
endmodule
