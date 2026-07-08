`timescale 1ns/1ps

module tb_ir_array_loopback_8lane;
  localparam int LANE_COUNT       = 8;
  localparam int MAX_PACKET_BYTES = 128;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam int PACKET_COUNT     = 4;
  localparam int TOTAL_BYTES      = PACKET_COUNT * MAX_PACKET_BYTES;

  logic clk;
  logic rst_n;
  logic enable_a, enable_b;
  logic [15:0] session_id_a, session_id_b;
  logic [LANE_COUNT-1:0] lane_mask_a, lane_mask_b;

  logic [7:0] a_tx_data;
  logic       a_tx_valid;
  logic       a_tx_ready;
  logic       a_tx_last;
  logic [7:0] a_rx_data;
  logic       a_rx_valid;
  logic       a_rx_ready;
  logic       a_rx_last;

  logic [7:0] b_tx_data;
  logic       b_tx_valid;
  logic       b_tx_ready;
  logic       b_tx_last;
  logic [7:0] b_rx_data;
  logic       b_rx_valid;
  logic       b_rx_ready;
  logic       b_rx_last;

  logic [LANE_COUNT-1:0] a_ir_tx_out, b_ir_tx_out;
  logic [LANE_COUNT-1:0] a_ir_rx_in,  b_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd, a_ir_mode_out, b_ir_sd, b_ir_mode_out;

  logic a_tx_packet_active, a_tx_packet_loading, a_tx_done_pulse, a_tx_error_overflow, a_tx_error_retry_exhausted;
  logic a_rx_ctx_valid, a_rx_ctx_complete, a_rx_done_pulse, a_rx_header_error, a_rx_protocol_error;
  logic a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any;
  logic [LANE_COUNT-1:0] a_lane_tx_busy_dbg;
  logic [MAX_FRAGS-1:0] a_tx_frag_pending_dbg, a_tx_frag_inflight_dbg, a_tx_frag_acked_dbg, a_rx_recv_bitmap_dbg;

  logic b_tx_packet_active, b_tx_packet_loading, b_tx_done_pulse, b_tx_error_overflow, b_tx_error_retry_exhausted;
  logic b_rx_ctx_valid, b_rx_ctx_complete, b_rx_done_pulse, b_rx_header_error, b_rx_protocol_error;
  logic b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any;
  logic [LANE_COUNT-1:0] b_lane_tx_busy_dbg;
  logic [MAX_FRAGS-1:0] b_tx_frag_pending_dbg, b_tx_frag_inflight_dbg, b_tx_frag_acked_dbg, b_rx_recv_bitmap_dbg;

  logic [LANE_COUNT-1:0] a_busy_q;
  int a_lane_starts [0:LANE_COUNT-1];
  int max_a_busy_lanes;
  int max_a_inflight_frags;
  int ready_cycle;
  int sent_packets;
  int rx_packet_idx;
  int rx_byte_idx;
  int rx_total_count;
  int tx_done_count;
  int b_done_count;
  bit sender_done;

  byte expected [0:PACKET_COUNT-1][0:MAX_PACKET_BYTES-1];

  function automatic int count_lanes(input logic [LANE_COUNT-1:0] bits);
    int n;
    begin
      count_lanes = 0;
      for (n = 0; n < LANE_COUNT; n++) begin
        if (bits[n]) count_lanes++;
      end
    end
  endfunction

  function automatic int count_frags(input logic [MAX_FRAGS-1:0] bits);
    int n;
    begin
      count_frags = 0;
      for (n = 0; n < MAX_FRAGS; n++) begin
        if (bits[n]) count_frags++;
      end
    end
  endfunction

  always #7.8125 clk = ~clk;

  genvar li;
  generate
    for (li = 0; li < LANE_COUNT; li++) begin : g_optical_loop
      assign a_ir_rx_in[li] = ~b_ir_tx_out[li];
      assign b_ir_rx_in[li] = ~a_ir_tx_out[li];
    end
  endgenerate

  task automatic wait_tx_handshake(input int pkt, input int byte_idx);
    int wait_cycles;
    begin
      wait_cycles = 0;
      do begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 1200000) begin
          $fatal(1, "Timeout waiting for TX ready pkt=%0d byte=%0d", pkt, byte_idx);
        end
      end while (!a_tx_ready);
    end
  endtask

  task automatic send_packet(input int pkt);
    begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        @(negedge clk);
        a_tx_data  = expected[pkt][k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == MAX_PACKET_BYTES - 1);
        wait_tx_handshake(pkt, k);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      sent_packets++;
      $display("A_8LANE_PACKET_QUEUED t=%0t pkt=%0d bytes=%0d", $time, pkt, MAX_PACKET_BYTES);
    end
  endtask

  always @(negedge clk) begin
    if (!rst_n) begin
      ready_cycle <= 0;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= 1'b1;
    end else begin
      ready_cycle <= ready_cycle + 1;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= !((ready_cycle % 13) == 5 || (ready_cycle % 29) == 11);
    end
  end

  always @(posedge clk) begin
    int busy_now;
    int inflight_now;
    if (!rst_n) begin
      a_busy_q             <= '0;
      max_a_busy_lanes     <= 0;
      max_a_inflight_frags <= 0;
      rx_packet_idx        <= 0;
      rx_byte_idx          <= 0;
      rx_total_count       <= 0;
      tx_done_count        <= 0;
      b_done_count         <= 0;
      for (int l = 0; l < LANE_COUNT; l++) begin
        a_lane_starts[l] <= 0;
      end
    end else begin
      a_busy_q <= a_lane_tx_busy_dbg;
      for (int l = 0; l < LANE_COUNT; l++) begin
        if (!a_busy_q[l] && a_lane_tx_busy_dbg[l]) begin
          a_lane_starts[l] <= a_lane_starts[l] + 1;
          $display("A_8LANE_TX_START t=%0t lane=%0d starts=%0d", $time, l, a_lane_starts[l] + 1);
        end
      end

      busy_now = count_lanes(a_lane_tx_busy_dbg);
      if (busy_now > max_a_busy_lanes) max_a_busy_lanes <= busy_now;

      inflight_now = count_frags(a_tx_frag_inflight_dbg);
      if (inflight_now > max_a_inflight_frags) max_a_inflight_frags <= inflight_now;

      if (a_tx_done_pulse) begin
        tx_done_count <= tx_done_count + 1;
        $display("A_8LANE_TX_DONE t=%0t count=%0d", $time, tx_done_count + 1);
      end

      if (b_rx_done_pulse) begin
        b_done_count <= b_done_count + 1;
        $display("B_8LANE_RX_DONE t=%0t count=%0d", $time, b_done_count + 1);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (rx_packet_idx >= PACKET_COUNT) begin
          $fatal(1, "Received unexpected extra 8-lane byte data=%02x", b_rx_data);
        end
        if (rx_byte_idx >= MAX_PACKET_BYTES) begin
          $fatal(1, "Packet %0d received more bytes than expected data=%02x", rx_packet_idx, b_rx_data);
        end
        if (b_rx_data !== expected[rx_packet_idx][rx_byte_idx]) begin
          $fatal(1, "Packet %0d byte %0d mismatch exp=%02x got=%02x",
            rx_packet_idx, rx_byte_idx, expected[rx_packet_idx][rx_byte_idx], b_rx_data);
        end
        rx_byte_idx    <= rx_byte_idx + 1;
        rx_total_count <= rx_total_count + 1;

        if (b_rx_last) begin
          if ((rx_byte_idx + 1) != MAX_PACKET_BYTES) begin
            $fatal(1, "Packet %0d length mismatch exp=%0d got=%0d",
              rx_packet_idx, MAX_PACKET_BYTES, rx_byte_idx + 1);
          end
          $display("B_8LANE_PAYLOAD_OK t=%0t pkt=%0d bytes=%0d", $time, rx_packet_idx, rx_byte_idx + 1);
          rx_packet_idx <= rx_packet_idx + 1;
          rx_byte_idx   <= 0;
        end
      end
    end
  end

  ir_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX)
  ) dut_a (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_a), .session_id(session_id_a),
    .lane_enable_mask(lane_mask_a), .rx_lane_enable_mask(lane_mask_a),
    .s_axis_tx_tdata(a_tx_data), .s_axis_tx_tvalid(a_tx_valid), .s_axis_tx_tready(a_tx_ready), .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data), .m_axis_rx_tvalid(a_rx_valid), .m_axis_rx_tready(a_rx_ready), .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out), .ir_rx_in(a_ir_rx_in), .ir_sd(a_ir_sd), .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(a_tx_packet_active), .tx_packet_loading(a_tx_packet_loading), .tx_done_pulse(a_tx_done_pulse),
    .tx_error_overflow(a_tx_error_overflow), .tx_error_retry_exhausted(a_tx_error_retry_exhausted),
    .rx_ctx_valid(a_rx_ctx_valid), .rx_ctx_complete(a_rx_ctx_complete), .rx_done_pulse(a_rx_done_pulse),
    .rx_header_error(a_rx_header_error), .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(a_rx_frame_overflow_any), .rx_crc_error_any(a_rx_crc_error_any), .rx_overrun_error_any(a_rx_overrun_error_any),
    .lane_tx_busy_dbg(a_lane_tx_busy_dbg),
    .tx_frag_pending_dbg(a_tx_frag_pending_dbg), .tx_frag_inflight_dbg(a_tx_frag_inflight_dbg), .tx_frag_acked_dbg(a_tx_frag_acked_dbg),
    .rx_recv_bitmap_dbg(a_rx_recv_bitmap_dbg)
  );

  ir_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX)
  ) dut_b (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_b), .session_id(session_id_b),
    .lane_enable_mask(lane_mask_b), .rx_lane_enable_mask(lane_mask_b),
    .s_axis_tx_tdata(b_tx_data), .s_axis_tx_tvalid(b_tx_valid), .s_axis_tx_tready(b_tx_ready), .s_axis_tx_tlast(b_tx_last),
    .m_axis_rx_tdata(b_rx_data), .m_axis_rx_tvalid(b_rx_valid), .m_axis_rx_tready(b_rx_ready), .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out), .ir_rx_in(b_ir_rx_in), .ir_sd(b_ir_sd), .ir_mode_out(b_ir_mode_out),
    .tx_packet_active(b_tx_packet_active), .tx_packet_loading(b_tx_packet_loading), .tx_done_pulse(b_tx_done_pulse),
    .tx_error_overflow(b_tx_error_overflow), .tx_error_retry_exhausted(b_tx_error_retry_exhausted),
    .rx_ctx_valid(b_rx_ctx_valid), .rx_ctx_complete(b_rx_ctx_complete), .rx_done_pulse(b_rx_done_pulse),
    .rx_header_error(b_rx_header_error), .rx_protocol_error(b_rx_protocol_error),
    .rx_frame_overflow_any(b_rx_frame_overflow_any), .rx_crc_error_any(b_rx_crc_error_any), .rx_overrun_error_any(b_rx_overrun_error_any),
    .lane_tx_busy_dbg(b_lane_tx_busy_dbg),
    .tx_frag_pending_dbg(b_tx_frag_pending_dbg), .tx_frag_inflight_dbg(b_tx_frag_inflight_dbg), .tx_frag_acked_dbg(b_tx_frag_acked_dbg),
    .rx_recv_bitmap_dbg(b_rx_recv_bitmap_dbg)
  );

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    enable_a = 1'b0;
    enable_b = 1'b0;
    session_id_a = 16'h8A08;
    session_id_b = 16'h8A08;
    lane_mask_a = '1;
    lane_mask_b = '1;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    sent_packets = 0;
    sender_done = 1'b0;

    for (int p = 0; p < PACKET_COUNT; p++) begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        expected[p][k] = byte'(8'h21 + (p * 8'h35) + (k * 3));
      end
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    for (int p = 0; p < PACKET_COUNT; p++) begin
      send_packet(p);
    end
    sender_done = 1'b1;
  end

  initial begin
    repeat (30000000) begin
      @(posedge clk);
      #1;
      if (rst_n && (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any)) begin
        $fatal(1,
          "8-lane loopback error flags: tx_overflow=%0b tx_retry_exhausted=%0b rx_hdr=%0b rx_proto=%0b rx_overflow=%0b rx_crc=%0b rx_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
      end

      if (rst_n && (a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any)) begin
        $fatal(1,
          "Unexpected A-side receive error: rx_hdr=%0b rx_proto=%0b rx_overflow=%0b rx_crc=%0b rx_overrun=%0b",
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any);
      end

      if (sender_done && (sent_packets == PACKET_COUNT) && (rx_packet_idx == PACKET_COUNT) &&
          (rx_total_count == TOTAL_BYTES) && (tx_done_count == PACKET_COUNT) &&
          (b_done_count == PACKET_COUNT) &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete &&
          (a_lane_tx_busy_dbg == '0) && (b_lane_tx_busy_dbg == '0)) begin
        for (int l = 0; l < LANE_COUNT; l++) begin
          if (a_lane_starts[l] < PACKET_COUNT) begin
            $fatal(1, "Expected lane %0d to transmit at least %0d times, got %0d",
              l, PACKET_COUNT, a_lane_starts[l]);
          end
        end
        if (max_a_busy_lanes < LANE_COUNT) begin
          $fatal(1, "Expected %0d busy lanes concurrently, got %0d", LANE_COUNT, max_a_busy_lanes);
        end
        if (max_a_inflight_frags < LANE_COUNT) begin
          $fatal(1, "Expected %0d in-flight fragments concurrently, got %0d", LANE_COUNT, max_a_inflight_frags);
        end
        $display("LOOPBACK_8LANE_PASS packets=%0d bytes=%0d max_busy_lanes=%0d max_inflight_frags=%0d lane_starts=%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
          PACKET_COUNT, rx_total_count, max_a_busy_lanes, max_a_inflight_frags,
          a_lane_starts[0], a_lane_starts[1], a_lane_starts[2], a_lane_starts[3],
          a_lane_starts[4], a_lane_starts[5], a_lane_starts[6], a_lane_starts[7]);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for 8-lane packet reception sent=%0d rx_pkt=%0d rx_byte=%0d rx_total=%0d tx_done=%0d b_done=%0d active=%0b loading=%0b rx_ctx=%0b complete=%0b starts=%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
      sent_packets, rx_packet_idx, rx_byte_idx, rx_total_count, tx_done_count, b_done_count,
      a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete,
      a_lane_starts[0], a_lane_starts[1], a_lane_starts[2], a_lane_starts[3],
      a_lane_starts[4], a_lane_starts[5], a_lane_starts[6], a_lane_starts[7]);
  end
endmodule
