module ir_fdx_partition_b_core #(
  parameter int LANE_COUNT       = 2,
  parameter int B_SESSION_ID     = 16'h2203,
  parameter int B_CNT_CHIP_MAX   = 7,
  parameter int B_CNT_PREAMBLE   = 64,
  parameter int RAW_PACKET_BYTES = 64,
  parameter int FRAGMENT_BYTES   = 16,
  parameter int APP_PAYLOAD_BYTES = (RAW_PACKET_BYTES > 8) ? (RAW_PACKET_BYTES - 8) : 1,
  parameter int B2A_ENABLE       = 1,
  parameter int B_TX_LANE_MASK   = 2,
  parameter int B_RX_LANE_MASK   = 1
)(
  input  logic                  clk_phy,
  input  logic                  rst_n,
  output logic [LANE_COUNT-1:0] ir_tx_out,
  input  logic [LANE_COUNT-1:0] ir_rx_in,
  output logic [LANE_COUNT-1:0] ir_sd,
  output logic [LANE_COUNT-1:0] ir_mode_out,
  output logic [31:0]           debug_status
);
  localparam int MAX_FRAGS       = (RAW_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int MAX_FRAME_BYTES = 14 + FRAGMENT_BYTES;
  localparam logic [15:0] B_SESSION_ID_U16 = B_SESSION_ID[15:0];
  localparam logic [15:0] APP_PAYLOAD_BYTES_U16 = APP_PAYLOAD_BYTES[15:0];
  localparam logic [LANE_COUNT-1:0] B_TX_MASK_VEC = B_TX_LANE_MASK[LANE_COUNT-1:0];
  localparam logic [LANE_COUNT-1:0] B_RX_MASK_VEC = B_RX_LANE_MASK[LANE_COUNT-1:0];

  logic [7:0] b_tx_data;
  logic       b_tx_valid;
  logic       b_tx_ready;
  logic       b_tx_last;
  logic [7:0] b_rx_data;
  logic       b_rx_valid;
  logic       b_rx_last;

  logic tx_packet_active;
  logic tx_packet_loading;
  logic tx_done_pulse;
  logic tx_error_overflow;
  logic tx_error_retry_exhausted;
  logic rx_ctx_valid;
  logic rx_ctx_complete;
  logic rx_done_pulse;
  logic rx_header_error;
  logic rx_protocol_error;
  logic rx_frame_overflow_any;
  logic rx_crc_error_any;
  logic rx_overrun_error_any;

  logic [LANE_COUNT-1:0] lane_tx_busy_dbg;
  logic [LANE_COUNT-1:0] lane_tx_load_pulse_dbg;
  logic [LANE_COUNT-1:0] lane_rx_frame_pulse_dbg;
  logic [LANE_COUNT-1:0] lane_rx_crc_error_dbg;
  logic [LANE_COUNT-1:0] lane_rx_error_dbg;
  logic [MAX_FRAGS-1:0]  tx_frag_pending_dbg;
  logic [MAX_FRAGS-1:0]  tx_frag_inflight_dbg;
  logic [MAX_FRAGS-1:0]  tx_frag_acked_dbg;
  logic [MAX_FRAGS-1:0]  rx_recv_bitmap_dbg;
  logic [31:0]           rx_debug_status_dbg;

  logic [15:0] tx_seq;
  logic [15:0] tx_byte_idx;
  logic [15:0] tx_start_count;
  logic [15:0] tx_done_count;
  logic        tx_wait_complete;
  logic        tx_error_latched;

  logic [15:0] rx_raw_idx;
  logic        rx_packet_bad;
  logic [15:0] rx_good_count;
  logic [15:0] rx_bad_count;
  logic        rx_error_latched;

  function automatic logic [7:0] b_payload_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      case (idx)
        0:  b_payload_byte = "B";
        1:  b_payload_byte = "2";
        2:  b_payload_byte = "A";
        3:  b_payload_byte = "!";
        4:  b_payload_byte = seq_f[7:0];
        5:  b_payload_byte = seq_f[15:8];
        6:  b_payload_byte = 8'h01;
        7:  b_payload_byte = 8'h00;
        8:  b_payload_byte = ~seq_f[7:0];
        9:  b_payload_byte = ~seq_f[15:8];
        10: b_payload_byte = 8'hfe;
        11: b_payload_byte = 8'hff;
        12: b_payload_byte = 8'h42;
        13: b_payload_byte = 8'h44;
        14: b_payload_byte = 8'h4d;
        15: b_payload_byte = 8'h31;
        default: b_payload_byte = (seq_f[7:0] + (idx * 19) + 8'hb0) & 8'hff;
      endcase
    end
  endfunction

  function automatic logic [7:0] b_raw_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    int payload_idx;
    begin
      payload_idx = idx - 8;
      case (idx)
        0: b_raw_byte = "I";
        1: b_raw_byte = "R";
        2: b_raw_byte = "P";
        3: b_raw_byte = "1";
        4: b_raw_byte = seq_f[7:0];
        5: b_raw_byte = seq_f[15:8];
        6: b_raw_byte = APP_PAYLOAD_BYTES_U16[7:0];
        7: b_raw_byte = APP_PAYLOAD_BYTES_U16[15:8];
        default: b_raw_byte = b_payload_byte(payload_idx, seq_f);
      endcase
    end
  endfunction

  function automatic logic a_raw_byte_bad(input int idx, input logic [7:0] data);
    begin
      case (idx)
        0: a_raw_byte_bad = (data != "I");
        1: a_raw_byte_bad = (data != "R");
        2: a_raw_byte_bad = (data != "P");
        3: a_raw_byte_bad = (data != "1");
        6: a_raw_byte_bad = (data != APP_PAYLOAD_BYTES_U16[7:0]);
        7: a_raw_byte_bad = (data != APP_PAYLOAD_BYTES_U16[15:8]);
        default: a_raw_byte_bad = 1'b0;
      endcase
    end
  endfunction

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      tx_seq           <= 16'h0001;
      tx_byte_idx      <= 16'h0000;
      tx_start_count   <= 16'h0000;
      tx_done_count    <= 16'h0000;
      tx_wait_complete <= 1'b0;
      tx_error_latched <= 1'b0;
      b_tx_data        <= 8'h00;
      b_tx_valid       <= 1'b0;
      b_tx_last        <= 1'b0;
    end else begin
      if (tx_error_overflow || tx_error_retry_exhausted) begin
        tx_error_latched <= 1'b1;
        b_tx_valid       <= 1'b0;
        b_tx_last        <= 1'b0;
        tx_wait_complete <= 1'b0;
        tx_byte_idx      <= 16'h0000;
      end else if (tx_done_pulse) begin
        if (tx_done_count != 16'hffff) tx_done_count <= tx_done_count + 16'd1;
        tx_wait_complete <= 1'b0;
        tx_seq <= tx_seq + 16'd1;
      end else if ((B2A_ENABLE != 0) && (tx_start_count != rx_good_count) &&
                   !tx_wait_complete) begin
        if (!b_tx_valid) begin
          tx_byte_idx    <= 16'h0000;
          b_tx_data      <= b_raw_byte(0, tx_seq);
          b_tx_last      <= (RAW_PACKET_BYTES == 1);
          b_tx_valid     <= 1'b1;
          if (tx_start_count != 16'hffff) tx_start_count <= tx_start_count + 16'd1;
        end else if (b_tx_ready) begin
          if (b_tx_last) begin
            b_tx_valid       <= 1'b0;
            b_tx_last        <= 1'b0;
            tx_wait_complete <= 1'b1;
          end else begin
            tx_byte_idx <= tx_byte_idx + 16'd1;
            b_tx_data   <= b_raw_byte(tx_byte_idx + 1, tx_seq);
            b_tx_last   <= ((tx_byte_idx + 1) == (RAW_PACKET_BYTES - 1));
          end
        end
      end
    end
  end

  always_ff @(posedge clk_phy) begin
    logic byte_bad_v;
    logic packet_bad_v;

    if (!rst_n) begin
      rx_raw_idx       <= 16'h0000;
      rx_packet_bad    <= 1'b0;
      rx_good_count    <= 16'h0000;
      rx_bad_count     <= 16'h0000;
      rx_error_latched <= 1'b0;
    end else begin
      if (rx_header_error || rx_protocol_error || rx_frame_overflow_any ||
          rx_crc_error_any || rx_overrun_error_any) begin
        rx_error_latched <= 1'b1;
      end

      if (b_rx_valid) begin
        byte_bad_v = a_raw_byte_bad(rx_raw_idx, b_rx_data);
        packet_bad_v = rx_packet_bad || byte_bad_v ||
                       (b_rx_last && (rx_raw_idx != (RAW_PACKET_BYTES - 1)));

        if (b_rx_last) begin
          if (packet_bad_v) begin
            if (rx_bad_count != 16'hffff) rx_bad_count <= rx_bad_count + 16'd1;
            rx_error_latched <= 1'b1;
          end else if (rx_good_count != 16'hffff) begin
            rx_good_count <= rx_good_count + 16'd1;
          end
          rx_raw_idx    <= 16'h0000;
          rx_packet_bad <= 1'b0;
        end else begin
          rx_raw_idx    <= rx_raw_idx + 16'd1;
          rx_packet_bad <= packet_bad_v;
        end
      end
    end
  end

  assign debug_status = {
    8'hED,
    tx_done_count[7:0],
    rx_good_count[7:0],
    rx_bad_count[3:0],
    tx_error_latched,
    rx_error_latched,
    tx_packet_active,
    b_tx_valid
  };

  ir_array_top #(
    .LANE_COUNT                (LANE_COUNT),
    .MAX_PACKET_BYTES          (RAW_PACKET_BYTES),
    .FRAGMENT_BYTES            (FRAGMENT_BYTES),
    .MAX_RETRY                 (4),
    .CNT_CHIP_MAX              (B_CNT_CHIP_MAX),
    .CNT_PREAMBLE              (B_CNT_PREAMBLE),
    .EOF_SILENCE_SYMS          (3),
    .FRAG_TIMEOUT_CYCLES       (50000),
    .TX_POST_ACK_GUARD_CYCLES  (8192),
    .RX_TO_TX_GUARD_CYCLES     (8192),
    .REASSEMBLY_TIMEOUT_CYCLES (200000),
    .MAX_FRAGS                 (MAX_FRAGS),
    .MAX_FRAME_BYTES           (MAX_FRAME_BYTES)
  ) u_partner (
    .clk_phy                  (clk_phy),
    .rst_n                    (rst_n),
    .enable                   (1'b1),
    .session_id               (B_SESSION_ID_U16),
    .lane_enable_mask         (B_TX_MASK_VEC),
    .rx_lane_enable_mask      (B_RX_MASK_VEC),
    .s_axis_tx_tdata          (b_tx_data),
    .s_axis_tx_tvalid         (b_tx_valid),
    .s_axis_tx_tready         (b_tx_ready),
    .s_axis_tx_tlast          (b_tx_last),
    .m_axis_rx_tdata          (b_rx_data),
    .m_axis_rx_tvalid         (b_rx_valid),
    .m_axis_rx_tready         (1'b1),
    .m_axis_rx_tlast          (b_rx_last),
    .ir_tx_out                (ir_tx_out),
    .ir_rx_in                 (ir_rx_in),
    .ir_sd                    (ir_sd),
    .ir_mode_out              (ir_mode_out),
    .tx_packet_active         (tx_packet_active),
    .tx_packet_loading        (tx_packet_loading),
    .tx_done_pulse            (tx_done_pulse),
    .tx_error_overflow        (tx_error_overflow),
    .tx_error_retry_exhausted (tx_error_retry_exhausted),
    .rx_ctx_valid             (rx_ctx_valid),
    .rx_ctx_complete          (rx_ctx_complete),
    .rx_done_pulse            (rx_done_pulse),
    .rx_header_error          (rx_header_error),
    .rx_protocol_error        (rx_protocol_error),
    .rx_frame_overflow_any    (rx_frame_overflow_any),
    .rx_crc_error_any         (rx_crc_error_any),
    .rx_overrun_error_any     (rx_overrun_error_any),
    .lane_tx_busy_dbg         (lane_tx_busy_dbg),
    .lane_tx_load_pulse_dbg   (lane_tx_load_pulse_dbg),
    .lane_rx_frame_pulse_dbg  (lane_rx_frame_pulse_dbg),
    .lane_rx_crc_error_dbg    (lane_rx_crc_error_dbg),
    .lane_rx_error_dbg        (lane_rx_error_dbg),
    .tx_frag_pending_dbg      (tx_frag_pending_dbg),
    .tx_frag_inflight_dbg     (tx_frag_inflight_dbg),
    .tx_frag_acked_dbg        (tx_frag_acked_dbg),
    .rx_recv_bitmap_dbg       (rx_recv_bitmap_dbg),
    .rx_debug_status_dbg      (rx_debug_status_dbg)
  );
endmodule
