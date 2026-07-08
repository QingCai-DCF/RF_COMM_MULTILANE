`timescale 1ns/1ps

module tb_ir_array_loopback_full_duplex_lane_partition;
`ifdef TB_FDX_4PLUS4
  localparam int LANE_COUNT       = 8;
  localparam logic [LANE_COUNT-1:0] A_TX_MASK = 8'b0000_1111;
  localparam logic [LANE_COUNT-1:0] A_RX_MASK = 8'b1111_0000;
  localparam logic [LANE_COUNT-1:0] B_TX_MASK = 8'b1111_0000;
  localparam logic [LANE_COUNT-1:0] B_RX_MASK = 8'b0000_1111;
  localparam int EXPECT_BUSY_PER_DIR = 4;
  localparam int EXPECT_TOTAL_BUSY   = 8;
  localparam int EXPECT_INFLIGHT_PER_DIR = 4;
`elsif TB_FDX_1PLUS1
  localparam int LANE_COUNT       = 2;
  localparam logic [LANE_COUNT-1:0] A_TX_MASK = 2'b01;
  localparam logic [LANE_COUNT-1:0] A_RX_MASK = 2'b10;
  localparam logic [LANE_COUNT-1:0] B_TX_MASK = 2'b10;
  localparam logic [LANE_COUNT-1:0] B_RX_MASK = 2'b01;
  localparam int EXPECT_BUSY_PER_DIR = 1;
  localparam int EXPECT_TOTAL_BUSY   = 2;
  localparam int EXPECT_INFLIGHT_PER_DIR = 1;
`else
  localparam int LANE_COUNT       = 4;
  localparam logic [LANE_COUNT-1:0] A_TX_MASK = 4'b0011;
  localparam logic [LANE_COUNT-1:0] A_RX_MASK = 4'b1100;
  localparam logic [LANE_COUNT-1:0] B_TX_MASK = 4'b1100;
  localparam logic [LANE_COUNT-1:0] B_RX_MASK = 4'b0011;
  localparam int EXPECT_BUSY_PER_DIR = 2;
  localparam int EXPECT_TOTAL_BUSY   = 4;
  localparam int EXPECT_INFLIGHT_PER_DIR = 2;
`endif
`ifndef TB_FDX_MAX_PACKET_BYTES
`ifdef TB_FDX_256B
`define TB_FDX_MAX_PACKET_BYTES 256
`else
`define TB_FDX_MAX_PACKET_BYTES 64
`endif
`endif
  localparam int MAX_PACKET_BYTES = `TB_FDX_MAX_PACKET_BYTES;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam int PACKET_COUNT     = 8;
  localparam int TOTAL_BYTES      = PACKET_COUNT * MAX_PACKET_BYTES;

  logic clk;
  logic rst_n;
  logic enable_a, enable_b;
  logic [15:0] session_id_a, session_id_b;
  logic [LANE_COUNT-1:0] a_tx_lane_mask, a_rx_lane_mask;
  logic [LANE_COUNT-1:0] b_tx_lane_mask, b_rx_lane_mask;

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

  byte ab_payload [0:PACKET_COUNT-1][0:MAX_PACKET_BYTES-1];
  byte ba_payload [0:PACKET_COUNT-1][0:MAX_PACKET_BYTES-1];
  int  a_rx_packet_idx;
  int  a_rx_byte_idx;
  int  b_rx_packet_idx;
  int  b_rx_byte_idx;
  int  a_rx_total_count;
  int  b_rx_total_count;
  int  a_tx_done_count;
  int  b_tx_done_count;
  int  a_rx_done_count;
  int  b_rx_done_count;
  int  ab_sent_count;
  int  ba_sent_count;
  int  ready_cycle;
  int  max_a_busy_lanes;
  int  max_b_busy_lanes;
  int  max_total_busy_lanes;
  int  max_a_inflight_frags;
  int  max_b_inflight_frags;
  real first_queue_time_ns;
  real completion_time_ns;
  real elapsed_us;
  real ab_mbps;
  real ba_mbps;
  real aggregate_mbps;
  bit  fdx_timer_started;
  bit  ab_sender_done;
  bit  ba_sender_done;

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
    for (li = 0; li < LANE_COUNT; li++) begin : g_optical_loop
      assign a_ir_rx_in[li] = ~b_ir_tx_out[li];
      assign b_ir_rx_in[li] = ~a_ir_tx_out[li];
    end
  endgenerate

  task automatic wait_a_tx_ready(input int byte_idx);
    int wait_cycles;
    begin
      wait_cycles = 0;
      do begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 1200000) begin
          $fatal(1, "Timeout waiting for A TX ready byte=%0d", byte_idx);
        end
      end while (!a_tx_ready);
    end
  endtask

  task automatic wait_b_tx_ready(input int byte_idx);
    int wait_cycles;
    begin
      wait_cycles = 0;
      do begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 1200000) begin
          $fatal(1, "Timeout waiting for B TX ready byte=%0d", byte_idx);
        end
      end while (!b_tx_ready);
    end
  endtask

  task automatic send_a_to_b(input int pkt);
    begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        @(negedge clk);
        a_tx_data  = ab_payload[pkt][k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == MAX_PACKET_BYTES - 1);
        wait_a_tx_ready(k);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      if (!fdx_timer_started) begin
        first_queue_time_ns = $realtime;
        fdx_timer_started = 1'b1;
      end
      ab_sent_count++;
      $display("A_TO_B_FDX_PACKET_QUEUED t=%0t pkt=%0d bytes=%0d", $time, pkt, MAX_PACKET_BYTES);
    end
  endtask

  task automatic send_b_to_a(input int pkt);
    begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        @(negedge clk);
        b_tx_data  = ba_payload[pkt][k];
        b_tx_valid = 1'b1;
        b_tx_last  = (k == MAX_PACKET_BYTES - 1);
        wait_b_tx_ready(k);
      end
      @(negedge clk);
      b_tx_valid = 1'b0;
      b_tx_last  = 1'b0;
      if (!fdx_timer_started) begin
        first_queue_time_ns = $realtime;
        fdx_timer_started = 1'b1;
      end
      ba_sent_count++;
      $display("B_TO_A_FDX_PACKET_QUEUED t=%0t pkt=%0d bytes=%0d", $time, pkt, MAX_PACKET_BYTES);
    end
  endtask

  always @(negedge clk) begin
    if (!rst_n) begin
      ready_cycle <= 0;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= 1'b1;
    end else begin
      ready_cycle <= ready_cycle + 1;
      a_rx_ready  <= !((ready_cycle % 13) == 4 || (ready_cycle % 29) == 11);
      b_rx_ready  <= !((ready_cycle % 11) == 3 || (ready_cycle % 23) == 7);
    end
  end

  always @(posedge clk) begin
    int a_busy_now;
    int b_busy_now;
    int total_busy_now;
    int a_inflight_now;
    int b_inflight_now;
    if (!rst_n) begin
      a_rx_packet_idx      <= 0;
      a_rx_byte_idx        <= 0;
      b_rx_packet_idx      <= 0;
      b_rx_byte_idx        <= 0;
      a_rx_total_count     <= 0;
      b_rx_total_count     <= 0;
      a_tx_done_count      <= 0;
      b_tx_done_count      <= 0;
      a_rx_done_count      <= 0;
      b_rx_done_count      <= 0;
      max_a_busy_lanes     <= 0;
      max_b_busy_lanes     <= 0;
      max_total_busy_lanes <= 0;
      max_a_inflight_frags <= 0;
      max_b_inflight_frags <= 0;
    end else begin
      a_busy_now = count_lanes(a_lane_tx_busy_dbg);
      b_busy_now = count_lanes(b_lane_tx_busy_dbg);
      total_busy_now = a_busy_now + b_busy_now;
      a_inflight_now = count_frags(a_tx_frag_inflight_dbg);
      b_inflight_now = count_frags(b_tx_frag_inflight_dbg);

      if (a_busy_now > max_a_busy_lanes) max_a_busy_lanes <= a_busy_now;
      if (b_busy_now > max_b_busy_lanes) max_b_busy_lanes <= b_busy_now;
      if (total_busy_now > max_total_busy_lanes) max_total_busy_lanes <= total_busy_now;
      if (a_inflight_now > max_a_inflight_frags) max_a_inflight_frags <= a_inflight_now;
      if (b_inflight_now > max_b_inflight_frags) max_b_inflight_frags <= b_inflight_now;

      if (a_tx_done_pulse) begin
        a_tx_done_count <= a_tx_done_count + 1;
        $display("A_FDX_TX_DONE t=%0t count=%0d", $time, a_tx_done_count + 1);
      end

      if (b_tx_done_pulse) begin
        b_tx_done_count <= b_tx_done_count + 1;
        $display("B_FDX_TX_DONE t=%0t count=%0d", $time, b_tx_done_count + 1);
      end

      if (a_rx_done_pulse) begin
        a_rx_done_count <= a_rx_done_count + 1;
        $display("A_FDX_RX_DONE t=%0t count=%0d", $time, a_rx_done_count + 1);
      end

      if (b_rx_done_pulse) begin
        b_rx_done_count <= b_rx_done_count + 1;
        $display("B_FDX_RX_DONE t=%0t count=%0d", $time, b_rx_done_count + 1);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (b_rx_packet_idx >= PACKET_COUNT) begin
          $fatal(1, "B received extra A-to-B packet byte data=%02x", b_rx_data);
        end
        if (b_rx_byte_idx >= MAX_PACKET_BYTES) begin
          $fatal(1, "B received more A-to-B bytes than expected pkt=%0d data=%02x",
            b_rx_packet_idx, b_rx_data);
        end
        if (b_rx_data !== ab_payload[b_rx_packet_idx][b_rx_byte_idx]) begin
          $fatal(1, "A-to-B pkt=%0d byte=%0d mismatch exp=%02x got=%02x",
            b_rx_packet_idx, b_rx_byte_idx, ab_payload[b_rx_packet_idx][b_rx_byte_idx], b_rx_data);
        end
        b_rx_byte_idx <= b_rx_byte_idx + 1;
        b_rx_total_count <= b_rx_total_count + 1;

        if (b_rx_last) begin
          if ((b_rx_byte_idx + 1) != MAX_PACKET_BYTES) begin
            $fatal(1, "A-to-B length mismatch pkt=%0d exp=%0d got=%0d",
              b_rx_packet_idx, MAX_PACKET_BYTES, b_rx_byte_idx + 1);
          end
          $display("A_TO_B_FDX_PAYLOAD_OK t=%0t pkt=%0d bytes=%0d",
            $time, b_rx_packet_idx, b_rx_byte_idx + 1);
          b_rx_packet_idx <= b_rx_packet_idx + 1;
          b_rx_byte_idx   <= 0;
        end
      end

      if (a_rx_valid && a_rx_ready) begin
        if (a_rx_packet_idx >= PACKET_COUNT) begin
          $fatal(1, "A received extra B-to-A packet byte data=%02x", a_rx_data);
        end
        if (a_rx_byte_idx >= MAX_PACKET_BYTES) begin
          $fatal(1, "A received more B-to-A bytes than expected pkt=%0d data=%02x",
            a_rx_packet_idx, a_rx_data);
        end
        if (a_rx_data !== ba_payload[a_rx_packet_idx][a_rx_byte_idx]) begin
          $fatal(1, "B-to-A pkt=%0d byte=%0d mismatch exp=%02x got=%02x",
            a_rx_packet_idx, a_rx_byte_idx, ba_payload[a_rx_packet_idx][a_rx_byte_idx], a_rx_data);
        end
        a_rx_byte_idx <= a_rx_byte_idx + 1;
        a_rx_total_count <= a_rx_total_count + 1;

        if (a_rx_last) begin
          if ((a_rx_byte_idx + 1) != MAX_PACKET_BYTES) begin
            $fatal(1, "B-to-A length mismatch pkt=%0d exp=%0d got=%0d",
              a_rx_packet_idx, MAX_PACKET_BYTES, a_rx_byte_idx + 1);
          end
          $display("B_TO_A_FDX_PAYLOAD_OK t=%0t pkt=%0d bytes=%0d",
            $time, a_rx_packet_idx, a_rx_byte_idx + 1);
          a_rx_packet_idx <= a_rx_packet_idx + 1;
          a_rx_byte_idx   <= 0;
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
    .lane_enable_mask(a_tx_lane_mask), .rx_lane_enable_mask(a_rx_lane_mask),
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
    .lane_enable_mask(b_tx_lane_mask), .rx_lane_enable_mask(b_rx_lane_mask),
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
    session_id_a = 16'h5678;
    session_id_b = 16'h5678;
    a_tx_lane_mask = A_TX_MASK;
    a_rx_lane_mask = A_RX_MASK;
    b_tx_lane_mask = B_TX_MASK;
    b_rx_lane_mask = B_RX_MASK;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    ab_sent_count = 0;
    ba_sent_count = 0;
    first_queue_time_ns = 0.0;
    completion_time_ns = 0.0;
    elapsed_us = 0.0;
    ab_mbps = 0.0;
    ba_mbps = 0.0;
    aggregate_mbps = 0.0;
    fdx_timer_started = 1'b0;
    ab_sender_done = 1'b0;
    ba_sender_done = 1'b0;

    for (int p = 0; p < PACKET_COUNT; p++) begin
      for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
        ab_payload[p][k] = byte'(8'h20 + (p * 8'h13) + k);
        ba_payload[p][k] = byte'(8'hc0 - (p * 8'h17) - k);
      end
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    for (int p = 0; p < PACKET_COUNT; p++) begin
      fork
        send_a_to_b(p);
        send_b_to_a(p);
      join
    end
    ab_sender_done = 1'b1;
    ba_sender_done = 1'b1;
  end

  initial begin
    repeat (30000000) begin
      @(posedge clk);
      if (rst_n && (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_tx_error_overflow || b_tx_error_retry_exhausted ||
          a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any)) begin
        $fatal(1,
          "Full-duplex lane-partition error flags: a_tx_overflow=%0b a_retry=%0b b_tx_overflow=%0b b_retry=%0b a_hdr=%0b a_proto=%0b a_frame_overflow=%0b a_crc=%0b a_overrun=%0b b_hdr=%0b b_proto=%0b b_frame_overflow=%0b b_crc=%0b b_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_tx_error_overflow, b_tx_error_retry_exhausted,
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
      end

      if (ab_sender_done && ba_sender_done &&
          (ab_sent_count == PACKET_COUNT) && (ba_sent_count == PACKET_COUNT) &&
          (a_tx_done_count == PACKET_COUNT) && (b_tx_done_count == PACKET_COUNT) &&
          (a_rx_done_count == PACKET_COUNT) && (b_rx_done_count == PACKET_COUNT) &&
          (a_rx_packet_idx == PACKET_COUNT) && (b_rx_packet_idx == PACKET_COUNT) &&
          (a_rx_total_count == TOTAL_BYTES) && (b_rx_total_count == TOTAL_BYTES) &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_tx_packet_active && !b_tx_packet_loading &&
          !a_rx_ctx_valid && !a_rx_ctx_complete && !b_rx_ctx_valid && !b_rx_ctx_complete) begin
        if (max_a_busy_lanes < EXPECT_BUSY_PER_DIR ||
            max_b_busy_lanes < EXPECT_BUSY_PER_DIR ||
            max_total_busy_lanes < EXPECT_TOTAL_BUSY) begin
          $fatal(1,
            "Expected simultaneous full-duplex traffic, got max_a=%0d max_b=%0d max_total=%0d expect_a_b=%0d expect_total=%0d",
            max_a_busy_lanes, max_b_busy_lanes, max_total_busy_lanes,
            EXPECT_BUSY_PER_DIR, EXPECT_TOTAL_BUSY);
        end
        if (max_a_inflight_frags < EXPECT_INFLIGHT_PER_DIR ||
            max_b_inflight_frags < EXPECT_INFLIGHT_PER_DIR) begin
          $fatal(1,
            "Expected enough in-flight fragments per direction, got a=%0d b=%0d expect=%0d",
            max_a_inflight_frags, max_b_inflight_frags, EXPECT_INFLIGHT_PER_DIR);
        end

        completion_time_ns = $realtime;
        elapsed_us = (completion_time_ns - first_queue_time_ns) / 1000.0;
        ab_mbps = (b_rx_total_count * 8.0) / elapsed_us;
        ba_mbps = (a_rx_total_count * 8.0) / elapsed_us;
        aggregate_mbps = ab_mbps + ba_mbps;
`ifdef TB_FDX_4PLUS4
        $display("LOOPBACK_FULL_DUPLEX_4PLUS4_LANE_PASS packet_pairs=%0d ab_bytes=%0d ba_bytes=%0d elapsed_us=%0.3f ab_mbps=%0.6f ba_mbps=%0.6f aggregate_mbps=%0.6f max_a_busy=%0d max_b_busy=%0d max_total_busy=%0d max_a_inflight=%0d max_b_inflight=%0d",
          PACKET_COUNT, b_rx_total_count, a_rx_total_count, elapsed_us,
          ab_mbps, ba_mbps, aggregate_mbps, max_a_busy_lanes, max_b_busy_lanes,
          max_total_busy_lanes, max_a_inflight_frags, max_b_inflight_frags);
`elsif TB_FDX_1PLUS1
        $display("LOOPBACK_FULL_DUPLEX_1PLUS1_LANE_PASS packet_pairs=%0d ab_bytes=%0d ba_bytes=%0d elapsed_us=%0.3f ab_mbps=%0.6f ba_mbps=%0.6f aggregate_mbps=%0.6f max_a_busy=%0d max_b_busy=%0d max_total_busy=%0d max_a_inflight=%0d max_b_inflight=%0d",
          PACKET_COUNT, b_rx_total_count, a_rx_total_count, elapsed_us,
          ab_mbps, ba_mbps, aggregate_mbps, max_a_busy_lanes, max_b_busy_lanes,
          max_total_busy_lanes, max_a_inflight_frags, max_b_inflight_frags);
`else
        $display("LOOPBACK_FULL_DUPLEX_LANE_PARTITION_PASS packet_pairs=%0d ab_bytes=%0d ba_bytes=%0d max_a_busy=%0d max_b_busy=%0d max_total_busy=%0d max_a_inflight=%0d max_b_inflight=%0d",
          PACKET_COUNT, b_rx_total_count, a_rx_total_count, max_a_busy_lanes, max_b_busy_lanes,
          max_total_busy_lanes, max_a_inflight_frags, max_b_inflight_frags);
`endif
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for full-duplex lane-partition completion ab_sender_done=%0b ba_sender_done=%0b ab_sent=%0d ba_sent=%0d a_rx_pkt=%0d b_rx_pkt=%0d a_rx_total=%0d b_rx_total=%0d a_tx_done=%0d b_tx_done=%0d a_rx_done=%0d b_rx_done=%0d max_a_busy=%0d max_b_busy=%0d max_total=%0d",
      ab_sender_done, ba_sender_done, ab_sent_count, ba_sent_count,
      a_rx_packet_idx, b_rx_packet_idx, a_rx_total_count, b_rx_total_count,
      a_tx_done_count, b_tx_done_count, a_rx_done_count, b_rx_done_count,
      max_a_busy_lanes, max_b_busy_lanes, max_total_busy_lanes);
  end
endmodule
