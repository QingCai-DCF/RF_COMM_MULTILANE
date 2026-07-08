module ir_stream_array_top_axi #(
  parameter int LANE_COUNT                = 4,
  parameter int STREAM_NODE_ID            = 0,
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
  parameter int STREAM_PHY_DBG_SELECT      = 0,
  parameter int RX_SELF_BLANK_CYCLES      = (CNT_CHIP_MAX >= 15) ? 8 : ((CNT_CHIP_MAX >= 7) ? 4 : 1),
  parameter int FORCE_SD_SHUTDOWN         = 0,
  parameter int PARALLEL_2LANE_MODE       = 0,
  parameter int TX_REQUIRE_ACK            = 1,
  parameter int FRAG_TIMEOUT_CYCLES       = 50000,
  parameter int TX_POST_ACK_GUARD_CYCLES  = 8192,
  parameter int RX_TO_TX_GUARD_CYCLES     = 8192,
  parameter int REASSEMBLY_TIMEOUT_CYCLES = 200000,
  parameter int MAX_FRAGS                 = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES,
  parameter int MAX_FRAME_BYTES           = (14 + FRAGMENT_BYTES),
  parameter int TX_ASYNC_FIFO_DEPTH       = 1024,
  parameter int RX_ASYNC_FIFO_DEPTH       = 1024,
  parameter int C_S_AXI_DATA_WIDTH        = 32,
  parameter int C_S_AXI_ADDR_WIDTH        = 6
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
  localparam int STICKY_W = 9;
  localparam int APP_HDR_BYTES = 8;
  localparam logic [15:0] APP_HDR_BYTES_U16 = APP_HDR_BYTES;
  localparam int SYNTH_MAX_PAYLOAD_BYTES = (MAX_PACKET_BYTES > APP_HDR_BYTES) ? (MAX_PACKET_BYTES - APP_HDR_BYTES) : 1;
  localparam logic [15:0] SYNTH_MAX_PAYLOAD_BYTES_U16 = SYNTH_MAX_PAYLOAD_BYTES;
  localparam logic [LANE_COUNT-1:0] DEFAULT_LANE_MASK = {LANE_COUNT{1'b1}};

  logic cfg_enable_axi;
  logic [15:0] cfg_session_id_axi;
  logic [LANE_COUNT-1:0] cfg_lane_enable_mask_axi;
  logic [LANE_COUNT-1:0] cfg_rx_lane_enable_mask_axi;
  logic cfg_commit_toggle_axi;
  logic [STICKY_W-1:0] sticky_clear_toggle_axi;
  logic cfg_test_mode_enable_axi;
  logic test_rx_inject_pulse_axi;
  logic [15:0] test_rx_payload_bytes_axi;
  logic [7:0] test_rx_pattern_id_axi;
  logic [15:0] test_rx_seq_base_axi;
  logic [31:0] test_rx_packet_count_axi;

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

  logic [STICKY_W-1:0] sticky_clear_toggle_phy;
  logic [STICKY_W-1:0] sticky_clear_toggle_phy_d;
  logic [STICKY_W-1:0] sticky_clear_pulse_phy;
  logic [STICKY_W-1:0] sticky_status_phy;
  logic [STICKY_W-1:0] sticky_status_axi;

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
  logic [MAX_FRAGS-1:0] tx_frag_pending_dbg_phy;
  logic [MAX_FRAGS-1:0] tx_frag_inflight_dbg_phy;
  logic [MAX_FRAGS-1:0] tx_frag_acked_dbg_phy;
  logic [MAX_FRAGS-1:0] rx_recv_bitmap_dbg_phy;
  logic [31:0] stream_debug_phy;

  logic tx_packet_active_axi;
  logic tx_packet_loading_axi;
  logic rx_ctx_valid_axi;
  logic rx_ctx_complete_axi;
  logic [LANE_COUNT-1:0] lane_tx_busy_dbg_axi;
  logic [MAX_FRAGS-1:0] tx_frag_pending_dbg_axi;
  logic [MAX_FRAGS-1:0] tx_frag_inflight_dbg_axi;
  logic [MAX_FRAGS-1:0] tx_frag_acked_dbg_axi;
  logic [MAX_FRAGS-1:0] rx_recv_bitmap_dbg_axi;
  logic [31:0] tx_lane_count_phy;
  logic [31:0] tx_lane_load_count_phy;
  logic [31:0] tx_lane_edge_count_phy;
  logic [31:0] rx_lane_edge_count_phy;
  logic [31:0] rx_lane_good_count_phy;
  logic [31:0] rx_lane_crc_count_phy;
  logic [31:0] rx_lane_err_count_phy;
  logic [31:0] phy_lane0_dbg_phy;
  logic [31:0] tx_lane_count_axi;
  logic [31:0] rx_lane_good_count_axi;
  logic [31:0] rx_lane_crc_count_axi;
  logic [31:0] rx_lane_err_count_axi;
  logic [31:0] phy_lane0_dbg_axi;
  logic [32*LANE_COUNT-1:0] stream_lane_rx_debug_phy;
  logic [LANE_COUNT-1:0] ir_tx_out_d_phy;
  logic [LANE_COUNT-1:0] ir_rx_in_d_phy;
  logic [LANE_COUNT-1:0] lane_tx_edge_pulse_phy;
  logic [LANE_COUNT-1:0] lane_rx_edge_pulse_phy;
  logic [31:0] selected_rx_debug_phy;
  logic [7:0] selected_rx_edge_count_phy;
  logic [1:0] selected_rx_lane_index_phy;
  logic selected_rx_level_phy;
  logic [31:0] selected_rx_debug_latched_phy;
  logic [31:0] selected_rx_debug_observe_phy;
  logic [31:0] stream_debug_latched_phy;
  logic [31:0] stream_debug_observe_phy;
  logic stream_debug_interesting_phy;

  logic [7:0] tx_phy_tdata;
  logic       tx_phy_tvalid;
  logic       tx_phy_tready;
  logic       tx_phy_tlast;
  logic [7:0] rx_phy_tdata;
  logic       rx_phy_tvalid;
  logic       rx_phy_tready;
  logic       rx_phy_tlast;
  logic [7:0] core_m_axis_rx_tdata;
  logic       core_m_axis_rx_tvalid;
  logic       core_m_axis_rx_tready;
  logic       core_m_axis_rx_tlast;
  logic       synth_rx_active_axi;
  logic [15:0] synth_rx_payload_len_axi;
  logic [15:0] synth_rx_total_len_axi;
  logic [15:0] synth_rx_seq_axi;
  logic [7:0] synth_rx_pattern_axi;
  logic [15:0] synth_rx_idx_axi;
  logic       synth_rx_done_pulse_axi;
  logic [STICKY_W-1:0] obs_clear_toggle_axi_d;
  logic       obs_clear_pulse_axi;
  logic       obs_core_rx_fire_axi;
  logic       obs_synth_rx_fire_axi;
  logic       obs_mux_rx_fire_axi;
  logic [31:0] obs_core_rx_tvalid_count_axi;
  logic [31:0] obs_core_rx_tready_count_axi;
  logic [31:0] obs_core_rx_tlast_count_axi;
  logic [31:0] obs_core_rx_byte_count_axi;
  logic [31:0] obs_synth_rx_tvalid_count_axi;
  logic [31:0] obs_synth_rx_tlast_count_axi;
  logic [31:0] obs_synth_rx_byte_count_axi;
  logic [31:0] obs_mux_rx_tvalid_count_axi;
  logic [31:0] obs_mux_rx_tlast_count_axi;
  logic [31:0] obs_mux_rx_byte_count_axi;

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

  function automatic logic [31:0] pick_rx_lane_debug(
    input logic [32*LANE_COUNT-1:0] lane_debug,
    input logic [LANE_COUNT-1:0] rx_mask
  );
    logic found;
    integer i;
    begin
      found = 1'b0;
      pick_rx_lane_debug = lane_debug[31:0];
      for (i = 0; i < LANE_COUNT; i = i + 1) begin
        if (!found && rx_mask[i]) begin
          pick_rx_lane_debug = lane_debug[32*i +: 32];
          found = 1'b1;
        end
      end
    end
  endfunction

  function automatic logic [1:0] pick_rx_lane_index(
    input logic [LANE_COUNT-1:0] rx_mask
  );
    logic found;
    integer i;
    begin
      found = 1'b0;
      pick_rx_lane_index = 2'd0;
      for (i = 0; i < LANE_COUNT && i < 4; i = i + 1) begin
        if (!found && rx_mask[i]) begin
          pick_rx_lane_index = i[1:0];
          found = 1'b1;
        end
      end
    end
  endfunction

  function automatic logic pick_rx_lane_level(
    input logic [LANE_COUNT-1:0] rx_levels,
    input logic [LANE_COUNT-1:0] rx_mask
  );
    logic found;
    integer i;
    begin
      found = 1'b0;
      pick_rx_lane_level = rx_levels[0];
      for (i = 0; i < LANE_COUNT; i = i + 1) begin
        if (!found && rx_mask[i]) begin
          pick_rx_lane_level = rx_levels[i];
          found = 1'b1;
        end
      end
    end
  endfunction

  function automatic logic [7:0] synth_payload_byte(
    input logic [15:0] seq_i,
    input logic [15:0] payload_idx_i,
    input logic [7:0] pattern_i
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
    input logic [7:0] pattern_i
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

  assign synth_rx_total_len_axi = synth_rx_payload_len_axi + APP_HDR_BYTES_U16;
  assign core_m_axis_rx_tready = (!synth_rx_active_axi) && m_axis_rx_tready;
  assign m_axis_rx_tdata = synth_rx_active_axi ?
                           synth_rx_byte(synth_rx_idx_axi,
                                         synth_rx_payload_len_axi,
                                         synth_rx_seq_axi,
                                         synth_rx_pattern_axi) :
                           core_m_axis_rx_tdata;
  assign m_axis_rx_tvalid = synth_rx_active_axi ? 1'b1 : core_m_axis_rx_tvalid;
  assign m_axis_rx_tlast = synth_rx_active_axi ?
                           (synth_rx_idx_axi == (synth_rx_total_len_axi - 1'b1)) :
                           core_m_axis_rx_tlast;
  assign obs_clear_pulse_axi = |(sticky_clear_toggle_axi ^ obs_clear_toggle_axi_d);
  assign obs_core_rx_fire_axi = core_m_axis_rx_tvalid && core_m_axis_rx_tready;
  assign obs_synth_rx_fire_axi = synth_rx_active_axi && m_axis_rx_tready;
  assign obs_mux_rx_fire_axi = m_axis_rx_tvalid && m_axis_rx_tready;

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      obs_clear_toggle_axi_d <= '0;
      obs_core_rx_tvalid_count_axi <= 32'h0000_0000;
      obs_core_rx_tready_count_axi <= 32'h0000_0000;
      obs_core_rx_tlast_count_axi <= 32'h0000_0000;
      obs_core_rx_byte_count_axi <= 32'h0000_0000;
      obs_synth_rx_tvalid_count_axi <= 32'h0000_0000;
      obs_synth_rx_tlast_count_axi <= 32'h0000_0000;
      obs_synth_rx_byte_count_axi <= 32'h0000_0000;
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
        obs_synth_rx_tvalid_count_axi <= 32'h0000_0000;
        obs_synth_rx_tlast_count_axi <= 32'h0000_0000;
        obs_synth_rx_byte_count_axi <= 32'h0000_0000;
        obs_mux_rx_tvalid_count_axi <= 32'h0000_0000;
        obs_mux_rx_tlast_count_axi <= 32'h0000_0000;
        obs_mux_rx_byte_count_axi <= 32'h0000_0000;
      end else begin
        if (core_m_axis_rx_tvalid) obs_core_rx_tvalid_count_axi <= obs_core_rx_tvalid_count_axi + 1'b1;
        if (obs_core_rx_fire_axi) obs_core_rx_tready_count_axi <= obs_core_rx_tready_count_axi + 1'b1;
        if (obs_core_rx_fire_axi && core_m_axis_rx_tlast) obs_core_rx_tlast_count_axi <= obs_core_rx_tlast_count_axi + 1'b1;
        if (obs_core_rx_fire_axi) obs_core_rx_byte_count_axi <= obs_core_rx_byte_count_axi + 1'b1;
        if (synth_rx_active_axi) obs_synth_rx_tvalid_count_axi <= obs_synth_rx_tvalid_count_axi + 1'b1;
        if (obs_synth_rx_fire_axi && m_axis_rx_tlast) obs_synth_rx_tlast_count_axi <= obs_synth_rx_tlast_count_axi + 1'b1;
        if (obs_synth_rx_fire_axi) obs_synth_rx_byte_count_axi <= obs_synth_rx_byte_count_axi + 1'b1;
        if (m_axis_rx_tvalid) obs_mux_rx_tvalid_count_axi <= obs_mux_rx_tvalid_count_axi + 1'b1;
        if (obs_mux_rx_fire_axi && m_axis_rx_tlast) obs_mux_rx_tlast_count_axi <= obs_mux_rx_tlast_count_axi + 1'b1;
        if (obs_mux_rx_fire_axi) obs_mux_rx_byte_count_axi <= obs_mux_rx_byte_count_axi + 1'b1;
      end
    end
  end

  function automatic logic [7:0] pick_lane_count(
    input logic [31:0] counts,
    input logic [LANE_COUNT-1:0] rx_mask
  );
    logic found;
    integer i;
    begin
      found = 1'b0;
      pick_lane_count = counts[7:0];
      for (i = 0; i < LANE_COUNT && i < 4; i = i + 1) begin
        if (!found && rx_mask[i]) begin
          pick_lane_count = counts[(8*i) +: 8];
          found = 1'b1;
        end
      end
    end
  endfunction

  localparam bit STREAM_DEBUG_MINIMAL = (STREAM_PHY_DBG_SELECT == 6);

  ir_axi_regs #(
    .C_S_AXI_DATA_WIDTH(C_S_AXI_DATA_WIDTH),
    .C_S_AXI_ADDR_WIDTH(C_S_AXI_ADDR_WIDTH),
    .LANE_COUNT(LANE_COUNT),
    .MAX_FRAGS(MAX_FRAGS)
  ) u_regs (
    .s_axi_aclk(s_axi_aclk),
    .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(s_axi_awaddr),
    .s_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp),
    .s_axi_bvalid(s_axi_bvalid),
    .s_axi_bready(s_axi_bready),
    .s_axi_araddr(s_axi_araddr),
    .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(s_axi_arready),
    .s_axi_rdata(s_axi_rdata),
    .s_axi_rresp(s_axi_rresp),
    .s_axi_rvalid(s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
    .cfg_enable(cfg_enable_axi),
    .cfg_session_id(cfg_session_id_axi),
    .cfg_lane_enable_mask(cfg_lane_enable_mask_axi),
    .cfg_rx_lane_enable_mask(cfg_rx_lane_enable_mask_axi),
    .cfg_commit_toggle(cfg_commit_toggle_axi),
    .sticky_clear_toggle(sticky_clear_toggle_axi),
    .cfg_test_mode_enable(cfg_test_mode_enable_axi),
    .test_rx_inject_pulse(test_rx_inject_pulse_axi),
    .test_rx_payload_bytes(test_rx_payload_bytes_axi),
    .test_rx_pattern_id(test_rx_pattern_id_axi),
    .test_rx_seq_base(test_rx_seq_base_axi),
    .test_rx_packet_count(test_rx_packet_count_axi),
    .tx_packet_active(tx_packet_active_axi),
    .tx_packet_loading(tx_packet_loading_axi),
    .rx_ctx_valid(rx_ctx_valid_axi),
    .rx_ctx_complete(rx_ctx_complete_axi),
    .sticky_tx_done(sticky_status_axi[0]),
    .sticky_rx_done(sticky_status_axi[1] | synth_rx_done_pulse_axi),
    .sticky_tx_overflow(sticky_status_axi[2]),
    .sticky_tx_retry_exhausted(sticky_status_axi[3]),
    .sticky_rx_header_error(sticky_status_axi[4]),
    .sticky_rx_protocol_error(sticky_status_axi[5]),
    .sticky_rx_frame_overflow(sticky_status_axi[6]),
    .sticky_rx_crc_error(sticky_status_axi[7]),
    .sticky_rx_overrun_error(sticky_status_axi[8]),
    .lane_tx_busy_dbg(lane_tx_busy_dbg_axi),
    .tx_frag_pending_dbg(tx_frag_pending_dbg_axi),
    .tx_frag_inflight_dbg(tx_frag_inflight_dbg_axi),
    .tx_frag_acked_dbg(tx_frag_acked_dbg_axi),
    .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg_axi),
    .tx_lane_count_dbg(tx_lane_count_axi),
    .rx_lane_good_count_dbg(rx_lane_good_count_axi),
    .rx_lane_crc_count_dbg(rx_lane_crc_count_axi),
    .rx_lane_err_count_dbg(rx_lane_err_count_axi),
    .phy_lane0_dbg(phy_lane0_dbg_axi),
    .obs_core_rx_tvalid_count_dbg(obs_core_rx_tvalid_count_axi),
    .obs_core_rx_tready_count_dbg(obs_core_rx_tready_count_axi),
    .obs_core_rx_tlast_count_dbg(obs_core_rx_tlast_count_axi),
    .obs_core_rx_byte_count_dbg(obs_core_rx_byte_count_axi),
    .obs_synth_rx_tvalid_count_dbg(obs_synth_rx_tvalid_count_axi),
    .obs_synth_rx_tlast_count_dbg(obs_synth_rx_tlast_count_axi),
    .obs_synth_rx_byte_count_dbg(obs_synth_rx_byte_count_axi),
    .obs_mux_rx_tvalid_count_dbg(obs_mux_rx_tvalid_count_axi),
    .obs_mux_rx_tlast_count_dbg(obs_mux_rx_tlast_count_axi),
    .obs_mux_rx_byte_count_dbg(obs_mux_rx_byte_count_axi)
  );

  cdc_sync #(.WIDTH(1)) u_cfg_en_sync (
    .clk_dst(clk_phy), .rst_n(rst_n), .data_in(cfg_enable_axi), .data_out(cfg_enable_sync)
  );
  cdc_sync #(.WIDTH(16)) u_cfg_sid_sync (
    .clk_dst(clk_phy), .rst_n(rst_n), .data_in(cfg_session_id_axi), .data_out(cfg_session_sync)
  );
  cdc_sync #(.WIDTH(LANE_COUNT)) u_cfg_mask_sync (
    .clk_dst(clk_phy), .rst_n(rst_n), .data_in(cfg_lane_enable_mask_axi), .data_out(cfg_lane_mask_sync)
  );
  cdc_sync #(.WIDTH(LANE_COUNT)) u_cfg_rx_mask_sync (
    .clk_dst(clk_phy), .rst_n(rst_n), .data_in(cfg_rx_lane_enable_mask_axi), .data_out(cfg_rx_lane_mask_sync)
  );
  cdc_sync #(.WIDTH(1)) u_cfg_commit_sync (
    .clk_dst(clk_phy), .rst_n(rst_n), .data_in(cfg_commit_toggle_axi), .data_out(cfg_commit_toggle_phy)
  );
  cdc_sync #(.WIDTH(STICKY_W)) u_clear_toggle_sync (
    .clk_dst(clk_phy), .rst_n(rst_n), .data_in(sticky_clear_toggle_axi), .data_out(sticky_clear_toggle_phy)
  );

  always_ff @(posedge clk_phy) begin
    if (!rst_n) begin
      cfg_commit_toggle_phy_d <= 1'b0;
      cfg_enable_phy <= 1'b0;
      cfg_session_id_phy <= 16'h0001;
      cfg_lane_enable_mask_phy <= DEFAULT_LANE_MASK;
      cfg_rx_lane_enable_mask_phy <= DEFAULT_LANE_MASK;
      sticky_clear_toggle_phy_d <= '0;
    end else begin
      cfg_commit_toggle_phy_d <= cfg_commit_toggle_phy;
      sticky_clear_toggle_phy_d <= sticky_clear_toggle_phy;
      if (cfg_commit_toggle_phy ^ cfg_commit_toggle_phy_d) begin
        cfg_enable_phy <= cfg_enable_sync;
        cfg_session_id_phy <= cfg_session_sync;
        cfg_lane_enable_mask_phy <= cfg_lane_mask_sync;
        cfg_rx_lane_enable_mask_phy <= cfg_rx_lane_mask_sync;
      end
    end
  end

  assign sticky_clear_pulse_phy = sticky_clear_toggle_phy ^ sticky_clear_toggle_phy_d;

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

  generate
    if (STREAM_DEBUG_MINIMAL) begin : g_minimal_debug
      assign tx_lane_count_phy      = 32'h0000_0000;
      assign rx_lane_good_count_phy = 32'h0000_0000;
      assign rx_lane_crc_count_phy  = 32'h0000_0000;
      assign rx_lane_err_count_phy  = 32'h0000_0000;
      assign phy_lane0_dbg_phy      = 32'h0000_0000;
    end else begin : g_full_debug
      assign lane_tx_edge_pulse_phy = ir_tx_out ^ ir_tx_out_d_phy;
      assign lane_rx_edge_pulse_phy = ir_rx_in ^ ir_rx_in_d_phy;
      assign tx_lane_count_phy = {tx_lane_edge_count_phy[15:0], tx_lane_load_count_phy[15:0]};
      assign selected_rx_debug_phy = pick_rx_lane_debug(stream_lane_rx_debug_phy, cfg_rx_lane_enable_mask_phy);
      assign selected_rx_edge_count_phy = pick_lane_count(rx_lane_edge_count_phy, cfg_rx_lane_enable_mask_phy);
      assign selected_rx_lane_index_phy = pick_rx_lane_index(cfg_rx_lane_enable_mask_phy);
      assign selected_rx_level_phy = pick_rx_lane_level(ir_rx_in, cfg_rx_lane_enable_mask_phy);

      always_ff @(posedge clk_phy) begin
        if (!rst_n) begin
          tx_lane_load_count_phy <= 32'h0000_0000;
          tx_lane_edge_count_phy <= 32'h0000_0000;
          rx_lane_edge_count_phy <= 32'h0000_0000;
          rx_lane_good_count_phy <= 32'h0000_0000;
          rx_lane_crc_count_phy  <= 32'h0000_0000;
          rx_lane_err_count_phy  <= 32'h0000_0000;
          ir_tx_out_d_phy        <= '0;
          ir_rx_in_d_phy         <= '0;
          selected_rx_debug_latched_phy <= 32'h0000_0000;
          stream_debug_latched_phy <= 32'h0000_0000;
        end else if (|sticky_clear_pulse_phy) begin
          tx_lane_load_count_phy <= 32'h0000_0000;
          tx_lane_edge_count_phy <= 32'h0000_0000;
          rx_lane_edge_count_phy <= 32'h0000_0000;
          rx_lane_good_count_phy <= 32'h0000_0000;
          rx_lane_crc_count_phy  <= 32'h0000_0000;
          rx_lane_err_count_phy  <= 32'h0000_0000;
          ir_tx_out_d_phy        <= ir_tx_out;
          ir_rx_in_d_phy         <= ir_rx_in;
          selected_rx_debug_latched_phy <= 32'h0000_0000;
          stream_debug_latched_phy <= 32'h0000_0000;
        end else begin
          ir_tx_out_d_phy        <= ir_tx_out;
          ir_rx_in_d_phy         <= ir_rx_in;
          tx_lane_load_count_phy <= inc_lane_counts(tx_lane_load_count_phy, lane_tx_load_pulse_phy);
          tx_lane_edge_count_phy <= inc_lane_counts(tx_lane_edge_count_phy, lane_tx_edge_pulse_phy);
          rx_lane_edge_count_phy <= inc_lane_counts(rx_lane_edge_count_phy, lane_rx_edge_pulse_phy);
          rx_lane_good_count_phy <= inc_lane_counts(rx_lane_good_count_phy, lane_rx_frame_pulse_phy);
          rx_lane_crc_count_phy  <= inc_lane_counts(rx_lane_crc_count_phy, lane_rx_crc_error_pulse_phy);
          rx_lane_err_count_phy  <= {
            4'hD,
            selected_rx_lane_index_phy,
            selected_rx_level_phy,
            selected_rx_edge_count_phy,
            selected_rx_debug_phy[31:15]
          };
          if (selected_rx_debug_phy != 32'h0000_0000) begin
            selected_rx_debug_latched_phy <= selected_rx_debug_phy;
          end
          if (stream_debug_interesting_phy) begin
            stream_debug_latched_phy <= stream_debug_phy;
          end
        end
      end

      assign selected_rx_debug_observe_phy =
        (selected_rx_debug_phy != 32'h0000_0000) ? selected_rx_debug_phy : selected_rx_debug_latched_phy;
      assign stream_debug_interesting_phy =
        (stream_debug_phy[31:28] == 4'hA) &&
        ((stream_debug_phy[27:24] != 4'h0) ||
         (stream_debug_phy[23:21] != 3'h0) ||
         (|stream_debug_phy[20:13]) ||
         stream_debug_phy[11] ||
         stream_debug_phy[10] ||
         stream_debug_phy[9] ||
         stream_debug_phy[8]);
      assign stream_debug_observe_phy =
        stream_debug_interesting_phy ? stream_debug_phy : stream_debug_latched_phy;

      always_comb begin
        unique case (STREAM_PHY_DBG_SELECT)
          1: phy_lane0_dbg_phy = selected_rx_debug_observe_phy;
          2: phy_lane0_dbg_phy = stream_debug_phy;
          3: phy_lane0_dbg_phy = ext_phy_dbg;
          4: phy_lane0_dbg_phy = selected_rx_debug_phy;
          5: phy_lane0_dbg_phy = stream_debug_observe_phy;
          default: phy_lane0_dbg_phy = (ext_phy_dbg != 32'h0000_0000) ? ext_phy_dbg : stream_debug_phy;
        endcase
      end
    end
  endgenerate

  ir_axis_async_fifo #(
    .DATA_W(8),
    .DEPTH(TX_ASYNC_FIFO_DEPTH)
  ) u_tx_async_fifo (
    .rst(~s_axi_aresetn),
    .s_clk(s_axi_aclk),
    .s_tdata(s_axis_tx_tdata),
    .s_tvalid(s_axis_tx_tvalid),
    .s_tready(s_axis_tx_tready),
    .s_tlast(s_axis_tx_tlast),
    .m_clk(clk_phy),
    .m_tdata(tx_phy_tdata),
    .m_tvalid(tx_phy_tvalid),
    .m_tready(tx_phy_tready),
    .m_tlast(tx_phy_tlast)
  );

  ir_axis_async_fifo #(
    .DATA_W(8),
    .DEPTH(RX_ASYNC_FIFO_DEPTH)
  ) u_rx_async_fifo (
    .rst(~rst_n),
    .s_clk(clk_phy),
    .s_tdata(rx_phy_tdata),
    .s_tvalid(rx_phy_tvalid),
    .s_tready(rx_phy_tready),
    .s_tlast(rx_phy_tlast),
    .m_clk(s_axi_aclk),
    .m_tdata(core_m_axis_rx_tdata),
    .m_tvalid(core_m_axis_rx_tvalid),
    .m_tready(core_m_axis_rx_tready),
    .m_tlast(core_m_axis_rx_tlast)
  );

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      synth_rx_active_axi <= 1'b0;
      synth_rx_payload_len_axi <= 16'd16;
      synth_rx_seq_axi <= 16'd1;
      synth_rx_pattern_axi <= 8'd2;
      synth_rx_idx_axi <= 16'd0;
      synth_rx_done_pulse_axi <= 1'b0;
    end else begin
      synth_rx_done_pulse_axi <= 1'b0;

      if (!synth_rx_active_axi) begin
        if (cfg_test_mode_enable_axi && test_rx_inject_pulse_axi) begin
          synth_rx_active_axi <= 1'b1;
          synth_rx_idx_axi <= 16'd0;
          synth_rx_seq_axi <= test_rx_seq_base_axi;
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
          synth_rx_active_axi <= 1'b0;
          synth_rx_idx_axi <= 16'd0;
          synth_rx_done_pulse_axi <= 1'b1;
        end else begin
          synth_rx_idx_axi <= synth_rx_idx_axi + 1'b1;
        end
      end
    end
  end

  cdc_sync #(.WIDTH(1)) u_st0 (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(tx_packet_active_phy), .data_out(tx_packet_active_axi));
  cdc_sync #(.WIDTH(1)) u_st1 (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(tx_packet_loading_phy), .data_out(tx_packet_loading_axi));
  cdc_sync #(.WIDTH(1)) u_st2 (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(rx_ctx_valid_phy), .data_out(rx_ctx_valid_axi));
  cdc_sync #(.WIDTH(1)) u_st3 (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(rx_ctx_complete_phy), .data_out(rx_ctx_complete_axi));
  cdc_sync #(.WIDTH(STICKY_W)) u_stk (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(sticky_status_phy), .data_out(sticky_status_axi));
  cdc_sync #(.WIDTH(LANE_COUNT)) u_busy (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(lane_tx_busy_dbg_phy), .data_out(lane_tx_busy_dbg_axi));
  cdc_sync #(.WIDTH(MAX_FRAGS)) u_pend (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(tx_frag_pending_dbg_phy), .data_out(tx_frag_pending_dbg_axi));
  cdc_sync #(.WIDTH(MAX_FRAGS)) u_iflt (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(tx_frag_inflight_dbg_phy), .data_out(tx_frag_inflight_dbg_axi));
  cdc_sync #(.WIDTH(MAX_FRAGS)) u_ackd (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(tx_frag_acked_dbg_phy), .data_out(tx_frag_acked_dbg_axi));
  cdc_sync #(.WIDTH(MAX_FRAGS)) u_recv (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(rx_recv_bitmap_dbg_phy), .data_out(rx_recv_bitmap_dbg_axi));
  generate
    if (STREAM_DEBUG_MINIMAL) begin : g_minimal_debug_axi
      assign tx_lane_count_axi      = 32'h0000_0000;
      assign rx_lane_good_count_axi = 32'h0000_0000;
      assign rx_lane_crc_count_axi  = 32'h0000_0000;
      assign rx_lane_err_count_axi  = 32'h0000_0000;
      assign phy_lane0_dbg_axi      = 32'h0000_0000;
    end else begin : g_full_debug_axi
      cdc_sync #(.WIDTH(32)) u_tx_lane_count (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(tx_lane_count_phy), .data_out(tx_lane_count_axi));
      cdc_sync #(.WIDTH(32)) u_rx_lane_good_count (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(rx_lane_good_count_phy), .data_out(rx_lane_good_count_axi));
      cdc_sync #(.WIDTH(32)) u_rx_lane_crc_count (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(rx_lane_crc_count_phy), .data_out(rx_lane_crc_count_axi));
      cdc_sync #(.WIDTH(32)) u_rx_lane_err_count (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(rx_lane_err_count_phy), .data_out(rx_lane_err_count_axi));
      cdc_sync #(.WIDTH(32)) u_phy_lane0_dbg (.clk_dst(s_axi_aclk), .rst_n(s_axi_aresetn), .data_in(phy_lane0_dbg_phy), .data_out(phy_lane0_dbg_axi));
    end
  endgenerate

  generate
    if (PARALLEL_2LANE_MODE != 0 && LANE_COUNT == 2) begin : g_parallel_2lane
      ir_stream_parallel_2lane_top #(
        .NODE_ID(STREAM_NODE_ID),
        .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_RETRY(MAX_RETRY),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(CNT_PREAMBLE),
        .EOF_SILENCE_SYMS(EOF_SILENCE_SYMS),
        .RX_DATA_PHASE_DELAY_CYCLES(RX_DATA_PHASE_DELAY_CYCLES),
        .RX_DETECT_START_CYCLES(RX_DETECT_START_CYCLES),
        .RX_DETECT_END_CYCLES(RX_DETECT_END_CYCLES),
        .RX_PREAMBLE_REALIGN_EDGE(RX_PREAMBLE_REALIGN_EDGE),
        .RX_SELF_BLANK_CYCLES(RX_SELF_BLANK_CYCLES),
        .FORCE_SD_SHUTDOWN(FORCE_SD_SHUTDOWN),
        .FRAG_TIMEOUT_CYCLES(FRAG_TIMEOUT_CYCLES),
        .TX_TO_RX_GUARD_CYCLES(RX_TO_TX_GUARD_CYCLES),
        .BACKOFF_SLOT_CYCLES(TX_POST_ACK_GUARD_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES(REASSEMBLY_TIMEOUT_CYCLES),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) u_stream (
        .clk_phy(clk_phy),
        .rst_n(rst_n),
        .enable(cfg_enable_phy),
        .session_id(cfg_session_id_phy),
        .lane_enable_mask(cfg_lane_enable_mask_phy[1:0]),
        .rx_lane_enable_mask(cfg_rx_lane_enable_mask_phy[1:0]),
        .s_axis_tx_tdata(tx_phy_tdata),
        .s_axis_tx_tvalid(tx_phy_tvalid),
        .s_axis_tx_tready(tx_phy_tready),
        .s_axis_tx_tlast(tx_phy_tlast),
        .m_axis_rx_tdata(rx_phy_tdata),
        .m_axis_rx_tvalid(rx_phy_tvalid),
        .m_axis_rx_tready(rx_phy_tready),
        .m_axis_rx_tlast(rx_phy_tlast),
        .ir_tx_out(ir_tx_out[1:0]),
        .ir_rx_in(ir_rx_in[1:0]),
        .ir_sd(ir_sd[1:0]),
        .ir_mode_out(ir_mode_out[1:0]),
        .tx_packet_active(tx_packet_active_phy),
        .tx_packet_loading(tx_packet_loading_phy),
        .tx_done_pulse(tx_done_pulse_phy),
        .tx_error_overflow(tx_error_overflow_phy),
        .tx_error_retry_exhausted(tx_error_retry_exhausted_phy),
        .rx_ctx_valid(rx_ctx_valid_phy),
        .rx_ctx_complete(rx_ctx_complete_phy),
        .rx_done_pulse(rx_done_pulse_phy),
        .rx_header_error(rx_header_error_phy),
        .rx_protocol_error(rx_protocol_error_phy),
        .rx_frame_overflow_any(rx_frame_overflow_phy),
        .rx_crc_error_any(rx_crc_error_phy),
        .rx_overrun_error_any(rx_overrun_error_phy),
        .lane_tx_busy_dbg(lane_tx_busy_dbg_phy[1:0]),
        .lane_tx_load_pulse_dbg(lane_tx_load_pulse_phy[1:0]),
        .lane_rx_frame_pulse_dbg(lane_rx_frame_pulse_phy[1:0]),
        .lane_rx_crc_error_dbg(lane_rx_crc_error_pulse_phy[1:0]),
        .lane_rx_error_dbg(lane_rx_error_pulse_phy[1:0]),
        .lane_rx_debug_status_dbg(stream_lane_rx_debug_phy[63:0]),
        .tx_frag_pending_dbg(tx_frag_pending_dbg_phy),
        .tx_frag_inflight_dbg(tx_frag_inflight_dbg_phy),
        .tx_frag_acked_dbg(tx_frag_acked_dbg_phy),
        .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg_phy),
        .debug_status(stream_debug_phy)
      );
    end else begin : g_stream_legacy
      ir_stream_array_top #(
        .LANE_COUNT(LANE_COUNT),
        .NODE_ID(STREAM_NODE_ID),
        .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
        .FRAGMENT_BYTES(FRAGMENT_BYTES),
        .MAX_RETRY(MAX_RETRY),
        .CNT_CHIP_MAX(CNT_CHIP_MAX),
        .CNT_PREAMBLE(CNT_PREAMBLE),
        .EOF_SILENCE_SYMS(EOF_SILENCE_SYMS),
        .RX_DATA_PHASE_DELAY_CYCLES(RX_DATA_PHASE_DELAY_CYCLES),
        .RX_DETECT_START_CYCLES(RX_DETECT_START_CYCLES),
        .RX_DETECT_END_CYCLES(RX_DETECT_END_CYCLES),
        .RX_PREAMBLE_REALIGN_EDGE(RX_PREAMBLE_REALIGN_EDGE),
        .RX_SELF_BLANK_CYCLES(RX_SELF_BLANK_CYCLES),
        .FORCE_SD_SHUTDOWN(FORCE_SD_SHUTDOWN),
        .TX_REQUIRE_ACK(TX_REQUIRE_ACK),
        .FRAG_TIMEOUT_CYCLES(FRAG_TIMEOUT_CYCLES),
        .TX_TO_RX_GUARD_CYCLES(RX_TO_TX_GUARD_CYCLES),
        .BACKOFF_SLOT_CYCLES(TX_POST_ACK_GUARD_CYCLES),
        .REASSEMBLY_TIMEOUT_CYCLES(REASSEMBLY_TIMEOUT_CYCLES),
        .MAX_FRAGS(MAX_FRAGS),
        .MAX_FRAME_BYTES(MAX_FRAME_BYTES)
      ) u_stream (
        .clk_phy(clk_phy),
        .rst_n(rst_n),
        .enable(cfg_enable_phy),
        .session_id(cfg_session_id_phy),
        .lane_enable_mask(cfg_lane_enable_mask_phy),
        .rx_lane_enable_mask(cfg_rx_lane_enable_mask_phy),
        .s_axis_tx_tdata(tx_phy_tdata),
        .s_axis_tx_tvalid(tx_phy_tvalid),
        .s_axis_tx_tready(tx_phy_tready),
        .s_axis_tx_tlast(tx_phy_tlast),
        .m_axis_rx_tdata(rx_phy_tdata),
        .m_axis_rx_tvalid(rx_phy_tvalid),
        .m_axis_rx_tready(rx_phy_tready),
        .m_axis_rx_tlast(rx_phy_tlast),
        .ir_tx_out(ir_tx_out),
        .ir_rx_in(ir_rx_in),
        .ir_sd(ir_sd),
        .ir_mode_out(ir_mode_out),
        .tx_packet_active(tx_packet_active_phy),
        .tx_packet_loading(tx_packet_loading_phy),
        .tx_done_pulse(tx_done_pulse_phy),
        .tx_error_overflow(tx_error_overflow_phy),
        .tx_error_retry_exhausted(tx_error_retry_exhausted_phy),
        .rx_ctx_valid(rx_ctx_valid_phy),
        .rx_ctx_complete(rx_ctx_complete_phy),
        .rx_done_pulse(rx_done_pulse_phy),
        .rx_header_error(rx_header_error_phy),
        .rx_protocol_error(rx_protocol_error_phy),
        .rx_frame_overflow_any(rx_frame_overflow_phy),
        .rx_crc_error_any(rx_crc_error_phy),
        .rx_overrun_error_any(rx_overrun_error_phy),
        .lane_tx_busy_dbg(lane_tx_busy_dbg_phy),
        .lane_tx_load_pulse_dbg(lane_tx_load_pulse_phy),
        .lane_rx_frame_pulse_dbg(lane_rx_frame_pulse_phy),
        .lane_rx_crc_error_dbg(lane_rx_crc_error_pulse_phy),
        .lane_rx_error_dbg(lane_rx_error_pulse_phy),
        .lane_rx_debug_status_dbg(stream_lane_rx_debug_phy),
        .tx_frag_pending_dbg(tx_frag_pending_dbg_phy),
        .tx_frag_inflight_dbg(tx_frag_inflight_dbg_phy),
        .tx_frag_acked_dbg(tx_frag_acked_dbg_phy),
        .rx_recv_bitmap_dbg(rx_recv_bitmap_dbg_phy),
        .debug_status(stream_debug_phy)
      );
    end
  endgenerate
endmodule
