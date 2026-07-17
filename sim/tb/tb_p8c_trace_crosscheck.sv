`timescale 1ns/1ps
module tb_p8c_trace_crosscheck;
  logic clk = 1'b0;
  always #5 clk = ~clk;
  logic rst_n, invalidate, clear_fault, charge, target_request;
  logic target_admit, hard_violation, throttle, hard_fault, history_valid, cooldown;
  logic [31:0] rolling, rolling_max, window_cycles, hard_limit, target_limit;
  logic [31:0] headroom, throttle_count, hard_count, cooldown_remaining, charge_count;

  ir_tfdu_exact_duty_accountant #(
    .CLOCK_HZ(1_000_000), .WINDOW_US(100),
    .HARD_PERCENT_STRICT_LT(20), .TARGET_PERCENT_MAX(18)
  ) dut (
    .clk, .rst_n, .history_invalidate_i(invalidate),
    .safety_fault_clear_i(clear_fault), .telemetry_clear_i(1'b0),
    .charge_i(charge), .target_request_i(target_request),
    .target_admit_next_o(target_admit), .hard_violation_next_o(hard_violation),
    .rolling_high_cycles_o(rolling), .rolling_high_cycles_max_seen_o(rolling_max),
    .rolling_window_cycles_o(window_cycles), .hard_limit_cycles_o(hard_limit),
    .target_limit_cycles_o(target_limit), .duty_headroom_cycles_o(headroom),
    .duty_target_throttle_o(throttle), .duty_target_throttle_count_o(throttle_count),
    .duty_hard_fault_o(hard_fault), .duty_hard_fault_count_o(hard_count),
    .duty_history_valid_o(history_valid), .duty_recovery_cooldown_active_o(cooldown),
    .duty_recovery_cooldown_remaining_o(cooldown_remaining),
    .actual_or_conservative_charge_count_o(charge_count)
  );

  integer cycle;
  initial begin
    rst_n = 1'b0; invalidate = 1'b0; clear_fault = 1'b0;
    charge = 1'b0; target_request = 1'b0;
    repeat (3) @(posedge clk);
    @(negedge clk); rst_n = 1'b1;
    for (cycle = 0; cycle < 250; cycle = cycle + 1) begin
      if (cycle != 0) @(negedge clk);
      invalidate = (cycle == 130);
      clear_fault = 1'b0;
      if (cycle >= 100 && cycle < 120)
        charge = 1'b1;
      else if (cycle >= 231)
        charge = ((cycle % 5) == 1);
      else
        charge = 1'b0;
      target_request = ((cycle % 3) == 0);
      @(posedge clk); #1;
      $display("P8C_TRACE,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",
        cycle, charge, target_request, invalidate, rolling, history_valid,
        cooldown_remaining, hard_fault, hard_count);
      if (history_valid && rolling * 100 >= window_cycles * 20 && !hard_fault)
        $fatal(1, "strict duty property escaped without sticky fault");
    end
    $display("P8C_TRACE_CROSSCHECK_RTL_PASS=1");
    $display("TB_P8C_TRACE_CROSSCHECK_PASS=1");
    $finish;
  end
endmodule
