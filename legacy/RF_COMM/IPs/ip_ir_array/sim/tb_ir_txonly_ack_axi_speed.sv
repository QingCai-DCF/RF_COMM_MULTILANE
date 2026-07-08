`timescale 1ns/1ps

module tb_ir_txonly_ack_axi_speed;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 255;
  localparam int FRAGMENT_BYTES   = 255;
  localparam int MAX_FRAGS        = 1;
  localparam int RAW_BYTES        = 255;
  localparam int USER_BYTES       = 247;
  localparam int MIN_MBPS_X1000   = 2400;

  logic clk;
  logic rst_n;

  logic [5:0]  s_axi_awaddr;
  logic        s_axi_awvalid;
  logic        s_axi_awready;
  logic [31:0] s_axi_wdata;
  logic [3:0]  s_axi_wstrb;
  logic        s_axi_wvalid;
  logic        s_axi_wready;
  logic [1:0]  s_axi_bresp;
  logic        s_axi_bvalid;
  logic        s_axi_bready;
  logic [5:0]  s_axi_araddr;
  logic        s_axi_arvalid;
  logic        s_axi_arready;
  logic [31:0] s_axi_rdata;
  logic [1:0]  s_axi_rresp;
  logic        s_axi_rvalid;
  logic        s_axi_rready;

  logic [7:0] a_tx_data;
  logic       a_tx_valid;
  logic       a_tx_ready;
  logic       a_tx_last;
  logic [7:0] a_rx_data;
  logic       a_rx_valid;
  logic       a_rx_ready;
  logic       a_rx_last;

  logic [0:0] a_ir_tx_out;
  logic [0:0] a_ir_rx_in;
  logic [0:0] a_ir_sd;
  logic [0:0] a_ir_mode_out;

  wire b_ir_tx_out;
  wire b_ir_rx_in;
  wire b_ir_sd;
  wire b_ir_mode_out;
  wire [31:0] b_debug_status;

  byte tx_raw [0:RAW_BYTES-1];
  time start_time;
  time done_time;
  int tx_done_count;
  int b_rx_done_count;
  longint duration_ns;
  longint mbps_x1000;
  logic done_seen_d;

  always #7.8125 clk = ~clk;

  assign a_ir_rx_in[0] = ~b_ir_tx_out;
  assign b_ir_rx_in    = ~a_ir_tx_out[0];

  ir_txonly_ack_axi #(
    .LANE_COUNT(LANE_COUNT),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_RETRY(4),
    .CNT_CHIP_MAX(7),
    .CNT_PREAMBLE(64),
    .EOF_SILENCE_SYMS(3),
    .FRAG_TIMEOUT_CYCLES(50000),
    .POST_ACK_GUARD_CYCLES(4096),
    .MAX_FRAGS(MAX_FRAGS),
    .TX_ASYNC_FIFO_DEPTH(1024),
    .C_S_AXI_DATA_WIDTH(32),
    .C_S_AXI_ADDR_WIDTH(6)
  ) dut_a (
    .clk_phy(clk),
    .rst_n(rst_n),
    .s_axi_aclk(clk),
    .s_axi_aresetn(rst_n),
    .s_axi_awaddr(s_axi_awaddr),
    .s_axi_awvalid(s_axi_awvalid),
    .s_axi_awready(s_axi_awready),
    .s_axi_wdata(s_axi_wdata),
    .s_axi_wstrb(s_axi_wstrb),
    .s_axi_wvalid(s_axi_wvalid),
    .s_axi_wready(s_axi_wready),
    .s_axi_bresp(s_axi_bresp),
    .s_axi_bvalid(s_axi_bvalid),
    .s_axi_bready(s_axi_bready),
    .s_axi_araddr(s_axi_araddr),
    .s_axi_arvalid(s_axi_arvalid),
    .s_axi_arready(s_axi_arready),
    .s_axi_rdata(s_axi_rdata),
    .s_axi_rresp(s_axi_rresp),
    .s_axi_rvalid(s_axi_rvalid),
    .s_axi_rready(s_axi_rready),
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
    .ext_phy_dbg(b_debug_status)
  );

  ir_sink_b0_bd dut_b (
    .clk_phy(clk),
    .rst_n(rst_n),
    .ir_tx_out(b_ir_tx_out),
    .ir_rx_in(b_ir_rx_in),
    .ir_sd(b_ir_sd),
    .ir_mode_out(b_ir_mode_out),
    .debug_status(b_debug_status)
  );

  task automatic axi_write(input logic [5:0] addr, input logic [31:0] data);
    begin
      @(posedge clk);
      s_axi_awaddr  <= addr;
      s_axi_wdata   <= data;
      s_axi_wstrb   <= 4'hf;
      s_axi_awvalid <= 1'b1;
      s_axi_wvalid  <= 1'b1;
      s_axi_bready  <= 1'b1;
      wait (s_axi_awready && s_axi_wready);
      @(posedge clk);
      s_axi_awvalid <= 1'b0;
      s_axi_wvalid  <= 1'b0;
      wait (s_axi_bvalid);
      @(posedge clk);
      s_axi_bready  <= 1'b0;
    end
  endtask

  always @(posedge clk) begin
    if (!rst_n) begin
      done_seen_d <= 1'b0;
    end else begin
      done_seen_d <= dut_a.sticky_status_phy[0];
      if (dut_a.sticky_status_phy[0] && !done_seen_d) begin
        tx_done_count <= tx_done_count + 1;
        done_time = $time;
        $display("A_TXONLY_DONE t=%0t count=%0d status=%09b dbg=%08x",
          $time, tx_done_count + 1, dut_a.sticky_status_phy, dut_a.phy_lane0_dbg_phy);
      end
      if (dut_b.u_partner.rx_done_pulse) begin
        b_rx_done_count <= b_rx_done_count + 1;
        $display("B_RX_DONE t=%0t count=%0d dbg=%08x", $time, b_rx_done_count + 1, b_debug_status);
      end
    end
  end

  initial begin
    clk = 1'b0;
    rst_n = 1'b0;
    s_axi_awaddr = '0;
    s_axi_awvalid = 1'b0;
    s_axi_wdata = '0;
    s_axi_wstrb = 4'h0;
    s_axi_wvalid = 1'b0;
    s_axi_bready = 1'b0;
    s_axi_araddr = '0;
    s_axi_arvalid = 1'b0;
    s_axi_rready = 1'b0;
    a_tx_data = 8'h00;
    a_tx_valid = 1'b0;
    a_tx_last = 1'b0;
    a_rx_ready = 1'b1;
    tx_done_count = 0;
    b_rx_done_count = 0;
    done_seen_d = 1'b0;
    start_time = 0;
    done_time = 0;

    for (int k = 0; k < RAW_BYTES; k++) begin
      tx_raw[k] = k[7:0] ^ 8'ha6;
    end

    repeat (20) @(posedge clk);
    rst_n = 1'b1;
    repeat (20) @(posedge clk);

    axi_write(6'h04, 32'h00002201);
    axi_write(6'h08, 32'h00000001);
    axi_write(6'h28, 32'h00000001);
    axi_write(6'h10, 32'h000001ff);
    axi_write(6'h00, 32'h00000001);
    repeat (20) @(posedge clk);

    start_time = $time;
    for (int k = 0; k < RAW_BYTES; k++) begin
      @(posedge clk);
      a_tx_data  <= tx_raw[k];
      a_tx_valid <= 1'b1;
      a_tx_last  <= (k == RAW_BYTES - 1);
      wait (a_tx_ready);
    end
    @(posedge clk);
    a_tx_valid <= 1'b0;
    a_tx_last  <= 1'b0;

    repeat (1000000) begin
      @(posedge clk);
      if (dut_a.sticky_status_phy[2] || dut_a.sticky_status_phy[3] ||
          dut_a.sticky_status_phy[4] || dut_a.sticky_status_phy[5] ||
          dut_a.sticky_status_phy[7] || dut_a.sticky_status_phy[8]) begin
        $fatal(1, "A TX-only error sticky=%09b dbg=%08x", dut_a.sticky_status_phy, dut_a.phy_lane0_dbg_phy);
      end
      if (dut_b.u_partner.rx_protocol_error || dut_b.u_partner.rx_frame_overflow_any ||
          dut_b.u_partner.rx_crc_error_any || dut_b.u_partner.rx_overrun_error_any) begin
        $fatal(1,
          "B error flags: proto=%0b frame_ovf=%0b crc=%0b overrun=%0b dbg=%08x",
          dut_b.u_partner.rx_protocol_error, dut_b.u_partner.rx_frame_overflow_any,
          dut_b.u_partner.rx_crc_error_any, dut_b.u_partner.rx_overrun_error_any, b_debug_status);
      end

      if ((tx_done_count > 0) && (b_rx_done_count > 0)) begin
        duration_ns = done_time - start_time;
        mbps_x1000 = (USER_BYTES * 8 * 1000000) / duration_ns;
        if (mbps_x1000 < MIN_MBPS_X1000) begin
          $fatal(1, "TXONLY half-duplex speed too low: %0d.%03d Mbit/s duration_ns=%0d",
            mbps_x1000 / 1000, mbps_x1000 % 1000, duration_ns);
        end
        $display("IR_TXONLY_ACK_AXI_SPEED_PASS user_bytes=%0d raw_bytes=%0d duration_ns=%0d mbps=%0d.%03d tx_done=%0d b_rx_done=%0d",
          USER_BYTES, RAW_BYTES, duration_ns, mbps_x1000 / 1000, mbps_x1000 % 1000, tx_done_count, b_rx_done_count);
        $finish;
      end
    end

    $fatal(1, "Timeout waiting for TX-only speed tx_done=%0d b_rx_done=%0d a_dbg=%08x b_dbg=%08x",
      tx_done_count, b_rx_done_count, dut_a.phy_lane0_dbg_phy, b_debug_status);
  end
endmodule
