`timescale 1ns/1ps

`ifdef TB_CNT15
`define TB_CNT_CHIP_MAX_VALUE 15
`else
`define TB_CNT_CHIP_MAX_VALUE 7
`endif

`ifdef TB_REPEATS2
`define TB_PATTERN_REPEATS_VALUE 2
`elsif TB_REPEATS8
`define TB_PATTERN_REPEATS_VALUE 8
`else
`define TB_PATTERN_REPEATS_VALUE 4
`endif

module tb_ir_stream_parallel_asym_2lane_perf #(
  parameter int LANE_COUNT       = 2,
  parameter int RAW_PACKET_BYTES = 255,
  parameter int APP_BYTES        = 247,
  parameter int CNT_CHIP_MAX     = `TB_CNT_CHIP_MAX_VALUE,
  parameter int PATTERN_REPEATS  = `TB_PATTERN_REPEATS_VALUE,
  parameter int MIN_TOTAL_MBPS_X1000 = 4000
);
  localparam int FRAGMENT_BYTES  = RAW_PACKET_BYTES;
  localparam int MAX_FRAGS       = 1;
  localparam int MAX_FRAME_BYTES = 14 + FRAGMENT_BYTES;
  localparam int LANE1_SLOTS_PER_REPEAT = 11;
  localparam int A_HEAVY_A_PACKETS = PATTERN_REPEATS * 20;
  localparam int A_HEAVY_B_PACKETS = PATTERN_REPEATS * 2;
  localparam int B_HEAVY_A_PACKETS = PATTERN_REPEATS * 2;
  localparam int B_HEAVY_B_PACKETS = PATTERN_REPEATS * 20;

  logic clk;
  logic rst_n;

  logic [7:0] a_tx_data [0:LANE_COUNT-1];
  logic [7:0] b_tx_data [0:LANE_COUNT-1];
  logic       a_tx_valid [0:LANE_COUNT-1];
  logic       b_tx_valid [0:LANE_COUNT-1];
  logic       a_tx_ready [0:LANE_COUNT-1];
  logic       b_tx_ready [0:LANE_COUNT-1];
  logic       a_tx_last [0:LANE_COUNT-1];
  logic       b_tx_last [0:LANE_COUNT-1];
  logic [7:0] a_rx_data [0:LANE_COUNT-1];
  logic [7:0] b_rx_data [0:LANE_COUNT-1];
  logic       a_rx_valid [0:LANE_COUNT-1];
  logic       b_rx_valid [0:LANE_COUNT-1];
  logic       a_rx_last [0:LANE_COUNT-1];
  logic       b_rx_last [0:LANE_COUNT-1];
  logic [0:0] a_ir_tx_out [0:LANE_COUNT-1];
  logic [0:0] b_ir_tx_out [0:LANE_COUNT-1];
  logic [0:0] a_ir_rx_in [0:LANE_COUNT-1];
  logic [0:0] b_ir_rx_in [0:LANE_COUNT-1];
  logic [0:0] a_ir_sd [0:LANE_COUNT-1];
  logic [0:0] b_ir_sd [0:LANE_COUNT-1];
  logic [0:0] a_ir_mode_out [0:LANE_COUNT-1];
  logic [0:0] b_ir_mode_out [0:LANE_COUNT-1];

  logic a_tx_done [0:LANE_COUNT-1];
  logic b_tx_done [0:LANE_COUNT-1];
  logic a_tx_overflow [0:LANE_COUNT-1];
  logic b_tx_overflow [0:LANE_COUNT-1];
  logic a_tx_exhaust [0:LANE_COUNT-1];
  logic b_tx_exhaust [0:LANE_COUNT-1];
  logic a_rx_done [0:LANE_COUNT-1];
  logic b_rx_done [0:LANE_COUNT-1];
  logic a_rx_header_error [0:LANE_COUNT-1];
  logic b_rx_header_error [0:LANE_COUNT-1];
  logic a_rx_protocol_error [0:LANE_COUNT-1];
  logic b_rx_protocol_error [0:LANE_COUNT-1];
  logic a_rx_frame_overflow_any [0:LANE_COUNT-1];
  logic b_rx_frame_overflow_any [0:LANE_COUNT-1];
  logic a_rx_crc_error_any [0:LANE_COUNT-1];
  logic b_rx_crc_error_any [0:LANE_COUNT-1];
  logic a_rx_overrun_any [0:LANE_COUNT-1];
  logic b_rx_overrun_any [0:LANE_COUNT-1];
  logic [31:0] debug_a [0:LANE_COUNT-1];
  logic [31:0] debug_b [0:LANE_COUNT-1];

  logic unused_rx_ctx_valid_a [0:LANE_COUNT-1];
  logic unused_rx_ctx_valid_b [0:LANE_COUNT-1];
  logic unused_rx_ctx_complete_a [0:LANE_COUNT-1];
  logic unused_rx_ctx_complete_b [0:LANE_COUNT-1];
  logic [0:0] unused_lane_tx_busy_a [0:LANE_COUNT-1];
  logic [0:0] unused_lane_tx_busy_b [0:LANE_COUNT-1];
  logic [0:0] unused_lane_pulse_a [0:LANE_COUNT-1];
  logic [0:0] unused_lane_pulse_b [0:LANE_COUNT-1];
  logic [0:0] unused_rx_pulse_a [0:LANE_COUNT-1];
  logic [0:0] unused_rx_pulse_b [0:LANE_COUNT-1];
  logic [0:0] unused_crc_a [0:LANE_COUNT-1];
  logic [0:0] unused_crc_b [0:LANE_COUNT-1];
  logic [0:0] unused_err_a [0:LANE_COUNT-1];
  logic [0:0] unused_err_b [0:LANE_COUNT-1];
  logic [31:0] unused_lane_debug_a [0:LANE_COUNT-1];
  logic [31:0] unused_lane_debug_b [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_tx_pending_a [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_tx_pending_b [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_tx_inflight_a [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_tx_inflight_b [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_tx_acked_a [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_tx_acked_b [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_rx_bitmap_a [0:LANE_COUNT-1];
  logic [MAX_FRAGS-1:0] unused_rx_bitmap_b [0:LANE_COUNT-1];

  int a_sent [0:LANE_COUNT-1];
  int b_sent [0:LANE_COUNT-1];
  int a_tx_done_count [0:LANE_COUNT-1];
  int b_tx_done_count [0:LANE_COUNT-1];
  int a_rx_packet_count [0:LANE_COUNT-1];
  int b_rx_packet_count [0:LANE_COUNT-1];
  int a_rx_byte_idx [0:LANE_COUNT-1];
  int b_rx_byte_idx [0:LANE_COUNT-1];
  int halfduplex_overlap_count;

  always #7.8125 clk = ~clk;

  function automatic logic [7:0] payload_byte(
    input int dir,
    input int lane,
    input int seq,
    input int idx
  );
    begin
      case (idx)
        0: payload_byte = "A";
        1: payload_byte = "S";
        2: payload_byte = "Y";
        3: payload_byte = "M";
        4: payload_byte = dir[7:0];
        5: payload_byte = lane[7:0];
        6: payload_byte = seq[7:0];
        7: payload_byte = seq[15:8];
        default: payload_byte = (8'h35 + (dir * 8'h41) + (lane * 8'h17) +
                                 (seq * 8'h0d) + (idx * 8'h05)) & 8'hff;
      endcase
    end
  endfunction

  task automatic send_a_packet(input int lane, input int seq);
    begin
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        @(negedge clk);
        a_tx_data[lane]  = payload_byte(0, lane, seq, k);
        a_tx_valid[lane] = 1'b1;
        a_tx_last[lane]  = (k == RAW_PACKET_BYTES - 1);
        do @(posedge clk); while (!a_tx_ready[lane]);
      end
      @(negedge clk);
      a_tx_valid[lane] = 1'b0;
      a_tx_last[lane]  = 1'b0;
      a_sent[lane]++;
    end
  endtask

  task automatic send_b_packet(input int lane, input int seq);
    begin
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        @(negedge clk);
        b_tx_data[lane]  = payload_byte(1, lane, seq, k);
        b_tx_valid[lane] = 1'b1;
        b_tx_last[lane]  = (k == RAW_PACKET_BYTES - 1);
        do @(posedge clk); while (!b_tx_ready[lane]);
      end
      @(negedge clk);
      b_tx_valid[lane] = 1'b0;
      b_tx_last[lane]  = 1'b0;
      b_sent[lane]++;
    end
  endtask

  task automatic run_a_heavy_lane0;
    begin
      for (int p = 1; p <= (PATTERN_REPEATS * LANE1_SLOTS_PER_REPEAT); p++) begin
        send_a_packet(0, a_sent[0] + 1);
      end
    end
  endtask

  task automatic run_a_heavy_lane1;
    begin
      for (int r = 0; r < PATTERN_REPEATS; r++) begin
        repeat (4) send_a_packet(1, a_sent[1] + 1);
        send_b_packet(1, b_sent[1] + 1);
        repeat (5) send_a_packet(1, a_sent[1] + 1);
        send_b_packet(1, b_sent[1] + 1);
      end
    end
  endtask

  task automatic run_b_heavy_lane0;
    begin
      for (int p = 1; p <= (PATTERN_REPEATS * LANE1_SLOTS_PER_REPEAT); p++) begin
        send_b_packet(0, b_sent[0] + 1);
      end
    end
  endtask

  task automatic run_b_heavy_lane1;
    begin
      for (int r = 0; r < PATTERN_REPEATS; r++) begin
        repeat (4) send_b_packet(1, b_sent[1] + 1);
        send_a_packet(1, a_sent[1] + 1);
        repeat (5) send_b_packet(1, b_sent[1] + 1);
        send_a_packet(1, a_sent[1] + 1);
      end
    end
  endtask

  function automatic int sum_a_rx_packets;
    begin
      sum_a_rx_packets = 0;
      for (int l = 0; l < LANE_COUNT; l++) sum_a_rx_packets += a_rx_packet_count[l];
    end
  endfunction

  function automatic int sum_b_rx_packets;
    begin
      sum_b_rx_packets = 0;
      for (int l = 0; l < LANE_COUNT; l++) sum_b_rx_packets += b_rx_packet_count[l];
    end
  endfunction

  task automatic wait_phase_done(
    input int start_a_rx,
    input int start_b_rx,
    input int expect_a_to_b,
    input int expect_b_to_a
  );
    begin
      while (((sum_b_rx_packets() - start_b_rx) < expect_a_to_b) ||
             ((sum_a_rx_packets() - start_a_rx) < expect_b_to_a)) begin
        @(posedge clk);
      end
    end
  endtask

  task automatic report_phase(
    input string name,
    input real start_ns,
    input int start_a_rx,
    input int start_b_rx,
    input int expect_a_to_b,
    input int expect_b_to_a
  );
    real elapsed_us;
    real a_mbps;
    real b_mbps;
    real total_mbps;
    int total_packets;
    begin
      elapsed_us = ($realtime - start_ns) / 1000.0;
      a_mbps = (expect_a_to_b * APP_BYTES * 8.0) / elapsed_us;
      b_mbps = (expect_b_to_a * APP_BYTES * 8.0) / elapsed_us;
      total_mbps = a_mbps + b_mbps;
      total_packets = (sum_b_rx_packets() - start_b_rx) + (sum_a_rx_packets() - start_a_rx);
      if (total_mbps < (MIN_TOTAL_MBPS_X1000 / 1000.0)) begin
        $fatal(1, "%s total throughput too low: total=%0.6f a_to_b=%0.6f b_to_a=%0.6f elapsed_us=%0.3f packets=%0d",
               name, total_mbps, a_mbps, b_mbps, elapsed_us, total_packets);
      end
      $display("IR_STREAM_PARALLEL_ASYM_2LANE_PHASE_PASS name=%s a_to_b_packets=%0d b_to_a_packets=%0d ratio_x1000=%0d elapsed_us=%0.3f a_to_b_mbps=%0.6f b_to_a_mbps=%0.6f total_mbps=%0.6f cnt_chip_max=%0d repeats=%0d",
               name, expect_a_to_b, expect_b_to_a,
               (expect_b_to_a == 0) ? 0 : ((expect_a_to_b * 1000) / expect_b_to_a),
               elapsed_us, a_mbps, b_mbps, total_mbps, CNT_CHIP_MAX, PATTERN_REPEATS);
    end
  endtask

  genvar gi;
  generate
    for (gi = 0; gi < LANE_COUNT; gi++) begin : g_lane
      localparam logic [15:0] LANE_SESSION_ID = 16'h3300 + gi;

      assign a_ir_rx_in[gi][0] = ~b_ir_tx_out[gi][0];
      assign b_ir_rx_in[gi][0] = ~a_ir_tx_out[gi][0];

      ir_stream_array_top #(
        .LANE_COUNT(1),
        .NODE_ID(0),
        .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_RETRY(4),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(64),
        .RX_DATA_PHASE_DELAY_CYCLES(0),
        .RX_DETECT_START_CYCLES((CNT_CHIP_MAX >= 15) ? 0 : 2),
        .RX_DETECT_END_CYCLES((CNT_CHIP_MAX >= 15) ? 10 : (CNT_CHIP_MAX - 2)),
        .RX_PREAMBLE_REALIGN_EDGE(0),
        .FRAG_TIMEOUT_CYCLES(120000),
        .TX_TO_RX_GUARD_CYCLES(1024),
        .BACKOFF_SLOT_CYCLES(1024),
        .REASSEMBLY_TIMEOUT_CYCLES(200000),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) dut_a (
        .clk_phy(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .session_id(LANE_SESSION_ID),
        .lane_enable_mask(1'b1),
        .rx_lane_enable_mask(1'b1),
        .s_axis_tx_tdata(a_tx_data[gi]),
        .s_axis_tx_tvalid(a_tx_valid[gi]),
        .s_axis_tx_tready(a_tx_ready[gi]),
        .s_axis_tx_tlast(a_tx_last[gi]),
        .m_axis_rx_tdata(a_rx_data[gi]),
        .m_axis_rx_tvalid(a_rx_valid[gi]),
        .m_axis_rx_tready(1'b1),
        .m_axis_rx_tlast(a_rx_last[gi]),
        .ir_tx_out(a_ir_tx_out[gi]),
        .ir_rx_in(a_ir_rx_in[gi]),
        .ir_sd(a_ir_sd[gi]),
        .ir_mode_out(a_ir_mode_out[gi]),
        .tx_packet_active(),
        .tx_packet_loading(),
        .tx_done_pulse(a_tx_done[gi]),
        .tx_error_overflow(a_tx_overflow[gi]),
        .tx_error_retry_exhausted(a_tx_exhaust[gi]),
        .rx_ctx_valid(unused_rx_ctx_valid_a[gi]),
        .rx_ctx_complete(unused_rx_ctx_complete_a[gi]),
        .rx_done_pulse(a_rx_done[gi]),
        .rx_header_error(a_rx_header_error[gi]),
        .rx_protocol_error(a_rx_protocol_error[gi]),
        .rx_frame_overflow_any(a_rx_frame_overflow_any[gi]),
        .rx_crc_error_any(a_rx_crc_error_any[gi]),
        .rx_overrun_error_any(a_rx_overrun_any[gi]),
        .lane_tx_busy_dbg(unused_lane_tx_busy_a[gi]),
        .lane_tx_load_pulse_dbg(unused_lane_pulse_a[gi]),
        .lane_rx_frame_pulse_dbg(unused_rx_pulse_a[gi]),
        .lane_rx_crc_error_dbg(unused_crc_a[gi]),
        .lane_rx_error_dbg(unused_err_a[gi]),
        .lane_rx_debug_status_dbg(unused_lane_debug_a[gi]),
        .tx_frag_pending_dbg(unused_tx_pending_a[gi]),
        .tx_frag_inflight_dbg(unused_tx_inflight_a[gi]),
        .tx_frag_acked_dbg(unused_tx_acked_a[gi]),
        .rx_recv_bitmap_dbg(unused_rx_bitmap_a[gi]),
        .debug_status(debug_a[gi])
      );

      ir_stream_array_top #(
        .LANE_COUNT(1),
        .NODE_ID(1),
        .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_RETRY(4),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(64),
        .RX_DATA_PHASE_DELAY_CYCLES(0),
        .RX_DETECT_START_CYCLES((CNT_CHIP_MAX >= 15) ? 0 : 2),
        .RX_DETECT_END_CYCLES((CNT_CHIP_MAX >= 15) ? 10 : (CNT_CHIP_MAX - 2)),
        .RX_PREAMBLE_REALIGN_EDGE(0),
        .FRAG_TIMEOUT_CYCLES(120000),
        .TX_TO_RX_GUARD_CYCLES(1024),
        .BACKOFF_SLOT_CYCLES(1024),
        .REASSEMBLY_TIMEOUT_CYCLES(200000),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) dut_b (
        .clk_phy(clk),
        .rst_n(rst_n),
        .enable(1'b1),
        .session_id(LANE_SESSION_ID),
        .lane_enable_mask(1'b1),
        .rx_lane_enable_mask(1'b1),
        .s_axis_tx_tdata(b_tx_data[gi]),
        .s_axis_tx_tvalid(b_tx_valid[gi]),
        .s_axis_tx_tready(b_tx_ready[gi]),
        .s_axis_tx_tlast(b_tx_last[gi]),
        .m_axis_rx_tdata(b_rx_data[gi]),
        .m_axis_rx_tvalid(b_rx_valid[gi]),
        .m_axis_rx_tready(1'b1),
        .m_axis_rx_tlast(b_rx_last[gi]),
        .ir_tx_out(b_ir_tx_out[gi]),
        .ir_rx_in(b_ir_rx_in[gi]),
        .ir_sd(b_ir_sd[gi]),
        .ir_mode_out(b_ir_mode_out[gi]),
        .tx_packet_active(),
        .tx_packet_loading(),
        .tx_done_pulse(b_tx_done[gi]),
        .tx_error_overflow(b_tx_overflow[gi]),
        .tx_error_retry_exhausted(b_tx_exhaust[gi]),
        .rx_ctx_valid(unused_rx_ctx_valid_b[gi]),
        .rx_ctx_complete(unused_rx_ctx_complete_b[gi]),
        .rx_done_pulse(b_rx_done[gi]),
        .rx_header_error(b_rx_header_error[gi]),
        .rx_protocol_error(b_rx_protocol_error[gi]),
        .rx_frame_overflow_any(b_rx_frame_overflow_any[gi]),
        .rx_crc_error_any(b_rx_crc_error_any[gi]),
        .rx_overrun_error_any(b_rx_overrun_any[gi]),
        .lane_tx_busy_dbg(unused_lane_tx_busy_b[gi]),
        .lane_tx_load_pulse_dbg(unused_lane_pulse_b[gi]),
        .lane_rx_frame_pulse_dbg(unused_rx_pulse_b[gi]),
        .lane_rx_crc_error_dbg(unused_crc_b[gi]),
        .lane_rx_error_dbg(unused_err_b[gi]),
        .lane_rx_debug_status_dbg(unused_lane_debug_b[gi]),
        .tx_frag_pending_dbg(unused_tx_pending_b[gi]),
        .tx_frag_inflight_dbg(unused_tx_inflight_b[gi]),
        .tx_frag_acked_dbg(unused_tx_acked_b[gi]),
        .rx_recv_bitmap_dbg(unused_rx_bitmap_b[gi]),
        .debug_status(debug_b[gi])
      );
    end
  endgenerate

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      halfduplex_overlap_count <= 0;
      for (int l = 0; l < LANE_COUNT; l++) begin
        a_tx_done_count[l] <= 0;
        b_tx_done_count[l] <= 0;
        a_rx_packet_count[l] <= 0;
        b_rx_packet_count[l] <= 0;
        a_rx_byte_idx[l] <= 0;
        b_rx_byte_idx[l] <= 0;
      end
    end else begin
      for (int l = 0; l < LANE_COUNT; l++) begin
        if (a_tx_done[l]) a_tx_done_count[l] <= a_tx_done_count[l] + 1;
        if (b_tx_done[l]) b_tx_done_count[l] <= b_tx_done_count[l] + 1;

        if (a_ir_tx_out[l][0] && b_ir_tx_out[l][0]) begin
          halfduplex_overlap_count <= halfduplex_overlap_count + 1;
          $fatal(1, "Half-duplex overlap lane=%0d t=%0t debug_a=%08x debug_b=%08x",
                 l, $time, debug_a[l], debug_b[l]);
        end

        if (a_tx_overflow[l] || a_tx_exhaust[l] || b_tx_overflow[l] || b_tx_exhaust[l] ||
            a_rx_header_error[l] || b_rx_header_error[l] ||
            a_rx_protocol_error[l] || b_rx_protocol_error[l] ||
            a_rx_frame_overflow_any[l] || b_rx_frame_overflow_any[l] ||
            a_rx_crc_error_any[l] || b_rx_crc_error_any[l] ||
            a_rx_overrun_any[l] || b_rx_overrun_any[l]) begin
          $fatal(1, "Unexpected asym lane error lane=%0d debug_a=%08x debug_b=%08x",
                 l, debug_a[l], debug_b[l]);
        end

        if (b_rx_valid[l]) begin
          if (b_rx_data[l] !== payload_byte(0, l, b_rx_packet_count[l] + 1, b_rx_byte_idx[l])) begin
            $fatal(1, "A-to-B mismatch lane=%0d pkt=%0d byte=%0d exp=%02x got=%02x",
                   l, b_rx_packet_count[l] + 1, b_rx_byte_idx[l],
                   payload_byte(0, l, b_rx_packet_count[l] + 1, b_rx_byte_idx[l]),
                   b_rx_data[l]);
          end
          if (b_rx_last[l]) begin
            if (b_rx_byte_idx[l] != RAW_PACKET_BYTES - 1) $fatal(1, "A-to-B length mismatch lane=%0d", l);
            b_rx_packet_count[l] <= b_rx_packet_count[l] + 1;
            b_rx_byte_idx[l] <= 0;
          end else begin
            b_rx_byte_idx[l] <= b_rx_byte_idx[l] + 1;
          end
        end

        if (a_rx_valid[l]) begin
          if (a_rx_data[l] !== payload_byte(1, l, a_rx_packet_count[l] + 1, a_rx_byte_idx[l])) begin
            $fatal(1, "B-to-A mismatch lane=%0d pkt=%0d byte=%0d exp=%02x got=%02x",
                   l, a_rx_packet_count[l] + 1, a_rx_byte_idx[l],
                   payload_byte(1, l, a_rx_packet_count[l] + 1, a_rx_byte_idx[l]),
                   a_rx_data[l]);
          end
          if (a_rx_last[l]) begin
            if (a_rx_byte_idx[l] != RAW_PACKET_BYTES - 1) $fatal(1, "B-to-A length mismatch lane=%0d", l);
            a_rx_packet_count[l] <= a_rx_packet_count[l] + 1;
            a_rx_byte_idx[l] <= 0;
          end else begin
            a_rx_byte_idx[l] <= a_rx_byte_idx[l] + 1;
          end
        end
      end
    end
  end

  initial begin
    real phase_start_ns;
    int start_a_rx;
    int start_b_rx;

    clk = 1'b0;
    rst_n = 1'b0;
    for (int l = 0; l < LANE_COUNT; l++) begin
      a_tx_data[l] = 8'h00;
      b_tx_data[l] = 8'h00;
      a_tx_valid[l] = 1'b0;
      b_tx_valid[l] = 1'b0;
      a_tx_last[l] = 1'b0;
      b_tx_last[l] = 1'b0;
      a_sent[l] = 0;
      b_sent[l] = 0;
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (200) @(posedge clk);

    start_a_rx = sum_a_rx_packets();
    start_b_rx = sum_b_rx_packets();
    phase_start_ns = $realtime;
    fork
      run_a_heavy_lane0();
      run_a_heavy_lane1();
    join_none
    wait_phase_done(start_a_rx, start_b_rx, A_HEAVY_A_PACKETS, A_HEAVY_B_PACKETS);
    report_phase("a_heavy_10_to_1", phase_start_ns, start_a_rx, start_b_rx,
                 A_HEAVY_A_PACKETS, A_HEAVY_B_PACKETS);

    repeat (2000) @(posedge clk);

    start_a_rx = sum_a_rx_packets();
    start_b_rx = sum_b_rx_packets();
    phase_start_ns = $realtime;
    fork
      run_b_heavy_lane0();
      run_b_heavy_lane1();
    join_none
    wait_phase_done(start_a_rx, start_b_rx, B_HEAVY_A_PACKETS, B_HEAVY_B_PACKETS);
    report_phase("b_heavy_10_to_1", phase_start_ns, start_a_rx, start_b_rx,
                 B_HEAVY_A_PACKETS, B_HEAVY_B_PACKETS);

    $display("IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS cnt_chip_max=%0d repeats=%0d a_total_sent=%0d b_total_sent=%0d a_total_rx=%0d b_total_rx=%0d halfduplex_overlaps=%0d",
             CNT_CHIP_MAX, PATTERN_REPEATS, a_sent[0] + a_sent[1],
             b_sent[0] + b_sent[1], sum_a_rx_packets(), sum_b_rx_packets(),
             halfduplex_overlap_count);
    $finish;
  end

  initial begin
    repeat (20000000) @(posedge clk);
    $fatal(1, "Timeout waiting for parallel asym test a_rx=%0d b_rx=%0d a_sent=%0d b_sent=%0d",
           sum_a_rx_packets(), sum_b_rx_packets(),
           a_sent[0] + a_sent[1], b_sent[0] + b_sent[1]);
  end
endmodule
