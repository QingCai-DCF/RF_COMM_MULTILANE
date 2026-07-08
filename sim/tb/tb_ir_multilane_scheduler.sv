`timescale 1ns/1ps
module tb_ir_multilane_scheduler;
  localparam int LANE_COUNT = 8;

  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic clear_sticky;
  logic commit_profile;
  logic [LANE_COUNT-1:0] requested_lane_enable_mask;
  logic [LANE_COUNT-1:0] requested_reliable_lane_mask;
  logic [LANE_COUNT-1:0] lane_fault_pulse;
  logic [LANE_COUNT-1:0] lane_recovered_pulse;
  logic [LANE_COUNT-1:0] requested_lane_enable_readback;
  logic [LANE_COUNT-1:0] requested_reliable_lane_readback;
  logic [LANE_COUNT-1:0] blocked_lane_mask;
  logic [LANE_COUNT-1:0] sticky_bad_lane_mask;
  logic [LANE_COUNT-1:0] effective_lane_enable_mask;
  logic [LANE_COUNT-1:0] effective_reliable_lane_mask;
  logic [LANE_COUNT-1:0] lane_enable_readback;
  logic [LANE_COUNT-1:0] reliable_lane_readback;
  logic lane1_reliable_blocked;
  logic fallback_to_lane0_active;
  logic no_reliable_lane_sticky;
  logic fault_isolated_pulse;
  logic [$clog2(LANE_COUNT)-1:0] selected_tx_lane;
  logic [$clog2(LANE_COUNT)-1:0] selected_ack_lane;

  ir_multilane_scheduler #(
    .LANE_COUNT(LANE_COUNT)
  ) dut (
    .clk(clk),
    .rst_n(rst_n),
    .clear_sticky(clear_sticky),
    .commit_profile(commit_profile),
    .requested_lane_enable_mask(requested_lane_enable_mask),
    .requested_reliable_lane_mask(requested_reliable_lane_mask),
    .lane_fault_pulse(lane_fault_pulse),
    .lane_recovered_pulse(lane_recovered_pulse),
    .requested_lane_enable_readback(requested_lane_enable_readback),
    .requested_reliable_lane_readback(requested_reliable_lane_readback),
    .blocked_lane_mask(blocked_lane_mask),
    .sticky_bad_lane_mask(sticky_bad_lane_mask),
    .effective_lane_enable_mask(effective_lane_enable_mask),
    .effective_reliable_lane_mask(effective_reliable_lane_mask),
    .lane_enable_readback(lane_enable_readback),
    .reliable_lane_readback(reliable_lane_readback),
    .lane1_reliable_blocked(lane1_reliable_blocked),
    .fallback_to_lane0_active(fallback_to_lane0_active),
    .no_reliable_lane_sticky(no_reliable_lane_sticky),
    .fault_isolated_pulse(fault_isolated_pulse),
    .selected_tx_lane(selected_tx_lane),
    .selected_ack_lane(selected_ack_lane),
    .debug_status()
  );

  task automatic expect(input bit cond, input string msg);
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

  task automatic commit(input logic [7:0] enable_mask, input logic [7:0] reliable_mask);
    begin
      requested_lane_enable_mask <= enable_mask;
      requested_reliable_lane_mask <= reliable_mask;
      commit_profile <= 1'b1;
      tick(1);
      commit_profile <= 1'b0;
      tick(1);
    end
  endtask

  initial begin
    rst_n = 1'b0;
    clear_sticky = 1'b0;
    commit_profile = 1'b0;
    requested_lane_enable_mask = 8'h00;
    requested_reliable_lane_mask = 8'h00;
    lane_fault_pulse = 8'h00;
    lane_recovered_pulse = 8'h00;
    tick(3);
    rst_n = 1'b1;
    tick(2);

    expect(lane_enable_readback == 8'h01, "default only enables lane0");
    expect(reliable_lane_readback == 8'h01, "default reliable mask is lane0");
    expect(blocked_lane_mask[1], "AB_L1 known-bad mask blocks lane1");
    expect(selected_tx_lane == 3'd0, "default selected lane is lane0");

    commit(8'h03, 8'h03);
    expect(requested_lane_enable_readback == 8'h03, "requested enable readback preserves profile");
    expect(lane_enable_readback == 8'h01, "lane1 is removed from effective enable mask");
    expect(lane1_reliable_blocked, "lane1 reliable enable request is blocked");

    commit(8'h02, 8'h02);
    expect(fallback_to_lane0_active, "lane1-only profile falls back to lane0");
    expect(lane_enable_readback == 8'h01, "fallback readback reports lane0");

    commit(8'h05, 8'h05);
    expect(lane_enable_readback == 8'h05, "lane0 and lane2 are allowed");
    expect(selected_tx_lane == 3'd0, "lowest healthy reliable lane is selected");
    lane_fault_pulse <= 8'h01;
    tick(1);
    expect(fault_isolated_pulse, "lane fault isolation pulse is observable");
    lane_fault_pulse <= 8'h00;
    tick(1);
    expect(sticky_bad_lane_mask[0], "lane0 fault becomes sticky");
    expect(lane_enable_readback == 8'h04, "lane2 remains after lane0 isolation");
    expect(selected_tx_lane == 3'd2, "scheduler falls forward to lane2");

    clear_sticky <= 1'b1;
    tick(1);
    clear_sticky <= 1'b0;
    tick(1);
    expect(sticky_bad_lane_mask == 8'h00, "clear_sticky clears bad lane mask");
    expect(lane_enable_readback == 8'h05, "clear restores committed healthy lanes");

    $display("TB_IR_MULTILANE_SCHEDULER_PASS=1");
    $finish;
  end
endmodule
