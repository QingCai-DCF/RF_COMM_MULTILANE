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
  logic [0:0] j_axi_awid;
  logic [7:0] j_axi_awlen;
  logic [2:0] j_axi_awsize;
  logic [1:0] j_axi_awburst;
  logic j_axi_awlock;
  logic [3:0] j_axi_awcache;
  logic [3:0] j_axi_awqos;
  logic j_axi_wlast;
  logic [0:0] j_axi_arid;
  logic [7:0] j_axi_arlen;
  logic [2:0] j_axi_arsize;
  logic [1:0] j_axi_arburst;
  logic j_axi_arlock;
  logic [3:0] j_axi_arcache;
  logic [3:0] j_axi_arqos;
  logic j_axi_rlast;
  logic [0:0] j_axi_bid;
  logic [0:0] j_axi_rid;
  logic [31:0] j_axi_awaddr;
  logic [2:0] j_axi_awprot;
  logic j_axi_awvalid;
  logic j_axi_awready;
  logic [31:0] j_axi_wdata;
  logic [3:0] j_axi_wstrb;
  logic j_axi_wvalid;
  logic j_axi_wready;
  logic [1:0] j_axi_bresp;
  logic j_axi_bvalid;
  logic j_axi_bready;
  logic [31:0] j_axi_araddr;
  logic [2:0] j_axi_arprot;
  logic j_axi_arvalid;
  logic j_axi_arready;
  logic [31:0] j_axi_rdata;
  logic [1:0] j_axi_rresp;
  logic j_axi_rvalid;
  logic j_axi_rready;
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
    .m_axi_awid(j_axi_awid), .m_axi_awaddr(j_axi_awaddr),
    .m_axi_awlen(j_axi_awlen), .m_axi_awsize(j_axi_awsize),
    .m_axi_awburst(j_axi_awburst), .m_axi_awlock(j_axi_awlock),
    .m_axi_awcache(j_axi_awcache), .m_axi_awprot(j_axi_awprot),
    .m_axi_awqos(j_axi_awqos), .m_axi_awvalid(j_axi_awvalid),
    .m_axi_awready(j_axi_awready), .m_axi_wdata(j_axi_wdata),
    .m_axi_wstrb(j_axi_wstrb), .m_axi_wlast(j_axi_wlast),
    .m_axi_wvalid(j_axi_wvalid), .m_axi_wready(j_axi_wready),
    .m_axi_bid(j_axi_bid), .m_axi_bresp(j_axi_bresp),
    .m_axi_bvalid(j_axi_bvalid), .m_axi_bready(j_axi_bready),
    .m_axi_arid(j_axi_arid), .m_axi_araddr(j_axi_araddr),
    .m_axi_arlen(j_axi_arlen), .m_axi_arsize(j_axi_arsize),
    .m_axi_arburst(j_axi_arburst), .m_axi_arlock(j_axi_arlock),
    .m_axi_arcache(j_axi_arcache), .m_axi_arprot(j_axi_arprot),
    .m_axi_arqos(j_axi_arqos), .m_axi_arvalid(j_axi_arvalid),
    .m_axi_arready(j_axi_arready), .m_axi_rid(j_axi_rid),
    .m_axi_rdata(j_axi_rdata), .m_axi_rresp(j_axi_rresp),
    .m_axi_rlast(j_axi_rlast), .m_axi_rvalid(j_axi_rvalid),
    .m_axi_rready(j_axi_rready)
  );

  // Convert full AXI4 debug bursts into the existing, safety-reviewed
  // AXI4-Lite register peripheral.  JTAG AXI emits a single ID, so the
  // converter may omit ID ports and the response IDs are tied to zero.
  assign j_axi_bid = 1'b0;
  assign j_axi_rid = 1'b0;
  p6_axi_protocol_converter u_axi_protocol_converter (
    .aclk(cfgmclk), .aresetn(eos),
    .s_axi_awaddr(j_axi_awaddr), .s_axi_awlen(j_axi_awlen),
    .s_axi_awsize(j_axi_awsize), .s_axi_awburst(j_axi_awburst),
    .s_axi_awlock(j_axi_awlock), .s_axi_awcache(j_axi_awcache),
    .s_axi_awprot(j_axi_awprot), .s_axi_awregion(4'b0),
    .s_axi_awqos(j_axi_awqos), .s_axi_awvalid(j_axi_awvalid),
    .s_axi_awready(j_axi_awready), .s_axi_wdata(j_axi_wdata),
    .s_axi_wstrb(j_axi_wstrb), .s_axi_wlast(j_axi_wlast),
    .s_axi_wvalid(j_axi_wvalid), .s_axi_wready(j_axi_wready),
    .s_axi_bresp(j_axi_bresp), .s_axi_bvalid(j_axi_bvalid),
    .s_axi_bready(j_axi_bready), .s_axi_araddr(j_axi_araddr),
    .s_axi_arlen(j_axi_arlen), .s_axi_arsize(j_axi_arsize),
    .s_axi_arburst(j_axi_arburst), .s_axi_arlock(j_axi_arlock),
    .s_axi_arcache(j_axi_arcache), .s_axi_arprot(j_axi_arprot),
    .s_axi_arregion(4'b0), .s_axi_arqos(j_axi_arqos),
    .s_axi_arvalid(j_axi_arvalid), .s_axi_arready(j_axi_arready),
    .s_axi_rdata(j_axi_rdata), .s_axi_rresp(j_axi_rresp),
    .s_axi_rlast(j_axi_rlast), .s_axi_rvalid(j_axi_rvalid),
    .s_axi_rready(j_axi_rready),
    .m_axi_awaddr(m_axi_awaddr), .m_axi_awprot(m_axi_awprot),
    .m_axi_awvalid(m_axi_awvalid), .m_axi_awready(m_axi_awready),
    .m_axi_wdata(m_axi_wdata), .m_axi_wstrb(m_axi_wstrb),
    .m_axi_wvalid(m_axi_wvalid), .m_axi_wready(m_axi_wready),
    .m_axi_bresp(m_axi_bresp), .m_axi_bvalid(m_axi_bvalid),
    .m_axi_bready(m_axi_bready), .m_axi_araddr(m_axi_araddr),
    .m_axi_arprot(m_axi_arprot), .m_axi_arvalid(m_axi_arvalid),
    .m_axi_arready(m_axi_arready), .m_axi_rdata(m_axi_rdata),
    .m_axi_rresp(m_axi_rresp), .m_axi_rvalid(m_axi_rvalid),
    .m_axi_rready(m_axi_rready)
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
