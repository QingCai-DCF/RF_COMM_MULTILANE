`timescale 1ns/1ps
`default_nettype none
`include "generated/ir_register_map_defs.svh"

module tb_p10_5_role_mask_commit;
  logic clk = 0;
  always #7.8125 clk = ~clk;
  logic rst_n = 0;

  logic [11:0] awaddr;
  logic awvalid;
  wire awready;
  logic [31:0] wdata;
  logic wvalid;
  wire wready;
  wire [1:0] bresp;
  wire bvalid;
  logic [11:0] araddr;
  logic arvalid;
  wire arready;
  wire [31:0] rdata;
  wire [1:0] rresp;
  wire rvalid;
  wire [3:0] mode_a, sd_a, txd_a, mode_b, sd_b, txd_b;
  wire full_shutdown;
  integer fmask;
  integer rmask;
  integer epoch_expected;

  p9_axi_dma_peripheral #(
    .DEPLOYMENT_ROLE(1), .LANE_COUNT(4), .WINDOW_SIZE(32),
    .SACK_BITS(32), .P10_5_DUAL_CAPABLE(1),
    .BUILD_ID(32'h5035_3446), .PROFILE_ID(32'h5035_4604)
  ) dut (
    .s_axi_aclk(clk), .s_axi_aresetn(rst_n),
    .s_axi_awaddr(awaddr), .s_axi_awprot(3'd0),
    .s_axi_awvalid(awvalid), .s_axi_awready(awready),
    .s_axi_wdata(wdata), .s_axi_wstrb(4'hf),
    .s_axi_wvalid(wvalid), .s_axi_wready(wready),
    .s_axi_bresp(bresp), .s_axi_bvalid(bvalid), .s_axi_bready(1'b1),
    .s_axi_araddr(araddr), .s_axi_arprot(3'd0),
    .s_axi_arvalid(arvalid), .s_axi_arready(arready),
    .s_axi_rdata(rdata), .s_axi_rresp(rresp), .s_axi_rvalid(rvalid),
    .s_axi_rready(1'b1),
    .s_axis_tvalid(1'b0), .s_axis_tready(), .s_axis_tdata(32'd0),
    .s_axis_tkeep(4'd0), .s_axis_tlast(1'b0),
    .m_axis_tvalid(), .m_axis_tready(1'b1), .m_axis_tdata(),
    .m_axis_tkeep(), .m_axis_tlast(), .stream_reset_request_o(),
    .ir_mode_out_0(mode_a), .ir_rx_in_0(4'hf), .ir_sd_0(sd_a),
    .ir_tx_out_0(txd_a), .loop_mode_b0(mode_b), .loop_rx_b0(4'hf),
    .loop_sd_b0(sd_b), .loop_tx_b0(txd_b),
    .monitor_valid_rx_frame_o(),
    .monitor_effective_full_shutdown_o(full_shutdown)
  );

  task automatic axi_write(input logic [11:0] address,
                           input logic [31:0] value);
    integer watchdog;
    begin
      @(negedge clk);
      awaddr = address;
      wdata = value;
      awvalid = 1;
      wvalid = 1;
      watchdog = 0;
      while (!(awready && wready) && watchdog < 20) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (!(awready && wready)) $fatal(1, "AXI write address/data timeout");
      @(negedge clk);
      awvalid = 0;
      wvalid = 0;
      watchdog = 0;
      while (!bvalid && watchdog < 20) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (!bvalid || bresp != 0) $fatal(1, "AXI write response failure");
      @(posedge clk);
    end
  endtask

  task automatic axi_read(input logic [11:0] address,
                          output logic [31:0] value);
    integer watchdog;
    begin
      @(negedge clk);
      araddr = address;
      arvalid = 1;
      watchdog = 0;
      while (!arready && watchdog < 20) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (!arready) $fatal(1, "AXI read address timeout");
      @(negedge clk);
      arvalid = 0;
      watchdog = 0;
      while (!rvalid && watchdog < 20) begin
        @(posedge clk); #1;
        watchdog = watchdog + 1;
      end
      if (!rvalid || rresp != 0) $fatal(1, "AXI read response failure");
      value = rdata;
      @(posedge clk);
    end
  endtask

  task automatic expect_reg(input logic [11:0] address,
                            input logic [31:0] expected,
                            input string label_text);
    logic [31:0] value;
    begin
      axi_read(address, value);
      if (value !== expected)
        $fatal(1, "%s expected=%08x observed=%08x",
               label_text, expected, value);
    end
  endtask

  initial begin
    awaddr = 0; awvalid = 0; wdata = 0; wvalid = 0;
    araddr = 0; arvalid = 0;
    repeat (8) @(posedge clk);
    rst_n = 1;
    repeat (5) @(posedge clk); #1;

    if (txd_a != 0 || txd_b != 0 || sd_a != 4'hf || !full_shutdown)
      $fatal(1, "P10.5 peripheral reset not fail closed");
    expect_reg(`IR_REG_P10_5_CAPS, 32'h5035_021f, "capability");
    expect_reg(`IR_REG_P10_5_VERSION, 32'h0001_0001, "version");

    // Overlap is rejected without changing any live role state.
    axi_write(`IR_REG_P10_5_MODE_SHADOW, 1);
    axi_write(`IR_REG_P10_5_ACTIVE_MASK_SHADOW, 4'hf);
    axi_write(`IR_REG_P10_5_F2R_MASK_SHADOW, 4'h3);
    axi_write(`IR_REG_P10_5_R2F_MASK_SHADOW, 4'h3);
    axi_write(`IR_REG_P10_5_ROLE_COMMIT, 32'hc05a_0001);
    expect_reg(`IR_REG_P10_5_ROLE_EPOCH, 0, "rejected epoch");
    expect_reg(`IR_REG_P10_5_ROLE_ERROR, 32'h5035_0003, "overlap error");
    expect_reg(`IR_REG_P10_5_ACTIVE_MASK, 0, "rejected active mask");
    expect_reg(`IR_REG_P10_5_ROLE_REJECT_COUNT, 1, "reject count");

    // Shadow writes remain invisible until the single atomic commit edge.
    axi_write(`IR_REG_P10_5_R2F_MASK_SHADOW, 4'hc);
    expect_reg(`IR_REG_P10_5_ACTIVE_MASK, 0, "pre-commit active mask");
    axi_write(`IR_REG_P10_5_ROLE_COMMIT, 32'hc05a_0001);
    expect_reg(`IR_REG_P10_5_ROLE_EPOCH, 1, "first role epoch");
    expect_reg(`IR_REG_P10_5_ACTIVE_MASK, 4'hf, "active mask");
    expect_reg(`IR_REG_P10_5_F2R_MASK, 4'h3, "F-to-R mask");
    expect_reg(`IR_REG_P10_5_R2F_MASK, 4'hc, "R-to-F mask");
    expect_reg(`IR_REG_P10_5_LOCAL_TX_MASK, 4'h3, "fixed local TX mask");
    expect_reg(`IR_REG_P10_5_LOCAL_RX_MASK, 4'hc, "fixed local RX mask");
    expect_reg(`IR_REG_P10_5_ROLE_COMMIT_COUNT, 1, "first commit count");

    axi_write(`IR_REG_P10_5_F2R_MASK_SHADOW, 4'hc);
    axi_write(`IR_REG_P10_5_R2F_MASK_SHADOW, 4'h3);
    expect_reg(`IR_REG_P10_5_F2R_MASK, 4'h3, "live mask before swap");
    axi_write(`IR_REG_P10_5_ROLE_COMMIT, 32'hc05a_0001);
    expect_reg(`IR_REG_P10_5_ROLE_EPOCH, 2, "second role epoch");
    expect_reg(`IR_REG_P10_5_LOCAL_TX_MASK, 4'hc, "swapped local TX mask");
    expect_reg(`IR_REG_P10_5_LOCAL_RX_MASK, 4'h3, "swapped local RX mask");
    expect_reg(`IR_REG_P10_5_ROLE_COMMIT_COUNT, 2, "second commit count");

    // Exhaust every ordered, nonempty, disjoint split.  This covers all
    // twelve 1+1, twelve 2+1, twelve 1+2 and six 2+2 assignments, plus the
    // legal 1+3/3+1 endpoints.  Every tuple becomes visible on exactly one
    // commit edge and is reflected in role-derived local TX/RX masks.
    epoch_expected = 2;
    for (fmask = 1; fmask < 16; fmask = fmask + 1) begin
      for (rmask = 1; rmask < 16; rmask = rmask + 1) begin
        if ((fmask & rmask) == 0) begin
          axi_write(`IR_REG_P10_5_ACTIVE_MASK_SHADOW, fmask | rmask);
          axi_write(`IR_REG_P10_5_F2R_MASK_SHADOW, fmask);
          axi_write(`IR_REG_P10_5_R2F_MASK_SHADOW, rmask);
          axi_write(`IR_REG_P10_5_ROLE_COMMIT, 32'hc05a_0001);
          epoch_expected = epoch_expected + 1;
          expect_reg(`IR_REG_P10_5_ROLE_EPOCH, epoch_expected,
                     "matrix role epoch");
          expect_reg(`IR_REG_P10_5_ACTIVE_MASK, fmask | rmask,
                     "matrix active mask");
          expect_reg(`IR_REG_P10_5_LOCAL_TX_MASK, fmask,
                     "matrix fixed local TX");
          expect_reg(`IR_REG_P10_5_LOCAL_RX_MASK, rmask,
                     "matrix fixed local RX");
        end
      end
    end

    // A bad key cannot partially update or advance the role generation.
    axi_write(`IR_REG_P10_5_ROLE_COMMIT, 32'h0000_0001);
    expect_reg(`IR_REG_P10_5_ROLE_EPOCH, epoch_expected,
               "bad-key epoch stable");
    expect_reg(`IR_REG_P10_5_ROLE_ERROR, 32'h5035_0001, "bad-key error");
    expect_reg(`IR_REG_P10_5_ROLE_REJECT_COUNT, 2, "final reject count");
    expect_reg(`IR_REG_P10_5_WIRE_SCHEMA, 32'h3528_1601, "wire schema");

    if (txd_a != 0 || txd_b != 0 || sd_a != 4'hf || !full_shutdown)
      $fatal(1, "role programming altered fail-closed physical outputs");
    $display("TB_P10_5_1PLUS1_MASK_MATRIX=PASS");
    $display("TB_P10_5_2PLUS1_MASK_MATRIX=PASS");
    $display("TB_P10_5_1PLUS2_MASK_MATRIX=PASS");
    $display("TB_P10_5_2PLUS2_PARTITIONS=PASS");
    $display("TB_P10_5_ROLE_MASK_COMMIT=PASS");
    $finish;
  end
endmodule

`default_nettype wire
