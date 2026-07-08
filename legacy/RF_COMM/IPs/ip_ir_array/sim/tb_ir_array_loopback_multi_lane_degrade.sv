`timescale 1ns/1ps

module tb_ir_array_loopback_multi_lane_degrade;
  localparam int LANE_COUNT       = 4;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam int PACKET_COUNT     = 5;

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

  byte expected [0:PACKET_COUNT-1][0:MAX_PACKET_BYTES-1];
  int  packet_len [0:PACKET_COUNT-1];
  logic [LANE_COUNT-1:0] packet_mask [0:PACKET_COUNT-1];

  logic [LANE_COUNT-1:0] a_busy_q;
  int a_lane_starts [0:LANE_COUNT-1];
  int max_busy_by_packet [0:PACKET_COUNT-1];
  int max_inflight_by_packet [0:PACKET_COUNT-1];
  int current_packet_idx;
  int sent_packets;
  int rx_packet_idx;
  int rx_byte_idx;
  int tx_done_count;
  int b_done_count;
  int ready_cycle;
  bit sender_done;

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

  function automatic int frag_count_for_len(input int len);
    begin
      frag_count_for_len = (len + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
    end
  endfunction

  function automatic int min_int(input int a, input int b);
    begin
      min_int = (a < b) ? a : b;
    end
  endfunction

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  genvar li;
  generate
    for (li = 0; li < LANE_COUNT; li++) begin : g_optical_loop
      assign a_ir_rx_in[li] = ~b_ir_tx_out[li];
      assign b_ir_rx_in[li] = ~a_ir_tx_out[li];
    end
  endgenerate

  always @(negedge clk) begin
    if (!rst_n) begin
      ready_cycle <= 0;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= 1'b1;
    end else begin
      ready_cycle <= ready_cycle + 1;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= !((ready_cycle % 13) == 5 || (ready_cycle % 31) == 9);
    end
  end

  always @(posedge clk) begin
    int busy_now;
    int inflight_now;
    if (!rst_n) begin
      a_busy_q          <= '0;
      current_packet_idx <= -1;
      for (int l = 0; l < LANE_COUNT; l++) begin
        a_lane_starts[l] <= 0;
      end
      for (int p = 0; p < PACKET_COUNT; p++) begin
        max_busy_by_packet[p]     <= 0;
        max_inflight_by_packet[p] <= 0;
      end
    end else begin
      a_busy_q <= a_lane_tx_busy_dbg;
      for (int l = 0; l < LANE_COUNT; l++) begin
        if (!a_busy_q[l] && a_lane_tx_busy_dbg[l]) begin
          a_lane_starts[l] <= a_lane_starts[l] + 1;
          $display("A_DEGRADE_LANE_TX_START t=%0t pkt=%0d lane=%0d starts=%0d mask=%04b",
            $time, current_packet_idx, l, a_lane_starts[l] + 1, lane_mask_a);
        end
      end

      if ((current_packet_idx >= 0) && (current_packet_idx < PACKET_COUNT)) begin
        busy_now = count_lanes(a_lane_tx_busy_dbg);
        if (busy_now > max_busy_by_packet[current_packet_idx]) begin
          max_busy_by_packet[current_packet_idx] <= busy_now;
        end

        inflight_now = count_frags(a_tx_frag_inflight_dbg);
        if (inflight_now > max_inflight_by_packet[current_packet_idx]) begin
          max_inflight_by_packet[current_packet_idx] <= inflight_now;
        end
      end
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      rx_packet_idx <= 0;
      rx_byte_idx   <= 0;
      tx_done_count <= 0;
      b_done_count  <= 0;
    end else begin
      if (a_tx_done_pulse) begin
        tx_done_count <= tx_done_count + 1;
        $display("A_DEGRADE_TX_DONE t=%0t count=%0d", $time, tx_done_count + 1);
      end

      if (b_rx_done_pulse) begin
        b_done_count <= b_done_count + 1;
        $display("B_DEGRADE_RX_DONE t=%0t count=%0d", $time, b_done_count + 1);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (rx_packet_idx >= PACKET_COUNT) begin
          $fatal(1, "Received unexpected extra degraded packet byte data=%02x", b_rx_data);
        end
        if (rx_byte_idx >= packet_len[rx_packet_idx]) begin
          $fatal(1, "Packet %0d received more bytes than expected data=%02x", rx_packet_idx, b_rx_data);
        end
        if (b_rx_data !== expected[rx_packet_idx][rx_byte_idx]) begin
          $fatal(1, "Packet %0d byte %0d mismatch exp=%02x got=%02x",
            rx_packet_idx, rx_byte_idx, expected[rx_packet_idx][rx_byte_idx], b_rx_data);
        end
        rx_byte_idx <= rx_byte_idx + 1;

        if (b_rx_last) begin
          if ((rx_byte_idx + 1) != packet_len[rx_packet_idx]) begin
            $fatal(1, "Packet %0d length mismatch exp=%0d got=%0d",
              rx_packet_idx, packet_len[rx_packet_idx], rx_byte_idx + 1);
          end
          $display("B_DEGRADE_PACKET_OK t=%0t pkt=%0d len=%0d mask=%04b",
            $time, rx_packet_idx, packet_len[rx_packet_idx], packet_mask[rx_packet_idx]);
          rx_packet_idx <= rx_packet_idx + 1;
          rx_byte_idx   <= 0;
        end
      end
    end
  end

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
    int wait_cycles;
    int expected_parallel;
    int start_before [0:LANE_COUNT-1];
    logic [LANE_COUNT-1:0] used_mask;
    begin
      lane_mask_a = packet_mask[pkt];
      lane_mask_b = packet_mask[pkt];
      repeat (20) @(posedge clk);
      current_packet_idx = pkt;
      for (int l = 0; l < LANE_COUNT; l++) begin
        start_before[l] = a_lane_starts[l];
      end

      for (int k = 0; k < packet_len[pkt]; k++) begin
        @(negedge clk);
        a_tx_data  = expected[pkt][k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == packet_len[pkt] - 1);
        wait_tx_handshake(pkt, k);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      sent_packets++;
      $display("A_DEGRADE_PACKET_QUEUED t=%0t pkt=%0d len=%0d mask=%04b",
        $time, pkt, packet_len[pkt], packet_mask[pkt]);

      wait_cycles = 0;
      while (!((rx_packet_idx > pkt) && (tx_done_count > pkt) && (b_done_count > pkt) &&
               !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete &&
               (a_lane_tx_busy_dbg == '0) && (b_lane_tx_busy_dbg == '0))) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 5000000) begin
          $fatal(1,
            "Timeout waiting for degraded packet completion pkt=%0d rx_pkt=%0d tx_done=%0d b_done=%0d a_active=%0b a_loading=%0b b_rx_ctx=%0b b_rx_complete=%0b a_busy=%04b b_busy=%04b",
            pkt, rx_packet_idx, tx_done_count, b_done_count,
            a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete,
            a_lane_tx_busy_dbg, b_lane_tx_busy_dbg);
        end
      end

      used_mask = '0;
      for (int l = 0; l < LANE_COUNT; l++) begin
        if (a_lane_starts[l] > start_before[l]) used_mask[l] = 1'b1;
      end

      expected_parallel = min_int(count_lanes(packet_mask[pkt]), frag_count_for_len(packet_len[pkt]));
      if ((used_mask & ~packet_mask[pkt]) != '0) begin
        $fatal(1, "Packet %0d used disabled lanes used=%04b mask=%04b", pkt, used_mask, packet_mask[pkt]);
      end
      if (count_lanes(used_mask) < expected_parallel) begin
        $fatal(1, "Packet %0d expected %0d used lanes, got %0d used=%04b mask=%04b",
          pkt, expected_parallel, count_lanes(used_mask), used_mask, packet_mask[pkt]);
      end
      if (max_busy_by_packet[pkt] < expected_parallel) begin
        $fatal(1, "Packet %0d expected max_busy >= %0d, got %0d",
          pkt, expected_parallel, max_busy_by_packet[pkt]);
      end
      if (max_inflight_by_packet[pkt] < expected_parallel) begin
        $fatal(1, "Packet %0d expected max_inflight >= %0d, got %0d",
          pkt, expected_parallel, max_inflight_by_packet[pkt]);
      end

      $display("DEGRADE_PACKET_PASS pkt=%0d len=%0d mask=%04b used=%04b max_busy=%0d max_inflight=%0d",
        pkt, packet_len[pkt], packet_mask[pkt], used_mask,
        max_busy_by_packet[pkt], max_inflight_by_packet[pkt]);
      current_packet_idx = -1;
      repeat (20) @(posedge clk);
    end
  endtask

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
    session_id_a = 16'h7151;
    session_id_b = 16'h7151;
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

    packet_len[0]  = 64;
    packet_mask[0] = 4'b1111;
    packet_len[1]  = 48;
    packet_mask[1] = 4'b1110;
    packet_len[2]  = 32;
    packet_mask[2] = 4'b0101;
    packet_len[3]  = 16;
    packet_mask[3] = 4'b1000;
    packet_len[4]  = 64;
    packet_mask[4] = 4'b1111;

    for (int p = 0; p < PACKET_COUNT; p++) begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        expected[p][k] = byte'(8'h50 + (p * 8'h17) + k);
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
    repeat (12000000) begin
      @(posedge clk);
      if (rst_n && (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_tx_error_overflow || b_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any)) begin
        $fatal(1,
          "Multi-lane degrade error flags: a_tx_overflow=%0b a_retry=%0b b_tx_overflow=%0b b_retry=%0b b_hdr=%0b b_proto=%0b b_overflow=%0b b_crc=%0b b_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_tx_error_overflow, b_tx_error_retry_exhausted,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
      end

      if (rst_n && (a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any)) begin
        $fatal(1,
          "Unexpected A-side receive error: rx_hdr=%0b rx_proto=%0b rx_overflow=%0b rx_crc=%0b rx_overrun=%0b",
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any);
      end

      if (sender_done && (sent_packets == PACKET_COUNT) && (rx_packet_idx == PACKET_COUNT) &&
          (tx_done_count == PACKET_COUNT) && (b_done_count == PACKET_COUNT) &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete &&
          (a_lane_tx_busy_dbg == '0) && (b_lane_tx_busy_dbg == '0)) begin
        $display("LOOPBACK_MULTI_LANE_DEGRADE_PASS packets=%0d masks=%04b,%04b,%04b,%04b,%04b max_busy=%0d,%0d,%0d,%0d,%0d max_inflight=%0d,%0d,%0d,%0d,%0d",
          PACKET_COUNT,
          packet_mask[0], packet_mask[1], packet_mask[2], packet_mask[3], packet_mask[4],
          max_busy_by_packet[0], max_busy_by_packet[1], max_busy_by_packet[2], max_busy_by_packet[3], max_busy_by_packet[4],
          max_inflight_by_packet[0], max_inflight_by_packet[1], max_inflight_by_packet[2], max_inflight_by_packet[3], max_inflight_by_packet[4]);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for multi-lane degrade completion sent=%0d rx_pkt=%0d rx_byte=%0d tx_done=%0d b_done=%0d current=%0d active=%0b loading=%0b rx_ctx=%0b complete=%0b",
      sent_packets, rx_packet_idx, rx_byte_idx, tx_done_count, b_done_count, current_packet_idx,
      a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete);
  end
endmodule
