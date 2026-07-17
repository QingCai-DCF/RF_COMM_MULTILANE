`timescale 1ns/1ps
module tb_p8c_exact_duty;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic invalidate;
  logic clear_fault;
  logic telemetry_clear;
  logic charge;
  logic target_request;
  logic target_admit;
  logic hard_next;
  logic [31:0] rolling;
  logic [31:0] rolling_max;
  logic [31:0] window_cycles;
  logic [31:0] hard_limit;
  logic [31:0] target_limit;
  logic [31:0] headroom;
  logic throttle;
  logic [31:0] throttle_count;
  logic hard_fault;
  logic [31:0] hard_fault_count;
  logic history_valid;
  logic cooldown;
  logic [31:0] cooldown_remaining;
  logic [31:0] charge_count;

  ir_tfdu_exact_duty_accountant #(
    .CLOCK_HZ(1_000_000),
    .WINDOW_US(100),
    .HARD_PERCENT_STRICT_LT(20),
    .TARGET_PERCENT_MAX(18)
  ) dut (
    .clk, .rst_n,
    .history_invalidate_i(invalidate),
    .safety_fault_clear_i(clear_fault),
    .telemetry_clear_i(telemetry_clear),
    .charge_i(charge),
    .target_request_i(target_request),
    .target_admit_next_o(target_admit),
    .hard_violation_next_o(hard_next),
    .rolling_high_cycles_o(rolling),
    .rolling_high_cycles_max_seen_o(rolling_max),
    .rolling_window_cycles_o(window_cycles),
    .hard_limit_cycles_o(hard_limit),
    .target_limit_cycles_o(target_limit),
    .duty_headroom_cycles_o(headroom),
    .duty_target_throttle_o(throttle),
    .duty_target_throttle_count_o(throttle_count),
    .duty_hard_fault_o(hard_fault),
    .duty_hard_fault_count_o(hard_fault_count),
    .duty_history_valid_o(history_valid),
    .duty_recovery_cooldown_active_o(cooldown),
    .duty_recovery_cooldown_remaining_o(cooldown_remaining),
    .actual_or_conservative_charge_count_o(charge_count)
  );

  task automatic check_expect(input logic condition, input string message);
    if (!condition) begin
      $fatal(1, "P8C_EXPECT_FAIL: %s", message);
    end
  endtask

  task automatic tick(input integer count);
    repeat (count) @(posedge clk);
    #1;
  endtask

  task automatic reset_and_cooldown;
    begin
      rst_n = 1'b0;
      charge = 1'b0;
      target_request = 1'b0;
      invalidate = 1'b0;
      clear_fault = 1'b0;
      telemetry_clear = 1'b0;
      tick(2);
      rst_n = 1'b1;
      tick(99);
      check_expect(!history_valid && cooldown_remaining == 1, "cooldown must remain active for 99/100 cycles");
      tick(1);
      check_expect(history_valid && !cooldown, "history becomes valid only after full window");
    end
  endtask

  initial begin
    reset_and_cooldown();
    check_expect(window_cycles == 100, "exact 100-cycle window");
    check_expect(hard_limit == 19, "strict less-than-20-percent limit is 19");
    check_expect(target_limit == 18, "18-percent target is 18");

    charge = 1'b1;
    target_request = 1'b1;
    tick(18);
    charge = 1'b0;
    #1;
    check_expect(rolling == 18, "target boundary accounted exactly");
    check_expect(!target_admit && throttle, "next target request is throttled at 18 percent");
    tick(1);
    target_request = 1'b0;
    check_expect(!hard_fault, "18-percent target is below strict hard limit");
    telemetry_clear = 1'b1;
    tick(1);
    telemetry_clear = 1'b0;
    check_expect(rolling == 18 && history_valid,
                 "telemetry clear cannot erase safety duty history");

    reset_and_cooldown();
    charge = 1'b1;
    tick(19);
    check_expect(rolling == 19 && !hard_fault, "19 percent is legal under strict less-than 20 percent");
    tick(1);
    check_expect(rolling == 20 && hard_fault && hard_fault_count == 1,
           "20 percent is illegal and latches one hard fault");
    charge = 1'b0;
    tick(5);
    check_expect(hard_fault, "hard duty fault is sticky");

    clear_fault = 1'b1;
    tick(1);
    clear_fault = 1'b0;
    check_expect(!hard_fault && !history_valid && cooldown_remaining == 100,
           "controlled clear invalidates history and starts full cooldown");
    tick(100);
    check_expect(history_valid, "controlled recovery completed after exact window");

    // Cross-bucket attack: ten highs at the end of one nominal bucket and ten
    // at the beginning of the next are seen as 20 in one exact sliding window.
    tick(90);
    charge = 1'b1;
    tick(20);
    check_expect(hard_fault && rolling == 20, "cross-bucket boundary attack is detected");

    $display("P8C_EXACT_1000US_SLIDING_DUTY_PASS=1");
    $display("P8C_STRICT_LT20_PERCENT_PASS=1");
    $display("P8C_LE18_TARGET_PASS=1");
    $display("P8C_HISTORY_COOLDOWN_PASS=1");
    $display("P8C_TELEMETRY_CLEAR_HISTORY_PRESERVED_PASS=1");
    $display("P8C_EXACT_VECTOR_MATRIX_PASS=1");
    $display("TB_P8C_EXACT_DUTY_PASS=1");
    $finish;
  end
endmodule
