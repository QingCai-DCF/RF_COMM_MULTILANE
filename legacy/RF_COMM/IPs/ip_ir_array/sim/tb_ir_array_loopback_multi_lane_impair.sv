`timescale 1ns/1ps

module tb_ir_array_loopback_multi_lane_impair;
  localparam int LANE_COUNT       = 4;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;

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

  logic [LANE_COUNT-1:0] drop_ab_mask;
  logic                  drop_ba;
  logic                  arm_lane0_data_drop;
  logic                  arm_final_ack_drop;
  logic [LANE_COUNT-1:0] a_busy_q;
  logic [LANE_COUNT-1:0] b_busy_q;
  int                    a_lane_starts [0:LANE_COUNT-1];
  int                    b_tx_starts;
  int                    ab_lane0_drop_count;
  int                    ba_ack_drop_count;
  int                    b_packet_done_count;
  int                    ready_cycle;
  int                    max_a_busy_lanes;
  int                    max_a_inflight_frags;
  bit                    payload_ok;
  bit                    saw_a_done;

  byte tx_payload [0:MAX_PACKET_BYTES-1];
  byte rx_payload [0:MAX_PACKET_BYTES-1];
  int  rx_count;

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

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  genvar li;
  generate
    for (li = 0; li < LANE_COUNT; li++) begin : g_unstable_optical_loop
      assign b_ir_rx_in[li] = drop_ab_mask[li] ? 1'b1 : ~a_ir_tx_out[li];
      assign a_ir_rx_in[li] = drop_ba         ? 1'b1 : ~b_ir_tx_out[li];
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
      b_rx_ready  <= !((ready_cycle % 17) == 3 || (ready_cycle % 37) == 19);
    end
  end

  always @(posedge clk) begin
    int busy_now;
    int inflight_now;
    if (!rst_n) begin
      drop_ab_mask          <= 4'b0001;
      drop_ba               <= 1'b0;
      arm_lane0_data_drop   <= 1'b1;
      arm_final_ack_drop    <= 1'b0;
      a_busy_q              <= '0;
      b_busy_q              <= '0;
      b_tx_starts           <= 0;
      ab_lane0_drop_count   <= 0;
      ba_ack_drop_count     <= 0;
      b_packet_done_count   <= 0;
      max_a_busy_lanes      <= 0;
      max_a_inflight_frags  <= 0;
      for (int l = 0; l < LANE_COUNT; l++) begin
        a_lane_starts[l] <= 0;
      end
    end else begin
      a_busy_q <= a_lane_tx_busy_dbg;
      b_busy_q <= b_lane_tx_busy_dbg;

      for (int l = 0; l < LANE_COUNT; l++) begin
        if (!a_busy_q[l] && a_lane_tx_busy_dbg[l]) begin
          a_lane_starts[l] <= a_lane_starts[l] + 1;
          $display("A_MULTI_IMPAIR_LANE_TX_START t=%0t lane=%0d starts=%0d",
            $time, l, a_lane_starts[l] + 1);
        end
      end

      if (!a_busy_q[0] && a_lane_tx_busy_dbg[0] && arm_lane0_data_drop && drop_ab_mask[0]) begin
        arm_lane0_data_drop <= 1'b0;
        ab_lane0_drop_count <= ab_lane0_drop_count + 1;
        $display("DROP_AB_LANE0_DATA t=%0t", $time);
      end

      if (a_busy_q[0] && !a_lane_tx_busy_dbg[0] && drop_ab_mask[0] && !arm_lane0_data_drop) begin
        drop_ab_mask[0] <= 1'b0;
        $display("DROP_AB_LANE0_RELEASE t=%0t", $time);
      end

      if (b_rx_done_pulse) begin
        b_packet_done_count <= b_packet_done_count + 1;
        arm_final_ack_drop  <= 1'b1;
        drop_ba             <= 1'b1;
        $display("B_MULTI_IMPAIR_PACKET_DONE_ARM_ACK_DROP t=%0t", $time);
      end

      if ((b_busy_q == '0) && (b_lane_tx_busy_dbg != '0)) begin
        b_tx_starts <= b_tx_starts + 1;
        if (arm_final_ack_drop && drop_ba) begin
          arm_final_ack_drop <= 1'b0;
          ba_ack_drop_count  <= ba_ack_drop_count + 1;
          $display("DROP_BA_COMPLETE_ACK t=%0t b_tx_start=%0d", $time, b_tx_starts + 1);
        end
      end

      if ((b_busy_q != '0) && (b_lane_tx_busy_dbg == '0) && drop_ba && !arm_final_ack_drop) begin
        drop_ba <= 1'b0;
        $display("DROP_BA_COMPLETE_ACK_RELEASE t=%0t", $time);
      end

      busy_now = count_lanes(a_lane_tx_busy_dbg);
      if (busy_now > max_a_busy_lanes) max_a_busy_lanes <= busy_now;

      inflight_now = count_frags(a_tx_frag_inflight_dbg);
      if (inflight_now > max_a_inflight_frags) max_a_inflight_frags <= inflight_now;
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
    session_id_a = 16'h6a5a;
    session_id_b = 16'h6a5a;
    lane_mask_a = '1;
    lane_mask_b = '1;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    rx_count = 0;
    payload_ok = 1'b0;
    saw_a_done = 1'b0;

    for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
      tx_payload[k] = byte'(8'h40 + k);
      rx_payload[k] = 8'h00;
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
      @(posedge clk);
      a_tx_data  <= tx_payload[k];
      a_tx_valid <= 1'b1;
      a_tx_last  <= (k == MAX_PACKET_BYTES-1);
      wait (a_tx_ready);
    end
    @(posedge clk);
    a_tx_valid <= 1'b0;
    a_tx_last  <= 1'b0;

    repeat (4000000) begin
      @(posedge clk);
      if (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_tx_error_overflow || b_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any) begin
        $fatal(1,
          "Multi-lane impair error flags: a_tx_overflow=%0b a_retry=%0b b_tx_overflow=%0b b_retry=%0b b_hdr=%0b b_proto=%0b b_overflow=%0b b_crc=%0b b_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_tx_error_overflow, b_tx_error_retry_exhausted,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
      end

      if (a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any) begin
        $fatal(1,
          "Unexpected A-side receive error: rx_hdr=%0b rx_proto=%0b rx_overflow=%0b rx_crc=%0b rx_overrun=%0b",
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any);
      end

      if (a_tx_done_pulse) saw_a_done = 1'b1;

      if (b_rx_valid && b_rx_ready) begin
        if (payload_ok) begin
          $fatal(1, "Multi-lane impaired payload was delivered more than once");
        end
        if (rx_count >= MAX_PACKET_BYTES) begin
          $fatal(1, "Received more bytes than expected");
        end
        if (b_rx_data !== tx_payload[rx_count]) begin
          $fatal(1, "Mismatch at %0d exp=%02x got=%02x", rx_count, tx_payload[rx_count], b_rx_data);
        end
        rx_payload[rx_count] = b_rx_data;
        rx_count = rx_count + 1;
        if (b_rx_last) begin
          if (rx_count != MAX_PACKET_BYTES) begin
            $fatal(1, "RX length mismatch exp=%0d got=%0d", MAX_PACKET_BYTES, rx_count);
          end
          payload_ok = 1'b1;
          $display("B_MULTI_IMPAIR_PAYLOAD_OK t=%0t bytes=%0d", $time, rx_count);
        end
      end

      if (payload_ok && saw_a_done && !a_tx_packet_active && !a_tx_packet_loading &&
          !b_rx_ctx_valid && !b_rx_ctx_complete) begin
        if (ab_lane0_drop_count != 1) $fatal(1, "Expected one A->B lane-0 data drop, got %0d", ab_lane0_drop_count);
        if (ba_ack_drop_count != 1) $fatal(1, "Expected one B->A complete-ACK drop, got %0d", ba_ack_drop_count);
        if (b_packet_done_count != 1) $fatal(1, "Expected one payload completion, got %0d", b_packet_done_count);
        if (a_lane_starts[0] < 2) $fatal(1, "Expected lane 0 retransmission, starts=%0d", a_lane_starts[0]);
        for (int l = 1; l < LANE_COUNT; l++) begin
          if (a_lane_starts[l] < 1) $fatal(1, "Expected lane %0d to transmit at least once", l);
        end
        if (max_a_busy_lanes < LANE_COUNT) begin
          $fatal(1, "Expected %0d busy lanes concurrently, got %0d", LANE_COUNT, max_a_busy_lanes);
        end
        if (max_a_inflight_frags < LANE_COUNT) begin
          $fatal(1, "Expected %0d in-flight fragments concurrently, got %0d", LANE_COUNT, max_a_inflight_frags);
        end
        $display("LOOPBACK_MULTI_LANE_IMPAIR_PASS bytes=%0d max_busy_lanes=%0d max_inflight_frags=%0d lane_starts=%0d,%0d,%0d,%0d ab_lane0_drops=%0d ba_ack_drops=%0d",
          rx_count, max_a_busy_lanes, max_a_inflight_frags,
          a_lane_starts[0], a_lane_starts[1], a_lane_starts[2], a_lane_starts[3],
          ab_lane0_drop_count, ba_ack_drop_count);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for multi-lane impaired recovery");
  end
endmodule
