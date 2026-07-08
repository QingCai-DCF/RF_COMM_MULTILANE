import ir_protocol_pkg::*;

module ir_stream_array_top #(
  parameter int LANE_COUNT                = 4,
  parameter int NODE_ID                   = 0,
  parameter int MAX_PACKET_BYTES          = 256,
  parameter int FRAGMENT_BYTES            = 64,
  parameter int MAX_RETRY                 = 4,
  parameter int CNT_CHIP_MAX              = 7,
  parameter int CNT_PREAMBLE              = 16,
  parameter int EOF_SILENCE_SYMS          = 3,
  parameter int RX_DATA_PHASE_DELAY_CYCLES = 0,
  parameter int RX_DETECT_START_CYCLES    = 0,
  parameter int RX_DETECT_END_CYCLES      = (CNT_CHIP_MAX >= 15) ? 10 : ((CNT_CHIP_MAX >= 7) ? (CNT_CHIP_MAX - 2) : CNT_CHIP_MAX),
  parameter int RX_PREAMBLE_REALIGN_EDGE  = 0,
  parameter int RX_SELF_BLANK_CYCLES      = (CNT_CHIP_MAX >= 15) ? 8 : ((CNT_CHIP_MAX >= 7) ? 4 : 1),
  parameter int FORCE_SD_SHUTDOWN         = 0,
  parameter logic [LANE_COUNT-1:0] ACK_LANE_MASK = {LANE_COUNT{1'b1}},
  parameter int TX_REQUIRE_ACK            = 1,
  parameter int FRAG_TIMEOUT_CYCLES       = 50000,
  parameter int TX_TO_RX_GUARD_CYCLES     = 2048,
  parameter int BACKOFF_SLOT_CYCLES       = 1024,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = 200000,
  parameter int MAX_FRAGS                 = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int MAX_FRAME_BYTES           = (IRP_DATA_HDR_BYTES + FRAGMENT_BYTES)
)(
  input  logic                         clk_phy,
  input  logic                         rst_n,
  input  logic                         enable,
  input  logic [15:0]                  session_id,
  input  logic [LANE_COUNT-1:0]        lane_enable_mask,
  input  logic [LANE_COUNT-1:0]        rx_lane_enable_mask,

  input  logic [7:0]                   s_axis_tx_tdata,
  input  logic                         s_axis_tx_tvalid,
  output logic                         s_axis_tx_tready,
  input  logic                         s_axis_tx_tlast,

  output logic [7:0]                   m_axis_rx_tdata,
  output logic                         m_axis_rx_tvalid,
  input  logic                         m_axis_rx_tready,
  output logic                         m_axis_rx_tlast,

  output logic [LANE_COUNT-1:0]        ir_tx_out,
  input  logic [LANE_COUNT-1:0]        ir_rx_in,
  output logic [LANE_COUNT-1:0]        ir_sd,
  output logic [LANE_COUNT-1:0]        ir_mode_out,

  output logic                         tx_packet_active,
  output logic                         tx_packet_loading,
  output logic                         tx_done_pulse,
  output logic                         tx_error_overflow,
  output logic                         tx_error_retry_exhausted,
  output logic                         rx_ctx_valid,
  output logic                         rx_ctx_complete,
  output logic                         rx_done_pulse,
  output logic                         rx_header_error,
  output logic                         rx_protocol_error,
  output logic                         rx_frame_overflow_any,
  output logic                         rx_crc_error_any,
  output logic                         rx_overrun_error_any,
  output logic [LANE_COUNT-1:0]        lane_tx_busy_dbg,
  output logic [LANE_COUNT-1:0]        lane_tx_load_pulse_dbg,
  output logic [LANE_COUNT-1:0]        lane_rx_frame_pulse_dbg,
  output logic [LANE_COUNT-1:0]        lane_rx_crc_error_dbg,
  output logic [LANE_COUNT-1:0]        lane_rx_error_dbg,
  output logic [32*LANE_COUNT-1:0]     lane_rx_debug_status_dbg,
  output logic [MAX_FRAGS-1:0]         tx_frag_pending_dbg,
  output logic [MAX_FRAGS-1:0]         tx_frag_inflight_dbg,
  output logic [MAX_FRAGS-1:0]         tx_frag_acked_dbg,
  output logic [MAX_FRAGS-1:0]         rx_recv_bitmap_dbg,
  output logic [31:0]                  debug_status
);
  localparam int LANE_W       = (LANE_COUNT <= 1) ? 1 : $clog2(LANE_COUNT);
  localparam int TX_LEN_W     = (MAX_PACKET_BYTES <= 1) ? 1 : $clog2(MAX_PACKET_BYTES + 1);
  localparam int FRAG_W       = (MAX_FRAGS <= 1) ? 1 : $clog2(MAX_FRAGS);
  localparam int FRAME_IDX_W  = (MAX_FRAME_BYTES <= 1) ? 1 : $clog2(MAX_FRAME_BYTES + 1);
  localparam int ACK_BITMAP_BYTES = (MAX_FRAGS + 7) / 8;
  localparam int ACK_FRAME_BYTES  = IRP_ACK_HDR_BYTES + ACK_BITMAP_BYTES;
  localparam int TX_CNT_PREAMBLE  = CNT_PREAMBLE + 96;

  typedef enum logic [3:0] {
    TX_IDLE,
    TX_COLLECT,
    TX_DROP,
    TX_WAIT_CH,
    TX_BACKOFF,
    TX_SEND_HDR,
    TX_SEND_PAYLOAD,
    TX_WAIT_ACK,
    TX_ACK_WAIT_CH,
    TX_SEND_ACK_HDR,
    TX_SEND_ACK_BITMAP
  } tx_state_t;

  typedef enum logic [2:0] {
    RX_IDLE,
    RX_HEADER,
    RX_PAYLOAD,
    RX_ACK_BITMAP,
    RX_DROP
  } rx_parse_state_t;

  tx_state_t tx_state;
  rx_parse_state_t rx_parse_state;

  logic [7:0] tx_pkt_buf [0:MAX_PACKET_BYTES-1];
  logic [7:0] rx_pkt_buf [0:MAX_PACKET_BYTES-1];
  logic [7:0] hdr_buf [0:IRP_DATA_HDR_BYTES-1];

  logic [TX_LEN_W-1:0] tx_wr_ptr;
  logic [15:0] tx_pkt_len;
  logic [15:0] tx_seq;
  logic [15:0] tx_seq_next;
  logic [FRAG_W-1:0] tx_frag_idx;
  logic [7:0] tx_frag_count;
  logic [7:0] tx_payload_len;
  logic [15:0] tx_payload_offset;
  logic [FRAME_IDX_W-1:0] tx_hdr_idx;
  logic [15:0] tx_payload_idx;
  logic [31:0] tx_ack_timeout;
  logic [7:0] tx_retry_count;
  logic [31:0] tx_backoff_cnt;
  logic [LANE_W-1:0] tx_lane_rr;
  logic [LANE_W-1:0] tx_active_lane;
  logic [MAX_FRAGS-1:0] tx_acked_bitmap;
  logic [MAX_FRAGS-1:0] tx_pending_bitmap;
  logic [MAX_FRAGS-1:0] tx_inflight_bitmap;

  logic ack_pending;
  logic [15:0] ack_session;
  logic [15:0] ack_seq;
  logic [7:0] ack_frag_count;
  logic [MAX_FRAGS-1:0] ack_bitmap;
  logic ack_complete;
  logic [LANE_W-1:0] ack_lane;
  logic [FRAME_IDX_W-1:0] ack_hdr_idx;
  logic [$clog2(ACK_BITMAP_BYTES+1)-1:0] ack_bitmap_idx;

  logic [15:0] rx_ctx_seq;
  logic [15:0] rx_ctx_total_len;
  logic [7:0] rx_ctx_frag_count;
  logic [MAX_FRAGS-1:0] rx_bitmap;
  logic [31:0] rx_ctx_timeout;
  logic rx_output_active;
  logic [15:0] rx_out_idx;

  logic [7:0] parse_header_len;
  logic [7:0] parse_hdr_idx;
  logic [7:0] parse_payload_len;
  logic [15:0] parse_total_len;
  logic [7:0] parse_frag_idx;
  logic [7:0] parse_frag_count;
  logic [15:0] parse_seq;
  logic [15:0] parse_session;
  logic [15:0] parse_payload_idx;
  logic [15:0] parse_payload_offset;
  logic [MAX_FRAGS-1:0] parse_ack_bitmap;
  logic [$clog2(ACK_BITMAP_BYTES+1)-1:0] parse_ack_idx;
  logic [7:0] parse_ack_bitmap_bytes;
  logic [15:0] parse_hdr_crc;
  logic parse_ack_complete;
  logic parse_is_ack;
  logic parse_is_data;
  logic [LANE_W-1:0] parse_lane;

  logic ack_rx_valid;
  logic [15:0] ack_rx_seq;
  logic [MAX_FRAGS-1:0] ack_rx_bitmap;
  logic ack_rx_complete;
  logic rx_payload_last_handshake;
  logic tx_current_frag_acked_now;
  logic tx_current_frag_acked_seen;

  logic [LANE_COUNT-1:0] lane_tx_axis_tvalid;
  logic [LANE_COUNT-1:0] lane_tx_axis_tready;
  logic [LANE_COUNT-1:0] lane_tx_axis_tlast;
  logic [7:0] lane_tx_axis_tdata [0:LANE_COUNT-1];
  logic [LANE_COUNT-1:0] lane_tx_busy;
  logic [LANE_COUNT-1:0] lane_rx_axis_tvalid;
  logic [LANE_COUNT-1:0] lane_rx_axis_tready;
  logic [LANE_COUNT-1:0] lane_rx_axis_tlast;
  logic [7:0] lane_rx_axis_tdata [0:LANE_COUNT-1];
  logic [LANE_COUNT-1:0] lane_rx_active;
  logic [LANE_COUNT-1:0] lane_rx_crc_error;
  logic [LANE_COUNT-1:0] lane_rx_overrun_error;
  logic [31:0] lane_rx_debug [0:LANE_COUNT-1];

  logic rx_mux_locked;
  logic [LANE_W-1:0] rx_mux_lane;
  logic rx_mux_tvalid;
  logic rx_mux_tready;
  logic rx_mux_tlast;
  logic [7:0] rx_mux_tdata;
  logic [LANE_W-1:0] rx_mux_lane_id;

  logic selected_tx_ready;
  logic selected_tx_valid;
  logic selected_tx_last;
  logic [7:0] selected_tx_data;
  logic selected_tx_first_byte;
  logic any_tx_busy;
  logic any_rx_active;
  logic channel_idle;
  logic [31:0] rx_to_tx_guard;

  logic [7:0] tx_frag_idx_byte;

  assign tx_frag_idx_byte = tx_frag_idx;

  initial begin
    if (LANE_COUNT < 1) $error("LANE_COUNT must be at least 1");
    if (MAX_FRAGS > 32) $error("ir_stream_array_top currently supports MAX_FRAGS <= 32");
    if (FRAGMENT_BYTES > 255) $error("FRAGMENT_BYTES must fit protocol payload_len field");
    if (MAX_FRAME_BYTES < (IRP_DATA_HDR_BYTES + FRAGMENT_BYTES)) $error("MAX_FRAME_BYTES too small");
  end

  function automatic logic [MAX_FRAGS-1:0] frag_mask(input logic [7:0] count);
    integer n;
    begin
      frag_mask = '0;
      for (n = 0; n < MAX_FRAGS; n = n + 1) begin
        if (n < count) frag_mask[n] = 1'b1;
      end
    end
  endfunction

  function automatic logic [7:0] ack_bitmap_bytes_fn(input logic [7:0] frag_count_f);
    begin
      ack_bitmap_bytes_fn = (frag_count_f + 7) / 8;
    end
  endfunction

  function automatic logic [15:0] data_hdr_crc_fn(
    input logic [15:0] session_f,
    input logic [15:0] seq_f,
    input logic [7:0] frag_idx_f,
    input logic [7:0] frag_count_f,
    input logic [15:0] total_len_f,
    input logic [7:0] payload_len_f
  );
    logic [15:0] crc_v;
    begin
      crc_v = 16'hFFFF;
      crc_v = crc16_ccitt_next_byte(IRP_SOF, crc_v);
      crc_v = crc16_ccitt_next_byte({IRP_VERSION, IRP_TYPE_DATA}, crc_v);
      crc_v = crc16_ccitt_next_byte(session_f[7:0], crc_v);
      crc_v = crc16_ccitt_next_byte(session_f[15:8], crc_v);
      crc_v = crc16_ccitt_next_byte(seq_f[7:0], crc_v);
      crc_v = crc16_ccitt_next_byte(seq_f[15:8], crc_v);
      crc_v = crc16_ccitt_next_byte(frag_idx_f, crc_v);
      crc_v = crc16_ccitt_next_byte(frag_count_f, crc_v);
      crc_v = crc16_ccitt_next_byte(total_len_f[7:0], crc_v);
      crc_v = crc16_ccitt_next_byte(total_len_f[15:8], crc_v);
      crc_v = crc16_ccitt_next_byte(payload_len_f, crc_v);
      crc_v = crc16_ccitt_next_byte(8'h00, crc_v);
      data_hdr_crc_fn = crc_v;
    end
  endfunction

  function automatic logic [15:0] ack_hdr_crc_fn(
    input logic [15:0] session_f,
    input logic [15:0] seq_f,
    input logic [7:0] frag_count_f,
    input logic [7:0] bitmap_bytes_f,
    input logic complete_f
  );
    logic [15:0] crc_v;
    begin
      crc_v = 16'hFFFF;
      crc_v = crc16_ccitt_next_byte(IRP_SOF, crc_v);
      crc_v = crc16_ccitt_next_byte({IRP_VERSION, IRP_TYPE_ACK}, crc_v);
      crc_v = crc16_ccitt_next_byte(session_f[7:0], crc_v);
      crc_v = crc16_ccitt_next_byte(session_f[15:8], crc_v);
      crc_v = crc16_ccitt_next_byte(seq_f[7:0], crc_v);
      crc_v = crc16_ccitt_next_byte(seq_f[15:8], crc_v);
      crc_v = crc16_ccitt_next_byte(frag_count_f, crc_v);
      crc_v = crc16_ccitt_next_byte(bitmap_bytes_f, crc_v);
      crc_v = crc16_ccitt_next_byte({7'd0, complete_f}, crc_v);
      crc_v = crc16_ccitt_next_byte(8'h00, crc_v);
      ack_hdr_crc_fn = crc_v;
    end
  endfunction

  function automatic logic [7:0] data_header_byte_fn(input logic [3:0] idx);
    logic [15:0] crc_v;
    begin
      crc_v = data_hdr_crc_fn(session_id, tx_seq, tx_frag_idx_byte, tx_frag_count, tx_pkt_len, tx_payload_len);
      case (idx)
        4'd0:  data_header_byte_fn = IRP_SOF;
        4'd1:  data_header_byte_fn = {IRP_VERSION, IRP_TYPE_DATA};
        4'd2:  data_header_byte_fn = session_id[7:0];
        4'd3:  data_header_byte_fn = session_id[15:8];
        4'd4:  data_header_byte_fn = tx_seq[7:0];
        4'd5:  data_header_byte_fn = tx_seq[15:8];
        4'd6:  data_header_byte_fn = tx_frag_idx_byte;
        4'd7:  data_header_byte_fn = tx_frag_count;
        4'd8:  data_header_byte_fn = tx_pkt_len[7:0];
        4'd9:  data_header_byte_fn = tx_pkt_len[15:8];
        4'd10: data_header_byte_fn = tx_payload_len;
        4'd11: data_header_byte_fn = 8'h00;
        4'd12: data_header_byte_fn = crc_v[7:0];
        default: data_header_byte_fn = crc_v[15:8];
      endcase
    end
  endfunction

  function automatic logic [7:0] ack_header_byte_fn(input logic [3:0] idx);
    logic [15:0] crc_v;
    logic [7:0] bitmap_bytes_v;
    begin
      bitmap_bytes_v = ack_bitmap_bytes_fn(ack_frag_count);
      crc_v = ack_hdr_crc_fn(ack_session, ack_seq, ack_frag_count, bitmap_bytes_v, ack_complete);
      case (idx)
        4'd0:  ack_header_byte_fn = IRP_SOF;
        4'd1:  ack_header_byte_fn = {IRP_VERSION, IRP_TYPE_ACK};
        4'd2:  ack_header_byte_fn = ack_session[7:0];
        4'd3:  ack_header_byte_fn = ack_session[15:8];
        4'd4:  ack_header_byte_fn = ack_seq[7:0];
        4'd5:  ack_header_byte_fn = ack_seq[15:8];
        4'd6:  ack_header_byte_fn = ack_frag_count;
        4'd7:  ack_header_byte_fn = bitmap_bytes_v;
        4'd8:  ack_header_byte_fn = {7'd0, ack_complete};
        4'd9:  ack_header_byte_fn = 8'h00;
        4'd10: ack_header_byte_fn = crc_v[7:0];
        default: ack_header_byte_fn = crc_v[15:8];
      endcase
    end
  endfunction

  function automatic logic [7:0] ack_bitmap_byte_fn(
    input logic [MAX_FRAGS-1:0] bitmap_f,
    input logic [7:0] byte_idx_f
  );
    integer b;
    begin
      ack_bitmap_byte_fn = 8'h00;
      for (b = 0; b < 8; b = b + 1) begin
        if ((byte_idx_f * 8 + b) < MAX_FRAGS) begin
          ack_bitmap_byte_fn[b] = bitmap_f[byte_idx_f * 8 + b];
        end
      end
    end
  endfunction

  function automatic logic find_enabled_lane(
    input  logic [LANE_W-1:0] start_lane,
    output logic [LANE_W-1:0] lane_o
  );
    integer l;
    integer cand;
    begin
      find_enabled_lane = 1'b0;
      lane_o = '0;
      for (l = 0; l < LANE_COUNT; l = l + 1) begin
        cand = start_lane + l;
        if (cand >= LANE_COUNT) cand = cand - LANE_COUNT;
        if (!find_enabled_lane && lane_enable_mask[cand]) begin
          lane_o = cand[LANE_W-1:0];
          find_enabled_lane = 1'b1;
        end
      end
    end
  endfunction

  function automatic logic find_ack_lane(
    input  logic [LANE_W-1:0] start_lane,
    output logic [LANE_W-1:0] lane_o
  );
    integer l;
    integer cand;
    begin
      find_ack_lane = 1'b0;
      lane_o = '0;
      for (l = 0; l < LANE_COUNT; l = l + 1) begin
        cand = start_lane + l;
        if (cand >= LANE_COUNT) cand = cand - LANE_COUNT;
        if (!find_ack_lane && lane_enable_mask[cand] && ACK_LANE_MASK[cand]) begin
          lane_o = cand[LANE_W-1:0];
          find_ack_lane = 1'b1;
        end
      end
    end
  endfunction

  genvar gi;
  generate
    for (gi = 0; gi < LANE_COUNT; gi = gi + 1) begin : g_lane
      localparam int BLANK_W = (RX_SELF_BLANK_CYCLES <= 1) ? 1 : $clog2(RX_SELF_BLANK_CYCLES + 1);
      localparam logic [BLANK_W-1:0] RX_SELF_BLANK_RELOAD = RX_SELF_BLANK_CYCLES[BLANK_W-1:0];
      logic [BLANK_W-1:0] rx_self_blank_cnt;
      logic rx_masked_in;

      assign ir_sd[gi]       = (FORCE_SD_SHUTDOWN != 0) ? 1'b1 : ~(enable && (lane_enable_mask[gi] || rx_lane_enable_mask[gi]));
      assign ir_mode_out[gi] = 1'b1;
      assign rx_masked_in    = (lane_tx_busy[gi] || ir_tx_out[gi] || (rx_self_blank_cnt != '0)) ? 1'b1 : ir_rx_in[gi];

      always_ff @(posedge clk_phy) begin
        if (!rst_n || !enable || (RX_SELF_BLANK_CYCLES == 0)) begin
          rx_self_blank_cnt <= '0;
        end else if (ir_tx_out[gi]) begin
          rx_self_blank_cnt <= RX_SELF_BLANK_RELOAD;
        end else if (rx_self_blank_cnt != '0) begin
          rx_self_blank_cnt <= rx_self_blank_cnt - 1'b1;
        end
      end

      ir_tx_4ppm_frame #(
        .CNT_CHIP_MAX    (CNT_CHIP_MAX),
        .CNT_PREAMBLE    (TX_CNT_PREAMBLE),
        .CNT_EOF_SILENCE (EOF_SILENCE_SYMS + 4)
      ) u_tx (
        .clk           (clk_phy),
        .rst_n         (rst_n),
        .enable        (enable && lane_enable_mask[gi]),
        .s_axis_tdata  (lane_tx_axis_tdata[gi]),
        .s_axis_tvalid (lane_tx_axis_tvalid[gi]),
        .s_axis_tready (lane_tx_axis_tready[gi]),
        .s_axis_tlast  (lane_tx_axis_tlast[gi]),
        .tx_busy       (lane_tx_busy[gi]),
        .ir_tx_out     (ir_tx_out[gi])
      );

      ir_rx_4ppm_frame #(
        .MAX_FRAME_BYTES  (MAX_FRAME_BYTES),
        .CNT_CHIP_MAX     (CNT_CHIP_MAX),
        .PREAMBLE_SYMS    (CNT_PREAMBLE),
        .EOF_SILENCE_SYMS (EOF_SILENCE_SYMS),
        .DATA_PHASE_DELAY_CYCLES(RX_DATA_PHASE_DELAY_CYCLES),
        .DETECT_START_CYCLES(RX_DETECT_START_CYCLES),
        .DETECT_END_CYCLES(RX_DETECT_END_CYCLES),
        .PREAMBLE_REALIGN_EDGE(RX_PREAMBLE_REALIGN_EDGE),
        .PREAMBLE_WAIT_FOR_DATA_SYMBOL(1)
      ) u_rx (
        .clk            (clk_phy),
        .rst_n          (rst_n),
        .enable         (enable && rx_lane_enable_mask[gi]),
        .ir_rx_in       (rx_masked_in),
        .m_axis_tdata   (lane_rx_axis_tdata[gi]),
        .m_axis_tvalid  (lane_rx_axis_tvalid[gi]),
        .m_axis_tready  (lane_rx_axis_tready[gi]),
        .m_axis_tlast   (lane_rx_axis_tlast[gi]),
        .rx_active      (lane_rx_active[gi]),
        .crc_error      (lane_rx_crc_error[gi]),
        .overrun_error  (lane_rx_overrun_error[gi]),
        .debug_status   (lane_rx_debug[gi])
      );

      assign lane_rx_debug_status_dbg[32*gi +: 32] = lane_rx_debug[gi];
    end
  endgenerate

  assign any_tx_busy = |lane_tx_busy;
  assign any_rx_active = |lane_rx_active;
  assign channel_idle = !any_tx_busy && !any_rx_active && (rx_to_tx_guard == 32'h0000_0000);

  always_comb begin
    selected_tx_valid = 1'b0;
    selected_tx_last  = 1'b0;
    selected_tx_data  = 8'h00;
    selected_tx_first_byte = 1'b0;

    if (tx_state == TX_SEND_HDR) begin
      selected_tx_valid = 1'b1;
      selected_tx_data  = data_header_byte_fn(tx_hdr_idx[3:0]);
      selected_tx_last  = 1'b0;
      selected_tx_first_byte = (tx_hdr_idx == '0);
    end else if (tx_state == TX_SEND_PAYLOAD) begin
      selected_tx_valid = 1'b1;
      selected_tx_data  = tx_pkt_buf[tx_payload_offset + tx_payload_idx];
      selected_tx_last  = (tx_payload_idx == tx_payload_len - 1'b1);
    end else if (tx_state == TX_SEND_ACK_HDR) begin
      selected_tx_valid = 1'b1;
      selected_tx_data  = ack_header_byte_fn(ack_hdr_idx[3:0]);
      selected_tx_last  = (ack_bitmap_bytes_fn(ack_frag_count) == 0) &&
                          (ack_hdr_idx == IRP_ACK_HDR_BYTES - 1);
      selected_tx_first_byte = (ack_hdr_idx == '0);
    end else if (tx_state == TX_SEND_ACK_BITMAP) begin
      selected_tx_valid = 1'b1;
      selected_tx_data  = ack_bitmap_byte_fn(ack_bitmap, ack_bitmap_idx);
      selected_tx_last  = (ack_bitmap_idx == ack_bitmap_bytes_fn(ack_frag_count) - 1'b1);
    end
  end

  always_comb begin
    integer ai;
    for (ai = 0; ai < LANE_COUNT; ai = ai + 1) begin
      lane_tx_axis_tvalid[ai] = 1'b0;
      lane_tx_axis_tlast[ai]  = 1'b0;
      lane_tx_axis_tdata[ai]  = 8'h00;
    end
    lane_tx_load_pulse_dbg = '0;
    if (selected_tx_valid) begin
      lane_tx_axis_tvalid[tx_active_lane] = selected_tx_valid;
      lane_tx_axis_tlast[tx_active_lane]  = selected_tx_last;
      lane_tx_axis_tdata[tx_active_lane]  = selected_tx_data;
      lane_tx_load_pulse_dbg[tx_active_lane] = selected_tx_valid && selected_tx_ready && selected_tx_first_byte;
    end
  end

  assign selected_tx_ready = lane_tx_axis_tready[tx_active_lane];

  always_comb begin
    integer mi;
    for (mi = 0; mi < LANE_COUNT; mi = mi + 1) lane_rx_axis_tready[mi] = 1'b0;
    rx_mux_tvalid  = 1'b0;
    rx_mux_tdata   = 8'h00;
    rx_mux_tlast   = 1'b0;
    rx_mux_lane_id = rx_mux_lane;

    if (rx_mux_locked) begin
      rx_mux_tvalid = lane_rx_axis_tvalid[rx_mux_lane];
      rx_mux_tdata  = lane_rx_axis_tdata[rx_mux_lane];
      rx_mux_tlast  = lane_rx_axis_tlast[rx_mux_lane];
      lane_rx_axis_tready[rx_mux_lane] = rx_mux_tready;
    end else begin
      for (mi = 0; mi < LANE_COUNT; mi = mi + 1) begin
        if (!rx_mux_tvalid && lane_rx_axis_tvalid[mi]) begin
          rx_mux_tvalid  = 1'b1;
          rx_mux_tdata   = lane_rx_axis_tdata[mi];
          rx_mux_tlast   = lane_rx_axis_tlast[mi];
          rx_mux_lane_id = mi[LANE_W-1:0];
          lane_rx_axis_tready[mi] = rx_mux_tready;
        end
      end
    end
  end

  assign rx_mux_tready = enable && (rx_parse_state != RX_DROP || rx_mux_tvalid);

  assign rx_payload_last_handshake = (rx_parse_state == RX_PAYLOAD) && rx_mux_tvalid && rx_mux_tready && rx_mux_tlast;
  assign tx_current_frag_acked_now = ack_rx_valid && (ack_rx_seq == tx_seq) && ack_rx_bitmap[tx_frag_idx];
  assign tx_current_frag_acked_seen = tx_current_frag_acked_now || tx_acked_bitmap[tx_frag_idx];

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      rx_mux_locked <= 1'b0;
      rx_mux_lane   <= '0;
    end else if (!enable) begin
      rx_mux_locked <= 1'b0;
      rx_mux_lane   <= '0;
    end else if (rx_mux_tvalid && rx_mux_tready) begin
      if (!rx_mux_locked && !rx_mux_tlast) begin
        rx_mux_locked <= 1'b1;
        rx_mux_lane   <= rx_mux_lane_id;
      end else if (rx_mux_tlast) begin
        rx_mux_locked <= 1'b0;
      end
    end
  end

  assign s_axis_tx_tready = enable &&
                            (((tx_state == TX_IDLE) &&
                              !tx_packet_active && !tx_error_retry_exhausted) ||
                             (tx_state == TX_COLLECT) ||
                             (tx_state == TX_DROP));

  always_ff @(posedge clk_phy) begin
    integer next_len_v;
    integer frag_len_v;
    logic [LANE_W-1:0] found_ack_lane_v;
    logic [LANE_W-1:0] found_tx_lane_v;
    logic found_ack_lane_valid_v;
    logic found_tx_lane_valid_v;
    if (!rst_n) begin
      tx_state                 <= TX_IDLE;
      tx_wr_ptr                <= '0;
      tx_pkt_len               <= 16'h0000;
      tx_seq                   <= 16'h0000;
      tx_seq_next              <= 16'h0001;
      tx_frag_idx              <= '0;
      tx_frag_count            <= 8'h00;
      tx_payload_len           <= 8'h00;
      tx_payload_offset        <= 16'h0000;
      tx_hdr_idx               <= '0;
      tx_payload_idx           <= 16'h0000;
      tx_ack_timeout           <= 32'h0000_0000;
      tx_retry_count           <= 8'h00;
      tx_backoff_cnt           <= 32'h0000_0000;
      tx_lane_rr               <= '0;
      tx_active_lane           <= '0;
      tx_acked_bitmap          <= '0;
      tx_pending_bitmap        <= '0;
      tx_inflight_bitmap       <= '0;
      tx_packet_active         <= 1'b0;
      tx_packet_loading        <= 1'b0;
      tx_done_pulse            <= 1'b0;
      tx_error_overflow        <= 1'b0;
      tx_error_retry_exhausted <= 1'b0;
      ack_pending              <= 1'b0;
      ack_session              <= 16'h0000;
      ack_seq                  <= 16'h0000;
      ack_frag_count           <= 8'h00;
      ack_bitmap               <= '0;
      ack_complete             <= 1'b0;
      ack_lane                 <= '0;
      ack_hdr_idx              <= '0;
      ack_bitmap_idx           <= '0;
      rx_to_tx_guard           <= 32'h0000_0000;
    end else begin
      tx_done_pulse     <= 1'b0;
      tx_error_overflow <= 1'b0;

      if (!enable) begin
        tx_state                 <= TX_IDLE;
        tx_wr_ptr                <= '0;
        tx_packet_active         <= 1'b0;
        tx_packet_loading        <= 1'b0;
        tx_error_retry_exhausted <= 1'b0;
        ack_pending              <= 1'b0;
        rx_to_tx_guard           <= 32'h0000_0000;
      end else begin
        if (rx_to_tx_guard != 32'h0000_0000) begin
          rx_to_tx_guard <= rx_to_tx_guard - 1'b1;
        end

        if (rx_done_pulse || ack_rx_valid || rx_payload_last_handshake) begin
          rx_to_tx_guard <= TX_TO_RX_GUARD_CYCLES[31:0];
        end

        if (ack_rx_valid && tx_packet_active && (ack_rx_seq == tx_seq)) begin
          tx_acked_bitmap <= tx_acked_bitmap | ack_rx_bitmap;
          tx_inflight_bitmap <= tx_inflight_bitmap & ~ack_rx_bitmap;
          tx_pending_bitmap <= tx_pending_bitmap & ~ack_rx_bitmap;
        end

        if (rx_done_pulse || rx_payload_last_handshake) begin
          found_ack_lane_valid_v = find_ack_lane(parse_lane, found_ack_lane_v);
          if (found_ack_lane_valid_v) begin
            ack_pending    <= 1'b1;
            ack_session    <= session_id;
            ack_seq        <= parse_seq;
            ack_frag_count <= parse_frag_count;
            ack_bitmap     <= rx_bitmap | (parse_frag_idx < MAX_FRAGS ? ({{(MAX_FRAGS-1){1'b0}}, 1'b1} << parse_frag_idx) : '0);
            ack_complete   <= ((rx_bitmap | ({{(MAX_FRAGS-1){1'b0}}, 1'b1} << parse_frag_idx)) == frag_mask(parse_frag_count));
            ack_lane       <= found_ack_lane_v;
          end else begin
            ack_pending    <= 1'b0;
          end
        end

        case (tx_state)
          TX_IDLE: begin
            tx_packet_active  <= 1'b0;
            tx_packet_loading <= 1'b0;
            tx_wr_ptr         <= '0;
            tx_inflight_bitmap <= '0;
            if (ack_pending) begin
              tx_state <= TX_ACK_WAIT_CH;
            end else if (s_axis_tx_tvalid && s_axis_tx_tready) begin
              tx_packet_active  <= 1'b1;
              tx_packet_loading <= 1'b1;
              tx_pkt_buf[0]     <= s_axis_tx_tdata;
              tx_wr_ptr         <= 1;
              if (s_axis_tx_tlast) begin
                tx_pkt_len        <= 16'd1;
                tx_seq            <= tx_seq_next;
                tx_seq_next       <= tx_seq_next + 1'b1;
                tx_frag_idx       <= '0;
                tx_frag_count     <= 8'd1;
                tx_pending_bitmap <= {{(MAX_FRAGS-1){1'b0}}, 1'b1};
                tx_acked_bitmap   <= '0;
                tx_packet_loading <= 1'b0;
                tx_state          <= TX_WAIT_CH;
              end else begin
                tx_state <= TX_COLLECT;
              end
            end
          end

          TX_COLLECT: begin
            if (s_axis_tx_tvalid && s_axis_tx_tready) begin
              if (tx_wr_ptr < MAX_PACKET_BYTES) begin
                tx_pkt_buf[tx_wr_ptr] <= s_axis_tx_tdata;
                next_len_v = tx_wr_ptr + 1;
                tx_wr_ptr <= tx_wr_ptr + 1'b1;
                if (s_axis_tx_tlast) begin
                  tx_pkt_len        <= next_len_v[15:0];
                  tx_seq            <= tx_seq_next;
                  tx_seq_next       <= tx_seq_next + 1'b1;
                  tx_frag_idx       <= '0;
                  tx_frag_count     <= ((next_len_v + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES);
                  tx_pending_bitmap <= frag_mask(((next_len_v + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES));
                  tx_acked_bitmap   <= '0;
                  tx_packet_loading <= 1'b0;
                  tx_state          <= TX_WAIT_CH;
                end
              end else begin
                tx_error_overflow <= 1'b1;
                tx_state          <= TX_DROP;
              end
            end
          end

          TX_DROP: begin
            if (s_axis_tx_tvalid && s_axis_tx_tready && s_axis_tx_tlast) begin
              tx_packet_active  <= 1'b0;
              tx_packet_loading <= 1'b0;
              tx_state          <= TX_IDLE;
            end
          end

          TX_ACK_WAIT_CH: begin
            tx_active_lane <= ack_lane;
            if (!ack_pending) begin
              tx_state <= TX_IDLE;
            end else if (!(lane_enable_mask[ack_lane] && ACK_LANE_MASK[ack_lane])) begin
              ack_pending <= 1'b0;
              tx_state    <= tx_packet_active ? TX_WAIT_CH : TX_IDLE;
            end else if (rx_done_pulse || ack_rx_valid || rx_payload_last_handshake) begin
              tx_state <= TX_ACK_WAIT_CH;
            end else if (channel_idle) begin
              ack_hdr_idx    <= '0;
              ack_bitmap_idx <= '0;
              tx_state       <= TX_SEND_ACK_HDR;
            end
          end

          TX_SEND_ACK_HDR: begin
            if (selected_tx_valid && selected_tx_ready) begin
              if (ack_hdr_idx == IRP_ACK_HDR_BYTES - 1) begin
                if (ack_bitmap_bytes_fn(ack_frag_count) == 0) begin
                  ack_pending <= 1'b0;
                  tx_state    <= tx_packet_active ? TX_WAIT_CH : TX_IDLE;
                end else begin
                  ack_bitmap_idx <= '0;
                  tx_state       <= TX_SEND_ACK_BITMAP;
                end
              end else begin
                ack_hdr_idx <= ack_hdr_idx + 1'b1;
              end
            end
          end

          TX_SEND_ACK_BITMAP: begin
            if (selected_tx_valid && selected_tx_ready) begin
              if (ack_bitmap_idx == ack_bitmap_bytes_fn(ack_frag_count) - 1'b1) begin
                ack_pending <= 1'b0;
                tx_state    <= tx_packet_active ? TX_WAIT_CH : TX_IDLE;
              end else begin
                ack_bitmap_idx <= ack_bitmap_idx + 1'b1;
              end
            end
          end

          TX_WAIT_CH: begin
            if (ack_pending) begin
              tx_state <= TX_ACK_WAIT_CH;
            end else if (tx_packet_active && tx_current_frag_acked_seen) begin
              tx_retry_count <= 8'h00;
              if ((tx_frag_idx + 1) >= tx_frag_count) begin
                tx_packet_active <= 1'b0;
                tx_done_pulse    <= 1'b1;
                tx_state         <= TX_IDLE;
              end else begin
                tx_frag_idx <= tx_frag_idx + 1'b1;
                tx_state    <= TX_WAIT_CH;
              end
            end else if (!tx_packet_active) begin
              tx_state <= TX_IDLE;
            end else if (rx_done_pulse || ack_rx_valid || rx_payload_last_handshake) begin
              tx_state <= TX_WAIT_CH;
            end else if (channel_idle) begin
              found_tx_lane_valid_v = find_enabled_lane(tx_lane_rr, found_tx_lane_v);
              if (found_tx_lane_valid_v) begin
                tx_active_lane <= found_tx_lane_v;
                tx_backoff_cnt <= NODE_ID * BACKOFF_SLOT_CYCLES;
                tx_state       <= TX_BACKOFF;
              end else begin
                tx_error_retry_exhausted <= 1'b1;
                tx_packet_active         <= 1'b0;
                tx_inflight_bitmap       <= '0;
                tx_state                 <= TX_IDLE;
              end
            end
          end

          TX_BACKOFF: begin
            if (ack_pending) begin
              tx_state <= TX_ACK_WAIT_CH;
            end else if (tx_packet_active && tx_current_frag_acked_seen) begin
              tx_retry_count <= 8'h00;
              if ((tx_frag_idx + 1) >= tx_frag_count) begin
                tx_packet_active <= 1'b0;
                tx_done_pulse    <= 1'b1;
                tx_state         <= TX_IDLE;
              end else begin
                tx_frag_idx <= tx_frag_idx + 1'b1;
                tx_state    <= TX_WAIT_CH;
              end
            end else if (rx_done_pulse || ack_rx_valid || rx_payload_last_handshake) begin
              tx_state <= TX_WAIT_CH;
            end else if (!channel_idle) begin
              tx_state <= TX_WAIT_CH;
            end else if (tx_backoff_cnt != 32'h0000_0000) begin
              tx_backoff_cnt <= tx_backoff_cnt - 1'b1;
            end else if (!lane_enable_mask[tx_active_lane]) begin
              tx_state <= TX_WAIT_CH;
            end else begin
              tx_payload_offset <= tx_frag_idx * FRAGMENT_BYTES;
              frag_len_v = tx_pkt_len - (tx_frag_idx * FRAGMENT_BYTES);
              if (frag_len_v > FRAGMENT_BYTES) frag_len_v = FRAGMENT_BYTES;
              tx_payload_len    <= frag_len_v[7:0];
              tx_payload_idx    <= 16'h0000;
              tx_hdr_idx        <= '0;
              tx_retry_count    <= tx_retry_count;
              tx_state          <= TX_SEND_HDR;
            end
          end

          TX_SEND_HDR: begin
            if (selected_tx_valid && selected_tx_ready) begin
              if (tx_hdr_idx == IRP_DATA_HDR_BYTES - 1) begin
                tx_payload_idx <= 16'h0000;
                tx_state       <= TX_SEND_PAYLOAD;
              end else begin
                tx_hdr_idx <= tx_hdr_idx + 1'b1;
              end
            end
          end

          TX_SEND_PAYLOAD: begin
            if (selected_tx_valid && selected_tx_ready) begin
              if (tx_payload_idx == tx_payload_len - 1'b1) begin
                if (tx_active_lane == LANE_COUNT-1) tx_lane_rr <= '0;
                else                                tx_lane_rr <= tx_active_lane + 1'b1;
                if (TX_REQUIRE_ACK == 0) begin
                  tx_pending_bitmap[tx_frag_idx]  <= 1'b0;
                  tx_inflight_bitmap[tx_frag_idx] <= 1'b0;
                  tx_acked_bitmap[tx_frag_idx]    <= 1'b1;
                  tx_retry_count                  <= 8'h00;
                  if ((tx_frag_idx + 1) >= tx_frag_count) begin
                    tx_packet_active <= 1'b0;
                    tx_done_pulse    <= 1'b1;
                    tx_state         <= TX_IDLE;
                  end else begin
                    tx_frag_idx <= tx_frag_idx + 1'b1;
                    tx_state    <= TX_WAIT_CH;
                  end
                end else begin
                  tx_inflight_bitmap[tx_frag_idx] <= 1'b1;
                  tx_ack_timeout <= FRAG_TIMEOUT_CYCLES[31:0];
                  tx_state <= TX_WAIT_ACK;
                end
              end else begin
                tx_payload_idx <= tx_payload_idx + 1'b1;
              end
            end
          end

          TX_WAIT_ACK: begin
            if (ack_pending) begin
              tx_state <= TX_ACK_WAIT_CH;
            end else if (tx_current_frag_acked_seen) begin
              tx_retry_count <= 8'h00;
              if ((tx_frag_idx + 1) >= tx_frag_count) begin
                tx_packet_active <= 1'b0;
                tx_done_pulse    <= 1'b1;
                tx_state         <= TX_IDLE;
              end else begin
                tx_frag_idx <= tx_frag_idx + 1'b1;
                tx_state    <= TX_WAIT_CH;
              end
            end else if (tx_ack_timeout != 32'h0000_0000) begin
              tx_ack_timeout <= tx_ack_timeout - 1'b1;
            end else begin
              tx_inflight_bitmap[tx_frag_idx] <= 1'b0;
              if (tx_retry_count >= MAX_RETRY) begin
                tx_error_retry_exhausted <= 1'b1;
                tx_packet_active         <= 1'b0;
                tx_state                 <= TX_IDLE;
              end else begin
                tx_retry_count <= tx_retry_count + 1'b1;
                tx_state       <= TX_WAIT_CH;
              end
            end
          end

          default: tx_state <= TX_IDLE;
        endcase
      end
    end
  end

  always_ff @(posedge clk_phy) begin
    logic [7:0] vt_byte;
    logic [3:0] frame_type;
    logic [MAX_FRAGS-1:0] bit_v;
    logic [15:0] header_session_v;
    logic [15:0] header_seq_v;
    logic [7:0] header_frag_idx_v;
    logic [7:0] header_frag_count_v;
    logic [15:0] header_total_len_v;
    logic [7:0] header_payload_len_v;
    logic [15:0] header_payload_offset_v;
    logic [7:0] header_ack_bitmap_bytes_v;
    logic header_ack_complete_v;
    logic [7:0] expected_ack_bitmap_bytes_v;
    logic [7:0] active_header_len_v;
    logic active_is_data_v;
    integer bi;
    if (!rst_n) begin
      rx_parse_state     <= RX_IDLE;
      parse_header_len   <= 8'h00;
      parse_hdr_idx      <= 8'h00;
      parse_payload_len  <= 8'h00;
      parse_total_len    <= 16'h0000;
      parse_frag_idx     <= 8'h00;
      parse_frag_count   <= 8'h00;
      parse_seq          <= 16'h0000;
      parse_session      <= 16'h0000;
      parse_payload_idx  <= 16'h0000;
      parse_payload_offset <= 16'h0000;
      parse_ack_bitmap   <= '0;
      parse_ack_idx      <= '0;
      parse_ack_bitmap_bytes <= 8'h00;
      parse_hdr_crc      <= 16'hFFFF;
      parse_ack_complete <= 1'b0;
      parse_is_ack       <= 1'b0;
      parse_is_data      <= 1'b0;
      parse_lane         <= '0;
      rx_ctx_valid       <= 1'b0;
      rx_ctx_complete    <= 1'b0;
      rx_ctx_seq         <= 16'h0000;
      rx_ctx_total_len   <= 16'h0000;
      rx_ctx_frag_count  <= 8'h00;
      rx_bitmap          <= '0;
      rx_ctx_timeout     <= 32'h0000_0000;
      rx_output_active   <= 1'b0;
      rx_out_idx         <= 16'h0000;
      m_axis_rx_tdata    <= 8'h00;
      m_axis_rx_tvalid   <= 1'b0;
      m_axis_rx_tlast    <= 1'b0;
      rx_done_pulse      <= 1'b0;
      rx_header_error    <= 1'b0;
      rx_protocol_error  <= 1'b0;
      ack_rx_valid       <= 1'b0;
      ack_rx_seq         <= 16'h0000;
      ack_rx_bitmap      <= '0;
      ack_rx_complete    <= 1'b0;
    end else begin
      rx_done_pulse     <= 1'b0;
      rx_header_error   <= 1'b0;
      rx_protocol_error <= 1'b0;
      ack_rx_valid      <= 1'b0;

      if (!enable) begin
        rx_parse_state   <= RX_IDLE;
        rx_ctx_valid     <= 1'b0;
        rx_ctx_complete  <= 1'b0;
        rx_output_active <= 1'b0;
        m_axis_rx_tvalid <= 1'b0;
        m_axis_rx_tlast  <= 1'b0;
      end else begin
        if (rx_ctx_valid && !rx_ctx_complete && rx_ctx_timeout != 32'h0000_0000) begin
          rx_ctx_timeout <= rx_ctx_timeout - 1'b1;
        end else if (rx_ctx_valid && !rx_ctx_complete && rx_ctx_timeout == 32'h0000_0000) begin
          rx_ctx_valid <= 1'b0;
          rx_bitmap    <= '0;
        end

        if (rx_output_active && (!m_axis_rx_tvalid || m_axis_rx_tready)) begin
          if (rx_out_idx < rx_ctx_total_len) begin
            m_axis_rx_tdata  <= rx_pkt_buf[rx_out_idx];
            m_axis_rx_tvalid <= 1'b1;
            m_axis_rx_tlast  <= (rx_out_idx == rx_ctx_total_len - 1'b1);
            rx_out_idx       <= rx_out_idx + 1'b1;
          end else begin
            m_axis_rx_tvalid <= 1'b0;
            m_axis_rx_tlast  <= 1'b0;
            rx_output_active <= 1'b0;
            rx_ctx_complete  <= 1'b0;
          end
        end else if (!rx_output_active && m_axis_rx_tvalid && m_axis_rx_tready) begin
          m_axis_rx_tvalid <= 1'b0;
          m_axis_rx_tlast  <= 1'b0;
        end

        if (rx_mux_tvalid && rx_mux_tready) begin
          case (rx_parse_state)
            RX_IDLE: begin
              parse_lane    <= rx_mux_lane_id;
              parse_hdr_idx <= 8'h00;
              parse_header_len <= 8'h00;
              parse_is_ack  <= 1'b0;
              parse_is_data <= 1'b0;
              hdr_buf[0]    <= rx_mux_tdata;
              parse_hdr_crc <= crc16_ccitt_next_byte(rx_mux_tdata, 16'hFFFF);
              if (rx_mux_tdata != IRP_SOF) begin
                rx_header_error <= 1'b1;
                rx_parse_state  <= rx_mux_tlast ? RX_IDLE : RX_DROP;
              end else if (rx_mux_tlast) begin
                rx_header_error <= 1'b1;
                rx_parse_state  <= RX_IDLE;
              end else begin
                parse_hdr_idx   <= 8'd1;
                rx_parse_state  <= RX_HEADER;
              end
            end

            RX_HEADER: begin
              active_header_len_v = parse_header_len;
              active_is_data_v    = parse_is_data;
              hdr_buf[parse_hdr_idx] <= rx_mux_tdata;

              if (parse_hdr_idx == 8'd1) begin
                vt_byte = rx_mux_tdata;
                frame_type = vt_byte[3:0];
                if (vt_byte[7:4] != IRP_VERSION) begin
                  rx_header_error <= 1'b1;
                  rx_parse_state  <= rx_mux_tlast ? RX_IDLE : RX_DROP;
                end else if (frame_type == IRP_TYPE_DATA) begin
                  active_header_len_v = IRP_DATA_HDR_BYTES[7:0];
                  active_is_data_v    = 1'b1;
                  parse_header_len <= IRP_DATA_HDR_BYTES[7:0];
                  parse_is_data    <= 1'b1;
                  parse_is_ack     <= 1'b0;
                end else if (frame_type == IRP_TYPE_ACK) begin
                  active_header_len_v = IRP_ACK_HDR_BYTES[7:0];
                  active_is_data_v    = 1'b0;
                  parse_header_len <= IRP_ACK_HDR_BYTES[7:0];
                  parse_is_ack     <= 1'b1;
                  parse_is_data    <= 1'b0;
                end else begin
                  rx_header_error <= 1'b1;
                  rx_parse_state  <= rx_mux_tlast ? RX_IDLE : RX_DROP;
                end
              end

              if ((parse_hdr_idx == 8'd1) ||
                  ((active_header_len_v != 0) && (parse_hdr_idx < (active_header_len_v - 2)))) begin
                parse_hdr_crc <= crc16_ccitt_next_byte(rx_mux_tdata, parse_hdr_crc);
              end

              if ((active_header_len_v != 0) && ((parse_hdr_idx + 1) == active_header_len_v)) begin
                header_session_v = {hdr_buf[3], hdr_buf[2]};
                header_seq_v     = {hdr_buf[5], hdr_buf[4]};
                if (({rx_mux_tdata, hdr_buf[active_header_len_v-2]} != parse_hdr_crc) ||
                    (header_session_v != session_id)) begin
                  rx_header_error <= 1'b1;
                  rx_parse_state  <= rx_mux_tlast ? RX_IDLE : RX_DROP;
                end else if (active_is_data_v) begin
                  header_frag_idx_v       = hdr_buf[6];
                  header_frag_count_v     = hdr_buf[7];
                  header_total_len_v      = {hdr_buf[9], hdr_buf[8]};
                  header_payload_len_v    = hdr_buf[10];
                  header_payload_offset_v = hdr_buf[6] * FRAGMENT_BYTES;
                  parse_session           <= header_session_v;
                  parse_seq               <= header_seq_v;
                  parse_frag_idx          <= header_frag_idx_v;
                  parse_frag_count        <= header_frag_count_v;
                  parse_total_len         <= header_total_len_v;
                  parse_payload_len       <= header_payload_len_v;
                  parse_payload_idx       <= 16'h0000;
                  parse_payload_offset    <= header_payload_offset_v;

                  if ((header_frag_count_v == 0) || (header_frag_count_v > MAX_FRAGS) ||
                      (header_frag_idx_v >= header_frag_count_v) ||
                      (header_payload_len_v == 0) || (header_payload_len_v > FRAGMENT_BYTES) ||
                      (header_total_len_v == 0) || (header_total_len_v > MAX_PACKET_BYTES) ||
                      ((header_payload_offset_v + header_payload_len_v) > header_total_len_v) ||
                      rx_mux_tlast) begin
                    rx_protocol_error <= 1'b1;
                    rx_parse_state    <= rx_mux_tlast ? RX_IDLE : RX_DROP;
                  end else begin
                    if (!rx_ctx_valid || (rx_ctx_seq != header_seq_v)) begin
                      rx_ctx_valid      <= 1'b1;
                      rx_ctx_complete   <= 1'b0;
                      rx_ctx_seq        <= header_seq_v;
                      rx_ctx_total_len  <= header_total_len_v;
                      rx_ctx_frag_count <= header_frag_count_v;
                      rx_bitmap         <= '0;
                    end
                    rx_ctx_timeout <= REASSEMBLY_TIMEOUT_CYCLES[31:0];
                    rx_parse_state <= RX_PAYLOAD;
                  end
                end else begin
                  header_frag_count_v        = hdr_buf[6];
                  header_ack_bitmap_bytes_v  = hdr_buf[7];
                  header_ack_complete_v      = hdr_buf[8][0];
                  expected_ack_bitmap_bytes_v = ack_bitmap_bytes_fn(header_frag_count_v);
                  parse_session              <= header_session_v;
                  parse_seq                  <= header_seq_v;
                  parse_frag_count           <= header_frag_count_v;
                  parse_ack_bitmap_bytes     <= header_ack_bitmap_bytes_v;
                  parse_ack_complete         <= header_ack_complete_v;
                  parse_ack_idx          <= '0;
                  parse_ack_bitmap       <= '0;
                  if ((header_frag_count_v == 0) || (header_frag_count_v > MAX_FRAGS) ||
                      (expected_ack_bitmap_bytes_v == 0) ||
                      (header_ack_bitmap_bytes_v != expected_ack_bitmap_bytes_v) ||
                      (header_ack_bitmap_bytes_v > ACK_BITMAP_BYTES) ||
                      rx_mux_tlast) begin
                    rx_protocol_error <= 1'b1;
                    rx_parse_state    <= rx_mux_tlast ? RX_IDLE : RX_DROP;
                  end else begin
                    rx_parse_state <= RX_ACK_BITMAP;
                  end
                end
              end else if (rx_mux_tlast) begin
                rx_header_error <= 1'b1;
                rx_parse_state  <= RX_IDLE;
              end else begin
                parse_hdr_idx <= parse_hdr_idx + 1'b1;
              end
            end

            RX_PAYLOAD: begin
              rx_pkt_buf[parse_payload_offset + parse_payload_idx] <= rx_mux_tdata;
              if (parse_payload_idx == parse_payload_len - 1'b1) begin
                if (!rx_mux_tlast) begin
                  rx_protocol_error <= 1'b1;
                  rx_parse_state    <= RX_DROP;
                end else begin
                  bit_v = ({{(MAX_FRAGS-1){1'b0}}, 1'b1} << parse_frag_idx);
                  if ((rx_bitmap & bit_v) == '0) begin
                    rx_bitmap <= rx_bitmap | bit_v;
                    if ((rx_bitmap | bit_v) == frag_mask(parse_frag_count)) begin
                      rx_ctx_complete  <= 1'b1;
                      rx_output_active <= 1'b1;
                      rx_out_idx       <= 16'h0000;
                      rx_done_pulse    <= 1'b1;
                    end
                  end
                  rx_parse_state <= RX_IDLE;
                end
              end else begin
                if (rx_mux_tlast) begin
                  rx_protocol_error <= 1'b1;
                  rx_parse_state    <= RX_IDLE;
                end else begin
                  parse_payload_idx <= parse_payload_idx + 1'b1;
                end
              end
            end

            RX_ACK_BITMAP: begin
              bit_v = '0;
              for (bi = 0; bi < 8; bi = bi + 1) begin
                if ((parse_ack_idx * 8 + bi) < MAX_FRAGS) begin
                  bit_v[parse_ack_idx * 8 + bi] = rx_mux_tdata[bi];
                end
              end
              parse_ack_bitmap <= parse_ack_bitmap | bit_v;
              if (parse_ack_idx == parse_ack_bitmap_bytes - 1'b1) begin
                if (!rx_mux_tlast) begin
                  rx_protocol_error <= 1'b1;
                  rx_parse_state    <= RX_DROP;
                end else begin
                  ack_rx_valid   <= 1'b1;
                  ack_rx_seq     <= parse_seq;
                  ack_rx_bitmap  <= parse_ack_bitmap | bit_v;
                  ack_rx_complete <= parse_ack_complete;
                  rx_parse_state <= RX_IDLE;
                end
              end else if (rx_mux_tlast) begin
                rx_protocol_error <= 1'b1;
                rx_parse_state    <= RX_IDLE;
              end else begin
                parse_ack_idx <= parse_ack_idx + 1'b1;
              end
            end

            RX_DROP: begin
              if (rx_mux_tlast) rx_parse_state <= RX_IDLE;
            end

            default: rx_parse_state <= RX_IDLE;
          endcase
        end
      end
    end
  end

  assign lane_tx_busy_dbg       = lane_tx_busy;
  assign lane_rx_frame_pulse_dbg = lane_rx_axis_tvalid & lane_rx_axis_tready & lane_rx_axis_tlast;
  assign lane_rx_crc_error_dbg  = lane_rx_crc_error;
  assign lane_rx_error_dbg      = lane_rx_overrun_error;
  assign rx_frame_overflow_any  = 1'b0;
  assign rx_crc_error_any       = |lane_rx_crc_error;
  assign rx_overrun_error_any   = |lane_rx_overrun_error;
  assign tx_frag_pending_dbg    = tx_pending_bitmap;
  assign tx_frag_inflight_dbg   = tx_inflight_bitmap;
  assign tx_frag_acked_dbg      = tx_acked_bitmap;
  assign rx_recv_bitmap_dbg     = rx_bitmap;
  assign debug_status = {
    4'hA,
    tx_state,
    rx_parse_state,
    ack_rx_valid,
    (ack_rx_seq == tx_seq),
    ack_rx_bitmap[tx_frag_idx],
    tx_current_frag_acked_seen,
    rx_done_pulse,
    rx_header_error,
    rx_protocol_error,
    ack_pending,
    channel_idle,
    any_rx_active,
    tx_active_lane[0],
    rx_mux_lane_id[0],
    tx_frag_idx[0],
    tx_retry_count
  };
endmodule
