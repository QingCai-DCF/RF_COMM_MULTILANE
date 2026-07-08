module ir_stream_bidir_b0_core #(
  parameter int LANE_COUNT       = 1,
  parameter int B_SESSION_ID     = 16'h2201,
  parameter int B_CNT_CHIP_MAX   = 15,
  parameter int B_CNT_PREAMBLE     = 64,
  parameter int B_RX_DATA_PHASE_DELAY_CYCLES = 0,
  parameter int B_RX_DETECT_START_CYCLES = (B_CNT_CHIP_MAX >= 15) ? 0 : ((B_CNT_CHIP_MAX >= 7) ? 3 : 0),
  parameter int B_RX_DETECT_END_CYCLES = (B_CNT_CHIP_MAX >= 15) ? 10 : B_CNT_CHIP_MAX,
  parameter int B_RX_PREAMBLE_REALIGN_EDGE = 0,
  parameter int B_GUARD_CYCLES     = 1408,
  parameter int B_BACKOFF_SLOT_CYCLES = 1024,
  parameter int B_START_IDLE_CYCLES = 100000,
  parameter int B_RECOVERY_RESET_CYCLES = 2048,
  parameter int B_PARALLEL_2LANE_MODE = 0,
  parameter int B_DEBUG_SELECT_RX_STATUS = 0,
  parameter int B_ACK_LANE_MASK = -1,
  parameter int B_TX_LANE_MASK = -1,
  parameter int B_RX_LANE_MASK = -1,
  parameter int B_EXPECTED_A_LANE_MASK = -1,
  parameter int RAW_PACKET_BYTES   = 255,
  parameter int FRAGMENT_BYTES     = (RAW_PACKET_BYTES > 255) ? 255 : RAW_PACKET_BYTES,
  parameter int APP_PAYLOAD_BYTES  = 247,
  parameter int B2A_ENABLE         = 1,
  parameter int B2A_FREE_RUN       = 0,
  parameter int B2A_ECHO_ENABLE    = 0,
  parameter int FORCE_SD_SHUTDOWN  = 0,
  parameter int TX_GAP_CYCLES      = 0
)(
  input  logic        clk_phy,
  input  logic        rst_n,
  output logic [LANE_COUNT-1:0] ir_tx_out,
  input  logic [LANE_COUNT-1:0] ir_rx_in,
  output logic [LANE_COUNT-1:0] ir_sd,
  output logic [LANE_COUNT-1:0] ir_mode_out,
  output logic [31:0] debug_status
);
  localparam int MAX_FRAGS        = (RAW_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int MAX_FRAME_BYTES  = 14 + FRAGMENT_BYTES;
  localparam logic [15:0] RAW_PACKET_BYTES_U16 = RAW_PACKET_BYTES[15:0];
  localparam logic [15:0] APP_PAYLOAD_BYTES_U16 = APP_PAYLOAD_BYTES[15:0];
  localparam logic [15:0] B_SESSION_ID_U16 = B_SESSION_ID[15:0];
  localparam logic [31:0] TX_GAP_CYCLES_U32 = TX_GAP_CYCLES[31:0];
  localparam logic [31:0] B_START_IDLE_CYCLES_U32 = B_START_IDLE_CYCLES[31:0];
  localparam logic [31:0] B_RECOVERY_RESET_CYCLES_U32 = B_RECOVERY_RESET_CYCLES[31:0];
  localparam logic [LANE_COUNT-1:0] B_ACK_LANE_MASK_VEC = B_ACK_LANE_MASK[LANE_COUNT-1:0];
  localparam logic [LANE_COUNT-1:0] B_TX_LANE_MASK_VEC =
    (B_TX_LANE_MASK < 0) ? {LANE_COUNT{1'b1}} : B_TX_LANE_MASK[LANE_COUNT-1:0];
  localparam logic [LANE_COUNT-1:0] B_RX_LANE_MASK_VEC =
    (B_RX_LANE_MASK < 0) ? {LANE_COUNT{1'b1}} : B_RX_LANE_MASK[LANE_COUNT-1:0];
  localparam logic [31:0] DEFAULT_EXPECTED_A_LANE_MASK_U32 =
    (32'h0000_0001 << LANE_COUNT) - 32'h0000_0001;
  localparam logic [31:0] EXPECTED_A_LANE_MASK_U32 =
    (B_EXPECTED_A_LANE_MASK < 0) ? DEFAULT_EXPECTED_A_LANE_MASK_U32 : B_EXPECTED_A_LANE_MASK[31:0];

  logic [7:0] b_tx_data;
  logic       b_tx_valid;
  logic       b_tx_ready;
  logic       b_tx_last;
  logic [7:0] b_rx_data;
  logic       b_rx_valid;
  logic       b_rx_last;

  logic [LANE_COUNT-1:0] lane_tx_busy_dbg;
  logic [LANE_COUNT-1:0] lane_tx_load_pulse_dbg;
  logic [LANE_COUNT-1:0] lane_rx_frame_pulse_dbg;
  logic [LANE_COUNT-1:0] lane_rx_crc_error_dbg;
  logic [LANE_COUNT-1:0] lane_rx_error_dbg;
  logic [32*LANE_COUNT-1:0] lane_rx_debug_status_dbg;
  logic [MAX_FRAGS-1:0] tx_frag_pending_dbg;
  logic [MAX_FRAGS-1:0] tx_frag_inflight_dbg;
  logic [MAX_FRAGS-1:0] tx_frag_acked_dbg;
  logic [MAX_FRAGS-1:0] rx_recv_bitmap_dbg;
  logic [31:0] stream_debug;
  logic [31:0] lane0_rx_debug_status;
  logic [31:0] lane1_rx_debug_status;
  logic [31:0] selected_rx_debug_status;
  logic [31:0] app_debug_status;
  logic [31:0] app_packet_bad_status;
  logic        app_packet_bad_seen;
  logic lane1_tx_load_dbg;

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

  logic [15:0] tx_seq;
  logic [15:0] tx_byte_idx;
  logic        tx_wait_complete;
  logic [31:0] tx_gap_count;
  logic [15:0] tx_start_count;
  logic [15:0] tx_done_count;
  logic [15:0] rx_good_count;
  logic [15:0] rx_bad_count;
  logic        rx_bad_seen;
  logic        b_tx_activity_seen;
  logic [7:0]  b_rx_summary_flags;
  logic [7:0] ack_tx_lane0_count;
  logic [7:0] ack_tx_lane1_count;
  logic [LANE_COUNT-1:0] ir_rx_in_d;
  logic raw_rx_edge_lane0;
  logic raw_rx_edge_lane1;
  logic [7:0] raw_rx_edge_lane0_count;
  logic [7:0] raw_rx_edge_lane1_count;
  logic        link_seen;
  logic        tx_error_latched;
  logic        rx_error_latched;
  logic        partner_enable;
  logic [31:0] partner_reset_count;
  logic [31:0] tx_start_idle_count;
  logic        tx_start_idle_ready;
  logic        stream_channel_idle;
  logic        stream_any_rx_active;
  logic        stream_ack_pending;

  logic [15:0] rx_raw_idx;
  logic [15:0] rx_payload_seq;
  logic [15:0] rx_declared_payload_len;
  logic        rx_packet_bad;
  logic [7:0]  b_echo_buf [0:RAW_PACKET_BYTES-1];
  logic [15:0] b_echo_len;
  logic        b_echo_valid;
  logic        b_echo_clear_req;

  assign stream_any_rx_active = stream_debug[11];
  assign stream_channel_idle  = stream_debug[12];
  assign stream_ack_pending   = stream_debug[13];
  assign tx_start_idle_ready  = (B_START_IDLE_CYCLES_U32 == 32'h0000_0000) ||
                                (tx_start_idle_count >= B_START_IDLE_CYCLES_U32);
  assign b_echo_clear_req     = (B2A_ECHO_ENABLE != 0) &&
                                (!partner_enable || tx_done_pulse ||
                                 tx_error_overflow || tx_error_retry_exhausted);

  generate
    if (LANE_COUNT > 1) begin : g_lane1_tx_load_dbg
      assign lane1_tx_load_dbg = lane_tx_load_pulse_dbg[1];
      assign raw_rx_edge_lane1 = ir_rx_in_d[1] ^ ir_rx_in[1];
    end else begin : g_no_lane1_tx_load_dbg
      assign lane1_tx_load_dbg = 1'b0;
      assign raw_rx_edge_lane1 = 1'b0;
    end
  endgenerate
  assign raw_rx_edge_lane0 = ir_rx_in_d[0] ^ ir_rx_in[0];
  assign lane0_rx_debug_status = lane_rx_debug_status_dbg[31:0];
  generate
    if (LANE_COUNT > 1) begin : g_lane1_rx_debug_status
      assign lane1_rx_debug_status = lane_rx_debug_status_dbg[63:32];
    end else begin : g_no_lane1_rx_debug_status
      assign lane1_rx_debug_status = 32'h0000_0000;
    end
  endgenerate
  always_comb begin
    unique case (B_DEBUG_SELECT_RX_STATUS)
      1: selected_rx_debug_status = lane0_rx_debug_status;
      2: selected_rx_debug_status = lane1_rx_debug_status;
      3: selected_rx_debug_status = stream_debug;
      default: selected_rx_debug_status = 32'h0000_0000;
    endcase
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      partner_enable      <= 1'b1;
      partner_reset_count <= 32'h0000_0000;
    end else if (tx_error_overflow || tx_error_retry_exhausted) begin
      partner_enable      <= 1'b0;
      partner_reset_count <= B_RECOVERY_RESET_CYCLES_U32;
    end else if (partner_reset_count != 32'h0000_0000) begin
      partner_enable      <= 1'b0;
      partner_reset_count <= partner_reset_count - 1'b1;
    end else begin
      partner_enable <= 1'b1;
    end
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      tx_start_idle_count <= 32'h0000_0000;
    end else if (!partner_enable || tx_packet_active || b_tx_valid || tx_wait_complete ||
                 !stream_channel_idle || stream_any_rx_active || stream_ack_pending) begin
      tx_start_idle_count <= 32'h0000_0000;
    end else if (tx_start_idle_count < B_START_IDLE_CYCLES_U32) begin
      tx_start_idle_count <= tx_start_idle_count + 1'b1;
    end
  end

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

  function automatic logic [7:0] b_tx_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      if ((B2A_ECHO_ENABLE != 0) && b_echo_valid && idx < b_echo_len) begin
        b_tx_byte = b_echo_buf[idx];
      end else begin
        b_tx_byte = b_raw_byte(idx, seq_f);
      end
    end
  endfunction

  function automatic logic [15:0] b_tx_len;
    begin
      if ((B2A_ECHO_ENABLE != 0) && b_echo_valid && b_echo_len != 16'h0000) begin
        b_tx_len = b_echo_len;
      end else begin
        b_tx_len = RAW_PACKET_BYTES_U16;
      end
    end
  endfunction

  function automatic logic [7:0] expected_a_payload_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      case (idx)
        0:  expected_a_payload_byte = "P";
        1:  expected_a_payload_byte = "S";
        2:  expected_a_payload_byte = "P";
        3:  expected_a_payload_byte = "S";
        4:  expected_a_payload_byte = seq_f[7:0];
        5:  expected_a_payload_byte = seq_f[15:8];
        6:  expected_a_payload_byte = 8'h00;
        7:  expected_a_payload_byte = 8'h00;
        8:  expected_a_payload_byte = EXPECTED_A_LANE_MASK_U32[7:0];
        9:  expected_a_payload_byte = EXPECTED_A_LANE_MASK_U32[15:8];
        10: expected_a_payload_byte = EXPECTED_A_LANE_MASK_U32[23:16];
        11: expected_a_payload_byte = EXPECTED_A_LANE_MASK_U32[31:24];
        12: expected_a_payload_byte = ~seq_f[7:0];
        13: expected_a_payload_byte = ~seq_f[15:8];
        14: expected_a_payload_byte = 8'hff;
        15: expected_a_payload_byte = 8'hff;
        default: expected_a_payload_byte =
          (seq_f[7:0] + (idx * 17) + EXPECTED_A_LANE_MASK_U32[7:0]) & 8'hff;
      endcase
    end
  endfunction

  function automatic logic [7:0] expected_a_raw_byte(
    input int idx,
    input logic [15:0] seq_f
  );
    begin
      if (idx >= 0 && idx < APP_PAYLOAD_BYTES) begin
        expected_a_raw_byte = expected_a_payload_byte(idx, seq_f);
      end else begin
        expected_a_raw_byte = 8'h00;
      end
    end
  endfunction

  function automatic logic a_raw_byte_bad(
    input int idx,
    input logic [7:0] data,
    input logic [15:0] seq_f
  );
    begin
      case (idx)
        0: a_raw_byte_bad = (data != "P");
        1: a_raw_byte_bad = (data != "S");
        2: a_raw_byte_bad = (data != "P");
        3: a_raw_byte_bad = (data != "S");
        4: a_raw_byte_bad = 1'b0;
        5: a_raw_byte_bad = 1'b0;
        6: a_raw_byte_bad = (data != 8'h00);
        7: a_raw_byte_bad = (data != 8'h00);
        12: a_raw_byte_bad = (data != ~seq_f[7:0]);
        13: a_raw_byte_bad = (data != ~seq_f[15:8]);
        default: begin
          if ((B2A_ECHO_ENABLE != 0) && idx >= 0 && idx < APP_PAYLOAD_BYTES) begin
            a_raw_byte_bad = 1'b0;
          end else if (idx >= 0 && idx < APP_PAYLOAD_BYTES) begin
            a_raw_byte_bad = (data != expected_a_payload_byte(idx, seq_f));
          end else begin
            a_raw_byte_bad = 1'b1;
          end
        end
      endcase
    end
  endfunction

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      tx_seq            <= 16'h0001;
      tx_byte_idx       <= 16'h0000;
      b_tx_data         <= 8'h00;
      b_tx_valid        <= 1'b0;
      b_tx_last         <= 1'b0;
      tx_wait_complete  <= 1'b0;
      tx_gap_count      <= 32'h0000_0000;
      tx_start_count    <= 16'h0000;
      tx_done_count     <= 16'h0000;
      tx_error_latched  <= 1'b0;
    end else begin
      if (tx_error_overflow || tx_error_retry_exhausted) begin
        tx_error_latched <= 1'b1;
      end

      if (!partner_enable || tx_error_overflow || tx_error_retry_exhausted) begin
        b_tx_valid       <= 1'b0;
        b_tx_last        <= 1'b0;
        tx_byte_idx      <= 16'h0000;
        tx_wait_complete <= 1'b0;
        tx_gap_count     <= TX_GAP_CYCLES_U32;
      end else if (tx_done_pulse) begin
        if (tx_done_count != 16'hffff) tx_done_count <= tx_done_count + 16'd1;
        tx_wait_complete <= 1'b0;
        tx_gap_count <= TX_GAP_CYCLES_U32;
        tx_seq <= tx_seq + 16'd1;
      end else if (tx_gap_count != 32'h0000_0000) begin
        tx_gap_count <= tx_gap_count - 1'b1;
      end else if ((B2A_ENABLE != 0) &&
                   ((B2A_FREE_RUN != 0) || (tx_done_count != rx_good_count)) &&
                   ((B2A_ECHO_ENABLE == 0) || b_echo_valid) &&
                   !tx_wait_complete &&
                   (b_tx_valid || tx_start_idle_ready)) begin
        if (!b_tx_valid) begin
          tx_byte_idx <= 16'h0000;
          b_tx_data   <= b_tx_byte(0, tx_seq);
          b_tx_last   <= (b_tx_len() == 16'd1);
          b_tx_valid  <= 1'b1;
          if (tx_start_count != 16'hffff) tx_start_count <= tx_start_count + 16'd1;
        end else if (b_tx_ready) begin
          if (b_tx_last) begin
            b_tx_valid       <= 1'b0;
            b_tx_last        <= 1'b0;
            tx_wait_complete <= 1'b1;
          end else begin
            tx_byte_idx <= tx_byte_idx + 16'd1;
            b_tx_data   <= b_tx_byte(tx_byte_idx + 1, tx_seq);
            b_tx_last   <= ((tx_byte_idx + 1) == (b_tx_len() - 1'b1));
          end
        end
      end
    end
  end

  always_ff @(posedge clk_phy) begin
    logic byte_bad_v;
    logic packet_bad_v;
    logic [7:0] expected_byte_v;
    logic [31:0] new_bad_status_v;

    if (!rst_n) begin
      rx_raw_idx       <= 16'h0000;
      rx_payload_seq   <= 16'h0000;
      rx_declared_payload_len <= 16'h0000;
      rx_packet_bad    <= 1'b0;
      rx_good_count    <= 16'h0000;
      rx_bad_count     <= 16'h0000;
      rx_bad_seen      <= 1'b0;
      link_seen        <= 1'b0;
      rx_error_latched <= 1'b0;
      app_debug_status <= 32'h0000_0000;
      app_packet_bad_status <= 32'h0000_0000;
      app_packet_bad_seen <= 1'b0;
      b_echo_len       <= 16'h0000;
      b_echo_valid     <= 1'b0;
    end else begin
      logic [15:0] expected_raw_len_v;
      logic len_bad_v;

      if (rx_header_error || rx_protocol_error || rx_frame_overflow_any ||
          rx_crc_error_any || rx_overrun_error_any) begin
        rx_error_latched <= 1'b1;
      end
      if (b_echo_clear_req) begin
        b_echo_valid <= 1'b0;
      end

      if (b_rx_valid) begin
        expected_raw_len_v = APP_PAYLOAD_BYTES_U16;
        len_bad_v = (expected_raw_len_v == 16'h0000) ||
                    (rx_raw_idx != (expected_raw_len_v - 1'b1));

        if (rx_raw_idx == 16'd4) rx_payload_seq[7:0]  <= b_rx_data;
        if (rx_raw_idx == 16'd5) rx_payload_seq[15:8] <= b_rx_data;
        if ((B2A_ECHO_ENABLE != 0) && (rx_raw_idx < RAW_PACKET_BYTES_U16)) begin
          b_echo_buf[rx_raw_idx] <= b_rx_data;
        end

        expected_byte_v = expected_a_raw_byte(rx_raw_idx, rx_payload_seq);
        byte_bad_v = a_raw_byte_bad(rx_raw_idx, b_rx_data, rx_payload_seq);
        new_bad_status_v = {4'hD, 4'h7, rx_raw_idx[7:0], expected_byte_v, b_rx_data};
        packet_bad_v = rx_packet_bad || byte_bad_v ||
                       (b_rx_last && len_bad_v);

        if (byte_bad_v && !rx_packet_bad && !app_packet_bad_seen) begin
          app_packet_bad_seen <= 1'b1;
          app_packet_bad_status <= new_bad_status_v;
        end

        if (b_rx_last) begin
          if (packet_bad_v) begin
            if (rx_bad_count != 16'hffff) rx_bad_count <= rx_bad_count + 16'd1;
            rx_bad_seen <= 1'b1;
            rx_error_latched <= 1'b1;
            if (app_packet_bad_seen) begin
              app_debug_status <= app_packet_bad_status;
            end else if (byte_bad_v) begin
              app_debug_status <= new_bad_status_v;
            end else begin
              app_debug_status <= {4'hD, 4'h8, rx_raw_idx[7:0], RAW_PACKET_BYTES_U16[7:0], 8'h00};
            end
          end else begin
            if (rx_good_count != 16'hffff) rx_good_count <= rx_good_count + 16'd1;
            link_seen <= 1'b1;
            app_debug_status <= 32'h0000_0000;
            if (B2A_ECHO_ENABLE != 0) begin
              b_echo_len <= rx_raw_idx + 16'd1;
              b_echo_valid <= 1'b1;
            end
          end
          rx_raw_idx    <= 16'h0000;
          rx_declared_payload_len <= 16'h0000;
          rx_packet_bad <= 1'b0;
          app_packet_bad_seen <= 1'b0;
          app_packet_bad_status <= 32'h0000_0000;
        end else begin
          rx_raw_idx    <= rx_raw_idx + 16'd1;
          rx_packet_bad <= packet_bad_v;
        end
      end
    end
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      ack_tx_lane0_count <= 8'h00;
      ack_tx_lane1_count <= 8'h00;
      ir_rx_in_d <= {LANE_COUNT{1'b1}};
      raw_rx_edge_lane0_count <= 8'h00;
      raw_rx_edge_lane1_count <= 8'h00;
      b_tx_activity_seen <= 1'b0;
    end else begin
      ir_rx_in_d <= ir_rx_in;
      if (raw_rx_edge_lane0 && raw_rx_edge_lane0_count != 8'hff) begin
        raw_rx_edge_lane0_count <= raw_rx_edge_lane0_count + 8'd1;
      end
      if (raw_rx_edge_lane1 && raw_rx_edge_lane1_count != 8'hff) begin
        raw_rx_edge_lane1_count <= raw_rx_edge_lane1_count + 8'd1;
      end
      if (lane_tx_load_pulse_dbg[0] && ack_tx_lane0_count != 8'hff) begin
        ack_tx_lane0_count <= ack_tx_lane0_count + 8'd1;
      end
      if (lane1_tx_load_dbg && ack_tx_lane1_count != 8'hff) begin
        ack_tx_lane1_count <= ack_tx_lane1_count + 8'd1;
      end
      if (|lane_tx_load_pulse_dbg) begin
        b_tx_activity_seen <= 1'b1;
      end
    end
  end

  assign b_rx_summary_flags = {
    3'b000,
    b_tx_activity_seen,
    (tx_start_count != 16'h0000),
    rx_error_latched,
    rx_bad_seen,
    (rx_good_count != 16'h0000)
  };

  assign debug_status = (B_DEBUG_SELECT_RX_STATUS == 7) ? {
    8'hEB,
    b_rx_summary_flags,
    rx_good_count[15:0]
  } : (B_DEBUG_SELECT_RX_STATUS != 0) ? selected_rx_debug_status :
    ((app_debug_status[31:28] == 4'hD) ? app_debug_status : {
    8'hEC,
    ack_tx_lane1_count[7:0],
    lane_tx_load_pulse_dbg[0] ? (ack_tx_lane0_count + 8'd1) : ack_tx_lane0_count,
    rx_good_count[7:0]
  });

  generate
    if (B_PARALLEL_2LANE_MODE != 0 && LANE_COUNT == 2) begin : g_b_parallel_2lane
      ir_stream_parallel_2lane_top #(
        .NODE_ID(1),
        .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_RETRY(4),
        .CNT_CHIP_MAX(B_CNT_CHIP_MAX),
        .CNT_PREAMBLE(B_CNT_PREAMBLE),
        .EOF_SILENCE_SYMS(3),
        .RX_DATA_PHASE_DELAY_CYCLES(B_RX_DATA_PHASE_DELAY_CYCLES),
        .RX_DETECT_START_CYCLES(B_RX_DETECT_START_CYCLES),
        .RX_DETECT_END_CYCLES(B_RX_DETECT_END_CYCLES),
        .RX_PREAMBLE_REALIGN_EDGE(B_RX_PREAMBLE_REALIGN_EDGE),
        .FORCE_SD_SHUTDOWN(FORCE_SD_SHUTDOWN),
        .ACK_LANE_MASK(B_ACK_LANE_MASK_VEC),
        .FRAG_TIMEOUT_CYCLES(120000),
        .TX_TO_RX_GUARD_CYCLES(B_GUARD_CYCLES),
        .BACKOFF_SLOT_CYCLES(B_BACKOFF_SLOT_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES(200000),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) u_partner_parallel (
        .clk_phy(clk_phy),
        .rst_n(rst_n),
        .enable(partner_enable),
        .session_id(B_SESSION_ID_U16),
        .lane_enable_mask(B_TX_LANE_MASK_VEC),
        .rx_lane_enable_mask(B_RX_LANE_MASK_VEC),
        .s_axis_tx_tdata(b_tx_data),
        .s_axis_tx_tvalid(b_tx_valid),
        .s_axis_tx_tready(b_tx_ready),
        .s_axis_tx_tlast(b_tx_last),
        .m_axis_rx_tdata(b_rx_data),
        .m_axis_rx_tvalid(b_rx_valid),
        .m_axis_rx_tready(1'b1),
        .m_axis_rx_tlast(b_rx_last),
        .ir_tx_out(ir_tx_out),
        .ir_rx_in(ir_rx_in),
        .ir_sd(ir_sd),
        .ir_mode_out(ir_mode_out),
        .tx_packet_active(tx_packet_active),
        .tx_packet_loading(tx_packet_loading),
        .tx_done_pulse(tx_done_pulse),
        .tx_error_overflow(tx_error_overflow),
        .tx_error_retry_exhausted(tx_error_retry_exhausted),
        .rx_ctx_valid(rx_ctx_valid),
        .rx_ctx_complete(rx_ctx_complete),
        .rx_done_pulse(rx_done_pulse),
        .rx_header_error(rx_header_error),
        .rx_protocol_error(rx_protocol_error),
        .rx_frame_overflow_any(rx_frame_overflow_any),
        .rx_crc_error_any(rx_crc_error_any),
        .rx_overrun_error_any(rx_overrun_error_any),
        .lane_tx_busy_dbg(lane_tx_busy_dbg),
        .lane_tx_load_pulse_dbg(lane_tx_load_pulse_dbg),
        .lane_rx_frame_pulse_dbg(lane_rx_frame_pulse_dbg),
        .lane_rx_crc_error_dbg(lane_rx_crc_error_dbg),
        .lane_rx_error_dbg(lane_rx_error_dbg),
        .lane_rx_debug_status_dbg(lane_rx_debug_status_dbg),
        .tx_frag_pending_dbg(tx_frag_pending_dbg),
        .tx_frag_inflight_dbg(tx_frag_inflight_dbg),
        .tx_frag_acked_dbg(tx_frag_acked_dbg),
        .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg),
        .debug_status(stream_debug)
      );
    end else begin : g_b_legacy
      ir_stream_array_top #(
        .LANE_COUNT(LANE_COUNT),
        .NODE_ID(1),
        .MAX_PACKET_BYTES(RAW_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_RETRY(4),
        .CNT_CHIP_MAX(B_CNT_CHIP_MAX),
        .CNT_PREAMBLE(B_CNT_PREAMBLE),
        .EOF_SILENCE_SYMS(3),
        .RX_DATA_PHASE_DELAY_CYCLES(B_RX_DATA_PHASE_DELAY_CYCLES),
        .RX_DETECT_START_CYCLES(B_RX_DETECT_START_CYCLES),
        .RX_DETECT_END_CYCLES(B_RX_DETECT_END_CYCLES),
        .RX_PREAMBLE_REALIGN_EDGE(B_RX_PREAMBLE_REALIGN_EDGE),
        .FORCE_SD_SHUTDOWN(FORCE_SD_SHUTDOWN),
        .ACK_LANE_MASK(B_ACK_LANE_MASK_VEC),
        .FRAG_TIMEOUT_CYCLES(120000),
        .TX_TO_RX_GUARD_CYCLES(B_GUARD_CYCLES),
        .BACKOFF_SLOT_CYCLES(B_BACKOFF_SLOT_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES(200000),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) u_partner (
        .clk_phy(clk_phy),
        .rst_n(rst_n),
        .enable(partner_enable),
        .session_id(B_SESSION_ID_U16),
        .lane_enable_mask(B_TX_LANE_MASK_VEC),
        .rx_lane_enable_mask(B_RX_LANE_MASK_VEC),
        .s_axis_tx_tdata(b_tx_data),
        .s_axis_tx_tvalid(b_tx_valid),
        .s_axis_tx_tready(b_tx_ready),
        .s_axis_tx_tlast(b_tx_last),
        .m_axis_rx_tdata(b_rx_data),
        .m_axis_rx_tvalid(b_rx_valid),
        .m_axis_rx_tready(1'b1),
        .m_axis_rx_tlast(b_rx_last),
        .ir_tx_out(ir_tx_out),
        .ir_rx_in(ir_rx_in),
        .ir_sd(ir_sd),
        .ir_mode_out(ir_mode_out),
        .tx_packet_active(tx_packet_active),
        .tx_packet_loading(tx_packet_loading),
        .tx_done_pulse(tx_done_pulse),
        .tx_error_overflow(tx_error_overflow),
        .tx_error_retry_exhausted(tx_error_retry_exhausted),
        .rx_ctx_valid(rx_ctx_valid),
        .rx_ctx_complete(rx_ctx_complete),
        .rx_done_pulse(rx_done_pulse),
        .rx_header_error(rx_header_error),
        .rx_protocol_error(rx_protocol_error),
        .rx_frame_overflow_any(rx_frame_overflow_any),
        .rx_crc_error_any(rx_crc_error_any),
        .rx_overrun_error_any(rx_overrun_error_any),
        .lane_tx_busy_dbg(lane_tx_busy_dbg),
        .lane_tx_load_pulse_dbg(lane_tx_load_pulse_dbg),
        .lane_rx_frame_pulse_dbg(lane_rx_frame_pulse_dbg),
        .lane_rx_crc_error_dbg(lane_rx_crc_error_dbg),
        .lane_rx_error_dbg(lane_rx_error_dbg),
        .lane_rx_debug_status_dbg(lane_rx_debug_status_dbg),
        .tx_frag_pending_dbg(tx_frag_pending_dbg),
        .tx_frag_inflight_dbg(tx_frag_inflight_dbg),
        .tx_frag_acked_dbg(tx_frag_acked_dbg),
        .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg),
        .debug_status(stream_debug)
      );
    end
  endgenerate
endmodule
