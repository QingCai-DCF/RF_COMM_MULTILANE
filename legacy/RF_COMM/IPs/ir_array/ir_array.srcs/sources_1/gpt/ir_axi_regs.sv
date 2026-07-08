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
  output logic                           cfg_commit_toggle,
  output logic [5:0]                     sticky_clear_toggle,
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
  input  logic [LANE_COUNT-1:0]          lane_tx_busy_dbg,
  input  logic [MAX_FRAGS-1:0]           tx_frag_pending_dbg,
  input  logic [MAX_FRAGS-1:0]           tx_frag_inflight_dbg,
  input  logic [MAX_FRAGS-1:0]           tx_frag_acked_dbg,
  input  logic [MAX_FRAGS-1:0]           rx_recv_bitmap_dbg
);
  localparam logic [31:0] DEFAULT_LANE_MASK = (32'h1 << LANE_COUNT) - 1;

  logic [31:0] reg_control;
  logic [31:0] reg_session;
  logic [31:0] reg_lane_mask;
  logic [31:0] reg_status;
  logic [31:0] reg_status_sticky;
  logic        aw_en;

  assign cfg_enable           = reg_control[0];
  assign cfg_session_id       = reg_session[15:0];
  assign cfg_lane_enable_mask = reg_lane_mask[LANE_COUNT-1:0];

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
      reg_lane_mask       <= DEFAULT_LANE_MASK;
      reg_status          <= 32'h0000_0000;
      reg_status_sticky   <= 32'h0000_0000;
      cfg_commit_toggle   <= 1'b0;
      sticky_clear_toggle <= 6'b0;
      aw_en               <= 1'b1;
    end else begin
      reg_status[0] <= tx_packet_active;
      reg_status[1] <= tx_packet_loading;
      reg_status[2] <= rx_ctx_valid;
      reg_status[3] <= rx_ctx_complete;
      reg_status[4 +: LANE_COUNT] <= lane_tx_busy_dbg;

      if (sticky_tx_done)              reg_status_sticky[0] <= 1'b1;
      if (sticky_rx_done)              reg_status_sticky[1] <= 1'b1;
      if (sticky_tx_overflow)          reg_status_sticky[2] <= 1'b1;
      if (sticky_tx_retry_exhausted)   reg_status_sticky[3] <= 1'b1;
      if (sticky_rx_header_error)      reg_status_sticky[4] <= 1'b1;
      if (sticky_rx_protocol_error)    reg_status_sticky[5] <= 1'b1;

      if (!s_axi_awready && s_axi_awvalid && s_axi_wvalid && aw_en) begin
        s_axi_awready <= 1'b1;
        s_axi_wready  <= 1'b1;
        aw_en         <= 1'b0;

        case (s_axi_awaddr[5:2])
          4'h0: begin
            if (s_axi_wstrb[0]) begin
              reg_control[7:0] <= s_axi_wdata[7:0];
              cfg_commit_toggle <= ~cfg_commit_toggle;
            end
          end
          4'h1: begin
            if (s_axi_wstrb[1:0] != 0) begin
              reg_session <= s_axi_wdata;
              cfg_commit_toggle <= ~cfg_commit_toggle;
            end
          end
          4'h2: begin
            reg_lane_mask <= s_axi_wdata;
            cfg_commit_toggle <= ~cfg_commit_toggle;
          end
          4'h4: begin
            reg_status_sticky   <= reg_status_sticky & ~s_axi_wdata;
            sticky_clear_toggle <= sticky_clear_toggle ^ s_axi_wdata[5:0];
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
          default: s_axi_rdata <= 32'h0000_0000;
        endcase
      end else if (s_axi_rvalid && s_axi_rready) begin
        s_axi_rvalid <= 1'b0;
      end
    end
  end
endmodule
