`timescale 1ns/1ps

module tb_ir_rx_ila_replay #(
  parameter int DETECT_START = 0,
  parameter int DETECT_END = 5,
  parameter int PHASE_DELAY = 0,
  parameter int REALIGN_EDGE = 0
);
  localparam int MAX_FRAME_BYTES = 269;

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

  int sample_count = 0;
  int byte_count = 0;
  int lane_idx = 0;
  bit saw_last = 1'b0;
  string csv_path;
  string rx_col;

  always #5 clk = ~clk;

  ir_rx_4ppm_frame #(
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES),
    .CNT_CHIP_MAX(7),
    .PREAMBLE_SYMS(64),
    .EOF_SILENCE_SYMS(3),
    .DATA_PHASE_DELAY_CYCLES(PHASE_DELAY),
    .DETECT_START_CYCLES(DETECT_START),
    .DETECT_END_CYCLES(DETECT_END),
    .PREAMBLE_REALIGN_EDGE(REALIGN_EDGE),
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

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      byte_count <= 0;
      saw_last <= 1'b0;
    end else if (rx_tvalid && rx_tready) begin
      if (byte_count < 32) begin
        $display("ILA_REPLAY_RX_BYTE idx=%0d data=0x%02x last=%0b t=%0t",
                 byte_count, rx_tdata, rx_tlast, $time);
      end
      byte_count <= byte_count + 1;
      if (rx_tlast) saw_last <= 1'b1;
    end
  end

  task automatic wait_clk(input int cycles);
    repeat (cycles) @(posedge clk);
  endtask

  task automatic drive_csv;
    int fd;
    int parsed;
    int sample_buf;
    int sample_win;
    int trigger;
    int a_tx;
    int a_rx;
    int a_sd;
    int a_mode;
    int b_tx;
    int b_rx;
    int b_sd;
    int b_mode;
    int b_debug;
    string line;
    logic [1:0] selected_rx;
    begin
      fd = $fopen(csv_path, "r");
      if (fd == 0) begin
        $fatal(1, "Unable to open ILA CSV: %s", csv_path);
      end

      while (!$feof(fd)) begin
        void'($fgets(line, fd));
        parsed = $sscanf(line, "%d,%d,%d,%h,%h,%h,%h,%h,%h,%h,%h,%h",
                         sample_buf, sample_win, trigger, a_tx, a_rx,
                         a_sd, a_mode, b_tx, b_rx, b_sd, b_mode, b_debug);
        if (parsed == 12) begin
          case (rx_col)
            "A_RX", "a_rx": selected_rx = a_rx[1:0];
            "B_RX", "b_rx": selected_rx = b_rx[1:0];
            default: begin
              $fatal(1, "Unsupported RXCOL=%s, expected A_RX or B_RX", rx_col);
            end
          endcase
          ir_rx_in <= selected_rx[lane_idx];
          sample_count++;
          @(posedge clk);
        end
      end

      $fclose(fd);
      ir_rx_in <= 1'b1;
      wait_clk(2000);
    end
  endtask

  task automatic read_config_file;
    int fd;
    int got;
    int lane_cfg;
    string line;
    string value;
    begin
      fd = $fopen("xsim_plusargs.cfg", "r");
      if (fd != 0) begin
        while (!$feof(fd)) begin
          void'($fgets(line, fd));
          got = $sscanf(line, "CSV=%s", value);
          if (got == 1) csv_path = value;
          got = $sscanf(line, "RXCOL=%s", value);
          if (got == 1) rx_col = value;
          got = $sscanf(line, "LANE=%d", lane_cfg);
          if (got == 1) lane_idx = lane_cfg;
        end
        $fclose(fd);
      end
    end
  endtask

  initial begin
    csv_path = "C:/Users/user/Documents/RF_COMM/reports/ila_a2b_lane0_20260626_143829.csv";
    rx_col = "B_RX";
    lane_idx = 0;
    read_config_file();
    void'($value$plusargs("CSV=%s", csv_path));
    void'($value$plusargs("RXCOL=%s", rx_col));
    void'($value$plusargs("LANE=%d", lane_idx));
    if ((lane_idx < 0) || (lane_idx > 1)) begin
      $fatal(1, "Unsupported LANE=%0d, expected 0 or 1", lane_idx);
    end

    wait_clk(20);
    rst_n <= 1'b1;
    enable <= 1'b1;
    wait_clk(20);

    drive_csv();

    $display("ILA_REPLAY_SUMMARY csv=%s rxcol=%s lane=%0d detect=%0d..%0d phase=%0d realign=%0d samples=%0d bytes=%0d saw_last=%0b crc_error=%0b overrun_error=%0b rx_active=%0b debug=0x%08x state=%0d ticks=%0d chip_idx=%0d preamble=%0d byte_cnt=%0d invalid=%0d",
             csv_path, rx_col, lane_idx,
             DETECT_START, DETECT_END, PHASE_DELAY, REALIGN_EDGE,
             sample_count, byte_count, saw_last, crc_error, overrun_error,
             rx_active, debug_status, dut.state, dut.ticks, dut.chip_idx,
             dut.preamble_cnt, dut.byte_cnt, dut.invalid_sym_count);

    if (byte_count != 0) begin
      $display("IR_RX_ILA_REPLAY_PASS bytes=%0d", byte_count);
    end else begin
      $display("IR_RX_ILA_REPLAY_NO_BYTES");
    end
    $finish;
  end
endmodule
