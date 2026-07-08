module ir_array_top #(
  parameter int LANE_COUNT                = 1,
  parameter int MAX_PACKET_BYTES          = 256,
  parameter int FRAGMENT_BYTES            = 16,
  parameter int MAX_RETRY                 = 4,
  parameter int CNT_CHIP_MAX              = 7,
  parameter int CNT_PREAMBLE              = 16,
  parameter int EOF_SILENCE_SYMS          = 3,
  parameter int FRAG_TIMEOUT_CYCLES       = 50000,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = 200000,
  parameter int MAX_FRAGS                 = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int MAX_FRAME_BYTES           = (14 + FRAGMENT_BYTES)
)(
  input  logic                         clk_phy,
  input  logic                         rst_n,
  input  logic                         enable,
  input  logic [15:0]                  session_id,
  input  logic [LANE_COUNT-1:0]        lane_enable_mask,
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
  output logic [LANE_COUNT-1:0]        lane_tx_busy_dbg,
  output logic [MAX_FRAGS-1:0]         tx_frag_pending_dbg,
  output logic [MAX_FRAGS-1:0]         tx_frag_inflight_dbg,
  output logic [MAX_FRAGS-1:0]         tx_frag_acked_dbg,
  output logic [MAX_FRAGS-1:0]         rx_recv_bitmap_dbg
);
  localparam int RR_W = (LANE_COUNT <= 1) ? 1 : $clog2(LANE_COUNT);

  logic                         tx_issue_valid;
  logic                         tx_issue_ready;
  logic [7:0]                   tx_issue_frag_idx;
  logic [8*MAX_FRAME_BYTES-1:0] tx_issue_frame_data;
  logic [15:0]                  tx_issue_frame_len;
  logic [15:0]                  active_pkt_seq;

  logic                         ack_update_valid;
  logic [15:0]                  ack_update_session_id;
  logic [15:0]                  ack_update_pkt_seq;
  logic                         ack_update_complete;
  logic [MAX_FRAGS-1:0]         ack_update_bitmap;
  logic                         ack_issue_valid;
  logic                         ack_issue_ready;
  logic [8*MAX_FRAME_BYTES-1:0] ack_issue_frame_data;
  logic [15:0]                  ack_issue_frame_len;

  logic [LANE_COUNT-1:0] lane_load_ready;
  logic [LANE_COUNT-1:0] lane_load;
  logic [LANE_COUNT-1:0] lane_busy;
  logic [LANE_COUNT-1:0] lane_rx_frame_valid;
  logic [LANE_COUNT-1:0] lane_rx_frame_ready;
  logic [8*MAX_FRAME_BYTES-1:0] lane_rx_frame_data [0:LANE_COUNT-1];
  logic [15:0]                  lane_rx_frame_len  [0:LANE_COUNT-1];
  logic [LANE_COUNT-1:0]        lane_rx_frame_overflow;
  logic [LANE_COUNT-1:0]        lane_rx_crc_error;
  logic [LANE_COUNT-1:0]        lane_rx_overrun_error;

  logic                         ingress_valid;
  logic                         ingress_ready;
  logic [8*MAX_FRAME_BYTES-1:0] ingress_frame_data;
  logic [15:0]                  ingress_frame_len;
  logic [7:0]                   ingress_lane_id;

  logic [RR_W-1:0] tx_rr_ptr;
  logic [RR_W-1:0] rx_rr_ptr;
  integer tx_sel_lane;
  integer rx_sel_lane;
  integer tx_l;
  integer rx_l;
  integer tx_cand;
  integer rx_cand;

  ir_array_tx_mgr #(
    .MAX_PACKET_BYTES    (MAX_PACKET_BYTES),
    .FRAGMENT_BYTES      (FRAGMENT_BYTES),
    .MAX_FRAME_BYTES     (MAX_FRAME_BYTES),
    .MAX_RETRY           (MAX_RETRY),
    .FRAG_TIMEOUT_CYCLES (FRAG_TIMEOUT_CYCLES),
    .MAX_FRAGS           (MAX_FRAGS)
  ) u_tx_mgr (
    .clk                  (clk_phy),
    .rst_n                (rst_n),
    .enable               (enable),
    .session_id           (session_id),
    .s_axis_tdata         (s_axis_tx_tdata),
    .s_axis_tvalid        (s_axis_tx_tvalid),
    .s_axis_tready        (s_axis_tx_tready),
    .s_axis_tlast         (s_axis_tx_tlast),
    .ack_valid            (ack_update_valid),
    .ack_session_id       (ack_update_session_id),
    .ack_pkt_seq          (ack_update_pkt_seq),
    .ack_complete         (ack_update_complete),
    .ack_bitmap           (ack_update_bitmap),
    .issue_valid          (tx_issue_valid),
    .issue_ready          (tx_issue_ready),
    .issue_frag_idx       (tx_issue_frag_idx),
    .issue_frame_data     (tx_issue_frame_data),
    .issue_frame_len      (tx_issue_frame_len),
    .active_pkt_seq       (active_pkt_seq),
    .packet_active        (tx_packet_active),
    .packet_loading       (tx_packet_loading),
    .done_pulse           (tx_done_pulse),
    .error_overflow       (tx_error_overflow),
    .error_retry_exhausted(tx_error_retry_exhausted),
    .frag_pending_dbg     (tx_frag_pending_dbg),
    .frag_inflight_dbg    (tx_frag_inflight_dbg),
    .frag_acked_dbg       (tx_frag_acked_dbg)
  );

  ir_array_rx_mgr #(
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES  (FRAGMENT_BYTES),
    .MAX_FRAME_BYTES (MAX_FRAME_BYTES),
    .MAX_FRAGS       (MAX_FRAGS),
    .REASSEMBLY_TIMEOUT_CYCLES(REASSEMBLY_TIMEOUT_CYCLES)
  ) u_rx_mgr (
    .clk                  (clk_phy),
    .rst_n                (rst_n),
    .enable               (enable),
    .session_id           (session_id),
    .in_frame_valid       (ingress_valid),
    .in_frame_ready       (ingress_ready),
    .in_frame_data        (ingress_frame_data),
    .in_frame_len         (ingress_frame_len),
    .in_lane_id           (ingress_lane_id),
    .ack_update_valid     (ack_update_valid),
    .ack_update_session_id(ack_update_session_id),
    .ack_update_pkt_seq   (ack_update_pkt_seq),
    .ack_update_complete  (ack_update_complete),
    .ack_update_bitmap    (ack_update_bitmap),
    .ack_issue_valid      (ack_issue_valid),
    .ack_issue_ready      (ack_issue_ready),
    .ack_issue_frame_data (ack_issue_frame_data),
    .ack_issue_frame_len  (ack_issue_frame_len),
    .m_axis_tdata         (m_axis_rx_tdata),
    .m_axis_tvalid        (m_axis_rx_tvalid),
    .m_axis_tready        (m_axis_rx_tready),
    .m_axis_tlast         (m_axis_rx_tlast),
    .rx_ctx_valid         (rx_ctx_valid),
    .rx_ctx_complete      (rx_ctx_complete),
    .rx_done_pulse        (rx_done_pulse),
    .header_error         (rx_header_error),
    .protocol_error       (rx_protocol_error),
    .recv_bitmap_dbg      (rx_recv_bitmap_dbg)
  );

  genvar gi;
  generate
    for (gi = 0; gi < LANE_COUNT; gi = gi + 1) begin : g_lane
      ir_comm_lane #(
        .MAX_FRAME_BYTES  (MAX_FRAME_BYTES),
        .CNT_CHIP_MAX     (CNT_CHIP_MAX),
        .CNT_PREAMBLE     (CNT_PREAMBLE),
        .EOF_SILENCE_SYMS (EOF_SILENCE_SYMS)
      ) u_lane (
        .clk              (clk_phy),
        .rst_n            (rst_n),
        .enable           (enable && lane_enable_mask[gi]),
        .load_frame       (lane_load[gi]),
        .frame_data       (ack_issue_valid ? ack_issue_frame_data : tx_issue_frame_data),
        .frame_len        (ack_issue_valid ? ack_issue_frame_len  : tx_issue_frame_len),
        .load_ready       (lane_load_ready[gi]),
        .lane_tx_busy     (lane_busy[gi]),
        .rx_frame_valid   (lane_rx_frame_valid[gi]),
        .rx_frame_ready   (lane_rx_frame_ready[gi]),
        .rx_frame_data    (lane_rx_frame_data[gi]),
        .rx_frame_len     (lane_rx_frame_len[gi]),
        .rx_frame_overflow(lane_rx_frame_overflow[gi]),
        .rx_crc_error     (lane_rx_crc_error[gi]),
        .rx_overrun_error (lane_rx_overrun_error[gi]),
        .ir_tx_out        (ir_tx_out[gi]),
        .ir_rx_in         (ir_rx_in[gi]),
        .ir_sd            (ir_sd[gi]),
        .ir_mode_out      (ir_mode_out[gi])
      );
    end
  endgenerate

  assign lane_tx_busy_dbg = lane_busy;

  always_comb begin
    for (tx_l = 0; tx_l < LANE_COUNT; tx_l = tx_l + 1) lane_load[tx_l] = 1'b0;
    tx_issue_ready  = 1'b0;
    ack_issue_ready = 1'b0;
    tx_sel_lane     = -1;

    for (tx_l = 0; tx_l < LANE_COUNT; tx_l = tx_l + 1) begin
      tx_cand = (tx_rr_ptr + tx_l) % LANE_COUNT;
      if ((tx_sel_lane == -1) && lane_enable_mask[tx_cand] && lane_load_ready[tx_cand]) tx_sel_lane = tx_cand;
    end

    if (tx_sel_lane != -1) begin
      if (ack_issue_valid) begin
        lane_load[tx_sel_lane] = 1'b1;
        ack_issue_ready        = 1'b1;
      end else if (tx_issue_valid) begin
        lane_load[tx_sel_lane] = 1'b1;
        tx_issue_ready         = 1'b1;
      end
    end
  end

  always_comb begin
    ingress_valid      = 1'b0;
    ingress_frame_data = '0;
    ingress_frame_len  = 16'h0000;
    ingress_lane_id    = 8'h00;
    rx_sel_lane        = -1;
    for (rx_l = 0; rx_l < LANE_COUNT; rx_l = rx_l + 1) lane_rx_frame_ready[rx_l] = 1'b0;

    for (rx_l = 0; rx_l < LANE_COUNT; rx_l = rx_l + 1) begin
      rx_cand = (rx_rr_ptr + rx_l) % LANE_COUNT;
      if ((rx_sel_lane == -1) && lane_rx_frame_valid[rx_cand]) rx_sel_lane = rx_cand;
    end

    if (rx_sel_lane != -1) begin
      ingress_valid      = lane_rx_frame_valid[rx_sel_lane];
      ingress_frame_data = lane_rx_frame_data[rx_sel_lane];
      ingress_frame_len  = lane_rx_frame_len[rx_sel_lane];
      ingress_lane_id    = rx_sel_lane[7:0];
      lane_rx_frame_ready[rx_sel_lane] = ingress_ready;
    end
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      tx_rr_ptr <= '0;
      rx_rr_ptr <= '0;
    end else begin
      if ((tx_sel_lane != -1) && ((ack_issue_valid && ack_issue_ready) || (tx_issue_valid && tx_issue_ready))) begin
        tx_rr_ptr <= (tx_sel_lane + 1) % LANE_COUNT;
      end
      if ((rx_sel_lane != -1) && ingress_valid && ingress_ready) begin
        rx_rr_ptr <= (rx_sel_lane + 1) % LANE_COUNT;
      end
    end
  end
endmodule
