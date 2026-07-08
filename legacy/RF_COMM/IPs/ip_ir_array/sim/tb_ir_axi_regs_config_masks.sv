`timescale 1ns/1ps

module tb_ir_axi_regs_config_masks;
  localparam int LANE_COUNT = 4;
  localparam int MAX_FRAGS  = 4;

  logic clk;
  logic rst_n;
  logic [5:0] awaddr;
  logic awvalid;
  logic awready;
  logic [31:0] wdata;
  logic [3:0] wstrb;
  logic wvalid;
  logic wready;
  logic [1:0] bresp;
  logic bvalid;
  logic bready;
  logic [5:0] araddr;
  logic arvalid;
  logic arready;
  logic [31:0] rdata;
  logic [1:0] rresp;
  logic rvalid;
  logic rready;

  logic cfg_enable;
  logic [15:0] cfg_session_id;
  logic [LANE_COUNT-1:0] cfg_lane_enable_mask;
  logic [LANE_COUNT-1:0] cfg_rx_lane_enable_mask;
  logic cfg_commit_toggle;
  logic [8:0] sticky_clear_toggle;

  always #5 clk = ~clk;

  task automatic axi_write(input logic [5:0] addr, input logic [31:0] data);
    int wait_cycles;
    begin
      @(negedge clk);
      awaddr  = addr;
      wdata   = data;
      wstrb   = 4'hf;
      awvalid = 1'b1;
      wvalid  = 1'b1;
      bready  = 1'b1;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 32) begin
          $fatal(1, "Timeout waiting for AXI write ready addr=0x%02x", addr);
        end
      end while (!(awready && wready));

      awvalid = 1'b0;
      wvalid  = 1'b0;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 32) begin
          $fatal(1, "Timeout waiting for AXI write response addr=0x%02x", addr);
        end
      end while (!bvalid);

      @(negedge clk);
      bready = 1'b0;
      awaddr = '0;
      wdata  = '0;
    end
  endtask

  task automatic axi_read(input logic [5:0] addr, output logic [31:0] data);
    int wait_cycles;
    begin
      @(negedge clk);
      araddr  = addr;
      arvalid = 1'b1;
      rready  = 1'b1;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 32) begin
          $fatal(1, "Timeout waiting for AXI read address ready addr=0x%02x", addr);
        end
      end while (!arready);

      arvalid = 1'b0;

      wait_cycles = 0;
      while (!rvalid) begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 32) begin
          $fatal(1, "Timeout waiting for AXI read data addr=0x%02x", addr);
        end
      end

      data = rdata;
      @(negedge clk);
      rready = 1'b0;
      araddr = '0;
    end
  endtask

  task automatic expect_read(input logic [5:0] addr, input logic [31:0] expected, input string name);
    logic [31:0] got;
    begin
      axi_read(addr, got);
      if (got !== expected) begin
        $fatal(1, "%s mismatch exp=0x%08x got=0x%08x", name, expected, got);
      end
    end
  endtask

  ir_axi_regs #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_FRAGS(MAX_FRAGS)
  ) dut (
    .s_axi_aclk(clk),
    .s_axi_aresetn(rst_n),
    .s_axi_awaddr(awaddr),
    .s_axi_awvalid(awvalid),
    .s_axi_awready(awready),
    .s_axi_wdata(wdata),
    .s_axi_wstrb(wstrb),
    .s_axi_wvalid(wvalid),
    .s_axi_wready(wready),
    .s_axi_bresp(bresp),
    .s_axi_bvalid(bvalid),
    .s_axi_bready(bready),
    .s_axi_araddr(araddr),
    .s_axi_arvalid(arvalid),
    .s_axi_arready(arready),
    .s_axi_rdata(rdata),
    .s_axi_rresp(rresp),
    .s_axi_rvalid(rvalid),
    .s_axi_rready(rready),
    .cfg_enable(cfg_enable),
    .cfg_session_id(cfg_session_id),
    .cfg_lane_enable_mask(cfg_lane_enable_mask),
    .cfg_rx_lane_enable_mask(cfg_rx_lane_enable_mask),
    .cfg_commit_toggle(cfg_commit_toggle),
    .sticky_clear_toggle(sticky_clear_toggle),
    .tx_packet_active(1'b0),
    .tx_packet_loading(1'b0),
    .rx_ctx_valid(1'b0),
    .rx_ctx_complete(1'b0),
    .sticky_tx_done(1'b0),
    .sticky_rx_done(1'b0),
    .sticky_tx_overflow(1'b0),
    .sticky_tx_retry_exhausted(1'b0),
    .sticky_rx_header_error(1'b0),
    .sticky_rx_protocol_error(1'b0),
    .sticky_rx_frame_overflow(1'b0),
    .sticky_rx_crc_error(1'b0),
    .sticky_rx_overrun_error(1'b0),
    .lane_tx_busy_dbg(4'h0),
    .tx_frag_pending_dbg(4'h0),
    .tx_frag_inflight_dbg(4'h0),
    .tx_frag_acked_dbg(4'h0),
    .rx_recv_bitmap_dbg(4'h0),
    .tx_lane_count_dbg(32'h0403_0201),
    .rx_lane_good_count_dbg(32'h0807_0605),
    .rx_lane_crc_count_dbg(32'h0c0b_0a09),
    .rx_lane_err_count_dbg(32'h100f_0e0d)
  );

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    awaddr = '0;
    awvalid = 1'b0;
    wdata = '0;
    wstrb = '0;
    wvalid = 1'b0;
    bready = 1'b0;
    araddr = '0;
    arvalid = 1'b0;
    rready = 1'b0;

    repeat (5) @(posedge clk);
    rst_n = 1'b1;
    repeat (5) @(posedge clk);

    expect_read(6'h08, 32'h0000_000f, "default TX lane mask");
    expect_read(6'h28, 32'h0000_000f, "default RX lane mask");
    expect_read(6'h2c, 32'h0403_0201, "TX lane counter");
    expect_read(6'h30, 32'h0807_0605, "RX good lane counter");
    expect_read(6'h34, 32'h0c0b_0a09, "RX CRC lane counter");
    expect_read(6'h38, 32'h100f_0e0d, "RX error lane counter");
    if (cfg_lane_enable_mask !== 4'hf || cfg_rx_lane_enable_mask !== 4'hf) begin
      $fatal(1, "Default cfg masks mismatch tx=%0h rx=%0h",
        cfg_lane_enable_mask, cfg_rx_lane_enable_mask);
    end

    axi_write(6'h08, 32'h0000_0003);
    expect_read(6'h08, 32'h0000_0003, "legacy TX lane mask");
    expect_read(6'h28, 32'h0000_0003, "legacy mirrored RX lane mask");
    if (cfg_lane_enable_mask !== 4'h3 || cfg_rx_lane_enable_mask !== 4'h3) begin
      $fatal(1, "Legacy cfg masks mismatch tx=%0h rx=%0h",
        cfg_lane_enable_mask, cfg_rx_lane_enable_mask);
    end

    axi_write(6'h28, 32'h0000_000c);
    expect_read(6'h08, 32'h0000_0003, "independent TX lane mask");
    expect_read(6'h28, 32'h0000_000c, "independent RX lane mask");
    if (cfg_lane_enable_mask !== 4'h3 || cfg_rx_lane_enable_mask !== 4'hc) begin
      $fatal(1, "Independent cfg masks mismatch tx=%0h rx=%0h",
        cfg_lane_enable_mask, cfg_rx_lane_enable_mask);
    end

    $display("AXI_REGS_CONFIG_MASKS_PASS tx_mask=0x%0h rx_mask=0x%0h",
      cfg_lane_enable_mask, cfg_rx_lane_enable_mask);
    $finish;
  end
endmodule
