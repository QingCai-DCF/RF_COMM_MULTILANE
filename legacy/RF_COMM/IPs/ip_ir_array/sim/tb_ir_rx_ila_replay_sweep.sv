`timescale 1ns/1ps

module tb_ir_rx_ila_replay_sweep;
  localparam int MAX_FRAME_BYTES = 269;
  localparam int NUM_WINDOWS = 8;
  localparam int NUM_PHASES = 8;
  localparam int NUM_REALIGNS = 2;
  localparam int NUM_CASES = NUM_WINDOWS * NUM_PHASES * NUM_REALIGNS;

  logic clk = 1'b0;
  logic rst_n = 1'b0;
  logic enable = 1'b0;
  logic ir_rx_in = 1'b1;
  string csv_path;
  string rx_col;
  int lane_idx = 0;
  int sample_count = 0;

  logic [7:0] rx_tdata [0:NUM_CASES-1];
  logic rx_tvalid [0:NUM_CASES-1];
  logic rx_tlast [0:NUM_CASES-1];
  logic rx_active [0:NUM_CASES-1];
  logic crc_error [0:NUM_CASES-1];
  logic overrun_error [0:NUM_CASES-1];
  logic [31:0] debug_status [0:NUM_CASES-1];
  int byte_count [0:NUM_CASES-1];
  bit saw_last [0:NUM_CASES-1];

  always #5 clk = ~clk;

  function automatic int window_start(input int idx);
    begin
      case (idx)
        0: window_start = 0;
        1: window_start = 0;
        2: window_start = 0;
        3: window_start = 1;
        4: window_start = 2;
        5: window_start = 2;
        6: window_start = 3;
        default: window_start = 2;
      endcase
    end
  endfunction

  function automatic int window_end(input int idx);
    begin
      case (idx)
        0: window_end = 7;
        1: window_end = 6;
        2: window_end = 5;
        3: window_end = 6;
        4: window_end = 6;
        5: window_end = 5;
        6: window_end = 7;
        default: window_end = 7;
      endcase
    end
  endfunction

  genvar ri;
  genvar pi;
  genvar wi;
  generate
    for (ri = 0; ri < NUM_REALIGNS; ri = ri + 1) begin : g_r
      for (pi = 0; pi < NUM_PHASES; pi = pi + 1) begin : g_p
        for (wi = 0; wi < NUM_WINDOWS; wi = wi + 1) begin : g_w
          localparam int IDX = (ri * NUM_PHASES * NUM_WINDOWS) + (pi * NUM_WINDOWS) + wi;
          localparam int DS = window_start(wi);
          localparam int DE = window_end(wi);

          ir_rx_4ppm_frame #(
            .MAX_FRAME_BYTES(MAX_FRAME_BYTES),
            .CNT_CHIP_MAX(7),
            .PREAMBLE_SYMS(64),
            .EOF_SILENCE_SYMS(3),
            .DATA_PHASE_DELAY_CYCLES(pi),
            .DETECT_START_CYCLES(DS),
            .DETECT_END_CYCLES(DE),
            .PREAMBLE_REALIGN_EDGE(ri),
            .PREAMBLE_WAIT_FOR_DATA_SYMBOL(1)
          ) dut (
            .clk(clk),
            .rst_n(rst_n),
            .enable(enable),
            .ir_rx_in(ir_rx_in),
            .m_axis_tdata(rx_tdata[IDX]),
            .m_axis_tvalid(rx_tvalid[IDX]),
            .m_axis_tready(1'b1),
            .m_axis_tlast(rx_tlast[IDX]),
            .rx_active(rx_active[IDX]),
            .crc_error(crc_error[IDX]),
            .overrun_error(overrun_error[IDX]),
            .debug_status(debug_status[IDX])
          );

          always_ff @(posedge clk) begin
            if (!rst_n) begin
              byte_count[IDX] <= 0;
              saw_last[IDX] <= 1'b0;
            end else if (rx_tvalid[IDX]) begin
              byte_count[IDX] <= byte_count[IDX] + 1;
              if (rx_tlast[IDX]) saw_last[IDX] <= 1'b1;
            end
          end
        end
      end
    end
  endgenerate

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
      if (fd == 0) $fatal(1, "Unable to open ILA CSV: %s", csv_path);

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
    int idx;
    int best_idx;
    int best_bytes;
    int ds;
    int de;
    int phase;
    int realign;

    csv_path = "C:/Users/user/Documents/RF_COMM/reports/ila_a2b_lane0_20260626_143829.csv";
    rx_col = "B_RX";
    lane_idx = 0;
    read_config_file();
    if ((lane_idx < 0) || (lane_idx > 1)) begin
      $fatal(1, "Unsupported LANE=%0d, expected 0 or 1", lane_idx);
    end
    wait_clk(20);
    rst_n <= 1'b1;
    enable <= 1'b1;
    wait_clk(20);

    drive_csv();

    best_idx = 0;
    best_bytes = 0;
    for (idx = 0; idx < NUM_CASES; idx = idx + 1) begin
      if (byte_count[idx] > best_bytes) begin
        best_idx = idx;
        best_bytes = byte_count[idx];
      end
    end

    for (idx = 0; idx < NUM_CASES; idx = idx + 1) begin
      realign = idx / (NUM_PHASES * NUM_WINDOWS);
      phase = (idx / NUM_WINDOWS) % NUM_PHASES;
      ds = window_start(idx % NUM_WINDOWS);
      de = window_end(idx % NUM_WINDOWS);
      if ((byte_count[idx] != 0) || (idx == best_idx) ||
          ((realign == 1) && (phase == 0) && (ds == 3) && (de == 7))) begin
        $display("ILA_REPLAY_SWEEP case=%0d csv=%s rxcol=%s lane=%0d detect=%0d..%0d phase=%0d realign=%0d samples=%0d bytes=%0d saw_last=%0b crc=%0b overrun=%0b rx_active=%0b debug=0x%08x",
                 idx, csv_path, rx_col, lane_idx, ds, de, phase, realign, sample_count, byte_count[idx],
                 saw_last[idx], crc_error[idx], overrun_error[idx],
                 rx_active[idx], debug_status[idx]);
      end
    end

    $display("ILA_REPLAY_SWEEP_BEST case=%0d bytes=%0d", best_idx, best_bytes);
    if (best_bytes != 0) begin
      $display("IR_RX_ILA_REPLAY_SWEEP_PASS");
    end else begin
      $display("IR_RX_ILA_REPLAY_SWEEP_NO_BYTES");
    end
    $finish;
  end
endmodule
