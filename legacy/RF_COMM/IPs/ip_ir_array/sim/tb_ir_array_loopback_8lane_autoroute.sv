`timescale 1ns/1ps

module tb_ir_array_loopback_8lane_autoroute;
  localparam int LANE_COUNT       = 8;
  localparam int LANE_W           = $clog2(LANE_COUNT);
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam int PACKET_COUNT     = 8;

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

  logic [LANE_W-1:0] ab_map [0:LANE_COUNT-1];
  logic [LANE_W-1:0] ba_map [0:LANE_COUNT-1];
  logic [LANE_COUNT-1:0] ab_good_src_mask;
  logic [LANE_COUNT-1:0] ba_good_src_mask;
  logic [LANE_COUNT-1:0] a_busy_q;
  logic [LANE_COUNT-1:0] b_busy_q;
  logic [LANE_COUNT-1:0] b_data_frame_hs;
  logic [LANE_COUNT-1:0] a_ack_frame_hs;

  logic [LANE_COUNT-1:0] pkt_a_tx_used [0:PACKET_COUNT-1];
  logic [LANE_COUNT-1:0] pkt_b_tx_ack_used [0:PACKET_COUNT-1];
  logic [LANE_COUNT-1:0] pkt_b_rx_data_used [0:PACKET_COUNT-1];
  logic [LANE_COUNT-1:0] pkt_a_rx_ack_used [0:PACKET_COUNT-1];
  logic [LANE_COUNT-1:0] packet_good_src_mask [0:PACKET_COUNT-1];
  int                    packet_map_id [0:PACKET_COUNT-1];

  byte expected [0:PACKET_COUNT-1][0:MAX_PACKET_BYTES-1];
  int  packet_len [0:PACKET_COUNT-1];
  int  current_packet_idx;
  int  sent_packets;
  int  rx_packet_idx;
  int  rx_byte_idx;
  int  tx_done_count;
  int  b_done_count;
  int  ready_cycle;
  int  packets_with_failed_attempts;
  logic [LANE_COUNT-1:0] good_src_coverage;
  logic [LANE_COUNT-1:0] tx_attempt_coverage;
  bit  sender_done;

  function automatic logic [LANE_COUNT-1:0] map_ab_mask(input logic [LANE_COUNT-1:0] src_mask);
    begin
      map_ab_mask = '0;
      for (int dst = 0; dst < LANE_COUNT; dst++) begin
        if (src_mask[ab_map[dst]]) map_ab_mask[dst] = 1'b1;
      end
    end
  endfunction

  function automatic logic [LANE_COUNT-1:0] map_ba_mask(input logic [LANE_COUNT-1:0] src_mask);
    begin
      map_ba_mask = '0;
      for (int dst = 0; dst < LANE_COUNT; dst++) begin
        if (src_mask[ba_map[dst]]) map_ba_mask[dst] = 1'b1;
      end
    end
  endfunction

  always #7.8125 clk = ~clk;

  always_comb begin
    for (int l = 0; l < LANE_COUNT; l++) begin
      b_ir_rx_in[l] = ab_good_src_mask[ab_map[l]] ? ~a_ir_tx_out[ab_map[l]] : 1'b1;
      a_ir_rx_in[l] = ba_good_src_mask[ba_map[l]] ? ~b_ir_tx_out[ba_map[l]] : 1'b1;
    end
  end

  always @(negedge clk) begin
    if (!rst_n) begin
      ready_cycle <= 0;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= 1'b1;
    end else begin
      ready_cycle <= ready_cycle + 1;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= !((ready_cycle % 23) == 11 || (ready_cycle % 47) == 17 || (ready_cycle % 101) == 37);
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      a_busy_q <= '0;
      b_busy_q <= '0;
      current_packet_idx <= -1;
      for (int p = 0; p < PACKET_COUNT; p++) begin
        pkt_a_tx_used[p]      <= '0;
        pkt_b_tx_ack_used[p]  <= '0;
        pkt_b_rx_data_used[p] <= '0;
        pkt_a_rx_ack_used[p]  <= '0;
      end
    end else begin
      a_busy_q <= a_lane_tx_busy_dbg;
      b_busy_q <= b_lane_tx_busy_dbg;

      if ((current_packet_idx >= 0) && (current_packet_idx < PACKET_COUNT)) begin
        for (int l = 0; l < LANE_COUNT; l++) begin
          if (!a_busy_q[l] && a_lane_tx_busy_dbg[l]) begin
            pkt_a_tx_used[current_packet_idx][l] <= 1'b1;
            $display("A_8LANE_AUTOROUTE_TX_ATTEMPT t=%0t pkt=%0d lane=%0d good=%08b",
              $time, current_packet_idx, l, ab_good_src_mask);
          end
          if (!b_busy_q[l] && b_lane_tx_busy_dbg[l]) begin
            pkt_b_tx_ack_used[current_packet_idx][l] <= 1'b1;
          end
          if (b_data_frame_hs[l]) begin
            pkt_b_rx_data_used[current_packet_idx][l] <= 1'b1;
          end
          if (a_ack_frame_hs[l]) begin
            pkt_a_rx_ack_used[current_packet_idx][l] <= 1'b1;
          end
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
        $display("A_8LANE_AUTOROUTE_TX_DONE t=%0t count=%0d", $time, tx_done_count + 1);
      end

      if (b_rx_done_pulse) begin
        b_done_count <= b_done_count + 1;
        $display("B_8LANE_AUTOROUTE_RX_DONE t=%0t count=%0d", $time, b_done_count + 1);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (rx_packet_idx >= PACKET_COUNT) begin
          $fatal(1, "Received unexpected extra 8-lane autoroute packet byte data=%02x", b_rx_data);
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
          $display("B_8LANE_AUTOROUTE_PACKET_OK t=%0t pkt=%0d len=%0d good_src=%08b",
            $time, rx_packet_idx, packet_len[rx_packet_idx], packet_good_src_mask[rx_packet_idx]);
          rx_packet_idx <= rx_packet_idx + 1;
          rx_byte_idx   <= 0;
        end
      end
    end
  end

  task automatic set_route_map(input int map_id);
    int src;
    begin
      for (int dst = 0; dst < LANE_COUNT; dst++) begin
        case (map_id % 4)
          0: src = (dst + map_id) % LANE_COUNT;
          1: src = ((dst * 3) + map_id) % LANE_COUNT;
          2: src = (LANE_COUNT - 1 - dst + map_id) % LANE_COUNT;
          default: src = ((dst * 5) + map_id + 1) % LANE_COUNT;
        endcase
        ab_map[dst] = src[LANE_W-1:0];

        case (map_id % 4)
          0: src = (dst + (2 * map_id) + 1) % LANE_COUNT;
          1: src = ((dst * 5) + map_id + 2) % LANE_COUNT;
          2: src = (LANE_COUNT - 1 - dst + (2 * map_id)) % LANE_COUNT;
          default: src = ((dst * 3) + map_id + 3) % LANE_COUNT;
        endcase
        ba_map[dst] = src[LANE_W-1:0];
      end

      $display("AUTOROUTE_8LANE_MAP_SET t=%0t id=%0d ab_dst_to_src=%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d ba_dst_to_src=%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
        $time, map_id,
        ab_map[0], ab_map[1], ab_map[2], ab_map[3], ab_map[4], ab_map[5], ab_map[6], ab_map[7],
        ba_map[0], ba_map[1], ba_map[2], ba_map[3], ba_map[4], ba_map[5], ba_map[6], ba_map[7]);
    end
  endtask

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
    logic [LANE_COUNT-1:0] expected_b_rx;
    logic [LANE_COUNT-1:0] expected_a_rx_ack;
    logic [LANE_COUNT-1:0] failed_attempts;
    begin
      set_route_map(packet_map_id[pkt]);
      ab_good_src_mask = packet_good_src_mask[pkt];
      ba_good_src_mask = '1;
      repeat (20) @(posedge clk);
      current_packet_idx = pkt;

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
      $display("A_8LANE_AUTOROUTE_PACKET_QUEUED t=%0t pkt=%0d len=%0d good_src=%08b map=%0d",
        $time, pkt, packet_len[pkt], ab_good_src_mask, packet_map_id[pkt]);

      wait_cycles = 0;
      while (!((rx_packet_idx > pkt) && (tx_done_count > pkt) && (b_done_count > pkt) &&
               !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete &&
               (a_lane_tx_busy_dbg == '0) && (b_lane_tx_busy_dbg == '0))) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 9000000) begin
          $fatal(1,
            "Timeout waiting for 8-lane autoroute packet completion pkt=%0d rx_pkt=%0d tx_done=%0d b_done=%0d a_active=%0b a_loading=%0b b_rx_ctx=%0b b_rx_complete=%0b a_busy=%08b b_busy=%08b",
            pkt, rx_packet_idx, tx_done_count, b_done_count,
            a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete,
            a_lane_tx_busy_dbg, b_lane_tx_busy_dbg);
        end
      end

      expected_b_rx = map_ab_mask(packet_good_src_mask[pkt]);
      failed_attempts = pkt_a_tx_used[pkt] & ~packet_good_src_mask[pkt];
      if ((pkt_a_tx_used[pkt] & packet_good_src_mask[pkt]) == '0) begin
        $fatal(1, "Packet %0d never tried the available 8-lane route used=%08b good=%08b",
          pkt, pkt_a_tx_used[pkt], packet_good_src_mask[pkt]);
      end
      if (failed_attempts == '0) begin
        $fatal(1, "Packet %0d did not exercise a failed 8-lane route before success used=%08b good=%08b",
          pkt, pkt_a_tx_used[pkt], packet_good_src_mask[pkt]);
      end
      if (pkt_b_rx_data_used[pkt] != expected_b_rx) begin
        $fatal(1, "Packet %0d A->B 8-lane autoroute mismatch used=%08b b_rx=%08b expected=%08b good=%08b map=%0d",
          pkt, pkt_a_tx_used[pkt], pkt_b_rx_data_used[pkt], expected_b_rx, packet_good_src_mask[pkt], packet_map_id[pkt]);
      end
      if (pkt_b_tx_ack_used[pkt] == '0 || pkt_a_rx_ack_used[pkt] == '0) begin
        $fatal(1, "Packet %0d missing 8-lane ACK route activity b_tx_ack=%08b a_rx_ack=%08b",
          pkt, pkt_b_tx_ack_used[pkt], pkt_a_rx_ack_used[pkt]);
      end
      expected_a_rx_ack = map_ba_mask(pkt_b_tx_ack_used[pkt]);
      if ((pkt_a_rx_ack_used[pkt] & expected_a_rx_ack) == '0) begin
        $fatal(1, "Packet %0d B->A 8-lane ACK route mismatch b_tx_ack=%08b a_rx_ack=%08b expected_any=%08b",
          pkt, pkt_b_tx_ack_used[pkt], pkt_a_rx_ack_used[pkt], expected_a_rx_ack);
      end

      packets_with_failed_attempts = packets_with_failed_attempts + 1;
      good_src_coverage = good_src_coverage | packet_good_src_mask[pkt];
      tx_attempt_coverage = tx_attempt_coverage | pkt_a_tx_used[pkt];

      $display("AUTOROUTE_8LANE_PACKET_PASS pkt=%0d map=%0d good_src=%08b tx_attempts=%08b failed_attempts=%08b b_rx_data=%08b b_tx_ack=%08b a_rx_ack=%08b",
        pkt, packet_map_id[pkt], packet_good_src_mask[pkt], pkt_a_tx_used[pkt],
        failed_attempts, pkt_b_rx_data_used[pkt], pkt_b_tx_ack_used[pkt], pkt_a_rx_ack_used[pkt]);
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

  genvar gi;
  generate
    for (gi = 0; gi < LANE_COUNT; gi++) begin : g_route_mon
      assign b_data_frame_hs[gi] =
        dut_b.g_lane[gi].u_lane.rx_frame_valid &&
        dut_b.g_lane[gi].u_lane.rx_frame_ready &&
        (dut_b.g_lane[gi].u_lane.rx_frame_data[8*1 +: 4] == 4'h1);
      assign a_ack_frame_hs[gi] =
        dut_a.g_lane[gi].u_lane.rx_frame_valid &&
        dut_a.g_lane[gi].u_lane.rx_frame_ready &&
        (dut_a.g_lane[gi].u_lane.rx_frame_data[8*1 +: 4] == 4'h2);
    end
  endgenerate

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    enable_a = 1'b0;
    enable_b = 1'b0;
    session_id_a = 16'h8a21;
    session_id_b = 16'h8a21;
    lane_mask_a = '1;
    lane_mask_b = '1;
    ab_good_src_mask = '1;
    ba_good_src_mask = '1;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    sent_packets = 0;
    packets_with_failed_attempts = 0;
    good_src_coverage = '0;
    tx_attempt_coverage = '0;
    sender_done = 1'b0;
    set_route_map(0);

    for (int p = 0; p < PACKET_COUNT; p++) begin
      packet_len[p] = 16 + (16 * (p % 2));
      packet_map_id[p] = p;
      packet_good_src_mask[p] = 8'b1000_0000 >> p;
    end

    for (int p = 0; p < PACKET_COUNT; p++) begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        expected[p][k] = byte'(8'h31 + (p * 8'h17) + (k * 5));
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
    repeat (96000000) begin
      @(posedge clk);
      if (rst_n && (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_tx_error_overflow || b_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any)) begin
        $fatal(1,
          "8-lane autoroute error flags: a_tx_overflow=%0b a_retry=%0b b_tx_overflow=%0b b_retry=%0b b_hdr=%0b b_proto=%0b b_overflow=%0b b_crc=%0b b_overrun=%0b",
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
        if (packets_with_failed_attempts != PACKET_COUNT) begin
          $fatal(1, "Not every 8-lane autoroute packet exercised failed-route recovery count=%0d packets=%0d",
            packets_with_failed_attempts, PACKET_COUNT);
        end
        if (good_src_coverage != '1 || tx_attempt_coverage != '1) begin
          $fatal(1, "8-lane autoroute coverage mismatch good=%08b tx_attempt=%08b",
            good_src_coverage, tx_attempt_coverage);
        end
        $display("LOOPBACK_8LANE_AUTOROUTE_PASS packets=%0d good_src_coverage=%08b tx_attempt_coverage=%08b failed_route_packets=%0d",
          PACKET_COUNT, good_src_coverage, tx_attempt_coverage, packets_with_failed_attempts);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for 8-lane autoroute completion sent=%0d rx_pkt=%0d rx_byte=%0d tx_done=%0d b_done=%0d current=%0d active=%0b loading=%0b rx_ctx=%0b complete=%0b",
      sent_packets, rx_packet_idx, rx_byte_idx, tx_done_count, b_done_count, current_packet_idx,
      a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete);
  end
endmodule
