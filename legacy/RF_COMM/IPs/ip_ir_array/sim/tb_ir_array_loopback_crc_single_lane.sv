`timescale 1ns/1ps

module tb_ir_array_loopback_crc_single_lane;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam logic [2:0] TX_STATE_DATA = 3'd3;

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

  logic corrupt_ab_symbol;
  logic corrupt_done;
  logic b_crc_error_q;
  logic [3:0] corrupt_chips;
  int   crc_error_count;
  int   a_tx_starts;
  logic a_busy_q;

  byte tx_payload [0:47];
  byte rx_payload [0:47];
  int  rx_count;
  bit  payload_ok;

  function automatic logic [3:0] rotate_onehot(input logic [3:0] chips);
    begin
      case (chips)
        4'b1000: rotate_onehot = 4'b0100;
        4'b0100: rotate_onehot = 4'b0010;
        4'b0010: rotate_onehot = 4'b0001;
        4'b0001: rotate_onehot = 4'b1000;
        default: rotate_onehot = 4'b0100;
      endcase
    end
  endfunction

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

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

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = corrupt_ab_symbol ? ~corrupt_chips[3 - dut_a.g_lane[0].u_lane.u_tx.chip_idx] : ~a_ir_tx_out[0];

  always @(posedge clk) begin
    if (!rst_n) begin
      corrupt_ab_symbol <= 1'b0;
      corrupt_done      <= 1'b0;
      corrupt_chips     <= 4'b0000;
      b_crc_error_q     <= 1'b0;
      crc_error_count   <= 0;
      a_tx_starts       <= 0;
      a_busy_q          <= 1'b0;
    end else begin
      b_crc_error_q <= b_rx_crc_error_any;
      a_busy_q      <= a_lane_tx_busy_dbg[0];

      if (!a_busy_q && a_lane_tx_busy_dbg[0]) begin
        a_tx_starts <= a_tx_starts + 1;
      end

      if (!b_crc_error_q && b_rx_crc_error_any) begin
        crc_error_count <= crc_error_count + 1;
        $display("B_PHY_CRC_ERROR t=%0t count=%0d", $time, crc_error_count + 1);
      end

      if (!corrupt_done && enable_a &&
          (dut_a.g_lane[0].u_lane.u_tx.state == TX_STATE_DATA) &&
          (dut_a.g_lane[0].u_lane.u_tx.chip_idx == 2'd0) &&
          (dut_a.g_lane[0].u_lane.u_tx.tick_cnt == '0)) begin
        corrupt_ab_symbol <= 1'b1;
        corrupt_done      <= 1'b1;
        corrupt_chips     <= rotate_onehot(dut_a.g_lane[0].u_lane.u_tx.curr_symbol_chips);
        $display("CORRUPT_AB_SYMBOL t=%0t orig=%04b repl=%04b",
          $time,
          dut_a.g_lane[0].u_lane.u_tx.curr_symbol_chips,
          rotate_onehot(dut_a.g_lane[0].u_lane.u_tx.curr_symbol_chips));
      end else if (corrupt_ab_symbol &&
          (dut_a.g_lane[0].u_lane.u_tx.state == TX_STATE_DATA) &&
          (dut_a.g_lane[0].u_lane.u_tx.chip_idx == 2'd3) &&
          (dut_a.g_lane[0].u_lane.u_tx.tick_cnt == CNT_CHIP_MAX)) begin
        corrupt_ab_symbol <= 1'b0;
        $display("CORRUPT_AB_RELEASE t=%0t", $time);
      end
    end
  end

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
  end

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
    payload_ok = 1'b0;

    for (int k = 0; k < 48; k++) begin
      tx_payload[k] = 8'hC0 + k;
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

    repeat (2000000) begin
      @(posedge clk);
      if (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_overrun_error_any) begin
        $fatal(1,
          "CRC loopback error flags: tx_overflow=%0b tx_retry_exhausted=%0b rx_hdr=%0b rx_proto=%0b rx_overflow=%0b rx_overrun=%0b rx_crc=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_overrun_error_any, b_rx_crc_error_any);
      end

      if (a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any) begin
        $fatal(1,
          "Unexpected A-side receive error: rx_hdr=%0b rx_proto=%0b rx_overflow=%0b rx_crc=%0b rx_overrun=%0b",
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (payload_ok) begin
          $fatal(1, "Payload was delivered more than once");
        end
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
          payload_ok = 1'b1;
          $display("B_PAYLOAD_OK t=%0t bytes=%0d", $time, rx_count);
        end
      end

      if (payload_ok && a_tx_done_pulse) begin
        if (!corrupt_done) $fatal(1, "CRC corruption was not injected");
        if (crc_error_count != 1) $fatal(1, "Expected one CRC error, got %0d", crc_error_count);
        if (a_tx_starts < 4) $fatal(1, "Expected at least one retransmission, A TX starts=%0d", a_tx_starts);
        $display("LOOPBACK_CRC_SINGLE_LANE_PASS bytes=%0d crc_errors=%0d a_tx_starts=%0d",
          rx_count, crc_error_count, a_tx_starts);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for CRC recovery");
  end
endmodule
