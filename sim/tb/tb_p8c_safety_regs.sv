`timescale 1ns/1ps
module tb_p8c_safety_regs;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n, wr_en, rd_en;
  logic [11:0] wr_addr, rd_addr;
  logic [31:0] wr_data, rd_data;
  logic rd_valid;
  logic arm, disarm, shutdown, clear_fault, snapshot, clear_telemetry;
  logic [63:0] rolling, rolling_max, headroom, throttle_count;
  logic [63:0] hard_count, continuous, longest, stuck_count, stuck_kill;
  logic [63:0] cooldown_remaining, charge_count, rx_count;
  logic [1:0] throttle_mask, hard_mask, stuck_mask, history_mask, cooldown_mask;

  `include "generated/ir_register_map_defs.svh"

  ir_p8c_safety_regs #(.PHYSICAL_MODULE_COUNT(2)) dut (
    .clk, .rst_n, .wr_en, .wr_addr, .wr_data, .rd_en, .rd_addr,
    .rd_data, .rd_valid,
    .endpoint_arm_request_o(arm),
    .endpoint_disarm_request_o(disarm),
    .full_shutdown_request_o(shutdown),
    .safety_fault_clear_request_o(clear_fault),
    .snapshot_request_o(snapshot),
    .telemetry_clear_request_o(clear_telemetry),
    .global_permit_raw_i(1'b1), .global_permit_sync_i(1'b1),
    .global_permit_effective_i(1'b0), .endpoint_armed_i(1'b0),
    .tx_kill_active_i(1'b1), .partial_frame_abort_block_i(1'b0),
    .endpoint_fatal_fault_i(1'b0), .arm_accept_pulse_i(1'b0),
    .arm_reject_pulse_i(1'b1), .arm_reject_reason_i(5'd7),
    .fault_clear_accept_pulse_i(1'b0),
    .global_permit_rise_count_i(32'd11),
    .global_permit_fall_count_i(32'd9),
    .global_permit_drop_during_frame_count_i(32'd4),
    .global_permit_rearm_count_i(32'd3),
    .last_global_permit_drop_reason_i(5'd2),
    .last_tx_kill_reason_i(5'd9),
    .bank_fault_mask_i(32'h0000_0100),
    .lane_tx_permit_mask_i(32'h0000_00ff),
    .effective_tx_enable_mask_i(32'h0000_0000),
    .physical_module_selected_mask_i(32'h0000_0002),
    .rolling_window_cycles_i(32'd64000),
    .hard_limit_cycles_i(32'd12799),
    .target_limit_cycles_i(32'd11520),
    .rolling_high_cycles_flat_i(rolling),
    .rolling_high_cycles_max_seen_flat_i(rolling_max),
    .duty_headroom_cycles_flat_i(headroom),
    .duty_target_throttle_count_flat_i(throttle_count),
    .duty_hard_fault_count_flat_i(hard_count),
    .continuous_high_cycles_flat_i(continuous),
    .longest_high_cycles_seen_flat_i(longest),
    .stuck_high_fault_count_flat_i(stuck_count),
    .stuck_high_kill_count_flat_i(stuck_kill),
    .cooldown_remaining_flat_i(cooldown_remaining),
    .charge_count_flat_i(charge_count),
    .rx_pulse_count_flat_i(rx_count),
    .duty_target_throttle_mask_i(throttle_mask),
    .duty_hard_fault_mask_i(hard_mask),
    .stuck_high_fault_mask_i(stuck_mask),
    .duty_history_valid_mask_i(history_mask),
    .cooldown_active_mask_i(cooldown_mask)
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) $fatal(1, "P8C_REG_EXPECT_FAIL: %s", message);
  endtask

  task automatic write_reg(input logic [11:0] address, input logic [31:0] value);
    begin
      @(negedge clk); wr_addr = address; wr_data = value; wr_en = 1'b1;
      @(posedge clk); #1; wr_en = 1'b0;
    end
  endtask

  task automatic read_reg(input logic [11:0] address, output logic [31:0] value);
    begin
      rd_addr = address; rd_en = 1'b1; #1; value = rd_data;
      check_expect(rd_valid, "read must be valid");
      rd_en = 1'b0;
    end
  endtask

  logic [31:0] value;
  initial begin
    rst_n = 1'b0; wr_en = 1'b0; rd_en = 1'b0; wr_addr = '0; wr_data = '0; rd_addr = '0;
    rolling = {32'd22, 32'd11}; rolling_max = {32'd44, 32'd33};
    headroom = {32'd11498, 32'd11509}; throttle_count = {32'd6, 32'd5};
    hard_count = {32'd8, 32'd7}; continuous = {32'd10, 32'd9};
    longest = {32'd12, 32'd11}; stuck_count = {32'd14, 32'd13};
    stuck_kill = {32'd16, 32'd15}; cooldown_remaining = {32'd18, 32'd17};
    charge_count = {32'd20, 32'd19}; rx_count = {32'd24, 32'd23};
    throttle_mask = 2'b10; hard_mask = 2'b10; stuck_mask = 2'b10;
    history_mask = 2'b11; cooldown_mask = 2'b00;
    repeat (3) @(posedge clk); rst_n = 1'b1; @(posedge clk); #1;

    read_reg(`IR_REG_P8C_PERMIT_STATUS, value);
    check_expect(value[4:0] == 5'b1_0011, "permit fields are status-driven and read-only");
    write_reg(`IR_REG_P8C_PERMIT_STATUS, 32'hffff_ffff);
    read_reg(`IR_REG_P8C_PERMIT_STATUS, value);
    check_expect(value[4:0] == 5'b1_0011, "write to permit status must be ignored");

    write_reg(`IR_REG_P8C_CONTROL,
      `IR_P8C_CONTROL_ENDPOINT_ARM_REQUEST_MASK |
      `IR_P8C_CONTROL_SNAPSHOT_REQUEST_MASK |
      `IR_P8C_CONTROL_TELEMETRY_CLEAR_REQUEST_MASK);
    check_expect(arm && snapshot && clear_telemetry, "control request pulses asserted");
    @(posedge clk); #1;
    check_expect(!arm && !snapshot && !clear_telemetry, "control requests are one-cycle pulses");

    write_reg(`IR_REG_P8C_SNAPSHOT_INDEX, 32'd1);
    write_reg(`IR_REG_P8C_CONTROL, `IR_P8C_CONTROL_SNAPSHOT_REQUEST_MASK);
    read_reg(`IR_REG_P8C_SNAPSHOT_ROLLING_HIGH, value);
    check_expect(value == 32'd22, "snapshot captures indexed physical module");
    rolling[63:32] = 32'd999;
    read_reg(`IR_REG_P8C_SNAPSHOT_ROLLING_HIGH, value);
    check_expect(value == 32'd22, "snapshot remains atomic after live input changes");
    read_reg(`IR_REG_P8C_SNAPSHOT_FLAGS, value);
    check_expect(value[4:0] == 5'b0_1111, "snapshot flags retain captured physical state");
    read_reg(`IR_REG_P8C_REGISTER_MAP_VERSION, value);
    check_expect(value == `IR_REGISTER_MAP_VERSION, "register map version exported");
    read_reg(`IR_REG_P8C_REGISTER_MAP_HASH_LOW, value);
    check_expect(value == `IR_REGISTER_MAP_HASH_LOW, "register map hash exported");

    write_reg(`IR_REG_P8C_CONTROL,
      `IR_P8C_CONTROL_ENDPOINT_DISARM_REQUEST_MASK |
      `IR_P8C_CONTROL_FULL_SHUTDOWN_REQUEST_MASK |
      `IR_P8C_CONTROL_SAFETY_FAULT_CLEAR_REQUEST_MASK);
    check_expect(disarm && shutdown && clear_fault, "remaining safety controls are requests");
    $display("P8C_REGISTER_RO_STATUS_PASS=1");
    $display("P8C_REGISTER_ATOMIC_SNAPSHOT_PASS=1");
    $display("TB_P8C_SAFETY_REGS_PASS=1");
    $finish;
  end
endmodule
