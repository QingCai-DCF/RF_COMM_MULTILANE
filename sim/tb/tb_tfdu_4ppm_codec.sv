`timescale 1ns/1ps
module tb_tfdu_4ppm_codec;
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
  logic rx_align;
  logic rx_pulse_active;
  logic [1:0] rx_symbol;
  logic rx_symbol_valid;
  logic rx_symbol_error;
  logic rx_preamble_valid;
  logic [15:0] rx_preamble_count;
  logic [3:0] rx_symbol_chips;
  logic [31:0] debug_status;
  int saw_error;

  ir_4ppm_codec #(
    .CNT_CHIP_MAX(1),
    .CNT_PREAMBLE(4),
    .TX_PULSE_CYCLES(1),
    .DETECT_START_CYCLES(0),
    .DETECT_END_CYCLES(1)
  ) dut (
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
    .rx_align(rx_align),
    .rx_pulse_active(rx_pulse_active),
    .rx_symbol(rx_symbol),
    .rx_symbol_valid(rx_symbol_valid),
    .rx_symbol_error(rx_symbol_error),
    .rx_preamble_valid(rx_preamble_valid),
    .rx_preamble_count(rx_preamble_count),
    .rx_symbol_chips(rx_symbol_chips),
    .debug_status(debug_status)
  );

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

  task automatic expect(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic tick(input int n);
    repeat (n) @(posedge clk);
  endtask

  task automatic send_tx_symbol(input logic [1:0] sym);
    int pulses;
    begin
      pulses = 0;
      wait (tx_symbol_ready);
      tx_symbol <= sym;
      tx_symbol_valid <= 1'b1;
      tick(1);
      tx_symbol_valid <= 1'b0;
      while (!tx_symbol_done) begin
        if (tx_pulse) pulses++;
        tick(1);
      end
      tick(1);
      expect(pulses == 1, "4PPM TX emits one pulse per symbol");
    end
  endtask

  task automatic send_tx_preamble;
    int pulses;
    int timeout;
    begin
      pulses = 0;
      timeout = 0;
      wait (tx_preamble_ready);
      tx_preamble_valid <= 1'b1;
      tick(1);
      tx_preamble_valid <= 1'b0;
      while (!tx_preamble_done && timeout < 80) begin
        if (tx_pulse) pulses++;
        tick(1);
        timeout++;
      end
      expect(tx_preamble_done, "4PPM TX preamble completes");
      expect(pulses == 4, "4PPM TX preamble emits CNT_PREAMBLE one-hot symbols");
      tick(1);
    end
  endtask

  task automatic drive_rx_symbol(input logic [1:0] sym);
    logic [3:0] chips;
    int i;
    begin
      chips = ref_encode(sym);
      rx_align <= 1'b1;
      tick(1);
      rx_align <= 1'b0;
      for (i = 0; i < 4; i++) begin
        rx_pulse_active <= chips[3 - i];
        tick(1);
        rx_pulse_active <= 1'b0;
        tick(1);
      end
      tick(1);
      expect(rx_symbol_valid, "4PPM RX reports a valid symbol");
      expect(!rx_symbol_error, "4PPM RX reports no error for one-hot symbol");
      expect(rx_symbol == sym, "4PPM RX symbol matches encoded input");
      expect(rx_symbol_chips == chips, "4PPM RX captured expected chip pattern");
    end
  endtask

  task automatic drive_rx_preamble;
    logic [3:0] chips;
    int sym;
    int i;
    int timeout;
    begin
      chips = ref_encode(2'b00);
      rx_align <= 1'b1;
      tick(1);
      rx_align <= 1'b0;
      for (sym = 0; sym < 4; sym++) begin
        for (i = 0; i < 4; i++) begin
          rx_pulse_active <= chips[3 - i];
          tick(1);
          rx_pulse_active <= 1'b0;
          tick(1);
        end
      end
      timeout = 0;
      while (!rx_preamble_valid && timeout < 20) begin
        tick(1);
        timeout++;
      end
      expect(rx_preamble_valid, "4PPM RX detects CNT_PREAMBLE repeated preamble symbols");
      expect(rx_preamble_count == 16'd4, "4PPM RX preamble count saturates at CNT_PREAMBLE");
      tick(1);
    end
  endtask

  initial begin
    rst_n = 1'b0;
    enable = 1'b0;
    tx_symbol = 2'b00;
    tx_symbol_valid = 1'b0;
    tx_preamble_valid = 1'b0;
    rx_align = 1'b0;
    rx_pulse_active = 1'b0;
    tick(3);

    rst_n = 1'b1;
    enable = 1'b1;
    tick(2);

    send_tx_symbol(2'b00);
    send_tx_symbol(2'b01);
    send_tx_symbol(2'b10);
    send_tx_symbol(2'b11);
    send_tx_preamble();

    drive_rx_symbol(2'b00);
    drive_rx_symbol(2'b01);
    drive_rx_symbol(2'b10);
    drive_rx_symbol(2'b11);
    drive_rx_preamble();

    rx_align <= 1'b1;
    tick(1);
    rx_align <= 1'b0;
    saw_error = 0;
    rx_pulse_active <= 1'b1;
    tick(1);
    if (rx_symbol_error) saw_error = 1;
    tick(1);
    if (rx_symbol_error) saw_error = 1;
    rx_pulse_active <= 1'b1;
    tick(1);
    if (rx_symbol_error) saw_error = 1;
    tick(1);
    if (rx_symbol_error) saw_error = 1;
    rx_pulse_active <= 1'b0;
    repeat (5) begin
      tick(1);
      if (rx_symbol_error) saw_error = 1;
    end
    expect(saw_error != 0, "invalid multi-pulse symbol is rejected");

    $display("M2_4PPM_PREAMBLE_PATH_PASS=1");
    $display("TB_TFDU_4PPM_CODEC_PASS=1");
    $finish;
  end
endmodule
