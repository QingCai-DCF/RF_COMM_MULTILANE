`timescale 1ns/1ps

module tb_ir_stream_fixed_4lane;
  localparam int LANE_COUNT       = 4;
  localparam int MAX_PACKET_BYTES = 128;
  localparam int FRAGMENT_BYTES   = 32;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int PKT_LEN          = 128;

  logic clk;
  logic rst_n;
  logic enable_a, enable_b;
  logic [7:0] a_tx_data, b_tx_data;
  logic a_tx_valid, b_tx_valid;
  logic a_tx_ready, b_tx_ready;
  logic a_tx_last, b_tx_last;
  logic [7:0] a_rx_data, b_rx_data;
  logic a_rx_valid, b_rx_valid;
  logic a_rx_ready, b_rx_ready;
  logic a_rx_last, b_rx_last;
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
  logic [LANE_COUNT-1:0] a_lane_tx_busy_q, b_lane_tx_busy_q;
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

  byte ab_payload [0:PKT_LEN-1];
  byte ba_payload [0:PKT_LEN-1];
  int a_rx_count;
  int b_rx_count;
  int a_tx_done_count;
  int b_tx_done_count;
  int a_lane_starts [0:LANE_COUNT-1];
  int b_lane_starts [0:LANE_COUNT-1];
  bit ab_ok;
  bit ba_ok;

  always #7.8125 clk = ~clk;

  genvar li;
  generate
    for (li = 0; li < LANE_COUNT; li = li + 1) begin : g_fixed_optical
      assign a_ir_rx_in[li] = ~b_ir_tx_out[li];
      assign b_ir_rx_in[li] = ~a_ir_tx_out[li];
    end
  endgenerate

  task automatic send_a_packet;
    begin
      for (int k = 0; k < PKT_LEN; k++) begin
        @(negedge clk);
        a_tx_data  = ab_payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == PKT_LEN - 1);
        do @(posedge clk); while (!a_tx_ready);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      $display("STREAM_4LANE_A_TO_B_QUEUED t=%0t len=%0d", $time, PKT_LEN);
    end
  endtask

  task automatic send_b_packet;
    begin
      for (int k = 0; k < PKT_LEN; k++) begin
        @(negedge clk);
        b_tx_data  = ba_payload[k];
        b_tx_valid = 1'b1;
        b_tx_last  = (k == PKT_LEN - 1);
        do @(posedge clk); while (!b_tx_ready);
      end
      @(negedge clk);
      b_tx_valid = 1'b0;
      b_tx_last  = 1'b0;
      $display("STREAM_4LANE_B_TO_A_QUEUED t=%0t len=%0d", $time, PKT_LEN);
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
      a_rx_count <= 0;
      b_rx_count <= 0;
      a_tx_done_count <= 0;
      b_tx_done_count <= 0;
      a_lane_tx_busy_q <= '0;
      b_lane_tx_busy_q <= '0;
      ab_ok <= 1'b0;
      ba_ok <= 1'b0;
      for (int l = 0; l < LANE_COUNT; l++) begin
        a_lane_starts[l] <= 0;
        b_lane_starts[l] <= 0;
      end
    end else begin
      a_lane_tx_busy_q <= a_lane_tx_busy;
      b_lane_tx_busy_q <= b_lane_tx_busy;
      for (int l = 0; l < LANE_COUNT; l++) begin
        if (!a_lane_tx_busy_q[l] && a_lane_tx_busy[l]) begin
          a_lane_starts[l] <= a_lane_starts[l] + 1;
          $display("STREAM_A_LANE_START t=%0t lane=%0d count=%0d", $time, l, a_lane_starts[l] + 1);
        end
        if (!b_lane_tx_busy_q[l] && b_lane_tx_busy[l]) begin
          b_lane_starts[l] <= b_lane_starts[l] + 1;
          $display("STREAM_B_LANE_START t=%0t lane=%0d count=%0d", $time, l, b_lane_starts[l] + 1);
        end
      end

      if (a_tx_done) a_tx_done_count <= a_tx_done_count + 1;
      if (b_tx_done) b_tx_done_count <= b_tx_done_count + 1;

      if (a_tx_overflow || b_tx_overflow || a_tx_exhaust || b_tx_exhaust ||
          a_rx_header_error || b_rx_header_error ||
          a_rx_protocol_error || b_rx_protocol_error) begin
        $fatal(1, "Unexpected 4lane stream error t=%0t dbg_a=%08x dbg_b=%08x", $time, debug_a, debug_b);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (ab_ok) $fatal(1, "A-to-B 4lane delivered more than once");
        if (b_rx_count >= PKT_LEN) $fatal(1, "A-to-B 4lane too many bytes");
        if (b_rx_data !== ab_payload[b_rx_count]) begin
          $fatal(1, "A-to-B 4lane byte mismatch idx=%0d exp=%02x got=%02x",
                 b_rx_count, ab_payload[b_rx_count], b_rx_data);
        end
        b_rx_count <= b_rx_count + 1;
        if (b_rx_last) begin
          if ((b_rx_count + 1) != PKT_LEN) $fatal(1, "A-to-B 4lane length mismatch");
          ab_ok <= 1'b1;
          $display("STREAM_4LANE_A_TO_B_OK t=%0t bytes=%0d", $time, b_rx_count + 1);
        end
      end

      if (a_rx_valid && a_rx_ready) begin
        if (ba_ok) $fatal(1, "B-to-A 4lane delivered more than once");
        if (a_rx_count >= PKT_LEN) $fatal(1, "B-to-A 4lane too many bytes");
        if (a_rx_data !== ba_payload[a_rx_count]) begin
          $fatal(1, "B-to-A 4lane byte mismatch idx=%0d exp=%02x got=%02x",
                 a_rx_count, ba_payload[a_rx_count], a_rx_data);
        end
        a_rx_count <= a_rx_count + 1;
        if (a_rx_last) begin
          if ((a_rx_count + 1) != PKT_LEN) $fatal(1, "B-to-A 4lane length mismatch");
          ba_ok <= 1'b1;
          $display("STREAM_4LANE_B_TO_A_OK t=%0t bytes=%0d", $time, a_rx_count + 1);
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
    .FRAG_TIMEOUT_CYCLES(120000),
    .BACKOFF_SLOT_CYCLES(1024)
  ) dut_a (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_a), .session_id(16'h6444),
    .lane_enable_mask(4'hf), .rx_lane_enable_mask(4'hf),
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
    .FRAG_TIMEOUT_CYCLES(120000),
    .BACKOFF_SLOT_CYCLES(1024)
  ) dut_b (
    .clk_phy(clk), .rst_n(rst_n), .enable(enable_b), .session_id(16'h6444),
    .lane_enable_mask(4'hf), .rx_lane_enable_mask(4'hf),
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
    b_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    b_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_last = 1'b0;

    for (int k = 0; k < PKT_LEN; k++) begin
      ab_payload[k] = byte'((k * 3 + 8'h31) & 8'hff);
      ba_payload[k] = byte'((k * 5 + 8'h92) & 8'hff);
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (20) @(posedge clk);

    send_a_packet();
    wait (ab_ok && a_tx_done_count == 1);
    repeat (2000) @(posedge clk);
    send_b_packet();

    repeat (4000000) begin
      @(posedge clk);
      if (ab_ok && ba_ok && (a_tx_done_count == 1) && (b_tx_done_count == 1)) begin
        bit all_a_lanes_used;
        bit all_b_lanes_used;
        all_a_lanes_used = 1'b1;
        all_b_lanes_used = 1'b1;
        for (int l = 0; l < LANE_COUNT; l++) begin
          if (a_lane_starts[l] == 0) all_a_lanes_used = 1'b0;
          if (b_lane_starts[l] == 0) all_b_lanes_used = 1'b0;
        end
        if (all_a_lanes_used && all_b_lanes_used) begin
          $display("IR_STREAM_FIXED_4LANE_PASS bytes_each_direction=%0d", PKT_LEN);
          $finish;
        end
      end
    end

    $fatal(1, "Timeout waiting for fixed 4lane pass ab=%0d ba=%0d a_done=%0d b_done=%0d starts_a=%0d/%0d/%0d/%0d starts_b=%0d/%0d/%0d/%0d dbg_a=%08x dbg_b=%08x",
           ab_ok, ba_ok, a_tx_done_count, b_tx_done_count,
           a_lane_starts[0], a_lane_starts[1], a_lane_starts[2], a_lane_starts[3],
           b_lane_starts[0], b_lane_starts[1], b_lane_starts[2], b_lane_starts[3],
           debug_a, debug_b);
  end
endmodule
