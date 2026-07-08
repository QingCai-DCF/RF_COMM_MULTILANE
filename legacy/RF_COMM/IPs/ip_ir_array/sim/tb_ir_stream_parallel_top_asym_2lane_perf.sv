`timescale 1ns/1ps

`ifdef TB_CNT15
`define TB_CNT_CHIP_MAX_VALUE 15
`else
`define TB_CNT_CHIP_MAX_VALUE 7
`endif

module tb_ir_stream_parallel_top_asym_2lane_perf;
  localparam int RAW_PACKET_BYTES = 255;
  localparam int APP_BYTES        = 247;
  localparam int CNT_CHIP_MAX     = `TB_CNT_CHIP_MAX_VALUE;
  localparam int A_HEAVY_A_PACKETS = 80;
  localparam int A_HEAVY_B_PACKETS = 8;
  localparam int B_HEAVY_A_PACKETS = 8;
  localparam int B_HEAVY_B_PACKETS = 80;
  localparam int MAX_SEQ = 256;

  logic clk;
  logic rst_n;
  logic [7:0] a_tx_data;
  logic a_tx_valid;
  logic a_tx_ready;
  logic a_tx_last;
  logic [7:0] b_tx_data;
  logic b_tx_valid;
  logic b_tx_ready;
  logic b_tx_last;
  logic [7:0] a_rx_data;
  logic a_rx_valid;
  logic a_rx_last;
  logic [7:0] b_rx_data;
  logic b_rx_valid;
  logic b_rx_last;
  logic [1:0] a_ir_tx_out;
  logic [1:0] b_ir_tx_out;
  logic [1:0] a_ir_rx_in;
  logic [1:0] b_ir_rx_in;
  logic [1:0] a_ir_sd;
  logic [1:0] b_ir_sd;
  logic [1:0] a_ir_mode_out;
  logic [1:0] b_ir_mode_out;
  logic [31:0] debug_a;
  logic [31:0] debug_b;

  logic a_tx_done;
  logic b_tx_done;
  logic a_tx_overflow;
  logic b_tx_overflow;
  logic a_tx_exhaust;
  logic b_tx_exhaust;
  logic a_rx_header_error;
  logic b_rx_header_error;
  logic a_rx_protocol_error;
  logic b_rx_protocol_error;
  logic a_rx_frame_overflow;
  logic b_rx_frame_overflow;
  logic a_rx_crc_error;
  logic b_rx_crc_error;
  logic a_rx_overrun;
  logic b_rx_overrun;
  logic [1:0] a_lane_tx_busy;
  logic [1:0] b_lane_tx_busy;
  logic [1:0] a_lane_tx_load;
  logic [1:0] b_lane_tx_load;
  logic [1:0] a_lane_rx_pulse;
  logic [1:0] b_lane_rx_pulse;
  logic [1:0] a_lane_crc;
  logic [1:0] b_lane_crc;
  logic [1:0] a_lane_err;
  logic [1:0] b_lane_err;
  logic [63:0] a_lane_debug;
  logic [63:0] b_lane_debug;
  logic [0:0] a_tx_pending;
  logic [0:0] b_tx_pending;
  logic [0:0] a_tx_inflight;
  logic [0:0] b_tx_inflight;
  logic [0:0] a_tx_acked;
  logic [0:0] b_tx_acked;
  logic [0:0] a_rx_bitmap;
  logic [0:0] b_rx_bitmap;
  logic unused_a_tx_active;
  logic unused_b_tx_active;
  logic unused_a_tx_loading;
  logic unused_b_tx_loading;
  logic unused_a_rx_ctx_valid;
  logic unused_b_rx_ctx_valid;
  logic unused_a_rx_ctx_complete;
  logic unused_b_rx_ctx_complete;
  logic unused_a_rx_done;
  logic unused_b_rx_done;

  byte a_rx_buf [0:RAW_PACKET_BYTES-1];
  byte b_rx_buf [0:RAW_PACKET_BYTES-1];
  bit a_seen [0:MAX_SEQ-1];
  bit b_seen [0:MAX_SEQ-1];
  int a_rx_idx;
  int b_rx_idx;
  int a_rx_packets;
  int b_rx_packets;
  int a_tx_done_count;
  int b_tx_done_count;
  int a_lane_load_count [0:1];
  int b_lane_load_count [0:1];
  int halfduplex_overlap_count;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in = ~b_ir_tx_out;
  assign b_ir_rx_in = ~a_ir_tx_out;

  function automatic logic [7:0] payload_byte(input int dir, input int seq, input int idx);
    begin
      case (idx)
        0: payload_byte = "A";
        1: payload_byte = "S";
        2: payload_byte = "Y";
        3: payload_byte = "M";
        4: payload_byte = dir[7:0];
        5: payload_byte = 8'h02;
        6: payload_byte = seq[7:0];
        7: payload_byte = seq[15:8];
        default: payload_byte = (8'h29 + (dir * 8'h43) + (seq * 8'h0d) + (idx * 8'h07)) & 8'hff;
      endcase
    end
  endfunction

  task automatic send_a_packet(input int seq);
    begin
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        @(negedge clk);
        a_tx_data = payload_byte(0, seq, k);
        a_tx_valid = 1'b1;
        a_tx_last = (k == RAW_PACKET_BYTES - 1);
        do @(posedge clk); while (!a_tx_ready);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last = 1'b0;
    end
  endtask

  task automatic send_b_packet(input int seq);
    begin
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        @(negedge clk);
        b_tx_data = payload_byte(1, seq, k);
        b_tx_valid = 1'b1;
        b_tx_last = (k == RAW_PACKET_BYTES - 1);
        do @(posedge clk); while (!b_tx_ready);
      end
      @(negedge clk);
      b_tx_valid = 1'b0;
      b_tx_last = 1'b0;
    end
  endtask

  task automatic send_a_range(input int first_seq, input int count);
    begin
      for (int s = first_seq; s < first_seq + count; s++) send_a_packet(s);
    end
  endtask

  task automatic send_b_range(input int first_seq, input int count);
    begin
      for (int s = first_seq; s < first_seq + count; s++) send_b_packet(s);
    end
  endtask

  task automatic validate_packet(input int dir, input byte pkt [0:RAW_PACKET_BYTES-1]);
    int seq;
    begin
      seq = pkt[6] | (pkt[7] << 8);
      if (seq <= 0 || seq >= MAX_SEQ) $fatal(1, "Bad sequence dir=%0d seq=%0d", dir, seq);
      for (int k = 0; k < RAW_PACKET_BYTES; k++) begin
        if (pkt[k] !== payload_byte(dir, seq, k)) begin
          $fatal(1, "Payload mismatch dir=%0d seq=%0d idx=%0d exp=%02x got=%02x",
                 dir, seq, k, payload_byte(dir, seq, k), pkt[k]);
        end
      end
      if (dir == 0) begin
        if (b_seen[seq]) $fatal(1, "Duplicate A-to-B seq=%0d", seq);
        b_seen[seq] = 1'b1;
      end else begin
        if (a_seen[seq]) $fatal(1, "Duplicate B-to-A seq=%0d", seq);
        a_seen[seq] = 1'b1;
      end
    end
  endtask

  task automatic wait_counts(input int start_a_rx, input int start_b_rx, input int expect_a_to_b, input int expect_b_to_a);
    begin
      while (((b_rx_packets - start_b_rx) < expect_a_to_b) ||
             ((a_rx_packets - start_a_rx) < expect_b_to_a)) begin
        @(posedge clk);
      end
    end
  endtask

  task automatic report_phase(input string name, input real start_ns,
                              input int start_a_rx, input int start_b_rx,
                              input int expect_a_to_b, input int expect_b_to_a);
    real elapsed_us;
    real a_mbps;
    real b_mbps;
    real total_mbps;
    begin
      elapsed_us = ($realtime - start_ns) / 1000.0;
      a_mbps = (expect_a_to_b * APP_BYTES * 8.0) / elapsed_us;
      b_mbps = (expect_b_to_a * APP_BYTES * 8.0) / elapsed_us;
      total_mbps = a_mbps + b_mbps;
      if (total_mbps < 4.0) begin
        $fatal(1, "%s total throughput too low: total=%0.6f a_to_b=%0.6f b_to_a=%0.6f elapsed_us=%0.3f",
               name, total_mbps, a_mbps, b_mbps, elapsed_us);
      end
      $display("IR_STREAM_PARALLEL_TOP_ASYM_2LANE_PHASE_PASS name=%s a_to_b_packets=%0d b_to_a_packets=%0d elapsed_us=%0.3f a_to_b_mbps=%0.6f b_to_a_mbps=%0.6f total_mbps=%0.6f a_tx_done=%0d b_tx_done=%0d tx_lane_a=%0d/%0d tx_lane_b=%0d/%0d cnt_chip_max=%0d",
               name, expect_a_to_b, expect_b_to_a, elapsed_us, a_mbps, b_mbps,
               total_mbps, a_tx_done_count, b_tx_done_count,
               a_lane_load_count[0], a_lane_load_count[1],
               b_lane_load_count[0], b_lane_load_count[1],
               CNT_CHIP_MAX);
    end
  endtask

  task automatic wait_tx_done(input int expect_a_done, input int expect_b_done);
    begin
      while ((a_tx_done_count < expect_a_done) || (b_tx_done_count < expect_b_done)) begin
        @(posedge clk);
      end
    end
  endtask

  always @(posedge clk) begin
    if (!rst_n) begin
      a_rx_idx <= 0;
      b_rx_idx <= 0;
      a_rx_packets <= 0;
      b_rx_packets <= 0;
      a_tx_done_count <= 0;
      b_tx_done_count <= 0;
      for (int l = 0; l < 2; l++) begin
        a_lane_load_count[l] <= 0;
        b_lane_load_count[l] <= 0;
      end
      halfduplex_overlap_count <= 0;
    end else begin
      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;
      if (b_tx_done) b_tx_done_count <= b_tx_done_count + 1;

      for (int l = 0; l < 2; l++) begin
        if (a_lane_tx_load[l]) a_lane_load_count[l] <= a_lane_load_count[l] + 1;
        if (b_lane_tx_load[l]) b_lane_load_count[l] <= b_lane_load_count[l] + 1;

        if (a_ir_tx_out[l] && b_ir_tx_out[l]) begin
          halfduplex_overlap_count <= halfduplex_overlap_count + 1;
          $fatal(1, "Half-duplex overlap lane=%0d debug_a=%08x debug_b=%08x", l, debug_a, debug_b);
        end
      end

      if (a_tx_overflow || b_tx_overflow || a_tx_exhaust || b_tx_exhaust ||
          a_rx_header_error || b_rx_header_error ||
          a_rx_protocol_error || b_rx_protocol_error ||
          a_rx_frame_overflow || b_rx_frame_overflow ||
          a_rx_crc_error || b_rx_crc_error || a_rx_overrun || b_rx_overrun) begin
        $fatal(1, "Unexpected parallel top error debug_a=%08x debug_b=%08x", debug_a, debug_b);
      end

      if (b_rx_valid) begin
        if (b_rx_idx >= RAW_PACKET_BYTES) $fatal(1, "B RX overflow");
        b_rx_buf[b_rx_idx] = b_rx_data;
        if (b_rx_last) begin
          if (b_rx_idx != RAW_PACKET_BYTES - 1) $fatal(1, "B RX length mismatch idx=%0d", b_rx_idx);
          validate_packet(0, b_rx_buf);
          b_rx_packets <= b_rx_packets + 1;
          b_rx_idx <= 0;
        end else begin
          b_rx_idx <= b_rx_idx + 1;
        end
      end

      if (a_rx_valid) begin
        if (a_rx_idx >= RAW_PACKET_BYTES) $fatal(1, "A RX overflow");
        a_rx_buf[a_rx_idx] = a_rx_data;
        if (a_rx_last) begin
          if (a_rx_idx != RAW_PACKET_BYTES - 1) $fatal(1, "A RX length mismatch idx=%0d", a_rx_idx);
          validate_packet(1, a_rx_buf);
          a_rx_packets <= a_rx_packets + 1;
          a_rx_idx <= 0;
        end else begin
          a_rx_idx <= a_rx_idx + 1;
        end
      end
    end
  end

  ir_stream_parallel_2lane_top #(
    .NODE_ID(0),
    .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(RAW_PACKET_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(64),
    .RX_DATA_PHASE_DELAY_CYCLES(0),
    .RX_DETECT_START_CYCLES((CNT_CHIP_MAX >= 15) ? 0 : 2),
    .RX_DETECT_END_CYCLES((CNT_CHIP_MAX >= 15) ? 10 : (CNT_CHIP_MAX - 2)),
    .RX_PREAMBLE_REALIGN_EDGE(0),
    .TX_TO_RX_GUARD_CYCLES(1024),
    .BACKOFF_SLOT_CYCLES(1024),
    .MAX_FRAGS(1),
    .MAX_FRAME_BYTES(14 + RAW_PACKET_BYTES)
  ) dut_a (
    .clk_phy(clk), .rst_n(rst_n), .enable(1'b1), .session_id(16'h4412),
    .lane_enable_mask(2'b11), .rx_lane_enable_mask(2'b11),
    .s_axis_tx_tdata(a_tx_data), .s_axis_tx_tvalid(a_tx_valid), .s_axis_tx_tready(a_tx_ready), .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data), .m_axis_rx_tvalid(a_rx_valid), .m_axis_rx_tready(1'b1), .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out), .ir_rx_in(a_ir_rx_in), .ir_sd(a_ir_sd), .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(unused_a_tx_active), .tx_packet_loading(unused_a_tx_loading), .tx_done_pulse(a_tx_done),
    .tx_error_overflow(a_tx_overflow), .tx_error_retry_exhausted(a_tx_exhaust),
    .rx_ctx_valid(unused_a_rx_ctx_valid), .rx_ctx_complete(unused_a_rx_ctx_complete), .rx_done_pulse(unused_a_rx_done),
    .rx_header_error(a_rx_header_error), .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(a_rx_frame_overflow), .rx_crc_error_any(a_rx_crc_error), .rx_overrun_error_any(a_rx_overrun),
    .lane_tx_busy_dbg(a_lane_tx_busy), .lane_tx_load_pulse_dbg(a_lane_tx_load),
    .lane_rx_frame_pulse_dbg(a_lane_rx_pulse), .lane_rx_crc_error_dbg(a_lane_crc), .lane_rx_error_dbg(a_lane_err),
    .lane_rx_debug_status_dbg(a_lane_debug),
    .tx_frag_pending_dbg(a_tx_pending), .tx_frag_inflight_dbg(a_tx_inflight), .tx_frag_acked_dbg(a_tx_acked),
    .rx_recv_bitmap_dbg(a_rx_bitmap), .debug_status(debug_a)
  );

  ir_stream_parallel_2lane_top #(
    .NODE_ID(1),
    .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
    .FRAGMENT_BYTES(RAW_PACKET_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(64),
    .RX_DATA_PHASE_DELAY_CYCLES(0),
    .RX_DETECT_START_CYCLES((CNT_CHIP_MAX >= 15) ? 0 : 2),
    .RX_DETECT_END_CYCLES((CNT_CHIP_MAX >= 15) ? 10 : (CNT_CHIP_MAX - 2)),
    .RX_PREAMBLE_REALIGN_EDGE(0),
    .TX_TO_RX_GUARD_CYCLES(1024),
    .BACKOFF_SLOT_CYCLES(1024),
    .MAX_FRAGS(1),
    .MAX_FRAME_BYTES(14 + RAW_PACKET_BYTES)
  ) dut_b (
    .clk_phy(clk), .rst_n(rst_n), .enable(1'b1), .session_id(16'h4412),
    .lane_enable_mask(2'b11), .rx_lane_enable_mask(2'b11),
    .s_axis_tx_tdata(b_tx_data), .s_axis_tx_tvalid(b_tx_valid), .s_axis_tx_tready(b_tx_ready), .s_axis_tx_tlast(b_tx_last),
    .m_axis_rx_tdata(b_rx_data), .m_axis_rx_tvalid(b_rx_valid), .m_axis_rx_tready(1'b1), .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out), .ir_rx_in(b_ir_rx_in), .ir_sd(b_ir_sd), .ir_mode_out(b_ir_mode_out),
    .tx_packet_active(unused_b_tx_active), .tx_packet_loading(unused_b_tx_loading), .tx_done_pulse(b_tx_done),
    .tx_error_overflow(b_tx_overflow), .tx_error_retry_exhausted(b_tx_exhaust),
    .rx_ctx_valid(unused_b_rx_ctx_valid), .rx_ctx_complete(unused_b_rx_ctx_complete), .rx_done_pulse(unused_b_rx_done),
    .rx_header_error(b_rx_header_error), .rx_protocol_error(b_rx_protocol_error),
    .rx_frame_overflow_any(b_rx_frame_overflow), .rx_crc_error_any(b_rx_crc_error), .rx_overrun_error_any(b_rx_overrun),
    .lane_tx_busy_dbg(b_lane_tx_busy), .lane_tx_load_pulse_dbg(b_lane_tx_load),
    .lane_rx_frame_pulse_dbg(b_lane_rx_pulse), .lane_rx_crc_error_dbg(b_lane_crc), .lane_rx_error_dbg(b_lane_err),
    .lane_rx_debug_status_dbg(b_lane_debug),
    .tx_frag_pending_dbg(b_tx_pending), .tx_frag_inflight_dbg(b_tx_inflight), .tx_frag_acked_dbg(b_tx_acked),
    .rx_recv_bitmap_dbg(b_rx_bitmap), .debug_status(debug_b)
  );

  initial begin
    real phase_start_ns;
    int start_a_rx;
    int start_b_rx;

    clk = 1'b0;
    rst_n = 1'b0;
    a_tx_data = 8'h00;
    b_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    b_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_last = 1'b0;
    for (int i = 0; i < MAX_SEQ; i++) begin
      a_seen[i] = 1'b0;
      b_seen[i] = 1'b0;
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (200) @(posedge clk);

    start_a_rx = a_rx_packets;
    start_b_rx = b_rx_packets;
    phase_start_ns = $realtime;
    fork
      send_a_range(1, A_HEAVY_A_PACKETS);
      send_b_range(1, A_HEAVY_B_PACKETS);
    join_none
    wait_counts(start_a_rx, start_b_rx, A_HEAVY_A_PACKETS, A_HEAVY_B_PACKETS);
    report_phase("a_heavy_10_to_1", phase_start_ns, start_a_rx, start_b_rx,
                 A_HEAVY_A_PACKETS, A_HEAVY_B_PACKETS);

    repeat (2000) @(posedge clk);

    start_a_rx = a_rx_packets;
    start_b_rx = b_rx_packets;
    phase_start_ns = $realtime;
    fork
      send_a_range(A_HEAVY_A_PACKETS + 1, B_HEAVY_A_PACKETS);
      send_b_range(A_HEAVY_B_PACKETS + 1, B_HEAVY_B_PACKETS);
    join_none
    wait_counts(start_a_rx, start_b_rx, B_HEAVY_A_PACKETS, B_HEAVY_B_PACKETS);
    report_phase("b_heavy_10_to_1", phase_start_ns, start_a_rx, start_b_rx,
                 B_HEAVY_A_PACKETS, B_HEAVY_B_PACKETS);
    wait_tx_done(A_HEAVY_A_PACKETS + B_HEAVY_A_PACKETS,
                 A_HEAVY_B_PACKETS + B_HEAVY_B_PACKETS);

    $display("IR_STREAM_PARALLEL_TOP_ASYM_2LANE_PERF_PASS cnt_chip_max=%0d a_rx=%0d b_rx=%0d a_tx_done=%0d b_tx_done=%0d a_lane_load=%0d/%0d b_lane_load=%0d/%0d halfduplex_overlaps=%0d",
             CNT_CHIP_MAX, a_rx_packets, b_rx_packets, a_tx_done_count,
             b_tx_done_count, a_lane_load_count[0], a_lane_load_count[1],
             b_lane_load_count[0], b_lane_load_count[1], halfduplex_overlap_count);
    $finish;
  end

  initial begin
    repeat (20000000) @(posedge clk);
    $fatal(1, "Timeout waiting for parallel top asym pass a_rx=%0d b_rx=%0d debug_a=%08x debug_b=%08x",
           a_rx_packets, b_rx_packets, debug_a, debug_b);
  end
endmodule
