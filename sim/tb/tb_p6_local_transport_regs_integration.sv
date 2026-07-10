`timescale 1ns/1ps

module tb_p6_local_transport_regs_integration;
  logic clk = 1'b0;
  always #5 clk = ~clk;
  logic rst_n = 1'b0;
  logic wr_en, rd_en;
  logic [11:0] wr_addr, rd_addr;
  logic [31:0] wr_data, rd_data;
  logic rd_valid;
  logic engine_reset_pulse, engine_clear_pulse, engine_start_pulse, engine_stop_pulse, engine_shutdown_pulse, engine_enable_phy;
  logic [15:0] cfg_session, cfg_payload_len;
  logic [7:0] cfg_lane_mask, cfg_ack_lane_mask, cfg_pattern_id;
  logic [31:0] cfg_seed, cfg_timeout_cycles;
  logic [7:0] engine_tx_payload_read_index, engine_compare_payload_read_index;
  logic [7:0] engine_tx_payload_read_data, engine_compare_payload_read_data;
  logic [31:0] committed_payload_crc32;
  logic engine_ready = 1'b1;
  logic engine_busy = 1'b0;
  logic engine_done_pulse = 1'b0;
  logic engine_fail_pulse = 1'b0;
  logic engine_timeout_pulse = 1'b0;
  logic [31:0] engine_error_code = 32'd0;
  logic engine_rx_byte_write_pulse = 1'b0;
  logic [7:0] engine_rx_byte_write_index = 8'd0;
  logic [7:0] engine_rx_byte_write_data = 8'd0;
  logic [15:0] engine_rx_payload_len = 16'd0;
  logic [31:0] engine_rx_payload_crc32 = 32'd0;
  logic [31:0] engine_rx_digest = 32'd0;
  logic [1:0] engine_rx_good_mask = 2'b00;
  logic [31:0] engine_crc_bad_count = 0, engine_payload_mismatch_count = 0;
  logic [31:0] engine_retry_count = 0, engine_retry_exhausted_count = 0, engine_tx_fail_count = 0;
  logic [31:0] engine_txd_high_max = 0, engine_duty_violation_count = 0, engine_shutdown_reason = 0;
  logic [31:0] engine_tx_pulse_count = 0, engine_rx_raw_count = 0, engine_frame_good_count = 0, engine_frame_bad_count = 0;
  logic [31:0] engine_ack_sent_count = 0, engine_ack_seen_count = 0;
  logic [31:0] commit_count, debug_status;

  p6_local_transport_regs dut (.*);

  task automatic write_reg(input logic [11:0] address, input logic [31:0] value);
    @(posedge clk); #1; wr_addr = address; wr_data = value; wr_en = 1'b1;
    @(posedge clk); #1; wr_en = 1'b0;
  endtask

  task automatic read_reg(input logic [11:0] address, output logic [31:0] value);
    @(posedge clk); #1; rd_addr = address; rd_en = 1'b1;
    @(posedge clk); #1; rd_en = 1'b0; value = rd_data;
  endtask

  task automatic expect_eq(input logic [31:0] actual, input logic [31:0] expected, input string label);
    if (actual !== expected) begin
      $error("%s actual=%08x expected=%08x", label, actual, expected);
      $finish;
    end
  endtask

  task automatic configure(input logic [15:0] session, input logic [7:0] lane, input logic [7:0] ack, input logic [15:0] length);
    write_reg(12'h108, session);
    write_reg(12'h10c, lane);
    write_reg(12'h110, ack);
    write_reg(12'h114, length);
    write_reg(12'h15c, 32'd64000);
  endtask

  task automatic negative_case(
      input logic [15:0] session, input logic [7:0] lane, input logic [7:0] ack,
      input logic [31:0] expected_error, input string label);
    logic [31:0] value;
    write_reg(12'h100, 32'h1);
    write_reg(12'h200, 32'h000000a5);
    configure(session, lane, ack, 16'd1);
    write_reg(12'h100, 32'h4);
    read_reg(12'h104, value);
    if ((value & 32'h70) != 32'h70) begin $error("%s reject status=%08x", label, value); $finish; end
    read_reg(12'h160, value); expect_eq(value, expected_error, {label, " error"});
    read_reg(12'h164, value); expect_eq(value, 32'h1, {label, " sticky"});
    read_reg(12'h12c, value); expect_eq(value, 32'h0, {label, " no tx"});
    write_reg(12'h100, 32'h2);
    read_reg(12'h160, value); expect_eq(value, 32'h0, {label, " error clear"});
    read_reg(12'h164, value); expect_eq(value, 32'h0, {label, " sticky clear"});
  endtask

  initial begin
    logic [31:0] value;
    wr_en = 0; rd_en = 0; wr_addr = 0; rd_addr = 0; wr_data = 0;
    repeat (4) @(posedge clk);
    rst_n = 1'b1;

    write_reg(12'h200, 32'h04030201);
    configure(16'h2201, 8'h03, 8'h03, 16'd4);
    write_reg(12'h100, 32'h4);
    repeat (8) @(posedge clk);
    read_reg(12'h104, value);
    if ((value & 32'h6) != 32'h6) begin $error("commit status=%08x", value); $finish; end
    read_reg(12'h114, value); expect_eq(value, 32'd4, "payload length readback");
    read_reg(12'h200, value); expect_eq(value, 32'h04030201, "payload window readback");
    read_reg(12'h120, value); expect_eq(value, 32'hb63cfbcd, "payload CRC readback");
    write_reg(12'h100, 32'h8);
    for (int idx = 0; idx < 4; idx++) begin
      @(posedge clk); #1;
      engine_rx_byte_write_index = idx;
      engine_rx_byte_write_data = idx + 1;
      engine_rx_byte_write_pulse = 1'b1;
      @(posedge clk); #1; engine_rx_byte_write_pulse = 1'b0;
    end
    engine_rx_payload_len = 4;
    engine_rx_payload_crc32 = 32'hb63cfbcd;
    engine_rx_digest = 32'hb63cfbcd;
    engine_rx_good_mask = 2'b11;
    @(posedge clk); #1; engine_done_pulse = 1'b1;
    @(posedge clk); #1; engine_done_pulse = 1'b0;
    read_reg(12'h300, value); expect_eq(value, 32'h04030201, "RX payload window");
    read_reg(12'h128, value); expect_eq(value, 32'd4, "RX payload length");
    read_reg(12'h168, value); expect_eq(value, 32'hb63cfbcd, "RX digest");

    negative_case(16'h2202, 8'h01, 8'h01, 32'd1, "session mismatch");
    negative_case(16'h2201, 8'h03, 8'h01, 32'd3, "ack mask mismatch");
    negative_case(16'h2201, 8'h04, 8'h04, 32'd2, "lane mask greater than 0x3");
    $display("TB_P6_REGS_NEGATIVE_CASES=3");
    $display("TB_P6_REGS_INTEGRATION_PASS=1");
    $finish;
  end
endmodule
