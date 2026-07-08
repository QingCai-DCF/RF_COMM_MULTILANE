`timescale 1ns/1ps

module tb_ir_array_loopback_single_lane;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int MAX_FRAME_BYTES  = 14 + FRAGMENT_BYTES;
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
  logic a_rx_crc_error_any, a_rx_overrun_error_any;
  logic [LANE_COUNT-1:0] a_lane_tx_busy_dbg;
  logic [MAX_FRAGS-1:0] a_tx_frag_pending_dbg, a_tx_frag_inflight_dbg, a_tx_frag_acked_dbg, a_rx_recv_bitmap_dbg;

  logic b_tx_packet_active, b_tx_packet_loading, b_tx_done_pulse, b_tx_error_overflow, b_tx_error_retry_exhausted;
  logic b_rx_ctx_valid, b_rx_ctx_complete, b_rx_done_pulse, b_rx_header_error, b_rx_protocol_error;
  logic b_rx_crc_error_any, b_rx_overrun_error_any;
  logic [LANE_COUNT-1:0] b_lane_tx_busy_dbg;
  logic [MAX_FRAGS-1:0] b_tx_frag_pending_dbg, b_tx_frag_inflight_dbg, b_tx_frag_acked_dbg, b_rx_recv_bitmap_dbg;

  byte tx_payload [0:47];
  byte rx_payload [0:47];
  int  rx_count;

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];

  always @(posedge clk) begin
    if (rst_n && enable_b && dut_b.g_lane[0].u_lane.rx_frame_valid && dut_b.g_lane[0].u_lane.rx_frame_ready) begin
      $display("B_PHY_FRAME t=%0t len=%0d sof=%02x type=%02x frag=%0d count=%0d payload_len=%0d",
        $time,
        dut_b.g_lane[0].u_lane.rx_frame_len,
        dut_b.g_lane[0].u_lane.rx_frame_data[8*0 +: 8],
        dut_b.g_lane[0].u_lane.rx_frame_data[8*1 +: 8],
        dut_b.g_lane[0].u_lane.rx_frame_data[8*6 +: 8],
        dut_b.g_lane[0].u_lane.rx_frame_data[8*7 +: 8],
        dut_b.g_lane[0].u_lane.rx_frame_data[8*10 +: 8]);
    end

    if (rst_n && enable_b && $rose(b_rx_overrun_error_any)) begin
      $display("B_OVERRUN t=%0t rx_state=%0d byte_cnt=%0d pair_cnt=%0d silence=%0d tx_state=%0d tx_bit_ptr=%0d tx_stop_cnt=%0d",
        $time,
        dut_b.g_lane[0].u_lane.u_rx.state,
        dut_b.g_lane[0].u_lane.u_rx.byte_cnt,
        dut_b.g_lane[0].u_lane.u_rx.pair_cnt,
        dut_b.g_lane[0].u_lane.u_rx.silence_sym_cnt,
        dut_a.g_lane[0].u_lane.u_tx.state,
        dut_a.g_lane[0].u_lane.u_tx.bit_ptr,
        dut_a.g_lane[0].u_lane.u_tx.stop_cnt);
    end

    if (rst_n && enable_b && b_rx_done_pulse) begin
      $display("B_PACKET_DONE t=%0t", $time);
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
    .rx_crc_error_any(a_rx_crc_error_any), .rx_overrun_error_any(a_rx_overrun_error_any),
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
    .rx_crc_error_any(b_rx_crc_error_any), .rx_overrun_error_any(b_rx_overrun_error_any),
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
    rx_count = 0;

    for (int k = 0; k < 48; k++) begin
      tx_payload[k] = 8'h40 + k;
      rx_payload[k] = 8'h00;
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    for (int k = 0; k < 48; k++) begin
      @(posedge clk);
      a_tx_data  <= tx_payload[k];
      a_tx_valid <= 1'b1;
      a_tx_last  <= (k == 47);
      wait (a_tx_ready);
    end
    @(posedge clk);
    a_tx_valid <= 1'b0;
    a_tx_last  <= 1'b0;

    repeat (500000) begin
      @(posedge clk);
      if (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_crc_error_any || b_rx_overrun_error_any) begin
        $fatal(1,
          "Loopback error flags: tx_overflow=%0b tx_retry_exhausted=%0b rx_hdr=%0b rx_proto=%0b rx_crc=%0b rx_overrun=%0b rx_state=%0d rx_byte_cnt=%0d rx_pair_cnt=%0d rx_silence=%0d rx_chip=%0d rx_ticks=%0d rx_sym=%04b rx_sym_valid=%0b tx_state=%0d tx_bit_ptr=%0d tx_chip=%0d tx_busy=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_rx_header_error, b_rx_protocol_error, b_rx_crc_error_any, b_rx_overrun_error_any,
          dut_b.g_lane[0].u_lane.u_rx.state,
          dut_b.g_lane[0].u_lane.u_rx.byte_cnt,
          dut_b.g_lane[0].u_lane.u_rx.pair_cnt,
          dut_b.g_lane[0].u_lane.u_rx.silence_sym_cnt,
          dut_b.g_lane[0].u_lane.u_rx.chip_idx,
          dut_b.g_lane[0].u_lane.u_rx.ticks,
          dut_b.g_lane[0].u_lane.u_rx.sym_capture,
          dut_b.g_lane[0].u_lane.u_rx.sym_valid,
          dut_a.g_lane[0].u_lane.u_tx.state,
          dut_a.g_lane[0].u_lane.u_tx.bit_ptr,
          dut_a.g_lane[0].u_lane.u_tx.chip_idx,
          dut_a.g_lane[0].u_lane.u_tx.tx_busy);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (rx_count >= 48) begin
          $fatal(1, "Received more bytes than expected");
        end
        rx_payload[rx_count] = b_rx_data;
        rx_count = rx_count + 1;
        if (b_rx_last) begin
          if (rx_count != 48) begin
            $fatal(1, "RX length mismatch exp=48 got=%0d", rx_count);
          end
          for (int q = 0; q < 48; q++) begin
            if (rx_payload[q] !== tx_payload[q]) begin
              $fatal(1, "Mismatch at %0d exp=%02x got=%02x", q, tx_payload[q], rx_payload[q]);
            end
          end
          $display("LOOPBACK_SINGLE_LANE_PASS bytes=%0d", rx_count);
          $finish;
        end
      end
    end

    $fatal(1, "Timeout waiting for packet reception");
  end
endmodule
