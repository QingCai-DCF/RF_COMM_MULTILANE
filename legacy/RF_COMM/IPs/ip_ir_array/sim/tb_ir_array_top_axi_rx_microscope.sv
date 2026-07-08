`timescale 1ns/1ps

interface axi_lite_microscope_if(input logic clk);
  logic [5:0]  awaddr;
  logic        awvalid;
  logic        awready;
  logic [31:0] wdata;
  logic [3:0]  wstrb;
  logic        wvalid;
  logic        wready;
  logic [1:0]  bresp;
  logic        bvalid;
  logic        bready;
  logic [5:0]  araddr;
  logic        arvalid;
  logic        arready;
  logic [31:0] rdata;
  logic [1:0]  rresp;
  logic        rvalid;
  logic        rready;

  task automatic init();
    begin
      awaddr = '0;
      awvalid = 1'b0;
      wdata = '0;
      wstrb = 4'h0;
      wvalid = 1'b0;
      bready = 1'b0;
      araddr = '0;
      arvalid = 1'b0;
      rready = 1'b0;
    end
  endtask

  task automatic write(input logic [5:0] addr, input logic [31:0] data);
    int wait_cycles;
    begin
      @(negedge clk);
      awaddr = addr;
      wdata = data;
      wstrb = 4'hf;
      awvalid = 1'b1;
      wvalid = 1'b1;
      bready = 1'b1;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 128) $fatal(1, "AXI write ready timeout addr=0x%02x", addr);
      end while (!(awready && wready));

      awvalid = 1'b0;
      wvalid = 1'b0;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 128) $fatal(1, "AXI write response timeout addr=0x%02x", addr);
      end while (!bvalid);

      @(negedge clk);
      bready = 1'b0;
      awaddr = '0;
      wdata = '0;
      wstrb = 4'h0;
    end
  endtask

  task automatic read(input logic [5:0] addr, output logic [31:0] data);
    int wait_cycles;
    begin
      @(negedge clk);
      araddr = addr;
      arvalid = 1'b1;
      rready = 1'b1;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 128) $fatal(1, "AXI read address timeout addr=0x%02x", addr);
      end while (!arready);

      arvalid = 1'b0;

      wait_cycles = 0;
      while (!rvalid) begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 128) $fatal(1, "AXI read data timeout addr=0x%02x", addr);
      end

      data = rdata;
      @(negedge clk);
      rready = 1'b0;
      araddr = '0;
    end
  endtask
endinterface

module tb_ir_array_top_axi_rx_microscope;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int CNT_CHIP_MAX     = 7;

  localparam logic [5:0] REG_CONTROL            = 6'h00;
  localparam logic [5:0] REG_SESSION            = 6'h04;
  localparam logic [5:0] REG_STICKY             = 6'h10;
  localparam logic [5:0] REG_RX_LANE_GOOD_COUNT = 6'h30;
  localparam logic [5:0] REG_PHY_LANE0_DBG      = 6'h3c;

  logic clk;
  logic rst_n;
  logic s_axi_aresetn;

  axi_lite_microscope_if axi_a(clk);
  axi_lite_microscope_if axi_b(clk);

  logic [7:0] a_tx_data;
  logic       a_tx_valid;
  logic       a_tx_ready;
  logic       a_tx_last;
  logic [7:0] a_rx_data;
  logic       a_rx_valid;
  logic       a_rx_ready;
  logic       a_rx_last;

  logic [7:0] b_tx_data;
  logic       b_tx_valid;
  logic       b_tx_ready;
  logic       b_tx_last;
  logic [7:0] b_rx_data;
  logic       b_rx_valid;
  logic       b_rx_ready;
  logic       b_rx_last;

  logic [LANE_COUNT-1:0] a_ir_tx_out;
  logic [LANE_COUNT-1:0] a_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd;
  logic [LANE_COUNT-1:0] a_ir_mode_out;
  logic [LANE_COUNT-1:0] b_ir_tx_out;
  logic [LANE_COUNT-1:0] b_ir_rx_in;
  logic [LANE_COUNT-1:0] b_ir_sd;
  logic [LANE_COUNT-1:0] b_ir_mode_out;

  byte tx_payload [0:15];

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in = ~b_ir_tx_out;
  assign b_ir_rx_in = ~a_ir_tx_out;

  task automatic axis_send_a(input int length);
    begin
      for (int k = 0; k < length; k++) begin
        @(posedge clk);
        a_tx_data  <= tx_payload[k];
        a_tx_valid <= 1'b1;
        a_tx_last  <= (k == length - 1);
        wait (a_tx_ready);
      end
      @(posedge clk);
      a_tx_valid <= 1'b0;
      a_tx_last  <= 1'b0;
      a_tx_data  <= 8'h00;
    end
  endtask

  task automatic wait_for_session_mismatch_debug(
    output logic [31:0] sticky,
    output logic [31:0] rx_good,
    output logic [31:0] debug_word
  );
    int wait_cycles;
    begin
      sticky = 32'h0;
      rx_good = 32'h0;
      debug_word = 32'h0;
      wait_cycles = 0;
      while (wait_cycles < 650000) begin
        repeat (1000) @(posedge clk);
        wait_cycles += 1000;
        axi_b.read(REG_STICKY, sticky);
        axi_b.read(REG_RX_LANE_GOOD_COUNT, rx_good);
        axi_b.read(REG_PHY_LANE0_DBG, debug_word);
        if (((sticky & 32'h0000_0010) != 0) && (debug_word[31:24] == 8'hD4) && (rx_good[7:0] != 8'h00)) begin
          return;
        end
      end
      $fatal(1, "Timeout waiting for D4 session mismatch sticky=0x%08x rx_good=0x%08x debug=0x%08x",
        sticky, rx_good, debug_word);
    end
  endtask

  ir_array_top_axi #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .TX_ASYNC_FIFO_DEPTH(64),
    .RX_ASYNC_FIFO_DEPTH(64)
  ) dut_a (
    .clk_phy(clk),
    .rst_n(rst_n),
    .s_axi_aclk(clk),
    .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(axi_a.awaddr),
    .s_axi_awvalid(axi_a.awvalid),
    .s_axi_awready(axi_a.awready),
    .s_axi_wdata(axi_a.wdata),
    .s_axi_wstrb(axi_a.wstrb),
    .s_axi_wvalid(axi_a.wvalid),
    .s_axi_wready(axi_a.wready),
    .s_axi_bresp(axi_a.bresp),
    .s_axi_bvalid(axi_a.bvalid),
    .s_axi_bready(axi_a.bready),
    .s_axi_araddr(axi_a.araddr),
    .s_axi_arvalid(axi_a.arvalid),
    .s_axi_arready(axi_a.arready),
    .s_axi_rdata(axi_a.rdata),
    .s_axi_rresp(axi_a.rresp),
    .s_axi_rvalid(axi_a.rvalid),
    .s_axi_rready(axi_a.rready),
    .s_axis_tx_tdata(a_tx_data),
    .s_axis_tx_tvalid(a_tx_valid),
    .s_axis_tx_tready(a_tx_ready),
    .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data),
    .m_axis_rx_tvalid(a_rx_valid),
    .m_axis_rx_tready(a_rx_ready),
    .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out),
    .ir_rx_in(a_ir_rx_in),
    .ir_sd(a_ir_sd),
    .ir_mode_out(a_ir_mode_out),
    .ext_phy_dbg(32'h0000_0000)
  );

  ir_array_top_axi #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .TX_ASYNC_FIFO_DEPTH(64),
    .RX_ASYNC_FIFO_DEPTH(64)
  ) dut_b (
    .clk_phy(clk),
    .rst_n(rst_n),
    .s_axi_aclk(clk),
    .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(axi_b.awaddr),
    .s_axi_awvalid(axi_b.awvalid),
    .s_axi_awready(axi_b.awready),
    .s_axi_wdata(axi_b.wdata),
    .s_axi_wstrb(axi_b.wstrb),
    .s_axi_wvalid(axi_b.wvalid),
    .s_axi_wready(axi_b.wready),
    .s_axi_bresp(axi_b.bresp),
    .s_axi_bvalid(axi_b.bvalid),
    .s_axi_bready(axi_b.bready),
    .s_axi_araddr(axi_b.araddr),
    .s_axi_arvalid(axi_b.arvalid),
    .s_axi_arready(axi_b.arready),
    .s_axi_rdata(axi_b.rdata),
    .s_axi_rresp(axi_b.rresp),
    .s_axi_rvalid(axi_b.rvalid),
    .s_axi_rready(axi_b.rready),
    .s_axis_tx_tdata(b_tx_data),
    .s_axis_tx_tvalid(b_tx_valid),
    .s_axis_tx_tready(b_tx_ready),
    .s_axis_tx_tlast(b_tx_last),
    .m_axis_rx_tdata(b_rx_data),
    .m_axis_rx_tvalid(b_rx_valid),
    .m_axis_rx_tready(b_rx_ready),
    .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out),
    .ir_rx_in(b_ir_rx_in),
    .ir_sd(b_ir_sd),
    .ir_mode_out(b_ir_mode_out),
    .ext_phy_dbg(32'h0000_0000)
  );

  initial begin
    logic [31:0] sticky;
    logic [31:0] rx_good;
    logic [31:0] debug_word;

    clk = 1'b0;
    rst_n = 1'b0;
    s_axi_aresetn = 1'b0;
    axi_a.init();
    axi_b.init();
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    a_rx_ready = 1'b1;
    b_tx_data = 8'h00;
    b_tx_valid = 1'b0;
    b_tx_last = 1'b0;
    b_rx_ready = 1'b1;

    for (int i = 0; i < 16; i++) begin
      tx_payload[i] = 8'h40 + i;
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    s_axi_aresetn = 1'b1;
    repeat (20) @(posedge clk);

    axi_a.write(REG_SESSION, 32'h0000_2201);
    axi_b.write(REG_SESSION, 32'h0000_2203);
    axi_a.write(REG_CONTROL, 32'h0000_0001);
    axi_b.write(REG_CONTROL, 32'h0000_0001);
    repeat (30) @(posedge clk);

    axis_send_a(16);
    wait_for_session_mismatch_debug(sticky, rx_good, debug_word);

    if (debug_word[23:12] != 12'h201 || debug_word[11:0] != 12'h203) begin
      $fatal(1, "D4 payload did not preserve seen/expected session lows debug=0x%08x", debug_word);
    end

    $display(
      "AXI_RX_MICROSCOPE_SESSION_MISMATCH_PASS sticky=0x%08x rx_good=0x%08x debug=0x%08x",
      sticky, rx_good, debug_word);
    $finish;
  end
endmodule
