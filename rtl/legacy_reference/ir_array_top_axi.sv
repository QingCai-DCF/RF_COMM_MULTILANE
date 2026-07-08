module ir_array_top_axi_full #(
  parameter int LANE_COUNT                = 4,
  parameter int MAX_PACKET_BYTES          = 256,
  parameter int FRAGMENT_BYTES            = 16,
  parameter int MAX_RETRY                 = (LANE_COUNT > 4) ? (LANE_COUNT * ((MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES)) : 4,
  parameter int CNT_CHIP_MAX              = 7,
  parameter int CNT_PREAMBLE              = 16,
  parameter int EOF_SILENCE_SYMS          = 3,
  parameter int FRAG_TIMEOUT_CYCLES       = 50000,
  parameter int TX_POST_ACK_GUARD_CYCLES  = 8192,
  parameter int RX_TO_TX_GUARD_CYCLES     = 8192,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = (LANE_COUNT > 4) ? (((MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES) * (MAX_RETRY + 2) * FRAG_TIMEOUT_CYCLES) : 200000,
  parameter int MAX_FRAGS                 = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int MAX_FRAME_BYTES           = (14 + FRAGMENT_BYTES),
  parameter int TX_ASYNC_FIFO_DEPTH       = 1024,
  parameter int RX_ASYNC_FIFO_DEPTH       = 1024,
  parameter int C_S_AXI_DATA_WIDTH        = 32,
  parameter int C_S_AXI_ADDR_WIDTH        = 6
)(
  input  logic                           clk_phy,
  input  logic                           rst_n,

  (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF s_axi:s_axis_tx:m_axis_rx, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK" *)
  input  logic                           s_axi_aclk,

  (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST" *)
  input  logic                           s_axi_aresetn,

  // AXI-Lite slave
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

  // AXI-Stream TX input (AXI clock domain)
  input  logic [7:0]                     s_axis_tx_tdata,
  input  logic                           s_axis_tx_tvalid,
  output logic                           s_axis_tx_tready,
  input  logic                           s_axis_tx_tlast,

  // AXI-Stream RX output (AXI clock domain)
  output logic [7:0]                     m_axis_rx_tdata,
  output logic                           m_axis_rx_tvalid,
  input  logic                           m_axis_rx_tready,
  output logic                           m_axis_rx_tlast,

  // PHY IO
  output logic [LANE_COUNT-1:0]          ir_tx_out,
  input  logic [LANE_COUNT-1:0]          ir_rx_in,
  output logic [LANE_COUNT-1:0]          ir_sd,
  output logic [LANE_COUNT-1:0]          ir_mode_out,
  input  logic [31:0]                    ext_phy_dbg
);

  localparam logic [LANE_COUNT-1:0] DEFAULT_LANE_MASK = {LANE_COUNT{1'b1}};
  localparam int STICKY_W = 9;

  // -----------------------------
  // AXI-domain configuration
  // -----------------------------
  logic cfg_enable_axi;
  logic [15:0] cfg_session_id_axi;
  logic [LANE_COUNT-1:0] cfg_lane_enable_mask_axi;
  logic [LANE_COUNT-1:0] cfg_rx_lane_enable_mask_axi;
  logic cfg_commit_toggle_axi;
  logic [STICKY_W-1:0] sticky_clear_toggle_axi;

  // -----------------------------
  // PHY-domain committed config
  // -----------------------------
  logic cfg_enable_sync;
  logic [15:0] cfg_session_sync;
  logic [LANE_COUNT-1:0] cfg_lane_mask_sync;
  logic [LANE_COUNT-1:0] cfg_rx_lane_mask_sync;
  logic cfg_commit_toggle_phy;
  logic cfg_commit_toggle_phy_d;

  logic cfg_enable_phy;
  logic [15:0] cfg_session_id_phy;
  logic [LANE_COUNT-1:0] cfg_lane_enable_mask_phy;
  logic [LANE_COUNT-1:0] cfg_rx_lane_enable_mask_phy;

  // -----------------------------
  // Sticky clear CDC
  // -----------------------------
  logic [STICKY_W-1:0] sticky_clear_toggle_phy;
  logic [STICKY_W-1:0] sticky_clear_toggle_phy_d;
  logic [STICKY_W-1:0] sticky_clear_pulse_phy;

  // -----------------------------
  // PHY-domain status/debug
  // -----------------------------
  logic tx_packet_active_phy;
  logic tx_packet_loading_phy;
  logic tx_done_pulse_phy;
  logic tx_error_overflow_phy;
  logic tx_error_retry_exhausted_phy;

  logic rx_ctx_valid_phy;
  logic rx_ctx_complete_phy;
  logic rx_done_pulse_phy;
  logic rx_header_error_phy;
  logic rx_protocol_error_phy;
  logic rx_frame_overflow_phy;
  logic rx_crc_error_phy;
  logic rx_overrun_error_phy;

  logic [LANE_COUNT-1:0] lane_tx_busy_dbg_phy;
  logic [LANE_COUNT-1:0] lane_tx_load_pulse_phy;
  logic [LANE_COUNT-1:0] lane_rx_frame_pulse_phy;
  logic [LANE_COUNT-1:0] lane_rx_crc_error_pulse_phy;
  logic [LANE_COUNT-1:0] lane_rx_error_pulse_phy;
  logic [32*LANE_COUNT-1:0] lane_rx_debug_status_phy;
  logic [MAX_FRAGS-1:0]  tx_frag_pending_dbg_phy;
  logic [MAX_FRAGS-1:0]  tx_frag_inflight_dbg_phy;
  logic [MAX_FRAGS-1:0]  tx_frag_acked_dbg_phy;
  logic [MAX_FRAGS-1:0]  rx_recv_bitmap_dbg_phy;
  logic [31:0]           rx_debug_status_phy;

  logic [STICKY_W-1:0] sticky_status_phy;
  logic [31:0] tx_lane_count_phy;
  logic [31:0] rx_lane_good_count_phy;
  logic [31:0] rx_lane_crc_count_phy;
  logic [31:0] rx_lane_err_count_phy;
  logic [7:0]  phy_lane0_tx_edge_count_phy;
  logic [7:0]  phy_lane0_rx_edge_count_phy;
  logic        phy_lane0_tx_d_phy;
  logic        phy_lane0_rx_d_phy;
  logic [31:0] phy_lane0_rx_debug_phy;
  logic [31:0] phy_lane0_dbg_phy;

  // -----------------------------
  // AXI-domain synced status/debug
  // -----------------------------
  logic [STICKY_W-1:0] sticky_status_axi;
  logic tx_packet_active_axi;
  logic tx_packet_loading_axi;
  logic rx_ctx_valid_axi;
  logic rx_ctx_complete_axi;

  logic [LANE_COUNT-1:0] lane_tx_busy_dbg_axi;
  logic [MAX_FRAGS-1:0]  tx_frag_pending_dbg_axi;
  logic [MAX_FRAGS-1:0]  tx_frag_inflight_dbg_axi;
  logic [MAX_FRAGS-1:0]  tx_frag_acked_dbg_axi;
  logic [MAX_FRAGS-1:0]  rx_recv_bitmap_dbg_axi;
  logic [31:0] tx_lane_count_axi;
  logic [31:0] rx_lane_good_count_axi;
  logic [31:0] rx_lane_crc_count_axi;
  logic [31:0] rx_lane_err_count_axi;
  logic [31:0] phy_lane0_dbg_axi;
  logic [STICKY_W-1:0] obs_clear_toggle_axi_d;
  logic obs_clear_pulse_axi;
  logic obs_rx_fire_axi;
  logic [31:0] obs_core_rx_tvalid_count_axi;
  logic [31:0] obs_core_rx_tready_count_axi;
  logic [31:0] obs_core_rx_tlast_count_axi;
  logic [31:0] obs_core_rx_byte_count_axi;
  logic [31:0] obs_mux_rx_tvalid_count_axi;
  logic [31:0] obs_mux_rx_tlast_count_axi;
  logic [31:0] obs_mux_rx_byte_count_axi;

  // -----------------------------
  // Stream bridge signals
  // -----------------------------
  logic [7:0] tx_phy_tdata;
  logic       tx_phy_tvalid;
  logic       tx_phy_tready;
  logic       tx_phy_tlast;

  logic [7:0] rx_phy_tdata;
  logic       rx_phy_tvalid;
  logic       rx_phy_tready;
  logic       rx_phy_tlast;

  // Async FIFO resets
  logic tx_fifo_rst;
  logic rx_fifo_rst;

  assign tx_fifo_rst = ~s_axi_aresetn;
  assign rx_fifo_rst = ~rst_n;

  function automatic logic [31:0] inc_lane_counts(
    input logic [31:0] current,
    input logic [LANE_COUNT-1:0] pulses
  );
    logic [31:0] next_counts;
    logic [7:0] lane_count;
    integer i;
    begin
      next_counts = current;
      for (i = 0; i < LANE_COUNT && i < 4; i = i + 1) begin
        lane_count = current[(8*i) +: 8];
        if (pulses[i] && lane_count != 8'hff) begin
          next_counts[(8*i) +: 8] = lane_count + 8'd1;
        end
      end
      inc_lane_counts = next_counts;
    end
  endfunction

  // ------------------------------------------
  // AXI-Lite register block
  // ------------------------------------------
  ir_axi_regs #(
    .C_S_AXI_DATA_WIDTH(C_S_AXI_DATA_WIDTH),
    .C_S_AXI_ADDR_WIDTH(C_S_AXI_ADDR_WIDTH),
    .LANE_COUNT        (LANE_COUNT),
    .MAX_FRAGS         (MAX_FRAGS)
  ) u_regs (
    .s_axi_aclk                  (s_axi_aclk),
    .s_axi_aresetn               (s_axi_aresetn),
    .s_axi_awaddr                (s_axi_awaddr),
    .s_axi_awvalid               (s_axi_awvalid),
    .s_axi_awready               (s_axi_awready),
    .s_axi_wdata                 (s_axi_wdata),
    .s_axi_wstrb                 (s_axi_wstrb),
    .s_axi_wvalid                (s_axi_wvalid),
    .s_axi_wready                (s_axi_wready),
    .s_axi_bresp                 (s_axi_bresp),
    .s_axi_bvalid                (s_axi_bvalid),
    .s_axi_bready                (s_axi_bready),
    .s_axi_araddr                (s_axi_araddr),
    .s_axi_arvalid               (s_axi_arvalid),
    .s_axi_arready               (s_axi_arready),
    .s_axi_rdata                 (s_axi_rdata),
    .s_axi_rresp                 (s_axi_rresp),
    .s_axi_rvalid                (s_axi_rvalid),
    .s_axi_rready                (s_axi_rready),

    .cfg_enable                  (cfg_enable_axi),
    .cfg_session_id              (cfg_session_id_axi),
    .cfg_lane_enable_mask        (cfg_lane_enable_mask_axi),
    .cfg_rx_lane_enable_mask     (cfg_rx_lane_enable_mask_axi),
    .cfg_commit_toggle           (cfg_commit_toggle_axi),
    .sticky_clear_toggle         (sticky_clear_toggle_axi),

    .tx_packet_active            (tx_packet_active_axi),
    .tx_packet_loading           (tx_packet_loading_axi),
    .rx_ctx_valid                (rx_ctx_valid_axi),
    .rx_ctx_complete             (rx_ctx_complete_axi),

    .sticky_tx_done              (sticky_status_axi[0]),
    .sticky_rx_done              (sticky_status_axi[1]),
    .sticky_tx_overflow          (sticky_status_axi[2]),
    .sticky_tx_retry_exhausted   (sticky_status_axi[3]),
    .sticky_rx_header_error      (sticky_status_axi[4]),
    .sticky_rx_protocol_error    (sticky_status_axi[5]),
    .sticky_rx_frame_overflow    (sticky_status_axi[6]),
    .sticky_rx_crc_error         (sticky_status_axi[7]),
    .sticky_rx_overrun_error     (sticky_status_axi[8]),

    .lane_tx_busy_dbg            (lane_tx_busy_dbg_axi),
    .tx_frag_pending_dbg         (tx_frag_pending_dbg_axi),
    .tx_frag_inflight_dbg        (tx_frag_inflight_dbg_axi),
    .tx_frag_acked_dbg           (tx_frag_acked_dbg_axi),
    .rx_recv_bitmap_dbg          (rx_recv_bitmap_dbg_axi),
    .tx_lane_count_dbg           (tx_lane_count_axi),
    .rx_lane_good_count_dbg      (rx_lane_good_count_axi),
    .rx_lane_crc_count_dbg       (rx_lane_crc_count_axi),
    .rx_lane_err_count_dbg       (rx_lane_err_count_axi),
    .phy_lane0_dbg               (phy_lane0_dbg_axi),
    .obs_core_rx_tvalid_count_dbg(obs_core_rx_tvalid_count_axi),
    .obs_core_rx_tready_count_dbg(obs_core_rx_tready_count_axi),
    .obs_core_rx_tlast_count_dbg (obs_core_rx_tlast_count_axi),
    .obs_core_rx_byte_count_dbg  (obs_core_rx_byte_count_axi),
    .obs_synth_rx_tvalid_count_dbg(32'h0000_0000),
    .obs_synth_rx_tlast_count_dbg (32'h0000_0000),
    .obs_synth_rx_byte_count_dbg  (32'h0000_0000),
    .obs_mux_rx_tvalid_count_dbg  (obs_mux_rx_tvalid_count_axi),
    .obs_mux_rx_tlast_count_dbg   (obs_mux_rx_tlast_count_axi),
    .obs_mux_rx_byte_count_dbg    (obs_mux_rx_byte_count_axi)
  );

  // ------------------------------------------
  // AXI -> PHY configuration CDC
  // Values are held stable in AXI domain and
  // latched in PHY domain on commit toggle edge.
  // ------------------------------------------
  cdc_sync #(.WIDTH(1))          u_cfg_en_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_enable_axi),
    .data_out(cfg_enable_sync)
  );

  cdc_sync #(.WIDTH(16))         u_cfg_sid_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_session_id_axi),
    .data_out(cfg_session_sync)
  );

  cdc_sync #(.WIDTH(LANE_COUNT)) u_cfg_mask_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_lane_enable_mask_axi),
    .data_out(cfg_lane_mask_sync)
  );

  cdc_sync #(.WIDTH(LANE_COUNT)) u_cfg_rx_mask_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_rx_lane_enable_mask_axi),
    .data_out(cfg_rx_lane_mask_sync)
  );

  cdc_sync #(.WIDTH(1))          u_cfg_commit_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (cfg_commit_toggle_axi),
    .data_out(cfg_commit_toggle_phy)
  );

  cdc_sync #(.WIDTH(STICKY_W))   u_clear_toggle_sync (
    .clk_dst (clk_phy),
    .rst_n   (rst_n),
    .data_in (sticky_clear_toggle_axi),
    .data_out(sticky_clear_toggle_phy)
  );

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      cfg_commit_toggle_phy_d   <= 1'b0;
      cfg_enable_phy            <= 1'b0;
      cfg_session_id_phy        <= 16'h0001;
      cfg_lane_enable_mask_phy  <= DEFAULT_LANE_MASK;
      cfg_rx_lane_enable_mask_phy <= DEFAULT_LANE_MASK;
      sticky_clear_toggle_phy_d <= '0;
    end else begin
      cfg_commit_toggle_phy_d   <= cfg_commit_toggle_phy;
      sticky_clear_toggle_phy_d <= sticky_clear_toggle_phy;

      if (cfg_commit_toggle_phy ^ cfg_commit_toggle_phy_d) begin
        cfg_enable_phy           <= cfg_enable_sync;
        cfg_session_id_phy       <= cfg_session_sync;
        cfg_lane_enable_mask_phy <= cfg_lane_mask_sync;
        cfg_rx_lane_enable_mask_phy <= cfg_rx_lane_mask_sync;
      end
    end
  end

  assign sticky_clear_pulse_phy = sticky_clear_toggle_phy ^ sticky_clear_toggle_phy_d;

  // ------------------------------------------
  // Sticky status in PHY domain
  // ------------------------------------------
  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      sticky_status_phy <= '0;
    end else begin
      if (tx_done_pulse_phy)            sticky_status_phy[0] <= 1'b1;
      if (rx_done_pulse_phy)            sticky_status_phy[1] <= 1'b1;
      if (tx_error_overflow_phy)        sticky_status_phy[2] <= 1'b1;
      if (tx_error_retry_exhausted_phy) sticky_status_phy[3] <= 1'b1;
      if (rx_header_error_phy)          sticky_status_phy[4] <= 1'b1;
      if (rx_protocol_error_phy)        sticky_status_phy[5] <= 1'b1;
      if (rx_frame_overflow_phy)        sticky_status_phy[6] <= 1'b1;
      if (rx_crc_error_phy)             sticky_status_phy[7] <= 1'b1;
      if (rx_overrun_error_phy)         sticky_status_phy[8] <= 1'b1;

      if (sticky_clear_pulse_phy[0])    sticky_status_phy[0] <= 1'b0;
      if (sticky_clear_pulse_phy[1])    sticky_status_phy[1] <= 1'b0;
      if (sticky_clear_pulse_phy[2])    sticky_status_phy[2] <= 1'b0;
      if (sticky_clear_pulse_phy[3])    sticky_status_phy[3] <= 1'b0;
      if (sticky_clear_pulse_phy[4])    sticky_status_phy[4] <= 1'b0;
      if (sticky_clear_pulse_phy[5])    sticky_status_phy[5] <= 1'b0;
      if (sticky_clear_pulse_phy[6])    sticky_status_phy[6] <= 1'b0;
      if (sticky_clear_pulse_phy[7])    sticky_status_phy[7] <= 1'b0;
      if (sticky_clear_pulse_phy[8])    sticky_status_phy[8] <= 1'b0;
    end
  end

  always_ff @(posedge clk_phy) begin
    if (!rst_n || (|sticky_clear_pulse_phy)) begin
      tx_lane_count_phy      <= 32'h0000_0000;
      rx_lane_good_count_phy <= 32'h0000_0000;
      rx_lane_crc_count_phy  <= 32'h0000_0000;
      rx_lane_err_count_phy  <= 32'h0000_0000;
      phy_lane0_tx_edge_count_phy <= 8'h00;
      phy_lane0_rx_edge_count_phy <= 8'h00;
      phy_lane0_tx_d_phy <= 1'b0;
      phy_lane0_rx_d_phy <= 1'b0;
    end else begin
      tx_lane_count_phy      <= inc_lane_counts(tx_lane_count_phy, lane_tx_load_pulse_phy);
      rx_lane_good_count_phy <= inc_lane_counts(rx_lane_good_count_phy, lane_rx_frame_pulse_phy);
      rx_lane_crc_count_phy  <= inc_lane_counts(rx_lane_crc_count_phy, lane_rx_crc_error_pulse_phy);
      rx_lane_err_count_phy  <= inc_lane_counts(rx_lane_err_count_phy, lane_rx_error_pulse_phy);
      phy_lane0_tx_d_phy <= ir_tx_out[0];
      phy_lane0_rx_d_phy <= ir_rx_in[0];
      if ((ir_tx_out[0] ^ phy_lane0_tx_d_phy) && phy_lane0_tx_edge_count_phy != 8'hff) begin
        phy_lane0_tx_edge_count_phy <= phy_lane0_tx_edge_count_phy + 8'd1;
      end
      if ((ir_rx_in[0] ^ phy_lane0_rx_d_phy) && phy_lane0_rx_edge_count_phy != 8'hff) begin
        phy_lane0_rx_edge_count_phy <= phy_lane0_rx_edge_count_phy + 8'd1;
      end
    end
  end

  assign phy_lane0_rx_debug_phy = lane_rx_debug_status_phy[31:0];

  assign phy_lane0_dbg_phy = (ext_phy_dbg[31:28] == 4'hE) ? ext_phy_dbg :
    ((rx_debug_status_phy[31:28] == 4'hD) ? rx_debug_status_phy :
    ((phy_lane0_rx_debug_phy != 32'h0000_0000) ? phy_lane0_rx_debug_phy :
    ((ext_phy_dbg != 32'h0000_0000) ? ext_phy_dbg : {
    12'h000,
    ir_mode_out[0],
    ir_sd[0],
    ir_rx_in[0],
    ir_tx_out[0],
    phy_lane0_rx_edge_count_phy,
    phy_lane0_tx_edge_count_phy
  })));

  // ------------------------------------------
  // AXIS CDC bridges
  // AXI side runs on s_axi_aclk
  // PHY side runs on clk_phy
  // ------------------------------------------
  ir_axis_async_fifo #(
    .DATA_W(8),
    .DEPTH (TX_ASYNC_FIFO_DEPTH)
  ) u_tx_async_fifo (
    .rst     (tx_fifo_rst),
    .s_clk   (s_axi_aclk),
    .s_tdata (s_axis_tx_tdata),
    .s_tvalid(s_axis_tx_tvalid),
    .s_tready(s_axis_tx_tready),
    .s_tlast (s_axis_tx_tlast),
    .m_clk   (clk_phy),
    .m_tdata (tx_phy_tdata),
    .m_tvalid(tx_phy_tvalid),
    .m_tready(tx_phy_tready),
    .m_tlast (tx_phy_tlast)
  );

  ir_axis_async_fifo #(
    .DATA_W(8),
    .DEPTH (RX_ASYNC_FIFO_DEPTH)
  ) u_rx_async_fifo (
    .rst     (rx_fifo_rst),
    .s_clk   (clk_phy),
    .s_tdata (rx_phy_tdata),
    .s_tvalid(rx_phy_tvalid),
    .s_tready(rx_phy_tready),
    .s_tlast (rx_phy_tlast),
    .m_clk   (s_axi_aclk),
    .m_tdata (m_axis_rx_tdata),
    .m_tvalid(m_axis_rx_tvalid),
    .m_tready(m_axis_rx_tready),
    .m_tlast (m_axis_rx_tlast)
  );

  assign obs_clear_pulse_axi = |(sticky_clear_toggle_axi ^ obs_clear_toggle_axi_d);
  assign obs_rx_fire_axi = m_axis_rx_tvalid && m_axis_rx_tready;

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      obs_clear_toggle_axi_d <= '0;
      obs_core_rx_tvalid_count_axi <= 32'h0000_0000;
      obs_core_rx_tready_count_axi <= 32'h0000_0000;
      obs_core_rx_tlast_count_axi <= 32'h0000_0000;
      obs_core_rx_byte_count_axi <= 32'h0000_0000;
      obs_mux_rx_tvalid_count_axi <= 32'h0000_0000;
      obs_mux_rx_tlast_count_axi <= 32'h0000_0000;
      obs_mux_rx_byte_count_axi <= 32'h0000_0000;
    end else begin
      obs_clear_toggle_axi_d <= sticky_clear_toggle_axi;
      if (obs_clear_pulse_axi) begin
        obs_core_rx_tvalid_count_axi <= 32'h0000_0000;
        obs_core_rx_tready_count_axi <= 32'h0000_0000;
        obs_core_rx_tlast_count_axi <= 32'h0000_0000;
        obs_core_rx_byte_count_axi <= 32'h0000_0000;
        obs_mux_rx_tvalid_count_axi <= 32'h0000_0000;
        obs_mux_rx_tlast_count_axi <= 32'h0000_0000;
        obs_mux_rx_byte_count_axi <= 32'h0000_0000;
      end else begin
        if (m_axis_rx_tvalid) obs_core_rx_tvalid_count_axi <= obs_core_rx_tvalid_count_axi + 1'b1;
        if (obs_rx_fire_axi) obs_core_rx_tready_count_axi <= obs_core_rx_tready_count_axi + 1'b1;
        if (obs_rx_fire_axi && m_axis_rx_tlast) obs_core_rx_tlast_count_axi <= obs_core_rx_tlast_count_axi + 1'b1;
        if (obs_rx_fire_axi) obs_core_rx_byte_count_axi <= obs_core_rx_byte_count_axi + 1'b1;
        if (m_axis_rx_tvalid) obs_mux_rx_tvalid_count_axi <= obs_mux_rx_tvalid_count_axi + 1'b1;
        if (obs_rx_fire_axi && m_axis_rx_tlast) obs_mux_rx_tlast_count_axi <= obs_mux_rx_tlast_count_axi + 1'b1;
        if (obs_rx_fire_axi) obs_mux_rx_byte_count_axi <= obs_mux_rx_byte_count_axi + 1'b1;
      end
    end
  end

  // ------------------------------------------
  // PHY -> AXI status/debug CDC
  // ------------------------------------------
  cdc_sync #(.WIDTH(1))          u_st0 (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_packet_active_phy),
    .data_out(tx_packet_active_axi)
  );

  cdc_sync #(.WIDTH(1))          u_st1 (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_packet_loading_phy),
    .data_out(tx_packet_loading_axi)
  );

  cdc_sync #(.WIDTH(1))          u_st2 (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_ctx_valid_phy),
    .data_out(rx_ctx_valid_axi)
  );

  cdc_sync #(.WIDTH(1))          u_st3 (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_ctx_complete_phy),
    .data_out(rx_ctx_complete_axi)
  );

  cdc_sync #(.WIDTH(STICKY_W))   u_stk (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (sticky_status_phy),
    .data_out(sticky_status_axi)
  );

  cdc_sync #(.WIDTH(LANE_COUNT)) u_busy (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (lane_tx_busy_dbg_phy),
    .data_out(lane_tx_busy_dbg_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS))  u_pend (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_frag_pending_dbg_phy),
    .data_out(tx_frag_pending_dbg_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS))  u_iflt (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_frag_inflight_dbg_phy),
    .data_out(tx_frag_inflight_dbg_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS))  u_ackd (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_frag_acked_dbg_phy),
    .data_out(tx_frag_acked_dbg_axi)
  );

  cdc_sync #(.WIDTH(MAX_FRAGS))  u_recv (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_recv_bitmap_dbg_phy),
    .data_out(rx_recv_bitmap_dbg_axi)
  );

  cdc_sync #(.WIDTH(32))         u_tx_lane_count (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (tx_lane_count_phy),
    .data_out(tx_lane_count_axi)
  );

  cdc_sync #(.WIDTH(32))         u_rx_lane_good_count (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_lane_good_count_phy),
    .data_out(rx_lane_good_count_axi)
  );

  cdc_sync #(.WIDTH(32))         u_rx_lane_crc_count (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_lane_crc_count_phy),
    .data_out(rx_lane_crc_count_axi)
  );

  cdc_sync #(.WIDTH(32))         u_rx_lane_err_count (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (rx_lane_err_count_phy),
    .data_out(rx_lane_err_count_axi)
  );

  cdc_sync #(.WIDTH(32))         u_phy_lane0_dbg (
    .clk_dst (s_axi_aclk),
    .rst_n   (s_axi_aresetn),
    .data_in (phy_lane0_dbg_phy),
    .data_out(phy_lane0_dbg_axi)
  );

  // ------------------------------------------
  // Core array top
  // ------------------------------------------
  ir_array_top #(
    .LANE_COUNT                (LANE_COUNT),
    .MAX_PACKET_BYTES          (MAX_PACKET_BYTES),
    .FRAGMENT_BYTES            (FRAGMENT_BYTES),
    .MAX_RETRY                 (MAX_RETRY),
    .CNT_CHIP_MAX              (CNT_CHIP_MAX),
    .CNT_PREAMBLE              (CNT_PREAMBLE),
    .EOF_SILENCE_SYMS          (EOF_SILENCE_SYMS),
    .FRAG_TIMEOUT_CYCLES       (FRAG_TIMEOUT_CYCLES),
    .TX_POST_ACK_GUARD_CYCLES  (TX_POST_ACK_GUARD_CYCLES),
    .RX_TO_TX_GUARD_CYCLES     (RX_TO_TX_GUARD_CYCLES),
    .REASSEMBLY_TIMEOUT_CYCLES (REASSEMBLY_TIMEOUT_CYCLES),
    .MAX_FRAGS                 (MAX_FRAGS),
    .MAX_FRAME_BYTES           (MAX_FRAME_BYTES)
  ) u_top (
    .clk_phy                  (clk_phy),
    .rst_n                    (rst_n),
    .enable                   (cfg_enable_phy),
    .session_id               (cfg_session_id_phy),
    .lane_enable_mask         (cfg_lane_enable_mask_phy),
    .rx_lane_enable_mask      (cfg_rx_lane_enable_mask_phy),

    .s_axis_tx_tdata          (tx_phy_tdata),
    .s_axis_tx_tvalid         (tx_phy_tvalid),
    .s_axis_tx_tready         (tx_phy_tready),
    .s_axis_tx_tlast          (tx_phy_tlast),

    .m_axis_rx_tdata          (rx_phy_tdata),
    .m_axis_rx_tvalid         (rx_phy_tvalid),
    .m_axis_rx_tready         (rx_phy_tready),
    .m_axis_rx_tlast          (rx_phy_tlast),

    .ir_tx_out                (ir_tx_out),
    .ir_rx_in                 (ir_rx_in),
    .ir_sd                    (ir_sd),
    .ir_mode_out              (ir_mode_out),

    .tx_packet_active         (tx_packet_active_phy),
    .tx_packet_loading        (tx_packet_loading_phy),
    .tx_done_pulse            (tx_done_pulse_phy),
    .tx_error_overflow        (tx_error_overflow_phy),
    .tx_error_retry_exhausted (tx_error_retry_exhausted_phy),

    .rx_ctx_valid             (rx_ctx_valid_phy),
    .rx_ctx_complete          (rx_ctx_complete_phy),
    .rx_done_pulse            (rx_done_pulse_phy),
    .rx_header_error          (rx_header_error_phy),
    .rx_protocol_error        (rx_protocol_error_phy),
    .rx_frame_overflow_any    (rx_frame_overflow_phy),
    .rx_crc_error_any         (rx_crc_error_phy),
    .rx_overrun_error_any     (rx_overrun_error_phy),

    .lane_tx_busy_dbg         (lane_tx_busy_dbg_phy),
    .lane_tx_load_pulse_dbg   (lane_tx_load_pulse_phy),
    .lane_rx_frame_pulse_dbg  (lane_rx_frame_pulse_phy),
    .lane_rx_crc_error_dbg    (lane_rx_crc_error_pulse_phy),
    .lane_rx_error_dbg        (lane_rx_error_pulse_phy),
    .lane_rx_debug_status_dbg (lane_rx_debug_status_phy),
    .tx_frag_pending_dbg      (tx_frag_pending_dbg_phy),
    .tx_frag_inflight_dbg     (tx_frag_inflight_dbg_phy),
    .tx_frag_acked_dbg        (tx_frag_acked_dbg_phy),
    .rx_recv_bitmap_dbg       (rx_recv_bitmap_dbg_phy),
    .rx_debug_status_dbg      (rx_debug_status_phy)
  );

endmodule

module ir_array_top_axi #(
  parameter int LANE_COUNT                = 4,
  parameter int MAX_PACKET_BYTES          = 256,
  parameter int FRAGMENT_BYTES            = 16,
  parameter int MAX_RETRY                 = (LANE_COUNT > 4) ? (LANE_COUNT * ((MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES)) : 4,
  parameter int CNT_CHIP_MAX              = 7,
  parameter int CNT_PREAMBLE              = 16,
  parameter int EOF_SILENCE_SYMS          = 3,
  parameter int FRAG_TIMEOUT_CYCLES       = 50000,
  parameter int TX_POST_ACK_GUARD_CYCLES  = 8192,
  parameter int RX_TO_TX_GUARD_CYCLES     = 8192,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = (LANE_COUNT > 4) ? (((MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES) * (MAX_RETRY + 2) * FRAG_TIMEOUT_CYCLES) : 200000,
  parameter int MAX_FRAGS                 = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int MAX_FRAME_BYTES           = (14 + FRAGMENT_BYTES),
  parameter int TX_ASYNC_FIFO_DEPTH       = 1024,
  parameter int RX_ASYNC_FIFO_DEPTH       = 1024,
  parameter int C_S_AXI_DATA_WIDTH        = 32,
  parameter int C_S_AXI_ADDR_WIDTH        = 6,
  parameter int TX_ONLY_ACK_MODE          = 0,
  parameter int STREAM_FULL_MODE          = 0,
  parameter int STREAM_TX_REQUIRE_ACK     = 1,
  parameter int PARALLEL_2LANE_MODE       = 0,
  parameter int STREAM_NODE_ID            = 0,
  parameter int RX_DATA_PHASE_DELAY_CYCLES = 0,
  parameter int RX_DETECT_START_CYCLES    = 0,
  parameter int RX_DETECT_END_CYCLES      = (CNT_CHIP_MAX >= 15) ? 10 : ((CNT_CHIP_MAX >= 7) ? (CNT_CHIP_MAX - 2) : CNT_CHIP_MAX),
  parameter int RX_PREAMBLE_REALIGN_EDGE  = 0,
  parameter int STREAM_PHY_DBG_SELECT      = 0,
  parameter int FORCE_SD_SHUTDOWN          = 0,
  parameter int RX_SELF_BLANK_CYCLES      = (CNT_CHIP_MAX >= 15) ? 8 : ((CNT_CHIP_MAX >= 7) ? 4 : 1)
)(
  input  logic                           clk_phy,
  input  logic                           rst_n,

  (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aclk, ASSOCIATED_BUSIF s_axi:s_axis_tx:m_axis_rx, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 100000000" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK" *)
  input  logic                           s_axi_aclk,

  (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axi_aresetn, POLARITY ACTIVE_LOW" *)
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST" *)
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
  generate
    if (TX_ONLY_ACK_MODE != 0) begin : g_tx_only
      ir_txonly_ack_axi #(
        .LANE_COUNT               (LANE_COUNT),
        .MAX_PACKET_BYTES         (MAX_PACKET_BYTES),
        .FRAGMENT_BYTES           (FRAGMENT_BYTES),
        .MAX_RETRY                (MAX_RETRY),
        .CNT_CHIP_MAX             (CNT_CHIP_MAX),
        .CNT_PREAMBLE             (CNT_PREAMBLE),
        .EOF_SILENCE_SYMS         (EOF_SILENCE_SYMS),
        .FRAG_TIMEOUT_CYCLES      (FRAG_TIMEOUT_CYCLES),
        .POST_ACK_GUARD_CYCLES    (TX_POST_ACK_GUARD_CYCLES),
        .MAX_FRAGS                (MAX_FRAGS),
        .TX_ASYNC_FIFO_DEPTH      (TX_ASYNC_FIFO_DEPTH),
        .C_S_AXI_DATA_WIDTH       (C_S_AXI_DATA_WIDTH),
        .C_S_AXI_ADDR_WIDTH       (C_S_AXI_ADDR_WIDTH)
      ) u_tx_only (
        .clk_phy          (clk_phy),
        .rst_n            (rst_n),
        .s_axi_aclk       (s_axi_aclk),
        .s_axi_aresetn    (s_axi_aresetn),
        .s_axi_awaddr     (s_axi_awaddr),
        .s_axi_awvalid    (s_axi_awvalid),
        .s_axi_awready    (s_axi_awready),
        .s_axi_wdata      (s_axi_wdata),
        .s_axi_wstrb      (s_axi_wstrb),
        .s_axi_wvalid     (s_axi_wvalid),
        .s_axi_wready     (s_axi_wready),
        .s_axi_bresp      (s_axi_bresp),
        .s_axi_bvalid     (s_axi_bvalid),
        .s_axi_bready     (s_axi_bready),
        .s_axi_araddr     (s_axi_araddr),
        .s_axi_arvalid    (s_axi_arvalid),
        .s_axi_arready    (s_axi_arready),
        .s_axi_rdata      (s_axi_rdata),
        .s_axi_rresp      (s_axi_rresp),
        .s_axi_rvalid     (s_axi_rvalid),
        .s_axi_rready     (s_axi_rready),
        .s_axis_tx_tdata  (s_axis_tx_tdata),
        .s_axis_tx_tvalid (s_axis_tx_tvalid),
        .s_axis_tx_tready (s_axis_tx_tready),
        .s_axis_tx_tlast  (s_axis_tx_tlast),
        .m_axis_rx_tdata  (m_axis_rx_tdata),
        .m_axis_rx_tvalid (m_axis_rx_tvalid),
        .m_axis_rx_tready (m_axis_rx_tready),
        .m_axis_rx_tlast  (m_axis_rx_tlast),
        .ir_tx_out        (ir_tx_out),
        .ir_rx_in         (ir_rx_in),
        .ir_sd            (ir_sd),
        .ir_mode_out      (ir_mode_out),
        .ext_phy_dbg      (ext_phy_dbg)
      );
    end else if (STREAM_FULL_MODE != 0) begin : g_stream_full
      ir_stream_array_top_axi #(
        .LANE_COUNT                (LANE_COUNT),
        .STREAM_NODE_ID            (STREAM_NODE_ID),
        .MAX_PACKET_BYTES          (MAX_PACKET_BYTES),
        .FRAGMENT_BYTES            (FRAGMENT_BYTES),
        .MAX_RETRY                 (MAX_RETRY),
        .CNT_CHIP_MAX              (CNT_CHIP_MAX),
        .CNT_PREAMBLE              (CNT_PREAMBLE),
        .EOF_SILENCE_SYMS          (EOF_SILENCE_SYMS),
        .RX_DATA_PHASE_DELAY_CYCLES(RX_DATA_PHASE_DELAY_CYCLES),
        .RX_DETECT_START_CYCLES    (RX_DETECT_START_CYCLES),
        .RX_DETECT_END_CYCLES      (RX_DETECT_END_CYCLES),
        .RX_PREAMBLE_REALIGN_EDGE  (RX_PREAMBLE_REALIGN_EDGE),
        .STREAM_PHY_DBG_SELECT     (STREAM_PHY_DBG_SELECT),
        .FORCE_SD_SHUTDOWN         (FORCE_SD_SHUTDOWN),
        .RX_SELF_BLANK_CYCLES      (RX_SELF_BLANK_CYCLES),
        .PARALLEL_2LANE_MODE       (PARALLEL_2LANE_MODE),
        .TX_REQUIRE_ACK            (STREAM_TX_REQUIRE_ACK),
        .FRAG_TIMEOUT_CYCLES       (FRAG_TIMEOUT_CYCLES),
        .TX_POST_ACK_GUARD_CYCLES  (TX_POST_ACK_GUARD_CYCLES),
        .RX_TO_TX_GUARD_CYCLES     (RX_TO_TX_GUARD_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES (REASSEMBLY_TIMEOUT_CYCLES),
        .MAX_FRAGS                 (MAX_FRAGS),
        .MAX_FRAME_BYTES           (MAX_FRAME_BYTES),
        .TX_ASYNC_FIFO_DEPTH       (TX_ASYNC_FIFO_DEPTH),
        .RX_ASYNC_FIFO_DEPTH       (RX_ASYNC_FIFO_DEPTH),
        .C_S_AXI_DATA_WIDTH        (C_S_AXI_DATA_WIDTH),
        .C_S_AXI_ADDR_WIDTH        (C_S_AXI_ADDR_WIDTH)
      ) u_stream_full (
        .clk_phy          (clk_phy),
        .rst_n            (rst_n),
        .s_axi_aclk       (s_axi_aclk),
        .s_axi_aresetn    (s_axi_aresetn),
        .s_axi_awaddr     (s_axi_awaddr),
        .s_axi_awvalid    (s_axi_awvalid),
        .s_axi_awready    (s_axi_awready),
        .s_axi_wdata      (s_axi_wdata),
        .s_axi_wstrb      (s_axi_wstrb),
        .s_axi_wvalid     (s_axi_wvalid),
        .s_axi_wready     (s_axi_wready),
        .s_axi_bresp      (s_axi_bresp),
        .s_axi_bvalid     (s_axi_bvalid),
        .s_axi_bready     (s_axi_bready),
        .s_axi_araddr     (s_axi_araddr),
        .s_axi_arvalid    (s_axi_arvalid),
        .s_axi_arready    (s_axi_arready),
        .s_axi_rdata      (s_axi_rdata),
        .s_axi_rresp      (s_axi_rresp),
        .s_axi_rvalid     (s_axi_rvalid),
        .s_axi_rready     (s_axi_rready),
        .s_axis_tx_tdata  (s_axis_tx_tdata),
        .s_axis_tx_tvalid (s_axis_tx_tvalid),
        .s_axis_tx_tready (s_axis_tx_tready),
        .s_axis_tx_tlast  (s_axis_tx_tlast),
        .m_axis_rx_tdata  (m_axis_rx_tdata),
        .m_axis_rx_tvalid (m_axis_rx_tvalid),
        .m_axis_rx_tready (m_axis_rx_tready),
        .m_axis_rx_tlast  (m_axis_rx_tlast),
        .ir_tx_out        (ir_tx_out),
        .ir_rx_in         (ir_rx_in),
        .ir_sd            (ir_sd),
        .ir_mode_out      (ir_mode_out),
        .ext_phy_dbg      (ext_phy_dbg)
      );
    end else begin : g_full
      ir_array_top_axi_full #(
        .LANE_COUNT                (LANE_COUNT),
        .MAX_PACKET_BYTES          (MAX_PACKET_BYTES),
        .FRAGMENT_BYTES            (FRAGMENT_BYTES),
        .MAX_RETRY                 (MAX_RETRY),
        .CNT_CHIP_MAX              (CNT_CHIP_MAX),
        .CNT_PREAMBLE              (CNT_PREAMBLE),
        .EOF_SILENCE_SYMS          (EOF_SILENCE_SYMS),
        .FRAG_TIMEOUT_CYCLES       (FRAG_TIMEOUT_CYCLES),
        .TX_POST_ACK_GUARD_CYCLES  (TX_POST_ACK_GUARD_CYCLES),
        .RX_TO_TX_GUARD_CYCLES     (RX_TO_TX_GUARD_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES (REASSEMBLY_TIMEOUT_CYCLES),
        .MAX_FRAGS                 (MAX_FRAGS),
        .MAX_FRAME_BYTES           (MAX_FRAME_BYTES),
        .TX_ASYNC_FIFO_DEPTH       (TX_ASYNC_FIFO_DEPTH),
        .RX_ASYNC_FIFO_DEPTH       (RX_ASYNC_FIFO_DEPTH),
        .C_S_AXI_DATA_WIDTH        (C_S_AXI_DATA_WIDTH),
        .C_S_AXI_ADDR_WIDTH        (C_S_AXI_ADDR_WIDTH)
      ) u_full (
        .clk_phy          (clk_phy),
        .rst_n            (rst_n),
        .s_axi_aclk       (s_axi_aclk),
        .s_axi_aresetn    (s_axi_aresetn),
        .s_axi_awaddr     (s_axi_awaddr),
        .s_axi_awvalid    (s_axi_awvalid),
        .s_axi_awready    (s_axi_awready),
        .s_axi_wdata      (s_axi_wdata),
        .s_axi_wstrb      (s_axi_wstrb),
        .s_axi_wvalid     (s_axi_wvalid),
        .s_axi_wready     (s_axi_wready),
        .s_axi_bresp      (s_axi_bresp),
        .s_axi_bvalid     (s_axi_bvalid),
        .s_axi_bready     (s_axi_bready),
        .s_axi_araddr     (s_axi_araddr),
        .s_axi_arvalid    (s_axi_arvalid),
        .s_axi_arready    (s_axi_arready),
        .s_axi_rdata      (s_axi_rdata),
        .s_axi_rresp      (s_axi_rresp),
        .s_axi_rvalid     (s_axi_rvalid),
        .s_axi_rready     (s_axi_rready),
        .s_axis_tx_tdata  (s_axis_tx_tdata),
        .s_axis_tx_tvalid (s_axis_tx_tvalid),
        .s_axis_tx_tready (s_axis_tx_tready),
        .s_axis_tx_tlast  (s_axis_tx_tlast),
        .m_axis_rx_tdata  (m_axis_rx_tdata),
        .m_axis_rx_tvalid (m_axis_rx_tvalid),
        .m_axis_rx_tready (m_axis_rx_tready),
        .m_axis_rx_tlast  (m_axis_rx_tlast),
        .ir_tx_out        (ir_tx_out),
        .ir_rx_in         (ir_rx_in),
        .ir_sd            (ir_sd),
        .ir_mode_out      (ir_mode_out),
        .ext_phy_dbg      (ext_phy_dbg)
      );
    end
  endgenerate
endmodule
