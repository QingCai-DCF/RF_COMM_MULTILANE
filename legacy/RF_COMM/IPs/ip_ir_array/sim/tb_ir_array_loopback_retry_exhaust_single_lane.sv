`timescale 1ns/1ps

module tb_ir_array_loopback_retry_exhaust_single_lane;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int MAX_RETRY        = 4;
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

  logic a_busy_q;
  int   a_tx_starts;
  int   b_rx_byte_count;
  bit   saw_retry_exhausted;

  byte tx_payload [0:15];

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  assign b_ir_rx_in[0] = 1'b1;          // Permanent A-to-B optical outage.
  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];

  always @(posedge clk) begin
    if (!rst_n) begin
      a_busy_q            <= 1'b0;
      a_tx_starts         <= 0;
      b_rx_byte_count     <= 0;
      saw_retry_exhausted <= 1'b0;
    end else begin
      a_busy_q <= a_lane_tx_busy_dbg[0];
      if (!a_busy_q && a_lane_tx_busy_dbg[0]) begin
        a_tx_starts <= a_tx_starts + 1;
        $display("A_TX_START t=%0t count=%0d", $time, a_tx_starts + 1);
      end

      if (b_rx_valid && b_rx_ready) begin
        b_rx_byte_count <= b_rx_byte_count + 1;
        $fatal(1, "Permanent outage delivered unexpected byte count=%0d data=%02x", b_rx_byte_count + 1, b_rx_data);
      end

      if (a_tx_done_pulse) begin
        $fatal(1, "TX done asserted during permanent outage");
      end

      if (a_tx_error_retry_exhausted) begin
        saw_retry_exhausted <= 1'b1;
        if (a_tx_starts != (MAX_RETRY + 1)) begin
          $fatal(1, "Expected %0d TX starts before retry exhaustion, got %0d", MAX_RETRY + 1, a_tx_starts);
        end
        if (b_rx_byte_count != 0) begin
          $fatal(1, "Permanent outage delivered %0d bytes before retry exhaustion", b_rx_byte_count);
        end
        $display("LOOPBACK_RETRY_EXHAUST_SINGLE_LANE_PASS tx_starts=%0d b_rx_bytes=%0d",
          a_tx_starts, b_rx_byte_count);
        $finish;
      end
    end
  end

  ir_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_RETRY(MAX_RETRY),
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
    .MAX_RETRY(MAX_RETRY),
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
    session_id_a = 16'h1234;
    session_id_b = 16'h1234;
    lane_mask_a = '1;
    lane_mask_b = '1;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    a_rx_ready = 1'b1;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    b_rx_ready = 1'b1;

    for (int k = 0; k < 16; k++) begin
      tx_payload[k] = 8'h20 + k;
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    for (int k = 0; k < 16; k++) begin
      @(posedge clk);
      a_tx_data  <= tx_payload[k];
      a_tx_valid <= 1'b1;
      a_tx_last  <= (k == 15);
      wait (a_tx_ready);
    end
    @(posedge clk);
    a_tx_valid <= 1'b0;
    a_tx_last  <= 1'b0;

    repeat (1200000) begin
      @(posedge clk);
      if (a_tx_error_overflow || b_tx_error_overflow || b_tx_error_retry_exhausted ||
          a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any) begin
        $fatal(1,
          "Unexpected side error before retry exhaustion: a_overflow=%0b b_overflow=%0b b_retry=%0b a_rx=%0b%0b%0b%0b%0b b_rx=%0b%0b%0b%0b%0b",
          a_tx_error_overflow, b_tx_error_overflow, b_tx_error_retry_exhausted,
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
      end
    end

    if (!saw_retry_exhausted) begin
      $fatal(1, "Timeout waiting for retry exhaustion");
    end
  end
endmodule
