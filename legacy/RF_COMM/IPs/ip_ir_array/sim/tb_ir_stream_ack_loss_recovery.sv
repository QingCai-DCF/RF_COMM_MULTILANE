`timescale 1ns/1ps

module tb_ir_stream_ack_loss_recovery;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 32;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int PKT_LEN          = 64;

  logic clk;
  logic rst_n;
  logic enable_a, enable_b;
  logic [7:0] a_tx_data;
  logic a_tx_valid;
  logic a_tx_ready;
  logic a_tx_last;
  logic [7:0] b_rx_data;
  logic b_rx_valid;
  logic b_rx_ready;
  logic b_rx_last;
  logic [7:0] b_tx_data;
  logic b_tx_valid;
  logic b_tx_ready;
  logic b_tx_last;
  logic [7:0] a_rx_data;
  logic a_rx_valid;
  logic a_rx_ready;
  logic a_rx_last;
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
  logic unused_rx_overflow_a, unused_rx_overflow_b;
  logic unused_rx_crc_any_a, unused_rx_crc_any_b;
  logic unused_rx_overrun_a, unused_rx_overrun_b;
  logic [31:0] debug_a, debug_b;

  logic drop_b_to_a;
  logic drop_armed;
  logic drop_seen_busy;
  int dropped_ack_count;
  int a_tx_done_count;
  int b_rx_done_count;
  int b_rx_count;
  bit payload_ok;
  byte payload [0:PKT_LEN-1];

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = drop_b_to_a ? 1'b1 : ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];

  task automatic send_a_packet;
    begin
      for (int k = 0; k < PKT_LEN; k++) begin
        @(negedge clk);
        a_tx_data  = payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == PKT_LEN - 1);
        do @(posedge clk); while (!a_tx_ready);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      $display("STREAM_ACKLOSS_A_PACKET_QUEUED t=%0t len=%0d", $time, PKT_LEN);
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
      drop_b_to_a <= 1'b0;
      drop_armed <= 1'b0;
      drop_seen_busy <= 1'b0;
      dropped_ack_count <= 0;
      a_tx_done_count <= 0;
      b_rx_done_count <= 0;
      b_rx_count <= 0;
      payload_ok <= 1'b0;
    end else begin
      if (b_rx_done && dropped_ack_count == 0) begin
        drop_b_to_a <= 1'b1;
        drop_armed <= 1'b1;
        dropped_ack_count <= 1;
        $display("STREAM_ACKLOSS_DROP_NEXT_B_ACK t=%0t", $time);
      end
      if (drop_armed && b_lane_tx_busy[0]) begin
        drop_seen_busy <= 1'b1;
      end
      if (drop_armed && drop_seen_busy && !b_lane_tx_busy[0]) begin
        drop_b_to_a <= 1'b0;
        drop_armed <= 1'b0;
        drop_seen_busy <= 1'b0;
        $display("STREAM_ACKLOSS_RELEASE_CHANNEL t=%0t", $time);
      end

      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;
      if (b_rx_done) b_rx_done_count <= b_rx_done_count + 1;

      if (a_tx_overflow || b_tx_overflow || a_tx_exhaust || b_tx_exhaust ||
          b_rx_header_error || b_rx_protocol_error) begin
        $fatal(1, "Unexpected ack-loss test hard error t=%0t dbg_a=%08x dbg_b=%08x", $time, debug_a, debug_b);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (payload_ok) $fatal(1, "Payload delivered more than once after ACK loss");
        if (b_rx_count >= PKT_LEN) $fatal(1, "Too many received bytes after ACK loss");
        if (b_rx_data !== payload[b_rx_count]) begin
          $fatal(1, "ACK-loss byte mismatch idx=%0d exp=%02x got=%02x",
                 b_rx_count, payload[b_rx_count], b_rx_data);
        end
        b_rx_count <= b_rx_count + 1;
        if (b_rx_last) begin
          if ((b_rx_count + 1) != PKT_LEN) $fatal(1, "ACK-loss length mismatch");
          payload_ok <= 1'b1;
          $display("STREAM_ACKLOSS_PAYLOAD_OK t=%0t bytes=%0d", $time, b_rx_count + 1);
        end
      end
    end
  end

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(0),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .CNT_PREAMBLE(16),
    .FRAG_TIMEOUT_CYCLES(30000),
    .BACKOFF_SLOT_CYCLES(1024)
  ) dut_a (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_a), .session_id(16'h7a0c),
    .lane_enable_mask('1), .rx_lane_enable_mask('1),
    .s_axis_tx_tdata(a_tx_data), .s_axis_tx_tvalid(a_tx_valid), .s_axis_tx_tready(a_tx_ready), .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data), .m_axis_rx_tvalid(a_rx_valid), .m_axis_rx_tready(a_rx_ready), .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out), .ir_rx_in(a_ir_rx_in), .ir_sd(a_ir_sd), .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(), .tx_packet_loading(), .tx_done_pulse(a_tx_done),
    .tx_error_overflow(a_tx_overflow), .tx_error_retry_exhausted(a_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_a), .rx_ctx_complete(unused_rx_ctx_complete_a), .rx_done_pulse(a_rx_done),
    .rx_header_error(a_rx_header_error), .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(unused_rx_overflow_a), .rx_crc_error_any(unused_rx_crc_any_a), .rx_overrun_error_any(unused_rx_overrun_a),
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
    .CNT_PREAMBLE(16),
    .FRAG_TIMEOUT_CYCLES(30000),
    .BACKOFF_SLOT_CYCLES(1024)
  ) dut_b (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_b), .session_id(16'h7a0c),
    .lane_enable_mask('1), .rx_lane_enable_mask('1),
    .s_axis_tx_tdata(b_tx_data), .s_axis_tx_tvalid(b_tx_valid), .s_axis_tx_tready(b_tx_ready), .s_axis_tx_tlast(b_tx_last),
    .m_axis_rx_tdata(b_rx_data), .m_axis_rx_tvalid(b_rx_valid), .m_axis_rx_tready(b_rx_ready), .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out), .ir_rx_in(b_ir_rx_in), .ir_sd(b_ir_sd), .ir_mode_out(b_ir_mode_out),
    .tx_packet_active(), .tx_packet_loading(), .tx_done_pulse(b_tx_done),
    .tx_error_overflow(b_tx_overflow), .tx_error_retry_exhausted(b_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_b), .rx_ctx_complete(unused_rx_ctx_complete_b), .rx_done_pulse(b_rx_done),
    .rx_header_error(b_rx_header_error), .rx_protocol_error(b_rx_protocol_error),
    .rx_frame_overflow_any(unused_rx_overflow_b), .rx_crc_error_any(unused_rx_crc_any_b), .rx_overrun_error_any(unused_rx_overrun_b),
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
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;

    for (int k = 0; k < PKT_LEN; k++) payload[k] = byte'((k * 13 + 8'h17) & 8'hff);

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (20) @(posedge clk);

    send_a_packet();

    repeat (3000000) begin
      @(posedge clk);
      if (payload_ok && (a_tx_done_count == 1) && (b_rx_done_count == 1) && dropped_ack_count == 1) begin
        $display("IR_STREAM_ACK_LOSS_RECOVERY_PASS bytes=%0d dropped_ack=%0d", PKT_LEN, dropped_ack_count);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for ACK-loss recovery payload_ok=%0d a_done=%0d b_rx_done=%0d dropped=%0d dbg_a=%08x dbg_b=%08x",
           payload_ok, a_tx_done_count, b_rx_done_count, dropped_ack_count, debug_a, debug_b);
  end
endmodule
