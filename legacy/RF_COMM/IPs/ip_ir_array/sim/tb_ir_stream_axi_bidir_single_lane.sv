`timescale 1ns/1ps

module tfdu_edge_channel_model_axi #(
  parameter int DELAY_CYCLES = 10,
  parameter int PULSE_CYCLES = 15
)(
  input  logic clk,
  input  logic rst_n,
  input  logic tx_in,
  output logic rx_out_n
);
  localparam int DELAY_W = (DELAY_CYCLES <= 0) ? 1 : DELAY_CYCLES;
  logic [DELAY_W:0] edge_pipe;
  logic tx_in_d;
  int unsigned low_count;
  logic delayed_edge;

  assign delayed_edge = edge_pipe[DELAY_W];

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      edge_pipe <= '0;
      tx_in_d   <= 1'b0;
      low_count <= 0;
      rx_out_n  <= 1'b1;
    end else begin
      tx_in_d <= tx_in;
      edge_pipe <= {edge_pipe[DELAY_W-1:0], tx_in && !tx_in_d};

      if (delayed_edge) begin
        low_count <= (PULSE_CYCLES > 0) ? (PULSE_CYCLES - 1) : 0;
      end else if (low_count != 0) begin
        low_count <= low_count - 1;
      end

      rx_out_n <= !(delayed_edge || (low_count != 0));
    end
  end
endmodule

module tb_ir_stream_axi_bidir_single_lane;
  localparam int LANE_COUNT       = 1;
  localparam int MAX_PACKET_BYTES = 96;
  localparam int FRAGMENT_BYTES   = 32;
  localparam int MAX_FRAGS        = (MAX_PACKET_BYTES + FRAGMENT_BYTES - 1) / FRAGMENT_BYTES;
  localparam int AB_LEN           = 90;
  localparam int BA_LEN           = 75;
  localparam int CNT_CHIP_MAX     = 15;
  localparam int BIDIR_BACKOFF_SLOT_CYCLES = 100000;

  logic clk_phy;
  logic s_axi_aclk;
  logic rst_n;
  logic s_axi_aresetn;

  logic [5:0] a_awaddr, b_awaddr;
  logic a_awvalid, b_awvalid;
  logic a_awready, b_awready;
  logic [31:0] a_wdata, b_wdata;
  logic [3:0] a_wstrb, b_wstrb;
  logic a_wvalid, b_wvalid;
  logic a_wready, b_wready;
  logic [1:0] a_bresp, b_bresp;
  logic a_bvalid, b_bvalid;
  logic a_bready, b_bready;
  logic [5:0] a_araddr, b_araddr;
  logic a_arvalid, b_arvalid;
  logic a_arready, b_arready;
  logic [31:0] a_rdata, b_rdata;
  logic [1:0] a_rresp, b_rresp;
  logic a_rvalid, b_rvalid;
  logic a_rready, b_rready;

  logic [7:0] a_tx_data, b_tx_data;
  logic a_tx_valid, b_tx_valid;
  logic a_tx_ready, b_tx_ready;
  logic a_tx_last, b_tx_last;
  logic [7:0] a_rx_data, b_rx_data;
  logic a_rx_valid, b_rx_valid;
  logic a_rx_ready, b_rx_ready;
  logic a_rx_last, b_rx_last;

  logic [LANE_COUNT-1:0] a_ir_tx_out, b_ir_tx_out;
  logic [LANE_COUNT-1:0] a_ir_rx_in, b_ir_rx_in;
  logic [LANE_COUNT-1:0] a_ir_sd, b_ir_sd;
  logic [LANE_COUNT-1:0] a_ir_mode_out, b_ir_mode_out;

  byte ab_payload [0:AB_LEN-1];
  byte ba_payload [0:BA_LEN-1];
  int a_rx_count;
  int b_rx_count;
  bit ab_ok;
  bit ba_ok;

  always #7.8125 clk_phy = ~clk_phy;
  always #5 s_axi_aclk = ~s_axi_aclk;

  tfdu_edge_channel_model_axi #(
    .DELAY_CYCLES(10),
    .PULSE_CYCLES(15)
  ) ch_b_to_a (
    .clk(clk_phy),
    .rst_n(rst_n),
    .tx_in(b_ir_tx_out[0]),
    .rx_out_n(a_ir_rx_in[0])
  );

  tfdu_edge_channel_model_axi #(
    .DELAY_CYCLES(10),
    .PULSE_CYCLES(15)
  ) ch_a_to_b (
    .clk(clk_phy),
    .rst_n(rst_n),
    .tx_in(a_ir_tx_out[0]),
    .rx_out_n(b_ir_rx_in[0])
  );

  task automatic axi_write_a(input [5:0] addr, input [31:0] data, input [3:0] strb);
    begin
      @(negedge s_axi_aclk);
      a_awaddr  = addr;
      a_wdata   = data;
      a_wstrb   = strb;
      a_awvalid = 1'b1;
      a_wvalid  = 1'b1;
      a_bready  = 1'b1;
      do @(posedge s_axi_aclk); while (!(a_awready && a_wready));
      @(negedge s_axi_aclk);
      a_awvalid = 1'b0;
      a_wvalid  = 1'b0;
      do @(posedge s_axi_aclk); while (!a_bvalid);
      @(negedge s_axi_aclk);
      a_bready = 1'b0;
    end
  endtask

  task automatic axi_write_b(input [5:0] addr, input [31:0] data, input [3:0] strb);
    begin
      @(negedge s_axi_aclk);
      b_awaddr  = addr;
      b_wdata   = data;
      b_wstrb   = strb;
      b_awvalid = 1'b1;
      b_wvalid  = 1'b1;
      b_bready  = 1'b1;
      do @(posedge s_axi_aclk); while (!(b_awready && b_wready));
      @(negedge s_axi_aclk);
      b_awvalid = 1'b0;
      b_wvalid  = 1'b0;
      do @(posedge s_axi_aclk); while (!b_bvalid);
      @(negedge s_axi_aclk);
      b_bready = 1'b0;
    end
  endtask

  task automatic axi_read_a(input [5:0] addr, output [31:0] data);
    begin
      @(negedge s_axi_aclk);
      a_araddr  = addr;
      a_arvalid = 1'b1;
      a_rready  = 1'b1;
      do @(posedge s_axi_aclk); while (!a_arready);
      @(negedge s_axi_aclk);
      a_arvalid = 1'b0;
      do @(posedge s_axi_aclk); while (!a_rvalid);
      data = a_rdata;
      @(negedge s_axi_aclk);
      a_rready = 1'b0;
    end
  endtask

  task automatic axi_read_b(input [5:0] addr, output [31:0] data);
    begin
      @(negedge s_axi_aclk);
      b_araddr  = addr;
      b_arvalid = 1'b1;
      b_rready  = 1'b1;
      do @(posedge s_axi_aclk); while (!b_arready);
      @(negedge s_axi_aclk);
      b_arvalid = 1'b0;
      do @(posedge s_axi_aclk); while (!b_rvalid);
      data = b_rdata;
      @(negedge s_axi_aclk);
      b_rready = 1'b0;
    end
  endtask

  task automatic dump_axi_status;
    begin
      $display("AXI_DEBUG A cfg_en=%0b session=%04x tx_mask=%b rx_mask=%b stream_dbg=%08x sticky_phy=%03x tx_lane=%08x rx_good=%08x rx_crc=%08x rx_err=%08x tx_fifo=%0b/%0b/%0b rx_fifo=%0b/%0b/%0b",
               dut_a.g_stream_full.u_stream_full.cfg_enable_phy,
               dut_a.g_stream_full.u_stream_full.cfg_session_id_phy,
               dut_a.g_stream_full.u_stream_full.cfg_lane_enable_mask_phy,
               dut_a.g_stream_full.u_stream_full.cfg_rx_lane_enable_mask_phy,
               dut_a.g_stream_full.u_stream_full.stream_debug_phy,
               dut_a.g_stream_full.u_stream_full.sticky_status_phy,
               dut_a.g_stream_full.u_stream_full.tx_lane_count_phy,
               dut_a.g_stream_full.u_stream_full.rx_lane_good_count_phy,
               dut_a.g_stream_full.u_stream_full.rx_lane_crc_count_phy,
               dut_a.g_stream_full.u_stream_full.rx_lane_err_count_phy,
               dut_a.g_stream_full.u_stream_full.tx_phy_tvalid,
               dut_a.g_stream_full.u_stream_full.tx_phy_tready,
               dut_a.g_stream_full.u_stream_full.tx_phy_tlast,
               dut_a.g_stream_full.u_stream_full.rx_phy_tvalid,
               dut_a.g_stream_full.u_stream_full.rx_phy_tready,
               dut_a.g_stream_full.u_stream_full.rx_phy_tlast);
      $display("AXI_DEBUG B cfg_en=%0b session=%04x tx_mask=%b rx_mask=%b stream_dbg=%08x sticky_phy=%03x tx_lane=%08x rx_good=%08x rx_crc=%08x rx_err=%08x tx_fifo=%0b/%0b/%0b rx_fifo=%0b/%0b/%0b",
               dut_b.g_stream_full.u_stream_full.cfg_enable_phy,
               dut_b.g_stream_full.u_stream_full.cfg_session_id_phy,
               dut_b.g_stream_full.u_stream_full.cfg_lane_enable_mask_phy,
               dut_b.g_stream_full.u_stream_full.cfg_rx_lane_enable_mask_phy,
               dut_b.g_stream_full.u_stream_full.stream_debug_phy,
               dut_b.g_stream_full.u_stream_full.sticky_status_phy,
               dut_b.g_stream_full.u_stream_full.tx_lane_count_phy,
               dut_b.g_stream_full.u_stream_full.rx_lane_good_count_phy,
               dut_b.g_stream_full.u_stream_full.rx_lane_crc_count_phy,
               dut_b.g_stream_full.u_stream_full.rx_lane_err_count_phy,
               dut_b.g_stream_full.u_stream_full.tx_phy_tvalid,
               dut_b.g_stream_full.u_stream_full.tx_phy_tready,
               dut_b.g_stream_full.u_stream_full.tx_phy_tlast,
               dut_b.g_stream_full.u_stream_full.rx_phy_tvalid,
               dut_b.g_stream_full.u_stream_full.rx_phy_tready,
               dut_b.g_stream_full.u_stream_full.rx_phy_tlast);
    end
  endtask

  task automatic send_a_packet;
    begin
      for (int k = 0; k < AB_LEN; k++) begin
        @(negedge s_axi_aclk);
        a_tx_data  = ab_payload[k];
        a_tx_valid = 1'b1;
        a_tx_last  = (k == AB_LEN - 1);
        do @(posedge s_axi_aclk); while (!a_tx_ready);
      end
      @(negedge s_axi_aclk);
      a_tx_valid = 1'b0;
      a_tx_last  = 1'b0;
      $display("STREAM_AXI_A_TO_B_QUEUED t=%0t len=%0d", $time, AB_LEN);
    end
  endtask

  task automatic send_b_packet;
    begin
      for (int k = 0; k < BA_LEN; k++) begin
        @(negedge s_axi_aclk);
        b_tx_data  = ba_payload[k];
        b_tx_valid = 1'b1;
        b_tx_last  = (k == BA_LEN - 1);
        do @(posedge s_axi_aclk); while (!b_tx_ready);
      end
      @(negedge s_axi_aclk);
      b_tx_valid = 1'b0;
      b_tx_last  = 1'b0;
      $display("STREAM_AXI_B_TO_A_QUEUED t=%0t len=%0d", $time, BA_LEN);
    end
  endtask

  always @(negedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      a_rx_ready <= 1'b1;
      b_rx_ready <= 1'b1;
    end else begin
      a_rx_ready <= (($time / 1000) % 7) != 2;
      b_rx_ready <= (($time / 1000) % 11) != 5;
    end
  end

  always @(posedge s_axi_aclk) begin
    if (!s_axi_aresetn) begin
      a_rx_count <= 0;
      b_rx_count <= 0;
      ab_ok <= 1'b0;
      ba_ok <= 1'b0;
    end else begin
      if (b_rx_valid && b_rx_ready) begin
        if (ab_ok) $fatal(1, "AXI A-to-B payload delivered more than once");
        if (b_rx_count >= AB_LEN) $fatal(1, "AXI A-to-B too many bytes");
        if (b_rx_data !== ab_payload[b_rx_count]) begin
          $fatal(1, "AXI A-to-B mismatch idx=%0d exp=%02x got=%02x",
                 b_rx_count, ab_payload[b_rx_count], b_rx_data);
        end
        b_rx_count <= b_rx_count + 1;
        if (b_rx_last) begin
          if ((b_rx_count + 1) != AB_LEN) $fatal(1, "AXI A-to-B length mismatch");
          ab_ok <= 1'b1;
          $display("STREAM_AXI_A_TO_B_OK t=%0t bytes=%0d", $time, b_rx_count + 1);
        end
      end

      if (a_rx_valid && a_rx_ready) begin
        if (ba_ok) $fatal(1, "AXI B-to-A payload delivered more than once");
        if (a_rx_count >= BA_LEN) $fatal(1, "AXI B-to-A too many bytes");
        if (a_rx_data !== ba_payload[a_rx_count]) begin
          $fatal(1, "AXI B-to-A mismatch idx=%0d exp=%02x got=%02x",
                 a_rx_count, ba_payload[a_rx_count], a_rx_data);
        end
        a_rx_count <= a_rx_count + 1;
        if (a_rx_last) begin
          if ((a_rx_count + 1) != BA_LEN) $fatal(1, "AXI B-to-A length mismatch");
          ba_ok <= 1'b1;
          $display("STREAM_AXI_B_TO_A_OK t=%0t bytes=%0d", $time, a_rx_count + 1);
        end
      end
    end
  end

  ir_array_top_axi #(
    .LANE_COUNT(LANE_COUNT),
    .STREAM_FULL_MODE(1),
    .STREAM_NODE_ID(0),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .MAX_FRAME_BYTES(14 + FRAGMENT_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(16),
    .RX_DETECT_START_CYCLES(2),
    .RX_DETECT_END_CYCLES(CNT_CHIP_MAX - 2),
    .RX_PREAMBLE_REALIGN_EDGE(0),
    .FRAG_TIMEOUT_CYCLES(120000),
    .TX_POST_ACK_GUARD_CYCLES(BIDIR_BACKOFF_SLOT_CYCLES),
    .RX_TO_TX_GUARD_CYCLES(2048)
  ) dut_a (
    .clk_phy(clk_phy), .rst_n(rst_n), .s_axi_aclk(s_axi_aclk), .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(a_awaddr), .s_axi_awvalid(a_awvalid), .s_axi_awready(a_awready),
    .s_axi_wdata(a_wdata), .s_axi_wstrb(a_wstrb), .s_axi_wvalid(a_wvalid), .s_axi_wready(a_wready),
    .s_axi_bresp(a_bresp), .s_axi_bvalid(a_bvalid), .s_axi_bready(a_bready),
    .s_axi_araddr(a_araddr), .s_axi_arvalid(a_arvalid), .s_axi_arready(a_arready),
    .s_axi_rdata(a_rdata), .s_axi_rresp(a_rresp), .s_axi_rvalid(a_rvalid), .s_axi_rready(a_rready),
    .s_axis_tx_tdata(a_tx_data), .s_axis_tx_tvalid(a_tx_valid), .s_axis_tx_tready(a_tx_ready), .s_axis_tx_tlast(a_tx_last),
    .m_axis_rx_tdata(a_rx_data), .m_axis_rx_tvalid(a_rx_valid), .m_axis_rx_tready(a_rx_ready), .m_axis_rx_tlast(a_rx_last),
    .ir_tx_out(a_ir_tx_out), .ir_rx_in(a_ir_rx_in), .ir_sd(a_ir_sd), .ir_mode_out(a_ir_mode_out),
    .ext_phy_dbg(32'h0000_0000)
  );

  ir_array_top_axi #(
    .LANE_COUNT(LANE_COUNT),
    .STREAM_FULL_MODE(1),
    .STREAM_NODE_ID(1),
    .MAX_PACKET_BYTES(MAX_PACKET_BYTES),
    .FRAGMENT_BYTES(FRAGMENT_BYTES),
    .MAX_FRAGS(MAX_FRAGS),
    .MAX_FRAME_BYTES(14 + FRAGMENT_BYTES),
    .CNT_CHIP_MAX(CNT_CHIP_MAX),
    .CNT_PREAMBLE(16),
    .RX_DETECT_START_CYCLES(2),
    .RX_DETECT_END_CYCLES(CNT_CHIP_MAX - 2),
    .RX_PREAMBLE_REALIGN_EDGE(0),
    .FRAG_TIMEOUT_CYCLES(120000),
    .TX_POST_ACK_GUARD_CYCLES(BIDIR_BACKOFF_SLOT_CYCLES),
    .RX_TO_TX_GUARD_CYCLES(2048)
  ) dut_b (
    .clk_phy(clk_phy), .rst_n(rst_n), .s_axi_aclk(s_axi_aclk), .s_axi_aresetn(s_axi_aresetn),
    .s_axi_awaddr(b_awaddr), .s_axi_awvalid(b_awvalid), .s_axi_awready(b_awready),
    .s_axi_wdata(b_wdata), .s_axi_wstrb(b_wstrb), .s_axi_wvalid(b_wvalid), .s_axi_wready(b_wready),
    .s_axi_bresp(b_bresp), .s_axi_bvalid(b_bvalid), .s_axi_bready(b_bready),
    .s_axi_araddr(b_araddr), .s_axi_arvalid(b_arvalid), .s_axi_arready(b_arready),
    .s_axi_rdata(b_rdata), .s_axi_rresp(b_rresp), .s_axi_rvalid(b_rvalid), .s_axi_rready(b_rready),
    .s_axis_tx_tdata(b_tx_data), .s_axis_tx_tvalid(b_tx_valid), .s_axis_tx_tready(b_tx_ready), .s_axis_tx_tlast(b_tx_last),
    .m_axis_rx_tdata(b_rx_data), .m_axis_rx_tvalid(b_rx_valid), .m_axis_rx_tready(b_rx_ready), .m_axis_rx_tlast(b_rx_last),
    .ir_tx_out(b_ir_tx_out), .ir_rx_in(b_ir_rx_in), .ir_sd(b_ir_sd), .ir_mode_out(b_ir_mode_out),
    .ext_phy_dbg(32'h0000_0000)
  );

  initial begin
    clk_phy = 1'b0;
    s_axi_aclk = 1'b0;
    rst_n = 1'b0;
    s_axi_aresetn = 1'b0;

    a_awaddr = '0; a_awvalid = 1'b0; a_wdata = '0; a_wstrb = '0; a_wvalid = 1'b0; a_bready = 1'b0;
    a_araddr = '0; a_arvalid = 1'b0; a_rready = 1'b0;
    b_awaddr = '0; b_awvalid = 1'b0; b_wdata = '0; b_wstrb = '0; b_wvalid = 1'b0; b_bready = 1'b0;
    b_araddr = '0; b_arvalid = 1'b0; b_rready = 1'b0;
    a_tx_data = 8'h00; a_tx_valid = 1'b0; a_tx_last = 1'b0;
    b_tx_data = 8'h00; b_tx_valid = 1'b0; b_tx_last = 1'b0;

    for (int k = 0; k < AB_LEN; k++) ab_payload[k] = byte'((k * 7 + 8'h2c) & 8'hff);
    for (int k = 0; k < BA_LEN; k++) ba_payload[k] = byte'((k * 11 + 8'h71) & 8'hff);

    repeat (40) @(posedge s_axi_aclk);
    rst_n = 1'b1;
    s_axi_aresetn = 1'b1;
    repeat (40) @(posedge s_axi_aclk);

    axi_write_a(6'h04, 32'h0000_60a5, 4'h3);
    axi_write_b(6'h04, 32'h0000_60a5, 4'h3);
    axi_write_a(6'h08, 32'h0000_0001, 4'hf);
    axi_write_b(6'h08, 32'h0000_0001, 4'hf);
    axi_write_a(6'h00, 32'h0000_0001, 4'h1);
    axi_write_b(6'h00, 32'h0000_0001, 4'h1);
    repeat (100) @(posedge s_axi_aclk);

    fork
      send_a_packet();
      send_b_packet();
    join

    repeat (4000000) begin
      @(posedge s_axi_aclk);
      if (ab_ok && ba_ok) begin
        $display("IR_STREAM_AXI_BIDIR_SINGLE_LANE_PASS a_to_b=%0d b_to_a=%0d", AB_LEN, BA_LEN);
        $finish;
      end
    end
    dump_axi_status();
    $fatal(1, "Timeout waiting for AXI stream bidir pass ab_ok=%0d ba_ok=%0d", ab_ok, ba_ok);
  end
endmodule
