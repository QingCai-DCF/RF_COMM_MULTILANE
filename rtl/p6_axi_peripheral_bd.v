`timescale 1ns/1ps

// Verilog module-reference shim for Vivado IP Integrator.  The canonical
// implementation remains the SystemVerilog p6_axi_peripheral module.
module p6_axi_peripheral_bd (
  input         s_axi_aclk,
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
  output [1:0]  ir_mode_out_0,
  input  [1:0]  ir_rx_in_0,
  output [1:0]  ir_sd_0,
  output [1:0]  ir_tx_out_0,
  output [1:0]  loop_mode_b0,
  input  [1:0]  loop_rx_b0,
  output [1:0]  loop_sd_b0,
  output [1:0]  loop_tx_b0
);
  p6_axi_peripheral impl (
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
    .ir_mode_out_0(ir_mode_out_0), .ir_rx_in_0(ir_rx_in_0),
    .ir_sd_0(ir_sd_0), .ir_tx_out_0(ir_tx_out_0),
    .loop_mode_b0(loop_mode_b0), .loop_rx_b0(loop_rx_b0),
    .loop_sd_b0(loop_sd_b0), .loop_tx_b0(loop_tx_b0)
  );
endmodule
