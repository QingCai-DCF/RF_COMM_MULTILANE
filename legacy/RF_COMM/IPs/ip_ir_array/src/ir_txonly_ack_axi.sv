import ir_protocol_pkg::*;

module ir_txonly_ack_axi #(
  parameter int LANE_COUNT             = 1,
  parameter int MAX_PACKET_BYTES       = 255,
  parameter int FRAGMENT_BYTES         = 255,
  parameter int MAX_RETRY              = 4,
  parameter int CNT_CHIP_MAX           = 7,
  parameter int CNT_PREAMBLE           = 64,
  parameter int EOF_SILENCE_SYMS       = 3,
  parameter int FRAG_TIMEOUT_CYCLES    = 50000,
  parameter int POST_ACK_GUARD_CYCLES  = 4096,
  parameter int MAX_FRAGS              = 1,
  parameter int TX_ASYNC_FIFO_DEPTH    = 1024,
  parameter int C_S_AXI_DATA_WIDTH     = 32,
  parameter int C_S_AXI_ADDR_WIDTH     = 6
)(
  input  logic                           clk_phy,
  input  logic                           rst_n,
  input  logic                           s_axi_aclk,
  input  logic                           s_axi_aresetn,

  input  logic [C_S_AXI_ADDR_WIDTH-1:0]  s_axi_awaddr,
  input  logic                           s_axi_awvalid,
  output logic                           s_axi_awready,
  input  logic [C_S_AXI_DATA_WIDTH-1:0]  s_axi_wdata,
  input  logic [3:0]                     s_axi_wstrb,
  input  logic                           s_axi_wvalid,
  output logic                           s_axi_wready,
  output logic [1:0]                     s_axi_bresp,
  output logic                           s_axi_bvalid,
  input  logic                           s_axi_bready,
  input  logic [C_S_AXI_ADDR_WIDTH-1:0]  s_axi_araddr,
  input  logic                           s_axi_arvalid,
  output logic                           s_axi_arready,
  output logic [C_S_AXI_DATA_WIDTH-1:0]  s_axi_rdata,
  output logic [1:0]                     s_axi_rresp,
  output logic                           s_axi_rvalid,
  input  logic                           s_axi_rready,

  input  logic [7:0]                     s_axis_tx_tdata,
  input  logic                           s_axis_tx_tvalid,
  output logic                           s_axis_tx_tready,
  input  logic                           s_axis_tx_tlast,

  output logic [7:0]                     m_axis_rx_tdata,
  output logic                           m_axis_rx_tvalid,
  input  logic                           m_axis_rx_tready,
  output logic                           m_axis_rx_tlast,

  output logic [LANE_COUNT-1:0]          ir_tx_out,
  input  logic [LANE_COUNT-1:0]          ir_rx_in,
  output logic [LANE_COUNT-1:0]          ir_sd,
  output logic [LANE_COUNT-1:0]          ir_mode_out,
  input  logic [31:0]                    ext_phy_dbg
);
  localparam int STICKY_W       = 9;
  localparam int DATA_HDR_BYTES = IRP_DATA_HDR_BYTES;
  localparam int ACK_HDR_BYTES  = IRP_ACK_HDR_BYTES;
  localparam int ACK_BUF_BYTES  = ACK_HDR_BYTES + 1;
  localparam int APP_HDR_BYTES  = 8;
  localparam logic [15:0] APP_HDR_BYTES_U16 = APP_HDR_BYTES;
  localparam int SYNTH_MAX_PAYLOAD_BYTES = (MAX_PACKET_BYTES > APP_HDR_BYTES) ? (MAX_PACKET_BYTES - APP_HDR_BYTES) : 1;
  localparam logic [15:0] SYNTH_MAX_PAYLOAD_BYTES_U16 = SYNTH_MAX_PAYLOAD_BYTES;
  localparam int SEND_IDX_W     = $clog2(DATA_HDR_BYTES + MAX_PACKET_BYTES + 1);
  localparam int WR_PTR_W       = $clog2(MAX_PACKET_BYTES + 1);

  typedef enum logic [2:0] {
    S_IDLE,
    S_COLLECT,
    S_DROP,
    S_WAIT_GUARD,
    S_SEND,
    S_WAIT_ACK
  } state_t;

  state_t state;

  logic cfg_enable_axi;
  logic [15:0] cfg_session_id_axi;
  logic [LANE_COUNT-1:0] cfg_lane_mask_axi;
  logic [LANE_COUNT-1:0] cfg_rx_lane_mask_axi;
  logic cfg_commit_toggle_axi;
  logic [STICKY_W-1:0] sticky_clear_toggle_axi;
  logic cfg_test_mode_enable_axi;
  logic test_rx_inject_pulse_axi;
  logic [15:0] test_rx_payload_bytes_axi;
  logic [7:0]  test_rx_pattern_id_axi;
  logic [15:0] test_rx_seq_base_axi;
  logic [31:0] test_rx_packet_count_axi;

  logic cfg_enable_phy;
  logic [15:0] cfg_session_id_phy;
  logic [LANE_COUNT-1:0] cfg_lane_mask_phy;
  logic [LANE_COUNT-1:0] cfg_rx_lane_mask_phy;
  logic [STICKY_W-1:0] sticky_clear_toggle_phy;
  logic [STICKY_W-1:0] sticky_clear_toggle_phy_d;
  logic [STICKY_W-1:0] sticky_clear_pulse_phy;

  logic [STICKY_W-1:0] sticky_status_phy;
  logic [STICKY_W-1:0] sticky_status_axi;

  logic tx_packet_active_phy;
  logic tx_packet_loading_phy;
  logic tx_packet_active_axi;
  logic tx_packet_loading_axi;
  logic [LANE_COUNT-1:0] lane_tx_busy_dbg_phy;
  logic [LANE_COUNT-1:0] lane_tx_busy_dbg_axi;

  logic [MAX_FRAGS-1:0] tx_frag_pending_phy;
  logic [MAX_FRAGS-1:0] tx_frag_inflight_phy;
  logic [MAX_FRAGS-1:0] tx_frag_acked_phy;
  logic [MAX_FRAGS-1:0] rx_recv_bitmap_phy;
  logic [MAX_FRAGS-1:0] tx_frag_pending_axi;
  logic [MAX_FRAGS-1:0] tx_frag_inflight_axi;
  logic [MAX_FRAGS-1:0] tx_frag_acked_axi;
  logic [MAX_FRAGS-1:0] rx_recv_bitmap_axi;

  logic [31:0] tx_lane_count_phy;
  logic [31:0] rx_lane_good_count_phy;
  logic [31:0] rx_lane_crc_count_phy;
  logic [31:0] rx_lane_err_count_phy;
  logic [31:0] phy_lane0_dbg_phy;
  logic [31:0] tx_lane_count_axi;
  logic [31:0] rx_lane_good_count_axi;
  logic [31:0] rx_lane_crc_count_axi;
  logic [31:0] rx_lane_err_count_axi;
  logic [31:0] phy_lane0_dbg_axi;

  logic [7:0] tx_fifo_tdata;
  logic       tx_fifo_tvalid;
  logic       tx_fifo_tready;
  logic       tx_fifo_tlast;

  logic [7:0] tx_enc_tdata;
  logic       tx_enc_tvalid;
  logic       tx_enc_tready;
  logic       tx_enc_tlast;
  logic       tx_busy;
  logic       lane_tx_out;
  logic       lane_rx_masked;

  logic [7:0] rx_axis_tdata;
  logic       rx_axis_tvalid;
  logic       rx_axis_tready;
  logic       rx_axis_tlast;
  logic       rx_crc_error;
  logic       rx_overrun_error;
  logic [31:0] rx_debug_status;
  logic       synth_rx_active_axi;
  logic [15:0] synth_rx_payload_len_axi;
  logic [15:0] synth_rx_total_len_axi;
  logic [15:0] synth_rx_seq_axi;
  logic [7:0]  synth_rx_pattern_axi;
  logic [15:0] synth_rx_idx_axi;
  logic        synth_rx_done_pulse_axi;
  logic [STICKY_W-1:0] obs_clear_toggle_axi_d;
  logic        obs_clear_pulse_axi;
  logic        obs_synth_rx_fire_axi;
  logic [31:0] obs_synth_rx_tvalid_count_axi;
  logic [31:0] obs_synth_rx_tlast_count_axi;
  logic [31:0] obs_synth_rx_byte_count_axi;
  logic [31:0] obs_mux_rx_tvalid_count_axi;
  logic [31:0] obs_mux_rx_tlast_count_axi;
  logic [31:0] obs_mux_rx_byte_count_axi;

  logic [7:0] pkt_buf [0:MAX_PACKET_BYTES-1];
  logic [WR_PTR_W-1:0] wr_ptr;
  logic [15:0] pkt_len;
  logic [15:0] pkt_seq;
  logic [15:0] seq_counter;
  logic [SEND_IDX_W-1:0] send_idx;
  logic [15:0] hdr_crc;
  logic [31:0] ack_timeout;
  logic [31:0] post_ack_guard;
  logic [7:0] retry_count;

  logic [7:0] ack_buf [0:ACK_BUF_BYTES-1];
  logic [$clog2(ACK_BUF_BYTES+1)-1:0] ack_wr_ptr;
  logic [$clog2(ACK_BUF_BYTES+1)-1:0] ack_len;
  logic ack_drop;
  logic ack_parse_pending;
  logic ack_ok_c;
  logic [15:0] ack_crc_c;
  logic [15:0] ack_crc_rx_c;
  logic [15:0] ack_session_c;
  logic [15:0] ack_seq_c;

  logic tx_fifo_fire;
  logic tx_enc_fire;
  logic [15:0] frame_len;
  logic [15:0] payload_rd_idx;
  logic [7:0] header_byte_c;
  logic [15:0] next_pkt_len_c;

  integer oi;
  integer ci;

  initial begin
    if (LANE_COUNT < 1) $error("LANE_COUNT must be at least 1");
    if (MAX_FRAGS != 1) $error("TX-only speed endpoint expects MAX_FRAGS=1");
    if (FRAGMENT_BYTES < MAX_PACKET_BYTES) $error("TX-only speed endpoint expects one-fragment packets");
    if (MAX_PACKET_BYTES > 255) $error("TX-only speed endpoint supports at most 255 packet bytes");
  end

  assign synth_rx_total_len_axi = synth_rx_payload_len_axi + APP_HDR_BYTES_U16;
  assign m_axis_rx_tdata  = synth_rx_active_axi ?
                            synth_rx_byte(synth_rx_idx_axi,
                                          synth_rx_payload_len_axi,
                                          synth_rx_seq_axi,
                                          synth_rx_pattern_axi) :
                            8'h00;
  assign m_axis_rx_tvalid = synth_rx_active_axi;
  assign m_axis_rx_tlast  = synth_rx_active_axi &&
                            (synth_rx_idx_axi == (synth_rx_total_len_axi - 1'b1));
  assign obs_clear_pulse_axi = |(sticky_clear_toggle_axi ^ obs_clear_toggle_axi_d);
  assign obs_synth_rx_fire_axi = synth_rx_active_axi && m_axis_rx_tready;

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      obs_clear_toggle_axi_d <= '0;
      obs_synth_rx_tvalid_count_axi <= 32'h0000_0000;
      obs_synth_rx_tlast_count_axi <= 32'h0000_0000;
      obs_synth_rx_byte_count_axi <= 32'h0000_0000;
      obs_mux_rx_tvalid_count_axi <= 32'h0000_0000;
      obs_mux_rx_tlast_count_axi <= 32'h0000_0000;
      obs_mux_rx_byte_count_axi <= 32'h0000_0000;
    end else begin
      obs_clear_toggle_axi_d <= sticky_clear_toggle_axi;
      if (obs_clear_pulse_axi) begin
        obs_synth_rx_tvalid_count_axi <= 32'h0000_0000;
        obs_synth_rx_tlast_count_axi <= 32'h0000_0000;
        obs_synth_rx_byte_count_axi <= 32'h0000_0000;
        obs_mux_rx_tvalid_count_axi <= 32'h0000_0000;
        obs_mux_rx_tlast_count_axi <= 32'h0000_0000;
        obs_mux_rx_byte_count_axi <= 32'h0000_0000;
      end else begin
        if (synth_rx_active_axi) obs_synth_rx_tvalid_count_axi <= obs_synth_rx_tvalid_count_axi + 1'b1;
        if (obs_synth_rx_fire_axi && m_axis_rx_tlast) obs_synth_rx_tlast_count_axi <= obs_synth_rx_tlast_count_axi + 1'b1;
        if (obs_synth_rx_fire_axi) obs_synth_rx_byte_count_axi <= obs_synth_rx_byte_count_axi + 1'b1;
        if (m_axis_rx_tvalid) obs_mux_rx_tvalid_count_axi <= obs_mux_rx_tvalid_count_axi + 1'b1;
        if (obs_synth_rx_fire_axi && m_axis_rx_tlast) obs_mux_rx_tlast_count_axi <= obs_mux_rx_tlast_count_axi + 1'b1;
        if (obs_synth_rx_fire_axi) obs_mux_rx_byte_count_axi <= obs_mux_rx_byte_count_axi + 1'b1;
      end
    end
  end

  function automatic logic [7:0] synth_payload_byte(
    input logic [15:0] seq_i,
    input logic [15:0] payload_idx_i,
    input logic [7:0]  pattern_i
  );
    begin
      case (pattern_i)
        8'd0: synth_payload_byte = 8'h00;
        8'd1: synth_payload_byte = 8'hff;
        8'd2: synth_payload_byte = payload_idx_i[7:0];
        default: synth_payload_byte = seq_i[7:0] ^ payload_idx_i[7:0] ^ 8'ha5;
      endcase
    end
  endfunction

  function automatic logic [7:0] synth_rx_byte(
    input logic [15:0] idx_i,
    input logic [15:0] payload_len_i,
    input logic [15:0] seq_i,
    input logic [7:0]  pattern_i
  );
    logic [15:0] payload_idx;
    begin
      payload_idx = idx_i - APP_HDR_BYTES_U16;
      case (idx_i)
        16'd0: synth_rx_byte = 8'h49; // I
        16'd1: synth_rx_byte = 8'h52; // R
        16'd2: synth_rx_byte = 8'h50; // P
        16'd3: synth_rx_byte = 8'h31; // 1
        16'd4: synth_rx_byte = seq_i[7:0];
        16'd5: synth_rx_byte = seq_i[15:8];
        16'd6: synth_rx_byte = payload_len_i[7:0];
        16'd7: synth_rx_byte = payload_len_i[15:8];
        default: synth_rx_byte = synth_payload_byte(seq_i, payload_idx, pattern_i);
      endcase
    end
  endfunction

  always_comb begin
    ir_tx_out   = '0;
    ir_sd       = '1;
    ir_mode_out = '0;
    ir_tx_out[0]   = lane_tx_out;
    ir_sd[0]       = ~cfg_enable_phy;
    ir_mode_out[0] = 1'b1;
  end

  ir_axi_regs #(
    .C_S_AXI_DATA_WIDTH(C_S_AXI_DATA_WIDTH),
    .C_S_AXI_ADDR_WIDTH(C_S_AXI_ADDR_WIDTH),
    .LANE_COUNT        (LANE_COUNT),
    .MAX_FRAGS         (MAX_FRAGS)
  ) u_regs (
    .s_axi_aclk                 (s_axi_aclk),
    .s_axi_aresetn              (s_axi_aresetn),
    .s_axi_awaddr               (s_axi_awaddr),
    .s_axi_awvalid              (s_axi_awvalid),
    .s_axi_awready              (s_axi_awready),
    .s_axi_wdata                (s_axi_wdata),
    .s_axi_wstrb                (s_axi_wstrb),
    .s_axi_wvalid               (s_axi_wvalid),
    .s_axi_wready               (s_axi_wready),
    .s_axi_bresp                (s_axi_bresp),
    .s_axi_bvalid               (s_axi_bvalid),
    .s_axi_bready               (s_axi_bready),
    .s_axi_araddr               (s_axi_araddr),
    .s_axi_arvalid              (s_axi_arvalid),
    .s_axi_arready              (s_axi_arready),
    .s_axi_rdata                (s_axi_rdata),
    .s_axi_rresp                (s_axi_rresp),
    .s_axi_rvalid               (s_axi_rvalid),
    .s_axi_rready               (s_axi_rready),
    .cfg_enable                 (cfg_enable_axi),
    .cfg_session_id             (cfg_session_id_axi),
    .cfg_lane_enable_mask       (cfg_lane_mask_axi),
    .cfg_rx_lane_enable_mask    (cfg_rx_lane_mask_axi),
    .cfg_commit_toggle          (cfg_commit_toggle_axi),
    .sticky_clear_toggle        (sticky_clear_toggle_axi),
    .cfg_test_mode_enable       (cfg_test_mode_enable_axi),
    .test_rx_inject_pulse       (test_rx_inject_pulse_axi),
    .test_rx_payload_bytes      (test_rx_payload_bytes_axi),
    .test_rx_pattern_id         (test_rx_pattern_id_axi),
    .test_rx_seq_base           (test_rx_seq_base_axi),
    .test_rx_packet_count       (test_rx_packet_count_axi),
    .tx_packet_active           (tx_packet_active_axi),
    .tx_packet_loading          (tx_packet_loading_axi),
    .rx_ctx_valid               (1'b0),
    .rx_ctx_complete            (1'b0),
    .sticky_tx_done             (sticky_status_axi[0]),
    .sticky_rx_done             (synth_rx_done_pulse_axi),
    .sticky_tx_overflow         (sticky_status_axi[2]),
    .sticky_tx_retry_exhausted  (sticky_status_axi[3]),
    .sticky_rx_header_error     (sticky_status_axi[4]),
    .sticky_rx_protocol_error   (sticky_status_axi[5]),
    .sticky_rx_frame_overflow   (1'b0),
    .sticky_rx_crc_error        (sticky_status_axi[7]),
    .sticky_rx_overrun_error    (sticky_status_axi[8]),
    .lane_tx_busy_dbg           (lane_tx_busy_dbg_axi),
    .tx_frag_pending_dbg        (tx_frag_pending_axi),
    .tx_frag_inflight_dbg       (tx_frag_inflight_axi),
    .tx_frag_acked_dbg          (tx_frag_acked_axi),
    .rx_recv_bitmap_dbg         (rx_recv_bitmap_axi),
    .tx_lane_count_dbg          (tx_lane_count_axi),
    .rx_lane_good_count_dbg     (rx_lane_good_count_axi),
    .rx_lane_crc_count_dbg      (rx_lane_crc_count_axi),
    .rx_lane_err_count_dbg      (rx_lane_err_count_axi),
    .phy_lane0_dbg              (phy_lane0_dbg_axi),
    .obs_core_rx_tvalid_count_dbg(32'h0000_0000),
    .obs_core_rx_tready_count_dbg(32'h0000_0000),
    .obs_core_rx_tlast_count_dbg (32'h0000_0000),
    .obs_core_rx_byte_count_dbg  (32'h0000_0000),
    .obs_synth_rx_tvalid_count_dbg(obs_synth_rx_tvalid_count_axi),
    .obs_synth_rx_tlast_count_dbg (obs_synth_rx_tlast_count_axi),
    .obs_synth_rx_byte_count_dbg  (obs_synth_rx_byte_count_axi),
    .obs_mux_rx_tvalid_count_dbg  (obs_mux_rx_tvalid_count_axi),
    .obs_mux_rx_tlast_count_dbg   (obs_mux_rx_tlast_count_axi),
    .obs_mux_rx_byte_count_dbg    (obs_mux_rx_byte_count_axi)
  );

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      synth_rx_active_axi      <= 1'b0;
      synth_rx_payload_len_axi <= 16'd16;
      synth_rx_seq_axi         <= 16'd1;
      synth_rx_pattern_axi     <= 8'd2;
      synth_rx_idx_axi         <= 16'd0;
      synth_rx_done_pulse_axi  <= 1'b0;
    end else begin
      synth_rx_done_pulse_axi <= 1'b0;

      if (!synth_rx_active_axi) begin
        if (cfg_test_mode_enable_axi && test_rx_inject_pulse_axi) begin
          synth_rx_active_axi <= 1'b1;
          synth_rx_idx_axi    <= 16'd0;
          synth_rx_seq_axi    <= test_rx_seq_base_axi;
          synth_rx_pattern_axi <= test_rx_pattern_id_axi;

          if (test_rx_payload_bytes_axi == 16'd0) begin
            synth_rx_payload_len_axi <= 16'd1;
          end else if (test_rx_payload_bytes_axi > SYNTH_MAX_PAYLOAD_BYTES_U16) begin
            synth_rx_payload_len_axi <= SYNTH_MAX_PAYLOAD_BYTES_U16;
          end else begin
            synth_rx_payload_len_axi <= test_rx_payload_bytes_axi;
          end
        end
      end else if (m_axis_rx_tready) begin
        if (synth_rx_idx_axi == (synth_rx_total_len_axi - 1'b1)) begin
          synth_rx_active_axi     <= 1'b0;
          synth_rx_idx_axi        <= 16'd0;
          synth_rx_done_pulse_axi <= 1'b1;
        end else begin
          synth_rx_idx_axi <= synth_rx_idx_axi + 1'b1;
        end
      end
    end
  end

  cdc_sync #(.WIDTH(1)) u_cfg_enable (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_enable_axi),
    .data_out(cfg_enable_phy)
  );

  cdc_sync #(.WIDTH(16)) u_cfg_session (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_session_id_axi),
    .data_out(cfg_session_id_phy)
  );

  cdc_sync #(.WIDTH(LANE_COUNT)) u_cfg_lane_mask (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_lane_mask_axi),
    .data_out(cfg_lane_mask_phy)
  );

  cdc_sync #(.WIDTH(LANE_COUNT)) u_cfg_rx_lane_mask (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_rx_lane_mask_axi),
    .data_out(cfg_rx_lane_mask_phy)
  );

  cdc_sync #(.WIDTH(STICKY_W)) u_clear_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (sticky_clear_toggle_axi),
    .data_out(sticky_clear_toggle_phy)
  );

  cdc_sync #(.WIDTH(STICKY_W)) u_sticky_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (sticky_status_phy),
    .data_out(sticky_status_axi)
  );

  cdc_sync #(.WIDTH(1)) u_tx_active_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_packet_active_phy),
    .data_out(tx_packet_active_axi)
  );

  cdc_sync #(.WIDTH(1)) u_tx_loading_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_packet_loading_phy),
    .data_out(tx_packet_loading_axi)
  );

  cdc_sync #(.WIDTH(LANE_COUNT)) u_lane_busy_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (lane_tx_busy_dbg_phy),
    .data_out(lane_tx_busy_dbg_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS)) u_tx_pending_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_frag_pending_phy),
    .data_out(tx_frag_pending_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS)) u_tx_inflight_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_frag_inflight_phy),
    .data_out(tx_frag_inflight_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS)) u_tx_acked_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_frag_acked_phy),
    .data_out(tx_frag_acked_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS)) u_rx_bitmap_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_recv_bitmap_phy),
    .data_out(rx_recv_bitmap_axi)
  );

  cdc_sync #(.WIDTH(32)) u_tx_count_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_lane_count_phy),
    .data_out(tx_lane_count_axi)
  );

  cdc_sync #(.WIDTH(32)) u_rx_good_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_lane_good_count_phy),
    .data_out(rx_lane_good_count_axi)
  );

  cdc_sync #(.WIDTH(32)) u_rx_crc_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_lane_crc_count_phy),
    .data_out(rx_lane_crc_count_axi)
  );

  cdc_sync #(.WIDTH(32)) u_rx_err_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_lane_err_count_phy),
    .data_out(rx_lane_err_count_axi)
  );

  cdc_sync #(.WIDTH(32)) u_phy_dbg_sync (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (phy_lane0_dbg_phy),
    .data_out(phy_lane0_dbg_axi)
  );

  ir_axis_async_fifo #(
    .DATA_W(8),
    .DEPTH (TX_ASYNC_FIFO_DEPTH)
  ) u_tx_async_fifo (
    .rst     (~s_axi_aresetn),
    .s_clk   (s_axi_aclk),
    .s_tdata (s_axis_tx_tdata),
    .s_tvalid(s_axis_tx_tvalid),
    .s_tready(s_axis_tx_tready),
    .s_tlast (s_axis_tx_tlast),
    .m_clk   (clk_phy),
    .m_tdata (tx_fifo_tdata),
    .m_tvalid(tx_fifo_tvalid),
    .m_tready(tx_fifo_tready),
    .m_tlast (tx_fifo_tlast)
  );

  ir_tx_4ppm_frame #(
    .CNT_CHIP_MAX   (CNT_CHIP_MAX),
    .CNT_PREAMBLE   (CNT_PREAMBLE),
    .CNT_EOF_SILENCE(EOF_SILENCE_SYMS + 4)
  ) u_tx (
    .clk          (clk_phy),
    .rst_n        (rst_n),
    .enable       (cfg_enable_phy && cfg_lane_mask_phy[0]),
    .s_axis_tdata (tx_enc_tdata),
    .s_axis_tvalid(tx_enc_tvalid),
    .s_axis_tready(tx_enc_tready),
    .s_axis_tlast (tx_enc_tlast),
    .tx_busy      (tx_busy),
    .ir_tx_out    (lane_tx_out)
  );

  assign lane_rx_masked = lane_tx_out ? 1'b1 : ir_rx_in[0];

  ir_rx_4ppm_frame #(
    .MAX_FRAME_BYTES (ACK_BUF_BYTES),
    .CNT_CHIP_MAX    (CNT_CHIP_MAX),
    .PREAMBLE_SYMS   (CNT_PREAMBLE),
    .EOF_SILENCE_SYMS(EOF_SILENCE_SYMS)
  ) u_rx (
    .clk          (clk_phy),
    .rst_n        (rst_n),
    .enable       (cfg_enable_phy && cfg_rx_lane_mask_phy[0]),
    .ir_rx_in     (lane_rx_masked),
    .m_axis_tdata (rx_axis_tdata),
    .m_axis_tvalid(rx_axis_tvalid),
    .m_axis_tready(rx_axis_tready),
    .m_axis_tlast (rx_axis_tlast),
    .rx_active    (),
    .crc_error    (rx_crc_error),
    .overrun_error(rx_overrun_error),
    .debug_status (rx_debug_status)
  );

  function automatic logic [7:0] data_header_byte(
    input logic [3:0] idx,
    input logic [15:0] session_i,
    input logic [15:0] seq_i,
    input logic [15:0] len_i,
    input logic [15:0] crc_i
  );
    begin
      case (idx)
        4'd0:  data_header_byte = IRP_SOF;
        4'd1:  data_header_byte = {IRP_VERSION, IRP_TYPE_DATA};
        4'd2:  data_header_byte = session_i[7:0];
        4'd3:  data_header_byte = session_i[15:8];
        4'd4:  data_header_byte = seq_i[7:0];
        4'd5:  data_header_byte = seq_i[15:8];
        4'd6:  data_header_byte = 8'h00;
        4'd7:  data_header_byte = 8'h01;
        4'd8:  data_header_byte = len_i[7:0];
        4'd9:  data_header_byte = len_i[15:8];
        4'd10: data_header_byte = len_i[7:0];
        4'd11: data_header_byte = 8'h00;
        4'd12: data_header_byte = crc_i[7:0];
        4'd13: data_header_byte = crc_i[15:8];
        default: data_header_byte = 8'h00;
      endcase
    end
  endfunction

  function automatic logic [15:0] data_header_crc(
    input logic [15:0] session_i,
    input logic [15:0] seq_i,
    input logic [15:0] len_i
  );
    logic [15:0] c;
    integer n;
    begin
      c = 16'hFFFF;
      for (n = 0; n < 12; n = n + 1) begin
        c = crc16_ccitt_next_byte(data_header_byte(n[3:0], session_i, seq_i, len_i, 16'h0000), c);
      end
      data_header_crc = c;
    end
  endfunction

  function automatic logic [15:0] ack_header_crc_calc;
    logic [15:0] c;
    integer n;
    begin
      c = 16'hFFFF;
      for (n = 0; n < 10; n = n + 1) begin
        c = crc16_ccitt_next_byte(ack_buf[n], c);
      end
      ack_header_crc_calc = c;
    end
  endfunction

  assign frame_len      = DATA_HDR_BYTES + pkt_len;
  assign payload_rd_idx = send_idx - DATA_HDR_BYTES;
  assign tx_fifo_fire   = tx_fifo_tvalid && tx_fifo_tready;
  assign tx_enc_fire    = tx_enc_tvalid && tx_enc_tready;
  assign tx_fifo_tready = cfg_enable_phy &&
                          ((state == S_IDLE) || (state == S_COLLECT) || (state == S_DROP));
  assign tx_enc_tvalid  = (state == S_SEND);
  assign tx_enc_tlast   = tx_enc_tvalid && (send_idx == (frame_len - 1'b1));
  assign rx_axis_tready = 1'b1;

  always_comb begin
    header_byte_c = data_header_byte(send_idx[3:0], cfg_session_id_phy, pkt_seq, pkt_len, hdr_crc);
    if (send_idx < DATA_HDR_BYTES) begin
      tx_enc_tdata = header_byte_c;
    end else if (payload_rd_idx < MAX_PACKET_BYTES) begin
      tx_enc_tdata = pkt_buf[payload_rd_idx];
    end else begin
      tx_enc_tdata = 8'h00;
    end
  end

  always_comb begin
    ack_crc_c     = ack_header_crc_calc();
    ack_crc_rx_c  = {ack_buf[11], ack_buf[10]};
    ack_session_c = {ack_buf[3], ack_buf[2]};
    ack_seq_c     = {ack_buf[5], ack_buf[4]};
    ack_ok_c      = (ack_len >= ACK_BUF_BYTES) &&
                    (ack_buf[0] == IRP_SOF) &&
                    (ack_buf[1] == {IRP_VERSION, IRP_TYPE_ACK}) &&
                    (ack_session_c == cfg_session_id_phy) &&
                    (ack_seq_c == pkt_seq) &&
                    (ack_buf[6] == 8'h01) &&
                    (ack_buf[7] == 8'h01) &&
                    (ack_buf[8][0] == 1'b1) &&
                    (ack_buf[9] == 8'h00) &&
                    (ack_crc_c == ack_crc_rx_c) &&
                    (ack_buf[12][0] == 1'b1);
  end

  assign tx_packet_active_phy  = (state != S_IDLE);
  assign tx_packet_loading_phy = (state == S_COLLECT);

  always_comb begin
    lane_tx_busy_dbg_phy = '0;
    lane_tx_busy_dbg_phy[0] = tx_busy || (state == S_SEND);
  end

  always_comb begin
    tx_frag_pending_phy  = '0;
    tx_frag_inflight_phy = '0;
    tx_frag_acked_phy    = '0;
    rx_recv_bitmap_phy   = '0;
    case (state)
      S_COLLECT,
      S_WAIT_GUARD,
      S_SEND: tx_frag_pending_phy[0] = 1'b1;
      S_WAIT_ACK: tx_frag_inflight_phy[0] = 1'b1;
      default: ;
    endcase
    if (sticky_status_phy[0]) begin
      tx_frag_acked_phy[0]  = 1'b1;
      rx_recv_bitmap_phy[0] = 1'b1;
    end
  end

  always_comb begin
    phy_lane0_dbg_phy = {
      4'hA,
      state,
      tx_busy,
      tx_fifo_tvalid,
      tx_fifo_tready,
      tx_enc_tready,
      retry_count[3:0],
      pkt_len[7:0],
      rx_debug_status[7:0]
    };
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      sticky_clear_toggle_phy_d <= '0;
      sticky_clear_pulse_phy    <= '0;
      sticky_status_phy         <= '0;
      state                     <= S_IDLE;
      wr_ptr                    <= '0;
      pkt_len                   <= 16'h0000;
      pkt_seq                   <= 16'h0000;
      seq_counter               <= 16'h0001;
      send_idx                  <= '0;
      hdr_crc                   <= 16'hFFFF;
      ack_timeout               <= 32'h0000_0000;
      post_ack_guard            <= 32'h0000_0000;
      retry_count               <= 8'h00;
      ack_wr_ptr                <= '0;
      ack_len                   <= '0;
      ack_drop                  <= 1'b0;
      ack_parse_pending         <= 1'b0;
      tx_lane_count_phy         <= 32'h0000_0000;
      rx_lane_good_count_phy    <= 32'h0000_0000;
      rx_lane_crc_count_phy     <= 32'h0000_0000;
      rx_lane_err_count_phy     <= 32'h0000_0000;
      for (oi = 0; oi < MAX_PACKET_BYTES; oi = oi + 1) begin
        pkt_buf[oi] <= 8'h00;
      end
      for (oi = 0; oi < ACK_BUF_BYTES; oi = oi + 1) begin
        ack_buf[oi] <= 8'h00;
      end
    end else begin
      sticky_clear_pulse_phy    <= sticky_clear_toggle_phy ^ sticky_clear_toggle_phy_d;
      sticky_clear_toggle_phy_d <= sticky_clear_toggle_phy;
      sticky_status_phy         <= sticky_status_phy & ~(sticky_clear_toggle_phy ^ sticky_clear_toggle_phy_d);

      if (post_ack_guard != 32'h0000_0000) begin
        post_ack_guard <= post_ack_guard - 1'b1;
      end

      if (rx_crc_error) begin
        sticky_status_phy[7] <= 1'b1;
        if (rx_lane_crc_count_phy[7:0] != 8'hff) rx_lane_crc_count_phy[7:0] <= rx_lane_crc_count_phy[7:0] + 8'd1;
      end
      if (rx_overrun_error) begin
        sticky_status_phy[8] <= 1'b1;
        if (rx_lane_err_count_phy[7:0] != 8'hff) rx_lane_err_count_phy[7:0] <= rx_lane_err_count_phy[7:0] + 8'd1;
      end

      if (rx_axis_tvalid && rx_axis_tready) begin
        if (!ack_drop && (ack_wr_ptr < ACK_BUF_BYTES)) begin
          ack_buf[ack_wr_ptr] <= rx_axis_tdata;
          ack_wr_ptr <= ack_wr_ptr + 1'b1;
        end else begin
          ack_drop <= 1'b1;
        end

        if (rx_axis_tlast) begin
          if (!ack_drop && (ack_wr_ptr < ACK_BUF_BYTES)) begin
            ack_len <= ack_wr_ptr + 1'b1;
            ack_parse_pending <= 1'b1;
          end else begin
            ack_len <= '0;
            sticky_status_phy[4] <= 1'b1;
            if (rx_lane_err_count_phy[7:0] != 8'hff) rx_lane_err_count_phy[7:0] <= rx_lane_err_count_phy[7:0] + 8'd1;
          end
          ack_wr_ptr <= '0;
          ack_drop   <= 1'b0;
        end
      end

      if (!cfg_enable_phy) begin
        state             <= S_IDLE;
        wr_ptr            <= '0;
        pkt_len           <= 16'h0000;
        send_idx          <= '0;
        ack_timeout       <= 32'h0000_0000;
        retry_count       <= 8'h00;
        ack_parse_pending <= 1'b0;
      end else begin
        if (ack_parse_pending) begin
          ack_parse_pending <= 1'b0;
          if ((state == S_WAIT_ACK) && ack_ok_c) begin
            sticky_status_phy[0] <= 1'b1;
            if (rx_lane_good_count_phy[7:0] != 8'hff) rx_lane_good_count_phy[7:0] <= rx_lane_good_count_phy[7:0] + 8'd1;
            post_ack_guard <= POST_ACK_GUARD_CYCLES[31:0];
            state <= S_IDLE;
          end else if (state == S_WAIT_ACK) begin
            sticky_status_phy[4] <= 1'b1;
            if (rx_lane_err_count_phy[7:0] != 8'hff) rx_lane_err_count_phy[7:0] <= rx_lane_err_count_phy[7:0] + 8'd1;
          end
        end

        case (state)
          S_IDLE: begin
            wr_ptr   <= '0;
            send_idx <= '0;
            if (tx_fifo_fire) begin
              pkt_buf[0] <= tx_fifo_tdata;
              if (tx_fifo_tlast) begin
                next_pkt_len_c = 16'd1;
                pkt_len        <= next_pkt_len_c;
                pkt_seq        <= seq_counter;
                seq_counter    <= seq_counter + 1'b1;
                hdr_crc        <= data_header_crc(cfg_session_id_phy, seq_counter, next_pkt_len_c);
                retry_count    <= 8'h00;
                state          <= (post_ack_guard == 32'h0000_0000) ? S_SEND : S_WAIT_GUARD;
              end else begin
                wr_ptr <= 1;
                state  <= S_COLLECT;
              end
            end
          end

          S_COLLECT: begin
            if (tx_fifo_fire) begin
              if (wr_ptr < MAX_PACKET_BYTES) begin
                pkt_buf[wr_ptr] <= tx_fifo_tdata;
                if (tx_fifo_tlast) begin
                  next_pkt_len_c = wr_ptr + 1'b1;
                  pkt_len        <= next_pkt_len_c;
                  pkt_seq        <= seq_counter;
                  seq_counter    <= seq_counter + 1'b1;
                  hdr_crc        <= data_header_crc(cfg_session_id_phy, seq_counter, next_pkt_len_c);
                  wr_ptr         <= '0;
                  retry_count    <= 8'h00;
                  state          <= (post_ack_guard == 32'h0000_0000) ? S_SEND : S_WAIT_GUARD;
                end else begin
                  wr_ptr <= wr_ptr + 1'b1;
                end
              end else begin
                sticky_status_phy[2] <= 1'b1;
                state <= tx_fifo_tlast ? S_IDLE : S_DROP;
              end
            end
          end

          S_DROP: begin
            if (tx_fifo_fire && tx_fifo_tlast) begin
              wr_ptr <= '0;
              state  <= S_IDLE;
            end
          end

          S_WAIT_GUARD: begin
            send_idx <= '0;
            if (post_ack_guard == 32'h0000_0000) begin
              state <= S_SEND;
            end
          end

          S_SEND: begin
            if (send_idx == '0 && tx_enc_fire) begin
              if (tx_lane_count_phy[7:0] != 8'hff) tx_lane_count_phy[7:0] <= tx_lane_count_phy[7:0] + 8'd1;
            end
            if (tx_enc_fire) begin
              if (tx_enc_tlast) begin
                send_idx    <= '0;
                ack_timeout <= FRAG_TIMEOUT_CYCLES;
                state       <= S_WAIT_ACK;
              end else begin
                send_idx <= send_idx + 1'b1;
              end
            end
          end

          S_WAIT_ACK: begin
            if (ack_timeout != 32'h0000_0000) begin
              ack_timeout <= ack_timeout - 1'b1;
            end else if (retry_count < MAX_RETRY) begin
              retry_count <= retry_count + 1'b1;
              send_idx    <= '0;
              state       <= S_SEND;
            end else begin
              sticky_status_phy[3] <= 1'b1;
              state <= S_IDLE;
            end
          end

          default: state <= S_IDLE;
        endcase
      end
    end
  end
endmodule
