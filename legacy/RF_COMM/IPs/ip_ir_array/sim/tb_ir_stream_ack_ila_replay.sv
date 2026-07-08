`timescale 1ns/1ps

module tb_ir_stream_ack_ila_replay;
  localparam int LANE_COUNT        = 2;
  localparam int RAW_PACKET_BYTES  = 264;
  localparam int APP_PAYLOAD_BYTES = 256;
  localparam int FRAGMENT_BYTES    = 64;
  localparam int MAX_FRAGS         = (RAW_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX      = 7;
  localparam int CNT_PREAMBLE      = 16;

  logic clk = 1'b0;
  logic rst_n = 1'b0;

  logic a_tx_valid = 1'b0;
  logic a_tx_ready;
  logic a_tx_last = 1'b0;
  logic [7:0] a_tx_data = 8'h00;
  logic a_rx_valid;
  logic a_rx_ready = 1'b1;
  logic a_rx_last;
  logic [7:0] a_rx_data;
  logic [LANE_COUNT-1:0] a_ir_tx_out;
  logic a_ir_rx_lane0 = 1'b1;
  logic [LANE_COUNT-1:0] a_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd;
  logic [LANE_COUNT-1:0] a_ir_mode_out;
  logic [LANE_COUNT-1:0] a_lane_tx_busy;
  logic [LANE_COUNT-1:0] a_lane_tx_load_pulse;
  logic [LANE_COUNT-1:0] a_lane_rx_frame_pulse;
  logic [LANE_COUNT-1:0] a_lane_rx_crc_error;
  logic [LANE_COUNT-1:0] a_lane_rx_error;
  logic [32*LANE_COUNT-1:0] a_lane_rx_debug;
  logic [MAX_FRAGS-1:0] a_tx_pending;
  logic [MAX_FRAGS-1:0] a_tx_inflight;
  logic [MAX_FRAGS-1:0] a_tx_acked;
  logic [MAX_FRAGS-1:0] a_rx_bitmap;
  logic a_tx_done;
  logic a_tx_overflow;
  logic a_tx_exhaust;
  logic a_rx_done;
  logic a_rx_header_error;
  logic a_rx_protocol_error;
  logic a_rx_frame_overflow_any;
  logic a_rx_crc_error_any;
  logic a_rx_overrun_any;
  logic unused_rx_ctx_valid_a;
  logic unused_rx_ctx_complete_a;
  logic [31:0] debug_a;

  string csv_path;
  int lane_idx;
  int csv_rows_driven = 0;
  int csv_rows_skipped = 0;
  int post_busy_delay = 64;
  int ack_seen_count = 0;
  int rx_frame_count = 0;
  int rx_crc_count = 0;
  int rx_header_count = 0;
  int rx_protocol_count = 0;
  int tx_done_count = 0;
  bit csv_done = 1'b0;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in = {1'b1, a_ir_rx_lane0};

  function automatic logic [7:0] a_payload_byte(
    input int idx,
    input logic [31:0] seq_f
  );
    begin
      case (idx)
        0:  a_payload_byte = "P";
        1:  a_payload_byte = "S";
        2:  a_payload_byte = "P";
        3:  a_payload_byte = "S";
        4:  a_payload_byte = seq_f[7:0];
        5:  a_payload_byte = seq_f[15:8];
        6:  a_payload_byte = seq_f[23:16];
        7:  a_payload_byte = seq_f[31:24];
        8:  a_payload_byte = 8'h01;
        9:  a_payload_byte = 8'h00;
        10: a_payload_byte = 8'h00;
        11: a_payload_byte = 8'h00;
        12: a_payload_byte = ~seq_f[7:0];
        13: a_payload_byte = ~seq_f[15:8];
        14: a_payload_byte = ~seq_f[23:16];
        15: a_payload_byte = ~seq_f[31:24];
        default: a_payload_byte = (seq_f[7:0] + (idx * 17) + 8'h01) & 8'hff;
      endcase
    end
  endfunction

  function automatic logic [7:0] a_raw_byte(
    input int idx,
    input logic [31:0] seq_f
  );
    int payload_idx;
    begin
      payload_idx = idx - 8;
      case (idx)
        0: a_raw_byte = "I";
        1: a_raw_byte = "R";
        2: a_raw_byte = "P";
        3: a_raw_byte = "1";
        4: a_raw_byte = seq_f[7:0];
        5: a_raw_byte = seq_f[15:8];
        6: a_raw_byte = APP_PAYLOAD_BYTES[7:0];
        7: a_raw_byte = APP_PAYLOAD_BYTES[15:8];
        default: a_raw_byte = a_payload_byte(payload_idx, seq_f);
      endcase
    end
  endfunction

  task automatic send_a_packet(input logic [31:0] seq_f);
    begin
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        @(negedge clk);
        a_tx_data  = a_raw_byte(k, seq_f);
        a_tx_valid = 1'b1;
        a_tx_last  = (k == RAW_PACKET_BYTES - 1);
        do @(posedge clk); while (!a_tx_ready);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
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
          got = $sscanf(line, "LANE=%d", lane_cfg);
          if (got == 1) lane_idx = lane_cfg;
          got = $sscanf(line, "POST_BUSY_DELAY=%d", lane_cfg);
          if (got == 1) post_busy_delay = lane_cfg;
        end
        $fclose(fd);
      end
    end
  endtask

  task automatic drive_csv_a_rx_aligned;
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
    bit found_first_csv_tx;
    bit saw_sim_busy;
    logic [1:0] selected_rx;
    begin
      wait (rst_n);
      wait (a_lane_tx_busy[0] === 1'b1);
      saw_sim_busy = 1'b1;
      wait (saw_sim_busy && (a_lane_tx_busy[0] === 1'b0));
      repeat (post_busy_delay) @(negedge clk);
      @(negedge clk);

      fd = $fopen(csv_path, "r");
      if (fd == 0) begin
        $fatal(1, "Unable to open ILA CSV: %s", csv_path);
      end

      found_first_csv_tx = 1'b0;
      while (!$feof(fd)) begin
        void'($fgets(line, fd));
        parsed = $sscanf(line, "%d,%d,%d,%h,%h,%h,%h,%h,%h,%h,%h,%h",
                         sample_buf, sample_win, trigger, a_tx, a_rx,
                         a_sd, a_mode, b_tx, b_rx, b_sd, b_mode, b_debug);
        if (parsed == 12) begin
          if (!found_first_csv_tx) begin
            if (b_tx[lane_idx]) begin
              found_first_csv_tx = 1'b1;
            end else begin
              csv_rows_skipped++;
            end
          end

          if (found_first_csv_tx) begin
            selected_rx = a_rx[1:0];
            a_ir_rx_lane0 <= selected_rx[lane_idx];
            csv_rows_driven++;
            @(negedge clk);
          end
        end
      end

      $fclose(fd);
      a_ir_rx_lane0 <= 1'b1;
      csv_done = 1'b1;
    end
  endtask

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      ack_seen_count <= 0;
      rx_frame_count <= 0;
      rx_crc_count <= 0;
      rx_header_count <= 0;
      rx_protocol_count <= 0;
      tx_done_count <= 0;
    end else begin
      if (dut_a.ack_rx_valid) ack_seen_count <= ack_seen_count + 1;
      if (a_lane_rx_frame_pulse[0]) rx_frame_count <= rx_frame_count + 1;
      if (a_lane_rx_crc_error[0]) rx_crc_count <= rx_crc_count + 1;
      if (a_rx_header_error) rx_header_count <= rx_header_count + 1;
      if (a_rx_protocol_error) rx_protocol_count <= rx_protocol_count + 1;
      if (a_tx_done) tx_done_count <= tx_done_count + 1;
    end
  end

  initial begin
    csv_path = "C:/Users/user/Documents/RF_COMM/reports/ila_2lane_prearmed_b_tx_lane0_20260626_204641.csv";
    lane_idx = 0;
    read_config_file();
    void'($value$plusargs("CSV=%s", csv_path));
    void'($value$plusargs("LANE=%d", lane_idx));
    void'($value$plusargs("POST_BUSY_DELAY=%d", post_busy_delay));
    if ((lane_idx < 0) || (lane_idx > 1)) begin
      $fatal(1, "Unsupported LANE=%0d, expected 0 or 1", lane_idx);
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (200) @(posedge clk);

    fork
      send_a_packet(32'd1);
      drive_csv_a_rx_aligned();
    join_none

    repeat (1200000) begin
      @(posedge clk);
      if (csv_done && (tx_done_count != 0 || a_tx_exhaust)) begin
        break;
      end
    end

    repeat (20000) @(posedge clk);

    $display("IR_STREAM_ACK_ILA_TOPLEVEL_SUMMARY csv=%s lane=%0d post_busy_delay=%0d skipped=%0d driven=%0d tx_done=%0d tx_exhaust=%0b ack_seen=%0d rx_frames=%0d rx_crc=%0d rx_header=%0d rx_protocol=%0d tx_pending=%05b tx_inflight=%05b tx_acked=%05b debug_a=0x%08x lane0_rx_debug=0x%08x rx_state=%0d tx_state=%0d",
             csv_path, lane_idx, post_busy_delay, csv_rows_skipped, csv_rows_driven,
             tx_done_count, a_tx_exhaust, ack_seen_count, rx_frame_count,
             rx_crc_count, rx_header_count, rx_protocol_count,
             a_tx_pending, a_tx_inflight, a_tx_acked, debug_a,
             a_lane_rx_debug[31:0], dut_a.rx_parse_state, dut_a.tx_state);

    if ((ack_seen_count != 0) && (a_tx_acked != '0) && !a_tx_exhaust) begin
      $display("IR_STREAM_ACK_ILA_TOPLEVEL_PASS");
    end else begin
      $display("IR_STREAM_ACK_ILA_TOPLEVEL_FAIL");
    end
    $finish;
  end

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(0),
    .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(CNT_PREAMBLE),
    .RX_DETECT_START_CYCLES(0),
    .RX_DETECT_END_CYCLES(5),
    .RX_PREAMBLE_REALIGN_EDGE(0),
    .FRAG_TIMEOUT_CYCLES(50000),
    .TX_TO_RX_GUARD_CYCLES(4096),
    .BACKOFF_SLOT_CYCLES(4096),
    .REASSEMBLY_TIMEOUT_CYCLES(200000),
    .MAX_FRAME_BYTES(14 + FRAGMENT_BYTES)
  ) dut_a (
    .clk_phy(clk),
    .rst_n(rst_n),
    .enable(1'b1),
    .session_id(16'h2201),
    .lane_enable_mask(2'b01),
    .rx_lane_enable_mask(2'b01),
    .s_axis_tx_tdata(a_tx_data),
    .s_axis_tx_tvalid(a_tx_valid),
    .s_axis_tx_tready(a_tx_ready),
    .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data),
    .m_axis_rx_tvalid(a_rx_valid),
    .m_axis_rx_tready(a_rx_ready),
    .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out),
    .ir_rx_in(a_ir_rx_in),
    .ir_sd(a_ir_sd),
    .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(),
    .tx_packet_loading(),
    .tx_done_pulse(a_tx_done),
    .tx_error_overflow(a_tx_overflow),
    .tx_error_retry_exhausted(a_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_a),
    .rx_ctx_complete(unused_rx_ctx_complete_a),
    .rx_done_pulse(a_rx_done),
    .rx_header_error(a_rx_header_error),
    .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(a_rx_frame_overflow_any),
    .rx_crc_error_any(a_rx_crc_error_any),
    .rx_overrun_error_any(a_rx_overrun_any),
    .lane_tx_busy_dbg(a_lane_tx_busy),
    .lane_tx_load_pulse_dbg(a_lane_tx_load_pulse),
    .lane_rx_frame_pulse_dbg(a_lane_rx_frame_pulse),
    .lane_rx_crc_error_dbg(a_lane_rx_crc_error),
    .lane_rx_error_dbg(a_lane_rx_error),
    .lane_rx_debug_status_dbg(a_lane_rx_debug),
    .tx_frag_pending_dbg(a_tx_pending),
    .tx_frag_inflight_dbg(a_tx_inflight),
    .tx_frag_acked_dbg(a_tx_acked),
    .rx_recv_bitmap_dbg(a_rx_bitmap),
    .debug_status(debug_a)
  );
endmodule
