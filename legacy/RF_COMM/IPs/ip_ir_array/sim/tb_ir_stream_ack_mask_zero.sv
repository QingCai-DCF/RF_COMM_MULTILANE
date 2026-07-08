`timescale 1ns/1ps

module tb_ir_stream_ack_mask_zero;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 32;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int AB_LEN           = 24;

  logic clk;
  logic rst_n;
  logic enable_a, enable_b;
  logic [7:0] a_tx_data;
  logic a_tx_valid;
  logic a_tx_ready;
  logic a_tx_last;
  logic [7:0] a_rx_data, b_rx_data;
  logic a_rx_valid, b_rx_valid;
  logic a_rx_ready, b_rx_ready;
  logic a_rx_last, b_rx_last;
  logic [LANE_COUNT-1:0] a_ir_tx_out, b_ir_tx_out;
  logic [LANE_COUNT-1:0] a_ir_rx_in, b_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd, b_ir_sd;
  logic [LANE_COUNT-1:0] a_ir_mode_out, b_ir_mode_out;

  logic a_tx_done;
  logic a_tx_overflow, b_tx_overflow;
  logic a_tx_exhaust, b_tx_exhaust;
  logic a_rx_done, b_rx_done;
  logic a_rx_header_error, b_rx_header_error;
  logic a_rx_protocol_error, b_rx_protocol_error;
  logic [LANE_COUNT-1:0] a_lane_tx_busy, b_lane_tx_busy;
  logic [LANE_COUNT-1:0] a_lane_tx_load_pulse, b_lane_tx_load_pulse;
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

  byte ab_payload [0:AB_LEN-1];
  int b_rx_count;
  int b_tx_load_count;
  int post_receive_cycles;
  bit ab_ok;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];

  task automatic send_a_packet;
    begin
      for (int k = 0; k < AB_LEN; k++) begin
        @(negedge clk);
        a_tx_data  = ab_payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == AB_LEN - 1);
        do @(posedge clk); while (!a_tx_ready);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      $display("STREAM_ACK_MASK_ZERO_A_TO_B_QUEUED t=%0t len=%0d", $time, AB_LEN);
    end
  endtask

  always @(posedge clk) begin
    if (!rst_n) begin
      b_rx_count <= 0;
      b_tx_load_count <= 0;
      post_receive_cycles <= 0;
      ab_ok <= 1'b0;
    end else begin
      if (a_tx_overflow || b_tx_overflow || b_tx_exhaust ||
          a_rx_header_error || b_rx_header_error ||
          a_rx_protocol_error || b_rx_protocol_error) begin
        $fatal(1, "Unexpected ACK-mask-zero error t=%0t dbg_a=%08x dbg_b=%08x a_exhaust=%0b",
               $time, debug_a, debug_b, a_tx_exhaust);
      end

      if (enable_b && (b_lane_tx_busy[0] || b_lane_tx_load_pulse[0])) begin
        $fatal(1, "B transmitted with ACK_LANE_MASK=0 t=%0t busy=%0b load=%0b dbg_b=%08x",
               $time, b_lane_tx_busy[0], b_lane_tx_load_pulse[0], debug_b);
      end

      if (b_lane_tx_load_pulse[0]) begin
        b_tx_load_count <= b_tx_load_count + 1;
      end

      if (b_rx_valid && b_rx_ready) begin
        if (ab_ok) $fatal(1, "A-to-B delivered more than once with ACK disabled");
        if (b_rx_count >= AB_LEN) $fatal(1, "A-to-B too many bytes");
        if (b_rx_data !== ab_payload[b_rx_count]) begin
          $fatal(1, "A-to-B byte mismatch idx=%0d exp=%02x got=%02x",
                 b_rx_count, ab_payload[b_rx_count], b_rx_data);
        end
        b_rx_count <= b_rx_count + 1;
        if (b_rx_last) begin
          if ((b_rx_count + 1) != AB_LEN) $fatal(1, "A-to-B length mismatch");
          ab_ok <= 1'b1;
          $display("STREAM_ACK_MASK_ZERO_A_TO_B_OK t=%0t bytes=%0d", $time, b_rx_count + 1);
        end
      end

      if (ab_ok) begin
        post_receive_cycles <= post_receive_cycles + 1;
      end
    end
  end

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(0),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_RETRY(1),
    .CNT_PREAMBLE(16),
    .FRAG_TIMEOUT_CYCLES(20000),
    .BACKOFF_SLOT_CYCLES(1024)
  ) dut_a (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_a), .session_id(16'h51a5),
    .lane_enable_mask('1), .rx_lane_enable_mask('1),
    .s_axis_tx_tdata(a_tx_data), .s_axis_tx_tvalid(a_tx_valid), .s_axis_tx_tready(a_tx_ready), .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data), .m_axis_rx_tvalid(a_rx_valid), .m_axis_rx_tready(a_rx_ready), .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out), .ir_rx_in(a_ir_rx_in), .ir_sd(a_ir_sd), .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(), .tx_packet_loading(), .tx_done_pulse(a_tx_done),
    .tx_error_overflow(a_tx_overflow), .tx_error_retry_exhausted(a_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_a), .rx_ctx_complete(unused_rx_ctx_complete_a), .rx_done_pulse(a_rx_done),
    .rx_header_error(a_rx_header_error), .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(unused_rx_overflow_a), .rx_crc_error_any(unused_rx_crc_any_a), .rx_overrun_error_any(unused_rx_overrun_a),
    .lane_tx_busy_dbg(a_lane_tx_busy), .lane_tx_load_pulse_dbg(a_lane_tx_load_pulse),
    .lane_rx_frame_pulse_dbg(unused_rx_pulse_a), .lane_rx_crc_error_dbg(unused_crc_a), .lane_rx_error_dbg(unused_err_a),
    .tx_frag_pending_dbg(unused_tx_pending_a), .tx_frag_inflight_dbg(unused_tx_inflight_a), .tx_frag_acked_dbg(unused_tx_acked_a),
    .rx_recv_bitmap_dbg(unused_rx_bitmap_a), .debug_status(debug_a)
  );

  ir_stream_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .NODE_ID(1),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_RETRY(1),
    .CNT_PREAMBLE(16),
    .ACK_LANE_MASK(1'b0),
    .FRAG_TIMEOUT_CYCLES(20000),
    .BACKOFF_SLOT_CYCLES(1024)
  ) dut_b (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_b), .session_id(16'h51a5),
    .lane_enable_mask('1), .rx_lane_enable_mask('1),
    .s_axis_tx_tdata(8'h00), .s_axis_tx_tvalid(1'b0), .s_axis_tx_tready(), .s_axis_tx_tlast(1'b0),
    .m_axis_rx_tdata(b_rx_data), .m_axis_rx_tvalid(b_rx_valid), .m_axis_rx_tready(b_rx_ready), .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out), .ir_rx_in(b_ir_rx_in), .ir_sd(b_ir_sd), .ir_mode_out(b_ir_mode_out),
    .tx_packet_active(), .tx_packet_loading(), .tx_done_pulse(),
    .tx_error_overflow(b_tx_overflow), .tx_error_retry_exhausted(b_tx_exhaust),
    .rx_ctx_valid(unused_rx_ctx_valid_b), .rx_ctx_complete(unused_rx_ctx_complete_b), .rx_done_pulse(b_rx_done),
    .rx_header_error(b_rx_header_error), .rx_protocol_error(b_rx_protocol_error),
    .rx_frame_overflow_any(unused_rx_overflow_b), .rx_crc_error_any(unused_rx_crc_any_b), .rx_overrun_error_any(unused_rx_overrun_b),
    .lane_tx_busy_dbg(b_lane_tx_busy), .lane_tx_load_pulse_dbg(b_lane_tx_load_pulse),
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
    a_rx_ready = 1'b1;
    b_rx_ready = 1'b1;

    for (int k = 0; k < AB_LEN; k++) ab_payload[k] = byte'((k * 7 + 8'h23) & 8'hff);

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (20) @(posedge clk);

    send_a_packet();

    repeat (1500000) begin
      @(posedge clk);
      if (ab_ok && post_receive_cycles > 20000) begin
        if (b_tx_load_count != 0) begin
          $fatal(1, "B ACK/TX load count nonzero with ACK disabled: %0d", b_tx_load_count);
        end
        $display("IR_STREAM_ACK_MASK_ZERO_PASS bytes=%0d b_tx_loads=%0d a_retry_exhausted=%0b",
                 AB_LEN, b_tx_load_count, a_tx_exhaust);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for ACK-mask-zero pass ab_ok=%0d b_rx_count=%0d b_tx_loads=%0d dbg_a=%08x dbg_b=%08x",
           ab_ok, b_rx_count, b_tx_load_count, debug_a, debug_b);
  end
endmodule
