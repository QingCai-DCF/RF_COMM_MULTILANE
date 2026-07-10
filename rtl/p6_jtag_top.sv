`timescale 1ns/1ps

// P6 immutable local-transport candidate: no PS or Ethernet dependency.
// The Vivado JTAG-to-AXI debug master is the only live host ingress.
module p6_jtag_top (
  output logic [1:0] ir_mode_out_0,
  input  logic [1:0] ir_rx_in_0,
  output logic [1:0] ir_sd_0,
  output logic [1:0] ir_tx_out_0,
  output logic [1:0] loop_mode_b0,
  input  logic [1:0] loop_rx_b0,
  output logic [1:0] loop_sd_b0,
  output logic [1:0] loop_tx_b0
);
  logic cfgmclk_raw;
  logic cfgmclk;
  logic eos;
  logic [31:0] m_axi_awaddr;
  logic [2:0] m_axi_awprot;
  logic m_axi_awvalid;
  logic m_axi_awready;
  logic [31:0] m_axi_wdata;
  logic [3:0] m_axi_wstrb;
  logic m_axi_wvalid;
  logic m_axi_wready;
  logic [1:0] m_axi_bresp;
  logic m_axi_bvalid;
  logic m_axi_bready;
  logic [31:0] m_axi_araddr;
  logic [2:0] m_axi_arprot;
  logic m_axi_arvalid;
  logic m_axi_arready;
  logic [31:0] m_axi_rdata;
  logic [1:0] m_axi_rresp;
  logic m_axi_rvalid;
  logic m_axi_rready;

  STARTUPE2 #(.PROG_USR("FALSE"), .SIM_CCLK_FREQ(0.0)) u_startupe2 (
    .CFGCLK(), .CFGMCLK(cfgmclk_raw), .EOS(eos), .PREQ(), .CLK(1'b0),
    .GSR(1'b0), .GTS(1'b0), .KEYCLEARB(1'b1), .PACK(1'b0),
    .USRCCLKO(1'b0), .USRCCLKTS(1'b1), .USRDONEO(1'b1), .USRDONETS(1'b1)
  );
  BUFG u_cfgmclk_bufg (.I(cfgmclk_raw), .O(cfgmclk));

  p6_jtag_axi_master u_jtag_axi (
    .aclk(cfgmclk), .aresetn(eos),
    .m_axi_awaddr, .m_axi_awprot, .m_axi_awvalid, .m_axi_awready,
    .m_axi_wdata, .m_axi_wstrb, .m_axi_wvalid, .m_axi_wready,
    .m_axi_bresp, .m_axi_bvalid, .m_axi_bready,
    .m_axi_araddr, .m_axi_arprot, .m_axi_arvalid, .m_axi_arready,
    .m_axi_rdata, .m_axi_rresp, .m_axi_rvalid, .m_axi_rready
  );

  p6_axi_peripheral u_p6_peripheral (
    .s_axi_aclk(cfgmclk), .s_axi_aresetn(eos),
    .s_axi_awaddr(m_axi_awaddr[11:0]), .s_axi_awprot(m_axi_awprot),
    .s_axi_awvalid(m_axi_awvalid), .s_axi_awready(m_axi_awready),
    .s_axi_wdata(m_axi_wdata), .s_axi_wstrb(m_axi_wstrb),
    .s_axi_wvalid(m_axi_wvalid), .s_axi_wready(m_axi_wready),
    .s_axi_bresp(m_axi_bresp), .s_axi_bvalid(m_axi_bvalid), .s_axi_bready(m_axi_bready),
    .s_axi_araddr(m_axi_araddr[11:0]), .s_axi_arprot(m_axi_arprot),
    .s_axi_arvalid(m_axi_arvalid), .s_axi_arready(m_axi_arready),
    .s_axi_rdata(m_axi_rdata), .s_axi_rresp(m_axi_rresp),
    .s_axi_rvalid(m_axi_rvalid), .s_axi_rready(m_axi_rready),
    .ir_mode_out_0, .ir_rx_in_0, .ir_sd_0, .ir_tx_out_0,
    .loop_mode_b0, .loop_rx_b0, .loop_sd_b0, .loop_tx_b0
  );
endmodule
