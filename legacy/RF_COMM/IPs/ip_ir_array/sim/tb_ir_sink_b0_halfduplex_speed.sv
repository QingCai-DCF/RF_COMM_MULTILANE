`timescale 1ns/1ps

module tb_ir_sink_b0_halfduplex_speed;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 256;
  localparam int FRAGMENT_BYTES   = 255;
  localparam int MAX_FRAGS        = 2;
  localparam int MAX_FRAME_BYTES  = 14 + FRAGMENT_BYTES;
  localparam int RAW_BYTES        = 255;
  localparam int USER_BYTES       = 247;
  localparam int MIN_MBPS_X1000   = 2400;

  logic clk;
  logic rst_n;

  logic [7:0] a_tx_data;
  logic       a_tx_valid;
  logic       a_tx_ready;
  logic       a_tx_last;
  logic [7:0] a_rx_data;
  logic       a_rx_valid;
  logic       a_rx_ready;
  logic       a_rx_last;

  logic [0:0] a_ir_tx_out;
  logic [0:0] a_ir_rx_in;
  logic [0:0] a_ir_sd;
  logic [0:0] a_ir_mode_out;

  wire b_ir_tx_out;
  wire b_ir_rx_in;
  wire b_ir_sd;
  wire b_ir_mode_out;
  wire [31:0] b_debug_status;

  logic a_tx_packet_active;
  logic a_tx_packet_loading;
  logic a_tx_done_pulse;
  logic a_tx_error_overflow;
  logic a_tx_error_retry_exhausted;
  logic a_rx_ctx_valid;
  logic a_rx_ctx_complete;
  logic a_rx_done_pulse;
  logic a_rx_header_error;
  logic a_rx_protocol_error;
  logic a_rx_frame_overflow_any;
  logic a_rx_crc_error_any;
  logic a_rx_overrun_error_any;
  logic [0:0] a_lane_tx_busy_dbg;
  logic [0:0] a_lane_tx_load_pulse_dbg;
  logic [0:0] a_lane_rx_frame_pulse_dbg;
  logic [0:0] a_lane_rx_crc_error_dbg;
  logic [0:0] a_lane_rx_error_dbg;
  logic [31:0] a_lane_rx_debug_status_dbg;
  logic [MAX_FRAGS-1:0] a_tx_frag_pending_dbg;
  logic [MAX_FRAGS-1:0] a_tx_frag_inflight_dbg;
  logic [MAX_FRAGS-1:0] a_tx_frag_acked_dbg;
  logic [MAX_FRAGS-1:0] a_rx_recv_bitmap_dbg;

  byte tx_raw [0:RAW_BYTES-1];
  time start_time;
  time done_time;
  int tx_done_count;
  int b_rx_done_count;
  longint duration_ns;
  longint mbps_x1000;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = ~b_ir_tx_out;
  assign b_ir_rx_in    = ~a_ir_tx_out[0];

  always @(posedge clk) begin
    if (rst_n && a_tx_done_pulse) begin
      tx_done_count <= tx_done_count + 1;
      done_time = $time;
      $display("A_TX_DONE t=%0t count=%0d acked=%04x", $time, tx_done_count + 1, a_tx_frag_acked_dbg);
    end
    if (rst_n && dut_b.u_partner.rx_done_pulse) begin
      b_rx_done_count <= b_rx_done_count + 1;
      $display("B_RX_DONE t=%0t count=%0d dbg=%08x", $time, b_rx_done_count + 1, b_debug_status);
    end
  end

  ir_array_top #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(64),
    .EOF_SILENCE_SYMS(3),
    .FRAG_TIMEOUT_CYCLES(50000),
    .TX_POST_ACK_GUARD_CYCLES(4096),
    .RX_TO_TX_GUARD_CYCLES(4096),
    .REASSEMBLY_TIMEOUT_CYCLES(200000),
    .MAX_FRAGS(MAX_FRAGS),
    .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
  ) dut_a (
    .clk_phy(clk),
    .rst_n(rst_n),
    .enable(1'b1),
    .session_id(16'h2201),
    .lane_enable_mask(1'b1),
    .rx_lane_enable_mask(1'b1),
    .s_axis_tx_tdata(a_tx_data),
    .s_axis_tx_tvalid(a_tx_valid),
    .s_axis_tx_tready(a_tx_ready),
    .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data),
    .m_axis_rx_tvalid(a_rx_valid),
    .m_axis_rx_tready(a_rx_ready),
    .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out),
    .ir_rx_in(a_ir_rx_in),
    .ir_sd(a_ir_sd),
    .ir_mode_out(a_ir_mode_out),
    .tx_packet_active(a_tx_packet_active),
    .tx_packet_loading(a_tx_packet_loading),
    .tx_done_pulse(a_tx_done_pulse),
    .tx_error_overflow(a_tx_error_overflow),
    .tx_error_retry_exhausted(a_tx_error_retry_exhausted),
    .rx_ctx_valid(a_rx_ctx_valid),
    .rx_ctx_complete(a_rx_ctx_complete),
    .rx_done_pulse(a_rx_done_pulse),
    .rx_header_error(a_rx_header_error),
    .rx_protocol_error(a_rx_protocol_error),
    .rx_frame_overflow_any(a_rx_frame_overflow_any),
    .rx_crc_error_any(a_rx_crc_error_any),
    .rx_overrun_error_any(a_rx_overrun_error_any),
    .lane_tx_busy_dbg(a_lane_tx_busy_dbg),
    .lane_tx_load_pulse_dbg(a_lane_tx_load_pulse_dbg),
    .lane_rx_frame_pulse_dbg(a_lane_rx_frame_pulse_dbg),
    .lane_rx_crc_error_dbg(a_lane_rx_crc_error_dbg),
    .lane_rx_error_dbg(a_lane_rx_error_dbg),
    .lane_rx_debug_status_dbg(a_lane_rx_debug_status_dbg),
    .tx_frag_pending_dbg(a_tx_frag_pending_dbg),
    .tx_frag_inflight_dbg(a_tx_frag_inflight_dbg),
    .tx_frag_acked_dbg(a_tx_frag_acked_dbg),
    .rx_recv_bitmap_dbg(a_rx_recv_bitmap_dbg),
    .rx_debug_status_dbg()
  );

  ir_sink_b0_bd dut_b (
    .clk_phy(clk),
    .rst_n(rst_n),
    .ir_tx_out(b_ir_tx_out),
    .ir_rx_in(b_ir_rx_in),
    .ir_sd(b_ir_sd),
    .ir_mode_out(b_ir_mode_out),
    .debug_status(b_debug_status)
  );

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    a_rx_ready = 1'b1;
    tx_done_count = 0;
    b_rx_done_count = 0;
    start_time = 0;
    done_time = 0;

    for (int k = 0; k < RAW_BYTES; k++) begin
      tx_raw[k] = k[7:0] ^ 8'h5a;
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (20) @(posedge clk);

    start_time = $time;
    for (int k = 0; k < RAW_BYTES; k++) begin
      @(posedge clk);
      a_tx_data  <= tx_raw[k];
      a_tx_valid <= 1'b1;
      a_tx_last  <= (k == RAW_BYTES - 1);
      wait (a_tx_ready);
    end
    @(posedge clk);
    a_tx_valid <= 1'b0;
    a_tx_last  <= 1'b0;

    repeat (1000000) begin
      @(posedge clk);
      if (a_tx_error_overflow || a_tx_error_retry_exhausted ||
          a_rx_header_error || a_rx_frame_overflow_any || a_rx_crc_error_any || a_rx_overrun_error_any) begin
        $fatal(1,
          "A error flags: tx_overflow=%0b tx_retry_exhausted=%0b rx_hdr=%0b rx_frame_ovf=%0b rx_crc=%0b rx_overrun=%0b",
          a_tx_error_overflow, a_tx_error_retry_exhausted, a_rx_header_error, a_rx_frame_overflow_any, a_rx_crc_error_any, a_rx_overrun_error_any);
      end
      if (dut_b.u_partner.rx_protocol_error || dut_b.u_partner.rx_frame_overflow_any ||
          dut_b.u_partner.rx_crc_error_any || dut_b.u_partner.rx_overrun_error_any) begin
        $fatal(1,
          "B error flags: proto=%0b frame_ovf=%0b crc=%0b overrun=%0b dbg=%08x",
          dut_b.u_partner.rx_protocol_error, dut_b.u_partner.rx_frame_overflow_any,
          dut_b.u_partner.rx_crc_error_any, dut_b.u_partner.rx_overrun_error_any, b_debug_status);
      end

      if ((tx_done_count > 0) && (b_rx_done_count > 0)) begin
        duration_ns = done_time - start_time;
        mbps_x1000 = (USER_BYTES * 8 * 1000000) / duration_ns;
        if (mbps_x1000 < MIN_MBPS_X1000) begin
          $fatal(1, "HALFDUPLEX speed too low: %0d.%03d Mbit/s duration_ns=%0d",
            mbps_x1000 / 1000, mbps_x1000 % 1000, duration_ns);
        end
        $display("IR_SINK_B0_HALFDUPLEX_SPEED_PASS user_bytes=%0d raw_bytes=%0d duration_ns=%0d mbps=%0d.%03d tx_done=%0d b_rx_done=%0d",
          USER_BYTES, RAW_BYTES, duration_ns, mbps_x1000 / 1000, mbps_x1000 % 1000, tx_done_count, b_rx_done_count);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for half-duplex sink speed tx_done=%0d b_rx_done=%0d acked=%04x b_dbg=%08x",
      tx_done_count, b_rx_done_count, a_tx_frag_acked_dbg, b_debug_status);
  end
endmodule
