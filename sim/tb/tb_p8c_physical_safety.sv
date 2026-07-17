`timescale 1ns/1ps
module tb_p8c_physical_safety;
  logic clk = 1'b0;
  always #5 clk = ~clk;

  logic rst_n;
  logic invalidate;
  logic clear_fault;
  logic sd_active;
  logic tx_request;
  logic txd;
  logic startup_done;
  logic [31:0] continuous;
  logic [31:0] longest;
  logic stuck_fault;
  logic [31:0] stuck_count;
  logic [31:0] stuck_kill_count;
  logic [31:0] rolling;
  logic [31:0] rolling_max;
  logic [31:0] headroom;
  logic target_throttle;
  logic [31:0] throttle_count;
  logic hard_fault;
  logic history_valid;
  logic cooldown;
  logic [31:0] cooldown_remaining;
  logic [31:0] rolling_before_short_sd;

  ir_tfdu_physical_module_safety #(
    .CLOCK_HZ(10_000_000),
    .STARTUP_US(1),
    .WINDOW_US(100),
    .HARD_PERCENT_STRICT_LT(20),
    .TARGET_PERCENT_MAX(18),
    .MAX_CONTINUOUS_HIGH_US(1)
  ) dut (
    .clk, .rst_n,
    .history_invalidate_i(invalidate),
    .safety_fault_clear_i(clear_fault),
    .telemetry_clear_i(1'b0),
    .sd_active_i(sd_active),
    .tx_request_i(tx_request),
    .txd_pre_final_o(txd),
    .startup_done_o(startup_done),
    .continuous_high_cycles_o(continuous),
    .longest_high_cycles_seen_o(longest),
    .stuck_high_fault_o(stuck_fault),
    .stuck_high_fault_count_o(stuck_count),
    .stuck_high_kill_count_o(stuck_kill_count),
    .rolling_high_cycles_o(rolling),
    .rolling_high_cycles_max_seen_o(rolling_max),
    .rolling_window_cycles_o(),
    .hard_limit_cycles_o(),
    .target_limit_cycles_o(),
    .duty_headroom_cycles_o(headroom),
    .duty_target_throttle_o(target_throttle),
    .duty_target_throttle_count_o(throttle_count),
    .duty_hard_fault_o(hard_fault),
    .duty_hard_fault_count_o(),
    .duty_history_valid_o(history_valid),
    .duty_recovery_cooldown_active_o(cooldown),
    .duty_recovery_cooldown_remaining_o(cooldown_remaining),
    .actual_or_conservative_charge_count_o()
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

  initial begin
    rst_n = 1'b0;
    invalidate = 1'b0;
    clear_fault = 1'b0;
    sd_active = 1'b0;
    tx_request = 1'b0;
    tick(2);
    rst_n = 1'b1;
    tick(1005);
    check_expect(history_valid && startup_done, "startup and history cooldown complete");

    tx_request = 1'b0;
    tick(1);
    check_expect(!txd, "zero-cycle request remains low");
    tx_request = 1'b1;
    tick(1);
    check_expect(txd && !stuck_fault, "one-cycle request is admitted");
    tx_request = 1'b0;
    tick(1);
    for (integer pulse_cycle = 0; pulse_cycle < 4; pulse_cycle = pulse_cycle + 1) begin
      tx_request = 1'b1;
      tick(1);
      check_expect(txd && !stuck_fault, "normal 4PPM-like pulse remains intact");
    end
    tx_request = 1'b0;
    tick(1);

    // MAX-1 and MAX cycles remain legal. The requested MAX+1 cycle is killed.
    tx_request = 1'b1;
    tick(9);
    check_expect(txd && !stuck_fault, "MAX-1 request remains active");
    tick(1);
    check_expect(txd && !stuck_fault, "MAX cycles remains allowed");
    tick(1);
    check_expect(!txd && stuck_fault, "MAX+1 requested cycle is killed and faulted");
    tick(9);
    check_expect(!txd && stuck_fault && stuck_count == 1,
                 "2*MAX very-long request remains killed without repeated fault events");
    tx_request = 1'b0;
    tick(2);
    check_expect(longest == 10 && stuck_count == 1 && stuck_kill_count == 1,
           "continuous-high telemetry records exact 1 us boundary");

    clear_fault = 1'b1;
    tick(1);
    clear_fault = 1'b0;
    check_expect(!stuck_fault && cooldown && cooldown_remaining == 1000,
           "stuck recovery begins full rolling-window cooldown");
    tx_request = 1'b1;
    tick(999);
    check_expect(!txd && !history_valid, "TX remains low throughout cooldown");
    tx_request = 1'b0;
    tick(1);
    check_expect(history_valid, "history valid after complete cooldown");

    tx_request = 1'b1;
    tick(1);
    tx_request = 1'b0;
    tick(1);
    rolling_before_short_sd = rolling;
    check_expect(rolling_before_short_sd == 1, "pre-SD physical charge is recorded");
    sd_active = 1'b1;
    tick(2);
    check_expect(!startup_done && !txd, "SD high forces Txd low and resets startup only");
    sd_active = 1'b0;
    tick(9);
    check_expect(!startup_done, "startup is not early");
    tick(1);
    check_expect(startup_done, "startup completes at exact 1 us reduced threshold");
    check_expect(rolling == rolling_before_short_sd && history_valid,
                 "short SD shutdown advances zeros without clearing duty history");

    // One-cycle requests at exactly 20 percent are shaped to <=18 percent.
    for (integer cycle = 0; cycle < 3000; cycle = cycle + 1) begin
      tx_request = ((cycle % 5) == 0);
      tick(1);
      check_expect(rolling <= 180, "target shaper never exceeds 18 percent");
      check_expect(!hard_fault, "normal shaper cannot reach hard fault");
    end
    tx_request = 1'b0;
    check_expect(throttle_count > 0 && rolling_max <= 180,
           "20-percent request stream was throttled to 18-percent target");

    tick(1001);
    sd_active = 1'b1;
    tick(1001);
    check_expect(!startup_done && !txd && history_valid && rolling == 0,
                 "SD longer than one window remains safe while old charge expires naturally");
    sd_active = 1'b0;
    tick(10);
    tx_request = 1'b1;
    tick(1);
    check_expect(txd, "fresh pulse is admitted after long SD and startup wait");
    rst_n = 1'b0;
    #1;
    check_expect(!txd, "reset asserted mid-high immediately forces Txd low");

    $display("P8C_MAX_CONTINUOUS_TXD_HIGH_LE_1US_PASS=1");
    $display("P8C_STUCK_HIGH_LATCH_KILL_PASS=1");
    $display("P8C_TARGET_SHAPER_PASS=1");
    $display("P8C_CONTINUOUS_VECTOR_MATRIX_PASS=1");
    $display("P8C_SD_HISTORY_PRESERVED_PASS=1");
    $display("TB_P8C_PHYSICAL_SAFETY_PASS=1");
    $finish;
  end
endmodule
