module ir_axi_regs #(
  parameter int C_S_AXI_DATA_WIDTH = 32,
  parameter int C_S_AXI_ADDR_WIDTH = 6,
  parameter int LANE_COUNT         = 4,
  parameter int MAX_FRAGS          = 16
)(
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
  output logic                           cfg_enable,
  output logic [15:0]                    cfg_session_id,
  output logic [LANE_COUNT-1:0]          cfg_lane_enable_mask,
  output logic [LANE_COUNT-1:0]          cfg_rx_lane_enable_mask,
  output logic                           cfg_commit_toggle,
  output logic [8:0]                     sticky_clear_toggle,
  output logic                           cfg_test_mode_enable,
  output logic                           test_rx_inject_pulse,
  output logic [15:0]                    test_rx_payload_bytes,
  output logic [7:0]                     test_rx_pattern_id,
  output logic [15:0]                    test_rx_seq_base,
  output logic [31:0]                    test_rx_packet_count,
  input  logic                           tx_packet_active,
  input  logic                           tx_packet_loading,
  input  logic                           rx_ctx_valid,
  input  logic                           rx_ctx_complete,
  input  logic                           sticky_tx_done,
  input  logic                           sticky_rx_done,
  input  logic                           sticky_tx_overflow,
  input  logic                           sticky_tx_retry_exhausted,
  input  logic                           sticky_rx_header_error,
  input  logic                           sticky_rx_protocol_error,
  input  logic                           sticky_rx_frame_overflow,
  input  logic                           sticky_rx_crc_error,
  input  logic                           sticky_rx_overrun_error,
  input  logic [LANE_COUNT-1:0]          lane_tx_busy_dbg,
  input  logic [MAX_FRAGS-1:0]           tx_frag_pending_dbg,
  input  logic [MAX_FRAGS-1:0]           tx_frag_inflight_dbg,
  input  logic [MAX_FRAGS-1:0]           tx_frag_acked_dbg,
  input  logic [MAX_FRAGS-1:0]           rx_recv_bitmap_dbg,
  input  logic [31:0]                    tx_lane_count_dbg,
  input  logic [31:0]                    rx_lane_good_count_dbg,
  input  logic [31:0]                    rx_lane_crc_count_dbg,
  input  logic [31:0]                    rx_lane_err_count_dbg,
  input  logic [31:0]                    phy_lane0_dbg,
  input  logic [31:0]                    obs_core_rx_tvalid_count_dbg,
  input  logic [31:0]                    obs_core_rx_tready_count_dbg,
  input  logic [31:0]                    obs_core_rx_tlast_count_dbg,
  input  logic [31:0]                    obs_core_rx_byte_count_dbg,
  input  logic [31:0]                    obs_synth_rx_tvalid_count_dbg,
  input  logic [31:0]                    obs_synth_rx_tlast_count_dbg,
  input  logic [31:0]                    obs_synth_rx_byte_count_dbg,
  input  logic [31:0]                    obs_mux_rx_tvalid_count_dbg,
  input  logic [31:0]                    obs_mux_rx_tlast_count_dbg,
  input  logic [31:0]                    obs_mux_rx_byte_count_dbg
);
  localparam int STICKY_W = 9;
  localparam logic [7:0] OBS_SELECT_MAGIC = 8'hA5;
  localparam logic [31:0] OBS_SIGNATURE = 32'h5033_0007;
  logic [31:0] reg_control;
  logic [31:0] reg_session;
  logic [31:0] reg_lane_mask;
  logic [31:0] reg_rx_lane_mask;
  logic [15:0] reg_test_rx_payload_bytes;
  logic [7:0]  reg_test_rx_pattern_id;
  logic [15:0] reg_test_rx_seq_base;
  logic [31:0] reg_test_rx_packet_count;
  logic [31:0] reg_status;
  logic [31:0] reg_status_sticky;
  logic        aw_en;
  integer      bi;

  function automatic logic [31:0] obs_debug_word(input logic [7:0] selector);
    begin
      case (selector)
        8'h00: obs_debug_word = OBS_SIGNATURE;
        8'h01: obs_debug_word = obs_core_rx_tvalid_count_dbg;
        8'h02: obs_debug_word = obs_core_rx_tready_count_dbg;
        8'h03: obs_debug_word = obs_core_rx_tlast_count_dbg;
        8'h04: obs_debug_word = obs_core_rx_byte_count_dbg;
        8'h05: obs_debug_word = obs_synth_rx_tvalid_count_dbg;
        8'h06: obs_debug_word = obs_synth_rx_tlast_count_dbg;
        8'h07: obs_debug_word = obs_synth_rx_byte_count_dbg;
        8'h08: obs_debug_word = obs_mux_rx_tvalid_count_dbg;
        8'h09: obs_debug_word = obs_mux_rx_tlast_count_dbg;
        8'h0a: obs_debug_word = obs_mux_rx_byte_count_dbg;
        default: obs_debug_word = 32'h0000_0000;
      endcase
    end
  endfunction

  function automatic logic [31:0] default_lane_mask;
    integer i;
    begin
      default_lane_mask = 32'h0;
      for (i = 0; i < LANE_COUNT && i < 32; i = i + 1) begin
        default_lane_mask[i] = 1'b1;
      end
    end
  endfunction

  assign cfg_enable           = reg_control[0];
  assign cfg_session_id       = reg_session[15:0];
  assign cfg_lane_enable_mask = reg_lane_mask[LANE_COUNT-1:0];
  assign cfg_rx_lane_enable_mask = reg_rx_lane_mask[LANE_COUNT-1:0];
  assign cfg_test_mode_enable = reg_control[8];
  assign test_rx_payload_bytes = reg_test_rx_payload_bytes;
  assign test_rx_pattern_id = reg_test_rx_pattern_id;
  assign test_rx_seq_base = reg_test_rx_seq_base;
  assign test_rx_packet_count = reg_test_rx_packet_count;

  always_ff @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      s_axi_awready       <= 1'b0;
      s_axi_wready        <= 1'b0;
      s_axi_bvalid        <= 1'b0;
      s_axi_bresp         <= 2'b00;
      s_axi_arready       <= 1'b0;
      s_axi_rvalid        <= 1'b0;
      s_axi_rresp         <= 2'b00;
      s_axi_rdata         <= '0;
      reg_control         <= 32'h0000_0000;
      reg_session         <= 32'h0000_0001;
      reg_lane_mask       <= default_lane_mask();
      reg_rx_lane_mask    <= default_lane_mask();
      reg_test_rx_payload_bytes <= 16'd16;
      reg_test_rx_pattern_id <= 8'd2;
      reg_test_rx_seq_base <= 16'd1;
      reg_test_rx_packet_count <= 32'd1;
      reg_status          <= 32'h0000_0000;
      reg_status_sticky   <= 32'h0000_0000;
      cfg_commit_toggle   <= 1'b0;
      sticky_clear_toggle <= '0;
      test_rx_inject_pulse <= 1'b0;
      aw_en               <= 1'b1;
    end else begin
      test_rx_inject_pulse <= 1'b0;
      reg_status <= 32'h0000_0000;
      reg_status[0] <= tx_packet_active;
      reg_status[1] <= tx_packet_loading;
      reg_status[2] <= rx_ctx_valid;
      reg_status[3] <= rx_ctx_complete;
      for (bi = 0; bi < LANE_COUNT && (4 + bi) < 32; bi = bi + 1) begin
        reg_status[4 + bi] <= lane_tx_busy_dbg[bi];
      end

      if (sticky_tx_done)            reg_status_sticky[0] <= 1'b1;
      if (sticky_rx_done)            reg_status_sticky[1] <= 1'b1;
      if (sticky_tx_overflow)        reg_status_sticky[2] <= 1'b1;
      if (sticky_tx_retry_exhausted) reg_status_sticky[3] <= 1'b1;
      if (sticky_rx_header_error)    reg_status_sticky[4] <= 1'b1;
      if (sticky_rx_protocol_error)  reg_status_sticky[5] <= 1'b1;
      if (sticky_rx_frame_overflow)  reg_status_sticky[6] <= 1'b1;
      if (sticky_rx_crc_error)       reg_status_sticky[7] <= 1'b1;
      if (sticky_rx_overrun_error)   reg_status_sticky[8] <= 1'b1;

      if (!s_axi_awready && s_axi_awvalid && s_axi_wvalid && aw_en) begin
        s_axi_awready <= 1'b1;
        s_axi_wready  <= 1'b1;
        aw_en         <= 1'b0;

        case (s_axi_awaddr[5:2])
          4'h0: begin
            if (s_axi_wstrb[0]) begin
              reg_control[7:0] <= s_axi_wdata[7:0];
            end
            if (s_axi_wstrb[1]) begin
              reg_control[15:8] <= s_axi_wdata[15:8];
            end
            if (s_axi_wstrb[2]) begin
              reg_control[23:16] <= s_axi_wdata[23:16];
            end
            if (s_axi_wstrb[3]) begin
              reg_control[31:24] <= s_axi_wdata[31:24];
            end
            if (s_axi_wstrb != 4'b0000) begin
              cfg_commit_toggle <= ~cfg_commit_toggle;
            end
          end
          4'h1: begin
            if (s_axi_wstrb[1:0] != 0) begin
              reg_session[15:0] <= s_axi_wdata[15:0];
            end
          end
          4'h2: begin
            reg_lane_mask <= s_axi_wdata;
            reg_rx_lane_mask <= s_axi_wdata;
          end
          4'ha: begin
            reg_rx_lane_mask <= s_axi_wdata;
          end
          4'h4: begin
            reg_status_sticky[STICKY_W-1:0] <= reg_status_sticky[STICKY_W-1:0] & ~s_axi_wdata[STICKY_W-1:0];
            sticky_clear_toggle <= sticky_clear_toggle ^ s_axi_wdata[STICKY_W-1:0];
          end
          4'h5: begin
            if (s_axi_wdata[0]) cfg_commit_toggle <= ~cfg_commit_toggle;
            if (s_axi_wdata[1]) test_rx_inject_pulse <= 1'b1;
          end
          4'h6: begin
            if (s_axi_wstrb[1:0] != 0) begin
              reg_test_rx_payload_bytes <= s_axi_wdata[15:0];
            end
          end
          4'h7: begin
            if (s_axi_wstrb[0]) begin
              reg_test_rx_pattern_id <= s_axi_wdata[7:0];
            end
          end
          4'h8: begin
            if (s_axi_wstrb[1:0] != 0) begin
              reg_test_rx_seq_base <= s_axi_wdata[15:0];
            end
          end
          4'h9: begin
            reg_test_rx_packet_count <= s_axi_wdata;
          end
          default: ;
        endcase
      end else begin
        s_axi_awready <= 1'b0;
        s_axi_wready  <= 1'b0;
      end

      if (!s_axi_bvalid && !aw_en) begin
        s_axi_bvalid <= 1'b1;
        s_axi_bresp  <= 2'b00;
      end else if (s_axi_bvalid && s_axi_bready) begin
        s_axi_bvalid <= 1'b0;
        aw_en        <= 1'b1;
      end

      if (!s_axi_arready && s_axi_arvalid) begin
        s_axi_arready <= 1'b1;
      end else begin
        s_axi_arready <= 1'b0;
      end

      if (s_axi_arvalid && !s_axi_rvalid) begin
        s_axi_rvalid <= 1'b1;
        s_axi_rresp  <= 2'b00;
        case (s_axi_araddr[5:2])
          4'h0: s_axi_rdata <= reg_control;
          4'h1: s_axi_rdata <= reg_session;
          4'h2: s_axi_rdata <= reg_lane_mask;
          4'h3: s_axi_rdata <= reg_status;
          4'h4: s_axi_rdata <= reg_status_sticky;
          4'h6: s_axi_rdata <= tx_frag_pending_dbg;
          4'h7: s_axi_rdata <= tx_frag_inflight_dbg;
          4'h8: s_axi_rdata <= tx_frag_acked_dbg;
          4'h9: s_axi_rdata <= rx_recv_bitmap_dbg;
          4'ha: s_axi_rdata <= reg_rx_lane_mask;
          4'hb: s_axi_rdata <= tx_lane_count_dbg;
          4'hc: s_axi_rdata <= rx_lane_good_count_dbg;
          4'hd: s_axi_rdata <= rx_lane_crc_count_dbg;
          4'he: s_axi_rdata <= rx_lane_err_count_dbg;
          4'hf: begin
            if (reg_test_rx_packet_count[31:24] == OBS_SELECT_MAGIC) begin
              s_axi_rdata <= obs_debug_word(reg_test_rx_packet_count[7:0]);
            end else begin
              s_axi_rdata <= phy_lane0_dbg;
            end
          end
          default: s_axi_rdata <= 32'h0000_0000;
        endcase
      end else if (s_axi_rvalid && s_axi_rready) begin
        s_axi_rvalid <= 1'b0;
      end
    end
  end
endmodule
