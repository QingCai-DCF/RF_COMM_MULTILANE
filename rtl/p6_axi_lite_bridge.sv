`timescale 1ns/1ps

module p6_axi_lite_bridge (
  input  logic         s_axi_aclk,
  input  logic         s_axi_aresetn,
  input  logic [11:0]  s_axi_awaddr,
  input  logic [2:0]   s_axi_awprot,
  input  logic         s_axi_awvalid,
  output logic         s_axi_awready,
  input  logic [31:0]  s_axi_wdata,
  input  logic [3:0]   s_axi_wstrb,
  input  logic         s_axi_wvalid,
  output logic         s_axi_wready,
  output logic [1:0]   s_axi_bresp,
  output logic         s_axi_bvalid,
  input  logic         s_axi_bready,
  input  logic [11:0]  s_axi_araddr,
  input  logic [2:0]   s_axi_arprot,
  input  logic         s_axi_arvalid,
  output logic         s_axi_arready,
  output logic [31:0]  s_axi_rdata,
  output logic [1:0]   s_axi_rresp,
  output logic         s_axi_rvalid,
  input  logic         s_axi_rready,

  output logic         reg_wr_en,
  output logic [11:0]  reg_wr_addr,
  output logic [31:0]  reg_wr_data,
  output logic         reg_rd_en,
  output logic [11:0]  reg_rd_addr,
  input  logic [31:0]  reg_rd_data,
  input  logic         reg_rd_valid
);
  logic aw_pending;
  logic w_pending;
  logic [11:0] awaddr_hold;
  logic [31:0] wdata_hold;
  logic [3:0] wstrb_hold;
  logic read_pending;

  assign s_axi_awready = !aw_pending && !s_axi_bvalid;
  assign s_axi_wready = !w_pending && !s_axi_bvalid;
  assign s_axi_arready = !read_pending && !s_axi_rvalid;

  always_ff @(posedge s_axi_aclk or negedge s_axi_aresetn) begin
    if (!s_axi_aresetn) begin
      aw_pending <= 1'b0;
      w_pending <= 1'b0;
      awaddr_hold <= 12'd0;
      wdata_hold <= 32'd0;
      wstrb_hold <= 4'd0;
      s_axi_bresp <= 2'b00;
      s_axi_bvalid <= 1'b0;
      reg_wr_en <= 1'b0;
      reg_wr_addr <= 12'd0;
      reg_wr_data <= 32'd0;
    end else begin
      reg_wr_en <= 1'b0;
      if (s_axi_awready && s_axi_awvalid) begin
        awaddr_hold <= s_axi_awaddr;
        aw_pending <= 1'b1;
      end
      if (s_axi_wready && s_axi_wvalid) begin
        wdata_hold <= s_axi_wdata;
        wstrb_hold <= s_axi_wstrb;
        w_pending <= 1'b1;
      end
      if (aw_pending && w_pending && !s_axi_bvalid) begin
        reg_wr_addr <= awaddr_hold;
        reg_wr_data <= wdata_hold;
        if (wstrb_hold == 4'hF) begin
          reg_wr_en <= 1'b1;
          s_axi_bresp <= 2'b00;
        end else begin
          s_axi_bresp <= 2'b10;
        end
        s_axi_bvalid <= 1'b1;
        aw_pending <= 1'b0;
        w_pending <= 1'b0;
      end
      if (s_axi_bvalid && s_axi_bready) s_axi_bvalid <= 1'b0;
    end
  end

  always_ff @(posedge s_axi_aclk or negedge s_axi_aresetn) begin
    if (!s_axi_aresetn) begin
      read_pending <= 1'b0;
      reg_rd_en <= 1'b0;
      reg_rd_addr <= 12'd0;
      s_axi_rdata <= 32'd0;
      s_axi_rresp <= 2'b00;
      s_axi_rvalid <= 1'b0;
    end else begin
      reg_rd_en <= 1'b0;
      if (s_axi_arready && s_axi_arvalid) begin
        reg_rd_addr <= s_axi_araddr;
        reg_rd_en <= 1'b1;
        read_pending <= 1'b1;
      end
      if (read_pending && reg_rd_valid) begin
        s_axi_rdata <= reg_rd_data;
        s_axi_rresp <= 2'b00;
        s_axi_rvalid <= 1'b1;
        read_pending <= 1'b0;
      end
      if (s_axi_rvalid && s_axi_rready) s_axi_rvalid <= 1'b0;
    end
  end

  logic unused_prot;
  assign unused_prot = ^{s_axi_awprot, s_axi_arprot};
endmodule
