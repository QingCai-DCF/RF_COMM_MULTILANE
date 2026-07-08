`timescale 1ns/1ps
module tb_ir_axi_regs_new;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic wr_en;
  logic [11:0] wr_addr;
  logic [31:0] wr_data;
  logic rd_en;
  logic [11:0] rd_addr;
  logic [31:0] rd_data;
  logic rd_valid;
  logic core_reset_pulse;
  logic enable_phy;
  logic start_pulse;
  logic stop_pulse;
  logic clear_sticky_pulse;
  logic commit_pulse;
  logic profile_committed;
  logic [7:0] cfg_payload_lane_mask;
  logic [7:0] cfg_rx_lane_mask;
  logic [7:0] cfg_ack_lane_mask;
  logic [15:0] cfg_session;
  logic [31:0] commit_count;

  localparam logic [11:0] REG_CONTROL = 12'h000;
  localparam logic [11:0] REG_PROFILE_LANE_MASK = 12'h004;
  localparam logic [11:0] REG_PROFILE_RX_LANE_MASK = 12'h008;
  localparam logic [11:0] REG_PROFILE_ACK_LANE_MASK = 12'h00C;
  localparam logic [11:0] REG_PROFILE_SESSION = 12'h010;
  localparam logic [11:0] REG_TIMING_DETECT_WINDOW = 12'h028;
  localparam logic [11:0] REG_PROFILE_ID = 12'h0F0;

  ir_axi_regs_new dut (
    .clk(clk),
    .rst_n(rst_n),
    .wr_en(wr_en),
    .wr_addr(wr_addr),
    .wr_data(wr_data),
    .rd_en(rd_en),
    .rd_addr(rd_addr),
    .rd_data(rd_data),
    .rd_valid(rd_valid),
    .core_reset_pulse(core_reset_pulse),
    .enable_phy(enable_phy),
    .start_pulse(start_pulse),
    .stop_pulse(stop_pulse),
    .clear_sticky_pulse(clear_sticky_pulse),
    .commit_pulse(commit_pulse),
    .profile_committed(profile_committed),
    .cfg_payload_lane_mask(cfg_payload_lane_mask),
    .cfg_rx_lane_mask(cfg_rx_lane_mask),
    .cfg_ack_lane_mask(cfg_ack_lane_mask),
    .cfg_session(cfg_session),
    .cfg_payload_len(),
    .cfg_fragment_bytes(),
    .cfg_cnt_chip_max(),
    .cfg_cnt_preamble(),
    .cfg_detect_start(),
    .cfg_detect_end(),
    .cfg_guard_cycles(),
    .cfg_retry_timeout(),
    .cfg_startup_us(),
    .cfg_duty_window(),
    .cfg_duty_max_permille(),
    .cfg_stuck_high_limit_us(),
    .status_phy_ready(1'b1),
    .status_busy(1'b0),
    .status_tx_done(1'b0),
    .status_rx_done(1'b0),
    .status_tx_fail(1'b0),
    .status_retry_count(8'd0),
    .status_crc_bad_count(8'd0),
    .status_session_bad_count(8'd0),
    .status_mask_bad_count(8'd0),
    .safety_shutdown_reason(32'd0),
    .counter_tx_pulse(32'd11),
    .counter_rx_raw_pulse(32'd12),
    .counter_frame_good(32'd13),
    .counter_frame_bad(32'd14),
    .counter_ack_sent(32'd15),
    .counter_ack_seen(32'd16),
    .commit_count(commit_count),
    .debug_status()
  );

  task automatic check_expect(input bit cond, input string msg);
    if (!cond) begin
      $error("EXPECT_FAIL: %s", msg);
      $finish;
    end
  endtask

  task automatic tick(input int n);
    repeat (n) begin
      @(posedge clk);
      #1;
    end
  endtask

  task automatic write_reg(input logic [11:0] addr, input logic [31:0] data);
    begin
      wr_addr <= addr;
      wr_data <= data;
      wr_en <= 1'b1;
      tick(1);
      wr_en <= 1'b0;
      tick(1);
    end
  endtask

  task automatic write_control(input logic [31:0] data);
    begin
      wr_addr <= REG_CONTROL;
      wr_data <= data;
      wr_en <= 1'b1;
      tick(1);
      if (data[0]) check_expect(core_reset_pulse, "reset pulse generated");
      if (data[2]) check_expect(start_pulse, "start pulse generated");
      if (data[3]) check_expect(stop_pulse, "stop pulse generated");
      if (data[4]) check_expect(clear_sticky_pulse, "clear sticky pulse generated");
      if (data[5]) check_expect(commit_pulse, "commit pulse generated");
      wr_en <= 1'b0;
      tick(1);
    end
  endtask

  task automatic read_reg(input logic [11:0] addr, output logic [31:0] data);
    begin
      rd_addr <= addr;
      rd_en <= 1'b1;
      tick(1);
      rd_en <= 1'b0;
      data = rd_data;
      check_expect(rd_valid, "read valid asserted");
      tick(1);
    end
  endtask

  logic [31:0] value;

  initial begin
    rst_n = 1'b0;
    wr_en = 1'b0;
    wr_addr = 12'd0;
    wr_data = 32'd0;
    rd_en = 1'b0;
    rd_addr = 12'd0;
    tick(3);
    rst_n = 1'b1;
    tick(2);

    check_expect(cfg_payload_lane_mask == 8'h01, "default payload mask lane0");
    check_expect(cfg_ack_lane_mask == 8'h01, "default ack mask lane0");
    check_expect(cfg_session == 16'h2201, "default G1 session");

    write_reg(REG_PROFILE_LANE_MASK, 32'h0000_0001);
    write_reg(REG_PROFILE_RX_LANE_MASK, 32'h0000_0001);
    write_reg(REG_PROFILE_ACK_LANE_MASK, 32'h0000_0001);
    write_reg(REG_PROFILE_SESSION, 32'h0000_2201);
    write_reg(REG_TIMING_DETECT_WINDOW, 32'h0000_0700);
    write_control(32'h0000_0020);
    check_expect(profile_committed, "commit write is observable");
    check_expect(commit_count == 32'd1, "commit count increments");
    write_control(32'h0000_0002);
    check_expect(enable_phy, "enable PHY bit latches");
    write_control(32'h0000_0006);
    write_control(32'h0000_0008);

    read_reg(REG_PROFILE_SESSION, value);
    check_expect(value == 32'h0000_2201, "session readback matches write");
    read_reg(REG_PROFILE_ID, value);
    check_expect(value == 32'h4731_2201, "profile id exposed");

    $display("TB_IR_AXI_REGS_NEW_PASS=1");
    $finish;
  end
endmodule
