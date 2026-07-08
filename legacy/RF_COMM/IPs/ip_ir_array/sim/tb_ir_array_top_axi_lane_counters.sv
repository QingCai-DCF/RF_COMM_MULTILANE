`timescale 1ns/1ps

interface axi_lite_if(input logic clk);
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
      awaddr  = '0;
      awvalid = 1'b0;
      wdata   = '0;
      wstrb   = 4'h0;
      wvalid  = 1'b0;
      bready  = 1'b0;
      araddr  = '0;
      arvalid = 1'b0;
      rready  = 1'b0;
    end
  endtask

  task automatic write(input logic [5:0] addr, input logic [31:0] data);
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
        if (wait_cycles > 128) begin
          $fatal(1, "AXI write ready timeout addr=0x%02x", addr);
        end
      end while (!(awready && wready));

      awvalid = 1'b0;
      wvalid  = 1'b0;

      wait_cycles = 0;
      do begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 128) begin
          $fatal(1, "AXI write response timeout addr=0x%02x", addr);
        end
      end while (!bvalid);

      @(negedge clk);
      bready = 1'b0;
      awaddr = '0;
      wdata  = '0;
      wstrb  = 4'h0;
    end
  endtask

  task automatic read(input logic [5:0] addr, output logic [31:0] data);
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
        if (wait_cycles > 128) begin
          $fatal(1, "AXI read address timeout addr=0x%02x", addr);
        end
      end while (!arready);

      arvalid = 1'b0;

      wait_cycles = 0;
      while (!rvalid) begin
        @(negedge clk);
        wait_cycles++;
        if (wait_cycles > 128) begin
          $fatal(1, "AXI read data timeout addr=0x%02x", addr);
        end
      end

      data = rdata;
      @(negedge clk);
      rready = 1'b0;
      araddr = '0;
    end
  endtask
endinterface

module tb_ir_array_top_axi_lane_counters;
  localparam int LANE_COUNT       = 4;
  localparam int MAX_PACKET_BYTES = 64;
  localparam int FRAGMENT_BYTES   = 16;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int CNT_CHIP_MAX     = 7;

  localparam logic [5:0] REG_CONTROL            = 6'h00;
  localparam logic [5:0] REG_STICKY             = 6'h10;
  localparam logic [5:0] REG_TX_LANE_COUNT      = 6'h2c;
  localparam logic [5:0] REG_RX_LANE_GOOD_COUNT = 6'h30;
  localparam logic [5:0] REG_RX_LANE_CRC_COUNT  = 6'h34;
  localparam logic [5:0] REG_RX_LANE_ERR_COUNT  = 6'h38;
  localparam logic [31:0] STICKY_ALL            = 32'h0000_01ff;

  logic clk;
  logic rst_n;
  logic s_axi_aresetn;

  axi_lite_if axi_a(clk);
  axi_lite_if axi_b(clk);

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
  byte rx_payload [0:15];
  int rx_count;

  always #7.8125 clk = ~clk; // 64 MHz PHY-side simulation clock.

  assign a_ir_rx_in = ~b_ir_tx_out;
  assign b_ir_rx_in = ~a_ir_tx_out;

  function automatic int packed_count_sum(input logic [31:0] value);
    begin
      packed_count_sum = value[7:0] + value[15:8] + value[23:16] + value[31:24];
    end
  endfunction

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

  task automatic wait_for_b_payload(input int length);
    int wait_cycles;
    begin
      wait_cycles = 0;
      while (rx_count < length) begin
        @(posedge clk);
        if (b_rx_valid && b_rx_ready) begin
          if (rx_count >= length) begin
            $fatal(1, "B received extra AXIS byte data=0x%02x", b_rx_data);
          end
          rx_payload[rx_count] = b_rx_data;
          rx_count++;
          if (b_rx_last && rx_count != length) begin
            $fatal(1, "B RX early TLAST exp=%0d got=%0d", length, rx_count);
          end
        end
        wait_cycles++;
        if (wait_cycles > 700000) begin
          $fatal(1,
            "Timeout waiting for AXI wrapper payload rx_count=%0d a_ready=%0b b_valid=%0b b_last=%0b",
            rx_count, a_tx_ready, b_rx_valid, b_rx_last);
        end
      end
      if (!b_rx_last) begin
        @(posedge clk);
      end
      for (int q = 0; q < length; q++) begin
        if (rx_payload[q] !== tx_payload[q]) begin
          $fatal(1, "Payload mismatch idx=%0d exp=0x%02x got=0x%02x",
            q, tx_payload[q], rx_payload[q]);
        end
      end
    end
  endtask

  task automatic expect_counter_nonzero(input string name, input logic [31:0] value);
    begin
      if (packed_count_sum(value) <= 0) begin
        $fatal(1, "%s did not increment, value=0x%08x", name, value);
      end
    end
  endtask

  task automatic expect_counter_zero(input string name, input logic [31:0] value);
    begin
      if (value !== 32'h0000_0000) begin
        $fatal(1, "%s expected zero, got=0x%08x", name, value);
      end
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
    .ir_mode_out(a_ir_mode_out)
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
    .ir_mode_out(b_ir_mode_out)
  );

  initial begin
    logic [31:0] a_tx_count;
    logic [31:0] a_rx_good_count;
    logic [31:0] a_rx_crc_count;
    logic [31:0] a_rx_err_count;
    logic [31:0] b_tx_count;
    logic [31:0] b_rx_good_count;
    logic [31:0] b_rx_crc_count;
    logic [31:0] b_rx_err_count;
    logic [31:0] a_tx_count_before_clear;
    logic [31:0] a_rx_good_count_before_clear;
    logic [31:0] b_tx_count_before_clear;
    logic [31:0] b_rx_good_count_before_clear;

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
    rx_count = 0;

    for (int i = 0; i < 16; i++) begin
      tx_payload[i] = 8'h80 + i;
      rx_payload[i] = 8'h00;
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    s_axi_aresetn = 1'b1;
    repeat (20) @(posedge clk);

    axi_a.write(REG_CONTROL, 32'h0000_0001);
    axi_b.write(REG_CONTROL, 32'h0000_0001);
    repeat (30) @(posedge clk);

    axis_send_a(16);
    wait_for_b_payload(16);
    repeat (12000) @(posedge clk);

    axi_a.read(REG_TX_LANE_COUNT, a_tx_count);
    axi_a.read(REG_RX_LANE_GOOD_COUNT, a_rx_good_count);
    axi_a.read(REG_RX_LANE_CRC_COUNT, a_rx_crc_count);
    axi_a.read(REG_RX_LANE_ERR_COUNT, a_rx_err_count);
    axi_b.read(REG_TX_LANE_COUNT, b_tx_count);
    axi_b.read(REG_RX_LANE_GOOD_COUNT, b_rx_good_count);
    axi_b.read(REG_RX_LANE_CRC_COUNT, b_rx_crc_count);
    axi_b.read(REG_RX_LANE_ERR_COUNT, b_rx_err_count);

    expect_counter_nonzero("A TX lane count", a_tx_count);
    expect_counter_nonzero("A RX ACK lane good count", a_rx_good_count);
    expect_counter_nonzero("B TX ACK lane count", b_tx_count);
    expect_counter_nonzero("B RX data lane good count", b_rx_good_count);
    expect_counter_zero("A RX CRC lane count", a_rx_crc_count);
    expect_counter_zero("A RX error lane count", a_rx_err_count);
    expect_counter_zero("B RX CRC lane count", b_rx_crc_count);
    expect_counter_zero("B RX error lane count", b_rx_err_count);

    a_tx_count_before_clear = a_tx_count;
    a_rx_good_count_before_clear = a_rx_good_count;
    b_tx_count_before_clear = b_tx_count;
    b_rx_good_count_before_clear = b_rx_good_count;

    axi_a.write(REG_STICKY, STICKY_ALL);
    axi_b.write(REG_STICKY, STICKY_ALL);
    repeat (40) @(posedge clk);

    axi_a.read(REG_TX_LANE_COUNT, a_tx_count);
    axi_a.read(REG_RX_LANE_GOOD_COUNT, a_rx_good_count);
    axi_b.read(REG_TX_LANE_COUNT, b_tx_count);
    axi_b.read(REG_RX_LANE_GOOD_COUNT, b_rx_good_count);

    expect_counter_zero("A TX lane count after clear", a_tx_count);
    expect_counter_zero("A RX good count after clear", a_rx_good_count);
    expect_counter_zero("B TX lane count after clear", b_tx_count);
    expect_counter_zero("B RX good count after clear", b_rx_good_count);

    $display(
      "AXI_TOP_LANE_COUNTERS_PASS a_tx=0x%08x a_rx_good=0x%08x b_tx=0x%08x b_rx_good=0x%08x bytes=%0d",
      a_tx_count_before_clear, a_rx_good_count_before_clear,
      b_tx_count_before_clear, b_rx_good_count_before_clear, rx_count);
    $finish;
  end
endmodule
