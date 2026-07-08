`timescale 1ns/1ps

module tb_ir_array_loopback_bidirectional_single_lane;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;
  localparam int AB_LEN           = 48;
  localparam int BA_LEN           = 37;

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

  byte ab_payload [0:MAX_PACKET_BYTES-1];
  byte ba_payload [0:MAX_PACKET_BYTES-1];
  int  a_rx_count;
  int  b_rx_count;
  int  a_tx_done_count;
  int  b_tx_done_count;
  int  a_rx_done_count;
  int  b_rx_done_count;
  int  ready_cycle;
  bit  ab_payload_ok;
  bit  ba_payload_ok;
  bit  ab_sender_done;
  bit  ba_sender_done;

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];
  assign b_ir_rx_in[0] = ~a_ir_tx_out[0];

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

  task automatic send_a_to_b;
    begin
      for (int k = 0; k < AB_LEN; k++) begin
        @(negedge clk);
        a_tx_data  = ab_payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == AB_LEN - 1);
        wait_a_tx_ready(k);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      ab_sender_done = 1'b1;
      $display("A_TO_B_PACKET_QUEUED t=%0t len=%0d", $time, AB_LEN);
    end
  endtask

  task automatic send_b_to_a;
    begin
      for (int k = 0; k < BA_LEN; k++) begin
        @(negedge clk);
        b_tx_data  = ba_payload[k];
        b_tx_valid = 1'b1;
        b_tx_last  = (k == BA_LEN - 1);
        wait_b_tx_ready(k);
      end
      @(negedge clk);
      b_tx_valid = 1'b0;
      b_tx_last  = 1'b0;
      ba_sender_done = 1'b1;
      $display("B_TO_A_PACKET_QUEUED t=%0t len=%0d", $time, BA_LEN);
    end
  endtask

  always @(negedge clk) begin
    if (!rst_n) begin
      ready_cycle <= 0;
      a_rx_ready  <= 1'b1;
      b_rx_ready  <= 1'b1;
    end else begin
      ready_cycle <= ready_cycle + 1;
      a_rx_ready  <= !((ready_cycle % 13) == 4);
      b_rx_ready  <= !((ready_cycle % 11) == 3);
    end
  end

  always @(posedge clk) begin
    if (!rst_n) begin
      a_rx_count     <= 0;
      b_rx_count     <= 0;
      a_tx_done_count <= 0;
      b_tx_done_count <= 0;
      a_rx_done_count <= 0;
      b_rx_done_count <= 0;
      ab_payload_ok  <= 1'b0;
      ba_payload_ok  <= 1'b0;
    end else begin
      if (a_tx_done_pulse) begin
        a_tx_done_count <= a_tx_done_count + 1;
        $display("A_TX_DONE t=%0t count=%0d", $time, a_tx_done_count + 1);
      end

      if (b_tx_done_pulse) begin
        b_tx_done_count <= b_tx_done_count + 1;
        $display("B_TX_DONE t=%0t count=%0d", $time, b_tx_done_count + 1);
      end

      if (a_rx_done_pulse) begin
        a_rx_done_count <= a_rx_done_count + 1;
        $display("A_RX_DONE t=%0t count=%0d", $time, a_rx_done_count + 1);
      end

      if (b_rx_done_pulse) begin
        b_rx_done_count <= b_rx_done_count + 1;
        $display("B_RX_DONE t=%0t count=%0d", $time, b_rx_done_count + 1);
      end

      if (b_rx_valid && b_rx_ready) begin
        if (ab_payload_ok) begin
          $fatal(1, "A-to-B payload was delivered more than once");
        end
        if (b_rx_count >= AB_LEN) begin
          $fatal(1, "B received more A-to-B bytes than expected");
        end
        if (b_rx_data !== ab_payload[b_rx_count]) begin
          $fatal(1, "A-to-B byte %0d mismatch exp=%02x got=%02x",
            b_rx_count, ab_payload[b_rx_count], b_rx_data);
        end
        b_rx_count <= b_rx_count + 1;

        if (b_rx_last) begin
          if ((b_rx_count + 1) != AB_LEN) begin
            $fatal(1, "A-to-B length mismatch exp=%0d got=%0d", AB_LEN, b_rx_count + 1);
          end
          ab_payload_ok <= 1'b1;
          $display("A_TO_B_PAYLOAD_OK t=%0t bytes=%0d", $time, b_rx_count + 1);
        end
      end

      if (a_rx_valid && a_rx_ready) begin
        if (ba_payload_ok) begin
          $fatal(1, "B-to-A payload was delivered more than once");
        end
        if (a_rx_count >= BA_LEN) begin
          $fatal(1, "A received more B-to-A bytes than expected");
        end
        if (a_rx_data !== ba_payload[a_rx_count]) begin
          $fatal(1, "B-to-A byte %0d mismatch exp=%02x got=%02x",
            a_rx_count, ba_payload[a_rx_count], a_rx_data);
        end
        a_rx_count <= a_rx_count + 1;

        if (a_rx_last) begin
          if ((a_rx_count + 1) != BA_LEN) begin
            $fatal(1, "B-to-A length mismatch exp=%0d got=%0d", BA_LEN, a_rx_count + 1);
          end
          ba_payload_ok <= 1'b1;
          $display("B_TO_A_PAYLOAD_OK t=%0t bytes=%0d", $time, a_rx_count + 1);
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
    session_id_a = 16'h3456;
    session_id_b = 16'h3456;
    lane_mask_a = '1;
    lane_mask_b = '1;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    ab_sender_done = 1'b0;
    ba_sender_done = 1'b0;

    for (int k = 0; k < MAX_PACKET_BYTES; k++) begin
      ab_payload[k] = byte'(8'h50 + k);
      ba_payload[k] = byte'(8'ha0 + (k * 3));
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    send_a_to_b();

    wait (ab_payload_ok && (a_tx_done_count == 1) && (b_rx_done_count == 1) &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete);
    repeat (20) @(posedge clk);

    send_b_to_a();
  end

  initial begin
    repeat (8000000) begin
      @(posedge clk);
      if (rst_n && (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          b_tx_error_overflow || b_tx_error_retry_exhausted ||
          a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any)) begin
        $fatal(1,
          "Bidirectional loopback error flags: a_tx_overflow=%0b a_retry=%0b b_tx_overflow=%0b b_retry=%0b a_hdr=%0b a_proto=%0b a_frame_overflow=%0b a_crc=%0b a_overrun=%0b b_hdr=%0b b_proto=%0b b_frame_overflow=%0b b_crc=%0b b_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted,
          b_tx_error_overflow, b_tx_error_retry_exhausted,
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
      end

      if (ab_sender_done && ba_sender_done && ab_payload_ok && ba_payload_ok &&
          (a_tx_done_count == 1) && (b_tx_done_count == 1) &&
          (a_rx_done_count == 1) && (b_rx_done_count == 1) &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_tx_packet_active && !b_tx_packet_loading &&
          !a_rx_ctx_valid && !a_rx_ctx_complete && !b_rx_ctx_valid && !b_rx_ctx_complete) begin
        $display("LOOPBACK_BIDIR_SINGLE_LANE_PASS ab_bytes=%0d ba_bytes=%0d a_tx_done=%0d b_tx_done=%0d a_rx_done=%0d b_rx_done=%0d",
          b_rx_count, a_rx_count, a_tx_done_count, b_tx_done_count, a_rx_done_count, b_rx_done_count);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for bidirectional completion ab_sent=%0b ba_sent=%0b ab_ok=%0b ba_ok=%0b a_rx=%0d b_rx=%0d a_tx_done=%0d b_tx_done=%0d a_rx_done=%0d b_rx_done=%0d",
      ab_sender_done, ba_sender_done, ab_payload_ok, ba_payload_ok,
      a_rx_count, b_rx_count, a_tx_done_count, b_tx_done_count, a_rx_done_count, b_rx_done_count);
  end
endmodule
