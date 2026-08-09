`timescale 1ns/1ps
`default_nettype wire

// Vivado IP Integrator boundary for one independent P10 AX7020 endpoint.
// ENDPOINT_ROLE=1 is AX7020-F (logical side A); ENDPOINT_ROLE=2 is AX7020-R
// (logical side B). Only the role-local two TFDU modules reach package pins.
module p10_axi_dma_endpoint_peripheral_bd #(
  parameter integer ENDPOINT_ROLE = 1,
  parameter integer LANE_COUNT = 2,
  parameter integer P10_5_DUAL_CAPABLE = 0,
  parameter [31:0] BUILD_ID_OVERRIDE = 32'h0000_0000
) (
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axi_aclk CLK" *)
  (* X_INTERFACE_PARAMETER = "ASSOCIATED_BUSIF s_axi:s_axis:m_axis, ASSOCIATED_RESET s_axi_aresetn, FREQ_HZ 64000000" *)
  input         s_axi_aclk,
  (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 s_axi_aresetn RST" *)
  (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
  input         s_axi_aresetn,
  input  [11:0] s_axi_awaddr,
  input  [2:0]  s_axi_awprot,
  input         s_axi_awvalid,
  output        s_axi_awready,
  input  [31:0] s_axi_wdata,
  input  [3:0]  s_axi_wstrb,
  input         s_axi_wvalid,
  output        s_axi_wready,
  output [1:0]  s_axi_bresp,
  output        s_axi_bvalid,
  input         s_axi_bready,
  input  [11:0] s_axi_araddr,
  input  [2:0]  s_axi_arprot,
  input         s_axi_arvalid,
  output        s_axi_arready,
  output [31:0] s_axi_rdata,
  output [1:0]  s_axi_rresp,
  output        s_axi_rvalid,
  input         s_axi_rready,

  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TVALID" *) input s_axis_tvalid,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TREADY" *) output s_axis_tready,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TDATA" *) input [31:0] s_axis_tdata,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TKEEP" *) input [3:0] s_axis_tkeep,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TLAST" *) input s_axis_tlast,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TVALID" *) output m_axis_tvalid,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TREADY" *) input m_axis_tready,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TDATA" *) output [31:0] m_axis_tdata,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TKEEP" *) output [3:0] m_axis_tkeep,
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TLAST" *) output m_axis_tlast,
  output stream_reset_request_o,

  output [LANE_COUNT-1:0] tfdu_mode_o,
  input  [LANE_COUNT-1:0] tfdu_rxd_i,
  output [LANE_COUNT-1:0] tfdu_sd_o,
  output [LANE_COUNT-1:0] tfdu_txd_o,
  output [3:0] pl_activity_led_n_o
);
  localparam [31:0] P10_MAGIC = 32'h5031_305A;
  localparam [31:0] P10_DEFAULT_BUILD_ID = P10_5_DUAL_CAPABLE != 0 ?
      (ENDPOINT_ROLE == 1 ? 32'h5035_3446 : 32'h5035_3452) :
      LANE_COUNT == 4 ?
      (ENDPOINT_ROLE == 1 ? 32'h5032_3446 : 32'h5032_3452) :
      (ENDPOINT_ROLE == 1 ? 32'h5032_5346 : 32'h5032_5352);
  localparam [31:0] P10_BUILD_ID = BUILD_ID_OVERRIDE != 0 ?
      BUILD_ID_OVERRIDE : P10_DEFAULT_BUILD_ID;
  localparam [31:0] P10_PROFILE_ID = ENDPOINT_ROLE == 1 ?
      (LANE_COUNT == 4 ? 32'h7020_04F0 : 32'h7020_00F0) :
      (LANE_COUNT == 4 ? 32'h7020_04A0 : 32'h7020_00A0);

  wire [LANE_COUNT-1:0] a_mode;
  wire [LANE_COUNT-1:0] a_sd;
  wire [LANE_COUNT-1:0] a_txd;
  wire [LANE_COUNT-1:0] b_mode;
  wire [LANE_COUNT-1:0] b_sd;
  wire [LANE_COUNT-1:0] b_txd;
  wire [LANE_COUNT-1:0] valid_rx_frame_activity;
  wire effective_full_shutdown;
  wire [LANE_COUNT-1:0] a_rxd = ENDPOINT_ROLE == 1 ?
      tfdu_rxd_i : {LANE_COUNT{1'b1}};
  wire [LANE_COUNT-1:0] b_rxd = ENDPOINT_ROLE == 2 ?
      tfdu_rxd_i : {LANE_COUNT{1'b1}};

  assign tfdu_mode_o = ENDPOINT_ROLE == 1 ? a_mode : b_mode;
  assign tfdu_sd_o = ENDPOINT_ROLE == 1 ? a_sd : b_sd;
  assign tfdu_txd_o = ENDPOINT_ROLE == 1 ? a_txd : b_txd;

  initial begin
    if (ENDPOINT_ROLE != 1 && ENDPOINT_ROLE != 2)
      $error("P10 ENDPOINT_ROLE must be 1 (fixed) or 2 (rotating)");
    if (LANE_COUNT != 2 && LANE_COUNT != 4)
      $error("P10 endpoint wrapper supports LANE_COUNT=2 or 4");
  end

  p9_axi_dma_peripheral #(
    .DEPLOYMENT_ROLE(ENDPOINT_ROLE),
    .LANE_COUNT(LANE_COUNT),
    .P10_5_DUAL_CAPABLE(P10_5_DUAL_CAPABLE),
    .BUILD_ID(P10_BUILD_ID),
    .PROFILE_ID(P10_PROFILE_ID),
    .IDENTITY_MAGIC(P10_MAGIC)
  ) impl (
    .s_axi_aclk(s_axi_aclk), .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(s_axi_awaddr), .s_axi_awprot(s_axi_awprot),
    .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid),
    .s_axi_bready(s_axi_bready), .s_axi_araddr(s_axi_araddr),
    .s_axi_arprot(s_axi_arprot), .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(s_axi_arready), .s_axi_rdata(s_axi_rdata),
    .s_axi_rresp(s_axi_rresp), .s_axi_rvalid(s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
    .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
    .s_axis_tdata(s_axis_tdata), .s_axis_tkeep(s_axis_tkeep),
    .s_axis_tlast(s_axis_tlast), .m_axis_tvalid(m_axis_tvalid),
    .m_axis_tready(m_axis_tready), .m_axis_tdata(m_axis_tdata),
    .m_axis_tkeep(m_axis_tkeep), .m_axis_tlast(m_axis_tlast),
    .stream_reset_request_o(stream_reset_request_o),
    .ir_mode_out_0(a_mode), .ir_rx_in_0(a_rxd),
    .ir_sd_0(a_sd), .ir_tx_out_0(a_txd),
    .loop_mode_b0(b_mode), .loop_rx_b0(b_rxd),
    .loop_sd_b0(b_sd), .loop_tx_b0(b_txd),
    .monitor_valid_rx_frame_o(valid_rx_frame_activity),
    .monitor_effective_full_shutdown_o(effective_full_shutdown)
  );

  generate
    if (LANE_COUNT == 2) begin : g_legacy_2lane_leds
      p10_lane_activity_leds #(
        .CLK_HZ(64_000_000), .TICK_HZ(1_000), .HOLD_MS(200)
      ) u_activity_leds (
        .clk(s_axi_aclk), .rst_n(s_axi_aresetn),
        .effective_full_shutdown_i(effective_full_shutdown || (&tfdu_sd_o)),
        .final_txd_activity_i(tfdu_txd_o),
        .valid_rx_frame_activity_i(valid_rx_frame_activity),
        .pl_led_n_o(pl_activity_led_n_o)
      );
    end else begin : g_4lane_leds
      p10_2_lane_activity_leds #(
        .CLK_HZ(64_000_000), .TICK_HZ(1_000), .HOLD_MS(200)
      ) u_activity_leds (
        .clk(s_axi_aclk), .rst_n(s_axi_aresetn),
        .effective_full_shutdown_i(effective_full_shutdown || (&tfdu_sd_o)),
        .final_txd_activity_i(tfdu_txd_o),
        .valid_rx_frame_activity_i(valid_rx_frame_activity),
        .pl_led_n_o(pl_activity_led_n_o)
      );
    end
  endgenerate
endmodule

`default_nettype wire
