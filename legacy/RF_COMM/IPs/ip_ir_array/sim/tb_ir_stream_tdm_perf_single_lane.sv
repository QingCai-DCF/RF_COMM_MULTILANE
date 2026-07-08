`timescale 1ns/1ps

module tb_ir_stream_tdm_perf_single_lane;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 247;
  localparam int FRAGMENT_BYTES   = 247;
  localparam int MAX_FRAGS        = 1;
  localparam int PKT_LEN          = 247;
  localparam int PACKETS_PER_DIR  = 64;

  logic clk;
  logic rst_n;
  logic enable_a, enable_b;

  logic [7:0] a_tx_data, b_tx_data;
  logic a_tx_valid, b_tx_valid;
  logic a_tx_ready, b_tx_ready;
  logic a_tx_last, b_tx_last;
  logic [7:0] a_rx_data, b_rx_data;
  logic a_rx_valid, b_rx_valid;
  logic a_rx_ready, b_rx_ready;
  logic a_rx_last, b_rx_last;

  logic [LANE_COUNT-1:0] a_ir_tx_out, b_ir_tx_out;
  logic [LANE_COUNT-1:0] a_ir_rx_in, b_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd, b_ir_sd;
  logic [LANE_COUNT-1:0] a_ir_mode_out, b_ir_mode_out;

  logic a_tx_done, b_tx_done;
  logic a_tx_overflow, b_tx_overflow;
  logic a_tx_exhaust, b_tx_exhaust;
  logic a_rx_done, b_rx_done;
  logic a_rx_header_error, b_rx_header_error;
  logic a_rx_protocol_error, b_rx_protocol_error;
  logic a_rx_frame_overflow_any, b_rx_frame_overflow_any;
  logic a_rx_crc_error_any, b_rx_crc_error_any;
  logic a_rx_overrun_any, b_rx_overrun_any;
  logic [LANE_COUNT-1:0] a_lane_tx_busy, b_lane_tx_busy;
  logic [LANE_COUNT-1:0] unused_lane_pulse_a, unused_lane_pulse_b;
  logic [LANE_COUNT-1:0] unused_rx_pulse_a, unused_rx_pulse_b;
  logic [LANE_COUNT-1:0] unused_crc_a, unused_crc_b;
  logic [LANE_COUNT-1:0] unused_err_a, unused_err_b;
  logic [MAX_FRAGS-1:0] unused_tx_pending_a, unused_tx_pending_b;
  logic [MAX_FRAGS-1:0] unused_tx_inflight_a, unused_tx_inflight_b;
  logic [MAX_FRAGS-1:0] unused_tx_acked_a, unused_tx_acked_b;
  logic [MAX_FRAGS-1:0] unused_rx_bitmap_a, unused_rx_bitmap_b;
  logic unused_rx_ctx_valid_a, unused_rx_ctx_valid_b;
  logic unused_rx_ctx_complete_a, unused_rx_ctx_complete_b;
  logic [31:0] debug_a, debug_b;

  int a_tx_done_count;
  int b_tx_done_count;
  int a_rx_done_count;
  int b_rx_done_count;
  int a_rx_packet_count;
  int b_rx_packet_count;
  int a_rx_byte_idx;
  int b_rx_byte_idx;
  int a_tx_burst_count;
  int b_tx_burst_count;
  int direction_switch_count;
  int halfduplex_overlap_count;
  logic a_busy_q, b_busy_q;
  int last_busy_dir;

  real start_ns;
  real end_ns;
  real elapsed_us;
  real a_to_b_mbps;
  real b_to_a_mbps;
  real aggregate_mbps;
  bit measure_started;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];

  function automatic byte payload_a_to_b(input int pkt, input int idx);
    payload_a_to_b = byte'((8'h31 + (pkt * 13) + (idx * 7)) & 8'hff);
  endfunction

  function automatic byte payload_b_to_a(input int pkt, input int idx);
    payload_b_to_a = byte'((8'h9a + (pkt * 11) + (idx * 5)) & 8'hff);
  endfunction

  task automatic send_a_stream;
    begin
      for (int pkt = 0; pkt < PACKETS_PER_DIR; pkt++) begin
        for (int k = 0; k < PKT_LEN; k++) begin
          @(negedge clk);
          a_tx_data  = payload_a_to_b(pkt, k);
          a_tx_valid = 1'b1;
          a_tx_last  = (k == PKT_LEN - 1);
          do @(posedge clk); while (!a_tx_ready);
        end
        @(negedge clk);
        a_tx_valid = 1'b0;
        a_tx_last  = 1'b0;
      end
    end
  endtask

  task automatic send_b_stream;
    begin
      for (int pkt = 0; pkt < PACKETS_PER_DIR; pkt++) begin
        for (int k = 0; k < PKT_LEN; k++) begin
          @(negedge clk);
          b_tx_data  = payload_b_to_a(pkt, k);
          b_tx_valid = 1'b1;
          b_tx_last  = (k == PKT_LEN - 1);
          do @(posedge clk); while (!b_tx_ready);
        end
        @(negedge clk);
        b_tx_valid = 1'b0;
        b_tx_last  = 1'b0;
      end
    end
  endtask

  always @(negedge clk) begin
    if (!rst_n) begin
      a_rx_ready <= 1'b1;
      b_rx_ready <= 1'b1;
    end else begin
      a_rx_ready <= 1'b1;
      b_rx_ready <= 1'b1;
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      a_tx_done_count        <= 0;
      b_tx_done_count        <= 0;
      a_rx_done_count        <= 0;
      b_rx_done_count        <= 0;
      a_rx_packet_count      <= 0;
      b_rx_packet_count      <= 0;
      a_rx_byte_idx          <= 0;
      b_rx_byte_idx          <= 0;
      a_tx_burst_count       <= 0;
      b_tx_burst_count       <= 0;
      direction_switch_count <= 0;
      halfduplex_overlap_count <= 0;
      a_busy_q               <= 1'b0;
      b_busy_q               <= 1'b0;
      last_busy_dir          <= 0;
    end else begin
      a_busy_q <= a_lane_tx_busy[0];
      b_busy_q <= b_lane_tx_busy[0];

      if (a_lane_tx_busy[0] && b_lane_tx_busy[0]) begin
        halfduplex_overlap_count <= halfduplex_overlap_count + 1;
        $fatal(1, "Half-duplex overlap detected t=%0t debug_a=%08x debug_b=%08x", $time, debug_a, debug_b);
      end

      if (!a_busy_q && a_lane_tx_busy[0]) begin
        a_tx_burst_count <= a_tx_burst_count + 1;
        if (last_busy_dir == 2) direction_switch_count <= direction_switch_count + 1;
        last_busy_dir <= 1;
      end

      if (!b_busy_q && b_lane_tx_busy[0]) begin
        b_tx_burst_count <= b_tx_burst_count + 1;
        if (last_busy_dir == 1) direction_switch_count <= direction_switch_count + 1;
        last_busy_dir <= 2;
      end

      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;
      if (b_tx_done) b_tx_done_count <= b_tx_done_count + 1;
      if (a_rx_done) a_rx_done_count <= a_rx_done_count + 1;
      if (b_rx_done) b_rx_done_count <= b_rx_done_count + 1;

      if (a_tx_overflow || b_tx_overflow || a_tx_exhaust || b_tx_exhaust ||
          a_rx_header_error || b_rx_header_error ||
          a_rx_protocol_error || b_rx_protocol_error ||
          a_rx_frame_overflow_any || b_rx_frame_overflow_any ||
          a_rx_crc_error_any || b_rx_crc_error_any ||
          a_rx_overrun_any || b_rx_overrun_any) begin
        $fatal(1,
          "Unexpected TDM stream error t=%0t a_tx_ov=%0b b_tx_ov=%0b a_exh=%0b b_exh=%0b a_hdr=%0b b_hdr=%0b a_proto=%0b b_proto=%0b a_frame=%0b b_frame=%0b a_crc=%0b b_crc=%0b a_ovr=%0b b_ovr=%0b debug_a=%08x debug_b=%08x",
          $time, a_tx_overflow, b_tx_overflow, a_tx_exhaust, b_tx_exhaust,
          a_rx_header_error, b_rx_header_error, a_rx_protocol_error, b_rx_protocol_error,
          a_rx_frame_overflow_any, b_rx_frame_overflow_any, a_rx_crc_error_any,
          b_rx_crc_error_any, a_rx_overrun_any, b_rx_overrun_any, debug_a, debug_b);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (b_rx_packet_count >= PACKETS_PER_DIR) $fatal(1, "B received too many A-to-B packets");
        if (b_rx_byte_idx >= PKT_LEN) $fatal(1, "B received too many bytes in packet");
        if (b_rx_data !== payload_a_to_b(b_rx_packet_count, b_rx_byte_idx)) begin
          $fatal(1, "A-to-B mismatch pkt=%0d byte=%0d exp=%02x got=%02x",
                 b_rx_packet_count, b_rx_byte_idx,
                 payload_a_to_b(b_rx_packet_count, b_rx_byte_idx), b_rx_data);
        end
        if (b_rx_last) begin
          if (b_rx_byte_idx != PKT_LEN - 1) $fatal(1, "A-to-B length mismatch pkt=%0d got=%0d", b_rx_packet_count, b_rx_byte_idx + 1);
          b_rx_packet_count <= b_rx_packet_count + 1;
          b_rx_byte_idx     <= 0;
        end else begin
          b_rx_byte_idx <= b_rx_byte_idx + 1;
        end
      end

      if (a_rx_valid && a_rx_ready) begin
        if (a_rx_packet_count >= PACKETS_PER_DIR) $fatal(1, "A received too many B-to-A packets");
        if (a_rx_byte_idx >= PKT_LEN) $fatal(1, "A received too many bytes in packet");
        if (a_rx_data !== payload_b_to_a(a_rx_packet_count, a_rx_byte_idx)) begin
          $fatal(1, "B-to-A mismatch pkt=%0d byte=%0d exp=%02x got=%02x",
                 a_rx_packet_count, a_rx_byte_idx,
                 payload_b_to_a(a_rx_packet_count, a_rx_byte_idx), a_rx_data);
        end
        if (a_rx_last) begin
          if (a_rx_byte_idx != PKT_LEN - 1) $fatal(1, "B-to-A length mismatch pkt=%0d got=%0d", a_rx_packet_count, a_rx_byte_idx + 1);
          a_rx_packet_count <= a_rx_packet_count + 1;
          a_rx_byte_idx     <= 0;
        end else begin
          a_rx_byte_idx <= a_rx_byte_idx + 1;
        end
      end
    end
  end

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(0),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(64),
    .FRAG_TIMEOUT_CYCLES(120000),
    .TX_TO_RX_GUARD_CYCLES(1408),
    .BACKOFF_SLOT_CYCLES(1024),
    .REASSEMBLY_TIMEOUT_CYCLES(200000)
  ) dut_a (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_a), .session_id(16'h7d41),
    .lane_enable_mask('1), .rx_lane_enable_mask('1),
    .s_axis_tx_tdata(a_tx_data), .s_axis_tx_tvalid(a_tx_valid), .s_axis_tx_tready(a_tx_ready), .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data), .m_axis_rx_tvalid(a_rx_valid), .m_axis_rx_tready(a_rx_ready), .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out), .ir_rx_in(a_ir_rx_in), .ir_sd(a_ir_sd), .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(), .tx_packet_loading(), .tx_done_pulse(a_tx_done),
    .tx_error_overflow(a_tx_overflow), .tx_error_retry_exhausted(a_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_a), .rx_ctx_complete(unused_rx_ctx_complete_a), .rx_done_pulse(a_rx_done),
    .rx_header_error(a_rx_header_error), .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(a_rx_frame_overflow_any), .rx_crc_error_any(a_rx_crc_error_any), .rx_overrun_error_any(a_rx_overrun_any),
    .lane_tx_busy_dbg(a_lane_tx_busy), .lane_tx_load_pulse_dbg(unused_lane_pulse_a),
    .lane_rx_frame_pulse_dbg(unused_rx_pulse_a), .lane_rx_crc_error_dbg(unused_crc_a), .lane_rx_error_dbg(unused_err_a),
    .tx_frag_pending_dbg(unused_tx_pending_a), .tx_frag_inflight_dbg(unused_tx_inflight_a), .tx_frag_acked_dbg(unused_tx_acked_a),
    .rx_recv_bitmap_dbg(unused_rx_bitmap_a), .debug_status(debug_a)
  );

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(1),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(64),
    .FRAG_TIMEOUT_CYCLES(120000),
    .TX_TO_RX_GUARD_CYCLES(1408),
    .BACKOFF_SLOT_CYCLES(1024),
    .REASSEMBLY_TIMEOUT_CYCLES(200000)
  ) dut_b (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_b), .session_id(16'h7d41),
    .lane_enable_mask('1), .rx_lane_enable_mask('1),
    .s_axis_tx_tdata(b_tx_data), .s_axis_tx_tvalid(b_tx_valid), .s_axis_tx_tready(b_tx_ready), .s_axis_tx_tlast(b_tx_last),
    .m_axis_rx_tdata(b_rx_data), .m_axis_rx_tvalid(b_rx_valid), .m_axis_rx_tready(b_rx_ready), .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out), .ir_rx_in(b_ir_rx_in), .ir_sd(b_ir_sd), .ir_mode_out(b_ir_mode_out),
    .tx_packet_active(), .tx_packet_loading(), .tx_done_pulse(b_tx_done),
    .tx_error_overflow(b_tx_overflow), .tx_error_retry_exhausted(b_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_b), .rx_ctx_complete(unused_rx_ctx_complete_b), .rx_done_pulse(b_rx_done),
    .rx_header_error(b_rx_header_error), .rx_protocol_error(b_rx_protocol_error),
    .rx_frame_overflow_any(b_rx_frame_overflow_any), .rx_crc_error_any(b_rx_crc_error_any), .rx_overrun_error_any(b_rx_overrun_any),
    .lane_tx_busy_dbg(b_lane_tx_busy), .lane_tx_load_pulse_dbg(unused_lane_pulse_b),
    .lane_rx_frame_pulse_dbg(unused_rx_pulse_b), .lane_rx_crc_error_dbg(unused_crc_b), .lane_rx_error_dbg(unused_err_b),
    .tx_frag_pending_dbg(unused_tx_pending_b), .tx_frag_inflight_dbg(unused_tx_inflight_b), .tx_frag_acked_dbg(unused_tx_acked_b),
    .rx_recv_bitmap_dbg(unused_rx_bitmap_b), .debug_status(debug_b)
  );

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    enable_a = 1'b0;
    enable_b = 1'b0;
    a_tx_data = 8'h00;
    b_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    b_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_last = 1'b0;
    measure_started = 1'b0;

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (200) @(posedge clk);

    measure_started = 1'b1;
    start_ns = $realtime;
    fork
      send_a_stream();
      send_b_stream();
    join_none

    repeat (40000000) begin
      @(posedge clk);
      if (measure_started &&
          a_rx_packet_count == PACKETS_PER_DIR &&
          b_rx_packet_count == PACKETS_PER_DIR &&
          a_tx_done_count == PACKETS_PER_DIR &&
          b_tx_done_count == PACKETS_PER_DIR &&
          a_rx_done_count == PACKETS_PER_DIR &&
          b_rx_done_count == PACKETS_PER_DIR) begin
        end_ns = $realtime;
        elapsed_us = (end_ns - start_ns) / 1000.0;
        a_to_b_mbps = (PACKETS_PER_DIR * PKT_LEN * 8.0) / elapsed_us;
        b_to_a_mbps = (PACKETS_PER_DIR * PKT_LEN * 8.0) / elapsed_us;
        aggregate_mbps = a_to_b_mbps + b_to_a_mbps;
        $display("IR_STREAM_TDM_PERF_SINGLE_LANE_PASS packets_each_direction=%0d payload_bytes=%0d elapsed_us=%0.3f a_to_b_mbps=%0.6f b_to_a_mbps=%0.6f aggregate_mbps=%0.6f a_tx_bursts=%0d b_tx_bursts=%0d direction_switches=%0d halfduplex_overlaps=%0d",
                 PACKETS_PER_DIR, PKT_LEN, elapsed_us, a_to_b_mbps, b_to_a_mbps,
                 aggregate_mbps, a_tx_burst_count, b_tx_burst_count,
                 direction_switch_count, halfduplex_overlap_count);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for TDM perf pass a_rx_pkts=%0d b_rx_pkts=%0d a_tx_done=%0d b_tx_done=%0d a_rx_done=%0d b_rx_done=%0d debug_a=%08x debug_b=%08x",
      a_rx_packet_count, b_rx_packet_count, a_tx_done_count, b_tx_done_count,
      a_rx_done_count, b_rx_done_count, debug_a, debug_b);
  end
endmodule
