`timescale 1ns/1ps

module tb_ir_array_loopback_long_packet_latency;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 256;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam time MAX_RX_LATENCY_NS   = 10_000_000; // 10 ms with this testbench's 1 ns time unit.
  localparam time MAX_DONE_LATENCY_NS = 12_000_000; // Includes final ACK return.

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

  byte tx_payload [0:MAX_PACKET_BYTES-1];
  byte rx_payload [0:MAX_PACKET_BYTES-1];
  int  rx_count;
  int  data_frame_count;
  logic [MAX_FRAGS-1:0] rx_frag_seen;
  time tx_start_time;
  time rx_last_time;
  time tx_done_time;
  bit  saw_rx_last;
  bit  saw_tx_done;
  bit  payload_sent;

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];

  task automatic wait_tx_ready(input int byte_idx);
    int wait_cycles;
    begin
      wait_cycles = 0;
      while (!a_tx_ready) begin
        @(posedge clk);
        wait_cycles++;
        if (wait_cycles > 2000) begin
          $fatal(1, "Timeout waiting for TX ready byte=%0d", byte_idx);
        end
      end
    end
  endtask

  always @(posedge clk) begin
    if (!rst_n) begin
      data_frame_count <= 0;
      rx_frag_seen     <= '0;
      rx_count         <= 0;
      saw_rx_last      <= 1'b0;
      saw_tx_done      <= 1'b0;
      rx_last_time     <= 0;
      tx_done_time     <= 0;
    end else begin
      if (enable_b && dut_b.g_lane[0].u_lane.rx_frame_valid && dut_b.g_lane[0].u_lane.rx_frame_ready &&
          (dut_b.g_lane[0].u_lane.rx_frame_data[8*0 +: 8] == 8'hA5) &&
          (dut_b.g_lane[0].u_lane.rx_frame_data[8*1 +: 4] == 4'h1)) begin
        int frag_idx;
        int frag_count;
        int payload_len;
        frag_idx    = dut_b.g_lane[0].u_lane.rx_frame_data[8*6 +: 8];
        frag_count  = dut_b.g_lane[0].u_lane.rx_frame_data[8*7 +: 8];
        payload_len = dut_b.g_lane[0].u_lane.rx_frame_data[8*10 +: 8];
        if (frag_count != MAX_FRAGS || payload_len != FRAGMENT_BYTES) begin
          $fatal(1, "Unexpected long-packet frame metadata frag=%0d frag_count=%0d payload_len=%0d",
            frag_idx, frag_count, payload_len);
        end
        if (frag_idx < 0 || frag_idx >= MAX_FRAGS) begin
          $fatal(1, "Unexpected long-packet frag_idx=%0d", frag_idx);
        end
        if (rx_frag_seen[frag_idx]) begin
          $fatal(1, "Unexpected duplicate long-packet fragment frag=%0d", frag_idx);
        end
        rx_frag_seen[frag_idx] <= 1'b1;
        data_frame_count <= data_frame_count + 1;
      end

      if (b_rx_valid && b_rx_ready) begin
        if (rx_count >= MAX_PACKET_BYTES) begin
          $fatal(1, "Received more than 256 bytes data=%02x", b_rx_data);
        end
        rx_payload[rx_count] = b_rx_data;
        if (b_rx_data !== tx_payload[rx_count]) begin
          $fatal(1, "Long-packet byte mismatch idx=%0d exp=%02x got=%02x",
            rx_count, tx_payload[rx_count], b_rx_data);
        end
        rx_count = rx_count + 1;
        if (b_rx_last) begin
          rx_last_time <= $time;
          saw_rx_last  <= 1'b1;
          if (rx_count != MAX_PACKET_BYTES) begin
            $fatal(1, "Long-packet RX length mismatch exp=256 got=%0d", rx_count);
          end
        end
      end

      if (a_tx_done_pulse) begin
        tx_done_time <= $time;
        saw_tx_done  <= 1'b1;
      end

      if (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_tx_error_overflow || b_tx_error_retry_exhausted ||
          b_rx_header_error || b_rx_protocol_error || b_rx_crc_error_any || b_rx_overrun_error_any ||
          a_rx_header_error || a_rx_protocol_error || a_rx_crc_error_any || a_rx_overrun_error_any) begin
        $fatal(1,
          "Long-packet error flags: a_tx_overflow=%0b a_retry=%0b b_tx_overflow=%0b b_retry=%0b b_hdr=%0b b_proto=%0b b_crc=%0b b_overrun=%0b a_hdr=%0b a_proto=%0b a_crc=%0b a_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_tx_error_overflow, b_tx_error_retry_exhausted,
          b_rx_header_error, b_rx_protocol_error, b_rx_crc_error_any, b_rx_overrun_error_any,
          a_rx_header_error, a_rx_protocol_error, a_rx_crc_error_any, a_rx_overrun_error_any);
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
    session_id_a = 16'h2561;
    session_id_b = 16'h2561;
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
    payload_sent = 1'b0;
    tx_start_time = 0;

    for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
      tx_payload[k] = byte'(8'h20 + k);
      rx_payload[k] = 8'h00;
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    tx_start_time = $time;
    for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
      @(negedge clk);
      a_tx_data  = tx_payload[k];
      a_tx_valid = 1'b1;
      a_tx_last  = (k == MAX_PACKET_BYTES - 1);
      wait_tx_ready(k);
    end
    @(negedge clk);
    a_tx_valid = 1'b0;
    a_tx_last  = 1'b0;
    payload_sent = 1'b1;
  end

  initial begin
    time rx_latency_ns;
    time done_latency_ns;
    repeat (3000000) begin
      @(posedge clk);
      if (payload_sent && saw_rx_last && saw_tx_done &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete) begin
        rx_latency_ns   = rx_last_time - tx_start_time;
        done_latency_ns = tx_done_time - tx_start_time;
        if (data_frame_count != MAX_FRAGS || rx_frag_seen != '1) begin
          $fatal(1, "Long-packet fragment coverage mismatch frames=%0d seen=%04h expected=%0d",
            data_frame_count, rx_frag_seen, MAX_FRAGS);
        end
        if (rx_latency_ns > MAX_RX_LATENCY_NS || done_latency_ns > MAX_DONE_LATENCY_NS) begin
          $fatal(1, "Long-packet latency exceeded budget rx_ns=%0d done_ns=%0d max_rx_ns=%0d max_done_ns=%0d",
            rx_latency_ns, done_latency_ns, MAX_RX_LATENCY_NS, MAX_DONE_LATENCY_NS);
        end
        $display(
          "LOOPBACK_SINGLE_LANE_256B_LATENCY_PASS bytes=%0d frags=%0d rx_latency_ns=%0d done_latency_ns=%0d rx_latency_us=%0d done_latency_us=%0d",
          MAX_PACKET_BYTES, data_frame_count, rx_latency_ns, done_latency_ns,
          rx_latency_ns / 1000, done_latency_ns / 1000);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for long-packet completion sent=%0b rx_last=%0b tx_done=%0b rx_count=%0d frames=%0d active=%0b loading=%0b b_ctx=%0b b_complete=%0b",
      payload_sent, saw_rx_last, saw_tx_done, rx_count, data_frame_count,
      a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete);
  end
endmodule
