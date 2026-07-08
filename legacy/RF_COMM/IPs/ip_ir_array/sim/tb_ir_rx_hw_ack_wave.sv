`timescale 1ns/1ps

module tb_ir_rx_hw_ack_wave;
  localparam int CNT_CHIP_MAX = 15;
  localparam int CHIP_CYCLES = CNT_CHIP_MAX + 1;
  localparam int RX_PULSE_CYCLES = 7;
  localparam int VISIBLE_PREAMBLE_SYMS = 85;
  localparam int PAYLOAD_BYTES = 13;
  localparam int FRAME_BYTES = 17;

  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic enable = 1'b0;
  logic ir_rx_in = 1'b1;
  logic [7:0] rx_tdata;
  logic rx_tvalid;
  logic rx_tready = 1'b1;
  logic rx_tlast;
  logic rx_active;
  logic crc_error;
  logic overrun_error;
  logic [31:0] debug_status;

  logic [7:0] frame [0:FRAME_BYTES-1];
  logic [7:0] expected [0:PAYLOAD_BYTES-1];
  logic [7:0] received [0:PAYLOAD_BYTES-1];
  int rx_count = 0;
  bit saw_last = 1'b0;

  always #5 clk = ~clk;

  ir_rx_4ppm_frame #(
    .MAX_FRAME_BYTES(32),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .PREAMBLE_SYMS(64),
    .EOF_SILENCE_SYMS(3),
    .DATA_PHASE_DELAY_CYCLES(0),
    .DETECT_START_CYCLES(0),
    .DETECT_END_CYCLES(10),
    .PREAMBLE_REALIGN_EDGE(0),
    .PREAMBLE_WAIT_FOR_DATA_SYMBOL(1)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .enable(enable),
    .ir_rx_in(ir_rx_in),
    .m_axis_tdata(rx_tdata),
    .m_axis_tvalid(rx_tvalid),
    .m_axis_tready(rx_tready),
    .m_axis_tlast(rx_tlast),
    .rx_active(rx_active),
    .crc_error(crc_error),
    .overrun_error(overrun_error),
    .debug_status(debug_status)
  );

  task automatic wait_cycles(input int cycles);
    repeat (cycles) @(posedge clk);
  endtask

  task automatic drive_chip(input bit pulse);
    if (pulse) begin
      ir_rx_in <= 1'b0;
      wait_cycles(RX_PULSE_CYCLES);
      ir_rx_in <= 1'b1;
      wait_cycles(CHIP_CYCLES - RX_PULSE_CYCLES);
    end else begin
      ir_rx_in <= 1'b1;
      wait_cycles(CHIP_CYCLES);
    end
  endtask

  task automatic drive_symbol(input logic [1:0] sym);
    int chip;
    for (chip = 0; chip < 4; chip = chip + 1) begin
      drive_chip(chip[1:0] == sym);
    end
  endtask

  task automatic drive_byte(input logic [7:0] data);
    drive_symbol(data[1:0]);
    drive_symbol(data[3:2]);
    drive_symbol(data[5:4]);
    drive_symbol(data[7:6]);
  endtask

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      rx_count <= 0;
      saw_last <= 1'b0;
    end else if (rx_tvalid && rx_tready) begin
      if (rx_count < PAYLOAD_BYTES) received[rx_count] <= rx_tdata;
      rx_count <= rx_count + 1;
      if (rx_tlast) saw_last <= 1'b1;
    end
  end

  initial begin
    frame[0]  = 8'hA5;
    frame[1]  = 8'h12;
    frame[2]  = 8'h03;
    frame[3]  = 8'h22;
    frame[4]  = 8'h01;
    frame[5]  = 8'h00;
    frame[6]  = 8'h02;
    frame[7]  = 8'h01;
    frame[8]  = 8'h00;
    frame[9]  = 8'h00;
    frame[10] = 8'h71;
    frame[11] = 8'h32;
    frame[12] = 8'h01;
    frame[13] = 8'hB3;
    frame[14] = 8'hED;
    frame[15] = 8'hDA;
    frame[16] = 8'hB7;

    for (int i = 0; i < PAYLOAD_BYTES; i = i + 1) begin
      expected[i] = frame[i];
    end

    wait_cycles(20);
    rst_n <= 1'b1;
    enable <= 1'b1;
    wait_cycles(20);

    for (int i = 0; i < VISIBLE_PREAMBLE_SYMS; i = i + 1) begin
      drive_symbol(2'b00);
    end

    for (int i = 0; i < FRAME_BYTES; i = i + 1) begin
      drive_byte(frame[i]);
    end

    ir_rx_in <= 1'b1;
    wait_cycles(CHIP_CYCLES * 16);
    wait_cycles(200);

    if (crc_error) begin
      $fatal(1, "CRC error asserted, debug=0x%08x", debug_status);
    end
    if (overrun_error) begin
      $fatal(1, "Overrun error asserted, debug=0x%08x", debug_status);
    end
    if (rx_count != PAYLOAD_BYTES) begin
      $display("DUT partial byte_cnt=%0d pair_cnt=%0d", dut.byte_cnt, dut.pair_cnt);
      for (int i = 0; i < FRAME_BYTES; i = i + 1) begin
        $display("DUT rx_buf[%0d]=0x%02x", i, dut.rx_buf[i]);
      end
      $fatal(1, "Expected %0d RX bytes, got %0d, debug=0x%08x", PAYLOAD_BYTES, rx_count, debug_status);
    end
    if (!saw_last) begin
      $fatal(1, "RX tlast was not observed, debug=0x%08x", debug_status);
    end
    for (int i = 0; i < PAYLOAD_BYTES; i = i + 1) begin
      if (received[i] !== expected[i]) begin
        $fatal(1, "RX byte[%0d] mismatch: got 0x%02x expected 0x%02x", i, received[i], expected[i]);
      end
    end

    $display("IR_RX_HW_ACK_WAVE_PASS bytes=%0d", rx_count);
    $finish;
  end
endmodule
