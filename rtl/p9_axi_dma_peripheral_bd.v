`timescale 1ns/1ps

// Verilog module-reference shim for Vivado IP Integrator.  Interface metadata
// keeps the AXI-Lite and two AXI-Stream boundaries explicit in the generated
// XSA/HWH instead of relying on port-name heuristics.
module p9_axi_dma_peripheral_bd (
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

  output [1:0] ir_mode_out_0,
  input  [1:0] ir_rx_in_0,
  output [1:0] ir_sd_0,
  output [1:0] ir_tx_out_0,
  output [1:0] loop_mode_b0,
  input  [1:0] loop_rx_b0,
  output [1:0] loop_sd_b0,
  output [1:0] loop_tx_b0
);
  p9_axi_dma_peripheral impl (
    .s_axi_aclk(s_axi_aclk), .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(s_axi_awaddr), .s_axi_awprot(s_axi_awprot),
    .s_axi_awvalid(s_axi_awvalid), .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata), .s_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(s_axi_wvalid), .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp), .s_axi_bvalid(s_axi_bvalid), .s_axi_bready(s_axi_bready),
    .s_axi_araddr(s_axi_araddr), .s_axi_arprot(s_axi_arprot),
    .s_axi_arvalid(s_axi_arvalid), .s_axi_arready(s_axi_arready),
    .s_axi_rdata(s_axi_rdata), .s_axi_rresp(s_axi_rresp),
    .s_axi_rvalid(s_axi_rvalid), .s_axi_rready(s_axi_rready),
    .s_axis_tvalid(s_axis_tvalid), .s_axis_tready(s_axis_tready),
    .s_axis_tdata(s_axis_tdata), .s_axis_tkeep(s_axis_tkeep),
    .s_axis_tlast(s_axis_tlast), .m_axis_tvalid(m_axis_tvalid),
    .m_axis_tready(m_axis_tready), .m_axis_tdata(m_axis_tdata),
    .m_axis_tkeep(m_axis_tkeep), .m_axis_tlast(m_axis_tlast),
    .stream_reset_request_o(stream_reset_request_o),
    .ir_mode_out_0(ir_mode_out_0), .ir_rx_in_0(ir_rx_in_0),
    .ir_sd_0(ir_sd_0), .ir_tx_out_0(ir_tx_out_0),
    .loop_mode_b0(loop_mode_b0), .loop_rx_b0(loop_rx_b0),
    .loop_sd_b0(loop_sd_b0), .loop_tx_b0(loop_tx_b0),
    .monitor_valid_rx_frame_o(), .monitor_effective_full_shutdown_o()
  );
endmodule
