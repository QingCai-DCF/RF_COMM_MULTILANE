`timescale 1ns/1ps

module tb_ir_array_loopback_recover_after_exhaust_single_lane;
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

  logic drop_ab;
  logic a_busy_q;
  int   a_tx_starts;
  int   starts_at_exhaust;
  int   starts_before_recovery_packet;
  int   rx_count;
  int   b_done_count;
  bit   saw_retry_exhausted;
  bit   recovery_packet_started;
  bit   recovery_payload_ok;
  bit   recovery_tx_done;

  byte first_payload [0:15];
  byte recovery_payload [0:31];
  byte rx_payload [0:31];

  always #7.8125 clk = ~clk; // 64 MHz simulation clock.

  assign b_ir_rx_in[0] = drop_ab ? 1'b1 : ~a_ir_tx_out[0];
  assign a_ir_rx_in[0] = ~b_ir_tx_out[0];

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

  task automatic send_first_payload;
    begin
      for (int k = 0; k < 16; k++) begin
        @(negedge clk);
        a_tx_data  = first_payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == 15);
        wait_tx_ready(k);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
    end
  endtask

  task automatic send_recovery_payload;
    begin
      recovery_packet_started = 1'b1;
      starts_before_recovery_packet = a_tx_starts;
      for (int k = 0; k < 32; k++) begin
        @(negedge clk);
        a_tx_data  = recovery_payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == 31);
        wait_tx_ready(k);
      end
      @(negedge clk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
    end
  endtask

  always @(posedge clk) begin
    if (!rst_n) begin
      a_busy_q                       <= 1'b0;
      a_tx_starts                    <= 0;
      starts_at_exhaust              <= 0;
      starts_before_recovery_packet  <= 0;
      rx_count                       <= 0;
      b_done_count                   <= 0;
      saw_retry_exhausted            <= 1'b0;
      recovery_packet_started        <= 1'b0;
      recovery_payload_ok            <= 1'b0;
      recovery_tx_done               <= 1'b0;
    end else begin
      a_busy_q <= a_lane_tx_busy_dbg[0];
      if (!a_busy_q && a_lane_tx_busy_dbg[0]) begin
        a_tx_starts <= a_tx_starts + 1;
        $display("A_RECOVER_TX_START t=%0t count=%0d drop_ab=%0b", $time, a_tx_starts + 1, drop_ab);
      end

      if (!saw_retry_exhausted && b_rx_valid && b_rx_ready) begin
        $fatal(1, "Outage packet delivered unexpected byte before retry exhaustion data=%02x", b_rx_data);
      end

      if (b_rx_valid && b_rx_ready && recovery_packet_started) begin
        if (rx_count >= 32) begin
          $fatal(1, "Recovery packet delivered extra byte data=%02x", b_rx_data);
        end
        rx_payload[rx_count] = b_rx_data;
        if (b_rx_data !== recovery_payload[rx_count]) begin
          $fatal(1, "Recovery byte mismatch idx=%0d exp=%02x got=%02x",
            rx_count, recovery_payload[rx_count], b_rx_data);
        end
        rx_count = rx_count + 1;
        if (b_rx_last) begin
          if (rx_count != 32) begin
            $fatal(1, "Recovery RX length mismatch exp=32 got=%0d", rx_count);
          end
          recovery_payload_ok = 1'b1;
          $display("B_RECOVERY_PAYLOAD_OK t=%0t bytes=%0d", $time, rx_count);
        end
      end

      if (b_rx_done_pulse) begin
        b_done_count <= b_done_count + 1;
      end

      if (a_tx_error_retry_exhausted) begin
        if (saw_retry_exhausted) begin
          $fatal(1, "Second retry exhaustion after recovery started");
        end
        saw_retry_exhausted <= 1'b1;
        starts_at_exhaust   <= a_tx_starts;
        if (a_tx_starts != (MAX_RETRY + 1)) begin
          $fatal(1, "Expected %0d starts before first retry exhaustion, got %0d",
            MAX_RETRY + 1, a_tx_starts);
        end
        $display("A_RECOVERY_RETRY_EXHAUSTED t=%0t starts=%0d", $time, a_tx_starts);
      end

      if (a_tx_done_pulse) begin
        if (!recovery_packet_started) begin
          $fatal(1, "TX done asserted during outage packet");
        end
        recovery_tx_done <= 1'b1;
      end

      if (a_tx_error_overflow || b_tx_error_overflow || b_tx_error_retry_exhausted ||
          a_rx_header_error || a_rx_protocol_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any ||
          b_rx_header_error || b_rx_protocol_error || b_rx_frame_overflow_any || b_rx_crc_error_any || b_rx_overrun_error_any) begin
        $fatal(1,
          "Recovery-after-exhaust side error: a_overflow=%0b b_overflow=%0b b_retry=%0b a_rx=%0b%0b%0b%0b%0b b_rx=%0b%0b%0b%0b%0b",
          a_tx_error_overflow, b_tx_error_overflow, b_tx_error_retry_exhausted,
          a_rx_header_error, a_rx_protocol_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any,
          b_rx_header_error, b_rx_protocol_error, b_rx_frame_overflow_any, b_rx_crc_error_any, b_rx_overrun_error_any);
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
    session_id_a = 16'h6e21;
    session_id_b = 16'h6e21;
    lane_mask_a = '1;
    lane_mask_b = '1;
    drop_ab = 1'b1;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    a_rx_ready = 1'b1;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    b_rx_ready = 1'b1;

    for (int k = 0; k < 16; k++) begin
      first_payload[k] = 8'h20 + k;
    end
    for (int k = 0; k < 32; k++) begin
      recovery_payload[k] = 8'h90 + k;
      rx_payload[k] = 8'h00;
    end

    repeat (10) @(posedge clk);
    rst_n = 1'b1;
    repeat (10) @(posedge clk);
    enable_a = 1'b1;
    enable_b = 1'b1;
    repeat (10) @(posedge clk);

    send_first_payload();

    repeat (1200000) begin
      @(posedge clk);
      if (saw_retry_exhausted && !a_tx_packet_active && !a_tx_packet_loading && !a_lane_tx_busy_dbg[0]) begin
        break;
      end
    end
    if (!saw_retry_exhausted) begin
      $fatal(1, "Timeout waiting for first retry exhaustion");
    end

    repeat (20) @(posedge clk);
    drop_ab = 1'b0;
    repeat (20) @(posedge clk);
    send_recovery_payload();

    repeat (800000) begin
      @(posedge clk);
      if (recovery_payload_ok && recovery_tx_done &&
          !a_tx_packet_active && !a_tx_packet_loading && !b_rx_ctx_valid && !b_rx_ctx_complete) begin
        if (starts_at_exhaust != (MAX_RETRY + 1)) begin
          $fatal(1, "Bad recorded exhaust starts=%0d", starts_at_exhaust);
        end
        if (b_done_count != 1) begin
          $fatal(1, "Expected one recovery B RX done, got %0d", b_done_count);
        end
        $display("LOOPBACK_RECOVER_AFTER_EXHAUST_SINGLE_LANE_PASS exhaust_starts=%0d recovery_starts=%0d recovery_bytes=%0d b_done=%0d",
          starts_at_exhaust, a_tx_starts - starts_before_recovery_packet, rx_count, b_done_count);
        $finish;
      end
    end

    $fatal(1,
      "Timeout waiting for recovery packet success saw_exhaust=%0b payload_ok=%0b tx_done=%0b rx_count=%0d starts=%0d active=%0b loading=%0b b_ctx=%0b b_complete=%0b",
      saw_retry_exhausted, recovery_payload_ok, recovery_tx_done, rx_count, a_tx_starts,
      a_tx_packet_active, a_tx_packet_loading, b_rx_ctx_valid, b_rx_ctx_complete);
  end
endmodule
